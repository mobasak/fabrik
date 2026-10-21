# Plan — review seats: write isolation in the seat guard (W-72dfd448)

Status: DRAFT
Profile: small
**Owner:** intel
**Surface:** `git rev-parse HEAD` = 4efc5d325 at authoring, re-grounded at 21744dd43 (2026-10-22; seat_guard.py and
its tests unchanged); `.claude/hooks/seat_guard.py` (651 lines), `tests/test_seat_guard.py` (33 tests), `commands/_agents/fabrik-reviewer.md:4` (read, not edited)

Spec: `docs/superpowers/specs/2026-10-15-review-seat-write-isolation-design.md` (DRAFT, `Size: small`, `Profile: delta`;
refined in this run by D-914). `/fabrik-plan-review` grades its sections together with this plan and flips both. Source:
mail 01M4PHYNXJ → work item W-72dfd448; design rulings D-913, D-914. Estimated diff (after the plan review's round 1): ≈250 code lines in ONE code file,
`.claude/hooks/seat_guard.py` (redirect capture and fd-number drop in `_simple_commands` ≈20, the destination rule
`_write_reason` with its per-verb option tables ≈75, its call before every `continue` in `_scan` ≈8, the unparseable
fallback ≈5, docstring ≈20); tests ≈160 lines in `tests/test_seat_guard.py`; one row in `docs/workstation/hooks-index.md`.

## What this plan is

Two inline phases the orchestrator codes itself in the `worktree-intel` worktree; no coder is dispatched:

- **A — the guard**: the shell write rule, the unparseable fallback, the tool-list pin, the docstring and the
  hooks-index row (spec § The delta items 1-4).
- **B — Finish**: the whole-plan `/fabrik-review` (the hook is a governance-sync path), CHANGELOG, the gate, commit,
  push, merge request.

Phase A ends with `/fabrik-review-scoped` on its surface; the Finish runs the ONE heavy `/fabrik-review` (the
`/fabrik-execute-plan` D7 floor) and writes one receipt.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § Intake Inventory I1–I3 (2 IN delivered differently, 1 OUT-OF-SCOPE → W-f7bf9a54) | IN as dispositioned there | Phase A, per the spec rows |
| I2 | *"Plan as Profile: small"* (this run's brief) | IN | this header |
| I3 | *"the matcher in .claude/settings.json:146 → Bash\|Write\|Edit\|NotebookEdit (reviewed commit only — the main checkout's settings are live)"* | OUT-OF-SCOPE — superseded by D-914: the seat holds no write tool (`commands/_agents/fabrik-reviewer.md:4`), so the matcher stays `Bash`; the destination is the tool-list pin, behaviour A1 | Phase A step 2 |
| I4 | *"_in_scratch :283-293 gains the session's own <main>/.tmp/runs/<sid>/"* | OUT-OF-SCOPE — D-914: no seat brief writes there (census in Evidence) and the payload names no main checkout to derive it from; the destination is spec § Contract deltas, which records the census | Evidence |
| I5 | *"graders in tests/test_seat_guard.py (33 today) per spec § Validation 1-6, each seen red first"* | IN | Phase A Behaviour Contract; Global Constraints |
| I6 | *"Sync paths (.claude/hooks/, .claude/settings.json) → full /fabrik-review at build"* | IN (the hook only) | Phase B step 1 |

Intake: 6 items — 4 IN, 2 OUT-OF-SCOPE (each named above), 0 ASK.

## What we already agreed (citations, not restatement)

- Goal and personas: `spec § Goal`, `spec § Personas`; today's code: `spec § What exists today`; external facts:
  `spec § External dependencies`.
- The delta 1-4 and the stated blind spots with the tripwire: `spec § The delta`; contract deltas and the MIRROR census:
  `spec § Contract deltas`; validation 1-6: `spec § Validation`; cost: `spec § Cost`; lifecycle: `spec § Lifecycle`.
- Approach B (judge panel 3/3, D-913), the tool-list pin replacing the tool-write hook (D-914) and the `perl -i` graft:
  `spec § Decisions taken`; rejected A, C, D and a per-seat cwd: `spec § Rejected alternatives`. The approval row is
  minted by `/fabrik-plan-review` at its gate (a `Size: small` spec is approved there, not here).

## Global Constraints (every phase inherits these)

- **Seats only.** Every new rule sits behind `decide()`'s existing early return (`.claude/hooks/seat_guard.py:566-567`):
  no `agent_id`, or an `agent_type` outside `SEAT_TYPES`, is allowed untouched — the lead, implementers and every other
  agent type keep writing as today.
- **Fail open on a guard bug, fail closed on an unknown destination.** `main()` keeps its `except Exception` → allow
  (`:620-627`, the charter); inside the rule, a `$`-bearing or substituted destination is NOT scratch (`_in_scratch`,
  `:284-285`), and neither is one starting with `~`.
- **Destinations only.** A read of the live tree (`cat`, `cp <live> <scratch>/`, `git -C <live> show`) stays allowed.
- **Relative destinations join the tracked cwd** (`os.path.join(ctx["cwd"], p)`) before `_in_scratch`, whose
  `realpath` (`:286`) would otherwise resolve against the hook process's own cwd. The tracked cwd is the shell's:
  `env -C` moves it for its own command only, and a command's redirects resolve against the cwd before it.
- **No settings change.** `.claude/settings.json` is untouched (D-914).
- **No new dependency**; `shlex`, `os.path` and `re` only (`core/10-python.md:38`).
- Tests: one per behaviour, watched-fail-first (`core/45-testing-strategy.md:22`), through the existing subprocess
  harness `_run()` (`tests/test_seat_guard.py:24-50`) and its `_denied()` (`:53`); red-on-revert runs in a throwaway
  worktree (`git worktree add --detach <scratch>/probe HEAD`), never the shared checkout.
- Seats never mutate git state; never read `~/.claude*`; seat scratch paths are absolute and each seat `cd`s to its own
  scratch first; a seat never executes a script it has not read.
- **Execution discipline (native seats only, D-181):** Phase A ends with `/fabrik-review-scoped` (the floor of three
  native seats on different angles, stamped with `command_run.py dispatch`) and does not hand on until its closing pass
  confirms zero defects. The Finish `/fabrik-review` partitions the whole-plan diff by file into a Sonnet and a Haiku
  finder per slice (D-344), the orchestrator executing every refutation and reproduction.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (FLOOR — TOOLING surface; MATCHED — seat_guard.py, test_seat_guard.py) | no deps-file edit | `core/10-python.md:38` |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED — test_seat_guard.py) | one test per behaviour; watched-fail-first; no cosmetic assertions | `core/45-testing-strategy.md:20`, `:21`, `:22` |
| `.windsurf/rules/core/40-documentation.md` (MATCHED — CHANGELOG.md, DECISIONS.md, this plan) | one CHANGELOG entry | `core/40-documentation.md:134` |
| `docs/workstation/hooks-index.md` (the hooks authority) | the `seat_guard.py` row names what the hook refuses | `docs/workstation/hooks-index.md:104` |
| `commands/_agents/fabrik-reviewer.md` (the seat's definition, read only) | the tool list the pin asserts | `commands/_agents/fabrik-reviewer.md:4` |
| `fabrik-lib` | nothing parses shell destinations or keys a hook on a subagent type — BUILD in the hook | `spec § fabrik-lib verdict` |
| `specs/services/*.yaml` `shape:` | untouched — a hub hook, no service | — |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Quote | Source |
|---|---|
| Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it. | `.windsurf/rules/core/10-python.md:38` |
| a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` |
| No cosmetic assertions | `.windsurf/rules/core/45-testing-strategy.md:21` |
| Gate-checked, no exceptions. Every code-shipping ticket must produce exactly one entry. | `.windsurf/rules/core/40-documentation.md:134` |

## Phase A — the guard

Appetite: 120

**Interfaces — Produces** (all in `.claude/hooks/seat_guard.py`, consumed only inside it; the grammar is spec § The
delta 2, 3 and 5, cited rather than restated):
- `_simple_commands()` (`:214-234`) returns a list of `_Cmd(list)` — the words as today, plus a `.redirs` attribute
  holding `(op, target)` for every OUTPUT redirect of spec § The delta 2, kept also for an empty or keyword-only word
  list; an fd number leaves the words only when glued to its operator in the raw text (an offset check on the raw
  string, since shlex drops the whitespace). The `["("]`/`[")"]` scope markers (`:227`) stay plain
  equality-comparable lists. `_scan` reads `raw.redirs` BEFORE `_strip` (`:533`), which returns a plain slice.
- `_write_reason(words, redirs, ctx, cwd_before) -> str` — "" or the reason `a review seat writes only under its
  scratch dir — <dest> is outside it`; the destinations are spec § The delta 2's, redirects judged against
  `cwd_before`.
- `_scan()` (`:504-561`) — calls `_write_reason` for every simple command right after `_strip` and BEFORE the
  `if not words: continue` (`:534-535`), the `cd`/`pushd` (`:537-547`) and `bash -c` (`:548-557`) `continue`s; then
  `_kill_reason` and `_git_reason` as today (`:558`).
- `_strip()` (`:255-260`) — an `env -C <dir>` changes `ctx["cwd"]` for the stripped command only; the scan restores
  it after the command is judged (spec § The delta 5).
- `_HEREDOC` (`:116`) — `(?<!<)<<(?!<)`, so `<<<` is a here-string, not a heredoc opener (spec § The delta 5).
- the `_UnparseableError` fallback (`:510-517`) — spec § The delta 3; a bare unterminated `echo "x` stays allowed
  (`tests/test_seat_guard.py:231`).
- The module docstring and the reason text name the rule, the blind spots (spec § The delta) and the COBRA line.
- `docs/workstation/hooks-index.md:104` — the `seat_guard.py` row names the write rule and its blind spots.

**Steps** (sequential):
1. Write the Phase A graders (Behaviour Contract below) in `tests/test_seat_guard.py`; run them and see each DENY row
   red against today's hook (`.venv/bin/python -m pytest tests/test_seat_guard.py -q`). The rows green today are
   proven by a named neuter in a throwaway worktree (`git worktree add --detach <scratch>/probe HEAD`), each watched
   red and restored: A1 — add `Write` to the `tools:` line; A2 — drop `decide()`'s early return (`:566-567`); A4 —
   drop the `/dev/` and fd exemptions; A5 — judge `cp` sources as destinations; A8's allow half — match every `>`
   in the fallback; A9 — let the new path's exception escape `main()`.
2. The tool-list pin (A1): a test reading `commands/_agents/fabrik-reviewer.md`'s frontmatter `tools:` line.
3. `_Cmd` with `.redirs` and the fd-number drop in `_simple_commands`.
4. `_write_reason` and its call in `_scan`; the unparseable fallback.
5. Run the whole file green — the 33 existing tests unchanged — then `ruff check` and `ruff format --check` on both files.
6. The docstring and the hooks-index row.
7. One live probe: dispatch a `fabrik-reviewer` seat (Agent tool, its scratch absolute, `cd` there first) told to run
   `printf x > <its scratch>/ok` and then `printf x > /opt/fabrik/.claude/worktrees/intel/.seat-probe-<sid>`; paste both
   outcomes in Evidence (the second must be refused) and `git status --short` after the seat (no new file). The hook is
   read from `${CLAUDE_PROJECT_DIR}` at every call (`.claude/settings.json:150`), so the edited file is live in this
   worktree without a reload.
8. `/fabrik-review-scoped` on Phase A's surface; fix what it finds.

**Behavior Contract (Phase A):**

- **Given** `commands/_agents/fabrik-reviewer.md`, **When** its frontmatter `tools:` line is read, **Then** it names none of `Write`, `Edit`, `NotebookEdit`, `MultiEdit` (A1)
- **Given** the lead (no `agent_id`) and a `general-purpose` agent, cwd = the repo, **When** `echo x > Makefile` or `rm -rf src`, **Then** allowed (A2)
- **Given** a seat with cwd = the repo, **When** `echo x > Makefile`, `echo x >> docs/a.md`, `ls | tee Makefile`, `cmd &> out.log`, `cmd >& out.log`, `cmd &>2`, `cmd <> Makefile`, `> Makefile`, `{ echo x; } > Makefile`, `(true) > Makefile`, `for i in a; do echo; done > Makefile`, `exec 3> Makefile`, `cp <scratch>/a 2 >/dev/null`, **Then** denied, the reason naming the destination (A3)
- **Given** the same seat, **When** `cmd > /dev/null 2>&1`, `cmd 2>&1 | head`, `cmd >&2`, `echo x > <scratch>/a`, `cd <scratch> && echo x > a`, `mkdir -p <scratch>/d 2>/dev/null`, `truncate -s 0 <scratch>/f`, **Then** allowed (A4)
- **Given** the same seat, **When** `cp <live file> <scratch>/`, `cp -r src <scratch>/s`, `cat Makefile`, `perl -Mstrict -ne print Makefile`, **Then** allowed (A5)
- **Given** the same seat, **When** `cp <scratch>/x Makefile`, `mv a b`, `mv Makefile <scratch>/`, `rsync --remove-source-files Makefile <scratch>/`, `rm -rf src`, `unlink f`, `gzip Makefile`, `touch x`, `mkdir d`, `truncate -s 0 f`, `sed -i s/a/b/ f`, `sed --in-place=.bak s/a/b/ f`, `perl -pi -e 1 f`, `perl -i -pe 1 f`, `dd if=/dev/zero of=f`, `install -t bin x`, `cp -rt src <scratch>/x`, `install -d live`, `ln -s <scratch>/x`, `sort -o f in`, `bash -c 'rm -rf src'`, `cd src > log`, `echo x > /dev/../opt/fabrik/Makefile`, **Then** denied (A6)
- **Given** the same seat, **When** `rm -rf "$D"`, `echo x > $(pwd)/x`, `touch ~/x`, `cd <scratch> && touch ~/x`, `rm -rf /tmp/*`, `rm -rf /tmp/claude-<uid>`, `rm -rf /tmp/claude-<uid>/<slug>`, **Then** denied (unknown, home, glob or ancestor-of-scratch destination) (A7)
- **Given** the same seat, **When** an untokenisable command naming a write (`echo "x > Makefile`), **Then** denied; `echo "unterminated` and `echo "unterminated 2>/dev/null` stay allowed (A8)
- **Given** raw non-JSON stdin, and a seat payload whose new write path raises (injected in-process with `monkeypatch`, the one grader outside `_run()`), **When** the hook runs, **Then** no deny — no output for raw stdin, only the existing `updatedInput` envelope for the seat (fail open) (A9)
- **Given** the same seat, **When** `env -C <scratch> true; rm -rf src` or `env -C <scratch> true; git reset --hard`, **Then** denied (the cwd move is scoped to its command); `env -C <scratch> touch x` is allowed (A10)
- **Given** the same seat, **When** `cat <<< hi` followed on later lines by `git reset --hard` and `hi`, **Then** denied (a here-string hides nothing) (A11)
- **Mocked:** only A9's crash injection (`monkeypatch` on the new write path, in-process); every other grader runs the real hook as a subprocess on a synthetic payload (`_run()`); A1 reads the real agent definition.

## Phase B — Finish

Appetite: 60

**Steps** (sequential):
1. The whole-plan `/fabrik-review` (D7 floor: the whole-plan diff by file, a Sonnet and a Haiku finder per slice as
   Agent-tool seats (D-961), the orchestrator executing every candidate), its receipt
   `docs/development/reviews/2026-10-15-plan-2-review-seat-write-isolation-review.md`.
2. `CHANGELOG.md` entry (`### Changed — review seats cannot write outside their scratch (<the commit date>)`); a
   `docs/DECISIONS.md` row only if the build takes a decision the spec did not (D-913, D-914 are the design rows; the
   approval row is `/fabrik-plan-review`'s).
3. `python scripts/final_gate.py --check --json` green; commit by pathspec with trailers; push; `merge_request.py
   request --review <receipt> --item W-72dfd448`.

## File Scope (owned paths)

- `.claude/hooks/seat_guard.py`
- `tests/test_seat_guard.py`
- `docs/workstation/hooks-index.md` (only the `seat_guard.py` row, `:104`)
- `docs/superpowers/specs/2026-10-15-review-seat-write-isolation-design.md`
- `docs/development/plans/2026-10-15-plan-2-review-seat-write-isolation.md`
- `docs/development/reviews/2026-10-15-plan-2-review-seat-write-isolation-review.md`
- `docs/development/reviews/2026-10-15-plan-2-review-seat-write-isolation-plan-review.md` (this plan review's own
  receipt, when one is written)
- `CHANGELOG.md` (one entry)

## Coverage Checklist

Derived from the `review_rubric.py` run below (FLOOR + MATCHED) plus the four recurrence classes.

| Row | Hunt | Verdict |
|---|---|---|
| FLOOR core/10-python | no deps-file edit; stdlib only | CLEAN — no dependency file in § File Scope; hunted: Global Constraints |
| FLOOR 12-FACTOR | no config, no env added | CLEAN — no new env var or file sink; hunted: Phase A Interfaces |
| MATCHED core/40-documentation | one CHANGELOG entry; the hooks-index row; D-914 in the same change as the spec refinement | CLEAN — Phase B step 2, Phase A step 6, this plan's commit |
| MATCHED core/45-testing-strategy | one grader per behaviour, each seen red | CLEAN — A1-A9 map spec § Validation 1-6 (Self-audit); A1's red is proven on revert |
| RECURRENCE fail-open vs fail-closed | guard crash → allow; unknown destination → deny | FIXED r1 — A7, A9 (A9 re-stated: a crash leaves the seat's `updatedInput` envelope, never a deny) |
| RECURRENCE cost/quota/limit accounting | none | CLEAN — no new hook invocation, no seat or quota change |
| RECURRENCE boundary/sentinel/prefix collisions | `/tmp` and its ancestors of other sessions' scratch, globs; `/dev/*` by `realpath`; glued vs spaced fd numbers; `>&` dup vs `&>` file; option values read as operands | FIXED r1 — spec § The delta 2 names each; A3, A4, A6, A7 grade them (round 1: ancestors and globs were scratch, `2 >` was an fd) |
| RECURRENCE behaviour-without-a-test | every spec § Validation item maps to an A row; every row green today has a named red | FIXED r1 — Self-audit mapping; Phase A step 1 names each neuter |

Rubric invocation (verbatim output; the File Scope is the changed-path set):

```text
$ python scripts/review_rubric.py --changed .claude/hooks/seat_guard.py tests/test_seat_guard.py docs/workstation/hooks-index.md docs/superpowers/specs/2026-10-15-review-seat-write-isolation-design.md docs/development/plans/2026-10-15-plan-2-review-seat-write-isolation.md CHANGELOG.md docs/DECISIONS.md
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

### core/40-documentation.md  (hit: CHANGELOG.md, docs/DECISIONS.md, docs/development/plans/2026-10-15-plan-2-review-seat-write-isolation.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_seat_guard.py)
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

## Evidence

Grounded at authoring (2026-10-15), executed. Three grounding seats ran (an Opus `fabrik-reviewer` on the hook's
anchors and callers, a Sonnet `fabrik-reviewer` census of every seat brief, a Sonnet `fabrik-researcher` on the hook
payload docs); their findings are folded into the spec and Phase A, each re-executed below.

- The seat's tools — `commands/_agents/fabrik-reviewer.md:4`:

```text
$ grep -n "^tools:" commands/_agents/fabrik-reviewer.md
4:tools: Read, Grep, Glob, Bash
```

- Today's tokeniser and scratch test (`.claude/hooks/seat_guard.py:214-234`, `:283-293`), imported from the file with
  `python3 -B`: the redirect target is dropped, an fd number and option values land among the words, `-pi` stays one
  token, `.tmp/runs` and a relative path are not scratch:

```text
$ python3 -B probe_tokens.py
'mkdir -p /tmp/s/x 2>/dev/null' -> [['mkdir', '-p', '/tmp/s/x', '2']]
'echo x > Makefile' -> [['echo', 'x']]
'truncate -s 0 /tmp/f' -> [['truncate', '-s', '0', '/tmp/f']]
'perl -pi -e s/a/b/ f' -> [['perl', '-pi', '-e', 's/a/b/', 'f']]
/tmp/foo True
/opt/fabrik/.tmp/runs/S/x False
relative/x False
```

- The brief census (spec § Contract deltas): 32 files searched at authoring; every seat write the briefs prescribe
  lands under `RUN-SCRATCH` (`.claude/workflows/fabrik-review-loop.js:258`, `:272`, `:230`;
  `commands/_fragments/subagents-core.md:5`); no brief names `.tmp/runs` for a seat. Re-checked 2026-10-22 for the
  Agent-tool path D-961 made the hub's only one: `commands/_fragments/no-workflow-hub.md` gives each seat its
  absolute scratch folder too. An adopted run folder is renamed INTO the adopting session's pad
  (`scripts/command_run.py::_adopt_run_scratch`, "move the wall seed's `resumable` folder into THIS session"), so it
  never sits under another session's `/tmp` dir.
- The `_HEREDOC` change (spec § The delta 5), run 2026-10-22 on a throwaway worktree of 21744dd43 with line 116
  patched to `r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1"`: the 33 existing tests stay green, a
  here-string hides nothing, and both heredoc forms still strip:

```text
$ pytest <probe>/tests/test_seat_guard.py -q
33 passed in 9.71s
$ _strip_heredocs('cat <<< hi\nrm -rf src\nhi\necho done') -> 'cat <<< hi\nrm -rf src\nhi\necho done'   (was 'cat <<< hi\necho done')
$ _strip_heredocs('cat <<EOF\nbody\nEOF\nls')               -> 'cat <<EOF\nls'
$ _strip_heredocs('cat <<-EOF\n\tbody\n\tEOF\nls')          -> 'cat <<-EOF\nls'
```

- External: https://code.claude.com/docs/en/hooks (subagent `agent_id`/`agent_type`; exact-string matchers) and
  https://code.claude.com/docs/en/tools-reference (no MultiEdit row), fetched 2026-10-15 (exa, WebFetch).

## Self-audit

- Every behaviour in `spec § Validation` maps to a row: spec 1 → A1, 2 → A2, 3 → A3/A4, 4 → A5/A6/A7, 5 → A8, 6 → A9,
  7 → A10/A11.
- Every item in What we already agreed maps to Phase A (delta 1-4) or Phase B (review, CHANGELOG, merge request).
- Diff estimate ≈250 code lines in 1 code file (tests excluded) after round 1: inside `Profile: small` (≤ ~400, ≤ 5).
- Cross-phase names: `_Cmd`, `.redirs` and `_write_reason` are produced and consumed in Phase A only.
- Every touchpoint is a `path:line` in today's hook, re-read by the Opus grounding seat (its drift corrections are
  applied: `decide` `:564-582`, `_scan` `:504-561`, `main` `:611-647`).

## Residual unknowns

- **R1 — resolved.** The live tool-write payload no longer matters: the seat has no write tool (D-914).
- **R2 — resolved.** An adopted RUN-SCRATCH folder lies in the adopting session's pad (Evidence), so `_in_scratch`'s
  other-session test never refuses it.
- **R3 — open, by design.** The blind spots in spec § The delta (interpreters, `xargs`/`find` writes, depth > 3,
  side-effect writes such as `.pytest_cache`) stay; the tripwire there names the resolution.

## Pass Ledger

(written by `/fabrik-plan-review`)
