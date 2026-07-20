# Fabrik External Systems & APIs

**Last Updated:** 2026-06-02 (Coolify section removed; deploy mechanism is now SSH+Compose via `fabrik apply`)

This document catalogs all external systems, APIs, and services that Fabrik integrates with, along with their API documentation links, authentication methods, and usage patterns.

---

## Table of Contents

1. [Infrastructure & Deployment](#infrastructure--deployment)
2. [DNS & Domains](#dns--domains)
3. [Storage & Backups](#storage--backups)
4. [Databases & Caching](#databases--caching)
5. [Email & Communication](#email--communication)
6. [Translation Services](#translation-services)
7. [AI/LLM Services](#aillm-services)
8. [Image & Media APIs](#image--media-apis)
9. [Scraping & Automation](#scraping--automation)
10. [Monitoring & Observability](#monitoring--observability)
11. [Security & Code Quality](#security--code-quality)
12. [Development Tools](#development-tools)

---

## Infrastructure & Deployment

### SSH + Docker Compose (active deploy mechanism since 2026-05-30)

**Purpose:** Fabrik's active deploy mechanism — replaces Coolify (removed 2026-05-30).

**How it works:**
- `fabrik apply specs/services/<id>.yaml` SSHes to the target VPS (`vps1`/`vps2`/`vps3`) and runs `docker compose up -d`
- Per-spec `target_vps` field routes to the right host (default `vps1`)
- All containers have stable `container_name:` (Lesson 22) so `docker exec` / `docker inspect` targeting is deterministic

**Code:**
- Driver: [`src/fabrik/orchestrator/deployer_ssh.py`](../../../src/fabrik/orchestrator/deployer_ssh.py)
- Bootstrap a fresh spoke: [`scripts/bootstrap/bootstrap-vps.sh`](../../../scripts/bootstrap/bootstrap-vps.sh) (14 idempotent steps)

**No external API; no rate limits.**

<!-- Coolify "external system" entry removed 2026-06-02 (coolify-residue-cleanup plan).
     `drivers/coolify.py` remains as archived legacy for the few CLI commands
     (`fabrik status`, `fabrik logs`, `fabrik reconcile-all`) that haven't been
     ported off the legacy API client; they are non-functional since the
     Coolify removal but the modules are intentionally retained. -->

---

### VPS (GreenCloudVPS)

**Purpose:** Virtual Private Server hosting

**Documentation:**
- Panel: https://greencloudvps.com
- VNC Console: Available when SSH is down

**Authentication:**
- Type: SSH Key + Password
- Env Vars: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_ROOT_PASSWORD`
- SSH Config: `~/.ssh/config` (alias: `vps`)

**Connection:**
- SSH: `ssh vps` (uses id_ed25519 key)
- IP: 172.93.160.197
- User: ozgur

**Usage in Fabrik:**
- Driver: SSH-based Docker commands
- Functions: Execute WP-CLI, Docker operations

**Notes:**
- Ubuntu 24.04 LTS
- amd64 architecture
- Requires passphrase-protected SSH key

---

## DNS & Domains

### Namecheap DNS

**Purpose:** Domain registration and DNS management

**Documentation:**
- API Docs: https://www.namecheap.com/support/api/methods/
- Developer Portal: https://www.namecheap.com/developer/

**Authentication:**
- Type: API Key + Username
- Env Vars: `NAMECHEAP_API_KEY`, `NAMECHEAP_API_USER`, `NAMECHEAP_CLIENT_IP`
- IP Whitelist: Required

**Key Endpoints:**
- Base URL: `https://api.namecheap.com/xml.response`
- Get Domains: `namecheap.domains.getDomainsList`
- Set Hosts: `namecheap.domains.dns.setHosts`
- DNS Records: `namecheap.domains.dns.getHosts`

**Usage in Fabrik:**
- Driver: `/opt/fabrik/src/fabrik/drivers/dns.py`
- Service URL: `https://provision.vps1.ocoron.com` (internal proxy)
- Functions: Create/update DNS records

**Rate Limits:**
- Standard: 10 requests/minute
- Premium: 50 requests/minute

**Notes:**
- Destructive API (setHosts replaces all records)
- Fabrik uses internal proxy service for safer operations

---

### Cloudflare DNS

**Purpose:** DNS management with per-record operations

**Documentation:**
- API Docs: https://developers.cloudflare.com/api/
- DNS API: https://developers.cloudflare.com/api/resources/dns/

**Authentication:**
- Type: Bearer Token
- Env Vars: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`
- Generate at: Cloudflare Dashboard → My Profile → API Tokens

**Key Endpoints:**
- Base URL: `https://api.cloudflare.com/client/v4`
- List Zones: `GET /zones`
- Get Zone ID: `GET /zones?name={domain}`
- List Records: `GET /zones/{zone_id}/dns_records`
- Create Record: `POST /zones/{zone_id}/dns_records`
- Update Record: `PATCH /zones/{zone_id}/dns_records/{id}`
- Delete Record: `DELETE /zones/{zone_id}/dns_records/{id}`

**Usage in Fabrik:**
- Driver: `/opt/fabrik/src/fabrik/drivers/cloudflare.py`
- Functions: Per-record CRUD operations (safer than Namecheap)

**Rate Limits:**
- Free: 1,200 requests/5 minutes
- Pro: 10,000 requests/5 minutes

**Notes:**
- Safer than Namecheap (per-record operations)
- Supports proxying (Cloudflare CDN)

---

## Storage & Backups

### Backblaze B2

**Purpose:** Cloud object storage for backups

**Documentation:**
- API Docs: https://www.backblaze.com/b2/docs/
- Quick Start: https://www.backblaze.com/b2/docs/introduction.html
- Python SDK: https://github.com/Backblaze/b2-command-line-tool

**Authentication:**
- Type: Application Key
- Env Vars: `B2_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`
- Generate at: B2 Console → Buckets → App Keys → Add New Application Key

**Key Endpoints:**
- Base URL: `https://api.backblazeb2.com/b2api/v2`
- Authorize Account: `b2_authorize_account`
- List Buckets: `b2_list_buckets`
- Upload File: `b2_upload_file`
- Download File: `b2_download_file_by_id`
- List Files: `b2_list_file_names`

**Usage in Fabrik:**
- Functions: Encrypted backups of project data
- Bucket: `vps1-ocoron-backups`

**Rate Limits:**
- Class A (transactions): 2,500/day (free)
- Class B (downloads): 10 GB/day (free)
- Class C (storage): 10 GB (free)

**Notes:**
- Requires encryption passphrase for backup security
- S3-compatible API

---

### Backrest (restic) — active backup tool since 2026-04-17

**Purpose:** Backup orchestration UI over `restic`. Replaced Duplicati 2026-04-17.

**Documentation:**
- GitHub: https://github.com/garethgeorge/backrest
- restic: https://restic.net/

**Authentication:**
- Type: Password (web UI)
- Web UI: `https://backup.vps1.ocoron.com`
- Config: `/opt/backrest/config/config.json` on vps1

**Usage in Fabrik:**
- Functions: scheduled restic snapshots to Backblaze B2 (encrypted, deduplicated)
- Plans (vps1): `b2-vps1` covers `postgres-dumps`, `docker-volumes`, `opt-configs`, `host-state`; each spoke (vps2/vps3) runs its own 2 plans
- restic 0.18.1 runs inside the backrest container

**Notes:**
- The `backrest` Gatus endpoint monitors its health
- Spec-driven: a service's `shape.has_persistent_data: true` triggers a Backrest plan registrar on `fabrik apply`

---

### Cloudflare R2

**Purpose:** S3-compatible object storage

**Documentation:**
- API Docs: https://developers.cloudflare.com/r2/api/
- S3 Compatibility: https://developers.cloudflare.com/r2/api/s3-compatibility/

**Authentication:**
- Type: Access Key + Secret Key
- Env Vars: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`
- Generate at: Cloudflare Dashboard → R2 → Manage R2 API Tokens

**Key Endpoints:**
- Base URL: `https://<account_id>.r2.cloudflarestorage.com`
- S3-compatible: Use AWS SDK with R2 endpoint
- List Objects: `GET /<bucket>`
- Upload Object: `PUT /<bucket>/<key>`
- Download Object: `GET /<bucket>/<key>`
- Delete Object: `DELETE /<bucket>/<key>`

**Usage in Fabrik:**
- Functions: File storage for projects
- Bucket: `fabrik-files`
- Endpoint: `https://066f5cf1dfe20ba18549a592809aa080.r2.cloudflarestorage.com`

**Rate Limits:**
- Class A (write): 3,000 requests/day (free)
- Class B (read): 10,000,000 requests/day (free)
- Class C (storage): 10 GB (free)

**Notes:**
- S3-compatible (use AWS SDK)
- No egress fees
- Better for global distribution than B2

---

## Databases & Caching

### PostgreSQL

**Purpose:** Relational database

**Documentation:**
- Official Docs: https://www.postgresql.org/docs/
- Python Driver: https://www.psycopg.org/docs/

**Authentication:**
- Type: Username + Password
- Env Vars: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- Connection String: `postgresql://user:pass@host:port/db`

**Usage in Fabrik:**
- Shared instance: `postgres-main`
- Project-specific databases: youtube_pipeline, proxy_management, translator_service, calendar_engine, llm_batch

**Notes:**
- Shared across multiple projects
- Requires connection pooling for high concurrency

---

### Redis

**Purpose:** In-memory data store (cache, queues)

**Documentation:**
- Official Docs: https://redis.io/docs/
- Python Client: https://redis-py.readthedocs.io/

**Authentication:**
- Type: Connection URL
- Env Vars: `REDIS_HOST`, `REDIS_PORT`, `REDIS_URL`
- Connection String: `redis://host:port`

**Usage in Fabrik:**
- Shared instance: `redis-main`
- Functions: Caching, job queues, rate limiting

**Notes:**
- Shared across multiple projects
- Requires persistence configuration

---

### Supabase

**Purpose:** Backend-as-a-Service (PostgreSQL + Auth + Storage)

**Documentation:**
- Official Docs: https://supabase.com/docs
- API Reference: https://supabase.com/docs/reference/javascript
- Python Client: https://supabase.com/docs/reference/python

**Authentication:**
- Type: API Keys
- Env Vars: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_PASSWORD`
- Generate at: Supabase Dashboard → Project Settings → API

**Key Endpoints:**
- Base URL: `https://<project-ref>.supabase.co`
- REST API: `https://<project-ref>.supabase.co/rest/v1/`
- Auth API: `https://<project-ref>.supabase.co/auth/v1/`
- Storage API: `https://<project-ref>.supabase.co/storage/v1/`

**Usage in Fabrik:**
- Functions: Database, authentication, file storage
- Project ID: `xjmsceegyztgtcpywhry`

**Rate Limits:**
- Free: 500 MB database, 1 GB storage, 2 API requests/second
- Pro: 8 GB database, 100 GB storage, 50 API requests/second

**Notes:**
- PostgreSQL with Row Level Security (RLS)
- Built-in authentication
- File storage with signed URLs

---

## Email & Communication

### Resend

**Purpose:** Email delivery service (primary)

**Documentation:**
- API Docs: https://resend.com/docs/api-reference
- Python SDK: https://github.com/resend/resend-python

**Authentication:**
- Type: API Key
- Env Vars: `RESEND_API_KEY`, `RESEND_DAILY_LIMIT`
- Generate at: Resend Dashboard → API Keys

**Key Endpoints:**
- Base URL: `https://api.resend.com`
- Send Email: `POST /emails`
- List Emails: `GET /emails`
- Get Domain: `GET /domains/{id}`

**Usage in Fabrik:**
- Functions: Transactional emails
- Daily Limit: 100 emails

**Rate Limits:**
- Free: 3,000 emails/month
- Pro: 50,000 emails/month

**Notes:**
- Primary email service
- Better deliverability than SES

---

### Amazon SES

**Purpose:** Email delivery service (backup)

**Documentation:**
- API Docs: https://docs.aws.amazon.com/ses/latest/APIReference/
- SMTP Settings: https://docs.aws.amazon.com/ses/latest/DeveloperGuide/smtp-credentials.html

**Authentication:**
- Type: SMTP Credentials
- Env Vars: `SES_SMTP_HOST`, `SES_SMTP_PORT`, `SES_SMTP_USER`, `SES_SMTP_PASS`
- Generate at: AWS Console → SES → SMTP Settings → Create SMTP Credentials

**SMTP Configuration:**
- Host: `email-smtp.<region>.amazonaws.com`
- Port: 465 (SSL) or 587 (TLS)
- Region: `eu-north-1`

**Usage in Fabrik:**
- Functions: Backup email service
- Daily Limit: 200 emails

**Rate Limits:**
- Sandbox: 200 emails/day
- Production: Request limit increase

**Notes:**
- Backup to Resend
- Requires DKIM/SPF setup for deliverability

---

### Gmail SMTP

**Purpose:** Personal email sending

**Documentation:**
- SMTP Settings: https://support.google.com/mail/answer/7126229
- App Passwords: https://support.google.com/accounts/answer/185833

**Authentication:**
- Type: App Password
- Env Vars: `GMAIL_SMTP_USER`, `GMAIL_SMTP_PASS`
- Generate at: Google Account → Security → 2-Step Verification → App Passwords

**SMTP Configuration:**
- Host: `smtp.gmail.com`
- Port: 587 (TLS) or 465 (SSL)

**Usage in Fabrik:**
- Functions: Personal email sending
- User: `obasak@gmail.com`

**Rate Limits:**
- Free: 500 emails/day
- Google Workspace: 2,000 emails/day

**Notes:**
- Requires 2FA enabled
- Use App Passwords (not account password)

---

### Microsoft 365

**Purpose:** Email reading (ob@ocoron.com)

**Documentation:**
- API Docs: https://learn.microsoft.com/en-us/graph/api/
- Python SDK: https://github.com/microsoftgraph/msgraph-sdk-python
- Certificate Auth: https://learn.microsoft.com/en-us/entra/identity-platform/certificate-credentials

**Authentication:**
- Type: Certificate-based OAuth
- Env Vars: `M365_TENANT_ID`, `M365_CLIENT_ID`, `M365_CERT_THUMBPRINT`, `M365_CERT_KEY_FILE`, `M365_TARGET_EMAIL`
- Generate at: Azure AD → App Registrations → Certificates & secrets

**Key Endpoints:**
- Base URL: `https://graph.microsoft.com/v1.0`
- Read Emails: `GET /users/{id}/mailFolders/inbox/messages`
- Send Email: `POST /users/{id}/sendMail`

**Usage in Fabrik:**
- Functions: Read emails for verification codes
- Target Email: `ob@ocoron.com`

**Rate Limits:**
- App-only: 15,000 requests/tenant/minute
- Delegated: 15,000 requests/user/minute

**Notes:**
- Certificate-based authentication (no user interaction)
- Requires certificate file on server

---

### Telegram

**Purpose:** Notification service

**Documentation:**
- Bot API: https://core.telegram.org/bots/api
- Python SDK: https://github.com/python-telegram-bot/python-telegram-bot

**Authentication:**
- Type: Bot Token
- Env Vars: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- Generate at: @BotFather → /newbot

**Key Endpoints:**
- Base URL: `https://api.telegram.org/bot<token>/`
- Send Message: `POST /sendMessage`
- Send Photo: `POST /sendPhoto`
- Get Updates: `GET /getUpdates`

**Usage in Fabrik:**
- Functions: System notifications, alerts

**Rate Limits:**
- 30 messages/second per bot
- 20 messages/minute per group

**Notes:**
- Placeholder (not configured yet)

---

## Translation Services

### DeepL

**Purpose:** Translation service (primary)

**Documentation:**
- API Docs: https://www.deepl.com/docs-api/
- Python SDK: https://github.com/DeepLcom/deepl-python

**Authentication:**
- Type: API Key
- Env Vars: `DEEPL_API_KEY`, `DEEPL_API_URL`, `DEEPL_MONTHLY_CHAR_LIMIT`
- Generate at: DeepL Account → Account → API Keys

**Key Endpoints:**
- Base URL: `https://api-free.deepl.com/v2`
- Translate Text: `POST /translate`
- Usage: `GET /usage`

**Usage in Fabrik:**
- Functions: Text translation
- Monthly Limit: 500,000 characters
- Service URL: `https://translator.vps1.ocoron.com`

**Rate Limits:**
- Free: 500,000 characters/month
- Pro: Unlimited

**Notes:**
- Primary translation service
- Better quality than Azure Translator

---

### Azure Translator

**Purpose:** Translation service (fallback)

**Documentation:**
- API Docs: https://learn.microsoft.com/en-us/azure/ai-services/translator/
- Python SDK: https://github.com/Azure/azure-sdk-for-python

**Authentication:**
- Type: API Key
- Env Vars: `AZURE_TRANSLATOR_KEY`, `AZURE_TRANSLATOR_REGION`, `AZURE_TEXT_ENDPOINT`, `AZURE_DOCUMENT_ENDPOINT`
- Generate at: Azure Portal → Cognitive Services → Translator → Keys and Endpoint

**Key Endpoints:**
- Base URL: `https://api.cognitive.microsofttranslator.com`
- Translate Text: `POST /translate`
- Detect Language: `POST /detect`
- Document Translation: `POST /batches`

**Usage in Fabrik:**
- Functions: Fallback translation service
- Region: `westeurope`

**Rate Limits:**
- Free: 2M characters/month
- Standard: Pay-as-you-go

**Notes:**
- Fallback to DeepL
- Supports document translation

---

## AI/LLM Services

> **No direct Anthropic/OpenAI API keys are used.** Fabrik does AI two ways only
> (see `spec_loader` `llm_provider: claude-code | openrouter`):
>
> - **Claude Code subscription OAuth** — the operational stack (sysadmin bot,
>   watchdog, aro-wake, bootstrap). No API key.
> - **OpenRouter** (OpenAI-compatible HTTP API) — content/LLM fallback; the
>   watchdog reads `WATCHDOG_OPENROUTER_KEY` from its own deploy env.
>
> The former direct-API `LLMClient` (`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`) and the
> `fabrik ai generate/revise` commands were removed 2026-06-16.

### OpenRouter

**Purpose:** OpenAI-compatible LLM gateway — content/LLM fallback path.

**Documentation:**
- API Docs: https://openrouter.ai/docs
- Models: https://openrouter.ai/models

**Authentication:**
- Type: API Key (Bearer)
- Env Var: `WATCHDOG_OPENROUTER_KEY` (set in the watchdog's deploy env, not the app `.env`)

**Key Endpoints:**
- Base URL: `https://openrouter.ai/api/v1`
- Chat Completions: `POST /chat/completions`

**Usage in Fabrik:**
- Functions: watchdog/fleet-healer LLM calls when not using Claude Code OAuth
- Models: full ids, e.g. `anthropic/claude-sonnet-4.6`, `google/gemini-2.5-flash`

---

### Factory AI

**Purpose:** AI platform (ob@ocoron.com)

**Documentation:**
- Website: https://factory.ai/
- API: Contact Factory AI for documentation

**Authentication:**
- Type: API Key
- Env Vars: `FACTORY_API_KEY`
- Generate at: Factory AI Dashboard

**Usage in Fabrik:**
- Functions: AI content generation

**Notes:**
- Custom AI platform
- User-specific account

---

### Black Forest Labs

**Purpose:** Image generation (FLUX)

**Documentation:**
- API Docs: https://docs.blackforestlabs.ai/
- Models: https://blackforestlabs.ai/

**Authentication:**
- Type: API Key
- Env Vars: `BFL_API_KEY`
- Generate at: Black Forest Labs Dashboard

**Key Endpoints:**
- Base URL: https://api.blackforestlabs.ai/v1
- Generate Image: `POST /flux-dev/v1/text-to-image`

**Usage in Fabrik:**
- Functions: AI image generation

**Rate Limits:**
- Contact Black Forest Labs

**Notes:**
- FLUX model for image generation

---

## Image & Media APIs

### Unsplash

**Purpose:** Stock photos

**Documentation:**
- API Docs: https://unsplash.com/developers
- Python SDK: https://github.com/unsplash/unsplash-python

**Authentication:**
- Type: Access Key
- Env Vars: `UNSPLASH_ACCESS_KEY`
- Generate at: Unsplash Developers → New Application

**Key Endpoints:**
- Base URL: `https://api.unsplash.com`
- Search Photos: `GET /search/photos`
- Get Photo: `GET /photos/{id}`
- Download Photo: `GET /photos/{id}/download`

**Usage in Fabrik:**
- Functions: Stock photo search and download
- Service URL: `https://images.vps1.ocoron.com`

**Rate Limits:**
- Free: 50 requests/hour
- Pro: 5,000 requests/hour

**Notes:**
- Placeholder (not configured yet)

---

### Pexels

**Purpose:** Stock photos and videos

**Documentation:**
- API Docs: https://www.pexels.com/api/
- Python SDK: https://github.com/Pexels/pexels-api-python

**Authentication:**
- Type: API Key
- Env Vars: `PEXELS_API_KEY`
- Generate at: Pexels API → New Key

**Key Endpoints:**
- Base URL: `https://api.pexels.com/v1`
- Search Photos: `GET /search`
- Curated Photos: `GET /curated`
- Get Photo: `GET /photos/{id}`

**Usage in Fabrik:**
- Functions: Stock photo search and download
- Service URL: `https://images.vps1.ocoron.com`

**Rate Limits:**
- Free: 200 requests/hour
- Pro: Unlimited

**Notes:**
- Configured and active

---

### Pixabay

**Purpose:** Stock photos and videos

**Documentation:**
- API Docs: https://pixabay.com/api/docs/
- Python SDK: https://github.com/thisisrandy/pixabay-py

**Authentication:**
- Type: API Key
- Env Vars: `PIXABAY_API_KEY`
- Generate at: Pixabay API → Get API Key

**Key Endpoints:**
- Base URL: `https://pixabay.com/api/`
- Search Images: `GET /`
- Search Videos: `GET /videos/`
- Get Image Details: `GET /?id={id}`

**Usage in Fabrik:**
- Functions: Stock photo search and download
- Service URL: `https://images.vps1.ocoron.com`

**Rate Limits:**
- Free: 100 requests/minute
- Pro: 5,000 requests/hour

**Notes:**
- Configured and active

---

## Scraping & Automation

### Webshare.io

**Purpose:** Rotating residential proxies

**Documentation:**
- API Docs: https://developers.webshare.io/
- Dashboard: https://proxy.webshare.io/

**Authentication:**
- Type: API Key + Username/Password
- Env Vars: `WEBSHARE_API_KEY`, `PROXY_USER`, `PROXY_PASSWORD`
- Generate at: Webshare Dashboard → API Keys

**Key Endpoints:**
- Base URL: `https://api.webshare.io/api`
- List Proxies: `GET /v2/proxy/list`
- Get Usage: `GET /v2/proxy/usage`

**Usage in Fabrik:**
- Functions: Web scraping, bypass geo-restrictions
- Service URL: `https://proxy.vps1.ocoron.com`

**Rate Limits:**
- Contact Webshare.io

**Notes:**
- Rotating residential proxies
- Better for scraping than datacenter proxies

---

### Anti-Captcha

**Purpose:** CAPTCHA solving service

**Documentation:**
- API Docs: https://anti-captcha.com/apidoc
- Python SDK: https://github.com/AdguardTeam/Anti-Captcha-Python

**Authentication:**
- Type: API Key
- Env Vars: `ANTICAPTCHA_API_KEY`
- Generate at: Anti-Captcha Dashboard → API Key

**Key Endpoints:**
- Base URL: `https://api.anti-captcha.com`
- Create Task: `POST /createTask`
- Get Task Result: `POST /getTaskResult`

**Usage in Fabrik:**
- Functions: CAPTCHA solving for scraping
- Service URL: `https://captcha.vps1.ocoron.com`

**Rate Limits:**
- Free: 10 tasks/minute
- Paid: Custom

**Notes:**
- Supports reCAPTCHA, hCaptcha, Turnstile, image CAPTCHAs

---

### Apify

**Purpose:** Web scraping platform

**Documentation:**
- API Docs: https://docs.apify.com/api/v2/
- Python SDK: https://github.com/apify/apify-client-python

**Authentication:**
- Type: API Token
- Env Vars: `APIFY_API_TOKEN`
- Generate at: Apify Console → Integrations → API

**Key Endpoints:**
- Base URL: `https://api.apify.com/v2`
- Run Actor: `POST /actor-tasks/{taskId}/runs`
- Get Results: `GET /actor-tasks/{taskId}/runs/{runId}/dataset/items`

**Usage in Fabrik:**
- Functions: YouTube Comments scraping (fallback)

**Rate Limits:**
- Free: 2,000 results/month
- Paid: Custom

**Notes:**
- YouTube Comments API fallback

---

### Abstract API

**Purpose:** Calendar holidays API

**Documentation:**
- API Docs: https://www.abstractapi.com/api/holidays
- Python SDK: https://github.com/abstractapi/public-holidays-api-python

**Authentication:**
- Type: API Key
- Env Vars: `ABSTRACT_API_KEY`
- Generate at: Abstract API → Public Holidays API

**Key Endpoints:**
- Base URL: `https://holidays.abstractapi.com/v1`
- Get Holidays: `GET /?country={code}&year={year}&month={month}&day={day}`

**Usage in Fabrik:**
- Functions: Calendar holiday data

**Rate Limits:**
- Free: 500 requests/month
- Pro: 10,000 requests/month

**Notes:**
- Used for calendar automation

---

### RapidAPI

**Purpose:** API marketplace

**Documentation:**
- API Docs: https://docs.rapidapi.com/
- YouTube Downloader: https://rapidapi.com/ytdl/api/youtube-video-audio-downloader

**Authentication:**
- Type: API Key
- Env Vars: `RAPIDAPI_KEY`, `RAPIDAPI_YT_HOST`
- Generate at: RapidAPI Dashboard → Applications → API Key

**Key Endpoints:**
- Base URL: `https://{host}/api`
- YouTube Download: `POST /download`

**Usage in Fabrik:**
- Functions: YouTube video/audio download

**Rate Limits:**
- Contact RapidAPI

**Notes:**
- YouTube video/audio downloader

---

### Soniox

**Purpose:** Audio transcription

**Documentation:**
- API Docs: Contact Soniox for documentation
- Website: https://soniox.com/

**Authentication:**
- Type: API Key
- Env Vars: `SONIOX_API_KEYS` (comma-separated)
- Generate at: Soniox Dashboard

**Usage in Fabrik:**
- Functions: Audio transcription for YouTube videos

**Rate Limits:**
- Contact Soniox

**Notes:**
- Multiple API keys for load balancing

---

## Monitoring & Observability

### Gatus

**Purpose:** Status/health-endpoint monitoring (the fleet status page).

**Documentation:**
- GitHub: https://github.com/TwiN/gatus

**Configuration:**
- **No API token / no auth env vars** — Gatus is config-file driven, not API-driven.
- Config: `configs/gatus/**/*.yaml` in this repo, synced to vps1 `/opt/monitoring/configs/gatus/` via `scripts/sync_gatus_to_vps.sh`.
- Web UI: `https://status.vps1.ocoron.com` (public).

**Usage in Fabrik:**
- Functions: per-endpoint health checks (HTTP/TCP/cert) with Telegram alerts via the `custom` alert type
- Spec-driven: a service spec auto-registers a Gatus endpoint on `fabrik apply` (gatus registrar)

**Notes:**
- Self-hosted on vps1, on the `fabrik` Docker network
- 31 endpoints across 18 YAML files (see `sync_gatus_to_vps.sh --diff` for live count)

---

<!-- Netdata "external system" entry removed 2026-06-17. Netdata was removed from
     the fleet 2026-05-30 (its Prometheus scrape job was deleted 2026-06-07 after a
     Telegram flood). System metrics now come from node-exporter + cAdvisor scraped
     by Prometheus and visualised in Grafana. No `netdata.vps1.ocoron.com` exists. -->

---

## Security & Code Quality

### Semgrep

**Purpose:** Static analysis security scanning

**Documentation:**
- Website: https://semgrep.dev/
- API Docs: https://semgrep.dev/api/
- Rules: https://semgrep.dev/docs/writing-rules/overview

**Authentication:**
- Type: API Token
- Env Vars: `SEMGREP_APP_TOKEN`
- Generate at: Semgrep Dashboard → Settings → API Tokens

**Key Endpoints:**
- Base URL: `https://semgrep.dev/api/v1`
- Scan Repository: `POST /deployments`
- Get Results: `GET /deployments/{id}`

**Usage in Fabrik:**
- Functions: Security scanning in CI/CD

**Rate Limits:**
- Free: 100 scans/month
- Team: Unlimited

**Notes:**
- Token: `web_mobasak_valid-from-2026-02-23`

---

## Development Tools

### GitHub

**Purpose:** Git hosting and CI/CD

**Documentation:**
- API Docs: https://docs.github.com/en/rest
- Actions: https://docs.github.com/en/actions

**Authentication:**
- Type: Personal Access Token
- Env Vars: `GITHUB_TOKEN`, `GITHUB_USERNAME`
- Generate at: GitHub Settings → Developer Settings → Personal Access Tokens → Tokens (classic)

**Key Endpoints:**
- Base URL: `https://api.github.com`
- Get Repository: `GET /repos/{owner}/{repo}`
- Create Webhook: `POST /repos/{owner}/{repo}/hooks`
- List Actions: `GET /repos/{owner}/{repo}/actions/runs`

**Usage in Fabrik:**
- Functions: Git operations, CI/CD integration

**Rate Limits:**
- Authenticated: 5,000 requests/hour
- Unauthenticated: 60 requests/hour

**Notes:**
- Username: `mobasak`

---

### Docker Hub

**Purpose:** Container registry

**Documentation:**
- API Docs: https://docs.docker.com/registry/spec/api/
- Python SDK: https://github.com/docker/docker-py

**Authentication:**
- Type: Access Token
- Env Vars: `DOCKER_HUB_USERNAME`, `DOCKER_HUB_ACCESS_TOKEN`
- Generate at: Docker Hub → Account Settings → Security → New Access Token

**Key Endpoints:**
- Base URL: `https://hub.docker.com/v2`
- Login: `POST /users/login`
- List Repositories: `GET /repositories/{username}`
- Push Image: `POST /images/{name}/push`

**Usage in Fabrik:**
- Functions: Container image management
- Username: `kasabo`

**Rate Limits:**
- Anonymous: 100 pulls/6 hours
- Authenticated: 200 pulls/6 hours
- Pro: Unlimited

**Notes:**
- Token: Access token (not password)

---

### Gumroad

**Purpose:** Payment platform

**Documentation:**
- API Docs: https://gumroad.com/api
- Webhooks: https://gumroad.com/api/webhooks

**Authentication:**
- Type: Webhook Secret
- Env Vars: `GUMROAD_WEBHOOK_SECRET`
- Generate at: Gumroad Dashboard → Settings → Advanced → Webhook Secret

**Usage in Fabrik:**
- Functions: Payment webhooks

**Notes:**
- Placeholder (not configured yet)

---

## Internal Services

The only Fabrik-authored microservice still deployed is:

- **site-provisioner** (`https://provision.vps1.ocoron.com`) — domain/DNS/container provisioning; container live and healthy on the `fabrik` network. See [`docs/../service-contracts/site-provisioner.md`](../service-contracts/site-provisioner.md).

The shared infra services (also internal) are catalogued in their own sections above: **Gatus** (status), **Backrest** (backup), **Grafana/Prometheus/Loki/Promtail** (monitoring stack), **Apprise** (notifications), **n8n** (automation), **Browserless**, **Gotenberg**, **Meilisearch**.

**Retired** (kept here only to explain stale subdomains/specs): `proxy`, `captcha`, `translator`, `emailgateway`, `dns-manager` (all retired pre-2026-06), `image-broker` (retired 2026-06-02), `netdata` (removed 2026-05-30). Their `*.vps1.ocoron.com` subdomains were deleted from Cloudflare during residue cleanup.

---

## WordPress Plugins

> **WordPress moved out of Fabrik to the standalone `/opt/wpf` project (2026).** The
> `src/fabrik/wordpress/*.py` paths cited below no longer exist in this repo — the
> plugin detection/forms/analytics logic now lives in `/opt/wpf`. Entries kept as a
> catalog of the plugins the WP pipeline handles.

### Yoast SEO

**Purpose:** WordPress SEO plugin

**Documentation:**
- Website: https://yoast.com/wordpress/plugins/seo/
- Developer Docs: https://developer.yoast.com/

**Usage in Fabrik:**
- Functions: SEO optimization, meta tags, schema markup
- Detection: `/opt/fabrik/src/fabrik/wordpress/seo.py`

**Notes:**
- WordPress.org plugin
- Free and premium versions

---

### Rank Math

**Purpose:** WordPress SEO plugin (alternative to Yoast)

**Documentation:**
- Website: https://rankmath.com/
- Developer Docs: https://rankmath.com/kb/

**Usage in Fabrik:**
- Functions: SEO optimization, meta tags, schema markup
- Detection: `/opt/fabrik/src/fabrik/wordpress/seo.py`

**Notes:**
- WordPress.org plugin
- Built-in Google Analytics support

---

### WPForms

**Purpose:** WordPress form builder plugin

**Documentation:**
- Website: https://wpforms.com/
- Developer Docs: https://wpforms.com/docs/

**Usage in Fabrik:**
- Functions: Contact form creation
- Driver: `/opt/fabrik/src/fabrik/wordpress/forms.py`

**Notes:**
- WordPress.org plugin
- Preferred form plugin in Fabrik

---

### Contact Form 7

**Purpose:** WordPress contact form plugin

**Documentation:**
- Website: https://contactform7.com/
- Developer Docs: https://contactform7.com/docs/

**Usage in Fabrik:**
- Functions: Contact form creation (fallback)
- Driver: `/opt/fabrik/src/fabrik/wordpress/forms.py`

**Notes:**
- WordPress.org plugin
- Fallback if WPForms not available

---

## Analytics & Tag Management

### Google Analytics 4

**Purpose:** Web analytics service

**Documentation:**
- Website: https://analytics.google.com/
- API Docs: https://developers.google.com/analytics/devguides/reporting/data/v1
- Measurement ID: `G-XXXXXXXXXX`

**Usage in Fabrik:**
- Functions: Website analytics tracking
- Injector: `/opt/fabrik/src/fabrik/wordpress/analytics.py`

**Rate Limits:**
- Free: 10M hits/month
- Analytics 360: 1B hits/month

**Notes:**
- Measurement ID format: `G-XXXXXXXXXX`

---

### Google Tag Manager

**Purpose:** Tag management platform

**Documentation:**
- Website: https://tagmanager.google.com/
- API Docs: https://developers.google.com/tag-platform/tag-manager/api/v2
- Container ID: `GTM-XXXXXXX`

**Usage in Fabrik:**
- Functions: Tag management, marketing pixels
- Injector: `/opt/fabrik/src/fabrik/wordpress/analytics.py`

**Rate Limits:**
- Free: 1M tags/month
- Standard: 10M tags/month

**Notes:**
- Container ID format: `GTM-XXXXXXX`

---

## Container Registries

### LinuxServer.io

**Purpose:** Container registry for ops tools

**Documentation:**
- Website: https://docs.linuxserver.io/
- Registry: `lscr.io`

**Usage in Fabrik:**
- Functions: Pre-built container images
- Tools: Duplicati, Plex, Jellyfin, qBittorrent, WireGuard, etc.

**Rate Limits:**
- No documented limits

**Notes:**
- Consistent PUID/PGID mapping
- s6-overlay supervisor
- Regular security updates

---

### hotio.dev

**Purpose:** Container registry for specific apps

**Documentation:**
- Website: https://hotio.dev/
- Registry: `ghcr.io/hotio`

**Usage in Fabrik:**
- Functions: Alternative container images
- Tools: Sonarr, Radarr, Lidarr, Prowlarr

**Rate Limits:**
- No documented limits

**Notes:**
- Better maintained for *arr stack
- Alternative to LinuxServer.io

---

### TrueForge/ContainerForge

**Purpose:** OCI registry for Home Assistant

**Documentation:**
- Website: https://trueforge.org/
- Registry: `oci.trueforge.org`

**Usage in Fabrik:**
- Functions: Home Assistant containers
- Tool: `python /opt/fabrik/scripts/container_images.py trueforge list`

**Rate Limits:**
- GitHub API rate limits apply

**Notes:**
- Uses GitHub Container Registry
- Focus on Home Assistant ecosystem

---

## Infrastructure Services

### Apprise

**Purpose:** Notification service

**Documentation:**
- Website: https://github.com/caronc/apprise
- API Docs: https://github.com/caronc/apprise/wiki

**Usage in Fabrik:**
- Functions: Multi-channel notifications
- Domain: `https://notify.vps1.ocoron.com`
- Port: 8005

**Supported Channels:**
- Slack, Email, Telegram, Discord, Generic Webhook

**Notes:**
- Self-hosted on VPS
- Used by n8n workflows

---

### Browserless

**Purpose:** Headless Chrome browser service

**Documentation:**
- Website: https://browserless.io/
- GitHub: https://github.com/browserless/chrome

**Usage in Fabrik:**
- Functions: Headless browser automation
- Domain: `https://browser.vps1.ocoron.com`
- Port: 3000

**Environment Variables:**
- `MAX_CONCURRENT_SESSIONS`: 10
- `CONNECTION_TIMEOUT`: 60000
- `PREBOOT_CHROME`: true

**Notes:**
- Self-hosted on VPS
- amd64 compatible

---

### Gotenberg

**Purpose:** PDF generation service

**Documentation:**
- Website: https://gotenberg.dev/
- GitHub: https://github.com/gotenberg/gotenberg

**Usage in Fabrik:**
- Functions: HTML to PDF conversion
- Domain: `https://pdf.vps1.ocoron.com`
- Port: 3003

**Notes:**
- Self-hosted on VPS
- amd64 compatible

---

### Meilisearch

**Purpose:** Search engine

**Documentation:**
- Website: https://www.meilisearch.com/
- Docs: https://docs.meilisearch.com/

**Usage in Fabrik:**
- Functions: Full-text search
- Domain: `https://search.vps1.ocoron.com`
- Port: 7700

**Environment Variables:**
- `MEILI_MASTER_KEY`: Required
- `MEILI_ENV`: production

**Notes:**
- Self-hosted on VPS
- amd64 compatible

---

### Minio

**Purpose:** S3-compatible object storage

**Documentation:**
- Website: https://min.io/
- Docs: https://min.io/docs/minio/linux/

**Usage in Fabrik:**
- Functions: S3-compatible storage
- Domain: `https://s3.vps1.ocoron.com`
- Ports: 9000 (API), 9001 (Console)

**Environment Variables:**
- `MINIO_ROOT_USER`: Required
- `MINIO_ROOT_PASSWORD`: Required

**Notes:**
- Self-hosted on VPS
- S3-compatible API
- amd64 compatible

---

### n8n

**Purpose:** Workflow automation platform

**Documentation:**
- Website: https://n8n.io/
- Docs: https://docs.n8n.io/

**Usage in Fabrik:**
- Functions: Workflow automation, webhooks
- Domain: `https://auto.vps1.ocoron.com`
- Port: 5678

**Environment Variables:**
- `N8N_BASIC_AUTH_ACTIVE`: true
- `N8N_BASIC_AUTH_USER`: Required
- `N8N_BASIC_AUTH_PASSWORD`: Required
- `N8N_ENCRYPTION_KEY`: Required

**Workflows:**
- Uptime alerts (`configs/n8n/workflows/uptime-alert.json`)
- Backup notifications (`configs/n8n/workflows/backup-notification.json`)

**Notes:**
- Self-hosted on VPS
- amd64 compatible
- Integrates with Apprise for notifications

---

## Monitoring Stack

### Loki

**Purpose:** Log aggregation system

**Documentation:**
- Website: https://grafana.com/oss/loki/
- Docs: https://grafana.com/docs/loki/latest/

**Usage in Fabrik:**
- Functions: Log aggregation and querying
- Port: 3100
- Config: `/opt/fabrik/configs/loki/loki-config.yaml`

**Notes:**
- Self-hosted on VPS
- amd64 compatible
- Part of monitoring stack

---

### Promtail

**Purpose:** Log shipping agent

**Documentation:**
- Website: https://grafana.com/oss/promtail/
- Docs: https://grafana.com/docs/promtail/latest/

**Usage in Fabrik:**
- Functions: Ship logs to Loki
- Config: `/opt/fabrik/configs/promtail/promtail-config.yaml`

**Notes:**
- Self-hosted on VPS
- amd64 compatible
- Part of monitoring stack

---

### Prometheus

**Purpose:** Metrics collection and monitoring

**Documentation:**
- Website: https://prometheus.io/
- Docs: https://prometheus.io/docs/

**Usage in Fabrik:**
- Functions: Metrics collection
- Port: 9090
- Config: `/opt/fabrik/configs/prometheus/prometheus.yml`

**Notes:**
- Self-hosted on VPS
- amd64 compatible
- Part of monitoring stack

---

### Grafana

**Purpose:** Metrics visualization and dashboards

**Documentation:**
- Website: https://grafana.com/
- Docs: https://grafana.com/docs/

**Usage in Fabrik:**
- Functions: Metrics dashboards
- Port: 3002
- Environment: `GF_SECURITY_ADMIN_PASSWORD`

**Notes:**
- Self-hosted on VPS
- amd64 compatible
- Part of monitoring stack

---

### Node Exporter

**Purpose:** System metrics exporter

**Documentation:**
- Website: https://github.com/prometheus/node_exporter
- Docs: https://github.com/prometheus/node_exporter

**Usage in Fabrik:**
- Functions: System-level metrics
- Port: 9100

**Notes:**
- Self-hosted on VPS
- amd64 compatible
- Part of monitoring stack

---

### cAdvisor

**Purpose:** Container metrics exporter

**Documentation:**
- Website: https://github.com/google/cadvisor
- Docs: https://github.com/google/cadvisor

**Usage in Fabrik:**
- Functions: Container-level metrics
- Port: 8080

**Notes:**
- Self-hosted on VPS
- amd64 compatible
- Part of monitoring stack

---

## Media & Entertainment (Referenced)

### Plex

**Purpose:** Media server

**Documentation:**
- Website: https://www.plex.tv/
- Docker: `lscr.io/linuxserver/plex`

**Usage in Fabrik:**
- Functions: Media streaming
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

### Jellyfin

**Purpose:** Media server

**Documentation:**
- Website: https://jellyfin.org/
- Docker: `lscr.io/linuxserver/jellyfin`

**Usage in Fabrik:**
- Functions: Media streaming
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

### Emby

**Purpose:** Media server

**Documentation:**
- Website: https://emby.media/
- Docker: `lscr.io/linuxserver/emby`

**Usage in Fabrik:**
- Functions: Media streaming
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

## Download Managers (Referenced)

### qBittorrent

**Purpose:** BitTorrent download manager

**Documentation:**
- Website: https://www.qbittorrent.org/
- Docker: `lscr.io/linuxserver/qbittorrent`

**Usage in Fabrik:**
- Functions: Torrent downloads
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

### SABnzbd

**Purpose:** Usenet download manager

**Documentation:**
- Website: https://sabnzbd.org/
- Docker: `lscr.io/linuxserver/sabnzbd`

**Usage in Fabrik:**
- Functions: Usenet downloads
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

### NZBGet

**Purpose:** Usenet download manager

**Documentation:**
- Website: https://nzbget.net/
- Docker: `lscr.io/linuxserver/nzbget`

**Usage in Fabrik:**
- Functions: Usenet downloads
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

## VPN (Referenced)

### WireGuard

**Purpose:** VPN protocol

**Documentation:**
- Website: https://www.wireguard.com/
- Docker: `lscr.io/linuxserver/wireguard`

**Usage in Fabrik:**
- Functions: VPN connections
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

### OpenVPN

**Purpose:** VPN protocol

**Documentation:**
- Website: https://openvpn.net/
- Docker: `lscr.io/linuxserver/openvpn-as`

**Usage in Fabrik:**
- Functions: VPN connections
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

## Dashboards (Referenced)

### Heimdall

**Purpose:** Dashboard for services

**Documentation:**
- Website: https://heimdall.site/
- Docker: `lscr.io/linuxserver/heimdall`

**Usage in Fabrik:**
- Functions: Service dashboard
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

### Homer

**Purpose:** Dashboard for services

**Documentation:**
- Website: https://github.com/bastienwirtz/homer
- Docker: `lscr.io/linuxserver/homer`

**Usage in Fabrik:**
- Functions: Service dashboard
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

### Organizr

**Purpose:** Dashboard for services

**Documentation:**
- Website: https://organizr.app/
- Docker: `lscr.io/linuxserver/organizr`

**Usage in Fabrik:**
- Functions: Service dashboard
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

## Additional Backup Tools (Referenced)

### Restic

**Purpose:** Backup tool

**Documentation:**
- Website: https://restic.net/
- Docker: `restic/restic`

**Usage in Fabrik:**
- Functions: Fast backups
- Status: Referenced, not deployed

**Notes:**
- Official image available
- amd64 compatible

---

### Borg

**Purpose:** Backup tool

**Documentation:**
- Website: https://borgbackup.org/
- Docker: `lscr.io/linuxserver/borg`

**Usage in Fabrik:**
- Functions: Deduplicated backups
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

## Reverse Proxy & SSL

### Traefik

**Purpose:** Reverse proxy and load balancer

**Documentation:**
- Website: https://traefik.io/
- Docs: https://doc.traefik.io/traefik/
- GitHub: https://github.com/traefik/traefik

**Usage in Fabrik:**
- Functions: Reverse proxy, SSL termination, load balancing
- Provider: Docker (labels on containers)
- EntryPoints: web (80), websecure (443)
- Network: fabrik

**Configuration:**
- certResolver: letsencrypt
- Labels on containers for routing

**Notes:**
- Self-hosted on VPS
- Manages SSL certificates via Let's Encrypt
- Auto-renewal every 90 days

---

### Let's Encrypt

**Purpose:** SSL certificate authority

**Documentation:**
- Website: https://letsencrypt.org/
- ACME Protocol: https://letsencrypt.org/docs/client-options.html

**Usage in Fabrik:**
- Functions: Free SSL certificates
- Integration: Via Traefik ACME
- Auto-renewal: Every 90 days

**Rate Limits:**
- Certificates per domain: 50 per week
- Duplicate certificates: 5 per week
- Failed validations: 5 per account per hour

**Notes:**
- Free SSL certificates
- ACME protocol
- Requires DNS validation

---

## Additional Container Registries

### Docker Hub (docker.io)

**Purpose:** Default container registry

**Documentation:**
- Website: https://hub.docker.com/
- API Docs: https://docs.docker.com/registry/spec/api/
- Registry API: https://registry-1.docker.io/v2/

**Usage in Fabrik:**
- Functions: Container image storage
- Tool: `python /opt/fabrik/scripts/container_images.py`

**Authentication:**
- Type: Username + Access Token
- Env Vars: `DOCKER_HUB_USERNAME`, `DOCKER_HUB_ACCESS_TOKEN`

**Rate Limits:**
- Anonymous: 100 pulls/6 hours
- Authenticated: 200 pulls/6 hours
- Pro: Unlimited

**Notes:**
- Default registry for Docker
- Official images available

---

### GitHub Container Registry (ghcr.io)

**Purpose:** Container registry for GitHub packages

**Documentation:**
- Website: https://github.com/features/packages
- Docs: https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry

**Usage in Fabrik:**
- Functions: Container storage for GitHub repos
- Tool: `python /opt/fabrik/scripts/container_images.py`

**Authentication:**
- Type: Personal Access Token
- Env Var: `GITHUB_TOKEN` (optional, for higher rate limits)

**Rate Limits:**
- Anonymous: 60 requests/hour
- Authenticated: 5,000 requests/hour

**Notes:**
- Integrated with GitHub repos
- Used by hotio.dev

---

## Additional Infrastructure Tools (Referenced)

### Code Server

**Purpose:** VS Code in browser

**Documentation:**
- Website: https://github.com/coder/code-server
- Docker: `lscr.io/linuxserver/code-server`

**Usage in Fabrik:**
- Functions: Browser-based IDE
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

### Gitea

**Purpose:** Self-hosted Git

**Documentation:**
- Website: https://gitea.io/
- Docker: `gitea/gitea`

**Usage in Fabrik:**
- Functions: Self-hosted Git server
- Status: Referenced, not deployed

**Notes:**
- Official image available
- amd64 compatible

---

## Additional Backup Tools (Referenced)

### Restic

**Purpose:** Modern backup tool

**Documentation:**
- Website: https://restic.net/
- Docker: `restic/restic`

**Usage in Fabrik:**
- Functions: Fast, secure backups
- Status: Referenced, not deployed

**Notes:**
- Official image available
- amd64 compatible
- Deduplication and encryption

---

### Borg

**Purpose:** Deduplicating backup tool

**Documentation:**
- Website: https://borgbackup.org/
- Docker: `lscr.io/linuxserver/borg`

**Usage in Fabrik:**
- Functions: Deduplicated backups
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

## Additional Web Servers (Referenced)

### Nginx

**Purpose:** Web server and reverse proxy

**Documentation:**
- Website: https://nginx.org/
- Docker: `nginx:alpine`

**Usage in Fabrik:**
- Functions: Web server
- Status: Referenced, not deployed

**Notes:**
- Official image available
- amd64 compatible

---

### Caddy

**Purpose:** Web server with automatic HTTPS

**Documentation:**
- Website: https://caddyserver.com/
- Docker: `caddy:2-alpine`

**Usage in Fabrik:**
- Functions: Web server with auto SSL
- Status: Referenced, not deployed

**Notes:**
- Official image available
- amd64 compatible
- Automatic HTTPS

---

## Additional Monitoring Tools (Referenced)

### Netdata

**Purpose:** Real-time system monitoring

**Documentation:**
- Website: https://www.netdata.cloud/
- Docker: `netdata/netdata`

**Usage in Fabrik:**
- Functions: Real-time monitoring
- Status: Referenced, not deployed

**Notes:**
- Official image available
- amd64 compatible
- Real-time metrics

---

## Additional Download Managers (Referenced)

### qBittorrent

**Purpose:** BitTorrent client

**Documentation:**
- Website: https://www.qbittorrent.org/
- Docker: `lscr.io/linuxserver/qbittorrent`

**Usage in Fabrik:**
- Functions: Torrent downloads
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

### SABnzbd

**Purpose:** Usenet download manager

**Documentation:**
- Website: https://sabnzbd.org/
- Docker: `lscr.io/linuxserver/sabnzbd`

**Usage in Fabrik:**
- Functions: Usenet downloads
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

### NZBGet

**Purpose:** Usenet download manager

**Documentation:**
- Website: https://nzbget.net/
- Docker: `lscr.io/linuxserver/nzbget`

**Usage in Fabrik:**
- Functions: Usenet downloads
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

## Additional VPN Tools (Referenced)

### WireGuard

**Purpose:** VPN protocol

**Documentation:**
- Website: https://www.wireguard.com/
- Docker: `lscr.io/linuxserver/wireguard`

**Usage in Fabrik:**
- Functions: VPN connections
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible
- Modern, fast VPN

---

### OpenVPN

**Purpose:** VPN protocol

**Documentation:**
- Website: https://openvpn.net/
- Docker: `lscr.io/linuxserver/openvpn-as`

**Usage in Fabrik:**
- Functions: VPN connections
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible
- Mature VPN solution

---

## Additional Dashboard Tools (Referenced)

### Heimdall

**Purpose:** Dashboard for services

**Documentation:**
- Website: https://heimdall.site/
- Docker: `lscr.io/linuxserver/heimdall`

**Usage in Fabrik:**
- Functions: Service dashboard
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

### Homer

**Purpose:** Dashboard for services

**Documentation:**
- Website: https://github.com/bastienwirtz/homer
- Docker: `lscr.io/linuxserver/homer`

**Usage in Fabrik:**
- Functions: Service dashboard
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

### Organizr

**Purpose:** Dashboard for services

**Documentation:**
- Website: https://organizr.app/
- Docker: `lscr.io/linuxserver/organizr`

**Usage in Fabrik:**
- Functions: Service dashboard
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

## Additional Media Servers (Referenced)

### Plex

**Purpose:** Media server

**Documentation:**
- Website: https://www.plex.tv/
- Docker: `lscr.io/linuxserver/plex`

**Usage in Fabrik:**
- Functions: Media streaming
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

### Jellyfin

**Purpose:** Media server

**Documentation:**
- Website: https://jellyfin.org/
- Docker: `lscr.io/linuxserver/jellyfin`

**Usage in Fabrik:**
- Functions: Media streaming
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible
- Open source

---

### Emby

**Purpose:** Media server

**Documentation:**
- Website: https://emby.media/
- Docker: `lscr.io/linuxserver/emby`

**Usage in Fabrik:**
- Functions: Media streaming
- Status: Referenced, not deployed

**Notes:**
- LinuxServer.io image available
- amd64 compatible

---

## Summary

**Total External Systems:** 84

**Categories:**
- Infrastructure & Deployment: 2
- DNS & Domains: 2
- Storage & Backups: 3
- Databases & Caching: 3
- Email & Communication: 5
- Translation Services: 2
- AI/LLM Services: 4
- Image & Media APIs: 3
- Scraping & Automation: 6
- Monitoring & Observability: 2
- Security & Code Quality: 1
- Development Tools: 3
- WordPress Plugins: 4
- Analytics & Tag Management: 2
- Container Registries: 3
- Infrastructure Services: 7
- Monitoring Stack: 6
- Reverse Proxy & SSL: 2
- Media & Entertainment (Referenced): 3
- Download Managers (Referenced): 3
- VPN (Referenced): 2
- Dashboards (Referenced): 3
- Additional Backup Tools (Referenced): 2
- Additional Infrastructure Tools (Referenced): 2
- Additional Web Servers (Referenced): 2
- Additional Monitoring Tools (Referenced): 1

**Status:**
- **Fully Configured:** 28 systems
- **Infrastructure Deployed:** 7 systems (Apprise, Browserless, Gotenberg, Meilisearch, Minio, n8n, Monitoring Stack)
- **Placeholder:** 8 systems (OpenAI, Anthropic, Unsplash, Gumroad, Telegram, etc.)
- **Referenced/Not Deployed:** 21 systems (Plex, Jellyfin, qBittorrent, WireGuard, etc.)

**Next Steps:**
1. Configure placeholder systems as needed
2. Add rate limit monitoring
3. Implement circuit breakers for external APIs
4. Add API health checks
5. Document error handling patterns
6. Consider deploying referenced systems as needed
