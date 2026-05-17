# Code Classification — Use, Modify, or Archive

**Principle:** Existing code serves the vision or gets archived. Nothing is sacred. 9,700 LoC and hundreds of hours of work only matter if they make the factory faster, leaner, or more autonomous.

---

## Classification Key

- **✅ USE** — fits the vision as-is. No changes needed.
- **🔧 MODIFY** — concept is right, implementation needs changes to fit golden base / GUI / watchdog.
- **📦 ARCHIVE** — doesn't serve the vision. Remove from active codebase, keep in git history.
- **❓ TBD** — needs validation during Phase 1 (deploy ocoron.com) to determine if it works.

---

## WordPress Engine (`src/fabrik/wordpress/`)

| File | Classification | Reason |
|---|---|---|
| `__init__.py` | ✅ USE | Public API, clean |
| `spec_loader.py` | 🔧 MODIFY | Works but hardcoded paths. Needs to support golden base context (no fresh install steps). Also: v2 file preference logic can be removed (consolidated specs). |
| `spec_validator.py` | ✅ USE | Schema validation still needed per-site |
| `preset_loader.py` | ✅ USE | Preset merge logic is core to the factory |
| `resolved_spec.py` | ✅ USE | Frozen spec dataclass, clean |
| `planner.py` | 🔧 MODIFY | Hash-based skip logic is good. Needs awareness of golden base (stages 3-4 skip when base image). Build dir creation stays. |
| `deployer.py` | 🔧 MODIFY | Core orchestrator. Needs: (1) golden base detection → skip theme/plugins stages, (2) `FABRIK_EXEC_MODE=local` support, (3) SSE event emission for GUI streaming. Currently returns report — needs to ALSO emit events. |
| `handoff.py` | ❓ TBD | Generates handoff.md report. Useful if you hand sites to clients. May not be needed for self-managed factory. Test during Phase 1. |
| `domain_setup.py` | 🔧 MODIFY | State machine is complex. Currently drives DNS provisioning. With golden base, Phase 1 (domain provision) is SEPARATE from Phase 5 (wp apply). This module may need splitting: pre-deploy DNS vs stage-1 DNS sync. |
| `settings.py` | ✅ USE | Per-site settings always different (blogname, email, timezone) |
| `theme.py` | 🔧 MODIFY | With golden base: theme is PRE-INSTALLED. This module only needs to apply brand colors/fonts from site.yaml. Remove install logic, keep customize logic. |
| `pages.py` | ✅ USE | Page creation via REST API — always per-site, always needed |
| `page_generator.py` | ✅ USE | Generates pages from entities — core factory feature |
| `section_renderer.py` | 🔧 MODIFY | 10 section types work. May need new sections as factory scales. Keep extensible. |
| `menus.py` | ✅ USE | Per-site menus always different |
| `forms.py` | ✅ USE | Per-site forms |
| `seo.py` | 🔧 MODIFY | Good base. Needs: (1) base RankMath settings move to golden base (not re-applied per site), (2) per-site settings (verification codes, homepage meta) stay here. Split base vs per-site. |
| `analytics.py` | ✅ USE | GA4/GTM IDs are always per-site |
| `legal.py` | ✅ USE | Auto-generates privacy/terms per jurisdiction — valuable |
| `media.py` | ✅ USE | Brand asset upload — always per-site |
| `content.py` | ❓ TBD | Uses Claude API directly for page content during initial deploy. Overlaps with TCO service. May be redundant if TCO handles all content. Test: does initial deploy need AI content, or do presets provide enough template content? |
| `cache.py` | ✅ USE | 4-layer flush needed for every site |

## Stages (`src/fabrik/wordpress/stages/`)

| File | Classification | Reason |
|---|---|---|
| `__init__.py` | ✅ USE | Registry + StageResult |
| `dns.py` | 🔧 MODIFY | With golden base: DNS should already be provisioned (Phase 1). Stage 1 becomes a VERIFICATION step (confirm records exist) not a creation step. |
| `settings.py` | ✅ USE | Always per-site |
| `theme.py` | 🔧 MODIFY | Golden base has theme installed. Stage becomes: apply brand customizations ONLY. If no changes from base → skip. |
| `plugins.py` | 🔧 MODIFY | Golden base has base plugins. Stage becomes: install ADDITIONS only (preset-specific: WooCommerce, FluentCRM, etc.). If no additions → skip entirely. |
| `languages.py` | ✅ USE | Per-site locale config |
| `pages.py` | ✅ USE | Always per-site |
| `menus.py` | ✅ USE | Always per-site |
| `forms.py` | ✅ USE | Always per-site |
| `seo.py` | 🔧 MODIFY | Base RankMath config in golden image. Stage applies: per-site verification codes, homepage meta, schema type. |
| `post_deploy.py` | ✅ USE | Sitemap resubmit + GA4 retrieval always needed |
| `analytics.py` | ✅ USE | Per-site GA4/GTM injection |
| `monitoring.py` | ✅ USE | Per-site Gatus + GlitchTip registration |
| `verify.py` | ✅ USE | 10 health checks always needed |

## Manifests (`src/fabrik/wordpress/manifests/`)

| File | Classification | Reason |
|---|---|---|
| `__init__.py` | ✅ USE | Registry |
| `checks.py` | ✅ USE | Verification manifest |
| `plugins.py` | 🔧 MODIFY | Needs split: BASE plugins (in golden image) vs ADDITION plugins (per-preset). Currently treats all as "to install." |
| `menus.py` | ✅ USE | Per-preset menu definitions |
| `pages.py` | ✅ USE | Per-preset page definitions |

## Drivers

| File | Classification | Reason |
|---|---|---|
| `drivers/wordpress.py` | 🔧 MODIFY | Needs `FABRIK_EXEC_MODE=local` (1-line gate). Also: ContainerResolver needs to work without SSH when on VPS. |
| `drivers/wordpress_api.py` | ✅ USE | REST API client — always needed |
| `drivers/dns.py` | ✅ USE | Site-provisioner client — always needed |
| `drivers/seo.py` | ✅ USE | SEO service client — feeds content pipeline |
| `drivers/tco.py` | ✅ USE | TCO client — content generation |
| `drivers/image_broker.py` | ✅ USE | Image sourcing — content pipeline |
| `drivers/glitchtip.py` | ✅ USE | DSN injection per-site |

## Orchestrators

| File | Classification | Reason |
|---|---|---|
| `orchestrator/content_publisher.py` | ✅ USE | Core of Phase 7 content loop |
| `orchestrator/deployer.py` | ✅ USE | Coolify deployment |
| `orchestrator/verifier.py` | ✅ USE | Health checks |
| `deploy_router.py` | 🔧 MODIFY | Needs golden base awareness in routing logic |
| `deploy_validator.py` | ✅ USE | Pre-deploy checks |
| `provisioner.py` | 🔧 MODIFY | Saga pattern good. Needs golden base support (MariaDB container is part of per-site compose, but WP container uses golden image). |
| `notifications.py` | ✅ USE | Telegram via n8n |
| `cli.py` | 🔧 MODIFY | Needs new commands: `fabrik wp create` (one-command), `fabrik watchdog run`. |
| `preplan.py` | ❓ TBD | Preplan capture before scaffold. GUI wizard may replace this. Or preplan feeds the wizard. Validate during Phase 4. |
| `scaffold.py` | 🔧 MODIFY | WordPress scaffold needs to use golden base image in generated compose. |

## Templates

| Path | Classification | Reason |
|---|---|---|
| `templates/wordpress/defaults.yaml` | 🔧 MODIFY | Split: base settings move to golden image build. Remaining defaults are per-site overridable values. |
| `templates/wordpress/presets/*.yaml` | ✅ USE | Core factory feature — 5 site categories |
| `templates/wordpress/schema/v1.yaml` | 🔧 MODIFY | May need new fields for golden base awareness, watchdog config. |
| `templates/wordpress/schema/MERGE_RULES.md` | ✅ USE | Merge logic stays |
| `templates/wordpress/schema/VALIDATION_RULES.md` | ✅ USE | Validation stays |
| `templates/wordpress/base/compose.yaml.j2` | 🔧 MODIFY | Image changes from `wordpress:php8.3-fpm-bookworm` → `fabrik/wp-golden:v1` |
| `templates/wordpress/base/compose-coolify.yaml.j2` | 🔧 MODIFY | Same image change |
| `templates/wordpress/base/compose.dev.yaml.j2` | 🔧 MODIFY | Local dev may keep fresh image for debugging. Or use golden for parity. Decide in Phase 2. |
| `templates/wordpress/base/wp-config-extra.php` | 🔧 MODIFY | Moves INTO golden image Dockerfile. Template becomes a reference/override mechanism for per-site additions. |
| `templates/wordpress/base/nginx/*.conf.j2` | 🔧 MODIFY | Base hardening moves into golden image. Per-site: domain-specific server_name, FastCGI cache rules for specific paths. |
| `templates/wordpress/base/Makefile.j2` | ✅ USE | Operational tooling stays per-site |
| `templates/wordpress/base/site.yaml.j2` | ✅ USE | Scaffold template for new sites |
| `templates/wordpress/plugins/premium/*.zip` | ✅ USE | Bundled into golden image at build time |
| `templates/wordpress/plugins/premium/wp_plugins_activation_notes.md` | ✅ USE | License keys needed during golden base build |
| `templates/wordpress/plugins_latest.json` | 🔧 MODIFY | Becomes the golden base plugin version manifest. Rebuild golden image when this updates. |

## Documentation

| File | Classification | Reason |
|---|---|---|
| `docs/workflows/wordpress-site-workflow.md` | 🔧 MODIFY | Rewrite to reflect golden base + GUI + watchdog flow |
| `docs/reference/wordpress/architecture.md` | 🔧 MODIFY | Update architecture to include golden base layer |
| `docs/reference/wordpress/deployment-workflow.md` | 🔧 MODIFY | Fix Apache→FPM references. Update for golden base. |
| `docs/reference/wordpress/site-specification.md` | ✅ USE | site.yaml format stays |
| `docs/reference/wordpress/pages-idempotency.md` | ✅ USE | Page logic unchanged |
| `docs/reference/wordpress/plugin-stack.md` | 🔧 MODIFY | Split: BASE stack (in golden) vs ADDITION stack (per-preset) |
| `docs/reference/wordpress/plugin-evaluation.md` | ✅ USE | Selection criteria still valid |
| `docs/reference/wordpress/fixes.md` | ✅ USE | Known issues reference |
| `docs/architecture/WORDPRESS-MODULE-INTEGRATION.md` | 🔧 MODIFY | Update for golden base + fabrik-api |
| `.windsurf/rules/62-wordpress.md` | ✅ USE | Rules still valid (they DEFINED the golden base requirements) |
| `docs/reference/wordpress/archived-*.md` | 📦 ARCHIVE | Already archived. Reference only. Best practices extracted into golden base + rule pack. |
| `docs/development/plans/2026-05-17-wordpress-blazing-fast.md` | 📦 ARCHIVE | Superseded by this plan folder. Move to archived/. |

## Specs

| File | Classification | Reason |
|---|---|---|
| `specs/sites/ocoron.com.yaml` | 🔧 MODIFY | Fix WPML→Polylang, fill remaining fields, change status DRAFT→READY |
| `specs/sites/ocoron.com-content-plan.md` | 🔧 MODIFY | Update: Image Broker is BUILT (not "FUTURE"), TCO is BUILT. Remove planning language for shipped features. |
| `specs/sites/ocoron.com-media/` | ✅ USE | Brand assets ready |
| `specs/sites/archived-ocoron.com.v1.*` | 📦 ARCHIVE | Already archived |

## Tests

| Path | Classification | Reason |
|---|---|---|
| `tests/wordpress/` (20 files) | 🔧 MODIFY | Tests that verify "install plugins from scratch" need updating for golden base (verify "additions only"). Stage skip tests needed. |
| `tests/test_scaffold_wordpress_templates.py` | 🔧 MODIFY | Scaffold now generates golden-base compose. Tests need updating. |
| Other WP tests | ✅ USE | Spec resolution, pages, CLI verify — still valid |

---

## Summary

| Classification | Count | % |
|---|---|---|
| ✅ USE as-is | 34 files | 45% |
| 🔧 MODIFY | 33 files | 44% |
| 📦 ARCHIVE | 5 files | 7% |
| ❓ TBD (validate in Phase 1) | 3 files | 4% |

**Key insight:** 45% of the code works as-is. 44% needs targeted modifications (mostly: "skip this when golden base" or "split base vs per-site"). Only 7% gets archived. The hundred hours of work are 93% preserved — just restructured for the factory model.
