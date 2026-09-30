"""Pins `saas/87-abuse-detection.md`'s activation to the files where a saas-skeleton's signup lives.

Until 2026-09-30 the pack's globs were `**/register/**` and `**/signup/**`. An emitted saas-skeleton has
neither directory: its signup is the vendored IdP router (`server/src/fastapi_user_auth/router.py`),
mounted from `server/src/<pkg>/auth.py`. So the pack never loaded on the code it governs, and the five
fleet repos it did load in matched by accident (a UI page folder, a stray worktree, a vendored UI kit).

This test emits a real saas-skeleton and asks the same glob question review time asks
(`rules_match.packs_for_paths`), so it fails if the scaffold moves its auth wiring or the globs drift.
The cheap way to satisfy it without the outcome is a catch-all glob (`**/*.py`); `test_pack_stays_scoped`
closes that by requiring the pack NOT to fire on the emitted app's unrelated modules.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from fabrik.scaffold import create_project

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import rules_match  # noqa: E402

PACK = "saas/87-abuse-detection.md"
NAME = "abuse-activation-test"
PKG = "abuse_activation_test"

requires_fabrik_env = pytest.mark.skipif(
    not Path("/opt/fabrik").exists() or os.getenv("CI") == "true",
    reason="Requires full fabrik environment at /opt/fabrik",
)


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("saas87")
    create_project(
        name=NAME,
        project_type="saas-skeleton",
        description="Activation test for the abuse-detection pack",
        base=base,
        generate_spec=False,
    )
    return base / NAME


def _rel(project: Path, p: Path) -> str:
    return p.relative_to(project).as_posix()


@requires_fabrik_env
@pytest.mark.parametrize(
    "tail",
    [f"server/src/{PKG}/auth.py", "server/src/fastapi_user_auth/router.py"],
)
def test_pack_fires_on_the_signup_wiring(project: Path, tail: str) -> None:
    path = project / tail
    assert path.is_file(), f"the scaffold no longer emits {tail} — re-derive the pack's globs"
    assert PACK in rules_match.packs_for_paths([_rel(project, path)], ROOT)


@requires_fabrik_env
@pytest.mark.parametrize("name", ["main.py", "tenant.py", "worker.py", "metrics.py"])
def test_pack_stays_scoped(project: Path, name: str) -> None:
    path = project / "server" / "src" / PKG / name
    assert path.is_file(), f"the scaffold no longer emits {name}"
    assert PACK not in rules_match.packs_for_paths([_rel(project, path)], ROOT)
