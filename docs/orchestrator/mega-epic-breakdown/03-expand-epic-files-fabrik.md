<!-- ⚠️ FABRIK ORCHESTRATOR COMMAND — OUR OWN TWIN OF `03-expand-epic-files-command.md`
     Unlike the Traycer source, our orchestrator READS THIS FILE DIRECTLY — no GUI copy-paste.
     It is TOOL-CAPABLE: it can read the repo, run commands, and fetch live sources.
     Keep it in lockstep with the Traycer twin; the ONLY intended differences are
     (a) the orchestrator framing, (b) the tool-capable inheritance from `00-trigger-fabrik`,
     and (c) the persistence model — we have NO native ticket store, so tickets are WRITTEN TO DISK
     under docs/development/epics/ (see § Output Contract). Traycer keeps them in its own store.

     ⚠️ Dispatch: the per-epic cross-field ADJUDICATION leg fans out (Step 2, sub-step 2a) — one unit per epic file — but the
     epic-file CONTENT stays single-agent Opus
     `[canonical: docs/superpowers/specs/2026-07-16-traycer-fabrik-twins-design.md § Capability delta —
     "mega-03 (one grounder per epic file)"; and "the synthesis/decision (… the epic-file content …)
     stays the driving Opus's"]`. A grounder that returns Success Criteria or Scope has overstepped.

     Reads — this list is the ACTING set. Every other backticked path below is provenance for a decision
     already stated inline: act on the inline statement, and open the source only if it is insufficient
     (if it IS insufficient, that is a defect in this file — report it, don't quietly absorb the cost):
       · the confirmed artifacts from `02-epic-decomposition-fabrik` + the `00-trigger-fabrik` Vision
         Summary — all from CONVERSATION, not disk (§ Input Contract). 02 writes nothing to disk, so a
         cold re-entry has nothing to re-read: re-run 02 rather than inventing a source.
       · `PORTS.md` — to ground every `Port:` a ticket asserts (Step 2, sub-step 2a)
       · the rule packs 02 named in each epic's `Rule Packs:` — a DYNAMIC set: you open whatever 02 emitted,
         to verify the path resolves. (02 already opened the planning-layer domain packs; you do not.)
       · `/opt/fabrik/src/fabrik/spec_loader.py` — the CURRENT `Shape` flags, never a remembered list
         (a HUB path: the rest of this list is project-relative, this one is not)
       · `ls docs/development/epics/` + `ls docs/superpowers/specs/` — confirm each ticket AND the Infrastructure
         Decisions spec you wrote exist (Step 3). ⚠️ On a REPAIR run, additionally **Read** each named epic
         ticket file before editing it: a retitle or renumber rewrites the Title line and heading in
         place and must preserve a body it did not author (Step 2, sub-step 2c)
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md.
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# Epic Ticket Breakdown

## Role

You are a ticket breakdown orchestrator. You read the confirmed compact epic proposal from `02-epic-decomposition-fabrik` and create one epic ticket per epic. Each ticket is the complete spec a coding agent needs to run `epic-to-ticket-workflow` for that epic — nothing more, nothing less.

## Core Philosophy

- **One ticket per epic.** Title = "Epic N — [Name]". Description = full self-sufficient epic spec.
- **Read the confirmed artifacts, expand, emit as tickets.** Take 02's compact proposal from the conversation (see Step 1), then EXPAND each epic into a full spec with Success Criteria, Out of Scope, Dependencies with specific artifacts, and complete Metadata. Do not invent new scope boundaries — but do flesh out the detail a coding agent needs.
- **DISK is the ticket store.** ⚠️ This is the load-bearing difference from Traycer, which persists tickets natively. **We have no native ticket store — so we write one file per epic:**

  ```text
  docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md
  ```

  (allowlisted in `CLAUDE.md` § HARD STOPS — NEVER and matched by `scripts/enforcement/check_doc_sprawl.py`; the dated shape mirrors the plans convention deliberately). **Write the file — do not leave the ticket in conversation only.**

  ⚠️ **Persist the Infrastructure Decisions spec too — to the SPEC store, not this directory:**

  ```text
  docs/superpowers/specs/YYYY-MM-DD-<project>-infrastructure-decisions.md
  ```

  Every ticket **references** that spec rather than duplicating it (the ticket's `### Infrastructure` section; `04` enforces "reference, not duplicate"), and `02` writes **nothing** to disk — so if you persist only the tickets, the spec dies with this session and the cold-context promise below is false: the ticket alone is not enough, and re-running `02` is exactly the "replaying this session" the file store exists to avoid. Write it ONCE, before the tickets, and cite its full path from every ticket's `### Infrastructure` section.

  ⚠️ **Do NOT put it under `docs/development/epics/`.** That directory's allowlist regex is `epic-<n>-<slug>` (`check_doc_sprawl.py`), so a spec there would have to masquerade as `epic-0` — and `04` (via `epic_order.py`) globs the whole directory and treats every hit as a ticket (counting it, title-checking it, demanding contiguous `1..N`, and flagging the excess as an orphan). `docs/superpowers/specs/**` is allowlisted with free naming, cannot collide with any ticket glob, and is where this chain's canon already lives. A breakdown that lives in the context window dies with it, and `04-cross-epic-validation-fabrik` + the cockpit/driver + `epic-to-ticket-workflow` must be able to read an epic back **on a cold context**, days later, without replaying this session. One epic per file: greppable, dispatchable, reviewable, and diffable.

- **Tool-capable — verify, don't assume.** Our orchestrator is Claude Code: it can **write files, run commands, and call MCP servers, skills, subagents and workflows.** Use that. Where a ticket asserts a port, a pack path, a `shape` flag, or a registrar, **ground it** — read `PORTS.md`, read the pack, read `spec_loader.py` — instead of copying an upstream claim you cannot see. The Traycer twin has to trust its inputs; **this one does not, so it must not.** A ticket citing a file that does not exist is a defect, not a formatting nit.
- **Expand, don't re-derive.** Scope boundaries, dependencies, and scaffold type were decided in `02-epic-decomposition-fabrik`. This step fleshes out the detail within those boundaries — it does not change them.

## Input Contract

**Required — all must be owner-confirmed:**

- Compact Epic Proposal (from `02-epic-decomposition-fabrik`) — confirmed
- Infrastructure Decisions spec (from `02-epic-decomposition-fabrik`) — confirmed
- Dependency Graph (from `02-epic-decomposition-fabrik`) — confirmed
- The confirmed **Vision Summary** (from `00-trigger-fabrik`, still in conversation) — 02 does not restate it, and Step 2 cannot write a ticket without it: `## Full Feature Inventory` (Scope In must cite its feature IDs **and names** — 02's compact entry carries only the numbers), `## Out of Scope (Vision Level)` (vision-level exclusions), and — EXISTING mode — the `## Compliance Report (Existing-mode extra section)` gap row each Retrofit epic's Success Criterion #1 hinges on

⚠️ `docs/operations/fabrik-lifecycle.md` covers **only lifecycle stages 3–4** (deploy/runtime behaviour + data safety); it carries **no** stage model. The 4-stage model (scaffold → implement → `fabrik apply` → `fabrik verify`) is asserted by the command chain itself: a **delta-feature** epic ticket must pass all four. ⚠️ **Retrofit exception:** a Retrofit on an already-deployed service creates **no new deploy unit** — it has no Stage-1/Stage-3 of its own; its Stage-3 equivalent is the gate + the compliance-row flip in Success Criteria #1.

**Hard stop if:** any of the above are missing or not confirmed by owner.

## Processing User Request

### Step 1: Read All Epic Specs

Take every confirmed artifact from `02-epic-decomposition-fabrik` — the Compact Epic Proposal, the Infrastructure Decisions, and the Dependency Graph — **plus the `00-trigger-fabrik` Vision Summary** (§ Input Contract; 02 does not restate it, and Scope In needs its feature names). On the fabrik path these are **in the conversation** (02 emits them there). ⚠️ 02 writes NOTHING to disk, so on a cold re-entry there is nothing to re-read: **re-run 02** rather than inventing a source — a ticket built on a half-remembered proposal is worse than no ticket. There is no `read_spec` tool here — that is Traycer's; our orchestrator reads the repo and the conversation directly.

Log each fetch: "Read: [spec title] — [N] characters."

Count: "Ready to ticket [N] epics."

### Step 2: Create One Ticket per Epic

**2a. Adjudicate each epic's cross-field consistency — DISPATCH, one unit per epic.**

Before writing anything, settle the cross-field questions every ticket will assert. **You supply the facts; the units supply the verdicts** — no boundary is drawn and no scope decided here, which is exactly why this fans out. ⚡ **One unit per epic, in parallel** (each epic is an independent row of 02's proposal and shares no state with the others):

```
fanout("review", units, repo="/opt/<project>", project="mega-expand", mode="read_only")
```

⚠️ **YOU read the disk; the units never do.** `read_only` sets `tools_enabled=False`, so each unit answers only from what you inlined into its `task` text — which is exactly right here, and the ONLY shape that works: `mode="write"` would hand each unit a `git worktree` at HEAD, and in a project **`PORTS.md` and `.windsurf/` are gitignored** (the `.gitignore` "Fabrik-synced" block is generated from the hub-only `/opt/fabrik/scripts/fabrik_synced_manifest.py` and written by `scaffold.py` + `sync_enforcement_to_projects.py`), so a write-mode grounder sees NEITHER — it would report "pack does not resolve" for every epic and fall back to memory on ports. So: **before dispatching, YOU open `PORTS.md` and `ls` the pack paths 02 named, and inline those findings into each unit's task.** A unit asked to check a fact you did not inline will hallucinate it `[canonical: core/62-using-subagents.md § Parallelism — "the parallelism trigger is tools_enabled=False ALONE … all parallel, regardless of owned_paths", and a read-only fan-out that needs file reads inlines them. fanout ALSO gives each unit a unique sentinel owned_paths (libs/subagents/agent.py:740-742) — belt-and-suspenders]`.

**Then add ≥1 native `fabrik-reviewer` on Opus** for the high-risk seam — that `Owned paths:` disjointness carried intact from 02's parallel gates 2/3 and 3/3 — and back-fill every pool run with `set_quality(r.agent_id, score, project="mega-expand", task_type="review", model=r.model)`. **BOTH layers, never either/or; passing `project=` is what records the flywheel** `[canonical: .windsurf/rules/core/62-using-subagents.md § Dispatch policy]`.

Each unit adjudicates, for its epic:
1. **`Port:`** — absent from the **inlined `PORTS.md` allocation table** (a cheap second pair of eyes on YOUR read, not independent verification).
2. **`Rule Packs:`** — every path 02 named appears in the **inlined `ls` output**; a path absent from it does not exist (again: confirming YOUR read).
3. **`Registrars:` ↔ `Shape:`** — consistent, including the carve-outs stated at Metadata below: gatus / authelia / prometheus each need `spec.domain` too, and `infra: {<name>: false}` force-disables.
4. **`Scaffold:`** ∈ the 11 scaffoldable types, and the **i18n trap**: `scripts/validate_i18n.py` ships only to the 5 `I18N_ENABLED_TYPES` — `saas-skeleton` · `static-site` · `desktop-app` · `mobile-app` · `docusaurus`, so a **Success Criterion** citing it on a `python-api` is a defect **unless** the epic carries an explicit vendor-the-i18n-kit step (`templates/i18n-kit/` → `scripts/`) — which `02-epic-decomposition-fabrik` § ── CHECKPOINT: Present Epic Proposal + Infrastructure Decisions ── → 1. Epic list → the compact-entry `i18n:` field makes MANDATORY exactly when the GUI trigger fires on a scaffold outside those 5 `[canonical: 00-trigger-fabrik § Architectural Mandates → i18n — vendor the kit, or the criterion cites a script the project will never have]`.

⚠️ **Checks 3 and 4 are where this leg earns its dispatch** — a per-epic consistency proof over 10 registrars × 8 flags with two carve-out rules, plus a cross-field trap check. Those are exactly the errors a single context makes while composing five tickets at once. Checks 1–2 are cheap confirmations of a read you already did; do not mistake them for independent verification.

**YOU (Opus) keep the writing.** The units return verdicts; you compose the ticket.

**2b. Persist the Infrastructure Decisions spec FIRST — one file, before any ticket.**

Write it to `docs/superpowers/specs/YYYY-MM-DD-<project>-infrastructure-decisions.md` (the spec store — NOT the ticket directory; see § Core Philosophy). Every ticket references it and none duplicates it, so it is half of the dispatch unit: write it before the tickets that point at it, and cite its full path in each ticket's `### Infrastructure` section.

⚠️ **EXISTING mode — carry 02's Deferred Compliance appendix into that same file**, verbatim, under a `## Deferred Compliance (not actioned this run)` section (02 surfaces it even when empty). Those `fix-later` / `accept-as-legacy` rows emit **no** epic, so no ticket can carry them — this file is the only thing that keeps them alive past this session, and `04`'s lens D checks them there.

**2c. Write the tickets.** ⚠️ **Two modes.** *Full run* (the default): every epic below. *Repair run* — when `04` routes back naming specific files (`04` now owns the integrity gate the retired `05` used to run), act on ONLY those and leave every other ticket untouched:
- **recreate** a named epic — write just that one, overwriting any existing file at its path. (A `04` integrity-gate Deficit — `epic_order.py --check` — makes it *missing*; a boundary re-cut routed per `04-cross-epic-validation-fabrik` makes an existing ticket *stale* — same action either way.)
- **renumber** a named mis-numbered file — rewrite its `Epic N — [Name]` **Title line AND the Description's `## Epic N — [Name]` heading** (the file carries the epic string in both) and rename the file to the right `epic-<n>-<slug>`, **reusing its original date prefix**; do NOT write an additional file (that returns an Excess to `04`'s integrity gate and loops);
- **retitle** a named ticket whose Title violates `Epic N — [Name]` (em-dash, single spaces, optional `Retrofit:` prefix) — rewrite the Title line and heading IN PLACE; do NOT renumber it, rename the file, or rewrite the body;
- **delete** a named orphan / redundant copy — `rm` exactly the file named, never one you inferred.
Announce which mode you are in and which files it touches, then re-run `04-cross-epic-validation-fabrik` before handing back: a repaired ticket has never been validated.

For each epic in the confirmed compact proposal (full run) — or each named file (repair run) — **write one ticket file** to `docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md`. Two flavours from 02:

- **Delta-feature epic** — name like `User Management`, `Billing`, etc. Default template (Success Criteria 5–8).
- **Retrofit epic** — name prefixed `Retrofit:` followed by the area (e.g. `Retrofit: i18n`, `Retrofit: Resilience on YouTube Data API`). Same template with the Retrofit-specific Success Criteria variants documented inline; 3–5 criteria permitted (a Retrofit has fewer naturally testable criteria than a delta-feature epic). ⚠️ **Not** conditional on being "code-only". The two N/A predicates are **independent**: **#3** is N/A only for a retrofit touching **no external-call sites** — a `Retrofit: Resilience …` epic **MUST keep #3** (`04-cross-epic-validation-fabrik` § Step 2, lens B flags it otherwise — it fixes up rather than failing, but do not lean on that); **#4** is N/A only for one touching **no mutation surfaces**. When **both** are genuinely N/A, #1 and #2 alone yield 2, so the epic **MUST add at least one area-specific criterion** to reach the floor of 3 (`04-cross-epic-validation-fabrik` § Step 2, lens B flags 'below per-flavour minimum' and fixes it up — there is no justification escape, so write the criterion here rather than making 04 invent it).

Both flavours produce identical ticket structure — the Retrofit prefix carries from `02-epic-decomposition-fabrik` Step 2b into the Title and Summary verbatim.

**Ticket Title:**

```text
Epic N — [Name]
```

**Ticket Frontmatter (REQUIRED — Traycer-ready `[canonical: EPIC-ARTIFACT-SCHEMA.md]`):** every epic file MUST open with the typed frontmatter block below, then the prose body. It is the ONE data model (D10): `scripts/epic_order.py` reads `epic_n`/`depends_on`/`parallel_with`/`owned_paths` for integrity + phased ordering (the code that replaced `05`), and `scripts/traycer_mirror.py` reads `kind`/`title`/`status` for the Traycer card render. ⚠️ `depends_on`/`parallel_with`/`owned_paths` are the **machine form** of the `### Dependencies` prose below — keep them identical (a mismatch is a defect `04` flags).

**Ticket Description (frontmatter block, then the body):**

```markdown
---
kind: story
title: "Epic N — [Name]"
status: 0
epic_n: N
slug: [slug]
depends_on: []          # hard-dep epic numbers (verbatim from 02's Depends on:)
parallel_with: []       # co-phase epic numbers (verbatim from 02's Parallel with:)
owned_paths: [...]       # verbatim from 02's Owned paths: — the concurrency contract
scaffold: [type]
port: [n]
target_vps: [vps]
---
## Epic N — [Name]

### Summary
[3-5 sentences. What this epic delivers. Expanded from compact proposal — not invented.]

### Scope
**In:**
- **[Feature ID]** [Feature name] — [what's included in THIS epic]
- ...

**Out:**
- [Feature or sub-feature] — handled by Epic [N]
- (If single-epic proposal OR this epic has no inter-epic boundary, write a single line: `- none — single-epic proposal` OR `- none — no overlap with other epics`. Do NOT fabricate "handled by Epic [N]" entries when N doesn't exist.)
- ...

### Success Criteria
[5-8 measurable outcomes for delta-feature epics; 3-5 for Retrofit epics — ⚠️ the two N/A predicates are **independent**: **#3** is N/A only for a retrofit touching **no external-call sites** — a `Retrofit: Resilience …` epic **MUST keep #3** (`04-cross-epic-validation-fabrik` § Step 2, lens B flags it otherwise — it fixes up rather than failing, but do not lean on that); **#4** is N/A only for one touching **no mutation surfaces**. When **both** are genuinely N/A, #1 and #2 alone yield 2, so the epic **MUST add at least one area-specific criterion** to reach the floor of 3 — `04-cross-epic-validation-fabrik` § Step 2, lens B flags 'below per-flavour minimum' and fixes it up; there is no justification escape, so write the criterion here rather than leaving 04 to invent it. MUST include AT LEAST ONE deploy/gate-level criterion AND ONE feature/compliance-level criterion. Pick whichever variant of each fits the epic:]
1. Deploy/gate-level — delta-feature epic: `fabrik apply` succeeds; health endpoint returns 200. — Retrofit epic on existing service (no new deploy unit): `python scripts/final_gate.py --json` returns `"status":"success"` (the **FULL Tier-2** gate — mypy + bandit + semgrep; ⚠️ `--lean` is Tier-1, for iteration only, **never** an acceptance gate per `CLAUDE.md` § Completion Contract) for the modified scope, AND the rule pack's compliance check moves from Partial/Violates → Compliant (per the gap row in the Vision Summary's Compliance Report).
2. Feature/compliance-level — delta-feature: [**the `Delivers:` value from 02's compact entry**, restated as an end-to-end user flow that proves the epic works. ⚠️ `Delivers` is the owner-visible outcome negotiated at 02's checkpoint — never drop it] — Retrofit: [the specific behaviour the rule pack mandates is now observable — e.g., `tr` locale renders for an i18n retrofit; rate-limit middleware blocks the test request for an abuse-detection retrofit].
3. [Resilience criterion — what happens when a dependency is down] — N/A for Retrofit epics not touching external-call sites.
4. [Audit logging captures key events from this epic] — N/A for Retrofit epics not touching mutation surfaces.
...

### Out of Scope (Epic Level)
[What this epic does NOT do — name the epic that handles it, OR explain why no other epic handles it.]
- [Exclusion] — handled by Epic [N]
- [Vision-level exclusion (from Vision Summary § Out of Scope (Vision Level))] — not in this product
- (Single-epic / non-overlapping case: state `- none — single-epic proposal` rather than referencing a non-existent Epic [N].)
- ...

### Dependencies
- **Consumes from prior epics:** [specific artifacts: DB tables, API endpoints, env vars, middleware — **carried verbatim from 02's `Consumes:` field**; expand into concrete names, never re-derive] or [`none — root epic`]
- **Produces for later epics:** [specific artifacts this epic creates that others need — **carried verbatim from 02's `Produces:` field**. `Delivers:` is owner-visible value; this is the machine contract downstream epics consume]
- **Depends on:** [Epic X (hard), Epic Y (soft)] or [none — root epic]
- **Parallel with:** [Epic X] or [none]
- **Owned paths:** [the file globs THIS epic writes — carried verbatim from 02's `Owned paths:`. ⚠️ **The concurrency contract.** Every epic named in `Parallel with:` must have DISJOINT owned paths, and at most one epic in a parallel set may own migrations (`alembic/versions/**`, `db/schema.sql`) — 02's parallel gate 2/3 + 3/3 proved this. The executing agent treats these as its **File Scope (owned paths)**: it writes here and nowhere else. A file outside this list showing up in the diff is a scope violation, not a bonus]

### Metadata
- Scaffold: [carried verbatim from 02's `Scaffold:` — one of the 11: `python-api` · `python-api-gpu` · `node-api` · `saas-skeleton` · `file-api` · `file-worker` · `static-site` · `docusaurus` · `chrome-extension` · `mobile-app` · `desktop-app`. ⚠️ `wordpress` is NOT one of them — it survives in `SCAFFOLD_TYPES` for the legacy deploy/shape path only; a WordPress epic is out of scope, route it to `/opt/wpf` `[canonical: 00-trigger-fabrik § Step N1 — agents-fabrik.md § Scaffold Types carries the wordpress row, marked RETIRED (scaffold path retired 2026-06-17, ef27a2c)]`]
- Port: [value]
- target_vps: [`vps1` (hub, default) / `vps2` / `vps3` — carried verbatim from 02's `Target host:`. Drives the spec's `target_vps:` field, and epic-to-ticket re-checks it as overlay constraint #31. ⚠️ A spoke-targeted service reaches shared infra over the mesh (`10.99.0.1`), NOT by Docker DNS]
- Shape: [`kind` + the 8 canonical flags: is_public, is_admin_dashboard, has_bearer_api, has_persistent_data, needs_database, has_search_feature, needs_cache, exposes_metrics — plus `watchdog.enabled`. Carried verbatim from 02's `Shape:`. ⚠️ `has_bearer_api` fires **no** registrar of its own]
- Concurrency: [mechanism]
- i18n: [mechanism or N/A]
- Responsive: [carry from compact entry verbatim — per `00-trigger-fabrik` § Architectural Mandates (always-read; it points to the Rule-area applicability matrix at Step E3.B), GUI mandates trigger on the *GUI surface*, NOT the scaffold type; mandatory for saas-skeleton / docusaurus front / mobile-app / desktop-app AND for python-api/node-api/file-api when `shape.is_admin_dashboard: true` OR `shape.is_public: true` with HTML output; N/A only when no HTML/native UI exists (pure JSON API, file-worker queue consumer). Chrome-extension popup is fixed 400px (carve-out per `00-trigger-fabrik` § Architectural Mandates → Responsive).]
- Dark+Light: [carry from compact entry verbatim — same feature-based trigger as Responsive above]
- Rule Packs: [IDs]
- HAS_USER_GUIDE: [true/false]
- Registrars: [which of the **10** fire for this epic's deploy unit(s) — 7 flag-driven + grafana (always) + glitchtip (`shape.kind`) + watchdog (opt-OUT: fires unless `watchdog: {enabled: false}`). ⚠️ **gatus, authelia and prometheus ALSO require `spec.domain`** — the flag alone fires nothing (`infrastructure.py:214,255,293`). ⚠️ **Any** registrar — grafana included — can additionally be force-disabled by `infra: { <name>: false }` (`infrastructure.py::_enabled`)]
- Universal categories: [comma-separated numbers from 1–14 this epic owns; copied verbatim from the per-epic compact entry produced by `02-epic-decomposition-fabrik` sub-step 2h]
- Abuse Detection: [required — SaaS scaffold with a free-tier signup surface (per `saas/87-abuse-detection.md`) / N/A — not a free-tier signup surface]
- Email: [transactional / marketing / two-stream (both, separate subdomains per `core/86-email-templates.md`) / none — epic does not send email / N/A]
- FINANCIALS: [required — SaaS scaffold pre-launch (per `saas/88-saas-launch-checklist.md` + `core/40-documentation.md`) / N/A — non-SaaS or this epic does not affect launch gate]

### Infrastructure
Inherited from the Infrastructure Decisions spec at `docs/superpowers/specs/YYYY-MM-DD-<project>-infrastructure-decisions.md` — **cite the real path, do not duplicate the content here.** That path is how a cold-context agent finds it; the spec does not live in this ticket's directory.

### Execution Order
[From Dependency Graph — where this epic sits in the execution sequence]

### Entry Point for epic-to-ticket-workflow
When dispatched, run **`epic-to-ticket-workflow/00-trigger-fabrik` in multi-epic (consume) mode** using this ticket as the starting context — it verifies this ticket's 15-field Metadata block and **emits the INFRA-CHECK** that everything downstream consumes. It then hands off to `01-epic-brief-fabrik`, which uses this ticket as its Epic Brief **input** — `01` § Step 1 Path B reads this file, § Step 5 drafts the brief from it.
⚠️ **Do NOT dispatch straight to `01`.** `01-epic-brief-fabrik` § Path B expects INFRA-CHECK to already exist — it reads "`00-trigger-fabrik` ran in consume mode over the dispatched epic ticket **FILE on disk**", and only `00` emits it. Skipping `00` starves `01` and `03-tech-plan` of every propagated field.
Infrastructure Decisions spec provides the shared infra context.
```

**Expansion rules:**

- Success Criteria must be TESTABLE — "user can do X" not "system supports X."
- Dependencies must name SPECIFIC artifacts — `tenants` table, `current_tenant_id()` function, not "Epic 1's infrastructure."
- Scope In must reference feature IDs from the Vision Summary's Full Feature Inventory.
- Each ticket stands alone — no "see Epic 1 for details" without stating what specifically is needed.

**Write each ticket file as you go** — do not batch all epics before writing. A partial run then still leaves every completed epic durable on disk.

**2d. Mirror each written file into the Traycer store — DETERMINISTIC, call the script (do NOT hand-write the mirror).** `[canonical: EPIC-ARTIFACT-SCHEMA.md; north-star R8/D4 — the projection is code, not prose]` After each epic file lands on disk, and once for the Infrastructure Decisions spec, run:

```bash
python /opt/fabrik/scripts/traycer_mirror.py --src docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md \
       --name epic-<n> --kind story --title "Epic <n> — <Name>" --status 0 --embed
python /opt/fabrik/scripts/traycer_mirror.py --src docs/superpowers/specs/YYYY-MM-DD-<project>-infrastructure-decisions.md \
       --name infra-decisions --kind spec --title "Infrastructure Decisions — <project>" --embed
```

⚠️ **This does not change the store of record.** DISK stays source-of-truth (D8). The script writes `~/.traycer/epics/$TRAYCER_EPIC_ID/artifacts/<name>/index.md` ONLY when `$TRAYCER_EPIC_ID` is set (i.e. running inside Traycer) — so the cockpit renders every epic as a card; it is a **NO-OP headless** (the driver run is untouched). The SAME command therefore works in any `/opt` project, in Traycer or headless.

### Step 3: Confirm

After all tickets are written, list them **with their paths** — and confirm each file exists on disk (`ls docs/development/epics/` **and** `ls docs/superpowers/specs/` — the spec lives in a different tree), don't assert it:

```text
Written:
- Infrastructure Decisions → docs/superpowers/specs/YYYY-MM-DD-<project>-infrastructure-decisions.md ✓
- Epic 1 — [Name] → docs/development/epics/YYYY-MM-DD-epic-1-<slug>.md ✓
- Epic 2 — [Name] → docs/development/epics/YYYY-MM-DD-epic-2-<slug>.md ✓
- ...
- Epic N — [Name] → docs/development/epics/YYYY-MM-DD-epic-N-<slug>.md ✓

Total: [N] tickets + the Infrastructure Decisions spec. Each ticket is dispatchable
independently, against that spec.
```

### Step 4: Route

"All [N] epic tickets created. Run `04-cross-epic-validation-fabrik` to validate cross-epic consistency before dispatching."

## Output Contract

**Produced as epic-ticket FILES — one per epic, written to disk (disk is our ticket store; Traycer's native one does not exist here):**

```text
docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md                    <- one per epic
docs/superpowers/specs/YYYY-MM-DD-<project>-infrastructure-decisions.md <- the spec every ticket cites
```

Both allowlisted in `CLAUDE.md` § HARD STOPS — NEVER; matched by `scripts/enforcement/check_doc_sprawl.py`. The spec lives in the SPEC store precisely so it never lands in `04`'s ticket glob. Each ticket is readable on a **cold context** — that is the whole point — and self-sufficient **together with the Infrastructure Decisions spec** it cites by full path. That pair, on disk, is the complete dispatch unit; nothing else from this session survives.

- One ticket per epic
- Title: `Epic N — [Name]` (delta-feature) or `Epic N — Retrofit: [area]` (Retrofit)
- Description: self-sufficient spec derived verbatim from 02's confirmed output
- Status: TODO (ready for dispatch)

**Consumed by:** coding agents running `epic-to-ticket-workflow/00-trigger-fabrik` in multi-epic (consume) mode when the ticket is dispatched — **not** `01` directly (see the Entry Point note in the template: only `00` emits the INFRA-CHECK that `01` § Path B expects). `01-epic-brief-fabrik` then reads this same ticket file directly (its Path B) — but only AFTER `00` has emitted the INFRA-CHECK.

## Does NOT

- Does NOT leave tickets in conversation only — **write each one to `docs/development/epics/`** (§ Output Contract). An epic that exists only in the context window is lost the moment the window turns over, and the cockpit/driver cannot dispatch what it cannot read.
- Does NOT write tickets anywhere else — the path is allowlisted; inventing a new location trips `check_doc_sprawl.py` and is a governance change, not this command's call.
- Does NOT change epic boundaries or move features between epics — those were confirmed in `02-epic-decomposition-fabrik`. If boundaries need changing, route back to 02.
- Does NOT validate cross-epic consistency — that is `04-cross-epic-validation-fabrik`.
- Does NOT dispatch tickets — dispatch is the cockpit epic-card click / the driver's phase queue (`05-dispatch` retired; ordering via `scripts/epic_order.py`, integrity + order emitted by `04`).

## Acceptance Criteria

- **Cross-field adjudication dispatched through `libs/subagents`** (Step 2, sub-step 2a) — YOU ground (`PORTS.md` + the pack `ls`) and inline the findings; one pool `fanout("review", …, project="mega-expand", mode="read_only")` unit per epic, each with the facts inlined, recording the flywheel via `project=` **AND** ≥1 native `fabrik-reviewer` on Opus for the `Owned paths:` seam, with every pool run back-filled by `set_quality`. Going all-native lands zero flywheel rows `[canonical: core/62-using-subagents.md § Dispatch policy — BOTH layers, never either/or]`.
- The Infrastructure Decisions spec is persisted ONCE to `docs/superpowers/specs/YYYY-MM-DD-<project>-infrastructure-decisions.md` before the tickets — carrying 02's **Deferred Compliance** appendix verbatim as a section (EXISTING mode; those rows emit no epic, so nothing else preserves them) — and every ticket's `### Infrastructure` section cites its full path — without it the tickets reference a spec that died with this session, and the cold-context promise is false.
- All epics from the confirmed proposal have a corresponding epic ticket, and **each is a FILE on disk** at `docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md` — verified by listing the directory, not asserted. A ticket left in conversation only is a **failed run**: `04`, the cockpit/driver, and `epic-to-ticket` must be able to read it on a cold context.
- Each ticket title follows the format: `Epic N — [Name]` (delta-feature) **or** `Epic N — Retrofit: [area]` (Retrofit). ⚠️ The `Retrofit:` prefix is the **sole carrier** of the epic flavour downstream — `epic-to-ticket/00` string-parses the Title. A title like `Epic 4 — i18n Retrofit` silently classifies as Delta-feature.
- Each ticket description is self-sufficient: a coding agent can run `epic-to-ticket-workflow/00-trigger-fabrik` in multi-epic (consume) mode — the chain's real entry point, never `01` directly — using only the ticket + Infrastructure Decisions spec.
- Ticket length is **structure-bounded by the template** (no numeric token cap — per `EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS` item 93). A ticket that will not fit the template means the epic is **over-scoped** → route back to `02-epic-decomposition-fabrik`.
- Each ticket has ALL required sections: Summary, Scope (In/Out), Success Criteria (**5-8** measurable for delta-feature; **3-5** for Retrofit), Out of Scope, Dependencies (with specific artifacts, incl. **Owned paths** — the concurrency contract), Metadata (**all 15 fields**: Scaffold, Port, target_vps, Shape, Concurrency, i18n, Responsive, Dark+Light, Rule Packs, HAS_USER_GUIDE, Registrars, Universal categories, Abuse Detection, Email, FINANCIALS), Infrastructure reference, Execution Order, Entry Point.
- Success Criteria are testable — "user can do X", not "system supports X."
- Dependencies name specific artifacts (tables, functions, endpoints, env vars), not vague references.
- Scope boundaries unchanged from 02's confirmed proposal — no feature migration without routing back to 02.
- Ticket count matches epic count from the compact proposal.
- Route to `04-cross-epic-validation-fabrik` stated after confirmation.
