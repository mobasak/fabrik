#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/daily_refresh.sh (the file this asserts the shape of)
"""Assert the cost-sidecar rebuild runs BEFORE the ranking regen in `daily_refresh.sh`.

Wired the other way round, `rank_task_subagents.py` renders yesterday's ② rate into
`TASK_SUBAGENT_SELECTION.md` for a full cycle — the doc `pick_models` reads would carry a figure the
same run is about to replace. Phase C of `docs/development/plans/2026-09-05-plan-1-windowed-cost-sidecar.md`.

⚠️ This body is specified VERBATIM in that plan, and the shape matters more than it looks. An earlier
revision used a compound shell gate that was broken three ways at once, each failure silent:

  * it anchored on `grep -n rank_task_subagents | head -1`, which resolves to a stale COMMENT rather
    than the `_step` invocation — the ordering it checked was between a comment and a step;
  * its regex demanded a literal space after `.py`, so the file's own quoted-path convention
    (`"$KB/rank_task_subagents.py"`) never matched and CORRECT wiring redded the gate;
  * with the anchor absent, `xargs` ran nothing and exited 0 — VACUOUSLY GREEN on a deleted step,
    which is the one state a gate like this exists to catch.

Hence: match only lines whose first non-space token is `_step`, require BOTH to be present, and
compare their positions. Proven on five cases before being written into the plan (and re-proven
against the live file at execution): red with no refresh step · green on correct quoted-path wiring ·
red when wired after the ranker · red when the ranker step is deleted · red when the token appears
only in a comment.

Exit 0 = correctly ordered. Exit 1 = missing or out of order. Exit 2 = the shell script is absent.
"""

import pathlib
import sys

_TARGET = pathlib.Path("scripts/kilo-benchmarks/daily_refresh.sh")


def main() -> int:
    if not _TARGET.exists():
        print(f"{_TARGET}: not found — run from the repo root", file=sys.stderr)
        return 2
    lines = _TARGET.read_text(encoding="utf-8").splitlines()

    def step(tok: str) -> int | None:
        """Line number of the first real `_step` invocation naming `tok`; never a comment."""
        return next(
            (
                i
                for i, line in enumerate(lines, 1)
                if line.lstrip().startswith("_step") and tok in line
            ),
            None,
        )

    refresh, ranker = step("claude_p_cost"), step("rank_task_subagents")
    if refresh is None:
        print(
            "daily_refresh.sh has no `_step` invoking claude_p_cost --refresh: the cost sidecar is "
            "never rebuilt, so ② fossilises and the selection doc renders a stale rate as current",
            file=sys.stderr,
        )
        return 1
    if ranker is None:
        print(
            "daily_refresh.sh has no `_step` invoking rank_task_subagents: the ranking is never "
            "regenerated, so `pick_models` reads whatever the doc last happened to contain",
            file=sys.stderr,
        )
        return 1
    if refresh >= ranker:
        print(
            f"ordering: claude_p_cost refresh is at line {refresh}, rank_task_subagents at {ranker} — "
            "the rebuild must come FIRST or the ranking renders the previous day's rate for a cycle",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
