"""Behavior contract: the sync must NEVER leave a project's .gitignore without the safety floor.

The bug this locks down (found live in 3 repos, 2026-07-14):

`sync_enforcement_to_projects.py` patches the "Fabrik-synced" block into each project's .gitignore.
When the project's .gitignore was EMPTY, the else-branch produced `"\\n\\n" + block` — a .gitignore
containing ONLY the Fabrik block. Two things then go wrong:

  1. It is SELF-PERPETUATING — the block regex now matches, so every later sync just swaps the block
     and the project's own rules never come back.
  2. The Fabrik block lists only centrally-managed FILES. It does not ignore `.env`, `.venv/` or
     `__pycache__/`. So the project was left one `git add -A` away from committing secrets.

The fix is a safety floor enforced by the sync itself, which also SELF-HEALS an already-damaged repo.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture(scope="module")
def sync():
    """Load the sync script as a module (registered first so @dataclass can resolve it)."""
    spec = importlib.util.spec_from_file_location(
        "syncmod", ROOT / "scripts" / "sync_enforcement_to_projects.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["syncmod"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def block() -> str:
    from fabrik_synced_manifest import gitignore_block_text

    return str(gitignore_block_text())


def _patch(sync, block: str, content: str) -> str:
    """Mirror of the sync's .gitignore patch logic (incl. the safety floor)."""
    if sync._GITIGNORE_BLOCK_RE.search(content):
        new = sync._GITIGNORE_BLOCK_RE.sub(lambda _m: block, content)
    else:
        new = content.rstrip("\n") + "\n\n" + block
    if not sync._covers_essentials(new):
        new = sync._ESSENTIAL_IGNORES + "\n" + new.lstrip("\n")
    return new


def test_empty_gitignore_never_yields_an_unprotected_file(sync, block):
    """THE bug's trigger: an empty .gitignore used to yield block-only, leaving .env exposed."""
    out = _patch(sync, block, "")
    assert sync._covers_essentials(out)
    assert ".env" in out


def test_block_only_gitignore_self_heals(sync, block):
    """An ALREADY-damaged repo (the live captcha state) must repair itself on the next sync."""
    damaged = "\n\n" + block
    assert not sync._covers_essentials(damaged), "fixture must actually be the damaged state"

    out = _patch(sync, block, damaged)
    assert sync._covers_essentials(out)


def test_healthy_gitignore_is_not_disturbed(sync, block):
    """The project's OWN rules must survive, the block is replaced in place, and no duplicate
    safety preamble is injected into an already-safe file."""
    healthy = (
        "# Environment\n.env\n.env.local\n.venv/\nvenv/\n__pycache__/\n*.pyc\n\n"
        "# Project-specific\nmy_secret_dir/\n\n" + block
    )
    out = _patch(sync, block, healthy)

    assert sync._covers_essentials(out)
    assert "my_secret_dir/" in out, "the project's own rules must be preserved"
    assert out.count("Essential safety rules") == 0, "must not add a redundant preamble"
    assert out.count("End Fabrik-synced block") == 1, "the block must be replaced, not duplicated"


def test_covers_essentials_ignores_comments(sync):
    """A commented-out rule is not a rule — it must not count as coverage."""
    assert not sync._covers_essentials("# .env\n# .venv/\n# __pycache__/\n")
    assert sync._covers_essentials(".env\n.venv/\n__pycache__/\n")


def test_the_fabrik_block_alone_is_not_safe(sync, block):
    """Guards the root misconception: the synced block lists centrally-managed FILES — it is NOT a
    substitute for the project's ignore rules. If this ever starts passing, the block has silently
    taken on project-hygiene duties and this whole safety net needs rethinking."""
    assert not sync._covers_essentials(block)


# --------------------------------------------------------------------------- #
# The AUTHORITATIVE gate — git decides, not a hand-rolled glob matcher.        #
# --------------------------------------------------------------------------- #


def _git_repo(tmp_path: Path, gitignore: str) -> Path:
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text(gitignore)
    return tmp_path


def test_git_check_accepts_equivalent_patterns(sync, tmp_path):
    """THE reason the literal check cannot be the gate: `.env*` and `venv/` DO protect `.env`, but a
    literal line-match says otherwise. Gating on the literal check would prepend redundant rules to
    ~40 healthy repos to fix 3 — churning the fleet to fix a handful. Git knows the real semantics.
    """
    repo = _git_repo(tmp_path, ".env*\nvenv/\n.venv/\n__pycache__/\n")

    assert sync._git_covers_essentials(repo) is True
    assert sync._covers_essentials((repo / ".gitignore").read_text()) is False  # the false alarm


def test_git_check_catches_the_real_damage(sync, tmp_path, block):
    """The live bug: a .gitignore containing ONLY the Fabrik block leaves .env exposed."""
    repo = _git_repo(tmp_path, "\n\n" + block)
    assert sync._git_covers_essentials(repo) is False


def test_git_check_fails_closed_when_not_a_repo(sync, tmp_path):
    """Fail CLOSED: if git can't answer, we repair rather than risk leaving a .env exposed."""
    assert sync._git_covers_essentials(tmp_path) is False
