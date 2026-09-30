"""Pins what `mobile-app/80-mobile.md` says the mobile-app scaffold emits to what it actually emits.

Until 2026-09-30 the pack told agents to theme through `react-native-unistyles`, validate forms with
`react-hook-form`, dodge the keyboard with the core `KeyboardAvoidingView` and load translations from
`src/locales/` — while the scaffold shipped Uniwind, `@tanstack/react-form`,
`react-native-keyboard-controller` and `src/translations/`. An agent following the pack fought the
code it was handed. This test emits a real mobile-app project and asserts each default the pack
names, so a scaffold change that moves one turns red here and the pack is re-read in the same change.

The cheap way to satisfy it without the outcome is to delete the pack sentence and the assertion
together; `test_pack_names_every_pinned_default` closes that by requiring the pack to still name
every package this file pins.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from fabrik.scaffold import create_project

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / ".windsurf" / "rules" / "mobile-app" / "80-mobile.md"
NAME = "mobile-pack-defaults-test"

PINNED = (
    "expo-router",
    "uniwind",
    "@tanstack/react-form",
    "react-native-keyboard-controller",
    "@shopify/flash-list",
    "react-native-mmkv",
    "react-native-nitro-modules",
    "expo-secure-store",
    "@hey-api/openapi-ts",
)

requires_fabrik_env = pytest.mark.skipif(
    not Path("/opt/fabrik").exists() or os.getenv("CI") == "true",
    reason="Requires full fabrik environment at /opt/fabrik",
)


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("mobile80")
    create_project(
        name=NAME,
        project_type="mobile-app",
        description="Defaults test for the mobile pack",
        base=base,
        generate_spec=False,
    )
    return base / NAME


def _deps(project: Path) -> dict[str, str]:
    data = json.loads((project / "package.json").read_text(encoding="utf-8"))
    return {**data.get("dependencies", {}), **data.get("devDependencies", {})}


@requires_fabrik_env
@pytest.mark.parametrize("package", PINNED)
def test_scaffold_ships_the_default_the_pack_names(project: Path, package: str) -> None:
    assert package in _deps(project), (
        f"the scaffold no longer ships {package}; re-read 80-mobile.md"
    )


@requires_fabrik_env
def test_scaffold_ships_no_react_navigation(project: Path) -> None:
    offenders = [p for p in _deps(project) if p.startswith("@react-navigation/")]
    assert not offenders, (
        f"the pack bans @react-navigation/* in app code; the scaffold ships {offenders}"
    )


@requires_fabrik_env
def test_scaffold_validates_generated_client(project: Path) -> None:
    config = (project / "openapi-ts.config.ts").read_text(encoding="utf-8")
    # the validator must sit INSIDE the @hey-api/sdk plugin object and be switched on
    plugin = re.search(r"name:\s*'@hey-api/sdk'[^}]*}", config)
    assert plugin, "no @hey-api/sdk plugin object in openapi-ts.config.ts"
    assert re.search(r"validator:\s*(true|'zod')", plugin.group(0)), (
        "the sdk plugin does not validate"
    )


@requires_fabrik_env
def test_scaffold_loads_translations_from_src_translations(project: Path) -> None:
    resources = (project / "src" / "lib" / "i18n" / "resources.ts").read_text(encoding="utf-8")
    assert "@/translations/" in resources
    assert (project / "src" / "translations" / "en.json").is_file()


@requires_fabrik_env
def test_scaffold_facts_the_pack_warns_about(project: Path) -> None:
    """Each assertion is a scaffold state the pack describes as a WORKAROUND; when the scaffold is
    fixed this turns red, and the pack's warning is removed in the same change."""
    rntl = _deps(project)["@testing-library/react-native"]
    assert re.match(r"[\^~]?13\.", rntl), (
        f"RNTL is now {rntl}: drop the pack's 'previous major' note"
    )
    sync = (project / "scripts" / "sync_rn_locales.py").read_text(encoding="utf-8")
    assert '"src" / "locales"' in sync, (
        "sync_rn_locales.py no longer targets src/locales: update § Localization"
    )
    app_config = (project / "app.config.ts").read_text(encoding="utf-8")
    assert "newArchEnabled: true" in app_config, (
        "the inert newArchEnabled key moved: update § Architecture"
    )
    assert "typedRoutes: true" in app_config
    translations = {f.name for f in (project / "src" / "translations").glob("*.json")}
    assert {"en.json", "ar.json"} <= translations and "tr.json" not in translations, (
        f"the scaffold's languages changed ({sorted(translations)}): update § Localization"
    )
    live = set(
        json.loads((project / "src" / "translations" / "en.json").read_text(encoding="utf-8"))
    )
    kit = set(json.loads((project / "static" / "i18n" / "en.json").read_text(encoding="utf-8")))
    assert not live & kit, (
        f"the two translation sets now share keys {sorted(live & kit)}: "
        "update § Localization's 'two unrelated sets'"
    )
    resources = (project / "src" / "lib" / "i18n" / "resources.ts").read_text(encoding="utf-8")
    assert "static/i18n" not in resources, (
        "the app now loads static/i18n: update § Localization's 'which the app does not load'"
    )


def test_roster_assigns_the_verification_mcps() -> None:
    roster = (ROOT / "docs" / "workstation" / "mcp-roster.md").read_text(encoding="utf-8")
    row = next((ln for ln in roster.splitlines() if ln.startswith("| `mobile-app` |")), "")
    assert "maestro" in row and "mobile-mcp" in row, (
        "the roster no longer assigns the MCPs the pack names"
    )


def test_pack_names_every_pinned_default() -> None:
    text = PACK.read_text(encoding="utf-8")
    for sentence in (
        "**The scaffold styles with Uniwind** (`uniwind`)",
        "Use `@tanstack/react-form` with Zod validators",
        "Handle the keyboard with `react-native-keyboard-controller`",
    ):
        assert sentence in text, f"80-mobile.md no longer prescribes: {sentence}"
    missing = [p for p in PINNED if f"`{p}`" not in text]
    assert not missing, (
        f"80-mobile.md no longer names {missing}; keep the pack and this test in step"
    )
