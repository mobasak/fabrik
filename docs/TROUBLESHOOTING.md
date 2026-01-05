# Troubleshooting

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

### Port Already in Use

**Symptom:** `Error: Port 8000 is already in use`

**Solutions:**

1. Check `/opt/fabrik/PORTS.md`
2. Find process: `ss -tlnp | grep 8000`
3. Use different port in spec

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

## Duplicati Issues

### Duplicati Bad Gateway

**Symptom:** https://backup.vps1.ocoron.com returns "Bad Gateway" error

**Cause:** Duplicati server crashed inside the container (often due to file permission issues or lock file conflicts). Container shows as "Up" but the internal server process is dead.

**Diagnosis:**
```bash
# Check if container is running (misleading - may show Up)
ssh vps "sudo docker ps --filter name=duplicati"

# Check actual server status - look for crash traces
ssh vps "sudo docker logs duplicati 2>&1 | tail -20"

# Test if server is responding internally
ssh vps "sudo docker exec duplicati curl -s http://localhost:8200/"
```

**Solution:**
```bash
# Restart the container
ssh vps "sudo docker restart duplicati"

# Verify it's working
curl -s -o /dev/null -w '%{http_code}' https://backup.vps1.ocoron.com/
# Should return 200
```

### Duplicati Login Not Working

**Symptom:** Password rejected at login page

**Cause:** Password is set via `CLI_ARGS` environment variable when container starts

**Solution:**
```bash
# Check current password in container env
ssh vps "sudo docker inspect duplicati --format '{{.Config.Env}}' | tr ' ' '\n' | grep webservice-password"

# Password is in fabrik .env
grep DUPLICATI_PASSWORD /opt/fabrik/.env
```

### Backup Job Not Visible in Web UI

**Symptom:** Created backup job via script but doesn't appear in UI

**Cause:** Job created in wrong database or server not restarted after DB changes

**Solution:**
```bash
# Verify job exists in server database
ssh vps "sudo sqlite3 /var/lib/docker/volumes/duplicati_duplicati-config/_data/Duplicati-server.sqlite 'SELECT * FROM Backup;'"

# Restart Duplicati to reload
ssh vps "sudo docker restart duplicati"
```

### Restore Not Working (Empty File List)

**Symptom:** Backup exists but restore shows no files

**Cause:** Local SQLite database (restore DB) not populated - happens when backup was run via CLI without `--dbpath` pointing to the correct location

**Solution:**
```bash
# Check if restore DB exists
ssh vps "sudo docker exec duplicati ls -la /config/*.sqlite"

# Verify DBPath is set in Backup table
ssh vps "sudo sqlite3 /var/lib/docker/volumes/duplicati_duplicati-config/_data/Duplicati-server.sqlite 'SELECT Name, DBPath FROM Backup;'"

# If DBPath is empty, update it:
ssh vps "sudo docker stop duplicati"
ssh vps "sudo sqlite3 /var/lib/docker/volumes/duplicati_duplicati-config/_data/Duplicati-server.sqlite \"UPDATE Backup SET DBPath='/config/VPS-Complete-Backup.sqlite' WHERE ID=2;\""
ssh vps "sudo docker start duplicati"
```

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
