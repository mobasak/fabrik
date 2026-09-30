"""Pins `mobile-app/81-mobile-billing.md` — the code agents copy from it, and the scaffold fact it warns about.

Agents follow this pack's webhook and client samples verbatim, so a regression in a sample ships to every
mobile repo. Three things can go false without any other gate turning red:

1. The webhook sample: it must parse, compare the Authorization header verbatim against a required Settings
   field (a missing secret must stop the app, not become "Bearer None"), dedupe on the event id, and re-read the
   customer instead of branching on the type.
2. The client sample: one public RevenueCat key per platform, `configure()` not awaited.
3. The scaffold's single `EXPO_PUBLIC_REVENUECAT_API_KEY` slot, which the pack tells agents to split — when the
   template ships two keys this goes red and the pack's warning is removed in the same change.

The cheapest way to satisfy (1) without the outcome is a sample that names `record_event_once` but never calls
it before the state write; the order check below reads the call sequence, not the names.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

from fabrik.scaffold import create_project

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / ".windsurf" / "rules" / "mobile-app" / "81-mobile-billing.md"

requires_fabrik_env = pytest.mark.skipif(
    not (ROOT / "templates" / "mobile-app").is_dir(),
    reason="needs the hub's templates/mobile-app",
)


def _blocks(lang: str) -> list[str]:
    return re.findall(rf"```{lang}\n(.*?)```", PACK.read_text(encoding="utf-8"), re.S)


def _webhook() -> ast.AsyncFunctionDef:
    tree = ast.parse(_blocks("python")[0])
    return next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef))


def _calls_in_order(fn: ast.AST) -> list[str]:
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
    calls.sort(key=lambda n: (n.lineno, n.col_offset))
    return [ast.unparse(n.func) for n in calls]


def test_webhook_reads_the_secret_so_a_missing_one_fails() -> None:
    src = ast.unparse(_webhook())
    assert "settings.revenuecat_webhook_auth" in src
    assert "getenv" not in src and "Bearer" not in src, (
        "RevenueCat sends the configured value verbatim; os.getenv turns a missing secret into 'Bearer None'"
    )
    assert "hmac.compare_digest" in src


def test_webhook_dedupes_before_it_writes_state() -> None:
    order = _calls_in_order(_webhook())
    assert "record_event_once" in order and "sync_entitlements" in order
    assert order.index("record_event_once") < order.index("sync_entitlements"), (
        "the event id must be recorded before any state is written — delivery is at-least-once"
    )


def test_webhook_never_branches_on_the_event_type_for_state() -> None:
    fn = _webhook()
    compared = [
        ast.unparse(n)
        for n in ast.walk(fn)
        if isinstance(n, ast.Compare) and "type" in ast.unparse(n.left)
    ]
    assert compared == ["event['type'] == 'TEST'"], (
        f"state must come from the re-read, not the event type; found {compared}"
    )


def test_client_sample_uses_one_key_per_platform_and_does_not_await_configure() -> None:
    ts = _blocks("typescript")[0]
    assert "EXPO_PUBLIC_REVENUECAT_IOS_KEY" in ts and "EXPO_PUBLIC_REVENUECAT_ANDROID_KEY" in ts
    assert "await Purchases.configure" not in ts
    assert "Purchases.logIn(" in ts


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("mobile-billing")
    os.environ.setdefault("FABRIK_ROOT", str(ROOT))
    create_project(
        "mobilebilling", "probe", base=base, project_type="mobile-app", generate_spec=False
    )
    return base / "mobilebilling"


@requires_fabrik_env
def test_scaffold_still_ships_one_revenuecat_key_slot(project: Path) -> None:
    env = (project / ".env.example").read_text(encoding="utf-8")
    keys = re.findall(r"^(EXPO_PUBLIC_REVENUECAT\w*)=", env, re.M)
    assert keys == ["EXPO_PUBLIC_REVENUECAT_API_KEY"], (
        f"the scaffold now ships {keys}: drop the pack's 'split the single key' note"
    )
    assert "`EXPO_PUBLIC_REVENUECAT_API_KEY`" in PACK.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "heading",
    [
        "## Turkey: Store Billing Is Mandatory",
        "## Store Fee Enrollment",
        "## Teknokent Tax Treatment",
    ],
)
def test_sections_other_packs_cite_exist(heading: str) -> None:
    lines = PACK.read_text(encoding="utf-8").splitlines()
    assert any(ln.startswith(heading) for ln in lines), (
        f"{heading!r} is cited by 00-domain-mobile-app.md and 89-mobile-launch-checklist.md"
    )
