"""Fabrik notification helpers.

Fire-and-forget webhook calls to n8n. All calls are best-effort:
failures are logged as warnings and never propagate to the caller.

Required env vars (optional — notifications silently skipped if absent):
    N8N_WEBHOOK_DEPLOY   — POST target for deploy success/failure events
    N8N_WEBHOOK_CONTENT  — POST target for content publish summary events
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _post(webhook_url: str, payload: dict[str, Any]) -> None:
    """Send a JSON POST to webhook_url. Never raises."""
    try:
        import httpx

        timeout = float(os.getenv("N8N_WEBHOOK_TIMEOUT", "5"))
        httpx.post(webhook_url, json=payload, timeout=timeout)
        logger.debug("Webhook sent to %s: %s", webhook_url, payload.get("event"))
    except Exception as exc:
        logger.warning("Webhook delivery failed (%s): %s", webhook_url, exc)


def notify_deploy(
    *,
    project: str,
    domain: str,
    success: bool,
    url: str | None = None,
    error: str | None = None,
    error_step: str | None = None,
) -> None:
    """Fire deploy success/failure event to N8N_WEBHOOK_DEPLOY.

    Args:
        project: Project/service name from spec.
        domain: Target domain.
        success: True if deployment completed successfully.
        url: Deployed URL (success only).
        error: Error message (failure only).
        error_step: Pipeline step where failure occurred.
    """
    webhook = os.getenv("N8N_WEBHOOK_DEPLOY")
    if not webhook:
        return

    _post(
        webhook,
        {
            "event": "deploy.success" if success else "deploy.failure",
            "project": project,
            "domain": domain,
            "url": url,
            "error": error,
            "error_step": error_step,
        },
    )


def notify_content(
    *,
    domain: str,
    published: int,
    failed: int,
    dry_run: bool = False,
) -> None:
    """Fire content publish summary event to N8N_WEBHOOK_CONTENT.

    Args:
        domain: Target domain.
        published: Number of briefs successfully published.
        failed: Number of briefs that failed.
        dry_run: Whether this was a dry-run.
    """
    webhook = os.getenv("N8N_WEBHOOK_CONTENT")
    if not webhook:
        return

    _post(
        webhook,
        {
            "event": "content.published",
            "domain": domain,
            "published": published,
            "failed": failed,
            "dry_run": dry_run,
        },
    )
