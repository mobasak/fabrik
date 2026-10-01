"""Pins `chrome-ext/00-domain-chrome-ext.md` to the scaffold it plans for and to its own ONE RULE.

The pack is `activation: manual`, so no glob check ever reads it; /fabrik-vision and /fabrik-epics load
it by path. Four things it states can go false without any other gate turning red:

1. What the chrome-extension scaffold emits as its backend — a same-repo `server/` FastAPI service
   beside `extension/`, with no database and no auth by default (the pack once told planners to add a
   separate python-api project).
2. Every `<sibling pack>.md § <section>` it cites — a renamed section in 70/85/88 leaves a dangling
   pointer at intake.
3. Every `§N <Word>` reference to one of its own dimensions — the epic table once pointed "§7 Analytics"
   at §7 Unit Economics.
4. Its ONE RULE — no copied value: no dollar amount and no percentage (fees and budgets live in 70/89).

The cheapest way to satisfy (4) without the outcome is to write a price in words ("five dollars"); the
check catches the shape agents actually copy from a vendor page (`$5`, `30%`), and the pack's review is
what catches the rest. The cheapest way past (3) is a reference with no word after the number ("§8"),
which the check cannot name-match; the pack uses that form only where the sentence names the dimension.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from fabrik import config as fabrik_config
from fabrik.scaffold import create_project

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
PACK = RULES / "chrome-ext" / "00-domain-chrome-ext.md"

requires_fabrik_env = pytest.mark.skipif(
    not (ROOT / "templates" / "chrome-extension").is_dir(),
    reason="needs the hub's templates/chrome-extension",
)


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("chrome-domain")
    # fabrik.config binds FABRIK_ROOT at import, so setting it here would change nothing:
    # assert the scaffolder reads THIS tree's templates instead of grading another one
    assert fabrik_config.FABRIK_ROOT.resolve() == ROOT, (
        f"the scaffolder reads {fabrik_config.FABRIK_ROOT}, not {ROOT}: run with FABRIK_ROOT={ROOT}"
    )
    create_project(
        "chromedomain", "probe", base=base, project_type="chrome-extension", generate_spec=False
    )
    return base / "chromedomain"


def _pack() -> str:
    return PACK.read_text(encoding="utf-8")


def _headings(pack_path: Path) -> list[str]:
    return [
        ln.lstrip("#").strip()
        for ln in pack_path.read_text(encoding="utf-8").splitlines()
        if ln.startswith("#")
    ]


# `70-chrome-ext.md` § Distribution Model — a backticked pack name, then one `§` heading prefix that
# ends at the first character that cannot belong to a heading.
_CITE = re.compile(
    r"`(?:\.windsurf/rules/)?(?:[a-z-]+/)?(\d\d-[a-z0-9-]+\.md)`\**\s*§ ((?:\d+\. )?[^.;:*—`]+)"
)


def _section_cites(text: str) -> list[tuple[str, str]]:
    cites = []
    for m in _CITE.finditer(text):
        section = re.sub(r"\s+(?:and|or|to)$", "", m.group(2).strip())
        section = re.split(r"\s+(?:and|or)\s+\*\*|,", section)[0].strip()
        if section.count(")") > section.count("("):  # the prose's closing paren, not the heading's
            section = section[: section.rindex(")")].strip()
        cites.append((m.group(1), section))
    return cites


@requires_fabrik_env
def test_scaffold_backend_is_the_repo_server(project: Path) -> None:
    assert (project / "server" / "src" / "chromedomain" / "main.py").is_file(), (
        "the scaffold no longer emits server/: update the pack's §5 Backend Dependency"
    )
    assert (project / "extension" / "wxt.config.ts").is_file()
    assert "`server/`" in _pack() and "`extension/`" in _pack()
    assert "python-api" not in _pack(), "the pack plans a separate backend project again"


@requires_fabrik_env
def test_scaffold_backend_ships_with_no_db_and_no_auth() -> None:
    defaults = (ROOT / "templates" / "chrome-extension" / "defaults.yaml").read_text(
        encoding="utf-8"
    )
    for flag in ("needs_database", "has_bearer_api"):
        assert re.search(rf"^\s*{flag}:\s*false\s*$", defaults, re.M), (
            f"{flag} is no longer false by default: update the pack's 'no database and no auth'"
        )
    assert "no database and no auth" in _pack()


def test_every_cited_sibling_section_exists() -> None:
    cites = _section_cites(_pack())
    assert len(cites) >= 6, f"the cite parser found only {len(cites)} cites: check _CITE"
    missing = []
    for pack_name, section in cites:
        target = next(RULES.rglob(pack_name), None)
        heads = _headings(target) if target else []
        # a cite may shorten a heading ("Auth" for "Auth (Extension ↔ Backend)"), never extend it
        if not any(re.match(re.escape(section) + r"(?![A-Za-z])", h) for h in heads):
            missing.append(f"{pack_name} § {section}")
    assert not missing, f"cited sections not found: {missing}"


def test_every_dimension_reference_names_its_dimension() -> None:
    pack = _pack()
    dims = {int(m.group(1)): m.group(2) for m in re.finditer(r"^### (\d+)\. (.+)$", pack, re.M)}
    assert len(dims) >= 10, f"found {len(dims)} numbered dimensions: check the heading pattern"
    # "§5 Backend" and "(§6's activation event)" both name their dimension
    refs = re.findall(r"§(\d+)(?:'s)?\s+([A-Za-z]+)", pack)
    assert len(refs) >= 5, f"found only {len(refs)} §N references: check the pattern"
    wrong = [
        f"§{n} {word} (dimension {n} is {dims.get(int(n), 'missing')})"
        for n, word in refs
        if word.lower() not in dims.get(int(n), "").lower()
    ]
    assert not wrong, f"references that name another dimension: {wrong}"


def test_pack_copies_no_price_or_rate() -> None:
    pack = _pack()
    prices = re.findall(r"\$\s?\d", pack)
    assert not prices, f"the pack copies a price ({prices}): cite 70/89 or the vendor page"
    rates = sorted(set(re.findall(r"\d+(?:\.\d+)?%", pack)))
    assert not rates, f"the pack copies a rate ({rates}): cite 70/85 instead"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "owned by **`70-chrome-ext.md` § Distribution Model** and",
            [("70-chrome-ext.md", "Distribution Model")],
        ),
        (
            "see `70-chrome-ext.md` § Build Tooling). Ship",
            [("70-chrome-ext.md", "Build Tooling")],
        ),
        (
            "owned by `core/85-payments-billing.md` § Payment Providers; the launch gate",
            [("85-payments-billing.md", "Payment Providers")],
        ),
        (
            "follows `70-chrome-ext.md` § Auth (Extension ↔ Backend). The",
            [("70-chrome-ext.md", "Auth (Extension ↔ Backend)")],
        ),
        (
            "(own work, per `89-extension-launch-checklist.md` § 3. Store listing assets) · next",
            [("89-extension-launch-checklist.md", "3. Store listing assets")],
        ),
        (
            "Gate on the server, per `core/35-security-auth.md`.",
            [],
        ),
    ],
)
def test_cite_parser_reads_every_spelling(text: str, expected: list[tuple[str, str]]) -> None:
    assert _section_cites(text) == expected
