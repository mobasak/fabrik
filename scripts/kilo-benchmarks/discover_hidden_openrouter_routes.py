#!/usr/bin/env python3
"""Discover OpenRouter routes hidden from the public catalog endpoint.

OpenRouter's /api/v1/models returns 338 models (today). But the site has
~4200 URLs in its sitemap.xml, and additional alpha-tier routes
(openrouter/owl-alpha, openrouter/elephant-alpha, etc.) are accessible
via the API but DON'T appear in either:

    /api/v1/models
    /api/v1/models?disabled=true
    /sitemap.xml

The verifier's "absent from catalog → deprecate" heuristic kept hiding
them every nightly run until the operator hit one and asked why it
wasn't visible. This discovery script closes the gap.

DISCOVERY SOURCES (in order, idempotent across runs):

  1. OR's /sitemap.xml — gives ~4200 URLs. We mine for
     https://openrouter.ai/<provider>/<model> patterns and diff against
     the canonical /api/v1/models id set. Any URL NOT in the API is a
     candidate to ingest. For each candidate we fetch the model PAGE and
     parse pricing/context out of the rendered HTML (no public JSON
     endpoint for these). Catches `preview`/`beta` variants OR drops
     from /api/v1/models but still serves.

  2. Hardcoded `openrouter/*` allowlist — for the meta-router family
     (`auto`, `fusion`, `pareto-code`, `bodybuilder`, `owl-alpha`,
     `elephant-alpha`, `free`). These are stable OR-managed routes that
     OR hides from BOTH the API and the sitemap. Allowlist values are
     pulled from operator observation; expand as new ones surface.
     For each: if the row exists in DB, ensure it has via_openrouter=1
     and status='active'. If it doesn't exist, insert a stub with
     conservative defaults (will be enriched by the next verifier run).

The verifier already exempts `openrouter/*` from the delist-on-absence
path (commit ab75b575). This script provides the COMPLEMENTARY discovery
loop: not just "don't deprecate" but "actively find new ones".

Usage:
    python discover_hidden_openrouter_routes.py            # report only
    python discover_hidden_openrouter_routes.py --apply    # write fixes to DB

Idempotent: re-running the script is a no-op if no new routes appeared.

Per the operator question (2026-07-01): "are you sure we can extract
all models with all their columns?" — Phase 2 of the answer (Phase 1
was the richer-extraction migration at d1f37b02).
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
SITEMAP_URL = "https://openrouter.ai/sitemap.xml"
OR_API_URL = "https://openrouter.ai/api/v1/models"
MODEL_PAGE_FMT = "https://openrouter.ai/{model_id}"

# Hardcoded `openrouter/*` allowlist — known stable meta-routers + alpha
# tiers that don't appear in /api/v1/models OR /sitemap.xml. Expand as
# new ones are observed.
OPENROUTER_META_ROUTES = (
    "openrouter/auto",
    "openrouter/fusion",
    "openrouter/pareto-code",
    "openrouter/bodybuilder",
    "openrouter/owl-alpha",
    "openrouter/elephant-alpha",
    "openrouter/free",
)

_MODEL_URL_RE = re.compile(
    r"https://openrouter\.ai/([a-z0-9_-]+)/([a-z0-9._:-]+)$",
    re.IGNORECASE,
)
_SITEMAP_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")


def _today_utc_iso() -> str:
    return datetime.now(UTC).date().isoformat()


def _fetch(url: str, *, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "fabrik-discover/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _fetch_api_ids() -> set[str]:
    """Return the set of model IDs exposed by /api/v1/models."""
    import json

    payload = _fetch(OR_API_URL)
    data = json.loads(payload)
    return {m["id"] for m in data.get("data", []) if "id" in m}


def _mine_sitemap_model_urls() -> list[str]:
    """Mine sitemap.xml for URLs that match the `provider/model` pattern.

    Returns the list of `provider/model` strings (without the URL prefix).
    Filters out non-model paths (rankings, docs, etc.) by requiring two
    URL segments after the host.
    """
    sitemap = _fetch(SITEMAP_URL)
    out: list[str] = []
    for m in _SITEMAP_LOC_RE.finditer(sitemap):
        url = m.group(1).strip()
        url_match = _MODEL_URL_RE.match(url)
        if url_match:
            provider, model = url_match.group(1), url_match.group(2)
            # Filter out OR's own UI paths (rankings/X, terms-of-service, etc.)
            if provider in {
                "rankings",
                "docs",
                "blog",
                "settings",
                "credits",
                "tos",
                "privacy",
                "playground",
                "chat",
                "errors",
                "providers",
                "models",
                "uptime",
                "api",
                "datasets",
                "feedback",
                "research",
                "experiments",
                # Client-app showcases — NOT model routes:
                "apps",
                "works-with-openrouter",
                "use-cases",
                "integrations",
                "showcase",
                "compare",
                "author",
                "authors",
                "team",
                "about",
                "pricing",
                "press",
                "careers",
                "contact",
            }:
                continue
            out.append(f"{provider}/{model}")
    return out


def _meta_field(html: str, prop: str) -> str | None:
    """Pull a `<meta property=X content=Y>` or `<meta name=X content=Y>`."""
    m = re.search(
        rf'<meta\s+(?:property|name)=["\']{re.escape(prop)}["\']\s+content=["\']([^"\']*)["\']',
        html,
    )
    return m.group(1) if m else None


def _scrape_model_page(model_id: str) -> dict:
    """Fetch openrouter.ai/<model_id> and extract what we can from the SSR
    HTML — title, description, og:image. The page doesn't currently embed
    structured pricing JSON in the SSR; it lazy-loads via client-side fetch.
    We populate the minimum needed to make the row visible: name, description.
    Pricing stays 0 until OR exposes the route via /api/v1/models AND the
    next verifier run populates it.

    Returns dict with keys: name, description (may be empty if scrape failed).
    """
    try:
        html = _fetch(MODEL_PAGE_FMT.format(model_id=model_id), timeout=15)
    except Exception as e:
        return {"name": model_id, "description": "", "scrape_error": str(e)}
    title = _meta_field(html, "og:title") or _meta_field(html, "twitter:title") or model_id
    # Strip the trailing " | OpenRouter" branding
    title = re.sub(r"\s*\|\s*OpenRouter\s*$", "", title or "").strip() or model_id
    desc = _meta_field(html, "og:description") or _meta_field(html, "twitter:description") or ""
    return {"name": title, "description": desc.strip()}


def _existing_ids(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT id FROM agents").fetchall()}


def _row_exists_with_via_or(conn: sqlite3.Connection, mid: str) -> tuple[bool, int]:
    row = conn.execute("SELECT via_openrouter FROM agents WHERE id = ?", (mid,)).fetchone()
    if row is None:
        return False, 0
    return True, row[0] or 0


def discover(
    db_path: Path = DB_PATH, apply: bool = False, ingest_sitemap: bool = False, max_ingest: int = 50
) -> dict:
    """Find OR routes not currently in DB + restore openrouter/* meta-routes.

    --apply alone: ingest the 7 known openrouter/* meta-routes (safe — small allowlist).
    --apply --ingest-sitemap: ALSO ingest sitemap candidates (up to max_ingest per run).
    """
    api_ids = _fetch_api_ids()
    sitemap_ids = _mine_sitemap_model_urls()
    sitemap_id_set = set(sitemap_ids)
    today_iso = _today_utc_iso()

    conn = sqlite3.connect(db_path)
    try:
        db_ids = _existing_ids(conn)

        # Allowlist: ensure every known openrouter/* meta-route exists +
        # is active + has via_openrouter=1. Don't touch via_kilo (Kilo's
        # CLI is the authority on that).
        meta_routes_fixed: list[str] = []
        meta_routes_inserted: list[str] = []
        for mid in OPENROUTER_META_ROUTES:
            exists, via_or = _row_exists_with_via_or(conn, mid)
            if exists:
                if via_or != 1:
                    if apply:
                        conn.execute(
                            "UPDATE agents SET via_openrouter = 1, status = 'active', "
                            "discard_reason = NULL WHERE id = ?",
                            (mid,),
                        )
                    meta_routes_fixed.append(mid)
                # else: already correct
            else:
                # Insert a stub. Next verifier run with richer extraction
                # will refresh the fields when/if OR exposes pricing for it.
                if apply:
                    page_data = _scrape_model_page(mid)
                    conn.execute(
                        "INSERT INTO agents (id, api_id, name, provider, "
                        "input_cost_per_m, output_cost_per_m, "
                        "via_openrouter, via_kilo, "
                        "status, last_verified, description) "
                        "VALUES (?, ?, ?, ?, 0, 0, 1, 0, 'active', ?, ?)",
                        (
                            mid,
                            mid,
                            page_data.get("name") or mid,
                            "openrouter",
                            today_iso,
                            page_data.get("description") or "",
                        ),
                    )
                meta_routes_inserted.append(mid)

        # Sitemap mining: routes in sitemap (and not openrouter/*) that
        # aren't in the API OR the DB → candidate to ingest.
        sitemap_only_not_in_db = sorted(
            mid
            for mid in sitemap_id_set
            if mid not in api_ids and mid not in db_ids and not mid.startswith("openrouter/")
        )
        sitemap_ingested: list[str] = []
        if apply and ingest_sitemap:
            for mid in sitemap_only_not_in_db[:max_ingest]:
                page_data = _scrape_model_page(mid)
                provider = mid.split("/", 1)[0]
                try:
                    conn.execute(
                        "INSERT INTO agents (id, api_id, name, provider, "
                        "input_cost_per_m, output_cost_per_m, "
                        "via_openrouter, via_kilo, "
                        "status, last_verified, description) "
                        "VALUES (?, ?, ?, ?, 0, 0, 1, 0, 'active', ?, ?)",
                        (
                            mid,
                            mid,
                            page_data.get("name") or mid,
                            provider,
                            today_iso,
                            page_data.get("description") or "",
                        ),
                    )
                    sitemap_ingested.append(mid)
                except sqlite3.IntegrityError:
                    pass  # race-safe (concurrent insert)

        if apply:
            conn.commit()
    finally:
        conn.close()

    return {
        "api_total": len(api_ids),
        "sitemap_model_urls": len(sitemap_id_set),
        "sitemap_only_not_in_db": len(sitemap_only_not_in_db),
        "sitemap_ingested": sitemap_ingested,
        "meta_routes_checked": list(OPENROUTER_META_ROUTES),
        "meta_routes_fixed": meta_routes_fixed,
        "meta_routes_inserted": meta_routes_inserted,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--apply", action="store_true", help="Write to DB (meta-routes + fixes)")
    parser.add_argument(
        "--ingest-sitemap",
        action="store_true",
        help="Also ingest sitemap candidates (up to --max-ingest per run)",
    )
    parser.add_argument(
        "--max-ingest",
        type=int,
        default=50,
        help="Per-run sitemap ingest cap (avoid hammering OR with model-page fetches)",
    )
    args = parser.parse_args()

    report = discover(args.db, args.apply, args.ingest_sitemap, args.max_ingest)
    print(f"[discover] api_total:                {report['api_total']}")
    print(f"[discover] sitemap_model_urls:       {report['sitemap_model_urls']}")
    print(f"[discover] sitemap_only_not_in_db:   {report['sitemap_only_not_in_db']}")
    if report["sitemap_only_not_in_db"] and not args.apply:
        print("  (re-run with --apply to ingest)")
    if report["sitemap_ingested"]:
        for mid in report["sitemap_ingested"][:10]:
            print(f"  + sitemap-ingested: {mid}")
        if len(report["sitemap_ingested"]) > 10:
            print(f"  + ... {len(report['sitemap_ingested']) - 10} more")
    print(f"[discover] meta_routes_checked:      {len(report['meta_routes_checked'])}")
    print(f"[discover] meta_routes_fixed:        {len(report['meta_routes_fixed'])}")
    print(f"[discover] meta_routes_inserted:     {len(report['meta_routes_inserted'])}")
    for mid in report["meta_routes_fixed"]:
        print(f"  ~ fixed (set via_or=1): {mid}")
    for mid in report["meta_routes_inserted"]:
        print(f"  + inserted: {mid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
