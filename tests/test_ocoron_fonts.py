"""The Ocoron house fonts agree everywhere a pack states them (W-eaa745f3, operator ruling 2026-10-24:
headings Arya, text IBM Plex Sans).

The font names live in seven places across five packs: the Font Stack table, the CSS custom
properties and coding-agent rule 1 of `core/ocoron-design-system.md`, the house-identity line and the
next/font example of `saas/60-saas-ui.md`, the Infima stacks of `core/42-docusaurus.md` and the Ocoron
sentence of `mobile-app/ocoron-mobile-design-system.md`. A font change that misses one leaves an
agent two answers. The retired names may survive only in the Tojlo packs, which keep them as a
declared override, and in CLAIMS.yaml's history.

The cheapest way to satisfy this without the outcome is to drop the font names from a mirror
altogether; the review owns that, since no test can see an omission.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
HEADING, BODY, MONO = "Arya", "IBM Plex Sans", "JetBrains Mono"
RETIRED = re.compile(r"Space[ _-]?Grotesk|space-grotesk|\bInter\b(?!-)")  # the font, not "inter-service"
RETIRED_ALLOWED = {"core/tojlo-design-system.md", "mobile-app/tojlo-mobile-design-system.md"}


def _read(rel: str) -> str:
    return (RULES / rel).read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    nxt = text.find("\n## ", start + len(heading))
    return text[start : nxt if nxt != -1 else len(text)]


def test_font_names_agree_across_packs() -> None:
    ocoron = _read("core/ocoron-design-system.md")
    table = _section(ocoron, "### Font Stack")
    assert re.search(rf"\| \*\*Headings\*\* \(`--font-heading`\) \| {HEADING} \| 700 \|", table)
    assert re.search(rf"\| \*\*Body / UI\*\* \(`--font-body`\) \| {BODY} \| 400, 500", table)
    assert re.search(rf"\| \*\*Code / Data\*\* \(`--font-mono`\) \| {MONO} \|", table)
    css = _section(ocoron, "## CSS custom properties")
    assert f"--font-heading: '{HEADING}', '{BODY}', sans-serif;" in css
    assert f"--font-body: '{BODY}', sans-serif;" in css
    assert f"Headings = {HEADING}. Body = {BODY}. Code/data = {MONO}." in ocoron
    saas = _read("saas/60-saas-ui.md")
    assert re.search(rf"house web identity \(ocoron\):\*\* {HEADING} \(headings[^)]*\), {BODY} \(body/UI\)", saas)
    assert "import { Arya, IBM_Plex_Sans, JetBrains_Mono } from 'next/font/google';" in saas
    docs = _read("core/42-docusaurus.md")
    assert f"`--ifm-heading-font-family` → `'{HEADING}', '{BODY}', sans-serif`" in docs
    assert f"`--ifm-font-family-base` → `'{BODY}', sans-serif`" in docs
    mobile = _read("mobile-app/ocoron-mobile-design-system.md")
    assert f"the heading font is {HEADING} and the body font {BODY}" in mobile


def test_retired_names_survive_only_where_declared() -> None:
    stray = []
    for path in sorted(RULES.rglob("*.md")):
        rel = path.relative_to(RULES).as_posix()
        if rel in RETIRED_ALLOWED:
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if RETIRED.search(line) and "scaffold embeds Inter" not in line:
                stray.append(f"{rel}:{n}: {line.strip()[:120]}")
    assert not stray, "a retired Ocoron font name outside the Tojlo override:\n" + "\n".join(stray)


def test_tojlo_declares_its_override_wherever_it_inherits_fonts() -> None:
    tojlo = _read("core/tojlo-design-system.md")
    assert "Tojlo override" in _section(tojlo, "## Inheritance Contract")
    assert "Inherited from Ocoron unchanged.** Same fonts" not in tojlo
    mobile = _read("mobile-app/tojlo-mobile-design-system.md")
    assert "Tojlo's are Ocoron's" not in mobile
