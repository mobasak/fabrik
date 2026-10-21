"""Framework-free doc crawler: sitemap discovery + scoped BFS + incremental dedup.

The fetcher is INJECTED (`fetch_fn: str -> html`) so this composes web-scrape (or
anything) without importing it — vendor-don't-import done right.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag

from .classify import classify_page
from .dedup import IncrementalIndex, content_hash
from .readability import html_to_markdown
from .sitemap import discover_sitemap_urls
from .types import CrawlProfile, DocPage

__all__ = ["Crawler"]

FetchFn = Callable[[str], str]

_DEFAULT_PORTS = {"http": "80", "https": "443"}


def _canon_netloc(scheme: str, netloc: str) -> str:
    """Drop an explicit default port so `host:443`/`host:80` match the bare host.
    Leaves a non-default port and bare hosts (incl. IPv6) untouched.
    """
    host, sep, port = netloc.rpartition(":")
    if sep and port == _DEFAULT_PORTS.get(scheme):
        return host
    return netloc


@dataclass
class Crawler:
    """Crawl one doc site into `DocPage`s. `crawl()` is a generator; the consumer
    owns storage and may persist `index` between runs for incremental crawls.
    """

    fetch_fn: FetchFn
    profile: CrawlProfile
    index: IncrementalIndex = field(default_factory=IncrementalIndex)
    # URLs successfully fetched in the most recent crawl(); pass to index.prune()
    # afterwards to drop entries for pages that have since disappeared.
    seen_urls: set[str] = field(default_factory=set)

    def crawl(self) -> Iterator[DocPage]:
        domains = self.profile.allowed_domains or self._derive_domains()
        domain_set = {d.lower() for d in domains}
        seeds = list(self.profile.start_urls)
        seeds += discover_sitemap_urls(self.fetch_fn, self._origins())

        queue: deque[tuple[str, int]] = deque()
        for u in seeds:
            queue.append((self._normalize(u), 0))
        visited: set[str] = set()
        self.seen_urls = set()
        fetched = 0  # bound TOTAL fetches (incl. unchanged re-crawls), not just yields

        while queue and fetched < self.profile.max_pages:
            url, depth = queue.popleft()
            if url in visited:
                continue
            visited.add(url)
            if not self._in_scope(url, domain_set):
                continue
            try:
                html = self.fetch_fn(url)
            except Exception:  # noqa: BLE001 — injected fetcher may raise anything
                continue
            fetched += 1
            self.seen_urls.add(url)

            links = self._extract_links(url, html, domain_set)
            if depth < self.profile.max_depth:
                for link in links:
                    if link not in visited:
                        queue.append((link, depth + 1))

            markdown = html_to_markdown(html)
            digest = content_hash(markdown)
            if self.index.should_skip(url, digest):
                continue  # unchanged since last crawl — links already queued above
            self.index.record(url, digest)
            yield DocPage(
                url=url,
                depth=depth,
                html=html,
                markdown=markdown,
                content_hash=digest,
                classify=classify_page(url, html),
                links=links,
            )

    # ── helpers ───────────────────────────────────────────────────────────
    def _derive_domains(self) -> list[str]:
        domains: set[str] = set()
        for u in self.profile.start_urls:
            p = urlparse(u)
            if p.netloc:
                domains.add(_canon_netloc(p.scheme, p.netloc))
        return list(domains)

    def _origins(self) -> list[str]:
        origins: list[str] = []
        seen: set[str] = set()
        for u in self.profile.start_urls:
            p = urlparse(u)
            if p.scheme and p.netloc:
                origin = f"{p.scheme}://{p.netloc}"
                if origin not in seen:
                    seen.add(origin)
                    origins.append(origin)
        return origins

    def _normalize(self, url: str) -> str:
        p = urlparse(url)
        query = "" if self.profile.strip_query else p.query
        netloc = _canon_netloc(p.scheme, p.netloc)  # default ports -> bare host
        return urlunparse(
            (p.scheme, netloc, p.path or "/", p.params, query, "")
        )  # drop fragment

    def _in_scope(self, url: str, domains: set[str]) -> bool:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False
        if p.netloc.lower() not in domains:
            return False
        path = p.path.lower()
        return not path.endswith(self.profile.skip_extensions)

    def _extract_links(self, base_url: str, html: str, domains: set[str]) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        anchors: list[Tag] = []
        for selector in self.profile.nav_selectors:  # nav links first (crawl priority)
            for node in soup.select(selector):
                anchors.extend(
                    a for a in node.find_all("a", href=True) if isinstance(a, Tag)
                )
        anchors.extend(a for a in soup.find_all("a", href=True) if isinstance(a, Tag))

        out: list[str] = []
        seen: set[str] = set()
        for a in anchors:
            href = a.get("href")
            if not isinstance(href, str) or not href.strip():
                continue
            absolute = self._normalize(urljoin(base_url, href.strip()))
            if absolute in seen:
                continue
            seen.add(absolute)
            if self._in_scope(absolute, domains):
                out.append(absolute)
        return out
