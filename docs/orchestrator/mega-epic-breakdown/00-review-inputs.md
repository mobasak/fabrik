# Operator review inputs — `00-trigger-mega-epic-fabrik.md`

Running ledger of the operator's review inputs for mega `00`. **Process: every new input is recorded
here FIRST, then implemented into the command file.** One row per input; status cites the commit.

| # | Date | Operator input (condensed, faithful) | Decision / implementation | Status |
|---|---|---|---|---|
| 1 | 2026-07-19 | Rename `00-trigger-fabrik.md` → `00-trigger-mega-epic-fabrik.md` | `git mv` + repo-wide reference retarget (governance maps, chains, north-star, driver spec, skill shim); 13 ettw cross-refs briefly broken by the rename script were caught + repaired | ✅ `95f3052f` |
| 2 | 2026-07-19 | Output must be "not only vision summary — decisions to lock **with** the vision summary" | The Vision Summary is framed as the project's **decisions lock**: persisted on confirm with a `**Status:** LOCKED <date>` header (the BIG-flow Gate-1 marker), Traycer mirror `--status 2`; driver spec's Gate-1 row updated to grep it | ✅ `95f3052f` |
| 3 | 2026-07-19 | Is `agents-fabrik.md` 100% up to date and correct? | Honest answer: **no** — proven immediately (it still described the live Kilo/Cascade/Claude triad). Stale lines fixed + fleet-synced. Full proof-grade currency = a `/fabrik-docs-review` convergence run — **offered, not yet run** | ✅ fix `ab3fe325` · ⏳ optional convergence run |
| 4 | 2026-07-19 | `fabrik preplan` is a MANUAL step the operator does with Gemini deep research, ChatGPT and Claude | Phase-1 line rewritten: preplan = operator-manual deep research dropped into `docs/preplans/*.md`; the `fabrik preplan` CLI (verified to exist) merely files/ingests it | ✅ `95f3052f` |
| 5 | 2026-07-19 | Windsurf Cascade + Kilo CLI are RETIRED — only Claude OAuth Max + OpenRouter | Swept from mega-00's context + the ettw chain (constraint #27 rewritten, INFRA-CHECK enum, 01 template, 03, 06) + `agents-fabrik.md`; saved as durable memory. NOT swept (siblings' lanes): `docs/reference/kilo/**`, `.windsurf/rules/ai/*` | ✅ `95f3052f` + `ab3fe325` |
| 6 | 2026-07-19 | Are the registrar claims 100% correct? (10 registrars, 7 flag-driven, grafana always, glitchtip kind, watchdog opt-out) | Verified against `infrastructure.py::resolve_applicability` — **100% matches code**; no edit needed. Nuance the text omits (harmless): every registrar also has an `infra.<name>: false` kill-switch override | ✅ verified, no change |
| 7 | 2026-07-19 | Responsive 375px mandate — but some SaaS sites can't be mobile-compatible; what to do? | Default stays 375px→2560px; added the **owner-exception path**: `Responsive: desktop-first (owner-approved exception — <why>)` recorded in the vision/decisions artifact, floor still stated (e.g. ≥1024px); never silent, never for public marketing surfaces | ✅ `95f3052f` |
| 8 | 2026-07-19 | Is the fleet-topology paragraph 100% correct? (3 hosts, mesh, hub-only infra, target_vps regex, resolution order) | Verified: regex `spec_loader.py:778`, resolution order `cli.py:944` (flag > state > spec > vps1), cited files exist, hub/spoke facts match the core map — **100% correct**; no edit | ✅ verified, no change |
| 9 | 2026-07-19 | Why does the Shape-model table exist? Is it up to date and 100% factual? | Purpose: intake-time registrar awareness so Technology Decisions never propose silently-under-provisioned services (shape blocks stay `02`'s per-epic job). Every row verified vs code (bearer bypass `infrastructure.py:836-842`, saas-skeleton defaults, gzip `scaffold.py:2955`, `Kind` enum, 11-template kind mapping) — **100% factual**; optional nuance: `infra.<name>: false` override unmentioned | ✅ verified, no change |

| 10 | 2026-07-19 | **WordPress development is DROPPED** ("not good at building with AI systems"). Replacement vision: fast, multilingual, on-brand static company/marketing + content/blog sites (one Vendure-backed store as the dynamic case), AI-generated from a brand kit, managed by conversation — agency-grade, factory-built | All mega files: WP references flipped from "out of scope → `/opt/wpf`" to **RETIRED**; site-building visions route to `/opt/web-ecommerce-factory`. `Kind.WORDPRESS` + `/opt/wpf` remain legacy-deploy-only | ✅ this commit |
| 11 | 2026-07-19 | **`/opt/web-ecommerce-factory` is in development** — Astro 6 static-first (zero-JS default, React islands only where unavoidable) · Turborepo/pnpm · Tailwind v4 `@theme` fed by DTCG 2025.10 brand-kit tokens · Zod-typed Astro Content Collections (AI writes into typed slots, build rejects invalid) · Astro i18n + mt-router (DeepL→Azure→LLM) · images FLUX/Recraft/Stability or Pexels/Pixabay per brand kit + SEO `asset_contract` · `/opt/seo` Briefs → `content_contract` → Zod build-gate refinements · generator CLI (TS/Node) brand-dna+page-plan → Astro repo · gate: tsc+Zod+`astro build`+contract · deploy `fabrik apply` + site-provisioner (Cloudflare DNS/SSL/GA4/GSC/HSTS) · ecommerce = self-hosted Vendure (GraphQL/NestJS/Postgres, API-only so no copyleft) + `fabrik-lib/payments` (iyzico/Paddle). Spec: `specs/services/web-ecommerce-factory.yaml` | Recorded here as the canonical tech reference; mega files carry only the compact routing pointer (no bloat) | ✅ this commit |

| 12 | 2026-07-19 | **⚠️ PROCESS RULE (binding on me): command files are canonical rules, NEVER changelogs.** No "RETIRED (date — reason)", "removed <date>", supersedes-notes, commit hashes, or delta-vs-old annotations in command files / rule packs. State only the current rule, present tense; when a rule changes, DELETE the old text. History lives in git, this ledger, and CHANGELOG — not in the commands | All change-annotations I had written stripped from mega 00/02/03/04, mega checklist, ettw 00/03/06, and the 62 pack; rule saved to durable memory | ✅ this commit |

| 13 | 2026-07-19 | "Why is `/opt/wpf` still in my 00 file?" — `/opt/wpf` does not belong in the commands at all | Every `/opt/wpf` / `wpf` mention purged from BOTH chains (mega + ettw incl. route tables, skip lists, checklists); websites route to `/opt/web-ecommerce-factory`, stated present-tense | ✅ this commit |

| 14 | 2026-07-19 | External systems are stored in `secrets/all-envs.env` — is the tech-stack guide reference stale? Is the env fully up to date, how often refreshed? | Commands now ALSO read `scripts/service_catalog.json` (the secret-free projection of `all-envs.env` — the only form agents may read; the guide reference stays for stack DEFAULTS). Freshness verified: consolidation current (zero `/opt/*/.env` newer than it); refresh is ON-DEMAND via `refresh_service_inventory.py` (built as a cron entry-point but NOT scheduled) | ✅ this commit · ⏳ operator call: schedule the cron |

## Prior inputs that shaped both `00`s (context)

- Decisions must never live only in chat → `00`s are chat-only; persistence lives in `01-decisions-lock`
  (ettw) / the LOCKED vision file (mega). A required template exists for the decisions artifact.
- Traycer case: the persisted file is mirrored as a named Traycer artifact (`decisions` / `vision`).
- No history/rename comments bloating command files — git carries provenance.

## Open items from this review

1. Optional: `/fabrik-docs-review` convergence run on `agents-fabrik.md` for a proof-grade currency claim (#3).
2. Optional: add the `infra.<name>: false` kill-switch nuance to the registrar + Shape-table prose (#6, #9) — say the word.
3. Siblings' lanes still carrying Kilo/Cascade content: `docs/reference/kilo/**`, `.windsurf/rules/ai/*` (#5).
