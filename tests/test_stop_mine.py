"""stop_mine.py — the promoted research miner, sharing the Stop hook's own DEFERRAL vocabulary.

Ticket: docs/development/plans/2026-09-23-plan-1-stop-and-compaction/T05-stop-mine-and-docs.md.
Interface (T03 -> T05, spine `## Interfaces`): `.claude/hooks/final_gate_stop.py`'s `_DEFER_RE`
and `deferral_shape(text: str) -> str | None` are the ONE vocabulary the hook's DEFERRAL check
and this miner both count with — the COBRA counter-measure at hook `:1508-1512`: a reworded
deferral must show up as a falling fire rate, never a silent miss, which only holds if the miner
never re-implements the vocabulary. The seam test below proves that by IDENTITY.

Parity with the hook is the contract everywhere else too (round-1 /fabrik-review, A-S1..A-O10):
the hook's own `_is_operator_row`, `_operator_text` and the transcript half of `_is_headless` are
the truth this miner replays, never approximates.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "sysadmin" / "stop_mine.py"


def _load_stop_mine() -> ModuleType:
    spec = importlib.util.spec_from_file_location("stop_mine_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_miner_counts_with_the_hooks_vocabulary() -> None:
    """The T03 -> T05 seam: the miner's `_DEFER_RE` and `deferral_shape` ARE the hook's own
    objects — attribute references onto the loaded hook module, never a re-implementation that
    could drift the day the hook's vocabulary changes."""
    sm = _load_stop_mine()
    hook = sm._hook()
    assert sm._DEFER_RE is hook._DEFER_RE
    assert sm.deferral_shape is hook.deferral_shape


def _write(path: Path, *entries: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def _asst(text: str, ts: str) -> dict:
    return {
        "type": "assistant",
        "timestamp": ts,
        "message": {"content": [{"type": "text", "text": text}]},
    }


def _user(text: str = "ok", ts: str = "2026-08-10T00:00:00.000Z", **extra: object) -> dict:
    return {
        "type": "user",
        "timestamp": ts,
        "message": {"content": [{"type": "text", "text": text}]},
        **extra,
    }


def test_the_backtest_counts_per_shape_and_per_repo(tmp_path: Path) -> None:
    """Two repos, one turn end per shape D1-D4, a benign true-negative turn end and an inline
    subagent sidechain — spec 2026-09-23 § Validation V1's first bullet ("report the fire rate,
    per shape and per repo")."""
    sm = _load_stop_mine()
    root = tmp_path / "projects"

    # repo-a: D1, then D2, then a benign NEXT: none turn end that must not fire.
    _write(
        root / "repo-a" / "sess-a.jsonl",
        _asst(
            "Work is done for now.\n\nNEXT: operator decision — approve the migration",
            "2026-08-12T00:00:00.000Z",
        ),
        _user("thanks", "2026-08-12T00:01:00.000Z"),
        _asst(
            "Two paths remain.\n\n(a) ship now (b) wait for review\nWhich do you prefer?",
            "2026-08-12T00:02:00.000Z",
        ),
        _user("ship it", "2026-08-12T00:03:00.000Z"),
        _asst("DONE: shipped the widget.\n\nNEXT: none — terminal", "2026-08-12T00:04:00.000Z"),
        _user("great", "2026-08-12T00:05:00.000Z"),
    )
    # repo-b: D3, then D4 (dangling — no reply follows, the session's last turn end).
    _write(
        root / "repo-b" / "sess-b.jsonl",
        _asst("Should I proceed with the migration?", "2026-08-13T00:00:00.000Z"),
        _user("go ahead", "2026-08-13T00:01:00.000Z"),
        _asst(
            "The remaining migration needs a fresh session to finish it properly.",
            "2026-08-13T00:02:00.000Z",
        ),
    )
    # an inline subagent sidechain in repo-b: its D1 must not be counted either.
    _write(
        root / "repo-b" / "sess-b-side.jsonl",
        {
            **_asst("NEXT: operator decision — a subagent's own excuse", "2026-08-13T00:03:00.000Z"),
            "isSidechain": True,
        },
        _user("noted", "2026-08-13T00:04:00.000Z"),
    )

    stats = sm.mine(root, since="2026-08-09", until="2026-09-23")

    assert stats["files"] == 3
    assert stats["skipped_files"] == 0
    assert stats["headless_turn_ends"] == 0
    assert stats["turn_ends"] == 5  # D1, D2, benign (repo-a) + D3, D4 (repo-b)
    assert stats["fires"] == 4
    assert stats["by_shape"] == {"D1": 1, "D2": 1, "D3": 1, "D4": 1}
    assert stats["by_repo"]["repo-a"] == {
        "turn_ends": 3,
        "fires": 2,
        "by_shape": {"D1": 1, "D2": 1},
    }
    assert stats["by_repo"]["repo-b"] == {
        "turn_ends": 2,
        "fires": 2,
        "by_shape": {"D3": 1, "D4": 1},
    }


def test_headless_is_per_turn_end_not_per_session(tmp_path: Path) -> None:
    """A-S1/A-O1/A-O7: headless is decided PER TURN END, like the hook's own `_is_headless` — the
    LAST real operator row before a turn end's opening prompt carries the entrypoint. A session
    that starts `sdk-cli` and continues interactively excludes only its headless turn end; the
    interactive continuation counts."""
    sm = _load_stop_mine()
    root = tmp_path / "projects"
    _write(
        root / "repo-a" / "sess.jsonl",
        _user("start the task", "2026-08-12T00:00:00.000Z", entrypoint="sdk-cli"),
        _asst("NEXT: operator decision — should never be counted", "2026-08-12T00:01:00.000Z"),
        _user("continuing interactively now", "2026-08-12T00:02:00.000Z"),  # no entrypoint
        _asst(
            "NEXT: operator decision — the interactive continuation counts",
            "2026-08-12T00:03:00.000Z",
        ),
        _user("thanks", "2026-08-12T00:04:00.000Z"),
    )
    stats = sm.mine(root, since="2026-08-09", until="2026-09-23")
    assert stats["headless_turn_ends"] == 1
    assert stats["turn_ends"] == 1
    assert stats["fires"] == 1
    assert stats["by_shape"] == {"D1": 1}


@pytest.mark.parametrize(
    "noise_row",
    [
        pytest.param({"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}}, id="tool_result"),
        pytest.param({**_user("ignored"), "isMeta": True}, id="isMeta"),
        pytest.param({**_user("ignored"), "isCompactSummary": True}, id="isCompactSummary"),
        pytest.param(_user("<system-reminder>context only</system-reminder>"), id="system-reminder-only"),
        pytest.param(_user("Stop hook feedback: fix the lint"), id="harness-prefix"),
    ],
)
def test_a_harness_or_system_row_never_closes_a_turn(tmp_path: Path, noise_row: dict) -> None:
    """A-O6/A-O10: a turn end closes only at a row that is real OPERATOR TEXT by the hook's own
    `_operator_text` — a tool result, an `isMeta` row, a compaction summary, and a harness row
    that is nothing BUT a system-reminder or a `Stop hook feedback:` prefix must all be skipped.
    Discriminating structure: a SECOND assistant message follows the noise row before the real
    reply — if the noise row wrongly closed the turn, the first (benign) message would ALSO be
    counted as its own turn end, so `turn_ends` would read 2, not 1."""
    sm = _load_stop_mine()
    root = tmp_path / "projects"
    row = dict(noise_row)
    row.setdefault("timestamp", "2026-08-12T00:00:30.000Z")
    _write(
        root / "repo-a" / "sess.jsonl",
        _asst("The plan and the code both agree, no decision left.", "2026-08-12T00:00:00.000Z"),
        row,
        _asst("NEXT: operator decision — approve the migration", "2026-08-12T00:01:00.000Z"),
        _user("ok, approved", "2026-08-12T00:02:00.000Z"),
    )
    stats = sm.mine(root, since="2026-08-09", until="2026-09-23")
    assert stats["turn_ends"] == 1
    assert stats["fires"] == 1
    assert stats["by_shape"] == {"D1": 1}


def test_assistant_string_content_is_read_as_text(tmp_path: Path) -> None:
    """A-S4: a bare STRING `message.content` on an assistant row is read as text, the same way
    the hook's own `_operator_text` treats a string content on a user row."""
    sm = _load_stop_mine()
    root = tmp_path / "projects"
    _write(
        root / "repo-a" / "sess.jsonl",
        {
            "type": "assistant",
            "timestamp": "2026-08-12T00:00:00.000Z",
            "message": {"content": "NEXT: operator decision — string content still counts"},
        },
        _user("ok", "2026-08-12T00:01:00.000Z"),
    )
    stats = sm.mine(root, since="2026-08-09", until="2026-09-23")
    assert stats["turn_ends"] == 1
    assert stats["fires"] == 1
    assert stats["by_shape"] == {"D1": 1}


def test_fail_open_per_line_and_per_file(tmp_path: Path) -> None:
    """A-S2/A-O5/A-O8: a malformed line, a non-dict top-level row, a non-UTF-8 byte and a
    directory literally named `x.jsonl` are all skipped and counted; the run completes and the
    OTHER, good file's turn end is still counted."""
    sm = _load_stop_mine()
    root = tmp_path / "projects"
    good = root / "repo-a" / "sess-good.jsonl"
    good.parent.mkdir(parents=True, exist_ok=True)
    good.write_text(
        "\n".join(
            [
                "not json at all {{{",  # malformed line
                json.dumps([1, 2, 3]),  # a non-dict top-level row
                json.dumps(_asst("NEXT: operator decision — the good turn end", "2026-08-12T00:00:00.000Z")),
                json.dumps(_user("ok", "2026-08-12T00:01:00.000Z")),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    with good.open("ab") as fh:
        fh.write(b'{"type": "assistant", "timestamp": "2026-08-12T00:02:00.000Z", "message": {"content": [{"type": "text", "text": "\xff\xfe not valid utf-8"}]}}\n')
    # a directory literally named `x.jsonl` under the population glob
    (root / "repo-a" / "x.jsonl").mkdir(parents=True)

    stats = sm.mine(root, since="2026-08-09", until="2026-09-23")
    assert stats["files"] == 1
    assert stats["skipped_files"] == 1  # the directory
    assert stats["turn_ends"] == 1
    assert stats["fires"] == 1


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores the mode bits this test relies on")
def test_an_unreadable_file_is_skipped_and_reported(tmp_path: Path) -> None:
    """A-S2/A-O8: a chmod-000 file never aborts the run — it is counted as skipped, and a
    sibling, readable file is still mined."""
    sm = _load_stop_mine()
    root = tmp_path / "projects"
    bad = root / "repo-a" / "sess-bad.jsonl"
    _write(bad, _asst("NEXT: operator decision — unreachable", "2026-08-12T00:00:00.000Z"))
    good = root / "repo-a" / "sess-good.jsonl"
    _write(
        good,
        _asst("NEXT: operator decision — reachable", "2026-08-12T00:00:00.000Z"),
        _user("ok", "2026-08-12T00:01:00.000Z"),
    )
    bad.chmod(0)
    try:
        stats = sm.mine(root, since="2026-08-09", until="2026-09-23")
    finally:
        bad.chmod(0o644)
    assert stats["files"] == 1
    assert stats["skipped_files"] == 1
    assert stats["turn_ends"] == 1


def test_a_turn_end_outside_the_window_is_excluded_inclusive_at_both_ends(tmp_path: Path) -> None:
    """A-O4/A-S3/A-O37: `--since`/`--until` bound the population on BOTH sides, inclusive at both
    ends — a turn end exactly on the since day and exactly on the until day both count, one
    before `since` and one after `until` do not."""
    sm = _load_stop_mine()
    root = tmp_path / "projects"
    _write(
        root / "repo-a" / "sess.jsonl",
        _asst("NEXT: operator decision — too early", "2026-08-08T23:59:59.000Z"),
        _user("ok", "2026-08-09T00:00:01.000Z"),
        _asst("NEXT: operator decision — on the since day", "2026-08-09T00:00:00.000Z"),
        _user("ok", "2026-08-09T00:01:00.000Z"),
        _asst("NEXT: operator decision — on the until day", "2026-09-23T23:59:59.000Z"),
        _user("ok", "2026-09-24T00:00:00.000Z"),
        _asst("NEXT: operator decision — too late", "2026-09-24T00:00:01.000Z"),
        _user("ok", "2026-09-24T00:00:02.000Z"),
    )
    stats = sm.mine(root, since="2026-08-09", until="2026-09-23")
    assert stats["turn_ends"] == 2
    assert stats["fires"] == 2
    assert stats["by_shape"] == {"D1": 2}


def test_a_non_utc_offset_timestamp_compares_on_its_utc_date(tmp_path: Path) -> None:
    """A-O2/A-O3: a naive `ts[:10]` slice reads the LOCAL calendar date embedded in the string,
    which can differ from the UTC date a `--since`/`--until` day boundary must compare against.
    `2026-08-09T01:30:00+03:00` is `2026-08-08T22:30:00Z` in UTC — one calendar day EARLIER — so
    `--since 2026-08-09` must exclude it, while a naive slice would have wrongly kept it."""
    sm = _load_stop_mine()
    root = tmp_path / "projects"
    _write(
        root / "repo-a" / "sess.jsonl",
        _asst(
            "NEXT: operator decision — reads as 08-09 locally but 08-08 in UTC",
            "2026-08-09T01:30:00+03:00",
        ),
        _user("ok", "2026-08-09T01:31:00+03:00"),
    )
    stats = sm.mine(root, since="2026-08-09", until="2026-09-23")
    assert stats["turn_ends"] == 0
    assert stats["fires"] == 0


def test_cli_refuses_a_malformed_date(tmp_path: Path) -> None:
    """A-O2: `--since`/`--until` are validated as real `YYYY-MM-DD` calendar dates at the
    argparse layer — a malformed or out-of-range one is refused (argparse exits 2), never
    silently misread as a valid, wrong date."""
    sm = _load_stop_mine()
    root = tmp_path / "projects"
    root.mkdir(parents=True)
    for bad in ("2026-13-40", "not-a-date", "2026/09/23"):
        with pytest.raises(SystemExit) as exc:
            sm.main(["--root", str(root), "--since", bad])
        assert exc.value.code == 2, bad


def test_cli_refuses_since_after_until(tmp_path: Path) -> None:
    """A-O3: a well-formed `--since` after a well-formed `--until` is refused at exit code 2
    rather than silently mining an inverted (always-empty) window."""
    sm = _load_stop_mine()
    root = tmp_path / "projects"
    root.mkdir(parents=True)
    assert sm.main(["--root", str(root), "--since", "2026-09-23", "--until", "2026-08-09"]) == 2


def test_a_fifo_named_jsonl_is_skipped_never_opened(tmp_path: Path) -> None:
    """A-S2/A-O8: the `Path.is_file()` guard runs BEFORE `open()` — a FIFO named `x.jsonl` is a
    non-regular path that a bare `open("rb")` would BLOCK on forever (no writer ever connects).
    Run as a real subprocess under a hard `timeout`: if the guard is ever lost the process hangs
    and the timeout itself fails this test, which a same-process call could not prove."""
    root = tmp_path / "projects"
    (root / "repo-a").mkdir(parents=True)
    os.mkfifo(root / "repo-a" / "x.jsonl")
    good = root / "repo-a" / "sess-good.jsonl"
    _write(
        good,
        _asst("NEXT: operator decision — reachable", "2026-08-12T00:00:00.000Z"),
        _user("ok", "2026-08-12T00:01:00.000Z"),
    )
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--since", "2026-08-09", "--until", "2026-09-23"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0, proc.stderr
    summary = json.loads(proc.stdout.strip().splitlines()[0])
    assert summary["files"] == 1
    assert summary["skipped_files"] == 1
    assert summary["turn_ends"] == 1


def test_a_tool_result_row_with_an_entrypoint_never_taints_headless(tmp_path: Path) -> None:
    """A-O1: headless tracking must read ONLY a real operator row's entrypoint
    (`hook._is_operator_row`) — a `tool_result`-shaped user row that happens to ALSO carry
    `entrypoint: sdk-cli` is not a real operator row and must not flip the turn's headless state,
    even though it sits between the opening interactive prompt and the assistant's response."""
    sm = _load_stop_mine()
    root = tmp_path / "projects"
    _write(
        root / "repo-a" / "sess.jsonl",
        _user("start the task", "2026-08-12T00:00:00.000Z"),  # interactive, opens the turn
        {
            "type": "user",
            "timestamp": "2026-08-12T00:00:30.000Z",
            "message": {"content": [{"type": "tool_result", "content": "ok"}]},
            "entrypoint": "sdk-cli",
        },
        _asst("NEXT: operator decision — must still count", "2026-08-12T00:01:00.000Z"),
        _user("ok, approved", "2026-08-12T00:02:00.000Z"),
    )
    stats = sm.mine(root, since="2026-08-09", until="2026-09-23")
    assert stats["headless_turn_ends"] == 0
    assert stats["turn_ends"] == 1
    assert stats["fires"] == 1
    assert stats["by_shape"] == {"D1": 1}


def test_a_deeply_nested_malformed_line_never_aborts_the_file(tmp_path: Path) -> None:
    """A-S2/A-O5: `json.loads` raises `RecursionError` (a `RuntimeError`, NOT a `ValueError`) on a
    line nested past the interpreter's recursion limit — proof that the per-line guard must stay
    `except Exception`, since a narrower `except ValueError` would let this line's exception abort
    the whole file's mining instead of skipping just this one row."""
    sm = _load_stop_mine()
    root = tmp_path / "projects"
    # Carries the `"type"` substring the pre-filter requires, deep enough to blow the recursion
    # limit (1000 by default) well before the string is exhausted.
    deeply_nested = ("[" * 10_000) + '"type"' + ("]" * 10_000)
    sess = root / "repo-a" / "sess.jsonl"
    sess.parent.mkdir(parents=True, exist_ok=True)
    sess.write_text(
        deeply_nested
        + "\n"
        + json.dumps(_asst("NEXT: operator decision — survives the crash line", "2026-08-12T00:00:00.000Z"))
        + "\n"
        + json.dumps(_user("ok", "2026-08-12T00:01:00.000Z"))
        + "\n",
        encoding="utf-8",
    )
    stats = sm.mine(root, since="2026-08-09", until="2026-09-23")
    assert stats["turn_ends"] == 1
    assert stats["fires"] == 1


_ACCEPTED_BLOCK = (
    "The export job is staged.\n\n"
    "DECISION NEEDED (ground: gate)\n"
    "- Question: Push the export to the public bucket now?\n"
    "- Why it is yours: gate — publish, the bucket is world-readable.\n"
    "- Options: A — push now · B — hold for the checksum pass\n"
    "- Recommendation: A — the checksums already match.\n\n"
    "NEXT: operator decision — see DECISION NEEDED above"
)
_REFUSED_BLOCK = _ACCEPTED_BLOCK.replace("gate — publish, the bucket", "gate — the bucket")


def test_an_accepted_decision_block_is_not_a_fire(tmp_path: Path) -> None:
    """C-S1 (whole-plan review, T06): the hook exempts a turn end whose DECISION block passes
    `parse_decision_block`; the miner classified with `deferral_shape` alone, so every legitimate
    gate stop counted as a deferral. An accepted block is counted apart, by ground; a refused one
    still fires with the shape `deferral_shape` names."""
    sm = _load_stop_mine()
    root = tmp_path / "projects"
    _write(
        root / "repo-a" / "sess.jsonl",
        _user("stage the export", "2026-08-12T00:00:00.000Z"),
        _asst(_ACCEPTED_BLOCK, "2026-08-12T00:01:00.000Z"),
        _user("yes, push it", "2026-08-12T00:02:00.000Z"),
        _asst(_REFUSED_BLOCK, "2026-08-12T00:03:00.000Z"),
        _user("hold on", "2026-08-12T00:04:00.000Z"),
    )
    hook = sm._hook()
    assert hook.deferral_shape(_ACCEPTED_BLOCK) == "D1", "the fixture must carry a real deferral"
    assert not hook.parse_decision_block(_REFUSED_BLOCK, run_live=False, transcript_path="")[0]
    stats = sm.mine(root, since="2026-08-09", until="2026-09-23")
    assert stats["turn_ends"] == 2
    assert stats["fires"] == 1
    assert stats["by_shape"] == {"D1": 1}
    assert stats["decision_blocks_accepted"] == {"gate": 1}
    assert "decision blocks accepted (not fires): gate 1" in sm._format_report(stats)
