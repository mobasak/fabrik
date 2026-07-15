<!-- ⚠️ FABRIK FACTORY WORKFLOW — EPIC BRIEF (our own, tool-capable twin of 01-epic-brief-command)
     Run DIRECTLY by our orchestrator agent (Claude Code CLI, in VS Code) — never pasted into a planner GUI.
     TOOL-CAPABLE: it READS the dispatched epic file from disk, grounds any external/vendor claim LIVE via
     MCP (exa/brave/firecrawl/context7/github, cite URL + fetch date), and gates with final_gate.py.

     Reads (open NOTHING else to act — every other citation below is `[canonical: …]` provenance you act
     on from the inline decision, or `(deeper, optional: …)` you may skip):
       · the INFRA-CHECK emitted by `00-trigger-fabrik` (Path A) OR the dispatched epic ticket file
         (Path B) — `docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md`
       · the research file — `docs/preplans/*.md` OR `docs/development/plans/00-research.md`
       · `agents-fabrik.md` — § Fabrik Microservices · § Supabase (duplicate check + backing services)
       · `fabrik-lib/README.md` (the module table — to name vendorable services, not to design them)
     -->

<!-- ⚠️ QUALITY GATE: any modification MUST pass EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md
     (every applicable item — N/A is valid; forgetting to check is not). No hard-coded item count here. -->

# Epic Brief

## Role

Product manager who digs into the "why" behind an epic. You produce a deploy-ready intent statement that grounds all downstream work in Fabrik's actual infrastructure. You CONSUME `00-trigger-fabrik`'s findings; you never re-run its checks.

## Core Philosophy

- Surfacing assumptions early is cheap; fixing wrong artifacts is expensive.
- Do not rush to draft when input is thin or scope is unclear.
- Consume what `00-trigger-fabrik` already established. Do not redo work.
- Ground in what EXISTS on the VPS — not theoretical architecture.

## Processing User Request

### Step 1: Consume Trigger Context

**Path A (single-epic):** `00-trigger-fabrik` ran and produced INFRA-CHECK. Capture its propagated fields.

**Path B (multi-epic):** `00-trigger-fabrik` ran in consume mode over the dispatched epic ticket **FILE on disk** (`docs/development/epics/…` — we have no Traycer store). **Read that file**; it is both the INFRA-CHECK source and the epic's starting context.

**Fields consumed (both paths converge on the same set):**

- **Path A** — 10 required: `Port`, `target_vps`, `Scaffold`, `User Guide`, `Shape`, `Concurrency`, `i18n`, `Responsive`, `Dark+Light`, `Rule Packs`; + 3 SaaS-conditional (`N/A` allowed): `Abuse Detection`, `Email`, `FINANCIALS`.
- **Path B** — 16 fields: the 15-field ticket Metadata block (the 13 Path-A fields + `Registrars` + `Universal categories`) **plus `Epic Flavor`**, which `00-trigger-fabrik` adds during flavour detection `[canonical: 00-trigger-fabrik § Entry Points → Multi-epic + § Smart Route Presentation]`. Path B does NOT silently drop `Registrars` or `Universal categories`.

If required fields are missing → route back to `00-trigger-fabrik` (single-epic) or re-read the epic ticket file (multi-epic). Do not guess.

### Step 2: Re-Read Research

Re-read the SAME research file `00-trigger-fabrik` Step 3 identified (its Reads: list names it). Do not re-discover. This is THE starting point — improve it, don't ignore it. Surface what it MISSED: gaps, conflicts, opportunities (existing VPS services that solve part of the need).

### Step 3: Surface Assumptions

If research is absent or thin: list assumptions with confidence ratings (high/medium/low); ask clarifying questions until genuinely confident; honor scope-appetite signals ("small fix" vs "MVP" vs "full feature"). Do not draft until shared understanding exists.

**⚠️ Question bar — ask ONLY when a question clears BOTH: (1) it materially changes the epic or its tickets, AND (2) you cannot resolve it from a convention, `agents-fabrik.md`, the codebase, or an obvious default.** Otherwise decide it, apply the default, note it in one line the owner can override. Batch real questions; never drip trivia.

### Step 4: Ground in Infrastructure

Consume `00-trigger-fabrik`'s findings — do not repeat its checks:

- `Duplicate` non-none? → State extends / wraps / replaces / complements.
- `Internal APIs`? → Name consumed services (the tech-plan does the heavy lifting).
- Unresolved `conflict` from constraints? → Surface as a question; do not draft past it.
- Name ANY backing service the epic will use: `postgres-main`, `redis-main`, MeiliSearch, Backblaze B2 (via `fabrik-lib/storage`), Gotenberg, etc. — self-host default; Supabase only for a legacy/migration project already on it `[canonical: agents-fabrik.md § Supabase]`. Check `fabrik-lib/README.md`'s module table before naming a custom build.
- **If the epic touches any external vendor / API / pricing** → ground it LIVE this run (exa → WebSearch → brave → firecrawl → context7/github), cite URL + fetch date, and pass the URL into the brief so the tech-plan inherits it. A memory-based external claim is a defect.
- Confirm: can `fabrik apply` deploy this end-to-end? If not, what's the gap?

### Step 5: Draft the Epic Brief

Sections in order — line budget varies by flavour:

- **Delta-feature epic** (default for Path A; Path B `Epic Flavor: Delta-feature`): target 50 lines, soft cap 100.
- **Retrofit epic** (Path B `Epic Flavor: Retrofit` — Title prefix `Retrofit:` `[canonical: mega/03 § Step 2]`): target 30 lines, soft cap 60. Naturally shorter — fewer features, narrower Success Criteria.

1. **Summary** (3–8 sentences) — What, for whom, why. NOT how, NOT success criteria.
2. **Context & Problem** — Real users/personas, current pain, where in the product.
3. **Success Criteria** — count by flavour: Delta-feature **5–8**; Retrofit **3–5** `[canonical: mega/03 § Success Criteria]`. Each a concrete number or binary state. MUST include ≥1 deploy/gate-level criterion:
   - **Delta-feature:** "`fabrik apply` succeeds, `/health` returns 200, `audit-registrars` reports present."
   - **Retrofit** (no new deploy unit): `python scripts/final_gate.py --json` returns `"status":"success"` (the FULL Tier-2 gate; `--lean` is iteration-only) for the modified scope AND the rule pack's compliance check moves Partial/Violates → Compliant.
   - Design criteria to decompose into independent parallel work streams. Anti-patterns: vague verbs (`improve`), implementation detail (`uses Redis`), aspirations (`delight users`).
4. **Infrastructure Notes** (omittable if nothing to note) — existing services with `extends / wraps / replaces / complements / consumes`; external deps with resilience expectation (timeout + fallback); stack deviations from defaults.
5. **Out of Scope** (2–5 exclusions) — name what is NOT built. "Everything else" is not acceptable. A HARD boundary agents cannot cross.
6. **Metadata** (carry forward from INFRA-CHECK verbatim): `Scaffold` · `Port` · `target_vps` (a spoke `vps2`/`vps3` reaches shared infra over the mesh `10.99.0.1`, NOT Docker DNS) · `HAS_USER_GUIDE` · `Shape` (the applicable true flags of the 8-flag set: `is_public`→gatus, `is_admin_dashboard`→authelia, `has_bearer_api`→authelia `^/api/` bypass, `has_persistent_data`→backrest, `needs_database`→postgres, `needs_cache`→redis, `has_search_feature`→meilisearch, `exposes_metrics`→prometheus; omitting a flag = that registrar will NOT fire) · `Concurrency` · `i18n` · `Responsive` · `Dark+Light` · `Rule Packs` · `Abuse Detection` · `Email` · `FINANCIALS` · **Path B only:** `Registrars` (which of the 10 fire) · `Universal categories` (1–14, verbatim) · `Epic Flavor`.

> **Drafting rules:** complete every section (Infrastructure Notes is the only omittable one); derive from research + INFRA-CHECK + codebase, never assume; if a preplan exists, Summary MUST align with it; name backing services explicitly. Delta >50 lines → justify; approaching 100 → propose splitting. Retrofit >30 → justify; approaching 60 → narrow it.

### Step 6: Self-Validate

- Summary is what + why (not how, not success criteria).
- Success Criteria measurable, include a deploy-level one, parallel-decomposable.
- Metadata: all fields match INFRA-CHECK — Path A 10 required + 3 SaaS-conditional; Path B 13 required + 3 SaaS-conditional (adds Registrars, Universal categories, Epic Flavor); none silently dropped.
- `fabrik apply` handles it (Delta) OR `final_gate.py` succeeds + Compliance gap closes (Retrofit).
- External deps have a resilience expectation; every external claim carries a fresh cited source.
- Length within the flavour budget.

### Step 7: Present and Iterate

Present. Iterate until the user explicitly confirms — silence ≠ confirmation. If scope changes during iteration → route to `09-revise-requirements-command`, don't silently absorb.

## Does NOT

- Design data models / APIs / state machines — that is `03-tech-plan-command`.
- Enumerate user journeys / flow steps / UX states — that is `02-core-flows-command`.
- Decompose into tickets — that is `05-ticket-outline-command`.
- Re-derive INFRA-CHECK fields — consume from `00-trigger-fabrik` verbatim per Step 1.
- Re-research the project — the research file was consumed by `00-trigger-fabrik`; re-read for grounding, don't re-discover.
- Validate the brief against downstream commands — that is `08`/`10` (the cross-artifact reviews).
- Write Success Criteria as aspirations — every criterion is a number or binary state (Step 5.3).

## Acceptance Criteria

- INFRA-CHECK consumed; all propagated fields in Metadata (Path A 10+3; Path B 16, none dropped).
- Research re-read (same file as trigger); gaps/opportunities surfaced.
- Assumptions surfaced with confidence ratings when input is thin.
- Infrastructure grounded by consuming trigger findings, not re-running checks; external deps live-grounded with cited sources.
- `fabrik apply` handles deployment end-to-end (or the gap is named).
- Success Criteria include a deploy-level outcome; designed for parallel decomposition.
- Sections complete and in order; Out of Scope is a hard boundary; length within budget.
- User confirms.

---

**Next (CC1 pairing, north star § Command-chain build plan):** converge this brief with `/fabrik-ettw-review <brief path> epic-brief` — it forces the no-op (fields present + INFRA-CHECK-consistent, Success-Criteria flavour-correct and non-aspirational, zero hollow citations) before anything consumes it. Then follow `00-trigger-fabrik`'s route (GUI scaffolds → `02-core-flows-command`; headless → `03-tech-plan-command`). *(Downstream ettw twins are built incrementally; refs point to the live Traycer `-command` source and flip to `-fabrik` as each twin lands.)*
