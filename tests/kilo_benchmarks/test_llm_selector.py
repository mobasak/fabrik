"""Integration tests for `scripts/kilo-benchmarks/llm_selector.py`.

Run against the REAL `kilo_agents.db` (read-only) — no mocks. The DB refreshes
daily via `wsl_startup_hook.sh`, so tests must adapt to changes in the catalog.
We never hardcode an agent_id as the expected value; instead we re-query the DB
with the same SQL the selector uses and assert the selector picks the same row
the SQL would pick.

Per `45-testing-strategy.md`: prefer integration tests against real artifacts
to catch shape drift; mocks would freeze the catalog.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts" / "kilo-benchmarks"
DB_PATH = SCRIPT_DIR / "kilo_agents.db"

# Hyphen in dir name → can't use a normal package import; load the module by
# filesystem path. Same trick used by the role_mapper smoke harnesses.
_spec = importlib.util.spec_from_file_location(
    "llm_selector", SCRIPT_DIR / "llm_selector.py"
)
assert _spec and _spec.loader
llm_selector = importlib.util.module_from_spec(_spec)
sys.modules["llm_selector"] = llm_selector
_spec.loader.exec_module(llm_selector)  # type: ignore[union-attr]

select_llm = llm_selector.select_llm
NoEligibleAgentError = llm_selector.NoEligibleAgentError
CONTEXT_HEADROOM = llm_selector.CONTEXT_HEADROOM
FREE_MARKERS = llm_selector.FREE_MARKERS


@pytest.fixture(scope="module")
def db_conn():
    if not DB_PATH.exists():
        pytest.skip(f"DB not present at {DB_PATH}; run kilo_agents_db.py first")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def _expected_cheapest(
    db_conn: sqlite3.Connection,
    *,
    min_tier: int,
    cost_axis: str,
    input_tokens: int,
    needs_vision: bool = False,
    allow_free: bool = False,
    stability_required: bool = True,
):
    """Re-implement the selector's filter+sort using a fresh query.

    Identical logic to `select_llm` but expressed independently so a bug in
    one is not masked by an identical bug in the other. Returns a sqlite Row
    or None (mirrors `LIMIT 1`).
    """
    cost_col = "input_cost_per_m" if cost_axis == "input" else "output_cost_per_m"
    required_ctx = int(input_tokens * CONTEXT_HEADROOM)
    sql = [
        "SELECT * FROM agents",
        "WHERE status='active'",
        "AND blocked=0",
        "AND quality_tier>=?",
        "AND input_cost_per_m>=0",
        "AND output_cost_per_m>=0",
        "AND (context_window_k * 1000) >= ?",
    ]
    params: list = [min_tier, required_ctx]
    if needs_vision:
        sql.append("AND has_vision=1")
    if stability_required:
        sql.append("AND is_ga=1")
    if not allow_free:
        for m in FREE_MARKERS:
            sql.append("AND LOWER(id) NOT LIKE ?")
            params.append(f"%{m}%")
    sql.append(
        f"ORDER BY {cost_col} ASC, "
        "COALESCE(arena_elo, 0) DESC, "
        "COALESCE(tbench_accuracy, 0) DESC, "
        "id ASC LIMIT 1"
    )
    return db_conn.execute("\n".join(sql), params).fetchone()


# ─── Acceptance criteria from the ticket §5 ────────────────────────────────


def test_long_digest_picks_cheapest_input_axis(db_conn):
    """select_llm('long_digest', 50_000) → lowest input-cost tier-1 GA model
    with context window >= ~60k tokens (50k * 1.2 headroom)."""
    expected = _expected_cheapest(
        db_conn,
        min_tier=1,
        cost_axis="input",
        input_tokens=50_000,
    )
    assert expected is not None, "DB must have at least one tier-1 GA model with 60k+ ctx"
    actual = select_llm("long_digest", 50_000)
    assert actual["id"] == expected["id"]
    assert (actual["context_window_k"] or 0) * 1000 >= 50_000 * CONTEXT_HEADROOM
    assert actual["quality_tier"] >= 1
    assert actual["is_ga"] == 1


def test_synthesize_picks_cheapest_output_axis_at_tier_two_or_higher(db_conn):
    expected = _expected_cheapest(
        db_conn,
        min_tier=2,
        cost_axis="output",
        input_tokens=50_000,
    )
    assert expected is not None
    actual = select_llm("synthesize", 50_000)
    assert actual["id"] == expected["id"]
    assert actual["quality_tier"] >= 2


def test_reason_requires_tier_three(db_conn):
    """select_llm('reason', 900_000) → tier-3 model with ctx >= ~1.08M, OR
    raises NoEligibleAgentError if none qualifies."""
    expected = _expected_cheapest(
        db_conn,
        min_tier=3,
        cost_axis="output",
        input_tokens=900_000,
    )
    if expected is None:
        with pytest.raises(NoEligibleAgentError):
            select_llm("reason", 900_000)
    else:
        actual = select_llm("reason", 900_000)
        assert actual["id"] == expected["id"]
        assert actual["quality_tier"] >= 3
        assert (actual["context_window_k"] or 0) * 1000 >= 900_000 * CONTEXT_HEADROOM


def test_input_tokens_beyond_every_window_raises(db_conn):
    """Skip-don't-pad: if NO model can hold the input, raise — never return
    a too-small model."""
    max_ctx_k = db_conn.execute(
        "SELECT MAX(context_window_k) FROM agents WHERE status='active' AND blocked=0"
    ).fetchone()[0]
    # 10x bigger than the largest known window — guarantees no fit.
    impossible_tokens = (max_ctx_k or 0) * 1000 * 10
    if impossible_tokens <= 0:
        pytest.skip("No active models in DB")
    with pytest.raises(NoEligibleAgentError):
        select_llm("long_digest", impossible_tokens)


def test_free_models_excluded_for_every_shipped_profile(db_conn):
    """All shipped profiles have allow_free=False — selector must never
    return a free-tier model for them."""
    import yaml

    with open(SCRIPT_DIR / "task_profiles.yaml") as f:
        profiles = yaml.safe_load(f)["profiles"]

    for profile_name, cfg in profiles.items():
        # Use a small token count so context is not the dominant filter.
        try:
            picked = select_llm(profile_name, 1_000)
        except NoEligibleAgentError:
            # No live model meets the floor for this profile right now —
            # that's a valid state, not a free-tier leak.
            continue
        lower_id = picked["id"].lower()
        assert not any(m in lower_id for m in FREE_MARKERS), (
            f"profile {profile_name!r} returned free-tier id {picked['id']!r}"
        )
        assert cfg["allow_free"] is False, (
            f"profile {profile_name!r} unexpectedly has allow_free=True"
        )


def test_preview_models_excluded_when_stability_required(db_conn):
    """is_ga=0 rows must never surface for stability_required profiles."""
    import yaml

    with open(SCRIPT_DIR / "task_profiles.yaml") as f:
        profiles = yaml.safe_load(f)["profiles"]

    for profile_name, cfg in profiles.items():
        if not cfg.get("stability_required", False):
            continue
        try:
            picked = select_llm(profile_name, 1_000)
        except NoEligibleAgentError:
            continue
        assert picked["is_ga"] == 1, (
            f"profile {profile_name!r} (stability_required) returned is_ga=0 id "
            f"{picked['id']!r}"
        )


def test_determinism_same_args_same_result(db_conn):
    """Pure function: same (profile, input_tokens, DB state) → identical model."""
    a = select_llm("extract", 50_000)
    b = select_llm("extract", 50_000)
    c = select_llm("extract", 50_000)
    assert a["id"] == b["id"] == c["id"]
    assert a["input_cost_per_m"] == b["input_cost_per_m"] == c["input_cost_per_m"]


def test_unknown_profile_raises_keyerror():
    with pytest.raises(KeyError):
        select_llm("does_not_exist", 1_000)


def test_negative_input_tokens_rejected():
    with pytest.raises(ValueError):
        select_llm("extract", -1)


def test_tokenizer_profile_returns_cheapest_input_cost(db_conn):
    """Tokenizer profile is the explicit alias for 'cheapest input-axis tier-1'.
    Must agree with `extract` when input sizes are identical."""
    a = select_llm("tokenizer", 5_000)
    b = select_llm("extract", 5_000)
    assert a["id"] == b["id"], (
        f"tokenizer ({a['id']}) and extract ({b['id']}) should agree at the same "
        "input size — they share floors and cost axis"
    )
