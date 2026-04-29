# Documentation Currency Review — 2026-04-28

**Author:** Cascade (post-mission audit after B23–B46 live-deploy proof)
**Scope:** every `*.md` under `/opt/fabrik/docs/`, plus root-level `INDEX.md`, `README.md`, `CHANGELOG.md`, `PORTS.md`, `tasks.md`, `AGENTS.md`, `AGENTS-compact.md`, `.env.example`.
**Trigger:** owner request "archive historical and review documentation again. we have made too many changes so documentation needs deep attention."

This report is the second half of the 2026-04-28 doc sweep. The first half — archiving 11 historical/superseded files and removing live Duplicati references — is captured in `CHANGELOG.md [Unreleased]`. This file documents what is **still stale or under-documented** so the owner (or a follow-up agent) can act on it.

---

## A. Resolved this pass (already actioned)

| # | What | Where |
|---|---|---|
| A1 | 11 historical docs archived via `git mv` | `docs/archive/2026-04-28-*` and `docs/development/plans/archived/` |
| A2 | Backrest replaces Duplicati in 7 live docs | `INDEX.md`, `README.md`, `PORTS.md`, `docs/SERVICES.md`, `docs/CONFIGURATION.md`, `docs/TROUBLESHOOTING.md`, `tasks.md` |
| A3 | `DUPLICATI_PASSPHRASE` removed from `.env.example` | `.env.example:50` (deleted) |
| A4 | `docs/DEPLOYMENT.md` backup-pointer corrected | `docs/DEPLOYMENT.md:6` |
| A5 | Lesson 32 added (silent-fallback pattern, key-alignment tests) | `docs/LESSONS_LEARNT.md` |
| A6 | `docs/reference/orchestrator.md` verifier description corrected | `docs/reference/orchestrator.md:47` |
| A7 | `--keep-on-failure` flag documented | `docs/reference/fabrik-cli-reference.md:53,61` |
| A8 | Two new TROUBLESHOOTING entries (verifier 404; Docusaurus terminal grace) | `docs/TROUBLESHOOTING.md:85–114` |
| A9 | `proof_run.py` registered in INDEX | `INDEX.md:478` |
| A10 | `docs/DEPLOYMENT.md` Last Updated banner refreshed | `docs/DEPLOYMENT.md:5` |

---

## B. Still stale — recommend follow-up

These are real currency gaps the owner should be aware of. Not actioned this pass to keep the diff scoped to the user's stated request (archive + review).

### B1. `docs/reference/scripts.md` — missing `proof_run.py`

- **Current state:** 404 lines, no mention of `proof_run.py` (`grep -c proof_run docs/reference/scripts.md` → 0).
- **Why it matters:** `proof_run.py` is the canonical regression harness for the deploy pipeline (per Lesson 32). Anyone changing `verifier.py`, `validator.py`, `spec_generator.py`, or `scaffold.py` should run it. Without an entry here it's invisible.
- **Suggested fix:** add a section `## proof_run.py` covering `SCAFFOLD_TYPES`, `--keep-on-failure`, `proof-logs/` outputs, the direct-Cloudflare DNS-cleanup fallback, and the "run quarterly + after pipeline changes" cadence. ~30 lines.

### B2. `docs/reference/templates.md` — count drift

- **Current state:** doc claims "12 templates as of 2026-04-22, all with `defaults.yaml`"; doc body has 31 backtick-prefixed table rows; `ls templates/` shows **16 directories** (some are not deploy templates: `prompts/`, `traycer/`, `scaffold/`, `spec-pipeline/`).
- **Why it matters:** The "12" number now appears in `INDEX.md:289` and is referenced from archived `DEPLOY_TEMPLATE_AUDIT_2026-04-10.md`. Drift makes future audits noisy.
- **Suggested fix:** decide which dirs under `templates/` are *deploy* templates vs. tooling, restate the canonical count, and either auto-generate the table from `templates/*/defaults.yaml` or freeze the number into the Last-Updated banner. Possibly worth adding a `scripts/enforcement/check_templates_table.py` Tier-2 script.

### B3. `docs/reference/health-monitoring.md` — last touched 2026-04-14

- **Current state:** version 1.2.0, dated before Lesson 31 (workers skip HTTP probe, 2026-04-26) and Lesson 32 (B23 healthcheck-key fix, 2026-04-28).
- **Why it matters:** This is the human-readable companion to the verifier; it predates two material changes to verifier behavior.
- **Suggested fix:** sync with `docs/reference/orchestrator.md:47`. Add: (a) "verifier reads `spec.health.path` not `spec.healthcheck.path`"; (b) worker scaffolds skip HTTP probe and check `running:healthy`; (c) `terminal_grace_period=180s` for slow Node multi-stage builds. Probably 20–40 lines.

### B4. `docs/QUICKSTART.md` — pre-mission (2026-04-22)

- **Current state:** 129 lines, Last Updated 2026-04-22 — predates B23–B46.
- **Why it matters:** This is the first doc a new user reads. If it shows the old `fabrik apply` behavior (verifier 404 fallback, no `--keep-on-failure`) the user will hit the exact 404 we just fixed.
- **Suggested fix:** quick read-through; likely just bump the "Last Updated" and add a one-liner about `--keep-on-failure` to the troubleshooting paragraph. ~10 lines.

### B5. `docs/FAQ.md` — last touched 2026-02-26

- **Current state:** 687 lines, **two months stale**. Predates: Coolify migration (2026-04-17), Authelia 2FA (2026-04-17), Backrest (2026-04-17), monitoring stack migration to Coolify (2026-04-17), shape-driven orchestrator (2026-04-22), B23–B46 (2026-04-28).
- **Why it matters:** Largest single source of stale guidance in the repo.
- **Suggested fix:** **dedicated cleanup pass**, not a one-shot edit. Either (a) audit each Q&A and patch in place, or (b) declare the FAQ rewrite a Phase task and seed an Unreleased FAQ rewrite plan. Recommend option (b) — 687 lines ≠ casual edit.

### B6. `docs/FEATURES.md` — last touched 2026-03-08

- **Current state:** 219 lines, ~7 weeks stale. Pre-Coolify-migration, pre-Authelia, pre-shape-orchestrator.
- **Why it matters:** It's marketing-source material per its own header. Stale features list = stale marketing.
- **Suggested fix:** owner-driven revision; agent edit alone risks under- or over-claiming. Defer.

### B7. `docs/reference/roadmap.md` — phase markers may be stale

- **Current state:** 305 lines. Roadmap marks Phase 1 as "Current"; the codebase has shipped Phase 4j (per `docs/development/plans/2026-04-18-zero-touch-deployment.md`).
- **Why it matters:** Disagrees with the active plan doc.
- **Suggested fix:** reconcile with `docs/development/plans/2026-04-18-zero-touch-deployment.md` and `docs/development/PLANS.md`. Decide: is the roadmap authoritative, or are the plan docs? Probably plan docs win and the roadmap should be retired or auto-generated.

### B8. `docs/operations/coolify-migration.md`

- **Current state:** Modified (per `git status`) but not yet committed; needs a check whether content matches the **completed** migration state (2026-04-17).
- **Suggested fix:** read the diff, confirm it reflects the completed migration, then either land it or revert.

### B9. Multiple "Modern GUI Approaches…" research notes in `docs/reference/`

- `Modern GUI Approaches for a Lean, Fast, Effective, Low-Confusion SaaS Web App.md`
- `Modern GUI Approaches for Chrome Extensionst.md` (note typo in filename)
- `Modern Mobile GUI Approaches for Android and iOS.md`
- **Why they exist:** research dumps from earlier prompt-engineering work.
- **Why it matters:** they live alongside *reference* docs but read like one-shot research outputs. They don't follow `kebab-case` naming (per AGENTS.md). The `docs/reference/SaaS-GUI.md` and the rule packs `60-saas-ui.md` / `ocoron-design-system.md` are the canonical sources now.
- **Suggested fix:** either rename to kebab-case + move under `docs/reference/research/`, or archive. Recommend archive — the design system is the source of truth.

### B10. `docs/reference/exampleconsultancysitemap.md`

- **Current state:** lowercase smashed-together filename; clearly a one-shot artifact.
- **Suggested fix:** archive or rename `docs/reference/research/example-consultancy-sitemap.md`.

### B11. `docs/operations/n8n-webhooks.md`, `docs/operations/vps-status.md`, `docs/operations/vps-urls.md`

- **Current state:** not audited this pass; high probability of drift after the Coolify migration (2026-04-17) and the addition of Authelia (2026-04-17), Gotenberg (2026-04-14), Meilisearch (2026-04-14), Backrest (2026-04-17).
- **Suggested fix:** spot-check `vps-urls.md` at minimum — it's a frequently-referenced quick-reference.

### B12. `.kilo/`, `.droid/` historical artifacts surfaced during search

- **Current state:** `.droid/traycer-reports/` and `.droid/review-context/` contain 2026-04-10 / 2026-03-25 artifacts referencing now-archived plan filenames.
- **Why it matters:** they're tooling history, not user-facing docs. Not in scope but flagged for awareness.
- **Suggested fix:** none required. Document only.

### B13. `INDEX.md` — extensive lint debt + rendering inconsistencies

- **Current state:** the IDE flagged ~70 markdownlint warnings while editing (MD060 table-column-style, MD040 fenced-code-language, MD032 blanks-around-lists). All pre-existed today's edits.
- **Why it matters:** linters won't be useful as guardrails until the pre-existing debt is paid down.
- **Suggested fix:** dedicated lint-cleanup pass with a script (`prettier`, `mdformat`, or `markdownlint --fix`). Out of scope for content review.

---

## C. Conventions to consider adding

These came up during the audit. Not bugs — process improvements.

### C1. Single canonical "Last Updated" header

Many docs use slightly different formats: `**Last Updated:** YYYY-MM-DD`, `**Date:** YYYY-MM-DD`, `**Version:** X.Y.Z` + `**Last Updated:**`, no header at all. A simple `scripts/enforcement/check_doc_header.py` could enforce one shape.

### C2. "When to read this" preamble for plans

`docs/development/plans/*.md` files swing between active, paused, and silently-completed. A standard top-of-file `**Status:** [ACTIVE|IN PROGRESS|COMPLETE|SUPERSEDED]` line + auto-archive of `COMPLETE` after N days would prevent the kind of stale-plan accumulation we just cleaned.

### C3. Archive naming convention

This pass used `docs/archive/2026-04-28-<slug>.md` for top-level archives and `docs/development/plans/archived/<original-name>.md` for plan archives. Two different conventions in one tree. Pick one. Recommend the dated prefix everywhere — it sorts chronologically and avoids slug collisions.

### C4. Auto-generated `INDEX.md` rows

`INDEX.md` currently embeds every doc's purpose by hand. The mission's Lesson 32 noted that **silent fallbacks** are dominant defects. The same risk applies to docs: every manual `INDEX.md` entry is a silent-fallback site (the entry says one thing, the file says another). Worth scripting.

---

## D. Files reviewed and confirmed current

- `docs/DEPLOYMENT.md` — refreshed today
- `docs/TROUBLESHOOTING.md` — refreshed today
- `docs/LESSONS_LEARNT.md` — Lesson 32 added today
- `docs/reference/orchestrator.md` — refreshed today
- `docs/reference/fabrik-cli-reference.md` — `--keep-on-failure` added today
- `INDEX.md` — `proof_run.py` added today; archived rows annotated
- `README.md` — Backrest replaces Duplicati; otherwise dates align
- `PORTS.md` — Backrest port updated
- `tasks.md` — services table updated
- `docs/CONFIGURATION.md` — Last Updated 2026-04-26; Backrest swap done today; otherwise current
- `docs/SERVICES.md` — services table updated today
- `AGENTS.md` (Traycer) — Last Updated 2026-04-17; **mostly current** but worth re-verifying once B23–B46 settle
- `AGENTS-compact.md` (coding agents) — short by design; verify it still reflects the current rule set after this sweep

---

## E. Recommended next pass

If a follow-up agent (or the owner) wants to keep going, the highest-leverage targets in priority order:

1. **B5: `docs/FAQ.md`** — biggest staleness, most user-visible.
2. **B1 + B3: `docs/reference/scripts.md` + `docs/reference/health-monitoring.md`** — small, mechanical, completes the B23–B46 doc trail.
3. **B2: `docs/reference/templates.md`** — count drift; quick fix or auto-gen.
4. **B11: `docs/operations/vps-urls.md`** — operational quick-reference; small.
5. **B7: `docs/reference/roadmap.md`** — reconcile with active plan docs.
6. **B6: `docs/FEATURES.md`** — owner-driven revision; defer.

---

## F. Final state after this pass

- 11 archives moved.
- 7 docs updated to reflect Backrest as the live backup tool.
- 1 stale env var removed.
- 1 new doc created (this file).
- CHANGELOG `[Unreleased]` updated.
- Estimated remaining stale-doc surface area: ~7 files (FAQ, health-monitoring, scripts, templates, roadmap, FEATURES, vps-urls/n8n-webhooks/vps-status). Of these, only FAQ is large.
