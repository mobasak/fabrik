# Fabrik Codebase Architecture Analysis

**Generated:** 2026-01-04
**Analyzed Version:** v0.1.0
**Git Commit:** 054958d

## Table of Contents

- [Executive Summary](#executive-summary)
- [High-Level Architecture](#high-level-architecture)
- [Directory Structure](#directory-structure)
- [Core Modules](#core-modules)
- [Module Dependencies](#module-dependencies)
- [Data Flow](#data-flow)
- [Integration Points](#integration-points)
- [Scripts and Automation](#scripts-and-automation)
- [Templates](#templates)
- [Technical Debt](#technical-debt)
- [Recommendations](#recommendations)

---

## Executive Summary

Fabrik is a deployment automation CLI that enables spec-driven deployment of Python APIs, WordPress sites, and AI-integrated applications via Coolify. The codebase is well-structured with clear separation of concerns between CLI commands, drivers for external services, and domain-specific WordPress automation.

**Key Characteristics:**
- **Architecture Pattern:** Layered architecture with clear driver abstraction
- **Primary Language:** Python 3.11+ with type hints (Pydantic for validation)
- **Integration Layer:** HTTP-based drivers for Coolify, DNS, Cloudflare, Supabase, R2
- **Domain Logic:** Extensive WordPress automation with preset-driven deployment
- **AI Integration:** Droid exec task runner for autonomous code operations

**Maturity Level:** Early production (v0.1.0) - Core functionality complete, WordPress automation 67% done

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Layer (cli.py)                      │
│     Commands: new, plan, apply, status, templates, etc.        │
└─────────────────────┬───────────────────────────────────────────┘
                      │
        ┌─────────────┴────────────┬────────────────┬─────────────┐
        │                          │                │             │
┌───────▼────────┐     ┌──────────▼─────────┐  ┌──▼────────┐ ┌──▼──────┐
│  Spec Loader   │     │  Template Renderer │  │ Scaffold  │ │Registry │
│ (spec_loader)  │     │(template_renderer) │  │(scaffold) │ │(registry)│
└───────┬────────┘     └──────────┬─────────┘  └───────────┘ └─────────┘
        │                         │
        └────────┬────────────────┘
                 │
     ┌───────────▼───────────────────────────────────────────┐
     │              Driver Layer (drivers/)                  │
     │                                                        │
     │  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌──────────┐   │
     │  │Coolify  │ │   DNS    │ │  R2    │ │ Supabase │   │
     │  │         │ │(Namecheap│ │(Cloudflare│Postgres │   │
     │  │         │ │ /CF)     │ │Storage)│ │  Auth)   │   │
     │  └─────────┘ └──────────┘ └────────┘ └──────────┘   │
     │                                                        │
     │  ┌───────────┐ ┌──────────────┐ ┌───────────────┐   │
     │  │Cloudflare │ │   WordPress  │ │ Uptime Kuma   │   │
     │  │   (DNS)   │ │  (WP-CLI +   │ │  (Monitoring) │   │
     │  │           │ │   REST API)  │ │               │   │
     │  └───────────┘ └──────────────┘ └───────────────┘   │
     └────────────────────────────────────────────────────────┘
                      │
          ┌───────────┴────────────┐
          │                        │
  ┌───────▼──────────┐    ┌───────▼────────────────────┐
  │  Provisioner     │    │  WordPress Module          │
  │  (provisioner)   │    │  (wordpress/)              │
  │                  │    │                            │
  │  Saga pattern    │    │  ┌──────────────────┐     │
  │  for end-to-end  │    │  │ Deployer         │     │
  │  site setup      │    │  │ Domain Setup     │     │
  │                  │    │  │ Spec Loader      │     │
  │  Step 0: Domain  │    │  │ Preset Loader    │     │
  │  Step 1: DNS     │    │  │ Theme, Settings  │     │
  │  Step 2: Deploy  │    │  │ Pages, Menus     │     │
  └──────────────────┘    │  │ SEO, Analytics   │     │
                          │  │ Forms, Media     │     │
                          │  └──────────────────┘     │
                          └────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│              Automation Layer (scripts/)                       │
│                                                                │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐   │
│  │Droid Tasks  │  │Droid Runner  │  │ Droid Models      │   │
│  │(task queue) │  │(monitor exec)│  │ (model registry)  │   │
│  └─────────────┘  └──────────────┘  └───────────────────┘   │
│                                                                │
│  ┌──────────────┐ ┌─────────────────┐ ┌──────────────────┐  │
│  │Health Check  │ │Process Monitor  │ │ Container Images │  │
│  │(autonomous)  │ │(long-running    │ │ (image registry) │  │
│  │              │ │ process watch)  │ │                  │  │
│  └──────────────┘ └─────────────────┘ └──────────────────┘  │
└────────────────────────────────────────────────────────────────┘

                        │
            ┌───────────┴──────────┐
            │                      │
    ┌───────▼────────┐     ┌──────▼────────────┐
    │   Templates    │     │   External APIs   │
    │                │     │                   │
    │ - scaffold     │     │ - Coolify API     │
    │ - saas-skeleton│     │ - Namecheap API   │
    │ - wordpress    │     │ - Cloudflare API  │
    │ - python-api   │     │ - Supabase API    │
    │ - node-api     │     │ - Uptime Kuma API │
    │ - file-worker  │     │ - WordPress APIs  │
    │ - docusaurus   │     │   (WP-CLI + REST) │
    └────────────────┘     └───────────────────┘
```

### Architecture Patterns

1. **Layered Architecture**
   - CLI → Core Modules → Drivers → External APIs
   - Clear separation of concerns
   - Driver abstraction isolates API changes

2. **Saga Pattern (Provisioner)**
   - Granular state management for multi-step provisioning
   - Retryable failures with state snapshots
   - States: INIT → STEP0 → STEP1 → GATE → STEP2 → COMPLETE

3. **Factory Pattern (Drivers)**
   - Each driver has a consistent interface
   - Environment-based configuration
   - HTTP-based communication via httpx

4. **Spec-Driven Deployment**
   - YAML specs define infrastructure as code
   - Pydantic validation ensures correctness
   - Jinja2 templating for compose.yaml generation

---

## Directory Structure

```
/opt/fabrik/
├── .droid/                 # Droid exec data exchange (tasks, responses, sessions)
├── .factory/               # Factory CLI configuration (hooks, skills, droids)
├── .github/                # GitHub Actions workflows (droid-review, security scan)
├── .tmp/                   # Temporary files (persists across restarts)
├── .cache/                 # Cache directory
├── .venv/                  # Python virtual environment
│
├── apps/                   # Deployed application instances
│   ├── example-api/        # Example Python API
│   └── postgres-main/      # Central PostgreSQL container
│
├── config/                 # Configuration files
│   └── models.yaml         # Droid model rankings and scenarios
│
├── data/                   # Persistent data
│   └── projects.yaml       # Project registry (auto-discovered /opt projects)
│
├── docs/                   # Documentation
│   ├── guides/             # How-to guides
│   ├── operations/         # Operational docs (VPS, backups, monitoring)
│   ├── reference/          # Reference documentation (architecture, phases)
│   └── archive/            # Historical documentation
│
├── infrastructure/         # Infrastructure as code (not heavily used)
│
├── logs/                   # Application logs
│
├── output/                 # Generated output files
│
├── scripts/                # Automation scripts
│   ├── droid/              # Batch refactoring scripts (imports, errors, lint)
│   ├── droid_tasks.py      # Droid exec task runner (primary interface)
│   ├── droid_runner.py     # Robust droid wrapper with monitoring
│   ├── droid_models.py     # Model registry (auto-updated from Factory docs)
│   ├── droid_model_updater.py # Daily model sync
│   ├── process_monitor.py  # Long-running process monitoring
│   ├── health_check_autonomous.py # Autonomous health verification
│   ├── container_images.py # Container image management
│   ├── setup_duplicati_backup.py # Backup configuration
│   ├── setup_uptime_kuma.py # Monitoring setup
│   └── run[c|d|dsh|k]      # Quick Docker/Compose/Shell launchers
│
├── specs/                  # Deployment specifications (YAML)
│
├── sql/                    # Database migration scripts
│
├── src/fabrik/             # Main source code (see Core Modules section)
│
├── templates/              # Deployment templates
│   ├── scaffold/           # Project scaffolding templates
│   ├── saas-skeleton/      # Next.js 14 SaaS template (MANDATORY for web apps)
│   ├── wordpress/          # WordPress site templates
│   ├── python-api/         # FastAPI template
│   ├── node-api/           # Express.js template
│   ├── file-worker/        # Background worker template
│   ├── file-api/           # File upload API template
│   ├── next-tailwind/      # Next.js + Tailwind template
│   └── docusaurus/         # Documentation site template
│
├── tests/                  # Test suite
│   └── monitoring_poc/     # Process monitoring proof-of-concept
│
├── AGENTS.md               # Droid exec agent briefing (critical reference)
├── README.md               # Project README
├── CHANGELOG.md            # Version history
├── tasks.md                # Current task tracking
├── pyproject.toml          # Python project config (dependencies, tools)
├── uv.lock                 # Dependency lock file (uv package manager)
├── Makefile                # Common development tasks
├── .env.example            # Environment variable template
└── windsurfrules           # Windsurf AI coding rules (symlinked to projects)
```

### Directory Purpose Analysis

| Directory | Purpose | Status |
|-----------|---------|--------|
| `apps/` | Deployed application instances | ✅ Active |
| `config/` | Configuration files | ✅ Active |
| `data/` | Persistent data (registries) | ✅ Active |
| `docs/` | Documentation | ✅ Well-organized |
| `infrastructure/` | Infrastructure as code | ⚠️ Underutilized |
| `logs/` | Application logs | ✅ Active |
| `output/` | Generated output | ✅ Active |
| `scripts/` | Automation scripts | ✅ Heavily used |
| `specs/` | Deployment specs | ✅ Active |
| `sql/` | Database migrations | ⚠️ Minimal usage |
| `src/fabrik/` | Core source code | ✅ Primary development |
| `templates/` | Project templates | ✅ Active |
| `tests/` | Test suite | ⚠️ Sparse coverage |

**Issues Identified:**
- `tests/` directory is sparse - limited test coverage
- `infrastructure/` and `sql/` directories are underutilized
- No dedicated `examples/` directory for sample projects

---

## Core Modules

### `/opt/fabrik/src/fabrik/` Structure

```
src/fabrik/
├── __init__.py             # Public API exports (Spec, TemplateRenderer)
├── main.py                 # Entry point (calls cli.main())
├── cli.py                  # CLI commands (Click framework)
├── config.py               # Configuration loading (env vars, paths)
├── spec_loader.py          # Spec file parsing (Pydantic models)
├── template_renderer.py    # Jinja2 template rendering
├── deploy.py               # Deployment helper (Coolify integration)
├── scaffold.py             # Project scaffolding
├── registry.py             # Project registry (/opt folder scanning)
├── provisioner.py          # Site provisioner (Saga pattern)
├── compose_linter.py       # Docker Compose validation
├── monitor.py              # Service monitoring utilities
│
├── api/                    # API server (currently empty)
│   └── __init__.py
│
├── drivers/                # External service integrations
│   ├── __init__.py         # Driver exports
│   ├── coolify.py          # Coolify API client
│   ├── dns.py              # DNS management (Namecheap wrapper)
│   ├── cloudflare.py       # Cloudflare DNS API
│   ├── supabase.py         # Supabase client (Postgres + Auth)
│   ├── r2.py               # Cloudflare R2 storage
│   ├── uptime_kuma.py      # Uptime Kuma monitoring
│   ├── wordpress.py        # WordPress WP-CLI wrapper
│   └── wordpress_api.py    # WordPress REST API client
│
├── models/                 # Data models (currently empty)
│   └── __init__.py
│
├── services/               # Business logic services (currently empty)
│   └── __init__.py
│
├── utils/                  # Utility functions (currently empty)
│   └── __init__.py
│
└── wordpress/              # WordPress automation
    ├── __init__.py         # Public API exports
    ├── deployer.py         # Orchestrates full WordPress deployment
    ├── domain_setup.py     # Domain provisioning (DNS + Cloudflare)
    ├── spec_loader.py      # WordPress-specific spec loading
    ├── spec_validator.py   # WordPress spec validation
    ├── preset_loader.py    # Preset configurations (company, saas, etc.)
    ├── theme.py            # Theme customization
    ├── settings.py         # WordPress settings management
    ├── pages.py            # Page creation via REST API
    ├── page_generator.py   # Page content generation
    ├── section_renderer.py # Section rendering (hero, features, etc.)
    ├── menus.py            # Menu creation
    ├── seo.py              # SEO configuration (Yoast, RankMath)
    ├── analytics.py        # Analytics injection (GA, GTM)
    ├── forms.py            # Contact form creation
    ├── media.py            # Media upload (brand assets)
    ├── content.py          # Content management utilities
    └── legal.py            # Legal page generation (privacy, terms)
```

### Module Descriptions

#### Core CLI Modules

| Module | Lines | Purpose | Key Classes/Functions |
|--------|-------|---------|----------------------|
| `cli.py` | 663 | CLI commands | `new()`, `plan()`, `apply()`, `status()`, `templates()`, `scan()`, `scaffold()` |
| `config.py` | 78 | Configuration loading | `Config`, `get_env()`, `ensure_directories()` |
| `spec_loader.py` | 294 | Spec parsing/validation | `Spec`, `Source`, `DNSConfig`, `load_spec()`, `save_spec()` |
| `template_renderer.py` | 217 | Template rendering | `TemplateRenderer.render()`, `list_templates()` |
| `deploy.py` | 48 | Deployment helper | `deploy_to_coolify()` |
| `scaffold.py` | 143 | Project scaffolding | `create_project()`, `validate_project()` |
| `registry.py` | 103 | Project registry | `ProjectRegistry.scan()`, `list()`, `update()` |
| `provisioner.py` | 667 | Site provisioner | `SiteProvisioner.provision_site()`, saga states |
| `compose_linter.py` | 130 | Compose validation | `ComposeLinter.lint()`, `check_fabrik_conventions()` |
| `monitor.py` | 226 | Service monitoring | `ServiceMonitor`, `check_health()` |

#### Driver Layer (External Integrations)

| Driver | Lines | Purpose | Key Classes/Functions |
|--------|-------|---------|----------------------|
| `coolify.py` | 532 | Coolify API | `CoolifyClient`, `list_applications()`, `deploy()`, `create_dockercompose_application()` |
| `dns.py` | 266 | DNS management | `DNSClient`, `add_record()`, `list_records()` (Namecheap proxy) |
| `cloudflare.py` | 358 | Cloudflare DNS | `CloudflareClient`, `create_zone()`, `add_record()` |
| `supabase.py` | 330 | Supabase | `SupabaseClient`, Postgres + Auth integration |
| `r2.py` | 391 | Cloudflare R2 | `R2Client`, S3-compatible storage |
| `uptime_kuma.py` | 160 | Monitoring | `UptimeKumaClient`, `add_fabrik_service_to_monitoring()` |
| `wordpress.py` | 254 | WordPress WP-CLI | `WordPressClient`, `wp_cli()`, `install_plugin()` |
| `wordpress_api.py` | 341 | WordPress REST | `WordPressAPIClient`, `create_post()`, `upload_media()` |

#### WordPress Automation

| Module | Lines | Purpose | Key Classes/Functions |
|--------|-------|---------|----------------------|
| `deployer.py` | 244 | Orchestrates deployment | `SiteDeployer.deploy()`, full site automation |
| `domain_setup.py` | 330 | Domain provisioning | `DomainProvisioner.provision()`, `sync_dns()` |
| `spec_loader.py` | 454 | WordPress spec parsing | `load_spec()`, preset expansion, variable interpolation |
| `spec_validator.py` | 234 | Spec validation | `SpecValidator.validate()`, comprehensive checks |
| `preset_loader.py` | 478 | Preset configs | `PresetLoader.load()`, 5 presets (company, landing, saas, ecommerce, content) |
| `theme.py` | 331 | Theme customization | `ThemeCustomizer.apply()`, brand colors/fonts |
| `settings.py` | 280 | WordPress settings | `SettingsApplicator.apply()`, editor credentials, site settings |
| `pages.py` | 288 | Page creation | `PageCreator.create()`, REST API integration |
| `page_generator.py` | 457 | Page content generation | `generate_pages()`, section-based pages |
| `section_renderer.py` | 571 | Section rendering | `SectionRenderer.render()`, 15+ section types |
| `menus.py` | 236 | Menu creation | `MenuCreator.create()`, hierarchical menus |
| `seo.py` | 286 | SEO configuration | `SEOApplicator.apply()`, Yoast/RankMath |
| `analytics.py` | 199 | Analytics injection | `AnalyticsInjector.inject()`, GA4, GTM |
| `forms.py` | 210 | Contact forms | `FormCreator.create()`, WPForms/Gravity Forms |
| `media.py` | 236 | Media upload | `MediaUploader.upload()`, brand assets |
| `content.py` | 137 | Content utilities | Content management helpers |
| `legal.py` | 186 | Legal pages | Privacy policy, terms of service generation |

---

## Module Dependencies

### Import Analysis

```
Root Package (fabrik)
│
├── cli.py
│   ├── fabrik.drivers.coolify (CoolifyClient)
│   ├── fabrik.drivers.dns (DNSClient)
│   ├── fabrik.deploy (deploy_to_coolify)
│   ├── fabrik.spec_loader (Kind, create_spec, load_spec, save_spec)
│   └── fabrik.template_renderer (list_templates, render_template)
│
├── deploy.py
│   └── fabrik.drivers.coolify (CoolifyClient)
│
├── provisioner.py
│   ├── fabrik.drivers.coolify (CoolifyClient)
│   └── fabrik.compose_linter (ComposeLinter)
│
├── template_renderer.py
│   └── fabrik.spec_loader (Spec)
│
├── drivers/ (no internal fabrik dependencies - all external: httpx, subprocess)
│   ├── coolify.py
│   ├── dns.py
│   ├── cloudflare.py
│   ├── supabase.py
│   ├── r2.py
│   ├── uptime_kuma.py
│   ├── wordpress.py
│   └── wordpress_api.py
│
└── wordpress/
    ├── deployer.py
    │   ├── fabrik.drivers.wordpress (WordPressClient)
    │   ├── fabrik.drivers.wordpress_api (WordPressAPIClient)
    │   ├── fabrik.wordpress.analytics (AnalyticsInjector)
    │   ├── fabrik.wordpress.domain_setup (DomainSetup)
    │   ├── fabrik.wordpress.forms (FormCreator)
    │   ├── fabrik.wordpress.menus (MenuCreator)
    │   ├── fabrik.wordpress.page_generator (generate_pages)
    │   ├── fabrik.wordpress.pages (CreatedPage, PageCreator)
    │   ├── fabrik.wordpress.seo (SEOApplicator)
    │   ├── fabrik.wordpress.settings (SettingsApplicator)
    │   ├── fabrik.wordpress.spec_loader (load_spec)
    │   ├── fabrik.wordpress.spec_validator (SpecValidator)
    │   └── fabrik.wordpress.theme (ThemeCustomizer)
    │
    ├── page_generator.py
    │   └── fabrik.wordpress.section_renderer (SectionRenderer)
    │
    ├── preset_loader.py
    │   ├── fabrik.drivers.wordpress (WordPressClient)
    │   └── fabrik.drivers.wordpress_api (WordPressAPIClient)
    │
    └── [other wordpress modules]
        ├── fabrik.drivers.wordpress (WordPressClient)
        └── fabrik.drivers.wordpress_api (WordPressAPIClient)
```

### Dependency Graph (ASCII)

```
                      CLI Layer
                      ┌──────┐
                      │ cli  │
                      └───┬──┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
    ┌───▼────┐     ┌──────▼──────┐     ┌───▼──────┐
    │ deploy │     │spec_loader  │     │ template │
    └───┬────┘     └──────┬──────┘     │ renderer │
        │                 │             └───┬──────┘
        │                 │                 │
        └────────┬────────┴─────────────────┘
                 │
            ┌────▼─────┐
            │ drivers/ │ ◄──────────┐
            └────┬─────┘            │
                 │                  │
        ┌────────┴────────┐         │
        │                 │         │
  ┌─────▼─────┐   ┌───────▼──────┐ │
  │ coolify   │   │ wordpress    │ │
  │ dns       │   │ cloudflare   │ │
  │ supabase  │   │ uptime_kuma  │ │
  │ r2        │   │ wordpress_api│ │
  └───────────┘   └──────────────┘ │
                                   │
                           ┌───────┴────────┐
                           │  wordpress/    │
                           │  (orchestrator)│
                           └────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────┐
        │                          │                      │
  ┌─────▼──────┐        ┌──────────▼──────┐      ┌───────▼─────┐
  │ deployer   │        │ spec_loader     │      │ preset_loader│
  │ domain_setup│       │ spec_validator  │      │              │
  └────────────┘        └─────────────────┘      └──────────────┘
        │
        └─────┬──────────┬──────────┬──────────┬──────────┬───────┐
              │          │          │          │          │       │
          ┌───▼──┐  ┌────▼───┐  ┌──▼───┐  ┌───▼──┐  ┌────▼──┐ ┌──▼──┐
          │theme │  │settings│  │pages │  │menus │  │seo    │ │forms│
          └──────┘  └────────┘  └──────┘  └──────┘  └───────┘ └─────┘
```

### Circular Import Analysis

**✅ No circular imports detected** in the core codebase.

**Design Strength:**
- Driver layer is self-contained (no fabrik imports)
- WordPress modules depend on drivers, not vice versa
- Deployer orchestrates modules, but modules don't import deployer
- Spec loader is imported by template renderer (one direction only)

**Potential Risk Areas:**
- `wordpress/__init__.py` re-exports everything, creating potential for circular issues if modules start cross-importing
- `drivers/__init__.py` similarly re-exports all drivers

**Recommendation:** Keep the current clean separation. Avoid cross-imports between wordpress modules.

---

## Data Flow

### 1. Spec-Driven Deployment Flow

```
User creates spec file (YAML)
         │
         ▼
   fabrik new <name> --template <template>
         │
         │ creates spec from template
         ▼
   specs/<name>.yaml
         │
         ▼
   fabrik plan <spec>  ◄─── (dry run)
         │
         │ loads spec → validates → renders template
         ▼
   Shows deployment preview
         │
         ▼
   fabrik apply <spec>
         │
         ├─→ render_template(spec) → compose.yaml
         │
         ├─→ deploy_to_coolify(compose_content)
         │   │
         │   ├─→ CoolifyClient.create_dockercompose_application()
         │   │
         │   └─→ CoolifyClient.deploy(uuid)
         │
         └─→ (optional) DNSClient.add_record() if DNS config present
```

### 2. WordPress Provisioning Flow (Saga Pattern)

```
User initiates WordPress site creation
         │
         ▼
   SiteProvisioner.provision_site(domain, preset, contact)
         │
         │ State: INIT
         ▼
   ┌─── Step 0: Domain Registration ────┐
   │                                     │
   │  1. CloudflareClient.create_zone()  │
   │     State: STEP0_CF_ZONE_CREATED    │
   │                                     │
   │  2. Register domain via DNS Manager │
   │     State: STEP0_DOMAIN_REGISTERED  │
   └─────────────────┬───────────────────┘
                     │
                     ▼
   ┌─── Step 1: DNS Setup ───────────────┐
   │                                      │
   │  1. Add DNS records to Cloudflare    │
   │     State: STEP1_DNS_RECORDS_UPSERTED│
   │                                      │
   │  2. Verify Cloudflare status         │
   │     State: STEP1_CF_STATUS_SNAPSHOT  │
   │                                      │
   │  3. Wait for zone activation         │
   │     State: GATE_WAIT_CF_ACTIVE       │
   └──────────────────┬───────────────────┘
                      │
                      ▼
   ┌─── Step 2: WordPress Deployment ────┐
   │                                      │
   │  1. Create Coolify application       │
   │     State: STEP2_COOLIFY_CREATED     │
   │                                      │
   │  2. Deploy WordPress container       │
   │     State: STEP2_COOLIFY_DEPLOY_     │
   │            REQUESTED                 │
   │                                      │
   │  3. Wait for deployment              │
   │     State: STEP2_COOLIFY_DEPLOY_     │
   │            SUCCEEDED                 │
   │                                      │
   │  4. Verify HTTP accessibility        │
   │     State: STEP2_HTTP_VERIFIED       │
   └──────────────────┬───────────────────┘
                      │
                      ▼
                  COMPLETE
```

Each state transition is saved to disk, enabling retry from any point.

### 3. WordPress Content Deployment Flow

```
User defines WordPress site spec (YAML)
         │
         ├─ domain: example.com
         ├─ preset: company | landing | saas | ecommerce | content
         ├─ brand: colors, fonts, logo
         ├─ pages: [ {id, title, sections: [...]} ]
         ├─ menus: [ {location, items: [...]} ]
         ├─ seo: { title_template, description, ... }
         └─ analytics: { google_analytics_id, gtm_id, ... }
         │
         ▼
   SiteDeployer.deploy(spec_path)
         │
         ├─→ 1. SpecValidator.validate(spec)
         │       └─ Validate structure, required fields, references
         │
         ├─→ 2. DomainSetup.setup(domain)
         │       └─ Ensure DNS + HTTPS
         │
         ├─→ 3. SettingsApplicator.apply(wp_client, settings)
         │       └─ Site title, tagline, editor credentials
         │
         ├─→ 4. ThemeCustomizer.apply(wp_client, brand)
         │       └─ Install Astra, apply colors/fonts
         │
         ├─→ 5. MediaUploader.upload(wp_client, brand_assets)
         │       └─ Upload logo, favicon
         │
         ├─→ 6. PageCreator.create(wp_api, pages)
         │       │
         │       └─→ For each page:
         │             └─→ generate_page_content(sections)
         │                   └─→ SectionRenderer.render(section_type)
         │                         ├─ hero, features, cta, pricing
         │                         ├─ testimonials, faq, contact
         │                         └─ Returns Gutenberg block JSON
         │
         ├─→ 7. MenuCreator.create(wp_client, menus)
         │       └─ Create navigation menus
         │
         ├─→ 8. SEOApplicator.apply(wp_client, seo_config)
         │       └─ Configure Yoast SEO / RankMath
         │
         ├─→ 9. AnalyticsInjector.inject(wp_client, analytics)
         │       └─ Add GA4 / GTM tracking code
         │
         └─→ 10. FormCreator.create(wp_client, forms)
                 └─ Create contact forms via WPForms
```

---

## Integration Points

### External API Dependencies

| Service | API Type | Auth Method | Driver |
|---------|----------|-------------|--------|
| **Coolify** | REST (HTTP) | Bearer Token | `coolify.py` |
| **Namecheap** | REST (HTTP Proxy) | None (internal VPS service) | `dns.py` |
| **Cloudflare** | REST (HTTP) | Bearer Token | `cloudflare.py` |
| **Supabase** | REST (HTTP) + SDK | API Key + Service Role Key | `supabase.py` |
| **Cloudflare R2** | S3 Compatible | Access Key + Secret | `r2.py` |
| **Uptime Kuma** | REST (HTTP) | Username + Password | `uptime_kuma.py` |
| **WordPress** | WP-CLI (SSH) + REST API | Basic Auth (REST), SSH (CLI) | `wordpress.py`, `wordpress_api.py` |

### Environment Variables Required

```bash
# VPS Configuration
VPS_HOST=vps1.ocoron.com
VPS_USER=deploy
VPS_SSH_KEY=~/.ssh/id_rsa

# Coolify
COOLIFY_API_URL=http://vps1.ocoron.com:8000
COOLIFY_API_TOKEN=<token>
COOLIFY_SERVER_UUID=<server-uuid>
COOLIFY_PROJECT_UUID=<project-uuid>

# DNS
DNS_PROVIDER=namecheap
NAMECHEAP_API_URL=https://namecheap.vps1.ocoron.com

# Cloudflare
CLOUDFLARE_API_TOKEN=<token>
CLOUDFLARE_ZONE_ID=<zone-id>
CLOUDFLARE_ACCOUNT_ID=<account-id>

# Supabase
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_KEY=<anon-key>
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>

# Cloudflare R2
R2_ACCESS_KEY_ID=<key>
R2_SECRET_ACCESS_KEY=<secret>
R2_BUCKET_NAME=<bucket>
R2_ACCOUNT_ID=<account-id>

# Uptime Kuma
UPTIME_KUMA_URL=http://vps1.ocoron.com:3001
UPTIME_KUMA_USERNAME=<username>
UPTIME_KUMA_PASSWORD=<password>

# WordPress (per site)
WP_ADMIN_USER=admin
WP_ADMIN_PASSWORD=<password>
WP_ADMIN_EMAIL=admin@example.com
```

### Database Dependencies

| Component | Database | Purpose |
|-----------|----------|---------|
| **Fabrik CLI** | None (file-based registry) | Uses `data/projects.yaml` |
| **WordPress Sites** | PostgreSQL (postgres-main) | Per-site database |
| **Coolify** | PostgreSQL (internal) | Coolify metadata |
| **Provisioner** | File-based (JSON snapshots) | State persistence for saga |

**Note:** Fabrik itself is stateless (no database), relying on spec files and the project registry YAML.

---

## Scripts and Automation

### Droid Exec Integration

Fabrik heavily integrates with Factory AI's `droid exec` for autonomous code operations.

#### Primary Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `droid_tasks.py` | Task runner with model selection | `python scripts/droid_tasks.py analyze "Review auth flow"` |
| `droid_runner.py` | Robust wrapper with monitoring | `python scripts/droid_runner.py run --task tasks/my_task.md` |
| `droid_models.py` | Model registry and ranking | `python scripts/droid_models.py stack-rank` |
| `droid_model_updater.py` | Daily model sync from Factory docs | `python scripts/droid_model_updater.py` |

#### Task Types and Model Assignments

| Task Type | Model | Reasoning | Autonomy | Purpose |
|-----------|-------|-----------|----------|---------|
| `analyze` | gemini-3-flash-preview | off | low | Read-only analysis |
| `code` | gpt-5.1-codex-max | medium | high | File editing |
| `refactor` | gpt-5.1-codex-max | medium | high | Code refactoring |
| `test` | gpt-5.1-codex-max | low | high | Test generation |
| `spec` | claude-sonnet-4-5 | high | low | Planning mode |
| `scaffold` | gpt-5.1-codex-max | medium | high | Project creation |
| `deploy` | gemini-3-flash-preview | off | high | Deployment configs |
| `health` | gemini-3-flash-preview | off | high | Autonomous health check |

#### Automation Workflows

1. **Daily Model Updates** (Cron)
   ```bash
   # Setup: ./scripts/setup_model_updates.sh
   # Runs: python scripts/droid_model_updater.py daily
   # Updates: config/models.yaml with latest Factory rankings
   ```

2. **Process Monitoring** (Long-Running Tasks)
   ```python
   # scripts/process_monitor.py
   # Monitors droid exec processes, detects stuck/timeout, sends alerts
   ```

3. **Health Check Automation**
   ```python
   # scripts/health_check_autonomous.py
   # Autonomous health verification after deployment (no --auto flag)
   ```

#### Batch Refactoring Scripts (`scripts/droid/`)

| Script | Purpose | Usage |
|--------|---------|-------|
| `refactor-imports.sh` | Organize Python imports | `./scripts/droid/refactor-imports.sh src` |
| `improve-errors.sh` | Improve error messages | `./scripts/droid/improve-errors.sh src` |
| `fix-lint.sh` | Fix lint violations | `./scripts/droid/fix-lint.sh src` |

All support `DRY_RUN=true` for preview mode.

### Other Automation Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `container_images.py` | Manage container images | `python scripts/container_images.py list` |
| `setup_duplicati_backup.py` | Configure backups | `python scripts/setup_duplicati_backup.py` |
| `setup_uptime_kuma.py` | Setup monitoring | `python scripts/setup_uptime_kuma.py` |
| `test_process_monitor.py` | Test monitoring system | `python scripts/test_process_monitor.py` |
| `runc` | Quick Docker container run | `./scripts/runc postgres` |
| `rund` | Quick Docker compose up | `./scripts/rund` |
| `rundsh` | Quick Docker compose shell | `./scripts/rundsh` |
| `runk` | Quick Docker stop | `./scripts/runk` |

---

## Templates

### Available Templates

| Template | Type | Purpose | Key Files |
|----------|------|---------|-----------|
| `scaffold` | Project template | Full project structure | `docs/`, `docker/`, AGENTS.md, factory configs |
| `saas-skeleton` | Next.js 14 + TypeScript | **MANDATORY for SaaS/web apps** | Marketing pages, app dashboard, ChatUI, SSE |
| `wordpress` | WordPress site | Spec-driven WordPress deployment | `base/compose-coolify.yaml.j2`, presets, plugins |
| `python-api` | FastAPI | Python REST API | Dockerfile, compose.yaml, src/main.py |
| `node-api` | Express.js | Node.js REST API | Dockerfile, compose.yaml, server.js |
| `file-worker` | Background worker | File processing worker | Dockerfile, worker/main.py |
| `file-api` | File upload API | File upload service | Dockerfile, src/main.py |
| `next-tailwind` | Next.js + Tailwind | Frontend web app | Dockerfile, compose.yaml |
| `docusaurus` | Docusaurus | Documentation site | Dockerfile, compose.yaml, docs/ |

### Template Structure

Each template follows this structure:

```
templates/<template-name>/
├── compose.yaml.j2         # Jinja2 template for Docker Compose
├── Dockerfile.j2           # (optional) Dockerfile template
├── README.md               # Template documentation
├── AGENTS.md.j2            # (optional) Agent briefing template
├── .env.example.j2         # Environment variable template
└── <template-specific files>
```

### SaaS Skeleton Details (Critical)

**Location:** `/opt/fabrik/templates/saas-skeleton/`

**Includes:**
- **Next.js 14** with App Router
- **TypeScript** + **Tailwind CSS**
- **Marketing pages:** Landing, pricing, features, about, contact
- **App pages:** Dashboard, settings, job workflow
- **ChatUI component** for droid exec integration
- **SSE streaming** for real-time droid output
- **Docker Compose** ready for Coolify deployment

**Usage:**
```bash
cp -r /opt/fabrik/templates/saas-skeleton /opt/<project-name>
cd /opt/<project-name>
npm install
cp .env.example .env
npm run dev
```

**Customization:** `lib/config/site.ts` for branding.

### WordPress Template Details

**Location:** `/opt/fabrik/templates/wordpress/`

**Key Components:**
- `base/compose-coolify.yaml.j2` - Docker Compose template (WordPress + PostgreSQL)
- `presets/` - 5 preset configurations (company, landing, saas, ecommerce, content)
- `plugins/` - Plugin definitions (2800+ plugins cataloged)
- `themes/` - Theme definitions (Astra, GeneratePress)
- `schema/` - JSON Schema for site specs
- `defaults.yaml` - Default WordPress configuration

**Presets:**

| Preset | Target Use Case | Key Features |
|--------|----------------|--------------|
| `company` | Corporate website | About, services, team, contact |
| `landing` | Single landing page | Hero, features, CTA, pricing |
| `saas` | SaaS product site | Features, pricing tiers, signup, docs |
| `ecommerce` | Online store | Products, cart, checkout, WooCommerce |
| `content` | Blog/magazine | Blog posts, categories, authors |

---

## Technical Debt

### Code Quality Issues

1. **Test Coverage** (HIGH PRIORITY)
   - `tests/` directory is sparse
   - Most modules lack unit tests
   - Integration tests missing for critical flows (provisioning, deployment)
   - **Impact:** Refactoring risk, harder to catch regressions
   - **Recommendation:** Add pytest tests for all driver modules and WordPress deployer

2. **Type Hints Coverage** (MEDIUM)
   - Most modules use type hints (good!)
   - Some functions lack return type annotations
   - `mypy --strict` not fully passing
   - **Recommendation:** Run `mypy --strict src/` and fix remaining issues

3. **Empty Placeholder Modules** (LOW)
   - `api/`, `models/`, `services/`, `utils/` directories exist but are empty
   - **Impact:** Confusing structure, unclear future intent
   - **Recommendation:** Either populate or remove these directories

4. **Docstring Coverage** (MEDIUM)
   - Most modules have docstrings
   - Function-level docstrings inconsistent
   - Missing docstrings for complex functions (e.g., provisioner saga logic)
   - **Recommendation:** Add docstrings for all public functions

### Architectural Issues

1. **Provisioner Saga Pattern Complexity** (HIGH)
   - `provisioner.py` is 667 lines with complex state management
   - Difficult to test and reason about
   - State transitions spread across multiple methods
   - **Impact:** Fragile provisioning flow, hard to add new steps
   - **Recommendation:**
     - Extract Step 0, Step 1, Step 2 into separate classes
     - Use state machine library (e.g., `python-statemachine`)
     - Add comprehensive logging and observability

2. **WordPress Deployer Orchestration** (MEDIUM)
   - `wordpress/deployer.py` orchestrates 10+ modules sequentially
   - No parallel execution (could be faster)
   - Error handling is basic (one failure stops everything)
   - **Impact:** Slow deployments, poor error recovery
   - **Recommendation:**
     - Add async/await for parallel operations (theme + plugins install)
     - Implement retry logic for transient failures
     - Add rollback capability

3. **Configuration Management** (MEDIUM)
   - Environment variables loaded via `os.getenv()` everywhere
   - No centralized config validation
   - Hard to track which env vars are required
   - **Impact:** Runtime errors due to missing env vars
   - **Recommendation:**
     - Centralize config in `config.py` with Pydantic validation
     - Validate all required env vars at startup
     - Document env vars in `.env.example`

4. **Driver Error Handling** (MEDIUM)
   - Drivers raise raw httpx exceptions
   - Inconsistent error messages
   - No retry logic for transient failures
   - **Impact:** Poor user experience, fragile API calls
   - **Recommendation:**
     - Create custom exception hierarchy (`FabrikAPIError`, `FabrikRateLimitError`, etc.)
     - Add tenacity retry decorators for transient errors
     - Wrap all API calls with try/except and meaningful errors

5. **Circular Import Risk** (LOW)
   - `__init__.py` files re-export everything
   - Could lead to circular imports if modules start cross-importing
   - **Impact:** Future refactoring risk
   - **Recommendation:** Keep current clean separation, add import linter to CI

### Performance Issues

1. **Sequential WordPress Deployment** (HIGH)
   - All operations run sequentially (theme, plugins, pages, menus)
   - Could parallelize theme + plugin installations
   - **Impact:** 5-10 minute deployments could be 2-3 minutes
   - **Recommendation:** Use asyncio for parallel operations

2. **No Caching** (MEDIUM)
   - Plugin/theme metadata fetched on every run (3MB JSON file)
   - API responses not cached
   - **Impact:** Slower execution, unnecessary API calls
   - **Recommendation:**
     - Cache plugin/theme metadata with TTL
     - Use httpx caching middleware for read-only API calls

3. **Large File Reads** (LOW)
   - `plugins_latest.json` is 3MB, loaded into memory
   - **Impact:** Memory footprint
   - **Recommendation:** Use streaming JSON parser or database

### Security Issues

1. **Secrets in Environment Variables** (HIGH)
   - Secrets passed via env vars (standard practice, but not ideal)
   - No secrets manager integration
   - `.env` file in project root (risk of accidental commit)
   - **Impact:** Secrets exposure risk
   - **Recommendation:**
     - Integrate with secrets manager (Bitwarden CLI, 1Password CLI)
     - Add pre-commit hook to block `.env` commits
     - Document secrets rotation process

2. **No Input Validation for User Content** (MEDIUM)
   - WordPress page content from spec not sanitized
   - Could inject malicious Gutenberg blocks
   - **Impact:** XSS risk in generated sites
   - **Recommendation:**
     - Sanitize all user-provided content before WordPress API calls
     - Validate Gutenberg block JSON structure

3. **SSH Key Hardcoded in Config** (LOW)
   - `VPS_SSH_KEY` defaults to `~/.ssh/id_rsa`
   - No support for SSH agents
   - **Impact:** Less flexible SSH authentication
   - **Recommendation:** Support SSH agent authentication

### Documentation Issues

1. **Inconsistent Documentation** (MEDIUM)
   - Some modules well-documented, others sparse
   - No API reference documentation
   - Missing architecture diagram (until this doc!)
   - **Impact:** Steep learning curve for new developers
   - **Recommendation:**
     - Auto-generate API docs with Sphinx or MkDocs
     - Add more inline code examples

2. **AGENTS.md Accuracy** (LOW)
   - Generally accurate but some outdated references
   - Missing some recent scripts (process_monitor.py)
   - **Impact:** Droid exec may miss best practices
   - **Recommendation:** Keep AGENTS.md in sync with codebase changes

### Operational Issues

1. **No Centralized Logging** (HIGH)
   - Logs scattered across stdout, files, and `.tmp/`
   - No structured logging (JSON format)
   - Hard to debug production issues
   - **Impact:** Poor observability
   - **Recommendation:**
     - Implement structured logging with `structlog`
     - Send logs to centralized system (e.g., Loki, CloudWatch)

2. **No Metrics/Observability** (MEDIUM)
   - No deployment metrics (success rate, duration)
   - No API call tracing
   - **Impact:** Can't measure system health
   - **Recommendation:**
     - Add Prometheus metrics
     - Instrument critical paths (deployment time, API latency)

3. **Manual Deployment** (MEDIUM)
   - No CI/CD pipeline for Fabrik itself
   - Manual deployment to VPS
   - **Impact:** Deployment friction, risk of human error
   - **Recommendation:**
     - Add GitHub Actions workflow for automated deployment
     - Use `fabrik apply` to deploy Fabrik itself (dogfooding!)

---

## Recommendations

### High Priority (Next Sprint)

1. **Add Test Coverage** ✅
   - Start with driver modules (easiest to test)
   - Add integration tests for provisioner saga
   - Target: 60% coverage

2. **Refactor Provisioner** ✅
   - Extract Step 0, 1, 2 into separate classes
   - Add state machine library
   - Improve logging and error messages

3. **Centralized Configuration** ✅
   - Move all env var loading to `config.py`
   - Add Pydantic validation
   - Document all required env vars

4. **Structured Logging** ✅
   - Implement `structlog` throughout
   - Add request ID tracing
   - Send logs to centralized system

5. **CI/CD Pipeline** ✅
   - Add GitHub Actions for tests, lint, type check
   - Automated deployment to VPS

### Medium Priority (Next Month)

6. **Async WordPress Deployment** ⏳
   - Parallelize theme + plugin installations
   - Reduce deployment time by 50%

7. **Error Handling Improvements** ⏳
   - Custom exception hierarchy
   - Retry logic with tenacity
   - Better error messages

8. **Caching Layer** ⏳
   - Cache plugin/theme metadata
   - HTTP response caching

9. **API Documentation** ⏳
   - Generate API docs with Sphinx
   - Publish to ReadTheDocs or GitHub Pages

10. **Secrets Management** ⏳
    - Integrate Bitwarden CLI or 1Password CLI
    - Document secrets rotation

### Low Priority (Future)

11. **Database for Registry** 🔵
    - Replace YAML file with SQLite/PostgreSQL
    - Better querying and scalability

12. **Metrics and Observability** 🔵
    - Prometheus metrics
    - Deployment dashboard

13. **Plugin Architecture** 🔵
    - Allow third-party plugins for new drivers
    - Plugin marketplace

14. **Web UI** 🔵
    - GUI for spec creation
    - Visual deployment dashboard

15. **Multi-VPS Support** 🔵
    - Deploy across multiple VPS instances
    - Load balancing and failover

### Technical Debt Paydown Strategy

**Phase 1 (Month 1):** Foundation
- Add tests, centralized config, structured logging, CI/CD

**Phase 2 (Month 2):** Performance
- Async deployment, caching, error handling improvements

**Phase 3 (Month 3):** Scalability
- Database registry, metrics, secrets management

**Phase 4 (Month 4+):** Innovation
- Plugin architecture, web UI, multi-VPS support

---

## Appendices

### A. Module Line Count Summary

```
Core Modules:
  cli.py                   663 lines
  provisioner.py           667 lines
  coolify.py               532 lines
  spec_loader.py           294 lines
  wordpress/deployer.py    244 lines
  template_renderer.py     217 lines

WordPress Modules:
  section_renderer.py      571 lines
  preset_loader.py         478 lines
  page_generator.py        457 lines
  spec_loader.py           454 lines
  r2.py                    391 lines
  cloudflare.py            358 lines

Total Lines: ~15,000+ (estimated, excluding external deps)
```

### B. External Dependencies (from pyproject.toml)

**Core:**
- click>=8.1.0 (CLI framework)
- pyyaml>=6.0 (YAML parsing)
- httpx>=0.25.0 (HTTP client)
- python-dotenv>=1.0.0 (Env var loading)
- pydantic>=2.0.0 (Data validation)
- rich>=13.0.0 (Terminal formatting)
- psutil>=6.0.0 (Process monitoring)

**Dev:**
- pytest>=7.0.0 (Testing)
- pytest-cov>=4.0.0 (Coverage)
- ruff>=0.1.0 (Linting)
- mypy>=1.0.0 (Type checking)
- pre-commit>=3.0.0 (Git hooks)

### C. Key Files Reference

| File | Lines | Complexity | Purpose |
|------|-------|------------|---------|
| `src/fabrik/provisioner.py` | 667 | High | Saga pattern provisioning |
| `src/fabrik/cli.py` | 663 | Medium | CLI commands |
| `src/fabrik/drivers/coolify.py` | 532 | Medium | Coolify API driver |
| `src/fabrik/wordpress/section_renderer.py` | 571 | High | Gutenberg section rendering |
| `scripts/droid_tasks.py` | 894 | High | Droid exec task runner |
| `scripts/droid_models.py` | 1035 | Medium | Model registry |

### D. Git History Insights

```bash
# Most modified files (last 100 commits)
git log --pretty=format: --name-only | sort | uniq -c | sort -rg | head -20
```

**Top 10 Most Modified:**
1. `docs/` (documentation updates)
2. `src/fabrik/wordpress/` (active development)
3. `scripts/droid_tasks.py` (frequent improvements)
4. `src/fabrik/cli.py` (new commands added)
5. `src/fabrik/provisioner.py` (saga refinement)

---

## Conclusion

Fabrik is a well-architected deployment automation tool with clear separation of concerns, strong driver abstraction, and extensive WordPress automation capabilities. The codebase is in early production stage (v0.1.0) with solid foundations but opportunities for improvement in testing, observability, and performance.

**Strengths:**
- Clean layered architecture
- No circular imports
- Strong Pydantic validation
- Extensive WordPress automation
- Droid exec integration for AI-powered ops

**Weaknesses:**
- Limited test coverage
- Complex provisioner saga pattern
- Sequential WordPress deployment (slow)
- No centralized logging or metrics
- Sparse documentation in some areas

**Next Steps:**
- Focus on test coverage and CI/CD (high priority)
- Refactor provisioner for clarity
- Add structured logging and observability
- Parallelize WordPress deployment for speed

This architecture document serves as the foundation for future development, refactoring, and onboarding new team members.

---

**Document Version:** 1.0
**Last Updated:** 2026-01-04
**Author:** Droid Exec Architecture Analysis Task
