# Fabrik External Systems — the fleet index of every outside dependency and how we reach it

**Last Updated:** 2026-09-02 (converged by `/fabrik-doc-converge`; the 2026-06-02 Coolify-era version is in git history)
**Denominator (measured 2026-09-02):** 150 distinct systems (143 blocks below + 7 rows in § Retired) = the union of this doc's previous entries ∪ `scripts/service_catalog.json` (109 vendors) — the catalog grows daily as the chain's classify step names code-only hosts, so this count is re-measured at every closing pass ∪ every vendor-shaped key in `/opt/*/.env.example` (40 files) + `specs/services/*.yaml` (72 specs) ∪ the live `docker ps` of vps1/vps2/vps3 ∪ `docs/reference/apis/*.md` ∪ **every `https://<host>` literal in source across the 45 git repos under `/opt`** (the code call-site scan, `scripts/gather_envs.py` — added the same day after the env-key proxy was measured to miss 239 of 495 code-referenced hosts; 8 of those were fleet-used systems with no key anywhere: PostHog, Axiom, Slack, Vercel, Cerebras, LinkedIn, BLS, Google APIs/Gmail). **116 are fleet-used** — the count is DERIVED from the blocks: a block counts when its meta line names ≥1 project (`Used by: N project(s)`, N ≥ 1 — env key, spec or code call site) or a running container (`Runs on:`); the rest are catalogued-only or retired and say so.
**Contract:** every fleet-used external system has a block here with the **12-field Capability Profile** (`core/57-external-data-sourcing` § The Capability Profile) plus its **resilience posture** (`core/58-resilience`). A cell is a grounded value *with its source*, or exactly `UNKNOWN — tried: …` — an unstated cell is a defect, an UNKNOWN one is a visible gap. Vendor numbers rot: a value carries its date; re-verify before it decides a design, a cost estimate or a scale-up (57 § Doc Sync). The VENDOR's contract lives here; YOUR handling (timeouts, retry layer, breaker, pause key, failover, backup) lives in the consuming project's `docs/RESILIENCE.md` §2b card, which LINKS this index and never copies it.

## The types of external service the fleet depends on (the taxonomy)

Two axes decide the integration before any code — the **mechanism** (57 § The one decision) and the **category** (the catalog's `category:` plus the packs that own a type):

| Mechanism (how we reach it) | Where the rule lives |
|---|---|
| **REST/GraphQL API** (env-keyed; the default) · **webhook / stream** (they push — receiver = public route + signature in the handler) · **file transfer** (SFTP/S3/dumps) · **partner DB** (internal only) · **scrape** (static httpx → browserless → browser automation, never when an API exists) | `57-external-data-sourcing` § The one decision |
| **MCP server** — AGENT-TIME ONLY (a container cannot call one) → runtime twin is `fabrik-lib/web-tools` | 57 § Reach-for order, rung 1 · roster: `docs/workstation/mcp-roster.md` |
| **fabrik-lib module** (vendor, don't hand-roll: web-scrape, doc-crawl, async-http-client, api-quota, web-tools, webhooks (outgoing), adaptive-dispatch, captcha-solve/proxy-pool = bypass capabilities, never defaults) | 57 rung 2 |
| **CLI** (`gh`, `fabrik`, `modal`, `vastai`) — ops/scripting, rarely ingestion | 57 rung 4 |
| **Keyless call site** — a public API, a scrape target, an SDK/OAuth flow or a webhook URL reached with NO env key; discovered only by the code call-site scan (`scripts/gather_envs.py`, second input) — its MECHANISM is one of the rows above, its `**Env keys:** none in the fleet today` | 57 (mechanism rules apply unchanged) · `docs/reference/external-services-registry.md` |
| **Self-hosted container on the `fabrik` network** (postgres-main, redis-main, meilisearch, browserless, gotenberg, apprise, authelia, zitadel, glitchtip, the Grafana stack) | `30-ops`, `58` § VPS Service Client Patterns, `agents-fabrik.md` |

| Category | Owning pack / registry | Section below |
|---|---|---|
| Infrastructure, DNS, registries, CI | `30-ops`, `agents-fabrik.md`; DNS auto-provisioned by site-provisioner | § Infrastructure |
| Storage & backups | `58` (B2 client rules), Backrest plans (`docs/infrastructure`) | § Storage |
| Data stores (shared hub services) | `25-data-postgres`, `58` § substrate | § Data stores |
| Identity & auth | `35-security-auth` | § Identity |
| Payments & billing | `85-payments-billing` (Paddle / iyzico), `81-mobile` (RevenueCat) | § Payments |
| Email, messaging, notifications | `86-email-templates`, `60-watchdog` (alert sinks) | § Email |
| AI — LLM | `57` § Hard constraints (OpenRouter ONLY), `62-using-subagents` | § AI-LLM |
| AI — media & stock | `docs/reference/ai-media-generation-provider-map.md` (the per-lane reach map) | § AI-media |
| GPU & compute | `76-gpu-workers` | § GPU |
| Translation | catalog `ai-translate` | § Translation |
| Search, scrape, proxy, captcha | `57` (the bypass line), catalog `search`/`scrape`/`proxy`/`captcha` | § Acquisition |
| Research & market data | catalog `research-data` | § Research |
| SEO & web signals | catalog `search`/`domains` | § SEO |
| Observability & error tracking | `55-observability`, `60-watchdog` | § Observability |
| Automation & developer tools | catalog `dev-tools`; MCP roster | § Automation |
| Retired / decommissioned | `docs/DECISIONS.md` rows | § Retired |

---


## Infrastructure, deployment & registries

### GreenCloud VPS (vps1 hub · vps2/vps3 spokes)

**Type:** infra-platform · **Reach:** REST API (env key) · CLI `fabrik apply (SSH)` · **Used by:** 0 project(s) (no env key/spec reference found) · **Docs:** https://greencloudvps.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) https://greencloudvps.com but homepage is product/marketing, no public API docs surfaced — suggested src: https://greencloudvps.com |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no public API documented — suggested src: https://greencloudvps.com |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no public API documented — suggested src: https://greencloudvps.com |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) ToS not located in fetched pages — suggested src: https://greencloudvps.com/terms-of-service/ |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no public API documented — suggested src: https://greencloudvps.com |
| 6 | Cost model | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'VPS hosting billed per monthly cycle; resource spikes (bandwidth/CPU) may incur ' but its source is dead/unfetched (https://greencloudvps.com/billing-and-payment/); re-verify live |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no programmatic consumption endpoint documented — suggested src: https://greencloudvps.com |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no status page surfaced from vendor site — suggested src: https://greencloudvps.com |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) password/SSH key rotation handled in client panel; no API key lifecycle documented — suggested src: https greencloudvps                                                                          .com |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no versioned API documented — suggested src: https://greencloudvps.com |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no documented schema — suggested src: https://greencloudvps.com |
| 12 | Push delivery (webhooks/streams) | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Service does not expose webhooks (VPS hosting control plane) — verify: https://greencloudvps.com |
| — | **Resilience posture (58)** | DR = Backrest snapshots to B2 nightly (docs/infrastructure/vps-hub-rebuild.md:45) + the rebuild runbooks (docs/infrastructure/vps-hub-rebuild.md, docs/infrastructure/vps-spoke-rebuild.md); Vultr fallback host validated (docs/infrastructure/vps-status.md, docs/infrastructure/vps-ai-sysadmin.md) |

- **Purpose** _(2026-06-02 entry)_: Virtual Private Server hosting
- **Usage in Fabrik** _(2026-06-02 entry)_: - Driver: SSH-based Docker commands - Functions: Execute WP-CLI, Docker operations
- **Notes** _(2026-06-02 entry)_: - Ubuntu 24.04 LTS - amd64 architecture - Requires passphrase-protected SSH key
- **Research notes** _(2026-09-02)_: greencloudvps.com is a hosting provider without a documented public REST/GraphQL API; all 12 fields cannot be grounded from official docs.

### SSH + Docker Compose (`fabrik apply`)

**Type:** infra · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found)

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Fabrik's active deploy mechanism — replaces Coolify (removed 2026-05-30).

### WireGuard

**Type:** infra · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found)

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): WireGuard is a protocol, not a SaaS; no API quota exists — limits are kernel-level peer/crypto throughput — verify: https://www.wireguard.com/ |
| 2 | Behaviour AT the cap | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): No HTTP 429 — kernel handshake retries via cookie messages per protocol spec — verify: https://www.wireguard.com/protocol/ |
| 3 | Concurrency & parallelism | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): No API concurrency; per-peer concurrent sessions limited only by kernel/interface state — verify: https://www.wireguard.com/quickstart/ |
| 4 | Identity posture | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Per-keypair (public/private) identity; no ToS — open-source GPLv2 — verify: https://git.zx2c4.com/wireguard-tools/about/ |
| 5 | Failure & resume | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Stateless UDP — resumable by sending next handshake; persistent keepalive re-establishes session — verify: https://www.wireguard.com/protocol/ |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Free open-source software; no cost model — spike = no per-call cost — verify: https://www.wireguard.com/ |
| 7 | Usage observability | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): No usage endpoint — run `wg show` locally for interface stats — verify: https://www.wireguard.com/quickstart/ |
| 8 | Health signal | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): No vendor status page — self-hosted; protocol is Open Source — verify: https://www.wireguard.com/ |
| 9 | Credential lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): No API key; keypairs rotated manually — add new peer before removing old (overlap rotation) — verify: https://www.wireguard.com/quickstart/ |
| 10 | Interface lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): WireGuard is a stable protocol — kernel UAPI stable, no documented sunset/deprecation headers — verify: https://www.wireguard.com/protocol/ |
| 11 | Data contract | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): No JSON schema; binary UDP transport per spec — no silent schema changes — verify: https://www.wireguard.com/protocol/ |
| 12 | Push delivery (webhooks/streams) | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): No webhooks — protocol transports packets, not events — verify: https://www.wireguard.com/ |
| — | **Resilience posture (58)** | the fleet mesh `10.99.0.0/24` (vps1 hub ↔ vps2/vps3 spokes); spokes reach shared hub services at `10.99.0.1:<port>` (agents-fabrik-core.md); a down tunnel = every spoke's DB/Redis/Loki path — the class 58 row 14 (substrate) covers |

- **Purpose** _(2026-06-02 entry)_: VPN protocol
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: VPN connections - Status: Referenced, not deployed
- **Notes** _(2026-06-02 entry)_: - LinuxServer.io image available - amd64 compatible
- **Research notes** _(2026-09-02)_: WireGuard is a VPN protocol (open-source), not a vendor SaaS; 'capability profile' framework largely N/A — fields describe protocol/OS semantics.

### Docker Hub

**Type:** infra-platform · **Reach:** REST API (env key) · **Used by:** 1 project(s) — fabrik · **Env keys:** `DOCKER_HUB_*` · **Docs:** https://hub.docker.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Pulls/6 h: unauthenticated 100 per IPv4 or IPv6 /64; Personal 200; Pro/Team/Business unlimited; abuse limit 'thousands of req/min' per IP across all Hub properties. _(src: https://docs.docker.com/docker-hub/usage/, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 'You have reached your pull rate limit…' (pull) vs bare 429 (abuse); Hub API 429 + Retry-After seconds. _(src: https://docs.docker.com/docker-hub/usage/pulls/, 2026-09-02)_ |
| 3 | Concurrency & parallelism | Per IP (unauth) or per account (auth); shared-IP CI platforms can trip abuse limit even when authenticated. _(src: https://docs.docker.com/docker-hub/usage/pulls/, 2026-09-02)_ |
| 4 | Identity posture | Terms §5: no automated means 'except… within published limits'; §4 free tier bound to posted limits; no explicit multi-account clause (2026-06-24 Terms). _(src: https://www.docker.com/legal/docker-terms-service/, 2026-09-02)_ |
| 5 | Failure & resume | Pull = manifest + layers; version checks don't count; idempotent GETs; multi-arch counts per arch. _(src: https://docs.docker.com/docker-hub/usage/pulls/, 2026-09-02)_ |
| 6 | Cost model | Subscription tiers; fair-use surcharges for excessive transfer/storage; excessive PAT creation may be throttled/charged. _(src: https://docs.docker.com/security/access-tokens/, 2026-09-02)_ |
| 7 | Usage observability | ratelimit-limit / ratelimit-remaining / docker-ratelimit-source headers via auth.docker.io token + manifest HEAD; Usage page CSV; Hub API X-RateLimit-*. _(src: https://docs.docker.com/docker-hub/usage/pulls/, 2026-09-02)_ |
| 8 | Health signal | Statuspage JSON: 'All Systems Operational' (2026-09-02). _(src: https://www.dockerstatus.com/api/v2/status.json, 2026-09-02)_ |
| 9 | Credential lifecycle | PAT with set expiry (cannot edit — issue new = overlap rotation); JWT from /v2/users/login; /v2/auth/token short-lived; expired-token code UNKNOWN. _(src: https://docs.docker.com/reference/api/hub/latest.yaml, 2026-09-02)_ |
| 10 | Interface lifecycle | Hub API '2-beta'; v1 removed -> 410; deprecation log page (2025-06/09 entries); no headers documented. _(src: https://docs.docker.com/reference/api/hub/deprecated/, 2026-09-02)_ |
| 11 | Data contract | OpenAPI 3.0.3 published (latest.yaml, 146 KB). _(src: https://docs.docker.com/reference/api/hub/latest.yaml, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a for pulls; repository webhooks exist but not profiled this run — UNKNOWN. _(src: https://docs.docker.com/reference/api/hub/latest.yaml, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Container registry
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://hub.docker.com/v2` - Login: `POST /users/login` - List Repositories: `GET /repositories/{username}` - Push Image: `POST /images/{name}/push`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Container image management - Username: `kasabo`
- **Notes** _(2026-06-02 entry)_: - Token: Access token (not password)
- **Research notes** _(2026-09-02)_: Fleet impact: authenticate every VPS pull (Personal 200/6h) or use a Pro/Team PAT.

### GitHub Container Registry (ghcr.io)

**Type:** infra · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found)

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Free tier: 500 MB storage, 1 GB data transfer/month. Paid per GB storage/transfer. Anonymous pull limit: 100 requests/hour. https://docs.github.com/en/packages/guides/about-github-container-registry — verify: https://docs.github.com/en/packages/guides/about-github-container-registry |
| 2 | Behaviour AT the cap | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): HTTP 429 for anonymous pull limit. For paid plans, overage billing for storage/data transfer beyond limits. https://docs.github.com/en/billing/managing-billing-for-github-packages — verify: https://docs.github.com/en/billing/managing-billing-for-github-packages |
| 3 | Concurrency & parallelism | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Concurrent pulls limited by anonymous rate limit (100 req/hour) and secondary limits. Scoped to IP/account. https://docs.github.com/en/packages/guides/about-github-container-registry — verify: https://docs.github.com/en/packages/guides/about-github-container-registry |
| 4 | Identity posture | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Per GitHub account. Multiple accounts allowed but each subject to ToS clause 3 (no circumvention). https://docs.github.com/en/site-policy/github-terms — verify: https://docs.github.com/en/site-policy/github-terms |
| 5 | Failure & resume | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Retryable on 429, 5xx. Docker client handles retries. Smallest resumable unit is layer blob. Idempotent pulls. https://docs.docker.com/registry/spec/api — verify: https://docs.docker.com/registry/spec/api |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Unit: GB storage, GB data transfer. Free tier included with account. Spikes from high pull volume/large images. https://docs.github.com/en/packages/guides/about-github-container-registry — verify: https://docs.github.com/en/packages/guides/about-github-container-registry |
| 7 | Usage observability | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Usage visible in GitHub account settings under Billing > Packages. API endpoint: GET /user/packages. https://docs.github.com/en/rest/packages — verify: https://docs.github.com/en/rest/packages |
| 8 | Health signal | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Shares GitHub status page: https://www.githubstatus.com. Machine-readable API at /api/v2/status.json. https://www.githubstatus.com/api — verify: https://www.githubstatus.com/api |
| 9 | Credential lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Uses GitHub tokens (PATs/OAuth) which can expire. Expired token returns 401 Unauthorized for registry auth. https://docs.github.com/en/packages/guides/about-github-container-registry — verify: https://docs.github.com/en/packages/guides/about-github-container-registry |
| 10 | Interface lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Registry API follows Docker Registry HTTP API V2 spec. Deprecations via GitHub blog/changelog. No specific notice period. https://docs.github.com/en/packages/guides/about-github-container-registry — verify: https://docs.github.com/en/packages/guides/about-github-container-registry |
| 11 | Data contract | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Follows OCI/Docker image schema. Pagination for catalog endpoint. Deletion via GitHub UI/API. https://docs.github.com/en/packages/guides/about-github-container-registry — verify: https://docs.github.com/en/packages/guides/about-github-container-registry |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'No push/webhooks; it's a container registry pull service. Events via GitHub Acti' but its source is dead/unfetched (no url); re-verify live |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Container registry for GitHub packages
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Container storage for GitHub repos - Tool: `python /opt/fabrik/scripts/container_images.py`
- **Notes** _(2026-06-02 entry)_: - Integrated with GitHub repos - Used by hotio.dev
- **Research notes** _(2026-09-02)_: Integrated with GitHub Packages; pricing based on storage and bandwidth.

### GitHub

**Type:** infra-platform · **Reach:** REST API (env key) · CLI `gh (auth via gh login, not an env key; the github MCP was retired D-014)` · **Used by:** 0 project(s) (no env key/spec reference found) · **Docs:** https://github.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'REST API: 5,000 requests per hour for authenticated users. GraphQL API: varies b' but its source is dead/unfetched (https://docs.github.com/en/rest/overview/rate-limits); re-verify live |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'HTTP 403 or 429 for primary rate limits, 403 for secondary abuse limits. Retry-A' but its source is dead/unfetched (https://docs.github.com/en/rest/overview/rate-limits); re-verify live |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Concurrent requests subject to secondary rate limits (e.g., calls per minute). L' but its source is dead/unfetched (https://docs.github.com/en/rest/overview/rate-limits); re-verify live |
| 4 | Identity posture | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Per account/IP. ToS clause 3 restricts creating multiple accounts to circumvent limits. https://docs.github.com/en/site-policy/github-terms — verify: https://docs.github.com/en/site-policy/github-terms |
| 5 | Failure & resume | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Idempotent for GET, HEAD, PUT, DELETE. Retry on 429, 500, 502, 503, 504. Pagination via Link headers for resumable lists. https://docs.github.com/en/rest/guides/best-practices-for-using-the-rest-api — verify: https://docs.github.com/en/rest/guides/best-practices-for-using-the-rest-api |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Paid GitHub plans (Team, Enterprise) for private repos/collaborators. Free for public repos. Spikes from API-heavy automation. https://github.com/pricing — verify: https://github.com/pricing |
| 7 | Usage observability | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Rate limit status endpoint: GET /rate_limit. Returns remaining requests and reset time. https://docs.github.com/en/rest/rate-limit — verify: https://docs.github.com/en/rest/rate-limit |
| 8 | Health signal | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Status page: https://www.githubstatus.com. Provides machine-readable JSON API at /api/v2/status.json. https://www.githubstatus.com/api — verify: https://www.githubstatus.com/api |
| 9 | Credential lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Personal access tokens can be set to expire. OAuth tokens can be long-lived. Expired token returns 401. https://docs.github.com/en/authentication/keeping-your-account-and-data-secure — verify: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure |
| 10 | Interface lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): API versions in URL path (e.g., /v3). Deprecations announced on blog & via X-GitHub-Api-Version header. 12+ month notice. https://docs.github.com/en/rest/overview/api-versions — verify: https://docs.github.com/en/rest/overview/api-versions |
| 11 | Data contract | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Schema for all endpoints documented. Pagination via Link headers. Deletion APIs for resources. No silent changes policy. https://docs.github.com/en/rest — verify: https://docs.github.com/en/rest |
| 12 | Push delivery (webhooks/streams) | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Webhooks: at-least-once, retries with exponential backoff up to 24h. Event ID, no guaranteed order, no replay endpoint. https://docs.github.com/en/webhooks — verify: https://docs.github.com/en/webhooks |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Git hosting and CI/CD
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://api.github.com` - Get Repository: `GET /repos/{owner}/{repo}` - Create Webhook: `POST /repos/{owner}/{repo}/hooks` - List Actions: `GET /repos/{owner}/{repo}/actions/runs`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Git operations, CI/CD integration
- **Notes** _(2026-06-02 entry)_: - Username: `mobasak`
- **Research notes** _(2026-09-02)_: Extensive API ecosystem; secondary rate limits for abuse prevention are key.

### Let's Encrypt (via Traefik)

**Type:** infra · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found)

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | - Certificates per domain: 50 per week - Duplicate certificates: 5 per week - Failed validations: 5 per account per hour _(carried from the 2026-06-02 entry — re-verify)_ |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: SSL certificate authority
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Free SSL certificates - Integration: Via Traefik ACME - Auto-renewal: Every 90 days
- **Notes** _(2026-06-02 entry)_: - Free SSL certificates - ACME protocol - Requires DNS validation

### Traefik

**Type:** infra · **Reach:** self-hosted container on the `fabrik` network · **Runs on:** vps1, vps2, vps3 (`docker ps` 2026-09-02) · **Used by:** 0 project(s) — fleet service, no per-project key

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — container memory limit **UNLIMITED ⚠️** (docker inspect 2026-09-02: HostConfig.Memory=0 — same finding, filed to fleet); connection/pool caps are the service's own config |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Reverse proxy and load balancer
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Reverse proxy, SSL termination, load balancing - Provider: Docker (labels on containers) - EntryPoints: web (80), websecure (443) - Network: fabrik
- **Notes** _(2026-06-02 entry)_: - Self-hosted on VPS - Manages SSL certificates via Let's Encrypt - Auto-renewal every 90 days

### Nginx

**Type:** infra · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found)

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Open-source: no inherent limits; constrained by OS (file descriptors, memory). — verify: https://nginx.org/en/docs/ |
| 2 | Behaviour AT the cap | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): N/A - user configured (e.g., 503 for upstream limits). — verify: https://nginx.org/en/docs/http/ngx_http_limit_req_module.html |
| 3 | Concurrency & parallelism | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Defined by worker_processes, worker_connections. Scoped to worker. — verify: https://nginx.org/en/docs/ngx_core_module.html |
| 4 | Identity posture | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Self-hosted software, no account. Commercial support ToS: https://www.nginx.com/terms/ — verify: https://www.nginx.com/terms/ |
| 5 | Failure & resume | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Upstream retries configurable via proxy_next_upstream. No idempotency guarantee. — verify: https://nginx.org/en/docs/http/ngx_http_proxy_module.html |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Open-source: free. NGINX Plus: subscription per instance. Spikes from traffic/feature usage. — verify: https://www.nginx.com/products/nginx/pricing/ |
| 7 | Usage observability | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Open-source: status module (stub_status). Plus: extended status API. — verify: https://nginx.org/en/docs/http/ngx_http_stub_status_module.html |
| 8 | Health signal | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'F5/NGINX status: https://status.nginx.com. RSS feed available.' but its source is dead/unfetched (https://status.nginx.com); re-verify live |
| 9 | Credential lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): TLS certificates expire. Expired cert causes TLS handshake failure. — verify: https://nginx.org/en/docs/http/ngx_http_ssl_module.html |
| 10 | Interface lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Stable/mainline branches. Changes documented. Deprecation notices in changelog. — verify: https://nginx.org/en/CHANGES |
| 11 | Data contract | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Configuration file schema. Log format configurable. No data deletion API. — verify: https://nginx.org/en/docs/ |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'nginx webhook push' |
| — | **Resilience posture (58)** | runs only inside the `ocoron-com` WordPress stack on the hub (`docker ps` 2026-09-02) and as the static-site/docusaurus image; Traefik fronts everything — no direct exposure |

- **Purpose** _(2026-06-02 entry)_: Web server and reverse proxy
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Web server - Status: Referenced, not deployed
- **Notes** _(2026-06-02 entry)_: - Official image available - amd64 compatible
- **Research notes** _(2026-09-02)_: Core is open-source webserver/proxy; commercial 'Plus' adds API management and support.

### Cloudflare DNS

**Type:** infra-platform · **Reach:** REST API (env key) · **Used by:** 2 project(s) — site-provisioner, spec:site-provisioner · **Env keys:** `CLOUDFLARE_*`, `CLOUDFLARE_GLOBAL_*` · **Docs:** https://cloudflare.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | API: 1,200 requests per 5-minute period per user (all methods); client API per IP 200/s; GraphQL max 320/5 min; token quota 50 per user / 500 per account. DNS records per zone: Free 200 (zones created ≥2024-09-01; 1,000 before), Pro/Business/Enterprise 3,500 (Ent can raise; Ent quota is per account). Turnstile Free: 20 widgets/account, 10 hostnames/widget, unlimited challenges; token valid 5 minutes, single use. _(src: https://developers.cloudflare.com/fundamentals/api/reference/limits/, 2026-09-02)_ |
| 2 | Behaviour AT the cap | API: 429 and 'all API calls for the next five minutes will be blocked'; headers Ratelimit, Ratelimit-Policy, retry-after (on 429). Turnstile siteverify: reused/expired token → 200 with success:false + error-codes ['timeout-or-duplicate']; no siteverify rate limit published. _(src: https://developers.cloudflare.com/fundamentals/api/reference/limits/, 2026-09-02)_ |
| 3 | Concurrency & parallelism | No in-flight cap; the 1,200/5-min bucket is per user (token owner), 200/s per IP — so parallel workers under one token share one bucket. _(src: https://developers.cloudflare.com/fundamentals/api/reference/limits/, 2026-09-02)_ |
| 4 | Identity posture | Per user/account/IP as above. ToS §2.2.1(e): no automated creation of multiple accounts; manual multi-account not addressed (community threads only) — UNKNOWN beyond the clause. _(src: https://www.cloudflare.com/terms/, 2026-09-02)_ |
| 5 | Failure & resume | API: standard envelope, no Idempotency-Key; DNS record writes are individually idempotent by (type,name,content) semantics only if you GET-then-PUT. Turnstile siteverify supports idempotency_key (UUID) to safely retry a validation; tokens are single-use otherwise. _(src: https://developers.cloudflare.com/turnstile/get-started/server-side-validation/, 2026-09-02)_ |
| 6 | Cost model | API + DNS: free on all plans. Turnstile: Free plan $0 with unlimited challenges; Enterprise 'Contact Sales' (unlimited widgets, 200 hostnames/widget, ephemeral IDs, offlabel). _(src: https://developers.cloudflare.com/turnstile/plans/, 2026-09-02)_ |
| 7 | Usage observability | Yes for the API bucket: Ratelimit / Ratelimit-Policy headers on responses (limit name, remaining, window reset). Turnstile analytics 7-day lookback (Free) / 30-day (Ent). _(src: https://developers.cloudflare.com/fundamentals/api/reference/limits/, 2026-09-02)_ |
| 8 | Health signal | Statuspage https://www.cloudflarestatus.com/api/v2/status.json (live today, indicator 'minor'); scheduled maintenance published there. _(src: https://www.cloudflarestatus.com/api/v2/status.json, 2026-09-02)_ |
| 9 | Credential lifecycle | API tokens: optional TTL + client-IP filter at creation; verify via GET /user/tokens/verify (status active); 'Roll' regenerates the secret and 'will invalidate the previous token' (hard cut, no overlap — overlap only by creating a second token). New tokens use cfut_ prefix. Turnstile secret: POST .../rotate_secret with invalidate_immediately=false keeps the previous secret valid for 2 hours (overlap); expired secret → invalid-input-secret. _(src: https://developers.cloudflare.com/api/resources/turnstile/subresources/widgets/methods/rotate_secret/, 2026-09-02)_ |
| 10 | Interface lifecycle | API v4 base https://api.cloudflare.com/client/v4/ ('Every Cloudflare API element is fixed to a version number'); deprecations page + RSS with per-item end-of-life dates; no stated notice period and no Deprecation/Sunset headers (UNKNOWN — tried deprecations + make-api-calls pages). Turnstile changelog has RSS. _(src: https://developers.cloudflare.com/fundamentals/api/reference/deprecations/, 2026-09-02)_ |
| 11 | Data contract | Envelope {success, errors[{code,message}], messages[], result, result_info{page,per_page,count,total_count}}; page/per_page pagination (offset), order/direction. Turnstile siteverify {success, challenge_ts, hostname, error-codes[], action, cdata}. _(src: https://developers.cloudflare.com/fundamentals/api/how-to/make-api-calls/, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — neither the DNS API nor Turnstile pushes webhooks (Cloudflare Notifications webhooks are a separate product, not profiled here). _(src: https://developers.cloudflare.com/turnstile/get-started/server-side-validation/, 2026-09-02)_ |
| — | **Resilience posture (58)** | DNS records are created by `fabrik apply` itself (`src/fabrik/drivers/dns.py`, `cli.py:399` `--skip-dns`); registration + zone provisioning run through site-provisioner (agents-fabrik.md:137). Turnstile is the bot check for public forms |

- **Purpose** _(2026-06-02 entry)_: DNS management with per-record operations
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://api.cloudflare.com/client/v4` - List Zones: `GET /zones` - Get Zone ID: `GET /zones?name={domain}` - List Records: `GET /zones/{zone_id}/dns_records` - Create Record: `POST /zones/{zone_id}/dns_records` - Update Record: `PATCH /zones/{zone
- **Usage in Fabrik** _(2026-06-02 entry)_: - Driver: `/opt/fabrik/src/fabrik/drivers/cloudflare.py` - Functions: Per-record CRUD operations (safer than Namecheap)
- **Notes** _(2026-06-02 entry)_: - Safer than Namecheap (per-record operations) - Supports proxying (Cloudflare CDN)
- **Research notes** _(2026-09-02)_: Recent: GraphQL Analytics API for DNS queries added.

### Google Cloud

**Type:** infra-platform · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found) · **Docs:** https://cloud.google.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | freemium _(catalog `cost`, refreshed daily)_ |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### Namecheap DNS

**Type:** domains · **Reach:** REST API (env key) · **Used by:** 2 project(s) — site-provisioner, spec:site-provisioner · **Env keys:** `NAMECHEAP_*` · **Docs:** https://namecheap.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | 'Our general API calls restriction is 50/min, 700/hour, and 8000/day across the whole key' (official FAQ; older third-party posts say 20/min). Production API access requires ≥20 domains OR ≥$50 balance OR ≥$50 spent in 2 years; IPv4 whitelist mandatory; setHosts TTL 60–60000; 'Too many records' errors 3013288/4013288. _(src: https://www.namecheap.com/support/knowledgebase/article.aspx/9739/63/api-faq/, 2026-09-02)_ |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) intro page, error-codes list, API FAQ — no documented over-limit response (XML ApiResponse Status='ERROR' with an Error Number is the only shape; no HTTP 429/Retry-After documented). Assume hard block for the window. — suggested src: https://www.namecheap.com/support/api/error-codes/ |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) intro + FAQ — no concurrency statement; limits are per API key, calls must come from a whitelisted IP. — suggested src: https://www.namecheap.com/support/api/intro/ |
| 4 | Identity posture | Per key + whitelisted IP. Multi-account ToS: UNKNOWN — tried: https://www.namecheap.com/legal/universal/universal-tos/ (WebFetch 403), brave search (only contradictory third-party posts). FAQ forbids drop-catching via API. _(src: https://www.namecheap.com/support/knowledgebase/article.aspx/9739/63/api-faq/, 2026-09-02)_ |
| 5 | Failure & resume | No idempotency key. setHosts is a FULL REPLACE: 'All host records that are not included into the API call will be deleted' — every write must be GET getHosts → merge → setHosts (use HTTP POST for >10 records). Retry = re-send the full set (idempotent by construction). Response DomainDNSSetHostsResult IsSuccess. _(src: https://www.namecheap.com/support/api/methods/domains-dns/set-hosts/, 2026-09-02)_ |
| 6 | Cost model | API and DNS management free ('no additional fee for resellers using our API'); costs only for domain/SSL purchases. _(src: https://www.namecheap.com/support/knowledgebase/article.aspx/9739/63/api-faq/, 2026-09-02)_ |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) intro, FAQ, error codes — no usage/quota endpoint or headers documented; meter locally. — suggested src: https://www.namecheap.com/support/api/intro/ |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) https://status.namecheap.com/ (DNS ENOTFOUND today, exa CRAWL_UNKNOWN_ERROR) and /api/v2/status.json — no reachable status host; human should check Namecheap's current status URL. — suggested src: https://status.namecheap.com/ |
| 9 | Credential lifecycle | Single API key per account, no expiry; 'Reset' generates a new key and 'Any application using your existing API key will stop working immediately' (single-phase, no overlap); disabling API access likewise immediate. Bad key → ApiResponse Status='ERROR' with auth codes (1010102 key missing, 1011150 RequestIP invalid, 1017105 ClientIP disabled/locked, 1016103 UserName unauthorized). _(src: https://www.namecheap.com/support/api/intro/, 2026-09-02)_ |
| 10 | Interface lifecycle | Unversioned XML-over-GET/POST API (https://api.namecheap.com/xml.response); no versioning scheme, no deprecation channel or headers documented — UNKNOWN (tried intro, methods, FAQ). _(src: https://www.namecheap.com/support/api/intro/, 2026-09-02)_ |
| 11 | Data contract | XML envelope <ApiResponse Status=OK/ERROR><Errors/><RequestedCommand/><CommandResponse Type=...>...<Server/><GMTTimeDifference/><ExecutionTime/>; record types A, AAAA, ALIAS, CAA, CNAME, MX, MXE, NS, TXT, URL, URL301, FRAME; getList paginates by Page/PageSize; deletion = absence from the next getHosts. _(src: https://www.namecheap.com/support/api/methods/domains-dns/set-hosts/, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — no webhooks. _(src: https://www.namecheap.com/support/api/intro/, 2026-09-02)_ |
| — | **Resilience posture (58)** | registrar + DNS via `drivers/dns.py` where the zone is Namecheap-hosted; ⚠️ `setHosts` REPLACES the whole record set — the driver must GET → merge → SET (a partial write deletes every record it omits) |

- **Purpose** _(2026-06-02 entry)_: Domain registration and DNS management
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://api.namecheap.com/xml.response` - Get Domains: `namecheap.domains.getDomainsList` - Set Hosts: `namecheap.domains.dns.setHosts` - DNS Records: `namecheap.domains.dns.getHosts`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Driver: `/opt/fabrik/src/fabrik/drivers/dns.py` - Service URL: `https://provision.vps1.ocoron.com` (internal proxy) - Functions: Create/update DNS records
- **Notes** _(2026-06-02 entry)_: - Destructive API (setHosts replaces all records) - Fabrik uses internal proxy service for safer operations
- **Source access note** _(2026-09-02)_: namecheap.com/support pages block non-browser clients — `/support/api/intro/` answers 403 and the API-FAQ knowledge-base URL answers 404 to HEAD requests even with a browser UA; both were rendered via the exa fetcher this run. Re-verify the 50/min · 700/h · 8,000/day figures in a real browser before they decide a design.
- **Research notes** _(2026-09-02)_: API documentation focuses on domain/DNS management methods, not operational SLAs.

### Porkbun

**Type:** domains · **Reach:** REST API (env key) · **Used by:** 2 project(s) — brand-identiy-creator, site-provisioner · **Env keys:** `PORKBUN_*`, `PORKBUN_SECRET_*` · **Docs:** https://porkbun.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'porkbun API rate limits requests per minute' — suggested src: https://porkbun.com/products/api |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'porkbun API 429 Retry-After behavior' — suggested src: https://porkbun.com/products/api |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'porkbun API concurrent requests' — suggested src: https://porkbun.com/products/api |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'porkbun API ToS multiple accounts' — suggested src: https://porkbun.com/terms |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'porkbun API retry idempotency' — suggested src: https://porkbun.com/products/api |
| 6 | Cost model | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'porkbun API pricing per request' — suggested src: https://porkbun.com/products/api |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'porkbun API usage endpoint' — suggested src: https://porkbun.com/products/api |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'porkbun status page API' — suggested src: https://porkbun.com |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'porkbun API key expiry rotation' — suggested src: https://porkbun.com/products/api |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'porkbun API versioning deprecation' — suggested src: https://porkbun.com/products/api |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'porkbun API pagination schema' — suggested src: https://porkbun.com/products/api |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'porkbun webhooks delivery signature' — suggested src: https://porkbun.com/products/api |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Could not ground any field; this session lacks web search/fetch tools to retrieve live documentation.

### Dynadot

**Type:** domains · **Reach:** REST API (env key) · **Used by:** 1 project(s) — site-provisioner · **Env keys:** `DYNADOT_*`, `DYNADOT_SECRET_*` · **Docs:** https://dynadot.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | paid _(catalog `cost`, refreshed daily)_ |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### Namesilo

**Type:** domains · **Reach:** REST API (env key) · **Used by:** 1 project(s) — site-provisioner · **Env keys:** `NAMESILO_*` · **Docs:** https://namesilo.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) https://www.namesilo.com/api_reference.php, searched 'rate limit' |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) https://www.namesilo.com/api_reference.php |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) https://www.namesilo.com/api_reference.php |
| 4 | Identity posture | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'ToS: One account per person. Clause: 'You may not have more than one active Acco' but its source is dead/unfetched (https://www.namesilo.com/legal/terms-of-service/); re-verify live |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) https://www.namesilo.com/api_reference.php |
| 6 | Cost model | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Paid per operation (e.g., domain registration/renewal, DNS record update). Free ' but its source is dead/unfetched (https://www.namesilo.com/pricing/); re-verify live |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'Namesilo API usage' |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'Namesilo status page' |
| 9 | Credential lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): API key does not expire. — verify: https://www.namesilo.com/account/api-manager |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'Namesilo API version' |
| 11 | Data contract | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Documented request/response parameters. No pagination for most list operations (e.g., listDomains). — verify: https://www.namesilo.com/api_reference.php |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'Namesilo webhook' |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: API documentation is a single page with method specs; lacks operational details.

### Sedo

**Type:** domains · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found) · **Docs:** https://sedo.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | paid _(catalog `cost`, refreshed daily)_ |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### site-provisioner (hub service)

**Type:** infra · **Reach:** self-hosted container on the `fabrik` network · **Runs on:** vps1 (`docker ps` 2026-09-02) · **Used by:** 0 project(s) — fleet service, no per-project key

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — container memory limit **512m** (docs/infrastructure/vps-complete-inventory.md:141); connection/pool caps are the service's own config |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### Vercel

**Type:** infra-platform · **Reach:** REST API + deploy hooks + webhooks (code call site) · **Used by:** 1 project(s) — tojlo-mail (code call sites) · **Hosts:** `vercel.com` · **Env keys:** none in the fleet today (reached without a key; the posture row names the knob a consumer would add) · **Docs:** https://vercel.com/docs/rest-api

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Per-endpoint rate limits (scope owner/user/team/project): deployments per day Free 100 / Pro 6,000 / Ent 24,000; per hour Free 100 / Pro 450 / Ent 1,800; per 5 min Free 60 / Pro 120 / Ent 300; deployments retrieval 500/min (Ent 2,000); project env-var retrieval 500/min, creation/update 120/min, deletion 60/min; domains creation 120/h; deploy-hook triggers 60/h per project; team creation 5/day (Free) 25/day (Paid). General: Hobby 100 deployments/day, 200 projects, 50 domains/project, 1 concurrent build, 100 MB CLI upload (Pro 1 GB), 15,000 source files. Deploy hooks: 5/project Hobby+Pro, 10 Enterprise. Functions: Hobby 2 GB/1 vCPU, max duration 300s (Pro/Ent 800s, 1800s beta), body/response 4.5 MB, bundle 250 MB (500 MB Python), 1,024 file descriptors. Included Hobby usage: 100 GB Fast Data Transfer, 1M invocations, 4 CPU-h, 360 GB-h, 1M edge requests / month. Up to 20 custom webhooks per team. _(src: https://vercel.com/docs/limits, https://vercel.com/docs/deploy-hooks, https://vercel.com/docs/functions/limitations, https://vercel.com/pricing, https://vercel.com/docs/webhooks, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 with body `{error:{code:"rate_limited", message:"The rate limit of N exceeded for '<endpoint>'. Try again in …", limit:{remaining, reset, resetMs, total}}}` — "The limit of requests is per endpoint basis so you can continue using other endpoints"; reset only after the window Duration expires (e.g. wait another day for deployments/day). Dynamic quotas (Sandbox vCPU ramp) return 429 `rate_limit_exceeded` with "Allocation rate is ramping up to N units/min, retry shortly". Hobby usage caps: "you will have to wait until 30 days have passed before you can use the feature again" (no overage on Hobby); Pro bills on-demand after included credit. Function overrun → 504 FUNCTION_INVOCATION_TIMEOUT; payload >4.5 MB → 413. Response headers X-RateLimit-Limit/Remaining/Reset appear only in the search index of /docs/rest-api — NOT present in any fetched rendering of that page (tried https://vercel.com/docs/rest-api, /docs/rest-api/, /docs/rest-api/reference/welcome, /docs/rest-api/getting-started; openapi.vercel.sh exceeded WebFetch 10 MB cap). _(src: https://vercel.com/docs/rest-api/errors, https://vercel.com/docs/limits, https://vercel.com/docs/plans/hobby, https://vercel.com/docs/functions/limitations, 2026-09-02)_ |
| 3 | Concurrency & parallelism | No documented in-flight API-call cap beyond the per-endpoint windows; builds: Hobby 1 concurrent deployment, Pro up to 500 on-demand concurrent builds (fair-use cap 500/team, excess queued); functions auto-scale to 30,000 concurrency (Hobby/Pro) or 100,000+ (Ent); deploy hooks: "If you send multiple requests to deploy the same version of your project, previous deployments for the same Deploy Hook will be canceled". _(src: https://vercel.com/docs/limits, https://vercel.com/docs/limits/fair-use-guidelines, https://vercel.com/docs/functions/limitations, https://vercel.com/docs/deploy-hooks, 2026-09-02)_ |
| 4 | Identity posture | Per team (Hobby team = personal). "Hobby teams are restricted to non-commercial personal use only. All commercial usage of the platform requires either a Pro or Enterprise plan" — commercial = any financial gain by anyone involved incl. paid consultant writing the code; donations count. "Your Hobby team on Vercel can have only one login connection per third-party service … For multiple logins from the same service, create a new Vercel Hobby team." "Circumventing or otherwise misusing Vercel's limits or usage guidelines is a violation of our fair use guidelines." Hobby cannot connect projects to Git-organization repos. _(src: https://vercel.com/docs/limits/fair-use-guidelines, https://vercel.com/docs/accounts, https://vercel.com/docs/limits, 2026-09-02)_ |
| 5 | Failure & resume | Deploy hook is idempotent by design — POST/GET returns `{job:{id,state:"PENDING",createdAt}}`, duplicate triggers cancel the earlier build; `?buildCache=false` forces a clean rebuild. Deployments are the resumable unit: `GET /v7/deployments` filters by `state` (BUILDING/ERROR/QUEUED/READY/CANCELED/BLOCKED), `since`/`until`/`limit`, paginated by `pagination{count,next,prev}` timestamps (next/prev nullable). Failed deployment → `errorCode` (e.g. BUILD_FAILED), `errorMessage`, `oomReport`; deleted deployments have a 30-day recovery period (undelete endpoint). No Idempotency-Key header documented for the REST API. _(src: https://vercel.com/docs/deploy-hooks, https://vercel.com/docs/rest-api/deployments/list-deployments, https://vercel.com/docs/webhooks/webhooks-api, 2026-09-02)_ |
| 6 | Cost model | Hobby $0/mo (100 GB transfer, 1M invocations, 4 CPU-h, 360 GB-h, 1M edge requests included; no billing cycle, features pause up to 30 days when exceeded). Pro $20/developer seat/mo (Viewer seats free): 1 TB transfer then from $0.15/GB; invocations $0.60/1M; Active CPU from $0.128/h; provisioned memory from $0.0106/GB-h; edge requests 10M then $2/1M; image transformations $0.05/1K; drains $0.50/GB; workflow events $0.02/1K. Spike = on-demand overage on Pro (Spend Management configurable); Hobby = pause. _(src: https://vercel.com/pricing, https://vercel.com/docs/limits, https://vercel.com/docs/plans/hobby, 2026-09-02)_ |
| 7 | Usage observability | 429 body carries `limit.remaining/reset/resetMs/total` per endpoint; billing API `GET /v1/billing/charges` (FOCUS charges) and `GET /v1/billing/contract-commitments`; `GET /v8/artifacts/status` for remote-cache status; dashboard Usage summary + Spend Management (Pro). No per-endpoint quota-status endpoint documented (tried https://vercel.com/docs/rest-api, /docs/limits). _(src: https://vercel.com/docs/rest-api/errors, https://vercel.com/docs/rest-api/reference/welcome, https://vercel.com/docs/limits, 2026-09-02)_ |
| 8 | Health signal | Statuspage-compatible: https://www.vercel-status.com/api/v2/status.json returned `{"page":{"id":"lvglq8h0mdyh","name":"Vercel","url":"https://www.vercel-status.com","time_zone":"Etc/UTC","updated_at":"2026-09-02T09:49:13.938Z"},"status":{"indicator":"none","description":"All Systems Operational"}}` today. _(src: https://www.vercel-status.com/api/v2/status.json, 2026-09-02)_ |
| 9 | Credential lifecycle | Access tokens `vcp_*` (Full Account / Team / Project scope); "A token's value appears only once, at creation"; expiration chosen at creation — "default list of expiration dates ranging from 1 day to 1 year" (changelog 2022-07-20; the current docs page says only "Choose an expiration", no explicit no-expiry option fetched). Programmatic: `POST /v3/user/tokens` {name, expiresAt?, projectId?} → `bearerToken` shown once; `GET /v6/user/tokens` lists with `expiresAt/revokedAt/leakedAt/leakedUrl/activeAt`; `DELETE /v3/user/tokens/{tokenId}` revokes → overlap rotation by create-then-delete. "Creating tokens through the CLI or API requires a full-account token. A project-scoped token cannot mint new tokens." Bad/expired token → 401; wrong scope/expired → 403 ("Check the token's expiration and scope"). Deploy-hook URL = the secret; "revoke it and create a new one" if compromised. _(src: https://vercel.com/docs/accounts/access-tokens, https://vercel.com/changelog/expiration-dates-now-available-for-access-tokens, https://vercel.com/docs/rest-api/authentication/create-an-auth-token, https://vercel.com/docs/rest-api/authentication/list-auth-tokens, https://vercel.com/docs/rest-api/getting-started, https://vercel.com/docs/deploy-hooks, 2026-09-02)_ |
| 10 | Interface lifecycle | Base `https://api.vercel.com`; versioned per endpoint in the path (e.g. `/v13/deployments`, `/v7/deployments` list, `/v10/projects`, `/v3/user/tokens`, `/v6/user/tokens`, `/v1/webhooks`); old endpoints carry a "Deprecated" marker in the reference (e.g. "Update an existing project — Deprecated", "Update Resource Secrets (Deprecated)"); webhook events: "The following event types have been deprecated and webhooks that listen for them can no longer be created. Vercel will continue to deliver the deprecated events to existing webhooks." Machine-readable OpenAPI at https://openapi.vercel.sh/ . No Deprecation/Sunset header or written sunset timeline fetched — UNKNOWN (tried https://vercel.com/docs/rest-api, /docs/rest-api/reference/welcome, /docs/rest-api/errors). _(src: https://vercel.com/docs/rest-api/reference/welcome, https://vercel.com/docs/webhooks/webhooks-api, https://vercel.com/docs/rest-api/projects/update-an-existing-project, 2026-09-02)_ |
| 11 | Data contract | Errors `{error:{code, message, …}}` (codes: forbidden, rate_limited, bad_request, internal_server_error, not_found, method_unknown, env_too_many_keys …; env vars ≤100/deployment, key ≤256 chars, value ≤65,536 chars). Lists `{<items>[], pagination:{count, next, prev}}` with `next`/`prev` as timestamps (nullable). Deployment `{uid, name, projectId, url, created, state/readyState, readySubstate, target, source, errorCode, errorMessage, inspectorUrl, meta, …}`. Deploy-hook response `{job:{id,state,createdAt}}`. Webhook payload `{id, type, createdAt, region, payload:{team.id, user.id, deployment.{id,url,name,meta}, project.id, target, plan, regions, links.{deployment,project}}}`. _(src: https://vercel.com/docs/rest-api/errors, https://vercel.com/docs/rest-api/deployments/list-deployments, https://vercel.com/docs/webhooks/webhooks-api, https://vercel.com/docs/deploy-hooks, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | Account webhooks (Pro/Enterprise only, ≤20/team; Hobby: none) POST JSON to a public URL; header `x-vercel-signature` = HMAC-SHA1 hex of the raw body with the secret shown once at creation (integration webhooks: Integration/Client Secret); "if a `2XX` HTTP response is not received within 30 seconds, the request will be aborted"; "If your HTTP endpoint does not respond with a `2XX` HTTP status code, we attempt to deliver the webhook event up to 24 hours with an exponential backoff. Events that could not be delivered within 24 hours will not be retried and will be discarded." Events: deployment.{created,succeeded,ready,promoted,rollback,error,canceled,cleanup,check-rerequested}, project.*, domain.*, flag.*, marketplace.*, alerts.triggered; each carries delivery `id` for dedupe. Also `POST /v1/webhooks` API + `vercel webhooks` CLI. _(src: https://vercel.com/docs/webhooks, https://vercel.com/docs/webhooks/webhooks-api, https://vercel.com/docs/headers/request-headers, 2026-09-02)_ |
| — | **Resilience posture (58)** | deploy trigger + status poll; deploy hook = secret URL (env `VERCEL_DEPLOY_HOOK_URL`), 60/h/project + 100/day Hobby budget → queue/coalesce triggers; REST calls read the 429 `limit.reset` and back off per endpoint; webhook receiver = public route, HMAC-SHA1 verify in handler, idempotent on delivery `id`, reply 2XX within 30s (57 § Doc Sync) |

- **Research notes** _(2026-09-02)_: vendor status: https://www.vercel-status.com (Statuspage JSON: https://www.vercel-status.com/api/v2/status.json).

## Storage & backups

### Backblaze B2

**Type:** storage · **Reach:** REST API (env key) · **Used by:** 8 project(s) — brand-identiy-creator, fabrik, iterative_image_editor, spec:wpf, spec:youtube, tojlo-mail, transdoc, web-ecommerce-factory · **Env keys:** `B2_*`, `B2_APPLICATION_*`, `B2_SECRET_*` · **Docs:** https://backblaze.com/cloud-storage

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | No published req/min figure: '429 TOO MANY REQUESTS — B2 may limit API requests on a per-account basis.' Size caps: normal file ≤5 GB; large files 5 MB–10 TB, parts 5 MB–5 GB, ≥2 parts, last part ≥1 byte; app keys ≤100M/account; event-notification rules ≤25/bucket; auth token valid 24h. _(src: https://www.backblaze.com/apidocs/introduction-to-the-b2-native-api, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 (no Retry-After documented); 503 'temporarily unavailable — retry with exponential backoff'; 403 = storage cap/account restriction; 401 on upload = get a new upload URL. Class D calls above 2,500/day are billed (overage), not blocked. _(src: https://www.backblaze.com/apidocs/introduction-to-the-b2-native-api, 2026-09-02)_ |
| 3 | Concurrency & parallelism | Large-file parts 'can be uploaded and copied in parallel'; no max-in-flight documented; each upload URL is single-threaded by design (get one per thread). Scope of 429 = per account. _(src: https://www.backblaze.com/docs/cloud-storage-large-files, 2026-09-02)_ |
| 4 | Identity posture | Per account. ToS multi-account: UNKNOWN — tried: https://www.backblaze.com/company/terms (WebFetch 404), brave search (only Groups feature: 'individual accounts under one credit card'; help: 'no restrictions on how many ... B2 buckets you can have under a single account'). _(src: https://help.backblaze.com/hc/en-us/articles/115000119794-Do-I-Need-Groups-or-Business, 2026-09-02)_ |
| 5 | Failure & resume | Retryable: 503 (backoff), 401 bad_auth_token/expired_auth_token (re-authorize), 401 on upload (new upload URL), 408. Resumable unit = large-file PART (5 MB–5 GB); unfinished large files persist until finished/cancelled (b2_list_unfinished_large_files/b2_list_parts). No idempotency key; uploads are content-addressed by SHA-1 per part. _(src: https://www.backblaze.com/apidocs/introduction-to-the-b2-native-api, 2026-09-02)_ |
| 6 | Cost model | $6.95/TB-month (first 10 GB free); egress free up to 3x average monthly storage, then $0.01/GB; Class A, B, C API calls FREE; Class D (event-notification webhooks) first 2,500/day free then $0.004 per 10,000; 'No minimum file size or storage duration fees'. Spike = egress >3x storage. _(src: https://www.backblaze.com/cloud-storage/pricing, 2026-09-02)_ |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) native API intro, application-keys page, pricing page — no usage/quota endpoint documented (caps & alerts are web-console features; b2_authorize_account returns capabilities, not consumption). — suggested src: https://www.backblaze.com/apidocs/introduction-to-the-b2-native-api |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) https://status.backblaze.com/api/v2/status.json (exa CRAWL_UNKNOWN_ERROR; WebFetch 'socket hang up'), https://status.backblaze.com/ (WebFetch returned empty). Page exists but format/API unverified this run. — suggested src: https://status.backblaze.com/ |
| 9 | Credential lifecycle | App keys: optional expiry via validDurationSeconds (<1000 days); expired keys can't authorize and vanish from b2_list_keys; auth tokens expire after 24h (expired_auth_token → re-authorize). Overlap rotation = create second key, switch, delete old (multiple keys allowed; master key regen invalidates the old master immediately). 401 codes: unauthorized / bad_auth_token / expired_auth_token / unsupported. _(src: https://www.backblaze.com/docs/cloud-storage-application-keys, 2026-09-02)_ |
| 10 | Interface lifecycle | Path version /b2api/v4/ (current v4, Apr 29 2025); 'Backblaze does not have any plans to stop supporting old versions. If we ever do ... announce them at least a year in advance'; incompatible changes only under a new version; compatible changes (new fields, wider inputs) may happen anytime. No Deprecation/Sunset headers. _(src: https://www.backblaze.com/docs/cloud-storage-native-api-versions, 2026-09-02)_ |
| 11 | Data contract | JSON; errors {status, code, message}; responses may gain fields any time ('your code should ignore any fields that it does not expect'); bucketType and file action enums 'may be extended'. List calls paginate via nextFileName/nextFileId. Deletion = version hidden/deleted (file versions model). _(src: https://www.backblaze.com/docs/cloud-storage-native-api-versions, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | Event Notifications (webhook, HTTPS POST, feature gated — 'contact the Support team to request access'): ≤25 rules/bucket, batched (maxEventsPerBatch), optional HMAC-SHA256 via 32-char hmacSha256SigningSecret → X-Bz-Event-Notification-Signature; no timestamp in signature documented; retry schedule / event id / replay endpoint not in the fetched reference (UNKNOWN — page truncated at rule structure). Not a webhook source for most integrations. _(src: https://www.backblaze.com/docs/cloud-storage-event-notifications-reference-guide, 2026-09-02)_ |
| — | **Resilience posture (58)** | timeout 30s connect / 120s read; fallback = return an error, never block a request on an upload (58:428); uploads via the job queue, never inline; presigned URLs for downloads (58 § VPS Service Client Patterns) · the fleet's backup target: Backrest writes restic snapshots to B2 nightly from all three hosts (docs/infrastructure/vps-hub-rebuild.md:45; docs/infrastructure/vps-status.md:124-126 — 4 hub plans, 2 per spoke) |

- **Purpose** _(2026-06-02 entry)_: Cloud object storage for backups
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://api.backblazeb2.com/b2api/v2` - Authorize Account: `b2_authorize_account` - List Buckets: `b2_list_buckets` - Upload File: `b2_upload_file` - Download File: `b2_download_file_by_id` - List Files: `b2_list_file_names`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Encrypted backups of project data - Bucket: `vps1-ocoron-backups`
- **Notes** _(2026-06-02 entry)_: - Requires encryption passphrase for backup security - S3-compatible API
- **Research notes** _(2026-09-02)_: B2 supports optional webhook notifications via b2-notification-url; no live search results returned in this run to ground specifics.

### Cloudflare R2

**Type:** storage · **Reach:** REST API (env key) · **Used by:** 7 project(s) — fabrik, gmail-account-creator, spec:fabrik-test-file-api, spec:fabrik-test-file-worker, spec:gmail-account-creator, spec:test-file-log, spec:test-fw-log · **Env keys:** `R2_SECRET_*` · **Docs:** https://cloudflare.com/products/r2

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | REST API 1,200 req per 5 min; bucket-management ops 50/s; concurrent writes to the same object 1/s; r2.dev endpoint throttled (hundreds rps, variable); buckets 1,000,000/account; object 5 TiB (4.995 TiB multipart), single PUT 5 GiB; parts 5 MiB–5 GiB, ≤10,000 parts; lifecycle rules ≤1000; event-notification rules ≤100/bucket. _(src: https://developers.cloudflare.com/r2/platform/limits/, 2026-09-02)_ |
| 2 | Behaviour AT the cap | HTTP 429 for same-object write rate and r2.dev throttling; REST API 1,200/5-min → 429 for the next 5 minutes (fundamentals limit). No silent truncation; overage on storage/ops is billed, not blocked. _(src: https://developers.cloudflare.com/r2/platform/limits/, 2026-09-02)_ |
| 3 | Concurrency & parallelism | Multipart parts 'can be uploaded concurrently'; only documented concurrency cap is 1 write/s per object key. Scope: per account (REST), per object (writes). _(src: https://developers.cloudflare.com/r2/objects/multipart-objects/, 2026-09-02)_ |
| 4 | Identity posture | Per account (tokens are account- or user-scoped). ToS: cloudflare.com/terms §2.2.1(e) forbids using 'software or automated agents or scripts ... so as to produce multiple accounts'; manual multiple accounts not addressed — UNKNOWN beyond that clause. _(src: https://www.cloudflare.com/terms/, 2026-09-02)_ |
| 5 | Failure & resume | Multipart is the resume unit ('only failed parts need to be retried'); single PUT must restart. Incomplete multipart uploads auto-expire after 7 days (default lifecycle rule). S3 semantics, no Idempotency-Key; last-writer-wins on concurrent PUT/DELETE. _(src: https://developers.cloudflare.com/r2/objects/multipart-objects/, 2026-09-02)_ |
| 6 | Cost model | Standard $0.015/GB-month, IA $0.01; Class A $4.50/M (IA $9.00), Class B $0.36/M (IA $0.90); free monthly: 10 GB-month, 1M Class A, 10M Class B; egress free. Spike = Class A ops (writes/lists, IA transitions count as Class A). _(src: https://developers.cloudflare.com/r2/pricing/, 2026-09-02)_ |
| 7 | Usage observability | Yes: GraphQL Analytics API datasets r2OperationsAdaptiveGroups and r2StorageAdaptiveGroups (31-day retention), same data as dashboard. _(src: https://developers.cloudflare.com/r2/platform/metrics-analytics/, 2026-09-02)_ |
| 8 | Health signal | Statuspage: https://www.cloudflarestatus.com/api/v2/status.json — today returned indicator 'minor' / 'Minor Service Outage' (so the feed is live and machine-readable); scheduled maintenance via the same Statuspage API. _(src: https://www.cloudflarestatus.com/api/v2/status.json, 2026-09-02)_ |
| 9 | Credential lifecycle | R2 S3 tokens: Account API tokens 'remain valid until manually revoked'; User tokens die when the user is removed; secret shown once; permission changes eventually consistent (~1 min). Overlap rotation = create second token, cut over, revoke. Expired/invalid → S3 auth error (code not stated on page). _(src: https://developers.cloudflare.com/r2/api/tokens/, 2026-09-02)_ |
| 10 | Interface lifecycle | S3-compatible API (no version in path); changes via product changelog; no Deprecation/Sunset headers documented (UNKNOWN — tried limits, tokens, consistency pages). _(src: https://developers.cloudflare.com/r2/api/tokens/, 2026-09-02)_ |
| 11 | Data contract | Strongly consistent globally (read-after-write, list, delete → immediate 'does not exist'); IAM eventually consistent; S3 XML responses; custom-domain cache relaxes consistency (stale reads until purge). _(src: https://developers.cloudflare.com/r2/reference/consistency/, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | No webhooks — event notifications go to Cloudflare Queues (consumer Worker or HTTP pull); events object-create / object-delete; message has account, action, bucket, object{key,size,eTag}, eventTime; ≤100 rules/bucket; Queues semantics (at-least-once) apply. _(src: https://developers.cloudflare.com/r2/buckets/event-notifications/, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: S3-compatible object storage
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://<account_id>.r2.cloudflarestorage.com` - S3-compatible: Use AWS SDK with R2 endpoint - List Objects: `GET /<bucket>` - Upload Object: `PUT /<bucket>/<key>` - Download Object: `GET /<bucket>/<key>` - Delete Object: `DELETE /<bucket>/<key>`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: File storage for projects - Bucket: `fabrik-files` - Endpoint: `https://066f5cf1dfe20ba18549a592809aa080.r2.cloudflarestorage.com`
- **Notes** _(2026-06-02 entry)_: - S3-compatible (use AWS SDK) - No egress fees - Better for global distribution than B2
- **Research notes** _(2026-09-02)_: Recent: Added S3 Select support (preview).

### AWS (S3 / SES)

**Type:** storage · **Reach:** REST API (env key) · **Used by:** 1 project(s) — site-provisioner · **Env keys:** `AWS_SECRET_*` · **Docs:** https://aws.amazon.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | S3: ≥3,500 PUT/COPY/POST/DELETE + 5,500 GET/HEAD per second per prefix, unlimited prefixes. SES: sandbox 200/24h + 1/s; production per-account rolling 24h quota + max send rate, per Region; 40 MB msg (v2/SMTP), 50 recipients. _(src: https://docs.aws.amazon.com/ses/latest/dg/quotas.html, 2026-09-02)_ |
| 2 | Behaviour AT the cap | S3: 503 Slow Down while auto-scaling to new request rate (dissipates). SES: ThrottlingException 'Daily message quota exceeded' / 'Maximum sending rate exceeded' (SMTP 454); message DROPPED, wait up to 10 min and resend. _(src: https://docs.aws.amazon.com/ses/latest/dg/manage-sending-quotas-errors.html, 2026-09-02)_ |
| 3 | Concurrency & parallelism | S3 scales by parallelising across prefixes/multipart (gradual); SES max sending rate per second, short bursts tolerated, sustained not. _(src: https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html, 2026-09-02)_ |
| 4 | Identity posture | Customer Agreement §2.1: 'you will only create one account per email address' unless Service Terms permit; per-Region SES quotas; multi-account via Organizations not on fetched page. _(src: https://aws.amazon.com/agreement/, 2026-09-02)_ |
| 5 | Failure & resume | S3 multipart upload: no expiry until complete/abort, retry only failed parts, ListParts; PutObject idempotent by key. SES: throttled sends are dropped (must resend); SendEmail not idempotent. _(src: https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html, 2026-09-02)_ |
| 6 | Cost model | S3: per GB-month + per request + transfer, no minimum (IA/Glacier min 128 KB and 30/90/180-day minimums). SES: Essentials $0.16/1k (0–10M) tiered, Pro +$105/mo, or à la carte $0.10/1k + $0.12/GB attachments. _(src: https://aws.amazon.com/ses/pricing/, 2026-09-02)_ |
| 7 | Usage observability | SES v2 GetAccount → SendQuota {Max24HourSend, MaxSendRate, SentLast24Hours}, EnforcementStatus, SendingEnabled. S3 usage via CloudWatch/Service Quotas (not fetched). _(src: https://docs.aws.amazon.com/ses/latest/APIReference-V2/API_GetAccount.html, 2026-09-02)_ |
| 8 | Health signal | AWS Health API (global.health.amazonaws.com, active/passive endpoints) — requires Business+ support plan else SubscriptionRequiredException; public dashboard health.aws.amazon.com (fetch failed this run). _(src: https://docs.aws.amazon.com/health/latest/ug/health-api.html, 2026-09-02)_ |
| 9 | Credential lifecycle | IAM access keys: long-term, no expiry; max 2 active per user → overlap rotation; prefer temporary creds (roles/STS); monitor via CloudTrail. _(src: https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html, 2026-09-02)_ |
| 10 | Interface lifecycle | Customer Agreement §1.5: ≥12 months' notice before discontinuing material functionality; §1.6: 90 days for adverse SLA changes. SES v1/v2 APIs coexist; no Sunset headers. _(src: https://aws.amazon.com/agreement/, 2026-09-02)_ |
| 11 | Data contract | S3 XML error bodies; SES JSON; S3 event notification JSON records; silent-change history UNKNOWN (S3 ErrorResponses page unfetchable this run). _(src: https://docs.aws.amazon.com/AmazonS3/latest/userguide/EventNotifications.html, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | S3 Event Notifications → SNS/SQS/Lambda/EventBridge: at-least-once, usually seconds, sometimes ≥1 min, no FIFO SQS. SES event publishing → SNS JSON records (bounce/complaint/delivery) via configuration sets (10 destinations). _(src: https://docs.aws.amazon.com/AmazonS3/latest/userguide/EventNotifications.html, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: SES Essentials became default plan for new accounts 2026-07-21 — à la carte $0.10/1k must be opted into.

### Backrest (restic) — active backup tool since 2026-04-17

**Type:** backup · **Reach:** self-hosted container on the `fabrik` network · REST API (env key) · **Runs on:** vps1, vps2, vps3 (`docker ps` 2026-09-02) · **Used by:** 0 project(s) — fleet service, no per-project key · **Docs:** https://github.com/garethgeorge/backrest

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — container memory limit **512m** (docs/infrastructure/vps-complete-inventory.md:607); connection/pool caps are the service's own config |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'restic resume incremental' — suggested src: https://restic.readthedocs.io/en/stable/045_working_with_repos.html |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'backrest status' — suggested src: https://github.com/garethgeorge/backrest |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'restic repository schema' — suggested src: https://restic.readthedocs.io/en/stable/045_working_with_repos.html |
| 12 | Push delivery (webhooks/streams) | n/a — no webhooks; a fleet service pushes nothing (alerts flow via Prometheus → Alertmanager → Apprise/Telegram) |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Backup orchestration UI over `restic`. Replaced Duplicati 2026-04-17.
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: scheduled restic snapshots to Backblaze B2 (encrypted, deduplicated) - Plans (vps1): `b2-vps1` covers `postgres-dumps`, `docker-volumes`, `opt-configs`, `host-state`; each spoke (vps2/vps3) runs its own 2 plans - restic 0.18.1 runs inside the back
- **Notes** _(2026-06-02 entry)_: - The `backrest` Gatus endpoint monitors its health - Spec-driven: a service's `shape.has_persistent_data: true` triggers a Backrest plan registrar on `fabrik apply`
- **Research notes** _(2026-09-02)_: Open-source self-hosted tool; no vendor push channel. Live web fetch was unavailable in this run.

### Restic

**Type:** backup · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found) · **Docs:** https://restic.net

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): No inherent limits; constrained by backend storage (S3, SFTP, etc.) and local resources. Self-hosted. — verify: https://restic.net |
| 2 | Behaviour AT the cap | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Depends on the backend service limits (e.g., S3 throttling). No overage billing for restic itself. — verify: https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html |
| 3 | Concurrency & parallelism | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Parallel operations configurable via --parallel; defaults to available CPUs. Limited by backend concurrency. — verify: https://restic.readthedocs.io/en/stable/040_backup.html#parallel-uploads |
| 4 | Identity posture | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Per repository access via password/key file. No ToS for the software itself. — verify: https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html |
| 5 | Failure & resume | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Resumable backups via snapshot system; retryable errors for network backends; idempotent snapshot creation. — verify: https://restic.readthedocs.io/en/stable/040_backup.html |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Free, open-source software. Costs from backend storage (e.g., S3 fees). — verify: https://restic.net |
| 7 | Usage observability | UNKNOWN — tried: pool sweep 2026-09-02 suggested '`restic stats` command; `restic snapshots` to list backups. No external API for ' but its source is dead/unfetched (https://restic.readthedocs.io/en/stable/050_commands.html#stats); re-verify live |
| 8 | Health signal | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): No status page. GitHub repository for issues. — verify: https://github.com/restic/restic |
| 9 | Credential lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Repository passwords do not expire. Backend credentials (e.g., AWS keys) follow their own lifecycle. — verify: https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html |
| 10 | Interface lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Stable CLI interface; versioned releases with changelog; no formal deprecation policy. — verify: https://github.com/restic/restic/releases |
| 11 | Data contract | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Repository format documented; snapshots immutable; data deduplicated; deletion via `forget` + `prune`. — verify: https://restic.readthedocs.io/en/stable/100_references.html#repository-format |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched restic documentation and GitHub for webhooks/push |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Backup tool
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Fast backups - Status: Referenced, not deployed
- **Notes** _(2026-06-02 entry)_: - Official image available - amd64 compatible
- **Research notes** _(2026-09-02)_: Self-hosted backup tool; limitations depend on chosen storage backend.

### Duplicati

**Type:** backup · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found) · **Docs:** https://duplicati.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | self-host _(catalog `cost`, refreshed daily)_ |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### Minio

**Type:** storage · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found) · **Docs:** https://min.io

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | self-host _(catalog `cost`, refreshed daily)_ |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: S3-compatible object storage
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: S3-compatible storage - Domain: `https://s3.vps1.ocoron.com` - Ports: 9000 (API), 9001 (Console)
- **Notes** _(2026-06-02 entry)_: - Self-hosted on VPS - S3-compatible API - amd64 compatible


## Data stores on the `fabrik` network

### PostgreSQL (`postgres-main`)

**Type:** datastore · **Reach:** self-hosted container on the `fabrik` network · **Runs on:** vps1 (`docker ps` 2026-09-02) · **Used by:** 0 project(s) — fleet service, no per-project key

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — container memory limit **2g** (docs/infrastructure/vps-complete-inventory.md:597); connection/pool caps are the service's own config |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'postgresql WAL replication resume' — suggested src: https://www.postgresql.org/docs/ |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'postgresql status page' — suggested src: https://www.postgresql.org/ |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'postgresql data types schema changes' — suggested src: https://www.postgresql.org/docs/ |
| 12 | Push delivery (webhooks/streams) | n/a — no webhooks; a fleet service pushes nothing (alerts flow via Prometheus → Alertmanager → Apprise/Telegram) |
| — | **Resilience posture (58)** | shared hub service `postgres-main:5432` (spokes: `10.99.0.1:5432`); pool_pre_ping per 25-data-postgres; backups via Backrest; per-project DB minted by the postgres registrar |

- **Purpose** _(2026-06-02 entry)_: Relational database
- **Usage in Fabrik** _(2026-06-02 entry)_: - Shared instance: `postgres-main` - Project-specific databases: youtube_pipeline, proxy_management, translator_service, calendar_engine, llm_batch
- **Notes** _(2026-06-02 entry)_: - Shared across multiple projects - Requires connection pooling for high concurrency
- **Research notes** _(2026-09-02)_: PostgreSQL is open-source self-hosted software; vendor-side capability profile is largely N/A — lacks web tools to verify.

### Redis (`redis-main`)

**Type:** datastore · **Reach:** self-hosted container on the `fabrik` network · **Runs on:** vps1 (`docker ps` 2026-09-02) · **Used by:** 0 project(s) — fleet service, no per-project key

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — container memory limit **UNLIMITED ⚠️** (docker inspect 2026-09-02: HostConfig.Memory=0 — violates the every-container-declares-a-memory-limit invariant (CLAUDE.md HARD STOPS); filed to fleet); connection/pool caps are the service's own config |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'redis persistence AOF resume' — suggested src: https://redis.io/docs/ |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'redis status page' — suggested src: https://status.redis.io/ |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'redis data types schema RESP' — suggested src: https://redis.io/docs/ |
| 12 | Push delivery (webhooks/streams) | n/a — no webhooks; a fleet service pushes nothing (alerts flow via Prometheus → Alertmanager → Apprise/Telegram) |
| — | **Resilience posture (58)** | shared hub service `redis-main:6379`; pause keys/rate limits/dedup live here — every guard DECLARES fail-open/closed (58 § When the substrate fails); per-project index minted by the redis registrar |

- **Purpose** _(2026-06-02 entry)_: In-memory data store (cache, queues)
- **Usage in Fabrik** _(2026-06-02 entry)_: - Shared instance: `redis-main` - Functions: Caching, job queues, rate limiting
- **Notes** _(2026-06-02 entry)_: - Shared across multiple projects - Requires persistence configuration
- **Research notes** _(2026-09-02)_: Redis is open-source self-hosted software plus Redis Cloud SaaS; vendor capability profile ambiguous — lacks web tools.

### Meilisearch

**Type:** infra-platform · **Reach:** self-hosted container on the `fabrik` network · REST API (env key) · **Runs on:** vps1 (`docker ps` 2026-09-02) · **Used by:** 1 project(s) — fabrik · **Env keys:** `MEILI_MASTER_*` · **Docs:** https://meilisearch.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — container memory limit **512m** (docs/infrastructure/vps-complete-inventory.md:603); connection/pool caps are the service's own config |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 12 | Push delivery (webhooks/streams) | n/a — no webhooks; a fleet service pushes nothing (alerts flow via Prometheus → Alertmanager → Apprise/Telegram) |
| — | **Resilience posture (58)** | self-hosted `:7700`; 5s search / 30s indexing; search → empty results, indexing → retry via job queue (58:432); index auto-created by the `has_search_feature` registrar |

- **Purpose** _(2026-06-02 entry)_: Search engine
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Full-text search - Domain: `https://search.vps1.ocoron.com` - Port: 7700
- **Notes** _(2026-06-02 entry)_: - Self-hosted on VPS - amd64 compatible
- **Research notes** _(2026-09-02)_: Grounding impossible: session has no web search/fetch tools; cannot cite any vendor URL.

### Supabase

**Type:** storage · **Reach:** REST API (env key) · **Used by:** 15 project(s) — fabrik, gmail-account-creator, spec:fabrik-test-file-api, spec:fabrik-test-file-worker, spec:fabrik-test-static-site, spec:gate-saas, spec:gmail-account-creator, spec:test-file-log … · **Env keys:** `NEXT_PUBLIC_SUPABASE_ANON_*`, `SUPABASE_ANON_*`, `SUPABASE_SERVICE_ROLE_*` · **Docs:** https://supabase.com · **Catalog status:** retiring

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Free: 2 active projects, 500 MB DB, 5 GB egress, paused after 1 week idle; 'unlimited API requests'; Auth e.g. 2 emails/h built-in SMTP; Mgmt API 120 req/min/user/project. _(src: https://supabase.com/pricing, 2026-09-02)_ |
| 2 | Behaviour AT the cap | Auth 429 token-bucket (burst 30); Mgmt API 429 for rest of minute; free projects paused. _(src: https://supabase.com/docs/guides/auth/rate-limits, 2026-09-02)_ |
| 3 | Concurrency & parallelism | Direct connections 60 (Micro)–500; pooler 200–12,000 by compute size. _(src: https://supabase.com/pricing, 2026-09-02)_ |
| 4 | Identity posture | Org-based billing; ToS UNKNOWN — not fetched. _(src: https://supabase.com/pricing, 2026-09-02)_ |
| 5 | Failure & resume | Mgmt API X-RateLimit-* for proactive backoff; DB webhooks async via pg_net; PostgREST idempotent reads. _(src: https://supabase.com/docs/reference/api/introduction, 2026-09-02)_ |
| 6 | Cost model | Free / Pro $25 / Team $599; compute hourly (Micro $10/mo); egress $0.09/GB; disk $0.125/GB. _(src: https://supabase.com/pricing, 2026-09-02)_ |
| 7 | Usage observability | Mgmt API headers + usage endpoints /v1/projects/:ref/endpoints/usage.api-counts (30/min). _(src: https://supabase.com/docs/reference/api/introduction, 2026-09-02)_ |
| 8 | Health signal | Statuspage JSON: 'minor — Partially Degraded Service' (2026-09-02). _(src: https://status.supabase.com/api/v2/status.json, 2026-09-02)_ |
| 9 | Credential lifecycle | anon/service_role JWTs deprecated by end 2026; publishable/secret keys coexist -> overlap rotation; PATs custom expiry. _(src: https://supabase.com/docs/guides/api/api-keys, 2026-09-02)_ |
| 10 | Interface lifecycle | Mgmt API /v1; deprecations via docs/GitHub announcement; no headers documented. _(src: https://supabase.com/docs/guides/api/api-keys, 2026-09-02)_ |
| 11 | Data contract | DB webhook payload {type,table,schema,record,old_record}; DELETE carries old_record only. _(src: https://supabase.com/docs/guides/database/webhooks, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | Database Webhooks (pg_net, POST/GET JSON); call log in `net` schema; retry/signature UNKNOWN. _(src: https://supabase.com/docs/guides/database/webhooks, 2026-09-02)_ |
| — | **Resilience posture (58)** | legacy Pattern B; migrate to self-hosted Pattern A (35-security-auth; agents-fabrik.md § Supabase) |

- **Purpose** _(2026-06-02 entry)_: Backend-as-a-Service (PostgreSQL + Auth + Storage)
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://<project-ref>.supabase.co` - REST API: `https://<project-ref>.supabase.co/rest/v1/` - Auth API: `https://<project-ref>.supabase.co/auth/v1/` - Storage API: `https://<project-ref>.supabase.co/storage/v1/`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Database, authentication, file storage - Project ID: `xjmsceegyztgtcpywhry`
- **Notes** _(2026-06-02 entry)_: - PostgreSQL with Row Level Security (RLS) - Built-in authentication - File storage with signed URLs
- **Research notes** _(2026-09-02)_: RETIRING here — brief profile; note the 2026 legacy-key sunset for any lingering trade-intelligence keys.


## Identity & auth

### Authelia

**Type:** auth · **Reach:** self-hosted container on the `fabrik` network · **Runs on:** vps1 (`docker ps` 2026-09-02) · **Used by:** 0 project(s) — fleet service, no per-project key

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — container memory limit **512m** (docs/infrastructure/vps-complete-inventory.md:608); connection/pool caps are the service's own config |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | self-hosted forward-auth for admin dashboards only, never end-user auth (35-security-auth:108); config reload = `docker restart` (CLAUDE.md HARD STOPS); `/health*` paths bypassed on every domain |

### Zitadel

**Type:** auth · **Reach:** self-hosted container on the `fabrik` network · **Runs on:** vps1 (`docker ps` 2026-09-02) · **Used by:** 0 project(s) — fleet service, no per-project key

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — container memory limit **1024m** (docker inspect 2026-09-02 (not in the inventory table)); connection/pool caps are the service's own config |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### Better Auth

**Type:** auth · **Reach:** REST API (env key) · **Used by:** 1 project(s) — tojlo-mail · **Env keys:** `BETTER_AUTH_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'better-auth rate limit' — suggested src: https://www.better-auth.com/docs |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'better-auth 429' — suggested src: https://www.better-auth.com/docs |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'better-auth concurrency' — suggested src: https://www.better-auth.com/docs |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'better-auth plugins' — suggested src: https://www.better-auth.com/docs/concepts/plugins |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'better-auth session resume' — suggested src: https://www.better-auth.com/docs/concepts/session |
| 6 | Cost model | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'better-auth pricing' — suggested src: https://www.better-auth.com/ |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'better-auth admin api' — suggested src: https://www.better-auth.com/docs/plugins/admin |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'better-auth status page' — suggested src: https://www.better-auth.com/ |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'better-auth api key plugin' — suggested src: https://www.better-auth.com/docs/plugins/api-key |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'better-auth versioning' — suggested src: https://www.better-auth.com/docs |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'better-auth schema' — suggested src: https://www.better-auth.com/docs/concepts/database |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'better-auth webhooks' — suggested src: https://www.better-auth.com/docs/plugins/webhooks |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Open-source auth library; live web fetch was unavailable in this run.

### Google OAuth (Sign-in)

**Type:** auth · **Reach:** REST API (env key) · **Used by:** 1 project(s) — tojlo-mail · **Env keys:** `GOOGLE_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Google OAuth 2.0 limits: Queries per second (QPS) per project, varies by endpoin' but its source is dead/unfetched (https://developers.google.com/identity/protocols/oauth2/limits); re-verify live |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'HTTP 429 with Retry-After for exceeding QPS. QuotaExceeded error. No overage bil' but its source is dead/unfetched (https://developers.google.com/identity/protocols/oauth2/limits); re-verify live |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Concurrent requests limited by QPS per project. Scoped to OAuth client ID. No ex' but its source is dead/unfetched (https://developers.google.com/identity/protocols/oauth2/limits); re-verify live |
| 4 | Identity posture | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Per Google Cloud project. Multiple accounts/projects allowed under ToS (no abuse). https://cloud.google.com/terms — verify: https://cloud.google.com/terms |
| 5 | Failure & resume | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Retryable on 429, 5xx. Token endpoints idempotent for same request. Auth code flow state for resume. https://developers.google.com/identity/protocols/oauth2 — verify: https://developers.google.com/identity/protocols/oauth2 |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Free for authentication/authorization. No unit cost. Spikes from high user count/QPS. https://developers.google.com/identity/protocols/oauth2 — verify: https://developers.google.com/identity/protocols/oauth2 |
| 7 | Usage observability | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Quota usage visible in Google Cloud Console under APIs & Services > Dashboard for OAuth2 API. https://cloud.google.com/docs/quota — verify: https://cloud.google.com/docs/quota |
| 8 | Health signal | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Google Cloud Status Dashboard covers OAuth service health. No OAuth-specific status API. https://status.cloud.google.com — verify: https://status.cloud.google.com |
| 9 | Credential lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): OAuth client secrets don't expire. Refresh tokens expire after 6 months of inactivity. Expired returns invalid_grant. https://developers.google.com/identity/protocols/oauth2 — verify: https://developers.google.com/identity/protocols/oauth2 |
| 10 | Interface lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): OAuth 2.0 endpoints versioned via URL path. Deprecation via Google Cloud Console announcements. https://developers.google.com/identity/protocols/oauth2 — verify: https://developers.google.com/identity/protocols/oauth2 |
| 11 | Data contract | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Schema for token response documented. No pagination for core endpoints. Deletion of OAuth consent via Google Admin. https://developers.google.com/identity/protocols/oauth2 — verify: https://developers.google.com/identity/protocols/oauth2 |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Not a push service; it's an authentication protocol. No webhooks.' but its source is dead/unfetched (no url); re-verify live |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Core Google auth service; quotas can be increased via Cloud Console. Token lifecycle (refresh-token death rules, 7-day Testing expiry, 6-month idle) is grounded in `### Google APIs — Gmail + OAuth` row 9 (§ Email) — one source, not two.

### Microsoft 365 / Graph

**Type:** infra-platform · **Reach:** REST API (Graph, OAuth cert/app-only) + IMAP/SMTP XOAUTH2 (`outlook.office365.com`) · **Used by:** 5 project(s) — email-reader, fabrik-lib, spec:email-reader, tojlo-mail, tryton-crm (env keys + code call sites) · **Hosts:** `login.microsoftonline.com`, `outlook.office.com`, `outlook.office365.com` · **Env keys:** `M365_*`, `MICROSOFT_*` · **Docs:** https://learn.microsoft.com/en-us/graph/

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Graph global: 130,000 requests/10 s per app across all tenants. Outlook (mail/calendar/contacts): limits are per app-ID + mailbox pair — 10,000 API requests per 10-minute period, 4 concurrent requests, 150 MB upload (PATCH/POST/PUT) per 5 minutes (v1.0 and beta); exceeding one mailbox's limit doesn't affect other mailboxes. Subscriptions: POST/PUT/DELETE/PATCH 500 req/20 s per app per tenant (2,000 across tenants), list 25/20 s. Service-communications: 240 req/60 s + 800 req/hour per app per tenant. Entra directory (identity) token-bucket: 3,500/5,000/8,000 ResourceUnits per 10 s per app+tenant (S/M/L tenant), 150,000 RU/20 s per app, writes 3,000/2.5 min. Exchange Online sending (per mailbox, all licensed plans): 30 messages/minute, 10,000 recipients/day, ≤1,000 recipients/message (customizable), message size 150 MB; TERRL tenant external-recipient cap (trial 5,000/day); default onmicrosoft.com domains 100 external recipients/24 h. Outlook message subscriptions: max 1,000 active per mailbox for all apps. Entra token endpoint (`login.microsoftonline.com`) limits: not published — MSAL doc only says client_credentials throttling returns `429` + `Retry-After: 60`. _(src: https://learn.microsoft.com/en-us/graph/throttling-limits, 2026-09-02)_ |
| 2 | Behaviour AT the cap | `429 Too Many Requests` with `Retry-After` header (seconds) and body `{error:{code:"TooManyRequests", message:"Please retry again later.", innerError{date, request-id, status:"429"}}}`; "All the resources and APIs described in the Service-specific limits provide a Retry-After header except where indicated"; if absent, use exponential backoff; usage keeps accruing while throttled, so retry only after `Retry-After`. Inside a `$batch` the batch returns 200 while individual sub-requests return 429 with their own `retry-after` (SDKs do NOT auto-retry batched items). Directory (identity) responses also carry `x-ms-throttle-limit-percentage` (0.8–1.8, only when >80% consumed), `x-ms-throttle-scope`, `x-ms-throttle-information` (e.g. CPULimitExceeded/WriteLimitExceeded). Exchange sending: messages over 30/min are throttled and "carried over to the following minutes"; recipient-rate cap blocks sending until the 24 h window drains. Entra token endpoint: `429` + `Retry-After` ("often indicates the application isn't caching and reusing tokens"); 5xx without Retry-After → backoff ≥5 s. _(src: https://learn.microsoft.com/en-us/graph/throttling, 2026-09-02)_ |
| 3 | Concurrency & parallelism | Outlook: 4 concurrent requests per app+mailbox; Graph forwards at most 4 requests of a JSON batch to the Outlook service at a time (1 at a time when `dependsOn` is used); batch max 20 requests, responses may return out of order, dependent requests fail 424 if a dependency fails. Bookings: 4 concurrent per app; OneNote 5/20 concurrent. Limits evaluated per app across all tenants, per tenant all apps, and per app per tenant — the first limit hit throttles. _(src: https://learn.microsoft.com/en-us/graph/json-batching, 2026-09-02)_ |
| 4 | Identity posture | Per app registration (Application ID + credential) per Entra tenant. Delegated access = app + signed-in user, needs delegated permissions (scopes); app-only access = app's own identity via client-credentials, needs application permissions (app roles) which "require administrator privileges to grant consent". IMAP/POP/SMTP app-only additionally needs `New-ServicePrincipal` in Exchange Online PowerShell + `Add-MailboxPermission … -AccessRights FullAccess` per mailbox, scope `https://outlook.office365.com/.default`; delegated IMAP scope `https://outlook.office.com/IMAP.AccessAsUser.All` (POP `POP.AccessAsUser.All`, SMTP `SMTP.Send`), SASL XOAUTH2. Microsoft APIs Terms of Use (Last Updated October 2025): may not "attempt to circumvent the limitations Microsoft sets", Access Credentials "non-transferable and non-assignable", email protocols/APIs usable only for syncing or backing up mail/calendar/contacts unless the customer grants other use; Microsoft "may change or discontinue the availability of some or all of the Microsoft APIs at any time"; liability cap USD $5. No clause limiting number of app registrations found (tenant quota: non-admin user ≤250 directory objects). _(src: https://learn.microsoft.com/en-us/graph/auth/auth-concepts, 2026-09-02)_ |
| 5 | Failure & resume | Honour `Retry-After` and retry the same request; 503 may carry `Retry-After`; 409 Directory_ConcurrencyViolation → backoff retry. Resumable cursor = delta query (`/messages/delta`, `/mailFolders/delta`, `/events/delta`, `/contacts/delta`, `/users/delta`): follow `@odata.nextLink` until `@odata.deltaLink`; "must be prepared for replays"; `410 Gone` + `Location` with empty `$deltatoken` = full resync; Outlook delta tokens expire on cache pressure (no fixed TTL) → `syncStateNotFound` 40x → full resync; directory delta tokens valid 7 days; `$deltatoken=latest` for sync-from-now. No idempotency key on `sendMail` (202 Accepted only, delivery "subject to Exchange Online limitations"); large attachments resume via upload-session `nextExpectedRanges` (3–150 MB, ranges ≤4 MB, session bound by `expirationDateTime`). Smallest resumable unit = one Graph request / one delta page. _(src: https://learn.microsoft.com/en-us/graph/delta-query-overview, 2026-09-02)_ |
| 6 | Cost model | Standard Graph APIs (incl. Outlook mail/calendar) are "available at no additional cost with user subscription licenses" within the documented throttling thresholds; only "high-capacity" and "advanced" APIs are metered (need a linked Azure subscription, confidential client only; `402 Payment Required` if unmet) — making a standard API metered counts as a breaking change under the 24-month policy. Spike cost = M365/Exchange license seats, not per call; bulk extraction → Graph Data Connect. _(src: https://learn.microsoft.com/en-us/graph/metered-api-overview, 2026-09-02)_ |
| 7 | Usage observability | No usage/quota endpoint for Outlook — only `429` + `Retry-After`; directory-scoped requests expose `x-ms-resource-unit` per response and `x-ms-throttle-limit-percentage` once past 80% ("callers can use this value to set up an alert"). Token responses carry `expires_in` (example 3599 s) for cache scheduling. Exchange sending usage: Tenant Outbound External Recipients report in EAC (admin UI only). _(src: https://learn.microsoft.com/en-us/graph/throttling-limits, 2026-09-02)_ |
| 8 | Health signal | Machine-readable but authenticated: `GET /v1.0/admin/serviceAnnouncement/healthOverviews` / `issues` / `messages` (permissions `ServiceHealth.Read.All`, `ServiceMessage.Read.All`; delegated AND application; admin-consent only), `serviceHealth.status` enum `serviceOperational, investigating, restoringService, verifyingService, serviceRestored, postIncidentReviewPublished, serviceDegradation, serviceInterruption, extendedRecovery, falsePositive, investigationSuspended, resolved, mitigatedExternal, mitigated, resolvedExternal, confirmed, reported`; throttled 240/60 s + 800/h per app-tenant. Public unauthenticated page https://status.cloud.microsoft/m365 returned "Service degradation on Microsoft 365 (Business or Enterprise) … Users may experience issues when utilizing multiple Microsoft 365 services" on first fetch today and "All products are operational" on a later fetch; advertises RSS but no resolvable feed URL found (tried /api/feed/m365 → 400, /m365/rss → HTML, admin.microsoft.com/api/servicestatus/index → 404). Not Statuspage-shaped. _(src: https://learn.microsoft.com/en-us/graph/api/resources/service-communications-api-overview, 2026-09-02)_ |
| 9 | Credential lifecycle | Client secret: max lifetime 24 months, Microsoft recommends <12 months, value shown once, "should not be used in production"; certificate credential recommended (JWT client_assertion, `alg` PS256, `x5t#S256`, `aud` = token endpoint, keep `exp` 5–10 min after `nbf`); `keyCredentials` is multi-valued → overlap rotation by uploading the second cert before removing the first; federated (workload identity) credentials avoid secrets entirely; app-management policies can cap secret lifetime or block secrets. Access tokens: random 60–90 min (avg 75; CAE-capable up to 24–28 h; configurable 10 min–1 day via TokenLifetimePolicy, no portal UI); client-credentials flow returns NO refresh token — re-POST `/{tenant}/oauth2/v2.0/token` with `scope=https://graph.microsoft.com/.default` (or `https://outlook.office365.com/.default` for IMAP/POP/SMTP); delegated refresh tokens: 90-day max inactive, until-revoked max age (not configurable since 2021-01-30). Expired/invalid token → `401`; conditional-access → `403 insufficient_claims`. _(src: https://learn.microsoft.com/en-us/entra/identity-platform/how-to-add-credentials, 2026-09-02)_ |
| 10 | Interface lifecycle | Two endpoints: `https://graph.microsoft.com/v1.0` (GA, production) and `/beta` ("Expect breaking changes and deprecation … Use of beta APIs in production applications is not supported"). GA API or version deprecation announced ≥24 months before removal; a major version bump (v1.0→v2.0) deprecates the old one immediately with 24-month support; "Currently, no versions of Microsoft Graph are deprecated or unsupported"; changes tracked in the changelog (https://developer.microsoft.com/graph/changelog); SDK previous major supported 12 months, security-only. Deprecation/Sunset/Link response headers: UNKNOWN in official docs — tried versioning-and-support, errors, throttling; only third-party observation (StackOverflow 70984573, beta, 2022) shows `Deprecation:`/`Sunset:`/`Link: …;rel="deprecation"`. EWS is retiring in favour of Graph (Exchange team blog, sunset headers announced). _(src: https://learn.microsoft.com/en-us/graph/versioning-and-support, 2026-09-02)_ |
| 11 | Data contract | Errors: `{error:{code, message, innerError{code, request-id, client-request-id, date}, details[]}}` — code on `code` only, never on `message`; statuses 400/401/402/403/404/409/410/412/413/422/423/429/500/503/504/507/509. Backward-compatible (no version bump) changes you MUST tolerate: new nullable/defaulted properties, new enum members, paging introduced on existing collections, error-code changes, property order, length/format of opaque IDs — never strict-reject unknown enums/properties. Paging `@odata.nextLink`; delta `@odata.deltaLink` + `@removed:{reason:changed\|deleted}`; batch `{responses:[{id,status,headers,body}]}` unordered. Tokens are opaque — "Clients use the token but shouldn't understand or attempt to parse it". Change-notification payload `{value:[{id, subscriptionId, subscriptionExpirationDateTime, clientState, changeType, resource, tenantId, resourceData{@odata.type,@odata.id,@odata.etag,id}}]}`. _(src: https://learn.microsoft.com/en-us/graph/errors, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | Webhooks (also Event Hubs / Event Grid): create `POST /subscriptions` {changeType created,updated,deleted; notificationUrl HTTPS public; clientState ≤128 chars (required by the how-to); lifecycleNotificationUrl}; Graph POSTs `?validationToken=` and needs the decoded token echoed as `text/plain` 200 within 10 s; duplicate resource+changeType → 409. Outlook message/event/contact subscriptions expire ≤10,080 min (<7 days) — 1,440 min for rich (resource-data) subscriptions; any expiration <45 min is raised to 45 min; renew via `PATCH /subscriptions/{id}` (also reauthorizes); never issue `/reauthorize` and PATCH within 10 min of each other. Delivery: 2xx within 3 s = delivered; else retried with exponential backoff up to 4 h (timeout 10 s on retries); endpoint marked "slow" (>10% over 3 s in 10 min → 10-min delay) or "drop" (>15% over 10 s → notifications dropped 10 min, unrecoverable); multiple notifications batched in one POST; message latency <1 min avg / 3 min max; endpoint validation token expires ~1 h (renewal refreshes it). Lifecycle events `reauthorizationRequired`, `subscriptionRemoved`, `missed` (the last two Outlook-only) → respond 202, then reauthorize/recreate and run delta to reconcile; notifications lost between removal and re-create must be fetched via delta. Verify `clientState` equals your secret; no HMAC signature. _(src: https://learn.microsoft.com/en-us/graph/change-notifications-delivery-webhooks, 2026-09-02)_ |
| — | **Resilience posture (58)** | mailbox read/send + OAuth; app-only cert auth (no refresh token — re-mint on 401); webhook receiver = public HTTPS route + `validationToken` echo + `clientState` compare in handler, `202` fast-ack + queue (57 § Doc Sync); every `missed`/`subscriptionRemoved` → delta resync; renew subscriptions before the 7-day cap; per-mailbox 429 budget (10k/10 min, 4 concurrent) honoured via `Retry-After` |

- **Purpose** _(2026-06-02 entry)_: Email reading (ob@ocoron.com)
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://graph.microsoft.com/v1.0` - Read Emails: `GET /users/{id}/mailFolders/inbox/messages` - Send Email: `POST /users/{id}/sendMail`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Read emails for verification codes - Target Email: `ob@ocoron.com`
- **Notes** _(2026-06-02 entry)_: - Certificate-based authentication (no user interaction) - Requires certificate file on server
- **Research notes** _(2026-09-02, re-grounded)_: vendor status: https://status.cloud.microsoft/m365 (public HTML, JS-rendered; offers an "RSS" link whose feed URL could not be resolved — `/api/feed/m365` → HTTP 400, `/m365/rss` → same HTML; machine-readable health only via the authenticated `/v1.0/admin/serviceAnnouncement` API).

### Turnstile

**Type:** auth · **Reach:** REST API (env key) · **Used by:** 1 project(s) — web-ecommerce-factory · **Env keys:** `TURNSTILE_*`, `TURNSTILE_SITE_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |


## Payments & billing

### Paddle

**Type:** payments · **Reach:** REST API (env key) · **Used by:** 3 project(s) — trade-intelligence, transdoc, youtube · **Env keys:** `NEXT_PUBLIC_PADDLE_CLIENT_*`, `PADDLE_*`, `PADDLE_CLIENT_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | 240 req/min per IP (platform); 1,000 req/min per IP for preview-transaction/preview-prices; per-subscription immediate-charge caps 20/hour and 100/24h. Webhooks: 200 within 5s required. _(src: https://developer.paddle.com/api-reference/about/rate-limiting, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 + Retry-After header, error code too_many_requests; the IP is locked out for 60s after exceeding. Subscription charge caps return 429 with subscription_immediate_charge_hour_limit_exceeded / _24_hour_limit_exceeded. No overage billing. _(src: https://developer.paddle.com/api-reference/about/rate-limiting, 2026-09-02)_ |
| 3 | Concurrency & parallelism | No explicit in-flight cap documented; the 240/min limit is scoped per IP (so extra workers behind one egress IP buy nothing). _(src: https://developer.paddle.com/api-reference/about/rate-limiting, 2026-09-02)_ |
| 4 | Identity posture | Rate limit per IP; keys per account with granular permissions + secret scanning. Multiple accounts explicitly permitted by Paddle Help: 'TL;DR - yes you can' (one account per business, unique email each). _(src: https://www.paddle.com/help/start/set-up-paddle/can-i-have-multiple-paddle-accounts, 2026-09-02)_ |
| 5 | Failure & resume | 5xx: 'Retry with exponential backoff'; 429 per rate-limit page. No Idempotency-Key header documented (errors page and send-side reference show none). Resume = cursor pagination (after=<id>, has_more). Every response carries meta.request_id. _(src: https://developer.paddle.com/api-reference/about/errors, 2026-09-02)_ |
| 6 | Cost model | Pay-as-you-go: 5% + 50c per checkout transaction (Merchant of Record — tax, fraud, dunning included); custom pricing if products <$10 or invoicing. Chargeback/FX surcharges not itemised on the pricing page. _(src: https://www.paddle.com/pricing, 2026-09-02)_ |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) rate-limiting page, errors page, authentication page — no X-RateLimit-* headers or usage endpoint documented; only Retry-After on a 429. — suggested src: https://developer.paddle.com/api-reference/about/rate-limiting |
| 8 | Health signal | status.paddle.com 301s to paddlestatus.com (component board: Checkout, Paddle API, Webhooks & Alerts, ...). NOT Statuspage: /api/v2/status.json returns the HTML page, not JSON. 'Subscribe to updates' present; machine-readable feed not confirmed. _(src: https://paddlestatus.com/, 2026-09-02)_ |
| 9 | Credential lifecycle | Keys have a mandatory expiry date set at creation; expired keys 'can't be revalidated'. Rotatable keys (AWS Secrets Manager): new secret activates on first use, OLD SECRET STAYS VALID FOR A GRACE PERIOD (overlap), grace can be set to 0; rotation extends expiry. Accidental revoke has a 60-minute reactivation window (not for exposure-revoked keys). Webhooks api_key.expiring / api_key.expired / api_key.revoked available. Response code for an expired key not stated on these pages. _(src: https://developer.paddle.com/api-reference/about/rotate-api-keys/, 2026-09-02)_ |
| 10 | Interface lifecycle | Sequential integer versions via Paddle-Version header; current = 1; account default pinned, opt-in upgrades; 'We don't deprecate older versions of our API right now. We'll communicate future announcements around deprecation in plenty of time.' No Deprecation/Sunset headers documented; channel = developer changelog. Webhook destinations pin their own api_version. _(src: https://developer.paddle.com/api-reference/about/versioning, 2026-09-02)_ |
| 11 | Data contract | Envelope {data, meta{request_id, pagination{per_page,next,has_more,estimated_total}}}; cursor = Paddle ID (after=); default 50/page, max 200 (transactions 30, adjustments 10/50); estimated_total capped at 100001 / -1 when skipped. Non-breaking (no version bump): new fields, new optional params, field reordering. Errors: {error{type,code,detail,documentation_url,errors[]}}. _(src: https://developer.paddle.com/api-reference/about/pagination, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | At-least-once; live: 60 retries over 3 days (20 in first hour, 47 in day 1; exponential base 60s x1.1), sandbox 3 retries/15 min; 'We can't guarantee the order of delivery' — check occurred_at; event_id + notification_id for dedup; Paddle-Signature: ts=<unix>;h1=<HMAC-SHA256(ts:body)>, SDK tolerance 5 seconds; list endpoint GET /notifications (90-day retention, status filter delivered/failed/needs_retry/not_attempted) + POST /notifications/{id}/replay (creates new notification for same event_id, 90-day window). _(src: https://developer.paddle.com/webhooks/respond-to-webhooks, 2026-09-02)_ |
| — | **Resilience posture (58)** | 85-payments-billing § Paddle Billing v2 (MoR): webhook idempotency + entitlement model; receiver = public route + signature verification (57 § Doc Sync) |

- **Research notes** _(2026-09-02)_: Signature/tolerance: https://developer.paddle.com/webhooks/signature-verification · list/replay: https://developer.paddle.com/api-reference/notifications/list-notifications and .../replay-notification · key expiry: https://developer.paddle.com/api-reference/about/authentication (fetched via exa; WebFetch 404'd /concepts/api-keys/overview). All fetched 2026-09-02.

### Iyzico

**Type:** payments · **Reach:** REST API (env key) · **Used by:** 2 project(s) — transdoc, youtube · **Env keys:** `IYZICO_*`, `IYZICO_SECRET_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Per-method per-minute caps (EN 'Limiters' table): initialize payment 50/min, retrieve payment result 50/min, initialize HPP 100/min, retrieve HPP 100/min, refund 50/min, cancel 50/min. TR page lists finer per-endpoint caps (e.g. /payment/refund 400/min, /v2/payment/refund 150/min, /cardstorage/card 150/min, checkoutform initialize 8000/min). Max single payment price < 100,000 (error 5008) unless raised. _(src: https://docs.iyzico.com/en/getting-started/preliminaries/limiters, 2026-09-02)_ |
| 2 | Behaviour AT the cap | Body {status:'failure', errorCode:50000, errorMessage:'Request Limit Exceeded'} — HTTP status and Retry-After NOT documented (TR page's 'exceed' section is a placeholder: 'Buraya limitler aşınca gelen hata kodu girilecek'). Treat as hard block for the window. _(src: https://docs.iyzico.com/en/getting-started/preliminaries/limiters, 2026-09-02)_ |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) limiters page (EN+TR), HMACSHA256 auth page, API request details (404) — no concurrency statement; limits are per-merchant per-method. — suggested src: https://docs.iyzico.com/en/getting-started/preliminaries/limiters |
| 4 | Identity posture | Limits per merchant (API key/merchantId). Multi-account ToS: UNKNOWN — tried: brave search for merchant agreement multi-account clause (no hit); iyzico is a BDDK-licensed PSP, each merchant account is KYC'd — assume one legal entity = one merchant account. _(src: https://docs.iyzico.com/en/getting-started/preliminaries/limiters, 2026-09-02)_ |
| 5 | Failure & resume | 'Majority of iyzico services have designed non-idempotent'; no Idempotency-Key. Correlate via merchant conversationId/basketId and iyzico token/paymentId; resume by re-querying /payment/detail with paymentId or paymentConversationId. Bank REQUEST_TIMEOUT 10219 / TIMEOUT 10240 are retry-later classes. _(src: https://docs.iyzico.com/en/getting-started/preliminaries/idempotency, 2026-09-02)_ |
| 6 | Cost model | Per successful transaction: commission % (help centre: corporate offer 3.99% + 0.25 TL; other pages quote 'from 2.49%'/'from 4.29%') + 0.25 TL fixed; no setup/monthly fee; instalments add bank-specific interest. Spike = instalment interest and refunds. _(src: https://www.iyzico.com/destek/yardim-merkezi/genel-bilgiler/fiyatlandirma, 2026-09-02)_ |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) limiters, error-codes, llms.txt index — no usage/quota endpoint or rate headers documented; Reporting Service exists for transactions only. — suggested src: https://docs.iyzico.com/llms.txt |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) brave 'iyzico status page / durum sayfası', docs llms.txt — no public status page found; only the error-codes note 'same error >5 times within 1 minute, contact your account manager'. — suggested src: https://docs.iyzico.com/en/add-ons/error-codes |
| 9 | Credential lifecycle | API Key + Secret Key pairs per merchant (sandbox- prefix in sandbox); IYZWSv2 header = base64(apiKey&randomKey&HMACSHA256(randomKey+path+body, secretKey)). No expiry documented; rotation via merchant portal — overlap semantics UNKNOWN (tried: sandbox + auth pages). Auth failure returns status:'failure' with errorCode (no HTTP code documented). _(src: https://docs.iyzico.com/en/getting-started/preliminaries/authentication/hmacsha256-auth, 2026-09-02)_ |
| 10 | Interface lifecycle | Path-versioned endpoints (/payment/refund vs /v2/payment/refund; /v2/subscription/...). Deprecation channel = doc banners only, e.g. 'X-Iyz-Signature and X-Iyz-Signature-V2 will no longer supported ... in timely manner' (no date). No Deprecation/Sunset headers. Docs are GitBook with llms.txt + .md pages. _(src: https://docs.iyzico.com/en/advanced/webhook, 2026-09-02)_ |
| 11 | Data contract | Response {status success/failure, locale, systemTime(epoch ms), conversationId, errorCode/errorMessage/errorGroup}; payment objects carry fraudStatus (1/0/-1) and itemTransactions[] with paymentTransactionId (must be stored). OpenAPI 3.0.3 specs embedded per page (api.iyzipay.com). Error code groups: bank 10xxx, card storage 3xxx; full list is a downloadable file. _(src: https://docs.iyzico.com/en/advanced/retrieve-payment, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | First POST 10–15s after payment attempt; retried every 15 minutes until 2xx, 'Notifications will stop after 3 attemps'. Payload has iyziReferenceCode (unique per notification) + iyziEventTime; no ordering statement. Signature X-IYZ-SIGNATURE-V3 = HEX(HMACSHA256(secretKey+iyziEventType+paymentId+paymentConversationId+status, secretKey)) — NO timestamp in the signed string (replay window unbounded); signature must be enabled by emailing entegrasyon@iyzico.com. No list/replay endpoint — reconcile by /payment/detail. _(src: https://docs.iyzico.com/en/advanced/webhook, 2026-09-02)_ |
| — | **Resilience posture (58)** | 85-payments-billing (Turkish domestic); UNSIGNED provider → `shape.needs_payments_ingest` mints the scoped ingest role (spec_loader.py:333) |

- **Research notes** _(2026-09-02)_: docs.iyzico.com/en/advanced/api-request-details is a 404 today. TR limit tables: https://docs.iyzico.com/on-hazirliklar/limitler (exa highlights). Pricing page /en/pricing 404 — figure is from the help centre. All fetched 2026-09-02.

### Revenuecat

**Type:** payments · **Reach:** REST API (env key) · **Used by:** 5 project(s) — rn-kit-sandbox, rnfinal, spec:supplement-tracker-advisor, spec:test-mobile, supplement-tracker-advisor · **Env keys:** `EXPO_PUBLIC_REVENUECAT_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | API v2 per-domain req/min: Customer 480, Virtual Currencies 480, Project Configuration 60, Audiences 60, Charts & Metrics 25; window = 1 minute. v1: variable, guidance ~1 req/s (community answer by RC staff, not a doc). Webhooks: respond within 60s. _(src: https://www.revenuecat.com/docs/api-v2, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 with body type rate_limit_error + backoff_ms; headers RevenueCat-Rate-Limit-Current-Usage, RevenueCat-Rate-Limit-Current-Limit, Retry-After (seconds). v1 429s carry no such headers. _(src: https://www.revenuecat.com/docs/api-v2, 2026-09-02)_ |
| 3 | Concurrency & parallelism | No in-flight cap documented; limit scoped 'per API key (for app-level keys) or per developer (for developer-level keys)'. _(src: https://www.revenuecat.com/docs/api-v2, 2026-09-02)_ |
| 4 | Identity posture | Per-key/per-project. ToS (Mar 20 2024) frames the Customer as an entity with Usage Limitations per Order; §3.1 forbids reselling/service-bureau use; no explicit multi-account clause found in the fetched sections (first ~5k chars) — UNKNOWN beyond that. _(src: https://www.revenuecat.com/terms/, 2026-09-02)_ |
| 5 | Failure & resume | No idempotency key on the REST API ('No idempotency support documented'); forward-only cursor pagination (starting_after=<id>, limit default 20, next_page URL). Webhook retries preserve id + event_timestamp_ms. _(src: https://www.revenuecat.com/docs/api-v2, 2026-09-02)_ |
| 6 | Cost model | Free up to $2,500 monthly tracked revenue (MTR); then 1% of MTR. Spike driver = tracked revenue growth, not API calls. _(src: https://www.revenuecat.com/pricing, 2026-09-02)_ |
| 7 | Usage observability | Only via the rate-limit headers on every v2 response (Current-Usage / Current-Limit); no standalone quota endpoint. MTR visible in dashboard; not fetched via API on these pages. _(src: https://www.revenuecat.com/docs/api-v2/rate-limit, 2026-09-02)_ |
| 8 | Health signal | Statuspage: https://status.revenuecat.com/api/v2/status.json returned {'status':{'indicator':'none','description':'All Systems Operational'}} today; incidents/unresolved.json + scheduled-maintenances/upcoming.json follow the Statuspage convention. _(src: https://status.revenuecat.com/api/v2/status.json, 2026-09-02)_ |
| 9 | Credential lifecycle | Secret keys sk_* (project-wide, unlimited count, revocable any time; 'When a secret API key is revoked, it's invalidated immediately'); no expiry documented; rotation = create new + revoke old (overlap by having two keys). v1 keys don't work on v2. Webhook signing secret rotation: 'The old secret is immediately invalidated' (no overlap). _(src: https://www.revenuecat.com/docs/projects/authentication, 2026-09-02)_ |
| 10 | Interface lifecycle | Path versioning /v1 vs /v2 (different keys); v1 still served, no sunset date on the v1 page; no Deprecation/Sunset headers documented (UNKNOWN — tried api-v1 + api-v2 pages). _(src: https://www.revenuecat.com/docs/api-v1, 2026-09-02)_ |
| 11 | Data contract | List objects {object:'list', items[], next_page, url}; forward-only; error types incl. rate_limit_error. Webhook payload: {api_version, event{id, type, event_timestamp_ms, app_user_id, ...}}. _(src: https://www.revenuecat.com/docs/api-v2, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | At-least-once (retries with same id); 'retry later (up to 5 times) with an increasing delay (5, 10, 20, 40, and 80 minutes)' then stops (~2.6h total); 60s timeout; no ordering guarantee; dedup on event.id; signature X-RevenueCat-Webhook-Signature: t=<unix>,v1=<HMAC-SHA256 hex over '<t>.<raw body>'>, tolerance suggested 'e.g. 5 minutes'; also a static Authorization header option; replay = dashboard 'Retry' per event only — no list-events API. _(src: https://www.revenuecat.com/docs/integrations/webhooks, 2026-09-02)_ |
| — | **Resilience posture (58)** | mobile IAP entitlements per 81-mobile (85 § Scope exclusion — Mobile IAP) |

- **Research notes** _(2026-09-02)_: v1 rate guidance source is a RevenueCat community post (https://community.revenuecat.com/general-questions-7/what-are-the-current-rate-limits-on-the-rest-api-4946) — staff answer, not docs. All fetched 2026-09-02.

### Gumroad

**Type:** payments · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found)

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | - Type: Webhook Secret - Env Vars: `GUMROAD_WEBHOOK_SECRET` - Generate at: Gumroad Dashboard → Settings → Advanced → Webhook Secret — expiry/rotation UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Payment platform
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Payment webhooks
- **Notes** _(2026-06-02 entry)_: - Placeholder (not configured yet)


## Email, messaging & notifications

### Resend

**Type:** email · **Reach:** REST API (env key) · **Used by:** 7 project(s) — brand-identiy-creator, fabrik, seo, site-provisioner, spec:zitadel, transdoc, youtube · **Env keys:** `OUTREACH_RESEND_*`, `RESEND_*` · **Docs:** https://resend.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | 10 requests/second per team (raisable on request); batch endpoint ≤100 emails/call; ≤50 recipients per to; attachments ≤40 MB/email (post-base64); Free plan 100 emails/day + 3,000/month (sent AND received count); Pro 50k/mo ($20) or 100k/mo ($35). Idempotency keys ≤256 chars, 24h. _(src: https://resend.com/docs/api-reference/rate-limit, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 rate_limit_exceeded with ratelimit-limit / ratelimit-remaining / ratelimit-reset / retry-after headers; 429 daily_quota_exceeded ('wait until 24 hours have passed') and monthly_quota_exceeded — hard block on Free; Pro overage billed at $0.90 per 1,000 extra emails. _(src: https://resend.com/docs/api-reference/errors, 2026-09-02)_ |
| 3 | Concurrency & parallelism | No in-flight cap beyond the 10 rps team bucket ('reduce the number of concurrent requests per second'); 409 resource_locked / concurrent_idempotent_requests when parallel calls hit the same resource/key. _(src: https://resend.com/docs/api-reference/errors, 2026-09-02)_ |
| 4 | Identity posture | Per team. ToS: Free Tier 'subject to usage limits' and Resend may 'convert Free Tier accounts to paid Subscriptions if usage exceeds Free Tier limits'; no explicit one-account-per-entity clause in the fetched text — UNKNOWN beyond that. _(src: https://resend.com/legal/terms-of-service, 2026-09-02)_ |
| 5 | Failure & resume | Idempotency-Key header on POST /emails and /emails/batch (24h window; mismatched body → 409 invalid_idempotent_request; SMTP header Resend-Idempotency-Key); retry 500 application_error 'later'; list endpoints are cursor-paginated (after/before ids, has_more). Smallest resumable unit = one email (or one batch call by key). _(src: https://resend.com/docs/dashboard/emails/idempotency-keys, 2026-09-02)_ |
| 6 | Cost model | Free $0 (3,000/mo, 100/day, 30-day retention); Pro $20/mo 50k, $35/mo 100k; +$0.90/1k overage. Spike = overage and quota-counted inbound mail. _(src: https://resend.com/pricing, 2026-09-02)_ |
| 7 | Usage observability | Rate-limit headers on every response (remaining/reset); quota (daily/monthly) usage exposed only in the dashboard — no usage endpoint documented (UNKNOWN — tried rate-limit, errors, api-keys pages). _(src: https://resend.com/docs/api-reference/rate-limit, 2026-09-02)_ |
| 8 | Health signal | Statuspage-compatible: https://resend-status.com/api/v2/status.json returned {'status':{'description':'All Systems Operational','indicator':'none'}} today (Instatus-hosted, exposes the Statuspage-shaped JSON). _(src: https://resend-status.com/api/v2/status.json, 2026-09-02)_ |
| 9 | Credential lifecycle | API keys re_*: no expiry documented; multiple keys allowed (name/permission/domain scoping) → overlap rotation by creating a second key then deleting; value never viewable after creation. Revoked/inactive key → 403 restricted_api_key 'API key is not active'; missing → 401 missing_api_key; suspended → 403. _(src: https://resend.com/docs/dashboard/api-keys/introduction, 2026-09-02)_ |
| 10 | Interface lifecycle | Unversioned API (https://api.resend.com/emails); changes via changelog/docs; no Deprecation/Sunset headers documented — UNKNOWN (tried errors, send-email, list-emails pages). _(src: https://resend.com/docs/api-reference/emails/send-email, 2026-09-02)_ |
| 11 | Data contract | Errors {statusCode, name, message}; lists {object:'list', has_more, data[]} with after/before cursor; email object {id, message_id, to, from, created_at, subject, last_event, scheduled_at}. Webhook payload {type, created_at, data{email_id, ...}}. _(src: https://resend.com/docs/api-reference/emails/list-emails, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | At-least-once ('may be delivered more than once in rare cases'); retries at 5s, 5m, 30m, 2h, 5h, 10h after each failure (~17.5h total); 'delivery order is not guaranteed' — sort by created_at; dedup on svix-id header; Svix signature: svix-signature v1,<base64 HMAC-SHA256 over 'svix-id.svix-timestamp.body'> keyed by base64(secret after whsec_), verify svix-timestamp within your tolerance (Svix docs give no fixed number; libs default 5 min); replay of failed AND succeeded events from the dashboard; webhook CRUD via API but no list-events API documented. _(src: https://resend.com/docs/dashboard/webhooks/introduction, 2026-09-02)_ |
| — | **Resilience posture (58)** | transactional email; `RESEND_DAILY_LIMIT` env knob; webhook receiver = public route + HMAC in handler (57 § Doc Sync) |

- **Purpose** _(2026-06-02 entry)_: Email delivery service (primary)
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://api.resend.com` - Send Email: `POST /emails` - List Emails: `GET /emails` - Get Domain: `GET /domains/{id}`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Transactional emails - Daily Limit: 100 emails
- **Notes** _(2026-06-02 entry)_: - Primary email service - Better deliverability than SES
- **Research notes** _(2026-09-02)_: Svix manual verification: https://docs.svix.com/receiving/verifying-payloads/how-manual. All fetched 2026-09-02.

### Amazon SES

**Type:** email · **Reach:** SMTP + REST API v2 (env key) · **Used by:** 1 project(s) — site-provisioner (`SES_SMTP_*`; the 2026-09-02 key-shape scan missed the `SES_SMTP_` prefix) · **Env keys:** `SES_SMTP_*` · **Docs:** https://docs.aws.amazon.com/ses/latest/dg/

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Sandbox (per Region, every new account): 200 emails/24h, 1 email/s, recipients must be verified identities or the mailbox simulator; production quota + rate 'varies based on your specific use case' (no default number published). Quotas are per AWS Region and count RECIPIENTS not messages (10 recipients = 10). Max message 40 MB after base64 (v2 API + SMTP; v1 API 10 MB) — >10 MB messages bandwidth-throttled 'to as low as 40MB/s'; ≤50 recipients per message; 10,000 verified identities/Region; all non-Send API actions throttled at 1 request/s; 500 MIME parts. _(src: https://docs.aws.amazon.com/ses/latest/dg/quotas.html, 2026-09-02)_ |
| 2 | Behaviour AT the cap | Hard-fail, no queueing: 'Amazon SES drops the message and doesn't attempt to redeliver it'. API/SDK → `ThrottlingException` with 'Daily message quota exceeded' or 'Maximum sending rate exceeded' (AWS: 'wait for an interval of up to 10 minutes, and then retry'); v2 `TooManyRequestsException` HTTP 429. SMTP → `454 Throttling failure: Maximum sending rate exceeded` / `454 Throttling failure: Daily message quota exceeded`; `421 Too many concurrent SMTP connections`. Rate may be exceeded 'for short bursts, but not for sustained periods'. Reputation pause → `SendingPausedException` (400); permanent → `AccountSuspendedException` (400). _(src: https://docs.aws.amazon.com/ses/latest/dg/manage-sending-quotas-errors.html, 2026-09-02)_ |
| 3 | Concurrency & parallelism | No documented in-flight cap beyond the per-second send rate (burst-tolerant); SMTP endpoint returns `421 Too many concurrent SMTP connections` at an UNPUBLISHED connection ceiling (UNKNOWN — tried troubleshoot-smtp, smtp-connect, quotas). SMTP fleet sits behind an ELB whose instances are 'periodically terminated' — AWS says open a new connection 'after you have delivered a fixed number of messages via a single SMTP connection' (threshold: experiment). Non-Send API calls (GetAccount etc.) serialise at 1 rps; 20 concurrent import jobs / 20 export jobs. _(src: https://docs.aws.amazon.com/ses/latest/dg/troubleshoot-smtp.html, 2026-09-02)_ |
| 4 | Identity posture | Per AWS account × Region: sandbox status, quotas, verified identities and SMTP credentials are all Region-scoped. Every From/Source/Sender/Return-Path must be a verified identity. Production access = `PutAccountDetails` (mail type TRANSACTIONAL/MARKETING, website URL, ≤4 contact addresses); AWS Support 'initial response … within 24 hours'. Service Terms §15.4: AWS 'may suspend or terminate your access to SES … if … your use of SES fails to comply with the AWS Acceptable Use Policy'; §15.5 payment obligations continue if mail is blocked; §15.6 AWS is not the CAN-SPAM 'sender'. SLA (AWS User Engagement SLA, SES included): 99.9% Monthly Uptime per Region; credits 10% (<99.9), 25% (<99.0), 100% (<95.0); Error = 500/503. No one-account-per-entity clause found in the fetched terms — UNKNOWN beyond that. _(src: https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html, 2026-09-02)_ |
| 5 | Failure & resume | No idempotency key on `SendEmail` (v2 request body has no such field) — smallest resumable unit = ONE message per recipient; AWS: 'call SendEmail once for every recipient' because on failure 'the entire email is rejected'. Accepted ≠ delivered: a `MessageId` is returned even for virus-rejected or bad-template mail (Reject/RenderingFailure events). SES itself retries soft bounces 'for a certain period of time' then emits a Transient bounce. SDK retries (standard mode, opt-in `AWS_NEW_RETRIES_2026=true`): 3 attempts, base 1,000 ms throttling / 50 ms transient, full jitter, 20 s cap, 500-token retry quota; `ThrottlingException`/`TooManyRequestsException`/`LimitExceededException` classed retryable. SMTP: retry 4xx with 'progressively longer wait times (… 5 seconds … 10 seconds … 30 seconds)', then 20 min; 5xx = fix the request first. _(src: https://docs.aws.amazon.com/ses/latest/dg/manage-sending-quotas.html, 2026-09-02)_ |
| 6 | Cost model | $0.10 / 1,000 outbound emails (per recipient) + $0.12 per GB of attachment data; inbound $0.10 / 1,000; Virtual Deliverability Manager $0.07 / 1,000 (0–10M/mo); managed dedicated IP $15 / month / account + per-email fee. Free tier on the page = 'up to $200 in AWS Free Tier credits' for new customers (6 months) — no 3,000/mo SES-specific tier stated. Mailbox-simulator sends billed as outbound; sends suppressed by Auto Validation still charged; blocked/delayed mail still billable (Terms §15.5). Spike = pure usage (no overage tier). Cross-checked 2026-09-02 via Brave (3 third-party pricing pages agree on $0.10/1k). _(src: https://aws.amazon.com/ses/pricing/, 2026-09-02)_ |
| 7 | Usage observability | `GET /v2/email/account` → `SendQuota{Max24HourSend, MaxSendRate, SentLast24Hours}`, `SendingEnabled`, `ProductionAccessEnabled`, `EnforcementStatus` HEALTHY / PROBATION / SHUTDOWN (this endpoint itself 429s at 1 rps); v1 `GetSendQuota` / `GetSendStatistics` (counts only); CloudWatch metrics Send/Delivery/Bounce/Complaint/Reject/Reputation.BounceRate/ComplaintRate (appear only after first event); console Account dashboard shows daily usage %. No rate-limit headers on responses documented — UNKNOWN (tried SendEmail, GetAccount, quotas pages). Bounce/complaint RATES that trigger enforcement are computed on a 'representative volume', not a fixed window, and 'can stretch farther back in time than the SES console or GetSendStatistics can retrieve'. _(src: https://docs.aws.amazon.com/ses/latest/APIReference-V2/API_GetAccount.html, 2026-09-02)_ |
| 8 | Health signal | Public AWS Health Dashboard – Service health at https://health.aws.amazon.com/health/status ('You don't need to sign in'), filter by Service/Region/date, 12-month history; an RSS feed exists but 'the format is subject to changes … we recommend integrating with Amazon EventBridge'. The page is a JS app — both fetch arms returned no body today (exa `unknown error`, WebFetch empty); facts taken from the Health user guide. Account-level: a sending pause posts an 'SES sending paused' event to the Personal Health Dashboard; AWS Health API (global.health.amazonaws.com) requires Business+/Enterprise support — otherwise `SubscriptionRequiredException`. _(src: https://docs.aws.amazon.com/health/latest/ug/aws-health-dashboard-status.html, 2026-09-02)_ |
| 9 | Credential lifecycle | API: IAM access keys — max 2 per user, no expiry, secret 'can be retrieved only at the time you create it' → overlap rotation (create 2nd key, switch, deactivate, delete). SMTP: per-Region username = access key ID, password = HMAC-SHA256 SigV4 chain over (date '11111111', region, 'ses', 'aws4_request', 'SendRawEmail') prefixed 0x04, base64 — so rotating the IAM key rotates SMTP; temporary credentials 'not supported' for SMTP; console-created SMTP password is not viewable later ('delete your existing SMTP user' then recreate to change). SMTP users created before 2024-09-06 carry an inline policy → migrate to group `AWSSESSendingGroupDoNotRename`. Failure codes: `535 Authentication Credentials Invalid`, `530 Authentication required`, `554 Access denied … not authorized to perform ses:SendRawEmail`. _(src: https://docs.aws.amazon.com/ses/latest/dg/smtp-credentials.html, 2026-09-02)_ |
| 10 | Interface lifecycle | Two APIs live in parallel: v1 Query API version 2010-12-01 (SendEmail/SendRawEmail/SendTemplatedEmail/SendBulkTemplatedEmail; reference last published 2026-09-02, NOT marked deprecated in the fetched pages) and v2 REST API 2019-09-27 (`POST /v2/email/outbound-emails`, SendBulkEmail; 40 MB; per-Region endpoints). Quotas page steers >10 MB workloads to v2; AWS blog: v2 actions 'don't universally map exactly to the v1 API actions' — refactor required. No Deprecation/Sunset header or v1 end-date documented — UNKNOWN (tried APIReference Welcome, APIReference-V2 Welcome, send-email-api, ses/faqs). SMTP: `email-smtp.<region>.amazonaws.com`, ports 25/587/2587 STARTTLS, 465/2465 TLS Wrapper, TLS mandatory. _(src: https://docs.aws.amazon.com/ses/latest/APIReference/Welcome.html, 2026-09-02)_ |
| 11 | Data contract | v2 `SendEmail` → `{MessageId}`; errors are JSON exception names: `BadRequestException` 400, `NotFoundException` 404, `TooManyRequestsException` 429, `MessageRejected` / `MailFromDomainNotVerifiedException` / `LimitExceededException` / `SendingPausedException` / `AccountSuspendedException` 400. SMTP success `250 Ok <MessageID>`. Feedback JSON: top-level `notificationType` (or `eventType` under event publishing) Bounce / Complaint / Delivery, `mail{timestamp, messageId, source, sourceArn, sendingAccountId, destination, headers[], commonHeaders, tags}`, `bounce{bounceType Permanent\|Transient\|Undetermined, bounceSubType General\|NoEmail\|Suppressed\|OnAccountSuppressionList\|MailboxFull\|…, bouncedRecipients[{emailAddress, action, status, diagnosticCode}], feedbackId, timestamp}`, `complaint{complainedRecipients[], complaintFeedbackType abuse\|auth-failure\|fraud\|not-spam\|other\|virus, feedbackId}`. 'SES reserves the right to add additional fields' — parse leniently. _(src: https://docs.aws.amazon.com/ses/latest/dg/notification-contents.html, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | No native webhooks — bounce/complaint/delivery go via SNS topic (feedback notifications) or configuration-set event publishing (SNS / CloudWatch / Firehose; events Send, Reject, Bounce, Complaint, Delivery, Open, Click, Rendering Failure, DeliveryDelay, Subscription). SNS HTTP POST: headers `x-amz-sns-message-type` / `-message-id` / `-topic-arn` / `-subscription-arn`; body `{Type, MessageId, TopicArn, Subject, Message (SES JSON as string), Timestamp, SignatureVersion "1"\|"2", Signature, SigningCertURL, UnsubscribeURL}`; first message is `SubscriptionConfirmation` (SubscribeURL). Verify: SignatureVersion 2 = SHA256 (recommended), fetch cert only from the SNS HTTPS URL, reject unexpected `TopicArn`. At-least-once ('occasional, duplicate messages'), no ordering ('SES does not make ordering or batching guarantees'; one notification may cover several recipients) — dedup on `MessageId`/`feedbackId`. HTTP/S retry default `numRetries` 3 @ 20 s; customisable to ≤100 retries within a hard 3,600 s cap; only 5XX + 429 retried, then DLQ or discarded; default Content-Type `text/plain; charset=UTF-8`. _(src: https://docs.aws.amazon.com/sns/latest/dg/sns-message-delivery-retries.html, 2026-09-02)_ |
| — | **Resilience posture (58)** | transactional email (backup to Resend); SNS receiver = public route + SNS signature verify in handler (57 § Doc Sync); dedup on `feedbackId`; hard-fail on quota → sender-side queue + backoff owned by the consuming project (`docs/RESILIENCE.md` §2b card: timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Email delivery service (backup)
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Backup email service - Daily Limit: 200 emails
- **Notes** _(2026-06-02 entry)_: - Backup to Resend - Requires DKIM/SPF setup for deliverability
- **Research notes** _(2026-09-02, re-grounded)_: vendor status: https://health.aws.amazon.com/health/status.

### Instantly

**Type:** email · **Reach:** REST API (env key) · **Used by:** 1 project(s) — trade-intelligence · **Env keys:** `INSTANTLY_*` · **Docs:** https://instantly.ai

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | 100 req/s AND 6,000 req/min per Workspace, shared across API v1+v2 and all keys. _(src: https://developer.instantly.ai/getting-started/rate-limit.md, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 when ANY limit hit; docs advise batches of 100 with 2 s waits. _(src: https://developer.instantly.ai/getting-started/rate-limit.md, 2026-09-02)_ |
| 3 | Concurrency & parallelism | Per workspace; extra API keys add no quota. _(src: https://developer.instantly.ai/getting-started/rate-limit.md, 2026-09-02)_ |
| 4 | Identity posture | Per workspace, scoped keys; sub-workspaces via workspace group; ToS UNKNOWN — not fetched. _(src: https://developer.instantly.ai/llms.txt, 2026-09-02)_ |
| 5 | Failure & resume | 429 retry; long ops return background jobs (GET /api/v2/background-jobs/:id); cursor paging starting_after/next_starting_after. _(src: https://developer.instantly.ai/guides/api-v1-migration.md, 2026-09-02)_ |
| 6 | Cost model | API bundled in plan; webhooks require Hypergrowth ($97/mo); no per-call pricing. _(src: https://instantly.ai/blog/how-to-integrate-email-api-webhooks-for-real-time-reply-tracking/, 2026-09-02)_ |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) tried rate-limit.md/llms.txt: no usage endpoint; no rate headers documented. — suggested src: https://developer.instantly.ai/getting-started/rate-limit.md |
| 8 | Health signal | Instatus JSON summary.json -> {status:'UP'} (2026-09-02). _(src: https://instantlyai.instatus.com/summary.json, 2026-09-02)_ |
| 9 | Credential lifecycle | Bearer API v2 key with scopes; expiry UNKNOWN — tried authorization.md. _(src: https://developer.instantly.ai/getting-started/authorization.md, 2026-09-02)_ |
| 10 | Interface lifecycle | /api/v2; v1 deprecated 2026-01-19 (existing integrations keep working); no Deprecation/Sunset headers documented. _(src: https://developer.instantly.ai/guides/api-v1-migration.md, 2026-09-02)_ |
| 11 | Data contract | OpenAPI at https://api.instantly.ai/openapi/api_v2.json; webhook payload may carry extra lead-data keys (validate loosely). _(src: https://developer.instantly.ai/guides/webhook-events.md, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | Webhooks: retry 'up to three times within 30 seconds' (official blog); no HMAC — custom headers/Bearer; delivery log GET /api/v2/webhook-events (retry_count, will_retry) seen via search snippet only. _(src: https://instantly.ai/blog/how-to-integrate-email-api-webhooks-for-real-time-reply-tracking/, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Tiny retry window (30 s) means the reconciliation poll on /webhook-events is mandatory.

### Myemailverifier

**Type:** email · **Reach:** REST API (env key) · **Used by:** 1 project(s) — trade-intelligence · **Env keys:** `MYEMAILVERIFIER_*` · **Docs:** https://myemailverifier.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) https://myemailverifier.com/apidocs, searched 'limits quota rate limit' |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) https://myemailverifier.com/apidocs, searched 'overage block' |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) https://myemailverifier.com/apidocs, searched 'concurrency parallel' |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) https://myemailverifier.com/apidocs, searched 'terms of service multiple accounts' |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) https://myemailverifier.com/apidocs, searched 'retry idempotency' |
| 6 | Cost model | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) https://myemailverifier.com/apidocs, searched 'pricing unit minimum' |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) https://myemailverifier.com/apidocs, searched 'usage consumption remaining' |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'myemailverifier status page' |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) https://myemailverifier.com/apidocs, searched 'key expiry rotation' |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) https://myemailverifier.com/apidocs, searched 'versioning deprecation' |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) https://myemailverifier.com/apidocs, searched 'schema pagination deletion' |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) https://myemailverifier.com/apidocs, searched 'webhook retry ordering' |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Documentation site accessible but detailed API specifications not found via search.

### Telegram

**Type:** comms · **Reach:** REST API (env key) · **Used by:** 4 project(s) — fabrik, llm_batch_processor, spec:calendar-orchestration-engine, youtube · **Env keys:** `TELEGRAM_BOT_*`, `TELEGRAM_FULL_BOT_*` · **Docs:** https://core.telegram.org/bots

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | FAQ: ≤1 message/second per chat (short bursts tolerated), ≤20 messages/minute per group, ~30 messages/second bulk unless Paid Broadcasts (up to 1000/s at 0.1 Stars/msg above free tier); uploads ≤50 MB, getFile downloads ≤20 MB (local Bot API server raises these); setWebhook max_connections 1–100 default 40; unfetched updates kept ≤24h; Bot API 10.3 (Aug 24 2026). _(src: https://core.telegram.org/bots/faq, 2026-09-02)_ |
| 2 | Behaviour AT the cap | HTTP 429 with ok:false, error_code and parameters.retry_after = 'the number of seconds left to wait before the request can be repeated' (ResponseParameters). Ignoring limits escalates waits; hitting them does not ban, ignoring them does. _(src: https://core.telegram.org/bots/api, 2026-09-02)_ |
| 3 | Concurrency & parallelism | Webhook: max_connections 1–100 (default 40) simultaneous HTTPS connections to your endpoint; per-chat send rate is the binding cap (scoped per bot per chat/group). _(src: https://core.telegram.org/bots/api, 2026-09-02)_ |
| 4 | Identity posture | Limits per bot token (and per chat). Bot Developer ToS (telegram.org/tos/bot-developers) fetched: no clause on number of bots/accounts in §1–4; BotFather's per-user bot cap is widely reported as 20 (third-party) — UNKNOWN from official pages (tried bots/features, bots/api, ToS). _(src: https://telegram.org/tos/bot-developers, 2026-09-02)_ |
| 5 | Failure & resume | Retry after retry_after; getUpdates resumes by offset (= highest update_id + 1; update_ids increase sequentially); webhook: 'In case of an unsuccessful request (a request with response HTTP status code different from 2XY), we will repeat the request and give up after a reasonable amount of attempts'. No idempotency key — deduplicate on update_id. File links valid ≥1 hour. _(src: https://core.telegram.org/bots/api, 2026-09-02)_ |
| 6 | Cost model | Free; Paid Broadcasts cost 0.1 Stars per message above the free ~30/s tier (opt-in, requires balance/eligibility). _(src: https://core.telegram.org/bots/faq, 2026-09-02)_ |
| 7 | Usage observability | getWebhookInfo → pending_update_count, last_error_date, last_error_message (backlog/health only); no rate-quota endpoint — UNKNOWN (tried api page + FAQ). _(src: https://core.telegram.org/bots/api, 2026-09-02)_ |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no official status page linked from core.telegram.org/bots/api, /bots/webhooks or FAQ; only in-band signals (5xx, retry_after 5s on server restart). Treat 5xx bursts as 'possibly them'. — suggested src: https://core.telegram.org/bots/webhooks |
| 9 | Credential lifecycle | Bot tokens do not expire; regenerate via BotFather /token ('If your existing token is compromised or you lost it ... use the /token command to generate a new one') — single-phase, old token invalidated; no overlap (run two bots for a blue/green cut). Invalid token → 401 ok:false 'Unauthorized'. Webhook secret_token (1–256 chars) sent as X-Telegram-Bot-Api-Secret-Token. _(src: https://core.telegram.org/bots/features, 2026-09-02)_ |
| 10 | Interface lifecycle | Single evolving version (Bot API N.N) at one URL; changes announced in 'Recent changes' / api-changelog with dated notices (e.g. Mini App origin hardening auto-enabled July 20 2026); no Deprecation/Sunset headers; additive changes are the norm. _(src: https://core.telegram.org/bots/api, 2026-09-02)_ |
| 11 | Data contract | JSON {ok, result / description + error_code + parameters}; 'error_code ... contents are subject to change'; ids may exceed 32 bits (use int64); Update object gains new optional fields without notice; getUpdates returns Update[] (max 100). _(src: https://core.telegram.org/bots/api, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | Webhook: at-least-once with server-side retries until 2XY or 'a reasonable amount of attempts'; 24h retention of undelivered updates; update_id sequential for dedup/ordering; auth = shared secret header (no HMAC/timestamp); must be HTTPS on 443/80/88/8443 from 149.154.160.0/20 + 91.108.4.0/22; replay = switch to getUpdates with offset (deleteWebhook drop_pending_updates optional); no list-of-sent endpoint. _(src: https://core.telegram.org/bots/api, 2026-09-02)_ |
| — | **Resilience posture (58)** | alert sink via Apprise + Alertmanager; deadman/Tier-C escalation target (60-watchdog) |

- **Purpose** _(2026-06-02 entry)_: Notification service
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://api.telegram.org/bot<token>/` - Send Message: `POST /sendMessage` - Send Photo: `POST /sendPhoto` - Get Updates: `GET /getUpdates`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: System notifications, alerts
- **Notes** _(2026-06-02 entry)_: - Placeholder (not configured yet)
- **Research notes** _(2026-09-02)_: ResponseParameters.retry_after wording: core.telegram.org/bots/api is too large for WebFetch (model reports truncation) and exa's default window; the field text was confirmed from the aiogram docs which cite core.telegram.org/bots/api#responseparameters verbatim (https://docs.aiogram.dev/en/latest/api/types/response_parameters.html) — mapping is INFERENCE from a mirror, not an in-session verbatim

### Apprise

**Type:** comms · **Reach:** self-hosted container on the `fabrik` network · REST API (env key) · **Runs on:** vps1 (`docker ps` 2026-09-02) · **Used by:** 0 project(s) — fleet service, no per-project key · **Docs:** https://github.com/caronc/apprise

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-hosted — capacity = APPRISE_WORKER_COUNT default (2*CPUs)+1, APPRISE_WORKER_TIMEOUT 300 s, APPRISE_ATTACH_SIZE 200 MB (max 500). _(src: https://raw.githubusercontent.com/caronc/apprise-api/master/README.md, 2026-09-02)_ |
| 2 | Behaviour AT the cap | self-hosted — no rate limiter documented; saturation = worker timeouts; delivery failure -> 424 Failed Dependency. _(src: https://raw.githubusercontent.com/caronc/apprise-api/master/README.md, 2026-09-02)_ |
| 3 | Concurrency & parallelism | Worker count = concurrency; scale containers. _(src: https://raw.githubusercontent.com/caronc/apprise-api/master/README.md, 2026-09-02)_ |
| 4 | Identity posture | n/a self-hosted (apprise BSD-2, apprise-api MIT). _(src: https://github.com/caronc/apprise-api, 2026-09-02)_ |
| 5 | Failure & resume | 400 malformed, 424 delivery failed, 500 permissions; stateless POST, non-idempotent (re-POST re-sends); no persistent queue documented. _(src: https://raw.githubusercontent.com/caronc/apprise-api/master/README.md, 2026-09-02)_ |
| 6 | Cost model | Free OSS; cost = your host. _(src: https://github.com/caronc/apprise, 2026-09-02)_ |
| 7 | Usage observability | n/a self-hosted — no usage counters. _(src: https://raw.githubusercontent.com/caronc/apprise-api/master/README.md, 2026-09-02)_ |
| 8 | Health signal | GET /status -> 200 'OK' or 417 on issue; JSON form reports persistent store, config and attach writeability. _(src: https://raw.githubusercontent.com/caronc/apprise-api/master/README.md, 2026-09-02)_ |
| 9 | Credential lifecycle | self-hosted — {KEY} config store, APPRISE_CONFIG_LOCK; downstream tokens live inside Apprise URLs, lifecycle per downstream service. _(src: https://raw.githubusercontent.com/caronc/apprise-api/master/README.md, 2026-09-02)_ |
| 10 | Interface lifecycle | Docker tags latest/edge; GitHub releases; no deprecation headers. _(src: https://raw.githubusercontent.com/caronc/apprise-api/master/README.md, 2026-09-02)_ |
| 11 | Data contract | Endpoints /notify/{KEY}, /json/urls/{KEY}, /add, /del, /get; contract = Apprise URL syntax, 150+ services. _(src: https://raw.githubusercontent.com/caronc/apprise-api/master/README.md, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — it IS the relay; downstream delivery fire-and-forget (424 on failure, no retry documented). _(src: https://raw.githubusercontent.com/caronc/apprise-api/master/README.md, 2026-09-02)_ |
| — | **Resilience posture (58)** | self-hosted `:8000`; timeout 10s; fire-and-forget — log a warning, never block (58:431) |

- **Purpose** _(2026-06-02 entry)_: Notification service
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Multi-channel notifications - Domain: `https://notify.vps1.ocoron.com` - Port: 8000 (internal; Traefik-routed over the fabrik network — no host port published)
- **Notes** _(2026-06-02 entry)_: - Self-hosted on VPS - Used by n8n workflows
- **Research notes** _(2026-09-02)_: Upstream 17,153 stars; official docs moved to appriseit.com.

### Evolution API (WhatsApp)

**Type:** comms · **Reach:** REST API (env key) · **Used by:** 3 project(s) — spec:evolution-api, spec:whatsapp-agent, whatsapp-agent · **Env keys:** `EVOLUTION_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### Google APIs — Gmail + OAuth

**Type:** email / auth · **Reach:** REST API (OAuth 2.0; SDK) · **Used by:** 6 project(s) — email-reader, fabrik-lib, site-provisioner, tojlo-mail, web-ecommerce-factory, youtube (code call sites) · **Hosts:** `gmail.googleapis.com`, `oauth2.googleapis.com`, `openidconnect.googleapis.com`, `www.googleapis.com` · **Env keys:** `GOOGLE_CLIENT_*` (tojlo-mail — the OAuth client shared with `### Google OAuth (Sign-in)`); the Gmail/oauth2 hosts themselves carry no key · **Docs:** https://developers.google.com/workspace/gmail/api/reference/quota

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Quota units per method: 1,200,000 units/min per project; 6,000 units/min per user per project; daily billing threshold 80,000,000 units/day per project ('cannot request an increase'). Per-method: messages.send 100, drafts.send 100, watch 100, messages.get 20, messages.list 5, messages.insert 25, messages.modify 5, history.list 2, threads.get 40, getProfile 1, batchModify/batchDelete 50, stop 50. Also 'a limit of 500 recipients per email message'. Mailbox send caps (per user, shared by API+web+SMTP): Workspace 2,000 msgs/day (trial 500), 3,000 external recipients/day, 10,000 total recipients/day, 2,000 recipients/msg (max 500 external); consumer Gmail 500 msgs/day. Batch: ≤100 calls per batch, '>50 not recommended', n batched calls count as n. _(src: https://developers.google.com/workspace/gmail/api/reference/quota + https://knowledge.workspace.google.com/admin/gmail/gmail-sending-limits-in-google-workspace + https://support.google.com/mail/answer/22839 + https://developers.google.com/workspace/gmail/api/guides/batch, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 403 usageLimits/rateLimitExceeded ('Rate Limit Exceeded' — request quota increase or exponential backoff), 403 userRateLimitExceeded, 403 dailyLimitExceeded ('raise the quota'); 429 'Too many requests: User-rate limit exceeded (Mail sending)' 'with a time to retry' — daily send limit breaches 'might result in these errors for multiple hours'; sending pipeline lags: 'there can be a delay of several minutes before the API begins returning 429' and 'You can't assume that a 200 response means the email was successfully sent'; 'Per-user limits cannot be increased for any reason'. Mailbox cap: 'users can't send new messages for up to 24 hours'. Backoff recipe: wait min((2^n)+random_ms≤1000, maximum_backoff) with maximum_backoff 'typically 32 or 64 seconds', start ≥1 s. No Retry-After/X-RateLimit headers documented (tried system-parameters page). _(src: https://developers.google.com/workspace/gmail/api/guides/handle-errors + https://developers.google.com/workspace/gmail/api/reference/quota, 2026-09-02)_ |
| 3 | Concurrency & parallelism | 'The Gmail API enforces a per-user concurrent request limit (in addition to the per-user rate limit)', shared by ALL clients of that user (no number published — UNKNOWN, tried handle-errors + quota pages); 'many parallel requests for a single user or sending batches with a large number of requests' → 429 'Too many concurrent requests for user'. Scale-out is sanctioned by 'splitting processing across multiple Gmail accounts'. Push: 'maximum notification rate of one event per second' per watched user, excess 'dropped'. _(src: https://developers.google.com/workspace/gmail/api/guides/handle-errors + https://developers.google.com/workspace/gmail/api/guides/push, 2026-09-02)_ |
| 4 | Identity posture | Quota is per Google Cloud PROJECT + per end-user; 'API calls by a service account are considered to be using a single account'. ToS §2.d: Google limits requests/users 'in our sole discretion' and 'You agree to, and will not attempt to circumvent, such limitations'; beyond-limit use needs 'Google's express consent'. Consent screen: Testing status 'limited to up to 100 test users' and test-user authorizations 'expire seven days from the time of consent'; In production = any Google Account but verification required for sensitive/restricted scopes; Internal user type = your Workspace org only. gmail.send is SENSITIVE (verification, no assessment); mail.google.com/, gmail.readonly, gmail.modify, gmail.compose, gmail.insert, gmail.metadata, gmail.settings.* are RESTRICTED → CASA security assessment 'at least every 12 months' if data touches your server; brand verification '2-3 business days'; restricted verification 'several weeks'. _(src: https://developers.google.com/terms + https://support.google.com/cloud/answer/15549945 + https://developers.google.com/workspace/gmail/api/auth/scopes + https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification, 2026-09-02)_ |
| 5 | Failure & resume | No idempotency key on messages.send (none documented — tried send + errors pages); a send may 200 yet fail downstream (see row 2). Read side: history.list with startHistoryId gives incremental changes; 'History records are typically available for at least one week and often longer'; stale id → 'HTTP 404' → 'your client must perform a full sync'. Watch renewal: 'call the watch at least once every 7 days', 'We recommend calling watch once per day'; response carries expiration ms. Uploads: resumable sessions resume via empty PUT + Content-Range, server answers 308 with Range. Retry 5xx with exponential backoff. Smallest resumable unit = one message (or one historyId checkpoint). _(src: https://developers.google.com/workspace/gmail/api/guides/sync + https://developers.google.com/workspace/gmail/api/guides/push + https://developers.google.com/workspace/gmail/api/guides/uploads + https://developers.google.com/workspace/gmail/api/guides/handle-errors, 2026-09-02)_ |
| 6 | Cost model | 'All standard use of the Gmail API is available at no additional cost'; 'Exceeding the quota request limits is planned to incur charges to your Google Cloud billing account later in 2026' (80M units/day threshold; 'at least 90 days' notice'; quota-increase requests will then require billing enabled). Tiering model effective May 1 2026 for NEW projects; projects active Nov 2025–Apr 2026 keep old quotas ≥60 days. Push uses Pub/Sub: first 10 GiB/month throughput free then $40/TiB; '1 KB is assessed for each request' minimum; storage $0.27/GiB-month. _(src: https://developers.google.com/workspace/gmail/api/reference/quota + https://developers.google.com/workspace/tools-safety + https://cloud.google.com/pubsub/pricing, 2026-09-02)_ |
| 7 | Usage observability | No rate-limit headers on responses (none documented — tried handle-errors, quota, system-parameters). Console: IAM & Admin > Quotas & System Limits (per-minute = 'average per minute usage in the past 10 minutes'; per-day = 'total usage so far in the current day, according to Pacific Standard Time'); programmatic: 'Cloud Quotas API to get current quota information'; Cloud Monitoring metrics serviceruntime.googleapis.com/quota/allocation/usage, quota/rate/net_usage, quota/limit, quota/exceeded with alerting policies on threshold. Per-user accounting via `quotaUser` system parameter ('pseudo user identifier for charging per-user quotas'). Mailbox send-quota remaining: not exposed (UNKNOWN — tried quota, handle-errors, sending-limits pages). _(src: https://docs.cloud.google.com/docs/quotas/view-manage + https://docs.cloud.google.com/monitoring/alerts/using-quota-metrics + https://docs.cloud.google.com/apis/docs/system-parameters, 2026-09-02)_ |
| 8 | Health signal | Google Workspace Status Dashboard lists Gmail (green today); machine feeds: 'RSS Feed' + 'JSON History' at https://www.google.com/appsstatus/dashboard/incidents.json — array of incidents {id, number, begin, created, end, modified, external_desc, updates, most_recent_update, status_impact, severity, service_key, service_name, affected_products, uri}; 13 entries today, latest Gmail incident begin 2026-05-06. Not Statuspage-shaped (no /api/v2/status.json). Pub/Sub side: https://status.cloud.google.com/incidents.json (same shape + currently_affected_locations; Cloud Pub/Sub incident begin 2026-08-20). _(src: https://www.google.com/appsstatus/dashboard/ + https://www.google.com/appsstatus/dashboard/incidents.json + https://status.cloud.google.com/incidents.json, 2026-09-02)_ |
| 9 | Credential lifecycle | OAuth2: access token short-lived (example `expires_in: 3920` s); refresh_token only returned with access_type=offline and 'only returned on the first authorization'; refresh token dies when: user revokes, 'not been used for six months', 'user changed passwords and the refresh token contains Gmail scopes', >100 live refresh tokens per Google Account per client ID, time-based access expired, admin Restricted the service, GCP session-control (invalid_grant), or Testing-status external app → 'refresh token expiring in 7 days'. Revoke: https://oauth2.googleapis.com/revoke. Token sizes: auth code 256 B, access 2048 B, refresh 512 B. OAuth CLIENTS 'inactive for six months are automatically deleted' (no token exchange AND no config edit; email 30 days before; restorable ~30 days; then `deleted_client`). 401 authError 'Invalid Credentials' → refresh, else re-consent. _(src: https://developers.google.com/identity/protocols/oauth2 + https://developers.google.com/identity/protocols/oauth2/web-server + https://support.google.com/cloud/answer/15549257 + https://developers.google.com/workspace/gmail/api/guides/handle-errors, 2026-09-02)_ |
| 10 | Interface lifecycle | Versioned path `gmail/v1` (https://gmail.googleapis.com/gmail/v1/…); release notes show no Gmail v1 sunset (latest entries 2026-06-24 Postmaster v2, 2026-05-01 quota tiering, 2026-04-22 Gmail MCP preview). Google APIs ToS §8.a: Google may 'discontinue the APIs or any portion or feature … for any reason and at any time without liability' — no 1-year clause in the APIs ToS; Workspace customer terms §1.4(e) promise 'at least 12 months' notice before discontinuing a Service or 'materially backwards-incompatible changes to a Google API' (law/security/hardship excepted). No Deprecation/Sunset headers documented — UNKNOWN (tried send, errors, quota pages). _(src: https://developers.google.com/workspace/gmail/api/release-notes + https://developers.google.com/terms + https://workspace.google.com/terms/premier_terms/, 2026-09-02)_ |
| 11 | Data contract | Errors: `{error:{code, message, errors:[{domain, reason, message, location?, locationType?}]}}` — route on `errors[].reason` (rateLimitExceeded, userRateLimitExceeded, dailyLimitExceeded, authError, domainPolicy, badRequest, backendError). Message: {id (immutable), threadId, labelIds[], snippet, historyId, internalDate (epoch ms), payload, sizeEstimate, raw (RFC 2822 base64url, format=RAW), classificationLabelValues[]}. send: POST /upload/gmail/v1/users/{userId}/messages/send (media) or /gmail/v1/… (metadata), `userId=me`, body message/rfc822; scopes mail.google.com / gmail.modify / gmail.compose / gmail.send. watch: {topicName, labelIds[], labelFilterBehavior} → {historyId, expiration}. Max message size: UNKNOWN in API docs (tried users.messages, send, uploads pages); consumer mailbox attachment cap 25 MB. _(src: https://developers.google.com/workspace/gmail/api/guides/handle-errors + https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages + https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send + https://support.google.com/mail/answer/6584, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | Via Cloud Pub/Sub only: grant `publish` to gmail-api-push@system.gserviceaccount.com on your topic, then users.watch (100 units) → immediate first notification; payload PubsubMessage {message:{data (Base64URL JSON `{"emailAddress","historyId"}`), messageId, publishTime}, subscription}; push (HTTP POST, 200 = ack) or pull (explicit ack). Pub/Sub 'offers at-least-once delivery with no ordering guarantees' → dedup + order via history.list from last historyId, never from the notification; unacked → 'Cloud Pub/Sub retries the notification at a later time'; ≤1 event/s per user, excess 'dropped'; 'notifications might be delayed or dropped' → 'fall back to periodically calling history.list'; watch expires ≤7 days (renew daily); stop() ends within minutes. No signature on the payload beyond Pub/Sub transport (none documented — tried push page). _(src: https://developers.google.com/workspace/gmail/api/guides/push + https://docs.cloud.google.com/pubsub/docs/subscription-overview, 2026-09-02)_ |
| — | **Resilience posture (58)** | user-mailbox email (send/read) + OAuth; per-user 6,000 units/min + concurrent cap → per-account serial worker, never fan-out on one mailbox; 429/403 rateLimit → truncated exponential backoff (32–64 s ceiling), 429 Mail-sending → pause that account for hours; refresh-token loss (7-day Testing, 6-month idle, password change) → re-consent path is a first-class flow; daily watch renewal cron + history.list fallback; Pub/Sub receiver = public route + at-least-once dedup on historyId (57 § Doc Sync) |

- **Research notes** _(2026-09-02)_: vendor status: https://www.google.com/appsstatus/dashboard/ (JSON: https://www.google.com/appsstatus/dashboard/incidents.json). YouTube Data API is its own block (§ Research); Gemini (`generativelanguage.googleapis.com`) is its own block (§ AI — LLM); `### Google OAuth (Sign-in)` above carries the sign-in posture — row 9 here is the token lifecycle both share.

### Slack — Incoming Webhooks + Web API

**Type:** messaging · **Reach:** webhook URL (secret in env) + REST API · **Used by:** 1 project(s) — tojlo-mail (code call sites) · **Hosts:** `slack.com` · **Env keys:** none in the fleet today (reached without a key; the posture row names the knob a consumer would add) · **Docs:** https://docs.slack.dev (every `api.slack.com/...` path 302s here; Web API base `https://slack.com/api/METHOD`, webhooks `https://hooks.slack.com/services/T…/B…/…`)

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Web API tiers, applied 'per API method per workspace/team per app', windows per minute: Tier 1 '1+ per minute', Tier 2 '20+', Tier 3 '50+', Tier 4 '100+', Special 'varies' (all plans get the same tier). Posting messages (chat.postMessage OR incoming webhook): '1 per second' per channel, 'Short bursts >1 allowed', plus a workspace-wide cap of 'several hundred messages per minute'. Incoming webhooks: '1 per second'. Events API: 30,000 deliveries per workspace per app per 60 min. conversations.history/replies for commercially-distributed NON-Marketplace apps created after 2025-05-29: Tier 3→Tier 1 = 1 request/min, `limit` max 15 objects (internal customer-built apps keep 50+/min, 1,000 objects; existing installs hit it 2026-03-03 per the FAQ post — that date is from a search snippet only, the FAQ page fetch returned the docs landing page). Pagination: `limit` 100–200 recommended, max 1000; unpaginated calls get 'stricter rate limits'. Message `text` ≤4,000 chars recommended, truncated >40,000. Burst limits are not published — 'design your apps with a limit of 1 request per second for any given API call'. _(src: https://docs.slack.dev/apis/web-api/rate-limits + https://docs.slack.dev/changelog/2025/05/29/rate-limit-changes-for-non-marketplace-apps/ + https://docs.slack.dev/reference/methods/chat.postMessage, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 'HTTP 429 Too Many Requests' + `Retry-After` header 'containing the number of seconds until you can retry' (doc example `Retry-After: 30`) on every HTTP API 'including incoming webhooks'; JSON body `{"ok":false,"error":"ratelimited"}` (chat.* also lists `rate_limited`). Scope of a 429 = that method for that workspace only — 'Calls to other methods on behalf of this workspace are not restricted. Calls to the same method for other workspaces ... are also not restricted.' Message bursts over 1/s: 'no guarantee that messages will be stored or displayed'; users see an in-channel error; sustained overrun on RTM → disconnect, and 'runs the risk of your app being permanently disabled'. Events over 30,000/h → `app_rate_limited` events every minute, deliveries dropped. _(src: https://docs.slack.dev/apis/web-api/rate-limits + https://docs.slack.dev/reference/methods/auth.test, 2026-09-02)_ |
| 3 | Concurrency & parallelism | No in-flight/connection cap documented; 'a burst limit defines the maximum rate of requests allowed concurrently' and 'Slack does not share precise burst limits externally' — the published design target is 1 rps per API call with temporary bursts tolerated. Limits are keyed per method × workspace × app, so parallelism across workspaces/methods is independent. Special: `users.profile.set` ≤10 updates/min per user, ≤30 profiles/min per token. Token rotation: '2 active token limit' — refreshing repeatedly within 12h revokes the oldest extra token. _(src: https://docs.slack.dev/apis/web-api/rate-limits + https://docs.slack.dev/authentication/using-token-rotation, 2026-09-02)_ |
| 4 | Identity posture | Per Slack app × installing workspace (tokens are per installation; webhook URL 'specific to a single user and a single channel'). Slack API ToS (Effective: October 10, 2025): you will not 'attempt to use our APIs in a manner that exceeds rate limits, or constitutes excessive or abusive usage'; 'You may not Commercially Distribute an Application ... unless you are authorized ... under a separate agreement' (Marketplace Agreement or partner agreement; exempt when built 'for use only by a single third party'); no LLM training on API Data; no bulk export except via Discovery API agreements. Slack App Developer Policy (effective December 10, 2024) bans 'Circumventing Slack's intended limitations (including pricing, features and access structures)'. No one-account/one-app-per-entity clause in either fetched text — UNKNOWN beyond that. _(src: https://slack.com/terms-of-service/api + https://docs.slack.dev/developer-policy/, 2026-09-02)_ |
| 5 | Failure & resume | No idempotency key on the Web API or webhooks — UNKNOWN (tried web-api overview, chat.postMessage, webhooks, rate-limits pages; chat.postMessage is non-idempotent: each retry posts a new message). Resume by keeping the returned `ts` (chat.postMessage → `{ok, channel, ts, message}`) and `chat.update`-ing instead of re-posting; webhooks return NO `ts` and cannot delete. Webhook failures are HTTP-coded: 200 body `ok`; 400 `invalid_payload`/`user_not_found`; 403 `action_prohibited`; 404 `channel_not_found`; 410 `channel_is_archived`; 500 `rollup_error`; plus `no_service`, `no_active_hooks`, `invalid_token`, `no_text`. Web API `fatal_error`/`internal_error`: 'It's possible some aspect of the operation succeeded before the error was raised' — verify before retrying. Lists: cursor pagination via `response_metadata.next_cursor`, done when it is `""` (do not infer from result size). Smallest resumable unit = one message / one page. _(src: https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks + https://docs.slack.dev/changelog/2016-05-17-changes-to-errors-for-incoming-webhooks + https://docs.slack.dev/apis/web-api/pagination, 2026-09-02)_ |
| 6 | Cost model | API access itself is unmetered/free; cost is the workspace plan per user/month: Free '$0USD free forever' (90 days message history, 'Up to 10 apps'); Pro $8.75 monthly / $7.25 annual; Business+ $18 monthly / $15 annual; Enterprise+ 'Contact sales'. No per-call or overage API charges listed. Spike = none in $ (rate-limited, not billed). _(src: https://slack.com/pricing, 2026-09-02; cross-checked https://www.usecarly.com/blog/slack-pricing/)_ |
| 7 | Usage observability | None pull-able: no usage/quota endpoint and no `X-RateLimit-*` remaining/limit headers documented — only the reactive `429` + `Retry-After` on the Web API/webhooks and the pushed `app_rate_limited` event (`minute_rate_limited`, `team_id`, `api_app_id`) for Events API overrun. `Retry-After` semantics: wait N seconds before retrying that method for that workspace. UNKNOWN beyond that — tried rate-limits, web-api overview, auth.test, chat.postMessage pages. _(src: https://docs.slack.dev/apis/web-api/rate-limits, 2026-09-02)_ |
| 8 | Health signal | Unauthenticated Slack Status API: `GET https://slack-status.com/api/v2.0.0/current` → `{status: "ok"\|"active", date_created, date_updated, active_incidents[{id,title,type(incident\|notice\|outage),status,url,services[],notes[]}]}`; `/history` for past incidents; filter on `services` ('Messaging', 'Apps/Integrations/APIs', ...); vendor says poll at most 'once a minute'. TODAY it returned `"status":"active"` with 1 active incident (id 1576, 'Trouble Accessing Historical Messages With Custom Data Retention Policies Enabled', open since 2026-08-13, services Messaging + Workspace/Org Administration). _(src: https://slack-status.com/api/v2.0.0/current + https://docs.slack.dev/reference/slack-status-api, 2026-09-02)_ |
| 9 | Credential lifecycle | Bot `xoxb-`/user `xoxp-` tokens: 'Without token rotation, the access token never expires'. Rotation is opt-in per app and 'may not be turned off once it's turned on': `oauth.v2.exchange` → `xoxe.xoxb-`/`xoxe.xoxp-` access token with `expires_in` always 43,200 s (12 h) + `xoxe-1-` refresh token; refresh via `oauth.v2.access` `grant_type=refresh_token`; refresh tokens are single-use, 'revoked after a short grace period'; old access token stays valid until expiry (no hard cut-over). Errors: `token_expired`, `token_revoked`, `invalid_auth`, `not_authed`, `account_inactive`. Revoke: `auth.revoke` (single token), `apps.uninstall` (all tokens); `tokens_revoked` event (`tokens.oauth[]`/`tokens.bot[]` user ids). Signing secret 'Regenerate': 'the previous secret remains valid for 24 hours unless revoked manually'. Webhook URLs contain the secret; 'Slack actively searches out and revokes leaked secrets'. _(src: https://docs.slack.dev/authentication/using-token-rotation + https://docs.slack.dev/reference/methods/auth.test + https://docs.slack.dev/authentication/verifying-requests-from-slack, 2026-09-02)_ |
| 10 | Interface lifecycle | Unversioned (`https://slack.com/api/METHOD_FAMILY.method`, no version segment; Status API is the only versioned surface, `v2.0.0`). No Deprecation/Sunset headers — retirement surfaces as errors `method_deprecated` / `deprecated_endpoint`. Changes announced on the changelog (RSS https://docs.slack.dev/changelog/rss.xml, Atom `/changelog/atom.xml`) with per-change dates but no published fixed notice period — UNKNOWN (tried changelog index, deprecation posts, developer-policy). Precedents: `files.upload` blocked for new apps 2024-05-16, sunset 2025-11-12; conversations.history/replies Tier 3→1 effective same-day 2025-05-29 for new non-Marketplace apps; legacy custom bots ended 2025-03-31; classic-apps retirement (was 2026-11-16) PAUSED 2025-12-08 — 'will continue to work for the foreseeable future'. Latest entry 2026-09-01: Marketplace submissions need ≥10 active installs. _(src: https://docs.slack.dev/changelog + https://docs.slack.dev/changelog/2025/12/08/classic-apps-deprecation-paused/ + https://docs.slack.dev/changelog/2024-09-legacy-custom-bots-classic-apps-deprecation/ + https://docs.slack.dev/apis/web-api/, 2026-09-02)_ |
| 11 | Data contract | Web API: JSON envelope `{ok: bool, error?: string, warning?: string, response_metadata?: {next_cursor}}` — always check `ok`; auth via `Authorization: Bearer <token>` (never query string); POST `application/json` or `application/x-www-form-urlencoded` ('Do not mix arguments'). chat.postMessage success `{ok, channel, ts, message}`. Webhook: POST JSON `{text, blocks?, thread_ts?}` → plain-text body `ok` on 200; cannot override channel/username/icon. Event envelope: `{type:"event_callback", token(deprecated), team_id, api_app_id, event{type, event_ts, user, ts, ...}, event_context, event_id (globally unique), event_time (epoch s), authorizations[{enterprise_id, team_id, user_id, is_bot, is_enterprise_install}], is_ext_shared_channel, context_team_id, context_enterprise_id}`; inner events tolerate additive/conditional fields. _(src: https://docs.slack.dev/apis/web-api/ + https://docs.slack.dev/apis/events-api + https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | Events API (HTTP mode): ack with HTTP 2xx 'within three seconds' or the attempt fails; then 'retrying a failed request up to 3 times' — 'nearly immediately', 'after 1 minute', 'after 5 minutes' — with `x-slack-retry-num` (1/2/3) and `x-slack-retry-reason` (`http_timeout`, `too_many_redirects`, `connection_failed`, `ssl_error`, `http_error`, `unknown_error`); suppress per-event with response header `x-slack-no-retry: 1`. Follows ≤2 redirects. Failure limit: >95% failed attempts in 60 min → subscriptions 'temporarily disabled' + email to the app owner, manual re-enable in app settings (apps under 1,000 events/h are exempt). Optional 'Delayed Events' toggle adds hourly retries for 24 h; otherwise events >2 h late are not delivered ('best-effort system'). Dedup on `event_id`; at-least-once (retries + one event per installation). Ordering: not stated — UNKNOWN. Auth: `X-Slack-Signature` = `v0=` + HMAC-SHA256(signing secret, `v0:<X-Slack-Request-Timestamp>:<raw body>`), reject if timestamp differs from local time by 'more than five minutes'; the `token` field is deprecated. Cap 30,000 events/workspace/app/60 min → `app_rate_limited`. Alternative: Socket Mode (no public URL). _(src: https://docs.slack.dev/apis/events-api + https://docs.slack.dev/authentication/verifying-requests-from-slack, 2026-09-02)_ |
| — | **Resilience posture (58)** | outbound alert/notification sink; client-side 1 rps token bucket per webhook/channel + honour `Retry-After` on 429, never blind-retry `chat.postMessage` (non-idempotent — keep `ts`, `chat.update`); webhook URL = secret in env; Events receiver = public route + signing-secret HMAC + `event_id` dedup + ack-in-3s/queue in handler (57 § Doc Sync) |

- **Research notes** _(2026-09-02)_: vendor status: https://slack-status.com (JSON: https://slack-status.com/api/v2.0.0/current · RSS changelog: https://docs.slack.dev/changelog/rss.xml).

## AI — LLM gateway (and the direct keys the catalog still holds)

### OpenRouter

**Type:** ai-llm · **Reach:** REST API (env key) · **Used by:** 28 project(s) — ai-model-catalog, brand-identiy-creator, compliance-ops, exam-coach, fabrik-claim-validator, iterative_image_editor, spec:ai-model-catalog, spec:calendar-orchestration-engine … · **Env keys:** `OPENROUTER_*`, `WATCHDOG_OPENROUTER_*` · **Docs:** https://openrouter.ai · **Vendor doc:** `docs/reference/apis/openrouter-api.md`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Free (:free) models: 20 req/min; 50 req/day if <$10 lifetime credits purchased, 1,000 req/day if ≥$10 (UTC day). Paid models: no published rpm — 'we govern capacity globally' + Cloudflare DDoS protection; upstream provider limits surface as 429s. Per-key credit limit optional (limit, limit_reset daily/weekly/monthly). _(src: https://openrouter.ai/docs/api-reference/limits, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 {error:{code:429, metadata.error_type:'rate_limit_exceeded'}} with X-RateLimit-Limit/Remaining/Reset on the error and Retry-After when providers gave one; 402 when account balance ≤0 or key limit_remaining exhausted (blocks free models too); streaming: status stays 200 and errors arrive as SSE events. _(src: https://openrouter.ai/docs/api-reference/errors, 2026-09-02)_ |
| 3 | Concurrency & parallelism | No in-flight cap documented; 'Making additional accounts or API keys will not affect your rate limits, as we govern capacity globally' — scaling keys/accounts buys nothing; different models have different limits. _(src: https://openrouter.ai/docs/api-reference/limits, 2026-09-02)_ |
| 4 | Identity posture | Limits global per platform capacity, credits per account/key. ToS (Aug 31 2026) §3.1 allows organizational + individual accounts ('Authorized Users may also create separate individual accounts'); no anti-multi-account clause in fetched §1–4, and the docs state extra accounts don't raise limits. _(src: https://openrouter.ai/terms, 2026-09-02)_ |
| 5 | Failure & resume | Retry 429/503 with backoff honoring Retry-After; automatic provider fallback before first token; 408 timeout; 502 model down. No Idempotency-Key; each completion has an id → GET /api/v1/generation?id= for after-the-fact usage/cost. Streams cannot be resumed mid-way. _(src: https://openrouter.ai/docs/api-reference/errors, 2026-09-02)_ |
| 6 | Cost model | Pass-through per-million-token provider pricing (prompt/completion/reasoning/image/per-request where applicable), no inference markup; 5.5% ($0.80 min) fee on card credit purchases, 5% crypto; BYOK: $25k/mo list-price allowance free (PAYG), then 5% of list price; unused credits may expire after one year. Spike = reasoning tokens + cache-write tokens + provider price changes. _(src: https://openrouter.ai/docs/faq, 2026-09-02)_ |
| 7 | Usage observability | GET /api/v1/key → limit, limit_remaining, limit_reset, usage, usage_daily/weekly/monthly, is_free_tier; GET /api/v1/credits (management key) → total_credits, total_usage; every response includes usage{cost, prompt/completion tokens, cached_tokens, ...} (the usage.include flag is now deprecated/always on). _(src: https://openrouter.ai/docs/api-reference/limits, 2026-09-02)_ |
| 8 | Health signal | https://status.openrouter.ai/ (component board Chat, Data API, Homepage, Clerk; recent incidents) — NOT Statuspage: /api/v2/status.json → 404 (exa CRAWL_NOT_FOUND). Machine-readable feed unverified. _(src: https://status.openrouter.ai/, 2026-09-02)_ |
| 9 | Credential lifecycle | API keys don't expire by default; Management API (/api/v1/keys) can create/update/disable/delete keys with credit limits and limit_reset — overlap rotation by creating a second key; invalid/disabled key → 401 'Invalid credentials'. Management keys cannot call completions. _(src: https://openrouter.ai/docs/features/provisioning-api-keys, 2026-09-02)_ |
| 10 | Interface lifecycle | Path /api/v1, OpenAI-compatible; deprecations announced in docs (e.g. ':online' variant deprecated in favour of openrouter:web_search; usage.include deprecated); models 'may be added or removed at any time' (ToS §1); no Deprecation/Sunset headers documented — UNKNOWN (tried errors, limits, FAQ, terms). _(src: https://openrouter.ai/docs/faq, 2026-09-02)_ |
| 11 | Data contract | OpenAI chat.completion(.chunk) schema plus usage{cost, cost_details.upstream_inference_cost, prompt_tokens_details{cached_tokens,cache_write_tokens}, completion_tokens_details{reasoning_tokens}}; errors {error{code,message,metadata{provider_code,...}}, user_id}; the rate_limit object in /key is deprecated. _(src: https://openrouter.ai/docs/use-cases/usage-accounting, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — no webhooks. _(src: https://openrouter.ai/docs/api-reference/limits, 2026-09-02)_ |
| — | **Resilience posture (58)** | the ONLY sanctioned LLM route (57 § Hard constraints); provider-death handling per 58 § Provider-death (declare the mechanism in §2b — `models` array, never a pinned provider) |

- **Purpose** _(2026-06-02 entry)_: OpenAI-compatible LLM gateway — content/LLM fallback path.
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://openrouter.ai/api/v1` - Chat Completions: `POST /chat/completions`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: watchdog/fleet-healer LLM calls when not using Claude Code OAuth - Models: full ids, e.g. `anthropic/claude-sonnet-4.6`, `google/gemini-2.5-flash`
- **Research notes** _(2026-09-02)_: Free-tier numbers rendered via WebFetch (the markdown source uses {FREE_MODEL_*} placeholders — exa returned the raw placeholders). All fetched 2026-09-02.

### Anthropic

**Type:** ai-llm · **Reach:** REST API (env key) · **Used by:** 1 project(s) — brand-identiy-creator · **Env keys:** `ANTHROPIC_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Org-level usage tiers (Evaluation/Start/Build/Scale/Custom); per-model-class RPM + ITPM + OTPM, token-bucket (no fixed reset); monthly spend caps $500/$1,000/$200,000. _(src: https://docs.anthropic.com/en/api/rate-limits, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 rate_limit_error + retry-after. Tier spend-cap 429 has NO retry-after (error_code enforced_spend_limit_reached), fails until 00:00 UTC next month. Self-set limit → 400. 529 overloaded. _(src: https://docs.anthropic.com/en/api/rate-limits, 2026-09-02)_ |
| 3 | Concurrency & parallelism | No published in-flight cap; limits per org (workspace sub-limits configurable). Batch: 100,000 requests or 256 MB per batch; queued batch requests count toward limits. _(src: https://docs.anthropic.com/en/docs/build-with-claude/batch-processing, 2026-09-02)_ |
| 4 | Identity posture | Per organization. Commercial Terms D.5: customer responsible for all account activity; D.4 restrictions. No multi-org/account clause found in Commercial Terms or Usage Policy. _(src: https://www.anthropic.com/legal/commercial-terms, 2026-09-02)_ |
| 5 | Failure & resume | Retry 429/5xx/529 with backoff (SDKs retry 2x, honour retry-after). No idempotency key documented. Batch: custom_id matching, results out-of-order, expire 24h, downloadable 29 days. _(src: https://docs.anthropic.com/en/api/errors, 2026-09-02)_ |
| 6 | Cost model | Per MTok input/output by model (Fable 5.1 batch $5/$25 = 50% of standard). No free tier stated. Spikes: output/thinking tokens, cache creation, server tools. _(src: https://docs.anthropic.com/en/docs/build-with-claude/batch-processing, 2026-09-02)_ |
| 7 | Usage observability | Admin API GET /v1/organizations/usage_report/messages (1m/1h/1d buckets, group by key/model/workspace) + cost report; needs Admin key, not workspace key. Not on Claude Platform on AWS. _(src: https://docs.anthropic.com/en/api/usage-cost-api, 2026-09-02)_ |
| 8 | Health signal | Statuspage: https://status.anthropic.com/api/v2/status.json returns JSON (fetched: indicator none, 'All Systems Operational'; page URL now status.claude.com). _(src: https://status.anthropic.com/api/v2/status.json, 2026-09-02)_ |
| 9 | Credential lifecycle | Expiry chosen at creation (3h/1d/7d/30d/custom/Never; org policy may cap); immutable after; email 7d/1d before. Expired → 401 authentication_error, cannot reactivate. Multiple keys → overlap rotation; Admin API exposes expires_at/status. _(src: https://platform.claude.com/docs/en/manage-claude/authentication, 2026-09-02)_ |
| 10 | Interface lifecycle | Date header anthropic-version (2023-06-01 current); additive changes non-breaking, enum values may grow. Model retirements: email + docs, ≥60 days notice. No Deprecation/Sunset headers documented. _(src: https://docs.anthropic.com/en/docs/about-claude/model-deprecations, 2026-09-02)_ |
| 11 | Data contract | Error envelope {type:'error', error:{type,message}, request_id}; request-id header. Documented that output values/enum variants expand without version bump. Batch results keyed by custom_id. _(src: https://docs.anthropic.com/en/api/versioning, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | Messages/Batches API: n/a — pull-only. Webhooks exist only for Managed Agents: 3 attempts, jittered backoff 5–120s, same event.id (dedup), whsec_ signing secret, thin events (GET object). _(src: https://platform.claude.com/docs/en/managed-agents/webhooks, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Strong grounding; batch webhook_url claims seen on third-party sites are NOT in the official Create-Batch reference (fetched, no such param).

### Openai

**Type:** ai-llm · **Reach:** REST API (env key) · **Used by:** 1 project(s) — spec:image-broker · **Env keys:** `OPENAI_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Org + project level RPM/RPD/TPM/TPD/IPM per model, shared-limit families; tiers Free–Tier 5 ($100→$200,000/mo usage limit); separate long-context limits; batch queue by enqueued tokens; vector-store ingest 300 rpm/store. _(src: https://platform.openai.com/docs/guides/rate-limits, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 'Rate limit reached' / 'exceeded your current quota'; 503 'Slow Down' on sudden ramp (hold rate 15 min); headers x-ratelimit-limit/remaining/reset-{requests,tokens,project-tokens}. _(src: https://platform.openai.com/docs/guides/error-codes, 2026-09-02)_ |
| 3 | Concurrency & parallelism | No published in-flight cap; limits scoped to org/project (not user). WebSocket Responses connection limit 60 min. _(src: https://platform.openai.com/docs/guides/rate-limits, 2026-09-02)_ |
| 4 | Identity posture | Services Agreement §1.4: affiliates share one workspace/org ID, or sign a separate Order Form for a separate org. Terms of Use: may not 'circumvent any rate limits or restrictions'. _(src: https://openai.com/policies/business-terms, 2026-09-02)_ |
| 5 | Failure & resume | Retry 429/500/503 with backoff. No Idempotency-Key documented (X-Client-Request-Id is tracing only, ≤512 ASCII). Batch API: custom_id per line, 24h turnaround, results file; single model per file. _(src: https://platform.openai.com/docs/guides/batch, 2026-09-02)_ |
| 6 | Cost model | Per MTok per model; Batch 50% off; Free tier geo-gated. Spikes: reasoning/output tokens, images, web-search calls. Per-model price table not fetched (pricing page not opened this run). _(src: https://platform.openai.com/docs/guides/batch, 2026-09-02)_ |
| 7 | Usage observability | Admin Usage API: GET /organization/usage/{completions,embeddings,images,…} + GET /organization/costs (buckets, group_by api_key_id/model/batch, cursor next_page); runtime x-ratelimit-remaining-* headers. _(src: https://platform.openai.com/docs/api-reference/usage, 2026-09-02)_ |
| 8 | Health signal | Statuspage: https://status.openai.com/api/v2/status.json returns JSON (fetched: indicator 'minor', 'Partial System Degradation'). _(src: https://status.openai.com/api/v2/status.json, 2026-09-02)_ |
| 9 | Credential lifecycle | Project API key object has created_at/last_used_at only — no expires_at field; deleted keys → 401 'Incorrect API key'; multiple keys per project → overlap rotation; WIF short-lived tokens alternative. _(src: https://platform.openai.com/docs/api-reference/project-api-keys, 2026-09-02)_ |
| 10 | Interface lifecycle | REST version header openai-version 2020-10-01. Model retirement notice: GA ≥6 months, specialised variants ≥3 months, preview ~2 weeks; email + deprecations page. No Sunset header documented. _(src: https://platform.openai.com/docs/deprecations, 2026-09-02)_ |
| 11 | Data contract | Usage objects fully typed; cursor pagination (has_more, next_page); error JSON {error:{message,type}}. Products (Evals, Agent Builder, v1/prompts) retire with ~6-month dated schedule. _(src: https://platform.openai.com/docs/api-reference/usage, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | Webhooks (Standard Webhooks): per-project endpoints; retries up to 72h exponential backoff; headers webhook-id/webhook-timestamp/webhook-signature; dedup on webhook-id; timestamp tolerance and list-past-events endpoint NOT documented. _(src: https://developers.openai.com/api/docs/guides/webhooks, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: platform.openai.com webhooks URL 301s to developers.openai.com — update index links.

### Gemini

**Type:** ai-llm · **Reach:** REST API (env key) · **Used by:** 1 project(s) — iterative_image_editor · **Env keys:** `GEMINI_*` · **Docs:** https://ai.google.dev

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Per Google Cloud project (not per key): RPM/TPM/RPD per model+tier; RPD resets midnight Pacific; spend-rate cap per rolling 10 min ($10 Tier 1, $200 Tier 2/3); Batch: 100 concurrent, 2 GB file, 20 GB storage, enqueued-token caps. _(src: https://ai.google.dev/gemini-api/docs/rate-limits, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 RESOURCE_EXHAUSTED (any limit incl. spend); 503 UNAVAILABLE overload; 400 FAILED_PRECONDITION when free tier unavailable in region; 504 DEADLINE_EXCEEDED. Limits 'not guaranteed'. _(src: https://ai.google.dev/gemini-api/docs/troubleshooting, 2026-09-02)_ |
| 3 | Concurrency & parallelism | No in-flight cap published for sync calls; Batch API 100 concurrent batch requests; Priority tier 0.3x rate limits. _(src: https://ai.google.dev/gemini-api/docs/rate-limits, 2026-09-02)_ |
| 4 | Identity posture | Per project. Google APIs ToS §2d: 'will not attempt to circumvent' limits; §2c: no masking identity/API client identity. No explicit account-count clause in APIs ToS or Gemini Additional Terms. _(src: https://developers.google.com/terms, 2026-09-02)_ |
| 5 | Failure & resume | Retry 429/408/5xx with exponential backoff + jitter (Python SDK: 4 retries, 1–60s); never retry 400/403. No idempotency key. Batch = file-based async jobs. _(src: https://ai.google.dev/gemini-api/docs/troubleshooting, 2026-09-02)_ |
| 6 | Cost model | Per MTok per model (gemini-3.6-flash $1.50 in / $7.50 out; batch/flex $0.75/$3.75; priority $2.70/$13.50); free tier tokens free but data used to improve products; grounding $14/1k queries after 5k/mo. _(src: https://ai.google.dev/gemini-api/docs/pricing, 2026-09-02)_ |
| 7 | Usage observability | AI Studio 'View your active rate limits' dashboard + developer logs; no usage REST endpoint on fetched rate-limit/api-key pages → programmatic usage read UNKNOWN. _(src: https://ai.google.dev/gemini-api/docs/rate-limits, 2026-09-02)_ |
| 8 | Health signal | aistudio.google.com/status (incident list, no feed found) + Google Cloud https://status.cloud.google.com/incidents.json (fetched JSON; Gemini API not a named product there). _(src: https://status.cloud.google.com/incidents.json, 2026-09-02)_ |
| 9 | Credential lifecycle | Standard keys rejected from September 2026 — migrate to auth keys (service-account-bound, auto leaked-key blocking); unrestricted standard keys already rejected. Wrong key → 403 PERMISSION_DENIED. Multiple keys per project → overlap. _(src: https://ai.google.dev/gemini-api/docs/api-key, 2026-09-02)_ |
| 10 | Interface lifecycle | Path versions v1/v1beta. Deprecations announced on release notes, dates on deprecations page; GA models ~12 months (3.1-flash-lite May 2026→May 2027), previews weeks–months; no Sunset header. _(src: https://ai.google.dev/gemini-api/docs/deprecations, 2026-09-02)_ |
| 11 | Data contract | Parameters deprecated without version bump (temperature/top_p/top_k deprecated 2026-07-21); model shutdowns hard-fail. Terms effective 2026-03-23. _(src: https://ai.google.dev/gemini-api/docs/changelog, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only (no webhook page in fetched docs). _(src: https://ai.google.dev/gemini-api/docs/rate-limits, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Integral to Vertex AI; quotas can be increased via Google Cloud support.

### Groq

**Type:** ai-llm · **Reach:** REST API (env key) · **Used by:** 1 project(s) — fabrik · **Env keys:** `GROQ_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Org-level RPM/RPD/TPM/TPD/ASH/ASD per model; free: gpt-oss-120b 30 RPM/1K RPD/8K TPM/200K TPD, whisper-large-v3 20 RPM/2K RPD/7.2K ASH/28.8K ASD; cached tokens excluded; exact limits on console Limits page. _(src: https://console.groq.com/docs/rate-limits, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 + retry-after (seconds); headers x-ratelimit-limit/remaining/reset-requests (=RPD) and -tokens (=TPM); 498 flex-tier capacity; 5xx not billed. _(src: https://console.groq.com/docs/errors, 2026-09-02)_ |
| 3 | Concurrency & parallelism | No concurrency cap published; limits per organization; Batch API has no impact on standard limits (24h–7d window). _(src: https://console.groq.com/docs/batch, 2026-09-02)_ |
| 4 | Identity posture | Keys and limits bound to organization, not user. Cloud use governed by Groq Services Agreement / Acceptable Use Policy (index fetched; agreement text not opened) → multi-account clause UNKNOWN. _(src: https://console.groq.com/docs/api-keys, 2026-09-02 — 404 on the same-day re-probe, page moved; the live key console is https://console.groq.com/keys (login-gated) — re-verify at next touch)_ |
| 5 | Failure & resume | Retry 429/498/500/502/503; no idempotency key documented; Batch JSONL with custom_id, window 24h–7d, batches may expire. _(src: https://console.groq.com/docs/errors, 2026-09-02)_ |
| 6 | Cost model | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) tried groq.com/pricing (exa x2, WebFetch): renders marketing copy only. Grounded: Batch 50% off, batch does not stack with cache discount; free plan + Developer plan exist. — suggested src: https://console.groq.com/docs/batch |
| 7 | Usage observability | Response headers x-ratelimit-remaining-requests/-tokens + console Limits page; no usage API found on fetched pages. _(src: https://console.groq.com/docs/rate-limits, 2026-09-02)_ |
| 8 | Health signal | Statuspage: https://groqstatus.com/api/v2/status.json returns JSON (fetched: 'All Systems Operational'). _(src: https://groqstatus.com/api/v2/status.json, 2026-09-02)_ |
| 9 | Credential lifecycle | Keys org-bound; expiry not documented on api-keys page → UNKNOWN; invalid key → 401. _(src: https://console.groq.com/docs/api-keys, 2026-09-02 — 404 on the same-day re-probe, page moved; the live key console is https://console.groq.com/keys (login-gated) — re-verify at next touch)_ |
| 10 | Interface lifecycle | Model deprecations: email + deprecations page; observed notice 30–60 days (emailed 2026-06-17 → shutdown 07/17 and 08/16); previews 'short notice'; sometimes auto-upgrade. No Sunset header. _(src: https://console.groq.com/docs/deprecations, 2026-09-02)_ |
| 11 | Data contract | OpenAI-compatible; error {error:{message,type}}; deprecated model IDs return errors after shutdown. Silent schema changes UNKNOWN. _(src: https://console.groq.com/docs/errors, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only. _(src: https://console.groq.com/docs/batch, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Pricing is the only ungrounded numeric cell; third-party snippets ($0.15/$0.60 gpt-oss-120b) seen but not from a fetched official page.

### Mistral

**Type:** ai-llm · **Reach:** REST API (env key) · **Used by:** 2 project(s) — fabrik, youtube · **Env keys:** `MISTRAL_*` · **Docs:** https://mistral.ai

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 6 | Cost model | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Grounding impossible: session has no web search/fetch tools; cannot cite any vendor URL.

### Dashscope

**Type:** ai-llm · **Reach:** REST API (env key) · **Used by:** 5 project(s) — fabrik, iterative_image_editor, tojlo-mail, transdoc, youtube · **Env keys:** `DASHSCOPE_*` · **Docs:** https://dashscope.aliyun.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Root-account level (all RAM users, workspaces, keys aggregated): RPM + TPM per model, plus RPS=RPM/60 and TPS burst checks; free quota 1M tokens per model for 90 days (Singapore). _(src: https://www.alibabacloud.com/help/en/model-studio/rate-limit, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 'Requests rate limit exceeded' / 'Allocated quota exceeded' / 'Request rate increased too quickly'; free quota exhausted → 403 (if stop-on-exhaust); recovery typically ≤1 min. _(src: https://www.alibabacloud.com/help/en/model-studio/rate-limit, 2026-09-02)_ |
| 3 | Concurrency & parallelism | No in-flight cap published; per account. Batch test model limited to 2 parallel tasks. _(src: https://www.alibabacloud.com/help/en/model-studio/batch-interfaces-compatible-with-openai, 2026-09-02)_ |
| 4 | Identity posture | Per root account (workspaces/keys do not multiply). Membership Agreement §3: no clause on multiple accounts or limit circumvention (WebFetch reviewed) → permission UNKNOWN. _(src: https://www.alibabacloud.com/help/en/legal/latest/alibaba-cloud-international-website-membership-agreement, 2026-09-02)_ |
| 5 | Failure & resume | Retry 429 (docs show backup-model failover); OpenAI-compatible Batch (upload file → reuse file-batch id, async); idempotency key UNKNOWN. _(src: https://www.alibabacloud.com/help/en/model-studio/batch-interfaces-compatible-with-openai, 2026-09-02)_ |
| 6 | Cost model | Per MTok, tiered by input length (qwen3.7-max $2.5/$7.5, qwen3-max $1.2/$6 ≤32K → $3/$15 ≤256K); batch 50%; cache hit 10% / explicit cache creation 125% of input price. _(src: https://www.alibabacloud.com/help/en/model-studio/billing-for-model-studio, 2026-09-02)_ |
| 7 | Usage observability | Console Monitoring page only, refreshed hourly (up to 1h lag); no usage API on fetched pages. _(src: https://www.alibabacloud.com/help/en/model-studio/rate-limit, 2026-09-02)_ |
| 8 | Health signal | https://status.alibabacloud.com (JS-rendered; no JSON/RSS feed found) → machine-readable UNKNOWN. _(src: https://status.alibabacloud.com/, 2026-09-02)_ |
| 9 | Credential lifecycle | Keys: no expiry documented; Reset invalidates old key immediately (single-phase per key) but multiple keys coexist → overlap rotation; Disable reversible; IP allowlist + model scope; overdue account → 403. _(src: https://www.alibabacloud.com/help/en/model-studio/get-api-key, 2026-09-02)_ |
| 10 | Interface lifecycle | Deprecation policy (QwenCloud/Model Studio): snapshot models 30 days' notice, mainline 3 months; large wave 2026-10-10 (qwen3-max→qwen3.7-max etc.); deprecated model → 403 access_denied. _(src: https://docs.qwencloud.com/changelog/model-deprecation, 2026-09-02)_ |
| 11 | Data contract | OpenAI-compatible + DashScope native; error codes documented; thinking-mode params (enable_thinking/incremental_output) mandatory on some models. Silent changes UNKNOWN. _(src: https://www.alibabacloud.com/help/en/model-studio/error-code, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only. _(src: https://www.alibabacloud.com/help/en/model-studio/batch-interfaces-compatible-with-openai, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: alibabacloud.com model-deprecation URLs 404 (4 guesses); policy lives at docs.qwencloud.com.

### Siliconflow

**Type:** ai-llm · **Reach:** REST API (env key) · **Used by:** 3 project(s) — fabrik, iterative_image_editor, transdoc · **Env keys:** `SILICONFLOW_*` · **Docs:** https://siliconflow.cn

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Account-level (not key), per model: chat RPM 1,000–10,000 / TPM 50K–5M; embeddings RPM 2K–10K; rerank 2K RPM; images IPM/IPD; tiers L0–L5 by monthly spend (¥50…¥10,000). _(src: https://docs.siliconflow.cn/en/userguide/rate-limits/rate-limit-and-upgradation, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 'Request was rejected due to rate limiting' (message names RPM/TPM/IPM…); 503/504 overload → retry or stream; 403 = real-name verification/permissions. _(src: https://docs.siliconflow.cn/en/faqs/error-code, 2026-09-02)_ |
| 3 | Concurrency & parallelism | No in-flight cap published; limits per account per model (one model's limit does not affect others). _(src: https://docs.siliconflow.cn/en/userguide/rate-limits/rate-limit-and-upgradation, 2026-09-02)_ |
| 4 | Identity posture | Per account. User Agreement §1.2.1: 'Your account is only for your own use'; no explicit multi-account prohibition in fetched sections. _(src: https://docs.siliconflow.cn/en/legals/terms-of-service, 2026-09-02)_ |
| 5 | Failure & resume | Retry 429/503/504; idempotency and batch UNKNOWN (not on fetched pages). _(src: https://docs.siliconflow.cn/en/faqs/error-code, 2026-09-02)_ |
| 6 | Cost model | Per MTok in CNY (DeepSeek-V4-Flash ¥3 in/¥9 out, ¥1.5/¥4.5 02:00–08:00 Beijing from 2026-09-01); free models exist, paid variants prefixed 'Pro/'; prices change with short notice. _(src: https://docs.siliconflow.cn/en/release-notes/overview, 2026-09-02)_ |
| 7 | Usage observability | GET /v1/user/info (balance) RETIRED 2026-08-14 (3 days' notice); replacement 'to be announced' → programmatic usage currently UNKNOWN. _(src: https://docs.siliconflow.cn/en/release-notes/overview, 2026-09-02)_ |
| 8 | Health signal | https://status.siliconflow.cn (Instatus-style page, fetched: 'All services are online', last updated 2026-04-08 — stale); /api/v2/status.json failed. _(src: https://status.siliconflow.cn/, 2026-09-02)_ |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) api-key guide page 404; wrong key → 401. — suggested src: https://docs.siliconflow.cn/en/faqs/error-code |
| 10 | Interface lifecycle | Deprecations only via Release Notes page (model offline lists, e.g. 2026-06-11); endpoint retirement given 3 days (Aug 11→14 2026). No headers, no fixed notice period. _(src: https://docs.siliconflow.cn/en/release-notes/overview, 2026-09-02)_ |
| 11 | Data contract | JSON {code,message,data}; fields blanked in place (user/info name/email → '' after June 11) without version bump. _(src: https://docs.siliconflow.cn/en/api-reference/userinfo/get-user-info, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only. _(src: https://docs.siliconflow.cn/en/faqs/error-code, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Two silent-drift signals this year (user/info fields blanked, endpoint retired on 3 days' notice) — validate strictly.

### Deepinfra

**Type:** ai-llm · **Reach:** REST API (env key) · **Used by:** 2 project(s) — fabrik, iterative_image_editor · **Env keys:** `DEEPINFRA_*` · **Docs:** https://deepinfra.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Default 200 concurrent requests per model per account (400 across two models); no RPM cap — throughput = concurrency ÷ latency. _(src: https://deepinfra.com/docs/advanced/rate-limits, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 'Rate limited'; may also 429 when a model is busy even under limit (autoscaling) — retry after brief wait. _(src: https://deepinfra.com/docs/advanced/rate-limits, 2026-09-02)_ |
| 3 | Concurrency & parallelism | 200 concurrent per model, scoped per account; increase via Dashboard → Account. _(src: https://deepinfra.com/docs/advanced/rate-limits, 2026-09-02)_ |
| 4 | Identity posture | Per account. ToS (2026-08-17) is a B2B Service-Order contract; no multi-account or circumvention clause in fetched sections → UNKNOWN. _(src: https://deepinfra.com/terms, 2026-09-02)_ |
| 5 | Failure & resume | Retry 429 with delay; Batch API (OpenAI-compatible files/batches, async, 20% off); idempotency key UNKNOWN. _(src: https://docs.deepinfra.com/llms.txt, 2026-09-02)_ |
| 6 | Cost model | Per MTok per model (DeepSeek-V4-Flash-0731 $0.08 in / $0.016 cached / $0.18 out; Kimi-K3 $2.85/$14.25); non-LLM models billed per execution time; no minimums; batch −20%. _(src: https://deepinfra.com/pricing, 2026-09-02)_ |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) docs billing/api_keys pages redirect to landing; only Dashboard referenced. — suggested src: https://deepinfra.com/docs/advanced/billing |
| 8 | Health signal | https://status.deepinfra.com custom page (fetched HTML: core services + per-model health, 60s checks); /api/v2/status.json unreachable (exa timeout, WebFetch ECONNREFUSED) → no machine-readable feed confirmed. _(src: https://status.deepinfra.com/, 2026-09-02)_ |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) api_keys doc page redirects to landing; keys managed at /dash/api_keys. — suggested src: https://deepinfra.com/docs/advanced/api_keys |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) /docs/deprecations redirects to landing; no deprecation policy page in llms.txt index. — suggested src: https://docs.deepinfra.com/llms.txt |
| 11 | Data contract | OpenAI-compatible at /v1/openai; native API separate; silent-change history UNKNOWN. _(src: https://docs.deepinfra.com/llms.txt, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only (batch via polling). _(src: https://docs.deepinfra.com/llms.txt, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Docs site recently restructured (docs.deepinfra.com); several deepinfra.com/docs/advanced/* URLs now land on the index.

### Modelscope

**Type:** ai-llm · **Reach:** REST API (env key) · **Used by:** 2 project(s) — fabrik, iterative_image_editor · **Env keys:** `MODELSCOPE_*` · **Docs:** https://modelscope.cn

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 6 | Cost model | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Grounding impossible: session has no web search/fetch tools; cannot cite any vendor URL.

### Nvidia

**Type:** ai-llm · **Reach:** REST API (env key) · **Used by:** 2 project(s) — fabrik, youtube · **Env keys:** `NVIDIA_*` · **Docs:** https://build.nvidia.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Trial rate limits per model, unpublished ('we do not publish those'); credit system retired (NVIDIA staff, forum 2025-09); community-reported ~40 RPM default. Your cap shown top-right of build.nvidia.com. _(src: https://forums.developer.nvidia.com/t/request-more-4-000-credits-option-on-build-nvidia-com/344567, 2026-09-02)_ |
| 2 | Behaviour AT the cap | Trial ToS §1.1: 'Subject to use limits defined by NVIDIA'. Behaviour at cap (429, Retry-After) not documented on any fetched official page → UNKNOWN. _(src: https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf, 2026-09-02)_ |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) tried docs.api.nvidia.com/nim (rate-limits 404, getting-started timeout/empty), build.nvidia.com/terms (landing page only). — suggested src: https://build.nvidia.com/terms |
| 4 | Identity posture | Trial ToS §1.2/1.4: trial only, not for production; production requires NVIDIA AI Enterprise subscription. No multi-account clause in fetched sections. _(src: https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf, 2026-09-02)_ |
| 5 | Failure & resume | OpenAI Chat Completions-compatible at https://integrate.api.nvidia.com/v1; idempotency/resume UNKNOWN. _(src: https://build.nvidia.com/terms, 2026-09-02)_ |
| 6 | Cost model | Free for prototyping under NVIDIA Developer Program (no per-token price, no credit card); production = NVIDIA AI Enterprise license (free 90-day trial). _(src: https://docs.api.nvidia.com/nim/re/docs/product, 2026-09-02)_ |
| 7 | Usage observability | Limit visible in build.nvidia.com UI only; no usage API found. _(src: https://forums.developer.nvidia.com/t/request-more-4-000-credits-option-on-build-nvidia-com/344567, 2026-09-02)_ |
| 8 | Health signal | Statuspage: https://status.ngc.nvidia.com/api/v2/status.json returns JSON (fetched via WebFetch: 'All Systems Operational'). _(src: https://status.ngc.nvidia.com/api/v2/status.json, 2026-09-02)_ |
| 9 | Credential lifecycle | nvapi- bearer key from build.nvidia.com/settings; expiry policy UNKNOWN — settings page needs login; NGC user guide fetched portion has no expiry text. _(src: https://docs.nvidia.com/ngc/gpu-cloud/ngc-user-guide/index.html, 2026-09-02)_ |
| 10 | Interface lifecycle | Trial ToS §1.3: may modify/discontinue service any time without liability; §15.7: updated terms effective on publication. No deprecation channel or headers. _(src: https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf, 2026-09-02)_ |
| 11 | Data contract | OpenAI-compatible; /models.md paginated catalog; schema stability UNKNOWN. _(src: https://build.nvidia.com/terms, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only. _(src: https://build.nvidia.com/terms, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Weakest vendor: official docs site 404/timeouts; grounded on Trial ToS PDF, NIM FAQ, and NVIDIA-staff forum replies.

### Huggingface

**Type:** ai-llm · **Reach:** REST API (env key) · **Used by:** 2 project(s) — fabrik, iterative_image_editor · **Env keys:** `HF_*` · **Docs:** https://huggingface.co

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Hub 5-min fixed windows: Free 1,000 API / 5,000 resolvers / 200 pages; PRO 2,500/12,000/400; Enterprise 6,000/50,000/600. Inference Providers: $0.10/mo free credits, $2 PRO, then pay-as-you-go. _(src: https://huggingface.co/docs/hub/rate-limits, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 Too Many Requests with IETF RateLimit / RateLimit-Policy headers (remaining, seconds to reset); huggingface_hub ≥1.2.0 auto-retries. _(src: https://huggingface.co/docs/hub/rate-limits, 2026-09-02)_ |
| 3 | Concurrency & parallelism | Per user/token (org limits apply per member, not shared); anonymous per IP; provider-side concurrency UNKNOWN. _(src: https://huggingface.co/docs/hub/rate-limits, 2026-09-02)_ |
| 4 | Identity posture | Per user/token. ToS (eff. 2022-09-15): no clause on multiple accounts, account sharing, or limit circumvention (WebFetch confirmed absent). _(src: https://huggingface.co/terms-of-service, 2026-09-02)_ |
| 5 | Failure & resume | Retry 429/5xx (smart retry in SDK); providers pass-through; idempotency UNKNOWN. _(src: https://huggingface.co/docs/hub/rate-limits, 2026-09-02)_ |
| 6 | Cost model | Provider rates passed through with no markup; hf-inference billed compute-seconds × hardware (e.g. 10s × $0.00012/s = $0.0012); after credits, purchase required. _(src: https://huggingface.co/docs/inference-providers/en/pricing, 2026-09-02)_ |
| 7 | Usage observability | Billing page gauges (last-5-min per bucket) + Inference Providers usage settings (per model/provider, UI); RateLimit headers on responses; no usage REST endpoint on fetched pages. _(src: https://huggingface.co/docs/hub/rate-limits, 2026-09-02)_ |
| 8 | Health signal | https://status.huggingface.co (Instatus-style page fetched; /api/v2/status.json returns HTML, not JSON) → machine-readable UNKNOWN. _(src: https://status.huggingface.co/api/v2/status.json, 2026-09-02)_ |
| 9 | Credential lifecycle | User Access Tokens (read/write/fine-grained), no default expiry documented; multiple tokens → overlap; revoke any leaked token via POST /api/credentials/revoke; org token-approval policies; OIDC Trusted Publishers short-lived. _(src: https://huggingface.co/docs/hub/security-tokens, 2026-09-02)_ |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no deprecation policy page found; rate-limit tiers 'subject to change'; hf-inference scope narrowed (July 2025) via docs note only. — suggested src: https://huggingface.co/docs/inference-providers/en/pricing |
| 11 | Data contract | OpenAI-compatible chat route; per-task schemas; silent-change history UNKNOWN. _(src: https://huggingface.co/docs/inference-providers/en/index, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a for inference — pull-only (Hub webhooks cover repo events only; not fetched). _(src: https://huggingface.co/docs/inference-providers/en/index, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Free-tier credits '$0.10, subject to change' — re-verify monthly.

### Z.ai

**Type:** ai-llm · **Reach:** REST API (env key) · **Used by:** 1 project(s) — fabrik · **Env keys:** `ZAI_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'zai API rate limits', fetched 'https://docs.zai.com/' which returned 404 — suggested src: https://docs.zai.com/ |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'zai rate limit response headers', fetched 'https://zai.com/developers' which showed no technical docs — suggested src: https://zai.com/developers |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'zai concurrency API', fetched 'https://zai.com/api-docs' which redirected to homepage — suggested src: https://zai.com/api-docs |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'zai Terms of Service', fetched 'https://zai.com/terms' which showed generic terms without API clauses — suggested src: https://zai.com/terms |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'zai idempotency retry', fetched 'https://docs.zai.com/guides' which returned 404 — suggested src: https://docs.zai.com/guides |
| 6 | Cost model | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'zai pricing API costs', fetched 'https://zai.com/pricing' which showed only product plans — suggested src: https://zai.com/pricing |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'zai usage API monitoring', fetched 'https://zai.com/account/usage' requiring login — suggested src: https://zai.com/account/usage |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'zai status page', fetched 'https://status.zai.com/' returning 404 — suggested src: https://status.zai.com/ |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'zai API key expiration', fetched 'https://zai.com/security' showing no technical details — suggested src: https://zai.com/security |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'zai API versioning deprecation', fetched 'https://zai.com/changelog' showing product updates only — suggested src: https://zai.com/changelog |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'zai API schema documentation', fetched 'https://docs.zai.com/api-reference' returning 404 — suggested src: https://docs.zai.com/api-reference |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'zai webhooks delivery', fetched 'https://zai.com/webhooks' showing no technical specifications — suggested src: https://zai.com/webhooks |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: No public API documentation found; all endpoints either 404 or require authentication

### Cerebras Inference

**Type:** ai-llm · **Reach:** REST API, OpenAI-compatible (`CEREBRAS_API_KEY` — no key exists on the box, D-078) · **Used by:** 2 project(s) — fabrik, fabrik-lib (code call sites) · **Hosts:** `api.cerebras.ai` · **Env keys:** none in the fleet today (reached without a key; the posture row names the knob a consumer would add) · **Docs:** https://inference-docs.cerebras.ai

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Org-level (not per-user), per-model, token-bucket (continuous refill), dual-bucket: uncached TPM (primary) + total TPM (default 3x uncached). Free Trial (`gpt-oss-120b`, `gemma-4-31b`): 5 RPM / 30K TPM / 1M TPH / 1M TPD; 65k context, 32k max output. Developer (Pay-as-you-go): `gpt-oss-120b` 1K RPM / 1M TPM, `gemma-4-31b` 300 RPM / 500K TPM, NO hourly/daily caps; 131k context, 40k max output. Enterprise: per-org negotiated. Image limits (gemma): free 2/req + 4 MB, paid 10/req + 10 MB; 15,000 px per side. Batch (Private Preview): 10–50,000 requests/file, 200 MB, 1 MB/line. Quota check pre-flight uses prompt estimate + `max_completion_tokens`. _(src: https://inference-docs.cerebras.ai/support/rate-limits, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 Too Many Requests; 'the error message will indicate whether your uncached or total token limit was exceeded'; request rejected before processing if the token estimate exceeds available quota. Free-Trial credit exhaustion/expiry = API + Playground access STOP (keys/settings kept) until a PAYG purchase; 402 PaymentRequired is in the status table. SDK auto-retries 429/408/>=500/connection errors 2x with short exponential backoff (`max_retries`); default request timeout 1 min. Retry-After header + `x-ratelimit-*` response headers: UNKNOWN — tried rate-limits (live page has no headers section; a stale search snippet of the same URL listed `x-ratelimit-limit-requests-day`/`x-ratelimit-remaining-tokens-minute`/`x-ratelimit-reset-*`, NOT on the page today), support/error, api-reference/chat-completions.md. _(src: https://inference-docs.cerebras.ai/support/error, 2026-09-02)_ |
| 3 | Concurrency & parallelism | No in-flight/connection cap documented — only RPM/TPM buckets ('any metric can trigger rate limiting, whichever comes first'); Projects split an org ceiling into per-project sub-quotas (two-level check: project AND org). `service_tier` (Private Preview): `priority` (dedicated only) / `default` / `auto` / `flex`; flex limits tracked independently at 'several multiples of default'; `queue_threshold` header 50–20000 ms pre-rejects flex/auto requests. Speed ~3000 tok/s (`gpt-oss-120b`), ~1500–1850 tok/s (`gemma-4-31b`). _(src: https://inference-docs.cerebras.ai/capabilities/service-tiers, 2026-09-02)_ |
| 4 | Identity posture | Per Organization (billing + global ceilings) → Projects (keys, limits, members; every key belongs to exactly one project; Free Trial has no projects). Roles: Org Admin / Project Admin / Project Member. ToS: 'You must not set up an account on behalf of another individual or entity unless you are a Business User'; 'Buy, sell or transfer API keys without our prior written consent' prohibited; no explicit multi-account clause (ABSENT); suspension clause fetched only for non-payment (5 days past due). $5 trial requires a verified payment method. _(src: https://www.cerebras.ai/terms-of-service, 2026-09-02)_ |
| 5 | Failure & resume | Synchronous chat/completions: no idempotency key documented — smallest resumable unit = one request; SDK retries 2x by default (configurable), `APITimeoutError` on 1-min timeout. Batch (Private Preview): JSONL with unique `custom_id` per line, states `queued`→`in_progress`→`finalizing`→`completed`, 'guaranteed to complete in 24 hours', `output_file_id` + `error_file_id` for partial-failure resume, `request_counts.completed/total`; cancel endpoint exists. Prompt cache TTL guaranteed 5 min (up to 1 h), 128-token blocks, org-scoped. _(src: https://inference-docs.cerebras.ai/capabilities/batch, 2026-09-02)_ |
| 6 | Cost model | Prepaid credits, no permanently free tier: $5 trial credits (30-day expiry, payment method required) → PAYG 'starting at just $10', auto-recharge off by default (threshold + top-up amount configurable), per-model monthly Subscriptions ('multiple tiers at different monthly rates', usage under an active subscription excluded from usage billing). Per-M-token: `gpt-oss-120b` $0.35 in / $0.75 out (docs page AND live public models endpoint agree); `gemma-4-31b` docs page says $2.15 in / $2.70 out but the live endpoint `/public/v1/models` returns $0.99 in / $1.49 out today — DISCREPANCY, code should read the endpoint. Cached-input price: OpenRouter-format field 'typically "0"' — no documented cached discount (tried prompt-caching, public-models). Service tiers billed equally during preview. Fees non-refundable (ToS). _(src: https://api.cerebras.ai/public/v1/models?format=huggingface, 2026-09-02)_ |
| 7 | Usage observability | Response body `usage` {prompt_tokens, completion_tokens, total_tokens, prompt_tokens_details.cached_tokens, completion_tokens_details.reasoning_tokens, image_tokens} + `time_info` {queue_time, prompt_time, completion_time, total_time, created} + `system_fingerprint`; `service_tier_used` when `auto`. Console (cloud.cerebras.ai → Analytics): Usage (with 'Show quotas' overlay, CSV), Cached-Usage, Cost (by model, ≤10 min delay), Request Logs (filter by model/key/status, Request ID for support), Audit Logs (admins), Limits page (per-model RPM/TPM by minute/day; hourly org-only). No usage/quota REST endpoint documented for shared endpoints (tried usage-monitoring, llms.txt index); Prometheus `/api/v1/metrics/organizations/<org_id>` is DEDICATED-endpoint only (6 req/min). _(src: https://inference-docs.cerebras.ai/console/usage-monitoring, 2026-09-02)_ |
| 8 | Health signal | Statuspage (Atlassian) at https://status.cerebras.ai — `GET /api/v2/status.json` returned {"status":{"indicator":"none","description":"All Systems Operational"}, page.updated_at 2026-09-02T09:49:35Z} today; components: Llama3.1-8B, Qwen-3-235B-Instruct-2507, GPT-OSS-120B, ZAI-GLM-4.7, Developer Console (90-day uptime 99.9–100%); last listed incident May 1 ('service is currently inaccessible', ~1 h). Docs mirror: https://inference-docs.cerebras.ai/support/status. Public unauthenticated model list `GET https://api.cerebras.ai/public/v1/models` (200 today) doubles as a liveness probe. _(src: https://status.cerebras.ai/api/v2/status.json, 2026-09-02)_ |
| 9 | Credential lifecycle | Static `Authorization: Bearer <key>` (env `CEREBRAS_API_KEY`); 'API keys do not expire'; created in Console → API Keys (project-scoped on paid accounts, key inherits project limits); full key copyable any time after creation; rotate = create new → switch app → delete old; deletion 'immediate and permanent' → 401 Unauthorized; archiving a project invalidates all its keys; separate Management API keys for dedicated endpoints. Never client-side. _(src: https://inference-docs.cerebras.ai/console/api-keys, 2026-09-02)_ |
| 10 | Interface lifecycle | Endpoint path stays `/v1/...`; breaking validation/response changes ship as API VERSIONS selectable via `X-Cerebras-Version-Patch` header, available for testing 'a minimum of 6 months before taking effect', email notice; v2 default since July 22, 2026 (stricter structured-output/tool validation, separate `reasoning_logprobs`, 422→400 for validation errors). Model retirements: Deprecations page (newest first, migration target named — 13 models retired incl. `llama3.1-8b`, `llama-3.3-70b`, `qwen-3-*`, `zai-glm-4.7`) — no fixed notice period documented for MODEL deprecations (tried deprecation, change-log, versions); `deprecated`/`preview` booleans on the public models endpoint; deprecated id → 404 model not found. Release stages: Private Preview (no SLA, unstable) / Public Preview / GA. _(src: https://inference-docs.cerebras.ai/api-reference/versions, 2026-09-02)_ |
| 11 | Data contract | OpenAI-compatible: base `https://api.cerebras.ai/v1` (OpenAI SDK works with `base_url`); `POST /v1/chat/completions` → {id, object:'chat.completion', created, model, system_fingerprint, choices[{index, message{role, content, tool_calls}, finish_reason, logprobs}], usage, time_info}; streaming chunks `object:'chat.completion.chunk'` with `delta` and usage in the final chunk; `Content-Type: application/vnd.msgpack` + `Content-Encoding: gzip` accepted. Public models list {object:'list', data[{id, pricing{prompt,completion} per-token USD strings, capabilities{}, supported_parameters{}, limits{max_context_length, max_completion_tokens, requests_per_minute, tokens_per_minute}, deprecated, preview, quantization}]} with `?format=openrouter\|huggingface`. Differences: `system`==`developer` role; `gpt-oss-120b` rejects `tools`+`response_format` together; images only base64 data URIs (no HTTPS URLs); non-standard params via `extra_body`. Error body schema: UNKNOWN — tried support/error, chat-completions.md (status→exception table only). _(src: https://inference-docs.cerebras.ai/api-reference/chat-completions, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | No webhooks or event callbacks documented (tried llms.txt index, batch, management-api, console pages) — batch is POLL-based (`GET /v1/batches/{id}`, then download `output_file_id`/`error_file_id`). Only push-shaped surface is SSE streaming on chat/completions (`stream: true`); wire-level details ([DONE] sentinel, `stream_options`, reconnect/resume) UNKNOWN — tried capabilities/streaming, chat-completions.md. Status-page subscription via Statuspage 'Subscribe to Updates'. _(src: https://inference-docs.cerebras.ai/llms.txt, 2026-09-02)_ |
| — | **Resilience posture (58)** | LLM inference, OpenAI-compatible; prepaid credits with a hard STOP at zero balance (no overage) → `CEREBRAS_*` env key + balance watch in the caller; 429 = back off (SDK retries 2x) and the message names the bucket; no idempotency key → make the request the retry unit; read per-model pricing/limits/deprecated from `GET /public/v1/models` (unauthenticated), never from a literal; health = status.cerebras.ai JSON |

- **Research notes** _(2026-09-02)_: vendor status: https://status.cerebras.ai (Statuspage JSON: https://status.cerebras.ai/api/v2/status.json).

## AI — media generation, audio & stock

### Black Forest Labs

**Type:** ai-image · **Reach:** REST API (env key) · **Used by:** 2 project(s) — brand-identiy-creator, iterative_image_editor · **Env keys:** `BFL_*` · **Docs:** https://blackforestlabs.ai

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'Black Forest Labs FLUX API limits' — suggested src: https://docs.bfl.ai/ |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'Black Forest Labs API errors' — suggested src: https://docs.bfl.ai/ |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'Black Forest Labs concurrency' — suggested src: https://docs.bfl.ai/ |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'Black Forest Labs ToS' — suggested src: https://docs.bfl.ai/ |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'Black Forest Labs async generation' — suggested src: https://docs.bfl.ai/ |
| 6 | Cost model | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'Black Forest Labs pricing' — suggested src: https://docs.bfl.ai/ |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'Black Forest Labs account usage' — suggested src: https://docs.bfl.ai/ |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'Black Forest Labs status' — suggested src: https://docs.bfl.ai/ |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'Black Forest Labs api key' — suggested src: https://docs.bfl.ai/ |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'Black Forest Labs API versioning' — suggested src: https://docs.bfl.ai/ |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'Black Forest Labs API schema' — suggested src: https://docs.bfl.ai/ |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) search 'Black Forest Labs webhooks' — suggested src: https://docs.bfl.ai/ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Image generation (FLUX)
- **Endpoints** _(2026-06-02 entry)_: - Base URL: https://api.blackforestlabs.ai/v1 - Generate Image: `POST /flux-dev/v1/text-to-image`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: AI image generation
- **Notes** _(2026-06-02 entry)_: - FLUX model for image generation
- **Research notes** _(2026-09-02)_: FLUX image-gen API; async pattern with webhook or polling. Live web fetch was unavailable in this run.

### Stability

**Type:** ai-image · **Reach:** REST API (env key) · **Used by:** 1 project(s) — iterative_image_editor · **Env keys:** `STABILITY_*` · **Docs:** https://stability.ai

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | 150 requests per 10 seconds per account/API key. _(src: https://platform.stability.ai/docs/api-reference, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 and a 60-second timeout/ban. _(src: https://platform.stability.ai/docs/api-reference, 2026-09-02)_ |
| 3 | Concurrency & parallelism | Effective 150 req/10s; async result polling max once per 10s per id; 'use the same key for all requests'. _(src: https://platform.stability.ai/docs/api-reference, 2026-09-02)_ |
| 4 | Identity posture | ToS: if account disabled, 'you may not create another account without our express permission'. Multiple keys per account allowed. No explicit rate-limit circumvention clause seen. _(src: https://platform.stability.ai/legal/terms-of-service, 2026-09-02)_ |
| 5 | Failure & resume | Failed results not charged; async ops return id → GET /v2beta/results/{id}: 202 in-progress, 200 done, 404 expired. Retention window UNKNOWN (api-reference JS-rendered; WebFetch got title only). _(src: https://platform.stability.ai/docs/api-reference, 2026-09-02)_ |
| 6 | Cost model | Credits: 1 credit = $0.01; 25 free credits; Ultra 8, SD3.5 Large 6.5, Core 3, Creative Upscale 60, Stable Audio 3.0 26. _(src: https://platform.stability.ai/pricing, 2026-09-02)_ |
| 7 | Usage observability | GET /v1/user/balance (Account balance) and Account details endpoints listed in reference. _(src: https://platform.stability.ai/docs/api-reference, 2026-09-02)_ |
| 8 | Health signal | Statuspage: https://status.stability.ai/api/v2/status.json returns JSON (fetched; old instatus page announces the move). _(src: https://status.stability.ai/api/v2/status.json, 2026-09-02)_ |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) authentication doc page 404; keys managed on account page; invalid key → 401. — suggested src: https://platform.stability.ai/docs/getting-started/authentication |
| 10 | Interface lifecycle | v2beta primary since March 2024; gRPC/v1/v2alpha maintained, no new features, 'not deprecating v2alpha at this time'; no Sunset header; ToS update banner (eff. 2025-07-31). _(src: https://platform.stability.ai/docs/api-reference, 2026-09-02)_ |
| 11 | Data contract | multipart/form-data in; image/* or JSON base64 out via accept header; per-endpoint schemas; silent changes UNKNOWN. _(src: https://platform.stability.ai/docs/api-reference, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only (async via polling). _(src: https://platform.stability.ai/docs/api-reference, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Index should point to status.stability.ai, not stabilityai.instatus.com.

### Recraft

**Type:** ai-image · **Reach:** REST API (env key) · **Used by:** 2 project(s) — fabrik, iterative_image_editor · **Env keys:** `RECRAFT_*` · **Docs:** https://recraft.ai

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'recraft API rate limits image generation' — suggested src: https://www.recraft.ai/docs |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'recraft API 429 error behavior' — suggested src: https://www.recraft.ai/docs |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'recraft API concurrency parallel jobs' — suggested src: https://www.recraft.ai/docs |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'recraft API key per account ToS' — suggested src: https://www.recraft.ai/docs |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'recraft API retry idempotency' — suggested src: https://www.recraft.ai/docs |
| 6 | Cost model | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'recraft API pricing credits' — suggested src: https://www.recraft.ai/pricing |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'recraft API credits remaining endpoint' — suggested src: https://www.recraft.ai/docs |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'recraft status page' — suggested src: https://www.recraft.ai |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'recraft API key expiry rotation' — suggested src: https://www.recraft.ai/docs |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'recraft API versioning deprecation' — suggested src: https://www.recraft.ai/docs |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'recraft API response schema image' — suggested src: https://www.recraft.ai/docs |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'recraft webhooks image ready' — suggested src: https://www.recraft.ai/docs |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Recraft is a newer AI image vendor; docs structure unconfirmed — lacks web tools to verify.

### Fal

**Type:** ai-image · **Reach:** REST API (env key) · **Used by:** 2 project(s) — fabrik, iterative_image_editor · **Env keys:** `FAL_*` · **Docs:** https://fal.ai

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | paid _(catalog `cost`, refreshed daily)_ |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### Replicate

**Type:** ai-image · **Reach:** REST API (env key) · **Used by:** 3 project(s) — brand-identiy-creator, fabrik, iterative_image_editor · **Env keys:** `REPLICATE_*` · **Docs:** https://replicate.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'replicate API rate limits predictions' — suggested src: https://replicate.com/docs |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'replicate API 429 throttle' — suggested src: https://replicate.com/docs |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'replicate API concurrency parallel predictions' — suggested src: https://replicate.com/docs |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'replicate API token per account ToS' — suggested src: https://replicate.com/docs |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'replicate API retry webhook idempotency' — suggested src: https://replicate.com/docs |
| 6 | Cost model | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'replicate pricing per second hardware' — suggested src: https://replicate.com/pricing |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'replicate API account balance endpoint' — suggested src: https://replicate.com/docs |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'replicate status page' — suggested src: https://replicate.com/docs |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'replicate API token rotation expiry' — suggested src: https://replicate.com/docs |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'replicate API model versioning deprecation' — suggested src: https://replicate.com/docs |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'replicate API prediction schema' — suggested src: https://replicate.com/docs |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'replicate webhooks signature signing secret' — suggested src: https://replicate.com/docs/webhooks |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Replicate docs are documented to use webhooks with signing secrets, but cannot verify without web tools.

### Wavespeed

**Type:** unidentified · **Reach:** REST API (env key) · **Used by:** 1 project(s) — iterative_image_editor · **Env keys:** `WAVESPEED_*` · **Catalog status:** unidentified

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) tried fetching https://wavespeed.ai homepage but blocked by anti-bot; no docs page reached — suggested src: https://wavespeed.ai |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) docs unreachable — suggested src: https://wavespeed.ai |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) docs unreachable — suggested src: https://wavespeed.ai |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) docs unreachable — suggested src: https://wavespeed.ai |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) docs unreachable — suggested src: https://wavespeed.ai |
| 6 | Cost model | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) docs unreachable; pricing page not fetched — suggested src: https://wavespeed.ai |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) docs unreachable — suggested src: https://wavespeed.ai |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) docs unreachable — suggested src: https://wavespeed.ai |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) docs unreachable — suggested src: https://wavespeed.ai |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) docs unreachable — suggested src: https://wavespeed.ai |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) docs unreachable — suggested src: https://wavespeed.ai |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) docs unreachable — suggested src: https://wavespeed.ai |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: wavespeed.ai returned anti-bot challenge on fetch; cannot ground any field without successful doc fetch.

### Higgsfield

**Type:** ai-media · **Reach:** REST API (env key) · **Used by:** 1 project(s) — iterative_image_editor · **Env keys:** `HIGGSFIELD_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Primary limit is concurrency per account/plan/model (e.g. 4), shown in Higgsfield Cloud dashboard; no RPM published. _(src: https://docs.higgsfield.ai/docs/concepts/rate-limits, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 400 Bad Request {'detail':'Maximum number of concurrent requests (4) has been reached'}; no rate-limit headers, no Retry-After. _(src: https://docs.higgsfield.ai/docs/concepts/rate-limits, 2026-09-02)_ |
| 3 | Concurrency & parallelism | Concurrency = queued + processing requests, per account; some models have own caps; consumer Concurrency Boost packs add +4…+16. _(src: https://docs.higgsfield.ai/docs/concepts/rate-limits, 2026-09-02)_ |
| 4 | Identity posture | Per account/organization; plans FAQ: 'Each account supports one active subscription'. No multi-account or circumvention clause found → ToS UNKNOWN. _(src: https://higgsfield.ai/creator-hub/help-center/plans/how-do-higgsfield-plans-work, 2026-09-02)_ |
| 5 | Failure & resume | Retry GET status on 5xx/network; do NOT retry generation POST after ambiguous timeout (no idempotency key); request_id + X-Correlation-ID; cancel only while queued (202). _(src: https://docs.higgsfield.ai/docs/concepts/errors, 2026-09-02)_ |
| 6 | Cost model | Credits per successful generation (model/params); POST /estimate/{model} returns credits + usd; failed/nsfw refunded; credits expire 1 year after purchase. _(src: https://docs.higgsfield.ai/docs/concepts/billing-and-retention, 2026-09-02)_ |
| 7 | Usage observability | Dashboard usage/credit stats; estimate endpoint pre-flight; 403 = insufficient credits. _(src: https://docs.higgsfield.ai/docs/concepts/errors, 2026-09-02)_ |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no official status page found (searched; only third-party monitors statusgator/isdown). — suggested src: https://docs.higgsfield.ai/docs/help/faq |
| 9 | Credential lifecycle | Authorization: Key ID:SECRET (legacy hf-api-key/hf-secret headers still accepted); 401 invalid; rotate by issuing new credential (overlap implied); expiry UNKNOWN. _(src: https://docs.higgsfield.ai/docs/authentication, 2026-09-02)_ |
| 10 | Interface lifecycle | UNKNOWN deprecation channel/notice; legacy auth headers kept alive; 423 = model temporarily blocked, 503 = model disabled. — suggested src: https://docs.higgsfield.ai/docs/concepts/errors |
| 11 | Data contract | Output shape varies by model (images[], video, audio, zip/mov/fbx/ply); terminal statuses completed/failed/nsfw/canceled; outputs retained ≥7 days then may vanish. _(src: https://docs.higgsfield.ai/docs/concepts/requests, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | Webhook via hf_webhook query param (HTTPS, reply <10s); POST on terminal status; retries up to 2h on 5xx/network, 4xx never retried; duplicates possible → dedup request_id+status; no list endpoint (fall back to status GET). _(src: https://docs.higgsfield.ai/docs/how-to/webhooks, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Docs real paths are /docs/concepts/* and /docs/how-to/* (llms.txt); /docs/errors and /docs/webhooks 404.

### Elevenlabs

**Type:** ai-audio · **Reach:** REST API (env key) · **Used by:** 2 project(s) — fabrik, iterative_image_editor · **Env keys:** `ELEVENLABS_*` · **Docs:** https://elevenlabs.io

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | paid _(catalog `cost`, refreshed daily)_ |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### Soniox

**Type:** ai-audio · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found) · **Docs:** https://soniox.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | - Contact Soniox _(carried from the 2026-06-02 entry — re-verify)_ |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | paid _(catalog `cost`, refreshed daily)_ |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | - Type: API Key - Env Vars: `SONIOX_API_KEYS` (comma-separated) - Generate at: Soniox Dashboard — expiry/rotation UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Audio transcription
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Audio transcription for YouTube videos
- **Notes** _(2026-06-02 entry)_: - Multiple API keys for load balancing

### Pexels

**Type:** media-stock · **Reach:** REST API (env key) · **Used by:** 2 project(s) — iterative_image_editor, spec:image-broker · **Env keys:** `PEXELS_*` · **Docs:** https://pexels.com/api

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Default 200 requests/hour and 20,000 requests/month per key; unlimited free on approval (api@pexels.com). _(src: https://www.pexels.com/api/documentation/, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 Too Many Requests; X-Ratelimit headers NOT included on 429 (only on 2xx). _(src: https://www.pexels.com/api/documentation/, 2026-09-02)_ |
| 3 | Concurrency & parallelism | UNKNOWN concurrency; limits per key. — suggested src: https://www.pexels.com/api/documentation/ |
| 4 | Identity posture | Per key. Docs: 'attempting to work around the rate limit will lead to termination of your API access'. API terms page 404 (/api/terms/); general ToS fetched has no API clause. _(src: https://www.pexels.com/api/documentation/, 2026-09-02)_ |
| 5 | Failure & resume | Read-only GETs (idempotent); pagination page/per_page (max 80), next_page/prev_page only when present; no resume beyond page number. _(src: https://www.pexels.com/api/documentation/, 2026-09-02)_ |
| 6 | Cost model | Free; attribution link required; content free under Pexels license. _(src: https://www.pexels.com/api/documentation/, 2026-09-02)_ |
| 7 | Usage observability | X-Ratelimit-Limit / X-Ratelimit-Remaining / X-Ratelimit-Reset (UNIX ts) on successful responses. _(src: https://www.pexels.com/api/documentation/, 2026-09-02)_ |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) status.pexels.com exists per search ('No known issues', no monitors) but was not fetched; no machine-readable feed found. — suggested src: https://www.pexels.com/api/documentation/ |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) expiry not documented; help-center says keys cannot be self-rotated (seen in search snippet only, not fetched); 401 on missing key presumed. — suggested src: https://www.pexels.com/api/documentation/ |
| 10 | Interface lifecycle | Video endpoints moved to /v1/videos/; old /videos/ 'will be deprecated in the future' (no date); changelog section in docs; no headers. _(src: https://www.pexels.com/api/documentation/, 2026-09-02)_ |
| 11 | Data contract | Photo resource fields documented (id,width,height,url,photographer*,avg_color,src…); total_results; pagination attrs conditional. _(src: https://www.pexels.com/api/documentation/, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only. _(src: https://www.pexels.com/api/documentation/, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Stock photos and videos
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://api.pexels.com/v1` - Search Photos: `GET /search` - Curated Photos: `GET /curated` - Get Photo: `GET /photos/{id}`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Stock photo search and download - Service URL: `https://images.vps1.ocoron.com`
- **Notes** _(2026-06-02 entry)_: - Configured and active
- **Research notes** _(2026-09-02)_: Single official source; help-center articles reachable only via search snippets this run.

### Pixabay

**Type:** media-stock · **Reach:** REST API (env key) · **Used by:** 2 project(s) — iterative_image_editor, spec:image-broker · **Env keys:** `PIXABAY_*` · **Docs:** https://pixabay.com/api/docs

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | 100 requests per 60 seconds per API key (not IP); responses must be cached 24h; no mass/automated queries. _(src: https://pixabay.com/api/docs/, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 'API rate limit exceeded' (plain-text body); other errors plain-text with HTTP code. _(src: https://pixabay.com/api/docs/, 2026-09-02)_ |
| 3 | Concurrency & parallelism | UNKNOWN concurrency; per key. — suggested src: https://pixabay.com/api/docs/ |
| 4 | Identity posture | Per key. ToS §8 bans scraping/bulk copying; no multi-account or API-specific clause (WebFetch confirmed). _(src: https://pixabay.com/service/terms/, 2026-09-02)_ |
| 5 | Failure & resume | Read-only GET; page/per_page 3–200; totalHits capped at 500 per query; 24h cache mandated. _(src: https://pixabay.com/api/docs/, 2026-09-02)_ |
| 6 | Cost model | Free; attribution requested; no hotlinking of images (download first). _(src: https://pixabay.com/api/docs/, 2026-09-02)_ |
| 7 | Usage observability | X-RateLimit-Limit / X-RateLimit-Remaining / X-RateLimit-Reset (seconds) headers. _(src: https://pixabay.com/api/docs/, 2026-09-02)_ |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no status page found (searched). — suggested src: https://pixabay.com/api/docs/ |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) expiry/rotation not documented. — suggested src: https://pixabay.com/api/docs/ |
| 10 | Interface lifecycle | 'New keys may be added at any time'; 'will do our best to notify before removing hash keys or adding required parameters' — no fixed notice, no headers. _(src: https://pixabay.com/api/docs/, 2026-09-02)_ |
| 11 | Data contract | Hash keys may be returned in random order; new keys anytime; totalHits max 500; documented sample response. _(src: https://pixabay.com/api/docs/, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only. _(src: https://pixabay.com/api/docs/, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Stock photos and videos
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://pixabay.com/api/` - Search Images: `GET /` - Search Videos: `GET /videos/` - Get Image Details: `GET /?id={id}`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Stock photo search and download - Service URL: `https://images.vps1.ocoron.com`
- **Notes** _(2026-06-02 entry)_: - Configured and active
- **Research notes** _(2026-09-02)_: Additive-only drift is explicitly documented — use non-strict unknown-key handling here.

### Unsplash

**Type:** ai-media · **Reach:** REST API (env key) · **Used by:** 2 project(s) — iterative_image_editor, spec:image-broker · **Env keys:** `UNSPLASH_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Demo 50 requests/hour; production 1,000 requests/hour per application; only api.unsplash.com JSON calls count (image CDN excluded). _(src: https://unsplash.com/documentation, 2026-09-02)_ |
| 2 | Behaviour AT the cap | Status code at cap not documented (community reports 403 'Rate Limit Exceeded' — unverified); headers X-Ratelimit-Limit / X-Ratelimit-Remaining. _(src: https://unsplash.com/documentation, 2026-09-02)_ |
| 3 | Concurrency & parallelism | UNKNOWN concurrency; per application access key. — suggested src: https://unsplash.com/documentation |
| 4 | Identity posture | Per application. Guidelines: apps must NOT make users register their own keys — share one key via proxy or ask for OAuth; 'Do not abuse the APIs'. api-terms page returned 401. _(src: https://help.unsplash.com/en/articles/2511245-unsplash-api-guidelines, 2026-09-02)_ |
| 5 | Failure & resume | GETs idempotent; must call photo.links.download_location on use; pagination 10/page default, max 30, Link header (first/prev/next/last), X-Total/X-Per-Page. _(src: https://unsplash.com/documentation, 2026-09-02)_ |
| 6 | Cost model | Free; hotlinking + attribution mandatory. _(src: https://unsplash.com/documentation, 2026-09-02)_ |
| 7 | Usage observability | X-Ratelimit-Limit and X-Ratelimit-Remaining headers on responses. _(src: https://unsplash.com/documentation, 2026-09-02)_ |
| 8 | Health signal | Statuspage: https://status.unsplash.com/api/v2/status.json returns JSON (fetched: 'All Systems Operational'). _(src: https://status.unsplash.com/api/v2/status.json, 2026-09-02)_ |
| 9 | Credential lifecycle | Access Key (Client-ID) + Secret; 401 'Invalid Access Token'; expiry/rotation UNKNOWN. _(src: https://unsplash.com/documentation, 2026-09-02)_ |
| 10 | Interface lifecycle | Accept-Version: v1; breaking changes announced in changelog ≥3 weeks ahead; Warning header returned on deprecated endpoints; undocumented fields may change without warning. _(src: https://unsplash.com/documentation, 2026-09-02)_ |
| 11 | Data contract | Public OpenAPI spec; summary vs full objects; errors array; conventional codes 400/401/403/404/500/503. _(src: https://unsplash.com/documentation, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only. _(src: https://unsplash.com/documentation, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Stock photos
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://api.unsplash.com` - Search Photos: `GET /search/photos` - Get Photo: `GET /photos/{id}` - Download Photo: `GET /photos/{id}/download`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Stock photo search and download - Service URL: `https://images.vps1.ocoron.com`
- **Notes** _(2026-06-02 entry)_: - Placeholder (not configured yet)
- **Research notes** _(2026-09-02)_: Production limit read via WebFetch (1,000/hr) — exa render omitted the number.

### Logo Dev

**Type:** ai-media · **Reach:** REST API (env key) · **Used by:** 1 project(s) — brand-identiy-creator · **Env keys:** `LOGO_DEV_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 6 | Cost model | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Grounding impossible: session has no web search/fetch tools; cannot cite any vendor URL.


## GPU & compute

### Runpod

**Type:** gpu · **Reach:** CLI `runpodctl` · **Used by:** 1 project(s) — iterative_image_editor · **Env keys:** `RUNPOD_*` · **Vendor doc:** `docs/reference/apis/runpod-api.md`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'runpod api limits quotas', fetched https://docs.runpod.io/api-reference, https://runpod.io/pricing |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'runpod rate limiting 429', fetched https://docs.runpod.io/api-reference |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'runpod concurrency parallelism', fetched https://docs.runpod.io/api-reference |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'runpod terms of service multiple accounts', fetched https://runpod.io/terms |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'runpod api idempotency retry', fetched https://docs.runpod.io/api-reference |
| 6 | Cost model | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Pay per second for GPU/pod usage; minimum 1 minute billing; free credits possibl' but its source is dead/unfetched (https://runpod.io/pricing); re-verify live |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'runpod usage api consumption', fetched https://docs.runpod.io/api-reference |
| 8 | Health signal | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Status page at https://status.runpod.io; no machine-readable API found.' but its source is dead/unfetched (https://status.runpod.io); re-verify live |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'runpod api key expiration', fetched https://docs.runpod.io/api-reference/authentication |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'runpod api versioning deprecation', fetched https://docs.runpod.io/api-reference |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'runpod api schema pagination', fetched https://docs.runpod.io/api-reference |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'runpod webhooks events', fetched https://docs.runpod.io/api-reference |
| — | **Resilience posture (58)** | provider failover chain per 76-gpu-workers § Provider Failover |

- **Research notes** _(2026-09-02)_: GPU cloud platform; documentation focuses on API endpoints, not explicit limits.

### Modal

**Type:** gpu · **Reach:** CLI `modal` · **Used by:** 1 project(s) — iterative_image_editor · **Env keys:** `MODAL_TOKEN_*` · **Vendor doc:** `docs/reference/apis/modal-api.md`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 6 | Cost model | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no web search/fetch tools available in this session |
| — | **Resilience posture (58)** | 76-gpu-workers § Provider Failover |

- **Research notes** _(2026-09-02)_: Grounding impossible: session has no web search/fetch tools; cannot cite any vendor URL.

### Vast

**Type:** gpu · **Reach:** CLI `vastai` · **Used by:** 1 project(s) — iterative_image_editor · **Env keys:** `VAST_*` · **Vendor doc:** `docs/reference/apis/vast-api.md`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Per-endpoint minimum interval between requests per identity (token + user + api_key + client IP); some endpoints add burst caps; numbers unpublished. _(src: https://docs.vast.ai/api-reference/rate-limits-and-errors, 2026-09-02)_ |
| 2 | Behaviour AT the cap | HTTP 429, often plain text 'API requests too frequent[: endpoint threshold=…]'; no Retry-After. _(src: https://docs.vast.ai/api-reference/rate-limits-and-errors, 2026-09-02)_ |
| 3 | Concurrency & parallelism | Per identity including client IP — scaling workers on one IP buys nothing. _(src: https://docs.vast.ai/api-reference/rate-limits-and-errors, 2026-09-02)_ |
| 4 | Identity posture | Per account, scoped keys; ToS (vast.ai/terms) UNKNOWN — not fetched. _(src: https://docs.vast.ai/guides/reference/api-keys.md, 2026-09-02)_ |
| 5 | Failure & resume | Error shape inconsistent ({success,error,msg} or msg only); create instance returns new_contract; 'poll trap': exited/unknown/offline never reaches running — destroy and retry. _(src: https://docs.vast.ai/api-reference/notifications.md, 2026-09-02)_ |
| 6 | Cost model | Marketplace, per-second billing; storage billed while stopped; bandwidth per byte; credits upfront; zero balance stops instances. _(src: https://docs.vast.ai/guides/instances/pricing.md, 2026-09-02)_ |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) billing section exists in API reference but not fetched this run. — suggested src: https://docs.vast.ai/api/ |
| 8 | Health signal | https://status.vast.ai/ exists (custom page, template placeholders in HTML); no JSON API referenced; /api/v2/status.json 404. _(src: https://status.vast.ai/, 2026-09-02)_ |
| 9 | Credential lifecycle | Key shown once; Reset = immediate hard cut 'no overlap window'; overlap only by creating a second key; delete -> 401; 90-day rotation advised. _(src: https://docs.vast.ai/guides/reference/api-keys.md, 2026-09-02)_ |
| 10 | Interface lifecycle | /api/v0 path; OpenAPI 1.0.0; deprecation channel UNKNOWN. _(src: https://docs.vast.ai/api-reference/notifications.md, 2026-09-02)_ |
| 11 | Data contract | gpu_ram MB in REST vs GB in CLI; onstart max 4048 chars; inconsistent error envelopes. _(src: https://docs.vast.ai/api-reference/notifications.md, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | Notification types with 'webhooks' channel (default_preferences {email,webhooks}); retry/signature UNKNOWN. _(src: https://docs.vast.ai/api-reference/notifications.md, 2026-09-02)_ |
| — | **Resilience posture (58)** | 76-gpu-workers § Provider Failover |

- **Research notes** _(2026-09-02)_: Base URL https://console.vast.ai/api/v0 (marketing page shows cloud.vast.ai).


## Translation

### DeepL

**Type:** ai-translate · **Reach:** REST API (env key) · **Used by:** 5 project(s) — fabrik, spec:translator, spec:wpf, transdoc, web-ecommerce-factory · **Env keys:** `DEEPL_*` · **Docs:** https://deepl.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Free: 500,000 chars/month; request body 128 KiB, headers 16 KiB; per-format document caps (docx 10 MB Free/100 MB Pro…); keys: 2 active (Free) / 25 (Pro); glossaries 1,000/account. _(src: https://developers.deepl.com/docs/resources/usage-limits, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 → exponential backoff (service adapts to load); 456 Quota exceeded (Free monthly cap / Pro Cost Control / key-level limit); 500 retry. _(src: https://developers.deepl.com/docs/best-practices/error-handling, 2026-09-02)_ |
| 3 | Concurrency & parallelism | No published concurrency; 429 is dynamic load-based. _(src: https://developers.deepl.com/docs/best-practices/error-handling, 2026-09-02)_ |
| 4 | Identity posture | Per subscription (optional per-key limits). Pro T&C §8.3.6: must not circumvent protection/authentication mechanisms; no clause limiting Free accounts per entity (WebFetch confirmed). _(src: https://www.deepl.com/en/pro-license, 2026-09-02)_ |
| 5 | Failure & resume | Retry 429/500 with backoff; translate is stateless (re-run re-billed); document translation async via document_id + document_key; no idempotency key documented. _(src: https://developers.deepl.com/docs/api-reference/document, 2026-09-02)_ |
| 6 | Cost model | Billed per source character (Unicode code points; translate+write summed); Free 500k/month; image translation beta unbilled. Current paid plan prices UNKNOWN — tried deepl.com/en/pro, /pro-api, /products/api (nav/marketing only). _(src: https://developers.deepl.com/docs/api-reference/usage-and-quota, 2026-09-02)_ |
| 7 | Usage observability | GET /v2/usage: character_count, character_limit (near-real-time, minutes); Pro adds per-product and per-key breakdown; 1e12 sentinel = no limit. _(src: https://developers.deepl.com/docs/api-reference/usage-and-quota, 2026-09-02)_ |
| 8 | Health signal | https://status.deepl.com custom page (fetched HTML: per-component 90-day availability incl. API EU/JP/US, incidents); no JSON feed confirmed (/api/v2/status.json failed). _(src: https://status.deepl.com/, 2026-09-02)_ |
| 9 | Credential lifecycle | Keys don't expire (no expiry documented); deactivation immediate + permanent; up to 25 Pro / 2 Free simultaneous keys → overlap rotation; key-level limits → 456 at 100%. Invalid-key status code not on fetched pages. _(src: https://developers.deepl.com/docs/admin/managing-api-keys, 2026-09-02)_ |
| 10 | Interface lifecycle | Path versions v2 (translate/usage) and v3 (glossaries); OpenAPI 3.13.0 embedded; no Deprecation/Sunset headers documented; api-versioning page 404. _(src: https://developers.deepl.com/docs/api-reference/usage-and-quota, 2026-09-02)_ |
| 11 | Data contract | /usage response shape differs by plan (Free/Pro Classic: 2 fields; Pro: per-product + per-key) — same endpoint, different schema. _(src: https://developers.deepl.com/docs/api-reference/usage-and-quota, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only. _(src: https://developers.deepl.com/docs/best-practices/error-handling, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Translation service (primary)
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://api-free.deepl.com/v2` - Translate Text: `POST /translate` - Usage: `GET /usage`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Text translation - Monthly Limit: 500,000 characters - Service URL: `https://translator.vps1.ocoron.com`
- **Notes** _(2026-06-02 entry)_: - Primary translation service - Better quality than Azure Translator
- **Research notes** _(2026-09-02)_: Third-party snippets say API Free/Pro were replaced by Developer/Growth plans July 2026 — not verified on an official page this run.

### Azure Translator

**Type:** ai-translate · **Reach:** REST API (env key) · **Used by:** 3 project(s) — spec:translator, transdoc, web-ecommerce-factory · **Env keys:** `AZURE_TRANSLATOR_*` · **Docs:** https://azure.microsoft.com/products/ai-services/ai-translator

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Per request 50,000 chars (× target langs); per hour by tier: F0 2M, S1/S2 40M, S3 120M, S4 200M chars (sliding window); custom models 3,600 chars/s; doc batch ≤40 MB/file, 1,000 files, 250 MB. _(src: https://learn.microsoft.com/en-us/azure/ai-services/translator/service-limits, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 request limits exceeded (also when quota consumed too fast); 403 free-trial quota used up; 408 custom model not ready (retry ~1 min); 503 retry. _(src: https://learn.microsoft.com/en-us/azure/ai-services/translator/text-translation/reference/status-response-codes, 2026-09-02)_ |
| 3 | Concurrency & parallelism | 'There are no limits on concurrent requests' — only chars/hour sliding window. _(src: https://learn.microsoft.com/en-us/azure/ai-services/translator/service-limits, 2026-09-02)_ |
| 4 | Identity posture | Per Translator resource/subscription tier; Azure lets you create additional subscriptions 'to avoid hitting subscription quota limits' (documented). Agreement text on account multiplicity not fetched → legal clause UNKNOWN. _(src: https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/create-subscription, 2026-09-02)_ |
| 5 | Failure & resume | Retry 429/408/500/503; translate stateless/idempotent; doc batch has job ids; X-RequestId/X-ClientTraceId for support; no idempotency key. _(src: https://learn.microsoft.com/en-us/azure/ai-services/translator/text-translation/reference/status-response-codes, 2026-09-02)_ |
| 6 | Cost model | F0: 2M chars/month free; S1 pay-as-you-go per million chars (amount rendered as '$-' behind region/currency selector); commitment tiers 250M/1B/4B chars; images per 1,000 (500-char increments). _(src: https://azure.microsoft.com/en-us/pricing/details/cognitive-services/translator/, 2026-09-02)_ |
| 7 | Usage observability | UNKNOWN direct usage endpoint — service-limits/pricing pages fetched name none (Azure Monitor metrics not fetched). — suggested src: https://learn.microsoft.com/en-us/azure/ai-services/translator/service-limits |
| 8 | Health signal | Azure Status RSS feed https://azure.status.microsoft/en-us/status/feed/ (fetched XML, live incident 2026-08-28) + Service Health per-subscription alerts. _(src: https://azure.status.microsoft/en-us/status/feed/, 2026-09-02)_ |
| 9 | Credential lifecycle | Two keys per resource; regenerating a key kills it immediately (401) → rotate one key at a time = overlap by design; Entra ID auth alternative. _(src: https://learn.microsoft.com/en-us/azure/ai-services/rotate-keys, 2026-09-02)_ |
| 10 | Interface lifecycle | api-version query versioning: Text v3 → 2026-06-06 GA (migration guide), Document 2026-03-01 GA; changes on What's New page; no Sunset header or notice period documented. _(src: https://learn.microsoft.com/en-us/azure/ai-services/translator/whats-new, 2026-09-02)_ |
| 11 | Data contract | JSON arrays per operation; X-RequestId response header; silent-change history UNKNOWN. _(src: https://learn.microsoft.com/en-us/azure/ai-services/translator/text-translation/reference/rest-api-guide, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only. _(src: https://learn.microsoft.com/en-us/azure/ai-services/translator/text-translation/reference/rest-api-guide, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Translation service (fallback)
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://api.cognitive.microsofttranslator.com` - Translate Text: `POST /translate` - Detect Language: `POST /detect` - Document Translation: `POST /batches`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Fallback translation service - Region: `westeurope`
- **Notes** _(2026-06-02 entry)_: - Fallback to DeepL - Supports document translation
- **Research notes** _(2026-09-02)_: Product rebranded 'Azure Translator in Foundry Tools'; v3 → 2026-06-06 migration is a live interface-lifecycle item.

### translator (catalog placeholder)

**Type:** ai-translate · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found)

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | freemium _(catalog `cost`, refreshed daily)_ |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |


## Search, scraping, proxies & captcha

### Exa

**Type:** search · **Reach:** REST API (env key) · MCP `exa` (agent-time only) · **Used by:** 3 project(s) — apidoccreator, brand-identiy-creator, fabrik · **Env keys:** `EXA_*` · **Docs:** https://exa.ai

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | paid _(catalog `cost`, refreshed daily)_ |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### Brave

**Type:** search · **Reach:** REST API (env key) · MCP `brave-search` (agent-time only) · **Used by:** 3 project(s) — brand-identiy-creator, fabrik, seo · **Env keys:** `BRAVE_*` · **Docs:** https://brave.com/search/api

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://brave.com/search/api — suggested src: https://brave.com/search/api |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://brave.com/search/api — suggested src: https://brave.com/search/api |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://brave.com/search/api — suggested src: https://brave.com/search/api |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://brave.com/search/api — suggested src: https://brave.com/search/api |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://brave.com/search/api — suggested src: https://brave.com/search/api |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Freemium (per caller's note); tier pricing not retrieved — verify: https://brave.com/search/api |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://brave.com/search/api — suggested src: https://brave.com/search/api |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://brave.com/search/api — suggested src: https://brave.com/search/api |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://brave.com/search/api — suggested src: https://brave.com/search/api |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://brave.com/search/api — suggested src: https://brave.com/search/api |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://brave.com/search/api — suggested src: https://brave.com/search/api |
| 12 | Push delivery (webhooks/streams) | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Not applicable — Brave Search API is request/response only — verify: https://brave.com/search/api |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Brave Search has tiered Data for Search plans (Free/Pro/Pro+); live fetch not performed in this run.

### Firecrawl

**Type:** scrape · **Reach:** REST API (env key) · MCP `firecrawl` (agent-time only) · **Used by:** 2 project(s) — brand-identiy-creator, fabrik · **Env keys:** `FIRECRAWL_*` · **Docs:** https://firecrawl.dev

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched for firecrawl rate limits, fetched https://firecrawl.dev/terms and https://firecrawl.dev/blog |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched for firecrawl rate limit behavior, fetched https://firecrawl.dev/terms |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched for firecrawl concurrency, fetched https://firecrawl.dev/terms |
| 4 | Identity posture | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Account-based; ToS clause 2.3 restricts sharing accounts. Scoped per API key. ht' but its source is dead/unfetched (https://firecrawl.dev/terms); re-verify live |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched for firecrawl retry idempotency, fetched https://firecrawl.dev/terms |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Pay-per-usage, based on pages scraped. Free tier: 100 pages/month. Spike from high-volume scraping. https://firecrawl.dev/pricing — verify: https://firecrawl.dev/pricing |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched for firecrawl usage API endpoint, fetched https://firecrawl.dev/docs |
| 8 | Health signal | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'No public status page or machine-readable status API found.' but its source is dead/unfetched (no url); re-verify live |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched for firecrawl API key expiry rotation, fetched https://firecrawl.dev/docs |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched for firecrawl API versioning deprecation, fetched https://firecrawl.dev/docs |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched for firecrawl data schema pagination, fetched https://firecrawl.dev/docs |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Does not appear to be a push/webhook service; focused on request-response scrapi' but its source is dead/unfetched (no url); re-verify live |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Scraping service; many details not documented in public pages.

### Apify

**Type:** scrape · **Reach:** REST API (env key) · **Used by:** 4 project(s) — proxy, spec:proxy, trade-intelligence, youtube · **Env keys:** `APIFY_*` · **Docs:** https://apify.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Global 250,000 req/min per user (per IP unauthenticated); per resource 60 rps (KV records 200, runs/dataset ops 400); concurrent Actor runs 25/32/128/256 by plan; $5 free usage/month. _(src: https://docs.apify.com/api/v2, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 {error:{type:'rate-limit-exceeded'}}; backoff from 500 ms random(DELAY,2×DELAY) doubling; Free plan blocked until next cycle when prepaid usage exhausted; paid plans overage billed. _(src: https://docs.apify.com/api/v2, 2026-09-02)_ |
| 3 | Concurrency & parallelism | Per user + per resource rps; max concurrent Actor runs per plan (Free 25, Starter 32, Scale 128, Business 256; add-on $5/run). _(src: https://docs.apify.com/platform/limits, 2026-09-02)_ |
| 4 | Identity posture | Per user/organization account (GTC §4.1 Personal Account; org tokens separate). No multi-account or circumvention clause in fetched GTC sections → UNKNOWN. _(src: https://docs.apify.com/legal/general-terms-and-conditions, 2026-09-02)_ |
| 5 | Failure & resume | Retry 429/5xx (official clients do backoff); sync run waits 300 s; resume via run id + dataset offset/limit or exclusiveStartKey; idempotency key UNKNOWN. _(src: https://docs.apify.com/api/v2, 2026-09-02)_ |
| 6 | Cost model | Plans $0/$19/$199/$999 incl. prepaid usage; CU (1 GB·h) $0.20→$0.13; residential proxy $8→$7/GB; store Actors pay-per-event or pay-per-usage; unused credits don't roll over. _(src: https://apify.com/pricing, 2026-09-02)_ |
| 7 | Usage observability | GET /v2/users/me/usage/monthly (cycle, per-service quantities, USD before/after discount, daily breakdown). _(src: https://docs.apify.com/api/v2/users-me-usage-monthly-get, 2026-09-02)_ |
| 8 | Health signal | Statuspage: https://status.apify.com/api/v2/status.json returns JSON (fetched: 'All Systems Operational'). _(src: https://status.apify.com/api/v2/status.json, 2026-09-02)_ |
| 9 | Credential lifecycle | Tokens support optional expiration date; rotation can keep old token alive 24h (overlap); scoped tokens; compromised tokens flagged in UI; 401/403 on missing/invalid. _(src: https://docs.apify.com/platform/integrations/api, 2026-09-02)_ |
| 10 | Interface lifecycle | API v2 by path; OpenAPI build-dated (v2-2026-08-31); legacy /v2/acts/ prefix kept working; max `limit` may change (don't hardcode); no Sunset header documented. _(src: https://docs.apify.com/api/v2, 2026-09-02)_ |
| 11 | Data contract | {data:{}} envelope with documented exceptions (dataset items, KV record); pagination offset/limit or exclusiveStartKey; errors {error:{type,message}}. _(src: https://docs.apify.com/api/v2, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | Webhooks: POST JSON, need 2xx; 11 retries exponential (~1 min → ~32 h); 2-min timeout; may fire more than once (be idempotent); auth via secret in URL/headers template, static source IPs; no signature scheme; no delivery-list endpoint documented. _(src: https://docs.apify.com/platform/integrations/webhooks/actions, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Web scraping platform
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://api.apify.com/v2` - Run Actor: `POST /actor-tasks/{taskId}/runs` - Get Results: `GET /actor-tasks/{taskId}/runs/{runId}/dataset/items`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: YouTube Comments scraping (fallback)
- **Notes** _(2026-06-02 entry)_: - YouTube Comments API fallback
- **Research notes** _(2026-09-02)_: Strong grounding; agentic payments (x402/Skyfire) now an alternative auth path.

### Dataforseo

**Type:** scrape · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found) · **Docs:** https://dataforseo.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | paid _(catalog `cost`, refreshed daily)_ |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### Scrapingdog

**Type:** scrape · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found) · **Docs:** https://scrapingdog.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Plan-based limits (e.g., 50k credits/month). Credits reset monthly. — verify: https://scrapingdog.com/pricing |
| 2 | Behaviour AT the cap | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Returns 429 when credits exhausted; requires plan upgrade or next reset. — verify: https://scrapingdog.com/documentation |
| 3 | Concurrency & parallelism | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Concurrent requests limited by plan (e.g., 5 concurrent). — verify: https://scrapingdog.com/documentation |
| 4 | Identity posture | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Per API key; ToS prohibit multiple accounts to evade limits (clause 4). — verify: https://scrapingdog.com/terms |
| 5 | Failure & resume | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Retry on failure; idempotent GET requests; no built-in checkpointing. — verify: https://scrapingdog.com/documentation |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Pay-per-credit; 1000 free credits/month; spikes from high-volume scraping. — verify: https://scrapingdog.com/pricing |
| 7 | Usage observability | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Dashboard shows credit usage; no API endpoint documented.' but its source is dead/unfetched (https://scrapingdog.com/dashboard); re-verify live |
| 8 | Health signal | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'No status page found.' but its source is dead/unfetched (no url); re-verify live |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'API keys do not expire; can be rotated manually in dashboard.' but its source is dead/unfetched (https://scrapingdog.com/dashboard); re-verify live |
| 10 | Interface lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): API version not evident in URLs; changes announced via blog/dashboard. — verify: https://scrapingdog.com/blog |
| 11 | Data contract | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Returns HTML/JSON; pagination handled via `page` parameter; no deletion signals. — verify: https://scrapingdog.com/documentation |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'scrapingdog webhooks', fetched https://scrapingdog.com/documentation |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Web scraping API; credit-based system with concurrent request limits.

### Brightdata

**Type:** acquire · **Reach:** REST API (env key) · **Used by:** 1 project(s) — trade-intelligence · **Env keys:** `BRIGHTDATA_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Usage caps depend on plan: Pay-as-you-go unlimited; Starter (1M rows/month); Adv' but its source is dead/unfetched (https://brightdata.com/products/usage); re-verify live |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Requests over plan quota return 429 with Retry-After. Overage billing available ' but its source is dead/unfetched (https://brightdata.com/docs/errors#429-too-many-requests); re-verify live |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Concurrency limits vary by plan and target site. Scoped per account/IP pool. Sel' but its source is dead/unfetched (https://brightdata.com/docs/rate-limits); re-verify live |
| 4 | Identity posture | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Per account key. ToS prohibits creating multiple accounts to circumvent limits (' but its source is dead/unfetched (https://brightdata.com/terms-of-service#clause-2-3); re-verify live |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep 2026-09-02 suggested '429, 5xx retryable. Idempotency via job IDs. Smallest resumable unit is a single' but its source is dead/unfetched (https://brightdata.com/docs/api-errors); re-verify live |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Unit: rows of extracted data or bandwidth (GB). Minimum increment: 1 row/0.1 GB. Free trial available. Spikes from high-volume targets. — verify: https://brightdata.com/pricing |
| 7 | Usage observability | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Dashboard API endpoint /api/usage provides current consumption, remaining quota.' but its source is dead/unfetched (https://brightdata.com/docs/api-dashboard#usage); re-verify live |
| 8 | Health signal | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Status page: https://status.brightdata.com. Has machine-readable JSON API at /ap' but its source is dead/unfetched (https://status.brightdata.com/api/v2/status.json); re-verify live |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'API keys do not auto-expire; manual rotation. Token revocation immediate. Expire' but its source is dead/unfetched (https://brightdata.com/docs/api-authentication#key-management); re-verify live |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'API versioning: path /api/v1/, /api/v2/. Deprecation announced via email/dashboa' but its source is dead/unfetched (https://brightdata.com/docs/api-changelog); re-verify live |
| 11 | Data contract | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Documented schema per dataset. Pagination with limit/offset. Deletion via API re' but its source is dead/unfetched (https://brightdata.com/docs/api-datasets); re-verify live |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Webhooks for job completion: at-least-once, retry 5 times with backoff. Event ID' but its source is dead/unfetched (https://brightdata.com/docs/webhooks); re-verify live |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Recent change: Pay-as-you-go plan now includes 5GB free monthly proxy bandwidth.

### Iproyal

**Type:** proxy · **Reach:** REST API (env key) · **Used by:** 1 project(s) — spec:youtube · **Env keys:** `IPROYAL_*` · **Docs:** https://iproyal.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Residential metered in GB; Web Unblocker 200 active connections; API request limits not published. _(src: https://docs.iproyal.com/overview.md?ask=What%20are%20the%20API%20rate%20limits%2C%20concurrent%20connection%20or%20thread%20limits%20per%20account%2C%20how%20do%20I%20check%20remaining%20traffic%20balance%20via%20API%2C%20do%20API%20tokens%20expire%20and%20how%20are%20they%20rotated%2C%20and%20what%20response%20codes%20indicate%20traffic%20exhausted%20or%20auth%20failure%3F, 2026-09-02)_ |
| 2 | Behaviour AT the cap | Proxy: 503 No Exits Available, 504 Exit Connection Failed, 500 internal; Web Unblocker 429. _(src: https://docs.iproyal.com/proxies/residential/proxy/making-requests/response-codes.md, 2026-09-02)_ |
| 3 | Concurrency & parallelism | Residential concurrency not documented — UNKNOWN; Web Unblocker 200 concurrent. _(src: https://docs.iproyal.com/llms.txt, 2026-09-02)_ |
| 4 | Identity posture | ToS v8 (2026-06-30) 2.5: one identity document verifies one account; 2.12: account strictly own use; sub-users are the sanctioned split. _(src: https://iproyal.com/terms-of-service/, 2026-09-02)_ |
| 5 | Failure & resume | 500/504 'retry the request'; proxy idempotency is yours; sticky sessions reset via DELETE /v1/sessions. _(src: https://docs.iproyal.com/proxies/residential/api/sessions.md, 2026-09-02)_ |
| 6 | Cost model | Pay-as-you-go traffic or subscription; fees non-refundable (6.9); $/GB UNKNOWN — not fetched. _(src: https://iproyal.com/terms-of-service/, 2026-09-02)_ |
| 7 | Usage observability | GET https://resi-api.iproyal.com/v1/me (available traffic, subuser count); sub-user traffic_available/traffic_used. _(src: https://docs.iproyal.com/proxies/residential/api/user.md, 2026-09-02)_ |
| 8 | Health signal | Statuspage JSON: 'minor — Minor Service Outage' (2026-09-02). _(src: https://status.iproyal.com/api/v2/status.json, 2026-09-02)_ |
| 9 | Credential lifecycle | Bearer API token; expiry/rotation not documented — UNKNOWN (GitBook ask). _(src: https://docs.iproyal.com/proxies/residential/api/sub-users.md, 2026-09-02)_ |
| 10 | Interface lifecycle | /v1 on resi-api; in-doc deprecation only (legacy `id` 'will be removed in the future'); no headers. _(src: https://docs.iproyal.com/proxies/residential/api/sub-users.md, 2026-09-02)_ |
| 11 | Data contract | SubuserResource {id(legacy),hash,username,password,traffic_available,traffic_used}; GB floats. _(src: https://docs.iproyal.com/proxies/residential/api/sub-users.md, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only. _(src: https://docs.iproyal.com/llms.txt, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Docs are GitBook with an `?ask=` endpoint — usable for future grounding.

### Webshare.io

**Type:** proxy · **Reach:** REST API (env key) · **Used by:** 4 project(s) — fabrik, proxy, spec:proxy, youtube · **Env keys:** `WEBSHARE_*` · **Docs:** https://webshare.io

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) tried https://webshare.io but fetch blocked; docs subdomain not reached — suggested src: https://webshare.io |
| 2 | Behaviour AT the cap | UNKNOWN — suggested src: https://webshare.io |
| 3 | Concurrency & parallelism | UNKNOWN — suggested src: https://webshare.io |
| 4 | Identity posture | UNKNOWN — suggested src: https://webshare.io |
| 5 | Failure & resume | UNKNOWN — suggested src: https://webshare.io |
| 6 | Cost model | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Proxies billed per GB bandwidth used; plans tiered monthly' but its source is dead/unfetched (https://webshare.io/pricing); re-verify live |
| 7 | Usage observability | UNKNOWN — suggested src: https://webshare.io |
| 8 | Health signal | UNKNOWN — suggested src: https://webshare.io |
| 9 | Credential lifecycle | UNKNOWN — suggested src: https://webshare.io |
| 10 | Interface lifecycle | UNKNOWN — suggested src: https://webshare.io |
| 11 | Data contract | UNKNOWN — suggested src: https://webshare.io |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — suggested src: https://webshare.io |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Rotating residential proxies
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://api.webshare.io/api` - List Proxies: `GET /v2/proxy/list` - Get Usage: `GET /v2/proxy/usage`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Web scraping, bypass geo-restrictions - Service URL: `https://proxy.vps1.ocoron.com`
- **Notes** _(2026-06-02 entry)_: - Rotating residential proxies - Better for scraping than datacenter proxies
- **Research notes** _(2026-09-02)_: webshare.io docs/API endpoints blocked by anti-bot on fetch; only homepage marketing reachable.

### Anti-Captcha

**Type:** captcha · **Reach:** REST API (env key) · **Used by:** 1 project(s) — fabrik · **Env keys:** `ANTICAPTCHA_*` · **Docs:** https://anti-captcha.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | No request-rate cap documented; 'free capacity 1000/min' per type; getBalance max once per 30 s; repeated 'nonsense' requests -> IP/subnet bans. _(src: https://anti-captcha.com/apidoc/errors, 2026-09-02)_ |
| 2 | Behaviour AT the cap | errorId>0 in HTTP 200 body: ERROR_NO_SLOT_AVAILABLE (2) raise bid/retry later; ERROR_ZERO_BALANCE (10); ERROR_IP_BLOCKED (21). _(src: https://anti-captcha.com/apidoc/errors, 2026-09-02)_ |
| 3 | Concurrency & parallelism | 'supports unlimited parallel processing threads'; worker pool 1000 busy / 1200 idle. _(src: https://anti-captcha.com/, 2026-09-02)_ |
| 4 | Identity posture | Per account clientKey, optional IP allowlist (ERROR_IP_NOT_ALLOWED). Multi-account ban text ('considered fraud… termination') exists only in search snippet — NEEDS-RAW-FETCH https://anti-captcha.com/faq/175_account_questions (JS-rendered, both fetch arms return landing page). _(src: https://anti-captcha.com/apidoc/errors, 2026-09-02)_ |
| 5 | Failure & resume | createTask non-idempotent (charged even if ERROR_CAPTCHA_UNSOLVABLE); poll getTaskResult status processing/ready; result kept 60 s after completion (ERROR_NO_SUCH_CAPCHA_ID); proxy errors retryable. _(src: https://anti-captcha.com/apidoc/methods/getTaskResult, 2026-09-02)_ |
| 6 | Cost model | Per 1000: images $0.5–0.7, reCAPTCHA v2 $0.95–2, v3 $1–2, Enterprise $5, Turnstile $2, GeeTest $1.8, Arkose $3; volume discounts; optional subscription credits. _(src: https://anti-captcha.com/, 2026-09-02)_ |
| 7 | Usage observability | getBalance (USD + captchaCredits), getSpendingStats (24 h volume/money), per-task cost in getTaskResult. _(src: https://anti-captcha.com/apidoc/methods/getSpendingStats, 2026-09-02)_ |
| 8 | Health signal | getQueueStats (waiting/load/bid/speed per queue, cached 10 s) is the live capacity signal; no status page found — UNKNOWN (tried search). _(src: https://anti-captcha.com/apidoc/methods/getQueueStats, 2026-09-02)_ |
| 9 | Credential lifecycle | Account key; no expiry documented; invalid key -> ERROR_KEY_DOES_NOT_EXIST (1) inside HTTP 200; rotation overlap UNKNOWN. _(src: https://anti-captcha.com/apidoc/errors, 2026-09-02)_ |
| 10 | Interface lifecycle | Unversioned URLs (api.anti-captcha.com/createTask); deprecations noted inline (languagePool 'moved to ImageToTextTask'); no headers; channel UNKNOWN. _(src: https://anti-captcha.com/apidoc/methods/createTask, 2026-09-02)_ |
| 11 | Data contract | Envelope {errorId,errorCode,errorDescription,…}; errors ride HTTP 200; solution object differs per task type; cost returned as string. _(src: https://anti-captcha.com/apidoc/methods/getTaskResult, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | Optional callbackUrl: AJAX POST identical to getTaskResult; retry/signature/list UNKNOWN — polling is canonical. _(src: https://anti-captcha.com/apidoc/methods/createTask, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: CAPTCHA solving service
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://api.anti-captcha.com` - Create Task: `POST /createTask` - Get Task Result: `POST /getTaskResult`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: CAPTCHA solving for scraping - Service URL: `https://captcha.vps1.ocoron.com`
- **Notes** _(2026-06-02 entry)_: - Supports reCAPTCHA, hCaptcha, Turnstile, image CAPTCHAs
- **Research notes** _(2026-09-02)_: All errors are HTTP 200 + errorId — strict-parse the envelope, never trust status code alone.

### captcha (catalog placeholder)

**Type:** captcha · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found)

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'captcha API limits quota', fetched generic CAPTCHA provider pages, no specific vendor 'captcha' found. |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'captcha API rate limit 429', fetched hcaptcha, recaptcha docs, could not match to vendor 'captcha'. |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'captcha concurrency', fetched anti-captcha, 2captcha docs, cannot ground for generic 'captcha'. |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'captcha terms of service multiple accounts', no single vendor 'captcha' documentation found. |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'captcha API retry idempotency', fetched multiple provider docs, cannot determine for generic vendor. |
| 6 | Cost model | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'captcha pricing free tier spike', results fragmented across many providers. |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'captcha API usage endpoint', could not identify specific vendor 'captcha'. |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'captcha status page', found status pages for specific providers but not generic 'captcha'. |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'captcha API key expiry', no documentation for vendor 'captcha' found. |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'captcha API versioning deprecation', cannot ground without specific vendor. |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'captcha API schema pagination', vendor 'captcha' too generic to ground. |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'captcha webhooks retry schedule', no single vendor 'captcha' documentation found. |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Vendor 'captcha' is ambiguous—could refer to hCaptcha, reCAPTCHA, or solving service.

### RapidAPI

**Type:** search · **Reach:** REST API (env key) · **Used by:** 4 project(s) — calendar-orchestration-engine, site-provisioner, spec:calendar-orchestration-engine, youtube · **Env keys:** `RAPIDAPI_*`, `RAPIDAPI_PROXY_*` · **Docs:** https://rapidapi.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'rapidapi hub rate limits per provider' — suggested src: https://docs.rapidapi.com/ |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'rapidapi 429 overage billing' — suggested src: https://docs.rapidapi.com/ |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'rapidapi concurrent requests' — suggested src: https://docs.rapidapi.com/ |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'rapidapi ToS multiple accounts' — suggested src: https://docs.rapidapi.com/terms |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'rapidapi proxy retry idempotency' — suggested src: https://docs.rapidapi.com/ |
| 6 | Cost model | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'rapidapi pricing per call freemium' — suggested src: https://docs.rapidapi.com/docs/pricing |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'rapidapi usage analytics endpoint' — suggested src: https://docs.rapidapi.com/ |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'rapidapi status page' — suggested src: https://status.rapidapi.com/ |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'rapidapi API key rotation' — suggested src: https://docs.rapidapi.com/ |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'rapidapi API versioning deprecation' — suggested src: https://docs.rapidapi.com/ |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'rapidapi proxy pagination' — suggested src: https://docs.rapidapi.com/ |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'rapidapi webhooks delivery' — suggested src: https://docs.rapidapi.com/ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: API marketplace
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://{host}/api` - YouTube Download: `POST /download`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: YouTube video/audio download
- **Notes** _(2026-06-02 entry)_: - YouTube video/audio downloader
- **Research notes** _(2026-09-02)_: RapidAPI is a hub; many fields are per-provider not platform-wide — lacks web tools to verify.

### Browserless

**Type:** infra-platform · **Reach:** self-hosted container on the `fabrik` network · REST API (env key) · MCP `playwright / chrome-devtools (agent-time)` (agent-time only) · **Runs on:** vps1 (`docker ps` 2026-09-02) · **Used by:** 2 project(s) — fabrik, fabrik-claim-validator · **Env keys:** `BROWSERLESS_*` · **Docs:** https://browserless.io

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — container memory limit **2g** (docs/infrastructure/vps-complete-inventory.md:599); connection/pool caps are the service's own config |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Retryable: 429, 502-504. Idempotent via session IDs. Smallest resumable unit is ' but its source is dead/unfetched (https://docs.browserless.io/docs/retries.html); re-verify live |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Status page: https://status.browserless.io. No machine-readable status API documented. — verify: https://status.browserless.io |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): WebSocket/HTTP API documented. Pagination via start/end timestamps for sessions. Schema stable. — verify: https://docs.browserless.io/docs/api.html |
| 12 | Push delivery (webhooks/streams) | n/a — no webhooks; a fleet service pushes nothing (alerts flow via Prometheus → Alertmanager → Apprise/Telegram) |
| — | **Resilience posture (58)** | self-hosted `:3000`; timeout 30s; fallback = cached/fallback content (58:430); `web-scrape` uses it for JS-rendered pages (fabrik-lib/web-scrape README) |

- **Purpose** _(2026-06-02 entry)_: Headless Chrome browser service
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Headless browser automation - Domain: `https://browser.vps1.ocoron.com` - Port: 3000
- **Notes** _(2026-06-02 entry)_: - Self-hosted on VPS - amd64 compatible
- **Research notes** _(2026-09-02)_: Self-hosted version 12.0 added ARM64 support.

### Gotenberg

**Type:** infra-platform · **Reach:** self-hosted container on the `fabrik` network · REST API (env key) · **Runs on:** vps1 (`docker ps` 2026-09-02) · **Used by:** 0 project(s) — fleet service, no per-project key · **Docs:** https://gotenberg.dev

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-hosted — one Chromium handles up to 6 parallel operations per instance; API_TIMEOUT 30 s; API_BODY_LIMIT configurable. _(src: https://gotenberg.dev/docs/configuration, 2026-09-02)_ |
| 2 | Behaviour AT the cap | Queue fills until timeout or max capacity -> request 'terminated prematurely'; 503 Service Unavailable on routes. _(src: https://gotenberg.dev/docs/configuration, 2026-09-02)_ |
| 3 | Concurrency & parallelism | 6 parallel Chromium ops per instance; scale by adding instances. _(src: https://gotenberg.dev/docs/configuration, 2026-09-02)_ |
| 4 | Identity posture | n/a self-hosted. _(src: https://gotenberg.dev/docs/configuration, 2026-09-02)_ |
| 5 | Failure & resume | 503 retryable; 400 client input; 403 outbound host denied; 499 client cancel; stateless idempotent conversions; Gotenberg-Trace correlation header. _(src: https://github.com/gotenberg/gotenberg/releases, 2026-09-02)_ |
| 6 | Cost model | Free OSS; cost = compute. _(src: https://github.com/gotenberg/gotenberg/releases, 2026-09-02)_ |
| 7 | Usage observability | GET /prometheus/metrics (queue/request metrics); no quota. _(src: https://gotenberg.dev/docs/routes, 2026-09-02)_ |
| 8 | Health signal | GET/HEAD /health -> 200 {status:'up',details:{chromium,…}} or 503. _(src: https://gotenberg.dev/docs/routes, 2026-09-02)_ |
| 9 | Credential lifecycle | Optional basic auth or OIDC bearer (8.36.0, mutually exclusive); credentials are yours. _(src: https://gotenberg.dev/docs/configuration, 2026-09-02)_ |
| 10 | Interface lifecycle | SemVer image gotenberg/gotenberg:8 (8.36.0 on 2026-08-14); flag deprecations announced inline (8.29.0, 8.32.0); GitHub releases. _(src: https://github.com/gotenberg/gotenberg/releases, 2026-09-02)_ |
| 11 | Data contract | multipart/form-data in, PDF out with Content-Disposition + Gotenberg-Trace; GET /version plain text. _(src: https://gotenberg.dev/docs/routes, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | Webhook mode: immediate 204; Gotenberg-Webhook-Url/-Error-Url; POST/PATCH/PUT; extra headers JSON; retry policy UNKNOWN (webhook module config not fetched). _(src: https://gotenberg.dev/docs/webhook, 2026-09-02)_ |
| — | **Resilience posture (58)** | self-hosted `:3000` on `fabrik` net; timeout 60s (generation is slow); fallback = 'PDF unavailable, retry later' (58:429) |

- **Purpose** _(2026-06-02 entry)_: PDF generation service
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: HTML to PDF conversion - Domain: `https://pdf.vps1.ocoron.com` - Port: 3003
- **Notes** _(2026-06-02 entry)_: - Self-hosted on VPS - amd64 compatible
- **Research notes** _(2026-09-02)_: 8.31–8.32 changed outbound URL filtering defaults; 8.35 stopped inheriting HTTP_PROXY implicitly.

### LinkedIn (scrape target)

**Type:** scrape-target · **Reach:** public pages via `fabrik-lib/web-scrape` (ToS-prohibited; no API key held) · **Used by:** 3 project(s) — brand-identiy-creator, fabrik, tojlo-mail (code call sites) · **Hosts:** `linkedin.com`, `www.linkedin.com` · **Env keys:** none in the fleet today (reached without a key; the posture row names the knob a consumer would add) · **Docs:** https://learn.microsoft.com/en-us/linkedin/

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | SCRAPE: robots.txt header: 'The use of robots or other automated means to access LinkedIn without the express permission of LinkedIn is strictly prohibited' (whitelist via whitelist-crawl@linkedin.com, bound by /legal/crawling-terms). Only `LinkedInBot` gets `Allow: /`; whitelisted engines (Googlebot, Bingbot, Applebot, …) get path Disallows incl. `/profile/`, `/search*`, `/voyager/api`, `/jobs-guest/`, `/organization-guest/`, `/authwall`, `/api/jobPostings/jobs*`; 28 agents in the fetched window get blanket `Disallow: /` (GPTBot, ClaudeBot, anthropic-ai, CCBot, Scrapy, Diffbot, PerplexityBot, Meta-ExternalAgent, …). The raw fetch returned 122 KB and cut mid-line at `User-agent: Poseidon Research Crawler` — the `User-agent: *` catch-all tail was NOT reached this run (NEEDS-RAW-FETCH: `curl -s https://www.linkedin.com/robots.txt \| tail -5`). API: limits are DAILY counts, two kinds — Application (per app/day) + Member (per member per app/day), reset midnight UTC; 'Standard rate limits are not published in documentation' — visible only in Developer Portal → app → Analytics; Community Management Dev-tier defaults 500 req/app, 100 req/member (raised from 100/10). _(src: https://learn.microsoft.com/en-us/linkedin/shared/api-guide/concepts/rate-limits, 2026-09-02)_ |
| 2 | Behaviour AT the cap | SCRAPE: non-browser UA / datacenter IP / burst → non-standard HTTP 999 (no reason phrase, no Retry-After, ~1.6 KB HTML body; historical body text 'unusual traffic from your network connection'), or a 200 fragment that JS-redirects to `/authwall`; block is 'automatic and temporary', lifts when network activity normalises. Logged-in accounts 'viewing an unusually large number of profiles in a short period of time' get profile-viewing 'temporarily restricted' and LinkedIn 'reserves the right to restrict, suspend, or terminate your account' (https://www.linkedin.com/help/recruiter/answer/a1393432). API: 429 with message 'Resource level throttle limit for calls to this resource is reached'; 429 also emitted 'as part of infrastructure protection' and 'will return to normal automatically'; no rate-limit / Retry-After headers documented; over-quota relief only via partner program. _(src: https://learn.microsoft.com/en-us/linkedin/shared/api-guide/concepts/error-handling, 2026-09-02)_ |
| 3 | Concurrency & parallelism | API: no in-flight/concurrency cap documented — throttles are daily buckets only; write contention surfaces as 409 `CONFLICT` 'Write Conflict' and 412 `PRECONDITION_FAILED`; batch writes return a per-key `results{}` / `errors{}` map (partial success = 204 per key + errors per key). SCRAPE: no published safe rate; detection is per-IP/session behaviour ('There is no universal safe request rate for LinkedIn scraping') — parallel fetches from one egress IP accelerate the 999 block. _(src: https://learn.microsoft.com/en-us/linkedin/marketing/error-responses, 2026-09-02)_ |
| 4 | Identity posture | User Agreement (effective 2025-11-03) §8.2 forbids to 'Develop, support or use software, devices, scripts, robots or any other means or processes (such as crawlers, browser plugins and add-ons or any other technology) to scrape or copy the Services' and to 'Use bots or other unauthorized automated methods to access the Services'. Crawling Terms (eff. 2017-05-25): whitelist use 'confined solely to search indexing for display in a publicly available search engine', 'your own true IP address and useragent', no bulk transfer. Legal: hiQ v. LinkedIn — 9th Cir. 2022-04-18 held scraping public pages is not a CFAA violation, BUT N.D. Cal. 2022-11-04 summary judgment found hiQ breached the User Agreement (automated scraping + fake 'turker' accounts), and on 2022-12-08 the court entered a Consent Judgment + Permanent Injunction: $500,000 against hiQ, barred from 'Scraping or accessing … whether logged in to a LinkedIn account or not', must 'delete any and all software or code' and data (https://newmedialaw.proskauer.com/2022/12/08/hiq-and-linkedin-reach-proposed-settlement-in-landmark-scraping-case/). Net: contract/ToS is the enforced route. API Terms (eff. 2023-01-13): scraping 'outside the APIs' banned; no 'creating multiple Applications for identical, or largely similar, usage' to dodge limits; Content stored only 'for the duration necessary'; LinkedIn may suspend if 'you have not recently used any such API'. _(src: https://www.linkedin.com/legal/user-agreement, 2026-09-02)_ |
| 5 | Failure & resume | SCRAPE: failure states = 999 / 403 / 429 / `/authwall` redirect / checkpoint-CAPTCHA / 200 with EMPTY schema.org `Person` ld+json on logged-out fetches; no Retry-After on 999; smallest resumable unit = one URL, resumed only after the block lifts or from a different network — retry-harder is what escalates a temporary IP block to an account restriction. API: offset pagination `start`/`count` (default count 10; end-of-data = fewer `elements` than `count`, no cursor/total); expired token → 401 'Expired access token'; expired/revoked refresh → 400 'The provided authorization grant or refresh token is invalid, expired or revoked' → full re-auth; 504 guidance: 'proper error handling logic, such as caching and retry patterns'; 500 tickets need `x-li-uuid`/`x-li-fabric`/`x-li-request-id`. _(src: https://learn.microsoft.com/en-us/linkedin/shared/api-guide/concepts/pagination, 2026-09-02)_ |
| 6 | Cost model | SCRAPE: $0 vendor-side; the cost is legal exposure (§4) + egress/proxy + ban. API: no fee stated on any fetched page — Open Permissions (`profile`, `email`, `w_member_social`) are self-serve 'available to all developers without special approval'; Advertising/Community Management APIs need LinkedIn approval (Development tier → Standard tier upgrade with screencast demo; Community Management 'only available to registered legal organizations for commercial use cases only'); `r_member_social` (Member Post Management) is CLOSED — 'not accepting access requests at this time due to resource constraints'; Compliance permissions closed. Price beyond 'no fee stated' UNKNOWN — tried getting-access, community-management-overview, increasing-access. _(src: https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access, 2026-09-02)_ |
| 7 | Usage observability | API: Developer Portal → app → Analytics tab shows usage + rate limit per endpoint, but 'only … for endpoints you have made at least 1 request to today (UTC)' (make 1 test call, refresh); Developer Admins get email at 75% of an APPLICATION-level quota, delayed '1–2 hours', 'only on application-level threshold breaches, not on member-level'; no usage/quota headers or endpoint; refresh-token usage visible in Developer Portal Tools. SCRAPE: none — the 999/authwall response IS the only signal. _(src: https://learn.microsoft.com/en-us/linkedin/shared/api-guide/concepts/rate-limits, 2026-09-02)_ |
| 8 | Health signal | Statuspage-compatible: https://www.linkedin-apistatus.com/api/v2/status.json returned {"page":{"id":"mxfydrt8b8xw","name":"LinkedIn API","updated_at":"2026-02-28T14:58:45.852Z"},"status":{"indicator":"none","description":"All Systems Operational"}} today; https://www.linkedin-status.com/api/v2/status.json (member products) also 'All Systems Operational' (updated 2026-08-02), and its history page says 'Please check LinkedIn API Status for updates on Developer tools'. No health signal for the scrape surface. _(src: https://www.linkedin-apistatus.com/api/v2/status.json, 2026-09-02)_ |
| 9 | Credential lifecycle | SCRAPE: no credential; using a member session cookie is a §8.2 'bots or other unauthorized automated methods' violation. API: OAuth 2.0 3-legged; authorization code '30-minute lifespan'; 'all access tokens are issued with a 60-day lifespan' (`expires_in` 5184000), ~500 chars ('handle tokens with length of at least 1000 characters'); default refresh = re-run the auth flow (consent screen bypassed only while member still logged in AND token unexpired); programmatic `refresh_token` only 'for all approved Marketing Developer Platform (MDP) partners': 365-day TTL that does NOT reset on use, each refresh mints a new 60-day access token, member 'must reauthorize your application when refresh tokens expire'; LinkedIn 'reserves the right to revoke Refresh Tokens or Access Tokens at any time'; requesting a different scope invalidates all prior tokens; member revocation → 401 'The token has been revoked'. _(src: https://learn.microsoft.com/en-us/linkedin/shared/authentication/programmatic-refresh-tokens, 2026-09-02)_ |
| 10 | Interface lifecycle | Marketing + Community Management APIs: base `https://api.linkedin.com/rest/`, header `Linkedin-Version: YYYYMM` mandatory ('the latest version is not applied by default'); new version monthly, each 'supported for a minimum of one (1) year'; latest 202608; 202508 sunsets 2026-08-17; missing header → 400 `VERSION_MISSING`; sunset header → 426 `NONEXISTENT_VERSION` 'Requested version yyyymmdd is not active'; LinkedIn 'reserves the right to release a patch version … for any critical security, privacy issues, or bug fixes'. Open-permission endpoints still on unversioned `/v2/` (e.g. `/v2/me`). SCRAPE: no contract — DOM/embedded JSON (`datalet-bpr-guid` code blocks, `__APOLLO_STATE__`, ld+json) changes unannounced. _(src: https://learn.microsoft.com/en-us/linkedin/marketing/versioning, 2026-09-02)_ |
| 11 | Data contract | API error body {message, serviceErrorCode, status} (+ `code`, `errorDetailType` `com.linkedin.common.error.BadRequest`, `errorDetails{inputErrors[],conditionalInputErrors[]}` on adAccounts/adCampaignGroups/adCampaigns); lists {elements[], paging{start,count}}; batch {results{key:{status}}, errors{key:{…}}}; Rest.li `X-Restli-Protocol-Version: 2.0.0` header; URN ids (`urn:li:sponsoredAccount:…`). SCRAPE: logged-out profile 200s carry an EMPTY schema.org `Person` ld+json; 999 body is an HTML fragment redirecting to `/authwall`. _(src: https://learn.microsoft.com/en-us/linkedin/shared/api-guide/concepts/error-handling, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | none — scrape target has no push. API side: the fetched Marketing/Community Management docs (overview, versioning, error-handling) document no webhooks or streams — all pull; 'Organization Social Actions Notifications' is an outbound member-notification feature, not a developer webhook. UNKNOWN beyond that — tried community-management-overview, versioning, error-handling. _(src: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-overview, 2026-09-02)_ |
| — | **Resilience posture (58)** | scrape target (ToS-prohibited; contract claims enforced post-hiQ); treat 999 / `/authwall` / 429 / checkpoint as circuit-OPEN, never retry-harder; per-run page budget env knob + per-host egress cooldown; official API only via approved OAuth app with 60-day token renewal job; no receiver (no push) |

- **Research notes** _(2026-09-02)_: vendor status: https://www.linkedin-apistatus.com (Atlassian Statuspage; JSON at /api/v2/status.json) — member-product page https://www.linkedin-status.com defers Developer tools to it.

## Research & market data

### Scopus

**Type:** research-data · **Reach:** REST API (env key) · **Used by:** 2 project(s) — fabrik-citation-verifier, spec:fabrik-citation-verifier · **Env keys:** `SCOPUS_*` · **Docs:** https://dev.elsevier.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'Scopus API rate limits Elsevier', fetched https://dev.elsevier.com/api_key_settings.html, https://dev.elsevier.com/guides/ScopusSearchViews/rate_limits.htm |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep 2026-09-02 suggested '429 with Retry-After header; overage billing possible depending on plan.' but its source is dead/unfetched (https://dev.elsevier.com/guides/ScopusSearchViews/rate_limits.htm); re-verify live |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Concurrency limits per API key; specific numbers not publicly listed.' but its source is dead/unfetched (https://dev.elsevier.com/guides/ScopusSearchViews/rate_limits.htm); re-verify live |
| 4 | Identity posture | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Per API key; ToS prohibit sharing keys or circumventing limits (clause 3.2).' but its source is dead/unfetched (https://dev.elsevier.com/terms_agree.html); re-verify live |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Retry with exponential backoff on 429/5xx; pagination via start/query parameters' but its source is dead/unfetched (https://dev.elsevier.com/guides/ScopusSearchViews/pagination.htm); re-verify live |
| 6 | Cost model | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Paid subscription plans; per-abstract retrieval; spikes from high-volume searche' but its source is dead/unfetched (https://dev.elsevier.com/pricing.html); re-verify live |
| 7 | Usage observability | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Usage dashboard in Elsevier Developer Portal; no dedicated API endpoint found.' but its source is dead/unfetched (https://dev.elsevier.com/user); re-verify live |
| 8 | Health signal | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'No dedicated Scopus status page; general Elsevier status at https://status.elsev' but its source is dead/unfetched (https://status.elsevier.com); re-verify live |
| 9 | Credential lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): API keys do not expire; can be regenerated manually. Inactive keys may be revoked. — verify: https://dev.elsevier.com/api_key_settings.html |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'API version in URL (e.g., /scopus/search/v1); deprecation announcements via port' but its source is dead/unfetched (https://dev.elsevier.com/tecdoc_api_versions.html); re-verify live |
| 11 | Data contract | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Documented XML/JSON schemas; pagination with `start` and `count`; deletion not applicable. — verify: https://dev.elsevier.com/documentation/ScopusSearchAPI.wadl |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'Scopus webhooks push API', fetched https://dev.elsevier.com |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Bibliographic database; rate limits are tiered but not publicly detailed.

### Ncbi

**Type:** research-data · **Reach:** REST API (env key) · **Used by:** 2 project(s) — fabrik-citation-verifier, spec:fabrik-citation-verifier · **Env keys:** `NCBI_*` · **Docs:** https://www.ncbi.nlm.nih.gov/home/develop/api

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): E-utilities: 10 requests/second, no daily limit if using API keys. Without key: 3/sec. Reset per second. — verify: https://www.ncbi.nlm.nih.gov/books/NBK25497/ |
| 2 | Behaviour AT the cap | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Returns HTTP 429 with Retry-After header for rate limit violations. — verify: https://www.ncbi.nlm.nih.gov/books/NBK25497/ |
| 3 | Concurrency & parallelism | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Concurrency limit is the rate limit (10/sec). Scoped to IP address or API key. — verify: https://www.ncbi.nlm.nih.gov/books/NBK25497/ |
| 4 | Identity posture | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Multiple accounts not addressed. Usage guidelines encourage responsible, non-commercial use. — verify: https://www.ncbi.nlm.nih.gov/home/develop/api/ |
| 5 | Failure & resume | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): 429 errors are retryable. No native idempotency keys. Smallest resumable unit is a single request. — verify: https://www.ncbi.nlm.nih.gov/books/NBK25497/ |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Free for non-commercial use. Cost spikes from high-volume automated queries triggering rate limits. — verify: https://www.ncbi.nlm.nih.gov/home/develop/api/ |
| 7 | Usage observability | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): No direct endpoint for consumption. Monitor via HTTP 429 responses and logs. — verify: https://www.ncbi.nlm.nih.gov/books/NBK25497/ |
| 8 | Health signal | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Status page: https://status.ncbi.nlm.nih.gov. RSS/Atom feed available.' but its source is dead/unfetched (https://status.ncbi.nlm.nih.gov); re-verify live |
| 9 | Credential lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): API keys do not expire. Expired/revoked key returns authentication error. — verify: https://www.ncbi.nlm.nih.gov/account/ |
| 10 | Interface lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Versioned via E-utilities (e.g., esearch.fcgi?db=...&version=2.0). Deprecation notices via announcement. — verify: https://www.ncbi.nlm.nih.gov/books/NBK25497/ |
| 11 | Data contract | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Documented XML/JSON schemas per database. Pagination via retmax/retstart. Deletion not typically signaled. — verify: https://www.ncbi.nlm.nih.gov/books/NBK25499/ |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'NCBI webhook push subscription' |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Rate limits are the primary operational constraint; using an API key significantly increases limits.

### Semantic Scholar

**Type:** research · **Reach:** REST API (env key) · **Used by:** 2 project(s) — fabrik-citation-verifier, spec:fabrik-citation-verifier · **Env keys:** `SEMANTIC_SCHOLAR_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Public API: 100 requests/day free; Academic/Commercial tiers: 500k/month. Resets daily/monthly. — verify: https://api.semanticscholar.org/api-docs/ |
| 2 | Behaviour AT the cap | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): 429 Too Many Requests; quota reset at UTC midnight (public tier). — verify: https://api.semanticscholar.org/api-docs/#tag/API-Overview |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'semantic scholar concurrency limit', fetched https://api.semanticscholar.org/api-docs/ |
| 4 | Identity posture | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Per API key; ToS prohibit circumventing limits (section 3.2).' but its source is dead/unfetched (https://www.semanticscholar.org/terms); re-verify live |
| 5 | Failure & resume | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Retry with exponential backoff on 429/5xx; idempotent GET; pagination via offset/limit. — verify: https://api.semanticscholar.org/api-docs/#tag/Paper-Data |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Free tier; paid tiers per paper retrieval; spikes from bulk queries. — verify: https://api.semanticscholar.org/api-docs/#tag/Pricing |
| 7 | Usage observability | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Usage visible in account dashboard for paid tiers; no public API endpoint. — verify: https://www.semanticscholar.org/product/api |
| 8 | Health signal | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'No public status page found.' but its source is dead/unfetched (no url); re-verify live |
| 9 | Credential lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): API keys do not expire; can be regenerated. — verify: https://www.semanticscholar.org/product/api |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'API version in URL (e.g., /v1); deprecation via changelog.' but its source is dead/unfetched (https://github.com/allenai/s2apidocs); re-verify live |
| 11 | Data contract | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Schema documented; pagination with `offset` & `limit`; data snapshots, not real-time. — verify: https://api.semanticscholar.org/api-docs/#tag/Paper-Data |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'semantic scholar webhooks', fetched https://api.semanticscholar.org/api-docs/ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Academic paper API; daily rate limit for free tier.

### Core

**Type:** research-data · **Reach:** REST API (env key) · **Used by:** 2 project(s) — fabrik-citation-verifier, spec:fabrik-citation-verifier · **Env keys:** `CORE_*` · **Docs:** https://core.ac.uk

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Public API: 100 req/hour, resets rolling hour. CORE API key: 1,000 req/hour, 10,000 req/day. Higher tiers available. — verify: https://core.ac.uk/documentation/api/#rate-limiting |
| 2 | Behaviour AT the cap | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Returns 429 with JSON error; Retry-After header. No overage billing; hard block until limit resets. — verify: https://core.ac.uk/documentation/api/#errors |
| 3 | Concurrency & parallelism | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): No documented concurrency limit. Limits scoped per API key (or IP if no key). — verify: https://core.ac.uk/documentation/api/#rate-limiting |
| 4 | Identity posture | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Per API key. ToS allows one account per person; prohibits sharing keys (clause 3.2). — verify: https://core.ac.uk/terms |
| 5 | Failure & resume | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Retryable: 429, 5xx. Idempotent. Pagination via page, pageSize. Smallest unit: single search/retrieval request. — verify: https://core.ac.uk/documentation/api/#pagination |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Unit: API request. Free tier: 100 req/hour. Paid plans increase quotas. Spikes from large search result pagination. — verify: https://core.ac.uk/services#api |
| 7 | Usage observability | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): No usage endpoint; check X-RateLimit-Remaining header in responses. — verify: https://core.ac.uk/documentation/api/#rate-limiting |
| 8 | Health signal | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): No status page URL documented. UNKNOWN — tried: searched 'CORE status page', none found. — verify: https://core.ac.uk/documentation/api |
| 9 | Credential lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): API keys do not expire; manual rotation. Invalid key returns 403 'Invalid API key'. — verify: https://core.ac.uk/documentation/api/#authentication |
| 10 | Interface lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): API version in URL (/api/v2/). Deprecation via changelog. Notice period not specified. — verify: https://core.ac.uk/documentation/api/#changelog |
| 11 | Data contract | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Documented JSON schema. Pagination via page/pageSize. Read-only; no deletion. Schema stable. — verify: https://core.ac.uk/documentation/api/#data-model |
| 12 | Push delivery (webhooks/streams) | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): No webhooks or push delivery; polling only. — verify: https://core.ac.uk/documentation/api |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Recent: Added PDF full-text extraction to API (beta).

### Comtrade

**Type:** research-data · **Reach:** REST API (env key) · **Used by:** 1 project(s) — trade-intelligence · **Env keys:** `COMTRADE_SUBSCRIPTION_*` · **Docs:** https://comtradeplus.un.org

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Guest: 100 req/hour, 1,000 req/day. Registered: 1,000 req/hour, 10,000 req/day. ' but its source is dead/unfetched (https://comtradeapi.un.org/data/doc/api#/Rate%20Limits); re-verify live |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Returns 429 Too Many Requests with Retry-After header. No overage billing; hard ' but its source is dead/unfetched (https://comtradeapi.un.org/data/doc/api#/Errors/429); re-verify live |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'No documented concurrency limit. Rate limits scoped per API key (registered) or ' but its source is dead/unfetched (https://comtradeapi.un.org/data/doc/api#/Rate%20Limits); re-verify live |
| 4 | Identity posture | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Per API key for registered users; IP for guests. ToS: one account per user; no clause on multiple accounts found. — verify: https://comtrade.un.org/policies/terms-of-use |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Retryable: 429, 5xx. Calls idempotent. No cursors; pagination via limit/offset. ' but its source is dead/unfetched (https://comtradeapi.un.org/data/doc/api#/Errors); re-verify live |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Freemium: free up to limits. Paid subscription for higher quotas (units: requests). Spikes from bulk data pulls. — verify: https://comtrade.un.org/policies/subscriptions |
| 7 | Usage observability | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'No usage endpoint; monitor X-RateLimit-* headers in responses.' but its source is dead/unfetched (https://comtradeapi.un.org/data/doc/api#/Rate%20Limits); re-verify live |
| 8 | Health signal | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'No status page URL documented. UNKNOWN — tried: searched 'UN Comtrade status', n' but its source is dead/unfetched (https://comtradeapi.un.org/data/doc/api); re-verify live |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'API keys do not expire. Manual rotation. Expired keys return 401 'Invalid subscr' but its source is dead/unfetched (https://comtradeapi.un.org/data/doc/api#/Authentication); re-verify live |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'API version in URL path (/api/v1/). Deprecation via API doc changelog. No Sunset' but its source is dead/unfetched (https://comtradeapi.un.org/data/doc/api#/Changelog); re-verify live |
| 11 | Data contract | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Documented JSON schema. Pagination via $skip, $top. Deletion not applicable (rea' but its source is dead/unfetched (https://comtradeapi.un.org/data/doc/api#/Data%20structure); re-verify live |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'No webhooks or push delivery; polling only.' but its source is dead/unfetched (https://comtradeapi.un.org/data/doc/api); re-verify live |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: API v1 released 2023; migration from legacy API ongoing.

### Boldata

**Type:** research-data · **Reach:** REST API (env key) · **Used by:** 1 project(s) — trade-intelligence · **Env keys:** `BOLDATA_*` · **Docs:** https://billofladingdata.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://billofladingdata.com — suggested src: https://billofladingdata.com |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://billofladingdata.com — suggested src: https://billofladingdata.com |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://billofladingdata.com — suggested src: https://billofladingdata.com |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://billofladingdata.com — suggested src: https://billofladingdata.com |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://billofladingdata.com — suggested src: https://billofladingdata.com |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Paid product (per caller's note); pricing page not reached — verify: https://billofladingdata.com |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://billofladingdata.com — suggested src: https://billofladingdata.com |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://billofladingdata.com — suggested src: https://billofladingdata.com |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://billofladingdata.com — suggested src: https://billofladingdata.com |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://billofladingdata.com — suggested src: https://billofladingdata.com |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://billofladingdata.com — suggested src: https://billofladingdata.com |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://billofladingdata.com — suggested src: https://billofladingdata.com |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Domain reachable per caller but live fetch not performed in this run.

### Zari

**Type:** research-data · **Reach:** REST API (env key) · **Used by:** 1 project(s) — trade-intelligence · **Env keys:** `ZARI_*` · **Docs:** https://zari.ai

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Free tier: 100 req/day, 10 req/min; Pro: 10,000 req/day, 100 req/min; resets daily UTC 00:00 — verify: https://zari.ai/pricing |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep 2026-09-02 suggested '429 with Retry-After header; hard block; no overage billing' but its source is dead/unfetched (https://docs.zari.ai/rate-limits); re-verify live |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Max 5 concurrent requests per API key; scoped to account' but its source is dead/unfetched (https://docs.zari.ai/rate-limits#concurrency); re-verify live |
| 4 | Identity posture | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Per API key; ToS prohibits multiple free accounts (§4.2) — verify: https://zari.ai/terms#section-4-2 |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep 2026-09-02 suggested '500-503 retryable; idempotency keys supported; cursor pagination; resumable at p' but its source is dead/unfetched (https://docs.zari.ai/api-reference#errors); re-verify live |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): $0.001 per request; 100 free/day; minimum $10; spiked by batch operations — verify: https://zari.ai/pricing |
| 7 | Usage observability | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'GET /v1/usage returns consumption & remaining quota' but its source is dead/unfetched (https://docs.zari.ai/api-reference#get-usage); re-verify live |
| 8 | Health signal | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'https://status.zari.ai; machine-readable JSON at /api/v1/status' but its source is dead/unfetched (https://status.zari.ai); re-verify live |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Keys expire yearly; 7-day overlap rotation; expired returns 403' but its source is dead/unfetched (https://docs.zari.ai/authentication#key-expiry); re-verify live |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Versioned URLs; deprecation via changelog; 6-month notice; Sunset headers' but its source is dead/unfetched (https://docs.zari.ai/versioning); re-verify live |
| 11 | Data contract | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'JSON Schema documented; versioned schemas; cursor pagination; 404 on deletion' but its source is dead/unfetched (https://docs.zari.ai/api-reference#schemas); re-verify live |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Not applicable — no webhooks offered' but its source is dead/unfetched (https://docs.zari.ai/webhooks); re-verify live |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Recent pricing change introduced free tier; concurrency limits tightened 2024-03

### Evds

**Type:** research-data · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found) · **Docs:** https://evds2.tcmb.gov.tr

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | free _(catalog `cost`, refreshed daily)_ |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### Fred

**Type:** research-data · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found) · **Docs:** https://fred.stlouisfed.org/docs/api

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | free _(catalog `cost`, refreshed daily)_ |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### DNA (research-data)

**Type:** research-data · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found)

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | paid _(catalog `cost`, refreshed daily)_ |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### Youtube

**Type:** research-data · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found) · **Docs:** https://developers.google.com/youtube

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | freemium _(catalog `cost`, refreshed daily)_ |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### Ctrader

**Type:** research · **Reach:** REST API (env key) · **Used by:** 2 project(s) — spec:trading-core, trading-core · **Env keys:** `CTRADER_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | 50 req/s per connection non-historical; 5 req/s per connection historical. _(src: https://help.ctrader.com/open-api/, 2026-09-02)_ |
| 2 | Behaviour AT the cap | ProtoOAErrorRes: REQUEST_FREQUENCY_EXCEEDED (108), CONNECTIONS_LIMIT_EXCEEDED (67), SERVER_IS_UNDER_MAINTENANCE (109) with maintenanceEndTimestamp/retryAfter. _(src: https://help.ctrader.com/open-api/model-messages/, 2026-09-02)_ |
| 3 | Concurrency & parallelism | Per connection; best practice max two connections (demo + live), each unlimited accounts; ports 5035 protobuf / 5036 JSON. _(src: https://help.ctrader.com/open-api/proxies-endpoints/, 2026-09-02)_ |
| 4 | Identity posture | Per app (clientId/secret) + per-cTID OAuth. Terms: 'fair and sensible' use, misuse -> access removed; no explicit multi-account clause. _(src: https://help.ctrader.com/open-api/terms-of-use/, 2026-09-02)_ |
| 5 | Failure & resume | Persistent TCP/WebSocket; ProtoHeartbeatEvent if idle >30 s; reconnect + re-auth after ProtoOAClientDisconnectEvent; historical by timestamp range, no cursor. _(src: https://help.ctrader.com/open-api/common-messages/, 2026-09-02)_ |
| 6 | Cost model | Free; Spotware may change pricing 'without prior notice'. _(src: https://help.ctrader.com/open-api/terms-of-use/, 2026-09-02)_ |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) tried getting-started/model-messages: no usage endpoint; only error responses. — suggested src: https://help.ctrader.com/open-api/ |
| 8 | Health signal | No public status page (status.ctrader.com ENOTFOUND; none found by search); maintenance signalled in-band via error 109 + maintenanceEndTimestamp. _(src: https://help.ctrader.com/open-api/model-messages/, 2026-09-02)_ |
| 9 | Credential lifecycle | Auth code 1 min; access token 2,628,000 s (~30 d); refresh token never expires; expired -> OA_AUTH_TOKEN_EXPIRED (1)/CH_ACCESS_TOKEN_INVALID (104); ProtoOAAccountsTokenInvalidatedEvent pushed. _(src: https://help.ctrader.com/open-api/account-authentication/, 2026-09-02)_ |
| 10 | Interface lifecycle | Protobuf 'ProtoOA*' v2 messages; 'reserves the right to modify the API… without prior notice'; no headers; channel = docs/Telegram. _(src: https://help.ctrader.com/open-api/terms-of-use/, 2026-09-02)_ |
| 11 | Data contract | Schema = Spotware .proto files; Protobuf additive; JSON alt on 5036; deletion n/a. _(src: https://help.ctrader.com/open-api/, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | Push = event stream on same socket; heartbeat >=30 s; no replay window or list — refetch state after reconnect. _(src: https://help.ctrader.com/open-api/common-messages/, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Demo and live are separate endpoints/connections; TCP must be SSL.

### SEO data provider (env `SEO_API_KEY`)

**Type:** research-data · **Reach:** REST API (env key) · **Used by:** 3 project(s) — fabrik, spec:wpf, web-ecommerce-factory · **Env keys:** `SEO_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'seo api rate limits', fetched https://moz.com/products/api, https://ahrefs.com/docs/api/v4, https://developers.google.com/search/apis |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'seo api 429 overage billing', fetched multiple vendor docs |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'seo api concurrency', fetched multiple vendor docs |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'seo api terms multiple accounts', fetched multiple vendor ToS |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'seo api idempotency retry', fetched multiple vendor docs |
| 6 | Cost model | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'seo api pricing unit free tier', fetched multiple vendor pricing pages |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'seo api usage dashboard', fetched multiple vendor docs |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'seo api status page', fetched multiple vendor sites |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'seo api key expiry rotation', fetched multiple vendor docs |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'seo api versioning deprecation', fetched multiple vendor docs |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'seo api schema pagination', fetched multiple vendor docs |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'seo webhooks', fetched multiple vendor docs |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: 'seo' is a category, not a specific vendor; could not ground to a single provider.

### U.S. Bureau of Labor Statistics API

**Type:** research-data · **Reach:** REST API (v1 keyless / v2 registered key) · **Used by:** 1 project(s) — web-ecommerce-factory (code call sites) · **Hosts:** `www.bls.gov` · **Env keys:** none in the fleet today (reached without a key; the posture row names the knob a consumer would add) · **Docs:** https://www.bls.gov/developers/ (API Signatures v2: https://www.bls.gov/developers/api_signature_v2.htm · FAQs: https://www.bls.gov/developers/api_faqs.htm · Release notes: https://www.bls.gov/bls/api_features.htm)

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | v2 (registered) vs v1 (unregistered): daily query limit 500 vs 25; series per query 50 vs 25; years per query 20 vs 10; request rate limit 50 requests per 10 seconds (both); net/percent changes, optional annual averages and catalog metadata v2-only. Single/Multiple Series signatures return 3 years by default. _(src: https://www.bls.gov/developers/api_faqs.htm, 2026-09-02)_ |
| 2 | Behaviour AT the cap | Rate cap → HTTP 429 'You have exceeded our limit on the number of queries that can be executed within a specific period of time.' _(src: https://www.bls.gov/developers/api_faqs.htm, 2026-09-02)_. Daily cap → HTTP 200 with envelope `{"status":"REQUEST_NOT_PROCESSED","responseTime":0,"message":["Request could not be serviced, as the daily threshold for total number of requests allocated to the user has been reached."],"Results":{}}` — text not on any BLS page; from a user-pasted response _(src: https://community.qlik.com/t5/Visualization-and-Usability/Loading-data-via-API-connection/td-p/1162323, 2026-09-02)_. ToS: attempting to 'exceed or circumvent these limits' → access 'may be permanently or temporarily blocked'. _(src: https://www.bls.gov/developers/termsOfService.htm, 2026-09-02)_ |
| 3 | Concurrency & parallelism | No concurrency cap documented; the only rate figure is 50 requests per 10 seconds for both versions, and unregistered (v1) quota is tracked per IP (community observation: 'They see your IP'). Batch via POST `seriesid[]` (≤50 v2 / ≤25 v1) instead of parallel GETs. _(src: https://www.bls.gov/developers/api_faqs.htm, 2026-09-02)_ |
| 4 | Identity posture | v1: no identity ('does not require registration and is open for public use'). v2: registration = email + organization name + CAPTCHA + ToS tick at https://data.bls.gov/registrationEngine/; key emailed from labstat@bls.gov. ToS: BLS 'may monitor your use', may 'refuse to provide the services' or terminate 'at any time for any other reason in its sole discretion'; no one-key-per-entity clause in the fetched text. _(src: https://www.bls.gov/developers/termsOfService.htm, 2026-09-02)_ |
| 5 | Failure & resume | Pull-only, idempotent reads: resumable unit = one query (series list × startyear–endyear window). Per-series soft errors arrive inside a `REQUEST_SUCCEEDED` envelope as `message[]` strings ('Invalid Series for Series …', 'No Data Available for Series … Year: …', 'Series does not exist', 'Database is locked for Series' = 'currently not available' → retry later). HTTP codes documented: 200, 202 ('request is processing'), 400, 401, 404, 429, 500. No pagination — window by year range. _(src: https://www.bls.gov/developers/api_faqs.htm, 2026-09-02)_ |
| 6 | Cost model | $0 for both versions; registration is free (email + org name). All BLS output is public domain ('free to use our public domain material without specific permission, although we do ask that you cite'). No paid tier exists — spike cost = hitting the 500/day wall, not money. _(src: https://www.bls.gov/bls/linksite.htm, 2026-09-02)_ |
| 7 | Usage observability | None — no rate-limit/quota headers, no usage endpoint, no dashboard documented; the only signal is the `REQUEST_NOT_PROCESSED` envelope on the 26th/501st query and HTTP 429 on the 10-second window. UNKNOWN beyond that — tried: developers/, api_faqs.htm, api_signature_v2.htm, api_features.htm, termsOfService.htm. _(src: https://www.bls.gov/developers/api_faqs.htm, 2026-09-02)_ |
| 8 | Health signal | No status page or JSON health endpoint. Live probe today: `GET https://api.bls.gov/publicAPI/v2/timeseries/data/LNS14000000` → `"status":"REQUEST_SUCCEEDED","responseTime":109` (latest point 2026-M06); the same series on v1 returned latest 2026-M02 — v1 served staler data. Planned downtime = dated announcement pages (e.g. 2026-06-21 07:00–14:00 ET, api.bls.gov listed). ToS: 'no warranty that the services will be error free or that access thereto will be continuous or uninterrupted'. _(src: https://api.bls.gov/publicAPI/v2/timeseries/data/LNS14000000 + https://www.bls.gov/bls/maintenance06212026.htm, 2026-09-02)_ |
| 9 | Credential lifecycle | Keys DO expire: 'Users must renew registration with the BLS Public Data API at least once a year.' Key = 32-char `registrationkey` sent as JSON field, form field, or `?registrationkey=` query param (URL-borne → treat as loggable). No revoke/rotate/multi-key endpoint documented; overlap = register a second email. Key behaviour on expiry (silent v1 downgrade vs error) UNKNOWN — tried: api_faqs.htm, api_signature_v2.htm, registrationEngine/. _(src: https://www.bls.gov/developers/api_faqs.htm, 2026-09-02)_ |
| 10 | Interface lifecycle | Path-versioned: `/publicAPI/v1/` (2013-08-19) and `/publicAPI/v2/` (2014-10-16; minor releases 2.1 2016-02, 2.2 2016-11, 2.3 2018-02, 2.4 2020-10-05 — last change). v1 still live today and 'API 1.0 signatures are compatible with API Version 2.0'; no deprecation/sunset announced; no Deprecation/Sunset headers documented. TLS 1.0 dropped 2018-10-01 (TLS 1.1+, prefer 1.2+). ToS may be modified 'at its sole discretion' with continued use = acceptance. _(src: https://www.bls.gov/bls/api_features.htm, 2026-09-02)_ |
| 11 | Data contract | Envelope `{status, responseTime, message[], Results}`; status ∈ {REQUEST_SUCCEEDED, REQUEST_NOT_PROCESSED}; `Results.series[]{seriesID, catalog?{series_title, series_id, seasonality, survey_name, survey_abbreviation, …}, data[]{year, period (M01–M12, M13 annual avg, Q01–Q04, S01–S03, A01), periodName, latest?:"true", value (string; "-" when unavailable), footnotes[]{code,text}, aspects?[], calculations?}}`. Results descending, most recent first (since 2.2). Series IDs uppercase, may contain `_ - #`. Also `/timeseries/popular?survey=`, `/surveys`, `/surveys/{abbr}` ({survey_name, survey_abbreviation, allowsNetChange, allowsPercentChange, hasAnnualAverages}); `.xlsx` variant. Requests: JSON or x-www-form-urlencoded, lowercase param names. _(src: https://www.bls.gov/developers/api_signature_v2.htm, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | None — no webhooks, streams or feeds for the API. Substitute = the release calendar (https://www.bls.gov/schedule/news_release/ — dated grid, releases at 08:30 or 10:00 AM ET) plus the documented lag: 'There is a one day lag between published data and its availability for retrieval from the API.' Poll `?latest=true` after release-day + 1. _(src: https://www.bls.gov/bls/api_features.htm, 2026-09-02)_ |
| — | **Resilience posture (58)** | pull-only public-data source; `BLS_REGISTRATION_KEY` env knob (v2) with v1 as keyless fallback; per-day query budget (500/25) enforced client-side because the server signals exhaustion only as a 200 `REQUEST_NOT_PROCESSED`; annual key renewal is a calendar item, not an alert |

- **Research notes** _(2026-09-02)_: vendor status: none found — BLS has no status page; scheduled downtime is announced as dated pages under https://www.bls.gov/bls/announcements/ (latest fetched: https://www.bls.gov/bls/maintenance06212026.htm, which lists `https://api.bls.gov/` among affected hosts).

## SEO & web signals

### Google Safe Browsing

**Type:** search · **Reach:** REST API (env key) · **Used by:** 1 project(s) — site-provisioner · **Env keys:** `GOOGLE_SAFE_BROWSING_*` · **Docs:** https://developers.google.com/safe-browsing

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Free tier: 10,000 requests per day per API key. No per-minute rate limit specified. Size caps per request. https://developers.google.com/safe-browsing/v4/usage-limits — verify: https://developers.google.com/safe-browsing/v4/usage-limits |
| 2 | Behaviour AT the cap | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): HTTP 429 for exceeding quota; Retry-After header may be present. Hard block, no overage billing for free tier. https://developers.google.com/safe-browsing/v4/usage-limits — verify: https://developers.google.com/safe-browsing/v4/usage-limits |
| 3 | Concurrency & parallelism | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Concurrent requests count towards daily quota. Limits per API key. No explicit max in-flight stated. https://developers.google.com/safe-browsing/v4/usage-limits — verify: https://developers.google.com/safe-browsing/v4/usage-limits |
| 4 | Identity posture | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Per API key/project. Terms of Service restrict circumventing limits. Acceptable Use Policy applies. https://developers.google.com/safe-browsing/terms — verify: https://developers.google.com/safe-browsing/terms |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Retryable on 429, 5xx. Lookup calls idempotent. No cursors; full lists in threat' but its source is dead/unfetched (https://developers.google.com/safe-browsing/v4/implementation); re-verify live |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Free up to 10k requests/day. No paid tier documented. Spike from high-volume URL checking. https://developers.google.com/safe-browsing/v4/usage-limits — verify: https://developers.google.com/safe-browsing/v4/usage-limits |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched for Safe Browsing usage monitoring API, fetched https://developers.google.com/safe-browsing/v4/reference/rest |
| 8 | Health signal | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Google Cloud Status Dashboard may include Safe Browsing. No dedicated status pag' but its source is dead/unfetched (no url); re-verify live |
| 9 | Credential lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): API keys don't expire; can be revoked. Expired/revoked key returns 403. https://developers.google.com/safe-browsing/v4/get-started — verify: https://developers.google.com/safe-browsing/v4/get-started |
| 10 | Interface lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): API versioned in URL (v4). Deprecation notices via Google Workspace blog. No fixed notice period. https://developers.google.com/safe-browsing/v4 — verify: https://developers.google.com/safe-browsing/v4 |
| 11 | Data contract | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Schema for ThreatMatches documented. No pagination for lookup. Lists fetched as full updates. https://developers.google.com/safe-browsing/v4/reference/rest — verify: https://developers.google.com/safe-browsing/v4/reference/rest |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'No push/webhooks; client pulls threat list updates via fetch API.' but its source is dead/unfetched (no url); re-verify live |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Free threat lookup service; daily quota is primary constraint.

### Chrome UX Report (CrUX)

**Type:** seo · **Reach:** REST API (env key) · **Used by:** 1 project(s) — web-ecommerce-factory · **Env keys:** `CRUX_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | 150 queries/min per Google Cloud project, shared by daily + History API; free; 'not possible to pay for an increased quota'. _(src: https://developer.chrome.com/docs/crux/history-api, 2026-09-02)_ |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) tried both API pages: no error-code section; quota is per-minute so back off ~60 s. — suggested src: https://developer.chrome.com/docs/crux/api |
| 3 | Concurrency & parallelism | 150 QPM per project (not per key). _(src: https://developer.chrome.com/docs/crux/api, 2026-09-02)_ |
| 4 | Identity posture | Per Cloud project; ToS clause on multiple projects UNKNOWN — Google APIs ToS not fetched this run. _(src: https://developer.chrome.com/docs/crux/api, 2026-09-02)_ |
| 5 | Failure & resume | Read-only POST, idempotent; 'repeated calls yield same results' within a day; no cursor; History returns up to 40 weeks (collectionPeriodCount 1–40) in one call. _(src: https://developer.chrome.com/docs/crux/history-api, 2026-09-02)_ |
| 6 | Cost model | Free, no charge, no paid tier. _(src: https://developer.chrome.com/docs/crux/api, 2026-09-02)_ |
| 7 | Usage observability | 'This limit, and your current usage, can be seen in the Google Cloud Console' — no API usage endpoint. _(src: https://developer.chrome.com/docs/crux/api, 2026-09-02)_ |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) tried both API pages: no status page referenced; update is 'best-effort, no SLA'. — suggested src: https://developer.chrome.com/docs/crux/api |
| 9 | Credential lifecycle | Google Cloud API key: expiry not documented; rotation with overlap (create new, migrate, delete old); restrictable by API/app. _(src: https://docs.cloud.google.com/docs/authentication/api-keys, 2026-09-02)_ |
| 10 | Interface lifecycle | v1 in path (/v1/records:queryRecord, :queryHistoryRecord); deprecation channel/headers UNKNOWN — tried docs. _(src: https://developer.chrome.com/docs/crux/history-api, 2026-09-02)_ |
| 11 | Data contract | 28-day rolling window, daily ~04:00 UTC, ~2-day lag; histograms + p75; CLS is a string; History weekly, Monday updates. _(src: https://developer.chrome.com/docs/crux/api, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only. _(src: https://developer.chrome.com/docs/crux/api, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Same key serves daily and History API.

### PageSpeed Insights

**Type:** seo · **Reach:** REST API (env key) · **Used by:** 1 project(s) — web-ecommerce-factory · **Env keys:** `PSI_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'Google PageSpeed Insights API quota' — suggested src: https://developers.google.com/speed/docs/insights/v5/get-started |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'PSI API 429 Retry-After' — suggested src: https://developers.google.com/speed/docs/insights/v5/get-started |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'PSI API concurrent requests per key' — suggested src: https://developers.google.com/speed/docs/insights/v5/get-started |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'PSI API key per IP ToS' — suggested src: https://developers.google.com/speed/docs/insights/v5/get-started |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'PSI API retryable errors strategy' — suggested src: https://developers.google.com/speed/docs/insights/v5/get-started |
| 6 | Cost model | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'PSI API pricing cost' — suggested src: https://developers.google.com/speed/docs/insights/v5/get-started |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'PSI API quota remaining endpoint' — suggested src: https://developers.google.com/speed/docs/insights/v5/get-started |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'Google Workspace status page PSI' — suggested src: https://status.cloud.google.com/ |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'PSI API key expiry rotation' — suggested src: https://developers.google.com/speed/docs/insights/v5/get-started |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'PSI API v5 deprecation' — suggested src: https://developers.google.com/speed/docs/insights/v5/get-started |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) 'PSI API response schema Lighthouse' — suggested src: https://developers.google.com/speed/docs/insights/v5/get-started |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) PSI has no webhook delivery — suggested src: https://developers.google.com/speed/docs/insights/v5/get-started |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: PSI likely refers to Google PageSpeed Insights API; vendor unconfirmed — lacks web tools to verify.

### Bing Webmaster

**Type:** search · **Reach:** REST API (env key) · **Used by:** 2 project(s) — site-provisioner, spec:site-provisioner · **Env keys:** `BING_WEBMASTER_*` · **Docs:** https://www.bing.com/webmasters

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://www.bing.com/webmasters — suggested src: https://www.bing.com/webmasters |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://www.bing.com/webmasters — suggested src: https://www.bing.com/webmasters |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://www.bing.com/webmasters — suggested src: https://www.bing.com/webmasters |
| 4 | Identity posture | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://www.bing.com/webmasters — suggested src: https://www.bing.com/webmasters |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://www.bing.com/webmasters — suggested src: https://www.bing.com/webmasters |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Free tier for site submission; paid Bing Webmaster API quota via Microsoft market (sources unverified) — verify: https://www.bing.com/webmasters |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://www.bing.com/webmasters — suggested src: https://www.bing.com/webmasters |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://www.bing.com/webmasters — suggested src: https://www.bing.com/webmasters |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://www.bing.com/webmasters — suggested src: https://www.bing.com/webmasters |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://www.bing.com/webmasters — suggested src: https://www.bing.com/webmasters |
| 11 | Data contract | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) fetch https://www.bing.com/webmasters — suggested src: https://www.bing.com/webmasters |
| 12 | Push delivery (webhooks/streams) | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Not applicable — Bing Webmaster is a crawl/SEO product, no outbound webhook delivery — verify: https://www.bing.com/webmasters |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Live web fetch was unavailable in this run; only URL provided by caller was fetched symbolically.

### Indexnow

**Type:** seo · **Reach:** REST API (env key) · **Used by:** 1 project(s) — web-ecommerce-factory · **Env keys:** `INDEXNOW_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Up to 10,000 URLs per POST; no numeric daily quota — 'verify that you don't submit too often'. _(src: https://www.indexnow.org/documentation, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 'Too Many Requests (potential Spam)'; 403 key invalid; 422 URL not of host / key mismatch. _(src: https://www.indexnow.org/documentation, 2026-09-02)_ |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) tried documentation + FAQ: nothing on concurrency. — suggested src: https://www.indexnow.org/faq |
| 4 | Identity posture | Per host via key file; open protocol, no ToS clause on accounts. _(src: https://www.indexnow.org/documentation, 2026-09-02)_ |
| 5 | Failure & resume | 200 = received only ('only indicates the search engine has received your URL'); 202 = key validation pending; resubmission harmless; no result/cursor. _(src: https://www.indexnow.org/documentation, 2026-09-02)_ |
| 6 | Cost model | Free. _(src: https://www.indexnow.org/documentation, 2026-09-02)_ |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) none in protocol; per-engine webmaster tools only (not fetched). — suggested src: https://www.indexnow.org/documentation |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) protocol has no status page; submissions relayed to all participating engines. — suggested src: https://www.indexnow.org/documentation |
| 9 | Credential lifecycle | Key 8–128 chars [a-zA-Z0-9-] hosted as {key}.txt; engines 'use the key until you change the key' — rotate by replacing file; invalid -> 403. _(src: https://www.indexnow.org/documentation, 2026-09-02)_ |
| 10 | Interface lifecycle | Unversioned https://<searchengine>/indexnow; changes via indexnow.org; no headers. _(src: https://www.indexnow.org/documentation, 2026-09-02)_ |
| 11 | Data contract | Request {host,key,keyLocation,urlList}; response is status code only, no body contract. _(src: https://www.indexnow.org/documentation, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — outbound push from you; no callbacks. _(src: https://www.indexnow.org/documentation, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Silent-truncation risk: 200 says received, never indexed.

### Openpagerank

**Type:** search · **Reach:** REST API (env key) · **Used by:** 2 project(s) — seo, site-provisioner · **Env keys:** `OPENPAGERANK_*` · **Docs:** https://www.domcop.com/openpagerank

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Free 30,000 domains/month @60 req/min; Bronze 100k/120; Silver 200k/300; Gold 1M/600; Platinum 4M/1,200; 100 domains/request; resets 1st of month. _(src: https://openpagerank.keywordseverywhere.com/pricing, 2026-09-02)_ |
| 2 | Behaviour AT the cap | Over-quota request 'declined, those domains are not counted' (429 quota_error); 429 rate_limit_error per minute. _(src: https://openpagerank.keywordseverywhere.com/pricing, 2026-09-02)_ |
| 3 | Concurrency & parallelism | Per key, requests/min by tier. _(src: https://openpagerank.keywordseverywhere.com/pricing, 2026-09-02)_ |
| 4 | Identity posture | Key tied to a Keywords Everywhere account; ToS UNKNOWN — not fetched. _(src: https://openpagerank.keywordseverywhere.com/docs, 2026-09-02)_ |
| 5 | Failure & resume | Read-only POST, idempotent; batch <=100; no cursor. _(src: https://openpagerank.keywordseverywhere.com/docs, 2026-09-02)_ |
| 6 | Cost model | Free tier; paid tiers bundled with Keywords Everywhere subscription (no separate OPR price). _(src: https://openpagerank.keywordseverywhere.com/pricing, 2026-09-02)_ |
| 7 | Usage observability | Usage endpoint (domains_remaining, monthly_domain_limit, domains_used, resets_at) + headers X-Domains-Remaining, X-RateLimit-Remaining. _(src: https://openpagerank.keywordseverywhere.com/docs, 2026-09-02)_ |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) tried docs + pricing: no status page referenced. — suggested src: https://openpagerank.keywordseverywhere.com/docs |
| 9 | Credential lifecycle | Bearer opr_live_ key; 401 authentication_error; expiry/rotation UNKNOWN — tried docs. _(src: https://openpagerank.keywordseverywhere.com/docs, 2026-09-02)_ |
| 10 | Interface lifecycle | /v1/domains/bulk; old domcop.com docs 301 to keywordseverywhere host; deprecation channel UNKNOWN. _(src: https://www.domcop.com/openpagerank/documentation, 2026-09-02)_ |
| 11 | Data contract | {as_of,count,results[{domain,found,open_page_rank,rank,referring_domains,history[]}],invalid[]}; monthly snapshots; interpolated months flagged `estimated`. _(src: https://openpagerank.keywordseverywhere.com/docs, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only. _(src: https://openpagerank.keywordseverywhere.com/docs, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: STALE if index cites domcop.com — now openpagerank.keywordseverywhere.com.

### Orbisearch

**Type:** search · **Reach:** REST API (env key) · **Used by:** 1 project(s) — trade-intelligence · **Env keys:** `ORBISEARCH_*` · **Docs:** https://orbisearch.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | 20 req/s per API key on /v1/verify; bulk lookup up to 10,000 rows/job. _(src: https://orbisearch.com/docs/api-reference/verify-email.md, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 + Retry-After; X-RateLimit-Limit/Remaining/Reset headers; 403 insufficient credits. _(src: https://orbisearch.com/docs/api-reference/verify-email.md, 2026-09-02)_ |
| 3 | Concurrency & parallelism | Per key 20 rps; use async /v1/bulk for volume. _(src: https://orbisearch.com/docs/api-reference/verify-email.md, 2026-09-02)_ |
| 4 | Identity posture | Per key; ToS UNKNOWN — not fetched. _(src: https://orbisearch.mintlify.app/llms.txt, 2026-09-02)_ |
| 5 | Failure & resume | Timeout -> HTTP 200 status=unknown/substatus=timeout; refund only on 502; bulk jobs polled by job_id with greylist auto-retry (retry_status). _(src: https://orbisearch.com/docs/guides/bulk-verification.md, 2026-09-02)_ |
| 6 | Cost model | 0.2 credits/verification, 1 credit/lookup; 24 h cache free; dedup within a job; packs e.g. 10,000 validations $30 (GitHub README 2025). _(src: https://orbisearch.com/docs/concepts/credits.md, 2026-09-02)_ |
| 7 | Usage observability | GET /v1/credits (balance + user id). _(src: https://orbisearch.com/docs/concepts/credits.md, 2026-09-02)_ |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) tried docs index: no status page referenced. — suggested src: https://orbisearch.mintlify.app/llms.txt |
| 9 | Credential lifecycle | X-API-Key; 401 on invalid; expiry/rotation UNKNOWN. _(src: https://orbisearch.com/docs/api-reference/verify-email.md, 2026-09-02)_ |
| 10 | Interface lifecycle | /v1; OpenAPI 1.0.0 embedded; deprecation channel UNKNOWN. _(src: https://orbisearch.com/docs/api-reference/verify-email.md, 2026-09-02)_ |
| 11 | Data contract | status safe/risky/invalid/unknown + substatus + flags; bulk-lookup results paginated. _(src: https://orbisearch.mintlify.app/llms.txt, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) marketing claims 'webhook callbacks' for bulk; bulk docs page documents none. — suggested src: https://orbisearch.com/docs/guides/bulk-verification.md |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Timeouts return 200 — count substatus=timeout as a failure metric.

### Abstract

**Type:** domains · **Reach:** REST API (env key) · **Used by:** 2 project(s) — calendar-orchestration-engine, spec:calendar-orchestration-engine · **Env keys:** `ABSTRACT_*` · **Docs:** https://abstractapi.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Per-product API key; free plans 1 request/second; each plan carries a fixed monthly request quota (ToS 'Subscription Plans'). Plan numbers not exposed in fetched docs. _(src: https://docs.abstractapi.com/api/ip-intelligence.md, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 429 'allowed requests per second reached'; 422 'insufficient API credits (Free plans)'; paid: overage billed, >=40% overage auto-upgrades plan; RPS breach 20x in 30 days auto-upgrades. _(src: https://www.abstractapi.com/legal/legal, 2026-09-02)_ |
| 3 | Concurrency & parallelism | RPS threshold per plan (free = 1 rps); scoped per API key, and each Abstract product has its own key. _(src: https://docs.abstractapi.com/api/ip-intelligence.md, 2026-09-02)_ |
| 4 | Identity posture | Per-key. Terms of Use (2025-07-15) fetched: no multi-account clause found in first 12k chars (bounded); bans automated access outside 'published interfaces'. _(src: https://www.abstractapi.com/legal/legal, 2026-09-02)_ |
| 5 | Failure & resume | Retry 429/500/503; single GET lookups are idempotent; no cursor/batch; 204 = 'no location data' (empty body, not an error). _(src: https://docs.abstractapi.com/api/ip-intelligence.md, 2026-09-02)_ |
| 6 | Cost model | Subscription with fixed requests/term + per-request overage fee + RPS tier; free tier gated by 422. Actual $ per plan UNKNOWN — tried https://www.abstractapi.com/api/ip-intelligence (no price table rendered). _(src: https://www.abstractapi.com/legal/legal, 2026-09-02)_ |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) tried docs.abstractapi.com llms.txt + ip-intelligence.md: no usage/remaining endpoint documented; 422 is the only quota signal. — suggested src: https://docs.abstractapi.com/llms.txt |
| 8 | Health signal | Better Stack status page (HTML, 'All services are online' 2026-09-02); /api/v2/status.json is NOT served — no Statuspage JSON. _(src: https://status.abstractapi.com/, 2026-09-02)_ |
| 9 | Credential lifecycle | Per-product key; expiry not documented (UNKNOWN — tried docs); missing/incorrect key returns 401. _(src: https://docs.abstractapi.com/api/ip-intelligence.md, 2026-09-02)_ |
| 10 | Interface lifecycle | 'All of Abstract's APIs are versioned' — /v1/ base URL; deprecation channel and Deprecation/Sunset headers UNKNOWN — tried docs. _(src: https://docs.abstractapi.com/api/ip-intelligence.md, 2026-09-02)_ |
| 11 | Data contract | JSON schema documented per product (ip-intelligence example with security/asn/location/timezone blocks); no pagination; 204 empty body is the silent shape. _(src: https://docs.abstractapi.com/api/ip-intelligence.md, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only. _(src: https://docs.abstractapi.com/llms.txt, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Bearer or api_key query auth; status page is Better Stack not Statuspage; ToS overage/RPS auto-upgrade is the cost spike.

### Whoxy

**Type:** domains · **Reach:** REST API (env key) · **Used by:** 1 project(s) — site-provisioner · **Env keys:** `WHOXY_*` · **Docs:** https://whoxy.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) exact quota numbers not surfaced on fetched pages — suggested src: https://whoxy.com/ |
| 2 | Behaviour AT the cap | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) cap behavior not documented on fetched pages — suggested src: https://whoxy.com/ |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) concurrency not documented — suggested src: https://whoxy.com/ |
| 4 | Identity posture | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Per-account API key; multiple-accounts ToS clause not located — verify: https://whoxy.com/ |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) retry/idempotency not documented — suggested src: https://whoxy.com/ |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Paid credit-based pricing per WHOIS lookup; pay-as-you-go model — verify: https://whoxy.com/pricing |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) remaining-credit endpoint not surfaced — suggested src: https://whoxy.com/ |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no status page surfaced — suggested src: https://whoxy.com/ |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) key rotation/expiry not documented — suggested src: https://whoxy.com/ |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) versioning not documented — suggested src: https://whoxy.com/ |
| 11 | Data contract | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): JSON WHOIS response documented in API reference — verify: https://whoxy.com/api-reference |
| 12 | Push delivery (webhooks/streams) | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): No webhook support — query-based API only — verify: https://whoxy.com/ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Cost model grounded; detailed quota/concurrency/health fields not located in fetched pages.

### Whoisjson

**Type:** domains · **Reach:** REST API (env key) · **Used by:** 1 project(s) — site-provisioner · **Env keys:** `WHOISJSON_*` · **Docs:** https://whoisjson.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Free plan capped at 500 WHOIS queries/month; paid plans raise limit — verify: https://whoisjson.com/pricing |
| 2 | Behaviour AT the cap | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Quota exceeded returns error/limit-exceeded response; no overage billing documented — verify: https://whoisjson.com/ |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) concurrency not documented on fetched pages — suggested src: https://whoisjson.com/ |
| 4 | Identity posture | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Per-account API key; ToS on multiple accounts not located in fetched pages — verify: https://whoisjson.com/ |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) idempotency/cursor not documented — suggested src: https://whoisjson.com/ |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Monthly subscription with included query quota; upgrade tiers remove caps — verify: https://whoisjson.com/pricing |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no remaining-quota endpoint surfaced — suggested src: https://whoisjson.com/ |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no status page surfaced — suggested src: https://whoisjson.com/ |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) key expiry policy not documented — suggested src: https://whoisjson.com/ |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) versioning not documented — suggested src: https://whoisjson.com/ |
| 11 | Data contract | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): JSON response fields documented in API docs (whois lookup endpoint) — verify: https://whoisjson.com/documentation |
| 12 | Push delivery (webhooks/streams) | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): No webhook support — synchronous query API — verify: https://whoisjson.com/documentation |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Marketing/pricing pages reachable; deeper docs subdomain not fully fetched.

### Whoisfreaks

**Type:** domains · **Reach:** REST API (env key) · **Used by:** 1 project(s) — site-provisioner · **Env keys:** `WHOISFREAKS_*` · **Docs:** https://whoisfreaks.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): User can request up to 2,000 WHOIS lookups per month on the free plan; paid plans scale higher — verify: https://whoisfreaks.com/pricing |
| 2 | Behaviour AT the cap | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Exceeding quota returns HTTP 429 Too Many Requests; no documented overage billing beyond plan cap — verify: https://whoisfreaks.com/pricing |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) concurrency limits not documented on fetched pages — suggested src: https://whoisfreaks.com/ |
| 4 | Identity posture | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Per-account API key; multiple accounts ToS clause not located in fetched pages — verify: https://whoisfreaks.com/ |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) idempotency/cursor behavior not documented on fetched pages — suggested src: https://whoisfreaks.com/ |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Monthly subscription tier with included lookup quota; overages require upgrade — verify: https://whoisfreaks.com/pricing |
| 7 | Usage observability | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no self-serve remaining-quota endpoint surfaced — suggested src: https://whoisfreaks.com/ |
| 8 | Health signal | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) no status page surfaced — suggested src: https://whoisfreaks.com/ |
| 9 | Credential lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) key expiry/rotation policy not documented — suggested src: https://whoisfreaks.com/ |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) API versioning not documented — suggested src: https://whoisfreaks.com/ |
| 11 | Data contract | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'JSON response schema documented in API docs (whois/v1 endpoint)' but its source is dead/unfetched (https://whoisfreaks.com/api-documentation); re-verify live |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'No webhook support — query-based API only' but its source is dead/unfetched (https://whoisfreaks.com/api-documentation); re-verify live |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Pricing page reachable but detailed docs subdomain only partially fetched; concurrency, observability, identity fields ungrounded.

### Domscan

**Type:** seo · **Reach:** REST API (env key) · **Used by:** 1 project(s) — site-provisioner · **Env keys:** `DOMSCAN_*`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | domscan.net: 10,000 free credits/month (refresh on signup anniversary); fresh RDAP ~100 req/min; cached (prefer_cache=1) unlimited; 50 domains + 50 TLDs per bulk request. _(src: https://domscan.net/docs/rate-limits, 2026-09-02)_ |
| 2 | Behaviour AT the cap | 402 INSUFFICIENT_CREDITS JSON (credits_remaining/credits_required); 429 rate limit; 503 upstream rate-limited. _(src: https://domscan.net/docs/credits-pricing, 2026-09-02)_ |
| 3 | Concurrency & parallelism | Per API key; ~100/min fresh; async batches via POST /v1/batches. _(src: https://domscan.net/docs/rate-limits, 2026-09-02)_ |
| 4 | Identity posture | ToS (2026-07-30): 'Each email address can belong to one active customer account'; 'may not attempt to circumvent rate limits'. _(src: https://domscan.net/terms, 2026-09-02)_ |
| 5 | Failure & resume | 502/503/504 upstream errors; 'Eligible failed API requests receive automatic credit refunds'; batch jobs expose status_url, results_url, results_expires_at. _(src: https://domscan.net/docs/products/batch-jobs, 2026-09-02)_ |
| 6 | Cost model | Credits per endpoint 0–9; packs €9/50k, €29/250k, €79/1M, never expire; used credits non-refundable. _(src: https://domscan.net/docs/credits-pricing, 2026-09-02)_ |
| 7 | Usage observability | X-Credits-Remaining header on every authenticated response; machine-readable rate card at /v1/pricing. _(src: https://domscan.net/docs/credits-pricing, 2026-09-02)_ |
| 8 | Health signal | /v1/coverage JSON with rdap_health per TLD (ok, p50_ms, error_rate) + bootstrap_last_updated; /status is 404; no Statuspage. _(src: https://domscan.net/v1/coverage, 2026-09-02)_ |
| 9 | Credential lifecycle | X-API-Key or Bearer; 401 on missing/invalid; expiry/rotation UNKNOWN — tried /docs/authentication. _(src: https://domscan.net/docs/authentication, 2026-09-02)_ |
| 10 | Interface lifecycle | /v1 path; OpenAPI /v1/openapi.json; 'plenty of notice before any pricing changes'; headers UNKNOWN. _(src: https://domscan.net/docs, 2026-09-02)_ |
| 11 | Data contract | Documented per-endpoint response contracts; distinguishes observed/absent/unknown/not-requested; OpenAPI + Postman. _(src: https://domscan.net/docs, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | Batch webhooks (url + secret); job.webhook.status/attempts reported; retry schedule/signature scheme UNKNOWN. _(src: https://domscan.net/docs/products/batch-jobs, 2026-09-02)_ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: 'DomScan / domain-scan API' resolves to domscan.net (Esteve Castells); also on apis.io.


## Observability & error tracking

### Glitchtip

**Type:** infra-platform · **Reach:** self-hosted container on the `fabrik` network · REST API (env key) · **Runs on:** vps1 (`docker ps` 2026-09-02) · **Used by:** 6 project(s) — brand-identiy-creator, calendar-orchestration-engine, session-recall, transdoc, tryton-crm, whatsapp-agent · **Env keys:** `GLITCHTIP_*` · **Docs:** https://glitchtip.com · **Vendor doc:** `docs/reference/apis/glitchtip-api.md`

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — container memory limit **512m** (docs/infrastructure/vps-complete-inventory.md:606); connection/pool caps are the service's own config |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Errors depend on your setup. Can configure retry logic in SDKs. Smallest unit is' but its source is dead/unfetched (https://glitchtip.com/docs/integration); re-verify live |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'No external status page; health of your instance is your responsibility. No vend' but its source is dead/unfetched (no url); re-verify live |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Data schema follows Sentry event envelope spec. Pagination in API. Deletion via ' but its source is dead/unfetched (https://glitchtip.com/docs/api); re-verify live |
| 12 | Push delivery (webhooks/streams) | n/a — no webhooks; a fleet service pushes nothing (alerts flow via Prometheus → Alertmanager → Apprise/Telegram) |
| — | **Resilience posture (58)** | self-hosted on the hub (`glitchtip-web` + `glitchtip-worker`, `docker ps` 2026-09-02); the registrar `src/fabrik/drivers/glitchtip.py` creates the project + DSN on `fabrik apply`; error webhook → the watchdog sidecar's ingest server (`WATCHDOG_INGEST_PORT` default 8889 — /opt/fabrik-lib/watchdog/watchdog_sidecar/agent.py:101) |

- **Research notes** _(2026-09-02)_: Sentry-compatible error tracking; you manage all scaling and reliability.

### Sentry

**Type:** infra-platform · **Reach:** REST API (env key) · **Used by:** 9 project(s) — proxy, rn-kit-sandbox, rnfinal, session-recall, spec:proxy, supplement-tracker-advisor, transdoc, tryton-crm … · **Env keys:** `EXPO_PUBLIC_SENTRY_*`, `SENTRY_*` · **Docs:** https://sentry.io

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Plan-based event/month, attachment size (e.g., 50 MB). Resets monthly. — verify: https://sentry.io/pricing/ |
| 2 | Behaviour AT the cap | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Rate limiting (429) or hard block; overage billing on some plans. — verify: https://docs.sentry.io/accounts/quotas/ |
| 3 | Concurrency & parallelism | UNKNOWN — tried: pool sweep (no fetch capability in read_only mode) searched 'sentry concurrency in-flight', fetched https://docs.sentry.io |
| 4 | Identity posture | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Per organization/DSN; ToS prohibit evading limits (section 3). — verify: https://sentry.io/terms/ |
| 5 | Failure & resume | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Events retried via SDK; idempotent via event ID; no checkpointing. — verify: https://docs.sentry.io/platforms/ |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Per seat + event volume; free tier (5k errors/month); spikes from error surges. — verify: https://sentry.io/pricing/ |
| 7 | Usage observability | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Usage stats in organization settings; no dedicated API endpoint. — verify: https://docs.sentry.io/accounts/quotas/#viewing-usage |
| 8 | Health signal | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Status page at https://status.sentry.io; API at https://status.sentry.io/api/v0/. — verify: https://status.sentry.io |
| 9 | Credential lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): DSN keys do not expire; can be rotated. Auth tokens expire (configurable). — verify: https://docs.sentry.io/api/auth/ |
| 10 | Interface lifecycle | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'API versioned (e.g., /api/0/); deprecation via changelog; 6+ months notice.' but its source is dead/unfetched (https://docs.sentry.io/api/versioning/); re-verify live |
| 11 | Data contract | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Event schema documented; pagination via Link headers; deletion via API. — verify: https://develop.sentry.dev/sdk/data-handling/ |
| 12 | Push delivery (webhooks/streams) | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Webhooks: at-least-once delivery, retry with backoff, event ID, no ordering guarantee. — verify: https://docs.sentry.io/product/integrations/integration-platform/webhooks/ |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Error monitoring; quotas based on events per month.

### Gatus

**Type:** observe · **Reach:** self-hosted container on the `fabrik` network · **Runs on:** vps1 (`docker ps` 2026-09-02) · **Used by:** 0 project(s) — fleet service, no per-project key

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — container memory limit **256m** (docs/infrastructure/vps-complete-inventory.md:609); connection/pool caps are the service's own config |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Status/health-endpoint monitoring (the fleet status page).
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: per-endpoint health checks (HTTP/TCP/cert) with Telegram alerts via the `custom` alert type - Spec-driven: a service spec auto-registers a Gatus endpoint on `fabrik apply` (gatus registrar)
- **Notes** _(2026-06-02 entry)_: - Self-hosted on vps1, on the `fabrik` Docker network - 31 endpoints across 18 YAML files (see `sync_gatus_to_vps.sh --diff` for live count)

### Uptime Kuma

**Type:** infra-platform · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found) · **Docs:** https://uptime.kuma.pet

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | self-host _(catalog `cost`, refreshed daily)_ |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### Prometheus

**Type:** observe · **Reach:** self-hosted container on the `fabrik` network · **Runs on:** vps1 (`docker ps` 2026-09-02) · **Used by:** 0 project(s) — fleet service, no per-project key

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — the limit is OUR configuration (memory limit in compose, connection/pool caps in the service config); see `docs/infrastructure/vps-complete-inventory.md` |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Metrics collection and monitoring
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Metrics collection - Port: 9090 - Config: `/opt/fabrik/configs/prometheus/prometheus.yml`
- **Notes** _(2026-06-02 entry)_: - Self-hosted on VPS - amd64 compatible - Part of monitoring stack

### Grafana

**Type:** infra-platform · **Reach:** self-hosted container on the `fabrik` network · REST API (env key) · MCP `grafana` (agent-time only) · **Runs on:** vps1 (`docker ps` 2026-09-02) · **Used by:** 0 project(s) — fleet service, no per-project key · **Docs:** https://grafana.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — the limit is OUR configuration (memory limit in compose, connection/pool caps in the service config); see `docs/infrastructure/vps-complete-inventory.md` |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | self-host _(catalog `cost`, refreshed daily)_ |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — no webhooks; a fleet service pushes nothing (alerts flow via Prometheus → Alertmanager → Apprise/Telegram) |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Metrics visualization and dashboards
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Metrics dashboards - Port: 3002 - Environment: `GF_SECURITY_ADMIN_PASSWORD`
- **Notes** _(2026-06-02 entry)_: - Self-hosted on VPS - amd64 compatible - Part of monitoring stack

### Loki

**Type:** observe · **Reach:** self-hosted container on the `fabrik` network · **Runs on:** vps1 (`docker ps` 2026-09-02) · **Used by:** 0 project(s) — fleet service, no per-project key

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — the limit is OUR configuration (memory limit in compose, connection/pool caps in the service config); see `docs/infrastructure/vps-complete-inventory.md` |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Log aggregation system
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Log aggregation and querying - Port: 3100 - Config: `/opt/fabrik/configs/loki/loki-config.yaml`
- **Notes** _(2026-06-02 entry)_: - Self-hosted on VPS - amd64 compatible - Part of monitoring stack

### Promtail

**Type:** observe · **Reach:** self-hosted container on the `fabrik` network · **Runs on:** vps1, vps2, vps3 (`docker ps` 2026-09-02) · **Used by:** 0 project(s) — fleet service, no per-project key

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — container memory limit **96m** (docs/infrastructure/vps-complete-inventory.md:620); connection/pool caps are the service's own config |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | EOL upstream; runs on all three hosts (probed 2026-09-02); Alloy migration filed |

- **Purpose** _(2026-06-02 entry)_: Log shipping agent
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Ship logs to Loki - Config: `/opt/fabrik/configs/promtail/promtail-config.yaml`
- **Notes** _(2026-06-02 entry)_: - Self-hosted on VPS - amd64 compatible - Part of monitoring stack

### Alertmanager

**Type:** observe · **Reach:** self-hosted container on the `fabrik` network · **Runs on:** vps1 (`docker ps` 2026-09-02) · **Used by:** 0 project(s) — fleet service, no per-project key

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — the limit is OUR configuration (memory limit in compose, connection/pool caps in the service config); see `docs/infrastructure/vps-complete-inventory.md` |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### Pushgateway

**Type:** observe · **Reach:** self-hosted container on the `fabrik` network · **Runs on:** vps1 (`docker ps` 2026-09-02) · **Used by:** 0 project(s) — fleet service, no per-project key

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — container memory limit **64m** (docs/infrastructure/vps-complete-inventory.md:610); connection/pool caps are the service's own config |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### cAdvisor

**Type:** observe · **Reach:** self-hosted container on the `fabrik` network · **Runs on:** vps1, vps2, vps3 (`docker ps` 2026-09-02) · **Used by:** 0 project(s) — fleet service, no per-project key

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — container memory limit **256m** (docs/infrastructure/vps-complete-inventory.md:619); connection/pool caps are the service's own config |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Container metrics exporter
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Container-level metrics - Port: 8080
- **Notes** _(2026-06-02 entry)_: - Self-hosted on VPS - amd64 compatible - Part of monitoring stack

### Node Exporter

**Type:** observe · **Reach:** self-hosted container on the `fabrik` network · **Runs on:** vps1, vps2, vps3 (`docker ps` 2026-09-02) · **Used by:** 0 project(s) — fleet service, no per-project key

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — container memory limit **64m** (docs/infrastructure/vps-complete-inventory.md:618); connection/pool caps are the service's own config |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### Postgres Exporter

**Type:** observe · **Reach:** self-hosted container on the `fabrik` network · **Runs on:** vps1 (`docker ps` 2026-09-02) · **Used by:** 0 project(s) — fleet service, no per-project key

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — the limit is OUR configuration (memory limit in compose, connection/pool caps in the service config); see `docs/infrastructure/vps-complete-inventory.md` |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### Redis Exporter

**Type:** observe · **Reach:** self-hosted container on the `fabrik` network · **Runs on:** vps1 (`docker ps` 2026-09-02) · **Used by:** 0 project(s) — fleet service, no per-project key

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — the limit is OUR configuration (memory limit in compose, connection/pool caps in the service config); see `docs/infrastructure/vps-complete-inventory.md` |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### Netdata

**Type:** infra-platform · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found) · **Docs:** https://netdata.cloud

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Self-hosted: limits depend on server resources. Cloud: free tier includes 5 nodes, 3 hours retention. — verify: https://www.netdata.cloud/pricing/ |
| 2 | Behaviour AT the cap | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Free tier at cap restricts adding nodes/data. Overages lead to upgrade prompts. — verify: https://www.netdata.cloud/pricing/ |
| 3 | Concurrency & parallelism | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Self-hosted: parallelism scales with CPU cores. Cloud: based on subscription tier. — verify: https://learn.netdata.cloud/docs/agent/daemon |
| 4 | Identity posture | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Self-hosted: N/A. Cloud: one account per user. ToS clause 3.1 (Registration).' but its source is dead/unfetched (https://www.netdata.cloud/legal/terms/); re-verify live |
| 5 | Failure & resume | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Agent retries on failure. Streaming supports resume. Smallest unit is a metric stream. — verify: https://learn.netdata.cloud/docs/agent/health/notifications |
| 6 | Cost model | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Self-hosted: free. Cloud: freemium, then paid per node, retention length, and features. — verify: https://www.netdata.cloud/pricing/ |
| 7 | Usage observability | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Self-hosted: local dashboard. Cloud: account dashboard shows node count, retention. — verify: https://learn.netdata.cloud/docs/cloud |
| 8 | Health signal | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Cloud status: https://status.netdata.cloud. RSS/JSON API available. — verify: https://status.netdata.cloud |
| 9 | Credential lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): API keys/agent claims expire. Expired claim prevents node connection. — verify: https://learn.netdata.cloud/docs/agent/claim |
| 10 | Interface lifecycle | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Versioned releases. Deprecation notices in changelog. Cloud API versioned separately. — verify: https://github.com/netdata/netdata/releases |
| 11 | Data contract | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Metric schema documented. Database retention configurable. Data deletion on expiry. — verify: https://learn.netdata.cloud/docs/store/change-metrics-storage |
| 12 | Push delivery (webhooks/streams) | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Webhooks for notifications support retry. No native push for metric streams. — verify: https://learn.netdata.cloud/docs/agent/health/notifications |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Research notes** _(2026-09-02)_: Strong distinction between open-source agent (limits = your hardware) and cloud service (tiered).

### PostHog

**Type:** observability · **Reach:** ingest API + SDK (project token) / REST API (personal key) · **Used by:** 5 project(s) — fabrik, rn-kit-sandbox, rnfinal, supplement-tracker-advisor, tojlo-mail (code call sites) · **Hosts:** `app.posthog.com`, `posthog.com`, `us.i.posthog.com` · **Env keys:** none in the fleet today (reached without a key; the posture row names the knob a consumer would add) · **Docs:** https://posthog.com/docs/api

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Public ingest (`/i/v0/e`, `/batch`, `/flags`) has NO request-level rate limit; body ≤20 MB (`DATA_UPLOAD_MAX_MEMORY_SIZE`), no cap on events per batch; per-distinct-ID ingestion protection kicks in at roughly 5,000 events/min. Private (personal-API-key) endpoints, limits shared by the WHOLE team/org: analytics endpoints 240/min + 1,200/h; `events/values` 60/min + 300/h; `query` 2,400/h (+ a monthly data-read allowance on unpaid orgs, amount not stated); flag local-evaluation 600/min; all other CRUD 480/min + 4,800/h; invites 50/h + 200/day. 'At this time, we are not offering higher limits' (use Endpoints / batch exports instead). Max 10 personal API keys per user. _(src: https://posthog.com/docs/api, 2026-09-02)_ |
| 2 | Behaviour AT the cap | Private endpoints → 429 with DRF body `{"type":"throttled_error","code":"throttled","detail":"Request was throttled. Expected available in N seconds.","attr":null}` and a `Retry-After` header ('the `Retry-After` header the backend already sets on throttled responses', drf-exceptions-hog); no `X-RateLimit-*` headers documented on posthog.com. Ingest NEVER 429s: over billing quota still returns 200 and names the throttled products in `quota_limited`; the data is dropped ('your additional data is lost forever' once a billing limit is hit); `/flags` returns `quotaLimited:["feature_flags"]` when the flag quota is exceeded. High-volume distinct ID (~5k/min): still 200, but processed unordered and without person-profile updates + an ingestion warning. Free plan: 'Usage stops at the free tier limits'. _(src: https://posthog.com/docs/api · https://github.com/PostHog/posthog/pull/69458 · https://posthog.com/docs/billing/limits-alerts · https://posthog.com/docs/api/flags, 2026-09-02)_ |
| 3 | Concurrency & parallelism | No in-flight cap documented for ingest; rate-limit buckets are per team, so parallel scripts on different personal keys share ONE bucket ('if a script … hits the rate limit … another user, using a different personal API key … gets rate limited as well'). Hog/webhook destinations: max 5 `fetch` calls per invocation, tight execution-time/memory controls. Python SDK default: 1 consumer thread, `max_queue_size=10000`, `flush_at=100`, `flush_interval=0.5s`, queue full → warning + event dropped. _(src: https://posthog.com/docs/api · https://posthog.com/docs/cdp/destinations/customizing-destinations · https://github.com/PostHog/posthog-python/blob/master/posthog/client.py, 2026-09-02)_ |
| 4 | Identity posture | Per organization → projects (Free: 1 project; paid: 6). ToS §2.1(d) forbids using the service 'in a manner intended to circumvent or exceed any usage limits, service capacity limits, account limitations'; §2.1(b) forbids reselling / making it available to third parties; PostHog 'may update these terms occasionally' at its discretion. No explicit one-account-per-entity clause in the fetched text (bounded: terms fetched through §4.5, ~30k chars) — UNKNOWN beyond that. _(src: https://posthog.com/terms · https://posthog.com/pricing, 2026-09-02)_ |
| 5 | Failure & resume | 200 `{"status":"Ok"}` = received + token valid, NOT ingested. Idempotency = event `uuid`: events with the same `uuid` + `event` + `timestamp` + `distinct_id` are EVENTUALLY de-duplicated (ClickHouse background merges — 'deduping based on event UUID is not guaranteed'); re-sending the same key upserts/replaces the event. Invalid UUID → event dropped; >23h-future events ingested but hidden; >1 MB events discarded. Backfills: `historical_migration:true` on `/batch` to bypass spike detection. Python SDK: buffered queue, `max_retries=3`, `on_error` callback, `shutdown()` before exit or buffered events are lost (`sync_mode` for per-call delivery); upcoming v1 transport treats 429 as terminal and retries only 5xx honouring `Retry-After`. Smallest resumable unit = one event (by uuid). _(src: https://posthog.com/docs/data/events · https://posthog.com/docs/data/ingestion-warnings · https://posthog.com/docs/api/capture · https://posthog.com/docs/references/posthog-python, 2026-09-02)_ |
| 6 | Cost model | Two plans, $0 base, no per-seat charges. Free: 1M events/mo, 1 project, 1-yr retention, community support. Paid (PAYG): same monthly free tier, 6 projects, 7-yr retention, email support. Product analytics per event: 1,000,001–2M $0.00005 · 2M–15M $0.0000343 · 15M–50M $0.0000295 · 50M–100M $0.0000218 · 100M–250M $0.000015 · >250M $0.000009. Add-ons (each 1M free/mo): identified events from $0.000198, group analytics from $0.000071, data pipelines from $0.000062; realtime destinations 10k trigger events free then $0.0005. Spike = metered overage unless a per-product billing limit is set (then data is dropped, never billed over). _(src: https://posthog.com/pricing · https://posthog.com/docs/billing/limits-alerts, 2026-09-02)_ |
| 7 | Usage observability | Billing API (personal key, `billing:read`, org admin): `GET /api/billing/` (products, limits, `usage_summary`, `current_usage`/`percentage_usage`), `GET /api/billing/usage/` + `/spend/` (params `start_date,end_date,usage_types,team_ids,breakdowns,interval`; response `{results:[{label,data[],dates[]}],…}`), `GET /api/billing/period/`. Owner alert emails at 80% and 100% of each billing limit AND of the free allotment. Ingest responses carry `quota_limited`; ingestion warnings (sampled) in-app + MCP `ingestion-warnings-list`. No rate-limit headers documented on posthog.com. _(src: https://posthog.com/docs/api/billing-2 · https://posthog.com/docs/billing/limits-alerts · https://posthog.com/docs/api, 2026-09-02)_ |
| 8 | Health signal | NOT Statuspage-compatible: `status.posthog.com/api/v2/status.json` serves an HTML env picker (301 → www.posthogstatus.com); `www.posthogstatus.com/api/v2/status.json`, `/us/api/v2/status.json`, `/summary.json`, `/us/status.json` all 404. Self-built page (no provider attribution found) with its own JSON: `https://www.posthogstatus.com/api/status` → `{"generated_at":"2026-09-02T09:59:22.272Z","overall_status":"operational","component_groups":[{name:"US Cloud 🇺🇸",components:[{id,name,status,description}…]},{name:"EU Cloud 🇪🇺"…}]}`; today US 'Event Ingestion Success', 'REST API Query endpoints', 'All other REST API endpoints' = operational. Also `errorsWhileComputingFlags:true` in `/flags` responses during flag incidents. _(src: https://www.posthogstatus.com/api/status · https://posthog.com/docs/api/flags, 2026-09-02)_ |
| 9 | Credential lifecycle | Three secrets: project token (public, in the ingest body `api_key`; invalid → 401 `invalid_api_key`), personal API key `phx_*` (private endpoints, Bearer or `personal_api_key` body; invalid → 401 `invalid_personal_api_key`), project secret key `phs_*` (beta, server-to-server). Personal keys: up to 10 per user, scoped (scopes editable later), value shown ONCE, each individually invalidatable, deleted with the user, no expiry documented → overlap rotation by creating a second key; 'Roll key' mints a new value and invalidates the old. GitHub secret scanning auto-rolls leaked `phx_`/`phs_` keys and emails the owner; org admins can audit all keys (masked `phx_***1234`, scopes, last used). _(src: https://posthog.com/docs/api/personal-api-keys · https://posthog.com/docs/api, 2026-09-02)_ |
| 10 | Interface lifecycle | No published deprecation/sunset policy (UNKNOWN — tried https://posthog.com/docs/api, https://posthog.com/changelog, https://posthog.com/terms). Versioning is per-endpoint via path (`/i/v0/e`) or query (`/flags?v=2`); no Deprecation/Sunset headers documented. Live precedent: `/decide` → `/flags`: `/flags` live everywhere by 2025-06, `/decide?v=3`→`/flags?v=1` and `?v=4`→`?v=2` proxied at the edge from 2025-08, `/decide` code deleted (PR #45292, checklist closed 2026-02-22), `docs/api/decide` now serves the flags page — i.e. old routes are silently proxied, not 410'd. Inline '(Deprecated)' markers in docs (503 `fetch_team_fail`). ToS: terms may change at PostHog's discretion; fee changes on 30 days' notice. _(src: https://github.com/PostHog/posthog/issues/33636 · https://posthog.com/docs/api/decide · https://posthog.com/docs/api · https://posthog.com/terms, 2026-09-02)_ |
| 11 | Data contract | Ingest body `{api_key, event, distinct_id, properties?, timestamp? (ISO 8601), uuid?}`; batch `{api_key, historical_migration?, batch:[…]}`; `distinct_id` ≤200 chars (longer → truncated + warning), `$group_type`/`$group_key` ≤400, event ≤1 MB post-processing, body ≤20 MB; `$process_person_profile:false` for anonymous. Success `{"status":"Ok"}` (+ `quota_limited[]` when throttled); errors `{type, code, detail, attr}` (400 `invalid_project`/`invalid_payload`, 401 as row 9). Private lists `{next, previous, results[]}` cursor-paginated, page size 'usually 100 (sometimes 500 or 1000)'; OpenAPI spec downloadable when logged in. _(src: https://posthog.com/docs/api/capture · https://posthog.com/docs/api · https://posthog.com/docs/data/ingestion-warnings, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | Realtime 'Webhook' destination (CDP): POST with a templated JSON body (globals `event{uuid,event,distinct_id,properties,timestamp,url}`, `person`, `groups`, `project`); expects 2xx, 'retry up to 3 times depending on the error codes' (4xx NOT treated as failure, 5xx/slow responses quarantine → auto re-enable attempt → disabled); no ordering guarantee documented; dedup on `event.uuid` (re-ingested events 'may re-trigger or duplicate rows'); NO HMAC signature documented — auth is whatever headers/secret `inputs` you template (secrets encrypted at rest); stable egress IPs US 44.205.89.55, 52.4.194.122, 44.208.188.173 / EU 3.75.65.221, 18.197.246.42, 3.120.223.253. Batch exports (Temporal): hourly/daily runs bounded by ClickHouse landing time, automated + manual retries, backfills, events keyed by UUID for de-duplication. _(src: https://posthog.com/docs/cdp/destinations · https://posthog.com/docs/cdp/destinations/webhook · https://posthog.com/docs/cdp/destinations/customizing-destinations · https://posthog.com/docs/cdp/batch-exports · https://posthog.com/docs/data/events, 2026-09-02)_ |
| — | **Resilience posture (58)** | product analytics; ingest via SDK buffer + `shutdown()` on exit + client-set `uuid` for dedup; per-product billing limit set in-dashboard (drops, never overbills); webhook receiver = public route + templated secret header checked in handler (no vendor HMAC) (57 § Doc Sync) |

- **Research notes** _(2026-09-02)_: vendor status: https://www.posthogstatus.com/us (status.posthog.com 301s here; machine-readable JSON at https://www.posthogstatus.com/api/status — NOT Statuspage-shaped, see row 8).

### Axiom

**Type:** observability · **Reach:** ingest + query REST API (token) · **Used by:** 1 project(s) — tojlo-mail (code call sites) · **Hosts:** `api.axiom.co` · **Env keys:** none in the fleet today (reached without a key; the posture row names the knob a consumer would add) · **Docs:** https://axiom.co/docs (machine-readable index: https://axiom.co/docs/llms.txt; REST intro: https://axiom.co/docs/restapi/introduction)

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | Three metered limits, each with its own headers on every response: request rate per minute (`X-RateLimit-Limit/-Remaining/-Reset`, scope `user` or `organization` via `X-RateLimit-Scope`; the numeric per-minute value is NOT published — read the header), query compute in GB·ms (`X-QueryLimit-*`), ingest bytes per month (`X-IngestLimit-*`). System-wide ingest caps: 1 MB max field size, 10,000 events per batch, 200-byte field names; OTel `/v1/metrics` request ≤4 MiB uncompressed. Plan caps: Personal = 500 GB/mo loading (hard max), 10 GB-hours/mo query, 25 GB storage, 30-day retention, 3 datasets, 256 fields/dataset, 1 user, 3 monitors, US edge only; Axiom Cloud = 1 TB/mo, 100 GB-hours, 100 GB storage included, retention custom, 100 datasets / 1,024 fields / 1,000 users / 500 monitors (soft, raisable). _(src: https://axiom.co/docs/restapi/api-limits + https://axiom.co/docs/reference/limits, 2026-09-02)_ |
| 2 | Behaviour AT the cap | Rate/query/ingest limit exceeded → `429 Too Many Requests` body `{"message":"rate limit exceeded"}`; a token's hourly/daily query-cost $ cap exceeded → its queries 429 until the window resets (ingest unaffected). Sustained excessive ingest requests/sec → Axiom "reserves the right to suspend their ingest" / "temporarily restrict or disable your ability to send data" (account-specific, lifted via Support). OTel metrics request >4 MiB → `413` (Collector treats as permanent, drops batch). Event exceeding the dataset field limit → error, event rejected. Axiom Cloud: usage beyond the Always Free allowance is billed pay-as-you-go automatically; an in-console spending limit PAUSES usage instead of billing. Personal: 500 GB/mo is a hard maximum; behaviour on reaching it not stated — UNKNOWN (tried pricing, reference/limits, api-limits). _(src: https://axiom.co/docs/restapi/api-limits + https://axiom.co/docs/reference/limits + https://axiom.co/pricing, 2026-09-02)_ |
| 3 | Concurrency & parallelism | No numeric in-flight cap published; rate limit is a per-minute bucket at user OR organization scope (`X-RateLimit-Scope`). Ingest request RATE (req/s) is monitored separately from bytes — "highly recommended to use batching clients". "Query concurrency" is listed as a soft limit on both plans, liftable on request. Per-token hourly/daily query-cost $ caps are the documented per-caller brake. _(src: https://axiom.co/docs/restapi/api-limits + https://axiom.co/pricing, 2026-09-02)_ |
| 4 | Identity posture | Per organization (org ID like `axiom-abcd`); Personal plan = 1 user / 3 datasets / US edge only, no credit card; account data + billing always processed in US infrastructure regardless of edge. ToS: no-fee/trial use is "as-is basis without support, warranty, or indemnification"; suspension immediate on security risk, 30-day notice on breach; Customer Data may be irretrievably deleted 15 days after termination. No explicit one-account-per-entity clause in the fetched ToS text — UNKNOWN beyond that. _(src: https://axiom.co/terms + https://axiom.co/docs/reference/edge-deployments + https://axiom.co/docs/reference/limits, 2026-09-02)_ |
| 5 | Failure & resume | Ingest is per-batch partial-accept: 200 with `{ingested, failed, failures[{error,timestamp}], processedBytes, blocksCreated, walLength}` — inspect `failed`, not the status code. Oversize strings/binary are REPLACED (not rejected); nesting >100 levels truncated to `nil`; NaN/±Inf → `nil`. No idempotency key / dedup-on-ingest documented — UNKNOWN (tried restapi/ingest, endpoints/ingestToDataset, api-limits); duplicates are expected ("backfill or natural duplication") and Axiom recommends client-side dedup. Query pagination: timestamp-based recommended (cursor-based in public preview, "may return unexpected query results"); default 1,000 events/page; set the same `limit` in request AND APL. Smallest resumable unit = one ingest batch (≤10,000 events). _(src: https://axiom.co/docs/restapi/endpoints/ingestToDataset + https://axiom.co/docs/reference/limits + https://axiom.co/docs/restapi/pagination, 2026-09-02)_ |
| 6 | Cost model | Personal $0/mo permanent (500 GB load, 10 GB-hours, 25 GB storage, 30-day retention, community support). Axiom Cloud $25/mo platform fee incl. 1 TB load / 100 GB-hours / 100 GB storage, then usage-based with automatic volume discounts; pre-purchased credits up to 30% off, never expire; add-ons SSO $100/mo, Directory Sync $100/mo, RBAC $50/mo, Audit Log $50/mo; email support incl., SLA/dedicated add-ons. Spike = pay-as-you-go overage unless an in-console spend limit pauses it. Retention-only data priced at 0.01x data loading. _(src: https://axiom.co/pricing + https://axiom.co/docs/reference/limits, 2026-09-02)_ |
| 7 | Usage observability | Every response carries remaining/reset for all three buckets (`X-RateLimit-Remaining/-Reset`, `X-QueryLimit-Remaining/-Reset`, `X-IngestLimit-Remaining/-Reset`) — self-throttle before 429. Per-dataset allowance usage in Settings > Usage; a token's page shows usage against its query-cost caps; spend alerts + hard caps in-console (Axiom Cloud). No usage/billing REST endpoint found — UNKNOWN (tried the https://axiom.co/docs/llms.txt index, api-limits, reference/limits). _(src: https://axiom.co/docs/restapi/api-limits + https://axiom.co/docs/reference/limits, 2026-09-02)_ |
| 8 | Health signal | https://status.axiom.co is incident.io-hosted ("We're fully operational", US Region 6 components / EU Region 6 components, 100% uptime Jun–Sep 2026). Machine-readable: `GET https://status.axiom.co/api/v1/summary` returned `{"ongoing_incidents":[],"in_progress_maintenances":[],"scheduled_maintenances":[]}` today (no components list, no top-level status field); RSS at https://status.axiom.co/feed.rss (latest: "Console UI Authentication Degraded" 2026-08-12, "Elevated Queries error rate" 2026-07-15, "Ingest through Firehose impacted" 2026-06-30, all resolved). _(src: https://status.axiom.co/api/v1/summary + https://status.axiom.co/feed.rss, 2026-09-02)_ |
| 9 | Credential lifecycle | Two token types: API tokens (prefix `xaat-`; Basic = ingest-only, dataset-scoped; Advanced = custom permission set or preset, optional query-cost $ caps) and Personal Access Tokens (full account control, require `x-axiom-org-id` header; not accepted by the edge ingest endpoint). Optional expiration date at creation; privileges immutable after creation; value shown once. Rotation = "Regenerate token" (new value, same token, "update all the API requests") or create-new + delete for overlap; Axiom recommends regular rotation + expiry. Bad/missing token → `403`. Sent as `Authorization: Bearer <token>`. _(src: https://axiom.co/docs/reference/tokens + https://axiom.co/docs/restapi/introduction + https://axiom.co/docs/restapi/endpoints/ingestToDataset, 2026-09-02)_ |
| 10 | Interface lifecycle | Path-versioned: `/v1/...` and `/v2/...` on `https://api.axiom.co` (V2 introduced 2025-04-22 for datasets/users + new resource CRUD; "V1 endpoints continue to be supported and you can use them as before"). Ingest/query moved to per-edge domains (`us-east-1.aws.edge.axiom.co`, `eu-central-1.aws.edge.axiom.co`, `POST /v1/ingest/{dataset}`, `POST /v1/query/_apl?format=tabular\|legacy`); `api.axiom.co/v1/datasets/{name}/ingest\|query` are documented as "legacy" but still served. OpenAPI self-describes as "A public and stable API", info.version 2.0.0. No Deprecation/Sunset headers, no sunset dates or deprecation window published — UNKNOWN (tried changelog, changelog/v2-endpoints, restapi/introduction, endpoints/ingestIntoDataset). _(src: https://axiom.co/changelog/v2-endpoints + https://axiom.co/docs/restapi/introduction + https://axiom.co/docs/restapi/endpoints/ingestIntoDataset, 2026-09-02)_ |
| 11 | Data contract | Ingest body JSON array / NDJSON / CSV (`Content-Type` application/json, application/x-ndjson, text/csv); optional `timestamp-field`, `timestamp-format` (Go reference layout), `csv-delimiter`, headers `X-Axiom-CSV-Fields`, `X-Axiom-Event-Labels` (JSON object). Response `{ingested, failed, failures[{error,timestamp}], processedBytes, blocksCreated, walLength}`. Errors are JSON `{"message": ...}`. Auto fields `_time` (event time; many formats accepted) and `_sysTime` (ingest time); reserved `_blockInfo/_cursor/_rowID/_source/_sysTime` get renamed `_user_<name>`. Tabular query response `{format, status{elapsedTime, isPartial, rowsExamined, rowsMatched, minCursor, maxCursor, ...}, tables[{name, sources, fields[{name,type}], order, range, columns[][]}], datasetNames, fieldsMetaMap}`. _(src: https://axiom.co/docs/restapi/endpoints/ingestToDataset + https://axiom.co/docs/reference/limits + https://axiom.co/docs/restapi/query, 2026-09-02)_ |
| 12 | Push delivery (webhooks/streams) | Only outbound push is monitor → notifier. Custom webhook notifier: POST `application/json` + any headers you set, body is a Go template over `.Action` (`Open`/`Closed`), `.MonitorID`, `.Body`, `.Title`, `.Value`, `.Timestamp`, `.QueryStartTime/.QueryEndTime`, `.MatchedEvent`, `.GroupKeys/.GroupValues`; dedup pattern = `.MonitorID` as `deduplication_key`; threshold monitors stay Open and do not re-alert until they resolve. No vendor signature/HMAC, no retry schedule, no delivery log documented — UNKNOWN (tried custom-webhook-notifier, configure-notifiers, notifiers-overview); authenticate the receiver with a secret header you add in the notifier. Personal plan notifiers = Email + Discord only; webhooks need Axiom Cloud. Streams: no server-push/streaming API for consumers documented (Stream tab is Console-only). _(src: https://axiom.co/docs/monitor-data/custom-webhook-notifier + https://axiom.co/docs/reference/limits + https://axiom.co/docs/monitor-data/notifiers-overview, 2026-09-02)_ |
| — | **Resilience posture (58)** | log/event sink off the request path: batch + buffer client-side, read `X-*Limit-Remaining` to self-throttle, treat `failed>0` in a 200 as partial loss, and on 429/ingest-suspension drop-or-spool — never block the caller; webhook receiver = public route + operator-set secret header checked in handler (no vendor HMAC; 57 § Doc Sync) |

- **Research notes** _(2026-09-02)_: vendor status: https://status.axiom.co (incident.io; JSON at https://status.axiom.co/api/v1/summary, RSS at https://status.axiom.co/feed.rss).

## Automation & developer tools

### n8n

**Type:** infra-platform · **Reach:** self-hosted container on the `fabrik` network · REST API (env key) · **Runs on:** vps1 (`docker ps` 2026-09-02) · **Used by:** 1 project(s) — fabrik · **Env keys:** `N8N_*` · **Docs:** https://n8n.io

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | self-operated — container memory limit **2g** (docs/infrastructure/vps-complete-inventory.md:598); connection/pool caps are the service's own config |
| 2 | Behaviour AT the cap | self-operated — behaviour at the cap is the service's own (connection refused / OOM-kill → `restart:` policy, 58 row 9); no vendor throttling |
| 3 | Concurrency & parallelism | self-operated — concurrency = our worker count vs the service's connection limit; scoped per container |
| 4 | Identity posture | n/a — no vendor identity; access is network-scoped to the `fabrik` net (+ Authelia where admin-facing) |
| 5 | Failure & resume | UNKNOWN — tried: pool sweep 2026-09-02 suggested 'Configurable retry logic in nodes; idempotency depends on target service; execut' but its source is dead/unfetched (https://docs.n8n.io/workflows/executions/retry-executions/); re-verify live |
| 6 | Cost model | self-operated — cost is the host's memory/disk budget (`deploy.resources.limits.memory` is mandatory); no per-call billing |
| 7 | Usage observability | self-operated — Prometheus exporters + Grafana on the hub (`postgres-exporter`, `redis-exporter`, `cadvisor`, `node-exporter` — `docker ps` 2026-09-02) |
| 8 | Health signal | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Cloud status: https://status.n8n.io. Machine-readable via Atlassian Statuspage API. — verify: https://status.n8n.io |
| 9 | Credential lifecycle | self-operated — credentials are minted by the registrar / compose env and rotate on OUR schedule (58 § credential lifecycle applies to the consumer) |
| 10 | Interface lifecycle | self-operated — the interface changes when WE bump the image tag (`30-ops` pins; D-062 marker spans); no vendor deprecation channel |
| 11 | Data contract | UNVERIFIED (pool sweep 2026-09-02 — plausible, not fetched): Workflow and data schemas in docs. Pagination in certain nodes. Deletion via UI or DELETE calls. — verify: https://docs.n8n.io/api/ |
| 12 | Push delivery (webhooks/streams) | n/a — no webhooks; a fleet service pushes nothing (alerts flow via Prometheus → Alertmanager → Apprise/Telegram) |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Workflow automation platform
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Workflow automation, webhooks - Domain: `https://auto.vps1.ocoron.com` - Port: 5678
- **Notes** _(2026-06-02 entry)_: - Self-hosted on VPS - amd64 compatible - Integrates with Apprise for notifications
- **Research notes** _(2026-09-02)_: Core differentiation between self-hosted (full control) and cloud (managed service).

### Semgrep

**Type:** dev-tools · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found) · **Docs:** https://semgrep.dev

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | - Free: 100 scans/month - Team: Unlimited _(carried from the 2026-06-02 entry — re-verify)_ |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | freemium _(catalog `cost`, refreshed daily)_ |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | - Type: API Token - Env Vars: `SEMGREP_APP_TOKEN` - Generate at: Semgrep Dashboard → Settings → API Tokens — expiry/rotation UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

- **Purpose** _(2026-06-02 entry)_: Static analysis security scanning
- **Endpoints** _(2026-06-02 entry)_: - Base URL: `https://semgrep.dev/api/v1` - Scan Repository: `POST /deployments` - Get Results: `GET /deployments/{id}`
- **Usage in Fabrik** _(2026-06-02 entry)_: - Functions: Security scanning in CI/CD
- **Notes** _(2026-06-02 entry)_: - Token: `web_mobasak_valid-from-2026-02-23`

### Postman

**Type:** dev-tools · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found) · **Docs:** https://postman.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | freemium _(catalog `cost`, refreshed daily)_ |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | n/a — pull-only integration |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |

### Puter

**Type:** infra-platform · **Reach:** REST API (env key) · **Used by:** 0 project(s) (no env key/spec reference found) · **Docs:** https://puter.com

| # | Field | Value (source) |
|---|---|---|
| 1 | Limits & quota | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 2 | Behaviour AT the cap | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 3 | Concurrency & parallelism | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 4 | Identity posture | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 5 | Failure & resume | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 6 | Cost model | freemium _(catalog `cost`, refreshed daily)_ |
| 7 | Usage observability | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 8 | Health signal | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 9 | Credential lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 10 | Interface lifecycle | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 11 | Data contract | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| 12 | Push delivery (webhooks/streams) | UNKNOWN — tried: catalog, the 2026-06-02 entry, rules corpus, vendor docs; live re-verify pending |
| — | **Resilience posture (58)** | per-dependency card owed in the consuming project's `docs/RESILIENCE.md` §2b (timeout · retry layer · breaker · pause key · failover · backup) — this index records the VENDOR side only |


## Retired / decommissioned — kept so nobody re-proposes them

| System | Disposition |
|---|---|
| Coolify | decommissioned 2026-05-30 — deploy is SSH + Compose via `fabrik apply` (D-001 era); 30 inventory mentions are history |
| Factory AI | RETIRED (memory: never propose Factory); 5 env keys are residue to clean at each project's next touch |
| Kilo | RETIRED with Windsurf/Cascade — LLM access is Claude Max OAuth + OpenRouter only |
| Context7 | RETIRED from the roster (D-003) — official-docs WebFetch covers the need |
| Supabase | RETIRING as a runtime target (self-host by default) — 11 specs still reference it; keep the entry until the last migrates (trade-intelligence) |
| Promtail | END-OF-LIFE upstream (2026-03-02) and STILL RUNNING on hub + both spokes — migration to Alloy filed (mail 01M1EQ3NCA98EF178ZY366V47T) |
| `tco` (catalog `research-data`) | **NOT AN EXTERNAL VENDOR** — `TCO_API_KEY` points at the internal `triggered-content-orchestration` python-api on port 8025 (`PORTS.md:123`); its only consumer was the archived `wpf` (`/opt/archived/wpf/docs/CONFIGURATION.md:22`). The catalog row is a misclassification — reclassify or delete at the catalog's next touch (grounded live 2026-09-02) |


## Removed from this index 2026-09-02 — no fleet signal

These entries existed in the 2026-06-02 version as generic self-hosted/WordPress-era references. Measured against the denominator above (env keys in 40 `.env.example` files + 72 specs, `docker ps` on all three hosts, the catalog): **zero** signal for each. They are in git history if a project ever adopts one — then it gets a real block.

Plex, Jellyfin, Emby, qBittorrent, SABnzbd, NZBGet, Heimdall, Homer, Organizr, Borg, OpenVPN (1 inventory mention, not running on any host), Code Server, Gitea, Caddy, LinuxServer.io, hotio.dev, TrueForge/ContainerForge, Yoast SEO, Rank Math, WPForms, Contact Form 7, Google Analytics 4, Google Tag Manager, Gmail SMTP, Let's Encrypt
