"""Pins on the D-335 review loop as a Claude Code workflow script (chunk 5, D-347/D-348).

The script is JavaScript the Workflow tool runs; nothing here executes it. These graders pin the
contract the command sources and the reviewer brief rely on: the file exists where the sources
point, its ``meta`` block is a pure literal (the tool refuses anything else), every finder call
returns a schema that REQUIRES ``files_read`` (the coverage-overclaim guard, § 4.9 finding 10), every
seat is the ``fabrik-reviewer`` agent type on a cheap model (D-344), the script never resumes a run
(resume re-runs a fan-out — finding 22), and the two partitioned sources plus the brief name it.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".claude" / "workflows" / "fabrik-review-loop.js"
SOURCES = [
    ROOT / "commands" / "_sources" / "fabrik-review.md",
    ROOT / "commands" / "_sources" / "fabrik-repo-review.md",
]
BRIEF = ROOT / "commands" / "_agents" / "fabrik-reviewer.md"
DOC = ROOT / "docs" / "reference" / "review-loop-workflow.md"
SCRIPT_PATH_TEXT = "/opt/fabrik/.claude/workflows/fabrik-review-loop.js"


def _script() -> str:
    assert SCRIPT.is_file(), f"missing {SCRIPT}"
    return SCRIPT.read_text(encoding="utf-8")


def test_the_meta_block_is_the_first_statement_and_a_pure_literal() -> None:
    body = _script()
    stripped = re.sub(r"^(//[^\n]*\n|/\*.*?\*/\s*|\s+)*", "", body, count=1, flags=re.S)
    assert stripped.startswith("export const meta = {"), stripped[:80]
    meta = stripped[: stripped.index("\n}\n") + 3]
    for forbidden in ("${", "(", "..."):
        assert forbidden not in meta, f"meta must be a pure literal, found {forbidden!r}"
    assert "name: 'fabrik-review-loop'" in meta


def test_every_finder_schema_requires_files_read_and_candidates() -> None:
    body = _script()
    m = re.search(r"const FINDINGS\s*=\s*\{(.*?)\n\}", body, re.S)
    assert m, "no FINDINGS schema"
    required = re.search(r"required:\s*\[([^\]]*)\]", m.group(1))
    assert required, "FINDINGS has no required list"
    for field in ("'files_read'", "'candidates'", "'notes'"):
        assert field in required.group(1), f"FINDINGS must require {field}"


def test_every_seat_is_the_reviewer_agent_on_a_cheap_model_and_no_run_is_resumed() -> None:
    body = _script()
    sites = [m.start() for m in re.finditer(r"\bagent\(", body)]
    assert len(sites) == 2, (
        f"exactly two agent() sites (finder map, verify seat), found {len(sites)}"
    )
    for start in sites:
        opts = body[start : body.index("})", start)]
        assert "agentType: 'fabrik-reviewer'" in opts, (
            "every seat is the fabrik-reviewer agent type"
        )
        assert re.search(r"model: (?:m|'sonnet'),", opts), (
            "seats run on the cheap models only (D-344)"
        )
    assert "'opus'" not in body and "'fable'" not in body, "no Opus/Fable finder (D-344)"
    code = "\n".join(line for line in body.splitlines() if not line.lstrip().startswith("//"))
    assert "resumeFromRunId" not in code and "workflow(" not in code, (
        "each pass is its own invocation"
    )


def test_the_script_diffs_files_read_against_the_slice_and_logs_the_gap() -> None:
    body = _script()
    assert "files_read" in body
    assert re.search(r"if \(gaps\.length\) log\(`[^`]*coverage gap", body), (
        "a coverage gap must be logged by its own conditional line (no silent caps)"
    )


def test_the_sources_and_the_brief_name_the_script() -> None:
    for src in SOURCES:
        text = src.read_text(encoding="utf-8")
        assert SCRIPT_PATH_TEXT in text, f"{src.name} does not launch the workflow"
    brief = BRIEF.read_text(encoding="utf-8")
    assert "files_read" in brief, "the brief must tell a finder to list every file it opened"
    assert DOC.is_file(), "the workflow's reference doc is missing"
