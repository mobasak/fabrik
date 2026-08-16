"""Behaviour tests for the command-corpus integrity check.

Each test names a defect class the 2026-08-16 corpus audit found LIVE, and proves
the check goes red on it. The path-look-alike test is the important negative: a
naive matcher "finds" four broken chains in `/opt/fabrik-lib`, `/run/fabrik-autoheal`
and `docs/reference/fabrik-mail.md` that were never broken, and a check that cries
wolf gets ignored — which is how a real break then ships.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "enforcement"))
sys.path.insert(0, str(REPO / "commands"))

from check_command_corpus import audit  # noqa: E402


@pytest.fixture
def corpus(tmp_path: Path):
    """A minimal two-command corpus; the callable writes the file under test."""
    src, frag = tmp_path / "_sources", tmp_path / "_fragments"
    src.mkdir()
    frag.mkdir()
    # Every fixture command carries a run record unless a test opts out: predicate 5
    # applies to the whole corpus, so a bare sibling would pollute every other test.
    (src / "fabrik-real.md").write_text("a real sibling command\n{{include:run-record}}\n")

    def write(body: str, *, with_record: bool = True) -> list[str]:
        prefix = "{{include:run-record}}\n" if with_record else ""
        (src / "fabrik-probe.md").write_text(prefix + body)
        return audit(src, frag, tmp_path / "no-assembler.py", REPO)

    return write


def test_provider_name_in_web_tools_is_caught(corpus):
    """The founding defect: provider names where tool names belong ⇒ agent runs blind."""
    problems = corpus('fanout("research", web_tools=["exa","brave","firecrawl","context7"])\n')
    assert problems, "the provider-name defect must be caught"
    joined = " ".join(problems)
    assert "'exa'" in joined and "'context7'" in joined, joined
    assert "runs blind" in joined


def test_real_web_tool_names_pass(corpus):
    assert corpus('fanout("research", web_tools=["web_search","web_scrape","docs_lookup"])\n') == []


def test_dangling_chain_reference_is_caught(corpus):
    problems = corpus("when done run /fabrik-nonexistent to continue\n")
    assert any("/fabrik-nonexistent" in p for p in problems)


def test_path_lookalikes_are_not_chain_references(corpus):
    """`/opt/fabrik-lib` is a directory, not a dead command — never flag it."""
    assert (
        corpus(
            "vendor from /opt/fabrik-lib, the pause marker is /run/fabrik-autoheal/pause,\n"
            "and the mailbox doc is docs/reference/fabrik-mail.md — then run /fabrik-real\n"
        )
        == []
    )


def test_missing_script_path_is_caught(corpus):
    problems = corpus("run `scripts/enforcement/check_totally_absent.py --json`\n")
    assert any("check_totally_absent.py" in p for p in problems)


def test_existing_script_path_passes(corpus):
    assert corpus("run `scripts/enforcement/check_command_corpus.py`\n") == []


def test_stale_trailer_model_is_caught(corpus):
    """Six live templates stamped a retired model into provenance trailers."""
    problems = corpus("Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>\n")
    assert any("Opus 4.8" in p for p in problems)


def test_empty_corpus_is_reported_not_silently_green(tmp_path: Path):
    """A check that finds nothing to audit must say so — silence would be vacuous."""
    src, frag = tmp_path / "_sources", tmp_path / "_fragments"
    src.mkdir()
    frag.mkdir()
    problems = audit(src, frag, tmp_path / "absent.py", REPO)
    assert problems and "nothing to audit" in problems[0]


def test_live_corpus_is_clean():
    """The shipped corpus itself must satisfy the check."""
    assert audit() == []


def test_command_without_a_run_record_is_caught(corpus):
    """CLAUDE.md makes the record the first act; 24 of 27 commands never opened one."""
    problems = corpus("a command body that never opens a run record\n", with_record=False)
    assert any("opens no run record" in p for p in problems)


def test_bespoke_start_block_satisfies_the_run_record(corpus):
    """A command with its own `start` block needs no fragment — both forms count."""
    assert corpus(
        "run `python3 scripts/command_run.py start --command x --phases 3`\n", with_record=False
    ) == []


def test_phase_count_prefers_explicit_phase_headings():
    from assemble_commands import _phase_count  # noqa: PLC0415

    assert _phase_count("## Phase 0 — a\n## Phase 1 — b\n## Phase 2 — c\n") == 3
    assert _phase_count("## PHASE 0 — a\n## PHASE 1 — b\n") == 2


def test_phase_count_ignores_a_lone_phase_heading_among_real_sections():
    """A single `Phase 0` plus branch sections is not a one-phase command (fabrik-release)."""
    from assemble_commands import _phase_count  # noqa: PLC0415

    text = "## Termination\n## Phase 0 — resolve\n## VPS path\n## MOBILE path\n## Output\n"
    assert _phase_count(text) == 5


def test_phase_count_never_returns_zero():
    """`--phases 0` would make a record that can never show progress."""
    from assemble_commands import _phase_count  # noqa: PLC0415

    assert _phase_count("prose with no headings at all\n") == 1
