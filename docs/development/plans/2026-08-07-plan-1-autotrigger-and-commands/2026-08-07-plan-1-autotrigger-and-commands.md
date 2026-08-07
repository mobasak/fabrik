# Plan: Auto-trigger stack + four missing commands

Status: IN-PROGRESS (execution dispatched 2026-08-07; converged at b44bf3250438 — 3 passes, 13 findings)

Skill auto-triggering (TRIGGER-sharpened descriptions, Stage taxonomy, Orient routing, a
UserPromptSubmit router hook, stage-skip artifact gates) plus the four commands this week's work
proved missing (`/fabrik-catchup`, `/fabrik-decommission`, `/fabrik-deploy-verify`,
`/fabrik-upstream`). All design decisions were settled in the operator conversation of 2026-08-07;
this set distills them for dispatch. Command/skill parity is structural (one assembler renders
both from one source — verified 20/20 at HEAD incl. the non-prefixed `design-review`,
`commands/assemble_commands.py`).

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | fabrik-catchup command | — | ⚡ | ✅ | merged 60bb9e47 (4 review rounds) |
| T02 | fabrik-decommission command | — | ⚡ | ⬜ | |
| T03 | fabrik-deploy-verify command | — | ⚡ | ⬜ | |
| T04 | fabrik-upstream command | — | ⚡ | ⬜ | |
| T05 | UserPromptSubmit router hook | — | ⚡ | ⬜ | |
| T06a | TRIGGER+Stage sweep (design/contract/plan skills) | — | ⚡ | ⬜ | |
| T06b | TRIGGER+Stage sweep (build/certify/release/gate/utility skills) | — | ⚡ | ⬜ | |
| T07 | Orient step-0 routing rule | — | ⚡ | ⬜ | |
| T08 | Stage-skip artifact gates | — | ⚡ | ⬜ | |
| T99 | Integration: parity, receipts, whole-plan gates | T01, T02, T03, T04, T05, T06a, T06b, T07, T08 | ⛓️ | ⬜ | |

## Merge Order

1. T01
2. T02
3. T03
4. T04
5. T06a
6. T06b
7. T05
8. T07
9. T08
10. T99

Serialized: commands/assemble_commands.py — T01, T02
Serialized: commands/assemble_commands.py — T01, T03
Serialized: commands/assemble_commands.py — T01, T04
Serialized: commands/assemble_commands.py — T02, T03
Serialized: commands/assemble_commands.py — T02, T04
Serialized: commands/assemble_commands.py — T03, T04
Serialized: commands/_sources/fabrik-release.md — T03, T06b

## Interfaces

- **Stage taxonomy (frozen vocabulary, § Global Constraints):** `1-design · 2-contract · 3-plan ·
  4-build · 5-certify · 6-release · gate · utility`. Producers: this spine. Consumers: T01–T04
  (their descriptions carry `Stage:`), T06a/T06b (sweep it into the 20 existing), T07 (the Orient
  table names stages), T05 (the router injects the matched stage). Seam test (consumer T99):
  every rendered skill description contains exactly one `Stage:` value from the vocabulary —
  `grep -L 'Stage: ' ~/.claude/skills/{fabrik-*,design-review}/SKILL.md` empty (the brace set is
  deliberate: a bare `fabrik-*` glob structurally skips `design-review`) + no off-vocabulary value.
- **Assembler wiring shape:** T01–T04 each add one NEXT-map entry + one PARAMS block to
  `commands/assemble_commands.py` (Serialized above). Seam test (consumer T99):
  `python commands/assemble_commands.py --check` clean with 24 commands + 24 skills (20 existing incl. `design-review` + 4 new).
- **Router roster discovery:** T05's hook reads the skill roster DYNAMICALLY from
  `~/.claude/skills/fabrik-*` at fire time — no dependency on T01–T04, future fabrik commands
  auto-enroll. `design-review` is DELIBERATELY outside the router roster (a pipeline-invoked GUI
  sub-gate, never prompt-auto-triggered; its T06b TRIGGER clause serves model-native matching
  only). Seam test (consumer T99): with all four new skills rendered, the roster probe lists 23
  fabrik-prefixed skills (of 24 total).

## Behavior Contract

- **Given** a neglected project, **When** `/fabrik-catchup` runs, **Then** it MEASURES first (plan-state vs locks, key-doc freshness vs code, stub sentinels, spec↔shape truth) and emits a worst-first fix queue routed to existing converge commands (commands/_sources/fabrik-catchup.md:1).
- **Given** a catchup fix queue, **When** executed, **Then** each fix lands via its owning command (`/fabrik-doc-converge`, `/fabrik-features`, `/fabrik-data-contract`) — catchup never re-implements a converge loop (commands/_sources/fabrik-catchup.md:1).
- **Given** a retirement request, **When** `/fabrik-decommission` runs, **Then** the consumer sweep and runtime-liveness probe (DNS vs siblings, never registry rows) run BEFORE any move, and runtime teardown is a separately operator-gated step (commands/_sources/fabrik-decommission.md:1).
- **Given** a completed decommission, **When** its receipts are checked, **Then** source sits under /opt/archived, spec/PORTS/catalog/audit rows are reconciled, and a memory record distinguishes archived-source from dead-service (commands/_sources/fabrik-decommission.md:1).
- **Given** an operator-run `fabrik apply`, **When** `/fabrik-deploy-verify` runs, **Then** DNS-vs-siblings, health/readiness, registrar outcomes, Gatus state, and a log scan each get a PASS/FAIL verdict with evidence (commands/_sources/fabrik-deploy-verify.md:1).
- **Given** a healthy-looking deploy with a FEATURES.md, **When** deploy-verify's smoke runs, **Then** the top user journeys from FEATURES rows are exercised against the LIVE service (commands/_sources/fabrik-deploy-verify.md:1).
- **Given** a synced-file defect found in a project, **When** `/fabrik-upstream` (project mode) runs, **Then** it produces a verifiable proposal (evidence, computed numbers, proposed diffs, why-filed-not-fixed) without touching the synced file (commands/_sources/fabrik-upstream.md:1).
- **Given** an upstream proposal, **When** `/fabrik-upstream` (hub mode) runs, **Then** every claim is independently re-verified before any edit, and the reply names what landed vs deferred (commands/_sources/fabrik-upstream.md:1).
- **Given** a user prompt matching a pipeline stage, **When** the router hook fires, **Then** it injects a directive-with-escape ("matches /fabrik-X — invoke it or state why not") naming the matched stage (.claude/hooks/skill_router.py:1).
- **Given** a prompt matching nothing, an explicit /command, or any internal error, **When** the hook fires, **Then** it stays SILENT — fail-open, no injection, never blocks (.claude/hooks/skill_router.py:1).
- **Given** a Turkish or paraphrased English prompt, **When** the regex tier misses, **Then** the Haiku tier classifies it (claude -p, hard timeout, empty-on-error) (.claude/hooks/skill_router.py:1).
- **Given** the 7 design/contract/plan skill descriptions, **When** T06a lands, **Then** each carries a TRIGGER clause with concrete bare-prose phrasings and exactly one Stage: value (commands/_sources/fabrik-spec.md:2).
- **Given** the 13 build/certify/release/gate/utility skill descriptions, **When** T06b lands, **Then** each carries a TRIGGER clause with concrete bare-prose phrasings and exactly one Stage: value (commands/_sources/fabrik-review.md:2).
- **Given** a fresh session reading CLAUDE.md, **When** Orient runs, **Then** step 0 routes the task to a matching skill BEFORE work starts, with the stage table inline (CLAUDE.md:9).
- **Given** the pipeline's stage→artifact map, **When** T08's audit runs, **Then** the spine Evidence records the full table and the top TWO unguarded stages gain gate checks with red-on-revert tests (scripts/enforcement/check_stage_artifacts.py:1).
- **Given** all tickets merged, **When** T99 runs, **Then** 24 commands + 24 skills render with `--check` clean, parity + Stage seam tests pass (roster probe: 23 fabrik-prefixed), doc receipts and the full Tier-2 gate are green (commands/assemble_commands.py:1).
- **Mocked:** nothing — real renders, real gate runs, real fixtures under tmp_path; the Haiku tier is tested with a stubbed subprocess (never a live billable call in tests).

## Global Constraints

- **Stage taxonomy (frozen):** `1-design | 2-contract | 3-plan | 4-build | 5-certify | 6-release |
  gate | utility` — exactly one per skill description, format `Stage: <value>` on its own sentence.
  No command renames — the DAG forbids queue numbers (operator decision 2026-08-07).
- **Router semantics:** directive-with-escape, injected as context, NEVER blocking; regex tier
  first (bilingual keyword map), Haiku tier (`claude -p`, ≤8s timeout) only on regex miss;
  fail-open on every error; explicit `/command` prompts and non-fabrik cwds are exempt.
- Never-Route: scripts/enforcement/
- Never-Route: .claude/hooks/
- Never-Route: commands/_sources/
- Never-Route: CLAUDE.md
- Never-Route: AGENTS-compact.md
- Never-Route: scripts/fabrik_synced_manifest.py
- All tickets `Complexity: native` or `never-route` accordingly — an all-native cycle: **NO-POOL:
  every surface is prompt-governance or enforcement (62:118-120)**.
- New command sources follow `docs/reference/MD/ai-prompt-templates.md` (Part A shape, Part B
  agentic patterns incl. termination contract + evidence-before-assertion, Part C markdown) and
  ship WITH their TRIGGER + `Stage:` from birth.
- Commit per ticket: explicit pathspecs + trailers (`Agent-Task: T##`); CHANGELOG/INDEX rows flow
  through `## Deltas` — governance files never in Touches.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `commands/assemble_commands.py` | NEXT map + PARAMS shapes + render/--check; one entry per new command | `commands/assemble_commands.py:40-48,177-190` |
| `commands/_sources/fabrik-doc-converge.md` | the freshest command-authoring exemplar (contract table, exclusions, fragments) | `commands/_sources/fabrik-doc-converge.md:1-78` |
| `.claude/hooks/final_gate_stop.py` | the hook idioms to reuse: stdin JSON contract, fail-open, counters, tests style | `.claude/hooks/final_gate_stop.py:101-140` |
| `.claude/settings.json` | hook wiring shape (SessionStart/Stop today; UserPromptSubmit added by T05) | `.claude/settings.json:1-30` |
| `scripts/fabrik_synced_manifest.py` | AGENT_HOOK_FILES sync block — T05 adds the router beside it | `scripts/fabrik_synced_manifest.py:87-98` |
| `scripts/fleet_doc_audit.py` | catchup's mechanical measurement layer (probes + report) | `scripts/fleet_doc_audit.py:1-60` |
| retirement lessons | archived-source ≠ dead-service; liveness by DNS-vs-siblings probe; port registry; consumer env sweep | `CHANGELOG.md` 2026-08-07 retirement + review entries |
| upstream exemplar | the trade-intelligence proposal format + hub verify-then-apply ritual | `/opt/trade-intelligence/docs/reference/upstream-proposals/2026-08-05-*.md` |
| `docs/reference/MD/ai-prompt-templates.md` | command-authoring contract (Parts A–C) | pack §A–C |
| skill descriptions today | 20 sources' frontmatter `description:` (incl. non-prefixed design-review) — T06a/T06b's sweep surface | `commands/_sources/*.md:2` |
| `CLAUDE.md` Orient | step-0 insertion point (heading :9, items :10-14 — insert after :9); § Pipeline stage flow | `CLAUDE.md:9-14,§ Pipeline` |
| stage-artifact precedents | EXECUTED-needs-review (check_convergence), release-needs-certification (fabrik-release § precondition) | `scripts/enforcement/check_convergence.py:418-470` |

## File Scope (owned paths)

- commands/_sources/fabrik-catchup.md
- commands/_sources/fabrik-decommission.md
- commands/_sources/fabrik-deploy-verify.md
- commands/_sources/fabrik-upstream.md
- commands/assemble_commands.py
- commands/_sources/fabrik-spec.md
- commands/_sources/fabrik-spec-review.md
- commands/_sources/fabrik-data-contract.md
- commands/_sources/fabrik-ui-design.md
- commands/_sources/fabrik-ui-design-review.md
- commands/_sources/fabrik-plan-after-chat.md
- commands/_sources/fabrik-plan-review.md
- commands/_sources/fabrik-execute-plan.md
- commands/_sources/fabrik-review.md
- commands/_sources/fabrik-repo-review.md
- commands/_sources/fabrik-rules-review.md
- commands/_sources/fabrik-generate-tests.md
- commands/_sources/fabrik-docs-review.md
- commands/_sources/fabrik-doc-converge.md
- commands/_sources/fabrik-features.md
- commands/_sources/fabrik-user-test.md
- commands/_sources/fabrik-service-test.md
- commands/_sources/fabrik-release.md
- commands/_sources/fabrik-workflow-review.md
- commands/_sources/design-review.md
- .claude/hooks/skill_router.py
- .claude/settings.json
- tests/test_skill_router_hook.py
- scripts/fabrik_synced_manifest.py
- CLAUDE.md
- AGENTS-compact.md
- scripts/enforcement/check_stage_artifacts.py
- scripts/enforcement/check_convergence.py
- scripts/final_gate.py
- tests/enforcement/test_check_stage_artifacts.py
- docs/development/plans/2026-08-07-plan-1-autotrigger-and-commands/2026-08-07-plan-1-autotrigger-and-commands.md
- docs/development/reviews/2026-08-07-plan-1-autotrigger-and-commands-review.md
- docs/reference/receipts-2026-08-07-autotrigger.md

## Evidence

Command/skill parity verified at grounding time: assembler output "rendered 20 commands + 20
skills", `--check` OK (the 19 count is the narrower `fabrik-*` glob — design-review is the 20th). Hook contract proven live twice this week
(`.claude/hooks/final_gate_stop.py` — stdin JSON incl. `transcript_path`, fail-open, 22 tests).
Sync path for hooks proven: `scripts/fabrik_synced_manifest.py:96`. Catchup's measurement layer
live: `scripts/fleet_doc_audit.py` (44 scanned / 38 flagged, report committed). The four commands'
motivating incidents are all in `CHANGELOG.md` [Unreleased] entries of 2026-08-05..07.

```
$ python commands/assemble_commands.py --check
check OK — installed commands + skills match rendered sources
```

## Self-audit

- The set encodes only decisions the operator made or confirmed in-conversation (stage taxonomy,
  no renames, router semantics, the four commands, build order); nothing here required fresh
  external grounding — `/fabrik-spec` deliberately skipped (operator-ratified routing).
- Ticket disjointness: the only shared file is `commands/assemble_commands.py` (T01–T04),
  licensed by six Serialized rows (all C(4,2) pairs); fabrik-release.md's T03/T06b share has its
  own row; every other Touches set is disjoint (verified by inspection; `check_plan_tickets --plan-dir` is the mechanical gate).
- Risk register: T05's Haiku tier adds a per-prompt subprocess — bounded by regex-first + 8s
  timeout + fail-open; T08 is the least pre-specified ticket — bounded by the top-2-gaps rule and
  pre-granted File Scope; quota — all-native cycle acknowledged (NO-POOL).
