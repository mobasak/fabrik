"""chrome-extension scaffold emits a WXT (not @crxjs) extension lane.

Structure assertions (fast, no pnpm/build). The end-to-end build gate
(`pnpm install` → `wxt build` → tsc → size-limit → eslint, all exit 0) is the
integration verification run at plan-execution time — see the plan's Evidence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fabrik.scaffold import I18N_ENABLED_TYPES, TYPE_REQUIRED_FILES, create_project


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
