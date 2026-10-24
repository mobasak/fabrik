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

import pytest

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
        "a5": (
            "find:B:haiku",
            "haiku",
            {
                "files_read": [],
                "candidates": [],
                "notes": "No, I have not stopped.",
                "ledger_status": [
                    {"id": "B-H0", "status": "NOW_FALSE", "command": "c", "output": "o"}
                ],
            },
            0,
            1,
        ),
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
    # 01M4C00TSS: a finder that returned but listed no file reviewed nothing — flagged, and its ledger rows tagged
    assert (
        seats["find:B:haiku"]["returned"] is True and seats["find:B:haiku"]["read_no_file"] is True
    )
    assert (
        seats["find:A:haiku"]["read_no_file"] is False
        and seats["refute:A"]["read_no_file"] is False
    )
    assert [x.get("read_no_file", False) for x in doc["ledger_status"]] == [False, True]
    # kaizen 01M55F55HE: a resumed review rebuilds its close-out from the pass file, so each seat's coverage
    # statement and MACHINERY block (its `notes`) and what it read survive the read, per seat
    assert seats["find:A:sonnet"]["notes"] == ["n"]
    assert seats["find:A:sonnet"]["files_read"] == ["a.py"]
    assert seats["find:B:haiku"]["notes"] == ["No, I have not stopped."]
    assert seats["find:B:haiku"]["files_read"] == []
    assert seats["find:B:sonnet"]["notes"] == [] and seats["find:B:sonnet"]["files_read"] == []
    assert (
        "find:B:haiku" in r.stdout
        and "READ 0 FILES" in r.stdout
        and "(find:B:haiku, READ 0 FILES)" in r.stdout
    )
    assert "1 read 0 files" in r.stdout, r.stdout


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


def test_a_seat_that_returns_more_than_once_keeps_one_clean_report_list(tmp_path: Path) -> None:
    """kaizen 01M55F55HE, review pass 1: `files_read` is the union of every result's string entries, trimmed,
    deduplicated and in first-seen order — a blank, a non-string or a non-list never reads as a file, the same rule
    `read_no_file` applies — and `notes` keeps each non-blank string note, so an off-schema result adds nothing."""
    d = _journal(
        tmp_path,
        [
            {"type": "started", "agentId": "a1", "label": "find:A:sonnet"},
            {
                "type": "result",
                "agentId": "a1",
                "result": {
                    "files_read": ["a.py", "", None, 3, {"p": "q"}, " b.py "],
                    "notes": "first",
                },
            },
            {
                "type": "result",
                "agentId": "a1",
                "result": {"files_read": ["b.py", "a.py", "c.py"], "notes": "   "},
            },
            {"type": "result", "agentId": "a1", "result": {"files_read": "a.py", "notes": ["x"]}},
            {"type": "started", "agentId": "a2", "label": "find:A:haiku"},
            {"type": "result", "agentId": "a2", "result": {"files_read": ["", None], "notes": "n"}},
        ],
    )
    out = tmp_path / "p.json"
    r = _tool("read", str(d), "--out", str(out))
    assert r.returncode == 0, r.stderr
    seats = {s["label"]: s for s in json.loads(out.read_text())["seats"]}
    assert seats["find:A:sonnet"]["duplicate_results"] == 3
    assert seats["find:A:sonnet"]["files_read"] == ["a.py", "b.py", "c.py"]
    assert seats["find:A:sonnet"]["notes"] == ["first"]
    assert (
        seats["find:A:haiku"]["files_read"] == [] and seats["find:A:haiku"]["read_no_file"] is True
    )


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


def test_read_flags_a_present_defect_with_no_candidate_and_seats_that_disagree(
    tmp_path: Path,
) -> None:
    """W-729416b3 (mail 01M48MQ2HS): a seat that reports a defect PRESENT but raises no candidate is the shape of
    the label inversion (161 of 587 such seats on the box, 104 Haiku), and two seats giving one id different
    statuses is a disagreement the lead must settle — both printed, never a gate; legacy labels count too."""
    row = lambda i, s: {"id": i, "status": s, "command": "c", "output": "o"}  # noqa: E731
    d = _journal(
        tmp_path,
        [
            {"type": "started", "agentId": "a1", "label": "find:A:haiku"},
            {"type": "started", "agentId": "a2", "label": "find:A:sonnet"},
            {"type": "started", "agentId": "a3", "label": "find:B:sonnet"},
            {"type": "started", "agentId": "a4", "label": "find:B:haiku"},
            {"type": "started", "agentId": "a5", "label": "find:C:haiku"},
            # A: haiku says the defect persists and raises nothing; sonnet says it is absent
            {
                "type": "result",
                "agentId": "a1",
                "result": {
                    "files_read": ["a.py"],
                    "candidates": [],
                    "ledger_status": [row("A-S1", "STILL_TRUE")],
                },
            },
            {
                "type": "result",
                "agentId": "a2",
                "result": {
                    "files_read": ["a.py"],
                    "candidates": [],
                    "ledger_status": [row("A-S1", "DEFECT_ABSENT")],
                },
            },
            # B: both say present (one legacy label), and each raises its candidate — no flag at all
            {
                "type": "result",
                "agentId": "a3",
                "result": {
                    "files_read": ["b.py"],
                    "candidates": [_cand2("B-S1", 1)],
                    "ledger_status": [row("B-S0", "DEFECT_PRESENT")],
                },
            },
            {
                "type": "result",
                "agentId": "a4",
                "result": {
                    "files_read": ["b.py"],
                    "candidates": [_cand2("B-H1", 2)],
                    "ledger_status": [row("B-S0", "STILL_TRUE")],
                },
            },
            # C: a NEW defect with no candidate is the same shape (review B3 r1 A-S1)
            {
                "type": "result",
                "agentId": "a5",
                "result": {
                    "files_read": ["c.py"],
                    "candidates": [],
                    "ledger_status": [row("C-S0", "NEW")],
                },
            },
        ],
    )
    out = tmp_path / "p.json"
    r = _tool("read", str(d), "--out", str(out), "--box", "12")
    assert r.returncode == 0, r.stderr
    flags = json.loads(out.read_text())["ledger_flags"]
    assert {(f["kind"], f.get("seat"), f["id"]) for f in flags} == {
        ("contradiction", "find:A:haiku", "A-S1"),
        ("disagree", None, "A-S1"),
        ("contradiction", "find:C:haiku", "C-S0"),
    }, flags
    assert "CONTRADICTION A-S1 (find:A:haiku)" in r.stdout and "DISAGREE A-S1" in r.stdout, r.stdout
    assert "B-S0" not in " ".join(
        ln for ln in r.stdout.splitlines() if "CONTRADICTION" in ln or "DISAGREE" in ln
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
    # mail 01M4PHYNXJ: the refusal is the menu — every claim with its seat and file:line, and the exact path out
    assert "a.py:1" in amb.stderr and "a.py:99" in amb.stderr, amb.stderr
    assert "find:A:sonnet" in amb.stderr and "find:A:haiku" in amb.stderr, amb.stderr
    assert "--args" in amb.stderr and amb.stdout == "", amb.stderr
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
    # A-S7 is outside --ids and no run file was given, so its verdict is not judged — and that is said (W-b1f67743)
    assert "NOT CHECKED 1 candidate(s) outside --ids" in r.stderr, r.stderr
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


def test_next_keeps_a_hyphenated_slice_name_whole() -> None:
    """Review of chunk 6, A-S1: a section slice named `rule-grammar` raises `rule-grammar-O1`; splitting on the
    first `-` renamed it `rule` and re-attached its ledger to no round-1 slice."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import review_loop_ledger as rl

    doc = {
        "candidates": [
            {
                "id": "rule-grammar-O1",
                "file": "s.md",
                "line": 3,
                "claim": "x",
                "seat": "find:rule-grammar:opus",
            },
            {"id": "rest-of-spec-S2", "file": "s.md", "line": 9, "claim": "y"},
        ]
    }
    out = rl.next_ledger(doc, ["rule-grammar-O1", "rest-of-spec-S2"])
    assert sorted(s["name"] for s in out) == ["rest-of-spec", "rule-grammar"], out


@pytest.mark.parametrize(
    ("seat", "slice_name"),
    [
        ("find:A:sonnet:retry", "A"),
        ("find:A:opus:retry", "A"),
        ("find:rule-grammar:haiku:retry", "rule-grammar"),
        ("find:x-y:sonnet:retry", "x-y"),
        ("find:a:b:sonnet:retry", "a:b"),
    ],
)
def test_next_attributes_a_retry_finders_candidate_to_its_own_slice(
    seat: str, slice_name: str
) -> None:
    """W-6399d1a3: a finder retry runs under `find:<slice>:<model>:retry` (fabrik-review-loop.js finder label), and
    splitting off only the last `:` field named a phantom slice `<slice>:<model>`, so the next pass carried that
    candidate's claim under a slice no round-1 seat owns. Five spellings — models, a hyphenated and a colon-bearing
    slice name — beside a first-attempt seat of another slice."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import review_loop_ledger as rl

    cid = f"{slice_name}-S1"
    doc = {
        "candidates": [
            {"id": cid, "file": "a.py", "line": 3, "claim": "x", "seat": seat},
            {"id": "other-H1", "file": "s.md", "line": 9, "claim": "y", "seat": "find:other:haiku"},
        ]
    }
    out = rl.next_ledger(doc, [cid, "other-H1"])
    assert sorted(s["name"] for s in out) == sorted([slice_name, "other"]), out


# --- next --args: the verdicts' own ids and whole slices (mail 01M4PHYNXJ) -----------------------------------


def _union(cid: str, line: int, claim: str, seat: str = "sonnet") -> dict:
    return {
        "id": cid,
        "file": "a.py",
        "line": line,
        "failure_class": "logic",
        "claim": claim,
        "seat": seat,
    }


def _run_file(tmp: Path) -> Path:
    """A Workflow run file as the harness keeps it: the launch `args` and the `result` whose union candidates
    carry the ids the verdicts use — `A-S1#2` is the workflow's own suffix for a second claim under `A-S1`."""
    args = {
        "pass": 1,
        "slices": [
            {
                "name": "A",
                "files": ["a.py"],
                "priority": "p-A",
                "models": ["sonnet", "haiku"],
                "scope": "s-A",
                "ledger": [{"id": "A-OLD", "claim": "stale"}],
            },
            {
                "name": "B",
                "files": ["b.py", "c.py"],
                "models": ["opus"],
                "agent": "fabrik-researcher",
            },
            {"name": "C", "files": ["d.py"]},
        ],
    }
    result = {
        "slices": [
            {
                "name": "A",
                "candidates": [_union("A-S1", 3, "first"), _union("A-S1#2", 40, "second", "haiku")],
            },
            {"name": "B", "candidates": [_union("B-O1", 7, "bee", "opus")]},
            {"name": "C", "candidates": []},
        ]
    }
    p = tmp / "wf_run.json"
    p.write_text(json.dumps({"runId": "wf_x", "args": args, "result": result}))
    return p


def _pass_file(tmp: Path) -> Path:
    """The raw pass file `read` writes: both seats raised `A-S1`, so it names two claims here."""
    p = tmp / "pass.json"
    p.write_text(
        json.dumps(
            {
                "candidates": [
                    {**_union("A-S1", 3, "first"), "seat": "find:A:sonnet"},
                    {**_union("A-S1", 40, "second"), "seat": "find:A:haiku"},
                    {**_union("B-O1", 7, "bee"), "seat": "find:B:opus"},
                ]
            }
        )
    )
    return p


def test_next_args_resolves_the_verdicts_own_ids_and_emits_whole_slices(tmp_path: Path) -> None:
    r = _tool(
        "next",
        str(_pass_file(tmp_path)),
        "--ids",
        "A-S1,A-S1#2,B-O1",
        "--args",
        str(_run_file(tmp_path)),
    )
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [
        {
            "name": "A",
            "files": ["a.py"],
            "models": ["sonnet", "haiku"],
            "scope": "s-A",
            "priority": "p-A",
            "ledger": [
                {"id": "A-S1", "file": "a.py", "line": 3, "claim": "first"},
                {"id": "A-S1#2", "file": "a.py", "line": 40, "claim": "second"},
            ],
        },
        {
            "name": "B",
            "files": ["b.py", "c.py"],
            "models": ["opus"],
            "agent": "fabrik-researcher",
            "ledger": [{"id": "B-O1", "file": "a.py", "line": 7, "claim": "bee"}],
        },
    ]
    # a slice no id names is said, never silently dropped; the stamp is counted before launch
    assert "not carried: C" in r.stderr, r.stderr
    assert "DISPATCH: 3 finder(s) + 2 refuter(s) = stamp 5" in r.stderr, r.stderr


def test_next_args_takes_a_bare_args_object_and_the_claims_from_the_pass_file(
    tmp_path: Path,
) -> None:
    bare = tmp_path / "args.json"
    bare.write_text(json.dumps(json.loads(_run_file(tmp_path).read_text())["args"]))
    r = _tool("next", str(_pass_file(tmp_path)), "--ids", "B-O1", "--args", str(bare))
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [
        {
            "name": "B",
            "files": ["b.py", "c.py"],
            "models": ["opus"],
            "agent": "fabrik-researcher",
            "ledger": [{"id": "B-O1", "file": "a.py", "line": 7, "claim": "bee"}],
        }
    ]
    assert (
        "not carried: A, C" in r.stderr
        and "DISPATCH: 1 finder(s) + 1 refuter(s) = stamp 2" in r.stderr
    )


@pytest.mark.parametrize(
    ("body", "ids", "needle"),
    [
        ("{not json", "B-O1", "not JSON"),
        (json.dumps({"args": {"pass": 2}}), "B-O1", "slices"),
        (json.dumps([1, 2]), "B-O1", "slices"),
        (
            json.dumps(
                {"args": {"slices": [{"name": "A", "files": ["a.py"]}]}, "result": {"slices": []}}
            ),
            "A-S1",
            "A-S1",
        ),
        (json.dumps({"slices": [{"name": "A", "files": ["a.py"]}]}), "B-O1", "slice B"),
    ],
)
def test_next_args_refuses_by_name(tmp_path: Path, body: str, ids: str, needle: str) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(body)
    r = _tool("next", str(_pass_file(tmp_path)), "--ids", ids, "--args", str(bad))
    assert r.returncode == 2 and needle in r.stderr and r.stdout == "", (r.returncode, r.stderr)
    assert "Traceback" not in r.stderr, r.stderr


def _run_with(tmp: Path, result: object, slices: list | None = None) -> Path:
    p = tmp / "wf_custom.json"
    launch = (
        slices
        if slices is not None
        else [{"name": "A", "files": ["a.py"]}, {"name": "B", "files": ["b.py"]}]
    )
    p.write_text(json.dumps({"args": {"slices": launch}, "result": result}))
    return p


@pytest.mark.parametrize(
    ("result", "ids", "needle"),
    [
        # review round 1 A-S2/A-H1/B-S2: one id carried by two different union rows names no single claim
        (
            {
                "slices": [
                    {"name": "A", "candidates": [_union("A-S1", 3, "x"), _union("A-S1", 9, "y")]}
                ]
            },
            "A-S1",
            "a.py:9",
        ),
        (
            {
                "slices": [
                    {"name": "A", "candidates": [_union("A-S1", 3, "x")]},
                    {"name": "B", "candidates": [_union("A-S1", 5, "z")]},
                ]
            },
            "A-S1",
            "a.py:5",
        ),
        # A-S4/B-S1: a result slice with no name, or candidates that are not a list, is malformed — refused by name
        ({"slices": [{"candidates": [_union("A-S1", 3, "x")]}]}, "A-S1", "name"),
        ({"slices": [{"name": "A", "candidates": 7}]}, "A-S1", "candidates"),
    ],
)
def test_next_args_refuses_an_ambiguous_or_malformed_union(
    tmp_path: Path, result: dict, ids: str, needle: str
) -> None:
    r = _tool(
        "next", str(_pass_file(tmp_path)), "--ids", ids, "--args", str(_run_with(tmp_path, result))
    )
    assert r.returncode == 2 and needle in r.stderr and r.stdout == "", (r.returncode, r.stderr)
    assert "Traceback" not in r.stderr, r.stderr


@pytest.mark.parametrize(
    ("slices", "needle"),
    [
        # A-H2: two launch slices under one name — which files/models apply is unknowable
        ([{"name": "A", "files": ["a.py"]}, {"name": "A", "files": ["z.py"]}], "slice A"),
        # A-H4: a launch slice with no files would emit a slice the workflow refuses
        ([{"name": "A", "priority": "p"}], "files"),
        # B-S3: models that are not a list would print a stamp the workflow never dispatches
        ([{"name": "A", "files": ["a.py"], "models": "sonnet"}], "models"),
    ],
)
def test_next_args_refuses_a_malformed_launch_slice(
    tmp_path: Path, slices: list, needle: str
) -> None:
    result = {"slices": [{"name": "A", "candidates": [_union("A-S1", 3, "x")]}]}
    r = _tool(
        "next",
        str(_pass_file(tmp_path)),
        "--ids",
        "A-S1",
        "--args",
        str(_run_with(tmp_path, result, slices)),
    )
    assert r.returncode == 2 and needle in r.stderr and r.stdout == "", (r.returncode, r.stderr)


def test_next_args_with_a_result_lacking_slices_reads_the_pass_file(tmp_path: Path) -> None:
    """A-H3: a run file whose result holds no `slices` (a run that died mid-pass) resolves against the pass file,
    where an ambiguous id still refuses."""
    run = _run_with(tmp_path, {"pass": 1})
    ok = _tool("next", str(_pass_file(tmp_path)), "--ids", "B-O1", "--args", str(run))
    assert ok.returncode == 0, ok.stderr
    assert json.loads(ok.stdout)[0]["ledger"] == [
        {"id": "B-O1", "file": "a.py", "line": 7, "claim": "bee"}
    ]
    amb = _tool("next", str(_pass_file(tmp_path)), "--ids", "A-S1", "--args", str(run))
    assert amb.returncode == 2 and "more than once" in amb.stderr, amb.stderr


def test_next_reads_each_id_once_and_refuses_an_unreadable_pass_file(tmp_path: Path) -> None:
    """A-S3: a repeated --ids entry is one ledger row; A-S1: a pass file that is not JSON is a refusal, never a
    traceback."""
    r = _tool("next", str(_pass_file(tmp_path)), "--ids", "B-O1,B-O1")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [
        {"name": "B", "ledger": [{"id": "B-O1", "file": "a.py", "line": 7, "claim": "bee"}]}
    ]
    bad = tmp_path / "torn.json"
    bad.write_text("{not json")
    t = _tool("next", str(bad), "--ids", "B-O1")
    assert t.returncode == 2 and "not JSON" in t.stderr and "Traceback" not in t.stderr, t.stderr


# --- the pin verb and the post-pass re-check (kaizen 01M4CGJZAX) --------------------------------------------


def _tool_in(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        cwd=str(cwd),
    )


_VCS_ENV = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "PATH": "/usr/bin:/bin",
}


def _repo(tmp: Path) -> Path:
    """A throwaway repo holding `a.py` and `sub/b.py`, committed once."""
    r = tmp / "repo"
    (r / "sub").mkdir(parents=True)
    (r / "a.py").write_text("A = 1\n")
    (r / "sub" / "b.py").write_text("B = 1\n")
    for argv in (
        ["init", "-q"],
        ["add", "a.py", "sub/b.py"],
        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base"],
    ):
        subprocess.run(["git", *argv], cwd=r, check=True, env=_VCS_ENV, capture_output=True)
    return r


def _writable(p: Path) -> bool:
    return bool(p.stat().st_mode & 0o222)


def _md5(p: Path) -> str:
    import hashlib

    return hashlib.md5(p.read_bytes()).hexdigest()


def test_pin_writes_read_only_pins_and_a_manifest(tmp_path: Path) -> None:
    """Rows 1790768995 and 1790353914: the verb, not the lead's hand, writes each slice file's pin with an md5
    manifest, and makes the pins AND their directories read-only — with the directory writable, `sed -i`
    (write-new-then-rename) mutated a 0444 pin at rc 0, as both design critiques executed."""
    repo, pins = _repo(tmp_path), tmp_path / "pins"
    got = _tool_in(repo, "pin", "--pins-dir", str(pins), "a.py", "sub/b.py")
    assert got.returncode == 0, got.stderr
    frag = json.loads(got.stdout.splitlines()[-1])
    want = {p: _md5(repo / p) for p in ("a.py", "sub/b.py")}
    assert frag["pins_dir"] == str(pins) and frag["pin_manifest"] == want, frag
    assert frag["digest"] == _md5(pins / "MANIFEST.md5"), frag
    for p in want:
        assert (pins / p).read_bytes() == (repo / p).read_bytes()
        assert not _writable(pins / p), f"{p} pin is writable"
    assert not _writable(pins) and not _writable(pins / "sub"), "a pins directory is writable"
    lines = sorted((pins / "MANIFEST.md5").read_text().splitlines())
    assert lines == sorted(f"{m}  {p}" for p, m in want.items()), lines
    sed = subprocess.run(
        ["sed", "-i", "s/A = 1/A = 9/", str(pins / "a.py")], capture_output=True, check=False
    )
    assert sed.returncode != 0 and _md5(pins / "a.py") == want["a.py"], "sed -i mutated a pin"


def test_pins_manifest_checks_the_copies_from_any_cwd(tmp_path: Path) -> None:
    """W-1008046c (site-provisioner 01M4RNTM85): MANIFEST.md5 is repo-relative — from the repo root
    it checks the LIVE files, and a seat cannot cd into the pins dir — so the copies were never
    checked. MANIFEST.pins.md5 names each copy by its absolute path (the pins_dir string the
    fragment prints), so one `md5sum -c` from ANY cwd checks the copies; `pins_digest` attests it."""
    repo, pins = _repo(tmp_path), tmp_path / "pins"
    got = _tool_in(repo, "pin", "--pins-dir", str(pins), "a.py", "sub/b.py")
    assert got.returncode == 0, got.stderr
    frag = json.loads(got.stdout.splitlines()[-1])
    pm = pins / "MANIFEST.pins.md5"
    assert frag["pins_digest"] == _md5(pm), frag
    lines = sorted(pm.read_text().splitlines())
    want = sorted(f"{_md5(repo / p)}  {frag['pins_dir']}/{p}" for p in ("a.py", "sub/b.py"))
    assert lines == want, lines
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    ok = subprocess.run(["md5sum", "-c", "--quiet", str(pm)], cwd=elsewhere, capture_output=True)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    (pins / "a.py").chmod(0o644)
    (pins / "a.py").write_text("A = 9\n")  # a seat that defeats the lock and alters a copy
    bad = subprocess.run(["md5sum", "-c", "--quiet", str(pm)], cwd=elsewhere, capture_output=True)
    assert bad.returncode != 0 and b"FAILED" in bad.stdout, bad.stdout
    live = subprocess.run(
        ["md5sum", "-c", "--quiet", str(pins / "MANIFEST.md5")], cwd=repo, capture_output=True
    )
    assert live.returncode == 0, "MANIFEST.md5 from the repo root still checks the live files"


@pytest.mark.parametrize(
    "name", ["MANIFEST.md5", "MANIFEST.json", "MANIFEST.pins.md5", "new\nline.py"]
)
def test_pin_refuses_reserved_and_newline_paths(tmp_path: Path, name: str) -> None:
    """A root file named like a manifest would be overwritten by it, and a newline in a path splits
    md5sum's line into a false FAILED: both refuse before anything is written."""
    repo, pins = _repo(tmp_path), tmp_path / "pins"
    (repo / name).write_text("x\n")
    got = _tool_in(repo, "pin", "--pins-dir", str(pins), "a.py", name)
    assert got.returncode != 0 and "cannot pin" in got.stderr, got.stderr
    assert not pins.exists()


def test_pin_refuses_a_newline_in_the_pins_dir(tmp_path: Path) -> None:
    """MANIFEST.pins.md5 carries the pins_dir string on every line, so a newline THERE splits the line
    exactly as one in a file path would (W-1008046c review A-S1): refused before anything is written."""
    repo, pins = _repo(tmp_path), tmp_path / "pi\nns"
    got = _tool_in(repo, "pin", "--pins-dir", str(pins), "a.py")
    assert got.returncode != 0 and "newline" in got.stderr, got.stderr
    assert not pins.exists() and not (tmp_path / "pi").exists()


def test_pin_from_a_ref_and_dirty_marker(tmp_path: Path) -> None:
    """A committed range is pinned from the commit (`--from`), never from a working tree that may carry WIP;
    the working-tree default names every file whose bytes are not HEAD's."""
    repo = _repo(tmp_path)
    (repo / "a.py").write_text("A = 2  # working-tree edit\n")
    got = _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "p1"), "--from", "HEAD", "a.py")
    assert got.returncode == 0, got.stderr
    assert (tmp_path / "p1" / "a.py").read_text() == "A = 1\n"
    assert "DIRTY" not in got.stderr
    wt = _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "p2"), "a.py", "sub/b.py")
    assert wt.returncode == 0, wt.stderr
    assert "DIRTY a.py" in wt.stderr and "DIRTY sub/b.py" not in wt.stderr, wt.stderr
    assert json.loads((tmp_path / "p2" / "MANIFEST.json").read_text())["source"] == "working-tree"
    assert json.loads((tmp_path / "p1" / "MANIFEST.json").read_text())["source"] != "working-tree"


def test_pin_records_the_base_sha_it_was_read_against(tmp_path: Path) -> None:
    """W-0b09fae6 (kaizen 01M5AHVAYZ): D-1051's delta brief names each pass's `base_sha`, so the pin records it
    — the full commit a seat archives and overlays the pins on: the `--base` commit when given, else the
    resolved `--from` ref, else HEAD — in MANIFEST.json and in the printed fragment, where a seat or a resuming
    lead can read it back."""
    repo = _repo(tmp_path)
    first = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    (repo / "a.py").write_text("A = 2\n")
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "second"],
        cwd=repo,
        check=True,
        env=_VCS_ENV,
        capture_output=True,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    wt = _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "wt"), "a.py")
    ref = _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "ref"), "--from", "HEAD~1", "a.py")
    assert wt.returncode == 0 and ref.returncode == 0, wt.stderr + ref.stderr
    assert json.loads((tmp_path / "wt" / "MANIFEST.json").read_text())["base_sha"] == head
    assert json.loads((tmp_path / "ref" / "MANIFEST.json").read_text())["base_sha"] == first
    assert json.loads(wt.stdout.strip().splitlines()[-1])["base_sha"] == head
    assert json.loads(ref.stdout.strip().splitlines()[-1])["base_sha"] == first
    # --base names the whole commit a seat copies from base_pin_dir in place of archiving base_sha, so the two agree
    based = _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "b"), "--base", "HEAD~1", "a.py")
    assert based.returncode == 0, based.stderr
    frag = json.loads(based.stdout.strip().splitlines()[-1])
    assert frag["base_sha"] == first and frag["base_pin_dir"] == f"{tmp_path / 'b'}.base"
    assert json.loads((tmp_path / "b" / "MANIFEST.json").read_text())["base_sha"] == first
    assert (
        tmp_path / "b.base" / "a.py"
    ).read_text() == "A = 1\n"  # the base_sha's bytes, not HEAD's


def test_pin_refuses_a_from_ref_that_names_no_commit(tmp_path: Path) -> None:
    """W-0b09fae6 review pass 1: `ls-tree` accepts a TREE, so a `--from <tree>` used to pin with a null base_sha —
    a pin no seat can archive. A `--from` that names no commit is refused before anything is written."""
    repo = _repo(tmp_path)
    tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    got = _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "p"), "--from", tree, "a.py")
    assert got.returncode != 0 and "names no commit" in got.stderr, got.stderr
    assert not (tmp_path / "p").exists()


def test_pin_from_a_ref_ignores_the_working_tree_shape(tmp_path: Path) -> None:
    """Review A-S1 (pin-refusal wording): `--from` reads the bytes from the commit, so a working-tree
    symlink or deletion at that path is irrelevant — the committed regular file is pinned. A path that
    escapes the repo is still refused lexically, and a symlink AT the ref still by its tree mode."""
    repo = _repo(tmp_path)
    (repo / "a.py").unlink()
    (repo / "a.py").symlink_to(tmp_path)  # an unrelated local symlink, pointing outside the repo
    got = _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "p1"), "--from", "HEAD", "a.py")
    assert got.returncode == 0, got.stderr
    assert (tmp_path / "p1" / "a.py").read_text() == "A = 1\n"
    out = _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "p2"), "--from", "HEAD", "../x.py")
    assert out.returncode == 2 and "outside the repo root" in out.stderr, out.stderr
    wt = _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "p3"), "a.py")
    assert wt.returncode == 2 and "a symlink" in wt.stderr, wt.stderr


def test_pin_base_extracts_the_commit_read_only(tmp_path: Path) -> None:
    """Row 1791115993: a whole base tree beside the pins, so a seat needs no repository command against the
    live checkout — the COMMITTED bytes, read-only to the directory level."""
    repo, pins = _repo(tmp_path), tmp_path / "pins"
    (repo / "a.py").write_text("A = 2  # working-tree edit\n")
    got = _tool_in(repo, "pin", "--pins-dir", str(pins), "--base", "HEAD", "a.py")
    assert got.returncode == 0, got.stderr
    base = Path(json.loads(got.stdout.splitlines()[-1])["base_pin_dir"])
    assert (base / "a.py").read_text() == "A = 1\n" and (base / "sub" / "b.py").is_file()
    assert not _writable(base / "a.py") and not _writable(base / "sub") and not _writable(base)


def test_pin_refuses_a_file_it_cannot_pin(tmp_path: Path) -> None:
    repo, pins = _repo(tmp_path), tmp_path / "pins"
    (tmp_path / "outside.py").write_text("X = 1\n")
    (repo / "link.py").symlink_to(tmp_path / "outside.py")
    for bad in ("missing.py", "../outside.py", "sub", "link.py"):
        got = _tool_in(repo, "pin", "--pins-dir", str(pins), "a.py", bad)
        assert got.returncode == 2 and bad in got.stderr, (bad, got.returncode, got.stderr)
    # from a commit too: `show REF:<dir>` prints a tree listing at rc 0, which was pinned as the file (review L-1)
    for bad in ("sub", "missing.py"):
        got = _tool_in(repo, "pin", "--pins-dir", str(pins), "--from", "HEAD", "a.py", bad)
        assert got.returncode == 2 and bad in got.stderr, (bad, got.returncode, got.stderr)
    assert not pins.exists(), "a refused pin wrote something"


def test_pin_refuses_a_used_dir_unless_replace(tmp_path: Path) -> None:
    """Each pass gets a NEW pins dir (a straggling seat from the last pass may still be reading the old one);
    re-pinning the same dir is an explicit `--replace`, and it must not die on the read-only bits it set."""
    repo, pins = _repo(tmp_path), tmp_path / "pins"
    assert _tool_in(repo, "pin", "--pins-dir", str(pins), "a.py").returncode == 0
    (repo / "a.py").write_text("A = 3\n")
    again = _tool_in(repo, "pin", "--pins-dir", str(pins), "a.py")
    assert again.returncode == 2 and "--replace" in again.stderr, again.stderr
    got = _tool_in(repo, "pin", "--pins-dir", str(pins), "--replace", "sub/b.py")
    assert got.returncode == 0, got.stderr
    assert not (pins / "a.py").exists(), (
        "a replaced dir kept a stale pin from the earlier file list"
    )
    assert (pins / "sub" / "b.py").is_file() and not _writable(pins / "sub" / "b.py")


def test_read_pins_flags_a_moved_pin_and_a_moved_live_file(tmp_path: Path) -> None:
    """Rows 1791023175 and 1790942447, at the pass's end: a changed pin is PIN MOVED — the pass is void, exit 3,
    and the seats live when it changed are named; a changed live file is LIVE MOVED, informational (exit 0): the
    lead's own fix or a sibling's commit moves it legitimately."""
    import os
    from datetime import UTC, datetime

    repo, pins = _repo(tmp_path), tmp_path / "pins"
    run = _run_dir(tmp_path)
    assert _tool_in(repo, "pin", "--pins-dir", str(pins), "a.py", "sub/b.py").returncode == 0
    out = tmp_path / "pass.json"
    clean = _tool_in(tmp_path, "read", str(run), "--out", str(out), "--pins", str(pins))
    assert clean.returncode == 0, clean.stderr
    got = json.loads(out.read_text())["pins"]
    assert (got["status"], got["checked"], got["pin_moved"], got["live_moved"]) == (
        "checked",
        2,
        [],
        [],
    )
    (repo / "sub" / "b.py").write_text("B = 2  # a sibling edit\n")
    live = _tool_in(tmp_path, "read", str(run), "--out", str(out), "--pins", str(pins))
    assert live.returncode == 0 and "LIVE MOVED sub/b.py" in live.stdout, (
        live.returncode,
        live.stdout,
    )
    pins.chmod(0o755)
    (pins / "a.py").chmod(0o644)
    (pins / "a.py").write_text("A = 99  # a seat's mutant\n")
    # the mutant lands inside find:A:sonnet's span (06:00–06:03 in _run_dir), outside find:B:haiku's
    stamp = datetime(2026, 9, 23, 6, 2, tzinfo=UTC).timestamp()
    os.utime(pins / "a.py", (stamp, stamp))
    moved = _tool_in(tmp_path, "read", str(run), "--out", str(out), "--pins", str(pins))
    assert moved.returncode == 3, (moved.returncode, moved.stdout, moved.stderr)
    assert "PIN MOVED a.py" in moved.stdout and "find:A:sonnet" in moved.stdout, moved.stdout
    doc = json.loads(out.read_text())["pins"]
    assert doc["pin_moved"] == ["a.py"] and doc["live_moved"] == ["sub/b.py"], doc
    assert "find:A:sonnet" in doc["live_at_move"]["a.py"], doc


def test_read_says_when_pins_were_not_checked(tmp_path: Path) -> None:
    """COBRA (D-253) on an optional manifest: the omission shows on the path the lead READS — the pass file and
    the summary — never only in the workflow's return value, which the lead is told not to read."""
    run, out = _run_dir(tmp_path), tmp_path / "pass.json"
    plain = _tool_in(tmp_path, "read", str(run), "--out", str(out))
    assert plain.returncode == 0 and "pins: NOT CHECKED" in plain.stdout, plain.stdout
    empty = tmp_path / "hand-pins"
    empty.mkdir()
    unp = _tool_in(tmp_path, "read", str(run), "--out", str(out), "--pins", str(empty))
    assert unp.returncode == 0 and "UNPINNED" in unp.stdout, unp.stdout
    assert json.loads(out.read_text())["pins"]["status"] == "unpinned"


def test_pin_base_skips_an_absolute_link_and_names_it(tmp_path: Path) -> None:
    """The hub itself tracks an absolute symlink (`vault`): the safe extract refuses it, and the first dogfood run
    of `pin --base` on the hub died with a traceback and a half-extracted 94 MB base. Such a member is SKIPPED and
    named; the rest of the base lands."""
    repo, pins = _repo(tmp_path), tmp_path / "pins"
    (repo / "vault").symlink_to("/etc/hostname")
    subprocess.run(["git", "add", "vault"], cwd=repo, check=True, env=_VCS_ENV, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "link"],
        cwd=repo,
        check=True,
        env=_VCS_ENV,
        capture_output=True,
    )
    got = _tool_in(repo, "pin", "--pins-dir", str(pins), "--base", "HEAD", "a.py")
    assert got.returncode == 0, got.stderr
    frag = json.loads(got.stdout.splitlines()[-1])
    assert frag["base_skipped"] == ["vault"] and "SKIPPED vault" in got.stderr, (frag, got.stderr)
    assert (Path(frag["base_pin_dir"]) / "a.py").is_file()
    assert not (Path(frag["base_pin_dir"]) / "vault").exists()


def test_pin_base_names_a_skipped_escaping_link(tmp_path: Path) -> None:
    """kaizen 01M5BMDT08 (Fable critique 7): a RELATIVE link climbing out of the repo is skipped like an absolute
    one, and its SKIPPED line says what it is — it used to call every skipped member "an absolute link"."""
    repo, pins = _repo(tmp_path), tmp_path / "pins"
    (repo / "esc").symlink_to("../outside")
    subprocess.run(["git", "add", "esc"], cwd=repo, check=True, env=_VCS_ENV, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "link"],
        cwd=repo,
        check=True,
        env=_VCS_ENV,
        capture_output=True,
    )
    got = _tool_in(repo, "pin", "--pins-dir", str(pins), "--base", "HEAD", "a.py")
    assert got.returncode == 0, got.stderr
    assert json.loads(got.stdout.splitlines()[-1])["base_skipped"] == ["esc"]
    assert "SKIPPED esc — " in got.stderr and "(an absolute or escaping link, or a device)" in got.stderr, got.stderr


def test_pin_refuses_a_pins_dir_that_is_a_file_and_rolls_back_a_failed_write(
    tmp_path: Path,
) -> None:
    """Review pass 1: A-S1 — `--pins-dir <an existing file>` raised NotADirectoryError past main(), a traceback at
    rc 1; A-S3 — an OSError mid-write left a half-written, still-writable pins dir. Both are now exit 2 with
    nothing left behind."""
    repo = _repo(tmp_path)
    afile = tmp_path / "taken"
    afile.write_text("x")
    got = _tool_in(repo, "pin", "--pins-dir", str(afile), "a.py")
    assert (
        got.returncode == 2 and "not a directory" in got.stderr and "Traceback" not in got.stderr
    ), got.stderr
    # a pins dir whose PARENT is read-only cannot be written: the verb must refuse cleanly, leaving nothing
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o555)
    try:
        got = _tool_in(repo, "pin", "--pins-dir", str(locked / "pins"), "a.py")
        assert got.returncode == 2 and "Traceback" not in got.stderr, (got.returncode, got.stderr)
        assert not (locked / "pins").exists()
    finally:
        locked.chmod(0o755)


def test_read_pins_attributes_a_seat_with_a_one_line_transcript(tmp_path: Path) -> None:
    """Review A-S2: a one-timestamp transcript is a zero-width span, so a seat that logged once and wrote the pin
    a few seconds later was never named. Spans are widened by `_SLACK` on both sides."""
    import os
    from datetime import UTC, datetime

    repo, pins = _repo(tmp_path), tmp_path / "pins"
    run = tmp_path / "wf_one"
    run.mkdir()
    (run / "journal.jsonl").write_text(
        json.dumps({"type": "started", "agentId": "z1", "label": "find:A:haiku"}) + "\n"
    )
    (run / "agent-z1.jsonl").write_text(
        json.dumps({"timestamp": "2026-09-23T06:00:00.000Z"}) + "\n"
    )
    assert _tool_in(repo, "pin", "--pins-dir", str(pins), "a.py").returncode == 0
    pins.chmod(0o755)
    (pins / "a.py").chmod(0o644)
    (pins / "a.py").write_text("A = 7\n")
    stamp = datetime(2026, 9, 23, 6, 0, 30, tzinfo=UTC).timestamp()
    os.utime(pins / "a.py", (stamp, stamp))
    out = tmp_path / "pass.json"
    got = _tool_in(tmp_path, "read", str(run), "--out", str(out), "--pins", str(pins))
    assert got.returncode == 3, got.stdout
    assert json.loads(out.read_text())["pins"]["live_at_move"]["a.py"] == ["find:A:haiku"]


# --- a seat's stray write into the live repo (infra 01M4CV040F) ---------------------------------------------------


def _vcs(repo: Path, *argv: str) -> None:
    subprocess.run(
        ["g" + "it", "-c", "user.email=t@t", "-c", "user.name=t", *argv],
        cwd=repo,
        check=True,
        env=_VCS_ENV,
        capture_output=True,
    )


def _leaky_repo(tmp: Path) -> Path:
    """`_repo` plus a committed .gitignore ignoring `/arch/` (the hub's own rule for the recipe's tar target) and
    an untracked file that already exists at pin time."""
    repo = _repo(tmp)
    (repo / ".gitignore").write_text("/arch/\n")
    _vcs(repo, "add", ".gitignore")
    _vcs(repo, "commit", "-q", "-m", "ignore")
    (repo / "old.txt").write_text("already here\n")
    return repo


def _tree_lines(out: str) -> list[str]:
    kinds = ("NEW UNTRACKED", "NEW IGNORED", "NEW MODIFIED", "CHANGED AGAIN", "SEAT ARCHIVE")
    return [ln for ln in out.splitlines() if ln.startswith(kinds)]


def test_pin_refuses_a_subdirectory_and_records_the_tree(tmp_path: Path) -> None:
    """From a subdirectory the listing covers only that subtree and misses a root-level tarball (both design
    critiques executed it), so `pin` runs from the toplevel only — and records the tree there before any write."""
    repo = _leaky_repo(tmp_path)
    sub = _tool_in(repo / "sub", "pin", "--pins-dir", str(tmp_path / "p0"), "b.py")
    assert sub.returncode == 2 and "toplevel" in sub.stderr, (sub.returncode, sub.stderr)
    assert _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "p1"), "a.py").returncode == 0
    tree = json.loads((tmp_path / "p1" / "MANIFEST.json").read_text())["tree"]
    assert "old.txt" in tree["untracked"] and "a.py" not in tree["untracked"], tree


def test_read_pins_names_new_tree_changes(tmp_path: Path) -> None:
    """A relative `-o arch.tar`, a relative `tar -C arch` and a write to a tracked file outside the slice, all from
    a seat's live cwd: each is named after the pass with its kind and size. What was there at pin time, the
    manifest's own files (LIVE MOVED owns them) and the pins dir's own files — here INSIDE the repo — are not."""
    repo = _leaky_repo(tmp_path)
    pins = repo / "pins"
    assert _tool_in(repo, "pin", "--pins-dir", str(pins), "a.py").returncode == 0
    (repo / "arch.tar").write_bytes(b"x" * 2048)
    (repo / "arch").mkdir()
    (repo / "arch" / "f").write_text("extracted\n")
    (repo / "sub" / "b.py").write_text("B = 9  # a seat's edit outside the slice\n")
    (repo / "a.py").write_text("A = 9  # the slice file: LIVE MOVED, not a tree change\n")
    run, out = _run_dir(tmp_path), tmp_path / "pass.json"
    got = _tool_in(tmp_path, "read", str(run), "--out", str(out), "--pins", str(pins))
    assert got.returncode == 0, (got.returncode, got.stdout, got.stderr)
    lines = _tree_lines(got.stdout)
    assert any(ln.startswith("NEW UNTRACKED arch.tar (2048 B)") for ln in lines), lines
    assert any(ln.startswith("NEW IGNORED arch/") for ln in lines), lines
    assert any(ln.startswith("NEW MODIFIED sub/b.py") for ln in lines), lines
    assert not any("old.txt" in ln or " a.py" in ln or "pins/" in ln for ln in lines), lines
    changes = {c["path"]: c["kind"] for c in json.loads(out.read_text())["pins"]["tree_changes"]}
    assert changes == {
        "arch.tar": "NEW UNTRACKED",
        "arch/": "NEW IGNORED",
        "sub/b.py": "NEW MODIFIED",
    }, changes


def test_read_pins_flags_a_seat_archive(tmp_path: Path) -> None:
    """The reported leak exactly: `git archive -o arch.tar <sha>` from the live cwd. Its pax comment names a commit
    of this repo, which no sibling's legitimate file carries, so it reads SEAT ARCHIVE and the read exits 4."""
    repo = _leaky_repo(tmp_path)
    pins = tmp_path / "pins"
    assert _tool_in(repo, "pin", "--pins-dir", str(pins), "a.py").returncode == 0
    _vcs(repo, "archive", "-o", "arch.tar", "HEAD")
    run, out = _run_dir(tmp_path), tmp_path / "pass.json"
    got = _tool_in(tmp_path, "read", str(run), "--out", str(out), "--pins", str(pins))
    assert got.returncode == 4, (got.returncode, got.stdout)
    assert any(ln.startswith("SEAT ARCHIVE arch.tar") for ln in _tree_lines(got.stdout)), got.stdout
    assert out.is_file(), "the pass file is written before the non-zero exit"


def test_read_pins_tree_not_checked_never_fails_the_read(tmp_path: Path) -> None:
    """A pins dir written before the snapshot existed, or a root the snapshot cannot run in, reads
    `tree: NOT CHECKED` — the read still succeeds and still writes its pass file."""
    repo = _leaky_repo(tmp_path)
    pins = tmp_path / "pins"
    assert _tool_in(repo, "pin", "--pins-dir", str(pins), "a.py").returncode == 0
    man = pins / "MANIFEST.json"
    pins.chmod(0o755)
    man.chmod(0o644)
    doc = json.loads(man.read_text())
    run, out = _run_dir(tmp_path), tmp_path / "pass.json"
    old = {k: v for k, v in doc.items() if k != "tree"}
    man.write_text(json.dumps(old))
    got = _tool_in(tmp_path, "read", str(run), "--out", str(out), "--pins", str(pins))
    assert got.returncode == 0 and "tree: NOT CHECKED" in got.stdout, got.stdout
    elsewhere = tmp_path / "not-a-repo"
    elsewhere.mkdir()
    man.write_text(json.dumps({**doc, "root": str(elsewhere)}))
    got = _tool_in(tmp_path, "read", str(run), "--out", str(out), "--pins", str(pins))
    assert got.returncode == 0 and "tree: NOT CHECKED" in got.stdout, (
        got.returncode,
        got.stdout,
        got.stderr,
    )
    assert json.loads(out.read_text())["pins"]["tree_changes"] is None


def test_read_pins_sees_inside_an_untracked_dir_and_names_a_change_again(tmp_path: Path) -> None:
    """Review pass 1: A-S1 — an untracked dir present at pin time collapsed to one `dir` entry, so a tarball a seat
    later wrote INTO it was invisible; B-S2 — CHANGED AGAIN had no grader; B-S4 — a staged rename (the porcelain
    source path rides as the next NUL entry) with a space in the name had none either."""
    repo = _leaky_repo(tmp_path)
    (repo / "scratch").mkdir()
    (repo / "scratch" / "notes.txt").write_text("mine\n")
    pins = tmp_path / "pins"
    assert _tool_in(repo, "pin", "--pins-dir", str(pins), "a.py").returncode == 0
    (repo / "scratch" / "arch.tar").write_bytes(b"y" * 100)
    (repo / "old.txt").write_text("already here, then rewritten\n")
    _vcs(repo, "mv", "sub/b.py", "sub/b c.py")
    run, out = _run_dir(tmp_path), tmp_path / "pass.json"
    got = _tool_in(tmp_path, "read", str(run), "--out", str(out), "--pins", str(pins))
    assert got.returncode == 0, (got.returncode, got.stdout, got.stderr)
    changes = {c["path"]: c["kind"] for c in json.loads(out.read_text())["pins"]["tree_changes"]}
    assert changes == {
        "scratch/arch.tar": "NEW UNTRACKED",
        "old.txt": "CHANGED AGAIN",
        "sub/b c.py": "NEW MODIFIED",
    }, changes


def test_fingerprint_falls_back_to_size_and_nanosecond_mtime(tmp_path: Path) -> None:
    """Review B-S3/A-S2: above the hash cap, or for a non-regular file, the fingerprint is size plus mtime — at
    NANOSECOND precision, so a same-size rewrite inside one second still reads as changed."""
    import importlib.util
    import os

    spec = importlib.util.spec_from_file_location("rll_fp", TOOL)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)
    assert mod._fingerprint(fifo).startswith("size:"), "a fifo is never opened for hashing"
    big = tmp_path / "big.bin"
    big.write_bytes(b"a" * 64)
    mod._HASH_CAP = 8
    os.utime(big, ns=(1_000_000_000_000_000_001, 1_000_000_000_000_000_001))
    first = mod._fingerprint(big)
    big.write_bytes(b"b" * 64)
    os.utime(big, ns=(1_000_000_000_000_000_002, 1_000_000_000_000_000_002))
    assert first.startswith("size:64:") and mod._fingerprint(big) != first, (
        first,
        mod._fingerprint(big),
    )


def test_seat_archive_needs_a_full_commit_name(tmp_path: Path) -> None:
    """Review A-S3: a pax comment that is a SHORT hex abbreviation of a real commit is not a seat's `git archive`
    signature — only a full 40- (or 64-) character name is."""
    import tarfile

    repo = _leaky_repo(tmp_path)
    head = subprocess.run(
        ["g" + "it", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    pins = tmp_path / "pins"
    assert _tool_in(repo, "pin", "--pins-dir", str(pins), "a.py").returncode == 0
    with tarfile.open(
        repo / "short.tar", "w", format=tarfile.PAX_FORMAT, pax_headers={"comment": head[:7]}
    ) as t:
        t.add(repo / "a.py", arcname="a.py")
    run, out = _run_dir(tmp_path), tmp_path / "pass.json"
    got = _tool_in(tmp_path, "read", str(run), "--out", str(out), "--pins", str(pins))
    assert got.returncode == 0 and "SEAT ARCHIVE" not in got.stdout, (got.returncode, got.stdout)
    assert any(ln.startswith("NEW UNTRACKED short.tar") for ln in _tree_lines(got.stdout)), (
        got.stdout
    )


def _session_run(tmp: Path, run_file: dict | str | None) -> Path:
    """The harness layout: the run's transcript dir at <session>/subagents/workflows/<runId>, and the run file it
    writes only when the workflow ends, at <session>/workflows/<runId>.json (a str is written raw)."""
    sess = tmp / "sess"
    (sess / "subagents" / "workflows").mkdir(parents=True)
    run = _run_dir(sess / "subagents" / "workflows")
    if run_file is not None:
        (sess / "workflows").mkdir()
        body = run_file if isinstance(run_file, str) else json.dumps(run_file)
        (sess / "workflows" / f"{run.name}.json").write_text(body)
    return run


def test_read_says_running_while_the_workflow_has_no_run_file(tmp_path: Path) -> None:
    """01M4PNBVJ1 rows 1791748866, 1791217578, 1790292451: a seat still out was printed NO RESULT, so a lead
    adjudicated half a pass. With no run file yet the resultless seats are RUNNING and the read exits 5 — also
    when the run dir is named relatively, from inside it."""
    out = tmp_path / "p.json"
    run = _session_run(tmp_path, None)
    r = _tool("read", str(run), "--out", str(out))
    assert r.returncode == 5, (r.returncode, r.stdout, r.stderr)
    assert "RUNNING" in r.stdout and "NO RESULT" not in r.stdout, r.stdout
    assert "workflow: RUNNING" in r.stdout and "idle" in r.stdout, r.stdout
    assert json.loads(out.read_text())["workflow"]["status"] == "running"
    rel = _tool_in(run, "read", ".")
    assert rel.returncode == 5 and "workflow: RUNNING" in rel.stdout, rel.stdout


def test_read_prints_the_workflows_own_failures_once_it_has_ended(tmp_path: Path) -> None:
    """01M4RMKM28 row 1791826392, 01M4PNBVJ1 row 1791033713: the workflow records a failed refuter, failed seats
    and dropped slices in its return, which the lead never read; `read` now prints them."""
    result = {
        "closable": False,
        "failed_refuters": 1,
        "dropped_seats": 1,
        "dropped_slices": 1,
        "slices": [
            {
                "name": "A",
                "seats": [{"model": "sonnet", "failed": False}, {"model": "haiku", "failed": True}],
                "refuter": {"failed": True, "reason": "null result"},
                "open": ["seat failed: haiku", "refuter failed"],
            },
            # review round 1: a string `open` is one reason, never split into characters (A-S2)
            {"name": "C", "seats": [], "refuter": {}, "open": "unread: c.py"},
        ],
    }
    # a launch slice with no name is never printed as `SLICE DROPPED None` (A-H2)
    args = {"slices": [{"name": "A"}, {"name": "B"}, {"name": "C"}, {"files": ["x.py"]}]}
    run = _session_run(tmp_path, {"status": "completed", "args": args, "result": result})
    out = tmp_path / "p.json"
    r = _tool("read", str(run), "--out", str(out))
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    opened = {s["name"]: s["open"] for s in json.loads(out.read_text())["workflow"]["slices"]}
    assert opened["C"] == ["unread: c.py"], opened
    assert "SLICE DROPPED None" not in r.stdout, r.stdout
    assert "workflow: completed · NOT closable" in r.stdout and "1 dropped slice(s)" in r.stdout, (
        r.stdout
    )
    assert "REFUTER FAILED A — null result" in r.stdout, r.stdout
    assert "SEAT FAILED A:haiku" in r.stdout and "SLICE DROPPED B" in r.stdout, r.stdout
    assert "NO RESULT" in r.stdout and "RUNNING" not in r.stdout, (
        "an ended run's resultless seat is NO RESULT"
    )


def test_read_names_a_run_file_that_is_not_final(tmp_path: Path) -> None:
    """A killed run with no `result` reads as ended (rc 0, its seats NO RESULT). A torn or non-ended run file is
    a reason to read again: UNREADABLE and an unknown status exit 5 like RUNNING (A1 critique, Opus 5)."""
    r = _tool("read", str(_session_run(tmp_path / "k", {"status": "killed"})))
    assert r.returncode == 0 and "workflow: killed — no result" in r.stdout, r.stdout
    r = _tool("read", str(_session_run(tmp_path / "u", "{not json")))
    assert r.returncode == 5 and "workflow: UNREADABLE" in r.stdout, r.stdout
    r = _tool("read", str(_session_run(tmp_path / "s", {"status": "running"})))
    assert r.returncode == 5 and "running — not ended" in r.stdout, r.stdout


def test_read_outside_the_harness_layout_checks_no_workflow(tmp_path: Path) -> None:
    r = _tool("read", str(_run_dir(tmp_path)))
    assert r.returncode == 0 and "workflow: NOT CHECKED" in r.stdout, r.stdout


def test_pin_writes_the_change_diff_from_its_basis(tmp_path: Path) -> None:
    """01M4PNBVJ1 row 1791099162, 01M4RM8CYR row 1791827197: the pin writes the change's diff beside the pins,
    so no brief hand-builds it. The basis is HEAD for a working-tree pin, REF^ for --from (all files from
    /dev/null when REF is a root commit), --base when given; a new untracked file diffs from /dev/null, and a
    file without a final newline or not UTF-8 comes out as git prints it."""
    repo = _repo(tmp_path)
    root = _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "p0"), "--from", "HEAD", "a.py")
    assert root.returncode == 0, root.stderr
    assert "--- /dev/null" in (tmp_path / "p0" / "change.diff").read_text(), (
        "a root commit diffs from nothing"
    )
    (repo / "a.py").write_text("A = 2")
    (repo / "new.py").write_bytes(b"N = '\xe9'\n")
    got = _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "p1"), "a.py", "new.py", "sub/b.py")
    assert got.returncode == 0, got.stderr
    frag = json.loads(got.stdout.splitlines()[-1])
    path = Path(frag["change_diff"])
    assert path == tmp_path / "p1" / "change.diff" and frag["change_diff_md5"] == _md5(path)
    diff = path.read_bytes().decode("utf-8", "surrogateescape")
    assert "-A = 1\n+A = 2\n\\ No newline at end of file" in diff, diff
    assert "--- /dev/null" in diff and "+N = '\udce9'" in diff, diff
    assert "sub/b.py" not in diff.split("\n", 1)[1], "an unchanged pin has no hunk"
    assert "change.diff" not in (tmp_path / "p1" / "MANIFEST.md5").read_text()
    for argv in (
        ["add", "a.py"],
        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "two"],
    ):
        subprocess.run(["git", *argv], cwd=repo, check=True, env=_VCS_ENV, capture_output=True)
    ref = _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "p2"), "--from", "HEAD", "a.py")
    assert "-A = 1\n+A = 2" in (tmp_path / "p2" / "change.diff").read_text(), ref.stdout
    based = _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "p3"), "--base", "HEAD~1", "a.py")
    assert based.returncode == 0 and "UNCHANGED" not in based.stderr, based.stderr
    assert "+A = 2" in (tmp_path / "p3" / "change.diff").read_text(), "--base wins over HEAD"


def test_pin_names_an_unchanged_pin_and_reserves_change_diff(tmp_path: Path) -> None:
    """01M4PNBVJ1 row 1791481582: a pin equal to its basis is named UNCHANGED — advice, never a refusal, since
    context files are pinned on purpose. A root file named change.diff is refused, never overwritten."""
    repo = _repo(tmp_path)
    (repo / "a.py").write_text("A = 2\n")
    got = _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "p1"), "a.py", "sub/b.py")
    assert got.returncode == 0, got.stderr
    assert "UNCHANGED sub/b.py" in got.stderr and "UNCHANGED a.py" not in got.stderr, got.stderr
    assert json.loads(got.stdout.splitlines()[-1])["unchanged"] == ["sub/b.py"]
    (repo / "change.diff").write_text("x\n")
    out = _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "p2"), "change.diff")
    assert out.returncode == 2 and "reserved" in out.stderr, out.stderr
    typo = _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "p3"), "--base", "deadbeef", "a.py")
    assert typo.returncode == 2 and "not a commit" in typo.stderr, typo.stderr
    assert not (tmp_path / "p3").exists(), "a refused basis leaves no pins dir behind"
    # review round 1 (A-S3/B-S3): a --base typo ending in `^` is refused by the diff's own check, not by luck
    caret = _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "p4"), "--base", "deadbeef^", "a.py")
    assert caret.returncode == 2 and "cannot diff against deadbeef^" in caret.stderr, caret.stderr


def test_pin_in_a_repo_with_no_commit_diffs_from_nothing(tmp_path: Path) -> None:
    """Review round 1 (A-H1): a working-tree pin in a fresh repo — HEAD names no commit yet — pinned before this
    change and must still: the implied basis falls back to /dev/null, only an explicit --base is refused."""
    repo = tmp_path / "fresh"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=_VCS_ENV, capture_output=True)
    (repo / "a.py").write_text("A = 1\n")
    got = _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "p"), "a.py")
    assert got.returncode == 0, got.stderr
    assert "--- /dev/null" in (tmp_path / "p" / "change.diff").read_text()
    assert json.loads((tmp_path / "p" / "MANIFEST.json").read_text())["base_sha"] is None
    assert json.loads(got.stdout.strip().splitlines()[-1])["base_sha"] is None


def test_read_pins_flags_a_mutated_change_diff(tmp_path: Path) -> None:
    """Review round 1 (A-S1): change.diff is every seat's view of the change, so a mutated one is PIN MOVED
    (rc 3) like a mutated pin — its md5 rides in MANIFEST.json."""
    repo, pins = _repo(tmp_path), tmp_path / "pins"
    (repo / "a.py").write_text("A = 2\n")
    assert _tool_in(repo, "pin", "--pins-dir", str(pins), "a.py").returncode == 0
    run = tmp_path / "run"
    run.mkdir()
    _run_dir(run)
    clean = _tool("read", str(run / "wf_x"), "--pins", str(pins))
    assert clean.returncode == 0 and "PIN MOVED" not in clean.stdout, clean.stdout
    pins.chmod(0o755)
    (pins / "change.diff").chmod(0o644)
    with (pins / "change.diff").open("a") as fh:
        fh.write("+forged\n")
    moved = _tool("read", str(run / "wf_x"), "--pins", str(pins))
    assert moved.returncode == 3 and "PIN MOVED change.diff" in moved.stdout, moved.stdout


def test_next_refuses_a_pass_file_read_before_the_workflow_ended(tmp_path: Path) -> None:
    """A1 critique (Fable 6): `read --out` writes the pass file before it exits 5, so `next` over it would seed
    pass 2 from half a pass — refused by name. A pass file with no `workflow` key (older, or outside the
    layout) is read as before."""
    out = tmp_path / "p.json"
    assert _tool("read", str(_session_run(tmp_path, None)), "--out", str(out)).returncode == 5
    r = _tool("next", str(out), "--ids", "A-S1")
    assert r.returncode == 2 and "read while the workflow was running" in r.stderr, r.stderr
    old = tmp_path / "old.json"
    (tmp_path / "x").mkdir()
    assert _tool("read", str(_run_dir(tmp_path / "x")), "--out", str(old)).returncode == 0
    assert _tool("next", str(old), "--ids", "A-S1").returncode == 0


def test_pin_stdout_is_the_fragment_alone(tmp_path: Path) -> None:
    """kaizen 01M4V6VQ8V (/fabrik-review row 1791913338): DIRTY and UNCHANGED lines printed on stdout ahead of the
    JSON, so a caller could not hand stdout to a Workflow launch whole. Advisories go to stderr; stdout is ONE JSON
    document."""
    repo = _repo(tmp_path)
    (repo / "a.py").write_text("A = 2\n")
    got = _tool_in(
        repo, "pin", "--pins-dir", str(tmp_path / "p"), "--base", "HEAD", "a.py", "sub/b.py"
    )
    assert got.returncode == 0, got.stderr
    frag = json.loads(got.stdout)
    assert frag["pins_dir"] == str(tmp_path / "p"), frag
    assert frag["dirty"] == ["a.py"] and frag["unchanged"] == ["sub/b.py"], frag
    assert "DIRTY a.py" in got.stderr and "UNCHANGED sub/b.py" in got.stderr, got.stderr


# W-b1f67743 (/fabrik-spec-review row 1790195711, mail 01M4PVPY8J): `next` dropped an open claim the lead's --ids
# left out ("review_loop_ledger.py next dropped B-S2, which I re-added by hand"). It now CARRIES every open claim it
# can see from a run file, says so on stderr, names what it cannot check, and `--drop` is the lead's way out.


def _ev(cid: str, verdict: str) -> dict:
    return {"id": cid, "verdict": verdict, "command": "pytest -q x", "output": "1 failed"}


def _judged_run(tmp: Path, slices: list, launch: list | None = None) -> Path:
    """A run file whose `result` holds the workflow's OWN normalised verdicts, index-aligned with candidates."""
    f = tmp / "run.json"
    args = {"slices": launch or [{"name": s["name"], "files": ["a.py"]} for s in slices]}
    f.write_text(json.dumps({"runId": "wf_y", "args": args, "result": {"slices": slices}}))
    return f


def _cands(*ids: str) -> list:
    return [_union(i, n + 1, f"claim {i}") for n, i in enumerate(ids)]


def _ledger_of(stdout: str) -> dict:
    return {s["name"]: [r["id"] for r in s["ledger"]] for s in json.loads(stdout)}


def _pass_with(tmp: Path, ledger_status: list | None = None) -> Path:
    p = tmp / "pass.json"
    p.write_text(
        json.dumps(
            {
                "candidates": [{**_union("A-S1", 1, "a"), "seat": "find:A:sonnet"}],
                "verdicts": [],
                "ledger_status": ledger_status or [],
            }
        )
    )
    return p


def test_next_carries_an_open_claim_from_the_runs_own_verdicts(tmp_path: Path) -> None:
    run = _judged_run(
        tmp_path,
        [
            {
                "name": "A",
                "candidates": _cands("A-S1", "A-S2", "A-S3", "A-S4", "A-S5", "A-S6"),
                # A-S6 has no verdict at its index: a short list reads unverified — re-verified, never dropped
                "verdicts": [
                    _ev("A-S1", "confirmed"),
                    _ev("A-S2", "confirmed"),
                    _ev("A-S3", "unverified"),
                    _ev("A-S4", "refuted"),
                    _ev("A-S5", "recorded"),
                ],
                "recorded": [_union("A-REC", 9, "report only")],
            },
            {"name": "B", "candidates": _cands("B-S1"), "verdicts": [_ev("B-S1", "refuted")]},
        ],
    )
    # A-REC's seat re-reports it present, and the launch ledger still lists it: recorded stays closed
    p = _pass_with(tmp_path, [{"id": "A-REC", "status": "DEFECT_PRESENT"}])
    args = json.loads(run.read_text())
    args["args"]["slices"][0]["ledger"] = [
        {"id": "A-REC", "file": "a.py", "line": 9, "claim": "report only"}
    ]
    run.write_text(json.dumps(args))
    r = _tool("next", str(p), "--ids", "A-S1", "--args", str(run))
    assert r.returncode == 0, r.stderr
    assert _ledger_of(r.stdout) == {"A": ["A-S1", "A-S2", "A-S3", "A-S6"]}, r.stdout
    for cid in ("A-S2", "A-S3", "A-S6"):
        assert f"CARRIED {cid}" in r.stderr, r.stderr
    for cid in ("A-S1", "A-S4", "A-S5", "A-REC", "B-S1"):
        assert f"CARRIED {cid}" not in r.stderr, (cid, r.stderr)
    assert "NOT CHECKED" not in r.stderr, "a run file's verdicts were read"


def test_next_without_a_run_file_says_what_it_did_not_check(tmp_path: Path) -> None:
    p = tmp_path / "p.json"
    p.write_text(
        json.dumps(
            {
                "candidates": [
                    {**_union("A-S1", 1, "a"), "seat": "find:A:sonnet"},
                    {**_union("B-S2", 9, "b"), "seat": "find:B:sonnet"},
                    {**_union("B-S2", 12, "b2"), "seat": "find:B:haiku"},
                ],
                "verdicts": [_ev("A-S1", "confirmed"), _ev("B-S2", "confirmed")],
                "ledger_status": [],
            }
        )
    )
    r = _tool("next", str(p), "--ids", "A-S1")
    assert r.returncode == 0, r.stderr
    assert _ledger_of(r.stdout) == {"A": ["A-S1"]}, "without a run file no verdict is judged"
    # three candidate rows, one named: two left — rows, not ids (review round 2, NEW-1)
    assert "NOT CHECKED 2 candidate(s) outside --ids" in r.stderr and "--args" in r.stderr, r.stderr
    quiet = _tool("next", str(p), "--ids", "A-S1,B-S2")
    assert quiet.returncode == 2, (
        "B-S2 names two claims: the existing ambiguity refusal still answers"
    )


@pytest.mark.parametrize("status", ["DEFECT_PRESENT", "NEW", "STILL_TRUE"])
def test_next_carries_a_present_claim_from_the_launch_ledger(tmp_path: Path, status: str) -> None:
    launch = [
        {
            "name": "C",
            "files": ["c.py"],
            "ledger": [
                {"id": "C-S7", "file": "c.py", "line": 4, "claim": "leaks"},
                {"id": "C-S8", "file": "c.py", "line": 8, "claim": "noted", "recorded": True},
                {"id": "C-S9", "file": "c.py", "line": 9, "claim": "closed"},
            ],
        },
        {"name": "A", "files": ["a.py"]},
    ]
    rows = [
        {
            "id": " c-s7 ",
            "status": status,
        },  # a seat's echo: trimmed and lower-cased, still the ledger's C-S7
        {"id": "C-S8", "status": status},
        {"id": "C-S9", "status": "DEFECT_ABSENT"},
        {"id": "C-X1", "status": status},
        {"id": "A-S2", "status": status},  # a candidate carries it: the candidate's verdict decides
    ]
    launch[1]["ledger"] = [{"id": "A-S2", "file": "a.py", "line": 2, "claim": "old"}]
    run = _judged_run(
        tmp_path,
        [
            {
                "name": "A",
                "candidates": _cands("A-S1", "A-S2"),
                "verdicts": [_ev("A-S1", "confirmed"), _ev("A-S2", "refuted")],
            },
            {"name": "C"},
        ],
        launch,
    )
    r = _tool("next", str(_pass_with(tmp_path, rows)), "--ids", "A-S1", "--args", str(run))
    assert r.returncode == 0, r.stderr
    got = {s["name"]: s["ledger"] for s in json.loads(r.stdout)}
    assert got["C"] == [{"id": "C-S7", "file": "c.py", "line": 4, "claim": "leaks"}], got
    assert "CARRIED C-S7" in r.stderr, r.stderr
    assert "C-S8" not in r.stderr and "C-S9" not in r.stderr, (
        "recorded and absent claims stay closed"
    )
    assert "OPEN NOT CARRIED C-X1" in r.stderr, "an open id nothing resolves is named"
    assert "A-S2" not in r.stdout + r.stderr, (
        "a refuted candidate is never reopened by its ledger row"
    )


def test_next_drop_excludes_an_open_claim(tmp_path: Path) -> None:
    run = _judged_run(
        tmp_path,
        [
            {
                "name": "A",
                "candidates": _cands("A-S1", "A-S2", "A-S3"),
                "verdicts": [
                    _ev("A-S1", "confirmed"),
                    _ev("A-S2", "unverified"),
                    _ev("A-S3", "refuted"),
                ],
            }
        ],
    )
    p = _pass_with(tmp_path, [{"id": "Z-S1", "status": "DEFECT_PRESENT"}])
    r = _tool("next", str(p), "--ids", "A-S1", "--args", str(run), "--drop", "A-S2,A-S2,Z-S1")
    assert r.returncode == 0, r.stderr
    assert _ledger_of(r.stdout) == {"A": ["A-S1"]}, r.stdout
    assert r.stderr.count("DROPPED A-S2") == 1 and "DROPPED Z-S1" in r.stderr, r.stderr
    assert "OPEN NOT CARRIED Z-S1" not in r.stderr, "a dropped open id is not also reported open"
    for bad in ("A-S1", "A-S3", "NOPE"):  # named in --ids · refuted · never raised
        refused = _tool("next", str(p), "--ids", "A-S1", "--args", str(run), "--drop", bad)
        assert refused.returncode == 2 and bad in refused.stderr, (bad, refused.stderr)


def test_next_names_what_the_run_file_could_not_settle(tmp_path: Path) -> None:
    """Review round 2 (B-S10, A-H2, B-S9, N1): a slice the refuter never judged is said with advice that fits a run
    file already given; a union id the run file repeats is named, never carried twice; one stuck id reported by two
    seats is named once."""
    run = _judged_run(
        tmp_path,
        [
            {"name": "A", "candidates": _cands("A-S1"), "verdicts": [_ev("A-S1", "confirmed")]},
            {"name": "B", "candidates": _cands("B-S1", "B-S2")},  # no verdicts list: never judged
            {
                "name": "C",
                "candidates": _cands("C-S1", "C-S1"),
                "verdicts": [_ev("C-S1", "confirmed"), _ev("C-S1", "confirmed")],
            },
        ],
    )
    rows = [{"id": "Z-S1", "status": "DEFECT_PRESENT"}, {"id": "z-s1 ", "status": "NEW"}]
    r = _tool("next", str(_pass_with(tmp_path, rows)), "--ids", "A-S1", "--args", str(run))
    assert r.returncode == 0, r.stderr
    assert _ledger_of(r.stdout) == {"A": ["A-S1"]}, r.stdout
    assert (
        "NOT CHECKED 2 candidate(s) outside --ids — their slice carries no verdicts" in r.stderr
    ), r.stderr
    assert "pass --args" not in r.stderr, "a run file was given: that advice would be wrong"
    lines = r.stderr.splitlines()
    assert not any(ln.startswith("CARRIED C-S1") for ln in lines), r.stderr
    assert sum(ln.startswith("OPEN NOT CARRIED C-S1") for ln in lines) == 1, r.stderr
    assert sum(ln.lower().startswith("open not carried z-s1") for ln in lines) == 1, (
        "one stuck claim, echoed by two seats, is named once"
    )
    assert "re-run next with --args" not in r.stderr, (
        "--args was given: the advice names the hand route"
    )


def test_next_advice_for_an_args_file_with_no_result_never_asks_for_args(tmp_path: Path) -> None:
    """W-9f436e18 (1): a run file whose run never returned (no `result` key) is still an `--args` file, so the
    NOT CHECKED advice must not tell the lead to pass `--args <run file>` — it names the missing result instead."""
    run = tmp_path / "run.json"
    run.write_text(
        json.dumps({"runId": "wf_n", "args": {"slices": [{"name": "A", "files": ["a.py"]}]}})
    )
    p = tmp_path / "pass.json"
    p.write_text(
        json.dumps(
            {
                "candidates": [
                    {**_union("A-S1", 1, "a"), "seat": "find:A:sonnet"},
                    {**_union("A-S2", 2, "b"), "seat": "find:A:sonnet"},
                ],
                "verdicts": [],
                "ledger_status": [],
            }
        )
    )
    r = _tool("next", str(p), "--ids", "A-S1", "--args", str(run))
    assert r.returncode == 0, r.stderr
    assert "NOT CHECKED 1 candidate(s) outside --ids" in r.stderr, r.stderr
    assert "pass --args" not in r.stderr, r.stderr
    assert "no usable `result`" in r.stderr, r.stderr


def test_next_treats_fold_equal_union_ids_as_one_repeated_claim(tmp_path: Path) -> None:
    """W-9f436e18 (2): the repeat guard compared raw ids, so `alpha-S1` and `alpha-s1 ` (fold-equal under the
    workflow's `foldId`) escaped it and both were carried; a fold-equal repeat names no single claim either."""
    run = _judged_run(
        tmp_path,
        [
            {"name": "A", "candidates": _cands("A-S1"), "verdicts": [_ev("A-S1", "confirmed")]},
            {
                "name": "alpha",
                "candidates": _cands("alpha-S1", "alpha-s1 ", "ALPHA-s1"),
                "verdicts": [
                    _ev("alpha-S1", "refuted"),
                    _ev("alpha-s1 ", "confirmed"),
                    _ev("ALPHA-s1", "confirmed"),
                ],
            },
        ],
    )
    r = _tool("next", str(_pass_with(tmp_path)), "--ids", "A-S1", "--args", str(run))
    assert r.returncode == 0, r.stderr
    lines = r.stderr.splitlines()
    assert not any(ln.lower().startswith("carried alpha-s1") for ln in lines), r.stderr
    assert sum(ln.lower().startswith("open not carried alpha-s1") for ln in lines) == 1, (
        "three spellings of one repeated claim are named once"
    )
    # the ids the lead NAMES are matched folded too: a fold-equal repeat is refused, never resolved to one spelling
    named = _tool("next", str(_pass_with(tmp_path)), "--ids", "A-S1,alpha-S1", "--args", str(run))
    assert named.returncode == 2 and "more than once" in named.stderr, named.stderr


def test_next_emits_one_row_for_fold_equal_spellings_of_one_claim_in_ids(tmp_path: Path) -> None:
    """W-9f436e18 closing pass, N-1: once `--ids` resolve folded, two spellings of ONE (unrepeated) claim hit the same
    union candidate — the dedup must be folded too, or the next ledger carries the row twice."""
    run = _judged_run(
        tmp_path,
        [
            {"name": "A", "candidates": _cands("A-S1"), "verdicts": [_ev("A-S1", "confirmed")]},
            {
                "name": "alpha",
                "candidates": _cands("alpha-S1"),
                "verdicts": [_ev("alpha-S1", "confirmed")],
            },
        ],
    )
    r = _tool(
        "next",
        str(_pass_with(tmp_path)),
        "--ids",
        "A-S1,alpha-S1,ALPHA-s1 ,A-s1",
        "--args",
        str(run),
    )
    assert r.returncode == 0, r.stderr
    assert _ledger_of(r.stdout) == {"A": ["A-S1"], "alpha": ["alpha-S1"]}, r.stdout


# ---- stage (W-b976638f, kaizen mail 01M5PN3806): one command builds a seat's test tree ----


def _commit(repo: Path, msg: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=_VCS_ENV, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", msg],
        cwd=repo,
        check=True,
        env=_VCS_ENV,
        capture_output=True,
    )


def _stage(pins: Path, out: Path, **env: str) -> subprocess.CompletedProcess:
    import os

    return subprocess.run(
        [sys.executable, str(TOOL), "stage", "--pins-dir", str(pins), "--out", str(out)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={**os.environ, **env},
        cwd=str(pins.parent),  # a relative --out a buggy stage accepted would land in tmp, never the checkout
    )


def test_pin_base_records_its_copy_in_the_manifest(tmp_path: Path) -> None:
    """`base_copy` names the commit the `.base` beside this manifest holds — stage trusts a copy only then."""
    repo, pins = _repo(tmp_path), tmp_path / "pins"
    assert _tool_in(repo, "pin", "--pins-dir", str(pins), "--base", "HEAD", "a.py").returncode == 0
    doc = json.loads((pins / "MANIFEST.json").read_text())
    assert doc["base_copy"] == doc["base_sha"] and len(doc["base_copy"]) == 40, doc
    plain = tmp_path / "plain"
    assert _tool_in(repo, "pin", "--pins-dir", str(plain), "a.py").returncode == 0
    assert "base_copy" not in json.loads((plain / "MANIFEST.json").read_text())


def test_stage_copies_the_base_and_overlays_every_pin(tmp_path: Path) -> None:
    repo, pins = _repo(tmp_path), tmp_path / "pins"
    (repo / "a.py").write_text("A = 2\n")
    got = _tool_in(repo, "pin", "--pins-dir", str(pins), "--base", "HEAD", "a.py", "sub/b.py")
    assert got.returncode == 0, got.stderr
    (tmp_path / "s").mkdir()
    got = _stage(pins, tmp_path / "s" / "arch")
    assert got.returncode == 0, got.stderr
    doc = json.loads(got.stdout.splitlines()[-1])
    arch = tmp_path / "s" / "arch"
    assert doc["arch"] == str(arch) and doc["source"] == "base-copy" and doc["overlaid"] == 2, doc
    assert (arch / "a.py").read_text() == "A = 2\n" and (arch / "sub" / "b.py").read_text() == "B = 1\n"
    assert _writable(arch / "a.py") and _writable(arch / "sub" / "b.py") and _writable(arch / "sub")
    assert (tmp_path / "s" / "home").is_dir() and (tmp_path / "s" / "tmp").is_dir()
    assert f'os.chdir("{arch}")' in doc["pytest"], doc["pytest"]


def test_stage_archives_base_sha_without_a_base_copy(tmp_path: Path) -> None:
    """No base copy: the base_sha archive, an unsafe member SKIPPED and named, the tar never under TMPDIR."""
    repo, pins = _repo(tmp_path), tmp_path / "pins"
    (repo / "vault").symlink_to("/etc/hostname")
    _commit(repo, "link")
    (repo / "sub" / "b.py").write_text("B = 2\n")
    assert _tool_in(repo, "pin", "--pins-dir", str(pins), "sub/b.py").returncode == 0
    (tmp_path / "s").mkdir()
    got = _stage(pins, tmp_path / "s" / "arch")
    assert got.returncode == 0, got.stderr
    doc = json.loads(got.stdout.splitlines()[-1])
    arch = tmp_path / "s" / "arch"
    assert doc["source"] == "archive" and doc["skipped"] == ["vault"], doc
    assert (arch / "a.py").read_text() == "A = 1\n" and (arch / "sub" / "b.py").read_text() == "B = 2\n"
    assert not (arch / "vault").exists() and not (arch / "vault").is_symlink()
    assert list((tmp_path / "s" / "tmp").iterdir()) == [], "the archive tar was left behind"


def test_stage_writes_its_archive_tar_under_the_seats_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fable critique 4: a seat may create nothing in /tmp outside its scratch, so the tar goes under SCRATCH/tmp.
    Asserted on the call, in-process: a temp dir cleans itself up, and tempfile falls back to /tmp silently when
    TMPDIR is unwritable, so no subprocess check can see where it went."""
    import importlib.util
    import tempfile

    spec = importlib.util.spec_from_file_location("rll_stage_probe", TOOL)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    seen: list[object] = []
    real = tempfile.TemporaryDirectory

    def spy(*a: object, **kw: object) -> tempfile.TemporaryDirectory:
        seen.append(kw.get("dir"))
        return real(*a, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(mod.tempfile, "TemporaryDirectory", spy)
    repo, pins = _repo(tmp_path), tmp_path / "pins"
    assert _tool_in(repo, "pin", "--pins-dir", str(pins), "a.py").returncode == 0
    (tmp_path / "s").mkdir()
    doc = mod.stage(pins, tmp_path / "s" / "arch")
    assert doc["source"] == "archive" and seen == [tmp_path / "s" / "tmp"], seen


def test_stage_ignores_an_unrecorded_base_copy(tmp_path: Path) -> None:
    """Both critiques replayed it: `pin --replace` without `--base` left the old `.base` beside a manifest that
    cannot say whose copy it is. The re-pin removes it now, and stage never copies a `.base` the manifest does not
    record (a legacy pin, or one a hand put there) — it archives base_sha instead."""
    repo, pins = _repo(tmp_path), tmp_path / "pins"
    assert _tool_in(repo, "pin", "--pins-dir", str(pins), "--base", "HEAD", "a.py").returncode == 0
    (repo / "a.py").write_text("A = 3\n")
    _commit(repo, "c2")
    assert _tool_in(repo, "pin", "--pins-dir", str(pins), "--replace", "a.py").returncode == 0
    assert not Path(f"{pins}.base").exists(), "a re-pin without --base left the old base copy"
    other = tmp_path / "other"
    assert _tool_in(repo, "pin", "--pins-dir", str(other), "a.py").returncode == 0
    stale = Path(f"{other}.base")
    (stale / "sub").mkdir(parents=True)
    (stale / "sub" / "b.py").write_text("STALE\n")
    (tmp_path / "s").mkdir()
    got = _stage(other, tmp_path / "s" / "arch")
    assert got.returncode == 0, got.stderr
    assert json.loads(got.stdout.splitlines()[-1])["source"] == "archive"
    assert (tmp_path / "s" / "arch" / "sub" / "b.py").read_text() == "B = 1\n"


def test_stage_writes_through_an_in_tree_parent_link(tmp_path: Path) -> None:
    """A pinned path under a tracked directory link: the recipe's makedirs+copyfile writes through it and keeps the
    link's other files, so stage does too (both critiques executed the recipe on this shape)."""
    repo = _repo(tmp_path)
    (repo / "sub" / "c.py").write_text("C = 1\n")
    (repo / "lib").symlink_to("sub")
    _commit(repo, "dirlink")
    (repo / "sub" / "b.py").write_text("B = 5\n")
    pins = tmp_path / "pins"
    assert _tool_in(repo, "pin", "--pins-dir", str(pins), "--base", "HEAD", "lib/b.py").returncode == 0
    (tmp_path / "s").mkdir()
    got = _stage(pins, tmp_path / "s" / "arch")
    assert got.returncode == 0, got.stderr
    arch = tmp_path / "s" / "arch"
    assert (arch / "lib").is_symlink() and (arch / "sub" / "b.py").read_text() == "B = 5\n"
    assert (arch / "sub" / "c.py").read_text() == "C = 1\n", "a sibling behind the link was dropped"


_BAD_OUTS = ["relative", "exists", "basename", "quote", "space", "no-parent", "inside-pins", "inside-repo"]


@pytest.mark.parametrize("case", _BAD_OUTS)
def test_stage_refuses_a_bad_out_and_leaves_no_tree(tmp_path: Path, case: str) -> None:
    repo, pins = _repo(tmp_path), tmp_path / "pins"
    assert _tool_in(repo, "pin", "--pins-dir", str(pins), "--base", "HEAD", "a.py").returncode == 0
    (tmp_path / "s" / "taken").mkdir(parents=True)
    out = {
        "relative": Path("s/arch"),
        "exists": tmp_path / "s" / "taken",
        "basename": tmp_path / "s" / "tree",
        "quote": tmp_path / "s" / "it's" / "arch",
        "space": tmp_path / "s" / "a b" / "arch",
        "no-parent": tmp_path / "nowhere" / "arch",
        "inside-pins": pins / "arch",
        "inside-repo": repo / "arch",
    }[case]
    if case in ("quote", "space"):
        out.parent.mkdir(parents=True)
    existed = out.exists()
    got = _stage(pins, out)
    assert got.returncode == 2 and "review_loop_ledger: " in got.stderr, (case, got.returncode, got.stderr)
    assert out.exists() == existed, case
    assert not (repo / "home").exists() and not (repo / "tmp").exists(), case


def _unlock(p: Path) -> None:
    import os

    for d, _, names in os.walk(p):
        Path(d).chmod(0o755)
        for n in names:
            (Path(d) / n).chmod(0o644)


_BAD_PINS = ["no-manifest", "moved-pin", "md5-list-differs", "no-files", "unsafe-path", "no-base"]


@pytest.mark.parametrize("case", _BAD_PINS)
def test_stage_refuses_a_bad_pins_dir_and_leaves_no_tree(tmp_path: Path, case: str) -> None:
    repo, pins = _repo(tmp_path), tmp_path / "pins"
    assert _tool_in(repo, "pin", "--pins-dir", str(pins), "a.py").returncode == 0
    _unlock(pins)
    mf = pins / "MANIFEST.json"
    doc = json.loads(mf.read_text())
    if case == "no-manifest":
        mf.unlink()
    elif case == "moved-pin":
        (pins / "a.py").write_text("A = 99\n")
    elif case == "md5-list-differs":
        (pins / "MANIFEST.md5").write_text("")
    elif case == "no-files":
        mf.write_text(json.dumps({**doc, "files": {}}))
    elif case == "unsafe-path":
        mf.write_text(json.dumps({**doc, "files": {"../a.py": doc["files"]["a.py"]}}))
    else:
        mf.write_text(json.dumps({**doc, "base_sha": None}))
    (tmp_path / "s").mkdir()
    got = _stage(pins, tmp_path / "s" / "arch")
    assert got.returncode == 2 and "review_loop_ledger: " in got.stderr, (case, got.stderr)
    assert not (tmp_path / "s" / "arch").exists(), case
