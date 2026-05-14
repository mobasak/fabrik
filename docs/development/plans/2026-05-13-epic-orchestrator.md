# Plan: Epic Orchestrator — Traycer-Plan-Driven Ticket Executor

**Status:** Designed, not started
**Estimated effort:** ~13 hours (~1.5 focused days)
**Owner:** Özgür (solo)
**Created:** 2026-05-13
**Related infra:** `scripts/kilo-benchmarks/`, `scripts/kilo_auto_route.py`, `scripts/classify_ticket.py`, `scripts/kilo_telemetry.py`

---

## Executive Summary

Build a deterministic Python orchestrator that reads a Traycer-generated epic
folder (tickets/ + specs/Epic_Brief.md), parses each ticket's `## 🤖 Agent
Briefing` block, and executes the per-ticket pipeline
(code → gate → review → fix → docs → stage) across configurable parallel
workers in git worktrees. Traycer decides the parallelism + execution order;
the orchestrator parses and executes.

Reuses every piece of existing infrastructure (classifier, role selector,
floors, telemetry, AA-throughput data, the cheapest-above-floors selector).
Adds one new SQLite table (`ticket_phases`) and seven new Python files.
Supports two backends: Kilo CLI (default) and Claude Code (WSL `claude`).
Windsurf Cascade / SWE tickets are explicitly skipped — those are manual.

---

## Design priorities (in pinned order)

1. **Accurate** — broken merged code costs more than slow code. Pre-flight
   checks before dispatch, both gates between phases (`final_gate.py` +
   ticket-specific verification command), mandatory review for
   HIGH/CRITICAL/DESTRUCTIVE tickets, same-family guard on reviewer,
   3-iteration fix loop with promote-to-human-review on max.
2. **Parallel** — wave-based scheduling from Traycer's plan;
   ThreadPoolExecutor for parallel tickets; git worktree per worker for
   isolation. Destructive tickets serialize automatically.
3. **Cost** — hybrid agent selection: respect operator's briefing first,
   classifier fallback. Per-ticket cost cap with circuit-breaker.
   `coding_simple` for low-complexity tickets.
4. **Fast** — pipeline parallelism (docs N || code N+1) deferred to v2.
   v1 keeps within-ticket phases sequential, parallelism only across tickets.

---

## Key Invariants

These hold at runtime and must not be silently violated:

1. **Briefing model > classifier model.** When a ticket has an Agent Briefing
   `**Assigned Model:**` field, the orchestrator uses it. Classifier runs in
   parallel only for divergence logging. Operator's manual judgement wins.

2. **Backend defaults to Kilo.** Unless a ticket's Agent Briefing carries an
   explicit `**Backend:** claude-code` (or `cascade-manual`), dispatch goes
   through `kilo_auto_route.py`. Cascade-manual tickets are skipped with a
   summary line; orchestrator does not try to execute them.

3. **Cost-monotonic priority assignments are respected.** When the
   orchestrator escalates a coder priority on retry (P1 fails → P2), the new
   pick costs more, never less. Enforced by the existing selector invariant.

4. **Same-family guard on reviewer.** For reviewing role, the orchestrator
   always passes `--exclude-provider <coder.provider>` so coder and reviewer
   come from different families. Falls through to cheapest qualified if no
   alternate exists; resolution reason recorded in telemetry.

5. **Never commit without operator request.** Per CLAUDE.md, the orchestrator
   stages changes (`git add`) but never runs `git commit` or `git push`.
   Operator reviews + commits manually. Worker worktrees merge back to main
   with staged changes only.

6. **Resumable on crash.** `ticket_phases` rows are written at each phase
   boundary. `--resume` reads existing completed rows, skips them, picks up
   from the next pending phase. No double-billing on restart.

7. **Telemetry rows exist for every dispatch.** `ticket_outcomes` (per-ticket
   summary) and `ticket_phases` (per-phase detail) are both written.
   Standalone audit query in `kilo_telemetry.py` reads them.

8. **Worktree isolation prevents cross-ticket contamination.** Parallel
   workers operate in disjoint `/tmp/orch-wt-<ticket_id>` worktrees. Final
   merge to main happens only after all parallel tickets in a wave complete.
   Merge conflicts halt the epic and require operator resolution.

---

## Architecture

```
epic_orchestrate.py <epic_path>
        │
        ▼
   ┌─ Read brief.md → extract "Execution sequence (final):" waves ──┐
   │    Day 1: T1-03                                                 │
   │    Day 1-2: T1-02 + T1-01                                       │
   │    Day 3 PM: T1-05 (destructive evening window)                 │
   │    Days 4-6: T2-01 → T2-02 → T2-03/04 + T3-01/02/03 (parallel) │
   │    ...                                                          │
   └─────────────────────────────────────────────────────────────────┘
        │
        ▼
   ┌─ For each ticket: parse Agent Briefing ────────────────────────┐
   │    • Assigned Model (e.g. "Opus 4.7")                          │
   │    • Backend (default Kilo; "claude-code" if specified)        │
   │    • Complexity class (HIGH / CRITICAL DESTRUCTIVE / ...)      │
   │    • Files to TOUCH (anchors + paths)                          │
   │    • DONE criteria (acceptance commands)                       │
   │    • Stop conditions (halt rules)                              │
   │    • Final verification command (gate)                         │
   └────────────────────────────────────────────────────────────────┘
        │
        ▼
   ┌─ Execute waves ────────────────────────────────────────────────┐
   │  For each wave:                                                │
   │    • Split into [parallel] and [destructive] tickets           │
   │    • Parallel: ThreadPoolExecutor, git worktree per ticket     │
   │    • Destructive: sequential, full-auto (trust Stop conditions)│
   │    • Each ticket runs the 7-phase pipeline below               │
   │  ticket_phases updated; executions/<ticket_id>/ artifacts      │
   └────────────────────────────────────────────────────────────────┘
        │
        ▼
   Epic summary: total cost, per-ticket status, failures
```

### Per-ticket 7-phase pipeline

```
0. Setup       — create worktree, resolve backend+model, skip cascade-manual
1. Pre-flight  — run Pre-flight checklist commands, verify outputs
2. Code        — dispatch via backend with ticket body + project rules
3. Gate 1      — final_gate.py --lean --json
4. Gate 2      — ticket's Final self-verification command
5. Review      — for HIGH/CRITICAL only; same-family guard reviewer
6. Fix loop    — max 3 iters; re-runs gates after each; promotes to
                 NEEDS_HUMAN_REVIEW on exhaustion
7. Docs        — documentation role; updates CHANGELOG + relevant docs
8. Stage       — worker worktree merges back, changes git add-staged
                 (NEVER committed), summary written, worktree cleaned
```

---

## Failure Modes

Each mode + its recovery path:

| Mode | Trigger | Recovery |
|------|---------|----------|
| Coder dispatch fails | Backend error (Kilo timeout, network, rate-limit) | Retry next priority (P2, P3); after 3 priorities → mark `TICKET_FAILED`, continue epic |
| Pre-flight check fails | Pre-flight command returns non-zero or wrong output | Halt that ticket → mark `NEEDS_HUMAN_REVIEW`, continue epic |
| Gate 1 / Gate 2 fails | `final_gate.py` or ticket verification fails | Enter Fix loop with error context; max 3 iters |
| Fix loop exhausted | 3 iterations and still failing | Mark `NEEDS_HUMAN_REVIEW`, continue epic |
| Review verdict = FAIL | Reviewer judges fundamentally wrong | Halt ticket, mark `NEEDS_HUMAN_REVIEW`, continue |
| Cost cap exceeded | Per-ticket spend > `--budget-cap-per-ticket` | Pause that ticket, alert operator, await `--continue-anyway` |
| Worktree merge conflict | Two parallel tickets touched overlapping files | Halt the failing merge, mark ticket `MERGE_CONFLICT`, continue others |
| Briefing model not in DB | Resolved to `None` after fuzzy match | Log warning, fall back to classifier (per Hybrid policy) |
| Cascade-manual ticket | Backend = `cascade-manual` | Skip with summary line; operator handles manually |
| Orchestrator crash | OOM, OS kill, etc. | `--resume` reads `ticket_phases`, skips completed phases, picks up |
| Epic-wide failure rate >30% | 30%+ of tickets marked failed/needs-review | Halt remaining tickets, alert operator, await direction |

---

## Acceptance Criteria

The v1 build is **DONE** when all 8 hold against the
`/tmp/traycer-epics/7a3f1e1b-...-Epic_Files_Corruption_Recovery_Request/`
epic in `--dry-run` mode (real run requires operator approval):

1. **Plan parsing.** `python epic_orchestrate.py <epic> --dry-run` parses all
   17 tickets without error, prints a structured plan showing: each ticket's
   id, title, backend, model, complexity, destructive flag, dependencies, and
   wave assignment. Output deterministic across runs.

2. **Briefing extraction accuracy.** For T1-02, the extracted model is
   `Opus 4.7`; for T1-05, the destructive flag is `true` and complexity is
   `CRITICAL DESTRUCTIVE`. Cross-check via grep on the source ticket file.

3. **Wave order matches brief.** The execution plan emitted by `--dry-run`
   matches the brief's `Execution sequence (final):` block (Day 1 T1-03 →
   Day 1-2 T1-02+T1-01 parallel → Day 2 T1-04 → ...). No tickets misplaced.

4. **Hybrid agent selection logs divergence.** For at least one ticket where
   classifier picks differently from briefing, the dry-run output shows a
   `[divergence]` line citing both picks. This proves the hybrid logic runs.

5. **Cascade-manual skip.** If a synthetic test ticket is added with
   `**Backend:** cascade-manual`, the dry-run plan marks it `SKIP_MANUAL`
   and does not include it in any wave's execution list.

6. **`ticket_phases` schema applied.** Running the orchestrator at least
   once creates the `ticket_phases` table with the documented columns. The
   audit query `python kilo_telemetry.py 30` does not error.

7. **Determinism.** Two `--dry-run` invocations produce byte-identical
   plan output (excluding timestamps).

8. **Doc updated.** A new `## Epic Orchestrator` section in
   `docs/workflows/KILO_AGENT_MANAGEMENT.md` documents the orchestrator,
   per-ticket pipeline, ticket_phases schema, and `--dry-run` / `--resume`
   / `--interactive` flags.

---

## File Inventory

### New files (~1050 LoC)

| Path | LoC | Responsibility |
|------|----:|----------------|
| `scripts/epic_orchestrate.py` | 150 | CLI entry, top-level loop, summary writer |
| `scripts/epic_ticket_parser.py` | 220 | Parse frontmatter + Agent Briefing → structured Ticket |
| `scripts/epic_plan_reader.py` | 80 | Parse brief's `Execution sequence` → waves |
| `scripts/epic_pipeline.py` | 280 | Per-ticket 7-phase loop |
| `scripts/epic_state.py` | 150 | `ticket_phases` SQLite + resume + worktree lifecycle |
| `scripts/epic_backend_kilo.py` | 70 | Wraps `kilo_auto_route.py` |
| `scripts/epic_backend_claude.py` | 100 | Wraps `claude -p --output-format json` |

### Existing-file modifications (~60 LoC)

| Path | Δ LoC | What |
|------|------:|------|
| `scripts/kilo-benchmarks/kilo_telemetry.py` | +50 | Add `ticket_phases` table schema + `start_phase()` / `complete_phase()` helpers |
| `scripts/kilo_auto_route.py` | +10 | Add `--phase` and `--epic-id` flags for telemetry labeling |

### Artifacts produced per ticket

```
<epic>/executions/<ticket_id>/
├── 01-preflight.log
├── 02-code-output.txt          (raw model output)
├── 02-code.patch               (git diff after Phase 2)
├── 03-gate1.log                (final_gate.py output)
├── 04-gate2.log                (ticket-specific verification)
├── 05-review.json              (reviewer verdict + findings)
├── 06-fix-iter-N.patch         (one per fix iteration)
├── 07-docs.patch
└── summary.md                  (per-ticket rollup)
```

Plus `<epic>/executions/epic_summary.md` — total cost, success rate, failures.

---

## `ticket_phases` Schema

```sql
CREATE TABLE ticket_phases (
    epic_id      TEXT NOT NULL,
    ticket_id    TEXT NOT NULL,
    phase        TEXT NOT NULL,        -- 'preflight'|'code'|'gate1'|'gate2'|'review'|'fix'|'docs'|'stage'
    iteration    INTEGER DEFAULT 1,    -- review/fix loop counter
    backend      TEXT,                 -- 'kilo' | 'claude-code'
    agent_used   TEXT,                 -- e.g. 'kilo/anthropic/claude-opus-4.7'
    cost_usd     REAL,
    duration_s   REAL,
    status       TEXT,                 -- 'pass'|'fail'|'needs_fix'|'error'|'skipped'
    artifact     TEXT,                 -- path to phase output file
    started_at   TIMESTAMP,
    completed_at TIMESTAMP,
    PRIMARY KEY (epic_id, ticket_id, phase, iteration)
);
CREATE INDEX idx_phases_epic ON ticket_phases(epic_id);
CREATE INDEX idx_phases_status ON ticket_phases(status);
```

---

## CLI Surface

```bash
# Preview the plan, no dispatch
python scripts/epic_orchestrate.py /tmp/traycer-epics/<id> --dry-run

# Real run
python scripts/epic_orchestrate.py /tmp/traycer-epics/<id>

# Pause between phases (operator confirms each)
python scripts/epic_orchestrate.py /tmp/traycer-epics/<id> --interactive

# Resume after crash (reads ticket_phases, skips completed)
python scripts/epic_orchestrate.py /tmp/traycer-epics/<id> --resume

# Tune parallel workers (default 4)
python scripts/epic_orchestrate.py /tmp/traycer-epics/<id> --workers 6

# Per-ticket budget cap (halts ticket if exceeded)
python scripts/epic_orchestrate.py /tmp/traycer-epics/<id> --budget-cap-per-ticket 5.00
```

---

## Execution Order (when green-lit)

1. **DB schema migration** (~30 min) — add `ticket_phases` table, update `kilo_telemetry.py` helpers
2. **Parsers** (~3 hr) — `epic_ticket_parser.py` + `epic_plan_reader.py`; tested against the 17-ticket epic
3. **Backend abstraction** (~2 hr) — `epic_backend_kilo.py` wraps existing dispatcher; `epic_backend_claude.py` is new (needs one manual `claude -p --output-format json` verification first)
4. **State + worktree** (~2 hr) — SQLite, worktree create/merge/cleanup, resume logic
5. **Pipeline** (~3 hr) — the 7-phase per-ticket loop
6. **CLI + summary** (~1 hr) — top-level coordinator, summary writer
7. **Dry-run validation** (~1 hr) — point at the 17-ticket epic, verify plan output
8. **Doc update** (~30 min) — `KILO_AGENT_MANAGEMENT.md` Orchestrator section

**Total: ~13 hours.** Realistic for 1.5 focused days.

---

## Risks (deferred for build-time resolution)

1. **Claude Code CLI specifics unverified.** I'm assuming
   `claude -p "prompt" --output-format json` produces parseable output with
   cost. If the actual CLI differs, the Claude backend parser needs
   adjustment. **Mitigation:** verify with one real `claude -p
   --output-format json` invocation before locking the backend.

2. **Files-to-TOUCH parser must handle anchors, not just paths.** Tickets
   reference files via drift-resistant string anchors (e.g.,
   `shutil.copy(fabrik_compact, project_dir / "AGENTS-compact.md")`). Parser
   extracts both anchor + path; pipeline passes both to the coder.

3. **Sub-ticket dependencies are NOT supported in v1.** Brief says
   "T1-02 + T1-01 (parallel after T1-02 G-B1a lands)". v1 treats this as
   "parallel after T1-02 completes" — operator-acceptable degradation.
   v2 could add `**Depends on:** T1-02@G-B1a` syntax.

4. **`final_gate.py` must run inside each worker's worktree.** Multi-worker
   parallelism + `final_gate.py` running against `/opt/fabrik` would race.
   Pipeline `cd`s into the worktree before invoking gate1.

5. **Worktree merge conflicts halt the epic.** If two parallel tickets touch
   overlapping files (despite Scope blocks claiming disjoint), the merge
   fails. v1 fails loud; operator resolves. v2 could pre-detect via Scope
   parsing.

---

## What's deferred to v2

- Pipeline parallelism (docs of ticket N runs alongside code of ticket N+1)
- Sub-ticket dependency syntax
- Cost prediction before dispatch
- Auto-merge worktree conflict resolution
- Per-epic cost dashboard UI
- Slack/email/Telegram notification channels

---

## Dependencies

This plan reuses (does not modify):

- `scripts/kilo-benchmarks/classify_ticket.py` — Phase 0 role selection
- `scripts/kilo-benchmarks/db_models.py` — `get_model_for_priority`, `get_model_avoiding_provider`
- `scripts/kilo_auto_route.py` — Phase 2/5/6 dispatch (via `epic_backend_kilo.py`)
- `scripts/final_gate.py` — Phase 3 gate
- `scripts/kilo-benchmarks/kilo_telemetry.py` — telemetry + cost parsing (extends with `ticket_phases`)

External tools required:

- `kilo` CLI in PATH (for KiloBackend)
- `claude` CLI in PATH (for ClaudeCodeBackend) — optional
- `git` 2.5+ (for worktree support)
- SQLite 3.x (already in `kilo_agents.db`)

---

## Final Self-Verification Command

When v1 implementation is complete, this command should pass:

```bash
cd /opt/fabrik && \
python scripts/epic_orchestrate.py /tmp/traycer-epics/7a3f1e1b-b602-4fd3-a4ba-d419d8a062dd-Epic_Files_Corruption_Recovery_Request --dry-run > /tmp/epic_dry_run_1.txt 2>&1 && \
python scripts/epic_orchestrate.py /tmp/traycer-epics/7a3f1e1b-b602-4fd3-a4ba-d419d8a062dd-Epic_Files_Corruption_Recovery_Request --dry-run > /tmp/epic_dry_run_2.txt 2>&1 && \
diff <(grep -v "generated_at" /tmp/epic_dry_run_1.txt) <(grep -v "generated_at" /tmp/epic_dry_run_2.txt) && \
echo "DETERMINISTIC ✓" && \
grep -c "^TICKET " /tmp/epic_dry_run_1.txt | grep -q "^17$" && \
echo "17 TICKETS PARSED ✓" && \
sqlite3 scripts/kilo-benchmarks/kilo_agents.db "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='ticket_phases';" | grep -q "^1$" && \
echo "ticket_phases TABLE EXISTS ✓"
```

All three lines must print.

---

## One-Test Rule

**Why:** The epic orchestrator runs 17 tickets across 4 tiers, parses Traycer-emitted markdown into a deterministic execution plan, and dispatches each ticket to the appropriate coder backend with retry / cost / phase telemetry. The plan's single highest-risk path is **deterministic parsing of the epic bundle**: if the same input bundle produces different orchestration plans on two consecutive `--dry-run` invocations, the entire campaign loses reproducibility (a fix-and-retry on ticket N could see ticket N-1 land at a different phase or with a different agent). One test that pins this contract is the minimum line of defense.

**Contract:**

- **Given:** the on-disk epic bundle at `/tmp/traycer-epics/7a3f1e1b-…-Epic_Files_Corruption_Recovery_Request/` with 17 ticket markdown files in `tickets/`.
- **When:** `python scripts/epic_orchestrate.py <bundle> --dry-run` is invoked twice in succession, capturing each run's stdout to a separate file.
- **Then:** `diff` of the two stdout captures (after stripping the `generated_at:` timestamp line) returns zero differences; the line `^TICKET ` appears exactly 17 times in each capture; the `ticket_phases` table exists in `scripts/kilo-benchmarks/kilo_agents.db`.
- **Mocked:** none — uses real SQLite + real file I/O. No live backend dispatch (the orchestrator's `--dry-run` flag short-circuits before any `kilo` / `claude` CLI invocation, so no network / no LLM cost).
