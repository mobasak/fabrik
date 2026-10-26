"""api_write.py — the API-key WRITE lane (D-1247, D-1248, D-1251, W-174b8543): a cloud-format brief run by headless
`claude -p` on a key with file tools only, in a throwaway local clone; the runner commits the edits and pushes only
`claude/<slug>`. The subject runs as a subprocess against a fake `claude` on PATH that edits files in its working
directory (or tampers with the clone) and a real temporary main checkout whose origin is a local bare repository, so
nothing here reaches a provider or GitHub."""

from __future__ import annotations

import json
import os
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
if "FAKE_GRANDCHILD" in os.environ:  # a process the child starts: a timeout must kill it too
    subprocess.Popen([sys.executable, "-c", "import sys, time; time.sleep(4); open(sys.argv[1], 'w').write('x')",
                      os.environ["FAKE_GRANDCHILD"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(float(os.environ.get("FAKE_SLEEP", "0")))
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


@pytest.mark.parametrize("bad", ["../x", "A", "a b", "x.lock", "x."])
def test_a_malformed_slug_refuses_before_anything(box: dict, bad: str) -> None:
    p = _run(box, "--key", "can", "--slug", bad, "--task-file", str(_brief(box, "ok")))
    assert p.returncode == 2 and _rows(box) == [] and _calls(box) == []
