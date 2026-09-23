# Plan 1 (2026-09-23) — premature stops and compaction survival: the DEFERRAL shape, the DECISION block, WHERE YOU ARE

Status: IN-PROGRESS
Profile: standard
**Owner:** infra (the unnamed hub window)
**Spec:** `docs/superpowers/specs/2026-09-23-stop-and-compaction-enforcement-design.md` — CONVERGED (D-371), design APPROVED by the operator 2026-09-23 (D-377).

## Goal

Build spec § The delta (C1–C4; C5 is a measurement, not a build): the Stop hook refuses a turn that hands a derivable step to the operator, the DECISION block is the one legitimate hand-off, and every compaction is followed by a WHERE YOU ARE block rebuilt from records. Acceptance = spec § Validation V1–V3. Every merge on a governance-sync path distributes at merge time (§ Execution Discipline), so V1 (the backtest and its judged sample) runs INSIDE T03, before T03's commit ships the hook; V4–V6 are scheduled measurements T06 records.

## What we already agreed (from the spec + this conversation)

- The approach is spec § C1 (DEFERRAL D1–D4 in the stall lane, same valve), § C2 (the DECISION block, grounds gate · underivable · owned), § C3 (WHERE YOU ARE from records, 72 h fold), § C4 (`# Compact instructions`) — D-371, panel 3/3.
- The operator approved the design: *"approved"* (D-377).
- Named-gate wording no longer exempts a DEFERRAL; gate-ending commands state their gate as a `ground: gate` block, rendered BEFORE the hook lands (spec § C1, § Lifecycle Adoption; D-372).
- No fleet `autoCompactWindow` (spec § C5, D-376).
- Mandatory inputs the review routed to `docs/STRATEGIC_BACKLOG.md` (row "Four own-fix defects the stop-and-compaction spec review RECORDED", 51098f062): A-O40 narrow D4 to the agent's own remaining work with the five factual sentences as green fixtures (→ T03); A-O41 the DECISION clear skips only built-in slash commands (→ T04); A-O42 V3's fixture pins that clear rule (→ T04); A-O43 `asked:` must quote an operator entry that is not a command expansion and ends in `?` (→ T03); `scope:` quotes verified the same way (→ T03); `draw.py`'s docstring (→ T05).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"approved"* — the design approval (D-377) | IN | this plan |
| I2 | the spec's C1–C4 build and V1–V3 acceptance | IN | T01a–T06 |
| I3 | the four recorded own-fix inputs + two notes (backlog row, 51098f062) | IN | T03, T04, T05 |
| I4 | fleet distribution (spec § Shape / infra) | IN — CHANGED: per-merge post-commit sync (§ Execution Discipline); T06 verifies nothing is pending | T06 |
| I5 | the fabrik-lib mail (its CLAUDE.md is HAND-MAINTAINED) | IN | T06 |
| I6 | V4–V6 (day-7/14 measurements) | IN — as a dated STRATEGIC_BACKLOG row T06 writes, since execution cannot wait 14 days | T06 |
| I7 | the run-record wait-vs-abandon false block (spec I17) | OUT-OF-SCOPE — its own backlog row exists (51098f062) | `docs/STRATEGIC_BACKLOG.md` |

Intake: 7 items — 6 IN, 1 OUT-OF-SCOPE (named), 0 ASK.

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01a | gate-ending command sources state their gate as a DECISION block | — | ⚡ | ✅ | 48120c74f |
| T01b | the kaizen vocabulary: the `decision_block` event and `deferral` as a premature cause | — | ⚡ | ✅ | a99e54f66 |
| T02a | hub `CLAUDE.md`: the DECISION block, the bar bullet, `# Compact instructions` | — | ⚡ | ⬜ | |
| T02b | `templates/governance/CLAUDE.md`: the same, in every § FINAL OUTPUT copy | T02a | ⛓️ | ⬜ | |
| T03 | the Stop hook: DEFERRAL D1–D4, the DECISION parser, the reasons, the input, the V1 backtest | T01a, T01b, T02b | ⛓️ | ⬜ | |
| T04 | `thread_anchor.py`: WHERE YOU ARE on compact, the DECISION harvest and clear, the 72 h fold | T03 | ⛓️ | ⬜ | |
| T05 | `stop_mine.py` (the miner, sharing `_DEFER_RE`), the V1 backtest, the three docs | T04 | ⛓️ | ⬜ | |
| T06 | Integration: receipt, whole-plan gate + review, docs-review, the sync, V2/V3, the mail, the V4–V6 row | T05 | ⛓️ | ⬜ | |

**Breadth advisory, adjudicated (`check_ticket_breadth.py --plan-dir` 2026-09-23 flagged T03):** KEPT, not split. Its three behaviours are one detector: the four DEFERRAL shapes, the one exemption that clears them (the DECISION block) and D4's precision are read together by the same `_detect_stall` pass and share the stall counter, so splitting them puts halves of one decision rule in two serialized merges on the same fleet-synced file. `scripts/sysadmin/kaizen_events.py` is the one-line registration of the event T03 emits. The advisory's calibration (2 of 4 flags matched, ρ=0.45) is a prompt to look, and this line records the look.

## Merge Order

1. T01a
2. T01b
3. T02a
4. T02b
5. T03
6. T04
7. T05
8. T06

Serialized: tests/test_governance_template_split.py — T02a T02b

## Interfaces

- **T03 → T04: the DECISION parser.** T03 produces `extract_decision_block(text: str) -> str | None` (the last block outside a fence, with its four lines) and `parse_decision_block(text: str, *, run_live: bool, transcript_path: str) -> tuple[bool, str]` in `.claude/hooks/final_gate_stop.py` (`(True, ground)` when well-formed and allowed, `(False, reason)` otherwise), and passes `--decision-ok` to its `thread_anchor.py harvest` call only on `(True, …)`, piping the same text it judged (the call at `final_gate_stop.py:1836-1847`). Seam test: `tests/test_thread_anchor.py::test_a_refused_block_is_never_stored` (owned by T04).
- **T03 → T04: the session helpers.** T03 produces `session_unpushed(root: Path, authored: set[str], *, timeout: float = 2.0, limit: int = 10) -> list[str]` (this session's unpushed commits, via `_commit_is_mine`, `:645`). T04 imports it, by path, with `_session_files`, `_baseline_floor`, `_this_sessions_edits` and `_run_record` (`:346`, `:1179`, `:1224`, `:519`), unchanged. Seam test: `tests/test_thread_anchor.py::test_where_block_lists_only_this_sessions_commits` (owned by T04).
- **T03 → T05: the vocabulary.** T03 produces `_DEFER_RE` and `deferral_shape(text: str) -> str | None` (returns `D1`…`D4` or None). `scripts/sysadmin/stop_mine.py` imports both. Seam test: `tests/test_stop_mine.py::test_the_miner_counts_with_the_hooks_vocabulary` (owned by T05).

## Behavior Contract

- **Given** the six gate-ending command sources, **When** T01a lands, **Then** each states its human gate as a `DECISION NEEDED (ground: gate)` block and none tells the agent to write `operator decision: <the act>` as the exemption (spec § Contract deltas)
- **Given** the kaizen modules, **When** T01b lands, **Then** `decision_block` is a registered event type and `deferral` is a premature stop cause (spec § Contract deltas; A-O19)
- **Given** hub `CLAUDE.md`, **When** T02a lands, **Then** § FINAL OUTPUT carries the DECISION block with one legitimate and one refused example, the `operator-decision-bar` bullet keeps its anchor and names the block, and a `# Compact instructions` section lists the five things a summary must carry (spec § C2, § C4)
- **Given** `templates/governance/CLAUDE.md`, **When** T02b lands, **Then** every § FINAL OUTPUT copy and the index line carry the same DECISION block, examples and `# Compact instructions` as the hub, byte-identical where the parity test compares (spec § Contract deltas)
- **Given** an interactive turn ending on a D1–D4 deferral with no DECISION block, **When** the Stop hook runs, **Then** it blocks with `cause=deferral` and the one-paragraph reason, and warns through after three blocks (spec § C1)
- **Given** a turn ending on a well-formed DECISION block, **When** the Stop hook runs, **Then** the stall lane allows the stop, a `decision_block` event carries its ground, and `owned`+`scope:` inside a live run and an `asked:`/`scope:` quote not found in an operator entry are refused (spec § C2; A-O43)
- **Given** factual prose about a new session and the judged false matches, **When** D4 runs, **Then** it does not fire, while it fires on at least 6 of the 8 judged real excuses (spec § C1 D4; A-O40)
- **Given** a compaction in a session with a live run, an accepted DECISION block, and commits by two sessions, **When** SessionStart fires with `source=compact`, **Then** WHERE YOU ARE shows the run, the last NEXT, the open block, and only this session's unpushed commits and dirty files (spec § C3)
- **Given** an open DECISION block, **When** the operator submits a plain answer, a built-in slash command, or a custom command, **Then** the plain answer and the custom command clear it and the built-in does not (spec § C3; A-O41, A-O42)
- **Given** anchors aged 71 h and 73 h, **When** `line` renders, **Then** the 71 h anchor prints in full and the 73 h one is folded into the one-line summary, and nothing is deleted (spec § C3 item 5)
- **Given** the promoted miner, **When** it runs the V1 backtest, **Then** it counts deferrals with the hook's own `_DEFER_RE` and reports the fire rate per shape and per repo (spec § Validation V1)
- **Given** every work ticket merged, **When** T06 runs, **Then** a `--dry-run` sync shows no pending difference for the hook, `thread_anchor.py` and the template in any synced repo (the per-merge post-commit sync already distributed them), the whole-plan `/fabrik-review` closes quiet with its receipt, and the V1 and V3 results are recorded (spec § Validation)

## Global Constraints

- The Stop hook never traps a session: every new cause rides `decide_stall` and `CAP = 3` (`final_gate_stop.py:40`, `:1296`).
- Every new path fails open, and a failure is written to stderr, never swallowed silently (spec § Lifecycle, Degradation).
- `.claude/hooks/`, `.claude/settings.json`, `scripts/thread_anchor.py`, `CLAUDE.md` and `templates/governance/CLAUDE.md` ship fleet-wide; nothing is hub-only on those paths.
- The sound mesh's PreCompact/PostCompact hooks are not touched (spec K7).
- Type hints on every new function signature (`.windsurf/rules/core/10-python.md:160`).
- The shared tree: never stage, revert, stash or `noqa` sibling WIP; shared-append ledgers go through the private-index recipe (CLAUDE.md § Behavior).
- Render the command corpus only from the main master checkout, in the order render → `--check` → `check_command_corpus.py` → commit.
- The pool is OFF (D-181/D-182). Seats never read `$HOME/.claude*`.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (ACTIVE) | typed signatures | `.windsurf/rules/core/10-python.md:160` "Use type hints for all function signatures" |
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | one test per behaviour; watched-fail-first | `.windsurf/rules/core/45-testing-strategy.md:20`, `:22` |
| `.windsurf/rules/core/40-documentation.md` (ACTIVE) | fenced code only in docs | `.windsurf/rules/core/40-documentation.md:243` |
| `fabrik-lib` | none — hub governance machinery, distributed by sync, never vendored | spec § fabrik-lib verdict table |
| `agents-fabrik.md` infra invariant | none touched (no service, port, compose or DB) | spec § Shape / infra implications |
| `specs/services/<id>.yaml` `shape:` | none — no deployed service | spec § Shape / infra implications |

## Constraints Digest

| Rule (verbatim) | file:line | Pack |
|---|---|---|
| the cap so a misfire can never trap the session. | `.claude/hooks/final_gate_stop.py:1301` | the Stop hook's own design rule (K1) |
| Precision over recall throughout — | `.claude/hooks/final_gate_stop.py:1313` | the Stop hook's own design rule (K2; the named-gate half superseded for DEFERRAL, D-372) |
| Use type hints for all function signatures | `.windsurf/rules/core/10-python.md:160` | core/10-python |
| **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** | `.windsurf/rules/core/45-testing-strategy.md:20` | core/45-testing-strategy |
| **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` | core/45-testing-strategy |
| **Fenced code blocks only** — never indented code (AI treats it inconsistently) | `.windsurf/rules/core/40-documentation.md:243` | core/40-documentation |

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket, on the coder's return, runs `/fabrik-review` on its changed surface to a coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green. T03 and T04 are the heavy fleet-synced surface: their reviews are partitioned by file with the Opus seat on the hook / `thread_anchor.py` (`dispatch_headroom.py --slices opus=1,sonnet=1`, stamped first). T06's whole-plan `/fabrik-review` writes the receipt.
- **Dispatch policy** — native Claude seats for every fan-out (the pool is OFF, D-181/D-182). Coders are native worktree coders: Opus for T03 and T04 (design-heavy hook code), Sonnet for T01, T02a, T02b and T05. The Opus seat is the authoritative review pass; the decide/merge is the orchestrator's.
- **Distribution** — every merge touching a governance-sync path (the `governance-sync` files-filter in `.pre-commit-config.yaml`: `templates/governance/`, `.claude/hooks/`, `scripts/thread_anchor.py`) is distributed fleet-wide AT MERGE TIME by the installed post-commit hook (`scripts/governance_sync_postcommit.sh`). So T02b, T03 and T04 each reach every synced repo when they merge, and the ticket order below is also the fleet's adoption order; each ticket's own review therefore closes BEFORE its merge. T06 verifies that nothing is pending rather than running a second sync.
- **Parallelism + merge** — T01a, T01b and T02a fan out concurrently (disjoint Touches) and merge in Merge-Order position; T02b follows T02a (Serialized on the parity test). T03 waits for T01a, T01b and T02b: the gate-ending commands and the contracts must name the DECISION block before the hook refuses anything else. The orchestrator renders the corpus from master on T01a's merge, so the rendered commands carry the block before T03's hook exists anywhere. T04, T05 and T06 follow serially. Results merge in the main checkout, per ticket, each after its own review.

## File Scope (owned paths)

- commands/_sources/fabrik-spec-review.md
- commands/_sources/fabrik-flows-review.md
- commands/_sources/fabrik-ui-design-review.md
- commands/_sources/fabrik-deploy-plan-review.md
- commands/_sources/fabrik-release.md
- commands/_sources/fabrik-deploy.md
- tests/test_gate_decision_blocks.py
- CLAUDE.md
- templates/governance/CLAUDE.md
- tests/test_governance_template_split.py
- .claude/hooks/final_gate_stop.py
- scripts/sysadmin/kaizen_events.py
- scripts/sysadmin/kaizen_collect_v2.py
- tests/test_kaizen_deferral_vocabulary.py
- tests/test_final_gate_stop_deferral.py
- tests/test_stop_hook_deferral_exemption.py
- tests/test_final_gate_stop_hook.py
- tests/test_kaizen_hook_emitters.py
- scripts/thread_anchor.py
- tests/test_thread_anchor.py
- scripts/sysadmin/stop_mine.py
- tests/test_stop_mine.py
- docs/workstation/hooks-index.md
- docs/reference/thread-anchors.md
- docs/workstation/kaizen-event-stream.md
- docs/reference/research/2026-09-23-stop-compaction/draw.py
- docs/development/reviews/2026-09-23-plan-1-stop-and-compaction-review.md

## Evidence

Every ticket's primary path, grounded this run at `c062a6f82`:

- T01a: the six sources end at a human gate (`commands/_sources/fabrik-spec-review.md:282`, `fabrik-flows-review.md:161`, `fabrik-ui-design-review.md:169`, `fabrik-deploy-plan-review.md:245`, `fabrik-release.md:6`, `fabrik-deploy.md:29`); `fabrik-plan-review.md:17` and `fabrik-epics-review.md:22` do NOT (no approval gate), so they are excluded.
- T02a/T02b: `CLAUDE.md:631` and `:661`, `:385`; `templates/governance/CLAUDE.md:629`, `:650`, `:672`, `:702`, `:359`.
- T03: `.claude/hooks/final_gate_stop.py:1631` (`_detect_stall`), `:1335` (`_PERMISSION_RE`), `:1422` (`_GATE_EXEMPT_BARE_RE`), `:2137-2139` (the stall reason), `:1836-1847` (the harvest call), `:17` (the header). T01b: `scripts/sysadmin/kaizen_events.py:114` (`EVENT_TYPES`), `scripts/sysadmin/kaizen_collect_v2.py:118` (`PREMATURE_CAUSES`).
- T04: `scripts/thread_anchor.py:165` (`cmd_harvest`), `:187` (`cmd_line`), `:225` (`main`), `:248` (the payload parse).
- T05: `docs/reference/research/2026-09-23-stop-compaction/mine.py` (the miner being promoted).

```
$ command grep -l -i -E "explicitly ask the user to approve|STOP — explicitly ask|Gate 2|approval gate|operator decision:" commands/_sources/*.md
commands/_sources/fabrik-deploy.md
commands/_sources/fabrik-deploy-plan-review.md
commands/_sources/fabrik-epics.md
commands/_sources/fabrik-epics-review.md
commands/_sources/fabrik-flows-review.md
commands/_sources/fabrik-plan-review.md
commands/_sources/fabrik-release.md
commands/_sources/fabrik-spec.md
commands/_sources/fabrik-spec-review.md
commands/_sources/fabrik-ui-design-review.md
commands/_sources/fabrik-workflow-review.md
```

Of these 11, 6 end a run at a human gate (above). `fabrik-epics` matches on "parallel gate 2/3" (an epic check, not Gate 2), `fabrik-spec` hands off to `/fabrik-spec-review`'s gate, and `fabrik-workflow-review` states it owns no gate (`:66`).

```
$ wc -c .claude/hooks/final_gate_stop.py scripts/thread_anchor.py scripts/sysadmin/kaizen_events.py CLAUDE.md templates/governance/CLAUDE.md
124339 .claude/hooks/final_gate_stop.py
 12893 scripts/thread_anchor.py
 33334 scripts/sysadmin/kaizen_events.py
102861 CLAUDE.md
105216 templates/governance/CLAUDE.md
```

The two contracts plus the 62 KB spec would exceed one ticket's READ budget (262,144 B), hence T02a/T02b.

## Self-audit

(a) Every agreement lands in a ticket: C1 → T03; C2 → T01a, T01b (the event), T02a, T02b, T03; C3 → T04; C4 → T02a, T02b; V1 → T03 (before its commit ships the hook) with T05's durable miner; V2 → every ticket's red fixtures; V3 → T04 + T06's dogfood; V4–V6 → T06's dated row; the six recorded inputs → T03, T04, T05. (b) Every cross-ticket interface is named in `## Interfaces` with its consumer-owned seam test. (c) Wired consumers: T03's parser is consumed by the hook itself and by T04; T04's WHERE block by the existing SessionStart entry (`.claude/settings.json`, the empty-matcher `thread_anchor.py line --hook`); T05's miner by T06's V1 read and the V4/V6 runs.

## Coverage Checklist

Rubric over the plan's File Scope (`python scripts/review_rubric.py --changed commands/_sources/fabrik-spec-review.md commands/_sources/fabrik-flows-review.md commands/_sources/fabrik-ui-design-review.md commands/_sources/fabrik-deploy-plan-review.md commands/_sources/fabrik-release.md commands/_sources/fabrik-deploy.md tests/test_gate_decision_blocks.py CLAUDE.md templates/governance/CLAUDE.md tests/test_governance_template_split.py .claude/hooks/final_gate_stop.py scripts/sysadmin/kaizen_events.py tests/test_final_gate_stop_deferral.py tests/test_stop_hook_deferral_exemption.py scripts/thread_anchor.py tests/test_thread_anchor.py scripts/sysadmin/stop_mine.py tests/test_stop_mine.py docs/workstation/hooks-index.md docs/reference/thread-anchors.md docs/workstation/kaizen-event-stream.md docs/reference/research/2026-09-23-stop-compaction/draw.py docs/development/reviews/2026-09-23-plan-1-stop-and-compaction-review.md`):

```text
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; TOOLING surface)

### core/10-python.md
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/40-documentation.md  (hit: CLAUDE.md, commands/_sources/fabrik-deploy-plan-review.md, commands/_sources/fabrik-deploy.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_final_gate_stop_deferral.py, tests/test_gate_decision_blocks.py, tests/test_governance_template_split.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.

# promote-to-check_*: ELIDED (the sanctioned elision — the tail is 20 greppable-literal lines; header, FLOOR and MATCHED above are verbatim)
```

Every row is adjudicated at the flip with ONE of the verdicts `check_review_coverage.py` accepts — `CLEAN` · `FIXED(n)` · `REFUTED` · `ROUTED(n)` · `RECORDED — (unexecuted|by design|measured|hygiene false positive)`.

| # | Class | Verdict | Where |
|---|---|---|---|
| 1 | core/10-python — typed signatures, `uv` runner, no new dependency, no `logging.getLogger` in a hook that has its own stderr contract | CLEAN | every new function in the Interfaces carries types (`extract_decision_block`, `parse_decision_block`, `deferral_shape`, `session_unpushed`); every Gate runs `uv run pytest`; no ticket touches `pyproject.toml`/`uv.lock` |
| 2 | 12-Factor — no service/worker/compose surface touched; rows inherited | CLEAN | the 28 Touches are hooks, scripts, tests, two contracts, six command sources, three docs and a receipt — no compose, service or worker |
| 3 | core/40-documentation — Doc Sync Matrix rows per ticket; fenced code only; the two contract copies and six command sources | FIXED(4) | the release and deploy gate sites (B-S1, B-S5); T02a/T02b's missing reads (B-S2, B-S3); every ticket carries a `Docs:` line; T05 owns the three doc rows |
| 4 | core/45-testing-strategy — one test per behaviour, red-first, green fixtures proven by mutation | FIXED(6) | the malformed-block fixtures completed (A-O10); the `isMeta` fixture (A-O9); the existing graders T03 changes named in three files (A-O2 ×2, A-O21); green fixtures proven by mutation (T03 step 2) |
| 5 | fail-open / fail-closed — every new hook path fails open and says so; the parser refuses (fails closed) on a malformed block | FIXED(3) | the text-only `_detect_stall` path (A-O7, A-O18); the WHERE block's import/call failures omit the item and write stderr (T04 step 4) |
| 6 | cost / limit edges — the 600-char tail vs the whole-message block parse; `CAP = 3` shared with the stall lane; the 10-item WHERE caps | FIXED(4) | the READ budgets (T03 split of reads, T01b); `session_unpushed`'s 2 s timeout inside the 10 s SessionStart budget (A-O4); the anchor caps (A-O6, A-O19) |
| 7 | boundary / sentinel / prefix — the D1 vocabulary vs the conversational footer; built-in vs custom slash commands; a block inside a fence | FIXED(3) | the whole-token built-in match (A-O14); `extract_decision_block` skipping fenced examples (A-O15); the D4 frame (A-O1) |
| 8 | behaviour without a test — every Behavior Contract row names its grader | FIXED(2) | T01b's row and its test added (A-O19 of pass 2); T06's row now states what it verifies under the per-merge sync (A-O3) |

## Pass Ledger

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | set md5 (start → end) |
|---:|---|---|---|---|
| Pass 1 | opus×1 (spine rules + T03 + T04) + sonnet×1 (T01, T02a, T02b, T05, T06 + narrative) + 2 refuters · all axes | found: 21, new: 21, confirmed: 21, fixed: 21, unexecuted: 0, edits: 26 | method: citation — the full partitioned pass; every candidate executed by its refuter, the load-bearing ones re-run by the orchestrator (the READ budgets, `_run_record`'s acceptance rules, `fabrik-release.md:188-191`, the `command_run.py` record fields); the fixes re-cut T03's D4 frame, gave T03 the existing graders it changes, named the per-merge post-commit sync, added `extract_decision_block` and `session_unpushed` to the interfaces, and moved the event registration to T01 so T03 fits its budget | 983e7e9f → a3486818 |
| Pass 2 | opus×1 + sonnet×1 (the round-1 slice owners) + 2 refuters · the fix diff plus one hop | found: 6, new: 3, confirmed: 5, fixed: 6, unexecuted: 0, edits: 17 | method: re-derivation — 18 of 22 ledger claims re-executed NOW_FALSE (the D4 frame 6/8 · 0/9 · 0/5; the built-in token rule; the interface names); 5 confirmed, 4 of them residue of pass 1's own fixes (the spec dropped from T03's reads, the text-only `_detect_stall` path, two graders missed, the cap evicting the paused thread); V1 moved INTO T03 because the per-merge sync ships the hook at T03's commit; the recorded A-O19 fixed too, as the new T01b | 9ed4e29c → 73ff341d |
| Pass 3 | opus×1 + sonnet×1 (the round-1 slice owners) + 2 refuters · the fix diff plus one hop | found: 4, new: 3, confirmed: 3, fixed: 3, unexecuted: 0, edits: 6 | method: re-derivation — all 6 ledger claims re-executed NOW_FALSE (D1's list and the C2 checks against spec:132/:176-181; the text-only path against `:1647-1649`; T01b against `kaizen_events.py:114`, `kaizen_collect_v2.py:118`); 3 confirmed (a grader in `tests/test_kaizen_hook_emitters.py:583`; D3's self-answered exclusion and the global `BLOCKED:` exemption not inlined; the dropped-anchor count with nowhere to print), 2 of them own-fix → the scope-growth stop fires (passes 2 and 3 both at two-thirds or more own-fix); the three are the fixed set pass 4 re-verifies | 73ff341d → 5cc1b9f1 |
| Pass 4 | opus×1 (the round-1 owner of slice A) · the fixed set only, under the scope-growth stop; slice B restated (verified in pass 3) | found: 0, new: 0, **confirmed: 0**, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — the three fixed-set claims re-executed NOW_FALSE (the emitter grader's one D1 literal found by probe; the D3 green column and the global `BLOCKED:` exemption matched to spec:134/:123; the dropped-count line). RECORDED — measured, not counted, destination `/fabrik-execute-plan`'s T03/T04 dispatch briefs: T03 reads `tests/test_kaizen_hook_emitters.py` only around `:570-595`; T03's quote-skip applies to D1, D2 and D4 as well as D3 (spec:122); T04 step 1 adds a young-cap-eviction fixture with no folded anchor; T03 step 2 adds `NEXT: /fabrik-spec-review <path>` as a D1 green fixture | 5cc1b9f1 → 5cc1b9f1 ✓ → **CONVERGED** |

## Residual unknowns

- U1 (spec): whether this box's Claude Code sends `last_assistant_message`. T03 logs its presence on the first 20 live Stops, and the transcript read stays as the fallback. Self-service.
- U2 (spec): where compact-time SessionStart output sits relative to the summary. T06's V3 dogfood reads the post-compact transcript. Self-service.
- **Sizing evidence (the emit gate at the flip):** `✓ [plan_tickets] /opt/fabrik/docs/development/plans/2026-09-23-plan-1-stop-and-compaction: graded 8 ticket(s), 28 Touches path(s), 33 Context-Files entry(ies); READ budget measured against /opt/fabrik; 0 finding(s)`.
