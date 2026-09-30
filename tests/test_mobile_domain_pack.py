"""Pins `mobile-app/00-domain-mobile-app.md` to the scaffold it plans for and to its own ONE RULE.

The pack is `activation: manual`, so no glob check ever reads it; it is loaded by path at vision intake.
Three things it states can go false without any other gate turning red:

1. What the mobile-app scaffold emits as its backend — a same-repo `server/` FastAPI service with no
   database and no auth by default, serving `/app-config` through the vendored `mobile_config`.
2. Every `<sibling pack>.md § <section>` it cites — a renamed section in 80/81/89 leaves a dangling
   pointer at intake (the pack's earlier Traycer consumers and sibling line cites both rotted this way).
3. Its ONE RULE — no copied value: no dollar amount and no percentage (fees, curves and targets live in 81/89).

The cheapest way to satisfy (3) without the outcome is to write a price in words ("two hundred dollars");
the check catches the shape agents actually copy from a vendor page (`$200`, `15%`), and the pack's
review is what catches the rest.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from fabrik.scaffold import create_project

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
PACK = RULES / "mobile-app" / "00-domain-mobile-app.md"

requires_fabrik_env = pytest.mark.skipif(
    not (ROOT / "templates" / "mobile-app").is_dir(),
    reason="needs the hub's templates/mobile-app",
)


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("mobile-domain")
    os.environ.setdefault("FABRIK_ROOT", str(ROOT))
    create_project(
        "mobiledomain", "probe", base=base, project_type="mobile-app", generate_spec=False
    )
    return base / "mobiledomain"


def _pack() -> str:
    return PACK.read_text(encoding="utf-8")


def _headings(pack_path: Path) -> list[str]:
    return [
        ln.lstrip("#").strip()
        for ln in pack_path.read_text(encoding="utf-8").splitlines()
        if ln.startswith("#")
    ]


# `80-mobile.md` § A, B + § C — a pack name, then one or more `§` groups of comma-separated section
# prefixes, ending at the first character that cannot belong to a heading.
_CITE = re.compile(
    r"`(?:\.windsurf/rules/)?(?:[a-z-]+/)?(\d\d-[a-z0-9-]+\.md)`((?:\s*\+?\s*§ [^.;:*()—`]+)+)"
)


def _section_cites(text: str) -> list[tuple[str, str]]:
    cites = []
    for m in _CITE.finditer(text):
        for group in re.findall(r"§ ([^§+]+)", m.group(2)):
            for part in group.split(","):
                part = re.sub(r"\s+(?:and|or)$", "", part.strip())
                if not part[
                    :1
                ].isupper():  # headings are capitalised; lowercase is the prose resuming
                    break
                cites.append((m.group(1), part))
    return cites


@requires_fabrik_env
def test_scaffold_backend_is_the_repo_server(project: Path) -> None:
    main = (project / "server" / "src" / "app" / "main.py").read_text(encoding="utf-8")
    assert "app_config" in main, (
        "server/ no longer serves /app-config: update the pack's §4 Backend"
    )
    assert (project / "server" / "src" / "mobile_config").is_dir()
    assert "`server/`" in _pack()


@requires_fabrik_env
def test_scaffold_backend_ships_with_no_db_and_no_auth() -> None:
    defaults = (ROOT / "templates" / "mobile-app" / "defaults.yaml").read_text(encoding="utf-8")
    for flag in ("needs_database", "has_bearer_api"):
        assert re.search(rf"^\s*{flag}:\s*false\s*$", defaults, re.M), (
            f"{flag} is no longer false by default: update the pack's 'no database and no auth'"
        )
    assert "no database and no auth" in _pack()


def test_every_cited_sibling_section_exists() -> None:
    cites = _section_cites(_pack())
    assert len(cites) >= 10, f"the cite parser found only {len(cites)} cites: check _CITE"
    missing = []
    for pack_name, section in cites:
        target = next(RULES.rglob(pack_name), None)
        heads = _headings(target) if target else []
        # a cite may shorten a heading ("Lists") or run on into prose ("App Identity owns the setup")
        if not any(h.startswith(section) or section.startswith(h) for h in heads):
            missing.append(f"{pack_name} § {section}")
    assert not missing, f"cited sections not found: {missing}"


def test_pack_copies_no_price_or_rate() -> None:
    pack = _pack()
    prices = re.findall(r"\$\s?\d", pack)
    assert not prices, f"the pack copies a price ({prices}): cite the owning pack or vendor page"
    rates = sorted(set(re.findall(r"\d+(?:\.\d+)?%", pack)))
    assert not rates, f"the pack copies a rate ({rates}): cite 81/89 instead"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "see `81-mobile-billing.md` § Store Fee Enrollment — read",
            [("81-mobile-billing.md", "Store Fee Enrollment")],
        ),
        (
            "`.windsurf/rules/mobile-app/80-mobile.md` § Lists, Styling, Accessibility.",
            [
                ("80-mobile.md", "Lists"),
                ("80-mobile.md", "Styling"),
                ("80-mobile.md", "Accessibility"),
            ],
        ),
        (
            "`89-mobile-launch-checklist.md` § Staged Rollout + § OTA Updates & Forced Upgrade. At",
            [
                ("89-mobile-launch-checklist.md", "Staged Rollout"),
                ("89-mobile-launch-checklist.md", "OTA Updates & Forced Upgrade"),
            ],
        ),
        (
            "**`89-mobile-launch-checklist.md` § Privacy Compliance**.",
            [("89-mobile-launch-checklist.md", "Privacy Compliance")],
        ),
        ("`mobile-app/80-mobile.md` § Testing).", [("80-mobile.md", "Testing")]),
        (
            "`89-mobile-launch-checklist.md` § Beta Metrics Gates, lean bundle, no jank;",
            [("89-mobile-launch-checklist.md", "Beta Metrics Gates")],
        ),
        (
            "`89-mobile-launch-checklist.md` § App Identity owns the setup.",
            [("89-mobile-launch-checklist.md", "App Identity owns the setup")],
        ),
        (
            "`core/35-security-auth.md` § Pattern A and § Passwordless — they own it",
            [("35-security-auth.md", "Pattern A"), ("35-security-auth.md", "Passwordless")],
        ),
        (
            "`80-mobile.md` § Build & Dev Workflow and `89-mobile-launch-checklist.md` § Staged Rollout.",
            [
                ("80-mobile.md", "Build & Dev Workflow"),
                ("89-mobile-launch-checklist.md", "Staged Rollout"),
            ],
        ),
    ],
)
def test_cite_parser_reads_every_spelling(text: str, expected: list[tuple[str, str]]) -> None:
    assert _section_cites(text) == expected
