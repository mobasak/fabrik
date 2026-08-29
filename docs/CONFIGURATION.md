# Configuration Guide

**Last Updated:** 2026-08-25

**Purpose:** This guide explains HOW to configure Fabrik and WHY certain configurations exist. For WHAT variables are needed, see `.env.example` which is self-documenting.

---

## Quick Setup

```bash
# 1. Copy template
cp .env.example .env

# 2. Edit with your values
nano .env

# 3. Verify (fabrik.config has no CLI/--verify flag — instantiate Config()
#    directly; it raises ValueError if a required var, e.g. VPS_HOST, is missing)
python -c "from fabrik.config import Config; Config(); print('OK — required vars present')"
```

**All variables are documented in `.env.example` with inline comments.**

---

## Getting Credentials

### VPS Access

**Why needed:** Deploy applications to your VPS via `fabrik apply` (SSH + Docker Compose).

**How to get:**
1. Provision VPS (DigitalOcean, Linode, etc.)
2. Note public IP (`VPS_IP`, `VPS_HOST`)
3. Create deploy user:
   ```bash
   ssh root@your-vps
   adduser deploy
   usermod -aG sudo deploy
   ```
4. Set up SSH key (optional but recommended):
   ```bash
   ssh-copy-id deploy@your-vps
   ```

<!--
Coolify API Token section — REMOVED 2026-06-02 (coolify-residue-cleanup plan).

Coolify was fully removed from vps1 on 2026-05-30 (no containers, no binary;
only /data/coolify/ filesystem residue remains). The active deploy path is
SSH + Docker Compose (`fabrik apply`). The legacy CLI commands (`fabrik status`,
`fabrik logs`, `fabrik reconcile-all`) that historically talked to the Coolify
API are now non-functional and listed under "Known broken" in the SSH-deployer
archived plan.

New projects never needed a Coolify API token.
-->

### FABRIK_EXEC_MODE — WordPress driver execution mode

> **⚠️ RETIRED — not merely moved.** WordPress left this repo for a standalone `/opt/wpf` project
> (2026-06-17), and **that project was itself ARCHIVED to `/opt/archived/wpf` on 2026-08-07**.
> `/opt/wpf` no longer exists, so the pointer this section used to give sent readers to a path that
> is gone. There is no `fabrik.drivers.wordpress` module in `/opt/fabrik` and no supported WordPress
> driver anywhere on the box; `FABRIK_EXEC_MODE` is not read by anything in this repo. The
> `wordpress` scaffold type survives only for legacy deploy/shape routing. Kept here as a
> *tombstone* — the variable is documented so nobody re-adds it thinking it was an oversight.

**Why needed:** The driver historically assumed it was running on a WSL workstation that reaches the VPS over SSH. On-VPS execution surfaces (systemd cron, self-healing watchdog) make wrapping every `docker exec` in `ssh vps …` pointless overhead. `FABRIK_EXEC_MODE` flips the dispatch at the driver level so the same code path runs unchanged in both environments.

**Values:**

| Value | When to use | Effect |
|-------|-------------|--------|
| `ssh` (default; unset = `ssh`) | WSL development; any remote orchestration | Driver invokes `ssh ${VPS_HOST} 'sudo docker exec …'` — byte-identical to pre-T1.1 behaviour |
| `local` | `fabrik` CLI running ON the VPS itself (T1.5 systemd cron, Phase 5 self-healing watchdog) | Driver invokes `sudo docker exec …` directly as an argv list — zero outbound SSH |

**Fail-fast:** any other value (e.g. `paramiko`, `remote`, typos) raises `ValueError` at the first driver call with the malformed value echoed back. Bad config surfaces immediately rather than ~30s into the first `docker exec` timeout.

**Back-compat guarantee:** unset env + unset constructor `exec_mode=` kwarg → SSH path. Existing WSL workflows and orchestration code that already pass `ssh_host=` keep working unchanged.

**Override precedence:** constructor `exec_mode=` kwarg > `FABRIK_EXEC_MODE` env var > `ssh` default. The constructor seam exists so unit tests and future orchestrators can pin the mode without mutating process env.

### DNS (Cloudflare driver)

> **⚠️ RETIRED — not deployed.** The dns-manager microservice was retired; `dns.vps1.ocoron.com` returns NXDOMAIN. DNS is now handled directly via the Cloudflare driver (`src/fabrik/drivers/cloudflare.py`). The historical service architecture below is kept for reference.

**Why this approach:** Fabrik talks to the Cloudflare API directly via the driver — no separate DNS microservice to deploy or keep healthy.

**Architecture:**
- ~~DNS Manager service runs at `https://dns.vps1.ocoron.com`~~ (retired)
- Cloudflare driver handles DNS record creation/updates
- Requires `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ZONE_ID` (see `.env.example`)

### Backblaze B2

**Why needed:** Encrypted backups of all project data.

**How to get:**
1. Create account: https://www.backblaze.com/b2/sign-up.html
2. Buckets → Create Bucket → Note name
3. App Keys → Add New → Copy ID and Key
4. Generate strong passphrase for encryption:
   ```bash
   python -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32)))"
   ```

### Docker Hub

**Why needed:** Private container images for proprietary services.

**How to get:**
1. Create account: https://hub.docker.com
2. Account Settings → Security → New Access Token
3. Select "Read, Write, Delete" permissions
4. Copy token (shown once)

### Content Creation Pipeline

**Architecture:** Three microservices orchestrate SEO-driven content generation:
1. **SEO Service** (port 8016) — Keyword research, clustering, content briefs
2. **TCO** (port 8025) — AI content generation from briefs
3. ~~**Image Broker** (port 18016) — Stock image selection (Pexels/Pixabay)~~ — **RETIRED 2026-06-02** (not deployed; `images.vps1.ocoron.com` returns NXDOMAIN)

**Environment variables:**
- `SEO_API_URL` — SEO service endpoint (http://localhost:8016 or https://seo.vps1.ocoron.com)
- `SEO_API_KEY` — Bearer token for SEO service authentication
- `TCO_API_URL` — TCO service endpoint (http://localhost:8025)
- `TCO_API_KEY` — Bearer token for TCO authentication
- ~~`IMAGE_BROKER_URL` — Image Broker endpoint (http://localhost:18016)~~ — **RETIRED 2026-06-02** (image-broker no longer deployed)
- `CONTENT_WORKER_ID` — Worker identifier for brief lifecycle tracking (default: fabrik-content-publisher)

**WordPress credentials:** `WP_ADMIN_USER` / `WP_ADMIN_PASSWORD` were read by the standalone `wpf` project, which was **archived to `/opt/archived/wpf` on 2026-08-07** — nothing in `/opt/fabrik` reads them, and the path this line used to cite no longer exists. Listed as a tombstone only; do not provision them.

**Development:** All services run locally via docker-compose. Use `http://localhost:PORT`.
**Production:** Services deployed on VPS at `*.vps1.ocoron.com` with internal Docker networking.

### AI Model Aggregator Keys

Used by `scripts/kilo-benchmarks/fetch_*_prices.py` to populate `agents.gateway_prices` with live per-model pricing across aggregators, so the AI Models Browser surfaces the cheapest gateway per row (same OR ↔ Kilo cheapest-rate pattern, extended to non-LLM specialists). See [docs/development/plans/archived/2026-06-29-plan-2-aggregator-pricing.md](development/plans/archived/2026-06-29-plan-2-aggregator-pricing.md).

- `FAL_KEY` — fal.ai key in `KEY_ID:SECRET` format. Get from [fal.ai/dashboard/keys](https://fal.ai/dashboard/keys). Read-only catalog access is sufficient for price discovery. **Positive balance required** for the specialty bench (`microbench_specialty.py`) since it enqueues real image generations against Fal.ai's BFL Flux mirror.

### NVIDIA Build — `NVIDIA_API_KEY` (free inference endpoints)

- `NVIDIA_API_KEY` — NVIDIA Build (build.nvidia.com) free, OpenAI-compatible inference at
  `https://integrate.api.nvidia.com/v1` (`nvapi-*` format; console key name
  `NVIDIABuild-Autogen-17`). $0 — free endpoints only, rate-limited per key. 83 model ids live
  as of 2026-08-26 (nemotron-3 family incl. the 1M-context `nemotron-3-ultra-550b-a55b`,
  `deepseek-v4-flash-0731`, `kimi-k3`, `gpt-oss-120b/20b`, vision/embedding/safety/translation
  specialists). Catalog + subagents-pool compatibility verdict:
  [docs/reference/nvidia-build.md](reference/nvidia-build.md). Full listing:
  `curl -H "Authorization: Bearer $NVIDIA_API_KEY" https://integrate.api.nvidia.com/v1/models`.
- `NVIDIA_API_KEY_2` / `_3` / `_4` — spare keys (all probed live HTTP 200, 2026-08-29;
  same free endpoint, per-key rate limits — spares for parallel harnesses or manual selection
  `NVIDIA_API_KEY=$NVIDIA_API_KEY_2 <cmd>`; rotation-on-429 inside the pool module is filed to
  fabrik-lib).

### Mistral La Plateforme — `MISTRAL_API_KEY` (+ spares, $10/month hard cap)

- `MISTRAL_API_KEY` — Mistral's free Experiment tier at `https://api.mistral.ai/v1`
  (OpenAI-compatible). $0; **per-model** limits: 1 req/s · 500k tok/min · 1B tok/month
  (console → Limits is the live authority). 54 models as of 2026-08-27 incl.
  `mistral-large-2512`, `mistral-medium-3.5`, codestral/devstral, magistral (reasoning),
  voxtral (audio), OCR. ⚠️ The free tier trains on submitted data — send public/low-sensitivity
  content only. Payload-screened 2026-08-27 for the crowdlex haiku-replacement:
  `mistral-medium-latest` 7.1s at 40k chars with 10/10 verbatim quotes; `mistral-large-latest`
  times out (>100s) at that size. Full listing:
  `curl -H "Authorization: Bearer $MISTRAL_API_KEY" https://api.mistral.ai/v1/models`.
- `MISTRAL_API_KEY_2` / `_3` / `_4` — spare keys (same per-key limits; select manually:
  `MISTRAL_API_KEY=$MISTRAL_API_KEY_2 <cmd>`).
- ⚠️ **The free tier is a $10/month CREDIT — an exhausted credit returns HTTP 401 until the
  monthly reset** (operator-confirmed 2026-08-29: all four keys 401'd because the month's
  credits were spent; this is the expected exhausted state, not key revocation). A 401 from
  Mistral therefore means "no credit left this month" first — re-probe after the reset before
  suspecting the key itself.
- `MISTRAL_MONTHLY_CAP_USD=10` — the monthly credit envelope (operator directive 2026-08-29).
  Any consumer driving Mistral usage must read it and budget within the envelope so credit
  lasts the month instead of dying mid-month; no per-call caps (sysadmin-loop rule) — the
  budget is monthly.

### Specialty-service bench providers (kilo-benchmarks)

Used by `/opt/ai-model-catalog/engine/microbench_specialty.py` (ai-model-catalog) to fill the AI Models Browser Speed column for non-LLM rows (`image_gen`, `tts`, `music_gen`, `stt`, `translation`). Sunday cron; $10 hard / $2.50 soft per-run cost cap. See [docs/development/plans/archived/2026-07-03-plan-1-full-speed-coverage-close.md](development/plans/archived/2026-07-03-plan-1-full-speed-coverage-close.md).

- `REPLICATE_API_TOKEN` — Replicate prediction API. Get from [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens). Unlocks Stability SD family + Stable Audio rows (~6 rows).
- `RECRAFT_API_KEY` — Recraft direct REST. Get from [recraft.ai/profile/api](https://www.recraft.ai/profile/api). Unlocks `recraft/v3` + `recraft/nano-banana` (~2 rows; 40 credits ≈ $0.04 per image).
- `DASHSCOPE_API_KEY` — Alibaba DashScope, `sk-ws-…` format. Get from [dashscope.console.aliyun.com](https://dashscope.console.aliyun.com/apiKey). Unlocks `qwen/qwen-mt-turbo` (translation).
- `SILICONFLOW_API_KEY` — SiliconFlow 72-model gateway (LLMs: Qwen 2.5→3.6, DeepSeek V3/V4, GLM 4.5→5.2, Kimi K2.5-2.7, MiniMax M2.5/M3, Tencent Hunyuan+Hy3, gemma-4, gpt-oss-20b/120b; images: full FLUX + Qwen-Image + Wan2.2 + Z-Image-Turbo; TTS: fish-speech-1.5, IndexTTS-2, CosyVoice2; Qwen3-Embedding 0.6B/4B/8B; Qwen3-Reranker 0.6B/8B). Use INTERNATIONAL endpoint `https://api.siliconflow.com/v1` — the `.cn` endpoint has a different key domain (returns 401 on international keys). Get from [cloud.siliconflow.com/account/ak](https://cloud.siliconflow.com/account/ak). Full catalog: `curl -H "Authorization: Bearer $SILICONFLOW_API_KEY" https://api.siliconflow.com/v1/models`.
- `MODELSCOPE_API_KEY` — ModelScope 55-model Alibaba model-hub gateway (OpenAI-compatible). Notable coverage: **ZhipuAI direct** (GLM-5.2 / 5.1 / 5 / 4.7-Flash — Zhipu's own inference), **Shanghai AI Lab Intern-S series** (S1 / S1-mini / S2-Preview — InternLM3's successors), **PaddlePaddle ERNIE-4.5** (Baidu), **Xiaomi MiMo-V2-Flash**, **Tencent Hunyuan Hy3**, **XiYanSQL**, plus 20 Qwen / MiniMax M2.5-M3 / DeepSeek V3.2-V4 / Kimi K2.5 / mistralai Mistral-Large. Format: `ms-*`. Endpoint: `https://api-inference.modelscope.cn/v1` (OpenAI-compatible). Get from [modelscope.cn/my/myaccesstoken](https://modelscope.cn/my/myaccesstoken). Full catalog: `curl -H "Authorization: Bearer $MODELSCOPE_API_KEY" https://api-inference.modelscope.cn/v1/models`.
- `HF_TOKEN` — HuggingFace Inference Providers meta-gateway (Novita / Sambanova / Fireworks / Together / Cerebras — one key, many downstream providers). Router endpoint `https://router.huggingface.co/v1` is OpenAI-compatible. Format: `hf_*`. Get from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens). **Token saved 2026-07-10; scraper + `via_hf` column ingestion pending** (see [`docs/reference/kilo/AGGREGATOR_ROADMAP.md`](reference/kilo/AGGREGATOR_ROADMAP.md) — NEXT AGGREGATOR wire-in, mirrors the ModelScope plan-2 pattern).
- `DEEPINFRA_API_KEY` — DeepInfra direct gateway (Tier 1 per [`AGGREGATOR_ROADMAP.md`](reference/kilo/AGGREGATOR_ROADMAP.md)). Pure savings — bypasses OpenRouter's 5.5% fee on models where DeepInfra is already OR's cheapest provider (deepseek-v4-flash, kimi-k2.7-code, deepseek-r1-0528, glm-5.2, and many more). OpenAI-compatible endpoint `https://api.deepinfra.com/v1/openai`. Get from [deepinfra.com/dash/api_keys](https://deepinfra.com/dash/api_keys). **Token saved 2026-07-10; scraper + `via_deepinfra` column ingestion pending** (roadmap step 2, mirrors ModelScope plan-2 pattern).
- `ELEVENLABS_API_KEY` — ElevenLabs REST. Get from [elevenlabs.io/app/settings/api-keys](https://elevenlabs.io/app/settings/api-keys). Unlocks TTS (`multilingual-v2`, `turbo-v2.5`, `eleven-v3-alpha`) + `sound-effects` (~4 rows). Free tier absorbs the bench cost (~2.4k of 10k chars).

### GlitchTip (error tracking)

GlitchTip (`errors.vps1.ocoron.com`, Sentry-compatible) is declared in `specs/infrastructure/glitchtip.yaml` and is the error-tracker source for the AI watchdog (`org=ocoron`, `team=vps1`). It reuses `postgres-main` (DB `glitchtip`) + `redis-main`. Env vars:

- `GLITCHTIP_SECRET_KEY` — Django secret key. **Use the existing live value** (`/opt/glitchtip/compose.yaml`); changing it invalidates all sessions.
- `GLITCHTIP_REDIS_URL` — e.g. `redis://redis-main:6379/<db>` (existing live value).
- `POSTGRES_PASSWORD` — shared `postgres-main` superuser password (already provisioned).

⚠️ Do not `fabrik apply specs/infrastructure/glitchtip.yaml` until these match the live deployment, or the live tracker + its session keys break. The spec declares the existing hand-deployed stack; `fabrik apply` is targeted, so adding it does not auto-redeploy.

### Watchdog DB access — `WATCHDOG_DB_URL_RO` / `WATCHDOG_DB_URL_RW` (auto-injected, do NOT set by hand)

For a watchdog-enabled project with `shape.needs_database`, the postgres registrar auto-provisions two per-project roles on the app DB and injects their DSNs into the project `.env` at `fabrik apply`: `WATCHDOG_DB_URL_RO` (SELECT-only, the sidecar's default diagnosis lane) and `WATCHDOG_DB_URL_RW` (DML-only — no DDL/DROP — the Tier-C approved-write lane). These are **generated + managed by the hub, never operator-set** (like `DATABASE_URL`): minted on fresh role creation, preserved on re-apply. Full contract + privilege boundary in the `WATCHDOG` rule pack (`.windsurf/rules/core/60-watchdog.md`).

### Payments webhook ingest — `PAYMENTS_INGEST_DATABASE_URL` (auto-injected, do NOT set by hand)

For a project with `shape.needs_payments_ingest` (vendors fabrik-lib `payments`, takes UNSIGNED-provider webhooks — iyzico has no signed org field), the postgres registrar mints a **scoped, NON-BYPASSRLS** cross-tenant ingest role and injects `PAYMENTS_INGEST_DATABASE_URL` at `fabrik apply` (hub-generated, never operator-set; minted on fresh create, preserved on re-apply — like `DATABASE_URL`). The role exists because `PgWebhookStore.resolve_org()` must read across tenants to discover *which* tenant a webhook belongs to (the tenant is the unknown being resolved), which the multi-tenant RLS model (ENABLE + FORCE) otherwise default-denies. Unlike fabrik-lib's BYPASSRLS default, this role is confined by permissive policies to ONLY the three payments tables the store touches — SELECT on `customers`/`subscriptions` and INSERT+SELECT on `webhook_events` (the SELECT half is required for `record_event`'s `INSERT … RETURNING`). A leaked DSN therefore cannot reach the app's own core tenant tables — proven at provision time: the role is `NOBYPASSRLS` and any non-payments table is `permission denied`.

**Consuming-project wiring** (the project's job, NOT built by the registrar): connect ingest with `PAYMENTS_INGEST_DATABASE_URL` and assert the wiring at boot with `verify_service_role(conn, allow_policy_based=True)` (fabrik-lib `payments`); the fulfilment WORKER does NOT use this role — it receives the resolved `org_id` in its job payload and runs as the ordinary tenant role with `SET app.current_org`. If the project's own `jobs`/queue table is under RLS, the project's migration adds its own policy for `{db}_payments_ingest` on that project-owned table (the registrar scopes only the payments-module tables). Contract to be documented fleet-wide in the multi-tenant/payments rule pack (infra hand-off).

### Watchdog governance mount — `WATCHDOG_GOVERNANCE_MOUNT` (auto-set, do NOT set by hand)

At `fabrik apply`, the watchdog driver ships the project's governance set — `CLAUDE.md` + `AGENTS.md` + `.windsurf/rules/**` — from the hub's project tree to a dedicated per-project host dir on the VPS (`/var/lib/watchdog-governance/<id>/`, world-readable, refreshed every apply), bind-mounts it **read-only** into the sidecar at `/governance`, and sets `WATCHDOG_GOVERNANCE_MOUNT=/governance` in the sidecar env. fabrik-lib's `_materialize_conventions` reads that path (else falls back to `/project`) to make the watchdog's Tier-D fixes convention-conforming. This exists because the `/opt/<id>:/project:ro` mount is **hollow** — VPS deploy excludes gitignored `.windsurf/rules/`. **Hub-managed, never operator-set;** fail-soft (if the governance set is absent the mount + env are skipped, and materialize falls back to `/project`). Design: `docs/superpowers/specs/archived/2026-07-07-watchdog-governance-mount-design.md`.

### Watchdog Tier-D operator knobs — `WATCHDOG_REDEPLOY_TIMEOUT` / `WATCHDOG_TELEGRAM_OPERATOR_IDS` (operator-supplied, project `.env`)

Unlike the auto-injected vars above, these two are **operator-supplied** in the project `.env` (loaded by the sidecar via `env_file`; the hub does NOT mint them): `WATCHDOG_REDEPLOY_TIMEOUT` (seconds before a redeploy is considered timed-out) and `WATCHDOG_TELEGRAM_OPERATOR_IDS` (comma-separated Telegram chat IDs that gate the fail-closed approval channel). Fail-closed behaviors they drive (fabrik-lib `watchdog/`, commit `1226196`): the sidecar does **not** auto-deploy when the Telegram channel is unreachable, and only PROPOSE-phase incidents auto-apply on timeout. Full behavior in the `WATCHDOG` rule pack.

### Grounding canary — `CANARY_ROSTER_N`

- `CANARY_ROSTER_N` — how many models `scripts/sysadmin/canary_grounding.py` draws per
  grounding-class task type (`review`/`docs`/`plan`) via `pick_models` when building the weekly
  canary roster (deduped union; `anthropic/*` always excluded). Default `8`; hub-local tunable,
  read at batch start. See `docs/reference/canary-grounding.md`.

### Subagent flywheel — `SUBAGENT_RUNS_DSN` / `SUBAGENT_PROJECT` (hub-injected; do NOT hand-set the DSN)

The vendored `libs/subagents` pool scores every run to `fabrik_analytics.subagent_runs` via `record_agent_run`, which `pick_models(task_type)` learns from. The module autoloads both vars from `.env` (`_dotenv.py`, non-overriding — a real `export` or a deploy-injected value always wins):

- `SUBAGENT_RUNS_DSN` — an **INSERT-only** writer DSN for `fabrik_analytics.subagent_runs`. The hub mints the per-project role (`create_subagent_ins_role`) and injects the DSN at `fabrik apply` (VPS) — like `WATCHDOG_DB_URL_*`, generated + managed by the hub, never operator-set; on **WSL dev** it lives in `/opt/fabrik/.env`. **Unset ⇒ `record_agent_run` fail-opens** (no row, no crash) and the flywheel silently doesn't learn — `scripts/enforcement/check_subagent_flywheel.py` WARNs on the resulting unreceipted pool runs.
- `SUBAGENT_PROJECT` — the project tag written on each row (e.g. `fabrik-hub`), so runs are attributable per project.
<!-- FABRIK_SUBAGENT_REQUIRE_REACHABLE was introduced by plan-1 (2026-07-09) then reverted the same day when fabrik-lib source-of-truth ruled the fork wrong-layer. The canonical reachability seam is `pick_models(task_type, exclude=unreachable_ids)`; callers build the set from `agents.reachable_with_existing_keys=0` per `.windsurf/rules/ai/00-ai-model-selection.md`. No env var. -->



The writer role is INSERT-only (no SELECT) — read the table via the `postgres` superuser, never the writer DSN.

### Fleet Claude-account sync — `CLAUDE_FLEET_HOSTS` / `CLAUDE_FLEET_SSH_USER` (WSL operator utility)

`scripts/sysadmin/sync-claude-accounts-to-fleet.sh` runs on the operator's **WSL** box and pushes every local `~/.claude/manager-accounts/*/` snapshot + the active `~/.claude/.credentials.json` to each VPS, so a quota rotation on any host lands on a still-valid account (idle standby snapshots otherwise go stale — the failure that silently broke the fleet). Accounts are discovered by glob (a new `can-*` snapshot is picked up automatically once `claude-manager` captures it); the credential-rotation mechanism itself is `scripts/sysadmin/claude_rotate.py`.

- `CLAUDE_FLEET_HOSTS` — space-separated SSH host aliases to sync (default `vps vps2 vps3`). **Add a new VPS by extending this** — the script is N-host by design. Aliases resolve via `~/.ssh/config`.
- `CLAUDE_FLEET_SSH_USER` — the SSH user (default `ozgur`, non-root: creds live in `~ozgur/.claude`, and root SSH post-bootstrap trips fail2ban).
- `DRY_RUN=1` — print the `ssh`/`scp` commands without touching any host (used by `test_sync_accounts.py`).
- `CLAUDE_FLEET_SYNC_LOG` — log path (default `~/.cache/claude-fleet-sync.log`); logs host + account-dir names only, never token bytes.

Run manually or on a WSL cron (e.g. every 6h). ⚠️ **Standby-token validity** (does an idle-synced snapshot's refresh token still work when rotated in?) can only be confirmed live: after a first sync, on one host, rotate to a standby account and `claude -p ping` — if it 401s, shorten the cadence.

### Unified Claude entrypoint — `scripts/sysadmin/claude-run.sh` + `CLAUDE_OPERATOR_USER`

Every sysadmin script (VPS-side) invokes Claude through `scripts/sysadmin/claude-run.sh` rather than a bare `claude`. It is a drop-in for `claude` (`claude-run.sh <claude-args…>`) that (1) routes through `claude_rotate.py` so a usage/quota limit auto-rotates the active account, and (2) **always runs as the operator account** so every caller shares the one credential home `/home/ozgur/.claude`. This is required because the cron runs `proactive-check.sh` / `morning-report.sh` / `weekly-security.sh` / `monthly-backup-verify.sh` as **root**, whose `/root/.claude` has no credentials — the wrapper re-enters as the operator via `sudo -u <operator> -H` (root→operator sudo needs no password; `-H` sets `HOME`) when the caller isn't already the operator, and runs directly when it is.

- `CLAUDE_OPERATOR_USER` — the operator account the wrapper runs claude as (default `ozgur`). All callers therefore rotate one shared `~/.claude`.
- `CLAUDE_BIN` — override the resolved claude binary (default: `command -v claude`, then `/usr/local/bin/claude` → `~operator/.local/bin/claude` → `/usr/bin/claude`).
- The 3 pre-existing rotation callers (`bot.py`, `aro-wake/main.py`, `claude-keepalive-rotate.sh`) already run as ozgur through `claude_rotate` and are unchanged.

### Mutation testing — `FABRIK_MUTMUT` (dev; advisory, opt-in)

The Behavior Contract's substance-mechanical layer: `mutmut` (dev dependency, `pyproject.toml [dev]`) proves the tests **kill mutants**, not just cover lines. `scripts/enforcement/check_mutation.py` is registered in `final_gate` as **advisory** — but through the gate it **never actually mutates**: `final_gate.py` deliberately strips `FABRIK_MUTMUT` before invoking this one child (a set flag would start a session-detached mutmut that the gate's 120s outer timeout then orphans on the shared box) and restores it after, so a gate run always prints the pointer and exits 0 regardless of the flag. A REAL run happens only by **direct invocation** (`FABRIK_MUTMUT=1 python scripts/enforcement/check_mutation.py`) or the **Sunday 05:00 cron** (diff-scoped + weekly, never a per-PR blocking gate per `45-testing-strategy.md`); it mutates only **committed** changed Python (never the dirty worktree, never `tests/` or the vendored `libs/`), and **always exits 0**.

```bash
pip install -e '.[dev]'                                        # installs mutmut>=3.6.0
FABRIK_MUTMUT=1 python scripts/enforcement/check_mutation.py   # run on your changed code
mutmut browse                                                  # inspect surviving mutants
```

Surviving mutants = a change to the covered code that failed **no** test → strengthen the assertions (or mark an equivalent mutant).

### FABRIK_MUTMUT / FABRIK_MUTMUT_SINCE / FABRIK_MUTMUT_WALL_CAP_S — mutation-testing controls

**What:** `FABRIK_MUTMUT=1` opts the advisory mutation runner
(`scripts/enforcement/check_mutation.py`) into an actual mutmut run **when invoked directly or by
the cron** (the gate-strip mechanics are in the section above — not restated here).
`FABRIK_MUTMUT_SINCE` (e.g. `"7 days ago"`) switches the diff
scope from the merge-base window to committed history since that time — the weekly cron sets it.
`FABRIK_MUTMUT_WALL_CAP_S` (default `1200`) hard-caps the mutmut run's wall clock; on cap the
runner reports partial results and still exits 0.

**Why needed:** mutation runs are slow and noisy — the advisory stays opt-in and bounded so the
weekly signal can never block or starve the box. Wired invoker: the Sunday 05:00 cron (see
crontab), ahead of Monday's fleet doc audit.

---

## Architecture Context

### Database Strategy

**Single shared PostgreSQL instance:**
- `postgres-main` container serves all projects
- Each project gets its own database
- Connection string format: `postgresql://user:pass@postgres-main:5432/dbname` <!-- noqa: doc example, not a real cred -->

**Why:** Resource efficiency, easier backups, consistent version.

### DNS Provider Choice

**Development:** Use DNS Manager service (no local credentials needed)

**Production options:**
1. **Cloudflare driver** (current) - Direct Cloudflare API via `src/fabrik/drivers/cloudflare.py`; fast propagation, free tier
2. ~~**DNS Manager service**~~ — **RETIRED** (not deployed; `dns.vps1.ocoron.com` returns NXDOMAIN)

**Migration path:** Set `CLOUDFLARE_*` vars, Fabrik auto-switches.

### Logging Architecture

**Two modes:**
- `LOG_FORMAT=json` → Structured logs for log aggregation (Loki, CloudWatch)
- `LOG_FORMAT=text` → Human-readable for development

**Log levels:**
- `DEBUG` → Development only (verbose, includes SQL queries)
- `INFO` → Production default (business events)
- `WARNING` → Potential issues
- `ERROR` → Failures requiring attention

---

## Environment-Specific Setups

### Development (WSL)

```bash
# .env
VPS_HOST=localhost
DATABASE_URL=postgresql://fabrik:dev@localhost:5432/fabrik_dev  # noqa: doc example, local dev placeholder
LOG_LEVEL=DEBUG
LOG_FORMAT=text
```

**Why:** Local services, verbose logging, human-readable output.

### Production (VPS)

```bash
# .env
VPS_HOST=172.93.160.197
VPS_IP=172.93.160.197
DATABASE_URL=postgresql://fabrik:${SECURE_PASSWORD}@postgres-main:5432/fabrik  # noqa: env-var interpolation, not a hardcoded cred
LOG_LEVEL=INFO
LOG_FORMAT=json
# Backups: Backrest manages credentials internally; no env var required (replaced Duplicati 2026-04-17)
```

**Why:** Real IPs, secure passwords, structured logs, encrypted backups.

---

## Configuration Files

### `.env` vs `.env.example`

| File | Purpose | Git |
|------|---------|-----|
| `.env.example` | Self-documenting template with all vars, defaults, and inline help | ✅ Committed |
| `.env` | Your actual credentials and config | ❌ Gitignored |

**Pattern:** `.env.example` has comprehensive comments. Copy and fill in values.

### Project-Specific `.env` Files

**For deployment secrets, Fabrik uses project-specific `.env` files.**

Each project has its own `.env` file at `/opt/{project}/.env` for deployment secrets:

```bash
# /opt/my-api/.env (project-specific)
API_KEY=your_api_key
DATABASE_PASSWORD=your_password
SECRET_TOKEN=your_secret_token
```

**How Fabrik loads secrets:**

1. **Scaffold auto-detection:** `fabrik scaffold` reads `.env.example` and auto-detects secret env vars (matching patterns like `_KEY`, `_SECRET`, `_PASSWORD`, `_TOKEN`, `_CREDENTIALS`). These are added to the spec's `from_env` field.

2. **Automatic loading:** `fabrik apply` automatically reads from the project's `.env` file before checking system environment variables.

3. **Precedence:** Command-line `-s` flags (highest) → Project `.env` file → Environment variables (lowest).

**Benefits:**
- No manual environment variable setting needed
- Secrets are isolated per project
- Works seamlessly across WSL dev and VPS Docker environments
- Easy to override with `-s` flags when needed

### `config/platform.yaml`

**Purpose:** Non-secret platform configuration.

**When to use:**
- Cross-environment settings (backup schedule)
- Feature flags
- Service discovery rules

**When NOT to use:**
- Secrets → Always in `.env`
- Per-deployment config → `specs/*.yaml`

### `FABRIK_LOCK_DIR` (T2-01)

Directory where `fabrik.locks_local.file_lock()` creates lock files. Used to
serialize WSL-side Python orchestration — for example, `fabrik reconcile-all`
walking specs and `state.save()` writing `.fabrik/state/<id>.json` under
contention.

- **Default:** `/tmp/fabrik-locks`
- **When to override:** if `/tmp` is on a filesystem without flock support
  (rare on modern WSL2; possible on some containers/CI), point at a path
  on the same filesystem as `FABRIK_ROOT`.

Distinct from the registrar-side VPS lock (`fabrik.drivers.locks.run_locked`),
which operates over SSH on the VPS and lives in `/tmp/fabrik-<resource>.lock`
on the remote host. The two never interact.

### Scheduled audits — WSL cron (T2-03)

`scripts/audit_authelia_gates.py` runs every Monday 06:00 local via WSL `cron`, verifying every admin-dashboard's Traefik router still has the `authelia-forward@docker` middleware attached (the policy-vs-enforcement drift class from Lesson 32 / GlitchTip 2026-04-18 incident).

The cron entry was installed on 2026-05-15 by T2-03 G-G4:

```cron
0 6 * * 1 PYTHONPATH=/opt/fabrik/src /opt/fabrik/.venv/bin/python /opt/fabrik/scripts/audit_authelia_gates.py >> /var/log/fabrik-audit.log 2>&1
```

Log file lives at `/var/log/fabrik-audit.log` (writable by `ozgur:ozgur`; `sudo touch + chown` if it disappears). Each run appends a single block ending in `SUMMARY: N OK, M GAP, K MISSING`.

**Verifying:**

```bash
crontab -l | grep audit_authelia_gates
sudo tail -20 /var/log/fabrik-audit.log
# Manual run on demand:
PYTHONPATH=/opt/fabrik/src /opt/fabrik/.venv/bin/python /opt/fabrik/scripts/audit_authelia_gates.py
```

**Removing:** `crontab -e` and delete the line. The script itself stays in place for ad-hoc runs.

WSL cron quirk: ensure `systemctl is-active cron` returns `active` after a WSL restart. Some fresh WSL installs don't autostart cron; if cron is `inactive` after reboot, run `sudo service cron start` and consider enabling on boot via `sudo systemctl enable cron`.

### Preplan workflow (T3-01)

Stage 1 of the Fabrik lifecycle captures project intent in `docs/preplans/<YYYY-MM-DD>-<slug>.md` BEFORE `fabrik scaffold` runs. The 9-section template (rendered by `fabrik preplan new <slug>` from `templates/preplan/preplan.md.j2`) covers Idea / Project type / Shape preview / External deps / Domain / Success criteria / Out of scope / Open questions / Notes (VPS1 inventory reminders — embedded so agents reading the preplan stay grounded in `postgres-main:5432`, `redis-main:6379`, `X-Internal-Token`, `/health` bypass, `/metrics`, GlitchTip DSN).

`fabrik scaffold <name> --from-preplan <path>` then:

- Pre-fills `--type` and description from the preplan
- Copies the markdown into `<project>/docs/preplan.md`
- Appends a `Preplan:` reference line to ALL 4 AI guardrail files (`AGENTS.md`, `CLAUDE.md`, `AGENTS-compact.md`, `.windsurfrules`) so every downstream agent reads the same intent

No new env vars. The workflow is documented in `docs/preplans/README.md` and Traycer ingests it via Step 2.5 of `docs/traycer/fabrik-workflow.md`.

<!--
`coolify.alias` spec field section — OBSOLETE 2026-06-02.

The Coolify Application UUID-suffix container renaming this section worked
around no longer happens — Coolify was fully removed from vps1 on 2026-05-30.
All containers now have stable names via compose `container_name:` fields
(Lesson 22). The `coolify-alias-watcher.service` was decommissioned with
Coolify. Code references to `coolify.alias` / `coolify_alias.add_alias()`
remain in archived legacy modules (`src/fabrik/orchestrator/coolify_alias.py`)
but are no longer called from any active code path.
-->

---

## Troubleshooting

### "Permission denied" on VPS

**Cause:** SSH key not set up or wrong user.

**Fix:**
```bash
ssh-copy-id deploy@your-vps
# Or use password temporarily:
VPS_SSH_KEY=  # Remove from .env
```

<!--
"Coolify API 401" troubleshooting section — REMOVED 2026-06-02.

Coolify is fully removed from vps1 (2026-05-30). The legacy CLI commands
that used to call the Coolify API (`fabrik status`, `fabrik logs`,
`fabrik reconcile-all`) are non-functional and listed under "Known broken"
in the archived SSH-deployer plan. New troubleshooting starts from
`docs/operations/deployment.md` (`fabrik apply` / SSH + Docker Compose).
-->

### Database connection refused

**Check:**
```bash
# Is postgres running?
docker ps | grep postgres-main

# Can you connect manually?
psql $DATABASE_URL

# Check from app container:
docker exec -it myapp psql $DATABASE_URL
```

### ~~DNS Manager service 404~~ (RETIRED — historical)

> **⚠️ RETIRED — not deployed.** The dns-manager service was retired; `dns.vps1.ocoron.com` now returns NXDOMAIN (not a 404). DNS is handled directly via the Cloudflare driver (`src/fabrik/drivers/cloudflare.py`) — set `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ZONE_ID`. The troubleshooting below is kept for historical reference only.

**Cause:** Service not deployed or wrong URL.

**Fix:**
```bash
# Check service health
curl https://dns.vps1.ocoron.com/health

# Fallback: Direct Namecheap API (used internally by dns-manager)
# These are configured in dns-manager's .env, not in application code
# NAMECHEAP_API_USER=youruser
# NAMECHEAP_API_KEY=yourkey
```

---

## Security Best Practices

### Password Generation

**DO:**
```bash
# 32+ characters, random
python -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32)))"
```

**DON'T:**
- `password123`
- Dictionary words
- Reuse across services

### Credential Storage

1. **Development:** `.env` file (gitignored)
2. **Production:** Environment variables in `/opt/<project>/.env` on the VPS, written and merged by `fabrik apply` (SSH + Docker Compose)
3. **Backup:** `/opt/fabrik/.env` (master copy)

### Rotation Schedule

- API tokens: Every 90 days
- Database passwords: Every 180 days
- Encryption passphrases: Never (backups become unrecoverable)

---

## Migration Guides

### Adding a New Service

1. Add env vars to `.env.example` with comments
2. Document credential acquisition in this guide
3. Update config verification in `fabrik.config`

### Changing DNS Provider

**Switch to Cloudflare:**
```bash
# 1. Get Cloudflare credentials
# 2. Add to .env:
CLOUDFLARE_API_TOKEN=xxx
CLOUDFLARE_ZONE_ID=xxx

# 3. Fabrik auto-detects and switches
```

**Rollback:** Remove `CLOUDFLARE_*` vars, falls back to default provider.

---

## Configuration Checklist

Before deploying:

- [ ] `.env` created from `.env.example`
- [ ] All required credentials obtained (VPS, Cloudflare, B2)
- [ ] SSH access verified: `ssh deploy@$VPS_HOST`
- [ ] Database accessible: `psql $DATABASE_URL`
- [ ] Backups configured: Backrest configured at `backup.vps1.ocoron.com` (Backblaze B2 remote)
- [ ] Verification passed: `python -c "from fabrik.config import Config; Config()"` (no `--verify` CLI exists; this raises `ValueError` if a required var is missing)
- [ ] Master backup exists: `/opt/fabrik/.env` synced

---

## Environment Variable Best Practices

### 1. Never Hardcode Values

```python
# ❌ WRONG - breaks in Docker/VPS
DB_HOST = "localhost"
API_KEY = "sk-abc123"  # noqa: anti-pattern doc example

# ✅ CORRECT - works everywhere
DB_HOST = os.getenv('DB_HOST', 'localhost')
API_KEY = os.getenv('API_KEY')
if not API_KEY:
    raise ValueError("API_KEY environment variable is required")
```

### 2. Load Configuration at Runtime

```python
# ❌ WRONG - env vars not set at import time
class Config:
    DB_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/db"  # noqa: env-var interpolation, doc example
    # This evaluates immediately when class is defined!

# ✅ CORRECT - load in function/property
def get_db_url() -> str:
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    host = os.getenv('DB_HOST', 'localhost')
    return f"postgresql://{user}:{password}@{host}/db"  # noqa: param interpolation, doc example

# OR use Pydantic Settings
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_user: str
    db_password: str
    db_host: str = "localhost"

settings = Settings()  # Loads from env at instantiation
```

### 3. Store Credentials in Two Places

**Always maintain backups:**

1. **Project `.env`** - For local development use
2. **`/opt/fabrik/.env`** - Master backup (survives project deletion)

```bash
# After creating project .env, backup to master
cp /opt/my-project/.env /opt/fabrik/.env.my-project.backup
```

### 4. Document in .env.example

```bash
# .env.example (COMMIT THIS to git)
# Never commit actual .env file!

# Database Configuration
DB_HOST=localhost                    # Database host (localhost for dev, postgres-main for Docker)
DB_PORT=5432                         # PostgreSQL port
DB_NAME=myapp_dev                    # Database name
DB_USER=postgres                     # Database username
DB_PASSWORD=                         # SET IN .env - never commit actual password

# AI/LLM: no direct API key. Operational AI uses Claude Code OAuth; content/LLM
# calls use OpenRouter (watchdog reads WATCHDOG_OPENROUTER_KEY in its own env).
```

### 5. Environment-Specific Defaults

**WSL (Development):**
```python
DB_HOST = os.getenv('DB_HOST', 'localhost')  # Local PostgreSQL
DB_PORT = int(os.getenv('DB_PORT', '5432'))
```

**VPS Docker (Production):**
```yaml
# compose.yaml
environment:
  - DB_HOST=postgres-main  # Container name, not localhost
  - DB_PORT=5432
```

**Supabase (retired as the default — deliberate ADR-recorded exception only, see `agents-fabrik.md` § Supabase):**
```python
# Use full connection string
DATABASE_URL = os.getenv('DATABASE_URL')  # Supabase provides this, for the exception path only
```

### 6. Validation Patterns

```python
import os
from typing import Optional

def get_required_env(key: str) -> str:
    """Get required environment variable or raise error."""
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Required environment variable {key} is not set")
    return value

def get_optional_env(key: str, default: str) -> str:
    """Get optional environment variable with default."""
    return os.getenv(key, default)

# Usage
API_KEY = get_required_env('API_KEY')  # Must be set
LOG_LEVEL = get_optional_env('LOG_LEVEL', 'INFO')  # Defaults to INFO
```

### 7. Type Conversion

```python
import os
from typing import List

# Boolean
DEBUG = os.getenv('DEBUG', 'false').lower() in ('true', '1', 'yes')

# Integer
PORT = int(os.getenv('PORT', '8000'))
MAX_WORKERS = int(os.getenv('MAX_WORKERS', '4'))

# Float
TIMEOUT = float(os.getenv('TIMEOUT', '30.0'))

# List (comma-separated)
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost').split(',')
# ALLOWED_HOSTS=localhost,example.com → ['localhost', 'example.com']
```

---

## n8n Webhook Notifications

Fabrik fires fire-and-forget webhooks after deploy events; a content-publish webhook function exists but is not currently wired to a caller.

**How it works:**
1. `src/fabrik/deploy_router.py` calls `notify_deploy()` (defined in `src/fabrik/notifications.py`) after every `fabrik apply`
2. `notify_content()` is also defined in `src/fabrik/notifications.py` (fires `N8N_WEBHOOK_CONTENT`) but has no call site in this repo — there is no `content_publisher.py` and no `fabrik content publish` command wired to it
3. n8n receives the POST, formats the message, POSTs to Apprise
4. Apprise fans out to configured channels (Telegram, email, etc.)

**Required env vars** (all optional — notifications silently skipped if absent):

```bash
N8N_WEBHOOK_DEPLOY=https://auto.vps1.ocoron.com/webhook/deploy-notify
N8N_WEBHOOK_CONTENT=https://auto.vps1.ocoron.com/webhook/content-notify
N8N_WEBHOOK_TIMEOUT=5   # seconds
APPRISE_STATELESS_URLS=tgram://BOTTOKEN/CHATID  # set in /opt/apprise/.env
```

**Setup sequence:**
1. Visit `https://auto.vps1.ocoron.com` → create owner account
2. Import workflows from `specs/n8n-workflows/` (Settings → Workflows → Import)
3. Activate each workflow → copy the Production webhook URL
4. Paste URL into `N8N_WEBHOOK_DEPLOY` / `N8N_WEBHOOK_CONTENT` in `.env`
5. Set `APPRISE_STATELESS_URLS` in `/opt/apprise/.env` on VPS, restart Apprise

**Apprise URL formats:**
- Telegram: `tgram://BOTTOKEN/CHATID`
- Email (Resend SMTP): `mailtos://resend:RESEND_API_KEY@smtp.resend.com?to=you@email.com`
- Multiple: comma-separated

**n8n workflows** (`specs/n8n-workflows/`):

| File | Event | Nodes |
|------|-------|-------|
| `01-deploy-notify.json` | `deploy.success` / `deploy.failure` from Fabrik | Webhook → Code → Apprise |
| `02-content-notify.json` | `content.published` from Fabrik | Webhook → Code → Apprise |
| `03-health-alert.json` | Gatus DOWN/UP | Webhook → Code → Apprise |
| `04-content-trigger.json` | Schedule every 6h | Schedule → HTTP → Apprise |

---

## External Services Registry (host-side tooling)

- `SERVICES_REGISTRY_DSN` — Postgres DSN for the local external-services registry
  (`services`/`api_keys`/`credit_snapshots`/`subscriptions`). Default
  `postgresql:///fabrik_services` (passwordless unix-socket peer auth). This is host-side
  operator tooling, **not** a deployed container — `localhost`/socket is correct here, not
  `postgres-main`. One-time provisioning: `sudo -u postgres createdb -O <user> fabrik_services`,
  then `psql "$SERVICES_REGISTRY_DSN" -f db/services_registry_schema.sql`.

## Alert delivery (`libs/alerting`)

Every alert this box raises — quota-drain warnings, keepalive failures, CI health,
watchdog incidents, the fabrik-mail digest — routes through `libs/alerting`. It tries
SSH → VPS Apprise first, then the direct Telegram Bot API, then logs a per-method
post-mortem naming which method failed and why.

**Prove the path end to end** (an operator or a cron can run this):

```bash
python -m alerting --selftest            # delivers a real message; exit 1 if none worked
python -m alerting --selftest --dry-run  # configuration only, sends nothing
```

| Variable | Purpose |
|---|---|
| `TELEGRAM_FULL_BOT_TOKEN` | The **complete** bot token, `<bot_id>:<secret>`. Preferred. |
| `TELEGRAM_BOT_ID` | Numeric bot id; composed with `TELEGRAM_BOT_TOKEN` when no full token is set. |
| `TELEGRAM_BOT_TOKEN` | The **secret half** of the token (or a complete colon-shaped token). |
| `TELEGRAM_CHAT_ID` | Target chat/user id. |
| `ALERT_VPS_HOST` | SSH alias for the Apprise hop (default `vps`). |
| `ALERT_APPRISE_URL` | Apprise URL as seen *from the VPS* (default `http://apprise:8000`). |
| `ALERT_ENABLED` | `0` disables; `1` forces on; unset auto-enables when any delivery var is set. |
| `ALERT_MIN_INTERVAL` | Dedup window in seconds per alert title (default `300`). |
| `FABRIK_MAIL_ROOT` | Root of the durable mail store (default `/opt/fabrik-mail`). Every mailbox lives at `<root>/<repo>/{inbox,archive,malformed}`; the test suite points this at a temp dir. |
| `FABRIK_OPT_ROOT` | Base used to validate that a recipient repo actually exists on the box (default `/opt`). A recipient with no directory under it is refused. |
| `FABRIK_MAIL_ESCALATE_DAYS` | escalation-digest age threshold in days (default `3`; a non-numeric or below-minimum value warns and uses the default). ⚠️ Read by the CRON LINE's env prefix, never from `.env` — cron sources no dotenv and the alerting loader's allowlist excludes it (`docs/workstation/fabrik-mail.md` § Escalation). |
| `FABRIK_MAIL_HOP_CAP` | fabrik-mail auto-reply hop budget — HOLD when `parent.hops >=` this (default `3`; `0` = refuse all auto-replies; a negative or non-numeric value warns and uses the default). |
| `FABRIK_MAIL_RATE_CAP` | fabrik-mail per-sender rate cap within the window (default `5`; `0` = refuse all; a negative or non-numeric value warns and uses the default). |
| `FABRIK_MAIL_RATE_WINDOW_S` | fabrik-mail rate window, seconds (default `3600`; a value below `1` warns and uses the default — a `0` window would disable the breaker). |

⚠️ **The Telegram credential is split.** A usable token is `<bot_id>:<secret>`, but
`/opt/fabrik/.env` has historically stored only the secret half in `TELEGRAM_BOT_TOKEN`.
Posting to `/bot<secret>/sendMessage` returns HTTP **404 Not Found**, which reads like a
dead endpoint rather than a malformed credential — that is exactly how alert delivery
stayed broken unnoticed (2026-08-16 liveness audit). Set `TELEGRAM_FULL_BOT_TOKEN`, or
supply `TELEGRAM_BOT_ID` so the halves can be composed.

## See Also

- [.env.example](../.env.example) - Complete list of all environment variables
- [SERVICES.md](SERVICES.md) - External services catalog
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common configuration issues
