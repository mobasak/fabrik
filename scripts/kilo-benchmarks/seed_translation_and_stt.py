#!/usr/bin/env python3
"""Seed translation + STT capability data into kilo_agents.db.

Two sources mined here, both zero-inference-cost:

  1. Translation bake-off doc at
     /opt/fabrik-lib/mt-router/docs/bakeoff-2026-05-26.md
     Operator-curated, 10 strings × 5 languages × 7 providers. Parses
     the markdown results table into per-model `translation_quality`
     JSON ({lang: pct, avg: pct}). Also INSERTs the 2 mt-router models
     that aren't on OpenRouter (qwen-mt-turbo via Alibaba DashScope,
     Hunyuan via SiliconFlow) so the catalog covers the full router.

  2. STT (speech-to-text) capability — hand-curated from public WER
     leaderboards (Common Voice 17.0, FLEURS multilingual, LibriSpeech
     test-clean). Includes both the 20 OpenRouter audio-input chat
     models (flagged `is_stt_capable=1`) and a few direct-API STT-only
     models (Whisper-1, gpt-4o-transcribe, Deepgram Nova-3, AssemblyAI
     Universal-2) seeded as new agents rows with `stt_only=1`.

This script is idempotent — re-running on an existing DB updates
existing rows without duplicates.

Sources for the STT seed (public, citable):
  - OpenAI Whisper: arxiv.org/abs/2212.04356 + openai.com/index/whisper
  - OpenAI gpt-4o-transcribe: openai.com/index/introducing-our-next-generation-audio-models
  - Deepgram Nova-3: deepgram.com/learn/introducing-nova-3 (own benchmark)
  - AssemblyAI: assemblyai.com/blog/universal-2 (own benchmark)
  - FLEURS leaderboard: huggingface.co/spaces/CAiRE/AudioOmni-Leaderboard

Usage:
    python seed_translation_and_stt.py
    python seed_translation_and_stt.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
BAKEOFF_PATH = Path("/opt/fabrik-lib/mt-router/docs/bakeoff-2026-05-26.md")


def _log(msg: str) -> None:
    print(f"[seed_t&s] {msg}")


def _today_utc_iso() -> str:
    return datetime.now(UTC).date().isoformat()


# --------------------------------------------------------------------
# 1. Translation bake-off parser
# --------------------------------------------------------------------

# Map the doc's provider+model identifiers to our `agents.id` values.
# When a model isn't on OpenRouter we list its native provider here so
# the seeder INSERTs the row with the right gateway flags.
BAKEOFF_MODEL_MAP: dict[str, dict] = {
    "deepseek/deepseek-v3.2": {
        "id": "deepseek/deepseek-v3.2",
        "via_openrouter": 1,
    },
    "google/gemini-2.5-flash": {
        "id": "google/gemini-2.5-flash",
        "via_openrouter": 1,
    },
    "x-ai/grok-4.3": {
        "id": "x-ai/grok-4.3",
        "via_openrouter": 1,
    },
    "mistralai/mistral-small-3.2-24b-instruct": {
        "id": "mistralai/mistral-small-3.2-24b-instruct",
        "via_openrouter": 1,
    },
    "tencent/Hunyuan-A13B-Instruct": {
        "id": "tencent/hunyuan-a13b-instruct",
        "via_openrouter": 0,
        "via_siliconflow": 1,
        "name": "Tencent: Hunyuan A13B Instruct",
        "provider": "tencent",
    },
    "qwen-mt-turbo": {
        "id": "qwen/qwen-mt-turbo",
        "via_openrouter": 0,
        "via_dashscope": 1,
        "name": "Qwen: Qwen-MT-Turbo (Alibaba DashScope)",
        "provider": "qwen",
        "input_cost_per_m": 0.16,
        "output_cost_per_m": 0.49,
        "context_window_k": 32,
        "description": (
            "Alibaba DashScope dedicated machine-translation model. 92 "
            "languages with native source/target via translation_options. "
            "Specialist strengths: French / Portuguese / German / Indonesian "
            "/ Arabic (top-3 in fabrik translation bake-off v2.2). Weaker on "
            "low-resource + morphology-heavy targets (HU/RO/UR/KO)."
        ),
    },
}

DEEPL_MAP = {
    "id": "deepl/deepl",
    "via_openrouter": 0,
    "name": "DeepL: Machine Translation (Tier 1 MT)",
    "provider": "deepl",
}
AZURE_MAP = {
    "id": "azure/translator",
    "via_openrouter": 0,
    "name": "Azure: Cognitive Translator (Tier 2 MT)",
    "provider": "azure",
}

BAKEOFF_NAME_TO_KEY = {
    "Grok": "x-ai/grok-4.3",
    "DeepSeek": "deepseek/deepseek-v3.2",
    "Mistral": "mistralai/mistral-small-3.2-24b-instruct",
    "Gemini": "google/gemini-2.5-flash",
    "Hunyuan": "tencent/Hunyuan-A13B-Instruct",
    "DeepL": "DEEPL",
    "Azure": "AZURE",
}


def parse_bakeoff(path: Path = BAKEOFF_PATH) -> dict[str, dict]:
    """Return {model_key: {tr, es, pt, ja, id, avg}} parsed from the
    results table in the bake-off markdown."""
    if not path.exists():
        _log(f"WARN: {path} missing — translation seed skipped")
        return {}
    text = path.read_text(encoding="utf-8")

    # Find the section header "## Results: Similarity to Human Translations"
    # and parse the markdown table directly under it.
    section = re.search(
        r"## Results: Similarity to Human Translations\s*\n(.*?)(?:\n## |\Z)",
        text,
        re.DOTALL,
    )
    if not section:
        _log("WARN: results table not found in bake-off doc")
        return {}
    block = section.group(1)

    out: dict[str, dict] = {}
    for line in block.splitlines():
        # Match data rows only — they start with "| **Provider**" or "| Provider"
        m = re.match(
            r"\|\s*\**(\w+)\**\s*\|\s*\$?([\d.]+|FREE)\s*\|"
            r"\s*\**([\d.]+)%?\**\s*\|\s*\**([\d.]+)%?\**\s*\|"
            r"\s*\**([\d.]+)%?\**\s*\|\s*\**([\d.]+)%?\**\s*\|"
            r"\s*\**([\d.]+)%?\**\s*\|\s*\**([\d.]+)%?\**\s*\|",
            line,
        )
        if not m:
            continue
        name = m.group(1)
        key = BAKEOFF_NAME_TO_KEY.get(name)
        if not key:
            continue
        out[key] = {
            "tr": float(m.group(3)),
            "es": float(m.group(4)),
            "pt": float(m.group(5)),
            "ja": float(m.group(6)),
            "id": float(m.group(7)),
            "avg": float(m.group(8)),
            "source": "fabrik-lib/mt-router bake-off 2026-05-26",
        }
    return out


def upsert_translation_rows(
    conn: sqlite3.Connection,
    scores: dict[str, dict],
) -> dict:
    """For each scored model: if it's already in `agents` UPDATE the
    translation_quality + translation_avg_pct + is_translation_capable
    + gateway flags. If missing, INSERT a stub row."""
    today = _today_utc_iso()
    counts = {"updated": 0, "inserted": 0}

    for key, scoreset in scores.items():
        mapping = (
            BAKEOFF_MODEL_MAP.get(key)
            if key in BAKEOFF_MODEL_MAP
            else (DEEPL_MAP if key == "DEEPL" else (AZURE_MAP if key == "AZURE" else None))
        )
        if not mapping:
            continue
        mid = mapping["id"]
        qj = json.dumps(scoreset)
        avg = scoreset["avg"]

        cur = conn.execute("SELECT id FROM agents WHERE id = ?", (mid,)).fetchone()
        if cur:
            conn.execute(
                "UPDATE agents SET translation_quality = ?, translation_avg_pct = ?, "
                "is_translation_capable = 1, last_verified = ? WHERE id = ?",
                (qj, avg, today, mid),
            )
            # Set gateway flags conditionally — don't clobber via_openrouter
            # for rows the OpenRouter verifier already touched.
            if mapping.get("via_dashscope"):
                conn.execute("UPDATE agents SET via_dashscope = 1 WHERE id = ?", (mid,))
            if mapping.get("via_siliconflow"):
                conn.execute("UPDATE agents SET via_siliconflow = 1 WHERE id = ?", (mid,))
            # Reactivate direct-API gateway rows that the OpenRouter verifier
            # may have deprecated in the past (it can't see DashScope /
            # SiliconFlow). Also push per-mapping defaults for cost / ctx /
            # description so direct-routed rows aren't stuck on zero.
            if mapping.get("via_dashscope") or mapping.get("via_siliconflow"):
                conn.execute(
                    "UPDATE agents SET status = 'active', discard_reason = NULL "
                    "WHERE id = ? AND status = 'deprecated' "
                    "AND COALESCE(discard_reason,'') LIKE '%verifier%'",
                    (mid,),
                )
            for col in ("input_cost_per_m", "output_cost_per_m", "context_window_k", "description"):
                if mapping.get(col) is not None:
                    conn.execute(
                        f"UPDATE agents SET {col} = COALESCE(NULLIF({col}, 0), ?) WHERE id = ?",
                        (mapping[col], mid),
                    )
            counts["updated"] += 1
        else:
            provider = mapping.get("provider") or (mid.split("/")[0] if "/" in mid else mid)
            conn.execute(
                "INSERT INTO agents (id, api_id, name, provider, "
                "input_cost_per_m, output_cost_per_m, context_window_k, "
                "description, status, last_verified, "
                "via_openrouter, via_kilo, via_dashscope, via_siliconflow, "
                "translation_quality, translation_avg_pct, is_translation_capable) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, 0, ?, ?, ?, ?, 1)",
                (
                    mid,
                    mid,
                    mapping.get("name") or mid,
                    provider,
                    mapping.get("input_cost_per_m") or 0,
                    mapping.get("output_cost_per_m") or 0,
                    mapping.get("context_window_k") or 0,
                    mapping.get("description"),
                    today,
                    mapping.get("via_openrouter", 0),
                    mapping.get("via_dashscope", 0),
                    mapping.get("via_siliconflow", 0),
                    qj,
                    avg,
                ),
            )
            counts["inserted"] += 1
    return counts


# --------------------------------------------------------------------
# 2. STT seed (hand-curated public WER leaderboards)
# --------------------------------------------------------------------

# STT models that have their OWN API (not OpenRouter chat completions).
# WER values from public sources cited in the script docstring.
# Lower WER = better. `en` = LibriSpeech test-clean; `multi` = FLEURS multilingual avg.
STT_SEED: list[dict] = [
    {
        "id": "openai/whisper-large-v3",
        "name": "OpenAI: Whisper Large v3",
        "provider": "openai",
        "stt_quality": {"en": 4.0, "multi": 9.7, "source": "OpenAI Whisper paper + FLEURS"},
        "via_openai_direct": 1,
    },
    {
        "id": "openai/gpt-4o-transcribe",
        "name": "OpenAI: GPT-4o Transcribe",
        "provider": "openai",
        "stt_quality": {"en": 2.5, "multi": 8.4, "source": "OpenAI (own benchmark)"},
        "via_openai_direct": 1,
    },
    {
        "id": "openai/gpt-4o-mini-transcribe",
        "name": "OpenAI: GPT-4o-Mini Transcribe",
        "provider": "openai",
        "stt_quality": {"en": 3.4, "multi": 11.5, "source": "OpenAI (own benchmark)"},
        "via_openai_direct": 1,
    },
    {
        "id": "deepgram/nova-3",
        "name": "Deepgram: Nova-3",
        "provider": "deepgram",
        "stt_quality": {"en": 6.84, "multi": 12.5, "source": "Deepgram (own benchmark, 5/2025)"},
        "via_openai_direct": 0,
    },
    {
        "id": "deepgram/nova-2",
        "name": "Deepgram: Nova-2",
        "provider": "deepgram",
        "stt_quality": {"en": 8.4, "multi": 15.2, "source": "Deepgram (own benchmark)"},
        "via_openai_direct": 0,
    },
    {
        "id": "assemblyai/universal-2",
        "name": "AssemblyAI: Universal-2",
        "provider": "assemblyai",
        "stt_quality": {"en": 6.6, "multi": 14.8, "source": "AssemblyAI (own benchmark, 2024)"},
        "via_openai_direct": 0,
    },
    {
        "id": "google/cloud-speech-v2",
        "name": "Google: Cloud Speech-to-Text v2",
        "provider": "google",
        "stt_quality": {"en": 7.8, "multi": 13.1, "source": "FLEURS leaderboard"},
        "via_openai_direct": 0,
    },
]


def upsert_stt_seed(conn: sqlite3.Connection) -> dict:
    today = _today_utc_iso()
    counts = {"updated": 0, "inserted": 0, "or_audio_flagged": 0}
    for m in STT_SEED:
        wer_avg = (m["stt_quality"].get("en", 0) + m["stt_quality"].get("multi", 0)) / 2
        qj = json.dumps(m["stt_quality"])
        cur = conn.execute("SELECT id FROM agents WHERE id = ?", (m["id"],)).fetchone()
        if cur:
            conn.execute(
                "UPDATE agents SET name = ?, provider = ?, stt_quality = ?, "
                "stt_wer_avg = ?, is_stt_capable = 1, status = 'active', "
                "last_verified = ? WHERE id = ?",
                (m["name"], m["provider"], qj, wer_avg, today, m["id"]),
            )
            counts["updated"] += 1
        else:
            conn.execute(
                "INSERT INTO agents (id, api_id, name, provider, "
                "input_cost_per_m, output_cost_per_m, context_window_k, "
                "status, last_verified, "
                "via_openrouter, via_kilo, "
                "stt_quality, stt_wer_avg, is_stt_capable) "
                "VALUES (?, ?, ?, ?, 0, 0, 0, 'active', ?, 0, 0, ?, ?, 1)",
                (m["id"], m["id"], m["name"], m["provider"], today, qj, wer_avg),
            )
            counts["inserted"] += 1

    # Flag all OpenRouter audio-input models as stt_capable so the
    # browser can surface them. Pulled from the OpenRouter live cache.
    cache = SCRIPT_DIR / "cache" / "openrouter_live_catalog.json"
    if cache.exists():
        live = json.loads(cache.read_text())
        for m in live.get("data", []):
            mods = (m.get("architecture") or {}).get("input_modalities") or []
            if "audio" in mods:
                cur = conn.execute("SELECT id FROM agents WHERE id = ?", (m["id"],)).fetchone()
                if cur:
                    conn.execute(
                        "UPDATE agents SET is_stt_capable = 1 WHERE id = ?",
                        (m["id"],),
                    )
                    counts["or_audio_flagged"] += 1
    return counts


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DB_PATH)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if not args.db.exists():
        _log(f"ERROR: {args.db} missing")
        return 1

    scores = parse_bakeoff()
    _log(f"Parsed {len(scores)} model scores from bake-off doc")

    conn = sqlite3.connect(args.db)
    try:
        if args.dry_run:
            _log(f"DRY-RUN: would upsert translation for: {list(scores.keys())}")
            _log(f"DRY-RUN: would upsert {len(STT_SEED)} STT seed rows")
            return 0
        conn.execute("BEGIN")
        tc = upsert_translation_rows(conn, scores)
        sc = upsert_stt_seed(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    _log(f"Translation: updated={tc['updated']} inserted={tc['inserted']}")
    _log(
        f"STT: updated={sc['updated']} inserted={sc['inserted']} "
        f"OR-audio flagged={sc['or_audio_flagged']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
