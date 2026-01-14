"""Minimal FastAPI app exposing dependency-aware health checks.

The health endpoint exercises real dependencies (Coolify + DNS manager)
so Coolify healthchecks and Uptime Kuma can detect upstream outages.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

from fabrik.config import ensure_directories
from fabrik.drivers.coolify import CoolifyClient
from fabrik.drivers.dns import DNSClient

logger = logging.getLogger(__name__)

app = FastAPI(title="Fabrik", version="0.1.0")


def _normalize_status(payload: Any) -> tuple[str, dict[str, Any]]:
    """Return normalized health status and detail dictionary."""

    if isinstance(payload, dict):
        status_value = str(payload.get("status", "")).lower()
        healthy = status_value in {"ok", "healthy", "pass", "success"}
        details = payload
    elif isinstance(payload, bool):
        healthy = payload
        details = {"status": "healthy" if payload else "unhealthy"}
    elif isinstance(payload, str):
        healthy = payload.lower() in {"ok", "healthy", "pass", "success"}
        details = {"status": payload}
    else:
        healthy = False
        details = {"status": "unknown", "detail": payload}

    return ("healthy" if healthy else "unhealthy"), details


def check_coolify() -> dict[str, Any]:
    """Ping Coolify's health endpoint.

    Returns a dict with `status` (healthy/unhealthy) and details/error.
    """

    try:
        client = CoolifyClient()
        response = client.health()
        normalized, details = _normalize_status(response)
        return {"status": normalized, "details": details}
    except Exception as exc:  # noqa: BLE001 - health must surface issues
        logger.warning("Coolify health check failed: %s", exc)
        return {"status": "unhealthy", "error": str(exc)}


def check_dns() -> dict[str, Any]:
    """Ping DNS manager health endpoint."""

    try:
        client = DNSClient()
        response = client.health()
        normalized, details = _normalize_status(response)
        return {"status": normalized, "details": details}
    except Exception as exc:  # noqa: BLE001 - health must surface issues
        logger.warning("DNS health check failed: %s", exc)
        return {"status": "unhealthy", "error": str(exc)}


@app.on_event("startup")
async def _startup() -> None:
    """Ensure runtime directories exist for logs/cache."""

    ensure_directories()


@app.get("/health")
async def health() -> JSONResponse:
    """Aggregate health across Coolify and DNS dependencies."""

    coolify_status = check_coolify()
    dns_status = check_dns()

    checks = {"coolify": coolify_status, "dns": dns_status}
    all_healthy = all(entry.get("status") == "healthy" for entry in checks.values())

    body = {
        "service": "fabrik",
        "status": "ok" if all_healthy else "degraded",
        "checks": checks,
    }

    return JSONResponse(
        status_code=status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=body,
    )


@app.get("/")
async def root() -> dict[str, str]:
    """Simple readiness endpoint."""

    return {"service": "fabrik", "status": "ready"}
