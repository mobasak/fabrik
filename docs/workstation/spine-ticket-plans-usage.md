# Spine+Ticket Plans — Operator Usage Guide

What the 2026-08-04 plan-architecture wave shipped, what it means for day-to-day work, and how to
run it. Shipped by `2026-08-04-plan-1-spine-ticket-plans` (archived; review artifact:
`docs/development/reviews/2026-08-04-plan-1-spine-ticket-plans-review.md`).

---

## The one-sentence version

Plans can now be **directories of tickets** instead of one giant file, all three pipeline commands
(`/fabrik-plan-after-chat` → `/fabrik-plan-review` → `/fabrik-execute-plan`) understand that shape
end-to-end, and a real gate (`scripts/enforcement/check_plan_tickets.py`, 180 tests across the
plan-gate suites) enforces the grammar — not prose.

## What you type — unchanged

The pipeline is the same three commands in the same order. Nothing new to memorize:

| Step | Command | What's new inside |
|---|---|---|
| 1 | `/fabrik-spec` → `/fabrik-spec-review` | unchanged |
| 2 | `/fabrik-plan-after-chat` | **decides the plan's SHAPE itself** (see below) |
| 3 | `/fabrik-plan-review` (auto-invoked) | reviews a whole SET as one unit when given a set |
| 4 | `/fabrik-execute-plan <file-or-dir>` | **dispatcher mode** for sets; classic phase mode for monoliths |

## The shape decision (automatic, in step 2)

- **Small work** (≤3 phases, ≤~300 lines, every phase's read-set within budget) → today's single
  monolith file. Nothing changes.
- **Big work** → a **plan set**: `docs/development/plans/YYYY-MM-DD-plan-<n>-<slug>/` containing
  - the same-stem **spine** — Ticket Board (⬜🔵🟡✅🔴 state), Merge Order (+ `Serialized:` barriers,
    direction per Merge-Order position), Interfaces (consumer-owned seam tests), roll-up Behavior
    Contract, Global Constraints (incl. `Never-Route:`), File Scope;
  - one **ticket per work unit** — `T##[a-z]?-<slug>.md`, each a self-contained cold-start brief:
    `## Scope` + DO-NOT, `## Touches` (its EXCLUSIVE write-set), `Depends:` / `Parallel:` /
    `Complexity:` / `Docs:` / `Gate:`, `## Behavior Contract` (≤8 G/W/T), `## Context Files`
    (everything a cold coder reads — the read-set rule), ≥1 `path:line` citation;
  - exactly one `Integration: true` ticket, last in Merge Order, `Complexity: native` — it owns the
    whole-plan receipts (doc-sync ranges, `/fabrik-docs-review`, `/fabrik-features`, seam-test run,
    final gate).

Sizing is computed (READ-budget bytes), and tickets that pass the budget but fail the author's
isolation simulation get split (`T05a`/`T05b`).

## Review of a set (step 3)

Point it at the directory, the spine, or any single ticket — the review unit is always the WHOLE
set. Anti-cheat is the combined directory hash per pass; convergence is preconditioned on
`python -m scripts.enforcement.check_plan_tickets --plan-dir <dir>` (repo root) exiting 0; the
`CONVERGED` flip re-runs the same contract in-process.

## Execution of a set (step 4 — dispatcher mode)

You invoke it once; the orchestrator then:

1. flips the spine `CONVERGED → IN-PROGRESS` on the first dispatch commit;
2. dispatches up to **3 coders** in parallel (Merge-Order tie-break) — pool units for
   `simple`/`complex` tickets, native Claude for `native`/`never-route`;
3. reviews EVERY returned ticket to a clean round before merge (per-round floor: 2–3 pool finders +
   exactly 1 native Opus; secrets-touching diffs native-only);
4. merges in Merge Order — code + Board flip + CHANGELOG/INDEX/LESSONS deltas in ONE commit per
   ticket under its full-ID `Agent-Task:` trailer (coders never touch governance files; they emit
   `## Deltas` blocks the orchestrator applies);
5. runs the Integration ticket, then one whole-plan validation to `found: 0, fixed: 0`;
6. flips `EXECUTED` (must cite the whole-plan validation review — gate-enforced; a per-ticket
   review never satisfies it), releases the lock, archives the **whole directory** to
   `docs/development/plans/archived/<dir>/`.

**Resumability:** the Board + per-ticket lock registry (`tickets:` map in
`.fabrik/plan-locks/<id>.json`) are the durable state. A crashed/quota-killed run resumes with a
salvage sweep; a quota-exhausted native call PAUSES the plan (lock `status: "paused"`) rather than
thinning the review floor. Terminal red tickets → spine `BLOCKED`, lock retained with `owned_paths`
cleared; your ruling re-dispatches (`BLOCKED → IN-PROGRESS`).

## What this buys

- **No more monolith-context blowups** — each ticket executes cold within a computed read budget.
- **Safe parallelism** — exclusive Touches ownership is gate-ERRORed; the rare shared file needs an
  explicit `Serialized:` licence row.
- **Governance files can't collide** — CHANGELOG/INDEX/docs README/FEATURES/LESSONS_LEARNT are
  banned from Touches and File Scope (locking CHANGELOG would make any two concurrent plans block).
- **"Done" is mechanical** — `EXECUTED` without an on-disk, coverage-adjudicated whole-plan review
  fails the gate.

## Existing plans — what to do with them

**Nothing retroactive is required.** Both shapes are first-class:

- **Archived plans** — leave untouched; every gate exempts `plans/archived/**`.
- **Active monolith plans already CONVERGED or IN-PROGRESS** — finish them as monoliths; phase mode
  is unchanged and fully supported.
- **A monolith still at DRAFT that is genuinely big** — re-run `/fabrik-plan-after-chat` on it; the
  shape decision will re-emit it as a set (the monolith file is superseded and archived by the
  normal flow).
- **Legacy/pre-pipeline plans** — grandfathered: the quality gate WARNs instead of ERRORing on
  plans that predate the pillar sections; don't retrofit them.

## Where things are

| Thing | Path |
|---|---|
| The gate | `scripts/enforcement/check_plan_tickets.py` (+ `check_plan_quality`, `check_convergence`) |
| CLI | `python -m scripts.enforcement.check_plan_tickets --plan-dir <dir>` (repo root) |
| Command sources | `commands/_sources/fabrik-{plan-after-chat,plan-review,execute-plan}.md` (render: `python commands/assemble_commands.py`) |
| Allowlist | `CLAUDE.md` § HARD STOPS new-`.md` row (spine+ticket dir shape included) |
| The shipped wave | CHANGELOG 2026-08-05 entries (Phases A–E + Finish) · Lesson 103 |
