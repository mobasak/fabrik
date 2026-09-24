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
    args: list[str],
    env: dict[str, str],
    stdin: str = "",
    script: Path = SCRIPT,
    cwd: Path | None = None,
) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        cwd=cwd,
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


@pytest.mark.parametrize(
    "prompt",
    [
        *_BUILTINS,
        " /model",
        "/compact keep the plan state",
        # A-O8: UI/local commands reach UserPromptSubmit too and are not an answer — matched
        # case-insensitively on the whole first token.
        "/status",
        "/RESUME",
        "/terminal-setup",
        "/Vim",
        "/permissions",
        # round 2 (A-O5): the rest of the closed list
        "/exit",
        "/add-dir",
        "/Plugin install x",
        "/bashes",
        "/output-style",
        "/release-notes",
        "/theme",
        "/privacy-settings",
        "/upgrade",
    ],
)
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


# ── T04 /fabrik-review round 1 ─────────────────────────────────────────────────────────────────


def _ta_module():
    """The script imported in-process (a fresh module per call), for the tests that must stub a
    seam — the time budget, the lost-update window."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(f"thread_anchor_t04_{time.time_ns()}", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_where_block_prints_the_last_next_once(tmp_path):
    """A-S1: the last NEXT is also the newest anchor — WHERE YOU ARE de-duplicates it exactly as
    the usual block does, instead of printing it as item 2 AND item 5."""
    env = _env(tmp_path)
    run3(["harvest", "--session", "s-d"], env, stdin="NEXT: resume phase C of the plan")
    out = _hook_line(env, {"session_id": "s-d", "source": "compact", "cwd": str(tmp_path)})[1]
    assert out.count("resume phase C of the plan") == 1, out


@pytest.mark.parametrize(
    "footer",
    [
        "**NEXT:** resume phase C of the plan",
        "**NEXT**: resume phase C of the plan",
        "- NEXT: resume phase C of the plan",
        "> NEXT: resume phase C of the plan",
    ],
)
def test_a_bold_or_bulleted_next_is_harvested_like_a_plain_one(tmp_path, footer):
    """T06 docs review, C-O6: the Stop hook reads a bold, bulleted or quoted `NEXT:` as the footer
    (`final_gate_stop._NEXT_LINE_RE`) but the harvest read only a plain `^NEXT:`, so after a
    compaction WHERE YOU ARE showed an older NEXT than the one the agent last wrote."""
    env = _env(tmp_path)
    run3(["harvest", "--session", "s-b"], env, stdin="NEXT: an older step, already done")
    run3(["harvest", "--session", "s-b"], env, stdin=f"work done\n\n{footer}\n")
    out = _hook_line(env, {"session_id": "s-b", "source": "compact", "cwd": str(tmp_path)})[1]
    assert "resume phase C of the plan" in out, out
    assert "an older step" not in out, out
    assert "**" not in out.split("resume phase C", 1)[1].split("\n", 1)[0], out


@pytest.mark.parametrize(
    ("message", "want", "not_want"),
    [
        # a quoted recap AFTER the real footer is someone else's words, never the operative NEXT
        (
            "done\n\nNEXT: resume phase C\n\n> NEXT: an older step, quoted\n",
            "resume phase C",
            "an older step",
        ),
        # a NEXT inside a fenced example is not a footer
        (
            "NEXT: resume phase C\n\n```\nNEXT: an example in a fence\n```\n",
            "resume phase C",
            "an example",
        ),
        # four spaces of indent is a markdown code block
        (
            "NEXT: resume phase C\n\n    NEXT: an indented example\n",
            "resume phase C",
            "an indented",
        ),
        # a value ending in `*` or `_` keeps it; only a closing bold marker is stripped
        ("NEXT: grep docs/*\n", "grep docs/*", None),
        ("NEXT: rename foo_\n", "rename foo_", None),
        # closing pass 2 (A-NEW1..3, A-H4): an unclosed fence is not a fence; CRLF; `__` bold;
        # an empty bold NEXT is no NEXT
        ("done\n```\nsnippet never closed\nNEXT: resume phase C\n", "resume phase C", None),
        ("NEXT: an older step\r\n\r\nNEXT: resume phase C\r\n", "resume phase C", "\r"),
        ("__NEXT:__ resume phase C\n", "resume phase C", "__ resume"),
        # pass 3 (A-S2 residue): an inner bold span keeps its own closer
        ("**NEXT: keep **phase C** open\n", "keep **phase C** open", None),
        ("**NEXT: resume **phase C**\n", "resume **phase C**", None),
        (
            "NEXT: resume phase C\n\n**NEXT:**\n",
            "resume phase C",
            "NEXT (before the compaction): *",
        ),
        ("**NEXT: resume phase C**\n", "resume phase C", "phase C**"),
    ],
)
def test_the_widened_next_harvest_reads_only_the_footer(tmp_path, message, want, not_want):
    """/fabrik-review round 1 of the bold-NEXT fix (A-S1, A-S2, A-S4, A-H3): widening the match to the
    hook's footer shapes must not harvest a quoted, fenced or indented NEXT, nor eat a trailing
    `*`/`_` that belongs to the value."""
    env = _env(tmp_path)
    run3(["harvest", "--session", "s-w"], env, stdin=message)
    out = _hook_line(env, {"session_id": "s-w", "source": "compact", "cwd": str(tmp_path)})[1]
    assert want in out, out
    if not_want:
        assert not_want not in out, out


def test_a_crlf_next_is_stored_without_its_carriage_return():
    """Closing pass 2 (A-NEW3): the old `\\s*$` dropped the `\\r` of a CRLF line; the widened
    match must too — the WHERE render hides it, so the harvested VALUE is what is asserted."""
    assert _ta_module()._next_values("NEXT: step one\r\n\r\nNEXT: resume phase C\r\n") == [
        "step one",
        "resume phase C",
    ]


def test_a_concurrent_harvest_never_loses_a_clear(tmp_path, monkeypatch):
    """A-S2: `_load`/`_save` was an unlocked read-modify-write. A Stop-side harvest that loaded the
    state before the operator's answer cleared the DECISION wrote the stale block back: the
    answered decision reopened. The clear runs in a second PROCESS inside the harvest's window."""
    env = _env(tmp_path)
    _open_decision(env, "s-lk")
    for k in ("THREAD_ANCHOR_DIR", "COMMAND_RUN_DIR", "HOME", "TMPDIR"):
        monkeypatch.setenv(k, env[k])
    ta = _ta_module()
    real_load = ta._load
    clearer: list[subprocess.Popen] = []

    def racing_load(session: str) -> dict:
        state = real_load(session)
        if not clearer:  # the harvest has READ the open block; now the operator answers
            clearer.append(
                subprocess.Popen(
                    [sys.executable, str(SCRIPT), "line", "--hook"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    env=env,
                )
            )
            clearer[0].stdin.write(
                json.dumps(
                    {"session_id": "s-lk", "hook_event_name": "UserPromptSubmit", "prompt": "B"}
                )
            )
            clearer[0].stdin.close()
            time.sleep(0.5)  # the clear lands (unlocked) or waits on the lock (locked)
        return state

    monkeypatch.setattr(ta, "_load", racing_load)
    ta.cmd_harvest("s-lk", "NEXT: keep going — item 2 of 9")
    assert clearer and clearer[0].wait(timeout=10) == 0
    st = _state(env, "s-lk")
    assert not st.get("decision"), "the operator's answer was lost to a concurrent harvest"
    assert st["last_next"]["text"].startswith("keep going"), "the harvest itself was lost"
    assert not list(Path(env["THREAD_ANCHOR_DIR"]).glob("*.tmp")), "a temp file was left behind"


def test_done_resets_the_dropped_count_and_no_open_anchor_hides_it(tmp_path):
    """A-S3: `dropped` only grew, so one eviction printed a fold line on every prompt forever."""
    env = _env(tmp_path)
    anchors = [_anchor(f"tangent {i} — item {i} of 99", 50 - i) for i in range(12)]
    _write_state(env, "s-dr", {"anchors": anchors, "last_next": None, "dropped": "garbage"})
    rc = run3(["harvest", "--session", "s-dr"], env, stdin="NEXT: tangent new — item 1 of 5")[0]
    texts = [a["text"] for a in _state(env, "s-dr")["anchors"]]
    assert rc == 0 and "tangent new — item 1 of 5" in texts, "a garbage count broke the harvest"
    assert len(texts) == 12, texts
    assert "dropped over the cap" in run3(["line", "--session", "s-dr"], env)[1]
    run3(["done", "--session", "s-dr", "--match", "tangent new"], env)
    assert "dropped over the cap" not in run3(["line", "--session", "s-dr"], env)[1]
    # a count with no open anchor at all prints nothing
    _write_state(env, "s-dz", {"anchors": [], "last_next": None, "dropped": 4})
    assert run3(["line", "--session", "s-dz"], env)[1] == ""


def test_where_block_respects_its_time_budget(tmp_path, monkeypatch):
    """A-S4: the SessionStart entry times out at 10 s and a 50 MB transcript already takes 4-11 s.
    Past the budget the costly item is skipped with one line; the record items still print."""
    import types

    env = _env(tmp_path)
    run3(["harvest", "--session", "s-t"], env, stdin="NEXT: resume the audit")
    for k in ("THREAD_ANCHOR_DIR", "COMMAND_RUN_DIR", "HOME", "TMPDIR"):
        monkeypatch.setenv(k, env[k])
    ta = _ta_module()

    def slow_files(tp: str, root: Path) -> dict:
        time.sleep(5)
        return {}

    ta._HOOK = types.SimpleNamespace(
        _run_record=lambda sid: None,
        _session_files=slow_files,
        _this_sessions_edits=lambda a, f: a,
        _baseline_floor=lambda sid: 0.0,
        session_unpushed=lambda root, authored, **kw: [],
    )
    monkeypatch.setattr(ta, "_WHERE_BUDGET_S", 0.5)
    t0 = time.monotonic()
    out = ta.cmd_where("s-t", tmp_path, str(tmp_path / "t.jsonl"))
    assert time.monotonic() - t0 < 2.0, "the render ran past its budget"
    assert "(skipped: time budget)" in out and "resume the audit" in out, out


def _lone_repo_with_hook(tmp_path: Path, hook_src: str) -> Path:
    lone = tmp_path / "lone"
    (lone / "scripts").mkdir(parents=True)
    (lone / ".claude" / "hooks").mkdir(parents=True)
    (lone / "scripts" / "thread_anchor.py").write_text(
        SCRIPT.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (lone / ".claude" / "hooks" / "final_gate_stop.py").write_text(hook_src, encoding="utf-8")
    return lone / "scripts" / "thread_anchor.py"


@pytest.mark.parametrize(
    "hook_src",
    [
        "print('NOISE-AT-IMPORT')\nimport sys\nsys.exit(3)\n",
        "print('NOISE-AT-IMPORT')\ndef _run_record(sid):\n    return None\n",
    ],
    ids=["sys-exit-at-import", "prints-at-import"],
)
def test_a_hook_that_exits_or_prints_at_import_never_reaches_the_context(tmp_path, hook_src):
    """A-O1: a SystemExit at hook import escaped `except Exception` and the SessionStart hook
    printed nothing; anything the hook prints at import landed in the injected context."""
    env = _env(tmp_path)
    lone = _lone_repo_with_hook(tmp_path, hook_src)
    run3(["harvest", "--session", "s-x"], env, stdin="NEXT: resume phase C", script=lone)
    rc, out, err = _hook_line(
        env, {"session_id": "s-x", "source": "compact", "cwd": str(tmp_path)}, script=lone
    )
    assert rc == 0 and "Traceback" not in err, err
    assert "WHERE YOU ARE" in out and "resume phase C" in out, out
    assert "NOISE-AT-IMPORT" not in out, out


def test_a_hook_that_exits_at_import_never_breaks_the_stop_side_harvest(tmp_path):
    """A-O1, the main-thread path: `harvest --decision-ok` imports the hook directly (the WHERE
    render imports it inside its bounded thread). A SystemExit there must not escape — the NEXT:
    line is still stored, no block is, and the exit code stays 0."""
    env = _env(tmp_path)
    lone = _lone_repo_with_hook(tmp_path, "import sys\nsys.exit(3)\n")
    rc, _, err = run3(
        ["harvest", "--session", "s-hx", "--decision-ok"], env, stdin=_DECISION_TEXT, script=lone
    )
    assert rc == 0 and "Traceback" not in err, err
    st = _state(env, "s-hx")
    assert st["last_next"]["text"].startswith("operator decision") and not st.get("decision")
    assert err.strip().startswith("thread_anchor:"), err


def test_dirty_files_with_arrows_and_escaped_names_are_found(tmp_path):
    """A-O4: porcelain v1 TEXT splits `a -> b.py` as a rename and C-quotes a tab; -z does not."""
    env = _env(tmp_path)
    work = _repo_with_upstream(tmp_path, env)
    names = ["a -> b.py", "tab\tname.py", "ünï.py"]
    for n in names:
        (work / n).write_text("wip\n", encoding="utf-8")
    tp = _transcript(tmp_path, [work / n for n in names])
    out = _hook_line(
        env,
        {"session_id": "s-z", "transcript_path": str(tp), "cwd": str(work), "source": "compact"},
    )[1]
    for n in names:
        assert n in out, (n, out)


def _answer(env: dict[str, str], sid: str) -> None:
    _hook_line(env, {"session_id": sid, "hook_event_name": "UserPromptSubmit", "prompt": "A"})
    assert not _state(env, sid).get("decision")


def test_the_stale_echo_is_refused_whatever_the_elapsed_time(tmp_path):
    """A-O7 / round 3 A-O6, A-O7: the Stop hook falls back to the previous turn's text when the new
    one is not flushed, so an ACCEPTED harvest can carry the SAME whole message the operator just
    answered. It is refused however long the tool-only turn ran — and no clock value in the state,
    past or future, changes that or crashes the harvest."""
    env = _env(tmp_path)
    _open_decision(env, "s-a")
    _answer(env, "s-a")
    for stale_ts in (time.time() - 900, 1e300):
        st = _state(env, "s-a")
        st["cleared_decision"] = {"digest": "legacy", "ts": stale_ts}  # an old shape: ignored
        _write_state(env, "s-a", st)
        rc, _, err = run3(
            ["harvest", "--session", "s-a", "--decision-ok"], env, stdin=_DECISION_TEXT
        )
        assert rc == 0 and "Traceback" not in err, err
        assert not _state(env, "s-a").get("decision"), f"the stale echo came back ({stale_ts})"
    other = _DECISION_TEXT.replace("Deploy the certified build", "Rotate the signing key")
    run3(["harvest", "--session", "s-a", "--decision-ok"], env, stdin=other)
    assert "Rotate the signing key" in _state(env, "s-a")["decision"]["text"]


def test_a_word_for_word_reask_in_a_new_message_is_stored_immediately(tmp_path):
    """Round 2 A-O3 / round 3: a deliberate re-ask arrives in a NEW message, so an identical block
    inside different surrounding text is stored at once — no window to wait out."""
    env = _env(tmp_path)
    _open_decision(env, "s-w")
    _answer(env, "s-w")
    reask = "The smoke pass found nothing new, so I am asking again.\n\n" + _DECISION_TEXT
    run3(["harvest", "--session", "s-w", "--decision-ok"], env, stdin=reask)
    assert "Deploy the certified build" in (_state(env, "s-w").get("decision") or {}).get(
        "text", ""
    ), "a word-for-word re-ask in a new message was dropped"


def test_an_old_cleared_state_shape_suppresses_nothing(tmp_path):
    """State written by an earlier build carries `cleared_decision` (a string or a dict) and no
    `cleared_msg`; it must never refuse a block."""
    env = _env(tmp_path)
    for i, legacy in enumerate(("0" * 64, {"digest": "x", "ts": time.time()}, 7)):
        sid = f"s-old{i}"
        _write_state(env, sid, {"anchors": [], "last_next": None, "cleared_decision": legacy})
        run3(["harvest", "--session", sid, "--decision-ok"], env, stdin=_DECISION_TEXT)
        assert _state(env, sid).get("decision"), legacy


def test_a_huge_integer_timestamp_is_an_unknown_age(tmp_path):
    """Round 2 A-O2: math.isfinite(10**400) raises OverflowError; main swallowed it and every
    later write to the session failed — the state was wedged."""
    env = _env(tmp_path)
    (Path(env["THREAD_ANCHOR_DIR"]) / "s-h.json").write_text(
        '{"anchors": [{"key": "big", "text": "big-ts thread — item 1 of 9", "ts": 1'
        + "0" * 400
        + '}], "last_next": null}',
        encoding="utf-8",
    )
    rc, out, err = run3(["line", "--session", "s-h"], env)
    assert rc == 0 and "big-ts thread — item 1 of 9" in out, (out, err)
    run3(["harvest", "--session", "s-h"], env, stdin="NEXT: next thing — item 2 of 9")
    assert "next thing — item 2 of 9" in run3(["line", "--session", "s-h"], env)[1]


def test_a_done_that_matches_nothing_keeps_the_dropped_count(tmp_path):
    """Round 2 A-O4: `done` acknowledged the drops even when it closed nothing (a typo)."""
    env = _env(tmp_path)
    anchors = [_anchor("tangent — item 1 of 99", 5)]
    _write_state(env, "s-nm", {"anchors": anchors, "last_next": None, "dropped": 3})
    out = run3(["done", "--session", "s-nm", "--match", "zzz-typo"], env)[1]
    assert "no anchor matched" in out
    assert _state(env, "s-nm")["dropped"] == 3, "a no-match `done` reset the count"


def test_the_where_block_survives_a_hook_import_abandoned_past_the_budget(tmp_path):
    """Round 2 A-O1: the import thread outlives the budget inside redirect_stdout; the block went
    to a pinned but never-flushed stdout and 0 bytes reached the hook. Run as its own process with
    a short budget, so the exit path is the real one."""
    env = _env(tmp_path)
    lone = _lone_repo_with_hook(tmp_path, "import time\ntime.sleep(3)\n")
    run3(["harvest", "--session", "s-ab"], env, stdin="NEXT: resume phase C", script=lone)
    code = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('ta_ab', {str(lone)!r})\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "m._WHERE_BUDGET_S = 0.5\n"
        "sys.exit(m.main(['line', '--hook']))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        input=json.dumps({"session_id": "s-ab", "source": "compact", "cwd": str(tmp_path)}),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert "WHERE YOU ARE" in proc.stdout and "resume phase C" in proc.stdout, proc.stdout
    assert "(skipped: time budget)" in proc.stdout, proc.stdout


def test_an_anchor_with_no_timestamp_is_young_and_never_evicted_first(tmp_path):
    """A-O12: a missing or non-numeric ts read as 0 — folded as ~497,000 h old and evicted first."""
    env = _env(tmp_path)
    anchors = [
        {"key": "no ts", "text": "no-ts thread — item 1 of 9"},
        {"key": "bad ts", "text": "bad-ts thread — item 2 of 9", "ts": "garbage"},
    ]
    anchors += [_anchor(f"tangent {i} — item {i} of 99", 50 - i) for i in range(10)]
    _write_state(env, "s-u", {"anchors": anchors, "last_next": None})
    run3(["harvest", "--session", "s-u"], env, stdin="NEXT: tangent new — item 1 of 5")
    texts = [a["text"] for a in _state(env, "s-u")["anchors"]]
    assert "no-ts thread — item 1 of 9" in texts and "bad-ts thread — item 2 of 9" in texts, texts
    out = run3(["line", "--session", "s-u"], env)[1]
    assert "older thread(s)" not in out, f"an unknown age was folded: {out!r}"


def test_where_block_stays_bounded(tmp_path):
    """B-S3: >10 unpushed commits, >10 dirty files and an over-long DECISION line — every list is
    cut at 10 and every line at 300 characters."""
    env = _env(tmp_path)
    work = _repo_with_upstream(tmp_path, env)
    edited = []
    for i in range(12):
        (work / f"mine{i}.py").write_text("x\n", encoding="utf-8")
        _git(work, env, "add", f"mine{i}.py")
        _git(work, env, "commit", "-q", "-m", f"mine: commit {i} " + "y" * 400)
        edited.append(work / f"mine{i}.py")
        (work / f"mine{i}_dirty.py").write_text("wip\n", encoding="utf-8")
        edited.append(work / f"mine{i}_dirty.py")
    tp = _transcript(tmp_path, edited)
    long = _DECISION_TEXT.replace("Deploy the certified", "Deploy " + "z" * 1000 + " the certified")
    run3(["harvest", "--session", "s-bd", "--decision-ok"], env, stdin=long)
    out = _hook_line(
        env,
        {"session_id": "s-bd", "transcript_path": str(tp), "cwd": str(work), "source": "compact"},
    )[1]
    lines = out.splitlines()
    assert all(len(ln) <= 300 for ln in lines), max(len(ln) for ln in lines)
    assert 1 <= sum("mine: commit" in ln for ln in lines) <= 10, out
    assert 1 <= sum(ln.rstrip().endswith("_dirty.py") for ln in lines) <= 10, out
    assert any(ln.endswith("…") for ln in lines), "no line was visibly cut"


def test_a_promptless_user_prompt_submit_keeps_the_block(tmp_path):
    """B-S2 (by design): a real UserPromptSubmit always carries `prompt`; a payload without one is
    no evidence of an answer, and the next real prompt clears the block."""
    env = _env(tmp_path)
    _open_decision(env, "s-p")
    _hook_line(env, {"session_id": "s-p", "hook_event_name": "UserPromptSubmit"})
    assert _state(env, "s-p").get("decision")


def test_a_next_that_only_shares_the_anchors_key_is_still_shown(tmp_path):
    """B-S2 (whole-plan review, T06): the key lower-cases and masks digits, so a NEXT that was never
    promoted (lower-case `phase b` is no anchor shape) can share the newest anchor's key. It was
    suppressed as "already shown" — in the usual block and in WHERE YOU ARE — though its text
    appears nowhere."""
    env = _env(tmp_path)
    run3(["harvest", "--session", "s-k"], env, stdin="NEXT: wire the parser — phase B — tests next")
    run3(["harvest", "--session", "s-k"], env, stdin="NEXT: wire the parser — phase b — ship it")
    st = _state(env, "s-k")
    assert [a["text"] for a in st["anchors"]] == ["wire the parser — phase B — tests next"]
    assert run3(["line", "--session", "s-k"], env)[1].count("phase b — ship it") == 1
    out = _hook_line(env, {"session_id": "s-k", "source": "compact", "cwd": str(tmp_path)})[1]
    assert out.count("phase b — ship it") == 1, out


# ── work tracking T04: DECISION blocks become items, the unfolded block, claim renewal ─────────
# Every store here is a temp repo initialised by the worktree's own scripts/work.py; the hub's
# `.fabrik/work/` is never read (the script resolves the repo from --repo or the payload's cwd only).

WORK = REPO / "scripts" / "work.py"
_OTHER_DECISION = _DECISION_TEXT.replace("Deploy the certified build", "Rotate the signing key")


def _work(env: dict[str, str], repo: Path, *args: str) -> str:
    proc = subprocess.run(
        [sys.executable, str(WORK), "--repo", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _store_repo(tmp_path: Path, env: dict[str, str], init: bool = True) -> Path:
    repo = tmp_path / "wrepo"
    _git(tmp_path, env, "init", "-q", str(repo))
    (repo / "README").write_text("seed\n", encoding="utf-8")
    _git(repo, env, "add", "README")
    _git(repo, env, "commit", "-q", "-m", "seed")
    if init:
        _work(env, repo, "init", "--distributor", "intel")
    return repo.resolve()


def _items(repo: Path) -> list[dict]:
    store = repo / ".fabrik" / "work"
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(store.glob("W-*.json"))]


def _msg_digest(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.strip().encode("utf-8", "replace")).hexdigest()


def _slot(repo: Path, text: str, ts: float | None = None) -> dict:
    """A slot exactly as a Stop harvest stores it — here WITHOUT its store item, the failed write."""
    block = text[text.index("DECISION NEEDED") : text.index("\n\nNEXT:")]
    return {
        "ts": time.time() if ts is None else ts,
        "text": block,
        "msg": _msg_digest(text),
        "repo": str(repo),
    }


def _slot_state(repo: Path, text: str, ts: float | None = None) -> dict:
    return {"anchors": [], "last_next": None, "decision": _slot(repo, text, ts)}


def _prompt(sid: str, repo: Path, prompt: str = "carry on") -> dict:
    return {
        "session_id": sid,
        "hook_event_name": "UserPromptSubmit",
        "prompt": prompt,
        "cwd": str(repo),
    }


def _snapshot(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


def test_a_harvested_decision_block_becomes_an_awaiting_item(tmp_path):
    env = _env(tmp_path)
    repo = _store_repo(tmp_path, env)
    rc, _, err = run3(
        ["harvest", "--session", "s-i", "--decision-ok", "--repo", str(repo)],
        env,
        stdin=_DECISION_TEXT,
    )
    assert rc == 0, err
    items = _items(repo)
    assert len(items) == 1, items
    assert items[0]["status"] == "awaiting-operator"
    assert _msg_digest(_DECISION_TEXT) in items[0]["msg_digests"]
    assert _state(env, "s-i")["decision"]["repo"] == str(repo)


def test_a_second_different_block_makes_a_second_item_and_leaves_the_first(tmp_path):
    env = _env(tmp_path)
    repo = _store_repo(tmp_path, env)
    args = ["harvest", "--session", "s-2", "--decision-ok", "--repo", str(repo)]
    run3(args, env, stdin=_DECISION_TEXT)
    (first,) = list((repo / ".fabrik" / "work").glob("W-*.json"))
    before = first.read_bytes()
    run3(args, env, stdin=_OTHER_DECISION)
    items = _items(repo)
    assert len(items) == 2, items
    assert first.read_bytes() == before, "the first item changed"
    assert {it["question"] for it in items} == {
        "Deploy the certified build to production now?",
        "Rotate the signing key to production now?",
    }


@pytest.mark.parametrize("who", ["same-session", "another-session"])
def test_a_failed_stop_write_is_rescued_by_the_next_prompt(tmp_path, who):
    """The second chance: the slot carries --repo; the next prompt — in that session, or in
    another after the first one ended — creates the item the Stop harvest failed to write."""
    env = _env(tmp_path)
    repo = _store_repo(tmp_path, env)
    _write_state(env, "s-dead", _slot_state(repo, _DECISION_TEXT))
    sid = "s-dead" if who == "same-session" else "s-live"
    rc, out, err = _hook_line(env, _prompt(sid, repo))
    assert rc == 0, err
    items = _items(repo)
    assert len(items) == 1 and items[0]["status"] == "awaiting-operator", (items, err)
    assert _msg_digest(_DECISION_TEXT) in items[0]["msg_digests"]
    assert "Deploy the certified build to production now?" in out, out
    # a second prompt finds the item by its message digest and creates nothing more
    _hook_line(env, _prompt("s-other", repo))
    assert len(_items(repo)) == 1


def test_a_slot_older_than_seven_days_is_not_rescued(tmp_path):
    env = _env(tmp_path)
    repo = _store_repo(tmp_path, env)
    _write_state(env, "s-old", _slot_state(repo, _DECISION_TEXT, ts=time.time() - 8 * 86400))
    assert _hook_line(env, _prompt("s-live", repo))[0] == 0
    assert _items(repo) == []


def test_a_rescue_that_fails_warns_once_on_stdout(tmp_path):
    import fcntl

    env = _env(tmp_path)
    repo = _store_repo(tmp_path, env)
    _write_state(env, "s-f", _slot_state(repo, _DECISION_TEXT))
    shared = repo / ".git" / "fabrik-work"
    shared.mkdir(exist_ok=True)
    fd = os.open(shared / ".lock", os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)  # the store is busy for the whole prompt
        t0 = time.monotonic()
        rc, out, err = _hook_line(env, _prompt("s-p", repo))
        elapsed = time.monotonic() - t0
    finally:
        os.close(fd)
    assert rc == 0, err
    assert elapsed < 4.0, f"a busy store held the prompt hook for {elapsed:.1f} s"
    assert _items(repo) == []
    warn = [ln for ln in out.splitlines() if "not written" in ln]
    assert len(warn) == 1 and len(warn[0]) <= 300, out


def test_a_repo_without_a_store_neither_rescues_nor_warns(tmp_path):
    env = _env(tmp_path)
    repo = _store_repo(tmp_path, env, init=False)
    _write_state(env, "s-n", _slot_state(repo, _DECISION_TEXT))
    before = _snapshot(repo)
    rc, out, err = _hook_line(env, _prompt("s-q", repo))
    assert rc == 0 and out == "", (out, err)
    assert _snapshot(repo) == before, "a store-less repo was written"


def test_a_reask_after_an_answer_whose_stop_write_failed_gets_a_new_item(tmp_path):
    """The RECORDED residue: matched by the MESSAGE digest, never by block_digest — the answered
    item has the same block, and must not swallow the re-ask."""
    env = _env(tmp_path)
    repo = _store_repo(tmp_path, env)
    run3(
        ["harvest", "--session", "s-r", "--decision-ok", "--repo", str(repo)],
        env,
        stdin=_DECISION_TEXT,
    )
    (item,) = _items(repo)
    _work(env, repo, "answer", item["id"], "--note", "A, deploy it", "--session", "s-r")
    reask = "The smoke pass found nothing new, so I am asking again.\n\n" + _DECISION_TEXT
    _write_state(env, "s-r", _slot_state(repo, reask))
    assert _hook_line(env, _prompt("s-r2", repo))[0] == 0
    awaiting = [it for it in _items(repo) if it["status"] == "awaiting-operator"]
    assert len(awaiting) == 1 and awaiting[0]["id"] != item["id"], _items(repo)
    assert _msg_digest(reask) in awaiting[0]["msg_digests"]


def test_the_clear_keeps_a_slot_replaced_after_the_rescue_read_it(tmp_path, monkeypatch):
    """The prompting session's slot is cleared only when its `msg` is still the one the rescue
    read; a slot a concurrent Stop harvest replaced in between is left for its own next prompt."""
    env = _env(tmp_path)
    repo = _store_repo(tmp_path, env)
    _write_state(env, "s-x", _slot_state(repo, _DECISION_TEXT))
    for k in ("THREAD_ANCHOR_DIR", "COMMAND_RUN_DIR", "HOME", "TMPDIR"):
        monkeypatch.setenv(k, env[k])
    ta = _ta_module()
    real = ta._rescue_decisions

    def rescue_then_replace(session: str, repo_: Path, *rest: float) -> tuple[str | None, str]:
        got = real(session, repo_, *rest)
        _write_state(env, "s-x", _slot_state(repo, _OTHER_DECISION))  # a new Stop landed
        return got

    monkeypatch.setattr(ta, "_rescue_decisions", rescue_then_replace)
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps(_prompt("s-x", repo))))
    assert ta.main(["line", "--hook"]) == 0
    assert "Rotate the signing key" in (_state(env, "s-x").get("decision") or {}).get("text", "")
    # without a replacement, the same prompt clears the slot as before
    _write_state(env, "s-y", _slot_state(repo, _DECISION_TEXT))
    assert _hook_line(env, _prompt("s-y", repo))[0] == 0
    assert not _state(env, "s-y").get("decision")


@pytest.mark.parametrize(
    "payload",
    [
        {"hook_event_name": "UserPromptSubmit", "prompt": "carry on"},
        {"hook_event_name": "SessionStart", "source": "compact"},
    ],
    ids=["prompt", "compact"],
)
def test_awaiting_items_from_other_sessions_print_first_unfolded(tmp_path, payload):
    env = _env(tmp_path)
    repo = _store_repo(tmp_path, env)
    for sid, text in (("s-a", _DECISION_TEXT), ("s-b", _OTHER_DECISION)):
        run3(["harvest", "--session", sid, "--decision-ok", "--repo", str(repo)], env, stdin=text)
    run3(["harvest", "--session", "s-c"], env, stdin="NEXT: resume phase C of the plan")
    rc, out, err = _hook_line(env, {**payload, "session_id": "s-c", "cwd": str(repo)})
    assert rc == 0, err
    lines = out.splitlines()
    # exactly the first two lines, in creation order, then the usual block — nothing before them
    assert lines[0].startswith("work: awaiting operator — W-"), out
    assert lines[0].endswith("Deploy the certified build to production now?"), out
    assert lines[1].startswith("work: awaiting operator — W-"), out
    assert lines[1].endswith("Rotate the signing key to production now?"), out
    assert not lines[2].startswith("work:"), out
    assert "resume phase C" in out, out
    if payload.get("source") == "compact":
        assert "WHERE YOU ARE" in out, out


def test_where_block_omits_the_slot_only_when_the_store_holds_its_item(tmp_path, monkeypatch):
    env = _env(tmp_path)
    repo = _store_repo(tmp_path, env)
    run3(
        ["harvest", "--session", "s-w", "--decision-ok", "--repo", str(repo)],
        env,
        stdin=_DECISION_TEXT,
    )
    out = _hook_line(env, {"session_id": "s-w", "source": "compact", "cwd": str(repo)})[1]
    assert "OPEN DECISION" not in out and out.count("Deploy the certified build") == 1, out
    # the store lost the item (a failed write before the compaction): the slot line prints
    for p in (repo / ".fabrik" / "work").glob("W-*.json"):
        p.unlink()
    for k in ("THREAD_ANCHOR_DIR", "COMMAND_RUN_DIR", "HOME", "TMPDIR"):
        monkeypatch.setenv(k, env[k])
    out = _ta_module().cmd_where("s-w", repo, "", repo=repo)
    assert "OPEN DECISION" in out, out


def test_a_quiet_stop_harvest_renews_the_sessions_claim(tmp_path):
    env = _env(tmp_path)
    repo = _store_repo(tmp_path, env)
    _work(env, repo, "add", "--kind", "task", "--title", "wire the harvest")
    (item,) = _items(repo)
    _work(env, repo, "claim", item["id"], "--session", "s-cl")
    claim_path = repo / ".git" / "fabrik-work" / "claims" / f"{item['id']}.json"
    claim = json.loads(claim_path.read_text(encoding="utf-8"))
    claim["at"] = time.time() - 3600
    claim_path.write_text(json.dumps(claim), encoding="utf-8")
    rc, _, err = run3(
        ["harvest", "--session", "s-cl", "--repo", str(repo)], env, stdin="no footer at all"
    )
    assert rc == 0, err
    renewed = json.loads(claim_path.read_text(encoding="utf-8"))
    assert renewed["at"] > time.time() - 60, (renewed, err)


def test_no_repo_and_no_cwd_touch_no_store(tmp_path):
    """Grounding risk 2: never os.getcwd() — run from INSIDE an initialised repo, nothing is read
    (no prompt block) and nothing is written."""
    env = _env(tmp_path)
    repo = _store_repo(tmp_path, env)
    _work(env, repo, "add", "--kind", "task", "--title", "ready work")
    before = _snapshot(repo)
    run3(["harvest", "--session", "s-g", "--decision-ok"], env, stdin=_DECISION_TEXT, cwd=repo)
    rc, out, _ = run3(
        ["line", "--hook"],
        env,
        stdin=json.dumps({"session_id": "s-g", "hook_event_name": "SessionStart"}),
        cwd=repo,
    )
    assert rc == 0 and "work:" not in out, out
    assert _snapshot(repo) == before, "a store was written without --repo or a payload cwd"


def test_a_next_naming_an_item_sets_its_next_field(tmp_path):
    env = _env(tmp_path)
    repo = _store_repo(tmp_path, env)
    _work(env, repo, "add", "--kind", "task", "--title", "wire the harvest")
    (item,) = _items(repo)
    nxt = f"finish {item['id']} — the claim renewal tests"
    run3(
        ["harvest", "--session", "s-nx", "--repo", str(repo)], env, stdin=f"done.\n\nNEXT: {nxt}\n"
    )
    assert _items(repo)[0].get("next") == nxt, _items(repo)


# ── T04 review pass 1: the echo guard, one rescue call, the prompt deadline, a bounded scan ────


class _CountingWork:
    """A stand-in for the loaded work.py that records every API call by name (and may veto one)."""

    def __init__(self, real, calls: list[str], guard=None) -> None:
        self._real, self._calls, self._guard = real, calls, guard

    def __getattr__(self, name: str):
        attr = getattr(self._real, name)
        if not callable(attr):
            return attr

        def wrapped(*a, **kw):
            self._calls.append(name)
            if self._guard is not None:
                self._guard(name)
            return attr(*a, **kw)

        return wrapped


def _in_process(monkeypatch, env: dict[str, str]):
    for k in ("THREAD_ANCHOR_DIR", "COMMAND_RUN_DIR", "HOME", "TMPDIR"):
        monkeypatch.setenv(k, env[k])
    ta = _ta_module()
    real = ta._work()
    assert real is not None
    return ta, real


def _main_line(ta, monkeypatch, payload: dict) -> int:
    import io

    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return ta.main(["line", "--hook"])


def _numbered(i: int) -> str:
    """A DECISION message whose BLOCK differs per i — equal blocks would merge into one item."""
    return _DECISION_TEXT.replace("Deploy the certified build", f"Deploy build {i}")


def test_an_echo_of_an_answered_message_never_reaches_the_store(tmp_path):
    """A-O3: the slot's echo guard refuses the same whole message after the operator answered it;
    the store call must see the same refusal, or the echo mints an item for a settled question."""
    env = _env(tmp_path)
    repo = _store_repo(tmp_path, env)
    run3(["harvest", "--session", "s-e", "--decision-ok"], env, stdin=_DECISION_TEXT)
    _hook_line(env, {"session_id": "s-e", "hook_event_name": "UserPromptSubmit", "prompt": "A"})
    assert not _state(env, "s-e").get("decision")
    rc, _, err = run3(
        ["harvest", "--session", "s-e", "--decision-ok", "--repo", str(repo)],
        env,
        stdin=_DECISION_TEXT,
    )
    assert rc == 0, err
    assert _items(repo) == [], "the echo of an answered message created a store item"


def test_the_rescue_makes_a_bounded_number_of_store_calls(tmp_path, monkeypatch, capsys):
    """A-O2/A-S2: 50 rescuable slots cost ONE ensure_decision_items call, never one store read per
    slot, and the prompt hook stays far inside its 10 s budget."""
    env = _env(tmp_path)
    repo = _store_repo(tmp_path, env)
    for i in range(50):
        _write_state(env, f"s-{i:02d}", _slot_state(repo, _numbered(i)))
    ta, real = _in_process(monkeypatch, env)
    calls: list[str] = []
    ta._WORK = _CountingWork(real, calls)
    t0 = time.monotonic()
    assert _main_line(ta, monkeypatch, _prompt("s-live", repo)) == 0
    assert time.monotonic() - t0 < 8.0
    assert len(calls) <= 6 and calls.count("ensure_decision_items") == 1, calls
    assert len(_items(repo)) == 50
    assert capsys.readouterr().out.startswith("work: awaiting operator")


def test_store_work_past_the_prompt_deadline_is_skipped(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path)
    repo = _store_repo(tmp_path, env)
    _write_state(env, "s-d", _slot_state(repo, _DECISION_TEXT))
    ta, real = _in_process(monkeypatch, env)
    calls: list[str] = []
    ta._WORK = _CountingWork(real, calls)
    monkeypatch.setattr(ta, "_PROMPT_STORE_BUDGET_S", 0.0)
    assert _main_line(ta, monkeypatch, _prompt("s-live", repo)) == 0
    assert calls == ["repo_root"], calls
    assert _items(repo) == []
    assert "work:" not in capsys.readouterr().out


def test_an_oversized_state_file_is_never_parsed(tmp_path):
    """A-S4/A-O6: the scan stats before it reads — a 300 KiB state file is skipped whole, and the
    other slots are still rescued."""
    env = _env(tmp_path)
    repo = _store_repo(tmp_path, env)
    big = _slot_state(repo, "huge\n\n" + _DECISION_TEXT)
    big["pad"] = "x" * (300 * 1024)
    _write_state(env, "s-big", big)
    _write_state(env, "s-small", _slot_state(repo, _OTHER_DECISION))
    assert _hook_line(env, _prompt("s-live", repo))[0] == 0
    items = _items(repo)
    assert [it["question"] for it in items] == ["Rotate the signing key to production now?"], items


def test_the_scan_reads_only_the_fifty_newest_state_files(tmp_path):
    env = _env(tmp_path)
    repo = _store_repo(tmp_path, env)
    oldest = "the oldest\n\n" + _DECISION_TEXT
    _write_state(env, "s-old", _slot_state(repo, oldest))
    hour_ago = time.time() - 3600
    os.utime(Path(env["THREAD_ANCHOR_DIR"]) / "s-old.json", (hour_ago, hour_ago))
    for i in range(50):
        _write_state(env, f"s-{i:02d}", _slot_state(repo, _numbered(i)))
    assert _hook_line(env, _prompt("s-live", repo))[0] == 0
    items = _items(repo)
    assert len(items) == 50, len(items)
    assert all(_msg_digest(oldest) not in it["msg_digests"] for it in items)


def test_no_store_call_runs_while_the_session_lock_is_held(tmp_path, monkeypatch):
    """A-S3 / grounding risk 1: the per-session lock and the store lock are never held together."""
    import contextlib

    env = _env(tmp_path)
    repo = _store_repo(tmp_path, env)
    ta, real = _in_process(monkeypatch, env)
    held: list[bool] = []
    real_locked = ta._locked

    @contextlib.contextmanager
    def tracking(session: str):
        with real_locked(session) as ok:
            held.append(True)
            try:
                yield ok
            finally:
                held.pop()

    monkeypatch.setattr(ta, "_locked", tracking)
    calls: list[str] = []
    overlaps: list[str] = []
    ta._WORK = _CountingWork(real, calls, guard=lambda n: held and overlaps.append(n))
    ta.cmd_harvest("s-lo", _DECISION_TEXT, decision_ok=True, repo=repo)
    ta.cmd_harvest("s-lo", "no footer", repo=repo)
    assert _main_line(ta, monkeypatch, _prompt("s-lo", repo, "A")) == 0
    assert "on_harvest" in calls and "prompt_block" in calls, calls
    assert overlaps == [], f"work.py called under the session lock: {overlaps}"


def test_rescuing_another_sessions_slot_leaves_its_claims_alone(tmp_path):
    """B-S5: the rescue writes on behalf of a session that may be dead; it must not extend that
    session's leases. Needs the T02 producer fix (the ensure functions renew no claim) — this
    test fails on a work.py without it."""
    env = _env(tmp_path)
    repo = _store_repo(tmp_path, env)
    _work(env, repo, "add", "--kind", "task", "--title", "held by a dead session")
    (item,) = _items(repo)
    _work(env, repo, "claim", item["id"], "--session", "s-dead")
    claim_path = repo / ".git" / "fabrik-work" / "claims" / f"{item['id']}.json"
    before = claim_path.read_bytes()
    time.sleep(0.05)
    _write_state(env, "s-dead", _slot_state(repo, _DECISION_TEXT))
    assert _hook_line(env, _prompt("s-live", repo))[0] == 0
    assert any(it["status"] == "awaiting-operator" for it in _items(repo))
    assert claim_path.read_bytes() == before, "the rescue renewed another session's claim"
