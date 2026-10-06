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
    ) -> str:
        body = (
            f"branch: {branch}\nhead: {head}\nbase: master\nitem: {item}\n"
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
    message = _git(world.main, "log", "-1", "--format=%B", new)
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


# --- (g): the hub's governance sync runs when a merged path matches the filter -------------
def test_the_hub_sync_runs_when_a_merged_path_matches_the_filter(world, monkeypatch):
    world.write(
        ".pre-commit-config.yaml",
        "repos:\n  - repo: local\n    hooks:\n      - id: governance-sync\n"
        "        files: '(^scripts/mail\\.py$|^templates/governance/)'\n"
        "      - id: other\n        files: '^x'\n",
    )
    world.commit_main("hooks", ".pre-commit-config.yaml")
    monkeypatch.setattr(world.mod, "HUB_CHECKOUT", world.main)
    head = world.branch({"scripts/mail.py": "# mail\n"})
    msg_id = world.send(head)

    assert world.run("merge") == 0
    assert world.sync_marker.read_text() == "x"
    assert "sync: ran for 1" in world.replies(msg_id)["fleet"]


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
    mod._copy_worktree_include(ctx, wt, _git(main, "rev-parse", "HEAD"))
    assert (wt / "local").read_text(encoding="utf-8") == "a tracked file\n"
    assert (wt / ".env").read_text(encoding="utf-8") == "A=1\n"  # the rest is still copied
