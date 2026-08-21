"""Tests for the COMMAND RUN-RECORD protocol (``scripts/command_run.py``).

Highest-risk behaviours (one test per user-observable behaviour):
- the pinned ``RUN:`` line's EXACT format (agents paste it verbatim into every reply)
- idle / corrupt / unwritable state is SILENT and never wedges an agent
- the class ledger persists across rounds; only a clean sweep retires a class
- the TERMINAL verdict fires exactly on all-swept + 0 findings
- the NON-CONVERGENCE warning fires on an oscillating series, never on a converging one
"""

from __future__ import annotations

import datetime as dt
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


def _cr(
    run_dir: Path,
    *args: str,
    sid: str | None = "s1",
    cwd: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": "/usr/bin:/bin",
        "COMMAND_RUN_DIR": str(run_dir),
        # Never let a test emit into the operator's real event store.
        "KAIZEN_EVENTS_DIR": str(_events_dir(run_dir)),
    }
    if sid is not None:
        env["CLAUDE_SESSION_ID"] = sid
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(cwd) if cwd else None,
        env=env,
    )


#: The fixture command name. It MUST NOT be one of the names `_close` special-cases
#: (`fabrik-review`, `fabrik-repo-review` — scripts/command_run.py `_close`), whose `done`
#: additionally requires a persisted `docs/development/reviews/*.md` from `git status`/HEAD.
#: Using a real review command here made the suite a TIME BOMB: it passed while HEAD
#: happened to be a commit that touched a review report, and went red the moment a commit
#: that did not became HEAD. Only `test_review_done_refused_without_a_persisted_report`,
#: which exists to test that guard, may name a special-cased command.
_PROBE = "fabrik-probe"


def _start(run_dir: Path, **kw: str) -> None:
    _cr(run_dir, "start", "--command", _PROBE, "--phases", "5",
        "--terminal", "found:0 no-op round", **kw)


def _rec(run_dir: Path, sid: str = "s1") -> dict:
    return json.loads(_cr(run_dir, "status", "--json", sid=sid).stdout)


# --- kaizen event-stream helpers ---------------------------------------------


def _events_dir(run_dir: Path) -> Path:
    return run_dir.parent / "events"


def _events(run_dir: Path, stem: str) -> list[dict]:
    path = _events_dir(run_dir) / f"{stem}.jsonl"
    if not path.is_file():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _iso(offset_s: float = 0.0) -> str:
    return (dt.datetime.now(dt.UTC) + dt.timedelta(seconds=offset_s)).isoformat(
        timespec="milliseconds"
    )


def _seed_event(
    run_dir: Path,
    stem: str,
    *,
    sid: str | None = None,
    cwd: Path | str | None = None,
    project: str = "",
    ts: str | None = None,
    event: str = "session_start",
) -> None:
    d = _events_dir(run_dir)
    d.mkdir(parents=True, exist_ok=True)
    row: dict = {
        "schema": 1,
        "ts": ts or _iso(),
        "sid": sid or stem,
        "sid_source": "env",
        "event": event,
        "exposure": {"project": project or "unknown"},
    }
    if cwd is not None:
        row["cwd"] = str(Path(cwd).resolve())
    with open(d / f"{stem}.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


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
                 "KAIZEN_EVENTS_DIR": str(_events_dir(run_dir)),
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
    env = dict(os.environ, COMMAND_RUN_DIR=str(tmp_path / "runs"),
               KAIZEN_EVENTS_DIR=str(tmp_path / "events"))
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


def test_stale_but_present_report_is_refused_in_isolation(tmp_path):
    """Round-33: the staleness branch was only ever tested confounded with deletion — a
    stale-but-PRESENT untracked file must be refused on mtime alone."""
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
    stale = d / "stale-review.md"
    stale.write_text("# stale but present\n")
    past = _t.time() - 3600
    os.utime(stale, (past, past))
    script = "/opt/fabrik/scripts/command_run.py"
    subprocess.run([sys.executable, script, "start", "--command", "fabrik-review",
                    "--phases", "3", "--terminal", "t"], cwd=repo, env=env, check=True, timeout=15)
    r = subprocess.run([sys.executable, script, "done", "--command", "fabrik-review",
                        "--evidence", "e"], cwd=repo, env=env,
                       capture_output=True, text=True, timeout=15)
    assert r.returncode == 1, "a stale-but-present file satisfied the check on presence alone"


def test_review_started_outside_any_repo_refuses_done(tmp_path):
    """Round-33: repo_root='' fell back to the CLOSE cwd — the wrong-repo hole reborn.
    Unverifiable must refuse, not guess."""
    import os
    import subprocess
    import sys
    env = dict(os.environ, COMMAND_RUN_DIR=str(tmp_path / "runs"))
    norepo = tmp_path / "norepo"
    norepo.mkdir()
    dirty = tmp_path / "dirty"
    dirty.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=dirty, check=True, timeout=15)
    (dirty / "docs/development/reviews").mkdir(parents=True)
    (dirty / "docs/development/reviews/x-review.md").write_text("# unrelated\n")
    script = "/opt/fabrik/scripts/command_run.py"
    subprocess.run([sys.executable, script, "start", "--command", "fabrik-review",
                    "--phases", "3", "--terminal", "t"], cwd=norepo, env=env, check=True, timeout=15)
    r = subprocess.run([sys.executable, script, "done", "--command", "fabrik-review",
                        "--evidence", "e"], cwd=dirty, env=env,
                       capture_output=True, text=True, timeout=15)
    assert r.returncode == 1, "a rootless record closed against the close-cwd's dirt"
    assert "no repo_root" in r.stdout


def test_blocked_works_on_a_rootless_record(tmp_path):
    """Round-37 finding 4: the only true exit for a rootless record must STAY open — a
    refactor moving the artifact check above the done/blocked branch would strand it."""
    import os
    import subprocess
    import sys
    env = dict(os.environ, COMMAND_RUN_DIR=str(tmp_path / "runs"))
    norepo = tmp_path / "norepo"
    norepo.mkdir()
    script = "/opt/fabrik/scripts/command_run.py"
    subprocess.run([sys.executable, script, "start", "--command", "fabrik-review",
                    "--phases", "3", "--terminal", "t"], cwd=norepo, env=env, check=True, timeout=15)
    r = subprocess.run([sys.executable, script, "blocked", "--command", "fabrik-review",
                        "--reason", "rootless-record"], cwd=norepo, env=env,
                       capture_output=True, text=True, timeout=15)
    assert r.returncode == 0, f"blocked no longer closes a rootless record: {r.stdout}{r.stderr}"
# --- T03: kaizen lifecycle events --------------------------------------------
#
# The record is the Stop hook's 5th cause and is fleet-synced, so the events are
# STRICTLY additive: emitted after `save()` returns, outside the record lock, each
# call wrapped. The tests below pin both halves — the events land, AND nothing an
# existing consumer reads (the `state` field, the pinned line, the record's shape)
# moved a byte.


def test_start_emits_run_open(run_dir: Path) -> None:
    _start(run_dir)
    rows = _events(run_dir, "s1")
    assert [r["event"] for r in rows] == ["run_open"], rows
    row = rows[0]
    assert row["command"] == "fabrik-probe", row
    assert row["phases"] == 5, row
    assert row["terminal"] == "found:0 no-op round", row
    assert row["sid"] == "s1" and row["sid_source"] == "env", row
    assert isinstance(row.get("exposure"), dict), row


def test_step_and_round_emit_their_events(run_dir: Path) -> None:
    _start(run_dir)
    _cr(run_dir, "step", "--phase", "2", "--title", "Independent finders")
    _cr(run_dir, "round", "--findings", "3", "--classes-swept", "auth", "--classes-new", "races")
    rows = _events(run_dir, "s1")
    assert [r["event"] for r in rows] == ["run_open", "phase", "round"], rows
    assert rows[1]["n"] == 2 and rows[1]["title"] == "Independent finders", rows[1]
    assert rows[2]["findings"] == 3, rows[2]
    assert rows[2]["classes_swept"] == ["auth"], rows[2]
    assert rows[2]["classes_new"] == ["races"], rows[2]


def test_done_emits_run_close_with_a_verdict_and_evidence_hash(run_dir: Path) -> None:
    _start(run_dir)
    _cr(run_dir, "done", "--command", "fabrik-probe", "--evidence", "round 4 found: 0")
    row = _events(run_dir, "s1")[-1]
    assert row["event"] == "run_close", row
    assert row["verdict"] == "done", row
    assert row["command"] == "fabrik-probe", row
    assert row["closed_by"] == "agent", row
    # a HASH of the evidence, never the evidence prose itself
    assert isinstance(row["evidence_hash"], str) and len(row["evidence_hash"]) >= 8, row
    assert "found: 0" not in json.dumps(row), row


def test_blocked_emits_run_close_with_the_blocked_verdict(run_dir: Path) -> None:
    _start(run_dir)
    _cr(run_dir, "blocked", "--command", "fabrik-probe", "--reason", "missing infra — no DB")
    row = _events(run_dir, "s1")[-1]
    assert row["event"] == "run_close" and row["verdict"] == "blocked", row
    assert row["closed_by"] == "agent", row


def test_closed_by_is_written_on_the_record(run_dir: Path) -> None:
    """`closed_by` is additive — absent while running, `agent` once an agent closes it."""
    _start(run_dir)
    assert "closed_by" not in _rec(run_dir), _rec(run_dir)
    _cr(run_dir, "done", "--command", "fabrik-probe", "--evidence", "x")
    rec = _rec(run_dir)
    assert rec["closed_by"] == "agent" and rec["state"] == "done", rec


def test_a_refused_close_mutates_nothing_and_emits_nothing(run_dir: Path) -> None:
    _start(run_dir)
    before = len(_events(run_dir, "s1"))
    assert _cr(run_dir, "done", "--command", "fabrik-docs-review", "--evidence", "x").returncode == 1
    assert len(_events(run_dir, "s1")) == before, "a refused close is not a mutation"
    assert _rec(run_dir)["state"] == "running"


def test_readers_emit_nothing(run_dir: Path) -> None:
    _start(run_dir)
    before = len(_events(run_dir, "s1"))
    _cr(run_dir, "line")
    _cr(run_dir, "status", "--json")
    assert len(_events(run_dir, "s1")) == before, "line/status are read-only"


def test_record_shape_and_pinned_line_are_unchanged_by_events(run_dir: Path) -> None:
    """The Stop hook's contract: `state` semantics + the pinned line stay byte-stable."""
    _start(run_dir)
    _cr(run_dir, "step", "--phase", "2", "--title", "Independent finders")
    rec = _rec(run_dir)
    # Exact, not a subset: a field silently appearing in a fleet-synced record that the
    # Stop hook and every project's copy also read is exactly what this pins. `event_seq`
    # is the one T03 addition, and it is additive — no existing consumer reads it.
    # `started_epoch` + `repo_root` are the review-guard's (mega-enforcement round-31/33).
    assert set(rec) == {
        "session_id", "command", "phases", "phase", "phase_title", "terminal",
        "state", "started_at", "started_epoch", "repo_root", "rounds", "classes",
        "stack", "updated_at", "updated_ts", "event_seq",
    }, sorted(rec)
    assert rec["state"] == "running"
    assert _cr(run_dir, "line").stdout.rstrip("\n") == (
        "RUN: /fabrik-probe · phase 2/5 (Independent finders) · terminal: found:0 no-op round"
    )


def _shim(tmp_path: Path, name: str, body: str) -> dict[str, str]:
    """A `kaizen_events` stand-in earlier on sys.path than the real one."""
    d = tmp_path / name
    d.mkdir()
    (d / "kaizen_events.py").write_text(body, encoding="utf-8")
    return {"PYTHONPATH": str(d)}


def test_a_raising_emitter_never_corrupts_a_record(run_dir: Path, tmp_path: Path) -> None:
    """The emitter is a SENSOR: it may fail, and the record must not notice."""
    boom = _shim(
        tmp_path,
        "boom",
        "UNKNOWN = 'unknown'\n"
        "def events_dir():\n    raise RuntimeError('boom')\n"
        "def emit(*a, **k):\n    raise RuntimeError('boom')\n",
    )
    for argv in (
        ["start", "--command", "fabrik-probe", "--phases", "5", "--terminal", "t"],
        ["step", "--phase", "2", "--title", "Independent finders"],
        ["round", "--findings", "0", "--classes-swept", "auth"],
    ):
        p = _cr(run_dir, *argv, extra_env=boom)
        assert p.returncode == 0, p.stdout + p.stderr
    rec = _rec(run_dir)
    assert rec["state"] == "running" and rec["phase"] == 2, rec
    assert rec["classes"] == {"auth": "clean"} and len(rec["rounds"]) == 1, rec
    assert _cr(run_dir, "line", extra_env=boom).stdout.startswith(
        "RUN: /fabrik-probe · phase 2/5 (Independent finders) · round 1"
    )
    p = _cr(run_dir, "done", "--command", "fabrik-probe", "--evidence", "x", extra_env=boom)
    assert p.returncode == 0, p.stdout + p.stderr
    assert _rec(run_dir)["state"] == "done"


def test_an_absent_kaizen_module_behaves_exactly_as_today(run_dir: Path, tmp_path: Path) -> None:
    gone = _shim(tmp_path, "gone", "raise ImportError('not synced to this project yet')\n")
    assert _cr(run_dir, "start", "--command", "fabrik-probe", "--phases", "5",
               "--terminal", "t", extra_env=gone).returncode == 0
    assert _rec(run_dir)["state"] == "running"
    assert _events(run_dir, "s1") == []


# --- T03: sid honesty — the `nosession` collision made MEASURABLE -------------


def test_nosession_events_carry_sid_source_none(run_dir: Path) -> None:
    """An empty CLAUDE_SESSION_ID (every Bash-tool shell) must not be laundered into
    an attributed session: the record still works, the EVENT says `none`."""
    assert _cr(run_dir, "start", "--command", "fabrik-probe", "--phases", "5",
               "--terminal", "t", sid=None).returncode == 0
    assert (run_dir / "nosession.json").is_file(), "the record naming must not move"
    rows = _events(run_dir, "unknown")
    assert [r["event"] for r in rows] == ["run_open"], rows
    assert rows[0]["sid_source"] == "none", rows[0]
    assert rows[0]["sid"] == "unknown", rows[0]


def test_adopt_sid_adopts_a_single_candidate(run_dir: Path, tmp_path: Path) -> None:
    """Before a record exists the window is the WHOLE store — a session that named this
    cwd an hour ago (its `session_start`, which always predates the run) is a candidate.

    Anchoring `start` on the record it is itself writing made this race the clock: the
    candidate was included only when both landed inside one second-truncated `started_at`.
    """
    work = tmp_path / "work"
    work.mkdir()
    _seed_event(run_dir, "sessA", cwd=work, ts=_iso(-3600))
    p = _cr(run_dir, "start", "--command", "fabrik-probe", "--phases", "5", "--terminal", "t",
            "--adopt-sid", sid=None, cwd=work)
    assert p.returncode == 0, p.stdout + p.stderr
    assert (run_dir / "nosession.json").is_file(), "adoption must NOT rename the record"
    rows = _events(run_dir, "sessA")
    assert [r["event"] for r in rows] == ["session_start", "run_open"], (rows, p.stderr)
    assert rows[1]["sid"] == "sessA", rows[1]
    assert rows[1]["sid_source"] == "join", "an adopted sid must be labelled, never laundered"
    assert _events(run_dir, "unknown") == []


def test_adopt_sid_refuses_an_ambiguous_join(run_dir: Path, tmp_path: Path) -> None:
    """Deterministic-join-or-nothing: two candidates means the event stays `unknown`."""
    work = tmp_path / "work"
    work.mkdir()
    _seed_event(run_dir, "sessA", cwd=work)
    _seed_event(run_dir, "sessB", cwd=work)
    p = _cr(run_dir, "start", "--command", "fabrik-probe", "--phases", "5", "--terminal", "t",
            "--adopt-sid", sid=None, cwd=work)
    assert p.returncode == 0, p.stdout + p.stderr
    assert len(_events(run_dir, "sessA")) == 1 and len(_events(run_dir, "sessB")) == 1
    rows = _events(run_dir, "unknown")
    assert [r["event"] for r in rows] == ["run_open"], rows
    assert rows[0]["sid_source"] == "none", rows[0]


def test_adopt_sid_ignores_a_session_that_never_named_this_cwd(
    run_dir: Path, tmp_path: Path
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    _seed_event(run_dir, "sessA", cwd=work)
    _seed_event(run_dir, "sessB", cwd=other)
    _cr(run_dir, "start", "--command", "fabrik-probe", "--phases", "5", "--terminal", "t",
        "--adopt-sid", sid=None, cwd=work)
    assert [r["event"] for r in _events(run_dir, "sessA")] == ["session_start", "run_open"]
    assert len(_events(run_dir, "sessB")) == 1


def test_adopt_sid_window_starts_at_the_runs_own_start(
    run_dir: Path, tmp_path: Path
) -> None:
    """Once a run exists the window is anchored to ITS start — a session whose only
    trace of this cwd predates the run is not a candidate."""
    work = tmp_path / "work"
    work.mkdir()
    _cr(run_dir, "start", "--command", "fabrik-probe", "--phases", "5", "--terminal", "t",
        sid=None, cwd=work)
    _seed_event(run_dir, "stale", cwd=work, ts=_iso(-3600))
    _cr(run_dir, "round", "--findings", "1", "--adopt-sid", sid=None, cwd=work)
    assert len(_events(run_dir, "stale")) == 1, "a pre-run event must not adopt"
    assert [r["event"] for r in _events(run_dir, "unknown")] == ["run_open", "round"]
    # an event INSIDE the window does adopt
    _seed_event(run_dir, "live", cwd=work, ts=_iso(5))
    _cr(run_dir, "round", "--findings", "0", "--adopt-sid", sid=None, cwd=work)
    assert [r["event"] for r in _events(run_dir, "live")] == ["session_start", "round"]


def test_adopt_sid_is_ignored_when_a_real_sid_exists(
    run_dir: Path, tmp_path: Path
) -> None:
    """An honest sid always wins — the join is a fallback, never an override."""
    work = tmp_path / "work"
    work.mkdir()
    _seed_event(run_dir, "sessA", cwd=work)
    _cr(run_dir, "start", "--command", "fabrik-probe", "--phases", "5", "--terminal", "t",
        "--adopt-sid", sid="s1", cwd=work)
    assert [r["event"] for r in _events(run_dir, "s1")] == ["run_open"]
    assert len(_events(run_dir, "sessA")) == 1


# --- acceptance round: the join reads TAILS, and refuses what it cannot prove --


def _seed_bulk(run_dir: Path, stem: str, *, rows: int, other: Path, tail_cwd: Path | None) -> None:
    """A LONG session file: `rows` events naming some OTHER cwd, and — when `tail_cwd` is
    given — one final event naming it. Padded so the file exceeds the tail window."""
    d = _events_dir(run_dir)
    d.mkdir(parents=True, exist_ok=True)
    pad = "p" * 200

    def row(cwd: Path) -> str:
        return json.dumps({
            "schema": 1, "ts": _iso(), "sid": stem, "sid_source": "env", "event": "round",
            "exposure": {"project": "unknown"}, "cwd": str(cwd.resolve()), "pad": pad,
        }) + "\n"

    with open(d / f"{stem}.jsonl", "a", encoding="utf-8") as fh:
        for _ in range(rows):
            fh.write(row(other))
        if tail_cwd is not None:
            fh.write(row(tail_cwd))


def test_join_reads_the_tail_of_a_long_session_file(run_dir: Path, tmp_path: Path) -> None:
    """A head-bounded scan makes a long-lived session INVISIBLE — and invisibility here is
    not a missed adoption but the WRONG one: the second candidate vanishes and the join
    hands this run's events to somebody else's stream."""
    work, other = tmp_path / "work", tmp_path / "other"
    work.mkdir()
    other.mkdir()
    _seed_bulk(run_dir, "long", rows=5200, other=other, tail_cwd=work)
    _seed_event(run_dir, "short", cwd=work)
    p = _cr(run_dir, "start", "--command", _PROBE, "--phases", "5", "--terminal", "t",
            "--adopt-sid", sid=None, cwd=work)
    assert p.returncode == 0, p.stdout + p.stderr
    assert [r["event"] for r in _events(run_dir, "unknown")] == ["run_open"], (
        "two sessions name this cwd — the join must REFUSE, not adopt the visible one"
    )
    assert len(_events(run_dir, "short")) == 1, "the short candidate must not be adopted"


def test_join_adopts_a_candidate_only_the_tail_proves(run_dir: Path, tmp_path: Path) -> None:
    """The other half of the same fix: the tail must actually be READ, not merely bounded."""
    work, other = tmp_path / "work", tmp_path / "other"
    work.mkdir()
    other.mkdir()
    _seed_bulk(run_dir, "long", rows=5200, other=other, tail_cwd=work)
    _cr(run_dir, "start", "--command", _PROBE, "--phases", "5", "--terminal", "t",
        "--adopt-sid", sid=None, cwd=work)
    assert [r["event"] for r in _events(run_dir, "long")][-1:] == ["run_open"]
    assert _events(run_dir, "unknown") == []


def test_join_refuses_when_a_session_is_too_long_to_prove_absence(
    run_dir: Path, tmp_path: Path
) -> None:
    """Absence is only evidence when the whole file was read. A file past the tail window
    showing no match is UNPROVABLE, and unprovable resolves toward refusal."""
    work, other = tmp_path / "work", tmp_path / "other"
    work.mkdir()
    other.mkdir()
    _seed_bulk(run_dir, "long", rows=5200, other=other, tail_cwd=None)
    _seed_event(run_dir, "short", cwd=work)
    _cr(run_dir, "start", "--command", _PROBE, "--phases", "5", "--terminal", "t",
        "--adopt-sid", sid=None, cwd=work)
    assert [r["event"] for r in _events(run_dir, "unknown")] == ["run_open"], (
        "one proven candidate + one unprovable session is not a deterministic join"
    )
    assert len(_events(run_dir, "short")) == 1


def test_start_never_inherits_a_previous_runs_anchor(run_dir: Path, tmp_path: Path) -> None:
    """The start verb's window is the WHOLE store. Reading the anchor off whatever record
    happened to be lying around filters the store by a FINISHED run's clock, hiding older
    candidates and turning a two-candidate refusal into a wrong adoption."""
    work = tmp_path / "work"
    work.mkdir()
    _seed_event(run_dir, "sessA", cwd=work, ts=_iso(-3600))
    _cr(run_dir, "start", "--command", _PROBE, "--phases", "1", "--terminal", "t",
        sid=None, cwd=work)
    _cr(run_dir, "done", "--command", _PROBE, "--evidence", "x", sid=None, cwd=work)
    _seed_event(run_dir, "sessB", cwd=work, ts=_iso())
    before = len(_events(run_dir, "unknown"))
    _cr(run_dir, "start", "--command", _PROBE, "--phases", "1", "--terminal", "t",
        "--adopt-sid", sid=None, cwd=work)
    assert len(_events(run_dir, "unknown")) == before + 1, (
        "sessA predates the closed run — a stale anchor would hide it and adopt sessB"
    )
    assert len(_events(run_dir, "sessA")) == 1 and len(_events(run_dir, "sessB")) == 1


def test_session_flag_prefix_is_still_unambiguous(run_dir: Path) -> None:
    """`--session-from-events` shared the `--sess` prefix with `--session`, so argparse
    stopped accepting the abbreviation. The replacement flag may not re-collide."""
    _cr(run_dir, "start", "--command", _PROBE, "--phases", "5", "--terminal", "t")
    p = _cr(run_dir, "--sess", "s1", "line")
    assert p.returncode == 0, p.stdout + p.stderr
    assert p.stdout.startswith(f"RUN: /{_PROBE}"), (p.stdout, p.stderr)


# --- acceptance round: the stream is ORDER-FAITHFUL and self-describing -------


def test_every_event_carries_a_monotonic_seq_and_its_command(run_dir: Path) -> None:
    """Timestamps are millisecond-quantized and concurrent writers interleave, so `ts`
    cannot order a stream. `(command, seq)` can."""
    _start(run_dir)
    _cr(run_dir, "step", "--phase", "2", "--title", "T")
    _cr(run_dir, "round", "--findings", "1")
    _cr(run_dir, "done", "--command", _PROBE, "--evidence", "x")
    rows = _events(run_dir, "s1")
    assert [r["seq"] for r in rows] == [1, 2, 3, 4], rows
    assert {r["command"] for r in rows} == {_PROBE}, rows
    assert _rec(run_dir)["event_seq"] == 4


def test_seq_survives_the_concurrent_writer_scramble(run_dir: Path) -> None:
    """Concurrent `round` processes land in any order, but the seqs must be a DENSE 1..N —
    that is what makes the stream repairable after the fact."""
    _start(run_dir)
    n = 12
    procs = [
        subprocess.Popen(
            [sys.executable, str(_SCRIPT), "round", "--findings", "1", "--classes-new", f"c{i}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={"PATH": "/usr/bin:/bin", "COMMAND_RUN_DIR": str(run_dir),
                 "KAIZEN_EVENTS_DIR": str(_events_dir(run_dir)), "CLAUDE_SESSION_ID": "s1"},
        )
        for i in range(n)
    ]
    for p in procs:
        p.wait(timeout=90)
    seqs = sorted(r["seq"] for r in _events(run_dir, "s1"))
    assert seqs == list(range(1, n + 2)), seqs  # the run_open is seq 1


def test_nested_run_close_is_attributable_without_replaying_the_stack(run_dir: Path) -> None:
    """A nested close is the one event whose meaning depends on state the collector does
    not have. It must say, in the line itself, what it went back to."""
    _start_nested(run_dir)
    _cr(run_dir, "done", "--command", _PROBE, "--evidence", "round 3 found: 0")
    row = _events(run_dir, "s1")[-1]
    assert row["event"] == "run_close" and row["command"] == _PROBE, row
    assert row["resumed"] == "fabrik-execute-plan", row
    assert row["resumed_phase"] == 2, row
    assert row["resumed_rounds"] == 0, row


# --- acceptance round: in-process seams (the flush hole, the emit kwargs) -----


def _in_process(tmp_path: Path, monkeypatch, name: str):
    """command_run loaded as a module against tmp state — for the seams a subprocess
    cannot reach (an injected mid-verb exception; the kwargs handed to emit())."""
    monkeypatch.setenv("COMMAND_RUN_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.setenv("CLAUDE_SESSION_ID", "s1")
    return _load(name, _SCRIPT)


def test_an_exception_after_save_still_flushes_the_event(tmp_path: Path, monkeypatch) -> None:
    """The mutation is PERSISTED the moment save() returns. If anything in the tail after
    it raises, the record and the stream disagree forever — the event is simply missing,
    and no collector logic can invent it."""
    cr = _in_process(tmp_path, monkeypatch, "cr_flush_hole")
    assert cr.main(["start", "--command", _PROBE, "--phases", "3"]) == 0

    def _boom(rec: dict) -> str:
        raise RuntimeError("injected tail failure")

    monkeypatch.setattr(cr, "_round_report", _boom)
    assert cr.main(["round", "--findings", "2"]) == 0, "a tail bug must not wedge the agent"
    rows = [json.loads(ln) for ln in
            (tmp_path / "events" / "s1.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["event"] for r in rows] == ["run_open", "round"], rows
    assert rows[1]["findings"] == 2 and rows[1]["seq"] == 2, rows[1]


def test_flush_bounds_the_exposure_probe_and_labels_a_joined_sid(
    tmp_path: Path, monkeypatch
) -> None:
    """Two contracts on the emit call itself: the exposure probe is BOUNDED (it shells out
    to git on an agent's hot path, after the mutation is already durable), and an adopted
    sid is labelled `join`, never laundered into `explicit`."""
    cr = _in_process(tmp_path, monkeypatch, "cr_emit_kwargs")
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    calls: list[dict] = []

    class _Fake:
        UNKNOWN = "unknown"

        @staticmethod
        def events_dir() -> Path:
            return tmp_path / "events"

        @staticmethod
        def emit(event, sid=None, **kw):
            calls.append({"event": event, "sid": sid, **kw})
            return True

    monkeypatch.setattr(cr, "_kaizen", lambda: _Fake)
    (tmp_path / "events").mkdir(parents=True, exist_ok=True)
    (tmp_path / "events" / "sessA.jsonl").write_text(
        json.dumps({"schema": 1, "ts": _iso(-60), "sid": "sessA", "event": "session_start",
                    "cwd": str(Path.cwd().resolve())}) + "\n", encoding="utf-8")
    assert cr.main(["start", "--command", _PROBE, "--phases", "3", "--adopt-sid"]) == 0
    assert len(calls) == 1, calls
    assert calls[0]["sid"] == "sessA", calls[0]
    assert calls[0]["sid_source"] == "join", calls[0]
    assert calls[0]["probe_timeout_s"] == 2.0, calls[0]


def test_code_session_id_env_keys_the_record(tmp_path):
    """The nosession collision (observed live 3x, 2026-08-20): Bash-tool shells carry an
    empty CLAUDE_SESSION_ID but DO carry CLAUDE_CODE_SESSION_ID (the real session uuid the
    Stop hook keys on) — without the second candidate, every concurrent session wrote ONE
    nosession.json and sibling starts clobbered each other's live records."""
    run_dir = tmp_path / "runs"
    r = _cr(
        run_dir, "start", "--command", "fabrik-probe", "--phases", "1",
        sid=None,
        extra_env={"CLAUDE_SESSION_ID": "", "CLAUDE_CODE_SESSION_ID": "uuid-alpha"},
    )
    assert r.returncode == 0, r.stderr
    assert (run_dir / "uuid-alpha.json").exists(), "record not keyed by CLAUDE_CODE_SESSION_ID"
    assert not (run_dir / "nosession.json").exists(), "still colliding into nosession.json"


def test_session_id_precedence_and_isolation(tmp_path):
    """Precedence: explicit > CLAUDE_SESSION_ID > CLAUDE_CODE_SESSION_ID; two sessions
    with distinct code-session ids never share a record file."""
    run_dir = tmp_path / "runs"
    r = _cr(
        run_dir, "start", "--command", "fabrik-probe", "--phases", "1",
        sid="legacy-var",
        extra_env={"CLAUDE_CODE_SESSION_ID": "uuid-beta"},
    )
    assert r.returncode == 0, r.stderr
    assert (run_dir / "legacy-var.json").exists(), "CLAUDE_SESSION_ID must outrank the code var"
    for uuid in ("uuid-a", "uuid-b"):
        r = _cr(
            run_dir, "start", "--command", "fabrik-probe", "--phases", "1",
            sid=None,
            extra_env={"CLAUDE_SESSION_ID": "", "CLAUDE_CODE_SESSION_ID": uuid},
        )
        assert r.returncode == 0, r.stderr
    assert (run_dir / "uuid-a.json").exists() and (run_dir / "uuid-b.json").exists(), (
        "concurrent sessions must get distinct record files"
    )


def test_adopt_join_declines_when_code_session_id_resolves(tmp_path, monkeypatch):
    """Round-105 MEDIUM: the adopt-join gate checked only CLAUDE_SESSION_ID, so on a
    Bash-tool shell (empty legacy var, populated CLAUDE_CODE_SESSION_ID) the record landed
    under the real sid while the EVENT was join-attributed into a sibling's stream — the
    cross-session collision reopened one layer over. The gate now honors the full chain."""
    cr = _in_process(tmp_path, monkeypatch, "cr_adopt_code")
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sidA-real")
    calls: list[dict] = []

    class _Fake:
        UNKNOWN = "unknown"

        @staticmethod
        def events_dir() -> Path:
            return tmp_path / "events"

        @staticmethod
        def emit(event, sid=None, **kw):
            calls.append({"event": event, "sid": sid, **kw})
            return True

    monkeypatch.setattr(cr, "_kaizen", lambda: _Fake)
    (tmp_path / "events").mkdir(parents=True, exist_ok=True)
    (tmp_path / "events" / "sessB.jsonl").write_text(
        json.dumps({"schema": 1, "ts": _iso(-60), "sid": "sessB", "event": "session_start",
                    "cwd": str(Path.cwd().resolve())}) + "\n", encoding="utf-8")
    assert cr.main(["start", "--command", _PROBE, "--phases", "1", "--adopt-sid"]) == 0
    assert len(calls) == 1, calls
    assert calls[0]["sid_source"] != "join", calls[0]
    assert calls[0]["sid"] != "sessB", "the event was join-attributed into a sibling's stream"
