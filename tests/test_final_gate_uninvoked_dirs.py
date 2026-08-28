"""_uninvoked_test_dirs — a green that covers `tests/` ONLY must say so.

The gate's leg runs `pytest tests/` with an explicit path, and pyproject's
``testpaths = ["tests"]`` says the same — so a suite living anywhere else is never
collected and a green run looks identical to one that ran it. Same fail-silent-green
shape as the NOT-INSTALLED skip lines, one level out (intel 01M153PX7G).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import final_gate as fg  # noqa: E402 — the path insert must precede the import

# --- uninvoked test dirs: a green that covers `tests/` only says so ------------
# intel 01M153PX7G: the gate's leg runs `pytest tests/` with an explicit path (and
# pyproject's testpaths says the same), so a suite anywhere else is never collected —
# while daily_refresh.sh:398 treats scripts/kilo-benchmarks/tests/'s golden-parity ORACLE
# as a severity=critical production gate. A green Tier-2 asserted nothing about it and
# looked identical to one that ran it. Same fail-silent-green shape as the
# NOT-INSTALLED skip lines, one level out.


def test_uninvoked_test_dirs_finds_the_kilo_oracle_suite() -> None:
    """The real case that motivated it must actually be named."""
    dirs = fg._uninvoked_test_dirs()
    assert "scripts/kilo-benchmarks/tests" in dirs, dirs


def test_uninvoked_test_dirs_excludes_the_invoked_tests_dir() -> None:
    """`tests/` IS invoked — naming it would be a false alarm on every run."""
    dirs = fg._uninvoked_test_dirs()
    assert not any(d == "tests" or d.startswith("tests/") for d in dirs), dirs


def test_uninvoked_test_dirs_excludes_scaffold_templates() -> None:
    """templates/** tests run in the EMITTED project, not this repo — reporting them
    would train the reader to ignore the line."""
    dirs = fg._uninvoked_test_dirs()
    assert not any(d.startswith("templates/") for d in dirs), dirs


def test_uninvoked_test_dirs_never_walks_the_filesystem() -> None:
    """Regression guard: the first cut used Path('.').glob('*/**/tests') and died with
    OSError(ENOMEM) walking a large untracked vault/. It must stay git-ls-files-based —
    a gate helper that can crash on a big working tree is worse than the gap it closes."""
    import inspect

    src = inspect.getsource(fg._uninvoked_test_dirs)
    assert "git" in src and "ls-files" in src, "must resolve via git, not a walk"
    # EXECUTABLE lines only. The first version of this assertion grepped raw source and
    # tripped on the comment that EXPLAINS the ENOMEM bug — a guard that fires on its own
    # documentation is the vacuous-test shape from the other direction.
    code = "\n".join(
        ln for ln in src.splitlines() if not ln.lstrip().startswith("#") and '"""' not in ln
    )
    body = code.split('"""')[-1] if '"""' in code else code
    assert ".glob(" not in body, "a filesystem glob can ENOMEM on a large tree"
