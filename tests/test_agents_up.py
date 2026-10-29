"""`agents-up <repo>` (D-1031): one tmux session per repo, one pane per builder, read from the repo's own registry.

Driven through `--print`, which reports the grid it would build and launches nothing — never tmux, never claude. A
fake `ps` on the launcher's own PATH (`$HOME/.local/bin`) stands in for the live claude processes.
"""

from __future__ import annotations

import json
import os
import pty
import re
import shutil
import subprocess
from pathlib import Path

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
    # answers only the launcher's exact question: every claude process, full width (-ww)
    ps.write_text(
        '#!/bin/sh\n[ "$*" = "-ww -C claude -o args=" ] || exit 1\n'
        f"cat <<'EOF'\n{ps_lines}\nEOF\n",
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


def _run(*args: str, home: Path, tty: bool = False, **env: str) -> subprocess.CompletedProcess[str]:
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
            ["bash", str(UP), *args], capture_output=True, text=True, timeout=30, env=full
        )
    master, slave = pty.openpty()
    try:
        done = subprocess.run(
            ["bash", str(UP), *args],
            stdin=slave,
            stdout=slave,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
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
    assert (
        len(run) == 1
        and f'claude -n fabrik-lib-dev1 --resume {DEV1} "You were relaunched' in run[0]
    ), out.stdout


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
        "no-builders": (json.dumps({COORD: "fabrik-lib-coordinator"}), "names no builder"),
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
    exit 0 ;;
  set-option)
    # tmux-setfail: the root cannot be recorded
    [ -f "$HOME/tmux-setfail" ] && exit 1
    exit 0 ;;
  split-window)
    # tmux-splitfail: no room for another pane
    [ -f "$HOME/tmux-splitfail" ] && exit 1
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
    assert sum(ln.startswith("split-window -t =fabrik-lib:agents ") for ln in log) == 1, log
    assert "select-pane -t =fabrik-lib:agents.0" in log, log  # a fresh grid opens on its first pane
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
    assert out.returncode == 0 and "no room for dev2's pane" in out.stderr, out.stderr
    labels = [ln for ln in _log(split) if ln.startswith("set -p ")]
    assert labels == ["set -p -t =fabrik-lib:agents @agent dev1"], _log(split)

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
    assert any(ln.startswith(f"split-window -t =fabrik-lib:agents -c {wt2} ") for ln in log), log
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
    """Bindings but no worktree: nothing to launch, exit 2 — the main checkout is never a builder's pane."""
    repo, store = _bound_repo(tmp_path, worktrees=())
    out = _run("--print", str(repo), home=_home(tmp_path), AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 2 and "pane " not in out.stdout, out.stdout
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
    assert "[dev1 exited — run: claude -n dev1 --resume" in got.stdout, got.stdout
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
    """The relaunch (L1, L4, L5): `claude -n <name> --resume <sid> "<wake prompt>"` with CLAUDE_CODE_RETRY_WATCHDOG=1 in
    the allow-listed env and oom_score_adj 200 set before claude starts; the prompt orders the self-watch arm and
    names no `hibernate.py woke` until T01a's lift-only woke is on this branch; no --permission-mode is passed (permissions.defaultMode decides). The
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
    assert args[:4] == ["-n", "dev1", "--resume", DEV1] and len(args) == 5, got.stdout
    prompt = args[4]
    assert f"selfwatch_arm.sh {DEV1}" in prompt, prompt
    assert "hibernate.py woke" not in prompt and "seed" not in prompt, prompt
    assert "carry on as usual" in prompt, prompt
    assert "CLAUDE_CODE_RETRY_WATCHDOG=1" in got.stdout, got.stdout
    assert re.search(r"^OOM=(200|[3-9]\d\d|1000)$", got.stdout, flags=re.M), got.stdout
    assert "--permission-mode" not in run and "--dangerously" not in run, run
    # the quoting survives the nested single quotes of the scope's `bash -c '<inner>'` for ANY folder name
    assert '"' not in prompt and "'" not in prompt and "$" not in prompt, prompt


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
    assert any(ln.startswith(f"split-window -t =fabrik-lib:agents -c {uncapped} ") for ln in log), (
        log
    )


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
