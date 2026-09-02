# AFTER-EDIT: ../flush_subagent_outboxes.py | ../daily_refresh.sh
"""The fleet-wide outbox walker — driven against a REAL Postgres and REAL outbox files.

Zero-mock policy: a substring assertion on the helper's call would stay green if the walker stopped
looping, stopped passing `receipt_dir`, or stopped walking nested repos. Every test below writes real
JSONL rows to real directories and reads the real table back.

`TEST_DATABASE_URL` must name a throwaway database (the fixture refuses anything without `test` in
its name before touching it) — the same guard `test_canary_grounding_column.py` uses.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS = TESTS_DIR.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parent.parent))

import flush_subagent_outboxes as walker  # noqa: E402

TEST_DSN = os.getenv("TEST_DATABASE_URL", "")
needs_db = pytest.mark.skipif(not TEST_DSN, reason="TEST_DATABASE_URL unset")


@pytest.fixture()
def throwaway_db():
    dbname = TEST_DSN.rstrip("/").rsplit("/", 1)[-1]
    if "test" not in dbname:
        pytest.fail(f"TEST_DATABASE_URL points at a non-throwaway db: {dbname!r}")
    import psycopg
    from libs.subagents.pg_ledger import SUBAGENT_RUNS_DDL

    with psycopg.connect(TEST_DSN) as conn:
        conn.execute(SUBAGENT_RUNS_DDL)
        conn.execute("TRUNCATE subagent_runs")
        conn.commit()
    yield TEST_DSN


def _row(agent_id: str, project: str = "some-run-label") -> str:
    return json.dumps({
        "project": project, "agent_id": agent_id, "task_type": "review",
        "model": "m/x", "provider": "p", "status": "scored", "cost_usd": 0.1,
        "turns": 1, "latency_s": 2.0, "quality_score": 4.0, "tool_calls": "{}",
        "session_id": None,
    })


def _seed(d: Path, *, live: int = 0, residual: int = 0, project: str = "some-run-label") -> None:
    d.mkdir(parents=True, exist_ok=True)
    if live:
        (d / "pg_outbox.jsonl").write_text(
            "\n".join(_row(f"a-{uuid.uuid4().hex[:8]}", project) for _ in range(live)) + "\n",
            encoding="utf-8")
    if residual:
        (d / "pg_outbox.flushing.jsonl").write_text(
            "\n".join(_row(f"r-{uuid.uuid4().hex[:8]}", project) for _ in range(residual)) + "\n",
            encoding="utf-8")


def _count(dsn: str) -> int:
    import psycopg

    with psycopg.connect(dsn) as conn:
        return conn.execute("SELECT count(*) FROM subagent_runs").fetchone()[0]


def _run_walker(root: Path, dsn: str, *extra: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, SUBAGENT_RUNS_DSN=dsn)
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "flush_subagent_outboxes.py"), "--root", str(root), *extra],
        capture_output=True, text=True, env=env,
    )


# ── enumeration ────────────────────────────────────────────────────────────────────────────────
def test_it_walks_nested_repos_a_bounded_glob_would_miss(tmp_path):
    """The population was mis-counted three times, twice by a glob that could not reach a nested
    repo (`/opt/trade-intelligence/web`, `/opt/fabrik-lib/subagents`). Depth is not bounded."""
    _seed(tmp_path / "repoA" / ".tmp" / "subagents", live=2)
    _seed(tmp_path / "repoB" / "web" / ".tmp" / "subagents", live=3)
    _seed(tmp_path / "repoC" / "x" / "y" / ".tmp" / "subagents", live=1)
    found = walker.outbox_dirs(tmp_path)
    assert len(found) == 3, f"a nested outbox was missed: {found}"
    assert sum(walker.pending_rows(d) for d in found) == 6


def test_a_directory_with_no_outbox_file_is_not_walked(tmp_path):
    (tmp_path / "repoA" / ".tmp" / "subagents").mkdir(parents=True)
    (tmp_path / "repoA" / ".tmp" / "subagents" / "ledger.jsonl").write_text("{}\n")
    assert walker.outbox_dirs(tmp_path) == []


def test_the_repo_name_is_derived_from_the_walked_path(tmp_path):
    """The walker is the ONLY place that knows a stranded row's true repo — the row's own `project`
    is a run label (4,435 of 9,327 rows say 'review')."""
    d = tmp_path / "trade-intelligence" / "web" / ".tmp" / "subagents"
    _seed(d, live=1)
    assert walker.repo_of(d, tmp_path) == "trade-intelligence"


# ── the flush itself ───────────────────────────────────────────────────────────────────────────
@needs_db
def test_rows_land_and_the_outbox_is_gone(throwaway_db, tmp_path):
    d = tmp_path / "repoA" / ".tmp" / "subagents"
    _seed(d, live=4)
    p = _run_walker(tmp_path, throwaway_db)
    assert p.returncode == 0, p.stdout + p.stderr
    assert _count(throwaway_db) == 4, p.stdout + p.stderr
    assert not (d / "pg_outbox.jsonl").exists()


@needs_db
def test_both_a_residual_and_a_live_outbox_drain_in_one_run(throwaway_db, tmp_path):
    """`_flush_locked` processes `.flushing` OR live, never both — 'there is NO file-merging'
    (pg_ledger.py:864-869). Four real repos hold both, so a one-shot walker would recover the
    residual and silently leave the live rows for tomorrow. The loop is the fix."""
    d = tmp_path / "repoA" / ".tmp" / "subagents"
    _seed(d, live=3, residual=5)
    p = _run_walker(tmp_path, throwaway_db)
    assert _count(throwaway_db) == 8, f"only one file drained: {p.stdout}{p.stderr}"
    assert not (d / "pg_outbox.jsonl").exists()
    assert not (d / "pg_outbox.flushing.jsonl").exists()


@needs_db
def test_receipts_land_in_the_owning_repo_not_the_hub(throwaway_db, tmp_path):
    """With `receipt_dir` unset, `ledger._receipts_path` falls back to `.tmp/subagents` relative to
    CWD — the hub — so another repo's receipts would be filed against fabrik and the owning repo
    would get none. Receipts are what check_subagent_flywheel.py reconciles against."""
    d = tmp_path / "repoA" / ".tmp" / "subagents"
    _seed(d, live=2)
    _run_walker(tmp_path, throwaway_db)
    assert (d / "receipts.jsonl").is_file(), "receipts were misfiled away from the owning repo"
    assert (d / "receipts.jsonl").read_text(encoding="utf-8").strip(), "receipt file is empty"


@needs_db
def test_one_repos_failure_does_not_stop_the_walk(throwaway_db, tmp_path):
    """Three repos, the middle one unreadable. The other two must still flush."""
    a = tmp_path / "aRepo" / ".tmp" / "subagents"
    b = tmp_path / "bRepo" / ".tmp" / "subagents"
    c = tmp_path / "cRepo" / ".tmp" / "subagents"
    for d in (a, b, c):
        _seed(d, live=2)
    # ⚠️ `chmod 000` on the FILE is not enough — the owner can still `os.replace` it, because rename
    # needs write on the DIRECTORY, not the file. Make the directory itself unwritable so the claim
    # genuinely fails (established while writing this test: the first version's cleanup blew up with
    # FileNotFoundError because the flush had claimed the "unreadable" file anyway).
    b.chmod(0o500)
    try:
        p = _run_walker(tmp_path, throwaway_db)
        assert p.returncode == 0, p.stdout + p.stderr
        assert _count(throwaway_db) == 4, f"a sibling's failure stopped the walk: {p.stdout}"
        assert "bRepo" in p.stdout, "the failing repo must still be NAMED in the enumeration"
    finally:
        b.chmod(0o755)


@needs_db
def test_the_manifest_maps_every_row_back_to_its_repo(throwaway_db, tmp_path):
    """Phase F must backfill repo attribution; the walker is where the repo is known."""
    _seed(tmp_path / "seo" / ".tmp" / "subagents", live=3)
    _seed(tmp_path / "youtube" / ".tmp" / "subagents", live=2)
    mf = tmp_path / "manifest.json"
    _run_walker(tmp_path, throwaway_db, "--manifest", str(mf))
    rows = {r["repo"]: r for r in json.loads(mf.read_text(encoding="utf-8"))}
    assert rows["seo"]["flushed"] == 3
    assert rows["youtube"]["flushed"] == 2


# ── fail-open ──────────────────────────────────────────────────────────────────────────────────
def test_an_unset_dsn_claims_nothing_and_still_exits_zero(tmp_path):
    """It must never claim or delete an outbox it cannot deliver — and it must say so, once,
    rather than reporting `dsn-missing` twenty times."""
    d = tmp_path / "repoA" / ".tmp" / "subagents"
    _seed(d, live=3)
    env = dict(os.environ)
    env["SUBAGENT_RUNS_DSN"] = ""
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "flush_subagent_outboxes.py"), "--root", str(tmp_path)],
        capture_output=True, text=True, env=env,
    )
    assert p.returncode == 0
    assert "SINK UNREACHABLE" in p.stderr, p.stdout + p.stderr
    assert (d / "pg_outbox.jsonl").is_file(), "an undeliverable outbox must NOT be claimed"
    assert "3 row(s) left in place" in p.stderr


def test_an_empty_tree_exits_zero_and_says_so(tmp_path):
    p = _run_walker(tmp_path, "postgresql:///definitely_not_a_db")
    assert p.returncode == 0
    assert "nothing stranded" in p.stdout


@needs_db
def test_an_unreachable_db_exits_zero_and_leaves_the_rows(throwaway_db, tmp_path):
    """Fail-open: a flusher that reds the daily refresh is worse than an unflushed row."""
    d = tmp_path / "repoA" / ".tmp" / "subagents"
    _seed(d, live=2)
    p = _run_walker(tmp_path, "postgresql://nobody@127.0.0.1:1/nope")
    assert p.returncode == 0, p.stdout + p.stderr
    # The rows survive — but in `.flushing`, not the live file: `flush_outbox` CLAIMS the batch with
    # an atomic `os.replace` BEFORE it connects, and "on a DB failure the batch stays in `.flushing`
    # for the next run" (pg_ledger.py:876). Asserting the live filename would be asserting the wrong
    # half of a documented contract.
    survived = (d / "pg_outbox.jsonl").is_file() or (d / "pg_outbox.flushing.jsonl").is_file()
    assert survived, "rows must survive an unreachable sink, in either the live or claimed file"
    kept = sum(
        sum(1 for _ in (d / f).open(encoding="utf-8"))
        for f in ("pg_outbox.jsonl", "pg_outbox.flushing.jsonl")
        if (d / f).is_file()
    )
    assert kept >= 2, f"rows were lost on an unreachable sink: {kept} survived of 2"


def test_an_unwritable_manifest_path_does_not_red_the_daily_refresh(tmp_path):
    """Phase-A review, self-found: the manifest write raised `FileNotFoundError` → exit 1 on an
    unwritable directory. The flush has ALREADY happened by then; killing the step over a reporting
    artifact would red the whole daily refresh, which is precisely what fail-open exists to prevent."""
    _seed(tmp_path / "repoA" / ".tmp" / "subagents", live=1)
    env = dict(os.environ)
    env["SUBAGENT_RUNS_DSN"] = ""
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "flush_subagent_outboxes.py"), "--root", str(tmp_path),
         "--dry-run", "--manifest", "/nonexistent-dir/m.json"],
        capture_output=True, text=True, env=env,
    )
    assert p.returncode == 0, p.stdout + p.stderr


def test_nothing_can_escape_non_zero(tmp_path, monkeypatch):
    """The top-level guard. `_step` in daily_refresh.sh reports the exit code, and a non-zero from
    this helper marks the step failed for a fault never worth stopping the pipeline over."""
    script = SCRIPTS / "flush_subagent_outboxes.py"
    # force an unexpected fault deep inside the walk by making the root a FILE, not a directory
    victim = tmp_path / "not-a-dir"
    victim.write_text("x", encoding="utf-8")
    p = subprocess.run(
        [sys.executable, str(script), "--root", str(victim)],
        capture_output=True, text=True, env=dict(os.environ),
    )
    assert p.returncode == 0, p.stdout + p.stderr


def test_one_repos_crash_does_not_skip_the_repos_after_it(tmp_path, monkeypatch):
    """Phase-A review, finder unit 0: `flush_outbox` documents itself as never-raising, but this
    walk touches ~10 repos it does not own. If the call ever DID raise, every repo after the failing
    one was skipped — and the top-level fail-open guard would exit 0, making a half-finished walk
    look like a completed one. The guard is per-DIRECTORY for that reason."""
    import flush_subagent_outboxes as w

    for name in ("aRepo", "bRepo", "cRepo"):
        _seed(tmp_path / name / ".tmp" / "subagents", live=1)

    calls: list[str] = []
    real = w.pg_ledger.flush_outbox

    def boom(*a, **k):
        d = k.get("outbox_dir", "")
        calls.append(d)
        if "bRepo" in d:
            raise RuntimeError("simulated fault inside the vendored module")
        return real(*a, **k)

    monkeypatch.setattr(w.pg_ledger, "flush_outbox", boom)
    rc = w.main(["--root", str(tmp_path)])
    assert rc == 0
    assert any("aRepo" in c for c in calls) and any("cRepo" in c for c in calls), (
        f"a crash in bRepo skipped a sibling repo: {calls}"
    )
