"""State store + reconciliation for ``fabrik vultr`` (Phase 2).

Single registry of the instances Fabrik provisioned via ``fabrik vultr``, at
``$FABRIK_ROOT/data/vultr-instances.json``. Writes are atomic (tmp + ``os.replace``)
under a local file lock — mirrors ``src/fabrik/state.py`` and uses the same
``fabrik.locks_local.file_lock`` primitive (NOT the VPS-side ``run_locked``).

``reconcile()`` compares local state to the live Vultr account to surface drift
(in state but deleted out-of-band; in Vultr but not tracked).

Schema (``schema_version: 1``)::

    {
      "schema_version": 1,
      "last_reconciled": "<ISO8601 UTC | null>",
      "instances": {
        "<name>": {
          "vultr_id": "...", "kind": "instance|bare_metal",
          "mode": "permanent|disposable", "ip": "...", "region": "...",
          "plan": "...", "created_at": "...", "destroy_after": "... | null",
          "destroyed_at": "... | null", "drill_kind": "... | null",
          "mesh_ip": "... | null", "spoke_name": "... | null"
        }
      }
    }
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fabrik.config import FABRIK_ROOT
from fabrik.locks_local import file_lock

logger = logging.getLogger(__name__)

STATE_FILE = FABRIK_ROOT / "data" / "vultr-instances.json"
SCHEMA_VERSION = 1
_LOCK = "vultr-state"
DISPOSABLE_RETENTION_DAYS = 30


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _empty() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "last_reconciled": None, "instances": {}}


def load_state() -> dict[str, Any]:
    """Read the registry (atomic-written, so lock-free reads are safe). Never raises."""
    if not STATE_FILE.exists():
        return _empty()
    try:
        data = json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("vultr_state.load: unreadable (%s); returning empty", e)
        return _empty()
    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("instances", {})
    data.setdefault("last_reconciled", None)
    return data


def _write_unlocked(state: dict[str, Any]) -> Path:
    """Atomic write WITHOUT acquiring the lock (caller must already hold it)."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    os.replace(tmp, STATE_FILE)
    return STATE_FILE


def save_state(state: dict[str, Any]) -> Path:
    """Atomically persist the full state under the lock."""
    with file_lock(_LOCK, timeout_seconds=15.0):
        return _write_unlocked(state)


def upsert_instance(name: str, record: dict[str, Any]) -> dict[str, Any]:
    """Insert/merge one instance record under a single read-modify-write lock."""
    with file_lock(_LOCK, timeout_seconds=15.0):
        state = load_state()
        merged = {**state["instances"].get(name, {}), **record}
        state["instances"][name] = merged
        _write_unlocked(state)
    return merged


def mark_destroyed(name: str, when: str | None = None) -> None:
    """Stamp ``destroyed_at`` on a tracked instance (kept for the audit window)."""
    with file_lock(_LOCK, timeout_seconds=15.0):
        state = load_state()
        if name in state["instances"]:
            state["instances"][name]["destroyed_at"] = when or _now()
            _write_unlocked(state)


def get_instance(name: str) -> dict[str, Any] | None:
    return load_state()["instances"].get(name)


def active_instances() -> dict[str, dict[str, Any]]:
    """Instances not yet marked destroyed."""
    return {n: r for n, r in load_state()["instances"].items() if not r.get("destroyed_at")}


def gc_old_disposables(retention_days: int = DISPOSABLE_RETENTION_DAYS) -> list[str]:
    """Drop disposable records destroyed longer than ``retention_days`` ago. Returns removed names."""
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    removed: list[str] = []
    with file_lock(_LOCK, timeout_seconds=15.0):
        state = load_state()
        for name, rec in list(state["instances"].items()):
            if rec.get("mode") != "disposable":
                continue
            destroyed = rec.get("destroyed_at")
            if not destroyed:
                continue
            try:
                if datetime.fromisoformat(destroyed) < cutoff:
                    del state["instances"][name]
                    removed.append(name)
            except ValueError:
                continue
        if removed:
            _write_unlocked(state)
    return removed


def reconcile(client: Any) -> dict[str, Any]:
    """Compare local state to the live Vultr account. Returns a drift report.

    - ``in_state_not_live``: tracked + not-destroyed locally, but absent on Vultr
      (deleted out-of-band — local record is stale).
    - ``in_live_not_state``: present on Vultr but not tracked locally
      (created out-of-band — e.g. a manual dashboard provision).
    """
    live: dict[str, dict[str, Any]] = {i["id"]: i for i in client.list_instances()}
    live.update({i["id"]: i for i in client.list_bare_metals()})
    live_ids = set(live)

    active = active_instances()
    tracked_ids = {r.get("vultr_id") for r in active.values() if r.get("vultr_id")}

    in_state_not_live = sorted(n for n, r in active.items() if r.get("vultr_id") not in live_ids)
    in_live_not_state = sorted(vid for vid in live_ids if vid not in tracked_ids)
    matched = sorted(n for n, r in active.items() if r.get("vultr_id") in live_ids)

    with file_lock(_LOCK, timeout_seconds=15.0):
        state = load_state()
        state["last_reconciled"] = _now()
        _write_unlocked(state)

    return {
        "matched": matched,
        "in_state_not_live": in_state_not_live,
        "in_live_not_state": in_live_not_state,
        "live_count": len(live_ids),
        "tracked_active_count": len(active),
    }
