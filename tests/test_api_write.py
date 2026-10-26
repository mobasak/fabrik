"""api_write.py — the API-key WRITE lane (D-1247, W-174b8543): a cloud-format brief run by headless `claude -p` on a key,
in a throwaway shared clone, pushing only `claude/<slug>`. The subject runs as a subprocess against a fake `claude` on
PATH that acts on its working directory (commits on the slug branch, or tries to push master) and a real temporary
main checkout whose origin is a local bare repository, so nothing here reaches a provider or GitHub."""

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
WRITE_TOOLS = ["Bash", "Edit", "Glob", "Grep", "Read", "Write"]

FAKE_CLAUDE = """#!{python}
import json, os, subprocess, sys, time
log = os.environ["FAKE_LOG"]
with open(log, "a", encoding="utf-8") as f:
    f.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd(),
                        "key": os.environ.get("ANTHROPIC_API_KEY", "")}}) + "\\n")
if "stream-json" in sys.argv:
    sys.stdout.write(open(os.environ["FAKE_PREFLIGHT"], encoding="utf-8").read())
    sys.exit(1)
sys.stdin.read()
if "FAKE_GRANDCHILD" in os.environ:  # a process the child starts, as Bash does: a timeout must kill it too
    subprocess.Popen([sys.executable, "-c", "import sys, time; time.sleep(4); open(sys.argv[1], 'w').write('alive')",
                      os.environ["FAKE_GRANDCHILD"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(float(os.environ.get("FAKE_SLEEP", "0")))
slug = os.environ["FAKE_SLUG"] if "FAKE_SLUG" in os.environ else None
action = os.environ.get("FAKE_ACTION", "commit")
def g(*a):
    return subprocess.run(["git", *a], capture_output=True, text=True)
if action in ("commit", "push-master"):
    p = [x for x in sys.argv if x.startswith("You are a metered")][0]
    slug = p.split("branch claude/")[1].split(" ")[0]
    g("checkout", "-q", "-B", "claude/" + slug, "origin/master")
    open("made-by-" + slug + ".txt", "w").write("x\\n")
    g("add", "made-by-" + slug + ".txt")
    g("-c", "user.name=w", "-c", "user.email=w@w.invalid", "commit", "-q", "-m", "work " + slug)
if action == "push-master":
    r = g("push", "origin", "HEAD:refs/heads/master")
    open(os.environ["FAKE_PUSH_LOG"], "a").write(str(r.returncode) + " " + r.stderr + "\\n")
sys.stdout.write(json.dumps({{"type": "result", "subtype": "success", "is_error": False,
                              "result": "done " + str(slug), "total_cost_usd": 0.42, "num_turns": 3}}))
"""


def _git(*a: str, cwd: Path | None = None) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(
        ["git", *a], cwd=cwd, env=env, capture_output=True, text=True, check=True
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
    _git("-C", str(main), "push", "-q", "origin", "master")
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
    init = {"type": "system", "subtype": "init", "apiKeySource": "none", "tools": WRITE_TOOLS}
    res = {
        "type": "result",
        "subtype": "success",
        "is_error": True,
        "total_cost_usd": 0,
        "duration_api_ms": 0,
    }
    pre.write_text(json.dumps(init) + "\n" + json.dumps(res) + "\n", encoding="utf-8")
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
        "FAKE_PUSH_LOG": str(tmp_path / "push.log"),
    }
    return {"tmp": tmp_path, "main": main, "origin": origin, "state": state, "env": env, "out": out}


def _brief(box: dict, name: str) -> Path:
    p = box["tmp"] / f"{name}.md"
    p.write_text(f"BASE: work on claude/{name}. Make the file.", encoding="utf-8")
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


def _origin_ref(box: dict, ref: str) -> str:
    p = subprocess.run(
        ["git", "--git-dir", str(box["origin"]), "rev-parse", "-q", "--verify", ref],
        capture_output=True,
        text=True,
    )
    return p.stdout.strip()


def test_a_run_commits_in_a_clone_and_pushes_only_its_branch(box: dict) -> None:
    """Behaviour 1: the brief runs in a throwaway clone, its claude/<slug> commit reaches origin, the ledger carries a
    write-lane start and a costed settle, the run directory is gone and the main checkout is untouched."""
    main_head = _git("-C", str(box["main"]), "rev-parse", "HEAD")
    main_refs = _git("-C", str(box["main"]), "for-each-ref")
    p = _run(box, "--key", "sarp", "--slug", "t1", "--task-file", str(_brief(box, "t1")))
    assert p.returncode == 0, p.stderr
    sha = _origin_ref(box, "refs/heads/claude/t1")
    assert sha and f"pushed {sha}" in p.stdout
    run = [c for c in _calls(box) if "stream-json" not in c["argv"]]
    assert len(run) == 1 and run[0]["key"] == KEYS["sarp"]
    assert Path(run[0]["cwd"]).name == "clone" and Path(run[0]["cwd"]) != box["main"]
    assert "--safe-mode" in run[0]["argv"] and ",".join(sorted(WRITE_TOOLS)) in run[0]["argv"]
    start, settle = _rows(box)
    assert (start["kind"], start["lane"], start["slug"], start["key"]) == (
        "start",
        "write",
        "t1",
        "sarp",
    )
    assert (settle["kind"], settle["cost"]) == ("settle", 0.42)
    assert not any((box["state"] / "api-write").iterdir())
    assert (box["out"] / "t1.md").read_text().strip() == "done t1"
    assert _git("-C", str(box["main"]), "rev-parse", "HEAD") == main_head
    assert _git("-C", str(box["main"]), "for-each-ref") == main_refs
    assert _git("-C", str(box["main"]), "worktree", "list").count("\n") == 0


def test_the_child_cannot_push_another_branch(box: dict) -> None:
    """Behaviour 2: the clone's pre-push hook refuses any ref but claude/<slug>; origin master does not move."""
    before = _origin_ref(box, "refs/heads/master")
    box["env"]["FAKE_ACTION"] = "push-master"
    p = _run(box, "--key", "can", "--slug", "t2", "--task-file", str(_brief(box, "t2")))
    assert p.returncode == 0, p.stderr
    log = Path(box["env"]["FAKE_PUSH_LOG"]).read_text()
    assert log.startswith("1 ") and "only refs/heads/claude/t2" in log
    assert _origin_ref(box, "refs/heads/master") == before
    assert _origin_ref(box, "refs/heads/claude/t2")


def test_an_existing_remote_branch_refuses_before_spending(box: dict) -> None:
    """Behaviour 3: origin already holding claude/<slug> refuses with no start row and no claude call, unless
    --force-new."""
    _git("-C", str(box["main"]), "push", "-q", "origin", "master:refs/heads/claude/t3")
    p = _run(box, "--key", "can", "--slug", "t3", "--task-file", str(_brief(box, "t3")))
    assert p.returncode == 2 and "already has claude/t3" in p.stderr
    assert _rows(box) == [] and _calls(box) == []
    p = _run(
        box, "--key", "can", "--slug", "t3", "--task-file", str(_brief(box, "t3")), "--force-new"
    )
    assert p.returncode == 0, p.stderr


def test_a_batch_runs_in_parallel_and_pick_spreads_the_keys(box: dict) -> None:
    """Behaviour 4: a --batch runs every entry; under --pick each job reserves the key with the most room at its own
    start, so three jobs land on three keys."""
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
    assert sorted(r["slug"] for r in starts) == ["a1", "a2", "a3"]
    assert sorted(r["key"] for r in starts) == sorted(KEYS)
    assert all(_origin_ref(box, f"refs/heads/claude/{s}") for s in ("a1", "a2", "a3"))


def test_the_preflight_must_report_the_write_tools(box: dict) -> None:
    """Behaviour 5: the keyless pre-flight runs this lane's argv and refuses when the tool set is not WRITE_TOOLS."""
    pre = Path(box["env"]["FAKE_PREFLIGHT"])
    pre.write_text(pre.read_text().replace('"Write"', '"WebFetch"'), encoding="utf-8")
    p = _run(box, "--key", "can", "--slug", "t5", "--task-file", str(_brief(box, "t5")))
    assert p.returncode == 2 and "pre-flight refused" in p.stderr
    assert _rows(box) == []


def test_a_timeout_settles_as_provisioned_and_cleans_up(box: dict) -> None:
    """Behaviour 6: a child past --timeout is killed with its process group, settled as a timeout with no cost,
    reported as an error, and its run directory removed."""
    marker = box["tmp"] / "grandchild-alive"
    box["env"]["FAKE_SLEEP"] = "30"
    box["env"]["FAKE_GRANDCHILD"] = str(marker)
    p = _run(
        box, "--key", "can", "--slug", "t6", "--task-file", str(_brief(box, "t6")), "--timeout", "2"
    )
    assert p.returncode == 1 and "timed out" in p.stdout
    settle = [r for r in _rows(box) if r["kind"] == "settle"]
    assert settle and settle[0]["subtype"] == "timeout" and settle[0]["cost"] is None
    assert not any((box["state"] / "api-write").iterdir())
    time.sleep(
        5
    )  # past the grandchild's 4 s: had it survived the kill, its marker would be on disk now
    assert not marker.exists()


@pytest.mark.parametrize("bad", ["../x", "A", "", "a b"])
def test_a_malformed_slug_refuses_before_anything(box: dict, bad: str) -> None:
    p = _run(box, "--key", "can", "--slug", bad, "--task-file", str(_brief(box, "ok")))
    assert p.returncode == 2 and _rows(box) == [] and _calls(box) == []
