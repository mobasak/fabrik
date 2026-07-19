<!-- ⚠️ FABRIK FACTORY WORKFLOW — DECISIONS LOCK
     Run DIRECTLY by our orchestrator agent (Claude Code CLI — bare terminal, or inside a Traycer session
     with Claude Code as the backend) — never pasted into a planner GUI.
     TOOL-CAPABLE: it READS the dispatched epic file / 00's chat INFRA-CHECK, grounds any external/vendor
     claim LIVE via MCP (exa/brave/firecrawl/context7/github, cite URL + fetch date), and — its whole
     reason to exist — WRITES the run's ONE persisted decisions artifact. `00` is CHAT-ONLY by design;
     THIS command is where decisions stop living in chat.

     Reads (open NOTHING else to act — every other citation below is `[canonical: …]` provenance you act
     on from the inline decision, or `(deeper, optional: …)` you may skip):
       · the INFRA-CHECK emitted in chat by `00-trigger-fabrik` (Path A) OR the dispatched epic ticket file
         (Path B) — `docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md`
       · the research file — `docs/preplans/*.md` OR `docs/development/plans/00-research.md`
       · `agents-fabrik.md` — § Fabrik Microservices · § Supabase (duplicate check + backing services)
       · `fabrik-lib/README.md` (the module table — to name vendorable services, not to design them)
     -->

<!-- ⚠️ QUALITY GATE: any modification MUST pass EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md
     (every applicable item — N/A is valid; forgetting to check is not). No hard-coded item count here. -->

# Decisions Lock (create the artifact — `01R` converges it, the operator's confirm locks it)

## Role

Decisions officer. `00-trigger-fabrik` oriented and routed **in chat**; you turn that run's findings into
the epic's **one persisted decisions artifact** — every choice, criterion, boundary, and grounded fact a
cold re-entry (or the driver resuming a lane) needs, none of it living only in a context window
`[canonical: north-star D6 — persist on confirm; do NOT leave load-bearing artifacts chat-only]`.
You CONSUME `00`'s findings; you never re-run its checks. You write the artifact as **`Status: DRAFT`** —
locking is NOT yours: `01R-decisions-review-fabrik` converges it to a no-op and the **operator's explicit
confirm** flips it to `LOCKED` (that confirm IS Gate 1).

## Core Philosophy

- Chat is not a store of record. The artifact on disk is.
- Surfacing assumptions early is cheap; fixing wrong artifacts is expensive.
- Consume what `00-trigger-fabrik` already established. Do not redo work.
- Ground in what EXISTS on the VPS — not theoretical architecture.
- **No length cap.** Completeness beats brevity here — this file is the epic's memory. Every section
  present; `none` is a valid value, silence is not.

## Processing User Request

### Step 1: Consume Trigger Context

**Path A (single-epic):** `00-trigger-fabrik` ran and emitted INFRA-CHECK in chat. Capture its propagated fields.

**Path B (multi-epic):** `00-trigger-fabrik` ran in consume mode over the dispatched epic ticket **FILE on
disk** (`docs/development/epics/…` — we have no Traycer store). **Read that file**; it is both the
INFRA-CHECK source and the epic's starting context.

**Fields consumed (both paths converge on the same set):**

- **Path A** — 10 required: `Port`, `target_vps`, `Scaffold`, `User Guide`, `Shape`, `Concurrency`, `i18n`, `Responsive`, `Dark+Light`, `Rule Packs`; + 3 SaaS-conditional (`N/A` allowed): `Abuse Detection`, `Email`, `FINANCIALS`.
- **Path B** — 16 fields: the 15-field ticket Metadata block (the 13 Path-A fields + `Registrars` + `Universal categories`) **plus `Epic Flavor`**, which `00-trigger-fabrik` adds during flavour detection `[canonical: 00-trigger-fabrik § Entry Points → Multi-epic + § Smart Route Presentation]`. Path B does NOT silently drop `Registrars` or `Universal categories`.

If required fields are missing → route back to `00-trigger-fabrik` (single-epic) or re-read the epic
ticket file (multi-epic). Do not guess.

### Step 2: Re-Read Research

Re-read the SAME research file `00-trigger-fabrik` Step 3 identified (its Reads: list names it). Do not
re-discover. This is THE starting point — improve it, don't ignore it. Surface what it MISSED: gaps,
conflicts, opportunities (existing VPS services that solve part of the need).

### Step 3: Surface Assumptions

If research is absent or thin: list assumptions with confidence ratings (high/medium/low); ask clarifying
questions until genuinely confident; honor scope-appetite signals ("small fix" vs "MVP" vs "full feature").
Do not draft until shared understanding exists.

**⚠️ Question bar — ask ONLY when a question clears BOTH: (1) it materially changes the epic or its
tickets, AND (2) you cannot resolve it from a convention, `agents-fabrik.md`, the codebase, or an obvious
default.** Otherwise decide it, apply the default, note it in one line the owner can override. Batch real
questions; never drip trivia.

### Step 4: Ground in Infrastructure

Consume `00-trigger-fabrik`'s findings — do not repeat its checks:

- `Duplicate` non-none? → State extends / wraps / replaces / complements.
- `Internal APIs`? → Name consumed services (the tech-plan does the heavy lifting).
- Unresolved `conflict` from constraints? → Surface as a question; do not draft past it.
- Name ANY backing service the epic will use: `postgres-main`, `redis-main`, MeiliSearch, Backblaze B2 (via `fabrik-lib/storage`), Gotenberg, etc. — self-host default; Supabase only for a legacy/migration project already on it `[canonical: agents-fabrik.md § Supabase]`. Check `fabrik-lib/README.md`'s module table before naming a custom build.
- **If the epic touches any external vendor / API / pricing** → ground it LIVE this run (exa → WebSearch → brave → firecrawl → context7/github), cite URL + fetch date, and record the URL in the artifact so the tech-plan inherits it. A memory-based external claim is a defect.
- Confirm: can `fabrik apply` deploy this end-to-end? If not, what's the gap?

### Step 5: CREATE the Decisions-Lock artifact (the output — an md file, always)

Write `docs/superpowers/specs/YYYY-MM-DD-<slug>-decisions.md` (allowlisted specs tree, matched by
`check_doc_sprawl.py`; Path A: `<slug>` = the project · Path B: `<slug>` = `<project>-epic-<n>`).
**Check before create:** if the file already exists (a prior run), STOP and reconcile — never overwrite a
sibling run's artifact. **This exact skeleton, every section present (`none` allowed, silence not; NO
length cap):**

```markdown
# Decisions Lock — <slug>

**Status:** DRAFT                 <!-- 01R flips to `LOCKED <YYYY-MM-DD>` after its no-op convergence —
                                       Path A: on the operator's explicit confirm (Gate 1); Path B: auto
                                       (the vision was already operator-locked at mega 00). The LOCKED
                                       line is the machine-readable marker downstream automation greps. -->
**Path:** A (project entry) | B (epic-fed: docs/development/epics/<epic-file>.md)
**Run:** <Traycer session | claude -p | interactive CLI> · **Created:** <YYYY-MM-DD>

## Goal
<3–8 sentences: what, for whom, why. NOT how, NOT success criteria. If a preplan exists, MUST align with it.>

## Context & Problem
<Real users/personas (named, never "users"), current pain, where in the product.>

## INFRA-CHECK
<the `00` Step-7 INFRA-CHECK line, verbatim, all fields populated>

## Decisions
| Decision | Choice | Why (one line) |
|---|---|---|
| Scaffold | <type> | <signal it was derived from> |
| target_vps | vps1|vps2|vps3 | <reason — a spoke reaches shared infra at 10.99.0.1, not Docker DNS> |
| Backing services | <postgres-main / redis-main / MeiliSearch / B2 / …> | <extends/wraps/replaces/consumes> |
| LLM gateway | openrouter/none | <reason> |
| Watchdog | accept-defaults/raise/opt-out | <reason> |
| i18n / Responsive / Dark+Light | <mechanism or N/A> | <trigger> |
| <every further choice this run made> | … | … |

## Success Criteria
<Delta-feature: 5–8 · Retrofit: 3–5 `[canonical: mega/03 § Success Criteria]`. Each a concrete number or
binary state; designed to decompose into independent parallel work streams. MUST include ≥1 deploy/gate-level
criterion — Delta: "`fabrik apply` succeeds, `/health` 200, `audit-registrars` present" · Retrofit:
"`final_gate.py --json` → success for the modified scope AND the rule pack's compliance gap closes".
Anti-patterns: vague verbs (`improve`), implementation detail (`uses Redis`), aspirations (`delight users`).>

## Out of Scope
<2–5 exclusions. A HARD boundary agents cannot cross. "Everything else" is not acceptable.>

## Constraint findings
<Path A: all 31 · Path B: the verified subset — one row each: `#N <name> — all clear|conflict|unknown (+note)`.
No silent unknowns.>

## Route
**Confirmed route:** <command sequence> · **Skipped:** <commands + why> · **Next:** <command>

## External dependencies (grounded this run)
| Dependency | Grounded fact (endpoint/limits/pricing) | Source URL · fetch date |
|---|---|---|

## Metadata (carried from INFRA-CHECK, verbatim — none silently dropped)
<Path A: 10 required + 3 SaaS-conditional · Path B: those + `Registrars` + `Universal categories` +
`Epic Flavor` — the field list from Step 1.>

## Open / BLOCKED
<each with a named resolution step, or `none`>
```

Then mirror it — **in a Traycer session this is what makes the `decisions` artifact appear; headless it
no-ops** (env-guarded by `$TRAYCER_EPIC_ID` `[canonical: mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md]`;
DISK is the store of record, the mirror is a projection):

```bash
python /opt/fabrik/scripts/traycer_mirror.py \
       --src docs/superpowers/specs/YYYY-MM-DD-<slug>-decisions.md \
       --name decisions --kind spec --title "Decisions Lock — <slug>" --status 0 --embed
```

### Step 6: Self-Validate (light pass — the adversarial one is `01R`'s job)

- Artifact exists on disk, `Status: DRAFT`, every skeleton section present.
- Goal is what + why (not how, not success criteria).
- Success Criteria measurable, include a deploy-level one, parallel-decomposable, flavour-correct count.
- Metadata: all fields match INFRA-CHECK — Path A 10+3; Path B 16; none silently dropped.
- `fabrik apply` handles it (Delta) OR `final_gate.py` succeeds + Compliance gap closes (Retrofit).
- External deps each carry a resilience expectation + a fresh cited source.

### Step 7: Hand off to `01R` — do NOT lock here

Present the artifact path + a one-screen summary. Then invoke **`01R-decisions-review-fabrik`** on the
file. Do not iterate-to-confirm in this command — the convergence loop AND the operator's lock confirm
both live in `01R`. If the operator volunteers scope changes while you present, fold them into the DRAFT
before handing off (cheap now, expensive later).

## Does NOT

- Design data models / APIs / state machines — that is `03-tech-plan-fabrik`.
- Enumerate user journeys / flow steps / UX states — that is `02-core-flows-fabrik`.
- Decompose into tickets — that is `05-ticket-outline-fabrik`.
- Re-derive INFRA-CHECK fields — consume from `00-trigger-fabrik` verbatim per Step 1.
- Re-research the project — the research file was consumed by `00-trigger-fabrik`; re-read for grounding, don't re-discover.
- **Flip `Status:` to `LOCKED`** — that is `01R` + the operator's explicit confirm (Gate 1). A `01` run
  that self-locks is defective.
- Validate the artifact against downstream commands — that is `08`/`10` (the cross-artifact reviews).
- Write Success Criteria as aspirations — every criterion is a number or binary state.

## Acceptance Criteria

- INFRA-CHECK consumed; all propagated fields in Metadata (Path A 10+3; Path B 16, none dropped).
- Research re-read (same file as trigger); gaps/opportunities surfaced.
- Assumptions surfaced with confidence ratings when input is thin.
- Infrastructure grounded by consuming trigger findings, not re-running checks; external deps live-grounded with cited sources.
- `fabrik apply` handles deployment end-to-end (or the gap is named).
- **The decisions artifact EXISTS on disk** (`docs/superpowers/specs/YYYY-MM-DD-<slug>-decisions.md`,
  `Status: DRAFT`, every skeleton section present) and the Traycer mirror ran (or no-op'd headless).
  A run whose decisions live only in chat is INCOMPLETE.
- Handed off to `01R-decisions-review-fabrik` — this command did NOT lock.

---

**Next:** `01R-decisions-review-fabrik <artifact path>` — the mandatory convergence twin: it grounds every
claim adversarially, loops to an md5-verified no-op, then STOPS for the operator's confirm, which flips
`DRAFT → LOCKED` (Gate 1). Only after `LOCKED` does the chain continue on `00`'s confirmed route (GUI
scaffolds → `02-core-flows-fabrik`; headless → `03-tech-plan-fabrik`).
