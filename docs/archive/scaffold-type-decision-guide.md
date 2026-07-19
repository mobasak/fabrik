# Scaffold Type Decision Guide

**Purpose:** Human-facing reference for choosing between WordPress, Docusaurus, and static-site scaffold types. Not injected into agent context.

---

## Quick Decision Matrix

| Question | WordPress | Docusaurus | Static Site |
|----------|-----------|------------|-------------|
| **Who writes content?** | Non-technical clients, marketing teams | Developers, technical writers | You (solo dev) |
| **Content type?** | Blog, e-commerce, CMS-driven pages | API docs, knowledge base, dev portal | Landing page, portfolio, one-pager |
| **Needs WYSIWYG editor?** | Yes | No | No |
| **Needs e-commerce?** | Yes (WooCommerce) | No | No |
| **Needs versioned docs?** | No | Yes (Git branch archiving) | No |
| **Needs interactive API playground?** | No | Yes (Scalar) | No |
| **Content update frequency?** | Daily/weekly by non-devs | Per release by devs | Rarely, by you |
| **Database required?** | Yes (MariaDB) | No (static output) | No (static output) |
| **Framework** | WordPress + PHP-FPM + Nginx | Docusaurus v3 (React/MDX) | Next.js 14 / plain HTML |
| **Docker pattern** | WP container + MariaDB + Redis + Nginx | Node build → Nginx static serve | Node build → Nginx static serve |

## Routing Rules

### Use `wordpress` when:
- Client or non-technical stakeholders create/edit content via a visual editor
- E-commerce is needed (WooCommerce for physical/digital goods)
- Multi-language content managed by non-developers (Polylang)
- Headless CMS backend feeding a Next.js frontend (WPGraphQL)
- Marketing sites, lead generation pages, client deliverables

### Use `docusaurus` when:
- Developer-authored documentation (API reference, SDK guides, changelogs)
- Technical knowledge base or internal dev portal
- Content is Markdown/MDX authored in an IDE, not a CMS
- Interactive API playground needed (Scalar integration)
- Versioned documentation across product releases

### Use `static-site` when:
- Landing page or single product marketing page you control fully
- Portfolio or personal site
- Simple one-pager with no CMS, no docs framework overhead
- You want Next.js features (ISR, dynamic routes) but not Docusaurus structure
- No non-technical editors involved

## Fabrik Use Cases

| Project | Scaffold Type | Rationale |
|---------|---------------|-----------|
| Product marketing site for a SaaS | `static-site` | Solo dev controls all content, no CMS needed |
| Client e-commerce store | `wordpress` | WooCommerce, client manages products/orders |
| Fabrik platform documentation | `docusaurus` | Dev-authored, versioned, API playground |
| Client blog / content site | `wordpress` | Non-technical editors need WYSIWYG |
| API reference for a microservice | `docusaurus` | OpenAPI spec + Scalar interactive docs |
| Event landing page | `static-site` | Simple one-pager, no framework overhead |
| Multi-language magazine | `wordpress` | Polylang + editorial workflow |
| Internal team knowledge base | `docusaurus` | Markdown in Git, developer audience |

## Infrastructure Comparison

| Aspect | WordPress | Docusaurus | Static Site |
|--------|-----------|------------|-------------|
| **Containers** | 4 (WP, Nginx, MariaDB, Redis) | 1 (Nginx) | 1 (Nginx) |
| **RAM usage** | ~512MB+ | ~50MB | ~50MB |
| **Attack surface** | High (PHP, plugins, DB) | Minimal (static files) | Minimal (static files) |
| **Maintenance** | Weekly updates (core, plugins, themes) | Low (rebuild on content change) | Near zero |
| **Backup complexity** | DB dump + wp-content volume | Git repo only | Git repo only |
| **Rule pack** | `WORDPRESS` | `DOCUSAURUS` | `TS_CORE`, `SAAS_UI` |

## Anti-Pattern: Wrong Scaffold Choice

| Mistake | Why It Fails | Correct Choice |
|---------|-------------|----------------|
| WordPress for a SaaS dashboard | WP is a CMS, not an app framework | `saas-skeleton` (Next.js + FastAPI) |
| Docusaurus for a client marketing site | Clients can't edit Markdown in Git | `wordpress` |
| Static site for 50+ page docs with versioning | No sidebar, no search, no versioning | `docusaurus` |
| WordPress for a single landing page | 4 containers for one page is overkill | `static-site` |
| Docusaurus for e-commerce | No database, no payment integration | `wordpress` (WooCommerce) |
