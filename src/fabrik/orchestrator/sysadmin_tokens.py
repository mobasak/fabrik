"""Per-host Telegram bot-token pool for spoke sysadmin auto-provisioning (PR3).

Each fleet host runs its own AI sysadmin bot with its own @BotFather token
(``env.sysadmin.template`` Option A). Creating a bot is interactive in Telegram,
so the operator pre-stages a small batch of tokens ONCE; ``fabrik vultr provision``
then claims the next free one unattended.

The pool lives in the DR store (git + W9-mirrored), NOT in ``data/`` — it is a
secret, shared fleet resource. Writes are atomic (tmp + ``os.replace``) under the
same ``fabrik.locks_local.file_lock`` primitive used by ``vultr_state``.

Pool file (``$FABRIK_DR_STORE/env/sysadmin-bot-tokens.json``)::

    {
      "schema_version": 1,
      "pool": [
        {"token": "<botfather-token>", "label": "SysAdminVPS4",
         "assigned_to": null, "assigned_at": null}
      ]
    }

Hygiene contract (plan PR3 constraint C4):
  - ``claim_bot_token`` never double-assigns; an already-claimed host reclaims
    the SAME token (idempotent); an empty/exhausted pool returns ``None`` (logged)
    so the caller can SKIP enabling the bot rather than write a placeholder that
    crash-loops ``bot.py`` into ``StartLimitBurst``.
  - ``release_bot_token`` returns a slot to the pool on reverse-teardown.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fabrik.locks_local import file_lock

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
_LOCK = "sysadmin-bot-tokens"
# @BotFather token shape: <digits>:<alphanumerics/underscore/hyphen>. Validated
# before assignment so a malformed/typo'd pool entry can never reach the sed that
# writes .env.sysadmin (defence-in-depth vs injection — PR3 review suggestion).
_TOKEN_RE = re.compile(r"^\d+:[A-Za-z0-9_-]+$")


def _dr_store() -> Path:
    """DR-store root — overridable for tests/non-default installs."""
    return Path(os.environ.get("FABRIK_DR_STORE", "/opt/fabrik-dr-store"))


def pool_path() -> Path:
    return _dr_store() / "env" / "sysadmin-bot-tokens.json"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _load() -> dict[str, Any]:
    """Read the pool. A missing/unreadable file is an EMPTY pool (logged), not an error."""
    path = pool_path()
    if not path.exists():
        logger.info("token pool absent at %s — treating as empty (stage tokens there)", path)
        return {"schema_version": SCHEMA_VERSION, "pool": []}
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("token pool unreadable (%s); treating as empty", e)
        return {"schema_version": SCHEMA_VERSION, "pool": []}
    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("pool", [])
    return data


def _write_unlocked(data: dict[str, Any]) -> None:
    """Atomic write WITHOUT the lock (caller holds it)."""
    path = pool_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    os.replace(tmp, path)


def claim_bot_token(name: str) -> str | None:
    """Claim the next free bot token for host ``name``.

    Idempotent: if ``name`` already holds a token, returns the same one (no new
    assignment). Returns ``None`` if the pool is empty/exhausted — the caller MUST
    then skip enabling the bot (never write a placeholder token).
    """
    with file_lock(_LOCK, timeout_seconds=15.0):
        data = _load()
        # Idempotent reclaim — a re-run of provision for the same host.
        for entry in data["pool"]:
            if entry.get("assigned_to") == name:
                logger.info("token pool: %s already holds %s — reusing", name, entry.get("label"))
                return entry["token"]
        # First free slot — but never assign a malformed token (it would later
        # be interpolated into the .env.sysadmin sed); skip + warn, try the next.
        for entry in data["pool"]:
            if entry.get("assigned_to") is not None:
                continue
            token = entry.get("token", "")
            if not _TOKEN_RE.match(token):
                logger.warning(
                    "token pool: skipping malformed token for label %s "
                    "(expected '<digits>:<alnum/_/->') — fix the pool file",
                    entry.get("label"),
                )
                continue
            entry["assigned_to"] = name
            entry["assigned_at"] = _now()
            _write_unlocked(data)
            logger.info("token pool: assigned %s to %s", entry.get("label"), name)
            return token
        free = sum(1 for e in data["pool"] if e.get("assigned_to") is None)
        logger.warning(
            "token pool EXHAUSTED (%d entries, %d free) — cannot auto-assign a bot "
            "for %s; stage more tokens at %s",
            len(data["pool"]),
            free,
            name,
            pool_path(),
        )
        return None


def release_bot_token(name: str) -> bool:
    """Return ``name``'s token to the pool (reverse-teardown). True if one was freed."""
    with file_lock(_LOCK, timeout_seconds=15.0):
        data = _load()
        freed = False
        for entry in data["pool"]:
            if entry.get("assigned_to") == name:
                entry["assigned_to"] = None
                entry["assigned_at"] = None
                freed = True
        if freed:
            _write_unlocked(data)
            logger.info("token pool: released slot held by %s", name)
        return freed


def pool_status() -> dict[str, int]:
    """Counts for ``fabrik vultr`` inspection / depletion visibility."""
    pool = _load()["pool"]
    assigned = sum(1 for e in pool if e.get("assigned_to"))
    return {"total": len(pool), "assigned": assigned, "free": len(pool) - assigned}
