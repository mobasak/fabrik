# `fabrik vultr` — quick reference

**Last Updated:** 2026-06-15
**Status:** ✅ Live on master. Spoke-restore B2 drill green + LE/DNS cutover validated end-to-end (commit `52988ac`, 2026-06-15); provision now auto-registers Prometheus + Gatus + spoke sysadmin.
**Historical plan (archived):** [`docs/archive/2026-06-07-fabrik-vultr-provisioning.md`](../archive/2026-06-07-fabrik-vultr-provisioning.md) — the build-era plan (§J API facts as verified then, §L phase gates); current truth is THIS doc + `src/fabrik/orchestrator/vultr_*.py`. Drill retrospectives: [`docs/archive/fabrik-vultr-drill-retros.md`](../archive/fabrik-vultr-drill-retros.md).

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
| `drill bare \| spoke \| hub \| spoke-restore` `[--dry-run --region --max-cost --keep-on-failure --g0-smoke]` | Disposable; always self-destroys (try/finally). `bare` = API+SSH smoke (~2m). `spoke` = `bootstrap-vps.sh --skip-mesh --skip-dns + --verify` (~8m, hermetic). `hub` = `bootstrap-hub.sh` (~90m, operator-run). `spoke-restore` = `scripts/bootstrap/bootstrap-spoke-restore.sh` against the latest spoke B2 snapshot (~1h) — the real B2-restore DR path |
| `drill-history` | Tail `logs/dr-drill-history.jsonl` |
| `provision <name>` `[--region --plan --dry-run -y]` | Permanent fleet member; ⚠️ real billing + mutates vps1 wg0 / DNS / monitoring; interactive confirm by default — `-y/--yes` skips it (automation only, still bills + mutates); on bootstrap-fail it **leaves the box** for forensic inspection |
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
| Real money | All commands spend within the $305 credit. Drills are cheap ($0.01–0.03) and auto-destroy. `scripts/vultr_weekly_maintenance.sh` cleans orphans — **not currently scheduled**; install it in crontab (`0 7 * * 1 …`, per its header) to automate. `--max-cost` refuses before create. |
| Spoke naming | Names must match `^vps[0-9]+$`. Mesh IP is deterministic `10.99.0.N`. `next_free_spoke()` consults vps1's live `wg0` so it skips the real vps2 / vps3. |
| Defaults | Region `lax`, `os_id 2284` (Ubuntu 24.04). `vdc` returns 0 plans (not offered by Vultr). |
| Tests + ground truth | 63 unit tests across 5 files under [`tests/drivers/test_vultr_*.py`](../../tests/drivers/) + [`tests/orchestrator/test_vultr_*.py`](../../tests/orchestrator/). `drill bare` + `drill spoke` live-proven end-to-end, zero orphans. |
| Commit hygiene | Don't `git add -A` — there's unrelated WIP in the tree. Stage surgically. |

---

## What this **does not** close on its own

- **`drill spoke`** uses `--skip-mesh --skip-dns` (hermetic by design). The mesh + DNS + monitoring fleet-add path that the real disaster would hit lives in `provision`, which mutates vps1 and can't be drilled hermetically.
- **B2 restore is now drilled** — `drill spoke-restore` runs `scripts/bootstrap/bootstrap-spoke-restore.sh` against the latest live spoke B2 snapshot. Green end-to-end 2026-06-15. (Closes the old "drills don't pull from B2" gap.)
- **LE / DNS cutover is now VALIDATED** — `bootstrap-hub.sh --drill-test-le-staging` + `step_17b` acquired a real Let's Encrypt **staging** cert end-to-end via the `tojlo.com` sandbox zone (commit `52988ac`, 2026-06-15): DNS rewrite green (`dr-drill-hub-20260615-154530`), ACME-staging cert green (`dr-drill-hub-20260615-160819`). The HTTP-01 challenge against rewritten DNS works; the prod-cert cutover differs only in the ACME endpoint flag.
- **Hub DR** — the unified `fabrik vultr drill hub` (one `bootstrap-hub.sh` run bundling `--cf-rewrite-dns --drill-test-le-staging --drill-start-core-only`) went **GREEN 2026-06-15** (`dr-drill-hub-20260615-111639`; restore-heavy path 5m46s — see `docs/operations/disaster-recovery.md`). Honest residual: the drill runs `--skip-services`, so the full compose-up "all containers green" wall-clock is still not measured as one continuous run. Tracked in [`STRATEGIC_BACKLOG.md`](../STRATEGIC_BACKLOG.md).
- **Observability fleet-add is now automatic** — `provision` calls `vultr_provision.py::_register_observability` (line 337/350) which registers the spoke's `aro-wake` Prometheus target + Gatus endpoint on vps1 (best-effort; failures land under `report['observability']`, don't fail the provision). PR3 also auto-installs the spoke's AI sysadmin via `_provision_sysadmin`. (Closes the old vps4-drill 14→14-targets gap.)
