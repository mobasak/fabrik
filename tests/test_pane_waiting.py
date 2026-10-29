"""Behavior Contract — the coordinator's PANE WAITING scan (W-a12b03a2).

`rotate_session.waiting(repo)` reads every builder pane in the repo's agents_up grid and names the ones waiting on a
dialog or ending a turn with a question; `work.py` prints them first in the coordinator's prompt block and puts one
`pane-waiting` Stop subject per pane ahead of everything else. The dialog screens below reproduce, row shape for row
shape, three dialogs captured from a throwaway Claude Code v2.1.312 session on 2026-10-29 (a Write permission dialog,
the workspace-trust prompt, an AskUserQuestion with wrapped options); the idle rows are the live turn-end forms.
tmux is a scripted fake (`ROTATE_TMUX`), so no test reads a real pane.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ROT = REPO / "scripts" / "sysadmin" / "rotate_session.py"
WORK = REPO / "scripts" / "work.py"
spec = importlib.util.spec_from_file_location("rotate_session_pw", ROT)
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)

RULE = "─" * 60
NB = " "

WRITE_DIALOG = "\n".join(
    [
        "● Write(hello.txt)",
        RULE,
        " Create file",
        " hello.txt",
        "╌" * 60,
        "  1 hi",
        "╌" * 60,
        " Do you want to create hello.txt?",
        " ❯ 1. Yes",
        "   2. Yes, and switch to accept edits (auto-approve file edits and common file commands) for this session",
        "   3. No",
        "",
        " Esc to cancel · Tab to amend",
        "",
    ]
)
BASH_DIALOG = (
    WRITE_DIALOG.replace("● Write(hello.txt)", "● Bash(rm -rf build)")
    .replace(" Create file\n hello.txt", " Bash command\n rm -rf build")
    .replace("Do you want to create hello.txt?", "Do you want to proceed?")
)
OTHER_BASH_DIALOG = BASH_DIALOG.replace("rm -rf build", "git push origin w")
TRUST_DIALOG = "\n".join(
    [
        RULE,
        " Accessing workspace:",
        "",
        " /tmp/probe",
        "",
        " Quick safety check: Is this a project you created or one you trust? (Like your own code, a well-known open "
        "source project.)",
        "",
        " Security guide",
        "",
        " ❯ No, exit",
        "   Yes, I trust this folder",
        "",
        " Enter to confirm · Esc to cancel",
        "",
    ]
)
ASK_DIALOG = "\n".join(
    [
        "❯ pick one for me",
        RULE,
        " ☐ Approach",
        "│ Which approach should I use to create hello.txt?",
        "❯ 1. Write to working dir (Recommended)",
        "     Use the Write tool to create hello.txt directly in the primary working directory, which is the",
        "     location you asked for. This keeps the file exactly where the request points and matches your",
        "     instruction to use the Write tool.",
        "  2. Write to scratchpad",
        "     Use the Write tool to create hello.txt inside the session scratchpad directory instead.",
        "  3. Type something.",
        RULE,
        "  4. Chat about this",
        "Enter to select · ↑/↓ to navigate · Esc to cancel",
        "",
    ]
)


def _idle(
    body: list[str],
    turn_end: str = "✻ Worked for 17s · done 1:57 AM",
    box: str = "",
    below: tuple = (),
) -> str:
    return "\n".join(
        [
            *body,
            turn_end,
            *below,
            "                       ✔ Update installed · Restart to update",
            RULE,
            f"❯{NB}{box}",
            RULE,
            "  Opus 5.5  ·  ctx 22%  ·  5h 29%",
            "  ⏵⏵ auto mode on · 3 shells",
            "",
        ]
    )


ASKING = _idle(
    [
        "● I measured both readings of the parser.",
        "  Should I keep the regex or copy the parser",
        "  into work.py?",
        "",
        "  RUN: /fabrik-task · phase 2/5 · elapsed 16/150 · terminal: the",
        "  coordinator sees every waiting pane",
        "  STATE: design written, two readings open",
        "  NEXT: awaiting your answer on the parser",
    ]
)
QUIET = _idle(
    [
        "● Merged and pushed.",
        "",
        "  STATE: item closed, worktree clean",
        "  NEXT: none — terminal; awaiting the rotation",
    ]
)


# ── the classifier ─────────────────────────────────────────────────────────────────────────────────────────────────


def test_live_dialogs_are_waiting():
    w = rs._waiting_on(WRITE_DIALOG)
    assert w is not None and w[0] == "dialog" and w[1] == "Do you want to create hello.txt?"
    t = rs._waiting_on(TRUST_DIALOG)  # un-numbered options: `_dialog` alone misses it
    assert rs._dialog(TRUST_DIALOG) is False
    assert (
        t is not None
        and t[0] == "dialog"
        and t[1].startswith("Quick safety check: Is this a project")
    )
    a = rs._waiting_on(ASK_DIALOG)  # options 4 rows apart: `_dialog` alone misses it
    assert rs._dialog(ASK_DIALOG) is False
    assert (
        a is not None
        and a[0] == "dialog"
        and a[1] == "Which approach should I use to create hello.txt?"
    )
    # two Bash dialogs share their question; the body (the command) keeps their fingerprints apart
    b1, b2 = rs._waiting_on(BASH_DIALOG), rs._waiting_on(OTHER_BASH_DIALOG)
    assert b1[1] == b2[1] == "Do you want to proceed?"
    assert b1[2] != b2[2]


def test_question_only_when_idle_and_asking():
    q = rs._waiting_on(ASKING)
    assert q is not None and q[0] == "question"
    assert (
        q[1]
        == "I measured both readings of the parser. Should I keep the regex or copy the parser into work.py?"
    )
    assert (
        "done 1:57 AM" in q[2]
    )  # the turn-end row is in the body: a new turn is a new fingerprint
    assert rs._waiting_on(QUIET) is None
    # `awaiting your reply` in the footer and a closing paren after the `?` both ask
    reply = _idle(["● Done.", "", "  STATE: built", "  NEXT: awaiting your reply"])
    assert rs._waiting_on(reply)[0] == "question"
    paren = _idle(["● (which one do you want?)", "", "  STATE: x", "  NEXT: none — terminal"])
    assert rs._waiting_on(paren)[0] == "question"
    # the live turn-end form with a trailing shell note
    shell = _idle(
        ["● Keep it?", "", "  STATE: x", "  NEXT: none"],
        turn_end="✻ Worked for 11s · done 12:30 PM · 1 shell still running",
    )
    assert rs._waiting_on(shell)[0] == "question"
    # the turn end is the `· done` form only: a duration row without it is not read as idle
    assert rs._waiting_on(_idle(["● Keep it?"], turn_end="✻ Worked for 17s")) is None
    # NOT waiting: text typed in the box, the agent still working on its own seats, a spinner, no turn end at all
    assert rs._waiting_on(_idle(["● Keep it?"], box="half typed")) is None
    assert (
        rs._waiting_on(
            _idle(["● Keep it?"], below=("✻ Waiting for 2 background agents to finish",))
        )
        is None
    )
    assert (
        rs._waiting_on(
            _idle(["● Keep it?"], turn_end="✻ Waiting for 2 background agents to finish")
        )
        is None
    )
    assert (
        rs._waiting_on(_idle(["● Keep it?"], below=("* Julienning… (1m 4s · ↓ 6.8k tokens)",)))
        is None
    )
    assert rs._waiting_on(_idle(["● Keep it?"], turn_end="")) is None


# ── the grid scan ──────────────────────────────────────────────────────────────────────────────────────────────────

FAKE_TMUX = """#!/usr/bin/env python3
import json, os, sys, time
st = json.load(open(os.environ["FAKE_TMUX_STATE"]))
a = sys.argv[1:]
if st.get("sleep"):
    time.sleep(st["sleep"])
if st.get("rc"):
    sys.stderr.write(st.get("err", "") + "\\n")
    sys.exit(st["rc"])
if a[0] == "list-panes":
    print("\\n".join(st["panes"]))
elif a[0] == "capture-pane":
    with open(os.environ["FAKE_TMUX_STATE"] + ".caps", "a") as fh:
        fh.write(a[-1] + "\\n")
    sys.stdout.write(st["screens"].get(a[-1], ""))
"""


@pytest.fixture
def tmux(tmp_path, monkeypatch):
    exe = tmp_path / "tmux"
    exe.write_text(FAKE_TMUX, encoding="utf-8")
    exe.chmod(0o755)
    state = tmp_path / "tmux.json"
    monkeypatch.setenv("ROTATE_TMUX", str(exe))
    monkeypatch.setenv("FAKE_TMUX_STATE", str(state))

    def put(**st):
        state.write_text(json.dumps(st), encoding="utf-8")

    return put


def _row(pane: str, session: str, group: str, agent: str, path: str) -> str:
    return "\t".join((pane, session, group, agent, path))


def test_grid_filter_and_dedupe(tmux, tmp_path):
    main = tmp_path / "fabrik"
    main.mkdir()
    tmux(
        panes=[
            _row("%5", "fabrik", "fabrik", "infra-2", "/x/wt/infra-2"),
            _row(
                "%5", "fabrik-2", "fabrik", "infra-2", "/x/wt/infra-2"
            ),  # the grouped twin: same pane
            _row("%7", "fabrik-2", "fabrik", "intel", "/x/wt/intel"),  # seen only through the twin
            _row("%8", "other", "", "dev1", "/x/other"),  # another repo's grid
            _row("%9", "fabrik", "fabrik", "", "/x/shell"),  # untagged
            _row("%10", "fabrik", "fabrik", "coord", "/x/elsewhere"),  # the caller by name
            _row(
                "%11", "fabrik", "fabrik", "wef4", str(main)
            ),  # a pane in the main checkout: the caller's own
        ],
        screens={
            "%7": OTHER_BASH_DIALOG,
            **dict.fromkeys(("%5", "%8", "%9", "%10", "%11"), BASH_DIALOG),
        },
    )
    got = rs.waiting(str(main), exclude="coord")
    assert [(g["agent"], g["pane"], g["kind"]) for g in got] == [
        ("infra-2", "%5", "dialog"),
        ("intel", "%7", "dialog"),
    ]
    assert all(g["fp"].startswith(f"pane:{g['agent']}:") for g in got)
    # the same question over two commands: the fingerprints differ by the command, so a new dialog re-arms the rung
    assert got[0]["line"] == got[1]["line"] == "Do you want to proceed?"
    assert got[0]["fp"].rsplit(":", 1)[1] != got[1]["fp"].rsplit(":", 1)[1]
    caps = (tmp_path / "tmux.json.caps").read_text().split()
    assert sorted(caps) == ["%5", "%7"]  # each pane captured once


def test_tmux_failure_modes(tmux, tmp_path, monkeypatch):
    main = str(tmp_path / "fabrik")
    for err in (
        "no server running on /tmp/tmux-1000/default",
        "error connecting to /tmp/tmux-1000/x (No such file)",
    ):
        tmux(rc=1, err=err)
        assert rs.waiting(main) == []  # no grid exists: nobody can be waiting
    monkeypatch.setenv("ROTATE_TMUX", str(tmp_path / "no-such-tmux"))
    assert rs.waiting(main) == []
    monkeypatch.setenv("ROTATE_TMUX", str(tmp_path / "tmux"))
    tmux(rc=1, err="server exited unexpectedly")
    with pytest.raises(RuntimeError):
        rs.waiting(main)
    tmux(
        sleep=0.6,
        panes=[_row("%5", "fabrik", "fabrik", "infra-2", "/x")],
        screens={"%5": WRITE_DIALOG},
    )
    with pytest.raises(
        RuntimeError, match="timed out"
    ):  # the second call times out on what is left
        rs.waiting(main, budget=0.8)
    tmux(panes=[_row("%5", "fabrik", "fabrik", "infra-2", "/x")], screens={"%5": WRITE_DIALOG})
    with pytest.raises(RuntimeError, match="budget spent"):  # a spent budget starts no call at all
        rs.waiting(main, budget=0)


# ── the two readers in work.py ─────────────────────────────────────────────────────────────────────────────────────


def _env(tmp_path: Path) -> dict[str, str]:
    for sub in ("home", "tmp"):
        (tmp_path / sub).mkdir(exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path / "home"),
        "TMPDIR": str(tmp_path / "tmp"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "FABRIK_MAIL_ROOT": str(tmp_path / "tmp" / "mail"),
        "COMMAND_RUN_DIR": str(tmp_path / "tmp" / "state" / "command-runs"),
        "AGENT_IDENTITY_FILE": str(tmp_path / "tmp" / "identity.jsonl"),
        "FABRIK_WORK_PROC": os.environ.get("FABRIK_WORK_PROC", ""),
        "CLAUDE_AGENT": "coord",
        "ROTATE_TMUX": os.environ["ROTATE_TMUX"],
        "FAKE_TMUX_STATE": os.environ["FAKE_TMUX_STATE"],
    }


def _git(cwd: Path, env: dict, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True)


def _work(env: dict, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(WORK), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _coordinator_repo(tmp_path: Path, env: dict, autonomy: bool) -> tuple[Path, Path]:
    repo = tmp_path / "grid"
    _git(tmp_path, env, "init", "-q", "-b", "master", str(repo))
    (repo / "README").write_text("seed\n", encoding="utf-8")
    _git(repo, env, "add", "README")
    _git(repo, env, "commit", "-q", "-m", "seed")
    assert _work(env, repo, "init", "--distributor", "coord").returncode == 0
    cfg = repo / ".fabrik" / "work" / "config.json"
    data = json.loads(cfg.read_text(encoding="utf-8"))
    data.update({"coordinator_mode": True, "autonomy": autonomy})
    cfg.write_text(json.dumps(data), encoding="utf-8")
    _git(repo, env, "add", ".fabrik")
    _git(repo, env, "commit", "-q", "-m", "store")
    wt = repo / ".claude" / "worktrees" / "infra-2"
    _git(repo, env, "worktree", "add", "-q", "-b", "w-infra-2", str(wt))
    return repo.resolve(), wt.resolve()


def _prompt(env: dict, cwd: Path) -> str:
    code = (
        "import importlib.util,sys;"
        f"s=importlib.util.spec_from_file_location('w',{str(WORK)!r});m=importlib.util.module_from_spec(s);"
        "sys.modules['w']=m;s.loader.exec_module(m);"
        f"print(m.prompt_block({str(cwd)!r},'sid-coord'))"
    )
    r = subprocess.run(
        [sys.executable, "-c", code], cwd=cwd, env=env, capture_output=True, text=True, timeout=60
    )
    assert r.returncode == 0, r.stderr
    return r.stdout


def _stop(env: dict, cwd: Path) -> dict:
    r = _work(env, cwd, "queue", "--stop", "--session", "sid-coord", "--cwd", str(cwd))
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_prompt_block_pane_lines(tmux, tmp_path):
    env = _env(tmp_path)
    repo, wt = _coordinator_repo(tmp_path, env, autonomy=False)
    tmux(panes=[_row("%5", "grid", "", "infra-2", str(wt))], screens={"%5": WRITE_DIALOG})
    lines = _prompt(env, repo).splitlines()
    assert lines[0].startswith(
        'work: PANE WAITING: infra-2 (%5) — dialog: "Do you want to create hello.txt?" — '
    )
    assert "tmux send-keys -t %5" in lines[0]
    assert not any(
        "PANE" in ln for ln in _prompt(env, wt).splitlines()
    )  # a builder's own block: none
    tmux(rc=1, err="server exited unexpectedly")
    assert _prompt(env, repo).splitlines()[0].startswith("work: PANE SCAN FAILED — ")


@pytest.mark.parametrize("autonomy", [False, True])
def test_stop_action_pane_rung(tmux, tmp_path, autonomy):
    env = _env(tmp_path)
    repo, wt = _coordinator_repo(tmp_path, env, autonomy=autonomy)
    tmux(
        panes=[
            _row("%5", "grid", "", "infra-2", str(wt)),
            _row("%7", "grid", "", "intel", "/x/intel"),
        ],
        screens={"%5": WRITE_DIALOG, "%7": ASKING},
    )
    got = _stop(env, repo)
    assert got["action"] == "pane-waiting" and "infra-2 (%5)" in got["text"]
    if autonomy:
        acts = [(c["action"], c["fp"].split(":")[1]) for c in got["candidates"][:2]]
        assert acts == [("pane-waiting", "infra-2"), ("pane-waiting", "intel")]
    assert _stop(env, wt).get("action") != "pane-waiting"  # a builder is never handed it
    tmux(rc=1, err="server exited unexpectedly")
    assert _stop(env, repo).get("action") != "pane-waiting"  # a blind scan never blocks


# ── review round 1 regressions (W-a12b03a2) ────────────────────────────────────────────────────────────────────────


def test_a_marker_asks_only_where_it_opens_and_tool_rows_never_ask():
    def footer(next_value: str) -> str:
        return _idle(["● Done.", "", "  STATE: x", f"  NEXT: {next_value}"])

    # a footer that NAMES a marker in passing waits on nothing
    assert (
        rs._waiting_on(footer("none — terminal (no DECISION NEEDED, not awaiting your reply)"))
        is None
    )
    assert rs._waiting_on(footer("none — terminal; no decision needed from you")) is None
    assert rs._waiting_on(footer("awaiting your reply"))[0] == "question"
    heading = _idle(["● DECISION NEEDED (ground: gate)", "  - Question: deploy now"])
    assert rs._waiting_on(heading)[0] == "question"
    # the house footer forms that hand the reader a decision (round 2: a block two paragraphs up was missed)
    multi = _idle(
        ["● DECISION NEEDED (ground: gate)", "  Option A or B.", "", "  Details.", "", "  STATE: x"]
        + ["  NEXT: DECISION NEEDED above"]
    )
    assert rs._waiting_on(multi)[0] == "question"
    assert (
        rs._waiting_on(footer("operator decision: deploy now — see DECISION NEEDED above"))[0]
        == "question"
    )
    # a message that opens with `name(` is text, not a tool call (round 2)
    assert rs._waiting_on(_idle(["● foo(bar) is fine, ok? Use it?"]))[0] == "question"
    assert rs._waiting_on(_idle(["● mcp__serena__find_symbol(name: x)", "  ⎿  found?"])) is None
    # what the agent RAN is not what it asks: a tool call and its result rows
    assert rs._waiting_on(_idle(["● Bash(ls)", "  ⎿  what is this?"])) is None
    assert rs._waiting_on(_idle(["● Keep it?", "", "● Bash(ls)", "  ⎿  done"]))[1] == "Keep it?"


def test_a_new_turn_below_the_turn_end_is_not_waiting_but_a_seat_notice_is():
    assert rs._waiting_on(_idle(["● Keep it?"], below=("● Read(foo)",))) is None
    assert rs._waiting_on(_idle(["● Keep it?"], below=("❯ go on",))) is None
    seat = _idle(["● Keep it?"], below=('● Agent "Review seat 3 opus" finished · 57s',))
    assert rs._waiting_on(seat)[0] == "question"


def test_the_same_prompt_keeps_its_fingerprint():
    moved = WRITE_DIALOG.replace(" ❯ 1. Yes", "   1. Yes").replace("   3. No", " ❯ 3. No")
    assert rs._waiting_on(WRITE_DIALOG)[2] == rs._waiting_on(moved)[2]  # arrowing between options
    two = _idle(
        ["● Keep it?"], turn_end="✻ Worked for 11s · done 12:30 PM · 2 shells still running"
    )
    one = _idle(["● Keep it?"], turn_end="✻ Worked for 11s · done 12:30 PM · 1 shell still running")
    assert rs._waiting_on(two)[2] == rs._waiting_on(one)[2]  # a background shell ending
    later = _idle(["● Keep it?"], turn_end="✻ Worked for 11s · done 12:41 PM")
    assert rs._waiting_on(later)[2] != rs._waiting_on(one)[2]  # a new turn asking again


def test_an_extended_colour_is_never_read_as_dim():
    assert rs._undimmed("\x1b[38;5;2m❯ 1. Yes\x1b[0m") == "❯ 1. Yes"  # colour index 2
    assert rs._undimmed("\x1b[38;2;215;119;87m❯ 1. Yes\x1b[39m") == "❯ 1. Yes"  # truecolor
    assert rs._undimmed("\x1b[48;5;2;1mbold\x1b[0m") == "bold"
    assert rs._undimmed("\x1b[2m 362 \x1b[0mdef x") == "def x"  # a real dim cell still drops
    coloured = WRITE_DIALOG.replace(" ❯ 1. Yes", "\x1b[38;2;215;119;87m ❯ 1. Yes\x1b[39m")
    assert rs._waiting_on(coloured)[0] == "dialog"


RAW_TMUX = """#!/usr/bin/env python3
import os, sys
a = sys.argv[1:]
if a[0] == "list-panes":
    sys.stdout.write("%5\\tfabrik\\t\\tinfra-2\\t/x/a\\n%6\\tfabrik\\t\\tintel\\t/x/b\\n%7\\tfabrik\\t\\tfleet\\t/x/c\\n")
elif a[-1] == "%5":
    sys.stdout.buffer.write(b"\\xff\\xfe binary output\\n")
elif a[-1] == "%6":
    sys.stderr.write("can't find pane: %6\\n")
    sys.exit(1)
else:
    sys.stdout.write(os.environ["SCREEN"])
"""


def test_one_pane_that_is_gone_or_shows_binary_does_not_blind_the_scan(tmp_path, monkeypatch):
    exe = tmp_path / "tmux"
    exe.write_text(RAW_TMUX, encoding="utf-8")
    exe.chmod(0o755)
    monkeypatch.setenv("ROTATE_TMUX", str(exe))
    monkeypatch.setenv("SCREEN", WRITE_DIALOG)
    got = rs.waiting(str(tmp_path / "fabrik"))
    assert [(g["agent"], g["kind"]) for g in got] == [("fleet", "dialog")]
    exe.chmod(0o644)  # a tmux that cannot be run is an OS error, reported as a failed scan
    with pytest.raises(RuntimeError):
        rs.waiting(str(tmp_path / "fabrik"))


def _work_module():
    spec_w = importlib.util.spec_from_file_location("work_pw", WORK)
    mod = importlib.util.module_from_spec(spec_w)
    sys.modules["work_pw"] = mod
    spec_w.loader.exec_module(mod)
    return mod


def test_the_line_quotes_the_prompt_and_fits_with_the_longest_name():
    w = _work_module()
    p = {"agent": "a" * 32, "pane": "%99999", "kind": "question", "line": 'say "yes" ' + "x" * 200}
    line = "work: " + w._pane_text(p)
    assert len(line) <= w.LINE_MAX, len(line)  # never clipped: the reply verbs survive
    assert line.endswith("(approve only what you read, D-1034)")
    assert ": \"say 'yes' " in line  # quoted as data; its own quotes cannot close the quote


def test_only_a_coordinator_main_checkout_scans(tmux, tmp_path, monkeypatch):
    env = _env(tmp_path)
    repo, wt = _coordinator_repo(tmp_path, env, autonomy=False)
    w = _work_module()
    monkeypatch.delenv("FABRIK_HEADLESS", raising=False)
    monkeypatch.delenv("CLAUDE_MESH_HEADLESS", raising=False)
    monkeypatch.setenv("FABRIK_WORK_PROC", str(tmp_path / "no-proc"))
    assert w._scans_panes(repo) is True
    assert (
        w._scans_panes(wt) is False
    )  # a linked worktree, even with coordinator_mode in its config
    monkeypatch.setenv("FABRIK_HEADLESS", "1")
    assert w._scans_panes(repo) is False  # a headless session answers nobody's pane
    monkeypatch.delenv("FABRIK_HEADLESS")
    cfg = repo / ".fabrik" / "work" / "config.json"
    data = json.loads(cfg.read_text(encoding="utf-8"))
    data["coordinator_mode"] = False
    cfg.write_text(json.dumps(data), encoding="utf-8")
    assert w._scans_panes(repo) is False


def test_a_headless_coordinator_session_never_runs_tmux(tmux, tmp_path):
    env = {**_env(tmp_path), "FABRIK_HEADLESS": "1"}
    repo, wt = _coordinator_repo(tmp_path, env, autonomy=True)
    tmux(panes=[_row("%5", "grid", "", "infra-2", str(wt))], screens={"%5": WRITE_DIALOG})
    _prompt(env, repo)
    _stop(env, repo)
    assert not (tmp_path / "tmux.json.caps").exists()


def test_a_classic_coordinator_keeps_one_ladder_when_no_pane_waits(tmux, tmp_path):
    env = _env(tmp_path)
    repo, _ = _coordinator_repo(tmp_path, env, autonomy=False)
    tmux(panes=[], screens={})
    assert "candidates" in _stop(env, repo)  # never the single-action shape that overwrites the map
    tmux(rc=1, err="server exited unexpectedly")
    assert "candidates" in _stop(env, repo)  # a scan blip keeps the shape too
