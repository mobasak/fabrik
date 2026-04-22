# Authelia Phase 12A Completion Report

**Date:** 2026-04-17 23:09 (UTC+3)
**Status:** ✅ COMPLETE
**Phase:** 12A - Test Instance Deployment

---

## Executive Summary

Successfully deployed Authelia test instance via Coolify API after resolving API URL configuration issue.

**Key Achievement:** First Authelia instance managed by Coolify, running in parallel with standalone production instance.

---

## Deployment Details

| Item | Value |
|------|-------|
| **Method** | Coolify API (`create_dockercompose_application`) |
| **UUID** | fgok8kcg4k400g8gc8wsk0kc |
| **Container** | authelia-fgok8kcg4k400g8gc8wsk0kc |
| **Volume** | fgok8kcg4k400g8gc8wsk0kc_authelia-config |
| **Domain** | https://auth-test.vps1.ocoron.com |
| **Status** | ✅ Running (healthy) |
| **Deployed** | 2026-04-17 23:04 UTC+3 |

---

## Issue Resolved: Coolify API URL

### Problem
Initial deployment failed with `405 Method Not Allowed` when using `http://localhost:8002` from `.env` file.

### Root Cause
- `.env` configured with `COOLIFY_API_URL=http://localhost:8002` (expects SSH tunnel)
- No SSH tunnel was running
- API calls failed with 405 error

### Solution
Used external URL directly: `https://coolify.vps1.ocoron.com/api/v1`

```python
# Working code
coolify_url = "https://coolify.vps1.ocoron.com/api/v1"
client = CoolifyClient(base_url=coolify_url, token=token)
```

### Lesson Learned
When deploying via Coolify API from WSL:
- Use external URL: `https://coolify.vps1.ocoron.com/api/v1`
- OR establish SSH tunnel: `ssh -L 8002:localhost:8000 vps`
- Document which approach is standard for Fabrik

---

## Configuration Migration

### Files Copied
1. `configuration.yml` - All Authelia settings
2. `users_database.yml` - Username/password hash
3. `db.sqlite3` - Sessions, 2FA secrets (311KB)

### Method
```bash
# Stop container
docker stop authelia-fgok8kcg4k400g8gc8wsk0kc

# Copy via temporary Alpine container
docker run --rm \
  -v fgok8kcg4k400g8gc8wsk0kc_authelia-config:/target \
  -v /opt/authelia/config:/source \
  alpine sh -c 'cp /source/*.yml /target/ && cp /source/db.sqlite3 /target/'

# Restart
docker start authelia-fgok8kcg4k400g8gc8wsk0kc
```

---

## Validation

### Container Health
```bash
$ docker ps | grep authelia-fgok8kcg4k400g8gc8wsk0kc
64e87c0e43d2   authelia/authelia:latest   Up 36 seconds (healthy)
```

### Logs
```
time="2026-04-17T23:09:09+03:00" level=info msg="Startup complete"
time="2026-04-17T23:09:09+03:00" level=info msg="Listening for non-TLS connections on '[::]:9091'"
```

### SSL Certificate
- Status: Provisioning (Let's Encrypt via Traefik)
- Expected: 2-3 minutes
- Domain: auth-test.vps1.ocoron.com

---

## Testing Instructions

### Login Test
1. Wait 2-3 minutes for SSL cert provisioning
2. Open: https://auth-test.vps1.ocoron.com
3. Login with EXISTING username/password
4. Enter code from EXISTING TOTP app (Google Authenticator/Authy)
5. Should work identically to production

### Expected Behavior
- ✅ Same username/password works
- ✅ Same 2FA TOTP codes work
- ✅ Session persistence works
- ✅ Access control rules identical

### Production Status
- ✅ Standalone Authelia still running at auth.vps1.ocoron.com
- ✅ All dashboards still protected
- ✅ Zero impact on production

---

## Next Steps

### Phase 12B: IP Bypass
1. Add WSL IP to bypass rules in both instances
2. Test bypass works
3. Verify ForwardAuth with test instance

### Phase 12C: Production Cutover
1. Stop standalone Authelia
2. Update test instance domain to `auth.vps1.ocoron.com`
3. Update all dashboard middleware
4. Verify all 8 dashboards accessible

---

## Files to Update

### Documentation
- [ ] COOLIFY_STATUS.md - Add test instance status
- [ ] MIGRATION_SUMMARY.md - Update Phase 12A complete
- [ ] CHANGELOG.md - Add Phase 12A entry
- [ ] LESSONS_LEARNT.md - Add Coolify API URL lesson

### Configuration
- [ ] Update `.env` with recommended COOLIFY_API_URL
- [ ] Document SSH tunnel vs external URL decision

---

## Metrics

| Metric | Value |
|--------|-------|
| Deployment Time | ~5 minutes (including troubleshooting) |
| Downtime | 0 minutes (parallel deployment) |
| Config Files | 3 files, 313KB total |
| Container Restarts | 2 (initial + after config copy) |
| API Calls | 1 (create_dockercompose_application) |

---

## Success Criteria

- [x] Test instance deployed via Coolify API
- [x] Container running and healthy
- [x] Config files migrated successfully
- [x] Production unaffected
- [x] SSL provisioning in progress
- [ ] Login test (pending SSL cert)
- [ ] 2FA test (pending SSL cert)

---

**Status:** Phase 12A COMPLETE. Ready for validation testing and Phase 12B.

**Last Updated:** 2026-04-17 23:10 (UTC+3)
