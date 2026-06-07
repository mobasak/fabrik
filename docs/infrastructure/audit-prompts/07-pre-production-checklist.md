# 07 — Pre-Production Checklist (per-spec, per-target_vps)

**Last Updated:** 2026-06-06 (procedure unchanged from 2026-06-02; today's fleet additions auditors should confirm BEFORE first traffic on a new spec: (a) on the target spoke, `aro-wake.service` is `active` and reachable from the Prometheus container — query Prometheus for `up{job="aro-wake",host="<target_vps>"}` should return 1; (b) the new service does NOT pick port 8201 (now occupied by aro-wake fleet-wide); (c) if the new service emits its own SLI metrics, follow the same scrape pattern documented in `prometheus-app-metrics-setup.md` § "aro-wake SLI metrics" — use docker bridge `10.0.1.1:<port>` for hub-resident services and wg0 mesh `10.99.0.<N>:<port>` for spoke-resident services.)
**Run mode:** **per spec** — before `fabrik apply` on a new service that will see real traffic.
**Scope:** confirm infra/security/observability/backup posture is correct **on the spec's `target_vps`** before traffic lands.
**Time budget:** ~15 min including the `fabrik apply --dry-run` step.

---

## Context

```text
- Fabrik specs live at specs/services/<id>.yaml. Each carries:
  - shape: drives which of 9 registrars fire (postgres, redis, gatus,
    glitchtip, backrest, grafana, authelia, meilisearch, prometheus)
  - target_vps: vps1 | vps2 | vps3 (default vps1)
  - domain: must match the spec's target_vps subdomain
    (`<svc>.vps1.ocoron.com` for vps1, `<svc>.vps2.ocoron.com` for vps2, etc.)
  - resources, health, expose, secrets blocks
- Active deploy: SSH + Docker Compose. fabrik apply orchestrates
  validate → DNS → SSH+Compose → 9 registrars → verifier (HTTPS health).
- Spoke deploys verified end-to-end 2026-06-02 with spoke-canary on vps2
  (HTTP 200 + Let's Encrypt YR2 cert).
- W15 prerequisite: spoke Traefik has the `gzip@docker` middleware label.
  Verify before deploying anything to a spoke.
```

---

## Inputs you need

- The spec path: e.g. `specs/services/<id>.yaml`
- The spec's `target_vps`: read with `python3 -c "import yaml; print(yaml.safe_load(open('specs/services/<id>.yaml')).get('target_vps','vps1'))"`
- The spec's `domain`: must match `<svc>.${target_vps}.ocoron.com`

## Commands to run

```bash
SPEC=specs/services/<id>.yaml
TARGET=$(python3 -c "import yaml; print(yaml.safe_load(open('$SPEC')).get('target_vps','vps1'))")
SVC=$(python3 -c "import yaml; print(yaml.safe_load(open('$SPEC'))['id'])")
DOMAIN=$(python3 -c "import yaml; print(yaml.safe_load(open('$SPEC')).get('domain',''))")

# SSH alias translation: dev-WSL ~/.ssh/config uses `vps` for the hub
# (historical, predates the multi-host fleet). Spokes use the spec name.
case "$TARGET" in
  vps1) SSH_HOST=vps ;;
  vps2|vps3) SSH_HOST=$TARGET ;;
  *) echo "BAIL: unknown target_vps: $TARGET"; exit 1 ;;
esac
echo "Spec: $SPEC | target_vps: $TARGET | ssh-alias: $SSH_HOST | service id: $SVC | domain: $DOMAIN"
echo

echo "=== SPEC VALIDATION ==="
.venv/bin/fabrik apply "$SPEC" --dry-run

echo
echo "=== INFRA STATE ON TARGET HOST ==="
# Note: heredoc is QUOTED ('EOF') so the python -c block's brackets/quotes
# pass through unmolested. Pass needed locals via inline env-passing.
ssh "$SSH_HOST" "TARGET=$TARGET bash -s" <<'EOF'
echo "host: $(hostname)"
echo "container count: $(sudo docker ps -q | wc -l)"
echo "ufw: $(sudo ufw status | head -1)"
echo "fabrik network: $(sudo docker network inspect fabrik --format '{{len .Containers}} containers' 2>&1)"
echo "traefik: $(sudo docker ps --filter name=traefik --format '{{.Names}} {{.Status}}')"
if [ "$TARGET" != "vps1" ]; then
  echo "spoke W15 labels:"
  sudo docker inspect traefik --format '{{range $k,$v := .Config.Labels}}{{$k}}={{$v}}{{println}}{{end}}' | grep -E "traefik\.enable|gzip\.compress"
fi
sudo cat /opt/backrest/config/config.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('backrest plans:', [p['id'] for p in d.get('plans', [])])
"
EOF

echo
echo "=== DNS A-RECORD STATE ==="
dig +short "$DOMAIN" @1.1.1.1
dig +short "$DOMAIN" @8.8.8.8
case "$TARGET" in
  vps1) EXPECTED_IP="172.93.160.197" ;;
  vps2) EXPECTED_IP="96.9.214.128" ;;
  vps3) EXPECTED_IP="104.128.190.151" ;;
esac
echo "Expected: $EXPECTED_IP"

echo
echo "=== SHARED INFRA REACHABILITY FROM TARGET (over mesh) ==="
ssh "$SSH_HOST" 'ping -c 2 -W 3 10.99.0.1'
# postgres-main/redis-main are docker DNS names — only resolve INSIDE the
# fabrik network. Probe from a throwaway container on that network, not
# the host shell.
ssh "$SSH_HOST" 'sudo docker run --rm --network fabrik alpine sh -c "nc -zv postgres-main 5432; nc -zv redis-main 6379" 2>&1 | tail -5'

echo
echo "=== HUB SHAPE-DRIVEN REGISTRAR DRY-RUN (expect dry_run statuses) ==="
.venv/bin/fabrik apply "$SPEC" --dry-run 2>&1 | grep -E "registrar|dry_run|skipped" | head -30

echo
echo "=== AUTHELIA RULE WILL BE ADDED FOR THIS DOMAIN? ==="
# Use the SSH_HOST alias, not literal `vps` — single-source the alias mapping.
ssh "$SSH_HOST" "sudo cat /opt/authelia/config/configuration.yml" | DOMAIN="$DOMAIN" python3 -c "
import os, yaml, sys
cfg = yaml.safe_load(sys.stdin)
rules = cfg.get('access_control', {}).get('rules', [])
domain = os.environ['DOMAIN']
matches = []
for r in rules:
    doms = r.get('domain', [])
    if isinstance(doms, str): doms = [doms]
    for d in doms:
        if d == domain or (d.startswith('*.') and domain.endswith(d[2:])):
            matches.append((r.get('policy'), d, r.get('resources', ['(any)'])))
if not matches:
    print('  (no existing rule for this domain; registrar will add)')
else:
    print(f'  {len(matches)} matching rule(s) (Authelia evaluates in file-order — first match wins):')
    for i, (pol, dom, res) in enumerate(matches, 1):
        print(f'  {i}. policy={pol}  domain={dom}  resources={res}')
"
```

---

## Go-live checklist (target: `target_vps` of the spec)

### Infrastructure layer

- [ ] **Spec validates clean** — `fabrik apply --dry-run` returns no errors.
- [ ] **`target_vps` is set** (vps1 default; spokes require explicit `target_vps: vps2` or `vps3`).
- [ ] **`domain` matches target** — `<svc>.${target_vps}.ocoron.com`. Mismatch = router never matches.
- [ ] **DNS A record exists and resolves to the target's public IP** — bootstrap-vps.sh step_13 should have created it; verify with `dig`.
- [ ] **`fabrik` Docker network present on target host.**
- [ ] **Traefik running on target host.** Spokes: confirm W15 labels (`traefik.enable=true` + `gzip.compress=true`).
- [ ] **Shared infra reachable** from target host over mesh (postgres-main, redis-main, etc. via `10.99.0.1`).

### Security layer

- [ ] **UFW active** on target with default deny.
- [ ] **fail2ban active** on target.
- [ ] **No `ports:` block in spec's compose** (Traefik fronts everything).
- [ ] **Authelia rule for the domain** — either already exists or will be added by the authelia registrar at apply time (verify via dry-run output).
- [ ] **Service-internal secret** (`SERVICE_INTERNAL_SECRET_KEY`) present if the spec has M2M callers.
- [ ] **No localhost in DB URLs** — `DATABASE_URL` must use `postgres-main:5432` or `10.99.0.1:5432` from spokes.

### Observability layer

- [ ] **`shape.is_public: true`** → expect Gatus endpoint to be created at apply time.
- [ ] **`shape.exposes_metrics: true`** → expect Prometheus scrape job to be added.
- [ ] **Service emits GlitchTip events** via SDK with `SENTRY_DSN` (registrar injects this; verify post-deploy via `docker inspect <main> | grep SENTRY_DSN` per Lesson 31 — NOT `docker exec printenv` because distroless).
- [ ] **Service's `/health` returns 200 with real dep checks** — must `await db.execute("SELECT 1")`, not return a static 200.
- [ ] **Promtail will pick up the container** (docker.sock auto-discovery; nothing to configure).

### Backup layer

- [ ] **DB / volume / config will be covered** by an existing Backrest plan after apply. For spokes, tenant data is NOT in the spoke's plans by design — operator must enable `docker-volumes-vpsN` / `postgres-dumps-vpsN` plans when actual data lands (W11.5 deferral).
- [ ] **Service has no other persistent state** that's outside the backup paths.

### Application layer

- [ ] **Image specifies a stable tag** (no `:latest` without a digest pin).
- [ ] **Memory limit set** (`deploy.resources.limits.memory` — gate enforces).
- [ ] **CPU limit set** (`deploy.resources.limits.cpus` — recommended).
- [ ] **`restart: unless-stopped`** on every service.
- [ ] **`container_name: <id>`** matches spec id (Fabrik convention since 2026-05-30 Coolify removal — required for stable `docker exec`/`docker inspect` targeting).
- [ ] **`HEALTHCHECK` in compose** with `start_period: 20s` minimum.
- [ ] **Traefik labels match service-category template** (admin → `authelia-forward@docker,gzip@docker`; api → `gzip@docker`; public → none).

### Operational layer

- [ ] **`CHANGELOG.md [Unreleased]` entry written.**
- [ ] **`docs/FEATURES.md` row added** (if user-visible feature).
- [ ] **`PORTS.md` updated** if a new port is allocated (rare — all should route via Traefik).
- [ ] **Operator silenced ContainerDown alerts** if the apply will take > 2 min (operator discipline; otherwise Telegram floods during the deploy).
- [ ] **Rollback plan exists** — `fabrik destroy --use-state` is the default. State file at `.fabrik/state/<id>.json` will be written on success.

---

## Output format

```markdown
## Pre-Prod Checklist — `<spec>` → `<target_vps>` — <UTC date>

**Verdict:** READY / NOT READY / READY WITH CAVEATS
**Spec:** specs/services/<id>.yaml
**Target host:** <vpsN>  (public IP <ip>, mesh IP 10.99.0.<N>)
**Domain:** <svc>.<vpsN>.ocoron.com

### Layer summary
| Layer | State | Notes |
| :--- | :--- | :--- |
| Infrastructure  | ✓ / ✗ | <one-line> |
| Security        | ✓ / ✗ | <one-line> |
| Observability   | ✓ / ✗ | <one-line> |
| Backup          | ✓ / ✗ | <one-line> |
| Application     | ✓ / ✗ | <one-line> |
| Operational     | ✓ / ✗ | <one-line> |

### Blockers (must fix before apply)
1. ...

### Cautions (can apply; track in CHANGELOG)
1. ...
```
