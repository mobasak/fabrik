"""Behavior Contract for scripts/kilo-benchmarks/scrape_modelscope_catalog.py.

Plan-2 Phase B — ModelScope gateway wire-in. Mirrors the SiliconFlow test
shape (tests/test_scrape_siliconflow_catalog.py if it exists, else the
SF scraper's own contract from scrape_siliconflow_catalog.py:63-141).
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_b1_org_map_zhipuai_to_z_ai():
    """ZhipuAI/GLM-5.2 → z-ai/glm-5.2 (both kebab + dot-kebab variants)."""
    from scrape_modelscope_catalog import _ms_to_agent_id_candidates

    cands = _ms_to_agent_id_candidates("ZhipuAI/GLM-5.2")
    assert cands[0] == "z-ai/glm-5.2", f"expected z-ai/glm-5.2 first, got {cands}"
    assert "z-ai/glm-5-2" in cands, f"dot-collapse variant missing: {cands}"


def test_b1_shanghai_ai_lab_provider_map():
    """Shanghai_AI_Laboratory/Intern-S1 → shanghai-ai-lab/ prefix."""
    from scrape_modelscope_catalog import _ms_to_agent_id_candidates

    cands = _ms_to_agent_id_candidates("Shanghai_AI_Laboratory/Intern-S1")
    assert all(c.startswith("shanghai-ai-lab/") for c in cands), (
        f"expected shanghai-ai-lab/ prefix on all candidates, got {cands}"
    )


def test_b2_apply_flags_idempotent_second_run(tmp_path):
    """Second run must report 0 flipped (COALESCE guard, SF Pass-2 lesson)."""
    from scrape_modelscope_catalog import apply_flags

    dbp = tmp_path / "agents.db"
    con = sqlite3.connect(str(dbp))
    con.execute("CREATE TABLE agents (id TEXT PRIMARY KEY, via_modelscope INTEGER DEFAULT 0)")
    con.execute("INSERT INTO agents (id) VALUES ('z-ai/glm-5.2')")
    con.commit()

    ms_models = [{"id": "ZhipuAI/GLM-5.2"}]
    _matched1, updated1, _unmatched1 = apply_flags(con, ms_models)
    assert updated1 == 1, f"first run should flip 1 row, got {updated1}"

    _matched2, updated2, _unmatched2 = apply_flags(con, ms_models)
    assert updated2 == 0, f"second run should flip 0 rows, got {updated2}"


def test_b3_fail_open_on_missing_key(monkeypatch):
    """MODELSCOPE_API_KEY unset → fetch_ms_models returns []."""
    from scrape_modelscope_catalog import fetch_ms_models

    monkeypatch.delenv("MODELSCOPE_API_KEY", raising=False)
    result = fetch_ms_models()
    assert result == [], f"expected [] on missing key, got {result!r}"


def test_b4_fail_open_on_network_error(monkeypatch):
    """Transient network failure → fetch_ms_models returns []."""
    from scrape_modelscope_catalog import fetch_ms_models

    monkeypatch.setenv("MODELSCOPE_API_KEY", "ms-fake-key")
    import httpx

    def raise_conn_error(*a, **kw):
        raise httpx.ConnectError("simulated network failure")

    monkeypatch.setattr(httpx, "get", raise_conn_error)
    result = fetch_ms_models()
    assert result == [], f"expected [] on network error, got {result!r}"


def test_b4b_fail_open_on_http_status_error(monkeypatch):
    """Phase-B review F3: a bad/expired token returning HTTP 401 must also
    fail-open (not raise), separately from ConnectError. `raise_for_status()`
    throws HTTPStatusError; the bare `except Exception` in fetch_ms_models
    must swallow it.
    """
    from scrape_modelscope_catalog import fetch_ms_models

    monkeypatch.setenv("MODELSCOPE_API_KEY", "ms-expired-key")
    import httpx

    class FakeResp:
        status_code = 401

        def raise_for_status(self):
            raise httpx.HTTPStatusError(
                "401 Unauthorized",
                request=httpx.Request("GET", "https://x/"),
                response=httpx.Response(401),
            )

        def json(self):
            return {}

    monkeypatch.setattr(httpx, "get", lambda *a, **kw: FakeResp())
    result = fetch_ms_models()
    assert result == [], f"expected [] on HTTP 401, got {result!r}"


def test_b5_candidate_dedup_no_dot():
    """Model name without `.` → single candidate (not two identical)."""
    from scrape_modelscope_catalog import _ms_to_agent_id_candidates

    cands = _ms_to_agent_id_candidates("deepseek-ai/DeepSeek-V4-Flash")
    assert len(set(cands)) == len(cands), f"dupes present: {cands}"


def test_org_map_uses_canonical_db_providers():
    """Phase-E whole-plan review F1 + F5 regression guard.

    _ORG_MAP maps HF-style ModelScope org names → canonical DB provider.
    3 mappings were wrong in the initial commit and got fixed in Phase E:
    paddlepaddle → baidu, xiaomimimo → xiaomi, tencent-hunyuan → tencent.
    A 4th (meituan-longcat → meituan) was fixed in this /fabrik-review Pass 1.
    A regression here silently drops per-model matches to zero.
    """
    from scrape_modelscope_catalog import _ORG_MAP, _ms_to_agent_id_candidates

    # These 3+1 corrected mappings MUST resolve to the specific DB provider.
    assert _ORG_MAP["paddlepaddle"] == "baidu"
    assert _ORG_MAP["xiaomimimo"] == "xiaomi"
    assert _ORG_MAP["tencent-hunyuan"] == "tencent"
    assert _ORG_MAP["meituan-longcat"] == "meituan"

    # Candidate emission for the 4 real MS-catalog org strings.
    cands_paddle = _ms_to_agent_id_candidates("PaddlePaddle/ERNIE-4.5-21B-A3B-PT")
    assert all(c.startswith("baidu/") for c in cands_paddle), (
        f"PaddlePaddle/ must map to baidu/, got {cands_paddle}"
    )
    cands_xiaomi = _ms_to_agent_id_candidates("XiaomiMiMo/MiMo-V2-Flash")
    assert all(c.startswith("xiaomi/") for c in cands_xiaomi), (
        f"XiaomiMiMo/ must map to xiaomi/, got {cands_xiaomi}"
    )
    cands_tencent = _ms_to_agent_id_candidates("Tencent-Hunyuan/Hy3")
    assert all(c.startswith("tencent/") for c in cands_tencent), (
        f"Tencent-Hunyuan/ must map to tencent/, got {cands_tencent}"
    )
    cands_meituan = _ms_to_agent_id_candidates("Meituan-LongCat/LongCat-Flash-Lite")
    assert all(c.startswith("meituan/") for c in cands_meituan), (
        f"Meituan-LongCat/ must map to meituan/, got {cands_meituan}"
    )


def test_b6_unmatched_ids_reported(tmp_path):
    """Unmatched MS models appear in the third return element."""
    from scrape_modelscope_catalog import apply_flags

    dbp = tmp_path / "agents.db"
    con = sqlite3.connect(str(dbp))
    con.execute("CREATE TABLE agents (id TEXT PRIMARY KEY, via_modelscope INTEGER DEFAULT 0)")
    con.commit()

    ms_models = [{"id": "XiaomiMiMo/MiMo-V2-Flash"}, {"id": "PaddlePaddle/ERNIE-4.5-0.3B-PT"}]
    _matched, _updated, unmatched = apply_flags(con, ms_models)
    assert len(unmatched) == 2, f"expected both unmatched, got {unmatched}"
    assert "XiaomiMiMo/MiMo-V2-Flash" in unmatched


# ── Phase D: ingest_new ────────────────────────────────────────────────────────


def _fresh_agents_db(tmp_path):
    """Build a fresh agents DB with the columns ingest_new INSERTs into."""
    dbp = tmp_path / "agents.db"
    con = sqlite3.connect(str(dbp))
    con.execute(
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY,
            api_id TEXT NOT NULL,
            name TEXT NOT NULL,
            provider TEXT NOT NULL,
            input_cost_per_m REAL NOT NULL DEFAULT 0,
            output_cost_per_m REAL NOT NULL DEFAULT 0,
            context_window_k INTEGER DEFAULT 128,
            has_vision INTEGER DEFAULT 0,
            has_tools INTEGER DEFAULT 0,
            has_reasoning INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            blocked INTEGER DEFAULT 0,
            block_reason TEXT,
            discard_reason TEXT,
            via_modelscope INTEGER DEFAULT 0,
            reachable_with_existing_keys INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    con.commit()
    return con


def test_d1_hf_success_inserts_enriched(tmp_path, monkeypatch):
    from ms_enrich import HFMetadata
    from scrape_modelscope_catalog import ingest_new

    con = _fresh_agents_db(tmp_path)
    monkeypatch.setattr(
        "scrape_modelscope_catalog.fetch_hf_metadata",
        lambda ms_id, **kw: HFMetadata(
            context_window_k=32,
            has_reasoning=False,
            has_tools=False,
            has_vision=False,
            is_gated=False,
            model_type="internlm3",
            pipeline_tag="text-generation",
            source_url="https://huggingface.co/api/models/x",
        ),
    )
    r = ingest_new(["Shanghai_AI_Laboratory/Intern-S1"], con)
    assert r.hf_enriched == 1
    assert r.placeholder == 0
    row = con.execute("SELECT id, blocked, via_modelscope, context_window_k FROM agents").fetchone()
    assert row is not None
    assert row[1] == 0  # blocked=0
    assert row[2] == 1  # via_modelscope=1
    assert row[3] == 32  # context_window_k


def test_d3_both_miss_placeholder(tmp_path, monkeypatch):
    from scrape_modelscope_catalog import ingest_new

    con = _fresh_agents_db(tmp_path)
    monkeypatch.setattr("scrape_modelscope_catalog.fetch_hf_metadata", lambda ms_id, **kw: None)
    monkeypatch.setattr("scrape_modelscope_catalog.fetch_ms_metadata", lambda ms_id, **kw: None)
    r = ingest_new(["IIC/GUI-Owl-1.5-8B-Instruct"], con)
    assert r.placeholder == 1
    cols = [c[0] for c in con.execute("SELECT * FROM agents").description]
    row = dict(zip(cols, con.execute("SELECT * FROM agents").fetchone(), strict=False))
    assert row["blocked"] == 1
    # F1 fix: use block_reason (pairs with blocked=1 per manage_blocked.py),
    # NOT discard_reason (pairs with status='deprecated').
    assert "needs_metadata_enrichment" in row["block_reason"]
    assert row["discard_reason"] is None
    assert row["via_modelscope"] == 1


def test_d4_idempotent(tmp_path, monkeypatch):
    from scrape_modelscope_catalog import ingest_new

    con = _fresh_agents_db(tmp_path)
    monkeypatch.setattr("scrape_modelscope_catalog.fetch_hf_metadata", lambda ms_id, **kw: None)
    monkeypatch.setattr("scrape_modelscope_catalog.fetch_ms_metadata", lambda ms_id, **kw: None)
    r1 = ingest_new(["IIC/x"], con)
    assert r1.placeholder == 1
    r2 = ingest_new(["IIC/x"], con)
    assert r2.placeholder == 0
    assert r2.skipped_dup == 1


def test_d5_ingest_new_flag_off_by_default(monkeypatch):
    """Running main without --ingest-new must NOT call ingest_new."""
    import scrape_modelscope_catalog as smc

    called = []
    monkeypatch.setattr(smc, "fetch_ms_models", lambda: [])
    monkeypatch.setattr(smc, "ingest_new", lambda *a, **kw: called.append(True) or None)
    smc.main([])  # no --ingest-new
    assert called == []


def test_d6_bad_id_skipped(tmp_path):
    from scrape_modelscope_catalog import ingest_new

    con = _fresh_agents_db(tmp_path)
    r = ingest_new(["no-slash-id"], con)
    assert r.skipped_bad_id == 1
    assert r.hf_enriched == 0


def test_d7_ms_scrape_tier2_inserts(tmp_path, monkeypatch):
    """Tier-2 (HF miss, MS-scrape success) — row inserted with blocked=0."""
    from ms_enrich import MSMetadata
    from scrape_modelscope_catalog import ingest_new

    con = _fresh_agents_db(tmp_path)
    monkeypatch.setattr("scrape_modelscope_catalog.fetch_hf_metadata", lambda ms_id, **kw: None)
    monkeypatch.setattr(
        "scrape_modelscope_catalog.fetch_ms_metadata",
        lambda ms_id, **kw: MSMetadata(
            context_window_k=16,
            description="ms-only",
            is_gated=False,
            source_url="https://modelscope.cn/models/x",
        ),
    )
    r = ingest_new(["MedAIBase/AntAngelMed"], con)
    assert r.ms_enriched == 1
    row = con.execute("SELECT blocked, context_window_k FROM agents").fetchone()
    assert row[0] == 0  # blocked=0 (routable)
    assert row[1] == 16


def test_d8_dup_check_covers_all_candidates(tmp_path, monkeypatch):
    """Phase-D review F3 regression — dup-check must consider ALL candidates,
    not just cands[0]. Scenario: DB already has the dot-collapsed variant
    (z-ai/glm-5-2); ingest of ZhipuAI/GLM-5.2 must skip (not double-insert
    the primary candidate z-ai/glm-5.2)."""
    from ms_enrich import HFMetadata
    from scrape_modelscope_catalog import ingest_new

    con = _fresh_agents_db(tmp_path)
    # Insert the dot-collapsed variant (candidate #2, not #1)
    con.execute(
        "INSERT INTO agents (id, api_id, name, provider) VALUES (?, ?, ?, ?)",
        ("z-ai/glm-5-2", "manual", "glm-5-2", "z-ai"),
    )
    con.commit()

    monkeypatch.setattr(
        "scrape_modelscope_catalog.fetch_hf_metadata",
        lambda ms_id, **kw: HFMetadata(
            context_window_k=128, has_reasoning=False, has_tools=False, has_vision=False,
            is_gated=False, model_type=None, pipeline_tag=None, source_url="x",
        ),
    )
    r = ingest_new(["ZhipuAI/GLM-5.2"], con)
    assert r.skipped_dup == 1
    assert r.hf_enriched == 0
    # Confirm no duplicate row
    n = con.execute("SELECT COUNT(*) FROM agents WHERE id LIKE 'z-ai/glm-5%'").fetchone()[0]
    assert n == 1


def test_d9_bad_id_empty_org_skipped(tmp_path):
    """Phase-D review F4 regression — '/foo' has '/' so old bad-id guard
    passed, but org is empty. Must skip (not insert row with provider='')."""
    from scrape_modelscope_catalog import ingest_new

    con = _fresh_agents_db(tmp_path)
    r = ingest_new(["/foo", "org/"], con)
    assert r.skipped_bad_id == 2
    assert con.execute("SELECT COUNT(*) FROM agents").fetchone()[0] == 0


def test_d10_hf_unknown_context_writes_null(tmp_path, monkeypatch):
    """Phase-D review F2 regression — HF returns metadata but config.json
    missed (context_window_k=None). MUST write NULL, not silently default to
    128 (which would masquerade as verified 128K)."""
    from ms_enrich import HFMetadata
    from scrape_modelscope_catalog import ingest_new

    con = _fresh_agents_db(tmp_path)
    monkeypatch.setattr(
        "scrape_modelscope_catalog.fetch_hf_metadata",
        lambda ms_id, **kw: HFMetadata(
            context_window_k=None,  # /resolve/config.json missed
            has_reasoning=False, has_tools=False, has_vision=False,
            is_gated=False, model_type=None, pipeline_tag=None, source_url="x",
        ),
    )
    r = ingest_new(["gated/model"], con)
    assert r.hf_enriched == 1
    ctx = con.execute("SELECT context_window_k FROM agents").fetchone()[0]
    assert ctx is None, f"context_window_k must be NULL when unknown, got {ctx}"


# ── Follow-up: retry_placeholders (auto-heal on daily cron) ────────────────────


def _insert_placeholder(con, api_id, agent_id):
    """Simulate a prior --ingest-new run that landed a placeholder row."""
    provider, _, name = agent_id.partition("/")
    con.execute(
        "INSERT INTO agents "
        "(id, api_id, name, provider, status, via_modelscope, reachable_with_existing_keys, "
        "blocked, block_reason, has_reasoning, has_tools, has_vision) "
        "VALUES (?, ?, ?, ?, 'active', 1, 1, 1, ?, 0, 0, 0)",
        (agent_id, api_id, name, provider, "needs_metadata_enrichment (MS-only, HF+MS scrape both failed)"),
    )
    con.commit()


def test_retry1_hf_now_returns_data_promotes_row(tmp_path, monkeypatch):
    """A placeholder row from a prior run gets auto-promoted when HF
    metadata becomes available on a later daily run."""
    from ms_enrich import HFMetadata
    from scrape_modelscope_catalog import retry_placeholders

    con = _fresh_agents_db(tmp_path)
    _insert_placeholder(con, "Shanghai_AI_Laboratory/Intern-S1", "shanghai-ai-lab/intern-s1")
    monkeypatch.setattr(
        "scrape_modelscope_catalog.fetch_hf_metadata",
        lambda ms_id, **kw: HFMetadata(
            context_window_k=32, has_reasoning=True, has_tools=False, has_vision=False,
            is_gated=False, model_type="internlm3", pipeline_tag="text-generation",
            source_url="x",
        ),
    )
    r = retry_placeholders(con)
    assert r.promoted == 1
    row = con.execute(
        "SELECT blocked, block_reason, context_window_k, has_reasoning FROM agents"
    ).fetchone()
    assert row[0] == 0  # blocked cleared
    assert row[1] is None  # block_reason cleared
    assert row[2] == 32  # context enriched
    assert row[3] == 1  # has_reasoning enriched


def test_retry2_both_still_miss_stays_placeholder(tmp_path, monkeypatch):
    """Neither HF nor MS-scrape can enrich — row must stay placeholder."""
    from scrape_modelscope_catalog import retry_placeholders

    con = _fresh_agents_db(tmp_path)
    _insert_placeholder(con, "IIC/GUI-Owl", "alibaba-iic/gui-owl")
    monkeypatch.setattr("scrape_modelscope_catalog.fetch_hf_metadata", lambda ms_id, **kw: None)
    monkeypatch.setattr("scrape_modelscope_catalog.fetch_ms_metadata", lambda ms_id, **kw: None)
    r = retry_placeholders(con)
    assert r.promoted == 0
    assert r.still_pending == 1
    row = con.execute("SELECT blocked, block_reason FROM agents").fetchone()
    assert row[0] == 1  # still blocked
    assert row[1] is not None


def test_retry3_ms_scrape_only_promotes_with_partial_data(tmp_path, monkeypatch):
    """HF misses but MS SPA scrape succeeds — row promotes with MS data."""
    from ms_enrich import MSMetadata
    from scrape_modelscope_catalog import retry_placeholders

    con = _fresh_agents_db(tmp_path)
    _insert_placeholder(con, "IIC/GUI-Owl", "alibaba-iic/gui-owl")
    monkeypatch.setattr("scrape_modelscope_catalog.fetch_hf_metadata", lambda ms_id, **kw: None)
    monkeypatch.setattr(
        "scrape_modelscope_catalog.fetch_ms_metadata",
        lambda ms_id, **kw: MSMetadata(
            context_window_k=8, description="ok", is_gated=False, source_url="x",
        ),
    )
    r = retry_placeholders(con)
    assert r.promoted == 1
    row = con.execute("SELECT blocked, context_window_k FROM agents").fetchone()
    assert row[0] == 0
    assert row[1] == 8


def test_retry4_no_placeholders_is_noop(tmp_path):
    """No placeholder rows in DB → retry returns cleanly with zero promotions."""
    from scrape_modelscope_catalog import retry_placeholders

    con = _fresh_agents_db(tmp_path)
    r = retry_placeholders(con)
    assert r.promoted == 0
    assert r.still_pending == 0


def test_retry5_only_touches_placeholder_rows(tmp_path, monkeypatch):
    """A regular blocked=1 row for OTHER reasons (e.g. blocked-too-slow) must
    NOT be touched by retry_placeholders — only our specific block_reason."""
    from ms_enrich import HFMetadata
    from scrape_modelscope_catalog import retry_placeholders

    con = _fresh_agents_db(tmp_path)
    # Regular blocked row (not ours)
    con.execute(
        "INSERT INTO agents (id, api_id, name, provider, status, blocked, block_reason) "
        "VALUES ('deepseek/x', 'x', 'x', 'deepseek', 'active', 1, 'too slow')"
    )
    con.commit()
    monkeypatch.setattr(
        "scrape_modelscope_catalog.fetch_hf_metadata",
        lambda ms_id, **kw: HFMetadata(
            context_window_k=32, has_reasoning=False, has_tools=False, has_vision=False,
            is_gated=False, model_type="x", pipeline_tag="x", source_url="x",
        ),
    )
    r = retry_placeholders(con)
    assert r.promoted == 0  # our function didn't touch it
    row = con.execute("SELECT blocked, block_reason FROM agents").fetchone()
    assert row[0] == 1  # still blocked
    assert row[1] == "too slow"  # untouched
