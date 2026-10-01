"""Pins `core/tojlo-design-system.md` to D-051 and to the packs it inherits from.

Since D-406 the structure lives in `core/design-system-template.md` and the values in `core/ocoron-design-system.md`.
The Tojlo pack kept restating both, and its copies drifted: retired slot names, stale hex values, a Tailwind v3
snippet, a contrast table computed for old colours. These facts are pinned:

1. It loads by description only, and the description names the declaration.
2. Every slot it names is a template slot (the retired `--color-purple` / `--color-secondary` only where the pack
   explains that they are aliases).
3. Hex values appear only in § Logo and § Email Templates — brand assets and email-safe colours — never as token
   values, which are Ocoron's.
4. Every `<pack>.md § <heading>` it cites exists.
5. Every "Tojlo <MODULE>" it names is in its own § Module Naming list.
6. Its T-rules run T1 to the number its Contents line states, with no gap.

The cheapest way to satisfy (3) is to move a token table into § Logo; the review owns that.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
PACK = RULES / "core" / "tojlo-design-system.md"
TEMPLATE = RULES / "core" / "design-system-template.md"
STATES = ("accent", "success", "warning", "danger", "info", "ai")
RETIRED = {"--color-purple", "--color-secondary"}
HEX_ALLOWED = ("Logo", "Email Templates")


def _parts() -> tuple[str, str]:
    _, front, body = PACK.read_text(encoding="utf-8").split("---", 2)
    return front, body


def _sections(body: str) -> list[tuple[str, str]]:
    parts = re.split(r"^## (.+)$", body, flags=re.M)
    return list(zip(parts[1::2], parts[2::2], strict=True))


def test_loads_by_description_only() -> None:
    front, _ = _parts()
    assert not re.search(r"^(?:globs|activation|trigger):", front, re.M), (
        "a house identity never loads by glob (D-051)"
    )
    description = re.search(r"^description:(.+)$", front, re.M)
    assert description and "declares" in description.group(1) and "Tojlo" in description.group(1)


def test_slots_are_template_slots() -> None:
    _, body = _parts()
    defined = set(re.findall(r"`(--[a-z0-9-]+)`", TEMPLATE.read_text(encoding="utf-8")))
    defined |= {f"--color-{s}{x}" for s in STATES for x in ("", "-fg", "-text", "-muted")}
    named = set(re.findall(r"`(--[a-z0-9-]+)`", body))
    assert len(named) >= 10, f"parsed only {len(named)} slots"
    assert named - RETIRED <= defined, (
        f"slots the template does not define: {sorted(named - RETIRED - defined)}"
    )
    for line in body.splitlines():
        if RETIRED & set(re.findall(r"`(--[a-z0-9-]+)`", line)):
            assert "alias" in line or "retired" in line, (
                f"a retired slot name used as a slot: {line!r}"
            )


def test_hex_only_in_logo_and_email() -> None:
    _, body = _parts()
    found = 0
    for title, text in _sections(body):
        for line in text.splitlines():
            for hexval in re.findall(r"#[0-9A-Fa-f]{6}\b", line):
                found += 1
                assert title.startswith(HEX_ALLOWED), (
                    f"hex {hexval} in § {title}: token values are Ocoron's — name the slot instead"
                )
    assert found, "no hex at all — the logo colour variants should still carry theirs"
    for line in body.splitlines():
        if re.search(r"#[0-9A-Fa-f]{6}\b", line):
            assert not re.search(r"`--color-[a-z-]+`", line), (
                f"a colour slot paired with a hex value — a token table; the values are Ocoron's: {line!r}"
            )


_CITE = re.compile(r"`(?:[a-z0-9-]+/)?([a-z0-9-]+\.md)`\s*§ ([A-Z][^.;:,()`—]*)")


def test_every_cited_section_exists() -> None:
    _, body = _parts()
    found, missing = 0, []
    for m in _CITE.finditer(body):
        targets = list(RULES.rglob(m.group(1)))
        assert len(targets) == 1, f"{m.group(1)} resolves to {len(targets)} packs"
        heads = [
            re.sub(r"\s*\(.*\)$", "", re.sub(r"^\d+\.\s+", "", ln.lstrip("#").strip()))
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
    assert found >= 8, f"parsed only {found} cites"
    assert not missing, f"cited sections that do not exist: {missing}"


def test_every_module_named_is_canonical() -> None:
    _, body = _parts()
    naming = body.split("### Module Naming", 1)[1].split("\n### ", 1)[0]
    canonical = set(re.findall(r"\*\*Tojlo ([A-Z]+)\*\*", naming))
    assert len(canonical) >= 10, f"parsed only {len(canonical)} canonical modules"
    # "Tojlo OS" is the platform's full name and "Tojlo AI Rules" a heading — brand terms, not modules
    named = set(re.findall(r"\bTojlo ([A-Z]{2,})\b", body)) - {"OS", "AI"}
    assert named <= canonical, (
        f"modules the canonical list does not have: {sorted(named - canonical)}"
    )


def test_t_rules_are_contiguous() -> None:
    _, body = _parts()
    stated = re.search(r"\[Rules for AI Agents\]\([^)]*\) · T1–T(\d+)", body)
    assert stated, "the Contents line no longer states the T-rule range"
    numbers = sorted({int(n) for n in re.findall(r"^T(\d+)\. ", body, re.M)})
    assert numbers == list(range(1, int(stated.group(1)) + 1)), (
        f"T-rules {numbers[:3]}…{numbers[-3:]} do not run T1–T{stated.group(1)}"
    )
