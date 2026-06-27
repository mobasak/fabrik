#!/usr/bin/env python3
"""Per-category selector — sibling to `llm_selector.py` and `embedding_selector.py`.

Phase 3 of the OpenRouter routing plan
(`docs/development/plans/2026-06-27-plan-openrouter-routing.md` §9.1).

Pure function of (DB state, category_config). No network, no LLM, no
caching. Deterministic: same DB + same config → byte-identical result.

Consumed by:
- `category_route_mapper.py` — orchestrator that iterates the YAML
  configs once per category and persists winners.
- Tests in `tests/kilo_benchmarks/test_category_selector.py`.

Mirror of `embedding_selector.py:select_for_role` — same shape, different
filter columns (chat-side `has_vision`/`has_tools`/`has_reasoning` instead
of embedding-side `is_multilingual`/`is_code_tuned`).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"

# Free-tier id markers (same constant family as llm_selector.py:47 +
# embedding_selector.py:27). Three duplicates in the codebase — kept as-is
# per plan §15 "Out of scope" R3: centralizing the constant is a separate
# refactor.
FREE_MARKERS = (":free", "/free")

# Sentinel pricing floor — rows with negative pricing are catalog errors;
# never serve them as routes.
PRICE_SENTINEL_FLOOR = 0.0


class NoEligibleCategoryError(RuntimeError):
    """Raised when no model satisfies a category's floors."""


def select_for_category(
    category: str,
    cfg: dict[str, Any],
    *,
    db_path: Path | str = DB_PATH,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Apply the category's floors against `agents JOIN agent_categories`
    and return up to N rows ranked by the category's `sort_key`.

    Floors honored (all optional):
      slots                  → default LIMIT
      min_quality_tier       → quality_tier >= ?
      min_context_window_k   → context_window_k >= ?
      require_vision         → has_vision = 1
      require_tools          → has_tools = 1
      require_reasoning      → has_reasoning = 1
      allow_free             → False excludes :free / /free ids
      stability_required     → True restricts to is_ga = 1
      sort_key               → 'input_cost_per_m ASC' (default)
                               OR 'tbench_accuracy DESC'
                               OR 'context_window_k DESC'

    Tie-break is fixed: COALESCE(arena_elo,0) DESC, id ASC. Determinism
    matters here — every wsl_startup_hook.sh run must produce identical
    output for the same DB state.

    Raises NoEligibleCategoryError when zero rows survive the filter.
    The orchestrator catches this and emits a graceful empty-routes
    entry per plan §9.2.
    """
    # Pass A Finding 1: SQLite interprets `LIMIT -1` as "no limit" and
    # `LIMIT 0` as zero rows — both subtly wrong for a typo in the YAML.
    # Fail loud at config-load time instead of producing a surprising
    # full-table-scan or a silent empty result.
    #
    # Pass B Finding 2: `int(3.5) → 3` silently truncates float configs.
    # `bool` is a subclass of `int` in Python (`isinstance(True, int) → True`)
    # so we also exclude bools — `slots: yes` in YAML parses as True which
    # would otherwise quietly become `slots: 1`. Strict typing here.
    slots_raw = cfg.get("slots", 1)
    if isinstance(slots_raw, bool) or not isinstance(slots_raw, int):
        raise ValueError(
            f"category {category!r}: slots must be an integer, got "
            f"{type(slots_raw).__name__}={slots_raw!r}"
        )
    slots = slots_raw
    if slots <= 0:
        raise ValueError(
            f"category {category!r}: slots must be >= 1, got {slots} "
            "(SQLite's `LIMIT -1` means 'no limit' — a typo here would "
            "silently emit every eligible candidate)"
        )
    if limit is None:
        limit = slots

    min_quality_tier = int(cfg.get("min_quality_tier", 1))
    min_context_window_k = int(cfg.get("min_context_window_k", 1))
    require_vision = bool(cfg.get("require_vision", False))
    require_tools = bool(cfg.get("require_tools", False))
    require_reasoning = bool(cfg.get("require_reasoning", False))
    allow_free = bool(cfg.get("allow_free", False))
    stability_required = bool(cfg.get("stability_required", False))
    # `.strip()` + allowlist is the injection defense — never remove
    # either without re-reading Pass A Finding 4. A whitespace-padded
    # YAML value like `sort_key: "  input_cost_per_m ASC; DROP TABLE..."`
    # would otherwise slip past a naive equality check.
    sort_key = str(cfg.get("sort_key", "input_cost_per_m ASC")).strip()

    # Sort-key allowlist — never inline operator input into SQL. The
    # YAML is operator-editable so this guard prevents an accidental
    # `sort_key: "1; DROP TABLE agents"` from doing damage (low-risk
    # given the file is hub-only, but defense-in-depth).
    sort_clauses = {
        "input_cost_per_m ASC": "a.input_cost_per_m ASC",
        "tbench_accuracy DESC": "COALESCE(a.tbench_accuracy, 0) DESC",
        "context_window_k DESC": "a.context_window_k DESC",
    }
    if sort_key not in sort_clauses:
        raise ValueError(
            f"category {category!r}: unsupported sort_key={sort_key!r}; "
            f"allowed: {sorted(sort_clauses)}"
        )
    primary_sort = sort_clauses[sort_key]

    sql_parts = [
        "SELECT a.* FROM agents a",
        "JOIN agent_categories ac ON ac.agent_id = a.id",
        "WHERE ac.category = ?",
        "AND a.status = 'active'",
        "AND a.blocked = 0",
        "AND a.quality_tier >= ?",
        "AND a.context_window_k >= ?",
        "AND a.input_cost_per_m >= ?",
    ]
    params: list[Any] = [category, min_quality_tier, min_context_window_k, PRICE_SENTINEL_FLOOR]

    if require_vision:
        sql_parts.append("AND a.has_vision = 1")
    if require_tools:
        sql_parts.append("AND a.has_tools = 1")
    if require_reasoning:
        sql_parts.append("AND a.has_reasoning = 1")
    if stability_required:
        sql_parts.append("AND a.is_ga = 1")
    if not allow_free:
        # LOWER(id) NOT LIKE %:free% AND LOWER(id) NOT LIKE %/free%
        clauses = " AND ".join("LOWER(a.id) NOT LIKE ?" for _ in FREE_MARKERS)
        sql_parts.append(f"AND ({clauses})")
        params.extend(f"%{m}%" for m in FREE_MARKERS)

    sql_parts.append(f"ORDER BY {primary_sort}, COALESCE(a.arena_elo, 0) DESC, a.id ASC")
    sql_parts.append("LIMIT ?")
    params.append(limit)

    sql = "\n".join(sql_parts)

    conn = sqlite3.connect(db_path)
    # PRAGMA fk is per-connection per Pass B Finding 3 + Phase 1 plan
    # contract. Read-only here, but consistency matters if the selector
    # is ever wrapped in a transaction that also mutates agent_categories.
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    if not rows:
        raise NoEligibleCategoryError(
            f"No model satisfies category={category!r} floors: "
            f"min_quality_tier={min_quality_tier}, "
            f"min_context_window_k={min_context_window_k}, "
            f"require_vision={require_vision}, "
            f"require_tools={require_tools}, "
            f"require_reasoning={require_reasoning}, "
            f"allow_free={allow_free}, "
            f"stability_required={stability_required}, "
            f"sort_key={sort_key!r}"
        )

    out: list[dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        # Surface the sort-axis value so the route mapper can persist
        # provenance ("we picked this because tbench_accuracy was X").
        sort_col = sort_key.split()[0]
        d["score_used"] = d.get(sort_col)
        d["score_type"] = sort_col
        out.append(d)
    return out
