#!/usr/bin/env python3
"""Populate `weekly_rank` + `weekly_category` from OpenRouter's /rankings pages.

OR publishes 7 leaderboard pages with REAL PRODUCTION USAGE per model —
which models are actually being called this week. This is missing
entirely from /api/v1/models and complements the benchmark scores we
already have (Arena ELO, AA Intelligence, TBench, SWE-bench, etc.).

The 7 pages we mirror:

  /rankings                  text LLMs       weekly tokens   (top 40)
  /rankings/image            image gen       weekly requests (top 18)
  /rankings/embeddings       embeddings      weekly requests (top 20)
  /rankings/rerank           rerank          weekly requests (top 4)
  /rankings/video            video gen       weekly requests (top 10)
  /rankings/speech           TTS             weekly requests (top 9)
  /rankings/transcription    STT             weekly requests (top 10)

LIVE SCRAPE LIMITATION: the leaderboards are React-rendered client-side
and the SSR HTML doesn't carry the row data. A puppeteer-driven loader
would catch everything, but that's a heavy runtime dependency. So this
scraper carries an EMBEDDED SNAPSHOT (`_RANKINGS_SNAPSHOT` below) of
the top-N for each page, captured via the operator's puppeteer-MCP
chain. The snapshot updates on demand (re-run the puppeteer sweep,
paste the new lists into the constant below).

When OR's frontend serves the rankings via a JSON endpoint we can
poll, this script grows a `_fetch_live_json()` path and the snapshot
becomes a fallback.

Writes per matched row:
  weekly_rank          INT  — 1 = most used in this category
  weekly_category      TEXT — text | image | embedding | rerank | video | speech | transcription
  weekly_last_scraped  TEXT — ISO date of the snapshot

Idempotent: re-running clears stale ranks first, then re-writes the
fresh snapshot. Models that fall off OR's leaderboard get NULL.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"

# Snapshot of /rankings/{text,image,embeddings,rerank,video,speech,
# transcription} captured 2026-07-01 via puppeteer-MCP. Each list is in
# rank order (index 0 = rank 1). Update via the puppeteer sweep below
# and paste the new lists back here.
_RANKINGS_SNAPSHOT: dict[str, list[str]] = {
    "text": [
        "deepseek/deepseek-v4-flash",
        "xiaomi/mimo-v2.5",
        "minimax/minimax-m3",
        "openrouter/owl-alpha",
        "tencent/hy3-preview",
        "anthropic/claude-opus-4.7",
        "z-ai/glm-5.2",
        "deepseek/deepseek-v4-pro",
        "anthropic/claude-opus-4.8",
        "anthropic/claude-sonnet-4.6",
        "stepfun/step-3.7-flash",
        "openai/gpt-5.5",
        "google/gemini-3-flash-preview",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "poolside/laguna-m.1:free",
        "deepseek/deepseek-v3.2",
        "google/gemini-2.5-flash-lite",
        "google/gemini-2.5-flash",
        "xiaomi/mimo-v2.5-pro",
        "openai/gpt-oss-120b",
        "google/gemini-3.1-pro-preview",
        "google/gemini-3.5-flash",
        "openai/gpt-5.4",
    ],
    "image": [
        "google/gemini-2.5-flash-image",
        "google/gemini-3.1-flash-image-preview",
        "google/gemini-3.1-flash-image",
        "google/gemini-3-pro-image-preview",
        "google/gemini-3-pro-image",
        "x-ai/grok-imagine-image-quality",
        "openai/gpt-5.4-image-2",
        "bytedance-seed/seedream-4.5",
        "black-forest-labs/flux.2-klein-4b",
        "black-forest-labs/flux.2-pro",
        "microsoft/mai-image-2.5",
        "openai/gpt-image-2",
        "openai/gpt-5-image-mini",
        "black-forest-labs/flux.2-max",
        "openai/gpt-5-image",
        "black-forest-labs/flux.2-flex",
        "sourceful/riverflow-v2.5-fast",
        "recraft/recraft-v4.1",
        "sourceful/riverflow-v2-fast",
        "openai/gpt-image-1-mini",
    ],
    "embedding": [
        "openai/text-embedding-3-small",
        "qwen/qwen3-embedding-8b",
        "openai/text-embedding-3-large",
        "perplexity/pplx-embed-v1-0.6b",
        "baai/bge-m3",
        "google/gemini-embedding-001",
        "google/gemini-embedding-2",
        "qwen/qwen3-embedding-4b",
        "nvidia/llama-nemotron-embed-vl-1b-v2:free",
        "perplexity/pplx-embed-v1-4b",
        "google/gemini-embedding-2-preview",
        "intfloat/multilingual-e5-large",
        "openai/text-embedding-ada-002",
        "baai/bge-base-en-v1.5",
        "mistralai/mistral-embed-2312",
        "sentence-transformers/all-minilm-l12-v2",
        "intfloat/e5-large-v2",
        "intfloat/e5-base-v2",
        "sentence-transformers/all-minilm-l6-v2",
        "mistralai/codestral-embed-2505",
    ],
    "rerank": [
        "cohere/rerank-4-fast",
        "cohere/rerank-v3.5",
        "nvidia/llama-nemotron-rerank-vl-1b-v2:free",
        "cohere/rerank-4-pro",
    ],
    "video": [
        "google/veo-3.1-fast",
        "google/veo-3.1",
        "bytedance/seedance-2.0",
        "google/veo-3.1-lite",
        "x-ai/grok-imagine-video",
        "bytedance/seedance-2.0-fast",
        "bytedance/seedance-1-5-pro",
        "kwaivgi/kling-v3.0-pro",
        "kwaivgi/kling-v3.0-std",
        "alibaba/wan-2.7",
        "alibaba/happyhorse-1.1",
        "alibaba/wan-2.6",
        "kwaivgi/kling-video-o1",
        "minimax/hailuo-2.3",
        "openai/sora-2-pro",
        "alibaba/happyhorse-1.0",
    ],
    "speech": [
        "google/gemini-3.1-flash-tts-preview",
        "hexgrad/kokoro-82m",
        "x-ai/grok-voice-tts-1.0",
        "microsoft/mai-voice-2",
        "mistralai/voxtral-mini-tts-2603",
        "canopylabs/orpheus-3b-0.1-ft",
        "sesame/csm-1b",
        "zyphra/zonos-v0.1-transformer",
        "zyphra/zonos-v0.1-hybrid",
    ],
    "transcription": [
        "openai/whisper-large-v3",
        "nvidia/parakeet-tdt-0.6b-v3",
        "openai/gpt-4o-mini-transcribe",
        "openai/whisper-large-v3-turbo",
        "qwen/qwen3-asr-flash-2026-02-10",
        "openai/gpt-4o-transcribe",
        "openai/whisper-1",
        "mistralai/voxtral-mini-transcribe",
        "google/chirp-3",
        "microsoft/mai-transcribe-1.5",
    ],
}


# OR's `weekly_category` is also OR's authoritative SERVICE-TYPE signal.
# Many of the 231 sitemap-ingested rows + some pre-existing rows have
# service_type='llm' by default. Gemini Flash IMAGE ended up as llm.
# Fix at the same time we write the rank.
_CATEGORY_TO_SERVICE_TYPE = {
    "text": "llm",
    "image": "image_gen",
    "video": "video_gen",
    "speech": "tts",
    "transcription": "stt",
    "embedding": "embedding",
    "rerank": "rerank",
}


def apply_snapshot(db_path: Path = DB_PATH, apply: bool = False) -> dict:
    """Walk the embedded snapshot. For each (category, [ranked_ids]):
    rank = index+1. Write to DB if --apply.

    Also reclassifies service_type when it's currently 'llm' but OR
    put the model on a non-text /rankings page — OR is authoritative
    for which service tier the model belongs to.
    """
    today_iso = datetime.now(UTC).date().isoformat()
    counts = {
        cat: {"snapshot": len(ids), "matched": 0, "missing": 0, "service_type_reclassified": 0}
        for cat, ids in _RANKINGS_SNAPSHOT.items()
    }

    if not apply:
        return {"today_iso": today_iso, "counts": counts}

    conn = sqlite3.connect(db_path)
    try:
        # Clear all stale ranks first so dropped-out models don't keep yesterday's slot
        conn.execute(
            "UPDATE agents SET weekly_rank = NULL, weekly_category = NULL "
            "WHERE weekly_rank IS NOT NULL OR weekly_category IS NOT NULL"
        )
        for category, ranked_ids in _RANKINGS_SNAPSHOT.items():
            target_st = _CATEGORY_TO_SERVICE_TYPE.get(category)
            for rank, mid in enumerate(ranked_ids, start=1):
                cur = conn.execute(
                    "UPDATE agents SET weekly_rank = ?, weekly_category = ?, "
                    "weekly_last_scraped = ? WHERE id = ?",
                    (rank, category, today_iso, mid),
                )
                if cur.rowcount:
                    counts[category]["matched"] += 1
                    if target_st and target_st != "llm":
                        cur2 = conn.execute(
                            "UPDATE agents SET service_type = ? "
                            "WHERE id = ? AND service_type = 'llm'",
                            (target_st, mid),
                        )
                        if cur2.rowcount:
                            counts[category]["service_type_reclassified"] += 1
                else:
                    counts[category]["missing"] += 1
        conn.commit()
    finally:
        conn.close()

    return {"today_iso": today_iso, "counts": counts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--apply", action="store_true", help="Write to DB")
    args = parser.parse_args()
    result = apply_snapshot(args.db, args.apply)
    print(f"[rankings] snapshot date: {result['today_iso']}")
    for category, c in result["counts"].items():
        print(
            f"  {category:14s} snapshot={c['snapshot']:3d}  matched={c['matched']:3d}  missing={c['missing']:3d}  reclassified={c.get('service_type_reclassified', 0):3d}"
        )
    if not args.apply:
        print("\n(re-run with --apply to write to DB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
