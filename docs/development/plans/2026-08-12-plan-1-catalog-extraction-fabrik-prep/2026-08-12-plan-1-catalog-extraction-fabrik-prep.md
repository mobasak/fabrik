# Catalog Extraction — fabrik-side preparation and safety instruments

Status: CONVERGED

**Spec:** [docs/superpowers/specs/2026-07-26-catalog-extraction-design.md](../../../superpowers/specs/2026-07-26-catalog-extraction-design.md) (CONVERGED 2026-08-12, D5 resolved)
**Prior art:** [docs/development/plans/2026-07-26-plan-1-ai-model-catalog-extraction.md](../2026-07-26-plan-1-ai-model-catalog-extraction.md) (HARDENED — 11 review rounds, ~62 fixes; its E.1 import-graph audit is inherited wholesale as T02, not re-derived)

## Goal

Make `/opt/fabrik` **ready and provably safe** for the AI-model-catalog engine extraction, and build the
two instruments that will prove the extraction correct when it happens: a golden-file oracle over the
consumer contract, and an import-graph audit that decides mechanically what may leave. Plus the two
safety fixes that must land *before* anything moves — un-muting the flywheel tripwire, and relocating the
shared cost JSONs out of the doomed tree.

**Why this is its own plan.** The migration is genuinely three repo-scoped units, because
`check_plan_tickets.py:885-888` ERRORs on out-of-repo Touches — a fabrik plan set cannot own
`/opt/ai-model-catalog` paths, and the spec's own Global Constraints already say *"commit + gate per-repo,
never cross."* This is unit 1 and it is **executable today with zero cross-repo writes**. Unit 2 (build the
engine in `/opt/ai-model-catalog`, sever the tentacles, SQLite→Postgres) must be authored **in that repo**
and needs explicit cross-repo authorization. Unit 3 (cutover + excise) is a later fabrik plan, gated on
unit 2 being green and consuming T02's classification output.

## Global Constraints

- **Scope is WSL-only** (spec §7 D5, operator decision 2026-08-12). No VPS deployment, no container, no
  `fabrik apply` anywhere in this plan.
- **The flywheel does not move and must not break.** `fabrik_analytics` stays on the WSL host's local
  PostgreSQL, same Unix socket, same reader, same user; all 5 configured writers untouched.
- **Nothing moves or is deleted in this plan.** It builds instruments and lands two safety fixes. The
  engine tree is read-only to every ticket here.
- **Copy, never move,** for any file a retained consumer resolves by path (rule 7) — a bare `mv` breaks
  the engine's own `_HERE`-relative readers while they are still running.
- **Fail-open floor is sacred:** `libs/subagents/select.py:479-483` (`table.get(task_type) or _TABLE[...]`)
  plus the 14-day staleness gate at `:373`. No step may weaken it; T03 makes breaks visible, not fatal.
- **Shared master:** stage explicit paths only (never `git add -A`), `git diff --cached --name-only` before
  every commit, never touch sibling-authored files.
- **12-Factor non-negotiables inherited by every ticket:** logs are unbuffered JSON to **stdout only, never
  a logfile** (XI) · migrations are a one-off process, never from startup (XII) · **same backing services in
  dev/test/prod** — no SQLite-for-Postgres, no `fakeredis` (X) · no sticky sessions (VI) · no daemonizing or
  PID files (VIII) · workers requeue in-flight jobs on SIGTERM (IX) · releases immutable (V) · config is
  granular env vars, no grouped env sets, no secrets in code (III) · shelled-out binaries installed and
  pinned (II).
- Never-Route: scripts/enforcement/
- Never-Route: scripts/final_gate.py
- Never-Route: .env

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | Golden-file oracle | — | ⚡ | ⬜ | |
| T02 | Import-graph audit | — | ⚡ | ⬜ | |
| T03 | Flywheel safety gates | — | ⚡ | ⬜ | |
| T04 | Shared data-file relocation | — | ⚡ | ⬜ | |
| T05 | Integration receipts | T04 | ⛓️ | ⬜ | |

## Merge Order

1. T01
2. T02
3. T03
4. T04
5. T05

Serialized: scripts/kilo-benchmarks/daily_refresh.sh — T01, T03

## Interfaces

- **T05 consumes T01's oracle** — seam test `tests/catalog_contract/test_snapshot.py` (owned by T01, read by
  T05 as its Context File). T01 produces `catalog_contract_snapshot.py --verify` returning exit 0 on an
  undrifted tree; T05 re-runs it after every other ticket has merged, which is the only place the four
  tickets' combined effect on the consumer contract is observed.
- **T05 consumes T02's classification output** — seam test `tests/catalog_contract/test_audit.py` (owned by
  T02). T02 produces a machine-readable per-node classification; T05 asserts the nodes T04 relocated appear
  as satisfied rule-7 entries, which is what proves the two tickets agree.
- **T02 observes T04's relocation** — no code dependency (both run standalone, hence both ⚡), but T02's
  rule-7 arm is what would have found T04's defect; T05 is where their agreement is asserted rather than
  assumed.

**Wired consumers (anti stored-and-never-read).** Every artifact this plan produces has a named caller:

| Produced by | Artifact | Production caller |
|---|---|---|
| T01 | `scripts/catalog_contract_snapshot.py` | `scripts/kilo-benchmarks/daily_refresh.sh` — T01 wires `--verify` in as a non-blocking drift canary (the reason `daily_refresh.sh` is in T01's Touches and carries a `Serialized:` row with T03), plus T05's integration run |
| T02 | `scripts/catalog_contract_audit.py` | T05's integration run asserts full classification. Its machine-readable output is additionally the **input contract for unit 3** (the excise plan), which is out of this plan's File Scope — stated so the dependency is explicit rather than assumed. The audit is deliberately one-shot: a per-run canary over the whole import graph would be expensive and is not what it is for. |
| T04 | `scripts/claude_p_cost.json`, `scripts/claude_price_ratios.json` | `scripts/claude_p_cost.py:53` `_find()` — already live in the repo; the copies simply become its first-choice path |

## Behavior Contract

- **Given** the live fabrik tree, **When** `--snapshot` runs, **Then** it writes whole-file goldens for the 10 engine-written `docs/reference/kilo/*.md` docs and the 4 `scripts/kilo_*.json` registries, and marker-body goldens for all 11 `(host, MARKER)` pairs including the three non-`ai/` hosts (docs/reference/kilo/TASK_SUBAGENT_SELECTION.md:1)
- **Given** a golden whose ONLY difference is a volatile date stamp (`Last refresh:` or `last-refreshed:`), **When** `--verify` runs, **Then** it reports NO drift (scripts/kilo-benchmarks/rank_task_subagents.py:1107)
- **Given** an unchanged tree the day AFTER snapshotting, **When** `--verify` runs, **Then** it reports zero drift and exits 0 (.windsurf/rules/ai/00-ai-model-selection.md:119)
- **Given** a consumed output mutated in a non-volatile field, **When** `--verify` runs, **Then** it names that exact artifact and exits non-zero (scripts/catalog_contract_snapshot.py:1)
- **Given** a consumed output missing entirely, **When** `--verify` runs, **Then** it reports the absence as drift rather than skipping it silently (scripts/catalog_contract_snapshot.py:1)
- **Given** a marker host whose hand-authored prose OUTSIDE the markers changed, **When** `--verify` runs, **Then** it reports no drift for that marker body (the block, not the file, is the contract) (.windsurf/rules/core/65-rag-search.md:134)
- **Given** the hand-authored `AGGREGATOR_ROADMAP.md` or `BENCHMARK_SOURCES.md` is edited, **When** `--verify` runs, **Then** it reports no drift (they are excluded — zero writers, absent from `daily_refresh.sh`) (scripts/kilo-benchmarks/daily_refresh.sh:551)
- **Given** the harness runs, **When** `--snapshot` captures the contract, **Then** it also records the exact DB queries the live hub consumers issue, satisfying the spec's Phase-0 requirement (docs/superpowers/specs/2026-07-26-catalog-extraction-design.md:166)
- **Given** `scripts/kilo_auto_route.py` inserts the engine dir on `sys.path` and then bare-imports, **When** the audit runs, **Then** `classify_ticket`, `db_models` and `kilo_telemetry` are reported as rule-6 RETAIN nodes (scripts/kilo_auto_route.py:55)
- **Given** a retained consumer that resolves an engine-resident data file by path, **When** the audit runs, **Then** it is reported as a rule-7 RELOCATE node (scripts/claude_p_cost.py:53)
- **Given** a reached node matching none of the 7 rules, **When** the audit runs, **Then** the tool prints that node and exits non-zero (scripts/catalog_contract_audit.py:1)
- **Given** a node reachable ONLY via `sys.path.insert` + bare import, **When** the audit runs, **Then** it appears in the graph (a path-grep baseline would miss it) (scripts/kilo_auto_route.py:55)
- **Given** the audit completes with every node classified, **When** it exits, **Then** it writes `scripts/catalog-contract-audit.json` with one record per node (path, rule, verdict) for the later excise plan to consume (scripts/catalog_contract_audit.py:1)
- **Given** a rule-7 data-file dep whose consumer-dir copy already exists, **When** the audit runs, **Then** it is emitted as rule-7 SATISFIED rather than an open RELOCATE (scripts/claude_p_cost.py:53)
- **Given** the flywheel read fails (psql/sudo unavailable), **When** `rank_task_subagents` runs, **Then** it emits the distinct broken stub and returns exit 1 rather than an empty-but-healthy result (scripts/kilo-benchmarks/rank_task_subagents.py:1374)
- **Given** the ranker returns exit 1, **When** `daily_refresh.sh` invokes it, **Then** an alert is fired on the same channel `check_daily_refresh_freshness.py` uses — propagating a non-zero exit is NOT sufficient (scripts/kilo-benchmarks/check_daily_refresh_freshness.py:1)
- **Given** a healthy flywheel, **When** the positive-proof probe runs, **Then** it asserts state `ok` AND a non-empty row set, failing if rows are empty (scripts/kilo-benchmarks/rank_task_subagents.py:175)
- **Given** the probe cannot reach the database at all (no passwordless sudo / no psql), **When** it runs, **Then** it FAILS loudly and never reports success or skips (docs/superpowers/specs/2026-07-26-catalog-extraction-design.md:240)
- **Given** the flywheel is genuinely empty but reachable, **When** the ranker runs, **Then** it exits 0 and does NOT emit the broken-read stub (scripts/kilo-benchmarks/rank_task_subagents.py:1114)
- **Given** the un-muting change, **When** an unrelated non-fatal step fails in the same run, **Then** the run's other `|| echo` non-fatal steps keep their existing behaviour (scripts/kilo-benchmarks/daily_refresh.sh:115)
- **Given** the copies exist at `scripts/`, **When** `claude_p_cost.py._find()` resolves either name, **Then** it returns the `scripts/` path, not the `kilo-benchmarks/` fallback (scripts/claude_p_cost.py:53)
- **Given** the `scripts/kilo-benchmarks/` originals are absent (simulating post-excise), **When** `cached_amortized_per_mtok()` runs, **Then** it returns the real rate and never the `$0.093/M` fail-soft anchor (scripts/claude_p_cost.py:97)
- **Given** the copy has been made, **When** the engine's own readers run, **Then** they still resolve their `_HERE`-relative originals unchanged (scripts/kilo-benchmarks/derive_cost.py:23)
- **Given** the copies exist, **When** `python scripts/claude_p_cost.py --refresh` runs, **Then** the ticket documents which copy it writes and how the engine's copy stays valid for the migration window (scripts/claude_p_cost.py:157)
- **Given** the two copies, **When** their contents are compared to the originals, **Then** they are byte-identical at copy time (scripts/kilo-benchmarks/claude_p_cost.json:1)
- **Given** all four work tickets merged, **When** the oracle's `--verify` runs, **Then** it reports zero drift, proving no ticket silently changed a consumed output (scripts/catalog_contract_snapshot.py:1)
- **Given** all four work tickets merged, **When** the audit runs, **Then** every node is classified and the relocated cost JSONs appear as satisfied rule-7 nodes (scripts/catalog_contract_audit.py:1)
- **Given** the whole-plan surface, **When** `python scripts/final_gate.py --check --json` runs, **Then** it reports `"status":"success"` (scripts/final_gate.py:1)
- **Given** the docs touched by this set, **When** `/fabrik-docs-review` runs to its fixed point, **Then** it converges with no remaining doc-vs-code drift (docs/superpowers/specs/2026-07-26-catalog-extraction-design.md:1)

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket, on the coder's return, runs `/fabrik-review` on its changed surface to a
  coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green. Per-round floor: 2–3
  pool finders plus exactly 1 native Opus. T03 touches the flywheel and is the highest-risk surface in the
  set — it gets the native Opus authoritative pass regardless of round count.
- **Dispatch policy** — pool-default (`fanout(task_type, …)`, which auto-records to the flywheel and wants
  the `set_quality` back-fill) for the gradeable work: T01, T02 and T04 are pool tickets. Native is added on
  top, never instead — T03 (`native`) and T05 (`native`, Integration) dispatch to the native worktree coder,
  `claude -p opus` for T03 given it touches the flywheel read path. Haiku never codes.
- **Parallelism + merge** — T01, T02, T03 and T04 have no data dependency on one another and fan out
  concurrently in isolated worktrees (all ⚡, disjoint Touches, no Serialized rows needed). Their results
  merge **serially in Merge Order** — the orchestrator adjudicates one at a time regardless of which coder
  returns first. T05 is the barrier: it runs only after T04 merges and is where the four tickets' combined
  effect is observed via the two seam tests in `## Interfaces`.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (ACTIVE) | typing, env handling, script structure for the two new tools | `select_rules.py` ACTIVE (24 packs) |
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | test-per-behavior, risk-ordered, TDD for the risky path (T03) | ACTIVE |
| `.windsurf/rules/core/55-observability.md` (ACTIVE) | stdout-only logging; the un-muted failure must surface as signal, not a logfile | ACTIVE |
| `.windsurf/rules/core/58-resilience.md` (ACTIVE) | fail-open vs fail-visible distinction that T03 turns on | ACTIVE |
| `.windsurf/rules/core/62-using-subagents.md` (ACTIVE) | pool-default dispatch + `fanout`→`set_quality` flywheel | ACTIVE |
| `.windsurf/rules/core/40-documentation.md` (ACTIVE) | Doc Sync Matrix rows each ticket declares in `Docs:` | ACTIVE |
| `fabrik-lib` consult | **No new capability is introduced** — this plan adds two repo-specific audit/snapshot tools over fabrik's own tree and copies two data files. No fabrik-lib module covers "audit THIS repo's import graph"; nothing to vendor. Not a 🆕 candidate either: it is fabrik-topology-specific, failing the generic + reused-by-≥2-types bar. | `/opt/fabrik-lib/README.md` module table read 2026-08-12 |
| `agents-fabrik-core.md` infra invariant | WSL dev uses local PG via env; no container, no `postgres-main` in this plan's scope | `agents-fabrik-core.md:15` |
| `specs/services/ai-model-catalog.yaml` `shape:` | **Unchanged by this plan** — no DB/cache/metrics/search/admin flag flips, because nothing deploys and no engine code moves here | read the `shape:` block (inspection, not `fabrik plan`) |
| Spec §7 *Flywheel-safety invariant* | the three gates T03 implements, verbatim | `docs/superpowers/specs/2026-07-26-catalog-extraction-design.md` §7 |
| Prior art E.1 (7 classification rules) | inherited wholesale as T02's classification arms — not re-derived | `docs/development/plans/2026-07-26-plan-1-ai-model-catalog-extraction.md` § Phase E |

## File Scope (owned paths)

- scripts/catalog_contract_snapshot.py
- scripts/catalog_contract_audit.py
- scripts/catalog-contract-audit.json
- scripts/catalog-contract-goldens/
- scripts/claude_p_cost.json
- scripts/claude_price_ratios.json
- scripts/kilo-benchmarks/daily_refresh.sh
- tests/catalog_contract/test_snapshot.py
- tests/catalog_contract/test_audit.py
- tests/catalog_contract/test_flywheel_safety.py
- tests/catalog_contract/test_cost_json_resolution.py
- docs/development/reviews/2026-08-12-plan-1-catalog-extraction-fabrik-prep-review.md

## Evidence

**T01 — the frozen set is real and counted, not assumed.**

```
$ ls docs/reference/kilo/*.md | wc -l
12
$ ls scripts/kilo_*.json
scripts/kilo_47_agents_final.json
scripts/kilo_all_models.json
scripts/kilo_embeddings_final.json
scripts/kilo_openrouter_routes_final.json
$ grep -l "AUTO-GENERATED\|GATEWAY_COUNTS\|OPENROUTER_ROUTES" .windsurf/rules/ai/*.md | wc -l
8
```

**T02 — the grep-invisible consumer that motivates an import-graph trace** (`scripts/kilo_auto_route.py:54-62`):

```
$ sed -n '54,62p' scripts/kilo_auto_route.py
BENCHMARKS_DIR = SCRIPT_DIR / "kilo-benchmarks"
sys.path.insert(0, str(BENCHMARKS_DIR))

from classify_ticket import classify_ticket  # noqa: E402
from db_models import (  # noqa: E402
    get_model_avoiding_provider,
    get_model_for_priority,
)
from kilo_telemetry import (  # noqa: E402
```

**T03 — the tripwire exists and the call site mutes it** (`rank_task_subagents.py:1374`, `daily_refresh.sh:423`):

```
$ sed -n '1374p' scripts/kilo-benchmarks/rank_task_subagents.py
    return 1 if state == "error" else 0
$ sed -n '423p' scripts/kilo-benchmarks/daily_refresh.sh
    || echo "[daily_refresh] rank_task_subagents failed (non-fatal)"
$ sudo -n -u postgres psql -d fabrik_analytics -tAc "SELECT count(*) FROM subagent_runs;"
6270        # LIVE counter, still growing (read 6274 minutes later) — the load-bearing fact is
            # "reachable and non-empty", never the exact value; T03's probe asserts non-empty, not a number
```

**T04 — the two JSONs exist ONLY in the doomed tree** (`scripts/claude_p_cost.py:53` fallback):

```
$ ls scripts/claude_p_cost.json scripts/claude_price_ratios.json
ls: cannot access 'scripts/claude_p_cost.json': No such file or directory
ls: cannot access 'scripts/claude_price_ratios.json': No such file or directory
$ ls scripts/kilo-benchmarks/claude_p_cost.json scripts/kilo-benchmarks/claude_price_ratios.json
scripts/kilo-benchmarks/claude_p_cost.json
scripts/kilo-benchmarks/claude_price_ratios.json
```

**Shape decision — why a set, and why fabrik-only** (`check_plan_tickets.py:885-888`):

```
$ grep -n "out-of-repo path" scripts/enforcement/check_plan_tickets.py
888:                        f"{t.tid}: out-of-repo path '{p}' in Touches — repo-relative only "
```

## Self-audit

**Grounding passes run.** Solo, inheriting the CONVERGED spec (re-reviewed in this same session, 8 passes,
md5-verified no-op) plus the HARDENED prior plan. Re-verified live this run: the 24 ACTIVE rule packs via
`select_rules.py`; the 12/4/8 frozen-set counts; `kilo_auto_route.py:54-62` rule-6 imports;
`coding-auto.sh:32` and `generate_kilo_agents.py:49` (the reason rule-6 consumers cannot simply be moved);
the rule-7 JSON absence at `scripts/`; `rank_task_subagents.py:1374` and `daily_refresh.sh:423`;
`check_plan_tickets.py:885-888`; the target repo's remote, single `Initial commit`, and its 59 uncommitted
files (governance-sync output, not WIP).

**(a) Coverage — every agreed item mapped to a ticket.**
- *Freeze the consumer contract before anything moves* (spec Phase 0) → **T01**.
- *Derive the move-set mechanically, never by hand* (spec §3a + prior-art E.1) → **T02**.
- *"We should not break flywheel"* (operator, 2026-08-12; spec §7 invariant, 3 gates) → **T03**.
- *Rule-7 data-file dependency must not become a silent post-excise regression* (prior art E.1 rule 7) → **T04**.
- *Whole-plan receipts, docs convergence, final gate* → **T05**.
- *WSL-only scope; flywheel does not move; SQLite→Postgres* (spec §7 D5) → Global Constraints; the Postgres
  consolidation itself belongs to unit 2 (the catalog repo), **not this plan** — deliberately out of scope.
- **Known gap, deliberate:** the actual move, cutover and excise are units 2 and 3. This plan produces the
  instruments that gate them; it does not perform them. Stated in Goal, not left implicit.

**(b) Cross-ticket signature consistency.** T05 is the only consumer of another ticket's produced surface. It
consumes `catalog_contract_snapshot.py --verify` (produced by T01, same flag name in T01's Behavior Contract
and T05's) and the audit's per-node classification (produced by T02's fifth behavior, consumed by T05's
second). Both seam tests are named in `## Interfaces`, owned by the producer's test file and listed in T05's
Context Files. No name appears in one ticket and differently in another.

**Independent review round (2026-08-12).** A native Opus reviewer in a non-author context read the spine and
all five tickets and raised 14 candidates; I re-verified each against live code before acting. **Confirmed and
fixed (8):** the golden set was defined over files a cron rewrites *daily* with an embedded date stamp
(`rank_task_subagents.py:1107`, marker openers carrying `last-refreshed:`, commits on 08-06…08-12), making
zero-drift unachievable — normalization is now a contract row; three engine-produced marker blocks sat outside
the declared `ai/*` scope (`65-rag-search.md:134` `EMBEDDING_WINNERS`, `KILO_MODEL_CAPABILITIES.md:760`
`EMBEDDING_CATALOG`, `KILO_AGENT_SELECTION_GUIDE.md:23,:81`); T03's *"non-zero propagated OR alert"*
disjunction was a **no-op fix** — `daily_refresh.sh` has no `set -e`, redirects to a logfile, and the crontab
has no MAILTO, so propagation surfaces to nobody (now pinned to an alert on the
`check_daily_refresh_freshness.py` channel); T05 asserted a rule-7 *SATISFIED* predicate T02 never promised
(row added); T05's Context Files reached none of the artifacts its own Scope tells it to run (5 paths added);
T04's copy silently redirects `refresh()`'s write target and freezes the engine copy (now owned explicitly);
my `derive_cost.py:24` cite was wrong — line 24 is a `$HOME` path, the real readers are `:23` and `:234`; and
`AUTO-GENERATED` is named in T01's Scope but appears in **0** of the `ai/*` packs. **Refuted in part (1):** the
claim that three `docs/reference/kilo/` docs are hand-authored — measured, only `AGGREGATOR_ROADMAP.md` and
`BENCHMARK_SOURCES.md` have zero writers; `AI_VENDOR_ACCESS.md` has 2. The principle (a glob count is not the
engine's output set) was adopted; the detail was corrected.

**Two deliberate exclusions, stated so a reviewer can tell reasoned omission from oversight:**
`capabilities.json` is named in the spec's Phase-0 snapshot list but is **correctly excluded** — its producer
`scripts/generate_capability_index.py` AST-walks fabrik's own code and never reads `kilo_agents.db`, matching
the spec's own 2026-08-12 correction that these are fabrik-local, not engine outputs.
`scripts/kilo-benchmarks/models_browser.html` (3.8 MB) is an engine output but is **not** in the frozen set:
it is a generated HTML view of the same catalog rows the selection docs already freeze, so it adds mass
without adding contract coverage.

**Fixed-point claim: reached.** The closing pass re-ran every embedded probe (all reproduce), re-verified every
cite added during the review round at its exact line, made ZERO edits and raised ZERO candidates, with an
identical combined-set hash at start and end (`40f015e0…`). `check_plan_tickets --plan-dir` exits 0 with zero
WARNs. Status flipped DRAFT → CONVERGED on that evidence.

## Residual unknowns

**Resolved this run**
- Plan shape (set vs monolith) — resolved: set, 4 work tickets + Integration, per the >3-unit rule.
- Whether one plan can span both repos — resolved: no; `check_plan_tickets.py:885-888` ERRORs on out-of-repo
  Touches, and the spec's Global Constraints independently require per-repo gating. Hence three units.
- Whether the two prior-art hard-won rules still hold 17 days on — resolved: both verified live (Evidence).
- Whether new tooling should extend something existing — resolved: no golden/audit tooling exists in
  `scripts/`; checked before creating.

**Still open**
- **Unit 2 needs cross-repo authorization.** Authoring the engine build-out plan inside
  `/opt/ai-model-catalog` is a cross-repo write requiring the operator's explicit approval in the turn it
  happens. *Resolution step:* ask the operator for that approval before invoking
  `/fabrik-plan-after-chat` from within `/opt/ai-model-catalog`. Does **not** block this plan.
- **T03's un-mute mechanism is a design choice within the ticket** — propagate the non-zero, or alert and
  continue. *Resolution step:* the ticket's Behavior Contract pins the observable ("surfaced, not swallowed")
  and leaves the mechanism to the coder; `/fabrik-review` adjudicates. Self-service, not a stall.
- **The target repo has 59 uncommitted governance-sync files.** Harmless to this plan (no ticket touches that
  repo), but unit 2 should start from a committed tree. *Resolution step:* commit them in that repo before
  unit 2 begins.
