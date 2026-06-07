# `fabrik vultr` — quick reference

**Last Updated:** 2026-06-08
**Status:** ✅ Live on master (commits `93de0fc` → `963beb7`, 2026-06-08).
**Plan / ground truth:** [`docs/development/plans/2026-06-07-fabrik-vultr-provisioning.md`](../development/plans/2026-06-07-fabrik-vultr-provisioning.md) — §J verified API facts, §L per-phase validation gates.

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

- **`drill spoke`** uses `--skip-mesh --skip-dns` (hermetic by design). The mesh + DNS + monitoring fleet-add path that the real disaster would hit lives in `provision`, which mutates vps1 and can't be drilled hermetically. Closing that gap requires a real `fabrik vultr provision vps4` test run + measure + `destroy vps4 --reverse-fleet-add` — covered as an "Now" tier item in [`STRATEGIC_BACKLOG.md`](../STRATEGIC_BACKLOG.md).
- **Hub DR end-to-end with B2 restore** — `drill hub` ships but the full "vps1 dies → fresh droplet → bootstrap-hub.sh → restore from B2 → 31 containers green → DNS cut over → Gatus green" wall-clock has never been measured. Also a "Now" tier item.
- **B2 restore in any drill** — drills don't pull from B2. Bootstrap path only.
