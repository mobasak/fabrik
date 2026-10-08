# Alloy Log Noise Filter — Setup

**Last Updated:** 2026-10-08 (renamed from its Promtail-named predecessor and rewritten for Grafana Alloy, the
log shipper's successor — spec `docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md` § The delta ›
D1–D3). **History (2026-07-20):** the Promtail-era drop filter was re-verified as the single-entry regex
`^ocoron-com-backup-1$` — the four dead `coolify-*` entries were cleaned in commit `05b93197`, 2026-06-17; vps1
container count corrected 28→31. **Prior 2026-06-06:** aro-wake on full fleet writes to host journald +
`/var/log/aro-wake.log` — those aren't shipped by the shipper's file-tailing discovery, so no aro-wake noise
filter is needed. Each host's Loki ingest stream for `host="vpsN"` will not include aro-wake-internal logs;
operators read those locally via `sudo tail /var/log/aro-wake.log`.
**Status:** ✅ Live on vps1. Alloy's `stage.drop` carries the same single-entry regex the Promtail config carried
(`configs/alloy/config.alloy`) — no behavior change intended by the shipper swap (spec D1: the committed config
is the converter's own output, no hand edits). Spoke-side Alloy containers run at `/opt/monitoring-agent/` on
vps2/vps3 and push logs to `loki:3100` via mesh. The Prometheus job `alloy` (hub + both spokes, `prometheus.yml`
job `alloy`, 3 targets) scrapes the shipper's own `/metrics` on all three hosts — unlike Promtail's old
`promtail-spokes` job, Alloy's hub instance is scraped too, not just the spokes (spec D3).
**Container:** `alloy` (stable name; was `promtail` — `promtail` stays **defined** under the `rollback` profile,
stopped, until Gate S, spec D6)
**Config:** `/opt/monitoring/configs/alloy/config.alloy` (host bind mount, repo mirror `configs/alloy/config.alloy`)
**Spoke Alloys:** `vps2`, `vps3` — rendered by `scripts/bootstrap/bootstrap-vps.sh` step 11 (different config, see
§ Multi-host)

---

## Goal

Alloy's `loki.source.file` component by default tails every Docker container log under
`/var/lib/docker/containers/*/*log` and ships them all to Loki. Some containers produce only Docker-daemon noise
with no actionable signal — the WordPress backup sidecar's cron loop is the classic example post-Coolify. A
`stage.drop` block in Alloy's `loki.process` pipeline filters these by container name before shipping, reducing
Loki ingestion volume + query noise.

The original Promtail-era filter set (2026-05-08) included Coolify-internal containers (`coolify-db`,
`coolify-redis`, `coolify-realtime`, `coolify-sentinel`) — Coolify itself was removed on 2026-05-30, so those
four containers no longer exist. Those four entries were removed from the Promtail config (commit `05b93197`,
2026-06-17), leaving the single-entry regex `^ocoron-com-backup-1$` that `alloy convert` carried straight into
`configs/alloy/config.alloy` (spec D1 — the converter's output is committed with no hand edits).

## Prerequisites

- **Docker daemon must emit container name in log attrs.** Requires `"tag": "{{.Name}}"` in `/etc/docker/daemon.json` under `log-opts`. Without this, Docker's default JSON log driver does NOT include `attrs.tag`, the `container_name` label is never extracted, and the drop filter silently does nothing. Alloy's `stage.json`/`stage.regex` pair extracts it exactly the way Promtail's did (same expressions, `configs/alloy/config.alloy`).
- Alloy running on vps1 from `/opt/monitoring/compose.yaml`
- Config volume bind-mounted from host to container at `/etc/alloy/config.alloy`
- Loki running and reachable at `http://loki:3100` from the `fabrik` network

### Docker daemon.json (required on every host)

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3",
    "tag": "{{.Name}}"
  }
}
```

After changing `daemon.json`: `systemctl restart docker`. **Existing containers must be recreated** (restart alone keeps the old log format) — `docker compose up -d --force-recreate` for each compose project. New containers automatically get the tag.

On spokes (vps2/vps3), `bootstrap-vps.sh` step 03 emits `daemon.json` with the `tag: "{{.Name}}"` field since 2026-06-02 (W4 pre-step). The previously-flagged gap is closed — spoke logs now carry the `container_name` label in Loki same as vps1. The existing vps2 + vps3 had docker restarted as part of W4-pre (2026-06-02), so the new tag applies to all running spoke containers immediately, and any spoke provisioned via `bootstrap-vps.sh` going forward gets it on first bootstrap.

## Reproducible Setup (vps1)

### 1. Write the Alloy config to host

This is the committed `configs/alloy/config.alloy` — `alloy convert`'s own output, no hand edits (spec D1):

```bash
ssh vps "sudo tee /opt/monitoring/configs/alloy/config.alloy > /dev/null << 'ALLOY'
loki.process \"containers\" {
	forward_to = [loki.write.default.receiver]

	stage.json {
		expressions = {
			attrs  = \"\",
			output = \"log\",
			stream = \"stream\",
		}
	}

	stage.json {
		expressions = {
			tag = \"\",
		}
		source = \"attrs\"
	}

	stage.regex {
		expression = \"(?P<container_name>(?:[a-zA-Z0-9][a-zA-Z0-9_.-]+))\"
		source     = \"tag\"
	}

	stage.labels {
		values = {
			container_name = null,
			stream         = null,
		}
	}

	stage.drop {
		source     = \"container_name\"
		expression = \"^ocoron-com-backup-1\$\"
	}

	stage.output {
		source = \"output\"
	}
}

loki.source.file \"containers\" {
	targets = [{
		__address__ = \"localhost\",
		__path__    = \"/var/lib/docker/containers/*/*log\",
		host        = \"vps1\",
		job         = \"containerlogs\",
	}]
	forward_to = [loki.process.containers.receiver]

	file_match {
		enabled = true
	}
	legacy_positions_file = \"/run/promtail/positions.yaml\"
}

loki.write \"default\" {
	endpoint {
		url = \"http://loki:3100/loki/api/v1/push\"
	}
	external_labels = {}
}
ALLOY"
```

### 2. Reload Alloy

Alloy does not hot-reload a component-level change like this one; it must be restarted:

```bash
ssh vps "sudo docker restart alloy"
```

### 3. Verify the filter is applied

Confirm zero startup errors:

```bash
ssh vps 'sudo docker logs alloy --tail 20 2>&1 | grep -iE "error|level=err"'
```

Expected: no output (silent = healthy). Also check readiness and metrics directly — `/-/ready` and `/metrics` are the two Alloy endpoints the Prometheus `alloy` job and Gatus scrape (spec D3, V8):

```bash
ssh vps 'sudo docker exec alloy wget -qO- http://localhost:12345/-/ready'
```

Confirm the filtered container no longer appears in Loki:

```bash
ssh vps 'sudo docker exec prometheus wget -qO- "http://loki:3100/loki/api/v1/label/container_name/values"' \
  | python3 -m json.tool
```

The `container_name` values list should NOT include `ocoron-com-backup-1` (the only container the filter matches; the regex has a single entry, `^ocoron-com-backup-1$`).

## How to Add or Remove Filtered Containers

Edit the `expression` in the `stage.drop` block — the pattern is a pipe-separated list of exact container names anchored with `^` and `$` (HCL string, so no backslash before the trailing `$`):

```hcl
stage.drop {
	source     = "container_name"
	expression = "^(name1|name2|name3)$"
}
```

After editing, restart Alloy:

```bash
ssh vps "sudo docker restart alloy"
```

## Containers Currently Kept (Not Filtered)

On vps1, that's all 31 running containers minus `ocoron-com-backup-1` (the only container the drop filter matches — the regex's single entry). Full list in `docs/infrastructure/vps-complete-inventory.md § vps1 container inventory`.

## Why `ocoron-com-backup-1` Is Filtered

The WordPress backup sidecar runs a cron-style loop that logs heartbeat lines every minute. Zero actionable signal; pure noise that takes up Loki retention budget. If backup failures need to be surfaced, route them through `apprise` or a Prometheus alert on `wp_backup_last_success` (would need to be added) rather than via log scraping.

## Multi-host

### Spoke Alloys

vps2 and vps3 each run an Alloy container deployed by `scripts/bootstrap/bootstrap-vps.sh` step 11. Their config lives at `/opt/monitoring-agent/alloy.alloy` on each spoke and is rendered from `scripts/bootstrap/templates/alloy.alloy.template` at bootstrap time.

Key differences from vps1's Alloy:

| Aspect | vps1 Alloy | Spoke Alloy |
| :--- | :--- | :--- |
| Loki target | `http://loki:3100` (local Docker DNS) | `http://{{HUB_MESH_IP}}:3100` (over mesh) |
| `host` label | `vps1` | `{{SPOKE_NAME}}` (`vps2` or `vps3`) |
| `--server.http.listen-addr` | `0.0.0.0:12345` (Docker network, `fabrik`, no host port) | `{{SPOKE_MESH_IP}}:12345` (mesh-only, `network_mode: host`) |
| Drop filter | yes — `^ocoron-com-backup-1$` (`stage.drop`, `configs/alloy/config.alloy`) | no (`scripts/bootstrap/templates/alloy.alloy.template` carries no `stage.drop` — spokes don't have tenants yet) |
| Memory ceiling | 256M (`infra/vps1/monitoring/compose.yaml`) | 128M (`monitoring-agent.compose.yaml.template`, spec D5) |

When a spoke's first tenant ships and starts producing noisy logs, add a `stage.drop` to the spoke's `alloy.alloy.template` the same way the hub's is written. Restart that spoke's Alloy: `ssh vpsN 'cd /opt/monitoring-agent && sudo docker compose restart alloy'`.

### Cross-host log queries in Grafana

The `host` label is set on every Loki stream — `vps1` / `vps2` / `vps3`. So:

```logql
{host="vps2"}                            # all logs from vps2
{host="vps2", container_name="n8n"}     # n8n logs on vps2
{host=~"vps[23]"}                        # both spokes
```

Drop filters apply per-host — vps1's drop filter does NOT remove `ocoron-com-backup-1` from spokes (it doesn't exist there). Each spoke's Alloy is independently configured.

## Troubleshooting

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| Logs from filtered container still appearing in Grafana/Loki | Alloy wasn't restarted | `sudo docker restart alloy` (or spoke equivalent) |
| Alloy logs show a config parse error | HCL syntax error (often a stray brace or quote) | `docker run --rm -v /opt/monitoring/configs/alloy:/etc/alloy:ro grafana/alloy:v1.20.1 fmt /etc/alloy/config.alloy` to lint, or `alloy run` in a disposable container (spec V2) |
| Container missing from Loki entirely (filter too broad) | `stage.drop` regex matches more than intended | Test the regex with `echo 'name' \| grep -E 'pattern'` first |
| `container_name` label is empty in Loki | Docker log tag format not configured | Confirm `daemon.json` has `"tag": "{{.Name}}"` under `log-opts`; recreate containers (`docker compose up -d --force-recreate`) |
| Spoke logs missing `container_name` label | bootstrap-vps.sh's daemon.json lacks the `tag` field | Edit `daemon.json` on the spoke and recreate containers; or update the bootstrap template |
| No logs from a spoke arrive at vps1 Loki | Loki isn't bound to mesh IP, or wg0 down on spoke, or firewall blocks | Check `ssh vps "sudo ss -tlnp \| grep 10.99.0.1:3100"`; mesh ping `ssh vpsN ping 10.99.0.1` |
| `/-/ready` or `/metrics` on `:12345` doesn't answer | Alloy container down, or the Prometheus `alloy` job is stale | `docker ps` for the `alloy` container; `prometheus.yml` job `alloy` targets `alloy:12345` (hub) + `10.99.0.2:12345` + `10.99.0.3:12345` (spec D3, V8) |

## Rollback

Until Gate S (spec D6: V8 + V9 green on all three hosts for 14 days), `promtail` stays **defined** under the
`rollback` profile in each host's compose file — stopped, never started by `docker compose up -d
--remove-orphans`, but restorable with `cp compose.yaml.pre-alloy compose.yaml && docker compose up -d
--remove-orphans`. A rolled-back host resumes Promtail's old config at `configs/promtail/promtail-config.yaml`
(documented, before the Alloy rename, in this doc's Promtail-named predecessor) and re-ships log lines Alloy
already sent since the switch (spec D6 — the duplicate span is bounded by how long Alloy ran before the
rollback).

## References

- Alloy `loki.process` component reference (the `stage.drop` block): <https://grafana.com/docs/alloy/latest/reference/components/loki/loki.process/>
- Alloy `loki.source.file` component reference: <https://grafana.com/docs/alloy/latest/reference/components/loki/loki.source.file/>
- Sister doc: [`grafana-dashboards-setup.md`](grafana-dashboards-setup.md) (Loki dashboards + host filter)
- Bootstrap script: [`scripts/bootstrap/bootstrap-vps.sh`](../../scripts/bootstrap/bootstrap-vps.sh) step 11 + [`templates/alloy.alloy.template`](../../scripts/bootstrap/templates/alloy.alloy.template)
- Design spec: [`docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md`](../superpowers/specs/2026-10-05-promtail-to-alloy-design.md)
