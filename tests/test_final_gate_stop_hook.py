"""Tests for the Claude Code SessionStart/Stop hook (.claude/hooks/final_gate_stop.py).

Highest-risk paths:
- ``decide()`` loop-guard (block red, never trap, skip when clean).
- baseline diffing: the Stop hook must block ONLY on failures the session introduced,
  never on inherited project debt (the real bug this design fixes).
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "final_gate_stop.py"
_spec = importlib.util.spec_from_file_location("final_gate_stop", _HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

# --- pure decide() loop-guard -------------------------------------------------


def test_clean_tree_allows() -> None:
    assert hook.decide(git_dirty=False, has_new_failures=True, gate_attempts=5) == ("allow", 0, 0)


def test_no_new_failures_allows() -> None:
    assert hook.decide(git_dirty=True, has_new_failures=False, gate_attempts=2) == ("allow", 0, 0)


def test_new_failures_block_and_increment() -> None:
    assert hook.decide(git_dirty=True, has_new_failures=True, gate_attempts=0) == ("block", 1, 0)
    assert hook.decide(git_dirty=True, has_new_failures=True, gate_attempts=1) == ("block", 2, 0)


def test_new_failures_block_up_to_cap() -> None:
    assert hook.decide(git_dirty=True, has_new_failures=True, gate_attempts=2) == ("block", 3, 0)


def test_over_cap_allows_with_warning() -> None:
    assert hook.decide(git_dirty=True, has_new_failures=True, gate_attempts=3) == ("allow_warn", 0, 0)


# --- integration: baseline diffing (the real bug) -----------------------------

_FAKE_GATE = """#!/usr/bin/env python3
import json, os, sys
fails = [f for f in os.environ.get("FAKE_FAILS", "").split(",") if f]
if not fails:
    print(json.dumps({"status": "success", "failures": []})); sys.exit(0)
print(json.dumps({"status": "failure", "failures": [{"check": c} for c in fails]}))
sys.exit(1)
"""


@pytest.fixture
def fake_project(tmp_path: Path) -> Path:
    p = tmp_path / "proj"
    (p / "scripts").mkdir(parents=True)
    (p / "scripts" / "final_gate.py").write_text(_FAKE_GATE)
    subprocess.run(["git", "init", "-q"], cwd=p, check=True, timeout=15)
    (p / "work.txt").write_text("uncommitted")  # dirty worktree
    return p


def _run_stop(project: Path, sid: str, fake_fails: str, *, baseline: list[str] | None) -> str:
    """Run the Stop hook; return stdout (block JSON or empty=allow)."""
    bl = Path(hook.tempfile.gettempdir()) / f"fabrik-gate-baseline-{sid}.json"
    ctr = Path(hook.tempfile.gettempdir()) / f"fabrik-gate-stop-{sid}.attempts"
    ctr.unlink(missing_ok=True)
    if baseline is None:
        bl.unlink(missing_ok=True)
    else:
        bl.write_text(json.dumps(baseline))
    env = {**os.environ, "FAKE_FAILS": fake_fails}
    proc = subprocess.run(
        [sys.executable, str(_HOOK)],
        input=json.dumps({"session_id": sid, "cwd": str(project), "hook_event_name": "Stop"}),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    bl.unlink(missing_ok=True)
    ctr.unlink(missing_ok=True)
    return proc.stdout.strip()


def test_inherited_failure_does_not_block(fake_project: Path) -> None:
    # Baseline already has check A; gate still fails only on A → no NEW failure → allow.
    out = _run_stop(fake_project, "s_inherit", "A", baseline=["A"])
    assert out == "", f"should allow (inherited debt), got: {out}"


def test_session_introduced_failure_blocks(fake_project: Path) -> None:
    # Baseline has A; gate now fails A AND B → B is new → block, naming only B.
    out = _run_stop(fake_project, "s_new", "A,B", baseline=["A"])
    assert out, "should block on the new failure"
    payload = json.loads(out)
    assert payload["decision"] == "block"
    assert "B" in payload["reason"] and "A" not in payload["reason"].split("New failing checks:")[1]


def test_missing_baseline_fails_open(fake_project: Path) -> None:
    # No baseline snapshot (SessionStart didn't run) → can't attribute → allow.
    out = _run_stop(fake_project, "s_nobaseline", "A,B", baseline=None)
    assert out == "", f"should fail-open without a baseline, got: {out}"


def test_green_gate_allows(fake_project: Path) -> None:
    out = _run_stop(fake_project, "s_green", "", baseline=["A"])
    assert out == "", f"green gate should allow, got: {out}"


def test_baseline_mode_writes_snapshot(fake_project: Path) -> None:
    sid = "s_baseline_mode"
    bl = Path(hook.tempfile.gettempdir()) / f"fabrik-gate-baseline-{sid}.json"
    bl.unlink(missing_ok=True)
    env = {**os.environ, "FAKE_FAILS": "A,C"}
    subprocess.run(
        [sys.executable, str(_HOOK), "--baseline"],
        input=json.dumps({"session_id": sid, "cwd": str(fake_project)}),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert bl.exists(), "baseline mode must write a snapshot"
    assert set(json.loads(bl.read_text())) == {"A", "C"}
    bl.unlink(missing_ok=True)


# --- commit-your-own-work enforcement (CLAUDE.md § EXIT flip, 2026-08-07) --------


def test_own_uncommitted_blocks_with_commit_action() -> None:
    assert hook.decide(git_dirty=True, has_new_failures=False, gate_attempts=0, own_uncommitted=True) == (
        "block_commit",
        0,
        1,
    )


def test_gate_failures_outrank_commit_block() -> None:
    # Fix first, commit second — red gate takes the block slot.
    action, _, _ = hook.decide(git_dirty=True, has_new_failures=True, gate_attempts=0, own_uncommitted=True)
    assert action == "block"


def test_own_uncommitted_respects_cap() -> None:
    assert hook.decide(
        git_dirty=True, has_new_failures=False, gate_attempts=0, own_uncommitted=True, commit_attempts=3
    ) == ("allow_warn", 0, 0)


def test_committed_own_work_allows() -> None:
    assert hook.decide(git_dirty=True, has_new_failures=False, gate_attempts=0, own_uncommitted=False) == (
        "allow",
        0,
        0,
    )


def test_session_files_parses_edit_tools_and_scopes_to_root(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    transcript = tmp_path / "t.jsonl"
    lines = [
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Edit", "input": {"file_path": str(root / "src/a.py")}},
                        {"type": "tool_use", "name": "Write", "input": {"file_path": str(root / "docs/b.md")}},
                        {"type": "tool_use", "name": "Read", "input": {"file_path": str(root / "c.py")}},
                        {"type": "tool_use", "name": "Edit", "input": {"file_path": "/elsewhere/outside.py"}},
                    ]
                },
            }
        ),
        '{"broken": "tool_use" not-valid-json',  # passes the pre-filter → exercises the json.loads except
        json.dumps({"type": "user", "message": {"content": "prose"}}),
    ]
    transcript.write_text("\n".join(lines), encoding="utf-8")
    got = hook._session_files(str(transcript), root.resolve())
    assert set(got) == {"src/a.py", "docs/b.md"}  # Read ignored; outside-root ignored


def test_session_files_returns_last_edit_timestamp(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    transcript = tmp_path / "t.jsonl"
    def mk(ts: str) -> str:
        return json.dumps(
            {
                "type": "assistant",
                "timestamp": ts,
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Edit",
                            "input": {"file_path": str(root / "a.py")},
                        }
                    ]
                },
            }
        )
    transcript.write_text(mk("2026-07-19T18:35:00.000Z") + "\n" + mk("2026-08-07T10:00:00.000Z"), encoding="utf-8")
    got = hook._session_files(str(transcript), root.resolve())
    assert got["a.py"] == 1786096800  # the LATER edit wins (2026-08-07T10:00Z)


def test_committed_session_edit_does_not_reattach_to_new_dirt(tmp_path: Path) -> None:
    # Live false-positive class (first ship): a resumed session's WEEKS-old edit
    # was committed long ago; TODAY the pipeline dirties the same file — the
    # commit-enforcement must NOT claim that dirt as this session's work.
    import subprocess as sp

    root = tmp_path / "repo"
    root.mkdir()
    sp.run(["git", "init", "-q"], cwd=root, check=True, timeout=15)
    sp.run(["git", "-C", str(root), "config", "user.email", "t@t"], check=True, timeout=15)
    sp.run(["git", "-C", str(root), "config", "user.name", "t"], check=True, timeout=15)
    f = root / "doc.md"
    f.write_text("v1\n", encoding="utf-8")
    sp.run(["git", "-C", str(root), "add", "doc.md"], check=True, timeout=15)
    sp.run(["git", "-C", str(root), "commit", "-qm", "session work committed"], check=True, timeout=15)
    f.write_text("v2 pipeline bump\n", encoding="utf-8")  # someone ELSE's new dirt
    # Session's last edit timestamp: long BEFORE the commit above (weeks ago).
    edit_ts = 1752950100  # 2026-07-19
    assert hook._last_commit_ts(root, "doc.md") >= edit_ts  # commit is newer
    # Wiring equivalent of the Stop-path filter:
    authored = {"doc.md": edit_ts}
    dirty = hook._dirty_paths(root)
    own = {r for r, ts in authored.items() if r in dirty and not (ts and hook._last_commit_ts(root, r) >= ts)}
    assert own == set()  # committed session work + foreign dirt → NOT flagged


def test_session_files_missing_transcript_fails_open() -> None:
    assert hook._session_files("/nonexistent/t.jsonl", Path("/tmp")) == {}


def test_gate_cap_exhaustion_does_not_starve_commit_block() -> None:
    # Review finding (2026-08-07): with a SHARED counter, 3 gate blocks exhausted
    # the CAP and the next stop skipped the commit check entirely. Independent
    # counters: after gate CAP is spent, an uncommitted-work stop still blocks.
    ga, ca = 0, 0
    for _ in range(3):
        action, ga, ca = hook.decide(True, True, ga, own_uncommitted=True, commit_attempts=ca)
        assert action == "block"
    # gate now green; commit check must still get its own full CAP
    action, ga, ca = hook.decide(True, False, ga, own_uncommitted=True, commit_attempts=ca)
    assert action == "block_commit" and ca == 1


def test_commit_cap_exhaustion_does_not_mask_new_gate_failure() -> None:
    ga, ca = 0, 3
    action, ga, ca = hook.decide(True, True, ga, own_uncommitted=True, commit_attempts=ca)
    assert action == "block" and ga == 1
