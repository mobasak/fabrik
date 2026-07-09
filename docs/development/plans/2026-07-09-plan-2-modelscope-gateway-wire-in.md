# ModelScope gateway wire-in — mirror the SiliconFlow 2026-07-09 pattern

**Status:** IN-PROGRESS
**Date:** 2026-07-09
**Owner:** primary (this session)
**Converged:** 2026-07-09 via `/fabrik-plan-review` — 4 passes, md5 fixed-point verified.
**Executing:** 2026-07-09 via `/fabrik-execute-plan` — baseline gate green (Tier-1 15/15).
**Goal:** Make ModelScope the 5th wired peer gateway (after OR, Kilo, DashScope, SiliconFlow) — per-model `via_modelscope=1` flag on `agents`, GUI badge + sidebar filter chip, daily-refresh integration, rule-pack gateway-count block, catalog documented in `AI_VENDOR_ACCESS.md`. Follows the exact 5-step recipe already documented in `docs/reference/kilo/AGGREGATOR_ROADMAP.md` and captured verbatim in the SiliconFlow chain (`commits 965e273a → ba674dc1` — key → template → vendor row → seed → scraper → GUI chip).

## What we already agreed (Phase 0)

Source of truth: this session's chat + the just-committed `docs/reference/kilo/AGGREGATOR_ROADMAP.md` entry marking ModelScope as **"KEY IN HAND — signed up. Wire on par with SF"**. No `/fabrik-spec` doc needed — the SF pattern IS the design spec.

**Pre-plan state (already committed as `1067ab43` before this plan starts):**
- `.env` — `MODELSCOPE_API_KEY=ms-…` (gitignored, single materialization)
- `.env.example` — placeholder row (`ms-your-modelscope-token-here`) with format hint
- `docs/CONFIGURATION.md` — env-var reference row
- `docs/reference/kilo/AGGREGATOR_ROADMAP.md` — Tier 1 row marked `KEY IN HAND`

**Live-verified this planning turn:**
- `HTTP 200` on `GET https://api-inference.modelscope.cn/v1/models` with the `ms-*` token → **55 models across 20 orgs**
- Sample IDs (HuggingFace-style `Org/Model`): `ZhipuAI/GLM-5.2`, `Shanghai_AI_Laboratory/Intern-S1`, `PaddlePaddle/ERNIE-4.5-300B-A47B-PT`, `deepseek-ai/DeepSeek-V4-Flash`, `Qwen/Qwen3-Coder-30B-A3B-Instruct`, `MiniMax/MiniMax-M3`, `moonshotai/Kimi-K2.5`, `Tencent-Hunyuan/Hy3`, `XiaomiMiMo/MiMo-V2-Flash`, `stepfun-ai/Step-3.5-Flash`, ...

**Chosen approach — 5 phases (A–E) mirroring the SF pattern:**
- **Phase A** — Migration + `AI_VENDOR_ACCESS.md` row (+ re-seed via `seed_specialty_catalog.py`, coarse-provider reachable flag) — dependency root
- **Phase B** — Author `scrape_modelscope_catalog.py` (per-model exact match) mirroring `scrape_siliconflow_catalog.py:1-171`; wire into `daily_refresh.sh` after SF step
- **Phase C** — Extend `update_gateway_counts.py` to query `via_modelscope` and emit the count row; re-run to refresh the rule-pack block
- **Phase D** — GUI wire: template chip + JS filter branch + per-row badge emit + Source-column tooltip, then re-run `export_models_browser.py`
- **Phase E** — Final gate + `/fabrik-docs-review` + CHANGELOG + INDEX + archive

**Rejected alternatives** (decided during planning):
- **Do the whole thing as one atomic commit.** Rejected — the SF pattern took a follow-up review pass to catch that "wired end-to-end" claim was overstated when the sidebar chip was missing. Phase-by-phase gates prevent that failure mode.
- **Reuse `via_siliconflow` column semantically.** Rejected — column names encode which gateway; overloading breaks GUI + gateway-counts + rank_coding derivation. Adding `via_modelscope` is 1 column via idempotent `ALTER TABLE ADD COLUMN IF NOT EXISTS`.
- **Skip AI_VENDOR_ACCESS.md row + only do per-model via_modelscope.** Rejected — the coarse-provider seed IS how `pick_models` currently reads reachability; skipping the row would leave `reachable_with_existing_keys` stale for ModelScope-only providers (Shanghai AI Lab, PaddlePaddle, Xiaomi, etc.).

**Constraints stated by user (in-chat):**
- "we have siliconflow api key, ... save it into .env file, can we fetch the modles from it now?" → wire on par with SF (implied)
- Roadmap doc entry: "Wire on par with SF" — confirms mirror scope

**Question bar — all resolved during this planning turn:**
- **Provider ORG normalization** (mapping HF-style ModelScope `Org/Model` → agents.provider): resolved by live-inspecting the SF scraper's `_ORG_MAP` at `scrape_siliconflow_catalog.py:33-56` — pattern is deterministic dict lookup + fallback to lowercase. This plan's Phase B carries a pre-computed MS `_ORG_MAP` grounded from the 55-model live catalog (see Phase B Steps).
- **Should `ZhipuAI/*` map to `z-ai` or a new `zhipuai` provider?** Resolved: **`z-ai`** — Z.ai is Zhipu (same company, renamed). Consistent with SF's `zai-org → z-ai` mapping. Verified: current DB has 12 `z-ai` provider rows and 0 `zhipuai` provider rows.
- **Should the MS scraper add new rows or only flip flags on existing IDs?** Resolved: **flip-only** (like SF). New-row ingestion is `verify_openrouter_catalog.py`'s job. Rows for models MS hosts that OR doesn't cover (e.g. `Xiaomi/MiMo-V2-Flash`) go into the **unmatched list** printed to stderr — the operator adds them via manual `INSERT` or a follow-up plan authorizes new-row auto-ingest.
- **Migration mechanism for the SQLite ALTER**: idempotent `ALTER TABLE agents ADD COLUMN via_modelscope INTEGER` (sqlite treats missing → 0 for INTEGER default; matches how the sibling `via_dashscope`/`via_siliconflow` columns behave). No separate migration file — sqlite's schema evolution convention in this project is inline via `PRAGMA table_info` guard in the scraper's first-run init.

None deferred. Zero `[OPEN → resolve at Phase N]` residuals.

**Branch: RICH.** SF pattern is the design spec; every phase is a mechanical mirror of a known-good 2026-07-09 commit chain.

## Global Constraints

Verbatim from binding sources — every phase inherits these:

- **Python 3.11+**, stdlib-first (`sqlite3`, `re`, `os`, `sys`, `pathlib`). Only new import: `httpx` (already vendored — used by every scraper).
- **Explicit `git add <path>` only** — never `git add -A` / `git add .` / `git commit -a` (CLAUDE.md HARD STOP).
- **Hub-side scope.** All edits under `scripts/kilo-benchmarks/**` + `.windsurf/rules/ai/**` + `docs/reference/kilo/**` + `CHANGELOG.md` + `INDEX.md`. No `compose.yaml`, no `fabrik apply`, no VPS deploy, no `specs/services/*.yaml` touched.
- **No new deps files.** `pyproject.toml`, `requirements.txt`, `uv.lock` untouchable (HARD STOP).
- **Fail-soft everywhere.** Scraper never crashes cron: `SILICONFLOW_API_KEY`-style guard — missing key → WARN + return 0. Same for network errors.
- **Provenance trailers** on every commit — `Agent-Role: orchestrator`, `Agent-Phase: A|B|C|D|E`, `Agent-Context:` one-liner.
- **Governance-sync awareness.** `.windsurf/rules/ai/**` + `docs/reference/kilo/**` are governance-synced (`scripts/fabrik_synced_manifest.py:67, 69`) — edits here propagate to every project. `scripts/kilo-benchmarks/**` is hub-only.
- **Secret discipline.** The token is stored ONLY in `.env`. Never `echo` its value; never stage it. All commits verified via `git diff --cached | grep -c "ms-9c67916c"` = 0 before push (pattern from the SF commit chain — commits `965e273a` + `f6d653fc` show this in their history).

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| ACTIVE rule pack `core/10-python.md` | Python 3.11 typing (`from __future__ import annotations`); no bare `except` | `.windsurf/rules/core/10-python.md` |
| ACTIVE rule pack `core/25-data-postgres.md` | SQLite idempotent DDL (`ADD COLUMN IF NOT EXISTS`-style; sqlite via PRAGMA guard) | `.windsurf/rules/core/25-data-postgres.md` |
| ACTIVE rule pack `core/45-testing-strategy.md` | Behavior Contract: one test per user-observable behavior, risk-ordered, TDD for risky | `.windsurf/rules/core/45-testing-strategy.md` |
| ACTIVE rule pack `ai/00-ai-model-selection.md` | Selection MDs discoverable + governance-synced. Gateway-counts block owned by `update_gateway_counts.py` | `.windsurf/rules/ai/00-ai-model-selection.md` — GATEWAY_COUNTS block starts at `:119` (verified this pass) |
| `scripts/kilo-benchmarks/scrape_siliconflow_catalog.py` — reference implementation | Mirror this shape exactly: `_ORG_MAP`, `_sf_to_agent_id_candidates`, `apply_flags`, `main` | 171 lines total; live-verified structure this turn |
| `scripts/kilo-benchmarks/update_gateway_counts.py` — real path:line | `:98-100` — has explicit `"siliconflow": n("SELECT count(*) ... WHERE via_siliconflow=1")` | Read this turn; Phase C mirrors this line's shape for `via_modelscope` |
| `scripts/kilo-benchmarks/daily_refresh.sh:330` — wire location | New `_step "scrape_modelscope_catalog"` block goes right after the SF step | Read this turn |
| `scripts/kilo-benchmarks/models_browser_template.html:554` — chip location | New chip block goes right after the `data-source="dashscope"` chip | Read this turn |
| `scripts/kilo-benchmarks/models_browser_template.html:1115` — JS filter branch | New `if (s === "modelscope" && !!m.via_modelscope)` goes right after `dashscope` branch | Read this turn |
| `scripts/kilo-benchmarks/models_browser_template.html:1143` — badge emit | New `if (m.via_modelscope) parts.push(...)` goes right after `via_siliconflow` badge | Read this turn |
| `scripts/kilo-benchmarks/kilo_agents.db` schema | `via_modelscope` column DOES NOT EXIST yet — verified via `PRAGMA table_info(agents)` this turn. Phase A adds it | Verified live this turn |
| fabrik-lib verdict | **N/A — no fabrik-lib capability adds/replaces here.** This is per-project glue code mirroring an existing per-project pattern (SF scraper). No new module warranted. | Confirmed: `/opt/fabrik-lib/README.md` module table has nothing that would replace a per-vendor catalog scraper |
| `AGENTS.md` invariants | **N/A** — no compose service, no network, no port, no VPS deploy | Spec inspection |
| `shape:` flag | **N/A** — no `specs/services/*.yaml` touched | Spec inspection |

**fabrik-lib consult:** confirmed — no vendor/enhance opportunity. The scraper mirrors a project-local pattern established by SF; abstracting it into fabrik-lib as "gateway-catalog-scraper" is a real 🆕 fabrik-lib candidate worth flagging in the handoff report (see § Handoff below), but out of scope for this plan (the plan's job is to mirror; the abstraction is a follow-up).

---

## Phase A — Migration + `AI_VENDOR_ACCESS.md` row + re-seed — ✅ EXECUTED 2026-07-09

**Goal.** Add the `via_modelscope INTEGER` column to `agents`. Add ModelScope row to `AI_VENDOR_ACCESS.md` under Specialty vendors, mirroring the SF row's shape (`AI_VENDOR_ACCESS.md:35` — the SF row). Re-run `seed_specialty_catalog.py` so the coarse-provider `reachable_with_existing_keys` flag flips for ModelScope-covered providers new to the DB (`ZhipuAI/z-ai`, `Shanghai_AI_Laboratory/shanghai-ai-lab`, `PaddlePaddle/paddlepaddle`, `Xiaomi/xiaomimimo`, `Tencent-Hunyuan/tencent-hunyuan`, etc.).

### Interfaces

**Consumes:** nothing (Phase A is root).

**Produces:**
- **DB column** `agents.via_modelscope INTEGER` (nullable; 0/1). Additive.
- **Vendor row** at `docs/reference/kilo/AI_VENDOR_ACCESS.md` (specifically: after the SiliconFlow row, before Anthropic direct API row).
- **Regression test** `scripts/kilo-benchmarks/tests/test_seed_reachability_backfill.py` — extended (existing file — adds a new test asserting ModelScope-added providers get `reachable_with_existing_keys=1` after re-seed).

### Behavior Contract

Highest-risk behavior first (TDD):

- **A1 — column is added idempotently**: running the column-add SQL twice against the same DB → no error, no data drift. Concrete test: `_ensure_via_modelscope_column(conn)` (a new helper in `scrape_modelscope_catalog.py` — introduced Phase A step A.4) can be called N times; `PRAGMA table_info` shows exactly one `via_modelscope` column.
- **A2 — vendor row parses cleanly by `seed_specialty_catalog.parse_vendor_catalog`**: after adding the row, `parse_vendor_catalog(AI_VENDOR_ACCESS.md)` returns a dict where the ModelScope-listed providers appear as accessible (True).
- **A3 — re-seed lifts reachable count for ModelScope-covered providers**: before-seed vs after-seed diff shows the specific providers ModelScope adds (Shanghai_AI_Laboratory, PaddlePaddle, XiaomiMiMo etc.) flipping to `reachable_with_existing_keys=1`.

### Steps

**A.0 — Preflight probes (2 s; halts phase on failure).**

```bash
python -m pytest --version 2>&1 | head -1                # → "pytest 9.0.2" (probed 2026-07-09 this planning turn)
python -c "import sqlite3, httpx; print('deps ok')"      # → "deps ok"
ls scripts/kilo-benchmarks/kilo_agents.db                # → present
grep -c "^MODELSCOPE_API_KEY=" .env                      # → 1 (registered 2026-07-09 this session)
```

If any probe fails: `BLOCKED: <what> — searched: A.0 preflight — missing: <need>`.

**A.1 — TDD: extend `test_seed_reachability_backfill.py` FIRST** with an A3 regression test that fixture-inserts a ModelScope-only provider (`shanghai-ai-lab`), runs `backfill_reachable_by_provider(...)` with `accessible_providers={"shanghai-ai-lab"}`, and asserts the row flipped to `reachable_with_existing_keys=1`.

**Gate A.1 (must FAIL RED — accessible_providers won't contain 'shanghai-ai-lab' until Phase A.2 adds the vendor row):**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_seed_reachability_backfill.py::test_backfill_flips_shanghai_ai_lab -x 2>&1 | tail -6
# Expected: FAILED — the seed_specialty_catalog's parse output doesn't yet include shanghai-ai-lab because AI_VENDOR_ACCESS.md doesn't list it.
```

Wait — this test is actually a pure `backfill_reachable_by_provider` unit test (per the Phase 0 pattern in the plan-1 archive). It uses an in-memory fixture DB and passes `accessible_providers` explicitly. It will PASS regardless of AI_VENDOR_ACCESS.md content. **Corrected:** the RED gate is A.3 (live-seed coverage assertion). A.1 test provides positive-behavior evidence but doesn't need to fail red.

**A.2 — Add ModelScope row to `AI_VENDOR_ACCESS.md`.**

Insert after the SiliconFlow row (`AI_VENDOR_ACCESS.md:35`). Row shape (verbatim structure mirroring the SF row's 6 columns):

```markdown
| ModelScope | qwen, deepseek, z-ai, moonshotai, minimax, mistralai, stepfun, nex-agi, meituan-longcat, shanghai-ai-lab, paddlepaddle, xiaomimimo, tencent-hunyuan, alibaba-iic, llm-research, medaibase, musepublic, opencompass, opengvlab, xgenerationlab | env `MODELSCOPE_API_KEY` | ✅ | credits pool | 55-model Alibaba model-hub gateway on `https://api-inference.modelscope.cn/v1` (OpenAI-compatible). Notable: ZhipuAI direct (GLM 5.2/5.1/5/4.7-Flash), Shanghai AI Lab Intern-S series (InternLM3 successors), PaddlePaddle ERNIE-4.5, Xiaomi MiMo, Tencent Hunyuan Hy3, XiYanSQL SQL coder, plus Qwen (20 models) / DeepSeek V3.2-V4 / MiniMax M2.5-M3 / Kimi K2.5 overlap. Format: `ms-*`. Full list: `python scripts/kilo-benchmarks/scrape_modelscope_catalog.py`. |
```

Bump `Last verified:` at line 1 to `2026-07-09` (unchanged — same date as SF row bump).

**Gate A.2:**

```bash
grep -c "^| ModelScope |" docs/reference/kilo/AI_VENDOR_ACCESS.md
# Expected: 1
python -c "
import sys; sys.path.insert(0, 'scripts/kilo-benchmarks')
from seed_specialty_catalog import parse_vendor_catalog
from pathlib import Path
acc = parse_vendor_catalog(Path('docs/reference/kilo/AI_VENDOR_ACCESS.md'))
new_providers = [p for p in ('shanghai-ai-lab', 'paddlepaddle', 'xiaomimimo', 'tencent-hunyuan', 'zhipuai') if acc.get(p)]
print('MS-added providers accessible=True after parse:', new_providers)
assert 'shanghai-ai-lab' in new_providers, 'seed parser did not pick up shanghai-ai-lab'
print('A.2 GATE OK')
"
```

**A.3 — Live re-seed via `seed_specialty_catalog.py` + `via_modelscope` column bootstrap.**

Column-add is idempotent SQL executed inline (not a separate migration file — SQLite convention here matches the sibling `via_*` columns which were also added via inline `ALTER`):

```bash
python -c "
import sqlite3
con = sqlite3.connect('scripts/kilo-benchmarks/kilo_agents.db')
cur = con.execute(\"PRAGMA table_info(agents)\")
cols = {r[1] for r in cur.fetchall()}
if 'via_modelscope' not in cols:
    con.execute('ALTER TABLE agents ADD COLUMN via_modelscope INTEGER')
    con.commit()
    print('added via_modelscope column')
else:
    print('via_modelscope already present — no-op')
con.close()
"
```

Then re-run seed:

```bash
python scripts/kilo-benchmarks/seed_specialty_catalog.py 2>&1 | tail -3
# Expected: "seeded/updated N specialty rows; M accessible providers; backfilled reachable=1 on K rows by provider match"
```

**Live coverage gate:**

```bash
python -c "
import sqlite3
con = sqlite3.connect('scripts/kilo-benchmarks/kilo_agents.db')
total, reach = con.execute(\"\"\"SELECT COUNT(*), SUM(reachable_with_existing_keys) FROM agents WHERE status='active' AND blocked=0\"\"\").fetchone()
pct = 100 * reach // total
print(f'  post-MS-seed: reachable={reach}/{total} ({pct}%)')
# Pre-MS-plan baseline (2026-07-09 this session): 271/362 (74%)
assert reach >= 271, f'A.3 coverage regression: reachable {reach} < baseline 271'
print('A.3 LIVE OK — no regression; net-new providers flipped')
"
```

**A.4 — Doc-sync + review + commit.**

1. `python scripts/enforcement/check_doc_sync.py` → resolve any WARN whose trigger is in this phase's diff.
2. **BLOCKING gate:** invoke `/fabrik-review` on Phase A's changed surface (`AI_VENDOR_ACCESS.md` + `kilo_agents.db` + `test_seed_reachability_backfill.py`). Full adversarial methodology per skill: parallel pool finders (default `minimax/minimax-m3` via `run_agents`, `pick_models("review")`, `allow_ungrounded=True` with diff inlined; each owes `record_agent_run + results_table`) + Opus refute/merge/decide, prove-before-fix each surviving finding with a kept regression test, loop until one full pass = zero CONFIRMED or PLAUSIBLE.
3. Commit:

   ```bash
   git add docs/reference/kilo/AI_VENDOR_ACCESS.md \
           scripts/kilo-benchmarks/kilo_agents.db \
           scripts/kilo-benchmarks/tests/test_seed_reachability_backfill.py
   git commit -m "$(cat <<'EOF'
   feat(kilo-db): Phase A — ModelScope vendor row + via_modelscope column + reseed

   Plan 2 (ModelScope gateway wire-in) Phase A.

   - AI_VENDOR_ACCESS.md: new SiliconFlow-style row for ModelScope under
     Specialty vendors. 20 DB providers listed matching the 55-model
     ModelScope inference catalog.
   - agents.via_modelscope INTEGER column added via idempotent ALTER
     TABLE (mirrors sibling via_siliconflow/via_dashscope columns).
   - seed_specialty_catalog.py re-run: reachable coverage held (baseline
     271/362) or lifted (new providers Shanghai_AI_Lab, PaddlePaddle,
     Xiaomi flipped via the coarse-provider match).
   - test_seed_reachability_backfill.py: +1 regression test for a
     ModelScope-only provider name.

   Agent-Role: orchestrator
   Agent-Phase: A
   Agent-Context: root wire-in — column + vendor row + re-seed

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
   )"
   ```

---

## Phase B — `scrape_modelscope_catalog.py` + `daily_refresh.sh` wire — ✅ EXECUTED 2026-07-09

**Goal.** Author `scripts/kilo-benchmarks/scrape_modelscope_catalog.py` mirroring `scrape_siliconflow_catalog.py:1-171` exactly. Flip `via_modelscope=1` on `agents` rows that exact-id-match ModelScope's 55-model catalog. Wire into `daily_refresh.sh` after the SiliconFlow scrape step (`daily_refresh.sh:330`).

### Interfaces

**Consumes** (from Phase A):
- Column `agents.via_modelscope INTEGER` exists.
- `AI_VENDOR_ACCESS.md` ModelScope row present.

**Produces:**
- **Script** `scripts/kilo-benchmarks/scrape_modelscope_catalog.py` — public functions:
  - `_norm(s: str) -> str` — mirror `scrape_siliconflow_catalog.py:63-64`
  - `_ms_to_agent_id_candidates(ms_id: str) -> list[str]` — mirror `_sf_to_agent_id_candidates`
  - `fetch_ms_models() -> list[dict]` — GET `https://api-inference.modelscope.cn/v1/models`, `Authorization: Bearer $MODELSCOPE_API_KEY`, fail-open on missing key / network error
  - `apply_flags(conn: sqlite3.Connection, ms_models: list[dict]) -> tuple[int, int, list[str]]` — mirror SF `apply_flags`; UPDATE guarded by `AND COALESCE(via_modelscope, 0) != 1` (per Pass-2 lesson from SF)
  - `main() -> int` — entrypoint; fail-open exits 0
- **Constants:** `DB_PATH`, `MS_URL`, `_ORG_MAP` (dict of 20 known SF-style org normalizations — see Steps).
- **Wire in `daily_refresh.sh`** — new `_step "scrape_modelscope_catalog"` block after `:330`.

### Behavior Contract

- **B1 — org-map maps to consistent providers**: `_ms_to_agent_id_candidates("ZhipuAI/GLM-5.2")` returns `["z-ai/glm-5.2", "z-ai/glm-5-2"]`; `_ms_to_agent_id_candidates("Shanghai_AI_Laboratory/Intern-S1")` returns candidates prefixed by `shanghai-ai-lab/`.
- **B2 — apply_flags idempotent (Pass 2 rowcount semantics)**: calling `apply_flags` twice with the same `ms_models` list on the same `conn` — second call reports `flipped 0` rows (COALESCE guard). Data unchanged.
- **B3 — fail-open on missing key**: `MODELSCOPE_API_KEY` unset → `fetch_ms_models` returns `[]` + prints WARN to stderr + `main` returns 0.
- **B4 — fail-open on network error**: transient network failure → return `[]` + WARN + return 0.
- **B5 — candidate dedup (Pass 2 lesson)**: `_ms_to_agent_id_candidates` for a model name without `.` → returns dedupe'd list via `list(dict.fromkeys(...))`.

### Steps

**B.1 — TDD: write B1/B2/B3/B4/B5 tests FIRST** at `scripts/kilo-benchmarks/tests/test_scrape_modelscope_catalog.py`. Mirror the SF test pattern from `test_scrape_siliconflow_catalog.py` if that file exists, or from `test_seed_reachability_backfill.py` shape if not.

Actual code the executor writes (grounded from SF's shape verbatim, adapted for MS):

```python
"""Behavior Contract for scripts/kilo-benchmarks/scrape_modelscope_catalog.py.

Plan-2 Phase B — ModelScope gateway wire-in.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_B1_org_map_zhipuai_to_z_ai():
    from scrape_modelscope_catalog import _ms_to_agent_id_candidates

    cands = _ms_to_agent_id_candidates("ZhipuAI/GLM-5.2")
    assert cands[0] == "z-ai/glm-5.2"
    assert "z-ai/glm-5-2" in cands  # dot-collapse variant


def test_B1_shanghai_ai_lab_provider_map():
    from scrape_modelscope_catalog import _ms_to_agent_id_candidates

    cands = _ms_to_agent_id_candidates("Shanghai_AI_Laboratory/Intern-S1")
    assert all(c.startswith("shanghai-ai-lab/") for c in cands)


def test_B2_apply_flags_idempotent_second_run(tmp_path):
    """Second run must report 0 flipped (COALESCE guard from SF Pass-2)."""
    from scrape_modelscope_catalog import apply_flags

    dbp = tmp_path / "agents.db"
    con = sqlite3.connect(str(dbp))
    con.execute(
        "CREATE TABLE agents (id TEXT PRIMARY KEY, via_modelscope INTEGER)"
    )
    con.execute("INSERT INTO agents (id) VALUES ('z-ai/glm-5.2')")
    con.commit()

    ms_models = [{"id": "ZhipuAI/GLM-5.2"}]
    _matched1, updated1, _unmatched1 = apply_flags(con, ms_models)
    assert updated1 == 1, f"first run should flip 1 row, got {updated1}"

    _matched2, updated2, _unmatched2 = apply_flags(con, ms_models)
    assert updated2 == 0, f"second run should flip 0 rows, got {updated2}"


def test_B3_fail_open_on_missing_key(monkeypatch):
    """MODELSCOPE_API_KEY unset → returns []."""
    from scrape_modelscope_catalog import fetch_ms_models

    monkeypatch.delenv("MODELSCOPE_API_KEY", raising=False)
    result = fetch_ms_models()
    assert result == []


def test_B4_fail_open_on_network_error(monkeypatch):
    """Transient network failure → returns []."""
    from scrape_modelscope_catalog import fetch_ms_models

    monkeypatch.setenv("MODELSCOPE_API_KEY", "ms-fake-key")
    # Force httpx.get to raise
    import httpx

    def raise_conn_error(*a, **kw):
        raise httpx.ConnectError("simulated network failure")

    monkeypatch.setattr(httpx, "get", raise_conn_error)
    result = fetch_ms_models()
    assert result == []


def test_B5_candidate_dedup_no_dot():
    """Model name without `.` → single candidate (not two identical)."""
    from scrape_modelscope_catalog import _ms_to_agent_id_candidates

    cands = _ms_to_agent_id_candidates("deepseek-ai/DeepSeek-V4-Flash")
    # Both branches (kebab, dot-kebab) produce the same string with no dots
    assert len(set(cands)) == len(cands), f"dupes: {cands}"
```

**Gate B.1 (must FAIL RED — module doesn't exist):**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_scrape_modelscope_catalog.py -x 2>&1 | tail -5
# Expected: ImportError — scrape_modelscope_catalog module not defined.
```

**B.2 — Implement `scripts/kilo-benchmarks/scrape_modelscope_catalog.py`.**

Grounded from `scrape_siliconflow_catalog.py:1-171` — the executor copies the SF scraper as a scaffold and rewires 4 things:
1. `SF_URL` → `MS_URL = "https://api-inference.modelscope.cn/v1/models"`
2. `SILICONFLOW_API_KEY` → `MODELSCOPE_API_KEY`
3. `_ORG_MAP` — swap for the ModelScope-specific dict (20 entries verified live this planning turn):
   ```python
   _ORG_MAP = {
       "deepseek-ai": "deepseek",
       "zhipuai": "z-ai",  # Z.ai IS Zhipu
       "minimax": "minimax",
       "shanghai_ai_laboratory": "shanghai-ai-lab",
       "paddlepaddle": "paddlepaddle",
       "xiaomimimo": "xiaomimimo",
       "tencent-hunyuan": "tencent-hunyuan",
       "iic": "alibaba-iic",
       "musepublic": "musepublic",
       "opengvlab": "opengvlab",
       "xgenerationlab": "xgenerationlab",
       "stepfun-ai": "stepfun",
       "moonshotai": "moonshotai",
       "qwen": "qwen",
       "mistralai": "mistralai",
       "meituan-longcat": "meituan-longcat",
       "nex-agi": "nex-agi",
       "llm-research": "llm-research",
       "medaibase": "medaibase",
       "opencompass": "opencompass",
   }
   ```
4. `via_siliconflow` → `via_modelscope` (all 4 SQL references).

**Gate B.2:**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_scrape_modelscope_catalog.py -v 2>&1 | tail -10
# Expected: 5 passed
```

**B.3 — Live-run against real ModelScope API.**

```bash
export MODELSCOPE_API_KEY="$(grep '^MODELSCOPE_API_KEY=' /opt/fabrik/.env | cut -d= -f2-)"
python scripts/kilo-benchmarks/scrape_modelscope_catalog.py 2>&1 | tail -5
# Expected: "fetched 55 MS models; matched N to agents.id; flipped via_modelscope=1 on M rows"
# N ≥ 30 (based on the 20-org overlap with existing DB providers)
# Followed by unmatched ids (e.g. Xiaomi/MiMo-V2-Flash if not in DB)

python -c "
import sqlite3
con = sqlite3.connect('scripts/kilo-benchmarks/kilo_agents.db')
n = con.execute(\"SELECT count(*) FROM agents WHERE via_modelscope=1 AND status='active' AND blocked=0\").fetchone()[0]
print(f'via_modelscope=1 rows (active+unblocked): {n}')
assert n >= 20, f'B.3 lift assertion failed — only {n} rows flipped (expected ≥20 given 20-org overlap)'
print('B.3 LIVE OK')
"
```

**B.4 — Wire into `daily_refresh.sh` after the SiliconFlow step (`:330`).**

Edit `daily_refresh.sh`: after the SF `_step` block, add:

```bash
  # ModelScope catalog scrape — flips via_modelscope=1 on matched agents.id
  # rows so the browser payload + rank scripts see MS as a real gateway.
  # Fetches the 55-model catalog from https://api-inference.modelscope.cn/v1/models
  # (OpenAI-compatible). Non-fatal on missing key or network failure. Idempotent.
  _step "scrape_modelscope_catalog" "$VENV_PY" "$KB/scrape_modelscope_catalog.py" \
    || echo "[daily_refresh] ModelScope catalog scrape failed (non-fatal)"
```

**Gate B.4:**

```bash
bash -n scripts/kilo-benchmarks/daily_refresh.sh && echo "  syntax ok"
grep -c "scrape_modelscope_catalog" scripts/kilo-benchmarks/daily_refresh.sh
# Expected: 2 (one comment, one _step; matches the SF wire's line count)
```

**B.5 — Doc-sync + review + commit.** Same shape as A.4. BLOCKING pool `/fabrik-review` looped to no-op.

Commit staging:

```bash
git add scripts/kilo-benchmarks/scrape_modelscope_catalog.py \
        scripts/kilo-benchmarks/tests/test_scrape_modelscope_catalog.py \
        scripts/kilo-benchmarks/daily_refresh.sh \
        scripts/kilo-benchmarks/kilo_agents.db
```

---

## Phase C — `update_gateway_counts.py` extension + rule-pack refresh — ✅ EXECUTED 2026-07-09

**Goal.** Extend `scripts/kilo-benchmarks/update_gateway_counts.py` to include a `via_modelscope=1` count query alongside the existing SF/DS ones (`update_gateway_counts.py:98-100`). Re-run it so the rule-pack `<!-- GATEWAY_COUNTS:START -->` block at `.windsurf/rules/ai/00-ai-model-selection.md:119` gains a `**ModelScope** (direct) | <N> | ...` row.

### Interfaces

**Consumes** (from Phase B):
- Column `agents.via_modelscope INTEGER` populated per-model.

**Produces:**
- Modified `scripts/kilo-benchmarks/update_gateway_counts.py` — one new count query + one new emit line, mirroring SF's shape at `:98-100`, `:140`, `:159`.
- Regenerated rule-pack block in `.windsurf/rules/ai/00-ai-model-selection.md` (governance-synced).

### Behavior Contract

- **C1 — count query returns real N**: `update_gateway_counts.py` invoked live outputs `'00-ai-model-selection.md': 'replaced'` (per SF pattern) and a `**ModelScope** (direct) | N | ...` row appears in the block.

### Steps

**C.1 — TDD: no new tests file** — the count script has no test file currently (SF didn't add one either). Behavior is verified via the live-run + rule-pack grep assertion.

**C.2 — Edit `update_gateway_counts.py`.** At `:98-100`, mirror the SF block:

```python
# BEFORE
"dashscope": n("SELECT count(*) FROM agents WHERE via_dashscope=1 AND status='active'"),
"siliconflow": n(
    "SELECT count(*) FROM agents WHERE via_siliconflow=1 AND status='active'"
),

# AFTER (add one entry after siliconflow)
"dashscope": n("SELECT count(*) FROM agents WHERE via_dashscope=1 AND status='active'"),
"siliconflow": n(
    "SELECT count(*) FROM agents WHERE via_siliconflow=1 AND status='active'"
),
"modelscope": n(
    "SELECT count(*) FROM agents WHERE via_modelscope=1 AND status='active'"
),
```

At `:139-140`, mirror the SF unpack:

```python
ds = counts["dashscope"]
sf = counts["siliconflow"]
ms = counts["modelscope"]  # NEW
```

At `:159`, mirror the SF emit line:

```python
lines.append(f"| **SiliconFlow** (direct) | {sf:,} | specialist routes (e.g. Hunyuan) |")
lines.append(f"| **ModelScope** (direct) | {ms:,} | Zhipu GLM direct, Intern-S, PaddlePaddle ERNIE, Xiaomi MiMo |")  # NEW
```

**Gate C.2:**

```bash
python scripts/kilo-benchmarks/update_gateway_counts.py 2>&1 | tail -3
# Expected: summary showing 'replaced' for 00-ai-model-selection.md

grep -A9 "GATEWAY_COUNTS:START" .windsurf/rules/ai/00-ai-model-selection.md | head -12
# Expected: contains "| **ModelScope** (direct) |" line with a numeric count
```

**C.3 — Doc-sync + review + commit.** Same shape as A.4. BLOCKING pool `/fabrik-review` looped to no-op.

Commit staging:

```bash
git add scripts/kilo-benchmarks/update_gateway_counts.py \
        .windsurf/rules/ai/00-ai-model-selection.md
```

---

## Phase D — GUI wire (template chip + badge + tooltip + regen) — ✅ EXECUTED 2026-07-09

**Goal.** Add `via ModelScope` sidebar filter chip + `<span class="src-badge ms">MS</span>` per-row badge + tooltip mention in `models_browser_template.html`. Regenerate `models_browser.html` via `export_models_browser.py`.

### Interfaces

**Consumes** (from Phase B):
- `agents.via_modelscope=1` populated per-model (payload will carry the flag).

**Produces:**
- Modified `scripts/kilo-benchmarks/models_browser_template.html`:
  - New chip at `:555` (after the `via DashScope` chip added by the SF fix commit)
  - New JS filter branch at `:1116` (after the `dashscope` branch)
  - New badge emit at `:1144` (after the SF badge emit)
  - New CSS class `.src-badge.ms` — distinct color per gateway convention (DS is green `#2a3a1a`, SF is amber `#3a2a1a`); use blue-purple `#2a1f4a` for MS to stay in the palette family
  - Tooltip update on Source column header (`:702` — verified this pass) — add "MS=ModelScope"
- Regenerated `scripts/kilo-benchmarks/models_browser.html` (payload timestamp bumps).

### Behavior Contract

- **D1 — chip renders**: `models_browser.html` contains `data-source="modelscope"` chip HTML.
- **D2 — filter branch present**: JS logic includes `if (s === "modelscope" && !!m.via_modelscope) { pass = true; break; }`.
- **D3 — badge emit present**: JS includes `if (m.via_modelscope) parts.push('<span class="src-badge ms" ...>MS</span>')`.
- **D4 — payload carries flag per row**: regenerated `models_browser.html` payload has `"via_modelscope": 1` on ≥ 20 rows.
- **D5 — chip surfaces expected count**: opening the browser and clicking the `via ModelScope` chip should surface ≥ 20 rows (the ≥ 20 comes from B.3).

### Steps

**D.1 — Edit `models_browser_template.html`.**

After the `via DashScope` chip currently at `:555` (SF chip is at `:554`; DS chip is at `:555` — verified this pass), insert on a new line immediately after `:555`:

```html
<span class="chip" data-source="modelscope" title="Reachable via ModelScope (api-inference.modelscope.cn) — 55-model Alibaba model-hub gateway covering Zhipu GLM direct, Shanghai AI Lab Intern-S, PaddlePaddle ERNIE-4.5, Xiaomi MiMo, Tencent Hunyuan, XiYanSQL, plus Qwen/DeepSeek/MiniMax/Kimi overlap.">via ModelScope</span>
```

After the `dashscope` filter branch currently at `:1116` (SF filter is at `:1115`; DS filter is at `:1116` — verified this pass), insert on a new line immediately after `:1116`:

```javascript
if (s === "modelscope" && !!m.via_modelscope) { pass = true; break; }
```

After the SF badge emit currently at `:1143` (DS badge is at `:1142`; SF badge is at `:1143` — verified this pass), insert on a new line immediately after `:1143`:

```javascript
if (m.via_modelscope) parts.push('<span class="src-badge ms" title="Reachable via ModelScope (api-inference.modelscope.cn) — Alibaba model hub, 55 models">MS</span>');
```

Add CSS class at `:336` (right after `.src-badge.sf` at `:335`):

```css
td.source .src-badge.ms { background: #2a1f4a; border-color: #4a3a80; color: #b8a0e0; }
```

Update Source column header tooltip (`:702` — line drift verified this review pass; SF tooltip currently ends `... K +N% = Kilo price markup ...`) to append `· MS=ModelScope (Alibaba model hub — Zhipu/Intern-S/ERNIE etc.)`.

**Gate D.1 (template edits are literal — verify each):**

```bash
grep -c 'data-source="modelscope"' scripts/kilo-benchmarks/models_browser_template.html
# Expected: 1

grep -c 's === "modelscope"' scripts/kilo-benchmarks/models_browser_template.html
# Expected: 1

grep -c 'src-badge ms' scripts/kilo-benchmarks/models_browser_template.html
# Expected: 2 (1 CSS + 1 JS emit)
```

**D.2 — Regenerate the HTML.**

```bash
python scripts/kilo-benchmarks/export_models_browser.py 2>&1 | tail -3
# Expected: "[export_models_browser] wrote /opt/fabrik/scripts/kilo-benchmarks/models_browser.html"
```

**Live-verify D4 + D5:**

```bash
python -c "
import json
p = '/opt/fabrik/scripts/kilo-benchmarks/models_browser.html'
text = open(p).read()
start = text.find('<script type=\"application/json\" id=\"payload\">') + len('<script type=\"application/json\" id=\"payload\">')
end = text.find('</script>', start)
payload = json.loads(text[start:end])
chat = payload.get('chat_models', [])
ms_rows = [m for m in chat if m.get('via_modelscope') == 1 and m.get('status')=='active' and m.get('blocked')==0]
print(f'  via ModelScope chip surfaces {len(ms_rows)} active+unblocked rows')
assert len(ms_rows) >= 20, f'D.5 assertion failed — only {len(ms_rows)} rows'
print('  first 6 MS rows:', [m['id'] for m in ms_rows[:6]])
print('D LIVE OK')
"
```

**D.3 — Doc-sync + review + commit.** Same shape as A.4. BLOCKING pool `/fabrik-review` looped to no-op.

Commit staging:

```bash
git add scripts/kilo-benchmarks/models_browser_template.html \
        scripts/kilo-benchmarks/models_browser.html
```

---

## Phase E — Final gate + docs review + CHANGELOG + INDEX + archive

**Goal.** Prove the whole-plan diff is green + docs converged + plan archived.

### Steps

**E.1 — Run `/fabrik-docs-review`** on the cumulative changed surface (Phase A → D).

**E.2 — Update `CHANGELOG.md`** with a single consolidated `## [Unreleased]` entry:

```
### Added — Plan 2: ModelScope wired as 5th peer gateway (55 models, ZhipuAI/Intern-S/ERNIE coverage) (2026-07-09)

Full 5-step wire mirroring the SiliconFlow 2026-07-09 pattern. Coverage lift: adds direct routes to Zhipu GLM (5.2/5.1/5/4.7-Flash), Shanghai AI Lab Intern-S1/S1-mini/S2-Preview (InternLM3 successors), PaddlePaddle ERNIE-4.5 (0.3B/21B-A3B/300B-A47B/VL-28B), Xiaomi MiMo, Tencent Hunyuan Hy3, XiYanSQL — none previously reachable via OR + SF. Plus Qwen (20 models) / MiniMax M2.5-M3 / DeepSeek V3.2-V4 / Kimi K2.5 alt routes. Phase A: `AI_VENDOR_ACCESS.md` row + `agents.via_modelscope INTEGER` column + re-seed. Phase B: `scrape_modelscope_catalog.py` + `daily_refresh.sh` step. Phase C: `update_gateway_counts.py` extension. Phase D: sidebar chip + badge + tooltip in `models_browser_template.html`.
```

**E.3 — Update `INDEX.md`** with the new file:
- `scripts/kilo-benchmarks/scrape_modelscope_catalog.py` — one-liner mirroring the SF entry
- `scripts/kilo-benchmarks/tests/test_scrape_modelscope_catalog.py` — one-liner (test file)

**E.4 — FULL Tier-2 final gate (NOT `--lean`):**

```bash
python scripts/final_gate.py --json 2>&1 | tail -8
# Expected: {"status": "success", "tier": 2, ...}
```

**E.5 — `check_convergence.py`.**

```bash
python scripts/enforcement/check_convergence.py 2>&1 | tail -5
```

**E.6 — Whole-plan `/fabrik-review`** on cumulative diff (`git diff <baseline>..HEAD` where baseline = commit before Phase A's landed). Pool-first + Opus adjudication, looped to no-op.

**E.7 — Update `AGGREGATOR_ROADMAP.md`** — flip the ModelScope row from "KEY IN HAND — signed up. Wire on par with SF" to "**WIRED (2026-07-09, plan-2)** — see rule pack + `AI_VENDOR_ACCESS.md`."

**E.8 — Flip Status + archive.**

```bash
# Edit plan Status: IN-PROGRESS → EXECUTED 2026-07-09 (<final-commit-sha>)
git mv docs/development/plans/2026-07-09-plan-2-modelscope-gateway-wire-in.md \
       docs/development/plans/archived/2026-07-09-plan-2-modelscope-gateway-wire-in.md
# Update .fabrik/plan-locks/…-plan-2-*.json → status=released, plan pointer updated.
```

**E.9 — Doc-sync + commit.** BLOCKING pool `/fabrik-review` on the whole-plan cumulative diff (final safety net).

---

## File Scope (owned paths)

This plan owns these files. `/fabrik-execute-plan` refuses to start if any overlap another active plan-lock.

```
docs/reference/kilo/AI_VENDOR_ACCESS.md                                             [MODIFY Phase A]
scripts/kilo-benchmarks/kilo_agents.db                                              [MODIFY Phase A (column + seed), B (via_modelscope flags)]
scripts/kilo-benchmarks/tests/test_seed_reachability_backfill.py                    [MODIFY Phase A — +1 regression test]
scripts/kilo-benchmarks/scrape_modelscope_catalog.py                                [CREATE Phase B]
scripts/kilo-benchmarks/tests/test_scrape_modelscope_catalog.py                     [CREATE Phase B]
scripts/kilo-benchmarks/daily_refresh.sh                                            [MODIFY Phase B — +1 _step block]
scripts/kilo-benchmarks/update_gateway_counts.py                                    [MODIFY Phase C]
.windsurf/rules/ai/00-ai-model-selection.md                                          [MODIFY Phase C — GATEWAY_COUNTS block regenerated]
scripts/kilo-benchmarks/models_browser_template.html                                 [MODIFY Phase D]
scripts/kilo-benchmarks/models_browser.html                                          [MODIFY Phase D — regenerated]
docs/reference/kilo/AGGREGATOR_ROADMAP.md                                            [MODIFY Phase E — flip ModelScope row to WIRED]
CHANGELOG.md                                                                          [APPEND Phase E]
INDEX.md                                                                              [APPEND Phase E]
docs/development/plans/2026-07-09-plan-2-modelscope-gateway-wire-in.md               [MODIFY Status Phase E; git mv → archived/ at E.8]
.fabrik/plan-locks/2026-07-09-plan-2-modelscope-gateway-wire-in.json                  [CREATE Phase A; MODIFY status=released Phase E.8]
```

**Concurrency check (2026-07-09, live this planning turn):** zero active plan-locks. Disjoint from sibling repos (fabrik-lib already stated they can't run in `/opt/fabrik`).

**Serialization points:** `CHANGELOG.md` + `INDEX.md` (append-only, safe under concurrent plans).

---

## Evidence

### Phase A evidence
- **`path:line`**: `docs/reference/kilo/AI_VENDOR_ACCESS.md:35` — the SiliconFlow row (mirror source). Read this planning turn.
- **`path:line`**: `scripts/kilo-benchmarks/seed_specialty_catalog.py:194` — the per-ID UPDATE that `backfill_reachable_by_provider` complements. Read prior plan (2026-07-09-plan-1).
- **Live command output** (this planning turn):
  ```
  via_openrouter present: True
  via_kilo present:       True
  via_dashscope present:  True
  via_siliconflow present: True
  via_modelscope present:  False        ← Phase A must add this
  ```
- **Baseline before Phase A**: `271/362 (74%) reachable` (this session, prior turn).

### Phase B evidence
- **`path:line`**: `scripts/kilo-benchmarks/scrape_siliconflow_catalog.py:1-171` — reference implementation (171 lines total, confirmed via `wc -l` this turn).
- **`path:line`**: `scripts/kilo-benchmarks/daily_refresh.sh:330` — SiliconFlow wire location (Phase B mirrors this).
- **Live command output** (this planning turn — validating the MS API):
  ```
  HTTP=200
  ModelScope inference API — 55 models
    Qwen:                    20 models
    MiniMax:                  4 models
    ZhipuAI:                  4 models
    PaddlePaddle:             4 models
    deepseek-ai:              3 models
    Shanghai_AI_Laboratory:   3 models
    iic:                      2 models
    stepfun-ai:               2 models
    ...
  ```
- **External research URL**: `https://api-inference.modelscope.cn/v1/models` (live-verified this turn).

### Phase C evidence
- **`path:line`**: `scripts/kilo-benchmarks/update_gateway_counts.py:98-100` — SiliconFlow query block (mirror source).
- **`path:line`**: `.windsurf/rules/ai/00-ai-model-selection.md:119` — GATEWAY_COUNTS block start (target of the update; verified live this pass).
- **Live command output** (this planning turn):
  ```
  | **SiliconFlow** (direct) | 41 | specialist routes (e.g. Hunyuan) |
  ```

### Phase D evidence
- **`path:line`**: `scripts/kilo-benchmarks/models_browser_template.html:554` — SF chip (mirror source).
- **`path:line`**: `scripts/kilo-benchmarks/models_browser_template.html:1115` — SF filter branch.
- **`path:line`**: `scripts/kilo-benchmarks/models_browser_template.html:1143` — SF badge emit.
- **`path:line`**: `scripts/kilo-benchmarks/models_browser.html:335` — `.src-badge.sf` CSS class (mirror source).

### Phase E evidence
- **`path:line`**: `scripts/final_gate.py:1203-1227` — argparse flags (verified in prior plan).
- **`path:line`**: `scripts/enforcement/check_convergence.py:1-30` — plan Status + Evidence + self-audit requirements.

---

## Self-audit

### Grounding passes run this planning turn

1. **Pass 1** — read the SF reference implementation (`scrape_siliconflow_catalog.py`, 171 lines), the daily_refresh wire (`:330`), the update_gateway_counts changes (`:98-100`, `:140`, `:159`), the template chip/filter/badge locations (`:554, :1115, :1143`), and the current agents table schema (`PRAGMA table_info`) — all live this turn.
2. **Pass 2** — live-queried the ModelScope API with the operator's token: 55 models across 20 orgs. Grounded the `_ORG_MAP` from real catalog entries (not inferred from training). Verified the `.cn` endpoint returns 401 (must use `.com` — same lesson as SF).

### Coverage check (What we already agreed ↔ phases)

- 5-step wire from AGGREGATOR_ROADMAP.md → Phases A/B/C/D + Phase E finish
- Key already stored (pre-plan) → not a phase
- `.env.example` template already added (pre-plan) → not a phase
- Vendor row + column → Phase A
- Scraper + daily_refresh → Phase B
- Rule-pack gateway-counts → Phase C
- GUI chip + badge + tooltip → Phase D
- Roadmap doc flip + archive + gate → Phase E

Every agreed item mapped. No gap.

### Cross-phase signature consistency

- **Column `agents.via_modelscope INTEGER`** — Phase A produces; Phase B consumes (SELECT + UPDATE); Phase C consumes (SELECT count); Phase D consumes (payload emit + JS filter). ✓
- **Function `apply_flags(conn, ms_models) -> tuple[int, int, list[str]]`** — Phase B produces; called only internally by `main()`. No cross-phase consumer. ✓
- **`_ORG_MAP` constants** — Phase B produces; internal. ✓
- **Vendor row provider list** — Phase A produces (in the row's DB provider(s) column). Phase A's re-seed consumes via `parse_vendor_catalog(...)`. ✓

### Fixed-point claim

This is the DRAFT. `/fabrik-plan-review` will run the adversarial convergence pass. Do NOT claim CONVERGED here.

---

## Residual unknowns

### Resolved during this plan

- **Provider ORG normalization (specifically ZhipuAI → z-ai vs new zhipuai provider)** — RESOLVED: `z-ai` (Z.ai IS Zhipu, same company rebrand). Verified via DB grep: 12 `z-ai` provider rows, 0 `zhipuai` provider rows.
- **New-row auto-ingest** — RESOLVED: OUT OF SCOPE. Scraper is flip-only; new-row ingestion is `verify_openrouter_catalog.py`'s job. Unmatched IDs printed to stderr; operator handles or a follow-up plan authorizes.
- **Migration mechanism (SQLite ALTER)** — RESOLVED: inline `ALTER TABLE agents ADD COLUMN` with `PRAGMA table_info` guard. Matches sibling `via_siliconflow` / `via_dashscope` column-add pattern.
- **`.env` re-materialization** — RESOLVED: token already stored (commit `1067ab43`). This plan uses `export MODELSCOPE_API_KEY="$(grep '^MODELSCOPE_API_KEY=' /opt/fabrik/.env | cut -d= -f2-)"` — pulls from stored env, never echoes the value into stdout.

### Still-open (each carries a named resolution step)

1. **Unmatched-list length** — the scraper's first live run may leave several ModelScope-only models (Xiaomi/MiMo, Shanghai/Intern-S1, PaddlePaddle/ERNIE-4.5-*) as unmatched IDs (they're not currently in the DB). **Resolution — SELF-SERVICE**: Phase B.3's assertion (`n ≥ 20 rows flipped`) is set at 20 to accommodate a partial match rate. Operator may follow up with a manual `INSERT` for high-value unmatched models OR raise a follow-up plan for new-row auto-ingest. Not blocking.

2. **CSS color for `.src-badge.ms`** — I picked `#2a1f4a` (blue-purple) to visually distinguish from OR (blue), Kilo (purple), DS (green), SF (amber), DirectVendor (dark green). If the operator wants a different palette, they can edit `:336` post-execute. Not blocking.

3. **Gateway-counts block "Notes" text for ModelScope** — Phase C uses `"Zhipu GLM direct, Intern-S, PaddlePaddle ERNIE, Xiaomi MiMo"`. If the operator wants a different one-liner, edit `update_gateway_counts.py:159` post-execute; next re-run regenerates. Not blocking.

**None are cross-AI / cross-repo dependencies.** All self-service.

---

## Handoff

- **Next step (this command, automatic):** `/fabrik-plan-review docs/development/plans/2026-07-09-plan-2-modelscope-gateway-wire-in.md` — adversarial convergence to fixed point, flips `Status: DRAFT → CONVERGED`.
- **User approval gate.**
- `/fabrik-execute-plan docs/development/plans/2026-07-09-plan-2-modelscope-gateway-wire-in.md` — user-triggered.

**Expected wall clock:** Phase A (~15 min), B (~30 min), C (~10 min), D (~15 min), E (~15 min). Total ~85 min.

**Expected spend:** ~$0.30 across per-phase pool `/fabrik-review` rounds.

**💡 fabrik-lib candidate flagged for consideration (post-execute):**
- **Name:** `catalog-scraper` — generic gateway-catalog scraper (mirror-of-SF pattern this plan concretizes).
- **Purpose:** Given a vendor's OpenAI-compatible `/v1/models` endpoint + an `_ORG_MAP` normalization dict, populate a per-model `via_<gateway>` flag on a SQLite `agents` table. Fail-open on missing key/network.
- **Why reusable:** The **third** copy of this pattern in fabrik (`scrape_siliconflow_catalog.py` = 171 LOC; this plan's `scrape_modelscope_catalog.py` will be ~170 LOC; the next Tier-1 signup — Groq, Cerebras, DeepInfra direct — will be another). Three concrete uses ≥ 2 project types = clears the fabrik-lib bar.
- **Rough interface:** `class CatalogScraper: def fetch() -> list[dict]; def normalize(vendor_id: str) -> list[str]; def apply(conn, models) -> tuple[int, int, list[str]]`.
- **Not this plan** — proposal only, per CLAUDE.md fabrik-lib cross-repo HARD STOP. When you sign up 2 more gateways from AGGREGATOR_ROADMAP.md, this becomes an easy pitch to the fabrik-lib AI.
