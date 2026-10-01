"""Pins `mobile-app/tojlo-mobile-design-system.md` to D-051, its sibling packs and the scaffold it names.

Tojlo is a house identity: its mobile patterns apply only where a project declares it. The pack once loaded by
file glob in every mobile repo — none of them Tojlo — so these facts are pinned:

1. It loads by description only (no `globs:`), and the description names the declaration.
2. Every slot it names is a template slot, and a bare accent/state colour is only ever a FILL.
3. No type below the mobile floor of 13.
4. Every module it names is in `core/tojlo-design-system.md` § Module Naming.
5. The rule IDs it inherits exist in the components pack, and its own IDs match its summary table.
6. Every `<pack>.md § <heading>` it cites exists; every scaffold file it names exists, and every package it says
   to add is still absent from the scaffold.

The cheapest way to satisfy (4)-(6) without the outcome is to stop naming modules, IDs or files; no test sees an
omission, so the review owns that.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from fabrik.scaffold import create_project

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
PACK = RULES / "mobile-app" / "tojlo-mobile-design-system.md"
COMPONENTS = RULES / "mobile-app" / "ocoron-mobile-design-system.md"
TEMPLATE = RULES / "core" / "design-system-template.md"
TOJLO = RULES / "core" / "tojlo-design-system.md"
STATES = ("accent", "success", "warning", "danger", "info", "ai")
TO_ADD = ("react-native-webview", "expo-notifications", "lucide-react-native")

requires_fabrik_env = pytest.mark.skipif(
    not (ROOT / "templates" / "mobile-app").is_dir(),
    reason="needs the hub's templates/mobile-app",
)


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("tojlo-mobile")
    os.environ.setdefault("FABRIK_ROOT", str(ROOT))
    create_project(
        "tojlomobile", "probe", base=base, project_type="mobile-app", generate_spec=False
    )
    return base / "tojlomobile"


def _parts() -> tuple[str, str]:
    _, front, body = PACK.read_text(encoding="utf-8").split("---", 2)
    return front, body


def test_loads_by_description_only() -> None:
    front, _ = _parts()
    assert not re.search(r"^(?:globs|activation|trigger):", front, re.M), (
        "a house-identity pack must not load by file glob (D-051)"
    )
    description = re.search(r"^description:(.+)$", front, re.M)
    assert description and "Tojlo" in description.group(1) and "declares" in description.group(1)


def test_slots_are_template_slots_and_bare_colours_are_fills() -> None:
    _, body = _parts()
    defined = set(re.findall(r"`(--[a-z0-9-]+)`", TEMPLATE.read_text(encoding="utf-8")))
    defined |= {f"--color-{s}{x}" for s in STATES for x in ("", "-fg", "-text", "-muted")}
    retired = {"--color-purple", "--color-secondary"}
    named = set(re.findall(r"`(--[a-z0-9-]+)`", body))
    assert named, "the pack names no slots"
    assert named - retired <= defined, (
        f"slots the template does not define: {sorted(named - retired - defined)}"
    )
    for line in body.splitlines():
        if retired & set(re.findall(r"`(--[a-z0-9-]+)`", line)):
            assert "retired" in line, f"a retired slot name used as a slot: {line!r}"
    bare = re.compile(r"`--color-(?:" + "|".join(STATES) + r")`")
    for line in body.splitlines():
        for m in bare.finditer(line):
            before, after = line[: m.start()], line[m.end() :]
            ok = (
                re.match(r" fill\b", after)
                or before.endswith("**Fill:** ")
                or re.search(r"(?:filled with the layer colour \(|slot names: )[^()]*$", before)
            )
            assert ok, (
                f"a bare accent/state colour is a FILL; as text or an icon use its -text slot: {line!r}"
            )


def test_no_type_below_the_mobile_floor() -> None:
    _, body = _parts()
    # "body font 500, 15" and "body font 500, uppercase, 13" both carry a size
    sizes = [int(n) for n in re.findall(r"\b\w+ font \d{3}(?:, uppercase)?, (\d+)\b", body)]
    assert len(sizes) >= 10, f"parsed only {len(sizes)} type sizes"
    roles = set(re.findall(r"\b(\w+) font \d{3}", body))
    assert roles <= {"body", "mono", "heading"}, (
        f"font roles the template does not define: {sorted(roles)}"
    )
    assert min(sizes) >= 13, f"type below the 13 floor: {sorted({n for n in sizes if n < 13})}"


def test_every_module_named_is_canonical() -> None:
    _, body = _parts()
    canonical = set(re.findall(r"\*\*Tojlo ([A-Z]+)\*\*", TOJLO.read_text(encoding="utf-8")))
    assert len(canonical) >= 10, f"parsed only {len(canonical)} canonical modules"
    named = set(re.findall(r"^\| (?:\*\*)?([A-Z]{2,})(?:\*\*)? \|", body, re.M)) - {"ID"}
    assert named, "the pack's module tables name no modules"
    assert named <= canonical, (
        f"modules not in core Tojlo's canonical list: {sorted(named - canonical)}"
    )


def test_rule_ids_inherited_and_own() -> None:
    _, body = _parts()
    components = COMPONENTS.read_text(encoding="utf-8")
    line = next(ln for ln in body.splitlines() if "mobile component patterns (" in ln)
    inherited = {
        f"{p}{n}"
        for p, lo, hi in re.findall(r"\b([A-Z]{2})(\d)-\1(\d)\b", line)
        for n in range(int(lo), int(hi) + 1)
    }
    assert len(inherited) == 37, (
        f"the inheritance line names {len(inherited)} ids, the components pack has 37"
    )
    missing = sorted(i for i in inherited if f"**{i}:**" not in components)
    assert not missing, f"inherited ids the components pack does not define: {missing}"
    own = set(re.findall(r"^- \*\*([A-Z]{2,3}\d):\*\*", body, re.M))
    summary = set(re.findall(r"^\| ([A-Z]{2,3}\d) \|", body, re.M))
    assert own and own == summary, f"rules vs summary table differ: {sorted(own ^ summary)}"


_CITE = re.compile(r"`(?:[a-z-]+/)?([a-z0-9-]+\.md)`\s*§ ([A-Z][^.;:,()`—]*)")


def test_every_cited_section_exists() -> None:
    _, body = _parts()
    found, missing = 0, []
    for m in _CITE.finditer(body):
        targets = list(RULES.rglob(m.group(1)))
        assert len(targets) == 1, f"{m.group(1)} resolves to {len(targets)} packs"
        # a heading may carry a number ("6. Swipeable Onboarding") or a parenthetical ("… (Tojlo-Specific Addition)")
        heads = [
            re.sub(r"\s*\(.*\)$", "", re.sub(r"^\d+\.\s+", "", ln.lstrip("#").strip()))
            for ln in targets[0].read_text(encoding="utf-8").splitlines()
            if ln.startswith("#")
        ]
        cited = m.group(2).strip()
        found += 1
        if not any(h.startswith(cited) or cited.startswith(h) for h in heads):
            missing.append(f"{m.group(1)} § {cited}")
    assert found >= 6, f"parsed only {found} cites"
    assert not missing, f"cited sections that do not exist: {missing}"


@requires_fabrik_env
def test_scaffold_names_are_what_the_scaffold_ships(project: Path) -> None:
    _, body = _parts()
    paths = set(re.findall(r"`(src/[^`]+\.tsx?)`", body))
    assert paths, "the pack names no scaffold files"
    missing = sorted(p for p in paths if not (project / p).is_file())
    assert not missing, f"the pack names scaffold files that do not exist: {missing}"
    pkg = json.loads((project / "package.json").read_text(encoding="utf-8"))
    deps = set(pkg.get("dependencies", {})) | set(pkg.get("devDependencies", {}))
    for name in TO_ADD:
        assert re.search(
            rf"npx expo install {re.escape(name)}|`{re.escape(name)}`, not in the scaffold", body
        ), f"the pack no longer says to add {name}"
        assert name not in deps, f"the scaffold now ships {name}: drop the add-step from the pack"
