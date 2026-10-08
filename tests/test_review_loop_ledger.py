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


def test_pin_from_a_ref_and_dirty_marker(tmp_path: Path) -> None:
    """A committed range is pinned from the commit (`--from`), never from a working tree that may carry WIP;
    the working-tree default names every file whose bytes are not HEAD's."""
    repo = _repo(tmp_path)
    (repo / "a.py").write_text("A = 2  # working-tree edit\n")
    got = _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "p1"), "--from", "HEAD", "a.py")
    assert got.returncode == 0, got.stderr
    assert (tmp_path / "p1" / "a.py").read_text() == "A = 1\n"
    assert "DIRTY" not in got.stdout
    wt = _tool_in(repo, "pin", "--pins-dir", str(tmp_path / "p2"), "a.py", "sub/b.py")
    assert wt.returncode == 0, wt.stderr
    assert "DIRTY a.py" in wt.stdout and "DIRTY sub/b.py" not in wt.stdout, wt.stdout
    assert json.loads((tmp_path / "p2" / "MANIFEST.json").read_text())["source"] == "working-tree"
    assert json.loads((tmp_path / "p1" / "MANIFEST.json").read_text())["source"] != "working-tree"


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
    assert frag["base_skipped"] == ["vault"] and "SKIPPED vault" in got.stdout, (frag, got.stdout)
    assert (Path(frag["base_pin_dir"]) / "a.py").is_file()
    assert not (Path(frag["base_pin_dir"]) / "vault").exists()


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
