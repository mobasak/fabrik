"""Per-deploy state file persistence for the Fabrik orchestrator.

Persists a JSON record under ``$FABRIK_ROOT/.fabrik/state/<spec_id>.json``
after every successful ``deploy()`` or ``refresh_infrastructure()`` run.
The file is the source of truth for:

* ``fabrik audit-registrars`` (T2-02) — reads ``target_vps`` to find the box,
  and reports the ``registrar_failures`` the last completed apply recorded;
* ``fabrik destroy --use-state`` (T4-02 G-F4, shipped 2026-05-16) —
  replays the destroy from the state file's ``registrars_applied`` list
  so the destroy doesn't depend on the current spec (which may have
  drifted). Implementation:
  :func:`fabrik.orchestrator.destroyer.destroy_from_state`;
* Cross-machine portability — operator on a different WSL host can
  inspect what's deployed without re-running orchestration.

Schema
------

The ``spec_id`` is the FILENAME (``<spec_id>.json``), NOT a field inside
the JSON. Each file is a single JSON object with exactly these 10 fields,
keys-sorted alphabetically for stable diffs::

    {
      "applied_at":          "<ISO 8601 UTC>",
      "coolify_app_name":    "<id or fabrik-<id>>",
      "coolify_uuid":        "<24-char alphanumeric uuid or null>",
      "domain":              "<FQDN or empty>",
      "git_sha":             "<40-char or empty if not in git>",
      "registrar_failures":  [
        {"registrar": "redis", "error": "REDIS_URL injection failed: ..."}
      ],
      "registrars_applied":  [
        {"type": "postgres",  "id": "translator",  "status": "applied", "data_bearing": true},
        {"type": "gatus",     "id": "translator",  "status": "applied", "data_bearing": false}
      ],
      "spec_hash":           "<16-char prefix of sha256 of yaml.dump(spec, sort_keys=True)>",
      "spec_path":           "/opt/fabrik/specs/services/<id>.yaml",
      "target_vps":          "vps1"
    }

``registrar_failures`` holds the failures of the last apply that COMPLETED
(W-2013a22d): ``[]`` means it finished clean. A rolled-back or failed run
writes no state file, so the previous file stays — read ``applied_at`` to
tell runs apart. A ``registrar`` label may be a non-registrar step
(``app-role``, ``shared-analytics``), and a registrar can appear in both
``registrars_applied`` and ``registrar_failures`` (added, then a later step
failed). A file written before the field existed has no key at all.

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
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fabrik.config import FABRIK_ROOT
from fabrik.locks_local import file_lock

logger = logging.getLogger(__name__)

# A registrar failure is raw exception text, and `fabrik export` ships these files.
_URL_CREDENTIALS = re.compile(r"://[^@/\s]*@")
_SQL_PASSWORD = re.compile(r"PASSWORD\s+'[^']*'", re.I)
_AUTH_HEADER = re.compile(r"(Authorization[\"']?\s*[:=]\s*[\"']?\w+\s+)[^\s\"',}]+", re.I)
_SECRET_WORDS = r"\w*(?:TOKEN|SECRET|KEY|PASSWORD|PASSWD|CREDENTIAL)S?\w*"
# a quoted value (spaces inside) — ssh._redact's `\S+` stops at the first space
_QUOTED = r"'(?:\\.|[^'\\])*(?:'|$)|\"(?:\\.|[^\"\\])*(?:\"|$)"
_QUOTED_ASSIGN = re.compile(rf"({_SECRET_WORDS}\s*=\s*)({_QUOTED})", re.I)
# a JSON / dict field: "password": "..."
_JSON_SECRET = re.compile(rf"([\"']{_SECRET_WORDS}[\"']\s*:\s*)({_QUOTED})", re.I)
_FAILURE_MAX_CHARS = 500
# the masks scan only this much: _QUOTED_ASSIGN backtracks O(n^2) on a long word run, and it runs on
# the deploy's success path with no timeout. 4x the cap keeps mask-before-cap for anything kept.
_FAILURE_SCAN_CHARS = 2000

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


def _sanitize_failure(text: object) -> str:
    """``text`` with secret-shaped parts masked, then capped — never raises.

    Masks before it caps, so a credential straddling the cap is masked whole.
    """
    from fabrik.drivers.ssh import _redact

    out = ("" if text is None else str(text))[:_FAILURE_SCAN_CHARS]
    out = _QUOTED_ASSIGN.sub(r"\1<redacted>", out)
    out = _JSON_SECRET.sub(lambda m: f"{m[1]}{m[2][0]}<redacted>{m[2][0]}", out)
    out = _AUTH_HEADER.sub(r"\1<redacted>", out)
    out = _redact(out)
    out = _URL_CREDENTIALS.sub("://[redacted]@", out)
    out = _SQL_PASSWORD.sub("PASSWORD '[redacted]'", out)
    return out[:_FAILURE_MAX_CHARS]


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
    target_vps: str = "vps1",
    registrar_failures: list[dict[str, Any]] | None = None,
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
        registrar_failures: ``[{"registrar": <label>, "error": <text>}]`` from
            the apply; each error is sanitised here. ``None`` writes ``[]`` —
            which reads "finished clean", so only ``_persist_state`` (the sole
            writer, after a completed apply) may rely on that default.
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
        "registrar_failures": [
            {"registrar": str(f.get("registrar") or ""), "error": _sanitize_failure(f.get("error"))}
            for f in (e if isinstance(e, dict) else {"error": e} for e in registrar_failures or [])
        ],
        "registrars_applied": normalized,
        "spec_hash": spec_hash,
        "spec_path": spec_path,
        "target_vps": target_vps,
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
