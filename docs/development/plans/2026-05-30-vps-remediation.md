# Plan — VPS Golden Image (gap-closing)

**Date:** 2026-05-30 (revised — comprehensive analysis)
**Owner:** Özgür (solo dev + AI agent assistance)
**Status:** Workstream 3 executed; Workstreams 1, 2, 4–10 pending owner approval.
**Gates:** Watchdog Platform P2 code execution (see [P2 sub-plan](2026-05-30-ai-watchdog-platform-P2-subplan.md))

---

## Critical context I missed in earlier drafts

After a deep VPS analysis (`ssh vps` introspection), I found existing infrastructure I should have known about:

- **`/opt/fabrik/docs/infrastructure/vps-bootstrap-plan.md`** — already exists on the VPS. Comprehensive plan for "fresh Ubuntu 24.04 → fully provisioned VPS in ~15 min via automated script." This IS the golden image plan. Just needs a Coolify-removal pass + watchdog addition.
- **`/opt/fabrik/docs/infrastructure/vps-captured-state-20260520.txt`** — 28KB / 737-line snapshot of the full VPS configuration from 2026-05-20. The baseline the bootstrap plan was written against.
- **`/etc/systemd/system/vps-sysadmin-bot.service`** — actively running since 2026-05-21. Telegram bot + Claude Code (v2.1.144) doing on-demand AI sysadmin at the host level. The "watchdog" concept already exists for the platform itself; the watchdog platform we're building is the per-project complement.
- **`/etc/cron.d/vps-sysadmin`** — proactive checks every 15 min + morning report 08:00 + weekly security Mon 08:30 + weekly maintenance Sun 03:00 + monthly backup verify 1st 04:00. All Claude-driven.

These artifacts are why "infra is good there and well documented too" — comprehensive sysadmin automation is already live. The golden image work is **gap-closing on top of that baseline**, not building from scratch.

---

## Verified current state vs captured baseline (2026-05-20)

### Changed since baseline

- ✅ Migrated all containers OUT of Coolify (verified: 0 `coolify.managed=true` containers running).
- ✅ Workstream 3 executed: removed `image-broker`, `site-provisioner` containers + `/opt/{image-broker,site-provisioner}/`; pruned 15 Coolify-era ghosts + `coolify-proxy` (reclaimed 54.58 MB).
- ✅ Updated `POSTGRES_CONTAINER` constant (P1 commit fd32c3e).
- ✅ Added `fabrik_analytics` DB + `cost_ledger` table on postgres-main (P1 commit fd32c3e).

### Running today (29 containers)

| Category | Count | Items |
| --- | ---: | --- |
| Core platform | 3 | postgres-main, redis-main, traefik |
| Auth | 1 | authelia |
| Observability — metrics | 9 | prometheus, grafana, alertmanager, pushgateway, cadvisor, node-exporter, postgres-exporter, redis-exporter, netdata |
| Observability — logs | 2 | **loki, promtail** *(I claimed in P1+P2 these weren't here — wrong)* |
| Observability — uptime + errors | 3 | gatus, glitchtip-web, glitchtip-worker |
| Backup + alerting | 2 | backrest, apprise |
| Off-the-shelf compute | 4 | browserless, gotenberg, meilisearch, n8n |
| Customer site | 5 | ocoron-com-{wordpress,db,redis,nginx,backup}-1 |

### Cleanup gaps found

| # | Gap | Evidence | Reclaim |
| --- | --- | --- | --- |
| G1 | 16 orphan Docker volumes (Coolify UUID-prefixed names) | `sudo docker volume ls \| grep -E '^[a-z0-9]{20,}'` returns 16; `docker system df` reports 2.824 GB / 41 % of volume disk reclaimable | **2.824 GB** |
| G2 | 23 orphan Docker networks (Coolify UUID-named) | `sudo docker network ls \| grep -E '^[a-z0-9]{20,}$'` returns 23 | minimal |
| G3 | 13 unused Docker images (verified via ancestor check) | `docker system df` reports 10.88 GB / 71 % of image disk reclaimable. Confirmed unused: 4 Coolify images (coolify, helper, realtime, sentinel), 2 site-provisioner builds, image-broker, traefik:v3.6, grafana:11.5.1, netdata:stable, postgres:15-alpine, curlimages/curl, alpine:latest | **10.88 GB** |
| G4 | 2 Coolify-era systemd units | `coolify-alias-watcher.service` (`enabled` + `active` — running but functionally obsolete post-Coolify; nothing to watch for); `coolify-ssh-permissions.timer` (`failed` since 2026-05-20) | — |
| G5 | 4 dormant /opt/ directories | `email-reader` (135 MB, dormant project), `namecheap` (51 MB, dormant — superseded by removed site-provisioner), `coolify-alias-watcher` (12 KB, legacy script), `backupsystem.tar.gz` (32 KB, orphan archive) | ~186 MB |
| G6 | Broken cron entry | `/etc/cron.d/duplicati-backup` references `/opt/scripts/duplicati-backup.sh` which doesn't exist | — |
| G7 | `vps-bootstrap-plan.md` outdated | Still documents Coolify install + Coolify-managed services. Needs SSH+Compose + watchdog pass. | — |
| G8 | `vps-captured-state-20260520.txt` outdated | Captured before migration + P1 + cleanup. Needs refresh. | — |

---

## Workstreams

### Workstream 1 — Coolify-residue cleanup (~15–30 min)

(Unchanged from previous revision.) Execute [2026-05-30-coolify-residue-cleanup.md](2026-05-30-coolify-residue-cleanup.md): Tier B docs continuation, Tier C source comments, `CoolifyConfig` removal from spec_loader, `ctx.coolify_uuid → ctx.app_name` rename across 10 files.

**Gate for Watchdog P2:** the spec-schema cleanup is the gate.

### Workstream 2 — Audit-registrars awareness (~5–10 min)

(Unchanged.) Add `audit_shared_analytics()` to `src/fabrik/audit.py`; wire into dispatch.

### Workstream 3 — Container hygiene cleanup (DONE 2026-05-30)

(Unchanged.) Pruned 15 ghosts + coolify-proxy; removed image-broker + site-provisioner.

### Workstream 4 — Docker volume cleanup (~2 min)

For each of the 16 Coolify UUID-prefixed volumes, verify zero containers attached (`docker volume inspect`), then `docker volume rm`. CRITICAL: the old `l0k4gk0kggc8...postgres-data` volume contains 131 MB of pre-migration postgres data. **Action: archive to backup before removal, then rm.**

Safe pruning command for all UUID-named volumes EXCEPT the postgres one (manual archive first):

```bash
ssh vps "sudo docker volume ls --format '{{.Name}}' | grep -E '^[a-z0-9]{20,}' | grep -v 'l0k4gk0kggc8okcwk0s4c8s8_postgres-data' | xargs -r sudo docker volume rm"
ssh vps "sudo docker run --rm -v l0k4gk0kggc8okcwk0s4c8s8_postgres-data:/old -v /opt/backups:/backup alpine tar czf /backup/coolify_postgres-data_pre_migration_$(date +%Y%m%d).tar.gz -C /old ."
ssh vps "sudo docker volume rm l0k4gk0kggc8okcwk0s4c8s8_postgres-data"
```

### Workstream 5 — Docker network cleanup (~30 s)

```bash
ssh vps "sudo docker network prune -f"
```

Removes all networks with no attached containers (Docker's prune is safe by design — it never removes used networks).

### Workstream 6 — Docker image cleanup (~30 s, ~10.88 GB reclaim)

```bash
ssh vps "sudo docker image prune -a -f --filter 'until=168h'"
```

Removes all images unused for 7+ days. Reclaims **10.88 GB** (`docker system df` verified — 71 % of image disk). Includes 4 Coolify images, 2 site-provisioner builds, image-broker, traefik:v3.6, grafana:11.5.1, netdata:stable, postgres:15-alpine, curlimages/curl, alpine:latest, plus their layer overhead.

### Workstream 7 — Coolify systemd cleanup (~2 min)

**Honest characterization:** `coolify-alias-watcher.service` is currently `enabled` AND `active` (running). It's not "dead legacy" — it's a live process that watches for Coolify container redeploys to re-apply friendly DNS aliases. With Coolify gone and verified zero `coolify.managed=true` containers, the service has nothing to watch for; disabling it is safe but it's *obsolete-but-live*, not *failed*.

`coolify-ssh-permissions.timer` IS failed (since 2026-05-20).

```bash
ssh vps "sudo systemctl disable --now coolify-alias-watcher.service coolify-ssh-permissions.timer 2>/dev/null"
ssh vps "sudo rm -f /etc/systemd/system/coolify-alias-watcher.service /etc/systemd/system/coolify-ssh-permissions.timer"
ssh vps "sudo systemctl daemon-reload"
```

Verification post-run: `systemctl list-units --type=service \| grep coolify` should be empty.

### Workstream 8 — Filesystem cleanup (~5 min)

Decision points (owner picks each):

- **`/opt/email-reader/`** (135 MB) — dormant project (December '25). Archive to `/opt/backups/archived/email-reader-$(date).tar.gz` then `sudo rm -rf /opt/email-reader`? Owner says yes/no.
- **`/opt/namecheap/`** (51 MB) — dormant DNS automation, superseded by removed site-provisioner. Archive + rm? Owner says yes/no.
- **`/opt/coolify-alias-watcher/`** (12 KB) — legacy script for the removed systemd unit. `sudo rm -rf`. Safe.
- **`/opt/backupsystem.tar.gz`** (32 KB) — orphan archive. Check contents, archive to /opt/backups if needed, then rm. Owner pick.
- **`/etc/cron.d/duplicati-backup`** — points at non-existent script. `sudo rm /etc/cron.d/duplicati-backup`. Safe.

### Workstream 9 — Update `vps-bootstrap-plan.md` (~10–15 min)

Refactor the existing `/opt/fabrik/docs/infrastructure/vps-bootstrap-plan.md` to reflect post-Coolify reality:

- Remove the Coolify install section + the Coolify-managed services section.
- Replace with: SSH+Compose deployment pattern, fabrik orchestrator install, per-project `compose.yaml` under `/opt/<project>/`.
- Add: watchdog sidecar deployment (forward reference to Watchdog Platform P2 sub-plan).
- Add: `fabrik_analytics` DB initialization (per P1 `ensure_shared_analytics_db()`).
- Remove: image-broker + site-provisioner from the services list (they're not currently deployed).
- Update: `/opt/coolify-alias-watcher/`, `coolify-alias-watcher.service`, `coolify-ssh-permissions.timer` mentions (these are gone post-Workstream 7).

### Workstream 10 — Regenerate captured-state baseline (~5 min)

Create `vps-captured-state-20260530.txt` (new snapshot post-cleanup). Either:

- Re-run the same capture script that produced the 2026-05-20 baseline (need to find it), OR
- Manually capture: `systemctl list-units --type=service`, `docker ps`, `docker volume ls`, `crontab -l`, `ufw status`, `sysctl -a`, `ss -tlnp`, all `/etc/cron.d/`, all relevant `/opt/*/compose.yaml`.

Keep the 2026-05-20 file as historical baseline; the new one is the post-migration golden state.

---

## WP-as-template — answer to your question

> *"the below one can be copied so i can replace it with a different website?"*
> (referring to ocoron-com — 5 containers: wordpress, db, redis, nginx, backup)

**Yes — three paths, ranked best-first:**

1. **Use the existing fabrik `wordpress` scaffold type.** `fabrik scaffold` already supports `wordpress` per `SCAFFOLD_TYPES` in `src/fabrik/scaffold.py:128`. Run `fabrik scaffold /opt/<new-site> --type wordpress --preset <content|company|landing|ecommerce>` and customize. This is the most aligned with fabrik's workflow.
2. **Direct copy of ocoron-com structure.** `cp -r /opt/ocoron-com /opt/<new-site> && cd /opt/<new-site> && sed -i 's/ocoron-com/<new-site>/g; s/ocoron.com/<new-domain>/g' compose.yaml nginx/default.conf`. Then regenerate the hardcoded `WORDPRESS_DB_PASSWORD` (currently visible in compose.yaml — that's a security issue worth fixing during the copy). Faster but bypasses fabrik's scaffolding patterns.
3. **Hybrid:** scaffold via fabrik to get the conventional structure, then port any ocoron-com customizations (php-fpm tuning at `php-fpm/zz-fabrik-listen.conf`, custom nginx at `nginx/default.conf`).

**Note on the hardcoded password:** ocoron-com's compose.yaml has `WORDPRESS_DB_PASSWORD: "dmkd56Q9ExZ799hIQkQuGywmjLZafQij"` visible in plain text. Fabrik's scaffold pattern uses generated secrets via `.env`. Whichever path you pick, do NOT propagate the hardcoded password.

---

## Sequencing with Watchdog Platform (AI-paced)

| Order | What | AI-paced effort |
| --- | --- | --- |
| DONE | Workstream 3 (container hygiene) | 30 s |
| Now | Workstream 4 (volume cleanup — verify postgres archive) | 2 min |
| Now | Workstream 5 (network prune) | 30 s |
| Now | Workstream 6 (image prune) | 30 s |
| Now | Workstream 7 (Coolify systemd) | 2 min |
| Now | Workstream 8 (filesystem cleanup) | 5 min |
| Next | Workstream 1 (Coolify-residue cleanup, gates P2 code) | 15–30 min |
| Then | Watchdog P2 code execution | 2–4 hrs |
| Then | Workstream 2 (audit-registrars) | 5–10 min |
| Then | Workstream 9 (update bootstrap plan) | 10–15 min |
| Then | Workstream 10 (regenerate captured state) | 5 min |
| Then | Watchdog P3 + P4 + P5 | per parent plan |

**Total VPS golden-image cleanup: ~30 min.** Plan + bootstrap doc updates: ~30 min more. Watchdog arc: 3–6 hrs.

---

## Acceptance criteria

**Golden state at completion:**

- Running container count: stable at 29 (or grows by 2 if email-reader/namecheap are kept and started).
- Stopped container count: 0.
- Coolify-labeled containers: 0.
- Coolify systemd units: 0.
- Orphan Docker volumes: 0 (or only intentional archives).
- Orphan Docker networks: 0 (post `network prune`).
- `vps-bootstrap-plan.md` reflects SSH+Compose + watchdog (no Coolify install / managed-services sections).
- `vps-captured-state-20260530.txt` exists as the new baseline.
- Disk reclaimed: **~13.9 GB total** (10.88 GB images + 2.824 GB volumes + 186 MB filesystem). Disk usage drops from 38 GB / 108 GB (35 %) to ~24 GB / 108 GB (22 %).
- All 5 AI sysadmin cron jobs still pass post-cleanup (proactive-check, morning-report, weekly-security, weekly-maintenance, monthly-backup-verify).

---

## What's NOT in this plan (deferred or rejected)

| Item | Why |
| --- | --- |
| `fabrik bootstrap-vps` CLI command | `vps-bootstrap-plan.md` exists; turning it into a CLI command is a separate effort. v1 stays as a shell-script-driven plan. |
| `fabrik audit-infra` drift detection | AI sysadmin's `/opt/fabrik/scripts/sysadmin/proactive-check.sh` already runs every 15 min — adding another drift mechanism is duplicate. |
| Removing Alpine `postgres-main` | Owner directive: infra is good. |
| Replacing `vps-sysadmin-bot.service` with the per-project watchdog | They serve different layers (host-level vs project-level). Both stay. |
| Removing OpenVPN | Active service, ports 1194 open in UFW. Out of scope. |
| Removing `glitchtip` | Active error-tracking service. Out of scope. |

---

## Disclosure — what I missed in earlier drafts of this file

1. **`vps-bootstrap-plan.md` already existed** at `/opt/fabrik/docs/infrastructure/`. I claimed earlier that no bootstrap plan existed; in fact it was sitting on the VPS the whole time. The right move was to UPDATE it, not propose a new one.
2. **`vps-sysadmin-bot.service` already runs Claude Code via systemd** with Telegram bot + 5 cron-driven sysadmin tasks. Host-level AI ops is already live. The watchdog platform is the per-project complement.
3. **Loki + Promtail are running.** I said in P1 and P2 drafts that they weren't in the stack. Wrong both times.
4. **16 orphan volumes, 23 orphan networks, ~3.5 GB orphan images** were never inventoried in earlier drafts. They're cleanup wins I missed.
5. **Timing estimates were 20–50× too high** in all earlier plans. Corrected here and in P2 sub-plan.

Apologies for the iterative discovery. The plan is now grounded in verified state.

---

## Next move

1. **Owner reviews this plan**, confirms scope for Workstreams 4–10 (and re-confirms 1+2 still wanted).
2. On confirm, execute Workstreams 4–8 in one ~10-minute pass (all are scripted, low-risk).
3. Then Workstream 1 (Coolify-residue cleanup) before Watchdog P2 code.
4. Workstreams 9 + 10 (doc updates) any time.
