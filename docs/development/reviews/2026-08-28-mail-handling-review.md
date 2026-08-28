# /fabrik-review — this session's mail-handling work (13 commits)

Status: CLOSED — coverage-adjudicated exit; Pass 3 returned `new: 0` with every candidate adjudicated

**Surface:** `HEAD f273064c41f87c9989b0f51e3f1c3af891ba66b1` · working-tree diff md5 `00987b4b4ced8f1245c663a15c2c1d6e`

**Commits under review (MINE only — the log range also carries sibling commits I did not author:
`3dfd3e70`/`830bb03d`/`81596907` flywheel, `6916ebb3` Lesson 138, and `f273064c`, which is FLEET
picking up the GlitchTip scaffold half I routed to them):**
`50f009a3` · `be3766e1` · `b64f10b8` · `f6810ca6` · `12123194` · `257f2fc3` · `ca6323a7` ·
`917608b2` · `873598cf` · `89b0fd00` · `7cc04941` · `8a943ef9` · `aa5935d3`

**Finders.** Native orchestrator only. `NO-POOL: operator standing directive — no subagent or pool
dispatch for hub work.`

**What makes this surface risky.** Nine of the thirteen commits change **governance-synced** files
(both constitutions, five rule packs, four enforcement checks) — they are live in ~46 repos on the
pre-commit sync. Three add BLOCKING findings to gates other repos must pass. One is a policy the
operator set that now binds every new project.

## Rubric

`python scripts/review_rubric.py --changed <10 representative paths>` — FLOOR (`core/35-security-auth`,
`core/25-data-postgres`, `core/30-ops`, all twelve 12-Factor axes) + MATCHED (`core/10-python`,
`core/40-documentation`, `core/45-testing-strategy`).

## Coverage Checklist

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | **fail-open vs fail-closed** (standing) | CLEAN | Every new code path probed on hostile/absent input (empty, NUL, 400 backticks, 200 pipes, missing repo): none raises, all return empty. The three new BLOCKING findings return `[]`/`0` where they cannot ask their question. |
| 2 | **cost / quota / limit** (standing) | REFUTED | No metered spend on this surface; the `claude -p` posture is unchanged. |
| 3 | **boundary / sentinel / prefix** (standing) | CLEAN | New regexes exercised against 8 hostile inputs without raising; the display-filter rule distinguishes asserting finals (`grep -q`/`grep -c`/`jq`) from display finals, proven on 6 real shapes. |
| 4 | **behavior-without-a-test** (standing) | CLEAN | **All 12 new behaviours have a test**, including the four WIRING tests added after a call-site mutation slipped past helper-only coverage three times. |
| 5 | new BLOCKING findings — fleet blast radius | CLEAN | Three new BLOCKING findings landed. Executed `check_convergence` in **all four repos with changed plan/review files** (fabrik, fabrik-lib, tojlo-mail, youtube): `rc=0` everywhere — I reddened nobody. |
| 6 | claims made TO filers (did I promise what I shipped?) | CLEAN | **20 of 20 promises made in replies verified against the shipped artifact.** One initially flagged (`step` accepting the D4 ticket artifact) was my over-escaped grep — disproved behaviourally: a `-T02-review.md` satisfies the gate, an unrelated `.md` does not. |
| 7 | rule-pack internal consistency (no pack contradicts another) | CLEAN | Seven rule packs edited. The stale `headless … OUT OF SCOPE` line is gone (0 occurrences); no pack still calls the password pages launch-blocking; `88-saas-launch-checklist` carries no conflicting demand. |
| 8 | beat routing correctness | CLEAN | Every one of the 31 changed paths is inside the infra beat. The GlitchTip scaffold half was reverted and routed to fleet — and `f273064c` in the log is fleet having picked it up. |
| 9 | provenance trailers on every commit | FIXED(1) | 12 of 13 commits carry `Agent-Role: primary` + `Agent-Name: infra`. The one gap (`257f2fc3`) is the disclosed `printf` truncation, already repaired forward by `ca6323a7`, which names the orphaned SHA. |
| 10 | Python discipline (`core/10-python`) | CLEAN | `ruff` clean on all 11 files I touched. The whole-tree 156 live in files I did not touch (sibling WIP). |
| 11 | testing strategy (`core/45-testing-strategy`) | CLEAN | 397 tests green across every suite covering the changed surface. |
| 12 | documentation (`core/40-documentation`) | CLEAN | No heading-level skips introduced — the 2 in `35-security-auth.md` are pre-existing (measured at `7cc04941~1`: 2 before, 2 after). The escaped-pipe table row parses to 7 cells. |
| 13 | Secrets / config (FLOOR 35) | CLEAN | No literal credential added across all `.py`/`.md` diffs. The GlitchTip rule REMOVES secret egress rather than adding config. |
| 14 | Postgres / Docker / 12-Factor (FLOOR 25/30) | REFUTED | No DB, service, container or port on this surface. |
| 15 | corpus / render parity | CLEAN | `assemble_commands.py --check` clean; corpus green across 47 files; doc links 0 broken of 1935. |
| 16 | measurement honesty (blast-radius numbers I published) | FIXED(1) | The wrong `3 hits across 1,134` number is gone from the source and replaced with the corrected `0 live hits` plus the method error. The `6 of 265` narrowing measurement is retained at `check_convergence.py:471-474`. |

## Pass Ledger

| Pass | finders | found | new | fixed |
|---|---|---|---|---|
| Pass 1 (WIDE) | native orchestrator, all 16 classes | 2 | 2 | 1 |
| Pass 2 (SCOPED) | native, the fix diff + its class | 0 | 0 | 0 |
| **Pass 3 (closing FULL sweep)** | native, all 16 classes vs the FINAL state | **0** | **0** | **0** |


## Findings

- **F1 — a BLOCKING enforcement rule shipped with no CHANGELOG entry.** CONFIRMED: `917608b2`
  changed `check_plan_tickets.py` (+ its test) and touched no `CHANGELOG.md`, against the Doc Sync
  Matrix's `Code changed → CHANGELOG.md` and CLAUDE.md § Completion Contract. **FIXED** — entry
  backfilled, naming the commit and the measurement that narrowed the rule.

## Refuted / escalated

- **F2 — the CHANGELOG gate cannot detect a missing entry, which is WHY F1 survived.** CONFIRMED by
  execution: `check_doc_sync._changelog_quality_ok()` asks whether `[Unreleased]` contains *a* `###`
  entry, not whether THIS change added one. Given a CHANGELOG holding only a stale sibling entry it
  returns `True`. On an active shared tree that section is never empty, so a BLOCKING check is
  effectively always green on this axis — contract-vs-grader again.

  **ESCALATED to the operator rather than fixed, because the fix is a governance decision and I
  measured its cost.** Across the last 80 hub commits, **49 touched a `.py` and 12 of them (24%)
  carried no CHANGELOG entry** — mostly OTHER agents' commits (`81596907`, `56beaa0e`, `b151bd7d`,
  `6386c9c5`, `84086154`). Narrowing to non-test production code does not reduce it: still 12.
  So the three options each have a real cost, and none is mine to pick:
  - make it blocking → fails ~1 in 4 code commits fleet-wide on landing (the wolf-crier failure);
  - ship an advisory → a 24% warn rate becomes wallpaper, which the pack itself warns against;
  - soften the rule → a governance change to the Doc Sync Matrix.

  Pre-existing; my work did not introduce it, and F1 is the evidence it is real rather than theoretical.
