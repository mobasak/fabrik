# 08 — Hardening Remediation (per host)

> **⚠ READ BEFORE EXECUTING ANYTHING.**
>
> This prompt produces commands that **change live state** on a target VPS. Use after audits 01-06 have surfaced findings. Every command must be reviewed, dry-run-equivalent-tested, and applied with `ContainerDown` alerts silenced for any op > 2 min (operator discipline: silence-alerts-before-downtime).

**Last Updated:** 2026-06-06 (procedure unchanged from 2026-06-02; today's NEW remediation patterns auditors may need: (1) **storm-breaker stuck-tripped on a target_host** — remove `/var/lib/aro-wake/pending.jsonl` stale entries: `sudo truncate -s 0 /var/lib/aro-wake/pending.jsonl` (operator must first confirm via logs that the storm cause was diagnosed + closed); (2) **test drop-in cleanup** — after any `ARO_WAKE_STORM_THRESHOLD=0` synthetic test, REMOVE `/etc/systemd/system/aro-wake.service.d/*.conf` drop-ins and `systemctl daemon-reload && systemctl restart aro-wake.service`; (3) **spoke-side `bot.py` `ModuleNotFoundError: telegram`** — install `python-telegram-bot==22.7` via `sudo pip install --break-system-packages python-telegram-bot==22.7` then `sudo systemctl restart vps-sysadmin-bot.service` (this is one of the 4 spoke bootstrap gaps from 2026-06-06 — should disappear once `bootstrap-vps.sh` is updated); (4) **aro-wake counters drift / Prometheus scrape errors** — restart `aro-wake.service` on the affected host (counters reset by design, `rate()` recovers via `_created` timestamps).)
**Run mode:** **per host** — execute fixes on one target VPS at a time.
**Scope:** apply findings from audits 01-06; verify after.
**Time budget:** highly variable per fix list.

---

## Design principles

1. **Idempotent commands.** Re-running must not break things.
2. **Backup before destruct.** Touching `.env`, `compose.yaml`, `traefik.yml`, `authelia/configuration.yml`, restic password, or any `*.key` → `cp <f> backups/<f>.backup.$(date +%Y%m%d-%H%M%S)` first.
3. **Silence alerts** during planned ops > 2 min (operator discipline: silence-alerts-before-downtime).
4. **Single-operator threat model.** Don't propose perm/rotation/audit work that doesn't name a realistic attacker (Memory: `feedback_threat_model_single_operator.md`).
5. **One workstream at a time.** Apply all of category A before starting category B. Verify between categories.
6. **The `coolify` Docker network name was renamed to `fabrik`** on 2026-05-31. New code must reference `fabrik`. Old code in archived legacy modules still references `coolify`; don't change those.

---

## Input: audit findings

This prompt assumes the operator has already run audits 01-06 and is feeding the prioritized findings here. Paste the findings as a numbered list with severity, evidence, host, and proposed fix.

```text
Findings to remediate (paste from audits 01-06):
1. [vps2 / SEV-HIGH] W15 gzip middleware missing on Traefik
   Evidence: docker inspect traefik | grep gzip → empty
   Proposed fix: add labels block to /opt/traefik/compose.yaml + restart
2. ...
```

---

## Stack context

```text
- 3 hosts under management. Each owns its own compose stacks, Backrest,
  Traefik. Fixes apply to one host at a time.
- Compose files at /opt/<svc>/compose.yaml (root-owned, 644).
- .env files at /opt/<svc>/.env (root-owned, 600 for ones with secrets).
- All containers stable-named via compose `container_name:` (a Fabrik convention since the 2026-05-30 Coolify removal — replaces UUID-suffix names). `fabrik` Docker network is shared.
- vps1 has Authelia + Traefik dashboard + 31 containers (29 platform + 2 dogfood). Spokes have 5.
- /opt/fabrik-lib/ on dev WSL is the vendor source for module copies; not
  on VPS.
- Memory limit invariant: every compose service must declare
  deploy.resources.limits.memory. The orchestrator validates this.
- DNS via site-provisioner on vps1; idempotent ensure_record API at
  /api/cloudflare/dns/<root>/subdomain.
```

---

## Hardening checklist — categorized

Categories are independent — apply in any order, but complete one before starting the next. After each category, re-run the relevant audit (01-06) to confirm the finding cleared.

### A. Network perimeter

```bash
ssh <target> bash <<'EOF'
# A1. Tighten UFW (idempotent; --force needed in non-interactive)
sudo ufw default deny incoming
sudo ufw default allow outgoing
# Only add rules you don't already have (ufw status numbered to check first)

# A2. Add mesh-allow on spokes if missing (W8 fix, may need re-apply)
sudo ufw allow from 10.99.0.0/24

# A3. Confirm DOCKER-USER chain still blocks mesh-only ports from public iface
sudo iptables -L DOCKER-USER -n --line-numbers

# A4. fail2ban refresh
sudo systemctl restart fail2ban
sudo fail2ban-client status sshd
EOF
```

### B. Container resource limits

```bash
# B1. Find services without memory limits
ssh <target> 'sudo docker ps --format "{{.Names}}" | while read n; do l=$(sudo docker inspect --format="{{.HostConfig.Memory}}" "$n"); [ "$l" = "0" ] && echo "NO LIMIT: $n"; done'

# B2. For each NO-LIMIT service, edit its compose to add the limit
# Example for /opt/<svc>/compose.yaml:
#   services:
#     <svc>:
#       deploy:
#         resources:
#           limits:
#             memory: 512M
#             cpus: "0.5"

# B3. Apply
ssh <target> 'cd /opt/<svc> && sudo docker compose up -d'

# B4. Verify
ssh <target> 'sudo docker inspect --format="{{.HostConfig.Memory}}" <svc>'
```

### C. W15 spoke Traefik labels (CRITICAL if missing on a spoke)

```bash
# C1. Verify
ssh vps2 'sudo docker inspect traefik --format "{{range \$k,\$v := .Config.Labels}}{{\$k}}={{\$v}}{{println}}{{end}}" | grep -E "traefik\.enable|gzip\.compress"'

# C2. If missing, fix by editing /opt/traefik/compose.yaml (the spoke's Traefik compose):
# Add to the traefik service:
#   labels:
#     - "traefik.enable=true"
#     - "traefik.http.middlewares.gzip.compress=true"

# C3. Apply
ssh vps2 'cd /opt/traefik && sudo cp compose.yaml compose.yaml.backup.$(date +%Y%m%d-%H%M%S) && sudo docker compose up -d'

# C4. Verify by deploying a canary spec or re-running 02-container-health on vps2
```

### D. Backrest failure-notification hook (currently unconfigured on all 3 hosts)

```bash
# Verified live 2026-06-02: no apprise hook configured in /opt/backrest/config/config.json
# on any of vps1/vps2/vps3. Backup-failure Telegram alerts are silently lost.
# If a hook IS later configured pointing at the Coolify-era UUID-suffix
# `apprise-lcocgs4gs8ksg4g08w40ows8`, also fix it to the stable `apprise` name.

# Step 1: backup the config
ssh <target> bash <<'EOF'
sudo cp /opt/backrest/config/config.json \
        /opt/backrest/config/config.json.backup.$(date +%Y%m%d-%H%M%S)
EOF

# Step 2: add hooks to each plan via the Backrest UI (auth-disabled on spokes;
# vps1 has auth — use the UI at https://backup.vps1.ocoron.com).
# Each plan's hooks block should look like:
#   "hooks": [
#     {
#       "conditions": ["CONDITION_ANY_ERROR"],
#       "actionWebhook": {
#         "url": "http://apprise:8000/notify/alerts",
#         "method": "POST",
#         "body": "{\"title\":\"Backrest [{{.Plan.Id}}] failed\",\"body\":\"{{.Error}}\"}"
#       }
#     }
#   ]

# Step 3: if config.json was edited directly, restart backrest:
ssh <target> 'sudo docker restart backrest'

# Step 4: verify the hook fires by manually triggering a failure (e.g. point
# a plan at a non-existent path with --dry-run=false) — check that an
# Apprise notification arrives in Telegram.

# If you find a stale Coolify-era UUID-suffix instead of `apprise`:
ssh <target> "sudo sed -i 's|apprise-lcocgs4gs8ksg4g08w40ows8|apprise|g' /opt/backrest/config/config.json && sudo docker restart backrest"
```

### E. Promtail noise filter for tenant containers

If a tenant container floods Loki with noisy logs (e.g. nightly backup container looping), add a `drop` stage to that host's `promtail.yaml`:

```yaml
# /opt/monitoring-agent/promtail.yaml (spoke) or
# /opt/monitoring/configs/promtail/promtail-config.yaml (hub — note `-config` suffix)
scrape_configs:
  - job_name: containers
    pipeline_stages:
      - drop:
          source: container_name
          expression: "^<noisy-container-name>$"
```

```bash
ssh vps  'sudo nano /opt/monitoring/configs/promtail/promtail-config.yaml'   # hub
ssh vps2 'sudo nano /opt/monitoring-agent/promtail.yaml'                     # spoke
ssh <target> 'sudo docker restart promtail'
```

### F. site-provisioner DNS step (W16-DNS) — verify creates records

If a new spoke comes online and the operator did not run `bootstrap-vps.sh step_13`, ensure DNS A records exist:

```bash
# Probes
dig +short vpsN.ocoron.com @1.1.1.1
dig +short '*.vpsN.ocoron.com' @1.1.1.1   # any random subdomain to test wildcard

# If missing, ensure via site-provisioner (idempotent; call from vps1):
ssh vps 'API=$(sudo grep "^API_KEY=" /opt/site-provisioner/.env | cut -d= -f2- | tr -d "\""); for sd in vpsN "*.vpsN"; do
  curl -fsS -X POST -H "X-API-Key: $API" -H "Content-Type: application/json" \
    -d "{\"subdomain\":\"$sd\",\"ip\":\"<public-ipv4>\",\"proxied\":false}" \
    https://provision.vps1.ocoron.com/api/cloudflare/dns/ocoron.com/subdomain
done'
```

### G. Authelia rule for a new admin dashboard

```bash
ssh vps bash <<'EOF'
sudo cp /opt/authelia/config/configuration.yml \
        /opt/authelia/config/configuration.yml.backup.$(date +%Y%m%d-%H%M%S)
# Edit to add a new rule under access_control.rules, then:
sudo docker restart authelia   # do NOT SIGHUP — Authelia exits; restart is required
EOF
```

### H. /data/coolify cleanup (hub only)

```bash
# Defer until next DR drill confirms no in-use dependency.
# When ready (irreversible — review du -sh first):
ssh vps 'sudo du -sh /data/coolify; sudo ls /data/coolify/'
# If genuinely safe:
ssh vps 'sudo rm -rf /data/coolify'
```

---

## Verification after each category

Run the relevant audit (01-06) again to confirm:

- A → 03-security-hardening
- B → 02-container-health
- C → 02-container-health on the spoke
- D → 06-backup-disaster-recovery
- E → 05-observability-pipeline
- F → bootstrap-vps.sh --verify shows the DNS row green
- G → 03-security-hardening (auth section)
- H → 01-full-system-audit (disk section)

---

## Output format

```markdown
## Hardening Run — <hostN> — <UTC date>

**Trigger:** audit XX (date)
**Categories applied:** A | B | C | D | E | F | G | H

### What changed
1. [category] <description>
   - Before: <state>
   - Command: <one-line>
   - After: <state>
   - Backup created: <path>

### Findings closed (with audit cross-ref)
- ...

### Carry-over to next session
- ...
```
