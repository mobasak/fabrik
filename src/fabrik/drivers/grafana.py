"""Grafana deployment-annotation driver — non-fatal, decorative.

Posts **global** annotations (no ``dashboardId``/``panelId``) to the
Fabrik Grafana at ``monitor.vps1.ocoron.com``. Global annotations render
as vertical markers on every dashboard that filters by the configured
tag (the default Fabrik dashboards filter by ``deployment``), giving
operators a visual correlation between metric anomalies and deploys.

Design notes
------------

* **Always non-fatal.** Grafana annotations are *decorative*, never
  infrastructure. A Grafana outage, an expired token, or a 5xx must
  never break a deploy. Every public function returns a status dict
  on any failure; nothing escapes. The orchestrator treats
  ``status != "created"`` as an observability degradation, not a
  deploy failure.

* **Universal applicability.** Per the plan's shape matrix, Grafana
  applies to *every* project. :func:`applies_to` always returns
  True — callers don't need to consult the shape for this driver.
  It is still exported for uniformity with the other drivers so
  :class:`InfrastructureProvisioner` can iterate registrars with a
  single abstraction.

* **Epoch milliseconds, not seconds.** Grafana silently pins seconds
  timestamps to epoch 0, producing invisible annotations. We
  compute ``int(time.time() * 1000)`` and guard against regressions
  with :func:`tests.drivers.test_grafana.TestPostDeploymentAnnotation.test_time_is_epoch_ms`.

* **Bearer token is never logged.** The token is read via
  :func:`os.getenv` inside :func:`_build_headers` and only ever
  placed in the ``Authorization`` header. It is never passed as a
  function argument (would appear in stack traces) or printed.

Environment
-----------

``GRAFANA_SERVICE_ACCOUNT_TOKEN`` — Bearer token with an Editor (or
higher) role on the Grafana org. Validated live by
``scripts/probes/grafana_token_check.sh`` (Phase 4-pre Task 3).
Absence of the token is **not** an error: the driver returns
``status=skipped`` so that new deployments on hosts where Grafana
hasn't been provisioned yet still succeed.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

GRAFANA_URL = "https://monitor.vps1.ocoron.com"
"""Public base URL. The driver uses HTTPS (not the internal container
short-name ``grafana:3000``) because :func:`post_deployment_annotation`
is invoked from the orchestrator in the WSL dev box as well as inside
the CI container, neither of which is on the VPS Docker network."""

_DEFAULT_TIMEOUT = 10
"""HTTP timeout. 10s accommodates worst-case TLS + annotation insert
(observed p99 via `scripts/probes/grafana_token_check.sh`: ~350ms)."""

DEPLOYMENT_TAG = "deployment"
"""Primary tag applied to every deployment annotation. Fabrik's default
dashboards filter by this tag to surface deploy markers. Keep stable —
changing it would desynchronize against the existing Grafana templates."""


def applies_to(shape: dict[str, Any] | None) -> bool:
    """Grafana annotations apply to every project, unconditionally.

    Included for symmetry with :mod:`fabrik.drivers.glitchtip` and
    :mod:`fabrik.drivers.meilisearch` so the orchestrator's registrar
    loop works with a single abstraction.

    Args:
        shape: Unused — accepted for interface uniformity.

    Returns:
        Always ``True``.
    """
    return True


def _build_headers() -> dict[str, str] | None:
    """Build the Authorization + Content-Type headers.

    Returns ``None`` when the token is unset so the caller can short-
    circuit to ``status=skipped`` without raising.
    """
    token = os.getenv("GRAFANA_SERVICE_ACCOUNT_TOKEN")
    if not token:
        return None
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _build_text(project_name: str, domain: str | None, git_sha: str | None) -> str:
    """Compose the annotation text. Short, parse-able in a dashboard tooltip."""
    parts = [f"Deployed {project_name}"]
    if git_sha:
        parts.append(f"({git_sha[:7]})")
    if domain:
        parts.append(f"to {domain}")
    return " ".join(parts)


def post_deployment_annotation(
    project_name: str,
    domain: str | None = None,
    git_sha: str | None = None,
    extra_tags: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Post a global deployment annotation to Grafana.

    Args:
        project_name: Short project name (used in the text AND as a
            per-project tag so dashboards can filter to one service).
        domain: Optional FQDN — appended to the annotation text for
            quick visual identification on multi-tenant dashboards.
        git_sha: Optional git SHA — first 7 chars are shown.
        extra_tags: Additional tags to append. The base tag list
            (``["deployment", project_name]``) always comes first —
            dashboard queries depend on those two anchors.
        dry_run: Skip all network calls.

    Returns:
        Status dict. Shape is stable across all outcomes so the
        orchestrator can always ``.get("annotation_id")`` without a
        type check:

        * ``{"status": "dry_run", "project": <name>, "annotation_id": None}``
        * ``{"status": "skipped", "reason": "no_token", "annotation_id": None}``
        * ``{"status": "created", "annotation_id": <int>, "project": <name>}``
        * ``{"status": "failed", "annotation_id": None, "error": <str>}``

    Never raises — the driver is non-fatal by contract. Exceptions are
    caught, logged at WARNING, and returned as ``status=failed``.
    """
    if dry_run:
        logger.info("[DRY RUN] Would post Grafana annotation for %s", project_name)
        return {
            "status": "dry_run",
            "project": project_name,
            "annotation_id": None,
        }

    headers = _build_headers()
    if headers is None:
        logger.warning("GRAFANA_SERVICE_ACCOUNT_TOKEN not set; skipping deployment annotation")
        return {
            "status": "skipped",
            "reason": "no_token",
            "project": project_name,
            "annotation_id": None,
        }

    tags = [DEPLOYMENT_TAG, project_name]
    if extra_tags:
        # Preserve caller's tag order; deduplicate while keeping first occurrence.
        seen = set(tags)
        for t in extra_tags:
            if t not in seen:
                tags.append(t)
                seen.add(t)

    body = {
        "time": int(time.time() * 1000),  # epoch MILLISECONDS — see module docstring
        "tags": tags,
        "text": _build_text(project_name, domain, git_sha),
    }

    try:
        resp = requests.post(
            f"{GRAFANA_URL}/api/annotations",
            json=body,
            headers=headers,
            timeout=_DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        payload = resp.json() if resp.content else {}
        annotation_id = payload.get("id")
        if not isinstance(annotation_id, int):
            # Grafana always returns an integer id on success. If we
            # somehow got here without one, flag failure so the rollback
            # path can't try to delete a non-existent annotation.
            logger.warning("Grafana annotation response missing integer id: %r", payload)
            return {
                "status": "failed",
                "annotation_id": None,
                "error": "no_id_in_response",
                "project": project_name,
            }
        logger.info("Grafana annotation posted: id=%d project=%s", annotation_id, project_name)
        return {
            "status": "created",
            "annotation_id": annotation_id,
            "project": project_name,
        }
    except requests.RequestException as e:
        logger.warning("Grafana annotation failed (non-fatal): %s", e)
        return {
            "status": "failed",
            "annotation_id": None,
            "error": str(e),
            "project": project_name,
        }


def delete_annotation(annotation_id: int, dry_run: bool = False) -> bool:
    """Rollback handler — delete a previously posted annotation.

    Used by :class:`DeploymentRollback` so a deploy that's rolled
    back doesn't leave a misleading "deployment success" marker on
    operator dashboards.

    Args:
        annotation_id: The ``id`` returned from
            :func:`post_deployment_annotation`.
        dry_run: No-op, returns True.

    Returns:
        ``True`` on HTTP 200 or 404 (both acceptable outcomes for a
        rollback — 404 means the annotation was already deleted or
        never committed).
        ``False`` on any other status, network failure, or missing
        token. Never raises.
    """
    if not isinstance(annotation_id, int):
        raise TypeError(f"annotation_id must be int (got {type(annotation_id).__name__})")

    if dry_run:
        logger.info("[DRY RUN] Would delete Grafana annotation id=%d", annotation_id)
        return True

    headers = _build_headers()
    if headers is None:
        logger.warning(
            "GRAFANA_SERVICE_ACCOUNT_TOKEN not set; cannot delete annotation id=%d",
            annotation_id,
        )
        return False

    # DELETE doesn't need a JSON body — strip the Content-Type header
    # to avoid a pointless preflight on Grafana's side.
    auth_only = {"Authorization": headers["Authorization"]}

    try:
        resp = requests.delete(
            f"{GRAFANA_URL}/api/annotations/{annotation_id}",
            headers=auth_only,
            timeout=_DEFAULT_TIMEOUT,
        )
        if resp.status_code in (200, 404):
            logger.info(
                "Deleted Grafana annotation id=%d (status=%d)",
                annotation_id,
                resp.status_code,
            )
            return True
        logger.warning(
            "Grafana delete annotation id=%d returned HTTP %d (non-fatal): %s",
            annotation_id,
            resp.status_code,
            resp.text[:200],
        )
        return False
    except requests.RequestException as e:
        logger.warning(
            "Grafana delete annotation id=%d failed (non-fatal): %s",
            annotation_id,
            e,
        )
        return False


__all__ = (
    "GRAFANA_URL",
    "DEPLOYMENT_TAG",
    "applies_to",
    "post_deployment_annotation",
    "delete_annotation",
)
