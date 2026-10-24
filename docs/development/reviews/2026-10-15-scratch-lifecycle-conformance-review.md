# Conformance review — scratch lifecycle (W-a71b3926)

**Status:** CONVERGED
**Command:** /fabrik-conformance-review · scoped to ONE spec↔plan pair (coordinator brief, W-a71b3926, P1, D-880)
**Surface:** `git rev-parse HEAD` = bdbadb76981b835a0e1266911dbe3e7bdea89e4f; inventory md5: spec `4ba81817559b240520ee933ce37a2657`, plan `eb065e6c1d7b294e22d235c4935410c8`
**Reviewer:** intel (non-author; fleet built it)

Anchor: no earlier conformance ledger for this scope exists under `docs/development/reviews/`, so pass 1 is a full pass.

## Inventory

| Spec | Plan | Status at HEAD | Verdict |
|---|---|---|---|
| `docs/superpowers/specs/2026-10-15-scratch-lifecycle-design.md` | `docs/development/plans/2026-10-15-plan-1-scratch-lifecycle.md` | plan EXECUTED 2026-10-15 (Phase A 5bed978ff, B 6caff3202, C 39d665c65, Finish 5b44c86f9) | PARTIAL — 15 CONFORMS, 8 PARTIAL, 0 DEVIATES; open findings F1-F3, F5, F7-F12 + refreeze debt R1 |

### Behaviour verdicts

| Behaviour | Verdict | Evidence (fresh run) | Gaps (`path:line`) |
|---|---|---|---|
| A1 | PARTIAL | graders 393 passed rc 0 (189.5 s, this session); probe (pass 2): `classify_run_folder` on the pinned module | F10 a `done` marker whose `closed_at` is NaN or -inf classifies `consumed` (`scripts/scratch_sweep.py:727-732` admits any float, `:441` compares it) — the 'on doubt, ACTIVE' rule breaks; same hole in `gap_keeps` for a NaN `created` (`:505-512`) |
| A2 | PARTIAL | live `.owner` on this run's folder carries every field, repo `/opt/fabrik/.git` | test slug covers `_` only; a live `.` slug works (recorded, not a defect); F12 an empty or all-punctuation `--command` mints `run-<started_at>-<hex>` (`scripts/command_run.py:2112`, `:1432`, `:1567`), which `RUN_KEY_RE` rejects (`scripts/scratch_sweep.py:515-517`), so the folder is judged by age, not by its marker |
| A3 | CONFORMS | graders 393 passed rc 0 (189.5 s, this session) | — |
| A4 | CONFORMS | graders 393 passed rc 0 (189.5 s, this session); graders renamed (`test_nested_close_marks_its_own_folder`, `test_close_without_run_scratch_is_unchanged`) — the 4 'uncollected' names REFUTED | a nested close under `blocked --wall` has no test (recorded) |
| A5 | CONFORMS | graders 393 passed rc 0 (189.5 s, this session) | — |
| A6 | CONFORMS | live: marker mtime 1792063748 → 1792063870 across one `step`; the bump sits in the step branch `scripts/command_run.py:6284` | — |
| A7 | CONFORMS | graders 393 passed rc 0 (189.5 s, this session) | — |
| B1 | PARTIAL | graders 393 passed rc 0 (189.5 s, this session) | F1 `tests/test_scratch_sweep_run_folders.py:345` asserts `.trash-big` absent, but the fixture's trash name is `.trash-big-<key>` (:262) — the no-walk half is vacuous; F2 `scripts/scratch_sweep.py:568-598` `git_pointer_files` is a depth-3 scan with no breadth budget (budget suggestion) |
| B2 | PARTIAL | graders 393 passed rc 0 (189.5 s, this session) | F3 case (a) of `test_active_condition_keeps` never makes the session live, so it passes on another ACTIVE condition — code conforms, the test does not discriminate |
| B3 | CONFORMS | graders 393 passed rc 0 (189.5 s, this session) | — |
| B4 | CONFORMS | graders 393 passed rc 0 (189.5 s, this session) | a different-command plain start over a wall record leaves it `resumable` — alarm-only by design (plan I9) |
| B5 | PARTIAL | graders 393 passed rc 0 (189.5 s, this session); closing seat probe: the `--dead` idleness walk handed the session directory | F9 `newest_mtime(sid_dir, …)` (`scripts/scratch_sweep.py:2321`) walks the whole session directory, run folders included (`:1096` skips nothing); the plan's 'patched to raise' guard (`tests/test_scratch_sweep_run_folders.py:318-327`) raises only on a path containing `/run-`, so it never fires. Fail-safe (a cut walk leaves the session unclassified), but a large run folder costs a full walk each night |
| B6 | CONFORMS | graders 393 passed rc 0 (189.5 s, this session) (golden table captured before Phase B) | — |
| B7 | CONFORMS | live: `.run-folders.lock` created at this run's `start` (D3 launched); launch after the lock drops (`scripts/command_run.py:3903-3906`), exact argv asserted (`tests/test_command_run_scratch.py:1028`) | F4 (recorded, A3 degradation): the mint resolves the session directory from `os.getcwd()` (`:5941`), D3 from the toplevel (`:5988`); from a subdirectory with a sid that has two slug directories the mint refuses (`:1648`) and prints `RUN-SCRATCH: none` |
| B8 | PARTIAL | graders 393 passed rc 0 (189.5 s, this session) | F5 `--strict-proc` never reaches run folders in `--dead` (`scripts/scratch_sweep.py:2389`, run rows planned at :2410) nor in session mode (`:2082`, `consumed` is outside `_allowed_classes`, removal at :2110-2119), against the flag's contract (:33); D-877's gap rule still keeps a gap that started after the marker (`:510`); F11 `_holds_backup` prunes every `run-`/`.trash-` prefix (`scripts/scratch_sweep.py:279`), not the minted key (`:521-524`) — a dead session whose only backup sits in an agent's own `scratchpad/run-tests/` is removed whole (probe, pass 3) |
| B9 | CONFORMS | graders 393 passed rc 0 (189.5 s, this session) | — |
| B10 | CONFORMS | graders 393 passed rc 0 (189.5 s, this session) | — |
| B11 | CONFORMS | graders 393 passed rc 0 (189.5 s, this session) | `--retire` returns before the per-session lock (`scripts/scratch_sweep.py:1024-1025`); it marks, it removes nothing — recorded |
| B12 | CONFORMS | graders 393 passed rc 0 (189.5 s, this session) | — |
| C1 | PARTIAL | graders 393 passed rc 0 (189.5 s, this session) | F8 spec D5 (spec :88) asks for a deadline per seat folder; `_seat_size_lines` spends one shared deadline over every seat (`scripts/command_run.py:1782`, `:1791`), so a slow first seat leaves later small ones 'unmeasured'; a `du` that fails prints nothing (`:1797-1798`, recorded) |
| C2 | CONFORMS | graders 393 passed rc 0 (189.5 s, this session); the writer is wired to the nightly `20 4 * * *` cron; no report on disk yet (merged today, first run 2026-10-16 04:20) | live SLA unproven until the first nightly |
| C3 | PARTIAL | graders 393 passed rc 0 (189.5 s, this session); SessionStart `--hook` registered in settings.json | F7 the stale-report alarm (`scripts/scratch_sweep.py:1284-1294`) is a trigger spec D6 / plan C3 do not list ('otherwise nothing'), refreeze debt; a never-written report raising nothing (`:1274-1276`) matches the contract — recorded as a design risk |
| C4 | CONFORMS | graders 393 passed rc 0 (189.5 s, this session) | — |

### Phase verdicts

| Phase | Rows | Verdict |
|---|---|---|
| Phase A (marker, mint, closes, handoff, heartbeat, coroner — 5bed978ff) | A1-A7 | PARTIAL — 5 CONFORMS; A1 (F10 non-finite `closed_at`), A2 (F12 a minted name the key regex rejects) |
| Phase B (removal, adoption, dead split, D3 launch, session mode, lock, retire, worktrees — 6caff3202) | B1-B12 | PARTIAL — 8 CONFORMS; B1 (F1, F2), B2 (F3), B5 (F9), B8 (F5, F11 — the data-loss regression) |
| Phase C (seat sizes, size report, alarm, refusal set — 39d665c65) | C1-C4 | PARTIAL — 2 CONFORMS; C1 (F8), C3 (F7 refreeze) |
| Finish (5b44c86f9) | — | spec refreeze owed (R1, F7) |

## Findings

| Id | Row | Class | Finding | Disposition |
|---|---|---|---|---|
| F1 | B1 | trivially-green test | `tests/test_scratch_sweep_run_folders.py:345` asserts `.trash-big` is gone, but the fixture renames to `.trash-big-<key>` (:262), so the assertion holds whether or not the walk-free removal ran | CLOSED — fixed by infra W-c0a1d324 (`53496f1f4`, `cded300a6`, on master); was ROUTED — fleet |
| F2 | B1 | cost | `scripts/scratch_sweep.py:568-598` `git_pointer_files` scans to depth 3 with no breadth budget; a wide run folder costs a full walk at classification | CLOSED — fixed by infra W-c0a1d324 (`53496f1f4`, `cded300a6`, on master); was ROUTED — fleet (budget suggestion) |
| F3 | B2 | trivially-green test | case (a) of `test_active_condition_keeps` (`tests/test_scratch_sweep_run_folders.py:384-389`) never makes the session live — `--run-folders` passes no `dead_of` (`scripts/scratch_sweep.py:1032`, `:1039`) — so the row passes on another ACTIVE condition | CLOSED — fixed by infra W-c0a1d324 (`53496f1f4`, `cded300a6`, on master); was ROUTED — fleet |
| F4 | B7 | fail-open degradation | the mint resolves the session directory from `os.getcwd()` (`scripts/command_run.py:5941`), the D3 launch from the toplevel (:5988); from a subdirectory with a two-slug sid the mint refuses (`:1648`) and the run gets `RUN-SCRATCH: none` (pass 2 corrected the mechanism: the marker's `repo` is right) | RECORDED — routed to fleet as advice |
| F5 | B8 | implemented-but-inert | `--strict-proc` never reaches run folders: in `--dead` it downgrades before run rows are planned (`scripts/scratch_sweep.py:2389`, `:2410`), in session mode `consumed` is outside `_allowed_classes` (`:2082`, `:2110-2119`) — against the flag's contract (:33) | CLOSED — fixed by infra W-c0a1d324 (`53496f1f4`, `cded300a6`, on master); was ROUTED — fleet |
| F6 | C3 | design risk | a report never written or unparseable yields no reason (`scripts/scratch_sweep.py:1274-1276`) while a stale one alarms; pass 2: the contract never promised a missing-report alarm | RECORDED — routed to fleet as advice |
| F7 | C3 | spec-refreeze debt | the stale-report alarm (`scripts/scratch_sweep.py:1284-1294`) is built but absent from spec D6 and plan C3 | ROUTED — fleet |
| F8 | C1 | deviation | spec D5 (spec :88) gives each seat folder its own `du` deadline; `_seat_size_lines` shares one across all seats (`scripts/command_run.py:1782`, `:1791`) | CLOSED — fixed by infra W-c0a1d324 (`53496f1f4`, `cded300a6`, on master); was ROUTED — fleet |
| F9 | B5 | deviation + trivially-green test | the `--dead` idleness walk enters run folders (`scripts/scratch_sweep.py:2321`, `:1096`); the B5 guard (`tests/test_scratch_sweep_run_folders.py:318-327`) inspects only the path it is handed, so it cannot see it | CLOSED — fixed by infra W-c0a1d324 (`53496f1f4`, `cded300a6`, on master); was ROUTED — fleet |
| F10 | A1 | fail-open | `judge_run_folder` admits a non-finite `closed_at` (`scripts/scratch_sweep.py:727-732`); NaN and -inf classify `consumed` (probe, pass 2); `gap_keeps` drops a gap for a NaN `created` (`:505-512`), at classification and again in the removal-time re-check (`:859-863`); pass 3: `write_size_report` takes a NaN or +inf `created` as known (`:1196-1202`), so a stale non-`done` folder never alarms. Root: `read_owner` (`:395-401`) lets `json.loads` parse `NaN`/`Infinity` and no reader checks finiteness — one fix there (e.g. `parse_constant` refusing) closes all three sites. Only a clobbered `.owner` can carry one | ROUTED — fleet |
| F11 | B8 | data loss (regression) | `_holds_backup` prunes any `scratchpad/` child named `run-*`/`.trash-*` (`scripts/scratch_sweep.py:279`) where the design governs only the minted key (`is_run_entry`, `:521-524`, P8). Probe (pass 3, redirected sandbox): a dead session whose only backup is `scratchpad/run-tests/main.py.bak` reads `dead`, not `dead-holds-backups`, and `--dead --apply` removes it with the backup. Before this plan nothing was pruned, so this is a regression. Census today: 0 of 59 live scratchpads exposed (2 unminted `run-`/`.trash-` folders, none holding a backup). Fix: prune with `is_run_entry` | ROUTED — fleet (urgent: the nightly runs `--dead --apply`) |
| F12 | A2 | boundary (mint vs classifier) | `start` accepts `--command ""` (or `"/"`, `"!!"`): `_norm_command` yields `""` (`scripts/command_run.py:2112`), `_scratch_name` strips to `<started_at>` (`:1432`), and the mint creates `run-2026-…-<hex>`; `RUN_KEY_RE` needs a command segment before the date (`scripts/scratch_sweep.py:515-517`), so `is_run_entry` reads it as an ordinary entry and a live `running` run idle past the stale threshold can be removed by age — INV-1 broken for a degenerate input. Pass 5: any command whose characters all fall in `[^0-9A-Za-z_-]` (`"日本"`, `"é"`, `"-"`) does the same — one root, the sanitised command segment can be empty. Fix: fall back to `run` when the sanitised command is empty (in `_run_scratch_key`), or refuse such a command in `start` | CLOSED — fixed by infra W-c0a1d324 (`53496f1f4`, `cded300a6`, on master); was ROUTED — fleet (low) |
| R1 | A1, B2 | spec-refreeze debt | spec INV-1 and V2 (`docs/superpowers/specs/2026-10-15-scratch-lifecycle-design.md:75`, `:112`) still say any non-empty gaps list keeps a folder; D-877's interim rule (a gap keeps only when its process started after the marker) is what is built. The plan says the operator ruling is "boarded", but no work item names D-877 in either store | ROUTED — fleet + coordinator |

Status update 2026-10-24 (W-2ce07f05): seven rows are CLOSED by infra's W-c0a1d324 fix, which is on master (`53496f1f4`, `cded300a6`; 251 tests in the two scratch test files pass). The Coverage Checklist and the Pass Ledger below still show the verdicts as they stood when the review ran.

Refuted or recorded, never counted as defects: four "uncollected" graders (renamed, or living in `tests/test_scratch_sweep_run_folders.py` — REFUTED) · A6 "bump outside step" (`scripts/command_run.py:6284` is the step branch — REFUTED) · B5 classification outside the lock (`apply_run_rows` re-checks at removal, `scripts/scratch_sweep.py:835-865` — REFUTED) · B7 `onexc` needs Python 3.12 (all 23 `/opt/*/.venv` interpreters and the system python are 3.12 — RECORDED, latent) · B4 a different-command start leaves a wall record `resumable` (alarm-only by design — RECORDED) · A2 `.` slug and A4 nested-wall close untested (RECORDED). Pass 2: the adoption handler's `owner` cannot be unbound (`_read_owner` never raises, `scripts/command_run.py:1612-1619` — REFUTED) · the size report missing a done folder a removal-time re-check kept for a new holder (that folder is not worktree-kept — REFUTED) · the coroner's `died` mark is final (it acts on death evidence by design, A7 — RECORDED) · `--retire` outside the per-session lock (marks, never removes — RECORDED) · a failed seat `du` prints nothing (RECORDED, F8's neighbour). Pass 5: `started_at` is always `%Y-%m-%dT%H:%M:%S%z` (`scripts/command_run.py:1911`), a resumed run keys on its new `started_at` (`:5925`, `:5783`) and adoption reuses the same key (`:5930`, `:1767`) — CLEAN; a 217-219 character command mints a name whose `.trash-` rename passes 255 bytes, so the folder is kept for ever (a leak, never an early removal — RECORDED). Pass 3: the size report's one 600 s budget across sessions (`scripts/scratch_sweep.py:1177`, `:1231`) marks tail sessions unmeasured — spec D6 names no per-session deadline (RECORDED, design observation).

## Coverage Checklist

Rubric: `python scripts/review_rubric.py --changed docs/superpowers/specs/2026-10-15-scratch-lifecycle-design.md docs/development/plans/2026-10-15-plan-1-scratch-lifecycle.md scripts/scratch_sweep.py scripts/command_run.py scripts/sysadmin/kaizen_coroner.py tests/test_scratch_sweep_run_folders.py tests/test_command_run_scratch.py`

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
- Type the package, never `.`: the root walks the hub-synced `scripts/`, where mypy finds the same file under two module names and stops on every fresh project. file-worker types `mypy --explicit-package-bases worker`; a `server/` backend (saas-skeleton, static-site, office-extension, chrome-extension, mobile-app) runs `mypy src` from `server/` (D-605).
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (`<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed) (see `30-ops.md` § Release & Admin Processes).
| `alembic upgrade head` in `lifespan` / startup hook | One-off admin process against the deployed release: `docker compose run --rm <svc> alembic upgrade head`, `<svc>` a service that declares `.env.owner` (a `migrate` service), never the app service (D-754) (concurrent replicas race the version table) |

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

### core/40-documentation.md  (hit: docs/development/plans/2026-10-15-plan-1-scratch-lifecycle.md, docs/superpowers/specs/2026-10-15-scratch-lifecycle-design.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_command_run_scratch.py, tests/test_scratch_sweep_run_folders.py)
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
- [ ] Destructive DB tests pass the throwaway guard before connecting — `require_throwaway(TEST_DATABASE_URL)` where the scaffold emitted `tests/conftest.py`; where it did not (an unscaffolded repo has no such helper), this anchored predicate, verbatim: `dbname = urlparse(url).path.lstrip('/'); assert dbname.lower().endswith(('_test', 'throwaway', 'scratch')), dbname` — never point them at a dev/shared DB.

# promote-to-check_*: 36 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `uv` `pip` `pip install` `poetry` `pipenv`
- `pyproject.toml` `uv.lock`
- `async def` `.query().all()` `25-data-postgres.md`
- `engine` `async_session` `get_db` `src/database.py` `25-data-postgres.md`
- `DATABASE_URL` `postgresql+asyncpg://user:pass@host:port/db` `REDIS_URL` `DB_HOST` `DB_PORT` `DB_NAME` `DB_USER` `DB_PASSWORD` `localhost` `postgres-main`
- `30-ops.md` `.tmp` `/tmp`
- `except Exception` `logger.exception()` `55-observability.md`
- `from {package}.logger import get_logger` `55-observability.md` `structlog.get_logger()` `logging.getLogger(__name__)`
- `asyncio.create_task()` `asyncio.TaskGroup`
- `datetime.now(UTC)` `datetime.utcnow()`
- `.` `scripts/` `mypy --explicit-package-bases worker` `server/` `mypy src` `server/`
- `ASYNC` `B` `S` `pyproject.toml`
- `uvicorn` `uvicorn.run()` `-slim` `linux/amd64` `30-ops.md`
- `uvicorn.run()`
- `config/production.yml` `settings.production` `config/{dev,staging,prod}.yaml`
- `logging.FileHandler` `logging.handlers.RotatingFileHandler` `TimedRotatingFileHandler` `loguru` `*.log` `55-observability.md`
- `alembic upgrade head` `lifespan` `@app.on_event("startup")` `upgrade head` `docker compose run --rm <svc> alembic upgrade head` `<svc>` `.env.owner` `migrate`
- `alembic upgrade head` `lifespan` `docker compose run --rm <svc> alembic upgrade head` `<svc>` `.env.owner` `migrate`
- `docs/OPERATIONS.md` `docs/DEPLOYMENT.md`
- `scripts/doc_reconcile.py` `docs/QUICKSTART.md` `docs/CONFIGURATION.md` `docs/data-contract.md` `docs/SERVICES.md` `docs/OPERATIONS.md`
```

| Class | Verdict |
|---|---|
| core/10-python (FLOOR) | CLEAN — stdlib-only scripts as the docstring requires (`scripts/scratch_sweep.py:35-36`); no dependency file touched; graders 393 passed |
| 12-FACTOR (FLOOR) | CLEAN — host tooling, no service; the size report is a state file under `~/.claude/state`, not a logfile |
| core/40-documentation (MATCHED) | ROUTED(1) — R1 and F7: the spec text lags the built rule (fleet mail) |
| core/45-testing-strategy (MATCHED) | ROUTED(1) — F1, F3 (fleet mail) |
| fail-open/fail-closed | ROUTED(1) — F11 a backup under an unminted `run-` folder is invisible and its dead session removed (data loss), F10 non-finite marker times read as consumed (fleet mail); F4 and F6 recorded as advice |
| cost/quota accounting | ROUTED(1) — F2 `git_pointer_files` has no breadth budget, F9 the nightly walk enters run folders, F8 a shared `du` deadline (fleet mail) |
| boundary/sentinel/prefix | ROUTED(1) — F1 `.trash-big` vs `.trash-big-<key>`, F10 NaN/-inf pass the numeric check, F11 prefix prune vs minted key, F12 a minted name the key regex rejects (fleet mail); every other prefix test is filtered upstream by `is_run_entry` (`scripts/scratch_sweep.py:533`, `:1677`) |
| behavior-without-a-test | ROUTED(1) — A4 nested close under `blocked --wall` and A2's `.` slug have no test (both behave correctly, live or by reading); named in the fleet mail as grader gaps |
| trivially-green test | ROUTED(1) — F1 vacuous absence assertion, F3 case (a) does not isolate its condition, F9 the walk guard cannot see a session-level walk (fleet mail) |
| implemented-but-inert | ROUTED(1) — F5 `--strict-proc` is inert for run folders (fleet mail); every other function has a production caller (`start`, the closes, `run_dead_mode`, the hook, cron `20 4 * * *`) |
| live-SLA broken | CLEAN — nothing broken live: marker, heartbeat, lock, cron entry `20 4 * * *` and the SessionStart hook all observed; the size report's first write is the 2026-10-16 04:20 nightly (not yet due) |
| spec-refreeze debt | ROUTED(2) — R1 (fleet mail + coordinator report, the D-877 ruling is not boarded) and F7 |
| plan CONVERGED but never executed | CLEAN — plan EXECUTED with per-phase commits 5bed978ff, 6caff3202, 39d665c65, 5b44c86f9 |
| supersession without a named successor | CLEAN — D-877 names itself interim and names the panel split it waits on; its missing board entry is R1 |

## Gate

`.venv/bin/python scripts/final_gate.py --check --json` from the worktree root, re-measured in the closing pass (excerpt of the verbatim output: status, check count, skipped checks, errors):

```json
{
  "status": "success",
  "checks": 57,
  "skipped_checks": [
    "static tier"
  ],
  "errors": null
}
```

## Pass Ledger

| Pass | finders | counters | method | inventory md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | native opus×1 + sonnet×2 (units A, B, C; author-blind, fleet built it) · full inventory, 23 rows | found: 15, new: 15, confirmed: 8, fixed: 0, unexecuted: 0 | method: re-derivation — each row grounded in code, graders re-run (393 passed), live marker/lock/cron/hook probes; 8 confirmed ROUTED, 3 refuted, 4 recorded | 4ba81817…/eb065e6c… → unchanged |
| Pass 2 | native opus×1 + sonnet×2 (fresh closing seats, units A, B, C, author-blind) · full inventory re-derived against the pass-1 ledger | found: 9, new: 9, confirmed: 3, fixed: 0, unexecuted: 0 | method: re-derivation — every row re-grounded; NaN probe re-run by the orchestrator; B5 walk and C1 deadline read at the cited lines; 3 confirmed (F8, F9, F10), 2 refuted, 4 recorded; F4/F6 reframed to RECORDED, B7 re-verdicted CONFORMS | 4ba81817…/eb065e6c… → unchanged |
| Pass 3 | native opus×1 + sonnet×2 (the pass-2 closing seats re-sweeping their own units) · classes non-finite-marker-field, walk-enters-run-folder, shared-deadline | found: 3, new: 3, confirmed: 2, fixed: 0, unexecuted: 0 | method: re-derivation — F10's third site (`write_size_report`) read at the lines; F11 reproduced by the orchestrator in a redirected sandbox and censused read-only on the live root; 1 recorded | 4ba81817…/eb065e6c… → unchanged |
| Pass 4 | native opus×1 (the unit-B closing seat) · class prefix-vs-minted-key over the whole pinned surface, 8 prefix sites | found: 1, new: 1, confirmed: 1, fixed: 0, unexecuted: 0 | method: re-derivation — 7 sites CLEAN (upstream `is_run_entry`, re-read by the orchestrator at `scripts/scratch_sweep.py:533`, `:786`, `:1189`, `:1677`), `_retire` RECORDED (operator-named, marker-gated); F12 (the reverse: a minted name the regex rejects) confirmed by reading the mint and the regex | 4ba81817…/eb065e6c… → unchanged |
| Pass 5 | native sonnet×1 (the unit-A closing seat, non-author) · class minted-name-rejected-by-regex — the closing pass | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation — `started_at` format, resume key, adoption key, zone sanitising CLEAN; the non-ASCII command variant is F12's own root (cited, not counted); the name-length leak RECORDED; every class in the ledger now swept | 4ba81817…/eb065e6c… → unchanged |
