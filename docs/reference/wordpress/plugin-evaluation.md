# Plugin Stack Evaluation for Fabrik Site Types

**Analysis Date:** 2024-12-24
**Site Types:** saas, company, content, landing, ecommerce (future)

---

## Evaluation Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Recommended - Add to preset |
| 🟡 | Conditional - Use if specific need |
| ⚪ | Skip - Fabrik handles or not needed |
| ❌ | Deprecated/Outdated - Don't use |
| 🔮 | Future - Phase 3+ consideration |

---

## Category-by-Category Evaluation

### VPN / Geo Testing (Lines 3-5)

| Tool | Verdict | Notes |
|------|---------|-------|
| Vyprn | ⚪ Skip | Not a WP plugin, use for manual testing |

---

### Code / Web Build Utilities (Lines 7-13)

| Tool | Verdict | Notes |
|------|---------|-------|
| Dirty Markup | ⚪ Skip | External tool, not WP |
| Adobe Animate CC | ⚪ Skip | Desktop tool |
| Adobe Dreamweaver | ⚪ Skip | Desktop tool |
| Adobe Acrobat Pro | ⚪ Skip | Desktop tool |

---

### Design / Photoshop (Lines 18-30)

| Tool | Verdict | Notes |
|------|---------|-------|
| All Photoshop tools | ⚪ Skip | Desktop tools, not WP plugins |

---

### WordPress Plugin Bundles (Lines 32-49)

| Plugin | Verdict | Site Types | Notes |
|--------|---------|------------|-------|
| MyThemeShop Updater | ⚪ Skip | - | We use GP Premium |
| My WP Backup Pro | ⚪ Skip | - | Fabrik R2 backups |
| WooCommerce Checkout Field Modifier | 🟡 Conditional | ecommerce | Only if WooCommerce |
| WooCommerce Products Already Added | 🟡 Conditional | ecommerce | Only if WooCommerce |
| WP Contact Widget | ⚪ Skip | - | GP Premium has this |
| WP Google Translate | ⚪ Skip | - | Use WPML instead |
| WP In Post Ads | 🟡 Conditional | content | Only if monetizing |
| WP Launcher | ⚪ Skip | - | Fabrik handles setup |
| **WP Mega Menu** | 🟡 Conditional | company | If complex navigation needed |
| **WP Notification Bar** | ✅ Recommended | saas, landing | Announcements, CTAs |
| **WP Review Pro** | 🟡 Conditional | content | Product reviews |
| WP Shortcode | ⚪ Skip | - | GP Premium has shortcodes |
| **WP Subscribe Pro** | ✅ Recommended | ALL | Email capture |
| WP Tab Widget Pro | ⚪ Skip | - | GP Premium handles |
| **WP Testimonials** | ✅ Recommended | company, saas | Trust building |
| **WP Time To Read** | ✅ Recommended | content | Engagement metric |

---

### WP Management (Lines 51-53)

| Tool | Verdict | Notes |
|------|---------|-------|
| ManageWP | ⚪ Skip | Fabrik CLI replaces this |

---

### Launch / Coming Soon (Lines 55-57)

| Plugin | Verdict | Site Types | Notes |
|--------|---------|------------|-------|
| **SeedProd Coming Soon Pro** | ✅ Recommended | landing | Pre-launch pages |

---

### Affiliate / Ecommerce Builders (Lines 59-73)

| Plugin | Verdict | Site Types | Notes |
|--------|---------|------------|-------|
| WP Dollar 3 | 🔮 Future | - | If building Amazon affiliate sites |
| Associate Goliath 5.0 | 🔮 Future | - | Amazon affiliate |
| WP Empire Builder 3.0 | 🔮 Future | - | Amazon affiliate |
| Content Egg Pro | 🔮 Future | content | Affiliate content aggregation |
| Ali Goliath | 🔮 Future | ecommerce | AliExpress dropship |

**Note:** These are specialized for affiliate/dropship sites. Evaluate when that site type is needed.

---

### Content Protection / Ads (Lines 75-78)

| Plugin | Verdict | Site Types | Notes |
|--------|---------|------------|-------|
| Smart Content Protector | 🟡 Conditional | content | If content theft is concern |
| AntiBlock Ads Manager | 🟡 Conditional | content | Only if ad-monetized |

---

### Ad Intelligence (Lines 80-85)

| Tool | Verdict | Notes |
|------|---------|-------|
| AdultAdSpy | ⚪ Skip | External SaaS, not WP |
| Adbeat | ⚪ Skip | External SaaS |
| WhatRunsWhere | ⚪ Skip | External SaaS |
| SocialAdNinja | ⚪ Skip | External SaaS |

---

### Affiliate Content Engines (Lines 87-90)

| Plugin | Verdict | Site Types | Notes |
|--------|---------|------------|-------|
| Affiliate Egg | 🔮 Future | content | Affiliate autoblogging |
| **Content Egg Pro** | 🔮 Future | content | Powerful for affiliate/comparison sites |

---

### AliExpress/Dropship (Lines 92-96)

| Plugin | Verdict | Notes |
|--------|---------|-------|
| Aliengine Store Builder | 🔮 Future | When ecommerce preset is built |
| Aliffiliate Advanced | 🔮 Future | Dropship sites |
| AliPlugin | 🔮 Future | Product import |

---

### Social Gating / Viral (Lines 98-106)

| Plugin | Verdict | Site Types | Notes |
|--------|---------|------------|-------|
| WP Sharely | 🟡 Conditional | content | Social-gate content |
| **TLDR** | ✅ Recommended | content | Summary button for long content |
| **Go Pricing** | ✅ Recommended | saas | Pricing tables - YOU HAVE THIS |
| WordPress Viral Quiz | 🟡 Conditional | content | If quiz/engagement focus |
| MyMail | ⚪ Skip | - | Use external (Resend) |
| Social Locker | 🟡 Conditional | content | Gate content for shares |
| **InstaShow** | 🟡 Conditional | company | Instagram feed |

---

### WP Security (Lines 108-114)

| Plugin | Verdict | Notes |
|--------|---------|-------|
| Hide My WP | ⚪ Skip | Overkill, we have wp-config hardening |
| Admin Rename Extender | ⚪ Skip | Not needed |
| Authentication Unique Keys | ⚪ Skip | Done in wp-config |
| Clef 2FA | ❌ Deprecated | Service shut down |
| Login Lockdown | ⚪ Skip | We use Limit Login Attempts |

---

### Booking / Membership / E-commerce (Lines 116-131)

| Plugin | Verdict | Site Types | Notes |
|--------|---------|------------|-------|
| **Bookly** | 🟡 Conditional | saas | If selling appointments |
| **S2Member** | 🟡 Conditional | saas | If membership/gated content |
| **WooCommerce** | ✅ Recommended | ecommerce | Core ecommerce |
| WooCommerce Restrict Shipping | 🟡 Conditional | ecommerce | Location restrictions |
| WooCommerce Gateways Country Limiter | 🟡 Conditional | ecommerce | Payment by country |
| **WooCommerce Subscriptions** | 🟡 Conditional | saas, ecommerce | Recurring payments |
| WooCommerce Extra Product Options | 🟡 Conditional | ecommerce | Complex products |
| WooCommerce Additional Variation Images | 🟡 Conditional | ecommerce | Product galleries |
| Variation Swatches | 🟡 Conditional | ecommerce | Better variation display |
| WooCommerce Checkout for Digital Goods | ✅ Recommended | saas | Simplified digital checkout |
| **Easy Digital Downloads** | 🟡 Conditional | saas | Alternative to WooCommerce for digital |
| WooCommerce Zapier | 🟡 Conditional | ecommerce | Automation |
| WooCommerce Wishlists | 🟡 Conditional | ecommerce | User wishlists |

---

### Content Display / Layout (Lines 133-147)

| Plugin | Verdict | Site Types | Notes |
|--------|---------|------------|-------|
| **Essential Grid** | ✅ Recommended | company, content | Portfolio/gallery grids |
| Theme Check | ⚪ Skip | Dev tool only |
| Thrive Content Builder | ⚪ Skip | Use Gutenberg + GP |
| **OptimizePress** | 🟡 Conditional | landing | Funnel builder |
| Beaver Builder | ⚪ Skip | Use Gutenberg + GP |
| Cornerstone | ⚪ Skip | Use Gutenberg + GP |
| Visual Composer | ⚪ Skip | Use Gutenberg + GP |
| MotoPress | ⚪ Skip | Use Gutenberg + GP |
| CSS Hero | ⚪ Skip | GP Customizer is enough |
| Lightbox Evolution | ⚪ Skip | GP/theme handles |
| **Foobox** | 🟡 Conditional | company | Better gallery lightbox |
| **Accordion FAQ** | ✅ Recommended | saas, company | FAQ sections |

---

### Tables / Data (Lines 149-152)

| Plugin | Verdict | Site Types | Notes |
|--------|---------|------------|-------|
| **TablePress** | ✅ Recommended | ALL | Responsive tables |
| **wpDataTables** | 🟡 Conditional | company, content | Advanced data/charts |

---

### Icons / Fonts (Lines 154-159)

| Plugin | Verdict | Notes |
|--------|---------|-------|
| Font Awesome Pro | ⚪ Skip | GP Premium includes icons |
| Entypo | ⚪ Skip | Not needed |
| Iconmonstr | ⚪ Skip | External resource |
| Google Fonts | ⚪ Skip | GP handles fonts |

---

### Translation / Multilingual (Lines 161-168)

| Plugin | Verdict | Site Types | Notes |
|--------|---------|------------|-------|
| Bablic | ⚪ Skip | WPML is better |
| **WPML** | ✅ Recommended | company, content | YOU HAVE THIS |
| Polylang | 🟡 Conditional | - | Free alternative to WPML |
| Ajax Translator Revolution | ⚪ Skip | WPML is better |
| Translation services | ⚪ Skip | External services |

---

### Chat / Support (Lines 170-175)

| Plugin | Verdict | Site Types | Notes |
|--------|---------|------------|-------|
| ClickDesk | ⚪ Skip | External SaaS |
| **TidioChat** | 🟡 Conditional | saas, company | Free tier available |
| Zadarma | ⚪ Skip | External phone service |

---

### Analytics / Tracking (Lines 177-184)

| Plugin | Verdict | Site Types | Notes |
|--------|---------|------------|-------|
| **Google Tag Manager** | ✅ Recommended | ALL | Central tracking |
| Clicky | ⚪ Skip | GA is standard |
| Google Analytics | ✅ via GTM | ALL | Use with GTM |
| Enhanced Ecommerce GA | 🟡 Conditional | ecommerce | WooCommerce tracking |
| Perfect Audience | ⚪ Skip | External retargeting |

---

### Performance / CDN (Lines 186-196)

| Plugin | Verdict | Notes |
|--------|---------|-------|
| MaxCDN | ⚪ Skip | Cloudflare handles CDN |
| WP Rocket | ⚪ Skip | Cloudflare + GP is enough |
| W3 Total Cache | ⚪ Skip | Cloudflare handles |
| **Kraken.io** | 🟡 Conditional | Image compression API |
| **WWW Image Optimizer** | ✅ Recommended | ALL - Local image optimization |
| Lazy Load XT | ⚪ Skip | Native WP lazy load |
| GTmetrix/Pingdom | ⚪ Skip | External testing tools |

---

### Backup / Migration (Lines 198-203)

| Plugin | Verdict | Notes |
|--------|---------|-------|
| UpdraftPlus | ⚪ Skip | Fabrik R2 backups |
| All-in-One WP Migration | ⚪ Skip | Fabrik handles |
| Duplicator | ⚪ Skip | Fabrik handles |
| CodeGuard | ⚪ Skip | Fabrik handles |

---

### Security (Lines 205-212)

| Plugin | Verdict | Notes |
|--------|---------|-------|
| Sucuri | ⚪ Skip | Cloudflare + our hardening |
| iThemes Security | ⚪ Skip | Overkill |
| Wordfence | ⚪ Skip | Overkill, resource heavy |
| Shield | ⚪ Skip | Limit Login is enough |
| BulletProof | ⚪ Skip | Overkill |

---

### Database / Maintenance (Lines 214-220)

| Plugin | Verdict | Site Types | Notes |
|--------|---------|------------|-------|
| **WP Sweep** | ✅ Recommended | ALL | DB cleanup |
| WP Optimize | ⚪ Skip | WP Sweep is cleaner |
| WP Performance Profiler | ⚪ Skip | Dev tool |
| P3 | ❌ Deprecated | Outdated |
| Easy Update Manager | ⚪ Skip | Fabrik handles updates |

---

### SEO / Schema (Lines 222-240)

| Plugin | Verdict | Site Types | Notes |
|--------|---------|------------|-------|
| Yoast | ⚪ Skip | Rank Math Pro is better |
| The SEO Framework | ⚪ Skip | Rank Math Pro |
| **SEO Post Content Links** | 🔮 Future | content | Auto internal linking - Phase 3 |
| Rankie | 🟡 Conditional | content | Rank tracking |
| Squirrly | ⚪ Skip | Rank Math handles |
| Schema plugins | ⚪ Skip | Rank Math Pro handles |
| **Page Links To** | 🟡 Conditional | ALL | External redirects |
| **Redirection** | ✅ Recommended | ALL | 301 management |
| Simple 301 Redirects | ⚪ Skip | Redirection is better |
| No Self Ping | ⚪ Skip | Minor |
| **Breadcrumb NavXT** | 🟡 Conditional | company, content | If theme lacks |

---

### Social Sharing (Lines 242-248)

| Plugin | Verdict | Site Types | Notes |
|--------|---------|------------|-------|
| addtoany | ⚪ Skip | Rank Math has this |
| Easy Social Share Buttons | 🟡 Conditional | content | Advanced sharing |
| Social Warfare | 🟡 Conditional | content | Share counts |
| **Hello Bar** | ✅ Recommended | landing, saas | CTA bars |
| **OneSignal** | 🟡 Conditional | content | Push notifications |

---

### Affiliate Links (Lines 250-256)

| Plugin | Verdict | Site Types | Notes |
|--------|---------|------------|-------|
| WP Profit Redirect | 🔮 Future | content | Split testing |
| **ThirstyAffiliates** | 🔮 Future | content | Link management |
| Elflink | ⚪ Skip | Outdated approach |
| **Ad Inserter** | 🟡 Conditional | content | Ad placement |

---

### Social Automation (Lines 258-264)

| Plugin | Verdict | Notes |
|--------|---------|-------|
| Massplanner | ❌ Deprecated | Shut down |
| Social Rabbit | 🟡 Conditional | Social automation |
| **NextScripts SNAP** | 🟡 Conditional | Auto-post to social |
| SocialPilot | ⚪ Skip | External SaaS |

---

### Content Research (Lines 266-279)

| Tool | Verdict | Notes |
|------|---------|-------|
| BuzzSumo | ⚪ Skip | External SaaS |
| **WordPress Popular Posts** | ✅ Recommended | content - Internal linking |
| CoSchedule | ⚪ Skip | External SaaS |
| SpinnerChief | ❌ Deprecated | Use AI instead |
| WordAI | 🔮 Future | Phase 3 AI integration |
| The Best Spinner | ❌ Deprecated | Use AI |
| Copyscape | ⚪ Skip | External tool |

---

### Domain / URL (Lines 281-288)

| Tool | Verdict | Notes |
|------|---------|-------|
| FreshDrop | ⚪ Skip | External domain service |
| Bitly | ⚪ Skip | External service |
| WP Bitly | 🟡 Conditional | Link tracking |

---

### Misc (Lines 296-310)

| Plugin | Verdict | Site Types | Notes |
|--------|---------|------------|-------|
| WP Job Manager | 🟡 Conditional | company | Job listings |
| bbPress | 🟡 Conditional | saas | Forums |
| BuddyPress | 🟡 Conditional | saas | Community |
| PayU Turkey | 🟡 Conditional | ecommerce | Turkish payments |
| **Privacy Policy Generator** | ✅ Recommended | ALL | Legal compliance |

---

## FINAL RECOMMENDATIONS BY SITE TYPE

### ALL Sites (Baseline)

```yaml
plugins:
  install:
    - limit-login-attempts-reloaded  # Security
    - redirection                     # 301s
    - wp-mail-smtp                    # Email
    - tablepress                      # Tables
    - wp-sweep                        # DB cleanup
  premium:
    - gp-premium.zip                  # Theme features
```

### `saas` Preset

```yaml
plugins:
  install:
    # Baseline +
    - accordion-faq                   # FAQ sections
    - wp-notification-bar             # Announcements
    - wp-subscribe-pro                # Email capture
    - wp-testimonials                 # Trust
  premium:
    - rank-math-pro.zip               # SEO
    - go-pricing.zip                  # Pricing tables
    - hello-bar.zip                   # CTA popups (if you have)
```

### `company` Preset

```yaml
plugins:
  install:
    # Baseline +
    - accordion-faq
    - wp-testimonials
    - breadcrumb-navxt                # If needed
  premium:
    - rank-math-pro.zip
    - wpml-cms.zip                    # Multilingual
    - wpml-string-translation.zip
    - essential-grid.zip              # Portfolios (if you have)
```

### `content` Preset

```yaml
plugins:
  install:
    # Baseline +
    - wp-time-to-read                 # Reading time
    - wordpress-popular-posts         # Internal linking
    - tldr                            # Summary button (if you have)
  premium:
    - rank-math-pro.zip
    - wpml-cms.zip                    # If multilingual
```

### `landing` Preset

```yaml
plugins:
  install:
    # Baseline (minimal) +
    - wp-notification-bar
  premium:
    - hello-bar.zip                   # CTA (if you have)
    - seedprod-coming-soon-pro.zip    # Pre-launch (if you have)
```

---

## PLUGINS TO PLACE IN /opt/fabrik/templates/wordpress/plugins/premium/

**Core (confirmed):**
- [x] gp-premium.zip ✅ Placed
- [x] rank-math-pro.zip ✅ Placed
- [ ] go-pricing.zip ← Place this
- [ ] wpml-cms.zip ← Place this
- [ ] wpml-string-translation.zip ← Place this

**Available (confirmed by user):**
- [ ] essential-grid.zip ✅ Has
- [ ] seedprod-coming-soon-pro.zip ✅ Has
- [ ] thrive-leads.zip ✅ Has (replaces Hello Bar, WP Subscribe Pro)
- [ ] convert-pro.zip ✅ Has (popups, modals, CTAs)
- [ ] real-testimonials-pro.zip ✅ Has (replaces WP Testimonials)
- [ ] wp-table-builder-pro.zip ✅ Has (replaces TablePress Pro)
- [ ] content-egg-pro.zip ✅ Has (affiliate content - Phase 3)

---

## PHASE 3 CONSIDERATIONS (AI Content)

These plugins are relevant for Phase 3 AI integration:

| Plugin | Purpose |
|--------|---------|
| SEO Post Content Links | Auto internal linking |
| WordAI API | Content rewriting |
| Content Egg Pro | Affiliate content aggregation |
| ThirstyAffiliates | Affiliate link management |

---

## NOT NEEDED (Fabrik Handles)

| Category | Plugin | Fabrik Alternative |
|----------|--------|-------------------|
| Backups | UpdraftPlus | R2 sidecar |
| Security | Wordfence, iThemes | wp-config hardening + Cloudflare |
| Caching | WP Rocket, W3TC | Cloudflare |
| CDN | MaxCDN | Cloudflare |
| Migration | Duplicator | Docker volumes |
| Management | ManageWP | Fabrik CLI |
| SSL | Various | Traefik + Let's Encrypt |
