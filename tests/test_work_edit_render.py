"""Behavior contract for ``work.py edit`` and ``render``'s tree scope (mail 01M55ZNVH7, kaizen).

``edit`` changes only what ``add`` writes — title, next, the spec/plan/decision links — on the kinds ``add`` makes,
under the store lock. ``render`` builds the backlog block from the caller's own store, so outside the main checkout
(a linked worktree, or ``--repo`` naming a tree the caller is not in) it refuses unless ``--here`` is given. Every
test runs against a throwaway git repo under ``tmp_path`` with an explicit ``env=`` — never the hub's own store.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "work.py"
BACKLOG = "docs/STRATEGIC_BACKLOG.md"


def _work_module() -> ModuleType:
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import work
    finally:
        sys.path.remove(str(SCRIPT.parent))
    return work


def _env(tmp_path: Path) -> dict[str, str]:
    """Hermetic: HOME and TMPDIR under tmp_path, git reads no user config, no session id."""
    for sub in ("home", "tmp"):
        (tmp_path / sub).mkdir(exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path / "home"),
        "TMPDIR": str(tmp_path / "tmp"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "FABRIK_MAIL_ROOT": str(tmp_path / "tmp" / "mail"),
        "COMMAND_RUN_DIR": str(tmp_path / "tmp" / "state" / "command-runs"),
        "CLAUDE_AGENT": "infra",
    }


def _git(cwd: Path, env: dict[str, str], *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True
    ).stdout


def run(args: list[str], env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _store(tmp_path: Path, env: dict[str, str]) -> Path:
    """A main checkout with a committed store and a backlog file that has no block yet."""
    repo = tmp_path / "repo"
    _git(tmp_path, env, "init", "-q", "-b", "master", str(repo))
    (repo / "docs").mkdir()
    (repo / BACKLOG).write_text("# Strategic backlog\n\nIntro.\n", encoding="utf-8")
    _git(repo, env, "add", BACKLOG)
    _git(repo, env, "commit", "-q", "-m", "seed")
    r = run(["init", "--distributor", "intel"], env, repo)
    assert r.returncode == 0, r.stderr
    _git(repo, env, "add", ".fabrik/work/config.json")
    _git(repo, env, "commit", "-q", "-m", "store")
    return repo.resolve()


def _add(repo: Path, env: dict[str, str], title: str = "A row", *extra: str) -> str:
    r = run(["add", "--kind", "backlog", "--title", title, *extra], env, repo)
    assert r.returncode == 0, r.stderr
    return Path(r.stdout.strip().splitlines()[-1]).stem


def _item_file(repo: Path, item_id: str) -> Path:
    return repo / ".fabrik" / "work" / f"{item_id}.json"


def _linked(repo: Path, env: dict[str, str], tmp_path: Path) -> Path:
    tree = tmp_path / "linked"
    _git(repo, env, "worktree", "add", "-q", "-b", "side", str(tree))
    return tree.resolve()


# ── edit ─────────────────────────────────────────────────────────────────────────────────────


def test_edit_changes_only_the_named_fields(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    (repo / "docs" / "plan-a.md").write_text("a\n", encoding="utf-8")
    item_id = _add(repo, env, "Old title", "--next", "old next", "--link", "spec=docs/s.md")
    path = _item_file(repo, item_id)
    before = json.loads(path.read_text(encoding="utf-8"))

    r = run(
        [
            "edit",
            item_id,
            "--title",
            "  New   title ",
            "--next",
            "new\nnext",
            "--link",
            "plan=docs/plan-a.md",
            "--unlink",
            "spec",
        ],
        env,
        repo,
    )
    assert r.returncode == 0, r.stderr
    after = json.loads(path.read_text(encoding="utf-8"))
    assert after["title"] == "New title"
    assert after["next"] == "new next"
    assert after["links"]["plan"] == "docs/plan-a.md"
    assert after["links"]["spec"] == ""
    changed = {k for k in before if before[k] != after[k]}
    assert changed == {"title", "next", "links"}, changed
    assert {k for k in before["links"] if before["links"][k] != after["links"][k]} == {
        "plan",
        "spec",
    }
    assert item_id in r.stdout

    # `--next ""` alone is a clear, never "naming nothing"
    r = run(["edit", item_id, "--next", ""], env, repo)
    assert r.returncode == 0, r.stderr
    assert json.loads(path.read_text(encoding="utf-8"))["next"] == ""
    assert "nothing to render" in r.stdout

    # a plan path that does not exist is applied, with a warning
    r = run(["edit", item_id, "--link", "plan=docs/nowhere.md"], env, repo)
    assert r.returncode == 0, r.stderr
    assert json.loads(path.read_text(encoding="utf-8"))["links"]["plan"] == "docs/nowhere.md"
    assert "docs/nowhere.md" in r.stderr and "not a file" in r.stderr

    # a decision link must be a ledger id
    r = run(["edit", item_id, "--link", "decision=D-12"], env, repo)
    assert r.returncode == 0, r.stderr
    assert json.loads(path.read_text(encoding="utf-8"))["links"]["decision"] == "D-12"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ([], "edit needs"),
        (["--title", "   "], "--title is empty"),
        (["--link", "plan=docs/p.md", "--unlink", "plan"], "both name plan"),
        (["--link", "plan="], "expected one of"),
        (["--link", "owner=x"], "expected one of"),
        (["--unlink", "owner"], "--unlink"),
        (["--link", "decision=ADR-1"], "not a ledger id"),
    ],
)
def test_edit_refuses_what_add_refuses(tmp_path, args, message):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item_id = _add(repo, env)
    path = _item_file(repo, item_id)
    before = path.read_bytes()
    r = run(["edit", item_id, *args], env, repo)
    assert r.returncode != 0, (args, r.stdout)
    assert message in r.stderr, (args, r.stderr)
    assert path.read_bytes() == before


@pytest.mark.parametrize("kind", ["decision", "next", "mail", "feedback"])
def test_edit_refuses_the_kinds_add_refuses(tmp_path, kind):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item_id = _add(repo, env)
    path = _item_file(repo, item_id)
    item = json.loads(path.read_text(encoding="utf-8"))
    item["kind"] = kind
    path.write_text(json.dumps(item, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    before = path.read_bytes()
    r = run(["edit", item_id, "--title", "x"], env, repo)
    assert r.returncode == 1, r.stdout
    assert f"a {kind} item" in r.stderr, r.stderr
    assert path.read_bytes() == before


def test_edit_names_a_missing_or_malformed_id(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    r = run(["edit", "W-00000000", "--title", "x"], env, repo)
    assert r.returncode == 1 and "W-00000000" in r.stderr, r.stderr
    r = run(["edit", "nope", "--title", "x"], env, repo)
    assert r.returncode == 1 and "not an item id" in r.stderr, r.stderr


_HOLD_LOCK = """
import fcntl, os, sys, time
fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT)
fcntl.flock(fd, fcntl.LOCK_EX)
print("held", flush=True)
time.sleep(float(sys.argv[2]))
"""


def test_edit_writes_only_under_the_store_lock(tmp_path, monkeypatch):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item_id = _add(repo, env)
    path = _item_file(repo, item_id)
    before = path.read_bytes()
    lock = repo / ".git" / "fabrik-work" / ".lock"
    assert lock.exists()
    holder = subprocess.Popen(
        [sys.executable, "-c", _HOLD_LOCK, str(lock), "5"], stdout=subprocess.PIPE, text=True
    )
    try:
        assert holder.stdout is not None and holder.stdout.readline().strip() == "held"
        work = _work_module()
        monkeypatch.setattr(work, "CLI_LOCK_TIMEOUT_S", 0.3)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        monkeypatch.chdir(repo)
        started = time.monotonic()
        rc = work.main(["edit", item_id, "--title", "under the lock"])
        assert rc == 1
        assert time.monotonic() - started < 4
        assert path.read_bytes() == before
    finally:
        holder.kill()
        holder.wait()
    rc = work.main(["edit", item_id, "--title", "under the lock"])
    assert rc == 0
    assert json.loads(path.read_text(encoding="utf-8"))["title"] == "under the lock"


def test_edit_in_a_linked_worktree_names_the_merge(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item_id = _add(repo, env)
    _git(repo, env, "add", f".fabrik/work/{item_id}.json")
    _git(repo, env, "commit", "-q", "-m", "item")
    tree = _linked(repo, env, tmp_path)
    r = run(["edit", item_id, "--title", "from the tree"], env, tree)
    assert r.returncode == 0, r.stderr
    assert (
        json.loads(_item_file(tree, item_id).read_text(encoding="utf-8"))["title"]
        == "from the tree"
    )
    assert json.loads(_item_file(repo, item_id).read_text(encoding="utf-8"))["title"] == "A row"
    assert "commit-items" in r.stdout


# ── render ───────────────────────────────────────────────────────────────────────────────────


def test_render_refuses_outside_the_main_checkout(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    tree = _linked(repo, env, tmp_path)
    _add(tree, env, "Only in the tree")
    before = (tree / BACKLOG).read_bytes()
    r = run(["render"], env, tree)
    assert r.returncode == 1, r.stdout
    assert "main checkout" in r.stderr and "work.py edit" in r.stderr and "--here" in r.stderr
    assert (tree / BACKLOG).read_bytes() == before

    # naming the main checkout with --repo from inside another tree is refused the same way
    main_before = (repo / BACKLOG).read_bytes()
    r = run(["--repo", str(repo), "render"], env, tree)
    assert r.returncode == 1, r.stdout
    assert "main checkout" in r.stderr
    assert (repo / BACKLOG).read_bytes() == main_before


def test_render_here_and_the_main_checkout(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    main_id = _add(repo, env, "Main row")
    r = run(["render"], env, repo)
    assert r.returncode == 0, r.stderr
    assert main_id in (repo / BACKLOG).read_text(encoding="utf-8")
    assert "do not commit" not in r.stdout

    tree = _linked(repo, env, tmp_path)
    tree_id = _add(tree, env, "Tree row")
    r = run(["render", "--here"], env, tree)
    assert r.returncode == 0, r.stderr
    text = (tree / BACKLOG).read_text(encoding="utf-8")
    assert tree_id in text and main_id not in text
    assert "do not commit" in r.stdout
