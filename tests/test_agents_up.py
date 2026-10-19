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


def _run(*args: str, home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(UP), *args],
        capture_output=True,
        text=True,
        timeout=30,
        env={"PATH": "/usr/bin:/bin", "HOME": str(home)},
    )


def _panes(out: str) -> list[str]:
    return [ln for ln in out.splitlines() if ln.startswith("pane ")]


def test_print_lists_one_pane_per_builder_without_the_coordinator(tmp_path: Path) -> None:
    """Each builder resumes its own session id, in name order, from the repo root; the coordinator — reached in VS
    Code, as hub-up states — gets no pane, whether it is named `coordinator` or `<repo>-coordinator`."""
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
    cases = {
        "not-json": "{ nope",
        "not-an-object": json.dumps(["x"]),
        "non-uuid-id": json.dumps({"abc": "dev1"}),
        "uppercase-id": json.dumps({DEV1.upper(): "dev1"}),
        "shell-in-name": json.dumps({DEV1: "dev1; rm -rf ~"}),
        "quote-in-name": json.dumps({DEV1: "dev'1"}),
        "dash-led-name": json.dumps({DEV1: "-dev1"}),
        "name-33-chars": json.dumps({DEV1: "a" * 33}),
        "empty-name": json.dumps({DEV1: ""}),
        "name-not-a-string": json.dumps({DEV1: 7}),
        "no-builders": json.dumps({COORD: "fabrik-lib-coordinator"}),
        # fabrik-lib's registry writer only ever ADDS a row, so a changed session id leaves the old one behind
        "two-ids-one-name": json.dumps({DEV1: "dev1", DEV2: "dev1"}),
        "repeated-key": f'{{"{DEV1}": "dev1", "{DEV2}": "dev2", "{DEV1}": "dev3"}}',
    }
    home = _home(tmp_path)
    for label, text in cases.items():
        repo = _repo(tmp_path / label, text)
        out = _run("--print", str(repo), home=home)
        assert out.returncode == 2, (label, out.stdout, out.stderr)
        assert "pane " not in out.stdout, (label, out.stdout)
        assert out.stderr.strip(), label
    # the length bound is a bound, not a refusal: 32 characters is a name
    ok = _run("--print", str(_repo(tmp_path / "len32", {DEV1: "a" * 32})), home=home)
    assert ok.returncode == 0 and f"pane {'a' * 32} {DEV1} " in ok.stdout, (ok.stdout, ok.stderr)


def test_a_repo_without_a_registry_refuses(tmp_path: Path) -> None:
    """The hub keeps no `.fabrik/session-agents.json` (hub-up holds its list), so `agents-up /opt/fabrik` says so and
    stops; so does a path that is no directory, and a call with no repo at all."""
    home = _home(tmp_path)
    bare = tmp_path / "bare"
    bare.mkdir()
    for args in (("--print", str(bare)), ("--print", str(tmp_path / "missing")), ("--print",), ()):
        out = _run(*args, home=home)
        assert out.returncode == 2, (args, out.stdout, out.stderr)
        assert "pane " not in out.stdout, args
    out = _run("--print", str(bare), home=home)
    assert "session-agents.json" in out.stderr, out.stderr


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
  show-options) cat "$HOME/tmux-owner" 2>/dev/null; exit 0 ;;
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
    assert log[-1] == "attach -t =fabrik-lib", log


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
    for label, owner in (("other", "/opt/elsewhere/fabrik-lib"), ("none", None)):
        home = _tmux_home(tmp_path / label, repo, has=True, owner=owner)
        out = _run(str(repo), home=home)
        assert out.returncode == 2, (label, out.stderr)
        assert "not attaching" in out.stderr, (label, out.stderr)
        assert not any(ln.startswith("attach") for ln in _log(home)), (label, _log(home))
