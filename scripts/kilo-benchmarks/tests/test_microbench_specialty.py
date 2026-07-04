# AFTER-EDIT: scripts/kilo-benchmarks/microbench_specialty.py
"""Hermetic tests for microbench_specialty + specialty_clients.

Plan 2026-07-03-plan-1-full-speed-coverage-close.md Phase B.6.
Zero real network — all `requests.post` / `requests.get` are patched.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from add_perf_seconds_column import ensure_perf_seconds_column  # noqa: E402
from specialty_clients import (  # noqa: E402
    bfl_via_fal,
    dashscope_translation,
    elevenlabs_sfx,
    elevenlabs_tts,
    openai_whisper,
    recraft,
    replicate,
)

# --------------------------------------------------------------- helpers


def _resp(
    status: int, *, json_data: dict | None = None, content: bytes = b"", text: str = ""
) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_data or {}
    r.content = content
    r.text = text or (str(json_data) if json_data else "")
    return r


@pytest.fixture
def tmpdb():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        p = Path(f.name)
    conn = sqlite3.connect(p)
    conn.execute(
        """CREATE TABLE agents (
            id TEXT PRIMARY KEY, service_type TEXT, status TEXT,
            output_tokens_per_sec REAL, perf_seconds REAL,
            speed_source TEXT, speed_updated_at TEXT
        )"""
    )
    conn.commit()
    conn.close()
    yield p
    p.unlink(missing_ok=True)


# --------------------------------------------------------------- 1


def test_bfl_via_fal_client_polls_queue_and_returns_seconds():
    enqueue = _resp(200, json_data={"status": "IN_QUEUE", "status_url": "https://queue.fal.run/y"})
    poll_completed = _resp(200, json_data={"status": "COMPLETED"})
    with (
        patch.object(bfl_via_fal.requests, "post", return_value=enqueue),
        patch.object(bfl_via_fal.requests, "get", return_value=poll_completed),
        patch.object(bfl_via_fal.time, "sleep"),
    ):
        r = bfl_via_fal.bench_one("bfl/flux-schnell", "K")
    assert r["error"] is None
    assert r["perf_seconds"] is not None
    assert r["perf_seconds"] >= 0
    # PRICING backfill: bfl/flux-schnell = $0.003 per_image
    assert r["cost_usd"] == pytest.approx(0.003)


def test_bfl_via_fal_rejects_status_url_on_untrusted_host():
    """SSRF guard: never send FAL_KEY to a non-Fal host, even if the enqueue
    response tells us to."""
    enqueue = _resp(200, json_data={"status": "IN_QUEUE", "status_url": "https://evil.example/y"})
    with patch.object(bfl_via_fal.requests, "post", return_value=enqueue):
        r = bfl_via_fal.bench_one("bfl/flux-schnell", "K")
    assert r["error"] is not None
    assert "evil.example" in r["error"]


def test_bfl_via_fal_surfaces_retry_after_header_from_429():
    """A real 429 with a Retry-After header must reach the dispatcher's parser
    so backoff honors the hint instead of falling back to the fixed 1s sleep."""
    resp = MagicMock()
    resp.status_code = 429
    resp.headers = {"Retry-After": "8"}
    resp.text = '{"error":"rate limited"}'
    with patch.object(bfl_via_fal.requests, "post", return_value=resp):
        r = bfl_via_fal.bench_one("bfl/flux-schnell", "K")
    assert r["error"] is not None
    assert "Retry-After: 8" in r["error"]


# --------------------------------------------------------------- 2


def test_bfl_via_fal_client_returns_error_on_fal_moderation_response():
    """Fal.ai surfaces moderation as a FAILED / ERROR status on the poll.

    Also verifies the balance-exhausted 403 path emits the [FAL-BALANCE-EXHAUSTED]
    marker so the daily_refresh operator sees the specific cause.
    """
    exhausted = _resp(403, text="Exhausted balance please top up")
    with patch.object(bfl_via_fal.requests, "post", return_value=exhausted):
        r = bfl_via_fal.bench_one("bfl/flux-schnell", "K")
    assert r["error"] is not None
    assert "[FAL-BALANCE-EXHAUSTED]" in r["error"]

    # Moderation surfaces as FAILED on the poll:
    enqueue = _resp(200, json_data={"status": "IN_QUEUE", "status_url": "https://queue.fal.run/y"})
    moderated = _resp(200, json_data={"status": "FAILED", "error": "content_moderated"})
    with (
        patch.object(bfl_via_fal.requests, "post", return_value=enqueue),
        patch.object(bfl_via_fal.requests, "get", return_value=moderated),
        patch.object(bfl_via_fal.time, "sleep"),
    ):
        r2 = bfl_via_fal.bench_one("bfl/flux-schnell", "K")
    assert r2["error"] is not None
    assert "FAILED" in r2["error"]


# --------------------------------------------------------------- 3


def test_recraft_client_returns_seconds_for_generate():
    ok = _resp(200, json_data={"credits": 40, "data": [{"url": "https://x"}]})
    with patch.object(recraft.requests, "post", return_value=ok):
        r = recraft.bench_one("recraft/v3", "K")
    assert r["error"] is None
    assert r["cost_usd"] == pytest.approx(0.04, rel=1e-6)
    assert r["perf_seconds"] >= 0


def test_recraft_fails_loud_when_credits_field_missing():
    """A 2xx without a `credits` field means the API contract shifted; silently
    treating that as $0 would break the cost cap."""
    ok = _resp(200, json_data={"data": [{"url": "https://x"}]})
    with patch.object(recraft.requests, "post", return_value=ok):
        r = recraft.bench_one("recraft/v3", "K")
    assert r["error"] is not None
    assert "no credits field" in r["error"]


# --------------------------------------------------------------- 4


def test_replicate_client_polls_prediction_until_terminal_state():
    create = _resp(200, json_data={"id": "p1", "urls": {"get": "https://api.replicate.com/x"}})
    processing = _resp(200, json_data={"status": "processing"})
    succeeded = _resp(200, json_data={"status": "succeeded", "metrics": {"total_cost": 0.005}})
    with (
        patch.object(replicate.requests, "post", return_value=create),
        patch.object(replicate.requests, "get", side_effect=[processing, succeeded]),
        patch.object(replicate.time, "sleep"),
    ):
        r = replicate.bench_one("stability/sdxl", "K")
    assert r["error"] is None
    assert r["cost_usd"] == pytest.approx(0.005)
    assert r["perf_seconds"] >= 0


def test_replicate_backfills_cost_from_pricing_when_metrics_missing():
    """metrics.total_cost is sometimes empty on succeeded — cost cap must still
    see real spend via the PRICING backfill."""
    create = _resp(200, json_data={"id": "p", "urls": {"get": "https://api.replicate.com/x"}})
    succeeded_no_cost = _resp(200, json_data={"status": "succeeded", "metrics": {}})
    with (
        patch.object(replicate.requests, "post", return_value=create),
        patch.object(replicate.requests, "get", return_value=succeeded_no_cost),
        patch.object(replicate.time, "sleep"),
    ):
        r = replicate.bench_one("stability/sdxl", "K")
    assert r["error"] is None
    # PRICING[stability/sdxl] = $0.003
    assert r["cost_usd"] == pytest.approx(0.003)


def test_replicate_rejects_poll_url_on_untrusted_host():
    create = _resp(200, json_data={"id": "p", "urls": {"get": "https://evil.example/x"}})
    with patch.object(replicate.requests, "post", return_value=create):
        r = replicate.bench_one("stability/sdxl", "K")
    assert r["error"] is not None
    assert "evil.example" in r["error"]


def test_replicate_returns_error_on_unpinned_model():
    """Placeholder version strings were removed; unpinned models fail loud
    instead of enqueuing a malformed prediction every week."""
    r = replicate.bench_one("stability/sd3.5-large", "K")
    assert r["error"] is not None
    assert "no Replicate version pinned" in r["error"]


# --------------------------------------------------------------- 5


def test_elevenlabs_tts_rest_client_measures_seconds_to_full_audio():
    audio = b"\x00" * 4096
    ok = _resp(200, content=audio)
    with patch.object(elevenlabs_tts.requests, "post", return_value=ok):
        r = elevenlabs_tts.bench_one("elevenlabs/multilingual-v2", "K")
    assert r["error"] is None
    assert r["cost_usd"] > 0
    # BENCH_TEXT is ~200 chars × 3e-5 = ~0.006
    assert r["cost_usd"] < 0.02


# --------------------------------------------------------------- 6


def test_elevenlabs_sfx_client_returns_seconds_for_sound_generation():
    ok = _resp(200, content=b"\x00" * 4096)
    with patch.object(elevenlabs_sfx.requests, "post", return_value=ok):
        r = elevenlabs_sfx.bench_one("elevenlabs/sound-effects", "K")
    assert r["error"] is None
    assert r["cost_usd"] == pytest.approx(0.02)


# --------------------------------------------------------------- 7


def test_openai_whisper_client_uploads_audio_and_times_transcription():
    ok = _resp(200, json_data={"text": "hello world"})
    with patch.object(openai_whisper.requests, "post", return_value=ok) as mp:
        r = openai_whisper.bench_one("openai/whisper-large-v3", "K")
    assert r["error"] is None
    assert r["perf_seconds"] >= 0
    # multipart file included
    call = mp.call_args
    assert "files" in call.kwargs
    assert "file" in call.kwargs["files"]
    # 10s of silence at 16kHz × 2 bytes + 44-byte header ~= 320KB
    fname, buf, mime = call.kwargs["files"]["file"]
    assert mime == "audio/wav"
    assert len(buf) > 100_000


# --------------------------------------------------------------- 8


def test_dashscope_qwen_mt_turbo_returns_translation_seconds():
    ok = _resp(
        200,
        json_data={
            "output": {"choices": [{"message": {"content": "Hola"}}]},
            "usage": {"total_tokens": 20},
        },
    )
    with patch.object(dashscope_translation.requests, "post", return_value=ok):
        r = dashscope_translation.bench_one("qwen/qwen-mt-turbo", "K")
    assert r["error"] is None
    assert r["perf_seconds"] >= 0
    # Fixed formula: len(BENCH_TEXT) × per_char (deterministic vs tokens×per_char)
    expected = len(dashscope_translation.BENCH_TEXT) * 0.000018
    assert r["cost_usd"] == pytest.approx(expected)


# --------------------------------------------------------------- 9


def test_dispatcher_routes_by_service_type():
    import microbench_specialty as mb

    keys = {
        "FAL_KEY": "f",
        "RECRAFT_API_KEY": "r",
        "REPLICATE_API_TOKEN": "p",
        "ELEVENLABS_API_KEY": "e",
        "OPENAI_API_KEY": "o",
        "DASHSCOPE_API_KEY": "d",
    }
    fn, key, tag = mb._dispatch("bfl/flux-schnell", "image_gen", keys)
    assert fn is bfl_via_fal.bench_one and tag == "fal_bfl"
    fn, key, tag = mb._dispatch("recraft/v3", "image_gen", keys)
    assert fn is recraft.bench_one and tag == "recraft_direct"
    fn, key, tag = mb._dispatch("stability/sdxl", "image_gen", keys)
    assert fn is replicate.bench_one and tag == "replicate_direct"
    fn, key, tag = mb._dispatch("elevenlabs/multilingual-v2", "tts", keys)
    assert fn is elevenlabs_tts.bench_one and tag == "elevenlabs_direct"
    fn, key, tag = mb._dispatch("elevenlabs/sound-effects", "music_gen", keys)
    assert fn is elevenlabs_sfx.bench_one and tag == "elevenlabs_direct"
    fn, key, tag = mb._dispatch("openai/whisper-large-v3", "stt", keys)
    assert fn is openai_whisper.bench_one and tag == "openai_direct"
    fn, key, tag = mb._dispatch("qwen/qwen-mt-turbo", "translation", keys)
    assert fn is dashscope_translation.bench_one and tag == "dashscope_direct"


# --------------------------------------------------------------- 10


def test_dispatcher_skips_row_without_matching_provider_key():
    import microbench_specialty as mb

    r = mb.bench_median("recraft/v3", "image_gen", {"RECRAFT_API_KEY": ""})
    assert r["error"] == "provider key not set"
    assert r["perf_seconds"] is None
    # Also unknown model → no client
    r2 = mb.bench_median("no/such-model", "image_gen", {"FAL_KEY": "x"})
    assert "no client" in (r2["error"] or "")


# --------------------------------------------------------------- 11


def test_write_result_reports_failure_on_zero_row_match(tmpdb):
    """UPDATE that matches no row must return False so the run summary
    doesn't lie about how many rows got benched."""
    import microbench_specialty as mb

    ensure_perf_seconds_column(tmpdb)
    # No INSERT — agents table is empty
    ok = mb._write_result(
        tmpdb,
        "nonexistent/id",
        {"perf_seconds": 1.0, "cost_usd": 0.0, "error": None, "tag": "recraft_direct"},
    )
    assert ok is False


def test_write_result_stores_perf_seconds_not_tokens_per_sec(tmpdb):
    import microbench_specialty as mb

    ensure_perf_seconds_column(tmpdb)
    with sqlite3.connect(tmpdb) as c:
        c.execute(
            "INSERT INTO agents(id, service_type, status) VALUES('recraft/v3','image_gen','active')"
        )
    ok = mb._write_result(
        tmpdb,
        "recraft/v3",
        {
            "perf_seconds": 3.5,
            "cost_usd": 0.04,
            "error": None,
            "tag": "recraft_direct",
        },
    )
    assert ok
    with sqlite3.connect(tmpdb) as c:
        row = c.execute(
            "SELECT perf_seconds, output_tokens_per_sec, speed_source FROM agents WHERE id='recraft/v3'"
        ).fetchone()
    assert row[0] == 3.5
    assert row[1] is None  # NOT written — different column
    assert row[2].startswith("recraft_direct ")


# --------------------------------------------------------------- 12


def test_cost_cap_stops_before_next_call_using_pricing_table(tmpdb, monkeypatch, capsys):
    import microbench_specialty as mb

    ensure_perf_seconds_column(tmpdb)
    with sqlite3.connect(tmpdb) as c:
        c.execute(
            "INSERT INTO agents(id, service_type, status) VALUES('recraft/v3','image_gen','active')"
        )
        c.execute(
            "INSERT INTO agents(id, service_type, status) VALUES('recraft/nano-banana','image_gen','active')"
        )

    monkeypatch.setattr(mb, "DB_PATH", tmpdb)
    monkeypatch.setattr(mb, "COST_CAP_USD", 0.01)  # trip after first row

    def fake_bench_median(model_id, service_type, keys):
        return {"perf_seconds": 3.0, "cost_usd": 0.05, "error": None, "tag": "recraft_direct"}

    monkeypatch.setattr(mb, "bench_median", fake_bench_median)
    monkeypatch.setattr(mb, "load_dotenv", lambda: None)
    monkeypatch.setattr(mb.os, "getenv", lambda k: "x")

    mb.run_specialty(dry_run=False)
    out = capsys.readouterr().out
    assert "cost_stop" in out


# --------------------------------------------------------------- 13


def test_readonly_recovery_reuses_the_llm_bench_pattern(tmpdb, monkeypatch, capsys):
    """SQLITE_READONLY on a write must be non-fatal — the loop continues."""
    import microbench_specialty as mb

    ensure_perf_seconds_column(tmpdb)
    with sqlite3.connect(tmpdb) as c:
        c.execute(
            "INSERT INTO agents(id, service_type, status) VALUES('recraft/v3','image_gen','active')"
        )

    def raise_readonly(*a, **kw):
        raise sqlite3.OperationalError("attempt to write a readonly database")

    monkeypatch.setattr(mb.sqlite3, "connect", raise_readonly)
    ok = mb._write_result(
        tmpdb,
        "recraft/v3",
        {
            "perf_seconds": 1.0,
            "cost_usd": 0.0,
            "error": None,
            "tag": "recraft_direct",
        },
    )
    assert ok is False
    out = capsys.readouterr().out
    assert "WRITE-FAIL" in out


# --------------------------------------------------------------- 14


def test_cohort_selects_only_perf_seconds_null_rows_one_time_bench(tmpdb):
    """One-time bench: once a row has perf_seconds, it never re-enters cohort,
    regardless of how old the stamp is."""
    import microbench_specialty as mb

    ensure_perf_seconds_column(tmpdb)
    with sqlite3.connect(tmpdb) as c:
        # Already-benched → EXCLUDED forever (even if from 90 days ago)
        c.execute(
            "INSERT INTO agents(id, service_type, status, perf_seconds, speed_updated_at) "
            "VALUES('recraft/v3','image_gen','active', 3.0, date('now'))"
        )
        c.execute(
            "INSERT INTO agents(id, service_type, status, perf_seconds, speed_updated_at) "
            "VALUES('elevenlabs/multilingual-v2','tts','active', 2.0, date('now','-90 days'))"
        )
        # NULL perf_seconds → INCLUDED (never been benched)
        c.execute(
            "INSERT INTO agents(id, service_type, status) "
            "VALUES('bfl/flux-schnell','image_gen','active')"
        )
        # LLM row → EXCLUDED (wrong service_type)
        c.execute(
            "INSERT INTO agents(id, service_type, status) "
            "VALUES('anthropic/claude-3-opus','llm','active')"
        )
        # Deprecated → EXCLUDED
        c.execute(
            "INSERT INTO agents(id, service_type, status) "
            "VALUES('old/one','image_gen','deprecated')"
        )

    with sqlite3.connect(tmpdb) as c:
        cohort = mb._select_cohort(c)
    ids = {r["id"] for r in cohort}
    assert ids == {"bfl/flux-schnell"}


# --------------------------------------------------------------- 15


def test_pricing_table_covers_all_active_specialty_rows():
    """Fail if a new specialty row lands in the DB without a PRICING entry.
    Blocks silent cost-cap breakage."""
    from specialty_pricing import PRICING

    db = SCRIPT_DIR / "kilo_agents.db"
    if not db.exists():
        pytest.skip(f"drift-guard needs the shared catalog DB at {db}")
    with sqlite3.connect(db) as c:
        rows = c.execute(
            """SELECT id FROM agents
               WHERE status='active'
                 AND output_tokens_per_sec IS NULL
                 AND service_type IN ('image_gen','tts','music_gen','stt','translation')"""
        ).fetchall()
    unpriced = [r[0] for r in rows if r[0] not in PRICING]
    assert not unpriced, f"Add PRICING entries for: {unpriced}"


# --------------------------------------------------------------- 16


def test_ssrf_allowlist_rejects_http_scheme_downgrade():
    """https-only guard on both Fal and Replicate poll URLs."""
    enqueue_fal = _resp(
        200, json_data={"status": "IN_QUEUE", "status_url": "http://queue.fal.run/y"}
    )
    with patch.object(bfl_via_fal.requests, "post", return_value=enqueue_fal):
        r = bfl_via_fal.bench_one("bfl/flux-schnell", "K")
    assert r["error"] is not None and "queue.fal.run" in r["error"]

    create_rep = _resp(200, json_data={"id": "p", "urls": {"get": "http://api.replicate.com/x"}})
    with patch.object(replicate.requests, "post", return_value=create_rep):
        r2 = replicate.bench_one("stability/sdxl", "K")
    assert r2["error"] is not None and "api.replicate.com" in r2["error"]


def test_replicate_survives_explicit_null_metrics():
    """`.get('metrics') or {}` handles a JSON explicit null without crashing."""
    create = _resp(200, json_data={"id": "p", "urls": {"get": "https://api.replicate.com/x"}})
    succeeded_null_metrics = _resp(200, json_data={"status": "succeeded", "metrics": None})
    with (
        patch.object(replicate.requests, "post", return_value=create),
        patch.object(replicate.requests, "get", return_value=succeeded_null_metrics),
        patch.object(replicate.time, "sleep"),
    ):
        r = replicate.bench_one("stability/sdxl", "K")
    assert r["error"] is None
    assert r["cost_usd"] == pytest.approx(0.003)


def test_replicate_survives_explicit_null_urls():
    """Explicit null on `urls` must not AttributeError; must return a clean error."""
    create_null_urls = _resp(200, json_data={"id": "p", "urls": None})
    with patch.object(replicate.requests, "post", return_value=create_null_urls):
        r = replicate.bench_one("stability/sdxl", "K")
    assert r["error"] is not None
    assert "no poll url" in r["error"]


def test_bfl_via_fal_survives_explicit_null_status():
    """Explicit null status field on poll response must not crash `.upper()`."""
    enqueue = _resp(200, json_data={"status": "IN_QUEUE", "status_url": "https://queue.fal.run/y"})
    poll_null = _resp(200, json_data={"status": None})
    # After one null-status poll we'd loop again; feed COMPLETED next so bench exits.
    poll_ok = _resp(200, json_data={"status": "COMPLETED"})
    with (
        patch.object(bfl_via_fal.requests, "post", return_value=enqueue),
        patch.object(bfl_via_fal.requests, "get", side_effect=[poll_null, poll_ok]),
        patch.object(bfl_via_fal.time, "sleep"),
    ):
        r = bfl_via_fal.bench_one("bfl/flux-schnell", "K")
    assert r["error"] is None


def test_recraft_rejects_negative_credits():
    """A negative credits value from a misbehaving upstream must be floored to 0,
    not allowed to decrement running_cost."""
    ok = _resp(200, json_data={"credits": -40, "data": [{"url": "x"}]})
    with patch.object(recraft.requests, "post", return_value=ok):
        r = recraft.bench_one("recraft/v3", "K")
    assert r["error"] is None
    assert r["cost_usd"] == 0.0


def test_recraft_rejects_non_numeric_credits():
    ok = _resp(200, json_data={"credits": "abc", "data": [{"url": "x"}]})
    with patch.object(recraft.requests, "post", return_value=ok):
        r = recraft.bench_one("recraft/v3", "K")
    assert r["error"] is not None
    assert "not numeric" in r["error"]


def test_post_run_verify_flags_misroute_as_bench_qa_fail(tmpdb, capsys):
    """If a llm row ever gets a *_direct speed_source today, exit non-zero."""
    import microbench_specialty as mb

    ensure_perf_seconds_column(tmpdb)
    today = "date('now')"
    with sqlite3.connect(tmpdb) as c:
        c.execute(
            f"INSERT INTO agents(id, service_type, status, speed_source, speed_updated_at) "
            f"VALUES('anthropic/claude-x','llm','active','recraft_direct 2026-07-04',{today})"
        )
    rc = mb._post_run_verify(tmpdb)
    out = capsys.readouterr().out
    assert rc == 1
    assert "[BENCH-QA-FAIL]" in out


def test_post_run_verify_clean_when_no_misroute(tmpdb, capsys):
    import microbench_specialty as mb

    ensure_perf_seconds_column(tmpdb)
    with sqlite3.connect(tmpdb) as c:
        c.execute(
            "INSERT INTO agents(id, service_type, status, perf_seconds, speed_source, "
            "speed_updated_at) VALUES('recraft/v3','image_gen','active',1.2,"
            "'recraft_direct 2026-07-04',date('now'))"
        )
    rc = mb._post_run_verify(tmpdb)
    out = capsys.readouterr().out
    assert rc == 0
    assert "precedence guard OK" in out


def test_log_scrubs_control_chars_and_newlines():
    """Server-echoed error must not spoof extra log lines."""
    import microbench_specialty as mb

    assert "\n" not in mb._scrub("hello\nworld")
    assert "\x1b" not in mb._scrub("hello\x1b[31mred")


def test_soft_cost_cap_emits_warning(tmpdb, monkeypatch, capsys):
    import microbench_specialty as mb

    ensure_perf_seconds_column(tmpdb)
    with sqlite3.connect(tmpdb) as c:
        for i in range(3):
            c.execute(
                f"INSERT INTO agents(id, service_type, status) VALUES('r/{i}','image_gen','active')"
            )

    monkeypatch.setattr(mb, "DB_PATH", tmpdb)
    monkeypatch.setattr(mb, "COST_SOFT_CAP_USD", 0.05)
    monkeypatch.setattr(mb, "COST_CAP_USD", 100.0)
    monkeypatch.setattr(
        mb,
        "bench_median",
        lambda mid, st, keys: {
            "perf_seconds": 1.0,
            "cost_usd": 0.03,
            "error": None,
            "tag": "recraft_direct",
        },
    )
    monkeypatch.setattr(mb, "load_dotenv", lambda: None)
    monkeypatch.setattr(mb.os, "getenv", lambda k: "x")

    mb.run_specialty(dry_run=False)
    out = capsys.readouterr().out
    assert "cost_soft_warn" in out


def test_backoff_on_429_respects_retry_after_header():
    import microbench_specialty as mb

    assert mb._parse_retry_after(None) is None
    assert mb._parse_retry_after("") is None
    assert mb._parse_retry_after("http 500: something else") is None
    assert mb._parse_retry_after("http 429: Retry-After: 7") == 7
    assert mb._parse_retry_after("http 429: retry_after=3 body...") == 3
    # bounded to <= 60
    assert mb._parse_retry_after("http 429: Retry-After: 9999") == 60

    # bench_median honors the hint between attempts (sleep receives the hint)
    calls = {"n": 0}

    def fake_client(model_id, key):
        calls["n"] += 1
        return {"perf_seconds": None, "cost_usd": 0.0, "error": "http 429: Retry-After: 4"}

    sleeps: list[float] = []

    def fake_dispatch(_id, _st, _keys):
        return fake_client, "K", "recraft_direct"

    with (
        patch.object(mb, "_dispatch", fake_dispatch),
        patch.object(mb.time, "sleep", side_effect=lambda s: sleeps.append(s)),
    ):
        mb.bench_median("recraft/v3", "image_gen", {"RECRAFT_API_KEY": "K"})
    assert calls["n"] == mb.BENCH_N_RUNS
    # BENCH_N_RUNS - 1 sleeps happened, each honoring the hint
    assert sleeps == [4.0] * (mb.BENCH_N_RUNS - 1)
