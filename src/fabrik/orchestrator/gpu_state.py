"""GPU rental session state.

Direct port of ``src/fabrik/orchestrator/vultr_state.py`` for GPU rentals.
State file at ``$FABRIK_ROOT/data/gpu-rent-state.json``. Writes are atomic
(tmp + ``os.replace``) under a file lock.

Schema v1:

.. code-block:: json

    {
      "schema_version": 1,
      "last_reconciled": "<ISO 8601 or null>",
      "sessions": {
        "<session_id>": {
          "provider":           "runpod",
          "kind":               "pod-h100" | "serverless" | ...,
          "workload":           "<free-text tag>",
          "resource_type":      "pod" | "endpoint",
          "resource_id":        "<RunPod pod_id or endpoint_id>",
          "gpu_type_id":        "NVIDIA H100 80GB HBM3" | null,
          "created_at":         "<ISO 8601>",
          "expires_at":         "<ISO 8601>",
          "destroyed_at":       "<ISO 8601 or null>",
          "destroy_pending":    false,
          "max_lifetime_hours": 4,
          "cost_estimate_usd":  12.0,
          "cost_actual_usd":    null
        }
      }
    }

A session whose ``destroyed_at`` is ``null`` AND ``destroy_pending`` is
``false`` is "active". A session whose ``destroy_pending`` is ``true``
needs the reaper to retry the destroy call.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fabrik.config import FABRIK_ROOT
from fabrik.locks_local import file_lock

logger = logging.getLogger(__name__)

STATE_FILE = FABRIK_ROOT / "data" / "gpu-rent-state.json"
SCHEMA_VERSION = 1
_LOCK = "gpu-rent-state"
RETENTION_DAYS = 30  # match vultr_state.DISPOSABLE_RETENTION_DAYS


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _empty() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "last_reconciled": None,
        "sessions": {},
    }


def load_state() -> dict[str, Any]:
    """Read the state file. Returns the empty skeleton if missing/corrupt."""
    if not STATE_FILE.exists():
        return _empty()
    try:
        data = json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("gpu_state: corrupt or unreadable state file (%s) — using empty", e)
        return _empty()
    # Forward-compat: if schema version is newer than we know, just trust it.
    if "sessions" not in data:
        data["sessions"] = {}
    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("last_reconciled", None)
    return data


def _write_unlocked(state: dict[str, Any]) -> Path:
    """Write the state atomically. Caller must hold the lock."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".gpu-rent-state.", dir=str(STATE_FILE.parent))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2, sort_keys=True)
        os.replace(tmp_path, STATE_FILE)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    return STATE_FILE


def save_state(state: dict[str, Any]) -> Path:
    """Write under the file lock."""
    with file_lock(_LOCK, timeout_seconds=15.0):
        return _write_unlocked(state)


def upsert(
    session_id: str,
    *,
    provider: str,
    kind: str,
    workload: str,
    resource_type: str,  # "pod" or "endpoint"
    resource_id: str,
    gpu_type_id: str | None,
    max_lifetime_hours: int,
    cost_estimate_usd: float,
) -> dict[str, Any]:
    """Record a newly-created GPU session.

    Returns the new session record.
    """
    now = datetime.now(UTC)
    expires = now + timedelta(hours=max_lifetime_hours)
    record = {
        "provider": provider,
        "kind": kind,
        "workload": workload,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "gpu_type_id": gpu_type_id,
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "destroyed_at": None,
        "destroy_pending": False,
        "max_lifetime_hours": max_lifetime_hours,
        "cost_estimate_usd": cost_estimate_usd,
        "cost_actual_usd": None,
    }
    with file_lock(_LOCK, timeout_seconds=15.0):
        state = load_state()
        state["sessions"][session_id] = record
        _write_unlocked(state)
    return record


def mark_destroyed(
    session_id: str,
    *,
    when: str | None = None,
    cost_actual_usd: float | None = None,
) -> None:
    """Mark a session destroyed and clear any pending flag."""
    with file_lock(_LOCK, timeout_seconds=15.0):
        state = load_state()
        rec = state["sessions"].get(session_id)
        if rec is None:
            logger.warning("gpu_state.mark_destroyed: unknown session %s", session_id)
            return
        rec["destroyed_at"] = when or _now()
        rec["destroy_pending"] = False
        if cost_actual_usd is not None:
            rec["cost_actual_usd"] = cost_actual_usd
        _write_unlocked(state)


def mark_destroy_pending(session_id: str) -> None:
    """Mark that a destroy attempt failed and the reaper should retry."""
    with file_lock(_LOCK, timeout_seconds=15.0):
        state = load_state()
        rec = state["sessions"].get(session_id)
        if rec is None:
            logger.warning("gpu_state.mark_destroy_pending: unknown session %s", session_id)
            return
        rec["destroy_pending"] = True
        _write_unlocked(state)


def record_actual_cost(session_id: str, cost_actual_usd: float) -> None:
    """Fill in the actual cost after billing reconciliation."""
    with file_lock(_LOCK, timeout_seconds=15.0):
        state = load_state()
        rec = state["sessions"].get(session_id)
        if rec is None:
            logger.warning("gpu_state.record_actual_cost: unknown session %s", session_id)
            return
        rec["cost_actual_usd"] = cost_actual_usd
        _write_unlocked(state)


def get_session(session_id: str) -> dict[str, Any] | None:
    state = load_state()
    return state["sessions"].get(session_id)


def active_sessions() -> dict[str, dict[str, Any]]:
    """All sessions that have NOT been destroyed yet."""
    state = load_state()
    return {sid: rec for sid, rec in state["sessions"].items() if rec.get("destroyed_at") is None}


def gc_old(retention_days: int = RETENTION_DAYS) -> list[str]:
    """Drop session records destroyed more than ``retention_days`` ago.

    Returns the list of removed session_ids. Mirror of
    ``vultr_state.gc_old_disposables``.
    """
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    removed: list[str] = []
    with file_lock(_LOCK, timeout_seconds=15.0):
        state = load_state()
        for sid, rec in list(state["sessions"].items()):
            destroyed = rec.get("destroyed_at")
            if not destroyed:
                continue
            try:
                if datetime.fromisoformat(destroyed) < cutoff:
                    del state["sessions"][sid]
                    removed.append(sid)
            except ValueError:
                continue
        if removed:
            _write_unlocked(state)
    return removed


def reconcile(client: Any) -> dict[str, Any]:
    """Compare local state to the live RunPod account. Returns a drift report.

    Drift categories:

    - ``in_state_not_live``: tracked + not-destroyed locally, but absent on RunPod
      (provider destroyed it without our knowledge — e.g. via dashboard)
    - ``lifetime_exceeded``: tracked + not-destroyed, age > ``max_lifetime_hours``
    - ``destroy_pending``: previous destroy attempt failed — needs retry
    - ``orphan_pods`` / ``orphan_endpoints``: alive on RunPod with our
      ``FABRIK_SESSION_ID`` env tag but no matching active session here
    - ``foreign``: alive on RunPod, NO ``FABRIK_SESSION_ID`` tag — left strictly alone

    This function does NOT destroy anything. ``gpu_reaper.reap()`` consumes
    this report when ``--auto-destroy`` is set.
    """
    now = datetime.now(UTC)
    state = load_state()
    sessions = state["sessions"]

    live_pods = {p["id"]: p for p in client.list_pods()}
    live_endpoints = {e["id"]: e for e in client.list_endpoints()}

    tracked_active_pod_ids = {
        rec["resource_id"]
        for rec in sessions.values()
        if rec.get("destroyed_at") is None and rec.get("resource_type") == "pod"
    }
    tracked_active_endpoint_ids = {
        rec["resource_id"]
        for rec in sessions.values()
        if rec.get("destroyed_at") is None and rec.get("resource_type") == "endpoint"
    }

    report = {
        "scanned_at": now.isoformat(),
        "in_state_not_live": [],
        "lifetime_exceeded": [],
        "destroy_pending": [],
        "orphan_pods": [],
        "orphan_endpoints": [],
        "foreign_count": 0,
    }

    # 1. in_state_not_live + lifetime_exceeded + destroy_pending (all from state)
    for sid, rec in sessions.items():
        if rec.get("destroyed_at"):
            continue
        rid = rec.get("resource_id")
        rtype = rec.get("resource_type")
        if rtype == "pod" and rid not in live_pods:
            report["in_state_not_live"].append(
                {"session_id": sid, "resource_id": rid, "type": "pod"}
            )
        elif rtype == "endpoint" and rid not in live_endpoints:
            report["in_state_not_live"].append(
                {"session_id": sid, "resource_id": rid, "type": "endpoint"}
            )
        if rec.get("destroy_pending"):
            report["destroy_pending"].append({"session_id": sid, "resource_id": rid, "type": rtype})
        try:
            if datetime.fromisoformat(rec["expires_at"]) < now:
                report["lifetime_exceeded"].append(
                    {
                        "session_id": sid,
                        "resource_id": rid,
                        "type": rtype,
                    }
                )
        except (KeyError, ValueError):
            continue

    # 2. orphans: live on RunPod with our tag but not in state
    for pid, pod in live_pods.items():
        if pid in tracked_active_pod_ids:
            continue
        env = pod.get("env") or {}
        if "FABRIK_SESSION_ID" in env:
            report["orphan_pods"].append(
                {
                    "resource_id": pid,
                    "fabrik_session_id": env["FABRIK_SESSION_ID"],
                }
            )
        else:
            report["foreign_count"] += 1

    for eid, ep in live_endpoints.items():
        if eid in tracked_active_endpoint_ids:
            continue
        env = ep.get("env") or {}
        if "FABRIK_SESSION_ID" in env:
            report["orphan_endpoints"].append(
                {
                    "resource_id": eid,
                    "fabrik_session_id": env["FABRIK_SESSION_ID"],
                }
            )
        else:
            report["foreign_count"] += 1

    # Stamp last_reconciled regardless of auto-destroy
    with file_lock(_LOCK, timeout_seconds=15.0):
        state = load_state()
        state["last_reconciled"] = now.isoformat()
        _write_unlocked(state)

    return report
