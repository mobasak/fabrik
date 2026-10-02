"""T08 — `command_run.py` wired to `task_lane` (plan 2026-10-02-plan-1): the lane v2 `start`.

Every grader drives the real script in a subprocess against a throwaway `COMMAND_RUN_DIR` and a
throwaway git repo (`tests/test_command_run_fabrik_task.py`'s harness, reused): the live state
dir is never written and no `$HOME`-rooted `.claude*` path is read. The lane switch is the
FIXTURE repo's own `.fabrik/lane.json`, so the hub's switch never leaks into a grader.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.test_command_run_fabrik_task import _cr, _rec, _start

_V2 = "decision=yes,heavy=no,mechanism=no,oneway=no,tradeoffs=no,consumers=internal"


def _git(repo: Path, *a: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *a],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout.strip()


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    d = tmp_path / "state" / "command-runs"
    d.mkdir(parents=True)
    return d


def _repo(tmp_path: Path, *, lane: int | None) -> Path:
    r = tmp_path / "repo"
    (r / "src").mkdir(parents=True)
    (r / "api").mkdir()
    for n in "abcdefgh":
        (r / "src" / f"{n}.py").write_text("x = 1\n", encoding="utf-8")
    (r / "api" / "openapi.yaml").write_text("openapi: 3.1.0\n", encoding="utf-8")
    _git(r, "init", "-q", "-b", "master")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "base")
    if lane is not None:
        (r / ".fabrik").mkdir()
        (r / ".fabrik" / "lane.json").write_text(json.dumps({"version": lane}), encoding="utf-8")
        _git(r, "add", ".fabrik/lane.json")
        _git(r, "commit", "-qm", "lane switch")
    return r


def _files(*names: str) -> list[str]:
    out: list[str] = []
    for n in names:
        out += ["--file", n]
    return out


def _ledger(run_dir: Path) -> list[dict]:
    p = run_dir.parent / "lane-refusals.jsonl"
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln]


def test_without_a_switch_the_start_is_v1_and_stamps_nothing(run_dir: Path, tmp_path: Path) -> None:
    """Row 1 (D12 OFF state). No `.fabrik/lane.json`: a 4-file start is today's `files > 3`
    refusal, a 1-file start opens a record with no `gate` key and prints `lane: v1`."""
    repo = _repo(tmp_path, lane=None)
    four = _files("src/a.py", "src/b.py", "src/c.py", "src/d.py")
    r = _cr(run_dir, *_start(*four, "--declare", _V2), cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "REFUSED — fabrik-task: files > 3 → /fabrik-spec" in r.stdout
    r = _cr(run_dir, *_start("--file", "src/a.py", "--declare", _V2), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "lane: v1" in r.stdout.splitlines()
    assert "gate" not in _rec(run_dir)["declared"]
    assert _ledger(run_dir) == []


def test_v1_ignores_the_v2_flags_with_a_note(run_dir: Path, tmp_path: Path) -> None:
    """Command text naming `--appetite` must keep working in a repo that has not opted in."""
    repo = _repo(tmp_path, lane=None)
    r = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", _V2, "--appetite", "60"),
        cwd=repo,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "--appetite ignored — this repo runs lane v1" in r.stderr
    assert "appetite" not in _rec(run_dir)["declared"]


def test_v2_admits_a_six_file_feature_and_names_the_switch_commit(
    run_dir: Path, tmp_path: Path
) -> None:
    """Row 2 (V1). With the switch at version 2 a 6-file start is admitted, stamped `gate: 2`
    with the full review it owes (> 5 files), and `start` prints `lane: v2` and the commit that
    set the switch."""
    repo = _repo(tmp_path, lane=2)
    switch = _git(repo, "rev-parse", "HEAD")
    six = _files(*(f"src/{n}.py" for n in "abcdef"))
    r = _cr(run_dir, *_start(*six, "--declare", _V2, "--appetite", "90"), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"lane: v2 (switch {switch}) · review: full · appetite: 90 min" in r.stdout
    d = _rec(run_dir)["declared"]
    assert (d["gate"], d["review"], d["appetite"], d["consumers"]) == (2, "full", 90, "internal")
    assert d["lane_switch"] == switch
    assert len(d["files"]) == 6


def test_v2_five_files_owe_the_scoped_review_and_the_default_appetite(
    run_dir: Path, tmp_path: Path
) -> None:
    """The full-review boundary is > 5: five files are the scoped review."""
    repo = _repo(tmp_path, lane=2)
    five = _files(*(f"src/{n}.py" for n in "abcde"))
    r = _cr(run_dir, *_start(*five, "--declare", _V2), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    d = _rec(run_dir)["declared"]
    assert (d["review"], d["appetite"]) == ("scoped", 240)


def test_v2_tradeoffs_with_why_is_ledgered_and_refused(run_dir: Path, tmp_path: Path) -> None:
    """Row 2 (V9; W-25318990). `tradeoffs=yes` with `--why` routes to the chain, and the refusal
    is written as one row of the ledger under the state dir's PARENT, carrying the why, the
    files, the session and the repo's git common dir — and its id is printed."""
    repo = _repo(tmp_path, lane=2)
    decl = _V2.replace("tradeoffs=no", "tradeoffs=yes")
    r = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", decl, "--why", "queue vs cron"),
        cwd=repo,
    )
    assert r.returncode == 1, r.stdout + r.stderr
    rows = _ledger(run_dir)
    assert len(rows) == 1
    row = rows[0]
    assert row["why"] == "queue vs cron"
    assert row["files"] == ["src/a.py"]
    assert row["session"] == "s1"
    assert row["route"] == "chain: tradeoffs"
    assert Path(row["repo"]) == (repo / ".git").resolve()
    assert f"REFUSED — fabrik-task: tradeoffs → /fabrik-spec (refusal {row['id']})" in r.stdout
    assert not (run_dir / "s1.json").exists()


def test_v2_tradeoffs_without_why_is_refused_naming_the_flag(run_dir: Path, tmp_path: Path) -> None:
    repo = _repo(tmp_path, lane=2)
    decl = _V2.replace("tradeoffs=no", "tradeoffs=yes")
    r = _cr(run_dir, *_start("--file", "src/a.py", "--declare", decl), cwd=repo)
    assert r.returncode == 1
    assert "--why is required with tradeoffs=yes" in r.stdout
    assert _ledger(run_dir) == []


def test_v2_a_contract_path_is_the_chain_and_ledgered(run_dir: Path, tmp_path: Path) -> None:
    repo = _repo(tmp_path, lane=2)
    r = _cr(run_dir, *_start("--file", "api/openapi.yaml", "--declare", _V2), cwd=repo)
    assert r.returncode == 1
    assert "contract: api/openapi.yaml → /fabrik-spec" in r.stdout
    assert [row["route"] for row in _ledger(run_dir)] == ["chain: contract"]


def test_v2_a_missing_consumers_key_is_refused(run_dir: Path, tmp_path: Path) -> None:
    repo = _repo(tmp_path, lane=2)
    decl = _V2.replace(",consumers=internal", "")
    r = _cr(run_dir, *_start("--file", "src/a.py", "--declare", decl), cwd=repo)
    assert r.returncode == 1
    assert "missing --declare keys: consumers" in r.stdout
    assert not (run_dir / "s1.json").exists()


def test_v2_from_downgrade_is_recorded(run_dir: Path, tmp_path: Path) -> None:
    repo = _repo(tmp_path, lane=2)
    r = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", _V2, "--from-downgrade", "LR-0a1b2c3d"),
        cwd=repo,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rec(run_dir)["declared"]["from_downgrade"] == "LR-0a1b2c3d"


def test_the_v2_flags_are_refused_under_any_other_command(run_dir: Path, tmp_path: Path) -> None:
    repo = _repo(tmp_path, lane=2)
    for flag, val in (("--appetite", "30"), ("--why", "x"), ("--from-downgrade", "LR-1")):
        r = _cr(
            run_dir,
            "start",
            "--command",
            "fabrik-review",
            "--phases",
            "3",
            flag,
            val,
            cwd=repo,
        )
        assert r.returncode == 1, flag
        assert "belong to --command fabrik-task" in r.stdout


# ---------------------------------------------------------------- the v2 close (row 3, row 6)

_FB = "confusion: none · waste: none · change: none · filed: none — surfaces exercised: the lane"


def _rows(run_dir: Path) -> list[dict]:
    p = run_dir.parent / "command-feedback.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _edit_commit(repo: Path, rel: str, text: str) -> str:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    _git(repo, "add", "--", rel)
    _git(repo, "commit", "-qm", f"edit {rel}")
    return _git(repo, "rev-parse", "HEAD")


def _design(run_dir: Path, repo: Path, approach: str, mirror: str = "none") -> None:
    d = repo.parent / "design.md"
    d.write_text(
        f"PROBLEM: x\nAPPROACH: {approach}\nDECISION: reversible\nMIRROR: {mirror}\n"
        "OUT: none\nTERMINAL: green\n\n## Behaviours\n- one — `tests/test_x.py::test_one`\n",
        encoding="utf-8",
    )
    r = _cr(run_dir, "step", "--phase", "2", "--title", "design", "--design", str(d), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr


def _close(run_dir: Path, repo: Path, verb: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return _cr(run_dir, verb, "--command", "fabrik-task", *extra, "--feedback", _FB, cwd=repo)


def _started_v2(run_dir: Path, tmp_path: Path, *extra: str) -> Path:
    repo = _repo(tmp_path, lane=2)
    r = _cr(run_dir, *_start("--file", "src/a.py", "--declare", _V2, *extra), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    return repo


def test_v2_done_refuses_an_undeclared_path_until_it_is_amended(
    run_dir: Path, tmp_path: Path
) -> None:
    """Row 3 (V4, D3.3). Two commits: the second touches `src/b.py`, which the design never
    named — `done --commit A B` is refused naming it; one `--design-amend` later it closes, and
    the row counts the amendment and the lines added."""
    repo = _started_v2(run_dir, tmp_path)
    _design(run_dir, repo, "edit `src/a.py`")
    a = _edit_commit(repo, "src/a.py", "x = 2\n")
    b = _edit_commit(repo, "src/b.py", "x = 2\ny = 3\n")
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", a, b)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "not named in the design note's APPROACH or MIRROR: src/b.py" in r.stdout
    assert _rec(run_dir)["state"] == "running"
    r = _cr(run_dir, "step", "--phase", "2", "--design-amend", "src/b.py", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", a, b)
    assert r.returncode == 0, r.stdout + r.stderr
    row = _rows(run_dir)[-1]
    assert (row["design_amends"], row["loc_added"], row["oversized_mini"]) == ("1", "3", "0")
    assert row["over_appetite"] == "no"


def test_v2_a_contract_hit_at_close_owes_a_receipt_and_blocked_does_not(
    run_dir: Path, tmp_path: Path
) -> None:
    """Row 3 (V3, D1; W-0a89f069). A commit touching a contract path, declared
    `consumers=internal` and named in the design, is a close-time contract hit: `done` is refused
    until `--review` names a full-review receipt; `blocked` closes without one and records the
    upgrade."""
    repo = _started_v2(run_dir, tmp_path)
    _design(run_dir, repo, "edit `src/a.py` and `api/openapi.yaml`")
    c = _edit_commit(repo, "api/openapi.yaml", "openapi: 3.1.1\n")
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", c)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "UPGRADE: contract — api/openapi.yaml" in r.stdout
    assert "done needs --review" in r.stdout
    r = _close(run_dir, repo, "blocked", "--reason", "missing infra", "--commit", c)
    assert r.returncode == 0, r.stdout + r.stderr
    row = _rows(run_dir)[-1]
    assert (row["upgrade"], row["upgrades"]) == ("contract", "contract")


def test_v2_a_valid_full_review_receipt_buys_the_contract_close(
    run_dir: Path, tmp_path: Path
) -> None:
    """Row 3. The same contract hit closes `done` once `--review` names a CONVERGED
    `/fabrik-review` receipt whose surface contains the commit; an unfinished receipt is refused
    with the receipt check's reason."""
    import sys

    from tests.test_review_receipt import _complete
    from tests.test_task_lane_receipt import RECEIPT_SCRIPT, REL

    repo = _started_v2(run_dir, tmp_path)
    _design(run_dir, repo, "edit `src/a.py` and `api/openapi.yaml`")
    base = _git(repo, "rev-parse", "HEAD")
    c = _edit_commit(repo, "api/openapi.yaml", "openapi: 3.1.1\n")
    out = repo / REL
    made = subprocess.run(
        [
            sys.executable,
            str(RECEIPT_SCRIPT),
            "--init",
            "--project-root",
            str(repo),
            "--out",
            str(out),
            "--changed",
            "api/openapi.yaml",
            "--range",
            f"{base}..{c}",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert made.returncode == 0, made.stderr
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", c, "--review", REL)
    assert r.returncode == 1, "an unfinished receipt must not buy the close"
    assert "REFUSED — fabrik-task: --review" in r.stdout
    out.write_text(_complete(out.read_text(encoding="utf-8")), encoding="utf-8")
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", c, "--review", REL)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rows(run_dir)[-1]["upgrade"] == "contract"


def test_v2_the_row_carries_from_downgrade_and_the_evidence_upgrade_token(
    run_dir: Path, tmp_path: Path
) -> None:
    """Row 6. `--from-downgrade` reaches the close row; an evidence `UPGRADE:` token keeps its
    single-token `upgrade` field."""
    repo = _started_v2(run_dir, tmp_path, "--from-downgrade", "LR-0a1b2c3d")
    _design(run_dir, repo, "edit `src/a.py`")
    a = _edit_commit(repo, "src/a.py", "x = 2\n")
    r = _close(run_dir, repo, "done", "--evidence", "UPGRADE: heavy — green", "--commit", a)
    assert r.returncode == 0, r.stdout + r.stderr
    row = _rows(run_dir)[-1]
    assert (row["from_downgrade"], row["upgrade"]) == ("LR-0a1b2c3d", "heavy")
    assert "upgrades" not in row


def test_review_and_several_commits_are_refused_on_a_v1_run(run_dir: Path, tmp_path: Path) -> None:
    """The unstamped close stays today's: one commit, no receipt."""
    repo = _repo(tmp_path, lane=None)
    r = _cr(run_dir, *_start("--file", "src/a.py", "--declare", _V2), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    a = _edit_commit(repo, "src/a.py", "x = 2\n")
    b = _edit_commit(repo, "src/a.py", "x = 3\n")
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", a, b)
    assert r.returncode == 1
    assert "this run is lane v1 — pass ONE --commit" in r.stdout
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", b, "--review", "x.md")
    assert r.returncode == 1
    assert "--review needs a lane v2 run" in r.stdout


# ---------------------------------------------------------------- appetite (row 5) and row fields (row 6)


def _age(run_dir: Path, minutes: int, *, mark: bool = False, sid: str = "s1") -> None:
    """Move the record's clock back: the run's start, or the open phase mark's start."""
    import time as _t

    p = run_dir / f"{sid}.json"
    rec = json.loads(p.read_text(encoding="utf-8"))
    when = _t.time() - minutes * 60
    if mark:
        rec["phase_marks"][-1]["started"] = when
    else:
        rec["started_epoch"] = when
    p.write_text(json.dumps(rec), encoding="utf-8")


def test_v2_task_line_shows_elapsed_over_appetite_and_the_order_past_2x(
    run_dir: Path, tmp_path: Path
) -> None:
    """Row 5 (V6, D4). A task started `--appetite 60`: at 61 minutes `line` shows the elapsed
    segment with no order; at 121 it carries the UPGRADE order, and the close records
    `over_appetite: yes` and the `appetite` upgrade."""
    repo = _started_v2(run_dir, tmp_path, "--appetite", "60")
    _design(run_dir, repo, "edit `src/a.py`")
    _age(run_dir, 61)
    line = _cr(run_dir, "line", cwd=repo).stdout
    assert " · elapsed 61/60" in line and "past 2×" not in line
    _age(run_dir, 121)
    line = _cr(run_dir, "line", cwd=repo).stdout
    assert " · elapsed 121/60 ⚠️ past 2× — UPGRADE: appetite" in line
    a = _edit_commit(repo, "src/a.py", "x = 2\n")
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", a)
    assert r.returncode == 0, r.stdout + r.stderr
    row = _rows(run_dir)[-1]
    assert (row["over_appetite"], row["upgrade"]) == ("yes", "appetite")


def test_v2_a_plan_phase_appetite_marks_and_counts_the_overrun(
    run_dir: Path, tmp_path: Path
) -> None:
    """Row 5 (V10, D11). An execute-plan phase entered `step --appetite 30`: at 61 minutes `line`
    prints the re-plan order; the next phase ends the mark; the close counts one mark and one
    overrun."""
    repo = _repo(tmp_path, lane=2)
    r = _cr(run_dir, "start", "--command", "fabrik-execute-plan", "--phases", "3", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    r = _cr(run_dir, "step", "--phase", "1", "--title", "one", "--appetite", "30", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    _age(run_dir, 61, mark=True)
    line = _cr(run_dir, "line", cwd=repo).stdout
    assert "(one) · elapsed 61/30 ⚠️ past 2× — stop and re-plan the rest of THIS phase" in line
    r = _cr(run_dir, "step", "--phase", "2", "--title", "two", cwd=repo)
    assert "elapsed" not in r.stdout, "the next phase ends the mark"
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-execute-plan",
        "--evidence",
        "x",
        "--feedback",
        _FB,
        cwd=repo,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    row = _rows(run_dir)[-1]
    assert (row["phase_marks"], row["over_appetite_phases"]) == ("1", "1")


def test_v1_step_appetite_is_ignored_and_the_row_keeps_its_shape(
    run_dir: Path, tmp_path: Path
) -> None:
    """Row 1 (D12 OFF state) for D11: no switch, so `--appetite` is noted and nothing is marked."""
    repo = _repo(tmp_path, lane=None)
    _cr(run_dir, "start", "--command", "fabrik-execute-plan", "--phases", "3", cwd=repo)
    r = _cr(run_dir, "step", "--phase", "1", "--title", "one", "--appetite", "30", cwd=repo)
    assert r.returncode == 0
    assert "--appetite ignored — this repo runs lane v1" in r.stderr
    _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-execute-plan",
        "--evidence",
        "x",
        "--feedback",
        _FB,
        cwd=repo,
    )
    row = _rows(run_dir)[-1]
    assert "phase_marks" not in row and "parent" not in row


def test_v2_a_nested_review_row_names_its_parent_and_a_small_spec_its_size(
    run_dir: Path, tmp_path: Path
) -> None:
    """Row 6. A `/fabrik-review` nested under a running `/fabrik-task` writes `parent:
    fabrik-task`; a `/fabrik-spec` close on a spec carrying `Size: small` writes `size: small`."""
    repo = _started_v2(run_dir, tmp_path)
    r = _cr(run_dir, "start", "--command", "fabrik-review", "--phases", "3", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    _cr(run_dir, "round", "--findings", "0", "--confirmed", "0", cwd=repo)
    r = _cr(
        run_dir,
        "blocked",
        "--command",
        "fabrik-review",
        "--reason",
        "missing infra",
        "--feedback",
        _FB,
        cwd=repo,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rows(run_dir)[-1]["parent"] == "fabrik-task"

    spec = repo / "docs" / "superpowers" / "specs" / "2026-10-02-x-design.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        "# X\n\n**Status:** DRAFT\nSize: small (≈200 lines, 3 files)\n\n## Goal\n", encoding="utf-8"
    )
    r = _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-spec",
        "--phases",
        "7",
        "--surface",
        "docs/superpowers/specs/2026-10-02-x-design.md",
        cwd=repo,
        sid="s2",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-spec",
        "--evidence",
        "x",
        "--feedback",
        _FB,
        cwd=repo,
        sid="s2",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rows(run_dir)[-1]["size"] == "small"


# ---------------------------------------------------------------- the nested review (row 4) and --surface


def _review_rounds(run_dir: Path, repo: Path) -> str:
    r = _cr(run_dir, "start", "--command", "fabrik-review", "--phases", "3", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    r = _cr(run_dir, "round", "--findings", "5", "--confirmed", "5", "--own-fix", "0", cwd=repo)
    assert "SCOPE GROWTH" not in r.stdout, "round 1 is the full pass"
    r = _cr(run_dir, "round", "--findings", "2", "--confirmed", "2", "--own-fix", "2", cwd=repo)
    return r.stdout


def test_v2_a_review_nested_under_a_task_stops_at_its_first_own_fix_round(
    run_dir: Path, tmp_path: Path
) -> None:
    """Row 4 (V8, D8). Under a running `/fabrik-task` an own-fix-only round 2 prints the in-lane
    stop; the same two rounds with no task parent print nothing (the ordinary window needs 3)."""
    repo = _started_v2(run_dir, tmp_path)
    out = _review_rounds(run_dir, repo)
    assert "SCOPE GROWTH (in-lane) — round 2 confirmed ONLY defects inside" in out
    assert "mostly" not in out.split("SCOPE GROWTH (in-lane)")[1].split("\n")[0]

    other = tmp_path / "other-state" / "command-runs"
    other.mkdir(parents=True)
    out = _review_rounds(other, repo)
    assert "SCOPE GROWTH" not in out


def test_v1_a_nested_review_keeps_the_ordinary_window(run_dir: Path, tmp_path: Path) -> None:
    """Row 1 (D12 OFF state) for D8."""
    repo = _repo(tmp_path, lane=None)
    r = _cr(run_dir, *_start("--file", "src/a.py", "--declare", _V2), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SCOPE GROWTH" not in _review_rounds(run_dir, repo)


@pytest.mark.parametrize("command", ["fabrik-spec-review", "fabrik-plan-review"])
def test_v2_spec_and_plan_review_need_a_surface(
    run_dir: Path, tmp_path: Path, command: str
) -> None:
    """Row 6 (W-25318990). At v2 the start without `--surface` is refused naming the flag; with
    it, it opens; at v1 the bare start opens as before."""
    repo = _repo(tmp_path, lane=2)
    r = _cr(run_dir, "start", "--command", command, "--phases", "3", cwd=repo)
    assert r.returncode == 1
    assert f"REFUSED — {command}: --surface <the spec or plan path> is required" in r.stdout
    r = _cr(run_dir, "start", "--command", command, "--phases", "3", "--surface", "x.md", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    v1 = _repo(tmp_path / "v1", lane=None)
    other = tmp_path / "v1-state" / "command-runs"
    other.mkdir(parents=True)
    r = _cr(other, "start", "--command", command, "--phases", "3", cwd=v1)
    assert r.returncode == 0, r.stdout + r.stderr


def test_v2_a_spec_downgrade_handoff_names_its_refusal(run_dir: Path, tmp_path: Path) -> None:
    """D9 / T06's join: a `/fabrik-spec` handoff whose reason opens `DOWNGRADE: <refusal id>`
    writes `from_downgrade` on its row; any other reason writes nothing."""
    repo = _repo(tmp_path, lane=2)
    seed = repo / "docs" / "seed.md"
    seed.parent.mkdir(parents=True, exist_ok=True)
    seed.write_text(
        "# seed\n\n## RESUME\n- /fabrik-task --from-downgrade LR-0a1b2c3d\n", encoding="utf-8"
    )
    for sid, reason, want in (
        ("s1", "DOWNGRADE: LR-0a1b2c3d — one reversible decision", "LR-0a1b2c3d"),
        ("s2", "the brief needs a design after all", None),
    ):
        r = _cr(run_dir, "start", "--command", "fabrik-spec", "--phases", "7", cwd=repo, sid=sid)
        assert r.returncode == 0, r.stdout + r.stderr
        r = _cr(
            run_dir,
            "handoff",
            "--command",
            "fabrik-spec",
            "--resume",
            "docs/seed.md",
            "--reason",
            reason,
            "--feedback",
            _FB,
            cwd=repo,
            sid=sid,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        assert _rows(run_dir)[-1].get("from_downgrade") == want


def test_v2_the_in_lane_stop_needs_an_own_fix_only_round_and_a_review(
    run_dir: Path, tmp_path: Path
) -> None:
    """T04-O5/O6: a round that is only MOSTLY own-fix (2 of 3) does not take the in-lane stop,
    and a non-review command nested under the task keeps the ordinary window."""
    repo = _started_v2(run_dir, tmp_path)
    r = _cr(run_dir, "start", "--command", "fabrik-review", "--phases", "3", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    _cr(run_dir, "round", "--findings", "5", "--confirmed", "5", "--own-fix", "0", cwd=repo)
    r = _cr(run_dir, "round", "--findings", "3", "--confirmed", "3", "--own-fix", "2", cwd=repo)
    assert "SCOPE GROWTH (in-lane)" not in r.stdout

    other = tmp_path / "s2" / "command-runs"
    other.mkdir(parents=True)
    repo2 = _repo(tmp_path / "two", lane=2)
    r = _cr(other, *_start("--file", "src/a.py", "--declare", _V2), cwd=repo2)
    assert r.returncode == 0, r.stdout + r.stderr
    r = _cr(other, "start", "--command", "fabrik-doc-converge", "--phases", "3", cwd=repo2)
    assert r.returncode == 0, r.stdout + r.stderr
    _cr(other, "round", "--findings", "5", "--confirmed", "5", "--own-fix", "0", cwd=repo2)
    r = _cr(other, "round", "--findings", "2", "--confirmed", "2", "--own-fix", "2", cwd=repo2)
    assert "SCOPE GROWTH (in-lane)" not in r.stdout


def test_the_documented_multi_commit_close_parses_as_separate_shas(tmp_path: Path) -> None:
    """T07-S3, routed to T08 (where the space-separated parser lives): the command text's capture
    file APPENDS each commit and is expanded UNQUOTED, so a two-commit run reaches `--commit` as two
    arguments — executed through bash and the real parser, never matched as prose."""
    import importlib.util
    import re as _re
    import sys as _sys

    root = Path(__file__).resolve().parents[1]
    src = (root / "commands/_sources/fabrik-task.md").read_text(encoding="utf-8")
    assert "git rev-parse -q --verify HEAD >> <scratchpad>" in src, "the capture must append"
    m = _re.search(r"--commit (\$\(cat <scratchpad>[^)]*\))", src)
    assert m, "the done line must expand the capture file UNQUOTED"
    cap = tmp_path / "commit.sha"
    cap.write_text("aaaa111\nbbbb222\n", encoding="utf-8")
    expr = m.group(1).replace(m.group(1)[6:-1], str(cap))
    words = subprocess.run(
        ["bash", "-c", f'printf "%s\\n" --commit {expr}'],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    ).stdout.split()
    spec = importlib.util.spec_from_file_location("_cr_parse", root / "scripts/command_run.py")
    cr = importlib.util.module_from_spec(spec)
    _sys.modules["_cr_parse"] = cr
    spec.loader.exec_module(cr)
    args = cr._build_parser().parse_args(
        ["done", "--command", "fabrik-task", "--evidence", "x", *words]
    )
    assert args.commit == ["aaaa111", "bbbb222"]


def test_v2_a_failed_measurement_refuses_done_and_lets_blocked_close(
    run_dir: Path, tmp_path: Path
) -> None:
    """Whole-plan review D-O2/A-O2/B-O3: on a gate-2 record a measurement that cannot run (here a
    corrupt declared appetite) must not accept `done` — it would admit an unreviewed contract hit;
    `blocked` still closes, and its row still reads as a v2 close."""
    repo = _started_v2(run_dir, tmp_path)
    _design(run_dir, repo, "edit `src/a.py`")
    a = _edit_commit(repo, "src/a.py", "x = 2\n")
    p = run_dir / "s1.json"
    rec = json.loads(p.read_text(encoding="utf-8"))
    rec["declared"]["appetite"] = "not-a-number"
    p.write_text(json.dumps(rec), encoding="utf-8")
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", a)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "the lane v2 close could not measure the run (ValueError)" in r.stdout
    assert _rec(run_dir)["state"] == "running"
    r = _close(run_dir, repo, "blocked", "--reason", "missing infra", "--commit", a)
    assert r.returncode == 0, r.stdout + r.stderr
    row = _rows(run_dir)[-1]
    assert (row["oversized_mini"], row["over_appetite"]) == ("unmeasurable=no-git", "unmeasurable")


def test_v2_from_downgrade_must_be_a_refusal_id(run_dir: Path, tmp_path: Path) -> None:
    """D7 A-O5: the report joins on this id, so a free string is refused."""
    repo = _repo(tmp_path, lane=2)
    r = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", _V2, "--from-downgrade", "whatever"),
        cwd=repo,
    )
    assert r.returncode == 1
    assert "is not a refusal id (LR-xxxxxxxx)" in r.stdout


def test_a_late_surface_still_sizes_the_spec_and_a_stamped_run_keeps_v2_fields(
    run_dir: Path, tmp_path: Path
) -> None:
    """D7 A-O1: `done --surface` names the spec at close and the row still carries `size`.
    D7 A-O4: a run stamped gate 2 keeps its v2 row fields after the switch is removed."""
    repo = _repo(tmp_path, lane=2)
    spec = repo / "docs" / "superpowers" / "specs" / "2026-10-02-y-design.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# Y\n\n**Status:** DRAFT\nSize: small\n\n## Goal\n", encoding="utf-8")
    r = _cr(run_dir, "start", "--command", "fabrik-spec", "--phases", "7", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    rel = "docs/superpowers/specs/2026-10-02-y-design.md"
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-spec",
        "--evidence",
        "x",
        "--surface",
        rel,
        "--feedback",
        _FB,
        cwd=repo,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rows(run_dir)[-1].get("size") == "small"

    other = tmp_path / "o" / "command-runs"
    other.mkdir(parents=True)
    repo2 = _repo(tmp_path / "two", lane=2)
    r = _cr(other, *_start("--file", "src/a.py", "--declare", _V2), cwd=repo2)
    assert r.returncode == 0, r.stdout + r.stderr
    r = _cr(other, "start", "--command", "fabrik-review", "--phases", "3", cwd=repo2)
    assert r.returncode == 0, r.stdout + r.stderr
    _git(repo2, "rm", "-q", ".fabrik/lane.json")
    _git(repo2, "commit", "-qm", "switch off")
    r = _cr(
        other,
        "blocked",
        "--command",
        "fabrik-review",
        "--reason",
        "missing infra",
        "--feedback",
        _FB,
        cwd=repo2,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rows(other)[-1].get("parent") == "fabrik-task"


def test_an_absolute_review_path_is_compared_repo_relative(tmp_path: Path) -> None:
    """D7 B-O2: the `--review` path the close exempts is spelled as the committed rows spell it —
    an absolute path inside the repo is relativised; one outside is kept for the receipt check to
    refuse."""
    import importlib.util
    import sys as _sys

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("_cr_rel", root / "scripts/command_run.py")
    cr = importlib.util.module_from_spec(spec)
    _sys.modules["_cr_rel"] = cr
    spec.loader.exec_module(cr)
    repo = tmp_path / "r"
    (repo / "docs").mkdir(parents=True)
    inside = repo / "docs" / "x-review.md"
    assert cr._repo_rel(repo, str(inside)) == "docs/x-review.md"
    assert cr._repo_rel(repo, "/elsewhere/y.md") == "/elsewhere/y.md"
    assert cr._repo_rel(repo, None) is None
    link = tmp_path / "link"
    link.symlink_to(repo, target_is_directory=True)
    assert cr._repo_rel(repo, str(link / "docs" / "x-review.md")) == "docs/x-review.md"


def test_a_present_but_broken_task_lane_says_so_and_runs_v1(run_dir: Path, tmp_path: Path) -> None:
    """D7 A-S2: a task_lane.py that does not import must not downgrade silently."""
    import shutil
    import sys as _sys

    root = Path(__file__).resolve().parents[1]
    tree = tmp_path / "tree" / "scripts"
    tree.mkdir(parents=True)
    shutil.copy(root / "scripts/command_run.py", tree / "command_run.py")
    (tree / "task_lane.py").write_text("this is not python(\n", encoding="utf-8")
    repo = _repo(tmp_path, lane=2)
    r = subprocess.run(
        [
            _sys.executable,
            str(tree / "command_run.py"),
            *_start("--file", "src/a.py", "--declare", _V2),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(repo),
        env={
            "PATH": "/usr/bin:/bin",
            "COMMAND_RUN_DIR": str(run_dir),
            "HOME": str(tmp_path / "home"),
            "CLAUDE_SESSION_ID": "s1",
            "KAIZEN_EVENTS_DIR": str(tmp_path / "ev"),
        },
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "task_lane.py did not import (SyntaxError) — lane v1" in r.stderr
    assert "lane: v1" in r.stdout


def test_v1_admits_exactly_three_files(run_dir: Path, tmp_path: Path) -> None:
    """D7 A-H9: the v1 file cap's boundary — three files start, four are refused (above)."""
    repo = _repo(tmp_path, lane=None)
    r = _cr(
        run_dir, *_start(*_files("src/a.py", "src/b.py", "src/c.py"), "--declare", _V2), cwd=repo
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "lane: v1" in r.stdout.splitlines()


def test_a_stamped_task_keeps_its_v2_row_fields_after_the_switch_is_removed(
    run_dir: Path, tmp_path: Path
) -> None:
    """D7 AB-O3: the record's OWN gate-2 stamp (not only a parent's) keeps the v2 row fields."""
    repo = _started_v2(run_dir, tmp_path)
    r = _cr(run_dir, "step", "--phase", "2", "--title", "d", "--appetite", "30", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    _git(repo, "rm", "-q", ".fabrik/lane.json")
    _git(repo, "commit", "-qm", "switch off")
    r = _close(run_dir, repo, "blocked", "--reason", "missing infra")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rows(run_dir)[-1].get("phase_marks") == "1"
