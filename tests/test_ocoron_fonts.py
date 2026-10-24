"""The Ocoron house fonts agree everywhere a pack states them (W-eaa745f3, operator ruling 2026-10-24:
headings Arya, text IBM Plex Sans).

The font names live in seven places across four packs: the Font Stack table, the Type Scale, the CSS
custom properties and coding-agent rule 1 of `core/ocoron-design-system.md`, the house-identity line
and the next/font example of `saas/60-saas-ui.md`, the Infima stacks of `core/42-docusaurus.md` and the
Ocoron sentence of `mobile-app/ocoron-mobile-design-system.md`. A font change that misses one leaves an
agent two answers. The retired names may survive only in the two Tojlo packs, which keep them as a
declared override; those two files are exempt from the scan whole, and the override is pinned
positively instead. The scan is per line: a name hard-wrapped across two lines is outside its model.

The cheapest way to satisfy this without the outcome is to drop the font names from a mirror
altogether; the review owns that, since no test can see an omission.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
HEADING, BODY, MONO = "Arya", "IBM Plex Sans", "JetBrains Mono"
# The retired fonts in any spelling an agent writes: CSS, prose, a package or an expo identifier.
# Lower-case "inter" counts too; "inter-service" and the like (a hyphen after it) do not.
RETIRED = re.compile(
    r"(?i:space(?:[\s_+.-]|%20)?grotesk)|(?i:\binter\b)(?!-)|Inter(?:[_\d]|Variable|-[A-Z])"
    r"|(?i:\binter[-_](?:tight|variable|thin|extralight|light|regular|medium|semibold|bold|extrabold|black|\d))"
    r"|(?i:expo-google-fonts/inter\b)"
)
INVISIBLE = dict.fromkeys(map(ord, "\xad\u200b\u200c\u200d\u2060\ufeff"))  # dropped before the scan
EXEMPT_PHRASE = (
    "the scaffold embeds Inter only"  # the mobile pack's statement of what the scaffold ships
)
RETIRED_ALLOWED = {"core/tojlo-design-system.md", "mobile-app/tojlo-mobile-design-system.md"}


def _read(rel: str) -> str:
    return (RULES / rel).read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    assert heading in text, f"the heading {heading!r} is gone: re-anchor this test"
    start = text.index(heading)
    level = heading.split(" ", 1)[0]
    nxt = re.search(rf"\n#{{1,{len(level)}}} ", text[start + len(heading) :])
    return text[start : start + len(heading) + nxt.start() if nxt else len(text)]


def test_font_names_agree_across_packs() -> None:
    ocoron = _read("core/ocoron-design-system.md")
    table = _section(ocoron, "### Font Stack")
    assert re.search(rf"\| \*\*Headings\*\* \(`--font-heading`\) \| {HEADING} \| 700 \|", table)
    assert re.search(rf"\| \*\*Body / UI\*\* \(`--font-body`\) \| {BODY} \| 400, 500 \|", table)
    assert re.search(rf"\| \*\*Code / Data\*\* \(`--font-mono`\) \| {MONO} \|", table)
    scale = _section(ocoron, "### Type Scale")
    for level in ("H1", "H2", "H3"):
        assert re.search(rf"\| {level} \| \d+px \| 700 \| {HEADING} \|", scale), (
            f"{level} is not Arya 700"
        )
    for level, weight in (("Body", 400), ("Body small", 400), ("Micro-label", 500)):
        assert re.search(rf"\| {level} \| \d+px \| {weight} \| {BODY} \|", scale), level
    css = _section(ocoron, "## CSS custom properties")
    assert f"--font-heading: '{HEADING}', '{BODY}', sans-serif;" in css
    assert f"--font-body: '{BODY}', sans-serif;" in css
    assert f"--font-mono: '{MONO}', monospace;" in css
    assert f"Headings = {HEADING}. Body = {BODY}. Code/data = {MONO}." in ocoron
    saas = _read("saas/60-saas-ui.md")
    assert re.search(
        rf"house web identity \(ocoron\):\*\* {HEADING} \(headings[^)]*\), {BODY} \(body/UI\)", saas
    )
    assert "import { Arya, IBM_Plex_Sans, JetBrains_Mono } from 'next/font/google';" in saas
    assert re.search(
        r"Arya\(\{ weight: \['700'\],[^)]*variable: '--font-heading'[^)]*fallback: \[\]", saas
    )
    assert re.search(
        r"IBM_Plex_Sans\(\{ weight: \['400', '500'\],[^)]*variable: '--font-body'", saas
    )
    assert "heading: ['var(--font-heading)', 'var(--font-body)']" in saas
    docs = _read("core/42-docusaurus.md")
    assert f"`--ifm-heading-font-family` → `'{HEADING}', '{BODY}', sans-serif`" in docs
    assert f"`--ifm-font-family-base` → `'{BODY}', sans-serif`" in docs
    mobile = _read("mobile-app/ocoron-mobile-design-system.md")
    assert f"the heading font is {HEADING} and the body font {BODY}" in mobile


def test_retired_names_survive_only_where_declared() -> None:
    files = sorted([*RULES.rglob("*.md"), *RULES.rglob("*.yaml")])
    assert len(files) > 50, f"scanned only {len(files)} rule files"
    stray = []
    for path in files:
        rel = path.relative_to(RULES).as_posix()
        if rel in RETIRED_ALLOWED:
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.translate(INVISIBLE).replace("\xa0", " ").replace("&nbsp;", " ")
            line = line.replace("\u2011", "-").replace(EXEMPT_PHRASE, "")
            if RETIRED.search(line):
                stray.append(f"{rel}:{n}: {line.strip()[:120]}")
    assert not stray, "a retired Ocoron font name outside the Tojlo override:\n" + "\n".join(stray)


def test_the_retired_pattern_catches_every_spelling_and_spares_prose() -> None:
    for caught in (
        "Space Grotesk",
        "space grotesk",
        "SpaceGrotesk_700",
        "'Inter', sans",
        "inter, sans-serif",
        "Inter_500Medium",
        "InterVariable",
        "Inter-Medium",
        "@expo-google-fonts/inter",
        "Inter 500",
        "family=Space+Grotesk:wght@700",
        "Space%20Grotesk",
        "Space.Grotesk",
        "inter-regular.woff2",
        "inter-medium",
        "inter_500medium",
        "@fontsource/inter-tight",
    ):
        assert RETIRED.search(caught), caught
    for spared in ("inter-service calls", "Interface", "International", "interact"):
        assert not RETIRED.search(spared), spared


def test_tojlo_states_its_own_stack_wherever_it_inherits_fonts() -> None:
    tojlo = _read("core/tojlo-design-system.md")
    contract = _section(tojlo, "## Inheritance Contract")
    stack = [ln for ln in contract.splitlines() if ln.startswith("- **Typography stack")]
    assert len(stack) == 1 and "Tojlo override" in stack[0], stack
    assert "Space Grotesk 600 and 700" in stack[0] and "Inter 400 and 500" in stack[0], stack
    assert "**Tojlo's own stack**" in _section(tojlo, "## Typography")
    assert "--font-heading: 'Space Grotesk', sans-serif;" in tojlo
    assert "except rule 1's font names" in tojlo
    mobile = _read("mobile-app/tojlo-mobile-design-system.md")
    assert "Tojlo's own stack" in mobile and "`@expo-google-fonts/space-grotesk`" in mobile
