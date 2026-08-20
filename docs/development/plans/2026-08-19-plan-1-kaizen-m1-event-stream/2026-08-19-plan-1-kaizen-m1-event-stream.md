# Kaizen M1 — the typed append-only event stream (measure truthfully)

Status: IN-PROGRESS
Spec: docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md § Layer 1 + § Sequencing M1 (operator dispatch 2026-08-19: "then /fabrik-plan-after-chat for M1")

## What we already agreed

- **Operator (verbatim, adopted into the spec):** "replace prose-parsing with a typed append-only
  event stream"; kaizen must be daily; the loop measures the WHOLE coding infrastructure.
- **Spec § L1 (CONVERGED, operator-approved):** hooks + run-record machinery emit one-line JSON
  events to `~/.claude/state/events/` — **one file per session** (concurrent writers into one file
  tear lines past PIPE_BUF); emission is **fail-open and zero-dependency** (append to a local file;
  a broken emitter must never break a session); transcripts become forensics, the meter reads
  events. Event vocabulary (spec `:57-63`): `session_start`, `run_open`, `phase`, `round`,
  `run_close`, `gate_run` with per-check outcomes, `rule_activation`, `stop_block` by cause,
  `final_block_emitted`, `death`, `revival`, `operator_override`.
- **Exposure metadata on every event** (spec `:97-104`): hub commit, rendered-command + rulepack
  hash, model, account, plan era, project, scaffold type, human-vs-headless flag, concurrency flag.
- **The coroner is REQUIRED** (spec `:113-130`): mid-stream deaths fire no Stop hook — reconstruct
  `death` events from the resume mesh's markers + transcript tails; the coroner closes the dead
  session's run record with verdict `died` (platform-stamped, never the agent); TTL force-close
  backstops it; "transcript exists but no `session_end`" is a first-class hole metric.
- **Versioned definitions + append-only derived-facts store** (spec `:82-95`): every metric carries
  a definition version + hash; published series are never overwritten; history recomputes from a
  compact one-row-per-session store, never a full transcript re-parse.
- **Collector proves itself first** (spec `:106-111`): duplex fixtures per parsing predicate + a
  golden corpus asserted before any number is consumed; instrument health is metric zero.
- **Noise-floor backfill** (spec `:132-134`): per-metric variance over history BEFORE adjudication.
- **Metric set** (spec `:136-156`): outcome tier (rework rate from provenance trailers,
  fleet-health sweep on clean worktrees, premature-stop rate, first-attempt gate pass), process
  tier (gate-failure taxonomy), compliance split (`rules_compliance` with run-record-closure
  denominator vs `terminator_spam`), **paired counter-metrics as a registry schema constraint**.
- **M1 autonomy: none (measurement only).** M1's exit gate (spec § Sequencing M1) includes
  "7 days of events" — **calendar time, post-execution**: this plan delivers the machinery and its
  immediate verifications; the 7-day observation and variance sign-off happen after, before M2.
- **M0 hand-offs bound into this plan:** `kaizen_metrics.py` retires WITH M1 (operator ruling,
  `docs/workstation/kaizen-shrink-audit.md` § Operator ruling); Lesson 127's collector refinements
  (structure-keyed extraction, `isSidechain` exclusion, registry-declaration joins — all shipped in
  `scripts/sysadmin/kaizen_shrink_audit.py` and REUSED here, not reinvented); the run-record
  `nosession` collision (root cause grounded below) gets its honest M1 treatment; the wake-proof
  `weekly_catchup.sh` pattern schedules any M1 cron.
- **Constraints (spec § Constraints + CLAUDE.md):** box-local Python stdlib, no new deps; the
  sound system (`~/.claude/bin/claude-sound.sh`) is production — the coroner READS its markers,
  never edits it; `.claude/hooks/*` are FLEET-SYNCED trigger surfaces (a hub edit distributes to
  ~46 repos — every hook change must be correct fleet-wide and fail-open); `final_gate.py` +
  `scripts/enforcement/` are never-route; the honesty rule binds every metric (`—` with reason,
  never a fabricated 0).

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | events-core: schema + emitter library + exposure resolver | — | ⚡ | ✅ | 19754de5 |
| T02 | hook emitters: session lifecycle + stop_block/final_block + operator_override | T01 | ⚡ | ✅ | 10-finding native acceptance, all red-proven; merged (squash of a151cccc+fd587961) |
| T03 | run-record events + sid plumbing + lifecycle audit | T01 | ⚡ | ✅ | 13-finding round 1 + 4-L round 2, all closed; merged (squash of 9610a1bb+96035db7+20aba0dd) |
| T04 | sensor emitters: gate_run per-check + rule_activation | T01 | ⚡ | ⬜ | |
| T05 | the coroner: death/revival reconstruction + record closure + hole metric | T01, T03 | — | ⬜ | |
| T06 | collector v2: derived-facts store + versioned metrics + paired-counter registry | T01, T02, T03, T04, T05 | — | ⬜ | |
| T07 | outcome tier: rework miner + fleet-health sweep + premature-stop | T06 | ⚡ | ⬜ | |
| T08 | noise-floor backfill + variance report | T06 | ⚡ | ⬜ | |
| T09 | integration: daily cutover, kaizen_metrics retirement, docs, receipts | T07, T08 | — | ⬜ | |

## Merge Order

1. T01
2. T02
3. T03
4. T04
5. T05
6. T06
7. T07
8. T08
9. T09

Serialized: scripts/sysadmin/kaizen_events.py — T01, T05
Serialized: scripts/sysadmin/kaizen_collect_v2.py — T06, T08

## Interfaces

- **T01 → T02/T03/T04/T05** — `kaizen_events.emit(event: str, **fields) -> bool` (fail-open: False
  on any error, never raises) + `kaizen_events.exposure() -> dict` + the event-schema doc
  (`docs/workstation/kaizen-event-stream.md` § Schema). Seam test owned by EACH consumer: its
  emitter writes a parseable line to a tmp events dir carrying `schema`, `ts`, `sid`, `event` +
  its exposure block (T02: `tests/test_kaizen_hook_emitters.py`; T03: extension of
  `tests/test_command_run.py`; T04: `tests/test_kaizen_sensor_emitters.py`).
- **T03 → T05** — the run-record close API (`command_run.py` `done`/`blocked` + record dict shape,
  `scripts/command_run.py:129-150`) consumed by the coroner's platform-stamped `died` closure. Seam
  test owned by T05: a fixture record + fixture death marker → record closed with
  `verdict: "died"`, `closed_by: "coroner"`.
- **T05/T02/T03/T04 → T06** — event files under a `Sources`-style overridable root; T06's seam test
  (owned by T06): a fixture session directory containing every T02–T05 event type parses into
  exactly one derived-facts row with the expected fields.
- **T06 → T07/T08** — `derived_facts.read_rows(since)` + `metric_registry` (versioned definitions
  with `counter_metric` REQUIRED — the schema constraint). Seam tests owned by T07/T08.

## Behavior Contract

- **Given** a session whose emitter raises anywhere (disk full, bad field, missing dir), **When**
  any instrumented surface runs, **Then** the session proceeds unharmed and the emitter returns
  False — fail-open is proven by a test that injects the failure
  (scripts/sysadmin/kaizen_events.py).
- **Given** two concurrent sessions emitting simultaneously, **When** their events land, **Then**
  each writes only its own per-session file and no line tears (one file per sid; O_APPEND
  single-line writes ≤ PIPE_BUF asserted in-test).
- **Given** an event emitted from a context with no resolvable session id, **When** it lands,
  **Then** `sid` is the literal `unknown` and the collector counts it in the unclassified-rate —
  never silently merged into another session's stream.
- **Given** a `SessionStart` and a Stop-hook block in a live session, **When** the hooks fire,
  **Then** `session_start` and `stop_block` (with its cause) events exist in that session's file,
  and a sanctioned-skip marker in the operator's reply emits `operator_override`
  (.claude/hooks/final_gate_stop.py).
- **Given** a `/fabrik-*` run opened, stepped, rounded, and closed, **When** the record mutates,
  **Then** matching `run_open`/`phase`/`round`/`run_close` events carry the record's command,
  phases, and verdict (scripts/command_run.py).
- **Given** a `final_gate.py --json` run, **When** it completes, **Then** ONE `gate_run` event
  carries per-check name+outcome for every executed check and the overall status
  (scripts/final_gate.py).
- **Given** a `select_rules.py` invocation, **When** packs resolve, **Then** a `rule_activation`
  event lists each ACTIVE pack with the glob that fired it (scripts/select_rules.py).
- **Given** a transcript tail carrying the mesh's death keys and no `session_end` event, **When**
  the coroner sweeps, **Then** a reconstructed `death` event exists with joined-or-`unknown`
  exposure fields, the session's run record (if `running`) is closed `verdict: died` stamped
  `closed_by: coroner`, and the session counts in the hole metric
  (scripts/sysadmin/kaizen_coroner.py).
- **Given** a run record still `running` past the TTL with no death evidence, **When** the coroner
  sweeps, **Then** the record closes `verdict: expired` — never left pinning its project.
- **Given** a metric definition registered without a paired counter-metric, **When** the registry
  loads, **Then** it REFUSES the definition (schema constraint, not convention)
  (scripts/sysadmin/kaizen_collect_v2.py).
- **Given** a definition change, **When** the collector recomputes, **Then** a NEW versioned series
  is written alongside history and no published row is overwritten (append-only proven by hash
  comparison in-test).
- **Given** the golden corpus, **When** the daily collector starts, **Then** it asserts expected
  counts BEFORE publishing and refuses to publish on mismatch (instrument health is metric zero).
- **Given** an unmeasurable signal anywhere in the pipeline, **When** a row renders, **Then** it
  prints `—` with its reason, never a fabricated 0 (the honesty rule, inherited).
- **Given** the historical corpus, **When** the backfill runs, **Then** per-metric mean+variance
  land in the noise-floor report with the definition hash they were computed under
  (scripts/sysadmin/kaizen_backfill.py).
- **Given** commits across /opt repos with provenance trailers, **When** the rework miner runs,
  **Then** rework rate = commits whose files are re-touched by a fix-shaped commit within N days,
  reported with its denominator (scripts/sysadmin/kaizen_outcomes.py).
- **Given** the cutover, **When** the daily collector cron is live, **Then** `kaizen_metrics.py` is
  archived (operator ruling executed), its catch-up slot repointed, and the kaizen logs carry the
  new daily rows (scripts/sysadmin/weekly_catchup.sh).

## Global Constraints

- Box-local Python 3.12 stdlib; `uv run pytest` (never bare pytest); no new deps.
- Shared tree, up to 3 concurrent sessions: explicit pathspecs, per-ticket commits with trailers;
  never touch sibling WIP.
- `.claude/hooks/*` + `.claude/settings.json` are FLEET-SYNCED (AGENT_HOOK_FILES in
  `scripts/fabrik_synced_manifest.py:113-121`) — every hook edit must be correct for ALL ~46
  projects, fail-open, and add no per-prompt latency worth noticing (emission is one append).
- The sound system is UNTOUCHABLE (`~/.claude/bin/claude-sound.sh`, operator-standing rule): the
  coroner consumes `/tmp/claude-sound-locks-$UID/*` markers and the notify log READ-ONLY.
- Never-Route: scripts/final_gate.py
- Never-Route: scripts/enforcement/
- Events and derived facts live under `~/.claude/state/` (box-local, never in-repo); event FILES
  are data stores, not logs — the 12-Factor XI stdout-only rule governs process LOGGING, and each
  emitter still logs its own failures to stderr only.
- 12-Factor: config via env with defaults (`KAIZEN_EVENTS_DIR` etc.); no daemons/PID files; no
  backing-service substitution (no DB — flat files by design, spec `:73-74`).
- The honesty rule (binding, inherited from M0): `—` with reason, never 0-for-no-data.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| Spec § Layer 1 | the event vocabulary, per-session files, fail-open law, coroner, versioned recompute, paired counters, golden corpus | `docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md:54-168` |
| Spec § Sequencing M1 | the deliverable list + exit gate (7 days of events is post-plan calendar time) | same file `:462` |
| `core/45-testing-strategy.md` (ACTIVE) | watched-fail-first for every new test; `uv run pytest` | `.windsurf/rules/core/45-testing-strategy.md:21,47` |
| `core/10-python.md` (ACTIVE) | env config via `os.getenv` w/ defaults; no grouped config sets | `.windsurf/rules/core/10-python.md:249` |
| `core/55-observability.md` (ACTIVE) | process logs to stdout/stderr only — event files are data, not logs (distinction stated in Global Constraints) | `.windsurf/rules/core/55-observability.md:62` |
| `core/62-using-subagents.md` (ACTIVE) | dispatcher economics for coder tiers + review floor | `.windsurf/rules/core/62-using-subagents.md:35` |
| `core/40-documentation.md` (ACTIVE) | Doc Sync Matrix rows (INDEX, CHANGELOG, kaizen.md, new subsystem doc) | `.windsurf/rules/core/40-documentation.md:59` |
| Hook wiring (user-level) | which events each hook layer can observe (Stop/StopFailure/PreCompact… are claude-sound.sh — UNTOUCHABLE; emitters go in the PROJECT-synced hooks + new user-level entries ONLY if additive) | `~/.claude/settings.json` hooks block (grounded 2026-08-19) |
| Hook wiring (project-synced) | the writable emitter seams: `final_gate_stop.py` (SessionStart --baseline + Stop), `session_orient.py`, `skill_router.py`, `mail_notify.py`, `agent_role.py` | `/opt/fabrik/.claude/settings.json` + `fabrik_synced_manifest.py:113-121` |
| Run-record machinery | records are per-sid (`<sid>.json` from `CLAUDE_SESSION_ID`); Bash-tool shells have EMPTY `CLAUDE_SESSION_ID` → everything collapses to `nosession.json` (root cause, grounded live) | `scripts/command_run.py:15-16,60-65` |
| Resume-mesh markers (coroner sources, READ-ONLY) | `.errparked` death records + `recheck-busy-*` markers in `/tmp/claude-sound-locks-$UID/`; the five mid-stream death texts + the structural `api_error` key (`retryAttempt == maxRetries`); `isApiErrorMessage` transcript rows | `docs/workstation/hooks-index.md:31,36` (the authority doc) |
| Gate seam | per-check results assemble as `(name, ok, msg)` tuples before the JSON report — the ONE emission point for `gate_run` | `scripts/final_gate.py:416-445,498` |
| Activation seam | `select_rules.py` computes ACTIVE packs + matching globs in `main()`; emits there | `scripts/select_rules.py:144-156` |
| M0 extraction machinery (REUSE, never reinvent) | structure-keyed typed/skill channels, `isSidechain` exclusion, boundary-aware counting, registry-declaration joins, `Signal` honesty type | `scripts/sysadmin/kaizen_shrink_audit.py` (`_typed_names`, `_skill_names`, `collect_*`) |
| What T06 replaces | `kaizen_metrics.py` (weekly, 5 pinned metrics, ISO-week idempotence, analyst-cell preservation) — retire WITH M1 per the operator ruling | `scripts/sysadmin/kaizen_metrics.py` + `docs/workstation/kaizen-shrink-audit.md` § Operator ruling |
| Wake-proof scheduling | any M1 cron uses the stamp-check catch-up pattern | `scripts/sysadmin/weekly_catchup.sh` |
| fabrik-lib consult | **BUILD** — README module table (checked 2026-08-19) has no event-stream/metrics-store module; closest (`app-audit-log`) is a service-side DB audit trail, wrong seam (box-local flat files, zero-dep). 🆕 fabrik-lib candidate: `event-stream` (fail-open typed JSONL emitter + reader; reusable by any project wanting local telemetry; interface: `emit(event, **fields)` / `read(dir, since)`) — propose only, hub creates | `/opt/fabrik-lib/README.md` module table |
| `.md` allowlist | new subsystem doc at `docs/workstation/kaizen-event-stream.md` (box-local system doc, kaizen.md precedent) | CLAUDE.md § HARD STOPS allowlist |
| No `shape:`/deploy | box-local machinery; no service, no spec, no VPS | spec § Shape/infra `:527` |

## File Scope (owned paths)

- scripts/sysadmin/kaizen_events.py
- scripts/sysadmin/kaizen_coroner.py
- scripts/sysadmin/kaizen_collect_v2.py
- scripts/sysadmin/kaizen_outcomes.py
- scripts/sysadmin/kaizen_backfill.py
- scripts/sysadmin/weekly_catchup.sh
- scripts/sysadmin/archived/kaizen_metrics.py
- scripts/sysadmin/kaizen_metrics.py
- .fabrik/liveness-registry.json
- scripts/command_run.py
- scripts/select_rules.py
- scripts/final_gate.py
- scripts/review_rubric.py
- .claude/hooks/final_gate_stop.py
- .claude/hooks/session_orient.py
- .claude/settings.json
- tests/test_kaizen_events.py
- tests/test_kaizen_hook_emitters.py
- tests/test_kaizen_sensor_emitters.py
- tests/test_kaizen_coroner.py
- tests/test_kaizen_collect_v2.py
- tests/test_kaizen_outcomes.py
- tests/test_kaizen_backfill.py
- tests/test_command_run.py
- tests/fixtures/kaizen-golden/
- docs/workstation/kaizen-event-stream.md
- docs/workstation/kaizen.md

## Evidence

- Hook wiring grounded live 2026-08-19: user-level `~/.claude/settings.json` routes
  Stop/StopFailure/Notification/PreToolUse/PreCompact/PostCompact through `claude-sound.sh`
  (UNTOUCHABLE) + SessionStart through the manager tap and session-recall; project-synced
  `/opt/fabrik/.claude/settings.json` routes SessionStart×4 (`final_gate_stop.py --baseline`,
  `session_orient.py`, `agent_role.py`, `mail_notify.py`), Stop (`final_gate_stop.py`),
  UserPromptSubmit×2 (`skill_router.py`, `mail_notify.py`) — the writable emitter seams.
- `nosession` root cause proven live: `scripts/command_run.py:60-61` reads `CLAUDE_SESSION_ID`;
  the Bash tool's shells carry it EMPTY (hit twice on 2026-08-19: closing this session's runs
  resumed two different SIBLING sessions' records from the shared `nosession.json`).
- Coroner sources exist now: `/tmp/claude-sound-locks-1000/` carries live `.recheck-busy-subagent`
  + `.rungsize` markers; `docs/workstation/hooks-index.md:31,36` documents the `.errparked` record,
  the five mid-stream death texts, and the structural `api_error` key.
- `~/.claude/state/events/` does not exist yet (virgin surface — no migration concerns).
- Gate seam: `scripts/final_gate.py` assembles `results` as `(name, ok, msg)` tuples
  (`:416-445`, `:498`) before the `--json` report — one choke point for `gate_run`.
- Activation seam: `scripts/select_rules.py:144-156` prints ACTIVE packs from frontmatter
  glob-matching — the same computation the `rule_activation` event serializes.
- Review convergence (2026-08-19, `/fabrik-plan-review`): 3 rounds — r1 six CONFIRMED
  coder-misbuild tightenings (emitter half), r2 four CONFIRMED (meter half, incl. the
  concurrency-flag definition and golden-mismatch refusal semantics), r3 full-set fresh sweep
  **NO FINDINGS** (the no-op round). Grounded corrections applied mid-review: the hook payload
  sid field EXISTS (`session_id`, `.claude/hooks/session_orient.py:99`), and the record's
  blocking field is `state` (`.claude/hooks/final_gate_stop.py:385,801`), joined by
  `died`/`expired` (`scripts/command_run.py:416` sets `state` to the closing verb). Grammar
  gate clean:

  ```console
  $ python3 scripts/enforcement/check_plan_tickets.py --plan-dir docs/development/plans/2026-08-19-plan-1-kaizen-m1-event-stream
  (no findings)
  $ echo $?
  0
  ```

## Self-audit

- **(a) Coverage vs the M1 row:** emitters (T01–T04) ✓ · exposure metadata (T01) ✓ ·
  `rule_activation` (T04) ✓ · platform-owned lifecycle audit (T03+T05: events cross-checked
  against records; coroner + TTL closure) ✓ · split compliance + outcome tier (T06, T07) ✓ ·
  versioned defs + append-only store + recompute (T06) ✓ · fixtures + golden corpus (T06, per-ticket
  duplex) ✓ · noise-floor backfill (T08) ✓ · paired-counter registry (T06 schema constraint) ✓ ·
  daily cron replaces weekly (T09) ✓ · coroner (T05, L1-REQUIRED) ✓.
- **(b) Cross-ticket signatures:** `emit()`/`exposure()` (T01.Produces) consumed by T02–T05;
  record-close API (T03) consumed by T05; event files consumed by T06; `read_rows`/`metric_registry`
  (T06) consumed by T07/T08 — one vocabulary, stated in § Interfaces with seam-test owners.
- **(c) Honest limits stated in-plan:** the M-gate's "7 days of events" + variance sign-off are
  post-execution calendar time; `rule_activation` measures *invocation-time* activation
  (select_rules/rubric runs), not per-edit glob firing — the per-edit variant needs a PostToolUse
  hook that does not exist today and is recorded as a residual, not silently claimed.
- Fixed point not yet claimed — that is `/fabrik-plan-review`'s flip.

## Residual unknowns

1. **Per-edit `rule_activation`** (which packs' globs matched each edited file, continuously):
   needs a PostToolUse hook surface; M1 ships invocation-time activation (select_rules/rubric
   emission) — honest label in the metric definition; the per-edit upgrade is an M2 candidate.
   Self-service: T04 states the label; no execution blocker.
2. **`CLAUDE_SESSION_ID` in hook processes**: hooks receive a JSON payload on stdin that carries
   the session id (the mesh consumes it today per hooks-index) — T02's first step probes the
   payload shape live and falls back to `unknown`-sid emission if a layer lacks it. Self-service
   probe written into the ticket; no execution blocker.
3. **Fleet-health sweep runtime cost** (clean-worktree build+test per project): T07 caps the pilot
   at the hub + projects with a test suite ≤ a per-project timeout, reports coverage honestly
   (`swept n/46 — the rest —` with reason); widening is post-M1 tuning, not a blocker.
