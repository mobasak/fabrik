"""Behavior contract for the thread-anchor register (scripts/thread_anchor.py).

Why it exists, measured 2026-08-29 on one live session: 905 ``NEXT:`` lines emitted, ZERO read
back, and a thread carried by 85 consecutive NEXT: lines ("corpus audit — command N of 31") was
silently dropped the moment an operator question arrived — 10 NEXT: lines later it had vanished,
and nothing anywhere could notice. NEXT: was a single slot, write-only, and died at compaction.

The register fixes the MECHANISM, not the discipline: the Stop hook harvests what agents already
emit (no new obligation), and the prompt hooks re-inject open anchors the same way mail_notify.py
provably gets mail read. Every test here is a behavior an agent actually needs, not coverage.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "thread_anchor.py"


def run(args: list[str], stdin: str = "", env_dir: Path | None = None) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin,
        capture_output=True,
        text=True,
        env={"THREAD_ANCHOR_DIR": str(env_dir)} if env_dir else None,
    )
    return proc.returncode, proc.stdout


def harvest(text: str, d: Path, session: str = "s1") -> None:
    rc, _ = run(["harvest", "--session", session], stdin=text, env_dir=d)
    assert rc == 0


def line(d: Path, session: str = "s1") -> str:
    rc, out = run(["line", "--session", session], env_dir=d)
    assert rc == 0
    return out


# ── The founding defect, reproduced end to end ────────────────────────────────────────────────
def test_a_tangent_does_not_erase_a_long_running_anchor(tmp_path):
    """The live failure: 85 NEXT: lines carried the audit, one operator question wiped it."""
    harvest("done stuff\nNEXT: the corpus audit — command 14 of 31 — /fabrik-user-test", tmp_path)
    # The tangent: an operator question produces an unrelated NEXT.
    harvest("answered the CI question\nNEXT: disable the workflows in the three repos", tmp_path)
    out = line(tmp_path)
    assert "14 of 31" in out, f"the anchor died on a tangent — the exact founding defect: {out!r}"
    assert "three repos" in out, "the tangent's own NEXT must also survive as the latest successor"


def test_progress_updates_the_anchor_instead_of_stacking_duplicates(tmp_path):
    """'command 14 of 31' then 'command 15 of 31' is ONE thread advancing, not two threads."""
    harvest("NEXT: corpus audit — command 14 of 31", tmp_path)
    harvest("NEXT: corpus audit — command 15 of 31", tmp_path)
    out = line(tmp_path)
    assert "15 of 31" in out
    assert "14 of 31" not in out, f"stale progress stacked as a second anchor: {out!r}"


def test_plan_and_epic_paths_are_anchors(tmp_path):
    harvest("NEXT: resume docs/development/plans/2026-08-29-plan-1-thread.md phase B", tmp_path)
    harvest("NEXT: reply to fleet's mail", tmp_path)  # tangent
    assert "2026-08-29-plan-1-thread" in line(tmp_path)


def test_done_closes_an_anchor_and_silence_returns(tmp_path):
    harvest("NEXT: corpus audit — command 14 of 31", tmp_path)
    rc, _ = run(["done", "--session", "s1", "--match", "corpus audit"], env_dir=tmp_path)
    assert rc == 0
    out = line(tmp_path)
    assert "14 of 31" not in out, f"a closed anchor kept resurfacing: {out!r}"


def test_no_state_means_total_silence(tmp_path):
    """Anti-noise: an empty register must print NOTHING — a block that fires on every trivial
    turn becomes the wallpaper that killed CI."""
    assert line(tmp_path) == ""


def test_a_plain_next_is_not_promoted_to_an_anchor(tmp_path):
    """Ordinary successors roll; only long-running shapes persist. Without this, every turn
    mints an anchor and the injection becomes an unreadable scroll."""
    harvest("NEXT: fix the typo in the README", tmp_path)
    harvest("NEXT: answer the operator", tmp_path)
    out = line(tmp_path)
    assert "typo" not in out, f"a one-shot NEXT was promoted to an anchor: {out!r}"


def test_output_is_capped_at_four_lines(tmp_path):
    for i in range(9):
        harvest(f"NEXT: sweep {i} — item 1 of {20 + i}", tmp_path)
    out = line(tmp_path)
    assert 0 < len(out.strip().splitlines()) <= 6, out  # header + <=4 anchors + latest


def test_state_survives_a_new_process_and_is_session_scoped(tmp_path):
    """Disk, not context — this is the compaction survival. And session-scoped, because three
    concurrent sessions share this repo and must not see each other's threads."""
    harvest("NEXT: cert board TC3 of 12", tmp_path, session="a")
    assert "TC3" in line(tmp_path, session="a") or "3 of 12" in line(tmp_path, session="a")
    assert line(tmp_path, session="b") == "", "session b saw session a's threads"


def test_hook_mode_reads_session_from_stdin_json(tmp_path):
    """UserPromptSubmit/SessionStart pass a JSON payload on stdin, not a --session flag."""
    harvest("NEXT: epic docs/development/epics/2026-08-29-epic-9-sso.md ticket 2 of 7", tmp_path)
    rc, out = run(["line", "--hook"], stdin=json.dumps({"session_id": "s1"}), env_dir=tmp_path)
    assert rc == 0 and "epic-9-sso" in out, out


def test_harvest_is_failopen_on_garbage(tmp_path):
    """Wired into the Stop hook: a crash here would block every end-of-turn in ~46 repos."""
    rc, _ = run(
        ["harvest", "--session", "s1"], stdin="\x00\xff not json not text \x00", env_dir=tmp_path
    )
    assert rc == 0


def test_a_reworded_suffix_does_not_mint_a_second_anchor(tmp_path):
    """Found live an hour after shipping: the injected block showed the SAME corpus-audit thread
    twice, because appending commentary ("… (now also held by the register)") changed the
    full-text key. Identity must rest on the anchor's PREFIX, where the stable subject lives."""
    harvest(
        "NEXT: the corpus audit — command 14 of 31 — /fabrik-user-test against the checklist",
        tmp_path,
    )
    harvest(
        "NEXT: the corpus audit — command 14 of 31 — /fabrik-user-test against the checklist (now held by the register)",
        tmp_path,
    )
    out = line(tmp_path)
    assert out.count("corpus audit") == 1, f"reworded suffix minted a duplicate anchor: {out!r}"


def test_done_and_line_never_block_on_an_open_stdin(tmp_path):
    """Found live: `done --match …` run from an agent's shell (stdin open, not a tty, nothing
    piped) hung forever in sys.stdin.read(). Only `harvest` and `--hook` consume stdin."""
    import subprocess as sp

    for args in (["done", "--session", "s1", "--match", "x"], ["line", "--session", "s1"]):
        proc = sp.Popen(
            [sys.executable, str(SCRIPT), *args],
            stdin=sp.PIPE,
            stdout=sp.PIPE,
            stderr=sp.PIPE,
            text=True,
            env={"THREAD_ANCHOR_DIR": str(tmp_path)},
        )
        try:
            proc.communicate(timeout=5)  # stdin PIPE left open until communicate closes it
        except sp.TimeoutExpired:
            proc.kill()
            raise AssertionError(f"{args[0]} blocked on stdin")


def test_divergence_inside_the_prefix_window_still_dedupes(tmp_path):
    """Second live recurrence: truncating the key to 72 chars only helped when the texts
    diverged AFTER char 72 — "…/fabrik-user-test" vs "…/fabrik-user-test (held by the
    register…)" diverge at ~54 and duplicated again. The CLASS fix is containment: a new
    anchor whose key extends (or is extended by) an existing key is the same thread."""
    harvest("NEXT: the corpus audit — command 14 of 31 — /fabrik-user-test", tmp_path)
    harvest(
        "NEXT: the corpus audit — command 14 of 31 — /fabrik-user-test (held by the register; resumes on your word)",
        tmp_path,
    )
    harvest("NEXT: the corpus audit — command 15 of 31 — /fabrik-flows", tmp_path)
    out = line(tmp_path)
    assert out.count("corpus audit") == 1, f"still duplicating: {out!r}"
    assert "15 of 31" in out, "the newest progress must win"


# ── 01M1J6HB + 01M1HJEH (2026-09-03): a silent no-op that reads as success — seen RED first ──


def test_done_reports_what_it_closed_and_refuses_an_empty_session(tmp_path):
    harvest("NEXT: command 3 of 31 — tryton release", tmp_path, session="s1")
    rc, out = run(["done", "--match", "zzz-nope"], env_dir=tmp_path)  # no --session, no env
    assert rc != 0 and not (tmp_path / "nosession.json").exists()
    rc, out = run(["done", "--session", "s1", "--match", "zzz-nope"], env_dir=tmp_path)
    assert rc == 0 and "no anchor matched" in out
    rc, out = run(["done", "--session", "s1", "--match", "tryton"], env_dir=tmp_path)
    assert rc == 0 and "closed 1 anchor" in out
    assert "tryton" not in run(["line", "--session", "s1"], env_dir=tmp_path)[1]


def test_hook_line_prints_the_session_in_the_close_command(tmp_path):
    harvest("NEXT: command 7 of 31 — something open", tmp_path, session="s9")
    assert "done --session s9 --match" in run(["line", "--session", "s9"], env_dir=tmp_path)[1]


# ── T04 (spec § C3): WHERE YOU ARE on compact, the DECISION harvest and clear, the 72 h fold ──

_DECISION_TEXT = (
    "Certified build is ready.\n\n"
    "DECISION NEEDED (ground: gate)\n"
    "- Question: Deploy the certified build to production now?\n"
    "- Why it is yours: gate — Gate 2, a destructive/irreversible action needing authorisation.\n"
    "- Options: A — deploy now · B — hold for one more smoke pass\n"
    "- Recommendation: A — the certification gauntlet already passed.\n\n"
    "NEXT: operator decision — see DECISION NEEDED above"
)
_BUILTINS = ("/compact", "/context", "/cost", "/model", "/autocompact", "/clear", "/help")


def _env(tmp_path: Path) -> dict[str, str]:
    """Hermetic: state, run records, HOME and TMPDIR under tmp_path; git reads no user config."""
    for sub in ("home", "runs", "threads", "tmp"):
        (tmp_path / sub).mkdir(exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path / "home"),
        "TMPDIR": str(tmp_path / "tmp"),
        "THREAD_ANCHOR_DIR": str(tmp_path / "threads"),
        "COMMAND_RUN_DIR": str(tmp_path / "runs"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }


def run3(
    args: list[str], env: dict[str, str], stdin: str = "", script: Path = SCRIPT
) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _hook_line(env: dict[str, str], payload: dict, script: Path = SCRIPT) -> tuple[int, str, str]:
    return run3(["line", "--hook"], env, stdin=json.dumps(payload), script=script)


def _state(env: dict[str, str], sid: str) -> dict:
    return json.loads((Path(env["THREAD_ANCHOR_DIR"]) / f"{sid}.json").read_text(encoding="utf-8"))


def _write_state(env: dict[str, str], sid: str, state: dict) -> None:
    (Path(env["THREAD_ANCHOR_DIR"]) / f"{sid}.json").write_text(json.dumps(state), encoding="utf-8")


def _anchor(text: str, hours: float) -> dict:
    return {"key": text.lower(), "text": text, "ts": time.time() - hours * 3600}


def _git(cwd: Path, env: dict[str, str], *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True
    ).stdout


def _repo_with_upstream(tmp_path: Path, env: dict[str, str]) -> Path:
    up = tmp_path / "up.git"
    _git(tmp_path, env, "init", "-q", "--bare", str(up))
    work = tmp_path / "work"
    _git(tmp_path, env, "init", "-q", str(work))
    (work / "README").write_text("seed\n", encoding="utf-8")
    _git(work, env, "add", "README")
    _git(work, env, "commit", "-q", "-m", "seed")
    _git(work, env, "remote", "add", "origin", str(up))
    _git(work, env, "push", "-q", "-u", "origin", "HEAD")
    return work.resolve()


def _transcript(tmp_path: Path, edited: list[Path], final_text: str = "") -> Path:
    """A session transcript whose Edit tool_uses name `edited`, stamped now."""
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entries: list[dict] = [
        {
            "type": "assistant",
            "timestamp": stamp,
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": f"t{i}",
                        "name": "Edit",
                        "input": {"file_path": str(p)},
                    }
                ]
            },
        }
        for i, p in enumerate(edited)
    ]
    if final_text:
        entries.append(
            {"type": "assistant", "message": {"content": [{"type": "text", "text": final_text}]}}
        )
    tp = tmp_path / "transcript.jsonl"
    tp.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return tp


def _running_record(env: dict[str, str], sid: str, state: str = "running") -> None:
    """The fields `scripts/command_run.py` writes at `start`/`step`/`round`."""
    rec = {
        "session_id": sid,
        "command": "fabrik-execute-plan",
        "phases": 5,
        "phase": 3,
        "phase_title": "wire the harvest",
        "terminal": "every ticket merged and reviewed",
        "surface": "scripts/thread_anchor.py",
        "state": state,
        "rounds": [{"n": 1}, {"n": 2}],
        "updated_ts": time.time(),
    }
    (Path(env["COMMAND_RUN_DIR"]) / f"{sid}.json").write_text(json.dumps(rec), encoding="utf-8")


def test_where_block_lists_only_this_sessions_commits(tmp_path):
    """The T03 → T04 seam: `session_unpushed` scoped to THIS transcript's edits — a sibling's
    unpushed commit on the same branch is never listed as this session's (spec § C3 item 4)."""
    env = _env(tmp_path)
    work = _repo_with_upstream(tmp_path, env)
    for name, msg in (("mine.py", "mine: the harvest"), ("sib.py", "sib: their fold")):
        (work / name).write_text("x\n", encoding="utf-8")
        _git(work, env, "add", name)
        _git(work, env, "commit", "-q", "-m", msg)
    (work / "mine_dirty.py").write_text("wip\n", encoding="utf-8")
    (work / "sib_dirty.py").write_text("wip\n", encoding="utf-8")
    tp = _transcript(tmp_path, [work / "mine.py", work / "mine_dirty.py"])
    sid = "sess-where"
    _running_record(env, sid)
    assert run3(["harvest", "--session", sid, "--decision-ok"], env, stdin=_DECISION_TEXT)[0] == 0
    run3(["harvest", "--session", sid], env, stdin="NEXT: resume phase C of the plan")

    rc, out, err = _hook_line(
        env,
        {
            "session_id": sid,
            "transcript_path": str(tp),
            "cwd": str(work),
            "source": "compact",
            "hook_event_name": "SessionStart",
        },
    )
    assert rc == 0, err
    assert "WHERE YOU ARE" in out, out
    assert "## 🧵 OPEN THREADS" not in out, f"the usual block printed beside WHERE YOU ARE: {out!r}"
    assert "mine: the harvest" in out, out
    assert "sib: their fold" not in out, f"a sibling's commit listed as this session's: {out!r}"
    assert "mine_dirty.py" in out and "sib_dirty.py" not in out, out
    assert "fabrik-execute-plan" in out and "resume phase C" in out, out
    assert "Deploy the certified build" in out, out


def test_a_refused_block_is_never_stored(tmp_path):
    """The T03 → T04 seam: the hook passes --decision-ok only on an accepted block; without it
    the harvest stores NO block (C-O8's twin, A-O30) — while the NEXT: line still harvests."""
    env = _env(tmp_path)
    assert run3(["harvest", "--session", "s-ref"], env, stdin=_DECISION_TEXT)[0] == 0
    st = _state(env, "s-ref")
    assert not st.get("decision"), f"a refused block was stored: {st!r}"
    assert st["last_next"]["text"].startswith("operator decision")
    rc = run3(["harvest", "--session", "s-ok", "--decision-ok"], env, stdin=_DECISION_TEXT)[0]
    assert rc == 0
    assert "Deploy the certified build" in _state(env, "s-ok")["decision"]["text"]


def test_where_block_shows_a_live_run_and_not_a_stopped_one(tmp_path):
    env = _env(tmp_path)
    run3(["harvest", "--session", "s-run"], env, stdin="NEXT: keep going")
    _running_record(env, "s-run")
    payload = {
        "session_id": "s-run",
        "source": "compact",
        "hook_event_name": "SessionStart",
        "cwd": str(tmp_path),
    }
    out = _hook_line(env, payload)[1]
    for want in (
        "/fabrik-execute-plan",
        "phase 3/5 (wire the harvest)",
        "round 2",
        "every ticket merged and reviewed",
        "scripts/thread_anchor.py",
    ):
        assert want in out, (want, out)
    _running_record(env, "s-run", state="done")
    out = _hook_line(env, payload)[1]
    assert "WHERE YOU ARE" in out and "fabrik-execute-plan" not in out, out


def _open_decision(env: dict[str, str], sid: str) -> None:
    assert run3(["harvest", "--session", sid, "--decision-ok"], env, stdin=_DECISION_TEXT)[0] == 0
    assert _state(env, sid).get("decision")


@pytest.mark.parametrize("prompt", [*_BUILTINS, " /model", "/compact keep the plan state"])
def test_a_builtin_slash_command_does_not_clear_the_decision(tmp_path, prompt):
    env = _env(tmp_path)
    _open_decision(env, "s-b")
    payload = {"session_id": "s-b", "hook_event_name": "UserPromptSubmit", "prompt": prompt}
    rc, _, _ = _hook_line(env, payload)
    assert rc == 0 and _state(env, "s-b").get("decision"), f"{prompt!r} cleared the block"


@pytest.mark.parametrize(
    "prompt", ["A, deploy it", "/fabrik-deploy prod", "/contextualize x", "/helpme", ""]
)
def test_a_plain_answer_or_a_custom_command_clears_the_decision(tmp_path, prompt):
    """A-O41/A-O42: the WHOLE first token is matched — `/contextualize` shares `/context`'s
    prefix and is a custom command, so it clears."""
    env = _env(tmp_path)
    _open_decision(env, "s-c")
    payload = {"session_id": "s-c", "hook_event_name": "UserPromptSubmit", "prompt": prompt}
    rc, _, _ = _hook_line(env, payload)
    assert rc == 0 and not _state(env, "s-c").get("decision"), f"{prompt!r} left the block open"


def test_the_prompt_time_reharvest_never_restores_a_cleared_block(tmp_path):
    env = _env(tmp_path)
    _open_decision(env, "s-r")
    tp = _transcript(tmp_path, [], final_text=_DECISION_TEXT)  # the previous turn: the block
    rc, _, _ = _hook_line(
        env,
        {
            "session_id": "s-r",
            "hook_event_name": "UserPromptSubmit",
            "prompt": "B, hold",
            "transcript_path": str(tp),
        },
    )
    assert rc == 0 and not _state(env, "s-r").get("decision")
    # and a later SessionStart pass over the same transcript does not resurrect it either
    _hook_line(
        env,
        {
            "session_id": "s-r",
            "hook_event_name": "SessionStart",
            "source": "resume",
            "transcript_path": str(tp),
        },
    )
    assert not _state(env, "s-r").get("decision")


def test_anchors_older_than_72h_fold_into_one_line_and_are_kept(tmp_path):
    env = _env(tmp_path)
    anchors = [_anchor("young thread — item 1 of 9", 71), _anchor("old thread — item 2 of 9", 73)]
    _write_state(env, "s-f", {"anchors": anchors, "last_next": None})
    rc, out, _ = run3(["line", "--session", "s-f"], env)
    assert rc == 0 and "young thread — item 1 of 9" in out, out
    assert "old thread" not in out, f"a 73 h anchor printed in full: {out!r}"
    assert "1 older thread(s), oldest 73h" in out, out
    assert len(_state(env, "s-f")["anchors"]) == 2, "the fold deleted an anchor"


def test_the_fold_line_close_command_carries_the_session(tmp_path):
    env = _env(tmp_path)
    _write_state(
        env, "s-cl", {"anchors": [_anchor("old thread — item 2 of 9", 90)], "last_next": None}
    )
    out = run3(["line", "--session", "s-cl"], env)[1]
    want = "close with python3 scripts/thread_anchor.py done --session s-cl --match <substr>"
    assert want in out, out


def test_the_young_cap_evicts_the_oldest_young_anchor_not_a_standing_one(tmp_path):
    """The founding case: a standing thread paused behind days of tangents (A-O13). The old cap
    dropped by LIST POSITION, so the oldest — the standing one — died first, silently."""
    env = _env(tmp_path)
    anchors = [_anchor("standing audit — command 14 of 31", 100)]
    anchors += [_anchor(f"tangent {i} — item {i} of 99", 50 - i) for i in range(12)]
    _write_state(env, "s-y", {"anchors": anchors, "last_next": None})
    run3(["harvest", "--session", "s-y"], env, stdin="NEXT: tangent new — item 1 of 5")
    texts = [a["text"] for a in _state(env, "s-y")["anchors"]]
    assert "standing audit — command 14 of 31" in texts, texts
    assert "tangent 0 — item 0 of 99" not in texts, "the oldest young anchor was not evicted"
    assert "tangent new — item 1 of 5" in texts
    out = run3(["line", "--session", "s-y"], env)[1]
    assert "1 older thread(s)" in out and "… 1 dropped over the cap" in out, out


def test_a_young_cap_eviction_shows_with_no_folded_anchor(tmp_path):
    """A-O19: the Stop-side harvest's stderr is seen by nobody, so the fold line is the only
    place an eviction surfaces — it must print even when no anchor is older than 72 h."""
    env = _env(tmp_path)
    anchors = [_anchor(f"tangent {i} — item {i} of 99", 50 - i) for i in range(12)]
    _write_state(env, "s-n", {"anchors": anchors, "last_next": None})
    run3(["harvest", "--session", "s-n"], env, stdin="NEXT: tangent new — item 1 of 5")
    out = run3(["line", "--session", "s-n"], env)[1]
    assert "… 1 dropped over the cap" in out, out
    assert "older thread(s)" not in out, out


def test_a_missing_hook_omits_its_items_and_never_crashes(tmp_path):
    """The script runs on every SessionStart in ~46 repos: a failed hook import omits the items
    that need it, says so in ONE stderr line each, never a traceback, never a non-zero exit."""
    env = _env(tmp_path)
    lone = tmp_path / "lone" / "scripts" / "thread_anchor.py"
    lone.parent.mkdir(parents=True)
    lone.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    run3(["harvest", "--session", "s-m"], env, stdin="NEXT: resume phase C", script=lone)
    _running_record(env, "s-m")
    rc, out, err = _hook_line(
        env, {"session_id": "s-m", "source": "compact", "cwd": str(tmp_path)}, script=lone
    )
    assert rc == 0 and "Traceback" not in err, err
    assert "WHERE YOU ARE" in out and "resume phase C" in out, out
    assert "fabrik-execute-plan" not in out
    lines = err.strip().splitlines()
    assert lines and all(ln.startswith("thread_anchor:") for ln in lines), err
