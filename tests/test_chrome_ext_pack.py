"""Pins `chrome-ext/70-chrome-ext.md` to the scaffold it describes, to its own cross-references and to D-486.

The pack is glob-activated in every chrome-extension repo, so a stale line in it is copied straight into code.
Five things it states can go false with no other gate turning red:

1. What the chrome-extension scaffold emits — the WXT entrypoints, `wxt zip`, the `src/locales` strings and a
   `server/` with no `/metrics` (the pack once promised `/metrics` and a `_locales`/`static/i18n` pair).
2. Every `§ <Section>` it cites, in itself, in a sibling pack or in the design-system template.
3. The developer-mode channel (D-486, the operator's ruling that an extension the store will not approve
   ships unpacked): the facts a developer needs to ship it — Developer mode staying on, the policy that can
   forbid it, the MV3 rules it does not lift, the manifest `key`, the update checker and `wxt zip`.
4. The auth route it names exists in `fabrik-lib/fastapi-user-auth` (it once named `/auth/login/extension`).
5. No version number in any shape (the corpus rule: a version in a pack goes stale).

The cheapest way past (3) is to keep the phrases and drop their meaning; the review is what reads the
meaning. The cheapest way past (5) is a version in words ("version twenty"); the check catches the shapes
agents actually copy (`v1.2`, `1.2.3`, `Chrome 137`, `>=1.59`).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from fabrik import config as fabrik_config
from fabrik.scaffold import create_project

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
PACK = RULES / "chrome-ext" / "70-chrome-ext.md"
TEMPLATE = RULES / "core" / "design-system-template.md"
AUTH_ROUTER = (
    Path(os.environ.get("FABRIK_LIB_DIR", "/opt/fabrik-lib"))
    / "fastapi-user-auth"
    / "fastapi_user_auth"
    / "router.py"
)

requires_fabrik_env = pytest.mark.skipif(
    not (ROOT / "templates" / "chrome-extension").is_dir(),
    reason="needs the hub's templates/chrome-extension",
)


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("chrome-ext")
    # fabrik.config binds FABRIK_ROOT at import, so setting it here would change nothing:
    # assert the scaffolder reads THIS tree's templates instead of grading another one
    assert fabrik_config.FABRIK_ROOT.resolve() == ROOT, (
        f"the scaffolder reads {fabrik_config.FABRIK_ROOT}, not {ROOT}: run with FABRIK_ROOT={ROOT}"
    )
    create_project(
        "chromeext", "probe", base=base, project_type="chrome-extension", generate_spec=False
    )
    return base / "chromeext"


def _pack() -> str:
    return PACK.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    start = text.index(f"\n## {heading}\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def _headings(path: Path) -> list[str]:
    return [
        ln.lstrip("#").strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.startswith("#")
    ]


_PACK_NAME = re.compile(r"`((?:[a-z.-]+/)*[a-z0-9-]+\.md)`\**\s*$")


def _read_heading(text: str, i: int) -> str:
    """The heading text after `§ ` at position i: a leading `N. `, then up to the first
    character that cannot belong to a heading; a `)` closes only a `(` the heading opened."""
    m = re.match(r"\d+\. ", text[i:])
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
    return re.sub(r"\s+(?:and|or|to|below|above|for|is|are|on|in)$", "", out.strip()).strip()


def _cites(text: str) -> list[tuple[str, str]]:
    """(target, heading) for every `§ <Heading>` outside a code span: a backticked doc name just before it
    names that doc, "template" names the design-system template, a cite that follows another with only a
    comma or "and" between them shares its doc ("§ 1. A, § 3. B and § 5. C"), and anything else is this
    pack. A `§` inside a code span (`agents-fabrik.md § Supabase`) is not read — the bound is stated."""
    cites: list[tuple[str, str]] = []
    prev_end, prev_target = -1, ""
    for m in re.finditer(r"§ (?=[A-Z0-9])", text):
        line_start = text.rfind("\n", 0, m.start()) + 1
        if text[line_start : m.start()].count("`") % 2:
            continue
        before = text[max(0, m.start() - 120) : m.start()]
        pm = _PACK_NAME.search(before)
        if pm:
            target = pm.group(1)
        elif re.search(r"template\s*$", before):
            target = "core/design-system-template.md"
        elif prev_end >= 0 and re.fullmatch(r"\s*(?:,|,?\s*and)\s*", text[prev_end : m.start()]):
            target = prev_target
        else:
            target = PACK.name
        heading = _read_heading(text, m.end())
        cites.append(
            (target.rsplit("/", 1)[-1] if not target.startswith("docs/") else target, heading)
        )
        prev_end, prev_target = m.end() + len(heading), target
    return cites


def _prefix(short: str, long: str) -> bool:
    return re.match(re.escape(short) + r"(?![A-Za-z])", long) is not None


def test_no_version_literals() -> None:
    body = _pack().split("\n---\n", 1)[1]  # the frontmatter's date is not a version
    found = re.findall(
        r"\bv\d+(?:\.\d+)?\b"  # v1.2, v137
        r"|\b\d+\.\d+\.\d+\b"  # 1.2.3
        r"|\bChrome v?\d{2,3}\b|\(Chrome \d"  # Chrome 137, Chrome v137, (Chrome 121+)
        r"|[≥>]=?\s?\d+(?:\.\d+)?"  # >=1.59, ≥ 2
        r"|@\d+\.\d+"  # size-limit@11.0
        r"|\b[a-z][\w./-]*[a-z] \d+\.\d+\b",  # wxt 0.19, @playwright/test 1.59
        body,
    )
    assert not found, f"version literals in the pack: {found}"


def test_every_cited_section_exists() -> None:
    cites = _cites(_pack())
    assert len(cites) >= 15, f"the cite parser found only {len(cites)} cites: check _cites"
    missing = []
    for target, heading in cites:
        if target == PACK.name:
            path: Path | None = PACK
        elif target.startswith("docs/"):
            path = ROOT / target
        else:
            path = next(RULES.rglob(target), None)
        path = path if path and path.is_file() else None
        heads = _headings(path) if path else []
        # a cite may shorten a heading, and prose may run on after one ("§ Bundle Budgets sets the
        # numbers"): a word-boundary prefix either way, never a bare substring
        if not any(_prefix(heading, h) or _prefix(h, heading) for h in heads):
            missing.append(f"{target} § {heading}")
    assert not missing, f"cited sections not found: {missing}"


@pytest.mark.parametrize(
    "fact",
    [
        "Load unpacked",
        "only while Developer mode stays on",
        "`ExtensionDeveloperModeSettings`",
        "available only to policy-installed extensions",
        "Manifest V2 no longer runs",
        "never auto-updates an unpacked extension",
        "manifest `key`",
        "`wxt zip`",
        "supported, first-class channel",
    ],
)
def test_developer_mode_channel_is_documented(fact: str) -> None:
    assert fact in _section(_pack(), "Distribution Model"), (
        f"§ Distribution Model no longer says {fact!r}: the developer-mode channel (D-486) lost a fact"
    )


@requires_fabrik_env
def test_scaffold_matches_the_pack(project: Path) -> None:
    ext = project / "extension"
    for entry in ("popup", "options"):
        assert (ext / "src" / "entrypoints" / entry).is_dir(), f"entrypoints/{entry}/ is gone"
    assert '"zip": "wxt zip"' in (ext / "package.json").read_text(encoding="utf-8")
    for lang in ("en", "tr"):
        assert (ext / "src" / "locales" / f"{lang}.json").is_file()
    main = next((project / "server" / "src").glob("*/main.py")).read_text(encoding="utf-8")
    assert "/metrics" not in main, "server/ now serves /metrics: update § Two-Faced Architecture"
    pack = _pack()
    assert "`entrypoints/popup/`" in pack and "`extension/src/locales/<lang>.json`" in pack
    assert "no `/metrics`" in pack


@pytest.mark.skipif(not AUTH_ROUTER.is_file(), reason="needs /opt/fabrik-lib")
def test_auth_route_exists() -> None:
    router = AUTH_ROUTER.read_text(encoding="utf-8")
    assert '@router.post("/login")' in router and 'prefix="/auth"' in router
    assert "`/auth/login`" in _pack()
    assert "/auth/login/extension" not in _pack()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("see § Versioning & Updates).", [(PACK.name, "Versioning & Updates")]),
        (
            "owned by `89-extension-launch-checklist.md` § 1. Developer account (one-time), § 3. Store listing assets and § 5. Review expectations & traps.",
            [
                ("89-extension-launch-checklist.md", "1. Developer account (one-time)"),
                ("89-extension-launch-checklist.md", "3. Store listing assets"),
                ("89-extension-launch-checklist.md", "5. Review expectations & traps"),
            ],
        ),
        (
            "the summary in `docs/reference/gui-toolchain.md` § Chrome extension.",
            [("docs/reference/gui-toolchain.md", "Chrome extension")],
        ),
        ("See `agents-fabrik.md § Supabase`.", []),
        ("(template § Visual Rules).", [("design-system-template.md", "Visual Rules")]),
        (
            "the follow `core/design-system-template.md` § Scaffold Adaptation Matrix; read",
            [("design-system-template.md", "Scaffold Adaptation Matrix")],
        ),
        ("(§ Design System (Compact) below).", [(PACK.name, "Design System (Compact)")]),
        ("`00-domain-chrome-ext.md` Fork 2", []),
    ],
)
def test_cite_parser_reads_every_spelling(text: str, expected: list[tuple[str, str]]) -> None:
    assert _cites(text) == expected
