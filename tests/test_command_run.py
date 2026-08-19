"""Tests for the COMMAND RUN-RECORD protocol (``scripts/command_run.py``).

Highest-risk behaviours (one test per user-observable behaviour):
- the pinned ``RUN:`` line's EXACT format (agents paste it verbatim into every reply)
- idle / corrupt / unwritable state is SILENT and never wedges an agent
- the class ledger persists across rounds; only a clean sweep retires a class
- the TERMINAL verdict fires exactly on all-swept + 0 findings
- the NON-CONVERGENCE warning fires on an oscillating series, never on a converging one
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "command_run.py"
_HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "final_gate_stop.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    d = tmp_path / "command-runs"
    d.mkdir()
    return d


def _cr(run_dir: Path, *args: str, sid: str = "s1") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=30,
        env={
            "PATH": "/usr/bin:/bin",
            "COMMAND_RUN_DIR": str(run_dir),
            "CLAUDE_SESSION_ID": sid,
        },
    )


def _start(run_dir: Path, **kw: str) -> None:
    _cr(run_dir, "start", "--command", "fabrik-probe", "--phases", "5",
        "--terminal", "found:0 no-op round", **kw)


def _rec(run_dir: Path, sid: str = "s1") -> dict:
    return json.loads(_cr(run_dir, "status", "--json", sid=sid).stdout)


# --- the pinned line ----------------------------------------------------------


def test_line_exact_format(run_dir: Path) -> None:
    """The pinned line is a CONTRACT string — agents reproduce it verbatim."""
    _start(run_dir)
    _cr(run_dir, "step", "--phase", "2", "--title", "Independent finders")
    for _ in range(3):
        _cr(run_dir, "round", "--findings", "1")
    out = _cr(run_dir, "line").stdout.rstrip("\n")
    assert out == (
        "RUN: /fabrik-probe · phase 2/5 (Independent finders) · round 3 "
        "· terminal: found:0 no-op round"
    ), out


def test_line_omits_round_segment_before_any_round(run_dir: Path) -> None:
    _start(run_dir)
    _cr(run_dir, "step", "--phase", "1", "--title", "Establish scope")
    out = _cr(run_dir, "line").stdout.rstrip("\n")
    assert "· round" not in out, out
    assert out.startswith("RUN: /fabrik-probe · phase 1/5 (Establish scope)"), out


def test_command_name_normalises_leading_slash(run_dir: Path) -> None:
    _cr(run_dir, "start", "--command", "/fabrik-docs-review", "--phases", "4")
    assert _cr(run_dir, "line").stdout.startswith("RUN: /fabrik-docs-review · phase 1/4")


# --- idle / corrupt / unwritable: silent, never raise -------------------------


def test_idle_line_is_silent(run_dir: Path) -> None:
    p = _cr(run_dir, "line")
    assert p.stdout == "" and p.returncode == 0, (p.stdout, p.returncode)


def test_idle_status_is_empty_json(run_dir: Path) -> None:
    p = _cr(run_dir, "status", "--json")
    assert p.returncode == 0
    assert json.loads(p.stdout) == {}


def test_corrupt_record_line_and_status_stay_silent(run_dir: Path) -> None:
    (run_dir / "s1.json").write_text("{not json at all")
    p_line = _cr(run_dir, "line")
    p_status = _cr(run_dir, "status", "--json")
    assert p_line.returncode == 0 and p_line.stdout == "", p_line
    assert p_status.returncode == 0 and json.loads(p_status.stdout) == {}, p_status


def test_unwritable_state_dir_fails_soft(tmp_path: Path) -> None:
    """A file where the dir should be → mkdir raises. The agent must not be wedged."""
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    bad = blocker / "nested"
    assert _cr(bad, "start", "--command", "fabrik-probe", "--phases", "5").returncode == 0
    p = _cr(bad, "line")
    assert p.returncode == 0 and p.stdout == "", p


# --- terminal states ----------------------------------------------------------


def test_done_clears_the_pinned_line(run_dir: Path) -> None:
    _start(run_dir)
    _cr(run_dir, "done", "--command", "fabrik-probe", "--evidence", "found: 0 on round 4")
    assert _cr(run_dir, "line").stdout == ""
    assert _rec(run_dir)["state"] == "done"


def test_blocked_clears_the_pinned_line(run_dir: Path) -> None:
    _start(run_dir)
    _cr(run_dir, "blocked", "--command", "fabrik-probe", "--reason", "missing infra — no DB")
    assert _cr(run_dir, "line").stdout == ""
    rec = _rec(run_dir)
    assert rec["state"] == "blocked" and "missing infra" in rec["blocked_reason"]


# --- F-R1: closing a run REQUIRES naming it (the defect this design prevents) --


def _start_nested(run_dir: Path) -> None:
    """A plan execution at phase 2/5 with a /fabrik-probe nested inside it."""
    _cr(run_dir, "start", "--command", "fabrik-execute-plan", "--phases", "5",
        "--terminal", "every phase EXECUTED")
    _cr(run_dir, "step", "--phase", "2", "--title", "Phase B")
    _cr(run_dir, "start", "--command", "fabrik-probe", "--phases", "5",
        "--terminal", "found:0 no-op round")


def test_nested_done_restores_and_reprints_the_parent_line(run_dir: Path) -> None:
    _start_nested(run_dir)
    out = _cr(run_dir, "done", "--command", "fabrik-probe", "--evidence", "round 3 found: 0").stdout
    assert "RUN: /fabrik-execute-plan · phase 2/5 (Phase B)" in out, out
    assert _rec(run_dir)["state"] == "running"
    assert _rec(run_dir)["command"] == "fabrik-execute-plan"


def test_duplicate_done_cannot_close_the_restored_parent(run_dir: Path) -> None:
    """THE probe: a retried/duplicated `done` must not close /fabrik-execute-plan at 2/5,
    silencing the pinned line and disarming the hook for the remaining 3 phases."""
    _start_nested(run_dir)
    _cr(run_dir, "done", "--command", "fabrik-probe", "--evidence", "round 3 found: 0")
    dup = _cr(run_dir, "done", "--command", "fabrik-probe", "--evidence", "round 3 found: 0")
    assert dup.returncode == 1, dup
    assert "fabrik-execute-plan" in (dup.stdout + dup.stderr), dup
    assert "fabrik-probe" in (dup.stdout + dup.stderr), dup
    assert _rec(run_dir)["state"] == "running", "the parent must still be live"
    assert _cr(run_dir, "line").stdout.startswith("RUN: /fabrik-execute-plan · phase 2/5")


def test_done_refuses_a_command_that_is_not_the_live_run(run_dir: Path) -> None:
    _start(run_dir)
    p = _cr(run_dir, "done", "--command", "fabrik-docs-review", "--evidence", "x")
    assert p.returncode == 1, p
    both = p.stdout + p.stderr
    assert "fabrik-probe" in both and "fabrik-docs-review" in both, both
    assert _rec(run_dir)["state"] == "running"


def test_blocked_refuses_a_command_that_is_not_the_live_run(run_dir: Path) -> None:
    _start(run_dir)
    p = _cr(run_dir, "blocked", "--command", "fabrik-docs-review", "--reason", "missing infra")
    assert p.returncode == 1, p
    assert _rec(run_dir)["state"] == "running"


def test_double_close_of_a_top_level_run_is_a_warned_noop(run_dir: Path) -> None:
    _start(run_dir)
    _cr(run_dir, "done", "--command", "fabrik-probe", "--evidence", "round 4 found: 0")
    again = _cr(run_dir, "done", "--command", "fabrik-probe", "--evidence", "round 4 found: 0")
    assert again.returncode == 0, again
    assert "already" in (again.stdout + again.stderr).lower(), again
    rec = _rec(run_dir)
    assert rec["state"] == "done" and rec["evidence"] == "round 4 found: 0"


# --- F-R3: the ledger's read-modify-write must be locked ---------------------


def test_concurrent_rounds_are_never_lost(run_dir: Path) -> None:
    """Subagents can share the parent's CLAUDE_SESSION_ID — an unlocked
    read-modify-write silently dropped 14 of 20 classes (probe-measured)."""
    _start(run_dir)
    n = 20
    procs = [
        subprocess.Popen(
            [sys.executable, str(_SCRIPT), "round", "--findings", "1",
             "--classes-new", f"c{i}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={"PATH": "/usr/bin:/bin", "COMMAND_RUN_DIR": str(run_dir),
                 "CLAUDE_SESSION_ID": "s1"},
        )
        for i in range(n)
    ]
    for p in procs:
        p.wait(timeout=60)
    rec = _rec(run_dir)
    assert len(rec["rounds"]) == n, f"lost rounds: {len(rec['rounds'])}/{n}"
    assert set(rec["classes"]) == {f"c{i}" for i in range(n)}, rec["classes"]
    assert [r["n"] for r in rec["rounds"]] == list(range(1, n + 1)), "round numbering must be dense"


# --- F-R4: distinct session ids must never collide onto one record -----------


def test_distinct_session_ids_never_share_a_record(run_dir: Path) -> None:
    """`abc.xyz` and `abc xyz` both sanitize to `abc_xyz` — an innocent session
    would inherit (and be blocked by) another session's run."""
    _cr(run_dir, "start", "--command", "fabrik-probe", "--phases", "5", sid="abc.xyz")
    assert _cr(run_dir, "line", sid="abc.xyz").stdout.startswith("RUN: /fabrik-probe")
    assert _cr(run_dir, "line", sid="abc xyz").stdout == "", "a different session must be idle"


def test_ordinary_session_ids_keep_their_plain_filename(run_dir: Path) -> None:
    """uuid-shaped ids are unchanged by sanitization → no hash suffix, no churn."""
    cr = _load("command_run_mod", _SCRIPT)
    plain = "0198f2c1-4a7b-7e31-9a2c-1f3d5b7e9c11"
    assert cr._safe_sid(plain) == plain


def test_hook_and_script_agree_on_every_record_filename() -> None:
    """The hook duplicates the resolver; a divergence silently disarms the 5th cause."""
    cr = _load("command_run_mod2", _SCRIPT)
    hook = _load("final_gate_stop_mod", _HOOK)
    for sid in ["plain-uuid-123", "abc.xyz", "abc xyz", "a/b", "", "nosession", "üñî", "x" * 80]:
        assert cr._safe_sid(sid) == hook._safe_sid(sid), sid


# --- the class ledger (Stage B) ----------------------------------------------


def test_class_ledger_persists_and_only_a_clean_sweep_retires(run_dir: Path) -> None:
    _start(run_dir)
    _cr(run_dir, "round", "--findings", "5", "--classes-new", "auth,concurrency")
    _cr(run_dir, "round", "--findings", "3", "--classes-swept", "auth")
    rec = json.loads(_cr(run_dir, "status", "--json").stdout)
    assert rec["classes"] == {"auth": "clean", "concurrency": "open"}, rec["classes"]
    # a later round that finds a NEW defect in a retired class re-opens it
    _cr(run_dir, "round", "--findings", "2", "--classes-new", "auth")
    assert json.loads(_cr(run_dir, "status", "--json").stdout)["classes"]["auth"] == "open"


def test_terminal_verdict_fires_on_all_swept_and_zero_findings(run_dir: Path) -> None:
    _start(run_dir)
    _cr(run_dir, "round", "--findings", "4", "--classes-new", "auth,concurrency")
    mid = _cr(run_dir, "round", "--findings", "1", "--classes-swept", "auth")
    assert "TERMINAL" not in mid.stdout, mid.stdout  # concurrency still open
    partial = _cr(run_dir, "round", "--findings", "2", "--classes-swept", "concurrency")
    assert "TERMINAL" not in partial.stdout, partial.stdout  # swept, but findings > 0
    final = _cr(run_dir, "round", "--findings", "0", "--classes-swept", "auth,concurrency")
    assert "TERMINAL" in final.stdout, final.stdout
    # The hint must be RUNNABLE, not merely present: F-R1 made --command required, so a
    # hint of the bare `done --evidence` form exits 2 at exactly the moment an agent is
    # trying to close its run correctly. Pin the full form, with the live command named.
    assert "done --command fabrik-probe --evidence" in final.stdout, final.stdout


def test_terminal_verdict_needs_a_non_empty_ledger(run_dir: Path) -> None:
    """A round with 0 findings and NO declared classes swept nothing — not terminal."""
    _start(run_dir)
    out = _cr(run_dir, "round", "--findings", "0").stdout
    assert "TERMINAL" not in out, out


def test_zero_findings_with_a_still_open_class_is_not_terminal(run_dir: Path) -> None:
    """F-R5: dropping `not open_c` survived the whole suite — nothing paired a
    0-findings round with an unswept class, which is the ledger's whole point."""
    _start(run_dir)
    _cr(run_dir, "round", "--findings", "4", "--classes-new", "auth,concurrency")
    out = _cr(run_dir, "round", "--findings", "0", "--classes-swept", "auth").stdout
    assert "TERMINAL" not in out, out
    assert _rec(run_dir)["classes"]["concurrency"] == "open"


# --- the non-convergence detector (the 30-round fix) -------------------------


def test_non_convergence_warning_fires_on_an_oscillating_series(run_dir: Path) -> None:
    _start(run_dir)
    outs = [_cr(run_dir, "round", "--findings", str(n)).stdout for n in (43, 11, 30, 13, 22)]
    assert all("NON-CONVERGENCE" not in o for o in outs[:4]), outs[:4]
    last = outs[4]
    assert "NON-CONVERGENCE" in last, last
    assert "30 → 13 → 22" in last, last
    assert "RE-SWEEP" in last.upper(), last


def test_terminal_round_is_never_scolded_for_non_convergence(run_dir: Path) -> None:
    """A no-op round CLOSES the loop — telling it to keep sweeping is self-contradictory.

    Live smoke: after 43,11,30,13,22 the closing 0-findings round printed the TERMINAL
    verdict AND the oscillation warning, because 13 → 22 → 0 is not non-increasing.
    """
    _start(run_dir)
    _cr(run_dir, "round", "--findings", "43", "--classes-new", "auth,concurrency")
    for n in (11, 30, 13, 22):
        _cr(run_dir, "round", "--findings", str(n))
    final = _cr(run_dir, "round", "--findings", "0", "--classes-swept", "auth,concurrency").stdout
    assert "TERMINAL" in final, final
    assert "NON-CONVERGENCE" not in final, final


def test_no_warning_on_a_converging_series(run_dir: Path) -> None:
    _start(run_dir)
    outs = [_cr(run_dir, "round", "--findings", str(n)).stdout for n in (5, 3, 0)]
    assert all("NON-CONVERGENCE" not in o for o in outs), outs


def test_no_warning_while_still_non_increasing_past_round_five(run_dir: Path) -> None:
    _start(run_dir)
    outs = [_cr(run_dir, "round", "--findings", str(n)).stdout for n in (40, 30, 20, 10, 5, 0)]
    assert all("NON-CONVERGENCE" not in o for o in outs), outs


def test_review_done_refused_without_a_persisted_report(tmp_path, monkeypatch):
    """Round-29 (mega-enforcement loop): the subject-sniff was retired on the claim that THIS
    record enforces artifact emission — and the claim was then proven false (`done` accepted
    any evidence string). Now mechanically true: a review's done needs a report on disk."""
    import os
    import subprocess
    import sys
    env = dict(os.environ, COMMAND_RUN_DIR=str(tmp_path / "runs"))
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, timeout=15)
    (repo / "x.txt").write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, timeout=15)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
                   cwd=repo, check=True, timeout=15)
    script = "/opt/fabrik/scripts/command_run.py"
    subprocess.run([sys.executable, script, "start", "--command", "fabrik-review",
                    "--phases", "3", "--terminal", "t"], cwd=repo, env=env, check=True, timeout=15)
    r = subprocess.run([sys.executable, script, "done", "--command", "fabrik-review",
                        "--evidence", "reviewed, all clean"],
                       cwd=repo, env=env, capture_output=True, text=True, timeout=15)
    assert r.returncode == 1, "done closed a review run with NO report anywhere"
    assert "persisted report" in r.stdout
    # writing the report unlocks the close
    (repo / "docs/development/reviews").mkdir(parents=True)
    (repo / "docs/development/reviews/2026-08-19-x-review.md").write_text("# r\n")
    r2 = subprocess.run([sys.executable, script, "done", "--command", "fabrik-review",
                         "--evidence", "report written"],
                        cwd=repo, env=env, capture_output=True, text=True, timeout=15)
    assert r2.returncode == 0, r2.stdout + r2.stderr


def test_review_done_pins_cwd_to_the_repo_recorded_at_start(tmp_path):
    """Round-31: no cwd pinning — a wrong repo's dirt passed, a subdir invocation false-refused."""
    import os
    import subprocess
    import sys
    env = dict(os.environ, COMMAND_RUN_DIR=str(tmp_path / "runs"))
    repo_a = tmp_path / "a"
    repo_b = tmp_path / "b"
    for r in (repo_a, repo_b):
        r.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=r, check=True, timeout=15)
    (repo_b / "docs/development/reviews").mkdir(parents=True)
    (repo_b / "docs/development/reviews/old-review.md").write_text("# unrelated dirt\n")
    script = "/opt/fabrik/scripts/command_run.py"
    subprocess.run([sys.executable, script, "start", "--command", "fabrik-review",
                    "--phases", "3", "--terminal", "t"], cwd=repo_a, env=env, check=True, timeout=15)
    # close from repo B (wrong repo, dirty reviews/): must still refuse — the check runs in A
    r = subprocess.run([sys.executable, script, "done", "--command", "fabrik-review",
                        "--evidence", "e"], cwd=repo_b, env=env,
                       capture_output=True, text=True, timeout=15)
    assert r.returncode == 1, "wrong-repo dirt satisfied the artifact check"
    # write the real report in A, close from a SUBDIR of A: must succeed
    (repo_a / "docs/development/reviews").mkdir(parents=True)
    (repo_a / "docs/development/reviews/2026-08-19-a-review.md").write_text("# r\n")
    sub = repo_a / "scripts"
    sub.mkdir()
    r2 = subprocess.run([sys.executable, script, "done", "--command", "fabrik-review",
                         "--evidence", "e"], cwd=sub, env=env,
                        capture_output=True, text=True, timeout=15)
    assert r2.returncode == 0, r2.stdout + r2.stderr


def test_review_done_rejects_deletions_and_stale_files_as_artifacts(tmp_path):
    """Round-31: a git rm of an old report — or a file predating the run — satisfied the check."""
    import os
    import subprocess
    import sys
    import time as _t
    env = dict(os.environ, COMMAND_RUN_DIR=str(tmp_path / "runs"))
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, timeout=15)
    d = repo / "docs/development/reviews"
    d.mkdir(parents=True)
    old = d / "old-review.md"
    old.write_text("# old\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, timeout=15)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
                   cwd=repo, check=True, timeout=15)
    past = _t.time() - 3600
    os.utime(old, (past, past))
    _t.sleep(1.1)  # run-binding is second-granular: the pre-run commit must be < started_at
    script = "/opt/fabrik/scripts/command_run.py"
    subprocess.run([sys.executable, script, "start", "--command", "fabrik-review",
                    "--phases", "3", "--terminal", "t"], cwd=repo, env=env, check=True, timeout=15)
    subprocess.run(["git", "rm", "-q", "docs/development/reviews/old-review.md"],
                   cwd=repo, check=True, timeout=15)
    r = subprocess.run([sys.executable, script, "done", "--command", "fabrik-review",
                        "--evidence", "e"], cwd=repo, env=env,
                       capture_output=True, text=True, timeout=15)
    assert r.returncode == 1, "a deletion (of a pre-run file) satisfied the artifact check"
