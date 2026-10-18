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
    r = run(
        ["render", "--here"], env, repo
    )  # `--here` in the main checkout: no notice (A-opus-p3-1)
    assert r.returncode == 0, r.stderr
    assert "do not commit" not in r.stdout

    tree = _linked(repo, env, tmp_path)
    tree_id = _add(tree, env, "Tree row")
    r = run(["render", "--here"], env, tree)
    assert r.returncode == 0, r.stderr
    text = (tree / BACKLOG).read_text(encoding="utf-8")
    assert tree_id in text and main_id not in text
    assert "do not commit" in r.stdout


# ── review pass 1 (fixup 1): the invariants behind A-opus-1/2/4/5 and A-sonnet-1/2 ─────────────


@pytest.mark.parametrize("kind", ["weird", "Backlog", " task", None])
def test_edit_allows_only_the_kinds_add_makes(tmp_path, kind):
    """An allowlist, never a denylist: a hand-set unknown kind, a case or space variant and a missing
    kind are refused exactly as the derived kinds are."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item_id = _add(repo, env)
    path = _item_file(repo, item_id)
    item = json.loads(path.read_text(encoding="utf-8"))
    if kind is None:
        item.pop("kind")
    else:
        item["kind"] = kind
    path.write_text(json.dumps(item, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    before = path.read_bytes()
    r = run(["edit", item_id, "--title", "x"], env, repo)
    assert r.returncode == 1, (kind, r.stdout)
    assert "refused" in r.stderr and "backlog" in r.stderr, r.stderr
    assert path.read_bytes() == before


def test_a_link_path_warns_unless_it_is_a_file_inside_the_repo(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item_id = _add(repo, env)
    outside = tmp_path / "outside.md"
    outside.write_text("x\n", encoding="utf-8")
    cases = {
        "docs/STRATEGIC_BACKLOG.md": False,  # a file inside the repo: silent
        "docs/missing.md": True,
        str(outside): True,  # absolute, outside
        "../outside.md": True,  # relative, escapes the repo though the file exists
        "a" * 300: True,  # a name the filesystem refuses: a warning, never a crash
    }
    for key in ("plan", "spec"):  # both path links are checked, not only plan (review B-sonnet-4)
        for value, warns in cases.items():
            r = run(["edit", item_id, "--link", f"{key}={value}"], env, repo)
            assert r.returncode == 0, (key, value[:40], r.stderr)
            assert ("not a file inside" in r.stderr) is warns, (key, value[:40], r.stderr)
            stored = json.loads(_item_file(repo, item_id).read_text(encoding="utf-8"))
            assert stored["links"][key] == value


def test_edit_keeps_the_links_shape_add_writes_and_refuses_a_malformed_one(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item_id = _add(repo, env)
    path = _item_file(repo, item_id)
    item = json.loads(path.read_text(encoding="utf-8"))
    item["links"] = {"plan": "docs/p.md"}  # a hand edit dropped spec and decision
    path.write_text(json.dumps(item, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    r = run(["edit", item_id, "--unlink", "plan"], env, repo)
    assert r.returncode == 0, r.stderr
    links = json.loads(path.read_text(encoding="utf-8"))["links"]
    assert links == {"decision": "", "plan": "", "spec": ""}, links

    item = json.loads(path.read_text(encoding="utf-8"))
    item["links"] = ["docs/p.md"]
    path.write_text(json.dumps(item, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    before = path.read_bytes()
    r = run(["edit", item_id, "--link", "plan=docs/q.md"], env, repo)
    assert r.returncode == 1, r.stdout
    assert "its links is not a mapping (list)" in r.stderr, r.stderr
    assert "Traceback" not in r.stderr, r.stderr
    assert path.read_bytes() == before
    # a title-only edit leaves the malformed links alone and still succeeds
    r = run(["edit", item_id, "--title", "fine"], env, repo)
    assert r.returncode == 0, r.stderr


def test_no_git_call_after_the_write_can_fail_edit_or_render(tmp_path, monkeypatch):
    """Every git answer edit and render need is taken BEFORE they write: a git failure after the write
    would report a failure for a change that already landed."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item_id = _add(repo, env)
    _git(repo, env, "add", f".fabrik/work/{item_id}.json")
    _git(repo, env, "commit", "-q", "-m", "item")
    tree = _linked(repo, env, tmp_path)
    work = _work_module()
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(tree)
    real_linked, real_item, real_text = work._is_linked_worktree, work._write_item, work._write_text
    written = {"yes": False}

    def write_item(*a, **k):
        written["yes"] = True
        return real_item(*a, **k)

    def write_text(*a, **k):
        written["yes"] = True
        return real_text(*a, **k)

    def linked(repo_path):
        if written["yes"]:
            raise work.WorkError("git asked after the write")
        return real_linked(repo_path)

    monkeypatch.setattr(work, "_write_item", write_item)
    monkeypatch.setattr(work, "_write_text", write_text)
    monkeypatch.setattr(work, "_is_linked_worktree", linked)
    assert work.main(["edit", item_id, "--title", "after"]) == 0
    assert json.loads(_item_file(tree, item_id).read_text(encoding="utf-8"))["title"] == "after"
    written["yes"] = False
    assert work.main(["render", "--here"]) == 0
    assert item_id in (tree / BACKLOG).read_text(encoding="utf-8")


# ── review pass 2 (fixup 2): A-opus-1/2/3, A-sonnet-1, B-haiku-1/4 ────────────────────────────


def test_here_renders_only_the_callers_own_tree(tmp_path):
    """`--here` never writes a tree the caller is not in: with `--repo` naming another tree it is
    refused like a plain render, from a linked tree and from outside any repo."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _add(repo, env, "Main row")
    tree = _linked(repo, env, tmp_path)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    before = (repo / BACKLOG).read_bytes()
    for cwd in (tree, outside):
        r = run(["--repo", str(repo), "render", "--here"], env, cwd)
        assert r.returncode == 1, (cwd, r.stdout)
        assert "not in" in r.stderr, r.stderr
        assert "do not commit" not in r.stdout
        assert (repo / BACKLOG).read_bytes() == before


def test_render_refuses_cleanly_when_the_cwd_is_gone(tmp_path, monkeypatch):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    work = _work_module()
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(repo)

    def gone():
        raise FileNotFoundError(2, "No such file or directory")

    monkeypatch.setattr(work.Path, "cwd", staticmethod(gone))
    before = (repo / BACKLOG).read_bytes()
    for args in (["--repo", str(repo), "render"], ["--repo", str(repo), "render", "--here"]):
        with pytest.raises(work.WorkError, match="not in"):
            work.cmd_render(work._repo_root(str(repo)), work._parser().parse_args(args))
    assert (repo / BACKLOG).read_bytes() == before


def test_a_symlink_loop_is_a_warning_never_a_crash(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item_id = _add(repo, env)
    (repo / "docs" / "loopa").symlink_to("loopb")
    (repo / "docs" / "loopb").symlink_to("loopa")
    r = run(["edit", item_id, "--link", "plan=docs/loopa"], env, repo)
    assert r.returncode == 0, r.stderr
    assert "not a file inside" in r.stderr
    assert (
        json.loads(_item_file(repo, item_id).read_text(encoding="utf-8"))["links"]["plan"]
        == "docs/loopa"
    )


def test_a_link_edit_never_changes_a_link_value_it_did_not_name(tmp_path):
    """A stored LINK_KEYS value that is not a string is refused by name, never silently coerced —
    an `--unlink plan` must not blank `spec` or `decision` (review pass 3, A-haiku-p3-2). A title-only
    edit leaves links exactly as stored."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item_id = _add(repo, env)
    path = _item_file(repo, item_id)
    item = json.loads(path.read_text(encoding="utf-8"))
    item["links"] = {"spec": None, "plan": "docs/p.md", "decision": 7}
    path.write_text(json.dumps(item, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    before = path.read_bytes()
    for args in (["--unlink", "plan"], ["--link", "plan=docs/q.md"]):
        r = run(["edit", item_id, *args], env, repo)
        assert r.returncode == 1, (args, r.stdout)
        assert "links.decision, links.spec is not a string" in r.stderr, r.stderr
        assert path.read_bytes() == before
    r = run(["edit", item_id, "--title", "only the title"], env, repo)
    assert r.returncode == 0, r.stderr
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["title"] == "only the title"
    assert stored["links"] == {"spec": None, "plan": "docs/p.md", "decision": 7}


def test_edit_changes_a_task_item(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    r = run(["add", "--kind", "task", "--title", "A task"], env, repo)
    assert r.returncode == 0, r.stderr
    item_id = Path(r.stdout.strip().splitlines()[-1]).stem
    r = run(["edit", item_id, "--title", "Renamed task"], env, repo)
    assert r.returncode == 0, r.stderr
    assert (
        json.loads(_item_file(repo, item_id).read_text(encoding="utf-8"))["title"] == "Renamed task"
    )


def test_edit_and_render_need_a_store(tmp_path):
    """Both verbs refuse a store-less repo with `init`'s refusal before anything else runs — the
    render refusal never stands in for it (review B-sonnet-4)."""
    env = _env(tmp_path)
    repo = tmp_path / "bare"
    _git(tmp_path, env, "init", "-q", "-b", "master", str(repo))
    (repo / "docs").mkdir()
    (repo / BACKLOG).write_text("# Strategic backlog\n", encoding="utf-8")
    before = (repo / BACKLOG).read_bytes()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    cases = [
        (["render"], repo),
        (["edit", "W-00000000", "--title", "x"], repo),
        # from another directory the store check must still come first (A-opus-p3-2)
        (["--repo", str(repo), "render"], outside),
        (["--repo", str(repo), "render", "--here"], outside),
    ]
    for args, cwd in cases:
        r = run(args, env, cwd)
        assert r.returncode == 1, (args, r.stdout)
        assert "init" in r.stderr, (args, r.stderr)
        assert "render refused" not in r.stderr, (args, r.stderr)
    assert (repo / BACKLOG).read_bytes() == before
