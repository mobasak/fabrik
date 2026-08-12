# AI-Model-Catalog Extraction — Migration Design Spec

**Status:** DRAFT — **re-opened 2026-08-12 by a second `/fabrik-spec-review`; BLOCKED on decision D5 (§7).**
**Date:** 2026-07-26 (re-reviewed 2026-08-12)
**Review history:**
- *2026-07-26* — CONVERGED by `/fabrik-spec-review` (5-pass loop, edit-free md5 no-op at Pass 5, md5 `775a703961c28308598ea1ea59176c43`).
- *2026-08-12* — **re-review before re-planning. Status reverted to DRAFT.** All 29 `path:line` citations re-verified against the live tree — **25 held exactly**, incl. every fail-open citation (`select.py:151/242/318/328/363/367/373/375/479-483`), the whole `rank_task_subagents` set, and the host-less `SUBAGENT_RUNS_DSN` at `.env:386`; **4 line numbers corrected** (`daily_refresh.sh:257,260`→`:272,275`; `docs_updater.py:733`→`:735`; `sync_enforcement` `main()` ~740→`:749`) and **4 quantitative claims corrected** (vendored copies 56→49, fleet dirs ~55→54, the file/test inventory, and the live flywheel row count made non-frozen). Four grounded sweeps + a live probe found **three previously-unnamed host-only seams**, of which one is architectural and blocking: (1) **D5** — the flywheel DB is on the WSL workstation's local socket, *not* `postgres-main`, and that box is not on the fleet mesh, so Phase 5's "provision a network-reachable DSN" had no target (§4, §7); (2) the **15 MB catalog SQLite is gitignored** while the deploy is git-sourced, so a deployed container would silently produce empty output (§4 Data stores); (3) the **`claude -p` credential seam** — six engine files need the host's rotated `~/.claude` (§4). Also corrected an internal contradiction that listed `capabilities.*` as engine outputs when their producer stays in fabrik (§2).
- External-facts (A) + fabrik-lib-verdict (B) axes remain N/A — pure relocation of existing code, no external deps, no new build/vendor capability. The binding axis here is codebase-grounding.
**Author:** primary (this session)
**Scope:** Extract the AI-model-catalog engine out of `/opt/fabrik` into the standalone `/opt/ai-model-catalog` project **without breaking fabrik or the /opt fleet, without losing functionality, and leaving zero engine residue in fabrik.**
**Authority:** Operator granted full authority in both `/opt/fabrik` and `/opt/ai-model-catalog` for the duration of this migration.
**Grounded by:** two evidence-based discovery passes (liveness/invocation surface + fleet consumer manifest) + the coupling audit + the extraction assessment (artifact 2026-07-26). Every claim below is tied to `path:line`.

---

## 1. Goal & constraints

Move the catalog **engine** (scrape → normalize → derive → rank → export → HTML) into `ai-model-catalog`, subject to four hard constraints:

1. **Don't break fabrik** — fabrik's subagent pool (`pick_models`) and its Traycer agent chain must keep working.
2. **Don't break the fleet** — the catalog's outputs are fleet-synced to the `/opt` projects (**54 fleet dirs / 49 vendored `select.py` copies**, measured 2026-08-12); their `pick_models` must keep resolving.
3. **No functionality lost** — every consumed output must keep being produced, byte-for-byte where it matters.
4. **No residue in fabrik** — the engine files, DB, and dead Kilo/Cascade scripts are removed; only the **consumer + distribution** surface remains (by design, not as leftover).

**Non-goal (this migration):** turning the catalog into a multi-tenant public SaaS. That is downstream productization (assessment Phases 2–6). This migration only relocates the engine and establishes the fabrik↔catalog contract.

---

## 2. The verified consumer contract (what must survive the move)

The engine has **five output classes**. What actually consumes each (live only):

| # | Output | Live consumers | Fleet-synced? | Fail-open? |
|---|---|---|---|---|
| 1 | `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` | `pick_models` in `libs/subagents/select.py:479` (**49 vendored copies**, measured 2026-08-12) via `_synced_ranking()` | **Yes** (54 fleet dirs) | **Yes** — `_TABLE` floor at `select.py:151`, 14-day staleness gate at `select.py:373` |
| 1b | `docs/reference/kilo/CODING_SUBAGENT_SELECTION.md` | `rank_task_subagents.py:312,360` (`_read_coding_selection`, coding fallback) | Yes | Yes (rows-first) |
| 1c | `KILO_MODEL_CAPABILITIES.md` (the engine's capability artifact, `generate_model_capabilities.py:20`), `KILO_AGENT_SELECTION_GUIDE.md`, `TTS/STT/TRANSLATION/IMAGE_GEN/CANDIDATE_SIGNUPS_SELECTION.md` | **doc-only** — presence enforced by `check_doc_index.py:39`, labelled by `docs_updater.py:735` | Yes | n/a (presence gate) |
| 2 | `kilo_agents.db` (SQLite) | hub-only: `kilo_model_sync.py`, `rank_task_subagents.py:335`, `microbench_coding_direct.py`, `manage_blocked.py`, `update_gateway_counts.py` | **No** (hub-local) | hardcoded paths — ⚠️ **and gitignored: see §4 Data stores, it cannot ride a git deploy** |
| 3 | Traycer registry `scripts/kilo_47_agents_final.json` (+ `kilo_all_models.json`, `kilo_embeddings_final.json`, `kilo_openrouter_routes_final.json`) | `kilo_model_sync.py:33`; `generate_kilo_agents.py` → `~/.traycer/cli-agents/*.sh` → `kilo_terminal_runner.py`/`kilo_auto_route.py` | No | hardcoded |
| 4 | `.windsurf/rules/ai/*.md` `GATEWAY_COUNTS` + `OPENROUTER_ROUTES` blocks | **doc-only** — read by AI agents at authoring time | **Yes** (rules/ synced) | n/a |
| 5 | Postgres `fabrik_analytics.subagent_runs` (flywheel) | **writers:** fleet-wide vendored `pg_ledger.py` (INSERT-only); **reader:** ONLY `rank_task_subagents.py:43-44,155` (via `sudo -u postgres psql`) | writers fleet-wide | reader fail-open (`("error",[])` stub) |

**⚠️ NOT an engine output (corrected 2026-08-12):** `docs/CAPABILITIES.md` + `capabilities.json` + `llms.txt` are produced by **`scripts/generate_capability_index.py:401-411`**, which **STAYS in fabrik** (§3b) and is explicitly retained in the post-cutover chain (§4 diagram, §5 Phase 3). They are therefore **fabrik-local artifacts, never part of the delivered bundle** — an earlier revision listed them as engine output class 5 and had §4's delivery step rsync `capabilities.*` INTO fabrik, which would have made the catalog overwrite (or fail to supply) a file fabrik generates itself. The engine's capability artifact is `KILO_MODEL_CAPABILITIES.md` (`generate_model_capabilities.py:20`) — row 1c above. `audit_capability_docs.py:168` is a fabrik-side *consumer* of the fabrik-side file, not an engine seam.

**The load-bearing fact:** `pick_models` degrades gracefully. `_synced_ranking()` returns `{}` on any miss (`select.py:363,367,375`), so `table.get(task_type)` falls through to the vendored `_TABLE[task_type]` (`select.py:479-483`). **Nothing hard-breaks if a doc goes missing — the risk is silent staleness, not a crash.** This is the migration's safety net.

**Distribution channel:** `sync_enforcement_to_projects.py` (`main()` at `:749`, core-script copy at `:404`) fleet-pushes `docs/reference/kilo/`, `.windsurf/rules/`, and the vendored `libs/subagents/` to every non-`_`/non-`archived` `/opt/*` dir. **This stays in fabrik** — it is the produce→**sync**→fleet chain's distribution leg.

---

## 3. Live / dead inventory (grounds the "no residue" cut)

### 3a. MOVES to `ai-model-catalog` (the engine — deleted from fabrik after cutover)

`scripts/kilo-benchmarks/**` — every scraper, migration, deriver, ranker, exporter, seeder, microbench, grader, audit, the config YAMLs, `kilo_agents.db` + backups, `models_browser_template.html`, `daily_refresh.sh` (engine steps only — see the split note in §5 Phase 3).

> **⚠️ Inventory is DERIVED AT EXECUTION TIME, never copied from this spec (re-verified 2026-08-12).** An earlier revision hard-coded "176 first-party files, ~51k LOC, 52 tests". That count is now stale: **52 files were added after this spec froze** (the whole `dispatcher-bench/` benchmark suite, `dispatcher_bench.py`, `build_lcb_difficulty_manifest.py`, `microbench_vision_describe.py`), and in-tree tests are **53** with **15** more at repo-root `tests/kilo_benchmarks/`. The engine is under active development; any hand-enumerated file list ages within days. The plan MUST derive the move-set mechanically (import-graph audit) and treat every count here as illustrative.
>
> **MUST NOT move (host-built / gitignored artifacts, not source):** `.lcb-venv/` (297 MB, 4,856 files — a host-built virtualenv with absolute shebangs), `.lcb-hf-cache/`, `.microbench_cache/`, `cache/`, `backups/`, and `translation_bench/cache/` (gitignored at `.gitignore:174`). These are regenerated by provisioning (`setup_lcb_grader.sh`), never copied.

The artifact **producers** that currently write into fabrik paths:

- Selection-doc producers: `rank_task_subagents.py`, `rank_coding_subagents.py`, `rank_{tts,stt,translation,image_gen,candidate_signups}.py`, `generate_model_capabilities.py`, `generate_selection_guide_roster.py`, `embedding_export_markdown.py`.
- Rule-pack producers: `category_export_markdown.py`, `update_gateway_counts.py`.
- Registry producer: `export_traycer_registry.py` (the clean engine→fabrik seam).
- HTML: `export_models_browser.py`.
- Throwaway: `process.py`, `process_v2.py` (delete, don't move).

### 3b. STAYS in fabrik (the consumer + distribution surface — NOT residue)

| Kept | Why |
|---|---|
| `libs/subagents/**` (`select.py`/`pick_models`, `agent.py`/`fanout`, `pg_ledger.py`) | Shared `fabrik-lib` module; fabrik's pool + the fleet depend on it. Canonical at `/opt/fabrik-lib/subagents`. |
| `scripts/generate_kilo_agents.py` | Consumes `kilo_47_agents_final.json` → emits fabrik-side Traycer agents. LIVE (`daily_refresh.sh:275`, `wsl_startup_hook.sh:106`). |
| `scripts/generate_capability_index.py` | Builds fabrik's capability index. |
| `scripts/sync_enforcement_to_projects.py` | Fleet distribution of the produced docs + rules. |
| `scripts/kilo_model_sync.py` (cron `59 11`), `kilo_terminal_runner.py`, `kilo_auto_route.py`, `coding-auto.sh` | LIVE Traycer chain. |
| The received `docs/reference/kilo/*.md` + `.windsurf/rules/ai/*` blocks | Consumed artifacts, now produced externally and delivered in. |
| `capabilities.json` / `docs/CAPABILITIES.md` / `llms.txt` | **Generated fabrik-side** by the retained `generate_capability_index.py` — NOT delivered in (§2). Listed here so the plan never adds them to the bundle. |

### 3c. DELETED outright (dead Kilo/Cascade residue — remove in Phase 4, independent of the move)

`kilo_docs_enforcer.py`, `kilo_code_review.py`, `kilo_code_review_bckp.py`, `kilo_dispatch.py`, `kilo_consult.py`, `kilo_cost_report.py`, `kilo_cost_tracker.py`, `Local_{Coder,Documentator,Review,Fixer}*.sh`, `kilo_agent_health.sh`, `fix_traycer_agents.py`, `Kilo_Review.sh`, `traycer_agent_review.py`, `mcp_kilo_server.py`. **Also purge their propagation:** remove them from `fabrik_synced_manifest.py:29-30` (`CORE_SCRIPTS`) and the `.pre-commit-config.yaml:57` + `watch_enforcement_changes.sh:49-50` watch patterns so they stop being copied to the fleet.

---

## 4. Architecture — Option A: publish-to-consumer, fabrik as "tenant zero"

The external `ai-model-catalog` runs the **full engine** (including the artifact producers) and reads fabrik's flywheel; it then **delivers** the consumed artifacts back to fabrik, which keeps distributing to the fleet.

```
ai-model-catalog (deployed, or hub-cron during transition)
  ├─ ingest → kilo_agents.db → derive → rank  (reads fabrik_analytics.subagent_runs via DSN)
  ├─ produce: TASK_SUBAGENT_SELECTION.md, other selection docs,
  │           GATEWAY_COUNTS/OPENROUTER_ROUTES blocks, kilo_47_agents_final.json,
  │           KILO_MODEL_CAPABILITIES.md, models_browser.html   (NOT capabilities.* — see §2)
  └─ DELIVER bundle ─────────────────────────────────►  /opt/fabrik
                                                          ├─ generate_kilo_agents (Traycer)
                                                          ├─ generate_capability_index
                                                          └─ sync_enforcement_to_projects ──► 54 fleet dirs
```

**Why A over B (live API):** fabrik's core agent loop must not gain a runtime network dependency. A file-delivery contract keeps `pick_models` reading a local file exactly as today, preserves the fail-open floor, and reuses the existing fleet-sync. A live API is a **later product feature** (assessment Phase 6), not the migration cut.

**Engine shape inside a web scaffold:** `ai-model-catalog` is a `saas-skeleton` (Next.js + FastAPI web tier), but the engine is a **batch pipeline, not a web service** — so it deploys as a **scheduled worker** within the project (its own cron/worker container in the compose, alongside — not inside — the web tier), keeping `daily_refresh` semantics. The web tier (API + UI) is Phase-6 productization; this migration only lands the worker.

**Delivery mechanism (transition-safe):** during transition the engine can run **hub-side cron** (as today, just relocated code) writing straight into fabrik's paths — zero contract change. Post-cutover, delivery becomes an explicit `deliver-to-fabrik` step (rsync/commit of the produced bundle into fabrik's `docs/reference/kilo/`, `.windsurf/rules/ai/`, `scripts/kilo_47_agents_final.json`), then fabrik's `sync_enforcement` runs. **The bundle does NOT include `capabilities.*`** — those are generated fabrik-side by the retained `generate_capability_index.py` (§2); an earlier revision listed them here, which would have had the catalog clobber a file fabrik produces itself. Fabrik's `daily_refresh.sh` shrinks to: `deliver` (or fetch) → `generate_kilo_agents` → `generate_capability_index` → `sync_enforcement`.

### Data stores (stated so the plan doesn't guess)

The engine keeps its **self-contained SQLite `kilo_agents.db` as-is** through this migration — it is the catalog store and travels with the engine (relocation, not conversion).

**⚠️ BLOCKING GAP — "travels with the engine" is not a mechanism (found 2026-08-12).** `kilo_agents.db` is **15 MB, 909 agent rows, and NOT IN GIT** — matched by `.gitignore:126` (`*.db`), confirmed absent via `git ls-files`. The catalog deploys with **`source.type: git`** (`specs/services/ai-model-catalog.yaml:18-21`, repo `mobasak/ai-model-catalog`), i.e. the VPS obtains its code by `git pull`. **A git-sourced container therefore receives NO database.** SQLite's `connect()` silently *creates an empty file*, so every ranker/exporter would emit empty output and the delivered selection docs would be empty — fabrik's `_TABLE` floor would then bound this to *silent fleet-wide staleness*, exactly the failure this design's safety net exists to survive but never identifies as reachable. (Corroborated by a second, louder path: `translation_bench/bake.py:487,438,461` connects the same gitignored DB and raises `no such table: agents` — **after** a fully-paid bake run.)
**The plan MUST choose and state a transport for the 15 MB store — this is not an execution detail:** (a) a persistent Docker **volume** seeded once (worker keeps SQLite; simplest, but the DB then lives only on the VPS and hub-side runs diverge); (b) **object-storage** fetch/put per run via `fabrik-lib/storage` (B2) — survives redeploys, adds a startup dependency; (c) **convert the catalog store to Postgres** — a *new database on the shared `postgres-main` instance*, which the project already depends on (`ai-model-catalog.yaml:22-23`). Biggest change, but the only option that also solves the flywheel seam below, since the catalog store and the flywheel would then live on one reachable instance (this pairs naturally with D5 option (a), §7). **Do not proceed on "it travels with the engine."**

To keep the three DB concerns distinct — they are easy to conflate, and option (c) touches only the first: (1) the engine's **catalog store** (`kilo_agents.db` today; transport per the choice above), (2) **read-only** access to fabrik's `fabrik_analytics.subagent_runs` **flywheel** (per D5), (3) the **saas app database** for users/accounts/saved views, which stays **reserved for Phase-6 productization and is untouched here**. Option (c) creates a *catalog* database; it does not start the Phase-6 app schema.

### The flywheel seam (the one genuinely shared boundary — probed 2026-08-12; the answer is now D5)

`rank_task_subagents.py` (moves with the engine) is the **only** reader of `fabrik_analytics.subagent_runs`; fleet writers (vendored `pg_ledger`, INSERT-only) stay put.

**Grounded reality (re-verified this session):** the hub's writer DSN is `SUBAGENT_RUNS_DSN=postgresql:///fabrik_analytics` — **host-less**, i.e. a local Unix-socket connection — and the reader connects via `sudo -u postgres psql -d fabrik_analytics` (also a local socket; `rank_task_subagents.py:187-191`, docstring:17). So on the hub host **both writer and reader hit the same LOCAL postgres instance**, which is why the flywheel works. Note: `pg_ledger.py:10` aspirationally says *"postgres-main (never localhost)"* — that comment **contradicts the actual host-less DSN**; trust the DSN, not the comment. (Pre-existing doc drift, not this migration's to fix — but it must not mislead the plan.)

**⚠️ THE PROBE HAS NOW BEEN RUN (2026-08-12) — and its answer invalidates the Phase-5 end-state as previously written.** This spec deferred "resolve the flywheel's physical host" to Phase 5. Resolved:

```
$ psql "$SUBAGENT_RUNS_DSN" -c '\conninfo'
You are connected to database "fabrik_analytics" as user "ozgur" via socket in "/var/run/postgresql" at port "5432".
$ sudo -n -u postgres psql -d fabrik_analytics -tAc "SHOW listen_addresses; SHOW port;"
localhost
5432
$ ss -lntp | grep 5432
LISTEN 0  600  127.0.0.1:5432  0.0.0.0:*
$ docker exec postgres-main psql -U postgres -lqt | cut -d'|' -f1 | grep -c fabrik_analytics
0
$ ip -4 addr show | grep -E "10\.99\.|wg"      # WireGuard fleet mesh membership
(no output)
$ sudo -n -u postgres psql -d fabrik_analytics -tAc "SELECT count(*) FROM subagent_runs;"
6261        # live counter, still growing — re-read 6264 twenty minutes later; treat as ~6.3k, never as a fixed value
```

**What this means:** `fabrik_analytics` lives on the **WSL dev workstation's local PostgreSQL**, bound to `127.0.0.1:5432` with `listen_addresses = localhost`. It is **NOT** on `postgres-main` (the shared container every deployed service uses), and the WSL box is **not on the WireGuard fleet mesh** (`10.99.0.0/24`) at all. It holds **~6.3k live rows and is actively growing** — load-bearing, not a toy.

**Consequence: "provision a network-reachable read-only DSN to that instance" is NOT ACHIEVABLE as written.** There is no network-reachable instance to point at, and no route from vps1 to that host. The flywheel works today *only* because the reader and all ~49 fleet writers sit on the same box and share one Unix socket (writers resolve the same host-less `SUBAGENT_RUNS_DSN`, `pg_ledger.py:152`). Moving the reader off-box breaks the read; moving the DB to reach it re-points every writer.

**This is now an OPEN DECISION (D5, §7) requiring operator sign-off — not a Phase-5 task.** The three viable end-states: **(a) migrate `fabrik_analytics` to `postgres-main`** — the only option that makes the deployed end-state work as designed, but it re-points the fleet's writers (~49 vendored `pg_ledger` copies resolve `SUBAGENT_RUNS_DSN` from env, so this is an env change, not a code change — verify before committing to it); **(b) the ranking step stays hub-side permanently** — contradicts §4's "deploys as a scheduled worker" and splits the engine across two hosts; **(c) the catalog runs as hub-side cron permanently** — cheapest, but it makes §4's "transition" state the terminal state and Phase 5 becomes a no-op. **Fail-safe unchanged:** whichever option is chosen, the reader's existing fail-open (`("error",[])` stub → `_TABLE` floor, `rank_task_subagents.py:179`) bounds a mis-provisioned seam to *staleness, never an outage* — this seam cannot break fabrik even if provisioned wrongly. Fabrik stays tenant-zero either way: its private telemetry drives its own selection doc, produced by the catalog.

⚠️ **This supersedes D2.** D2 (2026-07-26) resolved the seam as "a read-only `fabrik_analytics` DSN for the catalog", which presumed a network-reachable instance existed. The probe shows none does, so D2's resolution is not implementable on its own and D5 must settle the end-state first.

### The `claude -p` credential seam (a THIRD host-only boundary — found 2026-08-12, missed by the original review)

Structurally identical to the flywheel-socket problem above, and previously unnamed. Six engine files authenticate to Claude by shelling out to `npx @anthropic-ai/claude-code`, which reads the **host's rotated `~/.claude` OAuth credentials**: `claude_p.py:47-58` (the shim), `microbench_review.py:997`, `microbench_coding_direct.py:293`, `dispatcher_bench.py:149`, `derive_cost.py:24-26` (reads `~/.claude/.claude-manager/` usage-history + statusline + `manager-accounts`), and `microbench_vision_describe.py:198` (a *second*, differently-hardcoded path, `~/.local/bin/claude`). **`rank_task_subagents.py` is on this list too** — the sole flywheel reader and the primary selection-doc producer, i.e. the critical path.

`claude_p.py` is fail-CLOSED at its own layer (raises on non-zero exit `:64-67`, in-band `is_error` `:77-81`, missing usage `:84-85`, empty completion `:91-94`) — but several callers catch broadly and record an error row, so the aggregate behaviour is a **benchmark that completes with 100% error rows and a zero exit code**: silent.

**Fabrik already has the mechanism — the spec must use it.** `shape.uses_claude_cli: true` + `claude_cli_home` (declared in `spec_loader.py:342,357`) makes the deployer *require* the host's rotated `~/.claude:ro` mount, and it hard-fails the deploy otherwise (`deployer_ssh.py:540`, `:625-643`). Working precedent: `specs/services/seo.yaml:18-20`. **`specs/services/ai-model-catalog.yaml` does not declare either flag** — so a deployed catalog would silently have no Claude credentials. Either declare them (and accept that the rotation-aware mount only exists where the host's `~/.claude` does), or scope the claude-`-p` microbenches as **hub-only steps that never run in the deployed worker** — an explicit split the plan must write down, not discover.

---

## 5. Phased plan (safety-first, parallel-run, golden-file gated)

**Phase 0 — Freeze the contract (read-only).** Build the consumer manifest as an executable **golden-file harness**: snapshot today's `TASK_SUBAGENT_SELECTION.md` + all `docs/reference/kilo/*.md` + the `.windsurf/rules/ai/*` marker blocks + `kilo_47_agents_final.json` + `capabilities.json`, and capture the exact DB queries the live hub consumers run. This snapshot is the regression oracle for "no functionality lost." *Gate: harness reproduces every live output.*

**Phase 1 — Copy the engine into `ai-model-catalog` (fabrik untouched).** Move `kilo-benchmarks/**` + the producers; sever the **five** tentacles (paths→`REPO_ROOT`, `.env`→repo-local, Postgres peer-auth→DSN, `fabrik-lib`→pinned dep, **and the fifth below**); add a real dependency manifest (`pyproject`); port the tests (count derived, not copied from §3a).

> **⚠️ The FIFTH tentacle — host binaries, host state dirs, and sibling repos (found 2026-08-12).** The original four cover paths, env, DB auth and the lib dep, but a whole class of coupling escapes all four, and most of it fails **silently**. Enumerated by a four-way sweep of the engine tree — the plan must resolve each, and this list is a floor, not the completeness authority:
> - **Host CLI binaries invoked by name:** `kilo` (`kilo_agents_db.py:88`, `verify_openrouter_catalog.py:274`, `discover_kilo_agents.py:31` — note the Kilo CLI is *retired*, so these already no-op), `harbor` (`dataset_freshness.py:183`), `npx`/node, `bwrap` (`libs/subagents/sandbox.py:108`), `xdg-open` (`export_models_browser.py:404`), `ssh`+remote `sudo docker` (`alerting/apprise.py:53,61-71`), `git` (many), `psql`+`sudo` (`apply_subagent_runs_ddl.sh:29-45`).
> - **Host state directories:** `~/.claude/.claude-manager/` (`derive_cost.py:24-26`), `~/.traycer/cli-agents` (`generate_selection_guide_roster.py:91`), `~/.cache/harbor` (`microbench_terminal.py:84,108`, `dataset_freshness.py:67`, `scrape_tbench_task_results.py:58`), `~/.config/kilo` (`tools/sanitize_kilo_config.py:23`).
> - **Sibling-repo reads on the same filesystem:** `/opt/fabrik-lib/mt-router/...` (`seed_translation_and_stt.py:48`, unguarded → LOUD), `/opt/fabrik-lib/subagents` (`apply_subagent_runs_ddl.sh:29`), `/opt/site-provisioner` + `/opt/fabrik/.venv/bin` (`dispatcher_bench.py:49-51`), `/opt/fabrik/.env` (`audit_pipeline.py:31`, `microbench_vision_describe.py:97`, `tests/test_specialty_clients/test_smoke.py:34`).
> - **Intra-tree import coupling that breaks on a partial copy:** `specialty_clients/*` insert `parent.parent` on `sys.path` to import root-level `specialty_pricing` (7 files); `mine_docs_corpus.py:31` imports `scripts/doc_reconcile.py` from *outside* the engine dir; `structural_grader.py:39` / `microbench_review.py:47` resolve `parents[2]` assuming the `<fabrik>/scripts/kilo-benchmarks/` position.
> - **Undeclared third-party deps** (no in-subtree manifest today): `sacrebleu` (`translation_bench/metric.py:28`), `PyYAML` (`translation_bench/bake.py:41`) — the `pyproject` this phase adds must capture them.
> - **Alerting dies silently in a container:** the whole `alerting/` chain fail-softs (`alerting/__init__.py:52,101`); the SSH→VPS→docker leg cannot work off-host, leaving `telegram.py` (pure HTTPS) as the only container-portable delivery leg.
>
> **Verified CLEAN and container-portable (negative evidence, so the plan doesn't re-audit them):** `web_scrape/` and `libs/web_scrape/` (browserless is a caller-supplied URL; no browser binary), `direct_vendor_parsers/` (pure functions, no I/O), `migrations/` (DDL only), `dispatcher-bench/` fixtures. No Playwright/Selenium/chromium, no X11/DISPLAY, no hardcoded localhost port anywhere in the tree.

*Phase-1 gate: `daily_refresh` (engine steps) runs green standalone; producer outputs are **byte-identical** to Phase-0 goldens.*

**Phase 2 — Build the delivery bridge + parallel-run.** Wire the `deliver-to-fabrik` step (writes into fabrik's consumed paths). Keep fabrik's **own** `daily_refresh` running the old engine too. Run **both** for ≥3 days; diff the delivered bundle vs. fabrik's self-produced outputs daily. *Gate: zero diff across a full week including a Sunday (microbench day).*

**Phase 3 — Cutover.** Fabrik's `daily_refresh` stops running engine steps; the catalog becomes sole producer; fabrik keeps `generate_kilo_agents` + `generate_capability_index` + `sync_enforcement`. Vendored `_TABLE` floor stays as seatbelt. Monitor `pick_models` + the flywheel through ≥3 days of overlap. *Gate: fleet `TASK_SUBAGENT_SELECTION.md` freshness < 24h; a live `fanout` smoke picks the same models as pre-cutover.*

> **⚠️ The `daily_refresh.sh` split is NOT "engine steps vs the rest" (grounded 2026-08-12).** §3a moves the file with the engine, but the live 595-line script also performs **hub-only work that can never move**, and the plan must enumerate the split explicitly rather than infer it: the **hub crontab install** (`:49`), hardcoded hub roots + hub venv interpreter (`:55-58`, nothing is relative to the script), a `PATH` export existing solely to expose the host `kilo` CLI to cron (`:61`), a **`/tmp` lockfile coordinated with `wsl_startup_hook.sh`** (`:80-96`), steps that live **outside** the engine dir (`gather_envs.py` — which scans **every `/opt/*/.env`** — plus `classify_services.py`, `generate_capability_index.py`, `generate_kilo_agents.py`, `sync_enforcement_to_projects.py`, `:139,141,252,275,486`), the **fleet-sync flock** writing into ~46 sibling repos (`:486-489`), a **git add/commit/fetch/push of the hub repo** (`:540-590`, entirely `|| true`-swallowed), the **Sunday-gated** microbench branch (`:384-390`), and in-tree writes to `backups/`+`cache/` (`:117-118,331-333`) that presume a writable persistent volume. The two heartbeat `send_alert` imports (`:511,515`) must resolve to fabrik's retained `libs/alerting`, not the engine's vendored copy, or the operator's only cron-skip heartbeat goes dark behind a `|| true`.

**Phase 4 — Excise residue.** `git rm` the engine from fabrik + the dead Kilo/Cascade scripts (§3c) + purge their sync-manifest/watch-pattern propagation. Update `INDEX.md`/`PORTS.md`/`PROJECT_CATALOG.md`/`docs/README.md`. *Gate: full `final_gate.py --json` green; a real subagent-pool review runs end-to-end; `grep -r kilo-benchmarks` returns only the consumer/distribution references intended to stay.*

**Phase 5 — Deploy the catalog + resolve the three host-only seams.** ⚠️ **BLOCKED on D5 (§7) — this phase cannot be planned until the operator picks the flywheel end-state.** The probe this phase was meant to run has already been executed (§4): `fabrik_analytics` is on the WSL workstation's local socket, `listen_addresses=localhost`, not on `postgres-main`, and the box is not on the fleet mesh — so the original "provision a network-reachable read-only DSN" step has no target. Once D5 is decided, this phase carries **three** seams, not one: (1) the **flywheel** per D5; (2) the **catalog store** transport per §4 Data stores (volume / object-store / Postgres — the DB is gitignored and cannot ride a git deploy); (3) the **`claude -p` credentials** — either declare `shape.uses_claude_cli` + `claude_cli_home` in `specs/services/ai-model-catalog.yaml` (deployer then requires the `~/.claude:ro` mount) or split the claude-`-p` microbenches into hub-only steps. Then deploy via `fabrik apply` and retire the hub cron *only if* D5 permits. *Gate: each of the three seams demonstrably works from the DEPLOYED container (a real `SELECT` against the flywheel; a non-empty `agents` table read; one live claude-`-p` call) or is explicitly and deliberately scoped hub-only; catalog produces + delivers on its own schedule; fabrik consumes with no local engine.*

**Phase 6 (out of migration scope):** productization — API, UI rebuild, multi-tenancy, licensing the 7 high-risk feeds (assessment).

**Rollback at every phase:** until Phase 4, fabrik's own engine still exists and runs — reverting is "turn the catalog delivery off, fabrik self-produces again." The fail-open `_TABLE` floor means even a total catalog outage degrades the fleet to baked-in rankings, never an outage.

---

## 6. Risks

| Risk | Mitigation |
|---|---|
| A missed live consumer breaks silently | Phase-0 golden harness + Phase-2 week-long parallel diff; `pick_models` fail-open bounds worst case to staleness |
| Fleet gets stale selection docs post-cutover | Freshness monitor (< 24h) as a Phase-3 gate; `check_ai_pack_freshness.py` already exists (`wsl_startup_hook:164`) |
| Flywheel DSN read fails in prod | Reader already fail-open (`("error",[])` stub → `_TABLE` floor); alert on the stub |
| Dead-script deletion hits a hidden caller | Liveness pass proved zero live callers; Phase-4 gate greps the whole fleet before delete |
| Sunday microbench divergence | Parallel-run window explicitly spans a Sunday |
| `libs/subagents` double-vendor drift (`scripts/kilo-benchmarks/libs/subagents/` second copy) | Engine takes its own vendored copy; fabrik keeps `libs/subagents` from `fabrik-lib`; no shared file |
| **Deployed catalog produces EMPTY output** (gitignored 15 MB SQLite never reaches a git-sourced container; `.gitignore:126`) | §4 Data stores — the plan must pick a store transport (volume / object-store / Postgres) **before** deploy; gate on a non-empty `agents` read **from the deployed container**, never from the hub |
| **Deployed catalog silently loses all Claude-`-p` capability** (host `~/.claude` unreachable; 6 files, incl. `rank_task_subagents.py`) | Declare `shape.uses_claude_cli`+`claude_cli_home` (`deployer_ssh.py:540,625-643` enforces the mount) or scope those microbenches hub-only — §4 credential seam |
| **Alerting goes dark in the container** (`alerting/` fail-softs; ssh→VPS→docker leg is host-only, `alerting/__init__.py:52,101`) | `telegram.py` (pure HTTPS) is the only container-portable leg — the plan must ensure the worker's alert path uses it, or the engine fails silently and unobserved |

---

## 7. Decisions

D1–D4 were resolved by operator sign-off 2026-07-26. **D5 was opened by the 2026-08-12 re-review and is BLOCKING** — it must be answered before a plan is trustworthy, because it changes the migration's end state.

### ⚠️ D5 — Flywheel end-state: OPEN, blocking, operator's call

Grounded by live probe (§4): `fabrik_analytics` (~6.3k rows and growing) lives on the **WSL workstation's local PostgreSQL**, `127.0.0.1:5432`, `listen_addresses=localhost`, **not** on `postgres-main`, and that box is **not on the WireGuard fleet mesh**. Today the flywheel works only because the reader and all ~49 fleet writers share one Unix socket on one box. Pick one:

| Option | What it buys | What it costs |
|---|---|---|
| **(a) Migrate `fabrik_analytics` → `postgres-main`** | The only option where the designed end-state (deployed worker reads the flywheel) actually works; also the natural home for the catalog store, collapsing two seams into one | Re-points ~49 fleet writers. They resolve `SUBAGENT_RUNS_DSN` from **env** (`pg_ledger.py:152`), so this is likely an env/`.env` change rather than code — **verify that before committing**. Plus a data migration of the ~6.3k existing rows. |
| **(b) Ranking stays hub-side permanently** | No DB migration; keeps the fail-open floor untouched | Contradicts §4's "deploys as a scheduled worker"; the engine is then split across two hosts and "zero residue in fabrik" becomes false for the ranking step |
| **(c) Catalog runs as hub-side cron permanently** | Cheapest; the migration becomes a pure code relocation | §4's "transition" state becomes terminal; Phase 5 becomes a no-op and the VPS deploy is deferred to Phase 6 |

**Recommendation: (a)** — it is the only option that leaves the spec's own architecture intact, and it also solves the §4 catalog-store transport problem, since a Postgres-backed store on `postgres-main` removes the gitignored-SQLite gap entirely. But it is the largest change and the fleet-writer blast radius must be probed first, so it is the operator's decision, not the reviewer's.

**Previously resolved (2026-07-26):**

- **D1 — Architecture: RESOLVED → Option A** (file-delivery, fabrik=tenant-zero). Live API deferred to productization Phase 6.
- **D2 — Flywheel seam: ~~RESOLVED → read-only `fabrik_analytics` DSN~~ → SUPERSEDED BY D5 (2026-08-12).** The original resolution (a read-only DSN for the catalog, replacing the hub's `sudo -u postgres psql` read at `rank_task_subagents.py` docstring:17) presumed a network-reachable instance. The live probe (§4) shows the database is on the workstation's local socket only, so D2 cannot be implemented as written — D5 must choose the end-state first. The "reader stays fail-open" half of D2 still holds and is unaffected.
- **D3 — Dead-residue cleanup: RESOLVED → folded into this migration** (Phase 4 §3c), including purging the dead scripts from `fabrik_synced_manifest.py:29-30` + the `.pre-commit-config.yaml:57` / `watch_enforcement_changes.sh:49-50` patterns so they stop propagating to the fleet.
- **D4 — Vehicle: RESOLVED → single operator-carried plan** with a blocking `/fabrik-review` at each phase gate (rollback story is strong: fabrik self-produces until Phase 4).

**Operator directive (binding on the plan):** *don't skip a single thing · leave zero residue · break no working system · retire what is not used.*

---

## 8. Evidence appendix (path:line)

- `pick_models` fail-open + resolution: `libs/subagents/select.py:151` (`_TABLE`), `:242` (`SUBAGENT_SELECTION_DOC`), `:318` (`_HUB_SELECTION_DOC`), `:328` (`_project_selection_doc` walk-up), `:363/367/375` (`{}` on miss), `:373` (14-day gate), `:479-483` (fallthrough).
- Retirement proof: git `55a53b9a` "retired Kilo/Cascade triad"; `.pre-commit-config.yaml:57` (trigger regex only); `fabrik_synced_manifest.py:29-30` + `sync_enforcement_to_projects.py:404` (copy, never exec); `watch_enforcement_changes.sh:49-50` (watcher not launched); `final_gate.py` = 0 refs.
- Engine→fabrik seam: `export_traycer_registry.py` → `scripts/kilo_47_agents_final.json` → `generate_kilo_agents.py` (`daily_refresh.sh:272,275`; `wsl_startup_hook.sh:105,106`). *(Line numbers re-verified 2026-08-12 — the daily_refresh pair had drifted from the previously-cited `:257,260`.)*
- Flywheel: writers `pg_ledger.py:63` (`_INSERT`), auto-record `agent.py:986`; sole reader `rank_task_subagents.py:43-44,155`.
- Fleet distribution: `sync_enforcement_to_projects.py` pushes `docs/reference/kilo/` + `.windsurf/rules/` + `libs/subagents/`.

---

## Handoff

⚠️ **This spec is DRAFT, not CONVERGED — do NOT hand it to `/fabrik-plan-after-chat` yet.** D1–D4 are signed off (§7), but the 2026-08-12 re-review opened **D5 (flywheel end-state)**, which is BLOCKING: options (a)/(b)/(c) produce materially different plans — (a) adds a database-migration phase that re-points fleet writers, (b) and (c) delete Phase 5's deploy step entirely. Planning before D5 is answered would produce a plan for an architecture that may not be chosen.

**Next:** operator answers **D5** (§7 carries the three options, the blast radius of each, and the recommendation). On that answer the two remaining seams become mechanical: the catalog-store transport (§4 Data stores) largely follows from D5, and the `claude -p` seam is a shape-flag-or-split decision the plan can carry. **Then:** `/fabrik-plan-after-chat` to produce the execution plan with per-phase gates.

**Note for the planner (2026-08-12):** the prior monolithic plan `docs/development/plans/2026-07-26-plan-1-ai-model-catalog-extraction.md` (Status: HARDENED, 11 review rounds, ~62 fixes) predates the spine+ticket plan-set architecture and its file inventory is stale. Feed it in as **prior art** — especially its import-graph-audit completeness mechanism (E.1), which remains the right answer to the "hand-enumeration keeps missing members" problem restated in §3a. **No `/fabrik-data-contract` or `/fabrik-ui-design` needed** — this migration relocates a backend engine and adds no user-facing entity, field, or screen (the API + UI are Phase-6 productization, out of scope here), so despite `ai-model-catalog` being a `saas-skeleton` the GUI-design step does not apply to *this* spec. Do **not** start Phase 1 file moves until the plan is CONVERGED and operator-approved.
