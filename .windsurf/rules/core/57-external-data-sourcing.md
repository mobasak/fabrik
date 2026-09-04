---
activation: glob
globs: ["**/scrapers/**", "**/scraper*", "**/*scrape*", "**/*crawl*", "**/ingest/**", "**/connectors/**", "**/webhooks/**", "**/webhook*", "**/docs/reference/apis/**"]
description: External data sourcing — which mechanism (API/webhook/stream/file/DB/scrape) and which vendor or fabrik-lib module to reach for BEFORE writing an integration, and where the legal bypass line sits; pairs with 58-resilience (how to call safely)
trigger: glob
---
<!-- CONSUMER: Coding agents (all) + Traycer (tech-plan step)
     GOAL: Pick the RIGHT acquisition mechanism + an existing vendor/module before hand-rolling an integration.
     AGENT USAGE: Walk the ladder top-down; stop at the first that fits. Cite the mechanism + source in the plan.
                  Fill the twelve-field Capability Profile BEFORE designing — it is the input 58's failure-class map consumes.
     PAIRS WITH: 58-resilience (every call gets timeout+retry+circuit-breaker; its coverage map bounds what YOU can bound —
                 this pack's profile is what makes the VENDOR-side classes detectable) · 15-api-contracts (serving APIs, the inbound side). -->

# External Data Sourcing

**Activation:** Glob — code that pulls data from an outside system (scrapers, ingesters,
API clients, connectors, webhook handlers). ⚠️ `58-resilience` does NOT auto-load on
`connectors/`, `ingest/`, `webhooks/` or `scrapers/` paths — when this pack fires, read 58
explicitly; every rule below that says "the 58 contract" assumes you have.
**Purpose:** Choose the acquisition MECHANISM, reuse an EXISTING source before writing a new
integration, and record the vendor's envelope so the connector can **recover from vendor-side failure
without a human**. This pack is *what to reach for* and *what the vendor's contract is*;
`58-resilience` is *how to call it safely*. A connector built to both must autorecover from every
failure the vendor can cause — the profile below is what makes those failures detectable at all.

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

"Stop at the first that fits" chooses the INTERFACE, not the plan: when two rungs both fit
(REST *and* a bulk dump), **profile both before choosing** — fields 5 and 6 are what make a
100× cheaper backfill visible, and they are gathered after the choice only if you let them be.

**Never scrape when an API exists** — an API is a contract you can PROFILE (limits, resume,
deprecation channel) and be authorised under; a scraper has no contract, breaks on markup
change, and may violate ToS. (APIs still deprecate and break — field 10 exists because they do.)

---

## Reach-for order in Fabrik (reuse before build)

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
   ⚠️ **Check the roster before naming one — do not cite from memory**: the roster is SPLIT
   (user-level + per-repo `.mcp.json`), canonical at `/opt/fabrik/docs/workstation/mcp-roster.md`,
   probed by `python3 /opt/fabrik/scripts/sysadmin/mcp_health.py`.
2. **A `fabrik-lib` module** — vendor, don't hand-roll: `web-scrape` (httpx static +
   vps1 browserless for JS-rendered) · `doc-crawl` (sitemap + scoped BFS over an injected
   fetch) · `async-http-client` (pooled httpx + circuit breaker) · `captcha-solve`
   (pluggable, Anti-Captcha — ⚠️ a BYPASS capability, not a default; see § Hard constraints,
   "the bypass line") · `adaptive-dispatch` (learns which fetch strategy works per
   domain) · `web-tools` (env-keyed Exa/Brave/Firecrawl executors — the RUNTIME answer to rung 1)
   · `proxy-pool` (Postgres-backed proxy pool — ⚠️ same caveat as `captcha-solve`: a bypass
   capability, never a default) · `api-quota` (`QuotaTracker` parses rate-limit headers, persists
   quota state and gates calls at the cap; `KeyPool` rotates across many keys — the RUNTIME half of
   profile fields 1, 2, 7 and 9) · `webhooks` (**outgoing** delivery with HMAC signing — it does
   not receive; a receiver is yours to write per § Doc Sync). Check `/opt/fabrik-lib/README.md`
   for the real API. ⚠️ **A module that already retries IS the retry layer** — `web-scrape`
   retries 5xx/429 with backoff, `async-http-client` carries the breaker — wrapping it in your
   own `@retry` is the ×27 amplification `58` bans.
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
plan (which mechanism, which vendor) and check the vendor exists.

---

## The Capability Profile — know the envelope BEFORE you design against it

**Every external system gets a profile before code is written** (where it lives: § Doc Sync).
Discovering any of these after the fact means rewriting the integration, not tuning it.

Answer all twelve. **"Unknown" is a legitimate answer — an unstated one is not**: write
`UNKNOWN — <what you tried>`, so the next reader can see which numbers are real.
**An UNKNOWN never waives the design decision — design to the conservative reading**: unknown cap
behaviour ⇒ assume silent truncation and verify counts yourself; unknown idempotency ⇒ assume
non-idempotent; unknown resume ⇒ checkpoint on your side; unknown health signal ⇒ treat every
5xx burst as *possibly them* and pause rather than hammer; unknown key expiry ⇒ rotate on a
schedule anyway; unknown deprecation channel ⇒ watch the headers; unknown schema stability ⇒
validate strictly at the boundary.

| # | Field | Why it changes the design |
|---|---|---|
| 1 | **Limits & quota** — req/min, req/day, tokens, GB, rows; what resets, and WHEN | decides batch size and schedule |
| 2 | **Behaviour AT the cap** — 429 + `Retry-After`? hard block? silent truncation? billing overage? | decides whether you back off or must stop; silent truncation is the dangerous one — it looks like success |
| 3 | **Concurrency & parallelism** — max in-flight, and scoped to WHAT (key / account / IP / endpoint) | decides worker count; a per-IP cap means scaling workers buys nothing |
| 4 | **Identity posture** — limits per-key, per-account or per-IP? does the ToS permit multiple accounts/orgs — **cite the clause + URL, or UNKNOWN** | decides whether horizontal scale is even available — see the ⚠️ below |
| 5 | **Failure & resume** — which failures are retryable, is the call IDEMPOTENT, is there a cursor / checkpoint / resumable upload, and what is the smallest unit you can resume FROM | decides whether a long ingest is feasible at all, or must restart from zero |
| 6 | **Cost model** — per what unit, minimum billing increment, free tier, and what makes it SPIKE | decides whether the design is affordable at real volume, not at test volume |
| 7 | **Usage observability** — can you read your own consumption/remaining quota programmatically? | decides whether you can shed load BEFORE the wall or only discover it by failing |
| 8 | **Health signal** — how do you learn THEY are down, machine-readably? a status API (the Statuspage convention: public read-only `/api/v2/status.json`, `incidents/unresolved.json`, `scheduled-maintenances/upcoming.json`), a health endpoint, an incident feed; is maintenance announced ahead? | decides whether a 5xx burst reads as *pause and wait* or *my bug, stop retrying* — and whether you can pre-pause for announced maintenance instead of discovering it as an outage |
| 9 | **Credential lifecycle** — does the key/token EXPIRE, on what schedule; can it be rotated with an overlap (two keys valid at once) or only by a hard cut; what does an expired key LOOK like (401? 403? a silent empty 200?) | decides whether rotation can be automated at all, and whether the connector can even tell a dead credential from a dead vendor — an expired key is the failure a retry loop can never fix |
| 10 | **Interface lifecycle** — versioning scheme; deprecation channel; does the vendor emit `Deprecation` / `Sunset` headers (RFC 9745 / RFC 8594) or a `Link rel="deprecation"` / `successor-version`; notice period; is the same key usable on the successor | decides whether retirement is detectable at RUNTIME or only by someone reading an email — an endpoint that dies on a date is the one failure no retry recovers; the only autorecovery is migrating before it |
| 11 | **Data contract** — the response schema pinned at profile time; what the vendor changes WITHOUT a version bump (nullable flips, new enum values, added fields, pagination shape); freshness/lag and eventual-consistency window; how deletion shows (tombstone vs vanish); a sample kept for diffing | decides the validation posture: a `200` with a different shape is the failure that corrupts silently — outages page you, drift does not |
| 12 | **Push delivery semantics** (webhooks/streams only) — at-least-once or at-most-once; retry schedule and for how long; an event id for dedup; ordering guarantee; replay window; signature scheme + timestamp tolerance; a way to LIST what was sent | decides whether a missed delivery is recoverable at all — without an event id there is no dedup, without a list-endpoint there is no reconciliation, and a webhook you cannot reconcile is a data loss waiting for a deploy |

⚠️ **Field 4 is where an operational question becomes a legal one.** Asking "are multiple accounts
permitted, and are limits per-key or per-IP?" is ordinary capacity planning, and the answer is
sometimes an explicit yes (separate billing orgs, per-project keys). Provisioning extra accounts or
rotating IPs **in order to evade a cap the vendor set** is the circumvention shape from § Hard
constraints, and it is an operator decision with the ToS quoted — never an engineering convenience.
(That exit is legitimate here on the contractual-gate ground — an authorisation, not a menu.)
Record what the ToS actually says; do not infer permission from the absence of a block.

**Fields 5 and 7 are the most often skipped and the most expensive to retrofit.** A pipeline that
cannot resume turns one transient failure into a full re-run and a full re-bill; one that cannot
read its own usage can only be surprised by the wall. If the vendor exposes neither, say so and
design for it: checkpoint on YOUR side, meter YOUR own consumption locally.

**Fields 8–12 are the vendor-side failure classes `58-resilience`'s coverage map cannot bound from
your side — the profile is what makes each one detectable, and detection is what autorecovery hangs
on:**
- **8 → 58 rows 4/5 (refuses work · permanently dead).** With a health signal the connector pauses
  on *their* incident and resumes on *their* all-clear; without one it can only infer from its own
  error rate. Poll the status API on the pause path, not the hot path, and honour announced
  maintenance as a scheduled pause. A vendor with no signal ⇒ the 58 zero-progress alarm is your
  only detector — say so in §2b.
- **9 → a credential tripwire, not a retry.** A `401` from a key the profile says should be valid
  is not transient — classify it terminal for THIS key, rotate (overlap if the vendor allows,
  scheduled hard cut if not), and alert once. Rotate on a schedule shorter than the expiry so
  expiry never happens in production; the `58` last-resort rung that died of an expired credential
  is this row unfilled.
- **10 → a deprecation watch.** Log `Deprecation`/`Sunset` when they first appear, alert ONCE with
  the sunset date (title-deduped via `fabrik-lib/alerting/`), and open the migration then — not
  when the endpoint 410s. A vendor with no header channel ⇒ record their announcement channel and
  a re-verify date in the profile; the watch is a calendar, not a header.
- **11 → validate at the boundary, count what fails.** Parse every response through a strict
  model (pydantic `strict=True` / zod `.strict()`, unknown keys rejected deliberately), never
  silently drop an invalid record, and export the invalid-record RATE as a metric — a spike is the
  upstream change announcing itself, and a `missing` cluster on one field says which one.
- **12 → the receiver: ack fast, process async, dedup, RECONCILE.** Providers time out in seconds,
  so a receiver returns `2xx` after persisting the raw event and hands processing to the job queue
  (`75-workers-jobs`); it dedups on the event id, tolerates out-of-order delivery, and rejects a
  signature outside the timestamp tolerance. ⚠️ **And it runs a reconciliation poll** — a scheduled
  pull of "what did you send since <cursor>" against the vendor's list endpoint — because a
  delivery the provider gave up on during your deploy is otherwise unrecoverable by construction.
  No list endpoint in field 12 ⇒ say so, and treat every missed webhook as a known gap in §9.
- **Scrapers have two failure classes of their own.** A **markup change** is silent — the page
  still 200s — so the extraction YIELD (fields extracted per page) is the progress counter `58`
  row 22 alarms on, never the fetch count. A **bot-block** (`403`, a challenge page) is a pause
  condition, not a retry and not a bypass: `58` says never retry a 403, and § Hard constraints
  says never solve the challenge — the legal move is `adaptive-dispatch`'s strategy switch
  (static → rendered), then a pause, then an operator decision.
- **Some classes stay human-gated, and that is allowed — SAFELY.** A vendor's credit exhaustion
  (`402`) or a retired endpoint with no successor cannot be un-broken by code. The bar is not
  "no human ever" but "no human in the loop of *staying safe*": paused on the pause key, escalated
  ONCE, never hot-looping, and named as human-gated in §2b so nobody expects the queue to wake itself.

Everything the connector then DOES with these — the pause key, the alert, the classifier entry,
the retry predicate — lives in `docs/RESILIENCE.md` under `58`'s rules. Nothing here retries.

⚠️ **One subject, one home.** The profile records the VENDOR's contract (measured, dated). YOUR
handling of it — timeout/retry config, fallback, pause keys — stays in the per-dependency detail
card in `docs/RESILIENCE.md`; that card LINKS the profile and never copies its numbers.

⚠️ **Not gate-enforced yet, deliberately — and measured 2026-09-02: 0 of the 6 hub vendor docs in
`docs/reference/apis/` carry a profile.** This is a new obligation; per the FIX directive a detector
ships after its fire rate is measured, not before. Until then the profile's teeth are the
`Profile:` line on the dependency's card in `docs/RESILIENCE.md` — **§2b where the doc has one,
otherwise the project's equivalent per-dependency row or section** (the scaffold template does carry
the slot, verified at `templates/scaffold/docs/RESILIENCE_TEMPLATE.md:63` § 2b Detail Card Per
Dependency, whose first field is `Profile`; but a project scaffolded before it, or one whose
RESILIENCE.md was hand-rolled, has no §2b — trade-intelligence carries `§2a` plus named
per-dependency sections, and following this clause literally would have meant inventing a section
that clashes with the doc's own structure, 01M1NTZJGJG88EE94VWHM3Z1PH). An empty slot is a visible
gap, not an absent one; a profile pointer riding the project's OWN per-dependency structure
satisfies this, and the deviation belongs in the file rather than unsaid. Plus this pack at plan time — and that zero is the
number to move at each vendor's next touch, not a reason to lower the bar.

---

## Hard constraints (a mechanism/vendor choice that trips one is DEAD ON ARRIVAL)

- **LLM data = OpenRouter ONLY** — never a direct vendor LLM SDK (`openai`, `@anthropic-ai/sdk`).
  Non-LLM vendor APIs are fine directly.
- **Vendor keys are env vars** (`os.getenv`), never constants; the repo must stay open-sourceable (12F-III).
- **Every external call is under the `58-resilience` contract** — which also decides WHICH layer
  retries: a vendored module or a job queue that already retries is that layer, and nothing wraps a
  second retry around it. No bare `requests.get`. **And every external SYSTEM has its Capability
  Profile first** — 58 can only bound the failures you can see, and fields 8–12 are how you see
  the vendor's.
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
    AI-specific user-agent tokens (`GPTBot`, `CCBot`, `Google-Extended`, `ClaudeBot`,
    `PerplexityBot`) are the de-facto channel rights-holders use to reserve text-and-data-mining.
    Honour a TDM reservation even when your own UA is not the one named. ⚠️ **The token set churns
    and vendors now run SEVERAL bots each** — Anthropic retired `anthropic-ai` and `Claude-Web` for
    `ClaudeBot` (training) / `Claude-User` (user-initiated fetch) / `Claude-SearchBot` (indexing),
    and OpenAI/Perplexity document their user-initiated fetchers (`ChatGPT-User`, `Perplexity-User`)
    as *not* governed by robots.txt. Read a site's file for the group matching YOUR token, not a
    2024 block-list. The machine-readable successor is the IETF AIPREF `Content-Usage` rule
    (robots.txt directive + HTTP header, a draft that updates RFC 9309 if approved) — honour it
    where present. **The test to apply, so it is decidable:** *fetching* is governed by the
    robots group matching YOUR token (default group if none); *using the content to train or
    fine-tune a model* is reserved if ANY of these is present — an AI-token `Disallow` on the path,
    a `Content-Usage`/TDMRep/`ai.txt` reservation, or an `X-Robots-Tag`/meta `noai`-class signal —
    and a reservation on any channel forbids training even when fetching is allowed. In the EU this
    is law, not etiquette: AI Act Art. 53(1)(c) binds GPAI providers to honour Art. 4(3)
    DSM-Directive reservations (in force 2025-08-02), the GPAI Code of Practice commits signatories
    to robots.txt *plus* the other machine-readable protocols, and a German appellate court has
    held that a natural-language ToS opt-out is not enough. Whether robots.txt alone is a valid
    reservation is still contested — treat any channel as binding.
  - **⚠️ THE BYPASS LINE IS THE LEGAL LINE, and it runs straight through our own toolbox.**
    Reading a logged-out public page is a different act from defeating a control. The moment a
    pipeline solves a CAPTCHA, replays a session, rotates IPs to beat a block, or evades a hard
    rate limit, it leaves "public data" territory — and the live litigation wave targets the
    **tooling layer itself** (CAPTCHA solvers, anti-bot bypass, proxy services) as trafficking in
    circumvention technology, not just the scraper. **It is unsettled, with a first ruling**: in
    *Google v. SerpApi* (dismissed with leave to amend, July 2026) the court accepted that
    fingerprint-spoofing, IP rotation and CAPTCHA-solving ARE "circumvention" under §1201, and
    dismissed only because the barrier must guard works the copyright holder authorised it to
    guard — more than twenty §1201 scraping suits were on file by mid-2026. So the exposure is
    real, the theory is live, and none of it is settled in your favour. `captcha-solve` and the
    catalog's `proxy` and `captcha` categories are therefore **capabilities, never defaults**:
    reach for them only where a human operator has decided the specific source warrants it, and
    say so in the plan.
  - **ToS binds you when you ACCEPTED it** (US-shaped reasoning, not legal advice). Terms shown
    on a page you never agreed to are weak against a logged-out fetcher; terms you click through,
    or accept by creating an account, are an ordinary contract and scraping in breach of them is a
    straightforward claim. So "we have an account there" changes the answer — check before
    assuming the public-page reasoning applies.
  - Scraping to TRAIN or fine-tune a model is a materially higher-risk category than scraping the
    same page for internal use, and in the EU it is the regulated act above. If the output feeds a
    model, that is a `NEXT: operator decision` (contractual-gate ground), not an engineering call.

---

## Doc Sync

A new external dependency owes three things: **its Capability Profile** (§ The Capability Profile — all twelve
fields, `UNKNOWN — <what you tried>` where genuinely unknown; the dependency's RESILIENCE card links
it via its `Profile:` line — §2b where the doc has one, else the project's equivalent), a pointer from wherever the repo
indexes its integrations, and its key in `.env.example` + `docs/CONFIGURATION.md` (the Doc Sync
Matrix pairs those two — naming only `.env.example` reds the gate).

⚠️ **Where the profile lives differs between hub and project** — `EXTERNAL_SYSTEMS.md` is a
hub-only index; do not send a project at it.
- **Hub:** `docs/reference/apis/<vendor>.md`, plus its row in that dir's `EXTERNAL_SYSTEMS.md`.
- **Project:** `docs/reference/apis/<vendor>.md` too — **create the directory, it is legal**
  (`docs/reference/**/*.md` is on the `.md` allowlist, so the structure gate permits it) — and
  link it from `docs/README.md`, the docs index.

A new vendor added to `service_catalog.json` is hub-side (planning registry) — propose it, don't
fork the catalog in a project. The catalog is a "does a vendor exist for X" index (`category` ·
`cost` · `capability` · `url` · `status` · `match` · `hosts` · `merged_match`), never the envelope — the twelve profile
fields live in the vendor doc, dated and re-verifiable.

**Re-verify the profile when it decides something.** Quotas and pricing move; a profile is a dated
measurement, not a fact. Re-check before scaling an integration up, before a cost estimate goes
into a plan, whenever the vendor 429s in a way the profile does not predict, and the first time a
`Deprecation` header or an invalid-record spike appears — each of those is the profile telling you
it is wrong.

**And if the ingester RUNS somewhere, the fleet-AI docs are part of the same change (D-065).**
Acquisition code is rarely a pure library: it lands as a worker, a Beat/cron job, or a webhook
receiver, and those are exactly the facts the fleet AI reads to know what to deploy and what to
schedule. So:
- a scheduled pull (Beat/cron) → `docs/RESILIENCE.md` §7 Proactive Monitoring Schedule, the
  canonical jobs/intervals inventory (the number is fixed by the scaffold template; CLAUDE.md's Doc
  Sync Matrix cites it the same way)
- a new long-running consumer/worker, or anything that changes how the service is deployed →
  `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md`
- an inbound webhook receiver → it is a served route: `15-api-contracts` applies. **Decide its
  auth posture explicitly, and the answer is not Authelia**: a provider (Stripe, GitHub, GlitchTip)
  cannot complete a forward-auth flow, so a receiver behind Authelia 302s the provider to a login
  page and silently drops every delivery. The posture is **public route + signature verification
  in the handler** (HMAC / shared secret, compared with `hmac.compare_digest`) — auth moves INTO
  the handler, never onto Authelia. It does not ride the health-path bypass either. **The
  mechanism is the spec, not a hope:** route the receiver under the service's
  `shape.bearer_bypass_prefix` (a path-regex, default `^/api/` for `has_bearer_api` services,
  narrowable) — that IS the explicit public route; there is no per-path bypass field to invent. An
  UNSIGNED provider that must write cross-tenant is the `needs_payments_ingest` shape.
- a webhook whose provider needs a stable public URL → that is a deploy-time fact, not a code
  detail; state it in `docs/DEPLOYMENT.md` rather than leaving it in a handler docstring.
