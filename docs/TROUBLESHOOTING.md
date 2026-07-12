# Troubleshooting

**Last Updated:** 2026-06-02 (Coolify-flavored historical symptoms preserved as past-tense; symptoms now surface in `docker compose ps` / `docker inspect` instead of the Coolify UI which was removed 2026-05-30). Added B23 verifier 404 / Docusaurus terminal grace entries from B23–B46 proof mission; Backrest is the live backup tool since 2026-04-17.

Common issues and solutions.

## Connection Issues

### SSH Connection Refused

**Symptom:** `ssh: connect to host X port 22: Connection refused`

**Solutions:**

1. Check VPS is running
2. Verify SSH port is 22 (check `/etc/ssh/sshd_config`)
3. Check UFW allows port 22: `sudo ufw status`
4. Verify your IP isn't banned: `sudo fail2ban-client status sshd`

### SSH Connection Failures

**Symptom:** `fabrik apply` / `fabrik redeploy` fail with `RuntimeError: ssh ... exit 255` or `Could not resolve hostname`

**Solutions:**

1. Verify the `vps` SSH alias resolves: `ssh -v vps echo ok` — should connect without password prompt
2. If you use a non-default alias, set `FABRIK_VPS_SSH_HOST=<alias>` in `/opt/fabrik/.env`
3. Confirm the VPS is reachable: `ping <vps-host>` + `nc -vz <vps-host> 22`
4. Check UFW on the VPS allows port 22 from your IP
5. Verify your key is in the VPS `~/.ssh/authorized_keys`

## DNS Issues

### DNS Records Not Updating

**Symptom:** `fabrik apply` succeeds but domain doesn't resolve

**Solutions:**

1. Wait for DNS propagation (up to 48 hours, usually 5-30 min)
2. Check Namecheap API IP whitelist includes your current IP
3. Verify API credentials are correct
4. Check DNS manually: `dig +short yourdomain.com`

### SSL Certificate Not Issued

**Symptom:** HTTPS not working, certificate errors

**Solutions:**

1. Verify DNS points to correct VPS IP
2. Check ports 80/443 are open on VPS
3. Wait 5 minutes for Let's Encrypt
4. Check Traefik logs (the cert resolver): `ssh vps "sudo docker logs traefik --tail 100"`

## Deployment Issues

### Container Won't Start

**Symptom:** Deployment completes but app is down

**Solutions:**

1. Check logs: `fabrik logs my-app`
2. Verify all required env vars are set
3. Check health endpoint works locally
4. Verify database connection string

### Alerts are silently never delivered (Apprise `/notify/alerts` returns 204)

**Symptom:** Gatus (and `scripts/sysadmin/{morning-report,weekly-security,daily-digest}.sh`, and the AI
sysadmin) all report they *sent* an alert, but **nothing arrives in Telegram** — no error anywhere. This is
how vps1's dead `alertmanager` went unnoticed for 4 days while Gatus logged **5,893** failed checks.

**Cause:** The fleet convention is `POST http://apprise:8000/notify/alerts` — Apprise's **stateful** endpoint
(config key `alerts`). But Apprise is deployed with only the **stateless** target
(`APPRISE_STATELESS_URLS=tgram://…`, served at bare `/notify`). With no `alerts` config, Apprise answers
**`204 No Content`** — request accepted, **nothing sent**. A 204 looks like success to every caller.

**Diagnose (the 204 is the tell):**

```bash
ssh vps 'sudo docker logs apprise 2>&1 | grep "POST /notify" | tail'   # all 204 ⇒ every alert discarded
sudo bash scripts/sysadmin/ensure-apprise-alerts-config.sh --check     # → BROKEN: … → 204
```

**Fix (idempotent, safe to re-run):**

```bash
sudo bash scripts/sysadmin/ensure-apprise-alerts-config.sh   # creates the 'alerts' config from APPRISE_STATELESS_URLS
# verify: /notify/alerts → 200, and a probe message lands in Telegram
```

⚠️ The `alerts` config lives in the `apprise-config` volume — persistent across restarts/reboots, but **not
reproducible from git**. Re-run the script after any Apprise volume rebuild, or the alert path silently dies
again. Note a 200 from `/notify` (stateless) does **not** imply `/notify/alerts` works — test the path your
callers actually use.

**Prevention — the alert-path canary.** `scripts/sysadmin/fabrik-alert-canary.sh` (installed at
`/usr/local/bin/fabrik-alert-canary.sh` on vps1) watches the watcher: a monitoring stack that cannot page you
is indistinguishable from "all quiet", which is why this outage lasted 4 days.

- default → **silent** config probe (`POST /get/alerts`: 200 = config present, 204 = missing). No Telegram
  noise, safe hourly.
- `--e2e` → **true delivery** test (`POST /notify/alerts` must return 200 — Apprise returns 200 only when it
  actually delivered; 424 = send failed). Sends one message; use as a weekly heartbeat.
- On breakage it **auto-repairs** the config and **escalates via a DIRECT `api.telegram.org` call that bypasses
  Apprise entirely** — because a dead alert path cannot report its own death.

Verified by deleting the live `alerts` config: the canary detected the 204, repaired it, and delivered the
out-of-band escalation.

### A container stays down after a host reboot (Docker restart-policy race)

**Symptom:** After a VPS reboot (e.g. an unattended kernel upgrade) one container is `Exited (255)` and did
NOT come back, while its siblings show `Up N days`. Worst case: it's a monitoring/alerting service, so you
get **no page about its own absence** (this is exactly how vps1 `alertmanager` sat dead 4 days from 2026-07-08).

**Cause:** `restart: unless-stopped` does **not** resume a container that had already fully exited (non-zero)
at the instant `dockerd` stopped during shutdown. Containers still *running* at that instant are resumed on
boot; one that crash-exited first is left `Exited`.

**Immediate fix:**

```bash
ssh <host> 'sudo docker inspect <name> --format "ExitCode={{.State.ExitCode}} OOMKilled={{.State.OOMKilled}} FinishedAt={{.State.FinishedAt}}"'
# FinishedAt ≈ the reboot time + ExitCode 255 + OOMKilled=false ⇒ the reboot race (not a config bug)
ssh <host> 'cd /opt/<svc> && sudo docker compose up -d'   # restores it; validate config first if unsure
```

**Permanent fix (already deployed fleet-wide):** `fabrik-compose-boot.service` reconciles every
`/opt/*/compose.yaml` stack to running on boot — see `scripts/systemd/README.md`. Verify it's enabled:
`ssh <host> 'systemctl is-enabled fabrik-compose-boot.service'` → `enabled`. Spokes get it from
`bootstrap-vps.sh` step 16; the hub via `scripts/systemd/install-compose-boot.sh`.

### Out of Disk Space

**Symptom:** Deployments fail, Docker errors

**Solutions:**

```bash
# Check disk usage
df -h

# Clean Docker
docker system prune -a

# Check log sizes
du -sh /var/lib/docker/containers/*
```

### Deploy succeeds (`docker compose ps` shows healthy) but `fabrik apply` reports "Health check failed: 404"

**Symptom:** `docker compose ps` shows the container as `Up (healthy)` (pre-2026-05-30 the same was visible in the Coolify UI), but the orchestrator rolls the deploy back with a 404. Curl-ing the live URL works.

**Cause (historical):** Pre-2026-04-28, the verifier read `spec["healthcheck"]["path"]` but the spec generator emitted `health.path`. The silent fallback was `/health`. For any scaffold type whose healthcheck wasn't `/health` (`saas-skeleton`, `static-site`, `node-api`, `file-api` all use `/api/health`; `docusaurus` uses `/docs/intro`), the verifier always probed `/health` and 404'd. Fixed in B23 (see `CHANGELOG.md [Unreleased]` and Lesson 32).

**If you still see this:** verify the spec on disk matches the verifier's read site:

```bash
cat specs/services/<name>.yaml | grep -A2 '^health:'
# health:
#   path: /api/health     ← what the verifier should probe
```

Then re-run with `--keep-on-failure` to leave the container alive for inspection:

```bash
fabrik apply specs/services/<name>.yaml --use-orchestrator --keep-on-failure --yes
curl -fsS https://<name>.vps1.ocoron.com/api/health   # verify path manually
```

If the manual curl succeeds but the orchestrator still 404s, the verifier is reading the wrong key — open an issue.

### Docusaurus deploy reaches `running:healthy` after orchestrator gives up

**Symptom:** `fabrik apply <docusaurus-spec>` fails verification, but `docker compose ps` shows the container as `running:healthy` 1–2 minutes later.

**Cause:** Multi-stage Node builds (`docusaurus`, `saas-skeleton`) take 60–90s during which the container reports `exited:unhealthy` (old container removed, new one not yet running; pre-2026-05-30 this was visible as Coolify reporting `exited:unhealthy`). Pre-2026-04-28 the orchestrator's `terminal_grace_period` was 30s — it gave up before the new container even started. Fixed in B46 (now 180s).

**If you still see this with another slow-build type:** bump `terminal_grace_period` further in `@/opt/fabrik/src/fabrik/orchestrator/deployer.py::_wait_for_app_status`. Genuine failures still terminate via `fabrik apply` (SSH + Docker Compose)'s explicit `failed` deployment-job state, so longer grace only affects the legitimate deploy-recreate path.

### Port Already in Use

**Symptom:** `Error: Port 8000 is already in use`

**Solutions:**

1. Check `/opt/fabrik/PORTS.md`
2. Find process: `ss -tlnp | grep 8000`
3. Use different port in spec

### `fabrik apply` fails with "spec renders compose with `build:` but `source.type` is 'template'"

**Symptom:** `fabrik apply specs/services/<name>.yaml` fail-fasts before deploying with the message `source.type is 'template' (not 'git'). Coolify's inline-compose endpoint has no source for 'build:' to consume — the build will never run.`

**Cause:** The project has no git remote. `spec_generator.detect_git_source()` (`src/fabrik/spec_generator.py` line 291) runs `git -C <project> remote get-url origin` with 5s timeout at scaffold time. Without a remote, the emitted spec keeps `source.type: template`, and the deployer's B7 preflight in `src/fabrik/orchestrator/deployer_ssh.py` rejects the deploy. A `WARNING` is logged at scaffold time (`spec_generator.py` line 426): *"No git remote configured at `<path>` — emitting source.type=template. This spec will fail the deployer's build-source check..."* (older versions of the warning said "Coolify deploy").

**Fix:** Add a remote and re-emit the spec.

```bash
cd /opt/<project-name>
git remote add origin git@github.com:<user>/<project-name>.git
git push -u origin main
# Re-run the spec emitter so detect_git_source() picks up the remote:
fabrik scaffold <project-name> --type <type>   # if project tree exists, this re-runs spec emission
# OR cleanest: delete and rescaffold from a directory that already has a remote.
```

Reference path used by automation: `scripts/proof_run.py` lines 410–423 demonstrate the canonical sequence (scaffold → push → regenerate spec → apply).

## Database Issues

### Cannot Connect to PostgreSQL

**Symptom:** `Connection refused` or `authentication failed`

**Solutions:**

1. Verify Postgres container is running
2. Check DATABASE_URL format: `postgresql://user:pass@host:5432/db`
3. Verify credentials match what the postgres registrar wrote (`fabrik audit-registrars` shows the live DB user/db)
4. Check pg_hba.conf allows connection

### Backup Failed

**Symptom:** B2 backup job fails

**Solutions:**

1. Verify B2 credentials
2. Check bucket exists and is accessible
3. Review backup logs in the Backrest UI (`backup.vps1.ocoron.com`)
4. Test B2 connection: `b2 authorize-account`

## Backup Issues (Backrest)

> **2026-04-17 migration:** Duplicati was replaced by Backrest at `backup.vps1.ocoron.com`. Backrest is restic-based with Backblaze B2 as the remote. Old Duplicati troubleshooting was archived to `docs/archive/2026-04-28-duplicati-setup.md`. For Backrest operations, see Backrest's web UI and `docs/operations/disaster-recovery.md`.

## Getting Help

If issues persist:

1. Check logs: `fabrik logs <app> --tail 100`
2. Inspect the live container on the VPS: `ssh vps "sudo docker inspect <container>"`
3. Check VPS system logs: `ssh vps "sudo journalctl -xe"`

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `ECONNREFUSED` | Service not running | Start the service |
| `401 Unauthorized` | Invalid API token | Regenerate token |
| `DNS_PROBE_FINISHED_NXDOMAIN` | DNS not propagated | Wait or check records |
| `ERR_CERT_DATE_INVALID` | SSL not issued | Check ports 80/443 |
