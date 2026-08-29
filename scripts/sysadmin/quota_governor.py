#!/usr/bin/env python3
# AFTER-EDIT: tests/test_quota_governor.py | scripts/sysadmin/claude_broker.py | scripts/sysadmin/incident_context.py
"""Quota governor — headroom-aware router for the single-key ob@ VPS Claude.

Decide, per call, whether the active ob@ account or the OpenRouter pool runs the work — and NEVER
block an incident. This is a READER of `claude_rotate.py --status --json` output (the LIVE fleet
contract), not a modifier of the rotation machinery.

Routing (see docs/development/plans/2026-08-29-plan-1-vps-quota-governance.md):
  routine  → `pool` when the account is walled (`cap_walled`, the operator's authoritative weekly
             cap) OR `max(<every utilization window>)` >= RESERVE_PCT; else `ob@`.
  incident → `ob@` when the account is not capped AND the single-flight lock is free; else
             `pool-diagnose` (a capped account, or a fix already in flight — never blocked).

The reserve iterates EVERY utilization window the payload carries — `five_hour`, `seven_day`, and
every `model_windows` entry (per-model weekly sub-limits, e.g. Fable/Opus) — so a new window is
covered by construction. Grounded shape (fleet-mode `--status --json`, verified live 2026-08-29):
`{active:<slug>, accounts:[{email, slugs:[…], five_hour:{utilization,resets_at_epoch},
seven_day:{…}, model_windows:{<model>:{utilization,resets_at_epoch}}, weekly_cap, cap_walled}]}`.

Config is env-only (12-Factor III): QUOTA_RESERVE_PCT (default 80), QUOTA_CAP_TTL_S (default 21600
= 6h). No secrets, no new dependency (stdlib only). State lives under ~/.claude/state/ (VM-cut
survivable, matching the claude_rotate.py convention).
"""

from __future__ import annotations

import fcntl
import json
import math
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

_DIR = Path(__file__).resolve().parent
_STATE = Path(os.path.expanduser("~/.claude/state"))
_DEFAULT_RESERVE_PCT = 80.0
_DEFAULT_CAP_TTL_S = 21600.0  # 6h ≈ the 5h rolling window, a bounded default when no reset epoch


def _env_float(name: str, default: float) -> float:
    """Parse a float env var, FALLING BACK to *default* on absence/garbage — never raise.

    A malformed `QUOTA_RESERVE_PCT="80%"` must not crash the governor's construction (a deploy-time
    misconfig would otherwise defeat the "incident never blocked" invariant before any route()).
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        val = float(raw)
    except ValueError:
        return default
    # reject non-finite: float("inf")/"nan" parse without ValueError but would silently disable
    # shedding (inf reserve) or wedge the reactive cap (nan epoch → `now < nan` is always False).
    return val if math.isfinite(val) else default


def _default_status_fn() -> dict:
    """Run the LIVE `--status --json` CLI and return the parsed fleet payload (reader contract)."""
    out = subprocess.run(
        [sys.executable, str(_DIR / "claude_rotate.py"), "--status", "--json"],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return json.loads(out.stdout)


def _default_alert(subject: str, detail: str) -> None:
    """Best-effort Telegram via claude-sound.sh mesh-notify; never raises into the caller."""
    try:
        sound = Path(os.path.expanduser("~/.claude/bin/claude-sound.sh"))
        if sound.exists():
            subprocess.run(
                [str(sound), "mesh-notify", "quota-governor", str(_DIR), f"{subject}: {detail}"],
                capture_output=True,
                timeout=10,
                check=False,
            )
    except Exception:  # noqa: BLE001 — an alert failure must never break routing
        pass


class QuotaGovernor:
    """Headroom-aware router. Instantiate once per process; call `route()` per decision."""

    def __init__(
        self,
        *,
        reserve_pct: float | None = None,
        cap_ttl_s: float | None = None,
        status_fn: Callable[[], dict] | None = None,
        now_fn: Callable[[], float] | None = None,
        cap_state_path: Path | None = None,
        lock_path: Path | None = None,
        alert_fn: Callable[[str, str], None] | None = None,
    ) -> None:
        self.reserve_pct = (
            reserve_pct if reserve_pct is not None
            else _env_float("QUOTA_RESERVE_PCT", _DEFAULT_RESERVE_PCT)
        )
        self.cap_ttl_s = (
            cap_ttl_s if cap_ttl_s is not None
            else _env_float("QUOTA_CAP_TTL_S", _DEFAULT_CAP_TTL_S)
        )
        self._status_fn = status_fn or _default_status_fn
        self._now = now_fn or time.time
        self._cap_state_path = Path(cap_state_path) if cap_state_path else _STATE / "quota-governor-cap.json"
        self._lock_path = Path(lock_path) if lock_path else _STATE / "quota-governor-incident.lock"
        self._alert = alert_fn or _default_alert
        self._incident_lock_fd: int | None = None

    # ---- public API ---------------------------------------------------------

    def route(self, kind: str, *, caller: str | None = None) -> str:
        """Return "ob@" | "pool" | "pool-diagnose" for a "routine" | "incident" call.

        Fail-SAFE: any `--status` failure / unparseable row → routine sheds to the pool, an incident
        still runs on ob@ (the fix is never dropped because telemetry hiccupped).
        """
        row = self._active_row()
        if row is None:
            return "pool" if kind == "routine" else "ob@"

        capped = self._is_capped(row)
        if kind == "routine":
            m = self._max_util(row)
            # m is None → the row is present but carries NO parseable utilization window (schema
            # drift): headroom is UNKNOWN, so shed to the pool rather than assume 0% and burn ob@.
            if capped or m is None or m >= self.reserve_pct:
                return "pool"
            return "ob@"

        # incident — never blocked, never dropped
        if capped:
            return "pool-diagnose"
        if self._acquire_incident_lock():
            return "ob@"
        # another fix is in flight — shed to a read-only diagnosis, never a second ob@ slot
        return "pool-diagnose"

    def mark_capped(self, response_text: str) -> None:
        """Persist a reactive cap when a Claude response carries a usage-limit signal.

        The cap holds until the account's `seven_day` reset epoch, or — when that epoch is missing/
        unparseable (None) — a bounded `now + CAP_TTL_S`, so one None payload never wedges ob@
        capped forever (MED-1). No-op when the text carries no limit signal.
        """
        if not self._is_usage_limit(response_text):
            return
        row = self._active_row()
        epoch = None
        if row is not None:
            wk = row.get("seven_day")
            if isinstance(wk, dict):
                epoch = wk.get("resets_at_epoch")
        # Use the window's reset epoch ONLY when it is numeric AND in the future; a missing (None),
        # zero, or already-past epoch (stale telemetry, or a 5h signal while the weekly epoch trails
        # now) would write an already-expired cap that does nothing — fall back to a bounded
        # now + CAP_TTL_S so the reactive cap always actually holds (MED-1 + review MED).
        now = self._now()
        capped_until = epoch if isinstance(epoch, (int, float)) and epoch > now else now + self.cap_ttl_s
        self._write_cap_state({"capped_until_epoch": float(capped_until)})
        self._alert("ob@ capped (reactive)", f"usage-limit signal; holding until {capped_until:.0f}")

    def release_incident(self) -> None:
        """Release the single-flight incident lock once a fix completes."""
        if self._incident_lock_fd is not None:
            try:
                fcntl.flock(self._incident_lock_fd, fcntl.LOCK_UN)
                os.close(self._incident_lock_fd)
            except OSError:
                pass
            self._incident_lock_fd = None

    # ---- internals ----------------------------------------------------------

    def _active_row(self) -> dict | None:
        """The active account's row from `--status --json`, or None on any failure/unparseable shape.

        Resolves the fleet payload's `active` slug against each account's `slugs`. On a legacy
        (empty-fleet) payload without `accounts`, returns None → fail-safe.
        """
        try:
            payload = self._status_fn()
        except Exception:  # noqa: BLE001 — telemetry failure is a fail-safe condition, not a crash
            return None
        if not isinstance(payload, dict):
            return None
        active = payload.get("active")
        accounts = payload.get("accounts")
        if not isinstance(accounts, list):
            return None
        for acc in accounts:
            if isinstance(acc, dict) and active in (acc.get("slugs") or []):
                return acc
        return None

    def _max_util(self, row: dict) -> float | None:
        """Max utilization across five_hour, seven_day, and every model_windows entry.

        Returns None when the row carries NO parseable utilization window — a real ob@ row always
        has five_hour + seven_day, so an empty result means schema drift / unreadable telemetry, and
        the caller treats None as "headroom unknown → shed" (never as 0% = full headroom).
        """
        utils: list[float] = []
        for key in ("five_hour", "seven_day"):
            w = row.get(key)
            if isinstance(w, dict) and isinstance(w.get("utilization"), (int, float)):
                utils.append(float(w["utilization"]))
        mw = row.get("model_windows")
        if isinstance(mw, dict):
            for w in mw.values():
                if isinstance(w, dict) and isinstance(w.get("utilization"), (int, float)):
                    utils.append(float(w["utilization"]))
        return max(utils) if utils else None

    def _is_capped(self, row: dict) -> bool:
        """Capped = the fleet's authoritative `cap_walled` flag OR an active reactive cap."""
        if row.get("cap_walled") is True:
            return True
        return self._reactive_cap_active()

    def _reactive_cap_active(self) -> bool:
        state = self._read_cap_state()
        if not state:
            return False
        until = state.get("capped_until_epoch")
        if not isinstance(until, (int, float)):  # never compare now >= None
            return False
        return self._now() < until

    def _read_cap_state(self) -> dict:
        try:
            return json.loads(self._cap_state_path.read_text())
        except (OSError, ValueError):
            return {}

    def _write_cap_state(self, state: dict) -> None:
        self._cap_state_path.parent.mkdir(parents=True, exist_ok=True)
        # pid-unique tmp so two concurrent mark_capped() calls never race the same rename
        # (the single-flight lock guards incidents, not mark_capped).
        tmp = self._cap_state_path.with_suffix(f".{os.getpid()}.json.tmp")
        tmp.write_text(json.dumps(state))
        os.replace(tmp, self._cap_state_path)

    def _acquire_incident_lock(self) -> bool:
        """Non-blocking flock. True + hold on acquire; False when a fix is in flight OR the lock
        infra is unavailable.

        An `OSError` (bad state dir, permissions, disk-full) degrades to "unavailable" rather than
        raising — a broken lock must never turn an incident into an exception (the "incident never
        blocked" invariant); the incident then routes to `pool-diagnose`, never dropped.
        """
        try:
            self._lock_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self._lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        except OSError:
            return False
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:  # BlockingIOError — held by a live fix (or a lock-infra error)
            os.close(fd)
            return False
        self._incident_lock_fd = fd
        return True

    @staticmethod
    def _is_usage_limit(text: str) -> bool:
        """Reuse claude_rotate.is_usage_limit; lazy-import so a route() never pays the import."""
        if not text:
            return False
        try:
            if str(_DIR) not in sys.path:
                sys.path.insert(0, str(_DIR))
            from claude_rotate import is_usage_limit  # noqa: PLC0415 — lazy by design
            return bool(is_usage_limit(text))
        except Exception:  # noqa: BLE001 — fall back to a local signal if the import is unavailable
            import re
            return bool(re.search(r"usage limit|rate.?limit|out of extra usage|weekly limit", text, re.I))
