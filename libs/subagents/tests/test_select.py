"""select.py — worker selection: the 'cheapest model that clears the bar' rule.

Covers the levers the orchestrator uses to pick workers wisely: task-type ranking,
the cost ceiling (min-spend), exclude (reliability), value-vs-quality ordering, and the
public table being a safe copy. Also confirms the ledger records `task_type` (the
flywheel input).
"""

from __future__ import annotations

from datetime import date

import pytest

from subagents import (
    TASK_KINDS,
    TASK_MODEL_TABLE,
    load_task_ranking,
    model_price,
    pick_models,
)
from subagents.ledger import agent_record
from subagents.select import _OUT_PRICE


def test_every_task_kind_returns_ranked_models() -> None:
    for kind in TASK_KINDS:
        picks = pick_models(kind, n=3)
        assert picks, f"{kind} returned no models"
        assert all(m in _OUT_PRICE for m in picks), (
            f"{kind} picked an unpriced model: {picks}"
        )


def test_unknown_task_type_raises() -> None:
    with pytest.raises(ValueError, match="unknown task_type"):
        pick_models("nonsense")


def test_n_limits_the_count() -> None:
    assert len(pick_models("spec", n=1)) == 1
    assert len(pick_models("spec", n=2)) == 2


def test_quality_order_is_the_table_order() -> None:
    # default prefer="quality" returns the seed table's best-first order verbatim
    n = len(TASK_MODEL_TABLE["spec"])
    assert pick_models("spec", n=n) == TASK_MODEL_TABLE["spec"]


def test_max_cost_ceiling_drops_expensive_models() -> None:
    # minimax-m3 ($1.20/M) + deepseek-v4-pro ($0.87) lead 'plan'; a $0.5 ceiling must drop them
    # and keep the cheaper ranked ones (v3.2 $0.34, v4-flash $0.18, m2.5 $0.48) — min-spend guard.
    cheap = pick_models("plan", n=5, max_cost_per_mtok=0.5)
    assert "minimax/minimax-m3" not in cheap
    assert "deepseek/deepseek-v4-pro" not in cheap
    assert cheap and all(_OUT_PRICE[m] <= 0.5 for m in cheap)
    # an impossibly low ceiling filters everything (never raises — returns [])
    assert pick_models("plan", n=5, max_cost_per_mtok=0.0) == []


def test_exclude_removes_a_failed_worker() -> None:
    # the reliability lever: drop a model that failed this session
    picks = pick_models("plan", n=5, exclude=("minimax/minimax-m3",))
    assert "minimax/minimax-m3" not in picks


def test_prefer_value_reranks_toward_cheaper() -> None:
    # spec quality order leads with minimax-m2.5 (rank 1, $0.48); value re-ranks so the
    # nearly-as-good-but-cheaper deepseek-v3.2 ($0.34, rank 2) overtakes it.
    q = pick_models("spec", n=5, prefer="quality")
    v = pick_models("spec", n=5, prefer="value")
    assert q[0] == "minimax/minimax-m2.5"
    assert v[0] == "deepseek/deepseek-v3.2"
    assert set(q) == set(v)  # same candidate set, different order


def test_table_view_is_a_defensive_copy() -> None:
    # mutating the public view must not corrupt the internal default — and must be restored so
    # it can't leak into another test's order.
    original = list(TASK_MODEL_TABLE["spec"])
    try:
        TASK_MODEL_TABLE["spec"].append("garbage/model")
        assert "garbage/model" not in pick_models("spec", n=9)
    finally:
        TASK_MODEL_TABLE["spec"][:] = original


def test_zero_or_negative_n_returns_empty() -> None:
    # a non-positive n is empty, never a Python negative-slice surprise (n=-2 → all-but-2)
    assert pick_models("spec", n=0) == []
    assert pick_models("spec", n=-2) == []


def test_model_price_known_and_unknown() -> None:
    assert model_price("deepseek/deepseek-v3.2") == 0.343
    assert model_price("no/such-model") is None


# The hub's REAL synced doc format (rank_task_subagents.py → TASK_SUBAGENT_SELECTION.md, per the
# fabrik-AI UPSTREAM_FEEDBACK contract): the model is BACKTICKED and avg_cost carries a `$`.
_SYNCED_DOC = """\
Last refresh: 2026-07-06
Formula: success × quality / cost | Window: 90 days | Min runs: 3

### spec (n_total=127)
| rank | model | value | success | avg_cost | avg_quality | n |
|---:|---|---:|---:|---:|---:|---:|
| 1 | `z-ai/glm-5` | 4.82 | 0.94 | $0.3200 | 1.64 | 47 |
| 2 | `minimax/minimax-m2.5` | 4.10 | 0.90 | $0.2000 | 1.50 | 40 |
| 3 | `some/new-model` | 3.50 | 0.88 | $0.1500 | 1.40 | 5 |

### plan (n_total=0)
No aggregated runs yet — pick_models continues to use vendored _TABLE default.
"""


def test_load_task_ranking_parses_synced_doc(tmp_path) -> None:
    p = tmp_path / "TASK_SUBAGENT_SELECTION.md"
    p.write_text(_SYNCED_DOC)
    parsed = load_task_ranking(str(p))
    # spec section → rank-ordered model list; the empty (stub) plan section is dropped
    assert parsed == {"spec": ["z-ai/glm-5", "minimax/minimax-m2.5", "some/new-model"]}


def test_load_task_ranking_min_n_drops_thin_rows(tmp_path) -> None:
    p = tmp_path / "d.md"
    p.write_text(_SYNCED_DOC)
    parsed = load_task_ranking(str(p), min_n=10)  # some/new-model has n=5 → dropped
    assert parsed["spec"] == ["z-ai/glm-5", "minimax/minimax-m2.5"]


def test_load_task_ranking_missing_or_bad_path_is_empty() -> None:
    assert load_task_ranking("/no/such/file.md") == {}
    assert load_task_ranking(None) == {}  # no env, no path


def test_pick_models_prefers_synced_ranking_over_vendored() -> None:
    # a synced ranking that REORDERS spec (within the ≤$1.5 pool) wins over the seed _TABLE order:
    # here deepseek-v4-flash leads, though the vendored _TABLE["spec"] leads with minimax-m2.5.
    synced = {"spec": ["deepseek/deepseek-v4-flash", "minimax/minimax-m3"]}
    assert pick_models("spec", n=2, ranking=synced) == [
        "deepseek/deepseek-v4-flash",
        "minimax/minimax-m3",
    ]
    assert synced["spec"] != TASK_MODEL_TABLE["spec"][:2]  # the synced order really differs


def test_pick_models_cap_is_always_enforced_and_allow_above_cap_overrides() -> None:
    # pick_models is the SOLE gatekeeper: the ≤$1.5 fleet cap drops a pricier/unpriced synced model
    # even with NO explicit ceiling — a refreshed synced doc can't slip a >$1.5 model into the pool.
    synced = {"spec": ["some/new-model", "z-ai/glm-5"]}  # unpriced (inf) + $1.92, both > $1.5
    assert pick_models("spec", n=2, ranking=synced) == []  # Auto tier drops both
    # the On-request tier keeps them (in synced rank order) — pricier models stay reachable by opt-in.
    assert pick_models("spec", n=2, ranking=synced, allow_above_cap=True) == [
        "some/new-model",
        "z-ai/glm-5",
    ]


def test_pick_models_falls_back_to_table_for_uncovered_task() -> None:
    # synced doc covers only spec; a "code" pick still uses the vendored table
    synced = {"spec": ["some/new-model"]}
    n = len(TASK_MODEL_TABLE["code"])
    assert pick_models("code", n=n, ranking=synced) == TASK_MODEL_TABLE["code"]


def test_synced_unpriced_model_dropped_under_cost_ceiling() -> None:
    # FAIL-CLOSED: an unpriced synced model is DROPPED by a ceiling (a hard budget guard must
    # not be bypassed by an unknown price); a priced-but-expensive one is dropped too.
    synced = {"spec": ["some/new-model", "z-ai/glm-5", "deepseek/deepseek-v3.2"]}
    picks = pick_models("spec", n=3, ranking=synced, max_cost_per_mtok=0.5)
    assert picks == [
        "deepseek/deepseek-v3.2"
    ]  # unpriced + glm-5 dropped, cheap priced kept
    # even with NO explicit ceiling the always-on ≤$1.5 fleet cap drops the unpriced model:
    assert pick_models("spec", n=1, ranking=synced) == ["deepseek/deepseek-v3.2"]
    # only the On-request tier (allow_above_cap) keeps it, in synced rank order (fail-soft):
    assert pick_models("spec", n=1, ranking=synced, allow_above_cap=True) == [
        "some/new-model"
    ]


def test_reader_rejects_bogus_typo_and_normalizes_case(tmp_path) -> None:
    doc = (
        "### bogus\n| 1 | evil/model | 5 |\n\n"
        "### code-review\n| 1 | evil/model | 5 |\n\n"
        "### Spec\n| 1 | z-ai/glm-5 | 9 |\n"  # case-insensitive → the real 'spec'
    )
    p = tmp_path / "d.md"
    p.write_text(doc)
    # only-valid-TaskKind sections survive; a bogus name or a `code-review` typo is dropped
    assert load_task_ranking(str(p)) == {"spec": ["z-ai/glm-5"]}


def test_reader_garbled_header_resets_section(tmp_path) -> None:
    # a `###` line the regex rejects (no space after ###) must END the section, not leak its
    # rows into the previous valid kind (round-2 finding).
    doc = "### spec\n| 1 | z-ai/glm-5 | 9 |\n###code\n| 1 | evil/model | 9 |\n"
    p = tmp_path / "d.md"
    p.write_text(doc)
    assert load_task_ranking(str(p)) == {
        "spec": ["z-ai/glm-5"]
    }  # evil/model must NOT be in spec


def test_reader_indented_header_is_recognized(tmp_path) -> None:
    doc = "  ### spec\n| 1 | z-ai/glm-5 | 9 |\n"
    p = tmp_path / "d.md"
    p.write_text(doc)
    assert load_task_ranking(str(p)) == {"spec": ["z-ai/glm-5"]}


def test_reader_stale_doc_is_dropped(tmp_path) -> None:
    # a doc older than max_age_days is untrusted → {} (a stopped aggregator must not pin a
    # stale ranking forever); with no age gate it still parses (fabrik-AI parse contract).
    doc = "Last refresh: 2020-01-01\n\n### spec\n| 1 | `z-ai/glm-5` | 9 |\n"
    p = tmp_path / "d.md"
    p.write_text(doc)
    assert load_task_ranking(str(p), max_age_days=14) == {}
    assert load_task_ranking(str(p)) == {"spec": ["z-ai/glm-5"]}


def test_reader_fresh_doc_passes_age_gate(tmp_path) -> None:
    doc = f"Last refresh: {date.today().isoformat()}\n\n### spec\n| 1 | `z-ai/glm-5` | 9 |\n"
    p = tmp_path / "d.md"
    p.write_text(doc)
    assert load_task_ranking(str(p), max_age_days=14) == {"spec": ["z-ai/glm-5"]}


def test_prefer_value_ranks_unpriced_model_last() -> None:
    # prefer="value" on the On-request tier (allow_above_cap, so the always-on ≤$1.5 cap doesn't
    # pre-filter and the value ORDERING itself is what's under test): an unpriced model (unknown
    # cost) is ranked LAST — consistent with the fail-closed ceiling (never prefer unknown cost).
    synced = {"spec": ["some/new-unpriced", "z-ai/glm-5", "deepseek/deepseek-v3.2"]}
    v = pick_models("spec", n=3, ranking=synced, prefer="value", allow_above_cap=True)
    assert v[-1] == "some/new-unpriced"


def test_reader_skips_code_fenced_rows(tmp_path) -> None:
    doc = "### spec\n```\n| 1 | fake/model | 9 |\n```\n| 1 | z-ai/glm-5 | 9 |\n"
    p = tmp_path / "d.md"
    p.write_text(doc)
    assert load_task_ranking(str(p)) == {"spec": ["z-ai/glm-5"]}


def test_reader_rejects_non_model_shaped_cell(tmp_path) -> None:
    # a column-order drift (a number where the model should be) must NOT inject garbage
    doc = (
        "### spec\n| rank | value | model |\n|---|---|---|\n| 1 | 4.82 | z-ai/glm-5 |\n"
    )
    p = tmp_path / "d.md"
    p.write_text(doc)
    assert load_task_ranking(str(p)) == {}  # cells[1]='4.82' has no '/' → rejected


def test_reader_unicode_digit_does_not_raise(tmp_path) -> None:
    doc = "### spec\n| ² | z-ai/glm-5 | ² |\n| 1 | minimax/minimax-m2.5 | 40 |\n"
    p = tmp_path / "d.md"
    p.write_text(doc)
    # the '²' rank row is skipped (isdecimal False); the real row parses; NO ValueError raised
    assert load_task_ranking(str(p)) == {"spec": ["minimax/minimax-m2.5"]}


def test_reader_dedups_repeated_models(tmp_path) -> None:
    doc = (
        "### spec\n| 1 | z-ai/glm-5 | 9 |\n| 2 | z-ai/glm-5 | 9 |\n"
        "| 3 | minimax/minimax-m2.5 | 8 |\n"
    )
    p = tmp_path / "d.md"
    p.write_text(doc)
    # a dup would make pick_models return the same worker twice for an n-distinct A/B
    assert load_task_ranking(str(p)) == {"spec": ["z-ai/glm-5", "minimax/minimax-m2.5"]}


def test_ledger_records_task_type() -> None:
    # the flywheel input: a run's task_type must land in the provenance record
    class _Spec:
        task = "write the api-quota spec"
        model = "z-ai/glm-5"
        owned_paths: list[str] = []
        task_type = "spec"

    class _Result:
        agent_id = "agent-000-abc"
        status = "done"
        provider = "DeepInfra"
        cost_usd = 0.009
        turns = 1
        diff = ""
        error = None
        tool_calls: dict[str, int] = {}

    rec = agent_record(_Spec(), _Result())
    assert rec["task_type"] == "spec"
    assert rec["model"] == "z-ai/glm-5"


# ---------------------------------------------- pricing: static table + live fallback
def test_registered_models_priced() -> None:
    """The models registered on 2026-07-08 return their real OUTPUT $/Mtok (glm-5.2 corrected)."""
    from subagents.select import model_price

    assert model_price("z-ai/glm-5.2") == 3.00
    assert model_price("z-ai/glm-5.1") == 3.04
    assert model_price("qwen/qwen3.7-max") == 3.75
    assert model_price("x-ai/grok-4.20") == 2.50
    assert model_price("x-ai/grok-4.20-multi-agent") == 2.50


def test_unknown_model_none_without_live() -> None:
    from subagents.select import model_price

    assert model_price("acme/never-shipped-9000") is None


def test_live_fallback_prices_unknown_model(monkeypatch) -> None:
    """A table MISS with live=True fetches OpenRouter prices (mocked) — so ANY model prices."""
    import subagents.select as sel

    monkeypatch.setattr(sel, "_fetch_openrouter_prices", lambda: {"acme/rocket-9": 7.5})
    monkeypatch.setattr(sel, "_LIVE_FETCHED", False)
    monkeypatch.setattr(sel, "_LIVE_PRICE", {})
    assert sel.model_price("acme/rocket-9", live=True) == 7.5
    # still None if unknown even live (fail-closed)
    assert sel.model_price("acme/does-not-exist", live=True) is None


def test_live_fallback_via_env(monkeypatch) -> None:
    import subagents.select as sel

    monkeypatch.setattr(sel, "_fetch_openrouter_prices", lambda: {"acme/rocket-9": 7.5})
    monkeypatch.setattr(sel, "_LIVE_FETCHED", False)
    monkeypatch.setattr(sel, "_LIVE_PRICE", {})
    monkeypatch.setenv("SUBAGENT_LIVE_PRICING", "1")
    assert sel.model_price("acme/rocket-9") == 7.5  # env enables live without the kwarg


def test_fetch_openrouter_prices_total_on_failure(monkeypatch) -> None:
    """A network/parse failure must return {} — pricing never crashes selection."""
    import httpx

    import subagents.select as sel

    def _boom(*a, **k):  # noqa: ANN002, ANN003, ANN202
        raise httpx.HTTPError("no network")

    monkeypatch.setattr(httpx, "get", _boom)
    assert sel._fetch_openrouter_prices() == {}


def test_pick_models_live_admits_beyond_pool_model(monkeypatch) -> None:
    """A ranked model unknown to the static table is dropped by a ceiling — UNLESS live pricing
    can price it AND it's the On-request tier (allow_above_cap, since $7.5 > the $1.5 fleet cap).
    Proves a vendored agent can cost-bound a freshly-added, deliberately-pricier model."""
    import subagents.select as sel

    ranking = {"review": ["acme/rocket-9"]}  # not in _OUT_PRICE
    # without live → unpriced → fail-closed out by the ceiling (even on the On-request tier)
    assert (
        sel.pick_models(
            "review", n=1, max_cost_per_mtok=10.0, ranking=ranking, allow_above_cap=True
        )
        == []
    )
    # with live (mocked at $7.5 ≤ 10.0) AND allow_above_cap (past the $1.5 fleet cap) → admitted
    monkeypatch.setattr(sel, "_fetch_openrouter_prices", lambda: {"acme/rocket-9": 7.5})
    monkeypatch.setattr(sel, "_LIVE_FETCHED", False)
    monkeypatch.setattr(sel, "_LIVE_PRICE", {})
    assert sel.pick_models(
        "review",
        n=1,
        max_cost_per_mtok=10.0,
        ranking=ranking,
        live=True,
        allow_above_cap=True,
    ) == ["acme/rocket-9"]
    # but on the DEFAULT (Auto) tier the same $7.5 model is dropped by the always-on ≤$1.5 cap:
    monkeypatch.setattr(sel, "_LIVE_FETCHED", False)
    monkeypatch.setattr(sel, "_LIVE_PRICE", {})
    assert (
        sel.pick_models(
            "review", n=1, max_cost_per_mtok=10.0, ranking=ranking, live=True
        )
        == []
    )


def test_fetch_parses_converts_and_survives_bad_items(monkeypatch) -> None:
    """The REAL _fetch_openrouter_prices: per-token→per-Mtok conversion AND per-item
    resilience — one non-dict / bad-pricing row does not lose the good rows."""
    import httpx

    import subagents.select as sel

    class _Resp:
        def raise_for_status(self):  # noqa: ANN202
            return None

        def json(self):  # noqa: ANN202
            return {
                "data": [
                    {"id": "a/good", "pricing": {"completion": "0.000003"}},   # → 3.0/Mtok
                    "not-a-dict",                                              # bad row → skip
                    {"id": "b/nopricing"},                                     # no pricing → skip
                    {"id": "c/weird", "pricing": "free"},                      # pricing non-dict → skip
                    {"id": "d/badnum", "pricing": {"completion": "abc"}},      # bad float → skip
                    {"pricing": {"completion": "0.000001"}},                   # no id → skip
                    {"id": "e/ok", "pricing": {"completion": "0.0000025"}},    # → 2.5/Mtok
                ]
            }

    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp())  # noqa: ARG005
    prices = sel._fetch_openrouter_prices()
    assert set(prices) == {"a/good", "e/ok"}  # only the good rows survived
    assert prices["a/good"] == pytest.approx(3.0)
    assert prices["e/ok"] == pytest.approx(2.5)


def test_live_fetch_is_cached_once(monkeypatch) -> None:
    """The live list is fetched ONCE per process, then served from cache (no per-model refetch)."""
    import subagents.select as sel

    calls = {"n": 0}

    def _fake():  # noqa: ANN202
        calls["n"] += 1
        return {"x/one": 1.0}

    monkeypatch.setattr(sel, "_fetch_openrouter_prices", _fake)
    monkeypatch.setattr(sel, "_LIVE_FETCHED", False)
    monkeypatch.setattr(sel, "_LIVE_PRICE", {})
    assert sel.model_price("x/one", live=True) == 1.0
    assert sel.model_price("x/two", live=True) is None  # unknown, but no second fetch
    assert calls["n"] == 1


def test_explicit_live_false_forces_offline(monkeypatch) -> None:
    """An explicit live=False wins over env SUBAGENT_LIVE_PRICING=1 — no network I/O."""
    import subagents.select as sel

    monkeypatch.setenv("SUBAGENT_LIVE_PRICING", "1")
    calls = {"n": 0}

    def _fake():  # noqa: ANN202
        calls["n"] += 1
        return {"x/one": 1.0}

    monkeypatch.setattr(sel, "_fetch_openrouter_prices", _fake)
    monkeypatch.setattr(sel, "_LIVE_FETCHED", False)
    monkeypatch.setattr(sel, "_LIVE_PRICE", {})
    assert sel.model_price("x/one", live=False) is None  # forced offline despite env
    assert calls["n"] == 0  # no fetch happened
