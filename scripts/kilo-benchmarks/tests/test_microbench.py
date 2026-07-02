"""Regression tests for microbench_or_models.

Tests are hermetic — no real API calls. `bench_one` is mocked with
recorded SSE bytes streams to exercise the parser + math.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------- Streaming primitives ----------


def test_parse_stream_computes_tps_ttft_and_cost():
    """Feed a hand-built SSE stream through _parse_stream; assert math."""
    from microbench_or_models import _parse_stream

    # 3 content chunks 100ms apart + a final usage chunk.
    lines = [
        b": OPENROUTER PROCESSING",
        b"",
        b'data: {"choices":[{"delta":{"content":""}}]}',
        b"",
        b'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        b"",
        b'data: {"choices":[{"delta":{"content":" there"}}]}',
        b"",
        b'data: {"choices":[{"delta":{"content":" world"}}]}',
        b"",
        b'data: {"choices":[{"delta":{"content":""},"finish_reason":"length"}],'
        b'"usage":{"prompt_tokens":10,"completion_tokens":30,"total_tokens":40,"cost":1.5e-05}}',
        b"",
        b"data: [DONE]",
    ]

    class FakeResp:
        def iter_lines(self, decode_unicode=True):
            for line in lines:
                yield line.decode("utf-8") if decode_unicode else line

    r = _parse_stream(FakeResp())
    assert r["error"] is None, r
    assert r["prompt_tokens"] == 10
    assert r["completion_tokens"] == 30
    assert r["cost_usd"] == 1.5e-05
    # In a hermetic test the stream drains instantaneously — ttft can be
    # 0.0 (all chunks arrive within the same monotonic tick). Real
    # network measurements are always positive; assert non-negative here.
    assert r["tps"] > 0
    assert r["ttft_ms"] >= 0


def test_parse_stream_returns_error_when_no_usage_block():
    from microbench_or_models import _parse_stream

    class FakeResp:
        def iter_lines(self, decode_unicode=True):
            yield 'data: {"choices":[{"delta":{"content":"only content"}}]}'
            yield "data: [DONE]"

    r = _parse_stream(FakeResp())
    assert r["error"] and "no usage" in r["error"]


def test_parse_stream_returns_error_on_zero_completion_tokens():
    from microbench_or_models import _parse_stream

    class FakeResp:
        def iter_lines(self, decode_unicode=True):
            yield 'data: {"choices":[{"delta":{"content":"hi"}}]}'
            yield 'data: {"usage":{"prompt_tokens":5,"completion_tokens":0,"cost":0}}'
            yield "data: [DONE]"

    r = _parse_stream(FakeResp())
    assert r["error"] and "zero completion_tokens" in r["error"]


def test_parse_stream_ignores_malformed_data_lines():
    from microbench_or_models import _parse_stream

    class FakeResp:
        def iter_lines(self, decode_unicode=True):
            yield "data: not-valid-json"  # skipped
            yield 'data: {"choices":[{"delta":{"content":"hi"}}]}'
            yield "data: also-not-json {malformed"  # skipped
            # Two content chunks (not one) so the single-chunk rejection
            # doesn't hide the malformed-line-ignore behavior we're testing.
            yield 'data: {"choices":[{"delta":{"content":" there"}}]}'
            yield 'data: {"usage":{"prompt_tokens":1,"completion_tokens":2,"cost":1e-6}}'
            yield "data: [DONE]"

    r = _parse_stream(FakeResp())
    assert r["error"] is None
    assert r["completion_tokens"] == 2


# ---------- Review-2026-07-02 regression tests ----------


def test_parse_stream_rejects_single_chunk_streams_instead_of_fabricating_tps():
    """Review finding: single-chunk streams previously got a fake 0.1s
    stream_duration fallback that inflated TPS 10-30x. Must now return
    an error so the bench is skipped, not written to DB."""
    from microbench_or_models import _parse_stream

    class FakeResp:
        def iter_lines(self, decode_unicode=True):
            # One content chunk carrying all 300 tokens (Cerebras/Groq-LPU
            # pattern via OR routing on small responses).
            yield 'data: {"choices":[{"delta":{"content":"...all 300 tokens..."}}]}'
            yield 'data: {"usage":{"prompt_tokens":10,"completion_tokens":300,"cost":1e-5}}'
            yield "data: [DONE]"

    r = _parse_stream(FakeResp())
    assert r["error"] is not None, "single-chunk stream must return an error"
    assert "single-chunk" in r["error"], f"expected 'single-chunk' in error, got {r['error']!r}"
    assert r["tps"] is None, "must not fabricate a TPS value"


def test_bench_one_catches_unicode_decode_error_from_iter_lines(monkeypatch):
    """Review finding: iter_lines(decode_unicode=True) can raise
    UnicodeDecodeError on non-UTF-8 bytes from a mangling proxy. Must
    be caught and returned as an error (not propagate + crash the loop)."""
    from microbench_or_models import _parse_stream

    class BrokenResp:
        def iter_lines(self, decode_unicode=True):
            yield 'data: {"choices":[{"delta":{"content":"hi"}}]}'
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    r = _parse_stream(BrokenResp())
    assert r["error"] is not None
    assert "stream error" in r["error"] or "UnicodeDecodeError" in r["error"], r["error"]


def test_bench_one_uses_context_manager_to_close_response(monkeypatch):
    """Review finding: `with resp:` ensures the HTTP connection is
    released even if _parse_stream raises. Guard against reversion."""
    from microbench_or_models import bench_one

    closed = {"flag": False}

    class FakeResp:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            closed["flag"] = True
            return False

        def iter_lines(self, decode_unicode=True):
            yield 'data: {"choices":[{"delta":{"content":"hi"}}]}'
            yield 'data: {"usage":{"prompt_tokens":1,"completion_tokens":2,"cost":1e-6}}'
            yield "data: [DONE]"

    monkeypatch.setattr("microbench_or_models.requests.post", lambda *a, **k: FakeResp())
    bench_one("test/model", "fake-key")
    assert closed["flag"], "bench_one must close the response (with-context)"


def test_cohort_cutoff_uses_utc_not_local_timezone(tmp_path, monkeypatch):
    """Review finding: _select_cohort previously used local `date.today()`
    while _write_result uses `datetime.now(UTC).date()`. Under any non-UTC
    TZ the recency boundary drifts by ±1 day. This test seeds a boundary
    row and verifies the cutoff uses UTC."""
    import sqlite3
    from datetime import UTC, datetime

    from microbench_or_models import RECENCY_WINDOW_DAYS, _select_cohort

    # A row written at 30 UTC-days ago is exactly on the boundary.
    just_inside = (datetime.now(UTC).date() - timedelta(days=RECENCY_WINDOW_DAYS - 1)).isoformat()
    just_outside = (datetime.now(UTC).date() - timedelta(days=RECENCY_WINDOW_DAYS + 1)).isoformat()

    db = tmp_path / "cohort.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY, status TEXT DEFAULT 'active',
            service_type TEXT DEFAULT 'llm',
            input_cost_per_m REAL, output_cost_per_m REAL,
            output_tokens_per_sec REAL, ttft_ms REAL,
            speed_source TEXT, speed_updated_at TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO agents (id, input_cost_per_m, output_cost_per_m, output_tokens_per_sec, "
        "speed_source, speed_updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("inside/model", 1.0, 3.0, 50.0, "own_microbench x", just_inside),
            ("outside/model", 1.0, 3.0, 50.0, "own_microbench x", just_outside),
        ],
    )
    conn.commit()
    cohort = _select_cohort(conn)
    conn.close()

    ids = {r["id"] for r in cohort}
    # inside-window row (< 30 UTC days old) must be skipped
    assert "inside/model" not in ids
    # outside-window row (> 30 UTC days old) must be picked up
    assert "outside/model" in ids


# ---------- bench_median ----------


def test_bench_median_computes_median_and_skips_on_2_failures():
    """3 calls, one fails. Median-of-2 is returned."""
    from microbench_or_models import bench_median

    calls = [
        {
            "tps": 40,
            "ttft_ms": 500,
            "cost_usd": 1e-5,
            "error": None,
            "prompt_tokens": 1,
            "completion_tokens": 1,
        },
        {
            "tps": None,
            "ttft_ms": None,
            "cost_usd": 0.0,
            "error": "HTTP 500",
            "prompt_tokens": 0,
            "completion_tokens": 0,
        },
        {
            "tps": 60,
            "ttft_ms": 700,
            "cost_usd": 1e-5,
            "error": None,
            "prompt_tokens": 1,
            "completion_tokens": 1,
        },
    ]
    it = iter(calls)

    with patch("microbench_or_models.bench_one", side_effect=lambda *a, **k: next(it)):
        with patch("microbench_or_models.time.sleep"):
            r = bench_median("test/model", "fake-key", n=3)

    assert r["error"] is None, r
    assert r["tps"] == 50  # median of 40 and 60
    assert r["ttft_ms"] == 600
    assert r["cost_usd"] == 2e-5


def test_bench_median_aborts_after_2_failures():
    from microbench_or_models import bench_median

    fail = {
        "tps": None,
        "ttft_ms": None,
        "cost_usd": 0.0,
        "error": "HTTP 500",
        "prompt_tokens": 0,
        "completion_tokens": 0,
    }
    with patch("microbench_or_models.bench_one", return_value=fail):
        with patch("microbench_or_models.time.sleep"):
            r = bench_median("test/model", "fake-key", n=3)
    assert r["error"] and "failed" in r["error"]
    assert r["tps"] is None


# ---------- Cohort selection filters ----------


def _seed_cohort_db(tmp_path: Path) -> Path:
    db = tmp_path / "seed.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY, status TEXT DEFAULT 'active',
            service_type TEXT DEFAULT 'llm',
            input_cost_per_m REAL, output_cost_per_m REAL,
            output_tokens_per_sec REAL, ttft_ms REAL,
            speed_source TEXT, speed_updated_at TEXT
        );
        """
    )
    conn.commit()
    conn.close()
    return db


def test_cohort_excludes_expensive_models(tmp_path):
    from microbench_or_models import _select_cohort

    db = _seed_cohort_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.executemany(
        "INSERT INTO agents (id, input_cost_per_m, output_cost_per_m) VALUES (?, ?, ?)",
        [("cheap/mdl", 0.5, 2.0), ("expensive/mdl", 15.0, 30.0)],
    )
    conn.commit()

    cohort = _select_cohort(conn)
    conn.close()
    ids = {r["id"] for r in cohort}
    assert "cheap/mdl" in ids
    assert "expensive/mdl" not in ids


def test_cohort_excludes_free_variants(tmp_path):
    from microbench_or_models import _select_cohort

    db = _seed_cohort_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.executemany(
        "INSERT INTO agents (id, input_cost_per_m, output_cost_per_m) VALUES (?, ?, ?)",
        [("paid/mdl", 1.0, 3.0), ("paid/mdl:free", 1.0, 3.0)],
    )
    conn.commit()
    cohort = _select_cohort(conn)
    conn.close()
    ids = {r["id"] for r in cohort}
    assert "paid/mdl" in ids
    assert "paid/mdl:free" not in ids


def test_cohort_excludes_openrouter_meta_routers(tmp_path):
    from microbench_or_models import _select_cohort

    db = _seed_cohort_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.executemany(
        "INSERT INTO agents (id, input_cost_per_m, output_cost_per_m) VALUES (?, ?, ?)",
        [("normal/mdl", 1.0, 3.0), ("openrouter/auto", 1.0, 3.0)],
    )
    conn.commit()
    cohort = _select_cohort(conn)
    conn.close()
    ids = {r["id"] for r in cohort}
    assert "normal/mdl" in ids
    assert "openrouter/auto" not in ids


def test_cohort_excludes_zero_priced_rows(tmp_path):
    """lyria-3-*-preview music-gen misclassified as llm has $0 pricing —
    must be filtered out per plan Phase 2 Design step 2."""
    from microbench_or_models import _select_cohort

    db = _seed_cohort_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.executemany(
        "INSERT INTO agents (id, input_cost_per_m, output_cost_per_m) VALUES (?, ?, ?)",
        [("google/lyria-3-preview", 0.0, 0.0), ("normal/mdl", 1.0, 3.0)],
    )
    conn.commit()
    cohort = _select_cohort(conn)
    conn.close()
    ids = {r["id"] for r in cohort}
    assert "normal/mdl" in ids
    assert "google/lyria-3-preview" not in ids


def test_idempotent_skips_recently_benched_rows(tmp_path):
    """A row benched today with own_microbench source is not re-selected.

    Uses `datetime.now(UTC).date()` for the test boundary (not the local
    `date.today()`), matching production's `_write_result` + `_select_cohort`
    convention. Review 2026-07-02 caught that the earlier form (local
    date.today()) masked a TZ bug in _select_cohort.
    """
    from datetime import UTC, datetime

    from microbench_or_models import _select_cohort

    db = _seed_cohort_db(tmp_path)
    today = datetime.now(UTC).date().isoformat()
    old = (datetime.now(UTC).date() - timedelta(days=45)).isoformat()
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO agents (id, input_cost_per_m, output_cost_per_m, "
        "output_tokens_per_sec, speed_source, speed_updated_at) VALUES "
        "('fresh/mdl', 1.0, 3.0, 50.0, 'own_microbench x', ?)",
        (today,),
    )
    conn.execute(
        "INSERT INTO agents (id, input_cost_per_m, output_cost_per_m, "
        "output_tokens_per_sec, speed_source, speed_updated_at) VALUES "
        "('stale/mdl', 1.0, 3.0, 50.0, 'own_microbench y', ?)",
        (old,),
    )
    conn.commit()
    cohort = _select_cohort(conn)
    conn.close()
    ids = {r["id"] for r in cohort}
    assert "fresh/mdl" not in ids, "fresh own_microbench row should be skipped"
    assert "stale/mdl" in ids, "stale own_microbench row should be re-benched"


def test_cost_cap_aborts_loop(tmp_path, monkeypatch):
    """Mock bench returns $6/call, assert loop stops after 2 calls."""
    from microbench_or_models import run_microbench

    db = _seed_cohort_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.executemany(
        "INSERT INTO agents (id, input_cost_per_m, output_cost_per_m) VALUES (?, ?, ?)",
        [(f"model/{i}", 1.0, 3.0) for i in range(5)],
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")

    # Each bench call returns $6, hitting the $10 cap after 2 calls.
    def fake_bench(model_id, api_key, n=3):
        return {"tps": 100.0, "ttft_ms": 500.0, "cost_usd": 6.0, "error": None, "attempts": []}

    with patch("microbench_or_models.bench_median", side_effect=fake_bench):
        with patch("microbench_or_models.time.sleep"):
            code = run_microbench(db, cost_cap_usd=10.0)

    assert code == 0
    conn = sqlite3.connect(db)
    updated = conn.execute(
        "SELECT COUNT(*) FROM agents WHERE speed_source LIKE 'own_microbench%'"
    ).fetchone()[0]
    conn.close()
    assert updated == 2, f"expected exactly 2 rows updated before cap; got {updated}"


def test_run_without_api_key_exits_zero(tmp_path, monkeypatch, capsys):
    """No OPENROUTER_API_KEY → non-fatal exit 0 + SKIP log line."""
    from microbench_or_models import run_microbench

    db = _seed_cohort_db(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    # dotenv.load_dotenv would read .env — patch it to no-op for hermeticity
    with patch("microbench_or_models.load_dotenv"):
        code = run_microbench(db)

    assert code == 0
    captured = capsys.readouterr()
    assert "SKIP: OPENROUTER_API_KEY not set" in captured.out
