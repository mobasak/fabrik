# Plan — hourly scratch-sweep timer (W-d1a4a8f5)

Status: DRAFT
Profile: small

**Owner:** infra-2

Spec: `docs/superpowers/specs/2026-10-31-scratch-janitor-bound-design.md` (Size: small; converges with this plan in `/fabrik-plan-review`).

## What we already agreed

- Goal and why: spec § Goal, spec § Why this exists.
- Approach A — run the unchanged janitor hourly from a systemd user timer and retire the 04:20 crontab line: spec § Chosen approach, spec § Decisions taken (three blind judges, A first unanimously).
- Rejected B, C, D and the cron-only edit: spec § Rejected alternatives.
- Invariants 1–4 (no removal-rule change; one scheduler; no overlap; catch-up): spec § The delta.
- **Planning deviation (measured, Phase 1):** the installer is a standalone script modelled on `scripts/sysadmin/install_wsl_net_heartbeat_timer.sh`, not a new `operator_setup.py` step. The archive step's machinery is single-timer-specific — `Plan` holds one `archive_run`/`timer_was` (`scripts/sysadmin/operator_setup.py:115`), `_link_undo` hard-codes the archive timer (`scripts/sysadmin/operator_setup.py:394`), and six tests pin its exact undo lines (`tests/test_operator_setup.py:263`, `tests/test_operator_setup.py:338`, `tests/test_operator_setup.py:447`) — and nothing in that script writes a crontab. The spec's § The delta touchpoint is amended in Phase B to match.

## Phase A — units, installer, tests

Appetite: 40

Scope: spec § The delta touchpoints, as built in the prototype `proto.diff` (the run's durable folder, 332 added lines; files read from its `+++` headers below).
Complexity: inline

Steps:
1. Copy the prototype's four files into the tree: `scripts/sysadmin/systemd/scratch-sweep.service`, `scripts/sysadmin/systemd/scratch-sweep.timer`, `scripts/sysadmin/install_scratch_sweep_timer.sh` (mode 0755), `tests/test_scratch_sweep_timer.py`.
2. Prove red-first: on the base (the four files absent) every test fails, since each reads the units or the installer; then mutate the active-timer guard (`if [ "$active" != "active" ]` → `if false`) and see `test_a_failed_install_keeps_the_crontab_line[timer-not-active]` red; restore, all green.
3. Gate: `/opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_scratch_sweep_timer.py` → 11 passed; `systemd-analyze --user verify` both units silent; the live crontab's md5 unchanged across the run.
4. Review: `/fabrik-review-scoped` over Phase A's commit.

Behavior Contract (each row its test in `tests/test_scratch_sweep_timer.py`):
| # | Behaviour | Test |
|---|---|---|
| A1 | the units run the janitor hourly at :20 with catch-up, no flock wrapper, and verify silently | `test_the_units_run_the_janitor_hourly_and_verify` |
| A2 | the installer enables the timer and only then removes exactly the 04:20 line, backing up the crontab and printing an undo that restores it | `test_the_installer_enables_the_timer_then_removes_only_the_0420_line` |
| A3 | the 04:20 line as the only line leaves an empty crontab (no pipefail abort) | `test_the_0420_line_alone_leaves_an_empty_crontab` |
| A4 | no crontab, no line, an edited line or a duplicated line is never written | `test_a_crontab_without_exactly_one_0420_line_is_never_edited` |
| A5 | a failed install (linger off, verify warning, timer not active) keeps the crontab line | `test_a_failed_install_keeps_the_crontab_line` |
| A6 | a missing janitor refuses before any systemctl call | `test_a_missing_janitor_refuses_before_any_systemctl_call` |

## Phase B — docs, spec amendment, ledgers

Appetite: 30

Scope: spec § Documentation landing sites.
Complexity: inline

Steps:
1. `docs/workstation/cleanup-automation.md`: the schedule row (`docs/workstation/cleanup-automation.md:20`), the "what the cron line runs" line (`docs/workstation/cleanup-automation.md:161`), the nightly wording (`docs/workstation/cleanup-automation.md:244`) and the cron block (`docs/workstation/cleanup-automation.md:285`) now name the hourly timer, the installer, `journalctl --user -u scratch-sweep.service`, and the operator's one-time run.
2. `docs/workstation/wsl-startup-inventory.md:58` — the janitor entry names the timer instead of the 04:20 cron line.
3. `docs/workstation/hooks-index.md:98` — "nightly" size report → hourly.
4. The spec's § The delta touchpoint and § Documentation landing sites name the standalone installer (the deviation above); `docs/workstation/operator-setup.md` is no longer touched.
5. Ledgers: CHANGELOG entry, the D-row (approval and the deviation, minted by `/fabrik-plan-review`'s approval; the build's own row if the review adds one), LESSONS entry (measure the configured threshold's real distribution — the prune age), INDEX rows for the new script, units and test.
6. Gate: `python3 scripts/final_gate.py --json` → `status: success`; `render_doc_script_links.py --check`; then the whole-plan review at Finish (`/fabrik-execute-plan` D7, one heavy round).

## Constraints Digest

| Quote | Source |
|---|---|
| **`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`. | `.windsurf/rules/core/10-python.md:22` |
| **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. | `.windsurf/rules/core/45-testing-strategy.md:21` |
| a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` |
| **⚠️ Link it or it is decoration.** | `.windsurf/rules/core/40-documentation.md:225` |
| **Fenced code blocks only** — never indented code (AI treats it inconsistently) | `.windsurf/rules/core/40-documentation.md:244` |

Every selection cites a row (red-first tests; INDEX rows link the new files) or is unconstrained (unit files, a bash installer; no new dependency).

## File Scope (owned paths)

- `scripts/sysadmin/systemd/scratch-sweep.service`
- `scripts/sysadmin/systemd/scratch-sweep.timer`
- `scripts/sysadmin/install_scratch_sweep_timer.sh`
- `tests/test_scratch_sweep_timer.py`
- `docs/workstation/cleanup-automation.md`
- `docs/workstation/wsl-startup-inventory.md`
- `docs/workstation/hooks-index.md`
- `docs/superpowers/specs/2026-10-31-scratch-janitor-bound-design.md`
- `docs/development/plans/2026-10-31-plan-2-scratch-sweep-hourly-timer.md`

## Coverage Checklist

| Class | Source | Disposition |
|---|---|---|
| python-pack floor (no new Python runtime code; test-only module) | rubric FLOOR core/10-python.md | open — graded by the plan review |
| 12-factor axes (box-local unit; config in the unit file; logs to the journal) | rubric FLOOR 12-FACTOR | open — graded by the plan review |
| docs: link it, fenced blocks, heading levels | rubric MATCHED core/40-documentation.md | open — graded by the plan review |
| testing: behaviour contract, watched-fail-first, no cosmetic assertions | rubric MATCHED core/45-testing-strategy.md | open — graded by the plan review |
| recurrence: a guard that never fires (the active-timer check) | standing class | open — mutant shown red in Evidence |
| recurrence: a test that reaches live state (the live crontab) | standing class | open — md5 before/after in Evidence |
| recurrence: doc claim drift (04:20 / nightly wording) | standing class | open — Phase B steps 1–3 |
| recurrence: shared-append ledger collisions | standing class | open — private-index recipe at commit |

```
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

### core/40-documentation.md  (hit: docs/workstation/cleanup-automation.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
| `Agent-Role` | `primary` · `orchestrator` · `subagent` · `review-fix` · `ci-fix` | every AI commit (`ci-fix` ONLY when one of the hub's two unattended writers made the commit — the CI-fix dispatcher's `claude -p` run in THIS repo after a GitHub Actions failure, or the hub's own rules-version cron; any other session never writes it) |
| `Agent-Name` | the name the operator gave your window — your `CLAUDE.md` § Agent Provenance Trailers owns the rule (in a project: write it by hand; never invent one) | every AI commit |
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_scratch_sweep_timer.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A subagent seat runs no package-manager verb and runs `.venv/bin/python -m pytest` instead (`10-python.md` § Package Manager). A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot … (wrapped further — read the pack)
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

# promote-to-check_*: 38 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
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

## Evidence

Phase A — `scripts/sysadmin/install_wsl_net_heartbeat_timer.sh:26` (the linger check copied), `tests/test_wsl_net_heartbeat.py:270` (the stub world copied), `scripts/scratch_sweep.py:2205` (the janitor's own non-blocking lock — no wrapper), `docs/workstation/cleanup-automation.md:291` (the exact cron line the installer removes).

```
$ systemd-analyze --user verify scratch-sweep.service scratch-sweep.timer; echo "verify rc=$?"
verify rc=0
$ pytest -q tests/test_scratch_sweep_timer.py      # in the prototype worktree
11 passed in 0.78s
live crontab unchanged
$ (mutant: active-timer guard → `if false`) pytest -q tests/test_scratch_sweep_timer.py
FAILED tests/test_scratch_sweep_timer.py::test_a_failed_install_keeps_the_crontab_line[timer-not-active]
1 failed, 10 passed in 1.16s
$ (restored) pytest -q tests/test_scratch_sweep_timer.py
11 passed in 0.99s
```

Phase B — `docs/workstation/cleanup-automation.md:20`, `docs/workstation/wsl-startup-inventory.md:58`, `docs/workstation/hooks-index.md:98` (each states the janitor's 04:20 / nightly schedule, found by the systemd-environment grounding seat).

```
$ grep "^+++ " proto.diff
+++ b/scripts/sysadmin/install_scratch_sweep_timer.sh
+++ b/scripts/sysadmin/systemd/scratch-sweep.service
+++ b/scripts/sysadmin/systemd/scratch-sweep.timer
+++ b/tests/test_scratch_sweep_timer.py
```

External facts: the spec's research ledger `docs/reference/research/2026-10-31-scratch-janitor-bound-ledger.md` (rows sched-1, sched-2: `Persistent=true` catch-up and no second instance, https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html, fetched 2026-10-31).

## Self-audit

Grounding: three seats — the archive step's pattern (Opus: single-timer machinery, no crontab writer, ten traps), the test harness (Sonnet: stubs keyed on the archive timer, exact undo assertions), the janitor under systemd (Sonnet: no verdict changes under the user-service environment; nothing reads the old log; the docs to update). Their traps folded: the crontab line is removed only after the timer is `active` (trap 1); linger is required (trap 2); no `systemctl disable` anywhere (trap 5 — the installer never disables); no flock wrapper; install from the main checkout after merge (trap 9, the janitor-exists check).
(a) Coverage: Goal → Phase A; invariants 1–4 → A (units + installer + A1–A6); docs/landing sites → B; the deviation → B step 4.
(b) Cross-phase names: the unit names `scratch-sweep.service`/`.timer` and the installer path are the same in Phase A's files, Phase B's docs and the spec amendment.
Fixed point: not yet — `/fabrik-plan-review` grades it with the spec.

## Residual unknowns

- Resolved: where the bytes are; why cadence; whether systemd changes any verdict (no); how the crontab is edited safely.
- Open: whether `Persistent=true`'s stamp survives a WSL VM shutdown — resolution: after the operator's install and the next `wsl --shutdown`, `systemctl --user list-timers scratch-sweep.timer` shows a catch-up run (spec § Validation).
- Open: the steady-state size under hourly sweeping — resolution: the 24 h measurement and the 60 GB tripwire (spec § Lifecycle).
