"""Sitemap discovery — namespace-agnostic, recursive into sitemap indexes.

Uses the injected `fetch_fn` (e.g. web-scrape's `fetch_static`) so there's no
HTTP client coupling. Best-effort: a missing/!XML sitemap yields nothing.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable

__all__ = ["parse_sitemap", "discover_sitemap_urls"]

FetchFn = Callable[[str], str]


def _localname(tag: str) -> str:
    # strip the "{namespace}" prefix ElementTree prepends, so xmlns-qualified and
    # plain sitemaps both work.
    return tag.rsplit("}", 1)[-1].lower()


def parse_sitemap(xml_text: str) -> tuple[list[str], list[str]]:
    """Return (page_urls, child_sitemap_urls). A `<sitemapindex>` yields children."""
    # Sitemaps have no legitimate DTD. A DOCTYPE is the only way to declare internal
    # entities, so refusing it blocks "billion laughs" entity-expansion bombs from a
    # malicious crawled site (ElementTree expands internal entities). Prolog-only scan.
    if "<!doctype" in xml_text[:8192].lower():
        return [], []
    try:
        root = ET.fromstring(xml_text)
    except (ET.ParseError, ValueError):
        # ParseError = malformed XML; ValueError = str with an encoding declaration
        # on some Python versions. Best-effort: a bad sitemap yields nothing.
        return [], []
    locs = [
        e.text.strip()
        for e in root.iter()
        if _localname(e.tag) == "loc" and e.text and e.text.strip()
    ]
    if _localname(root.tag) == "sitemapindex":
        return [], locs
    return locs, []


def discover_sitemap_urls(
    fetch_fn: FetchFn, origins: list[str], *, max_sitemaps: int = 25
) -> list[str]:
    """Probe `<origin>/sitemap.xml` + `/sitemap_index.xml` per origin and recurse
    into indexes. Returns de-duped page URLs (order preserved).
    """
    queue: list[str] = []
    for origin in origins:
        base = origin.rstrip("/")
        queue.append(f"{base}/sitemap.xml")
        queue.append(f"{base}/sitemap_index.xml")

    fetched: set[str] = set()
    pages: list[str] = []
    seen_pages: set[str] = set()
    while queue and len(fetched) < max_sitemaps:
        sm = queue.pop(0)
        if sm in fetched:
            continue
        fetched.add(sm)
        try:
            xml_text = fetch_fn(sm)
        except Exception:  # noqa: BLE001 — injected fetcher may raise anything; best-effort
            continue
        page_urls, child_sitemaps = parse_sitemap(xml_text)
        for u in page_urls:
            if u not in seen_pages:
                seen_pages.add(u)
                pages.append(u)
        queue.extend(child_sitemaps)
    return pages
