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

### 5. Code Quality

- [ ] **All tests pass** (`pytest` / `npm test`)
- [ ] **Lint clean** (`ruff check .` / `eslint .`)
- [ ] **Type check clean** (`mypy .` / `tsc --noEmit`)
- [ ] **No TODO/FIXME** in critical paths
- [ ] **Error handling** covers all API endpoints
- [ ] **Logging** captures errors with context

### 6. Documentation

- [ ] **README.md** has quick start that works
- [ ] **CONFIGURATION.md** documents all env vars
- [ ] **API documentation** accurate (if API product)
- [ ] **CHANGELOG.md** updated with release notes

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

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Developer | | | |
| Reviewer (optional) | | | |

---

**Template Version:** 1.0.0
**Source:** `/opt/fabrik/templates/docs/LAUNCH_CHECKLIST_TEMPLATE.md`
