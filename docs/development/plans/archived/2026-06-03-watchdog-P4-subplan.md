# P4 Sub-plan — Universal-Coverage Overlay into `02-epic-decomposition-command.md`

**Date:** 2026-06-03
**Phase:** P4 of the AI Watchdog Platform plan (2-day, sub-plan worth writing)
**Parent plan:** [`2026-05-30-ai-watchdog-platform.md`](2026-05-30-ai-watchdog-platform.md) § "What 02 will enforce after P4 (14 universal categories + overlay)" (lines 294–322)
**Prompt that produced this:** [`2026-05-30-ai-watchdog-platform-prompts.md` § P4.A](2026-05-30-ai-watchdog-platform-prompts.md) (lines 377–446)
**Status:** ✅ Sub-plan draft — owner answered 4 open questions 2026-06-03 (revision r1 below); code edits to 02 + 03 STAGED. **No code edits performed yet.**

**Owner decisions captured (r1, 2026-06-03):**

| Q | Owner answer | Sub-plan resolution |
| --- | --- | --- |
| 1. Sub-step naming `2h` vs `Step 2.5`? | `2h` (yes to first option) | Keep `2h` throughout. |
| 2. `docusaurus / static-site` overlay disposition? | "i dont know" → I verified: `domain-modules/docusaurus.md` does NOT exist; only 5 overlays present (`chrome-ext`, `mobile-app`, `rag`, `saas`, `wordpress`) | Treat missing overlay as best-effort: 02's existing reader at lines 62–68 already iterates "for EACH scaffold type identified" — if no file exists, no-op. Parent plan's "docusaurus / static-site: minimal overlay; watchdog disabled" is informational, not a load instruction. New 2h verdict line for category #7 watchdog flips to N/A on `kind` ∈ `{static-site, docusaurus}`. |
| 3. 03 Metadata expansion option (A) ignore or (B) carry verbatim? | "obey metadata and plan" → option (B) | P4.B WILL edit `03-expand-epic-files-command.md` Metadata block (line 99–110) to add one line: `- Universal categories: [list]`. Adds ~1 line of code change to 03. § 7.3 + § 10 + § 8 acceptance updated below. |
| 4. Any side findings to promote? | "what are they" — see § 9 enumeration | 3 in-scope (1, 5, 6); 1 inline-fixed (3); 2 deferred (2, 4); 1 sentinel (7). No additional in-scope work beyond what § 1–8 already covered. |

**Effort:** 2 days (per parent plan § P4 row)
**Prior work shipped:** T-P1 + T-P2 (watchdog config + sidecar + driver + emitter + rule pack `60-watchdog.md`) + T-P3 (`self-healing.md` rule pack). 02 can now cite these as load-bearing references.

---

## 0. Verification (META-RULE 1 — no assumptions)

### 0.1 Files read for this sub-plan (with line counts, verified by `wc -l`)

| File | Lines | Purpose |
| --- | --- | --- |
| `docs/traycer/mega-epic-breakdown/02-epic-decomposition-command.md` | 325 | The surgical-edit target. Full read. |
| `docs/development/plans/2026-05-30-ai-watchdog-platform.md` | 400 | § "What 02 will enforce after P4" (lines 294–322 read) — source of the 14 categories + 6 overlays. |
| `docs/traycer/mega-epic-breakdown/00-trigger-workflow-command.md` | 673 | Upstream consumer; understand what shape 02 receives. Read § Step N4 (lines 277–342) — Vision Summary output. |
| `docs/traycer/mega-epic-breakdown/03-expand-epic-files-command.md` | 177 | Downstream consumer; 02's output must remain compatible. Full read. |
| `docs/traycer/mega-epic-breakdown/domain-modules/saas.md` | 334 | One overlay reference. Read § Part 1 (lines 28–233) — what an overlay provides to 02. |

### 0.2 Confirm 02's current structure (cited line numbers)

| Section | Line range | Notes |
| --- | --- | --- |
| Role | 13–15 | Architect splits Vision Summary into epics. |
| Goal | 17–26 | 5 deliverables; routes to 03. |
| Core Philosophy | 28–35 | Domain-not-layer boundaries; independently deployable epics. |
| Input Contract | 37–68 | Vision Summary required; reads `AGENTS.md`, `PORTS.md`, `fabrik-lifecycle.md`, domain-modules per scaffold. |
| Processing User Request intro | 70–74 | One checkpoint between Step 3 and Step 4. |
| **Step 1 — Consume Vision Summary** | 76–89 | Extract feature inventory, technology decisions, scaffold types, Compliance Report (EXISTING mode). |
| **Step 2 — Identify Epic Boundaries** | 91–156 | Has sub-steps 2a (group by domain), 2b (boundary rules + EXISTING-mode Retrofit emission), 2c (dependencies + parallel-classification gate), 2d (order for value delivery), 2e (background-processing check), 2f (fabrik-lib check), 2g (port allocation). |
| **Step 3 — Draft Infrastructure Decisions** | 158–203 | 10 standard sub-sections (Database Strategy, Auth Strategy, Email Strategy, Background Processing, Embedding Model, Backing Services, External Services, Domain Structure, Shared Env Vars, Shared Shape Decisions). |
| **CHECKPOINT — Present Epic Proposal + Infrastructure Decisions** | 205–268 | 7 numbered presentation blocks (epic list, infra decisions, mermaid graph, coverage check, execution order, deferred-compliance appendix, questions for owner). STOP GENERATION HERE (line 268). |
| **Step 4 — Iterate and Confirm** | 270–278 | Owner-driven iteration; routes to 03. |
| **Output Contract** | 280–294 | 5 produced artifacts (compact proposal, infra decisions, dep graph, coverage check, deferred-compliance appendix). |
| **Does NOT** | 296–302 | 5 explicit non-goals. |
| **Acceptance Criteria** | 304–325 | 13 base criteria + 4 EXISTING-mode adds. |

**Verified shape match with the P4.A spec listing** ("Step 1, Step 2, Step 3, Step 4, Checkpoint, Output Contract, Does NOT, Acceptance") — all present. The Checkpoint sits BETWEEN Step 3 and Step 4 (not after Step 4 as the spec heading order might suggest); this is the correct linear flow.

### 0.3 Confirm 03's input expectation (quoted)

**Quoted from `03-expand-epic-files-command.md` § Input Contract, lines 33–41:**

> **Required — all must be owner-confirmed:**
>
> - Compact Epic Proposal (from `02-epic-decomposition-command`) — confirmed
> - Infrastructure Decisions spec (from `02-epic-decomposition-command`) — confirmed
> - Dependency Graph (from `02-epic-decomposition-command`) — confirmed
>
> **Hard stop if:** any of the above are missing or not confirmed by owner.

And 03 § Step 1 (line 47): "Call `read_spec` for every confirmed artifact from `02-epic-decomposition-command`."

**Important compatibility note from 03's ticket-Metadata block (lines 99–110):** 03 expects the per-epic ticket to carry these metadata fields, which it derives from 02's compact proposal entries:

```text
Scaffold, Port, Shape, Concurrency, i18n, Responsive, Dark+Light, Rule Packs,
HAS_USER_GUIDE, Registrars
```

02's current compact-format block (lines 211–221) produces only: `Scope, Features, Scaffold, Depends on, Parallel with, Port, Delivers, Rule Packs, HAS_USER_GUIDE`. **6 fields 03 expects are not currently in 02's output**: `Shape`, `Concurrency`, `i18n`, `Responsive`, `Dark+Light`, `Registrars`. P4 needs to extend 02's compact format to emit these — and the universal-coverage check is the natural place to derive them.

### 0.4 Existing overlay-loading is already wired in 02

Lines 62–68 already instruct 02 to read `domain-modules/<type>.md` per scaffold type identified in the Vision Summary's Technology Decisions. P4 does NOT need to add overlay LOADING — only to wire the overlay's outputs into the new Universal Coverage Check sub-step and to make sure no duplication happens between the universal categories and the overlay's epic patterns.

---

## 1. The 14 universal categories — where each lands in 02

Each row: category → landing site → reason. Cross-cutting categories that absorb into an existing Step 3 § go there; ones that need an epic in Step 2 surface in the Universal Coverage Check sub-step (proposed in § 2 below). Category numbers match the parent plan's table at lines 298–313.

| # | Category | Trigger | Lands in 02 at... | Type |
| --- | --- | --- | --- | --- |
| 1 | Foundation | Always | **New sub-step 2h "Universal Coverage Check"** (asserts presence) + Step 3 § "Shared Shape Decisions" absorbs the spec `shape:` block | cross-cutting |
| 2 | Features | Always | Existing Step 2a (group features by domain — unchanged) | epic-level |
| 3 | Persistence | `shape.needs_database` | Existing Step 3 § "Database Strategy" (absorbs verbatim — no new sub-section) | infra |
| 4 | Workers | If pipeline/async work | Existing Step 2e "Background processing check" (unchanged; coverage check just asserts it ran) | epic-level |
| 5 | External integrations | Any upstream API use | **Existing Step 3 § "External Services" extended** with a one-line resilience-row pointer ("each entry MUST have a row in the relevant epic's `docs/RESILIENCE.md` per `58-resilience.md` § Per-Project Contract") | infra |
| 6 | Self-healing | `shape.kind ∈ {service, worker, wordpress}` | **New Step 3 § "Self-Healing Ladder" sub-section** (one paragraph + cite to `core/self-healing.md`) | infra |
| 7 | Watchdog wiring | `watchdog.enabled` (default per `kind`) | **New Step 3 § "Watchdog Wiring" sub-section** (cites `core/60-watchdog.md`; names the registrar that fires at `fabrik apply` time) | infra |
| 8 | Observability | Always | Coverage check asserts; concrete decisions land in **new Step 3 § "Observability Defaults" sub-section** (just-pointer; defers to `core/55-observability.md` matrix) | infra |
| 9 | Cost guardrails | LLM/paid-API use | **New Step 3 § "Cost Guardrails" sub-section** (cites `core/cost-budget.md`; names which epics own paid-API calls + their per-incident caps) | infra |
| 10 | Deployment | Always | Coverage check asserts; concrete deployment decisions stay in the existing per-epic shape block + Step 2g "Port allocation" | cross-cutting |
| 11 | Documentation | Always | Coverage check asserts (epic owner produces CHANGELOG/FEATURES/QUICKSTART/RESILIENCE entries in the epic's tickets per `core/40-documentation.md`); no new Step 3 sub-section needed | cross-cutting |
| 12 | Security | Always | **Existing Step 3 § "Auth Strategy" extended** with a one-line pointer to `core/app-audit-log.md` for sensitive-ops audit logging; coverage check asserts both auth and audit-log are covered | infra |
| 13 | Testing | Always | Coverage check asserts (epic owner provides integration tests per `core/45-testing-strategy.md`); no new Step 3 sub-section needed | cross-cutting |
| 14 | Retrofit | EXISTING mode | Existing Step 2b "Existing mode addition" (already emits Retrofit epics; unchanged) | epic-level |

**Net Step 3 changes:** 4 new sub-sections (Self-Healing Ladder, Watchdog Wiring, Observability Defaults, Cost Guardrails) + 2 minor inserts into existing sub-sections (External Services + Auth Strategy). The existing 10 sub-sections stay intact and in order.

---

## 2. New "Universal Coverage Check" sub-step (sub-step 2h)

**Insert point:** After current sub-step 2g "Port allocation" (line 156), before "Step 3: Draft Infrastructure Decisions" (line 158).

**Reason for placement:** 2a–2g produce a candidate epic set + ports; 2h then audits the candidate set against the 14 universal categories BEFORE Step 3 commits to Infrastructure Decisions. If 2h reveals a missing category, the agent re-runs 2a (group) for the missing scope before drafting infra. Placing 2h after Step 3 would risk drafting infra against an incomplete epic set.

**Sub-step heading:** `**2h. Universal Coverage Check:**`

**Purpose paragraph (one paragraph, for the sub-step body):**

> Before drafting Infrastructure Decisions, audit the candidate epic set against the 14 universal categories defined in `docs/development/plans/2026-05-30-ai-watchdog-platform.md § What 02 will enforce after P4`. Each category is either (a) covered by an existing candidate epic, (b) covered by a Step 3 Infrastructure Decisions sub-section drafted in the next step, or (c) explicitly N/A because its trigger condition is false for this vision. Produce one verdict line per category. If any category is unassigned, return to 2a and revise the epic grouping before continuing — Step 3 must NOT proceed against an incomplete epic set.

**Verdict-line shape (the agent emits 14 of these in 2h):**

```text
[Category N: <name>] — trigger: <met | not met (<why>)> →
  status: COVERED by Epic <X> | ABSORBED in Step 3 § <name> | N/A — <reason>
  cites: <rule pack file path>
```

**Per-category citation map (what 2h cites for each — these are the load-bearing rule packs / fabrik-lib paths the coverage assertion refers to; verbatim from parent plan lines 298–313):**

| # | Citation in 2h verdict line |
| --- | --- |
| 1 | scaffold sync, AI guardrails, `.windsurf/rules/` sync (via `fabrik fix`), `.env.example`, `project.yaml`, spec `shape:` block, `docs/RESILIENCE.md` |
| 2 | Vision Summary § Full Feature Inventory |
| 3 | `core/25-data-postgres.md` |
| 4 | `core/75-workers-jobs.md` + `pause-state/` |
| 5 | `core/58-resilience.md` + `async-http-client/circuit_breaker.py` + `upstream-quota/` |
| 6 | `core/self-healing.md` (shipped 2026-06-03) |
| 7 | `core/60-watchdog.md` (shipped 2026-06-02) |
| 8 | `core/55-observability.md` |
| 9 | `core/cost-budget.md` + `cost-budget/` |
| 10 | `core/30-ops.md` |
| 11 | `core/40-documentation.md` |
| 12 | `core/35-security-auth.md` + `saas/87-abuse-detection.md` + `core/app-audit-log.md` |
| 13 | `core/45-testing-strategy.md` |
| 14 | Compliance Report from 00 Step E5 (EXISTING mode only) |

**Output shape produced into the epic set:**

2h does NOT change epic boundaries directly. It produces:

1. A 14-line verdict block stored on the proposal under the heading `### Universal Coverage Check`.
2. For each "COVERED by Epic X" verdict: a note appended to that epic's compact entry of the form `Universal categories: <numbers>` (so the operator can audit at a glance which categories that epic owns).
3. For each "ABSORBED in Step 3 § X" verdict: a stub-line in the Infrastructure Decisions document referencing the matching sub-section drafted in Step 3 (cross-link, not duplicate content).
4. For each "N/A" verdict: a one-line note in the proposal under `### Universal Coverage Check` block (kept for audit trail; doesn't pollute the epic set).

---

## 3. Scaffold-type overlay integration

### 3.1 Where overlay loading happens

**Already in 02 at lines 62–68** — 02's Input Contract reads `domain-modules/<type>.md` per scaffold type identified in the Vision Summary's Technology Decisions § Scaffold types. Per saas.md lines 8–10: "Traycer reads this file from disk based on the Vision Summary's Technology Decisions § Scaffold types — no manual paste needed." **No change to loading mechanism needed.**

### 3.2 How Traycer chooses which overlay to load

The Vision Summary's Technology Decisions § Scaffold types lists one or more scaffolds (e.g., `saas-skeleton + python-api + chrome-extension`). 02 line 68 explicitly handles the multi-scaffold case: "Multi-scaffold vision (e.g., saas + mobile-app + chrome-extension) → read ALL matching modules." Loading is union-of-overlays.

**`docusaurus / static-site` caveat (r1 — verified):** the parent plan at line 322 lists `docusaurus / static-site: minimal overlay; watchdog disabled`, but `domain-modules/docusaurus.md` does NOT exist on disk. Only 5 overlay files are committed (`chrome-ext`, `mobile-app`, `rag`, `saas`, `wordpress`). 02's existing reader at lines 62–68 iterates "for EACH scaffold type identified" — a missing overlay file is a no-op (best-effort read). P4.B should treat this as the correct behavior: a docusaurus / static-site vision loads zero overlay rows and category #7 (Watchdog wiring) verdict in 2h flips to `N/A — kind ∈ {static-site, docusaurus} (sidecar disabled per 60-watchdog matrix)`. If a future P-prime ships an actual `docusaurus.md` overlay, the read loop will pick it up automatically — no 02 edit needed.

### 3.3 How overlay epics merge with universal-category epics — no duplication

**The key risk** is double-counting: the saas overlay's "§4 Tenancy + Auth + Org model — Foundation epic (Epic 1)" (saas.md line 201) could collide with the universal-category Foundation row (category #1). Same with "Billing + Gating" overlay epic vs. universal Security (#12) vs. universal Cost Guardrails (#9).

**Merge rule, to be added inside sub-step 2h after the 14 verdict lines:**

```text
After the 14 verdicts, apply the overlay-merge rule:
- For each loaded scaffold overlay, list its Mandatory Epic Coverage rows
  (e.g., saas.md § 1B Mandatory Epic Coverage).
- For each overlay row, identify the universal category it satisfies
  (e.g., "Billing + Gating" satisfies #4 Features AND #9 Cost Guardrails).
- If the universal category was COVERED by a candidate epic in 2a–2g AND
  the overlay row matches the same epic → merge: cite both in that epic's
  compact entry. No new epic.
- If the universal category was COVERED by a different epic OR ABSORBED
  in Step 3 § X AND the overlay row demands its own epic → add the
  overlay's epic to the candidate set as a new entry with Universal
  categories: <numbers>. Re-run 2c (dependency analysis) for the new
  epic before continuing.
- If the universal category was N/A but the overlay demands the
  coverage → flip the category to COVERED by the overlay's epic; update
  the 2h verdict line.
```

This makes the overlay additive to — not duplicative of — the universal-category audit.

---

## 4. Output contract updates

### 4.1 02's Output Contract (lines 280–294) — additions

Add to the "Produced as Traycer specs" block (line 282 area):

```text
6. Universal Coverage Check — 14-line verdict block + overlay-merge
   summary. Stored as part of the proposal spec.
```

And add to each per-epic compact-entry shape (lines 211–221) the 6 metadata fields 03 expects but 02 doesn't currently emit (§ 0.3 above):

```text
Epic [N]: [Name]
  Scope: [1-2 sentences]
  Features: [numbers from Feature Inventory]
  Scaffold: [type]
  Depends on: ...
  Parallel with: ...
  Port: ...
  Delivers: ...
  Rule Packs: [IDs from .windsurf/rules/]
  HAS_USER_GUIDE: [true/false]
  Shape: [flags — derived from spec shape block: kind, needs_database, needs_cache, is_public, is_admin_dashboard, has_persistent_data, has_search_feature, exposes_metrics, watchdog.enabled]
  Concurrency: [pause-state | adaptive-pool | none — derived from category 4]
  i18n: [en+tr | en-only | N/A — derived from saas overlay or kind]
  Responsive: [375px–2560px mandatory | N/A — derived from scaffold]
  Dark+Light: [mandatory | N/A — derived from scaffold]
  Registrars: [which of the 9 fire — derived from shape block]
  Universal categories: [comma-separated numbers from 1–14 this epic owns]
```

### 4.2 02's Acceptance Criteria (lines 304–325) — additions

Add after line 318 ("Compact proposal format — NOT full epic files (those come in 03)."):

```text
- Universal Coverage Check sub-step (2h) produced a verdict for every
  one of the 14 categories. No category left unaudited.
- Every "COVERED by Epic X" verdict matches an epic actually present
  in the compact proposal.
- Every "ABSORBED in Step 3 § X" verdict matches a sub-section actually
  drafted in Step 3.
- Every "N/A" verdict carries an explicit trigger-not-met reason cited
  from the spec shape block or Vision Summary.
- Overlay-merge rule applied: no overlay-mandated epic is duplicated
  by a universal-category epic.
- Each per-epic compact entry carries the 6 new metadata fields (Shape,
  Concurrency, i18n, Responsive, Dark+Light, Registrars) plus
  "Universal categories" — total 16 fields.
```

---

## 5. "Does NOT" updates

**Add to 02's Does NOT block (lines 296–302):**

```text
- Does NOT design watchdog sidecar configuration — watchdog wiring is
  category #7 with default-by-kind enabled flag; the registrar runs at
  `fabrik apply` and reads spec.watchdog.* (per core/60-watchdog.md).
  This command only asserts coverage in the audit and routes the epic
  that owns the spec to the watchdog Step 3 sub-section.

- Does NOT design self-healing ladder — category #6 is satisfied by
  citing core/self-healing.md in the Self-Healing Ladder Step 3
  sub-section. Per-project ladder rows are written in the epic's
  docs/RESILIENCE.md per 58-resilience § Per-Project Contract.

- Does NOT design cost-budget caps — category #9 cites
  core/cost-budget.md; per-epic caps are set in the watchdog config
  block of the spec (deferred to epic-to-ticket-workflow tickets).
```

No existing Does NOT row is removed — all 5 stay (lines 297–302). Three rows added.

---

## 6. Line-count estimate per edit

| Edit | Insert | Remove | Net |
| --- | --- | --- | --- |
| Sub-step 2h heading + purpose paragraph + verdict shape + citation map + output-shape rules | ~50 | 0 | +50 |
| 4 new Step 3 sub-sections (Self-Healing Ladder, Watchdog Wiring, Observability Defaults, Cost Guardrails) — each ~10 lines (heading + 5–7 prose lines + cite) | ~40 | 0 | +40 |
| 2 minor inserts (External Services resilience pointer; Auth Strategy audit-log pointer) | ~6 | 0 | +6 |
| Compact-entry shape expansion (6 new fields + Universal categories) | ~10 | 0 | +10 |
| Output Contract item #6 (Universal Coverage Check) | ~3 | 0 | +3 |
| Acceptance Criteria — 6 new rows | ~7 | 0 | +7 |
| Does NOT — 3 new rows | ~12 | 0 | +12 |
| Overlay-merge rule block inside 2h | ~15 | 0 | +15 |
| **Total** | **~143** | **0** | **~143** |

**Parent-plan target was 150–200 lines** (line 274). Estimate lands at ~143 insertions — comfortably inside the budget. No removals: the existing 02 structure is preserved and additive-only.

---

## 7. Backward compatibility with 03

### 7.1 Does 03 still consume 02's output unchanged after P4?

**Quoted from 03 § Input Contract (lines 35–41):** 03 expects Compact Epic Proposal + Infrastructure Decisions spec + Dependency Graph, all owner-confirmed, all fetched via `read_spec`.

**After P4, 02 still produces all three.** The Universal Coverage Check is appended to the Compact Epic Proposal (item #6 in the extended Output Contract); the 4 new Step 3 sub-sections live inside the Infrastructure Decisions document; the Dependency Graph is unchanged.

### 7.2 Does 03's ticket Metadata block need updates?

**Quoted from 03 § Step 2 Ticket Description Metadata (lines 99–110):**

```text
### Metadata
- Scaffold: [type]
- Port: [value]
- Shape: [registrar flags]
- Concurrency: [mechanism]
- i18n: [mechanism or N/A]
- Responsive: [375px–2560px mandatory / N/A — non-GUI scaffold]
- Dark+Light: [mandatory / N/A — non-GUI scaffold]
- Rule Packs: [IDs]
- HAS_USER_GUIDE: [true/false]
- Registrars: [which of the 9 fire for this epic's deploy unit(s)]
```

03 already EXPECTS these 10 metadata fields. 02 currently emits 5 of them (Scaffold, Port, Rule Packs, HAS_USER_GUIDE, plus the existing Depends-on/Parallel-with/Delivers prose). **The 6 missing fields P4 adds to 02 are exactly the 6 fields 03 already expects but currently has to invent.** P4 makes 02 the source of truth for those metadata fields — a NET IMPROVEMENT to the contract; no changes to 03.

### 7.3 03 Metadata gets one new line — "Universal categories"

**Owner decision r1:** option (B) — "obey metadata and plan". P4.B WILL edit `03-expand-epic-files-command.md` to carry the new field verbatim into the ticket Metadata block.

**The edit to 03:** insert one line into the Metadata block (currently 03 lines 99–110):

```text
### Metadata
- Scaffold: [type]
- Port: [value]
- Shape: [registrar flags]
- Concurrency: [mechanism]
- i18n: [mechanism or N/A]
- Responsive: [375px–2560px mandatory / N/A — non-GUI scaffold]
- Dark+Light: [mandatory / N/A — non-GUI scaffold]
- Rule Packs: [IDs]
- HAS_USER_GUIDE: [true/false]
- Registrars: [which of the 9 fire for this epic's deploy unit(s)]
- Universal categories: [comma-separated numbers from 1–14 this epic owns]   ← NEW
```

That makes 11 metadata fields in 03's ticket Description, matching exactly the 6 new + 5 existing fields P4 emits in 02's compact entry plus the universal-categories assignment. Traceability preserved end-to-end: operator can audit at the ticket level which of the 14 universal categories a given epic ticket inherits responsibility for.

**Net P4 edits to 03:** 1 line added to Metadata block. No other changes. 03's `read_spec` flow, ticket creation, expansion rules, and Step 3/4 routing are unchanged.

---

## 8. Acceptance criteria for P4 (lifted from parent plan)

From parent plan § Phased implementation (line 287):

> **P4 — 02 integration.** Universal-coverage overlay integrated into `02-epic-decomposition-command.md`. P1 + P2 + P3 must exist before 02 cites them. **2 days.** Acceptance: Traycer cold-read of updated 02 on test Vision Summary produces epic set covering all 14 universal categories + saas-skeleton overlay; existing Step 1–4 + Infrastructure Decisions structure preserved.

Restated for P4.B code prompts:

- **A1.** Traycer cold-read of updated 02 on a test Vision Summary (saas-skeleton + python-api scaffolds) produces an epic set in which every one of the 14 universal categories has exactly one of {COVERED by Epic X, ABSORBED in Step 3 § Y, N/A — reason}.
- **A2.** Loaded `domain-modules/saas.md` overlay rows (saas.md § 1B Mandatory Epic Coverage, lines 195–207) all merge cleanly with the universal-category verdicts — no overlay-mandated epic is duplicated; no overlay-mandated epic is dropped.
- **A3.** Existing 02 structure preserved: Step 1, Step 2 (2a–2g unchanged + new 2h), Step 3 (10 existing sub-sections unchanged + 4 new sub-sections + 2 minor pointer inserts), Checkpoint, Step 4 all in place at the same line ranges modulo the additions.
- **A4.** Each per-epic compact entry carries 16 fields (10 existing + 6 new) plus the "Universal categories" assignment.
- **A5.** Output Contract grew by 1 item (#6 Universal Coverage Check); Acceptance Criteria grew by 6 rows; Does NOT grew by 3 rows.
- **A6.** Total inserted lines ≤ 200 (parent-plan budget); estimated ~143 per § 6 above.
- **A7.** Exactly 1 line added to `03-expand-epic-files-command.md` Metadata block (`- Universal categories: [list]`); no other 03 edits. Verified by re-walking 03's Input Contract + ticket Description after the edit set.
- **A8.** All cited rule packs / fabrik-lib paths in 2h's citation map exist on disk (verified by `ls` before P4.B code-prompt runs):
  - `core/self-healing.md` ✓ shipped 2026-06-03 (commit `a153414`)
  - `core/60-watchdog.md` ✓ shipped 2026-06-02 (commit `1fbb326`)
  - `core/cost-budget.md` ✓ pre-existing
  - `core/app-audit-log.md` ✓ pre-existing
  - All other cited packs (`25-data-postgres`, `35-security-auth`, `40-documentation`, `45-testing-strategy`, `55-observability`, `58-resilience`, `75-workers-jobs`, `30-ops`) ✓ pre-existing.

---

## 9. Side findings (META-RULE 4 — flag, do NOT fix)

During the verification reads I noticed these issues. Each is FLAGGED for owner triage; none is fixed in this sub-plan. None blocks P4.B.

1. **03's ticket Metadata expects 6 fields 02 doesn't currently emit.** 03 lines 99–110 list Shape, Concurrency, i18n, Responsive, Dark+Light, Registrars. 02 doesn't currently produce them; 03 currently has to invent or omit. P4 incidentally fixes this by adding the 6 fields to 02's compact entry (§ 4.1). Flagging because this is a pre-existing 02↔03 contract gap independent of the universal-coverage work.

2. **`docs/operations/fabrik-lifecycle.md` cited at 02 line 58.** I did NOT read this file during the P4.A verification step because it's not in the P4.A read list. If 02's edits in P4.B introduce a new lifecycle stage reference (likely not — P4 is about epic-coverage audit, not lifecycle), the file should be re-read before P4.B ship.

3. **02's domain-modules read list (lines 62–68)** names `saas-skeleton`, `mobile-app`, `wordpress`, `chrome-extension`, and conditionally `rag.md` — but does NOT name `docusaurus / static-site` (one of the 6 overlays per parent plan line 322). **RESOLVED (r1 — verified 2026-06-03):** `domain-modules/docusaurus.md` does NOT exist on disk; only 5 overlays present. Treated as no-op in § 3.2 — best-effort read, watchdog category flips to N/A for static-site visions. Parent-plan line 322 is informational, not a load instruction. No P4-driven changes needed to 02's read list. If a docusaurus overlay file lands later, the existing iterator picks it up automatically.

4. **saas.md § Part 2 (lines 236+)** is "Reserved for future per-epic loading by `epic-to-ticket-workflow` command files" — not currently wired. P4 is about 02 only, so Part 2 is out of scope. Flagging because a future P-prime might wire Part 2 into the epic-to-ticket-workflow; P4 should be careful not to imply Part 2 is consumed by 02.

5. **Existing Step 2 has 7 sub-steps (2a–2g)** — adding 2h makes 8. The proposed sub-step letter is `h`, not `e2` or similar. Owner may prefer a different naming convention (e.g., promote to its own Step 2.5 or numbered sub-step). **RESOLVED (r1):** owner confirmed `2h` — keep throughout. No change.

6. **The "Existing mode addition" sub-section inside 2b (lines 104–122)** emits Retrofit epics. Category #14 (Retrofit) is satisfied by this existing flow. P4 does NOT add a new mechanism — it just adds a verdict line in 2h confirming Retrofit emission ran for EXISTING mode. Verified compatible; flagging for transparency.

7. **The `core/self-healing.md` shipped in commit `17e8757` then corrected in `a153414`** to drop unvetted citations and meet MD060 lint clean. P4.B's citation to `core/self-healing.md` references the corrected version. If the operator reverts `a153414` for any reason, P4.B's citation map (§ 2) needs a re-audit.

---

## 10. STAGED edits to 02 (NOT applied this turn)

For operator review only. P4.B will perform these surgical edits after sub-plan approval.

| Edit # | Target lines in current 02 | What | Estimated insert/delete |
| --- | --- | --- | --- |
| E1 | Insert after line 156 (end of 2g) | New sub-step 2h heading + body (per § 2 above) | +50 / 0 |
| E2 | Insert at line ~170 area (inside Step 3 § Database Strategy block, top — minor pointer only) | NO CHANGE; pre-existing § Database Strategy already covers category 3. Drop this edit. | 0 / 0 |
| E3 | Insert at line ~192 area (inside Step 3 § External Services block) | One-line resilience-row pointer per category 5 | +2 / 0 |
| E4 | Insert at line ~177 area (inside Step 3 § Auth Strategy block) | One-line audit-log pointer per category 12 | +2 / 0 |
| E5 | Insert after line 188 (after § Embedding Model block, before § Backing Services) | New § Self-Healing Ladder sub-section per category 6 | +10 / 0 |
| E6 | Insert after E5 | New § Watchdog Wiring sub-section per category 7 | +10 / 0 |
| E7 | Insert after E6 | New § Observability Defaults sub-section per category 8 | +10 / 0 |
| E8 | Insert after E7 | New § Cost Guardrails sub-section per category 9 | +10 / 0 |
| E9 | Replace lines 211–221 (compact entry shape) | Add 6 new metadata fields + Universal categories line | +6 / 0 |
| E10 | Insert at line 288 area (Output Contract item list) | New item #6 Universal Coverage Check | +3 / 0 |
| E11 | Insert at line 302 area (end of Does NOT block) | 3 new rows per § 5 above | +12 / 0 |
| E12 | Insert at line 318 area (end of Acceptance Criteria) | 6 new rows per § 4.2 above | +7 / 0 |
| E13 | Insert overlay-merge block inside 2h (after the 14 verdicts) | Per § 3.3 above | +15 / 0 |
| E14 | `03-expand-epic-files-command.md` Metadata block (around line 109, after `Registrars:`) | Add one line: `- Universal categories: [list]` per § 7.3 above | +1 / 0 |

Net: ~137 insertions + 0 deletions. (Minor ~6-line slippage vs. § 6 estimate of 143 is within margin; final P4.B will reconcile.)

---

## 11. Open questions for owner before P4.B starts

**All 4 resolved 2026-06-03 (r1).** History retained for traceability:

1. **Sub-step naming (Side finding #5).** "2h" or promote to "Step 2.5 — Universal Coverage Check"? → **Answer: `2h`.**
2. **`docusaurus / static-site` overlay disposition (Side finding #3).** Does the overlay file exist? Should 02 line 67 grow a row, or should the parent plan drop the row? → **Answer: file does NOT exist; treat as no-op best-effort read; parent-plan line is informational. No 02 read-list edit needed.**
3. **03's Metadata field expansion (§ 7.3).** Ship option (A) — 03 unchanged — or option (B) — add `Universal categories` to 03's ticket Metadata? → **Answer: option (B). P4.B adds 1 line to 03 (E14 in the staged-edits table).**
4. **Any of the 7 staged side findings worth promoting to in-scope for P4.B**, or all deferred? → **Answer: side findings enumerated; 3 already in-scope (1, 5, 6), 1 inline-fixed (3), 2 deferred (2, 4), 1 sentinel (7). No additional promotions.**

**Ready for P4.B code prompts when owner says go.**

---

## 12. Self-review against P4.A acceptance

| P4.A spec requirement | This sub-plan addresses | Where |
| --- | --- | --- |
| 1. For each of 14 universal categories: where in 02 does it land? | ✓ | § 1 (table; 14 rows) |
| 2. New "Universal Coverage Check" sub-step (insert line range, purpose, citations, output shape) | ✓ | § 2 (insert after line 156; 14-citation map; verdict shape; 4-item output shape) |
| 3. Scaffold-type overlay integration (where loaded, how chosen, no-duplication merge) | ✓ | § 3 (already loaded at lines 62–68; multi-scaffold union; overlay-merge rule) |
| 4. Output contract updates (new fields, new acceptance rows) | ✓ | § 4.1 (6 new compact-entry fields + Universal categories) and § 4.2 (6 new acceptance rows) |
| 5. "Does NOT" updates (P1/P2-covered items move in) | ✓ | § 5 (3 new rows — watchdog config, self-healing design, cost-budget caps) |
| 6. Line-count estimate (target 150–200) | ✓ | § 6 (~143 insertions, 0 deletions — within budget) |
| 7. Backward compatibility with 03 | ✓ | § 7 (quoted 03 Input Contract; recommended option A; no changes to 03 required) |
| 8. Acceptance criteria for P4 (lifted from plan v2) | ✓ | § 8 (8 criteria A1–A8) |
| 9. Side findings | ✓ | § 9 (7 flagged; none fixed) |

**Self-review verdict:** sub-plan complete. All 9 P4.A required sections present. Verification step (§ 0) names all 5 source files with line counts; cites 02 structure with exact line numbers; quotes 03's Input Contract; quotes 03's Metadata expectations; confirms overlay-loading mechanism already wired. No edits to 02 performed in this turn — META-RULE 3 (sub-plan first, code second) and META-RULE 5 (sub-plan only when asked) honored.

**Awaiting owner approval before P4.B code prompts begin.**
