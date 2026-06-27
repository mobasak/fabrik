#!/usr/bin/env python3
"""Pure-SQL classifier: populates `agent_categories` from `agents`.

Phase 1 of the OpenRouter routing plan
(`docs/development/plans/2026-06-27-plan-openrouter-routing.md` §7.2).

Seven category rules, one INSERT OR REPLACE per category. A model may
match multiple categories (e.g. a coding LLM that's also a general
language model) — the join table's PRIMARY KEY (agent_id, category)
makes this safe; the rules don't try to be mutually exclusive.

Categories mapped to the LLM-bearing packs in `.windsurf/rules/ai/`:
  - speech-audio  → 10-speech-audio.md
  - vision        → 20-vision.md
  - language      → 30-language.md   (general-purpose; excludes coder/code/audio ids;
                                      COALESCE(is_ga, 1) catches NULL is_ga rows)
  - multimodal    → 40-multimodal.md
  - agentic       → 50-agentic.md
  - code          → 60-code.md
  - long-context  → 90-long-context.md

Packs 25-3d-generation.md, 70-data-predictive.md, 80-specialized-domains.md
cover non-LLM vendors and intentionally receive zero rows.

No LLM, no network. Deterministic same-day-same-output behavior.

Run:
    python scripts/kilo-benchmarks/classify_ai_category.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"


# Order matters only for `INSERT OR REPLACE` re-population semantics.
# Each rule is the WHERE clause appended after the standard
# `status='active' AND blocked=0` floor.
RULES: list[tuple[str, str]] = [
    (
        "speech-audio",
        "id LIKE '%whisper%' OR id LIKE '%audio%' OR id LIKE '%voice%' OR id LIKE '%tts%'",
    ),
    (
        "vision",
        "has_vision = 1",
    ),
    (
        "multimodal",
        "has_vision = 1 AND has_tools = 1 AND has_reasoning = 1",
    ),
    (
        "agentic",
        "is_agentic = 1 AND has_tools = 1 AND has_reasoning = 1",
    ),
    (
        "code",
        "id LIKE '%coder%' OR id LIKE '%code%' "
        "OR weighted_coding > 0 OR humaneval_score > 0 OR coding_score > 0",
    ),
    (
        "long-context",
        "context_window_k >= 200",
    ),
    (
        # The language rule is the residual: general-purpose LLMs that are NOT
        # vision, code, or audio specialists. COALESCE handles NULL is_ga and
        # NULL has_vision (Pass 1D D1 — 31 NULL-is_ga rows would otherwise be
        # silently excluded). The `id NOT LIKE '%code%'` exclusion closes the
        # LIKE-rule overlap Pass 1B caught; the 9 score-column overlaps that
        # remain (Pass 2A) are by-design per the multi-category join contract.
        "language",
        "COALESCE(is_ga, 1) = 1 "
        "AND COALESCE(has_vision, 0) = 0 "
        "AND id NOT LIKE '%coder%' "
        "AND id NOT LIKE '%code%' "
        "AND id NOT LIKE '%audio%'",
    ),
]


def _log(msg: str) -> None:
    print(f"[classify_ai_category] {msg}")


def classify(db_path: Path | str = DB_PATH) -> dict[str, int]:
    """Re-populate `agent_categories` from `agents`. Returns row counts
    per category (after the run). Idempotent: same input → same output.

    Rule order does NOT affect category membership — every rule re-queries
    `agents` directly (not "agents minus previously-classified rows"), so a
    model that matches both `code` and `language` gets two rows regardless
    of which rule runs first. Order only affects which `INSERT OR REPLACE`
    "wins" if a (agent_id, category) pair appeared twice, which is
    impossible by construction (each category writes its own bucket).

    Pass B Finding 3 defense-in-depth: a sweep deletes orphan rows
    (agent_categories rows whose agent_id is no longer in `agents`). This
    SHOULD be handled by the FK CASCADE on the schema, but only fires
    when the DELETE-from-agents connection had `PRAGMA foreign_keys = ON`
    — a connection that didn't set the PRAGMA leaves orphans. Belt-and-
    braces, runs before the re-classify so the run is self-healing."""
    conn = sqlite3.connect(db_path)
    try:
        # FK CASCADE only fires when this PRAGMA is ON. Required even though
        # this script only INSERTs (a future CASCADE on agents-row delete
        # would silently fail otherwise).
        conn.execute("PRAGMA foreign_keys = ON")
        if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("PRAGMA foreign_keys could not be enabled.")

        # Pass B Finding 3 defense: clean up orphan rows that an external
        # script may have left if it deleted from `agents` without first
        # setting PRAGMA foreign_keys = ON on its own connection.
        orphan_n = conn.execute(
            "DELETE FROM agent_categories WHERE agent_id NOT IN (SELECT id FROM agents)"
        ).rowcount
        if orphan_n > 0:
            _log(
                f"WARN: deleted {orphan_n} orphan agent_categories rows "
                "(an external script likely deleted from agents without "
                "PRAGMA foreign_keys=ON — CASCADE silently no-opped)"
            )

        # Wipe categories we're about to re-classify (forward-compatible with
        # adding new categories: untouched categories remain).
        categories = [cat for cat, _ in RULES]
        placeholders = ",".join("?" * len(categories))
        conn.execute(
            f"DELETE FROM agent_categories WHERE category IN ({placeholders})",
            categories,
        )

        for category, where in RULES:
            conn.execute(
                "INSERT OR REPLACE INTO agent_categories (agent_id, category) "
                "SELECT id, ? FROM agents "
                f"WHERE status = 'active' AND blocked = 0 AND ({where})",
                (category,),
            )
        conn.commit()

        # Report per-category counts.
        counts: dict[str, int] = {}
        for category, _ in RULES:
            n = conn.execute(
                "SELECT count(*) FROM agent_categories WHERE category = ?",
                (category,),
            ).fetchone()[0]
            counts[category] = n
    finally:
        conn.close()

    total = sum(counts.values())
    _log(
        f"classified {total} rows across {len(counts)} categories: "
        + ", ".join(f"{c}={n}" for c, n in counts.items())
    )
    return counts


if __name__ == "__main__":
    if not DB_PATH.exists():
        _log(f"ERROR: {DB_PATH} does not exist. Run kilo_agents_db.py init first.")
        sys.exit(1)
    classify()
