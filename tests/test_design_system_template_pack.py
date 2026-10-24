"""Pins `core/design-system-template.md`'s CSS-first Tailwind guidance (W-dab6a341, mail 01M5Q7EJMSW4790Z8J1G6CNN2H).

The pack is glob-activated in every GUI repo, so a stale line in it is copied straight into code. Five things it
states can go false with no other gate turning red:

1. Its globs reach the files the fleet's sites are written in — `.astro` components and the CSS-first theme
   stylesheets, whose names vary (`global.css`, `theme.css`, `onepage-theme.css`, `site-base.css`, …), as well
   as the React/shadcn surfaces it always covered.
2. The § Tailwind (CSS-first) usage section exists once, between § Default tokens (CSS) and § Rules for Coding
   Agents, and § Mapping to the scaffold's variables points to it.
3. The text-colour slots (`--text-primary`, `--text-body`, `--text-muted`) sit inside Tailwind's FONT-SIZE
   namespace: declared in `@theme` they compile to `.text-primary { font-size: var(--text-primary) }`. No pack
   may tell an agent to declare them there, and the template must say so.
4. No pack writes the font token in the JS-config spelling `--font-family-*`; the CSS-first namespace is `--font-*`.
5. The section cites a source for its claims and carries no version number (the corpus rule: a version in a
   pack goes stale — `docs/reference/rules-currency-pass.md` § Version literals).

The cheapest way past (3) is to drop the sentence that names `@theme` beside the slots while keeping a block
that still puts them there; the check reads every pack's `@theme { … }` CSS blocks too. The cheapest way past
(1) is a glob that matches only the example paths below; the examples are the measured basenames.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pack_matches_path = _load("rules_match").pack_matches_path
_parse_frontmatter = _load("select_rules")._parse_frontmatter
RULES = ROOT / ".windsurf" / "rules"
TEMPLATE = RULES / "core" / "design-system-template.md"
SECTION = "## Tailwind (CSS-first) usage"
TEXT_SLOTS = ("--text-primary", "--text-body", "--text-muted")


def _template() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _section() -> str:
    text = _template()
    start = text.index(SECTION)
    end = text.index("\n## ", start + len(SECTION))
    return text[start:end]


def _globs() -> list[str]:
    globs, _ = _parse_frontmatter(_template())
    return globs


@pytest.mark.parametrize(
    "path",
    [
        "src/components/Hero.astro",
        "packages/sections/src/Gallery.astro",
        "src/styles/onepage-theme.css",
        "src/styles/site-base.css",
        "packages/brand/theme.css",
        "src/styles/tailwind.css",
        "src/global.css",
        "app/globals.css",
        "src/css/custom.css",
        "components/ui/button.tsx",
        "src/App.jsx",
        "tailwind.config.ts",
        "docs/design-system.md",
    ],
)
def test_globs_match_astro_and_css_first_stylesheets(path: str) -> None:
    assert any(pack_matches_path(path, g, empty_matches_all=False) for g in _globs()), (path, _globs())


def test_globs_stay_off_non_gui_files() -> None:
    for path in ("app/main.py", "README.md", "compose.yaml", "src/index.ts"):
        assert not any(pack_matches_path(path, g, empty_matches_all=False) for g in _globs()), path


def test_tailwind_section_is_placed_once() -> None:
    text = _template()
    assert text.count(SECTION) == 1
    pos = text.index(SECTION)
    assert text.index("## Default tokens (CSS)") < pos < text.index("## Rules for Coding Agents")
    mapping = text[text.index("### Mapping to the scaffold's variables") : text.index("## Contrast contract")]
    assert "§ Tailwind (CSS-first) usage" in mapping


def _theme_blocks(text: str) -> list[str]:
    return re.findall(r"@theme(?:\s+inline)?\s*\{([^}]*)\}", text)


def test_text_colour_slots_never_declared_in_theme() -> None:
    section = _section()
    for slot in TEXT_SLOTS:
        assert slot in section, slot
    assert "font-size" in section and "@theme inline" in section
    assert "--color-text-primary: var(--text-primary)" in section
    for pack in sorted(RULES.rglob("*.md")):
        text = pack.read_text(encoding="utf-8")
        for block in _theme_blocks(text):
            for slot in TEXT_SLOTS:
                assert not re.search(re.escape(slot) + r"\s*:", block), (pack.name, slot, block)
        # a prose instruction that sends the colour slots into @theme
        for para in text.split("\n\n"):
            if "declare these in `@theme`" in para:
                pytest.fail(f"{pack.name}: '{para[:120]}…' sends every slot, the text-colour ones included, into @theme")


def test_no_js_config_font_family_token() -> None:
    hits = [p.name for p in RULES.rglob("*.md") if "--font-family-" in p.read_text(encoding="utf-8")]
    assert not hits, hits


def test_section_cites_sources_and_carries_no_version() -> None:
    section = _section()
    for host in ("tailwindcss.com/docs/", "docs.astro.build/", "github.com/tailwindlabs/prettier-plugin-tailwindcss"):
        assert host in section, host
    found = re.findall(
        r"\bv\d+(?:\.\d+)?\b"  # v4, v3.4
        r"|\b\d+\.\d+(?:\.\d+)?\b"  # 4.3.3, 16.4
        r"|\b(?:Tailwind|Node(?:\.js)?|Safari|Chrome|Firefox|Astro|Prettier)\s+\d+"  # Tailwind 4, Chrome 111
        r"|[≥>]=?\s?\d+",
        section,
    )
    assert not found, f"version literals in the section: {found}"
