"""Pins `core/design-system-template.md`'s CSS-first Tailwind guidance (W-dab6a341, mail 01M5Q7EJMSW4790Z8J1G6CNN2H).

The pack is glob-activated in every GUI repo, so a stale line in it is copied straight into code. Five things it
states can go false with no other gate turning red:

1. Its globs reach the files the fleet's sites are written in — `.astro` components and the CSS-first theme
   stylesheets, whose names vary (`global.css`, `theme.css`, `onepage-theme.css`, `site-base.css`, …), as well
   as the React/shadcn surfaces it always covered — and stay off non-GUI CSS (coverage reports, API docs,
   Sphinx builds, vendored kits), which a bare `**/*.css` would activate the 1,600-line pack on.
2. The § Tailwind (CSS-first) usage section exists once, between § Default tokens (CSS) and § Rules for Coding
   Agents, and § Mapping to the scaffold's variables points to it.
3. The text-colour slots (`--text-primary`, `--text-body`, `--text-muted`) sit inside Tailwind's FONT-SIZE
   namespace: declared in `@theme` they compile to `.text-primary { font-size: var(--text-primary) }`. No pack
   may tell an agent to declare them there, and the template must say so.
4. No pack writes the font token in the JS-config spelling `--font-family-*`; the CSS-first namespace is `--font-*`.
5. The section cites a source for its claims and carries no version number (the corpus rule: a version in a
   pack goes stale — `docs/reference/rules-currency-pass.md` § Version literals).

The cheapest way past (3) is to drop the sentence that names `@theme` beside the slots while keeping a block
that still puts them there; the check reads every pack's `@theme [modifiers] { … }` CSS block too. Its prose half
is BOUNDED: it catches the "declare these/them/the slots in `@theme`" family in any wrap or case, skips a negated
sentence, and does not try other verbs ("put every slot in `@theme`") — a sentence-level verb list fired on two
legitimate sentences in the 57 live packs, so that class stays the review's. The cheapest way past
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
CITED_PAGES = (
    "https://tailwindcss.com/docs/upgrade-guide",
    "https://tailwindcss.com/docs/theme",
    "https://tailwindcss.com/docs/functions-and-directives",
    "https://tailwindcss.com/docs/dark-mode",
    "https://tailwindcss.com/docs/detecting-classes-in-source-files",
    "https://tailwindcss.com/docs/styling-with-utility-classes",
    "https://docs.astro.build/en/reference/directives-reference/",
    "https://tailwindcss.com/docs/adding-custom-styles",
    "https://tailwindcss.com/docs/responsive-design",
    "https://tailwindcss.com/docs/grid-template-columns",
    "https://github.com/tailwindlabs/prettier-plugin-tailwindcss",
)


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


@pytest.mark.parametrize(
    "path",
    [
        "app/main.py",
        "README.md",
        "src/index.ts",
        "htmlcov/style.css",
        "static/swagger-ui.css",
        "docs/assets/extra.css",
        "_build/html/_static/basic.css",
        "tests/fixtures/sample.css",
        "public/vendor/bootstrap.min.css",
        "scripts/sysadmin/dashboard_ui/static/app.css",
        "docs/styles/api.css",
        "site/styles/mkdocs.css",
        "htmlcov/styles/a.css",
        "docs/_static/pygments-theme.css",
    ],
)
def test_globs_stay_off_non_gui_files(path: str) -> None:
    assert not any(pack_matches_path(path, g, empty_matches_all=False) for g in _globs()), path


def test_tailwind_section_is_placed_once() -> None:
    text = _template()
    assert text.count(SECTION) == 1
    pos = text.index(SECTION)
    assert text.index("## Default tokens (CSS)") < pos < text.index("## Rules for Coding Agents")
    mapping = text[text.index("### Mapping to the scaffold's variables") : text.index("## Contrast contract")]
    assert "§ Tailwind (CSS-first) usage" in mapping


def _theme_blocks(text: str) -> list[str]:
    """Every `@theme [modifiers] { … }` body, any case, with nested braces (a `@keyframes` inside) counted."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    bodies = []
    for m in re.finditer(r"@theme\b[\w \t-]*\{", text, re.IGNORECASE):
        depth, i = 1, m.end()
        while i < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        bodies.append(text[m.end() : i])
    return bodies


# a prose instruction that sends every slot, the text-colour ones included, into @theme — any wrap, case or verb form
_SEND_ALL_TO_THEME = re.compile(
    r"\bdeclar\w*\s+(?:these|them|the\s+slots|every\s+slot|all\s+(?:the\s+)?slots)\b[^.]{0,60}?`@theme`(?!\s+inline)",
    re.IGNORECASE | re.DOTALL,
)
_NEGATION = re.compile(r"\b(?:never|not|don't|do not)\b", re.IGNORECASE)


def test_text_colour_slots_never_declared_in_theme() -> None:
    section = _section()
    for slot in TEXT_SLOTS:
        assert slot in section, slot
    assert "COLOUR slots inside the FONT-SIZE namespace" in section  # the warning itself, not words elsewhere
    assert "they compile to `.text-primary { font-size: var(--text-primary) }`" in section  # and what goes wrong
    assert "--color-text-primary: var(--text-primary)" in section
    for pack in sorted(RULES.rglob("*.md")):
        text = pack.read_text(encoding="utf-8")
        for block in _theme_blocks(text):
            for slot in TEXT_SLOTS:
                assert not re.search(re.escape(slot) + r"\s*:", block), (pack.name, slot, block)
        for sentence in re.split(r"(?<=[.!?])\s+|\n\s*\n", text):
            flat = " ".join(sentence.split())
            if _SEND_ALL_TO_THEME.search(flat) and not _NEGATION.search(flat):
                pytest.fail(f"{pack.name}: {flat[:160]}")


def test_no_js_config_font_family_token() -> None:
    # a DEFINITION of the JS-config key; the section's own warning names it as `--font-family-*`
    hits = [p.name for p in RULES.rglob("*.md") if re.search(r"--font-family(?:-[\w-]+)?\s*:", p.read_text(encoding="utf-8"))]
    assert not hits, hits


def test_section_cites_sources_and_carries_no_version() -> None:
    section = _section()
    cited = {u.rstrip(".,;:`") for u in re.findall(r"https://[^\s)]+", section)}
    for page in CITED_PAGES:
        assert page in cited, page
    found = re.findall(
        r"\b[vV]\d+(?:\.\d+)?\b"  # v4, V4, v3.4
        r"|\b\d+\.(?:\d+|x)(?:\.\d+)?\b"  # 4.3.3, 16.4, 4.x
        r"|\b(?:Tailwind(?:\s?CSS)?|tailwindcss|Node(?:\.js)?|Safari|Chrom(?:e|ium)|Firefox|Edge|iOS|macOS|Android|Astro|Vite|React|Svelte|Next\.js|Prettier|version)[\s/]+\d+"
        r"|\bTW\d|\bES\d{4}\b|@\d|\d+\+"  # TW4, ES2022, pkg@4, 16+
        r"|[≥>]=?\s?\d+",
        section,
    )
    assert not found, f"version literals in the section: {found}"
