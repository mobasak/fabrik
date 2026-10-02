# AFTER-EDIT: docs/reference/health-monitoring.md
"""Hourly reconcile of the postgres allocation registry (plan-2, D-498/D-500).

The hourly drift cron (``scripts/audit_all_registrars.py``) audits every spec.
A postgres result of ``drift`` with the database present and no
``allocations.json`` entry is an unregistered database: created outside
``create_database``'s CREATE path, or one whose registration failed at create
time. This module registers it — additively, inside the registry lock, never
overwriting or deleting an entry — and reports every outcome so a failure is
surfaced, never swallowed.

Safety:

- Default mode is ``report`` (``FABRIK_REGISTRY_RECONCILE``): nothing writes
  until the operator sets ``apply``.
- A database claimed by two or more specs is ``shared`` and never written; when
  the claim map is incomplete (a spec failed to load or audit, or a database
  spec's name failed to resolve) every candidate is ``failed`` with
  ``claims-unresolved`` — the provisioner refuses to guess in the same case.
- The owner role is read from ``pg_database``; no owner, no write.

Cobra check (D-253): the cheapest way to zero ``FabrikRegistrarDrift`` without
the outcome is to register every orphan blindly. The ``shared`` and
``claims-unresolved`` refusals and the owner read are the counter-measure, and
every refusal is a ``fabrik_registry_heal_failed`` or ``shared`` series, not a
silent skip.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from fabrik.app_role_check import _db_name_for_spec
from fabrik.audit import AuditResult, _resolved_for, _spec_id, _spec_to_dict
from fabrik.drivers.postgres import (
    POSTGRES_CONTAINER,
    _db_owner,
    _validate_identifier,
    register_allocation_if_absent,
)

logger = logging.getLogger(__name__)

Mode = Literal["apply", "report", "off"]
Outcome = Literal["registered", "already-present", "would-register", "shared", "failed"]
_MODES: tuple[Mode, ...] = ("apply", "report", "off")


@dataclass
class HealResult:
    spec_id: str
    db: str
    outcome: Outcome
    reason: str = ""


def mode() -> Mode:
    """``FABRIK_REGISTRY_RECONCILE``: ``apply`` writes, ``report`` (default) dry-runs,
    ``off`` skips. Any other value is ``report``, with one warning."""
    raw = os.getenv("FABRIK_REGISTRY_RECONCILE", "report")
    for m in _MODES:
        if raw == m:
            return m
    logger.warning("FABRIK_REGISTRY_RECONCILE=%r is not apply|report|off; using report", raw)
    return "report"


def claims(specs: Iterable[Any]) -> tuple[dict[str, list[str]], list[str]]:
    """Map database name -> spec ids over every spec whose postgres registrar applies,
    whatever its audit returned. Returns ``(map, unresolved)``; a spec whose name
    cannot be resolved is listed in ``unresolved``. Never raises."""
    claim_map: dict[str, list[str]] = {}
    unresolved: list[str] = []
    for spec in specs:
        sid = _spec_id(spec)
        try:
            if not _resolved_for(spec).get("postgres", (False, ""))[0]:
                continue
            db = _db_name_for_spec(_spec_to_dict(spec))
        except Exception as exc:  # noqa: BLE001 — an unresolvable spec is reported, never raised
            logger.warning("registry reconcile: cannot resolve the database of %s (%s)", sid, exc)
            unresolved.append(sid)
            continue
        claim_map.setdefault(db, []).append(sid)
    return claim_map, unresolved


def reconcile_postgres(
    audits: dict[str, dict[str, AuditResult]],
    claims: dict[str, list[str]],
    *,
    claims_complete: bool,
    dry_run: bool,
) -> list[HealResult]:
    """Register every unregistered database the audit found; one result per candidate."""
    results: list[HealResult] = []
    for spec_id, per_registrar in audits.items():
        result = per_registrar.get("postgres")
        if result is None or result.status != "drift":
            continue
        actual = result.actual or {}
        if actual.get("found") is not True or actual.get("in_registry") is not False:
            continue
        heal = _heal(spec_id, str(actual.get("db_name")), claims, claims_complete, dry_run)
        logger.info(
            "registry reconcile: spec=%s db=%s outcome=%s%s",
            heal.spec_id,
            heal.db,
            heal.outcome,
            f" reason={heal.reason}" if heal.reason else "",
        )
        results.append(heal)
    return results


def _heal(
    spec_id: str, db: str, claims: dict[str, list[str]], claims_complete: bool, dry_run: bool
) -> HealResult:
    if not claims_complete:
        return HealResult(spec_id, db, "failed", "claims-unresolved")
    others = sorted(set(claims.get(db, [])) - {spec_id})
    if others:
        return HealResult(spec_id, db, "shared", ",".join(others))
    if dry_run:
        return HealResult(spec_id, db, "would-register")
    try:
        _validate_identifier(db, "database")
        user = _db_owner(db, POSTGRES_CONTAINER)
        if user is None:
            return HealResult(spec_id, db, "failed", "owner-unresolved")
        wrote = register_allocation_if_absent(
            db,
            spec_id=spec_id,
            user=user,
            owner="fabrik",
            notes="registered by the hourly reconcile " + datetime.now(UTC).date().isoformat(),
        )
    except Exception as exc:  # noqa: BLE001 — a failed heal is a counted outcome, never a crash
        return HealResult(spec_id, db, "failed", type(exc).__name__)
    return HealResult(spec_id, db, "registered" if wrote else "already-present")
