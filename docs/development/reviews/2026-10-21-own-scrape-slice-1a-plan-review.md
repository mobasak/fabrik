# Plan review — own scrape tool, slice 1a, hub side (W-10146d20)

**Command:** /fabrik-plan-review
**Plan:** `docs/development/plans/2026-10-21-plan-3-own-scrape-slice-1a.md` (DRAFT at cb5e77346, armed at ded06464e)
**Spec:** `docs/superpowers/specs/2026-10-21-own-scrape-tools-design.md` (CONVERGED, D-1100)
**Shape:** agent-tool (the Workflow tool is never called)
**Status:** IN REVIEW

## Pass Ledger

The plan carries the same ledger in its own § Pass Ledger; this copy is the receipt's.

| Pass | seats · axes re-checked | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (Phases A and C, Global Constraints, Digest, Coverage, Evidence, File Scope) + sonnet×1 (Goal, agreed, Intake, Context Ledger, Phase B, Residual unknowns) · full pass | found: 25, confirmed: 23 (2 duplicates), refuted: 0 | lead executed each claim: a bare GET on :8033 → 406; `emit_mcp_project_config.py:39-46`; `assemble_commands.py:1171`; prototype grader v2; subagent `meta.json` `agentType` | 68dad3bf → e9fcc3f7 |
| Pass 2 | the same seats, each over the pass-1 fix diff + one hop | found: 8, confirmed: 7, own-fix: 5, refuted: 0 | lead executed: grader v3 (16/16 fixtures, 16 corpus lines); spec :217-227 and :245-249; `tests/test_emit_mcp_project_config.py:24/:42/:47`; emitter `:331`/`:334` | e9fcc3f7 → 17da142e |
| Pass 3 | the same seats, each over the pass-2 fix diff + one hop | sonnet: found 0 · opus: pending | — | 17da142e → |

## Findings

| Id | Pass | Anchor | Verdict |
|---|---|---|---|
| sonnet P1 | 1 | Phase B gate — a bare GET expecting 200 | FIXED r1 (MCP `initialize` + `tools/list` probe; a bare GET answers 406) |
| sonnet P2 | 1 | unit `EnvironmentFile=/opt/fabrik/.env` | FIXED r1 (no EnvironmentFile; precedent hardening) |
| sonnet P3 | 1 | venv and unit target `/opt/fabrik` from a worktree | FIXED r1 (pre-merge steps 1-8, post-merge gated steps 9-12) |
| sonnet P4 | 1 | importer discovery missed flat imports | FIXED r1 (regex names `tests/test_rivals_run.py`) |
| sonnet P5 | 1 | Fallback contract absent from the switch | FIXED r1 (table carried; grader) |
| sonnet P6 | 1 | nothing emits `.mcp.json` | FIXED r1 (emitter run, new-session start condition) |
| sonnet P7 | 1 | capability ledger U1-U7 unowned | FIXED r1 (I9, Phase B step 11) |
| sonnet P8 | 1 | rule 57 landing site and PORTS note | FIXED r1 (I10 IN, I11 mailed) |
| sonnet P9 | 1 | re-vendored web_tools lacks `proxy: "basic"` | FIXED r1 (step 2 checks it, mails a gap) |
| opus P-opus-1 | 1 | the server reaches no repo's `.mcp.json` | FIXED r1 (UNIVERSAL6 + D-row + roster + `check_mcp_scope.py`) |
| opus P-opus-2 | 1 | `assemble_commands.py --check` cannot pass before the render | FIXED r1 (temp `--dest` render, `:1171`) |
| opus P-opus-3 | 1 | paragraph rule satisfied by a later or negated pin | FIXED r1 (clause rule, fixtures) |
| opus P-opus-4 | 1, 2 | grader caught 2 of 5 mention spellings | FIXED r2 (five spellings, v3) |
| opus P-opus-5 | 1 | red-on-revert had nothing to revert | FIXED r1 (copy the change into the probe, both halves) |
| opus P-opus-6 | 1 | flat fetch order contradicts the Fallback contract | FIXED r1 |
| opus P-opus-7 | 1 | capability ledger missing | FIXED r1 (duplicate of sonnet P7) |
| opus P-opus-8 | 1 | all-pass decided after the run | FIXED r1 (pre-fixed `expected`, PASS defined, 10-20 URLs) |
| opus P-opus-9 | 1 | Phase C behaviours untested | FIXED r1 (`tests/test_scrape_ledger.py`, fallback grader) |
| opus P-opus-10 | 1 | fetch sentence unquoted, placed in the chain | FIXED r1, r2 (quoted; after the METERED sentence; names the agent) |
| opus P-opus-11 | 1 | transcript harvest not runnable | FIXED r1 (`--harvest` mode, roots, `agentType`) |
| opus P-opus-12 | 1 | rule 57 landing site | FIXED r1 (duplicate of sonnet P8) |
| opus P-opus-13 | 1 | Phase A gate skips the tier-order test | FIXED r1 |
| opus P-opus-14 | 1 | run folder outside the repo | FIXED r1 |
| opus P-opus-15 | 1 | 58-resilience row missing | FIXED r1 |
| opus P-opus-16 | 1, 2 | Digest glob unmatched under the convention | FIXED r2 (a glob `*` is kept) |
| opus P2-opus-1 | 2 | grader fail-open spellings (without, no, stealth, unbalanced backticks, e.g.) | FIXED r2 (v3, 16 fixtures) |
| opus P2-opus-2 | 2 | Phase C Fallback row contradicts spec :219-225 | FIXED r2 (row by row) |
| opus P2-opus-3 / sonnet P2-1 | 2 | emitter test outside scope, cannot fail | FIXED r2 (Touches, File Scope, `:24/:42/:47`) |
| opus P2-opus-4 | 2 | Global Constraints vs the emitter's `/opt` writes | FIXED r2 |
| sonnet P2-2 | 2 | emitter dry-run flag misnamed; `--root /opt` | FIXED r2 (`--check`, operator gate) |
