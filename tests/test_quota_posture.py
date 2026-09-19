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


def _posture(
    state: Path,
    *,
    band="GREEN",
    band_fable=None,
    band_fable_clamped=False,
    ts=None,
    slug="ozgurbasak",
    successor="mob",
    fleet_windows=None,
    band_account=None,
    fleet_measured=None,
    **over,
):
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
            # the account's OWN reading (D-275); defaults to the band so older graders see no clause
            "band_account": band_account if band_account is not None else band,
            "hottest_fable": "five_hour",
            "band_fable": band if band_fable is None else band_fable,
            # ⚠️ goes in `active`, NOT through `**over` — that merges into `active.windows`, so a
            # test passing it as a kwarg silently exercised the UNCLAMPED path and read green
            "band_fable_clamped": band_fable_clamped,
            "band_account_fable": band_account
            if band_account is not None
            else (band if band_fable is None else band_fable),
        },
        "fleet": {
            "queue": [],
            # parameterised for C5b, which proves the hold reads this field NOT AT ALL: the band
            # in the posture is already the FLEET's (D-275), so a RED means every serving account is
            # RED and `decide()` holds regardless of any successor. An interim cut gated the hold on
            # this field; that gate is gone, and the `successor=None` on the RED fixtures below is
            # harmless residue kept as documentation of that history.
            "successor": (
                {"email": f"{successor}@ocoron.com", "slug": successor} if successor else None
            ),
            # per-window fleet readings (D-275); None keeps the bare `band X` rendering
            "windows": fleet_windows or {},
            "measured": fleet_measured,
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


def test_the_contract_line_is_rendered_byte_for_byte_on_the_clamped_fable_path_too(tmp_path):
    """D-295 — the byte-for-byte grader above had NO clamped case, so the one path where the band is
    NOT the fleet's rendered unpinned: `on <window>` carried a phrase instead of a window label and a
    trailing clause the contract did not list, and nothing went red. The contracts now state that
    path (the THAT LAST ONE span, graded three-way identical), so the line that serves it is pinned
    here in the same shape as the unclamped one."""
    state, runs = tmp_path / "state", tmp_path / "runs"
    runs.mkdir()
    t = tmp_path / "t.jsonl"
    t.write_text(json.dumps({"type": "assistant", "message": {"model": "claude-fable-5-1"}}) + "\n")
    _posture(
        state,
        band="GREEN",
        band_account="GREEN",
        band_fable="RED",
        band_fable_clamped=True,
        fleet_windows={
            "five_hour": {"utilization": 10.0, "slug": "sarp"},
            "seven_day": {"utilization": 21.0, "slug": "sarp"},
            "fable": {"utilization": 21.0, "slug": "sarp"},
        },
        fleet_measured=2,
        successor="sarp",
    )
    line = _hook(
        {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "transcript_path": str(t)},
        state=state,
        runs=runs,
    ).stdout.strip()
    assert line == (
        "QUOTA: ozgurbasak · 5h 71% (wall in ~48m at 0.60%/m) · weekly 44% (reset in 2:10) · "
        "Fable 32% · band RED on this account's own Fable window (no relief leg) "
        "(fleet-wide: 5h 10% sarp · weekly 21% sarp · Fable 21% sarp) — this account's own Fable "
        "window binds; no flip reaches another account's Fable headroom, only pinning "
        "CLAUDE_CONFIG_DIR + CLAUDE_QUOTA_HOME to a slug that has it · successor sarp"
    ), line
    # the same required tokens the unclamped line owes
    for token in ("QUOTA: ", " · band ", " · successor ", " · Fable "):
        assert token in line, token
    # and the provenance sentence the contract pins for the UNCLAMPED path must not appear here
    assert "the band is the fleet's, act on it" not in line, (
        "on the clamped path the band is the account's — the contract now says so"
    )


_FLEET = {
    "five_hour": {"utilization": 0.0, "slug": "can"},
    "seven_day": {"utilization": 31.0, "slug": "ob"},
    "fable": {"utilization": 17.0, "slug": "can"},
}


def test_prompt_line_explains_the_fleet_band_and_names_when_this_account_alone_would_read_worse(
    tmp_path,
):
    """C2b — the line reaches every RUNNING session; the contract does not (Lesson 116). A fabrik-lib
    agent with the old per-account table in context saw `weekly 89% · band GREEN`, judged the label
    wrong, and overrode it by hand all session (01M2P42QZMTX8RAQ24SCV45VSY). So the line carries the
    fleet readings behind the band and states the rule when this account's reading disagrees."""
    state = tmp_path / "state"
    _posture(state, band="GREEN", band_account="AMBER", fleet_windows=_FLEET, successor="can")
    p = _hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"}, state=state)
    line = p.stdout.strip()
    assert line == (
        "QUOTA: ozgurbasak · 5h 71% (wall in ~48m at 0.60%/m) · weekly 44% (reset in 2:10) · "
        "Fable 32% · band GREEN (fleet-wide: 5h 0% can · weekly 31% ob) — this account alone reads "
        "AMBER; the band is the fleet's, act on it · successor can"
    ), line


def test_prompt_line_names_the_window_that_binds_at_amber_and_says_nothing_extra_when_bands_agree(
    tmp_path,
):
    """C2c — at AMBER/RED the line names the fleet window that put it there (the reporter's ask);
    when the account's reading equals the fleet's there is no "alone" clause to mislead with."""
    state = tmp_path / "state"
    hot = {
        "five_hour": {"utilization": 3.0, "slug": "can"},
        "seven_day": {"utilization": 86.0, "slug": "can"},
    }
    _posture(state, band="AMBER", band_account="AMBER", fleet_windows=hot, successor="can")
    p = _hook({"hook_event_name": "UserPromptSubmit", "session_id": "s2"}, state=state)
    line = p.stdout.strip()
    assert (
        " · band AMBER on weekly (fleet-wide: 5h 3% can · weekly 86% can) · successor can" in line
    ), line
    assert "alone" not in line, line


def test_prompt_line_shows_the_fleet_fable_reading_only_on_a_fable_model(tmp_path):
    """C2d — Fable is relevant solely where the running agent is Fable (operator): the fleet Fable
    reading joins the clause only there, and the "alone" clause then compares the Fable bands."""
    state = tmp_path / "state"
    _posture(state, band="GREEN", band_fable="GREEN", band_account="GREEN", fleet_windows=_FLEET)
    doc = json.loads((state / "quota-posture.json").read_text())
    doc["active"]["band_account_fable"] = "RED"
    (state / "quota-posture.json").write_text(json.dumps(doc))
    tp = tmp_path / "t.jsonl"
    tp.write_text(
        json.dumps({"type": "assistant", "message": {"model": "claude-fable-5-1"}}) + "\n"
    )
    p = _hook(
        {"hook_event_name": "UserPromptSubmit", "session_id": "s3", "transcript_path": str(tp)},
        state=state,
    )
    line = p.stdout.strip()
    assert (
        "(fleet-wide: 5h 0% can · weekly 31% ob · Fable 17% can) — this account alone reads RED"
        in line
    ), line
    p2 = _hook({"hook_event_name": "UserPromptSubmit", "session_id": "s4"}, state=state)
    assert "Fable 17% can" not in p2.stdout and "alone" not in p2.stdout, p2.stdout


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
    _posture(state, band="RED", successor=None)
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
        # ⚠️ every case below defeated the regex the review replaced, and the suite was fully green.
        # A corpus that contains only the spellings the author thought of grades the author.
        # a QUOTED script path made the hold VANISH — no match, no deny, a new run at RED
        ('python3 "/opt/fabrik/scripts/command_run.py" start --command fabrik-spec', True),
        ("python3 '/opt/fabrik/scripts/command_run.py' start --command fabrik-spec", True),
        # a QUOTED name fell outside the value class, so the REVIEW FAMILY was denied
        ("python3 scripts/command_run.py start --command 'fabrik-review'", False),
        ('python3 scripts/command_run.py start --command "fabrik-review-scoped"', False),
        # a decoy FIRST flag beat the real one, because argparse takes the LAST and the hold took
        # the first
        (
            "python3 scripts/command_run.py start --command fabrik-review --command fabrik-spec",
            True,
        ),
        # two starts on one line cannot be blessed by one name
        (
            "python3 scripts/command_run.py start --command fabrik-review ; "
            "python3 scripts/command_run.py start --command fabrik-spec",
            True,
        ),
        # the phrase inside a quoted MESSAGE is data — denying this denied a COMMIT, which is
        # precisely what RED mandates
        ('git commit -m "ran command_run.py start for the review" -- x', False),
        ("echo 'reminder: command_run.py start --command fabrik-spec'", False),
        ("python3 scripts/command_run.py start --command=fabrik-review", False),
        ("python3 scripts/command_run.py start --command=fabrik-spec", True),
        # ⚠️ and these defeated the FIRST tokenised version, which pre-split on `[;&|\n]+` before
        # shlex — severing any quote holding one of those characters. The half carrying the
        # filename then failed to parse and fell to the fail-closed arm, so the very commit the
        # previous fix claimed to unblock was denied again by a new route.
        ('git commit -m "fix(run): start; then done" -- scripts/command_run.py', False),
        ('git commit -m "fix: guard start && done" -- scripts/command_run.py', False),
        ('git commit -m "docs: the start|done pair" -- scripts/command_run.py', False),
        # a backslash continuation is how a real start is actually written, and `\n` was in that
        # split class, so the review-family start this hold's own escape depends on was denied
        (
            "python3 scripts/command_run.py start \\\n  --command fabrik-review-scoped \\\n"
            '  --phases 1 --terminal "x"',
            False,
        ),
        (
            "python3 scripts/command_run.py start \\\n  --command fabrik-spec \\\n  --phases 3",
            True,
        ),
        # a separator INSIDE a quoted argument is data; the start after it is still a start
        ('echo "a;b" ; python3 scripts/command_run.py start --command fabrik-spec', True),
        # a substituted path carries its metacharacters on the token
        ("python3 $(echo scripts/command_run.py) start --command fabrik-spec", True),
        ("python3 `echo scripts/command_run.py` start --command fabrik-spec", True),
        # a longer filename that merely ENDS with the script's name is not the script
        ("python3 scripts/my_command_run.py start --command fabrik-spec", False),
        # ⚠️ round 3. `shlex` splits on WHITESPACE only, so an unspaced operator rides on the verb
        # and an exact comparison failed — the hold VANISHED for the spellings an agent writes by
        # habit, not by evasion. Same class as the quoted path, three rewrites later.
        ("python3 scripts/command_run.py start;echo done", True),
        ("python3 scripts/command_run.py start&&echo done", True),
        ("python3 scripts/command_run.py start>/tmp/log", True),
        ("(python3 scripts/command_run.py start)", True),
        # the name must bind to THIS start. Accumulating names across the whole line made the
        # segmentation pointless in BOTH directions:
        (
            "python3 scripts/command_run.py done --command fabrik-review --evidence x && "
            "python3 scripts/command_run.py start --phases 2 --terminal t",
            True,  # the start is UNNAMED; the name belongs to the `done`
        ),
        (
            "python3 scripts/command_run.py start --command fabrik-review --phases 2 && "
            "python3 scripts/command_run.py done --command fabrik-deploy --evidence x",
            False,  # the START is review-family; the `done` afterwards is irrelevant
        ),
        ("python3 scripts/command_run.py start --phases 2 ; echo --command=fabrik-review", True),
        # the `--command` VALUE needs the same decoration cut as the script token, or the escape
        # hatch denies itself: the name read as `fabrik-review-scoped)`
        ("(python3 scripts/command_run.py start --command fabrik-review-scoped)", False),
        ("(python3 scripts/command_run.py start --command=fabrik-review)", False),
        # a `-c` payload is ONE token, so the basename never reached the comparison
        ('bash -c "python3 scripts/command_run.py start --command fabrik-spec"', True),
        ("sh -c 'python3 scripts/command_run.py start --command fabrik-review'", False),
        # ⚠️ and the fix for THAT must not re-expose a quoted message: only a `-c` argument is
        # re-parsed, never any token that merely contains the script name
        ('git commit -m "ran command_run.py start --command fabrik-spec" -- x', False),
        # a trailing comment with an apostrophe is an unbalanced quote to shlex; the retry reads it,
        # and an unreadable line ALLOWS rather than denying the commit RED mandates
        ('git commit -m "msg" -- scripts/command_run.py  # don\'t forget', False),
        # ⚠️ the heavy review. An unquoted NEWLINE yields no shlex token at all, so a `--command` on
        # the NEXT LINE bound to the unnamed start above it — the cheapest bypass on the board,
        # since it is what a multi-line Bash script has by default. The name binding now consumes
        # argv the way argparse does and stops at the first bare token.
        ("python3 scripts/command_run.py start --phases 2\necho --command fabrik-review", True),
        ("python3 scripts/command_run.py start --phases 2\necho --command=fabrik-review", True),
        # a COMBINED short flag is the habitual spelling of a payload; an exact-string set matched
        # none of them
        ('bash -lc "python3 scripts/command_run.py start --command fabrik-spec"', True),
        ('bash -ec "python3 scripts/command_run.py start --command fabrik-spec"', True),
        ("sh -eu -c 'python3 scripts/command_run.py start --command fabrik-review'", False),
        # a bare MENTION as an argument is not an invocation; matching it denied read-only commands,
        # which is the expensive direction
        ("grep -c command_run.py start", False),
        ('git -c core.editor="scripts/command_run.py start" rebase --continue', False),
        # ⚠️ the SLASH spelling, which is how the contract, the corpus and every agent writes these
        # commands — and it was DENIED, because `REVIEW_FAMILY` holds them bare. The fourth time
        # this escape hatch broke, and the first in a spelling the documentation itself uses. The
        # deny text rendered `Starting //fabrik-review`, the code admitting its own mismatch.
        ("python3 scripts/command_run.py start --command /fabrik-review --phases 3", False),
        ("python3 scripts/command_run.py start --command /fabrik-review-scoped", False),
        ("python3 scripts/command_run.py start --command=/fabrik-review", False),
        # ⚠️ a TRAILING slash is denied ON PURPOSE, and this is the case that documents why. I
        # widened `_command_name` to `strip("/")` so these two would pass, and a delta round proved
        # the trade was backwards: `command_run.py` records the name with `lstrip("/")`, so the
        # start was ALLOWED while the record landed as `fabrik-review/` — off-family for every
        # consumer, so the close skipped its coverage window and Stop still called the session
        # unreviewed. A loud deny at the start beats a silent failure to count at the end. Closing
        # it for real means making the RECORDER canonical; that file is fleet-synced and another
        # plan's lock owns it, so it is filed, not reached into.
        ("python3 scripts/command_run.py start --command /fabrik-review/", True),
        ("python3 scripts/command_run.py start --command fabrik-review-scoped/", True),
        ("python3 scripts/command_run.py start --command /fabrik-spec --phases 3", True),
        # ⚠️ A QUOTED shell operator inside the value is a KNOWN, RECORDED GAP — these cases pin
        # what the hook does today, which is NOT what it should do. shlex discards quoting, so the
        # hook cannot tell `--command 'fabrik-review;x'` (bash passes it whole; the recorder files
        # `fabrik-review;x`, off-family) from `--command fabrik-review;x` (bash cuts at the `;`).
        # `_cut` guesses the second, so the first is ALLOWED at RED and then counts as no review —
        # confirmed end-to-end against a real recorder. The guess is deliberate and it is the RIGHT
        # way round: dropping `_cut` fixes this and breaks the far likelier subshell spelling
        # `(… --command fabrik-review-scoped)`, where the `)` is bash syntax and dropping the cut
        # DENIES a legitimate review start. Punctuation-aware tokenisation resolves both in theory
        # and was executed here: it breaks the `$(echo …)` bypass this corpus already guards. So the
        # real fix is a fourth rewrite of the predicate, and each of its three rewrites introduced a
        # new defect — it is a named docs/STRATEGIC_BACKLOG.md row, not an end-of-run change.
        (
            "python3 scripts/command_run.py start --command 'fabrik-review;x' --phases 1 --terminal p",
            False,
        ),
        (
            "python3 scripts/command_run.py start --command='fabrik-review;x' --phases 1 --terminal p",
            False,
        ),
        # an INTERIOR slash is a PATH, not this command, and must stay denied — the strip must not
        # widen into a basename match
        ("python3 scripts/command_run.py start --command /opt/x/fabrik-review", True),
    ],
)
def test_red_holds_a_new_command_start_but_not_the_review_that_finishes(tmp_path, command, denied):
    """C5 — RED stops a FRESH round on something new; the mandated review of the change you are
    checkpointing is the one start that stays allowed, in every spelling the corpus uses."""
    state, runs = tmp_path / "state", tmp_path / "runs"
    runs.mkdir()
    _posture(state, band="RED", successor=None)
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

    _posture(state, band="RED", successor=None)
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
    _posture(state, band="GREEN", band_fable="RED", successor=None)
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


def test_the_two_notifier_readers_answer_about_the_same_file(tmp_path, monkeypatch):
    """The notifier seam, graded where it can DISCRIMINATE.

    `_tick_telegram` and `_notify_failure_reason` must resolve the SAME notifier. The existing
    grader for the reason string patches `Path.home()` AND sets `CLAUDE_SOUND_SH` to the same file,
    so it passes identically with the seam half-applied — it cannot see the defect. Here the two
    deliberately DISAGREE: the seam points at a file that does not exist while home holds one that
    does, which is exactly the production shape (a custom notifier) that made one function report
    "absent" while the other printed the long "could not be confirmed" list for the same tick.
    """
    import importlib.util

    home = tmp_path / "home"
    (home / ".claude" / "bin").mkdir(parents=True)
    (home / ".claude" / "bin" / "claude-sound.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("CLAUDE_SOUND_SH", str(tmp_path / "nowhere" / "custom-notifier.sh"))

    spec = importlib.util.spec_from_file_location(
        "cr_notifier_probe", HOOK.parent / "claude_rotate.py"
    )
    cr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cr)

    assert not cr._sound_script().is_file(), "the seam must win over home"
    assert cr._tick_telegram("k", "m") is False
    assert "unavailable" in cr._notify_failure_reason(), (
        "the two readers disagree: one says the notifier is absent, the other stats a different file"
    )


def test_amber_is_announced_again_after_a_red_excursion(tmp_path):
    """C9b — a session that drops to RED and comes back to AMBER hears it again.

    The marker only ever accumulated, so the second AMBER was silent — and nothing pruned these
    files either: one per session per band, forever, in the state dir the tick reads, with no owner.
    Clearing on the band change does both jobs, and it does them exactly when the fact stops holding.
    """
    state, runs = tmp_path / "state", tmp_path / "runs"
    runs.mkdir()
    call = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "s1"}

    _posture(state, band="AMBER")
    assert "additionalContext" in _hook(call, state=state, runs=runs).stdout
    assert _hook(call, state=state, runs=runs).stdout.strip() == "", "said twice in one band"

    _posture(state, band="RED", successor=None)
    _hook(call, state=state, runs=runs)
    assert not list(state.glob("quota-posture-said-*")), "the marker outlived its band"

    _posture(state, band="AMBER")
    assert "additionalContext" in _hook(call, state=state, runs=runs).stdout, (
        "AMBER after a RED excursion was never announced again"
    )


def test_a_stale_run_record_does_not_license_fan_out_at_red(tmp_path):
    """C3b — a record has to be LIVE, not merely present.

    An abandoned `running` record from a crashed session used to keep the `Agent` carve-out open
    forever. The Stop hook applies a 12-hour bound to the same file; so does this now.
    """
    state, runs = tmp_path / "state", tmp_path / "runs"
    runs.mkdir()
    _posture(state, band="RED", successor=None)
    rec = runs / "s1.json"
    rec.write_text(json.dumps({"state": "running"}), encoding="utf-8")
    call = {"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "s1"}
    assert _hook(call, state=state, runs=runs).stdout.strip() == "", (
        "a fresh record keeps its seats"
    )

    old = time.time() - (13 * 3600)
    os.utime(rec, (old, old))
    out = _hook(call, state=state, runs=runs).stdout
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny", out

    # the bound is the Stop hook's own env key, so raising it there raises it here
    out = _hook(call, state=state, runs=runs, extra_env={"COMMAND_RUN_STALE_H": "24"}).stdout
    assert out.strip() == "", "a raised bound must keep the record's seats"
    # ⚠️ but its "never trap me" does NOT disable this: a trap that holds YOU is not a carve-out
    # that holds the FLEET, and a non-positive value here keeps the default rather than becoming
    # an abandoned record licensing unlimited fan-out at RED forever
    for disable in ("0", "-1", "nonsense"):
        out = _hook(call, state=state, runs=runs, extra_env={"COMMAND_RUN_STALE_H": disable}).stdout
        assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny", (disable, out)


def test_the_deny_names_the_window_that_binds_this_session(tmp_path):
    """C3c — the deny message is the operator-facing evidence, so it must name the right window.

    It used to infer Fable-ness by comparing `band == band_fable`, which is ALWAYS true at RED:
    `band_fable` is the hottest INCLUDING Fable. Every RED deny therefore reported the Fable window,
    to Opus and Sonnet sessions alike.
    """
    state, runs = tmp_path / "state", tmp_path / "runs"
    runs.mkdir()
    # ⚠️ The two hottest keys must DIFFER or this grader cannot fail: `_deny_reason` branches only to
    # choose between them, so a fixture where both are `five_hour` renders byte-identically on both
    # sides and a revert to the old always-true inference sails through. The first version of this
    # test did exactly that, and its own comment said so without fixing it.
    doc = _posture(state, band="RED", band_fable="RED", successor=None)
    doc["active"]["hottest_fable"] = "fable"
    doc["active"]["windows"]["fable"]["utilization"] = 97.0
    (state / "quota-posture.json").write_text(json.dumps(doc), encoding="utf-8")
    call = {"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "s1"}

    reason = json.loads(_hook(call, state=state, runs=runs).stdout)["hookSpecificOutput"][
        "permissionDecisionReason"
    ]
    assert "five_hour" in reason and "fable" not in reason, reason
    assert "71%" in reason and "97%" not in reason, reason

    t = tmp_path / "t.jsonl"
    t.write_text(
        json.dumps({"type": "assistant", "message": {"model": "claude-fable-5-1"}}),
        encoding="utf-8",
    )
    reason = json.loads(_hook(dict(call, transcript_path=str(t)), state=state, runs=runs).stdout)[
        "hookSpecificOutput"
    ]["permissionDecisionReason"]
    assert "fable" in reason and "97%" in reason, reason


def test_the_session_model_is_the_last_assistant_entry_not_the_last_model_string(tmp_path):
    """C8b — a structured tool result AFTER the final assistant turn can carry a model of its own.

    The substring version picked it up, so an Opus session whose last tool result mentioned a Fable
    model was banded on the Fable window and could be denied at RED on a window that does not bind
    it. The scan is line-wise and reads only entries whose `type` is `assistant`.
    """
    mod = _load()
    t = tmp_path / "t.jsonl"
    t.write_text(
        json.dumps({"type": "assistant", "message": {"model": "claude-opus-5"}})
        + "\n"
        + json.dumps({"type": "user", "toolUseResult": {"model": "claude-fable-5-1"}})
        + "\n",
        encoding="utf-8",
    )
    assert mod._session_model(str(t)) == "claude-opus-5"


def test_a_non_finite_timestamp_is_unreadable_never_eternally_fresh(tmp_path):
    """C1b — a posture whose `ts` is a bare NaN must read as UNREADABLE, not as fresh forever.

    `isinstance(nan, float)` is True and `now - nan` is `nan`, and `nan > bound` is False — so the
    staleness check silently passed and the hook rendered an arbitrarily old posture as current on
    every prompt, with `posture unavailable` unable to fire. That is worse than a crash: a
    permanently confident wrong answer about the one thing this line exists to report.
    """
    mod = _load()
    state = tmp_path / "state"
    state.mkdir()
    for raw in (
        '{"schema": 1, "ts": NaN}',
        '{"schema": 1, "ts": Infinity}',
        '{"schema": 1, "ts": -Infinity}',
        '{"schema": 1, "ts": true}',
    ):
        (state / "quota-posture.json").write_text(raw, encoding="utf-8")
        p = _hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"}, state=state)
        assert "posture unavailable (unreadable)" in p.stdout, (raw, p.stdout)
    # and the hook's reader agrees with the rotation script's, which refuses the same constants
    import os as _os

    _os.environ["ROTATE_STATE_DIR"] = str(state)
    try:
        assert mod._load_posture(time.time()) == (None, "unreadable")
    finally:
        _os.environ.pop("ROTATE_STATE_DIR", None)


def test_malformed_payloads_never_block(tmp_path):
    """C10 — rc 0 and silence on anything we cannot parse: never block on our own defect."""
    state = tmp_path / "state"
    _posture(state, band="RED", successor=None)
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


def test_the_hook_and_the_recorder_agree_on_the_name_a_start_will_carry(tmp_path):
    """C15c — the SET was never the whole parity, and the half it left open is the half that broke.

    `_command_name` exists to answer ONE question: what will the RECORD say? A delta round caught
    this module widened to `strip("/")` — the sets still matched, the set assertion still passed,
    and the hook blessed a start whose recorded name no consumer would recognise.

    ⚠️ The oracle is the RECORDER ITSELF, driven for real, not a restatement of its rule. The first
    version of this grader asserted against a hardcoded `raw.lstrip("/")`, and the very next seat
    showed why that is worthless: mutate `command_run.py` instead of the hook and the grader stays
    green through the identical divergence. That is not hypothetical here — this run FILED a request
    to infra to make the recorder canonical (`strip("/")`), and when it lands, a literal oracle would
    keep passing while the hook began fail-CLOSED denying an in-family review start. So this runs the
    real `command_run.py start` in an isolated `COMMAND_RUN_DIR` and reads the name off disk: it
    fails whichever side moves.
    """
    mod = _load()
    for i, raw in enumerate(
        (
            "/fabrik-review",
            "fabrik-review/",
            "//fabrik-review//",
            "/fabrik-review-scoped",
            "/opt/x/fabrik-review",
            "fabrik-spec",
            # ⚠️ these three are NOT padding. A round proved the six-spelling set sleeps through two
            # whole mutant classes that only these catch: a `.strip()` added to either side's
            # normalisation (likely — `command_run.py` strips `surface` (:2519) while `command`
            # (:2501) takes only `lstrip("/")`), and removal of the `or None` collapse, which only
            # the empty-ish spellings exercise. Dropping them was an unremarked coverage cut.
            "/",
            "",
            " /fabrik-review",
        )
    ):
        runs = tmp_path / f"runs{i}"
        runs.mkdir()
        # ⚠️ `start` writes TWO places: the run record under `COMMAND_RUN_DIR` and an event line
        # under `KAIZEN_EVENTS_DIR`. conftest pins the second for the whole suite, so this is safe
        # today — but a grader that builds its own env and pins only one of two write channels is
        # the exact shape that once wrote fabricated events into the operator's REAL log. Pinned
        # here so the isolation is a property of this test, not of a fixture it never names.
        env = {
            **os.environ,
            "COMMAND_RUN_DIR": str(runs),
            "KAIZEN_EVENTS_DIR": str(tmp_path / f"events{i}"),
        }
        proc = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parents[1] / "scripts" / "command_run.py"),
                "start",
                "--command",
                raw,
                "--phases",
                "1",
                "--terminal",
                "parity probe",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert proc.returncode == 0, f"{raw!r}: start failed: {proc.stderr[-400:]}"
        files = list(runs.glob("*.json"))
        assert files, f"{raw!r}: the recorder wrote no record"
        recorded = json.loads(files[0].read_text()).get("command")
        assert mod._command_name(raw) == (recorded or None), (
            f"{raw!r}: the hook says {mod._command_name(raw)!r} but the recorder wrote "
            f"{recorded!r} — a start the hook blesses would not count as that command"
        )


def test_a_boolean_utilization_in_a_fleet_window_is_neither_compared_nor_named(tmp_path):
    """C2e — closing seat 3: a JSON `true` survives `_load_posture` (it guards NaN/Infinity, not
    booleans) and `True == 1` outranks every real reading in a `max()`, so the deny reason named a
    window rendered as `—` and asserted "no flip relieves this". The comparison and the rendering
    now share `_util`, the guard `_pct` already applies, so a value that cannot be printed cannot
    win the comparison either."""
    state = tmp_path / "state"
    fw = {
        "five_hour": {"utilization": 0.5, "slug": "can"},
        "seven_day": {"utilization": True, "slug": "ob"},
    }
    _posture(state, band="AMBER", band_account="AMBER", fleet_windows=fw, successor="can")
    p = _hook({"hook_event_name": "UserPromptSubmit", "session_id": "b1"}, state=state)
    line = p.stdout.strip()
    assert "band AMBER on 5h (fleet-wide: 5h 0% can)" in line, line
    assert "weekly —" not in line and "on weekly" not in line, line
    _posture(state, band="RED", band_account="RED", fleet_windows=fw, successor=None)
    p = _hook(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Agent",
            "session_id": "b2",
            "tool_input": {},
        },
        state=state,
        runs=tmp_path / "runs",
    )
    reason = json.loads(p.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "serve five_hour is can at 0%" in reason, reason
    assert "at —" not in reason, reason


# --- C5b: the hold trusts the FLEET band and nothing softens it -------------------------------


@pytest.mark.parametrize("successor", ["can", "ozgurbasak", None])
def test_red_holds_whatever_the_successor_field_says(tmp_path, successor):
    """C5b — the band in the posture is already the FLEET's (`claude_rotate.py::_fleet_readings`,
    per window, coolest serving account), so a RED means every account that could serve the hot
    window is RED too. The hold therefore binds regardless of `fleet.successor`: a successor at 89%
    weekly is a flip, not relief. An earlier cut gated the hold on that field as a stopgap for a
    per-account band; the operator's ruling (2026-09-17: fleet-wide, session and weekly combined,
    Fable where the agent is Fable) is honoured at the WRITER, and the hook trusts the band.
    """
    state, runs = tmp_path / "state", tmp_path / "runs"
    runs.mkdir()
    _posture(state, band="RED", successor=successor)
    p = _hook(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Agent",
            "session_id": "fleet",
            "tool_input": {},
        },
        state=state,
        runs=runs,
    )
    assert p.stdout.strip(), f"successor={successor!r}: a fleet RED must hold"
    assert json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


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


def test_the_tick_warns_when_the_posture_hook_is_not_wired(tmp_path, monkeypatch):
    """C14 — the tick names the gap, because nothing else can.

    Without the hook the posture is written every cycle and read by nobody, and the session sees NO
    `QUOTA:` line — which the contract tells the agent means exactly this. Advisory, never a block.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "cr_wiring_probe", HOOK.parent / "claude_rotate.py"
    )
    cr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cr)

    # the hook is looked up through the `/opt` seam, so an ABSENT hook warns about nothing —
    # assert that first, then install one inside the pinned dir and watch the warning appear
    assert cr._posture_hook_wiring_warnings() == [], "no hook installed ⇒ nothing to nag about"
    installed = Path(os.environ["FABRIK_OPT_DIR"]) / "fabrik" / "scripts" / "sysadmin"
    installed.mkdir(parents=True, exist_ok=True)
    (installed / "quota_posture_hook.py").write_text("", encoding="utf-8")

    files = []
    for i in range(6):
        p = tmp_path / f"s{i}" / "settings.json"
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({"hooks": {}}), encoding="utf-8")
        files.append(p)
    monkeypatch.setenv("QUOTA_POSTURE_SETTINGS", os.pathsep.join(str(p) for p in files))

    warns = cr._posture_hook_wiring_warnings()
    assert len(warns) == 1 and "6 of 6" in warns[0], warns
    assert "--install" in warns[0], "the warning must name its own remedy"

    mod = _load()
    mod.install(files)
    assert cr._posture_hook_wiring_warnings() == [], "a wired fleet must warn about nothing"

    # one file unwired again ⇒ the count is the population, not a bare number
    files[2].write_text(json.dumps({"hooks": {}}), encoding="utf-8")
    warns = cr._posture_hook_wiring_warnings()
    assert len(warns) == 1 and "1 of 6" in warns[0], warns


def test_the_installer_never_claims_ok_about_a_file_it_did_not_fix(tmp_path):
    """C11c — an event key holding a non-list is REPORTED, not silently skipped.

    `setdefault` returns the EXISTING value when the key is present, so the isinstance guard used to
    `continue` without recording the event: the file then said `OK (already wired)` on every later
    run while `check()` correctly said MISSING forever. An installer that reports OK about something
    it did not fix is worse than one that crashes — the operator has no reason to look again.
    """
    mod = _load()
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"hooks": {"UserPromptSubmit": "not-a-list"}}), encoding="utf-8")

    first = mod.install([p])[0][1]
    assert "SKIPPED" in first and "UserPromptSubmit" in first, first
    second = mod.install([p])[0][1]
    assert "OK (already wired)" not in second, (
        "the second run claimed OK about the event it never fixed"
    )
    assert "SKIPPED" in second and "UserPromptSubmit" in second, second
    # check() is the honest one and must still disagree with nothing
    assert "MISSING" in mod.check([p])[0][1]
    # the operator's own value is never rewritten
    assert json.loads(p.read_text())["hooks"]["UserPromptSubmit"] == "not-a-list"


def test_two_installs_in_one_second_keep_both_backups(tmp_path, monkeypatch):
    """C11d — the backup name is unique per process, because it is the only undo on offer.

    It carried a second-resolution stamp while the staging file was already pid-qualified, so two
    installs of one file inside the same wall-clock second destroyed the earlier backup silently.
    """
    mod = _load()
    monkeypatch.setattr(mod.time, "strftime", lambda *_a, **_k: "FROZEN")
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"hooks": {}}), encoding="utf-8")
    mod.install([p])
    p.write_text(json.dumps({"hooks": {}, "marker": "second"}), encoding="utf-8")
    real_pid = os.getpid
    monkeypatch.setattr(mod.os, "getpid", lambda: real_pid() + 1)
    mod.install([p])
    backups = sorted(q.name for q in tmp_path.glob("settings.json.backup.*"))
    assert len(backups) == 2, backups


def test_the_settings_denominator_counts_distinct_files(tmp_path, monkeypatch):
    """C11e — a repeated path would inflate `--check`'s own denominator and print one file twice.

    That is the count-without-its-denominator defect this repo's contract names, committed by the
    very thing that reports the count.
    """
    mod = _load()
    a = tmp_path / "a.json"
    a.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("QUOTA_POSTURE_SETTINGS", os.pathsep.join([str(a), "", str(a)]))
    assert mod.settings_files() == [a], mod.settings_files()


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
    # the fleet root is read from `CLAUDE_FLEET_ROOT` now, the seam `_fleet_root()` already used —
    # hardcoding `~/.claude-fleet` made the installer and the tick's advisory blind to a relocated
    # root, reporting nothing wrong while every per-slug window was unwired. The conftest pins it,
    # and a test that wants its own fleet names it, which is what the pin's composability is for.
    monkeypatch.setenv("CLAUDE_FLEET_ROOT", str(fleet))
    found = mod.settings_files()
    assert len(found) == 6, found
    assert not any("active" in str(p) for p in found), found


def test_prompt_line_names_a_required_window_nobody_serves(tmp_path):
    """C2f — Delta 8 seat A #2: the injected line printed `weekly 81% … band GREEN` with nothing
    to explain either; an unserved REQUIRED window is now named, because it is why the band is RED."""
    state = tmp_path / "state"
    fw = {"seven_day": {"utilization": 30.0, "slug": "intel"}}
    _posture(state, band="RED", band_account="GREEN", fleet_windows=fw, successor=None)
    p = _hook({"hook_event_name": "UserPromptSubmit", "session_id": "u1"}, state=state)
    line = p.stdout.strip()
    # the window the band is ON is the one nobody serves, never the hottest numeric one — the
    # first cut of this grader pinned `on weekly` here (Delta 9 seat C)
    assert "band RED on 5h (fleet-wide: 5h — nobody serves it · weekly 30% intel)" in line, line


def test_prompt_line_explains_maximal_scarcity_when_the_fleet_map_is_empty(tmp_path):
    """C2h — Delta 9 seat A F2: both accounts measured, neither serving — the map is `{}` and the
    line rendered no fleet clause at all, in the state the clause exists to explain. With nobody
    measured the same `{}` is a blackout and the clause stays absent (C2 pins that)."""
    state = tmp_path / "state"
    _posture(
        state, band="RED", band_account="GREEN", fleet_windows={}, fleet_measured=2, successor=None
    )
    p = _hook({"hook_event_name": "UserPromptSubmit", "session_id": "u1"}, state=state)
    line = p.stdout.strip()
    assert (
        "band RED on 5h and weekly (fleet-wide: 5h — nobody serves it · weekly — nobody serves it)"
        in line
    ), line
    _posture(
        state, band=None, band_account=None, fleet_windows={}, fleet_measured=0, successor=None
    )
    p = _hook({"hook_event_name": "UserPromptSubmit", "session_id": "u1"}, state=state)
    assert "fleet-wide" not in p.stdout, p.stdout


def test_the_deny_reason_names_the_window_nobody_serves(tmp_path):
    """C2j — Delta 10 seat A #1/#2: the deny reason is the message a HELD agent reads, and it was
    the one consumer the `measured` fix skipped — at maximal scarcity it said nothing fleet-wide,
    and with one window unserved it named the OTHER window, at 12%, as why no flip relieves."""
    state, runs = tmp_path / "state", tmp_path / "runs"
    runs.mkdir()
    call = {"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "s1"}
    _posture(
        state, band="RED", band_account="GREEN", fleet_windows={}, fleet_measured=2, successor=None
    )
    reason = json.loads(_hook(call, state=state, runs=runs).stdout)["hookSpecificOutput"][
        "permissionDecisionReason"
    ]
    assert "NO account can serve 5h and weekly" in reason, reason
    fw = {"seven_day": {"utilization": 12.0, "slug": "intel"}}
    _posture(
        state, band="RED", band_account="GREEN", fleet_windows=fw, fleet_measured=1, successor=None
    )
    reason = json.loads(_hook(call, state=state, runs=runs).stdout)["hookSpecificOutput"][
        "permissionDecisionReason"
    ]
    assert "NO account can serve 5h," in reason and "at 12%" not in reason, reason
    _posture(
        state, band="RED", band_account="GREEN", fleet_windows={}, fleet_measured=0, successor=None
    )
    reason = json.loads(_hook(call, state=state, runs=runs).stdout)["hookSpecificOutput"][
        "permissionDecisionReason"
    ]
    assert "Fleet-wide" not in reason, reason
    # the deny reason's OWN copy of the bool exclusion: a JSON `true` is not a count here either —
    # C2i drives the prompt line only, and this is the message a held agent reads (seat D #2)
    _posture(
        state,
        band="RED",
        band_account="GREEN",
        fleet_windows={},
        fleet_measured=True,
        successor=None,
    )
    reason = json.loads(_hook(call, state=state, runs=runs).stdout)["hookSpecificOutput"][
        "permissionDecisionReason"
    ]
    assert "Fleet-wide" not in reason, reason


def test_a_bool_measured_is_not_a_count_for_the_hook(tmp_path):
    """C2i — Delta 10 seat C: the hook's own copy of the bool-exclusion on `measured` had no
    grader (the writer's did); a JSON `true` must fall back to the map's truthiness, never read
    as 1 measured account."""
    state = tmp_path / "state"
    _posture(
        state,
        band="RED",
        band_account="GREEN",
        fleet_windows={},
        fleet_measured=True,
        successor=None,
    )
    p = _hook({"hook_event_name": "UserPromptSubmit", "session_id": "u1"}, state=state)
    assert "fleet-wide" not in p.stdout and "nobody serves it" not in p.stdout, p.stdout


def test_prompt_line_names_both_required_windows_when_nobody_serves_either(tmp_path):
    """C2g — Delta 9 seat C #3: with BOTH required windows unserved the line named no window at
    all (`hottest` was only ever set on a numeric reading); the contract says RED names the
    window that binds, and here both do."""
    state = tmp_path / "state"
    fw = {"fable": {"utilization": 10.0, "slug": "intel"}}
    _posture(state, band="RED", band_account="GREEN", fleet_windows=fw, successor=None)
    p = _hook({"hook_event_name": "UserPromptSubmit", "session_id": "u1"}, state=state)
    line = p.stdout.strip()
    assert (
        "band RED on 5h and weekly (fleet-wide: 5h — nobody serves it · weekly — nobody serves it)"
        in line
    ), line


def test_a_clamped_fable_band_explains_itself_instead_of_naming_a_cool_window(tmp_path):
    """Round 1 seat A, F1/F2/F3 — the Fable clamp made the band come from THIS ACCOUNT's own Fable
    window, a figure that is not in `fleet.windows` at all. Every consumer that explains a band
    from the fleet readings then explained the wrong thing: the line printed `band RED on weekly`
    while weekly sat at 21%, the deny text told a held agent "the coolest account that can still
    serve seven_day is sarp at 21%, so no flip relieves this" about a window a flip WOULD relieve,
    and the provenance sentence asserted "the band is the fleet's, act on it" about a band that is
    the account's. All three are the Delta 9 seat C class, one window further out."""
    state, runs = tmp_path / "state", tmp_path / "runs"
    runs.mkdir()
    t = tmp_path / "t.jsonl"
    t.write_text(json.dumps({"type": "assistant", "message": {"model": "claude-fable-5-1"}}) + "\n")
    fw = {
        "five_hour": {"utilization": 10.0, "slug": "sarp"},
        "seven_day": {"utilization": 21.0, "slug": "sarp"},
        "fable": {"utilization": 21.0, "slug": "sarp"},
    }
    _posture(
        state,
        band="GREEN",
        band_account="AMBER",
        band_fable="RED",
        band_fable_clamped=True,
        fleet_windows=fw,
        fleet_measured=2,
        successor="sarp",
    )
    line = _hook(
        {"hook_event_name": "UserPromptSubmit", "session_id": "s9", "transcript_path": str(t)},
        state=state,
        runs=runs,
    ).stdout
    assert "on weekly" not in line, f"a cool window must not be named as what binds: {line}"
    assert "this account's own Fable window (no relief leg)" in line, line
    assert "the band is the fleet's, act on it" not in line, (
        "false provenance: on the clamped path the band is the ACCOUNT's"
    )
    assert "only pinning" in line, "the line must name the one remedy that reaches Fable headroom"

    reason = json.loads(
        _hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Agent",
                "session_id": "s9",
                "transcript_path": str(t),
            },
            state=state,
            runs=runs,
        ).stdout
    )["hookSpecificOutput"]["permissionDecisionReason"]
    assert "at 21%, so no flip relieves this" not in reason, (
        f"the deny must not cite a window a flip WOULD relieve: {reason}"
    )
    assert "relief leg flips on the 5h and weekly windows only" in reason, reason
    assert "fleet-wide —" not in reason, "the header must not claim a fleet-wide band"

    # and the UNCLAMPED path is untouched: the fleet's own explanation still stands
    _posture(
        state,
        band="RED",
        band_account="GREEN",
        band_fable="RED",
        band_fable_clamped=False,
        fleet_windows={"seven_day": {"utilization": 95.0, "slug": "sarp"}},
        fleet_measured=2,
        successor=None,
    )
    line2 = _hook(
        {"hook_event_name": "UserPromptSubmit", "session_id": "s9", "transcript_path": str(t)},
        state=state,
        runs=runs,
    ).stdout
    assert "own Fable window" not in line2, "the clamped wording must not leak onto the fleet path"


# --- the stamp TIER (D-306): the warning tier is this hook's to announce -------------------------


def test_the_prompt_line_nudges_a_checkpoint_at_the_warning_tier(tmp_path):
    """The turn boundary is the only moment an agent can checkpoint BEFORE it is denied. At the
    `urgent-90` tier nothing is held yet — `quota_stop.py` allows — so this line is the warning
    that buys the graceful stop the runway exists for."""
    state = tmp_path / "state"
    _posture(state)
    (state / "fleet-exhausted").write_text("0\nurgent-90\n")
    out = _hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"}, state=state).stdout
    assert "QUOTA:" in out, out
    assert "checkpoint" in out.lower(), f"the warning tier must ask for a checkpoint: {out!r}"

    # at the WALL the hold speaks, not this line — no duplicate instruction
    (state / "fleet-exhausted").write_text("0\nwalled\n")
    walled = _hook({"hook_event_name": "UserPromptSubmit", "session_id": "s2"}, state=state).stdout
    assert "checkpoint" not in walled.lower(), f"the wall is quota_stop's to announce: {walled!r}"

    (state / "fleet-exhausted").unlink()
    clear = _hook({"hook_event_name": "UserPromptSubmit", "session_id": "s3"}, state=state).stdout
    assert "checkpoint" not in clear.lower(), clear


def test_the_pretooluse_leg_defers_only_to_a_real_wall(tmp_path):
    """The leg goes silent while the stamp stands because `quota_stop.py` is denying. At the
    warning tier it is NOT denying — so a genuine fleet RED would otherwise pass BOTH hooks
    unheld, which is the gap the tier split opens if this site is left reading `.exists()`."""
    state = tmp_path / "state"
    _posture(state, band="RED", successor=None)
    payload = {
        "hook_event_name": "PreToolUse",
        "session_id": "s1",
        "tool_name": "Agent",
        "tool_input": {"prompt": "go"},
    }
    (state / "fleet-exhausted").write_text("0\nurgent-90\n")
    warn = _hook(payload, state=state, runs=tmp_path / "runs").stdout
    assert "deny" in warn, f"a fleet RED must still be held when nothing else is holding: {warn!r}"

    (state / "fleet-exhausted").write_text("0\nwalled\n")
    wall = _hook(payload, state=state, runs=tmp_path / "runs").stdout
    assert wall.strip() == "", f"at the wall this hook says nothing — quota_stop owns it: {wall!r}"


def test_the_posture_hooks_tier_reader_agrees_with_the_tick_and_the_stop_hook(tmp_path):
    """Three copies of one reader now decide whether the fleet is held. Grade all three against
    the same bytes — a copy that drifts makes the band and the hold disagree about the wall."""
    mod = _load()
    root = Path(__file__).resolve().parents[1]
    others = []
    for name, rel in (
        ("tier_probe_tick", "scripts/sysadmin/claude_rotate.py"),
        ("tier_probe_stop", ".claude/hooks/quota_stop.py"),
    ):
        spec = importlib.util.spec_from_file_location(name, root / rel)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        others.append(m)
    s = tmp_path / "fleet-exhausted"
    for body in ("0", "0\nwalled\n", "0\nurgent-90\n", "", "x\nurgent-90", "0\nnonsense\n", "0\n"):
        s.write_text(body)
        got = [mod._stamp_tier(s)] + [m._stamp_tier(s) for m in others]
        assert len(set(got)) == 1, f"readers disagree on {body!r}: {got}"
    missing = tmp_path / "absent"
    assert {mod._stamp_tier(missing)} | {m._stamp_tier(missing) for m in others} == {"walled"}


def test_the_checkpoint_clause_does_not_claim_nothing_is_held(tmp_path):
    """This hook's own PreToolUse leg denies `Agent` at band RED — and band RED with no successor
    IS the state that arms `urgent-90`. The clause claimed "nothing is held yet" in exactly that
    state, contradicting the denial the same hook issues on the next tool call."""
    state = tmp_path / "state"
    _posture(state, band="RED", successor=None)
    (state / "fleet-exhausted").write_text("0\nurgent-90\n")
    line = _hook({"hook_event_name": "UserPromptSubmit", "session_id": "s1"}, state=state).stdout
    assert "CHECKPOINT NOW" in line, line
    assert "nothing is held yet" not in line.lower(), (
        f"the same hook denies Agent in this state — the line must not say otherwise: {line}"
    )
    assert "may still be held by the band" in line, line
    # and the denial the clause now admits to is real, in the same state
    deny = _hook(
        {
            "hook_event_name": "PreToolUse",
            "session_id": "s1",
            "tool_name": "Agent",
            "tool_input": {"prompt": "go"},
        },
        state=state,
        runs=tmp_path / "runs",
    ).stdout
    assert "deny" in deny, f"the contradiction is only resolved if this really denies: {deny}"


def test_the_three_tier_readers_agree_on_the_shapes_that_actually_diverge(tmp_path):
    """The first corpus covered the easy shapes. Three HAND-WRITTEN copies diverge on decoration:
    case, carriage returns, a third line, a NUL byte, control separators, a FIFO, a directory.
    Every one of those is graded here, because a copy that drifts makes the band and the hold
    disagree about whether the fleet is walled."""
    import os as _os

    mod = _load()
    root = Path(__file__).resolve().parents[1]
    mods = [mod]
    for name, rel in (
        ("tier_probe_tick2", "scripts/sysadmin/claude_rotate.py"),
        ("tier_probe_stop2", ".claude/hooks/quota_stop.py"),
    ):
        spec = importlib.util.spec_from_file_location(name, root / rel)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        mods.append(m)
    assert len({m.__file__ for m in mods}) == 3, "three DIFFERENT files, or this grades nothing"

    # ⚠️ EXPECTED VALUES, not just agreement. The first cut asserted `len(set(got)) == 1`, so an
    # all-three drift back to the defect passed — a seat reverted `.split("\n")` to `.splitlines()`
    # in every copy and this grader watched the exact bug it names (`0\x0burgent-90…`) and said
    # nothing. Agreement is necessary; correctness is what the fleet depends on.
    s = tmp_path / "fleet-exhausted"
    for body, want in (
        ("0\nWALLED\n", "walled"),
        ("0\nUrgent-90\n", "walled"),
        ("0\nurgent-90", "urgent-90"),
        ("0\r\nurgent-90\r\n", "urgent-90"),
        ("0\rurgent-90", "walled"),
        ("0\nurgent-90\nwalled\n", "urgent-90"),
        ("0\nurgent-90\x00\n", "walled"),
        ("0\x0burgent-90\nwalled\n", "walled"),
        ("0\n urgent-90 \n", "urgent-90"),
        ("0\nurgent-90x\n", "walled"),
        ("\x00\nurgent-90\n", "urgent-90"),
        ("0\n\nurgent-90\n", "walled"),
    ):
        s.write_text(body)
        got = [m._stamp_tier(s) for m in mods]
        assert len(set(got)) == 1, f"readers disagree on {body!r}: {got}"
        assert got[0] == want, f"{body!r}: all three agree on {got[0]!r}, but it must be {want!r}"
    fifo_dir = tmp_path / "f"
    fifo_dir.mkdir()
    _os.mkfifo(fifo_dir / "fleet-exhausted")
    assert len({m._stamp_tier(fifo_dir / "fleet-exhausted") for m in mods}) == 1
    d = tmp_path / "d"
    (d / "fleet-exhausted").mkdir(parents=True)
    assert {m._stamp_tier(d / "fleet-exhausted") for m in mods} == {"walled"}
