#!/usr/bin/env python3
"""
Embedding catalog scraper + DB schema for the embedding selection pipeline.

Sibling to `kilo_agents_db.py` (chat catalog). Key differences:

- Hits OpenRouter's `/v1/embeddings/models` endpoint (separate from the
  chat-completion catalog at `/v1/models`).
- Output cost is always $0 for embeddings — we still store the field for
  parity but it's effectively unused for selection.
- Adds `dimensions`, `is_multilingual`, `is_code_tuned` columns.

Run:
    python scripts/kilo-benchmarks/embedding_models_db.py all

Conventions: stdlib sqlite3, sync. Match sibling scripts.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
DUMP_PATH = SCRIPT_DIR / "embedding_models_dump.json"

OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/models?output_modalities=embeddings"
HTTP_TIMEOUT = 30

# Substrings in id that mark a multilingual-capable embedder. Auto-derived;
# refine in `embedding_role_configs.yaml`'s shortlist filter if needed.
MULTILINGUAL_MARKERS = (
    "multilingual",
    "bge-m3",  # BAAI bge-m3 family — multilingual dense+sparse+colbert
    "qwen3-embedding",
    "gemini-embedding",
    "mistral-embed",
    "nemotron-embed",
)

# Substrings in id that mark a code-tuned embedder.
CODE_MARKERS = (
    "code",
    "codestral",
)

# Substrings that mark a free-tier route (rate-limited, unsuitable for batch).
FREE_MARKERS = (":free", "/free")

# Substrings that mark a non-GA / preview / experimental release.
NON_GA_MARKERS = (
    ":free",
    "preview",
    "alpha",
    "beta",
    "experimental",
    "-exp-",
    "-rc",
)

# Quality-tier thresholds — proxy on input cost until MIRACL / MTEB scores
# are scraped. Embedding cost correlates strongly with model size + recall on
# OpenRouter's catalog today; revisit after the benchmark scraper ships.
#   tier 3 (frontier): input_cost_per_m >= $0.10 (gemini-embedding, openai-3-large, etc.)
#   tier 2 (mid)     : input_cost_per_m >= $0.02 (qwen3-embedding-4b, mistral-embed, etc.)
#   tier 1 (bulk)    : everything else (bge-m3, e5-large, qwen3-embedding-8b, etc.)
# Note: qwen3-embedding-8b lands in tier 1 by cost but ranks high on MIRACL —
# this is the exact gap the benchmark scraper will close.
TIER3_INPUT_COST = 0.10
TIER2_INPUT_COST = 0.02


# ─── Schema ────────────────────────────────────────────────────────────────


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Idempotent. Re-runnable. Adds tables/indexes only if missing."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS embedding_models (
            id TEXT PRIMARY KEY,                -- e.g. "qwen/qwen3-embedding-8b"
            api_id TEXT NOT NULL,
            name TEXT NOT NULL,
            provider TEXT NOT NULL,

            -- Pricing (per 1M input tokens). Output cost is always 0 for embeddings.
            input_cost_per_m REAL NOT NULL DEFAULT 0,

            -- Capabilities
            context_window_k INTEGER DEFAULT 8,    -- in thousands of tokens
            dimensions INTEGER,                    -- nullable when not advertised
            is_multilingual INTEGER DEFAULT 0,
            is_code_tuned INTEGER DEFAULT 0,
            is_ga INTEGER DEFAULT 1,
            quality_tier INTEGER DEFAULT 1,        -- 1=bulk, 2=mid, 3=frontier (cost proxy)

            -- Status
            status TEXT DEFAULT 'active',
            blocked INTEGER DEFAULT 0,
            block_reason TEXT,
            discard_reason TEXT,

            -- Metadata
            last_verified DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_embedding_models_provider
            ON embedding_models(provider);
        CREATE INDEX IF NOT EXISTS idx_embedding_models_status
            ON embedding_models(status);
        CREATE INDEX IF NOT EXISTS idx_embedding_models_input_cost
            ON embedding_models(input_cost_per_m);

        CREATE TABLE IF NOT EXISTS embedding_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            model_id TEXT NOT NULL REFERENCES embedding_models(id),
            priority INTEGER NOT NULL,
            reason TEXT,
            score_used REAL,
            score_type TEXT,
            assigned_by TEXT,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(role, priority)
        );

        CREATE INDEX IF NOT EXISTS idx_embedding_roles_role
            ON embedding_roles(role);
        CREATE INDEX IF NOT EXISTS idx_embedding_roles_model
            ON embedding_roles(model_id);

        -- Append-only daily snapshot for migration audit (parallel to
        -- agent_roles_history). Lets us see when the day's winner per role
        -- changed without overwriting the live row in embedding_roles.
        CREATE TABLE IF NOT EXISTS embedding_roles_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            priority INTEGER NOT NULL,
            model_id TEXT NOT NULL,
            snapshot_date DATE NOT NULL,
            score_used REAL,
            input_cost_per_m REAL,
            assigned_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(role, priority, snapshot_date)
        );

        CREATE INDEX IF NOT EXISTS idx_embedding_roles_hist_date
            ON embedding_roles_history(snapshot_date);
        CREATE INDEX IF NOT EXISTS idx_embedding_roles_hist_role
            ON embedding_roles_history(role);
        """
    )
    conn.commit()


# ─── Derivation helpers ────────────────────────────────────────────────────


def derive_is_multilingual(model_id: str) -> int:
    lower = model_id.lower()
    return 1 if any(m in lower for m in MULTILINGUAL_MARKERS) else 0


def derive_is_code_tuned(model_id: str) -> int:
    lower = model_id.lower()
    return 1 if any(m in lower for m in CODE_MARKERS) else 0


def derive_is_ga(model_id: str) -> int:
    lower = model_id.lower()
    return 0 if any(m in lower for m in NON_GA_MARKERS) else 1


def derive_quality_tier(input_cost_per_m: float) -> int:
    """Cost-based proxy. Replace with MIRACL/MTEB-based scoring when available."""
    if input_cost_per_m < 0:
        return 1  # sentinel pricing — treat as bulk until verified
    if input_cost_per_m >= TIER3_INPUT_COST:
        return 3
    if input_cost_per_m >= TIER2_INPUT_COST:
        return 2
    return 1


# ─── OpenRouter fetch ──────────────────────────────────────────────────────


def fetch_catalog() -> list[dict[str, Any]]:
    """Fetch the live embedding-models catalog from OpenRouter."""
    req = Request(
        OPENROUTER_EMBEDDINGS_URL,
        headers={"User-Agent": "fabrik-embedding-scraper/1.0"},
    )
    try:
        with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as e:
        raise RuntimeError(f"failed to fetch {OPENROUTER_EMBEDDINGS_URL}: {e}") from e
    return payload.get("data", [])


# ─── Normalization ─────────────────────────────────────────────────────────


_DIM_RE = re.compile(r"(\d+)\s*(?:dim|dimension|d)\b", re.IGNORECASE)


def normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert one raw OpenRouter row into our schema."""
    model_id = raw.get("id", "") or ""
    pricing = raw.get("pricing", {}) or {}
    prompt_per_token = pricing.get("prompt", "0")
    try:
        input_cost_per_m = float(prompt_per_token) * 1_000_000
    except (TypeError, ValueError):
        input_cost_per_m = -1.0  # sentinel — flagged by selector

    context_length = raw.get("context_length") or 0
    context_window_k = max(1, int(context_length) // 1000)

    # Try to recover dimensions from description / per_request_limits if present.
    # Most rows don't expose this; populate NULL if unknown.
    dim: int | None = None
    description = raw.get("description") or ""
    m = _DIM_RE.search(description)
    if m:
        try:
            dim = int(m.group(1))
        except ValueError:
            dim = None

    provider = model_id.split("/", 1)[0] if "/" in model_id else "unknown"
    name = raw.get("name") or model_id

    return {
        "id": model_id,
        "api_id": model_id,
        "name": name,
        "provider": provider,
        "input_cost_per_m": input_cost_per_m,
        "context_window_k": context_window_k,
        "dimensions": dim,
        "is_multilingual": derive_is_multilingual(model_id),
        "is_code_tuned": derive_is_code_tuned(model_id),
        "is_ga": derive_is_ga(model_id),
        "quality_tier": derive_quality_tier(input_cost_per_m),
    }


# ─── Sync ──────────────────────────────────────────────────────────────────


def sync(db_path: Path = DB_PATH) -> dict[str, int]:
    """Full sync: fetch → normalize → upsert. Idempotent."""
    raw_catalog = fetch_catalog()
    DUMP_PATH.write_text(json.dumps(raw_catalog, indent=2, default=str))

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        _ensure_schema(conn)

        inserted = 0
        updated = 0
        for raw in raw_catalog:
            n = normalize(raw)
            cursor = conn.execute("SELECT id FROM embedding_models WHERE id = ?", (n["id"],))
            existing = cursor.fetchone()

            if existing is None:
                conn.execute(
                    """
                    INSERT INTO embedding_models (
                        id, api_id, name, provider,
                        input_cost_per_m,
                        context_window_k, dimensions,
                        is_multilingual, is_code_tuned, is_ga, quality_tier,
                        status, last_verified, updated_at
                    ) VALUES (
                        :id, :api_id, :name, :provider,
                        :input_cost_per_m,
                        :context_window_k, :dimensions,
                        :is_multilingual, :is_code_tuned, :is_ga, :quality_tier,
                        'active', DATE('now'), CURRENT_TIMESTAMP
                    )
                    """,
                    n,
                )
                inserted += 1
            else:
                conn.execute(
                    """
                    UPDATE embedding_models SET
                        api_id = :api_id,
                        name = :name,
                        provider = :provider,
                        input_cost_per_m = :input_cost_per_m,
                        context_window_k = :context_window_k,
                        dimensions = COALESCE(:dimensions, dimensions),
                        is_multilingual = :is_multilingual,
                        is_code_tuned = :is_code_tuned,
                        is_ga = :is_ga,
                        quality_tier = :quality_tier,
                        last_verified = DATE('now'),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id
                    """,
                    n,
                )
                updated += 1

        conn.commit()
        return {"inserted": inserted, "updated": updated, "total": len(raw_catalog)}
    finally:
        conn.close()


# ─── CLI ───────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Embedding catalog scraper")
    parser.add_argument(
        "command",
        choices=("all", "schema-only"),
        nargs="?",
        default="all",
        help="all=fetch+upsert (default); schema-only=create tables, no fetch",
    )
    args = parser.parse_args(argv)

    if args.command == "schema-only":
        conn = sqlite3.connect(DB_PATH)
        try:
            _ensure_schema(conn)
            print("[embedding_models_db] schema ensured")
        finally:
            conn.close()
        return 0

    print(f"[embedding_models_db] fetching {OPENROUTER_EMBEDDINGS_URL}")
    result = sync()
    print(
        f"[embedding_models_db] inserted={result['inserted']} "
        f"updated={result['updated']} total={result['total']}"
    )
    print(f"[embedding_models_db] raw dump → {DUMP_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
