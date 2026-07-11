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
RESILIENCE_PATTERNS = (
    r"\bretry\b",
    r"\bbackoff\b",
    r"\bcircuit.?breaker\b",
    r"\bfallback\b",
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
    if "db" in parts:
        return "/".join(parts[: parts.index("db") + 1]) + "/schema.sql"
    return "db/schema.sql"


def _is_significant_code(f: str) -> bool:
    if _skip(f):
        return False
    in_dir = any(f.startswith(d) for d in SIGNIFICANT_DIRS)
    is_code = Path(f).suffix in CODE_EXTENSIONS
    return (in_dir and is_code) or Path(f).name in SIGNIFICANT_FILES


def _has_route_change(staged: list[str]) -> bool:
    for f in staged:
        if Path(f).suffix not in {".py", ".ts", ".tsx", ".js"} or _skip(f):
            continue
        try:
            text = Path(f).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if any(re.search(p, text) for p in ROUTE_PATTERNS):
            return True
    return False


def _changelog_quality_ok() -> bool:
    """CHANGELOG [Unreleased] has a real ### entry, no placeholders (from check_changelog)."""
    p = Path("CHANGELOG.md")
    if not p.exists():
        return False
    content = p.read_text(encoding="utf-8", errors="replace")
    start = content.find("## [Unreleased]")
    if start == -1:
        return False
    nxt = content.find("\n## [", start + 1)
    section = content[start : (nxt if nxt != -1 else len(content))].strip()
    # Strip fenced code blocks FIRST — a `### …` line that only appears inside a
    # ``` fence ``` (a template/example) is NOT a real changelog entry.
    defenced = re.sub(r"```.+?```", "", section, flags=re.DOTALL)
    if not CHANGELOG_ENTRY_RE.search(defenced):
        return False
    body = defenced.lower()
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

    # CONFIGURATION ← .env.example changed.
    if ".env.example" in staged_set and "docs/CONFIGURATION.md" not in staged_set:
        errors.append("docs/CONFIGURATION.md not updated after .env.example changed.")

    # db/schema.sql ← DB models / migrations changed.
    schema_triggers = [
        f
        for f in staged
        if not _skip(f)
        and (re.search(r"(^|/)models?(\.py|/)", f) or "/migrations/" in f or "/alembic/" in f)
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

    if _has_route_change(staged) and "docs/QUICKSTART.md" not in staged_set:
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
