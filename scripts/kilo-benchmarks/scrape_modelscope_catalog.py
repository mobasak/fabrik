#!/usr/bin/env python3
# AFTER-EDIT: docs/reference/kilo/AI_VENDOR_ACCESS.md scripts/kilo-benchmarks/models_browser.html
"""Scrape ModelScope's model catalog + flip `agents.via_modelscope=1` per exact match.

Live source: https://api-inference.modelscope.cn/v1/models — Alibaba model hub,
OpenAI-compatible endpoint. Auth: `MODELSCOPE_API_KEY` (`ms-*` token) in env.

Mirror of `scrape_siliconflow_catalog.py`'s per-model flag-flip logic.
Only populates the availability flag (via_modelscope=1); per-model pricing
is not on the /models endpoint.

Idempotent: safe to run daily from `daily_refresh.sh`. Prints match counts to
stderr for observability. Non-fatal on network failure or missing key
(exits 0 with a WARN).
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "kilo_agents.db"
MS_URL = "https://api-inference.modelscope.cn/v1/models"

# HF-style org → agents.provider normalization.
# ModelScope publishes models as `Org/ModelName` (HuggingFace convention);
# our DB uses lowercase kebab-case for provider. Verified live 2026-07-09
# against the 55-model ModelScope inference catalog.
_ORG_MAP = {
    "deepseek-ai": "deepseek",
    "zhipuai": "z-ai",  # Z.ai IS Zhipu — same company rebrand
    "minimax": "minimax",
    "shanghai_ai_laboratory": "shanghai-ai-lab",  # net-new (no DB rows yet — unmatched)
    "paddlepaddle": "baidu",  # PaddlePaddle is Baidu's DL brand; DB uses baidu/ernie-4.5-*
    "xiaomimimo": "xiaomi",  # MS publishes as XiaomiMiMo/, DB is xiaomi/mimo-v2-*
    "tencent-hunyuan": "tencent",  # MS publishes as Tencent-Hunyuan/Hy3, DB is tencent/hy3
    "iic": "alibaba-iic",  # net-new (no DB rows yet)
    "musepublic": "musepublic",  # net-new
    "opengvlab": "opengvlab",  # net-new
    "xgenerationlab": "xgenerationlab",  # net-new (XiYanSQL)
    "stepfun-ai": "stepfun",
    "moonshotai": "moonshotai",
    "qwen": "qwen",
    "mistralai": "mistralai",
    "meituan-longcat": "meituan",  # MS publishes as Meituan-LongCat/, DB is meituan/longcat-flash-chat
    "nex-agi": "nex-agi",
    "llm-research": "llm-research",  # net-new (LLM-Research/Llama-4-Maverick)
    "medaibase": "medaibase",  # net-new
    "opencompass": "opencompass",  # net-new
}


def _norm(s: str) -> str:
    """Lowercase + strip + collapse non-alnum-dash to `-` (mirrors
    `_canonicalize_id` convention from verify_openrouter_catalog.py)."""
    return re.sub(r"[^a-z0-9\-]", "-", (s or "").lower())


def _ms_to_agent_id_candidates(ms_id: str) -> list[str]:
    """Map a ModelScope id like `ZhipuAI/GLM-5.2` to candidate agents.id
    strings the DB might use. Returns a list because DB naming isn't
    consistent (e.g. glm-5.2 vs glm-5-2).
    """
    if "/" not in ms_id:
        return []
    org, model = ms_id.split("/", 1)
    prov = _ORG_MAP.get(org.lower(), org.lower())
    # Basic form: <prov>/<model-lowercase-with-.-preserved-and-_-to->
    model_kebab = model.lower().replace("_", "-")
    model_dot_kebab = model.lower().replace("_", "-").replace(".", "-")
    # Dedupe — for a model like `Intern-S1` (no dots), both candidates
    # collapse to the same string. Mirrors SF Pass 2 review PF-2b.
    return list(dict.fromkeys([f"{prov}/{model_kebab}", f"{prov}/{model_dot_kebab}"]))


def fetch_ms_models() -> list[dict]:
    """Return ModelScope /v1/models as a list of {id: str, ...} dicts. Never
    raises; empty list on any failure (fail-open — matches SF discipline)."""
    try:
        import httpx  # local import; script also runs on hosts without httpx

        key = os.getenv("MODELSCOPE_API_KEY")
        if not key:
            print(
                "[ms-scraper] WARN: MODELSCOPE_API_KEY unset — nothing to fetch",
                file=sys.stderr,
            )
            return []
        r = httpx.get(MS_URL, headers={"Authorization": f"Bearer {key}"}, timeout=15.0)
        r.raise_for_status()
        return r.json().get("data", []) if isinstance(r.json(), dict) else []
    except Exception as exc:  # noqa: BLE001 — fail-open contract
        print(f"[ms-scraper] WARN: fetch failed: {exc}", file=sys.stderr)
        return []


def apply_flags(conn: sqlite3.Connection, ms_models: list[dict]) -> tuple[int, int, list[str]]:
    """Flip `via_modelscope=1` on every agents row that matches a ModelScope id.

    Returns (matched, updated, unmatched_ms_ids). `matched` is how many MS
    entries mapped to a DB row (a single row may match >1 MS entry —
    idempotent flip either way). `updated` is rowcount from the UPDATE.
    """
    matched = 0
    unmatched: list[str] = []
    ids_to_flip: set[str] = set()
    for m in ms_models:
        ms_id = m.get("id") if isinstance(m, dict) else None
        if not ms_id:
            continue
        candidates = _ms_to_agent_id_candidates(ms_id)
        hit = None
        for cand in candidates:
            r = conn.execute("SELECT id FROM agents WHERE id = ?", (cand,)).fetchone()
            if r:
                hit = r[0]
                break
        if hit:
            matched += 1
            ids_to_flip.add(hit)
        else:
            unmatched.append(ms_id)
    if not ids_to_flip:
        return matched, 0, unmatched
    placeholders = ",".join("?" for _ in ids_to_flip)
    # `AND COALESCE(via_modelscope, 0) != 1` guard so the reported `updated`
    # rowcount reflects ONLY newly-flipped rows — mirrors SF Pass-2 lesson.
    cur = conn.execute(
        f"UPDATE agents SET via_modelscope = 1 "  # noqa: S608 — placeholders is a fixed count
        f"WHERE id IN ({placeholders}) AND COALESCE(via_modelscope, 0) != 1",
        tuple(sorted(ids_to_flip)),
    )
    updated = cur.rowcount
    conn.commit()
    return matched, updated, unmatched


def main() -> int:
    ms = fetch_ms_models()
    if not ms:
        print("[ms-scraper] 0 MS models fetched — nothing to do", file=sys.stderr)
        return 0
    conn = sqlite3.connect(DB_PATH)
    try:
        matched, updated, unmatched = apply_flags(conn, ms)
    finally:
        conn.close()
    print(
        f"[ms-scraper] fetched {len(ms)} MS models; matched {matched} to agents.id; "
        f"flipped via_modelscope=1 on {updated} rows"
    )
    if unmatched:
        print(
            f"[ms-scraper] {len(unmatched)} unmatched MS ids (no agents row):",
            file=sys.stderr,
        )
        for msid in unmatched[:20]:
            print(f"  {msid}", file=sys.stderr)
        if len(unmatched) > 20:
            print(f"  ... and {len(unmatched) - 20} more", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
