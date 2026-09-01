---
activation: glob
globs: ["**/scrapers/**", "**/scraper*", "**/*scrape*", "**/*crawl*", "**/ingest/**", "**/connectors/**", "**/webhooks/**", "**/webhook*", "**/docs/reference/apis/**"]
description: External data sourcing — which mechanism (API/webhook/stream/file/DB/scrape) and which vendor or fabrik-lib module to reach for BEFORE writing an integration, and where the legal bypass line sits; pairs with 58-resilience (how to call safely)
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
a new integration. This pack is *what to reach for*; `58-resilience` is *how to call it safely*.

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

⚠️ **Two lanes, and conflating them is the mistake this ladder invites.** An MCP server is an
**agent-time** tool: it exists in your session, not in the deployed container. A worker, Beat job
or webhook receiver **cannot call one**. So:
- **Agent-time** (researching a source, grounding a plan, a one-off pull): MCP server first.
- **Shipped runtime** (anything that runs in a container): start at rung 2. The same vendors are
  reachable at runtime through env-keyed APIs — `fabrik-lib/web-tools` exists precisely for this
  (Exa / Brave / Firecrawl as runtime HTTP executors, without the dev-time pool).

1. **An existing MCP server** — AGENT-TIME ONLY (they handle auth + fetching):
   web/search `exa` · `brave-search` · `firecrawl` · scrape/browser `playwright` ·
   `chrome-devtools` · research `pubchem` · `fabrik-citation-verifier` · code-intel `serena`.
   ⚠️ **Check the roster before naming one — do not cite from memory.** The canonical list is
   `/opt/fabrik/docs/workstation/mcp-roster.md` plus the repo-level `.mcp.json`; the roster is
   SPLIT (user-level + per-repo), so `~/.claude.json` alone shows a subset and an agent that
   trusts it concludes most servers are absent. Probe liveness with
   `python3 /opt/fabrik/scripts/sysadmin/mcp_health.py`, which diffs assigned-vs-live.
2. **A `fabrik-lib` module** — vendor, don't hand-roll: `web-scrape` (httpx static +
   vps1 browserless for JS-rendered) · `doc-crawl` (sitemap + scoped BFS over an injected
   fetch) · `async-http-client` (pooled httpx + circuit breaker) · `captcha-solve`
   (pluggable, Anti-Captcha — ⚠️ a BYPASS capability, not a default; see § Hard constraints,
   "the bypass line") · `adaptive-dispatch` (learns which fetch strategy works per
   domain) · `web-tools` (env-keyed Exa/Brave/Firecrawl executors — the RUNTIME answer to rung 1)
   · `proxy-pool` (Postgres-backed proxy pool — ⚠️ same caveat as `captcha-solve`: a bypass
   capability, never a default). Check `/opt/fabrik-lib/README.md` for the real API.
3. **A direct vendor API** from the registry — **`/opt/fabrik/scripts/service_catalog.json`
   is the authoritative, secret-free list**, each vendor keyed by `category:` — `ai-llm`
   (⚠️ OpenRouter-only, see § Hard constraints), `ai-image`, `ai-audio`, `ai-translate`,
   `search`, `scrape`, `captcha`, `proxy`, `domains`, `email`, `storage`, `backup`,
   `research-data`, `media-stock`, `infra-platform`, `comms`, `dev-tools`, `unidentified`.
   **Derive the count and the category set from the FILE, never from this list** — the file has
   a non-dict `_README` key, so the guard is not optional:
   `python3 -c "import json,collections;d=json.load(open('scripts/service_catalog.json'));print(collections.Counter(v['category'] for v in d.values() if isinstance(v,dict)))"`.
   Grep it by `category` before adding any new vendor; detailed contracts live in
   `docs/reference/apis/**`. Key via env var, never in code.
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
- **Anything the fetch path shells out to must exist in the CONTAINER, not just in WSL dev**
  (12F-II) — a binary present locally `FileNotFoundError`s in the image. Route it to the right
  file: an OS binary (`yt-dlp`, a headless browser) is a Dockerfile `apt-get`/`COPY` concern; a
  Python library (`curl_cffi`) belongs in `requirements.txt`. Probe binaries with
  `shutil.which()` at startup so a missing one fails loudly at boot, not mid-ingest.
- **Respect the source** — robots, rate limits, and a real User-Agent; cache and dedup (the
  `web-scrape`/`doc-crawl` modules already do robots + caching + sha256 dedup). Three points
  where "be polite" is now too weak to plan against:
  - **robots.txt is a published IETF standard (RFC 9309), not a courtesy.** It still carries no
    direct enforcement, but ignoring it is routinely used as evidence of bad faith, and
    AI-specific user-agent directives (`GPTBot`, `CCBot`, `Google-Extended`, `anthropic-ai`,
    `PerplexityBot`) are the de-facto channel rights-holders use to reserve text-and-data-mining.
    Honour a TDM reservation even when your own UA is not the one named.
  - **⚠️ THE BYPASS LINE IS THE LEGAL LINE, and it runs straight through our own toolbox.**
    Reading a logged-out public page is a different act from defeating a control. The moment a
    pipeline solves a CAPTCHA, replays a session, rotates IPs to beat a block, or evades a hard
    rate limit, it leaves "public data" territory — and the live litigation wave targets the
    **tooling layer itself** (CAPTCHA solvers, anti-bot bypass, proxy services) as trafficking in
    circumvention technology, not just the scraper. `captcha-solve` and the catalog's `proxy` and
    `captcha` categories are therefore **capabilities, never defaults**: reach for them only where
    a human operator has decided the specific source warrants it, and say so in the plan.
  - **ToS binds you when you ACCEPTED it.** Terms shown on a page you never agreed to are weak
    against a logged-out fetcher; terms you click through, or accept by creating an account, are
    an ordinary contract and scraping in breach of them is a straightforward claim. So "we have
    an account there" changes the answer — check before assuming the public-page reasoning
    applies.
  - Scraping to TRAIN or fine-tune a model is a materially higher-risk category than scraping the
    same page for internal use, and it is regulated separately in the EU. If the output feeds a
    model, that is a `NEXT: operator decision`, not an engineering call.

---

## Doc Sync

A new external dependency → `docs/reference/apis/EXTERNAL_SYSTEMS.md` (+ the vendor's own
row) and `.env.example` for its key. A new vendor added to `service_catalog.json` is
hub-side (planning registry) — propose it, don't fork the catalog in a project.

**And if the ingester RUNS somewhere, the fleet-AI docs are part of the same change (D-065).**
Acquisition code is rarely a pure library: it lands as a worker, a Beat/cron job, or a webhook
receiver, and those are exactly the facts the fleet AI reads to know what to deploy and what to
schedule. So:
- a scheduled pull (Beat/cron) → the canonical jobs/intervals inventory in `docs/RESILIENCE.md`
  (the monitoring-schedule section — cite it by NAME, not by number: the number is not stable
  across projects, and one sampled repo has no such heading at all)
- a new long-running consumer/worker, or anything that changes how the service is deployed →
  `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md`
- an inbound webhook receiver → it is a served route: `15-api-contracts` applies. **Decide its
  auth posture explicitly, and the answer is not Authelia**: a provider (Stripe, GitHub, GlitchTip)
  cannot complete a forward-auth flow, so a receiver behind Authelia 302s the provider to a login
  page and silently drops every delivery. The posture is **public route + signature verification
  in the handler** (HMAC / shared secret, compared with `hmac.compare_digest`) — auth moves INTO
  the handler, never onto Authelia. It does not ride the health-path bypass either; give it its
  own explicit public route.
- a webhook whose provider needs a stable public URL → that is a deploy-time fact, not a code
  detail; state it in `docs/DEPLOYMENT.md` rather than leaving it in a handler docstring.
