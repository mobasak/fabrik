# `fabrik vultr` — quick reference

**Last Updated:** 2026-06-08
**Status:** ✅ Live on master (commits `93de0fc` → `963beb7`, 2026-06-08).
**Plan / ground truth:** [`docs/archive/2026-06-07-fabrik-vultr-provisioning.md`](../archive/2026-06-07-fabrik-vultr-provisioning.md) — §J verified API facts, §L per-phase validation gates.

On-demand Vultr VPS — any product line, permanent spokes + disposable drills. Single CLI entrypoint, single state file, always-destroy semantics on drill paths, full unwind on permanent destroy.

---

## CLI surface

`fabrik vultr <cmd>`:

| Command | Purpose |
| :--- | :--- |
| `list` | Tracked instances + drift vs live account |
| `status <name>` | One tracked instance: local state + live Vultr state |
| `reconcile` | Compare local state to live account, print drift both directions |
| `cleanup` | Destroy disposables past `destroy_after` (dry-run default) |
| `drill bare \| spoke \| hub` `[--dry-run --region --max-cost --keep-on-failure]` | Disposable; always self-destroys (try/finally). `bare` = API+SSH smoke (~2m). `spoke` = `bootstrap-vps.sh --skip-mesh --skip-dns + --verify` (~8m, hermetic). `hub` = `bootstrap-hub.sh` (~90m, operator-run) |
| `drill-history` | Tail `logs/dr-drill-history.jsonl` |
| `provision <name>` `[--region --plan --dry-run]` | Permanent fleet member; ⚠️ real billing + mutates vps1 wg0 / DNS / monitoring; interactive confirm required, no `-y`; on bootstrap-fail it **leaves the box** for forensic inspection |
| `destroy <name>` `[--reverse-fleet-add --keep-dns --dry-run -y]` | Permanent needs `--reverse-fleet-add` — unwinds Gatus → Prometheus → Backrest → DNS → wg0 → instance |
| `cost` | Account charges + tracked run-rate |

---

## Programmatic API

```python
from fabrik.drivers.vultr import VultrClient
client = VultrClient()
kind, obj = client.create_instance(...)   # auto-routes vbm-* plans to /v2/bare-metals
client.wait_for_active(kind, obj["id"])   # 4-condition; don't poll status=="active" yourself
```

`wait_for_active` exists because `status == "active"` flips while the instance is still `power_status: stopped` and `server_status: locked` (verified live). Use it; don't reinvent.

---

## Gotchas that will bite you

| Trap | Reality |
| :--- | :--- |
| Auth | `VULTR_API_KEY` + `VULTR_SSHKEY_ID` in `/opt/fabrik/.env.sysadmin` (mode 600). `config.py` does **not** load this file; `VultrClient()` loads it itself. |
| State files | `data/vultr-instances.json` + `logs/dr-drill-history.jsonl` — **both gitignored**, never commit them. |
| Real money | All commands spend within the $305 credit. Drills are cheap ($0.01–0.03) and auto-destroy. Weekly cron `scripts/vultr_weekly_maintenance.sh` cleans orphans. `--max-cost` refuses before create. |
| Spoke naming | Names must match `^vps[0-9]+$`. Mesh IP is deterministic `10.99.0.N`. `next_free_spoke()` consults vps1's live `wg0` so it skips the real vps2 / vps3. |
| Defaults | Region `lax`, `os_id 2284` (Ubuntu 24.04). `vdc` returns 0 plans (not offered by Vultr). |
| Tests + ground truth | 36 unit tests under [`tests/drivers/test_vultr_*.py`](../../tests/drivers/) + [`tests/orchestrator/test_vultr_*.py`](../../tests/orchestrator/). `drill bare` + `drill spoke` live-proven end-to-end, zero orphans. |
| Commit hygiene | Don't `git add -A` — there's unrelated WIP in the tree. Stage surgically. |

---

## What this **does not** close on its own

- **`drill spoke`** uses `--skip-mesh --skip-dns` (hermetic by design). The mesh + DNS + monitoring fleet-add path that the real disaster would hit lives in `provision`, which mutates vps1 and can't be drilled hermetically.
- **Hub DR end-to-end with B2 restore** — `drill hub` ships but the full "vps1 dies → fresh droplet → bootstrap-hub.sh → restore from B2 → 31 containers green → DNS cut over → Gatus green" wall-clock has never been measured. Tracked as a "Now" tier item in [`STRATEGIC_BACKLOG.md`](../STRATEGIC_BACKLOG.md).
- **B2 restore in any drill** — drills don't pull from B2. Bootstrap path only.
- **Prometheus aro-wake target registration** — `provision` brings the spoke up but does NOT add it to vps1's `prometheus.yml` `aro-wake` job. Live verification of vps4 (2026-06-08): 14 active targets before + after provision. Add the spoke's `10.99.0.N:8201` target manually + SIGHUP, or extend `provision` to do it.
- **Gatus endpoint** — same as above. Bootstrap doesn't write `/opt/monitoring/configs/gatus/apps/aro-wake-vpsN.yaml` on vps1. Add manually or extend `provision`.

## Live-run measurements (vps4 drill, 2026-06-08)

End-to-end provision → destroy of a real billed test spoke (`fabrik vultr provision vps4 -y` → `fabrik vultr destroy vps4 --reverse-fleet-add -y`). Drove out 4 real bugs in the process — see "What broke + what we fixed" below.

| Phase | Wall-clock | Cost |
| :--- | :--- | :--- |
| Vultr create → instance active + IP assigned | 60–70s | — |
| sshd ready after `wait_for_active` returns | 10–25s (post-fix; hung indefinitely pre-fix) | — |
| `bootstrap-vps.sh` end-to-end (15 steps: SSH harden, UFW+fail2ban, Docker, Wireguard, mesh peer reg, DNS, monitoring, Traefik, sysadmin pack, aro-wake) | ~4m 36s | — |
| `destroy --reverse-fleet-add` (gatus → prom → backrest → DNS → wg0 → instance) | ~24s | — |
| **Round-trip total** (provision + destroy, no debugging) | **~5–6 min** | **~$0.06** (vc2-2c-4gb @ $24/mo × 10/(30×24×60)) |

Fleet-add **verified live** after provision:

- ✅ Mesh: vps1 ↔ vps4 over wg0, `ping 10.99.0.4` = 1.25ms
- ✅ DNS: `vps4.ocoron.com` + `*.vps4.ocoron.com` → 45.77.68.63 (via Cloudflare auth NS)
- ✅ Loki: host label `vps4` present, promtail shipping logs from vps4
- ✅ Traefik: container up, gzip middleware published
- ✅ aro-wake systemd unit installed
- ❌ Prometheus aro-wake job: vps4 NOT added (14 → 14 targets) — gap noted above

## What broke + what we fixed (drill #2 — 2026-06-08)

The drill caught 4 real bugs that the unit tests had not surfaced. All four were fixed in the same session and the live drill validated the fixes:

1. **`fabrik vultr provision` had no `-y/--yes` flag**, so `click.confirm("Proceed?")` read from `/dev/tty` and hung when piped. Added `-y` flag with explicit "automation use only" doc string.
2. **DNS driver defaulted to the dead `coolify` docker network**, breaking `--reverse-fleet-add` DNS unwind in a fresh operator environment that hadn't set the env override. Changed default to `fabrik` (the post-Coolify network). +3 unit tests in [`tests/drivers/test_dns_client.py`](../../tests/drivers/test_dns_client.py).
3. **`provision` had no sshd-ready poll** between `wait_for_active` (Vultr-API "active") and the bootstrap call. There's a 10–30s gap where Vultr reports active but cloud-init hasn't bound sshd — bootstrap-vps.sh's BatchMode preflight failed on the first try. Added `_wait_for_ssh()` polling up to 120s. +1 regression test.
4. **`bootstrap-vps.sh` step_02 aborted on `sudo ufw enable`**: kernel reloads the netfilter ruleset and the active SSH session drops with rc=255 (benign — port 22 is allowed and the next session connects fine), but `set -euo pipefail` killed the whole bootstrap. Added `|| true` + a 2s settle + a fresh-session re-probe via the verify block. Result: step_02 completed cleanly on the next run.

Also surfaced (NOT yet fixed — recorded for follow-up):

- **`bootstrap-vps.sh` step_04 silently removes ufw** on Ubuntu 24.04 because `iptables-persistent` conflicts with ufw at the firewall-management layer. step_15's aro-wake UFW rules then fail (`sudo: ufw: command not found`). vps2/vps3 don't hit this because they were bootstrapped pre-conflict.
- **`reverse_fleet_destroy` wg0 peer removal used invalid `wg set wg0 peer-remove-by-ip <ip>` syntax** (no such subcommand). Silently failed under `|| true` and reported "ok" — leaving a stale peer behind on vps1's wg0 after destroy. Verified live on vps4: peer still present after `destroy --reverse-fleet-add` succeeded. Fixed: look up the pubkey by allowed-ip match, then `wg set wg0 peer <pubkey> remove`.
- **`reverse_fleet_destroy` DNS step returns false-negative** when site-provisioner replies 500 for "record not found" — DNS records are actually removed, but `_try` records `error`. Cosmetic; cleanup is correct.
