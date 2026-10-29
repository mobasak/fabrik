"""The push law binds a linked-worktree branch that has no upstream (T03a, spec § D4 / V4).

`_ahead_of_upstream` used to answer None for every branch without `@{upstream}` — "mid-plan
worktree branches have no upstream by design" — so committed work on a worktree branch never
tripped the UNPUSHED cause. Under the worktree model that is exactly the state the push law
exists for: the base is the main checkout's branch (the git common dir's symbolic HEAD, the rule
`scripts/final_gate.py::_linked_worktree_base` uses), and a detached main checkout still answers
None, never a block.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "final_gate_stop.py"
_spec = importlib.util.spec_from_file_location("fgs_worktree_push", _HOOK)
hook = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(hook)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path) -> None:
    """No hook side effect reaches the operator's real state."""
    monkeypatch.delenv("CLAUDE_MESH_HEADLESS", raising=False)
    monkeypatch.setenv("THREAD_ANCHOR_DIR", str(tmp_path / "threads"))
    monkeypatch.setenv("COMMAND_RUN_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _main_and_worktree(tmp_path: Path, *, remote: bool = True) -> tuple[Path, Path]:
    """A main checkout on `master` (pushed to a bare `origin` unless `remote=False`) and a linked
    worktree on `feat` — no upstream — holding one commit of `notes.txt` that is not on `master`."""
    main = tmp_path / "main"
    subprocess.run(["git", "init", "-q", "-b", "master", str(main)], check=True)
    for cfg in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        _git(main, "config", *cfg)
    (main / "scripts").mkdir()
    (main / "scripts" / "final_gate.py").write_text("", encoding="utf-8")
    _git(main, "add", "scripts/final_gate.py")
    _git(main, "commit", "-qm", "base")
    if remote:
        origin = tmp_path / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "master", str(origin)], check=True)
        _git(main, "remote", "add", "origin", str(origin))
        _git(main, "push", "-q", "-u", "origin", "master")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "feat", str(wt))
    (wt / "notes.txt").write_text("a note\n", encoding="utf-8")
    _git(wt, "add", "notes.txt")
    _git(wt, "commit", "-qm", "docs: a note")
    return main, wt


def _drive(monkeypatch, tmp_path: Path, proj: Path) -> str:
    """Run the Stop hook's main() on a transcript that wrote `notes.txt` in `proj`."""
    tr = tmp_path / "t.jsonl"
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    entries = [
        {"type": "user", "message": {"content": [{"type": "text", "text": "write a note"}]}},
        {
            "type": "assistant",
            "timestamp": stamp,
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Write",
                        "input": {"file_path": str(proj / "notes.txt")},
                    }
                ]
            },
        },
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Committed."}]}},
    ]
    tr.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    # A closed command covering the note, so the SIXTH cause (which reviews every file since
    # W-ea06749b, `.txt` included) stays out of these push-law probes.
    runs = tmp_path / "runs"
    runs.mkdir(exist_ok=True)
    (runs / "sidwt.json").write_text(
        json.dumps(
            {
                "command": "fabrik-review-scoped",
                "state": "done",
                "started_epoch": 1.0,
                "updated_ts": time.time() + 120,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("COMMAND_RUN_DIR", str(runs))
    payload = {"cwd": str(proj), "session_id": "sidwt", "transcript_path": str(tr)}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(hook.tempfile, "gettempdir", lambda: str(tmp_path))
    assert hook.main([]) == 0
    return out.getvalue().strip()


def test_a_worktree_commit_without_upstream_counts_and_blocks(monkeypatch, tmp_path: Path) -> None:
    """V4: an unpushed commit on a worktree branch with no upstream blocks the Stop hook."""
    _main, wt = _main_and_worktree(tmp_path)
    assert hook._ahead_of_upstream(wt, {"notes.txt"}) == 1
    out = _drive(monkeypatch, tmp_path, wt)
    assert out, "the push cause did not fire on a worktree branch holding committed work"
    assert "UNPUSHED WORK" in json.loads(out)["reason"]


def test_the_count_is_zero_once_merged_into_the_main_branch(tmp_path: Path) -> None:
    main, wt = _main_and_worktree(tmp_path)
    _git(main, "merge", "-q", "--ff-only", "feat")
    assert hook._ahead_of_upstream(wt, {"notes.txt"}) == 0


def test_the_block_names_the_upstream_setting_push_and_the_list_agrees(
    monkeypatch, tmp_path: Path
) -> None:
    _main, wt = _main_and_worktree(tmp_path)
    reason = json.loads(_drive(monkeypatch, tmp_path, wt))["reason"]
    assert "git push -u origin HEAD" in reason
    assert "git pull --rebase=merges" not in reason
    sha = _git(wt, "rev-parse", "--short", "HEAD")
    assert hook.session_unpushed(wt, {"notes.txt"}) == [f"{sha} docs: a note"]


def test_the_upstream_block_text_is_unchanged(monkeypatch, tmp_path: Path) -> None:
    """The MIRROR: a branch WITH an upstream keeps the pull-then-push remedy."""
    main, _wt = _main_and_worktree(tmp_path)
    (main / "notes.txt").write_text("a main note\n", encoding="utf-8")
    _git(main, "add", "notes.txt")
    _git(main, "commit", "-qm", "docs: main note")
    reason = json.loads(_drive(monkeypatch, tmp_path, main))["reason"]
    assert "git pull --rebase=merges" in reason
    assert "git push -u origin HEAD" not in reason


def test_a_detached_main_checkout_is_indeterminate(tmp_path: Path) -> None:
    main, wt = _main_and_worktree(tmp_path)
    _git(main, "checkout", "-q", "--detach")
    assert hook._ahead_of_upstream(wt, {"notes.txt"}) is None
    assert hook.session_unpushed(wt, {"notes.txt"}) == []


def test_no_repo_is_indeterminate(tmp_path: Path) -> None:
    assert hook._ahead_of_upstream(tmp_path, {"notes.txt"}) is None
    assert hook.session_unpushed(tmp_path, {"notes.txt"}) == []


def test_a_repo_with_no_remote_is_indeterminate(monkeypatch, tmp_path: Path) -> None:
    """`git push -u origin HEAD` cannot succeed without a remote, so the fallback never blocks."""
    _main, wt = _main_and_worktree(tmp_path, remote=False)
    assert hook._ahead_of_upstream(wt, {"notes.txt"}) is None
    assert hook.session_unpushed(wt, {"notes.txt"}) == []
    assert _drive(monkeypatch, tmp_path, wt) == ""


def test_a_repo_whose_only_remote_is_not_origin_is_indeterminate(
    monkeypatch, tmp_path: Path
) -> None:
    """The remedy names `origin`; a repo whose only remote is `upstream` cannot run it."""
    main, wt = _main_and_worktree(tmp_path, remote=False)
    other = tmp_path / "upstream.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "master", str(other)], check=True)
    _git(main, "remote", "add", "upstream", str(other))
    assert hook._ahead_of_upstream(wt, {"notes.txt"}) is None
    assert hook.session_unpushed(wt, {"notes.txt"}) == []
    assert _drive(monkeypatch, tmp_path, wt) == ""


def test_an_origin_with_only_a_pushurl_is_indeterminate(monkeypatch, tmp_path: Path) -> None:
    """A pushurl-only `origin` accepts the push but never creates `refs/remotes/origin/<b>`, so
    `@{upstream}` never resolves and the block would repeat forever."""
    main, wt = _main_and_worktree(tmp_path, remote=False)
    bare = tmp_path / "push-only.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "master", str(bare)], check=True)
    _git(main, "config", "remote.origin.pushurl", str(bare))
    assert hook._ahead_of_upstream(wt, {"notes.txt"}) is None
    assert hook.session_unpushed(wt, {"notes.txt"}) == []
    assert _drive(monkeypatch, tmp_path, wt) == ""


def _worktree_on(main: Path, wt: Path) -> None:
    _git(main, "worktree", "add", "-q", "-b", "feat", str(wt))
    (wt / "notes.txt").write_text("a note\n", encoding="utf-8")
    _git(wt, "add", "notes.txt")
    _git(wt, "commit", "-qm", "docs: a note")


def _blocks_then_steps_aside_after_push_u(monkeypatch, tmp_path: Path, wt: Path) -> None:
    assert hook._ahead_of_upstream(wt, {"notes.txt"}) == 1
    assert "UNPUSHED WORK" in json.loads(_drive(monkeypatch, tmp_path, wt))["reason"]
    _git(wt, "push", "-q", "-u", "origin", "HEAD")
    assert hook._ahead_of_upstream(wt, {"notes.txt"}) is None, (
        "the block would repeat forever after the remedy it names has run"
    )


def test_a_single_branch_clone_steps_aside_after_push_u(monkeypatch, tmp_path: Path) -> None:
    """A `--single-branch` (or `--depth 1`) clone's fetch refspec maps only `master`, so
    `push -u` creates no `refs/remotes/origin/feat` and `@{upstream}` never resolves."""
    seed, _ = _main_and_worktree(tmp_path / "seed")
    origin = tmp_path / "seed" / "origin.git"
    assert _git(seed, "remote", "get-url", "origin") == str(origin)
    main = tmp_path / "main"
    subprocess.run(
        ["git", "clone", "-q", "--single-branch", "-b", "master", str(origin), str(main)],
        check=True,
    )
    for cfg in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        _git(main, "config", *cfg)
    wt = tmp_path / "wt"
    _worktree_on(main, wt)
    _blocks_then_steps_aside_after_push_u(monkeypatch, tmp_path, wt)


def test_an_unset_fetch_refspec_steps_aside_after_push_u(monkeypatch, tmp_path: Path) -> None:
    main, wt = _main_and_worktree(tmp_path)
    _git(main, "config", "--unset", "remote.origin.fetch")
    _blocks_then_steps_aside_after_push_u(monkeypatch, tmp_path, wt)


def test_a_repo_path_with_spaces_still_counts(tmp_path: Path) -> None:
    """The linked-worktree probe reads two PATHS from git; a space in them must not split them."""
    _main, wt = _main_and_worktree(tmp_path / "sp ace")
    assert " " in str(wt)
    assert hook._ahead_of_upstream(wt, {"notes.txt"}) == 1


def test_a_repo_path_with_a_form_feed_still_counts(tmp_path: Path) -> None:
    """`str.splitlines()` also breaks on \\x0b, \\x0c, \\x1c-\\x1e, \\x85, U+2028/9 — only `\\n` may."""
    _main, wt = _main_and_worktree(tmp_path / "form\x0cfeed")
    assert "\x0c" in str(wt)
    assert hook._ahead_of_upstream(wt, {"notes.txt"}) == 1


def test_a_detached_worktree_is_indeterminate(tmp_path: Path) -> None:
    """`git push -u origin HEAD` fails on a detached HEAD, so it must never be the remedy."""
    _main, wt = _main_and_worktree(tmp_path)
    _git(wt, "checkout", "-q", "--detach")
    assert hook._ahead_of_upstream(wt, {"notes.txt"}) is None
    assert hook.session_unpushed(wt, {"notes.txt"}) == []


def test_a_main_checkout_branch_without_upstream_is_indeterminate(tmp_path: Path) -> None:
    """HEAD ON the common dir's branch is the main checkout itself: no base, not a count of 0."""
    main, _wt = _main_and_worktree(tmp_path)
    _git(main, "checkout", "-q", "-b", "other")
    (main / "other.txt").write_text("o\n", encoding="utf-8")
    _git(main, "add", "other.txt")
    _git(main, "commit", "-qm", "other")
    assert hook._ahead_of_upstream(main, {"other.txt"}) is None


def test_a_commit_already_on_a_remote_is_not_counted(tmp_path: Path) -> None:
    """On `origin/master` but not yet on local `master`: it is off-box, so nothing to push."""
    _main, wt = _main_and_worktree(tmp_path)
    _git(wt, "push", "-q", "origin", "HEAD:master")
    assert _git(wt, "branch", "-r", "--contains", "HEAD") == "origin/master"
    assert hook._ahead_of_upstream(wt, {"notes.txt"}) == 0
    assert hook.session_unpushed(wt, {"notes.txt"}) == []


def test_a_gone_upstream_after_merge_is_not_counted(tmp_path: Path) -> None:
    """The branch was pushed, merged on the remote, and its remote branch deleted."""
    _main, wt = _main_and_worktree(tmp_path)
    _git(wt, "push", "-q", "-u", "origin", "feat")
    _git(wt, "push", "-q", "origin", "HEAD:master")
    _git(wt, "push", "-q", "origin", "--delete", "feat")
    gone = subprocess.run(
        ["git", "-C", str(wt), "rev-parse", "--verify", "--quiet", "@{upstream}"],
        capture_output=True,
    )
    assert gone.returncode != 0, "the fixture's upstream is not gone"
    # `branch.feat.merge` is still set, so the fallback steps aside: indeterminate, never a block
    assert hook._ahead_of_upstream(wt, {"notes.txt"}) is None


def test_one_deadline_bounds_the_whole_worktree_path(monkeypatch, tmp_path: Path) -> None:
    """`timeout` is the budget for the whole call, not per git call: the worktree path makes up to
    six, and `scripts/thread_anchor.py` hands over what is left of a ~2 s budget."""
    _main, wt = _main_and_worktree(tmp_path)
    real_git = shutil.which("git")
    assert real_git
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    shim = shim_dir / "git"
    shim.write_text(
        f'#!/bin/sh\nsleep 0.4 </dev/null >/dev/null 2>&1\nexec "{real_git}" "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    t0 = time.monotonic()
    hook.session_unpushed(wt, {"notes.txt"}, timeout=1.0)
    elapsed = time.monotonic() - t0
    assert elapsed < 1.6, f"a 1.0 s budget took {elapsed:.2f} s"


def test_every_push_remedy_names_the_gate_first(monkeypatch, tmp_path: Path) -> None:
    """kaizen 01M4EP8A40: close-chain orders commit → gate → push, but the Stop hook ordered a bare
    push — on a clean tree it never runs the gate, so a red-gated commit was told to publish. Every
    ORDINARY push remedy now carries `_GATE_BEFORE_PUSH` before its push command (both unpushed
    branches, driven; block_commit's "Then PUSH it", by its source); the urgent-90 checkpoint item
    stays push-only (D-306: that tier runs no gate, and the wall holds the Bash one would need)."""
    import ast

    gate = hook._GATE_BEFORE_PUSH
    assert "final_gate.py --check --json" in gate and "report it" in gate, gate
    main, wt = _main_and_worktree(tmp_path)
    for root, push in ((wt, "git push -u origin HEAD"), (main, "`git push`")):
        if root is main:
            (main / "notes.txt").write_text("a main note\n", encoding="utf-8")
            _git(main, "add", "notes.txt")
            _git(main, "commit", "-qm", "docs: main note")
        reason = json.loads(_drive(monkeypatch, tmp_path, root))["reason"]
        assert gate in reason and reason.index(gate) < reason.index(push), reason
        after = reason[reason.index(gate) + len(gate) :]
        assert after.startswith(("then push", "then publish")) and "push — then" not in reason, (
            reason
        )
    tree = ast.parse(Path(hook.__file__).read_text(encoding="utf-8"))
    urgent = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_urgent_checkpoint"
    )
    in_urgent = {id(n) for n in ast.walk(urgent)}
    orders = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or id(node) in in_urgent:
            continue
        text = "".join(
            c.value
            for c in ast.walk(node.value)
            if isinstance(c, ast.Constant) and isinstance(c.value, str)
        )
        if "git push" in text or "PUSH it" in text:
            orders += 1
            gate_at = [
                (n.lineno, n.col_offset)
                for n in ast.walk(node.value)
                if isinstance(n, ast.Name) and n.id == "_GATE_BEFORE_PUSH"
            ]
            push_at = [
                (c.lineno, c.col_offset)
                for c in ast.walk(node.value)
                if isinstance(c, ast.Constant)
                and isinstance(c.value, str)
                and ("git push" in c.value or "PUSH it" in c.value)
            ]
            # the gate clause comes BEFORE the push order in the source of the same expression
            assert gate_at and min(gate_at) < min(push_at), ast.unparse(node)[:200]
    assert orders >= 3, orders  # the two unpushed reasons and block_commit's
    urgent_text = "".join(
        c.value
        for c in ast.walk(urgent)
        if isinstance(c, ast.Constant) and isinstance(c.value, str)
    )
    assert "PUSH" in urgent_text and "--check --json" not in urgent_text


def test_a_mismatched_upstream_is_told_to_push_under_its_own_name(
    monkeypatch, tmp_path: Path
) -> None:
    """W-43ccb000: a worktree branch created from origin/master (`worktree add -b x path origin/master`,
    autoSetupMerge) tracks origin/master, so a plain `git push` is refused under push.default=simple
    ("the upstream branch … does not match the name of your current branch"). Such a branch is told
    `git push -u origin HEAD`, and the reason no longer claims it "has no upstream"; a branch whose
    upstream has its own name keeps the plain push."""
    main, _wt = _main_and_worktree(tmp_path)
    mismatched = tmp_path / "wtx"
    _git(main, "fetch", "-q", "origin")
    _git(main, "worktree", "add", "-q", "-b", "x", str(mismatched), "origin/master")
    assert _git(mismatched, "config", "--get", "branch.x.merge") == "refs/heads/master"
    (mismatched / "notes.txt").write_text("x note\n", encoding="utf-8")
    _git(mismatched, "add", "notes.txt")
    _git(mismatched, "commit", "-qm", "docs: x note")
    assert hook._has_upstream(mismatched) is False
    reason = json.loads(_drive(monkeypatch, tmp_path, mismatched))["reason"]
    assert "git push -u origin HEAD" in reason and "has no upstream" not in reason, reason
    assert "named differently" in reason, reason
    assert hook._has_upstream(main) is True  # master tracking origin/master keeps `git push`
