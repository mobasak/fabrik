# AI-Model-Catalog Extraction — move the engine into the scaffolded /opt/ai-model-catalog

**Status:** CONVERGED
**Date:** 2026-07-26
**Converged:** 2026-07-26 (`/fabrik-plan-review`, md5-verified no-op). Grounded live: `check_ai_pack_freshness.py` at real `scripts/` path; B.4 `which docker` toolchain probe; `_atomic_copy` (`sync_enforcement_to_projects.py:278`); `compose.yaml` worker service (`:83`); `watch_enforcement_changes.sh:49-50`; `.pre-commit-config.yaml:57`; `fabrik_synced_manifest.py:29-30`; `select.py:479-483` fail-open. **Key decoupling (B.2e):** the artifact producers derive output from `SCRIPT_DIR.parent.parent` (`category_export_markdown.py:56`, `update_gateway_counts.py:40`) — an `OUTPUT_ROOT` env (default `ENGINE_ROOT/out`) redirects file producers to `engine/out/<rel>` and refactors the marker-injectors to emit `engine/out/blocks/*.txt` (injection moves fabrik-side to `deliver_to_fabrik.py`), so producers never clobber the scaffold's own `.windsurf/rules/ai`. Zero `fabrik`-CLI gates; all 3 residuals SELF-SERVICE (no deferred question rides into execution).)
**Design spec:** [docs/superpowers/specs/2026-07-26-catalog-extraction-design.md](../../superpowers/specs/2026-07-26-catalog-extraction-design.md) (CONVERGED — the grounded source of truth; this plan executes it)
**Scaffold type:** source = `python-api-gpu`-style batch engine (the moving part); target = `/opt/ai-model-catalog` (`saas-skeleton`, already scaffolded, GitHub `mobasak/ai-model-catalog`, hub spec `specs/services/ai-model-catalog.yaml`)
**Author:** primary (this session)
**Authority:** operator granted **full authority in both `/opt/fabrik` and `/opt/ai-model-catalog`** for the duration of this migration (cross-repo HARD STOP suspended for THIS plan's scope only).

## Goal

Relocate the ~176-file AI-model-catalog **engine** (scrape → normalize → derive → rank → export) out of `/opt/fabrik/scripts/kilo-benchmarks/` into `/opt/ai-model-catalog/engine/`, **without breaking fabrik or the ~55-project fleet, without losing functionality, and leaving zero engine residue in fabrik** — per the CONVERGED spec (Option A: publish-to-consumer, fabrik as tenant-zero; the **produce → deliver → sync → fleet** contract). The catalog product (API/UI/multi-tenant) is Phase-6 productization, **out of scope**.

## Global Constraints (verbatim — every phase inherits these)

- **Two repos, one migration:** source `/opt/fabrik`, target `/opt/ai-model-catalog`. Each has its own gate (`scripts/final_gate.py`) that never sees the other's commits — commit + gate per-repo, never cross.
- **Data store:** the engine keeps its **self-contained SQLite `kilo_agents.db`** as-is (relocation, not conversion). The saas-skeleton's Postgres is the Phase-6 product/app layer — **not** touched here. (Spec §4 Data stores.)
- **Fail-open floor is sacred:** `libs/subagents/select.py:479-483` (`table.get(task_type) or _TABLE[task_type]`) + the 14-day staleness gate (`:373`) mean a missing/stale selection doc degrades the fleet to the vendored `_TABLE`, never an outage. No step may weaken it.
- **Shared master:** stage **explicit paths only** (never `git add -A`/`-a`), `git diff --cached --name-only` before every commit, `git fetch` + ff before push, never touch sibling-authored files.
- **Engine = a scheduled WORKER, not a web service:** it deploys as a cron/worker container in `ai-model-catalog`'s compose (the scaffold already has a `worker` service at `compose.yaml:83`). The web tier (`app/`, `api/`) is Phase-6.
- **Vendor, don't import (lifecycle boundary):** the engine takes its **own vendored copy** of `libs/subagents/`, `libs/web_scrape/`, `alerting/`; fabrik keeps `libs/subagents` from `/opt/fabrik-lib`. No shared file between the moved engine and fabrik.
- **12-Factor (binding):** logs → unbuffered **stdout** (the engine's `cache/update.log` is a batch-cron artifact that relocates as-is; converting to stdout-only is a Phase-5 *deploy* concern, flagged not done here — XI); **no migrations from web startup** (XII, n/a — SQLite); **same backing services dev/prod** (X — SQLite is the catalog store in both; the flywheel is Postgres in both); config = env vars, no secrets in code (III); backing services by DSN not code (IV — the flywheel DSN).
- **Deploy = trigger, not execute** — no `fabrik …` gate anywhere (hub-only CLI); every gate is a runnable `python`/`pytest`/`grep`/`sqlite3` assert from WSL dev.
- **DB/infra invariants:** `postgres-main:5432`, `redis-main:6379`, external `fabrik` network, per-service `deploy.resources.limits.memory`, no host `ports:`, Traefik routes, stable container DNS.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/75-workers-jobs.md` (ACTIVE) | the engine IS a batch worker — idempotency, orphan-sweep, pause-state discipline apply to the relocated pipeline | `select_rules.py` ACTIVE |
| `.windsurf/rules/core/25-data-postgres.md` (ACTIVE) | migration discipline — but the engine store is SQLite; the only Postgres is the read-only flywheel DSN | ACTIVE |
| `.windsurf/rules/core/55-observability.md` (ACTIVE) | stdout-only logs; the engine's `update.log` is a known deviation flagged for Phase-6 | ACTIVE |
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | Behavior Contract per phase; the 49 engine tests port + run | ACTIVE |
| `.windsurf/rules/core/62-using-subagents.md` (ACTIVE) | pool-default fan-out for the per-phase review finders + parallel grounders | ACTIVE |
| `.windsurf/rules/core/40-documentation.md` (ACTIVE) | Doc Sync Matrix — CHANGELOG/INDEX/SERVICES/PROJECT_CATALOG updates are phase-owned | ACTIVE |
| `fabrik-lib` — `libs/subagents/` | **STAYS a shared `fabrik-lib` module** (canonical `/opt/fabrik-lib/subagents`); fabrik's `pick_models` + the fleet depend on it. The engine **vendors its own copy** (lifecycle split). Real API: `pick_models(task_type)`, `fanout(...)`, `record_agent_run`. | `libs/subagents/select.py`, `agent.py`, `pg_ledger.py` |
| `AGENTS.md` / `agents-fabrik.md` — hub deploy model | `fabrik apply specs/services/ai-model-catalog.yaml` (hub-side) deploys the project; the VPS `git pull`s from `mobasak/ai-model-catalog` | `agents-fabrik-core.md` |
| `specs/services/ai-model-catalog.yaml` `shape:` | `needs_database: true` · `needs_cache: true` · `exposes_metrics: true`, `source.type: git` — the deployed target; the engine-worker rides this spec | read the `shape:` block (inspection, not `fabrik plan`) |
| The consumer contract (spec §2) | the 6 output classes fabrik+fleet consume — the golden-file oracle of Phase 0 | spec §2 |

**fabrik-lib consult:** the only "new capability" is the **deliver-to-fabrik** step (Phase 2). It is file distribution — **reuse the existing `sync_enforcement_to_projects.py` copy/atomic-write pattern** (`_atomic_copy` at `sync_enforcement_to_projects.py:278`), not a fresh build. No new fabrik-lib module needed. **💡 fabrik-lib candidate: none.**

## Behavior Contract (whole plan — risk-ordered)

1. **Fleet `pick_models` keeps resolving after cutover** *(flagship risk — 56 vendored copies across the fleet)*. Test: after Phase 3, a live `fanout("code", …)`/`pick_models("code")` returns the same model set as the pre-cutover baseline; and with the selection doc force-removed, it falls to `_TABLE` (fail-open) rather than raising.
2. **Golden-file parity** *(the "no functionality lost" oracle)*: every produced artifact (selection docs, rule-pack marker blocks, `kilo_47_agents_final.json`, `capabilities.*`) is **byte-identical** from the relocated engine vs the Phase-0 baseline.
3. **No live consumer breaks**: the spec §2 consumer manifest (pick_models, rank_task_subagents coding-fallback, the doc-presence gates, the Traycer chain) all resolve against the delivered artifacts.
4. **Zero residue**: after Phase 4, `grep -r "kilo-benchmarks"` in `/opt/fabrik` returns only the intended consumer/distribution references; the dead Kilo/Cascade scripts + their sync-manifest/watch propagation are gone.
5. **Flywheel DSN**: the deployed engine reads `fabrik_analytics.subagent_runs` over a network DSN, or fail-opens (`rank_task_subagents.py:179` stub) — never breaks fabrik.
6. **Rollback holds**: until Phase 4, fabrik's own engine still runs; reverting = "turn delivery off."

Trivia skipped: exact worker-container image tag, log-line wording, `--help` text.

---

## Phase A — Freeze the contract (the golden-file regression oracle) · READ-ONLY · runs in `/opt/fabrik`

**Deliverable:** a committed golden snapshot + a runnable diff harness that reproduces every live consumer output — the objective definition of "no functionality lost."

**Files (CREATE, in fabrik):**
- CREATE `scripts/kilo-benchmarks/tests/golden/` — the snapshot dir (gitignored large blobs excepted).
- CREATE `scripts/kilo-benchmarks/tests/capture_golden.py` — snapshots the consumer artifacts + records the exact hub-consumer DB queries.
- CREATE `scripts/kilo-benchmarks/tests/test_golden_parity.py` — behavior 2 harness (re-run producers → diff vs golden).

### Interfaces
**Produces (for Phase B/C):** `capture_golden.GOLDEN_DIR: Path`; `capture_golden.snapshot() -> dict` (writes the golden set, returns a manifest of `{path: sha256}`); `test_golden_parity.assert_parity(produced_dir, golden_dir)`.

### Steps
**A.1 — Enumerate + snapshot the consumer manifest (behavior 2/3 oracle).**
1. Snapshot the six output classes to `tests/golden/`: `docs/reference/kilo/{TASK,CODING}_SUBAGENT_SELECTION.md` + the other 7 selection docs; the `.windsurf/rules/ai/*.md` `GATEWAY_COUNTS`+`OPENROUTER_ROUTES` **marker-block bodies only** (extract between the markers — the surrounding pack is not engine-owned); `scripts/kilo_47_agents_final.json`; `docs/CAPABILITIES.md`+`capabilities.json`+`llms.txt`; and `sha256` each.
2. Record the exact DB queries the live hub consumers run (from spec §2 grounding): `rank_task_subagents.py:335` (`SELECT id,quality_tier FROM agents…`), the coding-fallback read, `update_gateway_counts.py` counts. Store as `tests/golden/db_queries.json`.
3. Gate: `python scripts/kilo-benchmarks/tests/capture_golden.py && python -c "import json,pathlib; m=json.load(open('scripts/kilo-benchmarks/tests/golden/manifest.json')); print(len(m),'artifacts snapshotted'); assert len(m)>=12"` → **Expected:** ≥12 artifacts, manifest written.

**A.2 — Prove the harness reproduces live output (red-then-green on a no-op).**
1. Write `test_golden_parity.py::test_selection_docs_match_current` — re-read the live docs, assert `sha256 == golden`. On a clean tree it is GREEN by construction (the golden IS the live output). Then **mutate one golden byte and assert the test goes RED** (proves the diff actually bites) → revert.
2. Gate: `python -m pytest scripts/kilo-benchmarks/tests/test_golden_parity.py -v` → **Expected:** pass; the deliberate-mutation sub-case proves red-on-diff.

**A.3 — Behavior Contract (this phase):** behaviors 2 + 3's oracle exists and bites. Author via pool: `fanout("code", units=[test_golden_parity spec], mode="write", owned_paths=["scripts/kilo-benchmarks/tests/test_golden_parity.py"], project="catalog-extraction")` → curate → `git apply` → re-run gate.

**A.closing (every phase ends here):**
1. `python scripts/final_gate.py --check --json | jq '.status'` → fix newly-red to `"success"` (baseline: pre-existing sibling reds — `commands/_fragments` structure, `docs/claudeck` links — are **not** this plan's).
2. `python scripts/enforcement/check_doc_sync.py` → resolve any WARN whose trigger file is in this phase's diff.
3. **`/fabrik-review`** on Phase A's changed surface (the 2 test files + capture script) — pool-default finders via `fanout("review", mode="read_only", project="catalog-extraction")` + 1 native `fabrik-reviewer` (Opus) → refute → prove-before-fix → iterate to a coverage-adjudicated no-op.
4. `CHANGELOG.md` entry (`### Added — catalog-extraction golden-file harness`); commit (explicit paths + `Agent-Role: orchestrator`, `Agent-Phase: A`) staging the plan file with `Status: CONVERGED → IN-PROGRESS` + `Phase A ✅ EXECUTED <date> (<commit>)`.

---

## Phase B — Copy the engine into `/opt/ai-model-catalog/engine/` · fabrik UNTOUCHED · runs in `/opt/ai-model-catalog`

**Deliverable:** the engine runs standalone in `ai-model-catalog`, producing **byte-identical** outputs vs the Phase-A golden; fabrik's own engine still runs (parallel-safe).

**Files (CREATE, in ai-model-catalog):**
- CREATE `engine/` ← copy of `/opt/fabrik/scripts/kilo-benchmarks/**` (98 scripts + 49 tests + config YAMLs + `kilo_agents.db` + `models_browser_template.html` + vendored `libs/`, `alerting/`, `web_scrape/`, `direct_vendor_parsers/`, `specialty_clients/`, `translation_bench/`). **Exclude:** `process.py`, `process_v2.py` (throwaway — spec §3a), the `.lcb-venv/`/`.lcb-src/` vendored trees (rebuilt by `setup_lcb_grader.sh`).
- CREATE `engine/pyproject.toml` — the **subsystem dependency manifest** the engine never had (spec §2 gap): pin `httpx`, `beautifulsoup4`, `pyyaml`, `psycopg[binary]`, `sacrebleu`, etc. from the real imports.
- CREATE `engine/daily_refresh.sh` ← relocated, with the four fabrik tentacles severed (see B.2).
- MODIFY `compose.yaml` — wire the engine as a scheduled-worker service (reuse the existing `worker` at `compose.yaml:83` or add `engine-cron`), `deploy.resources.limits.memory` set.

### Interfaces
**Consumes:** the Phase-A golden set (`/opt/fabrik/scripts/kilo-benchmarks/tests/golden/` — read cross-repo for the parity assert).
**Produces (for Phase C):** `engine/daily_refresh.sh` (green standalone); the produced-artifact bundle at `engine/out/` in **fabrik-relative mirrored layout** — `engine/out/docs/reference/kilo/*.md`, `engine/out/scripts/kilo_47_agents_final.json`, `engine/out/docs/CAPABILITIES.md`+`capabilities.json` (file producers) — plus `engine/out/blocks/<host>.<MARKER>.txt` (injector-block content — OPENROUTER_ROUTES · GATEWAY_COUNTS · EMBEDDING_ROSTER/CATALOG/WINNERS · ROSTER, per B.2e) — same relative names/content as the Phase-A golden.

### Steps
**B.1 — Copy + prune.** `rsync -a --exclude process.py --exclude process_v2.py --exclude '.lcb-*' /opt/fabrik/scripts/kilo-benchmarks/ /opt/ai-model-catalog/engine/`.
1. Gate: `test -f /opt/ai-model-catalog/engine/kilo_agents.db && ls /opt/ai-model-catalog/engine/*.py | wc -l` → **Expected:** DB present, ~96 scripts (98 − 2 throwaway).

**B.2 — Sever the four fabrik tentacles (TDD the path-decoupling first — highest risk).**
1. Write `engine/tests/test_no_fabrik_paths.py::test_no_hardcoded_opt_fabrik` — grep the engine tree, assert **zero** `"/opt/fabrik"` string literals remain (excluding comments referencing history) and no `import` reaches outside `engine/`. Run → **RED** (copies still carry `/opt/fabrik` anchors).
2. Fix: (a) replace `FABRIK_ROOT`/`/opt/fabrik` anchors with an `ENGINE_ROOT = Path(__file__).resolve().parent` / `REPO_ROOT` env; (b) repoint `load_dotenv` from `/opt/fabrik/.env` → `engine/.env` (a repo-local `.env`, gitignored); (c) the flywheel read (`rank_task_subagents.py`) → a `FLYWHEEL_DSN` env (Phase E provisions the real DSN; here default unset → fail-open); (d) the vendored `libs/subagents` is the engine's own copy — delete the `/opt/fabrik-lib` doc references; **(e) — the OUTPUT decoupling (CRITICAL — a naive `FABRIK_ROOT`→`ENGINE_ROOT` swap clobbers the scaffold's own rules).** The artifact producers derive their write path from `FABRIK_ROOT = SCRIPT_DIR.parent.parent` (`category_export_markdown.py:56`; `update_gateway_counts.py:40` → `RULES_DIR = FABRIK_ROOT/.windsurf/rules/ai`) — under `engine/` that resolves to `/opt/ai-model-catalog/` and would **overwrite the scaffold's own `.windsurf/rules/ai`**. Introduce an `OUTPUT_ROOT` env (default `ENGINE_ROOT/out`) and split producers by kind (classify by MECHANISM — grep each for a `write_text` of a whole file vs a `START_MARKER not in content … replace-between-markers`): **file producers** — the whole-file writers: `rank_*` (atomic `tmp.write_text`+`os.replace`, `rank_task_subagents.py:1363`), `generate_model_capabilities` (`OUT_FILE.write_text`, `:155`), `export_traycer_registry` (`out_path.write_text`, `:158`), `export_models_browser` (template `write_text`) — write whole files under `OUTPUT_ROOT/<fabrik-relative-path>`; **injector producers** — the marker-replacers that edit an EXISTING host file (`category_export_markdown` OPENROUTER_ROUTES, `update_gateway_counts` GATEWAY_COUNTS, `embedding_export_markdown` EMBEDDING_ROSTER/CATALOG/WINNERS, `generate_selection_guide_roster` ROSTER — each does `if MARKER not in content: append else replace`, `pack_path.write_text(new_content)`) — are refactored to **emit the marker-block content** to `OUTPUT_ROOT/blocks/<host>.<MARKER>.txt`, and the marker-injection into fabrik's real packs/docs **moves to the Phase-C deliver step** (fabrik-side). Run → **GREEN**.
3. Gate: `python -m pytest engine/tests/test_no_fabrik_paths.py -v` → **Expected:** pass.
4. Gate (no-clobber isolation): `.venv/bin/python -m pytest engine/tests/test_output_root_isolation.py` — asserts a producer run writes **only** under `engine/out/` (mirrored + `blocks/`) and leaves `/opt/ai-model-catalog/.windsurf/rules/ai` **byte-unchanged**. → **Expected:** pass.

**B.3 — Standalone green + byte-identical parity (behavior 2 — the flagship of this phase).**
1. `cd /opt/ai-model-catalog/engine && python -m venv .venv && .venv/bin/pip install -e .` (toolchain preflight: `.venv/bin/python --version` → 3.11+; `which sqlite3`).
2. Run the artifact producers only (no live scrapes — feed the copied `kilo_agents.db`; `OUTPUT_ROOT=engine/out`): the file producers write `engine/out/<fabrik-relative>`, the injector producers emit `engine/out/blocks/*.txt` (per B.2e).
3. Write `engine/tests/test_parity_vs_fabrik_golden.py` — diff `engine/out/**` (file artifacts by relative path + the `blocks/*.txt` bodies vs the golden marker-block bodies) vs `/opt/fabrik/scripts/kilo-benchmarks/tests/golden/**` by sha256. Run → **Expected: byte-identical** (same DB + same code = same output). Any diff = a decoupling bug (a path/env leaked into content) → fix.
4. Gate: `.venv/bin/python -m pytest engine/tests/test_parity_vs_fabrik_golden.py engine/tests/ -v` → **Expected:** all 49 ported tests + parity pass.

**B.4 — Compose worker wiring.**
1. Toolchain preflight: `which docker` → **Expected:** `/usr/bin/docker` (present in WSL dev). Add the engine as a scheduled-worker service in `compose.yaml` (memory limit, `PYTHONUNBUFFERED=1`, `fabrik` network, no host ports); `docker compose -f compose.yaml config -q` (CLI-only, no daemon needed) → **Expected:** valid.
2. Gate: `grep -A6 "engine" compose.yaml | grep -E "limits:|memory:|PYTHONUNBUFFERED"` → **Expected:** all present.

**B.5 — Doc + spec updates.** `ai-model-catalog` `CHANGELOG.md`; `docs/SERVICES.md`+`docs/OPERATIONS.md` (new worker service — Doc Sync Matrix); confirm `specs/services/ai-model-catalog.yaml` `shape.needs_database:true` already covers the SQLite/worker (no flag change — SQLite isn't the shape DB; note it).

**B.Behavior Contract:** behaviors 2 (parity) + the decoupling invariant (B.2 — `test_no_fabrik_paths.py`) + the OUTPUT-isolation invariant (B.2e — `test_output_root_isolation.py`, no-clobber of the project's own `.windsurf/rules/ai`). Risky path (parity) is TDD'd first.

**B.closing:** run in **ai-model-catalog**: `python scripts/final_gate.py --check --json` (that project's gate) → green; `check_doc_sync.py`; **`/fabrik-review`** on `engine/**` + `compose.yaml` (pool finders + native Opus for the DB/idempotency/decoupling surface) → no-op; commit (`Agent-Phase: B`) + plan-file marker.

---

## Phase C — Delivery bridge + parallel-run · both repos · the safety window

**Deliverable:** `ai-model-catalog` **delivers** the produced bundle into fabrik's consumed paths; both engines run in parallel for ≥1 week; a daily diff proves zero divergence. Fabrik is still on its own engine — nothing has broken.

**Files:**
- CREATE (ai-model-catalog) `engine/deliver_to_fabrik.py` — two delivery modes (per B.2e): (a) **copies** the file artifacts `engine/out/<rel>` → fabrik's `docs/reference/kilo/`, `scripts/kilo_47_agents_final.json`, `docs/CAPABILITIES.md`+`capabilities.json` (reuse the `_atomic_copy` pattern from `sync_enforcement_to_projects.py:278`); (b) **injects** each `engine/out/blocks/<host>.<MARKER>.txt` into its live host file via marker-replace (the `.windsurf/rules/ai/*.md` packs for OPENROUTER_ROUTES/GATEWAY_COUNTS; the `docs/reference/kilo/` selection-guide docs for ROSTER/EMBEDDING_*) — the marker-injection the four injector producers used to do in-producer now runs fabrik-side HERE (the engine only emits block bodies).
- CREATE (fabrik) `scripts/kilo-benchmarks/tests/test_parallel_run_diff.py` — daily diff: delivered bundle vs fabrik-self-produced.

### Interfaces
**Consumes:** `engine/out/**` (Phase B). **Produces (for Phase D):** the delivered artifacts in fabrik's consumed paths; a `parallel_run.log` of daily diffs.

### Steps
**C.1 — Build the deliver step.** `deliver_to_fabrik.py --dry-run` prints the planned copies; `--apply` writes them (atomic). Gate: `python engine/deliver_to_fabrik.py --dry-run | grep -c "docs/reference/kilo"` → **Expected:** ≥9 (the selection docs).
**C.2 — Parallel-run (behavior 3, real-world).** Keep fabrik's `daily_refresh` running its engine; run ai-model-catalog's engine → deliver into a **shadow dir** (`/tmp/deliver-shadow/`, not fabrik's live paths yet). Daily for **≥7 days incl. a Sunday** (microbench day), diff shadow vs fabrik-live. Gate: `python -m pytest scripts/kilo-benchmarks/tests/test_parallel_run_diff.py` → **Expected:** zero diff across the window.
**C.3 — Behavior Contract:** behavior 3 (no consumer divergence) proven over a full week including the Sunday specialty-bench.

**C.closing:** gate green in **both** repos (each its own `final_gate --check`); `check_doc_sync`; **`/fabrik-review`** on `deliver_to_fabrik.py` (native Opus — it writes into fabrik's consumed paths, high-blast) + the diff test → no-op; commit per-repo (`Agent-Phase: C`).

---

## Phase D — Cutover · runs in `/opt/fabrik`

**Deliverable:** fabrik's `daily_refresh` **stops running engine steps**; the external engine (delivering live) is the sole producer; fabrik keeps `generate_kilo_agents` + `generate_capability_index` + `sync_enforcement`. The vendored `_TABLE` floor stays as the seatbelt.

**Files (MODIFY, fabrik):**
- MODIFY `scripts/kilo-benchmarks/daily_refresh.sh` — remove the ENGINE steps (spec §3 liveness inventory); keep the CONSUMER steps: `deliver` (or fetch) → `generate_kilo_agents` → `generate_capability_index` → `sync_enforcement_to_projects`.
- MODIFY `scripts/wsl_startup_hook.sh` — same engine-step removal from its boot block.

### Interfaces
**Consumes:** the delivered artifacts (Phase C, now to fabrik's live paths). **Produces (for Phase E):** a fabrik `daily_refresh` with no local engine.

### Steps
**D.1 — Flip delivery to live paths + shrink daily_refresh.** Point `deliver_to_fabrik.py` at fabrik's real consumed paths; remove the engine `_step` calls from `daily_refresh.sh`/`wsl_startup_hook.sh`. Gate: `grep -cE "verify_openrouter_catalog|scrape_|derive_|rank_" scripts/kilo-benchmarks/daily_refresh.sh` → **Expected: 0** engine producers remain (only consumer steps).
**D.2 — Cutover verification (behavior 1 — flagship).**
1. `python -c "import sys; sys.path.insert(0,'libs'); from subagents.select import pick_models; print(pick_models('code')[:3])"` → **Expected:** same top-3 as the pre-cutover baseline (captured in Phase A).
2. Force-remove the selection doc → assert `pick_models('code')` still returns (falls to `_TABLE`), not raises → restore. **Expected:** fail-open holds.
3. Freshness monitor: `python scripts/check_ai_pack_freshness.py` (grounded at `scripts/check_ai_pack_freshness.py`, run by `wsl_startup_hook.sh:164`) → **Expected:** delivered docs < 24h old.
4. Overlap ≥3 days monitoring `pick_models` + the flywheel.
**D.3 — Behavior Contract:** behavior 1 (fleet resolves post-cutover) + 5 (fail-open).

**D.closing:** `final_gate --json` (fabrik) → green; `check_doc_sync`; **`/fabrik-review`** on the orchestrator diffs + a live `fanout` smoke → no-op; commit (`Agent-Phase: D`).

---

## Phase E — Excise residue + deploy + finalize the flywheel DSN · both repos

**Deliverable:** the engine + dead Kilo/Cascade scripts are **gone from fabrik** (zero residue); `ai-model-catalog` is deployed via `fabrik apply`; the deployed engine reads the flywheel over a network DSN.

**Files:**
- DELETE (fabrik) `scripts/kilo-benchmarks/**` **engine files** (keep nothing engine-side); the dead scripts (spec §3c): `kilo_docs_enforcer.py`, `kilo_code_review.py`(+`_bckp`), `kilo_dispatch.py`, `kilo_consult.py`, `kilo_cost_report/tracker.py`, `Local_{Coder,Documentator,Review,Fixer}*.sh`, `kilo_agent_health.sh`, `fix_traycer_agents.py`, `Kilo_Review.sh`, `traycer_agent_review.py`, `mcp_kilo_server.py`, `process.py`, `process_v2.py`.
- MODIFY (fabrik) `scripts/fabrik_synced_manifest.py:29-30` (drop the dead scripts from `CORE_SCRIPTS`), `.pre-commit-config.yaml:57` + `scripts/watch_enforcement_changes.sh:49-50` (drop the dead-script patterns), `INDEX.md`/`PORTS.md`/`docs/PROJECT_CATALOG.md`/`docs/README.md`.

### Steps
**E.1 — Pre-delete safety grep (behavior 4).** `grep -rl "kilo-benchmarks" /opt/fabrik --include=*.py --include=*.sh | grep -v "libs/subagents\|/tests/golden\|generate_kilo_agents\|generate_capability_index\|sync_enforcement"` → **Expected: empty** (nothing live still imports the engine before delete). Any hit = an unmigrated consumer → resolve first.
**E.2 — Excise.** `git rm -r scripts/kilo-benchmarks/<engine files>` + the dead scripts; purge the sync-manifest/watch patterns. Gate: `grep -rc "kilo_code_review\|kilo_docs_enforcer" scripts/fabrik_synced_manifest.py .pre-commit-config.yaml` → **Expected: 0** (no longer propagated to the fleet).
**E.3 — Full gate + subagent-pool smoke (behavior 4).** `python scripts/final_gate.py --json` → `"success"` (baseline-attributed); run a real `/fabrik-review` finder round end-to-end to prove fabrik's brain still works headless.
**E.4 — Deploy (ai-model-catalog) + flywheel DSN (behavior 5).**
1. **Probe the flywheel's true host** (spec §4 — the DSN is host-less today): on the hub `psql "$SUBAGENT_RUNS_DSN" -c '\conninfo'` → record the physical instance.
2. Commit + push `ai-model-catalog`; **hand off to the operator** for hub-side `fabrik apply specs/services/ai-model-catalog.yaml` (deploy = trigger-not-execute; the plan does NOT self-deploy).
3. Provision a **network-reachable read-only DSN** to that instance; point `rank_task_subagents` at it; confirm `SELECT` works from the deployed worker (or fail-opens). Gate: `psql "$FLYWHEEL_DSN" -c "SELECT count(*) FROM subagent_runs"` from the deploy context → **Expected:** a count, or a clean fail-open stub.
**E.5 — Behavior Contract:** behaviors 4 (residue) + 5 (flywheel DSN).

**E.closing:** run the **whole-plan `/fabrik-review`** over the cumulative diff (→ no-op); `final_gate --json` green (fresh) in both repos; `check_convergence.py` green; `/fabrik-docs-review` on the touched docs; commit (`Agent-Phase: E`) + flip plan `Status: IN-PROGRESS → EXECUTED <date>`; archive the plan to `docs/development/plans/archived/`.

**Out of migration scope (Phase 6, separate plan):** the catalog *product* — API, UI rebuild, multi-tenancy, billing, stdout-log conversion, and licensing the 7 high-risk scraped-ranking feeds (per the extraction assessment).

---

## Subagent strategy

| Fan-out | Where | Recipe | Records |
|---|---|---|---|
| Per-phase `/fabrik-review` finders | A/B/C/D/E closing | `fanout("review", units=[dims], mode="read_only", project="catalog-extraction")` + `set_quality` + **≥1 native `fabrik-reviewer` (Opus)** on the high-blast slices (deliver step, cutover, residue-delete) | `subagent_runs` |
| Behavior-test authoring | A.3/B.2/B.3/C.1 | `fanout("code", mode="write", owned_paths=[disjoint per unit], project="catalog-extraction")` → curate → `git apply` | `subagent_runs` |
| Parallel grounding (this plan-review) | Phase 1 | `fanout("research", mode="read_only", web_tools=[…])` per independent unit + native `fabrik-researcher` (Haiku sample) | `subagent_runs` |

**Parallelism:** A→B→C→D→E are **sequential** (each consumes the prior). Within a phase, the review finders + test authors fan out in parallel and merge. Cross-repo: Phase B runs in ai-model-catalog, A/D in fabrik, C/E in both — no shared file within a phase.

## File Scope (owned paths)

- **fabrik:** `scripts/kilo-benchmarks/**` (snapshot in A, delete in E), `scripts/kilo-benchmarks/tests/golden/**`, `scripts/kilo-benchmarks/tests/test_{golden_parity,parallel_run_diff}.py`, `scripts/kilo-benchmarks/daily_refresh.sh`, `scripts/wsl_startup_hook.sh`, `scripts/fabrik_synced_manifest.py`, `.pre-commit-config.yaml`, `scripts/watch_enforcement_changes.sh`, the dead Kilo/Cascade scripts (E), `CHANGELOG.md`, `INDEX.md`, `PORTS.md`, `docs/PROJECT_CATALOG.md`, `docs/README.md`, this plan file.
- **ai-model-catalog:** `engine/**`, `compose.yaml`, `CHANGELOG.md`, `docs/SERVICES.md`, `docs/OPERATIONS.md`.
- **Disjoint** from any known-active sibling plan (verify at scope-lock). The fabrik `INDEX.md`/`PORTS.md`/`PROJECT_CATALOG.md` are shared-churn files → **serialization points** (stage only this plan's lines, per the shared-master rule).

## Evidence

### Phase A grounded in
- Consumer manifest: spec §2 (the six output classes) — verified live this session (`select.py:479-483` fallthrough, `rank_task_subagents.py:335` query).
- `sync_enforcement_to_projects.py:278` `_atomic_copy` (the deliver-step reuse) — read this session.

### Phase B grounded in
- `ai-model-catalog` structure — `ls /opt/ai-model-catalog` (has `engine`-able tree; `compose.yaml` already carries a `worker` service at `:83`):
  ```
  services: ai-model-catalog(:12) · api(:46) · worker(:83) · fabrik network(:113)
  ```
- Engine size: `98 top-level .py + 49 tests` in `scripts/kilo-benchmarks/`.

### Phase D grounded in
- Engine→consumer split: spec §3b (STAYS: `generate_kilo_agents`, `generate_capability_index`, `sync_enforcement`) — verified via `daily_refresh.sh:257/260` seam.
- Fail-open: `select.py:479-483` + `:373` 14-day gate; freshness: `check_ai_pack_freshness.py` (`wsl_startup_hook:164`).

### Phase E grounded in
- Dead-script inventory + non-propagation: spec §3c; `fabrik_synced_manifest.py:29-30`, `watch_enforcement_changes.sh:49-50`, git `55a53b9a` "retired Kilo/Cascade triad".
- Flywheel host-less DSN: spec §4 (`SUBAGENT_RUNS_DSN=postgresql:///fabrik_analytics`, `rank_task_subagents.py:179` fail-open, `:187-191` sudo-psql).

## Self-audit

### Grounding passes run
- Solo (this turn), inheriting the CONVERGED spec (5-pass /fabrik-spec-review, same session). Re-confirmed live: `select.py:479-483`, ACTIVE-packs (24), `ai-model-catalog` tree + `compose.yaml` worker service, engine file counts.

### (a) Coverage — every "What we already agreed" mapped
- Move engine → ai-model-catalog (spec Goal) → Phases B (copy) + D (cutover) + E (excise/deploy).
- Don't break fabrik/fleet (constraint 1/2) → Phase A golden + C parallel-run + D fail-open verification.
- No functionality lost (constraint 3) → Phase A/B byte-identical parity.
- Zero residue (constraint 4) → Phase E excise + pre-delete grep + sync-manifest purge.
- Option A / tenant-zero / produce→deliver→sync (D1) → Phase C deliver bridge + D (fabrik keeps sync).
- Flywheel read-only DSN (D2) → Phase E.4 probe + provision.
- Fold dead-residue purge (D3) → Phase E.2.
- Single plan, review per boundary (D4) → this plan, `/fabrik-review` in every phase's closing.
- SQLite stays / engine=worker (spec §4) → Global Constraints + Phase B.4.

### (b) Cross-phase signature consistency
- `capture_golden.GOLDEN_DIR` (A) ← consumed by `test_parity_vs_fabrik_golden` (B) + `test_parallel_run_diff` (C). Names match.
- `engine/out/**` — file producers write `engine/out/<fabrik-relative>`, injector producers emit `engine/out/blocks/*.txt` (B.2e produces) → `deliver_to_fabrik.py` copies the former + marker-injects the latter (C consumes). Match.
- `OUTPUT_ROOT` env (B.2e introduces, default `ENGINE_ROOT/out`, decouples writes from `SCRIPT_DIR.parent.parent` so producers never clobber the scaffold's own `.windsurf/rules/ai`) → the golden (A) captures the same relative artifacts + marker-block bodies the producers emit. Match.
- `FLYWHEEL_DSN` env (B.2 introduces, default-unset fail-open) → provisioned real (E.4). Match.

Fixed-point claim: this plan carries the full grounding a fresh executor needs; `/fabrik-plan-review` re-ground every `path:line` to an md5-verified no-op (incl. the B.2e OUTPUT-decoupling defect).

## Residual unknowns

### Resolved during drafting
1. **Engine target dir** — `engine/` in ai-model-catalog (convention; the scaffold's `worker` service hosts it). RESOLVED.
2. **SQLite vs Postgres** — SQLite stays (spec §4). RESOLVED.
3. **Deliver mechanism** — reuse `_atomic_copy` from `sync_enforcement`. RESOLVED.

### Still-open (each self-service)
1. **[SELF-SERVICE — Phase B.2]** Exact set of `/opt/fabrik` string literals to rewrite. Resolution: `test_no_fabrik_paths.py`'s grep enumerates them; fix each; the test gates it. No stop.
2. **[SELF-SERVICE — Phase E.4]** The flywheel's true physical host (DSN is host-less). Resolution: `psql "$SUBAGENT_RUNS_DSN" -c '\conninfo'` on the hub — a one-command probe, executor runs it. Fail-open covers a miss.
3. **[SELF-SERVICE — Phase E]** Whether any /opt project (beyond fabrik) imports the engine directly. Resolution: E.1's fleet-wide grep; extend the delete-guard to any hit. No stop.

## Handoff

**Next (user-triggered):** `/fabrik-execute-plan docs/development/plans/2026-07-26-plan-1-ai-model-catalog-extraction.md` — the plan is `CONVERGED` (this `/fabrik-plan-review` re-grounded it to an md5-verified no-op). Phase E.4's `fabrik apply` deploy is a hub-side operator step (trigger-not-execute).
**💡 fabrik-lib candidates:** none — the deliver step reuses `sync_enforcement`'s copy pattern; the engine is project-local.
