"""Phase C of docs/development/plans/2026-09-16-plan-1-quota-posture.md — the readers.

The hook is box-local (`scripts/sysadmin/quota_posture_hook.py`, wired into the six user-level
settings files, never fleet-synced), so it is loaded BY PATH here exactly as the neighbouring hook
suites load theirs. Every grader drives the real stdin/stdout contract the CLI uses, because that
is the surface the contract in CLAUDE.md promises to every window on this box.

⚠️ The autouse pins in `tests/conftest.py` cover this file too: `FABRIK_OPT_DIR`,
`ROTATE_STATE_DIR` and `COMMAND_RUN_DIR` are all inside tmp. Nothing here may reach the operator's
live state — a rotation grader mailed 49 real project mailboxes on 2026-09-16 by doing exactly that.
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

HOOK = Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "quota_posture_hook.py"


def _load():
    spec = importlib.util.spec_from_file_location("quota_posture_hook_probe", HOOK)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _posture(state: Path, *, band="GREEN", band_fable=None, ts=None, slug="ozgurbasak", **over):
    """A schema-1 posture file in *state*, shaped exactly as `_quota_posture` writes it."""
    state.mkdir(parents=True, exist_ok=True)
    now = time.time() if ts is None else ts
    doc = {
        "schema": 1,
        "ts": now,
        "tick_period_s": 300.0,
        "active": {
            "email": f"{slug}@ocoron.com",
            "slug": slug,
            "weekly_cap": 99.0,
            "windows": {
                "five_hour": {
                    "utilization": 71.0,
                    "resets_at": now + 7800.0,
                    "wall_pct": 100.0,
                    "burn_per_min": 0.6,
                    "minutes_to_wall": 48.0,
                    "minutes_to_reset": 130.0,
                    "verdict": "wall_first",
                },
                "seven_day": {
                    "utilization": 44.0,
                    "resets_at": now + 7800.0,
                    "wall_pct": 99.0,
                    "burn_per_min": None,
                    "minutes_to_wall": None,
                    "minutes_to_reset": 130.0,
                    "verdict": "reset_first",
                },
                "fable": {
                    "utilization": 32.0,
                    "resets_at": now + 7800.0,
                    "wall_pct": 100.0,
                    "burn_per_min": None,
                    "minutes_to_wall": None,
                    "minutes_to_reset": 130.0,
                    "verdict": "reset_first",
                },
                "models": {},
            },
            "hottest": "five_hour",
            "band": band,
            "hottest_fable": "five_hour",
            "band_fable": band if band_fable is None else band_fable,
        },
        "fleet": {
            "queue": [],
            "successor": {"email": "mob@ocoron.com", "slug": "mob"},
            "next_relief": None,
            "hold": None,
            "last_flip": None,
            "thresholds": {"drain_band": 85.0, "urgent": 90.0},
        },
        "samples": {},
    }
    for k, v in over.items():
        doc["active"]["windows"][k] = v
    (state / "quota-posture.json").write_text(json.dumps(doc), encoding="utf-8")
    return doc


def _hook(payload: dict, *, state: Path, runs: Path | None = None, extra_env=None):
    """Drive the hook as the CLI does: JSON on stdin, JSON or a bare line on stdout, rc always 0."""
    env = dict(os.environ)
    env["ROTATE_STATE_DIR"] = str(state)
    if runs is not None:
        env["COMMAND_RUN_DIR"] = str(runs)
    env.update(extra_env or {})
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    return proc


# --- C1/C2: the prompt line ---------------------------------------------------------------------


def test_prompt_line_says_unavailable_when_the_file_is_absent_or_stale(tmp_path):
    """C1 — an unreadable posture is ABSENT, and absent is said out loud, never silently fine."""
    state = tmp_path / "state"
    state.mkdir()
    p = _hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"}, state=state)
    assert p.returncode == 0
    assert "posture unavailable (absent)" in p.stdout and "--status" in p.stdout

    _posture(state, ts=time.time() - 901.0)
    p = _hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"}, state=state)
    assert p.returncode == 0 and "posture unavailable (stale" in p.stdout

    # and a PreToolUse in either state holds nothing and says nothing
    p = _hook(
        {"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "s1"}, state=state
    )
    assert p.returncode == 0 and p.stdout.strip() == ""


def test_prompt_line_matches_the_contract_format_byte_for_byte(tmp_path):
    """C2 — the line the three contracts promise, rendered exactly, tokens and all."""
    state = tmp_path / "state"
    _posture(state)
    p = _hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"}, state=state)
    line = p.stdout.strip()
    assert line == (
        "QUOTA: ozgurbasak · 5h 71% (wall in ~48m at 0.60%/m) · weekly 44% (reset in 2:10) · "
        "Fable 32% · band GREEN · successor mob"
    ), line
    for token in ("QUOTA: ", " · band ", " · successor ", " · Fable "):
        assert token in line, token


def test_prompt_line_prints_an_em_dash_for_a_missing_figure_and_a_question_mark_for_no_band(
    tmp_path,
):
    """C2b — the contract's own escapes: a figure the tick has no reading for, and no band."""
    state = tmp_path / "state"
    _posture(state, band=None, fable=None)
    p = _hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"}, state=state)
    line = p.stdout.strip()
    assert "Fable —" in line and "band ?" in line, line


# --- C3/C4/C5: the RED hold ---------------------------------------------------------------------


def test_red_holds_agent_only_without_a_live_run(tmp_path):
    """C3/C4 — RED holds a NEW fan-out; a session already holding a run record keeps its seats."""
    state, runs = tmp_path / "state", tmp_path / "runs"
    runs.mkdir()
    _posture(state, band="RED")
    p = _hook(
        {"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "s1"},
        state=state,
        runs=runs,
    )
    out = json.loads(p.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "RED" in out["hookSpecificOutput"]["permissionDecisionReason"]

    (runs / "s1.json").write_text(json.dumps({"state": "running"}), encoding="utf-8")
    p = _hook(
        {"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "s1"},
        state=state,
        runs=runs,
    )
    assert p.stdout.strip() == "", p.stdout

    # every tool a checkpoint needs stays allowed, with or without a record
    for tool in ("Bash", "Edit", "Write", "Read", "Monitor", "TaskStop"):
        p = _hook(
            {"hook_event_name": "PreToolUse", "tool_name": tool, "session_id": "s2"},
            state=state,
            runs=runs,
        )
        assert p.stdout.strip() == "", (tool, p.stdout)


@pytest.mark.parametrize(
    "command,denied",
    [
        ("python3 scripts/command_run.py start --command fabrik-spec --phases 3", True),
        ("uv run python scripts/command_run.py start --command fabrik-plan-after-chat", True),
        (
            "cd /opt/x && python3 /opt/fabrik/scripts/command_run.py start --command fabrik-deploy",
            True,
        ),
        ("python3 scripts/command_run.py start --phases 2 --command fabrik-rivals", True),
        ("python3 /opt/fabrik/scripts/command_run.py start --command fabrik-review-scoped", False),
        ("python3 scripts/command_run.py start --command fabrik-review --phases 4", False),
        ("python3 scripts/command_run.py done --command fabrik-spec --evidence x", False),
        ("python3 scripts/command_run.py round --findings 0 --confirmed 0", False),
    ],
)
def test_red_holds_a_new_command_start_but_not_the_review_that_finishes(tmp_path, command, denied):
    """C5 — RED stops a FRESH round on something new; the mandated review of the change you are
    checkpointing is the one start that stays allowed, in every spelling the corpus uses."""
    state, runs = tmp_path / "state", tmp_path / "runs"
    runs.mkdir()
    _posture(state, band="RED")
    p = _hook(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "session_id": "s1",
        },
        state=state,
        runs=runs,
    )
    if denied:
        assert json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny", command
    else:
        assert p.stdout.strip() == "", (command, p.stdout)


def test_wall_is_left_to_quota_stop(tmp_path):
    """C6 — the WALL is `quota_stop.py`'s alone; the stamp is read BEFORE the band, so a lagging
    RED posture can never produce a second, differently worded deny for the same call."""
    state, runs = tmp_path / "state", tmp_path / "runs"
    runs.mkdir()
    _posture(state, band="WALL")
    p = _hook(
        {"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "s1"},
        state=state,
        runs=runs,
    )
    assert p.stdout.strip() == ""

    _posture(state, band="RED")
    (state / "fleet-exhausted").write_text("", encoding="utf-8")
    p = _hook(
        {"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "s1"},
        state=state,
        runs=runs,
    )
    assert p.stdout.strip() == "", "the stamp must win before the band"

    # ⚠️ TWO guards, and each needs its own assertion. The one above grades `main`'s early return;
    # this grades the pure predicate's own `stamp` argument, which `main` never passes as True.
    # Without this, deleting the predicate's guard changed nothing observable and the mutation went
    # UNCAUGHT — a dead parameter reads exactly like a working one (Phase C, review round 0).
    mod = _load()
    assert mod.decide("RED", "Agent", None, sid="s1", stamp=True) == ("pass", "")
    assert mod.decide("RED", "Agent", None, sid="s1", stamp=False)[0] == "deny"
    assert mod.decide("WALL", "Agent", None, sid="s1", stamp=False) == ("pass", "")


# --- C7/C8: the session's model ------------------------------------------------------------------


def test_fable_sessions_key_the_band_on_the_fable_window(tmp_path):
    """C7 — a Fable session is banded on its Fable window; any other model is not, and an unknown
    model never bands on Fable. The LINE shows the Fable figure either way."""
    state, runs = tmp_path / "state", tmp_path / "runs"
    runs.mkdir()
    _posture(state, band="GREEN", band_fable="RED")
    t = tmp_path / "t.jsonl"

    t.write_text(
        json.dumps({"type": "assistant", "message": {"model": "claude-fable-5-1"}}),
        encoding="utf-8",
    )
    p = _hook(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Agent",
            "session_id": "s1",
            "transcript_path": str(t),
        },
        state=state,
        runs=runs,
    )
    assert json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"

    t.write_text(
        json.dumps({"type": "assistant", "message": {"model": "claude-opus-5"}}), encoding="utf-8"
    )
    p = _hook(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Agent",
            "session_id": "s1",
            "transcript_path": str(t),
        },
        state=state,
        runs=runs,
    )
    assert p.stdout.strip() == ""

    p = _hook(
        {"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "s1"},
        state=state,
        runs=runs,
    )
    assert p.stdout.strip() == "", (
        "no transcript means an unknown model, which never bands on Fable"
    )


def test_session_model_reads_only_the_transcript_tail(tmp_path):
    """C8 — a hook on the tool path may not read a multi-megabyte transcript whole."""
    mod = _load()
    t = tmp_path / "big.jsonl"
    filler = json.dumps({"type": "assistant", "message": {"model": "claude-opus-5"}}) + "\n"
    with open(t, "w", encoding="utf-8") as fh:
        fh.write(filler * 20000)  # ~2 MiB
        fh.write(json.dumps({"type": "assistant", "message": {"model": "claude-fable-5-1"}}) + "\n")
    start = time.time()
    assert mod._session_model(str(t)) == "claude-fable-5-1"
    assert time.time() - start < 0.5
    assert mod._session_model(None) is None and mod._session_model(str(tmp_path / "nope")) is None


# --- C9/C10: AMBER once, and never blocking on our own defect -----------------------------------


def test_amber_is_said_once_per_band_change(tmp_path):
    """C9 — AMBER is ADVICE: context, never a permission decision, and once per session and band."""
    state, runs = tmp_path / "state", tmp_path / "runs"
    runs.mkdir()
    _posture(state, band="AMBER")
    call = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "s1"}

    first = _hook(call, state=state, runs=runs)
    out = json.loads(first.stdout)["hookSpecificOutput"]
    assert "additionalContext" in out and "permissionDecision" not in out
    assert "AMBER" in out["additionalContext"]

    assert _hook(call, state=state, runs=runs).stdout.strip() == "", "said twice in one session"

    fresh = dict(call, session_id="s2")
    assert (
        "additionalContext"
        in json.loads(_hook(fresh, state=state, runs=runs).stdout)["hookSpecificOutput"]
    )


def test_malformed_payloads_never_block(tmp_path):
    """C10 — rc 0 and silence on anything we cannot parse: never block on our own defect."""
    state = tmp_path / "state"
    _posture(state, band="RED")
    env = dict(os.environ, ROTATE_STATE_DIR=str(state))
    for raw in ("not json at all", "[]", "{}", "", "null", '{"hook_event_name": 7}'):
        proc = subprocess.run(
            [sys.executable, str(HOOK)],
            input=raw,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        assert proc.returncode == 0, raw
        assert proc.stdout.strip() == "", (raw, proc.stdout)


# --- C15: the local copies must not drift from command_run --------------------------------------


def test_the_hook_sid_and_state_dir_copies_agree_with_command_run(tmp_path, monkeypatch):
    """C15 — the hook COPIES `_safe_sid`/`_state_dir` rather than importing a 1,000-line CLI on
    every tool call. A copy that drifts sends the hold looking at the wrong record."""
    mod = _load()
    spec = importlib.util.spec_from_file_location(
        "command_run_parity_probe",
        Path(__file__).resolve().parents[1] / "scripts" / "command_run.py",
    )
    cr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cr)
    corpus = [
        "1970a0ff-baa3-401b-ba52-fb0c5de43261",
        "abc.xyz",
        "abc xyz",
        "",
        "nosession",
        "a/b\\c",
        "ünïcode-sid",
        "x" * 200,
    ]
    for sid in corpus:
        assert mod._safe_sid(sid) == cr._safe_sid(sid), sid
    monkeypatch.setenv("COMMAND_RUN_DIR", str(tmp_path / "runs"))
    assert mod._state_dir() == cr._state_dir()


def test_the_hook_review_family_copy_agrees_with_command_run():
    """C15b — the set that decides which `start` survives RED is the corpus's own, not a guess."""
    mod = _load()
    spec = importlib.util.spec_from_file_location(
        "command_run_family_probe",
        Path(__file__).resolve().parents[1] / "scripts" / "command_run.py",
    )
    cr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cr)
    assert set(mod.REVIEW_FAMILY) == set(cr.REVIEW_FAMILY)


# --- C11: the installer --------------------------------------------------------------------------


def test_install_adds_both_entries_once_and_preserves_every_other_key(tmp_path):
    """C11 — six INDEPENDENT settings files, two of them deliberately drifted in `model`. The
    installer wires each in place, idempotently, backs it up, and never copies one over another."""
    mod = _load()
    files = []
    for i in range(6):
        p = tmp_path / f"s{i}" / "settings.json"
        p.parent.mkdir(parents=True)
        cfg = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "x"}]}]}}
        if i >= 4:
            cfg["model"] = f"drifted-model-{i}"  # the measured per-account drift
        p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        files.append(p)

    assert sum(v != "OK" for _, v in mod.check(files)) == 6
    mod.install(files)
    assert sum(v != "OK" for _, v in mod.check(files)) == 0

    for i, p in enumerate(files):
        cfg = json.loads(p.read_text(encoding="utf-8"))
        for event in ("UserPromptSubmit", "PreToolUse"):
            entries = [e for e in cfg["hooks"][event] if "quota_posture_hook.py" in json.dumps(e)]
            assert len(entries) == 1, (p, event)
        assert cfg["hooks"]["SessionStart"], "an unrelated event was dropped"
        if i >= 4:
            assert cfg["model"] == f"drifted-model-{i}", "the per-account drift was clobbered"
        else:
            assert "model" not in cfg
        assert list(p.parent.glob("settings.json.backup.*")), "no backup beside the file"

    mod.install(files)  # idempotent: a second run adds nothing
    for p in files:
        cfg = json.loads(p.read_text(encoding="utf-8"))
        for event in ("UserPromptSubmit", "PreToolUse"):
            entries = [e for e in cfg["hooks"][event] if "quota_posture_hook.py" in json.dumps(e)]
            assert len(entries) == 1, (p, event, "a second --install duplicated the entry")


def test_settings_files_skips_the_active_symlink(tmp_path, monkeypatch):
    """C11b — the fleet root's `active` is a SYMLINK to whichever account is current. Including it
    would wire ONE account twice and take the second backup of an already-edited file."""
    mod = _load()
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    fleet = home / ".claude-fleet"
    for slug in ("can", "mob", "ob", "ozgurbasak", "sarp"):
        (fleet / slug).mkdir(parents=True)
    (fleet / "active").symlink_to(fleet / "can")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.delenv("QUOTA_POSTURE_SETTINGS", raising=False)
    found = mod.settings_files()
    assert len(found) == 6, found
    assert not any("active" in str(p) for p in found), found
