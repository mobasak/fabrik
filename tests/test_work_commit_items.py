"""Behavior contract for `work.py commit-items` and its Stop subject (W-4238b6ec, mail 01M3RT95).

Item files are written into the MAIN checkout's store by every session — worktree agents included —
and nothing committed them: 179 untracked + 8 modified `W-*.json` sat in /opt/fabrik on 2026-10-05.
The main checkout's session now commits them with one verb, in one plumbing commit that touches
nothing but uncommitted, valid, unstaged item files, and its Stop hook names the verb. Every test
runs against a throwaway git repo under ``tmp_path`` with an explicit ``env=``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "work.py"


def _env(tmp_path: Path) -> dict[str, str]:
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
    }


def _git(cwd: Path, env: dict[str, str], *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True, timeout=30
    ).stdout


def run(args: list[str], env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _ok(args: list[str], env: dict[str, str], cwd: Path) -> str:
    r = run(args, env, cwd)
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout


def _store(tmp_path: Path, env: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    _git(tmp_path, env, "init", "-q", "-b", "main", str(repo))
    (repo / "README").write_text("seed\n", encoding="utf-8")
    _git(repo, env, "add", "README")
    _git(repo, env, "commit", "-q", "-m", "seed")
    repo = repo.resolve()
    _ok(["init", "--distributor", "infra"], env, repo)
    _git(repo, env, "add", ".fabrik")
    _git(repo, env, "commit", "-q", "-m", "store")
    return repo


def _add(repo: Path, env: dict[str, str], title: str) -> str:
    out = _ok(["add", "--kind", "task", "--title", title], env, repo)
    return Path(out.strip().splitlines()[-1]).stem


def _rel(item_id: str) -> str:
    return f".fabrik/work/{item_id}.json"


def _head(repo: Path, env: dict[str, str]) -> str:
    return _git(repo, env, "rev-parse", "HEAD").strip()


def _committed(repo: Path, env: dict[str, str], rev: str = "HEAD") -> set[str]:
    out = _git(repo, env, "show", "--name-only", "--format=", rev)
    return {p for p in out.splitlines() if p}


def _porcelain(repo: Path, env: dict[str, str], *paths: str) -> str:
    return _git(repo, env, "status", "--porcelain", "--untracked-files=all", "--", *paths)


def test_commit_items_commits_every_uncommitted_item_once(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    old = _add(repo, env, "an item already committed")
    _git(repo, env, "add", _rel(old))
    _git(repo, env, "commit", "-q", "-m", "old item")
    data = json.loads((repo / _rel(old)).read_text())
    data["title"] = "an item a verb changed since"
    (repo / _rel(old)).write_text(json.dumps(data, indent=2) + "\n")
    new = _add(repo, env, "an item never committed")
    before = _head(repo, env)

    out = _ok(["commit-items"], env, repo)

    assert "[main " in out and "2 item file(s)" in out, out
    assert _git(repo, env, "rev-parse", "HEAD~1").strip() == before
    assert _committed(repo, env) == {_rel(old), _rel(new)}
    assert _porcelain(repo, env, ".fabrik/work") == ""
    assert _git(repo, env, "diff", "--cached", "--name-only").strip() == ""
    trailers = _git(repo, env, "log", "-1", "--format=%(trailers:key=Agent-Role,valueonly)")
    assert trailers.strip() == "primary"
    again = _ok(["commit-items"], env, repo)
    assert _head(repo, env) == _git(repo, env, "rev-parse", "HEAD").strip()
    assert "nothing to commit" in again


def test_commit_items_refuses_outside_the_main_checkout(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env, "minted in main")
    wt = tmp_path / "wt"
    _git(repo, env, "worktree", "add", "-q", str(wt), "-b", "side")
    before = _head(repo, env)

    r = run(["commit-items"], env, wt)
    assert r.returncode != 0 and "worktree" in (r.stdout + r.stderr), (r.stdout, r.stderr)
    assert _head(repo, env) == before

    _git(repo, env, "checkout", "-q", "--detach")
    r = run(["commit-items"], env, repo)
    assert r.returncode != 0 and "detached" in (r.stdout + r.stderr), (r.stdout, r.stderr)
    assert _porcelain(repo, env, _rel(item)).startswith("??")


def test_commit_items_skips_staged_and_invalid_files(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    good = _add(repo, env, "a valid item")
    staged = _add(repo, env, "an item a sibling staged")
    _git(repo, env, "add", _rel(staged))
    (repo / _rel("W-deadbeef")).write_text("{not json")
    other = _add(repo, env, "an item whose id does not match its name")
    wrong = repo / _rel("W-0badc0de")
    (repo / _rel(other)).rename(wrong)

    out = _ok(["commit-items"], env, repo)

    assert _committed(repo, env) == {_rel(good)}
    assert _rel(staged) in out and "W-deadbeef" in out and "W-0badc0de" in out, out
    assert _git(repo, env, "diff", "--cached", "--name-only").strip() == _rel(staged)


def test_commit_items_touches_nothing_but_item_files(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env, "an item")
    (repo / "README").write_text("a sibling's half-finished edit\n")
    (repo / "notes.md").write_text("untracked sibling file\n")
    _git(repo, env, "add", "notes.md")

    _ok(["commit-items"], env, repo)

    assert _committed(repo, env) == {_rel(item)}
    assert _porcelain(repo, env, "README").startswith(" M")
    assert _git(repo, env, "diff", "--cached", "--name-only").strip() == "notes.md"


def test_a_held_index_lock_commits_nothing_and_leaves_no_residue(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env, "an item")
    before = _head(repo, env)
    lock = repo / ".git" / "index.lock"
    lock.write_text("")
    try:
        r = run(["commit-items"], env, repo)
    finally:
        lock.unlink()
    assert r.returncode == 1 and "nothing committed" in r.stderr, (r.stdout, r.stderr)
    assert _head(repo, env) == before
    assert _porcelain(repo, env, _rel(item)).startswith("??")
    _ok(["commit-items"], env, repo)
    assert _committed(repo, env) == {_rel(item)}


def test_commit_items_refuses_a_main_repo_named_from_a_worktree_or_mid_merge(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env, "an item")
    wt = tmp_path / "wt"
    _git(repo, env, "worktree", "add", "-q", str(wt), "-b", "side")
    before = _head(repo, env)

    r = run(["--repo", str(repo), "commit-items"], env, wt)
    assert r.returncode == 2 and "main checkout" in r.stderr, (r.stdout, r.stderr)

    (repo / ".git" / "MERGE_HEAD").write_text(before + "\n")
    r = run(["commit-items"], env, repo)
    assert r.returncode == 2 and "merge is in progress" in r.stderr, (r.stdout, r.stderr)
    assert _head(repo, env) == before
    assert _porcelain(repo, env, _rel(item)).startswith("??")


def _stop(repo: Path, env: dict[str, str], session: str, cwd: Path) -> dict:
    out = _ok(["queue", "--stop", "--session", session, "--cwd", str(cwd)], env, cwd)
    return json.loads(out)


def test_stop_action_names_commit_items_in_the_main_checkout_only(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _add(repo, env, "an uncommitted item")
    wt = repo / ".claude" / "worktrees" / "fleet"
    _git(repo, env, "worktree", "add", "-q", str(wt), "-b", "worktree-fleet")
    main_env = {**env, "CLAUDE_AGENT": "infra", "CLAUDE_CODE_SESSION_ID": "s-main"}
    wt_env = {**env, "CLAUDE_AGENT": "fleet", "CLAUDE_CODE_SESSION_ID": "s-wt"}

    first = _stop(repo, main_env, "s-main", repo)
    assert first.get("action") == "commit-items", first
    assert "commit-items" in first.get("text", "")
    assert _stop(repo, wt_env, "s-wt", wt).get("action") != "commit-items"

    _ok(["commit-items"], main_env, repo)
    assert _stop(repo, main_env, "s-main", repo).get("action") != "commit-items"

    _add(repo, env, "a second uncommitted item")
    again = _stop(repo, main_env, "s-main", repo)
    assert again.get("action") == "commit-items" and again["fp"] != first["fp"], (first, again)


def test_a_session_holding_a_claim_is_not_nudged_mid_task(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env, "the task in hand")
    main_env = {**env, "CLAUDE_AGENT": "infra", "CLAUDE_CODE_SESSION_ID": "s-main"}
    _ok(["claim", item, "--session", "s-main"], main_env, repo)
    assert _stop(repo, main_env, "s-main", repo).get("action") != "commit-items"


def test_the_store_gitignore_never_hides_item_files():
    assert (REPO / ".fabrik" / "work" / ".gitignore").read_text(encoding="utf-8") == "*.tmp\n"


# ── Round-1 review fixes (A-S1..A-S5, B-S3, B-S4) ─────────────────────────────────────────


def test_every_in_progress_operation_refuses_the_verb(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _add(repo, env, "an item")
    git_dir = repo / ".git"
    for marker, word in (
        ("CHERRY_PICK_HEAD", "cherry-pick"),
        ("REVERT_HEAD", "revert"),
        ("rebase-merge", "rebase"),
        ("rebase-apply", "rebase"),
    ):
        path = git_dir / marker
        path.mkdir() if marker.startswith("rebase") else path.write_text(_head(repo, env) + "\n")
        try:
            r = run(["commit-items"], env, repo)
            assert r.returncode == 2 and word in r.stderr, (marker, r.stderr)
        finally:
            path.rmdir() if marker.startswith("rebase") else path.unlink()


def test_a_deleted_item_is_reported_as_deleted_never_invalid_or_committed(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    gone = _add(repo, env, "an item later removed by hand")
    _git(repo, env, "add", _rel(gone))
    _git(repo, env, "commit", "-q", "-m", "item")
    (repo / _rel(gone)).unlink()
    out = _ok(["commit-items"], env, repo)
    assert "skipped (deleted" in out and _rel(gone) in out and "not a valid item" not in out, out
    assert _porcelain(repo, env, _rel(gone)).startswith(" D")


def test_a_retry_after_a_refused_first_attempt_commits(tmp_path, monkeypatch):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env, "an item")
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import work
    finally:
        sys.path.remove(str(SCRIPT.parent))
    real = work._commit_store_files
    calls = []

    def flaky(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise work.WorkError("index.lock held — nothing committed")
        return real(*a, **k)

    monkeypatch.setattr(work, "_commit_store_files", flaky)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.chdir(repo)
    assert work.main(["commit-items"]) == 0
    assert len(calls) == 2
    assert _committed(repo, env) == {_rel(item)}


def _autonomy(repo: Path) -> None:
    """Turn the store's autonomy flag on (uncommitted): the subject is first on that ladder."""
    cfg = repo / ".fabrik" / "work" / "config.json"
    data = json.loads(cfg.read_text())
    data["autonomy"] = True
    cfg.write_text(json.dumps(data, indent=2) + "\n")


def test_the_subject_re_arms_as_the_backlog_doubles_and_names_a_refusal(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _autonomy(repo)
    main_env = {**env, "CLAUDE_AGENT": "infra", "CLAUDE_CODE_SESSION_ID": "s-main"}
    _add(repo, env, "one")
    one = _stop(repo, main_env, "s-main", repo)
    _add(repo, env, "two")
    two = _stop(repo, main_env, "s-main", repo)
    assert one["fp"] != two["fp"], (one, two)
    _git(repo, env, "checkout", "-q", "--detach")
    blocked = _stop(repo, main_env, "s-main", repo)
    assert blocked["action"] == "commit-items" and "detached" in blocked["text"], blocked
    assert blocked["fp"] != two["fp"]


def test_a_fresh_store_with_no_commit_still_gets_the_subject(tmp_path):
    env = _env(tmp_path)
    repo = tmp_path / "fresh"
    _git(tmp_path, env, "init", "-q", "-b", "main", str(repo))
    repo = repo.resolve()
    _ok(["init", "--distributor", "infra"], env, repo)
    _autonomy(repo)
    _add(repo, env, "an item in a repo with no commit")
    main_env = {**env, "CLAUDE_AGENT": "infra", "CLAUDE_CODE_SESSION_ID": "s-main"}
    assert _stop(repo, main_env, "s-main", repo).get("action") == "commit-items"


def test_under_autonomy_a_held_claim_does_not_hide_the_subject(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    cfg = repo / ".fabrik" / "work" / "config.json"
    data = json.loads(cfg.read_text())
    data["autonomy"] = True
    cfg.write_text(json.dumps(data, indent=2) + "\n")
    _git(repo, env, "add", str(cfg))
    _git(repo, env, "commit", "-q", "-m", "autonomy on")
    item = _add(repo, env, "the task in hand")
    main_env = {**env, "CLAUDE_AGENT": "infra", "CLAUDE_CODE_SESSION_ID": "s-main"}
    _ok(["claim", item, "--session", "s-main"], main_env, repo)
    out = _stop(repo, main_env, "s-main", repo)
    assert out.get("action") == "commit-items", out
    assert any(c.get("action") == "continue" for c in out.get("candidates", [])), out


def test_a_failed_relisting_never_hides_a_skipped_file(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    gone = _add(repo, env, "an item later removed by hand")
    _git(repo, env, "add", _rel(gone))
    _git(repo, env, "commit", "-q", "-m", "item")
    (repo / _rel(gone)).unlink()
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import work
    finally:
        sys.path.remove(str(SCRIPT.parent))
    monkeypatch.setattr(work, "_uncommitted_items_strict", lambda repo: None)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.chdir(repo)
    assert work.main(["commit-items"]) == 0
    assert "skipped (deleted" in capsys.readouterr().out
