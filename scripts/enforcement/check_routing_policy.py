#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/rank_task_subagents.py | tests/test_operator_routing_deny.py
"""The operator's routing policy is ENFORCED, not merely written down (D-159).

`docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` is what `pick_models` reads to choose the model for
every subagent dispatch, and it is fleet-synced to ~45 repos. Two operator policies live in it — the
deny (`OPERATOR_DENY` / `OPERATOR_DENY_ALWAYS`) and the allowlist (`OPERATOR_ALLOW`, D-159) — and
both are applied by a GENERATOR whose output is a tracked file that other processes also write.

⚠️ WHY THIS IS A GATE CHECK RATHER THAN A TEST. The equivalent assertions already exist in
`tests/test_operator_routing_deny.py` and they are INERT here: the hub deliberately runs no pytest
leg (no `.fabrik/run-pytest`, per CLAUDE.md — 5,913 tests would brick every completion gate), and no
pre-commit hook names that file. So the policy was guarded by tests nothing executed. Measured the
day this check was written: the hub's own `daily_refresh.sh` regenerated the doc and then, 110 lines
later in the SAME script, `deliver_to_fabrik --target-root /opt/fabrik` copied a fork's older copy
over it — for roughly 8 days, auto-committed each morning, unnoticed. A date-based freshness guard
could not see it (both stamps read the same day); only reading the CONTENT can.

Fail direction: ADVISORY on landing, per the standing rollout law (advisory first, fire rate
measured, promoted on evidence). It fires only when a routing section names a model policy forbids,
or when a task kind has no section at all — neither is a legitimate pattern, so the expected fire
rate is zero and a single fire is a real regression.
"""

from __future__ import annotations

import sys
from pathlib import Path

_RANKER_REL = Path("scripts/kilo-benchmarks/rank_task_subagents.py")


def _hub_root() -> Path | None:
    """The hub checkout this script BELONGS TO, or None in a synced project copy.

    Resolved from `__file__`, never the cwd, so a hub `git worktree` (which carries the full tree)
    still resolves to itself; gated on the ranker's presence so a project copy — which never
    receives `scripts/kilo-benchmarks/` — skips rather than dying on an import it cannot satisfy.

    ⚠️ NO `/opt/fabrik` FALLBACK, deliberately. An earlier draft tried the relative root and THEN a
    hardcoded hub path, to survive an exotic case (a symlinked `scripts/` dir). Measured, that
    fallback did real harm for a hypothetical gain: this file ships to ~45 project repos, and in a
    project copy on this box `/opt/youtube/scripts/enforcement/…` resolves relatively to
    `/opt/youtube` (no ranker → correct skip) but the fallback then found `/opt/fabrik`'s ranker and
    made a PROJECT's gate report on HUB state. Belonging is the question, not availability.
    """
    base = Path(__file__).resolve().parent.parent.parent
    if (base / _RANKER_REL).is_file():
        return base
    # Second candidate: the REPO this run belongs to. Not a hardcoded `/opt/fabrik` — that version
    # made a project copy report on hub state (its own defect, found in the closing pass) — and not
    # a third relative guess. `--show-toplevel` answers the question that actually matters, "which
    # checkout am I running in", and it survives the layout `parent.parent.parent` cannot: a
    # symlinked script whose `resolve()` lands outside the tree, which would otherwise SILENTLY skip
    # and report nothing wrong while the policy went unguarded.
    try:
        import subprocess

        root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout.strip()
    except Exception:
        return None
    if root and (Path(root) / _RANKER_REL).is_file():
        return Path(root)
    return None


def main() -> int:
    hub = _hub_root()
    if hub is None:
        print("check_routing_policy: SKIP — not the hub (no ranker present); policy is hub-owned")
        return 0

    sys.path.insert(0, str(hub / "scripts" / "kilo-benchmarks"))
    sys.path.insert(0, str(hub))
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("_rank_policy", hub / _RANKER_REL)
        if spec is None or spec.loader is None:
            print("check_routing_policy: SKIP — ranker present but not importable")
            return 0
        rank = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rank)
        from libs.subagents import TASK_KINDS, select
    except Exception as exc:  # pragma: no cover - environment shape, not logic
        print(
            f"check_routing_policy: SKIP — policy modules unavailable ({type(exc).__name__}: {exc})"
        )
        return 0

    # ⚠️ INSIDE the guard, deliberately. `_synced_ranking` is a PRIVATE function of a VENDORED
    # module: a re-vendor may rename it (AttributeError) and it can raise on a missing or malformed
    # doc. Outside a guard, either would exit non-zero — and `final_gate.run_optional_check`'s
    # `warn_only` contract reads a non-zero exit as a BROKEN CHECK that fails the gate outright, so
    # an advisory check would silently become blocking across ~45 repos. Reported by a closing-pass
    # finder (agent-000-9df517).
    try:
        ranking = select._synced_ranking()
    except Exception as exc:
        print(
            f"⚠ check_routing_policy ADVISORY — could not read the routing doc "
            f"({type(exc).__name__}: {exc}); the operator's deny/allowlist is UNVERIFIED this run"
        )
        return 0
    problems: list[str] = []

    if not ranking:
        problems.append(
            "the live selection doc parsed to NOTHING — every task kind falls back to the "
            "UNRESTRICTED vendored _TABLE, so neither the deny nor the allowlist is in force"
        )

    for kind in sorted(TASK_KINDS):
        models = ranking.get(kind)
        if not models:
            problems.append(
                f"{kind}: no routing section (or an empty one) — pick_models falls back to the "
                f"unrestricted vendored _TABLE for this kind"
            )
            continue
        for model in models:
            if not rank._allowed(model):
                problems.append(
                    f"{kind}: `{model}` is routable but the operator allowlist forbids it"
                )
            if model in rank.OPERATOR_DENY.get(kind, ()) or model in rank.OPERATOR_DENY_ALWAYS:
                problems.append(f"{kind}: `{model}` is routable but is DENIED")

    if problems:
        print("⚠ check_routing_policy ADVISORY — the live routing doc disagrees with hub policy:")
        for row in problems:
            print(f"  ⚠ {row}")
        print(
            "  FIX: re-run `python3 scripts/kilo-benchmarks/rank_task_subagents.py` and commit the "
            "result. If it comes back wrong, something ELSE is writing this doc — check "
            "`deliver_to_fabrik` ordering in scripts/kilo-benchmarks/daily_refresh.sh."
        )
        # ⚠️ EXIT 0 DELIBERATELY. `final_gate.run_optional_check(warn_only=True)` contracts that a
        # warn_only check "has no failing exit path" and treats a non-zero exit as a BROKEN CONTRACT
        # that fails the gate outright — so returning 1 here would promote this to blocking by
        # accident, on its first day, against the standing rollout law (advisory first, fire rate
        # measured, promoted on evidence). The stdout above IS the product. Promote by flipping the
        # registration in final_gate.py to a blocking check, not by changing this line.
        return 0

    total = sum(len(v) for v in ranking.values())
    print(
        f"check_routing_policy: OK — {len(ranking)} of {len(TASK_KINDS)} task kinds have a routing "
        f"section, {total} routable model entries, all allowed and none denied"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
