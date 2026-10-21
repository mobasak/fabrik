# Plan 3 — own scrape tool, slice 1a (hub side)

Status: DRAFT
Profile: small
**Owner:** intel
Spec: `docs/superpowers/specs/2026-10-21-own-scrape-tools-design.md` (CONVERGED, approved D-1100) · Work item: W-10146d20

## Goal

Deliver the hub side of the spec's slice 1a (spec § Lifecycle, "Slice 1a"): every Firecrawl tool line in the command
and agent sources pins `proxy: "basic"`; the `fabrik-scrape` MCP server fabrik-lib builds is vendored, run and
registered on this box; and `fabrik-researcher` switches its raw-page fetch to it once its own ledger is all-pass.

## What we already agreed

- The own tool is an MCP server, `fabrik-scrape`, built by fabrik-lib as `web-scrape-mcp` and vendored into the hub —
  spec § Chosen approach, item 1.
- Slice 1a is the scrape tool only, static and markdown paths, rendering off, on asks G5, G6, G7, G10, G11, plus
  `proxy: "basic"` on every Firecrawl line and the web-tools call log — spec § Lifecycle, "Slice 1a".
- Firecrawl stays the fallback, closed to operator-cleared sources until the slice-1d test — spec § Fallback contract.
- `fabrik-scrape` is a raw-page fetch, never in the graded search chain; `_TIER1` is not widened — spec § Chosen
  approach, item 2.
- A command switches only when its own ledger is all-pass; fact strings are fixed before the run — spec § Test
  ledger (closing paragraph) and § Lifecycle.
- fabrik-lib builds the module and asks as its W-89c8b88f, and the web-tools call log as its W-eadc4d0a (coordinator
  relay, 2026-10-21); this plan does not write into `/opt/fabrik-lib` (cross-repo hard stop).
- The approval row exists: `docs/DECISIONS.md` D-1100 (verified by grep before planning).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "plan the hub side of slice 1a" (this run's argument) | IN | Phases A-C |
| I2 | spec § Lifecycle 1a: "every command or seat line naming a Firecrawl tool gains `proxy: "basic"`" | IN | Phase A |
| I3 | spec § Lifecycle 1a: "infra registers it" | IN | Phase B (infra executes the unit install under a gate) |
| I4 | spec § Lifecycle 1a: "Then `fabrik-researcher` switches (its own ledger first)" | IN | Phase C |
| I5 | spec § Chosen approach 2: the three contract copies gain `fabrik-scrape` in the fetch sentence | IN for the hub's two copies (Phase C); OUT-OF-SCOPE for `/opt/fabrik-lib/CLAUDE.md` — a cross-repo file, requested from fabrik-lib by mail in Phase C |
| I6 | spec § Lifecycle 1b, 1c, 1d (crawl, rendering, the proxyUsed test) | OUT-OF-SCOPE | later plans, one per slice; 1d is gated on the operator's approval (spec § Fallback contract) |
| I7 | the seven other commands' switches (spec § Lifecycle: "one command per slice") | OUT-OF-SCOPE | later plans after this one; `fabrik-researcher` goes first |
| I8 | the web-tools caller-and-URL log (spec § Lifecycle 1a) | IN as a re-vendor of the hub's `libs/web_tools.py` (Phase B), built by fabrik-lib as W-eadc4d0a |

Intake: 8 items — 6 IN (one partly), 2 OUT-OF-SCOPE (each named), 0 ASK.

## Global Constraints

- Logs are unbuffered JSON or plain lines to stdout only; no `*.log` file write (`core/10-python.md:301-302`).
- `uv` for every package operation; the server's own venv is created and filled with `uv`, never `pip`
  (`core/10-python.md:22`); the hub's shared `.venv` and `pyproject.toml`/`uv.lock` are not touched.
- Python service ports are 8000-8099 (`core/10-python.md:282`); the server listens on `127.0.0.1:8034` only.
- No write outside this repo except the gated unit file in Phase B; no edit under `/opt/fabrik-lib` (cross-repo).
- Command and agent text is edited in `commands/_sources/` and `commands/_agents/` only; the rendered corpus is the
  coordinator's merge-time render (CLAUDE.md § Behavior, merge-time render only).
- No secret is printed; the browserless token stays in `/opt/fabrik/.env`.
- 12-Factor: config by env vars (III); no daemonizing or PID file — systemd supervises (VIII); stdout logs (XI); the
  vendored release is immutable, updated only by re-vendoring (V).

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `core/40-documentation.md` (MATCHED) | new reference doc allowed under `docs/reference/`; INDEX on any added file; PORTS curated tables only | `.windsurf/rules/core/40-documentation.md:192`, `:140`, `:170`; `PORTS.md:147` |
| `core/10-python.md` (FLOOR) | `uv`, type hints, stdout logs, port range | `.windsurf/rules/core/10-python.md:22`, `:168`, `:301`, `:282` |
| `core/57-external-data-sourcing.md` | agent-time tool = MCP server; bypass line | spec § Constraints Digest |
| fabrik-lib `web-scrape-mcp` (VENDOR, being built) | the `scrape` tool and its `blocked` contract | spec § fabrik-lib asks; fabrik-lib W-89c8b88f |
| fabrik-lib `web-tools` (VENDOR, re-vendored) | the Firecrawl call log | fabrik-lib W-eadc4d0a; hub copy `libs/web_tools.py` |
| precedent box MCP server | systemd unit + `mcp_defs.json` http entry | `/etc/systemd/system/fabrik-citation-verifier-mcp.service`; `scripts/sysadmin/mcp_defs.json:28-31` |
| `agents-fabrik.md` | none touched — no VPS, compose, DB or Traefik change in slice 1a | `/opt/fabrik/agents-fabrik.md:361` (Planning Constraints read; items 6 and 4 apply: ports checked, existing service reused) |
| `specs/services/*.yaml` `shape:` | none — not a scaffolded project | — |

No new capability is built fresh in the hub: every module is fabrik-lib's, vendored (spec § fabrik-lib verdict).

## Constraints Digest

| Quote | Source |
|---|---|
| Reference: docs/reference/**/*.md | `.windsurf/rules/core/40-documentation.md:192` |
| Rule: Edit existing docs instead of creating new ones. | `.windsurf/rules/core/40-documentation.md:186` |
| Update when: Any file added, removed, or moved. | `.windsurf/rules/core/40-documentation.md:140` |
| PORTS.md — port allocations, managed by scaffold + registrar system | `.windsurf/rules/core/40-documentation.md:170` |
| uv is the mandated Python package manager. Never use raw pip, pip install, poetry, or pipenv. | `.windsurf/rules/core/10-python.md:22` |
| Use type hints for all function signatures | `.windsurf/rules/core/10-python.md:168` |
| Python services: 8000-8099 | `.windsurf/rules/core/10-python.md:282` |
| Factor XI — Logs. Structured JSON, unbuffered, to stdout — and nothing else (PYTHONUNBUFFERED=1). | `.windsurf/rules/core/10-python.md:301` |

PORTS.md is edited only in its curated "Development Services (WSL Only)" table, which `PORTS.md:147` names the
authoritative registry; the generated block is left alone.

## Phase A — `proxy: "basic"` on every Firecrawl line (no dependency; runs now)

Appetite: 45

Implements spec § Lifecycle, slice 1a ("every command or seat line naming a Firecrawl tool gains `proxy: "basic"`")
and spec § Fallback contract (why Firecrawl's default `auto` mode is not allowed). DO-NOT: change any fetch order,
switch any command to `fabrik-scrape`, or touch the search-chain grader.

Complexity: inline
Gate: .venv/bin/python -m pytest tests/test_firecrawl_proxy_basic.py -q

### Touches

- tests/test_firecrawl_proxy_basic.py — NEW, the grader
- commands/_sources/fabrik-spec.md
- commands/_sources/fabrik-spec-review.md
- commands/_sources/fabrik-plan-after-chat.md
- commands/_sources/fabrik-vision.md
- commands/_agents/fabrik-researcher.md

### Behavior Contract

- **Given** a command or agent source line names `firecrawl_scrape` or `firecrawl_crawl`, **When** the grader scans `commands/_sources/` and `commands/_agents/`, **Then** the same line, or the bullet it belongs to, carries `proxy: "basic"` (spec § Lifecycle 1a)
- **Given** a line names only `firecrawl_search`, **When** the grader scans it, **Then** it is not required to carry the pin (search takes no proxy; spec § Fallback contract)

### Steps

1. Write `tests/test_firecrawl_proxy_basic.py`: collect every line under `commands/_sources/*.md` and
   `commands/_agents/*.md` matching `firecrawl_(scrape|crawl)`; for each, read its paragraph (the line plus the
   continuation lines up to the next blank line or list item); assert `proxy: "basic"` occurs in it; on failure list
   every `path:line` that lacks it. Measure the fire rate first: today it fires on all 12 lines (Evidence A).
2. Run it and confirm it FAILS red for the right reason (12 lines listed): `.venv/bin/python -m pytest
   tests/test_firecrawl_proxy_basic.py -q` → 1 failed.
3. Add `proxy: "basic"` beside each `firecrawl_scrape` / `firecrawl_crawl` mention in the five files above (12 lines,
   Evidence A), keeping each sentence's meaning: e.g. "`firecrawl_scrape` with `maxAge: 0`" becomes
   "`firecrawl_scrape` with `maxAge: 0` and `proxy: "basic"`".
4. Re-run the gate → `1 passed`. Prove red-on-revert in a throwaway worktree (`git worktree add <scratch>/probe HEAD`,
   revert one edited line there, run the test there → red; never in the shared tree).
5. `python3 scripts/enforcement/check_doc_sync.py` → no ERROR; CHANGELOG entry under `[Unreleased]`
   (`### Changed — Firecrawl calls in commands pin the basic proxy (2026-10-21)`); `INDEX.md` row for the new test.
6. `.venv/bin/python commands/assemble_commands.py --check` → no drift error (render stays the coordinator's job).
7. **`/fabrik-review` on this phase's changed surface — BLOCKING, run to its coverage-adjudicated exit** (the
   command sources are a governance-sync surface, CLAUDE.md § Orient lane row 1): partitioned file slices, a Sonnet
   and a Haiku finder per slice, every candidate executed by the lead, delta rounds to a closing round that confirms
   zero code or doc defects.
8. Commit the phase with explicit pathspecs and trailers; push.

### Interfaces

Produces: the grader `tests/test_firecrawl_proxy_basic.py`, which Phase C's edits must keep green.

## Phase B — vendor, run and register `fabrik-scrape` (after fabrik-lib W-89c8b88f and W-eadc4d0a merge)

Appetite: 90

Implements spec § Chosen approach 1 (the server) and § Lifecycle 1a ("infra registers it"), plus § Shape (one local
MCP server process, one `mcp_defs.json` entry, one port). DO-NOT: enable rendering, edit the vendored code, or touch
`libs/web_scrape/` (the older kilo-db copy).

Complexity: inline
Gate: curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8034/mcp

Start condition, self-service: fabrik-lib's reply mail names the merge SHAs of W-89c8b88f and W-eadc4d0a
(`python3 scripts/mail.py list` shows it). Until then the phase does not start; this is an event wait, not a question.

### Touches

- libs/web_scrape_mcp/ — NEW, the vendored module (copied whole from `/opt/fabrik-lib/web-scrape-mcp/` at the merged SHA)
- libs/web_tools.py — re-vendored from `/opt/fabrik-lib/web-tools/web_tools.py` at W-eadc4d0a's SHA
- scripts/sysadmin/mcp_defs.json — the `fabrik-scrape` http entry
- scripts/sysadmin/systemd/fabrik-scrape-mcp.service — NEW, the unit's source of truth in the repo
- docs/reference/fabrik-scrape-mcp.md — NEW, the subsystem doc
- docs/workstation/mcp-roster.md
- PORTS.md

### Behavior Contract

- **Given** the server is started by its unit, **When** a client posts an MCP `initialize` to `http://127.0.0.1:8034/mcp`, **Then** it answers 200 and lists the `scrape` tool (spec § Chosen approach 1)
- **Given** `scrape(url)` on docs.python.org/3/library/bisect.html, **When** called through the server, **Then** it returns markdown with `path` static or markdown and a `fetched_at` (spec § Chosen approach 1)
- **Given** `scrape` on the saved g2.com URL, **When** called, **Then** it returns `blocked: bot-wall` with `status` 403 and no render (spec § fabrik-lib asks G11)
- **Given** `scrape` on `http://127.0.0.1:8033/`, **When** called, **Then** it returns `blocked: scope` (spec § fabrik-lib asks G7)

### Steps

1. Read fabrik-lib's merged `web-scrape-mcp/README.md` and follow its vendor instructions; copy the module into
   `libs/web_scrape_mcp/` at the merged SHA, recording the SHA in a `VENDORED_FROM` line of its README.
2. Create its own venv with `uv venv libs/web_scrape_mcp/.venv` and `uv pip install --python
   libs/web_scrape_mcp/.venv/bin/python -r libs/web_scrape_mcp/requirements.txt` (ignored by `.gitignore:48`).
3. Re-vendor `libs/web_tools.py` from fabrik-lib at W-eadc4d0a's SHA; run the hub's tests that import it
   (`rg -l "libs.web_tools|from libs import web_tools" tests`) under `capped_run.sh`.
4. Write `scripts/sysadmin/systemd/fabrik-scrape-mcp.service` modelled on the precedent unit (Evidence B): `User=ozgur`,
   `WorkingDirectory=/opt/fabrik`, `EnvironmentFile=/opt/fabrik/.env` (browserless URL and token),
   `Environment=FABRIK_SCRAPE_HOST=127.0.0.1`, `Environment=FABRIK_SCRAPE_PORT=8034`, the server's own venv python as
   `ExecStart`, `Restart=always`, `MemoryMax=512M`, `NoNewPrivileges=true`. Port 8034 is free (Evidence B).
5. Gate: installing the unit writes `/etc/systemd/system/` (outside the repo) — the operator approves it through the
   coordinator; on approval infra runs `sudo install -m 644 scripts/sysadmin/systemd/fabrik-scrape-mcp.service
   /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now fabrik-scrape-mcp`.
6. Add `"fabrik-scrape": {"type": "http", "url": "http://127.0.0.1:8034/mcp"}` to `scripts/sysadmin/mcp_defs.json`
   beside the precedent entry (`:28-31`); run `python3 scripts/sysadmin/mcp_health.py` → `fabrik-scrape` live.
7. Run the phase gate → `200`; then the four Behavior Contract calls through the server with a small MCP client run
   from the server's venv; record outputs in the run folder.
8. Docs: write `docs/reference/fabrik-scrape-mcp.md` (what it is, tools, `blocked` reasons, unit, port, re-vendor
   steps) + its `INDEX.md` row; a `docs/workstation/mcp-roster.md` row beside the precedent (`:75`); a `PORTS.md`
   row in "Development Services (WSL Only)"; CHANGELOG entry; `check_doc_sync.py` → no ERROR.
9. **`/fabrik-review` on this phase's changed surface — BLOCKING, run to its coverage-adjudicated exit** (a new
   mechanism and a box service: full review), the vendored module excluded from finding scope but its
   integration (unit, entry, docs) in it.
10. Commit with explicit pathspecs and trailers; push.

### Interfaces

Consumes: fabrik-lib `web-scrape-mcp` at its merged SHA (tool `scrape`, spec § Chosen approach 1's return shape).
Produces: the live MCP endpoint `http://127.0.0.1:8034/mcp` named `fabrik-scrape`, which Phase C's ledger and the
researcher's `mcpServers` line consume.

## Phase C — the researcher's ledger, then its switch

Appetite: 120

Implements spec § Lifecycle 1a ("Then `fabrik-researcher` switches (its own ledger first, as for every command)"),
spec § Test ledger (fact strings fixed before the run) and spec § Chosen approach 2 (the researcher's order,
long-page rule, DEAD rule, credit-error rules; the contract copies' fetch sentence). DO-NOT: switch any other command;
widen `_TIER1`; edit `/opt/fabrik-lib/CLAUDE.md` (mailed instead).

Complexity: inline
Gate: .venv/bin/python -m pytest tests/test_firecrawl_proxy_basic.py tests/test_research_tier_order.py -q

### Touches

- scripts/scrape_ledger.py — NEW, the per-command ledger runner
- commands/_agents/fabrik-researcher.md
- CLAUDE.md
- templates/governance/CLAUDE.md

### Behavior Contract

- **Given** a ledger input of URLs with fact strings fixed beforehand, **When** `scripts/scrape_ledger.py` runs them through `fabrik-scrape`, **Then** it writes one row per URL with facts found, clean ratio, path and `blocked` reason, and never edits a fact string (spec § Test ledger)
- **Given** the researcher's ledger is all-pass, **When** its agent file switches, **Then** `mcpServers` lists `fabrik-scrape` and its raw-fetch order is `fabrik-scrape` → exa → Firecrawl (spec § Chosen approach 2)
- **Given** the two hub contract copies, **When** the fetch sentence gains `fabrik-scrape`, **Then** `tests/test_research_tier_order.py` stays green and `_TIER1` is unchanged (spec § Chosen approach 2)

### Steps

1. Build the researcher's URL list from session transcripts: `fabrik-researcher` seats' `firecrawl_scrape`,
   `web_fetch_exa` and `WebFetch` calls since 2026-10-01 (the `fc_calls.py` method, D-845), sampling up to 20 distinct
   URLs across kinds (docs page, API reference, GitHub raw file, PDF, a long page).
2. For each URL fix its fact strings BEFORE any run: one independent read (`WebFetch`), the strings quoted from it,
   that read recorded beside them in the ledger input (spec § Test ledger).
3. Write `scripts/scrape_ledger.py` (typed, stdout output, `# AFTER-EDIT:` header naming
   `docs/reference/fabrik-scrape-mcp.md`): reads the input JSON, calls the server's `scrape` tool for each URL with an
   MCP client, grades facts and clean ratio, writes the result JSON to the run folder. Run it with the server's venv
   (`libs/web_scrape_mcp/.venv/bin/python scripts/scrape_ledger.py <input>`), so the hub's dependencies stay unchanged.
4. All-pass means every URL either grades PASS or returns the `blocked` reason the spec expects for it (a PDF is
   `unsupported` until slice 1b). A FAIL stops the phase: the researcher keeps Firecrawl, and the failing kind goes to
   fabrik-lib as a new ask.
5. On all-pass, edit `commands/_agents/fabrik-researcher.md`: `mcpServers` (line 4, Evidence C) gains `fabrik-scrape`;
   the raw-fetch order, long-page rule (`:36-44`), DEAD rule (`:86`) and credit-error rules follow spec § Chosen
   approach 2. Keep Phase A's grader green.
6. Edit the fetch sentence in `CLAUDE.md` § External Knowledge (`:302`) and `templates/governance/CLAUDE.md` (`:276`)
   to name `fabrik-scrape` as the raw-page fetch beside `WebFetch`, outside the search chain; mail fabrik-lib the same
   sentence for `/opt/fabrik-lib/CLAUDE.md`.
7. Run the phase gate → all passed; `check_doc_sync.py` → no ERROR; CHANGELOG entry; `INDEX.md` row for the script.
8. **`/fabrik-review` on this phase's changed surface — BLOCKING, run to its coverage-adjudicated exit** (synced
   contract and agent files: full review).
9. Run `/fabrik-docs-review` over the plan's doc changes; then the plan's final gate:
   `python scripts/final_gate.py --check --json` → `"status":"success"` and
   `python scripts/enforcement/check_convergence.py --project-root .` → exit 0. A green gate is necessary, not
   sufficient: the proof is the ledger and the review receipts.
10. Commit with explicit pathspecs and trailers; push; raise the merge request.

### Interfaces

Consumes: `fabrik-scrape` at `http://127.0.0.1:8034/mcp` (Phase B); Phase A's grader.
Produces: the switched researcher; the ledger result JSON the merge request cites.

## Coverage Checklist

| Class | Source | State |
|---|---|---|
| doc-sync triggers (CHANGELOG, INDEX, reference doc) | `core/40-documentation.md` | OPEN — checked per phase |
| Python script discipline (uv, types, stdout) | `core/10-python.md` | OPEN — Phase C |
| 12-Factor (III, V, VIII, XI) | rubric FLOOR | OPEN — Phase B unit |
| governance-sync surfaces edited at source only | CLAUDE.md § Behavior | OPEN — Phases A, C |
| recurrence: a grader that passes on today's output only | standing class | OPEN — Phase A red-first |
| recurrence: a count without its denominator | standing class | OPEN — every Evidence count names its command |
| recurrence: a cross-repo write | standing class | OPEN — fabrik-lib reached by mail only |
| recurrence: a secret printed | standing class | OPEN — the unit reads `.env`, nothing echoes it |

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

### core/40-documentation.md  (hit: CLAUDE.md, PORTS.md, commands/_agents/fabrik-researcher.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_firecrawl_proxy_basic.py)
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

### core/57-external-data-sourcing.md  (hit: scripts/scrape_ledger.py, tests/test_firecrawl_proxy_basic.py)
- API clients, connectors, webhook handlers). ⚠️ `58-resilience` does NOT auto-load on `connectors/`, `ingest/`, `webhooks/` or `scrapers/` paths — when this pack fires, read 58 explicitly; every rule below that says "the 58 contract" assumes you have.
**Never scrape when an API exists** — an API is a contract you can PROFILE (limits, resume, deprecation channel) and be authorised under; a scraper has no contract, breaks on markup change, and may violate ToS. (APIs still deprecate and break — field 10 exists because they do.)
- ⚠️ **Two lanes, and conflating them is the mistake this ladder invites.** An MCP server is an
- ⚠️ **Check the roster before naming one — do not cite from memory**: the roster is SPLIT (user-level + per-repo `.mcp.json`), canonical at `/opt/fabrik/docs/workstation/mcp-roster.md`, probed by `python3 /opt/fabrik/scripts/sysadmin/mcp_health.py`.
- (pluggable, Anti-Captcha — ⚠️ a BYPASS capability, not a default; see § Hard constraints, "the bypass line") · `adaptive-dispatch` (learns which fetch strategy works per domain) · `web-tools` (env-keyed Exa/Brave/Firecrawl executors — the RUNTIME answer to rung 1) · `proxy-pool` (Postgres-backed proxy pool — ⚠️ same caveat as `captcha-solve`: a bypass capability, never a default) · `api-quota` (`QuotaTracker` parses rate-limit headers, persists quota state and gates calls at the cap; `KeyPool` rotates across many keys — the RUNTIME half of profile fields 1, 2, 7 and 9) · `webhooks` (**outgoing** delivery with HMAC signing — it does … (wrapped further — read the pack)
- (⚠️ OpenRouter-only, see § Hard constraints), `ai-image`, `ai-audio`, `ai-translate`, `search`, `scrape`, `captcha`, `proxy`, `domains`, `email`, `storage`, `backup`, `research-data`, `media-stock`, `infra-platform`, `comms`, `dev-tools`, `unidentified`.
**Derive the count and the category set from the FILE, never from this list** — the file has a non-dict `_README` key, so the guard is not optional: `python3 -c "import json,collections;d=json.load(open('scripts/service_catalog.json'));print(collections.Counter(v['category'] for v in d.values() if isinstance(v,dict)))"`. Grep it by `category` before adding any new vendor; detailed contracts live in `docs/reference/apis/**`. Key via env var, never in code.
**An UNKNOWN never waives the design decision — design to the conservative reading**: unknown cap behaviour ⇒ assume silent truncation and verify counts yourself; unknown idempotency ⇒ assume non-idempotent; unknown resume ⇒ checkpoint on your side; unknown health signal ⇒ treat every 5xx burst as *possibly them* and pause rather than hammer; unknown key expiry ⇒ rotate on a schedule anyway; unknown deprecation channel ⇒ watch the headers; unknown schema stability ⇒ validate strictly at the boundary.
| 4 | **Identity posture** — limits per-key, per-account or per-IP? does the ToS permit multiple accounts/orgs — **cite the clause + URL, or UNKNOWN** | decides whether horizontal scale is even available — see the ⚠️ below |
| 9 | **Credential lifecycle** — does the key/token EXPIRE, on what schedule; can it be rotated with an overlap (two keys valid at once) or only by a hard cut; what does an expired key LOOK like (401? 403? a silent empty 200?) | decides whether rotation can be automated at all, and whether the connector can even tell a dead credential from a dead vendor — an expired key is the failure a retry loop can never fix |
| 11 | **Data contract + EXPECTED YIELD** — the response schema pinned at profile time, and the yield the surface must return; what the vendor changes WITHOUT a version bump (nullable flips, new enum values, added fields, pagination shape); freshness/lag and eventual-consistency window; how deletion shows (tombstone vs vanish); a sample kept for diffing | decides the validation posture: a `200` with a different shape is the failure that corrupts silently — outages page you, drift does not ⚠️ **and the EXPECTED YIELD per page** — a number, or `0 is terminal` — and terminal is a POSITION, never a surface. Zero rows is the contract only where a predecessor proves you are past the data: page N+1 after page N returned rows, a delta past a non-empty cursor, a section index that listed N items. Zero on the FIRST page or a cold cursor is a failed fetch ONLY where the surface also states a `≥1` floor for that position — a listing whose first page always has rows. It is NOT a failure on a search or a filtered section, where an empty first page is the honest answer; those declare `0 is terminal` and nothing else. The incident this closes is the listing case: a challenge page on page 1 of a surface that promised rows, read as "crawl complete, 0 rows". A zero-row page is only a failure against a stated `≥1`; undeclared, it is not one (the scraper-failure-classes bullet under § The Capability Profile). |
- ⚠️ **Field 4 is where an operational question becomes a legal one.** Asking "are multiple accounts permitted, and are limits per-key or per-IP?" is ordinary capacity planning, and the answer is sometimes an explicit yes (separate billing orgs, per-project keys). Provisioning extra accounts or rotating IPs **in order to evade a cap the vendor set** is the circumvention shape from § Hard constraints, and it is an operator decision with the ToS quoted — never an engineering convenience. (That exit is legitimate here on the contractual-gate ground — an authorisation, not a menu.) Record what the ToS actually says; do not infer permission from the absence of a block.
- expiry never happens in production; the `58` last-resort rung that died of an expired credential is this row unfilled.
- model (pydantic `strict=True` / zod `.strict()`, unknown keys rejected deliberately), never silently drop an invalid record, and export the invalid-record RATE as a metric — a spike is the upstream change announcing itself, and a `missing` cluster on one field says which one.
- signature outside the timestamp tolerance. ⚠️ **And it runs a reconciliation poll** — a scheduled pull of "what did you send since <cursor>" against the vendor's list endpoint — because a delivery the provider gave up on during your deploy is otherwise unrecoverable by construction. No list endpoint in field 12 ⇒ say so, and treat every missed webhook as a known gap in §9.
- row 22 alarms on, never the fetch count. A **bot-block** (`403`, a challenge page) is a pause condition, not a retry and not a bypass: `58` says never retry a 403, and § Hard constraints says never solve the challenge — the legal move is `adaptive-dispatch`'s strategy switch (static → rendered), then a pause, then an operator decision.
- ONCE, never hot-looping, and named as human-gated in §2b so nobody expects the queue to wake itself.
- ⚠️ **One subject, one home.** The profile records the VENDOR's contract (measured, dated). YOUR handling of it — timeout/retry config, fallback, pause keys — stays in the per-dependency detail card in `docs/RESILIENCE.md`; that card LINKS the profile and never copies its numbers.
- ⚠️ **Not gate-enforced yet, deliberately — and measured 2026-09-02: 0 of the 6 hub vendor docs in `docs/reference/apis/` carry a profile.** This is a new obligation; per the FIX directive a detector ships after its fire rate is measured, not before. Until then the profile's teeth are the `Profile:` line on the dependency's card in `docs/RESILIENCE.md` — **§2b where the doc has one, otherwise the project's equivalent per-dependency row or section** (the scaffold template does carry the slot, verified at `templates/scaffold/docs/RESILIENCE_TEMPLATE.md:63` § 2b Detail Card Per Dependency, whose first field is `Profile`; but a project scaffolded before it, or one whose … (wrapped further — read the pack)
- **LLM data = OpenRouter ONLY** — never a direct vendor LLM SDK (`openai`, `@anthropic-ai/sdk`). Non-LLM vendor APIs are fine directly.
- **Vendor keys are env vars** (`os.getenv`), never constants; the repo must stay open-sourceable (12F-III).
- Honour a TDM reservation even when your own UA is not the one named. ⚠️ **The token set churns and vendors now run SEVERAL bots each** — Anthropic retired `anthropic-ai` and `Claude-Web` for `ClaudeBot` (training) / `Claude-User` (user-initiated fetch) / `Claude-SearchBot` (indexing), and OpenAI/Perplexity document their user-initiated fetchers (`ChatGPT-User`, `Perplexity-User`) as *not* governed by robots.txt. Read a site's file for the group matching YOUR token, not a 2024 block-list. The machine-readable successor is the IETF AIPREF `Content-Usage` rule (robots.txt directive + HTTP header, a draft that updates RFC 9309 if approved) — honour it … (wrapped further — read the pack)
- **⚠️ THE BYPASS LINE IS THE LEGAL LINE, and it runs straight through our own toolbox.** Reading a logged-out public page is a different act from defeating a control. The moment a pipeline solves a CAPTCHA, replays a session, rotates IPs to beat a block, or evades a hard rate limit, it leaves "public data" territory — and the live litigation wave targets the
- catalog's `proxy` and `captcha` categories are therefore **capabilities, never defaults**: reach for them only where a human operator has decided the specific source warrants it, and say so in the plan.
- on a page you never agreed to are weak against a logged-out fetcher; terms you click through, or accept by creating an account, are an ordinary contract and scraping in breach of them is a straightforward claim. So "we have an account there" changes the answer — check before assuming the public-page reasoning applies.
- ⚠️ **Where the profile lives differs between hub and project** — `EXTERNAL_SYSTEMS.md` is a hub-only index; do not send a project at it.
- `cost` · `capability` · `url` · `status` · `match` · `hosts` · `merged_match`), never the envelope — the twelve profile fields live in the vendor doc, dated and re-verifiable.
- the handler, never onto Authelia. It does not ride the health-path bypass either. **The mechanism is the spec, not a hope:** route the receiver under the service's `shape.bearer_bypass_prefix` (a path-regex, default `^/api/` for `has_bearer_api` services, narrowable) — that IS the explicit public route; there is no per-path bypass field to invent. An UNSIGNED provider that must write cross-tenant is the `needs_payments_ingest` shape.

# promote-to-check_*: 54 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
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

### Phase A

`commands/_agents/fabrik-researcher.md:35`, `commands/_sources/fabrik-spec.md:145`. Every Firecrawl scrape or crawl
line, then per-file counts, then the `proxy: "basic"` count (none) — `rg -n` / `rg -c` over the two directories:

```text
commands/_agents/fabrik-researcher.md:35:     FOUND re-fetch the page with `mcp__firecrawl__firecrawl_scrape` and `maxAge: 0` (a live fetch).
commands/_agents/fabrik-researcher.md:37:     FIRST instead — `mcp__firecrawl__firecrawl_scrape` with `formats: ["query"]`,
commands/_agents/fabrik-researcher.md:86:     `mcp__firecrawl__firecrawl_scrape` with `maxAge: 0` (a live fetch) also answers 404 — then it is `DEAD`
commands/_agents/fabrik-researcher.md:121:- **Library/API docs:** `WebFetch` the library's OFFICIAL docs site to find and read the page — but on an HTML docs page a schema field or a parameter name is quoted from the raw arm (rule 1: exa's fetch, then `mcp__firecrawl__firecrawl_scrape` with `maxAge: 0`; the page's `.md` source when the site publishes one), never from a WebFetch answer alone, which has stated fields the page does not carry (a /fabrik-spec run, 2026-10-06: three invented facts); JSON/XML and version claims keep rule 3's routing (no docs-summariser MCP is wired; the roster history lives in `docs/workstation/mcp-roster.md`).
commands/_sources/fabrik-spec-review.md:77:`mcp__firecrawl__firecrawl_search`/`firecrawl_scrape` (on the official library docs; `WebFetch` only to locate a page) → the `gh` CLI to read
commands/_sources/fabrik-spec-review.md:89:(`raw.githubusercontent.com`, view-source, `firecrawl_scrape` with `maxAge: 0` — firecrawl reuses recently indexed
commands/_sources/fabrik-plan-after-chat.md:221:  `mcp__firecrawl__firecrawl_search` / `firecrawl_scrape`** (and official-docs `WebFetch` for library detail). Capture the
commands/_sources/fabrik-spec.md:140:  `mcp__firecrawl__firecrawl_search` / `firecrawl_scrape` on the library's OFFICIAL docs site for framework/API detail (`WebFetch` only to locate
commands/_sources/fabrik-spec.md:145:- Capture the **real** endpoint / signature / auth model / limits / pricing from a RAW fetch (`firecrawl_scrape`
commands/_sources/fabrik-spec.md:262:  **actually fetch it this session** (`WebFetch` / `firecrawl_scrape`) — a claim you didn't
commands/_sources/fabrik-spec.md:264:  `firecrawl_scrape` with `maxAge: 0`, a live fetch) and match the string — normalising whitespace first (raw HTML wraps lines
commands/_sources/fabrik-vision.md:572:  `mcp__firecrawl__firecrawl_search`/`firecrawl_scrape` → `mcp__context7` (library docs) → `mcp__github`
commands/_sources/fabrik-spec-review.md:2
commands/_sources/fabrik-plan-after-chat.md:1
commands/_sources/fabrik-vision.md:1
commands/_agents/fabrik-researcher.md:4
commands/_sources/fabrik-spec.md:4
proxy-basic count above (empty = 0 files)
```

### Phase B

`scripts/sysadmin/mcp_defs.json:28`, `/etc/systemd/system/fabrik-citation-verifier-mcp.service` (the precedent unit,
lines 6-13), then the `mcp_defs.json` entry, then the 80xx listeners (`ss -ltn`) — 8034 is free:

```text
[Service]
Type=simple
User=ozgur
WorkingDirectory=/opt/fabrik-citation-verifier
Environment=FABRIK_CITATION_VERIFIER_URL=http://127.0.0.1:8032
Environment=FABRIK_MCP_HTTP_HOST=127.0.0.1
Environment=FABRIK_MCP_HTTP_PORT=8033
ExecStart=/opt/fabrik-citation-verifier/mcp_server/.venv/bin/python -m mcp_server.server_http
    "fabrik-citation-verifier": {
      "type": "http",
      "url": "http://127.0.0.1:8033/mcp"
    },
0.0.0.0:8031
0.0.0.0:8032
127.0.0.1:8033
127.0.0.1:8040
```

### Phase C

`CLAUDE.md:302`, `tests/test_research_tier_order.py:22`. The two contract fetch sentences, the researcher's
`mcpServers` line and the closed tier-1 set (`grep -n`):

```text
CLAUDE.md:302:2026-09-22, D-337 as refined by D-338): tier 1 is `WebSearch` → `WebFetch` or `brave-search` — any of them; **when they fail or do
templates/governance/CLAUDE.md:276:2026-09-22, D-337 as refined by D-338): tier 1 is `WebSearch` → `WebFetch` or `brave-search` — any of them; **when they fail or do
4:mcpServers: [exa, brave-search, firecrawl]
22:_TIER1 = r"(?:`WebSearch`|`WebFetch`|`mcp__brave-search__brave_web_search`)"
```

## Self-audit

- Grounding run: every anchor above was read this session (Evidence blocks are the captured outputs); the two packs
  in the must-read set were read by a seat and each quoted line re-read with `sed -n` before the Digest was written.
- (a) Coverage: each "What we already agreed" item → Phase A (proxy pin), Phase B (server, registration, call-log
  re-vendor), Phase C (ledger, switch, contract sentence); slices 1b-1d and other commands are named OUT-OF-SCOPE.
- (b) Cross-phase consistency: Phase B produces `fabrik-scrape` at `127.0.0.1:8034/mcp`; Phase C consumes that exact
  name and URL; Phase A's grader is consumed by Phase C's gate.
- Fixed point: not claimed — `/fabrik-plan-review` converges this DRAFT.

## Residual unknowns

| Unknown | Resolution step |
|---|---|
| the exact layout and vendor steps of `web-scrape-mcp` | resolved at Phase B step 1 from fabrik-lib's merged README; the start condition waits for it |
| the server's env-var names for host and port | Phase B step 4 uses the module's own names from its README; `FABRIK_SCRAPE_HOST`/`_PORT` are the default if it names none |
| whether the researcher's ledger is all-pass | Phase C step 4 decides; a FAIL keeps Firecrawl and files a fabrik-lib ask |
| the operator's approval of the unit install | Phase B step 5, boarded through the coordinator as a gate |

## File Scope (owned paths)

- tests/test_firecrawl_proxy_basic.py
- commands/_sources/fabrik-spec.md
- commands/_sources/fabrik-spec-review.md
- commands/_sources/fabrik-plan-after-chat.md
- commands/_sources/fabrik-vision.md
- commands/_agents/fabrik-researcher.md
- libs/web_scrape_mcp/
- libs/web_tools.py
- scripts/sysadmin/mcp_defs.json
- scripts/sysadmin/systemd/fabrik-scrape-mcp.service
- docs/reference/fabrik-scrape-mcp.md
- docs/workstation/mcp-roster.md
- PORTS.md
- scripts/scrape_ledger.py
- CLAUDE.md
- templates/governance/CLAUDE.md
