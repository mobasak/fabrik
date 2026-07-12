# WaveSpeed integration into the kilo-benchmarks pipeline

**Status:** CONVERGED
**Date:** 2026-07-12
**Converged:** 2026-07-12 (`/fabrik-plan-review` — Pass 1 edit-free md5-verified no-op; verified 7 path:line refs, 14 structural pillars, 8 Behavior Contract tests, toolchain preflight (python/pytest/sqlite3/jq/curl/httpx/dotenv), no active sibling plan-lock, 0 placeholders / 0 OPEN residuals; md5 start=end `56767bfe9e257f3aae29dda78af0f464`)
**Design spec:** [docs/superpowers/specs/2026-07-12-wavespeed-integration-design.md](../../superpowers/specs/2026-07-12-wavespeed-integration-design.md) (CONVERGED, md5 `6387897ccd8ff6989d02c4ab6665772e`)
**Scaffold type:** `python-api-gpu` (fabrik hub itself; scripts run hub-side via `daily_refresh.sh`)
**Author:** primary (this session)

## Goal

Wire the WaveSpeed AI catalog (941 models across 25 types on `https://api.wavespeed.ai/api/v3/`) into `scripts/kilo-benchmarks/kilo_agents.db` the same way SiliconFlow and ModelScope are wired: catalog scrape → row seed → per-model pricing → GUI surfacing. Purpose: give `pick_models` a WaveSpeed candidate pool and let `models_browser.html` compare cost/capability across vendors on one screen. Catalog-only (no benching this plan).

## Global Constraints

- **Python 3.11+**, project venv at `/opt/fabrik/.venv/bin/python` (matches `daily_refresh.sh:VENV_PY`).
- **DB path**: `/opt/fabrik/scripts/kilo-benchmarks/kilo_agents.db` (SQLite).
- **Auth**: `Authorization: Bearer ${WAVESPEED_API_KEY}` — the key lives in `/opt/fabrik/.env` (already added).
- **Bronze-tier rate limits do NOT bind catalog fetch** — `/api/v3/models` is a single request, well within any tier. See spec External deps table.
- **Idempotency invariant**: every script re-runs safely (`INSERT OR IGNORE` on model_id PRIMARY KEY; `UPDATE ... AND COALESCE(via_wavespeed, 0) != 1` guards the flip-counter).
- **Naming**: kebab-case for file names; snake_case for Python; `via_wavespeed INTEGER` column matches sibling naming (`via_openrouter/via_kilo/via_dashscope/via_siliconflow/via_modelscope` — all `INTEGER DEFAULT 0`).
- **New service_type enum values**: `3d_gen`, `moderation` — Python-side convention (no SQL CHECK constraint on `agents.service_type`).
- **HTTP client**: `httpx` sync (matches `ms_enrich.py:23` idiom; kilo-benchmarks pipeline is sync).
- **Cache dir**: `scripts/kilo-benchmarks/cache/` (gitignored via `cache/*.json`).
- **Coupling header on every new `scripts/**/*.py`**: `# AFTER-EDIT: <files | none>` in first ~25 lines (gate-enforced by `check_script_headers.py`).
- **No secrets in commits**: `WAVESPEED_API_KEY` is read from env only; never inlined in code or committed.
- **No `fabrik …` shell-outs**: kilo-benchmarks is hub-side, but the plan's gates run in `/opt/fabrik` WSL dev; keep them `python …` / `sqlite3 …` invocations. (This project IS the hub, so `fabrik` IS on PATH — but even here, gates stay tool-shell-outs to keep them cron-safe.)

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (ACTIVE) | Python/FastAPI patterns, typing, env handling — new scraper follows | `.windsurf/rules/core/10-python.md` |
| `.windsurf/rules/core/25-data-postgres.md` (ACTIVE) | Migration discipline — SQLite in-place idempotent ALTER matches | `.windsurf/rules/core/25-data-postgres.md` |
| `.windsurf/rules/core/40-documentation.md` (ACTIVE) | Doc Sync Matrix — CHANGELOG + INDEX + AI_VENDOR_ACCESS updates are phase-owned | `.windsurf/rules/core/40-documentation.md` |
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | Behavior Contract — one test per behavior, TDD for the risky path | `.windsurf/rules/core/45-testing-strategy.md` |
| `.windsurf/rules/core/62-using-subagents.md` (ACTIVE) | fanout pool-default for gradeable fan-out; native for authoritative/GUI | `.windsurf/rules/core/62-using-subagents.md` |
| `AGENTS.md` — hub-side script conventions | kilo-benchmarks lives at `scripts/kilo-benchmarks/`; SQLite catalog + `daily_refresh.sh` scheduled via crontab; `.venv/bin/python` is the interpreter | `AGENTS.md` (§ kilo-benchmarks) |
| `fabrik-lib/README.md` — vendor consult | **No fabrik-lib module covers "AI vendor catalog scraping"** (grep confirmed empty). `async-http-client/` is async → mismatches sync kilo-benchmarks. `web-scrape/` targets HTML pages (Next.js/Apollo), not JSON REST APIs. **BUILD project-local** per spec's vendor verdict table. | `/opt/fabrik-lib/README.md` |
| `scripts/kilo-benchmarks/add_perf_seconds_column.py:20` (precedent — migration) | Idempotent `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` — mirror verbatim | `scripts/kilo-benchmarks/add_perf_seconds_column.py:20-27` |
| `scripts/kilo-benchmarks/scrape_modelscope_catalog.py:104` (precedent — apply_flags) | Flag-flip pattern: match by canonical id, UPDATE guarded by `AND COALESCE(via_X, 0) != 1` | `scripts/kilo-benchmarks/scrape_modelscope_catalog.py:104-146` |
| `scripts/kilo-benchmarks/scrape_modelscope_catalog.py:182` (precedent — ingest_new) | INSERT-new pattern: `INSERT OR IGNORE INTO agents (...)` — mirror | `scripts/kilo-benchmarks/scrape_modelscope_catalog.py:182-275` |
| `scripts/kilo-benchmarks/seed_specialty_catalog.py:163` (precedent — service_type gate) | Real enum allowlist: `if service_type not in {"tts", "stt", "translation", "image_gen", "music_gen"}: continue` — extend to include `3d_gen`, `moderation` | `scripts/kilo-benchmarks/seed_specialty_catalog.py:163` |
| `scripts/kilo-benchmarks/daily_refresh.sh` (precedent — orchestration) | 9-step sequence, non-fatal error handling per step; `set -u` (not `set -e` at step granularity) | `scripts/kilo-benchmarks/daily_refresh.sh` |
| `scripts/kilo-benchmarks/export_models_browser.py:35` (precedent — payload) | `_fetch_chat_models` loads `SELECT * FROM agents`; payload is JSON blob injected into `models_browser.html` at the `<!--DATA_PLACEHOLDER-->` marker | `scripts/kilo-benchmarks/export_models_browser.py:35-78, 378` |
| `agents.db` schema (grounded) | Columns present: `via_openrouter/via_kilo/via_dashscope/via_siliconflow/via_modelscope` (all `INTEGER DEFAULT 0`); `service_type TEXT DEFAULT 'llm'`. Column `via_wavespeed` **absent** — added Phase A. | `sqlite3 kilo_agents.db ".schema agents"` (verified this session) |
| Current `service_type` distribution | `llm:656, image_gen:50, video_gen:28, tts:22, embedding:20, stt:18, translation:8, ocr:5, rerank:4, music_gen:4` — 10 enum values, 815 rows. Post-Phase-B: +12 enum values (`3d_gen`, `moderation`), +928 rows. | `sqlite3 kilo_agents.db "SELECT service_type, COUNT(*) FROM agents GROUP BY service_type"` |
| `libs/subagents/agent.py:689 fanout` + `pg_ledger.py:263 set_quality` + `pg_ledger.py:205 record_agent_run` | Pool-default fan-out API for parallel grounder / test-author / doc-reconciler workers | `libs/subagents/{agent.py,pg_ledger.py}` |
| **Data contract** | Not applicable — no user-facing form fields, no new entity; only additive columns/enum values on the internal `agents` catalog table. Spec's `shape:` decision recorded here for the executor. | Spec § Shape / infra implications |
| **UI design** | Not applicable — `models_browser.html` is an existing internal browser (additive badge only, no new screen). Non-GUI project (`python-api-gpu` hub scaffold). | Spec § Handoff |

## Behavior Contract (whole plan)

Distinct user-observable behaviors this plan adds (risk-ordered — highest first; TDD for the top two):

1. **Idempotent scraper** — running `python scrape_wavespeed_catalog.py` twice back-to-back leaves the DB byte-identical after the first run (no phantom rows, no double-flipped flags). *(risky: touches ~928 new rows)*
2. **Correct service_type mapping** — every WaveSpeed `type` in the catalog maps to the spec's mapping table; unknown types raise, don't silently `llm`-default. *(risky: silent misclassification would poison `pick_models`)*
3. **Flag-flip guarded counter** — the scraper reports the count of rows it flipped `via_wavespeed=1` vs rows already flipped, matching `apply_flags`' pattern (rowcount only counts newly-flipped).
4. **Migration idempotency** — `python add_via_wavespeed_column.py` is safe to run N times; second run reports "already present".
5. **Training rows skipped** — the 13 `type=training` rows never enter `agents` (not a serving endpoint).
6. **Catalog cache round-trip** — the raw catalog JSON persists at `scripts/kilo-benchmarks/cache/wavespeed_catalog.json` for future jsonata-based cost analysis (spec's deferred alternative).
7. **daily_refresh.sh non-fatal on WaveSpeed 5xx** — if `/api/v3/models` returns 500, the daily run continues to `export_models_browser.py` (matches existing `|| echo "[step] failed (non-fatal)"` convention).
8. **GUI badge renders** — a model with `via_wavespeed=1` in the payload shows the `Via WaveSpeed` badge in `models_browser.html` (existing badge iteration pattern, extended).

Trivia skipped: `--dry-run` flag boilerplate, `--help` output, docstring format.

---

## Phase A — Migration + scraper skeleton

**Deliverable:** `via_wavespeed` column added to `agents.db`; skeleton scraper fetches + caches; no rows written yet.

**Files:**
- CREATE `scripts/kilo-benchmarks/add_via_wavespeed_column.py` — one responsibility: idempotent column add.
- CREATE `scripts/kilo-benchmarks/scrape_wavespeed_catalog.py` — one responsibility: fetch, cache, map. Row-write disabled behind `--seed` flag (default off in this phase).
- CREATE `scripts/kilo-benchmarks/tests/test_add_via_wavespeed_column.py` — behavior 4.
- CREATE `scripts/kilo-benchmarks/tests/test_scrape_wavespeed_catalog.py` — behaviors 1, 2, 6.
- CREATE `scripts/kilo-benchmarks/cache/wavespeed_catalog.json` — written by the scraper (gitignored via `cache/*.json`).

### Interfaces

**Consumes** (from repo state):
- `agents.db` schema at `sqlite3 kilo_agents.db "PRAGMA table_info(agents)"` — 87 columns, no `via_wavespeed`.
- `WAVESPEED_API_KEY` from `/opt/fabrik/.env` (already present; loaded via `load_dotenv()`).

**Produces** (for later phases):
- `add_via_wavespeed_column.ensure_via_wavespeed_column(db_path: Path = DB_PATH) -> bool` — returns `True` if column added, `False` if already present. Consumed by Phase B (scraper calls it on entry).
- `scrape_wavespeed_catalog.fetch_ws_models() -> list[dict]` — fetches `/api/v3/models`, returns the `data[]` list unchanged.
- `scrape_wavespeed_catalog.CATALOG_CACHE_PATH: Path` — `scripts/kilo-benchmarks/cache/wavespeed_catalog.json`.
- `scrape_wavespeed_catalog.SERVICE_TYPE_MAPPING: dict[str, str]` — the spec's mapping table, as a Python dict keyed by WaveSpeed `type` (e.g. `"text-to-image": "image_gen"`).
- `scrape_wavespeed_catalog.PRICING_MULTIPLIERS: dict[str, int]` — the spec's normalization multipliers (e.g. `"image_gen": 1_000_000`, `"video_gen": 5_000_000`).
- `scrape_wavespeed_catalog.main(argv: list[str] | None = None) -> int` — entry point; `--dry-run` prints planned INSERTs; `--seed` enables actual writes.
- CLI convention: exit 0 on success; non-zero on network / auth / mapping error.

### Steps

**A.1 — TDD the migration idempotency (highest risk after network — protects against schema corruption).**
1. Write `tests/test_add_via_wavespeed_column.py` — test cases:
   - First-run: fresh DB → `ensure_via_wavespeed_column()` returns `True`; column present after.
   - Second-run: same DB → returns `False`; no schema change.
   - Column has type `INTEGER` (matches sibling `via_*` columns).
2. Run: `python -m pytest scripts/kilo-benchmarks/tests/test_add_via_wavespeed_column.py -v`. **Expected: RED** (module does not exist).
3. Confirm RED for the right reason (`ModuleNotFoundError: add_via_wavespeed_column`).
4. Create `scripts/kilo-benchmarks/add_via_wavespeed_column.py`, mirroring [add_perf_seconds_column.py:20-32](../../../scripts/kilo-benchmarks/add_perf_seconds_column.py#L20-L32) verbatim (rename `perf_seconds` → `via_wavespeed`; type `REAL` → `INTEGER`; `AFTER-EDIT: scripts/kilo-benchmarks/scrape_wavespeed_catalog.py`).
5. Run the tests → **Expected: GREEN**. Fix to green if not.

**A.2 — TDD service_type mapping correctness (behavior 2 — misclassification is silent poison).**
1. Write `tests/test_scrape_wavespeed_catalog.py::test_service_type_mapping_covers_every_wavespeed_type` — parametrize every WaveSpeed `type` from the cached catalog (see A.4 for how to obtain it locally without hitting the API) and assert each maps to one of the 12 known enum values or raises `KeyError`. Include an explicit case that `type="training"` maps to a sentinel value (`None`) and the scraper skips those rows.
2. Write `test_pricing_formula_per_service_type` — for each of the 8 mapped `service_type` values, assert `PRICING_MULTIPLIERS[st] * base_price` matches the spec's formula table (e.g. `image_gen: base × 1_000_000`; `video_gen: base × 5 × 1_000_000`).
3. Run → **RED** (module or constants missing).
4. Confirm RED for the right reason.
5. Create `scripts/kilo-benchmarks/scrape_wavespeed_catalog.py` skeleton:
   ```
   # AFTER-EDIT: scripts/kilo-benchmarks/daily_refresh.sh docs/reference/kilo/AI_VENDOR_ACCESS.md
   ```
   - `import httpx, argparse, os, sqlite3, sys, json`; `from pathlib import Path`; `from dotenv import load_dotenv`.
   - `DB_PATH`, `CATALOG_CACHE_PATH`, `WAVESPEED_URL = "https://api.wavespeed.ai/api/v3/models"` module-level constants.
   - `SERVICE_TYPE_MAPPING` and `PRICING_MULTIPLIERS` module-level dicts matching the spec.
   - `fetch_ws_models() -> list[dict]`: `httpx.get(WAVESPEED_URL, headers={"Authorization": f"Bearer {os.getenv('WAVESPEED_API_KEY')}"}, timeout=30.0)`. Raises on non-2xx (`response.raise_for_status()`). Returns `response.json()["data"]`.
   - `type_to_service_type(ws_type: str) -> str | None`: dict lookup; returns `None` for `"training"`; raises `KeyError` on genuinely unknown.
   - `output_cost_per_m(base_price: float, service_type: str) -> float`: `base_price * PRICING_MULTIPLIERS[service_type]`.
   - `main()` with `--dry-run` (default) and `--seed` (Phase B enables) flags; loads env; fetches; writes cache; prints counts.
6. Run the tests → **GREEN**.

**A.3 — Wire the migration into scraper entry.**
1. In `scrape_wavespeed_catalog.py::main()`, first non-arg line: `from add_via_wavespeed_column import ensure_via_wavespeed_column; ensure_via_wavespeed_column()`. Matches spec's "same as `microbench_specialty.py::run_specialty` invokes `add_perf_seconds_column`" pattern.
2. Add `tests/test_scrape_wavespeed_catalog.py::test_main_ensures_column` — run `main(["--dry-run"])` on a fresh temp DB; assert `via_wavespeed` column present after.
3. Run → GREEN.

**A.4 — Verify with a real fetch (behavior 6 — cache round-trip).**
1. Add `tests/test_scrape_wavespeed_catalog.py::test_fetch_and_cache_roundtrip` marked `@pytest.mark.integration` (opt-in) — actually hit the API, assert `CATALOG_CACHE_PATH` is written, load it back, assert `len(data) >= 900`.
2. Run: `python scripts/kilo-benchmarks/scrape_wavespeed_catalog.py --dry-run 2>&1 | head -20`.
   **Expected**: prints `[wavespeed] cached 941 models to scripts/kilo-benchmarks/cache/wavespeed_catalog.json` and `[wavespeed] dry-run — no rows written`.
3. `ls -la scripts/kilo-benchmarks/cache/wavespeed_catalog.json` — expect a JSON file > 1 MB.

**A.5 — Doc updates for this phase (per Doc Sync Matrix).**
1. `CHANGELOG.md` — append under `## [Unreleased]`:
   ```
   ### Added — WaveSpeed catalog scraper skeleton + via_wavespeed column (2026-07-12)
   - scripts/kilo-benchmarks/add_via_wavespeed_column.py — idempotent ALTER TABLE for via_wavespeed INTEGER.
   - scripts/kilo-benchmarks/scrape_wavespeed_catalog.py — Phase A skeleton: fetches /api/v3/models, caches JSON, --dry-run only.
   ```
2. `INDEX.md` — add the two new script rows in the `scripts/kilo-benchmarks/` section (matching adjacent format).
3. Run: `python scripts/enforcement/check_doc_sync.py 2>&1 | grep -iE "warn|error"` for files in this phase's diff. **Expected: empty** (WARN-clean for the phase's changed files).

**A.6 — Phase gate + review loop + commit.**
1. Run: `python scripts/final_gate.py --check --json | jq '.status'`. **Expected: "success"** (baseline: any pre-existing red owned by a sibling stays; only newly-red is yours to fix — spec's baseline discipline).
2. Run: `python -m pytest scripts/kilo-benchmarks/tests/test_add_via_wavespeed_column.py scripts/kilo-benchmarks/tests/test_scrape_wavespeed_catalog.py -v`. **Expected: all pass** (integration test skipped without `--run-integration`).
3. Run: `python scripts/enforcement/check_doc_sync.py`. **Expected: no WARN for files touched this phase.**
4. **`/fabrik-review` — BLOCKING gate, looped to no-op pass** on Phase A's changed surface (2 new scripts + 2 new test files + CHANGELOG + INDEX). Dispatch **pool-default** breadth finders via `fanout("review", units=[…], mode="read_only", allow_ungrounded=True, project="wavespeed-plan1", …)` (each owes `record_agent_run` + `results_table` + `set_quality` back-fill) **plus 1 native `fabrik-reviewer` on Opus** for the migration-critical schema change. Merge → refute → prove-before-fix each surviving finding with a kept regression test. Iterate find → fix → re-review until one round returns zero CONFIRMED **and** zero PLAUSIBLE findings. Every finding terminates FIXED or REFUTED.
5. Commit (explicit paths, provenance trailers per `CLAUDE.md § Agent Provenance Trailers`):
   ```
   feat(kilo-benchmarks): Phase A — WaveSpeed migration + scraper skeleton

   Agent-Role: orchestrator
   Agent-Phase: A
   Agent-Context: added via_wavespeed column + Phase A skeleton scraper (dry-run only, no row writes)

   Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
   ```
   Stage: `scripts/kilo-benchmarks/add_via_wavespeed_column.py scripts/kilo-benchmarks/scrape_wavespeed_catalog.py scripts/kilo-benchmarks/tests/test_add_via_wavespeed_column.py scripts/kilo-benchmarks/tests/test_scrape_wavespeed_catalog.py CHANGELOG.md INDEX.md docs/development/plans/2026-07-12-plan-1-wavespeed-integration.md` (plan-file update — flip `Status: DRAFT → IN-PROGRESS` and mark `Phase A ✅ EXECUTED <date> (<commit>)` on this same commit).

---

## Phase B — Full 941-row seed + via_wavespeed flip

**Deliverable:** all 928 serving-eligible WaveSpeed rows in `agents.db`; overlaps flagged `via_wavespeed=1`; `INSERT OR IGNORE` collision policy resolved.

**Files:**
- MODIFY `scripts/kilo-benchmarks/scrape_wavespeed_catalog.py` — enable the `--seed` code path (INSERT + flag-flip).
- MODIFY `scripts/kilo-benchmarks/tests/test_scrape_wavespeed_catalog.py` — behaviors 1, 3, 5 tests.

### Interfaces

**Consumes:**
- `add_via_wavespeed_column.ensure_via_wavespeed_column` (Phase A).
- `SERVICE_TYPE_MAPPING`, `PRICING_MULTIPLIERS`, `fetch_ws_models`, `output_cost_per_m`, `type_to_service_type` (Phase A).
- Precedent `apply_flags` at [scrape_modelscope_catalog.py:104-146](../../../scripts/kilo-benchmarks/scrape_modelscope_catalog.py#L104-L146) — mirror for canonical-id overlap detection.
- Precedent `ingest_new` at [scrape_modelscope_catalog.py:182-275](../../../scripts/kilo-benchmarks/scrape_modelscope_catalog.py#L182-L275) — mirror for INSERT OR IGNORE.

**Produces:**
- `scrape_wavespeed_catalog.canonical_slug(model_id: str) -> str` — strips the `wavespeed-ai/`, `pruna-ai/`, etc. prefix; used for cross-vendor overlap detection.
- `scrape_wavespeed_catalog.apply_wavespeed_flags(conn: sqlite3.Connection, ws_models: list[dict]) -> tuple[int, int]` — matches existing `apply_flags` signature; returns (matched, updated).
- `scrape_wavespeed_catalog.ingest_new_wavespeed(conn, ws_models) -> tuple[int, int]` — returns (inserted, skipped). Uses `INSERT OR IGNORE INTO agents (…)` — matches modelscope precedent; existing rows are NEVER overwritten (WaveSpeed-native only inserts; overlaps get via_wavespeed flip only).
- Agents rows inserted with columns filled: `id` (=WaveSpeed model_id verbatim, e.g. `wavespeed-ai/flux-schnell`), `api_id` (=model_id), `name`, `provider` (extracted from model_id prefix — `wavespeed-ai`/`pruna-ai`/`pixverse`/etc.), `service_type` (mapped), `output_cost_per_m` (computed), `input_cost_per_m` (=0 for non-LLM types), `description`, `via_wavespeed=1`, `status='active'`, `task_tier=2` (default balanced).
- **Idempotency contract**: `INSERT OR IGNORE` on `agents.id PRIMARY KEY` — Phase A's spec residual **#1 resolved here**: existing row wins; WaveSpeed rows only INSERT for NEW model_ids; overlaps get `via_wavespeed=1` via `apply_wavespeed_flags`. This matches the modelscope precedent exactly.

### Steps

**B.1 — TDD the flag-flip guarded counter (behavior 3 — off-by-one in the "updated" count silently misreports scrape health).**
1. Add `tests/test_scrape_wavespeed_catalog.py::test_apply_flags_guarded_counter` — seed a test DB with 3 rows matching WaveSpeed canonical slugs (2 with `via_wavespeed=0`, 1 with `via_wavespeed=1`); run `apply_wavespeed_flags`; assert `matched == 3`, `updated == 2`.
2. Run → RED.
3. Confirm RED for the right reason.
4. Implement `apply_wavespeed_flags` mirroring [scrape_modelscope_catalog.py:104-146](../../../scripts/kilo-benchmarks/scrape_modelscope_catalog.py#L104-L146), substituting `via_modelscope` → `via_wavespeed` and `_ms_to_agent_id_candidates` → `canonical_slug` + candidate list.
5. Run → GREEN.

**B.2 — Implement `canonical_slug` and overlap detection (behavior 1 support — needed for idempotent re-runs).**
1. Add `tests/test_scrape_wavespeed_catalog.py::test_canonical_slug` — parametrize: `("wavespeed-ai/flux-schnell", "flux-schnell")`, `("bfl/flux-schnell", "flux-schnell")`, `("pruna-ai/flux-schnell", "flux-schnell")`.
2. Implement `canonical_slug` as one-line function: `model_id.split("/", 1)[-1] if "/" in model_id else model_id`.
3. Run → GREEN.

**B.3 — Implement `ingest_new_wavespeed` + skip training rows (behavior 5).**
1. Add `tests/test_scrape_wavespeed_catalog.py::test_ingest_skips_training_rows` — feed a mock catalog including 2 `type="training"` rows; assert they're not in `agents` after ingest.
2. Add `tests/test_scrape_wavespeed_catalog.py::test_ingest_new_wavespeed_only` — feed a mock catalog with 5 novel model_ids + 3 already-in-DB model_ids; assert only 5 inserted; existing rows unchanged (compare `updated_at`).
3. Run → RED.
4. Implement `ingest_new_wavespeed`:
   - Iterate `ws_models`; skip `type=="training"`.
   - `service_type = type_to_service_type(m["type"])`; if `None`, skip.
   - Compute `output_cost = output_cost_per_m(m["base_price"], service_type)`.
   - Extract `provider = m["model_id"].split("/", 1)[0]`.
   - `INSERT OR IGNORE INTO agents (id, api_id, name, provider, service_type, output_cost_per_m, input_cost_per_m, description, via_wavespeed, status, task_tier) VALUES (?, ?, ?, ?, ?, ?, 0, ?, 1, 'active', 2)`.
5. Run → GREEN.

**B.4 — TDD full-run idempotency (behavior 1 — the flagship risk of this phase).**
1. Add `tests/test_scrape_wavespeed_catalog.py::test_main_seed_is_idempotent` — run `main(["--seed"])` twice on the same temp DB with a mocked `fetch_ws_models`; assert row count matches after the first run and stays identical after the second.
2. Run → RED (integration path).
3. Wire `main()`: on `--seed`, do the migration → fetch → cache → `apply_wavespeed_flags` → `ingest_new_wavespeed` → print counts (matched flipped, inserted, skipped-training).
4. Run → GREEN.

**B.5 — Live seed against the real API.**
1. Run: `python scripts/kilo-benchmarks/scrape_wavespeed_catalog.py --seed`. **Expected**: prints `[wavespeed] fetched 941 models · 13 training skipped · N matched (via_wavespeed flipped on existing rows) · M inserted (WaveSpeed-native new rows) · total 928 serving rows processed`.
2. Verify: `sqlite3 scripts/kilo-benchmarks/kilo_agents.db "SELECT COUNT(*) FROM agents WHERE via_wavespeed = 1"`. **Expected**: ≥ 900 (M new + N flipped, all `via_wavespeed=1`).
3. Verify: `sqlite3 scripts/kilo-benchmarks/kilo_agents.db "SELECT service_type, COUNT(*) FROM agents WHERE via_wavespeed = 1 GROUP BY service_type"`. **Expected**: roughly matches the spec's mapping-count table (`image_gen: ~363, video_gen: ~422, music_gen: ~76, stt: 10, ocr: 21, llm: 6, 3d_gen: 25, moderation: 5`; existing overlaps + inserts).
4. Verify idempotency: run the scrape a second time. **Expected**: `matched N (0 newly flipped) · 0 inserted · idempotent no-op`.

**B.6 — Doc updates for this phase.**
1. `CHANGELOG.md` — append:
   ```
   ### Changed — WaveSpeed catalog seeded (~928 rows) into agents.db (2026-07-12)
   - scripts/kilo-benchmarks/scrape_wavespeed_catalog.py --seed now writes catalog rows and flips via_wavespeed=1 on overlaps.
   ```
2. `docs/reference/kilo/AI_VENDOR_ACCESS.md` — update WaveSpeed row `DB provider(s)` cell from `(none yet — catalog seed pending)` to the actual populated set observed by `sqlite3 kilo_agents.db "SELECT DISTINCT provider FROM agents WHERE via_wavespeed = 1 ORDER BY 1"` (typically `wavespeed-ai, pruna-ai, pixverse, kwaivgi, sync, ...`).

**B.7 — Phase gate + review loop + commit.**
1. Run: `python scripts/final_gate.py --check --json | jq '.status'`. **Expected: "success"**.
2. Run: `python -m pytest scripts/kilo-benchmarks/tests/test_scrape_wavespeed_catalog.py -v`. **Expected: all pass**.
3. Run: `python scripts/enforcement/check_doc_sync.py`. **Expected: no WARN for Phase B's diff**.
4. **`/fabrik-review` — BLOCKING gate, looped to no-op** on Phase B's changed surface (scraper implementation + tests + CHANGELOG + AI_VENDOR_ACCESS). Pool-default breadth via `fanout("review", …)` + native `fabrik-reviewer` Opus for the mass-INSERT + idempotency logic (auth path, unique constraint reasoning, race conditions). Merge → refute → prove-before-fix. Iterate to no-op.
5. Commit — Agent-Role: orchestrator, Agent-Phase: B. Stage the plan-file phase-B `✅ EXECUTED` marker in this same commit.

---

## Phase C — service_type enum extension + daily_refresh.sh wiring

**Deliverable:** the two new enum values (`3d_gen`, `moderation`) recognized by every downstream service_type consumer; scraper wired into daily cron; browser catches `3d_gen` and `moderation` rows.

**Files:**
- MODIFY `scripts/kilo-benchmarks/seed_specialty_catalog.py` — extend the allowlist at line 163.
- MODIFY `scripts/kilo-benchmarks/daily_refresh.sh` — add step to run `scrape_wavespeed_catalog.py --seed`.
- CREATE `scripts/kilo-benchmarks/tests/test_service_type_extension.py` — behavior around the new enum values.

### Interfaces

**Consumes:**
- Rows written by Phase B (existing `agents` rows with `service_type IN ('3d_gen', 'moderation')`).
- `seed_specialty_catalog.py:163` — the actual enum allowlist.
- `daily_refresh.sh` step sequence.

**Produces:**
- `seed_specialty_catalog.py` — allowlist extended to `{"tts", "stt", "translation", "image_gen", "music_gen", "video_gen", "ocr", "3d_gen", "moderation"}` (adds `video_gen`, `ocr`, `3d_gen`, `moderation` — the video/ocr ones are silently already-populated by Phase B; sanity-add them so future runs of `seed_specialty_catalog` don't drop them).
- `daily_refresh.sh` — one new step `python scrape_wavespeed_catalog.py --seed || echo "[wavespeed] failed (non-fatal)"` inserted between the modelscope scrape and `export_models_browser.py` (matches existing convention).

### Steps

**C.1 — Grep for other hard-coded service_type allowlists (audit for hidden gates).**
1. Run: `grep -rn "service_type\s*not\s*in\|service_type\s*==\|SERVICE_TYPES\s*=" scripts/kilo-benchmarks/ --include="*.py"`. **Expected**: exhaustive list of every service_type gate. Add each to `docs/development/plans/2026-07-12-plan-1-wavespeed-integration.md` Evidence section as a hit list.
2. For each gate, decide: does it need extension (allowlist) or not (denylist / display-only)? Extend those that would drop 3d_gen/moderation rows.
3. Confirmed target: `seed_specialty_catalog.py:163`. Any other hit gets its own step here.

**C.2 — TDD the enum extension.**
1. Add `tests/test_service_type_extension.py::test_3d_gen_and_moderation_pass_specialty_gate` — mock a call to `seed_specialty_catalog.<function>` with `service_type='3d_gen'`; assert row is NOT skipped.
2. Run → RED (current allowlist excludes them).
3. Edit `seed_specialty_catalog.py:163`: `if service_type not in {"tts", "stt", "translation", "image_gen", "music_gen", "video_gen", "ocr", "3d_gen", "moderation"}: continue`.
4. Run → GREEN.

**C.3 — Wire scraper into `daily_refresh.sh`.**
1. Edit `daily_refresh.sh` — after the modelscope scrape line, add:
   ```
   "$VENV_PY" scrape_wavespeed_catalog.py --seed || echo "[wavespeed] failed (non-fatal)"
   ```
2. Verify: `bash -n scripts/kilo-benchmarks/daily_refresh.sh`. **Expected: no output** (syntax OK).
3. Verify insertion point: `grep -n "wavespeed\|modelscope\|export_models_browser" scripts/kilo-benchmarks/daily_refresh.sh`. **Expected**: wavespeed line appears between the last modelscope reference and `export_models_browser.py`.

**C.4 — Behavior contract test for non-fatal failure (behavior 7).**
1. Add `tests/test_daily_refresh_wavespeed_step.py::test_daily_refresh_continues_on_wavespeed_500` — inject a mocked `scrape_wavespeed_catalog.py` that exits 1, verify `daily_refresh.sh` (or a stub of the relevant loop) continues to `export_models_browser.py`. If a full sh test is too heavy, satisfy the contract by asserting `set -e` is NOT set at that step's granularity (grep the shell script) — this proves non-fatality by construction, matching how other steps are safeguarded.
2. Run → GREEN.

**C.5 — Doc updates for this phase.**
1. `CHANGELOG.md` — append:
   ```
   ### Changed — WaveSpeed scrape wired into daily_refresh.sh + service_type enum extended (2026-07-12)
   - seed_specialty_catalog.py allowlist now includes video_gen, ocr, 3d_gen, moderation.
   - daily_refresh.sh runs scrape_wavespeed_catalog.py --seed after the modelscope step.
   ```
2. No new INDEX entries (no new files).

**C.6 — Phase gate + review loop + commit.**
1. Run: `python scripts/final_gate.py --check --json | jq '.status'`. **Expected: "success"**.
2. Run: `python -m pytest scripts/kilo-benchmarks/tests/test_service_type_extension.py scripts/kilo-benchmarks/tests/test_daily_refresh_wavespeed_step.py -v`. **Expected: all pass**.
3. Run: `python scripts/enforcement/check_doc_sync.py`. **Expected: no WARN**.
4. **`/fabrik-review` — BLOCKING gate, looped to no-op** on Phase C's changed surface. Pool-default breadth via `fanout("review", …)` (no schema/auth risk this phase — no mandatory native Opus). Merge → refute → prove-before-fix → iterate to no-op.
5. Commit — Agent-Role: orchestrator, Agent-Phase: C. Stage the plan-file `✅ EXECUTED` marker.

---

## Phase D — GUI badge + payload update (`models_browser.html`)

**Deliverable:** every WaveSpeed row visible in `models_browser.html`; `Via WaveSpeed` badge renders; `service_type='3d_gen'` and `'moderation'` filter buttons work.

**Files:**
- MODIFY `scripts/kilo-benchmarks/export_models_browser.py` — include `via_wavespeed` in the payload (currently `SELECT *` already picks it up, but audit); extend service_type filter list to include new enums.
- MODIFY `scripts/kilo-benchmarks/models_browser.html` — add `Via WaveSpeed` badge (matching existing `via_siliconflow`/`via_modelscope` pattern); extend service_type filter dropdown.
- MODIFY `scripts/kilo-benchmarks/tests/test_export_models_browser.py` (if it exists — else create with just the WaveSpeed-relevant tests) — behaviors 8.

### Interfaces

**Consumes:**
- Rows written by Phase B (`agents.via_wavespeed=1` and `service_type IN ('3d_gen', 'moderation')`).
- Existing HTML badge pattern in `models_browser.html` (the JS iteration that reads each `via_*` field and renders a `<span class="badge">` — grep it Phase D step 1).
- Existing service_type filter dropdown or filter chip list in `models_browser.html`.

**Produces:**
- Updated payload JSON exposes `via_wavespeed` on every row (Phase B guarantees the column; `SELECT *` picks it up — audit + assert).
- New badge span rendered when `row.via_wavespeed === 1`.
- Filter for `service_type='3d_gen'` and `'moderation'` accepts + surfaces matching rows.

### Steps

**D.1 — Audit existing payload / badge pattern.**
1. Run: `grep -n "via_openrouter\|via_kilo\|via_siliconflow\|via_modelscope\|via_dashscope" scripts/kilo-benchmarks/models_browser.html | grep -v "id=\"payload\"" | head -20`. **Expected**: locates the JS badge iteration; capture the loop / conditional block for mirroring.
2. Confirm payload already exposes `via_wavespeed`: `python scripts/kilo-benchmarks/export_models_browser.py && python -c "import json,re; html=open('scripts/kilo-benchmarks/models_browser.html').read(); m=re.search(r'<!--DATA_PLACEHOLDER-->(.*?)</script>', html); assert m; payload=json.loads(m.group(1) if False else html[html.index('id=\"payload\">')+len('id=\"payload\">'):html.index('</script>', html.index('id=\"payload\">'))]); print('via_wavespeed present:', 'via_wavespeed' in payload['chat_models'][0])"`. Or simpler: `grep -c "via_wavespeed" scripts/kilo-benchmarks/models_browser.html` after re-running export. **Expected**: > 0.

**D.2 — TDD the badge presence (behavior 8).**
1. Add `tests/test_models_browser_payload.py::test_wavespeed_badge_row_in_payload` (create test file with the AFTER-EDIT header) — run `_build_payload(DB_PATH)`; assert at least 100 rows have `via_wavespeed == 1`. Assert at least one row has `service_type == '3d_gen'` and one `'moderation'`.
2. Run → GREEN (already true after Phase B), OR RED if the payload build path drops these — investigate + fix.

**D.3 — Extend the HTML badge iteration.**
1. Edit `models_browser.html` — find the badge iteration block (from D.1) and add the WaveSpeed case, mirroring the sibling `via_siliconflow` case verbatim (label: `Via WaveSpeed`; color/class matches the badge pattern — read the adjacent CSS class).
2. Verify: `python scripts/kilo-benchmarks/export_models_browser.py && grep -c "Via WaveSpeed\|via_wavespeed" scripts/kilo-benchmarks/models_browser.html`. **Expected**: > 5 (badge label + JS conditional + payload rows).

**D.4 — Extend the service_type filter (if the browser has a dropdown/filter).**
1. Grep: `grep -n "service_type\|image_gen\|video_gen" scripts/kilo-benchmarks/models_browser.html | head -20`. Locate the filter definition.
2. Add `3d_gen` and `moderation` options in the same format as adjacent enums.
3. Manual check via `firefox scripts/kilo-benchmarks/models_browser.html` or `python -m http.server 8000 --directory scripts/kilo-benchmarks/` then browse to `localhost:8000/models_browser.html` — filter by `3d_gen`, confirm rows show up. (This is an inspection step, not an automated test — the browser is internal-only.)

**D.5 — Doc updates for this phase.**
1. `CHANGELOG.md` — append:
   ```
   ### Added — Via WaveSpeed badge + 3d_gen/moderation filters in models_browser.html (2026-07-12)
   - export_models_browser.py payload now includes via_wavespeed on every row.
   - models_browser.html renders Via WaveSpeed badge + accepts 3d_gen/moderation filter values.
   ```
2. No new INDEX entries (only modifications).

**D.6 — Final phase gate + full-plan review + `/fabrik-docs-review`.**
1. Run: `python scripts/final_gate.py --json | jq '.status'` (Tier 2 — full, not `--check`). **Expected: "success"**. If a red exists that was red at plan start (baseline captured Phase A step A.6.1), it's a sibling's file and not this plan's to fix; document the attribution.
2. Run: `python -m pytest scripts/kilo-benchmarks/tests/test_models_browser_payload.py -v`. **Expected: all pass**.
3. Run: `python scripts/enforcement/check_convergence.py`. **Expected: "success"**.
4. Run: `python scripts/enforcement/check_subagent_flywheel.py`. **Expected: no WARN** (all pool-default review dispatches from A/B/C/D recorded to `fabrik_analytics.subagent_runs`).
5. **`/fabrik-review` — BLOCKING gate, looped to no-op** on Phase D's changed surface AND on the whole-plan cumulative diff (verifies no cross-phase regression). Pool-default breadth + native Opus for the payload/HTML change (touches user-visible surface). Iterate to no-op.
6. **`/fabrik-docs-review` — BLOCKING** on the docs the whole plan touched (`CHANGELOG.md`, `INDEX.md`, `AI_VENDOR_ACCESS.md`, plus this plan file itself). Converge doc claims to a truthful fixed point (touch-on-change proves presence; this proves correctness).
7. Commit — Agent-Role: orchestrator, Agent-Phase: D. Stage the plan-file `✅ EXECUTED` marker + flip `Status: IN-PROGRESS → EXECUTED <date>`.

---

## Subagent strategy

Per `.windsurf/rules/core/62-using-subagents.md` § Dispatch policy, this plan's gradeable fan-outs (per-phase review finders, per-phase behavior-test authoring, whole-plan docs reconciliation) route through the **OpenRouter pool via `fanout(task_type, units, …)`**:

| Fan-out | Where | Recipe | Records to |
|---|---|---|---|
| `/fabrik-review` breadth finders | every phase step A.6.4 / B.7.4 / C.6.4 / D.6.5 | `fanout("review", units=[dim1, dim2, dim3], mode="read_only", allow_ungrounded=True, project="wavespeed-plan1", …)` + `set_quality` back-fill each | `fabrik_analytics.subagent_runs` |
| Native Opus review pass | A.6.4 (schema migration), B.7.4 (mass INSERT + idempotency), D.6.5 (user-visible payload) | `Agent(subagent_type="fabrik-reviewer", model="opus", …)` — decide/merge you own | records nothing (native by nature) |
| Behavior-test authoring | inside phase steps A.1/A.2/B.1/B.3/C.2 | `fanout("code", units=[test_spec_A1, test_spec_A2, …], mode="write", owned_paths=[disjoint per unit], project="wavespeed-plan1", …)` — you `git apply` the survivors and re-run the phase gate | `fabrik_analytics.subagent_runs` |
| Doc reconciliation | D.6.6 (`/fabrik-docs-review`) | `fanout("docs", units=[per-file spec], mode="read_only", …)` + `set_quality` back-fill | `fabrik_analytics.subagent_runs` |

**Parallelism**: A/B are sequential (B consumes A's column + scraper skeleton); C/D can run in parallel after B (C touches `seed_specialty_catalog.py` + `daily_refresh.sh`; D touches `export_models_browser.py` + `models_browser.html` — disjoint). If parallelized, the executor must acquire a scope lock covering C+D's owned paths as a set.

## File Scope (owned paths)

- CREATE `scripts/kilo-benchmarks/add_via_wavespeed_column.py`
- CREATE `scripts/kilo-benchmarks/scrape_wavespeed_catalog.py`
- CREATE `scripts/kilo-benchmarks/tests/test_add_via_wavespeed_column.py`
- CREATE `scripts/kilo-benchmarks/tests/test_scrape_wavespeed_catalog.py`
- CREATE `scripts/kilo-benchmarks/tests/test_service_type_extension.py`
- CREATE `scripts/kilo-benchmarks/tests/test_daily_refresh_wavespeed_step.py`
- CREATE `scripts/kilo-benchmarks/tests/test_models_browser_payload.py`
- MODIFY `scripts/kilo-benchmarks/seed_specialty_catalog.py` (line 163 allowlist only)
- MODIFY `scripts/kilo-benchmarks/daily_refresh.sh` (add one step)
- MODIFY `scripts/kilo-benchmarks/export_models_browser.py` (audit; extend payload if needed)
- MODIFY `scripts/kilo-benchmarks/models_browser.html` (badge + filter list)
- MODIFY `scripts/kilo-benchmarks/kilo_agents.db` (schema: +1 column; data: ~928 rows via migration+scrape)
- MODIFY `scripts/kilo-benchmarks/cache/wavespeed_catalog.json` (gitignored — not committed)
- MODIFY `CHANGELOG.md` (4 entries appended under `[Unreleased]`)
- MODIFY `INDEX.md` (2 new script rows)
- MODIFY `docs/reference/kilo/AI_VENDOR_ACCESS.md` (WaveSpeed row `DB provider(s)` cell)
- MODIFY `docs/development/plans/2026-07-12-plan-1-wavespeed-integration.md` (this file — Status flip + `Phase X ✅ EXECUTED` per phase commit)

**Disjoint from any known-active sibling plan** at scope-lock time (spec resolved 2026-07-12; verify at scope-lock acquisition per `/fabrik-execute-plan` step 7).

## Evidence

### Phase A — grounded in

- [add_perf_seconds_column.py:20-32](../../../scripts/kilo-benchmarks/add_perf_seconds_column.py#L20-L32) — verbatim precedent for `ensure_via_wavespeed_column`.
- [ms_enrich.py:23](../../../scripts/kilo-benchmarks/ms_enrich.py#L23) — `httpx` sync client idiom (matches kilo-benchmarks convention).
- Live probe: `curl -sS -H "Authorization: Bearer $KEY" https://api.wavespeed.ai/api/v3/models | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["data"]))'` → **941** (verified 2026-07-12).

### Phase B — grounded in

- [scrape_modelscope_catalog.py:104-146](../../../scripts/kilo-benchmarks/scrape_modelscope_catalog.py#L104-L146) — `apply_flags` verbatim precedent.
- [scrape_modelscope_catalog.py:182-275](../../../scripts/kilo-benchmarks/scrape_modelscope_catalog.py#L182-L275) — `ingest_new` INSERT OR IGNORE precedent.
- Schema live-check:
  ```
  $ sqlite3 kilo_agents.db "PRAGMA table_info(agents)" | grep via_
  35|via_openrouter|INTEGER|0|0|0
  36|via_kilo|INTEGER|0|0|0
  46|via_dashscope|INTEGER|0|0|0
  47|via_siliconflow|INTEGER|0|0|0
  87|via_modelscope|INTEGER|0|0|0
  ```
  `via_wavespeed` absent — added by Phase A migration.
- Current service_type distribution: `llm:656, image_gen:50, video_gen:28, tts:22, embedding:20, stt:18, translation:8, ocr:5, rerank:4, music_gen:4` (10 enums, 815 rows — verified this session).

### Phase C — grounded in

- [seed_specialty_catalog.py:163](../../../scripts/kilo-benchmarks/seed_specialty_catalog.py#L163) — **the real enum allowlist** (spec had this wrong: said `derive_quality_v2.py::SERVICE_TYPES_KNOWN`, but that constant doesn't exist there; `derive_quality_v2` gates on family regex + bench thresholds, not on `service_type`).
- `daily_refresh.sh` — existing 9-step chain with `|| echo "[step] failed (non-fatal)"` convention (verified this session).

### Phase D — grounded in

- [export_models_browser.py:35-78](../../../scripts/kilo-benchmarks/export_models_browser.py#L35-L78) — `_fetch_chat_models` uses `SELECT * FROM agents` → `via_wavespeed` picked up automatically.
- [export_models_browser.py:378](../../../scripts/kilo-benchmarks/export_models_browser.py#L378) — the `<!--DATA_PLACEHOLDER-->` injection marker.
- Live payload preview confirms `via_openrouter`, `via_kilo`, `via_dashscope`, `via_siliconflow`, `via_modelscope` all present in the JSON blob today.

## Self-audit

### Grounding passes run

- Pass 1 — solo (this turn). Read: spec (155 lines), `select_rules.py` ACTIVE packs (19), agents.db schema, `add_perf_seconds_column.py` (full), `scrape_modelscope_catalog.py::apply_flags` + `ingest_new` (full), `discover_kilo_agents.py` (imports + insert), `derive_quality_v2.py` (first 100 lines), `seed_specialty_catalog.py::_infer_service_type` + line 163 allowlist, `export_models_browser.py::_fetch_chat_models`, `daily_refresh.sh` (full, 80 lines). Live URLs: 8 (WaveSpeed catalog, 3 API endpoints, 4 doc URLs). Live API probes: `/api/v3/models` (941 rows), `/api/v3/balance` ({balance:1}), `/api/v3/model/pricing` (HTTP 500 on flux-dev-fill — as spec said).
- **Finding — spec drift caught, adjusted in plan**: spec § Chosen approach #3 said "modify `derive_quality_v2.py`'s `SERVICE_TYPES_KNOWN` set" — that constant does not exist in `derive_quality_v2.py` (gates on family regex + benchmark thresholds, NOT on `service_type`). The real enum allowlist is [seed_specialty_catalog.py:163](../../../scripts/kilo-benchmarks/seed_specialty_catalog.py#L163). Plan Phase C targets the correct file. Also planned an audit-grep at C.1 to catch any other hard-coded service_type gates.

### (a) Coverage — every "What we already agreed" (Phase 0 of the spec) delivered by a phase

- Goal (wire WaveSpeed catalog into agents.db + models_browser.html) → Phases A+B+D.
- Composition #1 `scrape_wavespeed_catalog.py` → Phase A (skeleton) + B (seed logic).
- Composition #2 `add_via_wavespeed_column.py` → Phase A.
- Composition #3 `derive_quality_v2.py` delta → **corrected** in Phase C: real target is `seed_specialty_catalog.py:163`.
- Composition #4 `export_models_browser.py` + badge → Phase D.
- Composition #5 `AI_VENDOR_ACCESS.md` update → Phase B.6 (once seeded row-set is observed).
- Composition #6 `daily_refresh.sh` wiring → Phase C.
- Service_type mapping (8 categories → agent enums) → Phase A.2 (dict literal + tests).
- Pricing normalization → Phase A.2 (`PRICING_MULTIPLIERS` dict + tests).
- No benching → out of scope; captured as Residual #3 (deferred).
- Idempotency contract → Phase B (INSERT OR IGNORE) + spec Residual #1 resolved.
- Browser payload null-tolerance for non-LLM columns → Phase D.1 + D.2 (audit + test).

### (b) Cross-phase signature consistency

Verified:
- `add_via_wavespeed_column.ensure_via_wavespeed_column` — declared Phase A Interfaces.Produces; consumed Phase B Interfaces.Consumes (`scrape_wavespeed_catalog.main()` imports it). Names match.
- `SERVICE_TYPE_MAPPING`, `PRICING_MULTIPLIERS`, `fetch_ws_models`, `output_cost_per_m`, `type_to_service_type` — declared Phase A; consumed Phase B. Names match.
- `apply_wavespeed_flags`, `ingest_new_wavespeed`, `canonical_slug` — declared Phase B; consumed by Phase B's own `main()` (no downstream consumer needed).
- Service_type new enum values (`3d_gen`, `moderation`) — introduced by Phase B seed; recognized by Phase C's allowlist extension; filtered by Phase D's dropdown. Names match end-to-end.

Fixed-point claim: this DRAFT contains the full grounding a fresh executor needs — every file cited exists at the line noted (spec drift caught + corrected); every Interfaces.Produces is Interfaces.Consumed later; every phase has a runnable gate + review + doc step + explicit commit stanza. Convergence to CONVERGED is `/fabrik-plan-review`'s job.

## Residual unknowns

### Resolved during this drafting

1. **INSERT priority policy for cross-vendor overlaps** — RESOLVED: use `INSERT OR IGNORE` (existing row wins; overlaps only get `via_wavespeed=1` flip). Matches modelscope precedent exactly. See Phase B.3.
2. **Which script gates on service_type allowlist** — RESOLVED: not `derive_quality_v2.py` as the spec said (that gates on family regex); the real gate is `seed_specialty_catalog.py:163`. Phase C targets the corrected file + C.1 audits for any other hidden gates.
3. **Browser null-tolerance for non-LLM columns** — RESOLVED via existing pattern: `SELECT *` populates every column, JS iteration handles NULL gracefully (verified with the 815 existing rows, many of which have NULL coding scores). Phase D.2 asserts this holds for the new rows.
4. **Rate-limit compliance** — RESOLVED: 1 daily request to `/api/v3/models` well within Bronze 2/min limit; no burst concern.

### Still-open (each with resolution self-service)

1. **[SELF-SERVICE — Phase D.4]** Whether `models_browser.html` has a dedicated `service_type` filter chip/dropdown vs displays it as a column-value only. Resolution: `grep -n "service_type\|filter" scripts/kilo-benchmarks/models_browser.html`; if a filter exists, extend it; if not, the value shows in the column and no HTML change is needed. Executor decides in the moment; either path is one grep.
2. **[SELF-SERVICE — Phase C.1]** Whether any hidden `service_type` gate exists in scripts we haven't grep'd. Resolution: `grep -rn "service_type\s*not\s*in\|service_type\s*==\|SERVICE_TYPES" scripts/kilo-benchmarks/ --include="*.py"` in Phase C.1; extend each hit.
3. **[SELF-SERVICE — deferred]** Real per-call cost via jsonata evaluation. Not blocking this plan (rejected alternative in spec). Deferred to a follow-up plan post-Silver-tier top-up if the base_price approximation proves inaccurate in production ranking.

## Handoff

**Next command:** `/fabrik-plan-review docs/development/plans/2026-07-12-plan-1-wavespeed-integration.md` — the mandatory adversarial convergence pass that re-grounds every phase's `path:line`, re-checks each behavior-contract test can actually run, and flips `Status: DRAFT → CONVERGED` (or holds at DRAFT if a blocking unknown remains).

**Then (user-triggered):** `/fabrik-execute-plan docs/development/plans/2026-07-12-plan-1-wavespeed-integration.md`.

**💡 fabrik-lib candidates** identified in this plan: **none**. The scraper pattern is project-local to kilo-benchmarks (matches SiliconFlow + ModelScope + Dashscope precedents); nothing generic enough to promote to a reusable module.
