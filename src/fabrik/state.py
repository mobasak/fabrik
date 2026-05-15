"""Per-deploy state file persistence for the Fabrik orchestrator.

Persists a JSON record under ``$FABRIK_ROOT/.fabrik/state/<spec_id>.json``
after every successful ``deploy()`` or ``refresh_infrastructure()`` run.
The file is the source of truth for:

* ``fabrik audit-registrars`` (T2-02) — compares actual live state vs.
  what the state file says was applied;
* ``fabrik destroy --use-state`` (T4-01) — replays the destroy from the
  state file's ``registrars_applied`` list so the destroy doesn't depend
  on the current spec (which may have drifted);
* Cross-machine portability — operator on a different WSL host can
  inspect what's deployed without re-running orchestration.

Schema
------

The ``spec_id`` is the FILENAME (``<spec_id>.json``), NOT a field inside
the JSON. Each file is a single JSON object with exactly these 8 fields,
keys-sorted alphabetically for stable diffs::

    {
      "applied_at":          "<ISO 8601 UTC>",
      "coolify_app_name":    "<id or fabrik-<id>>",
      "coolify_uuid":        "<24-char alphanumeric uuid or null>",
      "domain":              "<FQDN or empty>",
      "git_sha":             "<40-char or empty if not in git>",
      "registrars_applied":  [
        {"type": "postgres",  "id": "translator",  "status": "applied", "data_bearing": true},
        {"type": "gatus",     "id": "translator",  "status": "applied", "data_bearing": false}
      ],
      "spec_hash":           "<16-char prefix of sha256 of yaml.dump(spec, sort_keys=True)>",
      "spec_path":           "/opt/fabrik/specs/services/<id>.yaml"
    }

The caller (``DeploymentOrchestrator._persist_state``) filters
``registrars_applied`` to entries whose ``type`` is in
``fabrik.orchestrator.infrastructure._REGISTRAR_ORDER`` — deploy-tier
``ResourceRecord`` types (``dns``, ``coolify``, ``files``, etc.) never
appear because the state file is the *registrar* manifest, not the full
*resource* manifest. ``state.save()`` itself trusts the input and only
stamps ``data_bearing`` per type.

Concurrency + atomicity
------------------------

* Writes are atomic via tmp-file + ``os.replace``.
* Concurrent saves for the same ``spec_id`` are serialized through
  :func:`fabrik.locks_local.file_lock`.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fabrik.config import FABRIK_ROOT
from fabrik.locks_local import file_lock

logger = logging.getLogger(__name__)

STATE_DIR = FABRIK_ROOT / ".fabrik" / "state"

DATA_BEARING_REGISTRARS = frozenset({"postgres", "redis", "meilisearch"})
"""Registrars whose live state holds user-visible data and therefore
require ``data_bearing: true`` in the state file. Redis is included
because Fabrik services use named DB indexes to hold per-service state
(captcha sessions, authelia sessions, etc.); a destroy must treat redis
the same way it treats postgres.

Used by ``fabrik destroy --partial`` (T2-02/T4-02) to require an explicit
``--drop-data`` flag before deleting these registrars' resources."""


def _git_sha() -> str:
    # Generate at save-time. Return empty string on any failure — we never
    # want a missing git sha to crash an orchestrator path; the state
    # file is best-effort metadata, not a load-bearing pre-flight check.
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(FABRIK_ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def save(
    spec_id: str,
    *,
    spec_path: str,
    spec_hash: str,
    coolify_uuid: str | None,
    coolify_app_name: str,
    registrars_applied: list[dict[str, Any]],
    domain: str = "",
    applied_at: str | None = None,
    git_sha: str | None = None,
) -> Path:
    """Atomically write ``.fabrik/state/<spec_id>.json``.

    Args:
        spec_id: The spec's ``id`` field (e.g. ``"translator"``).
        spec_path: Absolute path to the source spec YAML.
        spec_hash: SHA256 of the canonical spec content.
        coolify_uuid: 24-char Coolify resource UUID, or ``None`` for
            registrars-only flows where there is no Coolify app.
        coolify_app_name: ``<id>`` or ``fabrik-<id>`` — whichever name
            Coolify exposes the app under (per T1 G-G1 logic).
        registrars_applied: Raw list of registrar dicts from the caller.
            Each must have at least ``type``, ``id``, ``status`` keys.
            ``data_bearing`` is set automatically by this function from
            :data:`DATA_BEARING_REGISTRARS` — the caller does not have to
            pre-fill it (and any value the caller passes is overwritten,
            so the truth source is always this module's constant).
            Entries whose ``type`` is not in
            ``fabrik.orchestrator.infrastructure._REGISTRAR_ORDER`` are
            filtered out by the caller; this function trusts the input.
        domain: Service FQDN, or empty string if no public domain.
        applied_at: ISO-8601 UTC timestamp; generated if ``None``.
        git_sha: 40-char hash; generated via ``git rev-parse`` if ``None``.

    Returns:
        The path that was written.
    """
    if applied_at is None:
        applied_at = datetime.now(UTC).isoformat()
    if git_sha is None:
        git_sha = _git_sha()

    # Auto-stamp data_bearing per registrar type so callers never have
    # to remember the constant. This is the single source of truth.
    normalized = []
    for r in registrars_applied:
        entry = dict(r)
        entry["data_bearing"] = entry.get("type") in DATA_BEARING_REGISTRARS
        normalized.append(entry)

    payload = {
        "applied_at": applied_at,
        "coolify_app_name": coolify_app_name,
        "coolify_uuid": coolify_uuid,
        "domain": domain,
        "git_sha": git_sha,
        "registrars_applied": normalized,
        "spec_hash": spec_hash,
        "spec_path": spec_path,
    }

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    target = STATE_DIR / f"{spec_id}.json"
    tmp = target.with_suffix(f".tmp.{os.getpid()}")

    with file_lock(f"state-{spec_id}", timeout_seconds=15.0):
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
        os.replace(tmp, target)
    logger.debug("state.save: wrote %s", target)
    return target


def load(spec_id: str) -> dict[str, Any] | None:
    """Return the parsed state JSON or ``None`` if missing/unreadable."""
    target = STATE_DIR / f"{spec_id}.json"
    if not target.exists():
        return None
    try:
        return json.loads(target.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("state.load(%s): unreadable — %s", spec_id, e)
        return None


def archive_destroyed(spec_id: str) -> Path | None:
    """Move ``state/<spec_id>.json`` to ``state/_destroyed/<spec_id>.json.<ts>``.

    Returns the archive path, or ``None`` if there was nothing to archive.
    Called from the destroy orchestrator on success — preserves the
    audit trail rather than deleting the file outright.
    """
    src = STATE_DIR / f"{spec_id}.json"
    if not src.exists():
        return None
    archive_dir = STATE_DIR / "_destroyed"
    archive_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dest = archive_dir / f"{spec_id}.json.{ts}"
    with file_lock(f"state-{spec_id}", timeout_seconds=15.0):
        os.replace(src, dest)
    logger.debug("state.archive_destroyed: %s → %s", src, dest)
    return dest


def find_by_spec_id(spec_id: str) -> Path | None:
    """Return path to the current state file for ``spec_id``, or ``None``."""
    target = STATE_DIR / f"{spec_id}.json"
    return target if target.exists() else None
