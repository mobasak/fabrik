"""Incremental crawl state — SHA256 content-hash skip + stale prune.

The index is a plain dict the consumer owns and persists (JSON, a column, …) —
no DB coupling.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

__all__ = ["IncrementalIndex", "content_hash"]


def content_hash(text: str) -> str:
    """Stable SHA256 of the page's rendered content (markdown)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class IncrementalIndex:
    """url -> content_hash. `should_skip` is True when a page is unchanged."""

    hashes: dict[str, str] = field(default_factory=dict)

    def should_skip(self, url: str, new_hash: str) -> bool:
        return self.hashes.get(url) == new_hash

    def record(self, url: str, new_hash: str) -> None:
        self.hashes[url] = new_hash

    def prune(self, seen_urls: set[str]) -> list[str]:
        """Drop URLs not present in `seen_urls` (gone since last crawl). Returns them."""
        stale = [u for u in self.hashes if u not in seen_urls]
        for u in stale:
            del self.hashes[u]
        return stale

    def to_dict(self) -> dict[str, str]:
        return dict(self.hashes)

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> IncrementalIndex:
        return cls(dict(data))
