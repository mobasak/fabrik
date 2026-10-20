"""W-693ee1ca: plan-2 (merged 0a910fa46, D-464) has `fabrik apply` mint the payments fulfilment worker's own login.

Four fleet-synced pack lines still said the login did not exist. The mechanism is now stated once, in core/85's
Live-provider status bullet, and saas/95 and saas/88 point at it; each rewrite stays inside its bullet's line, so the
line numbers other docs cite (docs/CONFIGURATION.md cites core/85:27 and :28) still hold. The bullet's standing safety
sentences (PayTR off, the worker never a tenant-facing role) are pinned beside the new ones, so an edit that drops
them reds here too.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
BILLING = RULES / "core" / "85-payments-billing.md"
TENANT = RULES / "saas" / "95-multi-tenant-saas.md"
LAUNCH = RULES / "saas" / "88-saas-launch-checklist.md"


def _flat(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


def _line(path: Path, number: int) -> str:
    return path.read_text(encoding="utf-8").splitlines()[number - 1]


def test_ingest_bullet_names_the_workers_own_login() -> None:
    assert (
        "The fulfilment worker never uses this role: it has its own login, minted when"
        " `shape.needs_payments_fulfilment` is set (the Live-provider status bullet below)."
        in _line(BILLING, 28)
    )


def test_live_provider_bullet_states_what_an_apply_does() -> None:
    bullet = _line(BILLING, 45)
    for clause in (
        "⚠️ **PayTR stays OFF in production (`PAYMENTS_PAYTR_ENABLED=false`) until the fulfilment worker runs as its"
        ' OWN scoped login and boots `verify_service_role(worker_conn, lane="fulfilment")` green**',
        "On a `fabrik apply` database set `shape.needs_payments_fulfilment: true` (requires `needs_database: true`):"
        " the registrar mints `<db>_payments_fulfilment` (`LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS"
        " NOREPLICATION`, no role membership granted, and a re-apply does not revoke one added by hand), injects"
        " `PAYMENTS_FULFILMENT_DATABASE_URL` on the first mint, before granting it, and keeps it on a re-apply —"
        " never hand-set that variable — and, beyond `CONNECT` and `USAGE` on `public`, grants it only by running"
        " that function",
        "the module README § Gotchas still says the registrar does not provision it",
        "A payments schema not yet applied, in whole or in part, leaves the grant pending with a"
        " `⚠ payments-fulfilment-role: grant pending` line under the apply summary, and the run is not failed by it:"
        " re-apply after the schema lands.",
        "The apply step fails, naming the fix, when the payments tables exist but the function does not (apply the"
        " module's scoped-roles migration), when the function has another signature, when the payments tables exist"
        " but `jobs` does not, or when the function refuses (the ingest role still holds the legacy table-level"
        " grant; with both payments flags set the apply re-runs the ingest grant first). Elsewhere the owner runs"
        " the function.",
        "The worker login is never `<db>_app` or any tenant-facing role",
        "On that login your worker claims each job",
    ):
        assert clause in bullet, clause[:60]


def test_multi_tenant_pack_points_at_core_85() -> None:
    assert (
        "`shape.needs_payments_fulfilment: true` has `fabrik apply` mint that login and inject"
        " `PAYMENTS_FULFILMENT_DATABASE_URL` (`core/85` § Payment Providers, the Live-provider status bullet, which"
        " also carries the PayTR blocker)." in _line(TENANT, 151)
    )


def test_launch_checklist_conditions_paytr_on_the_worker() -> None:
    assert (
        "PayTR stays disabled in production until the project's fulfilment worker runs as its own login"
        ' (`shape.needs_payments_fulfilment`) and boots `verify_service_role(worker_conn, lane="fulfilment")` green,'
        " and with no merchant account behind it its first live transaction is the real test."
        in _line(LAUNCH, 34)
    )
    assert "settled" not in _line(LAUNCH, 34)


def test_the_stale_phrases_are_gone() -> None:
    for path in (BILLING, TENANT, LAUNCH):
        text = _flat(path)
        for phrase in (
            "does not exist yet",
            "awaiting design approval",
            "no role the registrar mints can create it",
            "Once it exists",
            "until the platform mints that login",
            "until its fulfilment write path exists",
        ):
            assert phrase not in text, f"{path.name}: {phrase}"


def test_cited_line_numbers_still_hold() -> None:
    assert _line(BILLING, 27).startswith("- **Queue:**")
    assert "SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user" in _line(
        BILLING, 28
    )
    assert _line(BILLING, 45).startswith("- **Live-provider status:**")
    assert _line(TENANT, 151).startswith("- **Cross-tenant payments ingest is not an admin case**")
    assert _line(LAUNCH, 34).startswith("- ⚠️ **Neither TRY lane can go live today**")


def test_the_node_pack_routes_turkish_one_off_charges_to_paytr() -> None:
    """W-2fd7cfd1: core/12-node said PayTR applied only to WooCommerce / physical D2C, not to Node SaaS backends,
    contradicting core/85's one-off TRY lane; its bullet and checklist now carry core/85's three lanes."""
    node = _flat(RULES / "core" / "12-node.md")
    billing = BILLING.read_text(encoding="utf-8")
    assert "**PayTR** for TR domestic one-off (TRY) charges" in node
    assert (
        "iyzico** for TRY subscriptions only where `docs/DECISIONS.md` records the decision" in node
    )
    assert (
        "PayTR TRY one-off, iyzico TRY subscriptions only under the recorded NON3D decision" in node
    )
    for stale in (
        "not to Node SaaS backends",
        "only to WooCommerce",
        "iyzico for TR SaaS, Paddle for international",
    ):
        assert stale not in node, stale
    assert node.count("`85-payments-billing.md` § Payment Providers") == 2
    assert "## Payment Providers" in billing.splitlines()
    assert "| Turkish domestic, **one-off** (TRY) | **PayTR** |" in _flat(BILLING)
    assert "TRY subscription → iyzico ONLY where `docs/DECISIONS.md` records" in _flat(BILLING)
