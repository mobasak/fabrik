# AFTER-EDIT: scripts/release_cut.py
"""Release cut: [Unreleased] graduates to a semver section + annotated tag.

Bump law: BREAKING anywhere in an entry title → major · any '### Added' → minor
· else patch. Current version = highest v* tag (fallback: 0.0.0 → first cut
derives from the bump). Empty [Unreleased] → refuse (nothing to release)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/release_cut.py"

CHANGELOG = """# Changelog

## [Unreleased]

### Added — new export endpoint (2026-08-09)
Adds /export.

### Fixed — off-by-one in pager (2026-08-08)
Fixes paging.

## [0.3.1] — 2026-07-30

### Fixed — old stuff
"""


def _repo(tmp_path: Path, changelog: str = CHANGELOG, tag: str | None = "v0.3.1") -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "master"], cwd=r, check=True, timeout=15)
    (r / "CHANGELOG.md").write_text(changelog)
    subprocess.run(["git", "add", "-A"], cwd=r, check=True, timeout=15)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"],
        cwd=r, check=True, timeout=15,
    )
    if tag:
        subprocess.run(["git", "tag", tag], cwd=r, check=True, timeout=15)
    return r


def _run(repo: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=repo, capture_output=True, text=True, timeout=30,
    )
    return proc.returncode, proc.stdout + proc.stderr


def test_dry_run_derives_minor_bump_from_added(tmp_path: Path) -> None:
    rc, out = _run(_repo(tmp_path), "--dry-run")
    assert rc == 0
    assert "0.4.0" in out  # Added → minor over v0.3.1
    assert "2 entr" in out  # both entries counted


def test_patch_bump_when_only_fixed_changed(tmp_path: Path) -> None:
    cl = CHANGELOG.replace("### Added — new export endpoint (2026-08-09)\nAdds /export.\n\n", "")
    rc, out = _run(_repo(tmp_path, changelog=cl), "--dry-run")
    assert rc == 0 and "0.3.2" in out


def test_breaking_gives_major(tmp_path: Path) -> None:
    cl = CHANGELOG.replace("### Fixed — off-by-one", "### Changed — BREAKING: pager API removed\nx.\n\n### Fixed — off-by-one")
    rc, out = _run(_repo(tmp_path, changelog=cl), "--dry-run")
    assert rc == 0 and "1.0.0" in out


def test_empty_unreleased_refuses(tmp_path: Path) -> None:
    cl = "# Changelog\n\n## [Unreleased]\n\n## [0.3.1] — 2026-07-30\n\n### Fixed — old\n"
    rc, out = _run(_repo(tmp_path, changelog=cl), "--dry-run")
    assert rc == 1 and "nothing to release" in out.lower()


def test_execute_graduates_and_tags(tmp_path: Path) -> None:
    r = _repo(tmp_path)
    rc, out = _run(r, "--execute", "--no-push", "--no-gh-release")
    assert rc == 0, out
    text = (r / "CHANGELOG.md").read_text()
    assert "## [0.4.0]" in text
    # [Unreleased] stays, empty, atop
    assert text.index("## [Unreleased]") < text.index("## [0.4.0]")
    assert "new export endpoint" in text.split("## [0.4.0]")[1].split("## [0.3.1]")[0]
    tags = subprocess.run(["git", "tag"], cwd=r, capture_output=True, text=True).stdout
    assert "v0.4.0" in tags
    # the graduation is committed
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=r, capture_output=True, text=True).stdout
    assert dirty.strip() == ""


def test_no_tags_first_cut(tmp_path: Path) -> None:
    rc, out = _run(_repo(tmp_path, tag=None), "--dry-run")
    assert rc == 0 and "0.1.0" in out  # minor bump from 0.0.0
