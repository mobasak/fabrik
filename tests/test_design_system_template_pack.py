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
is BOUNDED: it catches the "declare these/them/the slots in `@theme`" family in any wrap or case, skips a sentence
negated BEFORE the verb (sentences split at their ends, not after e.g./i.e.), and does not try other verbs ("put every slot in `@theme`") — a sentence-level verb list fired on two
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
    """Every `@theme [modifiers] { … }` body, any case, with nested braces (a `@keyframes` inside) counted; comments are stripped
    inside the body only, so glob prose like `**/*.tsx … **/*.css` outside it cannot pair into a fake comment."""
    bodies = []
    for m in re.finditer(r"@theme\b[\w\s-]*\{", text, re.IGNORECASE):
        depth, i = 1, m.end()
        while i < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        bodies.append(re.sub(r"/\*.*?\*/", "", text[m.end() : i], flags=re.DOTALL))
    return bodies


# a prose instruction that sends every slot, the text-colour ones included, into @theme — any wrap, case or verb form
_SEND_ALL_TO_THEME = re.compile(
    r"\bdeclar\w*\s+(?:these|them|the\s+slots|every\s+slot|all\s+(?:the\s+)?slots)\b(?:e\.g\.|i\.e\.|[^.]){0,60}?`@theme`(?!\s+inline)",
    re.IGNORECASE | re.DOTALL,
)
_NEGATION = re.compile(r"\b(?:never|not|don't|do not)\b", re.IGNORECASE)


def _send_all_sentences(text: str) -> list[str]:
    """Sentences that send every slot into `@theme` and are not negated."""
    out = []
    for sentence in re.split(r"(?<=[.!?])(?<!e\.g\.)(?<!i\.e\.)\s+|\n\s*\n", text):
        flat = " ".join(sentence.split())
        m = _SEND_ALL_TO_THEME.search(flat)
        if m and not _NEGATION.search(flat[: m.start()]):
            out.append(flat)
    return out


def test_theme_block_hidden_between_glob_prose_is_still_read() -> None:
    text = "globs: **/*.tsx\n@theme {\n  --text-primary: red;\n}\nmore: **/*.css"
    assert any("--text-primary" in b for b in _theme_blocks(text))


def test_negation_after_the_verb_does_not_excuse_the_sentence() -> None:
    assert _send_all_sentences("Declare these in `@theme` (not `@theme inline`).")
    assert not _send_all_sentences("Never declare these in `@theme`.")


def test_sentence_split_ignores_eg_and_ie() -> None:
    assert _send_all_sentences("Declare these (e.g. the colours) in `@theme`.")
    assert _send_all_sentences("Declare these (i.e. all of them) in `@theme`.")


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
        for flat in _send_all_sentences(text):
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


# mail 01M64H34W3BD6X85J5WPKNQWCZ: the `static inline` rule for a namespaced `var()` slot read as binding the `@theme
# inline` alias example beside it. The sentence is pinned WHOLE (a clause pin let a widened rule through), and the rule
# and its alias example must stay on one bullet line. Cheapest way past: keep the sentence and move the example's block —
# the same-line check reds on that; an alias moved into another pack's `@theme static` block reds the scan below.
ALIAS_SENTENCE = (
    "That alias is not a slot: a slot is a name § Token slots or the project's `docs/design-system.md` lists "
    "(the template lists `--surface-0`, not `--color-surface-0`), so the `@theme static inline` rule never binds the "
    "alias — `static` would also write `--color-surface-0: var(--surface-0)` under `:root, :host` (executed), while "
    "hand-written CSS references the slot (`var(--surface-0)`), never the alias, which `@theme inline` emits as no "
    "variable at all (executed); a listed `--color-*`, `--font-*`, `--radius-*` or `--ease-*` slot whose value is a "
    "`var()`, such as `--color-danger: var(--red-600)`, stays in `@theme static inline`."
)
_ALIAS_DECL = re.compile(r"--color-(?:surface-\d+|text-[\w-]+)\s*:\s*var\(")


def test_alias_of_a_root_slot_stays_in_theme_inline() -> None:
    lines = [ln for ln in _section().splitlines() if "`--color-surface-0: var(--surface-0)` →" in ln]
    assert len(lines) == 1, lines
    line = " ".join(lines[0].split())
    assert "goes in `@theme static inline`" in line and "with an `@theme inline` alias:" in line, line
    assert ALIAS_SENTENCE in line  # on the example's own bullet line, never moved to another bullet


def _static_theme_blocks(text: str) -> list[str]:
    return [b for m, b in zip(re.finditer(r"@theme\b([\w\s-]*)\{", text, re.IGNORECASE), _theme_blocks(text)) if "static" in m.group(1).lower()]


def test_no_alias_in_a_static_theme_block() -> None:
    assert _static_theme_blocks("@theme static inline {\n  --color-surface-0: var(--surface-0);\n}")  # the scan sees one
    assert _static_theme_blocks("@theme static\n  inline {\n  --color-surface-0: var(--surface-0);\n}")  # a wrapped prelude too
    assert _ALIAS_DECL.search(_static_theme_blocks("@theme static inline { --color-surface-0: var(--surface-0); }")[0])
    for pack in sorted(RULES.rglob("*.md")):
        for block in _static_theme_blocks(pack.read_text(encoding="utf-8")):
            assert not _ALIAS_DECL.search(block), (pack.name, block[:160])
