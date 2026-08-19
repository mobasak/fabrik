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
import time
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "final_gate_stop.py"
_spec = importlib.util.spec_from_file_location("final_gate_stop", _HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


@pytest.fixture(autouse=True)
def _isolate_kaizen_events(tmp_path_factory, monkeypatch) -> None:
    """Keep this suite's kaizen events out of the OPERATOR's real event store.

    The hook under test emits to ``$KAIZEN_EVENTS_DIR`` (default
    ``~/.claude/state/events``), and every helper below launches it with
    ``{**os.environ, …}`` — i.e. the developer's REAL home. Unisolated, a routine
    box-wide `pytest` run seeded the live store with synthetic session files (38 found
    and purged 2026-08-19), which the kaizen collector would then have measured as real
    sessions. Autouse + `os.environ` so it reaches every launch site at once, including
    any added later.
    """
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(tmp_path_factory.mktemp("kaizen-events")))


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
    assert hook.decide(git_dirty=True, has_new_failures=True, gate_attempts=3) == ("allow_warn_gate", 0, 0)


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
    ) == ("allow_warn_commit", 0, 0)


def test_committed_own_work_allows() -> None:
    assert hook.decide(git_dirty=True, has_new_failures=False, gate_attempts=0, own_uncommitted=False) == (
        "allow",
        0,
        0,
    )


_FAKE_GATE_WITH_OUTPUT = """#!/usr/bin/env python3
import json, os, sys
fails = [f for f in os.environ.get("FAKE_FAILS", "").split(",") if f]
if not fails:
    print(json.dumps({"status": "success", "failures": []})); sys.exit(0)
out = os.environ.get("FAKE_FAIL_OUTPUT", "")
per = json.loads(os.environ.get("FAKE_FAIL_OUTPUTS", "{}"))  # per-check override
print(json.dumps({"status": "failure", "failures": [{"check": c, "output": per.get(c, out)} for c in fails]}))
sys.exit(1)
"""


# --- routine-push law: committed-but-unpushed is an unfinished task ------------


def _push_repo(tmp_path: Path, *, upstream: bool, push: bool) -> Path:
    p = tmp_path / "pproj"
    (p / "scripts").mkdir(parents=True)
    (p / "scripts" / "final_gate.py").write_text(_FAKE_GATE)
    subprocess.run(["git", "init", "-q", "-b", "master"], cwd=p, check=True, timeout=15)
    (p / "a.txt").write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=p, check=True, timeout=15)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "w"],
        cwd=p, check=True, timeout=15,
    )
    if upstream:
        bare = tmp_path / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "master", str(bare)], check=True, timeout=15)
        subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=p, check=True, timeout=15)
        subprocess.run(["git", "push", "-qu", "origin", "master"], cwd=p, check=True, timeout=15)
        if not push:  # leave ONE commit ahead of the upstream
            (p / "b.txt").write_text("y")
            subprocess.run(["git", "add", "b.txt"], cwd=p, check=True, timeout=15)
            subprocess.run(
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "ahead"],
                cwd=p, check=True, timeout=15,
            )
    return p


def test_unpushed_committed_work_blocks(tmp_path: Path) -> None:
    p = _push_repo(tmp_path, upstream=True, push=False)
    out = _run_stop(p, "push1", "", baseline=[])
    assert out and "UNPUSHED" in out, out


def test_pushed_work_allows(tmp_path: Path) -> None:
    p = _push_repo(tmp_path, upstream=True, push=False)
    subprocess.run(["git", "push", "-q"], cwd=p, check=True, timeout=15)
    assert _run_stop(p, "push2", "", baseline=[]) == ""


def test_no_upstream_is_indeterminate_and_allows(tmp_path: Path) -> None:
    p = _push_repo(tmp_path, upstream=False, push=False)
    assert _run_stop(p, "push3", "", baseline=[]) == ""


def test_push_slot_resets_when_cause_resolves_across_a_gate_block(tmp_path: Path) -> None:
    # Reset-when-false for the p slot: a push block, then push (cause resolves),
    # then a gate/commit block must NOT carry the stale p count into a brand-new
    # unpushed streak (review finding — the stranded-counter class, p-slot edition).
    p = _push_repo(tmp_path, upstream=True, push=False)
    sid = "pstrand"
    ctr = Path(hook.tempfile.gettempdir()) / f"fabrik-gate-stop-{sid}.attempts"
    bl = Path(hook.tempfile.gettempdir()) / f"fabrik-gate-baseline-{sid}.json"
    try:
        bl.write_text(json.dumps([]))
        ctr.unlink(missing_ok=True)
        env = {**os.environ, "FAKE_FAILS": ""}

        def stop() -> str:
            proc = subprocess.run(
                [sys.executable, str(_HOOK)],
                input=json.dumps({"session_id": sid, "cwd": str(p), "hook_event_name": "Stop"}),
                capture_output=True, text=True, timeout=60, env=env,
            )
            return proc.stdout.strip()

        assert "UNPUSHED" in stop()                      # p -> 1
        subprocess.run(["git", "push", "-q"], cwd=p, check=True, timeout=15)  # cause resolves
        (p / "dirty.txt").write_text("x")                # dirty tree
        env["FAKE_FAILS"] = "NewCheck"                   # NEW gate failure -> gate block
        out = stop()
        assert "DEFINITION OF DONE NOT MET" in out
        env["FAKE_FAILS"] = ""
        (p / "dirty.txt").unlink()
        (p / "c.txt").write_text("z")                    # brand-new unpushed streak
        subprocess.run(["git", "add", "c.txt"], cwd=p, check=True, timeout=15)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "new"],
            cwd=p, check=True, timeout=15,
        )
        out = stop()
        assert "UNPUSHED WORK (attempt 1/3)" in out, out  # fresh streak starts at 1, not 2
    finally:
        ctr.unlink(missing_ok=True)
        bl.unlink(missing_ok=True)


def test_baseline_survives_resume_but_not_fresh_start(fake_project: Path) -> None:
    # Mesh interplay: a revived session (source=resume/compact) must KEEP its
    # original baseline — re-baselining would swallow the session's own gate
    # breakage into "inherited" and disarm the gate cause (review finding).
    sid = "blres"
    bl = Path(hook.tempfile.gettempdir()) / f"fabrik-gate-baseline-{sid}.json"
    try:
        bl.write_text(json.dumps(["Original"]))
        env = {**os.environ, "FAKE_FAILS": "NewCheck"}
        for source, expect in (("resume", ["Original"]), ("compact", ["Original"]),
                               ("startup", ["NewCheck"])):
            proc = subprocess.run(
                [sys.executable, str(_HOOK), "--baseline"],
                input=json.dumps({"session_id": sid, "cwd": str(fake_project),
                                  "hook_event_name": "SessionStart", "source": source}),
                capture_output=True, text=True, timeout=60, env=env,
            )
            assert proc.returncode == 0
            assert json.loads(bl.read_text()) == expect, f"source={source}"
    finally:
        bl.unlink(missing_ok=True)


def test_counters_read_legacy_three_slot(tmp_path: Path) -> None:
    ctr = tmp_path / "c.attempts"
    ctr.write_text("1,2,0")
    assert hook._read_counters(ctr) == (1, 2, 0, 0, 0)


def _run_stop_with_transcript(
    project: Path, sid: str, fake_fails: str, fail_output: str, authored_file: str, *, baseline: list[str],
    extra_authored: list[str] | None = None, per_check_outputs: dict[str, str] | None = None,
) -> str:
    """Stop-hook run with a transcript naming session-authored (committed) file(s)."""
    (project / "scripts" / "final_gate.py").write_text(_FAKE_GATE_WITH_OUTPUT)
    authored_all = [authored_file, *(extra_authored or [])]
    lines = []
    for af in authored_all:
        ap = project / af
        ap.parent.mkdir(parents=True, exist_ok=True)
        ap.write_text("session work")
        lines.append(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Edit", "input": {"file_path": str(ap)}}
        ]}}))
    subprocess.run(["git", "add", *authored_all], cwd=project, check=True, timeout=15)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "session work"],
        cwd=project, check=True, timeout=15,
    )
    transcript = project / "transcript.jsonl"
    transcript.write_text("\n".join(lines) + "\n", encoding="utf-8")
    bl = Path(hook.tempfile.gettempdir()) / f"fabrik-gate-baseline-{sid}.json"
    ctr = Path(hook.tempfile.gettempdir()) / f"fabrik-gate-stop-{sid}.attempts"
    ctr.unlink(missing_ok=True)
    bl.write_text(json.dumps(baseline))
    env = {**os.environ, "FAKE_FAILS": fake_fails, "FAKE_FAIL_OUTPUT": fail_output,
           "FAKE_FAIL_OUTPUTS": json.dumps(per_check_outputs or {})}
    proc = subprocess.run(
        [sys.executable, str(_HOOK)],
        input=json.dumps({
            "session_id": sid, "cwd": str(project),
            "transcript_path": str(transcript), "hook_event_name": "Stop",
        }),
        capture_output=True, text=True, timeout=60, env=env,
    )
    bl.unlink(missing_ok=True)
    ctr.unlink(missing_ok=True)
    return proc.stdout.strip()


def test_new_failure_citing_only_sibling_files_does_not_block(fake_project: Path) -> None:
    # NEW failing check whose output cites ONLY a sibling's file → shared-tree cause → allow.
    out = _run_stop_with_transcript(
        fake_project, "s_sibling", "DocSync",
        "CHANGELOG.md not updated for src/fabrik/orchestrator/__init__.py (sibling staged)",
        "mine/session_file.py", baseline=[],
    )
    assert out == "", f"sibling-caused new failure must not block, got: {out}"


def test_new_failure_citing_session_file_still_blocks(fake_project: Path) -> None:
    # Same shape, but the failure output cites the session-authored file → still block.
    out = _run_stop_with_transcript(
        fake_project, "s_selfcause", "DocSync",
        "CHANGELOG.md not updated for mine/session_file.py",
        "mine/session_file.py", baseline=[],
    )
    assert out, "session-caused new failure must still block"
    assert json.loads(out)["decision"] == "block"


def test_routine_governance_cite_alone_does_not_attribute(fake_project: Path) -> None:
    # THE live incident: every session authors CHANGELOG.md, and Doc Sync's output names
    # it even when a SIBLING's code change created the obligation. A failure citing only
    # CHANGELOG.md + sibling files must NOT attribute to a session that authored
    # CHANGELOG.md (plus unrelated work).
    out = _run_stop_with_transcript(
        fake_project, "s_govonly", "DocSync",
        "CHANGELOG.md not updated for 1 significant code/infra change(s) (e.g. src/sibling/thing.py).",
        "mine/session_file.py", baseline=[], extra_authored=["CHANGELOG.md"],
    )
    assert out == "", f"governance-name cite alone must not attribute, got: {out}"


def test_pathless_output_is_indeterminate_and_blocks(fake_project: Path) -> None:
    # A NEW failure whose output cites no path at all cannot be attributed — the hook
    # must NOT wave it through (the fail-open hole): keep blocking up to the cap.
    out = _run_stop_with_transcript(
        fake_project, "s_pathless", "shapeCheck",
        "0 rows matched the expected shape",
        "mine/session_file.py", baseline=[],
    )
    assert out, "path-less new failure is indeterminate and must block"


def test_two_empty_outputs_still_block(fake_project: Path) -> None:
    # Two failures with empty outputs used to make the joined text truthy ("\n") and
    # skip the guard; count must not change the verdict — still indeterminate → block.
    out = _run_stop_with_transcript(
        fake_project, "s_twoempty", "checkA,checkB", "",
        "mine/session_file.py", baseline=[],
    )
    assert out, "empty outputs are indeterminate regardless of failure count"


def test_inherited_failure_output_does_not_contaminate_attribution(fake_project: Path) -> None:
    # Baseline failure cites the session's file; the NEW failure cites only a sibling's.
    # Attribution must scope to the NEW failure's output → downgrade (allow).
    out = _run_stop_with_transcript(
        fake_project, "s_contam", "inheritedCheck,newCheck", "",
        "mine/session_file.py", baseline=["inheritedCheck"],
        per_check_outputs={
            "inheritedCheck": "old debt in mine/session_file.py",
            "newCheck": "sibling broke src/sibling/x.py",
        },
    )
    assert out == "", f"inherited output must not contaminate NEW-failure attribution, got: {out}"


def test_substring_cite_does_not_attribute(fake_project: Path) -> None:
    # Cited data_app.py must not match authored app.py (substring ban) → downgrade.
    out = _run_stop_with_transcript(
        fake_project, "s_substr", "lintCheck",
        "syntax error in src/data_app.py line 3",
        "app.py", baseline=[],
    )
    assert out == "", f"substring collision must not attribute, got: {out}"


def test_abs_path_cite_still_attributes(fake_project: Path) -> None:
    # A failure citing the session file by ABSOLUTE path still attributes (suffix match).
    out = _run_stop_with_transcript(
        fake_project, "s_abs", "lintCheck",
        "error at /opt/whatever/checkout/mine/session_file.py:3",
        "mine/session_file.py", baseline=[],
    )
    assert out, "absolute-path cite of a session file must still block"


def test_session_breaking_governance_file_itself_is_indeterminate(fake_project: Path) -> None:
    # A failure citing ONLY CHANGELOG.md, with CHANGELOG.md session-authored and NO
    # sibling trigger file in the output → the session may have broken it itself →
    # indeterminate → block (never waved through by the governance exclusion).
    out = _run_stop_with_transcript(
        fake_project, "s_govself", "MarkdownLint",
        "CHANGELOG.md: malformed heading at line 12",
        "CHANGELOG.md", baseline=[],
    )
    assert out, "governance-only cite with the file session-authored must block (indeterminate)"


def test_pre_session_edit_does_not_attribute() -> None:
    # A resumed transcript's weeks-old edit (ts far below the SessionStart baseline
    # floor) must not attribute today's failure to this session.
    old_edit = {"july/old_file.py": 1_700_000_000}  # far in the past
    verdict = hook._failure_cites_session(
        ["error in july/old_file.py"], old_edit, session_floor=1_786_000_000.0
    )
    assert verdict is False, "pre-session edits must not attribute"
    fresh_edit = {"july/old_file.py": 1_786_000_500}
    verdict2 = hook._failure_cites_session(
        ["error in july/old_file.py"], fresh_edit, session_floor=1_786_000_000.0
    )
    assert verdict2 is True, "in-session edits must attribute"


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
    # gate now green; commit check must still get its own full CAP — AND the
    # resolved gate streak's counter must RESET (stale carryover waved a new
    # regression through on its first stop; pass-3 finding).
    action, ga, ca = hook.decide(True, False, ga, own_uncommitted=True, commit_attempts=ca)
    assert action == "block_commit" and ca == 1 and ga == 0


def test_resolved_streak_counter_never_waves_a_new_streak_through() -> None:
    # Pass-3 repro: failure A blocked 3x -> resolved -> commit-block interleave ->
    # brand-new failure B must be BLOCKED on its first stop, not allow_warn'd.
    ga, ca = 0, 0
    for _ in range(3):
        action, ga, ca = hook.decide(True, True, ga, commit_attempts=ca)
        assert action == "block"
    action, ga, ca = hook.decide(True, False, ga, own_uncommitted=True, commit_attempts=ca)
    assert action == "block_commit" and ga == 0
    action, ga, ca = hook.decide(True, True, ga, commit_attempts=ca)  # NEW streak B
    assert action == "block" and ga == 1  # blocked, never waved through


def test_commit_cap_exhaustion_does_not_mask_new_gate_failure() -> None:
    ga, ca = 0, 3
    action, ga, ca = hook.decide(True, True, ga, own_uncommitted=True, commit_attempts=ca)
    assert action == "block" and ga == 1


def test_warn_actions_name_their_cause() -> None:
    # Review finding: an unconditional "gate still RED" warn was false on
    # commit-cap exhaustion — the two exhaustion paths must be distinguishable.
    a_gate, _, _ = hook.decide(True, True, gate_attempts=3)
    a_commit, _, _ = hook.decide(True, False, gate_attempts=0, own_uncommitted=True, commit_attempts=3)
    assert a_gate == "allow_warn_gate" and a_commit == "allow_warn_commit"


# --- promise-guard (stall detection) ------------------------------------------

def _turn(transcript: Path, *entries: str) -> None:
    transcript.write_text("\n".join(entries) + "\n", encoding="utf-8")


def _user(text: str = "do the thing") -> str:
    return json.dumps({"type": "user", "message": {"content": [{"type": "text", "text": text}]}})


def _asst_text(text: str) -> str:
    return json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}})


def _asst_tool(name: str, **inp) -> str:
    return json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": inp}]}})


def test_promise_without_dispatch_is_a_stall(tmp_path: Path) -> None:
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text("Pass 5 is owed. I'll run it and report at the quiet round."))
    kind = hook._detect_stall(str(tr), tmp_path, set())
    assert kind and kind[0] == "promise"


def test_promise_with_background_dispatch_is_kept(tmp_path: Path) -> None:
    # The promise was KEPT: a subagent dispatch happened in the same final turn.
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_tool("Task", prompt="run pass 5"),
          _asst_text("Starting it now — Pass 5 dispatched, will report."))
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


# Live incident (trade-intelligence, 2nd occurrence of the stall class): the agent
# named the obligation in PASSIVE voice — no first-person future verb anywhere —
# and ended the turn. The corpus's own convergence contracts teach this vocabulary
# ("you owe the next pass — dispatch it"), so the guard must read it.
_TRADE_INTEL_OWED_FINAL = (
    "Committed f4724e2. 19 backend tests green, tree clean, nine commits this run.\n\n"
    "Pass 7 is owed, and for the first time its scope is named work rather than "
    "another adversarial sweep: the JS stripper is still fail-open through nested "
    "template literals (one real file already desyncs), and the text assertions "
    "should now be relaxed — the behavioural guard carries the weight."
)


def test_passive_obligation_without_dispatch_is_a_stall(tmp_path: Path) -> None:
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text(_TRADE_INTEL_OWED_FINAL))
    kind = hook._detect_stall(str(tr), tmp_path, set())
    assert kind and kind[0] == "promise"


def test_passive_obligation_with_dispatch_is_kept(tmp_path: Path) -> None:
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_tool("Task", prompt="run pass 7"),
          _asst_text("Pass 7 is owed — dispatched, reporting at the quiet round."))
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


def test_first_person_owe_is_a_stall(tmp_path: Path) -> None:
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text("Gate is green. I still owe the confirming round."))
    kind = hook._detect_stall(str(tr), tmp_path, set())
    assert kind and kind[0] == "promise"


def test_negated_obligation_is_allowed(tmp_path: Path) -> None:
    # A convergence CONCLUSION uses the same nouns — "no further pass is owed".
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text(
        "Ledger row 3: edits 0, md5 identical — CONVERGED. No further pass is owed."))
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


# Live incident (brand-identiy-creator, 2026-08-11 — 3rd shape of the stall
# class): the agent CLAIMED continuation in an assertive gerund — no first-person
# future verb, no passive obligation — and ended the turn. "Continuing
# autonomously." is a promise by definition: it asserts ongoing action at the
# exact moment action stops. The same message also carries the structural form:
# a NEXT: footer naming a NUMBERED own-loop round.
_BRAND_IDENTITY_CONTINUING_FINAL = (
    "Round 6 findings fixed and committed.\n\n"
    "NEXT: round 7 on the r6 diff → a clean round closes Phase B → Phase C "
    "(C1–C20). Continuing autonomously."
)


def test_continuation_claim_without_dispatch_is_a_stall(tmp_path: Path) -> None:
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text(_BRAND_IDENTITY_CONTINUING_FINAL))
    kind = hook._detect_stall(str(tr), tmp_path, set())
    assert kind and kind[0] == "promise"


def test_continuation_claim_with_dispatch_is_kept(tmp_path: Path) -> None:
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_tool("Agent", prompt="round 7 finders"),
          _asst_text(_BRAND_IDENTITY_CONTINUING_FINAL))
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


def test_next_round_footer_alone_is_a_stall(tmp_path: Path) -> None:
    # The structural form with NO continuation gerund at all.
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text(
        "Round 6 committed, gates green.\n\nNEXT: round 7 on the r6 diff — a clean "
        "round closes Phase B."))
    kind = hook._detect_stall(str(tr), tmp_path, set())
    assert kind and kind[0] == "promise"


def test_next_round_footer_operator_gated_is_exempt(tmp_path: Path) -> None:
    # Same-line human-gate wording exempts, exactly as for the other patterns.
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text(
        "Round 6 committed.\n\nNEXT: round 7 — operator decision: resume or reshape."))
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


def test_terminal_bare_continuing_is_a_stall(tmp_path: Path) -> None:
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text("Fixes applied, gate green. Continuing."))
    kind = hook._detect_stall(str(tr), tmp_path, set())
    assert kind and kind[0] == "promise"


def test_conversational_continuing_is_not_a_stall(tmp_path: Path) -> None:
    # Plain gerund with neither qualifier nor terminal position — conversational.
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text(
        "Continuing our earlier discussion of the tradeoffs, option B is better "
        "because it keeps the contract in one file."))
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


def test_quoted_continuation_claim_is_not_a_stall(tmp_path: Path) -> None:
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text(
        'The guard now also catches "Continuing autonomously." as a stall shape.'))
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


def test_obligation_quoted_mid_sentence_is_exempt(tmp_path: Path) -> None:
    # The quote span, not just the char before the noun: a report QUOTING a
    # stall snippet is discussing it, not making it.
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text(
        'Finding 3: the final said "the confirming pass is owed" and stopped — classic stall, now fixed.'))
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


def test_negated_obligation_with_long_subject_is_allowed(tmp_path: Path) -> None:
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text(
        "No adversarial or confirming pass is owed. No whole-plan review pass is owed either."))
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


def test_obligation_adverb_variants_are_stalls(tmp_path: Path) -> None:
    tr = tmp_path / "t.jsonl"
    for text in ("Pass 7 is now owed.", "The confirming round is already owed.",
                 "Pass 7 is still outstanding.", "The sweep remains to be run."):
        _turn(tr, _user(), _asst_text(text))
        kind = hook._detect_stall(str(tr), tmp_path, set())
        assert kind and kind[0] == "promise", f"missed: {text!r}"


def test_deadline_and_gratitude_prose_are_allowed(tmp_path: Path) -> None:
    tr = tmp_path / "t.jsonl"
    for text in ("The quarterly review is due on Friday for the operator.",
                 "Two fixes are due before release; both landed and are committed.",
                 "Phase C is due once the operator approves.",
                 "We owe a debt of gratitude to the pool finders.",
                 "We owe it to future sessions to keep the ledger honest."):
        _turn(tr, _user(), _asst_text(text))
        assert hook._detect_stall(str(tr), tmp_path, set()) is None, f"false positive: {text!r}"


def test_due_to_causal_is_allowed(tmp_path: Path) -> None:
    # "due to" is causal prose, not an obligation.
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text(
        "The DataError on first run is due to the missing jsonb codec listener; fixed and green."))
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


def test_permission_question_with_session_owned_lock_is_a_stall(tmp_path: Path) -> None:
    locks = tmp_path / ".fabrik" / "plan-locks"
    locks.mkdir(parents=True)
    (locks / "x.json").write_text('{"status": "active"}')
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text("The T2 cap says route to a plan. Want me to run /fabrik-plan-after-chat now?"))
    # session-scoped: the lock counts only when THIS session authored it
    kind = hook._detect_stall(str(tr), tmp_path, {".fabrik/plan-locks/x.json"})
    assert kind and kind[0] == "permission"
    # an unrelated sibling's active lock (not session-authored) must NOT fire
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


def test_permission_question_without_midrun_marker_is_allowed(tmp_path: Path) -> None:
    # A follow-up OFFER after completed work (no active plan/review) is legitimate.
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text("All done and committed. Want me to also fold these in?"))
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


def test_human_gate_wording_is_never_a_stall(tmp_path: Path) -> None:
    locks = tmp_path / ".fabrik" / "plan-locks"
    locks.mkdir(parents=True)
    (locks / "x.json").write_text('{"status": "active"}')
    owned = {".fabrik/plan-locks/x.json"}
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text("Converged. Gate 2 is yours — awaiting your approval to deploy."))
    assert hook._detect_stall(str(tr), tmp_path, owned) is None
    _turn(tr, _user(), _asst_text("BLOCKED: vendor API — searched docs+web — missing auth scheme."))
    assert hook._detect_stall(str(tr), tmp_path, owned) is None


def test_unchecked_review_is_a_midrun_marker(tmp_path: Path) -> None:
    rev = tmp_path / "docs/development/reviews"
    rev.mkdir(parents=True)
    (rev / "2026-01-01-x-review.md").write_text("| class | UNCHECKED | |\n")
    tr = tmp_path / "t.jsonl"
    # No obligation clause here on purpose — this fixture isolates the PERMISSION
    # path (the UNCHECKED review doc arming the mid-run marker).
    _turn(tr, _user(), _asst_text("Round 2 finished clean. Shall I continue with the next pass?"))
    kind = hook._detect_stall(str(tr), tmp_path, {"docs/development/reviews/2026-01-01-x-review.md"})
    assert kind and kind[0] == "permission"


def test_garbage_transcript_fails_open(tmp_path: Path) -> None:
    tr = tmp_path / "t.jsonl"
    tr.write_text("not json at all\n{broken", encoding="utf-8")
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


def test_decide_stall_counter_and_cap() -> None:
    a1 = hook.decide_stall(True, 0)
    assert a1 == ("block_stall", 1)
    a3 = hook.decide_stall(True, 3)
    assert a3 == ("allow_warn_stall", 0)
    assert hook.decide_stall(False, 2) == ("allow", 0)  # cause resolved -> counter resets


def test_quoted_stall_phrases_are_exempt(tmp_path: Path) -> None:
    """Discussing/quoting a stall phrase must not fire (live FP: the guard's own
    author quoted 'Want me to…?' as an example and got blocked)."""
    locks = tmp_path / ".fabrik" / "plan-locks"
    locks.mkdir(parents=True)
    (locks / "x.json").write_text('{"status": "active"}')
    owned = {".fabrik/plan-locks/x.json"}
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text(
        "Agents get bounced when they end a turn on 'I'll run it' or \"Want me to…?\" — the guard is live."))
    assert hook._detect_stall(str(tr), tmp_path, owned) is None


def test_unquoted_stall_still_fires_alongside_quotes(tmp_path: Path) -> None:
    locks = tmp_path / ".fabrik" / "plan-locks"
    locks.mkdir(parents=True)
    (locks / "x.json").write_text('{"status": "active"}')
    owned = {".fabrik/plan-locks/x.json"}
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text(
        "The old stall was 'I did nothing'. Anyway: want me to run the next pass now?"))
    kind = hook._detect_stall(str(tr), tmp_path, owned)
    assert kind and kind[0] == "permission"


def test_next_operator_decision_line_does_not_blind_the_guard(tmp_path: Path) -> None:
    # Mandated FINAL OUTPUT vocabulary ("NEXT: operator decision: …") on its own
    # line must not disarm a genuine undispatched promise elsewhere in the
    # message — exemption tokens are line-scoped (BLOCKED: stays global).
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text(
        "I'll run the confirming pass and report back.\n\n"
        "GATE: success\nNEXT: operator decision: whether to push\n"))
    kind = hook._detect_stall(str(tr), tmp_path, set())
    assert kind and kind[0] == "promise"


def test_conditional_offer_is_an_operator_gate_not_a_stall(tmp_path: Path) -> None:
    # Live FP (guard fired on its own author): a follow-up OFFER conditioned on
    # the operator's word is a sanctioned stop, not a stall.
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text(
        "This is a command-source change plus a small helper — say the word and "
        "I'll run it through the pipeline."))
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


def test_gate_exemption_suppresses_a_real_promise(tmp_path: Path) -> None:
    """Mutation-killer: the exemption must be load-bearing — a REAL promise inside
    human-gate wording is exempt; delete the exemption regex and this goes red."""
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text("Gate 2 is yours — after you approve, I'll run the deploy-verify suite."))
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


def test_blocked_header_exempts_despite_long_detail(tmp_path: Path) -> None:
    """The exemption scans the FULL message — a BLOCKED header must not be split
    away from a trailing promise by the 600-char tail cut."""
    detail = "search detail line\n" * 60
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text(
        "BLOCKED: vendor API — searched: docs, web — missing: auth scheme.\n" + detail +
        "Once you supply the scheme I'll run the suite."))
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


def test_prose_unchecked_mention_does_not_arm_marker(tmp_path: Path) -> None:
    """Mutation-killer for the live-row form: a CLOSED review's prose mention of
    UNCHECKED must not arm the permission marker."""
    rev = tmp_path / "docs/development/reviews"
    rev.mkdir(parents=True)
    (rev / "r.md").write_text("fixed classes return to UNCHECKED until re-adjudicated\n")
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text("Shall I run the next pass now?"))
    assert hook._detect_stall(str(tr), tmp_path, {"docs/development/reviews/r.md"}) is None


def test_quoted_promise_does_not_mask_a_later_real_one(tmp_path: Path) -> None:
    """Guard-defeat killer: a quoted example must not disarm a genuine promise
    that follows it."""
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text(
        "The old stall was 'I'll run it'. Anyway, I'll run the next pass now."))
    kind = hook._detect_stall(str(tr), tmp_path, set())
    assert kind and kind[0] == "promise"


def test_conversational_verbs_without_action_object_are_silent(tmp_path: Path) -> None:
    """Read-only turns must never stall (the highest-volume FP class)."""
    tr = tmp_path / "t.jsonl"
    for msg in (
        "Three options exist. Let me run through them before you pick one.",
        "Let me start by confirming which VPS you mean.",
        "Findings below. I'll begin with the CONFIRMED ones.",
    ):
        _turn(tr, _user(), _asst_text(msg))
        assert hook._detect_stall(str(tr), tmp_path, set()) is None, msg


def test_rund_and_slashcommand_count_as_dispatch(tmp_path: Path) -> None:
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_tool("Bash", command="rund -- pytest -q tests/"),
          _asst_text("I'll run the suite and report as results land."))
    assert hook._detect_stall(str(tr), tmp_path, set()) is None
    _turn(tr, _user(), _asst_tool("SlashCommand", command="/fabrik-review"),
          _asst_text("I'll run /fabrik-review now."))
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


def test_prior_turn_dispatch_does_not_exempt_and_prior_promise_not_inherited(tmp_path: Path) -> None:
    """Turn-boundary killers: (a) a PRIOR turn's Task must not exempt this turn's
    promise; (b) an empty final message must not inherit an older promise."""
    tr = tmp_path / "t.jsonl"
    _turn(tr,
          _user("first ask"), _asst_tool("Task", prompt="old work"), _asst_text("done that."),
          _user("second ask"), _asst_text("I'll run the confirming pass now."))
    kind = hook._detect_stall(str(tr), tmp_path, set())
    assert kind and kind[0] == "promise", "prior-turn dispatch must not exempt"
    _turn(tr,
          _user(), _asst_text("I'll run the suite now."), _asst_tool("Read", file_path="/x"),
          _asst_text(""))
    assert hook._detect_stall(str(tr), tmp_path, set()) is None, "empty final text must not inherit"


def test_counter_format_round_trips(tmp_path: Path) -> None:
    c = tmp_path / "ctr"
    for raw, expect in [("3", (3, 0, 0, 0, 0)), ("3,1", (3, 1, 0, 0, 0)),
                        ("3,1,2", (3, 1, 2, 0, 0)), ("", (0, 0, 0, 0, 0)),
                        ("x,y", (0, 0, 0, 0, 0)), ("1,2,3,4", (1, 2, 3, 4, 0)),
                        ("1,2,3,4,5", (1, 2, 3, 4, 5))]:
        c.write_text(raw)
        assert hook._read_counters(c) == expect, raw


def test_e2e_stall_blocks_and_gate_block_does_not_strand_stall_counter(fake_project: Path) -> None:
    """End-to-end through main(): a stall emits decision:block; an intervening
    gate block must RESET the stall slot when the stall is absent (the stranded-
    counter regression class)."""
    sid = "s_stall_e2e"
    tr = fake_project / "transcript.jsonl"
    ctr = Path(hook.tempfile.gettempdir()) / f"fabrik-gate-stop-{sid}.attempts"
    bl = Path(hook.tempfile.gettempdir()) / f"fabrik-gate-baseline-{sid}.json"
    ctr.unlink(missing_ok=True)
    bl.write_text(json.dumps([]))
    def stop(fails: str, final_text: str) -> str:
        tr.write_text("\n".join([_user(), _asst_text(final_text)]) + "\n")
        env = {**os.environ, "FAKE_FAILS": fails}
        proc = subprocess.run([sys.executable, str(_HOOK)],
            input=json.dumps({"session_id": sid, "cwd": str(fake_project),
                              "transcript_path": str(tr), "hook_event_name": "Stop"}),
            capture_output=True, text=True, timeout=60, env=env)
        return proc.stdout.strip()
    out = stop("", "I'll run the confirming pass now.")
    assert out and json.loads(out)["decision"] == "block" and "STALL" in json.loads(out)["reason"]
    assert ctr.read_text().split(",")[2] == "1"
    # now a GATE failure with NO stall in the final message → stall slot must reset to 0
    out2 = stop("NEWCHECK", "Fixed some things; see the diff.")
    assert out2, "gate failure should block"
    assert ctr.read_text().split(",")[2] == "0", "stall slot must reset when the stall is absent"
    ctr.unlink(missing_ok=True)
    bl.unlink(missing_ok=True)


def test_passive_availability_stall_dispatchable(tmp_path: Path) -> None:
    # Live miss 2026-08-10 (iterative_image_editor orchestrator): the turn ended on
    # "T03 and T05 are now both dispatchable in parallel" with the tickets undispatched —
    # availability phrasing carries the same undone-own-work signal as "is owed".
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text(
        "T02's review round is closed and pushed. "
        "T03 and T05 are now both dispatchable in parallel."))
    kind = hook._detect_stall(str(tr), tmp_path, set())
    assert kind and kind[0] == "promise"


def test_passive_availability_ready_to_dispatch(tmp_path: Path) -> None:
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text("Phase C is ready to dispatch once you confirm nothing."))
    kind = hook._detect_stall(str(tr), tmp_path, set())
    assert kind and kind[0] == "promise"


def test_passive_availability_with_dispatch_is_kept(tmp_path: Path) -> None:
    # Availability phrasing + an ACTUAL dispatch in the same turn = work continuing.
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_tool("Task", prompt="execute T03"),
          _asst_text("T03 and T05 are dispatchable — T03 dispatched now, T05 queued behind it."))
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


def test_negated_availability_is_a_conclusion(tmp_path: Path) -> None:
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text(
        "Nothing further is dispatchable — every ticket is merged; the plan is EXECUTED."))
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


# --- FIFTH cause: an in-flight COMMAND RUN RECORD blocks the stop -------------
# Operator complaint: "agents are still stopping without reaching a no ops pass or
# fully executing the commands for no valid reason". A `running` record is the ONLY
# state that blocks; missing / corrupt / unreadable / stale fails OPEN — the fail
# direction is deliberately asymmetric so broken state can never trap an agent.


def _running_record(**over: object) -> dict:
    rec: dict = {
        "session_id": "x",
        "command": "fabrik-review",
        "phases": 5,
        "phase": 4,
        "phase_title": "Converge",
        "terminal": "found:0 no-op round",
        "state": "running",
        "rounds": [{"n": 1, "findings": 3, "swept": [], "new": []}],
        "classes": {"auth": "open"},
        "updated_ts": int(time.time()),
    }
    rec.update(over)
    return rec


def _run_stop_with_record(project: Path, tmp_path: Path, sid: str, rec: object) -> str:
    """Run the Stop hook with a command-run record present; return stdout."""
    run_dir = tmp_path / "command-runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    ctr = Path(hook.tempfile.gettempdir()) / f"fabrik-gate-stop-{sid}.attempts"
    ctr.unlink(missing_ok=True)
    if rec is not None:
        body = rec if isinstance(rec, str) else json.dumps(rec)
        (run_dir / f"{sid}.json").write_text(body)
    env = {**os.environ, "FAKE_FAILS": "", "COMMAND_RUN_DIR": str(run_dir)}
    proc = subprocess.run(
        [sys.executable, str(_HOOK)],
        input=json.dumps({"session_id": sid, "cwd": str(project), "hook_event_name": "Stop"}),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    ctr.unlink(missing_ok=True)
    return proc.stdout.strip()


def test_running_command_run_blocks_the_stop(fake_project: Path, tmp_path: Path) -> None:
    out = _run_stop_with_record(fake_project, tmp_path, "s_run_running", _running_record())
    assert out, "an in-flight command run must block the stop"
    payload = json.loads(out)
    assert payload["decision"] == "block"
    reason = payload["reason"]
    assert "/fabrik-review" in reason, reason
    assert "4/5" in reason, reason  # phase c/t
    assert "round 1" in reason, reason
    assert "found:0 no-op round" in reason, reason  # the terminal condition
    # Both exits, each PRE-FILLED with the live run's name — the agent must never have
    # to guess it, and a close naming anything else is refused.
    assert "done --command fabrik-review --evidence" in reason, reason
    assert "blocked --command fabrik-review --reason" in reason, reason


def test_done_record_does_not_block(fake_project: Path, tmp_path: Path) -> None:
    rec = _running_record(state="done", evidence="found: 0 on round 4")
    assert _run_stop_with_record(fake_project, tmp_path, "s_run_done", rec) == ""


def test_blocked_record_does_not_block(fake_project: Path, tmp_path: Path) -> None:
    rec = _running_record(state="blocked", blocked_reason="missing infra")
    assert _run_stop_with_record(fake_project, tmp_path, "s_run_blocked", rec) == ""


def test_corrupt_run_record_fails_open(fake_project: Path, tmp_path: Path) -> None:
    assert _run_stop_with_record(fake_project, tmp_path, "s_run_corrupt", "{not json") == ""


def test_missing_run_record_fails_open(fake_project: Path, tmp_path: Path) -> None:
    assert _run_stop_with_record(fake_project, tmp_path, "s_run_missing", None) == ""


def test_stale_run_record_fails_open(fake_project: Path, tmp_path: Path) -> None:
    # >COMMAND_RUN_STALE_H (12h) without an update = an abandoned record from a dead
    # session, not live work — never trap a new session on someone else's leftovers.
    stale = _running_record(updated_ts=int(time.time()) - 20 * 3600)
    assert _run_stop_with_record(fake_project, tmp_path, "s_run_stale", stale) == ""


def test_run_record_cause_uses_the_shared_anti_trap_idiom() -> None:
    # Same counter / reset-when-false / warn-through shape as every other cause.
    assert hook.decide_stall(True, 0) == ("block_stall", 1)
    assert hook.decide_stall(True, 2) == ("block_stall", 3)
    assert hook.decide_stall(True, 3) == ("allow_warn_stall", 0)
    assert hook.decide_stall(False, 2) == ("allow", 0)


def test_counter_file_gains_a_fifth_slot_tolerating_older_files(tmp_path: Path) -> None:
    ctr = tmp_path / "c.attempts"
    ctr.write_text("1,2,3")  # a 3-slot file written before the 5th cause existed
    assert hook._read_counters(ctr) == (1, 2, 3, 0, 0)
    ctr.write_text("1,2,3,4,5")
    assert hook._read_counters(ctr) == (1, 2, 3, 4, 5)


# --- F-R2: freshness must be POSITIVELY PROVEN, or the record fails open ------
# The isinstance() gate SKIPPED the staleness check for every unusual timestamp
# shape, so each of these blocked forever, indistinguishable from a real block.
# (json.loads accepts bare NaN / Infinity literals, so those reach the hook.)


@pytest.mark.parametrize(
    ("shape", "body"),
    [
        ("missing ts", '{"state": "running", "command": "x", "phases": 1, "phase": 1}'),
        ("NaN ts", '{"state": "running", "command": "x", "updated_ts": NaN}'),
        ("Infinity ts", '{"state": "running", "command": "x", "updated_ts": Infinity}'),
        ("-Infinity ts", '{"state": "running", "command": "x", "updated_ts": -Infinity}'),
        ("string ts", '{"state": "running", "command": "x", "updated_ts": "1755300000"}'),
        ("bool ts", '{"state": "running", "command": "x", "updated_ts": true}'),
        ("null ts", '{"state": "running", "command": "x", "updated_ts": null}'),
    ],
)
def test_unprovable_freshness_fails_open(
    fake_project: Path, tmp_path: Path, shape: str, body: str
) -> None:
    sid = "s_ts_" + shape.replace(" ", "_").replace("-", "n")
    assert _run_stop_with_record(fake_project, tmp_path, sid, body) == "", shape


def test_far_future_timestamp_fails_open(fake_project: Path, tmp_path: Path) -> None:
    # A ts beyond the clock-skew tolerance is not evidence of freshness — it is a
    # broken clock or a corrupted write. Unprovable → fail open.
    future = _running_record(updated_ts=int(time.time()) + 86_400)
    assert _run_stop_with_record(fake_project, tmp_path, "s_ts_future", future) == ""


def test_small_forward_skew_still_blocks(fake_project: Path, tmp_path: Path) -> None:
    # Within tolerance = an ordinary clock wobble on a LIVE record; must still block,
    # or the escape hatch becomes "set your clock 1 second ahead".
    skewed = _running_record(updated_ts=int(time.time()) + 5)
    assert _run_stop_with_record(fake_project, tmp_path, "s_ts_skew", skewed) != ""


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_stale_hours_that_disable_the_hatch_fail_open(
    fake_project: Path, tmp_path: Path, value: str
) -> None:
    """`COMMAND_RUN_STALE_H=0` means "don't trap me" — it must never mean "block
    forever". A non-finite bound is no bound at all, same verdict."""
    run_dir = tmp_path / "command-runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    sid = "s_staleh_" + value
    (run_dir / f"{sid}.json").write_text(json.dumps(_running_record()))
    env = {
        **os.environ,
        "FAKE_FAILS": "",
        "COMMAND_RUN_DIR": str(run_dir),
        "COMMAND_RUN_STALE_H": value,
    }
    proc = subprocess.run(
        [sys.executable, str(_HOOK)],
        input=json.dumps({"session_id": sid, "cwd": str(fake_project), "hook_event_name": "Stop"}),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    Path(hook.tempfile.gettempdir()).joinpath(f"fabrik-gate-stop-{sid}.attempts").unlink(
        missing_ok=True
    )
    assert proc.stdout.strip() == "", f"STALE_H={value}: {proc.stdout}"


# --- F-R4 (adjacent, declared): tmp-path helpers must sanitize the session id --


def test_tmp_path_helpers_sanitize_a_hostile_session_id() -> None:
    """A `/`-containing sid made _counter_path/_baseline_path escape the tmp dir;
    the resulting OSError hit the outermost except and failed the ENTIRE hook open,
    silently disabling all five causes."""
    sid = "a/b/../c"
    for path in (hook._counter_path(sid), hook._baseline_path(sid)):
        assert path.parent == Path(hook.tempfile.gettempdir()), path
        assert "/" not in path.name.replace(str(path.parent), ""), path


def test_tmp_path_helpers_keep_plain_ids_stable() -> None:
    # Existing sessions' files must not be renamed by this change.
    plain = "0198f2c1-4a7b-7e31-9a2c-1f3d5b7e9c11"
    assert hook._counter_path(plain).name == f"fabrik-gate-stop-{plain}.attempts"
    assert hook._baseline_path(plain).name == f"fabrik-gate-baseline-{plain}.json"


def test_distinct_hostile_ids_get_distinct_tmp_files() -> None:
    assert hook._counter_path("a.b") != hook._counter_path("a b")
    assert hook._baseline_path("a.b") != hook._baseline_path("a b")
