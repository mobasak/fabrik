"""Apple App Store RSS reviews adapter — free, no key, Tier-A. An opt-in exemplar of the adapter seam.

Opt in with ``adapters.use_free_adapters()`` (which registers it explicitly). Resolves the app id from the
subject via the iTunes Search API, then fetches the customer-reviews RSS feed. Handles the empty-feed case
gracefully (a feed with no reviews has no ``entry`` list, or only the app-info entry). ``fetch`` NEVER
raises → ``[]`` on any error.

Sources: ``itunes.apple.com/search?term={brand}&entity=software`` → ``results[0].trackId``; then
``itunes.apple.com/{cc}/rss/customerreviews/page=1/id={id}/sortby=mostrecent/json`` → ``feed.entry[]``
(~500/country cap; per-app flakiness). Country via ``config['apple_country']`` (default ``us``).
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote_plus

from ..dossier import Signal

logger = logging.getLogger(__name__)

_CC = re.compile(r"^[a-z]{2}$")

#: the product types this adapter serves.
PRODUCT_TYPES = frozenset({"mobile-app", "desktop"})


def _label(value: Any) -> str:
    """Apple RSS wraps scalars as ``{"label": "..."}`` (sometimes a list of them). Extract the text."""
    if isinstance(value, dict):
        return str(value.get("label") or "")
    if isinstance(value, list) and value:
        return _label(value[0])
    return str(value or "")


def _rating_to_sentiment(rating_label: str) -> str:
    try:
        r = int(rating_label)
    except (ValueError, TypeError):
        return "neutral"
    if r <= 2:
        return "negative"
    if r >= 4:
        return "positive"
    return "neutral"


class AppleRssAdapter:
    name = "apple_rss"
    key_env = ""  # free, no key

    async def fetch(self, subject: str, *, client: Any, config: Any) -> list[Signal]:
        if not (subject or "").strip():  # guard None/blank OUTSIDE the try (never-raise)
            return []
        cc = "us"
        if isinstance(config, dict):
            candidate = str(config.get("apple_country") or "").strip().lower()
            if _CC.match(candidate):  # allowlist an ISO alpha-2; a malformed value can't inject into the URL
                cc = candidate
        try:
            search = await client.get(
                f"https://itunes.apple.com/search?term={quote_plus(subject)}&entity=software&limit=1&country={cc}"
            )
            sdata = search.json()
            results = sdata.get("results") if isinstance(sdata, dict) else None
            if not isinstance(results, list) or not results or not isinstance(results[0], dict):
                return []
            app_id = str(results[0].get("trackId") or "").strip()
            if not app_id:
                return []
            reviews = await client.get(
                f"https://itunes.apple.com/{cc}/rss/customerreviews/page=1/id={app_id}/sortby=mostrecent/json"
            )
            data = reviews.json()
        except Exception as exc:  # noqa: BLE001 — an adapter must never break the run
            logger.warning("competitor_intel.apple_rss_fetch_failed cause=%s", type(exc).__name__)
            return []

        feed = data.get("feed") if isinstance(data, dict) else None
        entries = feed.get("entry") if isinstance(feed, dict) else None
        if isinstance(entries, dict):  # a single-review feed can come back as one dict, not a list
            entries = [entries]
        if not isinstance(entries, list):  # empty feed → no reviews
            # ⚠️ Distinguish "no reviews" from "we could not read the response". A drifted payload
            # (`feed` or `entry` not the documented shape) discards the whole fetch, and the
            # orchestrator has no channel for a whole-fetch discard — so this line is the only signal
            # an operator gets. `None` here is the ordinary empty-feed case and is NOT worth a warning.
            if data is not None and not isinstance(feed, dict):
                logger.warning(
                    "competitor_intel.apple_rss_payload_drift got=%s", type(feed).__name__
                )
            else:
                # INFO, not WARNING — an app with no reviews is ordinary and must not cry wolf. But it
                # must not be TOTALLY silent either: measured 2026-08-28, this endpoint returns an
                # empty feed for even the largest apps (see the grounding note below), so an operator
                # getting zero Tier-A signals needs one line telling them the fetch succeeded and the
                # feed was simply empty — rather than inferring a bug in their own wiring.
                logger.info("competitor_intel.apple_rss_empty_feed app_id=%s cc=%s", app_id, cc)
            return []
        out: list[Signal] = []
        app_url = f"https://apps.apple.com/{cc}/app/id{app_id}"
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            content = _label(entry.get("content"))
            rating = _label(entry.get("im:rating"))
            if not content:  # no review text → nothing to mine
                continue
            # ⚠️ `not rating` USED TO BE a second disjunct here, as a proxy for "this is the app-info
            # entry". It is the wrong test: rating-unknown is first-class EVERYWHERE else in this module
            # (`rating_num=None` below, `source_weight(rating=None)` → 0.8), so the proxy silently
            # discarded every genuine review Apple returns without a rating. But it could not simply be
            # DELETED either — that would admit the app-info entry, whose `content` is the vendor's own
            # marketing copy, as a Tier-A "review" of itself.
            # So: admit an entry only when it POSITIVELY identifies as a customer review — it carries at
            # least one of `author` / `im:version` / `im:rating`, which the catalogue app-info entry does
            # not have. Everything else is skipped.
            # ⚠️ GROUNDING LIMIT, stated because the fixture cannot stand in for the feed: this could NOT
            # be verified against a live payload. On 2026-08-28 the customerreviews endpoint returned a
            # well-formed feed envelope with NO `entry` key at all for every probe — 4 app ids
            # (284882215, 310633997, 324684580, 544007664) × json/xml × us/gb × 4 URL spellings incl.
            # Apple's documented `sortBy=mostRecent` casing. So the app-info entry's live shape is
            # UNCONFIRMED, and under that uncertainty the test must fail CLOSED.
            # ⚠️ IT DID NOT. The first version asked the NEGATIVE question — "does it carry catalogue
            # fields AND no review markers?" — which short-circuits to False for an entry carrying
            # NEITHER, admitting it. Review caught it and live-reproduced the exact laundering this
            # rewrite exists to prevent: `{"content": {"label": "This is the best app description ever,
            # buy now!"}, "id": ...}` became a Tier-A `Signal`. A negative test cannot fail safe on an
            # unknown shape, because an unknown shape answers "no" to every question you ask about it.
            # The positive test also SUBSUMES the catalogue check: a catalogue entry has no review
            # marker, so it is skipped without naming its fields at all.
            if not any(k in entry for k in ("author", "im:version", "im:rating")):
                continue
            # each review's own permalink (entry.id label) → a DISTINCT source_url per review, so N reviews
            # can cross-source-corroborate a BEAT theme. A shared app_url would collapse to one source.
            review_url = _label(entry.get("id")) or app_url
            try:
                rating_num: float | None = float(rating)
            except (ValueError, TypeError):
                rating_num = None
            out.append(
                Signal(
                    competitor=subject,
                    aspect="app-review",
                    sentiment=_rating_to_sentiment(rating),
                    quote=content[:500],
                    source_url=review_url,
                    tier="A",
                    rating=rating_num,  # feeds source_weight's extreme-rating discount
                )
            )
        return out
