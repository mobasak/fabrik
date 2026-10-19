"""`agents-up <repo>` (D-1031): one tmux session per repo, one pane per builder, read from the repo's own registry.

Driven through `--print`, which reports the grid it would build and launches nothing — never tmux, never claude. A
fake `ps` on the launcher's own PATH (`$HOME/.local/bin`) stands in for the live claude processes.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UP = ROOT / "scripts" / "sysadmin" / "agents_up.sh"

DEV1 = "610c3b1c-a5ef-4ba0-a662-f3f87399a58b"
DEV2 = "413b420e-3b36-4d13-b4f6-ee3f71f98de2"
SENT = "67ccc993-3fda-4dcd-a392-4531f01c6e5d"
COORD = "0f0e0d0c-0b0a-4908-8706-050403020100"


def _repo(tmp: Path, registry: object, name: str = "fabrik-lib") -> Path:
    repo = tmp / name
    (repo / ".fabrik").mkdir(parents=True)
    text = registry if isinstance(registry, str) else json.dumps(registry)
    (repo / ".fabrik" / "session-agents.json").write_text(text, encoding="utf-8")
    return repo.resolve()


def _home(tmp: Path, ps_lines: str = "", transcripts: tuple[tuple[Path, str], ...] = ()) -> Path:
    """A HOME with a fake `ps` printing `ps_lines`, and a transcript per (repo root, session id)."""
    home = tmp / "home"
    (home / ".local" / "bin").mkdir(parents=True, exist_ok=True)
    ps = home / ".local" / "bin" / "ps"
    # answers only the launcher's exact question: every claude process, full width (-ww)
    ps.write_text(
        '#!/bin/sh\n[ "$*" = "-ww -C claude -o args=" ] || exit 1\n'
        f"cat <<'EOF'\n{ps_lines}\nEOF\n",
        encoding="utf-8",
    )
    ps.chmod(0o755)
    for root, sid in transcripts:
        folder = (
            home / ".claude-fleet" / "active" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(root))
        )
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{sid}.jsonl").write_text("{}\n", encoding="utf-8")
    return home


def _run(*args: str, home: Path, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(UP), *args],
        capture_output=True,
        text=True,
        timeout=30,
        env={"PATH": "/usr/bin:/bin", "HOME": str(home), **env},
    )


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
        f"pane fabrik-lib-dev1 {DEV1} {repo} ok",
        f"pane fabrik-lib-dev2 {DEV2} {repo} ok",
        f"pane fabrik-lib-sentinel {SENT} {repo} ok",
    ], out.stdout
    run = [ln for ln in out.stdout.splitlines() if ln.startswith("run fabrik-lib-dev1 ")]
    assert len(run) == 1 and f"claude -n fabrik-lib-dev1 --resume {DEV1};" in run[0], out.stdout


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
        f"pane dev1 {DEV1} {repo} running",
        f"pane dev2 {DEV2} {repo} running",
        f"pane sentinel {SENT} {repo} ok",
        f"pane tester {third} {repo} running",
    ], out.stdout
    run = {ln.split()[1]: ln for ln in out.stdout.splitlines() if ln.startswith("run ")}
    # a running session's pane only prints a message; it never starts claude
    assert run["dev1"].startswith('run dev1 echo "[dev1 is already running elsewhere'), run["dev1"]
    assert run["dev2"].startswith('run dev2 echo "[dev2 is already running elsewhere'), run["dev2"]
    assert run["sentinel"].startswith("run sentinel env -i "), run["sentinel"]
    # the shell a running session's pane keeps is clean too, never the tmux server's environment
    assert run["dev1"].rstrip().endswith("bash -l") and "; exec env -i " in run["dev1"], run["dev1"]


def test_a_session_with_no_transcript_under_the_root_is_flagged(tmp_path: Path) -> None:
    """claude resumes a session by the folder it starts in; a session with no transcript there is reported, so a
    pane that will only print "No conversation found" is visible before the launch."""
    repo = _repo(tmp_path, {DEV1: "dev1", DEV2: "dev2"})
    home = _home(tmp_path, transcripts=((repo, DEV1), (repo / "elsewhere", DEV2)))
    out = _run("--print", str(repo), home=home)
    assert _panes(out.stdout) == [
        f"pane dev1 {DEV1} {repo} ok",
        f"pane dev2 {DEV2} {repo} no-transcript",
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
    launch = run[len("run dev1 ") :].split(";")[0]
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
        ["/bin/sh", "-c", launch], capture_output=True, text=True, timeout=30, env=polluted
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
    # the shell a pane keeps after claude exits starts from the same allow-list
    assert run.rstrip().endswith("bash -l") and run.count("env -i ") == 2, run


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
    """A repo with no `.fabrik/session-agents.json` says where the builders are named and stops; so does a path that
    is no directory, and a call with no repo at all."""
    home = _home(tmp_path)
    bare = tmp_path / "bare"
    bare.mkdir()
    cases = (
        (("--print", str(bare)), "does not exist"),
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
    assert "session-agents.json" in out.stderr and "whoami binding" in out.stderr, out.stderr


def test_the_session_name_is_the_repo_basename(tmp_path: Path) -> None:
    """tmux reads `.`, `:` and glob characters in a target, so only [A-Za-z0-9_-] survive; a trailing slash or a
    relative path changes nothing, because the root is resolved first."""
    repo = _repo(tmp_path, {DEV1: "dev1"}, name="web.shop:v2[x]*")
    home = _home(tmp_path)
    out = _run("--print", f"{repo}/", home=home)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines()[0] == "session web-shop-v2-x--", out.stdout
    assert _panes(out.stdout)[0].startswith(f"pane dev1 {DEV1} {repo} "), out.stdout
    rel = subprocess.run(
        ["bash", str(UP), "--print", repo.name],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=repo.parent,
        env={"PATH": "/usr/bin:/bin", "HOME": str(home)},
    )
    assert _panes(rel.stdout)[0].startswith(f"pane dev1 {DEV1} {repo} "), rel.stdout
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
    assert _panes(rel.stdout)[0].startswith(f"pane dev1 {DEV1} {dashed} "), rel.stdout


FAKE_TMUX = """#!/bin/sh
echo "$*" >> "$HOME/tmux.log"
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


def _tmux_home(tmp: Path, repo: Path, has: bool, owner: str | None) -> Path:
    """A HOME whose fake `tmux` logs every call and plays a session that exists (`has`) with an `@agents_up_root`."""
    home = _home(tmp, transcripts=((repo, DEV1), (repo, DEV2)))
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
    out = _run(str(repo), home=home)
    assert out.returncode == 0, out.stderr
    log = _log(home)
    assert log[0] == "has-session -t =fabrik-lib", log
    assert any(ln.startswith("new-session -d -s fabrik-lib -n agents -c ") for ln in log), log
    assert f"set-option -t =fabrik-lib @agents_up_root {repo}" in log, log
    assert sum(ln.startswith("split-window -t =fabrik-lib:agents ") for ln in log) == 1, log
    assert "select-pane -t =fabrik-lib:agents.0" in log, log  # a fresh grid opens on its first pane
    assert log[-1] == "attach -t =fabrik-lib", log
    # a root that cannot be recorded is said, because every later launch would refuse the grid
    failed = _tmux_home(tmp_path / "setfail", repo, has=False, owner=None)
    (failed / "tmux-setfail").write_text("", encoding="utf-8")
    out = _run(str(repo), home=failed)
    assert out.returncode == 0 and "could not record the root" in out.stderr, out.stderr
    assert _log(failed)[-1] == "attach -t =fabrik-lib", _log(failed)


def test_an_existing_grid_is_reattached_only_when_it_is_this_repos(tmp_path: Path) -> None:
    """A session is named after the folder only, so a grid already up under the name must carry this repo's root: the
    repo's own grid is reattached as it is (no pane rebuilt), another folder's is refused, and so is one that never
    records a root (after the one re-read an in-progress launch is given)."""
    repo = _repo(tmp_path, {DEV1: "dev1", DEV2: "dev2"})
    mine = _tmux_home(tmp_path / "mine", repo, has=True, owner=str(repo))
    out = _run(str(repo), home=mine)
    assert out.returncode == 0, out.stderr
    assert not any(ln.startswith(("new-session", "split-window")) for ln in _log(mine)), _log(mine)
    assert _log(mine)[-1] == "attach -t =fabrik-lib", _log(mine)
    # "other-tagged": another folder's recorded grid is never adopted, even when its panes carry this repo's names
    for label, owner in (
        ("other", "/opt/elsewhere/fabrik-lib"),
        ("none", None),
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
    one of this repo's builders; a stranger pane, an untagged pane or no pane at all still refuses."""
    repo = _repo(tmp_path, {DEV1: "dev1", DEV2: "dev2"})
    ours = _tmux_home(tmp_path / "ours", repo, has=True, owner=None)
    (ours / "tmux-panes").write_text("%1 dev1\n%2 dev2\n", encoding="utf-8")
    out = _run(str(repo), home=ours)
    assert out.returncode == 0 and "adopted" in out.stderr, out.stderr
    # its panes skipped the env allow-list, and the operator is told how to get clean ones
    assert "keep the environment they started with" in out.stderr, out.stderr
    assert f"set-option -t =fabrik-lib @agents_up_root {repo}" in _log(ours), _log(ours)
    assert not any(ln.startswith(("new-session", "split-window")) for ln in _log(ours)), _log(ours)
    assert _log(ours)[-1] == "attach -t =fabrik-lib", _log(ours)
    for label, panes in (
        ("stranger", "%1 dev1\n%2 stranger\n"),
        ("untagged", "%1 dev1\n%2 \n"),
        ("prefix", "%1 dev\n"),
    ):
        home = _tmux_home(tmp_path / label, repo, has=True, owner=None)
        (home / "tmux-panes").write_text(panes, encoding="utf-8")
        out = _run(str(repo), home=home)
        assert out.returncode == 2 and "not attaching" in out.stderr, (label, out.stderr)
        assert not any(ln.startswith(("attach", "set-option")) for ln in _log(home)), (
            label,
            _log(home),
        )


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
        out = _run(str(repo), home=home)
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


def test_a_builder_with_a_worktree_starts_in_it(tmp_path: Path) -> None:
    """W-6c7c3292 (fabrik-lib mail 01M59SWZGB): a builder works in `<repo>/.claude/worktrees/<name>`, and the main
    checkout is the coordinator's, so a builder resumed at the root would edit main's tree and read main's CLAUDE.md.
    A pane starts in the builder's worktree when it is a linked git worktree in place and at the root otherwise, and
    its transcript is looked for under the folder it starts in, since claude resumes by that folder. A file, a folder
    with no `.git` (left behind by `git worktree remove`), a nested clone (a `.git` FOLDER) and a symlink — which could
    take the pane out of the repo, and names a project folder claude never writes to — all start at the root, and each
    says so on stderr, because that builder then works in the main checkout; a builder with nothing by its name is
    silent."""
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
        transcripts=(
            (wt1, DEV1),
            (repo, DEV2),
            (repo, SENT),
            (repo, third),
            (repo, fourth),
            (repo, fifth),
            (repo, sixth),
            (repo, seventh),
        ),
    )
    out = _run("--print", str(repo), home=home)
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [
        f"pane clone {sixth} {repo} ok",
        f"pane dev1 {DEV1} {wt1} ok",
        f"pane dev2 {DEV2} {repo} ok",
        f"pane gone {seventh} {repo} ok",
        f"pane linked {fourth} {repo} ok",
        f"pane plain {fifth} {repo} ok",
        f"pane sentinel {SENT} {sent_wt} no-transcript",
        f"pane stale {third} {repo} ok",
    ], out.stdout
    warned = sorted(
        ln.split(":")[1].strip()
        for ln in out.stderr.splitlines()
        if "is not a linked git worktree in place" in ln
    )
    assert warned == ["clone", "dev2", "gone", "linked", "stale"], out.stderr


def _worktree(repo: Path, name: str) -> Path:
    """A git worktree's folder as the launcher sees it: `.claude/worktrees/<name>` holding a `.git` file."""
    wt = repo / ".claude" / "worktrees" / name
    wt.mkdir(parents=True)
    (wt / ".git").write_text(f"gitdir: {repo}/.git/worktrees/{name}\n", encoding="utf-8")
    return wt.resolve()


def test_the_launch_starts_each_pane_in_its_folder(tmp_path: Path) -> None:
    """The launch path hands tmux each pane's own folder — the first builder's to new-session, the next to its split —
    and reads each transcript under that folder, naming it when it is missing."""
    repo = _repo(tmp_path, {DEV1: "dev1", DEV2: "dev2"})
    wt1, wt2 = _worktree(repo, "dev1"), _worktree(repo, "dev2")
    home = _tmux_home(tmp_path, repo, has=False, owner=None)
    # dev1's transcript sits under its worktree; dev2's only under the root, where its pane does not start
    (home / ".claude-fleet" / "active" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(wt1))).mkdir(
        parents=True
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

    f = (
        home
        / ".claude-fleet"
        / "active"
        / "projects"
        / re.sub(r"[^A-Za-z0-9]", "-", str(repo))
        / f"{sid}.jsonl"
    )
    t = time.time() - age_s
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
    assert _panes(out.stdout) == [f"pane dev1 {NEW1} {repo} ok", f"pane dev2 {NEW2} {repo} ok"]
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
    assert _panes(out.stdout) == [f"pane dev1 {NEW2} {repo} ok"]
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
    assert _panes(out.stdout) == [f"pane dev1 {DEV1} {repo} ok", f"pane dev2 {NEW2} {repo} ok"]
    assert f"resuming {NEW1}" not in out.stderr, out.stderr
    # the last line naming dev1 wins over a larger `at` on an earlier line (a clock that stepped back)
    store = _store(
        tmp_path,
        [_bind(NEW2, "dev1", scope, NOW + 10), _bind(NEW1, "dev1", scope, NOW)],
        "s2.jsonl",
    )
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout)[0] == f"pane dev1 {NEW1} {repo} no-transcript", out.stdout
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
    assert _panes(out.stdout) == [f"pane dev1 {DEV1} {repo} ok"]


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
        assert _panes(out.stdout) == [f"pane dev1 {DEV1} {repo} ok"], (bad, out.stdout)
    # a time no int() takes reads as 0, as whoami's own `_at` does: the row still counts, the store is not lost
    store = _store(tmp_path, [_bind(NEW1, "dev1", scope, "²"), good], "sup.jsonl")
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0 and _panes(out.stdout) == [f"pane dev1 {DEV1} {repo} ok"], out.stderr
    assert "could not be read" not in out.stderr, out.stderr
    fifo = tmp_path / "fifo.jsonl"
    os.mkfifo(fifo)
    for store in (tmp_path / "missing.jsonl", tmp_path, fifo):
        out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
        assert out.returncode == 0, (store, out.stderr)
        assert _panes(out.stdout) == [f"pane dev1 {DEV1} {repo} ok"], (store, out.stdout)
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
    assert _panes(out.stdout) == [f"pane dev1 {NEW1} {repo} no-transcript"], out.stdout
    # no git scope at all: the store is never read, even when it holds a binding of an empty scope
    (tmp_path / "plain").mkdir()
    plain = _repo(tmp_path / "plain", {DEV1: "dev1"})
    store = _store(tmp_path, [_bind(NEW1, "dev1", "", NOW)], "empty.jsonl")
    out = _run("--print", str(plain), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [f"pane dev1 {DEV1} {plain} no-transcript"], out.stdout
    assert "no git scope" in out.stderr, out.stderr


def test_a_duplicate_name_resolves_through_the_store_or_refuses(tmp_path: Path) -> None:
    """A registry that kept dev1's old row beside its new one launches when the store names dev1's session; with no
    binding it is still refused, as before (D-1032's fail-closed rule, narrowed)."""
    repo, scope = _git_repo(tmp_path, {DEV1: "dev1", NEW1: "dev1"})
    home = _home(tmp_path, transcripts=((repo, NEW1),))
    store = _store(tmp_path, [_bind(NEW1, "dev1", scope, NOW)])
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [f"pane dev1 {NEW1} {repo} ok"]
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
    home = _home(tmp_path, transcripts=((repo, DEV1), (repo, DEV2), (repo, NEW2)))
    proj = home / ".claude-fleet" / "active" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(repo))
    old = time.time() - 3600
    for sid in (DEV1, DEV2):
        os.utime(proj / f"{sid}.jsonl", (old, old))
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


def _hint(run_line: str, cwd: Path) -> str:
    """What a pane prints when claude exits: the hint command from its `run` line, executed by bash."""
    cmd = re.search(r"; echo; (printf '%s\\n' .*?); exec env ", run_line)
    assert cmd, run_line
    said = subprocess.run(
        ["bash", "-c", cmd.group(1)], cwd=cwd, capture_output=True, text=True, timeout=30
    )
    return said.stdout.strip()


def test_the_exit_hint_never_runs_a_folder_name(tmp_path: Path) -> None:
    """The hint a pane prints when claude exits names the repo folder; a `$(...)`, a backtick or a `$NAME` in that name
    is printed, never run, and the printed command pastes back to the real folder."""
    for i, name in enumerate(("a$(touch pwned)b", "a`touch pwned`b", "a$HOME b")):
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
    home = _home(tmp_path, transcripts=((repo, DEV1), (repo, NEW1)))
    _aged(home, repo, DEV1, 60)
    _aged(home, repo, NEW1, 30)  # both transcripts dated; the binding's own is the newer
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [f"pane dev1 {NEW1} {repo} ok"], out.stderr
    _aged(home, repo, NEW1, 3600)  # ...and once the registry's is the newer, it stands
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert _panes(out.stdout) == [f"pane dev1 {DEV1} {repo} ok"], out.stderr
    proj = home / ".claude-fleet" / "active" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(repo))
    (proj / f"{NEW1}.jsonl").unlink()
    out = _run("--print", str(repo), home=home, AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert _panes(out.stdout) == [f"pane dev1 {NEW1} {repo} no-transcript"], out.stderr


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
