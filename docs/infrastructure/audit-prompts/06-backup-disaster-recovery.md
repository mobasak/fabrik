# 06 — Backup & Disaster Recovery (fleet-wide, per-host)

**Last Updated:** 2026-06-06 (procedure unchanged; today's DR-relevant additions: (a) **hub rebuild** now requires re-applying the spoke↔spoke routing rule `sudo ufw route allow in on wg0 out on wg0` AFTER restore — covered in `vps-hub-rebuild.md` "manual after-step" list; (b) **spoke rebuild** now requires four manual deps before `aro-wake.service`+`vps-sysadmin-bot.service` will start: Node.js 22+Claude Code CLI, `python3-venv` apt, `python-telegram-bot==22.7` pip, `/opt/fabrik/` ownership reset — covered in `vps-spoke-rebuild.md`; (c) **Prometheus monitoring stack** restore must re-deploy `prometheus.yml` with the `aro-wake` scrape job + `alerts.yml` with the `aro_wake` rule group; (d) `/var/lib/aro-wake/pending.jsonl` is in-flight state (24h TTL, 1000-entry cap) — NOT a backup target; (e) per-host aro-wake counters are in-memory and reset on restart by design — `rate()` in PromQL handles this via `_created` timestamps.)
**Run mode:** **per host** for probes; analyze fleet-wide for DR readiness.
**Scope:** Backrest config + B2 reachability + snapshot freshness + DR-store mirror + restore drill state.
**Time budget:** ~10 min probes per host + ~15 min cross-fleet analysis.

---

## Stack context

```text
- Backrest 1.13.0 + restic 0.18.1 on every VPS (W11 shipped 2026-06-01).
- Each VPS has its own restic repo in B2 us-west-004:
  - Hub: s3:.../vps1-ocoron-backup (4 plans: postgres-dumps, docker-volumes,
    opt-configs, host-state)
  - vps2 spoke: s3:.../vps1-ocoron-backup/spokes/vps2/ (2 plans: host-state,
    opt-configs)
  - vps3 spoke: s3:.../vps1-ocoron-backup/spokes/vps3/ (2 plans: host-state,
    opt-configs)
- Restic passwords are immutable post-init (W11 ship caveat — once `restic init` runs against a repo with a password, that password is welded in; rotating means re-initing the repo). Each repo has its own.
- W9 DR mirror: /opt/fabrik/.env + .env.sysadmin + 4 spoke files
  (.env.backrest + .restic-password per spoke) mirrored to private GitHub
  mobasak/fabrik-dr-store via inotify watcher.
- DR scripts:
  - bootstrap-hub.sh — 18 steps, target ≤ 90 min, undrilled.
  - bootstrap-spoke-restore.sh — 13 steps, ≤ 30 min, undrilled.
- Path-preserving bind mounts: /opt, /etc, /usr/local/bin, /root/.ssh,
  /home/ozgur/.ssh, /opt/backrest/.restic-password.
- No failure-notification hook configured in Backrest config.json on any
  host (verified live 2026-06-02: `grep apprise` returns empty on all 3).
  Backup-failure Telegram alerts won't reach the operator. If a hook IS
  later added pointing at `apprise-lcocgs4gs8ksg4g08w40ows8:8000` (the old
  Coolify-era UUID-suffix container name), it would also be broken — fix
  to `apprise:8000` (the stable name).
```

---

## Data collection — RUN PER HOST

```bash
ssh vps bash <<'EOF'    # repeat for vps2, vps3
echo "=== BACKREST CONFIG ==="
sudo cat /opt/backrest/config/config.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'instance: {d.get(\"instance\")}')
plans = d.get('plans', [])
repos = d.get('repos', [])
print(f'plans: {len(plans)}: {[p[\"id\"] for p in plans]}')
print(f'repos: {len(repos)}: {[(r[\"id\"], r[\"uri\"][:60]) for r in repos]}')
# Schedule per plan
for p in plans:
    s = p.get('schedule', {})
    print(f'  {p[\"id\"]}: schedule={s.get(\"cron\")} clock={s.get(\"clock\")}')
"
echo
echo "=== BACKREST CONTAINER STATE ==="
sudo docker ps --filter "name=backrest" --format "{{.Names}} {{.Status}}"
sudo docker logs backrest --since 24h 2>&1 | grep -iE "error|fail" | tail -10
echo
echo "=== RECENT BACKUP OPERATIONS (via local API; auth.disabled=true on spokes, may need creds on hub) ==="
if [ "$(hostname)" = "vps1.ocoron.com" ]; then
    echo "(hub has auth enabled; skip API probe — use UI or inspect oplog.sqlite)"
else
    sudo docker exec backrest sh -c 'wget -qO- --post-data="{\"selector\":{}}" --header="Content-Type: application/json" http://localhost:9898/v1.Backrest/GetOperations 2>/dev/null' | python3 -c "
import json, sys
from collections import Counter
d = json.loads(sys.stdin.read())
ops = d.get('operations', [])
success = Counter()
for o in ops:
    if o.get('operationBackup') is not None and o.get('status') == 'STATUS_SUCCESS':
        success[o.get('planId','?')] += 1
print(f'  successful backup ops per plan: {dict(success)}')
total = sum(success.values()); print(f'  total: {total}')
"
fi
echo
echo "=== /opt/backrest/data SQLITE STATE FILES ==="
sudo ls -la /opt/backrest/data/ 2>&1 | head -10
echo
echo "=== RESTIC PASSWORD FILE PERMISSIONS ==="
sudo ls -la /opt/backrest/.restic-password
echo
echo "=== SCHEDULED CRON / TIMERS for backup tasks ==="
sudo cat /etc/cron.d/* 2>/dev/null | grep -iE "backup|backrest|pg_dump" | head -5
sudo systemctl list-timers --all 2>&1 | grep -iE "backup|pg_dump" | head -5
echo
echo "=== APPRISE HOOK SANITY (will fire on failure?) ==="
sudo grep -A2 "hooks" /opt/backrest/config/config.json | head -10
echo "(any apprise reference here? 2026-06-02 live state: none. If empty, hooks aren't configured — backup-failure alerts won't reach Telegram.)"
echo
echo "=== HOST-SPECIFIC ==="
if [ "$(hostname)" = "vps1.ocoron.com" ]; then
    echo "Hub: pg_dumpall cron output:"
    sudo ls -la /opt/backups/ 2>&1 | head -5
    echo "Hub-specific path coverage (per opt-configs plan):"
    sudo cat /opt/backrest/config/config.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
for p in d.get('plans', []):
    paths = p.get('paths', [])
    print(f'  {p[\"id\"]}: {len(paths)} paths')
"
else
    echo "Spoke: state.db count + B2 push activity:"
    sudo find /opt/backrest -name "oplog.sqlite" -exec ls -la {} \;
fi
EOF
```

## DR-store mirror probe (dev WSL — not VPS)

```bash
# Run on the dev machine (where /opt/fabrik/.env lives)
ls -la /opt/fabrik/.env /opt/fabrik/.env.sysadmin 2>&1
systemctl --user is-active fabrik-dr-watcher.service 2>&1 || sudo systemctl is-active fabrik-dr-watcher.service
git -C ~/.fabrik/dr-store log --oneline -5 2>&1 || gh repo view mobasak/fabrik-dr-store --json updatedAt 2>&1
```

---

## Analysis checklist

### 1. Backup coverage (per host)

- Hub: 4 plans match `[postgres-dumps, docker-volumes, opt-configs, host-state]`. Any missing = critical gap.
- Spokes: 2 plans match `[host-state, opt-configs]`. Spoke tenant backups (`docker-volumes-vpsN`, `postgres-dumps-vpsN`) NOT enabled — gated on actual tenant data landing per W11.5.
- Path-preserving bind mounts intact: `/opt`, `/etc`, `/usr/local/bin`, `/root/.ssh`, `/home/ozgur/.ssh` (verify against `docker inspect backrest`).

### 2. Backup schedule

- Hub: postgres-dumps at 02:00, docker-volumes at 03:00, opt-configs at 03:00, host-state at 03:30 (verify against config.json cron).
- Spokes: 2 plans schedule per W11 ship.
- No "every minute" or "every second" schedules (drift indicator).

### 3. Backup integrity (recent snapshots)

- Each plan has had a successful run in the last 36h. Older = `backup_stale` (W10 watcher catches this on hub).
- For spokes: count via Backrest API (auth disabled on spokes) — example shows per-plan success counts.
- Hub: count via UI (`https://backup.vps1.ocoron.com`) or by reading oplog.sqlite (requires sqlite3).

### 4. Recovery readiness

- DR scripts exist + executable:
  - `scripts/bootstrap/bootstrap-hub.sh` (18 steps, ≤ 90 min target — undrilled)
  - `scripts/bootstrap/bootstrap-spoke-restore.sh` (13 steps, ≤ 30 min target — undrilled)
- Operator runbooks exist:
  - `docs/infrastructure/vps-hub-rebuild.md`
  - `docs/infrastructure/vps-spoke-rebuild.md`
- Inventory docs exist:
  - `docs/operations/hub-restore-inventory.md`
  - `docs/operations/spoke-restore-inventory.md`
- **DR drill NOT yet performed against a fresh VPS** — flag as gap (operator-gated).

### 5. Secrets management

- `/opt/backrest/.restic-password` mode 600 on each host.
- DR store mirror has `vps2-restic-password-latest` + `vps3-restic-password-latest` + hub `BACKREST_RESTIC_PASSWORD` in `env/latest`.
- `fabrik-dr-watcher.service` on dev WSL active.
- DR-store last commit < 30d (W10 `dr_store` watcher threshold).

### 6. Known gap — no failure-notification hooks configured

- Verified live 2026-06-02: Backrest config.json on **all 3 hosts** has zero `apprise` references — failure-notification hooks were never configured during the W2/W11 ship.
- Result: backup-failure Telegram alerts never reach operator (silent failure mode).
- Risk currently low — 4 hub plans + 2 per spoke have been running cleanly for 24h+ since W2/W11 ship, with no failures observed. But a future failure would go unnoticed until the operator manually checks Backrest UI or oplog.
- Action: add `hooks` blocks to each plan in `/opt/backrest/config/config.json`, with `conditions: [CONDITION_ANY_ERROR]` and URL `http://apprise:8000/notify/alerts` (stable container name; NOT the old Coolify-era UUID-suffix `apprise-lcocgs4gs8ksg4g08w40ows8`). Restart backrest after each edit.

### 7. What's NOT backed up (gaps)

- Hub: `docker volume`s of monitoring services that explicitly opted out (per W2 exclusion list: `monitoring_prometheus-data` 30d-retention, `monitoring_loki-data`, `monitoring_promtail-positions`, `ocoron-com_redis_data`).
- Spokes: no `docker-volumes-vpsN` plan — fine until W4 tenant data lands.
- `/var/spool/cron/crontabs/root`: not in any plan due to bind-mount conflict (the Backrest base image has `/etc/crontabs` as a symlink to `/var/spool/cron/crontabs` which collides with our `/etc:ro` mount — DR-in-hours track caveat); dumped via `pre-backup.sh` to `/opt/backups/root-crontab.txt` then captured by `postgres-dumps`.

---

## Output format

```markdown
## Backup + DR Audit — Fleet — <UTC date>

**Verdict:** GREEN / YELLOW / RED
**DR readiness:** drilled? | undrilled
**Summary:** one-paragraph

### Per-host backup state
| Host | Plans live | Last snapshot age | Repo URI tail |
| :--- | :--- | :--- | :--- |
| vps1 | 4 | <h>h ago | .../vps1-ocoron-backup |
| vps2 | 2 | <h>h ago | .../spokes/vps2/ |
| vps3 | 2 | <h>h ago | .../spokes/vps3/ |

### Findings (by severity)
1. [severity] <description>
   - Evidence
   - Fix

### DR drill action item
- ...
```
