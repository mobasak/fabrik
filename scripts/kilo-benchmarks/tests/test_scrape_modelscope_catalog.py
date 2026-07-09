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
