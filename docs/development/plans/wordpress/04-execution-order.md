# Execution Order — What to Build When

## Dependency Chain

```
[1] FABRIK_EXEC_MODE=local (1-line fix)
 ↓
[2] Golden Base Image (build + test)
 ↓
[3] fabrik-api (FastAPI bridge on VPS)
 ↓
[4] fabrik wp create --one-command (scaffold + plan + apply)
 ↓
[5] GUI Wizard (Next.js, uses fabrik-api)
 ↓
[6] VPS Cron for content (daily fabrik content publish)
 ↓
[7] Watchdog AI (agent managing all sites)
```

## Phase 1 — Foundation (make existing pipeline work from VPS)

| Ticket | What | Effort | Depends on |
|---|---|---|---|
| 1.1 | Implement `FABRIK_EXEC_MODE=local` in `src/fabrik/drivers/wordpress.py` | 1 hour | Nothing |
| 1.2 | Fix ocoron.com spec (WPML→Polylang, fill remaining fields) | 2 hours | Nothing |
| 1.3 | Fix `docs/reference/wordpress/deployment-workflow.md` (Apache→FPM references) | 30 min | Nothing |
| 1.4 | Deploy ocoron.com via pipeline (`fabrik wp plan + apply`) | 1 hour | 1.1 + 1.2 |
| 1.5 | Set up content cron: `0 3 * * * fabrik content publish ocoron.com --limit 2` | 30 min | 1.4 |
| 1.6 | Register ocoron.com in SEO service + create first keyword jobs | 1 hour | 1.4 |

**Result:** ocoron.com live via pipeline, content publishing daily.

## Phase 2 — Golden Base (make new sites instant)

| Ticket | What | Effort | Depends on |
|---|---|---|---|
| 2.1 | Create `templates/wordpress/golden/Dockerfile` | 4 hours | Phase 1 complete |
| 2.2 | Create `scripts/build_golden_base.sh` (build + tag + push to local registry) | 1 hour | 2.1 |
| 2.3 | Update `templates/wordpress/base/compose.yaml.j2` to use golden image | 1 hour | 2.2 |
| 2.4 | Update `deployer.py` — skip stages 3-4 when golden base detected | 2 hours | 2.3 |
| 2.5 | Update `stages/plugins.py` — only install ADDITIONS beyond base | 1 hour | 2.4 |
| 2.6 | Test: scaffold + plan + apply new site → live in <90 seconds | 2 hours | 2.5 |
| 2.7 | Add `fabrik wp preview` (temp subdomain, auto-delete 7d) + `fabrik wp promote` (move to real domain) | 4 hours | 2.6 |

**Result:** New sites deploy in ~90 seconds. Preview before burning DNS/registrar resources.

## Phase 3 — API Bridge (enable GUI and remote control)

| Ticket | What | Effort | Depends on |
|---|---|---|---|
| 3.1 | `fabrik scaffold fabrik-api --type python-api` | 30 min | Phase 2 |
| 3.2 | Implement endpoints: /health, /sites, /sites/{id}/deploy, /sites/{id}/stream | 8 hours | 3.1 |
| 3.3 | Implement: /sites POST (JSON → site.yaml → plan → apply) | 4 hours | 3.2 |
| 3.4 | Implement: /brand/generate (calls brand-identity-creator) | 2 hours | 3.2 |
| 3.5 | Implement: /sites/{id}/content/publish, /cache/flush, /verify | 3 hours | 3.2 |
| 3.6 | SSE streaming for deploy progress | 4 hours | 3.2 |
| 3.7 | Deploy fabrik-api as systemd service on VPS | 1 hour | 3.6 |
| 3.8 | Expose fabrik-api as MCP server (Claude/Windsurf/Traycer can call directly) | 2 hours | 3.7 |

**Result:** All fabrik operations accessible via authenticated HTTP API + MCP from anywhere.

## Phase 4 — GUI (visual management)

| Ticket | What | Effort | Depends on |
|---|---|---|---|
| 4.1 | `fabrik scaffold fabrik-control-panel --type saas-skeleton` | 30 min | Phase 3 |
| 4.2 | Creation wizard: preset picker → domain → brand → content → integrations → deploy | 16 hours | 4.1 + 3.4 |
| 4.3 | Operations dashboard: all sites list + health + stats | 8 hours | 4.1 + 3.5 |
| 4.4 | Per-site view: health, content, SEO, actions | 8 hours | 4.3 |
| 4.5 | SSE integration: live deploy progress in UI | 4 hours | 3.6 + 4.2 |
| 4.6 | Deploy to Coolify (Authelia-protected admin dashboard) | 2 hours | 4.5 |

**Result:** Full visual control over the WordPress factory.

## Phase 5 — Watchdog AI (autonomous management)

| Ticket | What | Effort | Depends on |
|---|---|---|---|
| 5.1 | Create `src/fabrik/watchdog/` package structure | 2 hours | Phase 3 (needs API) |
| 5.2 | Implement daily cycle: health check + content publish + broken links | 8 hours | 5.1 |
| 5.3 | Implement weekly cycle: GSC analysis + strategy adjustment + report | 12 hours | 5.2 |
| 5.4 | Implement monthly cycle: full audit + competitor analysis + plugin updates | 12 hours | 5.3 |
| 5.5 | Implement escalation logic (act vs report vs ask) | 4 hours | 5.2 |
| 5.6 | Per-site config format (`configs/watchdog/<site>.yaml`) | 2 hours | 5.1 |
| 5.7 | Deploy as VPS cron (daily/weekly/monthly) | 1 hour | 5.5 |
| 5.8 | Test: 7 days hands-off on ocoron.com, verify autonomous operation | ongoing | 5.7 |

**Result:** Sites manage themselves. You review weekly Telegram reports.

## Phase 6 — Scaling & SaaS (when portfolio outgrows VPS1)

| Ticket | What | Effort | Depends on |
|---|---|---|---|
| 6.1 | Create `data/vps-pool.yaml` registry with capacity tracking | 2 hours | Phase 5 running |
| 6.2 | Add `--vps` parameter to `fabrik apply` (site-to-VPS routing) | 4 hours | 6.1 |
| 6.3 | Cross-VPS Grafana dashboard (single pane for all nodes) | 4 hours | 6.2 |
| 6.4 | Add `owner_id` to site registry + fabrik-api endpoints | 2 hours | Phase 3 |
| 6.5 | Multi-user auth layer for GUI (customer login, site filtering) | 8 hours | 6.4 + Phase 4 |
| 6.6 | Billing integration (Paddle/Stripe → site quota) | 12 hours | 6.5 |

**Result:** Factory serves multiple VPS nodes + optionally multiple customers (SaaS mode).

**Trigger:** Start Phase 6 when VPS1 hits 80% RAM utilization or when you want to sell the service.

---

## Total Estimated Effort

| Phase | Hours | Calendar (focused) |
|---|---|---|
| Phase 1 (Foundation) | ~6 hours | 1 day |
| Phase 2 (Golden Base) | ~11 hours | 1.5 days |
| Phase 3 (API Bridge) | ~22 hours | 3 days |
| Phase 4 (GUI) | ~38 hours | 5 days |
| Phase 5 (Watchdog) | ~41 hours | 5 days |
| **Total** | **~118 hours** | **~15 focused days** |

## What You Get at Each Phase

- After Phase 1: ocoron.com live, content flowing daily
- After Phase 2: new sites in 90 seconds via CLI
- After Phase 3: remote control from any device via API
- After Phase 4: visual factory — click and deploy
- After Phase 5: fully autonomous — sites run themselves
