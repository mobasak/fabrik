"""chrome-extension scaffold emits a WXT (not @crxjs) extension lane.

Structure assertions (fast, no pnpm/build). The end-to-end build gate
(`pnpm install` → `wxt build` → tsc → size-limit → eslint, all exit 0) is the
integration verification run at plan-execution time — see the plan's Evidence.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from fabrik.scaffold import I18N_ENABLED_TYPES, TYPE_REQUIRED_FILES, create_project

FABRIK_ROOT = Path("/opt/fabrik")
# Portability guard (matches tests/test_scaffold.py): these tests scaffold against the
# real templates tree — skip cleanly where it isn't present (e.g. CI) rather than error.
pytestmark = pytest.mark.skipif(
    not FABRIK_ROOT.exists() or os.getenv("CI") == "true",
    reason="Requires the full fabrik environment at /opt/fabrik (templates dir)",
)


@pytest.fixture
def ext(tmp_path: Path) -> Path:
    """Scaffold a chrome-extension and return its extension/ dir."""
    create_project(
        "cxwxttest",
        "WXT chrome-ext test",
        base=tmp_path,
        project_type="chrome-extension",
        generate_spec=False,
    )
    return tmp_path / "cxwxttest" / "extension"


def test_emits_wxt_config_not_vite_or_manifest(ext: Path) -> None:
    """WXT owns the build + auto-generates the manifest — no vite.config/manifest.json."""
    assert (ext / "wxt.config.ts").exists()
    assert not (ext / "vite.config.ts").exists()
    assert not (ext / "manifest.json").exists()  # WXT auto-generates it


def test_wxt_config_wires_preact_compat_and_i18n(ext: Path) -> None:
    """@preact/preset-vite (react→preact/compat) + @wxt-dev/i18n/module."""
    cfg = (ext / "wxt.config.ts").read_text()
    assert "@preact/preset-vite" in cfg
    assert "preact()" in cfg
    assert "@wxt-dev/i18n/module" in cfg  # /module subpath, not the bare package


def test_file_based_entrypoints(ext: Path) -> None:
    """WXT file-based entrypoints under src/."""
    for p in (
        "src/entrypoints/background.ts",
        "src/entrypoints/content.ts",
        "src/entrypoints/popup/index.html",
        "src/entrypoints/popup/main.tsx",
        "src/entrypoints/options/main.tsx",
        "src/locales/en.json",
    ):
        assert (ext / p).exists(), p


def test_package_json_is_wxt_not_crxjs(ext: Path) -> None:
    """WXT dep set; no @crxjs; the load-bearing webext-permission-toggle pin is v6 (v7 doesn't exist)."""
    import json

    pkg = json.loads((ext / "package.json").read_text())
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    assert "wxt" in deps
    assert "preact" in deps
    assert "@preact/preset-vite" in deps
    assert not any("crxjs" in d for d in deps), "must not depend on @crxjs"
    assert deps["webext-permission-toggle"].startswith("^6"), "v7 does not exist"


def test_pnpm_workspace_allowbuilds_not_onlybuilt(ext: Path) -> None:
    """pnpm 11 uses allowBuilds (onlyBuiltDependencies was removed) so install exits 0."""
    ws = (ext / "pnpm-workspace.yaml").read_text()
    assert "allowBuilds:" in ws
    assert "esbuild: true" in ws
    assert "onlyBuiltDependencies" not in ws


def test_type_required_files_flipped_to_wxt() -> None:
    """The required-files contract no longer lists manifest.json/vite.config.ts."""
    req = TYPE_REQUIRED_FILES["chrome-extension"]
    assert "extension/wxt.config.ts" in req
    assert "extension/manifest.json" not in req
    assert "extension/vite.config.ts" not in req


def test_i18n_owned_by_wxt_dev_i18n() -> None:
    """chrome-extension dropped the legacy chrome_messages.py strategy (@wxt-dev/i18n owns it)."""
    assert "chrome-extension" not in I18N_ENABLED_TYPES


def test_tailwind_v4_wired(ext: Path) -> None:
    """Tailwind v4 (@tailwindcss/vite) is wired into the build (plan Phase A wxt.config + deps)."""
    import json

    pkg = json.loads((ext / "package.json").read_text())
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    assert "@tailwindcss/vite" in deps
    assert "tailwindcss" in deps
    assert "tailwindcss()" in (ext / "wxt.config.ts").read_text()
    assert (ext / "src" / "global.css").read_text().strip() == '@import "tailwindcss";'


def test_wxt_config_declares_mv3_permissions_and_icons(ext: Path) -> None:
    """The manifest permissions + explicit icons are declared (WXT auto-discovery
    won't match our icon16.png names, so they must be wired or Chrome shows no icon)."""
    cfg = (ext / "wxt.config.ts").read_text()
    assert "permissions: ['storage', 'activeTab']" in cfg
    assert "icons: {" in cfg
    assert "/icon16.png" in cfg


@pytest.mark.skipif(
    shutil.which("pnpm") is None or shutil.which("node") is None,
    reason="requires the node/pnpm toolchain (the build integration gate)",
)
def test_wxt_scaffold_builds_and_manifest_has_permissions(tmp_path: Path) -> None:
    """Behavior Contract (a): a fresh scaffold `pnpm install` + `wxt build` exits 0 and
    the generated manifest carries the declared MV3 permissions. This is the real proof
    the rewrite builds — slow (installs deps), gated on the toolchain being present."""
    import json
    import subprocess

    create_project(
        "cxbuildtest",
        "WXT build test",
        base=tmp_path,
        project_type="chrome-extension",
        generate_spec=False,
    )
    ext = tmp_path / "cxbuildtest" / "extension"
    inst = subprocess.run(
        ["pnpm", "install"], cwd=ext, capture_output=True, text=True, timeout=600
    )
    assert inst.returncode == 0, f"pnpm install failed:\n{inst.stderr[-2000:]}"
    build = subprocess.run(
        ["npx", "wxt", "build"], cwd=ext, capture_output=True, text=True, timeout=400
    )
    assert build.returncode == 0, f"wxt build failed:\n{build.stderr[-2000:]}"
    manifest = json.loads((ext / ".output" / "chrome-mv3" / "manifest.json").read_text())
    assert manifest["permissions"] == ["storage", "activeTab"]
    assert manifest["default_locale"] == "en"
    # Icons wired into the built manifest (else Chrome shows the gray puzzle default).
    assert manifest["icons"] == {"16": "/icon16.png", "48": "/icon48.png", "128": "/icon128.png"}
