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
    def __init__(self, tmp: Path, separate_git_dir: bool = False) -> None:
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
        sep = ["--separate-git-dir", str(tmp / "gitdir")] if separate_git_dir else []
        _git(self.main, self.env, "init", "-q", "-b", "master", *sep)
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

    def config(self, distributor: str, base: str = "master") -> None:
        store = self.wt / ".fabrik" / "work"
        store.mkdir(parents=True, exist_ok=True)
        (store / "config.json").write_text(
            json.dumps({"base_branch": base, "distributor": distributor}), encoding="utf-8"
        )

    def run(
        self, *extra: str, env: dict | None = None, review: str = "review.md"
    ) -> subprocess.CompletedProcess:
        self.review.write_text("receipt\n", encoding="utf-8")
        argv = [sys.executable, str(SCRIPT), "request", "--review", review, *extra]
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
        assert body["review"] == str(world.review.resolve())
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


# --- review round 1 (classes A-H) ------------------------------------------------------------------
def _load():
    spec = importlib.util.spec_from_file_location("merge_request_inproc", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _inproc(world, monkeypatch, capsys, hook, *extra):
    """Run ``request`` IN-PROCESS with ``hook(mod, argv, call)`` wrapping every child process, so
    a timeout or an odd stdout lands exactly where the real ``_run`` would raise or return it."""
    for key, value in world.env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.chdir(world.wt)
    mod = _load()
    real = mod._run

    def wrapped(argv, *a, **kw):
        return hook(mod, argv, lambda: real(argv, *a, **kw))

    monkeypatch.setattr(mod, "_run", wrapped)
    world.review.write_text("receipt\n", encoding="utf-8")
    rc = mod.main(["request", "--review", "review.md", *extra])
    return rc, capsys.readouterr()


def _is(argv, verb, agent=None):
    script = str(SCRIPTS / ("work.py" if verb == "release" else "mail.py"))
    return script in argv and verb in argv and (agent is None or agent in argv)


# A — base forging
@pytest.mark.parametrize("via", ["flag", "config"])
def test_a_forged_base_refuses_before_anything_is_sent(world, via):
    world.push()
    forged = "master\ndoorbell: forged"
    if via == "flag":
        r = world.run("--base", forged)
    else:
        world.config("infra", base=forged)
        r = world.run()
    assert r.returncode == 1, r.stdout + r.stderr
    assert "base" in r.stderr
    assert world.inbox() == []


def test_a_base_that_is_not_on_the_remote_refuses(world):
    world.push()
    r = world.run("--base", "nope")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "refs/heads/nope" in r.stderr
    assert world.inbox() == []


def test_a_body_value_with_a_newline_is_refused_by_the_writer():
    mod = _load()
    fields = {
        "branch": "x",
        "head": "y",
        "base": "m",
        "requester": "fleet",
        "review": "a\nhead: y",
    }
    with pytest.raises(mod.RefusedError):
        mod._body(fields, "infra", "owner")


# C — the pushed check compares refs/heads/<branch>
def test_upstream_tracking_master_passes_when_the_branch_itself_is_pushed(world):
    world.push()
    _git(world.wt, world.env, "branch", "--set-upstream-to=origin/master", "feat")
    r = world.run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert len(world.inbox()) == 1


def test_an_upstream_under_another_name_is_not_the_branch_pushed(world):
    _git(world.wt, world.env, "push", "-q", "-u", "origin", "feat:other")
    r = world.run()
    assert r.returncode == 1, r.stdout + r.stderr
    assert "refs/heads/feat" in r.stderr
    assert world.inbox() == []


def test_a_local_dot_upstream_is_not_pushed(world):
    world.push()
    _git(world.wt, world.env, "config", "branch.feat.remote", ".")
    r = world.run()
    assert r.returncode == 1, r.stdout + r.stderr
    assert "local upstream" in r.stderr
    assert world.inbox() == []


@pytest.mark.parametrize(
    "key", ["branch.feat.pushRemote", "remote.pushDefault", "branch.feat.remote"]
)
def test_a_dot_push_remote_names_the_config_key_that_set_it(world, key):
    """O16: the refusal names the key that produced `.` and that key's remedy."""
    world.push()
    _git(world.wt, world.env, "config", key, ".")
    r = world.run()
    assert r.returncode == 1, r.stdout + r.stderr
    assert key in r.stderr
    assert f"git config --unset {key}" in r.stderr
    assert world.inbox() == []


# D — the default base is the remote's HEAD, never the main checkout's branch
def test_default_base_is_the_remotes_head_not_the_main_checkouts_branch(world):
    world.push()
    _git(world.main, world.env, "checkout", "-q", "-b", "scratch")
    r = world.run()
    assert r.returncode == 0, r.stdout + r.stderr
    (path,) = world.inbox()
    assert _fields(path)[1]["base"] == "master"


def test_no_base_anywhere_refuses_with_pass_base(world):
    world.push()
    _git(world.remote, world.env, "symbolic-ref", "HEAD", "refs/heads/gone")
    r = world.run()
    assert r.returncode == 1, r.stdout + r.stderr
    assert "pass --base" in r.stderr
    assert world.inbox() == []


# E — the main checkout is mail.py's, also under --separate-git-dir
def _mail_main_checkout(monkeypatch, cwd: Path) -> Path:
    monkeypatch.chdir(cwd)
    spec = importlib.util.spec_from_file_location("fabrik_mail_t02", SCRIPTS / "mail.py")
    mail = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mail)
    return mail._main_checkout()


def test_main_checkout_is_derived_exactly_as_mail_py_does(world, monkeypatch):
    assert _load()._main_checkout(world.wt) == _mail_main_checkout(monkeypatch, world.wt)
    assert _load()._main_checkout(world.wt) == world.main


def test_separate_git_dir_repo_refuses_rather_than_mail_the_git_dirs_name(tmp_path, monkeypatch):
    """git lists a --separate-git-dir repo's main worktree as the GIT DIR (measured: with and
    without core.worktree), so mail.py would address mailbox `gitdir`. Both derivations agree
    (pinned); request refuses naming the cause instead of mailing a mailbox nobody reads."""
    world = World(tmp_path, separate_git_dir=True)
    world.push()
    assert _load()._main_checkout(world.wt) == _mail_main_checkout(monkeypatch, world.wt)
    r = world.run()
    assert r.returncode == 1, r.stdout + r.stderr
    assert "separate git dir" in r.stderr
    assert not (world.tmp / "mail").exists() or not any((world.tmp / "mail").iterdir())


# F — --review is an existing regular file ANYWHERE (spec § The delta 1: a run record lives outside
# the repo), stored as its absolute realpath
def test_a_run_record_outside_the_repo_is_accepted_and_stored_absolute(world):
    world.push()
    record = world.tmp / "home" / "command-runs" / "run-1234.json"
    record.parent.mkdir(parents=True)
    record.write_text('{"status": "done"}\n', encoding="utf-8")
    r = world.run(review=str(record))
    assert r.returncode == 0, r.stdout + r.stderr
    (path,) = world.inbox()
    assert _fields(path)[1]["review"] == str(record.resolve())


@pytest.mark.parametrize("shape", ["directory", "missing"])
def test_a_review_that_is_not_an_existing_regular_file_refuses(world, shape):
    world.push()
    target = world.wt / ("adir" if shape == "directory" else "nope.md")
    if shape == "directory":
        target.mkdir()
    r = world.run(review=str(target))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "--review" in r.stderr
    assert world.inbox() == []


# O14 — the remote checked is the one the branch PUSHES to
@pytest.mark.parametrize("how", ["pushRemote", "pushDefault"])
def test_a_triangular_setup_pushed_as_itself_passes(world, how):
    """Fetch from `origin` (the upstream), push to `fork`: the branch is pushed only to fork."""
    fork = world.tmp / "fork.git"
    _git(world.tmp, world.env, "init", "-q", "--bare", "-b", "master", str(fork))
    _git(world.wt, world.env, "remote", "add", "fork", str(fork))
    _git(world.wt, world.env, "push", "-q", "fork", "master", "feat")
    _git(world.wt, world.env, "config", "branch.feat.remote", "origin")
    _git(world.wt, world.env, "config", "branch.feat.merge", "refs/heads/master")
    if how == "pushRemote":
        _git(world.wt, world.env, "config", "branch.feat.pushRemote", "fork")
    else:
        _git(world.wt, world.env, "config", "remote.pushDefault", "fork")
    r = world.run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert len(world.inbox()) == 1


# G — agent names compare casefolded
def test_agent_names_compare_casefolded(world):
    """CLAUDE_AGENT itself is lowercase-only (whoami's grammar), so the owner side varies case."""
    world.push()
    resolver = _stub_resolver(world.tmp / "upper.py", "FLEET", 0)
    r = world.run(env={**world.env, "FABRIK_DECISIONS_PY": str(resolver)})
    assert r.returncode == 1 and "merge owner" in r.stderr, r.stdout + r.stderr
    world.config(" INFRA ")
    r = world.run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert len(world.inbox()) == 1


# B — every failure after the owner send MAY have written is exit 4
@pytest.mark.parametrize(
    "step",
    ["distributor-who", "copy-send-timeout", "release", "owner-send-timeout", "owner-send-odd"],
)
def test_every_post_send_failure_exits_partial(world, monkeypatch, capsys, step):
    world.push()
    world.config("intel")
    world.session(4244, "proj-infra", "infra")

    def hook(mod, argv, call):
        timed_out = getattr(mod, "TimedOutError", mod.RefusedError)
        if step == "distributor-who" and _is(argv, "who", "intel"):
            raise timed_out("timed out")
        if step == "release" and _is(argv, "release"):
            raise timed_out("timed out")
        if step == "copy-send-timeout" and _is(argv, "send", "intel"):
            call()  # the copy IS written
            raise timed_out("timed out")
        if step.startswith("owner-send") and _is(argv, "send", "infra"):
            call()  # the message IS written
            if step == "owner-send-timeout":
                raise timed_out("timed out")
            return subprocess.CompletedProcess(argv, 0, "garbage\n", "")
        return call()

    extra = () if step in ("distributor-who", "copy-send-timeout") else ("--item", "W-00000000")
    rc, out = _inproc(world, monkeypatch, capsys, hook, *extra)
    assert rc == 4, out.out + out.err
    assert "do NOT re-run request" in out.err and "check the inbox" in out.err
    assert any(_fields(p)[0]["agent"] == "infra" for p in world.inbox())
    # O12: the partial message lists EVERY step left undone at that point
    undone = {
        "distributor-who": ["send the distributor copy (intel)"],
        # O15: a copy that MAY have landed is confirmed, never re-sent (a re-send duplicates it)
        "copy-send-timeout": ["confirm the distributor copy to intel landed (check the inbox)"],
        "release": ["release W-00000000"],
        "owner-send-timeout": [
            "confirm the owner message landed",
            "send the distributor copy (intel)",
            "release W-00000000",
        ],
    }
    undone["owner-send-odd"] = undone["owner-send-timeout"]
    assert "not done:" in out.err
    for step_left in undone[step]:
        assert step_left in out.err, out.err
    if step == "copy-send-timeout":
        assert "send the distributor copy" not in out.err, out.err
    if step == "distributor-who":
        assert "SendMessage to=proj-infra" in out.out  # the owner's doorbell still rings
