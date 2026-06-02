"""Coolify alias-watcher write side (T2-04 G-J3) — LEGACY MODULE.

DECOMMISSIONED 2026-05-30: Coolify is gone; all containers now have stable
`container_name:` (Lesson 22) so the alias-watcher's whole reason to exist
(working around Coolify renaming single-image Applications on every redeploy)
no longer applies. The `/opt/coolify-alias-watcher/` directory on the VPS is
also decommissioned. New code paths must NOT call into this module.

Original docstring follows:

Companion to ``/opt/coolify-alias-watcher/`` on the VPS — that script is
the READ side (event-driven docker-events listener that re-applies
friendly DNS aliases after every Coolify Application redeploy). This
module is the WRITE side: when the orchestrator deploys a new service
whose spec sets ``coolify.alias``, it appends the prefix→alias mapping
to ``/opt/coolify-alias-watcher/aliases.json`` and restarts the watcher
service so the next docker-event fires under the new map.

Why prefixes, not full container names
--------------------------------------

Coolify renames single-image Application containers on every redeploy:
``<24-char-uuid>-<10-digit-timestamp>``. The timestamp suffix changes;
the UUID prefix is stable. The watcher matches on ``^${prefix}-`` so
the orchestrator only needs to know ``ctx.coolify_uuid`` (the bare
24-char UUID), not the current container name.

Why ``restart``, not ``reload``
-------------------------------

The ``coolify-alias-watcher.service`` unit defines ``Restart=always``
with NO ``ExecReload`` directive (verified live 2026-05-15). A
``systemctl reload`` always exits non-zero against that unit — even
though restart works fine. Restart cost is sub-second; we use restart
directly. See Pass-2 BLOCKER FIX in T2-04 ticket.
"""

from __future__ import annotations

import json
import logging
import shlex

from fabrik.drivers.ssh import ssh

logger = logging.getLogger(__name__)

ALIASES_PATH = "/opt/coolify-alias-watcher/aliases.json"
SERVICE_UNIT = "coolify-alias-watcher.service"


def _load_remote_aliases() -> dict:
    # Read the current aliases.json from VPS. Returns {} if file is
    # missing (first run on a fresh VPS) — caller will build it from
    # scratch.
    try:
        raw = ssh(f"sudo cat {ALIASES_PATH}")
    except RuntimeError as e:
        logger.warning("coolify_alias: cat %s failed (%s) — assuming empty", ALIASES_PATH, e)
        return {"version": 1, "aliases": {}}
    if not raw.strip():
        return {"version": 1, "aliases": {}}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(
            "coolify_alias: %s is invalid JSON (%s); refusing overwrite", ALIASES_PATH, e
        )
        raise


def _write_remote_aliases(payload: dict, *, dry_run: bool = False) -> None:
    # Atomic write via tee → /tmp/aliases.json.tmp + sudo mv. The
    # watcher's read happens on its NEXT restart, so a partial write
    # mid-deploy cannot put the watcher into a half-loaded state.
    new_content = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    quoted = shlex.quote(new_content)
    tmp_path = f"{ALIASES_PATH}.tmp"
    ssh(
        f"sudo tee {shlex.quote(tmp_path)} > /dev/null <<< {quoted}",
        dry_run=dry_run,
    )
    ssh(
        f"sudo chown root:root {shlex.quote(tmp_path)} && "
        f"sudo chmod 644 {shlex.quote(tmp_path)} && "
        f"sudo mv {shlex.quote(tmp_path)} {shlex.quote(ALIASES_PATH)}",
        dry_run=dry_run,
    )


def _restart_watcher(*, dry_run: bool = False) -> None:
    # Sub-second; no ExecReload available — restart is the only way.
    ssh(f"sudo systemctl restart {SERVICE_UNIT}", dry_run=dry_run)


def add_alias(coolify_uuid: str, alias: str, *, dry_run: bool = False) -> dict:
    """Register a stable Docker DNS alias for a Coolify-managed container.

    Args:
        coolify_uuid: The bare 24-char Coolify resource UUID
            (``ctx.coolify_uuid``). Becomes the PREFIX key the watcher
            matches with ``^${prefix}-`` — do NOT pass the full
            container name with timestamp suffix.
        alias: The friendly Docker DNS name (e.g. ``"meilisearch"``)
            that Gatus monitors / inter-service URLs depend on.
        dry_run: If True, plan only; emits zero VPS mutations.

    Returns:
        ``{"status": "added"|"exists"|"updated"|"dry_run", "prefix":
        coolify_uuid, "alias": alias}``

    Raises:
        ValueError: ``coolify_uuid`` or ``alias`` is empty / falsy.
        RuntimeError: VPS ssh call failed.
        json.JSONDecodeError: ``aliases.json`` on VPS is malformed.
    """
    if not coolify_uuid:
        raise ValueError("coolify_uuid must be a non-empty string")
    if not alias:
        raise ValueError("alias must be a non-empty string")

    current = _load_remote_aliases()
    aliases = current.setdefault("aliases", {})

    existing = aliases.get(coolify_uuid)
    if existing == alias:
        logger.info("coolify_alias: %s → %s already registered (noop)", coolify_uuid, alias)
        return {"status": "exists", "prefix": coolify_uuid, "alias": alias}

    status = "updated" if existing is not None else "added"
    aliases[coolify_uuid] = alias
    current.setdefault("version", 1)

    if dry_run:
        logger.info("[DRY RUN] coolify_alias: would %s %s → %s", status, coolify_uuid, alias)
        return {"status": "dry_run", "prefix": coolify_uuid, "alias": alias}

    _write_remote_aliases(current)
    _restart_watcher()
    logger.info("coolify_alias: %s %s → %s (watcher restarted)", status, coolify_uuid, alias)
    return {"status": status, "prefix": coolify_uuid, "alias": alias}


__all__ = ["add_alias", "ALIASES_PATH", "SERVICE_UNIT"]
