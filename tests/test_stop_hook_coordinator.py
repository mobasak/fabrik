"""The Stop hook's coordinator cause (W-83021827, D-521): one `work.py queue --stop` line, acted on.

Every case drives the REAL hook (`main`) over a throwaway clean main checkout, so no earlier cause
can speak. The `work.py` call is stubbed by argv (`_COORD_ARGV`) with the JSON line it would print;
`work.py`'s own decisions are graded in tests/test_work_coordinator.py.
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_TREE = Path(__file__).resolve().parents[1]
_HOOK = _TREE / ".claude" / "hooks" / "final_gate_stop.py"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load("fgs_coordinator", _HOOK)
SID = "sid-coordinator"
CLAIM = {
    "agent": "w1",
    "role": "worker",
    "action": "claim",
    "fp": "claim:few",
    "text": "1 item(s) are queued for you (w1) — claim W-00000001",
}


def _line(obj: dict) -> tuple[str, ...]:
    """A `work.py queue --stop` stub printing `obj` (extra argv is ignored)."""
    return (sys.executable, "-c", f"print({json.dumps(json.dumps(obj))})")


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("CLAUDE_MESH_HEADLESS", raising=False)
    monkeypatch.delenv("CLAUDE_AGENT", raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("THREAD_ANCHOR_DIR", str(tmp_path / "threads"))
    monkeypatch.setenv("COMMAND_RUN_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENT_IDENTITY_FILE", str(tmp_path / "identity.jsonl"))
    monkeypatch.setenv("FABRIK_MAIL_ROOT", str(tmp_path / "mail"))
    monkeypatch.setattr(hook.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(hook, "_merge_owner_duty", lambda root, sid: None)
    monkeypatch.setattr(hook, "_coord_band", lambda transcript: None)
    monkeypatch.setattr(hook, "_COORD_ARGV", _line(CLAIM))


def _repo(tmp_path: Path) -> Path:
    main = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "master", str(main)], check=True, timeout=30)
    for cfg in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        subprocess.run(["git", "-C", str(main), "config", *cfg], check=True, timeout=30)
    (main / "scripts").mkdir()
    (main / "scripts" / "final_gate.py").write_text("", encoding="utf-8")
    (main / ".gitignore").write_text(".fabrik/\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(main), "add", "-A"], check=True, timeout=30)
    subprocess.run(["git", "-C", str(main), "commit", "-qm", "base"], check=True, timeout=30)
    return main


def _drive(monkeypatch, cwd: Path, lam: str | None = None) -> tuple[dict | None, str]:
    payload: dict = {"cwd": str(cwd), "session_id": SID}
    if lam is not None:
        payload["last_assistant_message"] = lam
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    assert hook.main([]) == 0
    text = out.getvalue().strip()
    return (json.loads(text) if text else None), err.getvalue()


def test_an_action_blocks_with_its_text_then_warns_through_once_and_stays_silent(
    monkeypatch, tmp_path
):
    main = _repo(tmp_path)
    for attempt in range(1, hook.CAP + 1):
        out, _ = _drive(monkeypatch, main)
        assert out is not None and out["decision"] == "block", attempt
        assert "W-00000001" in out["reason"] and f"attempt {attempt}/{hook.CAP}" in out["reason"]
    out, err = _drive(monkeypatch, main)
    assert out is None and "queued" in err, "the fourth Stop warns through"
    out, err = _drive(monkeypatch, main)
    assert out is None and err == "", "the same fingerprint stays silent after the warn-through"


def test_a_new_fingerprint_blocks_again_and_a_null_action_resets(monkeypatch, tmp_path):
    main = _repo(tmp_path)
    for _ in range(hook.CAP + 1):
        _drive(monkeypatch, main)
    monkeypatch.setattr(hook, "_COORD_ARGV", _line({**CLAIM, "fp": "claim:many"}))
    out, _ = _drive(monkeypatch, main)
    assert out is not None and "attempt 1/" in out["reason"]
    monkeypatch.setattr(hook, "_COORD_ARGV", _line({**CLAIM, "action": None, "fp": ""}))
    assert _drive(monkeypatch, main)[0] is None
    assert not hook._coord_state_path(SID).exists(), "a null action clears the state"
    monkeypatch.setattr(hook, "_COORD_ARGV", _line({**CLAIM, "fp": "claim:many"}))
    out, _ = _drive(monkeypatch, main)
    assert out is not None and "attempt 1/" in out["reason"]


@pytest.mark.parametrize(
    "lam",
    [
        "DECISION NEEDED (ground: gate)\n- Question: Deploy now?\n- Why it is yours: gate — Gate 2, "
        "a deploy.\n- Options: A — deploy · B — hold\n- Recommendation: A — certified.",
        "BLOCKED: the store — searched: work.py — missing: the item file\n\nSTATE: blocked\nNEXT: none",
    ],
)
def test_a_decision_or_blocked_ending_is_exempt(monkeypatch, tmp_path, lam):
    main = _repo(tmp_path)
    out, _ = _drive(monkeypatch, main, lam=lam)
    assert out is None


def test_a_red_band_or_a_running_record_is_exempt(monkeypatch, tmp_path):
    main = _repo(tmp_path)
    monkeypatch.setattr(hook, "_coord_band", lambda transcript: "RED")
    assert _drive(monkeypatch, main)[0] is None
    monkeypatch.setattr(hook, "_coord_band", lambda transcript: None)
    monkeypatch.setattr(hook, "_run_record", lambda sid: {"state": "running", "command": "x"})
    out, _ = _drive(monkeypatch, main)
    assert (
        out is None
        or "coordinator" not in out.get("reason", "").lower()
        and "W-00000001" not in out.get("reason", "")
    )


def test_a_running_record_with_seats_out_stays_exempt(monkeypatch, tmp_path):
    """W-4c7edc74: seats in flight stand the run-record block down, never this cause's exemption."""
    main = _repo(tmp_path)
    monkeypatch.setattr(hook, "_run_record", lambda sid: {"state": "running", "command": "x"})
    monkeypatch.setattr(hook, "_seats_in_flight", lambda rec, transcript: True)
    out, _ = _drive(monkeypatch, main)
    assert out is None


def test_the_cause_never_writes_the_seven_slot_counter(monkeypatch, tmp_path):
    main = _repo(tmp_path)
    out, _ = _drive(monkeypatch, main)
    assert out is not None
    counter = Path(hook._counter_path(SID))
    assert not counter.exists(), (
        "a clean repo's 7-slot counter is unlinked at the pass-through; the coordinator cause "
        f"must not recreate it: {counter.read_text() if counter.exists() else ''}"
    )
    assert hook._coord_state_path(SID).exists()


def test_a_failed_or_garbled_queue_call_is_silent(monkeypatch, tmp_path):
    main = _repo(tmp_path)
    monkeypatch.setattr(hook, "_COORD_ARGV", (sys.executable, "-c", "print('not json')"))
    assert _drive(monkeypatch, main)[0] is None
    monkeypatch.setattr(hook, "_COORD_ARGV", (sys.executable, "-c", "import sys; sys.exit(3)"))
    assert _drive(monkeypatch, main)[0] is None


def test_the_queue_call_runs_as_this_session(monkeypatch, tmp_path):
    main = _repo(tmp_path)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "some-other-session")
    stub = (
        "import json, os; print(json.dumps({'action': 'claim', 'fp': 'claim:few', "
        "'text': 'as ' + os.environ.get('CLAUDE_CODE_SESSION_ID', '')}))"
    )
    monkeypatch.setattr(hook, "_COORD_ARGV", (sys.executable, "-c", stub))
    out, _ = _drive(monkeypatch, main)
    assert out is not None and f"as {SID}" in out["reason"], out


def test_a_corrupt_state_file_restarts_the_count_instead_of_crashing(tmp_path):
    hook._coord_state_path(SID).write_text('{"fp": "claim:few", "att": "oops"}', encoding="utf-8")
    duty = hook._coordinator_duty(tmp_path, SID, tmp_path)
    assert duty is not None and "attempt 1/" in duty[0]


def test_a_garbled_line_is_handled_inside_the_cause(monkeypatch, tmp_path):
    hook._coord_state_path(SID).write_text('{"fp": "claim:few", "att": 1}', encoding="utf-8")
    monkeypatch.setattr(hook, "_COORD_ARGV", (sys.executable, "-c", "print('not json')"))
    assert hook._coordinator_duty(tmp_path, SID, tmp_path) is None
    assert not hook._coord_state_path(SID).exists(), "a garbled line clears the state like a null"


# W-05d3af0f: at a fleet AMBER band the contract says "finish what you started, start nothing
# heavy", so the cause stops ordering NEW work and keeps enforcing what finishes or routes work.
_STARTS = ("claim", "owned", "feedback", "self", "doorbell", "merge", "triage")
_FINISHES = ("continue", "release", "commit-items", "mail")


@pytest.mark.parametrize("action", _STARTS)
def test_amber_stands_down_an_action_that_starts_new_work(monkeypatch, tmp_path, action):
    main = _repo(tmp_path)
    monkeypatch.setattr(hook, "_COORD_ARGV", _line({**CLAIM, "action": action, "fp": action}))
    monkeypatch.setattr(hook, "_coord_band", lambda transcript: "AMBER")
    assert _drive(monkeypatch, main)[0] is None
    monkeypatch.setattr(hook, "_coord_band", lambda transcript: "GREEN")
    out, _ = _drive(monkeypatch, main)
    assert out is not None and f"WORK WAITING — {action}" in out["reason"]


@pytest.mark.parametrize("action", _FINISHES)
def test_amber_still_enforces_finishing_and_routing_work(monkeypatch, tmp_path, action):
    main = _repo(tmp_path)
    monkeypatch.setattr(hook, "_COORD_ARGV", _line({**CLAIM, "action": action, "fp": action}))
    monkeypatch.setattr(hook, "_coord_band", lambda transcript: "AMBER")
    out, _ = _drive(monkeypatch, main)
    assert out is not None and f"WORK WAITING — {action}" in out["reason"]


def test_amber_ladder_skips_start_candidates_without_spending_them(monkeypatch, tmp_path):
    main = _repo(tmp_path)
    ladder = {
        "candidates": [
            {"action": "claim", "fp": "claim:x", "text": "claim W-00000001"},
            {"action": "continue", "fp": "item:W-00000002", "text": "finish W-00000002"},
        ]
    }
    monkeypatch.setattr(hook, "_COORD_ARGV", _line(ladder))
    monkeypatch.setattr(hook, "_coord_band", lambda transcript: "AMBER")
    out, _ = _drive(monkeypatch, main)
    assert out is not None and "W-00000002" in out["reason"]
    monkeypatch.setattr(hook, "_coord_band", lambda transcript: "GREEN")
    out, _ = _drive(monkeypatch, main)
    assert out is not None and "W-00000001" in out["reason"] and "attempt 1/" in out["reason"]


def test_an_amber_skip_leaves_the_attempt_count_where_it_was(monkeypatch, tmp_path):
    main = _repo(tmp_path)
    hook._coord_state_path(SID).write_text(json.dumps({"fp": "claim:few", "att": 2}))
    monkeypatch.setattr(hook, "_coord_band", lambda transcript: "AMBER")
    assert _drive(monkeypatch, main)[0] is None
    monkeypatch.setattr(hook, "_coord_band", lambda transcript: "GREEN")
    out, _ = _drive(monkeypatch, main)
    assert out is not None and f"attempt 3/{hook.CAP}" in out["reason"]


def test_an_unreadable_band_is_enforced_as_green(monkeypatch, tmp_path):
    main = _repo(tmp_path)
    monkeypatch.setattr(hook, "_coord_band", lambda transcript: None)
    out, _ = _drive(monkeypatch, main)
    assert out is not None and "WORK WAITING — claim" in out["reason"]


def test_a_stand_down_is_recorded_as_a_kaizen_event(monkeypatch, tmp_path):
    main = _repo(tmp_path)
    monkeypatch.setattr(hook, "_coord_band", lambda transcript: "AMBER")
    assert _drive(monkeypatch, main)[0] is None
    rows = [
        json.loads(ln)
        for p in (tmp_path / "events").rglob("*")
        if p.is_file()
        for ln in p.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    assert any(
        r.get("event") == "stop_block"
        and r.get("cause") == "coordinator"
        and r.get("outcome") == "stood_down"
        and r.get("action") == "claim"
        and r.get("band") == "AMBER"
        for r in rows
    ), rows


def test_every_action_work_py_emits_is_classified_for_amber():
    """A new action must be placed deliberately: unlisted, it would block at AMBER by default."""
    import ast

    tree = ast.parse((_TREE / "scripts" / "work.py").read_text(encoding="utf-8"))
    # The `action` values work.py builds, over the WHOLE file (a slice by function position missed a
    # rung outside it — review S-1), in these spellings: a dict-literal key in either quote style, any
    # call's `action=` keyword (`dict(…)`, `.update(…)`) but argparse's `add_argument`, a
    # `.setdefault("action", …)` / `.update({"action": …})` argument, and `x["action"] = …`.
    # NOT seen, by design: a comprehension, an augmented or annotated assign,
    # a key held in a variable, and anything another module builds.
    values: list[tuple[ast.AST, bool]] = []  # (value, is the item comment's record)
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = {k.value for k in node.keys if isinstance(k, ast.Constant)}
            for k, v in zip(node.keys, node.values, strict=True):
                if isinstance(k, ast.Constant) and k.value == "action":
                    # the item comment: a `by`/`via` record whose action is the verdict variable
                    comment = {"via", "by"} <= keys and isinstance(v, ast.Name) and v.id == "action"
                    values.append((v, comment))
        elif isinstance(node, ast.Call):
            attr = node.func.attr if isinstance(node.func, ast.Attribute) else ""
            if attr != "add_argument":
                values += [(kw.value, False) for kw in node.keywords if kw.arg == "action"]
            if (
                attr == "setdefault"
                and len(node.args) == 2
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "action"
            ):
                values.append((node.args[1], False))
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if (
                    isinstance(t, ast.Subscript)
                    and isinstance(t.slice, ast.Constant)
                    and t.slice.value == "action"
                ):
                    values.append((node.value, False))
    # ONE exception, by shape AND value: the item comment `{"by": …, "via": …, "action": action}`
    # (`cmd_verdict`, W-e1f1a1bd) records the operator's verdict, never a stop action.
    comments = [v for v, is_comment in values if is_comment]
    assert len(comments) == 1, (
        f"expected exactly one item-comment `action` field, found {len(comments)}"
    )
    stop = [v for v, is_comment in values if not is_comment]
    # every other `action` value is a literal name or None, so the set below sees them all
    unread = [
        ast.unparse(v)
        for v in stop
        if not (isinstance(v, ast.Constant) and (v.value is None or isinstance(v.value, str)))
    ]
    assert not unread, (
        f"an `action` built from a non-literal escapes the classification: {unread} — a stop action "
        "must be a literal name; a record that is not a stop action needs its own named exception"
    )
    emitted = {v.value for v in stop if isinstance(v, ast.Constant) and isinstance(v.value, str)}
    assert emitted == set(_STARTS) | set(_FINISHES), (
        f"unclassified `action` names {emitted ^ (set(_STARTS) | set(_FINISHES))}: a new stop action "
        "goes in _STARTS or _FINISHES; a record that is not a stop action needs its own named exception"
    )
    assert frozenset(_STARTS) == hook._COORD_AMBER_STARTS


def test_one_stand_down_event_names_every_skipped_action(monkeypatch, tmp_path):
    main = _repo(tmp_path)
    ladder = {
        "candidates": [
            {"action": "claim", "fp": "claim:x", "text": "claim W-00000001"},
            {"action": "owned", "fp": "owned:y", "text": "start W-00000003"},
        ]
    }
    monkeypatch.setattr(hook, "_COORD_ARGV", _line(ladder))
    monkeypatch.setattr(hook, "_coord_band", lambda transcript: "AMBER")
    assert _drive(monkeypatch, main)[0] is None
    rows = _events(tmp_path)
    stood = [r for r in rows if r.get("outcome") == "stood_down"]
    assert len(stood) == 1 and stood[0]["action"] == "claim,owned", stood


def test_a_warned_through_finisher_is_not_also_reported_as_a_stand_down(monkeypatch, tmp_path):
    main = _repo(tmp_path)
    hook._coord_state_path(SID).write_text(json.dumps({"map": {"item:W-00000002": hook.CAP}}))
    ladder = {
        "candidates": [
            {"action": "claim", "fp": "claim:x", "text": "claim W-00000001"},
            {"action": "continue", "fp": "item:W-00000002", "text": "finish W-00000002"},
        ]
    }
    monkeypatch.setattr(hook, "_COORD_ARGV", _line(ladder))
    monkeypatch.setattr(hook, "_coord_band", lambda transcript: "AMBER")
    _drive(monkeypatch, main)
    outcomes = [r.get("outcome") for r in _events(tmp_path) if r.get("cause") == "coordinator"]
    assert "warned_through" in outcomes and "stood_down" not in outcomes, outcomes


def test_a_single_action_block_reports_its_own_action(monkeypatch, tmp_path):
    main = _repo(tmp_path)
    hook._COORD_LAST_ACTION[:] = ["stale-from-an-earlier-call"]
    monkeypatch.setattr(hook, "_COORD_ARGV", _line({**CLAIM, "action": "continue", "fp": "c"}))
    out, _ = _drive(monkeypatch, main)
    assert out is not None
    blocked = [r for r in _events(tmp_path) if r.get("outcome") == "blocked"]
    assert blocked and blocked[-1]["action"] == "continue", blocked


def _events(tmp_path: Path) -> list[dict]:
    return [
        json.loads(ln)
        for p in (tmp_path / "events").rglob("*")
        if p.is_file()
        for ln in p.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]


# W-0fae19b7: at a rotation boundary (D-1119, D-1123) — a due stamp from the context or MB check AND
# the session's own `NEXT: … awaiting the rotation` footer — the cause holds the start actions of the
# session's own, as AMBER does; finishing and routing work still blocks.
_FOOTER = (
    "W-00000009 closed and pushed.\n\nSTATE: rotation asked\n"
    "NEXT: none — terminal; awaiting the rotation"
)
_ROT_HELD = ("claim", "owned", "feedback", "self", "doorbell", "merge")
_ROT_ENFORCED = ("continue", "release", "commit-items", "triage")


def _stamp(tmp_path: Path, value: str, *, kind: str = "ctx", sid: str = SID) -> None:
    """A stamp at the writer's default path under the test HOME, named by the RAW sid."""
    base = tmp_path / "home" / ".claude" / "state" / "rotate-advised"
    path = base / ".ctx" / sid if kind == "ctx" else base / sid
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


@pytest.fixture
def _stamps_from_home(monkeypatch) -> None:
    monkeypatch.delenv("ROTATE_STAMP_DIR", raising=False)


@pytest.mark.parametrize(("kind", "value"), [("ctx", "40\n"), ("ctx", "90\n"), ("mb", "200\n")])
@pytest.mark.parametrize("action", _ROT_HELD)
def test_rotation_boundary_stands_down_a_start_action(
    monkeypatch, tmp_path, _stamps_from_home, kind, value, action
):
    main = _repo(tmp_path)
    monkeypatch.setattr(hook, "_COORD_ARGV", _line({**CLAIM, "action": action, "fp": action}))
    _stamp(tmp_path, value, kind=kind)
    assert _drive(monkeypatch, main, lam=_FOOTER)[0] is None, "held at the rotation boundary"
    stood = [r for r in _events(tmp_path) if r.get("outcome") == "stood_down"]
    assert stood and stood[-1]["action"] == action and stood[-1]["reason"] == "rotation", stood


@pytest.mark.parametrize(
    "lam",
    [
        _FOOTER,
        "done\n\nNEXT: none – terminal; awaiting the rotation",
        "done\n\nNEXT: none - terminal - awaiting the rotation",
        "done\n\n**NEXT:** none — terminal; awaiting the rotation",
        "done\n\n- NEXT: none — terminal; awaiting the rotation",
        "done\n\nNEXT: awaiting the rotation",
        "done\n\n```\nSTATE: rotation asked\nNEXT: none — terminal; awaiting the rotation\n```",
        "done\r\n\r\nNEXT: none — terminal; awaiting the rotation\r\n",
        "done\n\nNEXT: none — terminal; awaiting the rotation.",
        "done\n\nNEXT: `none — terminal; awaiting the rotation`",
        "done\n\nNEXT: none awaiting the rotation",
        "done\n\nNEXT\t: none — terminal; awaiting the rotation",
        "done\n\n  NEXT: none — terminal; awaiting the rotation",
        "NEXT: W-00000001 — claim it\n\nlater: done\n\nNEXT: none — terminal; awaiting the rotation",
    ],
)
def test_rotation_footer_spellings(monkeypatch, tmp_path, _stamps_from_home, lam):
    main = _repo(tmp_path)
    _stamp(tmp_path, "50\n")
    assert _drive(monkeypatch, main, lam=lam)[0] is None, lam
    stood = [r for r in _events(tmp_path) if r.get("outcome") == "stood_down"]
    assert stood and stood[-1]["reason"] == "rotation", (lam, stood)


@pytest.mark.parametrize(
    "lam",
    [
        "The footer reads:\n\n```\nNEXT: none — terminal; awaiting the rotation\n```\n\nbut I go on."
        "\n\nNEXT: W-00000001 — claim it",
        "The footer reads:\n\n```\nNEXT: none — terminal; awaiting the rotation\n```\n\nbut I go on.",
        "done\n\nNEXT: W-00000001 — the next item, then awaiting the rotation",
        "done\n\nNEXT: none — terminal",
        "done\n\nNEXT: none — not awaiting the rotation",
        "done\n\nNEXT: none — terminal; NOT awaiting the rotation",
        "done\n\nNEXT: none — then claim W-00000001, awaiting the rotation",
        "done\n\nNEXT: none — awaiting the rotation of keys, then deploy",
        "done\n\nNEXT: awaiting the rotations",
        "done\n\n> NEXT: none — terminal; awaiting the rotation",
        "done\n\n    NEXT: none — terminal; awaiting the rotation",
        "done\n\n\tNEXT: none — terminal; awaiting the rotation",
        "done\n\nNEXT: none — W-00000009 is queued; awaiting the rotation",
        "prose\n\n```\nNEXT: none — terminal; awaiting the rotation\n```\n",
        "NEXT: none — terminal; awaiting the rotation\n\nNEXT: W-00000001 — claim it",
    ],
)
def test_rotation_footer_quoted_or_successor_first_does_not_count(
    monkeypatch, tmp_path, _stamps_from_home, lam
):
    main = _repo(tmp_path)
    _stamp(tmp_path, "50\n")
    out, _ = _drive(monkeypatch, main, lam=lam)
    assert out is not None and "WORK WAITING — claim" in out["reason"], lam


@pytest.mark.parametrize(
    ("kind", "value", "sid"),
    [
        ("ctx", "0\n", SID),
        ("ctx", "39\n", SID),
        ("ctx", "garbage\n", SID),
        ("ctx", "", SID),
        ("ctx", "+50\n", SID),
        ("ctx", "5_0\n", SID),
        ("ctx", "٥٠\n", SID),
        ("mb", "0\n", SID),
        ("mb", "-200\n", SID),
        ("mb", "9" * 5000, SID),
        ("mb", "x\n", SID),
        ("ctx", "50\n", "another-session"),
    ],
)
def test_rotation_hold_needs_both_a_due_stamp_and_the_footer(
    monkeypatch, tmp_path, _stamps_from_home, kind, value, sid
):
    main = _repo(tmp_path)
    _stamp(tmp_path, value, kind=kind, sid=sid)
    out, _ = _drive(monkeypatch, main, lam=_FOOTER)
    assert out is not None and "WORK WAITING — claim" in out["reason"], (kind, value, sid)
    _stamp(tmp_path, "60\n")
    out, _ = _drive(monkeypatch, main, lam="done\n\nSTATE: idle\nNEXT: none — terminal")
    assert out is not None and "WORK WAITING — claim" in out["reason"], "a due stamp alone"


def test_rotation_due_refuses_a_sid_the_writer_grammar_refuses(tmp_path, _stamps_from_home):
    _stamp(tmp_path, "50\n")
    _stamp(
        tmp_path, "200\n", kind="mb"
    )  # `.ctx/../<SID>` resolves here: the traversal has a target
    assert hook._rotation_due(SID)
    for bad in ("../" + SID, ".ctx", "", "-" + SID, "a" * 129):
        assert not hook._rotation_due(bad), bad


@pytest.mark.timeout(20)  # without the `is_file` guard the read blocks: a timeout makes it a red, not a hang
def test_rotation_due_never_reads_a_fifo_or_a_directory(tmp_path, _stamps_from_home):
    import os

    base = tmp_path / "home" / ".claude" / "state" / "rotate-advised"
    (base / ".ctx").mkdir(parents=True)
    os.mkfifo(base / ".ctx" / SID)  # opening it for read would block the Stop forever
    (base / SID).mkdir()
    assert not hook._rotation_due(SID)


@pytest.mark.parametrize("action", _ROT_ENFORCED)
def test_rotation_boundary_still_enforces_finishing_and_routing_work(
    monkeypatch, tmp_path, _stamps_from_home, action
):
    main = _repo(tmp_path)
    monkeypatch.setattr(hook, "_COORD_ARGV", _line({**CLAIM, "action": action, "fp": action}))
    _stamp(tmp_path, "50\n")
    out, _ = _drive(monkeypatch, main, lam=_FOOTER)
    assert out is not None and f"WORK WAITING — {action}" in out["reason"]


@pytest.mark.parametrize(
    ("role", "held"), [("worker", True), ("coordinator", False), ("main", False), ("", False)]
)
def test_rotation_boundary_holds_mail_only_for_a_worker(
    monkeypatch, tmp_path, _stamps_from_home, role, held
):
    main = _repo(tmp_path)
    monkeypatch.setattr(
        hook, "_COORD_ARGV", _line({**CLAIM, "role": role, "action": "mail", "fp": "mail"})
    )
    _stamp(tmp_path, "50\n")
    out, _ = _drive(monkeypatch, main, lam=_FOOTER)
    if held:
        assert out is None
    else:
        assert out is not None and "WORK WAITING — mail" in out["reason"]


def test_rotation_ladder_skips_start_candidates_without_spending_them(
    monkeypatch, tmp_path, _stamps_from_home
):
    main = _repo(tmp_path)
    ladder: dict = {
        "role": "worker",
        "candidates": [
            {"action": "feedback", "fp": "fb:x", "text": "run /fabrik-command-improve x"},
            {"action": "mail", "fp": "mail:y", "text": "answer mail y"},
            {"action": "release", "fp": "item:W-00000002", "text": "release W-00000002"},
        ],
    }
    monkeypatch.setattr(hook, "_COORD_ARGV", _line(ladder))
    _stamp(tmp_path, "50\n")
    out, _ = _drive(monkeypatch, main, lam=_FOOTER)
    assert out is not None and "W-00000002" in out["reason"]
    state = json.loads(hook._coord_state_path(SID).read_text(encoding="utf-8"))
    assert set(state["map"]) == {"item:W-00000002"}, "held candidates spend no attempt"
    ladder["candidates"] = ladder["candidates"][:2]
    monkeypatch.setattr(hook, "_COORD_ARGV", _line(ladder))
    assert _drive(monkeypatch, main, lam=_FOOTER)[0] is None
    stood = [r for r in _events(tmp_path) if r.get("outcome") == "stood_down"]
    assert stood and stood[-1]["action"] == "feedback,mail", stood
    assert stood[-1]["reason"] == "rotation", stood
    ladder["role"] = "coordinator"  # a coordinator's mail is routing work: it still blocks
    monkeypatch.setattr(hook, "_COORD_ARGV", _line(ladder))
    out, _ = _drive(monkeypatch, main, lam=_FOOTER)
    assert out is not None and "answer mail y" in out["reason"]


@pytest.mark.parametrize(("stamp", "reason"), [(True, "amber+rotation"), (False, "amber")])
def test_a_stand_down_event_names_its_reason(
    monkeypatch, tmp_path, _stamps_from_home, stamp, reason
):
    main = _repo(tmp_path)
    monkeypatch.setattr(hook, "_coord_band", lambda transcript: "AMBER")
    if stamp:
        _stamp(tmp_path, "50\n")
    assert _drive(monkeypatch, main, lam=_FOOTER)[0] is None
    stood = [r for r in _events(tmp_path) if r.get("outcome") == "stood_down"]
    assert stood and stood[-1]["reason"] == reason and stood[-1]["band"] == "AMBER", stood


def test_rotation_constants_match_the_stamp_writer():
    writer_path = Path("/opt/fabrik/scripts/sysadmin/transcript_size_check.py")
    if not writer_path.is_file():
        pytest.skip("the hub stamp writer is not on this box")
    writer = _load("tsc_parity", writer_path)
    assert hook._CTX_ROTATE_PCT == writer.CTX_ROTATE_PCT
    assert hook._ROTATE_SID_RE.pattern == writer._SID_RE.pattern
    assert hook._ROTATE_STAMP_DEFAULT == "~/.claude/state/rotate-advised"
    src = writer_path.read_text(encoding="utf-8")
    assert '_env_path("ROTATE_STAMP_DIR", "~/.claude/state/rotate-advised")' in src
    assert 'stamp_dir / ".ctx"' in src
    assert frozenset(_ROT_HELD) == hook._ROTATION_HOLDS
