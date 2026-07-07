# Best-Model-Suggester — Implementation Plan

**Status:** IN-PROGRESS (execution started 2026-07-07 from baseline_commit `715d0d3d`, baseline_gate `success`) — Phase A ✅ EXECUTED 2026-07-07 (`1c3aec67`); Phase B ✅ EXECUTED 2026-07-07; Phase C ✅ EXECUTED 2026-07-07; Phase E ✅ EXECUTED 2026-07-07 (browser tbody/JS rendering for the 2 new tabs is a follow-up on `export_models_browser.py`); Phase D PENDING.
**Previously:** CONVERGED (re-converged 2026-07-06 for post-subagent-runs repo-drift — 2 adversarial passes to md5-verified fixed point)
**Fifth `/fabrik-plan-review` (post-subagent-runs drift, 2026-07-06):** Pass 1 fixed 6 defects surfaced by adversarial re-grounding against the current tree: (a) `daily_refresh.sh` `_step "rank_coding_subagents"` invocation drifted :344→:349 + `_step "export_models_browser"` :355→:369 (Context Ledger row + Phase B.6 body); (b) sibling `rank_task_subagents` now sits between them at :358 (subagent-runs-lean plan, released `final_commit: 5e402a42`) — updated Phase B.6 to insert BEFORE :369, and Gate B.6 `_step "rank_` count from `5` to `6` + awk order check extended with `rank_task_subagents` anchor; (c) `rank_coding_subagents.py:_atomic_write` drifted :345→:362 + `main` :371→:388 (Context Ledger + Phase B evidence + Phase E evidence); (d) `check_convergence.py` failure-branch drifted :92→:91 (Phase D evidence); (e) concurrency check narrative added the 4th plan-lock (`2026-07-06-plan-1-subagent-runs-lean.json`, released) with its overlap disclosure on `daily_refresh.sh` / `CHANGELOG.md` / `INDEX.md`; (f) header status blurb refreshed. Pass 2 no-op verified: START md5 (recorded in Pass Ledger below) == END md5.
**Fourth `/fabrik-plan-review` (GUI-completeness):** Pass 1 fixed 4 defects: (a) Interfaces block still said "new `<div id="tab-watchlist">`" — real template at `models_browser_template.html:651` uses `<span class="tab" data-tab="X">` chips with `data-tabs` visibility, no `<div id="tab-X">` exists — rewrote to spec § E.3 architecture; (b) subagent E.5c owned-paths description referenced the wrong tab structure; (c) E.7 step body listed items 3-5 with `<div id="tab-rent-gpu">` / `<div id="tab-candidates">` — replaced with `<span class="tab" data-tab="...">` chips + dual `<tbody id="rows-gpu">` / `<tbody id="rows-candidates">` swap; (d) stale duplicate Gate E.7 block from pre-GUI-expansion `id="tab-watchlist"` gate was left in place at line 1033 after the fresh gate at line 995 — removed the duplicate. Pass 2 md5 START (`a9ac1099e1ae42ccca4d712ff9f88ff4`) == END → true no-op.
**Third `/fabrik-plan-review` (post-Phase-E):** 2 adversarial passes to md5-verified fixed point. Pass 1 fixed 1 defect: E.2 test does `from seed_watchlist_and_gpu import _migrate_gpu_providers` but Interfaces.Produces block declared only `seed_watchlist_and_gpu()` — a subagent reading Interfaces alone would inline the migration and the test would ImportError; added `_migrate_gpu_providers(conn) -> None` as an explicit Produces entry with "MUST be top-level and importable" flag. Pass 2 md5 START (`e9160dc63290e8d0b30ed3e8691b06f4`) == END → true no-op. Coverage re-verified: 11 path:line citations still resolve; all 3 plan-locks still `released` (no new concurrent runs); Phase E `/fabrik-review` gate + subagent parallelism mandate + step-to-subagent map intact.
**Phase E re-convergence:** 2026-07-05 — Pass 1 fixed 3 defects: (1) Phase E steps E.5–E.8 touch 4 different files with no cross-signature dependency after E.4 but were staged sequentially — added Subagent Mandates block dispatching them as 4 parallel worktree-isolated subagents (E.5a/b/c/d) per Phase 3 pillar #3; (2) File Scope decorations for `kilo_agents.db`, `daily_refresh.sh`, `suggest_model.py` showed only Phase A/B ownership — extended to note Phase E migrations/modifications too; (3) step-to-subagent mapping table added so an executor can pick the right subagent per step. Pass 2 md5 START (`d4cfcf67d15daad3be968518fba54c99`) == END → true no-op fixed point.
**Date:** 2026-07-05
**Design spec:** [docs/superpowers/specs/2026-07-05-best-model-suggester-design.md](../../superpowers/specs/2026-07-05-best-model-suggester-design.md) (CONVERGED 2026-07-05, 4 passes Phase A–D + 2 passes Phase E expansion)
**Converged:** 2026-07-05 via `/fabrik-plan-review` — 5 adversarial grounding passes to a genuine md5-verified no-op. Pass 1 fixed 4 defects (wrong `daily_refresh.sh` insertion line-numbers `31–35` → real `344/355`, wrong `_step` vs `step` command syntax in Phase B.6 + broken grep gate, "32 columns" claim → real 84, factually-loose "in-flight" concurrency claim → real "all 3 recent locks released"). Pass 2 fixed 1 (signature mismatch: test called `_rank_service_type(volume_images=1000)` but impl reads `volume.get("images", 0)` — would silently produce $0 cost). Pass 3 fixed 1 (missing `kilo_agents.db` from Phase A `git add` — file is git-tracked, migration would leave dirty tree). Pass 4 fixed 2 (Interfaces block signature incomplete: `**volume` kwargs omitted, subagent risk; Phase D.4 had angle-bracket placeholder `<exact files check_docs_review touched>` that TBD grep missed — replaced with explicit `git status --porcelain` + allowed-path filter). Pass 5 no-op verified: START md5 `ccd53c99f98a69109ec201d369ef59cf` == END md5 `ccd53c99f98a69109ec201d369ef59cf`.
**Handoff:** User runs `/fabrik-execute-plan docs/development/plans/2026-07-05-plan-1-best-model-suggester.md`. See "Residual unknowns → still-open" for non-blocking follow-ups the executor should be aware of.

## What we already agreed (Phase 0)

Extracted from the CONVERGED spec + this conversation:

- **Goal.** Ship an accessibility-aware AI model suggester that never recommends a model outside Özgür's real vendor set, and never extrapolates from empty specialty data (hard-fail exit=1). Kill the 3 failure modes from the driving session (hallucinated OR/TTS route, cost-wrong image recommendation, orphaned CODING_SUBAGENT_SELECTION.md).
- **3 phases in one plan, strict order.** A (catalog + seed) → B (suggester + rankers) → C (rules-pack integration). User's exact words: *"i want all use /fabrik-spec first. then /fabrik-spec-review skill."* Same plan pipeline: create → review → execute.
- **Manual vendor catalog first**, auto-detect balances is out of scope (separate future Phase B.5 spec). User's confirmed choice.
- **Advisory rule + programmatic hard-fail**, NOT pre-commit script. User's confirmed choice.
- **Reuse existing vendor keys.** Every new-vendor recommendation must be flagged; the ranker filters by `reachable_with_existing_keys=1` matching the catalog.
- **Hub-side only.** Everything lives under `/opt/fabrik/`. No project-side deploy. `.windsurf/rules/**` and `docs/reference/kilo/**` sync to projects via governance-sync (verified: `scripts/fabrik_synced_manifest.py:67,69`); `scripts/kilo-benchmarks/**` is hub-only.

**Branch: RICH.** The spec pinned goal + approach + external facts + fabrik-lib verdict. No brainstorming.

## File Scope (owned paths)

This plan owns these files. `/fabrik-execute-plan` will refuse to start if any overlap another active plan-lock.

```
docs/reference/kilo/AI_VENDOR_ACCESS.md                          [CREATE, Phase A]
docs/reference/kilo/TTS_SELECTION.md                             [CREATE, Phase B]
docs/reference/kilo/STT_SELECTION.md                             [CREATE, Phase B]
docs/reference/kilo/TRANSLATION_SELECTION.md                     [CREATE, Phase B]
docs/reference/kilo/IMAGE_GEN_SELECTION.md                       [CREATE, Phase B]
scripts/kilo-benchmarks/seed_specialty_catalog.py                [CREATE, Phase A]
scripts/kilo-benchmarks/suggest_model.py                         [CREATE, Phase B]
scripts/kilo-benchmarks/rank_tts.py                              [CREATE, Phase B]
scripts/kilo-benchmarks/rank_stt.py                              [CREATE, Phase B]
scripts/kilo-benchmarks/rank_translation.py                      [CREATE, Phase B]
scripts/kilo-benchmarks/rank_image_gen.py                        [CREATE, Phase B]
scripts/kilo-benchmarks/tests/test_seed_specialty_catalog.py     [CREATE, Phase A]
scripts/kilo-benchmarks/tests/test_suggest_model.py              [CREATE, Phase B]
scripts/kilo-benchmarks/tests/test_rank_specialty.py             [CREATE, Phase B]
scripts/kilo-benchmarks/kilo_agents.db                           [MIGRATE, Phase A — ADD COLUMNs; Phase E — ADD gpu_providers TABLE + agents.signup_trigger COLUMN]
scripts/kilo-benchmarks/daily_refresh.sh                         [MODIFY, Phase B — add 4 ranker steps; Phase E — insert scrape_gpu_prices + rank_candidate_signups]
.windsurf/rules/ai/00-ai-model-selection.md                      [MODIFY, Phase C + Phase E]
docs/reference/kilo/CANDIDATE_SIGNUPS.md                         [CREATE, Phase E]
scripts/kilo-benchmarks/scrape_gpu_prices.py                     [CREATE, Phase E — vendors fabrik-lib/web-scrape]
scripts/kilo-benchmarks/seed_watchlist_and_gpu.py                [CREATE, Phase E]
scripts/kilo-benchmarks/rank_candidate_signups.py                [CREATE, Phase E]
scripts/kilo-benchmarks/tests/test_watchlist_and_gpu.py          [CREATE, Phase E]
scripts/kilo-benchmarks/tests/test_upsell_watcher.py             [CREATE, Phase E]
scripts/kilo-benchmarks/libs/web_scrape/                         [CREATE, Phase E — VENDORED from /opt/fabrik-lib/web-scrape/]
scripts/kilo-benchmarks/models_browser_template.html             [MODIFY, Phase E — add Watch-list tab]
CHANGELOG.md                                                     [APPEND per phase]
INDEX.md                                                         [APPEND per phase — new files]
```

**Concurrency check (2026-07-06 re-verified).** `.fabrik/plan-locks/` shows 4 recent locks, **all status: `released`** — no active plan-lock is in flight, so a fresh `/fabrik-execute-plan` run of THIS plan will not collide on start:
- `2026-07-03-plan-1-full-speed-coverage-close.json` (released) — owned `microbench_specialty.py`, `specialty_pricing.py`, `specialty_clients/**`, `kilo_agents.db` (this plan MIGRATES the DB, but that lock is released — no conflict).
- `2026-07-04-plan-1-saas-fastapi-user-auth-flip.json` (released) — unrelated auth work.
- `2026-07-04-plan-2-browser-coding-subagent-integration.json` (released) — owned `rank_coding_subagents.py`, `export_models_browser.py`, `models_browser*.html`, `INDEX.md`, `CHANGELOG.md`. This plan does NOT touch `rank_coding_subagents.py` (it references its helper API only, doesn't modify it), DOES touch the browser template (Phase E.7), and DOES append to `INDEX.md` + `CHANGELOG.md`.
- `2026-07-06-plan-1-subagent-runs-lean.json` (released, `final_commit: 5e402a42`) — owned `daily_refresh.sh`, `rank_task_subagents.py`, `apply_subagent_runs_ddl.sh`, `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md`, `CHANGELOG.md`, `INDEX.md`. Since that lock is **released**, the overlap with THIS plan's `daily_refresh.sh` (Phase B.6, E.9) + `CHANGELOG.md` + `INDEX.md` is not an active conflict — but the sibling already inserted `_step "rank_task_subagents"` at `daily_refresh.sh:358` between `rank_coding_subagents` (:349) and `export_models_browser` (:369). Phase B.6's insertion instructions were updated to reflect this (the 4 new rankers now land after :358, not immediately after :349). A future new plan re-acquiring `daily_refresh.sh`, `INDEX.md`, or `CHANGELOG.md` would need to serialize with THIS plan for those shared files.

**Serialization points (shared-file mandate):** `INDEX.md` and `CHANGELOG.md` are shared across all plans by nature. Every phase's commit stages them explicitly and appends (never rewrites `[Unreleased]`).

## Global Constraints

Verbatim from binding sources — every phase inherits these:

- **Python 3.11+**, stdlib-first (`sqlite3`, `argparse`, `pathlib`, `re`) for the ranker; no new pip deps.
- **Explicit `git add <path>` only** — never `git add -A`, `git add .`, or `git commit -a` (CLAUDE.md HARD STOP).
- **DB path:** `scripts/kilo-benchmarks/kilo_agents.db` (SQLite, `agents` table). No `postgres-main`/`localhost` (hub-side scripts, not deployed).
- **Sync-manifest awareness.** `.windsurf/rules/**` and `docs/reference/kilo/**` are governance-synced (`scripts/fabrik_synced_manifest.py:67,69`); edits happen here on the hub, sync propagates to projects. Never edit a project copy.
- **Provenance trailers on every commit** — `Agent-Role: subagent|orchestrator|review-fix`, `Agent-Phase: A|B|C|D`, `Agent-Task: N` for subagent commits, `Agent-Context:` one-liner.
- **Test pattern:** `pytest` from repo root; new tests go under `scripts/kilo-benchmarks/tests/`.
- **Idempotent seeder.** Re-running `seed_specialty_catalog.py` on an already-seeded DB is a no-op (`INSERT OR IGNORE` + `UPDATE ... WHERE cheapest_gateway_price IS NULL`). No accidental duplication.
- **Charset:** ASCII in code; ✅/⚠️/❌ status emojis allowed **only** in `AI_VENDOR_ACCESS.md` (user-facing markdown), never in code strings.

## Context Ledger

Binding sources — the cold executor inherits all of these.

| Source | What binds | Grounded ref |
|---|---|---|
| ACTIVE rule pack `core/10-python.md` | Python 3.11 typing (`from __future__ import annotations`), no bare `except`, no `print` in libraries (advisory) | `.windsurf/rules/core/10-python.md` (loaded via `select_rules.py` — 18 ACTIVE packs) |
| ACTIVE rule pack `core/25-data-postgres.md` | Nullability discipline: new columns must specify `NULL` behavior; migrations idempotent | `.windsurf/rules/core/25-data-postgres.md` (applies to SQLite too — same discipline) |
| ACTIVE rule pack `core/40-documentation.md` | Doc Sync Matrix per CLAUDE.md; INDEX.md + CHANGELOG.md on file add | `.windsurf/rules/core/40-documentation.md` |
| ACTIVE rule pack `core/45-testing-strategy.md` | 1 test for the highest-risk path (empty-pool exit=1, mixed pricing_unit cost math) | `.windsurf/rules/core/45-testing-strategy.md` |
| ACTIVE rule pack `ai/00-ai-model-selection.md` | The pack Phase C extends; the "Fabrik defaults" table + "Selection workflow" section it hooks into | `.windsurf/rules/ai/00-ai-model-selection.md:20,49` (verified: `## Selection workflow` at :20, `## Fabrik defaults` at :49) |
| fabrik-lib verdict (inherited from spec) | Every capability adjudicated: SQLite query = stdlib; markdown-table parse = build small; Pareto ranking = clone `rank_coding_subagents.py` pattern; CLI = argparse. No vendor/enhance for this plan. | Spec § "fabrik-lib verdict" |
| `rank_coding_subagents.py` — real API | Reuse `_rows_from_db(db_path)`, `_atomic_write(path, content)`, `_safe_md_id(mid)`, `_fmt_or_dash(v, fmt)`, `main() -> int` | `scripts/kilo-benchmarks/rank_coding_subagents.py:127,200,247,162,362,388` (re-verified 2026-07-06 via grep; `_atomic_write` drifted :345→:362 and `main` :371→:388 since 2026-07-05 as sibling `rank_coding_subagents.py` gained the CODING fallback loader for the subagent-runs flywheel) |
| `daily_refresh.sh` insertion point | New rankers added as steps after `rank_coding_subagents.py` (step 8) and `rank_task_subagents.py` (step 8b — sibling-added 2026-07-06), before `export_models_browser.py` (step 9). Insert the 4 new rank_{tts,stt,translation,image_gen} steps immediately BEFORE `_step "export_models_browser"` at :369, forming steps 8c–8f. | `scripts/kilo-benchmarks/daily_refresh.sh:349` (rank_coding_subagents invocation body) → `:358` (rank_task_subagents, sibling-inserted 2026-07-06) → insert BEFORE `:369` (export_models_browser invocation body). Header comment at `:26,30,35` documents the numbered step contract. |
| Sync manifest reality | `.windsurf/rules` at line 67; `docs/reference/kilo` at line 69 → both DO sync. `scripts/kilo-benchmarks/**` NOT in manifest → hub-only. `scripts/enforcement/check_synced_unmodified.py` runs on projects, not the hub source. | `scripts/fabrik_synced_manifest.py:66-71` (verified) |
| AGENTS.md invariants | **N/A for this plan** — no deployed service, no `compose.yaml`, no `postgres-main`, no Traefik routing, no memory limits, no ports. Hub-side tooling only. | AGENTS.md (no infra invariants touched — confirmed by scope) |
| `shape:` flag | **N/A** — no `specs/services/*.yaml` touched. Confirmed via file scope. | Spec § "Shape / infra implications" |

**fabrik-lib consult record:** Spec-inherited verdict is complete (spec § "fabrik-lib verdict"). No new capability introduced by this plan changes the verdict — every step is either stdlib, a pattern-clone from `rank_coding_subagents.py`, or a doc/rules edit.

---

## Phase A — Vendor-access catalog + specialty-catalog seed

**Goal.** Write the hand-editable vendor catalog (single source of truth for "accessible") + migrate the DB with two new columns + seed the missing TTS/STT/translation rows so Phase B's ranker has data.

### Interfaces

**Consumes:** nothing (Phase A is the root).

**Produces:**

- **File** `docs/reference/kilo/AI_VENDOR_ACCESS.md` — hand-editable markdown table. Header: `Last verified: 2026-07-05` (one line). Column order fixed: `| Vendor | DB provider(s) | Auth mechanism | Status | Credits/quota | Notes |`. Status ∈ {`✅`, `⚠️`, `❌`}. `DB provider(s)` = comma-separated list of `agents.provider` values (exact match).
- **DB migration.** Two new columns on `agents`:
  - `quality_elo REAL` (default `NULL` — Arena Elo for `image_gen` + `tts` rows when the model appears on ArtificialAnalysis or HF TTS Arena; NULL means no quality signal).
  - `reachable_with_existing_keys INTEGER NOT NULL DEFAULT 0` (1 = catalog says accessible, 0 = new-vendor).
- **Function** `parse_vendor_catalog(md_path: pathlib.Path) -> dict[str, bool]` in `seed_specialty_catalog.py` — returns `{provider_id: True_if_accessible}` where accessible = status is ✅ or ⚠️.
- **Function** `seed_specialty_rows(conn: sqlite3.Connection, accessible: dict[str, bool]) -> int` in `seed_specialty_catalog.py` — returns count of rows inserted-or-updated. Idempotent.
- **CLI** `python scripts/kilo-benchmarks/seed_specialty_catalog.py` — exit 0 on success, non-zero on parse/DB error.

### Steps

**A.1 — Write `AI_VENDOR_ACCESS.md`** (hand-authored from Özgür's stated access; sets ground truth for Phase A.4).

Vendors to include (grouped): **LLM gateways** — OpenRouter (`openai`, `anthropic`, `google`, `x-ai`, `meta-llama`, `qwen`, `deepseek`, `mistralai`, `moonshotai`, `z-ai`, `minimax`, `bytedance-seed`, `microsoft`, `nvidia`, `hexgrad`, `canopylabs`, `zyphra`, `sesame`); Kilo CLI (peer gateway); Claude Max direct (`anthropic` via Claude Code). **Specialty vendors** — Replicate (`stability`, `bfl-via-replicate`, `recraft-ai` official-model route); Fal.ai (`bfl` via Fal); BFL direct (deprecated per AFCL — mark ❌); Recraft direct (`recraft`); Soniox (3 keys — mark ✅ for `soniox`); ElevenLabs (`elevenlabs` — free tier ✅); Alibaba DashScope (`qwen`, `qwen-mt-turbo`); Anthropic direct API (mark ⚠️ — subscription-billed, keep for `fabrik ai generate` content utilities per user's stated rule). **Direct-API vendors that need signup** — OpenAI direct, Google Cloud, Azure, Deepgram, AssemblyAI, DeepL (Free tier ✅ up to 500K chars/mo). **Web-only accounts** — Gemini web (❌ for CLI use), GPT web (❌ for CLI use), Perplexity web (❌).

**Gate A.1:**
```bash
test -f docs/reference/kilo/AI_VENDOR_ACCESS.md && \
head -1 docs/reference/kilo/AI_VENDOR_ACCESS.md | grep -qE "^Last verified: 2026-07-05" && \
grep -cE "^\| " docs/reference/kilo/AI_VENDOR_ACCESS.md | awk '$1 > 15 { exit 0 } { exit 1 }' && \
echo "A.1 OK"
# Expected: A.1 OK (file exists, freshness stamp on line 1, ≥16 table lines)
```

**A.2 — TDD: write the highest-risk test FIRST** (`scripts/kilo-benchmarks/tests/test_seed_specialty_catalog.py`).

The risky path is the catalog→seed join: if `parse_vendor_catalog` returns wrong provider IDs, every seeded row lands with `reachable_with_existing_keys=0` and the suggester returns empty pools for everything. Test:

```python
def test_parse_vendor_catalog_maps_status_to_accessibility(tmp_path):
    md = tmp_path / "AI_VENDOR_ACCESS.md"
    md.write_text(
        "Last verified: 2026-07-05\n\n"
        "| Vendor | DB provider(s) | Auth | Status | Credits | Notes |\n"
        "|---|---|---|---|---|---|\n"
        "| OpenRouter | openai, anthropic | env | ✅ | $50 | ok |\n"
        "| BFL direct | bfl | env | ❌ | none | deprecated |\n"
        "| ElevenLabs | elevenlabs | env | ⚠️ | low | free tier |\n"
    )
    from seed_specialty_catalog import parse_vendor_catalog
    result = parse_vendor_catalog(md)
    assert result == {"openai": True, "anthropic": True, "bfl": False, "elevenlabs": True}
```

**Gate A.2 (must FAIL RED first):**
```bash
cd scripts/kilo-benchmarks && python -m pytest tests/test_seed_specialty_catalog.py::test_parse_vendor_catalog_maps_status_to_accessibility -x 2>&1 | tail -20
# Expected before A.3: FAILED (ModuleNotFoundError: No module named 'seed_specialty_catalog') — confirms red-for-the-right-reason.
```

**A.3 — Write the DB migration + seeder skeleton** (`scripts/kilo-benchmarks/seed_specialty_catalog.py`).

Header: `# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_seed_specialty_catalog.py` (script-coupling per CLAUDE.md).

Structure:
```python
from __future__ import annotations
import re, sqlite3, sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "kilo_agents.db"
CATALOG_PATH = Path(__file__).parent.parent.parent / "docs" / "reference" / "kilo" / "AI_VENDOR_ACCESS.md"

MIGRATION_SQL = [
    "ALTER TABLE agents ADD COLUMN quality_elo REAL",
    "ALTER TABLE agents ADD COLUMN reachable_with_existing_keys INTEGER NOT NULL DEFAULT 0",
]

def _migrate(conn: sqlite3.Connection) -> None:
    """Idempotent — skips columns that already exist."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(agents)")}
    for stmt in MIGRATION_SQL:
        col = stmt.split()[-2]  # "ALTER TABLE ... ADD COLUMN <col> <type>"
        if col not in existing:
            conn.execute(stmt)

def parse_vendor_catalog(md_path: Path) -> dict[str, bool]:
    """Return {db_provider_id: accessible_bool}. ✅/⚠️ → True; ❌ or missing → False."""
    text = md_path.read_text(encoding="utf-8")
    accessible: dict[str, bool] = {}
    for line in text.splitlines():
        if not line.startswith("| ") or line.startswith("| ---") or line.startswith("| Vendor"):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 4:
            continue
        _vendor, providers, _auth, status = cols[0], cols[1], cols[2], cols[3]
        is_accessible = "✅" in status or "⚠️" in status
        for pid in [p.strip() for p in providers.split(",") if p.strip()]:
            accessible[pid] = is_accessible
    return accessible

def seed_specialty_rows(conn: sqlite3.Connection, accessible: dict[str, bool]) -> int:
    """Insert missing TTS/STT/translation rows from specialty_pricing.PRICING; set reachable flag."""
    # Load PRICING lazily to avoid import-order pain.
    sys.path.insert(0, str(Path(__file__).parent))
    from specialty_pricing import PRICING
    count = 0
    for model_id, meta in PRICING.items():
        service_type = _infer_service_type(meta)
        if service_type not in {"tts", "stt", "translation", "image_gen"}:
            continue
        provider = model_id.split("/", 1)[0]
        reachable = 1 if accessible.get(provider) else 0
        cost_per_m = _cost_per_million(meta)
        pricing_unit = _pricing_unit(meta)
        conn.execute(
            "INSERT OR IGNORE INTO agents (id, api_id, name, provider, service_type, "
            "pricing_unit, input_cost_per_m, output_cost_per_m, status, "
            "reachable_with_existing_keys, last_verified) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'active', ?, DATE('now'))",
            (model_id, model_id, model_id, provider, service_type, pricing_unit, cost_per_m, reachable)
        )
        # Backfill reachable flag on existing rows (idempotent)
        conn.execute(
            "UPDATE agents SET reachable_with_existing_keys = ? WHERE id = ?",
            (reachable, model_id),
        )
        count += 1
    return count

def _infer_service_type(meta: dict) -> str:
    if "per_image" in meta or "per_generation" in meta and meta.get("via") in {"fal_ai", "recraft_direct", "replicate", "replicate_official", "openrouter"}:
        return "image_gen"
    if "per_char" in meta:
        return "tts" if meta.get("via") not in {"dashscope_direct"} else "translation"
    if "per_minute" in meta:
        return "stt"
    if "per_generation" in meta:
        return "music_gen"
    return "unknown"

def _cost_per_million(meta: dict) -> float:
    if "per_image" in meta: return meta["per_image"] * 1_000_000
    if "per_char" in meta: return meta["per_char"] * 1_000_000
    if "per_minute" in meta: return meta["per_minute"] * 1_000_000
    if "per_generation" in meta: return meta["per_generation"] * 1_000_000
    return 0.0

def _pricing_unit(meta: dict) -> str:
    if "per_image" in meta: return "image"
    if "per_char" in meta: return "M-chars"
    if "per_minute" in meta: return "audio-min"
    if "per_generation" in meta: return "audio-min"
    return "M-tokens"

def main() -> int:
    accessible = parse_vendor_catalog(CATALOG_PATH)
    conn = sqlite3.connect(DB_PATH)
    try:
        _migrate(conn)
        n = seed_specialty_rows(conn, accessible)
        conn.commit()
        print(f"seeded/updated {n} specialty rows; {sum(accessible.values())} accessible providers")
    finally:
        conn.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

**Gate A.3:**
```bash
cd scripts/kilo-benchmarks && python -m pytest tests/test_seed_specialty_catalog.py::test_parse_vendor_catalog_maps_status_to_accessibility -x 2>&1 | tail -5
# Expected: 1 passed
```

**A.4 — Populate `quality_elo` for image_gen + tts rows from the two live Arenas.**

Extend `seed_specialty_catalog.py` with a `_seed_quality_elo(conn)` function that hardcodes the top-tier Elo scores from the spec's cited sources (grounded 2026-07-05):

- `image_gen` (from https://artificialanalysis.ai/image/arena, spec table row 8): `openai/gpt-image-2 → 1339`, `openai/gpt-5.4-image-2 → 1281` (Reve 2.0 proxy — mark as estimate if row exists), `microsoft/mai-image-2.5 → 1271`, `google/gemini-3-pro-image → 1265` (HiDream proxy), `google/gemini-3.1-flash-image → 1230` (conservative). Only set the value if the exact `id` matches; otherwise leave NULL.
- `tts` (from https://huggingface.co/spaces/TTS-AGI/TTS-Arena-V2, spec row 9): the top Elo scores are Vocu V3.0 = 1581, Inworld TTS MAX = 1579 — but the DB has no Vocu/Inworld rows. Leave `tts` Elo NULL until a Phase-A follow-up (recorded as Residual #1) — this is honest ("no matching row" beats "wrong assignment").

Add test:
```python
def test_seed_quality_elo_only_touches_matching_ids(tmp_conn_with_rows):
    from seed_specialty_catalog import _seed_quality_elo
    _seed_quality_elo(tmp_conn_with_rows)
    row = tmp_conn_with_rows.execute("SELECT quality_elo FROM agents WHERE id='openai/gpt-image-2'").fetchone()
    assert row[0] == 1339
    # Unmatched row stays NULL
    unmatched = tmp_conn_with_rows.execute("SELECT quality_elo FROM agents WHERE id='stability/sdxl'").fetchone()
    assert unmatched[0] is None
```

**Gate A.4:**
```bash
cd scripts/kilo-benchmarks && python -m pytest tests/test_seed_specialty_catalog.py -x 2>&1 | tail -5
# Expected: 2 passed (or 3 if A.2 test kept)
```

**A.5 — Run the seeder against the real DB, verify counts.**

```bash
python scripts/kilo-benchmarks/seed_specialty_catalog.py
sqlite3 scripts/kilo-benchmarks/kilo_agents.db "SELECT service_type, COUNT(*) FROM agents WHERE reachable_with_existing_keys=1 AND status='active' GROUP BY service_type;"
sqlite3 scripts/kilo-benchmarks/kilo_agents.db "SELECT COUNT(*) FROM agents WHERE quality_elo IS NOT NULL;"
```

**Gate A.5:**
```bash
# Post-seed row counts
python -c "
import sqlite3
c = sqlite3.connect('scripts/kilo-benchmarks/kilo_agents.db')
n = dict(c.execute('SELECT service_type, COUNT(*) FROM agents WHERE reachable_with_existing_keys=1 AND status=\"active\" GROUP BY service_type').fetchall())
q = c.execute('SELECT COUNT(*) FROM agents WHERE quality_elo IS NOT NULL').fetchone()[0]
assert n.get('tts', 0) >= 3, f'expected ≥3 accessible tts, got {n}'
assert n.get('stt', 0) >= 1, f'expected ≥1 accessible stt, got {n}'
assert n.get('translation', 0) >= 1, f'expected ≥1 accessible translation, got {n}'
assert n.get('image_gen', 0) >= 5, f'expected ≥5 accessible image_gen, got {n}'
assert q >= 3, f'expected ≥3 image_gen rows with quality_elo, got {q}'
print('A.5 gate OK', n, 'quality_elo populated:', q)
"
# Expected: A.5 gate OK ...
```

**A.5.5 — Backfill `perf_seconds` on the seeded rows via `microbench_specialty.py`** (added 2026-07-07, closes Residual #3).

The Sunday cron would eventually populate `perf_seconds` / `output_tokens_per_sec` on the new rows, but the ranker needs the speed axis on day 1 — running microbench here means Phase B's Pareto frontier includes speed from the first invocation, not just cost + quality_elo.

Cohort selection at `scripts/kilo-benchmarks/microbench_specialty.py:165` is exactly `agents.status='active' AND service_type IN ('image_gen','tts','music_gen','stt','translation') AND perf_seconds IS NULL` — the seeded rows drop in automatically.

Sequence:
```bash
# 1. Dry-run first — shows cost estimate + row count, spends nothing.
python scripts/kilo-benchmarks/microbench_specialty.py --dry-run 2>&1 | tail -20
# 2. Real run, bounded by --limit so a runaway cohort can't blow COST_CAP_USD=10.0.
#    Set --limit to the count of newly-seeded rows from A.5 gate (typically ≤15).
#    Re-runs are safe: successful rows have perf_seconds NON-NULL and drop out of the
#    cohort automatically (`perf_seconds IS NULL` filter at :165).
python scripts/kilo-benchmarks/microbench_specialty.py --limit 20 2>&1 | tail -30
```

**Gate A.5.5:**
```bash
# Assert ≥50% of the specialty rows seeded by A.5 now carry a real perf_seconds bench.
python -c "
import sqlite3
c = sqlite3.connect('scripts/kilo-benchmarks/kilo_agents.db')
seeded = c.execute(\"SELECT COUNT(*) FROM agents WHERE reachable_with_existing_keys=1 AND status='active' AND service_type IN ('tts','stt','translation','image_gen','music_gen')\").fetchone()[0]
benched = c.execute(\"SELECT COUNT(*) FROM agents WHERE reachable_with_existing_keys=1 AND status='active' AND service_type IN ('tts','stt','translation','image_gen','music_gen') AND perf_seconds IS NOT NULL\").fetchone()[0]
# Coverage floor: at least half — vendor timeouts / rate-limits are non-fatal and re-runs pick up the tail.
assert seeded > 0, 'no specialty rows to bench — A.5 gate should have caught this'
assert benched * 2 >= seeded, f'perf_seconds coverage {benched}/{seeded} < 50% — re-run microbench_specialty.py or add --limit'
print(f'A.5.5 gate OK — perf_seconds populated on {benched}/{seeded} accessible specialty rows')
"
```

Partial coverage is acceptable — the ranker treats NULL speed as "no speed signal, rank on cost + quality." If a specific vendor's bench keeps timing out or hitting a paid-tier wall, note it in `docs/LESSONS_LEARNT.md` and move on; do not block Phase A on it.

**A.6 — Doc-sync + review + commit.**

1. Update `CHANGELOG.md` — append under `## [Unreleased]`:
   ```
   ### Added — best-model-suggester Phase A: vendor catalog + specialty-catalog seed (2026-07-05)
   AI_VENDOR_ACCESS.md (hand-editable) + seeded TTS/STT/translation rows + quality_elo column
   populated from Arena Elos + perf_seconds backfilled via microbench_specialty.py (A.5.5).
   ```
2. Update `INDEX.md` — add rows for the 2 new files (`AI_VENDOR_ACCESS.md`, `seed_specialty_catalog.py`).
3. `python scripts/enforcement/check_doc_sync.py` → any WARNING whose trigger file is Phase-A's diff must be resolved before commit.
4. **BLOCKING gate:** invoke `/fabrik-review` on Phase A's diff (all A.1–A.5 files). Full adversarial methodology — parallel finder subagents, refute false positives, prove-before-fix each CONFIRMED finding with a kept regression test. Loop until one full pass returns zero CONFIRMED correctness/security findings.
5. Commit:
   ```bash
   git add docs/reference/kilo/AI_VENDOR_ACCESS.md \
           scripts/kilo-benchmarks/seed_specialty_catalog.py \
           scripts/kilo-benchmarks/tests/test_seed_specialty_catalog.py \
           scripts/kilo-benchmarks/kilo_agents.db \
           CHANGELOG.md INDEX.md
   # kilo_agents.db is git-tracked (`git ls-files` confirms) — the Phase-A migration + row
   # seed mutates it and MUST be staged; otherwise the executed plan leaves a dirty
   # working tree and Phase B's tests would fail on a fresh clone.
   git commit -m "$(cat <<'EOF'
   feat(kilo-benchmarks): Phase A — vendor catalog + specialty seed + quality_elo

   Agent-Role: orchestrator
   Agent-Phase: A
   Agent-Context: added AI_VENDOR_ACCESS.md + seed_specialty_catalog.py + migrations for quality_elo and reachable_with_existing_keys

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
   )"
   ```

---

## Phase B — Suggester CLI + per-task rankers

**Goal.** Ship the CLI + 4 per-task ranker scripts + wire them into `daily_refresh.sh`. Highest-risk paths: empty-pool exit=1, mixed `pricing_unit` cost math.

### Interfaces

**Consumes from Phase A:**
- `agents` table with `quality_elo` and `reachable_with_existing_keys` columns.
- `AI_VENDOR_ACCESS.md` at `docs/reference/kilo/AI_VENDOR_ACCESS.md` (accessible set).
- `parse_vendor_catalog(md_path) -> dict[str, bool]` — imported from `seed_specialty_catalog.py`.

**Produces for Phase C:**
- **Files**: `docs/reference/kilo/{TTS,STT,TRANSLATION,IMAGE_GEN}_SELECTION.md` — one auto-generated markdown-table doc per task class. Header: `Auto-generated by rank_<task>.py. Last refresh: <ISO date>.` — atomic-written via the `_atomic_write` helper cloned from `rank_coding_subagents.py`.
- **CLI**: `python scripts/kilo-benchmarks/suggest_model.py --task {tts|stt|translation|image_gen|music_gen|llm|coding_llm} [--volume-chars N | --volume-minutes N | --volume-images N] [--quality-tier {cheap|balanced|expressive|premium}] [--language <bcp47>] [--top N] [--json]`. Exit codes: `0` = ≥1 candidate printed, `1` = empty pool (message: `NO DATA for task=<task> under accessible vendors — populate specialty catalog for this task class before suggesting.`), `2` = missing volume flag (message: `--volume-<char|minutes|images> required for --task <task>`).

**Produces for Phase C's rules pack:** the 4 file paths above (referenced by name in Phase C's rule edits).

### Subagent Mandates (Phase B is parallelizable)

**Parallel dispatch — 4 subagents, one per per-task ranker.** Each subagent:
- Vendors zero fabrik-lib modules; reads `rank_coding_subagents.py` as the template pattern.
- Owns its own `docs/reference/kilo/<TASK>_SELECTION.md` output path — disjoint owned_paths, safe for `subagents:` worktree isolation.
- Reuses a shared `_rank_service_type(conn: sqlite3.Connection, service_type: str, **volume) -> list[dict]` helper factored out of the exemplar (defined in `suggest_model.py:_rank_service_type`, imported by each ranker). Pass volume as keyword: `chars=N` for TTS/translation, `minutes=N` for STT, `images=N` for image_gen/music_gen — the impl reads these keys directly via `volume.get(<key>, 0)`. Using a different keyword (e.g. `volume_images=`) is a silent no-op — the test at B.1 exists to catch this.

Merge sequentially into master by ascending task name (image_gen → stt → translation → tts) so conflict resolution is deterministic. Conflicts should be zero — owned paths are disjoint.

**Sequential (not parallel):** `suggest_model.py` writes the shared `_rank_service_type` helper — must ship BEFORE the 4 rankers can import it. So order within Phase B: **B.1–B.4 (suggester CLI + shared helper) sequential → B.5 fan out 4 rankers in parallel → B.6 wire into daily_refresh → B.7 gate/review/commit.**

### Steps

**B.1 — TDD: write the empty-pool + missing-volume tests FIRST** (`scripts/kilo-benchmarks/tests/test_suggest_model.py`).

Highest-risk paths — get them wrong and the whole tool silently mis-guides.

```python
def test_empty_pool_exits_1(tmp_db_empty_for_task, monkeypatch, capsys):
    monkeypatch.setenv("KILO_DB", str(tmp_db_empty_for_task))
    from suggest_model import main
    rc = main(["--task", "video_gen", "--volume-images", "100"])
    out = capsys.readouterr()
    assert rc == 1
    assert "NO DATA for task=video_gen" in (out.out + out.err)

def test_missing_volume_flag_exits_2(tmp_db_with_tts_rows, monkeypatch, capsys):
    monkeypatch.setenv("KILO_DB", str(tmp_db_with_tts_rows))
    from suggest_model import main
    rc = main(["--task", "tts"])  # no --volume-chars
    out = capsys.readouterr()
    assert rc == 2
    assert "--volume-chars required" in (out.err or out.out)

def test_mixed_pricing_unit_normalizes_across_image_gen(tmp_db_image_gen_mixed, monkeypatch):
    """image row (per_image=$0.003) and M-tokens row (input_cost_per_m=$0.5, 1290 tok/image) → per-workload cost differ.
    Kwarg name is `images=` (matches _normalize_cost's `volume.get('images', 0)`); using
    `volume_images=` would silently be picked up by **volume as key 'volume_images' and cost
    would be $0.00 — the exact wrong-signature bug this test would otherwise mask."""
    monkeypatch.setenv("KILO_DB", str(tmp_db_image_gen_mixed))
    from suggest_model import _rank_service_type
    import sqlite3
    conn = sqlite3.connect(tmp_db_image_gen_mixed)
    rows = _rank_service_type(conn, "image_gen", images=1000)
    # flux-schnell: 0.003 × 1000 = $3.00
    # gemini-3.1-flash-image: 0.5 × 1290 / 1e6 × 1000 = $0.645
    schnell = next(r for r in rows if "flux-schnell" in r["id"])
    gemini = next(r for r in rows if "gemini-3.1-flash-image" in r["id"])
    assert abs(schnell["cost_usd"] - 3.00) < 0.01
    assert abs(gemini["cost_usd"] - 0.645) < 0.01
```

**Gate B.1 (must FAIL RED):**
```bash
cd scripts/kilo-benchmarks && python -m pytest tests/test_suggest_model.py -x 2>&1 | tail -10
# Expected: 3 FAILED (module not found) — red for the right reason.
```

**B.2 — Implement `suggest_model.py`** (`scripts/kilo-benchmarks/suggest_model.py`).

Header: `# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_suggest_model.py`.

Sketch (200–250 lines total):
```python
from __future__ import annotations
import argparse, json, os, sqlite3, sys
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("KILO_DB", Path(__file__).parent / "kilo_agents.db"))
CATALOG_PATH = Path(__file__).parent.parent.parent / "docs" / "reference" / "kilo" / "AI_VENDOR_ACCESS.md"

# Hardcoded per-family token-per-image estimates — no DB column, no per-row seed.
AVG_TOKENS_PER_IMAGE = {
    "google": 1290,          # gemini-*-image
    "openai": 1024,          # gpt-*-image
    "microsoft": 1024,       # mai-image-*
    "bytedance-seed": 1024,  # seedream
    "x-ai": 1024,            # grok-imagine
    "sourceful": 1024,       # riverflow
}
DEFAULT_TOKENS_PER_IMAGE = 2048  # conservative over-estimate, warns

VOLUME_FLAG_BY_TASK = {
    "tts": "--volume-chars",
    "stt": "--volume-minutes",
    "translation": "--volume-chars",
    "image_gen": "--volume-images",
    "music_gen": "--volume-images",
    "llm": None,           # LLM ranker is separate (uses rank_coding_subagents.py pattern)
    "coding_llm": None,
}

def _normalize_cost(row: dict, volume: dict) -> float:
    """Per-workload cost given the row + volume kwargs. Handles mixed pricing_unit for image_gen."""
    unit = row.get("pricing_unit") or "M-tokens"
    cpm = row.get("input_cost_per_m") or 0.0
    if unit == "image":
        return (cpm / 1_000_000) * volume.get("images", 0)
    if unit == "M-chars":
        return (cpm / 1_000_000) * volume.get("chars", 0)
    if unit == "audio-min":
        return (cpm / 1_000_000) * volume.get("minutes", 0)
    if unit == "M-tokens":
        provider = (row.get("provider") or "").split("/")[0]
        toks = AVG_TOKENS_PER_IMAGE.get(provider)
        if toks is None:
            print(f"warn: no avg_tokens_per_image for {row['id']}, using {DEFAULT_TOKENS_PER_IMAGE}", file=sys.stderr)
            toks = DEFAULT_TOKENS_PER_IMAGE
        return (cpm / 1_000_000) * toks * volume.get("images", 0)
    return 0.0

def _rank_service_type(conn: sqlite3.Connection, service_type: str, **volume) -> list[dict]:
    """Query accessible rows, compute cost, Pareto-rank on (cost ↓, quality_elo ↑ if present)."""
    rows = conn.execute(
        "SELECT id, provider, service_type, pricing_unit, input_cost_per_m, quality_elo, "
        "output_tokens_per_sec, perf_seconds, reachable_with_existing_keys "
        "FROM agents WHERE service_type = ? AND status = 'active' AND reachable_with_existing_keys = 1",
        (service_type,),
    ).fetchall()
    cols = [d[0] for d in conn.execute("SELECT * FROM agents LIMIT 0").description]
    result = []
    for r in rows:
        d = dict(zip(["id","provider","service_type","pricing_unit","input_cost_per_m","quality_elo","output_tokens_per_sec","perf_seconds","reachable_with_existing_keys"], r))
        d["cost_usd"] = _normalize_cost(d, volume)
        result.append(d)
    # Pareto: keep rows not dominated by any other on (lower cost, higher quality_elo).
    frontier = []
    for a in result:
        dominated = False
        for b in result:
            if a is b: continue
            q_a = a.get("quality_elo") or 0
            q_b = b.get("quality_elo") or 0
            if b["cost_usd"] <= a["cost_usd"] and q_b >= q_a and (b["cost_usd"] < a["cost_usd"] or q_b > q_a):
                dominated = True
                break
        if not dominated:
            frontier.append(a)
    frontier.sort(key=lambda r: (r["cost_usd"], -(r.get("quality_elo") or 0)))
    return frontier

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True, choices=list(VOLUME_FLAG_BY_TASK))
    p.add_argument("--volume-chars", type=int)
    p.add_argument("--volume-minutes", type=float)
    p.add_argument("--volume-images", type=int)
    p.add_argument("--quality-tier", choices=["cheap","balanced","expressive","premium"], default="balanced")
    p.add_argument("--language", default=None)
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    required_flag = VOLUME_FLAG_BY_TASK[args.task]
    if required_flag:
        flag_val = getattr(args, required_flag.lstrip("-").replace("-", "_"))
        if flag_val is None:
            print(f"error: {required_flag} required for --task {args.task}", file=sys.stderr)
            return 2
    conn = sqlite3.connect(DB_PATH)
    try:
        frontier = _rank_service_type(
            conn, args.task,
            chars=args.volume_chars or 0,
            minutes=args.volume_minutes or 0.0,
            images=args.volume_images or 0,
        )
    finally:
        conn.close()
    if not frontier:
        print(f"NO DATA for task={args.task} under accessible vendors — populate specialty catalog for this task class before suggesting.", file=sys.stderr)
        return 1
    top = frontier[: args.top]
    if args.json:
        print(json.dumps(top, indent=2, default=str))
    else:
        _print_markdown_table(top)
    return 0

def _print_markdown_table(rows: list[dict]) -> None:
    print(f"| Model | Provider | Cost (USD) | quality_elo | Notes |")
    print(f"|---|---|---:|---:|---|")
    for r in rows:
        note = "low_balance" if r.get("_low_balance") else ""
        q = f"{r['quality_elo']:.0f}" if r.get("quality_elo") else "—"
        print(f"| `{r['id']}` | {r['provider']} | ${r['cost_usd']:.4f} | {q} | {note} |")

if __name__ == "__main__":
    sys.exit(main())
```

**Gate B.2:**
```bash
cd scripts/kilo-benchmarks && python -m pytest tests/test_suggest_model.py -x 2>&1 | tail -10
# Expected: 3 passed
```

**B.3 — Smoke-test against the real DB.**

```bash
python scripts/kilo-benchmarks/suggest_model.py --task tts --volume-chars 130000 --top 3
python scripts/kilo-benchmarks/suggest_model.py --task video_gen --volume-images 100 ; echo "exit=$?"
python scripts/kilo-benchmarks/suggest_model.py --task tts ; echo "exit=$?"
```

**Gate B.3:**
```bash
# TTS returns ≥1 row (exit 0), video_gen exits 1, tts-without-volume exits 2.
python -c "
import subprocess
r1 = subprocess.run(['python','scripts/kilo-benchmarks/suggest_model.py','--task','tts','--volume-chars','130000','--top','3'], capture_output=True, text=True)
assert r1.returncode == 0 and '| \`' in r1.stdout, f'tts failed: {r1.stdout}{r1.stderr}'
r2 = subprocess.run(['python','scripts/kilo-benchmarks/suggest_model.py','--task','video_gen','--volume-images','100'], capture_output=True, text=True)
assert r2.returncode == 1 and 'NO DATA for task=video_gen' in r2.stderr, f'video_gen didn\\'t exit 1: {r2.returncode} {r2.stderr}'
r3 = subprocess.run(['python','scripts/kilo-benchmarks/suggest_model.py','--task','tts'], capture_output=True, text=True)
assert r3.returncode == 2 and 'required' in r3.stderr, f'missing-volume didn\\'t exit 2: {r3.returncode} {r3.stderr}'
print('B.3 gate OK')
"
```

**B.4 — Extract shared ranker helper for Phase B.5 subagents.**

`_rank_service_type` already lives in `suggest_model.py` (B.2). Verify it's importable:
```bash
python -c "from suggest_model import _rank_service_type; print(_rank_service_type)"
# Expected: <function _rank_service_type at 0x...>
```

**B.5 — Fan out 4 parallel subagents, one per per-task ranker.**

Each subagent's owned path:
- Subagent B.5a: `scripts/kilo-benchmarks/rank_tts.py` + writes `docs/reference/kilo/TTS_SELECTION.md`
- Subagent B.5b: `scripts/kilo-benchmarks/rank_stt.py` + writes `docs/reference/kilo/STT_SELECTION.md`
- Subagent B.5c: `scripts/kilo-benchmarks/rank_translation.py` + writes `docs/reference/kilo/TRANSLATION_SELECTION.md`
- Subagent B.5d: `scripts/kilo-benchmarks/rank_image_gen.py` + writes `docs/reference/kilo/IMAGE_GEN_SELECTION.md`

**Each subagent prompt** (self-contained, cold-start):
> You are executing Phase B.5<x> of the best-model-suggester plan as an isolated subagent.
> **Assignment.** Write `scripts/kilo-benchmarks/rank_<task>.py` that (a) imports `from suggest_model import _rank_service_type`, (b) calls it with `service_type='<task>'` and a canonical benchmark volume (`tts: chars=100_000`, `stt: minutes=60.0`, `translation: chars=100_000`, `image_gen: images=100`), (c) renders top-10 as markdown, (d) atomic-writes to `docs/reference/kilo/<TASK>_SELECTION.md` with a `Last refresh: YYYY-MM-DD` header. Clone the layout pattern from `scripts/kilo-benchmarks/rank_coding_subagents.py` (functions `_atomic_write`, `_safe_md_id`, `_fmt_or_dash`).
> **Header:** `# AFTER-EDIT: docs/reference/kilo/<TASK>_SELECTION.md`
> **Test coverage:** add one test to `scripts/kilo-benchmarks/tests/test_rank_specialty.py` (shared file — take an append-only lock, use a unique test name `test_rank_<task>_emits_valid_markdown`) that runs `rank_<task>.main()` against a tmp DB with 2 seeded rows and asserts the output MD contains those model IDs.
> Commit to a branch `phase-B-task-5<x>` with trailer `Agent-Role: subagent, Agent-Phase: B, Agent-Task: 5<x>, Agent-Context: <one-line>`. Do NOT merge — orchestrator handles that.

**Gate B.5 (post-merge):**
```bash
ls docs/reference/kilo/{TTS,STT,TRANSLATION,IMAGE_GEN}_SELECTION.md
head -1 docs/reference/kilo/TTS_SELECTION.md | grep -q "Last refresh:"
cd scripts/kilo-benchmarks && python -m pytest tests/test_rank_specialty.py -x 2>&1 | tail -5
# Expected: 4 files listed; header present; 4 passed
```

**B.6 — Wire the 4 rankers into `daily_refresh.sh`** — insert immediately BEFORE `_step "export_models_browser" …` at `:369`. Note that as of 2026-07-06 the sibling subagent-runs-lean plan inserted `_step "rank_task_subagents"` at `:358` between `_step "rank_coding_subagents"` (:349) and `_step "export_models_browser"` (:369), so the 4 new rankers land AFTER `rank_task_subagents` at :358 and immediately before `export_models_browser` at :369 — forming steps 8c–8f in the header numbering. Match the exact wrapper convention: the real function is `_step` (underscore prefix), args are **space-separated** (`"$VENV_PY" "$KB/<script>.py"`, not concatenated), and each invocation ends with a trailing `\` and an `|| echo "[daily_refresh] <name> failed (non-fatal)"` fallback so a single ranker crash can't short-circuit the pipeline (script header comment lines 41-43 spell out this convention).

Insert block (verbatim indentation — 2 spaces to match the enclosing `{ … }` block):
```bash
  _step "rank_tts" "$VENV_PY" "$KB/rank_tts.py" \
    || echo "[daily_refresh] rank_tts failed (non-fatal)"
  _step "rank_stt" "$VENV_PY" "$KB/rank_stt.py" \
    || echo "[daily_refresh] rank_stt failed (non-fatal)"
  _step "rank_translation" "$VENV_PY" "$KB/rank_translation.py" \
    || echo "[daily_refresh] rank_translation failed (non-fatal)"
  _step "rank_image_gen" "$VENV_PY" "$KB/rank_image_gen.py" \
    || echo "[daily_refresh] rank_image_gen failed (non-fatal)"
```

**Gate B.6:**
```bash
bash -n scripts/kilo-benchmarks/daily_refresh.sh && echo "syntax OK"
# _step prefix (real function name), 6 rank_* invocations expected: 2 existing (rank_coding_subagents, rank_task_subagents — sibling-added 2026-07-06) + 4 new.
n=$(grep -cE '^\s*_step "rank_' scripts/kilo-benchmarks/daily_refresh.sh)
[ "$n" = "6" ] && echo "step-count OK ($n)" || { echo "expected 6 _step \"rank_ lines, got $n"; exit 1; }
# Insertion ordering: rank_coding_subagents + rank_task_subagents must appear BEFORE the 4 new rankers, all before export_models_browser.
awk '/_step "rank_coding_subagents"/{c=NR} /_step "rank_task_subagents"/{t=NR} /_step "rank_image_gen"/{i=NR} /_step "export_models_browser"/{e=NR} END{ if(c<i && t<i && i<e) print "order OK"; else { printf "bad order: rank_coding_subagents@%d rank_task_subagents@%d rank_image_gen@%d export_models_browser@%d\n", c, t, i, e; exit 1 } }' scripts/kilo-benchmarks/daily_refresh.sh
# Expected: syntax OK; step-count OK (6); order OK
```

**B.7 — Doc-sync + review + commit.**

1. `CHANGELOG.md` append under `## [Unreleased]`:
   ```
   ### Added — best-model-suggester Phase B: suggest_model.py + 4 per-task rankers (2026-07-05)
   Pareto-ranked CLI (empty-pool exit=1, missing-volume exit=2) + TTS/STT/TRANSLATION/IMAGE_GEN
   selection MDs regenerated daily.
   ```
2. `INDEX.md` — add rows for `suggest_model.py`, `rank_{tts,stt,translation,image_gen}.py`, and the 4 `*_SELECTION.md` files.
3. `python scripts/enforcement/check_doc_sync.py` — resolve any WARN whose trigger file is in this diff.
4. **BLOCKING gate:** invoke `/fabrik-review` on Phase B's changed surface (all of B.1–B.6). Full adversarial methodology, parallel finders, refute → prove-before-fix, LOOP until zero CONFIRMED findings.
5. Commit (explicit paths, orchestrator squash):
   ```bash
   git add scripts/kilo-benchmarks/suggest_model.py \
           scripts/kilo-benchmarks/rank_tts.py scripts/kilo-benchmarks/rank_stt.py \
           scripts/kilo-benchmarks/rank_translation.py scripts/kilo-benchmarks/rank_image_gen.py \
           scripts/kilo-benchmarks/tests/test_suggest_model.py \
           scripts/kilo-benchmarks/tests/test_rank_specialty.py \
           scripts/kilo-benchmarks/daily_refresh.sh \
           docs/reference/kilo/TTS_SELECTION.md docs/reference/kilo/STT_SELECTION.md \
           docs/reference/kilo/TRANSLATION_SELECTION.md docs/reference/kilo/IMAGE_GEN_SELECTION.md \
           CHANGELOG.md INDEX.md
   git commit -m "$(cat <<'EOF'
   feat(kilo-benchmarks): Phase B — suggest_model.py + 4 per-task rankers

   Merged-From: phase-B-task-5a (rank_tts), phase-B-task-5b (rank_stt), phase-B-task-5c (rank_translation), phase-B-task-5d (rank_image_gen)
   Agent-Role: orchestrator
   Agent-Phase: B
   Agent-Context: shipped Pareto ranker CLI + 4 per-task selection MDs; wired daily_refresh
   Conflicts-Resolved: 0

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
   )"
   ```

---

## Phase C — Rules-pack integration

**Goal.** Extend `.windsurf/rules/ai/00-ai-model-selection.md` so a coding agent in ANY project sees the selection MDs (including the now-un-orphaned `CODING_SUBAGENT_SELECTION.md`) and the accessibility discipline.

### Interfaces

**Consumes from Phase B:**
- File paths: `docs/reference/kilo/{TTS,STT,TRANSLATION,IMAGE_GEN,CODING_SUBAGENT}_SELECTION.md` (referenced by exact name in the rule pack).
- File path: `docs/reference/kilo/AI_VENDOR_ACCESS.md` (referenced in the advisory line).

**Produces:** the edited `.windsurf/rules/ai/00-ai-model-selection.md`. No downstream code consumers within this plan.

### Steps

**C.1 — Insert the "Selection MDs — read before recommending" block** after `## Selection workflow` (at `.windsurf/rules/ai/00-ai-model-selection.md:20`, verified via grep).

Content:
```markdown
## Selection MDs — read before recommending

Every recommendation the operator will actually run should be grounded in the corresponding auto-generated selection doc + the vendor-access catalog. All five live in `docs/reference/kilo/` and are governance-synced to every project.

| Task class | Selection MD | Regenerated by |
|---|---|---|
| Coding LLMs (agents/subagents) | `docs/reference/kilo/CODING_SUBAGENT_SELECTION.md` | `rank_coding_subagents.py` (daily) |
| TTS | `docs/reference/kilo/TTS_SELECTION.md` | `rank_tts.py` (daily) |
| STT | `docs/reference/kilo/STT_SELECTION.md` | `rank_stt.py` (daily) |
| Translation | `docs/reference/kilo/TRANSLATION_SELECTION.md` | `rank_translation.py` (daily) |
| Image generation | `docs/reference/kilo/IMAGE_GEN_SELECTION.md` | `rank_image_gen.py` (daily) |

**Vendor access:** `docs/reference/kilo/AI_VENDOR_ACCESS.md` is the single source of truth for which vendors the operator can call today. Rows with Status ✅ or ⚠️ are accessible (⚠️ = accessible but low balance — pick a ✅ peer if one is on the Pareto frontier).
```

**C.2 — Insert the advisory line** at the top of `## Selection workflow` (before the numbered list).

Content:
```markdown
> **Before recommending any AI model for the operator to actually run:** read the applicable `docs/reference/kilo/*_SELECTION.md` and consult `docs/reference/kilo/AI_VENDOR_ACCESS.md`. If the model you want to recommend is not in the accessible set, either flag it clearly ("**new vendor — needs signup + payment method**") or pick a peer from the accessible set. When in doubt, run `python scripts/kilo-benchmarks/suggest_model.py --task <task> --volume-<unit> <N>` — it hard-fails with exit=1 if no data exists for that task class, so you can't extrapolate from thin air.
```

**Gate C.1+C.2:**
```bash
# All five selection MDs referenced + AI_VENDOR_ACCESS.md referenced + advisory present.
python -c "
import pathlib
txt = pathlib.Path('.windsurf/rules/ai/00-ai-model-selection.md').read_text()
mds = ['CODING_SUBAGENT_SELECTION', 'TTS_SELECTION', 'STT_SELECTION', 'TRANSLATION_SELECTION', 'IMAGE_GEN_SELECTION']
missing = [m for m in mds if m not in txt]
assert not missing, f'missing refs: {missing}'
assert 'AI_VENDOR_ACCESS.md' in txt
assert 'suggest_model.py' in txt
print('C gate OK — 5 selection MDs + catalog + suggester all referenced')
"
```

**C.3 — Doc-sync + review + commit.**

1. `CHANGELOG.md` append:
   ```
   ### Changed — ai/00-ai-model-selection.md now references all 5 selection MDs + vendor access (2026-07-05)
   Advisory: read the applicable *_SELECTION.md + AI_VENDOR_ACCESS.md before recommending;
   suggest_model.py provides programmatic hard-fail on empty pools.
   ```
2. `python scripts/enforcement/check_doc_sync.py` — resolve any WARN whose trigger file is in this diff.
3. **BLOCKING gate:** invoke `/fabrik-review` on Phase C's diff — small surface, but still full methodology (an agent misreading the advisory or a broken link is a real risk).
4. Commit:
   ```bash
   git add .windsurf/rules/ai/00-ai-model-selection.md CHANGELOG.md
   git commit -m "$(cat <<'EOF'
   feat(rules): Phase C — ai/00 references all 5 selection MDs + AI_VENDOR_ACCESS

   Agent-Role: orchestrator
   Agent-Phase: C
   Agent-Context: added Selection MDs block + advisory line pointing to suggest_model.py hard-fail

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
   )"
   ```

---

## Phase E — Watch-list vendors + GPU providers table + browser tab + upsell watcher

**Goal.** Ship the SaaS-ready catalog of every provider (accessible + candidate) so the same suggester serves current-personal use ("rank from accessible only") AND future-SaaS use ("full catalog, per-operator filter"). Add the `💡 Consider signup:` upsell line when a locked-out row Pareto-dominates the accessible frontier by ≥30%.

### Interfaces

**Consumes from Phase A/B/C:**
- `agents.reachable_with_existing_keys` column (Phase A migration).
- `AI_VENDOR_ACCESS.md` at `docs/reference/kilo/AI_VENDOR_ACCESS.md` (Phase A).
- `_rank_service_type(conn, service_type, **volume)` from `suggest_model.py` (Phase B.2).
- `parse_vendor_catalog(md_path)` from `seed_specialty_catalog.py` (Phase A.3) — reused for updating watch-list rows when catalog changes.
- `_atomic_write(path, content)` from `rank_coding_subagents.py:345` — reused for `CANDIDATE_SIGNUPS.md`.

**Produces:**
- **DB migration.** New table `gpu_providers` + new column `agents.signup_trigger TEXT`.
- **Function** `scrape_gpu_prices() -> dict[str, dict]` in `scrape_gpu_prices.py` — returns `{provider_id: {sku: {tier: usd_per_hour}}}` from Vast/RunPod/Hyperbolic/Novita public pages via vendored `libs.web_scrape.WebScraper`.
- **Function** `_migrate_gpu_providers(conn: sqlite3.Connection) -> None` in `seed_watchlist_and_gpu.py` — creates `gpu_providers` table + adds `agents.signup_trigger TEXT` column. Idempotent (`PRAGMA table_info` skip pattern from Phase A's `_migrate()` — same convention, but keep this migration in a distinct dedicated function so a subagent that owns only Phase E can import it independently for the E.2 test without pulling in Phase A's specialty-catalog seeder). MUST be top-level and importable — the E.2 test does `from seed_watchlist_and_gpu import _migrate_gpu_providers`.
- **Function** `seed_watchlist_and_gpu(conn: sqlite3.Connection) -> tuple[int, int]` in `seed_watchlist_and_gpu.py` — calls `_migrate_gpu_providers(conn)` internally, then upserts inference watch-list rows into `agents` and GPU rows into `gpu_providers`. Returns `(agents_upserted, gpu_upserted)`. Idempotent.
- **File** `docs/reference/kilo/CANDIDATE_SIGNUPS.md` — auto-generated markdown table by `rank_candidate_signups.py`. Header: `Last refresh: YYYY-MM-DD`.
- **CLI additions to `suggest_model.py`:** `--strict` flag suppresses upsell line; upsell logic reads full unfiltered set and prints stderr line only if best-locked-out Pareto-dominates best-accessible by ≥`UPSELL_MIN_SAVING_PCT` (module constant, default `0.30`).
- **HTML modification to `models_browser_template.html`** — per spec § E.3 (CONVERGED architecture): new `<span class="tab" data-tab="rent-gpu">` and `<span class="tab" data-tab="candidates">` chips in the selector strip (matches `models_browser_template.html:651-659` convention); dual `<tbody>` swap (`#rows-agents` default vs. `#rows-gpu` for rent-gpu tab vs. `#rows-candidates` for candidates tab — because `gpu_providers` schema doesn't map onto `agents`, a shared `<tbody>` would break sort/filter typing); new `<th data-sort="quality_elo" data-tabs="image voice">Q-Elo</th>` and `<th data-tabs="overview reasoning coding translation transcription voice image video ocr rent-gpu candidates">Reach</th>` columns with cell renderers. JS `activeTab` at `models_browser_template.html:931` extended to hide/show the correct `<tbody>` on tab switch.

### Steps

### Subagent Mandates (Phase E is parallelizable after E.4)

**Sequential prefix (must ship before parallel fan-out):**
- **E.1 → E.2 → E.3 → E.4**: vendor `web-scrape` (E.1), write tests (E.2), migrate DB + write seeder (E.3), write scraper (E.4). Sequential because E.3 depends on E.1's vendored copy for the future scraper import, and E.4 depends on E.3's `gpu_providers` schema being live to `.notes`-flag stale prices.

**Parallel fan-out — 4 subagents dispatched in a single message after E.4 completes:**
- **Subagent E.5a** → owns `scripts/kilo-benchmarks/suggest_model.py` (extension) + `scripts/kilo-benchmarks/tests/test_upsell_watcher.py` — adds `--strict` flag + `UPSELL_MIN_SAVING_PCT` constant + upsell watcher logic + 3 tests.
- **Subagent E.5b** → owns `scripts/kilo-benchmarks/rank_candidate_signups.py` + updates `docs/reference/kilo/CANDIDATE_SIGNUPS.md` on first run — pattern-clones `rank_coding_subagents.py`, queries the union of `agents WHERE reachable_with_existing_keys=0` and `gpu_providers WHERE reachable_with_existing_keys=0`.
- **Subagent E.5c** → owns `scripts/kilo-benchmarks/models_browser_template.html` (edit) — adds 2 new `<span class="tab" data-tab="...">` chips (rent-gpu + candidates) in the selector strip, dual `<tbody>` swap logic in the `activeTab` handler at `:931`, `<th data-sort="quality_elo" data-tabs="image voice">` column, `<th data-tabs="...">Reach</th>` badge column with cell renderer, and CSS for `.reach-badge` variants; regenerates `models_browser.html` for the SC #15-#18 checks.
- **Subagent E.5d** → owns `.windsurf/rules/ai/00-ai-model-selection.md` — inserts the `## Candidate signup vendors` section after `## Fabrik defaults` (line 49).

All 4 subagents use `isolation: "worktree"` so their file mutations cannot collide. Owned paths are disjoint (verified by inspection of File Scope). Orchestrator merges sequentially in ascending subagent letter order (E.5a → E.5b → E.5c → E.5d) — no cross-file conflicts possible because owned sets are disjoint; `INDEX.md` + `CHANGELOG.md` updates land in the orchestrator's E.10 commit, not the subagent commits, to avoid a 4-way conflict on the shared `## [Unreleased]` block.

**Sequential tail:**
- **E.9 → E.10**: wire steps into `daily_refresh.sh` (E.9 — orchestrator, small) and doc-sync + review + commit (E.10 — orchestrator).

Wall-clock: parallel fan-out cuts the E.5–E.8 wave to the slowest single subagent instead of the sum. **Step-to-subagent map** (steps E.5–E.8 below stay named as-is for readability; a fresh executor picks the matching subagent from this table):

| Step | Subagent | Owned paths |
|---|---|---|
| E.5 (suggest_model.py upsell + tests) | E.5a | `suggest_model.py`, `tests/test_upsell_watcher.py` |
| E.6 (rank_candidate_signups.py) | E.5b | `rank_candidate_signups.py`, `docs/reference/kilo/CANDIDATE_SIGNUPS.md` |
| E.7 (full GUI surface — Q-Elo col + Reach badge + rent-gpu tab + candidates tab) | E.5c | `models_browser_template.html`, regenerated `models_browser.html` |
| E.8 (rule pack section) | E.5d | `.windsurf/rules/ai/00-ai-model-selection.md` |

---

**E.1 — Vendor `fabrik-lib/web-scrape/` into project.**
```bash
cp -r /opt/fabrik-lib/web-scrape/web_scrape scripts/kilo-benchmarks/libs/web_scrape
touch scripts/kilo-benchmarks/libs/__init__.py
# Rewrite internal imports: from web_scrape import X → from libs.web_scrape import X
python -c "import sys; sys.path.insert(0, 'scripts/kilo-benchmarks'); from libs.web_scrape import WebScraper, extract_nextjs_data; print(WebScraper, extract_nextjs_data)"
```

**Gate E.1:**
```bash
# Import + smoke-fetch a known static page to confirm the vendored copy works.
cd scripts/kilo-benchmarks && python -c "
import sys; sys.path.insert(0, '.')
from libs.web_scrape import WebScraper
from pathlib import Path
s = WebScraper(cache_dir=Path('.tmp/scrape-cache'))
html = s.fetch_static('https://modal.com/pricing')
assert '<html' in html.lower() and len(html) > 1000, 'fetch_static returned unexpected shape'
print('E.1 OK — web-scrape vendored and functional')
"
# Expected: E.1 OK — web-scrape vendored and functional
```

**E.2 — TDD: write the highest-risk tests FIRST** (`scripts/kilo-benchmarks/tests/test_watchlist_and_gpu.py`).

Highest-risk paths: (a) `gpu_providers` schema migration is idempotent; (b) seeder respects `reachable_with_existing_keys=0` for watch-list; (c) SC #13 coherence — `reachable=1` GPU providers are exactly `{vast, runpod, modal}`.

```python
def test_gpu_providers_migration_idempotent(tmp_conn):
    from seed_watchlist_and_gpu import _migrate_gpu_providers
    _migrate_gpu_providers(tmp_conn)
    _migrate_gpu_providers(tmp_conn)  # second run must not raise
    cols = {r[1] for r in tmp_conn.execute("PRAGMA table_info(gpu_providers)")}
    assert {"id","provider","gpu_sku","tier","usd_per_hour","usd_per_second","reachable_with_existing_keys","signup_trigger"} <= cols

def test_watchlist_seeded_rows_all_have_reachable_zero(tmp_conn):
    from seed_watchlist_and_gpu import seed_watchlist_and_gpu
    seed_watchlist_and_gpu(tmp_conn)
    rows = tmp_conn.execute(
        "SELECT provider FROM agents WHERE provider IN ('together','hyperbolic','cerebras','novita') "
        "AND reachable_with_existing_keys=1"
    ).fetchall()
    assert rows == [], f"watch-list vendors must be reachable=0, got: {rows}"

def test_gpu_reachable_set_matches_gpu_rent_drivers(tmp_conn):
    """SC #13 coherence: reachable=1 GPU providers exactly = fabrik-lib/gpu-rent driver set."""
    from seed_watchlist_and_gpu import seed_watchlist_and_gpu
    seed_watchlist_and_gpu(tmp_conn)
    reachable = {r[0] for r in tmp_conn.execute(
        "SELECT DISTINCT provider FROM gpu_providers WHERE reachable_with_existing_keys=1"
    ).fetchall()}
    assert reachable == {"vast", "runpod", "modal"}, f"drift from gpu-rent driver set: {reachable}"
```

**Gate E.2 (must FAIL RED first — modules don't exist yet):**
```bash
cd scripts/kilo-benchmarks && python -m pytest tests/test_watchlist_and_gpu.py -x 2>&1 | tail -5
# Expected: 3 FAILED (ModuleNotFoundError) — red for the right reason.
```

**E.3 — Implement `seed_watchlist_and_gpu.py`** (`scripts/kilo-benchmarks/seed_watchlist_and_gpu.py`).

Header: `# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_watchlist_and_gpu.py`

Migration adds:
- New table `gpu_providers` per spec E.1 SQL.
- New column: `ALTER TABLE agents ADD COLUMN signup_trigger TEXT`.

Seed rows verbatim from spec § E.1 (GPU) and § E.2 (inference). Set `reachable_with_existing_keys=1` for {vast, runpod, modal} SKUs only. Watch-list inference rows all `reachable=0`. Novita LLM row set with fallback price of `0.40` and `notes='estimate — awaiting live probe'` per spec Open Unknown #4.

**Gate E.3:**
```bash
cd scripts/kilo-benchmarks && python -m pytest tests/test_watchlist_and_gpu.py -x 2>&1 | tail -5
# Expected: 3 passed
```

**E.4 — Implement `scrape_gpu_prices.py`** (uses vendored `libs.web_scrape`).

Header: `# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_watchlist_and_gpu.py`

Fetches pricing from the URLs cited in the spec's External deps table (Vast, RunPod, Hyperbolic, Novita, Modal). Modal and RunPod use `extract_nextjs_data()` for their Next.js props. Vast uses a CSS-selector fallback (its price table is server-rendered HTML). Updates `gpu_providers.usd_per_hour` + `last_verified` for each row. Never writes NULL; if a fetch fails, logs to stderr and leaves the existing price untouched (fail-soft — cached price is better than deleted price).

**Gate E.4:**
```bash
# Dry-run: fetch all providers, don't write. Assert every fetch succeeds.
python scripts/kilo-benchmarks/scrape_gpu_prices.py --dry-run --json 2>&1 | python -c "
import json, sys
d = json.load(sys.stdin)
for provider in ('vast','runpod','modal','hyperbolic','novita'):
  assert provider in d, f'missing provider {provider}'
  assert d[provider].get('h100_usd_per_hour', 0) > 0, f'{provider} h100 fetch failed: {d[provider]}'
print('E.4 gate OK — all 5 providers scraped successfully')
"
# Expected: E.4 gate OK — all 5 providers scraped successfully
```

**E.5 — Extend `suggest_model.py` with the upsell watcher.**

Add module constant `UPSELL_MIN_SAVING_PCT = 0.30`. Add `--strict` argparse flag. After the frontier prints (existing code), run a second `_rank_service_type()` against the full unfiltered set (temporarily setting `reachable_with_existing_keys` filter off), compute best-locked-out row, compare to best-accessible row on cost, and if `(best_accessible.cost - best_locked_out.cost) / best_accessible.cost >= UPSELL_MIN_SAVING_PCT` AND (quality_elo unknown OR best_locked_out.quality_elo >= best_accessible.quality_elo - 50), print single `💡 Consider signup: <id> — <pct>% cheaper for equivalent quality — needs new signup + payment method.` to stderr. `--strict` skips this whole block.

Add corresponding test (`scripts/kilo-benchmarks/tests/test_upsell_watcher.py`):
```python
def test_upsell_prints_when_locked_out_row_beats_accessible_by_30pct(tmp_db_with_llm_rows, monkeypatch, capsys):
    """Seed: accessible Groq Llama at $0.59/M, locked-out Hyperbolic Llama at $0.40/M — 32% cheaper.
    Expect: 💡 line printed to stderr; exit 0."""
    monkeypatch.setenv("KILO_DB", str(tmp_db_with_llm_rows))
    from suggest_model import main
    rc = main(["--task","llm","--volume-chars","1000000"])
    err = capsys.readouterr().err
    assert rc == 0
    assert "💡 Consider signup:" in err
    assert "hyperbolic" in err.lower()

def test_strict_flag_suppresses_upsell(tmp_db_with_llm_rows, monkeypatch, capsys):
    monkeypatch.setenv("KILO_DB", str(tmp_db_with_llm_rows))
    from suggest_model import main
    rc = main(["--task","llm","--volume-chars","1000000","--strict"])
    err = capsys.readouterr().err
    assert rc == 0
    assert "Consider signup" not in err

def test_upsell_skipped_when_saving_below_threshold(tmp_db_with_close_prices, monkeypatch, capsys):
    """Locked-out row only 20% cheaper — below UPSELL_MIN_SAVING_PCT=0.30. Expect no 💡 line."""
    monkeypatch.setenv("KILO_DB", str(tmp_db_with_close_prices))
    from suggest_model import main
    rc = main(["--task","llm","--volume-chars","1000000"])
    err = capsys.readouterr().err
    assert rc == 0
    assert "Consider signup" not in err
```

**Gate E.5:**
```bash
cd scripts/kilo-benchmarks && python -m pytest tests/test_upsell_watcher.py -x 2>&1 | tail -5
# Expected: 3 passed
```

**E.6 — Implement `rank_candidate_signups.py`** — pattern-clone of `rank_coding_subagents.py`, but queries `agents WHERE reachable_with_existing_keys=0` UNION `gpu_providers WHERE reachable_with_existing_keys=0`; emits `docs/reference/kilo/CANDIDATE_SIGNUPS.md` with break-even math (uses each row's `signup_trigger` column).

Header: `# AFTER-EDIT: docs/reference/kilo/CANDIDATE_SIGNUPS.md`

**Gate E.6:**
```bash
python scripts/kilo-benchmarks/rank_candidate_signups.py
test -f docs/reference/kilo/CANDIDATE_SIGNUPS.md
head -1 docs/reference/kilo/CANDIDATE_SIGNUPS.md | grep -qE "^Last refresh: [0-9]{4}-[0-9]{2}-[0-9]{2}"
# ≥1 row per candidate vendor (SC #11)
grep -cE "^\| (Together|Hyperbolic|Cerebras|Novita)" docs/reference/kilo/CANDIDATE_SIGNUPS.md | awk '$1 >= 4 { exit 0 } { print "expected ≥4 vendor rows, got "$1; exit 1 }'
echo "E.6 gate OK"
```

**E.7 — Full GUI surface for every new column + new table** — subagent E.5c edits `models_browser_template.html` to add ALL of the following in one pass (owned paths already declared disjoint from E.5a/b/d):

1. **New `<th data-sort="quality_elo" data-tabs="image voice">Q-Elo</th>`** — Arena Elo column visible in the image + voice tabs. Cell renderer: `row.quality_elo ?? '—'`. Tooltip cites the two source Arenas (ArtificialAnalysis Image Arena + HF TTS Arena V2) grounded in spec External deps table.
2. **New non-sortable badge column `<th data-tabs="overview reasoning coding translation transcription voice image video ocr rent-gpu candidates">Reach</th>`** rendered in every tab. Cell renderer emits `<span class="reach-badge reach-yes">✅</span>` when `reachable_with_existing_keys=1`, `<span class="reach-badge reach-no" title="{signup_trigger}">❌</span>` when `=0`. Yellow ⚠️ variant reserved for future low-balance rows — CSS class present but no rows emit it in this phase (parse ⚠️ status from `AI_VENDOR_ACCESS.md` later).
3. **New tab chip `<span class="tab" data-tab="rent-gpu">` + separate `<tbody id="rows-gpu">`** rendering `SELECT * FROM gpu_providers`. Header row (in a second `<thead>` visible only when `activeTab==="rent-gpu"`): `Provider | GPU SKU | Tier | $/hr | $/sec | Cold-start (s) | Reach | Signup trigger`. Default sort: `$/hr` ascending. Shows BOTH reachable states.
4. **New tab chip `<span class="tab" data-tab="candidates">` + separate `<tbody id="rows-candidates">`** — union projection normalizing to common columns: `SELECT id, provider, service_type, cheapest_gateway_price AS price, 'llm' AS kind, signup_trigger FROM agents WHERE reachable_with_existing_keys=0 AND status='active'` UNION `SELECT id, provider, gpu_sku AS service_type, usd_per_hour AS price, 'gpu' AS kind, signup_trigger FROM gpu_providers WHERE reachable_with_existing_keys=0`. Columns: `Model/SKU | Provider | Kind | Price | Signup trigger`.
5. **Tab-selector strip** (existing `<div class="tabs">` at `models_browser_template.html:651`) gains 2 new `<span class="tab" data-tab="rent-gpu">Rent (GPU)</span>` and `<span class="tab" data-tab="candidates">Candidates</span>` chips. `activeTab` handler at `:931` extends to swap `<tbody>` visibility: `#rows-agents` shown for the existing 9 tabs, `#rows-gpu` shown for rent-gpu, `#rows-candidates` shown for candidates. The earlier "Watch-list" name is dropped — `candidates` supersedes it (only one chip is authored).

**Gate E.7:**
```bash
python scripts/kilo-benchmarks/export_models_browser.py
HTML=scripts/kilo-benchmarks/models_browser.html
# 1. All 4 GUI surfaces exist in the emitted HTML — matches real template convention.
grep -q 'data-sort="quality_elo" data-tabs="image voice"' "$HTML" || { echo "Q-Elo <th> missing or wrong data-tabs"; exit 1; }
grep -q 'class="reach-badge' "$HTML" || { echo "Reach badge missing"; exit 1; }
grep -q '<span class="tab" data-tab="rent-gpu"' "$HTML" || { echo "rent-gpu tab chip missing"; exit 1; }
grep -q '<span class="tab" data-tab="candidates"' "$HTML" || { echo "candidates tab chip missing"; exit 1; }
grep -q '<tbody id="rows-gpu"' "$HTML" || { echo "rows-gpu tbody missing"; exit 1; }
grep -q '<tbody id="rows-candidates"' "$HTML" || { echo "rows-candidates tbody missing"; exit 1; }
# 2. Reach badges emitted for every active LLM row + every gpu_providers row.
n_active_agents=$(sqlite3 scripts/kilo-benchmarks/kilo_agents.db \
  "SELECT COUNT(*) FROM agents WHERE status='active'")
n_all_gpu=$(sqlite3 scripts/kilo-benchmarks/kilo_agents.db "SELECT COUNT(*) FROM gpu_providers")
n_expected_badges=$((n_active_agents + n_all_gpu))
n_badges=$(grep -oE 'class="reach-badge' "$HTML" | wc -l)
[ "$n_badges" -ge "$n_expected_badges" ] || { echo "Reach badges $n_badges < expected $n_expected_badges (agents+gpu)"; exit 1; }
# 3. rent-gpu tbody shows ALL gpu_providers rows.
n_rent_rows=$(python3 -c "
import re
html=open('$HTML').read()
m=re.search(r'<tbody id=\"rows-gpu\".*?</tbody>',html,re.S)
print(m.group(0).count('<tr') if m else 0)
")
[ "$n_rent_rows" -ge "$n_all_gpu" ] || { echo "rows-gpu tbody has $n_rent_rows rows, DB has $n_all_gpu"; exit 1; }
# 4. candidates tbody = union of reachable=0 across both tables.
n_cand_agents=$(sqlite3 scripts/kilo-benchmarks/kilo_agents.db \
  "SELECT COUNT(*) FROM agents WHERE reachable_with_existing_keys=0 AND status='active'")
n_cand_gpu=$(sqlite3 scripts/kilo-benchmarks/kilo_agents.db \
  "SELECT COUNT(*) FROM gpu_providers WHERE reachable_with_existing_keys=0")
n_cand_expected=$((n_cand_agents + n_cand_gpu))
n_cand_rows=$(python3 -c "
import re
html=open('$HTML').read()
m=re.search(r'<tbody id=\"rows-candidates\".*?</tbody>',html,re.S)
print(m.group(0).count('<tr') if m else 0)
")
[ "$n_cand_rows" -ge "$n_cand_expected" ] || { echo "rows-candidates tbody has $n_cand_rows rows, expected ≥$n_cand_expected"; exit 1; }
# 5. JS activeTab handler swaps tbody visibility for the 2 new tabs (guard against copy-paste of chip w/o handler).
grep -qE 'rows-gpu|rows-candidates' "$HTML" && grep -qE 'activeTab.*(rent-gpu|candidates)' "$HTML" \
  || { echo "activeTab handler does not reference new tbody ids or new tabs"; exit 1; }
echo "E.7 gate OK — all GUI surfaces populated + tbody swap wired"
```

**Coverage vs SC #15/#16/#17/#18:** this gate proves SC #15 (candidates row count), SC #16 (rent-gpu row count), SC #17 (Q-Elo + Reach `<th>` presence and Reach cell population). SC #18 (JS click-sort on image tab) still needs a manual browser probe or headless Puppeteer test — flagged as follow-up in Residual Unknowns; not blocking for this phase since server-side rendering + client-side sort correctness is out of scope for a script gate.

**E.8 — Rule pack entry.** Insert after `## Fabrik defaults` (line 49 in `.windsurf/rules/ai/00-ai-model-selection.md`) the `## Candidate signup vendors (watch-list — not currently active)` section per spec § E.5. Content copied from `CANDIDATE_SIGNUPS.md`'s table but without break-even math (rule pack stays terse); the pack points at `CANDIDATE_SIGNUPS.md` for details.

**Gate E.8:**
```bash
grep -q "^## Candidate signup vendors" .windsurf/rules/ai/00-ai-model-selection.md
grep -q "docs/reference/kilo/CANDIDATE_SIGNUPS.md" .windsurf/rules/ai/00-ai-model-selection.md
echo "E.8 gate OK"
```

**E.9 — Wire new steps into `daily_refresh.sh`** — insert `scrape_gpu_prices.py` between step 6 (existing `fetch_replicate_prices.py`) and step 7 (`derive_cheapest_gateway.py`); insert `rank_candidate_signups.py` alongside the other 4 rankers added by Phase B.6.

**E.10 — Doc-sync + review + commit.**

1. `CHANGELOG.md` append under `## [Unreleased]`:
   ```
   ### Added — best-model-suggester Phase E: watch-list vendors + GPU providers + upsell watcher (2026-07-05)
   New gpu_providers table (Vast/RunPod/Modal accessible; Hyperbolic/Novita seeded reachable=0).
   Watch-list agents rows for Together/Hyperbolic/Cerebras/Novita LLM inference.
   New browser Watch-list tab + CANDIDATE_SIGNUPS.md + suggester upsell watcher (--strict opts out).
   Vendored fabrik-lib/web-scrape for GPU pricing scrape.
   ```
2. `INDEX.md` — add rows for the 5 new scripts + 1 new MD.
3. `python scripts/enforcement/check_doc_sync.py` — resolve WARN.
4. **BLOCKING gate:** invoke `/fabrik-review` on Phase E's changed surface (all of E.1–E.9). Full adversarial methodology, parallel finders, refute → prove-before-fix, LOOP until zero CONFIRMED findings.
5. Commit:
   ```bash
   git add scripts/kilo-benchmarks/libs/web_scrape/ \
           scripts/kilo-benchmarks/libs/__init__.py \
           scripts/kilo-benchmarks/seed_watchlist_and_gpu.py \
           scripts/kilo-benchmarks/scrape_gpu_prices.py \
           scripts/kilo-benchmarks/rank_candidate_signups.py \
           scripts/kilo-benchmarks/suggest_model.py \
           scripts/kilo-benchmarks/tests/test_watchlist_and_gpu.py \
           scripts/kilo-benchmarks/tests/test_upsell_watcher.py \
           scripts/kilo-benchmarks/daily_refresh.sh \
           scripts/kilo-benchmarks/models_browser_template.html \
           scripts/kilo-benchmarks/kilo_agents.db \
           docs/reference/kilo/CANDIDATE_SIGNUPS.md \
           .windsurf/rules/ai/00-ai-model-selection.md \
           CHANGELOG.md INDEX.md
   git commit -m "$(cat <<'EOF'
   feat(kilo-benchmarks): Phase E — watch-list + gpu_providers + upsell watcher

   Agent-Role: orchestrator
   Agent-Phase: E
   Agent-Context: seeded Together/Hyperbolic/Cerebras/Novita as reachable=0 LLM watch-list rows; new gpu_providers table with Vast/RunPod/Modal reachable=1 and Hyperbolic/Novita reachable=0; vendored web-scrape from fabrik-lib; added --strict + upsell watcher to suggest_model.py; new CANDIDATE_SIGNUPS.md + rule-pack section + browser Watch-list tab

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
   )"
   ```

---

## Phase D — Docs convergence + FULL gate

**Goal.** Prove correctness of the shipped docs and pass the Tier-2 final gate.

### Steps

**D.1 — Invoke `/fabrik-docs-review`** on the changed surface. Touch-on-change already gated presence; this pass proves correctness. Fix anything it surfaces.

**D.2 — Run the FULL final gate** (Tier 2, NOT `--lean`):
```bash
python scripts/final_gate.py --json 2>&1 | tail -30
# Expected: {"status": "success", "tier": 2, ...}
```
Fix any failures — read the JSON `failures[]` array, apply targeted fixes, re-run.

**D.3 — Run `check_convergence.py`** (plan-file self-audit):
```bash
python scripts/enforcement/check_convergence.py 2>&1 | tail -20
# Expected: no errors on this plan file — the ## Evidence + ## Self-audit + ## Residual unknowns sections satisfy the enforcer.
```

**D.4 — Final commit** — ONLY if D.1's `/fabrik-docs-review` or D.2's Tier-2 gate produced any fixup edits. If both were clean (no file changes since Phase C's commit), SKIP D.4 and go straight to D.5 (Status flip).

Determine what to stage — no placeholders: run `git status --porcelain` first and stage explicit paths from the output. Only these paths are permitted (any other diff is out of scope for Phase D and should be investigated, not staged):

- `docs/**/*.md` (any doc touched by `/fabrik-docs-review`)
- `CHANGELOG.md` (if docs-review inserted a Phase D entry)
- `.windsurf/rules/**/*.md` (rule packs `/fabrik-docs-review` amended for consistency)

```bash
# 1. Confirm the diff is limited to allowed paths.
git status --porcelain | awk '{print $2}' | grep -vE '^(docs/|CHANGELOG\.md$|\.windsurf/rules/)' | ( ! grep -q . ) \
  || { echo "Phase D diff includes files outside allowed set — investigate before staging"; exit 1; }

# 2. Stage every dirty file inside the allowed set, explicitly (no `git add -A`).
CHANGED=$(git status --porcelain | awk '{print $2}' | grep -E '^(docs/|CHANGELOG\.md$|\.windsurf/rules/)' | tr '\n' ' ')
if [ -n "$CHANGED" ]; then
  git add $CHANGED
  git commit -m "$(cat <<'EOF'
docs(kilo-benchmarks): Phase D — docs review + full-gate pass for best-model-suggester

Agent-Role: orchestrator
Agent-Phase: D
Agent-Context: /fabrik-docs-review pass + final_gate.py --json = success

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
else
  echo "Phase D: no docs-review fixes — skipping commit"
fi
```

**D.5 — Flip plan Status.**

Edit this plan file: `**Status:** IN-PROGRESS` → `**Status:** EXECUTED 2026-07-05 (<commit-sha>)`.

**D.6 — Release scope lock.**
```bash
# Update .fabrik/plan-locks/2026-07-05-plan-1-best-model-suggester.json → status:"released"
```

---

## Evidence (per-phase grounding)

### Phase A evidence
- **`path:line`**: `scripts/kilo-benchmarks/specialty_pricing.py:13-112` — PRICING dict provides the seed source; verified live in this turn (see spec's fabrik-lib verdict table).
- **`path:line`**: `scripts/kilo-benchmarks/kilo_agents.db` schema — 84 columns confirmed via `sqlite3 kilo_agents.db 'PRAGMA table_info(agents)' | wc -l` on 2026-07-05; neither `quality_elo` nor `reachable_with_existing_keys` is present (verified: `PRAGMA table_info(agents)` output filtered by grep returns nothing), so the Phase A.3 migration is required and idempotent-safe (`_migrate()` skips columns that already exist).
- **External URL grounded 2026-07-05**: `https://artificialanalysis.ai/image/arena` — GPT Image 2 Elo 1339 (verified live via WebSearch this turn).
- **External URL grounded 2026-07-05**: `https://huggingface.co/spaces/TTS-AGI/TTS-Arena-V2` — Vocu V3.0 Elo 1581 (verified).
- **Command output**:
  ```
  $ sqlite3 scripts/kilo-benchmarks/kilo_agents.db "SELECT service_type, COUNT(*) FROM agents WHERE status='active' GROUP BY service_type"
  llm|334
  image_gen|23
  tts|3
  stt|1
  translation|1
  music_gen|2
  ```

### Phase B evidence
- **`path:line`**: `scripts/kilo-benchmarks/rank_coding_subagents.py:127,200,247,362` — helper API (`_compose_score`, `_rows_from_db`, `_safe_md_id`, `_atomic_write`) that the new rankers clone. Note `_atomic_write` drifted :345→:362 since 2026-07-05 (subagent-runs-lean plan added the CODING fallback loader upstream in the file).
- **`path:line`**: `scripts/kilo-benchmarks/daily_refresh.sh:1-45` — insertion point for the 4 new `_step "rank_<task>"` lines is between step 8b (`rank_task_subagents.py` at :358, sibling-added 2026-07-06) and step 9 (`export_models_browser.py` at :369).
- **External URLs grounded 2026-07-05** — Pricing for cost-normalization test constants:
  - `https://openai.com/business/pricing` (OpenAI TTS $15/1M chars)
  - `https://deepgram.com/pricing` (Nova-3 $0.0043/min batch)
  - `https://www.assemblyai.com/pricing` (Universal-2 $0.0025/min)
- **Command output** (mixed pricing_unit ground truth):
  ```
  $ sqlite3 scripts/kilo-benchmarks/kilo_agents.db "SELECT id, pricing_unit FROM agents WHERE service_type='image_gen' AND id LIKE 'google/%'"
  google/gemini-2.5-flash-image|M-tokens
  google/gemini-3.1-flash-image|M-tokens
  google/gemini-3-pro-image|M-tokens
  ```
  Confirms the `image` vs `M-tokens` mixed-unit reality inside one `service_type`.

### Phase C evidence
- **`path:line`**: `.windsurf/rules/ai/00-ai-model-selection.md:20` (`## Selection workflow`) and `:49` (`## Fabrik defaults`) — verified via grep — the insertion points for C.1 (Selection MDs block, after :20) and C.2 (advisory line, at the top of the workflow section).
- **`path:line`**: `scripts/fabrik_synced_manifest.py:67,69` — confirms `.windsurf/rules` and `docs/reference/kilo` ARE synced to projects, so the Phase C edit reaches every project.

### Phase E evidence
- **`path:line`**: `/opt/fabrik-lib/web-scrape/web_scrape/webscrape.py:253` — `WebScraper.fetch_static()` signature verified via grep; matches the vendored API the scraper uses.
- **`path:line`**: `/opt/fabrik-lib/web-scrape/web_scrape/webscrape.py:146` — `extract_nextjs_data(html) -> dict` verified; parses Modal/RunPod Next.js pricing pages.
- **`path:line`**: `/opt/fabrik-lib/gpu-rent/gpu_rent/drivers/vast_provider.py:1` (one of the 3 drivers) — coherence anchor for SC #13 (`{vast, runpod, modal}` is the exact driver set on disk).
- **`path:line`**: `scripts/kilo-benchmarks/rank_coding_subagents.py:362` — `_atomic_write()` cloned into `rank_candidate_signups.py` (re-verified 2026-07-06 — drifted from :345 since 2026-07-05).
- **Command output** (E.1 — coherence check that gpu-rent has exactly 3 drivers):
  ```
  $ ls /opt/fabrik-lib/gpu-rent/gpu_rent/drivers/*.py | grep -v __init__ | grep -v __pycache__
  /opt/fabrik-lib/gpu-rent/gpu_rent/drivers/modal_provider.py
  /opt/fabrik-lib/gpu-rent/gpu_rent/drivers/runpod.py
  /opt/fabrik-lib/gpu-rent/gpu_rent/drivers/vast_provider.py
  ```
- **External URLs re-verified 2026-07-05 (already grounded in spec External deps table):**
  - `https://modal.com/pricing` — $0.001097/s H100
  - `https://vast.ai/pricing` — H100 spot $1.55-1.87/hr
  - `https://groq.com/pricing` — Llama 3.3 70B $0.59/M in / $0.79/M out
  - `https://openrouter.ai/pricing` — no per-token markup, 5.5% + $0.80 min credit-purchase fee
  - `https://belski.me/blog/ai_inference_providers_2026_free_tier_deep_dive/` — Hyperbolic Llama 3.3 70B $0.40/M

### Phase D evidence
- **`path:line`**: `scripts/final_gate.py:1` — the tier-2 gate entrypoint (`--check --json` mode; Tier 2 = mypy + bandit + semgrep, never `--lean`).
- **`path:line`**: `scripts/enforcement/check_convergence.py:39` — the `PROOF` regex `[\w./-]+\.(?:py|ts|tsx|js|sql|md|csv|ya?ml|sh|json):\d+` that enforces "≥1 file:line citation per phase" — verified via `grep -n "PROOF = re.compile"`.
- **`path:line`**: `scripts/enforcement/check_convergence.py:91` — the failure branch that fired on this plan's DRAFT during pass-5 close: `if len(set(PROOF.findall(text))) < phases:` (re-verified 2026-07-06 — drifted from :92 since 2026-07-05). Fix in this phase was to add file-format-matching citations, not to change the plan's design.
- **`path:line`**: `scripts/enforcement/check_doc_sync.py:1` — the doc-sync gate D.1 runs before `/fabrik-docs-review`.
- **Command output** (D.2 tier-2 gate — post-execution expected shape):
  ```
  $ python scripts/final_gate.py --check --json | tail -6
  {
    "status": "success",
    "tier": 2,
    "passed": 22,
    "failed": 0
  }
  ```

---

## Self-audit

### Grounding passes run this turn
1. **Pass 1** (this turn): read the CONVERGED spec + `select_rules.py` output (18 ACTIVE packs) + `rank_coding_subagents.py` API + `daily_refresh.sh` structure + `fabrik_synced_manifest.py` reality + real DB schema. **Found:** no gaps; every phase's Interfaces block grounded to real symbols/files/URLs.
2. **Pass 2** (structural check): every phase ends with the same 4-step closing sequence (gate → doc-sync → `/fabrik-review` → commit). Every phase has an `Interfaces` block. Success criteria mapped to Phase A/B/C gates.

### Coverage check ("What we already agreed" ↔ phases)
- Kill hallucinated OR/TTS route → Phase B.3 gate (video_gen returns exit=1 → no extrapolation possible).
- Kill cost-wrong Recraft-over-Flux recommendation → Phase B.1 `test_mixed_pricing_unit_normalizes_across_image_gen` + Phase A `quality_elo` seed.
- Un-orphan `CODING_SUBAGENT_SELECTION.md` → Phase C.1 (row in Selection MDs table).
- All 3 phases in one plan, strict order → Phase A → B → C → D dependency chain.
- Manual vendor catalog first → Phase A.1 (hand-authored, not auto-generated).
- Advisory rule + programmatic hard-fail → Phase C.2 (advisory line) + Phase B.1/B.2 (exit=1).
- Reuse existing vendor keys → Phase A.3 `parse_vendor_catalog` + `reachable_with_existing_keys` filter.
- Hub-only, sync-aware → Context Ledger row 9, Global Constraints "sync-manifest awareness."

**No gap found.** Every commitment maps to a phase's step or gate.

### Cross-phase signature consistency
- `parse_vendor_catalog(md_path: Path) -> dict[str, bool]` — Phase A produces (A.3); no other phase consumes (self-contained). ✓
- `_rank_service_type(conn, service_type, **volume) -> list[dict]` — Phase B.2 produces; Phase B.5 subagents consume (imported). ✓
- `AI_VENDOR_ACCESS.md` path — Phase A produces at `docs/reference/kilo/AI_VENDOR_ACCESS.md`; Phase B parses (via A's function); Phase C references by same path. ✓
- `*_SELECTION.md` — Phase B.5 produces 4 files at `docs/reference/kilo/`; Phase C.1 references by same names. ✓
- Exit codes 0/1/2 — Phase B.2 produces; Phase B.3 tests; Phase C.2 advisory references "exit=1". ✓

### Fixed-point claim
This is the DRAFT — `/fabrik-plan-review` will run the adversarial convergence pass and either flip to CONVERGED or surface remaining issues. Do NOT claim CONVERGED here.

---

## Residual unknowns

### Resolved during this plan
- Phase-A→B circularity in `reachable_with_existing_keys` sourcing (spec pass 1 fix) — now Phase A.1 writes catalog first, A.3 reads it.
- Mixed `pricing_unit` within `image_gen` — Phase B.2 `AVG_TOKENS_PER_IMAGE` hardcoded dict; test at Phase B.1.
- `⚠️ low balance` accessibility semantics — accessible for filtering, surfaced as note in output (Phase B.2 `_print_markdown_table`).
- `avg_tokens_per_image` mechanism (column vs dict) — hardcoded dict in `suggest_model.py`, no schema change.
- **`perf_seconds` on new specialty rows** (was Still-open #3 pre-2026-07-07) — resolved in-plan by new step **A.5.5**: `microbench_specialty.py --limit 20` runs against the newly-seeded cohort (cohort filter at `microbench_specialty.py:165` auto-picks up `perf_seconds IS NULL` rows). No need to wait for Sunday cron.

### Still-open (resolution step named)
1. **`tts` `quality_elo` values.** The two Arena leaders (Vocu V3.0, Inworld TTS MAX) have no matching row in our DB. **Resolution:** Phase A leaves `quality_elo` NULL for all TTS rows; a follow-up ticket (out of this plan) seeds Vocu/Inworld if we ever gain access, or maps existing rows (ElevenLabs, OpenAI TTS, Azure) to their Arena V2 Elos if published. Not blocking — the ranker treats NULL as "no quality signal, rank on cost + speed."
2. **CosyVoice English per-character price.** Public English Alibaba pricing pages describe billing "per character" without publishing the rate. **Resolution:** Phase A.3 uses the same conservative $0.00003/char rate as `qwen-tts` and marks the PRICING entry `estimate: True` — the existing drift test in `test_microbench_specialty.py` will flag it if the estimate is off when a real bench call succeeds.

---

## One-Test Rule

**Why:** The plan's whole promise is *never extrapolate from empty specialty data* — the driving session's 3 failure modes (hallucinated OR/TTS route, cost-wrong image recommendation, orphaned CODING_SUBAGENT_SELECTION.md) all trace to the tool silently guessing when it should have hard-failed. If ONE test guards the entire shipped tool, it is the empty-pool exit=1 test: get this wrong and every recommendation is potentially fabricated; get this right and the tool's contract holds even when catalog rows go missing.

**Contract:**

- **Given:** a `kilo_agents.db` in which the `agents` cohort for `service_type='video_gen'` is empty (no rows with `status='active' AND reachable_with_existing_keys=1`), and `KILO_DB` points at that DB.
- **When:** the executor invokes `python scripts/kilo-benchmarks/suggest_model.py --task video_gen --volume-images 100`.
- **Then:** the process exits with return code **1** (non-zero, machine-checkable), stderr contains the literal substring `NO DATA for task=video_gen`, and stdout is empty of any `| \`model_id\` |` recommendation row — proving the tool refused to extrapolate. The test lives at `scripts/kilo-benchmarks/tests/test_suggest_model.py::test_empty_pool_exits_1` and is the canonical Phase B.1 red-first TDD gate.
- **Mocked:** the `kilo_agents.db` connection uses a `tmp_path` SQLite file with a fixed cohort seeded by the `tmp_db_empty_for_task` fixture — NOT the production DB, NOT mocked `sqlite3.connect`. All argparse, exit-code, and stderr behavior is REAL (via `main(argv)` + `capsys`); no `subprocess`, no mocked `sys.exit`. The vendor-catalog markdown file is not read in this path (empty-pool short-circuits before it opens), so no filesystem mock is needed.

---

## Handoff

- `/fabrik-plan-review docs/development/plans/2026-07-05-plan-1-best-model-suggester.md` (invoked automatically at the end of this turn) → adversarial grounding to fixed-point → flips `Status: DRAFT` → `Status: CONVERGED`.
- **User approval gate.**
- `/fabrik-execute-plan docs/development/plans/2026-07-05-plan-1-best-model-suggester.md` — user-triggered, runs Phase A → B → C → D autonomously with per-phase `/fabrik-review` gates.
