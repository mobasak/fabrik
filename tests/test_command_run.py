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
    inject_feedback: bool = True,
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
    # A close now REFUSES without a feedback verdict (scripts/command_run.py
    # `_FEEDBACK_REQUIRED_FROM`). Every test below that closes a run does so as SETUP for some
    # other assertion, so the harness supplies the verdict once rather than 60 call sites
    # repeating it — a test that is ABOUT the verdict passes its own and opts out here.
    argv = list(args)
    if inject_feedback and argv and argv[0] in ("done", "blocked", "handoff") and "--feedback" not in argv:
        argv += ["--feedback", "none — harness setup"]
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *argv],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(cwd) if cwd else None,
        env=env,
    )


def _backdate(run_dir: Path, sid: str = "s1") -> None:
    """Age a record to before `_FEEDBACK_REQUIRED_FROM` so its close is grandfathered.

    Not a convenience: it is the only way to exercise the pre-cutoff branch, and that branch is
    load-bearing — it is what keeps a peer who was already mid-run when the requirement landed
    from being trapped by a rule their dispatch never mentioned.
    """
    f = run_dir / f"{sid}.json"
    rec = json.loads(f.read_text(encoding="utf-8"))
    rec["started_at"] = "2026-08-01T00:00:00+00:00"
    f.write_text(json.dumps(rec), encoding="utf-8")


#: The fixture command name. It MUST NOT be one of the names `_close` special-cases
#: (`fabrik-review`, `fabrik-repo-review` — scripts/command_run.py `_close`), whose `done`
#: additionally requires a persisted `docs/development/reviews/*.md` from `git status`/HEAD.
#: Using a real review command here made the suite a TIME BOMB: it passed while HEAD
#: happened to be a commit that touched a review report, and went red the moment a commit
#: that did not became HEAD. Only `test_review_done_refused_without_a_persisted_report`,
#: which exists to test that guard, may name a special-cased command.
_PROBE = "fabrik-probe"


def _start(run_dir: Path, **kw: str) -> None:
    _cr(
        run_dir,
        "start",
        "--command",
        _PROBE,
        "--phases",
        "5",
        "--terminal",
        "found:0 no-op round",
        **kw,
    )


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
    _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-execute-plan",
        "--phases",
        "5",
        "--terminal",
        "every phase EXECUTED",
    )
    # These tests exercise the NESTED-DONE mechanism, not the phase-review rule
    # (transdoc 1.1) — so the waiver is used deliberately rather than seeding an
    # artifact this fixture has no other reason to own. It also keeps the waiver
    # path itself under test on every nested-run assertion.
    _cr(
        run_dir,
        "step",
        "--phase",
        "2",
        "--title",
        "Phase B",
        "--review-waived",
        "nested-run fixture; not a phase-review test",
    )
    _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-probe",
        "--phases",
        "5",
        "--terminal",
        "found:0 no-op round",
    )


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
            [sys.executable, str(_SCRIPT), "round", "--findings", "1", "--classes-new", f"c{i}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={
                "PATH": "/usr/bin:/bin",
                "COMMAND_RUN_DIR": str(run_dir),
                "KAIZEN_EVENTS_DIR": str(_events_dir(run_dir)),
                "CLAUDE_SESSION_ID": "s1",
            },
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

    env = dict(
        os.environ,
        COMMAND_RUN_DIR=str(tmp_path / "runs"),
        KAIZEN_EVENTS_DIR=str(tmp_path / "events"),
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, timeout=15)
    (repo / "x.txt").write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, timeout=15)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
        cwd=repo,
        check=True,
        timeout=15,
    )
    script = "/opt/fabrik/scripts/command_run.py"
    subprocess.run(
        [
            sys.executable,
            script,
            "start",
            "--command",
            "fabrik-review",
            "--phases",
            "3",
            "--terminal",
            "t",
        ],
        cwd=repo,
        env=env,
        check=True,
        timeout=15,
    )
    r = subprocess.run(
        [
                sys.executable,
                script,
                "done",
            "--command",
            "fabrik-review",
            "--evidence",
            "reviewed, all clean",
                "--feedback",
                "none — harness setup",
            ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert r.returncode == 1, "done closed a review run with NO report anywhere"
    assert "persisted report" in r.stdout
    # writing the report unlocks the close
    (repo / "docs/development/reviews").mkdir(parents=True)
    (repo / "docs/development/reviews/2026-08-19-x-review.md").write_text("# r\n")
    r2 = subprocess.run(
        [
                sys.executable,
                script,
                "done",
            "--command",
            "fabrik-review",
            "--evidence",
            "report written",
                "--feedback",
                "none — harness setup",
            ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
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
    subprocess.run(
        [
            sys.executable,
            script,
            "start",
            "--command",
            "fabrik-review",
            "--phases",
            "3",
            "--terminal",
            "t",
        ],
        cwd=repo_a,
        env=env,
        check=True,
        timeout=15,
    )
    # close from repo B (wrong repo, dirty reviews/): must still refuse — the check runs in A
    r = subprocess.run(
        [sys.executable, script, "done", "--command", "fabrik-review", "--evidence", "e", "--feedback", "none — harness setup"],
        cwd=repo_b,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert r.returncode == 1, "wrong-repo dirt satisfied the artifact check"
    # write the real report in A, close from a SUBDIR of A: must succeed
    (repo_a / "docs/development/reviews").mkdir(parents=True)
    (repo_a / "docs/development/reviews/2026-08-19-a-review.md").write_text("# r\n")
    sub = repo_a / "scripts"
    sub.mkdir()
    r2 = subprocess.run(
        [sys.executable, script, "done", "--command", "fabrik-review", "--evidence", "e", "--feedback", "none — harness setup"],
        cwd=sub,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
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
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
        cwd=repo,
        check=True,
        timeout=15,
    )
    past = _t.time() - 3600
    os.utime(old, (past, past))
    _t.sleep(1.1)  # run-binding is second-granular: the pre-run commit must be < started_at
    script = "/opt/fabrik/scripts/command_run.py"
    subprocess.run(
        [
            sys.executable,
            script,
            "start",
            "--command",
            "fabrik-review",
            "--phases",
            "3",
            "--terminal",
            "t",
        ],
        cwd=repo,
        env=env,
        check=True,
        timeout=15,
    )
    subprocess.run(
        ["git", "rm", "-q", "docs/development/reviews/old-review.md"],
        cwd=repo,
        check=True,
        timeout=15,
    )
    r = subprocess.run(
        [sys.executable, script, "done", "--command", "fabrik-review", "--evidence", "e", "--feedback", "none — harness setup"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
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
    subprocess.run(
        [
            sys.executable,
            script,
            "start",
            "--command",
            "fabrik-review",
            "--phases",
            "3",
            "--terminal",
            "t",
        ],
        cwd=repo,
        env=env,
        check=True,
        timeout=15,
    )
    r = subprocess.run(
        [sys.executable, script, "done", "--command", "fabrik-review", "--evidence", "e", "--feedback", "none — harness setup"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
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
    subprocess.run(
        [
            sys.executable,
            script,
            "start",
            "--command",
            "fabrik-review",
            "--phases",
            "3",
            "--terminal",
            "t",
        ],
        cwd=norepo,
        env=env,
        check=True,
        timeout=15,
    )
    r = subprocess.run(
        [sys.executable, script, "done", "--command", "fabrik-review", "--evidence", "e", "--feedback", "none — harness setup"],
        cwd=dirty,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
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
    subprocess.run(
        [
            sys.executable,
            script,
            "start",
            "--command",
            "fabrik-review",
            "--phases",
            "3",
            "--terminal",
            "t",
        ],
        cwd=norepo,
        env=env,
        check=True,
        timeout=15,
    )
    r = subprocess.run(
        [
                sys.executable,
                script,
                "blocked",
            "--command",
            "fabrik-review",
            "--reason",
            "rootless-record",
                "--feedback",
                "none — harness setup",
            ],
        cwd=norepo,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
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
    assert (
        _cr(run_dir, "done", "--command", "fabrik-docs-review", "--evidence", "x").returncode == 1
    )
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
        "session_id",
        "command",
        "phases",
        "phase",
        "phase_title",
        "terminal",
        "state",
        "started_at",
        "started_epoch",
        "repo_root",
        "rounds",
        "classes",
        "stack",
        "updated_at",
        "updated_ts",
        "event_seq",
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
    assert (
        _cr(
            run_dir,
            "start",
            "--command",
            "fabrik-probe",
            "--phases",
            "5",
            "--terminal",
            "t",
            extra_env=gone,
        ).returncode
        == 0
    )
    assert _rec(run_dir)["state"] == "running"
    assert _events(run_dir, "s1") == []


# --- T03: sid honesty — the `nosession` collision made MEASURABLE -------------


def test_nosession_events_carry_sid_source_none(run_dir: Path) -> None:
    """An empty CLAUDE_SESSION_ID (every Bash-tool shell) must not be laundered into
    an attributed session: the record still works, the EVENT says `none`."""
    assert (
        _cr(
            run_dir,
            "start",
            "--command",
            "fabrik-probe",
            "--phases",
            "5",
            "--terminal",
            "t",
            sid=None,
        ).returncode
        == 0
    )
    # The name is now repo-SCOPED (`nosession-<repo>`): a bare `nosession` was one file in
    # a global state dir, so every id-less session on the box merged into it. What this test
    # actually guards — that an empty id is not laundered into an attributed session — is
    # unchanged, so assert the invariant rather than the literal.
    recs = list(run_dir.glob("nosession*.json"))
    assert len(recs) == 1 and recs[0].name.startswith("nosession"), recs
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
    p = _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-probe",
        "--phases",
        "5",
        "--terminal",
        "t",
        "--adopt-sid",
        sid=None,
        cwd=work,
    )
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
    p = _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-probe",
        "--phases",
        "5",
        "--terminal",
        "t",
        "--adopt-sid",
        sid=None,
        cwd=work,
    )
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
    _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-probe",
        "--phases",
        "5",
        "--terminal",
        "t",
        "--adopt-sid",
        sid=None,
        cwd=work,
    )
    assert [r["event"] for r in _events(run_dir, "sessA")] == ["session_start", "run_open"]
    assert len(_events(run_dir, "sessB")) == 1


def test_adopt_sid_window_starts_at_the_runs_own_start(run_dir: Path, tmp_path: Path) -> None:
    """Once a run exists the window is anchored to ITS start — a session whose only
    trace of this cwd predates the run is not a candidate."""
    work = tmp_path / "work"
    work.mkdir()
    _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-probe",
        "--phases",
        "5",
        "--terminal",
        "t",
        sid=None,
        cwd=work,
    )
    _seed_event(run_dir, "stale", cwd=work, ts=_iso(-3600))
    _cr(run_dir, "round", "--findings", "1", "--adopt-sid", sid=None, cwd=work)
    assert len(_events(run_dir, "stale")) == 1, "a pre-run event must not adopt"
    assert [r["event"] for r in _events(run_dir, "unknown")] == ["run_open", "round"]
    # an event INSIDE the window does adopt
    _seed_event(run_dir, "live", cwd=work, ts=_iso(5))
    _cr(run_dir, "round", "--findings", "0", "--adopt-sid", sid=None, cwd=work)
    assert [r["event"] for r in _events(run_dir, "live")] == ["session_start", "round"]


def test_adopt_sid_is_ignored_when_a_real_sid_exists(run_dir: Path, tmp_path: Path) -> None:
    """An honest sid always wins — the join is a fallback, never an override."""
    work = tmp_path / "work"
    work.mkdir()
    _seed_event(run_dir, "sessA", cwd=work)
    _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-probe",
        "--phases",
        "5",
        "--terminal",
        "t",
        "--adopt-sid",
        sid="s1",
        cwd=work,
    )
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
        return (
            json.dumps(
                {
                    "schema": 1,
                    "ts": _iso(),
                    "sid": stem,
                    "sid_source": "env",
                    "event": "round",
                    "exposure": {"project": "unknown"},
                    "cwd": str(cwd.resolve()),
                    "pad": pad,
                }
            )
            + "\n"
        )

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
    p = _cr(
        run_dir,
        "start",
        "--command",
        _PROBE,
        "--phases",
        "5",
        "--terminal",
        "t",
        "--adopt-sid",
        sid=None,
        cwd=work,
    )
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
    _cr(
        run_dir,
        "start",
        "--command",
        _PROBE,
        "--phases",
        "5",
        "--terminal",
        "t",
        "--adopt-sid",
        sid=None,
        cwd=work,
    )
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
    _cr(
        run_dir,
        "start",
        "--command",
        _PROBE,
        "--phases",
        "5",
        "--terminal",
        "t",
        "--adopt-sid",
        sid=None,
        cwd=work,
    )
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
    _cr(
        run_dir,
        "start",
        "--command",
        _PROBE,
        "--phases",
        "1",
        "--terminal",
        "t",
        sid=None,
        cwd=work,
    )
    _cr(run_dir, "done", "--command", _PROBE, "--evidence", "x", sid=None, cwd=work)
    _seed_event(run_dir, "sessB", cwd=work, ts=_iso())
    before = len(_events(run_dir, "unknown"))
    _cr(
        run_dir,
        "start",
        "--command",
        _PROBE,
        "--phases",
        "1",
        "--terminal",
        "t",
        "--adopt-sid",
        sid=None,
        cwd=work,
    )
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
            env={
                "PATH": "/usr/bin:/bin",
                "COMMAND_RUN_DIR": str(run_dir),
                "KAIZEN_EVENTS_DIR": str(_events_dir(run_dir)),
                "CLAUDE_SESSION_ID": "s1",
            },
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
    rows = [
        json.loads(ln)
        for ln in (tmp_path / "events" / "s1.jsonl").read_text(encoding="utf-8").splitlines()
    ]
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
        json.dumps(
            {
                "schema": 1,
                "ts": _iso(-60),
                "sid": "sessA",
                "event": "session_start",
                "cwd": str(Path.cwd().resolve()),
            }
        )
        + "\n",
        encoding="utf-8",
    )
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
        run_dir,
        "start",
        "--command",
        "fabrik-probe",
        "--phases",
        "1",
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
        run_dir,
        "start",
        "--command",
        "fabrik-probe",
        "--phases",
        "1",
        sid="legacy-var",
        extra_env={"CLAUDE_CODE_SESSION_ID": "uuid-beta"},
    )
    assert r.returncode == 0, r.stderr
    assert (run_dir / "legacy-var.json").exists(), "CLAUDE_SESSION_ID must outrank the code var"
    for uuid in ("uuid-a", "uuid-b"):
        r = _cr(
            run_dir,
            "start",
            "--command",
            "fabrik-probe",
            "--phases",
            "1",
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
        json.dumps(
            {
                "schema": 1,
                "ts": _iso(-60),
                "sid": "sessB",
                "event": "session_start",
                "cwd": str(Path.cwd().resolve()),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert cr.main(["start", "--command", _PROBE, "--phases", "1", "--adopt-sid"]) == 0
    assert len(calls) == 1, calls
    assert calls[0]["sid_source"] != "join", calls[0]
    assert calls[0]["sid"] != "sessB", "the event was join-attributed into a sibling's stream"


def _artifact_repo(tmp_path, name="repo"):
    import os
    import subprocess

    env = dict(
        os.environ,
        COMMAND_RUN_DIR=str(tmp_path / name / "runs"),
        KAIZEN_EVENTS_DIR=str(tmp_path / name / "events"),
        CLAUDE_SESSION_ID=f"artifact-test-{name}",
    )
    repo = tmp_path / name / "repo"
    repo.parent.mkdir(parents=True, exist_ok=True)
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, timeout=15)
    (repo / "x.txt").write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, timeout=15)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
        cwd=repo,
        check=True,
        timeout=15,
    )
    return env, repo


def test_cert_and_mega_done_also_require_their_reports(tmp_path):
    """Round-135 HIGH: the artifact guard covered only fabrik-review/repo-review — a
    fabrik-user-test/service-test/fab-mega-04-validate done closed with NO report ever
    written, the round-29 hole three commands over."""
    import subprocess

    script = "/opt/fabrik/scripts/command_run.py"
    for cmd in ("fabrik-user-test", "fab-mega-04-validate"):
        # a fresh repo per command: the 2s mtime grace otherwise lets the previous
        # command's report satisfy the next run in a fast-running test
        env, repo = _artifact_repo(tmp_path, name=cmd)
        subprocess.run(
            [sys.executable, script, "start", "--command", cmd, "--phases", "1", "--terminal", "t"],
            cwd=repo,
            env=env,
            check=True,
            timeout=15,
        )
        r = subprocess.run(
            [
                sys.executable,
                script,
                "done",
                "--command",
                cmd,
                "--evidence",
                "nothing written at all",
                "--feedback",
                "none — harness setup",
            ],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert r.returncode == 1, f"{cmd}: done closed with no report ({r.stdout})"
        assert "persisted report" in r.stdout
        (repo / "docs/development/reviews").mkdir(parents=True, exist_ok=True)
        rep = repo / f"docs/development/reviews/2026-08-21-{cmd}-x.md"
        rep.write_text("# r\ndone and closed\n")
        r2 = subprocess.run(
            [sys.executable, script, "done", "--command", cmd, "--evidence", "report written", "--feedback", "none — harness setup"],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert r2.returncode == 0, r2.stdout + r2.stderr


def test_done_refused_when_every_artifact_is_midloop(tmp_path):
    """Round-135 HIGH (content floor): a report declaring Status: IN-PROGRESS satisfies no
    terminal condition — done with ONLY mid-loop artifacts is the evidence-string hole
    wearing a file's clothes."""
    import subprocess

    env, repo = _artifact_repo(tmp_path)
    script = "/opt/fabrik/scripts/command_run.py"
    subprocess.run(
        [
            sys.executable,
            script,
            "start",
            "--command",
            "fabrik-review",
            "--phases",
            "1",
            "--terminal",
            "t",
        ],
        cwd=repo,
        env=env,
        check=True,
        timeout=15,
    )
    (repo / "docs/development/reviews").mkdir(parents=True)
    rep = repo / "docs/development/reviews/2026-08-21-midloop-review.md"
    rep.write_text("# r\nStatus: IN-PROGRESS — round 3 running\n")
    r = subprocess.run(
        [sys.executable, script, "done", "--command", "fabrik-review", "--evidence", "all done", "--feedback", "none — harness setup"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert r.returncode == 1, "done closed on a mid-loop-only artifact"
    assert "IN-PROGRESS" in r.stdout
    rep.write_text("# r\nStatus: closed — quiet round earned\n")
    r2 = subprocess.run(
        [sys.executable, script, "done", "--command", "fabrik-review", "--evidence", "closed", "--feedback", "none — harness setup"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert r2.returncode == 0, r2.stdout + r2.stderr


def test_done_artifact_floor_survives_the_exit_sequence_and_rejects_decoys(tmp_path):
    """Round-137, three live-reproduced holes in the round-136 floor: (a) a report committed
    mid-run followed by a later unrelated commit (the Completion Contract's own EXIT
    sequence) false-REFUSED the close — only HEAD was inspected; (b) a committed non-.md
    under reviews/ satisfied the gate with candidates=[] so the content floor never ran;
    (c) archived/ counted. The same live-.md-outside-archived filter now decides both the
    gate and the candidates, across the run window's commits."""
    import subprocess

    script = "/opt/fabrik/scripts/command_run.py"

    def _commit(repo, env, *paths, msg="x"):
        subprocess.run(["git", "add", *paths], cwd=repo, check=True, timeout=15)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg],
            cwd=repo,
            check=True,
            timeout=15,
        )

    # (a) report + later unrelated commit → done must STILL close
    env, repo = _artifact_repo(tmp_path, name="window")
    subprocess.run(
        [
            sys.executable,
            script,
            "start",
            "--command",
            "fabrik-review",
            "--phases",
            "1",
            "--terminal",
            "t",
        ],
        cwd=repo,
        env=env,
        check=True,
        timeout=15,
    )
    (repo / "docs/development/reviews").mkdir(parents=True)
    rep = repo / "docs/development/reviews/2026-08-21-window-review.md"
    rep.write_text("# r\nclosed clean\n")
    _commit(repo, env, "docs/development/reviews", msg="report")
    (repo / "CHANGELOG.md").write_text("entry\n")
    _commit(repo, env, "CHANGELOG.md", msg="changelog")
    # make the report's WORKING-TREE mtime stale so only the commit window can prove it
    import os as _os

    _os.utime(rep, (1, 1))
    r = subprocess.run(
        [sys.executable, script, "done", "--command", "fabrik-review", "--evidence", "e", "--feedback", "none — harness setup"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert r.returncode == 0, f"a later unrelated commit false-refused the close: {r.stdout}"

    # (b) non-.md decoy only → REFUSED
    env, repo = _artifact_repo(tmp_path, name="decoy")
    subprocess.run(
        [
            sys.executable,
            script,
            "start",
            "--command",
            "fabrik-review",
            "--phases",
            "1",
            "--terminal",
            "t",
        ],
        cwd=repo,
        env=env,
        check=True,
        timeout=15,
    )
    (repo / "docs/development/reviews").mkdir(parents=True)
    (repo / "docs/development/reviews/evidence.png").write_bytes(b"\x89PNG")
    _commit(repo, env, "docs/development/reviews", msg="png")
    r = subprocess.run(
        [sys.executable, script, "done", "--command", "fabrik-review", "--evidence", "see commit", "--feedback", "none — harness setup"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert r.returncode == 1, "a committed non-.md decoy satisfied the artifact floor"

    # (c) archived/ only → REFUSED
    env, repo = _artifact_repo(tmp_path, name="arch")
    subprocess.run(
        [
            sys.executable,
            script,
            "start",
            "--command",
            "fabrik-review",
            "--phases",
            "1",
            "--terminal",
            "t",
        ],
        cwd=repo,
        env=env,
        check=True,
        timeout=15,
    )
    (repo / "docs/development/reviews/archived").mkdir(parents=True)
    (repo / "docs/development/reviews/archived/old-review.md").write_text("# old\n")
    _commit(repo, env, "docs/development/reviews", msg="refile")
    r = subprocess.run(
        [sys.executable, script, "done", "--command", "fabrik-review", "--evidence", "refiled", "--feedback", "none — harness setup"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert r.returncode == 1, "an archived/ re-file satisfied the artifact floor"


def test_done_floor_rejects_symlinks_stale_rebases_and_survives_merges_and_long_runs(tmp_path):
    """Round-139, four live-reproduced seams in the round-138 walk: an untracked symlink
    decoy satisfied the floor; a rebase-replayed stale leftover looked fresh (%ct rewritten
    — %at survives replay); a report finalized only in a merge-conflict resolution listed no
    files (default merge suppression); and 55 follow-up commits pushed the report past the
    -n 50 bound. One walk now: %at, -m, the run's own time window, no symlinks."""
    import subprocess

    script = "/opt/fabrik/scripts/command_run.py"

    def _commit(repo, *paths, msg="x", env_extra=None):
        import os as _os

        subprocess.run(["git", "add", "-f", *paths], cwd=repo, check=True, timeout=15)
        full = dict(_os.environ, **(env_extra or {}))
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg],
            cwd=repo,
            check=True,
            timeout=15,
            env=full,
        )

    # (1) symlink decoy → REFUSED
    env, repo = _artifact_repo(tmp_path, name="sym")
    subprocess.run(
        [
            sys.executable,
            script,
            "start",
            "--command",
            "fabrik-review",
            "--phases",
            "1",
            "--terminal",
            "t",
        ],
        cwd=repo,
        env=env,
        check=True,
        timeout=15,
    )
    (repo / "docs/development/reviews").mkdir(parents=True)
    target = tmp_path / "sym" / "decoy_target.txt"
    target.write_text("unrelated\n")
    (repo / "docs/development/reviews/fake-review.md").symlink_to(target)
    r = subprocess.run(
        [sys.executable, script, "done", "--command", "fabrik-review", "--evidence", "e", "--feedback", "none — harness setup"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert r.returncode == 1, "a symlink decoy satisfied the artifact floor"

    # (2) stale leftover with an OLD author date but a fresh committer date (rebase replay)
    env, repo = _artifact_repo(tmp_path, name="rebase")
    subprocess.run(
        [
            sys.executable,
            script,
            "start",
            "--command",
            "fabrik-review",
            "--phases",
            "1",
            "--terminal",
            "t",
        ],
        cwd=repo,
        env=env,
        check=True,
        timeout=15,
    )
    (repo / "docs/development/reviews").mkdir(parents=True)
    stale = repo / "docs/development/reviews/stale-review.md"
    stale.write_text("# old abandoned review\n")
    import os as _os

    _commit(
        repo,
        "docs/development/reviews",
        msg="replayed",
        env_extra={"GIT_AUTHOR_DATE": "2020-06-01T00:00:00 +0000"},
    )
    _os.utime(stale, (1, 1))
    r = subprocess.run(
        [sys.executable, script, "done", "--command", "fabrik-review", "--evidence", "e", "--feedback", "none — harness setup"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert r.returncode == 1, "a rebase-replayed stale leftover satisfied the freshness floor"

    # (3) report finalized only inside a merge commit → must CLOSE
    env, repo = _artifact_repo(tmp_path, name="merge")
    (repo / "docs/development/reviews").mkdir(parents=True)
    f = repo / "docs/development/reviews/m-review.md"
    f.write_text("base\n")
    _commit(repo, "docs/development/reviews", msg="base-report")
    subprocess.run(["git", "checkout", "-q", "-b", "side"], cwd=repo, check=True, timeout=15)
    f.write_text("side version\n")
    _commit(repo, "docs/development/reviews", msg="side")
    subprocess.run(["git", "checkout", "-q", "-"], cwd=repo, check=True, timeout=15)
    f.write_text("main version\n")
    _commit(repo, "docs/development/reviews", msg="main")
    subprocess.run(
        [
            sys.executable,
            script,
            "start",
            "--command",
            "fabrik-review",
            "--phases",
            "1",
            "--terminal",
            "t",
        ],
        cwd=repo,
        env=env,
        check=True,
        timeout=15,
    )
    m = subprocess.run(
        ["git", "merge", "side"], cwd=repo, capture_output=True, text=True, timeout=15
    )
    assert m.returncode != 0, "fixture must conflict"
    f.write_text("# resolved during this run — closed clean\n")
    _commit(repo, "docs/development/reviews", msg="merge-resolve")
    _os.utime(f, (1, 1))
    r = subprocess.run(
        [sys.executable, script, "done", "--command", "fabrik-review", "--evidence", "e", "--feedback", "none — harness setup"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert r.returncode == 0, f"a merge-resolved report was false-refused: {r.stdout}"

    # (4) 55 commits after the report → must CLOSE
    env, repo = _artifact_repo(tmp_path, name="long")
    subprocess.run(
        [
            sys.executable,
            script,
            "start",
            "--command",
            "fabrik-review",
            "--phases",
            "1",
            "--terminal",
            "t",
        ],
        cwd=repo,
        env=env,
        check=True,
        timeout=15,
    )
    (repo / "docs/development/reviews").mkdir(parents=True)
    rep = repo / "docs/development/reviews/long-review.md"
    rep.write_text("# closed clean\n")
    _commit(repo, "docs/development/reviews", msg="report")
    for i in range(55):
        (repo / "f.txt").write_text(f"{i}\n")
        _commit(repo, "f.txt", msg=f"phase-{i}")
    _os.utime(rep, (1, 1))
    r = subprocess.run(
        [sys.executable, script, "done", "--command", "fabrik-review", "--evidence", "e", "--feedback", "none — harness setup"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert r.returncode == 0, f"a long run's report was false-refused: {r.stdout}"


def test_done_refused_when_the_report_was_added_then_deleted(tmp_path):
    """Round-141 CRITICAL: --name-only lines carry no status letter, so an add-then-delete
    pair inside the window matched the path test while the file no longer existed —
    ok_artifact True with candidates=[], both refusal branches skipped, run closed with
    zero review content anywhere. Existence now gates the gate."""
    import subprocess

    script = "/opt/fabrik/scripts/command_run.py"
    env, repo = _artifact_repo(tmp_path, name="adddel")
    subprocess.run(
        [
            sys.executable,
            script,
            "start",
            "--command",
            "fabrik-review",
            "--phases",
            "1",
            "--terminal",
            "t",
        ],
        cwd=repo,
        env=env,
        check=True,
        timeout=15,
    )
    (repo / "docs/development/reviews").mkdir(parents=True)
    rep = repo / "docs/development/reviews/x-review.md"
    rep.write_text("# report\n")
    subprocess.run(["git", "add", "docs/development/reviews"], cwd=repo, check=True, timeout=15)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "add"],
        cwd=repo,
        check=True,
        timeout=15,
    )
    subprocess.run(
        ["git", "rm", "-q", "docs/development/reviews/x-review.md"],
        cwd=repo,
        check=True,
        timeout=15,
    )
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "rm"],
        cwd=repo,
        check=True,
        timeout=15,
    )
    r = subprocess.run(
        [sys.executable, script, "done", "--command", "fabrik-review", "--evidence", "e", "--feedback", "none — harness setup"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert r.returncode == 1, "an add-then-delete pair closed the run with no report on disk"


# --- the cross-repo `nosession` corruption (9 reports, 6 senders, 2026-08-16..20) ---


def _mkrepo(base: Path, name: str) -> Path:
    d = base / name
    d.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=d, check=True, capture_output=True)
    return d


def test_id_less_runs_in_different_repos_never_share_a_record(tmp_path: Path) -> None:
    """The defect five repos reported and nobody fixed: the state dir is GLOBAL and the
    record is keyed on the session id alone, so every id-less session on the box — in ANY
    repo — merged into one `nosession.json`. tryton-crm watched its own `step --phase 5`
    land inside another repo's 4-phase record ("phase 5/4", a command it never ran), and
    then `done` was correctly refused because the live record named a foreign command, so
    the run could not be closed at all. `repo_root` was already stored INSIDE the record,
    which is why the corruption was visible but not preventable.

    Two id-less repos must therefore never resolve to the same file."""
    run_dir = tmp_path / "runs"
    repo_a, repo_b = _mkrepo(tmp_path, "alpha"), _mkrepo(tmp_path, "beta")
    env = {"CLAUDE_SESSION_ID": "", "CLAUDE_CODE_SESSION_ID": ""}

    a = _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-spec",
        "--phases",
        "7",
        "--terminal",
        "ta",
        sid=None,
        cwd=repo_a,
        extra_env=env,
    )
    assert a.returncode == 0, a.stderr
    b = _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-doc-converge",
        "--phases",
        "4",
        "--terminal",
        "tb",
        sid=None,
        cwd=repo_b,
        extra_env=env,
    )
    assert b.returncode == 0, b.stderr

    records = sorted(p.name for p in run_dir.glob("*.json"))
    assert len(records) == 2, f"one record per repo, got {records}"

    # repo A's live run must still be ITS OWN — not beta's, and closable by name.
    line = _cr(run_dir, "line", sid=None, cwd=repo_a, extra_env=env)
    assert "fabrik-spec" in line.stdout, f"repo A's pinned line was clobbered: {line.stdout!r}"
    assert "fabrik-doc-converge" not in line.stdout, "a FOREIGN repo's run leaked into A"
    done = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-spec",
        "--evidence",
        "e",
        sid=None,
        cwd=repo_a,
        extra_env=env,
    )
    assert done.returncode == 0, f"A could not close its own run: {done.stdout}{done.stderr}"


def test_id_less_runs_in_the_same_repo_still_share_one_record(tmp_path: Path) -> None:
    """The repo scoping deliberately does NOT try to separate two id-less sessions inside
    one repo — there is nothing left to key on, and inventing a per-process key would make
    the record unfindable by the Stop hook (which looks up the uuid from its own payload).
    Same repo, no ids: one record, as before. The fix targets the CROSS-REPO harm."""
    run_dir = tmp_path / "runs"
    repo = _mkrepo(tmp_path, "solo")
    env = {"CLAUDE_SESSION_ID": "", "CLAUDE_CODE_SESSION_ID": ""}
    for cmd in ("fabrik-spec", "fabrik-review"):
        assert (
            _cr(
                run_dir,
                "start",
                "--command",
                cmd,
                "--phases",
                "2",
                "--terminal",
                "t",
                sid=None,
                cwd=repo,
                extra_env=env,
            ).returncode
            == 0
        )
    assert len(list(run_dir.glob("*.json"))) == 1


# --- transdoc 1.1: the per-phase review must emit an artifact the gate can see ---


def _plan_run(run_dir: Path, repo: Path, phases: int = 3):
    return _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-execute-plan",
        "--phases",
        str(phases),
        "--terminal",
        "all phases",
        sid="plan-sid",
        cwd=repo,
    )


def test_execute_plan_cannot_advance_a_phase_without_the_previous_review_artifact(
    tmp_path: Path,
) -> None:
    """transdoc 1.1, the 71-defect gap: fabrik-execute-plan requires each phase to
    reach /fabrik-review's coverage-adjudicated exit, but check_review_coverage's
    subject is the DIRECTORY docs/development/reviews/ — a per-phase review emits
    nothing there, so at all 17 phase boundaries the gate had NO SUBJECT and
    passed. A contract clause with no mechanical binding is a suggestion."""
    run_dir = tmp_path / "runs"
    repo = _mkrepo(tmp_path, "proj")
    assert _plan_run(run_dir, repo).returncode == 0
    # phase 1 -> 2 with no artifact: refused
    p = _cr(run_dir, "step", "--phase", "2", "--title", "B", sid="plan-sid", cwd=repo)
    assert p.returncode != 0, f"advanced with no phase-1 review: {p.stdout}{p.stderr}"
    assert "phase 1" in (p.stdout + p.stderr).lower()

    # emit the artifact -> allowed
    rev = repo / "docs" / "development" / "reviews"
    rev.mkdir(parents=True)
    (rev / "2026-08-23-plan-1-thing-phase-1-review.md").write_text("# review\n", encoding="utf-8")
    ok = _cr(run_dir, "step", "--phase", "2", "--title", "B", sid="plan-sid", cwd=repo)
    assert ok.returncode == 0, f"artifact present but still refused: {ok.stdout}{ok.stderr}"


def test_phase_one_never_needs_a_predecessor_artifact(tmp_path: Path) -> None:
    """There is no phase 0 review to demand — the guard must not wedge a run at its
    own first step."""
    run_dir = tmp_path / "runs"
    repo = _mkrepo(tmp_path, "proj2")
    assert _plan_run(run_dir, repo).returncode == 0
    assert (
        _cr(run_dir, "step", "--phase", "1", "--title", "A", sid="plan-sid", cwd=repo).returncode
        == 0
    )


def test_non_plan_commands_are_untouched_by_the_phase_review_rule(tmp_path: Path) -> None:
    """`step` is used by EVERY /fabrik-* command; only fabrik-execute-plan has
    per-phase reviews. A guard that fired everywhere would wedge the whole corpus."""
    run_dir = tmp_path / "runs"
    repo = _mkrepo(tmp_path, "proj3")
    assert (
        _cr(
            run_dir,
            "start",
            "--command",
            "fabrik-spec",
            "--phases",
            "4",
            "--terminal",
            "t",
            sid="spec-sid",
            cwd=repo,
        ).returncode
        == 0
    )
    assert (
        _cr(run_dir, "step", "--phase", "3", "--title", "C", sid="spec-sid", cwd=repo).returncode
        == 0
    )


def test_a_waiver_is_allowed_but_recorded(tmp_path: Path) -> None:
    """In-flight runs must not be stranded mid-plan (transdoc's §5 blast-radius
    note), but an escape that leaves no trace is how prose became unenforceable in
    the first place. The waiver is permitted and written into the record."""
    run_dir = tmp_path / "runs"
    repo = _mkrepo(tmp_path, "proj4")
    assert _plan_run(run_dir, repo).returncode == 0
    p = _cr(
        run_dir,
        "step",
        "--phase",
        "2",
        "--title",
        "B",
        "--review-waived",
        "in-flight run predating the rule",
        sid="plan-sid",
        cwd=repo,
    )
    assert p.returncode == 0, p.stdout + p.stderr
    rec = json.loads((run_dir / "plan-sid.json").read_text())
    waived = rec.get("waived_reviews") or []
    assert waived and waived[0]["phase"] == 1, rec
    assert "in-flight" in waived[0]["reason"]


# --- the four bypasses found by re-verifying my OWN 1.1 fix (2026-08-23) ------


def test_phase_10_review_does_not_satisfy_phase_1(tmp_path: Path) -> None:
    """BYPASS 1, highest severity: the match was a bare substring, and `phase-1` is a
    PREFIX of `phase-10`. A project that reviewed only its final phase would sail
    through every earlier boundary — the guard reporting success without asking its
    question, which is the exact class this whole report is about."""
    run_dir = tmp_path / "runs"
    repo = _mkrepo(tmp_path, "prefix")
    rev = repo / "docs" / "development" / "reviews"
    rev.mkdir(parents=True)
    (rev / "2026-08-23-plan-1-phase-10-review.md").write_text("# ten\n", encoding="utf-8")
    assert _plan_run(run_dir, repo).returncode == 0
    p = _cr(run_dir, "step", "--phase", "2", "--title", "B", sid="plan-sid", cwd=repo)
    assert p.returncode != 0, "a phase-10 review satisfied phase 1"


def test_an_empty_review_file_is_not_a_review(tmp_path: Path) -> None:
    """BYPASS 3: `touch` satisfied the guard. Existence is what this binds — but an
    empty file is not even existence."""
    run_dir = tmp_path / "runs"
    repo = _mkrepo(tmp_path, "empty")
    rev = repo / "docs" / "development" / "reviews"
    rev.mkdir(parents=True)
    (rev / "phase-1-review.md").write_text("", encoding="utf-8")
    assert _plan_run(run_dir, repo).returncode == 0
    assert _cr(run_dir, "step", "--phase", "2", "--title", "B",
               sid="plan-sid", cwd=repo).returncode != 0


def test_skipping_phases_cannot_skip_their_reviews(tmp_path: Path) -> None:
    """BYPASS 2: only the immediate predecessor was checked, so `step --phase 5`
    from phase 1 demanded phase 4's artifact and phases 2-3 vanished silently. The
    refusal names the LOWEST unreviewed phase, which is the one to go back to."""
    run_dir = tmp_path / "runs"
    repo = _mkrepo(tmp_path, "skip")
    rev = repo / "docs" / "development" / "reviews"
    rev.mkdir(parents=True)
    (rev / "phase-4-review.md").write_text("# four\n", encoding="utf-8")
    assert _plan_run(run_dir, repo, phases=6).returncode == 0
    p = _cr(run_dir, "step", "--phase", "5", "--title", "E", sid="plan-sid", cwd=repo)
    assert p.returncode != 0
    assert "phase 1" in (p.stdout + p.stderr).lower(), p.stdout + p.stderr


def test_a_cosmetic_command_name_cannot_disable_the_rule(tmp_path: Path) -> None:
    """BYPASS 4: the membership test was exact, so `--command Fabrik-Execute-Plan`
    or a trailing space silently disabled the ENTIRE per-phase requirement for that
    run, with nothing printed anywhere."""
    run_dir = tmp_path / "runs"
    repo = _mkrepo(tmp_path, "casing")
    assert _cr(run_dir, "start", "--command", "Fabrik-Execute-Plan", "--phases", "3",
               "--terminal", "t", sid="case-sid", cwd=repo).returncode == 0
    assert _cr(run_dir, "step", "--phase", "2", "--title", "B",
               sid="case-sid", cwd=repo).returncode != 0


# ── the FEEDBACK verdict: making "Filed" MEASURED instead of hand-typed ──────────────────────────
# `kaizen_collect_v2.py` emits the columns `Top friction fixed` and `Filed (spec/mail)` but never
# populates them — they are the analyst's cells by design (docs/workstation/kaizen.md:202), and every
# row in kaizen-log-infra.md has carried "—" in both since the 2026-08-12 baseline. The weekly
# analyst had to reconstruct "what got in the way" from memory across sessions they cannot see.
#
# The close-out FEEDBACK line (commands/_fragments/close-feedback.md) supplies the corpus; this makes
# it COUNTABLE. Carried on the existing `run_close` event rather than a new vocabulary entry — the
# collector already reads run_close, so no consumer has to learn a new name.
#
# The load-bearing value is `unstated`. An agent that never passed --feedback is not the same as one
# that looked and found nothing, and only a distinct value makes the difference measurable instead of
# invisible — the same rule the FEEDBACK line itself enforces on the agent.


def test_done_records_a_filed_feedback_verdict(run_dir: Path) -> None:
    _start(run_dir)
    _cr(
        run_dir, "done", "--command", "fabrik-probe", "--evidence", "round 4 found: 0",
        "--feedback", "filed 01M11VS2ZE to intel — dead Kilo test modules break collection",
    )
    row = _events(run_dir, "s1")[-1]
    assert row["feedback"] == "filed", row
    assert row["feedback_to"] == ["intel"], row
    # a HASH, never the prose — same contract as evidence_hash
    assert isinstance(row["feedback_hash"], str) and len(row["feedback_hash"]) >= 8, row
    assert "Kilo" not in json.dumps(row), row


def test_done_records_an_explicit_none_verdict(run_dir: Path) -> None:
    """`none` is a real answer: the agent looked and had nothing to file."""
    _start(run_dir)
    _cr(
        run_dir, "done", "--command", "fabrik-probe", "--evidence", "x",
        "--feedback", "none — exercised the router and the corpus check",
    )
    row = _events(run_dir, "s1")[-1]
    assert row["feedback"] == "none", row
    assert row["feedback_to"] == [], row


def test_omitting_feedback_is_recorded_as_unstated_not_as_none(run_dir: Path) -> None:
    """THE point. If a missing verdict collapsed into `none`, the metric would report perfect
    diligence for a corpus nobody ever looked at — the fail-silent-green shape, in the telemetry.

    A close now REFUSES without a verdict, so `unstated` is reachable only through a GRANDFATHERED
    record (one started before `_FEEDBACK_REQUIRED_FROM`). That path must keep classifying
    correctly: the grader reads a 14-day window that still contains pre-cutoff closes, and
    re-labelling them `none` would retroactively invent compliance that never happened."""
    _start(run_dir)
    _backdate(run_dir, "s1")
    _cr(run_dir, "done", "--command", "fabrik-probe", "--evidence", "x",
        inject_feedback=False)
    row = _events(run_dir, "s1")[-1]
    assert row["feedback"] == "unstated", row


def test_blocked_carries_the_verdict_too(run_dir: Path) -> None:
    """A BLOCKED run is exactly when friction is worth hearing about."""
    _start(run_dir)
    _cr(
        run_dir, "blocked", "--command", "fabrik-probe", "--reason", "missing infra — no DB",
        "--feedback", "filed to fleet — the scaffold emits no DB fixture",
    )
    row = _events(run_dir, "s1")[-1]
    assert row["verdict"] == "blocked" and row["feedback"] == "filed", row
    assert row["feedback_to"] == ["fleet"], row


def test_multiple_beats_are_all_captured(run_dir: Path) -> None:
    _start(run_dir)
    _cr(
        run_dir, "done", "--command", "fabrik-probe", "--evidence", "x",
        "--feedback", "filed to infra and intel",
    )
    assert sorted(_events(run_dir, "s1")[-1]["feedback_to"]) == ["infra", "intel"]


def test_feedback_never_breaks_the_close(run_dir: Path) -> None:
    """The record is the point; telemetry is not allowed to cost a close."""
    _start(run_dir)
    out = _cr(
        run_dir, "done", "--command", "fabrik-probe", "--evidence", "x",
        # NOT a NUL byte: execve() forbids one in argv, so it can never reach this code and a
        # test using one measures subprocess, not the classifier. These CAN arrive.
        "--feedback", "\x01\x1b[31m filed to   nobody " + "z" * 5000,
    )
    assert out.returncode == 0, out.stderr
    row = _events(run_dir, "s1")[-1]
    assert row["event"] == "run_close" and row["feedback"] == "filed", row
    assert "z" * 100 not in json.dumps(row), "the prose must never reach the store"


# ── F3: the commands MANDATE a close that command_run had no word for ────────────────────────────
# transdoc, 2026-08-27: /fabrik-user-test and /fabrik-service-test both REQUIRE a run with open rows
# to close `NOT-QUIET (routes outstanding)` with a `## RESUME` block naming every open row. Neither
# `done` (the contract is not met) nor any of the three sanctioned BLOCKED causes means that, so a
# real 3-round gauntlet fixing 25 defects had to close under "unresolvable spec contradiction" — a
# stretch its author flagged in the reason string rather than let the record read cleaner than the
# truth. A disposition an agent is ORDERED to produce and CANNOT record is a contract defect.
#
# `handoff` is strictly HARDER to fake than the cause it replaces: --resume is required and names the
# artifact carrying the open rows, where "unresolvable spec contradiction" is free prose.


def test_handoff_closes_a_not_quiet_run_with_its_resume_artifact(run_dir: Path) -> None:
    _start(run_dir)
    out = _cr(
        run_dir, "handoff", "--command", "fabrik-probe",
        "--resume", "docs/development/certifications/2026-08-27-cert-x/ledger.md",
        "--reason", "3 DESIGN-GAP rows the run may not decide",
    )
    assert out.returncode == 0, out.stderr
    row = _events(run_dir, "s1")[-1]
    assert row["event"] == "run_close" and row["verdict"] == "handoff", row
    assert row["closed_by"] == "agent", row


def test_handoff_refuses_without_the_resume_artifact(run_dir: Path) -> None:
    """The whole point: it must be harder to fake than the BLOCKED cause it replaces."""
    _start(run_dir)
    out = _cr(run_dir, "handoff", "--command", "fabrik-probe", "--reason", "rows open")
    assert out.returncode != 0, out.stdout + out.stderr


def test_handoff_leaves_the_record_closed_so_the_stop_hook_releases(run_dir: Path) -> None:
    """A fourth close is only useful if it actually ENDS the run — otherwise the agent is still
    trapped and will reach for the stretched BLOCKED cause anyway."""
    _start(run_dir)
    _cr(
        run_dir, "handoff", "--command", "fabrik-probe", "--resume", "docs/x/ledger.md",
        "--reason", "rows open",
    )
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["state"] == "handoff", rec
    assert rec["state"] != "running", "the Stop hook keys on running — handoff must release it"


def test_handoff_carries_the_feedback_verdict_like_the_other_closes(run_dir: Path) -> None:
    _start(run_dir)
    _cr(
        run_dir, "handoff", "--command", "fabrik-probe", "--resume", "docs/x/ledger.md",
        "--reason", "rows open", "--feedback", "filed to infra — the grader is mute",
    )
    row = _events(run_dir, "s1")[-1]
    assert row["feedback"] == "filed" and row["feedback_to"] == ["infra"], row


def test_the_record_itself_carries_the_feedback_verdict(run_dir: Path) -> None:
    """The event stream is box-local telemetry; the RECORD is what a check can read per-run. Storing
    the verdict only on the event left the record unable to describe its own close — and left the
    duty ungradeable, which is how a prose obligation stays prose."""
    _start(run_dir)
    _cr(run_dir, "done", "--command", "fabrik-probe", "--evidence", "e",
        "--feedback", "filed to fleet — scaffold emits no DB fixture")
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["feedback"] == "filed", rec
    assert rec["feedback_to"] == ["fleet"], rec


def test_a_close_without_feedback_records_unstated_on_the_record_too(run_dir: Path) -> None:
    """Same grandfathered path, asserted on the RECORD rather than the event — that is what the
    per-run grader (`check_feedback_duty.py`) actually reads."""
    _start(run_dir)
    _backdate(run_dir, "s1")
    _cr(run_dir, "done", "--command", "fabrik-probe", "--evidence", "e",
        inject_feedback=False)
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["feedback"] == "unstated", rec


def test_a_post_cutoff_close_cannot_reach_unstated_at_all(run_dir: Path) -> None:
    """The other half of the pair, and the reason the change exists: for any run started under the
    current contract, `unstated` is now UNREACHABLE — the close is refused instead, and the record
    stays `running` so the Stop hook holds the turn open."""
    _start(run_dir)
    r = _cr(run_dir, "done", "--command", "fabrik-probe", "--evidence", "e", "--feedback", "")
    assert r.returncode == 1, r.stdout
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["state"] == "running" and "feedback" not in rec, rec


def test_an_honest_none_naming_the_surfaces_it_swept_is_not_read_as_filed(run_dir: Path) -> None:
    """F2 from /fabrik-review on this work. `close-feedback.md` INSTRUCTS the agent to write
    `none — <the surfaces this run exercised>`, and those surface names are frequently the beat
    names themselves ("infra rules", "the fleet specs"). Matching a beat anywhere therefore read an
    honest `none` as a filing — inflating compliance and under-counting the very verdict the metric
    exists to distinguish. A beat only means `filed` alongside an actual filing VERB."""
    for text in (
        "none — swept infra rules and the enforcement checks",
        "none - exercised the fleet spec loader",
        "nothing to file; looked at intel's flywheel rosters",
    ):
        _start(run_dir)
        _cr(run_dir, "done", "--command", "fabrik-probe", "--evidence", "e", "--feedback", text)
        row = _events(run_dir, "s1")[-1]
        assert row["feedback"] == "none", f"{text!r} -> {row['feedback']}"
        assert row["feedback_to"] == [], f"{text!r} -> {row['feedback_to']}"
        (run_dir / "s1.json").unlink()


def test_a_real_filing_still_registers_its_beats(run_dir: Path) -> None:
    for text, beats in (
        ("filed 01M11 to intel", ["intel"]),
        ("sent a finding to fleet", ["fleet"]),
        ("routed to infra and intel", ["infra", "intel"]),
        ("none for infra, but filed to fleet", ["fleet", "infra"]),  # a mixed line HAS filed
    ):
        _start(run_dir)
        _cr(run_dir, "done", "--command", "fabrik-probe", "--evidence", "e", "--feedback", text)
        row = _events(run_dir, "s1")[-1]
        assert row["feedback"] == "filed", f"{text!r} -> {row['feedback']}"
        assert sorted(row["feedback_to"]) == sorted(beats), f"{text!r} -> {row['feedback_to']}"
        (run_dir / "s1.json").unlink()


def test_the_stop_hooks_remedy_advertises_a_runnable_close() -> None:
    """The hook prints the way OUT of a blocked turn. Since the close now REFUSES without
    `--feedback`, a remedy missing it tells a stuck agent to run a command that cannot succeed —
    the record stays `running`, the hook fires again, and the loop has no exit.

    Both exits are asserted because the fix reached `done` and left `blocked` for a full review
    round, and `blocked` is the one a genuinely stuck agent reaches for. `check_command_corpus`
    predicate 7 polices the command corpus, but the hook is not corpus — this is its only guard.
    """
    import ast

    src = _HOOK.read_text(encoding="utf-8")
    ast.parse(src)  # a SyntaxError here disarms the whole enforcement mesh, silently

    i = src.index("COMMAND STILL RUNNING")
    block = src[i : src.index("\n    )", i)]
    for verb in ("done", "blocked"):
        seg = block[block.index(f"command_run.py {verb}") :]
        seg = seg[: seg.index("command_run.py", 10)] if "command_run.py" in seg[10:] else seg
        assert "--feedback" in seg, f"the hook's {verb} remedy omits --feedback:\n{seg}"


def test_the_phase_gate_accepts_the_dispatcher_mode_ticket_artifact(tmp_path) -> None:
    """`/fabrik-execute-plan` § D4 mandates `<plan>-T<id>-review.md` in dispatcher mode — there is
    no `phase-<N>` there, and its § Plan Status Tracking says the phase-boundary bullet does not
    apply. Accepting only the phase form made the two contracts unsatisfiable together: an executor
    naming artifacts correctly per D4 could never satisfy `step`, and one that satisfied `step` had
    misnamed them (transdoc, 2026-08-28). The refusal also cited check_review_coverage as needing
    the phase name — it rglobs every .md under reviews/ and has no phase filter at all."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("cr_gate", _SCRIPT)
    cr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cr)

    d = tmp_path / "docs" / "development" / "reviews"
    d.mkdir(parents=True)
    (d / "2026-08-28-plan-1-thing-T02-review.md").write_text("real content\n", encoding="utf-8")
    assert cr._phase_review_exists(str(tmp_path), 1), "a D4 ticket artifact must satisfy the gate"


def test_the_phase_gate_still_requires_some_artifact(tmp_path) -> None:
    """The precision side: loosening the pattern must not make the gate vacuous."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("cr_gate2", _SCRIPT)
    cr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cr)

    d = tmp_path / "docs" / "development" / "reviews"
    d.mkdir(parents=True)
    (d / "unrelated-notes.md").write_text("nothing to do with a review\n", encoding="utf-8")
    assert not cr._phase_review_exists(str(tmp_path), 1)


def test_a_run_advancing_phases_with_zero_rounds_is_noticed(run_dir: Path) -> None:
    """job-agent, 2026-08-28: NINE discovery rounds ran with zero recorded, and nothing noticed —
    found only when a round-9 call printed "ROUND 1 recorded". Every round advisory (oscillation,
    terminal verdict) keys on `round`, so an agent that never calls it gets silence and reads
    silence as approval. Their framing: a convergence check depending on a voluntary call from the
    agent whose judgement it checks is load-bearing on the wrong party."""
    _cr(run_dir, "start", "--command", _PROBE, "--phases", "5", "--terminal", "t")
    quiet = _cr(run_dir, "step", "--phase", "2", "--title", "early")
    assert "ZERO rounds" not in quiet.stderr, "a normal two-phase run must stay quiet"
    noisy = _cr(run_dir, "step", "--phase", "3", "--title", "later")
    assert "ZERO rounds recorded" in noisy.stderr, noisy.stderr


def test_the_zero_rounds_notice_stops_once_a_round_is_recorded(run_dir: Path) -> None:
    _cr(run_dir, "start", "--command", _PROBE, "--phases", "5", "--terminal", "t")
    _cr(run_dir, "round", "--findings", "2", "--classes-swept", "a", "--classes-new", "b")
    out = _cr(run_dir, "step", "--phase", "4", "--title", "after")
    assert "ZERO rounds" not in out.stderr, out.stderr


def test_the_zero_rounds_notice_never_refuses(run_dir: Path) -> None:
    """ADVISORY by design: a one-shot command legitimately records no rounds, and trapping it
    would be worse than the silence it replaces."""
    _cr(run_dir, "start", "--command", _PROBE, "--phases", "5", "--terminal", "t")
    assert _cr(run_dir, "step", "--phase", "3", "--title", "x").returncode == 0


def test_a_nothing_sentinel_is_not_recorded_as_a_class_name() -> None:
    """youtube, 2026-08-28, reproduced twice in one session across two commands: a genuinely clean
    round passing `--classes-new "none"` recorded the LITERAL string as an open class, so
    `classes open: dashboard-screens-missing, …, none` — the sentinel sat in the open list forever
    and the loop could never retire it. The ledger contradicted the round it was recording."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("cr_csv", _SCRIPT)
    cr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cr)

    for sentinel in ("none", "none-yet", "nothing", "n/a", "NA", "-", "0", "None"):
        assert cr._csv(sentinel) == [], f"{sentinel!r} must not become a class"


def test_a_sentinel_mixed_with_real_classes_drops_only_the_sentinel() -> None:
    """The precision side: dropping the whole list would lose real classes."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("cr_csv2", _SCRIPT)
    cr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cr)
    assert cr._csv("a,none,b") == ["a", "b"]
    assert cr._csv("dashboard-screens-missing,webhook-false-claim") == [
        "dashboard-screens-missing",
        "webhook-false-claim",
    ]
