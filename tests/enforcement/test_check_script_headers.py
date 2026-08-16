"""The `# AFTER-EDIT:` coupling header must be parsed in BOTH separator styles.

WHY. The corpus writes the coupled-file list two ways — `a.py, b.md` and `a.py | b.md` — and the
check split on `[,\\s]+` only. Every pipe therefore parsed as a coupled FILE named `|`, which is
never staged, so every script using the majority `scripts/sysadmin/` style warned on its own edit:

    liveness_audit.py: `# AFTER-EDIT:` lists coupled file(s) not updated in this change:
    |, |, .fabrik/liveness-registry.json, |, scripts/sysadmin/kaizen_metrics.py, |.

The bug is old; it was invisible because the check was registered with neither `advisory=` nor
`warn_only=`, so `run_optional_check` DISCARDED its stdout on exit 0. Declaring the row advisory
(2026-08-16) surfaced it on the first run — which is the argument for making a warn-only row
visible rather than leaving it silently green.

These tests drive `main()` against a throwaway git repo, so they exercise the real staged-diff
path, not a re-implementation of it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECK = REPO_ROOT / "scripts" / "enforcement" / "check_script_headers.py"


def _repo(tmp_path: Path, script_body: str) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for cfg in (("user.email", "t@fabrik.local"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(tmp_path), "config", *cfg], check=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "thing.py").write_text(script_body, encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "coupled.md").write_text("# coupled\n", encoding="utf-8")
    return tmp_path


def _run(cwd: Path, *stage: str) -> str:
    subprocess.run(["git", "-C", str(cwd), "add", *stage], check=True)
    proc = subprocess.run(
        [sys.executable, str(CHECK)], cwd=cwd, capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, "WARN-only by contract — it must never block"
    return proc.stdout + proc.stderr


@pytest.mark.parametrize(
    "header",
    [
        "# AFTER-EDIT: docs/coupled.md, docs/other.md",
        "# AFTER-EDIT: docs/coupled.md | docs/other.md",
        "# AFTER-EDIT: docs/coupled.md|docs/other.md",
    ],
)
def test_a_pipe_separator_is_not_a_filename(tmp_path: Path, header: str) -> None:
    """Only the genuinely-unstaged `docs/other.md` may be named — never a bare `|`."""
    out = _run(_repo(tmp_path, f"{header}\nx = 1\n"), "scripts/thing.py", "docs/coupled.md")
    assert "docs/other.md" in out, "the real unstaged coupled file must still be reported"
    assert "|" not in out.replace(header, ""), f"a separator was parsed as a filename: {out}"


def test_every_coupled_file_staged_warns_about_nothing(tmp_path: Path) -> None:
    """The liveness_audit.py case: a pipe-separated header, all coupled files staged."""
    repo = _repo(tmp_path, "# AFTER-EDIT: docs/coupled.md | docs/coupled.md\nx = 1\n")
    out = _run(repo, "scripts/thing.py", "docs/coupled.md")
    assert "WARNING" not in out, f"a fully-satisfied pipe header must be silent, got: {out}"


def test_a_missing_header_is_still_warned(tmp_path: Path) -> None:
    """The rule the check exists for — untouched by the separator fix."""
    out = _run(_repo(tmp_path, "x = 1\n"), "scripts/thing.py")
    assert "no `# AFTER-EDIT:` header" in out
