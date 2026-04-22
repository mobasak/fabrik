#!/usr/bin/env python3
"""Weekly drift audit for Authelia gating on admin dashboards.

Plan §8 acceptance criterion (``docs/development/plans/2026-04-18-zero-
touch-deployment.md:2088``):

    scripts/audit_authelia_gates.py weekly cron prints 7 OK lines, 0 GAP
    lines against the current admin-dashboard inventory. Any GAP →
    Alertmanager → Telegram alert (§8).

Why this script exists
----------------------
``LESSONS_LEARNT.md §8.9``: an Authelia ``access_control`` rule in
``/opt/authelia/config/configuration.yml`` is only enforced when Traefik
attaches the ``authelia-forward@docker`` middleware to the corresponding
router. Policy alone is not enforcement. The GlitchTip incident
(2026-04-18) — ``errors.vps1.ocoron.com`` publicly reachable despite a
``two_factor`` policy — demonstrated that the two sides can silently
drift apart. Coolify's runtime auto-inject makes this WORSE because a
compose PATCH can erase labels Coolify was quietly maintaining at boot.

This script hits the live Traefik API over SSH and verifies that every
router backing an admin dashboard matches the canonical inventory. It's
designed for a weekly systemd timer piping exit-1 output into
Alertmanager → Telegram. Any GAP is a potential 2FA-bypass bug.

The canonical inventory (7 hosts)
---------------------------------
6 services EXPECTED to carry ``authelia-forward@docker``:
  auto (n8n) · backup (Backrest) · coolify (Coolify UI) · monitor
  (Grafana) · netdata · notify (Apprise)

1 service EXPECTED to NOT carry it (app-layer auth per §8.13):
  errors (GlitchTip — django-allauth native TOTP)

The second bucket is just as important as the first. Accidentally
adding ``authelia-forward@docker`` to errors/GlitchTip causes double-
auth and breaks the app. The audit flags drift in BOTH directions.

Exit codes
----------
0 — all 7 dashboards match expectation (prints 7 OK lines)
1 — at least one dashboard drifted (GAP or MISSING) — cron MUST alert
2 — operational error (SSH unreachable, malformed JSON, etc.)

Invocation
----------
    # Run full audit (the usual invocation; pipe to `mail` / Alertmanager):
    python scripts/audit_authelia_gates.py

    # Print the canonical inventory without touching the VPS:
    python scripts/audit_authelia_gates.py --inventory

    # Override the Traefik API URL (for debugging; default works on VPS):
    python scripts/audit_authelia_gates.py --api-url http://127.0.0.1:8080/api/http/routers
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# The SSH helper lives in the Fabrik tree; the script runs with PYTHONPATH
# pointing at /opt/fabrik/src when installed. For ad-hoc runs (e.g.
# ``python scripts/audit_authelia_gates.py``) we prepend the src path so
# import works without an install step.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if (_REPO_ROOT / "src").is_dir() and str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from fabrik.drivers.ssh import ssh  # noqa: E402 — deliberate late import after sys.path edit

DEFAULT_TRAEFIK_API_URL = "http://127.0.0.1:8080/api/http/routers"

# --------------------------------------------------------------------------- #
# Canonical inventory
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Dashboard:
    """One admin-dashboard entry in the canonical inventory.

    Attributes:
        host: Subdomain prefix under ``vps1.ocoron.com`` (e.g. ``auto``).
            Match is substring (``{host}.vps1``) so the audit works
            regardless of whether the Traefik rule uses ``Host(...)``,
            ``HostRegexp(...)``, or any other matcher shape.
        service: Display label of the backing service. Informational only
            — the audit does not verify backend identity.
        authelia_expected: True → expect ``authelia-forward@docker``
            (or any ``authelia*`` middleware) on the router. False →
            expect NO authelia middleware; the service handles auth at
            the app layer (e.g. GlitchTip's django-allauth, §8.13).
        rationale: Short explanation printed in the OK/GAP line for
            operators. Spells out WHY a given expectation is set so an
            on-call engineer doesn't have to re-derive the policy.
    """

    host: str
    service: str
    authelia_expected: bool
    rationale: str


# Ordered alphabetically by host so cron output is grep-friendly and
# diff-stable. The count here MUST stay at 7 for the plan's "7 OK lines"
# acceptance criterion to make sense; any addition/removal is a policy
# change that needs a plan-doc update and new tests.
ADMIN_DASHBOARDS: tuple[Dashboard, ...] = (
    Dashboard(
        host="auto",
        service="n8n",
        authelia_expected=True,
        rationale="two_factor — no native auth",
    ),
    Dashboard(
        host="backup",
        service="Backrest",
        authelia_expected=True,
        rationale="two_factor — Backrest UI has no built-in auth",
    ),
    Dashboard(
        host="coolify",
        service="Coolify UI",
        authelia_expected=True,
        rationale="two_factor + ^/api/ bypass (§8.11)",
    ),
    Dashboard(
        host="errors",
        service="GlitchTip",
        authelia_expected=False,
        rationale="app-layer django-allauth TOTP — NO forward-auth (§8.13)",
    ),
    Dashboard(
        host="monitor",
        service="Grafana",
        authelia_expected=True,
        rationale="two_factor + ^/api/ bypass for annotations token",
    ),
    Dashboard(
        host="netdata",
        service="Netdata",
        authelia_expected=True,
        rationale="two_factor — Netdata has no native auth",
    ),
    Dashboard(
        host="notify",
        service="Apprise",
        authelia_expected=True,
        rationale="two_factor — Apprise has no native auth",
    ),
)
assert len(ADMIN_DASHBOARDS) == 7, (
    "Canonical inventory size changed — update plan §8 acceptance criterion"
)


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AuditResult:
    """Outcome of one dashboard check.

    Attributes:
        host: Dashboard host prefix (``auto``, ``coolify``, ...).
        state: ``"OK"``, ``"GAP"``, or ``"MISSING"``.
        reason: Human-readable rationale used in the printed report.
        middlewares: The middleware list seen on the router (or empty
            for MISSING / no-middleware). Included in output so an
            operator can see what drifted without SSH'ing in.
    """

    host: str
    state: str  # "OK" | "GAP" | "MISSING"
    reason: str
    middlewares: list[str]


def _router_matches_host(router: dict[str, Any], host: str) -> bool:
    """Return True if the router's rule targets ``{host}.vps1.ocoron.com``.

    Substring match on ``{host}.vps1`` — works for ``Host(`x.vps1...`)``,
    ``HostRegexp(...)``, PathPrefix combinations, etc. The risk of a
    false positive (e.g. a rule that mentions ``auto.vps1`` in a
    non-host context) is vanishingly small since Traefik rules are
    structured, not free-form."""
    rule = router.get("rule", "") or ""
    return f"{host}.vps1" in rule


def _has_authelia_middleware(router: dict[str, Any]) -> tuple[bool, list[str]]:
    """Permissive authelia-middleware detection.

    Any middleware with ``authelia`` in the name counts. Variant-
    tolerant on purpose — Traefik middleware names include provider
    suffix (``@docker``, ``@file``, ``@kubernetescrd``) and the
    Fabrik/Coolify conventions may not be the only provider in play.
    See LESSONS_LEARNT §8.9 for the original audit snippet using the
    same ``'authelia' in m`` match."""
    mws = router.get("middlewares") or []
    if not isinstance(mws, list):
        return (False, [])
    has = any(isinstance(m, str) and "authelia" in m.lower() for m in mws)
    return (has, [m for m in mws if isinstance(m, str)])


def classify_router(dash: Dashboard, router: dict[str, Any]) -> AuditResult:
    """Compare one router's actual state to the dashboard's expectation.

    Called once per (dashboard, router) pair after :func:`audit_routers`
    has matched them by host. Pure function — no IO, deterministic.
    """
    has_authelia, middlewares = _has_authelia_middleware(router)

    if dash.authelia_expected:
        if has_authelia:
            return AuditResult(
                host=dash.host,
                state="OK",
                reason=f"authelia middleware present ({dash.rationale})",
                middlewares=middlewares,
            )
        return AuditResult(
            host=dash.host,
            state="GAP",
            reason=(
                f"expected authelia-forward middleware is missing — "
                f"{dash.service} unprotected despite policy ({dash.rationale})"
            ),
            middlewares=middlewares,
        )

    # authelia_expected is False — app-layer auth case.
    if has_authelia:
        return AuditResult(
            host=dash.host,
            state="GAP",
            reason=(
                f"unexpected authelia middleware present — "
                f"{dash.service} uses app-layer auth and will double-auth "
                f"({dash.rationale})"
            ),
            middlewares=middlewares,
        )
    return AuditResult(
        host=dash.host,
        state="OK",
        reason=f"no authelia middleware as expected ({dash.rationale})",
        middlewares=middlewares,
    )


def audit_routers(routers: list[dict[str, Any]]) -> list[AuditResult]:
    """Audit the full list of Traefik routers against the canonical inventory.

    Output order follows :data:`ADMIN_DASHBOARDS` (alphabetical by host),
    NOT the order Traefik happens to return. Stable order makes the cron
    output diff-friendly week-to-week.
    """
    results: list[AuditResult] = []
    for dash in ADMIN_DASHBOARDS:
        matches = [r for r in routers if _router_matches_host(r, dash.host)]
        if not matches:
            results.append(
                AuditResult(
                    host=dash.host,
                    state="MISSING",
                    reason=(
                        f"no Traefik router found for {dash.host}.vps1.ocoron.com — "
                        f"{dash.service} is not reachable or the router was removed"
                    ),
                    middlewares=[],
                )
            )
            continue
        # If multiple routers match the host (rare — multi-router apps
        # like WordPress apex+www), we care about the one that would
        # gate ``/`` on the apex. Heuristic: pick the router whose
        # middlewares include authelia (indicating a gate), else the
        # first match. Good enough — the audit's purpose is drift
        # detection, not formal-verification.
        chosen = next(
            (r for r in matches if _has_authelia_middleware(r)[0]),
            matches[0],
        )
        results.append(classify_router(dash, chosen))
    return results


# --------------------------------------------------------------------------- #
# CLI / orchestration
# --------------------------------------------------------------------------- #


def _fetch_routers(api_url: str) -> list[dict[str, Any]]:
    """SSH to the VPS, curl the Traefik API, parse the JSON.

    Raises:
        RuntimeError: SSH failed (propagated from ``fabrik.drivers.ssh``).
        ValueError: Traefik returned non-JSON or a non-list payload.
    """
    raw = ssh(f"curl -fsS {api_url}", timeout=30)
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError(f"Traefik API returned {type(data).__name__}, expected list")
    return data


def _print_report(results: list[AuditResult]) -> None:
    """Emit one line per dashboard plus a compact summary footer.

    Line format (deliberately simple for grep / awk):

        OK    <host>   <middlewares>   <reason>
        GAP   <host>   <middlewares>   <reason>
        MISSING <host> (not in Traefik) <reason>

    Summary footer lets an Alertmanager webhook receiver emit a
    one-liner Telegram message without re-parsing the detail lines.
    """
    for r in results:
        mws_display = ",".join(r.middlewares) if r.middlewares else "-"
        print(f"{r.state:<7} {r.host:<8} middlewares=[{mws_display}]  {r.reason}")

    ok = sum(1 for r in results if r.state == "OK")
    gap = sum(1 for r in results if r.state == "GAP")
    missing = sum(1 for r in results if r.state == "MISSING")
    print(
        f"\nSUMMARY: {ok} OK, {gap} GAP, {missing} MISSING "
        f"(inventory size: {len(ADMIN_DASHBOARDS)})"
    )


def _print_inventory() -> None:
    """Dump the canonical inventory without touching the VPS.

    Useful for CI assertions and for cross-referencing against
    ``docs/infrastructure/vps-complete-inventory.md`` during reviews."""
    print("Canonical admin-dashboard inventory (source of truth for the audit):")
    print()
    for d in ADMIN_DASHBOARDS:
        marker = "authelia-forward" if d.authelia_expected else "NO middleware (app-auth)"
        print(f"  {d.host:<8} {d.service:<12} expect: {marker}")
        print(f"           rationale: {d.rationale}")
    print()
    print(f"Total: {len(ADMIN_DASHBOARDS)} dashboards")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit Authelia gating on admin dashboards. Verifies that every "
            "dashboard in the canonical inventory has the correct Traefik "
            "middleware state. Exit 0 on all-OK, 1 on any drift, 2 on "
            "operational error (SSH unreachable, malformed response, etc.)."
        ),
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_TRAEFIK_API_URL,
        help=(
            "Traefik dynamic-routers API URL reachable from the VPS "
            f"(default: {DEFAULT_TRAEFIK_API_URL})"
        ),
    )
    parser.add_argument(
        "--inventory",
        action="store_true",
        help="Print the canonical inventory and exit without touching the VPS.",
    )
    args = parser.parse_args(argv)

    if args.inventory:
        _print_inventory()
        return 0

    try:
        routers = _fetch_routers(args.api_url)
    except RuntimeError as e:
        # SSH failure — operational, not policy drift.
        print(f"ERROR: SSH to VPS failed: {e}", file=sys.stderr)
        return 2
    except (ValueError, json.JSONDecodeError) as e:
        print(f"ERROR: Traefik API response unreadable: {e}", file=sys.stderr)
        return 2

    results = audit_routers(routers)
    _print_report(results)

    any_drift = any(r.state != "OK" for r in results)
    return 1 if any_drift else 0


if __name__ == "__main__":
    sys.exit(main())
