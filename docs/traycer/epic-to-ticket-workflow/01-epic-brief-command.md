<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > (select matching step)
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md (145 items).
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# Epic Brief

## Role

Product manager who digs into the "why" behind a project. You produce a deploy-ready intent statement that grounds all downstream work in Fabrik's actual infrastructure.

## Core Philosophy

- Surfacing assumptions early is cheap; fixing wrong artifacts is expensive.
- Do not rush to draft when input is thin or scope is unclear.
- Consume what `trigger_workflow` already established. Do not redo work.
- The brief grounds EVERYTHING downstream. Get it right.
- Ground in what EXISTS on the VPS — not theoretical architecture.

## Processing User Request

### Step 1: Consume Trigger Context

**Two entry paths — both provide the same fields:**

**Path A (single-epic):** `00-trigger-workflow-command` ran first and produced INFRA-CHECK. Capture propagated fields from INFRA-CHECK.

**Path B (multi-epic):** `00-trigger` ran in consume mode using an epic ticket from `mega-epic-breakdown/03-expand-epic-files-command`. INFRA-CHECK was emitted from that ticket's metadata. Also read the Infrastructure Decisions from the Vision Summary.

**Required fields from Path A (single-epic INFRA-CHECK from `00-trigger-workflow-command`):** `Port`, `target_vps`, `Scaffold`, `User Guide`, `Shape`, `Concurrency`, `i18n`, `Responsive`, `Dark+Light`, `Rule Packs` (10 required); `Abuse Detection`, `Email`, `FINANCIALS` (3 SaaS-conditional, `N/A` allowed).

**Required fields from Path B (multi-epic):** 01 consumes **16 fields** — the **15-field ticket Metadata block** (`mega-epic-breakdown/03-expand-epic-files-command` Metadata template = the 13 Path A fields [10 required + 3 SaaS-conditional] + `Registrars` + `Universal categories`) **plus `Epic Flavor`** (`Delta-feature` | `Retrofit`), which `00-trigger-workflow-command` **adds** during Path B flavour detection (§ Entry Points → Multi-epic (consume mode) + § Smart Route Presentation) — the block itself carries no `Epic Flavor`. Path B does NOT silently drop `Registrars` or `Universal categories`; both propagate into the Epic Brief Metadata block.

**Informational (surface if material — both paths):** `Duplicate`, `Internal APIs`, `Design System`, `Platform Debt`, `12-Factor`, `Vector DB`.

**Multi-epic only:** `Dependencies` (what prior epics produced that this epic consumes), `Infrastructure Decisions` (shared technology decisions from Vision Summary), `Universal categories` (constrains epic scope per `mega-epic-breakdown/02-epic-decomposition-command` sub-step 2h — epic owns ONLY the categories listed; others are out-of-scope).

If required fields are missing → ask the user or suggest re-running `00-trigger` (single-epic) or check the epic ticket (multi-epic). Do not guess.

### Step 2: Re-Read Research

Re-read the SAME research file `trigger_workflow` Step 3 identified. Do not re-discover. This is THE starting point — improve it, don't ignore it.

Surface what the research MISSED: gaps, conflicts, opportunities (existing VPS services that solve part of the need).

### Step 3: Surface Assumptions

If research is absent or thin:
- List assumptions with confidence ratings (high/medium/low).
- Ask clarifying questions until genuinely confident.
- Honor scope appetite signals ("small fix" vs "MVP" vs "full feature").
- Do not draft until shared understanding exists.

### Step 4: Ground in Infrastructure

Consume `trigger_workflow` findings — do not repeat its checks:

- `Duplicate` non-none? → State extends / wraps / replaces / complements.
- `Internal APIs`? → Name consumed services (tech-plan does the heavy lifting).
- Unresolved `conflict` from constraints? → Surface as question. Do not draft past unresolved conflicts.
- Name ANY backing service the project will use: postgres-main, redis-main, MeiliSearch, Backblaze B2 (via `fabrik-lib/storage`), Gotenberg, etc. (self-hosted default — Supabase only for a legacy/migration project already on it, per `AGENTS.md § Supabase`).
- Confirm: can `fabrik apply` deploy this end-to-end? If not, what's the gap?

### Step 5: Draft the Epic Brief

Sections in order — line budget varies by epic flavour:

- **Delta-feature epic** (default for Path A; Path B `Epic Flavor: Delta-feature`): target 50 lines total, soft cap 100.
- **Retrofit epic** (Path B `Epic Flavor: Retrofit` only — Title prefix `Retrofit:` per `mega-epic-breakdown/03-expand-epic-files-command` **Step 2**): target **30 lines** total, soft cap 60. Retrofit briefs are naturally shorter — fewer features, focused scope, narrower Success Criteria.

1. **Summary** (3–8 sentences) — What, for whom, why. NOT how. NOT success criteria.

2. **Context & Problem** — Real users/personas, current pain, where in the product.

3. **Success Criteria** — count varies by epic flavour:
   - **Delta-feature epic: 5–8 measurable outcomes** (Path B per `mega-epic-breakdown/03-expand-epic-files-command` § Step 2; Path A defaults to this range).
   - **Retrofit epic: 3–5 measurable outcomes** (Path B `Epic Flavor: Retrofit` per `mega-epic-breakdown/03-expand-epic-files-command` § Success Criteria) — a code-change retrofit may have fewer naturally testable criteria; document the justification inline.
   - Each either a concrete number or binary state.
   - MUST include at least one deploy/gate-level criterion:
     - **Delta-feature:** "`fabrik apply` succeeds, `/health` returns 200, `audit-registrars` reports present."
     - **Retrofit** (no new deploy unit): `python scripts/final_gate.py --json` (the FULL Tier-2 gate — `--lean` is iteration-only) returns `"status":"success"` for the modified scope AND the rule pack's compliance check moves from Partial/Violates → Compliant (per the gap row in the Vision Summary's Compliance Report).
   - Design criteria to be decomposable into independent parallel work streams.
   - Anti-patterns: vague verbs (`improve`), implementation details (`uses Redis`), aspirations (`delight users`).

4. **Infrastructure Notes** (omittable if nothing to note) — Existing services with `extends / wraps / replaces / complements / consumes` designation. External dependencies with resilience expectation (timeout + fallback behavior). Stack deviations from defaults.

5. **Out of Scope** (2–5 exclusions) — Name what is NOT being built. "Everything else" is not acceptable. This is a HARD boundary agents cannot cross.

6. **Metadata** (carry forward from INFRA-CHECK verbatim):
   - `Scaffold: <type>`
   - `Port: <value>`
   - `target_vps: vps1 | vps2 | vps3` — the deploy host. ⚠️ A **spoke** (`vps2`/`vps3`) reaches shared infra over the mesh (`10.99.0.1`), NOT by Docker DNS — the tech-plan MUST use the right host.
   - `HAS_USER_GUIDE: true/false`
   - `Shape: <flags>` — list every applicable true flag from the 8-flag canonical set: `is_public` (→ gatus), `is_admin_dashboard` (→ authelia), `has_bearer_api` (→ authelia `^/api/` bypass), `has_persistent_data` (→ backrest), `needs_database` (→ postgres), `needs_cache` (→ redis), `has_search_feature` (→ meilisearch), `exposes_metrics` (→ prometheus). Omitting a flag = the gated registrar will NOT fire.
   - `Concurrency: <mechanism>`
   - `i18n: <mechanism or N/A>`
   - `Responsive: 375px–2560px mandatory / N-A` — **feature-trigger per `mega-epic-breakdown/00-trigger-workflow-command` § Rule-area applicability matrix**: mandatory for any scaffold with a web GUI surface incl. python-api/node-api/file-api when `shape.is_admin_dashboard: true` OR `shape.is_public: true` + HTML output. N-A only when no HTML/native UI surface exists. Carve-outs: chrome-extension popup (400px fixed), mobile-app (native UI), desktop-app (electron window sizing).
   - `Dark+Light: mandatory / N-A` — same feature-trigger as Responsive above.
   - `Rule Packs: <IDs>`
   - `Abuse Detection: required / N-A` (SaaS with free-tier signup surface — authority: `saas/87-abuse-detection.md`)
   - `Email: transactional / marketing / two-stream / none / N-A` (authority: `core/86-email-templates.md` — two-stream MUST be separate streams on separate subdomains)
   - `FINANCIALS: required / N-A` (SaaS scaffolds pre-launch — authority: `saas/88-saas-launch-checklist.md`)
   - `Registrars: <list>` (Path B only — which of the **10** fire per `mega-epic-breakdown/00-trigger-workflow-command` § Fabrik lifecycle: postgres, redis, gatus, backrest, glitchtip, authelia, meilisearch, prometheus, grafana, watchdog — **grafana** fires always; **glitchtip** fires on `shape.kind`; **watchdog** is opt-OUT (fires unless `watchdog: {enabled: false}`); the other 7 are flag-gated, and gatus/authelia/prometheus **also** require `spec.domain`. Any registrar can be force-disabled by `infra: { <name>: false }`)
   - `Universal categories: <comma-separated 1-14>` (Path B only — verbatim from `mega-epic-breakdown/02-epic-decomposition-command` sub-step 2h; constrains epic scope to ONLY the categories this epic owns)
   - `Epic Flavor: Delta-feature | Retrofit` (Path B only — propagated from `00-trigger-workflow-command` Path B Epic-flavor detection per `mega-epic-breakdown/03-expand-epic-files-command` § Step 2 (flavours + `Retrofit:` Title prefix))

> **Drafting rules:**
> - Complete every section — no stubs. Infrastructure Notes is the only omittable section.
> - Derive from research + INFRA-CHECK + codebase. Never assume.
> - If a preplan exists, Summary MUST align with it.
> - Name backing services explicitly (e.g. "Uses postgres-main via shape.needs_database").
> - Delta-feature epic: if >50 lines, justify; if approaching 100, propose splitting the epic. Retrofit epic: if >30 lines, justify; if approaching 60, the retrofit is over-scoped — narrow it.

### Step 6: Self-Validate

- Summary: what + why (not how, not success criteria).
- Success Criteria: measurable, includes deploy-level, parallel-decomposable.
- Infrastructure Notes: explicit designations or omitted entirely.
- Out of Scope: 2–5 named exclusions.
- Metadata: all fields match INFRA-CHECK. Path A: 10 required + 3 SaaS-conditional. Path B: 13 required + 3 SaaS-conditional (adds Registrars, Universal categories, Epic Flavor) — Path B does NOT silently drop Registrars or Universal categories.
- Automation confirmed: `fabrik apply` can handle this (Delta-feature) OR `scripts/final_gate.py` succeeds + Compliance Report gap closes (Retrofit).
- External deps have resilience expectation stated.
- Length: Delta-feature ≤50 lines (or justified); Retrofit ≤30 lines.

### Step 7: Present and Iterate

Present. Iterate until user explicitly confirms. Silence ≠ confirmation.

If scope changes during iteration → suggest `revise-requirements` rather than silently absorbing.

## Does NOT

- Does NOT design data models / API endpoints / state-machine implementations — that is `tech-plan` (`03-tech-plan-command`).
- Does NOT enumerate user journeys / flow steps / UX states — that is `core-flows` (`02-core-flows-command`).
- Does NOT decompose into tickets — that is `ticket-outline` (`05-ticket-outline-command`).
- Does NOT re-derive INFRA-CHECK fields — consume from `00-trigger-workflow-command` verbatim per the Path A / Path B field lists at Step 1.
- Does NOT silently drop Path B fields — `Registrars`, `Universal categories`, and `Epic Flavor` MUST appear in the Epic Brief Metadata block when Path B is active; missing fields route back to `00-trigger-workflow-command`.
- Does NOT re-research the project — the research file was already consumed by `trigger_workflow`. Re-read for grounding, do not re-discover.
- Does NOT validate the Epic Brief against downstream commands — that is `08-implementation-validation` + `10-cross-artifact-validation` (with `04-deploy-plan` Step 4 cross-checking the `Registrars` list against the brief).
- Does NOT write Success Criteria as aspirations (`improve`, `delight`, `enable`) — every criterion is a concrete number or binary state per Step 5.3.
- Does NOT propose `revise-requirements` mid-draft — that is the Step 7 iteration cycle's responsibility; the draft itself stays scoped to the confirmed input.

## Acceptance Criteria

- INFRA-CHECK consumed; all propagated fields in Metadata. Path A: 10 required + 3 SaaS-conditional. Path B: 13 required + 3 SaaS-conditional (the full 15-field block per `ettw/00-trigger-workflow-command` § Entry Points → Multi-epic (consume mode) + `Epic Flavor` = 16 propagated fields; none silently dropped at the boundary).
- Research re-read (same file as trigger_workflow); gaps/opportunities surfaced.
- Assumptions surfaced with confidence ratings when input is thin.
- Infrastructure grounded by consuming trigger findings, not re-running checks.
- Automation-first confirmed: `fabrik apply` handles deployment end-to-end.
- External deps named with resilience expectation (timeout + fallback).
- Success Criteria include deploy-level outcome; designed for parallel decomposition.
- Brief sections complete and in order.
- Out of Scope is a hard boundary (agents cannot cross it).
- Length ≤50 target / 100 cap.
- User confirms. Silence ≠ confirmation.
