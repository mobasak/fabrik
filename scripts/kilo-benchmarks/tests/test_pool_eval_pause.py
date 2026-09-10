# AFTER-EDIT: ../daily_refresh.sh | ../../enforcement/check_subagent_flywheel.py
"""The daily chain's POOL-EVALUATION PAUSE (operator, 2026-09-08).

"do not delete them but stop/pause them, if we want to reuse them, we can enable them" — so the
three OpenRouter evaluation/flywheel steps are gated, not removed, on the SAME committed constant
the enforcement gate and doc_reconcile read (`_pool_policy_on()`), giving one switch and no new state.

⚠️ THE ATOMICITY IS THE POINT, and it is why this file exists rather than a comment:
`deliver_to_fabrik` OVERWRITES TASK_SUBAGENT_SELECTION.md with the catalog's UNRESTRICTED doc and
`rank_task_subagents` regenerates it with the operator's roster afterwards. Pause the ranker alone
and the unrestricted doc is what stands — silently restoring every model D-159/D-168 removed. A
future edit that gates one and not the other must fail here.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

CHAIN = Path(__file__).resolve().parents[1] / "daily_refresh.sh"
GATED = ("flush_subagent_outboxes", "deliver_to_fabrik", "rank_task_subagents")
UNGATED = ("sync_enforcement_to_projects", "claude_p_cost_refresh", "external_services_chain")


def _text() -> str:
    return CHAIN.read_text(encoding="utf-8")


def test_all_three_pool_steps_are_gated_and_none_is_left_behind():
    """If a later edit gates two of three, the unpaused one either burns credit or lands the
    unrestricted doc. All three or none."""
    t = _text()
    for step in GATED:
        i = t.index(f'_step "{step}"')
        window = t[max(0, i - 1200) : i]
        assert "_pool_eval_paused" in window, f"{step} is NOT behind the pause guard"


def test_the_governance_and_cost_steps_are_not_paused():
    """The pause must not take the fleet's governance sync or the Claude cost refresh with it —
    neither has anything to do with the OpenRouter pool."""
    t = _text()
    for step in UNGATED:
        i = t.index(f'_step "{step}"')
        window = t[max(0, i - 400) : i]
        assert "_pool_eval_paused" not in window, (
            f"{step} must keep running while the pool is paused"
        )


def test_deliver_and_rank_share_one_condition():
    """The atomic pair. Both gate on the same predicate, so one cannot be re-enabled alone."""
    t = _text()
    d, r = t.index('_step "deliver_to_fabrik"'), t.index('_step "rank_task_subagents"')
    assert t[max(0, d - 1200) : d].count("_pool_eval_paused") == 1
    assert t[max(0, r - 1200) : r].count("_pool_eval_paused") == 1


def test_the_guard_reads_the_committed_constant_not_a_second_source():
    """One switch. A marker file or a duplicated flag would be a second thing to remember and a
    second thing to drift — the exact defect the policy constant was created to end."""
    t = _text()
    g = t[t.index("_pool_eval_paused() {") : t.index("_pool_eval_paused() {") + 400]
    assert "check_subagent_flywheel" in g and "_pool_policy_on" in g
    assert not re.search(r"\.fabrik/[a-z-]*pause|POOL_EVAL_PAUSED=", t), "no second source of truth"


def test_the_guard_actually_pauses_and_the_seam_actually_re_enables():
    """Executed, not read: the predicate must return paused today, and FABRIK_POOL_POLICY=on must
    flip it — otherwise 'we can enable them' is a claim nobody tested."""
    t = _text()
    body = t[
        t.index("_pool_eval_paused() {") : t.index("}\n", t.index("_pool_eval_paused() {")) + 1
    ]
    probe = f"FABRIK_ROOT=/opt/fabrik\nVENV_PY=/opt/fabrik/.venv/bin/python\n{body}\n"
    off = subprocess.run(
        ["bash", "-c", probe + "if _pool_eval_paused; then echo PAUSED; else echo ACTIVE; fi"],
        capture_output=True,
        text=True,
    )
    assert off.stdout.strip() == "PAUSED", off.stdout + off.stderr
    on = subprocess.run(
        ["bash", "-c", probe + "if _pool_eval_paused; then echo PAUSED; else echo ACTIVE; fi"],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "FABRIK_POOL_POLICY": "on", "HOME": str(Path.home())},
    )
    assert on.stdout.strip() == "ACTIVE", on.stdout + on.stderr
