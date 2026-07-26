---
activation: glob
globs: ["**/scrapers/**", "**/scraper*", "**/*scrape*", "**/*crawl*", "**/ingest/**", "**/connectors/**", "**/webhooks/**", "**/webhook*", "**/docs/reference/apis/**"]
description: External data sourcing — which mechanism (API/scrape/webhook/file/stream/MCP) and which vendor to reach for BEFORE writing an integration; pairs with 58-resilience (how to call safely)
trigger: glob
---
<!-- CONSUMER: Coding agents (all) + Traycer (tech-plan step)
     GOAL: Pick the RIGHT acquisition mechanism + an existing vendor/module before hand-rolling an integration.
     AGENT USAGE: Walk the ladder top-down; stop at the first that fits. Cite the mechanism + source in the plan.
     PAIRS WITH: 58-resilience (every call gets timeout+retry+circuit-breaker) · 15-api-contracts (serving APIs, the inbound side). -->

# External Data Sourcing

**Activation:** Glob — code that pulls data from an outside system (scrapers, ingesters,
API clients, connectors, webhook handlers).
**Purpose:** Choose the acquisition MECHANISM and reuse an EXISTING source before writing
a new integration. This pack is *what to reach for*; `58-resilience` is *how to call it
safely* (every external call still needs timeout + retry + circuit-breaker + fallback).

---

## The one decision (walk top-down, stop at the first that fits)

```
Does the provider give you an interface?
├─ YES, structured request/response  → REST or GraphQL API        ← always prefer
├─ YES, they push on events          → Webhook  (or SSE/WebSocket/queue for a stream)
├─ YES, but it's bulk                → File transfer (SFTP / S3-bucket / CSV-Parquet dump)
├─ YES, it's their database          → Direct DB connection (partner/internal only)
└─ NO interface at all               → Scrape:  static httpx → JS-rendered browserless → browser automation
```

Second axis: **pull** (you ask: API / scrape / file-fetch) vs **push** (they send:
webhook / stream). Prefer pull for data; reserve push (webhooks) for events/ops.

**Never scrape when an API exists** — an API is stable, rate-limited by contract, and
legal-by-design; a scraper breaks on markup change and may violate ToS.

---

## Reach-for order in Fabrik (reuse before build — 12-Factor II)

1. **An existing MCP server** if one covers it (they handle auth + fetching):
   web/search `exa` · `brave-search` · `firecrawl` · scrape/browser `playwright` ·
   `puppeteer` · `chrome-devtools` · code/docs `github` · `context7` · research
   `pubchem` · `fabrik-citation-verifier`. Full live list: `~/.claude.json` mcpServers.
2. **A `fabrik-lib` module** — vendor, don't hand-roll: `web-scrape` (httpx static +
   vps1 browserless for JS-rendered) · `doc-crawl` (sitemap + scoped BFS over an injected
   fetch) · `async-http-client` (pooled httpx + circuit breaker) · `captcha-solve`
   (pluggable, Anti-Captcha) · `adaptive-dispatch` (learns which fetch strategy works per
   domain). Check `/opt/fabrik-lib/README.md` for the real API.
3. **A direct vendor API** from the registry — **`/opt/fabrik/scripts/service_catalog.json`
   is the authoritative, secret-free list** (~90 vendors, each keyed by `category:` — `ai-llm`,
   `ai-image`, `ai-audio`, `ai-translate`, `search`, `scrape`, `captcha`, `proxy`,
   `domains`, `email`, `storage`, `backup`, `research-data`, `media-stock`,
   `infra-platform`, `comms`, `dev-tools`, `payments`). Grep it by `category` before adding
   any new vendor; detailed contracts live in `docs/reference/apis/**`. Key via env var, never in code.
4. **A CLI** last (`gh`, `fabrik`) — ops/scripting, rarely app-data ingestion.

A capability that clears none of these is a genuine new integration — justify it in the
plan (which mechanism, which vendor, cited limits/pricing) and check the vendor exists.

---

## Hard constraints (a mechanism/vendor choice that trips one is DEAD ON ARRIVAL)

- **LLM data = OpenRouter ONLY** — never a direct vendor LLM SDK (`openai`, `@anthropic-ai/sdk`).
  Non-LLM vendor APIs are fine directly.
- **Vendor keys are env vars** (`os.getenv`), never constants; the repo must stay open-sourceable (12F-III).
- **Every external call wraps in the `58-resilience` contract** — timeout + retry/backoff +
  circuit-breaker + graceful fallback. No bare `requests.get`.
- **Shelled-out fetch binaries must be installed + pinned in the Dockerfile** (12F-II) — an
  `impersonated-fetch`/`curl_cffi`/`yt-dlp` present in WSL dev `FileNotFoundError`s in the
  container. Declare it in `requirements.txt`, probe with `shutil.which()` at startup.
- **Respect the source** — robots/ToS, rate limits, and a real User-Agent; cache and
  dedup (the `web-scrape`/`doc-crawl` modules already do robots + caching + sha256 dedup).

---

## Doc Sync

A new external dependency → `docs/reference/apis/EXTERNAL_SYSTEMS.md` (+ the vendor's own
row) and `.env.example` for its key. A new vendor added to `service_catalog.json` is
hub-side (planning registry) — propose it, don't fork the catalog in a project.
