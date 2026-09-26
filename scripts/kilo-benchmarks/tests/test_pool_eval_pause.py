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


_INVOKE = re.compile(r'check_ai_pack_freshness\.py"?\s+--delivered-max-age')
_GATE = re.compile(r"^(\s*)if\s+!?\s*_pool_eval_paused\s*;\s*then\b")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _freshness_gate() -> tuple[list[str], int, int, int]:
    """(chain lines, leading-comment line, gate `if` line, closing `fi` line) of the delivered-freshness
    step. The `fi` is the first later line at the gate's indentation or shallower that opens with `fi`,
    so a trailing comment, a `;` or a blank line inside the block moves nothing."""
    lines = _text().splitlines()
    start = next(
        i for i, ln in enumerate(lines) if "# The engine-delivered `last-refreshed:`" in ln
    )
    gate = next(i for i in range(start, len(lines)) if _GATE.match(lines[i]))
    depth = _indent(lines[gate])
    fi = next(
        i
        for i in range(gate + 1, len(lines))
        if lines[i].strip().startswith("fi") and _indent(lines[i]) <= depth
    )
    return lines, start, gate, fi


def _freshness_block() -> str:
    """The delivered-freshness step as the chain holds it: from its leading comment to the `fi` that
    closes its pause gate."""
    lines, start, _, fi = _freshness_gate()
    return "\n".join(lines[start : fi + 1])


def _run_freshness_block(tmp_path: Path, paused: bool) -> tuple[str, str | None]:
    """Execute the block with the check forced stale: `_step` fails, the alert helper records its
    arguments, and the pause predicate answers as told. Returns (stdout, the alert text or None)."""
    kb = tmp_path / "kb"
    kb.mkdir()
    alert = tmp_path / "alert.txt"
    (kb / "pipeline_alert.sh").write_text(f'printf "%s\\n%s\\n" "$1" "$2" > "{alert}"\n')
    # `set -u` because the chain runs under it (an unbound variable there kills the rest of the
    # run, heartbeat included), and BLOCK-END proves the block fell through rather than exiting.
    script = (
        "set -u\n"
        f'FABRIK_ROOT="{tmp_path}"; VENV_PY=true; KB="{kb}"\n'
        '_step() { echo "STEP-RAN $1"; return 1; }\n'
        f"_pool_eval_paused() {{ return {0 if paused else 1}; }}\n"
        f"{_freshness_block()}\n"
        "echo BLOCK-END\n"
    )
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False)
    return out.stdout, alert.read_text() if alert.exists() else None


def test_the_delivered_freshness_page_stands_down_while_delivery_is_paused(tmp_path):
    """W-1a18423a: the chain skips deliver_to_fabrik while the pool is paused, so the delivered
    markers age by construction. Paging on that certainty fired every day and blamed the engine;
    while paused the step must page nothing and say in the log that the pause is the cause."""
    stdout, alert = _run_freshness_block(tmp_path, paused=True)
    assert alert is None, f"paged while paused:\n{alert}"
    assert "STEP-RAN" not in stdout, stdout
    assert "POOL EVAL PAUSED" in stdout and "check_ai_pack_freshness_delivered" in stdout, stdout
    assert "BLOCK-END" in stdout, f"the block did not fall through:\n{stdout}"


def test_the_delivered_freshness_page_still_fires_when_the_pool_is_on_and_names_both_causes(
    tmp_path,
):
    """The mirror of the stand-down: deleting the check would also stop the false page. With the
    pool on, a stale marker must still page, and the text must name the hub's own delivery step as
    well as the engine instead of blaming only the engine."""
    stdout, alert = _run_freshness_block(tmp_path, paused=False)
    assert "STEP-RAN check_ai_pack_freshness_delivered" in stdout, stdout
    assert alert is not None, "a stale marker did not page with the pool on"
    assert "BLOCK-END" in stdout, f"the block did not fall through:\n{stdout}"
    assert "Two causes" in alert and "deliver_to_fabrik step failed or was skipped" in alert, alert
    assert "engine venv missing" in alert, alert
    assert "/opt/ai-model-catalog/engine/cache/update.log" in alert, alert


def test_the_delivered_freshness_check_runs_only_inside_its_pause_gate():
    """A second, ungated copy of the check anywhere else in the chain would bring the daily false
    page back while the block tests above stay green. Exactly one live invocation (comments and the
    page's own "Re-check:" hint are not invocations), and it sits strictly inside the gate's branch:
    after the `if` line, before the `fi` line, indented deeper than the gate."""
    lines, _, gate, fi = _freshness_gate()
    calls = [
        i
        for i, ln in enumerate(lines)
        if _INVOKE.search(ln) and not ln.lstrip().startswith("#") and "Re-check:" not in ln
    ]
    assert len(calls) == 1, (
        f"{len(calls)} live invocations of the delivered-freshness check: {calls}"
    )
    (call,) = calls
    assert gate < call < fi and _indent(lines[call]) > _indent(lines[gate]), (
        f"the check at line {call + 1} is not inside the pause gate (lines {gate + 1}-{fi + 1})"
    )
