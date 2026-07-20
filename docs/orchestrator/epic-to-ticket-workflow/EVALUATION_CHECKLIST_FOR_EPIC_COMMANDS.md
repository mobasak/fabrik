<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > (select matching step)
     -->

# Workflow Command Evaluation Checklist

Every workflow command (00-11) must be evaluated against this list before it's considered complete. Not every item applies to every command — but every item must be CHECKED. "N/A for this command" is valid; forgetting to check is not.

---

## Vision & Lifecycle

1. Does it reference/respect the 4-stage lifecycle (Intent → Agentic → Registration → Verification)?
2. Does it confirm the project can pass through ALL 4 stages?
3. Does it reference `docs/operations/fabrik-lifecycle.md`?
4. Does it acknowledge the deploy target (VPS via `fabrik apply` / SSH + Docker Compose, not Vercel/Railway/K8s)?
5. Does it acknowledge the 10 registrars (7 flag-driven + grafana always-on + glitchtip kind-driven + watchdog opt-out) and their shape-gating?

## Architectural Mandates

6. **12-Factor** — does it verify/enforce all 12 factors where applicable?
7. **Concurrency** — does it state/enforce the parallelism mechanism for this service?
8. **i18n** — does it confirm multi-language support (en + tr) for GUI types? Does it enforce `validate_i18n.py` (3-level validation) in Done When for any ticket that adds/changes UI strings?
9. **Resilience** — does it require timeout + retry + circuit-breaker + graceful fallback for external calls?
10. **Self-healing** — does it ensure the service recovers without human intervention?
11. **Shape contract** — does it confirm shape ↔ code alignment?
11b. **Responsive design** — does it enforce 375px floor (RWD1-RWD10) for **any scaffold with a web GUI surface** (saas-skeleton / docusaurus front / python-api / node-api / file-api when `shape.is_admin_dashboard: true` OR `shape.is_public: true` + HTML output — **feature-trigger, NOT scaffold-type-gated** per `mega-epic-breakdown/00-trigger-mega-epic-fabrik` § Rule-area applicability matrix)? Carve-outs: chrome-extension popup (400px fixed), mobile-app (native UI), desktop-app (electron window sizing). Does it reference `docs/reference/mobile-responsive-testing-guide.md`?
11c. **Dark + light mode** — does it enforce both mandatory for **any scaffold with a GUI surface** (same feature-trigger as 11b above; OS detection + manual toggle + persistence)?
11d. **Abuse detection** — does it enforce registration gating for SaaS with free tiers per `saas/87-abuse-detection.md`?
11e. **Email two-stream** — does it enforce separate transactional/marketing streams on separate subdomains per `core/86-email-templates.md`?
11f. **Observability** — does it enforce `/health` for Gatus and `/metrics` for Prometheus on every service?
11g. **Vector DB ban** — if search/RAG: does it enforce pgvector only, self-hosted on postgres-main (`pgvector/pgvector:pg16` + `fabrik-lib/rag`)? Pinecone/Qdrant/Weaviate = rejection.
11h. **FINANCIALS.md** — does it enforce populated unit economics before launch for SaaS scaffolds per `saas/88-saas-launch-checklist.md`?

## Infrastructure Awareness

12. Does it check/use existing self-hosted VPS services BEFORE building new (postgres-main, redis-main, MeiliSearch, Gotenberg, Browserless, Apprise, n8n, Backblaze B2)? (Supabase is NOT a default — legacy/migration-only per `AGENTS.md § Supabase`.)
13. Does it reference the correct backing service addresses (internal Docker names, not localhost)?
14. Does it check for duplicate projects in `AGENTS.md` microservices table + `docs/BUSINESS_MODEL.md`?
15. Does it respect the tech-stack defaults — `AGENTS.md` § Tech Stack Defaults + `docs/reference/technology-stack-decision-guide.md`? (There is no section named "external services decision matrix" — do not look for one.)
15b. Does it check `fabrik-lib/README.md` for vendorable modules BEFORE designing a component from scratch (abuse prevention, email templates, storage, credits, webhooks, etc.)?

## Quality & Error-Free Execution

16. Does it produce output that agents can execute WITHOUT asking questions?
17. Does it reference `final_gate.py` as the quality enforcement mechanism?
18. Does it enforce structured logging (structlog/pino → stdout, no print)?
19. Does it enforce health endpoints that test real dependencies?
20. Does it enforce `deploy.resources.limits` in compose?

## Speed & Parallelism

21. **Planning is SLOW** — does it encourage thoroughness, questions, multiple rounds?
22. **Execution is FAST** — does it minimize ambiguity so agents fly?
23. Does it design for maximum parallel execution (independent work streams)?
24. Does it respect solo dev reality (one human orchestrating multiple AI agents)?

## Governance & Documentation

25. Does it reference the Documentation Sync Matrix (which docs to update per change)?
26. Does it enforce CHANGELOG + INDEX updates?
27. Does it reference the applicable `.windsurf/rules/` packs?
28. Does it know which rule packs apply per scaffold type (via `python scripts/select_rules.py` (the retired AGENTS.md pack table's mechanical successor))?
28b. Does it inject rule packs from 05's category table into ticket Context Files? (e.g., Search category → `core/65-rag-search` + `core/66-rag-chunking`)
29. Does it enforce Lessons Learnt when trigger conditions fire?
30. Does it enforce the Completion Self-Check + Governance Checklist?

## The Owner's Way of Working

31. Does it consume the owner's research file (dropped in `docs/development/plans/` or `docs/preplans/`)?
32. Does it NOT redo work already done by a prior command?
33. Does it propagate decisions downstream (Metadata → later commands)?
34. Does it wait for EXPLICIT user confirmation (silence ≠ confirmation)?
35. Does it suggest `revise-requirements` when scope changes, not silently absorb?

## Automation & Deploy

36. Does it confirm `fabrik apply` can handle this end-to-end (automation-first)?
37. Does it account for deploy edge cases (.env read-merge preserving registrar-injected vars, `--refresh-infra` when shape changes, build-cache invalidation with `--force`)?
38. Does it reference `fabrik dev` for local validation?
39. Does it reference `fabrik review` for pre-PR bundling?
40. Does it reference `fabrik destroy --use-state` for clean teardown?

## Agent Dispatch

41. Does it dispatch coding agents via Claude Code (Max OAuth) and gradeable fan-out via the OpenRouter subagent pool (`fanout` → `set_quality`, per `core/62-using-subagents.md`) — never the retired Kilo CLI / Windsurf Cascade routes?
42. Does it reference `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` (the auto-updating, flywheel-ranked router doc, regenerated daily) for pool model selection?
43. Does it let the user PICK which agent to dispatch (not force one)?

## The Pool as AI Infrastructure

43b. Does it consider the OpenRouter pool for NON-CODING tasks (data extraction, content generation, batch processing, research — `pick_models(task_type)` routes per `TASK_SUBAGENT_SELECTION.md`)?
43c. Does it reference `docs/reference/MD/ai-prompt-templates.md` when ticket involves designing new prompts, skills, or agent definitions?
43d. Does it reference `core/66-rag-chunking.md` when ticket involves search/RAG features?

## Versatility

44. Does it work for ALL 11 fabrik-scaffolded types (`python-api`, `python-api-gpu`, `node-api`, `saas-skeleton`, `file-api`, `file-worker`, `static-site`, `docusaurus`, `chrome-extension`, `mobile-app`, `desktop-app` per `mega-epic-breakdown/00-trigger-mega-epic-fabrik` § Shape model — WordPress is not built — websites → `/opt/web-ecommerce-factory`), or correctly skip via routing table?
45. Does it handle multi-epic entry correctly? (`00-trigger` is mandatory for ALL runs — single-epic and multi-epic. Multi-epic runs `00-trigger` in consume mode using the epic ticket metadata from `mega-epic-breakdown/03-expand-epic-files-fabrik`. `01-decisions-lock` always receives INFRA-CHECK from `00-trigger` regardless of path.)
45b. Does it handle existing projects via `mega-epic-breakdown/00-trigger-mega-epic-fabrik` in EXISTING mode (owner declares mode at Step 0; produces Vision Summary + Locked Decisions + Compliance Report; Compliance Report `fix-now` rows drive Retrofit epics in `02-epic-decomposition-fabrik`)?
46. Does it handle two-faced types (mobile/desktop/chrome-extension: backend deploys, client doesn't)?

## Scope Protection

47. Does it enforce explicit Out of Scope boundaries?
48. Does it include DO NOT rules for agents?
49. Does it prevent scope creep (agents can't touch files outside ticket scope)?

## Deployment Contract (compose.yaml)

50. Does it enforce `platform: linux/amd64`?
51. Does it enforce Traefik labels (Host, websecure, letsencrypt, hardcoded port)?
52. Does it enforce `healthcheck` with `start_period: 60s`?
53. Does it enforce `networks: fabrik: external: true`?
54. Does it enforce NO host port bindings (all via Traefik)?

## Security

55. Does it enforce M2M auth pattern (`X-Internal-Token` + `SERVICE_INTERNAL_SECRET_KEY`) for internal APIs?
56. Does it enforce Authelia forward-auth for admin dashboards?
57. Does it enforce no secrets in source code (Factor III)?
58. Does it enforce sensitive file backup before modification?
59. Does it reference UFW + DOCKER-USER iptables (defense-in-depth)?

## Budget & Constraints

60. Does it prefer free/self-hosted over paid SaaS?
61. Does it enforce no Alpine (slim-bookworm only)?
62. Does it respect port ranges (Python 8000-8099, Frontend 3000-3099)?
63. Does it check PORTS.md before assigning?
64. Does it enforce scaffold immutability (don't reorganize scaffolded structure)?

## Testing

65. Does it enforce ONE integration test per PRIMARY PATH?
66. Does it reference `final_gate.py` tiers (1 lean / 2 full / 3 systemic)?
67. Does it enforce `fabrik verify` + `fabrik audit-registrars` post-deploy?

## Future Items (acknowledge as planned)

68. Does it acknowledge the VPS watchdog agent — **SHIPPED, not planned**: the 10th registrar, opt-OUT on `fabrik apply` (`src/fabrik/drivers/watchdog.py`). A command that still calls it "planned" is stale.
69. Does it acknowledge auto-rollback wire (planned — verify.py:394)?
70. Does it acknowledge `fabrik export/import` for portability?

## Design & UX (GUI types)

71. Does it reference Ocoron design system (`.windsurf/rules/core/ocoron-design-system.md`)? For `mobile-app`, also `.windsurf/rules/mobile-app/ocoron-mobile-design-system.md`?
72. Does it enforce Verbal Identity (no forbidden language)?
73. Does it enforce the 7 enriched UI states (Loading/Empty/Error/Permission Denied/Success/Partial Success/Disabled) per design system?

## The Research Starting Point

74. Does it treat the owner's research file as THE starting point (not interview from zero)?
75. Does it IMPROVE the research rather than ignore it?
76. Does it surface what the research MISSED (gaps, conflicts, opportunities)?

## Agent Workforce Reality

77. Does it acknowledge the execution model of solo-human operator + multiple AI agents working in parallel (not assume a team handoff or multi-human coordination)?
78. Does it design tickets for agent independence — each agent works without blocking on another agent's mid-ticket output?
79. Does it allow throughput maximization by supporting multiple parallel Claude Code agents + OpenRouter-pool workers simultaneously?
80. Does it ensure agents communicate only through the codebase (git) — integration at batch boundaries, never mid-ticket coordination?
81. Does it batch human review at batch completion checkpoints, not per-ticket (3-5 tickets per review batch per `ettw/06-ticket-breakdown-fabrik`)?
82. Does it support agent selection per ticket based on complexity + cost (cheap flywheel-ranked pool models for simple, Claude Code/Opus for critical)?

## Deploy Lifecycle (Zero Residue)

83. Does it ensure deploy/redeploy/destroy leaves NO residue (no orphan containers, no stale DNS, no leftover files)?
84. Does it enforce clean container naming (stable `container_name:` set in compose; never Docker-generated suffixes)?
85. Does it ensure `fabrik destroy` reverses EVERYTHING `fabrik apply` created?
86. Does it enforce that the lifecycle works for ALL 11 scaffold types (proven by lifecycle proof test)?

## Iterative Convergence

87. Does it align with the vision EVERY TIME (iterate to converge)?
88. Does it update the memorized doc-sync set (11+ files) after changes?
89. Does it keep `docs/operations/fabrik-lifecycle.md` current (reflects 100% of what exists)?
90. Does it avoid re-doing work already done by prior commands?

## Agent Orchestration Quality

91. Does it maintain quality across ALL tickets (no degradation on ticket 15 vs ticket 1)?
92. Does it enforce the same governance depth on the LAST ticket as the FIRST?
93. Does it batch tickets (3-5 max per run) to prevent AI fatigue/degradation?
94. Does it produce tickets that are agent-INDEPENDENT (no inter-agent communication needed)?

## Owner's Research-First Approach

95. Owner researches EXTERNALLY first (ChatGPT/Claude/Gemini) → drops file in project.
96. Traycer READS the research → IMPROVES it → asks about GAPS → never starts from zero.
97. The research file is the STARTING POINT, not a reference to skim.
98. If no research file exists, Traycer interviews — but the owner's preference is research-first.

## Clean VPS / No Mess

99. No stale containers left after testing or failed deploys.
100. No orphan GitHub repos from test runs.
101. No leftover spec files from destroyed projects.
102. No dangling Docker images consuming disk.
103. Container names must be stable and recognizable (set via `container_name:`, not Docker-generated suffixes).
104. Memory limits enforced on ALL containers (no unlimited memory).

## The Vision Statement (always reference)

105. Stage 1: Intent & Scaffolding — context injection, AI guardrails, shape block.
106. Stage 2: Agentic Implementation — infra-aware code, spec contract, fabrik dev/review.
107. Stage 3: Proper Registration — fabrik apply, 10 registrars, auto-observability, network security.
108. Stage 4: Verification & Testing — health check, drift detection, Telegram alert, auto-rollback (WIP — `verify.py:394` is a stub), VPS watchdog (**SHIPPED** — the 10th registrar, opt-OUT).

## External Services (self-hosted-first — Backblaze B2, etc.; Supabase legacy/migration-only)

109. Self-hosted defaults enforced (per `AGENTS.md § Supabase`): auth → `fabrik-lib/fastapi-user-auth` (Pattern A, app issues its own JWTs); pgvector → `pgvector/pgvector:pg16` + `fabrik-lib/rag`; object storage → `fabrik-lib/storage`/B2; realtime → `redis-main` pubsub (+ WS/SSE only if needed). Supabase is NOT proposed for new work.
110. Backblaze B2 for file storage (via `fabrik-lib/storage`) — never local filesystem in production (Factor VI).
111. PostgreSQL on `postgres-main` is the default; Supabase is a deliberate, ADR-recorded exception only for a project already running on it (legacy — plan its migration to self-hosted).
112. Technology choice documented in tech-plan with justification.

## Documentation Templates (scaffolded, must be FILLED)

113. Every scaffolded doc template (README, CHANGELOG, CONFIGURATION, FEATURES, QUICKSTART, API_REFERENCE, DEPLOYMENT, RESILIENCE, DATABASE_SCHEMA, TROUBLESHOOTING, BUSINESS_MODEL, LESSONS_LEARNT) gets filled during the epic — not left empty.
114. The Documentation Sync Matrix in ticket-breakdown assigns which ticket fills which doc.
115. An empty template at epic end = governance failure.

## Lean, Factual, Comprehensive

116. Every command output is LEAN (no bloat, no filler, no repetition) but COMPREHENSIVE (nothing important omitted).
117. Target line counts per artifact: Core Flows 200, Tech Plan 300, Ticket 100. **The Decisions Lock is
     exempt — NO length cap** (it is the epic's persisted store of record; completeness beats brevity there
     `[canonical: 01-decisions-lock-fabrik § Core Philosophy]`).
118. Overruns require justification. Approaching 2x cap = split proposal. (Does not apply to the
     cap-exempt Decisions Lock.)
119. **Factual only.** Every statement in a command file must reflect what ACTUALLY exists in the codebase/VPS — not aspirational, not theoretical, not "planned." If something is planned but not built, say "planned" explicitly.
120. **No bullshit lines.** If a sentence doesn't change agent behavior or inform a decision, delete it.
121. **No duplication between commands.** Each command consumes upstream output. Never restate what a prior command already produced — reference it.
122. **Every instruction must be actionable.** "Consider X" is banned. "Check X and state finding" is correct.
123. **No misleading claims.** If content X lives in file Y, verify it actually does before writing "read Y for X." Wrong references waste agent time and erode trust.

## Regression-Coverage Anti-Patterns (added 2026-06-18 from cross-chain defect-class audit)

124. **Feature-vs-scaffold drift in GUI mandates** — command applies i18n / Responsive / Dark+Light requirements based on scaffold TYPE (e.g. `saas-skeleton ⇒ mandatory`, `python-api ⇒ N/A`) instead of the GUI surface itself. Includes python-api / node-api / file-api with `shape.is_admin_dashboard: true` OR `shape.is_public: true` + HTML output. → REWRITE the trigger to be feature-based per `mega-epic-breakdown/00-trigger-mega-epic-fabrik` § Rule-area applicability matrix. Hit in ettw/05 pre-`ff2c427`; same class fixed in mega chain at 00 (c2ef2ee + 87b1de8), 02 (d63c5ea), 03 (71dad46), 04 (5485644), ettw/05 (ff2c427).
125. **Dangling citation to archived/missing file** — command cites a path under `docs/development/plans/` or `docs/reference/` that has been archived to `archived/` OR no longer exists. → VERIFY every cited path with `ls`/`Read` before merge; if archived, either inline the relevant content or cite the archived path explicitly with `(archived; historical context only)`.
126. **Retrofit-epic special-case missing** — command (downstream of `mega-epic-breakdown/00-trigger-mega-epic-fabrik` EXISTING mode) treats Retrofit epics like delta-feature epics. Retrofit handling: Title prefix `Retrofit:`, 3–5 Success Criteria (not 5–8), `scripts/final_gate.py` as deploy-level criterion (not `fabrik apply`), optional Epic Closure. → ADD explicit Retrofit branch per `mega-epic-breakdown/03-expand-epic-files-fabrik` § Success Criteria + `ettw/05-ticket-outline-fabrik` Step 1 Multi-epic dispatch mode section.
127. **Presence-only validation when contract is semantic** — validator command checks "Field X | Present or N/A stated | Missing" without validating that the N/A reason matches the underlying trigger condition. A `Responsive: N/A — non-GUI scaffold` declared on an epic with `shape.is_admin_dashboard: true` would PASS a presence-only check despite being a rule-pack violation. → REWRITE PASS column to require value-matches-trigger; REWRITE FAIL column to name the rule-pack-violation case explicitly. Applies primarily to ettw/08-implementation-validation + ettw/10-cross-artifact-validation.
128. **Terminology drift across chain** — command uses a vocabulary that conflicts with sibling commands (e.g. `batch` for execution grouping when 02 + 04 + 05 use `Phase`; `ticket-breakdown` vs `Ticket Breakdown` for command names). → AUDIT shared vocabulary across all 13 ettw `-fabrik` files (00,01,01R,02–11) AND the 4 live mega-epic-breakdown files (00,02,03,04); pick one term per concept; rename outliers.
129. **Path A vs Path B drift** — command handles single-epic (Path A — `ettw/00-trigger` ran first producing INFRA-CHECK) but not multi-epic dispatched (Path B — `mega-epic-breakdown/03-expand-epic-files-fabrik` ticket consumed as INFRA-CHECK), or vice versa. Path B 15-field Metadata block per `ettw/00-trigger-fabrik` § Entry Points → Multi-epic (consume mode) (post-`5a48017`) must be honored: Scaffold, Port, target_vps, Shape, Concurrency, i18n, Responsive, Dark+Light, Rule Packs, HAS_USER_GUIDE, Registrars, Universal categories, Abuse Detection, Email, FINANCIALS. → ADD explicit "Path A: ... / Path B: ..." branches; verify all 15 Metadata fields propagate without silent dropping (incl. `target_vps`).
130. **Shared-state between parallel tickets** — command marks tickets as `⚡ parallel` without verifying they don't write/read the same file, table, or config. Two parallel tickets touching the same migration file = broken build. → ADD shared-state check per `ettw/05-ticket-outline-fabrik` § Step 2: Identify Work Units + Parallel Lanes (`do NOT mark tickets as parallel when one WRITES to a file/table/config that the other READS`); enforce in `ettw/06-ticket-breakdown` per-ticket Files Touched section.
131. **Per-Scaffold Observability Matrix row mismatch** — command applies the wrong row from `core/55-observability.md § Per-Scaffold Observability Matrix` (e.g., file-worker observability requirements applied to a saas-skeleton, or static-site `/health` mandate applied where the scaffold has no app process). → CITE the scaffold-specific matrix row explicitly; reference the matrix BY SCAFFOLD TYPE, not by generic "every service has /health".
132. **Hollow citation (forces a whole-doc read → bloat + content-poisoning)** — command cites `per §X` / `see <file>` where the reader CANNOT act on the sentence without opening the target, pulling an entire doc (and its unrelated, stale, or adversarial content) into context. → Classify every citation: **PROVENANCE** (decision already inline → keep inline, tag `[canonical: file §X]`) / **HOLLOW** (inline the minimal decision — trigger/value/carve-out — then tag) / **DEPTH-POINTER** (mark `(deeper, optional: <file>)`). Declare a **`Reads:` budget header** (a closed, section-scoped read-set) at the top of the command; **zero** citations may require a read to act. The `mega-epic-breakdown` twin of this item is #102 in `mega-epic-breakdown/EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md`. Serves the anti-bloat / anti-poisoning discipline in `docs/orchestrator/00-autonomous-factory-north-star.md` § Command-chain build plan (CC2).

## Enforcement & Research Discipline (added 2026-07-18 — the ettw twin of `mega-epic-breakdown` items 103–108, ported from the `/fabrik-data-contract` + `/fabrik-plan-after-chat` enforcement patterns)

These items port the enforcement/research disciplines that make the standalone design commands robust against agent shortcutting, ADAPTED to each ettw command's role. **Producers** — `00-trigger` · `01-decisions-lock` · `02-core-flows` · `03-tech-plan` · `04-deploy-plan` · `05-ticket-outline` · `06-ticket-breakdown` — self-audit ONCE before their checkpoint/handoff. **Convergence/review twins** — `01R-decisions-review` (converges + locks `01`'s artifact — Gate 1), `08-implementation-validation`, and `10-cross-artifact-validation` — own the loop-to-a-no-op (their Termination Contract); do NOT give a producer a full freeze loop that duplicates them. `07-execute` (executor, own loop), `09-revise-requirements`, and `11-deploy` are special-role and audited against these only where a discipline genuinely applies. The `mega-epic-breakdown` twins of these items are #103–108 in `mega-epic-breakdown/EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md`.

133. **Decide-don't-drip Question bar** — does the command carry an explicit two-part bar (ask the user ONLY when the answer *materially changes the artifact* AND *cannot be resolved* from the epic ticket / prior-step artifact / convention / rule-packs — otherwise decide, apply the convention, note it in one line)? A checkpoint that mechanically asks a fixed list every run over-interrupts; an artifact that hides a genuine two-way decision behind a silent guess is the mirror-image defect. → ADD a `## ⚠️ Question bar` section (producers with an owner checkpoint) and reframe any fixed "Questions for owner" list to surface only bar-clearing calls, each a *made* decision + its alternative. N/A for a pure transform with no owner checkpoint.

134. **Guardrails — never (hard prohibitions, distinct from `Does NOT`)** — `Does NOT` draws the SCOPE boundary (what the NEXT command owns); it does not list the actions that make THIS run defective. Does the command carry a `## Guardrails — never` section consolidating its hard prohibitions (e.g. never mark tickets `⚡ parallel` without the shared-state proof (item 130); never quote a remembered value where a read exists; never emit an artifact for a trigger-excluded row; never simulate the owner's confirmation)? → ADD the section; pull prohibitions already implied inline into one enforceable list.

135. **Pre-checkpoint / pre-handoff self-audit (the light half of convergence)** — before a producer presents to the owner (or hands to the next step), does it run ONE fresh-eyes pass over its own finished output — coverage round-trip against the epic ticket, every mechanical gate's verdict lines complete, cross-artifact field consistency — and state the result (`clean, 0 edits` or the edits it forced, re-checked)? ⚠️ **Anti-pattern to avoid:** a producer growing a full md5/Pass-Ledger freeze loop that DUPLICATES its review twin (`01R-decisions-review` / `10-cross-artifact-validation` / `08-implementation-validation`). → ADD a single self-audit step; keep the no-op loop in the twin.

136. **Consolidated grounding stance (unproven until read at `path:line`)** — are the command's "never from a remembered value" rules consolidated into one enforceable stance (treat every port / module API / cap default / schema fact / rule-pack heading as unproven until read at `path:line`; refute a source conflict by quoting the contradiction) rather than scattered? → ADD a grounding-stance paragraph where the command starts asserting facts. Internal-repo grounding — distinct from external live-research (item 137).

137. **Research posture correct for the command's tier (inherit vs re-ground vs escape-hatch)** — a DOWNSTREAM ettw command **inherits** the live-grounding done by the front door (`mega/00` Vision Summary + `ettw/00-trigger` INFRA-CHECK) and is forbidden to re-run it, with a NARROW escape-hatch for a genuinely new fact the upstream never established (route back, or ground live + cite for that one item, or record a BLOCKING unknown). → CONFIRM a downstream command neither re-grounds what upstream pinned NOR silently guesses an uncovered fact.

138. **Flywheel back-fill on any pool fanout** — if the command dispatches a `fanout` (grounders / reconcilers / finders — `03-tech-plan`, `06-ticket-breakdown`, `07`, `08`, `10` all do), does it require the `set_quality(...)` back-fill after merge+refute (an unrecorded pool run teaches the flywheel nothing — `check_subagent_flywheel.py` WARNs), and forbid hand-rolling `run_agents`+`record_run`? And keep the core JUDGMENT single-agent where the discipline demands it? → ADD the `set_quality` obligation wherever a fanout is mentioned.
