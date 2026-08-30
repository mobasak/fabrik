# AFTER-EDIT: .claude/hooks/session_orient.py, .claude/hooks/final_gate_stop.py
"""Kaizen M1 hook emitters (T02) — the session-lifecycle sensors.

Two FLEET-SYNCED hooks carry them (`.claude/hooks/*` distributes to ~46 repos), so
every test here is about one of three things:

1. **The seam contract** — each event type lands as ONE parseable JSON line in
   ``$KAIZEN_EVENTS_DIR/<sid>.jsonl`` carrying schema/ts/sid/event + an exposure whose
   VALUES describe the payload's project (not the hook process's cwd), with the cause
   taxonomy the collector buckets on (``stop_block.cause`` ∈ gate-red / uncommitted /
   unpushed / promise-stall / run-record, each with an ``outcome`` of ``blocked`` or
   ``warned_through``).

2. **Instrumentation symmetry** — the two hooks must instrument the SAME universe.
   `session_start` fires only where a Stop hook would also fire (a fabrik-style project,
   by the payload cwd's ``scripts/final_gate.py``) and only on a real session birth
   (``source=startup``), so the collector never sees a fabricated hole. Per-TURN
   liveliness is `stop_pass`, not a session-scoped "end".

3. **Fail-open at the IMPORT layer** — `kaizen_events` lives at ONE place per box, so
   the real degraded state is the module being unimportable from BOTH the repo-relative
   path AND the ``/opt/fabrik`` hub path. In that state the hooks must be byte-identical
   on **stdout AND stderr** and identical in exit code. The control run installs a
   `sys.meta_path` finder that refuses the module by name, which is exactly what both
   paths missing looks like to the `import` statement.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

FABRIK = Path(__file__).resolve().parents[1]
ORIENT = FABRIK / ".claude/hooks/session_orient.py"
STOP = FABRIK / ".claude/hooks/final_gate_stop.py"

_FAKE_GATE = """#!/usr/bin/env python3
import json, os, sys
fails = [f for f in os.environ.get("FAKE_FAILS", "").split(",") if f]
if not fails:
    print(json.dumps({"status": "success", "failures": []})); sys.exit(0)
print(json.dumps({"status": "failure",
                  "failures": [{"check": c, "output": ""} for c in fails]}))
sys.exit(1)
"""

_EXPOSURE_FIELDS = ("commit", "account", "model", "project", "headless", "plan_era")

# The module refuses to import no matter which path it is looked for on — the honest
# model of "this box has no kaizen_events", which is the only real degraded state now
# that the hub fallback is the adjudicated contract (one box, one module).
_BLOCKER_SRC = """
import sys


class _RefuseKaizenEvents:
    def find_spec(self, name, path=None, target=None):
        if name == "kaizen_events":
            raise ModuleNotFoundError("kaizen_events blocked at every path (test control)")
        return None


sys.meta_path.insert(0, _RefuseKaizenEvents())
sys.modules["kaizen_events"] = None
"""

# An importable module whose emit() explodes — proves the hooks' own output survives a
# sensor that raises, not merely a sensor that is absent.
_EXPLODER_SRC = """
import sys, types

mod = types.ModuleType("kaizen_events")


def _boom(*a, **k):
    raise RuntimeError("injected emitter failure")


mod.emit = _boom
mod.resolve_sid = _boom
mod.exposure = _boom
sys.modules["kaizen_events"] = mod
"""


# --- harness ------------------------------------------------------------------


def _env(tmp: Path, **extra: str) -> dict[str, str]:
    """A hermetic hook environment: our own TMPDIR (baseline/counter files), our own
    command-run dir, our own events dir. Both session-id vars are stripped — the test
    process is itself a Claude session and would otherwise donate its id to a payload
    that deliberately carries none (CLAUDE_CODE_SESSION_ID joined the resolver chain
    2026-08-21)."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k
        not in (
            "CLAUDE_SESSION_ID",
            "CLAUDE_CODE_SESSION_ID",
            "KAIZEN_EVENTS_DIR",
            "PYTHONPATH",
        )
    }
    for sub in ("tmpdir", "runs"):
        (tmp / sub).mkdir(parents=True, exist_ok=True)
    env.update(
        {
            "TMPDIR": str(tmp / "tmpdir"),
            "COMMAND_RUN_DIR": str(tmp / "runs"),
            "KAIZEN_EVENTS_DIR": str(tmp / "events"),
        }
    )
    env.update(extra)
    return env


def _sitecustomize_env(tmp: Path, base: dict[str, str], name: str, src: str) -> dict[str, str]:
    d = tmp / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "sitecustomize.py").write_text(src, encoding="utf-8")
    return {**base, "PYTHONPATH": str(d)}


def _no_module_env(tmp: Path, base: dict[str, str]) -> dict[str, str]:
    return _sitecustomize_env(tmp, base, "no_kaizen_module", _BLOCKER_SRC)


def _exploding_env(tmp: Path, base: dict[str, str]) -> dict[str, str]:
    return _sitecustomize_env(tmp, base, "exploding_kaizen", _EXPLODER_SRC)


def _events(tmp: Path, sid: str) -> list[dict]:
    path = tmp / "events" / f"{sid}.jsonl"
    if not path.is_file():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _of_type(evs: list[dict], event: str) -> list[dict]:
    return [e for e in evs if e.get("event") == event]


def _assert_seam(ev: dict, event: str, sid: str, project: Path | None = None) -> None:
    """The envelope every sensor owes the collector.

    When ``project`` is given the exposure VALUES are checked against that repo — key
    presence alone passed happily while every field described the hook process's own
    cwd instead of the session's project (the contamination this pins).
    """
    assert ev["schema"] == 1
    assert ev["event"] == event
    assert ev["sid"] == sid
    assert isinstance(ev["ts"], str) and ev["ts"]
    exp = ev["exposure"]
    assert isinstance(exp, dict)
    for field in _EXPOSURE_FIELDS:
        assert field in exp, f"exposure must carry {field!r}"
    if project is not None:
        assert exp["commit"] == _head(project), "exposure.commit must be the PAYLOAD project's HEAD"
        # The fixture lives under tmp, not /opt/<name> — a "fabrik" here would mean the
        # probe read the hook process's cwd (this repo) instead of the payload's.
        assert exp["project"] == "unknown"
        assert exp["plan_era"] == "—"


def _head(project: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project, capture_output=True, text=True, timeout=30
    ).stdout.strip()


def _git(project: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=project,
        check=True,
        timeout=30,
        capture_output=True,
    )


def _project(tmp: Path) -> Path:
    """A minimal fabrik-shaped project: a fake gate + a committed baseline commit."""
    p = tmp / "proj"
    (p / "scripts").mkdir(parents=True)
    (p / "scripts" / "final_gate.py").write_text(_FAKE_GATE, encoding="utf-8")
    _git(p, "init", "-q", "-b", "master")
    _git(p, "add", "scripts/final_gate.py")
    _git(p, "commit", "-qm", "base")
    return p


def _transcript(
    project: Path,
    text: str = "",
    edited: list[str] | None = None,
    text_blocks: list[str] | None = None,
) -> str:
    """A JSONL transcript: optional Edit tool_uses, then a final assistant message.

    ``text_blocks`` writes the final message as SEVERAL text blocks in one entry — the
    shape that splits a 6-line block across blocks.
    """
    lines: list[str] = []
    for rel in edited or []:
        path = project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("session work", encoding="utf-8")
        lines.append(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "tool_use", "name": "Edit", "input": {"file_path": str(path)}}
                        ]
                    },
                }
            )
        )
    blocks = text_blocks if text_blocks is not None else ([text] if text else [])
    if blocks:
        lines.append(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "text", "text": b} for b in blocks]},
                }
            )
        )
    tp = project / "transcript.jsonl"
    tp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(tp)


def _run_orient(
    project: Path,
    tmp: Path,
    sid: str | None,
    env: dict[str, str] | None = None,
    source: str | None = "startup",
):
    payload: dict[str, object] = {"cwd": str(project)}
    if sid is not None:
        payload["session_id"] = sid
    if source is not None:
        payload["source"] = source
    return subprocess.run(
        [sys.executable, str(ORIENT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=60,
        env=env or _env(tmp),
    )


def _run_stop(
    project: Path,
    tmp: Path,
    sid: str | None,
    *,
    baseline: list[str] | None = None,
    fake_fails: str = "",
    transcript: str | None = None,
    env: dict[str, str] | None = None,
    reset: bool = True,
):
    env = dict(env or _env(tmp))
    env["FAKE_FAILS"] = fake_fails
    tmpdir = Path(env["TMPDIR"])
    key = sid or "nosession"
    if reset:
        (tmpdir / f"fabrik-gate-stop-{key}.attempts").unlink(missing_ok=True)
    bl = tmpdir / f"fabrik-gate-baseline-{key}.json"
    if baseline is None:
        bl.unlink(missing_ok=True)
    else:
        bl.write_text(json.dumps(baseline), encoding="utf-8")
    payload: dict[str, object] = {"cwd": str(project), "hook_event_name": "Stop"}
    if sid is not None:
        payload["session_id"] = sid
    if transcript:
        payload["transcript_path"] = transcript
    return subprocess.run(
        [sys.executable, str(STOP)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )


# --- session_start: the instrumentation universe ------------------------------


def test_session_start_lands_one_parseable_event(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    proc = _run_orient(proj, tmp_path, "sidorient1")
    assert proc.returncode == 0
    assert "## ORIENT" in proc.stdout  # the hook's real job is unchanged
    evs = _events(tmp_path, "sidorient1")
    assert len(_of_type(evs, "session_start")) == 1
    ev = _of_type(evs, "session_start")[0]
    _assert_seam(ev, "session_start", "sidorient1", project=proj)
    assert ev["cwd"] == str(proj)


def test_no_session_start_outside_a_fabrik_project(tmp_path: Path) -> None:
    # SYMMETRY: the Stop hook returns early where scripts/final_gate.py is absent, so a
    # session_start there would be a session the collector can never see closed — a
    # fabricated hole in the completion metric.
    bare = tmp_path / "bare"
    bare.mkdir()
    proc = _run_orient(bare, tmp_path, "sidbare")
    assert proc.returncode == 0
    assert "## ORIENT" in proc.stdout  # orientation is unconditional; only the SENSOR is scoped
    assert _events(tmp_path, "sidbare") == []


def test_no_session_start_on_resume_or_compact(tmp_path: Path) -> None:
    # A resume/compact is not a session BIRTH — it is the same session continuing, and
    # the --baseline path special-cases them for exactly this reason. Counting them
    # would inflate the session denominator with every compaction.
    proj = _project(tmp_path)
    for source in ("resume", "compact"):
        _run_orient(proj, tmp_path, f"sid-{source}", source=source)
        assert _events(tmp_path, f"sid-{source}") == [], source
    _run_orient(proj, tmp_path, "sid-startup", source="startup")
    assert len(_of_type(_events(tmp_path, "sid-startup"), "session_start")) == 1


def test_orient_prints_its_block_even_when_the_emitter_raises(tmp_path: Path) -> None:
    # The ORIENT block is the hook's product; the sensor is a passenger. Emitting BEFORE
    # printing put the whole block behind an emitter that can throw.
    proj = _project(tmp_path)
    env = _exploding_env(tmp_path, _env(tmp_path))
    proc = _run_orient(proj, tmp_path, "sidboom", env=env)
    assert proc.returncode == 0
    assert "## ORIENT" in proc.stdout
    assert "session-recall" in proc.stdout  # the WHOLE block, not a truncated head


# --- stop_block causes --------------------------------------------------------


def test_stop_block_cause_gate_red(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    (proj / "work.txt").write_text("dirty", encoding="utf-8")
    proc = _run_stop(proj, tmp_path, "sidgate", baseline=[], fake_fails="Ruff")
    assert json.loads(proc.stdout)["decision"] == "block"
    blocks = _of_type(_events(tmp_path, "sidgate"), "stop_block")
    assert len(blocks) == 1
    _assert_seam(blocks[0], "stop_block", "sidgate", project=proj)
    assert blocks[0]["cause"] == "gate-red"
    assert blocks[0]["outcome"] == "blocked"


def test_stop_block_cause_uncommitted(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    # Top-level path on purpose: `git status --porcelain` collapses an untracked
    # DIRECTORY to `mine/`, so a nested file would never match _dirty_paths().
    tp = _transcript(proj, edited=["session_file.py"])
    proc = _run_stop(proj, tmp_path, "siduncom", baseline=[], transcript=tp)
    assert json.loads(proc.stdout)["decision"] == "block"
    blocks = _of_type(_events(tmp_path, "siduncom"), "stop_block")
    assert [(b["cause"], b["outcome"]) for b in blocks] == [("uncommitted", "blocked")]


def _with_upstream(tmp_path: Path, proj: Path) -> None:
    bare = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", "master", str(bare)], check=True, timeout=30
    )
    _git(proj, "remote", "add", "origin", str(bare))
    _git(proj, "push", "-qu", "origin", "master")
    (proj / "committed.txt").write_text("x", encoding="utf-8")
    _git(proj, "add", "committed.txt")
    _git(proj, "commit", "-qm", "ahead")  # committed, unpushed, tree CLEAN


def test_stop_block_cause_unpushed(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    _with_upstream(tmp_path, proj)
    proc = _run_stop(proj, tmp_path, "sidpush")
    assert json.loads(proc.stdout)["decision"] == "block"
    blocks = _of_type(_events(tmp_path, "sidpush"), "stop_block")
    assert [(b["cause"], b["outcome"]) for b in blocks] == [("unpushed", "blocked")]


def test_stop_block_cause_promise_stall(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    tp = _transcript(proj, text="Phase B is green.\n\nI'll run the review pass now.")
    proc = _run_stop(proj, tmp_path, "sidstall", transcript=tp)
    assert json.loads(proc.stdout)["decision"] == "block"
    blocks = _of_type(_events(tmp_path, "sidstall"), "stop_block")
    assert [(b["cause"], b["outcome"]) for b in blocks] == [("promise-stall", "blocked")]


def test_stop_block_cause_run_record(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    env = _env(tmp_path)
    (Path(env["COMMAND_RUN_DIR"]) / "sidrun.json").write_text(
        json.dumps(
            {
                "state": "running",
                "command": "fabrik-review",
                "phase": 2,
                "phases": 4,
                "updated_ts": time.time(),
            }
        ),
        encoding="utf-8",
    )
    proc = _run_stop(proj, tmp_path, "sidrun", env=env)
    assert json.loads(proc.stdout)["decision"] == "block"
    blocks = _of_type(_events(tmp_path, "sidrun"), "stop_block")
    assert [(b["cause"], b["outcome"]) for b in blocks] == [("run-record", "blocked")]
    assert blocks[0]["command"] == "fabrik-review"


# --- the give-up branch: enforcement that warned through is still enforcement --


def test_warn_through_is_recorded_as_its_own_outcome(tmp_path: Path) -> None:
    # After CAP blocked stops the hook gives up and lets the turn end. That give-up was
    # invisible: it looked identical to a clean pass, so "enforcement worked" counted a
    # cause the agent simply outlasted.
    proj = _project(tmp_path)
    _with_upstream(tmp_path, proj)
    for _ in range(3):
        proc = _run_stop(proj, tmp_path, "sidwarn", reset=False)
        assert json.loads(proc.stdout)["decision"] == "block"
    proc = _run_stop(proj, tmp_path, "sidwarn", reset=False)  # 4th: over the cap
    assert proc.stdout.strip() == ""  # allowed through
    evs = _events(tmp_path, "sidwarn")
    warned = [b for b in _of_type(evs, "stop_block") if b["outcome"] == "warned_through"]
    assert [b["cause"] for b in warned] == ["unpushed"]
    # ...and the pass-through says so too, so a give-up turn is never counted clean.
    passes = _of_type(evs, "stop_pass")
    assert passes[-1]["outcome"] == "warned_through"
    assert passes[-1]["warned"] == ["unpushed"]


# --- stop_pass: the PER-TURN pass-through -------------------------------------


def test_stop_pass_on_a_clean_turn(tmp_path: Path) -> None:
    # Named stop_pass, not session_end: the Stop hook fires once per TURN, so a
    # session-scoped "end" name would make every turn look like a session ending.
    proj = _project(tmp_path)
    proc = _run_stop(proj, tmp_path, "sidend")
    assert proc.stdout.strip() == ""  # allowed: no decision written
    evs = _events(tmp_path, "sidend")
    assert len(_of_type(evs, "stop_pass")) == 1
    _assert_seam(_of_type(evs, "stop_pass")[0], "stop_pass", "sidend", project=proj)
    assert _of_type(evs, "stop_pass")[0]["outcome"] == "clean"
    assert _of_type(evs, "stop_block") == []  # an allowed stop is never a block
    assert _of_type(evs, "session_end") == []  # the old per-turn name is retired


def test_many_turns_emit_many_stop_passes(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    for _ in range(3):
        _run_stop(proj, tmp_path, "sidturns")
    assert len(_of_type(_events(tmp_path, "sidturns"), "stop_pass")) == 3


# --- final_block_emitted ------------------------------------------------------

_SIX_LINE_BLOCK = (
    "GATE: python scripts/final_gate.py --json → success\n"
    "DOCS UPDATED: none\n"
    "CHANGELOG: n/a\n"
    "LESSONS LEARNT: none\n"
    "DONE: shipped the emitter\n"
    "NEXT: none — terminal\n"
)


def test_final_block_emitted_when_the_six_line_block_is_seen(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    proc = _run_stop(
        proj, tmp_path, "sidblock", transcript=_transcript(proj, text="Done.\n\n" + _SIX_LINE_BLOCK)
    )
    assert proc.stdout.strip() == ""
    evs = _events(tmp_path, "sidblock")
    assert len(_of_type(evs, "final_block_emitted")) == 1
    _assert_seam(_of_type(evs, "final_block_emitted")[0], "final_block_emitted", "sidblock")


def test_final_block_split_across_text_blocks_still_counts(tmp_path: Path) -> None:
    # One assistant entry can carry several text blocks; reading only the first split
    # the 6-line block in half and under-counted the terminator contract.
    proj = _project(tmp_path)
    tp = _transcript(
        proj,
        text_blocks=["Done.\n\nGATE: … → success\nDOCS UPDATED: none\nCHANGELOG: n/a\n",
                     "LESSONS LEARNT: none\nDONE: shipped it\nNEXT: none — terminal\n"],
    )
    _run_stop(proj, tmp_path, "sidsplit", transcript=tp)
    assert len(_of_type(_events(tmp_path, "sidsplit"), "final_block_emitted")) == 1


def test_state_footer_is_not_a_final_block(tmp_path: Path) -> None:
    # The two-line STATE/NEXT footer is the CONVERSATIONAL terminator — counting it as
    # the 6-line block would inflate the completion metric with every chat turn.
    proj = _project(tmp_path)
    footer = "STATE: mid-plan, phase 2 of 4\nNEXT: awaiting your reply\n"
    _run_stop(proj, tmp_path, "sidfooter", transcript=_transcript(proj, text=footer))
    assert _of_type(_events(tmp_path, "sidfooter"), "final_block_emitted") == []


def test_a_blocked_turn_emits_no_final_block(tmp_path: Path) -> None:
    # THE RETRY MULTIPLICATION: a turn that gets blocked N times used to emit
    # final_block_emitted on every retry, so one task terminator counted N times.
    # Message-shaped events belong to the exit that actually ENDS the turn.
    proj = _project(tmp_path)
    _with_upstream(tmp_path, proj)
    tp = _transcript(proj, text="Done.\n\n" + _SIX_LINE_BLOCK)
    for _ in range(3):
        proc = _run_stop(proj, tmp_path, "sidretry", transcript=tp, reset=False)
        assert json.loads(proc.stdout)["decision"] == "block"
    assert _of_type(_events(tmp_path, "sidretry"), "final_block_emitted") == []
    _run_stop(proj, tmp_path, "sidretry", transcript=tp, reset=False)  # cap → allowed
    assert len(_of_type(_events(tmp_path, "sidretry"), "final_block_emitted")) == 1


# --- operator_override: only a WAIVED enforcement cause -----------------------


def test_operator_override_when_a_human_gate_waives_a_real_stall(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    # 2026-08-29 hardening: the waiver line must also name a HARD-STOP class
    text = "Phase B is green.\n\nI'll run the deploy pass — on your approval of Gate 2.\n"
    proc = _run_stop(proj, tmp_path, "sidover", transcript=_transcript(proj, text=text))
    assert proc.stdout.strip() == ""  # the marker waved the stall through
    overrides = _of_type(_events(tmp_path, "sidover"), "operator_override")
    assert len(overrides) == 1
    _assert_seam(overrides[0], "operator_override", "sidover")
    assert overrides[0]["kind"] == "human-gate"
    assert overrides[0]["marker"]


def test_operator_override_when_a_blocked_escalation_waives_a_real_stall(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    # "I'll run the test suite" carries a real action object — without one the promise
    # guard never considers it a cause, so there would be nothing to waive.
    text = (
        "I'll run the test suite next.\n\n"
        "BLOCKED: postgres-main unreachable — searched: docs/, .env — missing: DSN\n"
    )
    _run_stop(proj, tmp_path, "sidesc", transcript=_transcript(proj, text=text))
    overrides = _of_type(_events(tmp_path, "sidesc"), "operator_override")
    assert [o["kind"] for o in overrides] == ["blocked-escalation"]


def test_no_override_without_an_enforcement_cause_to_waive(tmp_path: Path) -> None:
    """The four reproduced false positives: sanctioned-skip VOCABULARY with no stall.

    An override is 'a cause fired and a marker waved it through'. Matching the marker
    alone made every routine operator-gated task end an 'override', which is the single
    most common way a fabrik turn legitimately finishes — the metric would have been
    almost entirely noise.
    """
    proj = _project(tmp_path)
    cases = {
        # 1. the mandated FINAL OUTPUT footer of any operator-gated task
        "fp_footer": "Readiness verified.\n\nNEXT: operator decision: approve the deploy (Gate 2).\n",
        # 2. a BLOCKED escalation that names no un-run own work
        "fp_blocked": "BLOCKED: vault sealed — searched: docs/, .env — missing: unseal key\n",
        # 3. a message DISCUSSING the vocabulary
        "fp_quoted": 'The guard exempts any line containing "operator decision" or "Gate 2".\n',
        # 4. a plain hand-back naming its human gate
        "fp_await": "The diff is reviewed and committed. Awaiting your approval before the deploy.\n",
    }
    for sid, text in cases.items():
        proc = _run_stop(proj, tmp_path, sid, transcript=_transcript(proj, text=text))
        assert proc.stdout.strip() == "", sid  # none of these is a stall
        assert _of_type(_events(tmp_path, sid), "operator_override") == [], sid


def test_a_blocked_stall_is_not_an_override(tmp_path: Path) -> None:
    # A stall that was NOT waived is enforcement working, not an override.
    proj = _project(tmp_path)
    tp = _transcript(proj, text="I'll run the review pass now.")
    _run_stop(proj, tmp_path, "sidnowaive", transcript=tp)
    assert _of_type(_events(tmp_path, "sidnowaive"), "operator_override") == []


# --- honesty: an unattributable event is never a shared bucket -----------------


def test_absent_session_id_lands_in_unknown_not_a_shared_bucket(tmp_path: Path) -> None:
    # The Stop hook's own internal default for a missing id is the literal
    # "nosession" — a SHARED name every id-less session would merge into. The
    # emitter must resolve to `unknown` (the collector's unclassified bucket).
    proj = _project(tmp_path)
    _run_stop(proj, tmp_path, None)
    assert _of_type(_events(tmp_path, "unknown"), "stop_pass")
    assert _events(tmp_path, "nosession") == []


# --- fail-open at the import layer (the fleet-safety proof) --------------------


def _assert_identical(control, live) -> None:
    assert control.returncode == live.returncode == 0
    assert control.stdout == live.stdout
    assert control.stderr == live.stderr, "the emitter must not leak onto the hook's stderr"


def test_orient_is_byte_identical_without_the_module(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    live_env = _env(tmp_path)
    live = _run_orient(proj, tmp_path, "sidbc1", env=live_env)
    control = _run_orient(proj, tmp_path, "sidbc1", env=_no_module_env(tmp_path, live_env))
    _assert_identical(control, live)
    # ...and the two runs really WERE the two states: exactly the live one emitted.
    assert len(_of_type(_events(tmp_path, "sidbc1"), "session_start")) == 1


def test_stop_is_byte_identical_without_the_module(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    (proj / "work.txt").write_text("dirty", encoding="utf-8")
    live_env = _env(tmp_path)
    live = _run_stop(proj, tmp_path, "sidbc2", baseline=[], fake_fails="Ruff", env=live_env)
    control = _run_stop(
        proj,
        tmp_path,
        "sidbc2",
        baseline=[],
        fake_fails="Ruff",
        env=_no_module_env(tmp_path, live_env),
    )
    _assert_identical(control, live)
    assert json.loads(live.stdout)["decision"] == "block"
    assert len(_of_type(_events(tmp_path, "sidbc2"), "stop_block")) == 1


def test_stop_is_byte_identical_when_the_emitter_raises(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    live_env = _env(tmp_path)
    tp = _transcript(proj, text="Done.\n\n" + _SIX_LINE_BLOCK)
    live = _run_stop(proj, tmp_path, "sidbc3", transcript=tp, env=live_env)
    boom = _run_stop(
        proj, tmp_path, "sidbc3", transcript=tp, env=_exploding_env(tmp_path, live_env)
    )
    _assert_identical(boom, live)


def test_module_absent_means_no_transcript_read(tmp_path: Path) -> None:
    # Guard ORDER: the message-event helper must check the module BEFORE touching the
    # transcript, so a project without the sensor pays nothing for it. An unreadable
    # transcript path is the cheapest observable proxy — with the guard first, the
    # helper never reaches the read.
    proj = _project(tmp_path)
    tp = _transcript(proj, text="Done.\n\n" + _SIX_LINE_BLOCK)
    live_env = _env(tmp_path)
    control = _run_stop(
        proj, tmp_path, "sidnoread", transcript=tp, env=_no_module_env(tmp_path, live_env)
    )
    assert control.returncode == 0
    assert _events(tmp_path, "sidnoread") == []


# --- review fix-wave: adjudicated findings, red-first -------------------------


def test_one_override_event_carries_every_waived_stall() -> None:
    """P2: two stalls waived in one turn emit ONE operator_override carrying
    stalls=len(waived) + the kinds list — recording only waived[0] under-counted
    the override ledger."""
    import importlib.util  # noqa: PLC0415

    spec = importlib.util.spec_from_file_location("fgs_p2_probe", STOP)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    captured: list[tuple[str, dict]] = []
    mod._kaizen = lambda event, sid, **fields: captured.append((event, fields))
    mod.kaizen_events = True  # truthy import guard — the seam under test is below it
    waived = [("human-gate", "on your approval"), ("blocked-escalation", "BLOCKED: x")]
    mod._kaizen_pass("sid-p2", "", waived, [])
    overrides = [fields for event, fields in captured if event == "operator_override"]
    assert len(overrides) == 1, "one turn, ONE override event"
    assert overrides[0].get("stalls") == 2, "every waived stall must be counted"
    assert overrides[0].get("kinds") == ["human-gate", "blocked-escalation"]
    assert overrides[0].get("marker") == "on your approval", "first marker still carried"
