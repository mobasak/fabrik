import json


def process_assignments(file_path):
    with open(file_path) as f:
        models = json.load(f)

    # Filter out inactive models, though the data might only have active
    models = [m for m in models if m.get("status") == "active"]

    roles = {"coding": [], "reviewing": [], "fixing": [], "documentation": [], "testing": []}

    # Helper function to treat None as 0 for sorting
    def none_to_zero(val):
        return val if val is not None else 0

    # Role 1: coding
    # - Required: has_tools=1, is_agentic=1
    # - Hard min: tbench_accuracy >= 70.0. ONLY agents meeting this.
    # - Primary sort: tbench_accuracy (desc), then arena_elo (desc)
    coding_candidates = [
        m
        for m in models
        if m.get("has_tools")
        and m.get("is_agentic")
        and none_to_zero(m.get("tbench_accuracy")) >= 70.0
    ]
    coding_candidates.sort(
        key=lambda x: (none_to_zero(x.get("tbench_accuracy")), none_to_zero(x.get("arena_elo"))),
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
    # - Sort: (tbench_accuracy or 0) + (arena_elo or 0) (desc)
    fixing_candidates = [
        m
        for m in models
        if m.get("has_tools")
        and m.get("is_agentic")
        and none_to_zero(m.get("tbench_accuracy")) >= 70.0
    ]
    fixing_candidates.sort(
        key=lambda x: (none_to_zero(x.get("tbench_accuracy")) + none_to_zero(x.get("arena_elo"))),
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
    # - Required: has_tools=1, is_agentic=1
    # - Sort priority 1-2: tbench_accuracy (desc)
    # - Sort priority 3-5: perf_per_dollar > 500, then tbench_accuracy (desc)
    test_candidates = [m for m in models if m.get("has_tools") and m.get("is_agentic")]

    # We need to pick top 5. Let's get all of them and then apply the logic to the first 5.
    # First, sort by tbench_accuracy (desc) to get the top 2
    test_candidates_pool = list(test_candidates)
    test_candidates_pool.sort(key=lambda x: none_to_zero(x.get("tbench_accuracy")), reverse=True)

    top_2 = test_candidates_pool[:2]

    # For remaining, remove top_2 from pool
    remaining_pool = [m for m in test_candidates_pool if m not in top_2]

    # Sort remaining by (perf_per_dollar > 500) DESC, then tbench_accuracy (desc)
    remaining_pool.sort(
        key=lambda x: (
            none_to_zero(x.get("perf_per_dollar")) > 500,
            none_to_zero(x.get("tbench_accuracy")),
        ),
        reverse=True,
    )

    next_3 = remaining_pool[:3]

    roles["testing"] = [m["id"] for m in (top_2 + next_3)]

    # Wait, the user might want just the top N per role, but they didn't specify a limit except for testing (1-5).
    # Let's truncate everything to top 5, as usually roles have priorities 1..5. Wait, or maybe just output the full list?
    # I will output the lists. Let me just output what they asked.

    print(json.dumps(roles, indent=2))


if __name__ == "__main__":
    process_assignments("models_dump.json")
