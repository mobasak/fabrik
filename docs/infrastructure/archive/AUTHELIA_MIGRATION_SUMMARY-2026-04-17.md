# Authelia Migration Summary

**Date:** 2026-04-17 22:45 (UTC+3)
**Status:** Ready to Execute
**Prepared by:** Windsurf Cascade

---

## Executive Decision

**MIGRATE AUTHELIA TO COOLIFY** ✅

Your analysis was correct - keeping Authelia standalone contradicts the unified Coolify/Backrest architecture.

---

## Deliverables

| File | Purpose | Status |
|------|---------|--------|
| `docs/infrastructure/authelia-migration-plan.md` | Complete 400-line migration guide | ✅ Created |
| `scripts/migrate-authelia-to-coolify.sh` | Automated 3-phase migration script | ✅ Created |
| `specs/infrastructure/authelia-coolify.yaml` | Coolify-ready Docker Compose | ✅ Created |
| `CHANGELOG.md` | Migration plan entry | ✅ Updated |
| VPS Backup | `/tmp/authelia-backup-20260417-224123.tar.gz` | ✅ Created |

---

## Migration Phases

### Phase 12A: Test Instance (30 min)
- Deploy on `auth-test.vps1.ocoron.com`
- Copy config files
- Verify 2FA works
- **Risk:** None (production unaffected)

### Phase 12B: IP Bypass (15 min)
- Add WSL IP bypass to both instances
- Safety net for cutover
- **Risk:** Low (reversible)

### Phase 12C: Production Cutover (20 min)
- Stop standalone
- Switch domain to production
- Verify all dashboards
- **Risk:** Medium (< 2 min rollback)

---

## Safety Measures

1. **Automatic Backup:** Created before any changes
2. **Parallel Run:** Test instance runs alongside production
3. **IP Bypass:** WSL can access dashboards without 2FA during migration
4. **SSH Tunnel:** Direct Coolify UI access bypassing Authelia
5. **Rollback Script:** One command restores standalone

---

## Execution Commands

```bash
# Phase 12A: Test
cd /opt/fabrik
./scripts/migrate-authelia-to-coolify.sh test

# Phase 12B: Bypass
./scripts/migrate-authelia-to-coolify.sh bypass

# Phase 12C: Cutover
./scripts/migrate-authelia-to-coolify.sh cutover

# Rollback (if needed)
./scripts/migrate-authelia-to-coolify.sh rollback
```

---

## Benefits

### Operational
- ✅ Unified backup via Backrest (auto-includes config + SQLite)
- ✅ Centralized secrets in Coolify UI
- ✅ Simplified Traefik integration (internal service names)
- ✅ Consistent management (29/29 services = 100%)

### Technical
- ✅ No separate backup cron jobs
- ✅ No manual config file sync
- ✅ No bridge networking complexity
- ✅ Volume management by Coolify

---

## Current State

**Authentication Backend:** File-based (`users_database.yml`)
**Storage:** SQLite (`db.sqlite3`)
**Config Files:** 4 files (configuration.yml, users_database.yml, db.sqlite3, notification.txt)
**Protected Dashboards:** 8 services (Coolify, n8n, Grafana, Netdata, Backrest, Apprise, GlitchTip, others)

---

## Post-Migration Tasks

After successful cutover:

1. Test all 8 dashboards
2. Remove IP bypass from config
3. Test 2FA from incognito browser
4. Update COOLIFY_STATUS.md (29/29 services)
5. Update AGENTS.md (Authelia now Coolify-managed)
6. Verify Backrest includes Authelia in next backup
7. Add Gatus health check
8. Remove old files after 7 days

---

## Estimated Timeline

| Phase | Duration | Downtime |
|-------|----------|----------|
| 12A: Test | 30 min | 0 min |
| 12B: Bypass | 15 min | 0 min |
| 12C: Cutover | 20 min | ~1 min |
| **Total** | **65 min** | **~1 min** |

---

## Success Criteria

- [ ] Test instance deployed and healthy
- [ ] Can login with existing credentials on test domain
- [ ] 2FA TOTP works on test instance
- [ ] IP bypass configured and tested
- [ ] Production domain switched successfully
- [ ] All 8 dashboards accessible
- [ ] 2FA required from incognito browser
- [ ] No Traefik errors in logs
- [ ] Authelia container healthy in Coolify

---

## Rollback Capability

**Trigger:** Any failure during cutover
**Command:** `./scripts/migrate-authelia-to-coolify.sh rollback`
**Time:** < 2 minutes
**Result:** Standalone Authelia restored, all dashboards accessible

---

## Owner Notes

**Your analysis was spot-on:**
- Keeping Authelia standalone creates a "management island"
- Contradicts the unified Coolify/Backrest architecture
- Solo operator needs maximum automation and consistency

**The only valid concern (Coolify-itself protection) is addressed:**
- SSH tunnel backdoor: `ssh -L 8000:localhost:8000 vps`
- Direct access even if Authelia/Traefik are down

**Ready to execute when you are.** The script will guide you through each step with clear prompts and safety checks.

---

**Last Updated:** 2026-04-17 22:45 (UTC+3)
