"""MeiliSearch index provisioning on the shared Coolify-managed instance.

Creates (and, for rollback, deletes) a search index via ``docker exec`` +
``curl`` against the in-container HTTP API. This avoids exposing port 7700
to the host and avoids transmitting the master key over SSH — the
``MEILI_MASTER_KEY`` environment variable is already present inside the
container and dereferenced by a container-side ``sh -c`` subshell.

Shape-gating
------------

MeiliSearch is an **opt-in** registrar: only projects with
``shape.has_search_feature == True`` should trigger it. The orchestrator
(Phase 4h) asks each driver module ``applies_to(shape)`` before calling
its ``create_*`` entry point, so a throwaway static site never reaches
this module. :func:`applies_to` is the canonical shape predicate for
this driver and is exported as ``__all__``.

Design notes
------------
* **Container resolved by Coolify label**, not UUID — mirrors the
  ``authelia.py`` pattern and survives Coolify container re-creation.
  Verified live 2026-04-19: ``docker ps --filter label=coolify.serviceName=meilisearch``
  resolves to the current ``bs0wo48k4gwo440gcowscoc8-150802066640`` UUID.
* **Master key stays in the container.** The spec writes
  ``-H 'Authorization: Bearer $MEILI_MASTER_KEY'`` which, passed to
  ``docker exec`` without a shell, would reach ``curl`` as a literal
  string. We wrap the curl invocation in ``sh -c`` inside the container
  so the shell evaluates ``$MEILI_MASTER_KEY`` against the container's
  env, never the operator's. No secret crosses the SSH wire.
* **UID validation.** MeiliSearch's index UID rules
  (``[a-zA-Z0-9_-]{1,511}``) are enforced in Python before any SSH call.
  The regex is stricter than MeiliSearch's in two ways: we require a
  leading alphanumeric (no ``_``/``-`` first), and we cap at 128 chars
  (well under the 511 MeiliSearch limit) to keep shell commands short.
* **Idempotent.** :func:`create_index` GETs the index first; HTTP 200
  means "exists" and short-circuits without mutating.
* **Rollback:** :func:`delete_index` is the best-effort rollback path
  (never raises, returns bool) consumed by ``DeploymentRollback``.
"""

from __future__ import annotations

import json
import logging
import re
import shlex
from typing import Any

from fabrik.drivers.ssh import ssh

logger = logging.getLogger(__name__)

MEILI_LABEL_SELECTOR = "label=coolify.serviceName=meilisearch"
"""Docker filter that resolves the Coolify-managed MeiliSearch container
regardless of UUID suffix changes on recreate."""

MEILI_INTERNAL_URL = "http://localhost:7700"
"""URL used from inside the container. Port 7700 is MeiliSearch's default;
the operator never reaches this URL directly — it goes through
``traefik`` → ``https://search.vps1.ocoron.com`` for external access."""

SHAPE_FLAG = "has_search_feature"
"""Key on ``shape`` dict that gates this driver. Set by the project's
scaffold (``fabrik scaffold --has-search`` → ``shape.has_search_feature=true``)."""

_UID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")
"""MeiliSearch index UID subset: leading alphanumeric, up to 128 chars,
letters/digits/underscore/hyphen only. Stricter than MeiliSearch's own
``[a-zA-Z0-9_-]{1,511}`` to keep shell commands predictable."""


def applies_to(shape: dict[str, Any]) -> bool:
    """Return True iff this driver should be invoked for ``shape``.

    Canonical applicability predicate — every shape-driven driver under
    :mod:`fabrik.drivers` exports one of these so the Phase 4h
    orchestrator can do::

        for driver in (postgres, gatus, backrest, meilisearch, ...):
            if driver.applies_to(shape):
                driver.create_*(...)

    Args:
        shape: The project's shape dict (from ``fabrik scaffold`` /
            ``spec.yaml``). Any non-mapping input returns False.

    Returns:
        True only when ``shape[SHAPE_FLAG]`` is truthy. Missing key,
        falsy value, or non-dict all return False — the conservative
        default is "don't provision search".

    Example:
        >>> applies_to({"has_search_feature": True})
        True
        >>> applies_to({"kind": "static-site"})
        False
    """
    if not isinstance(shape, dict):
        return False
    return bool(shape.get(SHAPE_FLAG))


def _validate_uid(uid: str) -> None:
    """Raise :class:`ValueError` if ``uid`` is not a safe MeiliSearch index UID."""
    if not isinstance(uid, str) or not _UID_RE.match(uid):
        raise ValueError(
            f"Invalid MeiliSearch index UID {uid!r}: must match [a-zA-Z0-9][a-zA-Z0-9_-]{{0,127}}"
        )


def _resolve_container() -> str:
    """Resolve the current Meilisearch container name by Coolify label.

    Raises:
        RuntimeError: No container matches — Meilisearch is not deployed.
    """
    name = ssh(
        f"sudo docker ps --filter {MEILI_LABEL_SELECTOR} --format '{{{{.Names}}}}' | head -1"
    ).strip()
    if not name:
        raise RuntimeError(
            "MeiliSearch container not found "
            f"({MEILI_LABEL_SELECTOR}). Is the Coolify-managed "
            "service running?"
        )
    return name


def _container_curl(container: str, curl_args: str) -> str:
    """Run ``curl`` inside the Meilisearch container with the master key.

    The curl invocation is executed by a container-side ``sh -c`` so that
    ``$MEILI_MASTER_KEY`` is evaluated against the **container's** env
    (where it is set) rather than the operator's. No secret crosses the
    SSH wire.

    Args:
        container: Container name from :func:`_resolve_container`.
        curl_args: Everything after ``curl`` (e.g., ``"-s -X GET
            http://localhost:7700/indexes/foo -H \"Authorization:
            Bearer $MEILI_MASTER_KEY\""``). Must NOT be pre-shell-quoted.

    Returns:
        stdout from the curl call (stripped).
    """
    inner = f"curl {curl_args}"
    cmd = f"sudo docker exec {container} sh -c {shlex.quote(inner)}"
    return ssh(cmd)


def _index_exists(container: str, index_uid: str) -> bool:
    """Return True if the index is already present (HTTP 200 on GET)."""
    status = _container_curl(
        container,
        (
            f'-s -o /dev/null -w "%{{http_code}}" '
            f"{MEILI_INTERNAL_URL}/indexes/{index_uid} "
            f'-H "Authorization: Bearer $MEILI_MASTER_KEY"'
        ),
    )
    return status.strip() == "200"


def create_index(
    index_uid: str,
    primary_key: str = "id",
    dry_run: bool = False,
) -> dict:
    """Create a MeiliSearch index. Idempotent on ``index_uid``.

    Args:
        index_uid: Index identifier. Must match
            ``[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}``.
        primary_key: Document primary-key field. Default ``"id"`` (matches
            MeiliSearch's own default and the existing production audit).
            Same identifier regex applied.
        dry_run: Skip all VPS mutations.

    Returns:
        ``{"status": "created" | "exists" | "dry_run", "index": index_uid}``.

    Raises:
        ValueError: ``index_uid`` / ``primary_key`` failed validation.
        RuntimeError: Container not found, or the create-index API
            returned an error.
    """
    _validate_uid(index_uid)
    _validate_uid(primary_key)

    if dry_run:
        logger.info("[DRY RUN] Would create MeiliSearch index: %s", index_uid)
        return {"status": "dry_run", "index": index_uid}

    container = _resolve_container()

    if _index_exists(container, index_uid):
        logger.info("MeiliSearch index already exists: %s", index_uid)
        return {"status": "exists", "index": index_uid}

    # POST body — JSON, shlex-quoted inside the container command.
    body = json.dumps({"uid": index_uid, "primaryKey": primary_key})
    out = _container_curl(
        container,
        (
            f"-s -X POST {MEILI_INTERNAL_URL}/indexes "
            f'-H "Authorization: Bearer $MEILI_MASTER_KEY" '
            f'-H "Content-Type: application/json" '
            f"-d {shlex.quote(body)}"
        ),
    )

    # MeiliSearch returns a task-accepted envelope on success. An error
    # payload includes the literal ``"code"`` key with a category string.
    if '"code":"' in out and '"taskUid"' not in out:
        raise RuntimeError(f"MeiliSearch create_index failed for {index_uid!r}: {out}")

    logger.info("Created MeiliSearch index: %s", index_uid)
    return {"status": "created", "index": index_uid}


def delete_index(index_uid: str, dry_run: bool = False) -> bool:
    """Rollback handler — delete a MeiliSearch index. Best-effort.

    Args:
        index_uid: Index to delete.
        dry_run: Log intent and return True.

    Returns:
        True on success, no-op on missing index, or dry-run.
        False on any SSH/API error (logged at WARNING, not re-raised).
    """
    _validate_uid(index_uid)

    if dry_run:
        logger.info("[DRY RUN] Would delete MeiliSearch index: %s", index_uid)
        return True

    try:
        container = _resolve_container()
        _container_curl(
            container,
            (
                f"-s -X DELETE {MEILI_INTERNAL_URL}/indexes/{index_uid} "
                f'-H "Authorization: Bearer $MEILI_MASTER_KEY"'
            ),
        )
        logger.info("Deleted MeiliSearch index: %s", index_uid)
        return True
    except Exception as e:  # noqa: BLE001 — rollback must not raise
        logger.warning("MeiliSearch delete_index failed (non-fatal): %s", e)
        return False


__all__ = (
    "MEILI_LABEL_SELECTOR",
    "MEILI_INTERNAL_URL",
    "SHAPE_FLAG",
    "applies_to",
    "create_index",
    "delete_index",
)
