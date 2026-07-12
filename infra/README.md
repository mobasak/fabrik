# `infra/` — per-VPS deployment compose extracts (3-host fleet)

Reference copies of the Docker Compose files deployed on each fleet host, organised
by VPS. **Pulled from the live `/opt/<svc>/compose.yaml` on each host on 2026-06-17.**

- **Source of truth is the live host** (`/opt/<svc>/compose.yaml`), deployed/managed
  by `fabrik apply` (hub services) and `bootstrap-vps.sh` (spoke agents). Nothing
  deploys *from* `infra/` — it's a source-controlled mirror for review/DR reference.
- **No secrets here.** Every service externalises credentials via `env_file: .env`,
  `${VAR}` references, or mounted secret files (e.g. `.restic-password`) — never inline.
- All services run on the external **`fabrik`** Docker network (renamed from `coolify`
  2026-05-31; `fabrik apply` rejects a compose declaring `coolify`).
- Canonical *live* fleet state (counts, health, drift): [`docs/infrastructure/vps-complete-inventory.md`](../docs/infrastructure/vps-complete-inventory.md) and [`vps-urls.md`](../docs/infrastructure/vps-urls.md).

## Layout

```
infra/
├── vps1/   # hub  — LA            (172.93.160.197, mesh 10.99.0.1) — 16 services
├── vps2/   # spoke — Coventry UK  (mesh 10.99.0.2)                 — 3 services
└── vps3/   # spoke — Coventry UK  (mesh 10.99.0.3)                 — 3 services
```

## vps1 (hub) — 16 compose stacks

`apprise`, `authelia`, `backrest`, `browserless`, `gatus`, `glitchtip`, `gotenberg`,
`meilisearch`, `monitoring` (Prometheus + Grafana + Loki + Promtail + Alertmanager +
node-exporter + cAdvisor + pushgateway + exporters), `n8n`, `ocoron-com` (the live
WordPress site — wordpress/db/redis/nginx/backup), `postgres` (shared `postgres-main`),
`redis` (shared `redis-main`), `site-provisioner` (the one Fabrik-authored microservice),
`traefik`.

> `aro-wake` (`:8201`) and the AI sysadmin run as **systemd** units on vps1, not Compose
> stacks, so they are not under `infra/`. `watchdog-test` is included as a compose stack.
>
> **Boot resilience (ALL hosts):** `fabrik-compose-boot.service` (a root oneshot, `After=docker.service`)
> reconciles every `/opt/*/compose.yaml` stack to running on boot — closing the Docker
> `restart: unless-stopped` reboot race that left vps1 `alertmanager` down 4 days on 2026-07-08. Source +
> installer: `scripts/systemd/{fabrik-compose-boot.sh,fabrik-compose-boot.service,install-compose-boot.sh}`;
> spokes get it from `bootstrap-vps.sh` step 16. See `scripts/systemd/README.md` and
> `docs/TROUBLESHOOTING.md` § "container stays down after a host reboot".

## vps2 / vps3 (spokes) — 3 compose stacks each

Symmetric agent set, owned by `bootstrap-vps.sh` (NOT tenants of `fabrik apply`):

- **`monitoring-agent`** — node-exporter + cAdvisor + promtail, `network_mode: host`,
  listeners bound to the host's **mesh IP** (`10.99.0.2` / `10.99.0.3`) so vps1's
  Prometheus scrapes them over WireGuard; promtail pushes logs to Loki at `10.99.0.1`.
- **`backrest`** — per-spoke restic backups to Backblaze B2 (no public UI; managed via
  API from vps1 over the mesh).
- **`traefik`** — local reverse proxy + the `gzip@docker` middleware definition.

The two spokes are identical apart from the mesh IP (`.2` vs `.3`) and `hostname`.
