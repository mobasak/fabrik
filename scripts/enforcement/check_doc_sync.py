#!/usr/bin/env python3
# AFTER-EDIT: none
"""Doc Sync Matrix enforcement — the single "did you update docs when code changed" gate.

One data-driven check, mirroring the CLAUDE.md Doc Sync Matrix. For each rule: if a
*trigger* file is in the staged change but the *target* doc is NOT staged → violation.
This is "touch-on-change" (the proven check_changelog model) — it forces the update,
it cannot verify the prose is correct (truth isn't mechanizable).

Reaches all three coders through final_gate: Claude Code Stop hook BLOCKS on it,
Cascade post_cascade_response surfaces it, Kilo runs it as its mandated final step.

Severity:
- ERROR (blocks): tight code↔doc links — CHANGELOG, CONFIGURATION, db/schema.sql.
- WARN (advisory): fuzzy links — INDEX (file add/remove), QUICKSTART (API routes),
  FEATURES (shape), PORTS (compose), SERVICES (compose), OPERATIONS (compose),
  RESILIENCE (retry/backoff patterns).

Consolidates: check_changelog, check_configuration_md, check_index_md (touch), and
check_openapi_sync. Exit codes: 0 = pass (incl. warnings only); 1 = an ERROR violation.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# ── significant-code definition (faithful to check_changelog.py) ──────────────
SIGNIFICANT_DIRS = ("src/", "scripts/", "templates/", ".factory/", ".github/")
SKIP_PATTERNS = (
    "tests/",
    "test_",
    "_test.py",
    ".test.ts",
    ".spec.ts",
    "__pycache__/",
    ".pytest_cache/",
    "node_modules/",
    ".venv/",
)
CODE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".sh"}
SIGNIFICANT_FILES = {"Dockerfile", "compose.yaml", "compose.yml"}
ROUTE_PATTERNS = (
    r"@app\.(get|post|put|patch|delete|options|head)\s*\(",
    r"@router\.(get|post|put|patch|delete|options|head)\s*\(",
    r"@api_router\.(get|post|put|patch|delete|options|head)\s*\(",
)
CHANGELOG_ENTRY_RE = re.compile(r"###\s+(Added|Changed|Fixed|Removed|Security|Deprecated)")
# \bfallback\b was dropped 2026-08-26 (web-ecommerce-factory upstream proposal, measured
# 4/4 prose false-positives — comments and operator-facing strings): a REAL code fallback
# almost always co-occurs with retry/backoff/max_retries/circuit-breaker, which still
# trigger; a WARN whose only correct response is to ignore it teaches scroll-past.
RESILIENCE_PATTERNS = (
    r"\bretry\b",
    r"\bbackoff\b",
    r"\bcircuit.?breaker\b",
    r"\bmax_retries\b",
)


def _git(args: list[str]) -> list[str]:
    # Fail-safe: a git error, a bad/unresolvable range, OR a timeout (a --range scan can be much wider
    # than a staged diff) → [] rather than an uncaught crash of this ERROR-tier, gate-blocking check.
    try:
        out = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=30
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return []
    return out.split("\n") if out else []


def _staged() -> list[str]:
    return _git(["diff", "--cached", "--name-only"])


def _added_removed_renamed() -> list[str]:
    return _git(["diff", "--cached", "--diff-filter=ADR", "--name-only"])


def _range(base_range: str) -> list[str]:
    """Changed files across a git range (e.g. ``<base>..HEAD``) — the whole-plan cumulative scope
    used by the ``--range`` coverage receipt (all the same trigger→doc logic, wider input set)."""
    return _git(["diff", base_range, "--name-only"])


def _range_adr(base_range: str) -> list[str]:
    return _git(["diff", base_range, "--diff-filter=ADR", "--name-only"])


def _skip(f: str) -> bool:
    return any(p in f for p in SKIP_PATTERNS)


def _is_tracked(path: str) -> bool:
    """True iff *path* is a git-tracked file — a committed doc that can drift.

    A doc-sync check should only fire when there is an actual tracked artifact to
    keep in sync. Projects that generate or gitignore their schema mirror
    (migrations are canonical; e.g. a web-nested `web/db/schema.sql`) have no
    committed root `db/schema.sql` to drift, so they are exempt.
    """
    try:
        return (
            subprocess.run(
                ["git", "ls-files", "--error-unmatch", path],
                capture_output=True,
                timeout=10,
            ).returncode
            == 0
        )
    except Exception:
        return False


def _schema_doc_for(path: str) -> str:
    """The schema dump that should mirror a migration/model change.

    Anchored on the migration's own ``db/`` tree, so a web-nested
    ``web/db/migrations/*.sql`` maps to ``web/db/schema.sql`` (not the repo-root
    one); falls back to the conventional repo-root ``db/schema.sql`` when the
    change isn't under a ``db/`` directory.
    """
    parts = path.split("/")
    # case-insensitive on the `db` component to match the (now case-insensitive) trigger detection —
    # a `Db/Migrations/x.sql` maps to its sibling `Db/schema.sql`, not the generic repo-root fallback.
    lower = [p.lower() for p in parts]
    if "db" in lower:
        i = lower.index("db")
        return "/".join(parts[: i + 1]) + "/schema.sql"
    return "db/schema.sql"


_ORM_MARKERS = re.compile(
    r"__tablename__|__table__|declarative_base|DeclarativeBase|mapped_column|\bColumn\(|\bTable\(|"
    r"\bregistry\(|\.mapped\b|models\.Model\b|\bSQLModel\b|db\.Entity\b|peewee|tortoise|django\.db",
)


def _staged_text(path: str) -> str | None:
    """The INDEX copy of ``path`` (`git show :path`), or None when the index has none
    (an intent-to-add, an unstaged file) — `_blob` is CHANGELOG-only by construction."""
    try:
        r = subprocess.run(["git", "show", f":{path}"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _is_orm_model(f: str) -> bool:
    """A file NAMED models.py is a schema trigger only when its CONTENT defines an ORM model.

    The filename alone fired on a pure-Pydantic `models.py` (one `min_length` change) and demanded
    `db/schema.sql` — a BLOCKING false positive that cost a real improvement (site-provisioner
    01M1QS9527Y8K0P9VPE9XF5MYB, 2026-09-05). The content graded is the STAGED blob (`:path`) — the
    gate grades the index, and a working-tree read would judge an edit made after staging (review
    of 3833fb16, pass 1); the working tree is the fallback when the index has no entry or only the
    empty intent-to-add blob. A directory hit
    (`models/`), a non-.py name (case-insensitive, like the filename regex) or an unreadable /
    deleted file keeps the old verdict: fail closed toward the schema demand.
    """
    p = Path(f)
    if p.is_dir() or p.suffix.lower() != ".py":
        return True
    text = _staged_text(f)
    if not text:
        # None: the index has no entry. '': an INTENT-TO-ADD entry — `git show :path` returns the
        # empty blob with rc 0, so a brand-new ORM file added with `git add -N` read as non-ORM
        # and drew no demand (review pass 2, executed). Either way the working tree decides.
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return True
    return bool(_ORM_MARKERS.search(text))


def _is_significant_code(f: str) -> bool:
    if _skip(f):
        return False
    in_dir = any(f.startswith(d) for d in SIGNIFICANT_DIRS)
    is_code = Path(f).suffix in CODE_EXTENSIONS
    return (in_dir and is_code) or Path(f).name in SIGNIFICANT_FILES


def _has_route_change(staged: list[str], diff_scope: list[str] | None = None) -> bool:
    """Did the CHANGE touch a route — not merely: does the file CONTAIN one?

    Scans the diff's added/removed lines, the way the resilience detector below already does
    ("so pre-existing retry code doesn't false-positive"). Reading whole file TEXT made every
    edit to a file that merely embeds route source read as an API change: `src/fabrik/scaffold.py`
    carries route templates for every scaffold type, so a one-line `SCRIPT_FILES` append raised
    "API route changed but docs/QUICKSTART.md not updated" — and QUICKSTART documents the
    `fabrik` CLI, which had not changed (mail 01M1H61P4CKFPX47CZGYKNM1EP; the same warning was
    then misattributed to sibling commits, because the receipt reasoned by PATH and the detector
    by CONTENT). A warning whose only correct response is to ignore it teaches scroll-past —
    the same reasoning that dropped ``\bfallback\b`` from RESILIENCE_PATTERNS.

    *diff_scope* is the ``git diff`` prefix the caller already computed (``["diff", "--cached"]``
    or ``["diff", "<range>"]``). Omitted → falls back to reading file text, so any caller that
    has no diff (a test, a future programmatic use) keeps the old, broader behaviour rather than
    silently detecting nothing.
    """
    for f in staged:
        if Path(f).suffix not in {".py", ".ts", ".tsx", ".js"} or _skip(f):
            continue
        if diff_scope is None:
            try:
                text = Path(f).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
        else:
            try:
                out = subprocess.run(
                    ["git", *diff_scope, "-U0", "--", f],
                    capture_output=True,
                    text=True,
                    timeout=20,
                ).stdout
            except (subprocess.SubprocessError, OSError):
                continue
            # Added/removed CONTENT only: the ``+++``/``---`` headers name the file and would
            # otherwise put every path through the route regexes.
            text = "\n".join(
                ln[1:]
                for ln in out.splitlines()
                if ln[:1] in {"+", "-"} and not ln.startswith(("+++", "---"))
            )
        if any(re.search(p, text) for p in ROUTE_PATTERNS):
            return True
    return False


def _unreleased_of(content: str) -> str | None:
    """The `## [Unreleased]` section of *content*, or None when there is no such heading."""
    start = content.find("## [Unreleased]")
    if start == -1:
        return None
    nxt = content.find("\n## [", start + 1)
    return content[start : (nxt if nxt != -1 else len(content))].strip()


def _blob(rev: str) -> str | None:
    """`<rev>:CHANGELOG.md` as text, or None when that revision has no such file.

    None means "cannot be read", never "empty" — every caller must treat it as an
    unanswerable question rather than as evidence.
    """
    try:
        r = subprocess.run(
            ["git", "show", f"{rev}:CHANGELOG.md"], capture_output=True, text=True, timeout=15
        )
    except Exception:
        return None
    return r.stdout if r.returncode == 0 else None


def _unreleased_untouched(rng: str | None) -> bool:
    """True only when this change PROVABLY left `## [Unreleased]` byte-identical.

    `_changelog_quality_ok` asks a question about the FILE — "does [Unreleased] hold a real
    entry" — which on a shared tree a sibling's entry answers green no matter what you did.
    Staging any cosmetic CHANGELOG edit (a typo in an old release section) therefore satisfied
    the ERROR row while the change carried no entry of its own. This asks the question about
    the CHANGE instead.

    Deliberately NOT "did it add a new `###` heading": a task that spans commits writes its
    entry once and extends that prose in later commits, which is correct and common (measured
    over 223 significant-code commits across 5 repos — 0 would fail this rule, 2 would fail the
    heading rule, and both of those 2 were legitimate extensions).

    Fails OPEN on every unreadable baseline. This feeds an ERROR row on a governance-sync
    surface that reaches ~46 repos, so an unanswerable question must never become a red.
    """
    if rng:
        # `A..B` / `A...B` — compare the range's own endpoints. An open end means HEAD.
        parts = rng.split("...") if "..." in rng else rng.split("..")
        if len(parts) != 2:
            return False
        old_rev, new_rev = parts[0].strip(), (parts[1].strip() or "HEAD")
        if not old_rev:
            return False
    else:
        old_rev, new_rev = "HEAD", ""  # "" == the index, i.e. `git show :CHANGELOG.md`
    old, new = _blob(old_rev), _blob(new_rev)
    if old is None or new is None:
        return False
    old_sec, new_sec = _unreleased_of(old), _unreleased_of(new)
    if new_sec is None:
        return False  # no [Unreleased] at all — _changelog_quality_ok owns that verdict
    return old_sec == new_sec


def _changelog_quality_ok() -> bool:
    """CHANGELOG [Unreleased] has a real ### entry, no placeholders (from check_changelog)."""
    p = Path("CHANGELOG.md")
    if not p.exists():
        return False
    content = p.read_text(encoding="utf-8", errors="replace")
    section = _unreleased_of(content)
    if section is None:
        return False
    # Strip fenced code blocks FIRST — a `### …` line that only appears inside a
    # ``` fence ``` (a template/example) is NOT a real changelog entry.
    defenced = re.sub(r"```.+?```", "", section, flags=re.DOTALL)

    # …and INLINE code spans: an entry that DOCUMENTS placeholder tokens (`todo`, `fixme`)
    # is describing them, not leaving unfinished work. Live shared-tree false positive
    # 2026-08-10 — a sibling's scanner entry listing "`example`/`dummy`/`todo`/`tbd`"
    # reddened the gate for every agent in the repo, and the entry was not theirs to edit.
    # Stripped AFTER the entry-shape check below reads `defenced`, so a `### …` heading
    # inside ticks still cannot fake an entry.
    # Inline code spans are QUOTATIONS. An entry that writes `todo`, `TODO: wire the alert`, or
    # `<brief title>` inside ticks is DESCRIBING those tokens — documenting a scanner, a code
    # comment, or the changelog template — not leaving the entry itself unfinished. This gate asks
    # one question: "is this [Unreleased] entry real, or a stub?" A quotation is real prose.
    #
    # Two failures got us here, and this framing resolves both. Stripping only whole-span BARE
    # tokens was too narrow: it rejected `todos` (plural — the detector has `s?`, the strip did
    # not), `# TODO` comments, and — self-inflicted, hub-RED for every agent — the CHANGELOG
    # paragraph describing THIS VERY FIX, which necessarily quotes the tokens it detects. A gate
    # that cannot describe its own behaviour is broken. Stripping EVERY span was too broad in one
    # specific way: backticks pair left-to-right, so a single stray tick earlier in the line
    # swallowed a plainly-written marker after it.
    #
    # So: strip spans PER LINE, and only where the line's backticks are BALANCED (even count).
    # An odd count means the pairing is ambiguous, so that line is left intact and its bare
    # markers still fire — fail-closed exactly where the ambiguity lives.
    def _strip_quotations(text: str) -> str:
        out = []
        for line in text.split("\n"):
            out.append(re.sub(r"`[^`]*`", "", line) if line.count("`") % 2 == 0 else line)
        return "\n".join(out)

    defenced_for_tokens = _strip_quotations(defenced)
    if not CHANGELOG_ENTRY_RE.search(defenced):
        return False
    # ⚠ The template-placeholder test below reads `defenced`, NOT the token-stripped text: a pasted
    # changelog template with `<brief title>` / `<description>` inside ticks is exactly the thing
    # that check exists to reject, and reading the stripped body let it through (native review).
    body = defenced_for_tokens.lower()
    # Strip dated escalations like `TODO(2026-07-22)` — those are valid
    # follow-up markers, not placeholders. Only bare `todo` / `fixme` are
    # unfinished-work signals.
    body = re.sub(r"todo\(\d{4}-\d{2}-\d{2}\)", "", body)
    # Strip the specific documentation-referring compound `dated-todo` (prose
    # naming the TODO-format convention, not an unfinished-work marker).
    # Require surrounds to be neither hyphens nor word chars, so it doesn't
    # match inside compounds like `updated-todo-list` or `pre-dated-todo-item`.
    body = re.sub(r"(?<![-\w])dated-todos?(?![-\w])", "", body)
    if any(ph in body for ph in ("<brief title>", "<description>")):
        return False
    # `todo` / `fixme` are unfinished-work markers when they stand as tokens —
    # separated from surrounding chars by non-letter (whitespace / hyphen /
    # punctuation / start-or-end of string). They are NOT placeholders when
    # they sit inside an unrelated word (`autodoc`, `photodocumentation`,
    # `fixmeup`). Use letter-only boundaries so hyphenated compounds like
    # `updated-todo-list` and `todo-cleanup` still flag (real placeholders),
    # but fused words don't.
    return not any(
        re.search(rf"(?<![a-zA-Z]){word}s?(?![a-zA-Z])", body) for word in ("todo", "fixme")
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Doc Sync Matrix gate (touch-on-change).")
    ap.add_argument(
        "--range",
        dest="rng",
        metavar="BASE..HEAD",
        help="check the CUMULATIVE diff of a git range instead of the staged diff "
        "(the whole-plan coverage receipt). Same trigger→doc rules; wider input set.",
    )
    # argv=None (a bare programmatic main() call) → parse NO args (staged mode), NOT sys.argv — so a
    # caller/test invoking main() never accidentally consumes the host process's argv. The CLI passes
    # sys.argv[1:] explicitly (see __main__).
    args = ap.parse_args(argv if argv is not None else [])
    rng = args.rng.strip() if args.rng is not None else None
    if args.rng is not None and not rng:
        # --range was passed but empty/whitespace: a coverage receipt must NOT silently fall back to
        # the staged diff (a false "clean"). Surface the caller's broken range as an error.
        print("ERROR: --range was given an empty value.")
        return 1
    # NOTE: --range reads file CONTENT (route/resilience/changelog-quality) from the WORKING TREE, so
    # it assumes the checkout is at the range's HEAD endpoint — true for the Finish-step receipt.
    if rng:
        staged = _range(rng)
        diff_scope = ["diff", rng]
    else:
        staged = _staged()
        diff_scope = ["diff", "--cached"]
    if not staged:
        return 0
    staged_set = set(staged)
    adr = set(_range_adr(rng)) if rng else set(_added_removed_renamed())

    errors: list[str] = []
    warnings: list[str] = []

    # ── ERROR rows (tight code↔doc links) ─────────────────────────────────────
    # CHANGELOG ← any significant code/infra change.
    sig = [f for f in staged if _is_significant_code(f)]
    if sig and "CHANGELOG.md" not in staged_set:
        errors.append(
            f"CHANGELOG.md not updated for {len(sig)} significant code/infra change(s) "
            f"(e.g. {sig[0]}). Add an entry under ## [Unreleased]."
        )
    elif sig and "CHANGELOG.md" in staged_set and not _changelog_quality_ok():
        errors.append(
            "CHANGELOG.md [Unreleased] is empty or has a placeholder — add a real "
            "### Added/Changed/Fixed entry."
        )
    elif sig and "CHANGELOG.md" in staged_set and _unreleased_untouched(rng):
        errors.append(
            "CHANGELOG.md was changed but its [Unreleased] section was not — this change has "
            "no entry of its own (a sibling's existing entry does not count). Add one under "
            "## [Unreleased], or extend the entry this task already wrote."
        )

    # CONFIGURATION ← .env.example changed.
    if ".env.example" in staged_set and "docs/CONFIGURATION.md" not in staged_set:
        errors.append("docs/CONFIGURATION.md not updated after .env.example changed.")

    # db/schema.sql ← DB models / migrations changed.
    schema_triggers = [
        f
        for f in staged
        if not _skip(f)
        # case-insensitive to match check_doc_stubs._schema (which doc_reconcile's Tier-1 loop reuses)
        # — else a `Db/Migrations/x.sql` would reconcile the data-contract but not fire this ERROR gate.
        and (
            (re.search(r"(^|/)models?(\.py|/)", f, re.IGNORECASE) and _is_orm_model(f))
            or "/migrations/" in f.lower()
            or "/alembic/" in f.lower()
        )
    ]
    # Each migration/model change must update ITS schema dump (the sibling in the
    # migration's own db/ tree, or root db/schema.sql by convention). A dump that
    # isn't git-tracked (a generated/gitignored mirror) has nothing to drift, so
    # it's exempt — migrations are then the canonical source.
    for _trig in schema_triggers:
        _doc = _schema_doc_for(_trig)
        if _doc not in staged_set and _is_tracked(_doc):
            errors.append(f"{_doc} not updated after a DB model/migration change (e.g. {_trig}).")
            break

    # ── WARN rows (fuzzy links — never block) ─────────────────────────────────
    # INDEX ← file added/removed/renamed. WARN (not ERROR): blocking every new file
    # is too aggressive; the auto-generated INDEX tree-map (docs_updater --check)
    # remains the structural enforcement.
    structural = [f for f in adr if not _skip(f)]
    if structural and "INDEX.md" not in staged_set:
        warnings.append(
            f"{len(structural)} file(s) added/removed/renamed (e.g. {structural[0]}) "
            "but INDEX.md not updated."
        )

    if _has_route_change(staged, diff_scope) and "docs/QUICKSTART.md" not in staged_set:
        warnings.append("API route changed but docs/QUICKSTART.md not updated (check it).")
    shape = [f for f in staged if f.startswith("specs/services/") and f.endswith(".yaml")]
    if shape and "docs/FEATURES.md" not in staged_set:
        warnings.append("Service shape/spec changed but docs/FEATURES.md not updated (check it).")
    compose_changed = any(Path(f).name in {"compose.yaml", "compose.yml"} for f in staged)
    if compose_changed and "PORTS.md" not in staged_set:
        warnings.append("compose changed but PORTS.md not updated (update if a port changed).")
    # SERVICES ← compose service added/removed (new worker, sidecar, etc.).
    if compose_changed and "docs/SERVICES.md" not in staged_set:
        warnings.append("compose service changed but docs/SERVICES.md not updated (check it).")
    # OPERATIONS ← compose changed; ops runbooks track per-service procedures.
    if compose_changed and "docs/OPERATIONS.md" not in staged_set:
        warnings.append("compose changed but docs/OPERATIONS.md not updated (check runbooks).")

    # RESILIENCE ← retry/backoff/circuit-breaker/fallback code changed. Inspect the
    # STAGED DIFF (not the whole file) so pre-existing retry code doesn't false-positive.
    resilience_touched = False
    for f in staged:
        if Path(f).suffix != ".py" or _skip(f):
            continue
        try:
            diff_text = subprocess.run(
                ["git", *diff_scope, "-U0", "--", f],
                capture_output=True,
                text=True,
                timeout=20,
            ).stdout
        except (subprocess.SubprocessError, OSError):
            continue
        if any(re.search(p, diff_text, re.IGNORECASE) for p in RESILIENCE_PATTERNS):
            resilience_touched = True
            break
    if resilience_touched and "docs/RESILIENCE.md" not in staged_set:
        warnings.append(
            "Retry/backoff/circuit-breaker code changed but docs/RESILIENCE.md not updated."
        )

    for w in warnings:
        print(f"WARNING: {w}")
    if errors:
        print("ERROR: Doc Sync Matrix — docs not updated alongside their code change:")
        for e in errors:
            print(f"  - {e}")
        print("\nUpdate the listed doc(s) in this change, or `git commit --no-verify` to bypass.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
