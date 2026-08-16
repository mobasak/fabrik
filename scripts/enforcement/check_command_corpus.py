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

WHAT IT PROVES (all five are mechanically decidable — no judgement, no network)
------------------------------------------------------------------------------
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

BLOCKING. Each of the five is a true/false fact about the tree with no tolerance
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

# A chain reference is a bare /command token. The lookbehind rejects anything
# where the slash is part of a longer path (``/opt/fabrik-lib``, ``docs/x/fabrik-mail.md``)
# and the lookahead rejects file-shaped tails (``/fabrik-review.md``).
_CHAIN_RE = re.compile(r"(?<![\w/.-])/((?:fabrik|design)-[a-z][a-z-]*)(?!\.md)(?![\w/-])")
_WEB_TOOLS_RE = re.compile(r"web_tools\s*=\s*\[([^\]]*)\]")
_NAME_RE = re.compile(r"[\"'\\]*([a-z0-9_]+)[\"'\\]*")  # digits matter: "context7", not "context"
_SCRIPT_RE = re.compile(r"(?<![\w/-])(scripts/[\w/-]+\.py)")
_TRAILER_RE = re.compile(r"Co-Authored-By:\s*(.+?)\s*<")


def _live_web_tool_names() -> frozenset[str]:
    """Read the accepted names from the module itself — never a local copy."""
    sys.path.insert(0, str(REPO))
    from libs.subagents.web_tools import WEB_TOOL_NAMES  # noqa: PLC0415

    return frozenset(WEB_TOOL_NAMES)


def _canonical_trailer_model() -> str | None:
    """The Co-Authored-By model named in CLAUDE.md's own trailer example."""
    if not CLAUDE_MD.exists():
        return None
    found = _TRAILER_RE.findall(CLAUDE_MD.read_text(encoding="utf-8", errors="replace"))
    return found[0] if found else None


def _corpus_files(sources: Path, fragments: Path, assembler: Path) -> list[Path]:
    files = sorted(sources.glob("*.md"))
    files += sorted(fragments.glob("*.md")) if fragments.exists() else []
    if assembler.exists():
        files.append(assembler)
    return files


def audit(
    sources: Path = SOURCES,
    fragments: Path = FRAGMENTS,
    assembler: Path = ASSEMBLER,
    repo: Path = REPO,
) -> list[str]:
    """Return one problem string per real defect; empty means the corpus is sound."""
    problems: list[str] = []
    files = _corpus_files(sources, fragments, assembler)
    if not files:
        return [f"{sources}: no command sources found — the corpus check has nothing to audit"]

    valid_tools = _live_web_tool_names()
    known_commands = {p.stem for p in sources.glob("*.md")}
    canonical_model = _canonical_trailer_model()

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
            for literal in _WEB_TOOLS_RE.findall(line):
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
                if not (repo / script).exists():
                    problems.append(f"{rel}:{lineno}: {script} does not exist")
            if canonical_model:
                for model in _TRAILER_RE.findall(line):
                    if model != canonical_model:
                        problems.append(
                            f"{rel}:{lineno}: commit template says Co-Authored-By {model!r} "
                            f"but CLAUDE.md's canonical trailer says {canonical_model!r}"
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
        }
        for label, bad in cases.items():
            probe = src / "fabrik-probe.md"
            probe.write_text(bad)
            if not audit(src, frag, root / "absent.py", REPO):
                failures.append(f"VACUOUS: the {label} predicate did not fire on known-bad input")
            probe.unlink()

        good = src / "fabrik-good.md"
        good.write_text(
            "{{include:run-record}}\n"
            'fanout("research", web_tools=["web_search","docs_lookup"])\n'
            "next: /fabrik-real · see /opt/fabrik-lib and docs/reference/fabrik-mail.md\n"
            "run `scripts/enforcement/check_command_corpus.py`\n"
            f"Co-Authored-By: {_canonical_trailer_model()} <noreply@anthropic.com>\n"
        )
        noise = audit(src, frag, root / "absent.py", REPO)
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
    print(
        "✓ command corpus: web-tool names, chain targets, script paths, trailer models,"
        " run records — all sound"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
