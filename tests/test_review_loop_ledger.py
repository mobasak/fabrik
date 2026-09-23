"""scripts/review_loop_ledger.py — a review pass's ledger read from its workflow run into a FILE (row 5b, D-357).

The lead used to re-derive each pass from the tool's escaped output or an ad-hoc poll script, and the next
pass's claim list was hand-typed (once as strings the script rendered `undefined`). Finding 30 of
command-loop-performance.md: the lead reads a file, not its scrollback. Driven on a fabricated run directory
in the shape Claude Code writes: `journal.jsonl` (started/result rows keyed by agentId) and one transcript per
agent whose first and last `timestamp` bound the seat's minutes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "scripts" / "review_loop_ledger.py"


def _run_dir(tmp: Path) -> Path:
    d = tmp / "wf_x"
    d.mkdir()
    cand = {
        "id": "A-S1",
        "file": "a.py",
        "line": 3,
        "failure_class": "logic",
        "claim": "off by one",
        "scenario": "s",
        "check": "c",
        "confidence": "CONFIRMED",
    }
    seats = {
        "a1": (
            "find:A:sonnet",
            "sonnet",
            {
                "files_read": ["a.py"],
                "candidates": [cand],
                "notes": "n",
                "ledger_status": [
                    {"id": "A-S0", "status": "NOW_FALSE", "command": "c", "output": "o"}
                ],
            },
            0,
            3,
        ),
        "a2": (
            "find:A:haiku",
            "haiku",
            {"files_read": ["a.py"], "candidates": [], "notes": "n"},
            0,
            2,
        ),
        "a3": (
            "refute:A",
            "sonnet",
            {
                "verdicts": [
                    {
                        "id": "A-S1",
                        "verdict": "confirmed",
                        "command": "c",
                        "output": "o",
                        "mechanism": "m",
                    }
                ]
            },
            3,
            62,
        ),
        "a4": ("find:B:sonnet", "sonnet", None, 0, 1),
    }
    rows = [{"type": "launched"}]
    for aid, (label, model, result, start, end) in seats.items():
        rows.append({"type": "started", "agentId": aid, "label": label, "phase": "x"})
        if result is not None:
            rows.append({"type": "result", "agentId": aid, "result": result})
        (d / f"agent-{aid}.meta.json").write_text(
            json.dumps({"description": label, "model": model})
        )
        (d / f"agent-{aid}.jsonl").write_text(
            json.dumps({"timestamp": f"2026-09-23T06:{start:02d}:00.000Z"})
            + "\n"
            + json.dumps({"timestamp": f"2026-09-23T{6 + end // 60:02d}:{end % 60:02d}:00.000Z"})
            + "\n"
        )
    (d / "journal.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return d


def _tool(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), *args], capture_output=True, text=True, timeout=30, check=False
    )


def test_read_writes_the_pass_ledger_to_a_file_with_every_seat_timed(tmp_path: Path) -> None:
    out = tmp_path / "pass-1.json"
    r = _tool("read", str(_run_dir(tmp_path)), "--out", str(out), "--box", "12")
    assert r.returncode == 0, r.stderr
    doc = json.loads(out.read_text())
    seats = {s["label"]: s for s in doc["seats"]}
    assert seats["find:A:sonnet"]["minutes"] == 3.0 and seats["refute:A"]["minutes"] == 59.0
    assert seats["refute:A"]["over_box"] is True and seats["find:A:sonnet"]["over_box"] is False
    assert seats["find:B:sonnet"]["returned"] is False, "a seat with no result row is a failed seat"
    assert [c["id"] for c in doc["candidates"]] == ["A-S1"] and doc["candidates"][0][
        "seat"
    ] == "find:A:sonnet"
    assert doc["verdicts"][0]["verdict"] == "confirmed"
    assert doc["ledger_status"][0]["id"] == "A-S0"
    assert "OVER BOX" in r.stdout and "refute:A" in r.stdout and "NO RESULT" in r.stdout, r.stdout


def test_next_builds_the_following_pass_ledger_as_objects_grouped_by_slice(tmp_path: Path) -> None:
    out = tmp_path / "pass-1.json"
    _tool("read", str(_run_dir(tmp_path)), "--out", str(out))
    r = _tool("next", str(out), "--ids", "A-S1")
    assert r.returncode == 0, r.stderr
    slices = json.loads(r.stdout)
    assert slices == [
        {"name": "A", "ledger": [{"id": "A-S1", "file": "a.py", "line": 3, "claim": "off by one"}]}
    ]
    bad = _tool("next", str(out), "--ids", "A-S1,Z-S9")
    assert bad.returncode == 2 and "Z-S9" in bad.stderr, (
        "an id the pass never raised is refused by name"
    )


def test_a_missing_run_dir_refuses_loudly(tmp_path: Path) -> None:
    r = _tool("read", str(tmp_path / "absent"))
    assert r.returncode == 2 and "journal.jsonl" in r.stderr


def _journal(tmp: Path, rows: list, stamps: dict | None = None) -> Path:
    d = tmp / "edge"
    d.mkdir()
    (d / "journal.jsonl").write_text(
        "".join((r if isinstance(r, str) else json.dumps(r)) + "\n" for r in rows)
    )
    for aid, ts in (stamps or {}).items():
        (d / f"agent-{aid}.jsonl").write_text(
            "".join(json.dumps({"timestamp": t}) + "\n" for t in ts)
        )
    return d


def _cand2(cid: str, line: int) -> dict:
    return {"id": cid, "file": "a.py", "line": line, "claim": f"c{line}"}


def test_nothing_the_journal_carries_is_dropped_or_read_as_in_box(tmp_path: Path) -> None:
    """Review of D-357, pass 1: a result row with no started row lost its candidates (A-S1/B-S1); a malformed
    started row died as the `next` error (A-S3); a duplicate result row silently replaced the first (A-S7); an
    untimed or backwards-timed seat read as within its box (A-S4/B-S2/A-H1)."""
    d = _journal(
        tmp_path,
        [
            {"type": "started", "agentId": "a1", "label": "find:A:sonnet"},
            {"type": "started", "label": "find:A:haiku"},
            "{not json",
            {"type": "result", "agentId": "a1", "result": {"candidates": [_cand2("A-S1", 1)]}},
            {"type": "result", "agentId": "a1", "result": {"candidates": [_cand2("A-S2", 2)]}},
            {"type": "result", "agentId": "orphan", "result": {"candidates": [_cand2("A-S9", 9)]}},
        ],
        {"a1": ["2026-09-23T06:30:00Z", "2026-09-23T06:00:00Z"]},
    )
    out = tmp_path / "p.json"
    r = _tool("read", str(d), "--out", str(out), "--box", "12")
    assert r.returncode == 0, r.stderr
    doc = json.loads(out.read_text())
    ids = sorted(c["id"] for c in doc["candidates"])
    assert ids == ["A-S1", "A-S2", "A-S9"], ids
    seats = {s["label"]: s for s in doc["seats"]}
    assert seats["find:A:sonnet"]["minutes"] == 30.0 and seats["find:A:sonnet"]["over_box"] is True
    assert seats["find:A:sonnet"]["duplicate_results"] == 2
    assert "orphan:orphan" in seats and seats["orphan:orphan"]["returned"] is True
    assert "UNTIMED" in r.stdout and "DUPLICATE RESULT" in r.stdout and "unreadable" in r.stdout, (
        r.stdout
    )


def test_next_refuses_an_ambiguous_or_slice_less_id(tmp_path: Path) -> None:
    """A-S2/A-S5/B-H1: an id two seats both raised, or one with no `<slice>-` prefix, cannot name one claim."""
    d = _journal(
        tmp_path,
        [
            {"type": "started", "agentId": "a1", "label": "find:A:sonnet"},
            {"type": "started", "agentId": "a2", "label": "find:A:haiku"},
            {
                "type": "result",
                "agentId": "a1",
                "result": {"candidates": [_cand2("A-S1", 1), _cand2("nodash", 5)]},
            },
            {"type": "result", "agentId": "a2", "result": {"candidates": [_cand2("A-S1", 99)]}},
        ],
    )
    out = tmp_path / "p.json"
    _tool("read", str(d), "--out", str(out))
    amb = _tool("next", str(out), "--ids", "A-S1")
    assert amb.returncode == 2 and "A-S1" in amb.stderr and "more than once" in amb.stderr, (
        amb.stderr
    )
    bare = _tool("next", str(out), "--ids", "nodash")
    assert bare.returncode == 2 and "nodash" in bare.stderr and "slice" in bare.stderr, bare.stderr


def test_an_identical_repeat_is_one_claim_and_an_orphan_seat_cannot_pass_for_a_real_one(
    tmp_path: Path,
) -> None:
    """Review of D-357 pass 2: keeping every result row made a byte-identical repeat 'raised more than once', so
    `next` refused the seat's own ids (A-NEW1); an orphan seat labelled by its bare agentId could read as a real
    seat's label (A-NEW2)."""
    same = {"type": "result", "agentId": "a1", "result": {"candidates": [_cand2("A-S1", 1)]}}
    d = _journal(
        tmp_path,
        [
            {"type": "started", "agentId": "a1", "label": "a9"},
            same,
            same,
            {"type": "result", "agentId": "a9", "result": {"candidates": [_cand2("A-S7", 7)]}},
        ],
    )
    out = tmp_path / "p.json"
    _tool("read", str(d), "--out", str(out))
    r = _tool("next", str(out), "--ids", "A-S1")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [
        {"name": "A", "ledger": [{"id": "A-S1", "file": "a.py", "line": 1, "claim": "c1"}]}
    ]
    labels = [s["label"] for s in json.loads(out.read_text())["seats"]]
    assert labels == ["a9", "orphan:a9"], labels


def test_every_seat_carries_its_tokens_counted_once_per_message(tmp_path: Path) -> None:
    """Row 5b chunk 3 (D-358): a seat's tokens come from its own transcript — every assistant message's `usage`,
    counted ONCE per message id (a streamed message is logged more than once). No collector is needed: Claude
    Code's token metrics label a user-defined agent `custom`, while the transcript names the seat."""
    d = tmp_path / "wf_t"
    d.mkdir()
    (d / "journal.jsonl").write_text(
        json.dumps({"type": "started", "agentId": "a1", "label": "find:A:sonnet"})
        + "\n"
        + json.dumps({"type": "result", "agentId": "a1", "result": {"candidates": []}})
        + "\n"
    )
    u1 = {
        "input_tokens": 10,
        "output_tokens": 100,
        "cache_read_input_tokens": 1000,
        "cache_creation_input_tokens": 50,
    }
    u2 = {
        "input_tokens": 5,
        "output_tokens": 40,
        "cache_read_input_tokens": 2000,
        "cache_creation_input_tokens": 0,
    }
    lines = [
        {"timestamp": "2026-09-23T06:00:00Z", "message": {"id": "m1", "usage": u1}},
        {"timestamp": "2026-09-23T06:00:01Z", "message": {"id": "m1", "usage": u1}},
        {"timestamp": "2026-09-23T06:02:00Z", "message": {"id": "m2", "usage": u2}},
    ]
    (d / "agent-a1.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
    out = tmp_path / "p.json"
    r = _tool("read", str(d), "--out", str(out))
    assert r.returncode == 0, r.stderr
    seat = json.loads(out.read_text())["seats"][0]
    assert seat["tokens"] == {
        "input": 15,
        "output": 140,
        "cache_read": 3000,
        "cache_create": 50,
        "messages": 2,
    }, seat
    assert "3,000 cache read" in r.stdout and "140 out" in r.stdout, r.stdout


def test_a_message_logged_with_a_trailing_zero_line_or_no_id_is_still_counted(
    tmp_path: Path,
) -> None:
    """Review of D-358 pass 1: last-write-wins let a trailing all-zero line for an id erase its real usage (A-S3 —
    command_run.py takes the per-field maximum for exactly this), and a message without an id was dropped (B-S2)."""
    d = tmp_path / "wf_z"
    d.mkdir()
    (d / "journal.jsonl").write_text(
        json.dumps({"type": "started", "agentId": "a1", "label": "s"}) + "\n"
    )
    real = {
        "input_tokens": 10,
        "output_tokens": 100,
        "cache_read_input_tokens": 1000,
        "cache_creation_input_tokens": 5,
    }
    zero = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    lines = [
        {"message": {"id": "m1", "usage": real}},
        {"message": {"id": "m1", "usage": zero}},
        {
            "message": {
                "usage": {
                    "input_tokens": 1,
                    "output_tokens": 2,
                    "cache_read_input_tokens": 3,
                    "cache_creation_input_tokens": None,
                }
            }
        },
    ]
    (d / "agent-a1.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
    out = tmp_path / "p.json"
    _tool("read", str(d), "--out", str(out))
    t = json.loads(out.read_text())["seats"][0]["tokens"]
    assert t == {
        "input": 11,
        "output": 102,
        "cache_read": 1003,
        "cache_create": 5,
        "messages": 2,
    }, t
