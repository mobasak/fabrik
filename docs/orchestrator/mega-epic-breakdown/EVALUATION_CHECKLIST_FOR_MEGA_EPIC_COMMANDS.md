<!-- ⚠️ ORCHESTRATOR `-fabrik` COMMAND-CHAIN QA
     This checklist evaluates the mega-epic-breakdown `-fabrik` commands in
     `docs/orchestrator/mega-epic-breakdown/` — the DOER chain the driver/cockpit runs:
       00-trigger-fabrik · 02-epic-decomposition-fabrik ·
       03-expand-epic-files-fabrik · 04-cross-epic-validation-fabrik.
     `05-dispatch` is RETIRED (see `_retired/05-dispatch-epic-tickets-fabrik.RETIRED.md`);
     its ticket-set integrity gate + phased-order emission are now the deterministic
     `scripts/epic_order.py`, absorbed into 04. Dispatch is the cockpit epic-card click /
     the driver's phase queue — not a command.
     Stress-test every command against every applicable item.
     "N/A for this command" is valid; forgetting to check is not.
     -->

# Mega-Epic Command Evaluation Checklist

Every command in mega-epic-breakdown (00, 02, 03, 04 — `05` retired) must be evaluated against this list before it's considered complete. This checklist is for DECOMPOSITION quality — splitting a large vision into independent epics. For TICKET quality, see `epic-to-ticket-workflow/EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md`.

---

## Vision Completeness

1. Does it consume ALL of the owner's research files? (dropped in `docs/development/plans/` or `docs/preplans/`)
2. Does it treat the research as THE starting point — not interview from zero?
3. Does it surface what the research MISSED (gaps, conflicts, impossible constraints)?
4. Does it capture the FULL scope of the vision — no features silently dropped?
5. Does it identify explicit OUT OF SCOPE boundaries at the vision level?
6. Does it identify all PERSONAS (who uses this product)?
7. Does it identify all REVENUE/VALUE streams (why does this product exist)?

## Epic Boundary Quality

8. Can each epic be developed and deployed INDEPENDENTLY? (not "half a feature")
9. Does each epic have a clear DEPLOY MILESTONE? (something works end-to-end after this epic)
10. Does each epic produce a TESTABLE ARTIFACT? (user can click/call something new)
11. Are epic boundaries drawn along DOMAIN lines (not layer lines)? Domain = "user management" not "database layer"
12. Does NO epic share mutable state with a parallel epic? (shared DB schema = sequential dependency, not parallel)
13. Could a different AGENT team work each epic without coordinating mid-epic? (independence test)
14. Is each epic SELF-CONTAINED enough to go through epic-to-ticket-workflow/00-11 independently?

## Dependency Graph Quality

15. Are dependencies between epics EXPLICIT? (Epic 2 depends on Epic 1's DB schema — stated, not implied)
16. Is the dependency graph MINIMAL? (no unnecessary sequential chains — if epics CAN be parallel, they MUST be)
17. Are there no CIRCULAR dependencies? (A→B→C→A = broken graph)
18. Is the CRITICAL PATH identified? (longest sequential chain from first to last epic)
19. Can any epic on the critical path be SPLIT to shorten it?
20. Are parallel lanes identified? (which epics can run simultaneously after their dependencies complete)

## Infrastructure Decision Completeness

21. Are ALL shared infrastructure decisions made ONCE, not deferred to each epic?
22. Database: which databases, which schemas are shared vs epic-owned?
23. Auth: which auth mechanism (`fabrik-lib/fastapi-user-auth` Pattern A [default], Authelia forward-auth, custom — Supabase Auth is legacy/migration-only)?
24. Deploy target: VPS via `fabrik apply` (SSH + Docker Compose) confirmed? (not Vercel/Railway/K8s)
25. Backing services: which existing VPS services will be used (postgres-main, redis-main, MeiliSearch, etc.)?
26. External services: which third-party APIs/services (Backblaze B2, Paddle, Cloudflare, etc.)?
27. Domain/routing: which subdomains, which Traefik routing rules?
28. Scaffold type per epic: which of the 11 mega-epic-breakdown scaffold types applies (`python-api`, `python-api-gpu`, `node-api`, `saas-skeleton`, `file-api`, `file-worker`, `static-site`, `docusaurus`, `chrome-extension`, `mobile-app`, `desktop-app` per `00-trigger-fabrik` § Shape model — WordPress is out-of-scope, delegated to standalone `/opt/wpf`)?
29. Shape block per epic: what registrars will each epic's `fabrik apply` activate?

## Handoff to epic-to-ticket-workflow

30. Does each epic output file contain enough context for epic-to-ticket-workflow/01-epic-brief to START? (scope, success criteria, constraints, metadata)
31. Does each epic output file reference the shared infrastructure decisions? (not duplicate them)
32. Does each epic output file state what PRIOR EPICS produced that this epic consumes? (DB tables, API contracts, env vars)
33. Does each epic output file state what THIS EPIC produces that later epics need? (contracts, not implementation details)
34. Can Traycer run epic-to-ticket-workflow/01-epic-brief with ONLY the epic output file + the infrastructure decisions file? (no need to re-read the full vision research)

## Context Window Respect

35. Is the vision summary within its **mode-specific** budget? (NEW ≤5,000 / ≤8,000 hard; EXISTING ≤6,000 / ≤10,000 hard — see item 75. Both fit alongside the epic brief in a 200K context; the EXISTING allowance covers Locked Decisions + Compliance Report.)
36. Is each epic output file ≤10,000 tokens? (must fit alongside tech plan, deploy plan in later steps)
37. Is the infrastructure decisions file ≤5,000 tokens? (loaded alongside every epic brief)
38. Are details that belong in tech-plan/deploy-plan DEFERRED to those steps? (decomposition decides WHAT, not HOW)
39. Does it avoid re-stating the full vision research in every epic file? (reference it, don't copy it)

## Scope Protection

40. Does each epic have explicit OUT OF SCOPE? (what this epic does NOT do — even if it's in the vision)
41. Are the boundaries between adjacent epics CLEAR? (if Epic 2 builds "user management" and Epic 3 builds "admin dashboard", where does "admin user management" go?)
42. Are AMBIGUOUS boundaries surfaced as decisions for the owner? (not silently assigned)
43. Does it prevent scope creep between epics? (Epic 2 can't grow to absorb Epic 3's work)

## The 4-Stage Lifecycle

44. Does it reference `docs/operations/fabrik-lifecycle.md`?
45. Does each epic cover all 4 stages? (Intent → Implementation → Registration → Verification)
46. Or is it explicitly stated that some epics only cover certain stages? (e.g., "Epic 1 is foundation-only — no user-facing features, no Stage 4 health checks")
47. Are the 10 registrars (7 flag-driven + grafana always-on + glitchtip kind-driven + watchdog opt-out) considered per epic? (which registrars fire for each epic's `fabrik apply`)

## Solo Dev Reality

48. Can one human + AI agents execute one epic at a time? (don't assume parallel human attention across epics)
49. Are epics ordered to deliver VALUE EARLY? (not foundation-foundation-foundation-finally-something-works)
50. Does Epic 1 produce something the owner can SEE and USE? (motivation matters for solo devs)
51. Is the total epic count REASONABLE? (3-7 epics typical. 10+ = re-examine. 2 = probably not mega enough to need this workflow)

## Fabrik Infrastructure Awareness

52. Does it check for EXISTING projects on VPS that overlap? (`AGENTS.md` microservices table + `docs/BUSINESS_MODEL.md`)
53. Does it check for PORT conflicts? (`PORTS.md`)
54. Does it check for DUPLICATE functionality? (don't build what exists)
55. Does it use existing VPS services BEFORE building new? (postgres-main, redis-main, etc.)
56. Does it respect the tech-stack defaults — `AGENTS.md` § Tech Stack Defaults + `docs/reference/technology-stack-decision-guide.md`? (There is no section named "external services decision matrix" — do not look for one.)

## Owner's Research-First Approach

57. The research file is the STARTING POINT — not a reference to skim.
58. The workflow IMPROVES the research — identifies what's missing, what conflicts, what's impossible.
59. If no research file exists, the workflow interviews — but the preference is research-first.
60. Research from Gemini/ChatGPT/Claude is treated as EXPERT INPUT, not hallucination to verify.

## Output Quality

61. Every statement is FACTUAL — reflects what actually exists in the codebase/VPS.
62. Every instruction is ACTIONABLE — "Consider X" is banned, "Check X and state finding" is correct.
63. No DUPLICATION between commands — each command consumes upstream output, never restates.
64. No BULLSHIT lines — if a sentence doesn't change behavior or inform a decision, delete it.
65. No MISLEADING references — if content X lives in file Y, verify it actually does.
66. LEAN but COMPREHENSIVE — nothing important omitted, nothing unimportant included.

## Command File Structure (every command MUST have)

67. **Role** — one sentence defining who the AI is in this step.
68. **Core Philosophy** — 3-5 bullet rules for this step (not copy-paste from other commands).
69. **Processing Steps** — numbered, ordered, each with a clear verb (READ, IDENTIFY, PRODUCE, VALIDATE).
70. **Input Contract** — what prior command outputs are REQUIRED. Hard stop if missing.
71. **Output Contract** — exact format of what this command produces. Section headings, required fields, token budget.
72. **Acceptance Criteria** — checklist that must ALL pass before command output is considered done.
73. **Does NOT** — explicit list of what this command leaves for the NEXT command (prevents overlap).
74. **Consumes upstream, never restates** — if prior command decided X, this command references X, doesn't re-derive it.

## Output Format Contracts

75. **Vision Summary** (00 output): **NEW mode ≤5,000 target / ≤8,000 hard cap; EXISTING mode ≤6,000 / ≤10,000** (per `00-trigger-fabrik` § **Output Contract & Acceptance Criteria** — EXISTING legitimately adds `## Locked Decisions` + `## Compliance Report`, so a flat 5,000 would force harmful truncation of the compliance gaps the owner must decide on). Sections: Product Vision, Personas, Value Streams, Full Feature Inventory, Backing Services, External Services, Technology Decisions, Constraints, Out of Scope, Open Questions, Scale Assessment.
76. **Infrastructure Decisions** (02 output): ≤5,000 tokens. Sections per `02-epic-decomposition-fabrik` Step 3 template (14 sections): Database Strategy, Auth Strategy, Email Strategy, Background Processing, Embedding Model (if RAG), Self-Healing Ladder (if `shape.kind ∈ {service, worker}`), Watchdog Wiring (**ON by default — opt-OUT**, `infrastructure.py:314`; ⚠️ **no** `kind` test in the resolver — `core/60-watchdog.md`'s matrix is operator discipline, NOT code-enforced), Observability Defaults, Cost Guardrails (if any paid-API use), Backing Services, External Services, Domain Structure, Shared Environment Variables, Shared Shape Decisions.
77. **Compact Epic Proposal** (02 output): per `02-epic-decomposition-fabrik` § Acceptance Criteria, **23 indented fields** per epic in **five** groups — 9 epic-shape + 6 inheritance-metadata + 1 Universal categories + 3 conditional + **4 cross-epic-contract (Target host, Consumes, Produces, `Owned paths`)**. 03's Metadata consumes 15; **Consumes / Produces / Owned paths** feed 03 § Dependencies. ⚠️ `Owned paths` is the **concurrency contract** — the file globs an epic WRITES. It is what 02's parallel gate (2/3 file-scope disjointness, 3/3 single-migration-owner) intersects and what 04 Step 4 re-validates; without it a `Parallel with:` claim is unverifiable. It stays OUT of the 15-field Metadata block deliberately — it belongs in `### Dependencies`, beside the `Parallel with:` claim it justifies.
78. **Epic Tickets** (03 output, one Traycer ticket per epic): per `03-expand-epic-files-fabrik` template. Sections: Summary, Scope (In/Out), Success Criteria (5-8 for delta-feature OR 3-5 for Retrofit), Out of Scope, Dependencies (Consumes/Produces/Depends on/Parallel with/**Owned paths** — all five sub-bullets present; Owned paths is the concurrency contract that makes a `Parallel with:` claim checkable), Metadata (15 fields: Scaffold, Port, target_vps, Shape, Concurrency, i18n, Responsive, Dark+Light, Rule Packs, HAS_USER_GUIDE, Registrars, Universal categories, Abuse Detection, Email, FINANCIALS), Infrastructure, Execution Order, Entry Point.
79. **Dependency Graph** (02 output): Mermaid diagram with `subgraph "Phase N"` blocks + execution order + parallel lanes identified. Terminology is **Phase**, not **Batch** — consistent across 02 + 04 and `scripts/epic_order.py`'s `--json` phase output (see anti-pattern 101 below). ⚠️ The graph is now the *human-readable* twin of the machine truth: 03 emits `depends_on`/`parallel_with` in each ticket's typed frontmatter (item 84a), and `epic_order.py` derives the authoritative phased order from THOSE, not from this mermaid. The mermaid must not contradict the frontmatter (a mismatch is a defect 04 flags).
80. **Validation Report** (**04 output** — 05 retired): Feature Coverage, Epic Tickets (per-epic PASS/FAIL), Dependency Graph, Infrastructure Decisions (14-section check), Handoff Readiness (15-field Metadata check), **Ticket-set integrity** (the `scripts/epic_order.py --check --expected-count` gate absorbed from retired 05 — count-match, epic-number contiguity, duplicate/orphan detection, parallel-set disjointness + single-migration-owner proof), Overall result, and the **code-generated phased Execution Order** (`scripts/epic_order.py --json`, NOT hand-written). There is no downstream dispatch command: the report's execution order feeds the cockpit (epic-card click) / driver (phase queue) directly.

## Handoff Format (epic file → epic-to-ticket-workflow/01-epic-brief)

81. Each epic ticket (Traycer-stored, not on-disk file) MUST contain a `### Metadata` section with all **15 fields**: Scaffold, Port, target_vps, Shape, Concurrency, i18n, Responsive, Dark+Light, Rule Packs, HAS_USER_GUIDE, Registrars, Universal categories, Abuse Detection, Email, FINANCIALS (last 3 conditional — `N/A` allowed). Match per `03-expand-epic-files-fabrik` Metadata template + `04-cross-epic-validation-fabrik` Step 6 Handoff Readiness check + `epic-to-ticket-workflow/00-trigger-fabrik` § Entry Points → Multi-epic (consume mode) consume-mode field list (the upstream `mega-epic-breakdown/03` enforces; the downstream `epic-to-ticket-workflow/01` Path B consumes).
82. Each epic output file MUST contain a `## Success Criteria` section with numbered, testable criteria — matching what epic-to-ticket-workflow/01-epic-brief uses to validate coverage.
83. Each epic output file MUST contain a `## Dependencies` section stating: what prior epics produced (DB tables, API contracts, env vars) that this epic assumes exist.
84. Each epic output file MUST be SELF-SUFFICIENT — Traycer running epic-to-ticket-workflow/01 reads ONLY this file + infrastructure-decisions.md. No need to load the full vision research.

## Persistence, Typed Frontmatter & Traycer-Readiness (added 2026-07-18 — the disk-of-record + code-driven-ordering rework)

This section encodes the north-star decisions D6 (persist on confirm), D7 (epic cards in the GUI immediately), D8 (disk = source of truth), D10 (ONE typed data model), and R8/D4 (control flow in code, not prose). Every command in the chain must satisfy its applicable items.

84a. **Typed frontmatter on every epic ticket** (03 output): each `docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md` MUST open with the flat frontmatter block from `EPIC-ARTIFACT-SCHEMA.md` — `kind` / `title` / `status` / `epic_n` / `depends_on` / `parallel_with` / `owned_paths`. It is the ONE data model (D10) serving all three consumers: `scripts/epic_order.py` reads `epic_n`/`depends_on`/`parallel_with`/`owned_paths`; `scripts/traycer_mirror.py` reads `kind`/`title`/`status`; validation (04) reads all of it. `depends_on`/`parallel_with`/`owned_paths` are the **machine form** of the ticket's `### Dependencies` prose — they MUST be identical (a mismatch is a defect 04 flags).
84b. **Persist on confirm — nothing load-bearing stays chat-only** (D6). 00 persists the Vision Summary to `docs/superpowers/specs/YYYY-MM-DD-<project>-vision.md` the moment the owner confirms; 02 persists the Compact Proposal + Dependency Graph to `docs/superpowers/specs/YYYY-MM-DD-<project>-epic-proposal.md` on confirm; 03 persists the Infrastructure Decisions spec + one ticket file per epic. A command that leaves its load-bearing output in the conversation only is a **failed run** — a cold re-entry loses it. (The old "persisted automatically" claim was false and is removed.)
84c. **Two persistence trees, never crossed.** Epic **ticket files** live under `docs/development/epics/` (allowlist regex `epic-<n>-<slug>`, owned by 03). Everything else this chain persists — Vision Summary, Epic Proposal, Infrastructure Decisions — lives under `docs/superpowers/specs/**` (free-naming allowlist). A spec MUST NOT be written under `docs/development/epics/`: `epic_order.py` globs that whole directory and treats every hit as a ticket (counts it, demands contiguous `1..N`, flags the excess as an orphan). 02 writes NO ticket file; 04 writes NO epic content at all.
84d. **Traycer mirror is a dual-write, NO-OP headless** (D7/D8). 00/02/03 call `python /opt/fabrik/scripts/traycer_mirror.py --src <disk file> …` after persisting, mirroring the artifact into `~/.traycer/epics/$TRAYCER_EPIC_ID/artifacts/<name>/index.md` so the cockpit renders it as a card. DISK stays source-of-truth (D8) — the mirror is a copy, never the store of record. The script writes ONLY when `$TRAYCER_EPIC_ID` is set, so the identical command is a NO-OP in a headless driver run and works unchanged in any `/opt` project.
84e. **Ordering & integrity are code, not prose** (R8/D4). No command may hand-derive the phased execution order or the ticket-set integrity result. Both come from `scripts/epic_order.py`: `--check --expected-count <N>` (integrity gate, 04 Step 1.5, absorbed from retired 05) and `--json` (topological phased order, 04 Step 4). The script is stdlib-only and project-agnostic; its parallel-disjointness / single-migration-owner proof reads `owned_paths` from the frontmatter (84a).
84f. **05 is retired, not merely unused.** No command may reference a live `05-dispatch` step, emit "dispatch instructions", or defer ticket-set integrity / execution-order to it. Its two jobs are now `epic_order.py` (absorbed into 04); its file lives in `_retired/` as a tombstone. Dispatch is the cockpit epic-card click / the driver's phase queue.

## Iterative Convergence

85. Does it wait for EXPLICIT user confirmation? (silence ≠ confirmation)
86. Does it suggest revisions when scope changes instead of silently absorbing?
87. Does it iterate with the owner until the decomposition is RIGHT? (planning is SLOW, execution is FAST)
88. Does it present the dependency graph VISUALLY (mermaid diagram)?

## Anti-Patterns (if any of these are true, the command file is WRONG)

89. Command says "Consider..." instead of "Check X and state finding." → REWRITE.
90. Command produces output that requires the NEXT command to ask the user what's missing. → ADD to this command.
91. Command restates what a prior command already produced. → DELETE and reference.
92. Two commands produce overlapping output. → MERGE or split boundary clearly.
93. Command's **document-style output** (free-form prose where the agent decides length, e.g., Vision Summary / Infrastructure Decisions / Compact Epic Proposal) doesn't have a clear token budget. → ADD budget. **Structure-bounded outputs** (Traycer tickets with a fixed section template, Validation Reports with PASS/FAIL row-per-check, dispatch instructions with fixed steps) do NOT need a numeric cap — the template structure bounds them and a numeric cap would force harmful truncation. The test: if length is bounded by "how thorough should I be?", needs a budget; if length is bounded by "fill this template once", doesn't.
94. Command doesn't have Acceptance Criteria. → ADD.
95. Epic output file requires loading the full vision research alongside it. → CONDENSE epic file to be self-sufficient.
96. Command uses vague scope ("relevant files", "update as needed", "consider implications"). → REWRITE with concrete paths and actions.

## Regression-Coverage Anti-Patterns (added 2026-06-18 from session-fixed defect classes)

97. **Feature-vs-scaffold drift in GUI mandates** — command applies i18n / Responsive / Dark+Light requirements based on scaffold TYPE (e.g. `saas-skeleton ⇒ mandatory`, `python-api ⇒ N/A`) instead of the GUI surface itself. A python-api with `shape.is_admin_dashboard: true` HAS a GUI and must carry the mandates. → REWRITE the trigger to be feature-based per `00-trigger-fabrik` § Rule-area applicability matrix (the c2ef2ee fix class). This defect was previously hit in 00 (`c2ef2ee`), 03 (`71dad46`), 04 (`5485644`), and ettw/05 (`ff2c427`).
98. **Dangling citation to archived/missing file** — command cites a path under `docs/development/plans/` or `docs/reference/` that has been archived to `docs/development/plans/archived/` OR no longer exists. → VERIFY every cited path with `ls`/`Read` before merge; if archived, either inline the relevant content into the command or cite the archived path explicitly with `(archived; historical context only)`. This was the `02:f576b36` defect class (dangling `2026-05-30-ai-watchdog-platform.md`).
99. **Retrofit-epic special-case missing** — command treats every epic as a delta-feature epic and forces the same Success Criteria count (5-8), the same Title format (no `Retrofit:` prefix), the same Epic Closure mandatory rule, or the same deploy-level criterion. Retrofit epics emitted by `02-epic-decomposition-fabrik` Step 2b are 3-5 Success Criteria, `Retrofit:` prefix in Title, optional Epic Closure, and may have `final_gate.py` instead of `fabrik apply` as the deploy-level criterion. → ADD explicit Retrofit branch per `03-expand-epic-files-fabrik` § Step 2 (flavours + `Retrofit:` Title prefix). This was the `03:71dad46` defect class.
100. **Presence-only validation when the contract is semantic** — command's validation check says "Field X | Present or N/A stated | Missing" but doesn't validate that the N/A reason matches the underlying trigger condition. A field declared `N/A — non-GUI scaffold` on an epic with `shape.is_admin_dashboard: true` would PASS a presence-only check despite being a rule-pack violation. → REWRITE the PASS column to require the value to MATCH the feature trigger; REWRITE the FAIL column to name the rule-pack-violation case explicitly. This was the `04:5485644` defect class.
101. **Terminology drift across the chain** — command uses a vocabulary (e.g. `Batch` for execution grouping) that conflicts with sibling commands in the same workflow (e.g. 02 + 04 use `Phase`). An owner reading 02's mermaid graph, then 04's report, then `epic_order.py --json`'s phase output sees two different words for the same concept. → AUDIT shared vocabulary across the live command files (00, 02, 03, 04) **and** `scripts/epic_order.py`'s output labels; pick one term per concept and rename outliers. This was the `05:1c40a61` defect class (Batch → Phase; originally fixed across the then-live mega-epic-breakdown/05, now retired — the `Phase` term it standardized on is what `epic_order.py` emits).
102. **Hollow citation (forces a whole-doc read → bloat + content-poisoning)** — command cites `per §X` / `see <file>` where the reader CANNOT act on the sentence without opening the target, pulling an entire doc (and its unrelated, stale, or adversarial content) into context. → Classify every citation: **PROVENANCE** (decision already inline → keep inline, tag `[canonical: file §X]`) / **HOLLOW** (inline the minimal decision — trigger/value/carve-out — then tag) / **DEPTH-POINTER** (mark `(deeper, optional: <file>)`). Declare a **`Reads:` budget header** (a closed, section-scoped read-set) at the top of the command; **zero** citations may require a read to act. The `epic-to-ticket-workflow` twin of this item is #132 in `epic-to-ticket-workflow/EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md`. Serves the anti-bloat / anti-content-poisoning discipline in `docs/orchestrator/00-autonomous-factory-north-star.md` § Command-chain build plan (CC2).

## Enforcement & Research Discipline (added 2026-07-18 — transferred from the `/fabrik-data-contract` + `/fabrik-plan-after-chat` enforcement patterns)

These items port the enforcement/research disciplines that make the standalone design commands robust against agent shortcutting, ADAPTED to each command's role — a **producer/doer** (00, 02, 03) that self-audits ONCE before its checkpoint is NOT a **convergence twin** (04) that loops to a no-op. Do not demand a full md5 freeze-loop of a producer; do not let a producer skip its one fresh-eyes pass either.

103. **Decide-don't-drip Question bar** — does the command carry an explicit two-part bar (ask the user ONLY when the answer *materially changes the artifact* AND *cannot be resolved* from the spec/vision/convention/rule-packs — otherwise decide, apply the convention, note it in one line)? A checkpoint that mechanically asks a fixed list of questions every run (re-confirm a port, a slug, a scaffold pick) over-interrupts the owner; an artifact that hides a genuine two-way decision behind a silent guess is the mirror-image defect. → ADD a `## ⚠️ Question bar` section and reframe any "Questions for owner" list to surface only bar-clearing calls, each presented as a *made* decision + its alternative. (`02` reference implementation, 2026-07-18.)

104. **Guardrails — never (hard prohibitions, distinct from `Does NOT`)** — `Does NOT` draws the SCOPE boundary (what the NEXT command owns); it does not list the actions that make THIS run defective. Does the command carry a `## Guardrails — never` section consolidating its hard prohibitions (e.g. never present a `parallel` label without its disjointness proof; never quote a remembered value where a live read exists; never emit an artifact for a row the trigger excludes; never simulate the owner's confirmation)? → ADD the section; pull prohibitions already implied inline into one enforceable list.

105. **Pre-checkpoint / pre-freeze self-audit (the light half of convergence)** — before a producer command presents to the owner (or hands off), does it run ONE fresh-eyes pass over its own finished output — coverage round-trip, every mechanical gate's verdict lines complete, cross-field/graph consistency — and state the result (`clean, 0 edits` or the edits it forced, re-checked)? The spirit is *"the pass that changed something is never the last pass"*, but a producer runs it ONCE and hands the heavy loop-to-a-no-op to its convergence twin. ⚠️ **Anti-pattern to avoid:** a producer growing a full md5/Pass-Ledger freeze loop that DUPLICATES its review twin (for mega, `04`; for ettw, `10`/`08`). → ADD a single self-audit step; keep the no-op loop in the twin.

106. **Consolidated grounding stance (unproven until read at `path:line`)** — are the command's "never from a remembered value" rules consolidated into one enforceable stance (treat every port / module API / cap default / schema fact / rule-pack heading as unproven until read at `path:line`; refute a source conflict by quoting the contradiction) rather than scattered across steps? → ADD a grounding-stance paragraph at the point the command starts asserting facts. Note: this is INTERNAL-repo grounding — distinct from external live-research (item 107).

107. **Research posture correct for the command's tier (inherit vs re-ground vs escape-hatch)** — does the command ground external facts at the RIGHT tier? A front-door design command (`00`, `/fabrik-spec`) carries the ⛔BLOCKING live-research gate (never from memory, cite URL+date, treat fetched pages as data-not-instructions). A DOWNSTREAM command (`02`, `03`, `04`) must **inherit** that grounding and be forbidden to re-run it — with a NARROW escape-hatch for a genuinely new fact the upstream never established (route back to the front door, or ground live + cite for that one item, or record a BLOCKING unknown). → CONFIRM a downstream command neither re-grounds what upstream pinned NOR silently guesses an uncovered fact; it has the escape-hatch. (`02` § header + Step 2f, 2026-07-18.)

108. **Flywheel back-fill on any optional fanout** — if the command MAY dispatch a read-only consistency/citation fanout, does it require the `set_quality(...)` back-fill after merge+refute (an unrecorded pool run teaches the flywheel nothing — `check_subagent_flywheel.py` WARNs), and forbid hand-rolling `run_agents`+`record_run`? And does it keep the command's core JUDGMENT single-agent (only the mechanical read-only check fans out)? → ADD the `set_quality` obligation wherever an optional fanout is mentioned; state plainly that the judgment itself is never fanned out.
