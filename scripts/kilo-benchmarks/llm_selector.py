#!/usr/bin/env python3
"""
Deterministic LLM selector — sibling to the coding-agent role mapper.

Pipelines call:

    from llm_selector import select_llm, NoEligibleAgentError

    model = select_llm("long_digest", input_tokens=50_000)
    # → {"id": "qwen/qwen3.5-flash-02-23", "provider": "qwen",
    #    "context_window_k": 1000, "input_cost_per_m": 0.065, ...}

Pipelines never reference a raw model ID — they always go through a profile.
This file's contract: pure function of (profile, input_tokens, DB state).
No network, no LLM, no randomness, no caching.

Profiles live in task_profiles.yaml. See migrate_selector_columns.py for the
quality_tier / is_ga columns this selector relies on.

Conventions: stdlib sqlite3, sync. Match sibling scripts (pre_filter.py,
role_mapper.py, post_filter.py). This is a local benchmarks tool, not a
deployed service — no asyncpg / FastAPI / Settings / DATABASE_URL.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
PROFILES_PATH = SCRIPT_DIR / "task_profiles.yaml"

# Context headroom multiplier. The window must hold the prompt PLUS the
# output PLUS estimation drift. 1.2x means "20% slack on top of prompt size."
CONTEXT_HEADROOM = 1.2

# Sentinel pricing rows in the live catalog use very negative numbers to mean
# "unknown / broken". Reject those — never return a model with bogus pricing.
PRICE_SENTINEL_FLOOR = 0.0  # input/output must be >= 0

# Substrings in the model id that mark a free-tier route. Free models have
# strict rate limits (~20 rpm / 200 rpd) — banned for stability_required work.
FREE_MARKERS = (":free", "/free")


class NoEligibleAgentError(RuntimeError):
    """Raised when no model satisfies the profile constraints + context fit.

    Message format embeds the profile name, input_tokens, and the smallest
    constraint that failed so callers can decide whether to relax the
    profile or split the request.
    """


def _get_connection(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _load_profile(profile_name: str, profiles_path: Path | str = PROFILES_PATH) -> dict[str, Any]:
    with open(profiles_path) as f:
        data = yaml.safe_load(f)
    profiles = data.get("profiles", {})
    if profile_name not in profiles:
        raise KeyError(
            f"Profile {profile_name!r} not found in {profiles_path}. Available: {sorted(profiles)}"
        )
    return profiles[profile_name]


def _free_id_clause(allow_free: bool) -> tuple[str, list[Any]]:
    """SQL fragment + params to exclude free-tier IDs when allow_free is False.

    Returns raw conjuncts (no leading 'AND') so the caller can splice them
    into the WHERE list cleanly.
    """
    if allow_free:
        return "", []
    clauses = " AND ".join("LOWER(id) NOT LIKE ?" for _ in FREE_MARKERS)
    params: list[Any] = [f"%{m}%" for m in FREE_MARKERS]
    return clauses, params


def select_llm(
    profile: str,
    input_tokens: int,
    *,
    require_vision: bool = False,
    db_path: Path | str = DB_PATH,
    profiles_path: Path | str = PROFILES_PATH,
) -> dict[str, Any]:
    """
    Return the cheapest live model that satisfies the profile and fits
    `input_tokens` with `CONTEXT_HEADROOM` slack.

    Deterministic: same (profile, input_tokens, DB state, profiles file) →
    same result. No network calls, no LLM, no randomness.

    Parameters
    ----------
    profile : str
        Name of a profile in task_profiles.yaml.
    input_tokens : int
        Raw token count for the request. The selector requires
        `context_window_k * 1000 >= input_tokens * CONTEXT_HEADROOM`.
    require_vision : bool, optional
        Force vision routing even if the profile does not require it. Defaults
        to False — the profile's `needs_vision` is the primary source of truth.
    db_path, profiles_path : Path or str
        Override paths (used by tests).

    Returns
    -------
    dict
        Row from the agents table for the winning model. Caller can read
        `id`, `api_id`, `input_cost_per_m`, `output_cost_per_m`,
        `context_window_k`, etc.

    Raises
    ------
    NoEligibleAgentError
        When zero rows survive the filter. Skip-don't-pad: NEVER returns a
        model below the tier floor or with insufficient context.
    KeyError
        When `profile` is not defined in task_profiles.yaml.
    """
    if input_tokens < 0:
        raise ValueError(f"input_tokens must be >= 0, got {input_tokens}")

    cfg = _load_profile(profile, profiles_path)
    min_tier = int(cfg["min_tier"])
    cost_axis = cfg["cost_axis"]
    if cost_axis not in {"input", "output"}:
        raise ValueError(f"profile {profile!r} has invalid cost_axis={cost_axis!r}")
    needs_vision = bool(cfg.get("needs_vision", False)) or require_vision
    allow_free = bool(cfg.get("allow_free", False))
    stability_required = bool(cfg.get("stability_required", False))

    # Required context window (in raw tokens). context_window_k is in *thousands*.
    required_ctx_tokens = int(input_tokens * CONTEXT_HEADROOM)

    # Build SQL. All filters (stages 1-2 from the ticket) collapse into one
    # WHERE clause; cost sort is stage 3; LIMIT 1 + raise-on-empty is stage 4.
    sql_parts = [
        "SELECT * FROM agents",
        "WHERE status = 'active'",
        "AND blocked = 0",
        "AND quality_tier >= ?",
        # Sentinel guards — never return a row with broken pricing.
        "AND input_cost_per_m >= ?",
        "AND output_cost_per_m >= ?",
        # Context fit with headroom. context_window_k is in thousands of tokens.
        "AND (context_window_k * 1000) >= ?",
    ]
    params: list[Any] = [
        min_tier,
        PRICE_SENTINEL_FLOOR,
        PRICE_SENTINEL_FLOOR,
        required_ctx_tokens,
    ]

    if needs_vision:
        sql_parts.append("AND has_vision = 1")

    if stability_required:
        sql_parts.append("AND is_ga = 1")

    free_clause, free_params = _free_id_clause(allow_free)
    if free_clause:
        sql_parts.append(f"AND ({free_clause})")
        params.extend(free_params)

    # Sort: cost ASC, tiebreak by quality DESC then id for determinism.
    cost_col = "input_cost_per_m" if cost_axis == "input" else "output_cost_per_m"
    sql_parts.append(
        f"ORDER BY {cost_col} ASC, "
        "COALESCE(arena_elo, 0) DESC, "
        "tbench_accuracy DESC, "  # NULL last (SQLite) — unbenched below real 0, not tied
        "id ASC"
    )
    sql_parts.append("LIMIT 1")

    sql = "\n".join(sql_parts)

    conn = _get_connection(db_path)
    try:
        row = conn.execute(sql, params).fetchone()
    finally:
        conn.close()

    if row is None:
        raise NoEligibleAgentError(
            f"No agent satisfies profile={profile!r} input_tokens={input_tokens} "
            f"(min_tier={min_tier}, cost_axis={cost_axis}, "
            f"required_ctx_tokens={required_ctx_tokens}, "
            f"needs_vision={needs_vision}, allow_free={allow_free}, "
            f"stability_required={stability_required})"
        )

    return dict(row)


if __name__ == "__main__":
    # Smoke test — exercises every shipped profile with a representative
    # input size. Useful as a manual sanity check after a daily refresh.
    samples = [
        ("tokenizer", 50_000),
        ("extract", 50_000),
        ("classify", 5_000),
        ("summarize", 50_000),
        ("long_digest", 500_000),
        ("synthesize", 50_000),
        ("reason", 50_000),
    ]
    for prof, tokens in samples:
        try:
            m = select_llm(prof, tokens)
            print(
                f"[smoke] {prof:12s} @ {tokens:>8d} tok → {m['id']:50s} "
                f"(ctx={m['context_window_k']}k, in=${m['input_cost_per_m']}/M, "
                f"out=${m['output_cost_per_m']}/M, tier={m['quality_tier']})"
            )
        except NoEligibleAgentError as e:
            print(f"[smoke] {prof:12s} @ {tokens:>8d} tok → NoEligibleAgentError: {e}")
