"""Pins the web UI-design routing to the `frontend-design:frontend-design` skill (W-00de7d82, operator ruling
2026-10-24 relayed in mail 01M5QJ3V4AN7C9CJV9B9Q8QEWB: "use frontend design plugin for ui designs in websites").

Four things can go false with no other gate turning red:

1. The canonical rule exists once, in `core/63-frontend-design.md`, with the full skill name, the brief order
   that puts operator rulings and the frozen design system (the template's structure included) above the skill,
   and the skill's AI-generated clusters written out (the `design-review` agent has no Skill tool).
2. Every routing site points to that pack by the full name — a site that drops the pointer routes design work
   past the skill again.
3. No source, fragment, agent or pack names the bare `frontend-design`: two installed skills share that name
   (the plugin's and the older `example-skills:frontend-design`), so a bare name resolves to either.
4. The pack's globs load on web GUI files, nested HTML included (the fleet matcher reads a middle `**` as one
   segment, so depth is spelled out), and stay off the non-GUI paths listed below. Its CSS entry points are the
   template's and reach wherever the template's do.

The cheapest way past (2) is a pointer that names the pack but not the skill, or the skill but not the pack;
each site must hold one paragraph naming both. The cheapest way past (3) is the name without backticks — the check reads the
name as a token in any case, whatever surrounds it, except where a `:` or `@` joins it to a namespace, skill or
plugin id, or a `/` before it makes it a path segment.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = "frontend-design:frontend-design"
PACK_REL = "core/63-frontend-design.md"
PACK = ROOT / ".windsurf" / "rules" / PACK_REL
TITLE = "Designing what the brief leaves free"
# a bare name: not joined to a namespace (`x:frontend-design`), a skill (`frontend-design:x`), a plugin id
# (`frontend-design@x`) or a longer identifier
BARE = re.compile(r"(?<![:\w@/-])frontend-design(?!:[\w-]|@|[\w-])", re.IGNORECASE)
SITES = (
    "commands/_sources/fabrik-ui-design.md",
    "commands/_sources/fabrik-ui-design-review.md",
    "commands/_sources/design-review.md",
    "commands/_sources/fabrik-execute-plan.md",
    "commands/_agents/design-review.md",
    "commands/_agents/fabrik-gui.md",
    ".windsurf/rules/saas/60-saas-ui.md",
    ".windsurf/rules/chrome-ext/70-chrome-ext.md",
    ".windsurf/rules/desktop-app/72-desktop.md",
    "docs/reference/gui-toolchain.md",
)
SCANNED = ("commands/_sources", "commands/_fragments", "commands/_agents", ".windsurf/rules")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pack_matches_path = _load("rules_match").pack_matches_path
_parse_frontmatter = _load("select_rules")._parse_frontmatter


def _pack() -> str:
    return PACK.read_text(encoding="utf-8")


def test_the_pack_states_the_rule() -> None:
    text = _pack()
    flat = " ".join(text.split())
    assert text.count(f"## {TITLE}") == 1
    assert SKILL in text and "example-skills:frontend-design" in text  # names the one to use, and the one not to
    # the brief order: operator rulings first, then the frozen contracts, the template's structure inside them
    i_ruling = flat.index("operator's rulings")
    i_ui = flat.index("docs/ui-design.md", i_ruling)
    i_ds = flat.index("docs/design-system.md", i_ui)
    assert i_ruling < i_ui < i_ds
    assert "design-system-template.md" in flat[i_ds:]
    assert "brief, never a free axis" in flat
    # the clusters, written out for a reader with no Skill tool
    for cluster in ("cream background", "near-black background", "broadsheet", "identical rounded cards", "eyebrow"):
        assert cluster in flat, cluster
    # a finding can close, and an unattended run never stops to ask
    assert "never closes by editing a frozen contract" in flat
    assert "never stops to confirm" in flat
    assert "never mints" in flat


@pytest.mark.parametrize("rel", SITES)
def test_every_routing_site_points_to_the_pack(rel: str) -> None:
    paragraphs = re.split(r"\n\s*\n", (ROOT / rel).read_text(encoding="utf-8"))
    assert any(SKILL in para and PACK_REL in para for para in paragraphs), rel


def test_no_source_names_the_bare_skill() -> None:
    hits = []
    for base in SCANNED:
        for path in sorted((ROOT / base).rglob("*.md")):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if BARE.search(line):
                    hits.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()[:120]}")
    assert not hits, "\n".join(hits)


def test_the_bare_name_check_reads_the_shapes_it_must() -> None:
    for bare in ("the `frontend-design` skill", "use frontend-design here", "(frontend-design)",
                 "Invoke frontend-design: the skill", "load frontend-design/SKILL.md", "the Frontend-Design skill"):
        assert BARE.search(bare), bare
    for joined in (SKILL, "example-skills:frontend-design", "frontend-design@claude-plugins-official",
                   "plugins/frontend-design/skills", "frontend-design-routing"):
        assert not BARE.search(joined), joined


def _globs() -> list[str]:
    globs, _ = _parse_frontmatter(_pack())
    return globs


@pytest.mark.parametrize(
    "path",
    [
        "src/components/Hero.astro",
        "components/ui/button.tsx",
        "src/App.jsx",
        "src/components/Card.vue",
        "src/routes/+page.svelte",
        "src/index.html",
        "src/renderer/pages/index.html",
        "extension/src/entrypoints/popup/index.html",
        "public/index.html",
        "public/blog/post.html",
        "src/styles/site-base.css",
        "app/globals.css",
        "src/css/custom.css",
        "tailwind.config.ts",
        "docs/design-system.md",
        "docs/ui-design.md",
    ],
)
def test_the_pack_globs_stay_on_web_files(path: str) -> None:
    assert any(pack_matches_path(path, g, empty_matches_all=False) for g in _globs()), (path, _globs())


@pytest.mark.parametrize(
    "path",
    [
        "app/main.py",
        "README.md",
        "src/index.ts",
        "htmlcov/index.html",
        "htmlcov/style.css",
        "_build/html/index.html",
        "docs/_build/html/search.html",
        "site/index.html",
        "static/swagger-ui.css",
        "docs/assets/extra.css",
        "tests/fixtures/sample.css",
    ],
)
def test_the_pack_globs_stay_off_non_gui_files(path: str) -> None:
    assert not any(pack_matches_path(path, g, empty_matches_all=False) for g in _globs()), path
