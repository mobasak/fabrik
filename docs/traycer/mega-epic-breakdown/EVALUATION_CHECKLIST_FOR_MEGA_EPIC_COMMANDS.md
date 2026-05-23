<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     This checklist is used to evaluate mega-epic-breakdown commands (00, 02-05)
     during creation. Stress-test every command against every applicable item.
     "N/A for this command" is valid; forgetting to check is not.
     -->

# Mega-Epic Command Evaluation Checklist

Every command in mega-epic-breakdown (00, 02-05) must be evaluated against this list before it's considered complete. This checklist is for DECOMPOSITION quality — splitting a large vision into independent epics. For TICKET quality, see `my-workflow/EVALUATION_CHECKLIST.md`.

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
14. Is each epic SELF-CONTAINED enough to go through my-workflow/00-11 independently?

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
23. Auth: which auth mechanism (Authelia forward-auth, Supabase Auth, custom)?
24. Deploy target: VPS via Coolify confirmed? (not Vercel/Railway/K8s)
25. Backing services: which existing VPS services will be used (postgres-main, redis-main, MeiliSearch, etc.)?
26. External services: which third-party APIs/services (Supabase, Backblaze, Paddle, etc.)?
27. Domain/routing: which subdomains, which Traefik routing rules?
28. Scaffold type per epic: which of the 11 scaffold types applies?
29. Shape block per epic: what registrars will each epic's `fabrik apply` activate?

## Handoff to my-workflow

30. Does each epic output file contain enough context for my-workflow/01-epic-brief to START? (scope, success criteria, constraints, metadata)
31. Does each epic output file reference the shared infrastructure decisions? (not duplicate them)
32. Does each epic output file state what PRIOR EPICS produced that this epic consumes? (DB tables, API contracts, env vars)
33. Does each epic output file state what THIS EPIC produces that later epics need? (contracts, not implementation details)
34. Can Traycer run my-workflow/01-epic-brief with ONLY the epic output file + the infrastructure decisions file? (no need to re-read the full vision research)

## Context Window Respect

35. Is the vision summary ≤5,000 tokens? (must fit alongside epic brief in 200K context)
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

44. Does it reference `docs/reference/fabrik-lifecycle.md`?
45. Does each epic cover all 4 stages? (Intent → Implementation → Registration → Verification)
46. Or is it explicitly stated that some epics only cover certain stages? (e.g., "Epic 1 is foundation-only — no user-facing features, no Stage 4 health checks")
47. Are the 9 registrars considered per epic? (which registrars fire for each epic's `fabrik apply`)

## Solo Dev Reality

48. Can one human + AI agents execute one epic at a time? (don't assume parallel human attention across epics)
49. Are epics ordered to deliver VALUE EARLY? (not foundation-foundation-foundation-finally-something-works)
50. Does Epic 1 produce something the owner can SEE and USE? (motivation matters for solo devs)
51. Is the total epic count REASONABLE? (3-7 epics typical. 10+ = re-examine. 2 = probably not mega enough to need this workflow)

## Fabrik Infrastructure Awareness

52. Does it check for EXISTING projects on VPS that overlap? (`AGENTS.md` microservices table + `docs/reference/fabrik-project-catalog.md`)
53. Does it check for PORT conflicts? (`PORTS.md`)
54. Does it check for DUPLICATE functionality? (don't build what exists)
55. Does it use existing VPS services BEFORE building new? (postgres-main, redis-main, etc.)
56. Does it respect the external services decision matrix from `AGENTS.md`?

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

75. **Vision Summary** (00 output): ≤5,000 tokens. Sections: Product Vision, Personas, Value Streams, Full Feature Inventory, Constraints, Out of Scope, Open Questions.
76. **Infrastructure Decisions** (02 output): ≤5,000 tokens. Sections: Scaffold Type(s), Database Strategy, Auth Strategy, Backing Services, External Services, Domain/Routing, Shared Shape Block Decisions.
77. **Compact Epic Proposal** (02 output): Scope summary, features, scaffold, dependencies, parallel lanes, port, delivers, rule packs, HAS_USER_GUIDE per epic.
78. **Full Epic File** (03 output, one per epic): ≤10,000 tokens. Sections: Summary, Scope, Success Criteria, Out of Scope, Dependencies (produces/consumes), Technology Stack, Metadata for my-workflow/01-epic-brief, Estimated Scale.
79. **Dependency Graph** (02 output): Mermaid diagram + execution order table + parallel lanes identified.
80. **Validation Report** (05 output): Gap analysis, interface inventory, risk register, final approval gate.

## Handoff Format (epic file → my-workflow/01-epic-brief)

80. Each epic output file MUST contain a `## Metadata` section with: scaffold type, shape flags, concurrency model, i18n requirement, port assignment, rule packs list — matching what my-workflow/01-epic-brief expects in its "Metadata" field.
81. Each epic output file MUST contain a `## Success Criteria` section with numbered, testable criteria — matching what my-workflow/01-epic-brief uses to validate coverage.
82. Each epic output file MUST contain a `## Dependencies` section stating: what prior epics produced (DB tables, API contracts, env vars) that this epic assumes exist.
83. Each epic output file MUST be SELF-SUFFICIENT — Traycer running my-workflow/01 reads ONLY this file + infrastructure-decisions.md. No need to load the full vision research.

## Iterative Convergence

84. Does it wait for EXPLICIT user confirmation? (silence ≠ confirmation)
85. Does it suggest revisions when scope changes instead of silently absorbing?
86. Does it iterate with the owner until the decomposition is RIGHT? (planning is SLOW, execution is FAST)
87. Does it present the dependency graph VISUALLY (mermaid diagram)?

## Anti-Patterns (if any of these are true, the command file is WRONG)

88. Command says "Consider..." instead of "Check X and state finding." → REWRITE.
89. Command produces output that requires the NEXT command to ask the user what's missing. → ADD to this command.
90. Command restates what a prior command already produced. → DELETE and reference.
91. Two commands produce overlapping output. → MERGE or split boundary clearly.
92. Command's output doesn't have a clear token budget. → ADD budget.
93. Command doesn't have Acceptance Criteria. → ADD.
94. Epic output file requires loading the full vision research alongside it. → CONDENSE epic file to be self-sufficient.
95. Command uses vague scope ("relevant files", "update as needed", "consider implications"). → REWRITE with concrete paths and actions.
