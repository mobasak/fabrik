# Fabrik Development Dashboard

**Last Updated:** 2026-03-24

> **⚠️ SUPERSEDED (flagged 2026-06-16).** This is a frozen 2026-03 snapshot tracking
> the original 8-phase build plan (now essentially complete; the phase docs it links
> live under `docs/development/plans/previously-planned-fabrik-phases/`, kept as
> history). The **Phase Status** and **VPS Services** tables below are NOT current —
> several listed services (Coolify, Netdata, Image Broker, DNS Manager, Translator,
> Captcha, Email Gateway, Proxy, MinIO, File API, WordPress Test) are retired/not
> deployed. For live state use the canonical sources: **`PORTS.md`** (ports),
> **`AGENTS.md` § VPS Infra / Microservices** (services), **`docs/infrastructure/vps-status.md`**
> (fleet), and **`CHANGELOG.md`** (what shipped). Don't drive new work from this file.

---

## Current Focus

| Priority | Task | Phase Doc |
|----------|------|-----------|
| 🔴 1 | Deploy ocoron.com (multilingual) | [Phase2.md](docs/development/plans/previously-planned-fabrik-phases/Phase2.md) |
| 🟡 2 | Build preset loader | [Phase2.md](docs/development/plans/previously-planned-fabrik-phases/Phase2.md) |
| 🟡 3 | Create custom themes | [Phase2.md](docs/development/plans/previously-planned-fabrik-phases/Phase2.md) |

---

## Phase Status

| Phase | Name | Status | Doc |
|-------|------|--------|-----|
| 1 | Foundation | ✅ Complete | [Phase1.md](docs/development/plans/previously-planned-fabrik-phases/Phase1.md) |
| 1b | Cloud Infrastructure | ✅ Complete | [Phase1b.md](docs/development/plans/previously-planned-fabrik-phases/Phase1b.md) |
| 1c | Cloudflare DNS | ✅ Complete | [Phase1c.md](docs/development/plans/previously-planned-fabrik-phases/Phase1c.md) |
| 1d | AI Agent Integration | ✅ Complete | [Phase1d.md](docs/development/plans/previously-planned-fabrik-phases/Phase1d.md) |
| 2 | WordPress Automation | ⚡ 67% | [Phase2.md](docs/development/plans/previously-planned-fabrik-phases/Phase2.md) |
| 3 | AI Content Integration | ✅ Complete | [Phase3 context](docs/archive/2026-03-01-kilo-enhancement-context/2026-02-28-phase3-context.md) |
| 4 | DNS + Networking | ✅ Done in P1c | [Phase4.md](docs/development/plans/previously-planned-fabrik-phases/Phase4.md) |
| 5 | Staging + Multi-Env | ❌ Blocked (needs P2) | [Phase5.md](docs/development/plans/previously-planned-fabrik-phases/Phase5.md) |
| 6 | Advanced Monitoring | ✅ Complete | [Phase6 context](docs/archive/2026-03-01-kilo-enhancement-context/2026-02-28-phase6-context.md) |
| 7 | Multi-Server Scaling | ❌ Not Started | [Phase7.md](docs/development/plans/previously-planned-fabrik-phases/Phase7.md) |
| 8 | Business Automation | ✅ Complete | [Phase8 context](docs/archive/2026-03-01-kilo-enhancement-context/2026-02-28-phase8-context.md) |
| 9 | Docker Acceleration | ✅ Complete | [Phase9 context](docs/archive/2026-03-01-kilo-enhancement-context/2026-02-28-phase9-context.md) |
| 10 | Deployment Orchestrator | 🟡 In Design | [Phase10.md](docs/development/plans/previously-planned-fabrik-phases/Phase10.md) |

---

## VPS Services

| Service | URL | Status |
|---------|-----|--------|
| Coolify | vps1.ocoron.com:8000 | ✅ |
| Netdata | netdata.vps1.ocoron.com | ✅ |
| Gatus | status.vps1.ocoron.com | ✅ |
| Backrest | backup.vps1.ocoron.com | ✅ | (replaced Duplicati 2026-04-17)
| Image Broker | images.vps1.ocoron.com | ✅ |
| DNS Manager | dns.vps1.ocoron.com | ✅ |
| Translator | translator.vps1.ocoron.com | ✅ |
| Captcha | captcha.vps1.ocoron.com | ✅ |
| File API | files-api.vps1.ocoron.com | ✅ |
| Email Gateway | emailgateway.vps1.ocoron.com | ✅ |
| Proxy API | proxy.vps1.ocoron.com | ✅ |
| WordPress Test | wp-test.vps1.ocoron.com | ✅ |
| Browserless | browser.vps1.ocoron.com | ✅ |
| Gotenberg | pdf.vps1.ocoron.com | ✅ |
| MinIO | s3.vps1.ocoron.com | ✅ |
| Apprise | notify.vps1.ocoron.com | ✅ |
| Meilisearch | search.vps1.ocoron.com | ✅ |
| Grafana | monitor.vps1.ocoron.com | ✅ |
| n8n | auto.vps1.ocoron.com | ✅ |

---

## Update Protocol

When completing any task:

1. Update the **phase doc** (checkboxes, status)
2. Update this **dashboard** (phase status table)
3. Update **CHANGELOG.md** (code changes)

See: [Documentation Rules](.windsurf/rules/core/40-documentation.md)
