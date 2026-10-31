"""The hooks hold the pause (W-6e656dac T02, spec § Chosen approach L2).

Two hooks read the pause marker (`hibernate.json`, Interface M) INLINE — `quota_stop.py` is fleet-synced and may
import no hub module, and `quota_posture_hook.py` reads it the same way so the two cannot disagree:

* `quota_stop.py`: a `hibernate`-tier stamp holds through a stale, unknown or missing tick age while the pause is
  marked and not lifted, and the pause's own verbs (`hibernate.py status|woke|paused|lift`, exact forms) pass the hold.
* `quota_posture_hook.py`: while the pause is marked and not lifted, `Agent` and every `command_run.py start` (the
  review family included) are denied for every session, BEFORE the stamp/posture early return.

Every grader drives the real stdin/stdout contract of each hook; the autouse pins in `tests/conftest.py` keep
`ROTATE_STATE_DIR` inside tmp, and every subprocess here sets it explicitly too.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
STOP_HOOK = REPO / ".claude" / "hooks" / "quota_stop.py"
POSTURE_HOOK = REPO / "scripts" / "sysadmin" / "quota_posture_hook.py"
HIBERNATE = REPO / "scripts" / "sysadmin" / "hibernate.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


stop = _load("quota_stop_hibernate", STOP_HOOK)
posture = _load("quota_posture_hibernate", POSTURE_HOOK)
hib = _load("hibernate_hooks_probe", HIBERNATE)

NOW = time.time()


def _mark(state: Path, *, lifted: bool = False, **extra: object) -> None:
    state.mkdir(parents=True, exist_ok=True)
    m: dict[str, object] = {"paused_at": NOW - 60, "words": "/hibernate", **extra}
    if lifted:
        m["lifted_at"] = NOW - 10
    (state / "hibernate.json").write_text(json.dumps(m), encoding="utf-8")


def _run(path: Path, payload: dict, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ, **env},
        timeout=30,
    )


def _decision(r: subprocess.CompletedProcess) -> str:
    assert r.returncode == 0, r.stderr
    if not r.stdout.strip():
        return "allow_warn" if r.stderr.strip() else "allow"
    out = json.loads(r.stdout)["hookSpecificOutput"]
    return out.get("permissionDecision", "notice")


# ── quota_stop.py ────────────────────────────────────────────────────────────────────────────────────────────────


def _stop(tmp_path: Path, payload: dict, *, tier: str, tick: str) -> subprocess.CompletedProcess:
    """tick ∈ {fresh, days, missing}."""
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    (state / "fleet-exhausted").write_text(f"0\n{tier}\n")
    log = tmp_path / "rotate-tick.log"
    log.unlink(missing_ok=True)
    if tick != "missing":
        log.write_text("tick: ok\n")
        if tick == "days":
            old = time.time() - 3 * 86400
            os.utime(log, (old, old))
    return _run(
        STOP_HOOK, payload, {"ROTATE_STATE_DIR": str(state), "QUOTA_STOP_TICK_LOG": str(log)}
    )


EDIT = {"tool_name": "Edit", "tool_input": {"file_path": "x.py"}, "session_id": "s1"}


@pytest.mark.parametrize("tick", ["days", "missing"])
def test_a_marked_hibernate_tier_holds_through_a_stale_or_missing_tick(tmp_path, tick):
    """Row 1: the minutes after a wake, before the first tick, stay held — however long the sleep."""
    _mark(tmp_path / "state")
    r = _stop(tmp_path, EDIT, tier="hibernate", tick=tick)
    assert _decision(r) == "deny", (r.stdout, r.stderr)
    reason = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert reason.startswith("HIBERNATE"), reason


@pytest.mark.parametrize("tick", ["days", "missing"])
def test_the_stale_tick_fail_open_stands_for_every_other_shape(tmp_path, tick):
    """Only the marked `hibernate` tier overrides the fail-open: a lifted mark, no marker, and a `walled` or
    `battery` stamp under a mark all still allow (with the warning) when the tick is dead."""
    state = tmp_path / "state"
    _mark(state, lifted=True)
    assert _decision(_stop(tmp_path, EDIT, tier="hibernate", tick=tick)) == "allow_warn"
    (state / "hibernate.json").unlink()
    assert _decision(_stop(tmp_path, EDIT, tier="hibernate", tick=tick)) == "allow_warn"
    _mark(state)
    for tier in ("walled", "battery"):
        assert _decision(_stop(tmp_path, EDIT, tier=tier, tick=tick)) == "allow_warn", tier


def test_a_fresh_hibernate_tier_holds_with_the_hibernate_head(tmp_path):
    _mark(tmp_path / "state")
    r = _stop(tmp_path, EDIT, tier="hibernate", tick="fresh")
    assert _decision(r) == "deny"
    reason = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert reason.startswith("HIBERNATE HOLD"), reason
    assert "FLEET QUOTA EXHAUSTED" not in reason and "BATTERY" not in reason
    assert "partial result" in reason, "a held subagent is told to return now"
    assert "hibernate.py status" in reason
    assert "selfwatch_arm.sh s1" in reason, "the arm order still names the literal sid"


_HIB = "python3 /opt/fabrik/scripts/sysadmin/hibernate.py"


@pytest.mark.parametrize(
    "cmd",
    [
        f"{_HIB} status",
        f"{_HIB} status --json",
        f"{_HIB} status --self 1970a0ff-baa3-401b-ba52-fb0c5de43261",
        f"{_HIB} status --json --self abc.def_1",
        f"{_HIB} woke",
        f"{_HIB} woke --self abc-123",
        f"{_HIB} paused",
        f"{_HIB} lift",
    ],
)
def test_the_pause_verbs_pass_the_hold_in_their_exact_forms(cmd):
    """Row 2: the coordinator reads `status` from T-3, an agent runs `woke`/`paused`, and `lift` escapes a dead
    cron (its caller check is hibernate.py's own, never the hook's)."""
    assert stop.decide("Bash", cmd, stamp_exists=True, tick_age_s=10.0, tier="walled") == (
        "allow",
        "",
    ), cmd


@pytest.mark.parametrize(
    "cmd",
    [
        f"{_HIB} mark --words x",
        f"{_HIB} brief --role agent --words x",
        f"{_HIB} targets",
        f"{_HIB} lift --home /tmp/x",
        f"{_HIB} lift --proc /tmp/p",
        f"{_HIB} status --proc /tmp/p",
        f"{_HIB} status --home /tmp/h",
        f"{_HIB} status --self",
        f"{_HIB} status --self {'a' * 81}",
        f"{_HIB} status > /tmp/out",
        f"{_HIB} status; touch m",
        f"{_HIB} status && touch m",
        f"{_HIB} status $(touch m)",
        f"{_HIB} statusx",
        f"{_HIB} lift --json",
        "python3 /tmp/scripts/sysadmin/hibernate.py status",
        "python3 /opt/fabrik/scripts/sysadmin/hibernate.py.bak status",
        "python3 /opt/fabrik/../scripts/sysadmin/hibernate.py status",
        "python3 scripts/sysadmin/hibernate.py status",
        "python /opt/fabrik/scripts/sysadmin/hibernate.py status",
    ],
)
def test_every_other_hibernate_form_stays_held(cmd):
    assert (
        stop.decide("Bash", cmd, stamp_exists=True, tick_age_s=10.0, tier="walled")[0] == "deny"
    ), cmd


@pytest.mark.parametrize(
    "cmd",
    [
        f"{_HIB} paused --json",
        f"{_HIB} woke --json",
        f"{_HIB} paused --self x",
        f"{_HIB} status --self --home",
        f"{_HIB} status --self --json",
        f"{_HIB} status --json --json",
        f"{_HIB} woke --self abc --self def",
        f"{_HIB} woke --self -x",
    ],
)
def test_the_allow_list_is_no_wider_than_the_verbs_argparse(cmd):
    """Review J2: per verb, exactly what `hibernate.py`'s argparse takes — `status` [--json] [--self <sid>], `woke`
    [--self <sid>], `paused` and `lift` bare; a sid never starts with `-` (it would be read as a flag)."""
    assert (
        stop.decide("Bash", cmd, stamp_exists=True, tick_age_s=10.0, tier="walled")[0] == "deny"
    ), cmd


def test_status_takes_its_two_flags_in_either_order():
    for cmd in (f"{_HIB} status --self abc --json", f"{_HIB} status --json --self abc"):
        assert stop.decide("Bash", cmd, stamp_exists=True, tick_age_s=10.0) == ("allow", ""), cmd


def test_every_hibernate_command_the_hold_messages_print_is_one_the_hold_allows():
    """Review J3: a held agent pastes what the message names — `status|woke|paused` as one literal is a pipe, denied."""
    import re as _re

    texts = [stop._reason("Edit", "s1", hibernate=True), posture._pause_reason("The Agent tool")]
    for text in texts:
        cmds = _re.findall(r"`(python3 /opt/fabrik/scripts/sysadmin/hibernate\.py[^`]*)`", text)
        assert len(cmds) >= 2, text
        for cmd in cmds:
            assert stop._bash_allowed(cmd), cmd


# ── quota_posture_hook.py ────────────────────────────────────────────────────────────────────────────────────────


def _posture_file(state: Path, band: str = "GREEN") -> None:
    state.mkdir(parents=True, exist_ok=True)
    now = time.time()
    win = {
        "utilization": 10.0,
        "resets_at": now + 3600,
        "wall_pct": 100.0,
        "verdict": "reset_first",
    }
    doc = {
        "schema": 1,
        "ts": now,
        "tick_period_s": 300.0,
        "active": {
            "slug": "a",
            "email": "a@x",
            "windows": {"five_hour": win, "seven_day": win, "fable": win, "models": {}},
            "hottest": "five_hour",
            "band": band,
            "band_account": band,
            "hottest_fable": "five_hour",
            "band_fable": band,
            "band_account_fable": band,
        },
        "fleet": {"queue": [], "successor": None, "windows": {}, "thresholds": {}},
        "samples": {},
    }
    (state / "quota-posture.json").write_text(json.dumps(doc), encoding="utf-8")


def _posture_run(tmp_path: Path, payload: dict) -> subprocess.CompletedProcess:
    return _run(
        POSTURE_HOOK,
        {"hook_event_name": "PreToolUse", "session_id": "s1", **payload},
        {"ROTATE_STATE_DIR": str(tmp_path / "state"), "COMMAND_RUN_DIR": str(tmp_path / "runs")},
    )


def _live_run(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir(exist_ok=True)
    (runs / "s1.json").write_text(json.dumps({"state": "running"}), encoding="utf-8")


INTAKE = [
    {"tool_name": "Agent", "tool_input": {"prompt": "go"}},
    {
        "tool_name": "Bash",
        "tool_input": {
            "command": "python3 scripts/command_run.py start --command fabrik-spec --phases 3"
        },
    },
    {
        "tool_name": "Bash",
        "tool_input": {
            "command": "python3 scripts/command_run.py start --command fabrik-review --phases 4"
        },
    },
    {
        "tool_name": "Bash",
        "tool_input": {
            "command": "python3 /opt/fabrik/scripts/command_run.py start --command fabrik-review-scoped"
        },
    },
]


@pytest.mark.parametrize("payload", INTAKE, ids=["agent", "start", "review-start", "scoped-start"])
@pytest.mark.parametrize("stamp", [None, "hibernate", "walled", "urgent-90"])
def test_a_marked_pause_denies_intake_to_a_session_with_a_live_run_before_and_after_t3(
    tmp_path, payload, stamp
):
    """Row 3: GREEN posture, a live run (which licenses `Agent` at RED), the review family (which passes RED) —
    and before T-3 (no stamp) or after it (the `hibernate` tier, or any stamp that would return early)."""
    _posture_file(tmp_path / "state")
    _live_run(tmp_path)
    _mark(tmp_path / "state")
    if stamp:
        (tmp_path / "state" / "fleet-exhausted").write_text(f"0\n{stamp}\n")
    r = _posture_run(tmp_path, payload)
    assert _decision(r) == "deny", (r.stdout, r.stderr)
    reason = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert reason.startswith("HIBERNATE PAUSE"), reason


@pytest.mark.parametrize("payload", INTAKE[:2], ids=["agent", "start"])
def test_a_marked_pause_with_no_posture_file_still_denies(tmp_path, payload):
    """Row 4: no posture file is the `:1089` early return — the marker check runs before it."""
    _mark(tmp_path / "state")
    assert not (tmp_path / "state" / "quota-posture.json").exists()
    assert _decision(_posture_run(tmp_path, payload)) == "deny"


def test_a_marked_pause_denies_the_workflow_dispatch_too(tmp_path):
    """Review J4: `Workflow` is the other dispatch tool — nothing new is dispatched on any session."""
    _posture_file(tmp_path / "state")
    _live_run(tmp_path)
    _mark(tmp_path / "state")
    r = _posture_run(tmp_path, {"tool_name": "Workflow", "tool_input": {"script": "x"}})
    assert _decision(r) == "deny", (r.stdout, r.stderr)
    _mark(tmp_path / "state", lifted=True)
    assert _decision(_posture_run(tmp_path, {"tool_name": "Workflow", "tool_input": {}})) == "allow"


_HOSTILE = {
    "huge-int": '{"paused_at": 1' + "0" * 400 + "}",
    "huge-lifted": '{"paused_at": 1, "lifted_at": 1' + "0" * 400 + "}",
    "deep": "[" * 200000 + "]" * 200000,
    "deep-in-object": '{"paused_at": 1, "x": ' + "[" * 200000 + "]" * 200000 + "}",
}


@pytest.mark.parametrize("body", list(_HOSTILE.values()), ids=list(_HOSTILE))
def test_a_hostile_marker_reads_as_unmarked_and_never_crashes_a_reader(tmp_path, monkeypatch, body):
    """Review J1: a 400-digit int overflows `float()` and deep nesting raises RecursionError; both crashed the
    readers. Either is a corrupt marker, so UNMARKED — fail open, never a crash."""
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    (state / "hibernate.json").write_text(body, encoding="utf-8")
    assert stop._pause_marked() is False
    assert posture._pause_marked() is False


@pytest.mark.parametrize("body", list(_HOSTILE.values()), ids=list(_HOSTILE))
def test_a_hostile_marker_never_opens_either_hooks_hold(tmp_path, body):
    """Review J1, end to end: a crashed PreToolUse hook exits 1, which the harness reads as non-blocking — so the
    stamp's hold and the RED `Agent` hold opened. Each hook must still exit 0 with its normal deny."""
    state = tmp_path / "state"
    state.mkdir()
    (state / "hibernate.json").write_text(body, encoding="utf-8")
    r = _stop(tmp_path, EDIT, tier="hibernate", tick="fresh")
    assert r.returncode == 0 and _decision(r) == "deny", (r.returncode, r.stdout, r.stderr[-300:])
    (
        state / "fleet-exhausted"
    ).unlink()  # a standing stamp is quota_stop's; the RED band is this hook's
    _posture_file(state, band="RED")
    p = _posture_run(tmp_path, {"tool_name": "Agent", "tool_input": {"prompt": "go"}})
    assert p.returncode == 0 and _decision(p) == "deny", (p.returncode, p.stdout, p.stderr[-300:])


def test_a_lifted_or_absent_pause_holds_no_intake(tmp_path):
    _posture_file(tmp_path / "state")
    for p in INTAKE:
        assert _decision(_posture_run(tmp_path, p)) == "allow", p
    _mark(tmp_path / "state", lifted=True)
    for p in INTAKE:
        assert _decision(_posture_run(tmp_path, p)) == "allow", p


def test_a_marked_pause_leaves_checkpoint_work_alone(tmp_path):
    _mark(tmp_path / "state")
    for p in (
        {"tool_name": "Edit", "tool_input": {"file_path": "x.py"}},
        {"tool_name": "Bash", "tool_input": {"command": "git commit -m x -- a.py"}},
        {
            "tool_name": "Bash",
            "tool_input": {"command": "python3 scripts/command_run.py done --command x"},
        },
        {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m 'ran command_run.py start' -- a.py"},
        },
    ):
        assert _decision(_posture_run(tmp_path, p)) == "allow", p


# ── the seam: the marker the verbs write is the marker the hooks read ────────────────────────────────────────────


def test_the_hook_reads_the_marker_the_verbs_write(tmp_path, monkeypatch):
    """Interface M: `hibernate.py mark` (the real CLI) writes it; both hooks read it as marked; the lift written
    through `update_marker` (the path the tick and the hub's `lift` take) reads as unmarked in both."""
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    assert not stop._pause_marked() and not posture._pause_marked()
    r = subprocess.run(
        [
            sys.executable,
            str(HIBERNATE),
            "--home",
            str(tmp_path),
            "mark",
            "--words",
            "w",
            "--deadline",
            "10m",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "ROTATE_STATE_DIR": str(state)},
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    assert (state / "hibernate.json").is_file()
    assert stop._pause_marked() and posture._pause_marked()
    hib.update_marker(tmp_path, lambda m: {**m, "lifted_at": time.time(), "lift_path": "hub"})
    assert not stop._pause_marked() and not posture._pause_marked()


@pytest.mark.parametrize(
    "body",
    [
        None,
        "",
        "not json",
        "[]",
        "{}",
        '{"paused_at": 1}',
        '{"paused_at": 1, "lifted_at": 2}',
        '{"paused_at": 2, "lifted_at": 1}',
        '{"paused_at": 2, "lifted_at": 2}',
        '{"paused_at": null}',
        '{"paused_at": "1"}',
        '{"paused_at": true}',
        '{"paused_at": NaN}',
        '{"paused_at": Infinity}',
        '{"paused_at": 1, "lifted_at": null}',
        '{"paused_at": 1, "lifted_at": "x"}',
        '{"paused_at": 1, "deadline_at": "x"}',
        '{"paused_at": 1, "deadline_at": null}',
        '{"paused_at": 1, "lifted_at": NaN}',
        '{"words": "x"}',
    ],
)
def test_both_hooks_read_marked_exactly_when_paused_exits_zero(tmp_path, monkeypatch, body):
    """The inline copies agree with `hibernate.py paused` (exit 0 = marked) on every shape, the corrupt ones
    included: a corrupt marker is `paused` exit 2, which the hooks read as unmarked (they fail open)."""
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    if body is not None:
        (state / "hibernate.json").write_text(body, encoding="utf-8")
    expected = hib.paused(tmp_path)[0] == 0
    assert stop._pause_marked() is expected, body
    assert posture._pause_marked() is expected, body


def test_the_marker_readers_do_not_hang_on_a_fifo(tmp_path):
    """A FIFO at the marker path blocks a bare read forever — a PreToolUse hook that never returns stalls every
    tool call in the session."""
    state = tmp_path / "state"
    state.mkdir()
    os.mkfifo(state / "hibernate.json")
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import importlib.util, sys\n"
        "spec = importlib.util.spec_from_file_location('p', sys.argv[1])\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "print(m._pause_marked())\n"
    )
    for hook in (STOP_HOOK, POSTURE_HOOK):
        r = subprocess.run(
            [sys.executable, str(probe), str(hook)],
            capture_output=True,
            text=True,
            env={**os.environ, "ROTATE_STATE_DIR": str(state)},
            timeout=15,
        )
        assert r.stdout.strip() == "False", (hook, r.stdout, r.stderr)


def test_the_marker_state_dir_is_the_passwd_home_never_dollar_home(tmp_path, monkeypatch):
    """Interface M: with no `$ROTATE_STATE_DIR`, every reader resolves `<passwd home>/.claude/state` — the dir
    `mark` wrote — never `$HOME`, which a caller sets as freely."""
    import pwd

    monkeypatch.delenv("ROTATE_STATE_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    real = Path(pwd.getpwuid(os.getuid()).pw_dir) / ".claude" / "state" / "hibernate.json"
    assert stop._marker_path() == real
    assert posture._marker_path() == real
    assert hib.marker_path(hib._default_home()) == real
