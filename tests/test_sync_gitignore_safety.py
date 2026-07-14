"""Behavior contract: the sync must NEVER leave a project's .gitignore without the safety floor.

The bug this locks down (found live in 3 repos, 2026-07-14):

`sync_enforcement_to_projects.py` patches the "Fabrik-synced" block into each project's .gitignore.
When the project's .gitignore was EMPTY, the else-branch produced `"\\n\\n" + block` — a .gitignore
containing ONLY the Fabrik block. Two things then go wrong:

  1. SELF-PERPETUATING — the block regex then matches forever, so the project's own rules never return.
  2. The Fabrik block lists only centrally-managed FILES. It does not ignore `.env`, `.venv/` or
     `__pycache__/`. The project was left one `git add -A` away from committing secrets.

⚠️ Every test calls the REAL `patched_gitignore()`. An earlier version of this file re-implemented the
logic in a local helper — so it validated a COPY, and production could drift while the suite stayed
green. That is exactly how the prepend-vs-append defect (below) survived a "passing" suite.
"""

from __future__ import annotations

import importlib.util
import subprocess
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


def _repo(tmp_path: Path, gitignore: str) -> Path:
    """A REAL git repo — git's own ignore semantics are the thing under test and cannot be faked."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text(gitignore)
    return tmp_path


def _ignores_env(repo: Path) -> bool:
    """Ask git, not a regex — this is the only authority on what is actually ignored."""
    return (
        subprocess.run(
            ["git", "check-ignore", "-q", ".env"], cwd=repo, capture_output=True, check=False
        ).returncode
        == 0
    )


# --------------------------------------------------------------------------- #
# The repair — via the REAL production function                                #
# --------------------------------------------------------------------------- #


def test_empty_gitignore_never_yields_an_unprotected_file(sync, tmp_path):
    """THE bug's trigger: an empty .gitignore used to yield block-only, leaving .env exposed."""
    repo = _repo(tmp_path, "")
    out, repaired = sync.patched_gitignore("", repo)

    assert repaired
    (repo / ".gitignore").write_text(out)
    assert _ignores_env(repo), "git must actually ignore .env after the repair"


def test_block_only_gitignore_self_heals(sync, tmp_path, block):
    """An ALREADY-damaged repo (the live captcha state) must repair itself on the next sync."""
    repo = _repo(tmp_path, "\n\n" + block)
    assert not _ignores_env(repo), "fixture must really be the damaged, exposed state"

    out, repaired = sync.patched_gitignore((repo / ".gitignore").read_text(), repo)
    assert repaired
    (repo / ".gitignore").write_text(out)
    assert _ignores_env(repo)


def test_the_floor_beats_a_later_project_negation(sync, tmp_path, block):
    """REGRESSION — the floor is APPENDED, not prepended, and that is load-bearing.

    In .gitignore the LAST matching rule wins. Prepending put the safety floor FIRST, so a project
    rule as innocuous as a stray `!.env` silently overrode it: the sync printed "restored" while
    `.env` was still exposed. A safety mechanism that lies about having fixed something is worse than
    none — it buys false confidence. Appending makes the floor actually win.
    """
    repo = _repo(tmp_path, "# project rules\n!.env\n")
    assert not _ignores_env(repo), "fixture must start exposed"

    out, repaired = sync.patched_gitignore((repo / ".gitignore").read_text(), repo)
    assert repaired
    (repo / ".gitignore").write_text(out)

    assert _ignores_env(repo), "the floor must WIN over a later `!.env` — else it is not a floor"


def test_healthy_gitignore_is_not_disturbed(sync, tmp_path, block):
    """A project that already protects itself must be left alone — no redundant floor, no churn."""
    healthy = (
        "# Environment\n.env\n.env.local\n.venv/\nvenv/\n__pycache__/\n*.pyc\n\n"
        "# Project-specific\nmy_secret_dir/\n\n" + block
    )
    repo = _repo(tmp_path, healthy)

    out, repaired = sync.patched_gitignore(healthy, repo)

    assert not repaired, "an already-safe project must not be touched (that churns the fleet)"
    assert "my_secret_dir/" in out, "the project's own rules must survive"
    assert out.count("Essential safety rules") == 0, "no redundant floor on a healthy repo"
    assert out.count("End Fabrik-synced block") == 1, "block replaced, not duplicated"


def test_repair_is_idempotent(sync, tmp_path):
    """Repeated syncs must not stack duplicate floors — once safe, it stops repairing."""
    repo = _repo(tmp_path, "")
    for _ in range(3):
        out, _r = sync.patched_gitignore((repo / ".gitignore").read_text(), repo)
        (repo / ".gitignore").write_text(out)

    assert (repo / ".gitignore").read_text().count("Essential safety rules") == 1
    assert _ignores_env(repo)


def test_env_example_stays_committable(sync, tmp_path):
    """`.env.example` is a template that MUST be committed — the negation must survive the floor."""
    repo = _repo(tmp_path, "")
    out, _r = sync.patched_gitignore("", repo)
    (repo / ".gitignore").write_text(out)

    rc = subprocess.run(
        ["git", "check-ignore", "-q", ".env.example"], cwd=repo, capture_output=True, check=False
    ).returncode
    assert rc != 0, ".env.example must NOT be ignored — it is the committed template"


def test_non_repo_dir_does_not_stack_floors_forever(sync, tmp_path):
    """REGRESSION — the fail-closed branch was NOT idempotent, and it grew the file without bound.

    `_git_covers_essentials` fails closed, and a NON-repo makes `check-ignore` return 128 → read as
    "not ignored" → repair. But a non-repo can never *become* covered, so it repaired on EVERY run:
    floors 1 → 2 → 3, the file growing each sync. And `main()` discovers projects by `is_dir()`
    WITHOUT requiring `.git`, so plain directories under /opt are in the sync set today.
    """
    (tmp_path / ".gitignore").write_text("")  # a dir with a .gitignore but NO git repo

    for _ in range(3):
        out, repaired = sync.patched_gitignore((tmp_path / ".gitignore").read_text(), tmp_path)
        (tmp_path / ".gitignore").write_text(out)
        assert not repaired, "a non-repo has no clone to leak into — it must not be 'repaired'"

    assert (tmp_path / ".gitignore").read_text().count("Essential safety rules") == 0


def test_floor_is_never_appended_twice(sync, tmp_path):
    """Belt-and-braces: even if git keeps answering 'not covered' (e.g. a nested .gitignore defeats
    the floor), we must not append it again every sync — that grows the file forever while fixing
    nothing."""
    repo = _repo(tmp_path, "")
    out, _ = sync.patched_gitignore("", repo)
    (repo / ".gitignore").write_text(out)

    # nested .gitignore that re-exposes .env — git will still say "not covered"
    (repo / "sub").mkdir()
    (repo / "sub" / ".gitignore").write_text("!.env\n")

    out2, repaired2 = sync.patched_gitignore(out, repo)
    assert not repaired2, "the floor is already present — never append a second one"
    assert out2.count("Essential safety rules") == 1


def test_missing_gitignore_is_created_with_the_floor(sync, tmp_path):
    """REGRESSION — a repo with NO .gitignore is strictly MORE exposed than a block-only one, yet the
    safety net used to be gated on `if gitignore.exists()`: guarded by the very file whose absence is
    the hazard."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    assert not (tmp_path / ".gitignore").exists()

    out, repaired = sync.patched_gitignore("", tmp_path)
    assert repaired
    (tmp_path / ".gitignore").write_text(out)
    assert _ignores_env(tmp_path)


def test_a_local_only_exclude_does_not_count_as_safe(sync, tmp_path):
    """REGRESSION — FAIL-OPEN. `git check-ignore` honours `.git/info/exclude` and the user's GLOBAL
    ignore. Neither travels with the repo. If a damaged project's `.env` were ignored only by a
    local-only rule, the check answered "safe", the repair never fired, and every fresh clone — CI, a
    teammate, the VPS — stayed UNPROTECTED. The rule must hold for the REPO, not for this machine.
    """
    repo = _repo(tmp_path, "")  # committed .gitignore protects nothing
    info = repo / ".git" / "info"
    info.mkdir(parents=True, exist_ok=True)
    (info / "exclude").write_text(".env\n.venv/\n__pycache__/\n")

    # git itself now says .env IS ignored (locally!) — the trap.
    assert _ignores_env(repo), "fixture must reproduce the local-only ignore"

    # ...but our check must NOT be fooled: the rule is not in a tracked .gitignore.
    assert sync._git_covers_essentials(repo) is False


# --------------------------------------------------------------------------- #
# The AUTHORITATIVE gate — git decides, not a hand-rolled glob matcher.        #
# --------------------------------------------------------------------------- #


def test_git_check_accepts_equivalent_patterns(sync, tmp_path):
    """Why the literal check cannot be the gate: `.env*` and `venv/` DO protect `.env`, but a literal
    line-match says otherwise. Gating on it would churn ~40 healthy repos to fix 3."""
    repo = _repo(tmp_path, ".env*\nvenv/\n.venv/\n__pycache__/\n")

    assert sync._git_covers_essentials(repo) is True
    assert sync._covers_essentials((repo / ".gitignore").read_text()) is False  # the false alarm


def test_git_check_fails_closed_when_not_a_repo(sync, tmp_path):
    """Fail CLOSED: if git can't answer, repair rather than risk leaving a .env exposed."""
    assert sync._git_covers_essentials(tmp_path) is False


def test_the_fabrik_block_alone_is_not_safe(sync, block):
    """Guards the root misconception: the synced block lists centrally-managed FILES — it is NOT a
    substitute for the project's ignore rules. If this ever starts passing, the block has silently
    taken on project-hygiene duties and this whole net needs rethinking."""
    assert not sync._covers_essentials(block)
