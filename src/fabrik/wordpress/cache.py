"""
Atomic multi-layer cache invalidation for deployed WordPress sites.

WordPress sites on Fabrik sit behind four cache layers, each with its own
invalidation mechanism:

    1. Cloudflare edge cache (tiered CDN)   → HTTP POST /zones/{id}/purge_cache
    2. Nginx FastCGI cache                  → rm -rf /var/cache/nginx/wp_cache/*
    3. Redis object cache                   → wp redis flush  (or wp cache flush)
    4. WordPress transients / rewrite rules → wp cache flush + wp rewrite flush

Clearing only one layer leaves stale content visible (the exact class of bug
that caused the ocoron.com "Nothing Found" incident on 2026-04-15). This
module wraps all four in a single call that never silently skips a step.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass, field

import httpx

from fabrik.drivers.wordpress import WordPressClient, get_wordpress_client

logger = logging.getLogger(__name__)

_CLOUDFLARE_API = "https://api.cloudflare.com/client/v4"


@dataclass
class FlushResult:
    """Per-layer result of an atomic cache flush."""

    cloudflare: str = "skipped"
    nginx: str = "skipped"
    redis: str = "skipped"
    wordpress: str = "skipped"
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _cloudflare_zone_id(domain: str) -> str | None:
    """Resolve Cloudflare zone ID for a domain via env var convention.

    Convention: CLOUDFLARE_ZONE_ID_<DOMAIN_SLUG> where DOMAIN_SLUG is the
    apex name uppercased with non-alphanumerics stripped.

        ocoron.com      -> CLOUDFLARE_ZONE_ID_OCORON
        my-site.com     -> CLOUDFLARE_ZONE_ID_MYSITE
    """
    apex = domain.split(".")[0] if "." in domain else domain
    slug = "".join(ch for ch in apex if ch.isalnum()).upper()
    return os.getenv(f"CLOUDFLARE_ZONE_ID_{slug}")


def _purge_cloudflare(domain: str) -> str:
    """Purge the Cloudflare zone for *domain*.

    Returns a short status string. Raises RuntimeError on hard failure.
    """
    token = os.getenv("CLOUDFLARE_API_TOKEN")
    zone_id = _cloudflare_zone_id(domain)

    if not token:
        return "skipped: CLOUDFLARE_API_TOKEN not set"
    if not zone_id:
        return f"skipped: no CLOUDFLARE_ZONE_ID_* mapping for {domain}"

    response = httpx.post(
        f"{_CLOUDFLARE_API}/zones/{zone_id}/purge_cache",
        json={"purge_everything": True},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Cloudflare purge failed: HTTP {response.status_code} {response.text[:200]}"
        )
    data = response.json()
    if not data.get("success"):
        raise RuntimeError(f"Cloudflare purge returned success=false: {data}")
    return "purged (zone-wide)"


def _purge_nginx_fastcgi(site_name: str, *, ssh_host: str = "vps") -> str:
    """Remove nginx FastCGI cache files on the VPS.

    Uses SSH to invoke ``docker exec`` because the cache lives inside the
    ``<site>-nginx-1`` container volume. Idempotent.
    """
    container = f"{site_name}-nginx-1"
    cmd = [
        "ssh",
        ssh_host,
        f"sudo docker exec {container} sh -c 'rm -rf /var/cache/nginx/wp_cache/* || true'",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"nginx cache purge failed: {result.stderr.strip()}")
    return f"cleared ({container}:/var/cache/nginx/wp_cache)"


def _flush_wordpress(wp: WordPressClient) -> tuple[str, str]:
    """Flush WP object cache + rewrite rules. Returns (redis_status, wp_status)."""
    redis_status = "skipped"
    wp_status = "skipped"

    # Try redis-specific flush first (cleaner), fall back to generic cache flush.
    try:
        wp.run("redis flush")
        redis_status = "flushed"
    except Exception as exc:  # wp-redis plugin may be absent
        logger.debug("wp redis flush unavailable: %s", exc)
        redis_status = "no redis plugin"

    wp.cache_flush()
    wp.rewrite_flush()
    wp_status = "cache + rewrite flushed"
    return redis_status, wp_status


def flush_all(domain: str, *, site_name: str | None = None, ssh_host: str = "vps") -> FlushResult:
    """Atomically invalidate every cache layer for *domain*.

    Args:
        domain: Public domain (e.g. ``ocoron.com``).
        site_name: Container prefix (defaults to ``domain.replace('.', '-')``).
        ssh_host: SSH alias used to reach the VPS for nginx cache purge.

    Returns:
        FlushResult with per-layer status. ``result.ok`` is True only if no
        layer raised. Individual layers that are "not applicable" (e.g. no
        Cloudflare zone mapped) report "skipped: ..." but do not fail.
    """
    result = FlushResult()
    site_name = site_name or domain.replace(".", "-")

    # 1. Cloudflare (edge) — furthest layer first so origin refresh is visible.
    try:
        result.cloudflare = _purge_cloudflare(domain)
    except Exception as exc:
        result.errors.append(f"cloudflare: {exc}")
        result.cloudflare = f"error: {exc}"

    # 2. Nginx FastCGI — second outermost; otherwise Cloudflare revalidates
    #    and repopulates with the stale origin response.
    try:
        result.nginx = _purge_nginx_fastcgi(site_name, ssh_host=ssh_host)
    except Exception as exc:
        result.errors.append(f"nginx: {exc}")
        result.nginx = f"error: {exc}"

    # 3 + 4. WordPress object cache (Redis) and rewrite rules.
    try:
        wp = get_wordpress_client(domain)
        redis_status, wp_status = _flush_wordpress(wp)
        result.redis = redis_status
        result.wordpress = wp_status
    except Exception as exc:
        result.errors.append(f"wordpress: {exc}")
        result.wordpress = f"error: {exc}"

    return result
