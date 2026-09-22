"""Pins on the D-335 review loop as a Claude Code workflow script (chunk 5, D-347/D-348).

The script is JavaScript the Workflow tool runs; nothing here executes it. These graders pin the
contract the command sources and the reviewer brief rely on: the file exists where the sources
point, its ``meta`` block is a pure literal (the tool refuses anything else), every finder call
returns a schema that REQUIRES ``files_read`` (the coverage-overclaim guard, § 4.9 finding 10), every
seat is the ``fabrik-reviewer`` agent type on a cheap model (D-344), the script never resumes a run
(resume re-runs a fan-out — finding 22), and the two partitioned sources plus the brief name it.
"""

from __future__ import annotations

import json
import re
import subprocess
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
        opts = body[start : _call_end(body, start)]
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


def _call_end(body: str, start: int) -> int:
    """The index just past the `)` that closes the call opened at `start` — a balanced scan, so a `})`
    inside a comment or a string before the options object cannot truncate the window (A-S8)."""
    depth = 0
    for i in range(body.index("(", start), len(body)):
        if body[i] == "(":
            depth += 1
        elif body[i] == ")":
            depth -= 1
            if depth == 0:
                return i + 1
    raise AssertionError("unbalanced call")


def _run_ledger(args: dict, seat_results: dict) -> tuple[dict, str]:
    """The ledger the script returns and the log text (see `_harness`)."""
    out, log, _ = _harness(args, seat_results)
    return out, log


def _harness(args: dict, seat_results: dict) -> tuple[dict, str, dict]:
    """Execute the script's own pipeline under node with the Workflow globals stubbed: `agent` records the
    prompt it was sent and returns the canned result keyed by the call's label (`None` → a null seat),
    `parallel`/`pipeline` run the stages, `log` goes to stderr. Returns the ledger, the log text and the
    prompts by label."""
    src = _script().replace("export const meta", "const meta", 1)
    harness = f"""
globalThis.args = {json.dumps(args)};
const results = {json.dumps(seat_results)};
globalThis.log = (m) => console.error(String(m));
globalThis.parallel = async (thunks) => Promise.all(thunks.map((t) => t()));
globalThis.pipeline = async (items, ...stages) =>
  Promise.all(items.map(async (item) => {{ let v = item; for (const s of stages) v = await s(v, item); return v; }}));
const prompts = {{}};
globalThis.agent = async (prompt, opts) => {{
  prompts[opts.label] = prompt;
  return Object.hasOwn(results, opts.label) ? results[opts.label] : null;
}};
(async () => {{ {src} }})().then((out) => console.log(JSON.stringify({{ out, prompts }})));
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", harness],
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-1500:]
    doc = json.loads(proc.stdout.strip().splitlines()[-1])
    return doc["out"], proc.stderr, doc["prompts"]


_ARGS = {
    "pass": 1,
    "surface": "t",
    "base_sha": "0",
    "digest": "0",
    "pins_dir": "/p",
    "scratch_dir": "/s",
    "brief": "b",
    "slices": [{"name": "S", "files": ["a.py", "b.py"], "priority": "p"}],
}


def _cand(cid: str, line: int, cls: str = "logic") -> dict:
    return {
        "id": cid,
        "file": "a.py",
        "line": line,
        "failure_class": cls,
        "claim": cid,
        "scenario": "s",
        "check": "true",
        "confidence": "PLAUSIBLE",
    }


def test_the_union_merges_only_across_seats_near_the_same_line_and_never_drops_a_same_seat_neighbour() -> (
    None
):
    ledger, _ = _run_ledger(
        _ARGS,
        {
            "find:S:sonnet": {
                "files_read": ["a.py", "b.py"],
                "notes": "",
                "candidates": [_cand("S-S1", 3), _cand("S-S2", 5)],
            },
            "find:S:haiku": {"files_read": ["a.py"], "notes": "", "candidates": [_cand("S-H1", 7)]},
            "verify:S:S-S1": {
                "id": "WRONG-ECHO",
                "verdict": "confirmed",
                "command": "c",
                "output": "o",
                "mechanism": "m",
            },
            # verify:S:S-S2 absent → a null verify seat
        },
    )
    s = ledger["slices"][0]
    ids = [c["id"] for c in s["candidates"]]
    assert ids == ["S-S1", "S-S2"], f"the same seat's two neighbours are two defects, kept: {ids}"
    assert s["overlap"] == 1 and s["candidates"][0]["also"] == "S-H1", (
        "S-H1 at line 7 is S-S1's twin (cross-seat, within 5 lines)"
    )
    assert s["gaps"] == [], "b.py was read by the sonnet seat"
    verdict_ids = [v["id"] for v in s["verdicts"]]
    assert verdict_ids == ["S-S1", "S-S2"], (
        f"the verdict id is the candidate's, never the seat's echo: {verdict_ids}"
    )
    assert s["verdicts"][1]["verdict"] == "unverified", (
        "a null verify seat is unverified, never dropped"
    )
    by_model = {x["model"]: x for x in s["seats"]}
    assert by_model["sonnet"]["confirmed"] == 1 and by_model["haiku"]["confirmed"] == 1, (
        "a shared confirmed candidate credits both seats"
    )


def test_a_null_finder_makes_every_unread_file_a_logged_gap_and_the_seat_failed() -> None:
    ledger, log = _run_ledger(
        _ARGS,
        {
            "find:S:sonnet": {"files_read": ["a.py"], "notes": "", "candidates": []},
            # find:S:haiku absent → a null finder
        },
    )
    s = ledger["slices"][0]
    assert s["gaps"] == ["b.py"], s["gaps"]
    assert ledger["dropped_seats"] == 1 and any(x["failed"] for x in s["seats"])
    assert "coverage gap" in log and "SEAT FAILED" in log, log
    assert s["verdicts"] == [], "zero candidates run zero verify seats"


def test_a_later_pass_prompt_defines_its_ledger_status_on_the_defect_and_every_seat_must_finish_structured() -> (
    None
):
    args = {**_ARGS, "pass": 2}
    args["slices"] = [
        {
            **_ARGS["slices"][0],
            "ledger": [{"id": "S-S1", "file": "a.py", "line": 3, "claim": "off by one"}],
        }
    ]
    _, _, prompts = _harness(args, {})
    finder = prompts["find:S:sonnet"]
    assert "STILL_TRUE means the defect is still there" in finder, (
        "pass ≥ 2 keys the status on the DEFECT (R-3)"
    )
    assert "NOW_FALSE means it is gone" in finder
    assert "StructuredOutput" in prompts["find:S:haiku"], (
        "every finder is told to finish with the schema"
    )
