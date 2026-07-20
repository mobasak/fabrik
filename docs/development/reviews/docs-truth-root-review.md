# Docs-truth verification ledger — wave: root-canonical (Tier A)

**Plan:** `docs/development/plans/2026-07-20-plan-1-docs-truth-convergence.md` Phase E · **Date:** 2026-07-20
**Method:** native Opus verifier (partitioned children) → verified ledger (scratchpad `e3-root-ledger.md`) → dedicated fixer (re-verified each claim before writing) → my adjudication.

## Coverage & counts

| Doc | Claims | FALSE | STALE | Disposition |
|---|---:|---:|---:|---|
| docs/README.md · agents-fabrik-core.md · BUSINESS_MODEL · STRATEGIC_BACKLOG · CAPABILITIES/PROJECT_CATALOG frames | ~51 | 0 | 0 | CLEAN |
| agents-fabrik.md | ~40 | 0 | 6 | ALL FIXED (46 checks; IDE/AI-stack retirement; WSL-startup row; container-count hedge; age→45 per canonical owner doc) |
| owner_ozgur_basak.md | ~5 | 1 | 3 | ALL FIXED (x86_64 fleet, retired assistants, malformed cell) |
| reference/apis/EXTERNAL_SYSTEMS.md | ~26 | 0 | 4 | ALL FIXED (Supabase retired-default note; residual Netdata entry removed → total 76; WP paths → /opt/wpf verified; xref label) |
| CONFIGURATION.md | ~80 | 4 | 3 | ALL FIXED (config-verify one-liner replaces phantom `-m fabrik.config`; phantom wordpress/deployer/content_publisher blocks → /opt/wpf + notifications.py truth incl. dead-code note; archived-plan xrefs; Supabase) |
| SERVICES.md | 45 | 0 | 1 | FIXED (17 bootstrap steps) |
| TROUBLESHOOTING.md | 26 | 2 | 3 | ALL FIXED (2 entries marked LEGACY-Coolify-era with cannot-recur note; deployer_coolify attribution; line numbers) |
| QUICKSTART.md | 25 | 1 | 4 | ALL FIXED (next-tailwind truth; Cloudflare default; VPS_USER=ozgur; retired-consumer notes) |
| FEATURES.md + DEPLOYMENT_ARCHITECTURE.md | 44 | 4 | 17 | ALL FIXED by dedicated fixer (see workflows/reference ledger for the honest `pick_models` amendment) |
| **Total** | **~342** | **12** | **41** | — |

Dominant class confirmed: retired-tech live-framing (Kilo CLI / Windsurf Cascade / Coolify internals / Supabase-as-default) + references into deleted or relocated code (`deployer_coolify.py`, `provisioner.py`, `/opt/wpf` modules).

**Generated-content flags (upstream, queued for completion report):** CAPABILITIES.md generated CLI rows still say "Coolify API" (generator docstring fix); PROJECT_CATALOG generated "Total 48" vs section-sum 47 (generator).

**UNRESOLVED rows: 0.**
