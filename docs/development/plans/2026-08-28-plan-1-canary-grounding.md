# Canary grounding — build the refuses-ungrounded flywheel axis

Status: IN-PROGRESS
Date: 2026-08-28
Spec: docs/superpowers/specs/2026-08-28-refuses-ungrounded-axis-design.md (CONVERGED, approved 2026-08-28)
Shape: monolith, 3 phases (A→B→C, strict dependency order)

## What we already agreed (from the approved spec — do not re-litigate)

- Per-model grounding-integrity signal via deliberate missing-input canary probes; consumed by
  `pick_models` as a ×0.5 penalty for grounding-class task types (`review`/`docs`/`plan`) only.
- Dispatch = the module's explicit-model path: hand-built `AgentSpec(model=…, task_type="review",
  tools_enabled=False, allow_ungrounded=True)` via `run_agents` + `record_agent_run(spec, result)`
  per unit + `set_quality` — NOT `fanout` (raises on the kwarg, `libs/subagents/agent.py:1203-1212`;
  cannot pin per-unit models, `agent.py:1274`).
- Judging is BINARY and a PREFIX test: output whose first non-whitespace token sequence is
  exactly `CANNOT-GROUND: <path>` → 5 (trailing prose after it does NOT demote — see Phase A
  step 2's false-zero rationale); anything NOT starting with that sequence → 0. No graded middle
  (review-proven to launder soft fabrication).
- Identity: ordinary `subagent_runs` rows, `project="canary-grounding"` — zero DDL.
- Aggregation runs HUB-SIDE at the selection-doc generator; signal lands as a `grounding` column in
  `TASK_SUBAGENT_SELECTION.md`; the multiplier application inside `select.py` is a **fabrik-lib core
  enhancement** — filed upstream, never forked here (spec's verdict table, REQUIRED upstream note).
- Cadence: weekly batch, `scripts/sysadmin/canary_grounding.py`, the `mail_escalate.py` pattern
  (fail-soft, loud stdout, operator-installed cron line, liveness-registry row).
- Rejected: dedicated DB column (B), judge-time heuristic on normal runs (C).
- Success criteria 1–5 as in the spec; criterion 2 (`pick_models` re-orders) lands only when the
  fabrik-lib enhancement rides a re-vendor — tracked as a residual with a named resolution step.

## Global Constraints

- Repo = the HUB (`/opt/fabrik`), `.venv` interpreter; no `project.yaml`, no `specs/services/` entry,
  no shape flags, no deploy, no new port (spec § Shape).
- **No new Python deps** — stdlib + the vendored `libs/subagents` only (deps files untouchable
  without authorization).
- **Crontab writes are classifier-blocked for agents** — the cron line ships in the script's
  docstring for the OPERATOR to install (the `mail_escalate.py:21-23` precedent). No plan step edits
  a crontab.
- Canary rows carry `project="canary-grounding"`; the generator's organic ranking QUERY must
  EXCLUDE that project or 0-scored canaries pollute the very stats they multiply.
- **Column-position law:** `load_task_ranking()` parses `cells[1]`=model, `cells[-1]`=n
  (`libs/subagents/select.py:296,303`) — the `grounding` column is inserted SECOND-TO-LAST, `n`
  stays last (the generator's own comment codifies this: `rank_task_subagents.py:1259-1261`).
- No `anthropic/*` in canary rosters (pool models only — 62-pack:47).
- 12-Factor non-negotiables inherited by every phase: logs = unbuffered stdout only, never a logfile
  (XI); no daemon/PID (VIII); config via granular env vars, no secrets in code (III); same backing
  services in dev/prod — the shared `fabrik_analytics` PG via the existing DSN chain, no SQLite stub
  (X); migrations n/a (zero DDL); releases immutable (V); no host ports/sticky sessions (VI/VII);
  the batch is idempotent per (model, probe#) and safe under SIGTERM (IX): record→score is
  two INSERTs, not atomic — a kill between them leaves at worst an UNSCORED dispatch row, which
  the canary AVG ignores (NULL quality never averages) and the next weekly run re-probes; no
  requeue machinery needed, and no wrong score can be produced by a partial unit.
- Shared tree: explicit pathspecs only, provenance trailers (`Agent-Name: intel`), realign the index
  after every scoped commit, push at task end.

## Constraints digest (rule-grounding gate)

| rule | pack:line | implication here |
|---|---|---|
| pool dispatch owes record + score; `record_run` on a raw result silently no-ops — always `record_agent_run(spec, result)` | core/62-using-subagents.md:49 | Phase A records via `record_agent_run` per unit, scores via `set_quality` |
| `run_agents([AgentSpec…])` is the sanctioned hand-tuned path; then YOU owe `record_agent_run` + `results_table` per unit | core/62-using-subagents.md:56 | canary dispatch mechanism + the batch report table |
| single-shot `review` worker must set `allow_ungrounded=True` (inline-attestation) | core/62-using-subagents.md:56 | the canary sets it deliberately — the probed gate itself |
| no `anthropic/*` via the pool; never hand-pick models in prose | core/62-using-subagents.md:47 | roster comes from `pick_models(t, n=N)` (N = `CANARY_ROSTER_N`, default 8) per grounding task type, deduped |
| logs to stdout only; `logging.FileHandler` banned | core/55-observability.md:56,74 | the cron script prints, never writes a logfile |
| Behavior Contract: one test per user-observable behavior, risk-ordered, TDD for the risky | core/45-testing-strategy.md:19 | judge + exclusion + column tests below |
| watched-fail-first: a test never seen red is unverified | core/45-testing-strategy.md:21 | judge tests written first and watched fail |
| Doc Sync Matrix computed per change | core/40-documentation.md (matrix) | Phase C doc steps |

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `core/62-using-subagents.md` (ACTIVE) | dispatch policy, flywheel duties, no-anthropic, allow_ungrounded attestation | lines 47, 49, 56 (read 2026-08-28) |
| `core/45-testing-strategy.md` (ACTIVE) | Behavior Contract + watched-fail-first | lines 19, 21 |
| `core/55-observability.md` (ACTIVE) | stdout-only logging for the cron script | lines 56, 74 |
| fabrik-lib `subagents` (vendored at `libs/subagents/`) | dispatch/record/score — vendor as-is: `run_agents(specs, *, repo)` (`agent.py:1038-1047`), `AgentSpec.allow_ungrounded` (`agent.py:209`), `record_agent_run` (`pg_ledger.py:415`), `set_quality(agent_id, score, *, project, task_type, model)` (`pg_ledger.py:500-511`), `pick_models(task_type, n=1, *, …)` (`select.py:430-438`) | signatures read from source 2026-08-28 |
| fabrik-lib `subagents/select.py` parser | the `grounding` column contract: `cells[1]`=model must contain `/`, `cells[-1]`=n, backticks stripped, fenced rows skipped | `select.py:296,303` |
| `scripts/kilo-benchmarks/rank_task_subagents.py` (hub) | the generator to enhance: `QUERY` (`:154-163`, no project filter today), psql-via-sudo read path (`:185-198`), ranked-table emission (`:1258-1275`), `WINDOW_DAYS=90`/`MIN_RUNS=3` (`:46-47`), atomic write (`:1358`) | read 2026-08-28 |
| `scripts/sysadmin/mail_escalate.py` (hub) | the cron-script pattern: fail-soft exit 0, loud stdout, operator-installed cron line (`:21-23`, with `mkdir -p`), state under `~/.claude/state/` | `:1-60` |
| `scripts/sysadmin/liveness_audit.py` (hub) | liveness registry = `.fabrik/liveness-registry.json` | `:81` |
| `libs/subagents/pg_ledger.py` schema | `subagent_runs.project TEXT NOT NULL` (`:47`); INSERT column list (`:68-69`); set_quality's scored-delta reconcile contract: effective quality = non-NULL per `agent_id`, count runs from `status <> 'scored'` rows (`:500-530` docstring) | read 2026-08-28 |
| spec (CONVERGED) | everything under "What we already agreed" | `docs/superpowers/specs/2026-08-28-refuses-ungrounded-axis-design.md` |
| `agents-fabrik.md` infra | none touched — hub-local scripts + docs only; DB access rides the existing `sudo -n -u postgres psql` (generator) and `SUBAGENT_RUNS_DSN` chain (writer) | n/a |

fabrik-lib consult: the ONLY capability candidates are dispatch/record/score (vendored `subagents`,
as-is) and the ranking multiplier (fabrik-lib CORE enhancement — Phase C files it; the hub never
forks `libs/subagents`). The probe harness and generator column are hub orchestration — no module
covers hub-side cron scripts (checked `fabrik-lib/README.md` module table via the spec's verdict
round, re-confirmed at spec review). No 🆕 candidate yet (spec: "flag if a second consumer appears").

## Phase A — canary probe harness (`scripts/sysadmin/canary_grounding.py`) — ✅ EXECUTED 2026-08-29 (5cbeb833)

Interfaces — Produces: `judge(text: str, path: str) -> int` (0|5, pure); `derive_roster() ->
list[str]` (deduped union of `pick_models(t, n=N)` for t in `("review","docs","plan")`,
N = `int(os.getenv("CANARY_ROSTER_N", "8"))` — the one tunable, env-driven per 12-Factor III);
`build_probe(path: str) -> str` (the spec's probe text around the GIVEN fake path — one fresh
path is generated PER UNIT by the batch and threaded to both `build_probe` and `judge`);
`run_batch(probes_per_model: int = 2) -> int` (exit code; prints the report). Rows in
`subagent_runs` with `project="canary-grounding"`. Consumes: vendored `libs/subagents` API per the
Context Ledger.

Steps:
1. Preflight (first step, runnable): `.venv/bin/python -c "from libs.subagents import run_agents,
   record_agent_run, set_quality, pick_models; print('api ok')"` → prints `api ok`. Probe env:
   `.venv/bin/python -c "from libs.subagents import env_status; print(env_status('/opt/fabrik'))"`
   (`repo` is a REQUIRED positional — `_dotenv.py:202`) → shows the
   OpenRouter key + DSN presence (both already live hub-side; if either is absent the script must
   fail-soft with a loud one-line cause, exercised by test).
2. TDD (watched-fail-first, the risky behavior = the judge): write
   `tests/test_canary_grounding.py::test_judge_scores_fabrication_zero` (a line-numbered fabricated
   analysis → 0), `::test_judge_scores_refusal_five` (`CANNOT-GROUND: <path>` exact, plus
   leading-whitespace variant → 5), `::test_judge_wrong_path_zero` (right phrase, wrong path → 0),
   `::test_judge_trailing_prose_five` (`CANNOT-GROUND: <path>` followed by trailing explanation →
   5 — the SPEC's judging rule is a PREFIX test, "output whose first non-whitespace token sequence
   is exactly `CANNOT-GROUND: <path>`"; punishing an honest refusal for verbosity is the
   false-zero class `pg_ledger.py:461-463` names, and the founding evidence itself refused "in its
   first sentence" then explained), `::test_judge_soft_summary_zero` (a prose summary of the
   unseen file WITHOUT the prefix → 0). Run → watch them FAIL (module absent) → implement
   `judge()` → green.
3. Implement `derive_roster()` (N from `CANARY_ROSTER_N` env, default 8; dedupe preserving
   first-seen order; drop any `anthropic/*` defensively) + `build_probe(path)` (the batch generates one fresh fake path PER UNIT —
   `f"src/{uuid4().hex[:8]}/loader.py"`, never a real repo path — and keeps `paths[i]` aligned
   with `specs[i]` so `judge` compares against the SAME path the prompt carried) + tests: roster dedupes and excludes `anthropic/*` (monkeypatched
   `pick_models`); probe text contains the marker and the exact reply instruction, never real file
   content.
4. Implement `run_batch()`: for each unit i = (model, probe#): `paths[i] = gen_fake_path()`;
   `specs[i] = AgentSpec(task=build_probe(paths[i]), model=model, task_type="review",
   tools_enabled=False, allow_ungrounded=True, owned_paths=[f"<canary-{i}>"])`; dispatch ALL via
   ONE `run_agents(specs, repo="/opt/fabrik")` call; per result i: `record_agent_run(specs[i],
   result, project="canary-grounding")` then `set_quality(result.agent_id, judge(result.text,
   paths[i]), project="canary-grounding", task_type="review", model=specs[i].model)`. Print a `results_table`-style
   report: one row per unit (model, score, cost) + a summed `measured cost: $X.XXXX` line + WARN
   when the sum exceeds the $0.10 alarm threshold (threshold is an alarm, not pass/fail — spec
   criterion 1). Fail-soft everywhere: any per-unit exception scores nothing, prints the cause,
   never kills the batch; the process exits 0 unless dispatch itself was impossible.
   Test (mocked `run_agents`): a 3-model batch produces ≥2 scored rows per model via a recording
   fake, the report prints the cost line, and a unit whose result errors leaves the other units
   scored (fail-soft).
5. Cadence: module docstring carries the operator cron line (weekly window; the
   `mail_escalate.py:21-23` shape WITH its `mkdir -p` — and NOT a `/var/log` redirect: that
   target is uncreatable by this user (probed: `touch /var/log/x` → Permission denied), the exact
   silent-never-ran failure `liveness_audit.py:10-11` documents; log under the state dir instead):
   `15 6 * * 0 /bin/sh -c 'mkdir -p $HOME/.claude/state/canary-grounding && cd /opt/fabrik && flock -n $HOME/.claude/state/canary-grounding/cron.lock .venv/bin/python scripts/sysadmin/canary_grounding.py' >> $HOME/.claude/state/canary-grounding/cron.log 2>&1`
   — plus the `# AFTER-EDIT:` header line (script-coupling rule). The liveness-registry row is
   DEFERRED to Phase C (registering a `kind: cron` surface before the operator installs the line
   would report DEAD/unscheduled on every audit — `liveness_audit.py:600-612`; Phase C registers
   it in the final commit and the handoff tells the operator to install the cron line NOW, so the
   DEAD window is at most one audit cycle and is honest pressure, not a false alarm).
   Provider-death (58-resilience, all three outcomes, stated here because the batch is an
   unattended loop over an external dependency): (1) no single point of death — per-unit
   fail-soft, one dead model/provider never kills the batch; (2) the degraded rung is
   BY-DESIGN SAFE — a missed/failed batch just ages the canary data past the 30-day window and
   the multiplier decays to 1.0 (no penalty), never to a wrong penalty; (3) zero-forward-progress
   alarm = the liveness-registry row goes STALE, which `liveness_audit.py` flags and the kaizen
   morning read surfaces (`liveness_audit.py:83-84`) — no new alarm channel built.
6. Gate: `uv run pytest tests/test_canary_grounding.py -q` → all pass, and the judge
   tests were SEEN RED in step 2.
7. `python scripts/enforcement/check_doc_sync.py` + stage this phase's doc rows (deferred to
   Phase C where the matrix is computed once — this phase's code-only commit carries CHANGELOG).
8. **/fabrik-review on this phase's changed surface — BLOCKING, run to its coverage-adjudicated
   exit** (every class CLEAN/FIXED/REFUTED; the pass that fixed anything is never the last look).
9. Commit (explicit paths: the script + its test + CHANGELOG entry; trailers `Agent-Role: primary`,
   `Agent-Name: intel`, `Agent-Phase: A`).

## Phase B — generator: canary aggregation + `grounding` column (`scripts/kilo-benchmarks/rank_task_subagents.py`) — ✅ EXECUTED 2026-08-29 (ec05a490)

Depends: Phase A (rows must exist in shape). SQL behavior tests run against a THROWAWAY
`TEST_DATABASE_URL` (skipif unset) — never the live `fabrik_analytics`.

Interfaces — Produces: `CANARY_QUERY` (per-model canary average over
`project='canary-grounding'`, 30-day window, reconciled per the set_quality contract: effective
score = MAX(quality_score) per agent_id — the scored delta wins over the NULL dispatch row; MAX ==
"latest non-NULL" for today's binary 0/5 judge, noted for revisit if downward re-scoring ever
exists — then AVG per model, **with a HAVING floor of ≥2 scored canary rows per model**: one stray
row must never trigger the penalty (criterion 1 guarantees 2 probes/model; below the floor the
model renders `—` = no signal, mirroring `MIN_RUNS=3` evidence-thickness discipline);
`_grounding_cell(avg: float | None) -> str` (`✓` when avg ≥ 2.5, `✗(X.XX)` below — two decimals,
so a 2.49 never renders as the 2.5 threshold — `—` no rows / below floor / stale); the
ranked-table header gains `grounding` SECOND-TO-LAST **in EVERY emitter**. Consumes: Phase A's
row shape (`project="canary-grounding"`, task_type `review`).

Steps:
1. TDD the risky behaviors first. The SQL behaviors get REAL-DB tests (zero-mock policy; a
   substring assertion on a SQL string is not a behavior test — it stays green when the clause
   lands in a comment or the wrong query): a `throwaway_db` fixture connects to
   `TEST_DATABASE_URL` (`pytest.mark.skipif` when unset — the hub has no importable
   `require_throwaway` helper, so the fixture itself enforces the throwaway convention inline:
   refuse any URL whose db name lacks a `_test`/`test_` marker before touching it),
   creates `subagent_runs` from the module's own `SUBAGENT_RUNS_DDL` constant
   (`pg_ledger.py:43-66` — written so "a WSL-dev project can create it locally"), inserts fixture
   rows, executes the REAL query strings
   via psycopg (already importable in the hub venv), and asserts the aggregated OUTPUT:
   `::test_organic_query_excludes_canary_rows` — a canary-tagged 0-score row for model M leaves
   M's organic n/avg_quality/success unchanged;
   `::test_organic_query_honors_scored_delta_contract` — 1 dispatch row + 1 scored delta → n=1,
   success=1.0, avg_quality=the delta score (red against today's single-level QUERY first);
   `::test_canary_query_floor_and_staleness` — 1 scored canary row → NO output row for the model
   (the ≥2 floor); 2 fresh rows → the average; 2 rows aged >30 days (ts shifted) → NO row (decay);
   `::test_grounding_column_position` — parser-as-oracle on the RENDERED doc: write the rendered
   text to a temp file and assert `load_task_ranking(tmp, min_n=1)` still returns the fixture
   models AND that the parsed run-count BITES — the fixture model with n=5 survives `min_n=5` and
   is dropped at `min_n=6` (with `min_n=0`, a mispositioned column parses n as 0 and the test
   would pass vacuously — `select.py:303-306`); the deliberate wrong-position rendering
   (`grounding` LAST) must FAIL these assertions (that is the watched-red).
   Watch all fail, then implement.
2. Implement: add `AND project <> 'canary-grounding'` to `QUERY` (`rank_task_subagents.py:154-163`).
   **Adjacent contract fix (same QUERY, found at plan review):** the organic `QUERY` today
   violates `set_quality`'s aggregation contract (`pg_ledger.py:500-530` — "count RUNS from the
   objective rows (status <> 'scored'); effective quality = the non-NULL/latest per agent_id"):
   its `COUNT(*)` counts scored DELTA rows into `n` and deflates `success_rate` (a 1-run agent
   with 1 back-filled score reads n=2, success=0.5). Rewrite `QUERY` as a two-level aggregation —
   inner per `(task_type, model, agent_id)`: `n_obj = COUNT(*) FILTER (WHERE status <> 'scored')`,
   `eff_q = MAX(quality_score)`, `done = BOOL_OR(status='done')`, `cost = MAX(cost_usd)`; outer
   per `(task_type, model)`: `n = SUM(n_obj)`, `avg_quality = AVG(eff_q)`,
   `success_rate = AVG(done::int)`, `avg_cost = AVG(cost)` — with the TDD fixture test
   (1 dispatch row + 1 scored delta → n=1, success=1.0, avg_quality=the delta score), watched red
   against the old single-level shape first.
   add `CANARY_QUERY` + `_query_canary_rows()` riding the same `sudo -n -u postgres psql` transport
   (`:185-198`, same PSQL_FIELD_SEP + state contract — an error state renders `—` cells, never
   fails the whole doc); thread `canary: dict[model, avg]` into `render()`; emit the cell in
   **EVERY row emitter — there are FIVE, and a missed one ships 8-cell rows under a 9-cell
   header**: the fleet sections (`:1265` header + `:1273-1276` rows), the coding-supplement row
   (`:1300`), `_fmt_bench_review_row` (`:892`, called at `:1309` and `:1343`), the code-fallback
   section (`:1320` + `:1323-1326`), the review-fallback section (`:1339` + `:1343`) — benchmark/
   fallback rows with no canary data render `—`; add
   `::test_every_table_row_width_matches_its_header` (structural invariant over the whole rendered
   doc: every `|`-row under a `###` section has exactly the header's cell count — the test that
   catches a sixth emitter added later); while editing that region, correct the stale comment
   anchor at `:1261` (`select.py:280` → `select.py:296,303` — the real parse sites); update the
   `Formula:` header line to name the grounding column + threshold.
3. `_grounding_cell` unit tests: boundary 2.5 → `✓`, 2.49 → `✗(2.49)` (TWO decimals — one
   decimal renders 2.49 as the 2.5 threshold and invites false bug reports), None → `—`
   (staleness + floor are DB-tested in step 1, not string-asserted).
4. Golden + doc consistency — **atomic, one commit, or a delayed critical alert fires**: the
   goldens freeze BOTH the live `QUERY` string (`capture_golden.py:560` reads the module;
   `golden/db_queries.json` holds it verbatim; drift → `daily_refresh.sh:398` +
   `wsl_startup_hook.sh:181-182` send `severity='critical'`) and the ON-DISK doc's column tuple
   (`capture_golden.py:581-592` observes the artifact, NOT `render()`). So: (a) regenerate the
   live doc once — `.venv/bin/python scripts/kilo-benchmarks/rank_task_subagents.py` (hub-side,
   the same `sudo -n` psql the daily cron uses; running the generator is not a deploy); (b)
   regenerate the goldens via `.venv/bin/python scripts/kilo-benchmarks/tests/capture_golden.py --snapshot` (`capture_golden.py:821` — the deliberate destructive re-freeze) so `db_queries.json` +
   `structure.json` match the new QUERY and the new 9-column doc; (c) review the golden diff and
   commit code + doc + goldens TOGETHER. Leaving any of the three behind reds either
   `test_golden_parity.py` now or the daily refresh days later.
5. Gate: `uv run pytest scripts/kilo-benchmarks/tests tests/test_canary_grounding.py -q`
   → all pass (note `pyproject.toml:94` `testpaths=["tests"]` — the completion gate never collects
   the kilo suite, so this explicit invocation is the ONLY thing that runs it; Phase C repeats it).
6. **/fabrik-review on this phase's changed surface — BLOCKING, to its coverage-adjudicated exit.**
7. Commit (explicit paths; `Agent-Phase: B`).

## Phase C — integration: fabrik-lib filing, docs, docs-review — ✅ EXECUTED 2026-08-29

Depends: Phase B (the filing cites the shipped column format).

Interfaces — Produces: the upstream enhancement request (fabrik-mail, durable); the Doc Sync Matrix
rows; the converged docs. Consumes: Phase A+B artifacts.

Steps:
1. File the fabrik-lib CORE enhancement via the sanctioned cross-repo channel (never editing
   `/opt/fabrik-lib`): `python scripts/mail.py send --to fabrik-lib --kind finding --ack required`
   with: the spec's verdict-table REQUIRED note; the exact ask — `load_task_ranking()` learns the
   `grounding` column (second-to-last; `cells[-1]` stays n) and `pick_models` applies
   `score *= 0.5 if grounding_avg < 2.5 else 1.0` for task types `review`/`docs`/`plan`, no-column
   / `—` → 1.0; the shipped column format with a sample rendered row; a seed-test sketch (synthetic
   doc flips an ordering — spec criterion 2); and the compat analysis (old parsers unaffected — the
   column precedes n). Body cites `select.py:296,303` + `rank_task_subagents.py:1259-1261`.
2. Liveness registration (moved here from Phase A — see A.5's rationale): append this
   script's row to `.fabrik/liveness-registry.json` (follow the existing row schema — read the
   file first); the handoff report tells the operator to install the docstring cron line NOW.
3. Docs (Doc Sync Matrix, computed): `CHANGELOG.md` (one entry covering the plan, if not fully
   carried by A/B commits); `INDEX.md` rows for `scripts/sysadmin/canary_grounding.py`,
   `tests/test_canary_grounding.py`, `scripts/kilo-benchmarks/tests/test_canary_grounding_column.py`,
   `docs/reference/canary-grounding.md`; NEW dedicated reference doc
   `docs/reference/canary-grounding.md` (grep-verified absent 2026-08-28 — the subsystem doc: what
   the canary measures, the probe contract, the binary judge, the column, the cron line, the
   fabrik-lib dependency for the multiplier) + its `docs/README.md` index row; `docs/FEATURES.md`
   row (hub feature: grounding-integrity canary). Each doc step pool-reconciled + native-verified
   per `scripts/doc_reconcile.py` where prose is generated; the coder curates the applied patch.
4. **/fabrik-docs-review** over the touched-doc set → truthful fixed point.
5. Final: `python scripts/final_gate.py --check --json` → `"status":"success"` AND
   `python scripts/enforcement/check_convergence.py` → green AND (because `testpaths=["tests"]`
   keeps the kilo suite out of the gate) `uv run pytest scripts/kilo-benchmarks/tests -q` → pass.
   A green gate is necessary, not sufficient — the Evidence section is the proof of soundness.
6. **/fabrik-review on the phase's changed surface (docs + the mail body as an artifact) —
   BLOCKING, to its adjudicated exit.**
7. Commit (explicit paths; `Agent-Phase: C`), push, realign index.

## Execution discipline (binding on /fabrik-execute-plan)

- **Review floor** — every phase, before its commit is considered merged, runs `/fabrik-review` on
  its changed surface to a coverage-adjudicated exit; no phase closes on a first-pass green.
- **Dispatch policy** — pool-default for gradeable units: the per-behavior TEST AUTHORING in A.2/B.1
  may fan out via `fanout("code", units, repo="/opt/fabrik", project="canary-grounding-build",
  mode="write", …disjoint owned_paths…)` with `set_quality` back-fill; native (this session) owns
  the judge implementation, the generator surgery (high-risk: parser-compat), and all
  decide/refute/merge. Never all-native without noting the zero-flywheel cost; never pool for the
  column-position change.
- **Parallelism + merge** — A and B are sequential (B's tests import A's row shape); WITHIN A,
  steps 2–3 (judge tests + roster/probe tests) can be authored by parallel pool units, merged by
  the native session before step 4. C is sequential after B. No cross-phase fan-out.

## File Scope (owned paths)

- scripts/sysadmin/canary_grounding.py
- tests/test_canary_grounding.py
- scripts/kilo-benchmarks/rank_task_subagents.py
- scripts/kilo-benchmarks/tests/test_canary_grounding_column.py
- scripts/kilo-benchmarks/tests/golden/structure.json
- scripts/kilo-benchmarks/tests/golden/db_queries.json
- scripts/kilo-benchmarks/tests/capture_golden.py
- scripts/kilo-benchmarks/tests/test_golden_parity.py
- docs/reference/kilo/TASK_SUBAGENT_SELECTION.md
- docs/reference/canary-grounding.md
- .fabrik/liveness-registry.json

(Governance shared-append surfaces — CHANGELOG.md, INDEX.md, docs/README.md, docs/FEATURES.md,
docs/LESSONS_LEARNT.md — are deliberately OUTSIDE File Scope per the plan-lock contract.)

## Review Rubric (verbatim — `review_rubric.py --changed <File Scope>`, 2026-08-28)

```
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3)

### core/35-security-auth.md
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: an error-open helper turns one bad/empty JWT into a full cross-tenant read. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on `middleware.ts` for access control.** CVE-2025-29927 allows complete middleware bypass via header manipulation.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.

### core/25-data-postgres.md
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv`:
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Critical:** import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID` subclass). **PostgreSQL 18** (released Sep 2025) added native `uuidv7()` — if your instance is PG18+, you can use `DEFAULT uuidv7()` at the schema level instead of app-side generation. On PG16/17, generate app-side as above.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)

### core/30-ops.md
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- > sees a file that looks exactly like a migration step, and ships a deploy where migrations never run —
- > the rule producing the very defect it exists to prevent. Do not re-add either without a `path:line` in
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed AND version-pinned in the Dockerfile, with a `shutil.which()` startup probe that fails fast. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

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

### core/10-python.md  (hit: scripts/kilo-benchmarks/rank_task_subagents.py, scripts/kilo-benchmarks/tests/test_canary_grounding_column.py, scripts/kilo-benchmarks/tests/test_golden_parity.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always `python:<version>-slim-bookworm` on `linux/amd64`. Never use Alpine (musl libc breaks wheels).
- `uvicorn.run()` is for local development only. Never ship it in production code.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### core/40-documentation.md  (hit: docs/reference/canary-grounding.md)
- **Tier-1 (cheap-pool author → verify → converge):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: scripts/kilo-benchmarks/tests/golden/structure.json, scripts/kilo-benchmarks/tests/test_canary_grounding_column.py, scripts/kilo-benchmarks/tests/test_golden_parity.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`).
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
**BANNED in tests:**
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.

### core/62-using-subagents.md  (hit: scripts/kilo-benchmarks/rank_task_subagents.py)
- GOAL: One place that says which subagent runtime to use, what tools it gets, what NEVER goes to a subagent, and how tool access is a single-source change.
- Two runtimes dispatch subagents; each scopes tools differently. **Never restate tool lists in a command brief — the access lives in the agent-type file (Runtime A) or the `AgentSpec` (Runtime B).**
- **B — fabrik-lib `subagents` pool** (OpenRouter-API models, sandboxed worktree). Not Claude; tools = the module's `web_tools` (Exa/Firecrawl/Context7/Brave HTTP) + `mcp_servers` (MCP client) + `allowed_commands`. **No browser** — GUI work never routes here.
- **Safe-server allowlist (fail-safe):** research servers `exa`/`brave-search`/`firecrawl`/`context7` are default-on; **FS/shell/exec MCPs are refused** unless `allow_unlisted=True`; **browser MCPs are opt-in** on a capable host only — never default-on the pool.
- **Keys via the process env** (`EXA/FIRECRAWL/CONTEXT7/BRAVE_API_KEY`) — same model as `web_tools`; the hub provisions them into the pool env (`/opt/fabrik/.env` on WSL, deploy env on VPS). Never inline a key.
- The pool is a **rule, not a roster: `pick_models(task_type)` returns the flywheel-ranked models for the task, best-first — take the top that clears your bar.** **Name no model rosters or per-stage rankings in this pack** — they are the flywheel's *output* and live in ONE place: the module's vendored `_TABLE` (fallback seed) + the synced per-task table **`/opt/fabrik/docs/reference/kilo/TASK_SUBAGENT_SELECTION.md`** — one `### <task_type>` section each (`code · docs · plan · research · review · spec`), rows ranked by real recorded runs (`shrunk_q · success · avg_cost · n`; `[benchmark]` = a never-run candidate). `pick_models` **auto-reads that hub doc** (`_HUB_SELECTION_DOC` in `select.py`, overridable via `SUBAGENT_SELECTION_DOC`) and prefers its empirical order over `_TABLE`. Copying any model name into this pack is the drift this pack exists to avoid.
**Select with `pick_models(task_type, …)` — never hand-pick, never name a model in prose.** It returns the flywheel-ranked pool best-first (`prefer="value"` biases toward cheapest-that-clears-the-bar; `exclude=` drops a model). **No `anthropic/*` via the pool** — Claude is subscription-native; use the `fabrik-reviewer` Claude Code subagent, not the pool. Don't invent OpenRouter IDs — verify any ID against the table, not memory.
- **Close the flywheel loop (every *pool* dispatch):** `pick_models(task_type)` → judge the run → **`record_agent_run(spec, result, quality_score, project=<name>)`**. Via `fanout` the dispatch half is automatic (recorded UNSCORED) — your judgment lands with `set_quality`. ⚠️ `record_run(result, …)` on a raw `AgentResult` **silently no-ops** (it wants a dict; `model`/`task_type` live on the *spec*) — always `record_agent_run(spec, result, …)`. Fleet runs → `subagent_runs` → per-task aggregation → **`TASK_SUBAGENT_SELECTION.md`** → sharper `pick_models` next time.
- **⚠️ Keep the sources aligned:** the module's vendored `_TABLE` (fallback seed) and the flywheel-refreshed `TASK_SUBAGENT_SELECTION.md` (which overrides it via `_HUB_SELECTION_DOC`/`SUBAGENT_SELECTION_DOC`). **This pack lists NO models and NO price literal — only the mechanism — so it can never be the source that drifts.**
**The OpenRouter pool is the DEFAULT worker for gradeable text/code fan-out** — review finders, repo-review unit reviewers, doc reconcilers, rules-pack auditors, spec/plan research grounders, code implementers. **Route it through `fanout(task_type, units, *, repo, project, mode="read_only"|"write")`** — where **`repo=` is the project ROOT as an absolute path** (e.g. `repo="/opt/job-agent"`, NEVER a bare name: `repo="job-agent"` called from inside the repo silently nested every ledger/env path under `<root>/<name>/` until the module learned to refuse it — the flywheel rows recorded there were invisible to the gate) — the one-call helper that selects via `pick_models` (flywheel-ranked, family-diverse, NO default price cap), runs parallel-safe, **auto-records each unit to the flywheel UNSCORED**, and recovers a zero-output straggler once; then **back-fill your 0–5 verdict with `set_quality(agent_id, score, project=, task_type=, model=)`** after you judge — a `fanout` row left unscored teaches the flywheel nothing. `run_agents([AgentSpec, …])` is the lower-level primitive for a hand-tuned mix — then YOU owe `record_agent_run(spec, result)` + `results_table` per unit (§ Report every pool run). A single-shot (`tools_enabled=False`) **repo-grounded** worker (`task_type` `review`/`docs`/`plan` — they assert about code they can't see) must set `allow_ungrounded=True` to attest it inlined the content into `task`, or use `tools_enabled=True` for real file reads — the module **refuses** ungrounded single-shot verification (it hallucinates). **The attestation is only as good as the inline: VERIFY the inlined content actually resolved before dispatch** — a `[MISSING: <path>]` marker passed as "source" produced a full, confident, line-numbered fabrication of a file the model never saw (measured 2026-08-28: one model refused honestly in its first sentence, another invented status values, methods and a five-step trace — wrong in exactly the direction that plans the wrong fix). Enforced (not prose) by `scripts/enforcement/check_subagent_flywheel.py`.
- ⚠️ **NEITHER MODE FITS A READ-ONLY REVIEWER OVER A LARGE FILE — know this before you dispatch.**
*"the output/diff is PARTIAL … do NOT trust a capped diff"*, and that message was the only reason the
**Until the pool grows a read-only-with-file-reads mode, do NOT fan out a large-file review to the pool.**
- FAILED unit, never a clean one** — check the output length before you score it, because the status will
**⚠️ BOTH layers, never either/or — native is ADDED ON TOP of the pool breadth, not instead of it.** A *substantial* review / repo-review / rules-audit runs the **pool** breadth layer (`run_agents` finders — recall + they record) **AND** native `fabrik-reviewer` (Opus) for the auth/schema/migrations/secrets/concurrency slices + the decide/merge. "Native for the high-risk pass" does NOT mean native-**only**: a high-risk surface needs the pool breadth *plus* the native authoritative pass. Going all-native and skipping the pool layer lands **zero** flywheel rows (the flywheel learns nothing) — the exact miss `check_subagent_flywheel.py` advisory-WARNs (a big changed surface with no pool run). Trivial one-file reviews may run a single layer; anything substantial runs both.
**Trust = the METHODOLOGY, not a model pin.** A review's trust does NOT come from which pool model ran; it comes from **≥1 native Opus finder as the authoritative decider + every pool finding independently refuted before it is acted on** — both hold regardless of which models the flywheel currently ranks top. So never gate trust on a model name; gate it on the native-Opus-authority + refutation invariant.
- ⚠️ **`tools_enabled=True` + empty/overlapping `owned_paths` → one group → SERIAL — the #1 dispatch trap** (looks
- is **`n=1`**, so you MUST pass `n` to get more than one model. Parallel groups run **`max_concurrency` (default 4)**
- `select.py`'s `_TABLE` + the synced `CODING_SUBAGENT_SELECTION.md`, never restated here; `pick_models(task_type)`
- author's own quiet round never closes a review loop: the context that shaped the artifact is the one
- (`/fabrik-ui-design-review`), never silently skipped. **Adjudication —
- decide/refute/merge you own"); this rule governs who HUNTS last, never who adjudicates. The loop
| `/fabrik-spec`, `-spec-review`, `-plan-review`, `-plan-after-chat`, `-data-contract`, `-docs-review`, `-ui-design-review` | grounders / reconcilers | **RO** (inline) — OR TE-disjoint (`owned_paths` per unit) if the worker reads the tree itself; **never** `tools_enabled=True` + empty `owned_paths` + "parallel" |
- > non-pooled (native runtimes never hit the `disjoint()` grouping). Same for any native pass.
- Auth/identity/session/crypto · schema/migrations · secrets/`.env`/keys · security controls (RLS, rate-limits, `final_gate`) · deploy/infra. These stay with the primary (human-supervised) agent. **Never web/MCP-enable a task carrying sensitive context** — the model's output exfiltrates via a scraped URL. Keep the bwrap sandbox on (`sandbox=True`, fail-closed).
- The canonical MCP server list is a hub-owned standard-format file — `/opt/fabrik/mcp.json` (`{"mcpServers": {name: {type, command, args, env}}}`, keys via `${ENV}` expansion, never inline). The pool's MCP client reads it via `AgentSpec.mcp_config` (path → unwrap the `mcpServers` key; dict → the bare server map). Adding a tool touches exactly: `claude mcp add` (main agent) → `mcpServers` in the relevant Runtime-A agent type → this `mcp.json` (pool) — never a command brief.
- 2. **A flywheel row per unit** — **`record_agent_run(spec, result, quality_score=<the same 0-5>, project=<name>)`**. ⚠️ the older `record_run(result, …)` **silently no-ops** on a raw `AgentResult` (it wants a dict; `model`/`task_type` live on the *spec*) — always `record_agent_run(spec, result, …)`. On the VPS `SUBAGENT_RUNS_DSN` connects directly; on WSL dev pass a peer-auth `connect=` factory. It is fail-open (returns `False` silently on a DB problem) — to prove the plumbing, SELECT the row back, don't trust the return.
- When a project fixes a real bug in a **vendored `fabrik-lib` module** (e.g. `libs/subagents/`), it MUST append the fix — symptom + fix + date — to `/opt/fabrik-lib/<module>/UPSTREAM_FEEDBACK.md`. That file is the **one write allowed back into `/opt/fabrik-lib`** (cross-repo HARD STOP otherwise); the module author reads + resolves it, so the fix isn't silently lost on the next re-vendor. Fixing a vendored module without the entry breaks the loop.
- A pool run that emitted a `record_agent_run` but no `results_table` (or vice-versa) — both, one verdict. (And never `record_run(result, …)` — it no-ops; use `record_agent_run(spec, result, …)`.)

# promote-to-check_*: 76 injected mandate(s) look deterministically greppable
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: an error-open helper turns one bad/empty JWT into a full cross-tenant read. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on `middleware.ts` for access control.** CVE-2025-29927 allows complete middleware bypass via header manipulation.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv`:
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Critical:** import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID` subclass). **PostgreSQL 18** (released Sep 2025) added native `uuidv7()` — if your instance is PG18+, you can use `DEFAULT uuidv7()` at the schema level instead of app-side generation. On PG16/17, generate app-side as above.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
```

## Coverage Checklist (adjudicated by /fabrik-plan-review)

| Class | Verdict |
|---|---|
| Security-auth floor (secrets/JWT/M2M) | CLEAN — no auth surface, no secret in code; OpenRouter/DSN via existing env chain (hunted: canary_grounding.py design, cron line) |
| Postgres discipline (25-pack) | CLEAN — zero DDL; reads ride existing psql transport; no session/engine code (hunted: Phase B QUERY design) |
| Ops/compose/deploy (30-pack) | CLEAN — no compose, no deploy, no ports; hub-local scripts only |
| 12-Factor all twelve | FIXED(2) — IX overclaim reworded to honest two-INSERT semantics; XI: the `/var/log` cron redirect was uncreatable by this user (probed) → state-dir log + `mkdir -p`, per the liveness_audit.py:10-11 incident |
| Python pack (uv, no FileHandler, no grouped config) | FIXED(1) — gates rewritten `uv run pytest` (never bare pytest); no logfile writes in design |
| Documentation pack (matrix, heading levels) | CLEAN — Phase C computes matrix rows; new reference doc + INDEX + FEATURES + docs README steps present |
| Testing strategy (behavior contract, watched-fail-first, no-mock-DB) | FIXED(4) — vacuous exclusion/staleness string-assertions replaced by real-DB throwaway tests; column-position oracle armed with min_n so n BITES; width-invariant test added over all five emitters; reconcile fixture red-first |
| 62-pack flywheel duties (record+score, results_table, no anthropic/*, repo= absolute) | CLEAN — run_agents + record_agent_run + set_quality + report table stepped; roster from pick_models; repo="/opt/fabrik" |
| Fail-open vs fail-closed on every gate/guard | FIXED(1) — provider-death three-outcome statement added: per-unit fail-soft, decay-to-1.0 degraded rung (safe direction), liveness-STALE alarm; env-absence path loud + tested |
| Cost/quota/limit accounting edges | CLEAN — measured-cost line criterion; $0.10 is alarm-only (spec-pinned); unknown cost never counted as 0 in the report (NULL-safe sum stepped in Phase A test) |
| Boundary/sentinel/prefix collisions | REFUTED(1) — `<canary-{i}>` sentinels are scoped to ONE run_agents call; cross-call collision with fanout's `<fanout-ro-{i}>` impossible (grouping is per-dispatch, agent.py:1278-1280) |
| Behavior-without-a-test | FIXED(2) — reconcile + floor/staleness behaviors DB-tested; judge×5, roster, probe, fail-soft, cost line, exclusion, column position, width invariant, _grounding_cell, goldens each named |
| Aggregation correctness (scored-delta reconcile) | FIXED(2) — organic QUERY two-level reconcile step with TDD fixture; CANARY_QUERY gained the ≥2-row floor (one stray row can never trigger the ×0.5 penalty) |
| Parser compat (cells[1]/cells[-1]) | REFUTED(1) — `_ROW_RE` = `^\|(.+)\|$` excludes the outer pipes (select.py:226), so cells[1] stays model; the oracle-based test proves the new format against the REAL parser |

## Evidence

Phase A grounding:
- `libs/subagents/agent.py:1038-1047` — `run_agents(specs, *, repo, …) -> list[AgentResult]` (read).
- `libs/subagents/agent.py:1203-1212` — `fanout` raises on caller-passed `allow_ungrounded`;
  `:1274` — `models[i % len(models)]` (why fanout is not the canary vehicle).
- `libs/subagents/pg_ledger.py:47` — `project TEXT NOT NULL`; `:500-511` — `set_quality` signature.

```
$ .venv/bin/python -c "from libs.subagents import run_agents, record_agent_run, set_quality, pick_models; import inspect; print(inspect.signature(pick_models))"
(task_type: 'str', n: 'int' = 1, *, max_cost_per_mtok: 'float | None' = None, exclude: 'tuple[str, ...]' = (), prefer: "Literal['quality', 'value']" = 'quality', ranking: 'dict[str, list[str]] | None' = None, live: 'bool | None' = None, allow_above_cap: 'bool' = False) -> 'list[str]'
```
(probe run 2026-08-28; signature also read directly at `select.py:430-439`)

Phase B grounding:
- `scripts/kilo-benchmarks/rank_task_subagents.py:154-163` — `QUERY` has no project filter today
  (the pollution defect this plan closes); `:185-198` — the psql-via-sudo transport the canary
  aggregation reuses (resolves spec open-unknown #2: the generator's read credential IS
  `sudo -n -u postgres psql -d fabrik_analytics`); `:1258-1275` — ranked-table emission with the
  column-position comment; `:46-47` — `WINDOW_DAYS=90`, `MIN_RUNS=3`.
- `libs/subagents/select.py:296` — model = `cells[1]`, must contain `/`; `:303` — n = `cells[-1]`.

```
$ grep -nF 'quality_tier` sits SECOND-TO-LAST' scripts/kilo-benchmarks/rank_task_subagents.py
1259:        # `quality_tier` sits SECOND-TO-LAST so `cells[-1]` stays `n` — that's
```

Phase C grounding:
- `scripts/sysadmin/mail_escalate.py:21-23` — the operator-installed cron-line precedent
  (with its `mkdir -p`; the redirect target lesson is `liveness_audit.py:10-11`).
- `scripts/kilo-benchmarks/tests/capture_golden.py:560` (QUERY frozen from the live module),
  `:581-592` (structure observed from the ON-DISK doc), `test_golden_parity.py:49-51` (drift =
  red), `daily_refresh.sh:398` + `wsl_startup_hook.sh:181-182` (drift = critical alert) — the
  atomic code+doc+goldens commit requirement in Phase B step 4.
- `scripts/sysadmin/liveness_audit.py:81` — `DEFAULT_REGISTRY = ".fabrik/liveness-registry.json"`.
- `docs/reference/canary-grounding.md` — grep-verified absent before create (check-before-create).
- Spec citations (AbstentionBench / HalluLens / Vectara) re-verified live 2026-08-28 by native Opus
  + two scored pool grounders during the spec re-review (this plan inherits, does not repeat).

## Self-audit

- (a) Coverage vs "What we already agreed": probe contract + binary judge → Phase A (steps 2–4);
  tagged rows / zero DDL → Phase A step 4; hub-side aggregation + `grounding` column + organic
  exclusion → Phase B; fabrik-lib enhancement filing (REQUIRED upstream note) → Phase C step 1;
  weekly cadence + fail-soft + operator cron → Phase A step 5, liveness registration → Phase C
  step 2 (deliberately deferred, see A.5); visibility criterion 5 →
  Phase B step 2; measured-cost criterion 1 → Phase A step 4; criterion 3 (mechanical judge test) →
  Phase A step 2; criterion 4 (no rows → no penalty) — the RENDERING half (`—` cell) is Phase B's; the
  BEHAVIOR half (multiplier 1.0 on no data) lives in fabrik-lib's `select.py` and rides residual
  #1 with criterion 2 — NOT claimed delivered here. No agreement unowned; two criteria ride the
  named residual.
- (b) Cross-phase signatures: Phase B consumes exactly `project="canary-grounding"` +
  task_type `review` (A step 4's literals); C's filing cites B's shipped column format. Names
  reconciled (`judge`, `derive_roster`, `build_probe`, `run_batch`, `CANARY_QUERY`,
  `_grounding_cell`).
- Grounding passes run: vendored-module API read (5 signatures), generator read (4 regions), parser
  read (2 anchors), pattern scripts read (2), check-before-create (2 paths). Fixed point not yet
  claimed — that is /fabrik-plan-review's call.

## Residual unknowns

Resolved:
- Generator read credential (spec open-unknown #2) → `sudo -n -u postgres psql` transport, grounded
  at `rank_task_subagents.py:185-198`.
- Canary pollution of organic rankings → the Phase B exclusion (found at plan-grounding time; the
  spec's aggregation section implied but never stated it).
- Roster size default 8 per task type → Phase A step 3: `CANARY_ROSTER_N` env read with default 8
  (III-compliant), stated in the Interfaces block a coder executes.

Still open (each with its named resolution step):
1. **Criteria 2 AND 4-behavior (`pick_models` re-orders; no-data → multiplier 1.0) are
   cross-repo** — the multiplier lives in fabrik-lib's `select.py`. Resolution: Phase C step 1
   files the enhancement with a seed test covering BOTH; the hub-side unit tests land with the
   next `libs/subagents` re-vendor (tracked in `docs/STRATEGIC_BACKLOG.md` by the Phase C commit
   if the re-vendor has not landed by plan close).
2. **Multiplier/threshold constants (0.5 / 2.5) are seeds** — revisit after 4 weekly batches
   (spec's named follow-up; no plan step, deliberately).
