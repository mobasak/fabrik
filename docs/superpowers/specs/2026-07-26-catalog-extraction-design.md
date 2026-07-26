# AI-Model-Catalog Extraction — Migration Design Spec

**Status:** CONVERGED
**Date:** 2026-07-26
**Converged:** 2026-07-26 (`/fabrik-spec-review` — 5-pass loop; every `path:line` re-verified live; corrected one self-introduced flywheel-DSN overclaim + resolved 2 internal contradictions; edit-free md5-verified no-op at Pass 5, md5 `775a703961c28308598ea1ea59176c43`). External-facts (A) + fabrik-lib-verdict (B) axes N/A — pure relocation of existing code, no external deps, no new build/vendor capability.
**Author:** primary (this session)
**Scope:** Extract the AI-model-catalog engine out of `/opt/fabrik` into the standalone `/opt/ai-model-catalog` project **without breaking fabrik or the /opt fleet, without losing functionality, and leaving zero engine residue in fabrik.**
**Authority:** Operator granted full authority in both `/opt/fabrik` and `/opt/ai-model-catalog` for the duration of this migration.
**Grounded by:** two evidence-based discovery passes (liveness/invocation surface + fleet consumer manifest) + the coupling audit + the extraction assessment (artifact 2026-07-26). Every claim below is tied to `path:line`.

---

## 1. Goal & constraints

Move the catalog **engine** (scrape → normalize → derive → rank → export → HTML) into `ai-model-catalog`, subject to four hard constraints:

1. **Don't break fabrik** — fabrik's subagent pool (`pick_models`) and its Traycer agent chain must keep working.
2. **Don't break the fleet** — the catalog's outputs are fleet-synced to **~55 `/opt` projects**; their `pick_models` must keep resolving.
3. **No functionality lost** — every consumed output must keep being produced, byte-for-byte where it matters.
4. **No residue in fabrik** — the engine files, DB, and dead Kilo/Cascade scripts are removed; only the **consumer + distribution** surface remains (by design, not as leftover).

**Non-goal (this migration):** turning the catalog into a multi-tenant public SaaS. That is downstream productization (assessment Phases 2–6). This migration only relocates the engine and establishes the fabrik↔catalog contract.

---

## 2. The verified consumer contract (what must survive the move)

The engine has **six output classes**. What actually consumes each (live only):

| # | Output | Live consumers | Fleet-synced? | Fail-open? |
|---|---|---|---|---|
| 1 | `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` | `pick_models` in `libs/subagents/select.py:479` (**56 vendored copies**) via `_synced_ranking()` | **Yes** (all 55 projects) | **Yes** — `_TABLE` floor at `select.py:151`, 14-day staleness gate at `select.py:373` |
| 1b | `docs/reference/kilo/CODING_SUBAGENT_SELECTION.md` | `rank_task_subagents.py:312,360` (`_read_coding_selection`, coding fallback) | Yes | Yes (rows-first) |
| 1c | `KILO_MODEL_CAPABILITIES.md`, `KILO_AGENT_SELECTION_GUIDE.md`, `TTS/STT/TRANSLATION/IMAGE_GEN/CANDIDATE_SIGNUPS_SELECTION.md` | **doc-only** — presence enforced by `check_doc_index.py:39`, labelled by `docs_updater.py:733` | Yes | n/a (presence gate) |
| 2 | `kilo_agents.db` (SQLite) | hub-only: `kilo_model_sync.py`, `rank_task_subagents.py:335`, `microbench_coding_direct.py`, `manage_blocked.py`, `update_gateway_counts.py` | **No** (hub-local) | hardcoded paths |
| 3 | Traycer registry `scripts/kilo_47_agents_final.json` (+ `kilo_all_models.json`, `kilo_embeddings_final.json`, `kilo_openrouter_routes_final.json`) | `kilo_model_sync.py:33`; `generate_kilo_agents.py` → `~/.traycer/cli-agents/*.sh` → `kilo_terminal_runner.py`/`kilo_auto_route.py` | No | hardcoded |
| 4 | `.windsurf/rules/ai/*.md` `GATEWAY_COUNTS` + `OPENROUTER_ROUTES` blocks | **doc-only** — read by AI agents at authoring time | **Yes** (rules/ synced) | n/a |
| 5 | `docs/CAPABILITIES.md` + `capabilities.json` + `llms.txt` | `audit_capability_docs.py:168`, `docs_updater.py`, `check_doc_index.py` | No | arg-overridable |
| 6 | Postgres `fabrik_analytics.subagent_runs` (flywheel) | **writers:** fleet-wide vendored `pg_ledger.py` (INSERT-only); **reader:** ONLY `rank_task_subagents.py:43-44,155` (via `sudo -u postgres psql`) | writers fleet-wide | reader fail-open (`("error",[])` stub) |

**The load-bearing fact:** `pick_models` degrades gracefully. `_synced_ranking()` returns `{}` on any miss (`select.py:363,367,375`), so `table.get(task_type)` falls through to the vendored `_TABLE[task_type]` (`select.py:479-483`). **Nothing hard-breaks if a doc goes missing — the risk is silent staleness, not a crash.** This is the migration's safety net.

**Distribution channel:** `sync_enforcement_to_projects.py` (`main()` ~line 740) fleet-pushes `docs/reference/kilo/`, `.windsurf/rules/`, and the vendored `libs/subagents/` to every non-`_`/non-`archived` `/opt/*` dir. **This stays in fabrik** — it is the produce→**sync**→fleet chain's distribution leg.

---

## 3. Live / dead inventory (grounds the "no residue" cut)

### 3a. MOVES to `ai-model-catalog` (the engine — deleted from fabrik after cutover)

`scripts/kilo-benchmarks/**` (176 first-party files, ~51k LOC, 52 tests) — every scraper, migration, deriver, ranker, exporter, seeder, microbench, grader, audit, the config YAMLs, `kilo_agents.db` + backups, `models_browser_template.html`, `daily_refresh.sh` (engine steps), and the artifact **producers** that currently write into fabrik paths:
- Selection-doc producers: `rank_task_subagents.py`, `rank_coding_subagents.py`, `rank_{tts,stt,translation,image_gen,candidate_signups}.py`, `generate_model_capabilities.py`, `generate_selection_guide_roster.py`, `embedding_export_markdown.py`.
- Rule-pack producers: `category_export_markdown.py`, `update_gateway_counts.py`.
- Registry producer: `export_traycer_registry.py` (the clean engine→fabrik seam).
- HTML: `export_models_browser.py`.
- Throwaway: `process.py`, `process_v2.py` (delete, don't move).

### 3b. STAYS in fabrik (the consumer + distribution surface — NOT residue)

| Kept | Why |
|---|---|
| `libs/subagents/**` (`select.py`/`pick_models`, `agent.py`/`fanout`, `pg_ledger.py`) | Shared `fabrik-lib` module; fabrik's pool + the fleet depend on it. Canonical at `/opt/fabrik-lib/subagents`. |
| `scripts/generate_kilo_agents.py` | Consumes `kilo_47_agents_final.json` → emits fabrik-side Traycer agents. LIVE (`daily_refresh:260`, `wsl_startup:106`). |
| `scripts/generate_capability_index.py` | Builds fabrik's capability index. |
| `scripts/sync_enforcement_to_projects.py` | Fleet distribution of the produced docs + rules. |
| `scripts/kilo_model_sync.py` (cron `59 11`), `kilo_terminal_runner.py`, `kilo_auto_route.py`, `coding-auto.sh` | LIVE Traycer chain. |
| The received `docs/reference/kilo/*.md`, `.windsurf/rules/ai/*` blocks, `capabilities.*` | Consumed artifacts, now produced externally and delivered in. |

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
  │           capabilities.*, models_browser.html
  └─ DELIVER bundle ─────────────────────────────────►  /opt/fabrik
                                                          ├─ generate_kilo_agents (Traycer)
                                                          ├─ generate_capability_index
                                                          └─ sync_enforcement_to_projects ──► 55 projects
```

**Why A over B (live API):** fabrik's core agent loop must not gain a runtime network dependency. A file-delivery contract keeps `pick_models` reading a local file exactly as today, preserves the fail-open floor, and reuses the existing fleet-sync. A live API is a **later product feature** (assessment Phase 6), not the migration cut.

**Engine shape inside a web scaffold:** `ai-model-catalog` is a `saas-skeleton` (Next.js + FastAPI web tier), but the engine is a **batch pipeline, not a web service** — so it deploys as a **scheduled worker** within the project (its own cron/worker container in the compose, alongside — not inside — the web tier), keeping `daily_refresh` semantics. The web tier (API + UI) is Phase-6 productization; this migration only lands the worker.

**Delivery mechanism (transition-safe):** during transition the engine can run **hub-side cron** (as today, just relocated code) writing straight into fabrik's paths — zero contract change. Post-cutover, delivery becomes an explicit `deliver-to-fabrik` step (rsync/commit of the produced bundle into fabrik's `docs/reference/kilo/`, `.windsurf/rules/ai/`, `scripts/kilo_47_agents_final.json`, `capabilities.*`), then fabrik's `sync_enforcement` runs. Fabrik's `daily_refresh.sh` shrinks to: `deliver` (or fetch) → `generate_kilo_agents` → `generate_capability_index` → `sync_enforcement`.

### Data stores (stated so the plan doesn't guess)

The engine keeps its **self-contained SQLite `kilo_agents.db` as-is** through this migration — it is the catalog store and travels with the engine (relocation, not conversion). The saas-skeleton's **Postgres is reserved for the product/app layer** (users, accounts, saved views) in productization (Phase 6) — **not** converted here. So `ai-model-catalog` has three DB concerns, only the first two touched by this migration: (1) its own SQLite catalog `kilo_agents.db` (moves), (2) **read-only** access to fabrik's `fabrik_analytics.subagent_runs` flywheel (new DSN — see below), (3) the saas app Postgres (untouched until Phase 6).

### The flywheel seam (the one genuinely shared boundary — and the one thing the plan MUST probe, not assume)

`rank_task_subagents.py` (moves with the engine) is the **only** reader of `fabrik_analytics.subagent_runs`; fleet writers (vendored `pg_ledger`, INSERT-only) stay put.

**Grounded reality (re-verified this session):** the hub's writer DSN is `SUBAGENT_RUNS_DSN=postgresql:///fabrik_analytics` — **host-less**, i.e. a local Unix-socket connection — and the reader connects via `sudo -u postgres psql -d fabrik_analytics` (also a local socket; `rank_task_subagents.py:187-191`, docstring:17). So on the hub host **both writer and reader hit the same LOCAL postgres instance**, which is why the flywheel works. Note: `pg_ledger.py:10` aspirationally says *"postgres-main (never localhost)"* — that comment **contradicts the actual host-less DSN**; trust the DSN, not the comment. (Pre-existing doc drift, not this migration's to fix — but it must not mislead the plan.)

**Migration implication — a NAMED Phase-5 verification, not an assumption:** a *deployed* `ai-model-catalog` container cannot reach a local socket. So the plan MUST, before switching the reader: (a) probe the flywheel's true physical host on the hub — `psql "$SUBAGENT_RUNS_DSN" -c '\conninfo'` (resolves whether `fabrik_analytics` lives on the hub host's postgres or the `postgres-main` container); then (b) provision a **network-reachable read-only DSN** to that exact instance for the catalog, replacing the `sudo psql` path. Fabrik stays tenant-zero: its private telemetry drives its own selection doc, produced by the catalog. **Fail-safe:** if the DSN is unreachable from the deployed catalog for any reason, the reader's existing fail-open (`("error",[])` stub → `_TABLE` floor, `rank_task_subagents.py:179`) bounds the blast radius to *staleness, never an outage* — so this seam cannot break fabrik even if mis-provisioned. (D2 resolved → read-only DSN; see §7.)

---

## 5. Phased plan (safety-first, parallel-run, golden-file gated)

**Phase 0 — Freeze the contract (read-only).** Build the consumer manifest as an executable **golden-file harness**: snapshot today's `TASK_SUBAGENT_SELECTION.md` + all `docs/reference/kilo/*.md` + the `.windsurf/rules/ai/*` marker blocks + `kilo_47_agents_final.json` + `capabilities.json`, and capture the exact DB queries the live hub consumers run. This snapshot is the regression oracle for "no functionality lost." *Gate: harness reproduces every live output.*

**Phase 1 — Copy the engine into `ai-model-catalog` (fabrik untouched).** Move `kilo-benchmarks/**` + the producers; sever the four tentacles (paths→`REPO_ROOT`, `.env`→repo-local, Postgres peer-auth→DSN, `fabrik-lib`→pinned dep); add a real dependency manifest (`pyproject`); port the 52 tests. *Gate: `daily_refresh` runs green standalone; producer outputs are **byte-identical** to Phase-0 goldens.*

**Phase 2 — Build the delivery bridge + parallel-run.** Wire the `deliver-to-fabrik` step (writes into fabrik's consumed paths). Keep fabrik's **own** `daily_refresh` running the old engine too. Run **both** for ≥3 days; diff the delivered bundle vs. fabrik's self-produced outputs daily. *Gate: zero diff across a full week including a Sunday (microbench day).*

**Phase 3 — Cutover.** Fabrik's `daily_refresh` stops running engine steps; the catalog becomes sole producer; fabrik keeps `generate_kilo_agents` + `generate_capability_index` + `sync_enforcement`. Vendored `_TABLE` floor stays as seatbelt. Monitor `pick_models` + the flywheel through ≥3 days of overlap. *Gate: fleet `TASK_SUBAGENT_SELECTION.md` freshness < 24h; a live `fanout` smoke picks the same models as pre-cutover.*

**Phase 4 — Excise residue.** `git rm` the engine from fabrik + the dead Kilo/Cascade scripts (§3c) + purge their sync-manifest/watch-pattern propagation. Update `INDEX.md`/`PORTS.md`/`PROJECT_CATALOG.md`/`docs/README.md`. *Gate: full `final_gate.py --json` green; a real subagent-pool review runs end-to-end; `grep -r kilo-benchmarks` returns only the consumer/distribution references intended to stay.*

**Phase 5 — Deploy the catalog + finalize the flywheel DSN.** First **probe the flywheel's true host** — `psql "$SUBAGENT_RUNS_DSN" -c '\conninfo'` on the hub (the DSN is host-less today, so its physical instance must be resolved, not assumed — see §4). Deploy `ai-model-catalog` via `fabrik apply`; provision a **network-reachable read-only DSN** to that instance and point `rank_task_subagents` at it (replacing `sudo psql`); confirm the deployed catalog can actually `SELECT` from `subagent_runs`; retire the hub cron. *Gate: `\conninfo` host recorded; deployed catalog reads the flywheel over the network (or fail-opens cleanly); catalog produces + delivers on its own schedule; fabrik consumes with no local engine.*

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

---

## 7. Resolved decisions (operator-approved 2026-07-26)

All four resolved by operator sign-off this session — no open execution-blocking questions remain.

- **D1 — Architecture: RESOLVED → Option A** (file-delivery, fabrik=tenant-zero). Live API deferred to productization Phase 6.
- **D2 — Flywheel seam: RESOLVED → read-only `fabrik_analytics` DSN** for the catalog, replacing the hub's `sudo -u postgres psql` read at `rank_task_subagents.py` (docstring:17). Reader stays fail-open.
- **D3 — Dead-residue cleanup: RESOLVED → folded into this migration** (Phase 4 §3c), including purging the dead scripts from `fabrik_synced_manifest.py:29-30` + the `.pre-commit-config.yaml:57` / `watch_enforcement_changes.sh:49-50` patterns so they stop propagating to the fleet.
- **D4 — Vehicle: RESOLVED → single operator-carried plan** with a blocking `/fabrik-review` at each phase gate (rollback story is strong: fabrik self-produces until Phase 4).

**Operator directive (binding on the plan):** *don't skip a single thing · leave zero residue · break no working system · retire what is not used.*

---

## 8. Evidence appendix (path:line)

- `pick_models` fail-open + resolution: `libs/subagents/select.py:151` (`_TABLE`), `:242` (`SUBAGENT_SELECTION_DOC`), `:318` (`_HUB_SELECTION_DOC`), `:328` (`_project_selection_doc` walk-up), `:363/367/375` (`{}` on miss), `:373` (14-day gate), `:479-483` (fallthrough).
- Retirement proof: git `55a53b9a` "retired Kilo/Cascade triad"; `.pre-commit-config.yaml:57` (trigger regex only); `fabrik_synced_manifest.py:29-30` + `sync_enforcement_to_projects.py:404` (copy, never exec); `watch_enforcement_changes.sh:49-50` (watcher not launched); `final_gate.py` = 0 refs.
- Engine→fabrik seam: `export_traycer_registry.py` → `scripts/kilo_47_agents_final.json` → `generate_kilo_agents.py` (`daily_refresh.sh:257,260`; `wsl_startup_hook.sh:105,106`).
- Flywheel: writers `pg_ledger.py:63` (`_INSERT`), auto-record `agent.py:986`; sole reader `rank_task_subagents.py:43-44,155`.
- Fleet distribution: `sync_enforcement_to_projects.py` pushes `docs/reference/kilo/` + `.windsurf/rules/` + `libs/subagents/`.

---

## Handoff

D1–D4 are signed off (§7) and this spec is CONVERGED by `/fabrik-spec-review`. **Next:** `/fabrik-plan-after-chat` to produce the phased execution plan with per-phase gates. **No `/fabrik-data-contract` or `/fabrik-ui-design` needed** — this migration relocates a backend engine and adds no user-facing entity, field, or screen (the API + UI are Phase-6 productization, out of scope here), so despite `ai-model-catalog` being a `saas-skeleton` the GUI-design step does not apply to *this* spec. Do **not** start Phase 1 file moves until the plan is CONVERGED and operator-approved.
