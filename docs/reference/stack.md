Below is your previous “Ultimate Stack v1.0” rewritten for **Docker + Coolify** while keeping your existing libraries, /opt layout, and WSL→VPS flow. This is the “best, easy to use, fast to monetize” path with **one repeatable deployment pattern** for all future products.

---

## DONE (what this stack guarantees when implemented)

1. **WSL is your dev factory** (Windsurf/AI coders produce code + Dockerfiles + compose).
2. **VPS is production** and is managed by **Coolify**.
3. Every product ships as **one Compose app** (web + worker + optional frontend), with:

   * one-click redeploy from GitHub,
   * required env var validation,
   * persistent storage for DB/files,
   * backups to S3 for DB (Coolify-managed).
4. You can launch a new product by copying a template folder and changing ~10 lines.

---

## 1) Core principle change: from “systemd + venv” → “Compose as the contract”

Previously, we used systemd+venv to reduce moving parts. With Coolify, the simplification flips:

### New simplification

**Docker Compose becomes the single source of truth**:

* what runs,
* how it’s configured,
* what depends on what,
* what needs persistent storage,
* how it scales (web replicas, worker replicas later).

This matches Coolify’s design: it deploys multi-container apps from Compose and uses Compose env var expansion conventions, including “required env vars.” ([Coolify][1])

---

## 2) Your updated “Ultimate Stack v1.0” (Coolify/Docker edition)

### 2.1 Infrastructure backbone (VPS)

* **Coolify** installed on the VPS as the deployment control plane.
* Ports open for HTTPS:

  * 80/443 for apps (Let’s Encrypt requires reachability; if blocked, cert issuance fails). ([Coolify][2])
* Storage:

  * Persistent volumes/bind mounts for Postgres and any file artifacts. ([Coolify][3])
* Backups:

  * Use Coolify’s scheduled DB backups to S3-compatible storage (Backblaze B2/R2/S3). ([Coolify][4])

### 2.2 Service layout (repeatable for every product)

Each product is a “Coolify Compose app” that contains:

**Always**

* `web` = FastAPI API (Uvicorn)
* `worker` = background runner (your job queue poller)
* `db` is *shared* (recommended) or per-product (optional)
* `redis` optional early (you can add later with minimal change)

**Optional**

* `frontend` = Next.js or simple UI container
* `adminer` or `pgadmin` (internal only)

Coolify supports multi-container Compose deployments. ([Coolify][5])

---

## 3) Repo & /opt structure (WSL dev + GitHub + Coolify deploy)

### 3.1 Strong recommendation: monorepo with 1 compose per product

Your WSL workspace (Git repo) should look like:

```text
ozgur-stack/
  apps/
    yt-insights/
      services/
        api/         # FastAPI service
        worker/      # job runner
        scraper/     # scrapy project (optional split)
        rag/         # indexing + retrieval logic
      compose.yaml
      .env.example
      README.md
    longevity/
      services/...
      compose.yaml
    qms-factory/
      services/...
      compose.yaml

  shared/
    py/
      core_db/       # SQLAlchemy base, session, Alembic config
      core_llm/      # LLM wrapper (OpenAI/Claude/Gemini)
      core_jobs/     # job table + job runner utilities
      core_scrape/   # proxy/captcha helpers
    docker/
      base-python.Dockerfile
      base-node.Dockerfile
    docs/
      stack-v1.md
      runbook.md
```

**Why this is “anti research-loop”:**

* every product follows the same skeleton,
* every deployment is a compose app,
* the only decisions are “which services does this product need?”.

---

## 4) Compose design (the “contract” Coolify deploys)

### 4.1 Environment variables: enforce correctness (and avoid silent misconfig)

In Coolify + Compose, you can mark env vars as **required** using Compose parameter syntax, and Coolify will surface them in the UI and block deployment if missing. ([Coolify][1])

Example pattern (important):

```yaml
environment:
  - DATABASE_URL=${DATABASE_URL:?}
  - OPENAI_API_KEY=${OPENAI_API_KEY:?}
  - WEBHOOK_SECRET=${WEBHOOK_SECRET:?}
  - LOG_LEVEL=${LOG_LEVEL:-info}
```

Coolify also only applies env vars that appear in the compose file; if a variable isn’t referenced in compose, Coolify may not apply it to a service. ([coollabstechnologiesbt.mintlify.dev][6])

### 4.2 Persistent storage: what must persist

Use volumes/bind mounts for:

* Postgres data
* any “artifact outputs” you serve (reports, exports) unless you use object storage

Coolify documents persistent storage/volumes and bind mounts. ([Coolify][3])

### 4.3 Example: “YT Insights” compose.yaml (production pattern)

This is a template-level example (you’ll customize names/paths):

```yaml
services:
  web:
    build:
      context: ./services/api
    environment:
      - DATABASE_URL=${DATABASE_URL:?}
      - APP_ENV=${APP_ENV:-prod}
      - LOG_LEVEL=${LOG_LEVEL:-info}
      - PROXY_PROVIDER=${PROXY_PROVIDER:-webshare}
      - WEBSHARE_API_KEY=${WEBSHARE_API_KEY:-}
      - ANTICAPTCHA_API_KEY=${ANTICAPTCHA_API_KEY:-}
      - GUMROAD_WEBHOOK_SECRET=${GUMROAD_WEBHOOK_SECRET:?}
    ports:
      - "8000"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz').read()"]
      interval: 30s
      timeout: 5s
      retries: 3

  worker:
    build:
      context: ./services/worker
    environment:
      - DATABASE_URL=${DATABASE_URL:?}
      - APP_ENV=${APP_ENV:-prod}
      - LOG_LEVEL=${LOG_LEVEL:-info}
      - WEBSHARE_API_KEY=${WEBSHARE_API_KEY:-}
      - ANTICAPTCHA_API_KEY=${ANTICAPTCHA_API_KEY:-}
    depends_on:
      - web

  # OPTIONAL: if you want to store generated reports locally
  artifacts:
    image: busybox
    volumes:
      - yt_artifacts:/data

volumes:
  yt_artifacts:
```

In Coolify you attach a domain to `web` and it handles routing/HTTPS via its proxy layer; HTTPS/Let’s Encrypt depends on correct DNS and open ports. ([hamy.xyz][7])

---

## 5) Databases in the Coolify world

### 5.1 Best practice for you: “one Postgres for all products” (initially)

* Create Postgres **via Coolify’s database feature** (recommended), because Coolify can then manage backups more cleanly. (This assumption is aligned with how many users set backups; Coolify’s docs focus on its database backup capability.) ([Coolify][4])

### 5.2 Backups (non-negotiable)

Use Coolify’s database backup scheduling to S3 storage. ([Coolify][4])

This gives you the “no data loss acceptable” requirement with minimal operational overhead.

---

## 6) Jobs & background work: how your previous “simple queue” maps to Docker

Previously you had:

* Postgres `jobs` table
* `worker.py` polling jobs
* tenacity retries
* schedule/systemd timers

### Now (Docker/Coolify)

You keep the logic exactly the same, but:

* `worker` is a container, not a systemd service.
* scheduling is done via:

  * either a `scheduler` container (runs periodic enqueues),
  * or the `worker` itself runs both polling + periodic tasks.

Recommended v1 pattern:

* `worker` polls the DB every N seconds (cheap, simple).
* periodic tasks (e.g., “rebuild indexes nightly”) are also stored in DB jobs and enqueued by a small `scheduler` service if you want cleaner separation.

This preserves your “no Celery needed yet” approach, but is deployable and scalable with Compose.

---

## 7) Product-level stack (updated with Docker + Coolify)

### 7.1 YouTube Scraper / Insights (fastest monetization path)

**Flow**

1. Gumroad purchase → webhook → FastAPI `/webhooks/gumroad`
2. create `job` in Postgres
3. `worker` executes: scrape → store → summarize → generate report
4. deliver:

   * email (MailerLite or SES/SMTP)
   * dashboard link on your app
   * downloadable report

**Why Docker+Coolify helps**

* web + worker ship together as one unit.
* redeploy instantly when you improve scrapers/pipelines.

### 7.2 Anti-aging / Wellness

**Flow**

* WordPress (fast SEO publishing) + embedded JS widget calling your FastAPI RAG endpoint.
* RAG service runs as a Coolify app:

  * `web` (FastAPI)
  * `worker` (index refresh / ingestion)
* TR/EN:

  * WP multilingual + RAG answers in query language.

### 7.3 Remote QMS Factory

**Flow**

* Landing page + intake form → creates Engagement in DB.
* Worker generates:

  * doc request checklist
  * initial templates
  * trace matrices
  * CAPA/risk logs
* Delivery:

  * shared client repository + your internal portal (later)
* Kommo becomes optional early; you can run pipeline inside your portal first, then integrate when leads scale.

Docker+Coolify value:

* This becomes a “productized service OS” you can clone and reuse.

---

## 8) How to actually deploy in Coolify (repeatable playbook)

### 8.1 Per product (YT, Longevity, QMS)

1. Create a new Coolify application using **Docker Compose build pack**. ([Coolify][5])
2. Connect GitHub repo.
3. Select `apps/<product>/compose.yaml`.
4. Use Compose env var references so Coolify can manage them:

   * required: `${VAR:?}`
   * optional default: `${VAR:-default}` ([Coolify][1])
5. In Coolify UI, fill env vars (remember: variables must exist in compose to be applied). ([coollabstechnologiesbt.mintlify.dev][6])
6. Add domain as `https://...` so Coolify triggers cert issuance (and ensure DNS A-record points to the VPS). ([hamy.xyz][7])

### 8.2 Shared DB

* Create Postgres in Coolify “Databases”.
* Turn on scheduled backups to S3. ([Coolify][4])
* Set `DATABASE_URL` in each app.

---

## 9) Updated “Frozen Decisions” (90-day execution lock)

### Infra

* Deployment control plane: **Coolify**
* Runtime: **Docker Compose per product**
* DB: **Postgres 16** (Coolify-managed if possible)
* API: **FastAPI**
* Jobs: **Postgres jobs table + worker container**
* Scraping: **Scrapy + playwright** + Webshare + Anti-captcha
* RAG: Postgres + pgvector + (LangChain or LlamaIndex; pick one)
* Backups: Coolify scheduled DB backups → S3 ([Coolify][4])

### Business layer (unchanged)

* Gumroad, MailerLite, Substack, Skool, Kommo, WordPress.

---

## 10) Concrete next steps (the shortest path to “money loop”)

### Step 1 — Make “YT Insights” the reference deployment

1. Add Dockerfiles:

   * `services/api/Dockerfile`
   * `services/worker/Dockerfile`
2. Add `compose.yaml` with required env vars `${VAR:?}`. ([Coolify][1])
3. Deploy in Coolify from GitHub using Docker Compose build pack. ([Coolify][5])
4. Add HTTPS domain; fix DNS/ports if cert fails. ([hamy.xyz][7])
5. Connect Gumroad webhook → create job → deliver report.

### Step 2 — Clone that app template twice

* Copy folder structure for `longevity` and `qms-factory`.
* Only change:

  * env vars
  * routes
  * templates
  * ingestion sources

That's how you scale to 3 businesses without new architecture each time.

---

## 11) Current Tools & Services Inventory

> **Source:** Extracted from all `/opt/*/.env` files and dependency manifests. Updated 2025-12-22.

### 11.1 Active Projects in /opt

> **Full project registry with statuses:** See `@/opt/fabrik/docs/reference/project-registry.md`

#### Tier 1: Infrastructure Services (Deploy First)

| Project | Purpose | Stack | Port | Status |
|---------|---------|-------|------|--------|
| `/opt/proxy` | Proxy management (Webshare.io) | Python | 8000 | ✅ Deployed VPS |
| `/opt/captcha` | Captcha solving wrapper | FastAPI, Anti-Captcha | 8000 | ✅ Deployed VPS |
| `/opt/emailgateway` | Email sending gateway | Node.js/Fastify, Resend, SES | 3000 | ✅ Deployed VPS |
| `/opt/translator` | Translation service | FastAPI, DeepL, Azure | 8000 | ✅ Deployed VPS |
| `/opt/email-reader` | Email reading (Gmail, M365) | FastAPI, Google/Microsoft APIs | 5050 | 🟡 WSL only |
| `/opt/namecheap` | DNS management | FastAPI, Namecheap API | 8001 | ✅ Deployed VPS |

#### Tier 2: Core Products

| Project | Purpose | Stack | Port | Status |
|---------|---------|-------|------|--------|
| `/opt/youtube` | YouTube scraping, transcription, comments | Python, PostgreSQL | - | 🟡 Active Dev |
| `/opt/calendar-orchestration-engine` | Calendar/holiday data | Express, PostgreSQL | 3001 | ✅ Ready for VPS |
| `/opt/proposal-creator` | Proposal/document generation (SaaS potential) | Python, Claude, WeasyPrint | - | ✅ Working |
| `/opt/image-generation` | AI image generation for all projects | Python, BFL API | - | 🔴 In Dev |
| `/opt/llm_batch_processor` | Web-based ChatGPT/Claude automation | Python, Playwright | - | ✅ Working |

#### Tier 3: Future Products

| Project | Purpose | Status |
|---------|---------|--------|
| `/opt/brand-identity-creator` | Brand design automation | 🔴 Needs Dev |
| `/opt/complianceOS` | Compliance management SaaS | 📋 Planned (10 days) |
| `/opt/trade-intelligence` | Foreign trade intelligence (billofladingdata.com) | 🔴 Starting |
| `/opt/triggered-content-orchestration` | Content publishing automation (SaaS) | 📋 Major project |
| `/opt/ugc` | User-generated content collection (forums) | 📋 Not started |
| `/opt/spect-interviewer` | Project specification assistant | 🟡 Early stage |

#### Support & Utilities

| Project | Purpose | Status |
|---------|---------|--------|
| `/opt/iterative_image_editor` | Image editing with FLUX | 🟡 Dev (merge into image-generation?) |
| `/opt/backupsystem` | Backup automation (WSL) | ✅ Working |
| `/opt/backup` (VPS) | VPS backup to B2 | ✅ Deployed VPS |
| `/opt/fabrik` | Deployment automation CLI | 🟡 In Development |
| `/opt/web-scraper` | Scrapers for calendar-orchestration-engine | ✅ Working |

---

### 11.2 External APIs & Services

#### Speech & Transcription

| Service | Provider | Usage | Project |
|---------|----------|-------|---------|
| **Soniox** | soniox.com | Speech-to-text transcription | youtube |

#### Video & Media

| Service | Provider | Usage | Project |
|---------|----------|-------|---------|
| **YouTube Data API** | Google | Metadata, comments, captions, search | youtube |
| **RapidAPI YT Downloader** | RapidAPI | Video/audio downloading (50k req/mo) | youtube |
| **yt-dlp** | Open source | YouTube downloader | youtube |
| **FLUX Kontext Pro** | Black Forest Labs (BFL) | AI image generation/editing | iterative_image_editor |

#### Proxy & Anti-Bot

| Service | Provider | Usage | Project |
|---------|----------|-------|---------|
| **Webshare.io** | webshare.io | Datacenter/residential proxies | youtube, proxy, namecheap |
| **Anti-Captcha** | anti-captcha.com | Captcha solving | captcha, youtube |
| **Apify** | apify.com | YouTube Comments Scraper (fallback) | youtube, proxy |
| **Tor** | torproject.org | SOCKS5 proxy (fallback) | youtube |

#### Translation

| Service | Provider | Usage | Project |
|---------|----------|-------|---------|
| **DeepL API** | DeepL | Primary translation (500k chars/mo free) | translator |
| **Azure Translator** | Microsoft | Fallback translation (2M chars/hr) | translator |

#### Email

| Service | Provider | Usage | Project |
|---------|----------|-------|---------|
| **Resend** | resend.com | Primary email sending (100/day) | emailgateway |
| **Amazon SES** | AWS | Backup email sending (200/day) | emailgateway |
| **Gmail API** | Google | Email reading (ozgur@adazonia.com) | email-reader |
| **Microsoft Graph** | Microsoft | Email reading (ob@ocoron.com) | email-reader |

#### AI & LLM

| Service | Provider | Usage | Project |
|---------|----------|-------|---------|
| **Claude** | Anthropic | AI content generation | proposal-creator |
| **Factory.ai Droid** | Factory.ai | AI coding/automation, batch processing | proposal-creator, calendar-orchestration-engine |
| **ChatGPT/Claude Web** | OpenAI/Anthropic | Web interface automation | llm_batch_processor |

#### DNS & Domains

| Service | Provider | Usage | Project |
|---------|----------|-------|---------|
| **Namecheap API** | Namecheap | Domain/DNS management | namecheap |

#### Calendar & Data

| Service | Provider | Usage | Project |
|---------|----------|-------|---------|
| **Abstract API** | abstractapi.com | Holiday/calendar data | calendar-orchestration-engine |
| **Nager.Date** | nager.date | Public holiday API | calendar-orchestration-engine |

#### Infrastructure

| Service | Provider | Usage | Project |
|---------|----------|-------|---------|
| **Coolify** | coolify.io | Deployment control plane | fabrik (planned) |
| **Backblaze B2** | Backblaze | Backup storage | fabrik (planned) |

---

### 11.3 Databases

| Database | Version | Usage | Projects |
|----------|---------|-------|----------|
| **PostgreSQL** | 16 | Primary relational DB | youtube, translator, calendar-orchestration-engine, proxy, llm_batch_processor, namecheap |
| **SQLite** | - | Lightweight embedded DB | emailgateway |

#### Database Instances

| Database Name | Project | User |
|---------------|---------|------|
| `youtube_pipeline` | youtube | youtube_user |
| `proxy_management` | proxy, youtube | postgres/ozgur |
| `translator_service` | translator | postgres |
| `calendar_engine` | calendar-orchestration-engine | postgres |
| `llm_batch` | llm_batch_processor | llm_batch |

---

### 11.4 Python Libraries

#### Web Frameworks & APIs

| Library | Version | Purpose | Projects |
|---------|---------|---------|----------|
| **FastAPI** | ≥0.104 | Web framework | captcha, translator, email-reader, namecheap |
| **Uvicorn** | ≥0.24 | ASGI server | captcha, translator, email-reader, namecheap |
| **Pydantic** | ≥2.0 | Data validation | captcha, translator, namecheap, llm_batch_processor |
| **pydantic-settings** | ≥2.0 | Settings management | captcha, translator, namecheap, llm_batch_processor |

#### Database

| Library | Version | Purpose | Projects |
|---------|---------|---------|----------|
| **psycopg2-binary** | ≥2.9.9 | PostgreSQL sync driver | youtube |
| **asyncpg** | ≥0.29 | PostgreSQL async driver | translator, llm_batch_processor |
| **SQLAlchemy** | ≥2.0 | ORM | translator |
| **Alembic** | ≥1.13 | Database migrations | translator |

#### HTTP & Networking

| Library | Version | Purpose | Projects |
|---------|---------|---------|----------|
| **httpx** | ≥0.25 | Async HTTP client | captcha, translator, namecheap, llm_batch_processor |
| **requests** | ≥2.31 | HTTP library | youtube, namecheap, iterative_image_editor |
| **aiofiles** | ≥23.2 | Async file I/O | translator |
| **PySocks** | ≥1.7.1 | SOCKS proxy support | youtube |

#### Web Scraping & Automation

| Library | Version | Purpose | Projects |
|---------|---------|---------|----------|
| **yt-dlp** | ≥2024.10 | YouTube downloader | youtube |
| **Selenium** | ≥4.15 | Browser automation | youtube |
| **undetected-chromedriver** | ≥3.5.4 | Anti-bot Chrome driver | youtube |
| **youtube-comment-downloader** | ≥0.1.78 | Comment extraction | youtube |
| **apify-client** | ≥2.3 | Apify API client | youtube |
| **Playwright** | ≥1.40 | Browser automation | llm_batch_processor |

#### CLI & Output

| Library | Version | Purpose | Projects |
|---------|---------|---------|----------|
| **Click** | ≥8.1 | CLI framework | namecheap, proposal-creator, llm_batch_processor |
| **Rich** | ≥13.0 | Terminal formatting | namecheap, proposal-creator, llm_batch_processor |
| **colorlog** | ≥6.8 | Colored logging | youtube |

#### Utilities

| Library | Version | Purpose | Projects |
|---------|---------|---------|----------|
| **python-dotenv** | ≥1.0 | Environment loading | all |
| **PyYAML** | ≥6.0 | YAML parsing | youtube, namecheap, proposal-creator, llm_batch_processor |
| **tenacity** | ≥8.2 | Retry logic | translator, namecheap |
| **python-dateutil** | ≥2.8 | Date utilities | translator, proposal-creator |
| **psutil** | ≥5.9.6 | System utilities | youtube |
| **schedule** | ≥1.2.1 | Background scheduling | namecheap |

#### Image Processing

| Library | Version | Purpose | Projects |
|---------|---------|---------|----------|
| **Pillow** | ≥9.0 | Image processing | iterative_image_editor |
| **NumPy** | ≥1.20 | Numerical computing | iterative_image_editor |
| **OpenCV** | ≥4.5 | Computer vision | iterative_image_editor |
| **rembg** | ≥2.0 | Background removal | iterative_image_editor |
| **scikit-image** | ≥0.19 | Image processing | iterative_image_editor |
| **ONNX Runtime** | ≥1.15 | ML inference | iterative_image_editor |

#### Document Generation

| Library | Version | Purpose | Projects |
|---------|---------|---------|----------|
| **WeasyPrint** | ≥60.0 | PDF generation | proposal-creator |
| **Jinja2** | ≥3.1 | Templating | proposal-creator |
| **Markdown** | ≥3.5 | Markdown processing | proposal-creator |
| **jsonschema** | ≥4.20 | JSON validation | proposal-creator |

#### AI/LLM

| Library | Version | Purpose | Projects |
|---------|---------|---------|----------|
| **anthropic** | ≥0.40 | Claude API client | proposal-creator |

#### Authentication

| Library | Version | Purpose | Projects |
|---------|---------|---------|----------|
| **google-api-python-client** | ≥2.100 | Google APIs | email-reader |
| **google-auth-oauthlib** | ≥1.0 | Google OAuth | email-reader |
| **msal** | ≥1.20 | Microsoft authentication | email-reader |

#### Testing & Development

| Library | Version | Purpose | Projects |
|---------|---------|---------|----------|
| **pytest** | ≥7.0 | Testing framework | translator, namecheap, llm_batch_processor |
| **pytest-asyncio** | ≥0.23 | Async testing | translator, namecheap, llm_batch_processor |
| **pytest-cov** | ≥4.0 | Coverage | namecheap, llm_batch_processor |
| **ruff** | ≥0.1 | Linter/formatter | namecheap, llm_batch_processor |
| **black** | ≥23.12 | Code formatter | namecheap, llm_batch_processor |
| **mypy** | ≥1.0 | Type checker | namecheap, llm_batch_processor |

---

### 11.5 Node.js / TypeScript Libraries

#### Web Frameworks

| Library | Version | Purpose | Projects |
|---------|---------|---------|----------|
| **Express** | ≥5.2 | Web framework | calendar-orchestration-engine |
| **Fastify** | ≥4.28 | Web framework | emailgateway |

#### Database

| Library | Version | Purpose | Projects |
|---------|---------|---------|----------|
| **pg** | ≥8.16 | PostgreSQL client | calendar-orchestration-engine |
| **sql.js** | ≥1.11 | SQLite in-memory | emailgateway |

#### Email

| Library | Version | Purpose | Projects |
|---------|---------|---------|----------|
| **Nodemailer** | ≥6.9 | Email sending (SES) | emailgateway |

#### Utilities

| Library | Version | Purpose | Projects |
|---------|---------|---------|----------|
| **dotenv** | ≥17.2 | Environment loading | emailgateway, calendar-orchestration-engine |
| **date-fns** | ≥4.1 | Date utilities | calendar-orchestration-engine |
| **date-fns-tz** | ≥3.2 | Timezone support | calendar-orchestration-engine |
| **cron** | ≥4.4 | Job scheduling | calendar-orchestration-engine |
| **uuid** | ≥10.0 | UUID generation | emailgateway |
| **Zod** | ≥3.23 | Schema validation | emailgateway |
| **envalid** | ≥8.0 | Environment validation | emailgateway |

#### Logging

| Library | Version | Purpose | Projects |
|---------|---------|---------|----------|
| **Pino** | ≥9.4 | Structured logging | emailgateway |
| **pino-pretty** | ≥11.2 | Log formatting | emailgateway |

#### Frontend (Admin UI)

| Library | Version | Purpose | Projects |
|---------|---------|---------|----------|
| **React** | ≥18.2 | UI framework | calendar-orchestration-engine |
| **Vite** | ≥5.0 | Build tool | calendar-orchestration-engine |
| **TailwindCSS** | ≥4.x | CSS framework | calendar-orchestration-engine |
| **Lucide React** | latest | Icons | calendar-orchestration-engine |

#### TypeScript

| Library | Version | Purpose | Projects |
|---------|---------|---------|----------|
| **TypeScript** | ≥5.6 | Type system | emailgateway, calendar-orchestration-engine |
| **ts-node** | ≥10.9 | TypeScript execution | calendar-orchestration-engine |
| **tsx** | ≥4.19 | TypeScript execution | emailgateway |

---

### 11.6 API Keys & Credentials Summary

> **Security Note:** All credentials stored in `.env` files (gitignored). Never commit to git.

| Service | Env Variable | Project(s) |
|---------|--------------|------------|
| Soniox | `SONIOX_API_KEYS` | youtube |
| YouTube Data API | `YOUTUBE_API_KEY` | youtube |
| RapidAPI | `RAPIDAPI_KEY` | youtube |
| Webshare.io | `WEBSHARE_API_KEY` | youtube, proxy, namecheap |
| Anti-Captcha | `ANTICAPTCHA_API_KEY` | captcha |
| Apify | `APIFY_API_TOKEN` | youtube, proxy |
| Factory.ai | `FACTORY_API_KEY` | proposal-creator, calendar-orchestration-engine |
| DeepL | `DEEPL_API_KEY` | translator |
| Azure Translator | `AZURE_TRANSLATOR_KEY` | translator |
| Resend | `RESEND_API_KEY` | emailgateway |
| Amazon SES | `SES_SMTP_USER`, `SES_SMTP_PASS` | emailgateway |
| Google OAuth | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | email-reader |
| Microsoft 365 | `M365_CLIENT_ID`, `M365_TENANT_ID` | email-reader |
| Namecheap | `NAMECHEAP_API_KEY`, `NAMECHEAP_API_USER` | namecheap |
| Abstract API | `ABSTRACT_API_KEY` | calendar-orchestration-engine |
| BFL (FLUX) | `BFL_API_KEY` | iterative_image_editor |

---

### 11.7 VPS & Infrastructure

| Component | Value | Notes |
|-----------|-------|-------|
| **VPS IP** | 172.93.160.197 | Production server |
| **SSH User** | ozgur / deploy | Admin access |
| **SSH Key** | ~/.ssh/id_rsa | Local key |
| **OS** | Ubuntu | VPS |
| **Dev Environment** | WSL Ubuntu | Windows host |

---

If you paste your current YouTube project's components (what processes exist: API? worker? scraper? where files are stored?), I can output a **production-grade compose.yaml** tailored to it (including volumes, healthchecks, and Coolify-friendly env var patterns).

[1]: https://coolify.io/docs/knowledge-base/docker/compose?utm_source=chatgpt.com "Docker Compose | Coolify Docs"
[2]: https://coolify.io/docs/troubleshoot/dns-and-domains/lets-encrypt-not-working?utm_source=chatgpt.com "Let's Encrypt Not Generating SSL Certificates on Coolify | Coolify"
[3]: https://coolify.io/docs/knowledge-base/persistent-storage?utm_source=chatgpt.com "Persistent Storage | Coolify Docs"
[4]: https://coolify.io/docs/databases/backups?utm_source=chatgpt.com "Backups | Coolify Docs"
[5]: https://coolify.io/docs/applications/build-packs/docker-compose?utm_source=chatgpt.com "Docker Compose Build Packs | Coolify Docs"
[6]: https://coollabstechnologiesbt.mintlify.dev/docs/knowledge-base/docker/compose?utm_source=chatgpt.com "How to use Docker Compose deployments with Coolify."
[7]: https://hamy.xyz/blog/2025-03_coolify-https-domains?utm_source=chatgpt.com "How to Setup an Https Custom Domain with Coolify"
