#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_seed_specialty_catalog.py
"""Phase A of best-model-suggester — seed the specialty catalog + set reachable_with_existing_keys.

Reads docs/reference/kilo/AI_VENDOR_ACCESS.md (hand-authored — the single source of
truth for "accessible") and:

1. Migrates `agents` with two new columns: `quality_elo` REAL, and
   `reachable_with_existing_keys` INTEGER NOT NULL DEFAULT 0.
2. Parses the catalog into a `{db_provider_id: accessible_bool}` dict.
3. Seeds the missing TTS / STT / translation / image_gen rows from
   `specialty_pricing.PRICING` (owned by the specialty-bench plan), setting
   `reachable_with_existing_keys = 1` when the row's provider is in the accessible
   set.
4. Backfills `quality_elo` for image_gen + tts rows from the two live Arenas
   (ArtificialAnalysis image + HF TTS Arena V2) — only when a row's `id` matches
   an exact hardcoded key. Non-matching rows stay NULL.

Idempotent: re-running is a no-op (INSERT OR IGNORE + PRAGMA-guarded migration).
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "kilo_agents.db"
CATALOG_PATH = (
    Path(__file__).parent.parent.parent
    / "docs"
    / "reference"
    / "kilo"
    / "AI_VENDOR_ACCESS.md"
)

MIGRATION_SQL = [
    "ALTER TABLE agents ADD COLUMN quality_elo REAL",
    "ALTER TABLE agents ADD COLUMN reachable_with_existing_keys INTEGER NOT NULL DEFAULT 0",
]

# Grounded 2026-07-05 from https://artificialanalysis.ai/image/arena (spec External deps).
# Only rows whose `id` matches a key here get an Elo assignment; every other row stays NULL.
# TTS Arena leaders (Vocu V3.0, Inworld TTS MAX) have no matching row in the DB, so no
# tts entries here — see plan Residual #1.
_QUALITY_ELO_BY_ID = {
    "openai/gpt-image-2": 1339,
    "microsoft/mai-image-2.5": 1271,
    "google/gemini-3-pro-image": 1265,  # HiDream proxy
    "google/gemini-3.1-flash-image": 1230,
}


def _migrate(conn: sqlite3.Connection) -> None:
    """Idempotent — skips columns that already exist.

    Re-checks `PRAGMA table_info` on every iteration so an ALTER earlier in the
    loop (that adds one of MIGRATION_SQL's columns) is visible when the next
    iteration's guard runs.
    """
    for stmt in MIGRATION_SQL:
        # "ALTER TABLE agents ADD COLUMN <col> <type>":
        # split() → ["ALTER","TABLE","agents","ADD","COLUMN","<col>","<type>"] → index 5.
        parts = stmt.split()
        col = parts[5]
        existing = {row[1] for row in conn.execute("PRAGMA table_info(agents)")}
        if col not in existing:
            conn.execute(stmt)


def parse_vendor_catalog(md_path: Path) -> dict[str, bool]:
    """Return `{db_provider_id: accessible_bool}`. ✅/⚠️ → True; ❌ or missing → False.

    Iterates the file line-by-line, keeping only pipe-table rows whose first
    non-empty cell is a Vendor value (not a header/separator). The provider
    column is comma-split and each token is trimmed — the seeder relies on
    those tokens matching `agents.provider` exactly.
    """
    text = md_path.read_text(encoding="utf-8")
    accessible: dict[str, bool] = {}
    for line in text.splitlines():
        if not line.startswith("| "):
            continue
        if line.startswith("| ---") or line.startswith("|---") or line.startswith("| Vendor"):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 4:
            continue
        _vendor, providers, _auth, status = cols[0], cols[1], cols[2], cols[3]
        is_accessible = "✅" in status or "⚠️" in status
        for pid in [p.strip() for p in providers.split(",") if p.strip()]:
            if pid == "(none — deprecated)" or pid.startswith("("):
                # "(none)" / "(none — routed via ...)" / "(peer gateway — ...)" — not a real provider id.
                continue
            # Once a provider is marked accessible anywhere, keep it accessible
            # (a vendor might appear across two rows — accessible via one path wins).
            accessible[pid] = accessible.get(pid, False) or is_accessible
    return accessible


def _infer_service_type(model_id: str, meta: dict) -> str:
    """Map a specialty_pricing meta dict to an agents.service_type value."""
    via = meta.get("via", "")
    # Image gen routes: per_image or per_generation via a known image vendor.
    if "per_image" in meta:
        return "image_gen"
    if "per_generation" in meta and via in {
        "fal_ai",
        "recraft_direct",
        "replicate",
        "replicate_official",
        "openrouter",
    }:
        return "image_gen"
    if "per_char" in meta:
        # DashScope translation charges per-char; TTS also per-char. Split by via.
        if via in {"dashscope_direct"}:
            return "translation"
        return "tts"
    if "per_minute" in meta:
        return "stt"
    if "per_generation" in meta:
        return "music_gen"
    return "unknown"


def _cost_per_million(meta: dict) -> float:
    """Normalize a specialty_pricing entry to cost per 1M units (cost * 1e6)."""
    if "per_image" in meta:
        return meta["per_image"] * 1_000_000
    if "per_char" in meta:
        return meta["per_char"] * 1_000_000
    if "per_minute" in meta:
        return meta["per_minute"] * 1_000_000
    if "per_generation" in meta:
        return meta["per_generation"] * 1_000_000
    return 0.0


def _pricing_unit(meta: dict) -> str:
    """The `pricing_unit` column value that matches this pricing shape."""
    if "per_image" in meta:
        return "image"
    if "per_char" in meta:
        return "M-chars"
    if "per_minute" in meta:
        return "audio-min"
    if "per_generation" in meta:
        return "audio-min"
    return "M-tokens"


def seed_specialty_rows(conn: sqlite3.Connection, accessible: dict[str, bool]) -> int:
    """Insert missing TTS/STT/translation/image_gen rows from specialty_pricing.PRICING.

    Sets `reachable_with_existing_keys` based on the parsed catalog. Idempotent:
    INSERT OR IGNORE for new rows; UPDATE ... WHERE ... rewrites reachable to
    match the latest catalog even for pre-existing rows (a vendor going from ❌
    to ✅ propagates immediately).
    """
    sys.path.insert(0, str(Path(__file__).parent))
    from specialty_pricing import PRICING  # noqa: E402

    count = 0
    for model_id, meta in PRICING.items():
        service_type = _infer_service_type(model_id, meta)
        if service_type not in {"tts", "stt", "translation", "image_gen", "music_gen"}:
            continue
        provider = model_id.split("/", 1)[0]
        reachable = 1 if accessible.get(provider) else 0
        cost_per_m = _cost_per_million(meta)
        pricing_unit = _pricing_unit(meta)
        conn.execute(
            "INSERT OR IGNORE INTO agents "
            "(id, api_id, name, provider, service_type, "
            " pricing_unit, input_cost_per_m, output_cost_per_m, status, "
            " reachable_with_existing_keys, last_verified) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'active', ?, DATE('now'))",
            (
                model_id,
                model_id,
                model_id,
                provider,
                service_type,
                pricing_unit,
                cost_per_m,
                reachable,
            ),
        )
        # Backfill reachable flag on existing rows (idempotent — matches the
        # latest catalog even for pre-existing rows).
        conn.execute(
            "UPDATE agents SET reachable_with_existing_keys = ? WHERE id = ?",
            (reachable, model_id),
        )
        count += 1
    return count


def _seed_quality_elo(conn: sqlite3.Connection) -> None:
    """Backfill quality_elo for rows whose id matches a hardcoded Arena entry.

    Only touches matching ids; every other row stays NULL. Idempotent.
    """
    for model_id, elo in _QUALITY_ELO_BY_ID.items():
        conn.execute(
            "UPDATE agents SET quality_elo = ? WHERE id = ?",
            (elo, model_id),
        )


def main() -> int:
    accessible = parse_vendor_catalog(CATALOG_PATH)
    conn = sqlite3.connect(DB_PATH)
    try:
        _migrate(conn)
        n = seed_specialty_rows(conn, accessible)
        _seed_quality_elo(conn)
        conn.commit()
        print(
            f"seeded/updated {n} specialty rows; "
            f"{sum(accessible.values())} accessible providers"
        )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
