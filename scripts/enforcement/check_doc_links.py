#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_check_doc_links.py docs/workflows/FINAL_GATE_WORKFLOW.md
"""Link integrity for the live docs tree — every repo-path reference must resolve.

Born from the 2026-07-20 docs-truth convergence, which found 668 broken (source,
target) pairs because nothing enforced links. This gate keeps the LIVE tree at zero:

- SOURCES: tracked ``docs/**/*.md`` (excluding ``docs/archive/**`` — archived docs
  are frozen history, their internal links are exempt) plus the root navigation
  files (INDEX.md, README.md, CLAUDE.md, AGENTS.md, agents-fabrik.md,
  agents-fabrik-core.md).
- TARGETS: markdown links and bare repo-path mentions (docs/, scripts/, src/,
  specs/, configs/, templates/, .windsurf/ prefixes with doc/code extensions),
  resolved both repo-root-relative and source-file-relative.
- EXEMPT: http(s) URLs, anchors-only links, placeholder/example paths, the
  project-context allowlist (doc names that exist in scaffolded PROJECTS, cited
  from synced/orchestrator docs — they are not hub paths), in a PROJECT the
  Fabrik-synced docs named by ``.fabrik/synced.lock`` as SOURCES (a linked
  worktree without its own lock reads the main checkout's), and
  ``docs/reference/LOCAL_LLM_INFRASTRUCTURE.md`` as a SOURCE (operator-excluded
  from the 2026-07-20 run; waiver removed with its deferred link fixups).

Exit 0 = zero broken references; exit 1 otherwise (Tier-2 blocking).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

REPO = Path(__file__).resolve().parents[2]

ROOT_SOURCES = [
    "INDEX.md",
    "README.md",
    "CLAUDE.md",
    "AGENTS.md",
    "agents-fabrik.md",
    "agents-fabrik-core.md",
]

# Doc names that live in scaffolded PROJECTS (cited from synced / orchestrator /
# workflow docs as project-side paths) — not hub files, never broken here.
PROJECT_CONTEXT_ALLOW = {
    "docs/DEPLOYMENT.md",
    "docs/OPERATIONS.md",
    "docs/RESILIENCE.md",
    "docs/data-contract.md",
    "docs/ui-design.md",
    "docs/flows.md",  # frozen journey contract (/fabrik-flows) — project-side artifact
    "docs/design-system.md",
    "docs/DATABASE_SCHEMA.md",
    "docs/FEATURES.md",  # exists hub-side too; harmless double-cover
    "docs/development/plans/00-research.md",
    "docs/preplan.md",
    "docs/multilingual-plan.md",
    "docs/reference/multilingual-plan.md",
    "docs/reference/scaffold-templates/FEATURES_TEMPLATE.md",
    "scripts/validate_i18n.py",
    "scripts/sync_rn_locales.py",  # i18n-kit adapter, scaffold-copied to projects
    "scripts/sync_docusaurus.py",  # i18n-kit adapter, scaffold-copied to projects
    "docs/lessons-learnt.md",  # legacy-tolerated project-side name (CLAUDE.md matrix)
    "docs/archive/README.md",  # scaffold-emitted per project; hub archive has none by design
    "docs/reference/opt-project-catalog.md",  # manifest DEST name in projects
    "scripts/ci_local.sh",
    "scripts/long_task.py",
    "db/schema.sql",
    "src/auth.py",
    "src/api.py",
    "src/main.py",
    "docs/FINANCIALS.md",
    "docs/API_REFERENCE.md",
    "docs/CHANGELOG.md",
    "docs/spec.md",
    "docs/user-guide/",
}

# Source files waived entirely (each with a reason + removal condition).
SOURCE_WAIVERS = {
    # Operator-excluded from the 2026-07-20 docs-truth run (live sibling WIP);
    # its :760/:762 links break transiently until the deferred fixups land.
    "docs/reference/LOCAL_LLM_INFRASTRUCTURE.md",
    # Live sibling-AI WIP spec (2026-07-20): forward-references files its own plan
    # will create. Waiver removed when that plan executes.
    "docs/superpowers/specs/2026-07-20-claude-p-first-class-scoring-design.md",
}

_PLACEHOLDER_RE = re.compile(
    r"[<>{}*]|YYYY|\bmy-api\b|\bmyservice\b|\bmy-service\b|\bmy-app\b|\bfoo\b"
    r"|example\.com|<your|\bNNN\b|\bxxx\b"
)

# CommonMark: the whitespace before a title and before `)` holds spaces or tabs and up to ONE line
# ending — `\r\n`, `\r` or `\n`, since check_doc_index reads INDEX.md as bytes (W-55905ee1); a blank
# line (two line endings) ends the link.
_LE = r"(?:\r\n|\r|\n)"
_WS1 = r"[ \t]*(?:" + _LE + r"[ \t]*)?"
# at least one whitespace before a title
_SEP = r"(?:[ \t]+(?:" + _LE + r"[ \t]*)?|" + _LE + r"[ \t]*)"
_TITLE_CLOSE_RE = re.compile(
    r"(?:"
    + _SEP
    + r"""(?:"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'|\((?:[^()\\\n]|\\.)*\)))?"""
    + _WS1
    + r"\)"
)
_ESCAPED_RE = re.compile(r"\\([!-/:-@\[-`{-~])")
_PUNCT = frozenset("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")  # CommonMark's escapable set
_BARE_RE = re.compile(
    r"(?<![\w/-])((?:docs|scripts|src|specs|configs|templates|\.windsurf)/"
    r"[A-Za-z0-9_./-]+?\.(?:md|py|sh|yaml|yml|json|txt))(?![\w.-])"
)


def _is_template_source(rel: str) -> bool:
    """Scaffold templates carry INTENTIONAL placeholder refs — to a project's OWN
    future files (`src/app/...`, `docs/DATA_MODEL.md`) that don't exist until the
    template is filled in. They are not broken links; they are the whole point of a
    template. In the hub these live under ``templates/`` (not scanned) or
    ``docs/archive/`` (already skipped), but in a scaffolded PROJECT they land under
    ``docs/`` (e.g. ``docs/reference/scaffold-templates/FEATURES_TEMPLATE.md``) and
    would false-flag every project — and the check is synced, so it can't be fixed
    locally. Excluded as SOURCES by the ``*_TEMPLATE.md`` naming and the
    ``scaffold-templates/`` dir. (Reported by the /opt/seo AI: 21 of 28 "broken"
    refs were template artifacts.)"""
    name = rel.rsplit("/", 1)[-1]
    return name.endswith("_TEMPLATE.md") or "scaffold-templates/" in rel


def _tracked_md_sources() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "docs/**/*.md", "docs/*.md"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.splitlines()
    # Scope = the live KNOWLEDGE tree. Excluded as sources: all archives (frozen
    # history), the plan/epic/review/spec pipeline artifacts (they cite future
    # deliverables and pre-migration paths by design), LESSONS_LEARNT.md (a dated
    # ledger — entries cite files as they were on the entry date), DECISIONS.md (an
    # immutable ledger — a row minted with a DRAFT plan cites files not yet made, and a
    # row whose cite later breaks can never be edited, so it redded every session's
    # gate: W-e9c8a4df; it stays a link TARGET), and scaffold TEMPLATES (intentional
    # placeholder refs — see _is_template_source).
    skip_prefixes = (
        "docs/archive/",
        "docs/infrastructure/archive/",
        "docs/development/",
        "docs/superpowers/",
    )
    srcs = [
        p
        for p in out
        if not p.startswith(skip_prefixes)
        and p not in ("docs/LESSONS_LEARNT.md", "docs/DECISIONS.md")
        and not _is_template_source(p)
    ]
    srcs += [p for p in ROOT_SOURCES if (REPO / p).exists()]
    # In a PROJECT, Fabrik-synced docs (gitignored, centrally distributed) are hub
    # CONTEXT, never a link-check target: their hub-relative refs cannot resolve
    # locally and cannot be fixed locally (synced-files gate forbids edits). The
    # lock records exactly what was distributed. A linked worktree created between two
    # syncs has the synced docs (.worktreeinclude copies them) but not the lock (the sync
    # writes it there only at the NEXT run, and only under .claude/worktrees/), so a
    # worktree without its own lock reads the MAIN checkout's — the same resolution
    # command_run.py uses to answer "is this repo synced". Anything occupying the
    # worktree's own lock path IS its lock: one that does not parse (or is a directory)
    # keeps today's no-exemption, and nothing falls through to the other copy.
    lock = REPO / ".fabrik" / "synced.lock"
    if not lock.exists():
        main = _main_checkout()
        if main is not None:
            lock = main / ".fabrik" / "synced.lock"
    if lock.exists():
        try:
            import json as _json

            synced = set(_json.loads(lock.read_text()))
            srcs = [p for p in srcs if p not in synced]
        except (ValueError, OSError):
            pass  # unreadable lock -> keep prior behavior
    return [REPO / p for p in sorted(set(srcs)) if str(Path(p)) not in SOURCE_WAIVERS]


def link_targets(text: str):
    """Yield the destination of every inline link in `text` as CommonMark reads it (W-dd091f0d).

    After `](`: an `<angle>` destination (no newline, no unescaped `<` or `>`) or a bare one with
    BALANCED parentheses and no whitespace, then an optional whitespace-led title (`"…"`, `'…'` or
    `(…)`) and the closing `)`. The fragment is dropped and backslash escapes of ASCII punctuation
    are undone; a link that is not well formed yields nothing. The old `\\]\\(([^)\\s]+?)…\\)`
    regex truncated `docs/a(b).md` to `docs/a(b`, missed a titled link entirely and kept the
    brackets of an angle one (`<docs/x.md>`); none of those ends in a checked suffix, so a link of
    any of the three shapes to a MISSING file was never examined. check_doc_index
    carries the same function (no enforcement check imports a sibling check; `_`-prefixed helpers such as `_fences` are shared); a test in
    tests/test_check_doc_index_percent_encoding.py pins the two to one output."""
    n = len(text)
    opened_at = n  # the first `[` behind an EVEN backslash run (`\\[` opens, `\[` does not)
    o = text.find("[")
    while o != -1:
        b = o
        while b > 0 and text[b - 1] == "\\":
            b -= 1
        if (o - b) % 2 == 0:
            opened_at = o
            break
        o = text.find("[", o + 1)
    i = text.find("](")
    while i != -1:
        # Not a link: a `]` escaped by an odd run of backslashes, or a `](` with no unescaped `[`
        # anywhere before it — accepting one would consume a real link inside its "title".
        b = i
        while b > 0 and text[b - 1] == "\\":
            b -= 1
        if (i - b) % 2 or opened_at > i:
            i = text.find("](", i + 2)
            continue
        j = i + 2
        while j < n and text[j] in " \t":
            j += 1
        if j < n and text[j] in "\r\n":  # one line ending may precede the destination (W-55905ee1)
            j += 2 if text[j : j + 2] == "\r\n" else 1
            while j < n and text[j] in " \t":
                j += 1
        dest = None
        if j < n and text[j] == "<":
            k = j + 1
            while k < n and text[k] not in "<>\n":
                k += 2 if text[k] == "\\" and text[k + 1 : k + 2] in _PUNCT else 1
            if k < n and text[k] == ">":
                dest, k = text[j + 1 : k], k + 1
        else:
            k, depth = j, 0
            while k < n:
                c = text[k]
                if c == "\\" and text[k + 1 : k + 2] in _PUNCT:
                    k += 2
                    continue
                # Any str.isspace() char ends it (NBSP-class too, OUT); a NUL stays and is reported.
                if c.isspace():
                    break
                if c == "(":
                    depth += 1
                elif c == ")":
                    if depth == 0:
                        break
                    depth -= 1
                k += 1
            if depth == 0:
                dest = text[j:k]
        close = _TITLE_CLOSE_RE.match(text, k) if dest is not None else None
        if dest is None or close is None:
            i = text.find("](", i + 2)
            continue
        cut, p = len(dest), 0  # the fragment starts at the first UNESCAPED `#`
        while p < len(dest):
            if dest[p] == "\\" and dest[p + 1 : p + 2] in _PUNCT:
                p += 2
            elif dest[p] == "#":
                cut = p
                break
            else:
                p += 1
        dest = _ESCAPED_RE.sub(r"\1", dest[:cut])
        if dest:
            yield dest
        # Resume AFTER the link: a `](` inside its destination or title is not a second link.
        i = text.find("](", close.end())


# A backtick run, text, then the same run: an inline code span on one line, not a fence opener.
_INLINE_SPAN_RE = re.compile(r"(`{3,})[^`]+\1(?!`)")


_SPAN_BLANKER: object = (
    None  # unloaded; then _fences.blank_code_spans, or False where it is missing
)


def _blank_spans(text: str) -> str:
    """Inline code spans blanked, length-preserving, by `_fences.blank_code_spans` (W-b9af1d47) — the copy
    docs_updater blanks with. Imported on first use by the sibling directory; in a project whose `_fences.py`
    lags the sync it is absent, and the text comes back unblanked: today's reading, never a crash."""
    global _SPAN_BLANKER
    if _SPAN_BLANKER is None:
        here = str(Path(__file__).resolve().parent)
        if here not in sys.path:
            sys.path.insert(0, here)
        try:
            import _fences
        except ImportError:
            _SPAN_BLANKER = False
        else:
            _SPAN_BLANKER = getattr(_fences, "blank_code_spans", False)
    return _SPAN_BLANKER(text) if _SPAN_BLANKER else text  # type: ignore[operator]


def _iter_refs(text: str):
    """Yield (target, kind) pairs, skipping fenced code blocks for links and bare paths alike.

    A fenced link is a code EXAMPLE, so it is not graded (W-f11e740e: over 44 /opt repos it removed
    none of the findings and stopped examining 3 resolving example links). The fence is the toggle
    bare paths always used — any line starting with ``` opens or closes one — kept on purpose: a
    CommonMark fence model (run length, ~~~, info strings) measured 16 NEW findings fleet-wide, all a
    shared lessons-learnt template whose fences only balance by this toggle, so it waits on that
    template (W-f11e740e review residue). One exception: a line-leading inline span that closes on its
    own line (```` ```x``` ````) is inline code, never a fence — it would hide every link below it.
    Cost, stated: a fence that is never closed stops grading links and bare paths to the end of the
    file. A link inside an inline code span is an example too (W-b9af1d47): the link reader reads the
    line with spans blanked, while the fence toggle, the stale markers and the bare-path scan read it
    raw, and fence lines and bodies are blanked before the span pass (a closing fence's ``` would pair with
    an inline ``` below it). The blanked text is cut at each raw line's offsets — the blanker keeps every length, and a
    second splitlines() would not, since it also breaks on the \\f, \\v and U+2028 a span turns into
    spaces."""
    rows = []  # (line, its offset in text, a fence line or fence body)
    in_fence, pos = False, 0
    for raw in text.splitlines(keepends=True):
        line = raw.splitlines()[0]
        stripped = line.lstrip()
        toggle = stripped.startswith("```") and not _INLINE_SPAN_RE.match(stripped)
        rows.append((line, pos, toggle or in_fence))
        in_fence ^= toggle
        pos += len(raw)
    # Fence lines and bodies are blanked before the span pass, so a fence's ``` never pairs with an inline ```
    # run in the paragraph after it, and a body's backticks never pair with an opener above the fence — a
    # blanked fence line alone does not stop that when the fence opens after a \f, \v or U+2028, which this
    # toggle splits on and the span blanker does not (review pass 2).
    masked = list(text)
    for line, start, fenced in rows:
        if fenced:
            masked[start : start + len(line)] = " " * len(line)
    blanked = _blank_spans("".join(masked))
    in_fence = False
    for line, start, _fenced in rows:
        span_free = blanked[start : start + len(line)]
        stripped = line.lstrip()
        if stripped.startswith("```") and not _INLINE_SPAN_RE.match(stripped):
            in_fence = not in_fence
            continue
        # documented-stale convention: a line carrying the warning marker or an
        # explicit retirement note may cite a path that intentionally no longer
        # exists (Phase-D truth annotations) — skip its refs.
        if (
            "\u26a0" in line
            or "⚠" in line
            or "no longer exists" in line
            or ".deprecated" in line
            or "since removed" in line
            or "does not exist" in line
        ):
            continue
        if not in_fence:
            for target in link_targets(span_free):
                yield target, "link"
            for m in _BARE_RE.finditer(line):
                yield m.group(1), "bare"


_LINK_BASE_RE = re.compile(r"<!--\s*link-base:\s*([A-Za-z0-9_./-]+?)\s*-->")


def _link_bases(text: str) -> list[str]:
    """Extra resolution roots a doc declares for ITSELF — `<!-- link-base: sites/bhdtrade -->`.

    A doc that MIRRORS a manifest written relative to a sub-root (web-ecommerce-factory's
    `sites/<ref>/` inheritance table, pinned to the tuple's spelling by a test) cannot be written
    repo-relative and could never pass this check (01M1G8CR, 2026-09-02). Purely additive: a doc
    without the marker resolves exactly as before."""
    bases = []
    for b in _LINK_BASE_RE.findall(text):
        b = b.rstrip("/")
        # A base is a sub-root INSIDE the repo — never a parent hop or an absolute path, which
        # would let a doc declare `/etc` or `../../opt` as a place its refs "resolve".
        if b.startswith("/") or b == ".." or b.startswith("../") or "/../" in b:
            continue
        bases.append(b)
    return bases


def _resolves(target: str, src: Path, extra_bases: list[str] | None = None) -> bool:
    t = target.strip().strip("`")
    if not t or t.startswith(("http://", "https://", "mailto:", "#", "~")):
        return True
    if _PLACEHOLDER_RE.search(t):
        return True
    # The link as WRITTEN first, then percent-decoded (W-7ae1169a) — the contract check_doc_index
    # applies to the same INDEX links in the same gate run: `%20` alone left `%25`, `%23` and UTF-8
    # escapes "broken", and decoding alone broke a file whose real name holds `%XX`, linked by that
    # name. A decoded form holding a NUL names no file (`.resolve()` would raise) and is skipped.
    decoded = pct_decode(t)
    return any(
        _resolves_path(c, src, extra_bases) for c in dict.fromkeys((t, decoded)) if "\x00" not in c
    )


def pct_decode(text: str) -> str:
    """Percent-decode a markdown link target or text, keeping `%2F` LITERAL.

    surrogateescape matches how paths are read here, so a non-UTF-8 byte (`%E9`) decodes to the
    same string the filesystem walk yields. `%2F` stays as written because a renderer resolves an
    escaped slash as part of ONE path segment, never as a separator: decoding it made
    `docs%2Fsub%2Fx.md` index and resolve `docs/sub/x.md`, a link that does not reach that file.
    check_doc_index carries the same one-liner (no enforcement check imports a sibling check; `_`-prefixed helpers such as `_fences` are shared); a test in
    tests/test_check_doc_index_percent_encoding.py pins the two to one output."""
    return unquote(re.sub(r"%2[Ff]", "%252F", text), errors="surrogateescape")


def _resolves_path(t: str, src: Path, extra_bases: list[str] | None) -> bool:
    norm = t.lstrip("/") if t.startswith("/") else t
    if not norm.startswith("../"):
        while norm.startswith("./"):
            norm = norm[2:]
    if norm.rstrip("/") in PROJECT_CONTEXT_ALLOW or norm in PROJECT_CONTEXT_ALLOW:
        return True
    # repo-root resolution, then declared per-file bases (`<!-- link-base: … -->`). Bounded LEXICALLY: a deep
    # `../` walks past `/` (the kernel caps it there), so an unbounded `(REPO / norm).exists()` resolved to any
    # host file. Lexical, not `.resolve()`, so an in-repo symlink keeps resolving as before.
    for base in ("", *(extra_bases or ())):
        cand = Path(os.path.normpath(REPO / base / norm))
        if _bounded(cand) and cand.exists():
            return True
    # source-relative resolution
    cand = (src.parent / t).resolve()
    if _bounded(cand) and cand.exists():
        return True
    return _resolves_in_main_checkout(norm) or _escapes_from_main_checkout(t, src)


_MAIN_CACHE: dict[str, Path | None] = {}


def _main_checkout() -> Path | None:
    """The main checkout of REPO when REPO is a linked worktree, else None.

    A gitignored runtime artifact (a kilo cache file, a generated catalog) exists only in the checkout that
    produced it, so a doc citing it reads broken in every fresh worktree although the repo is fine. The main
    checkout is the parent of the git common dir; any git error answers None (no extra resolution)."""
    key = str(REPO)
    if key not in _MAIN_CACHE:
        main = None
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--path-format=absolute", "--git-dir", "--git-common-dir"],
                cwd=REPO,
                capture_output=True,
                text=True,
                timeout=10,
            )
            dirs = r.stdout.removesuffix("\n").split("\n")
            if r.returncode == 0 and len(dirs) == 2 and dirs[0] != dirs[1]:
                common = Path(dirs[1])
                # A submodule's common dir is `<outer>/.git/modules/<name>`: its parent is git internals,
                # and the submodule's own working tree is recorded in that dir's `core.worktree`.
                wt = subprocess.run(
                    ["git", "--git-dir", str(common), "config", "core.worktree"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                ).stdout.strip()
                main = (common / wt).resolve() if wt else common.parent
        except (OSError, subprocess.SubprocessError):
            pass
        _MAIN_CACHE[key] = main
    return _MAIN_CACHE[key]


def _resolves_in_main_checkout(norm: str) -> bool:
    """From a linked worktree, a repo-relative ref that git IGNORES resolves if the main checkout has it.

    Only gitignored paths: a tracked file missing from the worktree is a real break, and in the main checkout
    this adds nothing. The cheapest way to pass without the outcome — citing a gitignored path that exists
    nowhere — still fails, because the main checkout must hold the file."""
    main = _main_checkout()
    if main is None or norm.startswith("../"):
        return False
    cand = Path(os.path.normpath(main / norm))
    if not str(cand).startswith(str(main) + "/") or not cand.exists():
        return False
    r = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", norm], cwd=REPO, capture_output=True, timeout=10
    )
    return r.returncode == 0


def _escapes_from_main_checkout(t: str, src: Path) -> bool:
    """A source-relative ref that climbs OUT of the repo (`../../../fabrik-lib/README.md`) names a place relative
    to the MAIN checkout; a worktree nested at `.claude/worktrees/<n>` climbs somewhere else, so re-resolve it
    from the main checkout's copy of the source file. A ref that is missing from there too stays broken, and a ref
    that lands INSIDE the main checkout is never re-resolved: its target is the branch's own file, so one the
    branch deleted stays broken although the main checkout still has it."""
    main = _main_checkout()
    if main is None or not t.startswith("../"):
        return False
    try:
        rel = src.resolve().relative_to(REPO.resolve())
    except ValueError:
        return False
    cand = ((main / rel).parent / t).resolve()
    if cand.is_relative_to(main.resolve()):
        return False
    return _bounded(cand) and cand.exists()


def _bounded(cand: Path) -> bool:
    """Inside this repo, or inside one of the two sanctioned sibling repos.

    The Fabrik repos are sanctioned siblings: a project doc cites hub or fabrik-lib files by their ABSOLUTE path
    (a repo-relative `docs/…` would be checked against the project's own tree), and such a citation resolves on
    the host — so a cited file that is later moved goes red instead of passing silently (D-370, mail
    01M35H43N07E0S9Z43QYGXPPW4). The trailing slash keeps `/opt/fabrikX/` out. Every resolution branch of
    `_resolves` goes through here, so no branch reaches the rest of the host FS.
    """
    s = str(cand)
    return s.startswith((str(REPO) + "/", "/opt/fabrik/", "/opt/fabrik-lib/"))


def main() -> int:
    as_json = "--json" in sys.argv
    broken: list[str] = []
    # Denominator, not just the verdict. A bare "OK" is indistinguishable from "OK, I examined
    # nothing" — measured 2026-08-25 across all 59 checks, 17 emit an affirmative success claim with
    # no subject present and only ONE stated how much it looked at. In an empty-repo fixture this
    # check scanned a single README with no links and still said "zero broken references in the live
    # tree": true sentence, false impression. See docs/reference/enforcement-battery-audit.md.
    docs_scanned = 0
    refs_checked = 0
    for src in _tracked_md_sources():
        try:
            text = src.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        docs_scanned += 1
        rel_src = src.relative_to(REPO)
        seen: set[str] = set()
        bases = _link_bases(text)
        for target, kind in _iter_refs(text):
            if target in seen:
                continue
            seen.add(target)
            # markdown links only need checking when they look like repo paths
            if kind == "link" and (
                target.startswith(("http", "#", "mailto:")) or "." not in target
            ):
                continue
            # `link_targets` already cut the fragment and undid `\#`; splitting again at `#` would
            # cut a literal `#` in the name and skip the link unexamined (W-dd091f0d review).
            if kind == "link" and not re.search(r"\.(md|py|sh|yaml|yml|json|txt)$", target):
                continue
            refs_checked += 1
            if not _resolves(target, src, extra_bases=bases):
                broken.append(f"{rel_src}: broken ref -> {target}")
    if as_json:
        print(
            json.dumps(
                {
                    "status": "success" if not broken else "failure",
                    "broken": broken,
                    "docs_scanned": docs_scanned,
                    "refs_checked": refs_checked,
                }
            )
        )
    else:
        for b in broken:
            print(f"ERROR: {b}")
        if not broken:
            print(
                f"check_doc_links: OK — 0 broken of {refs_checked} refs across {docs_scanned} docs"
            )
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
