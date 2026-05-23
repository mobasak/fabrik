#!/usr/bin/env python3
"""
Embedding-side per-role selector — sibling to chat's `selector.py`.

Same algorithm shape as `llm_selector.select_llm`: apply hard floors, then
take cheapest-above-floors. Different filter columns (multilingual, code-tuned,
quality_tier-as-cost-proxy) and a separate sqlite table (`embedding_models`).

Pure function of (DB state, role_config). No network, no LLM, no caching.

Consumed by:
- `embedding_role_mapper.py` — orchestrator that loads YAML configs, calls
  this once per role, and persists the result to `embedding_roles`.
- Tests in `tests/kilo_benchmarks/test_embedding_selector.py`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"

# Free-tier id markers (rate-limited routes — never suitable for batch).
FREE_MARKERS = (":free", "/free")

# Sentinel pricing floor — embedding_models_db writes -1.0 when pricing is
# unparseable; we always reject those rows.
PRICE_SENTINEL_FLOOR = 0.0


class NoEligibleEmbeddingError(RuntimeError):
    """Raised when no embedding model satisfies a role's floors."""


def select_for_role(
    role_cfg: dict[str, Any],
    *,
    db_path: Path | str = DB_PATH,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Apply the role's floors to `embedding_models` and return the
    cheapest-above-floors rows, ordered for priority assignment.

    Returns up to `limit` rows (defaults to `role_cfg["slots"]`).
    Each row is a dict with the full embedding_models columns plus
    `score_used` (the cost-axis value the row was sorted by) and
    `score_type` ("input_cost_per_m").

    Raises NoEligibleEmbeddingError if zero rows survive the floors.
    """
    min_quality_tier = int(role_cfg.get("min_quality_tier", 1))
    min_context_window_k = int(role_cfg.get("min_context_window_k", 1))
    require_multilingual = bool(role_cfg.get("require_multilingual", False))
    require_code_tuned = bool(role_cfg.get("require_code_tuned", False))
    allow_free = bool(role_cfg.get("allow_free", False))
    stability_required = bool(role_cfg.get("stability_required", True))
    cost_axis = role_cfg.get("cost_axis", "input")
    if cost_axis != "input":
        raise ValueError(f"unsupported cost_axis={cost_axis!r}; embeddings only support 'input'")

    slots = int(role_cfg.get("slots", 1))
    if limit is None:
        limit = slots

    sql_parts = [
        "SELECT * FROM embedding_models",
        "WHERE status = 'active'",
        "AND blocked = 0",
        "AND quality_tier >= ?",
        "AND context_window_k >= ?",
        "AND input_cost_per_m >= ?",
    ]
    params: list[Any] = [min_quality_tier, min_context_window_k, PRICE_SENTINEL_FLOOR]

    if require_multilingual:
        sql_parts.append("AND is_multilingual = 1")
    if require_code_tuned:
        sql_parts.append("AND is_code_tuned = 1")
    if stability_required:
        sql_parts.append("AND is_ga = 1")
    if not allow_free:
        clauses = " AND ".join("LOWER(id) NOT LIKE ?" for _ in FREE_MARKERS)
        sql_parts.append(f"AND ({clauses})")
        params.extend(f"%{m}%" for m in FREE_MARKERS)

    # Sort: cheapest first, then by quality desc, then by context desc,
    # finally by id for determinism. The tie_break field in YAML is currently
    # informational — the sort below is the canonical implementation.
    sql_parts.append(
        "ORDER BY input_cost_per_m ASC, quality_tier DESC, context_window_k DESC, id ASC"
    )
    sql_parts.append("LIMIT ?")
    params.append(limit)

    sql = "\n".join(sql_parts)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    if not rows:
        raise NoEligibleEmbeddingError(
            f"No embedding satisfies role floors: "
            f"min_quality_tier={min_quality_tier}, "
            f"min_context_window_k={min_context_window_k}, "
            f"require_multilingual={require_multilingual}, "
            f"require_code_tuned={require_code_tuned}, "
            f"allow_free={allow_free}, "
            f"stability_required={stability_required}"
        )

    out: list[dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        d["score_used"] = d["input_cost_per_m"]
        d["score_type"] = "input_cost_per_m"
        out.append(d)
    return out
