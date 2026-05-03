# Troubleshooting

**Last Updated:** 2026-04-28 (added B23 verifier 404 / Docusaurus terminal grace entries from B23–B46 proof mission; replaced Duplicati block with one-paragraph migration notice — Backrest is the live backup tool since 2026-04-17)

Common issues and solutions.

## Connection Issues

### SSH Connection Refused

**Symptom:** `ssh: connect to host X port 22: Connection refused`

**Solutions:**

1. Check VPS is running
2. Verify SSH port is 22 (check `/etc/ssh/sshd_config`)
3. Check UFW allows port 22: `sudo ufw status`
4. Verify your IP isn't banned: `sudo fail2ban-client status sshd`

### Coolify API Unreachable

**Symptom:** `ConnectionError: Unable to connect to Coolify API`

**Solutions:**

1. Verify Coolify is running: `ssh deploy@vps docker ps | grep coolify`
2. Check COOLIFY_API_URL is correct (include https://)
3. Verify API token is valid
4. Check firewall allows 443

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
4. Check Coolify logs: `docker logs coolify`

## Deployment Issues

### Container Won't Start

**Symptom:** Deployment completes but app is down

**Solutions:**

1. Check logs: `fabrik logs my-app`
2. Verify all required env vars are set
3. Check health endpoint works locally
4. Verify database connection string

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

### Deploy succeeds in Coolify but `fabrik apply` reports "Health check failed: 404"

**Symptom:** Coolify shows the container as `Up (healthy)`, but the orchestrator rolls the deploy back with a 404. Curl-ing the live URL works.

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

**Symptom:** `fabrik apply <docusaurus-spec>` fails verification, but `coolify` shows the container as `running:healthy` 1–2 minutes later.

**Cause:** Multi-stage Node builds (`docusaurus`, `saas-skeleton`) take 60–90s during which Coolify reports the application as `exited:unhealthy` (old container removed, new one not yet running). Pre-2026-04-28 the orchestrator's `terminal_grace_period` was 30s — it gave up before the new container even started. Fixed in B46 (now 180s).

**If you still see this with another slow-build type:** bump `terminal_grace_period` further in `@/opt/fabrik/src/fabrik/orchestrator/deployer.py::_wait_for_app_status`. Genuine failures still terminate via Coolify's explicit `failed` deployment-job state, so longer grace only affects the legitimate deploy-recreate path.

### Port Already in Use

**Symptom:** `Error: Port 8000 is already in use`

**Solutions:**

1. Check `/opt/fabrik/PORTS.md`
2. Find process: `ss -tlnp | grep 8000`
3. Use different port in spec

### `fabrik apply` fails with "spec renders compose with `build:` but `source.type` is 'template'"

**Symptom:** `fabrik apply specs/services/<name>.yaml` fail-fasts before deploying with the message `source.type is 'template' (not 'git'). Coolify's inline-compose endpoint has no source for 'build:' to consume — the build will never run.`

**Cause:** The project has no git remote. `spec_generator.detect_git_source()` (`src/fabrik/spec_generator.py` line 291) runs `git -C <project> remote get-url origin` with 5s timeout at scaffold time. Without a remote, the emitted spec keeps `source.type: template`, and the deployer's B7 preflight in `src/fabrik/orchestrator/deployer.py` rejects the deploy. A `WARNING` is logged at scaffold time (`spec_generator.py` line 426): *"No git remote configured at <path> — emitting source.type=template. This spec will fail Coolify deploy..."*

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
3. Verify credentials in Coolify database settings
4. Check pg_hba.conf allows connection

### Backup Failed

**Symptom:** B2 backup job fails

**Solutions:**

1. Verify B2 credentials
2. Check bucket exists and is accessible
3. Review backup logs in Coolify
4. Test B2 connection: `b2 authorize-account`

## Backup Issues (Backrest)

> **2026-04-17 migration:** Duplicati was replaced by Backrest at `backup.vps1.ocoron.com`. Backrest is restic-based with Backblaze B2 as the remote. Old Duplicati troubleshooting was archived to `docs/archive/2026-04-28-duplicati-setup.md`. For Backrest operations, see Backrest's web UI and `docs/operations/backup-strategy.md`.

## Getting Help

If issues persist:

1. Check logs: `fabrik logs <app> --tail 100`
2. Review Coolify dashboard for errors
3. Check VPS system logs: `journalctl -xe`

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `ECONNREFUSED` | Service not running | Start the service |
| `401 Unauthorized` | Invalid API token | Regenerate token |
| `DNS_PROBE_FINISHED_NXDOMAIN` | DNS not propagated | Wait or check records |
| `ERR_CERT_DATE_INVALID` | SSL not issued | Check ports 80/443 |
