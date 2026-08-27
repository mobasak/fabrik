"""Hacker News (Algolia) adapter — free, no auth, Tier-A. An opt-in exemplar of the adapter seam.

Opt in with ``adapters.use_free_adapters()`` (which registers it explicitly) or ``register(HnAlgoliaAdapter(),
product_types=PRODUCT_TYPES)``. The core never registers it, so it leaves the registry empty (Tier-C default).

Source: ``hn.algolia.com/api/v1/search?query={brand}&tags=comment`` → ``hits[].comment_text`` (full comment
text, free, ~10k req/hr). Dev/B2B-biased, so it serves only tech-ish product types.
"""

from __future__ import annotations

import html
import logging
import re
from typing import Any
from urllib.parse import quote_plus

from ..dossier import Signal

logger = logging.getLogger(__name__)

#: the product types this adapter serves (dev/B2B-biased source).
PRODUCT_TYPES = frozenset({"saas", "headless-api", "desktop", "extension", "docs"})

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _strip_html(text: str) -> str:
    return _WS.sub(" ", html.unescape(_TAG.sub(" ", text))).strip()


class HnAlgoliaAdapter:
    """Free/no-key HN comment search. ``fetch`` NEVER raises — any error → ``[]``."""

    name = "hn_algolia"
    key_env = ""  # free, no key → enabled whenever registered for the product type

    async def fetch(self, subject: str, *, client: Any, config: Any) -> list[Signal]:
        if not (subject or "").strip():  # guard None/blank OUTSIDE the try (never-raise)
            return []
        url = (
            "https://hn.algolia.com/api/v1/search"
            f"?query={quote_plus(subject)}&tags=comment&hitsPerPage=20"
        )
        try:
            resp = await client.get(url)
            if getattr(resp, "status_code", 200) != 200:
                return []
            data = resp.json()
        except Exception as exc:  # noqa: BLE001 — an adapter must never break the run
            logger.warning("competitor_intel.hn_algolia_fetch_failed cause=%s", type(exc).__name__)
            return []
        hits = data.get("hits") if isinstance(data, dict) else None
        if not isinstance(hits, list):
            return []
        out: list[Signal] = []
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            text = _strip_html(str(hit.get("comment_text") or ""))
            if not text:
                continue
            object_id = str(hit.get("objectID") or "").strip()
            src = f"https://news.ycombinator.com/item?id={object_id}" if object_id else ""
            out.append(
                Signal(
                    competitor=subject,
                    aspect="hn-comment",
                    sentiment="neutral",  # HN comments are unclassified mentions; the consumer may classify
                    quote=text[:500],
                    source_url=src,
                    tier="A",
                )
            )
        return out
