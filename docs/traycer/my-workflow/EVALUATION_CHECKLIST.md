# Workflow Command Evaluation Checklist

Every workflow command (00-11) must be evaluated against this list before it's considered complete. Not every item applies to every command — but every item must be CHECKED. "N/A for this command" is valid; forgetting to check is not.

---

## Vision & Lifecycle

1. Does it reference/respect the 4-stage lifecycle (Intent → Agentic → Registration → Verification)?
2. Does it confirm the project can pass through ALL 4 stages?
3. Does it reference `docs/reference/fabrik-lifecycle.md`?
4. Does it acknowledge the deploy target (VPS via Coolify, not Vercel/Railway/K8s)?
5. Does it acknowledge the 9 registrars and their shape-gating?

## Architectural Mandates

6. **12-Factor** — does it verify/enforce all 12 factors where applicable?
7. **Concurrency** — does it state/enforce the parallelism mechanism for this service?
8. **i18n** — does it confirm multi-language support (en + tr) for GUI types?
9. **Resilience** — does it require timeout + retry + circuit-breaker + graceful fallback for external calls?
10. **Self-healing** — does it ensure the service recovers without human intervention?
11. **Shape contract** — does it confirm shape ↔ code alignment?

## Infrastructure Awareness

12. Does it check/use existing VPS services BEFORE building new (postgres-main, redis-main, MeiliSearch, Gotenberg, Browserless, Apprise, n8n, Backblaze B2, Supabase)?
13. Does it reference the correct backing service addresses (internal Docker names, not localhost)?
14. Does it check for duplicate projects in `AGENTS.md` microservices table + `docs/reference/fabrik-project-catalog.md`?
15. Does it respect the external services decision matrix?

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
28. Does it know which rule packs apply per scaffold type (from `AGENTS.md` § Project Type → Default Packs)?
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
37. Does it account for Coolify workarounds (SSH fallback, .env pre-seed)?
38. Does it reference `fabrik dev` for local validation?
39. Does it reference `fabrik review` for pre-PR bundling?
40. Does it reference `fabrik destroy --use-state` for clean teardown?

## Agent Dispatch

41. Does it identify agents from ALL THREE suppliers (Claude Code, Windsurf Cascade, Kilo CLI)?
42. Does it reference `docs/traycer/kilo_selected_agents.md` + `docs/reference/windsurf/cascade-models.md`?
43. Does it let the user PICK which agent to dispatch (not force one)?

## Versatility

44. Does it work for ALL 11 scaffold types (or correctly skip via routing table)?
45. Does it handle the "Feature for existing project" rubric?
46. Does it handle two-faced types (mobile/desktop/chrome-extension: backend deploys, client doesn't)?

## Scope Protection

47. Does it enforce explicit Out of Scope boundaries?
48. Does it include DO NOT rules for agents?
49. Does it prevent scope creep (agents can't touch files outside ticket scope)?

## Deployment Contract (compose.yaml)

50. Does it enforce `platform: linux/amd64`?
51. Does it enforce Traefik labels (Host, websecure, letsencrypt, hardcoded port)?
52. Does it enforce `healthcheck` with `start_period: 60s`?
53. Does it enforce `networks: coolify: external: true`?
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

68. Does it acknowledge the VPS watchdog agent (planned — self-healing daemon on VPS)?
69. Does it acknowledge auto-rollback wire (planned — verify.py:394)?
70. Does it acknowledge `fabrik export/import` for portability?

## Design & UX (GUI types)

71. Does it reference Ocoron design system (`.windsurf/rules/ocoron-design-system.md`)?
72. Does it enforce Verbal Identity (no forbidden language)?
73. Does it enforce the 5 UI states (Empty/Loading/Error/Success/Disabled)?

## The Research Starting Point

74. Does it treat the owner's research file as THE starting point (not interview from zero)?
75. Does it IMPROVE the research rather than ignore it?
76. Does it surface what the research MISSED (gaps, conflicts, opportunities)?

## Agent Workforce Reality

77. Solo HUMAN operator — but multiple AI agents working in PARALLEL.
78. Design tickets for agent independence (each agent works without blocking on another agent's output).
79. Maximize throughput by dispatching to Claude Code + Windsurf Cascade + Kilo CLI simultaneously.
80. Agents don't communicate with each other — only through the codebase (git). Integration happens at batch boundaries, not mid-ticket.
81. The human reviews at batch completion checkpoints, not per-ticket.
82. Agent selection per ticket based on complexity + cost (free locals for simple, premium cloud for critical).

## Deploy Lifecycle (Zero Residue)

83. Does it ensure deploy/redeploy/destroy leaves NO residue (no orphan containers, no stale DNS, no leftover files, no ghost Coolify apps)?
84. Does it enforce clean container naming (no shitty/random names visible in Coolify GUI)?
85. Does it ensure `fabrik destroy` reverses EVERYTHING `fabrik apply` created?
86. Does it enforce that the lifecycle works for ALL 11 scaffold types (proven by lifecycle proof test)?

## Iterative Convergence

87. Does it align with the vision EVERY TIME (iterate to converge)?
88. Does it update the memorized doc-sync set (11+ files) after changes?
89. Does it keep `docs/reference/fabrik-lifecycle.md` current (reflects 100% of what exists)?
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
103. Container names in Coolify GUI must be recognizable (not UUID gibberish).
104. Memory limits enforced on ALL containers (no unlimited memory).

## The Vision Statement (always reference)

105. Stage 1: Intent & Scaffolding — context injection, AI guardrails, shape block.
106. Stage 2: Agentic Implementation — infra-aware code, spec contract, fabrik dev/review.
107. Stage 3: Proper Registration — fabrik apply, 9 registrars, auto-observability, network security.
108. Stage 4: Verification & Testing — health check, drift detection, Telegram alert, auto-rollback (WIP), VPS watchdog (planned).

## External Services (Supabase, Backblaze, etc.)

109. Supabase available for: managed auth, realtime, pgvector, storage — USE when appropriate.
110. Backblaze B2 for file storage — never local filesystem in production (Factor VI).
111. Both PostgreSQL (self-hosted) and Supabase (managed) are valid — project decides based on needs.
112. Technology choice documented in tech-plan with justification.

## Documentation Templates (scaffolded, must be FILLED)

113. Every scaffolded doc template (README, CHANGELOG, CONFIGURATION, FEATURES, QUICKSTART, API_REFERENCE, DEPLOYMENT, RESILIENCE, DATABASE_SCHEMA, TROUBLESHOOTING, BUSINESS_MODEL, LESSONS_LEARNT) gets filled during the epic — not left empty.
114. The Documentation Sync Matrix in ticket-breakdown assigns which ticket fills which doc.
115. An empty template at epic end = governance failure.

## Lean, Factual, Comprehensive

116. Every command output is LEAN (no bloat, no filler, no repetition) but COMPREHENSIVE (nothing important omitted).
117. Target line counts per artifact: Epic Brief 50, Core Flows 200, Tech Plan 300, Ticket 100.
118. Overruns require justification. Approaching 2x cap = split proposal.
119. **Factual only.** Every statement in a command file must reflect what ACTUALLY exists in the codebase/VPS — not aspirational, not theoretical, not "planned." If something is planned but not built, say "planned" explicitly.
120. **No bullshit lines.** If a sentence doesn't change agent behavior or inform a decision, delete it.
121. **No duplication between commands.** Each command consumes upstream output. Never restate what a prior command already produced — reference it.
122. **Every instruction must be actionable.** "Consider X" is banned. "Check X and state finding" is correct.
123. **No misleading claims.** If content X lives in file Y, verify it actually does before writing "read Y for X." Wrong references waste agent time and erode trust.
