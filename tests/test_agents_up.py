"""`agents-up <repo>` (D-1031): one tmux session per repo, one pane per builder, read from the repo's own registry.

Driven through `--print`, which reports the grid it would build and launches nothing — never tmux, never claude. A
fake `ps` on the launcher's own PATH (`$HOME/.local/bin`) stands in for the live claude processes.
"""

from __future__ import annotations

import importlib.util
import json
import os
import pty
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
# AGENTS_UP_UNDER_TEST: the red-on-revert proof points the suite at the pre-change script (a copy, never the tracked one)
UP = Path(os.environ.get("AGENTS_UP_UNDER_TEST") or ROOT / "scripts" / "sysadmin" / "agents_up.sh")
GIB = 1024 * 1024  # kB per GiB

DEV1 = "610c3b1c-a5ef-4ba0-a662-f3f87399a58b"
DEV2 = "413b420e-3b36-4d13-b4f6-ee3f71f98de2"
SENT = "67ccc993-3fda-4dcd-a392-4531f01c6e5d"
COORD = "0f0e0d0c-0b0a-4908-8706-050403020100"


_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")


def _repo(tmp: Path, registry: object, name: str = "fabrik-lib", worktrees: bool = True) -> Path:
    """A registry repo. A builder gets a pane only in its own linked worktree (W-89474fc1), so by default every builder
    name the registry gives — a valid name, not a coordinator — gets one (`_worktree`)."""
    repo = tmp / name
    (repo / ".fabrik").mkdir(parents=True)
    text = registry if isinstance(registry, str) else json.dumps(registry)
    (repo / ".fabrik" / "session-agents.json").write_text(text, encoding="utf-8")
    repo = repo.resolve()
    if worktrees and isinstance(registry, str):
        try:
            registry = json.loads(registry)
        except ValueError:
            registry = None
    if worktrees and isinstance(registry, dict):
        for agent in sorted({v for v in registry.values() if isinstance(v, str)}):
            if (
                _NAME.fullmatch(agent)
                and agent != "coordinator"
                and not agent.endswith("-coordinator")
            ):
                _worktree(repo, agent)
    return repo


def _wt(repo: Path, name: str) -> Path:
    return repo / ".claude" / "worktrees" / name


# A user manager the test controls: `manager-down` makes every call fail (no bus), `slice-refused` refuses the slice
# ceiling; each call is logged. systemd-run logs its argv and runs the command after `--`, so a pane line is EXECUTED
# with the cap it really carries.
FAKE_SYSTEMCTL = """#!/bin/sh
echo "$*" >> "$HOME/systemctl.log"
[ -f "$HOME/manager-down" ] && exit 1
case "$*" in *set-property*) [ -f "$HOME/slice-refused" ] && exit 1 ;; esac
exit 0
"""
FAKE_SYSTEMD_RUN = """#!/bin/sh
echo "$*" >> "$HOME/systemd-run.log"
while [ $# -gt 0 ] && [ "$1" != "--" ]; do shift; done
shift
exec "$@"
"""


def _home(
    tmp: Path,
    ps_lines: str = "",
    transcripts: tuple[tuple[Path, str], ...] = (),
    root_only: bool = False,
) -> Path:
    """A HOME with a fake `ps` printing `ps_lines`, a fake user manager, and a transcript per (folder, session id). A
    repo root's transcript is also put under each of its linked worktrees, where the pane starts, unless `root_only`."""
    home = tmp / "home"
    (home / ".local" / "bin").mkdir(parents=True, exist_ok=True)
    _meminfo(home, 27)
    ps = home / ".local" / "bin" / "ps"
    # answers only the launcher's exact question: every claude process, full width (-ww), pid first. A line that
    # carries no pid of its own (`<digits> <args>`) is given an unused one.
    numbered = "\n".join(
        ln if re.match(r"\s*\d+ ", ln) else f"{9000 + i} {ln}"
        for i, ln in enumerate(ps_lines.splitlines())
    )
    ps.write_text(
        '#!/bin/sh\n[ "$*" = "-ww -C claude -o pid=,args=" ] || exit 1\n'
        f"cat <<'EOF'\n{numbered}\nEOF\n",
        encoding="utf-8",
    )
    ps.chmod(0o755)
    for tool, text in (("systemctl", FAKE_SYSTEMCTL), ("systemd-run", FAKE_SYSTEMD_RUN)):
        (home / ".local" / "bin" / tool).write_text(text, encoding="utf-8")
        (home / ".local" / "bin" / tool).chmod(0o755)
    for root, sid in transcripts:
        for folder in _copies(root, root_only):
            proj = (
                home
                / ".claude-fleet"
                / "active"
                / "projects"
                / re.sub(r"[^A-Za-z0-9]", "-", str(folder))
            )
            proj.mkdir(parents=True, exist_ok=True)
            (proj / f"{sid}.jsonl").write_text("{}\n", encoding="utf-8")
    return home


def _meminfo(home: Path, gib: int | None) -> Path:
    """The fake /proc root `_run` points FABRIK_PROC_ROOT at: MemTotal of `gib` GiB, or no meminfo at all (None)."""
    proc = home / "proc"
    proc.mkdir(parents=True, exist_ok=True)
    meminfo = proc / "meminfo"
    if gib is None:
        meminfo.unlink(missing_ok=True)
    else:
        meminfo.write_text(
            f"MemTotal:       {gib * GIB} kB\nMemAvailable:   1 kB\n", encoding="utf-8"
        )
    return proc


def _copies(root: Path, root_only: bool) -> list[Path]:
    wts = root / ".claude" / "worktrees"
    if root_only or not wts.is_dir():
        return [root]
    return [
        root,
        *sorted(p for p in wts.iterdir() if (p / ".git").is_file() and not p.is_symlink()),
    ]


def _run(
    *args: str, home: Path, tty: bool = False, timeout: int = 30, **env: str
) -> subprocess.CompletedProcess[str]:
    """Run the launcher. `tty=True` gives it a pty for stdin and stdout (an interactive caller, so it may attach);
    otherwise stdin and stdout are pipes, as in a coordinator's Bash tool, a cron job or a hook."""
    full = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(home),
        "FABRIK_PROC_ROOT": str(home / "proc"),
        **env,
    }
    if not tty:
        return subprocess.run(
            ["bash", str(UP), *args], capture_output=True, text=True, timeout=timeout, env=full
        )
    master, slave = pty.openpty()
    try:
        done = subprocess.run(
            ["bash", str(UP), *args],
            stdin=slave,
            stdout=slave,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            env=full,
        )
    finally:
        os.close(slave)
        os.close(master)
    return subprocess.CompletedProcess(done.args, done.returncode, "", done.stderr)


def _panes(out: str) -> list[str]:
    return [ln for ln in out.splitlines() if ln.startswith("pane ")]


def test_print_lists_one_pane_per_builder_without_the_coordinator(tmp_path: Path) -> None:
    """Each builder resumes its own session id, in name order, from the repo root; the coordinator — reached in VS
    Code — gets no pane, whether it is named `coordinator` or `<repo>-coordinator`."""
    repo = _repo(
        tmp_path,
        {
            SENT: "fabrik-lib-sentinel",
            COORD: "fabrik-lib-coordinator",
            DEV2: "fabrik-lib-dev2",
            DEV1: "fabrik-lib-dev1",
            "1a1a1a1a-1a1a-4a1a-8a1a-1a1a1a1a1a1a": "coordinator",
        },
    )
    home = _home(tmp_path, transcripts=((repo, DEV1), (repo, DEV2), (repo, SENT)))
    out = _run("--print", str(repo), home=home)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines()[0] == "session fabrik-lib", out.stdout
    assert _panes(out.stdout) == [
        f"pane fabrik-lib-dev1 {DEV1} {_wt(repo, 'fabrik-lib-dev1')} ok",
        f"pane fabrik-lib-dev2 {DEV2} {_wt(repo, 'fabrik-lib-dev2')} ok",
        f"pane fabrik-lib-sentinel {SENT} {_wt(repo, 'fabrik-lib-sentinel')} ok",
    ], out.stdout
    run = [ln for ln in out.stdout.splitlines() if ln.startswith("run fabrik-lib-dev1 ")]
    # the inner command: claude resumes with the suppression and the wake prompt as ONE single-quoted word each
    assert (
        len(run) == 1
        and f"claude -n fabrik-lib-dev1 --permission-mode bypassPermissions --resume {DEV1} --settings '{SETTINGS}' 'You were relaunched"
        in _inner(run[0])
    ), out.stdout
    # the suppression: skillOverrides.auto-mode-setup=off and no spinner tips, and the survey off in the pane's env
    cfg = json.loads(SETTINGS)
    assert cfg == {"skillOverrides": {"auto-mode-setup": "off"}, "spinnerTipsEnabled": False}
    assert "CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1" in run[0], run[0]


def test_a_running_session_is_never_resumed_twice(tmp_path: Path) -> None:
    """Two processes on one session id fuse the transcript and the hooks. A session already resumed elsewhere — by a
    terminal (`--resume <sid>`) or by the VS Code extension (`--resume=<sid>`, how all three fabrik-lib builders ran
    on 2026-10-19) — gets a pane that only says so; a mere prefix of another id is not a match."""
    third = "1a1a1a1a-1a1a-4a1a-8a1a-1a1a1a1a1a1a"
    repo = _repo(tmp_path, {DEV1: "dev1", DEV2: "dev2", SENT: "sentinel", third: "tester"})
    ps = (
        f"/home/u/.vscode-server/extensions/anthropic.claude-code/native-binary/claude --output-format stream-json --resume={DEV1} --setting-sources user\n"
        f"claude -n dev2 --resume {DEV2}\n"
        f"claude --resume {SENT}0\n"
        f"claude -r {third}"
    )
    home = _home(
        tmp_path,
        ps_lines=ps,
        transcripts=((repo, DEV1), (repo, DEV2), (repo, SENT), (repo, third)),
    )
    out = _run("--print", str(repo), home=home)
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [
        f"pane dev1 {DEV1} {_wt(repo, 'dev1')} running",
        f"pane dev2 {DEV2} {_wt(repo, 'dev2')} running",
        f"pane sentinel {SENT} {_wt(repo, 'sentinel')} ok",
        f"pane tester {third} {_wt(repo, 'tester')} running",
    ], out.stdout
    run = {ln.split()[1]: ln for ln in out.stdout.splitlines() if ln.startswith("run ")}
    # a running session's pane only prints a message; it never starts claude
    assert _inner(run["dev1"]).startswith('echo "[dev1 is already running elsewhere'), run["dev1"]
    assert _inner(run["dev2"]).startswith('echo "[dev2 is already running elsewhere'), run["dev2"]
    assert _inner(run["sentinel"]).startswith(OOM_LINE + "env -i "), run["sentinel"]
    # the shell a running session's pane keeps is clean too, never the tmux server's environment
    assert _inner(run["dev1"]).rstrip().endswith("bash -l") and "; exec env -i " in _inner(
        run["dev1"]
    ), run["dev1"]


def test_a_session_with_no_transcript_under_the_root_is_flagged(tmp_path: Path) -> None:
    """claude resumes a session by the folder it starts in; a session with no transcript there is reported, so a
    pane that will only print "No conversation found" is visible before the launch."""
    repo = _repo(tmp_path, {DEV1: "dev1", DEV2: "dev2"})
    home = _home(tmp_path, transcripts=((repo, DEV1), (repo / "elsewhere", DEV2)))
    out = _run("--print", str(repo), home=home)
    assert _panes(out.stdout) == [
        f"pane dev1 {DEV1} {_wt(repo, 'dev1')} ok",
        f"pane dev2 {DEV2} {_wt(repo, 'dev2')} no-transcript",
    ], out.stdout


def test_each_pane_carries_its_own_environment(tmp_path: Path) -> None:
    """A pane gets the tmux SERVER's environment, and a server started from a VS Code session carries ~20 of that
    session's variables. The pane's command is EXECUTED here, under such a polluted environment, with a fake `claude`
    that prints what it received: only the allow-list arrives — the shell basics, PATH, the config, the quota home and
    CLAUDE_AGENT — and so does the shell the pane keeps after claude exits."""
    repo = _repo(tmp_path, {DEV1: "dev1"})
    home = _home(tmp_path, transcripts=((repo, DEV1),))
    fake = home / ".local" / "bin" / "claude"
    fake.write_text("#!/bin/sh\nenv | sort\n", encoding="utf-8")
    fake.chmod(0o755)
    out = _run("--print", str(repo), home=home)
    run = next(ln for ln in out.stdout.splitlines() if ln.startswith("run dev1 "))
    launch = run[
        len("run dev1 ") :
    ]  # the WHOLE pane: the scope, claude, its hint and the shell it keeps
    polluted = {
        "HOME": str(home),
        "USER": "u",
        "LOGNAME": "u",
        "SHELL": "/bin/bash",
        "TERM": "tmux-256color",
        "PATH": "/usr/bin:/bin",
        "CLAUDECODE": "1",
        "CLAUDE_CODE_SESSION_ID": "39bff247-2733-4e93-8385-bce51336f65c",
        "CLAUDE_CODE_MESSAGING_TOKEN": "secret",
        "CLAUDE_EFFORT": "medium",
        "GIT_EDITOR": "true",
        "VSCODE_IPC_HOOK_CLI": "/run/vscode.sock",
        "CLAUDE_CONFIG_DIR": "/wrong",
    }
    got = subprocess.run(
        ["/bin/sh", "-c", launch],
        capture_output=True,
        text=True,
        timeout=30,
        env=polluted,
        stdin=subprocess.DEVNULL,  # the kept login shell reads EOF and exits
    )
    seen = dict(ln.split("=", 1) for ln in got.stdout.splitlines() if "=" in ln)
    for leaked in ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_MESSAGING_TOKEN"):
        assert leaked not in seen, (leaked, got.stdout)
    for leaked in ("CLAUDE_EFFORT", "GIT_EDITOR", "VSCODE_IPC_HOOK_CLI"):
        assert leaked not in seen, (leaked, got.stdout)
    assert seen["CLAUDE_CONFIG_DIR"] == f"{home}/.claude-fleet/active", got.stdout
    assert seen["CLAUDE_QUOTA_HOME"] == f"{home}/.claude-fleet/active", got.stdout
    assert seen["CLAUDE_AGENT"] == "dev1" and seen["HOME"] == str(home), got.stdout
    # the one variable added to the allow-list: the feedback survey is off in every pane (W-b9ad80ae D3)
    assert seen["CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY"] == "1", got.stdout
    assert seen["TERM"] == "tmux-256color" and seen["PATH"].startswith(f"{home}/.local/bin:"), (
        got.stdout
    )
    # the shell basics come from the pane's own shell; LANG falls back when the server has none
    assert seen["USER"] == "u" and seen["LOGNAME"] == "u" and seen["SHELL"] == "/bin/bash", (
        got.stdout
    )
    assert seen["LANG"] == "C.UTF-8", got.stdout
    # the scope runs from the allow-list too, and so does the shell a pane keeps after claude exits (inside it); the
    # branch after a scope that ended badly opens no shell at all (review round 2). PATH is fixed ONCE — three fixed
    # copies of a 4 KB WSL PATH brought a pane command near the size tmux takes in one message (review round 1)
    assert run.count("env -i ") == 3 and _inner(run).rstrip().endswith("bash -l"), run
    assert run.count(f"PATH={home}/.local/bin:") == 1, run
    # one scope per pane (its argv logged on one line; the pane command it carries holds a newline of its own)
    scoped = [
        ln
        for ln in (home / "systemd-run.log").read_text(encoding="utf-8").splitlines()
        if ln.startswith("--user ")
    ]
    assert len(scoped) == 1 and scoped[0].startswith(
        "--user --scope --quiet --slice=fabrik-agents.slice -p MemorySwapMax=0 -p TasksMax=1024 -- bash -c "
    ), scoped


def test_a_malformed_registry_refuses_the_launch(tmp_path: Path) -> None:
    """A name or id reaches a shell string, so every row is validated, and one bad row refuses the whole launch
    rather than silently dropping a builder or resuming a stale session."""
    # each case is refused for ITS reason: a later check (or a crash) refusing it too would pass an exit-code-only test
    cases = {
        "not-json": ("{ nope", "is not a valid registry"),
        "not-an-object": (json.dumps(["x"]), "must be an object"),
        "non-uuid-id": (json.dumps({"abc": "dev1"}), "is not a session id"),
        "uppercase-id": (json.dumps({DEV1.upper(): "dev1"}), "is not a session id"),
        "shell-in-name": (json.dumps({DEV1: "dev1; rm -rf ~"}), "is not an agent name"),
        "quote-in-name": (json.dumps({DEV1: "dev'1"}), "is not an agent name"),
        "dash-led-name": (json.dumps({DEV1: "-dev1"}), "is not an agent name"),
        "name-33-chars": (json.dumps({DEV1: "a" * 33}), "is not an agent name"),
        "empty-name": (json.dumps({DEV1: ""}), "is not an agent name"),
        "name-not-a-string": (json.dumps({DEV1: 7}), "is not an agent name"),
        # fabrik-lib's registry writer only ever ADDS a row, so a changed session id leaves the old one behind
        "two-ids-one-name": (json.dumps({DEV1: "dev1", DEV2: "dev1"}), "more than one session id"),
        "repeated-key": (
            f'{{"{DEV1}": "dev1", "{DEV2}": "dev2", "{DEV1}": "dev3"}}',
            "appears twice",
        ),
    }
    home = _home(tmp_path)
    for label, (text, reason) in cases.items():
        repo = _repo(tmp_path / label, text)
        out = _run("--print", str(repo), home=home)
        assert out.returncode == 2, (label, out.stdout, out.stderr)
        assert "pane " not in out.stdout, (label, out.stdout)
        assert reason in out.stderr and "Traceback" not in out.stderr, (label, out.stderr)
    # a registry that names only a coordinator is not malformed — it is EMPTY: exit 3, "nothing to launch" (W-b9ad80ae D4)
    empty = _run(
        "--print",
        str(_repo(tmp_path / "no-builders", {COORD: "fabrik-lib-coordinator"})),
        home=home,
    )
    assert empty.returncode == 3 and "names no builder" in empty.stderr, (
        empty.stdout,
        empty.stderr,
    )
    assert "pane " not in empty.stdout, empty.stdout
    # the length bound is a bound, not a refusal: 32 characters is a name
    ok = _run("--print", str(_repo(tmp_path / "len32", {DEV1: "a" * 32})), home=home)
    assert ok.returncode == 0 and f"pane {'a' * 32} {DEV1} " in ok.stdout, (ok.stdout, ok.stderr)


def test_a_repo_without_a_registry_refuses(tmp_path: Path) -> None:
    """A repo with no `.fabrik/session-agents.json` and no scope to read its whoami bindings from has nowhere to find
    its builders, says so and stops; so does a path that is no directory, and a call with no repo at all."""
    home = _home(tmp_path)
    bare = tmp_path / "bare"
    bare.mkdir()
    cases = (
        (("--print", str(bare)), "has no registry"),
        (("--print", str(tmp_path / "missing")), "is not a directory"),
        (("--print",), "usage:"),
        ((), "usage:"),
        (("--print", ""), "usage:"),
    )
    for args, reason in cases:
        out = _run(*args, home=home)
        assert out.returncode == 2, (args, out.stdout, out.stderr)
        assert "pane " not in out.stdout, args
        assert reason in out.stderr, (args, out.stderr)
    out = _run("--print", str(bare), home=home)
    assert "session-agents.json" in out.stderr and "whoami bindings" in out.stderr, out.stderr


def test_the_session_name_is_the_repo_basename(tmp_path: Path) -> None:
    """tmux reads `.`, `:` and glob characters in a target, so only [A-Za-z0-9_-] survive; a trailing slash or a
    relative path changes nothing, because the root is resolved first."""
    repo = _repo(tmp_path, {DEV1: "dev1"}, name="web.shop:v2[x]*")
    home = _home(tmp_path)
    out = _run("--print", f"{repo}/", home=home)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines()[0] == "session web-shop-v2-x--", out.stdout
    assert _panes(out.stdout)[0].startswith(f"pane dev1 {DEV1} {_wt(repo, 'dev1')} "), out.stdout
    rel = subprocess.run(
        ["bash", str(UP), "--print", repo.name],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=repo.parent,
        env={"PATH": "/usr/bin:/bin", "HOME": str(home)},
    )
    assert _panes(rel.stdout)[0].startswith(f"pane dev1 {DEV1} {_wt(repo, 'dev1')} "), rel.stdout
    # a relative path that starts with `-` is a folder, never an option to `cd`
    dashed = _repo(tmp_path, {DEV1: "dev1"}, name="-lib")
    rel = subprocess.run(
        ["bash", str(UP), "--print", dashed.name],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=dashed.parent,
        env={"PATH": "/usr/bin:/bin", "HOME": str(home)},
    )
    assert rel.returncode == 0, rel.stderr
    assert _panes(rel.stdout)[0].startswith(f"pane dev1 {DEV1} {_wt(dashed, 'dev1')} "), rel.stdout


FAKE_TMUX = """#!/bin/sh
echo "$*" >> "$HOME/tmux.log"
# ids as a real server hands them out under -P: window @n, pane %n, from one counter
next() { n=$(cat "$HOME/tmux-seq" 2>/dev/null || echo 0); n=$((n+1)); echo $n > "$HOME/tmux-seq"; echo $n; }
# tmux 3.4 (W-1961cc42): an option command given the bare exact target `=name` answers "no such session" while
# `=name:` works — the fake fails the same way, so a regression to the bare form is red here, not only on the box
case "$1" in
  show-options|set-option)
    prev=""
    for a in "$@"; do
      if [ "$prev" = "-t" ]; then
        case "$a" in =*:*) ;; =*) echo "no such session: $a" >&2; exit 1 ;; esac
      fi
      prev="$a"
    done ;;
esac
case "$1" in
  has-session) [ -f "$HOME/tmux-has" ] ;;
  show-options)
    # tmux-owner-late: the owner appears only on the second read (a launch still building the grid)
    if [ -f "$HOME/tmux-owner-late" ] && [ ! -f "$HOME/tmux-read-once" ]; then
      : > "$HOME/tmux-read-once"; exit 0
    fi
    cat "$HOME/tmux-owner" 2>/dev/null; exit 0 ;;
  new-session)
    # tmux-newfail: another launch created the session first; tmux-deadfail: tmux itself failed, no session exists
    if [ -f "$HOME/tmux-newfail" ]; then : > "$HOME/tmux-has"; exit 1; fi
    [ -f "$HOME/tmux-deadfail" ] && exit 1
    n=$(next); case "$*" in *" -P "*) echo "@$n %$n" ;; esac
    exit 0 ;;
  new-window)
    n=$(next); case "$*" in *" -P "*) echo "@$n %$n" ;; esac
    exit 0 ;;
  set-option)
    # tmux-setfail: the root cannot be recorded
    [ -f "$HOME/tmux-setfail" ] && exit 1
    exit 0 ;;
  split-window)
    # tmux-splitfail: no room for another pane
    [ -f "$HOME/tmux-splitfail" ] && exit 1
    n=$(next); case "$*" in *" -P "*) echo "%$n" ;; esac
    exit 0 ;;
  list-panes)
    # tmux-panes: one '<pane id> <@agent tag>' line per pane of an existing grid (a hand-built grid's panes)
    # honours the asked format: without #{pane_id} only the tag column prints, as real tmux would
    case "$*" in
      *pane_id*) cat "$HOME/tmux-panes" 2>/dev/null ;;
      *) cut -d' ' -f2- "$HOME/tmux-panes" 2>/dev/null ;;
    esac
    exit 0 ;;
  *) exit 0 ;;
esac
"""


def _tmux_home(
    tmp: Path, repo: Path, has: bool, owner: str | None, root_only: bool = False
) -> Path:
    """A HOME whose fake `tmux` logs every call and plays a session that exists (`has`) with an `@agents_up_root`."""
    home = _home(tmp, transcripts=((repo, DEV1), (repo, DEV2)), root_only=root_only)
    tmux = home / ".local" / "bin" / "tmux"
    tmux.write_text(FAKE_TMUX, encoding="utf-8")
    tmux.chmod(0o755)
    if has:
        (home / "tmux-has").write_text("", encoding="utf-8")
    if owner is not None:
        (home / "tmux-owner").write_text(owner + "\n", encoding="utf-8")
    return home


def _log(home: Path) -> list[str]:
    return (home / "tmux.log").read_text(encoding="utf-8").splitlines()


def test_a_new_grid_records_its_repo_and_attaches(tmp_path: Path) -> None:
    """The launch path, against a fake tmux: one new session, its root recorded as `@agents_up_root`, one split per
    further builder, every target exact (`=`), then attach."""
    repo = _repo(tmp_path, {DEV1: "dev1", DEV2: "dev2"})
    home = _tmux_home(tmp_path, repo, has=False, owner=None)
    out = _run(str(repo), home=home, tty=True)
    assert out.returncode == 0, out.stderr
    log = _log(home)
    assert log[0] == "has-session -t =fabrik-lib", log
    assert any(ln.startswith("new-session -d -s fabrik-lib -n agents -c ") for ln in log), log
    assert f"set-option -t =fabrik-lib: @agents_up_root {repo}" in log, log
    assert sum(ln.startswith("split-window -t @1 ") for ln in log) == 1, (
        log
    )  # the window by id, never by name
    assert "select-pane -t %1" in log, log  # a fresh grid opens on its first pane
    assert log[-1] == "attach -t =fabrik-lib", log
    # a root that cannot be recorded is said, because every later launch would refuse the grid
    failed = _tmux_home(tmp_path / "setfail", repo, has=False, owner=None)
    (failed / "tmux-setfail").write_text("", encoding="utf-8")
    out = _run(str(repo), home=failed, tty=True)
    assert out.returncode == 0 and "could not record the root" in out.stderr, out.stderr
    assert _log(failed)[-1] == "attach -t =fabrik-lib", _log(failed)


def test_an_existing_grid_is_reattached_only_when_it_is_this_repos(tmp_path: Path) -> None:
    """A session is named after the folder only, so a grid already up under the name must carry this repo's root: the
    repo's own grid is reattached as it is (no pane rebuilt), another folder's is refused, and so is one that never
    records a root (after the one re-read an in-progress launch is given)."""
    repo = _repo(tmp_path, {DEV1: "dev1", DEV2: "dev2"})
    mine = _tmux_home(tmp_path / "mine", repo, has=True, owner=str(repo))
    out = _run(str(repo), home=mine, tty=True)
    assert out.returncode == 0, out.stderr
    assert not any(ln.startswith(("new-session", "split-window")) for ln in _log(mine)), _log(mine)
    assert _log(mine)[-1] == "attach -t =fabrik-lib", _log(mine)
    # "other-tagged": another folder's recorded grid is never adopted, even when its panes carry this repo's names
    for label, owner in (
        ("other", "/opt/elsewhere/fabrik-lib"),
        ("other-tagged", "/opt/elsewhere/fabrik-lib"),
    ):
        home = _tmux_home(tmp_path / label, repo, has=True, owner=owner)
        if label == "other-tagged":
            (home / "tmux-panes").write_text("%1 dev1\n%2 dev2\n", encoding="utf-8")
        out = _run(str(repo), home=home)
        assert out.returncode == 2, (label, out.stderr)
        assert "not attaching" in out.stderr, (label, out.stderr)
        assert not any(ln.startswith("attach") for ln in _log(home)), (label, _log(home))


def test_a_hand_built_grid_of_this_repos_builders_is_adopted(tmp_path: Path) -> None:
    """W-bb6c9d9a: fabrik-lib's ~/bin/fabrik-lib-up builds a grid under the same name with no recorded root, but tags
    every pane with its agent. That grid is adopted — its root recorded, reattached as it is — only when every pane is
    one of this repo's builders; a stranger pane, an untagged pane or no pane at all is NOT adopted, but a grid that is
    up is attached whatever the root read returned (W-e841ac37): it attaches with a warning, root unrecorded."""
    repo = _repo(tmp_path, {DEV1: "dev1", DEV2: "dev2"})
    ours = _tmux_home(tmp_path / "ours", repo, has=True, owner=None)
    (ours / "tmux-panes").write_text("%1 dev1\n%2 dev2\n", encoding="utf-8")
    out = _run(str(repo), home=ours, tty=True)
    assert out.returncode == 0 and "adopted" in out.stderr, out.stderr
    # its panes skipped the env allow-list, and the operator is told how to get clean ones
    assert "keep the environment they started with" in out.stderr, out.stderr
    assert f"set-option -t =fabrik-lib: @agents_up_root {repo}" in _log(ours), _log(ours)
    assert not any(ln.startswith(("new-session", "split-window")) for ln in _log(ours)), _log(ours)
    assert _log(ours)[-1] == "attach -t =fabrik-lib", _log(ours)
    for label, panes in (
        ("stranger", "%1 dev1\n%2 stranger\n"),
        ("untagged", "%1 dev1\n%2 \n"),
        ("prefix", "%1 dev\n"),
    ):
        home = _tmux_home(tmp_path / label, repo, has=True, owner=None)
        (home / "tmux-panes").write_text(panes, encoding="utf-8")
        out = _run(str(repo), home=home, tty=True)
        assert out.returncode == 0, (label, out.stderr)
        assert "could not confirm that tmux session fabrik-lib is this repo's" in out.stderr, (
            label,
            out.stderr,
        )
        assert "adopted" not in out.stderr and "not attaching" not in out.stderr, out.stderr
        assert not any(
            ln.startswith(("set-option", "new-session", "split-window")) for ln in _log(home)
        ), (
            label,
            _log(home),
        )
        assert _log(home)[-1] == "attach -t =fabrik-lib", (label, _log(home))
    # no panes at all and no recorded root (a failed root write): attached with the warning, never refused
    home = _tmux_home(tmp_path / "bare", repo, has=True, owner=None)
    out = _run(str(repo), home=home, tty=True)
    assert out.returncode == 0 and "attaching to it anyway" in out.stderr, out.stderr
    assert _log(home)[-1] == "attach -t =fabrik-lib", _log(home)


def test_a_launch_racing_another_attaches_only_to_this_repos_grid(tmp_path: Path) -> None:
    """Two launches of one repo (a double-clicked `.bat`): the loser's `new-session` fails because the winner just
    created the session, whose root the winner records a moment later. The loser re-reads an empty owner once, then
    attaches to its own repo's grid without touching it — or refuses a same-named grid of another folder."""
    repo = _repo(tmp_path, {DEV1: "dev1", DEV2: "dev2"})
    cases = {
        "race-mine": (True, str(repo), 0),
        "race-other": (True, "/opt/elsewhere/fabrik-lib", 2),
        "late-owner-mine": (False, str(repo), 0),
    }
    for label, (race, owner, rc) in cases.items():
        home = _tmux_home(tmp_path / label, repo, has=not race, owner=owner)
        if race:
            (home / "tmux-newfail").write_text("", encoding="utf-8")
        (home / "tmux-owner-late").write_text("", encoding="utf-8")
        out = _run(str(repo), home=home, tty=True)
        log = _log(home)
        assert out.returncode == rc, (label, out.stderr, log)
        reads = [ln for ln in log if ln.startswith("show-options")]
        assert len(reads) == 2, (label, log)  # the empty first read is re-read once
        assert not any(
            ln.startswith(("split-window", "select-pane", "set-option")) for ln in log
        ), (
            label,
            log,
        )
        if rc == 0:
            assert log[-1] == "attach -t =fabrik-lib", (label, log)
        else:
            assert not any(ln.startswith("attach") for ln in log), (label, log)
            assert "belongs to /opt/elsewhere/fabrik-lib" in out.stderr, (label, out.stderr)


def test_the_launch_path_reports_what_it_could_not_do(tmp_path: Path) -> None:
    """The tmux failure paths the fake can now produce: tmux failing outright (exit 1, nothing attached), no room for a
    second pane (said, that pane skipped and never labelled), a session with no transcript (said before its pane opens),
    and a launch from inside tmux (the client switched, never a nested attach)."""
    repo = _repo(tmp_path, {DEV1: "dev1", DEV2: "dev2"})

    dead = _tmux_home(tmp_path / "dead", repo, has=False, owner=None)
    (dead / "tmux-deadfail").write_text("", encoding="utf-8")
    out = _run(str(repo), home=dead)
    assert out.returncode == 1, (out.stderr, _log(dead))
    assert not any(ln.startswith(("attach", "switch-client")) for ln in _log(dead)), _log(dead)

    split = _tmux_home(tmp_path / "split", repo, has=False, owner=None)
    (split / "tmux-splitfail").write_text("", encoding="utf-8")
    out = _run(str(repo), home=split)
    # T04 residue 3: a pane skipped for no room is exit 4, never 0 — the boot sweep reads 0 as "every builder
    # relaunched"; the line names the session so a caller can tell which builder did not come back
    assert out.returncode == 4, (out.returncode, out.stderr)
    assert f"no room for dev2's pane (session {DEV2})" in out.stderr, out.stderr
    labels = [ln for ln in _log(split) if ln.startswith("set -p ")]
    assert labels == ["set -p -t %1 @agent dev1"], _log(split)
    detached = _tmux_home(tmp_path / "split-detach", repo, has=False, owner=None)
    (detached / "tmux-splitfail").write_text("", encoding="utf-8")
    out = _run("--detach", str(repo), home=detached)
    assert out.returncode == 4, (out.returncode, out.stderr)
    assert "--detach — the fabrik-lib grid is up" in out.stderr, out.stderr
    header = UP.read_text(encoding="utf-8").split("\nset ", 1)[0]
    assert "4 SOME PANE NOT OPENED" in header and "1 tmux failed" in header, "exit list"

    bare = _home(tmp_path / "bare", transcripts=((repo, DEV1),))
    tmux = bare / ".local" / "bin" / "tmux"
    tmux.write_text(FAKE_TMUX, encoding="utf-8")
    tmux.chmod(0o755)
    out = _run(str(repo), home=bare)
    assert out.returncode == 0, out.stderr
    assert f"dev2: no transcript for session {DEV2}" in out.stderr, out.stderr
    assert "dev1: no transcript" not in out.stderr, out.stderr

    inside = _tmux_home(tmp_path / "inside", repo, has=False, owner=None)
    out = _run(str(repo), home=inside, TMUX="/tmp/tmux-1000/default,1,0")
    assert out.returncode == 0, out.stderr
    assert _log(inside)[-1] == "switch-client -t =fabrik-lib", _log(inside)
    assert not any(ln.startswith("attach") for ln in _log(inside)), _log(inside)


def test_a_builder_without_a_worktree_gets_no_pane(tmp_path: Path) -> None:
    """W-6c7c3292, W-89474fc1: a builder works in `<repo>/.claude/worktrees/<name>`, and the main checkout is the
    coordinator's, so a builder resumed at the root would edit main's tree and read main's CLAUDE.md. A pane starts
    ONLY in the builder's worktree when it is a linked git worktree in place, and its transcript is looked for under
    that folder, since claude resumes by it. A file, a folder with no `.git` (left behind by `git worktree remove`), a
    nested clone (a `.git` FOLDER), a symlink — which could take the pane out of the repo — and nothing at all by that
    name give NO pane, each said on stderr; never a pane at the root."""
    third, fourth, fifth, sixth, seventh = (
        f"{c * 8}-{c * 4}-4{c * 3}-8{c * 3}-{c * 12}" for c in "abcde"
    )
    repo = _repo(
        tmp_path,
        {
            DEV1: "dev1",
            DEV2: "dev2",
            SENT: "sentinel",
            third: "stale",
            fourth: "linked",
            fifth: "plain",
            sixth: "clone",
            seventh: "gone",
        },
        worktrees=False,
    )
    wts = repo / ".claude" / "worktrees"
    wt1, sent_wt = _worktree(repo, "dev1"), _worktree(repo, "sentinel")
    (wts / "dev2").write_text("", encoding="utf-8")  # a file is not a worktree
    (wts / "stale").mkdir()  # a folder without .git is not a worktree
    (wts / "clone" / ".git").mkdir(parents=True)  # a nested clone is not a linked worktree
    elsewhere = _worktree(tmp_path / "elsewhere", "linked")
    (wts / "linked").symlink_to(elsewhere)  # a symlink is not a worktree in place
    (wts / "gone").symlink_to(tmp_path / "nowhere")  # nor is a dangling one, which -e cannot see
    # sentinel's worktree exists but its transcript sits only under the root: flagged, never silently the root
    home = _home(
        tmp_path,
        transcripts=((wt1, DEV1), (repo, DEV2), (repo, SENT), (repo, third), (repo, fifth)),
        root_only=True,
    )
    out = _run("--print", str(repo), home=home)
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [
        f"pane dev1 {DEV1} {wt1} ok",
        f"pane sentinel {SENT} {sent_wt} no-transcript",
    ], out.stdout
    assert f" {repo} " not in out.stdout, (
        out.stdout
    )  # no pane, and no run line, ever names the main checkout
    warned = sorted(
        ln.split(":")[1].strip()
        for ln in out.stderr.splitlines()
        if "no pane; it works in the main checkout" in ln
    )
    assert warned == ["clone", "dev2", "gone", "linked", "plain", "stale"], out.stderr


def _worktree(repo: Path, name: str) -> Path:
    """A git worktree's folder as the launcher sees it: `.claude/worktrees/<name>` holding a `.git` file."""
    wt = repo / ".claude" / "worktrees" / name
    wt.mkdir(parents=True, exist_ok=True)
    (wt / ".git").write_text(f"gitdir: {repo}/.git/worktrees/{name}\n", encoding="utf-8")
    return wt.resolve()


def test_the_launch_starts_each_pane_in_its_folder(tmp_path: Path) -> None:
    """The launch path hands tmux each pane's own folder — the first builder's to new-session, the next to its split —
    and reads each transcript under that folder, naming it when it is missing."""
    repo = _repo(tmp_path, {DEV1: "dev1", DEV2: "dev2"})
    wt1, wt2 = _worktree(repo, "dev1"), _worktree(repo, "dev2")
    home = _tmux_home(tmp_path, repo, has=False, owner=None, root_only=True)
    # dev1's transcript sits under its worktree; dev2's only under the root, where its pane does not start
    (home / ".claude-fleet" / "active" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(wt1))).mkdir(
        parents=True, exist_ok=True
    )
    (
        home
        / ".claude-fleet"
        / "active"
        / "projects"
        / re.sub(r"[^A-Za-z0-9]", "-", str(wt1))
        / f"{DEV1}.jsonl"
    ).write_text("{}\n", encoding="utf-8")
    out = _run(str(repo), home=home)
    assert out.returncode == 0, out.stderr
    log = _log(home)
    assert any(ln.startswith(f"new-session -d -s fabrik-lib -n agents -c {wt1} ") for ln in log), (
        log
    )
    assert any(ln.startswith(f"split-window -t @1 -c {wt2} ") for ln in log), log
    wt2_proj = (
        home / ".claude-fleet" / "active" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(wt2))
    )
    assert f"dev2: no transcript for session {DEV2} under {wt2_proj} " in out.stderr, out.stderr
    assert "dev1: no transcript" not in out.stderr, out.stderr


# --- the identity store (W-66e2f6a7): each builder resumes its newest whoami binding for this repo ----------------

NEW1 = "2b2b2b2b-2b2b-4b2b-8b2b-2b2b2b2b2b2b"
NEW2 = "3c3c3c3c-3c3c-4c3c-8c3c-3c3c3c3c3c3c"


def _git_repo(tmp: Path, registry: object) -> tuple[Path, str]:
    """A registry repo that is a real git repo, so it has a scope; returns (root, its git common dir)."""
    repo = _repo(tmp, registry)
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    return repo, str(repo / ".git")


def _store(tmp: Path, rows: list[object], name: str = "agent-identity.jsonl") -> Path:
    path = tmp / name
    path.write_text(
        "".join((r if isinstance(r, str) else json.dumps(r)) + "\n" for r in rows), encoding="utf-8"
    )
    return path


def _bind(sid: str, name: str, scope: str, at: object) -> dict:
    return {"session_id": sid, "name": name, "toplevel": scope, "at": at, "pid": 1, "force": True}


def _aged(home: Path, repo: Path, sid: str, age_s: float) -> None:
    """Set a transcript's mtime `age_s` seconds into the past (the registry id's last activity)."""
    import os
    import time

    t = time.time() - age_s
    for folder in _copies(repo, False):  # every copy _home wrote: the root's and its worktrees'
        f = (
            home
            / ".claude-fleet"
            / "active"
            / "projects"
            / re.sub(r"[^A-Za-z0-9]", "-", str(folder))
            / f"{sid}.jsonl"
        )
        if f.exists():
            os.utime(f, (t, t))


NOW = 2_000_000_000  # a binding time after every fixture transcript's mtime


def test_the_newest_binding_beats_a_stale_registry_row(tmp_path: Path) -> None:
    """The registry still names dev1's pre-/clear session, last active before dev1 re-bound: the binding wins and stderr
    says which session replaced which. A registry id the store never saw, with no later activity (a trimmed row, or a
    session the launcher started), gives way the same way."""
    repo, scope = _git_repo(tmp_path, {DEV1: "dev1", DEV2: "dev2"})
    store = _store(
        tmp_path,
        [
            _bind(DEV1, "dev1", scope, 100),
            _bind(NEW1, "dev1", scope, NOW),
            _bind(NEW2, "dev2", scope, NOW),
        ],
    )
    home = _home(tmp_path, transcripts=((repo, DEV1), (repo, NEW1), (repo, NEW2)))
    _aged(home, repo, DEV1, 3600)
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [
        f"pane dev1 {NEW1} {_wt(repo, 'dev1')} ok",
        f"pane dev2 {NEW2} {_wt(repo, 'dev2')} ok",
    ]
    assert (
        f"dev1: resuming {NEW1}, its newest whoami binding, not the registry's {DEV1}" in out.stderr
    )
    assert (
        f"dev2: resuming {NEW2}, its newest whoami binding, not the registry's {DEV2}" in out.stderr
    )


def test_a_registry_session_active_after_the_binding_stands(tmp_path: Path) -> None:
    """A registry id whose transcript moved after the binding was written is the live one (a session a writer
    registered as it started, never bound): it stands, and stderr says why."""
    repo, scope = _git_repo(tmp_path, {NEW2: "dev1"})
    store = _store(tmp_path, [_bind(DEV1, "dev1", scope, 100)])
    home = _home(tmp_path, transcripts=((repo, NEW2),))
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [f"pane dev1 {NEW2} {_wt(repo, 'dev1')} ok"]
    assert (
        f"dev1: the registry's {NEW2} was active after its binding {DEV1} — resuming {NEW2}"
        in out.stderr
    )


def test_a_session_belongs_to_the_name_on_its_last_row_anywhere(tmp_path: Path) -> None:
    """whoami's own reader: a session re-bound to another name — in this repo or any other — is that name's, so it
    never resumes under its old one; the last line naming a builder wins over a larger `at` (a clock that stepped
    back); and a session that would serve two panes refuses the launch."""
    repo, scope = _git_repo(tmp_path, {DEV1: "dev1", DEV2: "dev2"})
    rows = [
        _bind(DEV1, "dev1", scope, NOW + 10),
        _bind(NEW1, "dev1", scope, NOW),  # a later line with a smaller `at` still wins
        _bind(
            NEW1, "dev2", "/elsewhere/.git", NOW
        ),  # ...until another repo re-binds the session as dev2
        _bind(NEW2, "dev2", scope, NOW),
    ]
    store = _store(tmp_path, rows)
    home = _home(tmp_path, transcripts=((repo, DEV1), (repo, NEW2)))
    _aged(home, repo, DEV1, 3600)
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [
        f"pane dev1 {DEV1} {_wt(repo, 'dev1')} ok",
        f"pane dev2 {NEW2} {_wt(repo, 'dev2')} ok",
    ]
    assert f"resuming {NEW1}" not in out.stderr, out.stderr
    # the last line naming dev1 wins over a larger `at` on an earlier line (a clock that stepped back)
    store = _store(
        tmp_path,
        [_bind(NEW2, "dev1", scope, NOW + 10), _bind(NEW1, "dev1", scope, NOW)],
        "s2.jsonl",
    )
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout)[0] == f"pane dev1 {NEW1} {_wt(repo, 'dev1')} no-transcript", (
        out.stdout
    )
    # a registry that gives dev2 the session dev1 now owns: one session, two panes — refused
    two = tmp_path / "two"
    two.mkdir()
    r2, s2 = _git_repo(two, {DEV1: "dev1", NEW1: "dev2"})
    store = _store(two, [_bind(DEV1, "dev1", s2, 50), _bind(NEW1, "dev1", s2, NOW)])
    out = _run("--print", str(r2), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 2, out.stdout
    assert "pane " not in out.stdout
    assert f"session {NEW1} would serve dev1 and dev2" in out.stderr, out.stderr


def test_a_builder_never_takes_the_coordinators_session(tmp_path: Path) -> None:
    """The coordinator gets no pane, but its sessions still count: a binding that would put a builder on the session
    the registry gives the coordinator refuses the launch, and a coordinator binding adds no pane."""
    repo, scope = _git_repo(tmp_path, {DEV1: "dev1", COORD: "coordinator"})
    home = _home(tmp_path, transcripts=((repo, DEV1),))
    _aged(home, repo, DEV1, 3600)
    store = _store(tmp_path, [_bind(DEV1, "dev1", scope, 100), _bind(COORD, "dev1", scope, NOW)])
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 2, out.stdout
    assert f"session {COORD} would serve coordinator and dev1" in out.stderr, out.stderr
    store = _store(tmp_path, [_bind(NEW2, "coordinator", scope, NOW)], "s2.jsonl")
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [f"pane dev1 {DEV1} {_wt(repo, 'dev1')} ok"]


def test_a_broken_store_or_scope_falls_back_to_the_registry(tmp_path: Path) -> None:
    """Every store problem leaves the registry's ids, never the whole launch: a missing store, a directory or a FIFO
    at its path (never read, so never a hang), garbage lines, a row of another repo or of no repo, a malformed id,
    and a time no int() takes. A repo with no git scope never reads the store, and an inherited GIT_DIR cannot move
    the scope. In each case the registry's id is the binding's predecessor, so a row wrongly counted would flip it."""
    import os

    repo, scope = _git_repo(tmp_path, {DEV1: "dev1"})
    home = _home(tmp_path, transcripts=((repo, DEV1),))
    _aged(home, repo, DEV1, 3600)
    good = _bind(DEV1, "dev1", scope, 100)
    for i, bad in enumerate(
        [
            "not json",
            "[1, 2]",
            _bind(NEW1, "dev1", "/elsewhere/.git", NOW),
            _bind(NEW1, "dev1", "", NOW),
            _bind("NOT-A-UUID", "dev1", scope, NOW),
            _bind(NEW1.upper(), "dev1", scope, NOW),
            {"session_id": 7, "name": "dev1", "toplevel": scope, "at": NOW},
            _bind(NEW1, "Dev 1; rm -rf /", scope, NOW),
        ]
    ):
        store = _store(tmp_path, [good, bad], f"bad{i}.jsonl")
        out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
        assert out.returncode == 0, (bad, out.stderr)
        assert _panes(out.stdout) == [f"pane dev1 {DEV1} {_wt(repo, 'dev1')} ok"], (bad, out.stdout)
    # a time no int() takes reads as 0, as whoami's own `_at` does: the row still counts, the store is not lost
    store = _store(tmp_path, [_bind(NEW1, "dev1", scope, "²"), good], "sup.jsonl")
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0 and _panes(out.stdout) == [
        f"pane dev1 {DEV1} {_wt(repo, 'dev1')} ok"
    ], out.stderr
    assert "could not be read" not in out.stderr, out.stderr
    fifo = tmp_path / "fifo.jsonl"
    os.mkfifo(fifo)
    for store in (tmp_path / "missing.jsonl", tmp_path, fifo):
        out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
        assert out.returncode == 0, (store, out.stderr)
        assert _panes(out.stdout) == [f"pane dev1 {DEV1} {_wt(repo, 'dev1')} ok"], (
            store,
            out.stdout,
        )
        if store != tmp_path / "missing.jsonl":
            assert "is not a regular file" in out.stderr, (store, out.stderr)
    # an inherited GIT_DIR names another repo: the scope is still this repo's, so this repo's binding counts
    (tmp_path / "o").mkdir()
    other, _ = _git_repo(tmp_path / "o", {NEW2: "x"})
    store = _store(tmp_path, [good, _bind(NEW1, "dev1", scope, NOW)], "gd.jsonl")
    out = _run(
        "--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store), GIT_DIR=str(other / ".git")
    )
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [f"pane dev1 {NEW1} {_wt(repo, 'dev1')} no-transcript"], out.stdout
    # no git scope at all: the store is never read, even when it holds a binding of an empty scope
    (tmp_path / "plain").mkdir()
    plain = _repo(tmp_path / "plain", {DEV1: "dev1"})
    store = _store(tmp_path, [_bind(NEW1, "dev1", "", NOW)], "empty.jsonl")
    out = _run("--print", str(plain), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [f"pane dev1 {DEV1} {_wt(plain, 'dev1')} no-transcript"], (
        out.stdout
    )
    assert "no git scope" in out.stderr, out.stderr


def test_a_duplicate_name_resolves_through_the_store_or_refuses(tmp_path: Path) -> None:
    """A registry that kept dev1's old row beside its new one launches when the store names dev1's session; with no
    binding it is still refused, as before (D-1032's fail-closed rule, narrowed)."""
    repo, scope = _git_repo(tmp_path, {DEV1: "dev1", NEW1: "dev1"})
    home = _home(tmp_path, transcripts=((repo, NEW1),))
    store = _store(tmp_path, [_bind(NEW1, "dev1", scope, NOW)])
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [f"pane dev1 {NEW1} {_wt(repo, 'dev1')} ok"]
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(tmp_path / "none.jsonl"))
    assert out.returncode == 2, out.stdout
    assert "more than one session id" in out.stderr, out.stderr


def test_the_store_path_and_the_rebind_reach_the_panes(tmp_path: Path) -> None:
    """An AGENT_IDENTITY_FILE the launcher was given reaches each pane as an absolute path, so the panes' whoami writes
    the store the next launch reads; the exit hint names the re-bind and the launcher's absolute path."""
    repo, scope = _git_repo(tmp_path, {DEV1: "dev1", COORD: "coordinator"})
    store = _store(tmp_path, [_bind(NEW2, "coordinator", scope, NOW)])
    home = _home(tmp_path, transcripts=((repo, DEV1),))
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    run = [ln for ln in out.stdout.splitlines() if ln.startswith("run dev1 ")]
    assert len(run) == 1 and f"AGENT_IDENTITY_FILE={store}" in run[0], run
    assert f"after a /clear: whoami_agent.py --as dev1 --force, then {UP} {repo})]" in _hint(
        run[0], tmp_path
    )
    out = _run("--print", str(repo), home=home)
    run = [ln for ln in out.stdout.splitlines() if ln.startswith("run dev1 ")]
    assert "AGENT_IDENTITY_FILE" not in run[0], run
    # run by a relative path, the hint still names the launcher absolutely: a pane starts in another folder
    rel = subprocess.run(
        ["bash", UP.name, "--print", str(repo)],
        cwd=UP.parent,
        capture_output=True,
        text=True,
        timeout=30,
        env={"PATH": "/usr/bin:/bin", "HOME": str(home)},
    )
    run = [ln for ln in rel.stdout.splitlines() if ln.startswith("run dev1 ")]
    assert len(run) == 1 and f"then {UP} {repo})]" in _hint(run[0], tmp_path), (run, rel.stderr)


def test_a_missing_binding_and_a_newer_unbound_session_are_said(tmp_path: Path) -> None:
    """A builder with no binding in this scope resumes the registry's id and says so; a newer session transcript in its
    pane's folder that no binding or registry row names is pointed out with the re-bind command, because a /clear
    without the re-bind leaves exactly that. A file that is no session id is never taken for one."""
    import os
    import time

    repo, scope = _git_repo(tmp_path, {DEV1: "dev1", DEV2: "dev2"})
    store = _store(tmp_path, [_bind(DEV2, "dev2", scope, 100)])
    wt1, wt2 = _wt(repo, "dev1"), _wt(repo, "dev2")
    home = _home(tmp_path, transcripts=((wt1, DEV1), (wt2, DEV2), (wt1, NEW2)))
    projects = home / ".claude-fleet" / "active" / "projects"
    proj = projects / re.sub(r"[^A-Za-z0-9]", "-", str(wt1))
    old = time.time() - 3600
    for folder, sid in ((wt1, DEV1), (wt2, DEV2)):
        f = projects / re.sub(r"[^A-Za-z0-9]", "-", str(folder)) / f"{sid}.jsonl"
        os.utime(f, (old, old))
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert f"dev1: no whoami binding in {scope} — resuming the registry's {DEV1}" in out.stderr, (
        out.stderr
    )
    assert (
        f"a newer session {NEW2} is in {proj}" in out.stderr and "--as dev1 --force" in out.stderr
    ), out.stderr
    (proj / f"{NEW2}.jsonl").unlink()
    (proj / "not a session.jsonl").write_text("{}\n", encoding="utf-8")
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert "a newer session" not in out.stderr, out.stderr


OOM_LINE = "echo 200 > /proc/self/oom_score_adj 2>/dev/null; "
# the probed suppression (W-b9ad80ae T02, live on claude 2.1.312): one JSON constant on every claude call
SETTINGS = '{"skillOverrides":{"auto-mode-setup":"off"},"spinnerTipsEnabled":false}'


def _inner(run_line: str) -> str:
    """The pane command a `run` line carries: inside the scope's `bash -c '<it>'` when capped, else the line itself."""
    import shlex

    cmd = run_line.split(" ", 2)[2]
    if " -- bash -c " in cmd:
        return shlex.split(cmd.split(" -- bash -c ", 1)[1])[0]
    return cmd


def _hint(run_line: str, cwd: Path) -> str:
    """What a pane prints when claude exits: the hint command from its `run` line, executed by bash — and identically
    by a POSIX `sh` in the C locale, since tmux runs a pane's command with the user's own shell."""
    pane = _inner(run_line)
    cmd = re.search(r"; (printf '%s\\n' .*?); exec env ", pane)
    assert cmd, pane
    said = [
        subprocess.run(
            [shell, "-c", cmd.group(1)],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
            env={"PATH": "/usr/bin:/bin", "LANG": "C"},
        ).stdout.strip()
        for shell in ("bash", "sh")
    ]
    assert said[0] == said[1], said
    return said[0]


def test_the_exit_hint_never_runs_a_folder_name(tmp_path: Path) -> None:
    """The hint a pane prints when claude exits names the repo folder; a `$(...)`, a backtick or a `$NAME` in that name
    is printed, never run, and the printed command pastes back to the real folder."""
    for i, name in enumerate(("a$(touch pwned)b", "a`touch pwned`b", "a$HOME b", "q'uote")):
        base = tmp_path / str(i)
        base.mkdir()
        repo = _repo(base, {DEV1: "dev1"}, name=name)
        home = _home(base, transcripts=((repo, DEV1),))
        out = _run("--print", str(repo), home=home)
        assert out.returncode == 0, out.stderr
        run = [ln for ln in out.stdout.splitlines() if ln.startswith("run dev1 ")]
        said = _hint(run[0], base)
        assert not (base / "pwned").exists(), said
        tail = said.rsplit(" --force, then ", 1)[1].removesuffix(")]")
        # pasted into a shell, the printed command names the launcher and this folder, and runs nothing
        pasted = subprocess.run(
            ["bash", "-c", f"printf '%s\\n' {tail}"],
            cwd=base,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert pasted.stdout.splitlines() == [str(UP), str(repo)], (said, pasted.stderr)
        assert not (base / "pwned").exists(), said


def test_an_undated_binding_is_not_older_than_every_transcript(tmp_path: Path) -> None:
    """A binding whose `at` cannot be read (0) proves no age: the registry's id overrides it only when its transcript
    is newer than the binding session's own transcript, and with neither dated the binding stands."""
    repo, scope = _git_repo(tmp_path, {DEV1: "dev1"})
    store = _store(tmp_path, [_bind(NEW1, "dev1", scope, "not a time")])
    wt1 = _wt(repo, "dev1")
    home = _home(tmp_path, transcripts=((wt1, DEV1), (wt1, NEW1)))
    _aged(home, wt1, DEV1, 60)
    _aged(home, wt1, NEW1, 30)  # both transcripts dated; the binding's own is the newer
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [f"pane dev1 {NEW1} {_wt(repo, 'dev1')} ok"], out.stderr
    _aged(home, wt1, NEW1, 3600)  # ...and once the registry's is the newer, it stands
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert _panes(out.stdout) == [f"pane dev1 {DEV1} {_wt(repo, 'dev1')} ok"], out.stderr
    proj = home / ".claude-fleet" / "active" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(wt1))
    (proj / f"{NEW1}.jsonl").unlink()
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [f"pane dev1 {NEW1} {_wt(repo, 'dev1')} no-transcript"], out.stderr


def test_a_session_the_store_gives_the_coordinator_is_never_a_builders(tmp_path: Path) -> None:
    """A registry row naming a builder whose session the store says the coordinator now owns refuses the launch, the
    same as a registry row naming the coordinator: one session, two processes."""
    repo, scope = _git_repo(tmp_path, {DEV1: "dev1"})
    store = _store(
        tmp_path, [_bind(DEV1, "dev1", scope, 100), _bind(DEV1, "coordinator", scope, NOW)]
    )
    home = _home(tmp_path, transcripts=((repo, DEV1),))
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 2, out.stdout
    assert f"session {DEV1} would serve coordinator and dev1" in out.stderr, out.stderr


# --- W-89474fc1: repos with no registry, the coordinator from the ledger, and every pane capped -------------------

B1 = "4d4d4d4d-4d4d-4d4d-8d4d-4d4d4d4d4d4d"
B2 = "5e5e5e5e-5e5e-4e5e-8e5e-5e5e5e5e5e5e"
B3 = "6f6f6f6f-6f6f-4f6f-8f6f-6f6f6f6f6f6f"


def _bound_repo(tmp: Path, worktrees: tuple[str, ...] = ("b2", "b3")) -> tuple[Path, Path]:
    """A git repo with NO registry, as 7 of the 9 agent repos are: b1 works in the main checkout, b2 and b3 in their
    worktrees; the store binds all three here, and one name in another repo. Returns (root, store)."""
    repo = (tmp / "shop").resolve()
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    for name in worktrees:
        _worktree(repo, name)
    scope = str(repo / ".git")
    store = _store(
        tmp,
        [
            _bind(B1, "b1", scope, NOW),
            _bind(B2, "b2", scope, NOW),
            _bind(B3, "b3", scope, NOW),
            _bind(NEW1, "b9", "/opt/elsewhere/.git", NOW),
        ],
    )
    return repo, store


def _ledger(repo: Path, owner: str) -> None:
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs" / "DECISIONS.md").write_text(
        "| ID | When | Who | What | Why | Where |\n|---|---|---|---|---|---|\n"
        f"| D-001 | 2026-10-20 | operator | MERGE OWNER: {owner} | the coordinator | here |\n",
        encoding="utf-8",
    )


def test_no_registry_takes_builders_from_the_identity_store(tmp_path: Path) -> None:
    """A repo with no `.fabrik/session-agents.json` gets its builders from the names bound in its own scope, each
    resuming its binding; a bound name with no worktree gets no pane and, with no merge owner declared, is said to be
    taken as the coordinator; another repo's binding never appears."""
    repo, store = _bound_repo(tmp_path)
    home = _home(tmp_path, transcripts=((_wt(repo, "b2"), B2), (_wt(repo, "b3"), B3)))
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines()[0] == "session shop", out.stdout
    assert _panes(out.stdout) == [
        f"pane b2 {B2} {_wt(repo, 'b2')} ok",
        f"pane b3 {B3} {_wt(repo, 'b3')} ok",
    ], out.stdout
    assert (
        "b1: .claude/worktrees/b1 is not a linked git worktree in place — no pane" in out.stderr
    ), out.stderr
    assert "taken as the coordinator" in out.stderr and "b9" not in out.stdout, out.stderr
    assert "not the registry's" not in out.stderr, out.stderr  # there is no registry to name
    # a ledger that declares NO merge owner (decisions.py exit 3) launches the same way
    (repo / "docs").mkdir()
    (repo / "docs" / "DECISIONS.md").write_text(
        "| ID | When | Who | What | Why | Where |\n|---|---|---|---|---|---|\n"
        "| D-001 | 2026-10-20 | operator | adopt the work store | why | here |\n",
        encoding="utf-8",
    )
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0 and [p.split()[1] for p in _panes(out.stdout)] == ["b2", "b3"], (
        out.stderr
    )
    assert "taken as the coordinator" in out.stderr, out.stderr


def test_the_merge_owner_gets_no_pane(tmp_path: Path) -> None:
    """The repo's coordinator is its ledger's declared merge owner, never a position: here b2, which even has a
    worktree, gets no pane, and b1 (no worktree) is no longer said to be the coordinator."""
    repo, store = _bound_repo(tmp_path)
    _ledger(repo, "b2")
    home = _home(tmp_path, transcripts=((_wt(repo, "b3"), B3),))
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [f"pane b3 {B3} {_wt(repo, 'b3')} ok"], out.stdout
    assert "b2: the repo's merge owner (its coordinator) — no pane" in out.stderr, out.stderr
    assert "taken as the coordinator" not in out.stderr, out.stderr
    # a registry repo's merge owner is dropped the same way, whatever its name
    reg = _repo(tmp_path / "reg", {DEV1: "dev1", DEV2: "lead"})
    _ledger(reg, "lead")
    out = _run("--print", str(reg), home=_home(tmp_path / "reg"))
    assert [p.split()[1] for p in _panes(out.stdout)] == ["dev1"], (out.stdout, out.stderr)


def test_no_worktree_builder_refuses(tmp_path: Path) -> None:
    """Bindings but no worktree: nothing to launch, exit 3 (not the 2 of a refusal) — the main checkout is never a
    builder's pane."""
    repo, store = _bound_repo(tmp_path, worktrees=())
    out = _run("--print", str(repo), home=_home(tmp_path), AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 3 and "pane " not in out.stdout, out.stdout
    assert "has no builder with its own worktree" in out.stderr, out.stderr


def test_a_failed_merge_owner_lookup_refuses(tmp_path: Path) -> None:
    """A ledger that is there but cannot be read refuses the launch: a coordinator mistaken for a builder would get a
    pane. A repo with no ledger at all declares nobody and launches."""
    import os

    repo, store = _bound_repo(tmp_path)
    _ledger(repo, "b2")
    ledger = repo / "docs" / "DECISIONS.md"
    os.chmod(ledger, 0)
    try:
        out = _run("--print", str(repo), home=_home(tmp_path), AGENT_IDENTITY_FILE=str(store))
    finally:
        os.chmod(ledger, 0o644)
    assert out.returncode == 2 and "pane " not in out.stdout, out.stdout
    assert "could not read the merge owner" in out.stderr, out.stderr


def test_panes_run_capped_in_the_agents_slice(tmp_path: Path) -> None:
    """Every pane — claude, its hint and the shell it keeps — runs inside one `systemd-run --user --scope` in
    fabrik-agents.slice with MemorySwapMax=0 and TasksMax and NO MemoryMax of its own (the parent slice's ceiling bounds
    them all, W-6e656dac L5); --print reports each cap and never touches the slice, and a launch sets the slice's own
    ceiling first. A set FABRIK_AGENT_MEM_MAX is retired: warned about and ignored."""
    repo = _repo(tmp_path, {DEV1: "dev1", DEV2: "dev2"})
    home = _tmux_home(tmp_path, repo, has=False, owner=None)
    out = _run(
        "--print", str(repo), home=home, FABRIK_AGENT_MEM_MAX="2G", FABRIK_AGENT_TASKS_MAX="512"
    )
    assert out.returncode == 0, out.stderr
    assert "FABRIK_AGENT_MEM_MAX is retired" in out.stderr and "ignored" in out.stderr, out.stderr
    assert [ln for ln in out.stdout.splitlines() if ln.startswith("cap ")] == [
        "cap dev1 512",
        "cap dev2 512",
    ]
    for ln in out.stdout.splitlines():
        if ln.startswith("run "):
            assert (
                " systemd-run --user --scope --quiet --slice=fabrik-agents.slice -p MemorySwapMax=0"
                " -p TasksMax=512 -- bash -c '" in ln
            ), ln
            assert "MemoryMax" not in ln.split(" -- bash -c ")[0], ln
            assert "claude -n" in _inner(ln) or "already running" in _inner(ln), ln
    assert "set-property" not in (home / "systemctl.log").read_text(encoding="utf-8")
    out = _run(str(repo), home=home, FABRIK_AGENT_SLICE_MAX="12G")
    assert out.returncode == 0, out.stderr
    calls = (home / "systemctl.log").read_text(encoding="utf-8").splitlines()
    assert (
        "--user set-property --runtime fabrik-agents.slice MemoryHigh=infinity MemoryMax=12G"
        " MemorySwapMax=infinity" in calls
    ), calls
    created = [ln for ln in _log(home) if ln.startswith(("new-session", "split-window"))]
    assert len(created) == 2 and all("systemd-run --user --scope" in ln for ln in created), created


def _slice_line(home: Path, repo: Path, **env: str) -> tuple[str, str]:
    out = _run("--print", str(repo), home=home, **env)
    assert out.returncode == 0, out.stderr
    line = next(ln for ln in out.stdout.splitlines() if ln.startswith("slice "))
    return line, out.stderr


def test_the_slice_ceiling_follows_memtotal_and_the_nonagent_floor(tmp_path: Path) -> None:
    """W-6e656dac L5 + W-0b8a0fba: MemoryHigh = MemTotal - max(4G, floor) and MemoryMax = MemTotal - max(2G,
    floor - 2G), whole G, floor = FABRIK_AGENT_NONAGENT_FLOOR (12G); a 27 GiB box gets 15G/17G, a floor of 1G gives the
    plain MemTotal-4G / MemTotal-2G, MemTotal rounds DOWN to whole G, and the launch sets exactly that — never swap."""
    repo = _repo(tmp_path, {DEV1: "dev1"})
    home = _tmux_home(tmp_path, repo, has=False, owner=None)
    line, err = _slice_line(home, repo)
    assert line == "slice fabrik-agents.slice MemoryHigh=15G MemoryMax=17G", (line, err)
    assert "D-1075" not in err, err
    line, _ = _slice_line(home, repo, FABRIK_AGENT_NONAGENT_FLOOR="1G")
    assert line == "slice fabrik-agents.slice MemoryHigh=23G MemoryMax=25G", line
    line, _ = _slice_line(home, repo, FABRIK_AGENT_NONAGENT_FLOOR="6")  # whole G, the G is optional
    assert line == "slice fabrik-agents.slice MemoryHigh=21G MemoryMax=23G", line
    (home / "proc" / "meminfo").write_text(f"MemTotal: {27 * GIB + GIB - 1} kB\n", encoding="utf-8")
    line, _ = _slice_line(home, repo)  # 27.99 GiB is 27 whole G
    assert line == "slice fabrik-agents.slice MemoryHigh=15G MemoryMax=17G", line
    out = _run(str(repo), home=home)
    assert out.returncode == 0, out.stderr
    calls = (home / "systemctl.log").read_text(encoding="utf-8").splitlines()
    assert (
        "--user set-property --runtime fabrik-agents.slice MemoryHigh=15G MemoryMax=17G MemorySwapMax=infinity"
        in calls
    ), calls
    # the override replaces the derived MemoryMax and clears MemoryHigh
    line, _ = _slice_line(home, repo, FABRIK_AGENT_SLICE_MAX="20G")
    assert line == "slice fabrik-agents.slice MemoryHigh=infinity MemoryMax=20G", line


def test_a_small_or_unreadable_memtotal_keeps_the_old_ceiling_and_says_so(tmp_path: Path) -> None:
    """Under 8G, unreadable, or a floor that leaves nothing: D-1075's 16G MemoryMax, said on stderr; and a bad floor
    refuses."""
    repo = _repo(tmp_path, {DEV1: "dev1"})
    home = _tmux_home(tmp_path, repo, has=False, owner=None)
    for label, setup, why in (
        ("small", lambda: _meminfo(home, 7), "MemTotal is 7G, under 8G"),
        ("unreadable", lambda: _meminfo(home, None), "MemTotal is unreadable"),
        (
            "garbled",
            lambda: (home / "proc" / "meminfo").write_text("MemTotal: lots kB\n"),
            "unreadable",
        ),
    ):
        setup()
        line, err = _slice_line(home, repo)
        assert line == "slice fabrik-agents.slice MemoryHigh=infinity MemoryMax=16G", (label, line)
        assert why in err and "keeping D-1075's 16G ceiling" in err, (label, err)
    # a floor that leaves nothing never LOOSENS the cap: the minimum margins, said (an 8G box is not given 16G)
    for gib in (8, 12):
        _meminfo(home, gib)
        line, err = _slice_line(home, repo)
        assert line == f"slice fabrik-agents.slice MemoryHigh={gib - 4}G MemoryMax={gib - 2}G", (
            gib,
            line,
        )
        assert "leaves nothing" in err and "minimum margins" in err and "16G" not in err, err
    _meminfo(home, 8)
    line, _ = _slice_line(home, repo, FABRIK_AGENT_NONAGENT_FLOOR="2G")
    assert line == "slice fabrik-agents.slice MemoryHigh=4G MemoryMax=6G", line
    out = _run("--print", str(repo), home=home, FABRIK_AGENT_NONAGENT_FLOOR="12X")
    assert out.returncode == 2 and "bad FABRIK_AGENT_NONAGENT_FLOOR '12X'" in out.stderr, out.stderr


def test_an_oom_kill_is_named_in_the_hint(tmp_path: Path) -> None:
    """A pane whose claude the memory ceiling killed (exit 137) says so before the resume hint."""
    repo = _repo(tmp_path, {DEV1: "dev1"})
    home = _home(tmp_path, transcripts=((repo, DEV1),))
    fake = home / ".local" / "bin" / "claude"
    fake.write_text("#!/bin/sh\nexit 137\n", encoding="utf-8")
    fake.chmod(0o755)
    out = _run("--print", str(repo), home=home)
    run = next(ln for ln in out.stdout.splitlines() if ln.startswith("run dev1 "))
    got = subprocess.run(
        ["/bin/sh", "-c", run[len("run dev1 ") :]],
        capture_output=True,
        text=True,
        timeout=30,
        env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
        stdin=subprocess.DEVNULL,
    )
    assert (
        "[dev1 was killed (exit 137, SIGKILL) — in this capped pane most likely at the fabrik-agents.slice memory"
        " ceiling (MemoryMax=17G)]" in got.stdout
    ), got.stdout + got.stderr
    assert (
        "[dev1 exited — run: claude -n dev1 --permission-mode bypassPermissions --resume"
        in got.stdout
    ), got.stdout
    # an uncapped pane names the kill and never claims a ceiling it does not have
    (home / "manager-down").write_text("", encoding="utf-8")
    out = _run("--print", str(repo), home=home)
    run = next(ln for ln in out.stdout.splitlines() if ln.startswith("run dev1 "))
    got = subprocess.run(
        ["/bin/sh", "-c", run[len("run dev1 ") :]],
        capture_output=True,
        text=True,
        timeout=30,
        env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
        stdin=subprocess.DEVNULL,
    )
    assert (
        "[dev1 was killed (exit 137, SIGKILL)]" in got.stdout and "MemoryMax" not in got.stdout
    ), got.stdout


def test_a_scope_that_ends_badly_says_so_and_opens_no_uncapped_shell(tmp_path: Path) -> None:
    """A capped pane whose systemd-run fails says so, never a pane that just closes. The same branch runs when the kept
    shell inside the scope exits non-zero (review round 2), so it opens NO shell of its own — a shell there would be
    outside the cap — and only waits for Enter."""
    repo = _repo(tmp_path, {DEV1: "dev1"})
    home = _home(tmp_path, transcripts=((repo, DEV1),))
    fake = home / ".local" / "bin" / "claude"
    fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)

    def pane(stdin: str) -> str:
        out = _run("--print", str(repo), home=home)
        run = next(ln for ln in out.stdout.splitlines() if ln.startswith("run dev1 "))
        got = subprocess.run(
            ["/bin/sh", "-c", run[len("run dev1 ") :]],
            capture_output=True,
            text=True,
            timeout=30,
            env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
            input=stdin,
        )
        return got.stdout + got.stderr

    # the kept shell exits non-zero; a line typed after it must reach no second (uncapped) shell
    said = pane("false\nexit\necho ESCAPED\n")
    assert (
        "the capped scope ended with exit 1" in said and "press Enter to close this pane" in said
    ), said
    assert "ESCAPED" not in said, said
    # systemd-run itself cannot start the scope
    (home / ".local" / "bin" / "systemd-run").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    said = pane("echo ESCAPED\n")
    assert (
        "[dev1: the capped scope ended with exit 1 — if nothing ran above, systemd-run could not start it"
        in said
    )
    assert "ESCAPED" not in said, said


def test_no_user_manager_runs_uncapped_with_a_warning(tmp_path: Path) -> None:
    """No systemd user manager answers: the panes still open, uncapped, and that is said on stderr AND inside every
    pane (the launcher's stderr is repainted by the attach)."""
    repo = _repo(tmp_path, {DEV1: "dev1"})
    home = _home(tmp_path, transcripts=((repo, DEV1),))
    (home / "manager-down").write_text("", encoding="utf-8")
    out = _run("--print", str(repo), home=home)
    assert out.returncode == 0, out.stderr
    assert "WARNING — no systemd-run on PATH, or no systemd user manager answers" in out.stderr, (
        out.stderr
    )
    assert "cap dev1 uncapped" in out.stdout, out.stdout
    run = next(ln for ln in out.stdout.splitlines() if ln.startswith("run dev1 "))
    assert run.startswith("run dev1 echo '[UNCAPPED:") and "systemd-run" not in run, run


def test_a_malformed_cap_refuses(tmp_path: Path) -> None:
    """A cap is <digits><K|M|G> from 1M (a task count 1 to 999999); 0, a bare number, an unknown unit or a size under
    1M would be a cap that kills everything or that systemd misreads, so each refuses the launch. An empty value is
    the default, as in capped_run.sh."""
    repo = _repo(tmp_path, {DEV1: "dev1"})
    home = _home(tmp_path, transcripts=((repo, DEV1),))
    for var, value in (
        ("FABRIK_AGENT_SLICE_MAX", "0G"),
        ("FABRIK_AGENT_SLICE_MAX", "512K"),
        ("FABRIK_AGENT_SLICE_MAX", "16"),
        ("FABRIK_AGENT_SLICE_MAX", "1T"),
        ("FABRIK_AGENT_TASKS_MAX", "0"),
        ("FABRIK_AGENT_TASKS_MAX", "1e3"),
        ("FABRIK_AGENT_TASKS_MAX", "1000000"),
    ):
        out = _run("--print", str(repo), home=home, **{var: value})
        assert out.returncode == 2 and "pane " not in out.stdout, (var, value, out.stdout)
        assert f"bad {var} '{value}'" in out.stderr, (var, value, out.stderr)
    ok = _run(
        "--print",
        str(repo),
        home=home,
        FABRIK_AGENT_SLICE_MAX="1024K",
        FABRIK_AGENT_TASKS_MAX="999999",
    )
    assert ok.returncode == 0 and "cap dev1 999999" in ok.stdout, ok.stderr


def test_the_bus_is_found_without_xdg_and_a_refused_slice_refuses(tmp_path: Path) -> None:
    """A launch from a `.bat` (`wsl.exe --exec bash -l`) has no XDG_RUNTIME_DIR, so the launcher sets it when the user
    bus is there, before it asks the manager anything; and a manager that answers but refuses the slice ceiling
    refuses the launch rather than open panes with no total bound (capped_run.sh's rule)."""
    import os

    bus = Path(f"/run/user/{os.getuid()}/bus")
    repo = _repo(tmp_path, {DEV1: "dev1"})
    home = _tmux_home(tmp_path, repo, has=False, owner=None)
    strict = home / ".local" / "bin" / "systemctl"
    strict.write_text(
        '#!/bin/sh\n[ -n "$XDG_RUNTIME_DIR" ] || exit 1\n' + FAKE_SYSTEMCTL.split("\n", 1)[1],
        encoding="utf-8",
    )
    out = _run("--print", str(repo), home=home)  # _run passes no XDG_RUNTIME_DIR
    if bus.is_socket():
        assert "cap dev1 1024" in out.stdout, (out.stdout, out.stderr)
        assert f"XDG_RUNTIME_DIR=/run/user/{os.getuid()}" in out.stdout, out.stdout
    else:
        assert "cap dev1 uncapped" in out.stdout, out.stdout
    (home / "slice-refused").write_text("", encoding="utf-8")
    out = _run(str(repo), home=home, XDG_RUNTIME_DIR=str(tmp_path))
    assert out.returncode == 2, out.stderr
    assert (
        "refused the fabrik-agents.slice ceiling (MemoryHigh=15G MemoryMax=17G) — not launching"
        in out.stderr
    ), out.stderr
    log = _log(home) if (home / "tmux.log").exists() else []
    assert not any(ln.startswith(("new-session", "attach")) for ln in log), log
    # reattaching to this repo's running grid starts nothing, so a refused ceiling never blocks it
    (home / "tmux-has").write_text("", encoding="utf-8")
    (home / "tmux-owner").write_text(f"{repo}\n", encoding="utf-8")
    out = _run(str(repo), home=home, tty=True, XDG_RUNTIME_DIR=str(tmp_path))
    assert out.returncode == 0 and _log(home)[-1] == "attach -t =fabrik-lib", (
        out.stderr,
        _log(home),
    )


# --- T05 (W-6e656dac): --detach, the wake prompt and watchdog, the uncapped policy, the non-TTY caller (W-1961cc42) ---


def test_detach_builds_the_grid_and_never_attaches(tmp_path: Path) -> None:
    """`--detach` stops before attach/switch-client — from inside tmux too, with the grid new or already up, and
    whether or not a terminal is there — and says so."""
    repo = _repo(tmp_path, {DEV1: "dev1", DEV2: "dev2"})
    new = _tmux_home(tmp_path / "new", repo, has=False, owner=None)
    out = _run("--detach", str(repo), home=new, tty=True, TMUX="/tmp/tmux-1000/default,1,0")
    assert out.returncode == 0, out.stderr
    log = _log(new)
    assert any(ln.startswith("new-session -d -s fabrik-lib") for ln in log), log
    assert f"set-option -t =fabrik-lib: @agents_up_root {repo}" in log, log
    assert not any(ln.startswith(("attach", "switch-client")) for ln in log), log
    assert "--detach — the fabrik-lib grid is up, not attaching" in out.stderr, out.stderr
    up = _tmux_home(tmp_path / "up", repo, has=True, owner=str(repo))
    out = _run(
        str(repo), "--detach", home=up, tty=True
    )  # flags lead: this is a usage error, never an attach
    assert out.returncode == 2 and "usage:" in out.stderr, out.stderr
    out = _run("--detach", str(repo), home=up, tty=True)
    assert out.returncode == 0 and "leaving it as it is" in out.stderr, out.stderr
    assert not any(ln.startswith(("new-session", "split-window", "attach")) for ln in _log(up)), (
        _log(up)
    )


def test_a_caller_with_no_terminal_detaches_and_says_so(tmp_path: Path) -> None:
    """W-1961cc42: from a non-TTY shell (a coordinator's Bash tool) the grid is built, its root is recorded (the option
    write uses the target tmux 3.4 accepts) and the script detaches saying so, instead of failing at `attach`."""
    repo = _repo(tmp_path, {DEV1: "dev1", DEV2: "dev2"})
    home = _tmux_home(tmp_path, repo, has=False, owner=None)
    out = _run(str(repo), home=home)  # pipes for stdin and stdout
    assert out.returncode == 0, out.stderr
    log = _log(home)
    assert f"set-option -t =fabrik-lib: @agents_up_root {repo}" in log, log
    assert "could not record the root" not in out.stderr, out.stderr
    assert "no terminal on stdin/stdout" in out.stderr and "left detached" in out.stderr, out.stderr
    assert "tmux attach -t =fabrik-lib" in out.stderr, out.stderr
    assert not any(ln.startswith("attach") for ln in log), log


def test_an_up_grid_is_attached_not_rebuilt_and_the_owner_read_uses_the_option_target(
    tmp_path: Path,
) -> None:
    """W-e841ac37: without --detach a grid that is already up is ATTACHED (a terminal) and never rebuilt, and the
    ownership read that gates it uses the target tmux 3.4 accepts (the fake fails the bare `=name` form)."""
    repo = _repo(tmp_path, {DEV1: "dev1", DEV2: "dev2"})
    home = _tmux_home(tmp_path, repo, has=True, owner=str(repo))
    out = _run(str(repo), home=home, tty=True)
    assert out.returncode == 0, out.stderr
    log = _log(home)
    assert "show-options -t =fabrik-lib: -v @agents_up_root" in log, log
    assert not any(ln.startswith(("new-session", "split-window")) for ln in log), log
    assert log[-1] == "attach -t =fabrik-lib", log


def test_each_pane_runs_claude_with_the_wake_prompt_watchdog_and_oom_score(tmp_path: Path) -> None:
    """The relaunch (L1, L4, L5): `claude -n <name> --permission-mode bypassPermissions --resume <sid> "<wake prompt>"`
    with CLAUDE_CODE_RETRY_WATCHDOG=1 in the allow-listed env and oom_score_adj 200 set before claude starts; the prompt
    orders the self-watch arm, then `hibernate.py woke --self <sid>`, resuming from its seed only on exit 0; the mode is
    passed because a --resume keeps the session's saved mode (operator ruling 2026-10-30, W-b9b6472e). The
    pane command is EXECUTED against a fake claude that prints its argv and env."""
    repo = _repo(tmp_path, {DEV1: "dev1"})
    home = _home(tmp_path, transcripts=((repo, DEV1),))
    fake = home / ".local" / "bin" / "claude"
    fake.write_text(
        '#!/bin/sh\nprintf "ARG<%s>\\n" "$@"\nenv | grep -E "^CLAUDE_CODE_RETRY_WATCHDOG="\n'
        "grep oom_score_adj /dev/null; cat /proc/self/oom_score_adj | sed 's/^/OOM=/'\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    out = _run("--print", str(repo), home=home)
    run = next(ln for ln in out.stdout.splitlines() if ln.startswith("run dev1 "))
    got = subprocess.run(
        ["/bin/sh", "-c", run[len("run dev1 ") :]],
        capture_output=True,
        text=True,
        timeout=30,
        env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
        stdin=subprocess.DEVNULL,
    )
    args = re.findall(r"^ARG<(.*)>$", got.stdout, flags=re.M)
    assert (
        args[:8]
        == [
            "-n",
            "dev1",
            "--permission-mode",
            "bypassPermissions",
            "--resume",
            DEV1,
            "--settings",
            SETTINGS,
        ]
        and len(args) == 9
    ), got.stdout
    prompt = args[8]
    hub = UP.resolve().parent.parent.parent  # $HUB: the checkout the launcher runs from, double-quoted in the prose (no /opt/fabrik literal)
    assert f'bash "{hub}/scripts/sysadmin/selfwatch_arm.sh" {DEV1} in the background' in prompt, (
        prompt
    )
    assert "/opt/fabrik/scripts" not in prompt or str(hub) == "/opt/fabrik", prompt
    assert f'python3 "{hub}/scripts/sysadmin/hibernate.py" woke --self {DEV1}' in prompt, prompt
    assert "only if it exits 0, resume your item from the seed it prints" in prompt, prompt
    # review G3: `woke` exit 2 cannot tell (a corrupt marker or run record) — stay paused, never carry on; the
    # relaunch prompt and the self-watch's hibernate RESUME line carry the SAME clause (both files read)
    clause = (
        "only if it exits 0, resume your item from the seed it prints; on exit 1 carry on as usual;"
        " on exit 2 stay paused and tell your coordinator"
    )
    assert clause in prompt, prompt
    assert clause in (UP.parent / "mesh" / "claude-selfwatch.sh").read_text(encoding="utf-8")
    assert "on any other exit" not in prompt, prompt
    assert "CLAUDE_CODE_RETRY_WATCHDOG=1" in got.stdout, got.stdout
    assert re.search(r"^OOM=(200|[3-9]\d\d|1000)$", got.stdout, flags=re.M), got.stdout
    assert "--dangerously" not in run, run
    assert "--permission-mode bypassPermissions --resume" in _hint(run, tmp_path), run
    # the quoting survives the nested single quotes of the scope's `bash -c '<inner>'` for ANY folder name
    assert "'" not in prompt and "$" not in prompt, prompt


def test_every_claude_command_cmd_of_builds_carries_the_permission_mode() -> None:
    """W-b9b6472e (operator ruling 2026-10-30: every agent runs in bypassPermissions): a `--resume` keeps the saved
    mode, so EVERY `claude -n` the pane builder writes — each launch branch and each printed relaunch line — names
    `$perm`, and `$perm` is the one value. The routes (grid start, --pane-cmd, the spawn and --move launches) all go
    through `cmd_of`; the behaviour tests above execute three of them, this one stops a future branch dropping it.
    It reads the CODE lines only (comments stripped) and is keyed on the shapes a launch takes there — a `claude=`
    assignment (any spelling of the command after it) and a printed `run: claude` hint — never on one `-n` spelling,
    so `${perm}`, a reordered flag or a comment naming `claude -n` stays green, and a new branch spelled
    `claude --name …` or `command claude …` without the mode goes red (review pass 1, all three seats)."""
    text = UP.read_text(encoding="utf-8")
    body = text[text.index("cmd_of() {") : text.index("\ncap_of() {")]
    # code lines only: whole-line comments dropped and a trailing ` # …` cut (cmd_of quotes no ` #` in its strings)
    code = "\n".join(
        re.sub(r"\s+#.*$", "", ln) for ln in body.splitlines() if not ln.lstrip().startswith("#")
    )
    mode = re.compile(r"\$\{?perm\}?(?![A-Za-z0-9_])")
    # one value, assigned once: a second assignment (or a conditional one) could switch every launch back
    assigns = re.findall(r"^\s*(?:local\s+(?:-\w+\s+)?)?perm=(.*)$", code, flags=re.M)
    assert len(assigns) == 1, assigns
    assert assigns[0].strip("'\" ") == "--permission-mode bypassPermissions", assigns
    # no other permission mode anywhere in the builder's code
    assert code.count("--permission-mode") == 1, code
    # every launch assignment and every printed relaunch line names the mode; an array form is refused outright
    assert not re.search(r"^\s*(?:local\s+)?claude=\(", code, flags=re.M), "claude=( array launch"
    # any assignment to `claude` — `local` or not, quoted any way, alone or after a `;` (review pass 2, Opus N1)
    launches = re.findall(r"(?:^|;)\s*(?:local\s+)?claude=(\S[^\n]*)$", code, flags=re.M)
    hints = re.findall(r"run: claude[^\n]*", code)
    assert len(launches) >= 3 and len(hints) >= 2, (launches, hints)  # 3 launch branches + 2 hints
    assert all(mode.search(ln) for ln in launches + hints), launches + hints


def test_an_up_grid_with_no_readable_root_is_attached_on_a_real_server(tmp_path: Path) -> None:
    """W-e841ac37 on a real scratch tmux server: a same-named grid that records no root and is not this repo's builders
    (made by hand) is attached-to (left detached for a non-TTY caller) with the warning, never refused."""
    server = f"t05o-{os.getpid()}"
    repo = _repo(tmp_path, {DEV1: "dev1"})
    home = _home(tmp_path, transcripts=((repo, DEV1),))
    real = shutil.which("tmux")
    assert real, "tmux is the launcher's own dependency"
    wrapper = home / ".local" / "bin" / "tmux"
    wrapper.write_text(f'#!/bin/sh\nexec {real} -L {server} "$@"\n', encoding="utf-8")
    wrapper.chmod(0o755)
    try:
        subprocess.run(
            [real, "-L", server, "new-session", "-d", "-s", "fabrik-lib", "sleep 120"], check=True
        )
        out = _run(str(repo), home=home)
        assert out.returncode == 0, out.stderr
        assert "attaching to it anyway" in out.stderr and "left detached" in out.stderr, out.stderr
        assert "not attaching" not in out.stderr, out.stderr
    finally:
        subprocess.run([real, "-L", server, "kill-server"], capture_output=True)


def test_an_uncapped_start_is_refused_on_the_bat_path_and_allowed_on_the_boot_path(
    tmp_path: Path,
) -> None:
    """No user manager: the interactive path refuses naming why (exit 2, nothing launched) unless
    FABRIK_AGENTS_UNCAPPED=1; --detach (the boot path) launches uncapped with D-1075's warning."""
    repo = _repo(tmp_path, {DEV1: "dev1"})
    home = _tmux_home(tmp_path, repo, has=False, owner=None)
    (home / "manager-down").write_text("", encoding="utf-8")
    out = _run(str(repo), home=home, tty=True)
    assert out.returncode == 2, out.stderr
    assert "not launching" in out.stderr and "FABRIK_AGENTS_UNCAPPED=1" in out.stderr, out.stderr
    assert not (home / "tmux.log").exists() or not any(
        ln.startswith("new-session") for ln in _log(home)
    ), _log(home)
    out = _run(str(repo), home=home, tty=True, FABRIK_AGENTS_UNCAPPED="1")
    assert out.returncode == 0 and "UNCAPPED" in out.stderr, out.stderr
    assert any(ln.startswith("new-session") for ln in _log(home)), _log(home)
    boot = _tmux_home(tmp_path / "boot", repo, has=False, owner=None)
    (boot / "manager-down").write_text("", encoding="utf-8")
    out = _run("--detach", str(repo), home=boot)
    assert out.returncode == 0 and "WARNING — no systemd-run on PATH" in out.stderr, out.stderr
    assert any(ln.startswith("new-session") for ln in _log(boot)), _log(boot)
    # a grid already up needs no start, so it is never refused for lacking a manager
    up = _tmux_home(tmp_path / "up", repo, has=True, owner=str(repo))
    (up / "manager-down").write_text("", encoding="utf-8")
    out = _run(str(repo), home=up, tty=True)
    assert out.returncode == 0 and _log(up)[-1] == "attach -t =fabrik-lib", (out.stderr, _log(up))


def test_on_a_real_tmux_server_the_root_is_recorded_and_a_relaunch_finds_its_own_grid(
    tmp_path: Path,
) -> None:
    """W-1961cc42 measured on a scratch `tmux -L` server (the box's tmux 3.4 behaviour is in the log): a non-TTY launch
    builds the grid and records the root readably; a second launch — non-TTY, no --detach — finds the grid up, does NOT
    refuse it, and builds nothing; --detach on the up grid exits 0."""
    server = f"t05-{os.getpid()}"
    repo = _repo(tmp_path, {DEV1: "dev1"})
    home = _home(tmp_path, transcripts=((repo, DEV1),))
    wrapper = home / ".local" / "bin" / "tmux"
    real = shutil.which("tmux")
    assert real, "tmux is the launcher's own dependency"
    wrapper.write_text(f'#!/bin/sh\nexec {real} -L {server} "$@"\n', encoding="utf-8")
    wrapper.chmod(0o755)
    claude = home / ".local" / "bin" / "claude"
    claude.write_text("#!/bin/sh\nsleep 120\n", encoding="utf-8")
    claude.chmod(0o755)

    def tmux(*a: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([real, "-L", server, *a], capture_output=True, text=True, timeout=20)

    try:
        first = _run(str(repo), home=home)
        assert first.returncode == 0, first.stderr
        assert "could not record the root" not in first.stderr, first.stderr
        assert "left detached" in first.stderr, first.stderr
        got = tmux("show-options", "-t", "=fabrik-lib:", "-v", "@agents_up_root")
        assert got.stdout.strip() == str(repo), (got.stdout, got.stderr)
        panes = tmux("list-panes", "-s", "-t", "=fabrik-lib", "-F", "x").stdout.split()
        second = _run(str(repo), home=home)
        assert second.returncode == 0, second.stderr
        assert "not attaching" not in second.stderr and "leaving it as it is" in second.stderr, (
            second.stderr
        )
        assert tmux("list-panes", "-s", "-t", "=fabrik-lib", "-F", "x").stdout.split() == panes
        third = _run("--detach", str(repo), home=home)
        assert third.returncode == 0 and "--detach" in third.stderr, third.stderr
    finally:
        tmux("kill-server")


# --- W-456aa02a: a pane starts in the worktree its session lives in, not only the one named after the builder ------
# Claude Code keeps the folder a pane STARTED in as the window's project folder (CLAUDE_PROJECT_DIR: its hooks,
# settings and permissions) even after the session moves into another worktree; infra's pane started in
# `worktrees/infra` (1602 commits behind master) while infra worked in `infra-uncapped`, so every hook fix since was off
# for that window. The worktree whose claude project folder holds the session is where the agent works.


def _transcript(home: Path, folder: Path, sid: str) -> None:
    proj = (
        home / ".claude-fleet" / "active" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(folder))
    )
    proj.mkdir(parents=True, exist_ok=True)
    (proj / f"{sid}.jsonl").write_text("{}\n", encoding="utf-8")


AGENT_TREE = "agent-a0123456789abcdef"
LONER = "7a7a7a7a-7a7a-4a7a-8a7a-7a7a7a7a7a7a"
STALE1 = "9c9c9c9c-9c9c-4c9c-8c9c-9c9c9c9c9c9c"
STALE2 = "adadadad-adad-4dad-8dad-adadadadadad"
GHOST = "8b8b8b8b-8b8b-4b8b-8b8b-8b8b8b8b8b8b"


def test_a_pane_starts_where_its_session_lives(tmp_path: Path) -> None:
    """B1: a builder whose session sits in another linked worktree starts there, said on stderr, with an `ok` status; a
    builder with no own-named worktree gets that pane too once the repo declares a merge owner; a Claude Code subagent
    tree (`agent-*`) is taken but flagged; the coordinator's own worktree is never a builder's; a worktree-less name no
    tree holds is dropped before its stale rows can refuse the launch; the launch path hands tmux the found folder."""
    repo = _repo(
        tmp_path,
        {DEV1: "infra", DEV2: "dev2", LONER: "loner", STALE1: "ghost", STALE2: "ghost"},
        worktrees=False,
    )
    _worktree(repo, "infra")
    _worktree(repo, "dev2")
    uncapped, sub = _worktree(repo, "infra-uncapped"), _worktree(repo, AGENT_TREE)
    coord = _worktree(repo, "coordinator")
    _ledger(repo, "coordinator")
    home = _home(tmp_path, transcripts=((repo, DEV1), (repo, DEV2), (repo, LONER)), root_only=True)
    _transcript(home, uncapped, DEV1)
    _transcript(home, _wt(repo, "dev2"), DEV2)
    _transcript(home, sub, LONER)
    # the coordinator's tree also holds loner's session: never a candidate
    _transcript(home, coord, LONER)
    # ghost's session sits only in ANOTHER builder's own-named tree: ghost is still dropped before its stale rows
    _transcript(home, _wt(repo, "dev2"), STALE1)
    out = _run("--print", str(repo), home=home)
    assert out.returncode == 0, out.stderr
    assert "more than one session id" not in out.stderr, (
        out.stderr
    )  # ghost's two stale rows never read
    assert (
        "ghost: .claude/worktrees/ghost is not a linked git worktree in place — no pane"
        in out.stderr
    ), out.stderr
    assert _panes(out.stdout) == [
        f"pane dev2 {DEV2} {_wt(repo, 'dev2')} ok",
        f"pane infra {DEV1} {uncapped} ok",
        f"pane loner {LONER} {sub} ok",
    ], out.stdout
    assert (
        f"infra: starts in .claude/worktrees/infra-uncapped, where its session {DEV1} lives"
        in out.stderr
    ), out.stderr
    assert "dev2: starts in" not in out.stderr, out.stderr
    assert f"loner: starts in .claude/worktrees/{AGENT_TREE}" in out.stderr, out.stderr
    assert "a Claude Code subagent tree" in out.stderr, out.stderr
    # the launch path hands tmux the found folder
    tmux = home / ".local" / "bin" / "tmux"
    tmux.write_text(FAKE_TMUX, encoding="utf-8")
    tmux.chmod(0o755)
    out = _run(str(repo), home=home)
    assert out.returncode == 0, out.stderr
    log = _log(home)
    assert any(ln.startswith(f"split-window -t @1 -c {uncapped} ") for ln in log), log


def test_a_session_only_under_the_root_keeps_the_named_tree(tmp_path: Path) -> None:
    """B2: a session no worktree holds (only the root's archive link) keeps today's pane in `<name>`, flagged
    `no-transcript` as today — the root is never a candidate, and no `starts in` line is printed."""
    repo = _repo(tmp_path, {DEV1: "dev1"})
    _worktree(repo, "other")
    home = _home(tmp_path, transcripts=((repo, DEV1),), root_only=True)
    out = _run("--print", str(repo), home=home)
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [f"pane dev1 {DEV1} {_wt(repo, 'dev1')} no-transcript"], out.stdout
    assert "starts in" not in out.stderr, out.stderr


def test_a_session_in_several_trees_keeps_the_named_tree(tmp_path: Path) -> None:
    """B3: several holding folders → `<name>`, said; another builder's own-named tree is never taken from it; a folder
    off the agent-name grammar is no candidate; and with NO merge owner declared, a name without its own worktree keeps
    today's no-pane line however its session is filed (it is taken as the coordinator)."""
    repo = _repo(
        tmp_path, {DEV1: "dev1", DEV2: "dev2", SENT: "sent", GHOST: "ghost"}, worktrees=False
    )
    for name in ("dev1", "dev2", "sent"):
        _worktree(repo, name)
    a, b, odd = _worktree(repo, "spare-a"), _worktree(repo, "spare-b"), _worktree(repo, "Odd_Tree")
    home = _home(
        tmp_path,
        transcripts=((repo, DEV1), (repo, DEV2), (repo, SENT), (repo, GHOST)),
        root_only=True,
    )
    _transcript(home, a, DEV1)
    _transcript(home, b, DEV1)
    _transcript(
        home, _wt(repo, "dev1"), DEV1
    )  # dev1: three holders, its own tree among them — still said
    _transcript(home, _wt(repo, "dev1"), DEV2)  # dev2's session sits only in dev1's own-named tree
    _transcript(home, odd, SENT)  # sent's only holder is off the agent-name grammar
    _transcript(home, a, GHOST)  # ghost has no own worktree and no merge owner is declared
    out = _run("--print", str(repo), home=home)
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [
        f"pane dev1 {DEV1} {_wt(repo, 'dev1')} ok",
        f"pane dev2 {DEV2} {_wt(repo, 'dev2')} no-transcript",
        f"pane sent {SENT} {_wt(repo, 'sent')} no-transcript",
    ], out.stdout
    assert (
        f"dev1: session {DEV1} sits in more than one worktree (dev1, spare-a, spare-b)"
        in out.stderr
    ), out.stderr
    assert (
        "ghost: .claude/worktrees/ghost is not a linked git worktree in place — no pane"
        in out.stderr
    ), out.stderr
    assert "taken as the coordinator" in out.stderr, out.stderr
    assert "starts in" not in out.stderr, out.stderr


def test_two_builders_in_one_tree_fall_back(tmp_path: Path) -> None:
    """B4: two builders whose sessions both resolve to one folder each fall back to `<name>`, said on stderr with the
    folder and both sids, and the rest of the grid still launches (never a whole-launch refusal)."""
    repo = _repo(tmp_path, {DEV1: "dev1", DEV2: "dev2", SENT: "sent"})
    shared = _worktree(repo, "shared")
    home = _home(tmp_path, transcripts=((repo, DEV1), (repo, DEV2), (repo, SENT)), root_only=True)
    _transcript(home, shared, DEV1)
    _transcript(home, shared, DEV2)
    _transcript(home, _wt(repo, "sent"), SENT)
    out = _run("--print", str(repo), home=home)
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [
        f"pane dev1 {DEV1} {_wt(repo, 'dev1')} no-transcript",
        f"pane dev2 {DEV2} {_wt(repo, 'dev2')} no-transcript",
        f"pane sent {SENT} {_wt(repo, 'sent')} ok",
    ], out.stdout
    assert (
        f"dev1, dev2: sessions {DEV1}, {DEV2} both sit in .claude/worktrees/shared" in out.stderr
    ), out.stderr


# --- W-b9ad80ae T02: the spawned launch path (`--pane-cmd`, `--session-id`, suppression, exit 3, running by name) ---


def _spawn_repo(tmp: Path, spawned: bool = True) -> tuple[Path, Path, str]:
    """A registry-less repo whose builders b2 and b3 are bound by the SPAWNER (`spawned: true`, null pid — T01), with
    worktrees and no transcript yet. Returns (root, store, scope)."""
    repo, _ = _bound_repo(tmp)
    scope = str(repo / ".git")
    rows = [
        {
            **_bind(sid, name, scope, NOW),
            "pid": None,
            "force": False,
            **({"spawned": True} if spawned else {}),
        }
        for sid, name in ((B2, "b2"), (B3, "b3"))
    ]
    return repo, _store(tmp, rows, "spawn.jsonl"), scope


def _fake_claude(home: Path) -> None:
    fake = home / ".local" / "bin" / "claude"
    fake.write_text('#!/bin/sh\nprintf "ARG<%s>\\n" "$@"\n', encoding="utf-8")
    fake.chmod(0o755)


def _argv(home: Path, command: str) -> list[str]:
    """Execute a pane command with a fake `claude` that prints its argv; the claude arguments it received."""
    got = subprocess.run(
        ["/bin/sh", "-c", command],
        capture_output=True,
        text=True,
        timeout=30,
        env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
        stdin=subprocess.DEVNULL,
    )
    return re.findall(r"^ARG<(.*)>$", got.stdout, flags=re.M)


def _runs(stdout: str) -> dict[str, str]:
    return {ln.split()[1]: _inner(ln) for ln in stdout.splitlines() if ln.startswith("run ")}


def test_a_spawned_builder_with_no_transcript_launches_with_session_id(tmp_path: Path) -> None:
    """D2 (W-14219e6f point 13, B14): a builder bound by the spawner (`spawned: true`) whose session has no transcript in
    ANY project folder launches `--session-id` with the first prompt; with the transcript under any other folder, with a
    later non-spawned row (its own re-bind), or with no `spawned` flag at all it resumes."""
    repo, store, scope = _spawn_repo(tmp_path)
    home = _home(tmp_path)
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    runs = _runs(out.stdout)
    assert (
        f"claude -n b2 --permission-mode bypassPermissions --session-id {B2} --settings '{SETTINGS}' 'You were started by agents_up"
        in runs["b2"]
    ), runs["b2"]
    assert "--resume" not in runs["b2"].split("; rc=")[0], runs["b2"]
    assert f"--session-id {B3}" in runs["b3"], runs["b3"]
    assert "no transcript for session" not in out.stderr, (
        out.stderr
    )  # a new session has none, by design
    # the transcript sits under a project folder the pane does not start in (the session moved): resume, never reuse the id
    _transcript(home, tmp_path / "somewhere" / "else", B2)
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    runs = _runs(out.stdout)
    assert (
        f"claude -n b2 --permission-mode bypassPermissions --resume {B2} --settings" in runs["b2"]
    ), runs["b2"]
    assert f"--session-id {B3}" in runs["b3"], runs["b3"]  # the other builder is unaffected
    # the builder's own re-bind is the LAST row (no `spawned`, a pid): still spawner-bound (T10 F1 — the spawned row
    # binds it, the last row still names b3), so the transcript alone decides: none yet → --session-id, one → resume
    rows = [json.loads(ln) for ln in store.read_text(encoding="utf-8").splitlines()]
    rebound = _store(tmp_path, [*rows, _bind(B3, "b3", scope, NOW + 5)], "rebound.jsonl")
    h2 = _home(tmp_path / "h2")
    out = _run("--print", str(repo), home=h2, AGENT_IDENTITY_FILE=str(rebound))
    runs = _runs(out.stdout)
    assert (
        f"--session-id {B2}" in runs["b2"]
        and f"claude -n b3 --permission-mode bypassPermissions --session-id {B3}" in runs["b3"]
    ), out.stdout
    _transcript(h2, _wt(repo, "b3"), B3)
    runs = _runs(_run("--print", str(repo), home=h2, AGENT_IDENTITY_FILE=str(rebound)).stdout)
    assert f"claude -n b3 --permission-mode bypassPermissions --resume {B3}" in runs["b3"], runs[
        "b3"
    ]
    # a binding with no `spawned` flag (every ordinary builder) never takes --session-id, transcript or not
    plain_repo, plain_store, _ = _spawn_repo(tmp_path / "plain", spawned=False)
    out = _run(
        "--print",
        str(plain_repo),
        home=_home(tmp_path / "plain"),
        AGENT_IDENTITY_FILE=str(plain_store),
    )
    assert (
        "--session-id" not in out.stdout
        and f"claude -n b2 --permission-mode bypassPermissions --resume {B2}" in out.stdout
    ), out.stdout


def test_pane_cmd_prints_one_command_for_a_resolved_new_builder(tmp_path: Path) -> None:
    """D1: `--pane-cmd <repo> <name> <sid> --new` prints exactly the one command the grid would run — `--session-id`, the
    first prompt, the suppression — and `--new` asserts the RESOLVER's own <new>: a sid with a transcript, a sid that is
    not spawner-bound, a pair the resolver never printed, or a name it dropped exit 2 with the reason and print nothing."""
    repo, store, _ = _spawn_repo(tmp_path)
    home = _home(tmp_path)
    env = {"AGENT_IDENTITY_FILE": str(store)}
    out = _run("--pane-cmd", str(repo), "b2", B2, "--new", home=home, **env)
    assert out.returncode == 0, out.stderr
    assert len(out.stdout.splitlines()) == 1, out.stdout
    inner = _inner("run b2 " + out.stdout.strip())
    assert (
        f"claude -n b2 --permission-mode bypassPermissions --session-id {B2} --settings '{SETTINGS}' '"
        in inner
    ), inner
    assert "CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1" in out.stdout and "CLAUDE_AGENT=b2" in out.stdout
    # without --new either form prints; here the same new session, so the same command
    again = _run("--pane-cmd", str(repo), "b2", B2, home=home, **env)
    assert again.returncode == 0 and again.stdout == out.stdout, again.stderr
    # --new on a sid with a transcript (anywhere): refused, with the transcript named as the reason
    _transcript(home, tmp_path / "elsewhere", B3)
    for args, reason in (
        (("b3", B3, "--new"), f"{B3} has a transcript — not a new session"),
        (("b2", DEV1, "--new"), f"b2 with session {DEV1} is not a builder the resolver gives"),
        (("b9", B2, "--new"), f"b9 with session {B2} is not a builder the resolver gives"),
        (("b1", B1, "--new"), "is not a builder the resolver gives"),  # b1 has no worktree: dropped
    ):
        bad = _run("--pane-cmd", str(repo), *args, home=home, **env)
        assert bad.returncode == 2 and bad.stdout == "", (args, bad.stdout, bad.stderr)
        assert reason in bad.stderr, (args, bad.stderr)
    # a builder that is not spawner-bound: --new is refused, the plain form still prints its resume command
    prepo, pstore, _ = _spawn_repo(tmp_path / "plain", spawned=False)
    penv = {"AGENT_IDENTITY_FILE": str(pstore)}
    phome = _home(tmp_path / "plain")
    bad = _run("--pane-cmd", str(prepo), "b2", B2, "--new", home=phome, **penv)
    assert bad.returncode == 2 and bad.stdout == "", bad.stdout
    assert f"{B2} is not a spawner-bound session" in bad.stderr, bad.stderr
    ok = _run("--pane-cmd", str(prepo), "b2", B2, home=phome, **penv)
    assert (
        ok.returncode == 0
        and f"claude -n b2 --permission-mode bypassPermissions --resume {B2}"
        in _inner("run b2 " + ok.stdout.strip())
    )
    # a resolver refusal refuses with its own message and code
    nothing = _run("--pane-cmd", str(tmp_path / "gone"), "b2", B2, home=home, **env)
    assert nothing.returncode == 2 and "is not a directory" in nothing.stderr, nothing.stderr
    for bad_argv in (("b2",), ("b2", B2, "--new", "--bogus"), ("B2", B2), ("b2", "not-a-uuid")):
        r = _run("--pane-cmd", str(repo), *bad_argv, home=home, **env)
        assert r.returncode == 2 and r.stdout == "", (bad_argv, r.stdout, r.stderr)


def test_the_first_prompt_reaches_claude_byte_for_byte(tmp_path: Path) -> None:
    """B7: the first prompt is passed through `squote`, never placed inside the inner double quotes, so its backtick,
    double quotes and `$` reach claude exactly as written — in a capped pane (nested scope quotes) and an uncapped one.
    The command is EXECUTED by /bin/sh against a fake claude printing its argv."""
    repo, store, _ = _spawn_repo(tmp_path)
    home = _home(tmp_path)
    _fake_claude(home)
    env = {"AGENT_IDENTITY_FILE": str(store)}
    for label in ("capped", "uncapped"):
        if label == "uncapped":
            (home / "manager-down").write_text("", encoding="utf-8")
        out = _run(
            "--pane-cmd", str(repo), "b2", B2, "--new", home=home, FABRIK_AGENTS_UNCAPPED="1", **env
        )
        assert out.returncode == 0, (label, out.stderr)
        args = _argv(home, out.stdout.strip())
        assert (
            args[:7]
            == [
                "-n",
                "b2",
                "--permission-mode",
                "bypassPermissions",
                "--session-id",
                B2,
                "--settings",
            ]
            and args[7] == SETTINGS
        ), (
            label,
            args,
        )
        assert len(args) == 9, (label, args)
        prompt = args[8]
        # the merge-owner default sentence carries backticks, the quoted rule carries double quotes, the name carries a `$`
        assert "`decisions.py --merge-owner`" in prompt, (label, prompt)
        assert (
            '"Every question goes to your coordinator by SendMessage - never to the operator."'
            in prompt
        ), prompt
        assert "($CLAUDE_AGENT)" in prompt, (
            label,
            prompt,
        )  # literal: not expanded by the pane's shell
        for part in (
            f'selfwatch_arm.sh" {B2} in the background',
            'whoami_agent.py" --as b2 --force',
            "python3 scripts/work.py next",
            "docs/reference/agents/builder.md",
        ):
            assert part in prompt, (label, part, prompt)
        assert "\n" not in prompt and "Your item is" not in prompt, (label, prompt)


def test_the_first_prompt_names_this_builders_coordinator_and_item_only(tmp_path: Path) -> None:
    """PO1/PO2: `--coordinator` and `--item` fill the first prompt's two sentences; a `--print` start reads the same from
    FABRIK_SPAWN_NAME/_COORDINATOR/_ITEM and applies them ONLY to the builder named; a malformed name or id exits 2."""
    repo, store, _ = _spawn_repo(tmp_path)
    home = _home(tmp_path)
    _fake_claude(home)
    env = {"AGENT_IDENTITY_FILE": str(store)}
    out = _run(
        "--pane-cmd",
        str(repo),
        "b2",
        B2,
        "--new",
        "--coordinator",
        "coord-a",
        "--item",
        "W-1a2b3c4d",
        home=home,
        **env,
    )
    assert out.returncode == 0, out.stderr
    prompt = _argv(home, out.stdout.strip())[8]
    assert "Your coordinator is coord-a." in prompt and "Your item is W-1a2b3c4d." in prompt, prompt
    assert "merge-owner" not in prompt, prompt
    # the resolver path: only the builder FABRIK_SPAWN_NAME names gets the two sentences
    pr = _run(
        "--print",
        str(repo),
        home=home,
        FABRIK_SPAWN_NAME="b2",
        FABRIK_SPAWN_COORDINATOR="coord-a",
        FABRIK_SPAWN_ITEM="W-1a2b3c4d",
        **env,
    )
    assert pr.returncode == 0, pr.stderr
    runs = {ln.split()[1]: ln for ln in pr.stdout.splitlines() if ln.startswith("run ")}
    b2, b3 = (
        _argv(home, runs["b2"].split(" ", 2)[2])[8],
        _argv(home, runs["b3"].split(" ", 2)[2])[8],
    )
    assert "Your coordinator is coord-a." in b2 and "Your item is W-1a2b3c4d." in b2, b2
    assert "coord-a" not in b3 and "Your item is" not in b3 and "merge-owner" in b3, b3
    # malformed: a name with a space, an upper-case name, an item that is no W- id, a flag with no value; same for the env
    for argv in (
        ("--coordinator", "x y"),
        ("--coordinator", "Coord"),
        ("--coordinator", "a;b"),
        ("--item", "W-1a2b3c4"),
        ("--item", "w-1a2b3c4d"),
        ("--item", "W-1A2B3C4D"),
        ("--coordinator",),
        ("--coordinator", ""),  # F5: an empty value given to the flag is malformed, not "unset"
        ("--item", ""),
    ):
        bad = _run("--pane-cmd", str(repo), "b2", B2, "--new", *argv, home=home, **env)
        assert bad.returncode == 2 and bad.stdout == "", (argv, bad.stdout, bad.stderr)
    # F6: a malformed value refuses the pane of the NEW builder FABRIK_SPAWN_NAME names...
    for var, value in (("FABRIK_SPAWN_COORDINATOR", "x y"), ("FABRIK_SPAWN_ITEM", "nope")):
        bad = _run("--print", str(repo), home=home, FABRIK_SPAWN_NAME="b2", **{var: value}, **env)
        assert bad.returncode == 2 and var in bad.stderr, (var, bad.stdout, bad.stderr)
    # ...and never a grid with no such builder: a stale variable (a name no builder has, a resumed-only grid) stops nothing
    for var, value in (
        ("FABRIK_SPAWN_COORDINATOR", "x y"),
        ("FABRIK_SPAWN_ITEM", "nope"),
        ("FABRIK_SPAWN_NAME", "B 2"),
    ):
        stale = _run("--print", str(repo), home=home, **{var: value}, **env)
        assert stale.returncode == 0 and "pane b2 " in stale.stdout, (var, stale.stderr)
    plain, pstore, _ = _spawn_repo(tmp_path / "resumed", spawned=False)
    ok = _run(
        "--print",
        str(plain),
        home=_home(tmp_path / "resumed"),
        FABRIK_SPAWN_NAME="b2",
        FABRIK_SPAWN_COORDINATOR="x y",
        AGENT_IDENTITY_FILE=str(pstore),
    )
    assert ok.returncode == 0 and "pane b2 " in ok.stdout, (
        ok.stderr
    )  # b2 resumes: no first prompt, nothing to validate


def test_an_empty_repo_exits_3_and_an_unreadable_store_exits_2(tmp_path: Path) -> None:
    """D4/B5: exit 3 is "nothing to launch" — a registry naming only a coordinator, or bindings with no builder worktree
    — and never a refusal: a malformed registry row, an unreadable ledger, and an identity store that exists but cannot
    be read in a repo with no registry (reading no builders would look like an empty repo) all stay 2."""
    home = _home(tmp_path)
    only_coord = _repo(
        tmp_path / "c",
        {COORD: "fabrik-lib-coordinator", "1a1a1a1a-1a1a-4a1a-8a1a-1a1a1a1a1a1a": "coordinator"},
    )
    assert _run("--print", str(only_coord), home=home).returncode == 3
    repo, store = _bound_repo(tmp_path / "nowt", worktrees=())
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 3 and "has no builder with its own worktree" in out.stderr, out.stderr
    # a merge owner covering every bound worktree leaves no builder either: 3
    owned, ostore = _bound_repo(tmp_path / "owned", worktrees=("b2",))
    _ledger(owned, "b2")
    assert _run("--print", str(owned), home=home, AGENT_IDENTITY_FILE=str(ostore)).returncode == 3
    # a registry-less repo: the store is a directory / unreadable
    bare, _ = _bound_repo(tmp_path / "bare")
    directory = tmp_path / "store-dir"
    directory.mkdir()
    out = _run("--print", str(bare), home=home, AGENT_IDENTITY_FILE=str(directory))
    assert out.returncode == 2 and "refusing rather than reading no builders" in out.stderr, (
        out.stderr
    )
    # (the mode-0 leg is its own test, skipped for root, which reads anything)
    # the same broken store in a repo WITH a registry still falls back to the registry (rc 0), as before
    reg = _repo(tmp_path / "reg", {DEV1: "dev1"})
    out = _run(
        "--print",
        str(reg),
        home=_home(tmp_path / "reg", transcripts=((reg, DEV1),)),
        AGENT_IDENTITY_FILE=str(directory),
    )
    assert out.returncode == 0 and _panes(out.stdout), out.stderr


def test_a_grid_whose_worktrees_all_vanish_before_launch_exits_2(tmp_path: Path) -> None:
    """Folded residue: every resolved worktree removed between the resolve and the launch leaves no session to select or
    attach — it says so and exits 2, never an `attach` to nothing. (The fake tmux's has-session removes the worktrees'
    `.git` files, the one call that runs between the resolver and the first `dir_of`.)"""
    repo = _repo(tmp_path, {DEV1: "dev1", DEV2: "dev2"})
    home = _tmux_home(tmp_path, repo, has=False, owner=None)
    gits = [_wt(repo, n) / ".git" for n in ("dev1", "dev2")]
    tmux = home / ".local" / "bin" / "tmux"
    needle = 'has-session) [ -f "$HOME/tmux-has" ] ;;'
    assert needle in FAKE_TMUX
    tmux.write_text(
        FAKE_TMUX.replace(
            needle,
            "has-session) rm -f "
            + " ".join(f"'{g}'" for g in gits)
            + '; [ -f "$HOME/tmux-has" ] ;;',
        ),
        encoding="utf-8",
    )
    out = _run(str(repo), home=home, tty=True)
    assert out.returncode == 2, (out.stdout, out.stderr)
    assert (
        "every builder's worktree went away between resolve and launch — nothing launched"
        in out.stderr
    ), out.stderr
    log = _log(home)
    assert not any(
        ln.startswith(("new-session", "select-pane", "attach", "switch-client")) for ln in log
    ), log


def test_a_claude_started_by_name_in_the_panes_folder_is_running(tmp_path: Path) -> None:
    """D9 (B4): a spawned pane's claude carries `-n <name>` and no `--resume`, so the process is matched by name AND cwd:
    `-n infra-2` in infra-2's worktree (or below it) reads running; `-n infra` elsewhere does not read as infra; the name
    `infra` never matches `-n infra-2` (grep -w would: `-` is a boundary); the same name with its cwd elsewhere is not it."""
    repo = _repo(tmp_path, {DEV1: "infra", DEV2: "infra-2"})
    ps = "4001 claude -n infra\n4002 claude -n infra-2 --settings x\n4003 /x/claude -n infra-3"
    home = _home(tmp_path, ps_lines=ps, transcripts=((repo, DEV1), (repo, DEV2)))
    proc = home / "proc"
    for pid, cwd in (
        ("4001", tmp_path / "elsewhere"),
        ("4002", _wt(repo, "infra-2") / "sub"),
        ("4003", _wt(repo, "infra-2")),
    ):
        (proc / pid).mkdir()
        (proc / pid / "cwd").symlink_to(cwd)
    out = _run("--print", str(repo), home=home)
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [
        f"pane infra {DEV1} {_wt(repo, 'infra')} ok",
        f"pane infra-2 {DEV2} {_wt(repo, 'infra-2')} running",
    ], out.stdout
    # infra-2's process moving out of its folder, and a process with no readable cwd, are not a running infra-2
    (proc / "4002" / "cwd").unlink()
    (proc / "4002" / "cwd").symlink_to(tmp_path / "elsewhere")
    (proc / "4003" / "cwd").unlink()
    out = _run("--print", str(repo), home=home)
    assert [p.rsplit(" ", 1)[1] for p in _panes(out.stdout)] == ["ok", "ok"], out.stdout
    # a folder that merely SHARES the prefix is not "below" it
    (proc / "4002" / "cwd").unlink()
    (proc / "4002" / "cwd").symlink_to(Path(str(_wt(repo, "infra-2")) + "-x"))
    out = _run("--print", str(repo), home=home)
    assert [p.rsplit(" ", 1)[1] for p in _panes(out.stdout)] == ["ok", "ok"], out.stdout


# --- W-b9ad80ae T02 review pass 1: the graders for F1-F9 and T-C1..T-C7 -----------------------------------------------


def test_a_live_claude_on_the_session_id_reads_running_whatever_its_flags_and_cwd(
    tmp_path: Path,
) -> None:
    """F1: the sid is unique, so ANY live claude carrying it — `--resume <sid>`, `--resume=<sid>`, `-r <sid>`,
    `--session-id <sid>`, `--session-id=<sid>` — makes the pane `running`, with no name or cwd condition; `--name <name>`
    in the folder counts like `-n`; a flag that merely ENDS in `-r`/`--resume` never matches, nor does a sid prefix."""
    repo = _repo(
        tmp_path, {DEV1: "dev1", DEV2: "dev2", SENT: "sentinel", NEW1: "four", NEW2: "five"}
    )
    cases = {
        "dev1": f"claude --session-id {DEV1}",
        "dev2": f"claude --session-id={DEV2} --name x",
        "sentinel": f"claude -n sentinel --foo-r {SENT}",  # a look-alike flag: not a match
        "four": f"claude --foo--resume {NEW1}",  # a look-alike flag: not a match
        "five": f"claude --session-id {NEW2}0",  # a sid prefix: not a match
    }
    ps = "\n".join(cases.values())
    home = _home(
        tmp_path, ps_lines=ps, transcripts=tuple((repo, s) for s in (DEV1, DEV2, SENT, NEW1, NEW2))
    )
    out = _run("--print", str(repo), home=home)
    got = {p.split()[1]: p.rsplit(" ", 1)[1] for p in _panes(out.stdout)}
    assert got == {
        "dev1": "running",
        "dev2": "running",
        "sentinel": "ok",
        "four": "ok",
        "five": "ok",
    }, out.stdout
    # `--name <name>` in the pane's folder is the named-process rule too
    solo = _repo(tmp_path / "solo", {DEV1: "dev1"})
    home = _home(tmp_path / "solo", ps_lines="4001 claude --name dev1", transcripts=((solo, DEV1),))
    (home / "proc" / "4001").mkdir()
    (home / "proc" / "4001" / "cwd").symlink_to(_wt(solo, "dev1"))
    assert _panes(_run("--print", str(solo), home=home).stdout)[0].endswith(" running")


def test_pane_cmd_applies_the_grids_cap_rules(tmp_path: Path) -> None:
    """F4: `--pane-cmd` with no reachable user manager refuses (exit 2, nothing printed) unless FABRIK_AGENTS_UNCAPPED=1,
    exactly as the grid does; with a manager it asserts the slice ceiling before printing (the fake systemctl logs it)."""
    repo, store, _ = _spawn_repo(tmp_path)
    home = _home(tmp_path)
    env = {"AGENT_IDENTITY_FILE": str(store)}
    ok = _run("--pane-cmd", str(repo), "b2", B2, "--new", home=home, **env)
    assert ok.returncode == 0, ok.stderr
    assert "set-property --runtime fabrik-agents.slice" in (home / "systemctl.log").read_text(
        encoding="utf-8"
    )
    (home / "manager-down").write_text("", encoding="utf-8")
    refused = _run("--pane-cmd", str(repo), "b2", B2, "--new", home=home, **env)
    assert refused.returncode == 2 and refused.stdout == "", (refused.stdout, refused.stderr)
    assert "no memory or task bound" in refused.stderr, refused.stderr
    allowed = _run(
        "--pane-cmd", str(repo), "b2", B2, "--new", home=home, FABRIK_AGENTS_UNCAPPED="1", **env
    )
    assert allowed.returncode == 0 and allowed.stdout.startswith("echo '[UNCAPPED"), allowed.stderr
    # a manager that answers but refuses the ceiling refuses the command too
    (home / "manager-down").unlink()
    (home / "slice-refused").write_text("", encoding="utf-8")
    bad = _run("--pane-cmd", str(repo), "b2", B2, "--new", home=home, **env)
    assert bad.returncode == 2 and bad.stdout == "", (bad.stdout, bad.stderr)


def test_a_forged_agent_line_in_a_store_row_launches_nothing(tmp_path: Path) -> None:
    """F7: a store row whose session_id carries a newline would print a forged `agent …` line that reaches a pane's shell
    string. The resolver emits `known` only for a lowercase UUID, and no forged builder appears in the grid."""
    repo, scope = _git_repo(tmp_path, {DEV1: "dev1"})
    forged = f"{NEW1}\nagent evil {NEW2} dev1 1"
    store = _store(
        tmp_path,
        [_bind(DEV1, "dev1", scope, NOW), {**_bind(NEW1, "zzz", scope, NOW), "session_id": forged}],
    )
    home = _home(tmp_path, transcripts=((repo, DEV1),))
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert [p.split()[1] for p in _panes(out.stdout)] == ["dev1"], out.stdout
    assert "evil" not in out.stdout and NEW2 not in out.stdout, out.stdout


def test_a_new_sessions_hint_and_running_message_say_session_id(tmp_path: Path) -> None:
    """F8: a session with no transcript cannot be resumed, so the kept-shell hint (and the "already running" message)
    of a new=1 pane name `--session-id <sid>`; a resumed pane still says `--resume <sid>`."""
    repo, store, _ = _spawn_repo(tmp_path)
    home = _home(tmp_path)
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    run = next(ln for ln in out.stdout.splitlines() if ln.startswith("run b2 "))
    assert (
        f"[b2 exited — run: claude -n b2 --permission-mode bypassPermissions --session-id {B2} (after a /clear"
        in _hint(run, tmp_path)
    )
    assert f"claude -n b2 --permission-mode bypassPermissions --resume {B2} (after" not in _hint(
        run, tmp_path
    )
    # running (a live claude on the sid): the message names the same flag
    home2 = _home(tmp_path / "r", ps_lines=f"claude --session-id {B2}")
    out = _run("--print", str(repo), home=home2, AGENT_IDENTITY_FILE=str(store))
    run = next(ln for ln in out.stdout.splitlines() if ln.startswith("run b2 "))
    said = subprocess.run(  # the message is decided when printed (T10 F14): run it
        ["sh", "-c", _inner(run).split("; exec ")[0]], capture_output=True, text=True, timeout=30
    ).stdout
    assert (
        f"close it there, then run: claude -n b2 --permission-mode bypassPermissions --session-id {B2}]"
        in said
    ), (said, run)
    plain, pstore, _ = _spawn_repo(tmp_path / "plain", spawned=False)
    out = _run(
        "--print", str(plain), home=_home(tmp_path / "plain"), AGENT_IDENTITY_FILE=str(pstore)
    )
    run = next(ln for ln in out.stdout.splitlines() if ln.startswith("run b2 "))
    assert f"claude -n b2 --permission-mode bypassPermissions --resume {B2} (after" in _hint(
        run, tmp_path
    )


def test_a_hub_path_with_a_space_reads_as_one_path_in_the_prompts(tmp_path: Path) -> None:
    """F9/F2: the launcher's own checkout ($HUB) is double-quoted inside both prompts (the wake prompt has no /opt/fabrik
    literal), so a checkout path with a space still reads as one path. The launcher is copied beside the scripts it needs
    into a tree whose name carries a space."""
    hub = tmp_path / "my hub"
    (hub / "scripts" / "sysadmin").mkdir(parents=True)
    shutil.copy(
        UP, hub / "scripts" / "sysadmin" / "agents_up.sh"
    )  # the script under test, not a sibling copy
    shutil.copy(UP.parent.parent / "decisions.py", hub / "scripts" / "decisions.py")
    repo, store, _ = _spawn_repo(tmp_path)
    home = _home(tmp_path)
    _fake_claude(home)
    env = {"AGENT_IDENTITY_FILE": str(store)}
    out = subprocess.run(
        ["bash", str(hub / "scripts" / "sysadmin" / "agents_up.sh"), "--print", str(repo)],
        capture_output=True,
        text=True,
        timeout=30,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(home),
            "FABRIK_PROC_ROOT": str(home / "proc"),
            **env,
        },
    )
    assert out.returncode == 0, out.stderr
    runs = {ln.split()[1]: ln for ln in out.stdout.splitlines() if ln.startswith("run ")}
    first = _argv(home, runs["b2"].split(" ", 2)[2])[8]
    assert f'bash "{hub.resolve()}/scripts/sysadmin/selfwatch_arm.sh" {B2}' in first, first
    assert f'python3 "{hub.resolve()}/scripts/whoami_agent.py" --as b2' in first, first
    # a resumed builder's wake prompt: the same quoting, and the hub literal gone
    plain, pstore, _ = _spawn_repo(tmp_path / "plain", spawned=False)
    out = subprocess.run(
        ["bash", str(hub / "scripts" / "sysadmin" / "agents_up.sh"), "--print", str(plain)],
        capture_output=True,
        text=True,
        timeout=30,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(home),
            "FABRIK_PROC_ROOT": str(home / "proc"),
            "AGENT_IDENTITY_FILE": str(pstore),
        },
    )
    wake_run = next(ln for ln in out.stdout.splitlines() if ln.startswith("run b2 "))
    wake = _argv(home, wake_run.split(" ", 2)[2])[8]
    assert f'bash "{hub.resolve()}/scripts/sysadmin/selfwatch_arm.sh" {B2}' in wake, wake
    assert "/opt/fabrik" not in wake, wake


def test_pane_cmd_prints_the_resolvers_new_not_a_hard_coded_one(tmp_path: Path) -> None:
    """T-C1: for a builder the resolver says is NOT new, the printed command part (before the kept-shell hint, which
    legitimately says `--resume`) resumes and never carries `--session-id`; mutant `cmd_of … 1` fails this."""
    prepo, pstore, _ = _spawn_repo(tmp_path / "plain", spawned=False)
    out = _run(
        "--pane-cmd",
        str(prepo),
        "b2",
        B2,
        home=_home(tmp_path / "plain"),
        AGENT_IDENTITY_FILE=str(pstore),
    )
    assert out.returncode == 0, out.stderr
    command = _inner("run b2 " + out.stdout.strip()).split("; rc=")[0]
    assert f"--resume {B2} --settings" in command and "--session-id" not in command, command


def test_a_new_session_launch_does_not_warn_about_its_missing_transcript(tmp_path: Path) -> None:
    """T-C2: the launch loop's "no transcript … the pane will try anyway" warning is skipped for a new=1 builder (a new
    session has none, by design) and still said for a resumed builder."""
    repo, store, _ = _spawn_repo(tmp_path)
    home = _tmux_home(tmp_path, repo, has=False, owner=None)
    out = _run(str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert "no transcript for session" not in out.stderr, out.stderr
    plain, pstore, _ = _spawn_repo(tmp_path / "plain", spawned=False)
    phome = _tmux_home(tmp_path / "plain", plain, has=False, owner=None)
    out = _run(str(plain), home=phome, AGENT_IDENTITY_FILE=str(pstore))
    assert f"b2: no transcript for session {B2}" in out.stderr, out.stderr


def test_pane_cmd_for_a_worktree_that_vanished_prints_nothing(tmp_path: Path) -> None:
    """T-C3: `--pane-cmd` where `dir_of` prints nothing (the worktree's `.git` removed after the resolve) exits 2 with
    empty stdout. The fake `ps`... runs after the resolver, so it removes the `.git` file."""
    repo, store, _ = _spawn_repo(tmp_path)
    home = _home(tmp_path)
    git = _wt(repo, "b2") / ".git"
    ps = home / ".local" / "bin" / "ps"
    ps.write_text(f"#!/bin/sh\nrm -f '{git}'\n", encoding="utf-8")
    out = _run(
        "--pane-cmd", str(repo), "b2", B2, "--new", home=home, AGENT_IDENTITY_FILE=str(store)
    )
    assert out.returncode == 2 and out.stdout == "", (out.stdout, out.stderr)
    assert "no longer a linked git worktree" in out.stderr, out.stderr


def test_a_process_named_infra_2_inside_infras_folder_is_not_infra(tmp_path: Path) -> None:
    """T-C4: the name boundary is graded by itself (the cwd check alone cannot mask it): a `-n infra-2` process whose cwd
    is inside infra's folder leaves `infra` not running."""
    repo = _repo(tmp_path, {DEV1: "infra", DEV2: "infra-2"})
    home = _home(
        tmp_path, ps_lines="4002 claude -n infra-2", transcripts=((repo, DEV1), (repo, DEV2))
    )
    (home / "proc" / "4002").mkdir()
    (home / "proc" / "4002" / "cwd").symlink_to(_wt(repo, "infra") / "sub")
    out = _run("--print", str(repo), home=home)
    assert [p.rsplit(" ", 1)[1] for p in _panes(out.stdout)] == ["ok", "ok"], out.stdout


def test_a_sid_whose_last_row_names_another_builder_resumes(tmp_path: Path) -> None:
    """T-C5: `fresh()` requires the sid's LAST in-scope row to name THIS builder: b2's sid last bound (spawned) to b3
    in this scope is not b2's new session, so b2 resumes."""
    # the registry gives b2 the sid; the store says its last row in this scope names b3, spawned
    repo, scope = _git_repo(tmp_path, {B2: "b2"})
    store = _store(
        tmp_path, [{**_bind(B2, "b3", scope, NOW), "pid": None, "force": False, "spawned": True}]
    )
    out = _run("--print", str(repo), home=_home(tmp_path), AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert (
        "--session-id" not in out.stdout
        and f"claude -n b2 --permission-mode bypassPermissions --resume {B2}" in out.stdout
    ), out.stdout


def _refreshed(tmp: Path, store: Path, scope: str, sid: str, name: str) -> Path:
    """The store plus the row master's `whoami_agent.refresh()` appends at a SessionStart: same sid, name and scope,
    a pid, `refresh: true`, no `spawned`."""
    rows = [json.loads(ln) for ln in store.read_text(encoding="utf-8").splitlines()]
    row = {**_bind(sid, name, scope, NOW + 5), "force": False, "unlocked": False, "refresh": True}
    return _store(tmp, [*rows, row], "refreshed.jsonl")


def test_t10_f1_a_refresh_row_after_the_spawned_row_still_launches_session_id(
    tmp_path: Path,
) -> None:
    """T10 F1: a claude that died after SessionStart (refresh row written) and before its first transcript write is
    relaunched `--session-id`, never `--resume` of a session with no transcript; once the transcript exists, resume."""
    repo, store, scope = _spawn_repo(tmp_path)
    store = _refreshed(tmp_path, store, scope, B2, "b2")
    home = _home(tmp_path)
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    runs = _runs(out.stdout)
    assert (
        f"claude -n b2 --permission-mode bypassPermissions --session-id {B2} --settings"
        in runs["b2"]
    ), runs["b2"]
    _transcript(home, tmp_path / "anywhere", B2)
    runs = _runs(_run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store)).stdout)
    assert (
        f"claude -n b2 --permission-mode bypassPermissions --resume {B2} --settings" in runs["b2"]
    ), runs["b2"]


@pytest.mark.parametrize("bad", [["x"], {"n": 1}, None, 7])
def test_t10_f18_a_spawned_row_with_a_non_string_name_never_breaks_the_resolver(
    tmp_path: Path, bad: object
) -> None:
    """T10 F18: a hand-edited or corrupted `spawned: true` row whose name is not a string is skipped, never a crash that
    exits 2 for every builder; b2's own spawned row still launches `--session-id`."""
    repo, store, scope = _spawn_repo(tmp_path)
    rows = [json.loads(ln) for ln in store.read_text(encoding="utf-8").splitlines()]
    odd = {"session_id": NEW1, "name": bad, "toplevel": scope, "spawned": True}
    store = _store(tmp_path, [*rows, odd], "odd.jsonl")
    out = _run("--print", str(repo), home=_home(tmp_path), AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert (
        f"claude -n b2 --permission-mode bypassPermissions --session-id {B2} --settings"
        in _runs(out.stdout)["b2"]
    ), out.stdout


def test_t10_f14_a_spawned_panes_hint_picks_its_flag_when_printed(tmp_path: Path) -> None:
    """T10 F14: the kept-shell hint and the "already running" message of a spawned pane name `--session-id` while no
    project folder holds the session's transcript and `--resume` once one does — decided when PRINTED, not at launch."""
    repo, store, _ = _spawn_repo(tmp_path)
    home = _home(tmp_path)
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    run = next(ln for ln in out.stdout.splitlines() if ln.startswith("run b2 "))
    assert (
        f"[b2 exited — run: claude -n b2 --permission-mode bypassPermissions --session-id {B2} (after a /clear"
        in _hint(run, tmp_path)
    )
    _transcript(
        home, tmp_path / "where" / "it ran", B2
    )  # the same launched pane: its claude wrote a transcript
    assert (
        f"[b2 exited — run: claude -n b2 --permission-mode bypassPermissions --resume {B2} (after a /clear"
        in _hint(run, tmp_path)
    )
    home2 = _home(tmp_path / "r", ps_lines=f"claude --session-id {B2}")
    out = _run("--print", str(repo), home=home2, AGENT_IDENTITY_FILE=str(store))
    run = next(ln for ln in out.stdout.splitlines() if ln.startswith("run b2 "))
    said = [
        subprocess.run(
            [shell, "-c", _inner(run).split("; exec ")[0]],
            capture_output=True,
            text=True,
            timeout=30,
            env={"PATH": "/usr/bin:/bin", "LANG": "C"},
        ).stdout
        for shell in ("bash", "sh")
    ]
    assert (
        said[0] == said[1]
        and f"then run: claude -n b2 --permission-mode bypassPermissions --session-id {B2}]"
        in said[0]
    ), said
    _transcript(home2, tmp_path / "elsewhere", B2)
    again = subprocess.run(
        ["sh", "-c", _inner(run).split("; exec ")[0]], capture_output=True, text=True, timeout=30
    ).stdout
    assert f"then run: claude -n b2 --permission-mode bypassPermissions --resume {B2}]" in again, (
        again
    )


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a mode-0 file")
def test_a_mode_zero_store_in_a_registry_less_repo_exits_2(tmp_path: Path) -> None:
    """T-C6: the mode-0 leg of the unreadable-store check, skipped for root (which reads anything)."""
    bare, _ = _bound_repo(tmp_path / "bare")
    locked = _store(tmp_path, [], "locked2.jsonl")
    os.chmod(locked, 0)
    try:
        out = _run("--print", str(bare), home=_home(tmp_path), AGENT_IDENTITY_FILE=str(locked))
    finally:
        os.chmod(locked, 0o644)
    assert out.returncode == 2 and "refusing rather than reading no builders" in out.stderr, (
        out.stderr
    )


def test_a_padded_pid_in_ps_output_still_reads_running(tmp_path: Path) -> None:
    """T-C7: real `ps -o pid=` right-aligns the pid (`  4002 claude …`); the launcher's `read -r pid args` tolerates the
    padding, which the unpadded fakes never graded."""
    repo = _repo(tmp_path, {DEV2: "infra-2"})
    home = _home(tmp_path, ps_lines=f"{4002:>7} claude -n infra-2", transcripts=((repo, DEV2),))
    (home / "proc" / "4002").mkdir()
    (home / "proc" / "4002" / "cwd").symlink_to(_wt(repo, "infra-2"))
    out = _run("--print", str(repo), home=home)
    assert _panes(out.stdout) == [f"pane infra-2 {DEV2} {_wt(repo, 'infra-2')} running"], out.stdout


# --- W-b9ad80ae T02 review pass 2: every refusal is decided before the first side effect or output line ---------------


def _mixed_repo(tmp: Path) -> tuple[Path, Path]:
    """b2 resumes (an ordinary binding), b3 is a NEW spawner-bound builder that sorts AFTER it."""
    repo, _, scope = _spawn_repo(tmp)
    rows = [
        _bind(B2, "b2", scope, NOW),
        {**_bind(B3, "b3", scope, NOW), "pid": None, "force": False, "spawned": True},
    ]
    return repo, _store(tmp, rows, "mixed.jsonl")


def test_a_malformed_spawn_variable_refuses_before_a_grid_is_started(tmp_path: Path) -> None:
    """N1: with FABRIK_SPAWN_NAME naming a new builder that sorts after a resumed one and a malformed ITEM or COORDINATOR,
    `--detach` makes no tmux call at all (a partial grid would be left "already up" and the new builder never launched),
    and `--print` prints no `session`/`pane`/`cap` line. A stale variable naming no new builder stops nothing."""
    repo, store = _mixed_repo(tmp_path)
    home = _tmux_home(tmp_path, repo, has=False, owner=None)
    for var, value in (("FABRIK_SPAWN_ITEM", "nope"), ("FABRIK_SPAWN_COORDINATOR", "x y")):
        env = {"FABRIK_SPAWN_NAME": "b3", var: value, "AGENT_IDENTITY_FILE": str(store)}
        out = _run("--detach", str(repo), home=home, **env)
        assert out.returncode == 2 and var in out.stderr, (var, out.stderr)
        log = home / "tmux.log"
        # the only tmux call allowed is the read-only has-session probe that decides new-grid vs attach: no session made
        assert not log.exists() or set(_log(home)) <= {"has-session -t =shop"}, (var, _log(home))
        assert not (home / "systemctl.log").exists() or "set-property" not in (
            home / "systemctl.log"
        ).read_text(encoding="utf-8"), var
        bad = _run("--print", str(repo), home=home, **env)
        assert bad.returncode == 2 and bad.stdout == "" and "pane " not in bad.stdout, (
            var,
            bad.stdout,
            bad.stderr,
        )
    # the name is b2 (resumed): nothing to validate, the grid starts
    ok = _run(
        "--detach",
        str(repo),
        home=home,
        FABRIK_SPAWN_NAME="b2",
        FABRIK_SPAWN_ITEM="nope",
        AGENT_IDENTITY_FILE=str(store),
    )
    assert ok.returncode == 0, ok.stderr


def test_a_refused_pane_cmd_never_writes_the_slice_property(tmp_path: Path) -> None:
    """O1: the found / --new / dir_of checks run BEFORE the cap rules, so a refused request leaves the user manager
    untouched; an accepted one asserts the ceiling (after the checks)."""
    repo, store, _ = _spawn_repo(tmp_path)
    home = _home(tmp_path)
    env = {"AGENT_IDENTITY_FILE": str(store)}
    for args in (("b9", B2, "--new"), ("b2", DEV1), ("b2", B2, "--new", "--item", "nope")):
        bad = _run("--pane-cmd", str(repo), *args, home=home, **env)
        assert bad.returncode == 2 and bad.stdout == "", (args, bad.stderr)
    log = home / "systemctl.log"
    assert not log.exists() or "set-property" not in log.read_text(encoding="utf-8"), log.read_text(
        encoding="utf-8"
    )
    assert _run("--pane-cmd", str(repo), "b2", B2, "--new", home=home, **env).returncode == 0
    assert "set-property" in log.read_text(encoding="utf-8")


def test_pane_cmd_is_its_own_mode(tmp_path: Path) -> None:
    """O2: `--pane-cmd` beside `--print` or `--detach` is a usage error (exit 2, nothing printed) — it never prints the
    whole grid, and `--detach` never lets it skip the uncapped refusal."""
    repo, store, _ = _spawn_repo(tmp_path)
    home = _home(tmp_path)
    for flag in ("--print", "--detach"):
        out = _run(
            flag,
            "--pane-cmd",
            str(repo),
            "b2",
            B2,
            "--new",
            home=home,
            AGENT_IDENTITY_FILE=str(store),
        )
        assert out.returncode == 2 and out.stdout == "", (flag, out.stdout)
        assert "its own mode" in out.stderr, (flag, out.stderr)


def test_a_stale_spawn_variable_never_stops_an_attach_to_an_up_grid(tmp_path: Path) -> None:
    """Pass 3: the FABRIK_SPAWN_* check runs only where a first prompt can be built. With the grid ALREADY UP (this
    repo's recorded root) an attach builds no pane and no prompt, so a malformed ITEM or COORDINATOR naming a new builder
    stops nothing — `--detach` attaches (rc 0), and no pane is made."""
    repo, store = _mixed_repo(tmp_path)
    home = _tmux_home(tmp_path, repo, has=True, owner=str(repo))
    for var, value in (("FABRIK_SPAWN_ITEM", "nope"), ("FABRIK_SPAWN_COORDINATOR", "x y")):
        out = _run(
            "--detach",
            str(repo),
            home=home,
            FABRIK_SPAWN_NAME="b3",
            AGENT_IDENTITY_FILE=str(store),
            **{var: value},
        )
        assert out.returncode == 0 and "grid is already up" in out.stderr, (var, out.stderr)
    assert not any(ln.startswith(("new-session", "split-window")) for ln in _log(home)), _log(home)


# --- W-b9ad80ae T03: windows of four, the grouped overflow sessions, --window <n> ---------------------------------------
# These run on a SCRATCH `tmux -L <unique>` server (never the default socket) and assert the server's STATE — windows,
# panes, sessions, groups — never a call log. XDG_RUNTIME_DIR=/nonexistent keeps every run off the real user manager;
# the fake systemctl/systemd-run on the launcher's PATH answer instead.

SIX = [f"{c * 8}-{c * 4}-4{c * 3}-8{c * 3}-{c * 12}" for c in "abcdef"]
NOBUS = {"XDG_RUNTIME_DIR": "/nonexistent"}


def _flag_of(pid: int) -> str:
    """The `@agents_up_building` value of a live builder: `<pid>:<start time>` (field 22 of /proc/<pid>/stat)."""
    stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    return f"{pid}:{stat.rsplit(') ', 1)[1].split()[19]}"


class _Scratch:
    """A scratch tmux server behind a wrapper on the launcher's PATH. `fail_splits` are the 1-based ordinals of the
    `split-window` calls the wrapper refuses (a real server cannot be made to run out of room on demand)."""

    def __init__(
        self,
        tmp_path: Path,
        request: pytest.FixtureRequest,
        builders: int,
        fail_splits: tuple[int, ...] = (),
        steal_focus: bool = False,
        garble_ids: bool = False,
    ) -> None:
        self.real = shutil.which("tmux") or ""
        assert self.real, "tmux is the launcher's own dependency"
        self.server = f"t03-{os.getpid()}-{abs(hash(str(tmp_path))) % 10**8}"
        self.repo = _repo(tmp_path, {SIX[i]: f"dev{i + 1}" for i in range(builders)})
        self.S = self.repo.name
        self.home = _home(tmp_path, transcripts=tuple((self.repo, SIX[i]) for i in range(builders)))
        wrapper = self.home / ".local" / "bin" / "tmux"
        real = f"{self.real} -L {self.server}"
        script = (
            "#!/bin/sh\n"
            # a switch-client needs a client a scratch server does not have: log the target, never run it
            'if [ "$1" = switch-client ]; then echo "$*" >> "$HOME/switch.log"; exit 0; fi\n'
            # lose-race: the FIRST has-session says "no grid" (a launch that decided to build, then lost the race)
            'if [ "$1" = has-session ] && [ -f "$HOME/lose-race" ] && [ ! -f "$HOME/lost-once" ]; then\n'
            '  : > "$HOME/lost-once"; exit 1\n'
            "fi\n"
            # concurrent: on the first has-session of <name>+2 a second --window run creates it, grouped with <name>
            'if [ "$1" = has-session ] && [ -f "$HOME/concurrent" ] && [ ! -f "$HOME/concurrent-done" ]; then\n'
            '  b=$(cat "$HOME/concurrent")\n'
            '  case "$*" in *"=$b+2") : > "$HOME/concurrent-done"\n'
            f'    {real} new-session -d -t "=$b" -s "$b+2"\n'
            f'    {real} display-message -p -t "=$b+2:" "#{{session_id}}" > "$HOME/concurrent-id" ;;\n'
            "  esac\n"
            "fi\n"
            'if [ "$1" = split-window ]; then\n'
            '  n=$(cat "$HOME/split-count" 2>/dev/null || echo 0); n=$((n+1)); echo $n > "$HOME/split-count"\n'
            f'  for f in {" ".join(map(str, fail_splits))}; do [ "$n" = "$f" ] && exit 1; done\n'
            "fi\n"
        )
        if steal_focus:  # every new-window selects itself in the base session, as a session left on the last window would be
            script += (
                'if [ "$1" = new-window ]; then\n'
                f'  out=$({real} "$@") || exit 1\n'
                '  echo "$out"\n'
                f'  {real} select-window -t "${{out%% *}}" >/dev/null\n'
                "  exit 0\n"
                "fi\n"
            )
        if garble_ids:  # tmux creates the session but the launcher is handed no ids: the build dies after new-session
            script += (
                'if [ "$1" = new-session ]; then\n'
                f'  {real} "$@" >/dev/null || exit 1\n'
                '  echo "garbage"\n'
                "  exit 0\n"
                "fi\n"
            )
        wrapper.write_text(script + f'exec {real} "$@"\n', encoding="utf-8")
        wrapper.chmod(0o755)
        claude = self.home / ".local" / "bin" / "claude"
        claude.write_text("#!/bin/sh\nsleep 120\n", encoding="utf-8")
        claude.chmod(0o755)
        request.addfinalizer(self.close)

    def close(self) -> None:
        killed = self.tmux("kill-server")
        # kill-server leaves the socket file behind; ours alone (named after this test's server) is removed, and only
        # once the server is really gone (a live server with no socket could never be reached again)
        sock = Path(os.environ.get("TMUX_TMPDIR", "/tmp")) / f"tmux-{os.getuid()}" / self.server
        if (
            killed.returncode == 0 or self.tmux("list-sessions").returncode != 0
        ):  # never while a server still answers
            sock.unlink(missing_ok=True)

    def tmux(self, *a: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.real, "-L", self.server, *a], capture_output=True, text=True, timeout=20
        )

    def up(self, *args: str, timeout: int = 30, **env: str) -> subprocess.CompletedProcess[str]:
        return _run(*args, str(self.repo), home=self.home, timeout=timeout, **{**NOBUS, **env})

    def lines(self, *a: str) -> list[str]:
        return self.tmux(*a).stdout.splitlines()

    def windows(self) -> list[str]:
        return self.lines(
            "list-windows", "-t", f"={self.S}", "-F", "#{window_name} #{window_panes}"
        )

    def sessions(self) -> list[str]:
        return sorted(self.lines("list-sessions", "-F", "#{session_name}"))

    def one(self, session: str, fmt: str) -> str:
        return self.tmux("display-message", "-p", "-t", f"={session}:", fmt).stdout.strip()

    def tags(self) -> list[str]:
        return sorted(
            self.lines("list-panes", "-s", "-t", f"={self.S}", "-F", "#{window_name} #{@agent}")
        )


def test_six_builders_fill_agents_with_four_and_agents_2_with_two_in_a_grouped_session(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    sc = _Scratch(tmp_path, request, 6)
    out = sc.up()
    assert out.returncode == 0, out.stderr
    assert sc.windows() == ["agents 4", "agents-2 2"], sc.windows()
    assert sc.sessions() == [sc.S, f"{sc.S}+2"], sc.sessions()
    group = sc.one(sc.S, "#{session_group}")
    assert group and sc.one(f"{sc.S}+2", "#{session_group}") == group
    assert (
        sc.one(f"{sc.S}+2", "#{window_name}") == "agents-2"
    )  # the overflow session opens on its own window
    assert sc.one(sc.S, "#{window_name}") == "agents"  # and tab 1's current window is `agents`
    assert sc.tags() == sorted(
        [f"agents dev{i}" for i in (1, 2, 3, 4)] + [f"agents-2 dev{i}" for i in (5, 6)]
    ), sc.tags()
    assert sc.one(sc.S, "#{@agents_up_building}") == "", (
        "the building flag is cleared once the grid is built"
    )
    assert sc.one(sc.S, "#{@agents_up_root}") == str(sc.repo)


def test_four_builders_or_fewer_make_one_window_and_no_overflow_session(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    for n in (1, 4):
        sc = _Scratch(tmp_path / f"n{n}", request, n)
        out = sc.up()
        assert out.returncode == 0, (n, out.stderr)
        assert sc.windows() == [f"agents {n}"], (n, sc.windows())
        assert sc.sessions() == [sc.S], (n, sc.sessions())


def test_a_failed_split_is_said_and_the_next_builder_takes_the_slot(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    sc = _Scratch(tmp_path, request, 6, fail_splits=(1,))  # dev2's split-window
    out = sc.up()
    assert out.returncode == 4, out.stderr  # a skipped pane is exit 4 (T04 residue 3)
    assert (
        "no room for dev2's pane (session " in out.stderr
        and ") — open it by hand: " in out.stderr
        and "claude -n dev2" in out.stderr
    ), out.stderr
    assert sc.windows() == ["agents 4", "agents-2 1"], sc.windows()
    assert sc.tags() == sorted([f"agents dev{i}" for i in (1, 3, 4, 5)] + ["agents-2 dev6"]), (
        sc.tags()
    )
    assert sc.sessions() == [sc.S, f"{sc.S}+2"], sc.sessions()


def test_a_relaunch_kills_stale_overflow_sessions_and_never_another_repos_base(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    sc = _Scratch(tmp_path, request, 6)
    for args in (
        ("new-session", "-d", "-s", sc.S, "sleep 300"),
        ("new-session", "-d", "-t", f"={sc.S}", "-s", f"{sc.S}+2"),
        ("new-session", "-d", "-t", f"={sc.S}", "-s", f"{sc.S}+3"),
        ("new-session", "-d", "-s", f"{sc.S}-2", "sleep 300"),  # another repo's base session
    ):
        assert sc.tmux(*args).returncode == 0, args
    old_plus2 = sc.tmux(
        "display-message", "-p", "-t", f"={sc.S}+2:", "#{session_id}"
    ).stdout.strip()
    other = sc.tmux("display-message", "-p", "-t", f"={sc.S}-2:", "#{session_id}").stdout.strip()
    assert (
        sc.tmux("kill-session", "-t", f"={sc.S}").returncode == 0
    )  # the old base dies; its members survive
    out = sc.up()
    assert out.returncode == 0, out.stderr
    assert sc.sessions() == sorted([sc.S, f"{sc.S}+2", f"{sc.S}-2"]), sc.sessions()  # +3 is gone
    new_plus2 = sc.tmux(
        "display-message", "-p", "-t", f"={sc.S}+2:", "#{session_id}"
    ).stdout.strip()
    assert (
        new_plus2 and new_plus2 != old_plus2
    )  # re-created in the new group, not the old one reused
    assert sc.one(f"{sc.S}+2", "#{window_name}") == "agents-2"
    assert (
        sc.tmux("display-message", "-p", "-t", f"={sc.S}-2:", "#{session_id}").stdout.strip()
        == other
    )


def test_a_window_name_is_matched_exactly_never_loosely(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    """B12: with only `agents-22` in the grid, `--window 2` finds no `agents-2` (tmux's own name target would pick
    `agents-22` by prefix) and so creates no `<S>+2`."""
    sc = _Scratch(tmp_path, request, 2)
    assert sc.tmux("new-session", "-d", "-s", sc.S, "-n", "agents-22", "sleep 300").returncode == 0
    assert sc.tmux("set-option", "-t", f"={sc.S}:", "@agents_up_root", str(sc.repo)).returncode == 0
    # the premise: tmux alone, asked for `agents-2`, answers with the OTHER window
    loose = sc.tmux("display-message", "-p", "-t", f"={sc.S}:agents-2", "#{window_name}")
    assert loose.stdout.strip() == "agents-22", loose
    out = sc.up("--window", "2")
    assert out.returncode == 0 and "has no window agents-2 now" in out.stderr, out.stderr
    assert sc.sessions() == [sc.S], sc.sessions()


def test_window_n_attaches_the_overflow_session_at_once_whatever_the_building_flag_says(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    sc = _Scratch(tmp_path, request, 6)
    assert sc.up().returncode == 0
    dead = subprocess.Popen(["true"])
    dead.wait()
    # F4: a dead PID, `0` (`kill -0 0` succeeds), a live PID with the wrong start time (a recycled PID) and a bare PID all
    # read "not building"; F15: the attach comes at once, never after the (large) wait budget
    for label, flag in (
        ("no flag", None),
        ("dead pid", f"{dead.pid}:1"),
        ("zero", "0"),
        ("zero pair", "0:1"),
        ("recycled pid", f"{os.getpid()}:1"),
        ("bare pid", str(os.getpid())),
    ):
        sc.tmux("kill-session", "-t", f"={sc.S}+2")
        if flag is not None:
            assert (
                sc.tmux("set-option", "-t", f"={sc.S}:", "@agents_up_building", flag).returncode
                == 0
            )
        began = time.monotonic()
        # the run's own timeout (60) sits well above the budget (30): a run that waits exits 2 and fails HERE, not by a timeout
        out = sc.up("--window", "2", timeout=60, FABRIK_AGENTS_WINDOW_WAIT_S="30")
        assert out.returncode == 0, (label, out.stderr)
        assert time.monotonic() - began < 10, label
        assert "not ready" not in out.stderr, (label, out.stderr)
        assert f"tmux attach -t ={sc.S}+2" in out.stderr, (
            label,
            out.stderr,
        )  # non-TTY: left detached, said so
        group = sc.one(sc.S, "#{session_group}")
        assert group and sc.one(f"{sc.S}+2", "#{session_group}") == group, label
        assert sc.one(f"{sc.S}+2", "#{window_name}") == "agents-2", label
    # a grid another folder's launcher owns is never attached
    assert (
        sc.tmux("set-option", "-t", f"={sc.S}:", "@agents_up_root", "/opt/elsewhere/x").returncode
        == 0
    )
    out = sc.up("--window", "2")
    assert out.returncode == 2 and "belongs to /opt/elsewhere/x" in out.stderr, out.stderr


def test_window_n_without_that_window_shows_the_current_one_and_creates_nothing(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    sc = _Scratch(tmp_path, request, 6)
    assert sc.up().returncode == 0
    out = sc.up("--window", "3")
    assert out.returncode == 0, out.stderr
    assert "has no window agents-3 now — showing its current window" in out.stderr, out.stderr
    assert f"tmux attach -t ={sc.S})" in out.stderr, out.stderr
    assert sc.sessions() == [sc.S, f"{sc.S}+2"], sc.sessions()  # no `<S>+3`


def test_window_n_waits_for_a_live_builder_then_gives_up_and_rejects_n_below_2(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    sc = _Scratch(tmp_path, request, 2)
    absent = sc.up("--window", "2", FABRIK_AGENTS_WINDOW_WAIT_S="2")
    assert (
        absent.returncode == 2 and f"the {sc.S} grid was not ready within 2 s" in absent.stderr
    ), absent.stderr
    assert sc.tmux("new-session", "-d", "-s", sc.S, "sleep 300").returncode == 0
    assert (
        sc.tmux(
            "set-option", "-t", f"={sc.S}:", "@agents_up_building", _flag_of(os.getpid())
        ).returncode
        == 0
    )
    building = sc.up("--window", "2", FABRIK_AGENTS_WINDOW_WAIT_S="2")
    assert building.returncode == 2 and "was not ready within 2 s" in building.stderr, (
        building.stderr
    )
    for bad in ("1", "0", "x", ""):
        out = sc.up("--window", bad)
        assert out.returncode == 2 and "usage" in out.stderr, (bad, out.stderr)
    assert _run("--window", home=sc.home, **NOBUS).returncode == 2
    mixed = sc.up("--window", "2", "--print")
    assert mixed.returncode == 2 and "its own mode" in mixed.stderr, mixed.stderr


def test_the_building_flag_is_set_with_the_session_and_cleared_after_the_last_pane(
    tmp_path: Path,
) -> None:
    """Fake tmux: the flag rides the SAME `new-session` invocation (chained with `;`), before the root is recorded, and is
    unset before the attach."""
    repo = _repo(tmp_path, {DEV1: "dev1", DEV2: "dev2"})
    home = _tmux_home(tmp_path, repo, has=False, owner=None)
    out = _run(str(repo), home=home, tty=True, **NOBUS)
    assert out.returncode == 0, out.stderr
    log = _log(home)
    text = (home / "tmux.log").read_text(
        encoding="utf-8"
    )  # a pane command spans lines: search the whole text
    chained = text.index(" ; set-option -t =fabrik-lib: @agents_up_building ")
    assert text.index("new-session -d -s fabrik-lib") < chained < text.index("@agents_up_root"), (
        text
    )
    unset = log.index("set-option -t =fabrik-lib: -u @agents_up_building")
    assert log.index(f"set-option -t =fabrik-lib: @agents_up_root {repo}") < unset < len(log) - 1, (
        log
    )
    assert log[-1] == "attach -t =fabrik-lib", log


# --- T03 review pass 1 ----------------------------------------------------------------------------------------------


def test_a_launch_that_loses_the_race_kills_nothing_of_the_winners(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    """F1: the loser decided to build (its has-session said no), then its new-session failed on the winner's session. Its
    stale-overflow cleanup must not have run: the winner's `<S>+2` is the same session afterwards."""
    sc = _Scratch(tmp_path, request, 6)
    assert sc.up().returncode == 0
    winners = sc.one(f"{sc.S}+2", "#{session_id}")
    (sc.home / "lose-race").write_text("", encoding="utf-8")
    out = sc.up()
    assert out.returncode == 0, out.stderr
    assert (sc.home / "lost-once").exists(), "the loser must have taken the build path"
    assert sc.sessions() == [sc.S, f"{sc.S}+2"], sc.sessions()
    assert sc.one(f"{sc.S}+2", "#{session_id}") == winners
    assert (
        sc.one(sc.S, "#{@agents_up_building}") == ""
    )  # and the loser cleared nothing it did not set, set nothing


def test_a_session_still_grouped_under_the_base_name_is_said_and_no_overflow_is_made(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    """F2: D-1132's hand-made `<S>-2`, grouped with a killed `<S>`, keeps the group name `<S>` alive, and a new
    `new-session -t =<S>` would JOIN it. It is never killed (it may be another repo's), the launch says so naming it, and
    no overflow session is made; a later `--window 2` refuses rather than attach a session showing the old windows."""
    sc = _Scratch(tmp_path, request, 6)
    for args in (
        ("new-session", "-d", "-s", sc.S, "-n", "oldwin", "sleep 300"),
        ("new-session", "-d", "-t", f"={sc.S}", "-s", f"{sc.S}-2"),
        ("kill-session", "-t", f"={sc.S}"),
    ):
        assert sc.tmux(*args).returncode == 0, args
    stale = sc.one(f"{sc.S}-2", "#{session_id}")
    out = sc.up()
    assert out.returncode == 0, out.stderr
    assert f"the tmux session {sc.S}-2 is still grouped under the name {sc.S}" in out.stderr, (
        out.stderr
    )
    assert f"tmux kill-session -t ={sc.S}-2" in out.stderr, out.stderr
    assert sc.sessions() == sorted([sc.S, f"{sc.S}-2"]), (
        sc.sessions()
    )  # no `<S>+2`, and `<S>-2` untouched
    assert sc.one(f"{sc.S}-2", "#{session_id}") == stale
    assert sc.windows() == ["agents 4", "agents-2 2"], sc.windows()
    # G1: `--window 2` must not join the stale group (it would drag the base into it and lose the grid's windows)
    again = sc.up("--window", "2")
    assert (
        again.returncode == 2
        and f"free the group with: tmux kill-session -t ={sc.S}-2" in again.stderr
    ), again.stderr
    assert sc.windows() == ["agents 4", "agents-2 2"], sc.windows()
    assert sc.one(sc.S, "#{session_group}") == ""
    assert sc.sessions() == sorted([sc.S, f"{sc.S}-2"]), sc.sessions()  # no `<S>+2`
    assert (
        sc.tmux("new-window", "-d", "-t", f"={sc.S}-2:").returncode == 0
    )  # a change on the stale side
    assert sc.windows() == ["agents 4", "agents-2 2"], sc.windows()


def test_a_stale_member_whose_name_holds_the_separator_is_still_found(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    """G2: tmux allows `|` and `~` in a session name; the member's name is everything before the LAST `|~|`."""
    sc = _Scratch(tmp_path, request, 6)
    odd = "x|~|y"
    for args in (
        ("new-session", "-d", "-s", sc.S, "-n", "oldwin", "sleep 300"),
        ("new-session", "-d", "-t", f"={sc.S}", "-s", odd),
        ("kill-session", "-t", f"={sc.S}"),
    ):
        assert sc.tmux(*args).returncode == 0, args
    out = sc.up()
    assert out.returncode == 0, out.stderr
    assert f"the tmux session {odd} is still grouped under the name {sc.S}" in out.stderr, (
        out.stderr
    )
    assert sc.sessions() == sorted([sc.S, odd]), sc.sessions()


def test_a_concurrent_window_run_keeps_the_session_the_other_run_just_created(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    """F3: between this run's first look and its `<S>+2` check another `--window 2` run created `<S>+2` and grouped `<S>`.
    The group is read AFTER the session's, so the fresh session is kept (not killed under the other run)."""
    sc = _Scratch(tmp_path, request, 2)
    for args in (
        ("new-session", "-d", "-s", sc.S, "-n", "agents", "sleep 300"),
        ("new-window", "-d", "-t", f"={sc.S}:", "-n", "agents-2", "sleep 300"),
        ("set-option", "-t", f"={sc.S}:", "@agents_up_root", str(sc.repo)),
    ):
        assert sc.tmux(*args).returncode == 0, args
    (sc.home / "concurrent").write_text(sc.S, encoding="utf-8")
    out = sc.up("--window", "2")
    assert out.returncode == 0, out.stderr
    assert (sc.home / "concurrent-done").exists()
    theirs = (sc.home / "concurrent-id").read_text(encoding="utf-8").strip()
    assert sc.one(f"{sc.S}+2", "#{session_id}") == theirs
    assert sc.one(f"{sc.S}+2", "#{window_name}") == "agents-2"


def test_an_existing_overflow_session_is_reused_only_when_grouped_with_the_base(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    """F10: invariant 4's reuse rule. A `<S>+2` grouped with `<S>` is kept; an ungrouped one, and one grouped with a
    different base, are replaced and end in `<S>`'s group."""
    sc = _Scratch(tmp_path, request, 6)
    assert sc.up().returncode == 0
    group = sc.one(sc.S, "#{session_group}")
    kept = sc.one(f"{sc.S}+2", "#{session_id}")
    assert sc.up("--window", "2").returncode == 0
    assert sc.one(f"{sc.S}+2", "#{session_id}") == kept
    for label, make in (
        ("ungrouped", ("new-session", "-d", "-s", f"{sc.S}+2", "sleep 300")),
        ("other group", None),
    ):
        assert sc.tmux("kill-session", "-t", f"={sc.S}+2").returncode == 0
        if make:
            assert sc.tmux(*make).returncode == 0, label
        else:
            assert sc.tmux("new-session", "-d", "-s", "elsewhere", "sleep 300").returncode == 0
            assert (
                sc.tmux("new-session", "-d", "-t", "=elsewhere", "-s", f"{sc.S}+2").returncode == 0
            )
        before = sc.one(f"{sc.S}+2", "#{session_id}")
        assert sc.up("--window", "2").returncode == 0, label
        assert sc.one(f"{sc.S}+2", "#{session_id}") != before, label
        assert sc.one(f"{sc.S}+2", "#{session_group}") == group, label
        assert sc.one(f"{sc.S}+2", "#{window_name}") == "agents-2", label


def test_a_window_renamed_with_a_suffix_is_not_the_window(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    """F5: `agents-2 old` is not `agents-2` (a whitespace split would have taken it)."""
    sc = _Scratch(tmp_path, request, 2)
    assert (
        sc.tmux("new-session", "-d", "-s", sc.S, "-n", "agents-2 old", "sleep 300").returncode == 0
    )
    assert sc.tmux("set-option", "-t", f"={sc.S}:", "@agents_up_root", str(sc.repo)).returncode == 0
    out = sc.up("--window", "2")
    assert out.returncode == 0 and "has no window agents-2 now" in out.stderr, out.stderr
    assert sc.sessions() == [sc.S], sc.sessions()


def test_a_server_whose_only_window_is_agents_2_has_no_window_agents(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    """F14 / row 5: tmux itself answers a lookup of `agents` with `agents-2`; the script's own find_window (extracted from
    the script and run against the scratch server) finds none for `agents` and the id for `agents-2`."""
    sc = _Scratch(tmp_path, request, 2)
    assert sc.tmux("new-session", "-d", "-s", sc.S, "-n", "agents-2", "sleep 300").returncode == 0
    loose = sc.tmux("display-message", "-p", "-t", f"={sc.S}:agents", "#{window_name}")
    assert loose.stdout.strip() == "agents-2", loose
    func = re.search(r"^find_window\(\) \{.*?^\}", UP.read_text(encoding="utf-8"), re.S | re.M)
    assert func, "find_window is the script's window lookup"

    def lookup(name: str) -> str:
        env = {"PATH": f"{sc.home}/.local/bin:/usr/bin:/bin", "HOME": str(sc.home)}
        done = subprocess.run(
            ["bash", "-c", f'S="$1"; {func.group(0)}\nfind_window "$2"', "x", sc.S, name],
            capture_output=True,
            text=True,
            timeout=20,
            env=env,
        )
        return done.stdout.strip()

    assert lookup("agents") == ""
    assert re.fullmatch(r"@\d+", lookup("agents-2")), lookup("agents-2")


def test_the_final_select_leaves_the_base_session_on_agents(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    """F8: every window this launch creates steals the base session's focus (as a tmux left on the last window would be);
    the launch must hand tab 1 back to `agents`."""
    sc = _Scratch(tmp_path, request, 6, steal_focus=True)
    out = sc.up()
    assert out.returncode == 0, out.stderr
    assert sc.windows() == ["agents 4", "agents-2 2"], sc.windows()
    assert sc.one(sc.S, "#{window_name}") == "agents"
    assert sc.one(f"{sc.S}+2", "#{window_name}") == "agents-2"


def test_a_build_that_dies_after_the_session_clears_the_building_flag(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    """F9: tmux made the session but handed back no ids, so the launch exits 1 mid-build; the EXIT trap clears the flag."""
    sc = _Scratch(tmp_path, request, 2, garble_ids=True)
    out = sc.up()
    assert out.returncode == 1 and "tmux gave no window and pane id" in out.stderr, out.stderr
    assert sc.sessions() == [sc.S], sc.sessions()
    assert sc.one(sc.S, "#{@agents_up_building}") == ""


def test_the_attach_tail_follows_the_session_window_n_chose(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    """F11: from inside tmux, `--window 2` switches the client to `=<S>+2`, not `=<S>`; `--window 02` is 2."""
    sc = _Scratch(tmp_path, request, 6)
    assert sc.up().returncode == 0
    out = sc.up("--window", "02", TMUX="/tmp/none,1,0")
    assert out.returncode == 0, out.stderr
    assert (sc.home / "switch.log").read_text(encoding="utf-8").splitlines() == [
        f"switch-client -t ={sc.S}+2"
    ]


def test_window_arguments_are_checked_and_never_touch_spawn_or_slice_checks(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    """F6, F12: only an integer 2 or more, once; its own mode. And `--window` builds no pane, so a malformed spawn
    variable (or a refused slice) stops nothing."""
    sc = _Scratch(tmp_path, request, 6)
    for bad in (
        ["2x"],
        ["-3"],
        [],
        ["2", "--window", "3"],
        ["2", "--detach"],
        ["2", "--pane-cmd"],
        ["--detach"],
    ):
        out = sc.up("--window", *bad)
        assert out.returncode == 2, (bad, out.stdout, out.stderr)
        assert sc.tmux("list-sessions").returncode != 0, bad  # nothing was started
    assert sc.up().returncode == 0
    out = sc.up("--window", "2", FABRIK_SPAWN_NAME="dev1", FABRIK_SPAWN_ITEM="nope")
    assert out.returncode == 0 and f"tmux attach -t ={sc.S}+2" in out.stderr, out.stderr


def test_the_building_flag_clears_after_the_last_pane_of_every_window(tmp_path: Path) -> None:
    """F13: with six builders the unset comes after the last `split-window` and `new-window`, never after the root."""
    repo = _repo(tmp_path, {SIX[i]: f"dev{i + 1}" for i in range(6)})
    home = _home(tmp_path, transcripts=tuple((repo, s) for s in SIX))
    tmux = home / ".local" / "bin" / "tmux"
    tmux.write_text(FAKE_TMUX, encoding="utf-8")
    tmux.chmod(0o755)
    out = _run(str(repo), home=home, tty=True, **NOBUS)
    assert out.returncode == 0, out.stderr
    text = (home / "tmux.log").read_text(encoding="utf-8")
    last_pane = max(text.rfind("\nsplit-window "), text.rfind("\nnew-window "))
    assert (
        last_pane > 0 and text.count("\nnew-window ") == 1 and text.count("\nsplit-window ") == 4
    ), text.count("\n")
    first_unset = text.find(
        "set-option -t =fabrik-lib: -u @agents_up_building"
    )  # the FIRST unset, not the last
    assert first_unset > last_pane


def test_a_live_grids_viewer_session_is_not_stale_and_does_not_block_window_n(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    """H1: a session grouped with a healthy grid (an operator's viewer) is live; `--window 2` builds `<S>+2` beside it."""
    sc = _Scratch(tmp_path, request, 6)
    assert sc.up().returncode == 0
    assert sc.tmux("new-session", "-d", "-t", f"={sc.S}", "-s", "viewer").returncode == 0
    viewer = sc.one("viewer", "#{session_id}")
    assert sc.tmux("kill-session", "-t", f"={sc.S}+2").returncode == 0
    out = sc.up("--window", "2")
    assert sc.one("viewer", "#{session_id}") == viewer
    group = sc.one(sc.S, "#{session_group}")
    assert group and sc.one(f"{sc.S}+2", "#{session_group}") == group, out.stderr
    assert sc.one(f"{sc.S}+2", "#{window_name}") == "agents-2"
    assert out.returncode == 0, out.stderr


# --- W-e38f8ee7: `--pane-cmd … --into <folder> --from <old sid> --replacing <pid>` (rotate-session --move's launch) ---

MOVED = "8e8e8e8e-8e8e-4e8e-8e8e-8e8e8e8e8e8e"


def _move_repo(tmp: Path) -> tuple[Path, Path, Path]:
    """`_bound_repo` (b2, b3 in their own trees) plus `b2-work`, the linked worktree b2 now works in; b2's session B2
    is filed under its own tree, where the grid starts it. Returns (root, store, home)."""
    repo, store = _bound_repo(tmp)
    _worktree(repo, "b2-work")
    home = _home(tmp, transcripts=((_wt(repo, "b2"), B2), (_wt(repo, "b3"), B3)))
    return repo, store, home


def _move_args(
    repo: Path, name: str = "b2", sid: str = MOVED, into: str = "b2-work", old: str = B2
) -> list[str]:
    return [
        "--pane-cmd",
        str(repo),
        name,
        sid,
        "--into",
        into,
        "--from",
        old,
        "--replacing",
        "4242",
    ]


def _live_claude(home: Path, pid: int, cwd: Path, args: str) -> None:
    """One claude process as `named_running` sees it: a fake `ps` line and a /proc/<pid>/cwd under FABRIK_PROC_ROOT."""
    d = home / "proc" / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "cwd").symlink_to(cwd)
    (home / ".local" / "bin" / "ps").write_text(
        f'#!/bin/sh\n[ "$*" = "-ww -C claude -o pid=,args=" ] || exit 1\necho \'{pid} {args}\'\n',
        encoding="utf-8",
    )


def test_pane_cmd_into_prints_a_fresh_launch_with_the_move_prompt(tmp_path: Path) -> None:
    """W-e38f8ee7 B6: `--pane-cmd … --into` prints ONE pane command that starts a FRESH `--session-id <sid>` claude, and
    its wake is the move prompt: the folder and the new id, then rotate_session.resume_prompt's text with the id
    filled in (the two copies are pinned equal). The replaced claude (`--replacing`, here running `-n b2` in the target
    folder, as fleet's was) never makes it `running`; the kept shell's hint names `--session-id` while no transcript
    exists. Executed by /bin/sh against a fake claude."""
    repo, store, home = _move_repo(tmp_path)
    _live_claude(home, 4242, _wt(repo, "b2-work"), f"claude -n b2 --resume {B2}")
    _fake_claude(home)
    out = _run(*_move_args(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert len(out.stdout.splitlines()) == 1, out.stdout
    inner = _inner("run b2 " + out.stdout.strip())
    assert (
        f"claude -n b2 --permission-mode bypassPermissions --session-id {MOVED} --settings '{SETTINGS}' '"
        in inner
    ), inner
    assert "is already running elsewhere" not in inner, inner
    assert "--resume" not in inner.split("; rc=")[0], inner
    args = _argv(home, out.stdout.strip())
    assert (
        args[:7]
        == [
            "-n",
            "b2",
            "--permission-mode",
            "bypassPermissions",
            "--session-id",
            MOVED,
            "--settings",
        ]
        and len(args) == 9
    ), args
    prompt = args[8]
    head = (
        f"You were moved by agents_up into .claude/worktrees/b2-work as a fresh session {MOVED}, "
        "so your hooks load from the tree you work in. "
    )
    assert prompt.startswith(head), prompt
    spec = importlib.util.spec_from_file_location(
        "_rs_parity", ROOT / "scripts" / "sysadmin" / "rotate_session.py"
    )
    rs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rs)
    want = (
        rs.resume_prompt("b2")
        .replace("<your session id>", MOVED)
        .replace(
            "bash /opt/fabrik/scripts/sysadmin/selfwatch_arm.sh",
            f'bash "{ROOT}/scripts/sysadmin/selfwatch_arm.sh"',
        )
        .replace(
            "python3 /opt/fabrik/scripts/whoami_agent.py",
            f'python3 "{ROOT}/scripts/whoami_agent.py"',
        )
    )
    # the checkout's paths are double-quoted, as first_prompt's are, so a path with a space stays one word (pass 1, B1)
    assert prompt[len(head) :] == want, (prompt[len(head) :], want)
    said = _hint("run b2 " + out.stdout.strip(), tmp_path)
    assert f"claude -n b2 --permission-mode bypassPermissions --session-id {MOVED}" in said, said
    # the same valid launch with one flag given twice is refused, never silently the last value (pass 1, B5)
    for flag, value in (("--into", "b2-work"), ("--from", B2), ("--replacing", "4242")):
        twice = _run(*_move_args(repo), flag, value, home=home, AGENT_IDENTITY_FILE=str(store))
        assert twice.returncode == 2 and twice.stdout == "", (flag, twice.stdout)
        assert f"{flag} is given once" in twice.stderr, (flag, twice.stderr)


def test_pane_cmd_into_refusals(tmp_path: Path) -> None:
    """W-e38f8ee7 B7: every `--pane-cmd --into` refusal exits 2 and prints nothing — a known id or one with a
    transcript, a name the resolver does not give, a `--from` that is not the chosen session, a folder that is no
    linked worktree in place, a coordinator's tree or another builder's, ANOTHER live `claude -n <name>` in the folder
    (the `--replacing` pid excepted), and the flag combinations."""
    repo, store, home = _move_repo(tmp_path)
    env = {"AGENT_IDENTITY_FILE": str(store)}
    _worktree(repo, "coordinator")
    (repo / ".claude" / "worktrees" / "plain").mkdir()
    _transcript(home, tmp_path / "anywhere", NEW2)
    for args, reason in (
        (_move_args(repo, sid=NEW2), f"{NEW2} has a transcript — not a fresh session"),
        (
            _move_args(repo, sid=B3),
            f"{B3} is a session this repo already knows — not a fresh session",
        ),
        (_move_args(repo, name="b9"), "b9 is not a builder the resolver gives"),
        (_move_args(repo, old=B3), f"b2's session is {B2}, not {B3}"),
        (
            _move_args(repo, into="plain"),
            "plain: .claude/worktrees/plain is no longer a linked git worktree in place",
        ),
        (
            _move_args(repo, into="nope"),
            "nope: .claude/worktrees/nope is no longer a linked git worktree in place",
        ),
        (_move_args(repo, into="coordinator"), "coordinator is the coordinator's tree"),
        (_move_args(repo, into="b3"), "b3 is b3's tree"),
        (_move_args(repo, into="Bad"), "'Bad' is not a worktree folder name"),
    ):
        bad = _run(*args, home=home, **env)
        assert bad.returncode == 2 and bad.stdout == "", (args, bad.stdout, bad.stderr)
        assert reason in bad.stderr, (args, bad.stderr)
    # another claude by the same name already works in the folder: refused; the replaced pid alone is not (B6)
    _live_claude(home, 4243, _wt(repo, "b2-work"), f"claude -n b2 --resume {DEV1}")
    bad = _run(*_move_args(repo), home=home, **env)
    assert bad.returncode == 2 and bad.stdout == "", bad.stdout
    assert (
        "another claude -n b2 (pid 4243) already runs in .claude/worktrees/b2-work" in bad.stderr
    ), bad.stderr
    # the three flags come together, and never with --new/--coordinator/--item
    base = ["--pane-cmd", str(repo), "b2", MOVED]
    for argv in (
        [*base, "--into", "b2-work"],
        [*base, "--into", "b2-work", "--from", B2],
        [*base, "--from", B2, "--replacing", "4242"],
        [*_move_args(repo), "--new"],
        [*_move_args(repo), "--item", "W-1a2b3c4d"],
        [*_move_args(repo), "--coordinator", "c"],
        [*base, "--into", "b2-work", "--from", B2, "--replacing", "x1"],
        [*base, "--into", "b2-work", "--from", "not-a-uuid", "--replacing", "1"],
    ):
        bad = _run(*argv, home=home, **env)
        assert bad.returncode == 2 and bad.stdout == "", (argv, bad.stdout, bad.stderr)


def test_pane_cmd_into_refuses_the_owner_a_shared_folder_and_a_foreign_pid(tmp_path: Path) -> None:
    """W-e38f8ee7 review pass 1 (B2, B3, B4): `--into` refuses the merge owner's tree (the resolver drops the owner, so
    only the owner check sees it), a folder another builder's session resolved to (not its own-named tree), and a
    `--replacing` pid that is not a running `claude -n <name>` — a wrong pid would otherwise disarm the refusal of a
    second same-named claude in the folder."""
    # the merge owner: b3 is declared owner, so it is no builder and `--into b3` meets the owner check alone
    repo, store, home = _move_repo(tmp_path / "own")
    _ledger(repo, "b3")
    _live_claude(home, 4242, _wt(repo, "b2"), f"claude -n b2 --resume {B2}")
    bad = _run(*_move_args(repo, into="b3"), home=home, AGENT_IDENTITY_FILE=str(store))
    assert bad.returncode == 2 and bad.stdout == "", bad.stdout
    assert "b3 is the coordinator's tree (the merge owner)" in bad.stderr, bad.stderr
    # b3's session lives in b2-work, so b3's resolved folder is b2-work: never b2's to move into
    repo, store = _bound_repo(tmp_path / "shared")
    _worktree(repo, "b2-work")
    home = _home(
        tmp_path / "shared", transcripts=((_wt(repo, "b2"), B2), (_wt(repo, "b2-work"), B3))
    )
    bad = _run(*_move_args(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert bad.returncode == 2 and bad.stdout == "", bad.stdout
    assert "b2-work is b3's tree" in bad.stderr, bad.stderr
    # the replaced pid must be this builder's claude: another name, or no such process, refuses
    repo, store, home = _move_repo(tmp_path / "pid")
    for args in (f"claude -n b3 --resume {B3}", None):
        if args:
            _live_claude(home, 4242, _wt(repo, "b3"), args)
        else:
            (home / ".local" / "bin" / "ps").write_text(
                '#!/bin/sh\n[ "$*" = "-ww -C claude -o pid=,args=" ] || exit 1\n', encoding="utf-8"
            )
        bad = _run(*_move_args(repo), home=home, AGENT_IDENTITY_FILE=str(store))
        assert bad.returncode == 2 and bad.stdout == "", (args, bad.stdout)
        assert "--replacing 4242 is not a running claude -n b2" in bad.stderr, (args, bad.stderr)
