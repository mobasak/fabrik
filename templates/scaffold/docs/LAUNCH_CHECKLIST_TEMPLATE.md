# Launch Checklist

**Project:** [PROJECT_NAME]
**Target Launch Date:** YYYY-MM-DD
**Version:** X.Y.Z

---

## Pre-Launch Checklist

Complete ALL items before going live. No exceptions.

---

### 1. Environment & Infrastructure

- [ ] **Server configured** (systemd service or container)
- [ ] **Reverse proxy** configured (nginx/caddy) with SSL
- [ ] **SSL certificates** installed and auto-renewing
- [ ] **Firewall rules** set (ufw - only required ports open)
- [ ] **Domain DNS** configured and propagated
- [ ] **Environment variables** set (not in repo, not hardcoded)

### 2. Monitoring & Alerts

- [ ] **Health endpoint** (`/health`) returns 200 when healthy
- [ ] **Health check monitored** (uptime service or cron)
- [ ] **Error alerts** configured (email/SMS/Slack on CRITICAL)
- [ ] **Disk space alert** (>80% triggers warning)
- [ ] **Process restart on crash** (systemd restart policy or watchdog)
- [ ] **Log rotation** configured (prevent disk fill)

### 3. Data Safety

- [ ] **Database backup** automated (daily minimum)
- [ ] **Backup restoration TESTED** (backups are useless until proven)
- [ ] **Backup retention policy** defined (7/30/90 days)
- [ ] **.env file backed up** separately (not in repo)
- [ ] **Secrets rotated** from development values

### 4. Performance & Security

- [ ] **No debug mode** in production
- [ ] **Database indexes** on frequent query columns
- [ ] **Connection pooling** enabled
- [ ] **Rate limiting** on public endpoints
- [ ] **SQL injection** tested (parameterized queries)
- [ ] **XSS tested** (if web UI)
- [ ] **CORS policy** configured correctly
- [ ] **Auth tokens** have expiration

### 5. Code Quality (Agent Contract)

**⚙️ AUTOMATED GATES:** Agent completion contract (4 steps) from `AGENTS-compact.md`.

#### Quality Gate (Standard for all tasks)
```bash
python scripts/final_gate.py --lean --json
```

- [ ] **Tier 1 checks:** Ruff, mypy, secrets, schema sync, changelog → PASS
- [ ] **JSON output:** `"status": "success"`
- [ ] Gate auto-staged changes

#### Full Gate (Milestone/batch closure only)
```bash
python scripts/final_gate.py --json
```

- [ ] **Tier 2 checks:** All Tier 1 + 16 additional consistency checks → PASS
- [ ] **Exit code:** 0

**Manual Checks:**
- [ ] **All tests pass** (`pytest` / `npm test`)
- [ ] **No TODO/FIXME** in critical paths
- [ ] **Error handling** covers all API endpoints
- [ ] **Logging** captures errors with context

**Optional Tools (use only if explicitly needed):**
- Kilo Review: `python scripts/kilo_code_review.py staged --plan "..." --output json`
- Documentator: `python scripts/kilo_docs_enforcer.py --auto-generate --verbose`

### 6. Documentation

**Required (written by agents, gate-enforced):**
- [ ] **CHANGELOG.md** updated with release notes
- [ ] **README.md** has quick start that works (test it)
- [ ] **.env.example** has all variables with comments
- [ ] **PORTS.md** registered (MANDATORY — checked by final_gate.py)

**If applicable:**
- [ ] **API documentation** for new endpoints/functions
- [ ] **CONFIGURATION.md** explains HOW to get credentials

---

## Product Launch Checklist

### 7. Value Proposition

- [ ] **One-line value prop** clear and visible
- [ ] **Pricing page** live (if paid product)
- [ ] **Onboarding flow** gets user to first value in <3 minutes

### 8. User Experience

- [ ] **Error messages** are user-friendly (not stack traces)
- [ ] **Request ID** shown to users for support ("Contact us with ID: xxx")
- [ ] **Loading states** for slow operations
- [ ] **Mobile responsive** (if web app)

### 9. Legal & Compliance

- [ ] **Terms of Service** page exists
- [ ] **Privacy Policy** page exists
- [ ] **Cookie consent** (if EU users / using cookies)
- [ ] **GDPR data export/delete** capability (if EU users)

### 10. Growth & Analytics

- [ ] **Landing page** with single clear CTA
- [ ] **Analytics** tracking page views and key events
- [ ] **One distribution channel** chosen and ready
- [ ] **Feedback mechanism** exists (email, form, or in-app)

---

## Post-Launch Verification

### Immediately After Deploy

- [ ] Site loads correctly
- [ ] Health endpoint returns 200
- [ ] Can complete primary user action
- [ ] Errors are being logged
- [ ] Alerts are working (trigger test alert)

### Within 24 Hours

- [ ] Check error logs for unexpected issues
- [ ] Verify backup ran successfully
- [ ] Review any user feedback
- [ ] Check resource usage (CPU, memory, disk)

---

## Rollback Plan

If critical issues found:

1. **Immediate:** Revert to previous deployment
2. **Database:** Migrations are forward-only; create new migration to fix
3. **DNS:** Keep old server running for 24h as fallback
4. **Communication:** Have status page or email ready

---

## Human Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Developer | | | |
| Reviewer (optional) | | | |

---

**Template Version:** 2.0.0 (Fabrik Workflow Integrated)
