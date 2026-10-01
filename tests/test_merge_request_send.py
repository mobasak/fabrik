"""Behavior-contract tests for `merge_request.py request` (plan 2026-09-30-plan-1 T02).

Spec: docs/superpowers/specs/2026-09-30-merge-request-loop-design.md § The delta 1-4, 8 and
§ Validation V1, V2.

Everything is a FIXTURE under tmp_path: a bare repo is the remote (no network), the main checkout
and its LINKED worktree are real git repos, the mail store is ``FABRIK_MAIL_ROOT``, the doorbell's
session registry and proc tree are ``FABRIK_SESSIONS_ROOT``/``FABRIK_PROC_ROOT``, the owner resolver
is a stub (``FABRIK_DECISIONS_PY``) except where the REAL resolver's exit 3 is the point, and HOME is
a scratch dir. The script runs as a subprocess, exactly as an agent runs it.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
SCRIPT = SCRIPTS / "merge_request.py"
REAL_DECISIONS = SCRIPTS / "decisions.py"
BTIME = 1_700_000_000
CLK = os.sysconf("SC_CLK_TCK")


def test_merge_request_and_mail_are_this_worktrees_copies():
    """W-83ff5917: the suite exercises THIS tree's scripts, never the main checkout's."""
    spec = importlib.util.spec_from_file_location("merge_request_t02", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert Path(mod.__file__).resolve() == SCRIPT
    assert mod.MAIL_PY == SCRIPTS / "mail.py"
    assert mod.WORK_PY == SCRIPTS / "work.py"


def _git(cwd: Path, env: dict, *args: str) -> str:
    res = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    assert res.returncode == 0, f"git {args}: {res.stderr}"
    return res.stdout.strip()


def _stub_resolver(path: Path, out: str, rc: int) -> Path:
    path.write_text(f"import sys\nprint({out!r})\nsys.exit({rc})\n", encoding="utf-8")
    return path


class World:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        for d in ("home", "sessions", "proc", "mail"):
            (tmp / d).mkdir()
        (tmp / "proc" / "stat").write_text(f"cpu 1\nbtime {BTIME}\n", encoding="utf-8")
        hooks = tmp / "opt" / "proj" / ".claude" / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "mail_notify.py").write_text("# fixture\n", encoding="utf-8")
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(tmp / "home"),
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.invalid",
            "FABRIK_MAIL_ROOT": str(tmp / "mail"),
            "FABRIK_OPT_ROOT": str(tmp / "opt"),
            "FABRIK_SESSIONS_ROOT": str(tmp / "sessions"),
            "FABRIK_PROC_ROOT": str(tmp / "proc"),
            "AGENT_IDENTITY_FILE": str(tmp / "agent-identity.jsonl"),
            "COMMAND_RUN_DIR": str(tmp / "home" / "command-runs"),
            "CLAUDE_AGENT": "fleet",
            "FABRIK_DECISIONS_PY": str(_stub_resolver(tmp / "resolver.py", "infra", 0)),
        }
        self.remote = tmp / "remote.git"
        _git(tmp, self.env, "init", "-q", "--bare", "-b", "master", str(self.remote))
        self.main = tmp / "proj"
        self.main.mkdir()
        _git(self.main, self.env, "init", "-q", "-b", "master")
        (self.main / "docs").mkdir()
        (self.main / "docs" / "DECISIONS.md").write_text("# Decisions\n", encoding="utf-8")
        (self.main / "README.md").write_text("proj\n", encoding="utf-8")
        _git(self.main, self.env, "add", "docs/DECISIONS.md", "README.md")
        _git(self.main, self.env, "commit", "-q", "-m", "init")
        _git(self.main, self.env, "remote", "add", "origin", str(self.remote))
        _git(self.main, self.env, "push", "-q", "origin", "master")
        self.wt = tmp / "wt"
        _git(self.main, self.env, "worktree", "add", "-q", "-b", "feat", str(self.wt))
        self.review = self.wt / "review.md"
        self.commit("work.txt", "done\n")

    def commit(self, name: str, text: str) -> str:
        (self.wt / name).write_text(text, encoding="utf-8")
        _git(self.wt, self.env, "add", name)
        _git(self.wt, self.env, "commit", "-q", "-m", f"add {name}")
        return _git(self.wt, self.env, "rev-parse", "HEAD")

    def push(self) -> None:
        _git(self.wt, self.env, "push", "-q", "-u", "origin", "feat")

    def config(self, distributor: str) -> None:
        store = self.wt / ".fabrik" / "work"
        store.mkdir(parents=True, exist_ok=True)
        (store / "config.json").write_text(
            json.dumps({"base_branch": "master", "distributor": distributor}), encoding="utf-8"
        )

    def run(self, *extra: str, env: dict | None = None) -> subprocess.CompletedProcess:
        self.review.write_text("receipt\n", encoding="utf-8")
        argv = [sys.executable, str(SCRIPT), "request", "--review", "review.md", *extra]
        return subprocess.run(
            argv,
            cwd=self.wt,
            env=env or self.env,
            capture_output=True,
            text=True,
            timeout=120,
            stdin=subprocess.DEVNULL,
            check=False,
        )

    def inbox(self) -> list[Path]:
        box = self.tmp / "mail" / "proj" / "inbox"
        return sorted(box.glob("*.md")) if box.is_dir() else []

    def session(self, pid: int, name: str, agent: str) -> None:
        """A LIVE session of ``agent`` in this repo, in the registry + the fixture proc tree."""
        entry = self.tmp / "sessions" / f"{pid}.json"
        entry.write_text(
            json.dumps(
                {"pid": pid, "sessionId": f"sid-{pid}", "cwd": str(self.main), "name": name}
            ),
            encoding="utf-8",
        )
        os.utime(entry, (BTIME + 10_000, BTIME + 10_000))
        proc = self.tmp / "proc" / str(pid)
        proc.mkdir()
        (proc / "environ").write_bytes(f"PATH=/usr/bin\0CLAUDE_AGENT={agent}\0".encode())
        (proc / "cmdline").write_bytes(b"/usr/local/bin/claude\0--resume\0")
        fields = ["S"] + ["0"] * 18 + [str(5_000 * CLK)] + ["0"] * 5
        (proc / "stat").write_text(f"{pid} (claude) {' '.join(fields)}\n", encoding="utf-8")


def _fields(path: Path) -> tuple[dict, dict]:
    """(frontmatter, body fields) of a delivered message."""
    text = path.read_text(encoding="utf-8")
    _, fm_text, body = text.split("---", 2)
    fm = dict(line.split(": ", 1) for line in fm_text.strip().splitlines() if ": " in line)
    out: dict[str, str] = {}
    for line in body.splitlines():
        k, sep, v = line.partition(":")
        if sep and k.strip() and k.strip() not in out:
            out[k.strip()] = v.strip()
    return fm, out


@pytest.fixture()
def world(tmp_path):
    return World(tmp_path)


# --- V1: pushed and at tip, or nothing is sent ------------------------------------------------
def test_unpushed_branch_refuses_and_writes_no_mail(world):
    r = world.run()
    assert r.returncode == 1, r.stdout + r.stderr
    assert "not pushed" in r.stderr
    assert world.inbox() == []


def test_remote_behind_local_head_refuses_and_writes_no_mail(world):
    world.push()
    head = world.commit("more.txt", "later\n")  # local HEAD now ahead of origin/feat
    r = world.run()
    assert r.returncode == 1, r.stdout + r.stderr
    assert head[:12] in r.stderr and "push" in r.stderr
    assert world.inbox() == []


def test_unreachable_remote_refuses_with_the_git_error_and_writes_no_mail(world):
    world.push()
    _git(world.wt, world.env, "remote", "set-url", "origin", str(world.tmp / "gone.git"))
    r = world.run()
    assert r.returncode == 1, r.stdout + r.stderr
    assert "cannot be reached" in r.stderr and "gone.git" in r.stderr
    assert world.inbox() == []


# --- delta 8: UNDECLARED gives the adopt command; a resolver failure never does ----------------
def test_undeclared_repo_refuses_with_the_adopt_command(world):
    """The REAL resolver: a ledger with no MERGE OWNER row exits 3 → the adopt command."""
    world.push()
    env = {**world.env, "FABRIK_DECISIONS_PY": str(REAL_DECISIONS)}
    r = world.run(env=env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "docs_updater.py --adopt" in r.stderr
    assert world.inbox() == []


def test_repo_with_no_decisions_ledger_refuses_with_the_adopt_command(world):
    world.push()
    (world.main / "docs" / "DECISIONS.md").unlink()
    env = {**world.env, "FABRIK_DECISIONS_PY": str(REAL_DECISIONS)}
    r = world.run(env=env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "docs_updater.py --adopt" in r.stderr
    assert world.inbox() == []


@pytest.mark.parametrize("shape", ["missing", "exit-1", "exit-2-empty"])
def test_resolver_failure_names_the_resolver_never_the_adopt_command(world, shape):
    world.push()
    resolver = world.tmp / "broken.py"
    if shape == "exit-1":
        _stub_resolver(resolver, "", 1)
    elif shape == "exit-2-empty":
        _stub_resolver(resolver, "", 2)
    r = world.run(env={**world.env, "FABRIK_DECISIONS_PY": str(resolver)})
    assert r.returncode == 1, r.stdout + r.stderr
    assert "resolver" in r.stderr and str(resolver) in r.stderr
    assert "--adopt" not in r.stderr
    assert world.inbox() == []


# --- V2: owner + a distinct distributor = two messages; otherwise one ------------------------
def test_distributor_distinct_from_owner_gets_an_ack_no_copy(world):
    world.push()
    world.config("intel")
    head = _git(world.wt, world.env, "rev-parse", "HEAD")
    r = world.run()
    assert r.returncode == 0, r.stdout + r.stderr
    msgs = [_fields(p) for p in world.inbox()]
    assert len(msgs) == 2
    by_agent = {fm["agent"]: (fm, body) for fm, body in msgs}
    assert set(by_agent) == {"infra", "intel"}
    assert by_agent["infra"][0]["ack"] == "required"
    assert by_agent["intel"][0]["ack"] == "no"
    for fm, body in by_agent.values():
        assert fm["kind"] == "merge-request"
        assert body["branch"] == "feat"
        assert body["head"] == head
        assert body["base"] == "master"
        assert body["item"] == "none"
        assert body["review"] == "review.md"
        assert body["doorbell"] == "none"
        assert body["requester"] == "fleet"
        assert body["sent"].endswith("Z")


@pytest.mark.parametrize("distributor", [None, "infra"])
def test_no_config_or_distributor_equal_to_owner_sends_exactly_one(world, distributor):
    world.push()
    if distributor is not None:
        world.config(distributor)
    r = world.run()
    assert r.returncode == 0, r.stdout + r.stderr
    msgs = [_fields(p) for p in world.inbox()]
    assert len(msgs) == 1
    assert msgs[0][0]["agent"] == "infra" and msgs[0][0]["ack"] == "required"


def test_the_owner_never_requests_from_itself(world):
    world.push()
    r = world.run(env={**world.env, "CLAUDE_AGENT": "infra"})
    assert r.returncode == 1
    assert "merge owner" in r.stderr
    assert world.inbox() == []


def test_the_mailbox_is_the_main_checkouts_name_not_the_worktrees(world):
    """The worktree dir is `wt`; the mail must land in `proj` (W-a681a4a7's class)."""
    world.push()
    assert world.run().returncode == 0
    assert len(world.inbox()) == 1
    assert not (world.tmp / "mail" / "wt").exists()


# --- delta 4: the doorbell ----------------------------------------------------------------------
def test_a_live_owner_session_is_named_in_doorbell_and_gets_a_sendmessage_line(world):
    world.push()
    world.session(4242, "proj-infra", "infra")
    r = world.run()
    assert r.returncode == 0, r.stdout + r.stderr
    (path,) = world.inbox()
    _, body = _fields(path)
    assert body["doorbell"] == "proj-infra"
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith("SendMessage")]
    assert lines == [f"SendMessage to=proj-infra: merge request {path.stem} from fleet for feat"]


def test_no_live_session_writes_doorbell_none_and_no_sendmessage_line(world):
    world.push()
    world.session(4243, "proj-intel", "intel")  # live, but not the owner
    r = world.run()
    assert r.returncode == 0, r.stdout + r.stderr
    (path,) = world.inbox()
    assert _fields(path)[1]["doorbell"] == "none"
    assert "SendMessage" not in r.stdout


# --- delta 2: --item releases the caller's claim ------------------------------------------------
def test_item_held_by_the_caller_is_released(world):
    env = {**world.env, "CLAUDE_CODE_SESSION_ID": "sess-caller"}
    work = [sys.executable, str(SCRIPTS / "work.py")]

    def wp(*args: str) -> str:
        res = subprocess.run(
            [*work, *args],
            cwd=world.wt,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        assert res.returncode == 0, res.stdout + res.stderr
        return res.stdout.strip()

    wp("init", "--distributor", "infra")
    item = wp("add", "--kind", "task", "--title", "finish feat").split()[0]
    item = Path(item).stem if item.endswith(".json") else item
    wp("claim", item)
    claims = Path(_git(world.wt, env, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    claim_file = claims / "fabrik-work" / "claims" / f"{item}.json"
    assert json.loads(claim_file.read_text())["lease_s"] > 0
    world.push()
    r = world.run("--item", item, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(claim_file.read_text())["lease_s"] == 0
    (path,) = world.inbox()
    assert _fields(path)[1]["item"] == item


def test_a_failed_distributor_copy_keeps_the_owner_request_and_exits_partial(world):
    """The owner's request is delivered first; a refused copy is exit 4 (never re-run), not 1."""
    world.push()
    world.config("Not An Agent!")  # mail.py refuses this addressee
    r = world.run()
    assert r.returncode == 4, r.stdout + r.stderr
    assert "do NOT re-run" in r.stderr
    (path,) = world.inbox()
    assert _fields(path)[0]["agent"] == "infra"


def test_a_malformed_item_id_refuses_before_anything_is_sent(world):
    world.push()
    r = world.run("--item", "W-1\nhead: 0000")
    assert r.returncode == 1
    assert "not a work item id" in r.stderr
    assert world.inbox() == []
