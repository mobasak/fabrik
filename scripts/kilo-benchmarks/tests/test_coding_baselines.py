"""Phase C Behavior Contract — coding metrics persist + feed selection.

Covers: model_coding_metrics round-trip; load_coding_metrics latest-per-model + fail-soft;
persist_baseline writes the livecodebench 'code' prior; the precedence set that keeps a measured
LiveCodeBench baseline from being clobbered by the terminal-bench scraped build.
All against a TEMP sqlite — no real db, no network, no spend.
"""

import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

import microbench_coding_direct as mcd  # noqa: E402
from build_task_baselines import load_coding_metrics  # noqa: E402


def _score(model: str, pass_at_1: float, n: int = 5) -> mcd.CodingScore:
    return mcd.CodingScore(model, pass_at_1, n_problems=n, n_graded=n, n_err=0, cost_usd=0.05,
                           latencies=[1.0] * n, out_tokens=50 * n)


def test_persist_metrics_roundtrips(tmp_path):
    db = tmp_path / "k.db"
    scores = {"m1": _score("m1", 0.8), "m2": _score("m2", 0.4)}
    mcd.persist_metrics(scores, "release_v5", db_path=db)
    conn = sqlite3.connect(db)
    rows = dict(conn.execute("SELECT model_id, grade FROM model_coding_metrics").fetchall())
    conn.close()
    assert rows == {"m1": "A", "m2": "C"}  # 0.8*5=4.0→A ; 0.4*5=2.0→C
    mcd.report_stored(db_path=db)  # must not crash on a populated table


def test_persist_metrics_skips_unmeasured(tmp_path):
    db = tmp_path / "k.db"
    unmeasured = mcd.CodingScore("m", 0.5, n_problems=5, n_graded=2, n_err=3, cost_usd=0.01)  # <3 graded
    mcd.persist_metrics({"m": unmeasured}, "release_v5", db_path=db)
    conn = sqlite3.connect(db)
    n = conn.execute("SELECT COUNT(*) FROM model_coding_metrics").fetchone()[0]
    conn.close()
    assert n == 0  # unmeasured models are never persisted (would poison the ranker)


def test_persist_baseline_writes_livecodebench_code_prior(tmp_path):
    db = tmp_path / "k.db"
    n = mcd.persist_baseline({"m1": _score("m1", 0.6)}, "release_v5", db_path=db)
    assert n == 1
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT task_type, baseline, pass_rate, source FROM model_task_baseline WHERE model_id='m1'"
    ).fetchone()
    conn.close()
    assert row[0] == "code"
    assert row[1] == 3.0 and row[2] == 0.6  # baseline = pass@1*5 ; pass_rate = pass@1
    assert row[3] == "livecodebench:release_v5"  # the source the precedence guard keys on


def test_load_coding_metrics_latest_per_model_and_fail_soft(tmp_path):
    db = tmp_path / "k.db"
    assert load_coding_metrics(db) == {}  # absent table -> fail-soft {}
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE model_coding_metrics (model_id TEXT, grade TEXT, pass_at_1 REAL, "
                 "score5 REAL, cost_per_1k REAL, p50_latency_s REAL, n_err INT, built_at TEXT)")
    conn.executemany("INSERT INTO model_coding_metrics VALUES (?,?,?,?,?,?,?,?)", [
        ("m1", "B", 0.6, 3.0, 0.1, 2.0, 0, "2026-07-18"),
        ("m1", "A", 0.8, 4.0, 0.1, 2.0, 0, "2026-07-19"),  # newer -> wins
        ("m2", "C", 0.4, 2.0, 0.1, 2.0, 0, "2026-07-19"),
    ])
    conn.commit()
    conn.close()
    got = load_coding_metrics(db)
    assert got["m1"]["grade"] == "A" and got["m1"]["pass_at_1"] == 0.8  # latest-per-model
    assert set(got) == {"m1", "m2"}


def test_measured_models_drives_resume(tmp_path):
    """F11 resume: a model persisted (metrics AND baseline) for a window today shows in _measured_models,
    so --all skips it; a different window does not skip (window-scoped)."""
    db = tmp_path / "k.db"
    assert mcd._measured_models("release_v5", db_path=db) == set()  # nothing measured yet -> no skips
    mcd.persist_metrics({"m1": _score("m1", 0.7)}, "release_v5", db_path=db)
    mcd.persist_baseline({"m1": _score("m1", 0.7)}, "release_v5", db_path=db)
    assert mcd._measured_models("release_v5", db_path=db) == {"m1"}  # measured -> resume skips it
    assert mcd._measured_models("release_v6", db_path=db) == set()  # different window -> re-measure


def test_measured_models_requires_both_metrics_and_baseline(tmp_path):
    """A model with ONLY model_coding_metrics written (persist_baseline never ran, e.g. crashed) must NOT
    count as measured — else resume would silently skip it forever, permanently missing its baseline row
    (the routing-source table `pick_models('code')` actually ranks on)."""
    db = tmp_path / "k.db"
    mcd.persist_metrics({"m1": _score("m1", 0.7)}, "release_v5", db_path=db)
    assert mcd._measured_models("release_v5", db_path=db) == set()  # metrics-only -> NOT measured
    mcd.persist_baseline({"m1": _score("m1", 0.7)}, "release_v5", db_path=db)
    assert mcd._measured_models("release_v5", db_path=db) == {"m1"}  # both present -> measured


def test_precedence_set_excludes_measured_from_scraped_build(tmp_path):
    """A model with a measured coding metric is dropped from the terminal-bench 'code' set, so
    persist (INSERT OR REPLACE) never clobbers its livecodebench: baseline."""
    db = tmp_path / "k.db"
    mcd.persist_metrics({"measured": _score("measured", 0.7)}, "release_v5", db_path=db)
    measured = set(load_coding_metrics(db))
    assert measured == {"measured"}
    scraped_rows = [{"model_id": "measured"}, {"model_id": "scraped-only"}]
    kept = [r for r in scraped_rows if r["model_id"] not in measured]  # the guard in main()
    assert [r["model_id"] for r in kept] == ["scraped-only"]  # measured survives, scraped-only rebuilt
