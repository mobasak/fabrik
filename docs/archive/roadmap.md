# Complete Fabrik Roadmap (historical — superseded planning artifact)

> **⚠️ Historical / superseded — archive candidate (re-verified 2026-06-16).**
> This is the **original 8-phase build plan** from the pre-2026-05 era when
> Coolify was the deploy control plane. It is kept as a historical record of
> the planned sequence; it is **not** a live roadmap and should not be used
> to gauge current status.
>
> **What actually happened since this was written:** 7 of the 8 phases below
> are substantially **shipped**, and the foundation premise (Coolify as the
> deploy engine, "start at Phase 1 Step 1") was **superseded** by the
> SSH + Docker Compose migration. Coolify was **decommissioned 2026-05-30**;
> deploys now run via `fabrik apply` (SSH + Docker Compose to the VPS fleet),
> and `coolify` survives only as a legacy Docker **network name**. The
> Coolify-install + Coolify-driver line items remain accurate *as history*
> but are not the current path. The current system also extends well beyond
> this plan — a 3-VPS fleet + on-demand Vultr, `--target-vps` multi-host
> deploys, `fabrik vultr` provisioning + DR drills (hub / spoke /
> spoke-restore, validated end-to-end 2026-06-15/16), and an AI sysadmin
> trio live on the whole fleet — none of which this 2025-era plan anticipated.
>
> **Per-phase status is annotated inline below.** For the current picture see
> [docs/operations/fabrik-lifecycle.md](../operations/fabrik-lifecycle.md)
> (4-stage lifecycle), [docs/DEPLOYMENT_ARCHITECTURE.md](../DEPLOYMENT_ARCHITECTURE.md),
> and [docs/reference/fabrik-vultr.md](../reference/fabrik-vultr.md) (provisioning + DR drills).

## Phase 1: Foundation — ✅ SHIPPED (then migrated off Coolify)

> **Status:** Done. The full chain (`fabrik plan`/`apply`, spec loader, DNS,
> template renderer, first Python + WordPress deploys, Gatus, backup/restore)
> shipped. The Coolify-specific steps (6–9, 15) were completed and then
> **superseded** — the control plane is now SSH + Docker Compose
> (`src/fabrik/orchestrator/deployer_ssh.py`), not the Coolify driver/UI.
> DNS is multi-provider (`drivers/dns.py`, `drivers/cloudflare.py`).

**Goal:** One working deployment engine that proves the full chain.

| Step | Task | Time |
|------|------|------|
| **VPS Hardening** |
| 1 | SSH hardening (keys only, no root, AllowUsers) | 15 min |
| 2 | UFW (22, 80, 443 only) | 10 min |
| 3 | Fail2ban | 10 min |
| 4 | Unattended upgrades | 5 min |
| 5 | Docker log rotation | 5 min |
| **Coolify Setup** |
| 6 | Install Coolify | 30 min |
| 7 | Secure Coolify (password, HTTPS) | 15 min |
| 8 | Deploy postgres-main via UI | 10 min |
| 9 | Deploy redis-main via UI | 10 min |
| 10 | Configure postgres backup to B2 | 15 min |
| **Fabrik Core** |
| 11 | Create folder structure | 15 min |
| 12 | Set up secrets (platform.env) | 15 min |
| 13 | Implement spec_loader.py | 1 hr |
| 14 | Implement dns_namecheap.py (export→diff→apply) | 2 hrs |
| 15 | Implement coolify.py driver | 2 hrs |
| 16 | Implement template_renderer.py | 1 hr |
| 17 | Implement `fabrik new` | 30 min |
| 18 | Implement `fabrik plan` | 1 hr |
| 19 | Implement `fabrik apply` | 1 hr |
| **First Deployment** |
| 20 | Create app-python template | 1 hr |
| 21 | Deploy hello-api end-to-end | 1 hr |
| **WordPress** |
| 22 | Create wp-site template | 2 hrs |
| 23 | Implement WP post-deploy hooks | 1 hr |
| 24 | Deploy test WordPress site | 1 hr |
| **Monitoring** |
| 25 | Deploy Gatus | 30 min |
| 26 | Configure checks + alerts | 30 min |
| **Validation** |
| 27 | Test backup + restore | 1 hr |

**Time:** ~20 hours (3-4 days)

**Deliverable:** Can run `fabrik apply` to deploy Python APIs and WordPress sites with HTTPS, backups, and monitoring.

---

### Phase 2: WordPress Automation — ✅ SHIPPED

> **Status:** Done, then split out. WordPress scaffolding/presets still ship
> in Fabrik (`fabrik scaffold --type wordpress`), but WP *deployment* +
> WP-CLI/REST lifecycle automation have **moved to a separate `wpf` CLI**
> (`/opt/wpf/`); `fabrik` now points WordPress users there. WP site creation
> is out of Fabrik scope.

**Goal:** Full WordPress lifecycle management via CLI/API.

| Step | Task | Time |
|------|------|------|
| **WordPress Driver** |
| 1 | Implement WP-CLI wrapper (execute in container) | 2 hrs |
| 2 | Implement WP REST API client | 2 hrs |
| 3 | Create application password on deploy | 30 min |
| **Theme Management** |
| 4 | Install themes from WP repo | 1 hr |
| 5 | Install themes from ZIP | 1 hr |
| 6 | Activate and configure themes | 1 hr |
| **Plugin Management** |
| 7 | Install plugins from WP repo | 1 hr |
| 8 | Install plugins from ZIP | 1 hr |
| 9 | Configure plugin settings via WP-CLI | 2 hrs |
| 10 | Handle "manual activation required" plugins | 1 hr |
| **Content Operations** |
| 11 | Create/update pages | 1 hr |
| 12 | Create/update posts | 1 hr |
| 13 | Upload media | 1 hr |
| 14 | Create menus | 1 hr |
| 15 | Create contact forms (CF7) | 1 hr |
| **CLI Extensions** |
| 16 | `fabrik wp:plugin` commands | 1 hr |
| 17 | `fabrik wp:theme` commands | 1 hr |
| 18 | `fabrik wp:content` commands | 1 hr |

**Time:** ~20 hours (3-4 days)

**Deliverable:** Can install themes, plugins, and create content without wp-admin login.

---

### Phase 3: AI Content Integration — ✅ SHIPPED

> **Status:** Done. `fabrik ai generate` ships (`src/fabrik/ai/client.py`),
> and agent-driven workflows are live (Windsurf/Kilo/Traycer rule packs +
> AGENTS.md). Note the operational AI stack (sysadmin/watchdog) standardized
> on **Claude Code CLI** (subscription OAuth); the `ANTHROPIC_API_KEY` path is
> only for `fabrik ai generate` content utilities.

**Goal:** AI agents can generate and publish content.

| Step | Task | Time |
|------|------|------|
| **Content Generation** |
| 1 | LLM client wrapper (Claude/OpenAI) | 2 hrs |
| 2 | Page generation from prompts | 2 hrs |
| 3 | Post generation from prompts | 2 hrs |
| 4 | SEO meta generation | 1 hr |
| **Content Revision** |
| 5 | Fetch existing content | 1 hr |
| 6 | Revise based on instructions | 2 hrs |
| 7 | Diff and update | 1 hr |
| **Bulk Operations** |
| 8 | Generate service pages from list | 2 hrs |
| 9 | Generate FAQ pages | 1 hr |
| 10 | Generate blog post series | 2 hrs |
| **CLI Extensions** |
| 11 | `fabrik ai:generate` commands | 2 hrs |
| 12 | `fabrik ai:revise` commands | 2 hrs |
| **Agent Integration** |
| 13 | Windsurf agent context/rules | 2 hrs |
| 14 | Test agent-driven deployments | 2 hrs |

**Time:** ~24 hours (4-5 days)

**Deliverable:** Windsurf agents can create sites, generate content, and make revisions without human intervention.

---

### Phase 4: DNS Migration + Advanced Networking — ✅ SHIPPED (Cloudflare driver)

> **Status:** Done. The Cloudflare driver ships (`src/fabrik/drivers/cloudflare.py`)
> with per-record CRUD (no destructive replace-all) alongside Namecheap via
> the unified `drivers/dns.py` client; the live fleet runs on Cloudflare
> (proxy/A-record management is in use). Optional WAF/page-rules (steps 8–9)
> were not pursued as separate line items.

**Goal:** Cleaner DNS automation, optional Cloudflare benefits.

| Step | Task | Time |
|------|------|------|
| **Cloudflare Driver** |
| 1 | Implement dns_cloudflare.py | 2 hrs |
| 2 | Per-record CRUD (no replace-all) | 1 hr |
| 3 | Test alongside Namecheap | 1 hr |
| **Migration Path** |
| 4 | Document Namecheap → Cloudflare migration | 1 hr |
| 5 | Migrate one domain as test | 1 hr |
| 6 | Update specs to use Cloudflare | 30 min |
| **Optional Cloudflare Features** |
| 7 | Enable proxy (CDN) for static assets | 1 hr |
| 8 | Basic WAF rules | 1 hr |
| 9 | Page rules for caching | 1 hr |

**Time:** ~10 hours (1-2 days)

**Deliverable:** Can use either Namecheap or Cloudflare. Optional CDN/WAF for client sites.

---

### Phase 5: Staging + Multi-Environment — ⬜ NOT SHIPPED (only phase still open)

> **Status:** Not built. No `fabrik staging:*` commands exist. The "same code
> in 3 envs" portability invariant (WSL dev / VPS Docker / Supabase) covers
> the multi-environment need in practice, so dedicated staging tooling was
> never prioritized. This is the one phase from the original plan that
> remains genuinely unbuilt.

**Goal:** Test changes before production.

| Step | Task | Time |
|------|------|------|
| **Staging Support** |
| 1 | Add `environment` field to spec | 1 hr |
| 2 | Staging subdomain convention (staging.domain.com) | 1 hr |
| 3 | Clone production to staging | 2 hrs |
| 4 | Sync staging → production | 2 hrs |
| **Database Cloning** |
| 5 | pg_dump production → staging | 1 hr |
| 6 | Anonymize sensitive data option | 2 hrs |
| **CLI Extensions** |
| 7 | `fabrik staging:create` | 1 hr |
| 8 | `fabrik staging:sync` | 1 hr |
| 9 | `fabrik staging:promote` | 1 hr |

**Time:** ~13 hours (2-3 days)

**Deliverable:** Can create staging environments, test changes, and promote to production.

---

### Phase 6: Advanced Monitoring — ✅ SHIPPED

> **Status:** Done. The observability stack is live on the fleet — Prometheus
> (`drivers/prometheus.py`, ~13 jobs), Grafana (`drivers/grafana.py`),
> Loki, and Gatus (`drivers/gatus.py`, ~33 endpoints). Alerting runs through
> 13 alert rules + Telegram. Auto-registered per service via the spec `shape:`
> contract on `fabrik apply`.

**Goal:** Visibility into performance and issues.

| Step | Task | Time |
|------|------|------|
| **Log Aggregation** |
| 1 | Deploy Loki | 1 hr |
| 2 | Configure Docker log driver for Loki | 1 hr |
| 3 | Query logs via CLI | 1 hr |
| **Metrics** |
| 4 | Deploy Prometheus | 1 hr |
| 5 | Configure container metrics | 1 hr |
| 6 | Configure Postgres metrics | 1 hr |
| **Visualization** |
| 7 | Deploy Grafana | 1 hr |
| 8 | Create system dashboard | 2 hrs |
| 9 | Create per-app dashboards | 2 hrs |
| **Alerting** |
| 10 | Configure Grafana alerts | 1 hr |
| 11 | Slack/email integration | 1 hr |

**Time:** ~14 hours (2-3 days)

**Deliverable:** Full observability stack with dashboards and alerting.

---

### Phase 7: Multi-Server Scaling — ✅ SHIPPED (via `--target-vps`, not Coolify)

> **Status:** Done, by a different mechanism than planned. Multi-host is live
> via the `--target-vps` flag on `apply`/`redeploy`/`destroy`
> (resolution: CLI flag > state `target_vps` > spec `target_vps:` > vps1),
> not by "adding a server to Coolify" (step 3 below is obsolete — Coolify is
> decommissioned). The fleet is **3 VPS + on-demand Vultr** spokes provisioned
> by `fabrik vultr` (`src/fabrik/orchestrator/vultr_provision.py`). Servers are
> targeted per-spec; the shared DB layer (`postgres-main`/`redis-main`) is in place.

**Goal:** Add capacity without architectural changes.

| Step | Task | Time |
|------|------|------|
| **Second VPS** |
| 1 | Provision second VPS | 30 min |
| 2 | Harden (same as first) | 45 min |
| 3 | ~~Add to Coolify as server~~ → register host + deploy with `--target-vps` (Coolify decommissioned) | 30 min |
| **Load Distribution** |
| 4 | Add `server` field to spec | 1 hr |
| 5 | Update Fabrik to target specific servers | 2 hrs |
| 6 | Document server selection rules | 1 hr |
| **Shared Database Access** |
| 7 | Configure Postgres for remote connections | 1 hr |
| 8 | Secure with firewall rules | 1 hr |
| 9 | Connection pooling (PgBouncer) | 2 hrs |

**Time:** ~11 hours (2 days)

**Deliverable:** Can deploy to multiple servers, shared database layer.

---

### Phase 8: Business Automation (n8n) — ✅ SHIPPED

> **Status:** Done. n8n is deployed (`specs/infrastructure/n8n.yaml`) with
> persistence, and workflows ship in `specs/n8n-workflows/` (deploy-notify,
> content-notify, health-alert, content-trigger). Auth is via Authelia SSO
> (n8n v1.0+ removed basic auth). See `docs/operations/n8n-webhooks.md`.

**Goal:** Visual workflow automation when complexity justifies it.

| Step | Task | Time |
|------|------|------|
| **n8n Deployment** |
| 1 | Create n8n spec/template | 1 hr |
| 2 | Deploy via Fabrik | 30 min |
| 3 | Configure persistence | 30 min |
| **Initial Workflows** |
| 4 | Lead capture → CRM/email | 2 hrs |
| 5 | Form submission → notification | 1 hr |
| 6 | Scheduled reports | 2 hrs |
| **Integration** |
| 7 | n8n → Fabrik API triggers | 2 hrs |
| 8 | Webhook receivers | 1 hr |

**Time:** ~10 hours (2 days)

**Deliverable:** Visual workflow automation for business processes.

---

## Summary: All Phases

| Phase | Focus | Time | Cumulative | Status (2026-06-16) |
| ----- | ----- | ---- | ---------- | ------------------- |
| 1 | Foundation (Fabrik core + first deploys; **migrated off Coolify** → SSH+Compose) | 20 hrs | 20 hrs | ✅ shipped |
| 2 | WordPress automation (now in separate `wpf` CLI) | 20 hrs | 40 hrs | ✅ shipped (split out) |
| 3 | AI content integration | 24 hrs | 64 hrs | ✅ shipped |
| 4 | DNS migration + Cloudflare | 10 hrs | 74 hrs | ✅ shipped |
| 5 | Staging + multi-environment | 13 hrs | 87 hrs | ⬜ not shipped |
| 6 | Advanced monitoring | 14 hrs | 101 hrs | ✅ shipped |
| 7 | Multi-server scaling (via `--target-vps` + Vultr) | 11 hrs | 112 hrs | ✅ shipped |
| 8 | Business automation (n8n) | 10 hrs | 122 hrs | ✅ shipped |

---

## Decision Points Between Phases

**After Phase 1 → Phase 2?**
- Do you need WordPress content automation now?
- Or do you need more Python APIs deployed first?

**After Phase 2 → Phase 3?**
- Do you have content to generate?
- Or is manual content sufficient for now?

**After Phase 3 → Phase 4?**
- Is Namecheap DNS causing friction?
- Do you need CDN/WAF?

**After Phase 4 → Phase 5?**
- Do you have client sites that need staging?
- Or is direct-to-production acceptable?

**After Phase 5 → Phase 6?**
- Are you debugging performance issues?
- Do you need historical metrics?

**After Phase 6 → Phase 7?**
- Is the VPS hitting resource limits?
- Do you have budget for second server?

**After Phase 7 → Phase 8?**
- Do you have 5+ integrations to manage?
- Are Python scripts becoming unmaintainable?

---

## Recommended Path (as originally planned — now historical)

The original build order, given the 2025-era goals (revenue-generating
systems, AI agents driving infrastructure):

```
Phase 1 (Foundation)          ← original START
    ↓
Phase 2 (WordPress)           ← Client revenue potential
    ↓
Phase 3 (AI Content)          ← agent capability
    ↓
[Evaluate: Do you need more?]
    ↓
Phase 4-8 as needed
```

This sequence was followed and largely completed. **Phases 1–4, 6, 7, 8 are
shipped; only Phase 5 (dedicated staging tooling) remains unbuilt**, and the
foundation was re-platformed from Coolify onto SSH + Docker Compose. The
"on-demand build later" framing for Phases 4–8 is therefore historical — they
were built. For what to work on next, this document is not the source of
truth; see the live operations/reference docs linked at the top.
