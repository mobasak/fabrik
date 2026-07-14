<!-- ⚠️ FABRIK ORCHESTRATOR COMMAND — OUR OWN TWIN OF `03-expand-epic-files-command.md`
     Unlike the Traycer source, our orchestrator READS THIS FILE DIRECTLY — no GUI copy-paste.
     It is TOOL-CAPABLE: it can read the repo, run commands, and fetch live sources.
     Keep it in lockstep with the Traycer twin; the ONLY intended differences are
     (a) the orchestrator framing, (b) the tool-capable inheritance from `00-trigger-fabrik`,
     and (c) the persistence model — we have NO native ticket store, so tickets are WRITTEN TO DISK
     under docs/development/epics/ (see § Output Contract). Traycer keeps them in its own store.
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

  (allowlisted in `CLAUDE.md` § HARD STOPS and matched by `scripts/enforcement/check_doc_sprawl.py`; the dated shape mirrors the plans convention deliberately). **Write the file — do not leave the ticket in conversation only.** A breakdown that lives in the context window dies with it, and `05-dispatch-epic-tickets-command` + `epic-to-ticket-workflow` must be able to read an epic back **on a cold context**, days later, without replaying this session. One epic per file: greppable, dispatchable, reviewable, and diffable.

- **Tool-capable — verify, don't assume.** Our orchestrator is Claude Code: it can **write files, run commands, and call MCP servers, skills, subagents and workflows.** Use that. Where a ticket asserts a port, a pack path, a `shape` flag, or a registrar, **ground it** — read `PORTS.md`, read the pack, read `spec_loader.py` — instead of copying an upstream claim you cannot see. The Traycer twin has to trust its inputs; **this one does not, so it must not.** A ticket citing a file that does not exist is a defect, not a formatting nit.
- **Expand, don't re-derive.** Scope boundaries, dependencies, and scaffold type were decided in `02-epic-decomposition-fabrik`. This step fleshes out the detail within those boundaries — it does not change them.

## Input Contract

**Required — all must be owner-confirmed:**

- Compact Epic Proposal (from `02-epic-decomposition-fabrik`) — confirmed
- Infrastructure Decisions spec (from `02-epic-decomposition-fabrik`) — confirmed
- Dependency Graph (from `02-epic-decomposition-fabrik`) — confirmed

Additionally read: `docs/operations/fabrik-lifecycle.md` — ⚠️ it covers **only lifecycle stages 3–4** (deploy/runtime behaviour + data safety); it carries **no** stage model. The 4-stage model (scaffold → implement → `fabrik apply` → `fabrik verify`) is asserted by the command chain itself: a **delta-feature** epic ticket must pass all four. ⚠️ **Retrofit exception:** a Retrofit on an already-deployed service creates **no new deploy unit** — it has no Stage-1/Stage-3 of its own; its Stage-3 equivalent is the gate + the compliance-row flip in Success Criteria #1.

**Hard stop if:** any of the above are missing or not confirmed by owner.

## Processing User Request

### Step 1: Read All Epic Specs

Take every confirmed artifact from `02-epic-decomposition-fabrik` — the Compact Epic Proposal, the Infrastructure Decisions, and the Dependency Graph. On the fabrik path these are **in the conversation** (02 emits them there); on a re-entry into a fresh session, re-read them from wherever the orchestrator persisted them. There is no `read_spec` tool here — that is Traycer's; our orchestrator reads the repo and the conversation directly.

Log each fetch: "Read: [spec title] — [N] characters."

Count: "Ready to ticket [N] epics."

### Step 2: Create One Ticket per Epic

For each epic in the confirmed compact proposal, **write one ticket file** to `docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md`. Two flavours from 02:

- **Delta-feature epic** — name like `User Management`, `Billing`, etc. Default template (Success Criteria 5–8).
- **Retrofit epic** — name prefixed `Retrofit:` followed by the area (e.g. `Retrofit: i18n`, `Retrofit: Resilience on YouTube Data API`). Same template with the Retrofit-specific Success Criteria variants documented inline; 3–5 criteria permitted (a Retrofit has fewer naturally testable criteria than a delta-feature epic). ⚠️ **Not** conditional on being "code-only". The two N/A predicates are **independent**: **#3** is N/A only for a retrofit touching **no external-call sites** — a `Retrofit: Resilience …` epic **MUST keep #3** (`04-cross-epic-validation` § Step 3 fails it otherwise); **#4** is N/A only for one touching **no mutation surfaces**. When **both** are genuinely N/A, #1 and #2 alone yield 2, so the epic **MUST add at least one area-specific criterion** to reach the floor of 3 (`04` fails 'below per-flavour minimum' — no justification escape).

Both flavours produce identical ticket structure — the Retrofit prefix carries from `02-epic-decomposition-fabrik` Step 2b into the Title and Summary verbatim.

**Ticket Title:**

```text
Epic N — [Name]
```

**Ticket Description:**

```markdown
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
[5-8 measurable outcomes for delta-feature epics; 3-5 for Retrofit epics — ⚠️ the two N/A predicates are **independent**: **#3** is N/A only for a retrofit touching **no external-call sites** — a `Retrofit: Resilience …` epic **MUST keep #3** (`04-cross-epic-validation` § Step 3 fails it otherwise); **#4** is N/A only for one touching **no mutation surfaces**. When **both** are genuinely N/A, #1 and #2 alone yield 2, so the epic **MUST add at least one area-specific criterion** to reach the floor of 3 — `04` fails 'below per-flavour minimum' with no justification escape. MUST include AT LEAST ONE deploy/gate-level criterion AND ONE feature/compliance-level criterion. Pick whichever variant of each fits the epic:]
1. Deploy/gate-level — delta-feature epic: `fabrik apply` succeeds; health endpoint returns 200. — Retrofit epic on existing service (no new deploy unit): `python scripts/final_gate.py --json` returns `"status":"success"` (the **FULL Tier-2** gate — mypy + bandit + semgrep; ⚠️ `--lean` is Tier-1, for iteration only, **never** an acceptance gate per `CLAUDE.md` § Completion Contract) for the modified scope, AND the rule pack's compliance check moves from Partial/Violates → Compliant (per the gap row in the Vision Summary's Compliance Report).
2. Feature/compliance-level — delta-feature: [**the `Delivers:` value from 02's compact entry**, restated as an end-to-end user flow that proves the epic works. ⚠️ `Delivers` is the owner-visible outcome negotiated at 02's checkpoint — never drop it] — Retrofit: [the specific behaviour the rule pack mandates is now observable — e.g., `tr` locale renders for an i18n retrofit; rate-limit middleware blocks the test request for an abuse-detection retrofit].
3. [Resilience criterion — what happens when a dependency is down] — N/A for Retrofit epics not touching external-call sites.
4. [Audit logging captures key events from this epic] — N/A for Retrofit epics not touching mutation surfaces.
...

### Out of Scope (Epic Level)
[What this epic does NOT do — name the epic that handles it, OR explain why no other epic handles it.]
- [Exclusion] — handled by Epic [N]
- [Vision-level exclusion (from Vision Summary § Out of Scope)] — not in this product
- (Single-epic / non-overlapping case: state `- none — single-epic proposal` rather than referencing a non-existent Epic [N].)
- ...

### Dependencies
- **Consumes from prior epics:** [specific artifacts: DB tables, API endpoints, env vars, middleware — **carried verbatim from 02's `Consumes:` field**; expand into concrete names, never re-derive] or [`none — root epic`]
- **Produces for later epics:** [specific artifacts this epic creates that others need — **carried verbatim from 02's `Produces:` field**. `Delivers:` is owner-visible value; this is the machine contract downstream epics consume]
- **Depends on:** [Epic X (hard), Epic Y (soft)] or [none — root epic]
- **Parallel with:** [Epic X] or [none]

### Metadata
- Scaffold: [one of the 11 scaffoldable types per `00-trigger-fabrik` § Shape model — carried verbatim from 02's `Scaffold:`]
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
Inherited from Infrastructure Decisions spec (do not duplicate here).

### Execution Order
[From Dependency Graph — where this epic sits in the execution sequence]

### Entry Point for epic-to-ticket-workflow
When dispatched, run **`epic-to-ticket-workflow/00-trigger-fabrik` in multi-epic (consume) mode** using this ticket as the starting context — it verifies this ticket's 15-field Metadata block and **emits the INFRA-CHECK** that everything downstream consumes. It then hands off to `01-epic-brief-command`, which uses this ticket as the Epic Brief.
⚠️ **Do NOT dispatch straight to `01`.** `01` § Path B expects INFRA-CHECK to already exist ("`00-trigger` ran in consume mode — INFRA-CHECK was emitted from that ticket's metadata"), and only `00` emits it. Skipping `00` starves `01` and `03-tech-plan` of every propagated field.
Infrastructure Decisions spec provides the shared infra context.
```

**Expansion rules:**

- Success Criteria must be TESTABLE — "user can do X" not "system supports X."
- Dependencies must name SPECIFIC artifacts — `tenants` table, `current_tenant_id()` function, not "Epic 1's infrastructure."
- Scope In must reference feature IDs from the Vision Summary's Full Feature Inventory.
- Each ticket stands alone — no "see Epic 1 for details" without stating what specifically is needed.

**Write each ticket file as you go** — do not batch all epics before writing. A partial run then still leaves every completed epic durable on disk.

### Step 3: Confirm

After all tickets are written, list them **with their paths** — and confirm each file exists on disk (`ls docs/development/epics/`), don't assert it:

```text
Tickets written:
- Epic 1 — [Name] → docs/development/epics/YYYY-MM-DD-epic-1-<slug>.md ✓
- Epic 2 — [Name] → docs/development/epics/YYYY-MM-DD-epic-2-<slug>.md ✓
- ...
- Epic N — [Name] → docs/development/epics/YYYY-MM-DD-epic-N-<slug>.md ✓

Total: [N] tickets. Each is dispatchable independently.
```

### Step 4: Route

"All [N] epic tickets created. Run `04-cross-epic-validation-command` to validate cross-epic consistency before dispatching."

## Output Contract

**Produced as epic-ticket FILES — one per epic, written to disk (disk is our ticket store; Traycer's native one does not exist here):**

```text
docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md
```

Allowlisted in `CLAUDE.md` § HARD STOPS; matched by `scripts/enforcement/check_doc_sprawl.py`. Each file is self-sufficient and readable on a **cold context** — that is the whole point.

- One ticket per epic
- Title: `Epic N — [Name]` (delta-feature) or `Epic N — Retrofit: [area]` (Retrofit)
- Description: self-sufficient spec derived verbatim from 02's confirmed output
- Status: TODO (ready for dispatch)

**Consumed by:** coding agents running `epic-to-ticket-workflow/01-epic-brief-command` when the ticket is dispatched.

## Does NOT

- Does NOT leave tickets in conversation only — **write each one to `docs/development/epics/`** (§ Output Contract). An epic that exists only in the context window is lost the moment the window turns over, and `05` cannot dispatch what it cannot read.
- Does NOT write tickets anywhere else — the path is allowlisted; inventing a new location trips `check_doc_sprawl.py` and is a governance change, not this command's call.
- Does NOT change epic boundaries or move features between epics — those were confirmed in `02-epic-decomposition-fabrik`. If boundaries need changing, route back to 02.
- Does NOT validate cross-epic consistency — that is `04-cross-epic-validation-command`.
- Does NOT dispatch tickets — that is `05-dispatch-epic-tickets-command` (dispatch step).

## Acceptance Criteria

- All epics from the confirmed proposal have a corresponding epic ticket, and **each is a FILE on disk** at `docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md` — verified by listing the directory, not asserted. A ticket left in conversation only is a **failed run**: `05-dispatch` and `epic-to-ticket` must be able to read it on a cold context.
- Each ticket title follows the format: `Epic N — [Name]` (delta-feature) **or** `Epic N — Retrofit: [area]` (Retrofit). ⚠️ The `Retrofit:` prefix is the **sole carrier** of the epic flavour downstream — `epic-to-ticket/00` string-parses the Title. A title like `Epic 4 — i18n Retrofit` silently classifies as Delta-feature.
- Each ticket description is self-sufficient: a coding agent can run `epic-to-ticket-workflow/01-epic-brief-command` using only the ticket + Infrastructure Decisions spec.
- Ticket length is **structure-bounded by the template** (no numeric token cap — per `EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS` item 93). A ticket that will not fit the template means the epic is **over-scoped** → route back to `02-epic-decomposition-fabrik`.
- Each ticket has ALL required sections: Summary, Scope (In/Out), Success Criteria (**5-8** measurable for delta-feature; **3-5** for Retrofit), Out of Scope, Dependencies (with specific artifacts), Metadata (**all 15 fields**: Scaffold, Port, target_vps, Shape, Concurrency, i18n, Responsive, Dark+Light, Rule Packs, HAS_USER_GUIDE, Registrars, Universal categories, Abuse Detection, Email, FINANCIALS), Infrastructure reference, Execution Order, Entry Point.
- Success Criteria are testable — "user can do X", not "system supports X."
- Dependencies name specific artifacts (tables, functions, endpoints, env vars), not vague references.
- Scope boundaries unchanged from 02's confirmed proposal — no feature migration without routing back to 02.
- Ticket count matches epic count from the compact proposal.
- Route to `04-cross-epic-validation-command` stated after confirmation.
