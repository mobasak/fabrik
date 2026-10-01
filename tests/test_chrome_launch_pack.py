"""Pins `chrome-ext/89-extension-launch-checklist.md` to its consumer, its cross-references and D-486.

/fabrik-release runs this checklist for every chrome-extension release, and the checklist is glob-activated in every
chrome-extension repo. Five things it states can go false with no other gate turning red:

1. Every `§ <Section>` it cites, in itself or in a sibling pack (it once cited "§ backend is Epic 1",
   "§ performance gate" and "§ legal", none of which existed).
2. The developer-mode release (D-486): § 7 carries the gates an unlistable release needs — the recorded reason, the
   manifest `key`, the update checker and its version manifest, the checksum, the install guide, Gate 2.
3. The trader/non-trader declaration in § 1.
4. Its consumer: /fabrik-release's EXTENSION path still names this pack and still splits the listable and unlistable rings.
5. Its globs: no `**/manifest.json`, which fired the checklist in an Obsidian plugin and two other non-extension repos.
6. No version number in any shape.

The cheapest way past (2) and (3) is to keep the phrases and drop their meaning; the review reads the meaning. The
cheapest way past (6) is a version in words; the check catches the shapes agents copy.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
PACK = RULES / "chrome-ext" / "89-extension-launch-checklist.md"
RELEASE = ROOT / "commands" / "_sources" / "fabrik-release.md"
# project-side docs the checklist writes into; they live in the extension repo, not the hub, so their § cites are
# not resolvable here — the bound is this named set, never "any docs/ path"
PROJECT_DOCS = frozenset({"docs/DEPLOYMENT.md"})


def _pack() -> str:
    return PACK.read_text(encoding="utf-8")


def _section(text: str, prefix: str) -> str:
    start = re.search(rf"^## {re.escape(prefix)}.*$", text, re.M)
    assert start, f"no section starting {prefix!r}"
    end = text.find("\n## ", start.end())
    return text[start.start() : end if end != -1 else len(text)]


def _headings(path: Path) -> list[str]:
    return [
        ln.lstrip("#").strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.startswith("#")
    ]


def _prefix(short: str, long: str) -> bool:
    return re.match(re.escape(short) + r"(?![A-Za-z0-9])", long) is not None


_PACK_NAME = re.compile(r"`((?:[a-z.-]+/)*[A-Za-z0-9_-]+\.md)`\**\s*$")


def _read_heading(text: str, i: int) -> str:
    """The heading after `§ ` at i. A numbered heading (`3. Store listing assets`) reads to the first character that
    cannot belong to a heading; a bare number (`§ 7`, `§ 1–6`, `§ 2–§ 4`) is the section number alone."""
    m = re.match(r"(\d+)(\. )?", text[i:])
    if m and not m.group(2):
        return m.group(1)
    out = m.group(0) if m else ""
    j = i + len(out)
    depth = 0
    while j < len(text) and text[j] not in ".;:,*—`|§\n":
        ch = text[j]
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                break
            depth -= 1
        out += ch
        j += 1
    return re.sub(r"\s+(?:and|or|to|for|is|are|on|in)$", "", out.strip()).strip()


def _cites(text: str) -> list[tuple[str, str]]:
    """(target, heading) for every `§ <Heading>` outside a code span: a backticked pack name just before it names that
    pack, a cite following another with only a comma or "and" between shares its pack, anything else is this pack."""
    cites: list[tuple[str, str]] = []
    prev_end, prev_target = -1, ""
    for m in re.finditer(r"§ (?=[A-Za-z0-9])", text):
        line_start = text.rfind("\n", 0, m.start()) + 1
        if text[line_start : m.start()].count("`") % 2:
            continue
        before = text[max(0, m.start() - 120) : m.start()]
        pm = _PACK_NAME.search(before)
        if pm:
            target = pm.group(1)
            if not target.startswith("docs/"):
                target = target.rsplit("/", 1)[-1]
        elif prev_end >= 0 and re.fullmatch(r"\s*(?:,|,?\s*and)\s*", text[prev_end : m.start()]):
            target = prev_target
        else:
            target = PACK.name
        heading = _read_heading(text, m.end())
        cites.append((target, heading))
        prev_end, prev_target = m.end() + len(heading), target
    return cites


def test_no_version_literals() -> None:
    body = _pack().split("\n---\n", 1)[1]
    found = re.findall(
        r"\bv\d+(?:\.\d+)?\b|\b\d+\.\d+\.\d+\b|\bChrome v?\d{2,3}\b|\(Chrome \d"
        r"|[≥>]=?\s?\d+(?:\.\d+)?|@\d+\.\d+|\b[a-z][\w./-]*[a-z] \d+\.\d+\b",
        body,
    )
    assert not found, f"version literals in the pack: {found}"


def test_every_cited_section_exists() -> None:
    cites = _cites(_pack())
    assert len(cites) >= 12, f"the cite parser found only {len(cites)} cites: check _cites"
    missing = []
    for target, heading in cites:
        if target in PROJECT_DOCS:
            continue
        path = PACK if target == PACK.name else next(RULES.rglob(target), None)
        heads = _headings(path) if path else []
        if not any(_prefix(heading, h) or _prefix(h, heading) for h in heads):
            missing.append(f"{target} § {heading}")
    assert not missing, f"cited sections not found: {missing}"


@pytest.mark.parametrize(
    "fact",
    [
        "the store will not approve (D-486",
        "`docs/DEPLOYMENT.md` § distribution",
        "manifest `key` is pinned",
        "update checker is live",
        "SHA-256",
        "Load unpacked",
        "keep Developer mode on",
        "no agent publishes",
    ],
)
def test_developer_mode_release_gates(fact: str) -> None:
    assert fact in _section(_pack(), "7. "), f"§ 7 no longer carries {fact!r} (D-486)"


def test_trader_declaration_is_a_gate() -> None:
    one = _section(_pack(), "1. ")
    assert "Trader or non-trader declaration" in one and "trader/non-trader declaration" in one


def test_release_command_still_runs_this_pack() -> None:
    release = RELEASE.read_text(encoding="utf-8")
    ext = release[release.index("## EXTENSION path") : release.index("## DESKTOP path")]
    assert "89-extension-launch-checklist.md" in ext
    assert "UNLISTABLE" in ext and "LISTABLE" in ext, (
        "the release path no longer splits the two rings"
    )


def test_globs_skip_manifest_json() -> None:
    front = _pack().split("\n---\n", 1)[0]
    assert "**/extension/**" in front
    assert "manifest.json" not in front, "a manifest.json glob fires in non-extension repos"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "follows `70-chrome-ext.md` § Enterprise force-install. Shipping",
            [("70-chrome-ext.md", "Enterprise force-install")],
        ),
        (
            "(`00-domain-chrome-ext.md` § 5. Backend Dependency).",
            [("00-domain-chrome-ext.md", "5. Backend Dependency")],
        ),
        (
            "(`saas/88-saas-launch-checklist.md` § Legal Pages and § Data Protection (GDPR + KVKK)).",
            [
                ("88-saas-launch-checklist.md", "Legal Pages"),
                ("88-saas-launch-checklist.md", "Data Protection (GDPR + KVKK)"),
            ],
        ),
        ("Every release: § 2–§ 4 re-run.", [(PACK.name, "2"), (PACK.name, "4")]),
        ("§ 1–6 for the store, § 7 for", [(PACK.name, "1"), (PACK.name, "7")]),
        (
            "(`00-domain-chrome-ext.md` § backend is Epic 1).",
            [("00-domain-chrome-ext.md", "backend is Epic 1")],
        ),
        (
            "written in `docs/DEPLOYMENT.md` § store listing — create",
            [("docs/DEPLOYMENT.md", "store listing")],
        ),
    ],
)
def test_cite_parser_reads_every_spelling(text: str, expected: list[tuple[str, str]]) -> None:
    assert _cites(text) == expected
