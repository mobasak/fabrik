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

WHAT IT PROVES (all seven are mechanically decidable — no judgement, no network)
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

BLOCKING. Each of the seven is a true/false fact about the tree with no tolerance
band, and every one of them was found VIOLATED in a corpus that looked healthy.

Anti-vacuity: ``--selftest`` feeds a known-bad corpus through the same predicates
and requires each to fail, then a known-good one and requires silence. A check
that cannot fail is not a check.
"""

from __future__ import annotations

import argparse
import re
import sys
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
_WEB_TOOLS_RE = re.compile(r"web_tools\s*=\s*\[([^\]]*)\]")
_NAME_RE = re.compile(r"[\"'\\]*([a-z0-9_]+)[\"'\\]*")  # digits matter: "context7", not "context"
# Both citation forms: bare `scripts/x.py` AND hub-absolute `/opt/fabrik/scripts/x.py` — the
# orchestrator docs cite almost exclusively in the absolute form, and the lookbehind-only regex
# was blind to every one of them (predicate 3 said "all sound" while it audited nothing there —
# reproduced with a dead absolute citation, round-5 closing sweep). The absolute prefix is
# stripped before resolution, so both forms check the same repo-rooted path.
_SCRIPT_RE = re.compile(r"(?:/opt/fabrik/|(?<![\w/-]))(scripts/[\w/-]+\.py)")
_CLOSE_CMD_RE = re.compile(r"command_run\.py\s+(?:done|blocked|handoff)\s+--command")
_TRAILER_RE = re.compile(r"Co-Authored-By:\s*(.+?)\s*<")


def _live_web_tool_names(repo: Path = REPO) -> frozenset[str] | None:
    """Read the accepted names from the module itself — never a local copy.

    Takes ``repo`` as a parameter (same rule as everything else here: the module constant
    poisons any caller that isn't the default one). Returns ``None`` when the module is
    absent, and the caller SKIPS predicate 1 — never an empty set, which would invert the
    check and flag every name as invalid; and never an import crash, which took a BLOCKING
    gate down with a ModuleNotFoundError in any repo that never vendored the pool.
    """
    if not (repo / "libs" / "subagents" / "web_tools.py").exists():
        return None
    sys.path.insert(0, str(repo))
    from libs.subagents.web_tools import WEB_TOOL_NAMES  # noqa: PLC0415

    return frozenset(WEB_TOOL_NAMES)


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
        body = path.read_text(encoding="utf-8", errors="replace")
        if "{{include:run-record}}" not in body and "command_run.py start" not in body:
            problems.append(
                f"{path.relative_to(repo) if path.is_relative_to(repo) else path}: opens no run "
                "record — add `{{include:run-record}}` (or a bespoke `command_run.py start` block). "
                "Without it the Stop hook cannot block an abandoned run."
            )

    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        # Never bare `relative_to`: it raises on any path outside the repo (temp-dir
        # fixtures, a corpus checked from elsewhere) and that ValueError is precisely
        # what left check_doc_sprawl silently inert for weeks.
        rel = path.relative_to(repo) if path.is_relative_to(repo) else path
        for lineno, line in enumerate(text.splitlines(), 1):
            for literal in _WEB_TOOLS_RE.findall(line) if valid_tools is not None else []:
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

        cases = {
            "web-tool name": 'fanout("research", web_tools=["exa","brave"])\n',
            "chain target": "then run /fabrik-does-not-exist to finish\n",
            "script path": "run `scripts/enforcement/check_no_such_thing.py`\n",
            "trailer model": "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>\n",
            "run record": "a command body that never opens a run record\n",
            # Predicate 7: an advertised close the tool would REFUSE. The good fixture below
            # carries the same command WITH --feedback, so this also pins the false-positive side.
            "advertised close": (
                "{{include:run-record}}\n"
                'close it: `python3 scripts/command_run.py done --command x --evidence "e"`\n'
            ),
        }
        # Predicate 6 has its own fixture (an agent dir, not a command body).
        bad_agents = root / "_bad_agents"
        bad_agents.mkdir()
        (bad_agents / "mismatch.md").write_text("---\nname: something-else\ndescription: d\n---\n")
        if not audit(
            src, frag, root / "absent.py", REPO, traycer_skills=root / "no-orch", agents=bad_agents
        ):
            failures.append(
                "VACUOUS: the agent-definition predicate did not fire on known-bad input"
            )
        cases["agent definition"] = "(fixture-based — see bad_agents above)"
        for label, bad in cases.items():
            probe = src / "fabrik-probe.md"
            probe.write_text(bad)
            if not audit(src, frag, root / "absent.py", REPO, traycer_skills=root / "no-orch"):
                failures.append(f"VACUOUS: the {label} predicate did not fire on known-bad input")
            probe.unlink()

        good = src / "fabrik-good.md"
        good.write_text(
            "{{include:run-record}}\n"
            'fanout("research", web_tools=["web_search","docs_lookup"])\n'
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
        f"✓ selftest: all {len(cases)} predicates fire on bad input and stay silent on good input"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Command-corpus integrity (see module docstring).")
    parser.add_argument(
        "--selftest", action="store_true", help="prove the predicates can fail (anti-vacuity)"
    )
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()

    problems = audit()
    if problems:
        print(f"✗ command corpus: {len(problems)} broken reference(s)")
        for line in problems:
            print(f"  {line}")
        return 1
    # DENOMINATOR: this check is SYNCED to ~46 repos where the corpus does not exist, and it
    # correctly returns [] there — but "all sound" then reads as a clean audit of nothing.
    # See docs/reference/enforcement-battery-audit.md.
    audited = len(_corpus_files(SOURCES, FRAGMENTS, REPO / "commands" / "assemble_commands.py"))
    print(
        "✓ command corpus: web-tool names, chain targets, script paths, trailer models,"
        " run records, agent definitions, advertised closes —"
        f" all sound across {audited} corpus file(s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
