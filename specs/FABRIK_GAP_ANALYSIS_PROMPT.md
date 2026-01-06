# Fabrik Gap Analysis Request

## Your Task

Analyze the Fabrik codebase comprehensively and identify:

1. **Gaps** — Missing functionality that would improve idea-to-product automation
2. **Errors** — Bugs, anti-patterns, or technical debt
3. **Friction Points** — Manual steps that could be automated
4. **Integration Issues** — Poor connections between modules

## What Fabrik Does

Fabrik is a spec-driven deployment automation platform:

- **Spec Engine**: YAML specs define deployments (fabrik new/plan/apply/destroy)
- **Provisioner**: Saga-pattern multi-step deployment with retry/recovery
- **Drivers**: Coolify, Cloudflare, DNS, R2, Supabase, Uptime Kuma, WordPress
- **WordPress Suite**: 17 modules for full WordPress automation
- **Templates**: python-api, node-api, next-tailwind, saas-skeleton, wordpress (145 files)
- **Project Registry**: Tracks all /opt projects
- **AI Enforcement**: Windsurf rules, hooks, convention validators
- **Droid Integration**: Model management, process monitoring, review loops

## Key Files to Analyze

### Core
- `src/fabrik/cli.py` (780 lines) — Main CLI
- `src/fabrik/provisioner.py` (685 lines) — Deployment saga
- `src/fabrik/spec_loader.py` — YAML spec parsing
- `src/fabrik/template_renderer.py` — Jinja2 rendering
- `src/fabrik/verify.py` — Verification framework

### Drivers
- `src/fabrik/drivers/coolify.py` — Coolify API
- `src/fabrik/drivers/cloudflare.py` — Cloudflare API
- `src/fabrik/drivers/supabase.py` — Supabase integration

### WordPress (17 modules)
- `src/fabrik/wordpress/deployer.py` — Full site deployment
- `src/fabrik/wordpress/page_generator.py` — Page creation
- `src/fabrik/wordpress/spec_loader.py` — WordPress specs

### Enforcement
- `scripts/enforcement/validate_conventions.py` — Convention validator
- `.windsurf/rules/*.md` — Cascade rules
- `.windsurf/hooks.json` — Pre/post hooks

### Droid Integration
- `scripts/droid_models.py` — Model management
- `scripts/droid_runner.py` — Droid orchestration
- `scripts/process_monitor.py` — Stuck process detection

## Your Output Format

Provide your analysis in this structure:

### 1. Critical Gaps (P0)
Issues that break the idea-to-product flow

### 2. High-Value Improvements (P1)
Features that would significantly speed up deployment

### 3. Quick Wins (P2)
Easy fixes with good ROI

### 4. Technical Debt (P3)
Code quality issues to address

### 5. Recommended Implementation Order
Prioritized list with effort estimates

## Constraints

- **READ-ONLY**: Do not modify any files
- **Be specific**: Reference exact files and line numbers
- **Be actionable**: Each suggestion should be implementable
- **Focus on automation**: Goal is to minimize manual steps from idea to production

## Questions to Answer

1. What manual steps exist between "I have an idea" and "It's deployed"?
2. What breaks most often during deployment?
3. What takes the longest?
4. What would a competitor platform do better?
5. What's the #1 thing missing?
