import json


def none_to_zero(val):
    """Treat None as 0 — correct for a HARD-MIN filter (`>=70`) and for
    non-tbench keys (arena_elo, perf_per_dollar) where 'no value' == 'no boost'."""
    return val if val is not None else 0


def _null_last(val):
    """Sort key for tbench_accuracy under reverse=True: a NULL (unbenched) model
    must rank strictly BELOW a real 0-scorer (measured 0% ≠ unmeasured). Using a
    sentinel below 0 keeps a genuine 0 above None. See plan-1 Phase C."""
    return val if val is not None else -1.0


def filter_ge70(models):
    """Agents eligible for the tbench-gated roles (coding, fixing): tool-using,
    agentic, and a HARD-MIN tbench_accuracy >= 70 (NULL correctly excluded)."""
    return [
        m
        for m in models
        if m.get("has_tools")
        and m.get("is_agentic")
        and none_to_zero(m.get("tbench_accuracy")) >= 70.0
    ]


def rank_testing_pool(models):
    """Return the ordered testing-role ids (top-2 by tbench, then next-3 by
    perf-then-tbench). The pool is NOT tbench-filtered, so NULL models reach the
    sort → use `_null_last` so a real 0 outranks an unbenched NULL."""
    pool = [m for m in models if m.get("has_tools") and m.get("is_agentic")]
    pool = sorted(pool, key=lambda x: _null_last(x.get("tbench_accuracy")), reverse=True)
    top_2 = pool[:2]
    remaining = [m for m in pool if m not in top_2]
    remaining = sorted(
        remaining,
        key=lambda x: (none_to_zero(x.get("perf_per_dollar")) > 500, _null_last(x.get("tbench_accuracy"))),
        reverse=True,
    )
    next_3 = remaining[:3]
    return [m["id"] for m in (top_2 + next_3)]


def process_assignments(file_path):
    with open(file_path) as f:
        models = json.load(f)

    # Filter out inactive models, though the data might only have active
    models = [m for m in models if m.get("status") == "active"]

    roles = {"coding": [], "reviewing": [], "fixing": [], "documentation": [], "testing": []}

    # Role 1: coding
    # - Required: has_tools=1, is_agentic=1
    # - Hard min: tbench_accuracy >= 70.0. ONLY agents meeting this.
    # - Primary sort: tbench_accuracy (desc, NULL last), then arena_elo (desc)
    coding_candidates = filter_ge70(models)
    coding_candidates.sort(
        key=lambda x: (_null_last(x.get("tbench_accuracy")), none_to_zero(x.get("arena_elo"))),
        reverse=True,
    )
    roles["coding"] = [m["id"] for m in coding_candidates]

    # Role 2: reviewing
    # - Required: has_reasoning=1
    # - Sort: arena_elo (desc), then has_vision (desc), is_agentic (desc)
    reviewing_candidates = [m for m in models if m.get("has_reasoning")]
    reviewing_candidates.sort(
        key=lambda x: (
            none_to_zero(x.get("arena_elo")),
            none_to_zero(x.get("has_vision")),
            none_to_zero(x.get("is_agentic")),
        ),
        reverse=True,
    )
    roles["reviewing"] = [m["id"] for m in reviewing_candidates]

    # Role 3: fixing
    # - Required: has_tools=1, is_agentic=1
    # - Hard min: tbench_accuracy >= 70.0
    # - Sort: (tbench_accuracy or -1) + (arena_elo or 0) (desc) — NULL last
    fixing_candidates = filter_ge70(models)
    fixing_candidates.sort(
        key=lambda x: (_null_last(x.get("tbench_accuracy")) + none_to_zero(x.get("arena_elo"))),
        reverse=True,
    )
    roles["fixing"] = [m["id"] for m in fixing_candidates]

    # Role 4: documentation
    # - Required: arena_elo >= 1350
    # - Sort: perf_per_dollar (desc, treat null as 0), context_window_k (desc)
    doc_candidates = [m for m in models if none_to_zero(m.get("arena_elo")) >= 1350]
    doc_candidates.sort(
        key=lambda x: (
            none_to_zero(x.get("perf_per_dollar")),
            none_to_zero(x.get("context_window_k")),
        ),
        reverse=True,
    )
    roles["documentation"] = [m["id"] for m in doc_candidates]

    # Role 5: testing
    # - Required: has_tools=1, is_agentic=1 (pool NOT tbench-filtered → NULL last)
    # - Sort priority 1-2: tbench_accuracy (desc); 3-5: perf_per_dollar>500, then tbench
    roles["testing"] = rank_testing_pool(models)

    print(json.dumps(roles, indent=2))


if __name__ == "__main__":
    process_assignments("models_dump.json")
