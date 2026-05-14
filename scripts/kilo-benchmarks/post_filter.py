#!/usr/bin/env python3
"""
Post-filter for role mapper.

Enforces two constraints on the reviewing fleet in a single unified loop:
- Dominance: no single provider may own >50% of reviewing slots.
- Family diversity: ≥2 distinct providers AND ≥1 provider not in coding P1-P2.

The two checks share a swap mechanism (find lowest-priority offender, replace
with the best alternate from a different provider, preferring providers not
already used in coding P1-P2). Looping until both constraints hold or no
further swap is possible — capped at 5 iterations.
"""

import copy
from typing import Any

# Literal rule from the spec: "max 2 slots per provider in reviewing".
# Using `len(assignments) // 2` would scale this to 1 per provider for a
# 3-slot fleet, which is stricter than the stated rule and forces dominated
# Pareto swaps when the frontier is small. Use the literal cap instead.
MAX_PER_PROVIDER = 2


def _provider_counts(assignments: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for a in assignments:
        counts[a["provider"]] = counts.get(a["provider"], 0) + 1
    return counts


def _check_constraints(
    assignments: list[dict[str, Any]],
    coding_p1_p2_providers: list[str],
) -> tuple[list[str], bool, dict[str, int]]:
    """Return (dominant_providers, diversity_violated, provider_counts)."""
    counts = _provider_counts(assignments)
    dominant = [p for p, c in counts.items() if c > MAX_PER_PROVIDER]

    distinct = set(counts.keys())
    diversity_ok = len(distinct) >= 2 and any(p not in coding_p1_p2_providers for p in distinct)
    return dominant, not diversity_ok, counts


def _pick_target_slot(
    assignments: list[dict[str, Any]],
    dominant: list[str],
    counts: dict[str, int],
) -> dict[str, Any]:
    """
    Choose which assignment to swap out.

    - Dominance violation: lowest priority entry of the most-dominant provider.
    - Diversity-only violation: lowest priority overall.
    """
    if dominant:
        worst_provider = max(dominant, key=lambda p: counts[p])
        offenders = [a for a in assignments if a["provider"] == worst_provider]
        return max(offenders, key=lambda x: x["priority"])
    return max(assignments, key=lambda x: x["priority"])


def _pick_replacement(
    reviewing_shortlist: list[dict[str, Any]],
    current_providers: set[str],
    coding_p1_p2_providers: list[str],
    used_agent_ids: set[str],
) -> dict[str, Any] | None:
    """
    Find the best candidate from a provider NOT currently in reviewing,
    preferring providers also NOT in coding P1-P2.

    `reviewing_shortlist` is assumed to be already sorted by relevance
    (pre_filter ranks by primary metric DESC), so the first matching
    candidate is the strongest.
    """
    shortlist_providers = {m["provider"] for m in reviewing_shortlist}
    alternates = shortlist_providers - current_providers
    strict = alternates - set(coding_p1_p2_providers)
    targets = strict if strict else alternates

    if not targets:
        return None

    for candidate in reviewing_shortlist:
        if candidate["provider"] in targets and candidate["id"] not in used_agent_ids:
            return candidate
    return None


def _apply_swap(
    target: dict[str, Any],
    candidate: dict[str, Any],
    reason_tag: str,
) -> None:
    """
    Mutate `target` in-place to point at `candidate`.

    Score is recorded against arena_elo because this function is only called
    for reviewing-role swaps (primary metric = arena_elo). Recording any other
    metric would break the homogeneity that Bug 3's fix established.

    Also refreshes total_cost — the candidate has different pricing than the
    original target, and downstream re-sort relies on accurate cost values.
    """
    original_reason = target.get("reason", "")
    target["agent_id"] = candidate["id"]
    target["provider"] = candidate["provider"]
    target["arena_elo"] = candidate.get("arena_elo")
    target["score_used"] = candidate.get("arena_elo")
    target["score_type"] = "arena_elo"
    candidate_cost = (candidate.get("input_cost_per_m") or 0) + (
        candidate.get("output_cost_per_m") or 0
    )
    target["total_cost"] = candidate_cost
    target["reason"] = (
        f"Swapped P{target['priority']} → {candidate['provider']} for {reason_tag} "
        f"(original: {original_reason})"
    )


def apply_family_diversity(
    assignments: list[dict[str, Any]],
    reviewing_shortlist: list[dict[str, Any]],
    coding_p1_p2_providers: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Apply dominance + family-diversity constraints to the reviewing fleet.

    Name kept for backwards compatibility with `role_mapper.py`, but the
    function now enforces BOTH constraints in a single unified swap loop.
    """
    warnings: list[str] = []
    assignments = copy.deepcopy(assignments)

    reviewing_assignments = [a for a in assignments if a["role"] == "reviewing"]
    if not reviewing_assignments:
        warnings.append("No reviewing assignments found")
        return assignments, warnings

    used_agent_ids = {a["agent_id"] for a in reviewing_assignments}

    max_iterations = 5
    for iteration in range(1, max_iterations + 1):
        dominant, diversity_violated, counts = _check_constraints(
            reviewing_assignments, coding_p1_p2_providers
        )

        if not dominant and not diversity_violated:
            if iteration == 1:
                warnings.append("Constraints already satisfied")
            else:
                warnings.append(f"Constraints satisfied after {iteration - 1} swap(s)")
            break

        # Pick the offender and a replacement
        target = _pick_target_slot(reviewing_assignments, dominant, counts)
        current_providers = {a["provider"] for a in reviewing_assignments}
        candidate = _pick_replacement(
            reviewing_shortlist, current_providers, coding_p1_p2_providers, used_agent_ids
        )

        if candidate is None:
            unresolved = []
            if dominant:
                unresolved.append(f"dominance ({dominant})")
            if diversity_violated:
                unresolved.append("diversity")
            warnings.append(
                f"No alternate provider available — leaving {', '.join(unresolved)} unresolved"
            )
            break

        reason_tag = "dominance" if dominant else "diversity"
        used_agent_ids.discard(target["agent_id"])
        used_agent_ids.add(candidate["id"])
        warnings.append(
            f"Iter {iteration}: P{target['priority']} → {candidate['id']} "
            f"({candidate['provider']}) [{reason_tag}]"
        )
        _apply_swap(target, candidate, reason_tag)
    else:
        warnings.append(f"Hit max iterations ({max_iterations}) without converging")

    # Final state
    final_dominant, final_diversity_violated, _ = _check_constraints(
        reviewing_assignments, coding_p1_p2_providers
    )
    if final_dominant:
        warnings.append(f"DOMINANCE STILL VIOLATED: {final_dominant}")
    if final_diversity_violated:
        warnings.append("DIVERSITY STILL VIOLATED")
    if not final_dominant and not final_diversity_violated:
        warnings.append("Final: both constraints satisfied")

    # ─── Final monotonicity guard ──────────────────────────────────────────
    # The selector outputs cost-ascending priorities by construction. Any swap
    # in this filter can break that order (e.g., reviewing P4=$30 + P5=$17.50
    # after an Anthropic→OpenAI dominance swap). Re-sort every role by
    # total_cost ASC, tiebreaking by score_used DESC, and reassign priorities.
    #
    # Defensive on purpose: only reviewing has post-filter rules today, but
    # any future rule that swaps in another role gets monotonicity for free.
    # This is the invariant that makes the runtime "P1 = cheapest qualified"
    # semantics actually hold.
    by_role: dict[str, list[dict[str, Any]]] = {}
    for a in assignments:
        by_role.setdefault(a["role"], []).append(a)

    rebuilt: list[dict[str, Any]] = []
    for role, role_assignments in by_role.items():
        role_assignments.sort(
            key=lambda a: (
                a.get("total_cost", float("inf")),
                -(a.get("score_used") or 0),
            )
        )
        renumbered = []
        for new_pri, a in enumerate(role_assignments, start=1):
            if a.get("priority") != new_pri:
                warnings.append(
                    f"Monotonicity re-sort: {role} P{a['priority']} → P{new_pri} "
                    f"({a['agent_id']} @ ${a.get('total_cost', 0):.2f})"
                )
                a["priority"] = new_pri
            renumbered.append(a)
        rebuilt.extend(renumbered)

    return rebuilt, warnings


if __name__ == "__main__":
    # Test fixture 1: Already diverse (no swap should happen)
    print("=== Test 1: Already diverse ===")
    assignments1 = [
        {
            "role": "coding",
            "agent_id": "anthropic/claude-opus-4.6",
            "priority": 1,
            "provider": "anthropic",
        },
        {
            "role": "coding",
            "agent_id": "google/gemini-3.1-pro",
            "priority": 2,
            "provider": "google",
        },
        {
            "role": "reviewing",
            "agent_id": "anthropic/claude-sonnet-4.6",
            "priority": 1,
            "provider": "anthropic",
        },
        {"role": "reviewing", "agent_id": "openai/gpt-5.4", "priority": 2, "provider": "openai"},
    ]
    reviewing_shortlist1 = [
        {"id": "anthropic/claude-sonnet-4.6", "provider": "anthropic", "arena_elo": 1500},
        {"id": "openai/gpt-5.4", "provider": "openai", "arena_elo": 1468},
    ]
    result1, warnings1 = apply_family_diversity(
        assignments1, reviewing_shortlist1, ["anthropic", "google"]
    )
    print("Warnings:", warnings1)

    # Test fixture 2: Reviewing has only 3 slots, all anthropic
    print("\n=== Test 2: 3 anthropic slots, swap to non-coding-P1-P2 ===")
    assignments2 = [
        {
            "role": "coding",
            "agent_id": "anthropic/claude-opus-4.6",
            "priority": 1,
            "provider": "anthropic",
        },
        {
            "role": "coding",
            "agent_id": "google/gemini-3.1-pro",
            "priority": 2,
            "provider": "google",
        },
        {
            "role": "reviewing",
            "agent_id": "anthropic/claude-sonnet-4.6",
            "priority": 1,
            "provider": "anthropic",
        },
        {
            "role": "reviewing",
            "agent_id": "anthropic/claude-sonnet-4.5",
            "priority": 2,
            "provider": "anthropic",
        },
        {
            "role": "reviewing",
            "agent_id": "anthropic/claude-opus-4.5",
            "priority": 3,
            "provider": "anthropic",
        },
    ]
    reviewing_shortlist2 = [
        {"id": "openai/gpt-5.4", "provider": "openai", "arena_elo": 1468},
        {"id": "anthropic/claude-sonnet-4.6", "provider": "anthropic", "arena_elo": 1500},
    ]
    result2, warnings2 = apply_family_diversity(
        assignments2, reviewing_shortlist2, ["anthropic", "google"]
    )
    print("Warnings:", warnings2)
    for a in [x for x in result2 if x["role"] == "reviewing"]:
        print(f"  P{a['priority']}: {a['agent_id']} ({a['provider']})")

    # Test fixture 3: No alternate provider in shortlist
    print("\n=== Test 3: No alternates ===")
    assignments3 = [
        {
            "role": "coding",
            "agent_id": "anthropic/claude-opus-4.6",
            "priority": 1,
            "provider": "anthropic",
        },
        {
            "role": "reviewing",
            "agent_id": "anthropic/claude-sonnet-4.6",
            "priority": 1,
            "provider": "anthropic",
        },
        {
            "role": "reviewing",
            "agent_id": "anthropic/claude-opus-4.6",
            "priority": 2,
            "provider": "anthropic",
        },
        {
            "role": "reviewing",
            "agent_id": "anthropic/claude-haiku-4.5",
            "priority": 3,
            "provider": "anthropic",
        },
    ]
    reviewing_shortlist3 = [
        {"id": "anthropic/claude-sonnet-4.6", "provider": "anthropic", "arena_elo": 1500},
    ]
    result3, warnings3 = apply_family_diversity(assignments3, reviewing_shortlist3, ["anthropic"])
    print("Warnings:", warnings3)
