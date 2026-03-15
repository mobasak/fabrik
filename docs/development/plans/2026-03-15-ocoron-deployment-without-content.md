# ocoron.com Deployment Without Content Creation

**Status:** IN_PROGRESS  
**Date:** 2026-03-15  
**Type:** Execution Plan

---

## Goal

Deploy ocoron.com WordPress site with full structure (pages, menus, plugins, theme) but without AI-generated content. Content creation is handled by separate SEO/content modules currently under development.

---

## DONE WHEN

- [x] Understand deployment workflow (plan → apply → verify)
- [ ] Execute `fabrik wp plan ocoron.com` successfully
- [ ] Review generated build artifacts
- [ ] Execute dry-run deployment
- [ ] Deploy to production (structure only)
- [ ] Verify deployment with health checks
- [ ] Document WPML manual setup steps
- [ ] Document any issues encountered

---

## Out of Scope

- AI content generation (handled by `/opt/seo` module)
- WordPress content population (manual or via separate content API)
- WPML translation content (structure only, translations via wp-admin)
- Custom theme development (using GeneratePress preset)

---

## Deployment Approach: Content-Agnostic Structure

### Key Design Decision

The WordPress deployer is **already designed** for content-agnostic deployment:

1. **Spec Configuration:** `content.source: manual` in `specs/sites/ocoron.com.yaml`
2. **Pages Stage Behavior:** Creates page structure with placeholder content only
3. **No WP_ADMIN_PASSWORD:** When this env var is absent, REST API client is `None`, pages stage skips content creation
4. **Idempotency:** Each stage tracks checksums, only re-runs when spec changes

---

## Deployment Workflow

### Step 1: Generate Build Plan

```bash
cd /opt/fabrik
fabrik wp plan ocoron.com
```

**Output:**
```
.builds/ocoron.com/
├── plan.json                      # Per-stage hashes, skip flags
├── blueprint.resolved.yaml        # Merged spec (company preset + ocoron overrides)
└── manifests/
    ├── plugins.json               # Plugin list (WPML, Rank Math, Thrive, etc.)
    ├── pages.json                 # Page structure (Home, Services, About, etc.)
    └── checks.yaml                # Health check definitions
```

**Verification:**
- `plan.json` contains 10-12 stages with unique hashes
- `blueprint.resolved.yaml` includes company preset defaults merged with ocoron.com.yaml
- `manifests/plugins.json` includes ~15 plugins from company preset + additions

---

### Step 2: Dry-Run Deployment

```bash
fabrik wp apply ocoron.com --dry-run
```

**Purpose:**
- Validate Coolify API connectivity
- Check plugin license availability (WPML, Rank Math Pro, etc.)
- Verify DNS configuration
- Preview stage execution plan

**Expected Output:**
```
🔍 DRY-RUN MODE: No changes will be made

Stage 1/10: dns          ✅ ocoron.com DNS verified
Stage 2/10: settings     ✅ Would configure site title, timezone, permalinks
Stage 3/10: theme        ✅ Would install GeneratePress + child theme
Stage 4/10: plugins      ✅ Would install 15 plugins
Stage 5/10: languages    ✅ Would install tr_TR locale
Stage 6/10: pages        ✅ Would create 17 page stubs
Stage 7/10: menus        ✅ Would create primary + footer menus
Stage 8/10: forms        ✅ Would configure Fluent Forms
Stage 9/10: seo          ✅ Would apply Rank Math settings, GA4
Stage 10/10: verify      ✅ Would run 9 health checks

✅ Dry-run complete: 10 stages validated
```

---

### Step 3: Production Deployment

```bash
fabrik wp apply ocoron.com
```

**What Happens Per Stage:**

| Stage | Action | Content Created | Notes |
|-------|--------|-----------------|-------|
| **dns** | Verify Cloudflare DNS | None | Checks A/CNAME records for ocoron.com |
| **settings** | Configure WordPress | Site settings | Title: "Ocoron", tagline, permalinks, timezone: Europe/Istanbul |
| **theme** | Install theme | Theme files | GeneratePress + child theme with custom settings |
| **plugins** | Install plugins | Plugin files | WPML, Rank Math Pro, Thrive Architect, FluentCRM, Complianz, etc. |
| **languages** | Install locale | tr_TR language pack | Warns: "Complete WPML setup manually in wp-admin" |
| **pages** | Create structure | **17 placeholder pages** | Home, Services (+ 15 subpages), About, Insights, Contact, Privacy, Terms |
| **menus** | Create menus | Navigation structure | Primary menu (Services dropdown), Footer menu |
| **forms** | Setup forms | Contact form | Fluent Forms with fields: name, email, company, subject, message |
| **seo** | Apply SEO config | Meta settings | Rank Math: title, description, schema, GA4 (G-VK6FMQRVRL) |
| **verify** | Health checks | Verification report | 9 checks: DNS, SSL, sitemap, REST API, admin access, etc. |

**Page Structure Created (17 pages):**

```
Home (/)
Services (/services)
├── Investment Incentives (/services/investment-incentives)
├── Foreign Trade (/services/foreign-trade)
├── AI Consultancy (/services/ai-consultancy)
├── Manufacturing (/services/manufacturing)
├── Logistics (/services/logistics)
├── B2B Marketing (/services/b2b-marketing)
├── Medical Procurement (/services/medical-procurement)
├── Quality Management (/services/quality-management)
├── Company Registration (/services/company-registration)
├── Virtual Office (/services/virtual-office)
├── Tekmer Support (/services/tekmer-support)
├── E-commerce Integration (/services/ecommerce-integration)
├── Supplier Network (/services/supplier-network)
├── Global Sourcing (/services/global-sourcing)
└── US Company Formation (/services/us-company-formation)
About (/about)
Insights (/insights) — Blog index
Contact (/contact)
Privacy Policy (/privacy-policy)
Terms of Service (/terms)
```

**IMPORTANT: Page Content**
- Each page has **placeholder content only**
- Headings, slugs, menu placement are correct
- Body content is empty or generic placeholder text
- Ready for content population via SEO/content modules

---

### Step 4: Verify Deployment

```bash
fabrik wp verify ocoron.com
```

**Health Checks:**
1. DNS resolution (A record → VPS IP)
2. SSL certificate valid (Let's Encrypt)
3. HTTP 200 on homepage
4. WordPress REST API accessible
5. wp-admin login functional
6. Rank Math sitemap generated (`/sitemap_index.xml`)
7. WPML language switcher present
8. Contact form renders
9. Analytics code injected (GA4)

**Expected Output:**
```
✅ DNS: ocoron.com resolves to VPS1 IP
✅ SSL: Certificate valid, issued by Let's Encrypt
✅ HTTP: Homepage returns 200
✅ REST API: /wp-json/ accessible
✅ Sitemap: Rank Math sitemap generated
✅ WPML: Language switcher detected
✅ Forms: Fluent Forms contact form renders
✅ Analytics: GA4 tracking code present
✅ Admin: wp-admin accessible
```

---

## WPML Manual Setup (Required)

### Why Manual Setup?

The `languages` stage installs WPML plugins and tr_TR locale, but **does not configure translation workflows** because:
1. Translation structure depends on content existence
2. WPML editor assignment requires human decision
3. String translation needs content context

### Post-Deployment Steps

1. **Log into wp-admin:**
   ```
   URL: https://ocoron.com/wp-admin
   User: contact@ocoron.com
   Password: [from deployment output]
   ```

2. **Go to WPML → Languages:**
   - Verify primary language: English (EN)
   - Verify secondary language: Turkish (TR)
   - URL format: Different languages in directories (`/tr/`)

3. **Configure Translation Management:**
   - Go to WPML → Translation Management
   - Assign translators (if applicable)
   - Set translation workflow (manual, automatic, or none)

4. **Translate Pages (After Content Population):**
   - Edit any page
   - Click "Translate" button (WPML adds this)
   - Paste Turkish content
   - Save

5. **Translate Strings:**
   - Go to WPML → String Translation
   - Translate site tagline, menu items, form labels

---

## Re-Running Stages After Content Ready

### Force Re-Run Pages Stage

When SEO/content modules generate content:

```bash
fabrik wp apply ocoron.com --force-stage pages
```

**What happens:**
- Bypasses idempotency check for pages stage
- Re-creates pages with new content
- Other stages remain skipped (unchanged)

### Force Re-Run SEO Stage

When meta descriptions updated:

```bash
fabrik wp apply ocoron.com --force-stage seo
```

---

## Issue Documentation Protocol

**Before solving any issue:**

1. **Document the issue:**
   - What command was run
   - Expected vs actual output
   - Error messages (full text)
   - Relevant logs/stack traces

2. **Create issue document:**
   ```
   docs/development/plans/issues/YYYY-MM-DD-issue-<slug>.md
   ```

3. **Diagnose root cause:**
   - Check stage logs in `.builds/ocoron.com/logs/`
   - Review Coolify deployment logs
   - Verify DNS/SSL configuration

4. **Propose fix:**
   - Document proposed solution
   - Test in dry-run mode first
   - Apply fix
   - Verify resolution

5. **Update this plan:**
   - Add issue to "Issues Encountered" section below
   - Link to issue document

---

## Issues Encountered

### Issue Template

```markdown
### [YYYY-MM-DD] Issue Title

**Stage:** [stage name]
**Severity:** [BLOCKER | MAJOR | MINOR]

**Symptom:**
[What went wrong]

**Root Cause:**
[Why it happened]

**Fix Applied:**
[What was done to resolve]

**Verification:**
[How we confirmed it's fixed]

**Link:** [docs/development/plans/issues/YYYY-MM-DD-issue-slug.md]
```

---

## Deployment Checklist

### Pre-Deployment
- [x] Spec file validated (`specs/sites/ocoron.com.yaml`)
- [x] `content.source: manual` confirmed
- [x] SEO metadata complete (title, description, GA4 ID)
- [x] Logo files exist in `specs/sites/ocoron.com-media/`
- [ ] Cloudflare DNS configured for ocoron.com
- [ ] VPS1 Coolify accessible
- [ ] WPML license key available
- [ ] Rank Math Pro license key available
- [ ] Thrive Architect license key available

### Post-Deployment
- [ ] All 10 stages completed successfully
- [ ] Health checks pass (9/9)
- [ ] WPML configured in wp-admin
- [ ] Editor account credentials saved
- [ ] Deployment report generated
- [ ] Handoff document created

---

## Next Steps

1. **Execute `fabrik wp plan ocoron.com`**
2. **Review generated build artifacts**
3. **Execute dry-run deployment**
4. **Document any validation errors**
5. **Proceed to production deployment**
6. **Complete WPML manual setup**
7. **Wait for SEO/content modules to complete**
8. **Re-run pages stage with real content**

---

## References

- Spec: `specs/sites/ocoron.com.yaml`
- Content Plan: `specs/sites/ocoron.com-content-plan.md`
- SEO Module: `/opt/seo/`
- WordPress Deployer: `src/fabrik/wordpress/deployer.py`
- Stage Implementations: `src/fabrik/wordpress/stages/`
