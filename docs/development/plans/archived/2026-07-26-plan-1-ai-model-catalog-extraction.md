# AI-Model-Catalog Extraction — move the engine into the scaffolded /opt/ai-model-catalog

**Status:** ✅ **EXECUTED 2026-08-15.** All five phases landed: A (`dedbb5e0`+`6879959d`), B (`9bdacfc`→`fa76d32`), C code (`07d0d51`,`5266354a`,`ee8988c`), D (`3d2b7c1`), E (`73bde59a`). C.2's ≥7-day window was **waived by operator ruling** — see Phase C. The engine now lives at `/opt/ai-model-catalog/engine/`; fabrik is a consumer. Behavior contract verified end-to-end: fleet `pick_models` identical to the pre-cutover baseline, fail-open holds, the coding router resolves, residue **0**, and the retained remnant is proven SOUND by a computed manifest rather than asserted. ⚠️ The review history below is kept deliberately: **11 passes found 150+ wrong claims**, and the lesson that mattered is that a ~100-file cross-referenced excise cannot be specified in prose — the set had to become a program. ⚠️ **NOT CONVERGED — corrected 2026-08-15.** This line
previously asserted a `dc3eddf8…` md5-verified no-op; that claim was **false at the time it was read**. Passes 2–7
of `/fabrik-plan-review` found **115** wrong or drifted claims (37 → 74 → 85 → 115 as each pass measured more; the header previously said 37, understating the defect density by 3×), none of them findable by re-reading the plan — every
one needed opening the file or running the command. See § Pass Ledger for the real, per-pass record; the plan
earns `CONVERGED` only when a pass makes zero edits with `md5(start) == md5(end)`. History: plan-review md5-no-op + a 5-round `/fabrik-review` (native Opus) fixing 24 excise-boundary defects, then rounds 8–11 (+38 fixes) — then **re-aligned 2026-08-12** to the re-converged spec: 9 drift fixes (WSL-only per D5, E.4 retired, B.2c DO-NOT-REWRITE, SQLite→Postgres, D2 superseded), Phase **A.0** added for the spec's binding flywheel-safety invariant, and 16 findings from an independent Opus grounder including 4 S1s (the Postgres conversion orphaning two retained SQLite consumers; a missing B.2g conversion step; the shared `/tmp` lockfile that let the parallel-run gate pass trivially; post-move positive-proof). The superseded prep set was archived unexecuted.

**Whole-plan review (E.closing):** [docs/development/reviews/2026-07-26-plan-1-ai-model-catalog-extraction-review.md](../../reviews/2026-07-26-plan-1-ai-model-catalog-extraction-review.md) — the coverage-adjudicated review of the cumulative D+E diff, which is the irreversible half of the migration.
**Date:** 2026-07-26
**Converged:** ⛔ **NOT CONVERGED — field retired pass 7.** It read *"2026-07-26 (`/fabrik-plan-review`, md5-verified no-op)"*; that no-op was not reproducible and the claim was false when read. Grounding notes from that pass follow, kept for their cites (several of which later proved wrong — see the blocker blocks): Grounded live: `check_ai_pack_freshness.py` at real `scripts/` path; B.4 `which docker` toolchain probe; `_atomic_copy` (`sync_enforcement_to_projects.py:279`); `compose.yaml` worker service (`:83`); `watch_enforcement_changes.sh:49-50`; `.pre-commit-config.yaml:65` (⚠️ was `:57` — corrected; `:57` is the unrelated `command-corpus-check` entry, E-B6); `fabrik_synced_manifest.py:29-30`; `select.py:479-483` fail-open. **Key decoupling (B.2e):** the artifact producers derive output from `SCRIPT_DIR.parent.parent` (`category_export_markdown.py:56`, `update_gateway_counts.py:40`) — an `OUTPUT_ROOT` env (default `ENGINE_ROOT/out`) redirects `FABRIK_ROOT`-derived file producers to `engine/out/<rel>`, the two `--output`-driven producers (`export_traycer_registry:52`, `export_models_browser:32`) get the flag from `daily_refresh.sh`, and the marker-injectors emit `engine/out/blocks/*.txt` (injection moves fabrik-side to `deliver_to_fabrik.py`), so producers never clobber the scaffold's own `.windsurf/rules/ai`. **Corrected by the `/fabrik-review` native-Opus pass:** `CAPABILITIES.md`/`capabilities.json`/`llms.txt` are `generate_capability_index.py` (retained fabrik consumer), NOT engine outputs — the engine's capability artifact is `KILO_MODEL_CAPABILITIES.md`; and fabrik's retained `generate_kilo_agents.py:38` reads `kilo_agents.db` directly, so the DB is delivered + kept (not deleted) in Phase E. Zero `fabrik`-CLI gates; all 3 residuals SELF-SERVICE (no deferred question rides into execution).)
**Design spec:** [docs/superpowers/specs/2026-07-26-catalog-extraction-design.md](../../superpowers/specs/2026-07-26-catalog-extraction-design.md) (CONVERGED — the grounded source of truth; this plan executes it)
**Scaffold type:** source = `python-api-gpu`-style batch engine (the moving part); target = `/opt/ai-model-catalog` (`saas-skeleton`, already scaffolded, GitHub `mobasak/ai-model-catalog`, hub spec `specs/services/ai-model-catalog.yaml`)
**Author:** primary (this session)
**Authority:** operator granted **full authority in both `/opt/fabrik` and `/opt/ai-model-catalog`** for the duration of this migration (cross-repo HARD STOP suspended for THIS plan's scope only).

## Goal

Relocate the ~176-file AI-model-catalog **engine** (scrape → normalize → derive → rank → export) out of `/opt/fabrik/scripts/kilo-benchmarks/` into `/opt/ai-model-catalog/engine/`, **without breaking fabrik or the ~55-project fleet, without losing functionality, and leaving zero engine residue in fabrik** — per the CONVERGED spec (Option A: publish-to-consumer, fabrik as tenant-zero; the **produce → deliver → sync → fleet** contract). The catalog product (API/UI/multi-tenant) is Phase-6 productization, **out of scope**.

## Global Constraints (verbatim — every phase inherits these)

- **⚠️ SCOPE IS WSL-ONLY (D5 resolved 2026-08-12, spec §7).** The engine relocates and keeps running on the WSL box. There is **no VPS deployment, no container, and no `fabrik apply` in this plan** — E.4 is retired to a separate later spec. **The flywheel does not move:** `fabrik_analytics` stays on the WSL host's local PostgreSQL, same unix socket, same reader (`sudo -n -u postgres psql`), same user; all 5 configured writers untouched. Operator constraint, binding on every phase: *we should not break flywheel.*

- **Two repos, one migration:** source `/opt/fabrik`, target `/opt/ai-model-catalog`. Each has its own gate (`scripts/final_gate.py`) that never sees the other's commits — commit + gate per-repo, never cross.
- **Data store (CHANGED 2026-08-12 — operator decision, spec §7):** the engine's SQLite `kilo_agents.db` is **consolidated into Postgres inside the new repo**. This supersedes the earlier *relocation, not conversion*. Phase B still COPIES the `.db` (it is both the migration SOURCE and the Phase-A parity oracle); the conversion is a B-phase step, not a Phase-6 deferral. It also independently closes the gitignored-DB gap (`.gitignore:126` — a git-sourced deploy would never have received the file). The saas app schema (users/accounts) stays Phase-6, untouched.
- **Fail-open floor is sacred:** `libs/subagents/select.py:479-483` (`table.get(task_type) or _TABLE[task_type]`) + the 14-day staleness gate (`:373`) mean a missing/stale selection doc degrades the fleet to the vendored `_TABLE`, never an outage. No step may weaken it.
- **Shared master:** stage **explicit paths only** (never `git add -A`/`-a`), `git diff --cached --name-only` before every commit, `git fetch` + ff before push, never touch sibling-authored files.
- **Engine = a scheduled WORKER, not a web service (WSL-only, D5):** it runs as a **WSL cron job** from `/opt/ai-model-catalog/engine/`, exactly as it does in fabrik today. ~~it deploys as a cron/worker container in `ai-model-catalog`'s compose~~ — containerisation moved to the later VPS spec (the scaffold already has a `worker` service at `compose.yaml:83`). The web tier (`app/`, `api/`) is Phase-6.
- **⚠️ DELIVERY TRANSPORT — the producing engine runs on the WSL hub box, NOT the VPS container (G3, resolved here so no phase assumes filesystem adjacency it lacks).** `deliver_to_fabrik.py` uses local-FS `_atomic_copy` from `/opt/ai-model-catalog/engine/out/` → `/opt/fabrik/...`; that is only valid because **both repos are on the same WSL box**, which is where the daily consumer chain (`daily_refresh.sh` cron) already runs. The **E.4 VPS deployment is the product/worker tier** (it exercises the engine in-container + serves Phase-6), and it **does NOT deliver to fabrik** — a container on vps1 cannot write `/opt/fabrik` on the WSL box. If delivery must later move to the deployed container, the transport becomes **publish-to-git** (engine commits `out/` to the `ai-model-catalog` repo; fabrik's `deliver` step becomes a `git pull` + copy) — that is the "(or fetch)" branch in D.1 and is **Phase-6 scope, not this plan**. No step in A–E may assume the VPS container has access to fabrik's filesystem.
- **Vendor, don't import (lifecycle boundary):** the engine takes its **own vendored copy** of `libs/subagents/`, `libs/web_scrape/`, `alerting/`; fabrik keeps `libs/subagents` from `/opt/fabrik-lib`. No shared file between the moved engine and fabrik.
- **12-Factor (binding):** logs → unbuffered **stdout** — **(rationale updated 2026-08-12 — B.4 is deleted and E.4 retired, so the container justification is dead; 12-Factor XI still binds because it binds every process, container or WSL cron)**, its `cache/update.log` file-write must become stdout-only **in Phase B (B.2f), before the container is wired**, not deferred (a deployed container writing a logfile is an active XI violation — Promtail→Loki owns routing). **The app writes NO logfile in any environment** — an operator wanting a local file redirects at the invocation layer (`daily_refresh.sh >> /var/log/… 2>&1` in cron), which is outside the app and 12F-legal; **no migrations from web startup** (XII — ⚠️ **CORRECTED 2026-08-15 (P5-9): this said "n/a — SQLite" and is
  no longer n/a.** B.2g converts the catalog store to Postgres, so XII becomes live and binding: the B.2g DDL +
  one-shot migrate script is an **admin process run against the deployed release**, never invoked from any
  startup path); **same backing services dev/prod** (X — ⚠️ same correction: this said "SQLite is the catalog
  store in both", which B.2g superseded. Post-conversion **Postgres is the catalog store in dev and prod**, and
  the flywheel is Postgres in both. Two lines above, Global Constraints already records the Postgres decision,
  and the Context Ledger already flags `25-data-postgres` as "NOW FULLY BINDING" — this bullet was the last
  place still asserting the retired SQLite answer); config = env vars, no secrets in code (III); backing services by DSN not code (IV — the flywheel DSN **and** the B.2g `CATALOG_DSN`).
- **Deploy = trigger, not execute** — no `fabrik …` gate anywhere (hub-only CLI); every gate is a runnable `python`/`pytest`/`grep`/`sqlite3` assert from WSL dev.
- **DB/infra invariants — ⚠️ NOT APPLICABLE under D5 (WSL-only); retained for the VPS spec.** In particular `postgres-main` is affirmatively WRONG for this plan: spec §4's probe shows the flywheel is on the WSL host's LOCAL socket, and the catalog store (B.2g) is the WSL local Postgres. ~~`postgres-main:5432`, `redis-main:6379`, external `fabrik` network, per-service `deploy.resources.limits.memory`, no host `ports:`, Traefik routes, stable container DNS.~~

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/75-workers-jobs.md` (ACTIVE) | the engine IS a batch worker — idempotency, orphan-sweep, pause-state discipline apply to the relocated pipeline | `select_rules.py` ACTIVE |
| `.windsurf/rules/core/25-data-postgres.md` (ACTIVE) | **NOW FULLY BINDING (corrected 2026-08-12):** B.2g performs a real SQLite→Postgres migration, so this pack's migration discipline governs the catalog store itself. The earlier text discharged an ACTIVE pack at exactly the moment a genuine Postgres migration entered scope. ~~migration discipline — but the engine store is SQLite; the only Postgres is the read-only flywheel DSN | ACTIVE |
| `.windsurf/rules/core/55-observability.md` (ACTIVE) | stdout-only logs. ⚠️ **Note the internal inconsistency (2026-08-12):** B.2f REMOVES the `update.log` write in Phase B, while this row called it a deviation deferred to Phase-6. B.2f wins — but since D5 removed the container that justified it, the removal is now an unforced behaviour change to a working WSL cron pipeline: **flag it for the operator rather than shipping it silently.** ~~the engine's `update.log` is a known deviation flagged for Phase-6 | ACTIVE |
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | Behavior Contract per phase; the engine test files port + run — ⚠️ **COUNT REMOVED pass 7. This plan has carried 64 / 67 / 68 / 69 / 70 / 71 for this one quantity. Compute it: `find engine/tests -name 'test_*.py' | wc -l`. The only assertion that means anything is that it does not SHRINK** | ACTIVE |
| `.windsurf/rules/core/62-using-subagents.md` (ACTIVE) | pool-default fan-out for the per-phase review finders + parallel grounders | ACTIVE |
| `.windsurf/rules/core/40-documentation.md` (ACTIVE) | Doc Sync Matrix — CHANGELOG/INDEX/SERVICES/PROJECT_CATALOG updates are phase-owned | ACTIVE |
| `fabrik-lib` — `libs/subagents/` | **STAYS a shared `fabrik-lib` module** (canonical `/opt/fabrik-lib/subagents`); fabrik's `pick_models` + the fleet depend on it. The engine **vendors its own copy** (lifecycle split). Real API: `pick_models(task_type)`, `fanout(...)`, `record_agent_run`. | `libs/subagents/select.py`, `agent.py`, `pg_ledger.py` |
| `AGENTS.md` / `agents-fabrik.md` — hub deploy model | **OUT OF SCOPE (D5)** — no deploy in this plan. Retained for the VPS spec: ~~`fabrik apply specs/services/ai-model-catalog.yaml` (hub-side) deploys the project; the VPS `git pull`s from `mobasak/ai-model-catalog` | `agents-fabrik-core.md` |
| `specs/services/ai-model-catalog.yaml` `shape:` | `needs_database: true` · `needs_cache: true` · `exposes_metrics: true`, `source.type: git` — the deployed target; the engine-worker rides this spec | read the `shape:` block (inspection, not `fabrik plan`) |
| The consumer contract (spec §2) | the 6 output classes fabrik+fleet consume — the golden-file oracle of Phase 0 | spec §2 |

**fabrik-lib consult:** the only "new capability" is the **deliver-to-fabrik** step (Phase 2). It is file distribution — **reuse the existing `sync_enforcement_to_projects.py` copy/atomic-write pattern** (`_atomic_copy` at `sync_enforcement_to_projects.py:279`), not a fresh build. No new fabrik-lib module needed. **💡 fabrik-lib candidate: none.**

## Behavior Contract (whole plan — risk-ordered)

1. **Fleet `pick_models` keeps resolving after cutover** *(flagship risk — **48** vendored copies, measured
   2026-08-15 via `ls -d /opt/*/libs/subagents | wc -l`; the repo's canonical figure is 49 at
   `daily_refresh.sh:456` + `rank_task_subagents.py:1373`. "56" was this plan's own invention — see D-B5)*. Test: after Phase 3, a live `fanout("code", …)`/`pick_models("code")` returns the same model set as the pre-cutover baseline; and with the selection doc force-removed, it falls to `_TABLE` (fail-open) rather than raising.
2. **Golden-file parity** *(the "no functionality lost" oracle)*: every **engine-produced** artifact (selection docs, rule-pack marker blocks, `kilo_47_agents_final.json`, `KILO_MODEL_CAPABILITIES.md` + its EMBEDDING_CATALOG block, `models_browser.html`) is **STRUCTURALLY equivalent** to the Phase-0 baseline — ⚠️ **"byte-identical" retired here in pass 7.** The 2026-08-12 blockquote replaced byte-identity with structural equivalence and moved byte-equality to Phase C's same-moment diff, but it only edited B.3's body; this, the MASTER contract a certification pass audits against, still said byte-identical. Byte-equality is asserted ONLY in C.2's same-instant old-vs-new diff. **NOT** `docs/CAPABILITIES.md`/`capabilities.json`/`llms.txt` — those are produced by `scripts/generate_capability_index.py` (`:406-407`, catalogs fabrik-lib, lives OUTSIDE `kilo-benchmarks/`), a **retained fabrik consumer** that STAYS (Phase D), not an engine output.
3. **No live consumer breaks**: the spec §2 consumer manifest (pick_models, rank_task_subagents coding-fallback, the doc-presence gates, the Traycer chain) all resolve against the delivered artifacts.
4. **Zero residue**: after Phase 4, `grep -r "kilo-benchmarks"` in `/opt/fabrik` returns only the intended consumer/distribution references; the dead Kilo/Cascade scripts + their sync-manifest/watch propagation are gone.
5. **Flywheel integrity (REPLACED 2026-08-12 — the deployed/network-DSN form retired with E.4)**: from the RELOCATED repo the read still returns `state=="ok"` with a NON-EMPTY row set, and a broken read still exits 1 (`rank_task_subagents.py:1374`) AND fires an alert rather than being swallowed at `daily_refresh.sh:423`. Fail-open stub returns are `:213`/`:216` — never breaks fabrik.
6. **Rollback holds**: until Phase 4, fabrik's own engine still runs; reverting = "turn delivery off."

Trivia skipped: exact worker-container image tag, log-line wording, `--help` text.

---

## Phase A — Freeze the contract + arm the flywheel tripwire · runs in `/opt/fabrik` — ✅ EXECUTED **2026-08-12** (`8cd1a402` — date corrected pass 7)

**A.0 — Flywheel-safety gates (NEW 2026-08-12; spec §7 *Flywheel-safety invariant*, BINDING).** The operator's
constraint is *"we should not break flywheel"*, and the relocation is the single event most likely to break the
read: `rank_task_subagents.py` authenticates via `sudo -n -u postgres psql` (`:187-191`), a property of the
INVOKING CONTEXT, not of the file's path. A prior `/fabrik-review` already built the right tripwire — `_query_rows()`
returns `(state, rows)` and `main()` returns **exit 1** when the read is BROKEN as distinct from genuinely empty
(`:1114`, `:1374`) — **but the call site mutes it**: `daily_refresh.sh:423` invokes the ranker as
`_step … || echo "[daily_refresh] rank_task_subagents failed (non-fatal)"`, and the file has **no `set -e`**
(grep-verified: 0 matches), redirects everything to `$LOG_FILE`, and the crontab has **no MAILTO**. So today a broken
read publishes a stub selection doc, fleet-syncs it to 49 vendored copies, and alerts nobody. Three gates, all
required, landed BEFORE any file moves:
1. **Positive proof, not absence of error** — assert `state == "ok"` AND a **non-empty** row set, run under the real
   cron user/shell. Gate: `sudo -n -u postgres psql -d fabrik_analytics -tAc "SELECT count(*) FROM subagent_runs"`
   → **Expected:** a non-zero count. A sudo/psql failure is **BLOCKING**, never a skip — "it didn't crash" is not
   evidence when the code fail-opens by design.
2. **Preserve the tripwire** — a regression test asserting a simulated read failure still yields exit 1 and the
   distinct stub (monkeypatched subprocess, so it runs anywhere). Gate: `python -m pytest <the new test> -q` → pass.
3. **Un-mute it** — the ranker's non-zero must reach a human. Propagating the exit code is **NOT sufficient** (no
   `set -e`, output to a logfile, no MAILTO); fire an alert on the channel `check_daily_refresh_freshness.py`
   already uses. Gate: `grep -n 'rank_task_subagents' scripts/kilo-benchmarks/daily_refresh.sh` → **Expected:** no
   bare `|| echo … non-fatal` swallow on that invocation.

*(A.0 is the SOLE source of these three gates. The sibling prep set that also carried them was archived
unexecuted on 2026-08-12 — see § Plan reconciliation at the foot of this file.)*

## Phase A — Freeze the contract (the golden-file regression oracle) · READ-ONLY (A.1–A.3) · runs in `/opt/fabrik` — ✅ EXECUTED **2026-08-12** (`dedbb5e0` + `6879959d`) — ⚠️ cite corrected pass 7: the previous `60dcfffc`/2026-08-15 was an unrelated enforcement fix, so the provenance of the phase claiming EXECUTED was unverifiable

**Deliverable:** a committed golden snapshot + a runnable diff harness that reproduces every live consumer output — the objective definition of "no functionality lost."

**Files (CREATE, in fabrik):**
- CREATE `scripts/kilo-benchmarks/tests/golden/` — the snapshot dir (gitignored large blobs excepted).
- CREATE `scripts/kilo-benchmarks/tests/capture_golden.py` — snapshots the consumer artifacts + records the exact hub-consumer DB queries.
- CREATE `scripts/kilo-benchmarks/tests/test_golden_parity.py` — behavior 2 harness (re-run producers → diff vs golden).

### Interfaces
**Produces (for Phase B/C):** ⚠️ **REWRITTEN pass 7 — the old contract promised a `{path: sha256}` manifest (the RETIRED byte-oracle; `grep -c sha256 golden/structure.json` → **0**) and `test_golden_parity.assert_parity(...)`, which **does not exist** (`grep -n 'def assert_parity'` → no match).** The real contract: `capture_golden.GOLDEN_DIR: Path`; `capture_golden.snapshot()` writes `golden/structure.json` (keys `artifacts` · `markers` · `db_queries` · `oracle_version`) + `golden/db_queries.json`; consumers compare via `capture_golden._shape_for` / `marker_shape` / `shape_drift` / `magnitudes_ok`, which is what `/opt/ai-model-catalog/engine/tests/test_parity_vs_fabrik_golden.py` does.

### Steps
**A.1 — Enumerate + snapshot the consumer manifest (behavior 2/3 oracle).**
1. Snapshot the engine output classes to `tests/golden/`, keyed by whole-file vs marker-block-body (#10 — get this split right or B.3 parity false-flags):
   - **Whole-file goldens** (`sha256` the whole file): the **6** selection docs matching `docs/reference/kilo/*_SELECTION.md` — verified: `CODING_SUBAGENT_SELECTION.md`, `TASK_SUBAGENT_SELECTION.md`, `IMAGE_GEN_SELECTION.md`, `STT_SELECTION.md`, `TRANSLATION_SELECTION.md`, `TTS_SELECTION.md` (⚠️ the narrower `*_SUBAGENT_SELECTION.md` glob matches only 2 and would silently drop the image-gen/stt/translation/tts docs from the oracle — exactly the producers most exposed to the B.2e refactor); `scripts/kilo_47_agents_final.json`; `models_browser.html`; and `KILO_MODEL_CAPABILITIES.md` **with its injected `EMBEDDING_CATALOG` marker-section STRIPPED** — `generate_model_capabilities.py:20` writes the whole file as the **base** (zero EMBEDDING markers — grep-confirmed), then `embedding_export_markdown` injects `EMBEDDING_CATALOG` into the LIVE file; the decoupled engine emits only the base whole-file to `engine/out/`, so the whole-file golden must be that base (strip the block before hashing).
   - **Marker-block-body goldens** (extract *between* the markers only — the host is not engine-owned): the `.windsurf/rules/ai/*.md` `OPENROUTER_ROUTES`+`GATEWAY_COUNTS` bodies; `EMBEDDING_ROSTER` (host `KILO_AGENT_SELECTION_GUIDE.md`), `EMBEDDING_CATALOG` (host `KILO_MODEL_CAPABILITIES.md`), `EMBEDDING_WINNERS` (host core `65-rag-search.md`) — 1:1 marker→host per `embedding_export_markdown.py:283-315`; and `ROSTER` (host `KILO_AGENT_SELECTION_GUIDE.md`, `generate_selection_guide_roster.py:21`).
   - **Do NOT** snapshot `docs/CAPABILITIES.md`/`capabilities.json`/`llms.txt` — they are `generate_capability_index.py` outputs (retained fabrik consumer, not the engine).
2. Record the exact DB queries the live hub consumers run (from spec §2 grounding): `rank_task_subagents.py:335` (`SELECT id,quality_tier FROM agents…`), the coding-fallback read, `update_gateway_counts.py` counts. Store as `tests/golden/db_queries.json`.
3. Gate — ⚠️ **REWRITTEN 2026-08-15 (A-B1): the original gate opened `golden/manifest.json`, a file nothing
   has ever written.** The real oracle is `structure.json` (`capture_golden.py:50` — `MANIFEST = GOLDEN_DIR /
   "structure.json"`), whose top-level keys are `artifacts`/`markers`/`db_queries`/`oracle_version`, so the old
   `len(m)>=12` + `'blocks/' in k` assertions were keyed to a shape that does not exist and the gate could
   only ever raise `FileNotFoundError`. Gate on the artifact + marker INVENTORY inside `structure.json`:
   `python scripts/kilo-benchmarks/tests/capture_golden.py --snapshot && python -c "import json; s=json.load(open('scripts/kilo-benchmarks/tests/golden/structure.json')); a,m=s['artifacts'],s['markers']; print(len(a),'artifacts',len(m),'markers'); assert len(a)>=13; assert len(m)>=18, 'markers missing'; assert any('KILO_MODEL_CAPABILITIES' in k for k in a)"`
   → **Expected:** **13 artifacts and 18 markers** — ⚠️ **floors tightened pass 7: the previous `>=12`/`>=6` passed with 12 of 18 markers gone (every OPENROUTER_ROUTES and GATEWAY_COUNTS pack block), reproducing the exact weakness the sentence below says the gate exists to remove.** Live inventory is 13/18; a floor at the live value fails the moment anything stops being produced (OPENROUTER_ROUTES + GATEWAY_COUNTS across their two
   different 7-pack sets — see C-B2 — plus EMBEDDING_ROSTER/CATALOG/WINNERS and ROSTER) including the
   capabilities base. A bare artifact count would pass while every marker was silently missing, which is the
   failure this gate exists for.

> ⚠️ **MECHANISM CHANGED 2026-08-12 (operator-directed, after two review rounds) — byte-identity
> is replaced by STRUCTURAL equivalence here; byte-equality moves to Phase C where it belongs.**
> A.2's original `sha256 == golden` and B.3's "byte-identical" gate both assume these artifacts
> are stable between runs. They are not: they are live aggregates over a flywheel that gains rows
> daily. Measured across two consecutive daily auto-commits (`8b1f077c` → `400ca5bb`), after
> date-normalisation, three artifacts still differed on real content — `n_total 274→296`,
> `glm-4.5-air 2.55/$0.0017/67 → 2.57/$0.0019/75`. A frozen-in-time byte-golden is therefore
> permanently stale within 24 h, and normalising hard enough to survive the churn blanks the very
> content the oracle protects (one attempt collapsed `gpt-4o-2024-05-13`, `-08-06` and `-11-20`
> into one string). **The oracle now freezes inventory + shape** (artifact presence, marker
> presence, markdown skeleton + table COLUMN contracts, JSON key schema) — stable across
> regeneration, and still red on the failures that matter: an artifact no longer produced, a
> marker no longer injected, a lost table column, a lost JSON field. Verified: 0 structural drift
> across the same regeneration that produced 3 byte-drifts. **Byte-equality is still required and
> still gated — in Phase C's same-moment parallel-run diff (old engine vs new engine, same DB,
> same instant), which is the only comparison that is meaningful for churning data.** B.3's
> "byte-identical" wording is superseded accordingly.

**A.2 — Prove the harness reproduces live output (red-then-green on a no-op).**
1. ⚠️ **REWRITTEN 2026-08-15 (A-B1): `test_selection_docs_match_current` was never written and its
   `sha256 == golden` premise is the retired byte-oracle.** The shipped tests are structural and already carry
   the red-on-diff proof this step demands — `test_structure_survives_a_real_daily_regeneration` (the churn
   the byte-oracle died on) and `test_gutted_tables_are_drift_even_with_perfect_structure` (an artifact that
   keeps its skeleton but loses its rows must still go RED). The step's real obligation is unchanged and
   still binding: **prove the oracle bites** — mutate a captured structure (drop a table column / a marker /
   a JSON key) and watch a test go RED, then revert.
2. Gate: `python -m pytest scripts/kilo-benchmarks/tests/test_golden_parity.py -v` → **Expected:** pass, with at least one sub-case demonstrating red-on-structural-drift.

**A.3 — Behavior Contract (this phase):** behaviors 2 + 3's oracle exists and bites. Author via pool: `fanout("code", units=[test_golden_parity spec], mode="write", owned_paths=["scripts/kilo-benchmarks/tests/test_golden_parity.py"], project="catalog-extraction")` → curate → `git apply` → re-run gate.

**A.closing (every phase ends here):**
1. `python scripts/final_gate.py --check --json | jq '.status'` → fix newly-red to `"success"` (baseline: pre-existing sibling reds — `commands/_fragments` structure, `docs/claudeck` links — are **not** this plan's).
2. `python scripts/enforcement/check_doc_sync.py` → resolve any WARN whose trigger file is in this phase's diff.
3. **`/fabrik-review`** on Phase A's changed surface (the 2 test files + capture script) — pool-default finders via `fanout("review", mode="read_only", project="catalog-extraction")` + 1 native `fabrik-reviewer` (Opus) → refute → prove-before-fix → iterate to a coverage-adjudicated no-op.
4. `CHANGELOG.md` entry (`### Added — catalog-extraction golden-file harness`); commit (explicit paths + `Agent-Role: orchestrator`, `Agent-Phase: A`) staging the plan file with `Status: CONVERGED → IN-PROGRESS` *(the flip applies once this plan's own review loop lands CONVERGED; the header currently reads HARDENED)* + `Phase A ✅ EXECUTED <date> (<commit>)`.

---

## Phase B — Copy the engine into `/opt/ai-model-catalog/engine/` · fabrik UNTOUCHED · runs in `/opt/ai-model-catalog` — ✅ EXECUTED 2026-08-15 (B.1 `9bdacfc` → B.closing `fa76d32`)

> **B.3 parity: GREEN** — 17 producers run clean under `OUTPUT_ROOT`, 31 artifacts incl. **18 marker
> blocks matching the golden's 18 exactly**; 32 assertions pass and the oracle was **proven to bite**
> on three mutations (artifact not produced · marker not emitted · artifact husked to a heading),
> green again on restore. **B.4a flywheel: GREEN** — `state=ok`, **72 rows**, from the relocated repo.
> **B.5 docs:** SERVICES + OPERATIONS carry the engine. Gate: **43 passed / 3 failed**, all three
> baseline-attributed and none naming `engine/` (Project Structure went GREEN vs the 9bdacfc
> baseline). ⚠️ `Fabrik-Synced Files` is **sync LAG, not a defect**: the project holds its July
> scaffold copies while fabrik HEAD moved to August via its own daily auto-commit (`2bc30c90`) —
> hand-editing a project's synced copy is a HARD STOP; the next governance-sync resolves it.

**Deliverable:** the engine runs standalone in `ai-model-catalog`, producing **structurally equivalent** outputs vs the Phase-A golden (byte-identity retired — see Behavior 2); fabrik's own engine still runs (parallel-safe).

**Files (CREATE, in ai-model-catalog):**
- CREATE `engine/` ← copy of `/opt/fabrik/scripts/kilo-benchmarks/**` (**101** scripts as of 2026-08-12 — was 98 when this plan froze; the +3 are `build_lcb_difficulty_manifest.py`, `dispatcher_bench.py`, `microbench_vision_describe.py` — + **55** in-tree tests (was 50 when this plan froze — same drift as the script count) + config YAMLs + `kilo_agents.db` + `models_browser_template.html` + vendored `libs/`, `alerting/`, `web_scrape/`, `direct_vendor_parsers/`, `specialty_clients/`, `translation_bench/`, **and the four dirs the un-excluded `rsync -a` also sweeps — `vendor/claude_evaluator/`, `tools/`, `migrations/` (2 SQL schema files), `corpora/` (~472K, used by `mine_docs_corpus.py`/`research_grader.py`)** — all genuinely engine-owned, listed here so the Files inventory matches what the command actually moves) **PLUS the 14 repo-root engine test files `/opt/fabrik/tests/kilo_benchmarks/**` → `engine/tests/`** (they `importlib`-load engine scripts, e.g. `test_llm_selector.py:29`, so they move with the code they test — **67** engine test files total (55 in-tree + 14 repo-root − 2 rule-6 tests; the plan's 64 predates both drifts); Phase E `git rm`s them from fabrik). **Exclude:** `process.py`, `process_v2.py` (throwaway — spec §3a); **the rule-6 fabrik-consumer-only TESTS `tests/test_commit_trailer_guard.py` (imports fabrik's `check_commit_trailers`) and `tests/test_docs_grader.py` (imports fabrik's `doc_reconcile`) — ADDED 2026-08-15 after both failed collection in the new repo:** the original exclude list covered the three rule-6 *modules* but not the *tests* that exercise fabrik-only code, so they arrive importing modules that do not exist here, the `.lcb-venv/`/`.lcb-src/` vendored trees (rebuilt by `setup_lcb_grader.sh`), **and the 3 rule-6 fabrik-consumer-only modules `classify_ticket.py`/`db_models.py`/`kilo_telemetry.py` (N5)** — no engine script imports them (verified: the only in-engine matches are their own docstrings; `export_traycer_registry.py:118` is a string-literal metadata field, not an import), so copying them would leave dead duplicates in two repos and violate Global Constraints' "**No shared file between the moved engine and fabrik**". They stay in fabrik for `kilo_auto_route.py`.
- CREATE `engine/pyproject.toml` — the **subsystem dependency manifest** the engine never had (spec §2 gap): pin `httpx`, `beautifulsoup4`, `pyyaml`, `psycopg[binary]`, `sacrebleu`, etc. from the real imports. **It must carry a `[build-system]` block + explicit packaging config** (e.g. `setuptools` + `[tool.setuptools] py-modules = []` / `packages = []` for this flat, script-heavy tree) — otherwise B.3's `pip install -e .` fails on a directory that was never a package. If editable-install proves fiddly for the flat layout, the fallback is `pip install -r requirements.txt` + `PYTHONPATH=engine` (state which one the executor used).
- CREATE `/opt/ai-model-catalog/engine/daily_refresh.sh` ← relocated, with the **six** fabrik tentacles severed (four known at drafting + `doc_reconcile` + `fabrik.drivers`) (see B.2).
- MODIFY `compose.yaml` — wire the engine as a scheduled-worker service (reuse the existing `worker` at `compose.yaml:83` or add `engine-cron`), `deploy.resources.limits.memory` set.

### Interfaces
**Consumes:** the Phase-A golden set (`/opt/fabrik/scripts/kilo-benchmarks/tests/golden/` — read cross-repo for the parity assert).
**Produces (for Phase C):** `/opt/ai-model-catalog/engine/daily_refresh.sh` (green standalone); the produced-artifact bundle at `engine/out/` in **fabrik-relative mirrored layout** — `engine/out/docs/reference/kilo/*.md` (selection docs), `engine/out/scripts/kilo_47_agents_final.json`, `engine/out/models_browser.html` (file producers) — plus `engine/out/blocks/<host>.<MARKER>.txt` (injector-block content — OPENROUTER_ROUTES · GATEWAY_COUNTS · EMBEDDING_ROSTER/CATALOG/WINNERS · ROSTER, per B.2e; EMBEDDING_* inject into `KILO_AGENT_SELECTION_GUIDE.md` + `KILO_MODEL_CAPABILITIES.md` + core `65-rag-search.md`, ROSTER into `KILO_AGENT_SELECTION_GUIDE.md`) — plus `engine/out/kilo_agents.db` (the raw DB delivered for fabrik's retained `generate_kilo_agents` consumer — see F1/Phase C) — same relative names/content as the Phase-A golden. **Not** `CAPABILITIES.md`/`capabilities.json`/`llms.txt` (retained-fabrik-consumer outputs, not the engine).

### Steps

⚠️⚠️ **PHASE B BLOCKERS — pass-5 grounding, 2026-08-15. ⏱️ HISTORICAL SNAPSHOT, taken at `6935ce9`, when B.2f/B.3/B.4a/B.5 had not started.** They have since ALL shipped (see the ✅ block at this phase's head, and the FIXED notes below): B.3 parity green + mutation-proven, B.4a `state=ok`/72 rows, B.5 docs landed, Phase B `✅ EXECUTED`. **Every finding below is either marked FIXED or still open — read the markers, not this heading.** It is kept because the findings are the record of what was wrong, not a claim about today.

**B-B1 — ⛔ CRITICAL, HARD-STOP CLASS: the two `rank_*` producers write to `/opt/docs/`, OUTSIDE BOTH REPOS.**
`/opt/ai-model-catalog/engine/rank_task_subagents.py:148-154` builds `OUTPUT_PATH` from `Path(__file__).resolve().parent.parent.parent`,
which from `/opt/ai-model-catalog/engine/` resolves to **`/opt`** — verified live:
`/opt/docs/reference/kilo/TASK_SUBAGENT_SELECTION.md`. Same at `:309-315` (`CODING_FALLBACK_PATH`) and
`rank_coding_subagents.py:53`. `_atomic_write` (`:1363`) does `path.parent.mkdir(parents=True, exist_ok=True)`,
so **the first run creates `/opt/docs/`** — a write outside any project tree, which CLAUDE.md lists as a HARD
STOP. It has not fired only because these producers have not been run since the move (`ls -d /opt/docs` → No
such file). **Why B.2e missed it:** the step says "repoint the `FABRIK_ROOT`/`FABRIK_DIR` anchor to
`OUTPUT_ROOT`", and `rank_*` has **no named anchor** — `grep -c 'OUTPUT_ROOT\|FABRIK_ROOT\|FABRIK_DIR'
rank_task_subagents.py` → **0**. It inlines the walk. A grep-for-the-anchor instruction is structurally blind to
an inlined `parent.parent.parent`, so commit `13b7ec1`'s "7 producers no longer derive a root by walking out of
`engine/`" is false for exactly the two that matter most. Secondary: `CODING_FALLBACK_PATH` now reads a
nonexistent file, so the blend at `:1320` silently degrades to `n_total=0`. **Fix `rank_task_subagents.py` and
`rank_coding_subagents.py` to honour `OUTPUT_ROOT` before any producer is run.**

> ✅ **B-B1 FIXED 2026-08-15 (`ai-model-catalog` `e858a64`) — and it was FOUR TIMES WIDER than reported, and
> it had ALREADY FIRED.** A class sweep for the idiom (not the two named instances) found **20** modules in
> five shapes: selection-doc producers (3 hops → `/opt`), Traycer JSON exports (2 hops → the scaffold repo
> root), `.env` loaders (B-B7), "repo root" haystack readers (`docs_grader`/`mine_docs_corpus`/`structural_grader`
> — under `engine/` these would have made the grader scan every project on the box as one codebase), and one
> vendored fixture (correctly exempted). **Damage already done, found by looking rather than by any gate:** the
> scaffold's own `.windsurf/rules/ai/*.md` carried injected `GATEWAY_COUNTS` blocks stamped *"auto-managed by
> `update_gateway_counts.py`"*, and `docs/reference/kilo/` carried **nine** files stamped *"Generator:
> `rank_coding_subagents.py`"* — the precise clobber B.2e exists to prevent, sitting in the tree since 06:04.
> Both surfaces restored to HEAD; the stray `kilo_embeddings_final.json` at the scaffold root removed.
> `/opt/docs/` was never created **only** because the producers had not been run since the move.
> **The gate now exists:** `/opt/ai-model-catalog/engine/tests/test_output_root_isolation.py` — the file B.2 gate 4 requires and
> that had never been written — AST-walks every module, symbolically counts how many levels each path
> expression walks up from `__file__` **through module-level names** (so `SCRIPT_DIR = Path(__file__).parent`
> then `SCRIPT_DIR.parent.parent` is caught as 3), and fails anything above one hop. Committed **RED at 20
> modules, green at 0**, with an anti-vacuity guard and a discriminator proving it stays quiet on the correct
> `OUTPUT_ROOT` idiom and bites on all four real ones. ⚠️ **`test_no_fabrik_paths.py` passed throughout** —
> every one of these is a *computed* path, so string-matching is structurally blind to the entire class.
> Regression-checked against a baseline worktree at the prior commit: **16 pre-existing failures before, the
> same 16 after, zero new** (1264 passed, +145). One self-inflicted defect en route, recorded because it is
> the reusable lesson: redirecting into `engine/out/` broke 13 embedding tests with `FileNotFoundError`,
> because the *old* parent always existed and the new one must be created — `mkdir(parents=True)` added at the
> three write sites.

**B-B2 — `/opt/ai-model-catalog/engine/daily_refresh.sh` is entirely non-functional; B.2f is not done.** `:55` repoints
`FABRIK_ROOT` to the engine root but the **sub-paths were not repointed with it**: `:58` still sets
`KB="$FABRIK_ROOT/scripts/kilo-benchmarks"`, a directory that does not exist under `engine/`, and there are
**65** `$KB/` references. Every `_step` invocation is a dead path. `:56` still sets
`LOG_FILE=".../cache/update.log"` and `:610` still `>> "$LOG_FILE"`, so **B.2 gate 3 FAILS today** (its grep
returns 6 matches). B.2e(ii)'s `--output` flags were never added at `:306`/`:490`, so
`export_traycer_registry` writes to the scaffold repo root and `export_models_browser` has already written a
3.9 MB `engine/models_browser.html` outside `engine/out/`. Five steps still invoke **fabrik-only** scripts
(`gather_envs`, `classify_services`, `generate_capability_index`, `generate_kilo_agents`,
`sync_enforcement_to_projects`) that do not exist in the engine at all. Files line 146 and the B.3 Produces
line both assert a "relocated / green standalone" `daily_refresh.sh` — **false against the live tree.**

**B-B3 — no `pyproject.toml`, no `requirements.txt`, no `.venv`: FIVE gates in this phase are unrunnable.**
All three absent (verified). B.3 step 1's `pip install -e .` fails **and its documented fallback**
(`pip install -r requirements.txt`) has no file either. Unrunnable as written: B.1 step 2a, B.2 gate 4, B.3
steps 1 and 4, B.4a. Files line 145 asserts the `[build-system]` block — it does not exist.

**B-B4 — B.1 step 1 contains TWO MUTUALLY EXCLUSIVE GATES, and the second one destroys the data the first
one exists to save.** The step first requires `test -s engine/cache/speed_overrides.json` (pass), then
requires `[ -z "$(ls -A engine/cache)" ]` — "dir exists **and is empty**". A directory holding
`speed_overrides.json` can never be empty; run verbatim today the second gate **FAILS** (`ls -A cache/` →
`blocked_writes`, `speed_overrides.json`, `vendor_failures.json`). An executor who takes the empty-dir gate
literally deletes the hand-maintained, previously-git-ignored `speed_overrides.json` — **the exact
silent-data-loss the sentence two lines above it exists to prevent.** Drop the empty-dir assertion; assert
instead that `cache/` contains *only* `speed_overrides.json` after the carve-out.

**B-B5 — the `, id` tiebreak B.2g(iii) mandates "FIRST" is still absent from every flagship producer.**
`rank_task_subagents.py:549/:653/:974` are bare `ORDER BY … DESC`; `:741`, `export_traycer_registry.py:83`,
`export_models_browser.py:79/:88/:111/:168` are non-total orders. Only `generate_model_capabilities.py:64` and
`embedding_export_markdown.py:277` carry it. B.3 will hit precisely the false-diff hazard B.2g predicts. (The
`NULLS LAST` half **is** done — `catalog_store.py:165`, cite exact.)

**B-B6 — three different test counts, and all three are wrong.** Line 37 says 64, B.1 gate 3 says 64, lines
144/157/184 say 67; live `find engine/tests -name 'test_*.py' | wc -l` → **68** (67 ported + the
`test_no_fabrik_paths.py` B.2 creates). By the time B.3 runs, B.2 gate 4 and B.3 step 3 add two more → **70**.
B.3 gate 4 freezes "67" in the same sentence that warns "assert the COLLECTED COUNT, never a frozen literal".
Same class: B.1 gate 3's "**96 scripts**" is live **98** (96 copied + `blocks_out.py` + `catalog_store.py`).
**Every count in this phase must be computed at run time, never asserted.**

**B-B7 — `engine/.env` does not exist and one loader escapes both repos.** B.2(b) is undone:
`fetch_direct_vendor_prices.py:73-74` and `check_daily_refresh_freshness.py:44` load
`/opt/ai-model-catalog/.env` (the scaffold's, not the engine's), and `microbench_terminal.py:876` resolves
`SCRIPT_DIR.parent.parent/".env"` = **`/opt/.env`** — the same escape class as B-B1. None contains the literal
`/opt/fabrik`, so `test_no_fabrik_paths.py` is structurally blind to all three.

**B-B8 — 200 stale `.pyc` files carrying `/opt/fabrik` `co_filename` rode in on B.1's `rsync -a`.** No
`--exclude __pycache__`; `rsync -a` preserves mtimes so the cached bytecode stays **valid** and is used, making
tracebacks in the new repo point at the old one. `test_no_fabrik_paths.py:24` lists `__pycache__` in
`SKIP_DIRS`, so the invariant test cannot see it. Not committed (gitignored) — on-disk residue only, but
residue inside the "zero residue" boundary. Add the exclude and purge.

**B-B9 — `CATALOG_DSN` is read but never provisioned, so B.2g's oracle would silently test SQLite.** It
appears only as `os.environ.get` reads in `catalog_store.py`; no `.env`, no compose entry, no export in
`daily_refresh.sh`. Unset ⇒ silent SQLite fallback — so B.3 "run the producers against the POSTGRES store"
(line 177) proves nothing unless the DSN is provisioned first. PLAUSIBLE→CONFIRMED by absence; provision it
explicitly and assert the store in the gate.

**B-B10 — `grep -c … → Expected: 0` inverts its own exit status.** B.3 step 2 and B.2 gate 3 both expect a
count of `0`, but `grep -c` **exits 1** when it prints `0`. Under `set -e` or any exit-status runner, the
PASSING case is recorded as a failure. Use `[ "$(grep -c …)" = 0 ]`.

**B-B11 — B.5 is not done.** `docs/SERVICES.md` in `ai-model-catalog` has **zero** engine mentions (its 3
`OPERATIONS.md` hits are scaffold placeholder prose — "needs engineering time", "bite new engineers"); both
files are untouched since scaffold. `CHANGELOG.md:13` carries a B.2g entry only — nothing for B.1/B.2/B.2e.
✅ The spec claim IS confirmed: `specs/services/ai-model-catalog.yaml:11` `needs_database: true`.

> ✅ **B-B2, B-B3, B-B5 FIXED 2026-08-15** (`ai-model-catalog` `a992256`, `b385570`, `cb1214c`).
> **B-B3** — `engine/pyproject.toml` written from AST-derived real imports (not the plan's illustrative
> list), `[tool.setuptools] py-modules = []` for the flat ~100-module tree, LCB/EvalPlus as an optional
> `[lcb]` extra so torch/vllm never enter a base install; `.venv` created and `pip install -e .[dev]`
> **succeeds** — the five gates this blocked now run, and B.1 step 2a reports **0 collection errors**
> (1291 tests) for the first time, after guarding the two `evalplus` tests so an absent OPTIONAL dep
> skips instead of erroring. ⚠️ **Deriving the manifest surfaced TWO MORE fabrik tentacles neither
> grounder found — the plan says four, it is six:** (#5) `docs_grader.py` + `mine_docs_corpus.py`
> `import doc_reconcile`, which resolved in fabrik only because they put `SCRIPT_DIR.parent`
> (= `scripts/`) on `sys.path`; **both failed at import here**, silently, because B.1 excluded the one
> test that would have caught it — fixed by vendoring the **three** helpers they use (AST-verified
> identical to fabrik's, constants included) rather than the 489-line file, which imports
> `_doc_registry`/`check_doc_stubs`/`libs` and would drag a fabrik chain in; (#6)
> `tests/test_rank_task_subagents.py` imports `fabrik.drivers.postgres` — **the SYSTEM interpreter was
> masking it** (fabrik is pip-installed there), and only the fresh `.venv` exposed it; skipped, not
> vendored, since that privilege boundary is on the shared flywheel DB which does not move (D5).
> *Sub-lesson worth keeping:* the first guard used `importorskip("fabrik")` and **passed alone but
> failed in-suite** — something earlier puts that name on `sys.path`, so the parent import succeeded
> and the next line still died on `fabrik.drivers`. Guard the submodule you import, never its parent.
> **B-B2** — `KB` now means the engine root (it meant `<repo>/scripts/kilo-benchmarks`, so all 65 `$KB/`
> references, i.e. **every** `_step`, were dead paths). B.2f done: the `cache/update.log` write is gone
> and with it the whole writability ladder **and** the block-scope redirect hazard it guarded — there is
> no `} >> "$LOG_FILE"` left that can fail and skip the body. **C-B1 fixed here** (it is this file):
> lockfile namespaced to `/tmp/.amc_engine_daily_*`, prune loop and docs matched. B.2e(ii) done: both
> `--output`-driven producers now get an explicit `--output`. Five fabrik CONSUMER steps removed (they
> rode the shared orchestrator into the copy and referenced a `scripts/` dir that does not exist here;
> Phase D keeps them in fabrik) — 55 `_step` invocations → **50**. Both `load_dotenv` calls repointed to
> `engine/.env` (B.2b) and `engine/.env.example` written from the **38** env vars the engine really
> reads. ⚠️ **`engine/.env` itself is deliberately NOT created:** the keys already live in fabrik's
> `.env`, and copying them makes a second copy on the box to rotate and to leak — an operator decision,
> recorded rather than taken.
> **B-B5** — eleven queries across six producers got a tiebreak on a column that is actually unique in
> that query's shape (`m.model_id` where the metrics tables have no `id`; `a.id`/`r.id`/`agent_id`/
> `model_id` elsewhere), so B.3 cannot false-diff on a LIMIT-boundary tie. Two of them
> (`microbench_judged`, `microbench_review`) were in nobody's list and were caught by sweeping the
> idiom; both feed `TASK_SUBAGENT_SELECTION.md`. The only bare `ORDER BY` left is `ORDER BY id`, already
> total. All three fixes regression-checked against a baseline worktree: **16 pre-existing failures
> before, the same 16 after, zero new** (1265 passed).

> 🔍 **PHASE-B ADVERSARIAL REVIEW (native Opus, 2026-08-15) — 17 findings. FIXED: 11. OPEN: 6.**
>
> **The meta-finding: the isolation invariant I shipped was VACUOUS** — 0 flags while ≥6 real escapes
> lived, with four independent defects (visited only `ast.Assign`; `str()` zeroed the counter, so the
> live `str(Path(__file__).parents[2])` was missed while its own discriminator asserted it caught a
> form present NOWHERE; `.parents[n]` off by one, sitting exactly on the `MAX_HOPS=1` boundary so
> `parents[1]` — the scaffold root — passed; and the env carve-out ran before the name table was
> built, poisoning it). Rebuilt with two passes, NET depth (`/` descends), a PER-FILE budget (a flat
> one flagged 82 innocent subdirectory files — a detector that cries wolf on 82 files gets turned
> off), and a subtree-scoped environ exemption. It then found **10 real escapes** and independently
> reproduced four of the reviewer's confirmed findings. All fixed. ⚠️ `tests/` had been in
> `SKIP_DIRS`, which hid the worst one: **`tests/capture_golden.py` is PRODUCTION code** (cron runs
> it) and resolved **`/opt`**, so `--verify` reported all 13 artifacts + 18 markers as NO LONGER
> PRODUCED **every night** and fired a critical alert — a permanently-red alarm is a disabled alarm,
> and it is the only runtime detector that a producer stopped producing.
>
> Also fixed: `docs/traycer/kilo_selected_agents.md` was produced by **neither** of its two producers,
> forever, silently (one crashed on a missing parent dir — which also skipped `export_local_models()`
> in the same branch — and the other fails soft on an absent host) **and the parity oracle listed
> exactly that file in `_NEEDS_NETWORK` and skipped it.** `_NEEDS_NETWORK` is now empty: 33 assertions,
> 13 artifacts, zero skips. Two more producers had lost their `mkdir`. `catalog_store` never translated
> `INSERT OR REPLACE ... VALUES` **without a column list** (SQLite allows it; two live writers use it),
> so with `CATALOG_DSN` set every judged-microbench and coding-direct metrics write hit a Postgres
> syntax error — and those tables feed `TASK_SUBAGENT_SELECTION.md`. `microbench_review` handed
> **`/opt`** to the subagent pool as its workspace root. Four `.env` loads resolved to `/opt/.env`, so
> the Telegram token never loaded and the staleness alarm was silent.
>
> ⚠️ **O1 ✅ FIXED (`eff0695`) and O4 ✅ FIXED (`eff0695`) — struck below. O2/O3/O5/O6 re-verified STILL LIVE in pass 7. Also unrecorded in any status block: amc `9f59990` and `98c78ea`.**
> ~~**(O1)**~~ ✅ **FIXED** — `autocommit_pipeline_outputs.sh` stages **nothing** — its path list is old-repo-relative
> (`.windsurf/`, `docs/`, `scripts/kilo-benchmarks/`, none of which exist under `engine/`) and the
> genuinely-regenerated files aren't in the list at all; worse, the 0-matched case `exit 0`s BEFORE
> the "a pipeline output was renamed" warning, so losing 15 of 16 paths warns and losing 16 of 16 is
> silent. **(O2)** three read-modify-write producers (`role_mapper:335`, `kilo_agents_db:1093/:1256`)
> now fail soft into permanent no-ops because their hosts never exist under `OUTPUT_ROOT`; none is in
> the golden, so no oracle notices. **(O3)** `_fix_order_by` mangles `ORDER BY x;`, silently swallows
> the clause into a trailing `-- comment` (reverting Postgres to its own NULL ordering — the exact
> inversion it exists to prevent), and is not string-literal aware; latent today, no live query hits
> it. ~~**(O4)**~~ ✅ **FIXED** — `test_no_fabrik_paths` could not see `"/opt/" + "fabrik"`, which is how
> `deliver_to_fabrik.py:47` writes the one genuine cross-repo default — the test that exists to notice
> cross-repo references is blind to the only real one. **(O5)** `_output_root()` binds at IMPORT time
> in three producers despite a docstring promising call-time. **(O6)** `daily_refresh.sh` has a dead
> `if false` branch and writes `$KB/cache/...` at `:337` before the only `mkdir -p` at `:545` —
> surviving only because one git-tracked file keeps the dir alive.

**Verified-good in Phase B (recorded so the next pass does not re-litigate):** the `speed_overrides.json`
carve-out is fully done and now git-**tracked** (`engine/.gitignore:15`); `_query_rows` + the
`sudo -n -u postgres psql` shellout are intact, so B.2c's DO-NOT-REWRITE held; `test_no_fabrik_paths.py` passes
255 cases and is **non-vacuous** (anti-vacuity guard `:111-115`, red-side discriminator `:118-127`); every one
of B.2e's seven producer line-cites is exact; the B.2g transitive-reader finding (i) is real and was caught;
the size claims hold (8.7G source / 8.3G `.lcb-hf-cache` exact; post-exclude 33M vs the plan's 30M — drifted,
gate still holds). ⚠️ One sub-justification **REFUTED**: `scrape_coding_benchmarks.py:357-358` **warns and
degrades** on a missing `cache/`, it does not crash — the pre-create conclusion may hold for the other 12
cache-touching scripts, but the named evidence does not support it.

**B.1 — Copy + prune (TWO copies — the engine tree AND the repo-root engine tests).**
1. `rsync -a --exclude process.py --exclude process_v2.py --exclude '.lcb-*' --exclude '.microbench_cache' --exclude 'cache/' --exclude 'backups/' --exclude '.tmp' --exclude classify_ticket.py --exclude db_models.py --exclude kilo_telemetry.py /opt/fabrik/scripts/kilo-benchmarks/ /opt/ai-model-catalog/engine/`. The last three excludes are the **rule-6 fabrik-consumer-only** modules (N5 — no engine script imports them; copying them creates the dual-editable "shared file" Global Constraints forbid). **The state excludes are load-bearing (R10-4):** the source tree is **8.7G as of 2026-08-12** (422M when this plan was written; `.lcb-hf-cache` alone is now 8.3G — the existing `--exclude '.lcb-*'` already catches it, and the post-exclude tree measures **30M** (25M when written; re-measured 2026-08-15), well inside the gate) — `.lcb-venv` 297M, `backups/` 42M, `.microbench_cache` 27M, `cache/` 26M — all regenerable runtime state that must NOT land in a fresh git repo (`cache/` also holds the very `update.log` B.2f removes the write of). Add them to `engine/.gitignore` too, so a later run can't re-commit them. **⚠️ `cache/` is NOT purely regenerable — carve out the curated file first (N2, silent-data-loss):** `scripts/kilo-benchmarks/cache/speed_overrides.json` is **hand-maintained**, non-regenerable data (14 entries; its `_README` reads *"Manual speed data for models artificialanalysis.ai does not track… Each entry must explain the source"*) and it is **git-ignored** (`.gitignore:163`), so excluding `cache/` wholesale destroys the only copy. Copy it explicitly — `rsync -a /opt/fabrik/scripts/kilo-benchmarks/cache/speed_overrides.json /opt/ai-model-catalog/engine/cache/` — and **un-ignore it in `engine/.gitignore`** (`!cache/speed_overrides.json`) so it is version-controlled from now on rather than surviving only on one disk. Gate: `test -s /opt/ai-model-catalog/engine/cache/speed_overrides.json && python -c "import json;assert len(json.load(open('/opt/ai-model-catalog/engine/cache/speed_overrides.json')))>=14"` → **Expected:** pass (without it, `scrape_artificial_analysis.py` silently exports degraded speed data for the models AA doesn't track). **Then exclude the remaining CONTENTS and re-create the empty dirs — `mkdir -p /opt/ai-model-catalog/engine/{cache,backups}`:** `cache/` is read/written at runtime by ≥5 engine scripts and at least one (`scrape_coding_benchmarks.py`) **never `mkdir`s it** (verified: 0 mkdir calls), so a missing dir is a first-run crash, not a clean regeneration. Gate — ⚠️ **REWRITTEN (B-B4): the old form demanded the dir be EMPTY, which contradicts the carve-out two sentences above and, run verbatim, deletes the hand-maintained `speed_overrides.json` it exists to save.** Assert the dir exists and contains ONLY the curated file: `test -d …/engine/cache && [ "$(ls -A …/engine/cache)" = "speed_overrides.json" ]` → **Expected:** exit 0.
2. **`rsync -a /opt/fabrik/tests/kilo_benchmarks/ /opt/ai-model-catalog/engine/tests/` (R10-1 — the SEPARATE top-level dir).** B.1's first rsync is scoped to `scripts/kilo-benchmarks/` and **structurally cannot reach** `/opt/fabrik/tests/kilo_benchmarks/`; without this second copy the 14 repo-root engine tests (+ their `fixtures/` of cached HTML two tests require) never arrive, and B.3's 64-file gate fails at 50.
2a. **Rewrite those 14 tests' path preamble — they ALL break on arrival otherwise (N1, CONFIRMED).** Every one of the 14 computes `REPO_ROOT = Path(__file__).resolve().parents[2]` then `SCRIPT_DIR = REPO_ROOT/"scripts"/"kilo-benchmarks"` (e.g. `test_llm_selector.py:22-23`), with **zero** env overrides (verified: 0 of 14 use `getenv`/`environ`). At `engine/tests/`, `parents[2]` = `/opt/ai-model-catalog`, so `SCRIPT_DIR` points at a path that does not exist (the engine is FLAT at `engine/*.py`, not `engine/scripts/kilo-benchmarks/*.py`) → all 14 fail at collection with `FileNotFoundError`/`_spec is None`. Fix: rewrite the preamble to `SCRIPT_DIR = Path(__file__).resolve().parents[1]` (= `engine/`). ⚠️ **CORRECTED 2026-08-15 — `REPO_ROOT` is NOT a 'now-meaningless hop', and dropping it blindly breaks three files (observed live).** 17 further references build paths from it: `test_fetch_direct_vendor_prices.py` uses `REPO_ROOT/"scripts"/"kilo-benchmarks"` 16 times for `sys.path.insert` plus a `kilo_agents.db` path (all → `SCRIPT_DIR`), and `test_embedding_export_markdown.py:25` builds `DOCS_DIR = REPO_ROOT/"docs"/"reference"/"kilo"`, which is an OUTPUT path and must go through the B.2e `OUTPUT_ROOT` mirror. Grep `REPO_ROOT` in the 14 files and repoint each by MEANING before deleting the binding. ⚠️ **B.2's `test_no_fabrik_paths.py` cannot catch this** — it greps the literal string `"/opt/fabrik"`, which these files never contain; the break is a *computed* relative path (the exact dynamic-path class E.1 warns a grep misses). Gate: `cd /opt/ai-model-catalog/engine && .venv/bin/python -m pytest tests/ --collect-only -q` → **Expected:** **0 collection errors**; the file count is COMPUTED in the same run, never asserted as a literal (B-B6 — six different literals have appeared for this one number)
3. Gate: `test -f /opt/ai-model-catalog/engine/kilo_agents.db && ls /opt/ai-model-catalog/engine/*.py | wc -l` → **Expected:** DB present, **the count computed in the same run** (the literal was 96; live is 100 after B.2e/B.2g added `blocks_out.py` and `catalog_store.py` — a frozen literal here fails for the wrong reason); `ls /opt/ai-model-catalog/engine/{classify_ticket,db_models,kilo_telemetry}.py 2>&1 | grep -c "No such file"` → **Expected: 3** (none copied); `find /opt/ai-model-catalog/engine/tests -name 'test_*.py' | wc -l` → **Expected: the count computed in the same run, never a literal** (see B-B6 — six different literals have appeared for this); `du -sh /opt/ai-model-catalog/engine` → **Expected: well under 100M** (no `.lcb-venv`/`backups`/`cache`/`.microbench_cache`).

**B.2 — Sever the fabrik tentacles (**SIX**, not four — `doc_reconcile` and `fabrik.drivers` were found in pass 6; see the B-B3 fix note) (TDD the path-decoupling first — highest risk).**
1. Write `/opt/ai-model-catalog/engine/tests/test_no_fabrik_paths.py::test_no_hardcoded_opt_fabrik` — grep the engine tree, assert **zero** `"/opt/fabrik"` string literals remain (excluding comments referencing history) and no `import` reaches outside `engine/`. Run → **RED** (copies still carry `/opt/fabrik` anchors).
2. Fix: (a) replace `FABRIK_ROOT`/`/opt/fabrik` anchors with an `ENGINE_ROOT = Path(__file__).resolve().parent` / `REPO_ROOT` env; (b) repoint `load_dotenv` from `/opt/fabrik/.env` → `engine/.env` (a repo-local `.env`, gitignored); (c) **⚠️ SUPERSEDED BY D5 — DO NOT REWRITE THE FLYWHEEL READ IN THIS PLAN.** The rewrite described next existed solely to make a *container* work. Under WSL-only the engine runs on the same box as the database, so `sudo -n -u postgres psql` keeps working unchanged — and rewriting it would modify the one call the operator named as must-not-break, with a default-unset failure mode that publishes a stub selection doc fleet-wide. **Keep the existing call verbatim; add a preflight assert instead** (`sudo -n -u postgres psql -d fabrik_analytics -tAc "SELECT 1"` → `1`, plus a positive-proof NON-EMPTY row read; a failure is BLOCKING, never a skip). Retained below for the later VPS spec, which is where `FLYWHEEL_DSN` belongs — ~~an env var alone is NOT enough (G2, grounded):~~ the read is a **shellout**, `subprocess.run(["sudo","-u","postgres","psql",…])` (`rank_task_subagents.py:17` docstring, `:38` `import subprocess`, `:185-191`), and a container has **neither a local postgres socket nor `sudo`**. Rewrite the call to `psql "$FLYWHEEL_DSN" -A -F$'\t' -c …` (drop `sudo -u postgres`; keep the `-A -F` parsing contract at `:166-169`/`:218-219` intact) or swap to a `psycopg` client; default unset → the `:179` fail-open "error" state (Phase E provisions the real DSN); (d) the vendored `libs/subagents` is the engine's own copy — delete the `/opt/fabrik-lib` doc references; **(e) — the OUTPUT decoupling (CRITICAL — a naive `FABRIK_ROOT`→`ENGINE_ROOT` swap clobbers the scaffold's own rules).** The artifact producers derive their write path from `FABRIK_ROOT = SCRIPT_DIR.parent.parent` (`category_export_markdown.py:56`; `update_gateway_counts.py:42` → `RULES_DIR = FABRIK_ROOT/.windsurf/rules/ai` (was cited :40 — that line is `FABRIK_ROOT = SCRIPT_DIR.parent.parent`; re-grounded 2026-08-15)) — under `engine/` that resolves to `/opt/ai-model-catalog/` and would **overwrite the scaffold's own `.windsurf/rules/ai`**. Introduce an `OUTPUT_ROOT` env (default `ENGINE_ROOT/out`) and split producers by kind (classify by MECHANISM — grep each for a `write_text` of a whole file vs a `START_MARKER not in content … replace-between-markers`): **file producers** — the whole-file writers, split by how each derives its path (grep confirmed — they are NOT uniform): (i) **`FABRIK_ROOT`-derived** — `rank_*` (atomic `tmp.write_text`+`os.replace`, `rank_task_subagents.py:1363`) and `generate_model_capabilities` (`OUT_FILE = FABRIK_DIR/docs/reference/kilo/KILO_MODEL_CAPABILITIES.md`, `:20/:155`): repoint the `FABRIK_ROOT`/`FABRIK_DIR` anchor to `OUTPUT_ROOT` so they write `OUTPUT_ROOT/<fabrik-relative-path>`; (ii) **CLI-`--output`-driven** — `export_traycer_registry` (`DEFAULT_OUTPUT = SCRIPT_DIR.parent/kilo_47_agents_final.json`, `:52`; `--output`, `:133/:156`) and `export_models_browser` (`OUTPUT_PATH = SCRIPT_DIR/models_browser.html`, `:32`; `--output`, `:390`): they DON'T read `FABRIK_ROOT`, so an `OUTPUT_ROOT` env alone won't redirect them — `daily_refresh.sh` (and the parity runner) must invoke them with an explicit `--output OUTPUT_ROOT/<rel>` (grep `daily_refresh.sh` for their call sites and add the flag). Both classes land under `engine/out/<fabrik-relative-path>`; **injector producers** — the marker-replacers that edit an EXISTING host file (`category_export_markdown` OPENROUTER_ROUTES, `update_gateway_counts` GATEWAY_COUNTS, `embedding_export_markdown` EMBEDDING_ROSTER/CATALOG/WINNERS, `generate_selection_guide_roster` ROSTER — each does `if MARKER not in content: append else replace`, `pack_path.write_text(new_content)`) — are refactored to **emit the marker-block content** to `OUTPUT_ROOT/blocks/<host>.<MARKER>.txt` **plus a machine-readable `OUTPUT_ROOT/blocks/manifest.json`** — the block→host **interface** C consumes (the filename alone can't encode the host's *directory*): `[{"block":"KILO_AGENT_SELECTION_GUIDE.md.EMBEDDING_ROSTER.txt","host":"docs/reference/kilo/KILO_AGENT_SELECTION_GUIDE.md","start":"<!-- EMBEDDING_ROSTER:START -->","end":"<!-- EMBEDDING_ROSTER:END -->"}, …]`. Marker→host is **NOT 1:1 — CORRECTED 2026-08-15 during B.2e execution; the CITE re-corrected in pass 5.** It holds only for the three `EMBEDDING_*` markers the plan actually grounded. `OPENROUTER_ROUTES` and `GATEWAY_COUNTS` each target **7 hosts — but two DIFFERENT sevens** (C-B2). ⚠️ The mechanism cite was wrong: `PACK_TO_CATEGORY` does **not** exist in `category_export_markdown.py` at all (grep-verified, pass 5) — it is defined at `update_gateway_counts.py:260` and iterated at `:275`, and that file also owns `RULES_DIR = FABRIK_ROOT/.windsurf/rules/ai` (`:42`). `category_export_markdown` derives its hosts from `ai_category_configs.yaml` (`CONFIG_PATH:57`) instead, so **a path-grep enumerates its hosts as zero** — the two injectors do not share a host-discovery mechanism, and any consumer written to one of them breaks on the other. The flat-list manifest absorbs this (the filename keys on host basename), but **any Phase C code written to a 1:1 assumption will break** — `deliver_to_fabrik.py` must group by host, not look up by marker. Original (wrong) claim: strictly 1:1 (verified `embedding_export_markdown.py:283` ROSTER→guide, `:284` CATALOG→capabilities, `:315` WINNERS→core `65-rag-search.md`, **guarded by `if RAG_SEARCH_PATH.exists():` at `:285`** — ⚠️ **that guard CANNOT be preserved literally in the engine (found 2026-08-15):** under `OUTPUT_ROOT` the host path never exists, so keeping the line verbatim silently stops emitting `EMBEDDING_WINNERS` forever. The engine emits it unconditionally and marks the row `"optional": true` in the manifest; `deliver_to_fabrik.py` mirrors the guard (skip-with-a-logged-warning if the host is absent, never crash), and the golden/parity treat that block as conditional), so the manifest is a flat list; `deliver_to_fabrik.py` injects by reading it, never by re-deriving paths from prose. ⚠️ **Two manifest keys the plan omitted, both required (found 2026-08-15):** (i) `"stamp"` — `category_export_markdown` writes a `Last content verification:` line that lives OUTSIDE the marker pair, so a body-only emission drops it entirely; (ii) `"start_prefix"` — two producers DATE-STAMP their START line, so a consumer matching the full literal `start` string never finds yesterday's block and appends a duplicate on every run. The marker-injection into fabrik's real packs/docs **moves to the Phase-C deliver step** (fabrik-side). **(f) — 12F XI stdout logging (F5):** the engine's `cache/update.log` file-write (`daily_refresh.sh:56` `LOG_FILE=…/cache/update.log`) is **removed outright — the app logs to stdout, period.** Do NOT keep an in-app "tee to a local log if the operator wants" hedge: that is the same XI violation and it re-creates the `cache/` state B.1 rsyncs. An operator who wants a local file redirects at the *invocation* layer (`daily_refresh.sh >> /var/log/… 2>&1` in cron) — outside the app, which is 12F-legal. Run → **GREEN**.
3. Gate: `python -m pytest /opt/ai-model-catalog/engine/tests/test_no_fabrik_paths.py -v` → **Expected:** pass; `grep -rE "cache/update\.log|>> .*\.log" engine/ | grep -v LOG_TO_STDOUT` → **Expected:** no unconditional in-container logfile write.
4. Gate (no-clobber isolation): `.venv/bin/python -m pytest /opt/ai-model-catalog/engine/tests/test_output_root_isolation.py` — asserts a producer run writes **only** under `engine/out/` (mirrored + `blocks/`) and leaves `/opt/ai-model-catalog/.windsurf/rules/ai` **byte-unchanged**. → **Expected:** pass.

**B.2g — SQLite → Postgres conversion (NEW 2026-08-12; the step Global Constraints promises).** The
data-store decision is only real if a step performs it. Deliverables: (1) schema DDL for the catalog store in the
new repo's Postgres (`server/db/`), derived from the live SQLite schema (`sqlite3 kilo_agents.db .schema`);
(2) a one-shot idempotent migrate script; (3) repoint the engine's `DB_PATH = Path(__file__).parent /
"kilo_agents.db"` readers at a `CATALOG_DSN` env. ⚠️ **Scope corrected 2026-08-15: ~40 was measured at 70** files referencing `kilo_agents.db` in the copied engine — enumerate with `grep -rl kilo_agents.db engine/*.py` and convert from that list, never from the stale estimate, or ~30 readers keep a live SQLite handle after the store has moved. **Gate (equality, not vibes):** row counts per table match
between source SQLite and target Postgres, and `SELECT count(*) FROM agents` matches **the count read from the SOURCE SQLite in the same run** — **NOT a frozen literal.** The plan said 909; the live DB reads **916** (measured 2026-08-15), because the catalog grows daily. A hardcoded number here fails the conversion for the wrong reason, or worse invites someone to 'fix' the gate by editing the number — which would silently accept real row loss. Capture `sqlite3 kilo_agents.db 'SELECT count(*) FROM agents'` FIRST, then assert Postgres equals it.
⚠️ **THREE FINDINGS FROM B.2g EXECUTION (2026-08-15), all verified against the live stores:**
(i) **The grep enumeration under-counts.** `correlated_prior.py` and `microbench_review.py` are real catalog readers that never contain the literal `kilo_agents.db` — they do `from build_task_baselines import DB_PATH`. A path-grep misses transitive importers; enumerate by IMPORT GRAPH, which is the same lesson E.1 already states for the excise.
(ii) **⚠️ SQLite and Postgres DISAGREE ON NULL ORDERING, and it silently inverts every ranking query.** `ORDER BY arena_elo DESC` puts NULLs LAST in SQLite and FIRST in Postgres — so a shortlist query returns the models with NO score at the top. Caught live producing garbage shortlists; fixed generically in the translator (`catalog_store.py:165` appends `NULLS LAST`) and pinned by regression tests. Any future direct Postgres query in this engine inherits the hazard.
(iii) **⚠️ B.3 BYTE-PARITY HAZARD — fix BEFORE running the oracle.** Producers whose `ORDER BY` is not a TOTAL order tie-break differently across engines: observed `claude-opus-4.6` ↔ `gemini-3.5-flash` swapping at the LIMIT boundary, both `arena_elo=1535`. The row DATA is identical, so this is not a conversion bug — but the byte-identical oracle will flag it as one. Add a deterministic `, id` tiebreak to the producers FIRST, or B.3 fails on a false diff and someone 'fixes' the oracle instead of the query.

⚠️ **B.3's parity oracle must run the producers against the POSTGRES store** — running it against the un-converted SQLite proves nothing about the conversion, which is the whole point of the oracle.
🔴 **UNMET AS OF 2026-08-15 (B-B9, re-confirmed pass 7): `CATALOG_DSN` is provisioned NOWHERE** — no `engine/.env`, no export in `daily_refresh.sh`, and `catalog_store.py:11` documents the unset case as a silent `sqlite3.connect` fallback. **So B.3's GREEN was measured against SQLite.** The structural contract (artifacts, markers, columns, key schema) is genuinely proven; the CONVERSION is not. Provision the DSN and re-run B.3 before treating B.2g as certified. This is not a blocker on D — it is a caveat on what B.3's green means.

**B.3 — Standalone green + structural parity (behavior 2 — the flagship of this phase).**
1. `cd /opt/ai-model-catalog/engine && python -m venv .venv && .venv/bin/pip install -e .` (toolchain preflight: `.venv/bin/python --version` → 3.11+; `which sqlite3`).
2. Run the artifact producers only (no live scrapes — feed the copied `kilo_agents.db`; `OUTPUT_ROOT=engine/out`): the file producers write `engine/out/<fabrik-relative>`, the injector producers emit `engine/out/blocks/*.txt` + `manifest.json` (per B.2e). **Assert the refactor actually took (else B.3 parity fails confusingly on the one hybrid file):** `grep -c "EMBEDDING_CATALOG" engine/out/docs/reference/kilo/KILO_MODEL_CAPABILITIES.md` → **Expected: 0** — the engine emits the **base**; the block lives only in `engine/out/blocks/`. A non-zero count means an injector still injects in-producer (B.2e incomplete), not a parity bug.
3. ⚠️ **REWRITTEN 2026-08-15 (A-B1) — the sha256 golden set this step diffed against never existed.**
   `/opt/fabrik/scripts/kilo-benchmarks/tests/golden/` holds exactly `structure.json` and
   `db_queries.json`; there are **no** whole-file hashes, no `blocks/` bodies, no `manifest.json`, and
   `grep -c sha256 structure.json` → **0**. The 2026-08-12 blockquote in Phase A already retired
   byte-identity in favour of STRUCTURAL equivalence and moved byte-equality to Phase C's same-moment
   parallel-run — this step was simply never rewritten to match, so following it literally builds a
   harness against a fiction. **What B.3 asserts instead:** write
   `/opt/ai-model-catalog/engine/tests/test_parity_vs_fabrik_golden.py` comparing the engine's `engine/out/**` to the
   **structural contract** in `golden/structure.json` — the artifact inventory (13), the marker
   inventory (18 `<host>::<MARKER>` keys), each artifact's markdown skeleton + table COLUMN contract,
   and each JSON's key schema. Red on: an artifact no longer produced, a marker no longer emitted, a
   lost table column, a lost JSON field. **Byte-equality is NOT asserted here and its absence is not a
   gap** — these are live aggregates over a flywheel that gains rows daily (measured: 3 artifacts
   byte-drifted across two consecutive runs with 0 structural drift), so a frozen byte-golden is stale
   within 24 h. Phase C's old-vs-new-at-the-same-instant diff is the only byte comparison that means
   anything, and it already owns that. ⚠️ **The tempting wrong fix — regenerating goldens from the
   RELOCATED engine and diffing them against themselves — makes the oracle self-certifying and
   silently retires behavior 2. Do not.**
4. Gate: `.venv/bin/python -m pytest tests/test_parity_vs_fabrik_golden.py tests/ -v` → **Expected:** parity passes and the collected count is **computed at run time, never asserted against a frozen literal** (B-B6: the plan has carried 64, 67 and 68 for this one number; live is 69 files / 1291 tests and it moves every time a phase adds a test). The signal that matters is a count that SHRINKS between runs — that is silent test loss. Pre-existing failures are baseline-attributed: capture them from a worktree at the phase's starting commit and assert **zero NEW** names, not zero failures.

**B.4 — ⛔ DELETED (D5, 2026-08-12): compose worker wiring + image deps served the retired container only. Its `psql`-in-Dockerfile mandate also contradicted B.2c's DO-NOT-REWRITE.**
> ⚠️ **The three numbered steps that used to follow were REMOVED in pass 7, not struck through.** They were unmarked imperatives — including a "MANDATORY Dockerfile update" whose content B.2c forbids — sitting under a ⛔ DELETED heading, i.e. exactly the hazard E.4's own rewrite names when it says its steps were *"DELETED here rather than left as imperatives a skim could execute."* Nothing in B.4 executes. The compose/worker work belongs to the separate VPS spec.
> ⚠️ Two consumers still assume it: Files says `MODIFY compose.yaml — wire the engine as a scheduled-worker service`, and File Scope owns `compose.yaml`. Both are VPS-spec scope, not this plan's.

**B.4a — Flywheel positive-proof, POST-MOVE (spec §7 gate 1, which A.0 cannot satisfy).** A.0 proves the read
works in fabrik, which was never in doubt; the spec requires the assert *from the relocated repo under the real
invocation context*. Gate, run from `/opt/ai-model-catalog/engine/` as the cron user/shell:
`.venv/bin/python -c "from rank_task_subagents import _query_rows; s,r=_query_rows(); assert s=='ok' and r, (s,len(r))"`
→ **Expected:** exit 0. A failure is BLOCKING — never a skip.

**B.5 — Doc + spec updates.** `ai-model-catalog` `CHANGELOG.md`; `docs/SERVICES.md`+`docs/OPERATIONS.md` (new worker service — Doc Sync Matrix); confirm `specs/services/ai-model-catalog.yaml` `shape.needs_database:true` already covers the SQLite/worker (no flag change — **CORRECTED 2026-08-12** — post-B.2g the catalog store IS Postgres, so `needs_database: true` now genuinely covers it; the old reasoning (~~SQLite isn't the shape DB~~); note it).

**B.Behavior Contract:** behaviors 2 (parity) + the decoupling invariant (B.2 — `test_no_fabrik_paths.py`) + the OUTPUT-isolation invariant (B.2e — `test_output_root_isolation.py`, no-clobber of the project's own `.windsurf/rules/ai`). Risky path (parity) is TDD'd first.

**B.closing:** run in **ai-model-catalog**: `python scripts/final_gate.py --check --json` (that project's gate) → green; `check_doc_sync.py`; **`/fabrik-review`** on `engine/**` + `compose.yaml` (pool finders + native Opus for the DB/idempotency/decoupling surface) → no-op; commit (`Agent-Phase: B`) + plan-file marker.

---

## Phase C — Delivery bridge + parallel-run · both repos · the safety window — 🟡 CODE COMPLETE 2026-08-15 (`07d0d51`, `5266354a`, `ee8988c`) · **WINDOW OPEN — calendar-gated**

> **C.1 ✅** `/opt/ai-model-catalog/engine/deliver_to_fabrik.py` + 11 injection tests, each proven to BITE by mutation.
> **C.2 harness ✅ and the window is OPEN** — a real shadow bundle was delivered to
> `/tmp/deliver-shadow` today (23 files, 11 hosts seeded, live repo untouched). **C.3 ✅** all three
> rollback gates green: fabrik's own producers satisfy the golden (81/0), `pick_models` + 
> `kilo_auto_route` resolve, the selection-doc-removed fail-open holds, and `git status` on
> `.windsurf/` + `docs/reference/kilo/` is clean.
>
> ⛔ **C.2's ≥7-day observation window (incl. a Sunday) CANNOT be completed inside one run** — it is
> elapsed-time data that does not exist yet, and **Phase D's cutover is gated on it by design**.
> Cutting over early would discard the safety property the window exists to establish.
>
> **C-B5 (new, found by RUNNING it):** the plan says "diff shadow vs fabrik-live" without
> constraining WHEN. Measured today — fabrik's cron produced at 03:01Z, the relocated engine at
> 15:40Z — `TASK_SUBAGENT_SELECTION.md` diverged on `n_total=124` vs `142` with a reshuffled top-3.
> Neither engine is wrong: the flywheel gained 18 runs between them and every ranking derives from
> it, so a pair taken 12h apart is GUARANTEED to differ on real data and **the window as specified
> could never go green.** The harness now refuses to judge a pair skewed >3h (neither pass nor fail),
> and C.2's protocol is to run the two engines ADJACENTLY. Evidence the decoupling itself is sound:
> with skew removed `kilo_47_agents_final.json` is **byte-IDENTICAL** between the two engines;
> the selection doc differs on 13 of 227 lines, all flywheel-derived.
>
> ⚠️ **Incident, recorded because the lesson generalises:** proving the `--target-root` containment
> guard by NEUTERING it caused the exact escape it guards. `DEFAULT_TARGET_ROOT` resolves to the real
> `/opt/fabrik`, so the neutered run injected into the live fleet-synced `.windsurf/rules/ai/20-vision.md`
> — and that corrupted pack took **fabrik's own contract oracle from 81/0 to 8 FAILED**, i.e. the escape
> reddened the very check that would have to certify a fleet sync. Both restored (fabrik 81/0, tree
> clean). Fixed by an autouse fixture pointing `DEFAULT_TARGET_ROOT` at `tmp_path`: a test whose subject
> writes into repos must have NO live path reachable from ANY code path, and the mutation proof is
> precisely when the implementation is wrong on purpose. Re-verified — the identical neuter now fails
> SAFELY (2 red, 0 files modified).

**Deliverable:** `ai-model-catalog` **delivers** the produced bundle into fabrik's consumed paths; both engines run in parallel for ≥1 week; a daily diff proves zero divergence. Fabrik is still on its own engine — nothing has broken.

**Files:**
⚠️ **S1a (2026-08-12) — the Postgres conversion orphans TWO retained fabrik consumers that read the SQLite
file directly, and both STAY in fabrik:** `scripts/generate_kilo_agents.py:33,39` (`import sqlite3`;
`DB_PATH = .../kilo-benchmarks/kilo_agents.db`) and the rule-6 carve-out `scripts/kilo-benchmarks/db_models.py:16,20`,
which `scripts/kilo_auto_route.py:55-62` imports via `sys.path.insert` and `coding-auto.sh:32` execs by absolute
path. After conversion the engine has no SQLite file to emit, so mode (c) below would deliver a **frozen** `.db`
(silent staleness in Traycer agent regeneration + the coding router) or Phase E deletes it and `kilo_auto_route`
dies at import. **Contract: the engine exports a SQLite SNAPSHOT of the Postgres catalog store to
`engine/out/kilo_agents.db` as an explicit delivery artifact.** Gate: after a delivery,
`sqlite3 <delivered.db> "SELECT count(*) FROM agents"` matches the Postgres count.

- CREATE (ai-model-catalog) `/opt/ai-model-catalog/engine/deliver_to_fabrik.py` — three delivery modes: (a) **copies** the file artifacts `engine/out/<rel>` → fabrik's `docs/reference/kilo/` (selection docs + `KILO_MODEL_CAPABILITIES.md` **base**, see #10), `scripts/kilo_47_agents_final.json`, and `scripts/kilo-benchmarks/models_browser.html` (#11 — its retained fabrik home, carved out of the Phase-E delete) (reuse the `_atomic_copy` pattern from `sync_enforcement_to_projects.py:279`) — **NOT** `CAPABILITIES.md`/`capabilities.json` (fabrik's own `generate_capability_index.py` still produces those locally, Phase D — delivering them would collide with a live producer); (b) **injects** each `engine/out/blocks/<host>.<MARKER>.txt` into its live host file via marker-replace — the full host set (grep-grounded): the `.windsurf/rules/ai/*.md` packs for OPENROUTER_ROUTES/GATEWAY_COUNTS; **three** hosts for the `EMBEDDING_ROSTER/CATALOG/WINNERS` blocks — `docs/reference/kilo/KILO_AGENT_SELECTION_GUIDE.md`, `docs/reference/kilo/KILO_MODEL_CAPABILITIES.md`, and **`.windsurf/rules/core/65-rag-search.md`** (`embedding_export_markdown.py:40-42`; ⚠️ the last is a **CORE** rule pack — higher blast than ai/); and `KILO_AGENT_SELECTION_GUIDE.md` for `ROSTER` (`generate_selection_guide_roster.py:21`) — the marker-injection the four injector producers used to do in-producer now runs fabrik-side HERE (the engine only emits block bodies). **Ordering (#10):** for the hybrid `KILO_MODEL_CAPABILITIES.md` (whole-file base + injected `EMBEDDING_CATALOG`), mode (a) copies the base FIRST, then mode (b) injects the `EMBEDDING_CATALOG` block into it — so (a) must precede (b) for that file; (c) **copies `engine/out/kilo_agents.db` → fabrik `scripts/kilo-benchmarks/kilo_agents.db`** (F1 — fabrik's retained `generate_kilo_agents.py:38` reads this DB directly via `sqlite3.connect`; without the delivered DB, Phase E's delete of the engine copy silently breaks Traycer CLI-agent regeneration).
- CREATE (ai-model-catalog) `/opt/ai-model-catalog/engine/tests/test_deliver_injection.py` (F4) — the marker-injection is high-blast **new** code (it writes into LIVE fabrik packs/docs); it must port + prove the hardened edge cases the 4 origin injectors carry: **idempotent** (inject twice → identical), **replace-not-duplicate** on a valid START/END pair, and **orphan/dangling-marker self-heal** (`category_export_markdown._replace_or_append_markers:191`, `embedding_export_markdown._replace_between_markers:209-245`). Red-then-green each. **Blast note:** one host is a CORE pack (`65-rag-search.md`), so a bad inject corrupts a fleet-synced rule — this test is not optional.
- CREATE (fabrik) `scripts/kilo-benchmarks/tests/test_parallel_run_diff.py` — daily diff: delivered bundle vs fabrik-self-produced.

### Interfaces
**Consumes:** `engine/out/**` (Phase B). **Produces (for Phase D):** the delivered artifacts in fabrik's consumed paths; a `parallel_run.log` of daily diffs.

### Steps
**C.1 — Build the deliver step.** `deliver_to_fabrik.py --dry-run` prints the planned copies; `--apply` writes them (atomic). **⚠️ It MUST take `--target-root <dir>` (default `/opt/fabrik`) — N3:** every copy AND every marker-injection resolves under that root, so C.2's parallel-run can deliver into `/tmp/deliver-shadow/` **without touching a single live fabrik path** (mode b writes into rule packs incl. the CORE `65-rag-search.md` — injecting those live during the safety window would defeat Phase C's whole purpose and Behavior 6's rollback guarantee). D.1's "point it at fabrik's real consumed paths" = dropping the flag / passing `--target-root /opt/fabrik`. Gate: `python /opt/ai-model-catalog/engine/deliver_to_fabrik.py --dry-run --target-root /tmp/deliver-shadow | grep -c "docs/reference/kilo"` → **Expected:** ≥6 (the real selection-doc count, R10-2), and **every printed destination starts with `/tmp/deliver-shadow`** (assert no `/opt/fabrik` path appears: `… --dry-run --target-root /tmp/deliver-shadow | grep -c "^/opt/fabrik"` → **Expected: 0**).
⚠️ **S1d (2026-08-12) — the parallel-run gate can pass TRIVIALLY.** `daily_refresh.sh:92-96` guards on
`LOCK_FILE="/tmp/.fabrik_daily_$(date -u +%Y%m%d)"` and `exit 0`s if it exists. Under WSL-only BOTH engines run on
the SAME box and share that path, so whichever runs second exits 0 having produced nothing — and
`test_parallel_run_diff.py` then diffs a STALE shadow bundle against fabrik-live and can go GREEN while the
relocated engine never ran at all. **Fix before C.2 runs:** namespace the engine copy's lockfile
(`/tmp/.amc_engine_daily_$(date -u +%F)`), and add a C.2 gate asserting the shadow bundle's mtime advanced that
day — `test $(date -u +%F) = $(date -u -r engine/out/docs/reference/kilo/TASK_SUBAGENT_SELECTION.md +%F)`.

**C.2 — Parallel-run (behavior 3, real-world).** Keep fabrik's `daily_refresh` running its engine; run ai-model-catalog's engine → deliver into a **shadow dir** (`/tmp/deliver-shadow/`, not fabrik's live paths yet). Daily for **≥7 days incl. a Sunday** (microbench day), diff shadow vs fabrik-live. Gate: `python -m pytest scripts/kilo-benchmarks/tests/test_parallel_run_diff.py` → **Expected:** zero diff across the window.
**C.3 — Behavior Contract:** behavior 3 (no consumer divergence) proven over a full week including the Sunday specialty-bench; **+ the deliver-injection idempotency/self-heal contract** (`test_deliver_injection.py`, F4) — inject-twice-identical, replace-not-duplicate, orphan-marker self-heal — since the marker-replace logic is re-implemented fabrik-side and writes into live packs; **+ behavior 6 (ROLLBACK — N4: it was declared in the master contract but owned by no phase).** C owns it because C is the safety window: prove "reverting = turn delivery off" by asserting fabrik's own engine still produces independently — gates (the artifact oracle alone proves nothing about the CONSUMER — prove both): (i) with delivery disabled (no `--apply` that day), `python -m pytest scripts/kilo-benchmarks/tests/test_golden_parity.py` → **Expected:** still green from fabrik's own producers; (ii) **the consumers still resolve** — `python -c "import sys; sys.path.insert(0,'libs'); from subagents.select import pick_models; print(pick_models('code')[:3])"` → same top-3 as baseline, AND `python scripts/kilo_auto_route.py --help` (the Traycer coding dispatch path) exits 0; (iii) **nothing live was touched all window** — `--target-root /tmp/deliver-shadow` means `git status --porcelain docs/reference/kilo/ .windsurf/rules/` → **Expected: empty** apart from fabrik's own daily_refresh output. Together these prove "reverting = turn delivery off" leaves fabrik fully self-sufficient.

**C.closing:** gate green in **both** repos (each its own `final_gate --check`); `check_doc_sync`; **`/fabrik-review`** on `deliver_to_fabrik.py` (native Opus — it writes into fabrik's consumed paths, high-blast) + the diff test → no-op; commit per-repo (`Agent-Phase: C`).

---

## Phase D — Cutover · runs in `/opt/fabrik`

> **REWRITTEN CLEAN 2026-08-15 (pass 9).** The previous D+E was 483 lines carrying 39 warning
> markers and 76 blocker references — eight review passes had appended findings faster than the steps
> were corrected, so each new edit had ~40 neighbours to reconcile and passes 6–8 each left the
> *step* asserting what its own *blocker* refuted. Every verified finding is folded into the steps
> below, stated ONCE. The 115-finding record is preserved verbatim in § Appendix — Review Record;
> nothing was discarded, but **these steps are now the artifact and the appendix is history.**
>
> **Every gate here was RUN against the live tree before being written down.** Where a gate could not
> pass, could not fail, or measured the wrong thing, it was rewritten and re-run — that is the whole
> reason this section exists.

**Deliverable:** fabrik's `daily_refresh.sh` and `wsl_startup_hook.sh` stop running engine steps; the
external engine (delivering live) is the sole producer; fabrik keeps `generate_kilo_agents`,
`generate_capability_index` and `sync_enforcement_to_projects`. The vendored `_TABLE` floor stays.

**✅ C.2 WINDOW WAIVED — operator ruling 2026-08-15, recorded here because it changes the risk.** D was
gated on a ≥7-day parallel run. The operator waived it explicitly. What that trades away: the window
would have caught a divergence that only appears across several daily cycles (a Sunday-only specialty
bench, a weekly scrape). What still protects the cutover: C.1's delivery bridge is mutation-proven,
C.3's three rollback gates are green, the same-instant diff showed `kilo_47_agents_final.json`
byte-IDENTICAL between the two engines, and behavior 6 holds — reverting is still 'turn delivery off',
because D deletes no producer, it only stops fabrik invoking its own.

**Files (MODIFY, fabrik):**
- `scripts/kilo-benchmarks/daily_refresh.sh` — remove the engine steps, keep the consumer steps.
- `scripts/wsl_startup_hook.sh` — **owned by THIS phase.** It invokes **23 distinct engine files**
  (18 via `*_SCRIPT=` variables at `:36-44`/`:53-61`, every one used at `:150-154`/`:161-163`/
  `:188-211`, plus 5 by absolute path at `:130`/`:232`/`:233`/`:234`/`:235`/`:236`/`:243`). It is a
  full second engine pipeline, not a husk. Every invocation is swallowed by `>> $LOG_FILE 2>&1 || {…}`.
- `scripts/generate_kilo_agents.py` — strip the `if not args.dry_run:` "Auto-update docs" block
  (`:952-972`) that `importlib.exec_module`s two engine scripts. Phase C's deliver step owns roster +
  capabilities injection now, so the block is redundant; left in place it degrades to a silent
  `[warn]` at `:970` on the live path.

### Steps

**D.0 — Capture the cutover baseline (NEW; D.2 has always compared against a baseline nobody created).**
`tests/golden/` holds only `db_queries.json` and `structure.json`; neither records a `pick_models`
result. Capture one BEFORE any cutover step:
`python -c "import sys,json;sys.path.insert(0,'libs');from subagents.select import pick_models;
json.dump({t:pick_models(t,n=3) for t in ('code','review','docs','plan','research','spec')},
open('scripts/kilo-benchmarks/tests/golden/pick_models_baseline.json','w'),indent=1)"`
→ **Expected:** the file exists and every value is a **non-empty** list. ⚠️ NOT '3-element': `pick_models` returns *up to* n, and the synced doc lists a single model for `plan` and `spec`, so a correct capture yields `{code:3, review:3, docs:3, plan:1, research:3, spec:1}`. A 3-element assertion reds a correct baseline — or invites someone to 'fix' the producer. Commit it.

**D.1 — Shrink the two orchestrators.** Remove every engine `_step` from `daily_refresh.sh` (**55 real invocations**; `grep -c '_step '` returns 57 but `:364` and `:527` are comments) except the seven allow-listed. From `wsl_startup_hook.sh` remove the **18 `*_SCRIPT=` engine invocations** — ⚠️ **but NOT the five absolute-path ones at `:130`/`:232`/`:233`/`:234`/`:235`/`:236`/`:243`.** Those five ARE the retention justification for `rank_task_subagents.py`, `capture_golden.py`, `check_daily_refresh_freshness.py`, `pipeline_alert.sh` and `autocommit_pipeline_outputs.sh`; stripping them would leave K2 retaining five files with zero readers, and `:232`'s ranker invocation carries the **A.0 gate-3 alert** built specifically to satisfy the operator's *"we should not break flywheel"* constraint. Removing it silently undoes A.0. The retained `daily_refresh.sh` is an
**allow-list** of exactly SEVEN — ⚠️ `check_daily_refresh_freshness` is itself a `_step` (`daily_refresh.sh:163`), so an allow-list that retains the FILE but omits the STEP name reds gate (i) on the very thing the ⚠️ below says to keep: `gather_envs`, `classify_services`, `deliver_to_fabrik`,
`generate_capability_index`, `generate_kilo_agents`, `sync_enforcement_to_projects`, `check_daily_refresh_freshness` — six exist today, `deliver_to_fabrik` is the Phase-C script invoked as a `_step` under exactly that name. **55 real invocations − 6 retained = 49 removed.**

⚠️ `check_daily_refresh_freshness` is **RETAINED, not dropped.** An earlier version deleted it as an
obsolete self-check "with no orphan, no carve-out" — `wsl_startup_hook.sh:236` is a live second
caller. It moves with the retained remnant.

- **Gate (i) — the step allow-list.** Comments must be stripped FIRST, or the gate reds on prose: the
  comment at `daily_refresh.sh:527` contains the literal `_step "label"` and a naive grep extracts
  `label`, making the gate unpassable after a perfect surgery.
  `grep -vE '^[[:space:]]*#' scripts/kilo-benchmarks/daily_refresh.sh | grep -hoE '_step "[a-z_0-9]+"' | sort -u`
  → **Expected:** a subset of the six allow-list names.
- **Gate (ii) — engine-script references, both files.** The char class MUST include `/`, or every
  subdirectory script collapses to its directory name and `$KB/tests/capture_golden.py` renders as
  `$KB/tests`, which the retained list contains — the gate then passes with the blocker present.
  `grep -hoE '(\$KB|\$\{KB\}|scripts/kilo-benchmarks)/[A-Za-z_0-9./-]+' scripts/kilo-benchmarks/daily_refresh.sh scripts/wsl_startup_hook.sh | sort -u`
  → **Expected:** every hit is a member of the § E retained remnant **or is `cache/` / `backups/`** — ⚠️ those two are runtime state the retained orchestrator still writes (`:56` heartbeat log path, `:137` DB backup, `:562-576` the freshness stamp K2's `check_daily_refresh_freshness.py` reads) and the pass-9 rewrite dropped them from the Expected list, making the gate unpassable after a perfect surgery (which now includes
  `tests/capture_golden.py`, `pipeline_alert.sh`, `autocommit_pipeline_outputs.sh`,
  `check_daily_refresh_freshness.py` and `rank_task_subagents.py` — do NOT read the old
  "any `.py` here must be removed" wording, which contradicted the remnant).

**D.2 — Cutover verification (behavior 1).**
1. `python -c "import sys;sys.path.insert(0,'libs');from subagents.select import pick_models;print(pick_models('code',n=3))"`
   → **Expected:** equals `pick_models_baseline.json["code"]` from D.0. **`n=3` is required** —
   `pick_models(task_type, n=1)` is the signature, so `[:3]` on the default returns ONE model.
2. Force-remove the selection doc → `pick_models('code',n=3)` still returns (falls to `_TABLE`), does not raise → restore. ⚠️ **Disable the governance-sync FIRST** (`SKIP=governance-sync`, and do not run `sync_enforcement_to_projects.py` while the doc is absent): `docs/reference/kilo` is `GOVERNANCE_DIRS[2]` and governance dirs **are** orphan-pruned (`sync_enforcement_to_projects.py:548` — `if relative not in source_files: dest_file.unlink()`), so any sync firing during the window deletes the doc from 47 project copies. Use a copy-aside/restore, never a `git rm`. **Verified working:** the fallback returns a *different* ordering, so this
   gate genuinely discriminates.
3. **Delivered-doc freshness.** Do NOT use `check_ai_pack_freshness.py`: its own docstring says
   *"Exit 0 always — a freshness signal, NOT a gate"*, it reads hand-written pack stamps rather than
   delivered-doc mtimes, and its threshold is 90 days.
   `python -c "import time,pathlib;p=pathlib.Path('/opt/fabrik/docs/reference/kilo/TASK_SUBAGENT_SELECTION.md');
   age=(time.time()-p.stat().st_mtime)/3600;assert age<30, f'{age:.1f}h old'"`
   → **Expected:** exit 0. (30h, not 24h: a 24h threshold on a 24h cron has zero margin and reds on
   any delivery slip. Absolute path, because the gate is CWD-sensitive otherwise.)
4. **Fleet smoke — must shadow the hub doc, or it cannot fail.** `libs/subagents/select.py:357-359`
   prefers `_HUB_SELECTION_DOC` whenever `/opt/fabrik` exists, so a project reading its own vendored
   copy is never exercised on this box: with a project's copy husked to `BROKEN/sync-failed-model`
   the unshadowed gate still returned the correct hub answer, from the wrong file.
   `cd /opt/<project> && SUBAGENT_SELECTION_DOC=$PWD/docs/reference/kilo/TASK_SUBAGENT_SELECTION.md python -c "…pick_models('code',n=3)…"`
   → **Expected:** matches the D.0 baseline, proving `sync_enforcement_to_projects` really delivered.
   (**48** vendored copies, measured.)
5. Overlap ≥3 days monitoring `pick_models` + the flywheel. *(Elapsed-time; not runnable in a session.)*

**D.3 — Behavior Contract:** behavior 1, both clauses — the fleet resolves post-cutover (D.2.1/D.2.4)
and the selection-doc-removed `_TABLE` fail-open holds (D.2.2).

**D.closing:** `final_gate --json` green; `check_doc_sync`; `/fabrik-review` on the diff → no-op;
commit (`Agent-Phase: D`) + plan marker.

---

## Phase E — Excise residue · runs in `/opt/fabrik`

**Deliverable:** the engine and the genuinely-dead Kilo/Cascade scripts are gone from fabrik.
**Deploy is OUT OF SCOPE (D5)** — no `fabrik apply`, no container, no network DSN.

### What is KEPT — decided, not deferred

**K1 — `scripts/kilo_code_review.py` and `scripts/kilo_docs_enforcer.py` STAY.** They are not Kilo
residue; they are live fleet-synced governance on eight surfaces — `fabrik_synced_manifest.py:29-30`
(CORE_SCRIPTS), the governance-sync `files:` filter at `.pre-commit-config.yaml:65`,
`sync_enforcement_to_projects.py:5`, `watch_enforcement_changes.sh:49-50`, `src/fabrik/scaffold.py:1017-1018`,
the fleet-synced pack `.windsurf/rules/core/50-code-review.md:75,87`,
`templates/saas-skeleton/AGENTS.md:101`, `templates/scaffold/gitignore-synced-block.txt:30` — with
**48 project copies on disk**. Deleting them fails silently in both directions: `sync_enforcement_to_projects.py:405`
copies CORE_SCRIPTS under a bare `if source.exists():` with orphan pruning only for `VENDORED_DIRS`,
and `scaffold.py:1025` has the same guard, so new projects would ship without Step-3/Step-4 tooling
and no test asserts otherwise. **Because they stay, `scaffold.py` needs no change** and their two
tests (`tests/test_kilo_review_validation.py`, `tests/test_kilo_strictness_scenarios.py`) stay too.

**K2 — the retained remnant is COMPUTED, not listed.** ⚠️ Ten review passes could not keep a hand-written KEEP list sound; the proof is that the list below retained `rank_task_subagents.py` while deleting `build_task_baselines.py` and `derive_cost.py` **which it imports** (both behind `try/except`, so post-excise it exits 0 and publishes a silently degraded selection doc to 47 project copies), and retained `check_daily_refresh_freshness.py` while deleting the `alerting/` package it needs to raise the alarm. **Run `python scripts/kilo-benchmarks/tests/excise_manifest.py --check`** — it states the ROOTS (a judgement, each with its retained caller as evidence) and computes the CLOSURE (a fact), failing when any retained file depends on a deleted one. ⚠️ **It must run AFTER D.1**: `daily_refresh.sh` is a root and the closure follows what it invokes, so against today's un-shrunk orchestrator the KEEP set is **156 files, not 16** — the script refuses to certify until the orchestrator is down to its six-name allow-list. The roots below are the input to that computation, not the answer:
`kilo_agents.db` · `models_browser.html` · `daily_refresh.sh` (shrunk, `0 6 * * *` cron) ·
`tests/golden/**` · `tests/capture_golden.py` · `tests/test_golden_parity.py` ·
`tests/test_parallel_run_diff.py` · `pipeline_alert.sh` · `autocommit_pipeline_outputs.sh` ·
`check_daily_refresh_freshness.py` · `rank_task_subagents.py` · the rule-6 coding-router deps
`classify_ticket.py` + `db_models.py` + `kilo_telemetry.py` · the rule-7 data files
`claude_p_cost.json` + `claude_price_ratios.json`.
*Why each:* the three `tests/` Python files are the ONLY readers of the retained `tests/golden/**` —
without them the golden survives with zero readers, and `C.3` gate (i) invokes one of them post-E.
The five shell/py at the end are invoked by the RETAINED boot hook and orchestrator.

**K3 — rule-7 data relocation.** `cp` (not `git mv`) `claude_p_cost.json` + `claude_price_ratios.json`
to `scripts/`, `git add` both. `scripts/claude_p_cost.py` resolves them via `_find()` (`:49-56`) as
`_HERE/<name>` then `_HERE/"kilo-benchmarks"/<name>`; after E they are the only copies and the first
path wins. ⚠️ It is **NOT** fleet-synced (absent from `fabrik_synced_manifest.py`) — its own docstring
says otherwise and is wrong; the blast radius of getting this wrong is hub-only.

### What is DELETED

**E.2(i)** — `git rm -r` the engine under `scripts/kilo-benchmarks/`, keeping K2.
**E.2(ii)** — the genuinely-dead top-level scripts (verified 2026-08-15: all present, brace expansion resolves
to **14** files, exit 0 — 9 named + 4 `Local_*.sh` + `Kilo_Review.sh`. My first draft of this line said
13; the count is stated here because a `git rm` naming one absent path fails the WHOLE command):
`git rm scripts/{kilo_dispatch.py,kilo_consult.py,kilo_cost_report.py,kilo_agent_health.sh,fix_traycer_agents.py,traycer_agent_review.py,mcp_kilo_server.py,run_kilo_workflow.sh,kilo_code_review_bckp.py} scripts/Local_*.sh scripts/Kilo_Review.sh`
⚠️ `kilo_code_review_bckp.py` **is** deleted despite K1 keeping its sibling: it has zero live CODE consumers (CHANGELOG, the design spec, and a capabilities.json row that regenerates) and cannot match the `\.py$`-anchored sync
filter. Keeping it would violate behavior 4.
**E.2(iii)** — `git rm tests/kilo_benchmarks/**` (**15** files — 14 tests + `__init__.py`) plus the two co-deleted
root tests: `tests/test_kilo_dispatch.py` (its module goes) and `tests/test_derive_cost_by_family.py`
(`derive_cost.py` is dead outside the engine — only engine-internal importers, and
`claude_p_cost.py:9-12` deliberately keeps a standalone copy rather than importing it).
⚠️ `process.py`/`process_v2.py` are NOT top-level; they exist only under `kilo-benchmarks/` and are
covered by (i). Do **not** "fix" this with a `scripts/process*.py` glob — that matches the live
`scripts/process_monitor.py`.

**E.2(iv) — dangling references to the deleted set** (each verified live): **all SIX `.windsurf/workflows/*.md`** — ⚠️ **my pass-9 text had this exactly INVERTED and it was measured wrong: `grep -rn kilo_code_review .windsurf/workflows/` returns ZERO.** `kilo.md` invokes `kilo_dispatch.py`; `local-coder`, `local-review`, `local-docs`, `local-fixer` invoke the four `Local_*.sh`; `auto-review` invokes `Kilo_Review.sh` — every one of those targets is in E.2(ii)'s `git rm`. `.windsurf/workflows` is a GOVERNANCE_DIR (`fabrik_synced_manifest.py:82`), so leaving five of them dangling propagates broken workflows to ~47 repos · 23 `scripts/traycer_agents_fixed/*.sh` and the
three sibling fixers `fix_balanced_tier_agents.py`, `fix_economy_tier_agents.py`,
`implement_self_review_workflow.py` plus `templates/traycer/agent-post-execution-hook.md`, all of
which invoke `traycer_agent_review.py` · the dead-script patterns in `fabrik_synced_manifest.py` and
`.pre-commit-config.yaml:65` (**not** the `kilo_code_review|kilo_docs_enforcer` entries — K1) ·
`watch_enforcement_changes.sh:49-50` · the rule-4 docs.

**E.2(v-pre) — repoint the retained orchestrator's alerting import (LOST in the pass-9 rewrite; the gate survived, the step did not).** `daily_refresh.sh:459` and `:514` do `sys.path.insert(0,'$KB'); from alerting import send_alert` — `$KB/alerting/` is deleted by E.2(i), and both calls are swallowed by `|| true`, so the operator's only heartbeat alert goes dark **silently**. Repoint both to fabrik's retained `libs/alerting`. Gate: `grep -c "sys.path.insert(0, 'libs')" scripts/kilo-benchmarks/daily_refresh.sh` → **Expected: 2**.

**E.2(v) — the residue emitter.** `rank_coding_subagents.py:392` writes
`**Generator:** \`scripts/kilo-benchmarks/rank_coding_subagents.py\`` into the delivered docs, so the
relocated engine re-injects the banned string daily into rule-1 KEEP artifacts. Repoint the header to
the engine's own path in `ai-model-catalog` **before** the residue gate is trusted, or the gate and
rule 1 are permanently unsatisfiable.

### Gates

- **(a) dead-pattern purge —** `[ "$(grep -rho 'kilo_dispatch\|kilo_consult\|mcp_kilo_server\|kilo_agent_health\|traycer_agent_review' scripts/fabrik_synced_manifest.py .pre-commit-config.yaml scripts/watch_enforcement_changes.sh | wc -l)" = 0 ]`
  → **Expected: exit 0.** ⚠️ Do NOT include `kilo_code_review|kilo_docs_enforcer`: a gate demanding
  those reach zero mandates the K1 regression — it forces them out of the sync while the files stay
  on disk, orphaning 48 project copies.
- **(a-inverse) the KEPT modules stay wired —** `grep -c 'kilo_code_review' scripts/fabrik_synced_manifest.py`
  → **Expected: ≥1.**
- **(b) positive-deletion proof —** `ls scripts/kilo_dispatch.py scripts/kilo_consult.py scripts/kilo_cost_report.py scripts/mcp_kilo_server.py 2>&1 | grep -c 'No such file'`
  → **Expected: 4.** ⚠️ `grep -c` exits 1 when it prints `0`, so never place this after `set -e`
  without `|| true`.
- **(c) residue —** `grep -rlE "scripts/kilo-benchmarks/[a-z_0-9]+\.py" /opt/fabrik --include=*.py --include=*.sh --include=*.md | grep -vE "/\.git/|/\.claude/worktrees/|docs/archive/|docs/superpowers/specs/|scripts/\.archive/|CHANGELOG\.md|LESSONS_LEARNT\.md|docs/development/|tests/integration/test_routing_failover\.sh|tests/test_docs_updater\.py"`
  → **Expected: empty.** ⚠️ `/\.claude/worktrees/` is **required**: those files are excluded from git
  via `.git/info/exclude`, not from grep, and sibling worktrees put 67–340 matches there — without it
  behavior 4 is unprovable on this box. Two intentional fixtures are excluded and must never be
  "fixed": `test_routing_failover.sh:49`'s fail-open sentinel and `test_docs_updater.py:187`'s string
  fixture asserting cross-repo links do NOT resolve.
- **(d) retained consumers still run —** `test -f scripts/kilo-benchmarks/kilo_agents.db`;
  `grep -c "generate_selection_guide_roster.py\|generate_model_capabilities.py" scripts/generate_kilo_agents.py`
  → **Expected: 0** after D.1's strip; `python scripts/kilo_auto_route.py --help` → exit 0;
  `python -c "import sys;sys.path.insert(0,'libs');from alerting import send_alert"` → imports.
  ⚠️ Do **not** gate on `generate_kilo_agents.py --out …`: that flag does not exist (argparse accepts
  only `-h`/`-d`), and the "equivalent" non-dry-run wipes `~/.traycer/cli-agents` via `shutil.rmtree`
  (`:875`). The failure it targets prints `[warn] Could not update` to stdout with **exit 0**, and the
  emitter sits inside `if not args.dry_run:` — so a `--dry-run` grep can never see it either. ⚠️ **And do not use the disposable-HOME run either** — `HOME` protects `~/.traycer` but NOT the repo: the non-dry-run path `exec_module`s two scripts that `write_text` into the fleet-synced `docs/reference/kilo/`, colliding with C.3 gate (iii)'s clean-tree assertion. It is also vacuous by construction post-D.1, since the `[warn] Could not update` emitter is inside the block D.1 strips. **Prove it by the static check above** (`grep -c` → 0) **plus** `python scripts/generate_kilo_agents.py --dry-run` exiting 0, which exercises the import path without writing.

**E.1 — Import-graph audit: BUILT, at `scripts/kilo-benchmarks/tests/excise_manifest.py`** (not a throwaway — it is the KEEP/DELETE authority and runs as a gate). It already handles the classes the previously-embedded version missed: package dirs (`alerting/` is exactly that case), subdirectory paths, `.sh` invocations, and `importlib` string literals. Retained for reference: Four defects in the previously-embedded version must not be reproduced: derive ENTRY from
the live crontab with a `/`-tolerant pattern **and guard every path with `.exists()`** (the old form
emitted other repos' absolute paths and died on `FileNotFoundError` before printing a line, while
missing this plan's own `0 6 * * *` cron); give the shell branch a `/`-tolerant pattern **and a `.sh`
alternation** (without them it cannot see `capture_golden.py`, `pipeline_alert.sh` or `coding-auto.sh`
— the very C3 dependency it exists to find); iterate the RULE-7 pass over the transitive set, not
`ENTRY`; and cover `.db`/`.html` as well as `json|yaml|txt`, since the two rule-1 artifacts are
otherwise invisible to the tool meant to prove the sweep complete. **Expected:** every `RULE-6 DEP` is in K2, and every `RULE-7 DATA DEP` is **either relocated per K3 or itself retained**. ⚠️ The second clause is the correction: with the mandated fixes applied (transitive iteration + `.db`/`.html` coverage) the pass legitimately reports `kilo_agents.db` — which K2 retains **in place** and gate (d) asserts exists. A stop-rule of 'any unrelocated RULE-7 DEP is an orphan' would fail on the artifact the plan deliberately keeps. Today the correct output is **5** RULE-6 lines
— the three carve-out modules plus `generate_model_capabilities.py` and
`generate_selection_guide_roster.py`, which D.1's strip removes; treat those two as handled, not as
orphans to carve out.

**E.3 — Full gate + pool smoke.** `python scripts/final_gate.py --json` → `"success"`
(baseline-attributed); run a real `/fabrik-review` finder round end-to-end.

**E.4 — ⛔ RETIRED (D5).** Deploy + network flywheel DSN are out of scope; the probe this step planned
was already run (spec §4: `fabrik_analytics` is on the WSL host's local socket,
`listen_addresses=localhost`, box not on the WireGuard mesh). Its steps were **deleted** rather than
left as imperatives a skim could execute.

**E.5 — Behavior Contract:** behavior 4 (residue).

**E.closing:** whole-plan `/fabrik-review` over the cumulative diff → no-op; `final_gate --json` green
(fresh) in both repos; `check_convergence.py` green; `/fabrik-docs-review`; commit (`Agent-Phase: E`)
+ flip `Status: → EXECUTED <date>`; archive to `docs/development/plans/archived/`.

**Out of migration scope (Phase 6, separate plan):** the catalog *product* — API, UI, multi-tenancy,
billing, and licensing the 7 high-risk scraped-ranking feeds.

---

## Subagent strategy

| Fan-out | Where | Recipe | Records |
|---|---|---|---|
| Per-phase `/fabrik-review` finders | A/B/C/D/E closing | `fanout("review", units=[dims], mode="read_only", project="catalog-extraction")` + `set_quality` + **≥1 native `fabrik-reviewer` (Opus)** on the high-blast slices (deliver step, cutover, residue-delete) | `subagent_runs` |
| Behavior-test authoring | A.3/B.2/B.3/C.1 | `fanout("code", mode="write", owned_paths=[disjoint per unit], project="catalog-extraction")` → curate → `git apply` | `subagent_runs` |
| Parallel grounding (this plan-review) | Phase 1 | `fanout("research", mode="read_only", web_tools=[…])` per independent unit + native `fabrik-researcher` (Haiku sample) | `subagent_runs` |

**Parallelism:** A→B→C→D→E are **sequential** (each consumes the prior). Within a phase, the review finders + test authors fan out in parallel and merge. Cross-repo: Phase B runs in ai-model-catalog, A/D in fabrik, C/E in both — no shared file within a phase.

## File Scope (owned paths)

- **fabrik:** `scripts/kilo-benchmarks/**` (snapshot in A, engine SCRIPTS deleted in E — **the retained remnant is § E K2, which is the single authority; do not re-list it here.** It grew from 4 items to 16 across the reviews and this line kept the stale four, which is how the two diverged), **`src/fabrik/scaffold.py`** (named by no list until now — it copies `kilo_code_review.py`/`kilo_docs_enforcer.py` into every scaffolded project under a silent `.exists()` guard; K1 keeps both, so it needs NO change, but it must be in scope so the next reviewer does not re-discover it), `scripts/traycer_agents_fixed/*.sh` (23), `.windsurf/workflows/kilo.md`, `scripts/fix_{balanced,economy}_tier_agents.py`, `scripts/implement_self_review_workflow.py`, `templates/traycer/agent-post-execution-hook.md`, **`tests/kilo_benchmarks/**`** (moved to engine in B, `git rm`'d in E), **`scripts/run_kilo_workflow.sh`** (deleted in E), `scripts/generate_kilo_agents.py` (D: strip auto-update block), `scripts/kilo-benchmarks/tests/test_{golden_parity,parallel_run_diff}.py`, `scripts/wsl_startup_hook.sh`, `scripts/fabrik_synced_manifest.py`, `.pre-commit-config.yaml`, `scripts/watch_enforcement_changes.sh`, the dead Kilo/Cascade scripts (E), the rule-4 docs (`docs/FEATURES.md`, `docs/operations/AI_MODELS_BROWSER_OPS.md`, `docs/workflows/KILO_BENCHMARK_WORKFLOW.md`, `docs/workflows/KILO_AGENT_MANAGEMENT.md`, `docs/CONFIGURATION.md`), `CHANGELOG.md`, `INDEX.md`, `PORTS.md`, `docs/PROJECT_CATALOG.md`, `docs/README.md`, this plan file. **(The exact rule-3/rule-4 set is enumerated mechanically by E.1's discovery grep — this list is the known core, not the completeness authority.)**
- **ai-model-catalog:** `engine/**`, `compose.yaml`, `CHANGELOG.md`, `docs/SERVICES.md`, `docs/OPERATIONS.md`.
- **Disjoint** from any known-active sibling plan (verify at scope-lock). The fabrik `INDEX.md`/`PORTS.md`/`PROJECT_CATALOG.md` are shared-churn files → **serialization points** (stage only this plan's lines, per the shared-master rule).

## Evidence

### Phase A grounded in
- Consumer manifest: spec §2 (the six output classes) — verified live this session (`select.py:479-483` fallthrough, `rank_task_subagents.py:335` query).
- `sync_enforcement_to_projects.py:279` `_atomic_copy` (the deliver-step reuse) — read this session.

### Phase B grounded in
- `ai-model-catalog` structure — `ls /opt/ai-model-catalog` (has `engine`-able tree; `compose.yaml` already carries a `worker` service at `:83`):
  ```
  services: ai-model-catalog(:12) · api(:46) · worker(:83) · fabrik network(:113)
  ```
- Engine size — ⚠️ **RE-MEASURED 2026-08-15 (P5-10): this section, the plan's own *grounding record*, was
  carrying the frozen 2026-07-26 numbers while the Files list at Phase B had already been corrected.** Live
  today: **101** top-level `.py` (not 98) + **55** in-tree tests (not 50) in `scripts/kilo-benchmarks/`
  (`ls scripts/kilo-benchmarks/*.py | wc -l` → 101; `find scripts/kilo-benchmarks/tests -name 'test_*.py' | wc -l`
  → 55) **+ 14 repo-root engine test files in `tests/kilo_benchmarks/`** (unchanged; `ls tests/kilo_benchmarks/*.py
  | grep -v __init__ | wc -l` → 14). Engine test total = 55 + 14 − 2 rule-6 tests = **67**, matching Phase B —
  **not** the 64 this line used to assert. A stale Evidence block is worse than no Evidence block: it is the
  section a fresh executor trusts as already-verified.

### Phase D grounded in
- Engine→consumer split: spec §3b (STAYS: `generate_kilo_agents`, `generate_capability_index`, `sync_enforcement`) — verified via `daily_refresh.sh:257/260` seam.
- Fail-open: `select.py:479-483` + `:373` 14-day gate; freshness: `check_ai_pack_freshness.py` (`wsl_startup_hook:213` — cite corrected pass 7; and per P6-5 it is an exit-0-always SIGNAL on 90-day pack stamps, **not** a delivered-doc gate).

### Phase E grounded in
- Dead-script inventory + non-propagation: spec §3c; `fabrik_synced_manifest.py:29-30`, `watch_enforcement_changes.sh:49-50`, git `55a53b9a` "retired Kilo/Cascade triad".
- Flywheel host-less DSN: spec §4 (`SUBAGENT_RUNS_DSN=postgresql:///fabrik_analytics`, `rank_task_subagents.py:213`/`:216` fail-open, `:187-191` sudo-psql).

## Self-audit

### Grounding passes run
- Solo (this turn), inheriting the CONVERGED spec (5-pass /fabrik-spec-review, same session). Re-confirmed live: `select.py:479-483`, ACTIVE-packs (24), `ai-model-catalog` tree + `compose.yaml` worker service, engine file counts.

### (a) Coverage — every "What we already agreed" mapped
- Move engine → ai-model-catalog (spec Goal) → Phases B (copy) + D (cutover) + E (excise/deploy).
- Don't break fabrik/fleet (constraint 1/2) → Phase A golden + C parallel-run + D fail-open verification.
- No functionality lost (constraint 3) → Phase A/B **structural** parity + Phase C's same-instant byte diff.
- Zero residue (constraint 4) → Phase E excise + pre-delete grep + sync-manifest purge.
- Option A / tenant-zero / produce→deliver→sync (D1) → Phase C deliver bridge + D (fabrik keeps sync).
- Flywheel read-only DSN (D2) → **SUPERSEDED by D5 (2026-08-12)**: the probe was run and found no network-reachable instance; the flywheel does not move and the read is unchanged. E.4 retired.
- Fold dead-residue purge (D3) → Phase E.2.
- Single plan, review per boundary (D4) → this plan, `/fabrik-review` in every phase's closing.
- Catalog store → **Postgres** (operator 2026-08-12) → Global Constraints + **B.2g**. *(B.4 is deleted; the old "SQLite stays / engine=worker" mapping is superseded.)*

### (b) Cross-phase signature consistency
- `capture_golden.GOLDEN_DIR` (A) ← consumed by `test_parity_vs_fabrik_golden` (B) + `test_parallel_run_diff` (C). ⚠️ **The old "Names match" was FALSE** — the Interfaces block promised `assert_parity()` and a sha256 manifest, neither of which exists. Corrected there; the real shared surface is `structure.json` + `capture_golden`'s shape extractors.
- `engine/out/**` — file producers write `engine/out/<fabrik-relative>` (two sub-classes per B.2e: `FABRIK_ROOT`-repoint for `rank_*`/`generate_model_capabilities`; explicit `--output` for `export_traycer_registry`/`export_models_browser`), injectors emit `engine/out/blocks/*.txt`, plus `engine/out/kilo_agents.db` (F1) → `deliver_to_fabrik.py` copies the file artifacts, marker-injects the blocks, and copies the DB to fabrik (C consumes). Match.
- **Engine outputs vs retained-consumer outputs (F2):** the engine produces the selection docs, marker blocks, `kilo_47_agents_final.json`, `KILO_MODEL_CAPABILITIES.md`, `models_browser.html`, `kilo_agents.db`. `docs/CAPABILITIES.md`/`capabilities.json`/`llms.txt` are `generate_capability_index.py` outputs (retained fabrik consumer, Phase D) — NOT engine outputs, NOT in the golden, NOT delivered (would collide with the live local producer). Consistent A↔B↔C↔D.
- `OUTPUT_ROOT` env (B.2e introduces, default `ENGINE_ROOT/out`, decouples writes from `SCRIPT_DIR.parent.parent` so producers never clobber the scaffold's own `.windsurf/rules/ai`; the two `--output`-driven producers get the flag from `daily_refresh.sh`) → the golden (A) captures the same relative artifacts + marker-block bodies the producers emit. Match.
- ~~`FLYWHEEL_DSN` env (B.2 introduces) → provisioned real (E.4). Match.~~ ⛔ **VOID (pass 7): neither end exists.** B.2c is `SUPERSEDED BY D5 — DO NOT REWRITE THE FLYWHEEL READ`, and E.4 is `⛔ RETIRED`. A self-audit certifying a producer/consumer pair where both ends were retired is worse than a missing row.

Fixed-point claim: this plan carries the full grounding a fresh executor needs; `/fabrik-plan-review` re-ground every `path:line` (incl. the B.2e OUTPUT-decoupling defect), and a follow-up `/fabrik-review` native-Opus pass caught + fixed the artifact-attribution defects (F2 `CAPABILITIES.*` misattribution, F1 retained-consumer `kilo_agents.db` delete-break, F3 `--output`-driven producers, F4 deliver-injection test, F5 12F-XI stdout, F6 golden artifact, F7 test count).

## Residual unknowns

### Resolved during drafting
1. **Engine target dir** — `engine/` in ai-model-catalog. **REASON CORRECTED 2026-08-12:** not "the scaffold's `worker` service hosts it" (that service is the retired container). Under WSL-only **no build context binds the engine at all**, so a top-level `engine/` is correct and keeps the 101-script flat tree out of the scaffold's `server/src/ai_model_catalog` package namespace. The later VPS spec re-decides. RESOLVED.
2. **SQLite vs Postgres** — CHANGED 2026-08-12 (operator, spec §7): **consolidated into Postgres in the new repo.** RESOLVED the other way; see Global Constraints.
3. **Deliver mechanism** — reuse `_atomic_copy` from `sync_enforcement`. RESOLVED.

### Still-open (each self-service)
1. **[SELF-SERVICE — Phase B.2]** Exact set of `/opt/fabrik` string literals to rewrite. Resolution: `test_no_fabrik_paths.py`'s grep enumerates them; fix each; the test gates it. No stop.
2. **RESOLVED 2026-08-12 — no longer a residual.** The flywheel's physical host was PROBED and recorded in spec §4 (WSL local socket, `listen_addresses=localhost`, not on `postgres-main`, box not on the WireGuard mesh). E.4 is retired. Original text: ~~[SELF-SERVICE — Phase E.4] … Resolution:~~ `psql "$SUBAGENT_RUNS_DSN" -c '\conninfo'` on the hub — a one-command probe, executor runs it. Fail-open covers a miss.
3. **[SELF-SERVICE — Phase E]** Whether any /opt project (beyond fabrik) imports the engine directly. Resolution: E.1's fleet-wide grep; extend the delete-guard to any hit. No stop.

## Pass Ledger (`/fabrik-plan-review`)

The loop terminates only on a pass with `edits: 0` **and** `md5(start) == md5(end)`. Recorded here because a
review that lives only in chat is not a review — and because the header spent three passes asserting a
convergence it never had.

| Pass | scope re-grounded | raised | new: | edits | plan md5 (start → end) |
|-----:|---|---:|---:|---:|---|
| 1–3 | pre-2026-08-15 rounds. ⚠️ The `dc3eddf8…` no-op these claimed was **not reproducible** — treat as unverified | — | — | — | not recorded |
| 4 | C/D grounders + orchestrator re-verify (C-B1…C-B4, D-B1…D-B5) | 9 | 9 | 9 | → `46361555…` |
| 5 | closing full read; A/C/D by orchestrator, B + E by two independent Opus grounders | 43 | 43 | 43 | `46361555…` → (edited) |
| 6 | **EXECUTION-GROUNDED**, scoped to D+E: every gate RUN; pool breadth (3 models) + native Opus | 11 | 11 | 11 | `63cc676b…` → `6f5f5625…` |
| 7 | **closing full read** (all 1,178 lines, nothing skimmed) + orchestrator fold-in | 30 | 30 | **35 step-body edits** | `4cb61ca9…` → (edited) |
| 8 | verification of pass 7's 35 edits; every rewritten gate RUN | 13 | 13 | 1 (the gate that mandated the P6-1 regression) | `9cff3f01…` → (edited) |
| 9 | **STRUCTURAL REWRITE of D+E** — 483 lines/39 markers/76 blocker refs → 227/8/0; record moved to an appendix | — | — | whole-section | → `b3db651e…` |

⚠️ **Rebuilt in pass 7.** The previous table had a six-cell row against a four-column header, listed pass 6
before pass 5, left an md5 as the prose placeholder "(non-identical — pass 6 owed)", and had an unexplained
gap between pass 5's end and pass 6's start — so its own termination condition (`md5(start) == md5(end)`) was
unauditable from it.

**Pass 7 — the DIAGNOSIS, and it indicts every pass including mine.** An independent closing read of all 1,178
lines found 30 more and named the structural cause: *"pass 6 changed the METHOD (run the gates) but not the
DELIVERABLE — it appended eleven correct findings and edited ZERO of the eleven step bodies they indict. Every
prior pass did the same. The plan is now a document in which the blocker blocks are more accurate than the
steps, and the executor reads the steps."* That is exactly right, and it explains why six passes kept finding
things: **recording a defect was being mistaken for fixing it.** Pass 7 therefore made **35 step-body edits** —
the data-destroying `cache/` gate, the E.2 delete list, the char class that let a gate pass with its own
blocker present, the fleet smoke that could not fail, the freshness gate measuring the wrong thing on a 90-day
threshold, the Interfaces contract promising a function that does not exist, the A.1 floors that passed with
12 of 18 markers gone, the retained remnant missing seven files, four surviving "byte-identical" claims, the
stale Handoff, and the Converged field. **The blocker blocks stay as the record; the STEPS are now the
corrected artifact.**

**Pass 6 — the method changed, and it is the finding.** Four prose passes shipped 74 wrong claims;
pass 6 RAN the gates instead and found 11 more in the two phases that have not executed — including
that **E.2 as written deletes live fleet-synced governance with no failing check anywhere** (P6-1),
that **two D gates cannot fail** (P6-3, P6-4, each proven by constructing the failure they exist to
catch), and that one of my OWN pass-5 findings was wrong (**E-B5 REFUTED**, P6-2). ⚠️ The pool
breadth layer (3 models) returned almost entirely RESTATEMENTS of the blocker blocks already written
into the plan — scored 2-3/5. That is a method lesson worth keeping: **once a plan contains its own
defect list, prose review summarises it back instead of finding anything new.** Every genuinely new
pass-6 finding came from executing a command. Probe duty: the plan embeds **0** runnable probes
(`$ `-prefixed fences) across ~600 lines — which is precisely why 74 claims could be wrong and look
right.

**Pass 5 total: 43 findings** — 10 orchestrator (below), 11 Phase B (**B-B1…B-B11**), 20 Phase E
(**E-B1…E-B20**), plus 2 sub-claims refuted inside otherwise-correct findings. Running total across passes
2–5: **74** wrong or drifted claims. The distribution is the lesson: **every single one required opening a
file or running a command** — the plan reads impeccably and was wrong 74 times.

⚠️ **The four that would have caused real damage, all found in this pass:** `B-B1` (two producers write to
`/opt/docs/`, outside both repos — a HARD STOP, armed but not yet fired), `B-B4` (a gate whose literal
execution deletes the hand-maintained data the previous sentence protects), `E-B1` (E.2 orphans five live
callers under the retained boot hook, every failure swallowed, with the alerting script itself deleted), and
`E-B12` (a false piece of evidence whose "obvious fix" would `git rm` the live `process_monitor.py`).

**Pass-5 findings (orchestrator half, each verified by opening the file or running the command):**

| # | Finding | Verdict |
|---|---|---|
| A-B1 | A.1/A.2/B.3 gate on `golden/manifest.json`, `blocks/`, sha256 byte-identity and `test_selection_docs_match_current` — **none exist**; the real oracle is `structure.json` (`capture_golden.py:50`) | CONFIRMED — CRITICAL, blocks B.3 |
| D-B6 | `pick_models('code')[:3]` returns **one** model (`select.py:430-432`, `n: int = 1`); the flagship gate calls it a top-3 and cannot see a `_TABLE` fallback | CONFIRMED |
| P5-1 | `PACK_TO_CATEGORY` is at `update_gateway_counts.py:260/:275`, **not** `category_export_markdown.py:303`; the two injectors do not share a host-discovery mechanism | CONFIRMED |
| P5-2 | C-B4 ("rule-6 carve-out incomplete") was **my own false finding** — all three modules are carved out at `:155`, `:334`, `:386` | **REFUTED** |
| P5-3 | "56 vendored copies" (2 sites) — live count **48**, repo canonical 49; D-B5 recorded it but never fixed the sites | CONFIRMED |
| P5-4 | Header + Handoff asserted `CONVERGED` / an md5-verified no-op that never happened | CONFIRMED |
| P5-5 | No Pass Ledger existed at all — hence this section | CONFIRMED |
| P5-7 | `_atomic_copy` is `sync_enforcement_to_projects.py:279`, cited as `:278` in 4 places | CONFIRMED |
| P5-9 | Global Constraints' 12-Factor bullet still answered X and XII with "n/a — SQLite", which B.2g superseded — the last site asserting the retired store decision | CONFIRMED |
| P5-10 | § Evidence still recorded `98 .py + 50 tests = 64`; live is `101 + 55` → **67**, matching Phase B. The plan's grounding record was the stale one | CONFIRMED |

Re-verified and **held** from pass 4: C-B1 (lockfile byte-identical at `:125-131` in both engines), C-B2 (two
different 7-packs; 3 of 11 `ai/*.md` carry neither marker), C-B3 (the `^/opt/fabrik` anchor is escapable —
proved with a 2-line fixture), D-B1 (57 grep hits, **55** real invocations, comments at `:364`/`:527`, and
`label` really is in the `sort -u` output), D-B2 (`wsl_startup_hook.sh:236` is the second caller), D-B3
(`tests/golden/` holds exactly `db_queries.json` + `structure.json`; no `pick_models` baseline anywhere).

## Handoff

**Next (user-triggered):** `/fabrik-execute-plan docs/development/plans/2026-07-26-plan-1-ai-model-catalog-extraction.md`. ⚠️ **STATE, refreshed pass 7 (the old text said "B in progress" and never mentioned C):** Phase A `✅ EXECUTED`, Phase B `✅ EXECUTED`, Phase C `🟡 CODE COMPLETE — window OPEN`, Phases D+E **unexecuted**. **The one live gate is C.2's ≥7-day parallel-run window; Phase D is gated on it by design** and cutting over early discards the safety property it exists to establish. Before D runs: A-B1 ✅ fixed, C-B1 ✅ fixed, B-B9 (`CATALOG_DSN` unprovisioned) still open, and E.2 must not run until P6-1's KEEP decision is reflected in whatever tooling executes the deletes. ⚠️ **The plan is NOT `CONVERGED`** — this line's earlier "re-grounded to an md5-verified no-op" claim was false (see § Pass Ledger). Execution has begun anyway under operator direction (Phases A ✅, B in progress); the **blockers block at Phase D's head is binding** — A-B1 must be resolved before B.3, C-B1 before C.2, and E.2 must not run until C1/C2/C3 are scheduled. E.4 is retired (D5).
**💡 fabrik-lib candidates:** none — the deliver step reuses `sync_enforcement`'s copy pattern; the engine is project-local.

---

## Plan reconciliation (2026-08-12)

A sibling plan SET — now at
`docs/development/plans/archived/2026-08-12-plan-1-catalog-extraction-fabrik-prep/` (5 tickets, **SUPERSEDED,
archived unexecuted 2026-08-12**) — was authored before this plan was re-reviewed, and overlapped it:

| Sibling ticket | Overlap with this plan | Disposition |
|---|---|---|
| T01 golden-file oracle | **Duplicates Phase A.1–A.3, less well.** This plan's A.1 already carries the whole-file vs marker-body split, the `EMBEDDING_CATALOG` strip, the `EMBEDDING_WINNERS`/`ROSTER` hosts, the 6-doc `*_SELECTION.md` scoping and the `db_queries.json` capture — every fix an independent review had to add back to T01. | **This plan wins; retire T01.** |
| T02 import-graph audit | Duplicates E.1's audit, which is the original and carries all 7 classification rules. | **This plan wins; retire T02.** |
| T03 flywheel safety gates | **No counterpart here** until A.0 above. | Either source is fine — **run once**. |
| T04 shared cost-JSON relocation | Duplicates E.1 rule 7 (`claude_p_cost.json` / `claude_price_ratios.json`). | **This plan wins; retire T04.** |
| T05 integration receipts | Set-shape ceremony; this monolith uses per-phase closings instead. | Retire with the set. |

**ACTIONED 2026-08-12 (operator-directed):** the sibling set was marked `Status: SUPERSEDED` and archived as a
whole directory (spine + all 5 tickets travel together, per the plan-lifecycle rule). It is SUPERSEDED, not
EXECUTED — no ticket ran, no commit carries an `Agent-Task` trailer for it, and its Board is entirely ⬜.
T03's three gates live on here as **A.0**. This plan is now the single artifact for the migration.


---

## Appendix — Review Record (passes 2–8, verbatim)

**This is HISTORY, not instructions.** It is the accreted D+E text as it stood before the pass-9
rewrite: 483 lines, 39 warning markers, 76 blocker references. Every verified finding in it has
been folded into the rewritten Phases D and E above, stated once. It is kept because the findings
are the record of what was wrong and why — but **an executor must read the phases, never this.**
The reason this appendix exists at all is the pass-8 diagnosis: with ~40 blocker blocks interleaved
among the steps, every correction had forty neighbours to reconcile, so passes 6, 7 and 8 each left
the STEP asserting what its own BLOCKER refuted. Separating the record from the artifact is the fix.

<details>
<summary>Expand the pre-rewrite D+E (483 lines)</summary>

## Phase D — Cutover · runs in `/opt/fabrik`

**Deliverable:** fabrik's `daily_refresh` **stops running engine steps**; the external engine (delivering live) is the sole producer; fabrik keeps `generate_kilo_agents` + `generate_capability_index` + `sync_enforcement`. The vendored `_TABLE` floor stays as the seatbelt.

**Files (MODIFY, fabrik):**
- MODIFY `scripts/kilo-benchmarks/daily_refresh.sh` — remove the ENGINE steps (spec §3 liveness inventory); keep the CONSUMER steps: `deliver` (or fetch) → `generate_kilo_agents` → `generate_capability_index` → `sync_enforcement_to_projects`.
- MODIFY `scripts/generate_kilo_agents.py` (#9 — CRITICAL, retained consumer with a hidden engine-script dependency): **strip the `if not args.dry_run:` "Auto-update docs" block (`:952-972`)** that `importlib.exec_module`s `kilo-benchmarks/generate_selection_guide_roster.py` + `generate_model_capabilities.py` — those two ENGINE scripts are deleted in Phase E, so on the live (non-dry-run) path (`daily_refresh.sh:275`) both imports would raise → the `except` at `:970` swallows it to a silent `[warn]` and roster + model-capabilities regeneration silently STOPS. The **Phase-C deliver step now owns** roster + capabilities injection (it delivers `KILO_MODEL_CAPABILITIES.md` + injects the ROSTER/EMBEDDING blocks), so this block is redundant — remove it, leaving `generate_kilo_agents` reading only the delivered `kilo_agents.db`. This also resolves the ownership overlap the deliver step exposed.
- MODIFY `scripts/wsl_startup_hook.sh` — same engine-step removal from its boot block.

### Interfaces
**Consumes:** the delivered artifacts (Phase C, now to fabrik's live paths). **Produces (for Phase E):** a fabrik `daily_refresh` with no local engine.

### Steps
⚠️⚠️ **PHASE A/C/D BLOCKERS — pass-4 and pass-5 grounding, 2026-08-15, each re-verified by the orchestrator.**

**A-B1 — ⛔ THE GOLDEN ORACLE A.1/A.2/B.3 ARE WRITTEN AGAINST DOES NOT EXIST (pass 5, CRITICAL — it blocks
B.3, the flagship of the phase now executing).** The 2026-08-12 blockquote above replaced byte-identity with
STRUCTURAL equivalence and the code followed it — `capture_golden.py:50` defines `MANIFEST = GOLDEN_DIR /
"structure.json"`, and the live `tests/golden/` holds exactly **two** files, `structure.json` and
`db_queries.json`. But the surrounding step text was never rewritten, so the plan still gates on the
superseded mechanism:
- **A.1 step 3's gate opens `golden/manifest.json`** → `FileNotFoundError`. It never existed and nothing
  writes it. Its assertions are keyed to a `{path: sha256}` map: `len(m)>=12` (real `structure.json` has **4**
  top-level keys — `artifacts`, `db_queries`, `markers`, `oracle_version`), `sum(… 'blocks/' in k)>=6` (**no**
  key contains `blocks/`; no `blocks/` dir was ever captured). ✅ **The GOOD news, and the reason the fix is
  cheap:** the marker inventory *does* exist, under a different shape — `structure.json["markers"]` holds **18**
  `<host>::<MARKER>` keys, and `["artifacts"]` holds **13**. Measured 2026-08-15, and it independently
  re-confirms C-B2 exactly: OPENROUTER_ROUTES on `{10,20,30,40,50,60,90}` and GATEWAY_COUNTS on
  `{00,10,20,30,40,50,60}` = 14 pack markers, plus `ROSTER`, `EMBEDDING_ROSTER`, `EMBEDDING_CATALOG` and
  `65-rag-search.md::EMBEDDING_WINNERS`. So the oracle is real and well-shaped; only the plan's *gate text*
  was written against the retired mechanism.
- **A.2 step 1 names `test_selection_docs_match_current`** — grep-verified **absent** from
  `test_golden_parity.py`. The real tests are structural (`test_structure_survives_a_real_daily_regeneration`,
  `test_gutted_tables_are_drift_even_with_perfect_structure`, …).
- **B.3 step 3 diffs `engine/out/**` vs `golden/**` "by sha256", split into whole-file goldens and
  block-body goldens.** Neither class is on disk. **Phase B's parity oracle has nothing to compare against.**
⚠️ **Phase A is marked ✅ EXECUTED with both of its gates in this state** — which is the point: a gate that
cannot run also cannot fail, so it certified nothing. **The danger is the plausible "fix":** regenerating
goldens from the RELOCATED engine and diffing them against itself, which makes the oracle self-certifying and
silently retires behavior 2. **Required before B.3 runs:** rewrite A.1/A.2/B.3 to gate on `structure.json` +
`db_queries.json` (the oracle that actually exists), and get byte-equality where the blockquote already put
it — Phase C's same-moment parallel-run diff, the only comparison meaningful for churning data.

**C-B1 — the parallel-run proof is ALREADY defeated, in the copied file.** `/opt/ai-model-catalog/engine/daily_refresh.sh`
carries the guard BYTE-IDENTICALLY at the same lines as fabrik's (`LOCK_FILE="/tmp/.fabrik_daily_$(date
-u +%Y%m%d)"` :125, `exit 0` :129). Both engines contend on ONE lockfile on ONE box, so C.2 can go green
with the relocated engine never executing a single step. S1d predicted the hazard; it is now shipped.
Fix in B/C before C.2 runs, or the whole safety window proves nothing. *(Cite corrected: the guard is at
:125-131, not :92-96.)*

**C-B2 — the marker host sets are two DIFFERENT 7-packs, not one.** OPENROUTER_ROUTES = {10,20,30,40,50,
60,**90**}; GATEWAY_COUNTS = {**00**,10,20,30,40,50,60}. Union = 8 packs → **14** block files. Three of
the 11 `ai/*.md` packs carry NEITHER marker, so the literal glob over-reaches by 3. And
`category_export_markdown.py` has no `PACK_TO_CATEGORY`/`RULES_DIR`/`glob` at all — its hosts come from
`ai_category_configs.yaml` (`CONFIG_PATH:57`), so a path-grep enumerates nothing.

**C-B3 — C.1's safety gate is VACUOUS.** `--dry-run | grep -c "^/opt/fabrik"` anchors at column 0; any
action-verb prefix (`COPY /opt/fabrik/… → …`) makes it pass regardless. The assertion protecting the
CORE pack `65-rag-search.md` cannot fail as written.

**C-B4 — ❌ REFUTED in pass 5 (this was MY OWN false finding; kept visible rather than deleted).** I claimed
the rule-6 carve-out covered only `db_models`. It covers all three. Re-verified 2026-08-15: the modules
`classify_ticket.py` / `db_models.py` / `kilo_telemetry.py` are named together in the B.1 rsync excludes
(`:155`), in the Files DELETE **exception** list (`:334`), and in E.1's expected `RULE-6 DEP` output (`:386`).
The live import shape is confirmed — `kilo_auto_route.py:56` `sys.path.insert`s, then imports `classify_ticket`
(`:58`), `db_models` (`:59-62`), `kilo_telemetry` (`:63-67`) — but every one of them is already retained. **No
action; the carve-out is complete.** Recorded because a review that only ever confirms its own findings is not
a review.

**D-B1 — D.1's gate CANNOT PASS, even after a perfect surgery.** The comment at `daily_refresh.sh:527`
contains the literal `_step "label"`, and `grep -hoE '_step "[a-z_0-9]+"'` extracts it — `label` is not
in the allow-list, so the gate reds on prose. Verified: `label` is in today's `sort -u` output.

**D-B2 — `check_daily_refresh_freshness` HAS a second caller.** The plan says deleting it leaves "no
orphan, no carve-out". `wsl_startup_hook.sh:236` invokes it by absolute path. The prose licenses a
deletion that orphans a live call.

**D-B3 — D.2's pre-cutover baseline DOES NOT EXIST.** `tests/golden/` holds exactly two files
(`db_queries.json`, `structure.json`); neither records a `pick_models` top-3. D.2's flagship assertion
has nothing to compare against, and no phase creates it.

**D-B4 — the step enumeration misses 12 engine steps**, including all seven `rank_*` (among them
`rank_task_subagents`, which produces the very `TASK_SUBAGENT_SELECTION.md` D.2 certifies) and
`update_gateway_counts` (one of Phase C's four named injectors).

**D-B5 — "56 vendored copies" is wrong twice.** Measured today: **48**. The repo's canonical figure
everywhere else (daily_refresh.sh:456, rank_task_subagents.py:1373, the design spec) is 49; the plan is
the only artifact saying 56.

⚠️⚠️⚠️ **PASS-6 — EXECUTION-GROUNDED (every gate below was RUN against the live tree, 2026-08-15).
Four prose passes reviewed these two phases and shipped 74 wrong claims; this pass ran the commands
instead. It refutes one of my own recorded findings and finds that E.2 as written DELETES LIVE
FLEET-SYNCED GOVERNANCE.**

**P6-1 — ⛔ E.2 DELETES LIVE FLEET GOVERNANCE, and BOTH consumers skip it SILENTLY.**
`scripts/kilo_code_review.py` and `kilo_docs_enforcer.py` are **not Kilo residue** — they are live
synced surfaces on **eight** of them: `fabrik_synced_manifest.py:29` CORE_SCRIPTS ·
`.pre-commit-config.yaml:65` governance-sync filter · `sync_enforcement_to_projects.py:5` ·
`watch_enforcement_changes.sh:49` · `src/fabrik/scaffold.py:1017` · the fleet-synced rule pack
`.windsurf/rules/core/50-code-review.md:75,87` · `templates/saas-skeleton/AGENTS.md:101` ·
`templates/scaffold/gitignore-synced-block.txt:30`. **48 projects hold a copy today.** And nothing
turns red: `sync_enforcement_to_projects.py:405` copies CORE_SCRIPTS under `if source.exists():` —
a **silent skip** — and orphan pruning exists only for `VENDORED_DIRS` and the enforcement dir
(`:457-495`), never for CORE_SCRIPTS. `scaffold.py:1025` has the same silent `.exists()` guard, so
new projects would ship without Step-3/Step-4 tooling; no scaffold test asserts otherwise. After
E.2, **48 repos keep a zombie copy the hub no longer owns, forever, with no failing check anywhere.**
`CHANGELOG.md:15311` records that their previous ABSENCE from CORE_SCRIPTS already broke all 38
child projects once. ✅ **DECIDED 2026-08-15 (not deferred — the evidence settles it): these two are outside this
plan's blast radius. They are KEPT, and they have been CUT from E.2(ii)'s `git rm` and from the
Files DELETE list below.**

**P6-2 — ❌ E-B5 REFUTED (my own finding, wrong).** I recorded that `wsl_startup_hook.sh`'s 18
`*_SCRIPT=` assignments were "dead, uses=0". That was a grep artifact. Direct proof:
`grep -nF '$DB_SCRIPT'` → `:150`; `$EMBEDDING_DB_SCRIPT` → `:161`; `$AA_SCRAPER_SCRIPT` → `:152`;
`$AI_PACK_FRESHNESS_SCRIPT` → `:213`. **All 19 are USED** (`:150-154`, `:161-163`, `:188-211`). The
hook is a full second engine pipeline, not a husk — acting on E-B5 ("leave them, they're dead")
ships a boot pipeline invoking 19 deleted scripts. **C2 is also half-wrong:** Phase **D** does own
the hook (D's Files list). What is true is that **D.1's scope is under-sized** — it says "~9 engine
scripts at `:36-44`"; the real figure is **19 variable-invoked + 5 more by absolute path**
(`:130/:233/:235` `pipeline_alert.sh`, `:232` `rank_task_subagents.py`, `:234`
`tests/capture_golden.py`, `:236` `check_daily_refresh_freshness.py`, `:243`
`autocommit_pipeline_outputs.sh`), every one swallowed by `>> $LOG_FILE 2>&1 || {…}`.

**P6-3 — 🔴 D.1 gate (ii) FAILS OPEN on the exact C3 blocker.** The char class
`[A-Za-z_0-9.-]` excludes `/`, so **every subdirectory script collapses to its directory name**:
`$KB/tests/capture_golden.py` renders as **`$KB/tests`**, which the gate's own Expected text lists
as a retained remnant. The gate goes green with C3 fully present. Same for the two engine `.sh`
files, which the Expected sentence ("any `.py` engine script here must be removed") textually
exempts. 84 hits measured.

**P6-4 — 🔴 D.2 step 4's fleet smoke CANNOT FAIL, proven by construction.**
`libs/subagents/select.py:357-359` — `_HUB_SELECTION_DOC` wins **whenever `/opt/fabrik` exists on
the box**; the project-relative copy (`:361`) is only consulted if it does not. Built the failure it
exists to catch (a fake project whose vendored doc was husked to `BROKEN/sync-failed-model`):
hub present → the correct hub top-3 (**GREEN, wrong**); hub hidden → `['BROKEN/sync-failed-model']`
(the truth). **The gate whose stated purpose is proving the sync actually delivered to a consumer
reading its OWN copy is structurally blind to a total delivery break, on the only box it will run
on.** Behavior 1's flagship fleet clause is unprovable as written.

**P6-5 — 🔴 D.2 step 3 measures the wrong thing and cannot fail.**
`check_ai_pack_freshness.py:7` says in its own docstring *"Exit 0 always — a freshness signal, NOT a
gate"*; every `main()` return is 0. It reads `.windsurf/rules/ai/*.md` hand-written
`Last content verification:` stamps, **not delivered-doc mtimes**, with a **90-day** threshold
(`AI_PACK_STALE_DAYS:27`), not 24h — and it already emits 3 warnings today. Cite corrected: it runs
at `wsl_startup_hook.sh:213`, not `:164`. **Post-cutover there is NO gate on delivered-doc freshness
at all.**

**P6-6 — 🔴 E.1's retained-consumer gate (iii) cannot run, and its "or equiv" is DESTRUCTIVE.**
`python scripts/generate_kilo_agents.py --out /tmp/gka-smoke` → `error: unrecognized arguments`,
exit 2. The argparse accepts only `-h` and `-d/--dry-run` (`:945-949`); `OUTPUT_DIR` is hard-coded to
`Path.home()/".traycer"/"cli-agents"` (`:40`) and the non-dry-run path does `shutil.rmtree(OUTPUT_DIR)`
(`:875`). So "(or equiv)" means **wiping the operator's live Traycer agent dir** — there is no
sandbox. And even if run, the failure it targets prints `[warn] Could not update` to stdout with
**exit 0** (`:970-971`), so an exit-code gate cannot fail; it needs a stdout grep the plan omits.

**P6-7 — 🔴 E.1's residue gate STRUCTURALLY CONTRADICTS rule 1, permanently.**
`rank_coding_subagents.py:392` emits `**Generator:** \`scripts/kilo-benchmarks/rank_coding_subagents.py\``
into the delivered docs, so the relocated engine **re-injects the forbidden string every day** into
five rule-1 KEEP artifacts. The gate and rule 1 cannot both be satisfied until the header emitter is
repointed — **a change no phase owns.** (Plus E-B4 re-confirmed: 408 matches, **340** inside
`.claude/worktrees/` across 5 live sibling worktrees; 28 real.)

**P6-8 — E.1's audit script: its ACTUAL output contradicts the plan's "Expected" AND the plan's own
✅ "Verified-good" claim.** Run verbatim it prints **5** `RULE-6 DEP` lines — the three carved-out
modules *plus* `generate_model_capabilities.py` and `generate_selection_guide_roster.py`. The plan
says "Expected: every printed RULE-6 DEP is in the carve-out" and its stop-rule says any that is not
"= an unhandled orphan → fix it before E.2" — so an executor is instructed to **carve out two engine
scripts Phase E exists to delete**. (They are handled, by D.1's `importlib`-block strip; nothing in
E.1 says so.) Its ENTRY-derivation command also **crashes the tool**: 19 of 21 paths it emits are
other repos' (`/scripts/wip_backup.sh` → `FileNotFoundError`, no existence guard), and it misses the
plan's own `0 6 * * *` cron because the char class has no `/`.

**P6-9 — E.2 gate (a) never prints `0` and `set -e`-ABORTS exactly when it passes.** `grep -rc` over
two files always prints `file:count` per file (measured: `2` and `1`), and on the clean case exits
**1**, killing the script on success. Coverage it never sees: `watch_enforcement_changes.sh:49-50`
(in MODIFY, in no gate), `src/fabrik/scaffold.py:1017-1018` (in **no** plan list),
`.windsurf/rules/core/50-code-review.md:75,87`, and two `templates/` files.

**P6-10 — C3 extends further than recorded.** The same `git rm -r` also deletes
`tests/test_golden_parity.py` and `tests/test_parallel_run_diff.py` — the plan's **own Phase-A and
Phase-C oracles**, named in File Scope as owned paths. After E.2 the retained `tests/golden/**` has
**zero readers**: no `--verify`, no parity test, no diff test.

**P6-11 — C1 ANSWERED with evidence (the plan says "decide it HERE"; here is the decision).**
`derive_cost.py` is **dead outside the engine** (only engine-internal importers; `claude_p_cost.py:9-12`
deliberately keeps a standalone copy rather than importing it) → **co-delete
`tests/test_derive_cost_by_family.py`**. `kilo_dispatch.py`'s shell callers all die with it → **co-delete
`tests/test_kilo_dispatch.py`**, but E.2 must ALSO purge the **1** fleet-synced workflow that invokes it — `.windsurf/workflows/kilo.md` (⚠️ pass 7 correction: **6** was the union across ALL dead scripts, and 3 of those 6 reference `kilo_code_review`, now KEPT — purging all six would break live governance) or the dangling
refs propagate fleet-wide. `kilo_code_review.py` is **LIVE** (P6-1) → **KEEP the module**, and with it
`tests/test_kilo_review_validation.py` + `tests/test_kilo_strictness_scenarios.py`. All four tests
collect and pass today (105 passed).

✅ **Ran clean and confirmed accurate:** D.2 step 2's `_TABLE` fail-open (returns a *different*
top-3, so it genuinely discriminates — and this partially refutes **D-B6**, whose fix `n=3` is right
but whose stated reason was overstated); E.1 sub-checks (i)/(ii)/heartbeat/`kilo_auto_route --help`;
E.2 gate (b) as a positive-deletion proof; D.1's arithmetic (57 hits − 2 comments = **55** real, 5
retained → **50** to remove). Cites re-confirmed: `daily_refresh.sh` alerting `:459`/`:514`;
`.pre-commit-config.yaml:65`; 23 `traycer_agents_fixed` files; 6 workflows; **48** vendored copies.

**D.1 — Flip delivery to live paths + shrink daily_refresh (large surgery — **55** real engine `_step`
invocations, of which the allow-list retains 5, so **50** to remove. ⚠️ My own 2026-08-15 correction of
"~40 → 57" was ALSO wrong: `grep -c '_step '` returns 57 but two of those lines are comments (:364,
:527). Measure invocations, not grep hits.).** Point `deliver_to_fabrik.py` at fabrik's real consumed paths; remove **every** engine `_step` from `daily_refresh.sh`/`wsl_startup_hook.sh`. The retained `daily_refresh.sh` is an **allow-list** — it may ONLY keep: the fabrik-infra steps (`gather_envs`, `classify_services`), the new `deliver` (or fetch) step, and the consumer steps (`generate_capability_index`, `generate_kilo_agents`, `sync_enforcement_to_projects`). **`check_daily_refresh_freshness` is DROPPED (#15):** it is a `$KB/` helper reading `kilo-benchmarks/cache/daily_refresh_last_success.txt` (`check_daily_refresh_freshness.py:5`) — the OLD engine-refresh self-check; post-cutover the relevant freshness is the DELIVERED-doc age, already monitored by `check_ai_pack_freshness.py` (D.2.3), so this obsolete helper is deleted with the engine (no orphan, no carve-out). Everything else — all `$KB/`-invoked producers incl. `generate_model_capabilities` (`:242`), `generate_selection_guide_roster` (`:244`), `export_traycer_registry` (`:272`), `export_models_browser` (`:454`), **all SEVEN `rank_*` steps — `rank_task_subagents` (which produces the very `TASK_SUBAGENT_SELECTION.md` D.2 certifies), `rank_coding_subagents`, `rank_stt`, `rank_tts`, `rank_translation`, `rank_image_gen`, `rank_candidate_signups` — ⚠️ added pass 7; D-B4 flagged their absence and the enumeration was never updated**, plus `update_gateway_counts`, and the ~29 `scrape_*`/`migrate_*`/`embedding_*`/`category_*`/`seed_*`/`fetch_*`/`verify_openrouter_catalog`/`discover_*`/`kilo_agents_db`/`role_mapper`/`update_kilo_benchmarks`/`classify_ai_category`/`backfill_*`/`microbench_*`/`restore_*` steps — is removed. **Same removal applies to `scripts/wsl_startup_hook.sh` (#16 — it invokes ~9 engine scripts, `wsl_startup_hook.sh:36-44`: `kilo_agents_db`, `update_kilo_benchmarks`, `scrape_artificial_analysis`, `role_mapper`, `export_traycer_registry`, `embedding_*`).** **Gate — TWO separate checks (one pattern can't cover both idioms; the old mixed grep was unexecutable):**
   - **(i) step allow-list:** `grep -hoE '_step "[a-z_0-9]+"' scripts/kilo-benchmarks/daily_refresh.sh | sort -u` → **Expected:** a subset of `{gather_envs, classify_services, deliver_to_fabrik, generate_capability_index, generate_kilo_agents, sync_enforcement_to_projects}` — any other step name is an engine producer still present. (`deliver_to_fabrik` is the Phase-C script invoked as a `_step` like any other; name it exactly that.)
   - **(ii) engine-script reference check (covers `$KB/` expansion AND literal paths, in BOTH files):** `grep -hoE '(\$KB|\$\{KB\}|scripts/kilo-benchmarks)/[A-Za-z_0-9./-]+' scripts/kilo-benchmarks/daily_refresh.sh scripts/wsl_startup_hook.sh | sort -u`  ⚠️ **`/` ADDED to the char class (P6-3).** Without it every subdirectory script collapsed to its directory name — `$KB/tests/capture_golden.py` rendered as `$KB/tests`, which this gate's own Expected text lists as a RETAINED remnant, so the gate went green with the C3 blocker fully present. The Expected text must also stop saying "any `.py` engine script": the two engine `.sh` files (`pipeline_alert.sh`, `autocommit_pipeline_outputs.sh`) were textually exempted by that wording → **Expected:** only references to the retained remnant (`kilo_agents.db`, `models_browser.html`, `cache/`, `backups/`, `tests/golden/`) — **any `.py` engine script here must be removed.**
**D.2 — Cutover verification (behavior 1 — flagship).**
⚠️ **D-B6 (pass 5) — as written, step 1 compares ONE model and calls it a top-3.** `pick_models` is
`def pick_models(task_type, n: int = 1, …)` (`libs/subagents/select.py:430-432`), so `pick_models('code')[:3]`
returns a **single-element** list — verified live 2026-08-15: `['qwen/qwen3-coder-next']`, versus
`pick_models('code', n=3)` → `['qwen/qwen3-coder-next', 'google/gemini-3-flash-preview', 'openai/gpt-5.6-luna']`.
A 1-element result is also what a **degraded `_TABLE` fallback** can return, so the gate cannot distinguish
healthy from fallen-back — it is the flagship behavior's verification and it is blind to the flagship failure.
**Pass `n=3` explicitly in steps 1 and 4.** Compounding this, D-B3: the baseline it compares against was never
captured, so today step 1 has neither the right arity nor anything to compare to.
1. `python -c "import sys; sys.path.insert(0,'libs'); from subagents.select import pick_models; print(pick_models('code', n=3))"` → **Expected:** same top-3 as the pre-cutover baseline (which **D-B3 says does not exist** — capture it before cutover or this step is unrunnable).
2. Force-remove the selection doc → assert `pick_models('code')` still returns (falls to `_TABLE`), not raises → restore. **Expected:** fail-open holds.
3. ⚠️ **REWRITTEN (P6-5): the old step was wrong three ways and could not fail.** `check_ai_pack_freshness.py` says in its own docstring *"Exit 0 always — a freshness signal, NOT a gate"*; it reads hand-written `Last content verification:` stamps in `.windsurf/rules/ai/*.md` — **not delivered-doc mtimes** — against a **90-day** threshold, not 24h, and it already emits 3 warnings today. It runs at `wsl_startup_hook.sh:213` (not `:164`). **There is currently NO gate on delivered-doc freshness.** Write one: `python -c "import time,pathlib;p=pathlib.Path('docs/reference/kilo/TASK_SUBAGENT_SELECTION.md');assert time.time()-p.stat().st_mtime < 86400, 'delivered doc older than 24h'"` → **Expected:** exit 0.
4. **Fleet smoke — ⚠️ REWRITTEN (P6-4): the old form CANNOT FAIL, proven by construction.** `libs/subagents/select.py:357-359` prefers `_HUB_SELECTION_DOC` **whenever `/opt/fabrik` exists on the box**; the project-relative copy (`:361`) is only consulted if it does not. Measured with a fake project whose vendored doc was husked to `BROKEN/sync-failed-model`: hub present → the correct hub top-3 (**GREEN, from the WRONG file**); hub hidden → `['BROKEN/sync-failed-model']` (the truth). So the gate whose stated purpose is proving the sync delivered to a consumer reading its OWN copy is blind to a total delivery break, on the only box it runs on. **Run it with the hub doc temporarily shadowed** (`SUBAGENT_SELECTION_DOC=<project>/docs/reference/kilo/TASK_SUBAGENT_SELECTION.md`) so the project's own copy is the one read. (Behavior 1 is the FLAGSHIP risk — **48** vendored copies, D-B5 — and steps 1-3 only prove the HUB.) Run `pick_models` from a real **synced project** (not the hub): `cd /opt/<some-project> && python -c "import sys; sys.path.insert(0,'libs'); from subagents.select import pick_models; print(pick_models('code', n=3))"` (⚠️ `n=3` — D-B6) → **Expected:** resolves to the same top-3 as the hub baseline, proving `sync_enforcement_to_projects` actually delivered the selection docs to a consumer that reads its OWN vendored copy. A hub-only check cannot catch a sync-delivery break.
5. Overlap ≥3 days monitoring `pick_models` + the flywheel.
**D.3 — Behavior Contract:** behavior 1 ONLY — both its clauses: fleet resolves post-cutover (D.2.1/D.2.4) **and** the selection-doc-removed `_TABLE` fail-open (D.2.2), which is behavior 1's own second clause. (NOT behavior 5 — that is the *flywheel DSN* fail-open, a different subsystem, owned by E.5.)

**D.closing:** `final_gate --json` (fabrik) → green; `check_doc_sync`; **`/fabrik-review`** on the orchestrator diffs + a live `fanout` smoke → no-op; commit (`Agent-Phase: D`).

---

## Phase E — Excise residue + deploy + finalize the flywheel DSN · both repos

**Deliverable:** the engine + dead Kilo/Cascade scripts are **gone from fabrik** (zero residue). **Deploy is OUT OF SCOPE (D5)** — no `fabrik apply`, no container, no network DSN; the engine keeps running on WSL and the flywheel read is unchanged.

**⚠️ The excise touches a LARGE, interconnected file set — do NOT hand-enumerate it (7 review rounds proved hand-lists keep missing members). E.1 builds an authoritative IMPORT-GRAPH audit (NOT a path-grep — a path-grep misses the `sys.path.insert`+bare-`import` and `importlib.spec_from_file_location`-computed-path idioms that break live consumers silently, e.g. `kilo_auto_route.py:54-62`) + classifies EVERY node by RULE. The grep is a necessary FIRST pass; the import-graph trace is the completeness guarantee.**

**Classification rules (apply to every audited node):**
1. **DELIVERED consumer artifact** → **KEEP**. ⚠️ **ENUMERATION CORRECTED pass 7 — the old list named 9 of the 13 the oracle actually holds, and this rule decides what survives E.2.** The full set, read from `golden/structure.json["artifacts"]`: the **7** `docs/reference/kilo/*_SELECTION.md` + `CANDIDATE_SIGNUPS.md`, `KILO_MODEL_CAPABILITIES.md`, **`docs/traycer/kilo_selected_agents.md`**, `models_browser.html`, `kilo_47_agents_final.json`, **`kilo_embeddings_final.json`**, **`kilo_openrouter_routes_final.json`** — plus `kilo_agents.db`. The four bolded were named nowhere in the plan. **Derive this list from `structure.json` at execution time, never from prose** — it's the engine's *output* delivered to fabrik, not residue.
2. **Retained consumer/orchestrator** (`scripts/kilo-benchmarks/daily_refresh.sh` shrunk, `scripts/kilo-benchmarks/tests/golden/**`, `generate_kilo_agents.py`, `generate_capability_index.py`, `sync_enforcement_to_projects.py`) → **KEEP** (repoint any engine dep — see MODIFY).
3. **Engine code or its tests** (`scripts/kilo-benchmarks/**` scripts, **`tests/kilo_benchmarks/**`** the 14 repo-root engine test files, `scripts/run_kilo_workflow.sh` the engine-workflow wrapper) → **MOVE to the engine in Phase B, then DELETE from fabrik**.
4. **Live doc describing the engine's fabrik location/workflow** → **UPDATE** to "engine lives in ai-model-catalog, output delivered." (Includes `docs/operations/wsl-environment.md`, `docs/workflows/DATA_SYNC_WORKFLOW.md`, `.windsurf/workflows/subagent-runs-flywheel.md`, `.windsurf/rules/ai/00-ai-model-selection.md` — the E.1 audit enumerates the exact set; bare-filename refs are found by the audit, not the prefix gate.)
5. **Historical/archived** (`docs/archive/**`, `docs/superpowers/specs/**`, `scripts/.archive/**`, `CHANGELOG.md`, `LESSONS_LEARNT.md`) → **LEAVE** (history is immutable; behavior-4 grep excludes these).
6. **Retained consumer with an engine-INTERNAL dependency** (the `kilo_auto_route.py` class — a live fabrik runtime consumer that `sys.path.insert`s into `kilo-benchmarks/` and imports engine modules) → **VENDOR the transitive engine-module deps into the retained set** (keep them in fabrik alongside the consumer). **Vendoring is the ONLY valid action here — do NOT relocate such a consumer into the engine** (G5): `coding-auto.sh:32` hard-codes `DISPATCHER="$FABRIK_ROOT/scripts/kilo_auto_route.py"` and `generate_kilo_agents.py:49` installs `coding-auto.sh` into every agent dir as a static helper, and that script exec's this dispatcher by absolute path, so moving it breaks the live Traycer coding-router path (behavior 3). Concretely: `scripts/kilo_auto_route.py` (Traycer coding auto-router, dispatched by `scripts/coding-auto.sh` (`:32` assigns `DISPATCHER`, `:62` execs it), reached via `coding-auto.sh`, which `generate_kilo_agents.py:49` installs as a static helper) imports `classify_ticket`, `db_models`, `kilo_telemetry` from `scripts/kilo-benchmarks/` — those three modules (+ their own transitive kilo-benchmarks deps, traced by the audit) are **RETAINED** (carved out of the delete), so the coding-router still resolves post-excise. Fixed the #9-class break that `sys.path.insert` hid from every grep.
7. **Retained consumer with an engine-resident DATA-FILE dependency** (N2 — the class rule 6 misses, because rule 6 only covers Python *imports*) → **RELOCATE the data file out of the engine tree into the consumer's own dir**, then let the engine keep its own copy. Concretely: `scripts/claude_p_cost.py` — fleet-synced consumer infra that **stays** (its own header, `:9-11`) — resolves `claude_p_cost.json` + `claude_price_ratios.json` via `_find()` (`:50-54`) as `_HERE/<name>` → **fallback** `_HERE/"kilo-benchmarks"/<name>`; **both files exist ONLY at `scripts/kilo-benchmarks/`** (verified), so Phase E's bulk delete removes them and `cached_amortized_per_mtok()` silently fails-soft to the wrong `$0.093/M` anchor (`:97`) **fleet-wide** — a silent wrong-number break, not a crash. **Action: `cp` (NOT `git mv`) — `git add` a COPY at `scripts/{claude_p_cost.json,claude_price_ratios.json}`, leaving the originals in place until Phase E deletes the engine tree.** ⚠️ A bare `mv` **breaks the engine's own readers**, which resolve `_HERE`-relative and would still be running through Phases A–D: `derive_cost.py:23` (`_HERE/"claude_price_ratios.json"`), `:158` (`_HERE/"claude_p_cost.json"`), `rank_task_subagents.py:483` (`Path(__file__).resolve().parent/"claude_p_cost.json"`). The engine's copies travel with it via B.1's rsync (they're `_HERE`-relative, so they keep resolving inside `engine/`); fabrik's new `scripts/` copy becomes `claude_p_cost.py`'s first-choice path (`_find()` `:53`, `_HERE`=`scripts/`) and the ONLY copy after E deletes the engine — refreshed thereafter by the hub-local `python scripts/claude_p_cost.py --refresh` (it reads `~/.claude`, hub-local data, not an engine output). **Gate:** after E.2, `python -c "import json,pathlib;print(json.load(open('scripts/claude_p_cost.json'))['amortized_per_mtok'])"` → **Expected:** the real rate, NOT the `$0.093/M` fail-soft anchor (`claude_p_cost.py:97`). **Sweep verified complete this review** — those two JSONs are the only `kilo-benchmarks/` data files any retained consumer reads (checked all 6 retained entry-points); E.1's rule-7 pass re-proves it at execution.

**Files:**
- DELETE (fabrik): `scripts/kilo-benchmarks/**` **engine SCRIPTS** (rule 3) — **EXCEPT the rule-1/rule-2/rule-6 remnant kept in fabrik:** `kilo_agents.db` (F1), `models_browser.html` (#11), `daily_refresh.sh` (#13, shrunk consumer orchestrator + `0 6 * * *` cron), `tests/golden/**`, ⚠️ **plus SEVEN files added to the remnant in pass 7 (C3 + E-B1 + P6-10 each demanded them and none was ever added): `tests/capture_golden.py` (the oracle `wsl_startup_hook.sh:234` and `daily_refresh.sh` both invoke — without it `tests/golden/**` is retained with ZERO readers), `tests/test_golden_parity.py` + `tests/test_parallel_run_diff.py` (this plan's OWN Phase-A and Phase-C oracles, named as owned paths in File Scope, and C.3 gate (i) invokes one of them post-E), `pipeline_alert.sh`, `check_daily_refresh_freshness.py`, `autocommit_pipeline_outputs.sh` and `rank_task_subagents.py` (all invoked by the RETAINED boot hook at `:130/:232/:233/:234/:235/:236/:243`)**, **and the rule-6 coding-router deps `classify_ticket.py` + `db_models.py` + `kilo_telemetry.py` (+ their transitive `kilo-benchmarks/` imports, traced by E.1's import-graph audit)** — retained because `scripts/kilo_auto_route.py` (a live fabrik runtime consumer, dispatched by `scripts/coding-auto.sh`) `sys.path.insert`s into `kilo-benchmarks/` and imports them (Pass7-finding-1; `kilo_auto_route.py`/`coding-auto.sh` themselves live in `scripts/`, not `kilo-benchmarks/`, so they're already retained). **Also DELETE `tests/kilo_benchmarks/**`** (14 repo-root engine test files, #F1-Pass6 — `pyproject.toml:94 testpaths=["tests"]` collects them, so leaving them errors `final_gate` at collection once the engine scripts are gone; they move to the engine in Phase B) **and `scripts/run_kilo_workflow.sh`** (engine-workflow wrapper referencing 3 deleted scripts, `:25-27`). **Then — a SEPARATE `git rm`, because these live at `scripts/` TOP-LEVEL, not under `kilo-benchmarks/` (N3, verified)** — the dead Kilo/Cascade scripts (spec §3c), each at `scripts/<name>`: ⚠️ **`kilo_docs_enforcer.py` and `kilo_code_review.py`(+`_bckp`) are CUT from this list (P6-1, decided 2026-08-15 — not deferred): they are LIVE fleet-synced governance on eight surfaces with 48 project copies, and BOTH consumers skip silently, so deleting them leaves 48 zombie copies with no failing check. They are outside this plan's blast radius.** Remaining: `kilo_dispatch.py`, `kilo_consult.py`, `kilo_cost_report.py` (flat file — verified; there is no `kilo_cost_report/` package dir), `Local_{Coder,Documentator,Review,Fixer}*.sh`, `kilo_agent_health.sh`, `fix_traycer_agents.py`, `Kilo_Review.sh`, `traycer_agent_review.py`, `mcp_kilo_server.py`. ⚠️ **`process.py`/`process_v2.py` REMOVED from this top-level list in pass 7** — E-B13 named this exact non-fix and it survived two more passes. They exist ONLY under `scripts/kilo-benchmarks/`, i.e. inside deletion (i). And do NOT "fix" this by adding a `scripts/process*.py` glob: that matches the live `scripts/process_monitor.py` (E-B12).
- **CREATE (fabrik): `scripts/kilo-benchmarks/tests/audit_engine_coupling.py`** — the E.1 import-graph + rule-7 data-file audit tool (throwaway; deleted with the engine tree in E.2).
- **CREATE (fabrik): `scripts/claude_p_cost.json` + `scripts/claude_price_ratios.json`** — the **rule-7** relocation (N2): `cp` from `scripts/kilo-benchmarks/` (NOT `git mv` — the engine's `_HERE`-relative readers `derive_cost.py:23/158`, `rank_task_subagents.py:483` must keep resolving through Phases A–D), `git add` both. After E.2 deletes the engine tree these are the ONLY copies, and they are `claude_p_cost.py`'s first-choice path (`_find()` `:53`).
- MODIFY (fabrik): `scripts/fabrik_synced_manifest.py:29-30` + `.pre-commit-config.yaml:57` + `scripts/watch_enforcement_changes.sh:49-50` (drop dead-script patterns); `INDEX.md`/`PORTS.md`/`docs/PROJECT_CATALOG.md`/`docs/README.md`; **`scripts/kilo-benchmarks/daily_refresh.sh`** — the two heartbeat `from alerting import send_alert` calls (**`:459`, `:514`** — ⚠️ was `:511`/`:515`, corrected E-B7) must import from **`libs/alerting`** (fabrik's retained canonical, `libs/alerting/__init__.py`), NOT the deleted vendored `kilo-benchmarks/alerting/` (#F3-Pass6 — else the operator's only cron-skip heartbeat silently goes dark via the `|| true` swallow); **the rule-4 docs** describing the relocated engine (`docs/FEATURES.md:113/121`, `docs/operations/AI_MODELS_BROWSER_OPS.md:7`, `docs/workflows/KILO_BENCHMARK_WORKFLOW.md`, `docs/workflows/KILO_AGENT_MANAGEMENT.md`, `docs/CONFIGURATION.md` daily_refresh refs) → reword to "produced by the ai-model-catalog engine, delivered to fabrik" (E.1's grep enumerates the exact set).

### Steps
**E.1 — Authoritative import-graph audit + classification (the completeness guarantee, behavior 4).** A path-grep alone is NOT sufficient (it misses `sys.path.insert`+bare-import and `importlib`-computed-path — the idioms that silently broke `kilo_auto_route.py`). Two passes: **(a) text sweep** — `grep -rlE "kilo-benchmarks|from alerting import|import alerting|export_models_browser|rank_coding_subagents|classify_ticket|db_models|kilo_telemetry|daily_refresh" /opt/fabrik --include=*.py --include=*.sh --include=*.md | grep -vE "/\.git/|/scripts/kilo-benchmarks/(alerting|specialty_clients|translation_bench|direct_vendor_parsers|web_scrape|libs)/|docs/development/(plans|reviews)/"`; **(b) import-graph trace (the real guarantee) — RUNNABLE, not prose.** Write `scripts/kilo-benchmarks/tests/audit_engine_coupling.py` (a throwaway audit tool, deleted with the engine) implementing exactly this, and run it:
```python
# For each retained fabrik entry-point, AST-walk its transitive local imports and report
# every dependency that resolves inside scripts/kilo-benchmarks/ (the to-be-deleted set).
import ast, sys, pathlib
KB = pathlib.Path("/opt/fabrik/scripts/kilo-benchmarks")
ENTRY = ["scripts/kilo_auto_route.py", "scripts/generate_kilo_agents.py",
         "scripts/generate_capability_index.py", "scripts/sync_enforcement_to_projects.py",
         "scripts/kilo_model_sync.py",   # N1 — LIVE CRON: `59 11 * * * … kilo_model_sync.py --sync`
         "scripts/claude_p_cost.py"]     # N2 — fleet-synced consumer w/ a DATA-FILE dep (rule 7)
# ⚠️ Derive ENTRY from the LIVE crontab + hooks, never from memory:
#   crontab -l | grep -oE '/?scripts/[a-z_0-9-]+\.(py|sh)' | sort -u   →  every scheduled entry point
#   plus scripts/wsl_startup_hook.sh, scripts/coding-auto.sh, scripts/kilo-benchmarks/daily_refresh.sh
def local_imports(p):                      # names imported/invoked by this file
    src = pathlib.Path(p).read_text(encoding="utf-8", errors="replace")
    if not p.endswith(".py"):              # ⚠️ shell entry-points: ast.parse would SyntaxError.
        import re as _re                   # scan for `$KB/x.py` / `kilo-benchmarks/x.py` invocations
        return {m for m in _re.findall(r'(?:\$\{?KB\}?|kilo-benchmarks)/([A-Za-z_0-9]+)\.py', src)}
    t = ast.parse(src)
    out = set()
    for n in ast.walk(t):
        if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module: out.add(n.module.split(".")[0])
        elif isinstance(n, ast.Import):
            for a in n.names: out.add(a.name.split(".")[0])
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.endswith(".py"):
            out.add(n.value[:-3])          # catches importlib.spec_from_file_location("x.py")
    return out
seen, todo, hits = set(), list(ENTRY), []
while todo:
    f = todo.pop()
    if f in seen: continue
    seen.add(f)
    for name in local_imports(f):
        cand = KB / f"{name}.py"
        if cand.exists():                  # a dependency inside the delete set
            hits.append((f, str(cand))); todo.append(str(cand))
for src, dep in sorted(set(hits)): print(f"RULE-6 DEP: {src} -> {dep}")
print(f"total engine deps reachable from retained entry-points: {len(set(d for _, d in hits))}")

# RULE-7 pass — DATA-file deps a retained consumer reads out of the engine tree (N2's class).
import re
for e in ENTRY:                            # any '<name>.json'/'.yaml'/'.txt' literal resolving into KB/
    for lit in re.findall(r'["\']([A-Za-z0-9_.-]+\.(?:json|ya?ml|txt))["\']',
                          pathlib.Path(e).read_text(encoding="utf-8", errors="replace")):
        if (KB / lit).exists(): print(f"RULE-7 DATA DEP: {e} -> {KB/lit}  (relocate out of the engine tree)")
```
**Expected (post-fix):** every printed `RULE-6 DEP` is in the rule-6 carve-out (today: `classify_ticket.py`, `db_models.py`, `kilo_telemetry.py` from `kilo_auto_route.py` — verified self-contained, stdlib-only imports + the retained `kilo_agents.db` at `db_models.py:20`), and every printed **`RULE-7 DATA DEP`** has been relocated per rule 7 (today: `claude_p_cost.json`, `claude_price_ratios.json` → `cp` to `scripts/`, in the Files CREATE list). **Any `RULE-6 DEP` not carved out, or any `RULE-7 DATA DEP` not relocated, = an unhandled orphan → fix it before E.2.** Also shell-side: `grep -nE '\$KB/|kilo-benchmarks/' scripts/kilo-benchmarks/daily_refresh.sh scripts/wsl_startup_hook.sh scripts/coding-auto.sh` → every hit must resolve to a retained-remnant file. Classify every node from (a)+(b) by the 6 rules; every rule-6 dep (like `classify_ticket`/`db_models`/`kilo_telemetry`) is carved out (KEEP), every rule-3 is deleted, every rule-4 doc updated. **Post-classification gate (behavior 4):** after E.2, `grep -rlE "scripts/kilo-benchmarks/[a-z_0-9]+\.py" /opt/fabrik --include=*.py --include=*.sh --include=*.md | grep -vE "/\.git/|docs/archive/|docs/superpowers/specs/|scripts/\.archive/|CHANGELOG\.md|LESSONS_LEARNT\.md|docs/development/|tests/integration/test_routing_failover\.sh|tests/test_docs_updater\.py"` → **Expected: empty** (TWO intentional fixtures, both excluded and never "fixed": `test_routing_failover.sh:49`'s `__does_not_exist__.py` fail-open sentinel, and — ⚠️ **added pass 7** — `tests/test_docs_updater.py:187`, a STRING fixture asserting that cross-repo links do NOT resolve. It was in the 28 real hits and in no exclusion list); AND a positive check that the rule-6 deps resolve: `python scripts/kilo_auto_route.py --help` (or a dry classify) → **Expected:** imports `classify_ticket`/`db_models`/`kilo_telemetry` cleanly (they were carved out). Any unexpected hit = an unhandled node → resolve before claiming behavior 4. **⚠️ The gate is a backstop, not the guarantee — bare-filename doc refs (`wsl-environment.md:80`) escape the prefix pattern; the import-graph audit (b) + the rule-4 doc sweep are what actually close behavior 4.**
**Retained-consumer runtime gate (F1 + #9 — the `--dry-run` probe is NOT enough; the break is on the non-dry-run path):** prove `generate_kilo_agents` runs post-delete on its REAL path: (i) `test -f scripts/kilo-benchmarks/kilo_agents.db` (delivered DB present); (ii) `grep -c "generate_selection_guide_roster.py\|generate_model_capabilities.py" scripts/generate_kilo_agents.py` → **Expected: 0** (Phase-D strip removed the deleted-script `importlib` block); (iii) ⚠️ **REWRITTEN (P6-6): `--out` DOES NOT EXIST** (argparse accepts only `-h`/`-d`, `:945-949`), and `OUTPUT_DIR` is hard-coded to `~/.traycer/cli-agents` (`:40`) with a `shutil.rmtree` on the non-dry-run path (`:875`) — so "or equiv" meant **wiping the operator's live Traycer agent dir**. Run the dry-run and grep STDOUT instead (the failure prints `[warn] Could not update` with **exit 0**, so an exit-code gate cannot see it): `python scripts/generate_kilo_agents.py --dry-run 2>&1 | grep -c 'Could not update'` → **Expected: 0** → **Expected:** emits the Traycer scripts, no `[warn] Could not update` line. **Heartbeat gate (#F3-Pass6):** `python -c "import sys; sys.path.insert(0,'libs'); from alerting import send_alert"` → **Expected:** imports (the retained `daily_refresh.sh` heartbeat now resolves `alerting` from `libs/`, not the deleted vendored copy). If any fails, fix before E.2.
⚠️⚠️ **E.2 BLOCKERS — THREE CRITICAL findings, each verified against the live tree 2026-08-15 by an
independent grounder and re-verified by the orchestrator. E.2 MUST NOT RUN until all three are
scheduled, because none of them fails a test — each deletes something a live caller still needs.**

**C1 — three LIVE test imports sit OUTSIDE every delete set.** `tests/test_kilo_dispatch.py:14`
(`import kilo_dispatch`), `tests/test_kilo_review_validation.py:11,649,695,733` and
`tests/test_kilo_strictness_scenarios.py:19` (`from scripts.kilo_code_review import …`). They live at
`tests/test_kilo_*.py`, NOT under `tests/kilo_benchmarks/**` which is all E.2 deletes, and
`pyproject.toml:94 testpaths=["tests"]` collects them. Deleting the targets reds `final_gate` at E.3.
✅ **DECIDED pass 6/7 (P6-11) — no longer deferred.** `derive_cost.py` is dead outside the engine (engine-internal importers only; `claude_p_cost.py:9-12` deliberately keeps a standalone copy rather than importing it) → **co-delete `tests/test_derive_cost_by_family.py`**. `kilo_dispatch.py`'s shell callers all die with it → **co-delete `tests/test_kilo_dispatch.py`**, and purge the ONE workflow that invokes it (`.windsurf/workflows/kilo.md` — ⚠️ pass 7 measured this: it is **1**, not the 6 pass 6 wrote; 6 is the union across all dead scripts, and three of those six reference `kilo_code_review`, which is now KEPT). `kilo_code_review.py` is **LIVE fleet governance (P6-1) → KEEP the module**, and with it `tests/test_kilo_review_validation.py` + `tests/test_kilo_strictness_scenarios.py`. All four tests collect and pass today.

**C2 — `wsl_startup_hook.sh` invokes 20 distinct engine scripts and Phase E schedules no MODIFY for
it.** Phase E's File Scope lists the file but no phase-E ACTION touches it, while E.1's own shell gate
asserts every hit resolves to a retained remnant — a gate this phase cannot pass as written. If Phase
D shrinks the hook, Phase E must SAY so; today neither phase owns it and the boot pipeline breaks.

**C3 — the contract oracle is invoked by RETAINED scripts but is not itself retained.**
`tests/capture_golden.py --verify` runs from `wsl_startup_hook.sh:234` AND `daily_refresh.sh:505`,
both retained. It is the BLOCKING gate in front of a fleet-sync: the hook's own alert text says *"The
auto-commit below fleet-syncs `.windsurf/rules/**`, so treat this as blocking."* E.2 deletes the
engine `tests/` tree, which orphans the retained `tests/golden/**` data and silently removes the only
thing standing between a husked artifact and ~46 repos. Add `capture_golden.py` to the retained
remnant explicitly.

**HIGH — `src/fabrik/scaffold.py:1017-1018` copies `kilo_code_review.py`/`kilo_docs_enforcer.py` into
every newly scaffolded project** (`core_scripts`), guarded by `.exists()` — so deleting them is a
SILENT scaffold regression, and the file appears in no plan list. **HIGH — E.1's residue gates pattern
only on `kilo-benchmarks/…` and engine module names, so they never see the top-level dead-script
basenames**: 22 `scripts/traycer_agents_fixed/*.sh:171` invoke `traycer_agent_review.py`, and five
fleet-synced `.windsurf/workflows/*.md` invoke `kilo_dispatch.py`/`Kilo_Review.sh`/`Local_*.sh`.
**PLAN ERROR — `process.py`/`process_v2.py` are NOT top-level**; `ls scripts/process*.py` fails. They
exist only under `scripts/kilo-benchmarks/`, i.e. inside deletion (i); the Files DELETE list's "N3
verified, top-level" claim is the wrong half, and E.2(ii)'s own `git rm` already omits them.

⚠️⚠️ **PHASE E ADDENDUM — pass-5 grounding (independent Opus grounder + orchestrator re-verification),
2026-08-15. 22 findings; the four load-bearing ones make an E.1/E.2 gate unpassable or delete a live caller.**

**E-B1 — C3 undercounts by FOUR. The retained `wsl_startup_hook.sh` invokes FIVE engine files, none of them
in the remnant.** Verified verbatim: `:232` `rank_task_subagents.py`, `:234` `tests/capture_golden.py --verify`,
`:236` `check_daily_refresh_freshness.py`, `:130/:233/:235` `pipeline_alert.sh`, `:243`
`autocommit_pipeline_outputs.sh`. The remnant (`:334`) names none of them. **This also directly refutes D.1's
"`check_daily_refresh_freshness` is DROPPED … no orphan, no carve-out"** — `:236` is a live caller D.1 does not
own (see D-B2). Failure mode: E.2 lands, the next shell open runs the hook, five invocations hit "No such
file", every one swallowed by `>> $LOG_FILE 2>&1 || {…}` — and `pipeline_alert.sh`, the thing that would tell
you, is itself among the deleted. **Add all five to the retained remnant, or give Phase E an explicit MODIFY
for the hook.**

**E-B2 — a FOURTH C1-class test, unnamed anywhere in the plan: `tests/test_derive_cost_by_family.py`.** It is
repo-root (not under `tests/kilo_benchmarks/**`, which is all E.2 deletes), collected by `testpaths=["tests"]`,
and does a **module-level** `importlib.util.spec_from_file_location("derive_cost", …/kilo-benchmarks/derive_cost.py)`
(`:17-20`). Deleting `derive_cost.py` errors it at **collection** and reds `final_gate` at E.3. It is exactly
the `importlib`-computed-path idiom E.1 says it exists to catch — missed because the audit walks `ENTRY`, and
`ENTRY` contains no tests.

**E-B3 — E.1's audit script is structurally blind to C3, proven by running its own regex.** The shell branch
pattern `(?:\$\{?KB\}?|kilo-benchmarks)/([A-Za-z_0-9]+)\.py` requires `.py` **immediately** after the prefix,
so `$KB/tests/capture_golden.py` MISSES (subdirectory), `pipeline_alert.sh` MISSES (no `.sh` alternation at
all), and `coding-auto.sh` — named in the ⚠️ ENTRY comment — yields `[]`. The tool the plan calls "the
completeness guarantee" cannot see the blocker the plan calls critical.

**E-B4 — E.1's post-E.2 residue gate can NEVER return empty on this box.** Its exclusion list covers
`/\.git/` but not `.claude/worktrees/`, which is excluded from git via `.git/info/exclude` — not from grep.
Live: **5** worktrees, **342** matching files inside them (the number moves as siblings work). Behavior 4 is
unprovable as written on any shared tree with a live sibling worktree. **Add `/\.claude/worktrees/` to the
exclusion.**

**E-B5 — ❌ REFUTED in pass 6/7 (my own false finding; kept visible, not deleted). The claim below that these are "dead assignments with zero uses" is WRONG — a grep artifact.** Measured: **18** engine `*_SCRIPT=` assignments, **every one used** (`:150-154`, `:161-163`, `:188-211`), **plus 5** more invoked by absolute path = **23 distinct engine files**. The hook is a full second engine pipeline, not a husk; acting on the original finding ships a boot pipeline invoking 23 deleted scripts. ⚠️ The plan has carried FOUR answers for this one quantity (~9 · 20 · 19 · 23) — **23 is the measured one.** Original text: ~~C2's "20 distinct engine scripts" is a grep-hit count, not an invocation count.~~ `wsl_startup_hook.sh`
*references* 20 and *invokes* **3** `.py` (+2 `.sh`); lines 36-61 are 18 `*_SCRIPT="…"` assignments with
**zero uses** — dead assignments from an earlier shrink. This is the same measure-invocations-not-grep-hits
error D.1 corrects for `daily_refresh.sh`, committed one paragraph later. **Internal contradiction:** D.1
(`:303`) says the same file "invokes ~9 engine scripts, `:36-44`". Neither 20 nor 9 is right. C2's
*conclusion* survives and is strengthened by E-B1.

**E-B6 — `.pre-commit-config.yaml:57` is WRONG; the real line is `:65`** (the `governance-sync` `files:`
filter). `:57` is the unrelated `command-corpus-check` entry — an executor following the cite edits the wrong
gate. Cited in the MODIFY list and § Evidence.

**E-B7 — the `daily_refresh.sh` alerting cites `:511`/`:515` are WRONG; real `from alerting import` lines are
`:459` and `:514`.** `libs/alerting/` exists, so the #F3 fix target is real — only the coordinates were wrong.

**E-B8 — `derive_cost.py:158` is WRONG; `_COST_SIDECAR = _HERE / "claude_p_cost.json"` is at `:234`** (`:158`
is a function parameter). `derive_cost.py:23 _RATIOS` and `rank_task_subagents.py:483` are both **exact**.

**E-B9 — `capture_golden.py --verify` is described as "the BLOCKING gate"; both callers are ADVISORY.**
`daily_refresh.sh:510-511` says so in a comment ("must never be able to abort a healthy nightly refresh") and
`wsl_startup_hook.sh:234-235` is `|| { … }`. The quoted "treat this as blocking" text is real — but it is
**prose inside an alert body**, not control flow. C3's severity framing overstates it: nothing stops the sync
today either. (C3's substance still stands — the file must be retained.)

**E-B10 — "22 `traycer_agents_fixed/*.sh:171`" is wrong three ways.** Live: **23** files, **23** invoke
`traycer_agent_review.py`, and only 14 at `:171` (1 at `:184`, 8 at `:191`). And **four more referencing files
appear in no plan list**: `scripts/fix_balanced_tier_agents.py`, `scripts/fix_economy_tier_agents.py`,
`scripts/implement_self_review_workflow.py`, `templates/traycer/agent-post-execution-hook.md` — only
`fix_traycer_agents.py` is in E.2(ii), so three sibling fixers survive pointing at a deleted target.

**E-B11 — "five `.windsurf/workflows/*.md`" is SIX**: `kilo.md`, `local-coder.md`, `local-review.md`,
`local-fixer.md`, `local-docs.md`, `auto-review.md`. ⚠️ `.windsurf/workflows` is in
`fabrik_synced_manifest.py:82`, so these ride the sync to ~46 repos — the dangling references propagate
**fleet-wide**.

**E-B12 — ⚠️ the PLAN-ERROR block's own evidence is false, and acting on it deletes a live script.** It
asserts "`ls scripts/process*.py` fails". It **succeeds, exit 0** — `scripts/process_monitor.py`. The
substantive claim holds (`process.py`/`process_v2.py` exist only under `kilo-benchmarks/`), but anyone
"fixing" E.2(ii) by adding a `scripts/process*.py` glob would `git rm` the live `process_monitor.py`.

**E-B13 — the PLAN-ERROR block never fixed the list it corrects.** `:334`'s DELETE list still enumerates
`process.py`, `process_v2.py` inside the "each at `scripts/<name>`" **top-level** set that the block itself
declares to be the wrong half.

**E-B14 — `claude_p_cost.py` is NOT fleet-synced.** Rule 7 calls it "fleet-synced consumer infra"; live
`grep -c claude_p_cost scripts/fabrik_synced_manifest.py` → **0**, absent from `CORE_SCRIPTS` and from the
`:65` governance filter, and absent from projects. The plan took the file's **own docstring** (`:9-11`) as
ground truth. Everything else in rule 7 is confirmed (`_find()` is `:49-56`, not `:50-54`; the `$0.093/M`
anchor is defined `:41`, consumed `:97`) — but the blast radius of the un-relocated break is **hub-only, not
fleet-wide**, so rule 7's severity drops accordingly.

**E-B15 — the ENTRY-derivation command drops subdir crons AND feeds the audit paths that crash it.**
`grep -oE '/?scripts/[a-z_0-9-]+\.(py|sh)'` has no `/` in the class, so it misses **the plan's own #13 cron**
(`0 6 * * * /opt/fabrik/scripts/kilo-benchmarks/daily_refresh.sh`) plus `scripts/enforcement/`,
`scripts/sysadmin/` entries. Conversely it emits **other repos'** paths with a leading slash
(`/scripts/recovery_sweep.py` from `/opt/youtube`, …), which `pathlib.Path(p).read_text()` resolves as
absolute → **`FileNotFoundError`, with no existence guard**. Following the instruction literally crashes the
tool. (Also: `ENTRY` is relative while `KB` is absolute, so the script only runs from CWD `/opt/fabrik`
despite being CREATEd under `scripts/kilo-benchmarks/tests/`; and the literal `ENTRY` contains no shell
entry-points, making its own shell branch dead code.)

**E-B16 — the RULE-7 pass has three holes the plan claims are closed.** (a) it iterates `for e in ENTRY`, not
`for e in seen`, so a data-file dep of a transitively-reached module is never scanned — concrete miss:
`db_models.py:20 DB_PATH = … "kilo_agents.db"`, and `db_models` is only ever reached transitively; (b) the
extension alternation is `json|ya?ml|txt`, so `.db` and `.html` — i.e. **the two rule-1 artifacts** — are
invisible to the tool meant to prove the sweep complete; (c) `local_imports` only tests `KB/f"{name}.py"`,
never `KB/name/"__init__.py"`, so `alerting/` (a real package dir) is undetectable — and E.1's text sweep
`grep -vE`s it out too. The plan's "**Sweep verified complete this review**" is therefore asserted, not
proven, and "E.1's rule-7 pass re-proves it at execution" is **UNVERIFIABLE by that code**.

**E-B17 — E.2 gate (a) is not mechanically checkable and under-covers.** `grep -rc <pat> fileA fileB` prints
`file:count` per file, never a scalar `0`; and when both truly reach zero `grep -c` **exits 1**, so under
`set -e` the gate errors exactly when it passes (same class as B-B10). It also omits
`scripts/watch_enforcement_changes.sh`, whose `:49-50` is in the MODIFY list but in no gate. Gate (b) is sound.

**E-B18 — the scaffold HIGH is confirmed and has ZERO test coverage.** `src/fabrik/scaffold.py:1015-1026`:
`core_scripts` includes `kilo_code_review.py` (`:1017`) and `kilo_docs_enforcer.py` (`:1018`), copied under an
`.exists()` guard (`:1025`) → **silent skip, no error**. Neither `tests/test_scaffold.py` nor
`test_scaffold_fix.py` asserts they are copied, so nothing goes red. **`src/fabrik/scaffold.py` appears in no
plan list, including File Scope.** Compounding: both are live synced `CORE_SCRIPTS`
(`fabrik_synced_manifest.py:29-30`) with copies in projects today, so deleting the hub sources changes what
`check_synced_unmodified.py` compares against in ~46 repos — covered by no phase-E step.

**E-B19 — the rule-4 doc set is materially larger than either list.** Running the residue gate on the current
tree matches **28** non-engine, non-worktree files, including fleet-synced surfaces named nowhere in the plan:
`.windsurf/rules/core/65-rag-search.md`, `docs/reference/kilo/{CODING_SUBAGENT_SELECTION,BENCHMARK_SOURCES,AI_VENDOR_ACCESS}.md`,
`docs/CAPABILITIES.md`, `docs/reference/{terminal-bench-runner,LOCAL_LLM_INFRASTRUCTURE,architecture}.md`,
`INDEX.md`. The plan hedges with "E.1's grep enumerates the exact set" — but per E-B4 that grep cannot reach
empty, so the hedge does not close it.

**E-B20 — File Scope (`:449`) and the DELETE list (`:334`) disagree, and both omit blocker-implicated files.**
`:449`'s retention omits the rule-6 trio that `:334` explicitly retains, plus `capture_golden.py` and the
rule-7 JSONs. Named in rule 4 but absent from File Scope: `docs/operations/wsl-environment.md`,
`docs/workflows/DATA_SYNC_WORKFLOW.md`, `.windsurf/workflows/subagent-runs-flywheel.md`,
`.windsurf/rules/ai/00-ai-model-selection.md`. Named in CREATE but absent: `audit_engine_coupling.py`, both
rule-7 JSONs. In **neither** list: `src/fabrik/scaffold.py`, the four C1-class tests,
`scripts/traycer_agents_fixed/*.sh` (23), `.windsurf/workflows/*.md` (6), the three sibling fixers, the
Traycer template.

✅ **Verified-good in Phase E** — ⚠️ **one entry below is REFUTED: the claim that E.1's audit "output matches the plan's Expected (post-fix)" is FALSE (P6-8: it prints FIVE `RULE-6 DEP` lines, not three). The "do not re-litigate" framing has been dropped — a skip-instruction wrapped around a wrong claim is worse than a plain error.** The rest holds: E.2(ii)'s `git rm` list is **complete and correct** — all
12 named files exist and `scripts/Local_*.sh` expands to 4 real files; there is no `kilo_cost_report/` package
dir. Rule 6 is accurate to the line (`kilo_auto_route.py:54-56/:58/:59-62/:63-67`, `coding-auto.sh:32/:62`,
`generate_kilo_agents.py:49-51`). C1 is confirmed (and *undercounts* its own line list —
`test_kilo_review_validation.py` also matches at `:615/:655/:701/:737`). `run_kilo_workflow.sh:25-27`,
`test_routing_failover.sh:49`, `pyproject.toml:94`, and the 14 `tests/kilo_benchmarks/` files are all exact.
E.1's audit script **does run clean** from `/opt/fabrik` on the current `ENTRY` and its output matches the
plan's "Expected (post-fix)" — the defects are in what it **cannot see**, not in what it reports.

**E.2 — Excise (TWO separate deletions — different directories, N3).** (i) `git rm -r scripts/kilo-benchmarks/<engine files>` (keeping the rule-1/2/6/7 remnant); (ii) `git rm scripts/{kilo_dispatch.py,kilo_consult.py,kilo_cost_report.py,kilo_agent_health.sh,fix_traycer_agents.py,traycer_agent_review.py,mcp_kilo_server.py,run_kilo_workflow.sh} scripts/Local_*.sh scripts/Kilo_Review.sh` — ⚠️ **`kilo_docs_enforcer.py`, `kilo_code_review.py` and `_bckp` were REMOVED from this command (P6-1): they are live fleet-synced governance, KEPT.** (My first edit pasted that note INSIDE the brace expansion, which would have made the command unparseable if copy-pasted — the fix-introduces-a-defect pattern this plan keeps demonstrating.) — **top-level paths**, which (i)'s recursive delete never touches. Then purge the sync-manifest/watch patterns. Gates: (a) reference purge — ⚠️ **REWRITTEN TWICE — read this, because my pass-7 version MANDATED the very regression P6-1 exists to prevent.** Pass 7 wrote `[ "$(grep -rho 'kilo_code_review\|kilo_docs_enforcer' fabrik_synced_manifest.py .pre-commit-config.yaml watch_enforcement_changes.sh | wc -l)" = 0 ]`. Run today that is **exit 1, 6 matches** — and those six matches ARE the live fleet-sync wiring (`CORE_SCRIPTS:29-30`, the governance-sync `files:` filter at `.pre-commit-config.yaml:65`, `watch_enforcement_changes.sh:49-50`) **for the two modules P6-1 decided to KEEP.** Making that gate green means unwiring them from the sync while leaving the files on disk — hub keeps them, 48 projects go orphaned, `check_synced_unmodified.py` compares against a source no longer in the manifest. That is P6-1's exact failure, delivered by the gate written to prevent it. **The purge is now scoped to the genuinely dead scripts only:** `[ "$(grep -rho 'kilo_dispatch\|kilo_consult\|mcp_kilo_server\|kilo_agent_health\|traycer_agent_review' scripts/fabrik_synced_manifest.py .pre-commit-config.yaml scripts/watch_enforcement_changes.sh | wc -l)" = 0 ]` → **Expected: exit 0**, AND the inverse invariant `grep -c 'kilo_code_review' scripts/fabrik_synced_manifest.py` → **Expected: ≥1 — the KEPT modules must STAY wired to the sync**; (b) **positive-deletion proof (the (a) gate only proves the manifest stopped naming them, never that the files are gone)** — ⚠️ **CORRECTED (P6-1): the old form listed `kilo_docs_enforcer.py` and `kilo_code_review.py`, which are now KEPT — it would have demanded proof that live governance had been deleted.** `ls scripts/kilo_cost_report.py scripts/mcp_kilo_server.py scripts/kilo_dispatch.py scripts/kilo_consult.py 2>&1 | grep -c 'No such file'` → **Expected: 4**; and the inverse, `ls scripts/kilo_code_review.py scripts/kilo_docs_enforcer.py >/dev/null 2>&1` → **Expected: exit 0** (both still present — deleting them is the P6-1 regression).
**E.3 — Full gate + subagent-pool smoke (behavior 4).** `python scripts/final_gate.py --json` → `"success"` (baseline-attributed); run a real `/fabrik-review` finder round end-to-end to prove fabrik's brain still works headless.
**E.4 — ⛔ RETIRED (D5, 2026-08-12): deploy + network flywheel DSN are OUT OF SCOPE.** The probe this step planned has already been RUN (spec §4): `fabrik_analytics` sits on the WSL workstation's local socket, `listen_addresses=localhost`, **not** on `postgres-main`, and that box is not on the WireGuard mesh — so *provision a network-reachable read-only DSN* had no target. Retained verbatim below as the hand-off brief for the separate VPS-deployment spec:
> *(The three original numbered steps — probe the flywheel host, `fabrik apply`, and provision a
> network-reachable read-only DSN — are DELETED here rather than left as imperatives a skim could
> execute. They belong to the VPS-deployment spec, together with spec §4's already-recorded probe
> output, which resolved the host question this step was created to answer.)*
**E.5 — Behavior Contract:** behavior 4 (residue). *(Behavior 5, the flywheel DSN, moves to the VPS spec together with E.4.)*

**E.closing:** run the **whole-plan `/fabrik-review`** over the cumulative diff (→ no-op); `final_gate --json` green (fresh) in both repos; `check_convergence.py` green; `/fabrik-docs-review` on the touched docs; commit (`Agent-Phase: E`) + flip plan `Status: IN-PROGRESS → EXECUTED <date>`; archive the plan to `docs/development/plans/archived/`.

**Out of migration scope (Phase 6, separate plan):** the catalog *product* — API, UI rebuild, multi-tenancy, billing, stdout-log conversion, and licensing the 7 high-risk scraped-ranking feeds (per the extraction assessment).

---


</details>
