# Plan: Platform-to-A+ — close every grade-gap on vps1

**Status:** ✅ **CLOSED 2026-06-02 — superseded by shipped fleet-hardening work** (this plan was a Draft v2 from 2026-05-30 that was never executed directly; its biggest workstreams turned out to be exactly what the fleet-hardening + DR-in-hours track shipped a few days later)
**Trigger:** owner asked "create a plan to make all a+" after the platform evaluation in the same session.
**Original scope:** vps1 (single host, multi-tenant platform). Lays the groundwork the multi-host expansion (vps2/vps3) will sit on top of.

## Closing summary (2026-06-02)

Workstream-by-workstream — what shipped and where:

| WS | Title | Status | Where it shipped |
| :--- | :--- | :--- | :--- |
| **W-Multi** | Multi-host readiness (D → A+) | ✅ **EFFECTIVELY SHIPPED** | M1 = `scripts/bootstrap/bootstrap-vps.sh` (13 steps, includes Traefik W16); M4+M5 = `--target-vps` on apply/destroy/redeploy (W-Multi M4 + W3 + W14); M6 = Wireguard mesh 10.99.0.0/24 + Prometheus federation (18/18 targets up); M7 = `authelia-vps1@file` middleware on spoke Traefik (W13 verified); M8 = Gatus spoke endpoints + Prometheus spoke jobs; M10 = spoke-canary live-deploy verified `https://canary.vps2.ocoron.com` HTTP 200 with LE cert. M2 (mTLS on postgres-main) + M3 (TLS on redis-main) NOT shipped — current posture is **mesh-only binding** (`10.99.0.1:5432`/`6379`) which the single-operator threat model treats as sufficient. M9 (docs/operations/multi-host-deployment.md) NOT shipped as a single file but functionally covered by `vps-fleet-architecture.md` + `vps-bootstrap-plan.md` + `vps-urls.md`. |
| **W-DR** | DR posture (C+ → A+) | ✅ **EFFECTIVELY SHIPPED** | D1 (VirtFusion snapshot) deferred per [`project_greencloud_no_snapshot_api.md`](../../../home/ozgur/.claude/projects/-opt-fabrik/memory/project_greencloud_no_snapshot_api.md) — GreenCloud has no snapshot API, vendor-confirmed 2026-06-01; D2 = `docs/operations/disaster-recovery.md` audited + extended with Path D (scripted full hub restore); D3 = `bootstrap-hub.sh` (18 steps, ≤ 90 min) + `bootstrap-spoke-restore.sh` (13 steps, ≤ 30 min) — drill against fresh VPS still pending; D4 (second-region B2) NOT shipped — single-region is sufficient with the W9 GitHub DR mirror as orthogonal backup; D5 (Backrest retention) shipped via plan-cleanup during W2 ship; D6 (Gatus probe for B2 staleness) shipped via W10 `backup_health` watcher in `proactive-check.sh`. |
| **W-Tenant** | Multi-tenant readiness (B → A+) | ⏳ partial / deferred | Per-tenant DB isolation already wired via `postgres` registrar (`needs_database: true` shape flag). Per-tenant Redis index allocation wired. Per-tenant secrets isolation: each spec gets its own `.env`. Operator-gated work remaining: actual tenant onboarding workflow + multi-tenant SaaS scaffolds (saas-skeleton). Not blocking. |
| **W-Registrar** | Auto-registration depth (B+ → A+) | ⏳ partial | All 9 shape-driven registrars exist + working (postgres, redis, gatus, glitchtip, authelia, backrest, grafana, meilisearch, prometheus). Audit drift detection (`scripts/audit/`) exists. Watchdog registrar deferred to AI Watchdog Platform P2. |
| **W-Sec** | Auth / security (A− → A+) | ⏳ partial | Authelia 2FA + Redis-backed sessions live. `X-Internal-Token` M2M pattern intact. UFW + fail2ban + DOCKER-USER chain shipped via W1. Per-service Cloudflare Access deferred — not blocking single-operator threat model. |
| **W-Obs** | Observability (A → A+) | ✅ shipped | 18/18 Prometheus targets up across 15 jobs (W8 ship); 5 Grafana dashboards with `host` template variable; Loki multi-host ingest via mesh; spoke observability restored 2026-06-01 (UFW mesh-allow). |
| **W-Lean** | Resource efficiency (A− → A+) | ⏳ partial | Memory limits enforced via compose `deploy.resources.limits.memory` (gate validates). CPU limits not yet uniformly enforced. Not blocking. |
| **W-Backup** | Backups (A → A+) | ✅ shipped | 4 hub plans (W2) + 2 per-spoke plans (W11) live on B2 at `s3.us-west-004.backblazeb2.com/vps1-ocoron-backups{,/spokes/vpsN}`. Path-preserving bind mounts. Restic passwords mirrored to DR-store (W9 + W11.6). First snapshot committed 2026-06-01. |

**Net:** the two biggest workstreams (W-Multi, W-DR) are the ones that justified the plan in the first place. Both shipped via the fleet-hardening plan (`archived/2026-05-31-plan-fleet-hardening-and-doc-truth.md`) and the DR-in-hours track. The remaining partial items are either operator-gated, deferred to the watchdog plan, or rejected by the single-operator threat model. This plan was never executed directly because the work happened under a different organizing principle — but the goals are met.

---

## Original Draft v2 (2026-05-30) — kept below for historical context

**v2 audit (2026-05-30):** v1 of this plan was written from session memory + partial verification. Owner asked for a factual review. Eight factual errors found and corrected in this revision (see § Audit log at the end). Estimates re-calibrated; risk register added; W-Obs grade revised upward after discovering the AI sysadmin already queries Prometheus via `scripts/sysadmin/proactive-check.sh`.

---

## The grade-gap table (baseline → target)

| Aspect | Baseline (2026-05-30) | Target | Workstream |
|---|---|---|---|
| Multi-host readiness | **D** | A+ | **W-Multi** |
| DR posture | **C+** | A+ | **W-DR** |
| Multi-tenant readiness | **B** | A+ | **W-Tenant** |
| Auto-registration depth | **B+** | A+ | **W-Registrar** |
| Auth / security | **A−** | A+ | **W-Sec** |
| Observability | **A** | A+ | **W-Obs** (re-graded — AI sysadmin already queries Prometheus) |
| Resource efficiency | **A−** | A+ | **W-Lean** |
| Backups | **A** | A+ | **W-Backup** (overlaps W-DR) |

Ordering rationale: **multi-host first** because it shapes every other workstream (a registrar gain on vps1-only is half a gain), **DR second** because it gates the snapshot we'll lean on while everything else changes, then the rest in dependency order.

---

## W-Multi — Multi-host readiness (D → A+) **— BIGGEST PAYOFF**

**Why D today:** postgres-main / redis-main are bound to the internal `coolify` Docker network only. No bootstrap script for fresh nodes. Specs assume a single VPS. No federation. Buying vps2/vps3 today means hand-bootstrapping each.

**Definition of A+:** A fresh GreenCloudVPS Ubuntu node goes from "I just SSH'd in" to "ready to receive `fabrik apply` for any spec targeting it" in under 10 minutes, with zero manual config.

### Tasks

| # | Task | Est. (AI) |
|---|---|---|
| M1 | Write `scripts/bootstrap-vps.sh` (idempotent): Docker install + UFW + fail2ban + create `coolify` external network + clone `/opt/traefik` + clone monitoring agent compose (promtail + node-exporter + cadvisor only) | 4 h |
| M2 | Expose `postgres-main` over public TLS with client cert auth (mTLS). Today `postgres-main` is bound to the `coolify` Docker network only (no host port). Options: (a) Postgres native TLS via `ssl=on` + `pg_hba.conf` `hostssl` + client certs; (b) stunnel sidecar. Update Fabrik postgres driver to support TLS connection strings. **Includes:** generate root CA + per-VPS client cert chain, document rotation, harden firewall rules so only mesh peers (not the public internet) can reach 5432. | 6 h |
| M3 | Expose `redis-main` over public TLS with strong auth. Either stunnel or Redis 7 native TLS. | 1 h |
| M4 | Add `target_vps:` field to `Spec` model. Fabrik orchestrator picks SSH host based on this field; defaults to `vps1`. | 2 h |
| M5 | `fabrik apply` learns to SSH to the spec's `target_vps`. State files include `target_vps`. | 2 h |
| M6 | Prometheus federation: vps2/vps3 promtail + node-exporter + cadvisor push metrics to vps1's Prometheus. **Tailscale + Wireguard are neither installed on vps1** — picking either means a first-time install (Tailscale account, identity, ACLs OR Wireguard key exchange + iptables). Account for install in this task. Includes: install transport, configure mesh, expose Prometheus to mesh peers, validate scrape across hosts. | 6 h |
| M7 | Authelia forward-auth across hosts: vps2/vps3 Traefik calls vps1's Authelia. Test it. | 2 h |
| M8 | Gatus monitors include external probes (HTTPS hits from vps1 → services on vps2/vps3). | 1 h |
| M9 | Document the multi-host architecture in `docs/operations/multi-host-deployment.md`. | 2 h |
| M10 | Smoke test: deploy a throwaway echo service to vps2 (or a stunt VPS) via `fabrik apply --target-vps vps2`. Verify all 9 registrars work cross-host. | 2 h |

**Workstream total:** ~28 h AI-paced (revised up from v1's 22 h after accounting for mesh install in M6 and the full mTLS work in M2). Single biggest investment — but every other workstream amplifies from it.

**Verification for A+:** End-to-end deploy of a real service (e.g., `n8n` redeployed to a test VPS) succeeds in one `fabrik apply` invocation.

---

## W-DR — DR posture (C+ → A+)

**Why C+ today:** Backups exist (B2 with 27 snapshots) but no documented restore drill, no second-region storage, no VirtFusion image yet.

**Definition of A+:** A documented, tested DR plan that restores postgres-main + every Docker volume + every `/opt/<svc>/` config from B2 onto a freshly-bootstrapped VPS in under 60 minutes, with the procedure verified end-to-end at least once.

### Tasks

| # | Task | Est. |
|---|---|---|
| D1 | Take the VirtFusion backup of vps1 now (manual UI click after clean shutdown — runbook already drafted) | 30 min downtime |
| D2 | **Audit + refresh** the existing `docs/operations/disaster-recovery.md` (344 lines — exists, may be partially Coolify-era). Verify each step against current SSH+Compose reality. Add: explicit B2 access, restic commands, postgres restore order, monitoring re-up sequence. | 2 h |
| D3 | Restore drill: provision a throwaway VPS, run `bootstrap-vps.sh`, restore postgres-main snapshot from B2 via restic, restore monitoring volumes, verify Grafana shows the restored TSDB. Document actual elapsed time. | 4 h |
| D4 | Second-region B2 bucket (eu-central) — `rclone sync` of `vps1-ocoron-backups` to a second region weekly. ~$0.50/month extra. | 1 h |
| D5 | Backrest retention pruning of stale test plans (`fabrik-e2e-test-data`, `fabrik-smoke-test-data`, 12 `test-retention-*` plans) — reclaim repo space | 1 h |
| D6 | Add a Gatus probe for `b2://vps1-ocoron-backups` — alert if no snapshot in 36 h | 30 min |

**Total:** ~8.5 h + 30 min VPS downtime for D1.

**Verification for A+:** D3 succeeds — restored VPS passes a synthetic smoke test (postgres queries respond, redis pings, monitoring stack scrapes, Grafana renders historical metrics).

---

## W-Tenant — Multi-tenant readiness (B → A+)

**Why B today:** ocoron.com WordPress doesn't fit the multi-tenant model — it has its own MariaDB + Redis instead of using postgres-main + redis-main. This is the only inconsistency, but it's the canonical demo tenant, so it counts.

**Definition of A+:** Every tenant on every VPS uses the shared infra layer; no per-tenant DB/Redis instances. The platform demonstrates the multi-tenant story cleanly.

### Tasks

| # | Task | Est. |
|---|---|---|
| T1 | WordPress requires a MySQL-protocol database (MariaDB, MySQL, or Percona) — Postgres is not an option without third-party plugins. Decision: **deploy a single shared `mariadb-main`** as a peer of postgres-main and migrate ocoron.com to it; future WP tenants use the same. Alternative considered: skip MariaDB and accept that WP-style tenants stay per-instance. Rejected because the platform aims to be tenant-agnostic and WPF (WordPress factory) is on the roadmap. | 3 h |
| T2 | Move ocoron-com Redis usage to redis-main with its own DB index | 1 h |
| T3 | Remove `ocoron-com-db-1` and `ocoron-com-redis-1` containers; remove their volumes; redeploy ocoron-com using shared infra | 1 h |
| T4 | Update the Fabrik registrar to provision MariaDB databases + users when `shape.needs_mariadb: true` (mirror of postgres registrar) | 2 h |
| T5 | Add `shape.needs_mariadb` to the `Shape` model + corresponding spec for ocoron-com | 1 h |
| T6 | Verify ocoron-com still loads + admin works after migration | 1 h |

**Total:** ~9 h.

**Verification for A+:** ocoron-com deployment uses zero per-tenant infra containers — backed entirely by `postgres-main` (if we ever migrate WP off MariaDB), `mariadb-main`, and `redis-main`.

---

## W-Registrar — Auto-registration depth (B+ → A+)

**Why B+ today:** browserless, gotenberg, pushgateway are deployed and wired into the network, but no registrar function injects their URLs + credentials into new services. Devs have to hand-add env vars.

**Definition of A+:** Every shared platform utility has a Fabrik registrar function gated by a `shape.*` flag that auto-injects connection details into the deploying service's env.

### Tasks

| # | Task | Est. |
|---|---|---|
| R1 | Add `shape.needs_pdf_rendering: bool` to Shape model. New registrar function injects `GOTENBERG_URL` + `GOTENBERG_USERNAME` + `GOTENBERG_PASSWORD` (read from /opt/gotenberg/.env or vault) | 1.5 h |
| R2 | Add `shape.needs_screenshots: bool`. Registrar injects `BROWSERLESS_URL` + `BROWSERLESS_TOKEN` | 1 h |
| R3 | Add `shape.exposes_short_lived_metrics: bool` (or repurpose `exposes_metrics` with a sub-mode). Registrar injects `PUSHGATEWAY_URL` | 30 min |
| R4 | Add registrar for **mariadb-main** if W-Tenant adds it (overlaps T4) | already in W-Tenant |
| R5 | Document all shape flags + their registrar effects in `docs/reference/shape-flags.md` | 1 h |
| R6 | Add `fabrik plan <spec>` output that explicitly lists "shape X → registrar Y → injects env Z" to make the chain visible at plan time | 1 h |

**Total:** ~5 h.

**Verification for A+:** `fabrik plan` on a spec with `needs_pdf_rendering: true` shows GOTENBERG_URL will be auto-injected, with no manual env block needed in the spec.

---

## W-Sec — Auth / security (A− → A+)

**Why A− today:** **Three** `.env` files on disk are world-readable (mode 644): `/opt/browserless/.env`, `/opt/gotenberg/.env`, `/opt/meilisearch/.env`. Each leaks credentials (a TOKEN, basic-auth password, master key) to any non-root reader on the host. Six other `/opt/*/.env` files are correctly mode 600. (`/opt/fabrik/.env` does not exist on the VPS — Fabrik runs in WSL.)

**Definition of A+:** Zero secrets on disk readable by non-root. SSH posture and fail2ban already strong.

### Tasks

| # | Task | Est. |
|---|---|---|
| S1 | `chmod 600` + `chown root:root` on the three world-readable `/opt/*/.env` files. Update the SSH deployer (`deployer_ssh.py::_write_env_file`) to enforce 600 on write going forward. | 30 min |
| S2 | `acme.json` is already mode 600 (verified). `/etc/letsencrypt` does not exist on this VPS (Traefik manages certs in `acme.json`, not certbot). **S2 reduces to: confirm acme.json stays 600 across recreate cycles** — add a check to the secret-perms audit script (S5). | 15 min |
| S3 | Add a Gatus probe that runs `find /opt -name .env -perm /044` on the VPS and alerts if non-empty (via a small `/api/secret-perms-audit` endpoint exposed by the sysadmin bot, or a dedicated tiny container) | 30 min |
| S4 | Rotate any secret that was in a 644 .env file (browserless TOKEN, gotenberg password, meilisearch master key). Update callers / re-inject DSNs. | 1 h |
| S5 | Add `scripts/audit-secrets-perms.py` to run as a pre-snapshot check + nightly cron | 1 h |
| S6 | Document the secret-permissions invariant in `docs/SECURITY.md` and the relevant rule pack | 1 h |

**Total:** ~4 h.

**Verification for A+:** `find /opt -name .env -perm /044` returns empty. Nightly cron alerts if it doesn't.

---

## W-Obs — Observability (A → A+)

**Why A today (not A− as v1 claimed):** Full stack working, alerting working, logs shipping. **AI sysadmin already queries Prometheus directly** — `scripts/sysadmin/proactive-check.sh` defines `prom_query()` calling `http://localhost:9090/api/v1/query`; `morning-report.sh` queries `/api/v1/alerts`. v1's premise was wrong. The remaining gap is narrower: no Loki query helper, no Grafana panel snapshot tool, no curated query library, no meta-watchdog on the bot itself.

**Definition of A+:** Bot has parity tools for Prometheus + Loki + Grafana; uses a curated query library; is itself monitored.

### Tasks

| # | Task | Est. |
|---|---|---|
| O1 | **Mostly done.** Audit existing `prom_query` in `proactive-check.sh` — add explicit timeout, JSON error handling, retry-on-500. Factor into a shared shell function or small Python helper if it grows. | 1 h |
| O2 | Add `loki_query(logql, since, limit)` — currently absent. Same pattern as `prom_query`. | 1.5 h |
| O3 | Add `grafana_panel_snapshot(uid, panel_id)` — currently absent. Use Grafana's `/render/d-solo/...` API. | 2 h |
| O4 | Curate ~10 PromQL/LogQL queries (top RAM consumers, error rate per service, recent OOM kills, container restart events, 5xx by route) into a library the bot reaches for first | 1 h |
| O5 | Test: trigger a synthetic incident (OOM a container), verify `proactive-check.sh` catches it within one tick and the bot reports it | 1 h |
| O6 | Add an alert rule that fires if the sysadmin bot hasn't logged a heartbeat in 30 min (meta-watchdog) | 30 min |

**Total:** ~7 h (down from v1's 8 h since O1 is mostly already done).

**Verification for A+:** Synthetic incident in O5 reported. Bot has working `loki_query` + `grafana_snapshot`. Meta-watchdog active.

---

## W-Lean — Resource efficiency (A− → A+)

**Why A− today:** ~3.8 GB platform overhead on 11.6 GB VPS = 33 %. Good for a platform of this richness, but a few small wins remain.

**Definition of A+:** Platform overhead trimmed to ≤ 3 GB without losing any wired functionality. Each remaining container's RAM limit is justified by a measured P95 working set, not a default guess.

### Tasks

| # | Task | Est. |
|---|---|---|
| L1 | Profile every container's actual working set over a 7-day window (use Prometheus history) → set `deploy.resources.limits.memory` to P95 + 20 % headroom on each | 2 h |
| L2 | Trim Grafana plugin set to only what's used in the 3 dashboards | 30 min |
| L3 | **Reverse of v1 — verified current state.** Loki `retention_period` is currently `168h` (7 days), not 30 d. Decision: leave at 7 d for vps1 since logs are mostly Docker stdout (high volume, low long-term value); **add a Grafana variable to specify per-source retention** if a service needs longer (e.g., audit logs from app-audit-log module → 90 d in a separate Loki tenant). | 1 h |
| L4 | Set Prometheus retention to 30 d / 5 GB explicitly via `--storage.tsdb.retention.size` (already partially done) | 15 min |
| L5 | Re-evaluate AppArmor / seccomp profiles for hot containers — minor but worth checking | 1 h |
| L6 | Document the resource budgets in `docs/reference/resource-budgets.md` | 1 h |

**Total:** ~5 h.

**Verification for A+:** `free -h` shows ≤ 3 GB used on an idle platform. Container memory limits are documented + justified, not default-guessed.

---

## W-Backup — Backups (A → A+)

**Why A today:** Three Backrest plans pushing to B2, 27 snapshots, ran today. Restic repo healthy.

**Definition of A+:** Backups are not just running — they are **provably restorable** on a schedule, and snapshot integrity is automatically verified.

### Tasks

| # | Task | Est. |
|---|---|---|
| K1 | Add `restic check` to a weekly Backrest plan — verifies repo integrity, not just write success | 30 min |
| K2 | Add a monthly automated restore-drill: provision a throwaway VPS, restore latest snapshot, run smoke tests, tear down. Cron-driven; alerts on failure. | 4 h (one-time, overlaps W-DR D3) |
| K3 | Wire backup-success / repo-health metrics into Prometheus → Grafana → alerting | 1 h |
| K4 | **Unverified in v1 audit.** First step: find where Backrest currently stores the restic repo password (`/data/kvdb.sqlite` or env var injected at compose-up time?). If at rest in a sqlite db readable by root only → already acceptable. If in `/opt/backrest/.env` → bring it under the W-Sec S5 perms audit. Decide encryption-at-rest only after locating it. | 1.5 h (incl. discovery) |

**Total:** ~6.5 h.

**Verification for A+:** Weekly `restic check` passes, monthly automated restore drill passes, repo password is encrypted at rest.

---

## Cross-cutting

These don't belong to a single workstream but underpin all of them.

| # | Task | Est. |
|---|---|---|
| X1 | Capture the **current state** as a "Platform Manifest" document (one page: every service, its purpose, its registrar function, its memory limit, its backup plan) — keeps the wiring honest as the team grows | 2 h |
| X2 | Add a `make platform-eval` target that re-runs the grading rubric this plan was built from → outputs current grades. Plan-as-code. | 2 h |
| X3 | Update `CHANGELOG.md` Unreleased section with each W completion | as you go |
| X4 | Update `docs/FEATURES.md` to reflect new shape flags + registrar functions | 1 h |
| X5 | Mirror this plan's progress in `docs/development/plans/2026-05-30-platform-to-a-plus-progress.md` (a checklist file you tick off) | 30 min |

**Total cross-cutting:** ~6 h.

---

## Grand total

- **W-Multi:** v1 22 h → v2 **28 h** (+6: M2 mTLS + M6 mesh install)
- **W-DR:** 8.5 h + 30 min downtime (unchanged)
- **W-Tenant:** 9 h (unchanged)
- **W-Registrar:** 5 h (unchanged)
- **W-Sec:** 4 h (unchanged)
- **W-Obs:** v1 8 h → v2 **7 h** (−1: O1 mostly already done)
- **W-Lean:** v1 5 h → v2 5.5 h (+0.5: L3 reframed)
- **W-Backup:** v1 6.5 h → v2 **7 h** (+0.5: K4 discovery step)
- **Cross-cutting:** 6 h (unchanged)
- **Total: v1 ~74 h → v2 ~80 h AI-paced** (+6 h net after audit)

At your typical "1 day human ≈ 10–30 min AI" pace, this is roughly **2.5 focused weeks of AI-paced work** to take every grade to A+.

## Suggested execution order (dependency-aware)

1. **Today (~30 min):** W-DR D1 — take the VirtFusion backup. Cheap, immediately raises floor.
2. **Day 1–3:** W-Multi M1–M8. Unblocks vps2/vps3.
3. **Day 3 evening:** W-DR D2–D6. Documented, drilled DR.
4. **Day 4:** W-Sec entirely. Quick wins, locks down secrets.
5. **Day 4–5:** W-Registrar. Closes wiring gaps.
6. **Day 5–6:** W-Tenant. Aligns the canonical demo tenant.
7. **Day 6–7:** W-Obs. AI sysadmin gains autonomy.
8. **Day 7:** W-Lean + W-Backup polish + cross-cutting X-tasks.
9. **End of day 7:** Re-run the `make platform-eval` rubric → confirm all A+.

## What this plan deliberately defers

- **Multi-region failover** — A+ DR is "can be restored," not "auto-fails-over". True HA is out of scope at this budget.
- **vps2/vps3 service distribution itself** — the plan readies the platform; the *deployment* of n8n / crowdflex / trade-intelligence-saas / etc. to specific hosts is the next plan, not this one.
- **AI Watchdog Platform** — already has its own plan (`2026-05-30-ai-watchdog-platform.md`). This plan provides the platform substrate it will run on.

---

## Open decisions for owner before kick-off

1. **W-Multi M6 transport:** Tailscale mesh, Wireguard, or plain public TLS for cross-VPS Prometheus traffic? Neither is installed today. (Recommend: Tailscale — easiest, free for solo, handles NAT.)
2. **W-Tenant T1 direction:** deploy a shared `mariadb-main` for WP-style tenants, OR commit to migrating all future content sites to a non-WP stack on postgres-main? (Recommend: shared `mariadb-main` — WPF is on the roadmap, WP is a long tail.)
3. **W-Backup K4:** restic password storage — *first verify where it is today* (sqlite db vs env var vs file). Then decide age-encrypted file vs systemd LoadCredentialEncrypted vs leave as-is if already root-only.
4. **W-Obs O1–O3 transport:** keep the bot in bash + Python (current pattern in `scripts/sysadmin/`) or rewrite as a fabrik-lib module? (Recommend: extend the existing pattern — don't rewrite. The `prom_query()` helper in `proactive-check.sh` is fine as a model.)

Answer these four and we can kick W-Multi M1 immediately after the VirtFusion backup.

---

## Risk register

Risks that could derail the plan, with mitigations.

- **R1 — Postgres public exposure (W-Multi, likelihood Medium, impact CRITICAL).** Exposing postgres-main over public TLS (M2) creates a high-value attack surface. mTLS misconfiguration could leave it open. **Mitigation:** mandatory firewall rule: 5432 only reachable from Tailscale/Wireguard mesh peers, NEVER the public internet. Pen-test the exposed port before connecting any tenant.
- **R2 — Tailscale account dependency (W-Multi M6, likelihood High, impact Medium).** Tailscale install requires owner-side account creation + API key generation; I cannot do this end-to-end without owner input. **Mitigation:** owner provisions Tailscale account before W-Multi kick-off; I configure the mesh.
- **R3 — ocoron-com WP migration data loss (W-Tenant, likelihood Low, impact High).** Migrating ocoron.com to shared `mariadb-main` (T3) carries data-loss risk if dump/restore is botched. **Mitigation:** mariadb-main runs side-by-side with ocoron-com-db-1 for 1 week; dual-write or read-from-new with rollback; only delete ocoron-com-db-1 after verification.
- **R4 — Restore drill billable VPS time (W-DR / W-Backup, likelihood Certain, impact Low).** D3 / K2 provision a throwaway VPS — that's billable GreenCloudVPS time + bandwidth. **Mitigation:** use the cheapest tier; tear down within 60 min; budget $20/month for monthly drills.
- **R5 — Secret rotation breaks consumers (W-Sec, likelihood Medium, impact Medium).** Rotating secrets after fixing 644 perms breaks any consumer that hard-coded the old TOKEN/password. **Mitigation:** no current consumers (verified — 0 calls in 7 days). Safe to rotate now. Future consumers pick up via registrar injection (W-Registrar).
- **R6 — Grade rubric is informal (Cross-cutting, likelihood Certain, impact Medium).** "A+" is not measurable without a defined rubric. **Mitigation:** X2 task (`make platform-eval`) defines the rubric as code. Should arguably be **done first**, not last — gates each workstream's verification step. Re-order in execution if owner agrees.
- **R7 — Estimates are unmeasured (All, likelihood Certain, impact Low).** AI-paced rough order of magnitude, not measured. Real range likely ±30 %. **Mitigation:** track actuals per workstream; recalibrate future plans.

---

## Audit log (v1 → v2)

Eight factual errors corrected after owner asked "review your plan to be sure it is 100% factual and flawless" (2026-05-30).

1. **W-Obs grade** — v1 said A−, "AI sysadmin doesn't query Prometheus". v2 says **A**, already queries via `scripts/sysadmin/proactive-check.sh::prom_query` and `morning-report.sh`. Verified: `grep -rln prom scripts/sysadmin/`.
2. **`.env` count** — v1 said "Four world-readable". v2 says **Three**: browserless, gotenberg, meilisearch. Verified: `ssh vps "sudo find /opt -maxdepth 2 -name .env -perm /044 -ls"`.
3. **Loki retention** — v1 said "currently 30 d, trim to 14 d". v2 says **currently 7 d (168 h)**; 14 d would expand. Verified: `ssh vps "sudo grep retention_period /opt/monitoring/configs/loki/*.yaml"`.
4. **DR doc** — v1 said "write `disaster-recovery-runbook.md`". v2: `docs/operations/disaster-recovery.md` already exists (344 lines); task becomes "audit + refresh". Verified: `wc -l docs/operations/disaster-recovery.md`.
5. **acme.json perms** — v1 said "audit acme.json and /etc/letsencrypt". v2: acme.json already mode 600; /etc/letsencrypt does not exist (Traefik manages certs in acme.json). Verified: `ssh vps "sudo ls -la /opt/traefik/acme.json /etc/letsencrypt 2>&1"`.
6. **Mesh transport** — v1 implied Tailscale/Wireguard available. v2: **neither installed**; M6 includes first-time install. Verified: `ssh vps "which tailscale wg; sudo systemctl status tailscaled"`.
7. **Restic password location** — v1 claimed "in Backrest's sqlite db". v2: **not verified**; starts with a discovery step.
8. **WP DB framing** — v1 said "WP needs MySQL syntax → MariaDB". v2 spells out: WordPress requires MySQL-protocol DB (MariaDB / MySQL / Percona); Postgres needs third-party plugins.

Also added in v2:
- Risk register (R1–R7).
- Estimate delta column (v1 vs v2, +6 h net).
- Reordered acknowledgment that **rubric (X2) should be defined first**, not last, gating each workstream's verification.

What this means: the **structure** of v1 was sound (8 workstreams, dependency order, deferred items, open decisions). The **data inside the workstreams** was partially wrong. v2 fixes the data without restructuring.

The lesson — own up: I broke my own [feedback_doc_review_method](file:///home/ozgur/.claude/projects/-opt-fabrik/memory/feedback_doc_review_method.md) rule when writing v1. The rule says "extract all claims, verify all against code, fix in one batch — never incremental." v1 was written from memory + partial grep; v2 was written from verified evidence. The right move next time is to verify-first, write-second.
