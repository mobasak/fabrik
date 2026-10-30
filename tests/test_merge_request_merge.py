"""Behavior-contract tests for `merge_request.py merge` and `resume` (plan 2026-09-30-plan-1 T03).

Spec: docs/superpowers/specs/2026-09-30-merge-request-loop-design.md § The delta 5, § Data-safety
invariants, § Validation V4-V7d; W-8a6a5644 residuals O35, O36.

Everything is a FIXTURE under tmp_path: a bare repo is the remote, the main checkout and the
requester's LINKED worktree are real git repos, the mail store is ``FABRIK_MAIL_ROOT``, the owner
resolver is a stub (``FABRIK_DECISIONS_PY``), the scratch parent of every throwaway worktree is a
private temp dir, and the hub sync is replaced by a marker writer. The verbs run IN-PROCESS so the
``on_phase`` seam can be replaced at the exact point a test needs (never an environment variable).
"""

from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
SCRIPT = SCRIPTS / "merge_request.py"
MAIL = SCRIPTS / "mail.py"

CHANGELOG = "# Changelog\n\n## [Unreleased]\n\n### Added — base entry\n\n## [0.1]\n- old\n"
DECISIONS = "# Decisions\n\n| D-1 | first |\n\n## tail\n"


def _git(cwd: Path, *args: str, check: bool = True) -> str:
    res = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if check:
        assert res.returncode == 0, f"git {args}: {res.stderr}"
    return res.stdout.strip()


def _load_module():
    spec = importlib.util.spec_from_file_location("merge_request_t03", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class World:
    """A remote, a main checkout on master (the owner's), and a requester worktree on ``feat``."""

    def __init__(self, tmp: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.tmp = tmp
        self.mp = monkeypatch
        self.mod = _load_module()
        for d in ("home", "mail", "scratch"):
            (tmp / d).mkdir()
        hooks = tmp / "opt" / "proj" / ".claude" / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "mail_notify.py").write_text("# fixture\n", encoding="utf-8")
        resolver = tmp / "resolver.py"
        resolver.write_text("print('infra')\n", encoding="utf-8")
        env = {
            "HOME": str(tmp / "home"),
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.invalid",
            "FABRIK_MAIL_ROOT": str(tmp / "mail"),
            "FABRIK_OPT_ROOT": str(tmp / "opt"),
            "FABRIK_SESSIONS_ROOT": str(tmp / "home" / "sessions"),
            "AGENT_IDENTITY_FILE": str(tmp / "agent-identity.jsonl"),
            "COMMAND_RUN_DIR": str(tmp / "home" / "command-runs"),
            "CLAUDE_AGENT": "infra",
            "CLAUDE_CODE_SESSION_ID": "sid-owner",
            "FABRIK_DECISIONS_PY": str(resolver),
        }
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setattr(tempfile, "tempdir", str(tmp / "scratch"))
        self.sync_marker = tmp / "synced"
        monkeypatch.setattr(
            self.mod,
            "SYNC_ARGV",
            [sys.executable, "-c", f"open({str(self.sync_marker)!r}, 'a').write('x')"],
        )
        # runners start bare here: a real scope would outlive the test (W-73d00b05's own graders
        # clear this pin)
        monkeypatch.setattr(self.mod, "_SCOPE", {"ok": False}, raising=False)
        self.remote = tmp / "remote.git"
        _git(tmp, "init", "-q", "--bare", "-b", "master", str(self.remote))
        self.main = tmp / "proj"
        self.main.mkdir()
        _git(self.main, "init", "-q", "-b", "master")
        self.write("README.md", "proj\n")
        self.write("notes.txt", "notes\n")
        self.write("CHANGELOG.md", CHANGELOG)
        self.write("docs/DECISIONS.md", DECISIONS)
        self.write("docs/LESSONS_LEARNT.md", "# Lessons\n")
        self.commit_main("init", "README.md", "notes.txt", "CHANGELOG.md", "docs")
        _git(self.main, "remote", "add", "origin", str(self.remote))
        _git(self.main, "push", "-q", "origin", "master")
        _git(self.main, "branch", "-q", "--set-upstream-to=origin/master")
        cfg = self.main / ".fabrik" / "work" / "config.json"
        cfg.parent.mkdir(parents=True)
        cfg.write_text(json.dumps({"distributor": "intel"}), encoding="utf-8")
        self.wt = tmp / "wt"
        _git(self.main, "worktree", "add", "-q", "-b", "feat", str(self.wt))
        monkeypatch.chdir(self.main)

    # --- file and git helpers -------------------------------------------------------------------
    def write(self, rel: str, text: str, root: Path | None = None) -> None:
        path = (root or self.main) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def read(self, rel: str) -> str:
        return (self.main / rel).read_text(encoding="utf-8")

    def commit_main(self, msg: str, *paths: str) -> str:
        _git(self.main, "add", "--", *paths)
        _git(self.main, "commit", "-q", "-m", msg)
        return _git(self.main, "rev-parse", "HEAD")

    def branch(self, files: dict[str, str | None], msg: str = "branch work") -> str:
        """Commit ``files`` on ``feat`` (None deletes) and push it; returns the head."""
        for rel, text in files.items():
            if text is None:
                _git(self.wt, "rm", "-q", "--", rel)
            else:
                self.write(rel, text, root=self.wt)
                _git(self.wt, "add", "--", rel)
        _git(self.wt, "commit", "-q", "-m", msg)
        _git(self.wt, "push", "-q", "origin", "feat")
        return _git(self.wt, "rev-parse", "HEAD")

    def push_from_elsewhere(self, rel: str, text: str) -> str:
        """Another machine moves origin's master."""
        other = self.tmp / f"other-{len(list(self.tmp.glob('other-*')))}"
        _git(self.tmp, "clone", "-q", str(self.remote), str(other))
        self.write(rel, text, root=other)
        _git(other, "add", "--", rel)
        _git(other, "commit", "-q", "-m", f"elsewhere {rel}")
        _git(other, "push", "-q", "origin", "master")
        return _git(other, "rev-parse", "HEAD")

    def base(self) -> str:
        return _git(self.main, "rev-parse", "refs/heads/master")

    def origin(self) -> str:
        return _git(self.main, "ls-remote", str(self.remote), "refs/heads/master").split()[0]

    # --- mail helpers ---------------------------------------------------------------------------
    def send(
        self,
        head: str,
        *,
        agent: str | None = "infra",
        ack: str | None = None,
        item: str = "none",
        branch: str = "feat",
        base: str = "master",
    ) -> str:
        body = (
            f"branch: {branch}\nhead: {head}\nbase: {base}\nitem: {item}\n"
            f"review: {self.tmp / 'review.md'}\ndoorbell: none\nsent: 2026-10-01T00:00:00Z\n"
            "requester: fleet\n\nWHAT — merge request.\n"
        )
        argv = [sys.executable, str(MAIL), "send", "--to", "proj", "--kind", "merge-request"]
        argv += ["--to-agent", agent] if agent else []
        argv += ["--ack", ack] if ack else []
        res = subprocess.run(
            argv, cwd=self.main, input=body, capture_output=True, text=True, timeout=60, check=False
        )
        assert res.returncode == 0, res.stderr
        return Path(res.stdout.strip().splitlines()[-1]).stem

    def inbox(self) -> list[str]:
        box = self.tmp / "mail" / "proj" / "inbox"
        return sorted(p.stem for p in box.glob("*.md")) if box.is_dir() else []

    def archived(self, msg_id: str) -> str:
        return (self.tmp / "mail" / "proj" / "archive" / f"{msg_id}.md").read_text(encoding="utf-8")

    def replies(self, msg_id: str) -> dict[str, str]:
        """{addressee: body} of every reply threaded on ``msg_id``."""
        out: dict[str, str] = {}
        for path in (self.tmp / "mail" / "proj" / "inbox").glob("*.md"):
            text = path.read_text(encoding="utf-8")
            head = text.split("\n---", 1)[0]
            if "kind: reply" in head and f"re: {msg_id}" in head:
                agent = next(
                    ln[len("agent: ") :] for ln in head.splitlines() if ln.startswith("agent: ")
                )
                out[agent] = text
        return out

    def record(self, msg_id: str) -> dict:
        return json.loads((self.main / ".git" / "fabrik-merge" / f"{msg_id}.json").read_text())

    # --- running the verbs ----------------------------------------------------------------------
    def run(self, *argv: str, phase=None) -> int:
        self.mp.setattr(self.mod, "on_phase", phase or (lambda name: None))
        return self.mod.main(list(argv))

    def state(self) -> dict:
        """Origin, local refs and the main checkout byte-for-byte (work-item files excluded)."""
        files: dict[str, bytes] = {}
        for root, dirs, names in os.walk(self.main):
            rel_root = Path(root).relative_to(self.main)
            if rel_root.parts[:1] == (".git",):
                dirs[:] = []
                continue
            for name in names:
                rel = rel_root / name
                if rel.parts[:2] == (".fabrik", "work") and name.startswith("W-"):
                    continue
                files[str(rel)] = (Path(root) / name).read_bytes()
        return {
            "files": files,
            "index": _git(self.main, "ls-files", "-s"),
            "status": _git(self.main, "status", "--porcelain"),
            "refs": _git(self.main, "for-each-ref", "refs/heads"),
            "origin": self.origin(),
        }

    def worktrees(self) -> list[str]:
        """The registered worktree paths (a HEAD line moves with a merge; the set must not)."""
        out = _git(self.main, "worktree", "list", "--porcelain")
        return [ln for ln in out.splitlines() if ln.startswith("worktree ")]

    def scratch_left(self) -> list[str]:
        return sorted(p.name for p in (self.tmp / "scratch").iterdir())


@pytest.fixture()
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def _added(world: World, rel: str) -> list[str]:
    """Lines the main checkout's working copy adds over HEAD for ``rel``."""
    diff = _git(world.main, "diff", "-U0", "HEAD", "--", rel)
    return [ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]


# --- V4: the happy path over sibling ledger WIP ----------------------------------------------
def test_merge_lands_one_merge_commit_and_keeps_sibling_ledger_wip(world):
    head = world.branch(
        {
            "CHANGELOG.md": CHANGELOG.replace(
                "## [Unreleased]\n\n", "## [Unreleased]\n\n### Added — branch entry\n\n"
            ),
            "docs/DECISIONS.md": DECISIONS.replace("| D-1 |", "| D-2 | branch |\n| D-1 |"),
        }
    )
    world.write("CHANGELOG.md", CHANGELOG + "- wip sibling\n")
    world.write("docs/DECISIONS.md", DECISIONS + "sibling wip row\n")
    msg_id = world.send(head, item="W-0123abcd")
    old, trees = world.base(), world.worktrees()

    assert world.run("merge") == 0

    new = world.base()
    assert _git(world.main, "rev-parse", f"{new}^1", f"{new}^2").split() == [old, head]
    message = _git(world.main, "log", "-1", "--format=%s", new)  # Agent-Context repeats the phrase
    assert f"request {msg_id}, item W-0123abcd" in message
    assert world.origin() == new
    # sibling WIP byte-for-byte on top of the merged content; nothing staged
    assert (
        world.read("CHANGELOG.md")
        == _git(world.main, "show", "HEAD:CHANGELOG.md") + "\n- wip sibling\n"
    )
    assert "### Added — branch entry" in world.read("CHANGELOG.md")
    assert _added(world, "CHANGELOG.md") == ["- wip sibling"]
    assert _added(world, "docs/DECISIONS.md") == ["sibling wip row"]
    assert _git(world.main, "diff", "--cached", "--name-only") == ""
    replies = world.replies(msg_id)
    assert set(replies) == {"fleet", "intel"}
    assert new in replies["fleet"] and "outcome: merged" in replies["fleet"]
    assert "no owner tests ran (no .fabrik/merge-tests, no touched tests/)" in replies["intel"]
    assert "not carried" not in replies["fleet"]
    assert f"merge-sha: {new}" in world.archived(msg_id)
    assert "disposition: done" in world.archived(msg_id)
    assert world.record(msg_id)["phase"] == "replied"
    assert world.worktrees() == trees and world.scratch_left() == []
    assert not world.sync_marker.exists()  # not the hub: (g) owes nothing


# --- V5: every preflight refusal leaves origin, base and the main checkout byte-identical ----
def _untracked(world):
    world.write("new.txt", "mine\n")
    return world.branch({"new.txt": "theirs\n"}), "untracked"


def _dirty_non_ledger(world):
    head = world.branch({"README.md": "branch readme\n"})
    world.write("README.md", "owner wip\n")
    return head, "not a ledger"


def _dirty_deleted(world):
    head = world.branch({"docs/LESSONS_LEARNT.md": None})
    world.write("docs/LESSONS_LEARNT.md", "# Lessons\nowner wip\n")
    return head, "deletes it"


def _staged_only(world):
    head = world.branch({"README.md": "branch readme\n"})
    world.write("README.md", "staged\n")
    _git(world.main, "add", "README.md")
    world.write("README.md", "proj\n")  # working copy equals HEAD; only the index differs
    return head, "staged differently"


def _ledger_edits_existing_line(world):
    head = world.branch({"CHANGELOG.md": CHANGELOG.replace("- old\n", "- old B\n")})
    world.write("CHANGELOG.md", CHANGELOG.replace("- old\n", "- old A\n"))
    world.commit_main("base edits the line", "CHANGELOG.md")
    return head, "edits an existing line"


def _red_owner_test(world):
    world.write(".fabrik/merge-tests", 'python3 -c "import sys; sys.exit(3)"\n')
    world.commit_main("owner tests", ".fabrik/merge-tests")
    return world.branch({"x.txt": "x\n"}), "owner tests red"


def _dirty_ledger_carry_conflicts(world):
    head = world.branch({"CHANGELOG.md": CHANGELOG.replace("- old\n", "- old B\n")})
    world.write("CHANGELOG.md", CHANGELOG.replace("- old\n", "- old W\n"))  # uncommitted WIP
    return head, "edits an existing line"


def _branch_mints_a_colliding_d_id(world):
    head = world.branch(
        {"docs/DECISIONS.md": DECISIONS.replace("| D-1 |", "| D-3 | branch |\n| D-1 |")}
    )
    world.write("docs/DECISIONS.md", DECISIONS.replace("| D-1 |", "| D-3 | base |\n| D-1 |"))
    world.commit_main("base row", "docs/DECISIONS.md")
    return head, "D-3 collides"


@pytest.mark.parametrize(
    "setup",
    [
        _untracked,
        _dirty_non_ledger,
        _dirty_deleted,
        _staged_only,
        _ledger_edits_existing_line,
        _red_owner_test,
        _dirty_ledger_carry_conflicts,
        _branch_mints_a_colliding_d_id,
    ],
)
def test_preflight_refusal_leaves_everything_byte_identical(world, setup):
    head, why = setup(world)
    msg_id = world.send(head)
    before, trees = world.state(), world.worktrees()

    assert world.run("merge") == 1

    assert world.state() == before
    assert world.worktrees() == trees and world.scratch_left() == []
    archived = world.archived(msg_id)
    assert "disposition: blocked" in archived and why in archived
    assert "outcome: refused" in world.replies(msg_id)["fleet"]


def test_origin_ahead_at_start_refuses(world):
    head = world.branch({"x.txt": "x\n"})
    world.push_from_elsewhere("y.txt", "y\n")
    msg_id = world.send(head)
    before = world.state()

    assert world.run("merge") == 1

    assert world.state() == before
    assert "ahead of the local base" in world.archived(msg_id)


# --- V6: a base that moves during the build rebuilds in full, then refuses ---------------------
def _counting_tests(world) -> Path:
    counter = world.tmp / "test-runs"
    world.write(".fabrik/merge-tests", f"python3 -c \"open({str(counter)!r}, 'a').write('x')\"\n")
    world.commit_main("owner tests", ".fabrik/merge-tests")
    return counter


def test_base_moved_once_rebuilds_with_fresh_tests_and_merges(world):
    counter = _counting_tests(world)
    head = world.branch({"x.txt": "x\n"})
    msg_id = world.send(head)
    calls: list[str] = []

    def phase(name):
        if name == "after-build":
            calls.append(name)
            if len(calls) == 1:
                world.write("bump.txt", "bump\n")
                world.commit_main("pipeline commit", "bump.txt")

    assert world.run("merge", phase=phase) == 0
    assert len(calls) == 2 and counter.read_text() == "xx"
    assert _git(world.main, "rev-parse", "master^2") == head
    assert world.record(msg_id)["phase"] == "replied"


def test_base_moving_every_build_refuses_after_three_rebuilds(world):
    counter = _counting_tests(world)
    head = world.branch({"x.txt": "x\n"})
    msg_id = world.send(head)
    calls: list[str] = []

    def phase(name):
        if name == "after-build":
            calls.append(name)
            world.write(f"bump{len(calls)}.txt", "bump\n")
            world.commit_main("pipeline commit", f"bump{len(calls)}.txt")

    assert world.run("merge", phase=phase) == 1
    assert len(calls) == 4 and counter.read_text() == "xxxx"
    assert _git(world.main, "log", "--format=%H", "-F", f"--grep=request {msg_id}", "master") == ""
    assert _git(world.main, "log", "-1", "--format=%s", "master") == "pipeline commit"
    assert "disposition: blocked" in world.archived(msg_id)


# --- V7d / O35: a rejected push is finished by resume through a catch-up merge -----------------
def test_rejected_push_is_finished_by_resume_with_a_catch_up_merge(world):
    head = world.branch({"x.txt": "x\n"})
    world.write("notes.txt", "owner unstaged wip\n")
    msg_id = world.send(head)
    pushed: list[str] = []

    def race(name):
        if name == "before-push" and not pushed:
            pushed.append(world.push_from_elsewhere("y.txt", "y\n"))

    assert world.run("merge", phase=race) == 4
    merge_sha = world.record(msg_id)["merge_sha"]
    assert world.origin() == pushed[0]  # the push was rejected; the merge is committed locally
    assert world.record(msg_id)["phase"] == "carried"
    assert "disposition" not in world.archived(msg_id)

    assert world.run("resume", msg_id) == 0

    assert world.origin() == world.base()
    for sha in (merge_sha, pushed[0]):
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, "master"], cwd=world.main, check=True
        )
    assert world.read("notes.txt") == "owner unstaged wip\n"  # the WIP is intact
    assert (
        world.read("y.txt") == "y\n" and _git(world.main, "diff", "--cached", "--name-only") == ""
    )
    assert _git(world.main, "stash", "list") == ""
    assert not (world.main / ".git" / "rebase-merge").exists()
    assert f"merge-sha: {merge_sha}" in world.archived(msg_id)


# --- V7: picking, stranded records, the lock ------------------------------------------------
def test_merge_picks_only_the_owners_request_and_claims_before_building(world):
    head = world.branch({"x.txt": "x\n"})
    copy_id = world.send(head, agent="intel", ack="no")
    stray_id = world.send(head, agent=None)
    own_id = world.send(head)
    seen: list[list[str]] = []

    def phase(name):
        if name == "after-build":
            seen.append(world.inbox())

    assert world.run("merge", phase=phase) == 0
    assert own_id not in seen[0] and {copy_id, stray_id} <= set(seen[0])
    assert {copy_id, stray_id} <= set(world.inbox()) and own_id not in world.inbox()
    assert own_id in _git(world.main, "log", "-1", "--format=%B", "master")


def _strand(world, pid: int, start, *, phase: str = "claimed", claim: bool = True) -> str:
    head = world.branch({"x.txt": "x\n"})
    msg_id = world.send(head)
    if claim:
        res = subprocess.run(
            [sys.executable, str(MAIL), "claim", msg_id, "--repo", "proj"],
            cwd=world.main,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert res.returncode == 0, res.stderr
    records = world.main / ".git" / "fabrik-merge"
    records.mkdir(exist_ok=True)
    rec = {
        "id": msg_id,
        "phase": phase,
        "branch": "feat",
        "head": head,
        "base": "master",
        "item": "none",
        "requester": "fleet",
        "review": "",
        "session": "sid-dead",
        "pid": pid,
        "start": start,
    }
    (records / f"{msg_id}.json").write_text(json.dumps(rec), encoding="utf-8")
    return msg_id


def _dead_pid() -> int:
    proc = subprocess.Popen(["true"])
    proc.wait()
    return proc.pid


@pytest.mark.parametrize("who", ["dead", "reused"])
def test_stranded_record_is_resumed_first(world, who):
    pid, start = (_dead_pid(), "123") if who == "dead" else (os.getpid(), "0")
    msg_id = _strand(world, pid, start)

    assert world.run("merge") == 0

    rec = world.record(msg_id)
    assert rec["phase"] == "replied" and rec["pid"] == os.getpid()
    assert _git(world.main, "rev-parse", "master^2") == rec["head"]


def test_a_record_naming_the_live_run_itself_is_not_stranded(world):
    msg_id = _strand(world, os.getpid(), world.mod._proc_start(os.getpid()))
    old = world.base()

    assert world.run("merge") == 0

    assert world.record(msg_id)["phase"] == "claimed" and world.base() == old


@pytest.mark.parametrize("verb", ["merge", "resume"])
def test_a_held_merge_lock_stops_a_second_run_before_anything(world, verb):
    head = world.branch({"x.txt": "x\n"})
    msg_id = world.send(head)
    trees = world.worktrees()
    fd = os.open(world.main / ".git" / "fabrik-merge.lock", os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        argv = ["merge"] if verb == "merge" else ["resume", msg_id]
        assert world.run(*argv) == 1
    finally:
        os.close(fd)
    assert world.inbox() == [msg_id]
    assert not (world.main / ".git" / "fabrik-merge").exists()
    assert world.worktrees() == trees and world.scratch_left() == []


# --- (e): a path edited between the CAS and the carry keeps the edit -----------------------
def test_a_path_raced_before_the_carry_keeps_the_edit_with_its_index_at_the_merge(world):
    head = world.branch({"README.md": "branch readme\n"})
    msg_id = world.send(head)

    def race(name):
        if name == "before-carry":
            world.write("README.md", "owner raced edit\n")

    assert world.run("merge", phase=race) == 0

    assert world.read("README.md") == "owner raced edit\n"
    staged = _git(world.main, "ls-files", "-s", "README.md").split()[1]
    assert staged == _git(world.main, "rev-parse", "master:README.md")
    for agent in ("fleet", "intel"):  # requester AND coordinator see it, under its own heading
        reply = world.replies(msg_id)[agent]
        listed = reply.split("not carried:", 1)[1]
        assert "README.md" in listed and "git commit -a" in listed


# --- V7: head already in base → no second merge ---------------------------------------------
def test_resume_of_a_request_already_in_base_names_the_existing_merge(world):
    head = world.branch({"x.txt": "x\n"})
    msg_id = world.send(head)
    _git(
        world.main,
        "merge",
        "-q",
        "--no-ff",
        "-m",
        f"merge(infra): feat — request {msg_id}, item none",
        head,
    )
    existing = world.base()
    world.write("later.txt", "later\n")
    tip = world.commit_main("a later base commit", "later.txt")  # base moved past the merge

    assert world.run("resume", msg_id) == 0

    assert world.base() == tip == world.origin()  # no second merge commit
    assert existing in world.replies(msg_id)["fleet"]
    assert f"merge-sha: {existing}" in world.archived(msg_id)


# --- V7c / V7d: re-hash before the CAS; the base's merge-tests --------------------------------
def test_a_path_edited_before_the_cas_returns_the_run_to_the_preflight(world):
    head = world.branch(
        {
            "CHANGELOG.md": CHANGELOG.replace(
                "## [Unreleased]\n\n", "## [Unreleased]\n\n### Added — b\n\n"
            )
        }
    )
    msg_id = world.send(head)
    builds: list[str] = []

    def phase(name):
        if name == "after-build":
            builds.append(name)
        if name == "before-cas" and len(builds) == 1:
            world.write("CHANGELOG.md", CHANGELOG + "- raced wip\n")

    assert world.run("merge", phase=phase) == 0
    assert len(builds) == 2  # back to (a) with a fresh snapshot, never a write over the edit
    assert _added(world, "CHANGELOG.md") == ["- raced wip"]
    assert world.record(msg_id)["phase"] == "replied"


def test_the_bases_merge_tests_run_never_the_branchs(world):
    marker = world.tmp / "which-tests"
    world.write(".fabrik/merge-tests", f"python3 -c \"open({str(marker)!r}, 'w').write('base')\"\n")
    world.commit_main("owner tests", ".fabrik/merge-tests")
    _git(world.wt, "merge", "-q", "--ff-only", "master")  # the branch starts from that base
    head = world.branch({".fabrik/merge-tests": "exit 1\n", "x.txt": "x\n"})
    msg_id = world.send(head)

    assert world.run("merge") == 0
    assert marker.read_text() == "base"
    assert "tests: .fabrik/merge-tests (base copy): green" in world.replies(msg_id)["fleet"]


# --- (b): pure-insertion ledger conflicts resolve, newest D-row first -----------------------
def test_a_pure_insertion_decisions_conflict_resolves_newest_first(world):
    head = world.branch(
        {"docs/DECISIONS.md": DECISIONS.replace("| D-1 |", "| D-2 | branch |\n| D-1 |")}
    )
    world.write("docs/DECISIONS.md", DECISIONS.replace("| D-1 |", "| D-3 | base |\n| D-1 |"))
    world.commit_main("base row", "docs/DECISIONS.md")
    world.send(head)

    assert world.run("merge") == 0
    rows = [ln for ln in world.read("docs/DECISIONS.md").splitlines() if ln.startswith("| D-")]
    assert rows == ["| D-3 | base |", "| D-2 | branch |", "| D-1 | first |"]


def test_a_resolved_ledger_conflict_commits_the_request_message_without_git_comments(world):
    """V9 (2026-10-01): a ledger conflict resolved in (b) committed with `--no-edit`, which reuses
    git's MERGE_MSG — its `# Conflicts:` comment block landed in the merge commit on master."""
    head = world.branch(
        {"docs/DECISIONS.md": DECISIONS.replace("| D-1 |", "| D-2 | branch |\n| D-1 |")}
    )
    world.write("docs/DECISIONS.md", DECISIONS.replace("| D-1 |", "| D-3 | base |\n| D-1 |"))
    world.commit_main("base row", "docs/DECISIONS.md")
    msg_id = world.send(head)

    assert world.run("merge") == 0
    body = _git(world.main, "log", "-1", "--format=%B", "master")
    assert msg_id in body
    assert not [ln for ln in body.splitlines() if ln.startswith("#")], body


# --- (g): the hub's governance sync runs OUTSIDE the merge lock (W-4f4ac600) ---------------
_SYNC_CONFIG = (
    "repos:\n  - repo: local\n    hooks:\n      - id: governance-sync\n"
    "        files: '(^scripts/mail\\.py$|^templates/governance/)'\n"
    "      - id: other\n        files: '^x'\n"
)


def _hub(world, monkeypatch) -> Path:
    """Make the scratch checkout the hub, with a governance-sync filter; returns the state dir."""
    world.write(".pre-commit-config.yaml", _SYNC_CONFIG)
    world.commit_main("hooks", ".pre-commit-config.yaml")
    monkeypatch.setattr(world.mod, "HUB_CHECKOUT", world.main)
    return world.main / ".git" / "fabrik-merge"


def _fake_sync(world, monkeypatch, body: str) -> None:
    """SYNC_ARGV runs ``body`` (Python) with ``marker`` and ``state`` bound."""
    code = (
        "import fcntl, os, pathlib, sys, time\n"
        f"marker = pathlib.Path({str(world.sync_marker)!r})\n"
        f"state = pathlib.Path({str(world.main / '.git' / 'fabrik-merge')!r})\n" + body
    )
    monkeypatch.setattr(world.mod, "SYNC_ARGV", [sys.executable, "-c", code])


def _sync_landing(world, text: str = "# mail\n") -> str:
    """A request whose merge touches a governance-sync path."""
    return world.send(world.branch({"scripts/mail.py": text}))


def test_the_hub_sync_runs_when_a_merged_path_matches_the_filter(world, monkeypatch, capsys):
    state = _hub(world, monkeypatch)
    msg_id = _sync_landing(world)

    assert world.run("merge") == 0
    assert world.sync_marker.read_text() == "x"
    reply = world.replies(msg_id)["fleet"]
    assert "sync: owed for 1 governance-sync path(s) — runs outside the merge lock" in reply
    assert "sync: ran" in capsys.readouterr().err
    owed = (state / "sync-owed.log").stat().st_size
    assert owed > 0
    assert int((state / "sync-done").read_text()) == owed


def test_the_sync_runs_outside_the_merge_lock(world, monkeypatch):
    _hub(world, monkeypatch)
    _fake_sync(
        world,
        monkeypatch,
        "fd = os.open(state.parent / 'fabrik-merge.lock', os.O_RDWR | os.O_CREAT)\n"
        "end = time.monotonic() + 60\n"
        "got = 'held'\n"
        "while time.monotonic() < end:\n"
        "    try:\n"
        "        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
        "        got = 'free'\n"
        "        break\n"
        "    except BlockingIOError:\n"
        "        time.sleep(0.1)\n"
        "marker.write_text(got)\n",
    )
    _sync_landing(world)

    assert world.run("merge") == 0
    assert world.sync_marker.read_text() == "free"


def test_a_debt_owed_during_a_sync_is_covered_by_one_more_run(world, monkeypatch):
    _hub(world, monkeypatch)
    # the first sync owes once more while it runs (as a later landing would); the SAME runner's
    # next turn covers that debt (each sync records its runner's pid — a drain rerun would be a
    # second runner), and no third sync runs
    _fake_sync(
        world,
        monkeypatch,
        "first = not marker.exists()\n"
        "with open(marker, 'a') as f: f.write(f'{os.getppid()}\\n')\n"
        "if first:\n"
        "    with open(state / 'sync-owed.log', 'a') as f: f.write('owed during the sync\\n')\n",
    )
    _sync_landing(world)

    assert world.run("merge") == 0
    runners = world.sync_marker.read_text().split()
    assert len(runners) == 2, runners
    assert runners[0] == runners[1], f"the debt was covered by a second runner: {runners}"


def test_a_failed_sync_stays_owed_and_the_next_kick_retries_it(world, monkeypatch, capsys):
    state = _hub(world, monkeypatch)
    # exit 3, not 1: the runner itself exits 1 on any failed sync, so the sync's own code must
    # still reach the line the merge owner reads
    _fake_sync(world, monkeypatch, "print('step one'); print('boom'); sys.exit(3)\n")
    _sync_landing(world)

    assert world.run("merge") == 0  # a sync's failure never changed the merge's exit
    err = capsys.readouterr().err
    assert (
        "sync: FAILED (exit 3: step one boom) — run scripts/sync_enforcement_to_projects.py --force"
        in err
    )
    assert not (state / "sync-done").exists()

    _fake_sync(world, monkeypatch, "marker.write_text('retried')\n")
    msg_id = world.send(world.branch({"notes.txt": "a landing that owes no sync\n"}))
    assert world.run("merge") == 0
    assert world.sync_marker.read_text() == "retried"
    assert "the last background sync FAILED (exit 3)" in world.replies(msg_id)["fleet"]


def test_a_runner_crash_is_printed_with_its_reason_not_a_stale_status(world, monkeypatch, capsys):
    state = _hub(world, monkeypatch)
    state.mkdir(parents=True, exist_ok=True)
    (state / "sync-status.txt").write_text('{"at": 0, "covers": 1, "rc": 0}')  # an older run's
    (state / "sync-done").mkdir()  # writing it fails inside the runner, after a green sync
    _sync_landing(world)

    assert world.run("merge") == 0
    err = capsys.readouterr().err
    assert "sync: FAILED (exit 70: runner crashed: IsADirectoryError" in err
    assert "sync: ran" not in err
    assert not list(state.glob(".sync-done.*")), "the failed write left its temp file"


def test_a_sync_orphaned_by_a_killed_runner_keeps_the_sync_lock(world, monkeypatch):
    _hub(world, monkeypatch)
    # the sync kills its runner, then asks whether the sync lock is still held — by itself
    _fake_sync(
        world,
        monkeypatch,
        "import signal\n"
        "os.kill(os.getppid(), signal.SIGKILL)\n"
        "time.sleep(0.5)\n"
        "fd = os.open(state / 'sync.lock', os.O_RDWR)\n"
        "try:\n"
        "    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
        "    marker.write_text('free')\n"
        "except BlockingIOError:\n"
        "    marker.write_text('held')\n",
    )
    _sync_landing(world)

    assert world.run("merge") == 0
    end = time.monotonic() + 30  # the orphan writes after its runner's drain has returned
    while time.monotonic() < end and not (
        world.sync_marker.exists() and world.sync_marker.read_text()
    ):
        time.sleep(0.1)
    assert world.sync_marker.read_text() == "held"


def test_a_debt_owed_after_the_runner_exits_gets_one_more_runner(world, monkeypatch, capsys):
    state = _hub(world, monkeypatch)
    state.mkdir(parents=True, exist_ok=True)
    (state / "sync-owed.log").write_text("owed after the runner's last check\n")
    _fake_sync(world, monkeypatch, "marker.write_text('x')\n")
    done = subprocess.Popen([sys.executable, "-c", "pass"])  # a runner that exited 0, debt open
    world.mod._SYNC_RUN.update(proc=done, state=state, main=world.main)

    world.mod._drain_sync()
    assert world.sync_marker.read_text() == "x"
    err = capsys.readouterr().err
    assert "sync: ran" in err
    assert "FAILED" not in err


def test_a_sync_that_cannot_be_owed_is_reported_and_the_landing_still_replies(world, monkeypatch):
    state = _hub(world, monkeypatch)
    (state / "sync-owed.log").mkdir(parents=True)  # the owed line cannot be written
    msg_id = _sync_landing(world)

    assert world.run("merge") == 0
    reply = world.replies(msg_id)["fleet"]
    assert "sync: FAILED to owe or start (" in reply
    assert "run scripts/sync_enforcement_to_projects.py --force" in reply


@pytest.mark.skipif(os.geteuid() == 0, reason="chmod 0 does not bar root's reads")
def test_a_drain_that_cannot_read_its_state_keeps_the_exit_code(world, monkeypatch, capsys):
    state = _hub(world, monkeypatch)
    state.mkdir(parents=True, exist_ok=True)
    (state / "sync-owed.log").write_text("owed\n")
    done = subprocess.Popen([sys.executable, "-c", "pass"])
    done.wait()
    world.mod._SYNC_RUN.update(proc=done, state=state, main=world.main)
    state.chmod(0)
    try:
        assert world.run("merge") == 0  # nothing waits in the inbox: the verb's own exit is 0
    finally:
        state.chmod(0o755)
    assert "merge_request: sync: unknown (" in capsys.readouterr().err


def test_a_rerun_that_cannot_start_leads_with_failed(world, monkeypatch, capsys):
    state = _hub(world, monkeypatch)
    state.mkdir(parents=True, exist_ok=True)
    (state / "sync-owed.log").write_text("owed after the runner's last check\n")
    done = subprocess.Popen([sys.executable, "-c", "pass"])  # exited 0, the debt still open
    done.wait()
    world.mod._SYNC_RUN.update(proc=done, state=state, main=world.main)

    def no_start(*args, **kwargs):
        raise OSError("no such exec")

    monkeypatch.setattr(world.mod.subprocess, "Popen", no_start)
    world.mod._drain_sync()
    err = capsys.readouterr().err
    assert err.startswith("merge_request: sync: FAILED to start (no such exec)"), err


def test_a_refused_verb_still_drains_its_sync(world, monkeypatch, capsys):
    state = _hub(world, monkeypatch)
    state.mkdir(parents=True, exist_ok=True)
    (state / "sync-owed.log").write_text("owed\n")
    (state / "sync-done").write_text(f"{(state / 'sync-owed.log').stat().st_size}\n")
    done = subprocess.Popen([sys.executable, "-c", "pass"])  # this run's runner, covered
    world.mod._SYNC_RUN.update(proc=done, state=state, main=world.main)

    assert world.run("resume", "01NOSUCHREQUEST000000000000") == 1  # REFUSED
    assert "merge_request: sync: ran" in capsys.readouterr().err


def test_a_sync_past_the_drain_bound_is_reported_still_running(world, monkeypatch, capsys):
    _hub(world, monkeypatch)
    monkeypatch.setattr(world.mod, "SYNC_TIMEOUT_S", 1)  # the drain's bound (this process only)
    _fake_sync(world, monkeypatch, "time.sleep(4)\nmarker.write_text('done')\n")
    _sync_landing(world)

    assert world.run("merge") == 0
    assert "merge_request: sync: still running in the background (pid " in capsys.readouterr().err
    end = time.monotonic() + 30  # let the runner finish inside the test
    while time.monotonic() < end and not world.sync_marker.exists():
        time.sleep(0.1)
    assert world.sync_marker.read_text() == "done"


# W-73d00b05: capped_run.sh's EXIT trap stops its scope, and a start_new_session runner is still in
# it — so a runner alive when merge_request.py exits died with its sync. It now starts in its own
# bounded transient scope when one can start, bare otherwise.
_RUNNER = [sys.executable, "merge_request.py", "sync-runner", "--state", "s", "--", "sync"]


def _probe_ran(monkeypatch, mod, result) -> list[list[str]]:
    """Stub the scope probe's subprocess.run: ``result`` is an exit code or an exception to raise."""
    mod._SCOPE.clear()
    calls: list[list[str]] = []

    def run(argv, **_kw):
        calls.append(list(argv))
        if isinstance(result, BaseException):
            raise result
        return subprocess.CompletedProcess(argv, result)

    monkeypatch.setattr(mod.subprocess, "run", run)
    return calls


@pytest.mark.parametrize(
    "result",
    [1, OSError("no systemd-run"), subprocess.TimeoutExpired("systemd-run", 10)],
    ids=["refused", "absent", "timeout"],
)
def test_the_runner_starts_bare_when_no_scope_can_start(world, monkeypatch, result):
    calls = _probe_ran(monkeypatch, world.mod, result)

    assert world.mod._runner_scope(_RUNNER, {}) == _RUNNER
    assert world.mod._runner_scope(_RUNNER, {}) == _RUNNER
    assert len(calls) == 1  # one probe per process, its answer kept


def test_the_runner_starts_in_its_own_bounded_scope(world, monkeypatch):
    mod = world.mod
    calls = _probe_ran(monkeypatch, mod, 0)

    argv = mod._runner_scope(_RUNNER, {})
    cut = argv.index("--")
    prefix, tail = argv[:cut], argv[cut + 1 :]
    assert tail == _RUNNER
    assert prefix[:4] == ["systemd-run", "--user", "--scope", "-q"]
    for flag in (
        "--collect",
        "--slice=fabrik-agents.slice",
        f"RuntimeMaxSec={mod.SYNC_RUNNER_MAX_S}",
        f"MemoryMax={mod.SYNC_RUNNER_MEM}",
        "MemorySwapMax=0",
        "TimeoutStopSec=5",
    ):
        assert flag in prefix, (flag, prefix)
    assert any(p.startswith("--unit=fabrik-sync-runner-") for p in prefix), prefix
    # the probe ran the SAME flags (a property the manager refuses fails the probe, not the start)
    (probe,) = calls
    assert probe[probe.index("--") + 1 :] == ["true"]
    strip = [p for p in probe[: probe.index("--")] if not p.startswith("--unit=")]
    assert strip == [p for p in prefix if not p.startswith("--unit=")]
    # the backstop outlasts a runner that retires at its soft deadline mid-way through no sync
    assert mod.SYNC_RUNNER_MAX_S >= mod.SYNC_RUNNER_SOFT_S + mod.SYNC_TIMEOUT_S
    assert mod.SYNC_RUNNER_SOFT_S >= mod.QUEUE_WALL_S + mod.SYNC_LOCK_WAIT_S


def test_a_runner_past_its_soft_deadline_runs_no_sync(world, monkeypatch, tmp_path):
    mod = world.mod
    state = tmp_path / "state"
    state.mkdir()
    (state / "sync-owed.log").write_text("owed\n")
    marker = tmp_path / "synced-past-deadline"
    monkeypatch.setattr(mod, "SYNC_RUNNER_SOFT_S", 0)

    rc = mod._sync_runner(state, [sys.executable, "-c", f"open({str(marker)!r}, 'w')"])

    assert rc == 0
    assert not marker.exists()
    assert not (state / "sync-done").exists()  # the debt stays owed for the next kick
    status = json.loads((state / "sync-status.txt").read_text())
    assert status["rc"] == 0 and "retired at its bound" in status["tail"]


_CAPPED = SCRIPTS / "capped_run.sh"
_KICK_AND_EXIT = """\
import importlib.util, os, sys, pathlib
spec = importlib.util.spec_from_file_location("mr_w73", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
state, marker = pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
mod.SYNC_ARGV = [sys.executable, "-c",
                 f"import time; time.sleep(3); open({str(marker)!r}, 'w').write('done')"]
state.mkdir(parents=True, exist_ok=True)
(state / "sync-owed.log").write_text("owed\\n")
mod._kick_sync(state.parent, state)
os._exit(0)  # exit at once, no drain: the wrapper stops its scope while the sync still sleeps
"""


def test_a_runner_outlives_its_merge_process_under_capped_run(world, tmp_path):
    probe = world.mod
    probe._SCOPE.clear()
    if not probe._scope_ok(probe._runner_env(dict(os.environ))):
        pytest.skip("no transient user scope can start here (capped_run then runs uncapped)")
    child = tmp_path / "kick.py"
    child.write_text(_KICK_AND_EXIT)
    state, marker = tmp_path / "fabrik-merge", tmp_path / "synced-after-exit"

    run = subprocess.run(
        [str(_CAPPED), "--timeout", "60", "--", sys.executable, str(child), str(SCRIPT),
         str(state), str(marker)],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert run.returncode == 0, run.stderr
    end = time.monotonic() + 30
    while time.monotonic() < end and not marker.exists():
        time.sleep(0.2)
    assert marker.exists() and marker.read_text() == "done", "the runner died with its wrapper"
    end = time.monotonic() + 15  # the runner writes sync-done after its sync
    while time.monotonic() < end and not (state / "sync-done").exists():
        time.sleep(0.2)
    assert int((state / "sync-done").read_text()) == (state / "sync-owed.log").stat().st_size


def test_a_debt_left_by_a_killed_run_runs_at_the_next_landing(world, monkeypatch):
    state = _hub(world, monkeypatch)
    state.mkdir(parents=True, exist_ok=True)
    (state / "sync-owed.log").write_text("2026-10-30T00:59:53 left by a killed run\n")
    world.send(world.branch({"notes.txt": "a landing that owes no sync\n"}))

    assert world.run("merge") == 0
    assert world.sync_marker.read_text() == "x"


def test_a_runner_waits_for_a_held_sync_lock_then_runs(world, monkeypatch):
    import threading

    state = _hub(world, monkeypatch)
    _fake_sync(world, monkeypatch, "marker.write_text('ran')\n")
    _sync_landing(world)
    state.mkdir(parents=True, exist_ok=True)
    fd = os.open(state / "sync.lock", os.O_RDWR | os.O_CREAT, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX)  # another process's sync holds it
    synced_while_held: list[bool] = []

    def release() -> None:
        # hold until this landing owed its sync (or 30 s), then 2 s more: a sync that ran while
        # the lock was held has written the marker by now
        end = time.monotonic() + 30
        while not (state / "sync-owed.log").exists() and time.monotonic() < end:
            time.sleep(0.1)
        time.sleep(2)
        synced_while_held.append(world.sync_marker.exists())
        os.close(fd)

    t = threading.Thread(target=release)
    t.start()
    try:
        assert world.run("merge") == 0
    finally:
        t.join()
    assert synced_while_held == [False]
    assert world.sync_marker.read_text() == "ran"


def test_no_sync_is_owed_outside_the_hub(world, monkeypatch):
    world.write(".pre-commit-config.yaml", _SYNC_CONFIG)
    world.commit_main("hooks", ".pre-commit-config.yaml")
    _sync_landing(world)  # HUB_CHECKOUT stays /opt/fabrik: this checkout is not the hub

    assert world.run("merge") == 0
    assert not world.sync_marker.exists()
    assert not (world.main / ".git" / "fabrik-merge" / "sync-owed.log").exists()


# --- (c): the owner's tests import the MERGED tree and reach ../fabrik-lib -------------------
def test_owner_tests_see_the_merged_src_first_and_the_fabrik_lib_link(world):
    (world.tmp / "fabrik-lib").mkdir()
    probe = world.tmp / "probe"
    script = (
        "import os, pathlib; "
        "first = os.environ['PYTHONPATH'].split(os.pathsep)[0]; "
        f"pathlib.Path({str(probe)!r}).write_text(' '.join(["
        "str(first == os.path.join(os.getcwd(), 'src')), "
        "str(os.path.isdir('../fabrik-lib')), os.path.basename(os.getcwd())]))"
    )
    world.write(".fabrik/merge-tests", f'python3 -c "{script}"\n')
    world.commit_main("owner tests", ".fabrik/merge-tests")
    world.send(world.branch({"x.txt": "x\n"}))

    assert world.run("merge") == 0
    assert probe.read_text() == "True True proj"
    assert world.scratch_left() == []


def test_owner_tests_see_the_worktreeinclude_files_the_main_checkout_holds(world):
    """brand-identiy-creator 01M46NZMP4F08KBP7WC8KF1Z37: the build tree is a fresh checkout, so a
    pydantic-settings app whose Settings() reads the gitignored `.env` failed at import and a
    correct request was refused. The base's `.worktreeinclude` set is copied in from the main
    checkout, as Claude Code copies it into a new worktree — a file the tree already tracks is
    never overwritten, and a path outside the checkout is never read."""
    probe = world.tmp / "env-probe"
    world.write(
        ".worktreeinclude",
        "# comment\n.env\nlocal/\ntracked.cfg\n../outside.txt\nlink.env\nlink_dir/\n",
    )
    world.write("tracked.cfg", "base\n")
    world.commit_main("include list", ".worktreeinclude", "tracked.cfg")
    world.write(".env", "DATABASE_URL=postgresql://u:p@h/app\n")  # untracked, as gitignored
    world.write("secret.txt", "unlisted\n")
    world.write("realdir/x.txt", "unlisted\n")
    (world.main / "link_dir").symlink_to(world.main / "realdir")  # a listed dir symlink too
    (world.main / "link.env").symlink_to(world.main / "secret.txt")  # a listed symlink is skipped
    # the owner's uncommitted edit to the list is never read: the BASE's list governs
    world.write(".worktreeinclude", "# comment\n.env\nlocal/\ntracked.cfg\nextra.txt\n")
    world.write("extra.txt", "never\n")
    world.write("local/deep/a.txt", "a\n")
    world.write("tracked.cfg", "dirty in main\n")  # the owner's uncommitted edit
    (world.tmp / "outside.txt").write_text("never\n", encoding="utf-8")
    script = (
        "import os, pathlib; "
        f"pathlib.Path({str(probe)!r}).write_text(' '.join(["
        "open('.env').read().strip(), open('local/deep/a.txt').read().strip(), "
        "open('tracked.cfg').read().strip(), str(os.path.exists('../outside.txt')), "
        "str(os.path.lexists('link.env') or os.path.exists('secret.txt') "
        "or os.path.lexists('link_dir')), "
        "str(os.path.exists('extra.txt'))]))"
    )
    world.write(".fabrik/merge-tests", f'python3 -c "{script}"\n')
    world.commit_main("owner tests", ".fabrik/merge-tests")
    _git(world.wt, "merge", "-q", "--ff-only", "master")
    world.send(world.branch({"x.txt": "x\n"}))

    assert world.run("merge") == 0
    got = probe.read_text()
    assert got == "DATABASE_URL=postgresql://u:p@h/app a base False False False", got
    assert world.scratch_left() == []


def test_owner_tests_read_an_ignored_worktreeinclude_from_the_main_checkout(world):
    """brand-identiy-creator 01M48K5ZGYWBX1F4S8K8GQ32E0: every synced project IGNORES
    `.worktreeinclude` (the synced .gitignore block), so `git show <base>:.worktreeinclude` failed,
    nothing was copied and the owner tests refused every correct merge. An ignored list is read
    from the main checkout's working tree."""
    probe = world.tmp / "env-probe"
    world.write(".gitignore", ".worktreeinclude\n.env\nlocal/\n")
    script = (
        f"import pathlib; pathlib.Path({str(probe)!r}).write_text("
        "open('.env').read().strip() + ' ' + open('local/deep/a.txt').read().strip())"
    )
    world.write(".fabrik/merge-tests", f'python3 -c "{script}"\n')
    world.commit_main("ignore + owner tests", ".gitignore", ".fabrik/merge-tests")
    world.write(".worktreeinclude", ".env\nlocal/\n")  # sync-written, ignored, never tracked
    world.write(".env", "DATABASE_URL=postgresql://u:p@h/app\n")
    world.write("local/deep/a.txt", "a\n")
    _git(world.wt, "merge", "-q", "--ff-only", "master")
    world.send(world.branch({"x.txt": "x\n"}))

    assert world.run("merge") == 0
    assert probe.read_text() == "DATABASE_URL=postgresql://u:p@h/app a"
    assert world.scratch_left() == []


def test_no_readable_worktreeinclude_is_named_in_the_refusal_not_silent(world):
    """The same report: the failed read was a silent no-op, so the refusal named only the red test.
    With no list at the base and none ignored in the main checkout, the owner-tests refusal says
    so — the reason the requester reads carries it."""
    world.write(".fabrik/merge-tests", "exit 1\n")
    world.commit_main("owner tests", ".fabrik/merge-tests")
    world.write(".worktreeinclude", ".env\n")  # untracked but NOT ignored: never read
    _git(world.wt, "merge", "-q", "--ff-only", "master")
    msg = world.send(world.branch({"x.txt": "x\n"}))

    assert world.run("merge") != 0
    reason = world.record(msg)["reason"]
    assert "owner tests red" in reason and ".worktreeinclude" in reason, reason


def test_no_worktreeinclude_on_a_green_merge_prints_a_note(world, capsys):
    """A green merge with no readable list still says so on stderr, once."""
    world.send(world.branch({"x.txt": "x\n"}))
    assert world.run("merge") == 0
    err = capsys.readouterr().err
    assert err.count(".worktreeinclude") == 1, err


def test_the_note_survives_a_rebuild_and_a_partial_exit_once(world, capsys):
    """Review pass 1 (A-S1, B-S1): a base that moves mid-build rebuilds with a new `old`, and a
    note keyed on the sha printed twice; a post-CAS push rejection exits PARTIAL past the only
    print of the notes. One note, on the PARTIAL exit too."""
    world.send(world.branch({"x.txt": "x\n"}))
    calls: list[str] = []
    pushed: list[str] = []

    def phase(name):
        if name == "after-build":
            calls.append(name)
            if len(calls) == 1:
                world.write("bump.txt", "bump\n")
                world.commit_main("pipeline commit", "bump.txt")
        if name == "before-push" and not pushed:
            pushed.append(world.push_from_elsewhere("README.md", "elsewhere\n"))

    assert world.run("merge", phase=phase) == 4
    assert len(calls) == 2  # it did rebuild
    err = capsys.readouterr().err
    assert err.count(".worktreeinclude") == 1, err


# --- (c) fallback: touched tests run with the merged src AFTER the stdlib (wef 01M453XP8W) ------
_SHADOW_TEST = """\
import os, pathlib, subprocess, sys
import copy
import xml.etree.ElementTree as ET
import mypkg


def test_x():
    src = os.path.join(os.getcwd(), "src")
    assert hasattr(copy, "deepcopy"), copy.__file__
    assert ET.fromstring("<a/>").tag == "a"
    assert mypkg.__file__.startswith(src + os.sep), mypkg.__file__
    child = subprocess.run(
        [sys.executable, "-c", "import mypkg; print(mypkg.__file__)"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert child.startswith(src + os.sep), child
    pathlib.Path(os.environ["SHADOW_MARK"]).write_text("ran")
"""


def _shadow_branch(world, monkeypatch, test=_SHADOW_TEST):
    mark = world.tmp / "shadow-ran"
    monkeypatch.setenv("SHADOW_MARK", str(mark))
    head = world.branch(
        {
            "src/copy/__init__.py": "# a project package named like the stdlib's copy\n",
            "src/mypkg/__init__.py": "MERGED = True\n",
            "tests/test_x.py": test,
        }
    )
    return head, mark


def test_owner_tests_run_with_the_merge_check_signal_in_both_legs(world, monkeypatch):
    """W-c3177526: the owner tests run BEFORE the merge's render reaches ~/.claude, so both legs tell
    them so — FABRIK_MERGE_CHECK=1, which the hub conftest reads to skip its live-box tests. The
    caller's own value is removed first: this grader itself runs inside merge checks."""
    monkeypatch.delenv("FABRIK_MERGE_CHECK", raising=False)
    owner = world.tmp / "owner-leg"
    world.write(
        ".fabrik/merge-tests",
        f"python3 -c \"import os; open({str(owner)!r}, 'w').write(os.environ.get('FABRIK_MERGE_CHECK', 'unset'))\"\n",
    )
    world.commit_main("owner tests", ".fabrik/merge-tests")
    world.send(world.branch({"x.txt": "x\n"}))
    assert world.run("merge") == 0
    assert owner.read_text() == "1"

    world.write(".fabrik/merge-tests", "")
    world.commit_main("no owner tests", ".fabrik/merge-tests")
    fallback = world.tmp / "fallback-leg"
    monkeypatch.setenv("SIGNAL_MARK", str(fallback))
    test = (
        "import os, pathlib\n"
        "def test_signal():\n"
        "    pathlib.Path(os.environ['SIGNAL_MARK']).write_text(os.environ.get('FABRIK_MERGE_CHECK', 'unset'))\n"
    )
    world.send(world.branch({"tests/test_signal.py": test}))
    assert world.run("merge") == 0
    assert fallback.read_text() == "1"
    assert os.environ.get("FABRIK_MERGE_CHECK") is None


def test_fallback_tests_import_a_stdlib_named_src_package_without_shadowing(world, monkeypatch):
    head, mark = _shadow_branch(world, monkeypatch)
    msg_id = world.send(head)

    assert world.run("merge") == 0
    assert mark.read_text() == "ran"
    assert world.scratch_left() == []
    assert "pytest tests/test_x.py under " in world.replies(msg_id)["intel"]


def test_fallback_ignores_the_callers_pythonpath(world, monkeypatch):
    decoy = world.main / ".claude" / "worktrees" / "peer" / "src"
    (decoy / "mypkg").mkdir(parents=True)
    (decoy / "mypkg" / "__init__.py").write_text("DECOY = True\n", encoding="utf-8")
    ambient = world.tmp / "ambient"  # an unrelated repo's src the caller's shell exports
    (ambient / "copy").mkdir(parents=True)
    (ambient / "copy" / "__init__.py").write_text("AMBIENT = True\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join([str(decoy), str(ambient)]))
    head, mark = _shadow_branch(world, monkeypatch)
    world.send(head)

    assert world.run("merge") == 0
    assert mark.read_text() == "ran"
    assert world.scratch_left() == []


def test_fallback_runs_the_main_checkouts_venv_python(world, monkeypatch):
    used = world.tmp / "venv-used"
    venv = world.main / ".venv" / "bin" / "python"
    venv.parent.mkdir(parents=True)
    venv.write_text(f'#!/bin/sh\necho x > "{used}"\nexec "{sys.executable}" "$@"\n')
    venv.chmod(0o755)
    head, mark = _shadow_branch(world, monkeypatch)
    msg_id = world.send(head)

    assert world.run("merge") == 0
    assert used.read_text() == "x\n" and mark.read_text() == "ran"
    assert f"under {venv}: green" in world.replies(msg_id)["intel"]
    assert world.scratch_left() == []


def test_fallback_src_beats_a_copy_installed_in_the_venvs_site_packages(world, monkeypatch):
    """The reason ``src`` went first at all: an editable install of the main checkout lives in
    site-packages and would otherwise grade master, not the merge."""
    venv = world.main / ".venv"
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True, timeout=120
    )
    py = venv / "bin" / "python"
    site_dir = subprocess.run(
        [str(py), "-c", "import site; print(site.getsitepackages()[0])"],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout.strip()
    import _pytest  # the outer interpreter's pytest, reachable from the new venv

    outer = str(Path(_pytest.__file__).resolve().parent.parent)
    Path(site_dir, "outer.pth").write_text(outer + "\n", encoding="utf-8")
    Path(site_dir, "mypkg").mkdir()
    Path(site_dir, "mypkg", "__init__.py").write_text("INSTALLED = True\n", encoding="utf-8")
    head, mark = _shadow_branch(world, monkeypatch)
    world.send(head)

    assert world.run("merge") == 0
    assert mark.read_text() == "ran"
    assert world.scratch_left() == []


def test_fallback_a_package_style_src_is_imported_from_the_tree_root(world, monkeypatch):
    """wef 01M3WW45D0QVW14KJQW70PFE2P: src/__init__.py makes the ROOT the import root (`src.x`);
    src/ itself is not, so its stdlib-named package is never a top-level `copy`."""
    mark = world.tmp / "pkg-ran"
    monkeypatch.setenv("SHADOW_MARK", str(mark))
    test = (
        "import os, pathlib, subprocess, sys\n"
        "import importlib.util\n"
        "import copy\n"
        "import src.copy\n\n\n"
        "def test_x():\n"
        "    assert hasattr(copy, 'deepcopy')\n"
        "    assert importlib.util.find_spec('mypkg') is None\n"
        "    child = subprocess.run([sys.executable, '-c', 'import src.mypkg, os; print(src.mypkg.__file__)'],\n"
        "                           cwd='/', capture_output=True, text=True, check=True).stdout.strip()\n"
        "    assert child.startswith(os.path.join(os.getcwd(), 'src') + os.sep), child\n"
        "    pathlib.Path(os.environ['SHADOW_MARK']).write_text('ran')\n"
    )
    world.send(
        world.branch(
            {
                "src/__init__.py": "",
                "src/copy/__init__.py": "LOCAL = True\n",
                "src/mypkg/__init__.py": "MERGED = True\n",
                "tests/test_x.py": test,
            }
        )
    )

    assert world.run("merge") == 0
    assert mark.read_text() == "ran"
    assert world.scratch_left() == []


def test_a_red_fallback_test_refuses_the_merge(world, monkeypatch, capsys):
    head, _ = _shadow_branch(world, monkeypatch, test="def test_x():\n    assert False\n")
    old = world.base()
    world.send(head)

    assert world.run("merge") == 1
    assert world.base() == old
    assert "owner tests red (pytest tests/test_x.py under" in capsys.readouterr().err


# --- review round 1 ---------------------------------------------------------------------------
def _second_branch(world, rel: str) -> str:
    """A second requester branch off the initial commit, pushed."""
    wt2 = world.tmp / "wt2"
    root = _git(world.main, "rev-list", "--max-parents=0", "master")
    _git(world.main, "worktree", "add", "-q", "-b", "feat2", str(wt2), root)
    world.write(rel, "second\n", root=wt2)
    _git(wt2, "add", "--", rel)
    _git(wt2, "commit", "-q", "-m", "second branch")
    _git(wt2, "push", "-q", "origin", "feat2")
    return _git(wt2, "rev-parse", "HEAD")


def _reject_push_with(world, rel: str, text: str):
    pushed: list[str] = []

    def race(name):
        if name == "before-push" and not pushed:
            pushed.append(world.push_from_elsewhere(rel, text))

    return race


# 1 — a refused catch-up never wedges the owner
def test_a_refused_catch_up_is_parked_and_never_blocks_the_inbox(world, capsys):
    msg_id = world.send(world.branch({"README.md": "branch readme\n"}))
    assert world.run("merge", phase=_reject_push_with(world, "README.md", "elsewhere\n")) == 4
    capsys.readouterr()

    assert world.run("resume", msg_id) == 4  # origin and local diverge in README.md

    err = capsys.readouterr().err
    rec = world.record(msg_id)
    assert rec["phase"] == "catchup-refused" and rec["merge_sha"]
    assert "diverged in README.md" in err and f"merge_request.py resume {msg_id}" in err
    assert "rebase on" not in rec["reason"]
    rec_path = world.main / ".git" / "fabrik-merge" / f"{msg_id}.json"
    rec.update(pid=_dead_pid(), start="1")
    rec_path.write_text(json.dumps(rec), encoding="utf-8")
    other = world.send(_second_branch(world, "z.txt"), branch="feat2")

    assert world.run("merge") == 4  # never wedged: it returns, naming the parked request

    assert other in world.inbox() and world.replies(other) == {}  # O11: the inbox waits
    assert world.record(msg_id)["phase"] == "catchup-refused"
    assert "skipping" in capsys.readouterr().err
    assert world.run("resume", msg_id) == 4  # only an explicit resume retries it


# 3 — the body's branch is a branch name, never a refspec or an option
@pytest.mark.parametrize("bad", ["-upload-pack=x", "a..b", "x:refs/heads/master"])
def test_a_malformed_branch_field_refuses_before_any_fetch(world, bad):
    msg_id = world.send(world.branch({"x.txt": "x\n"}), branch=bad)
    old = world.base()

    assert world.run("merge") == 1
    assert world.base() == old and "disposition: blocked" in world.archived(msg_id)


# 4 — after the CAS, every failure is PARTIAL (4), never a refusal (1)
def test_a_reply_timeout_after_the_cas_is_partial(world, monkeypatch):
    msg_id = world.send(world.branch({"x.txt": "x\n"}))
    real = world.mod._mail_cli

    def flaky(ctx, *args, **kw):
        if args[0] == "send":
            raise world.mod.TimedOutError("mail.py send timed out")
        return real(ctx, *args, **kw)

    monkeypatch.setattr(world.mod, "_mail_cli", flaky)
    assert world.run("merge") == 4
    assert world.origin() == world.base() == world.record(msg_id)["merge_sha"]


# W-d0bbb94d — an unreachable remote defers (step a) or stays PARTIAL (catch-up), never refuses
def _origin_gone(world) -> str:
    url = _git(world.main, "remote", "get-url", "origin")
    _git(world.main, "remote", "set-url", "origin", str(world.tmp / "gone.git"))
    return url


def _pid_gone(world, msg_id: str) -> None:
    path = world.main / ".git" / "fabrik-merge" / f"{msg_id}.json"
    rec = json.loads(path.read_text())
    rec.update(pid=_dead_pid(), start="123")
    path.write_text(json.dumps(rec))


def test_an_unreachable_remote_defers_and_replies_nothing(world, capsys):
    msg_id = world.send(world.branch({"x.txt": "x\n"}))
    _origin_gone(world)
    old = world.base()

    assert world.run("merge") == 1

    rec = world.record(msg_id)
    assert rec["phase"] == "claimed" and rec.get("outcome") != "refused", rec
    assert "(a) preflight" in rec["deferred"]
    assert world.replies(msg_id) == {} and "disposition:" not in world.archived(msg_id)
    assert world.base() == old
    assert f"DEFERRED {msg_id}" in capsys.readouterr().err


def test_a_deferred_request_merges_on_the_next_run(world):
    msg_id = world.send(world.branch({"x.txt": "x\n"}))
    url = _origin_gone(world)
    assert world.run("merge") == 1
    _git(world.main, "remote", "set-url", "origin", url)
    _pid_gone(world, msg_id)

    assert world.run("merge") == 0

    rec = world.record(msg_id)
    assert rec["phase"] == "replied" and "deferred" not in rec, rec
    assert "outcome: merged" in world.replies(msg_id)["fleet"]


def test_a_fetch_timeout_defers(world, monkeypatch):
    msg_id = world.send(world.branch({"x.txt": "x\n"}))
    real = world.mod._run

    def slow(argv, *a, **kw):
        if argv[:2] == ["git", "fetch"]:
            raise world.mod.TimedOutError("git fetch -q timed out after 60s")
        return real(argv, *a, **kw)

    monkeypatch.setattr(world.mod, "_run", slow)
    assert world.run("merge") == 1
    rec = world.record(msg_id)
    assert rec["phase"] == "claimed" and "timed out" in rec["deferred"], rec
    assert world.replies(msg_id) == {}


def test_a_missing_remote_ref_still_refuses(world):
    _git(world.main, "branch", "rel")  # a local base the reachable origin does not have
    msg_id = world.send(world.branch({"x.txt": "x\n"}), base="rel")

    assert world.run("merge") == 1

    rec = world.record(msg_id)
    assert rec["phase"] == "replied" and rec["outcome"] == "refused", rec
    assert "deferred" not in rec
    assert "outcome: refused" in world.replies(msg_id)["fleet"]


def test_a_deferral_claims_nothing_from_the_inbox(world):
    first = world.send(world.branch({"x.txt": "x\n"}))
    head2 = world.branch({"y.txt": "y\n"})  # pushed while origin is still reachable
    _origin_gone(world)
    assert world.run("merge") == 1
    _pid_gone(world, first)
    second = world.send(head2)

    assert world.run("merge") == 1

    assert world.record(first)["phase"] == "claimed"
    assert second in world.inbox()


def test_one_fetch_per_unreachable_remote_per_run(world, monkeypatch):
    first = world.send(world.branch({"x.txt": "x\n"}))
    head2 = world.branch({"y.txt": "y\n"})
    _origin_gone(world)
    assert world.run("merge") == 1
    second = world.send(head2)
    assert world.run("merge", second) == 1  # claimed by id: both records now deferred
    _pid_gone(world, first)
    _pid_gone(world, second)
    fetches: list[list[str]] = []
    real = world.mod._run

    def counting(argv, *a, **kw):
        if argv[:2] == ["git", "fetch"]:
            fetches.append(argv)
        return real(argv, *a, **kw)

    monkeypatch.setattr(world.mod, "_run", counting)
    assert world.run("merge") == 1

    assert len(fetches) == 1, fetches  # the second record deferred without its own timeout
    assert "earlier in this run" in world.record(second)["deferred"]
    assert world.record(first)["phase"] == world.record(second)["phase"] == "claimed"


def test_an_unreachable_remote_never_starves_a_request_on_another(world):
    other = world.tmp / "other.git"
    _git(world.tmp, "clone", "-q", "--bare", str(world.remote), str(other))
    _git(world.main, "remote", "add", "other", str(other))
    _git(world.main, "branch", "-q", "rel", "master")
    _git(world.main, "config", "branch.rel.remote", "other")
    _git(world.main, "push", "-q", "other", "rel")
    first = world.send(world.branch({"x.txt": "x\n"}))
    head2 = world.branch({"y.txt": "y\n"})
    _origin_gone(world)
    assert world.run("merge") == 1
    _pid_gone(world, first)
    second = world.send(head2, base="rel")

    world.run("merge")  # the stranded record defers again; the reachable request still merges

    assert world.record(first)["phase"] == "claimed"
    assert world.record(second)["phase"] == "replied"
    assert "outcome: merged" in world.replies(second)["fleet"]


def test_an_unreachable_catch_up_is_partial_not_parked(world):
    msg_id = world.send(world.branch({"x.txt": "x\n"}))
    assert world.run("merge", phase=_reject_push_with(world, "y.txt", "y\n")) == 4
    _origin_gone(world)

    assert world.run("resume", msg_id) == 4

    assert world.record(msg_id)["phase"] == "carried"


def test_a_failed_catch_up_fetch_on_resume_is_partial(world):
    msg_id = world.send(world.branch({"x.txt": "x\n"}))
    assert world.run("merge", phase=_reject_push_with(world, "y.txt", "y\n")) == 4
    _git(world.main, "remote", "set-url", "origin", str(world.tmp / "gone.git"))

    assert world.run("resume", msg_id) == 4


# 5 — each path is re-hashed immediately before it is written
def test_a_path_edited_after_the_carry_snapshot_is_never_overwritten(world, monkeypatch):
    msg_id = world.send(world.branch({"README.md": "branch readme\n"}))
    armed: list[bool] = []
    real = world.mod._snapshot

    def snapshot(cwd, paths):
        out = real(cwd, paths)
        if armed and armed.pop():
            world.write("README.md", "edited inside the carry\n")
        return out

    monkeypatch.setattr(world.mod, "_snapshot", snapshot)
    assert (
        world.run("merge", phase=lambda n: armed.append(True) if n == "before-carry" else None) == 0
    )
    assert world.read("README.md") == "edited inside the carry\n"
    assert "README.md" in world.replies(msg_id)["fleet"].split("not carried:", 1)[1]


# 6 — the record exists before the claim
@pytest.mark.parametrize("claimed", [True, False])
def test_a_claiming_record_is_continued_or_reclaimed(world, claimed):
    msg_id = _strand(world, _dead_pid(), "1", phase="claiming", claim=claimed)

    assert world.run("merge") == 0

    assert world.record(msg_id)["phase"] == "replied" and msg_id not in world.inbox()
    assert _git(world.main, "rev-parse", "master^2") == world.record(msg_id)["head"]


def test_the_record_is_written_before_mail_claim_runs(world, monkeypatch):
    msg_id = world.send(world.branch({"x.txt": "x\n"}))
    real = world.mod._mail_cli
    seen: list[str] = []

    def spy(ctx, *args, **kw):
        if args[0] == "claim":
            seen.append(world.record(msg_id)["phase"])
        return real(ctx, *args, **kw)

    monkeypatch.setattr(world.mod, "_mail_cli", spy)
    assert world.run("merge") == 0
    assert seen == ["claiming"]


# 7 — an unreadable record never blocks the run
def test_an_unreadable_record_is_skipped_with_a_warning(world, capsys):
    records = world.main / ".git" / "fabrik-merge"
    records.mkdir()
    (records / "01BADBADBADBADBADBADBADBAD.json").write_text("{not json", encoding="utf-8")
    msg_id = world.send(world.branch({"x.txt": "x\n"}))

    assert world.run("merge") == 0
    assert world.record(msg_id)["phase"] == "replied"
    assert "unreadable" in capsys.readouterr().err


# 8 — a stale throwaway worktree is removed and pruned
def test_a_stale_throwaway_worktree_is_removed(world):
    stale = world.tmp / "scratch" / "fabrik-merge-ab12cd34" / "proj"  # mkdtemp's own shape
    _git(world.main, "worktree", "add", "-q", "--detach", str(stale), "master")
    before = world.worktrees()
    assert f"worktree {stale}" in before

    assert world.run("merge") == 0

    assert f"worktree {stale}" not in world.worktrees() and world.scratch_left() == []


# O12 — the sweep touches only what this tool created, under its own temp root
@pytest.mark.parametrize(
    "where",
    [
        "elsewhere/fabrik-merge-ab12cd34/proj",  # right name, outside the temp root
        "scratch/fabrik-merge-mine/proj",  # under the root, not mkdtemp's name
        "scratch/fabrik-merge-ab12cd34/other",  # mkdtemp's dir, not <repo basename>
        "scratch/x/fabrik-merge-ab12cd34/proj",  # nested below the root, not directly under
    ],
)
def test_the_sweep_never_touches_a_worktree_it_did_not_create(world, where):
    keep = world.tmp / where
    _git(world.main, "worktree", "add", "-q", "--detach", str(keep), "master")
    (keep.parent / "sibling-data.txt").write_text("not ours\n", encoding="utf-8")

    assert world.run("merge") == 0

    assert f"worktree {keep}" in world.worktrees()
    assert (keep / "README.md").is_file() and (keep.parent / "sibling-data.txt").is_file()


# 9 — a checkout that moved onto base after the preflight is preflighted again
def test_a_main_checkout_switched_onto_base_after_preflight_goes_back(world):
    _git(world.main, "checkout", "-q", "-b", "side")
    msg_id = world.send(world.branch({"x.txt": "x\n"}))
    builds: list[str] = []

    def phase(name):
        if name == "after-build":
            builds.append(name)
        if name == "before-cas" and len(builds) == 1:
            _git(world.main, "checkout", "-q", "master")

    assert world.run("merge", phase=phase) == 0
    assert len(builds) == 2
    assert world.read("x.txt") == "x\n"
    assert _git(world.main, "status", "--porcelain", "--untracked-files=no") == ""
    assert world.record(msg_id)["phase"] == "replied"


# 10 — a D-id collision in the carry is not carried, the WIP stays
def test_a_d_id_collision_in_the_carry_is_listed_and_the_wip_kept(world):
    head = world.branch(
        {"docs/DECISIONS.md": DECISIONS.replace("| D-1 |", "| D-5 | branch |\n| D-1 |")}
    )
    wip = DECISIONS + "| D-5 | owner wip |\n"
    world.write("docs/DECISIONS.md", wip)
    msg_id = world.send(head)

    assert world.run("merge") == 0

    assert world.read("docs/DECISIONS.md") == wip
    staged = _git(world.main, "ls-files", "-s", "docs/DECISIONS.md").split()[1]
    assert staged == _git(world.main, "rev-parse", "master:docs/DECISIONS.md")
    listed = world.replies(msg_id)["fleet"].split("not carried:", 1)[1]
    assert "docs/DECISIONS.md" in listed and "D-5" in listed


# --- closing pass -----------------------------------------------------------------------------
# O11 — while a record is parked at catchup-refused, the inbox waits untouched
def test_a_parked_catch_up_holds_the_inbox_untouched(world, capsys):
    parked = _strand(world, _dead_pid(), "1", phase="catchup-refused")
    first = world.send(_second_branch(world, "z.txt"), branch="feat2")
    second = world.send(world.branch({"y.txt": "y\n"}))
    old = world.base()

    assert world.run("merge") == 4

    assert {first, second} <= set(world.inbox())
    for msg_id in (first, second):
        assert world.replies(msg_id) == {}
    assert world.base() == old
    err = capsys.readouterr().err
    assert parked in err and f"merge_request.py resume {parked}" in err and "by hand" in err


# O13 — a carry failure after the catch-up CAS is reported as what it is
def test_a_carry_failure_after_the_catch_up_cas_is_not_called_a_refused_catch_up(
    world, monkeypatch, capsys
):
    msg_id = world.send(world.branch({"x.txt": "x\n"}))
    assert world.run("merge", phase=_reject_push_with(world, "y.txt", "y\n")) == 4
    capsys.readouterr()
    real = world.mod._carry
    calls: list[int] = []

    def carry(ctx, base, old, new, snap):
        calls.append(1)
        if "catch up" in _git(world.main, "log", "-1", "--format=%s", new):
            raise world.mod.RefusedError("git checkout failed: disk full")
        return real(ctx, base, old, new, snap)

    monkeypatch.setattr(world.mod, "_carry", carry)

    assert world.run("resume", msg_id) == 4

    err = capsys.readouterr().err
    rec = world.record(msg_id)
    assert rec["phase"] != "catchup-refused"
    assert "by hand" not in err and "catch-up merge" in err and "committed" in err
    assert "y.txt" in err and "disk full" in err  # the paths not carried, and why
    assert "catch up" in _git(world.main, "log", "-1", "--format=%s", "master")


# O15 — the O13 report holds even when listing the paths fails too
def test_a_carry_failure_whose_path_listing_also_fails_is_still_not_parked(
    world, monkeypatch, capsys
):
    msg_id = world.send(world.branch({"x.txt": "x\n"}))
    assert world.run("merge", phase=_reject_push_with(world, "y.txt", "y\n")) == 4
    capsys.readouterr()
    real_carry, real_paths = world.mod._carry, world.mod._merged_paths
    failing: list[bool] = []

    def carry(ctx, base, old, new, snap):
        if "catch up" in _git(world.main, "log", "-1", "--format=%s", new):
            failing.append(True)
            raise world.mod.RefusedError("git checkout failed: disk full")
        return real_carry(ctx, base, old, new, snap)

    def merged_paths(cwd, old, new):
        if failing:
            raise world.mod.RefusedError("git diff failed: disk full")
        return real_paths(cwd, old, new)

    monkeypatch.setattr(world.mod, "_carry", carry)
    monkeypatch.setattr(world.mod, "_merged_paths", merged_paths)

    assert world.run("resume", msg_id) == 4

    err = capsys.readouterr().err
    assert world.record(msg_id)["phase"] != "catchup-refused"
    assert "by hand" not in err and "committed locally" in err
    assert "not carried: unknown (git diff failed: disk full)" in err


# O16 — the parked message names the remote the push actually goes to
def test_the_parked_message_names_the_push_remote_not_origin(world, capsys):
    _git(world.main, "remote", "add", "upstream", str(world.remote))
    _git(world.main, "config", "branch.master.pushRemote", "upstream")
    parked = _strand(world, _dead_pid(), "1", phase="catchup-refused")

    assert world.run("merge") == 4

    err = capsys.readouterr().err
    assert parked in err and "merge upstream/master into master by hand" in err
    assert "origin/master" not in err


# O14 — with no snapshot (a resume of a head already in base) a dirty ledger is 3-way merged
def test_a_dirty_ledger_with_no_snapshot_is_three_way_merged_keeping_the_wip(world):
    head = world.branch(
        {
            "CHANGELOG.md": CHANGELOG.replace(
                "## [Unreleased]\n\n", "## [Unreleased]\n\n### Added — o14 branch entry\n\n"
            )
        }
    )
    msg_id = world.send(head)
    old = world.base()
    tree = _git(world.main, "rev-parse", f"{head}^{{tree}}")
    msg = f"merge(infra): feat — request {msg_id}, item none"
    merge = _git(world.main, "commit-tree", "-p", old, "-p", head, "-m", msg, tree)
    _git(world.main, "update-ref", "refs/heads/master", merge, old)  # index and files stay at old
    world.write("CHANGELOG.md", CHANGELOG + "- owner wip\n")

    assert world.run("resume", msg_id) == 0

    text = world.read("CHANGELOG.md")
    assert "### Added — o14 branch entry" in text and text.endswith("- owner wip\n")
    # exactly the WIP line over the merge: one line added, nothing of the merge missing
    numstat = _git(world.main, "diff", "--numstat", "HEAD", "--", "CHANGELOG.md")
    assert numstat.split() == ["1", "0", "CHANGELOG.md"]
    assert "not carried" not in world.replies(msg_id)["fleet"]


# --- W-9c2f371a (fabrik-lib 01M3TVN8): a refusal tells the REQUESTER to merge, never rebase ------
# `request` requires the branch pushed, so a rebase could only be republished with --force, a
# universal HARD STOP; `git merge <base>` into the branch pushes fast-forward.


def _base_edits_readme(world):
    head = world.branch({"README.md": "branch readme\n"})
    world.write("README.md", "base readme\n")
    world.commit_main("base edits readme", "README.md")
    return head


def _rebase_advice(text: str) -> list[str]:
    """Every word-boundary `rebase` except the one sanctioned `never a rebase`."""
    import re

    return re.findall(r"[^\n]*\brebase\b[^\n]*", text.replace("never a rebase", ""))


def test_a_ledger_conflict_refusal_says_merge_never_rebase(world):
    head, _why = _ledger_edits_existing_line(world)
    msg_id = world.send(head)
    assert world.run("merge") == 1
    reply = world.replies(msg_id)["fleet"]
    reason = next(line for line in reply.splitlines() if line.startswith("reason:"))
    assert "edits an existing line" in reason and "git merge master" in reason, reply
    assert _rebase_advice(reply) == [], reply


def test_a_conflict_refusal_and_its_how_line_say_merge_never_rebase(world):
    msg_id = world.send(_base_edits_readme(world))
    assert world.run("merge") == 1
    reply = world.replies(msg_id)["fleet"]
    assert "conflict in README.md" in reply and "HOW —" in reply, reply
    reason = next(line for line in reply.splitlines() if line.startswith("reason:"))
    how = next(line for line in reply.splitlines() if line.startswith("HOW —"))
    assert "git merge master" in reason and "never a rebase" in how, reply
    assert _rebase_advice(reply) == [], reply


def test_an_owner_wip_conflict_never_sends_the_requester_to_merge(world):
    """The owner's uncommitted ledger work conflicts, not the branch: the REASON names the owner
    and never tells the requester to merge (the HOW line's generic advice may)."""
    head, _why = _dirty_ledger_carry_conflicts(world)
    msg_id = world.send(head)
    assert world.run("merge") == 1
    reason = next(
        line for line in world.replies(msg_id)["fleet"].splitlines() if line.startswith("reason:")
    )
    assert "owner" in reason and "git merge" not in reason, reason
    assert _rebase_advice(reason) == [], reason


def test_no_requester_text_says_rebase():
    src = SCRIPT.read_text(encoding="utf-8")
    assert "rebase on" not in src and "rebase {" not in src


def test_a_tracked_file_where_the_include_list_has_a_directory_never_crashes_the_copy(tmp_path):
    """Review round 2: a listed directory whose name the merged tree tracks as a FILE raised
    FileExistsError out of the copy, an unhandled crash instead of a clean merge."""
    mod = _load_module()
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q", "-b", "master")
    (main / ".worktreeinclude").write_text("local/\n.env\n", encoding="utf-8")
    _git(main, "add", ".worktreeinclude")
    _git(main, "-c", "user.name=t", "-c", "user.email=t@x", "commit", "-q", "-m", "list")
    (main / "local").mkdir()
    (main / "local" / "deep.txt").write_text("deep\n", encoding="utf-8")
    (main / ".env").write_text("A=1\n", encoding="utf-8")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / "local").write_text("a tracked file\n", encoding="utf-8")

    class _Ctx:
        pass

    ctx = _Ctx()
    ctx.main = main
    ctx.notes = []
    assert mod._copy_worktree_include(ctx, wt, _git(main, "rev-parse", "HEAD")) is None
    assert (wt / "local").read_text(encoding="utf-8") == "a tracked file\n"
    assert (wt / ".env").read_text(encoding="utf-8") == "A=1\n"  # the rest is still copied


# W-29ba0047 (fabrik-lib 01M3TW5MF2) — a repo NAMED fabrik-lib builds its throwaway: the
# `<tmp>/fabrik-lib` link must not collide with the worktree that already holds that path.
def test_a_repo_named_fabrik_lib_builds_its_throwaway(tmp_path, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "scratch"))
    (tmp_path / "scratch").mkdir()
    for key, value in {
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }.items():
        monkeypatch.setenv(key, value)
    main = tmp_path / "fabrik-lib"
    main.mkdir()
    _git(main, "init", "-q", "-b", "master")
    (main / "README.md").write_text("lib\n", encoding="utf-8")
    _git(main, "add", "README.md")
    _git(main, "commit", "-q", "-m", "init")
    ctx = mod._Ctx(main, main / ".git", "infra")
    rec = {"id": "01TESTTHROWAWAY"}
    with mod._throwaway(ctx, rec, "master") as wt:
        assert wt.name == "fabrik-lib" and (wt / "README.md").is_file()
        assert (
            wt / ".git"
        ).exists()  # a real worktree; on HEAD the link step raised FileExistsError


def test_a_repo_without_whoami_agent_resolves_the_caller_from_claude_agent(tmp_path, monkeypatch):
    """The request told repos CLAUDE_AGENT is enough when whoami_agent.py cannot be vendored."""
    mod = _load_module()
    monkeypatch.setattr(sys, "path", list(sys.path))  # _caller_agent inserts HERE; keep it local
    monkeypatch.setattr(mod, "HERE", tmp_path)  # a scripts/ dir with no whoami_agent.py
    monkeypatch.setitem(sys.modules, "whoami_agent", None)  # the import fails
    monkeypatch.setenv("CLAUDE_AGENT", "fleet")
    assert mod._caller_agent() == "fleet"
    monkeypatch.setenv("CLAUDE_AGENT", "../etc")  # outside the agent-name grammar
    assert mod._caller_agent() == ""
    monkeypatch.delenv("CLAUDE_AGENT")
    assert mod._caller_agent() == ""


def test_mail_claim_resolves_the_caller_without_whoami_agent(monkeypatch):
    """The owner side too: mail.py's caller check falls back to a valid CLAUDE_AGENT."""
    spec = importlib.util.spec_from_file_location("mail_t03", SCRIPT.parent / "mail.py")
    mail = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mail)
    monkeypatch.setattr(mail, "_whoami", lambda: None)
    monkeypatch.setenv("CLAUDE_AGENT", "infra")
    assert mail._caller_agent() == "infra"
    monkeypatch.setenv("CLAUDE_AGENT", "Infra/../x")
    assert mail._caller_agent() == ""


def test_the_merge_request_name_grammar_is_whoami_agents():
    mod = _load_module()
    spec = importlib.util.spec_from_file_location("whoami_t03", SCRIPT.parent / "whoami_agent.py")
    who = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(who)
    assert mod._AGENT_NAME_RE.pattern == who._NAME_RE.pattern


def test_a_fabrik_lib_alias_of_the_main_checkout_links_to_the_throwaway(tmp_path, monkeypatch):
    """`<parent>/fabrik-lib -> <main>`: the throwaway's ../fabrik-lib is the commit under test."""
    mod = _load_module()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "scratch"))
    (tmp_path / "scratch").mkdir()
    for key, value in {
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }.items():
        monkeypatch.setenv(key, value)
    main = tmp_path / "lib-real"
    main.mkdir()
    _git(main, "init", "-q", "-b", "master")
    (main / "README.md").write_text("lib\n", encoding="utf-8")
    _git(main, "add", "README.md")
    _git(main, "commit", "-q", "-m", "init")
    (tmp_path / "fabrik-lib").symlink_to(main)
    ctx = mod._Ctx(main, main / ".git", "infra")
    with mod._throwaway(ctx, {"id": "01TESTALIAS"}, "master") as wt:
        assert (wt.parent / "fabrik-lib").resolve() == wt.resolve()


# --- W-c751bca6: retry a request refused for a base-side fault; name it in the refusal ---------
def _red_base_refusal(world) -> tuple[str, str]:
    """A request refused because the BASE's owner tests are red, whatever the branch carries."""
    world.write(".fabrik/merge-tests", 'python3 -c "import sys; sys.exit(3)"\n')
    world.commit_main("owner tests", ".fabrik/merge-tests")
    head = world.branch({"x.txt": "x\n"})
    msg_id = world.send(head)
    assert world.run("merge") == 1
    assert world.record(msg_id)["outcome"] == "refused"
    return head, msg_id


def _fix_base(world) -> None:
    world.write(".fabrik/merge-tests", "true\n")
    world.commit_main("fix owner tests", ".fabrik/merge-tests")


def _every_reply(world, msg_id: str, agent: str) -> list[str]:
    """Every reply threaded on ``msg_id`` to ``agent`` (``World.replies`` keeps one per addressee)."""
    out = []
    for path in sorted((world.tmp / "mail" / "proj" / "inbox").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        head = text.split("\n---", 1)[0]
        if (
            "kind: reply" in head
            and f"re: {msg_id}" in head
            and f"\nagent: {agent}\n" in head + "\n"
        ):
            out.append(text)
    return out


def test_retry_merges_a_request_refused_for_a_base_fault(world):
    """A refusal the base caused cost the requester a re-send of an identical request: `resume`
    answered "already replied" and `merge` found nothing waiting. The owner fixes the base and
    retries; the branch is merged, the mail is acked done with the merge SHA (the check a stale
    `blocked` ack would skip), and the requester can tell the current reply from the refusal."""
    head, msg_id = _red_base_refusal(world)
    _fix_base(world)

    assert world.run("retry", msg_id) == 0
    rec = world.record(msg_id)
    assert rec["phase"] == "replied" and rec["outcome"] == "merged", rec
    assert _git(world.main, "merge-base", "--is-ancestor", head, world.base(), check=False) == ""
    assert rec["retries"] and "owner tests red" in rec["retries"][0]["reason"], rec
    acks = [ln for ln in world.archived(msg_id).splitlines() if ln.startswith("acked-by:")]
    assert len(acks) == 1 and "disposition: done" in acks[0] and rec["merge_sha"] in acks[0], acks
    replies = _every_reply(world, msg_id, "fleet")
    assert len(replies) == 2, replies
    current = [r for r in replies if "outcome: merged" in r]
    assert len(current) == 1 and "retry: 1 — supersedes the refused reply" in current[0], replies


def test_retry_refuses_a_moved_branch_and_an_unrefused_request(world, capsys):
    """A branch that moved means the requester superseded this request. A merged request, or an
    id with no record, has nothing to retry. Each refusal changes nothing."""
    _head, msg_id = _red_base_refusal(world)
    _fix_base(world)
    moved = world.branch({"y.txt": "y\n"}, msg="more work")
    capsys.readouterr()
    before, archived = world.base(), world.archived(msg_id)

    assert world.run("retry", msg_id) == 1
    err = capsys.readouterr().err
    assert f"moved to {moved[:12]}" in err and "superseded" in err, err
    assert world.record(msg_id)["outcome"] == "refused" and world.base() == before
    assert world.archived(msg_id) == archived and msg_id not in world.inbox()

    ok_id = world.send(moved)
    assert world.run("merge") == 0
    capsys.readouterr()
    assert world.run("retry", ok_id) == 1
    assert "only a refused request is retried" in capsys.readouterr().err
    assert world.run("retry", "01NOSUCHREQUEST00000000000") == 1
    assert "no record of request 01NOSUCHREQUEST00000000000" in capsys.readouterr().err


def test_retry_refuses_a_gone_branch_an_unreachable_remote_and_a_held_record(world, capsys):
    """Each gate before the mail moves: the branch deleted on the remote, a remote that cannot be
    reached (a refusal here, never a deferral: nothing is claimed to defer), and another request
    for the branch that holds a record short of `replied` (mid-claim in another run)."""
    head, msg_id = _red_base_refusal(world)
    _fix_base(world)
    archived = world.archived(msg_id)

    _git(world.wt, "push", "-q", "origin", "--delete", "feat")
    assert world.run("retry", msg_id) == 1
    assert "is gone from origin" in capsys.readouterr().err
    _git(world.wt, "push", "-q", "origin", "feat")

    url = str(world.remote)
    _git(world.main, "remote", "set-url", "origin", str(world.tmp / "no-such-remote.git"))
    assert world.run("retry", msg_id) == 1
    assert "could not reach origin" in capsys.readouterr().err
    _git(world.main, "remote", "set-url", "origin", url)

    held = dict(world.record(msg_id), id="01HELDCLAIM0000000000000000", phase="claimed")
    (world.main / ".git" / "fabrik-merge" / f"{held['id']}.json").write_text(json.dumps(held))
    assert world.run("retry", msg_id) == 1
    assert f"request {held['id']} for branch feat waits" in capsys.readouterr().err
    assert world.archived(msg_id) == archived and world.record(msg_id)["outcome"] == "refused"


def test_a_failed_requeue_restores_the_refused_record(world, monkeypatch, capsys):
    """The fresh record is written before `mail.py requeue`; a requeue that fails left the mail
    where it was, so the refused record is put back and nothing else changed."""
    _head, msg_id = _red_base_refusal(world)
    _fix_base(world)
    before, archived = world.record(msg_id), world.archived(msg_id)
    real = world.mod._mail_cli

    def failing_requeue(ctx, *args, **kw):
        if args[:1] == ("requeue",):
            return subprocess.CompletedProcess(args, 1, "", "requeue refused\n")
        return real(ctx, *args, **kw)

    monkeypatch.setattr(world.mod, "_mail_cli", failing_requeue)
    assert world.run("retry", msg_id) == 1
    assert "nothing changed" in capsys.readouterr().err
    assert world.record(msg_id) == before and world.archived(msg_id) == archived


def test_retry_refuses_while_a_resent_request_waits(world, capsys):
    """The incident's own sequel: the requester already re-sent the same head. Retrying the first
    id merged it and the re-sent one was then refused "already in master but no merge commit names
    request" — telling the requester to change a merged branch. The retry names the waiting one."""
    head, msg_id = _red_base_refusal(world)
    _fix_base(world)
    dup = world.send(head)
    capsys.readouterr()

    assert world.run("retry", msg_id) == 1
    err = capsys.readouterr().err
    assert dup in err and f"merge {dup}" in err, err
    assert world.record(msg_id)["outcome"] == "refused" and dup in world.inbox()


def test_a_retry_stopped_before_its_requeue_is_reopened_by_resume(world, monkeypatch):
    """The retry writes its record before `mail.py requeue`; a run that stops in between left the
    mail archived with the refusal's `blocked` ack, and `resume` continued it as claimed — the
    merge landed but its ack was skipped (the stale line read as "already acked")."""
    head, msg_id = _red_base_refusal(world)
    _fix_base(world)
    real = world.mod._mail_cli

    def stop_at_requeue(ctx, *args, **kw):
        if args[:1] == ("requeue",):
            raise KeyboardInterrupt  # the run dies here, as a SIGKILL would
        return real(ctx, *args, **kw)

    monkeypatch.setattr(world.mod, "_mail_cli", stop_at_requeue)
    with pytest.raises(KeyboardInterrupt):
        world.run("retry", msg_id)
    monkeypatch.setattr(world.mod, "_mail_cli", real)
    assert world.record(msg_id)["phase"] == "claiming"

    assert world.run("resume", msg_id) == 0
    rec = world.record(msg_id)
    assert rec["outcome"] == "merged", rec
    acks = [ln for ln in world.archived(msg_id).splitlines() if ln.startswith("acked-by:")]
    assert len(acks) == 1 and "disposition: done" in acks[0], acks


def test_a_requeue_that_keeps_the_ack_refuses_until_stripped(world, monkeypatch, capsys):
    """`mail.py requeue` leaves an undecodable message's ack in place. The retry refused, but the
    record stayed `claiming` with the mail in the inbox, and `resume` claimed it directly: the
    merge landed and its own ack was skipped. Every run refuses until the ack is stripped."""
    _head, msg_id = _red_base_refusal(world)
    _fix_base(world)
    box = world.tmp / "mail" / "proj"
    real = world.mod._mail_cli

    def requeue_keeps_ack(ctx, *args, **kw):
        if args[:1] == ("requeue",):
            (box / "archive" / f"{msg_id}.md").rename(box / "inbox" / f"{msg_id}.md")
            return subprocess.CompletedProcess(args, 0, "", "")
        return real(ctx, *args, **kw)

    monkeypatch.setattr(world.mod, "_mail_cli", requeue_keeps_ack)
    assert world.run("retry", msg_id) == 1
    monkeypatch.setattr(world.mod, "_mail_cli", real)
    assert world.run("resume", msg_id) == 1
    assert "still carries its old ack" in capsys.readouterr().err
    assert world.record(msg_id)["phase"] == "claiming" and msg_id in world.inbox()

    inbox = box / "inbox" / f"{msg_id}.md"
    kept = [ln for ln in inbox.read_text().splitlines() if not ln.startswith("acked-by:")]
    inbox.write_text("\n".join(kept) + "\n")
    assert world.run("resume", msg_id) == 0
    acks = [ln for ln in world.archived(msg_id).splitlines() if ln.startswith("acked-by:")]
    assert len(acks) == 1 and "disposition: done" in acks[0], acks


def test_retry_refuses_a_head_already_in_base(world, capsys):
    """A head merged under ANOTHER request (one already replied, so not "open") would be re-opened
    only to be refused again "already in base", its first refusal's ack lost on the way."""
    head, msg_id = _red_base_refusal(world)
    _fix_base(world)
    other = world.send(head)
    assert world.run("merge", other) == 0
    capsys.readouterr()
    archived = world.archived(msg_id)

    assert world.run("retry", msg_id) == 1
    assert "already in master" in capsys.readouterr().err
    assert world.archived(msg_id) == archived and world.record(msg_id)["outcome"] == "refused"


def test_a_red_base_is_named_in_the_refusal(world):
    """ "owner tests red" read the same for a red base and a red branch, so neither side knew
    whether to fix the branch or wait. The refusal runs the same tests on the base alone."""
    _head, msg_id = _red_base_refusal(world)
    reason = world.record(msg_id)["reason"]
    assert reason.count("owner tests red (") == 1, reason
    assert "on base alone (one run): red too (exit 3" in reason, reason
    assert f"merge_request.py retry {msg_id}" in reason, reason
    reply = world.replies(msg_id)["fleet"]
    assert "change nothing and send nothing" in reply, reply


def test_a_green_base_names_the_branch(world):
    """A branch whose own change breaks the base's tests is told so, never sent to wait."""
    world.write(".fabrik/merge-tests", "test ! -e BREAK.txt\n")
    world.commit_main("owner tests", ".fabrik/merge-tests")
    msg_id = world.send(world.branch({"BREAK.txt": "x\n"}))
    assert world.run("merge") == 1
    reason = world.record(msg_id)["reason"]
    assert "owner tests red" in reason and "on base alone (one run): green" in reason, reason


def test_base_alone_not_checked_for_new_tests_or_a_timeout(world, monkeypatch):
    """The fallback leg runs the tests the diff touched; when every one is new in the branch the
    base has nothing to run. A merged run that timed out is not run a second time: that would
    only double the time the merge lock is held. Both say so instead of guessing."""
    head, _ = _shadow_branch(world, monkeypatch, test="def test_x():\n    assert False\n")
    msg_id = world.send(head)
    assert world.run("merge") == 1
    reason = world.record(msg_id)["reason"]
    assert "on base alone: not checked" in reason and "new in the branch" in reason, reason

    world.write(".fabrik/merge-tests", "exit 124\n")
    world.commit_main("owner tests time out", ".fabrik/merge-tests")
    slow = world.send(world.branch({"z.txt": "z\n"}, msg="z"))
    assert world.run("merge") == 1
    reason = world.record(slow)["reason"]
    assert "on base alone: not checked" in reason and "timed out" in reason, reason


def test_base_alone_names_an_outer_timeout_and_a_check_that_could_not_run(world, monkeypatch):
    """The outer bound (a runner that itself hangs) raises instead of exiting 124, and the base-alone
    run can fail on its own; both are the "not checked" clause, never a changed refusal."""
    world.write(".fabrik/merge-tests", "exit 1\n")
    world.commit_main("owner tests", ".fabrik/merge-tests")
    real = world.mod._run_owner_leg

    def hangs(ctx, wt, script, touched):
        raise world.mod.TimedOutError("sh -e -c timed out after 1860s")

    monkeypatch.setattr(world.mod, "_run_owner_leg", hangs)
    first = world.send(world.branch({"a.txt": "a\n"}, msg="a"))
    assert world.run("merge") == 1
    reason = world.record(first)["reason"]
    assert "timed out after 1860s" in reason and "not checked (the merged run timed out)" in reason

    calls: list[str] = []

    def red_then_broken(ctx, wt, script, touched):
        calls.append(str(wt))
        if len(calls) > 1:
            raise RuntimeError("the base tree is unusable")
        return real(ctx, wt, script, touched)

    monkeypatch.setattr(world.mod, "_run_owner_leg", red_then_broken)
    second = world.send(world.branch({"b.txt": "b\n"}, msg="b"))
    assert world.run("merge") == 1
    reason = world.record(second)["reason"]
    assert reason.startswith("(a)-(d) build, preflight, tests, CAS: owner tests red"), reason
    assert "not checked (the check could not run: the base tree is unusable)" in reason, reason


# --- W-347cd0c3: one owner-test budget per invocation, inside the documented wrapper -------------
def _logging_runner(world) -> Path:
    """A stand-in for capped_run.sh that logs its argv and honours ``--timeout`` with coreutils
    ``timeout`` (exit 124 on the limit, as capped_run's own time limit exits)."""
    log = world.tmp / "runner.log"
    runner = world.tmp / "runner.sh"
    runner.write_text(
        f'#!/bin/sh\necho "$*" >> {log}\nshift\nt="$1"\nshift 2\nexec timeout "$t" "$@"\n',
        encoding="utf-8",
    )
    runner.chmod(0o755)
    world.mp.setenv("FABRIK_CAPPED_RUN", str(runner))
    return log


def test_the_owner_test_budget_refuses_before_any_outer_wrapper(world):
    import time

    log = _logging_runner(world)
    # the budget (8 s) is shorter than one leg's limit (60 s): the leg is stopped at what is left
    world.mp.setattr(world.mod, "TEST_TIMEOUT_S", 60)
    world.mp.setattr(world.mod, "MERGE_TEST_BUDGET_S", 8, raising=False)
    world.mp.setattr(world.mod, "LEG_FLOOR_S", 1, raising=False)
    world.write(".fabrik/merge-tests", "sleep 30\n")
    world.commit_main("slow owner tests", ".fabrik/merge-tests")
    msg_id = world.send(world.branch({"s.txt": "s\n"}, msg="s"))
    t0 = time.monotonic()
    assert world.run("merge") == 1
    took = time.monotonic() - t0
    reason = world.record(msg_id)["reason"]
    assert "budget" in reason and "not a test verdict" in reason, reason
    assert f"`merge_request.py retry {msg_id}`" in reason, reason
    assert "on base alone" not in reason and "owner tests red" not in reason, reason
    # one line per runner call (the script's own newline splits an argv across two log lines)
    limits = [
        int(ln.split()[1]) for ln in log.read_text().splitlines() if ln.startswith("--timeout ")
    ]
    assert len(limits) == 1 and 1 <= limits[0] <= 8, limits  # one leg, at what the budget left
    assert took < 25, took  # the leg was stopped at the budget, not run for its 30 s
    # the requester is told it is not theirs to fix
    replies = world.replies(msg_id)
    told = "the owner-test budget of the run, change nothing and send nothing either"
    assert replies and all(told in " ".join(r.split()) for r in replies.values()), replies


def test_an_owner_exit_124_inside_a_shortened_leg_stays_a_red(world):
    """The owner's own `timeout` (here a plain exit 124) ends the leg well inside its shortened
    limit: that is the tests' verdict, never the budget's."""
    _logging_runner(world)
    world.mp.setattr(world.mod, "TEST_TIMEOUT_S", 60)
    world.mp.setattr(world.mod, "MERGE_TEST_BUDGET_S", 30)
    world.mp.setattr(world.mod, "LEG_FLOOR_S", 1)
    world.write(".fabrik/merge-tests", "exit 124\n")
    world.commit_main("owner tests time out themselves", ".fabrik/merge-tests")
    msg_id = world.send(world.branch({"t.txt": "t\n"}, msg="t"))
    assert world.run("merge") == 1
    reason = world.record(msg_id)["reason"]
    assert "owner tests red" in reason and "exit 124" in reason and "budget" not in reason, reason


def test_an_outer_timeout_under_a_shortened_limit_is_the_budget(world, monkeypatch):
    """A runner that itself hangs past limit + 60 raises TimedOutError; under a shortened limit
    that is the budget too, with no base-alone run."""
    world.write(".fabrik/merge-tests", "true\n")
    world.commit_main("owner tests", ".fabrik/merge-tests")

    def hangs_short(ctx, wt, script, touched):
        ctx.leg_limit = 5
        raise world.mod.TimedOutError("sh -e -c timed out after 65s")

    monkeypatch.setattr(world.mod, "_run_owner_leg", hangs_short)
    msg_id = world.send(world.branch({"h.txt": "h\n"}, msg="h"))
    assert world.run("merge") == 1
    reason = world.record(msg_id)["reason"]
    assert "budget" in reason and "stopped at 5s" in reason, reason
    assert "on base alone" not in reason and "timed out after" not in reason, reason


def test_the_leg_floor_is_exact(world):
    ctx = world.mod._Ctx(world.main, world.main / ".git", "infra")
    floor = world.mod.LEG_FLOOR_S
    ctx.test_deadline = world.mod.time.monotonic() + floor + 0.5
    assert world.mod._leg_timeout(ctx) == floor  # exactly the floor left: a leg of that length
    ctx.test_deadline = world.mod.time.monotonic() + floor - 0.5
    with pytest.raises(world.mod.BudgetSpentError):
        world.mod._leg_timeout(ctx)


def test_a_parked_budget_catch_up_is_told_resume_not_a_hand_merge(world, capsys):
    parked = _strand(world, _dead_pid(), "1", phase="catchup-refused")
    path = world.main / ".git" / "fabrik-merge" / f"{parked}.json"
    rec = json.loads(path.read_text())
    rec["reason"] = world.mod._catch_up_refused(
        world.mod._Ctx(world.main, world.main / ".git", "infra"),
        rec,
        "origin",
        world.mod.BudgetSpentError("the owner-test budget of this run (3600s) ran out"),
    )
    path.write_text(json.dumps(rec))
    assert world.run("merge") == 4
    err = capsys.readouterr().err
    assert f"`merge_request.py resume {parked}` again" in err and "by hand" not in err, err


def test_a_spent_budget_starts_no_leg_and_a_catch_up_names_resume(world):
    log = _logging_runner(world)
    world.mp.setattr(world.mod, "MERGE_TEST_BUDGET_S", 0, raising=False)
    world.write(".fabrik/merge-tests", "true\n")
    world.commit_main("owner tests", ".fabrik/merge-tests")
    msg_id = world.send(world.branch({"n.txt": "n\n"}, msg="n"))
    before = world.state()
    assert world.run("merge") == 1
    reason = world.record(msg_id)["reason"]
    assert "budget" in reason and f"`merge_request.py retry {msg_id}`" in reason, reason
    assert not log.exists(), log.read_text()  # no leg started, so the runner never ran
    after = world.state()
    assert (after["refs"], after["origin"]) == (before["refs"], before["origin"])
    # a catch-up refused by the budget is a new run's job, never a hand merge
    ctx = world.mod._Ctx(world.main, world.main / ".git", "infra")
    spent = world.mod.BudgetSpentError("x")
    text = world.mod._catch_up_refused(ctx, {"id": msg_id, "base": "master"}, "origin", spent)
    assert f"`merge_request.py resume {msg_id}` again" in text and "by hand" not in text, text


def test_the_documented_merge_wrapper_covers_the_budget():
    """The newest decision row naming the merge command must give capped_run room for the whole
    budget plus the push, the sync and 300 s for builds, preflights, the carry and the reply, and
    rund a longer bound than capped_run (a shorter outer bound kills the merge mid-push)."""
    import re

    mod = _load_module()
    rows = (Path(__file__).resolve().parents[1] / "docs" / "DECISIONS.md").read_text(
        encoding="utf-8"
    )
    shape = re.compile(
        r"rund --timeout (\d+) -- \S*capped_run\.sh --timeout (\d+) -- python3 "
        r"scripts/merge_request\.py merge"
    )
    found = [
        (int(m.group(1)), int(m.group(2)), int(d))
        for d, line in re.findall(r"(?m)^\| D-(\d+) (.*)$", rows)
        for m in shape.finditer(line)
    ]
    assert found, "no decision row documents the merge command"
    outer, capped, _row = max(found, key=lambda f: f[2])
    need = (
        getattr(mod, "MERGE_TEST_BUDGET_S", 10**9) + mod.PUSH_TIMEOUT_S + mod.SYNC_TIMEOUT_S + 300
    )
    assert capped >= need and outer > capped, (outer, capped, need)


# --- W-e914202a: every scripted merge commit is signed with a parseable trailer block --------
def _trailer_lines(world: World, sha: str) -> list[str]:
    """The trailer lines git itself parses from ``sha``'s message, in order (never a substring)."""
    body = _git(world.main, "log", "-1", "--format=%B", sha)
    res = subprocess.run(
        ["git", "interpret-trailers", "--parse"],
        cwd=world.main,
        input=body + "\n",
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return res.stdout.splitlines()


def _trailers(world: World, sha: str) -> dict[str, str]:
    return dict(ln.split(": ", 1) for ln in _trailer_lines(world, sha) if ": " in ln)


def test_a_request_merge_commit_carries_parseable_provenance_trailers(world):
    head = world.branch({"x.txt": "x\n"})
    msg_id = world.send(head, item="W-0123abcd")

    assert world.run("merge") == 0

    new = world.base()
    assert _git(world.main, "log", "-1", "--format=%s", new) == (
        f"merge(infra): feat — request {msg_id}, item W-0123abcd"
    )
    # the exact block, in order: a duplicated or forged trailer line fails here, and no Merged-From
    # (scratch_sweep reads it over merges, where a reused branch name would read merged for ever)
    assert _trailer_lines(world, new) == [
        "Agent-Role: orchestrator",
        "Agent-Name: infra",
        f"Agent-Context: merge_request.py merged branch feat for request {msg_id}, item W-0123abcd",
    ]


def test_a_conflict_resolved_merge_commit_is_signed(world):
    head = world.branch(
        {"docs/DECISIONS.md": DECISIONS.replace("| D-1 |", "| D-2 | branch |\n| D-1 |")}
    )
    world.write("docs/DECISIONS.md", DECISIONS.replace("| D-1 |", "| D-3 | base |\n| D-1 |"))
    world.commit_main("base row", "docs/DECISIONS.md")
    msg_id = world.send(head)

    assert world.run("merge") == 0
    tr = _trailers(world, world.base())
    assert tr.get("Agent-Role") == "orchestrator" and tr.get("Agent-Name") == "infra", tr
    assert msg_id in tr.get("Agent-Context", ""), tr


def test_a_catch_up_merge_commit_is_signed(world, capsys):
    head = world.branch({"x.txt": "x\n"})
    msg_id = world.send(head)
    pushed: list[str] = []

    def race(name):
        if name == "before-push" and not pushed:
            pushed.append(world.push_from_elsewhere("y.txt", "y\n"))

    assert world.run("merge", phase=race) == 4
    capsys.readouterr()
    assert world.run("resume", msg_id) == 0

    tip = world.base()
    assert _git(world.main, "rev-parse", f"{tip}^2") == pushed[0]  # the catch-up merge itself
    assert _trailer_lines(world, tip) == [
        "Agent-Role: orchestrator",
        "Agent-Name: infra",
        f"Agent-Context: merge_request.py catch-up of origin/master after request {msg_id}",
    ]
    # both runs passed the post-CAS steps: the duty is recorded once, and the resume's gate line
    # reports the REQUEST merge's owner tests (recorded by the first run), named as such
    assert world.record(msg_id)["evidence"].count(world.mod.GATE_DUTY) == 1
    out = capsys.readouterr().out
    assert (
        f"{world.mod.GATE_DUTY}; owner tests of the request merge: no owner tests ran "
        "(no .fabrik/merge-tests, no touched tests/)"
    ) in out.splitlines(), out


def test_the_gate_line_without_recorded_tests_says_so():
    mod = _load_module()
    assert mod._gate_line({"merge_sha": "abc123"}) == (
        f"{mod.GATE_DUTY}; owner tests of the request merge: none recorded "
        "(resumed an existing merge abc123)"
    )
    rec = {"evidence": ["tests: A", "catch-up merge s of origin/master (tests: B)", mod.GATE_DUTY]}
    assert mod._gate_line(rec).endswith("owner tests of the request merge: A")


def test_an_uppercase_ascii_owner_signs_its_lowercase_name_without_a_note(world):
    ctx = world.mod._Ctx(world.main, world.main / ".git", "INFRA")
    message = world.mod._signed(ctx, "merge(INFRA): subject", "context")
    assert "Agent-Name: infra" in message.splitlines() and ctx.notes == []


def test_the_owner_grammar_note_is_written_once_per_run(world):
    ctx = world.mod._Ctx(world.main, world.main / ".git", "two words")
    for _ in range(2):  # a rebuild signs again
        world.mod._signed(ctx, "merge(x): subject", "context")
    assert len(ctx.notes) == 1, ctx.notes


def test_the_block_parses_under_merge_log(world):
    """merge.log=true makes `git merge -m` append a shortlog AFTER the message: without --no-log
    the last paragraph is prose and git parses no trailer at all."""
    _git(world.main, "config", "merge.log", "true")
    head = world.branch({"x.txt": "x\n"})
    world.send(head)

    assert world.run("merge") == 0
    assert _trailers(world, world.base()).get("Agent-Role") == "orchestrator"


@pytest.mark.parametrize("owner", ["two words", "Straße", "infra_x", "a" * 33, "Kelvin"])
def test_an_owner_outside_the_name_grammar_signs_without_agent_name(world, owner):
    ctx = world.mod._Ctx(world.main, world.main / ".git", owner)
    message = world.mod._signed(ctx, "merge(x): subject", "context")
    lines = message.splitlines()
    assert lines[:2] == ["merge(x): subject", ""]
    assert lines[2:] == ["Agent-Role: orchestrator", "Agent-Context: context"], message
    assert any("outside the agent-name grammar" in n for n in ctx.notes), ctx.notes


def test_a_multi_line_trailer_value_refuses(world):
    ctx = world.mod._Ctx(world.main, world.main / ".git", "infra")
    with pytest.raises(world.mod.RefusedError):
        world.mod._signed(ctx, "merge(x): subject", "context\nAgent-Role: forged")


def test_the_reflog_carries_the_subject_only(world):
    head = world.branch({"x.txt": "x\n"})
    msg_id = world.send(head)

    assert world.run("merge") == 0
    entry = _git(world.main, "reflog", "show", "-1", "--format=%gs", "refs/heads/master")
    assert entry == f"merge_request: merge(infra): feat — request {msg_id}, item none", entry


def test_merge_states_that_the_gate_is_the_callers(world, capsys):
    head = world.branch({"x.txt": "x\n"})
    msg_id = world.send(head)

    assert world.run("merge") == 0
    out = capsys.readouterr().out.splitlines()
    i = next(n for n, ln in enumerate(out) if ln.startswith(f"merged {msg_id} as "))
    duty = (
        "gate: merge does not run final_gate — gating the merged result is the caller's duty; "
        "merge itself runs only the owner tests"
    )
    assert out[i + 1] == (
        f"{duty}; owner tests of the request merge: no owner tests ran (no .fabrik/merge-tests, "
        "no touched tests/)"
    ), out
    assert f"evidence: {duty}\n" in world.replies(msg_id)["fleet"]
