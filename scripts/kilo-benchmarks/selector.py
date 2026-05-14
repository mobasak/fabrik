#!/usr/bin/env python3
"""
Role selector — "cheapest above floors" mode.

For each role:
1. Apply quality floor (role's primary_metric).
2. Apply speed floor (output_tokens_per_sec).
3. Optional cost cap.
4. Sort survivors by total_cost ascending.
5. P1 = cheapest qualified agent; P2..PN = next-cheapest fallbacks.

User intent: "pay as low as possible without losing quality and speed."
Quality and speed are CONSTRAINTS; cost is the objective.

Models with NULL on the primary metric OR NULL on output_tokens_per_sec are
excluded from selection (you can't verify they meet the floor). To re-include
unmatched models, add manual entries to cache/speed_overrides.json and re-run
scrape_artificial_analysis.py.
"""

from pathlib import Path
from typing import Any

import yaml


def load_role_configs(path: Path | str | None = None) -> dict[str, Any]:
    if path is None:
        path = Path(__file__).parent / "role_configs.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def passes_floors(
    model: dict[str, Any],
    primary_metric: str,
    quality_floor: float,
    speed_floor: float,
    secondary_floors: dict[str, float] | None = None,
) -> tuple[bool, str]:
    """Return (passes, reason_if_fail)."""
    quality = model.get(primary_metric)
    if quality is None:
        return False, f"missing {primary_metric}"
    if quality < quality_floor:
        return False, f"{primary_metric}={quality} < floor {quality_floor}"

    speed = model.get("output_tokens_per_sec")
    if speed is None:
        return False, "missing output_tokens_per_sec"
    if speed < speed_floor:
        return False, f"speed={speed} < floor {speed_floor}"

    # Secondary floors — used to catch agentic-fitness gaps that the primary
    # metric can mask. NULL on a secondary metric counts as failure: we'd
    # rather drop a model than ship one we can't verify.
    if secondary_floors:
        for metric, floor in secondary_floors.items():
            value = model.get(metric)
            if value is None:
                return False, f"missing {metric} (secondary floor)"
            if value < floor:
                return False, f"{metric}={value} < secondary floor {floor}"

    return True, ""


def select_for_role(
    role: str,
    shortlist: list[dict[str, Any]],
    primary_metric: str,
    quality_floor: float,
    speed_floor: float,
    cost_cap: float | None,
    fleet_size: int,
    secondary_floors: dict[str, float] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Returns (selected, rejected) — rejected carries the reason it failed
    so the dry-run output can explain absences.
    """
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for m in shortlist:
        total_cost = (m.get("input_cost_per_m") or 0) + (m.get("output_cost_per_m") or 0)
        m["total_cost"] = total_cost

        if cost_cap is not None and total_cost > cost_cap:
            rejected.append(
                {"id": m["id"], "reason": f"total_cost ${total_cost:.2f} > cap ${cost_cap}"}
            )
            continue

        ok, why = passes_floors(m, primary_metric, quality_floor, speed_floor, secondary_floors)
        if not ok:
            rejected.append({"id": m["id"], "reason": why})
            continue

        selected.append(m)

    # Sort survivors by cost ASC — P1 is the cheapest qualified agent.
    # Tiebreak by quality DESC so equal-cost slots prefer higher quality.
    selected.sort(key=lambda m: (m["total_cost"], -m[primary_metric]))
    return selected[:fleet_size], rejected


def select_all_roles(
    shortlists: dict[str, list[dict[str, Any]]],
    role_configs_path: Path | str | None = None,
) -> dict[str, Any]:
    configs = load_role_configs(role_configs_path)
    roles_cfg = configs["roles"]

    assignments: list[dict[str, Any]] = []
    role_floors: dict[str, int] = {}
    skipped_slots: list[dict[str, Any]] = []
    rejections: dict[str, list[dict]] = {}

    for role, shortlist in shortlists.items():
        if not shortlist:
            continue

        cfg = roles_cfg.get(role, {})
        primary_metric = cfg.get("primary_metric", "arena_elo")
        quality_floor = float(cfg.get("quality_floor", 0))
        speed_floor = float(cfg.get("speed_floor", 0))
        cost_cap = cfg.get("cost_cap")
        fleet_size = int(cfg.get("fleet_size", 5))
        secondary_floors = cfg.get("secondary_floors") or {}

        selected, rejected = select_for_role(
            role,
            shortlist,
            primary_metric,
            quality_floor,
            speed_floor,
            cost_cap,
            fleet_size,
            secondary_floors,
        )
        rejections[role] = rejected

        # Debug: print qualified fleet up-front so anomalies are visible
        sec_summary = ", ".join(f"{k}≥{v}" for k, v in secondary_floors.items())
        floor_line = f"{primary_metric}≥{quality_floor}, speed≥{speed_floor}tps"
        if sec_summary:
            floor_line += f", {sec_summary}"
        fleet_summary = ", ".join(
            f"{m['id']}({m[primary_metric]:.2f}/{int(m['output_tokens_per_sec'])}tps@${m['total_cost']:.2f})"
            for m in selected
        )
        print(f"[selector] {role} qualified ({floor_line}): {fleet_summary or '<empty>'}")

        for priority, model in enumerate(selected, start=1):
            assignments.append(
                {
                    "role": role,
                    "agent_id": model["id"],
                    "priority": priority,
                    "provider": model.get("provider", "unknown"),
                    "score_used": model[primary_metric],
                    "score_type": primary_metric,
                    # Embed total_cost so post_filter can re-sort after swaps
                    # without needing to look up the shortlist. Also useful
                    # downstream (exporter, doc table, runtime budget gates).
                    "total_cost": model["total_cost"],
                    "reason": (
                        f"{primary_metric}={model[primary_metric]:.2f}, "
                        f"speed={int(model['output_tokens_per_sec'])}tps, "
                        f"cost=${model['total_cost']:.2f}/M"
                    ),
                }
            )

        elos = [m.get("arena_elo") for m in shortlist if m.get("arena_elo") is not None]
        if elos:
            role_floors[role] = int(min(elos))

        if len(selected) < fleet_size:
            for priority in range(len(selected) + 1, fleet_size + 1):
                top_rejections = rejected[:3]
                detail = (
                    "; ".join(f"{r['id']} ({r['reason']})" for r in top_rejections)
                    or "no rejections recorded"
                )
                skipped_slots.append(
                    {
                        "role": role,
                        "priority": priority,
                        "reason": (
                            f"Only {len(selected)} of {len(shortlist)} shortlist candidates met "
                            f"quality_floor={quality_floor} AND speed_floor={speed_floor}tps. "
                            f"Top rejections: {detail}"
                        ),
                    }
                )

    return {
        "role_floors": role_floors,
        "assignments": assignments,
        "skipped_slots": skipped_slots,
        "rejections": rejections,
    }


if __name__ == "__main__":
    # Smoke test with mock data
    mock = {
        "coding": [
            {
                "id": "google/gemini-3.1-pro-preview",
                "provider": "google",
                "weighted_coding": 93.9,
                "arena_elo": 1531,
                "input_cost_per_m": 2.0,
                "output_cost_per_m": 12.0,
                "output_tokens_per_sec": 133.0,
                "ttft_ms": 36800.0,
            },
            {
                "id": "moonshotai/kimi-k2.5",
                "provider": "moonshotai",
                "weighted_coding": 82.6,
                "arena_elo": None,
                "input_cost_per_m": 0.40,
                "output_cost_per_m": 1.90,
                "output_tokens_per_sec": 66.0,
                "ttft_ms": 3010.0,
            },
            {
                "id": "qwen/qwen3.6-plus",
                "provider": "qwen",
                "weighted_coding": 77.9,
                "arena_elo": 1482,
                "input_cost_per_m": 0.325,
                "output_cost_per_m": 1.95,
                "output_tokens_per_sec": 53.0,
                "ttft_ms": 2780.0,
            },
            {
                "id": "openai/gpt-5.4",
                "provider": "openai",
                "weighted_coding": 89.3,
                "arena_elo": 1468,
                "input_cost_per_m": 2.5,
                "output_cost_per_m": 15.0,
                "output_tokens_per_sec": 74.0,
                "ttft_ms": 1830.0,
            },
        ],
    }
    out = select_all_roles(mock)
    print("\nAssignments:")
    for a in out["assignments"]:
        print(f"  {a['role']}#{a['priority']}: {a['agent_id']}  ({a['reason']})")
    print("\nSkipped:")
    for s in out["skipped_slots"]:
        print(f"  {s['role']}#{s['priority']}: {s['reason']}")
