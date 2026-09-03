#!/usr/bin/env python3
# AFTER-EDIT: tests/test_check_command_corpus.py, docs/reference/command-corpus-check.md, scripts/final_gate.py | none
"""Command-corpus integrity — the /fabrik-* commands must reference things that EXIST.

WHY THIS EXISTS
---------------
The command corpus tells every agent on the box what to run. When a command names
something that no longer exists, nothing fails loudly: the agent follows the
instruction, gets a degraded result, and reports success. That is the same
failure shape as a gate check that asserts nothing.

The founding case (2026-08-16 corpus audit): four commands told agents to ground
research with ``fanout(..., web_tools=["exa","brave","firecrawl","context7"])``.
Those are PROVIDER names. ``libs/subagents/web_tools.py::WEB_TOOL_NAMES`` accepts
only TOOL names (``web_search``/``web_search_brave``/``web_scrape``/``web_crawl``/
``docs_lookup``), and ``loop.py`` filters the advertised schemas by that set — an
unknown name yields an EMPTY list, whereupon ``merged.pop("tools")`` runs the
"grounder" with no tools at all. It still returned confident prose. Every spec and
plan grounded that way was ungrounded, and no gate, test, or human review caught
it for as long as the text stood.

WHAT IT PROVES (all eight are mechanically decidable — no judgement, no network)
-------------------------------------------------------------------------------
1. WEB-TOOL NAMES  — every ``web_tools=[...]`` literal names only real tools,
   imported live from ``WEB_TOOL_NAMES`` rather than copied here (a copy drifts).
2. CHAIN TARGETS   — every ``/fabrik-x`` / ``/design-review`` chain reference
   resolves to a real source, so the pipeline cannot dead-end. Path-shaped
   look-alikes (``/opt/fabrik-lib``, ``/run/fabrik-autoheal``,
   ``docs/reference/fabrik-mail.md``) are NOT chain references and are excluded
   by the boundary lookarounds — getting this wrong is how a reader "finds"
   four broken chains that were never broken.
3. SCRIPT PATHS    — every ``scripts/**.py`` a command tells an agent to run exists.
4. TRAILER MODEL   — the ``Co-Authored-By:`` in copy-paste commit templates matches
   the canonical example in ``CLAUDE.md``, so templates cannot stamp a retired
   model into provenance trailers (found live: six templates said "Opus 4.8").
5. RUN RECORD      — every command opens one, so the Stop hook can block an abandoned
   run (it was wired into 3 of 27 when this check was written).
6. AGENT DEFS      — every ``commands/_agents/*.md`` has frontmatter, a ``name:`` matching
   its filename, and a ``description:`` (the dispatcher selects on it). Until 2026-08-27
   the four subagent definitions existed ONLY on the box, outside git and this audit.
7. ADVERTISED CLOSE — every printed ``command_run.py done|blocked|handoff`` carries
   ``--feedback``, which the tool now REQUIRES. A printed close missing it instructs a
   command that is refused, leaving the record ``running`` and the Stop hook holding the
   turn open: the machinery documenting an exit that does not work. Found live in 36
   sites the day the refusal landed.

8. CALLER CLAIMS   — every command a source CLAIMS calls it ("auto-called by /fabrik-x", or a
   ``## Where this auto-fires (N call sites)`` section) actually names it back. Found live:
   ``/fabrik-generate-tests`` advertised ``/fabrik-review`` as a caller while that file carried
   zero references to it — and the false name was concealing a COPY of its whole pipeline.
   Bare cross-references are deliberately NOT graded (460 of them live, 17.8% one-directional).

BLOCKING. Each of the eight is a true/false fact about the tree with no tolerance
band, and every one of them was found VIOLATED in a corpus that looked healthy.

Anti-vacuity: ``--selftest`` feeds a known-bad corpus through the same predicates
and requires each to fail, then a known-good one and requires silence. A check
that cannot fail is not a check.
"""

from __future__ import annotations

import argparse
import importlib.util
import marshal
import re
import sys
import traceback
from collections.abc import Collection
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCES = REPO / "commands" / "_sources"
FRAGMENTS = REPO / "commands" / "_fragments"
ASSEMBLER = REPO / "commands" / "assemble_commands.py"
CLAUDE_MD = REPO / "CLAUDE.md"
# The orchestrator-workflow wrappers (Traycer chains). Their canonical BODIES live under
# docs/orchestrator/**, outside commands/_sources — which is exactly how the whole set escaped
# this audit until 2026-08-16 (zero of the four mega wrappers opened a run record, none of the
# docs was among the audited files, and a dead scripts/ reference sat in three of them).
# Hub-only, like the corpus itself: absent in projects → the section is silently N/A.
TRAYCER_SKILLS = REPO / "docs" / "orchestrator" / "_traycer-skills"
_ORCH_DOC_RE = re.compile(r"^`/opt/fabrik/(docs/orchestrator/[^`]+\.md)`", re.M)

# A chain reference is a bare /command token. The lookbehind rejects anything
# where the slash is part of a longer path (``/opt/fabrik-lib``, ``docs/x/fabrik-mail.md``)
# and the lookahead rejects file-shaped tails (``/fabrik-review.md``).
_CHAIN_RE = re.compile(r"(?<![\w/.-])/((?:fabrik|design)-[a-z][a-z-]*)(?!\.md)(?![\w/-])")
_WEB_TOOLS_RE = re.compile(
    r"web_tools\s*=\s*(?:(?:frozenset|set|sorted|list|tuple)\(\s*)*[\[{(](.*?)[\]})](?!\s*(?:[|+]|if\b|else\b))"
)  # list/set/frozenset and nested-call forms, captured to the END of the argument — the first closer NOT followed by an operator (`|`, `+`) or a ternary keyword — so `{"a"} | {"exa"}`, `sorted({"exa"})`, a ternary, an inline-code span and a bare prose tail (`web_tools=["exa"] for facts`) all keep every name; the capture is then cut at the first keyword-argument boundary (`, system=…`), so a following argument is never harvested; per LINE (a multi-line literal is out of scope); UNQUOTED names (`[exa]`) are invisible by design since pass 43 — the price of not harvesting `if`/`else`; a literal whose tail starts with an operator or ternary keyword and has NO later closer on the line is invisible too, and a keyword argument inside a ternary's condition cuts the harvest early — 0 of 49 tracked `web_tools=` lines outside the review ledger take either shape (DM2/DO2/DQ2/DS2/DU3)
_KWARG_CUT_RE = re.compile(
    r",\s*[A-Za-z_][A-Za-z0-9_]*\s*="
)  # the first `, name=` after the literal ends the harvest (DS2)
_NAME_RE = re.compile(
    r"[\"'\\]+([a-z0-9_]+)[\"'\\]+"
)  # QUOTED names only — digits matter ("context7"); the wider capture would otherwise harvest `if`/`else`/`sorted` as tool names (DQ2)
# Both citation forms: bare `scripts/x.py` AND hub-absolute `/opt/fabrik/scripts/x.py` — the
# orchestrator docs cite almost exclusively in the absolute form, and the lookbehind-only regex
# was blind to every one of them (predicate 3 said "all sound" while it audited nothing there —
# reproduced with a dead absolute citation, round-5 closing sweep). The absolute prefix is
# stripped before resolution, so both forms check the same repo-rooted path.
_SCRIPT_RE = re.compile(r"(?:/opt/fabrik/|(?<![\w/-]))(scripts/[\w/-]+\.py)")
# The script prefix is OPTIONAL: prose instructions routinely write `done --command x …` in a
# backtick span with `command_run.py` established lines earlier — and the prefixed-only regex was
# BLIND to every one of them (found at cmd 24/31: six feedback-less closes across four commands
# hid behind it, each instructing a close the tool refuses).
_CLOSE_CMD_RE = re.compile(r"(?:command_run\.py\s+)?\b(?:done|blocked|handoff)\s+--command\s")
_TRAILER_RE = re.compile(r"Co-Authored-By:\s*(.+?)\s*<")
# A caller CLAIM — the two forms the corpus actually uses (surveyed, not guessed):
#   (a) a verb of invocation: "auto-called by /fabrik-x", "invoked by /fabrik-x", "dispatched by …"
#   (b) a section headed "Where this auto-fires (N call sites)", every bullet of which names one
# Deliberately NARROW. A bare cross-reference is NOT a claim: the live corpus makes 460 such
# mentions (SKIP routes, successor pointers, "see also"), 17.8% of which have no back-reference —
# treating those as defects would fire 82 times on day one and train the reader to skip the check.
# The claim forms above fire 3 times across 31 sources, and caught the one that was false.
# ⚠️ Those counts are derived with THIS module's _CHAIN_RE and _claimed_callers. The first
# version quoted 439/17.5%/77/5 from a throwaway prototype whose regex differed from the shipped
# one — measured numbers that described code nobody would ever run. Re-derive, never re-quote.
_CLAIM_VERB_RE = re.compile(
    r"(?:auto-)?(?:called|invoked|dispatched|fired|cited)\s+(?:by|from)\b([^.;]*)", re.I
)
# ⚠️ NARROW on purpose — `call sites?` / `auto-fires` only. The first draft also accepted
# "where this runs", which matched `## Where this runs` in /fabrik-deploy-plan and its review —
# sections about which REPO you run the command from (hub vs project), not about who calls it.
# Both were silent only by coincidence (those two happen to name each other for unrelated
# pipeline reasons); the day one stopped, this predicate would have fabricated a finding on an
# unrelated command. Found reviewing this predicate: the survey checked the SPELLINGS a heading
# might use and never opened the sections the regex would then capture.
_CALLSITE_HEAD_RE = re.compile(r"^#{2,4}\s+.*\b(?:call sites?|auto-fires)\b", re.I)


def _live_web_tool_names(repo: Path = REPO) -> frozenset[str] | None:
    """Read the accepted names from the module itself — never a local copy.

    Takes ``repo`` as a parameter (same rule as everything else here: the module constant
    poisons any caller that isn't the default one). Returns ``None`` when the module is
    absent, and the caller SKIPS predicate 1 — never an empty set, which would invert the
    check and flag every name as invalid; and never an import crash, which took a BLOCKING
    gate down with a ModuleNotFoundError in any repo that never vendored the pool. ⚠ The
    caller decides what ``None`` means: in a project the module is absent BY DESIGN (an
    advisory); in the hub a module that is present but unusable is a DEFECT and must red the
    gate (DY1). The target's OWN health is asked of the file — read + compile — BEFORE the
    import (EG1): a traceback cannot be trusted to name it (a NUL-corrupted file raises a
    SyntaxError with no filename, an unreadable one a PermissionError inside the import
    machinery, a directory a ModuleNotFoundError in the importer). Known: the
    ``libs.subagents`` package import is cached in ``sys.modules``, so a second repo in the
    same process reuses the first's names — one repo per process (0 of 48 callers; DU4).
    """
    target = repo / "libs" / "subagents" / "web_tools.py"
    try:
        # a dangling or looping symlink is PRESENT (a broken vendored link is a hub defect, never
        # "absent"); an unreadable PARENT makes `exists()` itself raise EACCES — pathlib ignores
        # only ENOENT/ENOTDIR/EBADF/ELOOP — and that too is the target's own defect (EI1)
        present = target.exists() or target.is_symlink()
    except OSError as exc:
        _IMPORT_FAILURE.append(_scrub(f"{exc.__class__.__name__}: {exc}", repo))
        _IMPORT_BLAME.append(str(target))
        return None
    if not present:
        return None
    broken = _target_is_broken(target)
    if broken:
        _IMPORT_FAILURE.append(_scrub(broken, repo))
        _IMPORT_BLAME.append(str(target))
        return None
    if str(repo) not in sys.path:  # once — every audit() call inserted another copy (DS1)
        sys.path.insert(0, str(repo))
    try:
        from libs.subagents.web_tools import WEB_TOOL_NAMES  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001 - never a traceback out of a gate; the CALLER decides what the failure means (a problem in the hub when it is web_tools.py's own, an advisory otherwise — EA1)
        failure = f"{exc.__class__.__name__}: {exc}"
        blame = _blame_for(exc)
        if not blame or _same_file(blame, Path(__file__)):
            # no source frame at all (the only import in THIS file is the target's, so the last
            # real frame is the checker): the shape of a torn bytecode cache anywhere in the
            # `libs.subagents` graph — ask the CACHES which module's is unloadable, the target's
            # first, then its package siblings, then the parent package (EI1/EK1); none → unknown
            owner = _bad_cache_owner(target)
            if owner is None:
                blame = ""
            else:
                blame = str(owner)
                failure = f"bytecode cache of {owner.name} unloadable ({failure}) — delete {owner.parent.name}/__pycache__"
        _IMPORT_FAILURE.append(_scrub(failure, repo))
        _IMPORT_BLAME.append(blame)
        return None

    shape = _shape_problem(WEB_TOOL_NAMES)
    if (
        shape
    ):  # a stub, a bare str, None, non-str members — each inverts or takes down the gate (DY1/EE1)
        _IMPORT_FAILURE.append(shape)
        _IMPORT_BLAME.append(str(target))
        return None
    return frozenset(WEB_TOOL_NAMES)


def _target_is_broken(target: Path) -> str | None:
    """Ask the module FILE whether it can be read and compiled — one read of one file, and
    every shape a traceback misattributes is settled with certainty: a directory at the path,
    an unreadable file, NUL bytes, a compile-time SyntaxError (EG1). A file that compiles can
    still fail at import (a raise, a renamed constant, a broken sibling) — that is
    `_blame_for`'s job."""
    if not target.is_file():
        return "not a regular file"
    try:
        compile(target.read_bytes(), str(target), "exec")
    except (
        OSError,
        ValueError,
        SyntaxError,
        RecursionError,
        MemoryError,
    ) as exc:  # a pathological source must not take the gate down either (EI1)
        return f"{exc.__class__.__name__}: {exc}"
    return None


def _blame_for(exc: BaseException) -> str:
    """The FILE an import failure was raised in, for a failure the target itself did not
    cause: `exc.path` — an ImportError at the import site (a renamed constant names the
    target; a broken sibling's import names the sibling); an exception's `filename` when it
    names a REAL file (a compile-time SyntaxError in a sibling: CPython strips the
    import-machinery frames, so the last frame would be the importer; a PermissionError
    carries the file it could not open); otherwise the last traceback frame — a RUNTIME
    SyntaxError from `compile()`/`eval()` says `<string>` and keeps its frames (EC1/EE1/EG1)."""
    path = getattr(exc, "path", None)
    if path:
        return str(path)
    fn = getattr(exc, "filename", None)
    # a `.py` only: a module that fails opening a DATA file at import carries that file's name,
    # and it is the module's own failure — the frame (the module) is the truth there (EI1)
    if isinstance(fn, str) and fn.endswith(".py") and not fn.startswith("<") and Path(fn).is_file():
        return fn
    tb = traceback.extract_tb(exc.__traceback__)
    # the last frame that names a REAL file: the import machinery's own frames (`<frozen
    # importlib._bootstrap_external>`) sit below the importer and name nothing (EI1)
    for frame in reversed(tb):
        # a real, EXISTING file: a sourceless `.pyc` records a `.py` that is gone (EK1)
        if not frame.filename.startswith("<") and Path(frame.filename).is_file():
            return frame.filename
    return ""  # no source frame at all — the caller asks the bytecode caches (EK1)


def _scrub(text: str, repo: Path) -> str:
    """An exception's text quotes absolute paths (`Permission denied: '/home/…/web_tools.py'`);
    a synced check's stdout never carries a path under the operator's home (EI1)."""
    for root in {str(repo), str(repo.resolve())}:
        text = text.replace(root + "/", "")
    return text.replace(
        str(Path.home()) + "/", "~/"
    )  # a dependency under the operator's home reads `~/…` (EK1)


def _bad_cache_owner(target: Path) -> Path | None:
    """Which module's bytecode cache is unloadable: the target's first, then its package
    siblings, then the parent package — the order the import executes them. A torn `.pyc`
    (a killed write, ENOSPC) raises EOFError inside frozen importlib with no path and no
    filename; a zero-byte or unreadable one falls back to source and never fails (EK1)."""
    siblings = sorted(p for p in target.parent.glob("*.py") if p != target)
    parents = sorted(target.parent.parent.glob("*.py"))
    for src in [target, *siblings, *parents]:
        pyc = Path(importlib.util.cache_from_source(str(src)))
        if not pyc.is_file():
            continue
        try:
            marshal.loads(pyc.read_bytes()[16:])
        except Exception:  # noqa: BLE001 - any unloadable cache is the answer
            return src
    return None


def _shape_problem(value: object) -> str | None:
    """`WEB_TOOL_NAMES` must be a non-empty collection of non-empty str — any real collection
    (a set, a tuple, a list, `dict` keys — what the consumer's `name in WEB_TOOL_NAMES` and
    this check's `frozenset()` both accept), never a str or bytes (a set of CHARACTERS —
    `valid: _, a, b, …`, every real name flagged, fleet-wide), None or an int (the `frozenset`
    crashes), a generator (one-shot), or a non-str member (the remediation join crashes).
    `libs/` is excluded from ruff and mypy, so this check is the constant's only reader (EE1/EG1)."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Collection):
        return f"WEB_TOOL_NAMES is not a collection of str ({type(value).__name__})"
    if not value:
        return "WEB_TOOL_NAMES is empty"
    if not all(isinstance(n, str) and n for n in value):
        return "WEB_TOOL_NAMES has a member that is not a non-empty str"
    return None


def _same_file(blame: str, target: Path) -> bool:
    """Identity, never a suffix: `libs/web_tools.py` (a real standalone module in this tree) and
    a `deep_web_tools.py` both end with the name (EE1). A blame that cannot be resolved (a
    symlink loop — pathlib re-raises ELOOP as RuntimeError; an embedded NUL — ValueError) is
    not the target (EG1)."""
    try:
        return Path(blame).resolve() == target.resolve()
    except (OSError, RuntimeError, ValueError):
        return False


def _display_path(blame: str, repo: Path) -> str:
    """Repo-relative when the file is inside the repo — the LITERAL path first (a symlinked
    `libs/` resolves outside the tree and must still read `libs/subagents/…`), then the resolved
    one for an ABSOLUTE path only (a relative or pseudo path — `<frozen importlib._bootstrap>`,
    `<string>` — would otherwise resolve against the cwd and read as a repo file); otherwise the
    name, with its package for an `__init__.py`, never an absolute path under the operator's
    home in a synced check's stdout (EC1/EE1/EG1)."""
    if not blame:
        return "an unknown file"
    p = Path(blame)
    candidates: list[tuple[Path, Path]] = [(p, repo)]
    if p.is_absolute():
        try:
            candidates.append((p.resolve(), repo.resolve()))
        except (OSError, RuntimeError, ValueError):
            pass
    for a, b in candidates:
        try:
            return str(a.relative_to(b))
        except ValueError:
            continue
    if blame.startswith("<"):
        return f"{blame} (not a file)"
    shown = f"{p.parent.name}/{p.name}" if p.name.startswith("__init__") else p.name
    return f"{shown} (outside the repo)"


def _canonical_trailer_model(repo: Path = REPO) -> str | None:
    """The Co-Authored-By model named in CLAUDE.md's own trailer example.

    ``repo``-derived like everything else — the module-constant version silently graded every
    fixture audit against the real hub's CLAUDE.md, making predicate 4 untestable in isolation
    (the same poisons-any-other-caller class this file already documents twice)."""
    claude_md = repo / "CLAUDE.md"
    if not claude_md.exists():
        return None
    found = _TRAILER_RE.findall(claude_md.read_text(encoding="utf-8", errors="replace"))
    return found[0] if found else None


# Files this run could NOT read. A skipped read must never be indistinguishable from a clean
# one: `main` reports "all sound across N file(s) read" where N counts files the predicates OPENED, so a
# silent skip would claim coverage the run did not have — the exact fail-silent-green shape this
# check exists to catch, rebuilt inside the fix for the OSError crash.
SKIPPED: list[str] = []
SKIPPED_PREDICATES: list[
    str
] = []  # a predicate that could not run at all — the hub's web-tool check without its module (DU1)
_IMPORT_FAILURE: list[
    str
] = []  # why `_live_web_tool_names` returned None when the module EXISTS (DW1)
_IMPORT_BLAME: list[
    str
] = []  # the FILE the failure was raised in — the import runs the whole `libs.subagents` package graph, and only a failure inside web_tools.py itself is this check's to block on (EA1)
AUDITED: set[str] = (
    set()
)  # every file a predicate actually OPENED this audit — the success line's denominator (DS2)


def _read(path: Path) -> str | None:
    """Read a corpus file, or None if it vanished mid-audit.

    Three sessions plus a daily pipeline share this tree, so every path this check collects can
    be renamed or deleted between the glob that found it and the read that opens it. An
    unhandled OSError here is a BLOCKING gate failure for every session in the repo, reported
    against whichever predicate happened to touch the file first — so the read is tolerant and
    the caller skips. Unreadable means UNPROVABLE, never violated.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        AUDITED.add(str(path))
        return text
    except OSError as exc:
        # DEDUPE by path: _read is called from four sites, so one vanished file otherwise
        # appended three entries and the "files actually audited" arithmetic over-subtracted.
        entry = f"{path}: {exc.__class__.__name__}"
        if entry not in SKIPPED:
            SKIPPED.append(entry)
        return None


def _claimed_callers(body: str) -> dict[str, int]:
    """Map each command this source CLAIMS calls it -> the 1-indexed line making the claim.

    The call-sites section must CLOSE at the next heading of the same or higher level. An
    unclosed section would turn every command named lower in the file into a fabricated claim,
    which on a 500-line source means inventing defects — the exact way a check earns its way
    into being ignored.
    """
    out: dict[str, int] = {}
    in_callsites = False
    in_fence = False
    head_level = 0
    for lineno, line in enumerate(body.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        # A `#` inside a fenced block is a COMMENT, not a heading. Without this the first
        # shell comment in a call-sites section closed the section and every claim below it
        # went unexamined — the check reporting success because it had stopped asking.
        if line.startswith("#") and not in_fence:
            level = len(line) - len(line.lstrip("#"))
            if _CALLSITE_HEAD_RE.match(line):
                in_callsites, head_level = True, level
                continue
            if in_callsites and level <= head_level:
                in_callsites = False
        if in_callsites:
            for name in _CHAIN_RE.findall(line):
                out.setdefault(name, lineno)
        for tail in _CLAIM_VERB_RE.findall(line):
            for name in _CHAIN_RE.findall(tail):
                out.setdefault(name, lineno)
    return out


def _corpus_files(sources: Path, fragments: Path, assembler: Path) -> list[Path]:
    files = sorted(sources.glob("*.md"))
    files += sorted(fragments.glob("*.md")) if fragments.exists() else []
    if assembler.exists():
        files.append(assembler)
    return files


def _orch_corpus(traycer_skills: Path, repo: Path) -> tuple[list[Path], list[str]]:
    """The orchestrator corpus: every tracked wrapper's canonical doc, plus wrapper problems.

    The mapping is read from the WRAPPERS (each names its doc in a stable generated line), not
    duplicated here — a copy of the assembler's ORCH_SOURCES table would drift, and importing
    the assembler would drag its dependencies into every project this check is synced to.

    EVERY wrapper must open a run record — no banner condition. The first version required it
    only of GENERATED wrappers, which meant deleting the banner line exempted a wrapper from the
    one thing this predicate exists to prove (reproduced 2026-08-18). Since the same change
    brought the whole set (mega + ettw) under generation, the honest rule has no carve-out; a
    genuinely new hand-written wrapper fails until it is added to ORCH_SOURCES, which is the fix.
    """
    docs: list[Path] = []
    problems: list[str] = []
    for wrapper in sorted(traycer_skills.glob("*/SKILL.md")):
        name = wrapper.parent.name
        body = wrapper.read_text(encoding="utf-8", errors="replace")
        AUDITED.add(str(wrapper))
        m = _ORCH_DOC_RE.search(body)
        if m is None:
            problems.append(
                f"docs/orchestrator/_traycer-skills/{name}: wrapper names no canonical doc "
                "(`/opt/fabrik/docs/orchestrator/...`) — nothing to audit, which is not the same "
                "as nothing wrong"
            )
            continue
        # Resolve + containment: the captured path is repo-relative but `[^`]+` admits `..`;
        # without this a wrapper could aim the audit at (and "validate") a file outside
        # docs/orchestrator entirely.
        doc = (repo / m.group(1)).resolve()
        try:
            doc.relative_to((repo / "docs" / "orchestrator").resolve())
        except ValueError:
            problems.append(
                f"docs/orchestrator/_traycer-skills/{name}: canonical-doc path escapes "
                f"docs/orchestrator/ ({m.group(1)}) — refusing to audit it"
            )
            continue
        if not doc.exists():
            problems.append(
                f"docs/orchestrator/_traycer-skills/{name}: canonical doc {m.group(1)} does not "
                "exist — the wrapper points agents at nothing"
            )
            continue
        docs.append(doc)
        if "command_run.py start" not in body:
            problems.append(
                f"docs/orchestrator/_traycer-skills/{name}: wrapper opens no run record — "
                "every orchestrator command must; add it to assemble_commands.py's ORCH_SOURCES "
                "and re-render (hand-editing the wrapper is the drift the render check catches)"
            )
    return docs, problems


#: Agent definitions — `commands/_agents/*.md`, rendered to `~/.claude/agents/`. Predicate 6.
AGENTS_SRC = SOURCES.parent / "_agents"


def audit(
    sources: Path = SOURCES,
    fragments: Path = FRAGMENTS,
    assembler: Path = ASSEMBLER,
    repo: Path = REPO,
    traycer_skills: Path | None = None,
    agents: Path | None = None,
) -> list[str]:
    """Return one problem string per real defect; empty means the corpus is sound."""
    problems: list[str] = []
    SKIPPED.clear()
    AUDITED.clear()
    SKIPPED_PREDICATES.clear()
    _IMPORT_FAILURE.clear()
    _IMPORT_BLAME.clear()
    files = _corpus_files(sources, fragments, assembler)
    if not files:
        # ⚠️ NOT-APPLICABLE, not a failure — this check is SYNCED to ~46 projects, and the command
        # corpus exists ONLY in the hub (`/opt/fabrik/commands/_sources` → rendered box-wide).
        # Every project therefore hit this branch and got a BLOCKING red gate for a directory it is
        # not supposed to have. Measured 2026-08-16 in ai-model-catalog, whose gate went from
        # 46 passed / 0 failed to a hard failure the moment a governance-sync landed this file.
        #
        # The distinction that matters: an ABSENT corpus in a project is correct; an absent or
        # EMPTY corpus in the hub is a real defect (the renderer would prune installed commands
        # box-wide). So fail only where the corpus is supposed to exist — i.e. where the assembler
        # lives — and stay silent elsewhere.
        if assembler.exists() or sources.exists():
            return [f"{sources}: no command sources found — the corpus check has nothing to audit"]
        return []

    # ⚠️ The orchestrator section runs ONLY behind the hub gate above — i.e. after a non-empty
    # command corpus proved this is the hub (or a hub-shaped fixture). The first version appended
    # orch docs BEFORE that branch, which was reproduced doing two bad things at once in a
    # project-shaped tree that happened to carry `_traycer-skills/`: (a) `files` became non-empty
    # with an EMPTY `known_commands`, so every /fabrik-* chain ref in the orch docs "failed" (28
    # bogus problems, masking the accurate no-corpus message); (b) execution then reached
    # `_live_web_tool_names()`, whose `from libs.subagents...` import does not exist in projects —
    # an unhandled ModuleNotFoundError in a BLOCKING gate check, fleet-wide.
    orch_docs: list[Path] = []
    if traycer_skills is None:
        # Derive from `repo`, never the module constant: the selftest audits a FIXTURE repo, and
        # a real-tree default leaked the live orchestrator docs into it — every /fabrik-* chain
        # ref then "failed" against the fixture's two-command _sources. Same class as the
        # temp-dir relative_to hazard above: a path that ignores the parameter poisons any
        # caller that isn't the default one.
        traycer_skills = repo / "docs" / "orchestrator" / "_traycer-skills"
    if traycer_skills.is_dir():
        orch_docs, orch_problems = _orch_corpus(traycer_skills, repo)
        files = files + orch_docs
        problems.extend(orch_problems)
    elif assembler.exists():
        # The hub without its tracked wrapper tree is a defect, not an N/A: ORCH commands are
        # invokable box-wide, and an absent tracked tree means nothing pins what they load.
        problems.append(
            f"{traycer_skills}: orchestrator wrapper tree missing in the hub — "
            "run `python3 commands/assemble_commands.py` to (re)generate it"
        )

    valid_tools = _live_web_tool_names(repo)
    if valid_tools is None and assembler.exists():
        # the HUB without its vendored pool module: predicate 1 — the founding one — would run
        # zero times and the success line would still name it; a project never reaches this
        # branch at all — no corpus, no assembler — so the skip advisory is a HUB verdict (DU1/EC1). A module that is PRESENT but unusable here (a raise
        # on import, a renamed or empty constant after a vendor sync) is a hub DEFECT: the
        # round-46 guard turned that from a blocking red into a green with an advisory the
        # `--json` mode never showed — it is a problem, never a skip (DY1)
        target = repo / "libs" / "subagents" / "web_tools.py"
        if _IMPORT_FAILURE and (
            _IMPORT_BLAME[-1] == str(target) or _same_file(_IMPORT_BLAME[-1], target)
        ):
            problems.append(
                f"libs/subagents/web_tools.py is present but unusable ({_IMPORT_FAILURE[-1]}) — "
                "predicate 1 (web-tool names) could not run in the hub; fix the module, do not skip"
            )
        elif _IMPORT_FAILURE:
            # the import executes the whole `libs.subagents` package graph (and httpx): a failure
            # raised in a SIBLING file — a peer session's half-saved agent.py on this shared tree —
            # is not this check's surface and must not red every session's gate under
            # web_tools.py's name (EA1); it is named, and predicate 1 is recorded as not run
            blame = _display_path(_IMPORT_BLAME[-1], repo)
            SKIPPED_PREDICATES.append(
                f"web-tool names: {blame} failed to import ({_IMPORT_FAILURE[-1]}) while loading "
                "libs/subagents/web_tools.py — predicate 1 did not run; not this check's surface"
            )
        else:
            SKIPPED_PREDICATES.append(
                "web-tool names: libs/subagents/web_tools.py absent — predicate 1 did not run"
            )
    known_commands = {p.stem for p in sources.glob("*.md")}
    canonical_model = _canonical_trailer_model(repo)
    orch_doc_set = set(orch_docs)

    # 5. RUN RECORD — CLAUDE.md makes opening one the first act of any /fabrik-* invocation,
    # and the Stop hook's fifth cause reads it. It was wired into 3 of 27 commands, so for the
    # other 24 the pinned RUN: line, the class ledger, the non-convergence detector and the
    # hook all stayed disarmed — which is exactly the "agents stop without finishing the
    # command" failure the record was built to prevent. A command may carry the shared
    # fragment or its own bespoke `start` block; having neither is the defect.
    for path in sorted(sources.glob("*.md")):
        body = _read(path)
        if body is None:
            continue
        if "{{include:run-record}}" not in body and "command_run.py start" not in body:
            problems.append(
                f"{path.relative_to(repo) if path.is_relative_to(repo) else path}: opens no run "
                "record — add `{{include:run-record}}` (or a bespoke `command_run.py start` block). "
                "Without it the Stop hook cannot block an abandoned run."
            )

    for path in files:
        text = _read(path)
        if text is None:
            continue
        # Never bare `relative_to`: it raises on any path outside the repo (temp-dir
        # fixtures, a corpus checked from elsewhere) and that ValueError is precisely
        # what left check_doc_sprawl silently inert for weeks.
        rel = path.relative_to(repo) if path.is_relative_to(repo) else path
        for lineno, line in enumerate(text.splitlines(), 1):
            for literal in (
                (_KWARG_CUT_RE.split(cap, 1)[0] for cap in _WEB_TOOLS_RE.findall(line))
                if valid_tools is not None
                else []
            ):
                for name in _NAME_RE.findall(literal):
                    if name and name not in valid_tools:
                        problems.append(
                            f"{rel}:{lineno}: web_tools name {name!r} is not a real tool — "
                            f"valid: {', '.join(sorted(valid_tools))}. An unknown name silently "
                            "advertises NO tools, so the agent runs blind."
                        )
            for cmd in _CHAIN_RE.findall(line):
                if cmd not in known_commands:
                    problems.append(f"{rel}:{lineno}: /{cmd} does not exist in commands/_sources/")
            for script in _SCRIPT_RE.findall(line):
                # Two resolution contexts, deliberately distinct. A hub COMMAND source speaks to
                # agents whose cwd is a repo carrying the synced scripts/ tree — hub-rooted
                # existence is the right test, and loosening it would mask a genuinely deleted
                # hub script that happens to share a name with a template file. An ORCHESTRATOR
                # doc speaks to agents working IN a project, where scaffolding delivers scripts
                # from templates/ (e.g. `scripts/validate_i18n.py` from templates/i18n-kit/ —
                # hub-rooting alone called that live reference dead 5 times across three mega
                # docs). Template matches must be FILES: a directory named like a script is not
                # a runnable delivery.
                ok = (repo / script).exists()
                if not ok and path in orch_doc_set:
                    ok = any(c.is_file() for c in (repo / "templates").glob(f"**/{script}"))
                if not ok:
                    problems.append(f"{rel}:{lineno}: {script} does not exist")
            if canonical_model:
                for model in _TRAILER_RE.findall(line):
                    if model != canonical_model:
                        problems.append(
                            f"{rel}:{lineno}: commit template says Co-Authored-By {model!r} "
                            f"but CLAUDE.md's canonical trailer says {canonical_model!r}"
                        )
    # ── Predicate 7: an advertised CLOSE must be a RUNNABLE close ──────────────────────────────
    # `command_run.py done|blocked|handoff` REFUSES without `--feedback` (the close-out feedback
    # duty). Every place the corpus PRINTS that command is in-product documentation an agent
    # copies verbatim — so a printed close missing the flag instructs a command the tool then
    # refuses, leaving the record `running` and the Stop hook holding the turn open. Measured the
    # day the refusal landed: 36 such sites across the run-record fragment, the 17 generated
    # orchestrator wrappers, and the Stop hook — the fix reached 2 of them, and only a mechanical
    # sweep found the rest. The flag may wrap to a continuation line, so the window is 4 lines.
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            AUDITED.add(str(path))
        except OSError:
            continue
        rel = path.relative_to(repo) if path.is_relative_to(repo) else path
        for i, line in enumerate(lines):
            if not _CLOSE_CMD_RE.search(line):
                continue
            if "--feedback" not in "\n".join(lines[i : i + 4]):
                problems.append(
                    f"{rel}:{i + 1}: advertises a close with no --feedback — the tool REFUSES "
                    "it, so this instructs a command that cannot succeed"
                )

    # ── Predicate 8: a CLAIMED caller must actually CALL ───────────────────────────────────────
    # Found live at cmd 13/31 (2026-08-29): `/fabrik-generate-tests` advertised itself as
    # "auto-called by … `/fabrik-review` reactively" while fabrik-review.md carried ZERO
    # references to it. Two harms, and the second is the one that matters: the reader is told a
    # call happens that never does, AND the false name concealed why — `/fabrik-review` had
    # REPRODUCED the whole five-step pipeline inline instead of invoking it, so the same
    # contract was being maintained in two files and a fix to the canonical one could not reach
    # the other. Nothing in the corpus check noticed either half; the defect surfaced only
    # because the operator asked who the callers were.
    #
    # The claim is directional ON PURPOSE. "X names Y" implies nothing — successor pointers and
    # SKIP routes name commands constantly. Only an explicit claim of BEING CALLED is checkable,
    # because only it asserts something about a file other than its own.
    for path in sorted(sources.glob("*.md")):
        body = _read(path)
        if body is None:
            continue
        rel = path.relative_to(repo) if path.is_relative_to(repo) else path
        for caller, lineno in _claimed_callers(body).items():
            if caller == path.stem or caller not in known_commands:
                continue  # self-reference, or a dangling name predicate 2 already reports
            # `known_commands` proves the file existed when the SET was built, not when it is
            # READ — the race is strictly between those two moments (see _read).
            caller_body = _read(sources / f"{caller}.md")
            if caller_body is None:
                continue
            if f"/{path.stem}" not in caller_body:
                problems.append(
                    f"{rel}:{lineno}: claims caller /{caller}, whose source never names "
                    f"/{path.stem} — the advertised wiring does not exist, so either wire it "
                    f"up or drop the claim"
                )

    # ── Predicate 6: agent definitions are GOVERNED ────────────────────────────────────────────
    # Until 2026-08-27 the four subagent definitions lived ONLY in ~/.claude/agents/: no repo
    # source, no generator, not in git, and outside this audit entirely — so the corpus check
    # vouched for 31 commands while the agents those commands DISPATCH were unreviewable. Exactly
    # the blind spot that once left the orchestrator wrappers unaudited.
    #
    # HUB-ONLY, like the rest of this check: a project has no _agents/ dir and must stay silent.
    agents_src = agents if agents is not None else AGENTS_SRC
    if agents_src.is_dir():
        for adef in sorted(agents_src.glob("*.md")):
            text = adef.read_text(encoding="utf-8", errors="replace")
            AUDITED.add(str(adef))
            if not text.startswith("---"):
                problems.append(
                    f"_agents/{adef.name}: no frontmatter — Claude Code cannot register it"
                )
                continue
            head = text.split("\n---", 1)[0]
            declared = ""
            for line in head.splitlines():
                if line.startswith("name:"):
                    declared = line.split(":", 1)[1].strip()
                    break
            if not declared:
                problems.append(f"_agents/{adef.name}: frontmatter declares no `name:`")
            elif declared != adef.stem:
                problems.append(
                    f"_agents/{adef.name}: declares `name: {declared}` — an agent whose name "
                    f"disagrees with its filename cannot be dispatched by either"
                )
            if "description:" not in head:
                problems.append(
                    f"_agents/{adef.name}: no `description:` — the dispatcher selects on it, so an "
                    f"agent without one is invisible to model-native routing"
                )
    return problems


def _selftest() -> int:
    """Prove each predicate can FAIL on bad input and stays silent on good input."""
    import tempfile  # noqa: PLC0415

    failures: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src, frag = root / "_sources", root / "_fragments"
        src.mkdir()
        frag.mkdir()
        (src / "fabrik-real.md").write_text("placeholder\n{{include:run-record}}\n")

        # every case opens a run record, so ONLY the predicate under test can fire — and each case
        # names the SIGNATURE its predicate prints: "some problem fired" let the run-record
        # predicate vouch for every other canary (review 2026-09-03, DM2/DO2)
        cases = {
            "web-tool name": (
                '{{include:run-record}}\nfanout("research", web_tools=["exa","brave"])\n',
                "is not a real tool",
            ),
            "web-tool name (set form)": (
                '{{include:run-record}}\nfanout("research", web_tools=frozenset({"exa","brave"}))\n',
                "is not a real tool",
            ),
            "web-tool name (union form)": (
                '{{include:run-record}}\nfanout("research", web_tools=frozenset({"web_search"} | {"exa"}))\n',
                "name 'exa' is not a real tool",
            ),
            "web-tool name (sorted form)": (
                '{{include:run-record}}\nfanout("research", web_tools=frozenset(sorted({"exa"})))\n',
                "name 'exa' is not a real tool",
            ),
            "web-tool name (prose tail)": (
                '{{include:run-record}}\nGround research with web_tools=["exa"] for best results\n',
                "name 'exa' is not a real tool",
            ),
            "web-tool name (inline code)": (
                '{{include:run-record}}\nthe grounder passes `web_tools=["exa"]` for facts\n',
                "name 'exa' is not a real tool",
            ),
            "chain target": (
                "{{include:run-record}}\nthen run /fabrik-does-not-exist to finish\n",
                "does not exist in commands/_sources/",
            ),
            "script path": (
                "{{include:run-record}}\nrun `scripts/enforcement/check_no_such_thing.py`\n",
                "check_no_such_thing.py does not exist",
            ),
            "trailer model": (
                "{{include:run-record}}\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>\n",
                "commit template says Co-Authored-By",
            ),
            "run record": ("a command body that never opens a run record\n", "opens no run record"),
            # Predicate 8: a caller CLAIM the alleged caller does not honour. fabrik-real.md
            # never names /fabrik-probe, so the advertised wiring does not exist.
            "caller claim": (
                "{{include:run-record}}\n"
                "## Where this auto-fires (1 call site)\n"
                "- **`/fabrik-real` (reactive):** when a review finds an untested behavior.\n",
                "claims caller /fabrik-real",
            ),
            # Predicate 7: an advertised close the tool would REFUSE. The good fixture below
            # carries the same command WITH --feedback, so this also pins the false-positive side.
            "advertised close": (
                "{{include:run-record}}\n"
                'close it: `python3 scripts/command_run.py done --command x --evidence "e"`\n',
                "advertises a close with no --feedback",
            ),
        }
        # Predicate 6 has its own fixture (an agent dir, not a command body) — asserted by ITS
        # signature, never by "something fired"
        bad_agents = root / "_bad_agents"
        bad_agents.mkdir()
        (bad_agents / "mismatch.md").write_text("---\nname: something-else\ndescription: d\n---\n")
        agent_probs = audit(
            src, frag, root / "absent.py", REPO, traycer_skills=root / "no-orch", agents=bad_agents
        )
        if not any("declares `name:" in p for p in agent_probs):
            failures.append(
                "VACUOUS: the agent-definition predicate did not fire on known-bad input"
            )
        for label, (bad, signature) in cases.items():
            probe = src / "fabrik-probe.md"
            probe.write_text(bad)
            probs = audit(src, frag, root / "absent.py", REPO, traycer_skills=root / "no-orch")
            if not any(signature in p for p in probs):
                failures.append(
                    f"VACUOUS: the {label} predicate did not fire on known-bad input "
                    f"(expected {signature!r}; got {probs or 'nothing'})"
                )
            probe.unlink()

        # The honoured-claim half of predicate 8: fabrik-real must name fabrik-good back, or the
        # good fixture would pass by never making a claim at all — a self-test that dodges the
        # predicate it is meant to vouch for.
        (src / "fabrik-real.md").write_text(
            "placeholder\n{{include:run-record}}\nI invoke /fabrik-good when a behavior is untested.\n"
        )
        good = src / "fabrik-good.md"
        good.write_text(
            "{{include:run-record}}\n"
            "description: auto-called by /fabrik-real reactively.\n"
            'fanout("research", web_tools=["web_search","docs_lookup"])\n'
            'fanout("research", web_tools=["web_search"] if fast else ["web_scrape"])  # a ternary: `if`/`else` are not tool names (DQ2)\n'
            'fanout("research", web_tools=["web_search"] if fast else DEFAULT, system="exa")  # a later argument is never harvested (DS2)\n'
            "next: /fabrik-real · see /opt/fabrik-lib and docs/reference/fabrik-mail.md\n"
            "run `scripts/enforcement/check_command_corpus.py`\n"
            'close: `python3 scripts/command_run.py done --command x --evidence "e" '
            '--feedback "none — swept it"`\n'
            f"Co-Authored-By: {_canonical_trailer_model()} <noreply@anthropic.com>\n"
        )
        noise = audit(src, frag, root / "absent.py", REPO, traycer_skills=root / "no-orch")
        if noise:
            failures.append(f"FALSE POSITIVE on known-good input: {noise}")

    for line in failures:
        print(f"✗ {line}")
    if failures:
        return 1
    print(
        f"✓ selftest: {len(cases) + 1} canaries over the eight predicates fire on bad input and stay silent on good input"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Command-corpus integrity (see module docstring).")
    parser.add_argument(
        "--selftest", action="store_true", help="prove the predicates can fail (anti-vacuity)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress the clean-path ✓ denominator line (the gate passes this: an `advisory` row "
        "ships its stdout unfiltered into every green gate run fleet-wide, and the --json "
        "`warnings` array admits only ⚠-first output — the ⚠ lines always print; DY1)",
    )
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()

    problems = audit()
    if problems:
        print(f"✗ command corpus: {len(problems)} broken reference(s)")
        for line in problems:
            print(f"  {line}")
        # the verdict above was computed over whatever could be read — the run that most needs
        # the coverage ⚠ lines is the failing one, and they were only printed on success (EA1)
        _print_coverage_warnings(len(AUDITED))
        return 1
    # DENOMINATOR: this check is SYNCED to ~46 repos where the corpus does not exist, and it
    # correctly returns [] there — but "all sound" then reads as a clean audit of nothing.
    # See docs/reference/enforcement-battery-audit.md.
    audited = len(
        AUDITED
    )  # what the predicates OPENED (corpus + orchestrator docs + wrappers + agent defs), never the collected list alone — 55 printed against 93 read (DS2)
    if not args.quiet:
        print(
            "✓ command corpus: web-tool names, chain targets, script paths, trailer models,"
            " run records, agent definitions, advertised closes, caller claims —"
            # the population is what was READ plus what could not be — never the collected list (DU1)
            f" all sound across {audited} file(s) read"
        )
    _print_coverage_warnings(audited)
    return 0


def _print_coverage_warnings(audited: int) -> None:
    """The ⚠ lines — printed on BOTH exits and under `--quiet`: a ⚠ is the point of the row's
    stdout (DU1/DY1/EA1)."""
    if SKIPPED:
        print(
            f"⚠ {len(SKIPPED)} file(s) could NOT be read and were NOT audited "
            f"(attempted {audited + len(SKIPPED)}): {', '.join(SKIPPED)}"
        )
    for note in SKIPPED_PREDICATES:
        print(f"⚠ predicate skipped — {note}")


if __name__ == "__main__":
    sys.exit(main())
