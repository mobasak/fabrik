# Subagent usage across fabrik commands + enforced flywheel scoring — Design Spec

Status: CONVERGED
Date: 2026-07-08
Converged: 2026-07-08 (/fabrik-spec-review — 5 passes to an edit-free no-op; all path:line citations re-verified against live code, OpenRouter cost grounded via this session's dogfood)

## Goal

Make the OpenRouter subagent **pool** actually get used and its runs actually recorded, across the fabrik
command family — by replacing advisory prose ("native-default, pool gated/Step-3") with (1) a clear
**runtime-per-task rule**, (2) **fleet-synced enforcement** that fails/warns the gate when a pool run isn't
scored + recorded, and (3) **default DSN provisioning** so `record_agent_run` writes without hand-wiring.

**Root cause being fixed:** the pool was built + proven (dogfood 2026-07-08) but never used and never
recorded, because (a) the governance I wrote actively deferred it, (b) prose/memory don't propagate to other
projects or compel behavior, and (c) `SUBAGENT_RUNS_DSN` is unset on WSL dev so `record_agent_run`
fail-opens to `False`.

## The runtime rule (principle)

**Everything decomposable → a subagent. The only question is the runtime:**

- **POOL** (`run_agents`, cheap OpenRouter ≤$1.5/Mtok) → **gradeable text/code fan-out**: review finders,
  repo-review unit reviewers, doc reconcilers, rules-pack auditors, spec/plan research grounders, code
  implementers. **Feeds the flywheel** (`record_agent_run` → `subagent_runs` → `pick_models` learns).
- **NATIVE Claude subagent** → **GUI** (`fabrik-gui`, has `mcpServers: [playwright, shadcn, chrome-devtools]`)
  + the **authoritative/high-risk pass** (`fabrik-reviewer`/Opus on auth/schema/migrations/concurrency) +
  the **orchestrator's decide/refute/merge**. **No flywheel row by nature** — it's always Claude on
  subscription; there is no cheap-model choice to rank. (The pool *can* reach browser MCPs via
  `mcp_allow_unlisted=True` — `mcp_tools.py:370` — but cheap models can't judge UI and Claude-via-OpenRouter
  is per-token expensive, so native `fabrik-gui` is the right tool, not a gap.)

## Per-command runtime map

| Command | Fan-out unit | Runtime | Records? |
|---|---|---|:--:|
| `/fabrik-execute-plan` | implementers | **Pool** (worktree) + native review at phase boundaries | pool: yes |
| `/fabrik-review` | finders | **Pool** finders + native Opus on auth/schema; you decide | pool: yes |
| `/fabrik-repo-review` | 20+ unit reviewers | **Pool** mass fan-out + native on highest-blast-radius | pool: yes |
| `/fabrik-rules-review` | per-pack auditors | **Pool** (read-only) + you merge | pool: yes |
| `/fabrik-spec-review` · `/fabrik-plan-review` | fact / plan grounders | **Pool** (research + `web_tools`) + you merge | pool: yes |
| `/fabrik-docs-review` | reconcilers | **Pool** (`tools_enabled=True`, reads worktree) + native ~20% verify-sample | pool: yes |
| `/fabrik-plan-after-chat` · `/fabrik-data-contract` | `path:line` grounders | **Pool** (`tools_enabled=True` worktree grep) + native ~20% citation verify-sample — **[DECISION, overridable]** | pool: yes |
| `/fabrik-spec` | fact grounders | **Pool** research + native design Q&A | pool: yes |
| `/fabrik-ui-design(-review)` | screens/flows | **Native** `fabrik-gui` (design judgment; browser MCPs) | no |
| *always* | decide/refute/merge, GUI | **You / native** | no |

## Chosen approach — ledger↔db reconciliation check, fleet-synced, warn-then-fail

**A. Flip the governance (`.windsurf/rules/core/62-using-subagents.md`, synced).** Replace "native-default,
pool phased/gated/Step-3, NOT default-on" with the runtime rule above: pool is the **default** worker for
pool-suitable fan-out; native for GUI + authoritative + decide-merge.

**B. Enforcement — `scripts/enforcement/check_subagent_flywheel.py` (fleet-synced), wired into
`final_gate.py`.** Detection uses the pool's own trace: every `run_agents` appends to
`.tmp/subagents/ledger.jsonl` (`agent.py:286,292` — cumulative, append-only, `ledger.py:65`). **The check
reconciles LOCALLY and does NOT read `subagent_runs`** — the provisioned writer role is **INSERT-only**
(`postgres.py:865-866`, no `SELECT`), so a DB read isn't available to the gate anyway. Instead,
`record_agent_run` is **enhanced to write a local receipt** on a successful (`True`) write (marking that
ledger run as recorded+scored); the check flags any ledger entry with **no matching receipt** (= a pool run
that ran but was never scored+recorded). This also dissolves the cumulative-ledger window problem —
unrecorded = *ledger − receipts*, not a time window. **Native subagents never write the ledger, so they are
automatically out of scope** (no false positives on GUI/authoritative work). Registered via the existing
`run_optional_check(..., advisory=True)` runner (`final_gate.py:140`) initially.

**C. Provisioning — `SUBAGENT_RUNS_DSN` (INSERT-only writer role) by default.** VPS is already handled
(`postgres.py:782 create_subagent_ins_role` + `inject_env`). The gap is **WSL dev**: add a
`SUBAGENT_RUNS_DSN` placeholder to the scaffolder's `.env.example` (`scaffold.py:1022`) + a dev-setup step
that points it at a local `fabrik_analytics` writer role, so `record_agent_run` writes without hunting for
creds.

**Teeth [DECISION, overridable]:** default **warn-then-fail** — `advisory=True` now, escalate to hard-fail
on a dated flag (e.g. 2 weeks) once the habit + DSN provisioning have settled fleet-wide. Alternative:
hard-fail from day 1 (max pressure, risks blocking commits mid-adoption).

## Success criteria (testable)

1. `62-using-subagents.md` states **pool-default** for pool-suitable fan-out (native for GUI / authoritative
   / decide-merge) — the "gated / Step-3 / NOT default-on" language is gone.
2. `record_agent_run` (canonical + vendored) writes a **local receipt on `True`**; a fabrik-lib
   `audit_unrecorded(ledger_path)` helper returns ledger entries with no receipt.
3. `SUBAGENT_RUNS_DSN` is set **by default** (scaffold `.env.example` + WSL-dev setup + the existing VPS
   `inject_env`) → a fresh project's `record_agent_run` writes a real row with **no hand-wiring**.
4. `scripts/enforcement/check_subagent_flywheel.py` (fleet-synced) **WARNs** when the ledger has unreceipted
   pool runs; hard-fails after the escalation date. A pool run with no `record_agent_run` is a gate finding.
5. The check yields **zero false positives on native-only work** (no ledger entry → out of scope).
6. End-to-end: a `/fabrik-review` run dispatches pool finders → records + shows `results_table` → gate green;
   omitting the record → the gate flags it.

## Rejected alternatives

- **Prose-only (rules pack / memory).** Rejected — this is the exact failure being fixed: doesn't propagate
  to other projects (a memory is project-scoped) and doesn't compel behavior.
- **Claude Code stop-hook enforcement.** Rejected as the primary teeth — not in the fleet-sync set, harder
  to reason about, Claude-Code-only. (Could complement the gate later.)
- **Hard-fail from day 1.** Rejected as the *default* — blocks commits before the DSN is provisioned
  everywhere; kept as the escalation target.

## External dependencies (grounded)

- **OpenRouter** (pool model provider) — **no new integration**; live-exercised THIS session. Real billed
  costs (dogfood 2026-07-08, `project='pool-dogfood'` in `fabrik_analytics.subagent_runs`): `minimax-m3`
  $0.00056/47s (5/5), `deepseek-v3.2` $0.00014/6s (4/5), `deepseek-v4-pro` $0.00073/10s (4/5) — a review
  task. Model list prices live in `libs/subagents/select.py:_OUT_PRICE` + the synced
  `docs/reference/kilo/CODING_SUBAGENT_SELECTION.md` (coding-selection AI owns). No stale-memory pricing.
- **Postgres `subagent_runs`** (internal) — hub auto-provisions on `fabrik apply`
  (`ensure_shared_analytics_db` + `create_subagent_ins_role`, `postgres.py:782`). INSERT-only writer role.
  Step 2 (live write) proven this session.

## fabrik-lib vendor → enhance → build verdict

| Capability | Verdict | Note |
|---|---|---|
| Pool runtime (`run_agents`/`pick_models`/`record_agent_run`/`results_table`/ledger) | **VENDOR as-is** | already vendored byte-identical to canonical @ `90e0d0d6` |
| Local receipt on `record_agent_run` success + a ledger↔receipt audit helper | **VENDOR + ENHANCE** `libs/subagents` | the module owns BOTH the ledger format AND `record_agent_run`, so the receipt + `audit_unrecorded(ledger_path)` helper belong there — generic to any pool consumer. **Core enhancement → `UPSTREAM_FEEDBACK.md` + propose to canonical (coordinate with fabrik-lib AI); do NOT fork it in the vendored copy** |
| Enforcement check (thin gate wrapper) | **BUILD (glue, fleet-synced)** | `check_subagent_flywheel.py` calls the module's audit helper + wires `final_gate`; fabrik-governance-specific, distributed via `scripts/enforcement/` sync |
| DSN provisioning (scaffold `.env.example` + WSL-dev setup) | **BUILD (glue/config)** | VPS side already exists (`postgres.py`/`inject_env`) |
| Governance flip (62 runtime rule) | **EDIT** | prose in the fleet-synced rules pack |

No new external API; no new fabrik-lib module needed.

## Shape / infra implications

- **No new scaffold type; no new deployed service.** This is fabrik governance + tooling.
- Touches the **fleet-sync set** (`scripts/enforcement/`, `.windsurf/rules/core/62`, scaffold `.env.example`),
  so it propagates to all ~35 projects on the next sync (`fabrik_synced_manifest.py`: `ENFORCEMENT_DIR`,
  `.windsurf/rules`).
- **Coordination (cross-AI):** two dependencies land outside this repo. (1) The coding-selection AI owns the
  `subagent_runs` role/grants + `CODING_SUBAGENT_SELECTION.md`; the WSL-dev writer DSN + any grant change is
  theirs/deploy's domain — coordinate, don't unilaterally alter roles on `fabrik_analytics`. (2) The
  **`record_agent_run` local-receipt enhancement** is a **fabrik-lib module core change** — propose via
  `UPSTREAM_FEEDBACK.md` and land it in canonical with the fabrik-lib AI, then re-vendor; do NOT fork the
  vendored copy. The `check_subagent_flywheel.py` wrapper can ship once the receipt+audit helper is vendored.

## Constraints

- The **NEVER-route-to-pool** list stays absolute: auth/identity/session/crypto, schema/migrations,
  secrets/`.env`/keys, security controls, deploy/infra → native/human only.
- The check must not flag **native-only** work (no ledger entry = out of scope, by design).
- `record_agent_run` **fail-opens to `False`** on a missing `psycopg` / GRANT gap / unreachable DB — the
  receipt is written **only on `True`**, so a fail-open write correctly leaves the ledger entry
  unreceipted → the check flags it (that's the point: a silent `False` becomes a visible gate finding).
- The subagent writer role is **INSERT-only** (`postgres.py:865-866` — no `SELECT`/`UPDATE`/`DELETE`), so the
  enforcement check **cannot read `subagent_runs`** — it reconciles locally (ledger ↔ receipts), never via a
  DB query.
- Cross-repo HARD STOP: role/grant changes on `postgres-main`/`fabrik_analytics` are the coding-selection
  AI's / deploy domain.

## Open / blocking unknowns

- **[DECISION — not blocking]** `path:line` grounders (`plan-after-chat`/`data-contract`): pool + native
  ~20% citation verify-sample (default, consistent with docs-review) vs native-only for citation fidelity.
  User confirms at approval.
- **[DECISION]** enforcement teeth: warn-then-fail (default) vs hard-fail-now. User confirms at approval.
- **[RESOLVED in this pass]** the cumulative-ledger window — the local-receipt mechanism dissolves it
  (unrecorded = *ledger − receipts*, not a time window). Confirmed: `Ledger.append` is append-only to a
  fixed per-repo path (`ledger.py:65`, `agent.py:292`). **Receipt location + format RESOLVED (2026-07-08,
  w/ fabrik-lib AI):** `record_agent_run(…, receipt_dir=None)` appends `{agent_id, ts, recorded:true, project}`
  to `<cwd>/.tmp/subagents/receipts.jsonl`; `audit_unrecorded(ledger_path, receipts_path=None)` co-locates
  receipts at `ledger_path.parent/receipts.jsonl`. Receipt keyed by `agent_id` only (`task_type`/`model` come
  from the ledger record via `audit_unrecorded`'s return, not the receipt); write is fail-open. `run_agents`-
  callers pass `receipt_dir=<repo>/.tmp/subagents` explicitly so receipts never depend on cwd.
- **[OPEN — coordination]** WSL-dev `SUBAGENT_RUNS_DSN`: reuse the `subagent_smoke_writer` role (exists) or a
  dedicated per-dev writer? Resolve with the coding-selection AI.
