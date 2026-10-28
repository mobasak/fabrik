"""api_write.py — the API-key WRITE lane (D-1247, D-1248, D-1251, W-174b8543): a cloud-format brief run by headless
`claude -p` on a key with file tools only, in a throwaway local clone; the runner commits the edits and pushes only
`claude/<slug>`. The subject runs as a subprocess against a fake `claude` on PATH that edits files in its working
directory (or tampers with the clone) and a real temporary main checkout whose origin is a local bare repository, so
nothing here reaches a provider or GitHub."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "api_write.py"
KEYS = {
    "can": "sk-ant-api03-" + "C" * 40 + "can0",
    "sarp": "sk-ant-api03-" + "S" * 40 + "sarp",
    "ozgurbasak": "sk-ant-api03-" + "O" * 40 + "ozgb",
}
ENV_NAME = {
    "can": "ANTHROPIC_API_KEY_CAN",
    "sarp": "ANTHROPIC_API_KEY_SARP",
    "ozgurbasak": "ANTHROPIC_API_KEY_OZGURBASAK",
}
FILE_TOOLS = ["Edit", "Glob", "Grep", "Read", "Write"]

FAKE_CLAUDE = """#!{python}
import json, os, subprocess, sys, time
prompt = sys.stdin.read()
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd(), "env_names": sorted(os.environ),
                        "has_git": os.path.lexists(".git"), "ceiling": os.environ.get("GIT_CEILING_DIRECTORIES"),
                        "toplevel": subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                                                   text=True).stdout.strip(),
                        "key": os.environ.get("ANTHROPIC_API_KEY", ""),
                        "headless": os.environ.get("FABRIK_HEADLESS"), "prompt": prompt}}) + "\\n")
if "stream-json" in sys.argv:
    sys.stdout.write(open(os.environ["FAKE_PREFLIGHT"], encoding="utf-8").read())
    sys.exit(1)
if "FAKE_GRANDCHILD" in os.environ and "FAST" not in prompt:  # a process the child starts: a kill reaches it too
    subprocess.Popen([sys.executable, "-c", "import sys, time; time.sleep(4); open(sys.argv[1], 'w').write('x')",
                      os.environ["FAKE_GRANDCHILD"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if "FAKE_READY" in os.environ:  # the grandchild is running: a signal now must reach it
        open(os.environ["FAKE_READY"], "w").close()
time.sleep(0 if "FAST" in prompt else float(os.environ.get("FAKE_SLEEP", "0")))
action = os.environ.get("FAKE_ACTION", "edit")
if action != "none":
    open("made.txt", "w").write(os.environ.get("FAKE_CONTENT", "work\\n"))
if action == "tamper-config":  # a .git of its own in the work tree, config included
    os.makedirs(".git", exist_ok=True)
    with open(".git/config", "a") as f:
        f.write("[core]\\n\\tfsmonitor = touch " + os.environ["FAKE_PWNED"] + "\\n")
if action == "nested-git":  # a .git pointer file deeper in the tree, aimed at another repository
    os.makedirs("sub", exist_ok=True)
    open("sub/.git", "w").write("gitdir: " + os.environ["FAKE_PWNED"] + "\\n")
if action == "tamper-gitdir":  # what only gate code could do: rewrite the run's own git dir config
    with open("../gitdir/config", "a") as f:
        f.write("[core]\\n\\tfsmonitor = touch " + os.environ["FAKE_PWNED"] + "\\n")
if action == "binary-key":  # a key inside a file git treats as binary
    open("blob.bin", "wb").write(b"\\x00\\x01" + os.environ["FAKE_KEY"].encode() + b"\\x00")
is_error = action == "error"
sys.stdout.write(json.dumps({{"type": "result", "subtype": "error_during_execution" if is_error else "success",
                              "is_error": is_error, "result": "done\\nSUBJECT: add made.txt",
                              "total_cost_usd": 0.42, "num_turns": 3}}))
"""


def _git(*a: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(
        ["git", *a], env=env, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture()
def box(tmp_path: Path) -> dict:
    origin = tmp_path / "origin.git"
    _git("init", "-q", "--bare", "-b", "master", str(origin))
    main = tmp_path / "main"
    _git("init", "-q", "-b", "master", str(main))
    (main / "README.md").write_text("hub\n", encoding="utf-8")
    _git("-C", str(main), "add", "README.md")
    _git(
        "-C",
        str(main),
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@t.invalid",
        "commit",
        "-q",
        "-m",
        "init",
    )
    _git("-C", str(main), "remote", "add", "origin", str(origin))
    _git("-C", str(main), "push", "-q", "origin", "master", "master:refs/heads/side")
    state = tmp_path / "state"
    state.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    fake.write_text(FAKE_CLAUDE.format(python=sys.executable), encoding="utf-8")
    fake.chmod(0o755)
    env_file = tmp_path / "dot.env"
    env_file.write_text(
        "".join(f'{ENV_NAME[k]}="{v}"\n' for k, v in KEYS.items()), encoding="utf-8"
    )
    pre = tmp_path / "preflight.jsonl"
    _preflight(pre, FILE_TOOLS)
    out = tmp_path / "out"
    out.mkdir()
    env = {
        **{k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "ROTATE_STATE_DIR": str(state),
        "API_WRITE_RUN_ROOT": str(state / "api-write"),
        "API_CREDIT_ENV_FILE": str(env_file),
        "API_WRITE_MAIN_CHECKOUT": str(main),
        "API_CREDIT_MANAGED_DIR": str(tmp_path / "no-managed"),
        "FAKE_LOG": str(tmp_path / "fake.log"),
        "FAKE_PREFLIGHT": str(pre),
        "FAKE_PWNED": str(tmp_path / "pwned"),
        "SSH_AUTH_SOCK": str(tmp_path / "agent.sock"),
        "GIT_DIR": str(tmp_path / "elsewhere.git"),
    }
    return {"tmp": tmp_path, "main": main, "origin": origin, "state": state, "env": env, "out": out}


def _preflight(path: Path, tools: list[str]) -> None:
    init = {"type": "system", "subtype": "init", "apiKeySource": "none", "tools": tools}
    res = {
        "type": "result",
        "subtype": "success",
        "is_error": True,
        "total_cost_usd": 0,
        "duration_api_ms": 0,
    }
    path.write_text(json.dumps(init) + "\n" + json.dumps(res) + "\n", encoding="utf-8")


def _brief(box: dict, name: str) -> Path:
    p = box["tmp"] / f"{name}.md"
    p.write_text(
        f"BASE: git fetch origin x && git checkout -B claude/{name}. Make the file.",
        encoding="utf-8",
    )
    return p


def _run(box: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "run",
            "--model",
            "haiku",
            "--out-dir",
            str(box["out"]),
            *args,
        ],
        env=box["env"],
        capture_output=True,
        text=True,
        timeout=120,
    )


def _rows(box: dict) -> list[dict]:
    led = box["state"] / "api-credit.jsonl"
    return [json.loads(x) for x in led.read_text().splitlines()] if led.exists() else []


def _calls(box: dict) -> list[dict]:
    log = Path(box["env"]["FAKE_LOG"])
    return [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []


def _runs(box: dict) -> list[dict]:
    return [c for c in _calls(box) if "stream-json" not in c["argv"]]


def _origin(box: dict, ref: str) -> str:
    p = subprocess.run(
        ["git", "--git-dir", str(box["origin"]), "rev-parse", "-q", "--verify", ref],
        capture_output=True,
        text=True,
    )
    return p.stdout.strip()


def test_a_run_edits_in_a_clone_and_the_runner_commits_and_pushes_its_branch(box: dict) -> None:
    """Behaviour 1: the child edits files in a throwaway clone already on claude/<slug> at origin/<base>; the runner
    commits them as one trailered commit and pushes only that branch; ledger, out file, cleanup; main untouched."""
    main_refs = _git("-C", str(box["main"]), "for-each-ref")
    p = _run(
        box,
        "--key",
        "sarp",
        "--slug",
        "t1",
        "--task-file",
        str(_brief(box, "t1")),
        "--base",
        "side",
    )
    assert p.returncode == 0, p.stderr
    sha = _origin(box, "refs/heads/claude/t1")
    assert sha and sha in p.stdout
    body = _git("--git-dir", str(box["origin"]), "log", "-1", "--format=%s%n%b", sha)
    assert body.startswith("add made.txt") and "Agent-Task: t1" in body and "key sarp" in body
    assert _git("--git-dir", str(box["origin"]), "rev-parse", f"{sha}^") == _origin(
        box, "refs/heads/side"
    )
    assert _git("--git-dir", str(box["origin"]), "show", f"{sha}:made.txt") == "work"
    run = _runs(box)
    assert len(run) == 1 and run[0]["key"] == KEYS["sarp"] and Path(run[0]["cwd"]).name == "clone"
    assert (
        run[0]["prompt"].startswith("RUNNER NOTE")
        and "claude/t1 at origin/side" in run[0]["prompt"]
    )
    start, settle = _rows(box)
    assert (start["lane"], start["slug"], start["key"], settle["cost"]) == (
        "write",
        "t1",
        "sarp",
        0.42,
    )
    assert not any((box["state"] / "api-write").iterdir())
    assert (box["out"] / "t1.md").read_text().startswith("done")
    assert _git("-C", str(box["main"]), "for-each-ref") == main_refs


def test_the_child_has_file_tools_only_and_gates_are_exact(box: dict) -> None:
    """Behaviour 2: no gates → no Bash at all; gates → Bash(<gate>) per exact string, no wildcard; dontAsk,
    --restricted, no bypass; the child env drops GIT_* and the SSH agent, strips a credential the runner's own env
    carries, and says FABRIK_HEADLESS=1 even when the runner's env says 0 (the headless guard's delegated
    spawner, tests/test_hooks_headless_guard.py, is graded HERE, on the env the spawn actually received)."""
    box["env"] = {**box["env"], "FABRIK_HEADLESS": "0", "ANTHROPIC_FOO_PROBE": "leak"}
    assert (
        _run(box, "--key", "can", "--slug", "t2", "--task-file", str(_brief(box, "t2"))).returncode
        == 0
    )
    argv = _runs(box)[0]["argv"]
    assert argv[argv.index("--tools") + 1] == "Read,Edit,Write,Glob,Grep"
    assert not any(a.startswith("Bash") for a in argv) and "bypassPermissions" not in argv
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk" and "--restricted" in argv
    names = _runs(box)[0]["env_names"]
    assert "SSH_AUTH_SOCK" not in names and "ANTHROPIC_FOO_PROBE" not in names
    assert _runs(box)[0]["headless"] == "1"
    assert [n for n in names if n.startswith("GIT_")] == ["GIT_CEILING_DIRECTORIES"]
    assert _runs(box)[0]["ceiling"] == str(Path(_runs(box)[0]["cwd"]).parent)
    _preflight(Path(box["env"]["FAKE_PREFLIGHT"]), FILE_TOOLS + ["Bash"])
    gate = "python3 -m pytest -q tests/test_x.py"
    assert (
        _run(
            box,
            "--key",
            "can",
            "--slug",
            "t2b",
            "--task-file",
            str(_brief(box, "t2b")),
            "--gate",
            gate,
        ).returncode
        == 0
    )
    argv = _runs(box)[1]["argv"]
    allowed = argv[argv.index("--allowedTools") + 1 : argv.index("--no-session-persistence")]
    assert [a for a in allowed if a.startswith("Bash")] == [f"Bash({gate})"]


@pytest.mark.parametrize(
    "gate", ["python3 -m pytest *", "pytest; rm -rf /", "a && b", "x $(y)", "a\nb", "echo `id`"]
)
def test_a_gate_with_shell_syntax_or_a_glob_is_refused(box: dict, gate: str) -> None:
    p = _run(
        box, "--key", "can", "--slug", "t3", "--task-file", str(_brief(box, "t3")), "--gate", gate
    )
    assert p.returncode == 2 and _rows(box) == [] and _calls(box) == []


@pytest.mark.parametrize(
    ("action", "where"), [("tamper-config", ".git"), ("nested-git", "sub/.git")]
)
def test_a_git_entry_the_child_leaves_is_never_trusted(box: dict, action: str, where: str) -> None:
    """Behaviour 3: the child starts with no .git in its work tree (the git dir sits outside it); a .git it creates
    anywhere — a config with fsmonitor, or a pointer file aimed elsewhere — gets no commit, no push, and the injected
    command never runs."""
    box["env"]["FAKE_ACTION"] = action
    p = _run(box, "--key", "can", "--slug", "t4", "--task-file", str(_brief(box, "t4")))
    assert _runs(box)[0]["has_git"] is False
    assert p.returncode == 1 and f"left a git entry at {where}" in p.stdout
    assert not _origin(box, "refs/heads/claude/t4") and not Path(box["env"]["FAKE_PWNED"]).exists()


def test_the_childs_git_does_not_climb_into_an_enclosing_repository(box: dict) -> None:
    """Behaviour 3c: with the state directory inside some other repository, a git run from the child's work tree finds
    no repository (discovery stops at the run directory) instead of that enclosing one."""
    outer = box["tmp"] / "outer"
    _git("init", "-q", str(outer))
    box["env"]["ROTATE_STATE_DIR"] = str(outer / "state")
    box["env"]["API_WRITE_RUN_ROOT"] = str(outer / "state" / "api-write")
    assert (
        _run(
            box, "--key", "can", "--slug", "t4c", "--task-file", str(_brief(box, "t4c"))
        ).returncode
        == 0
    )
    assert _runs(box)[0]["toplevel"] == ""


def test_a_changed_git_dir_config_is_never_trusted(box: dict) -> None:
    """Behaviour 3b: a changed config in the run's own git dir (only gate code could write it) refuses before any
    runner git, so its injected command never runs."""
    box["env"]["FAKE_ACTION"] = "tamper-gitdir"
    p = _run(box, "--key", "can", "--slug", "t4b", "--task-file", str(_brief(box, "t4b")))
    assert p.returncode == 1 and "git config changed" in p.stdout
    assert not _origin(box, "refs/heads/claude/t4b") and not Path(box["env"]["FAKE_PWNED"]).exists()


@pytest.mark.parametrize("action", ["edit", "binary-key"])
def test_a_key_in_the_diff_refuses_the_push(box: dict, action: str) -> None:
    """Behaviour 4: the runner scans the commit for the key values and the sk-ant- pattern before pushing — a text
    file, and a file git treats as binary."""
    box["env"].update(
        FAKE_ACTION=action,
        # binary-key: only the binary file holds a key, so a text-only scan would pass it
        FAKE_CONTENT=KEYS["ozgurbasak"] + "\n" if action == "edit" else "no key here\n",
        FAKE_KEY=KEYS["sarp"],
    )
    p = _run(box, "--key", "can", "--slug", "t5", "--task-file", str(_brief(box, "t5")))
    assert p.returncode == 1 and "holds a key value" in p.stdout
    assert not _origin(box, "refs/heads/claude/t5")


def test_an_existing_remote_branch_or_a_missing_base_refuses_before_spending(box: dict) -> None:
    _git("-C", str(box["main"]), "push", "-q", "origin", "master:refs/heads/claude/t6")
    p = _run(box, "--key", "can", "--slug", "t6", "--task-file", str(_brief(box, "t6")))
    assert p.returncode == 2 and "already has claude/t6" in p.stderr
    p = _run(
        box,
        "--key",
        "can",
        "--slug",
        "t6b",
        "--task-file",
        str(_brief(box, "t6b")),
        "--base",
        "nope",
    )
    assert p.returncode == 2 and "no branch 'nope'" in p.stderr
    assert _rows(box) == [] and _calls(box) == []
    assert (
        _run(
            box,
            "--key",
            "can",
            "--slug",
            "t6",
            "--task-file",
            str(_brief(box, "t6")),
            "--force-new",
        ).returncode
        == 0
    )


def test_a_batch_runs_in_parallel_and_pick_spreads_the_keys(box: dict) -> None:
    batch = box["tmp"] / "batch.json"
    batch.write_text(
        json.dumps(
            [{"slug": s, "task_file": str(_brief(box, s)), "files": []} for s in ("a1", "a2", "a3")]
        ),
        encoding="utf-8",
    )
    p = _run(box, "--pick", "--batch", str(batch), "--jobs", "3", "--budget", "50")
    assert p.returncode == 0, p.stderr
    starts = [r for r in _rows(box) if r["kind"] == "start"]
    assert sorted(r["key"] for r in starts) == sorted(KEYS)
    assert all(_origin(box, f"refs/heads/claude/{s}") for s in ("a1", "a2", "a3"))


def test_a_child_error_settles_and_pushes_nothing(box: dict) -> None:
    box["env"]["FAKE_ACTION"] = "error"
    p = _run(box, "--key", "can", "--slug", "t8", "--task-file", str(_brief(box, "t8")))
    assert (
        p.returncode == 1 and "child error" in p.stdout and not _origin(box, "refs/heads/claude/t8")
    )
    settle = [r for r in _rows(box) if r["kind"] == "settle"]
    assert settle and settle[0]["is_error"] is True and settle[0]["cost"] == 0.42


def test_no_edits_pushes_nothing(box: dict) -> None:
    box["env"]["FAKE_ACTION"] = "none"
    p = _run(box, "--key", "can", "--slug", "t9", "--task-file", str(_brief(box, "t9")))
    assert (
        p.returncode == 1
        and "nothing pushed" in p.stdout
        and not _origin(box, "refs/heads/claude/t9")
    )


def test_the_preflight_must_report_the_child_tools(box: dict) -> None:
    _preflight(Path(box["env"]["FAKE_PREFLIGHT"]), FILE_TOOLS + ["Bash"])
    p = _run(box, "--key", "can", "--slug", "t10", "--task-file", str(_brief(box, "t10")))
    assert p.returncode == 2 and "pre-flight refused" in p.stderr and _rows(box) == []


def test_a_timeout_kills_the_group_settles_and_pushes_nothing(box: dict) -> None:
    marker = box["tmp"] / "grandchild-alive"
    box["env"].update(FAKE_SLEEP="30", FAKE_GRANDCHILD=str(marker))
    p = _run(
        box,
        "--key",
        "can",
        "--slug",
        "t11",
        "--task-file",
        str(_brief(box, "t11")),
        "--timeout",
        "2",
    )
    assert (
        p.returncode == 1 and "timed out" in p.stdout and not _origin(box, "refs/heads/claude/t11")
    )
    settle = [r for r in _rows(box) if r["kind"] == "settle"]
    assert settle and settle[0]["subtype"] == "timeout" and settle[0]["cost"] is None
    assert not any((box["state"] / "api-write").iterdir())
    time.sleep(
        5
    )  # past the grandchild's 4 s: had it survived the kill, its marker would be on disk now
    assert not marker.exists()


def test_batch_and_slug_together_or_an_inline_task_refuse(box: dict) -> None:
    batch = box["tmp"] / "b.json"
    batch.write_text(
        json.dumps([{"slug": "b1", "task_file": str(_brief(box, "b1"))}]), encoding="utf-8"
    )
    p = _run(
        box,
        "--key",
        "can",
        "--batch",
        str(batch),
        "--slug",
        "b2",
        "--task-file",
        str(_brief(box, "b2")),
    )
    assert p.returncode == 2 and "not both" in p.stderr
    batch.write_text(json.dumps([{"slug": "b3", "task": "do it"}]), encoding="utf-8")
    p = _run(box, "--key", "can", "--batch", str(batch))
    assert p.returncode == 2 and "no inline task" in p.stderr and _calls(box) == []


@pytest.mark.parametrize(
    "under",
    [
        ".claude/state/api-write",
        ".claude-fleet/can/api-write",
        "repo/.claude/x",
        ".Claude/x",
        "link/api-write",
    ],
)
def test_a_run_root_under_a_claude_dir_refuses_before_anything(box: dict, under: str) -> None:
    """Claude Code denies every Write/Edit under ~/.claude as a settings path, so a child cloned there reads and
    plans but changes nothing (the first live runs, W-174b8543): refused before any spend — before the key file is
    even read (it is missing here, so a later refusal would name it instead). `link` is a symlink into .claude."""
    (box["tmp"] / ".claude" / "state").mkdir(parents=True)
    (box["tmp"] / "link").symlink_to(box["tmp"] / ".claude" / "state")
    box["env"] = {
        **box["env"],
        "API_WRITE_RUN_ROOT": str(box["tmp"] / under),
        "API_CREDIT_ENV_FILE": str(box["tmp"] / "missing.env"),
    }
    p = _run(box, "--key", "can", "--slug", "t9", "--task-file", str(_brief(box, "t9")))
    assert p.returncode == 2 and "sits under a .claude directory" in p.stderr
    assert _rows(box) == [] and _calls(box) == []


@pytest.mark.parametrize("raw", ["~/plain-api-write", "rel/x", " ", "~nosuchuser-zz9/x"])
def test_a_relative_run_root_is_refused_or_expanded(box: dict, raw: str) -> None:
    """A relative value would land under the launch directory; `~` is expanded, the rest refused before any spend."""
    home = box["tmp"] / "home"
    box["env"] = {**box["env"], "API_WRITE_RUN_ROOT": raw, "HOME": str(home)}
    p = _run(box, "--key", "can", "--slug", "t7", "--task-file", str(_brief(box, "t7")))
    if raw.startswith("~nosuchuser"):  # an unknown user: a clean refusal, never a traceback
        assert p.returncode == 2 and "cannot expand ~" in p.stderr and "Traceback" not in p.stderr
        assert _calls(box) == []
    elif raw.startswith("~"):
        assert p.returncode == 0
        assert Path(_runs(box)[0]["cwd"]).is_relative_to(home / "plain-api-write")
    elif raw.strip():
        assert p.returncode == 2 and "is not an absolute path" in p.stderr and _calls(box) == []
    else:  # blank means unset: the default root
        assert p.returncode == 0
        assert Path(_runs(box)[0]["cwd"]).is_relative_to(home / ".cache" / "fabrik" / "api-write")


def test_the_default_timeout_outlasts_a_long_round() -> None:
    """A timed-out run pushes nothing, and a re-ledger round runs past an hour (W-15bb59ea)."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import api_write

    assert api_write.DEFAULT_TIMEOUT_S == 10800


def test_the_default_run_root_is_the_users_cache_not_claude_state(box: dict) -> None:
    home = box["tmp"] / "home"
    env = {k: v for k, v in box["env"].items() if k != "API_WRITE_RUN_ROOT"}
    box["env"] = {**env, "HOME": str(home)}
    assert (
        _run(box, "--key", "can", "--slug", "t8", "--task-file", str(_brief(box, "t8"))).returncode
        == 0
    )
    cwd = Path(_runs(box)[0]["cwd"])
    assert cwd.is_relative_to(home / ".cache" / "fabrik" / "api-write")
    assert not any(part.startswith(".claude") for part in cwd.parts)


@pytest.mark.parametrize("bad", ["../x", "A", "a b", "x.lock", "x."])
def test_a_malformed_slug_refuses_before_anything(box: dict, bad: str) -> None:
    p = _run(box, "--key", "can", "--slug", bad, "--task-file", str(_brief(box, "ok")))
    assert p.returncode == 2 and _rows(box) == [] and _calls(box) == []


def _module():
    sys.path.insert(0, str(ROOT / "scripts"))
    import api_write

    return api_write


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGHUP, signal.SIGINT])
def test_a_group_signal_kills_settles_and_names_every_job(box: dict, sig: signal.Signals) -> None:
    """W-d077095a, Behaviours 1-3. A stopped Claude Code background task gets SIGTERM to its whole process group and
    SIGKILL about 1.4 s later (2.1.311, measured); a closed terminal sends SIGHUP and Ctrl-C SIGINT. The children sit
    in their own sessions, so the signal never reaches them: the runner must kill them, settle the started run as
    interrupted, start nothing queued, push nothing, remove the run directory and name every job — in a FILE sink
    (block-buffered unless the runner says otherwise), where the line of a job that finished earlier is already
    written while the runner still runs, so a SIGKILL cannot take it. f1 finishes at once (FAST), s1 sleeps, s2
    waits in the queue."""
    marker = box["tmp"] / "grandchild-alive"
    ready = box["tmp"] / "grandchild-started"
    box["env"].update(FAKE_SLEEP="30", FAKE_GRANDCHILD=str(marker), FAKE_READY=str(ready))
    fast = _brief(box, "f1")
    fast.write_text(fast.read_text(encoding="utf-8") + " FAST", encoding="utf-8")
    batch = box["tmp"] / "batch.json"
    batch.write_text(
        json.dumps(
            [{"slug": "f1", "task_file": str(fast)}]
            + [{"slug": s, "task_file": str(_brief(box, s))} for s in ("s1", "s2")]
        ),
        encoding="utf-8",
    )
    sink = box["tmp"] / "runner.log"
    with open(sink, "w", encoding="utf-8") as fh:
        p = subprocess.Popen(
            [
                sys.executable,
                str(SCRIPT),
                "run",
                "--model",
                "haiku",
                "--out-dir",
                str(box["out"]),
                "--key",
                "can",
                "--batch",
                str(batch),
                "--jobs",
                "1",
            ],
            env=box["env"],
            stdout=fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    try:
        deadline = time.monotonic() + 60
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ready.exists(), "s1's child never launched its grandchild"
        deadline = (
            time.monotonic() + 10
        )  # f1's line is printed as its job returns, beside s1's start
        while (
            "api_write: f1 " not in sink.read_text(encoding="utf-8") and time.monotonic() < deadline
        ):
            time.sleep(0.05)
        early = sink.read_text(encoding="utf-8")
        assert "api_write: f1 " in early, f"f1's line is still in the runner's buffer: {early!r}"
        os.killpg(p.pid, sig)  # the harness signals the whole group, never one pid
        try:
            rc = p.wait(timeout=1.4)
        except subprocess.TimeoutExpired:
            rc = None
    finally:
        try:
            os.killpg(
                p.pid, signal.SIGKILL
            )  # the harness's follow-up: whatever is still in the group dies
        except ProcessLookupError:
            pass
        p.wait(timeout=10)
    log = sink.read_text(encoding="utf-8")
    assert rc == 128 + sig, f"rc {rc} (None = still running when the SIGKILL came); log:\n{log}"
    rows = _rows(box)
    starts = [r for r in rows if r["kind"] == "start"]
    settles = [r for r in rows if r["kind"] == "settle"]
    assert len(starts) == 2 and len(settles) == 2, rows
    s1 = next(s for s in settles if s["run"] == starts[1]["run"])
    assert s1["subtype"] == "interrupted" and s1["source"] == "run"
    assert _origin(box, "refs/heads/claude/f1")  # finished before the signal: pushed as normal
    assert f"api_write: s1 run {starts[1]['run']}" in log and f"interrupted by {sig.name}" in log, (
        log
    )
    assert "s2: not started: runner interrupted" in log, log
    assert not _origin(box, "refs/heads/claude/s1") and not _origin(box, "refs/heads/claude/s2")
    assert not any((box["state"] / "api-write").iterdir())
    note = (box["out"] / "s1.md").read_text(encoding="utf-8")
    assert f"interrupted by {sig.name}" in note and starts[1]["run"] in note
    assert len(_runs(box)) == 2  # the queued job's child never ran
    time.sleep(5)  # past the grandchild's 4 s: a survivor of the kill would have written its marker
    assert not marker.exists()


@pytest.fixture()
def stopped():
    """The module's stop state, reset around an in-process test so it never leaks into another."""
    aw = _module()
    aw._reset_stop()
    yield aw
    aw._reset_stop()


def test_a_child_started_after_the_signal_is_killed_at_once(stopped) -> None:
    """Behaviour 4: a child the worker starts after the handler's snapshot is killed at its registration."""
    stopped._on_signal(signal.SIGTERM, None)
    t = time.monotonic()
    rc, _out, _err, killed = stopped.run_child(
        [sys.executable, "-c", "import time; time.sleep(30)"], "", Path.cwd(), dict(os.environ), 60
    )
    assert killed and rc == -signal.SIGKILL and time.monotonic() - t < 5


def test_the_handler_survives_a_reaped_child(stopped) -> None:
    """Behaviour 5: a child reaped but not yet dropped from the registry has no group left; killpg raises
    ProcessLookupError, which must not escape the handler (it would abort the runner with no job line)."""
    gone = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    gone.wait()
    gone.returncode = None  # what the registry holds in the window between the reap and the drop
    live = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True
    )
    stopped._LIVE.update({gone.pid: gone, live.pid: live})
    try:
        stopped._on_signal(signal.SIGTERM, None)
        assert live.wait(timeout=5) == -signal.SIGKILL
    finally:
        stopped._LIVE.clear()
        if live.poll() is None:
            live.kill()


def test_a_child_done_before_the_signal_still_pushes(box: dict, stopped, monkeypatch) -> None:
    """Behaviour 6: a child that exited on its own just before the signal is paid-for, finished work — it settles
    with its cost, commits and pushes; only a child the HANDLER killed is interrupted."""
    for k, v in box["env"].items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("GIT_DIR")
    monkeypatch.setattr(stopped.ac, "preflight", lambda *a, **k: None)
    done = json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "SUBJECT: finished before the signal",
            "total_cost_usd": 0.5,
            "num_turns": 2,
        }
    )

    def finished_then_signalled(argv, prompt, cwd, env, timeout):
        (cwd / "made.txt").write_text("work\n", encoding="utf-8")
        stopped._on_signal(
            signal.SIGTERM, None
        )  # the signal lands after the child exited on its own
        return 0, done, "", False

    monkeypatch.setattr(stopped, "run_child", finished_then_signalled)
    a = argparse.Namespace(
        model="haiku",
        force_new=False,
        pick=False,
        key="can",
        budget=5.0,
        timeout=60,
        max_turns=5,
        out_dir=str(box["out"]),
    )
    job = {"slug": "d1", "prompt": "make it", "base": "master", "gates": []}
    keys = stopped.ac.read_keys(stopped.ac.env_file())
    r = stopped.one(job, a, keys, box["main"], str(box["origin"]))
    assert r["pushed"] and r.get("error") is None, r
    assert _origin(box, "refs/heads/claude/d1") == r["pushed"]
    settle = [x for x in _rows(box) if x["kind"] == "settle"]
    assert settle and settle[0]["cost"] == 0.5 and settle[0]["subtype"] == "success"


def _zombie(pid: int) -> bool:
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] == "Z"
    except OSError:
        return False


def test_a_child_that_exited_before_the_kill_is_not_counted_killed(stopped, monkeypatch) -> None:
    """Review pass 1 (A-S1): the handler marks every registered child it signals, and a child that had already exited
    (not yet reaped) is marked too — its work is finished and paid for, so the real run_child must not report it
    killed. The stop is made to land exactly in that window: after the child is a zombie, before communicate reaps."""
    real = subprocess.Popen.communicate

    def stop_lands_after_the_exit(self, *args, **kwargs):
        deadline = time.monotonic() + 10
        while not _zombie(self.pid) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert _zombie(self.pid), "the child never exited"
        stopped._on_signal(signal.SIGTERM, None)
        return real(self, *args, **kwargs)

    monkeypatch.setattr(subprocess.Popen, "communicate", stop_lands_after_the_exit)
    rc, _out, _err, killed = stopped.run_child(
        [sys.executable, "-c", "pass"], "", Path.cwd(), dict(os.environ), 60
    )
    assert rc == 0 and killed is False


@pytest.mark.parametrize("where", ["clone", "preflight"])
def test_a_stop_during_the_set_up_refuses_before_any_spend(
    box: dict, stopped, monkeypatch, where: str
) -> None:
    """Review pass 1 (B-S2): a stop landing while a job clones or runs its pre-flight must leave no start row and
    report not started. Two guards carry it, each graded alone: the stop check before `reserve` (the clone case: the
    set-up succeeds) and the refusal-under-stop mapping (the pre-flight case: its child dies with the group, so the
    pre-flight refuses)."""
    for k, v in box["env"].items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("GIT_DIR")
    real_clone = stopped.make_clone

    def clone_then_stop(*args, **kwargs):
        out = real_clone(*args, **kwargs)
        if where == "clone":
            stopped._on_signal(signal.SIGTERM, None)
        return out

    def preflight(*args, **kwargs):
        if where == "preflight":
            stopped._on_signal(signal.SIGTERM, None)
            raise stopped.ac.RefusalError(2, "pre-flight refused: its child died (rc -15)")

    monkeypatch.setattr(stopped, "make_clone", clone_then_stop)
    monkeypatch.setattr(stopped.ac, "preflight", preflight)
    a = argparse.Namespace(
        model="haiku",
        force_new=False,
        pick=False,
        key="can",
        budget=5.0,
        timeout=60,
        max_turns=5,
        out_dir=str(box["out"]),
    )
    job = {"slug": "u1", "prompt": "make it", "base": "master", "gates": []}
    keys = stopped.ac.read_keys(stopped.ac.env_file())
    with pytest.raises(stopped.ac.RefusalError, match="not started: runner interrupted"):
        stopped.one(job, a, keys, box["main"], str(box["origin"]))
    assert _rows(box) == [] and _runs(box) == []


def test_git_runs_in_its_own_session(stopped, tmp_path: Path, monkeypatch) -> None:
    """Review pass 1 (B-S3): the runner's git runs in its own session, so the harness's signal to the runner's group
    never cuts a push of finished work midway. Observed through `git()` itself with a git on PATH that records its
    session id."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    seen = tmp_path / "sid"
    fake = bin_dir / "git"
    fake.write_text(
        f"#!{sys.executable}\nimport os\nopen({str(seen)!r}, 'w').write(str(os.getsid(0)))\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    stopped.git("version")
    assert int(seen.read_text()) != os.getsid(0)


def test_a_failed_wait_never_leaves_a_paid_child_running(stopped, monkeypatch) -> None:
    """Review pass 1 (A-S6): when communicate raises anything but a timeout, the child is dropped from the registry —
    a stop could no longer reach it, and it would spend on — so run_child kills its group before re-raising."""
    started: list[subprocess.Popen] = []

    def broken(self, *args, **kwargs):
        started.append(self)
        raise RuntimeError("the wait failed")

    monkeypatch.setattr(subprocess.Popen, "communicate", broken)
    with pytest.raises(RuntimeError):
        stopped.run_child(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            "",
            Path.cwd(),
            dict(os.environ),
            60,
        )
    # reaped by run_child itself (closing pass, NEW-2): no wait here, a zombie would leave returncode None
    assert started[0].returncode == -signal.SIGKILL


def test_a_hung_up_terminal_still_removes_the_runs_set_aside(box: dict) -> None:
    """Review pass 1 (A-S5): after SIGHUP the terminal is gone and a print raises; the run directories set aside on
    the stop are removed all the same (here the runner's stdout is a pipe nobody reads any more)."""
    box["env"].update(FAKE_SLEEP="30")
    p = subprocess.Popen(
        [
            sys.executable,
            str(SCRIPT),
            "run",
            "--model",
            "haiku",
            "--out-dir",
            str(box["out"]),
            "--key",
            "can",
            "--slug",
            "h1",
            "--task-file",
            str(_brief(box, "h1")),
        ],
        env=box["env"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        p.stdout.close()  # the reader is gone: the runner's next print raises BrokenPipeError
        deadline = time.monotonic() + 60
        while not _runs(box) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert _runs(box), "the child never started"
        os.killpg(p.pid, signal.SIGHUP)
        p.wait(timeout=10)
    finally:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        p.wait(timeout=10)
    settles = [r for r in _rows(box) if r["kind"] == "settle"]
    assert settles and settles[0]["subtype"] == "interrupted"
    assert not any((box["state"] / "api-write").iterdir())
