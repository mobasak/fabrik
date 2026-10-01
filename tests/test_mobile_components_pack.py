"""Pins `mobile-app/ocoron-mobile-design-system.md` to the template it builds on and the scaffold it names.

The pack is the mobile component spec every mobile-app project loads. Four things rot silently:

1. A slot the pack names that `core/design-system-template.md` does not define, or an accent or state
   colour written as TEXT where the template requires its `-text` slot (a bare `--color-danger` is a fill).
2. A scaffold file, package or default the pack names that the scaffold no longer ships — or a package the
   pack tells agents to ADD that the scaffold now ships, so the instruction is stale.
3. A rule ID the Tojlo mobile pack inherits that this pack no longer defines.
4. A brand font name outside the one Ocoron sentence: the patterns name font ROLES (D-051 — a house brand
   applies only where a project declares it).

The cheapest way to satisfy (2) without the outcome is to stop naming scaffold files at all; no test can see
an omission, so the review owns that.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from fabrik import config as fabrik_config
from fabrik.scaffold import create_project

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
PACK = RULES / "mobile-app" / "ocoron-mobile-design-system.md"
TEMPLATE = RULES / "core" / "design-system-template.md"
TOJLO = RULES / "mobile-app" / "tojlo-mobile-design-system.md"

# Packages the pack says the scaffold ships, and packages it tells agents to add.
SHIPPED = (
    "@shopify/flash-list",
    "expo-haptics",
    "react-native-gesture-handler",
    "@gorhom/bottom-sheet",
    "react-native-mmkv",
    "@tanstack/react-form",
    "react-native-keyboard-controller",
    "expo-secure-store",
)
TO_ADD = ("@react-native-community/datetimepicker", "@expo-google-fonts/space-grotesk")
STATES = ("accent", "success", "warning", "danger", "info", "ai")

requires_fabrik_env = pytest.mark.skipif(
    not (ROOT / "templates" / "mobile-app").is_dir(),
    reason="needs the hub's templates/mobile-app",
)


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("mobile-components")
    # fabrik.config binds FABRIK_ROOT at import, so setting it here would change nothing:
    # assert the scaffolder reads THIS tree's templates instead of grading another one
    assert fabrik_config.FABRIK_ROOT.resolve() == ROOT, (
        f"the scaffolder reads {fabrik_config.FABRIK_ROOT}, not {ROOT}: run with FABRIK_ROOT={ROOT}"
    )
    create_project(
        "mobilecomponents", "probe", base=base, project_type="mobile-app", generate_spec=False
    )
    return base / "mobilecomponents"


def _pack() -> str:
    return PACK.read_text(encoding="utf-8")


def _body() -> str:
    return _pack().split("---", 2)[2]


def test_every_slot_is_a_template_slot() -> None:
    defined = set(re.findall(r"`(--[a-z0-9-]+)`", TEMPLATE.read_text(encoding="utf-8")))
    defined |= {f"--color-{s}{suffix}" for s in STATES for suffix in ("", "-fg", "-text", "-muted")}
    named = set(re.findall(r"`(--[a-z0-9-]+)`", _body()))
    assert named, "the pack names no slots"
    assert named <= defined, f"slots the template does not define: {sorted(named - defined)}"


def test_colours_used_as_text_take_their_text_slot() -> None:
    # A bare accent/state slot must BE the fill it names: written "`--color-x` fill" or as a pill's colour,
    # "pill (`--color-x`)". A "fill" elsewhere on the line ("as text, never a fill") does not count.
    bare = re.compile(r"`--color-(?:" + "|".join(STATES) + r")`")
    for line in _body().splitlines():
        for m in bare.finditer(line):
            assert re.match(r" fill\b", line[m.end() :]) or line[: m.start()].endswith("pill ("), (
                f"a bare accent/state colour is a FILL; as text or an icon on a surface use its -text slot: {line!r}"
            )
    assert not re.search(r"#[0-9A-Fa-f]{3,8}\b|rgba?\(", _body()), "raw colour values in the pack"
    assert not re.search(r"\bwhite (?:icon|text|label)", _body(), re.I), (
        "a hard-coded white instead of a -fg slot"
    )


@requires_fabrik_env
def test_scaffold_names_are_what_the_scaffold_ships(project: Path) -> None:
    body = _body()
    paths = set(re.findall(r"`(src/[^`]+\.tsx?)`", body))
    assert paths, "the pack names no scaffold files"
    missing = sorted(p for p in paths if not (project / p).is_file())
    assert not missing, f"the pack names scaffold files that do not exist: {missing}"
    pkg = json.loads((project / "package.json").read_text(encoding="utf-8"))
    deps = set(pkg.get("dependencies", {})) | set(pkg.get("devDependencies", {}))
    for name in SHIPPED:
        assert f"`{name}`" in body or f"`{name}/" in body, f"the pack no longer names {name}"
        assert name in deps, f"the scaffold no longer ships {name}: update the pack"
    for name in TO_ADD:
        assert re.search(rf"(?:npx expo install |add `){re.escape(name)}", body), (
            f"the pack no longer tells agents to add {name}"
        )
        assert name not in deps, f"the scaffold now ships {name}: drop the add-step from the pack"
    modal = (project / "src" / "components" / "ui" / "modal.tsx").read_text(encoding="utf-8")
    assert re.search(r"snapPoints:\s*_snapPoints\s*=\s*\['60%'\]", modal), (
        "the Modal wrapper's default snap point changed: update § Bottom Sheet"
    )
    assert "60% snap point" in body
    assert "enableDynamicSizing={false}" in modal and "rgba(0, 0, 0, 0.4)" in modal, (
        "the Modal wrapper no longer forces dynamic sizing off or draws a 0.4 scrim: update § Bottom Sheet"
    )
    assert "forces `enableDynamicSizing={false}`" in body and "scrim at 0.4" in body
    listing = (project / "src" / "components" / "ui" / "list.tsx").read_text(encoding="utf-8")
    assert "ActivityIndicator" in listing, (
        "EmptyList no longer shows a spinner: drop LI5's replace-it note"
    )
    fonts = (project / "app.config.ts").read_text(encoding="utf-8")
    assert "Inter_500Medium" in fonts and "SpaceGrotesk" not in fonts, (
        "the scaffold's embedded fonts changed: update the Ocoron font sentence"
    )


def test_ids_the_tojlo_pack_inherits_are_defined() -> None:
    tojlo = TOJLO.read_text(encoding="utf-8")
    wanted: set[str] = set()
    for prefix, lo, hi in re.findall(r"\b([A-Z]{2})(\d)-\1(\d)\b", tojlo):
        wanted |= {f"{prefix}{n}" for n in range(int(lo), int(hi) + 1)}
    assert len(wanted) >= 30, f"parsed only {len(wanted)} inherited ids from the Tojlo pack"
    body = _body()
    for rule_id in sorted(wanted):
        assert f"**{rule_id}:**" in body, (
            f"{rule_id} is inherited by the Tojlo pack but not defined here"
        )
        assert f"\n| {rule_id} |" in body, f"{rule_id} is missing from the Rules Summary"


def test_brand_fonts_only_in_the_ocoron_sentence() -> None:
    lines = [ln for ln in _body().splitlines() if re.search(r"\bInter\b|Space Grotesk", ln)]
    assert len(lines) == 1 and "Ocoron-declared" in lines[0], (
        f"brand font names outside the Ocoron sentence — name the role (heading font, body font): {lines}"
    )
    assert "Traycer" not in _pack()


_CITE = re.compile(r"`(?:[a-z-]+/)?([a-z0-9-]+\.md)`\s*§ ([A-Z][^.;:,()`—]*)")


def test_every_cited_section_exists() -> None:
    found, missing = 0, []
    for m in _CITE.finditer(_body()):
        targets = list(RULES.rglob(m.group(1)))
        assert len(targets) == 1, (
            f"{m.group(1)} resolves to {len(targets)} packs: make the cite a path"
        )
        heads = [
            ln.lstrip("#").strip()
            for ln in targets[0].read_text(encoding="utf-8").splitlines()
            if ln.startswith("#")
        ]
        cited = m.group(2).strip()
        found += 1

        # one must be a prefix of the other, ending at a word boundary ("Sound" does not match "Sounds and
        # Haptics"; "Save Behavior" matches "Save Behavior — draft persistence …")
        def _prefix(a: str, b: str) -> bool:
            return bool(re.match(re.escape(a) + r"(?![A-Za-z])", b))

        if not any(h and (_prefix(h, cited) or _prefix(cited, h)) for h in heads):
            missing.append(f"{m.group(1)} § {cited}")
    assert found >= 5, f"parsed only {found} cites"
    assert not missing, f"cited sections that do not exist: {missing}"
