"""GPU rental reaper — drift detection + optional auto-destroy.

Library function consumed by ``fabrik gpu reconcile``. Phase 1 ships this as
operator-invoked (no daemon); Phase 4 wraps it in a systemd user timer.

The reaper is tag-scoped: it ONLY destroys resources carrying the
``FABRIK_SESSION_ID`` env tag. Foreign pods on the operator's accounts
(manually created, other projects) are NEVER touched. Constraint C4 of the
plan.

**Multi-provider** (verified 2026-06-16 across RunPod / Modal / Vast.ai):
``reap_all_providers()`` iterates each configured provider, runs the
tag-scoped reconcile, merges results. Per-provider failures (e.g. Modal
token missing) downgrade to a per-provider error entry rather than
aborting the whole reconcile.

Returns a single dict so the CLI can present it neatly + the JSONL audit
log gets one row per reaper invocation.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fabrik.drivers.runpod import RunPodClient, RunPodError
from fabrik.orchestrator import gpu_rent, gpu_state

logger = logging.getLogger(__name__)

# Providers the reaper walks in ``reap_all_providers()``. Order matters
# only for the log readability — destroy decisions are per-provider.
REAPER_PROVIDERS = ("runpod", "modal", "vast")


def reap_all_providers(*, auto_destroy: bool = False) -> dict[str, Any]:
    """Walk state + every configured provider; merge into a single report.

    Skips a provider gracefully if its client can't be constructed (e.g.
    Modal token not set). Each provider gets a per-provider sub-report under
    ``report["providers"][<name>]`` plus the categories are merged top-level
    for back-compat with the single-provider call shape.
    """
    now = datetime.now(UTC)
    merged: dict[str, Any] = {
        "scanned_at": now.isoformat(),
        "in_state_not_live": [],
        "lifetime_exceeded": [],
        "destroy_pending": [],
        "orphan_pods": [],
        "orphan_endpoints": [],
        "foreign_count": 0,
        "auto_destroy": auto_destroy,
        "destroyed": [],
        "errors": [],
        "providers": {},
    }
    for provider in REAPER_PROVIDERS:
        try:
            client = gpu_rent.client_for_provider(provider)
        except Exception as e:  # noqa: BLE001
            # Most common: missing token in .env.sysadmin. Don't abort —
            # report and continue. The operator may not have all 3 wired.
            logger.info("reaper skipping provider %s: %s", provider, e)
            merged["providers"][provider] = {
                "skipped": True,
                "reason": f"client init failed: {e}",
            }
            continue
        try:
            sub = reap(client, auto_destroy=auto_destroy, provider_label=provider)
        except Exception as e:  # noqa: BLE001
            logger.exception("reaper failed for provider %s", provider)
            merged["providers"][provider] = {
                "skipped": False,
                "error": repr(e),
            }
            merged["errors"].append({"provider": provider, "error": repr(e)})
            continue
        merged["providers"][provider] = sub
        # Merge category counts into the top-level for back-compat
        for key in (
            "in_state_not_live",
            "lifetime_exceeded",
            "destroy_pending",
            "orphan_pods",
            "orphan_endpoints",
            "destroyed",
            "errors",
        ):
            for entry in sub.get(key, []):
                # Tag with provider so the operator can see WHICH provider
                # owns each drift entry.
                if isinstance(entry, dict) and "provider" not in entry:
                    entry["provider"] = provider
                merged[key].append(entry)
        merged["foreign_count"] += sub.get("foreign_count", 0)
    return merged


def reap(
    client: Any = None,
    *,
    auto_destroy: bool = False,
    provider_label: str = "runpod",
) -> dict[str, Any]:
    """Walk state + provider. Report drift. Optionally destroy.

    Drift categories surfaced (from :func:`gpu_state.reconcile`):

    - ``lifetime_exceeded`` — past ``max_lifetime_hours``
    - ``orphan_pods`` / ``orphan_endpoints`` — alive on RunPod with our
      ``FABRIK_SESSION_ID`` env, no matching active session here
    - ``destroy_pending`` — previous destroy attempt failed; retry
    - ``in_state_not_live`` — state says active, RunPod says missing
      (someone destroyed it outside of Fabrik)
    - ``foreign_count`` — non-Fabrik pods on the account (NEVER touched)

    With ``auto_destroy=True``, destroys everything in the first three
    categories (NOT in_state_not_live — that's just an informational drift).
    Returns the same dict shape regardless of auto_destroy, with
    ``destroyed`` + ``errors`` populated when auto_destroy was set.
    """
    client = client or RunPodClient()
    # Pass provider_label so reconcile only flags sessions belonging to
    # this provider as in_state_not_live (multi-provider safety).
    report = gpu_state.reconcile(client, provider=provider_label)
    report["auto_destroy"] = auto_destroy
    report["provider"] = provider_label
    report["destroyed"] = []
    report["errors"] = []

    if not auto_destroy:
        return report

    # Combine the categories the reaper will destroy
    to_kill: list[dict[str, str]] = []
    for entry in report["lifetime_exceeded"]:
        to_kill.append(entry)
    for entry in report["orphan_pods"]:
        to_kill.append(
            {
                "type": "pod",
                "resource_id": entry["resource_id"],
                "session_id": entry["fabrik_session_id"],
            }
        )
    for entry in report["orphan_endpoints"]:
        to_kill.append(
            {
                "type": "endpoint",
                "resource_id": entry["resource_id"],
                "session_id": entry["fabrik_session_id"],
            }
        )
    for entry in report["destroy_pending"]:
        to_kill.append(entry)

    # Dedup by (type, resource_id) — an orphan can also be lifetime_exceeded
    seen: set[tuple[str, str]] = set()
    unique_targets: list[dict[str, str]] = []
    for t in to_kill:
        key = (t.get("type") or "pod", t["resource_id"])
        if key in seen:
            continue
        seen.add(key)
        unique_targets.append(t)

    for target in unique_targets:
        rtype = target.get("type") or "pod"
        rid = target["resource_id"]
        sid = target.get("session_id")
        try:
            if rtype == "pod":
                client.destroy_pod(rid)
            elif rtype == "endpoint":
                client.destroy_endpoint(rid)
            else:
                report["errors"].append({"resource_id": rid, "error": f"unknown type {rtype}"})
                continue
            if sid:
                try:
                    gpu_state.mark_destroyed(sid)
                except Exception as e:
                    logger.warning("reaper: state mark_destroyed failed for %s: %s", sid, e)
            report["destroyed"].append(target)
        except RunPodError as e:
            report["errors"].append(
                {
                    "resource_id": rid,
                    "type": rtype,
                    "session_id": sid,
                    "error": str(e),
                }
            )

    # Write a single audit-log line for the reaper run
    now = datetime.now(UTC)
    gpu_rent.write_report(
        {
            "ts": int(now.timestamp()),
            "ts_iso": now.isoformat(),
            "session_id": f"reaper-{now.strftime('%Y%m%d-%H%M%S')}",
            "kind": "reaper",
            "workload": "reconcile",
            "provider": "runpod",
            "success": len(report["errors"]) == 0,
            "checks": {
                "lifetime_exceeded": len(report["lifetime_exceeded"]),
                "orphan_pods": len(report["orphan_pods"]),
                "orphan_endpoints": len(report["orphan_endpoints"]),
                "destroy_pending": len(report["destroy_pending"]),
                "in_state_not_live": len(report["in_state_not_live"]),
                "foreign_count": report["foreign_count"],
                "destroyed": len(report["destroyed"]),
                "errors": len(report["errors"]),
            },
            "error": None
            if not report["errors"]
            else "; ".join(
                f"{e.get('resource_id')}: {e.get('error')}" for e in report["errors"][:3]
            ),
        }
    )

    return report
