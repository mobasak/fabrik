"""W-a312d48c — the § EXIT push ladder checks the upstream's reflog for a rewrite before it rebases (D-1178).

WHY. Both contracts told a rejected clean-tree push to run `git pull --rebase=merges`, which "replays only YOUR
unpushed commits". After someone force-rewrites the remote branch that is false: pull's fork-point skips every
commit the old remote tip held, so commits this clone had already pushed vanish at exit 0 with no conflict
(fabrik-lib D-480, reproduced in this file). The ladder now reads `git reflog show --format=%gs @{u}` from the top:
a `forced-update` line above the newest `update by push` line means stop and report; none means
`git rebase --rebase-merges @{u}`, which does no fork-point filtering, so no pushed commit is skipped.

The tests run the documented decision against throwaway repos — the reflog command is taken from each contract's
own text, so a contract that renames it fails here — and pin that both contracts drop the false claim.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CONTRACTS = ("CLAUDE.md", "templates/governance/CLAUDE.md")
ENV = {
    **{k: v for k, v in os.environ.items() if not k.startswith("GIT_")},  # a hook's GIT_DIR/GIT_INDEX_FILE
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, env=ENV, text=True, capture_output=True, check=check)


def _commit(clone: Path, name: str) -> None:
    (clone / name).write_text(name, encoding="utf-8")
    _git(clone, "add", name)
    _git(clone, "commit", "-q", "-m", name)


def _exit_step(rel: str) -> str:
    text = (REPO / rel).read_text(encoding="utf-8")
    start = text.index("5. **EXIT**")
    return " ".join(text[start : text.index("**Then CLEAN your own scratch**", start)].split())


def _reflog_command(rel: str) -> list[str]:
    m = re.search(r"read `(git reflog show [^`]+)` from the top", _exit_step(rel))
    assert m, f"{rel}: the ladder no longer names the reflog read"
    return m.group(1).split()


def _verdict(clone: Path, rel: str) -> str:
    """The ladder's decision, read off the reflog the way the contract says: top line first."""
    out = subprocess.run(_reflog_command(rel), cwd=clone, env=ENV, text=True, capture_output=True, check=True)
    for line in out.stdout.splitlines():
        if "forced-update" in line:
            return "stop"
        if "update by push" in line:
            return "rebase"
    return "rebase"


@pytest.fixture
def two_clones(tmp_path: Path) -> tuple[Path, Path]:
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    a, b = tmp_path / "A", tmp_path / "B"
    _git(tmp_path, "clone", "-q", str(origin), str(a))
    _git(tmp_path, "clone", "-q", str(origin), str(b))
    _commit(a, "base.txt")
    _git(a, "push", "-q", "-u", "origin", "main")
    _git(b, "pull", "-q")
    return a, b


def _rewrite_remote_after_a_pushed(a: Path, b: Path) -> None:
    _commit(a, "pushed.txt")
    _git(a, "push", "-q")
    _git(b, "pull", "-q")
    _git(b, "reset", "-q", "--hard", "HEAD~1")
    _commit(b, "other.txt")
    _git(b, "push", "-q", "--force")
    _commit(a, "later.txt")
    assert _git(a, "push", "-q", check=False).returncode != 0


def test_the_old_ladder_step_drops_a_pushed_commit(two_clones: tuple[Path, Path]) -> None:
    """The defect the ladder no longer recommends: pull --rebase exits 0 and the pushed commit is gone."""
    a, b = two_clones
    _rewrite_remote_after_a_pushed(a, b)
    assert _git(a, "pull", "-q", "--rebase=merges", check=False).returncode == 0
    assert not (a / "pushed.txt").exists()


@pytest.mark.parametrize("rel", CONTRACTS)
def test_a_rewrite_seen_by_this_fetch_stops(two_clones: tuple[Path, Path], rel: str) -> None:
    a, b = two_clones
    _rewrite_remote_after_a_pushed(a, b)
    _git(a, "fetch", "-q")
    assert _verdict(a, rel) == "stop"


@pytest.mark.parametrize("rel", CONTRACTS)
def test_a_rewrite_an_earlier_fetch_already_saw_still_stops(two_clones: tuple[Path, Path], rel: str) -> None:
    a, b = two_clones
    _rewrite_remote_after_a_pushed(a, b)
    _git(a, "fetch", "-q")
    _git(a, "fetch", "-q")
    assert _verdict(a, rel) == "stop"


@pytest.mark.parametrize("rel", CONTRACTS)
def test_a_normal_advance_rebases_and_keeps_every_commit(two_clones: tuple[Path, Path], rel: str) -> None:
    a, b = two_clones
    _commit(a, "pushed.txt")
    _git(a, "push", "-q")
    _git(b, "pull", "-q")
    _commit(b, "theirs.txt")
    _git(b, "push", "-q")
    _commit(a, "mine.txt")
    assert _git(a, "push", "-q", check=False).returncode != 0
    _git(a, "fetch", "-q")
    assert _verdict(a, rel) == "rebase"
    _git(a, "rebase", "-q", "--rebase-merges", "@{u}")
    _git(a, "push", "-q")
    assert all((a / f).exists() for f in ("pushed.txt", "theirs.txt", "mine.txt"))


@pytest.mark.parametrize("rel", CONTRACTS)
def test_a_never_pushed_clone_still_stops_on_a_rewrite(tmp_path: Path, rel: str) -> None:
    """No `update by push` line at all: the contract's "or anywhere when there is no such line" makes it a stop."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    b, c = tmp_path / "B", tmp_path / "C"
    _git(tmp_path, "clone", "-q", str(origin), str(b))
    _commit(b, "one.txt")
    _commit(b, "two.txt")
    _git(b, "push", "-q", "-u", "origin", "main")
    _git(tmp_path, "clone", "-q", str(origin), str(c))
    assert _verdict(c, rel) == "rebase"  # a fresh clone's empty upstream reflog takes the "none" branch
    _git(b, "reset", "-q", "--hard", "HEAD~1")
    _commit(b, "three.txt")
    _git(b, "push", "-q", "--force")
    _git(c, "fetch", "-q")
    assert _verdict(c, rel) == "stop"


def test_no_upstream_makes_the_reflog_read_fail(tmp_path: Path) -> None:
    """The contract's `no upstream (`@{u}` errors) → stop` case: the read itself errors, it never reads as clean."""
    _git(tmp_path, "init", "-q", "-b", "main", str(tmp_path / "solo"))
    _commit(tmp_path / "solo", "only.txt")
    cmd = _reflog_command("CLAUDE.md")
    assert subprocess.run(cmd, cwd=tmp_path / "solo", env=ENV, capture_output=True).returncode != 0


@pytest.mark.parametrize("rel", CONTRACTS)
def test_the_contract_drops_the_false_claim(rel: str) -> None:
    step = _exit_step(rel)
    assert "replays only YOUR unpushed" not in step
    assert "`git pull --rebase=merges`" not in step
    ladder = step[step.index("tree CLEAN →") : step.index("**NEVER `--force`**")]
    # the rule, not loose phrases: the stop-to-none span is pinned whole, so no qualifier or extra step fits in it
    assert re.search(
        r"a `forced-update` line above the newest `update by push` line, or anywhere when there is no such line,"
        r" means the remote branch was REWRITTEN since you last pushed \(by this fetch or an earlier one, which"
        r" comparing tips misses\) → stop and report, never rebase onto it — a rebase pushes back what the rewrite"
        r" removed, and `git pull --rebase` silently DROPS your own already-pushed commits at exit 0 \(its"
        r" fork-point skips them; reproduced, fabrik-lib D-480, (?:hub )?D-1178\); none → `git rebase"
        r" --rebase-merges @\{u\}` then push \(",
        ladder,
    ), f"{rel}: the stop/rebase rule is reworded, qualified or reordered"
    assert ladder.count("`git rebase --rebase-merges @{u}`") == 1
    assert ladder.count("git pull") == 1, f"{rel}: `git pull` may appear only as the warning"
    assert "no upstream (`@{u}` errors), or a rejection that is not a non-fast-forward" in ladder
    assert "**NEVER `--force`**" in step
