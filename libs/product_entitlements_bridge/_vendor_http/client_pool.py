"""Named singleton httpx.AsyncClient pool.

Each upstream service gets one long-lived AsyncClient with HTTP/2,
shared connection pool, and configurable defaults. No per-request
client creation — reduces TLS handshake cost and connection churn.

Usage:
    from libs.async_http_client.client_pool import get_client, close_all

    client = await get_client("my_api", headers={"Authorization": "Bearer ..."})
    r = await client.get("https://api.example.com/v1/data")

    # In FastAPI lifespan shutdown:
    await close_all()
"""

from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

_clients: dict[str, httpx.AsyncClient] = {}
_locks: dict[str, asyncio.Lock] = {}


async def get_client(
    name: str,
    *,
    headers: dict[str, str] | None = None,
    base_url: str = "",
    timeout: float = 30.0,
) -> httpx.AsyncClient:
    """Return the named singleton AsyncClient, creating it on first call.

    ``headers``, ``base_url``, and ``timeout`` are only used at creation
    time. Later calls with the same ``name`` return the existing client.

    Args:
        name: Identifier for this upstream (e.g. "payment_api", "search_api").
        headers: Default headers for all requests via this client.
        base_url: Prepended to all request URLs (e.g. "https://api.example.com").
        timeout: Default timeout in seconds.

    Returns:
        A long-lived httpx.AsyncClient with HTTP/2 (falls back to HTTP/1.1
        if h2 package is not installed).
    """
    cached = _clients.get(name)
    if cached is not None:
        return cached

    lock = _locks.setdefault(name, asyncio.Lock())
    async with lock:
        # Double-check after acquiring lock
        cached = _clients.get(name)
        if cached is not None:
            return cached

        try:
            client = httpx.AsyncClient(
                headers=headers or {},
                base_url=base_url,
                timeout=timeout,
                http2=True,
                follow_redirects=True,
            )
        except ImportError:
            # h2 extra not installed — fall back to HTTP/1.1
            logger.warning("http2_unavailable", extra={"upstream": name})
            client = httpx.AsyncClient(
                headers=headers or {},
                base_url=base_url,
                timeout=timeout,
                follow_redirects=True,
            )

        _clients[name] = client
        logger.info("http_client_created", extra={"upstream": name})
        return client


async def close_all() -> None:
    """Close every cached client. Call from FastAPI lifespan shutdown."""
    for name, client in list(_clients.items()):
        try:
            await client.aclose()
        except Exception as exc:
            logger.warning(
                "http_client_close_error",
                extra={"upstream": name, "error": str(exc)},
            )
    _clients.clear()
    _locks.clear()
