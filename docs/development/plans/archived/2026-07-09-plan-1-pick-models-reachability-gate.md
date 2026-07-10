# pick_models reachability gate — close the "AI recommends unreachable model" trap

**Status:** EXECUTED 2026-07-09 — Phases 0/A/B/C/D shipped. Live: 25 → 260 reachable (7% → 71%), 18 B-contract tests green, live INSERT recorded reachable_at_dispatch=1 on subagent_runs. Loop.py auto-wire deferred as residual (callers pass kwarg explicitly). Commits: 2e4505e1 (0) · 073aee70 (A) · cbe0f056 (B) · 4d0457e8 (C) · 5a45b3a2 (D).
**Date:** 2026-07-09
**Owner:** primary (this session)
**Goal:** Make `libs/subagents.pick_models(task_type)` refuse — by default — to return a model whose vendor requires an API key the operator doesn't currently have. Today's DB shows **93% of active agents (344/369) flagged unreachable** — every call is a silent-fail trap. Root cause is a real seeding gap (bulk backfill by provider never happens) compounded by the absence of a reachability filter in the emit path. Fix both.

## What we already agreed (Phase 0)

Source of truth: the direct conversation this turn (proposal presented → user said "proceed"). No `/fabrik-spec` doc; the design is fully pinned in the sketch already accepted.

- **The trap.** `pick_models(task_type)` currently enforces the ≤$1.5/Mtok cost cap but NOT any reachability check. 344/369 active agents show `reachable_with_existing_keys=0`. Every dispatch that lands on one of those hits an unusable route → silent-fail / wasted call.
- **The seeding gap is real (Phase 0 must fix it first, else Phase A's filter empties the pool).** `AI_VENDOR_ACCESS.md:20` says OpenRouter routes to `openai, anthropic, google, x-ai, meta-llama, qwen, deepseek, mistralai, moonshotai, z-ai, minimax, bytedance-seed, microsoft, nvidia, hexgrad, canopylabs, zyphra, sesame`. But `seed_specialty_catalog.py:194` only runs `UPDATE agents SET reachable_with_existing_keys = ? WHERE id = ?` for the specific ids it seeds (TTS/STT/translation/image_gen rows) — the 340+ pre-existing LLM rows whose providers ARE in that OR list never get their flag flipped. Diagnosed live this planning turn: `openai` provider = 65 rows, 4 reachable; `anthropic` = 15 rows, 0 reachable; `deepseek` = 10 rows, 0 reachable.
- **Chosen approach — 5 phases, dependency-ordered:**
  - **Phase 0** (seeding backfill): extend `seed_specialty_catalog.py` with a `backfill_reachable_by_provider()` step that walks every `provider` listed in `AI_VENDOR_ACCESS.md`'s gateway rows AND bulk-UPDATEs every `agents` row whose provider matches. Idempotent. Live coverage gate: after re-seed, reachable must be ≥ 60% of active — below that, the AI_VENDOR_ACCESS.md OR row is stale and Phase 0 escalates.
  - **Phase A** (emit-time filter): `rank_coding_subagents.py:268` + `rank_task_subagents.py` add `AND reachable_with_existing_keys=1` to their WHERE clause. Emit `<!-- reachable: N/M -->` comment header into the selection MDs so downstream `pick_models` never sees an unreachable row.
  - **Phase B** (`pick_models` opt-out flag): add `require_reachable: bool = True` keyword-only param to `libs/subagents/select.py::pick_models`. Default True (safer than current). `require_reachable=False` matches CURRENT behavior for benchmarking on-request models the operator is considering signing up for.
  - **Phase C** (fallback + telemetry): if reachable-filter empties the pool for a task_type, `pick_models` emits stderr WARN + falls through to the unreachable pool (fail-open — don't wedge daily_refresh). Add a `reachable_at_dispatch INTEGER` column on `subagent_runs` so the flywheel can score reachable vs unreachable pools separately.
  - **Phase D** (cross-project sync + docs): mirror the `libs/subagents/select.py` change into the fabrik-lib upstream via `UPSTREAM_FEEDBACK.md`; update `.windsurf/rules/ai/00-ai-model-selection.md`, `docs/CONFIGURATION.md`, and `docs/reference/kilo/AI_VENDOR_ACCESS.md` prose.
  - **Phase E** (final gate + archive).
- **Rejected alternatives** (both user-confirmed as "polish, leave until operator use case forces them"):
  - rent-gpu + candidates browser tab integration into `pick_models` — these are planning-time signals, not per-call decisions; belongs in a monthly-report script, not in the gate.
  - `rank_music_gen.py` — deferred until operator use case.
- **Constraints stated by the user:**
  - "half-day of work" — plan sized to fit.
  - "single-plan scope, disjoint from Plans 5/6" — verified live: plan 5 owns `sysadmin/**`, plan 6 owns `libs/subagents/UPSTREAM_FEEDBACK.md` fleet-sync; my scope is `scripts/kilo-benchmarks/**` + `libs/subagents/select.py` + `libs/subagents/pg_ledger.py`.

**Branch: RICH.** The sketch pins goal + approach + every phase. No brainstorming. No `/fabrik-spec` needed.

**Question bar — all resolved during this planning turn:**
- **Schema addition mechanism** (Phase C's `reachable_at_dispatch` column): use `ALTER TABLE ... ADD COLUMN reachable_at_dispatch INTEGER` via a new migration file `scripts/kilo-benchmarks/migrations/2026-07-09-add-reachable-at-dispatch.sql` following the pattern of `apply_subagent_runs_ddl.sh` (idempotent `IF NOT EXISTS`). Not a runtime block — `pg_ledger.py`'s INSERT falls through to the column list it constructs; a missing column just means the value isn't recorded (fail-soft). Decided.
- **Cross-repo edit** (`libs/subagents/select.py` — is this a vendored copy?): live-checked `diff -q /opt/fabrik/libs/subagents/agent.py /opt/fabrik-lib/subagents/subagents/agent.py` → **the two files DIFFER**; hub has a locally-modified copy. Edits land here + upstream via `UPSTREAM_FEEDBACK.md` (per CLAUDE.md § fabrik-lib). No cross-repo commit — only append to `UPSTREAM_FEEDBACK.md` in the fabrik-lib repo (allowed per CLAUDE.md fabrik-lib exception). Decided.
- **What counts as "reachable via OR"** (the Phase 0 seeding): the exact string list from `AI_VENDOR_ACCESS.md:20` OpenRouter row (18 providers). Additionally, the Kilo CLI row at `:21` grants the SAME providers subscription-billed. The seeder should union both. Decided.

None deferred. No `[OPEN → resolve at Phase N]` residuals — all execution-blocking questions answered here.

## Global Constraints

Verbatim from binding sources — every phase inherits these:

- **Python 3.11+**, stdlib-first (`sqlite3`, `subprocess`, `re`, `pathlib`, `datetime`). No new pip deps this plan.
- **Explicit `git add <path>` only** — never `git add -A` / `git add .` / `git commit -a` (CLAUDE.md HARD STOP).
- **Hub-side scope.** All edits are under `scripts/kilo-benchmarks/**` + `libs/subagents/**` + docs. No `compose.yaml`, no `fabrik apply`, no VPS deploy, no `specs/services/*.yaml` touched.
- **No new deps files** — `pyproject.toml`, `requirements.txt`, `uv.lock` untouchable (HARD STOP).
- **Fail-soft everywhere.** Filter that empties the pool must NEVER raise; it emits a WARN + falls through. Same discipline as the ≤$1.5 cost cap.
- **Backwards compatible.** `pick_models(task_type)` current callers (no kwarg) get the DEFAULT `require_reachable=True` — which becomes the new safer floor. Callers wanting the old permissive behavior pass `require_reachable=False` explicitly. No callsite change forced.
- **Provenance trailers** on every commit — `Agent-Role: orchestrator`, `Agent-Phase: 0|A|B|C|D|E`, `Agent-Context:` one-liner.
- **Governance-sync awareness.** `scripts/kilo-benchmarks/**` + `libs/subagents/**` are **NOT** in `scripts/fabrik_synced_manifest.py` — they're hub-only. Safe to edit.
- **`.env` autoload discipline.** Any new env var (Phase C's `FABRIK_SUBAGENT_REQUIRE_REACHABLE`) is optional with a sensible default; no ambient state.

## Context Ledger

Binding sources — the cold executor inherits all of these.

| Source | What binds | Grounded ref |
|---|---|---|
| ACTIVE rule pack `core/10-python.md` | Python 3.11 typing; no bare `except`; no `print` in libraries | `.windsurf/rules/core/10-python.md` (19 ACTIVE packs via `select_rules.py`) |
| ACTIVE rule pack `core/25-data-postgres.md` | idempotent DDL, additive columns only, no `DROP`; fail-soft on migration failures | `.windsurf/rules/core/25-data-postgres.md` |
| ACTIVE rule pack `core/45-testing-strategy.md` | Behavior Contract: one test per user-observable behavior, risk-ordered, TDD for the risky | `.windsurf/rules/core/45-testing-strategy.md` |
| ACTIVE rule pack `ai/00-ai-model-selection.md` | § Selection MDs — read the `*_SELECTION.md` + `AI_VENDOR_ACCESS.md` before proposing a model. The rule pack itself is the doc Phase D updates | `.windsurf/rules/ai/00-ai-model-selection.md` |
| ACTIVE rule pack `core/62-using-subagents.md` | pool-default for gradeable fan-out; `record_agent_run(spec, result)` + `results_table`; `check_subagent_flywheel.py` gates | `.windsurf/rules/core/62-using-subagents.md` |
| `libs/subagents/select.py:275` — real API | `pick_models(task_type: str, n: int = 1, *, max_cost_per_mtok: float\|None = None, exclude: tuple[str, ...] = (), prefer: Literal["quality","value"] = "quality", ranking: dict[str, list[str]]\|None = None, live: bool\|None = None, allow_above_cap: bool = False) -> list[str]` — verified live this turn | Read `:274-300` this turn |
| `libs/subagents/pg_ledger.py:56` — real API | `record_agent_run(spec, result, *, quality_score=None, project=None, ...)`; INSERT builds column list dynamically — safe to add a column | Read this turn |
| `libs/subagents/README.md` — real capability | The vendored subagents module is the reachability-filter home — the change belongs upstream in fabrik-lib (via `UPSTREAM_FEEDBACK.md`) | Confirmed diff vs fabrik-lib this turn |
| `scripts/kilo-benchmarks/rank_coding_subagents.py:268` | `WHERE status='active' AND service_type='llm' AND ({placeholder}) AND quality_tier IS NOT NULL AND quality_tier >= 1` — real target for Phase A filter injection | Read this turn |
| `scripts/kilo-benchmarks/rank_task_subagents.py:72` | Query hits `subagent_runs`, not `agents` — Phase A's filter goes on the JOIN'd agents side | Read this turn |
| `scripts/kilo-benchmarks/seed_specialty_catalog.py:194` | `UPDATE agents SET reachable_with_existing_keys = ? WHERE id = ?` — per-ID only; Phase 0 adds a bulk `WHERE provider IN (...)` UPDATE | Read this turn |
| `docs/reference/kilo/AI_VENDOR_ACCESS.md:20-21` | OpenRouter gateway row lists 18 providers as reachable; Kilo CLI row at `:21` peer-gateway grants the same providers — Phase 0 unions both | Read live this turn (line quotes above) |
| `scripts/kilo-benchmarks/kilo_agents.db` schema | `agents.reachable_with_existing_keys INTEGER NOT NULL DEFAULT 0` — column already present, no new migration on the SQLite side | Verified live: `PRAGMA table_info(agents)` this turn |
| `AGENTS.md` invariants | **N/A** — no service/DB/network invariant touched. All hub-side scripts, no compose | Spec inspection |
| `shape:` flag | **N/A** — no `specs/services/*.yaml` touched | Spec inspection |
| fabrik-lib verdict | **Enhance vendored `libs/subagents/select.py` in-project + upstream via `UPSTREAM_FEEDBACK.md`.** No new module needed. The reachability filter is a small semantic addition to an existing capability, not a new one. `fabrik-lib/README.md` module table has no reachability-specific module — the change stays inside `subagents`. | `/opt/fabrik-lib/subagents/README.md` (read this turn) |

**fabrik-lib consult:** Confirmed. The `subagents` module owns the semantic; the change goes upstream via `UPSTREAM_FEEDBACK.md`. No new fabrik-lib candidate.

---

## Phase 0 — Fix the seeding gap so Phase A's filter doesn't empty the pool — ✅ EXECUTED 2026-07-09

**Goal.** Extend `seed_specialty_catalog.py` with a bulk-UPDATE that walks every gateway row in `AI_VENDOR_ACCESS.md` (`OpenRouter` at `:20`, `Kilo CLI` at `:21`, plus any `✅` direct-vendor row) and flips `agents.reachable_with_existing_keys=1` for every existing row whose `provider` matches. Re-run against the live DB. Coverage gate: reachable count must lift from 25/369 (7%) to ≥ 60% of active — below that, escalate (AI_VENDOR_ACCESS.md OR row is stale).

### Interfaces

**Consumes:** nothing (this is a root fix; Phase A depends on it).

**Produces:**
- New function `backfill_reachable_by_provider(conn: sqlite3.Connection, accessible_providers: set[str]) -> int` in `scripts/kilo-benchmarks/seed_specialty_catalog.py`. Returns the count of rows flipped. Idempotent.
- Modified `main()` in the same file — new call wired after existing per-ID UPDATEs.
- Regression test `scripts/kilo-benchmarks/tests/test_seed_reachability_backfill.py`.

### Behavior Contract

- **B0.1 — bulk backfill by provider** (highest-risk, TDD): given a fixture DB with providers `openai` (2 rows, unreachable), `anthropic` (1 row, unreachable), `unknown_provider` (1 row, unreachable), and `accessible_providers={openai, anthropic}`, `backfill_reachable_by_provider()` flips exactly 3 rows and returns `3`; the `unknown_provider` row stays at 0.
- **B0.2 — idempotent second run**: running the same call twice on the same fixture returns `3` then `0` (already flipped rows don't count as newly flipped).
- **B0.3 — respects only accessible set**: `accessible_providers=set()` → 0 rows flipped, no error.
- **B0.4 — live coverage gate**: after `main()` runs against the real `kilo_agents.db`, reachable-active count is ≥ 60% (i.e. ≥ 222 rows) of the 369 active-unblocked baseline.

### Steps

**0.1 — Preflight probe (halts the phase if fixture setup is impossible).**

```bash
python -c "import sqlite3; sqlite3.connect(':memory:').cursor().execute('CREATE TABLE t (x INT)')" && echo "sqlite3 OK"
python -m pytest --version 2>&1 | head -1     # → "pytest 9.0.2" (probed 2026-07-08 this session)
ls scripts/kilo-benchmarks/kilo_agents.db      # → present
```

If any probe fails: `BLOCKED: <what> — searched: 0.1 preflight — missing: <need>`.

**0.2 — TDD: write B0.1/B0.2/B0.3 tests FIRST** at `scripts/kilo-benchmarks/tests/test_seed_reachability_backfill.py`.

```python
"""Behavior Contract for seed_specialty_catalog.backfill_reachable_by_provider."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _fixture(tmp_path):
    p = tmp_path / "agents.db"
    con = sqlite3.connect(str(p))
    con.execute(
        "CREATE TABLE agents (id TEXT PRIMARY KEY, provider TEXT, status TEXT, "
        "blocked INT DEFAULT 0, reachable_with_existing_keys INT DEFAULT 0)"
    )
    con.executemany(
        "INSERT INTO agents (id, provider, status) VALUES (?, ?, 'active')",
        [
            ("openai/gpt-5", "openai"),
            ("openai/gpt-5-codex", "openai"),
            ("anthropic/claude-opus-4.5", "anthropic"),
            ("unknown/foo", "unknown_provider"),
        ],
    )
    con.commit()
    return p, con


def test_backfill_flips_only_matching_provider_rows(tmp_path):
    from seed_specialty_catalog import backfill_reachable_by_provider

    _p, con = _fixture(tmp_path)
    n = backfill_reachable_by_provider(con, {"openai", "anthropic"})
    assert n == 3, f"expected 3 flips, got {n}"
    reachable_by_provider = dict(
        con.execute(
            "SELECT provider, SUM(reachable_with_existing_keys) FROM agents GROUP BY provider"
        )
    )
    assert reachable_by_provider["openai"] == 2
    assert reachable_by_provider["anthropic"] == 1
    assert reachable_by_provider["unknown_provider"] == 0


def test_backfill_idempotent_second_run(tmp_path):
    from seed_specialty_catalog import backfill_reachable_by_provider

    _p, con = _fixture(tmp_path)
    assert backfill_reachable_by_provider(con, {"openai", "anthropic"}) == 3
    assert backfill_reachable_by_provider(con, {"openai", "anthropic"}) == 0


def test_backfill_empty_accessible_set(tmp_path):
    from seed_specialty_catalog import backfill_reachable_by_provider

    _p, con = _fixture(tmp_path)
    assert backfill_reachable_by_provider(con, set()) == 0
```

**Gate 0.2 (must FAIL RED — function doesn't exist yet):**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_seed_reachability_backfill.py -x 2>&1 | tail -5
# Expected: ImportError / AttributeError — backfill_reachable_by_provider not defined.
```

**0.3 — Implement `backfill_reachable_by_provider` in `seed_specialty_catalog.py`.**

Add after the existing per-ID UPDATE loop:

```python
def backfill_reachable_by_provider(
    con: sqlite3.Connection, accessible_providers: set[str]
) -> int:
    """Bulk-flip `agents.reachable_with_existing_keys=1` for every row whose
    provider is in the accessible set AND is currently 0. Returns the count of
    rows actually flipped this call (idempotent — repeat runs return 0).
    """
    if not accessible_providers:
        return 0
    placeholders = ",".join("?" for _ in accessible_providers)
    cur = con.execute(
        f"""
        UPDATE agents
        SET reachable_with_existing_keys = 1
        WHERE reachable_with_existing_keys = 0
          AND provider IN ({placeholders})
        """,
        tuple(sorted(accessible_providers)),
    )
    n = cur.rowcount
    con.commit()
    return n
```

Wire into `main()` after the existing per-ID UPDATE:

```python
accessible = _parse_ai_vendor_access(...)     # existing
accessible_providers = {p for p, ok in accessible.items() if ok}
n_flipped = backfill_reachable_by_provider(con, accessible_providers)
print(f"[seed] backfilled reachable_with_existing_keys=1 on {n_flipped} rows by provider match")
```

**Gate 0.3:**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_seed_reachability_backfill.py -v 2>&1 | tail -6
# Expected: 3 passed
```

**0.4 — Live re-seed + B0.4 coverage gate.**

```bash
python scripts/kilo-benchmarks/seed_specialty_catalog.py 2>&1 | tail -5
python -c "
import sqlite3
con = sqlite3.connect('scripts/kilo-benchmarks/kilo_agents.db')
total, reach = con.execute(\"\"\"
    SELECT COUNT(*), SUM(reachable_with_existing_keys)
    FROM agents WHERE status='active' AND blocked=0
\"\"\").fetchone()
pct = 100 * reach // total
print(f'reachable={reach}/{total} ({pct}%)')
assert pct >= 60, f'B0.4 coverage gate failed — {pct}% < 60%; AI_VENDOR_ACCESS.md OR row likely stale'
print('B0.4 LIVE OK')
"
```

If the assert fails (< 60%): `BLOCKED: reachable coverage <60% — searched: AI_VENDOR_ACCESS.md:20-21 OR/Kilo rows — missing: an additional provider not yet listed as accessible; escalate to operator to update AI_VENDOR_ACCESS.md`.

**0.5 — Doc-sync + review + commit.**

1. `python scripts/enforcement/check_doc_sync.py` → resolve any WARN whose trigger is in Phase-0's diff.
2. **BLOCKING gate:** invoke `/fabrik-review` on Phase 0's diff (`scripts/kilo-benchmarks/seed_specialty_catalog.py` + `scripts/kilo-benchmarks/tests/test_seed_reachability_backfill.py`). Full adversarial methodology per `/fabrik-review` skill — **PARALLEL pool finders (`minimax/minimax-m3` via `run_agents`, `pick_models("review")`, ≤$0.30 each, `wall_clock_s=900`, `allow_ungrounded=True` with diff inlined) + refute/merge/decide by orchestrator (Opus) + prove-before-fix each surviving finding with a kept regression test**. Every finding terminates FIXED or REFUTED (no "noted / deferred"). Loop until one full pass returns zero CONFIRMED or PLAUSIBLE. Each pool finder owes `record_agent_run(spec, r, quality_score=<0-5>, project="fabrik-hub")`.
3. Commit:

   ```bash
   git add scripts/kilo-benchmarks/seed_specialty_catalog.py \
           scripts/kilo-benchmarks/tests/test_seed_reachability_backfill.py \
           scripts/kilo-benchmarks/kilo_agents.db
   git commit -m "$(cat <<'EOF'
   fix(kilo-db): Phase 0 — bulk backfill reachable_with_existing_keys by provider

   Plan 1 (pick_models reachability gate) Phase 0.

   Root cause: seed_specialty_catalog.py only ran UPDATE ... WHERE id=? for
   specific specialty-seeded rows. 340+ pre-existing LLM rows whose providers
   ARE in AI_VENDOR_ACCESS.md's OpenRouter route list never had their flag
   flipped — so 344/369 active agents (93%) showed unreachable, and every
   pick_models call had a 93% silent-fail rate.

   Fix: new backfill_reachable_by_provider(conn, accessible_providers) does a
   single bulk UPDATE by provider IN (...). Idempotent (returns 0 on second
   run). 3 behavior-contract tests + live coverage assertion (post-seed
   reachable count ≥ 60% of active).

   Agent-Role: orchestrator
   Agent-Phase: 0
   Agent-Context: seeding backfill; 3 B-contract tests + live coverage gate green

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
   )"
   ```

---

## Phase A — Filter at emit time in both rankers — ✅ EXECUTED 2026-07-09

**Goal.** `rank_coding_subagents.py` and `rank_task_subagents.py` add `AND reachable_with_existing_keys=1` to their WHERE clauses so the emitted `CODING_SUBAGENT_SELECTION.md` + `TASK_SUBAGENT_SELECTION.md` never surface unreachable rows. Emit a `<!-- reachable: N/M -->` HTML comment at the top of each MD so downstream (`pick_models`, human operators) sees the coverage.

### Interfaces

**Consumes:** Phase 0's fixed DB state (LLM rows for accessible providers now show reachable=1).

**Produces:**
- Modified `rank_coding_subagents.py` — same public API, new WHERE clause + `<!-- reachable: N/M -->` header.
- Modified `rank_task_subagents.py` — same shape.
- Regression tests `scripts/kilo-benchmarks/tests/test_rank_reachability_filter.py` (2 tests each × 2 rankers = 4 tests).

### Behavior Contract

- **A.1 — coding ranker filter** (TDD): given a fixture with 4 active LLM rows — 2 reachable, 2 unreachable — `rank_coding_subagents` emits only the 2 reachable rows and the MD starts with `<!-- reachable: 2/4 -->`.
- **A.2 — task ranker filter**: same shape, applied to `rank_task_subagents` (the `agents` JOIN side).
- **A.3 — dropped-count logged to stderr**: each ranker prints `[rank_coding] excluded N/M unreachable rows` on stderr so cron logs surface the drop.
- **A.4 — empty pool WARN, not raise**: if the filter empties the pool (all rows unreachable), the ranker still emits an MD (with header showing `0/M`) + WARNs; does NOT raise or exit non-zero.

### Steps

**A.1 — TDD: write B-contract tests FIRST** at `scripts/kilo-benchmarks/tests/test_rank_reachability_filter.py`.

Skeleton (executor fills in the fixture-DB + subprocess invocation shape):

```python
def test_rank_coding_filters_unreachable_and_emits_header(tmp_path):
    # Build a fixture db with 4 active LLM rows: 2 reachable, 2 unreachable.
    # Run rank_coding_subagents.main() on it. Assert output MD has:
    #   - <!-- reachable: 2/4 --> at line 1
    #   - only the 2 reachable ids in the ranked table
    ...

def test_rank_coding_empty_pool_still_emits_header(tmp_path):
    # Fixture: all 4 rows unreachable. Assert MD renders with header
    # <!-- reachable: 0/4 --> and no ranked rows (no crash).
    ...
```

**Gate A.1 (must FAIL RED — filter not yet in code):**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_rank_reachability_filter.py -x 2>&1 | tail -5
```

**A.2 — Add filter to `rank_coding_subagents.py:268`.**

Change:
```python
WHERE status='active' AND service_type='llm'
```
to:
```python
WHERE status='active' AND service_type='llm'
  AND reachable_with_existing_keys=1
```

And emit the header. At the top of the MD builder, insert:

```python
n_reach = con.execute(
    "SELECT COUNT(*) FROM agents WHERE status='active' AND service_type='llm' "
    "AND reachable_with_existing_keys=1"
).fetchone()[0]
n_total = con.execute(
    "SELECT COUNT(*) FROM agents WHERE status='active' AND service_type='llm'"
).fetchone()[0]
md_lines.append(f"<!-- reachable: {n_reach}/{n_total} -->\n")
sys.stderr.write(f"[rank_coding] excluded {n_total - n_reach}/{n_total} unreachable rows\n")
```

**A.3 — Header-only emit for `rank_task_subagents.py` (no SQL filter — grounded live).**

Confirmed this planning turn (`grep -nE "FROM agents|JOIN agents" scripts/kilo-benchmarks/rank_task_subagents.py` returned empty): `rank_task_subagents.py` does NOT read from the `agents` SQLite table at all — its `QUERY` at `:66` hits `subagent_runs` on postgres and treats `model` as a free-form string identifier with no FK to `agents`. So Phase A.3 for rank_task is **header-only**: after `_query_rows()` returns, open the SQLite DB (`scripts/kilo-benchmarks/kilo_agents.db`), read `SELECT id FROM agents WHERE status='active' AND reachable_with_existing_keys=1` into `reachable_set`, emit two comments at the top of the MD:

```python
md_lines.append(f"<!-- reachable: {len(reachable_set)}/{n_total_active} -->\n")
md_lines.append(f"<!-- reachable-set: {', '.join(sorted(reachable_set))} -->\n")
sys.stderr.write(f"[rank_task] emitted reachable-set with {len(reachable_set)} ids\n")
```

The ranked table still surfaces every model (including unreachable ones) — Phase B's `pick_models` reads the reachable-set comment and does the filter at the consumer end. This is the correct architectural split for rank_task since it has no join to `agents`.

**Gate A.2/A.3:**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_rank_reachability_filter.py -v 2>&1 | tail -6
# Expected: 4 passed
```

**A.4 — Live re-run + verify emitted MDs.**

```bash
python scripts/kilo-benchmarks/rank_coding_subagents.py 2>&1 | tail -3
head -1 docs/reference/kilo/CODING_SUBAGENT_SELECTION.md
# Expected: "<!-- reachable: N/M -->" with N > 0

python scripts/kilo-benchmarks/rank_task_subagents.py 2>&1 | tail -3
head -1 docs/reference/kilo/TASK_SUBAGENT_SELECTION.md
# Expected: same header shape
```

**A.5 — Doc-sync + review + commit.** Same shape as Phase 0.5 — **BLOCKING pool `/fabrik-review`** looped to no-op, each pool finder records to the flywheel.

---

## Phase B — `pick_models(task_type, require_reachable=True)` opt-out — ✅ EXECUTED 2026-07-09

**Goal.** Add the kwarg + wire it into the ranking-doc parser so `pick_models` never returns an unreachable model by default. `require_reachable=False` preserves the current (permissive) behavior for benchmarking.

### Interfaces

**Consumes:** Phase A's emitted `<!-- reachable: N/M -->` header AND the reachable-only ranked table body.

**Produces:**
- Modified `libs/subagents/select.py::pick_models` — new kwarg `require_reachable: bool = True`. Signature becomes:
  ```python
  def pick_models(
      task_type: str,
      n: int = 1,
      *,
      max_cost_per_mtok: float | None = None,
      exclude: tuple[str, ...] = (),
      prefer: Literal["quality", "value"] = "quality",
      ranking: dict[str, list[str]] | None = None,
      live: bool | None = None,
      allow_above_cap: bool = False,
      require_reachable: bool = True,
  ) -> list[str]:
  ```
- New env-var override: `FABRIK_SUBAGENT_REQUIRE_REACHABLE=0` disables the filter fleet-wide (escape hatch).
- Regression test `tests/test_pick_models_reachability.py` (or wherever `libs/subagents/tests/` lives — grep for existing `test_pick_models_*` layout during execution).

### Behavior Contract

- **B.1 — default filters unreachable**: given a ranking doc whose header says `<!-- reachable: 2/4 -->` (i.e. Phase A's emitter tagged which ids are reachable), `pick_models("code")` returns only reachable ids from the top.
- **B.2 — opt-out returns everything**: `pick_models("code", require_reachable=False)` returns the full ranked list, including unreachable ids.
- **B.3 — env override**: `FABRIK_SUBAGENT_REQUIRE_REACHABLE=0` matches the opt-out behavior even without the kwarg.
- **B.4 — kwarg-first precedence**: explicit `require_reachable=True` overrides `FABRIK_SUBAGENT_REQUIRE_REACHABLE=0` (kwarg wins).

### Steps

**B.1 — TDD tests FIRST**. Same structure — build a fake ranking doc, monkeypatch `_read_ranking_doc` (or equivalent), assert the returned list respects the filter.

**Gate B.1 (must FAIL RED):**

```bash
python -m pytest tests/test_pick_models_reachability.py -x 2>&1 | tail -5
```

**B.2 — Implement.**

- Add kwarg to signature.
- Read `FABRIK_SUBAGENT_REQUIRE_REACHABLE` env at function entry (default `"1"` → True).
- Parse the `<!-- reachable: N/M -->` header out of the loaded ranking doc; treat every id under a `<!-- reachable-set: [id1, id2, ...] -->` sub-header (a new emit from Phase A — decision: emit BOTH the count AND the explicit set, so `pick_models` doesn't need the DB) as reachable.
- **Update Phase A's emit accordingly**: also emit `<!-- reachable-set: id1, id2, ... -->` as the second HTML-comment line. (Adds ~1 line to Phase A. Interfaces block above updated.)
- Filter the returned ids against `reachable_set` when `require_reachable=True`.

**Gate B.2:**

```bash
python -m pytest tests/test_pick_models_reachability.py -v 2>&1 | tail -6
# Expected: 4 passed
```

**B.3 — Doc-sync + review + commit.** BLOCKING pool `/fabrik-review` looped to no-op.

---

## Phase C — Fallback + `reachable_at_dispatch` telemetry — ✅ EXECUTED 2026-07-09 (fallback WARN landed in Phase B; loop.py auto-wire deferred as residual)

**Goal.** If Phase B's filter empties a task_type's pool, `pick_models` WARNs + falls through to the unfiltered pool (fail-open). Add a `reachable_at_dispatch INTEGER` column on `subagent_runs` and set it inside `record_agent_run` so the flywheel scores reachable vs unreachable pools separately.

### Interfaces

**Consumes:** Phase B's `require_reachable` kwarg + reachable-set parsing.

**Produces:**
- New migration file `scripts/kilo-benchmarks/migrations/2026-07-09-add-reachable-at-dispatch.sql` (idempotent):
  ```sql
  ALTER TABLE subagent_runs ADD COLUMN IF NOT EXISTS reachable_at_dispatch INTEGER;
  CREATE INDEX IF NOT EXISTS idx_subagent_runs_reachable ON subagent_runs (reachable_at_dispatch);
  ```
- Modified `libs/subagents/pg_ledger.py::record_agent_run` — accepts new kwarg `reachable_at_dispatch: int | None = None`, includes it in the INSERT column list if non-None.
- Modified `libs/subagents/select.py::pick_models` — returns not just `list[str]` but attaches reachability to the pick via a side-channel (a module-level `_LAST_PICK_REACHABLE` dict keyed by model_id) that `run_agents` reads and passes to `record_agent_run`. Simple; no signature change on `pick_models`.
- Regression test `tests/test_reachable_at_dispatch.py`.

### Behavior Contract

- **C.1 — empty pool fallback WARNs** (TDD): if the reachable pool for a task_type is empty, `pick_models` emits stderr WARN "no reachable model for task=X — falling back to unreachable pool" AND returns the unreachable top pick.
- **C.2 — migration is idempotent**: running the migration twice on the same DB is a no-op the second time (no error).
- **C.3 — `record_agent_run` writes `reachable_at_dispatch`**: given `reachable_at_dispatch=1`, the resulting DB row has that value; given `None`, the column stays NULL.
- **C.4 — pre-migration is a documented no-op via FAIL-OPEN**: if a code copy with the new 12-column `_INSERT` runs against a DB that hasn't migrated yet, psycopg raises `UndefinedColumn`; `record_run`'s existing `except Exception:` at `pg_ledger.py:85` catches it and returns False (unrecorded run) — no crash. The sequencing invariant (Phase C.1 runs migration before C.3 code lands) prevents this in normal operation; the fail-open is defense-in-depth. Test asserts: patched `.execute()` that raises `UndefinedColumn` results in `record_agent_run(...) is False` and no re-raise.

### Steps

**C.0 — Toolchain preflight (halts the phase if any probe fails; ~2 s).**

```bash
which psql && psql --version 2>&1 | head -1
                # → /usr/bin/psql · "psql (PostgreSQL) 16.14 …" (probed 2026-07-09 this planning turn)
test -n "$SUBAGENT_RUNS_DSN" && echo "DSN set" || echo "DSN MISSING"
                # → "DSN set" (grep grep .env: SUBAGENT_RUNS_DSN=postgresql:///fabrik_analytics; verified in prior plan runs)
```

If `psql` is missing: `BLOCKED: psql not on PATH — searched: C.0 preflight — missing: apt-get install postgresql-client`. If DSN is missing: `BLOCKED: SUBAGENT_RUNS_DSN not set — searched: .env + shell env — missing: DSN entry`.

**C.1 — Write the migration file.**

```bash
mkdir -p scripts/kilo-benchmarks/migrations
cat > scripts/kilo-benchmarks/migrations/2026-07-09-add-reachable-at-dispatch.sql <<'SQL'
-- Plan 1 (pick_models reachability gate) Phase C.
-- Additive column so pool runs record whether pick_models had a reachable option.
ALTER TABLE subagent_runs ADD COLUMN IF NOT EXISTS reachable_at_dispatch INTEGER;
CREATE INDEX IF NOT EXISTS idx_subagent_runs_reachable ON subagent_runs (reachable_at_dispatch);
SQL
```

Run it via the canonical `sudo -n -u postgres psql` pattern (verified live this planning turn — `SUBAGENT_RUNS_DSN` is an INSERT-only role's DSN with no DDL privileges; DDL needs the `postgres` superuser via unix-socket peer auth, mirroring `apply_subagent_runs_ddl.sh`'s pattern at :1-40):

```bash
sudo -n -u postgres psql -v ON_ERROR_STOP=1 -d fabrik_analytics \
  -f scripts/kilo-benchmarks/migrations/2026-07-09-add-reachable-at-dispatch.sql
```

**Gate C.1:**

```bash
sudo -n -u postgres psql -d fabrik_analytics -c "\d subagent_runs" 2>&1 | grep reachable_at_dispatch
# Expected: reachable_at_dispatch | integer
```

**C.1b — Update `apply_subagent_runs_ddl.sh` EXPECTED_COLUMNS constant.**

Grounded live this planning turn: `scripts/kilo-benchmarks/apply_subagent_runs_ddl.sh:26` holds `EXPECTED_COLUMNS="id,ts,project,agent_id,task_type,model,provider,status,cost_usd,turns,latency_s,quality_score,tool_calls"` (13 columns) and ASSERTS this against the live schema on every run. My migration adds a 14th column, so the next `apply_subagent_runs_ddl.sh` invocation will fail loudly unless this constant is updated in the same commit. Append `,reachable_at_dispatch` to the constant.

**Gate C.1b:**

```bash
bash scripts/kilo-benchmarks/apply_subagent_runs_ddl.sh 2>&1 | tail -3
# Expected: "OK" (schema matches EXPECTED_COLUMNS) — no assertion failure
```

**C.2 — TDD tests FIRST** for `pick_models` fallback + `record_agent_run` column.

**Gate C.2 (must FAIL RED):**

```bash
python -m pytest tests/test_reachable_at_dispatch.py -x 2>&1 | tail -5
```

**C.3 — Implement.**

`pick_models` fallback:
```python
if require_reachable and not any_reachable_left(candidates, reachable_set):
    sys.stderr.write(
        f"[pick_models] WARN: no reachable model for task={task_type!r}; "
        "falling back to unreachable pool — dispatch may silently fail.\n"
    )
    reachable_set = None  # disables the filter for this call
```

`pick_models` reachability side-channel:
```python
_LAST_PICK_REACHABLE: dict[str, int] = {}  # module-level

# Inside pick_models after selecting picks:
for m in picks:
    _LAST_PICK_REACHABLE[m] = 1 if (reachable_set and m in reachable_set) else 0
```

`record_agent_run` gains kwarg (in `libs/subagents/pg_ledger.py`):
```python
def record_agent_run(
    spec, result, *, quality_score=None, project=None, dsn=None,
    connect=None, receipt_dir=None,
    reachable_at_dispatch: int | None = None,   # NEW
) -> bool:
    ...
    # Threads reachable_at_dispatch down into record_run which builds the tuple.
```

`_INSERT` at `pg_ledger.py:55` becomes (add column #12 + one more `%s`):
```python
_INSERT = (
    "INSERT INTO subagent_runs "
    "(project, agent_id, task_type, model, provider, status, cost_usd, turns, "
    "latency_s, quality_score, tool_calls, reachable_at_dispatch) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)"
)
```

`record_run(record, ...)` extends the tuple passed to `.execute()` with `record.get("reachable_at_dispatch")` at the end (NULL when unset — the column is nullable).

**Sequencing invariant** (already enforced by Phase C.1 running before C.3): the migration adds the column to the shared `subagent_runs` table BEFORE the code change lands. A vendored copy in another project with the OLD 11-column `_INSERT` continues working (the extra nullable DB column is invisible to older INSERTs). Once that project re-vendors, its new 12-column INSERT hits a DB that already has the column. No pre-migration window exists in normal ordering.

Wire `run_agents` (in `libs/subagents/loop.py` or similar) to read `select._LAST_PICK_REACHABLE.get(spec.model)` and pass it to `record_agent_run`.

**Gate C.3:**

```bash
python -m pytest tests/test_reachable_at_dispatch.py -v 2>&1 | tail -6
# Expected: 4 passed
```

**C.4 — Doc-sync + review + commit.** BLOCKING pool `/fabrik-review` looped to no-op.

---

## Phase D — Cross-project sync + docs — ✅ EXECUTED 2026-07-09

**Goal.** Land the `select.py` + `pg_ledger.py` changes upstream in fabrik-lib via `UPSTREAM_FEEDBACK.md`. Update the 3 docs.

### Interfaces

**Consumes:** all prior phases' code changes.

**Produces:**
- Appended entry in `/opt/fabrik-lib/subagents/UPSTREAM_FEEDBACK.md` (this is the ONE cross-repo write CLAUDE.md permits).
- Modified `.windsurf/rules/ai/00-ai-model-selection.md` § Selection MDs — added rule: "any `pick_models` caller with `require_reachable=False` MUST justify it in an inline comment."
- Modified `docs/CONFIGURATION.md` — row for `FABRIK_SUBAGENT_REQUIRE_REACHABLE`.
- Modified `docs/reference/kilo/AI_VENDOR_ACCESS.md` prose — brief note that the OR / Kilo gateway rows are now the seed source for `pick_models`'s reachability filter.

### Steps

**D.1 — Append UPSTREAM_FEEDBACK.md** (in `/opt/fabrik-lib/`):

```bash
cat >> /opt/fabrik-lib/subagents/UPSTREAM_FEEDBACK.md <<'EOF'

## 2026-07-09 — pick_models reachability gate + record_agent_run.reachable_at_dispatch

Plan `2026-07-09-plan-1-pick-models-reachability-gate` landed 3 semantic additions this
project needs upstream so every vendored copy across the fleet inherits them:

1. **`pick_models(..., require_reachable: bool = True)`** — filters ids whose vendor
   isn't reachable-with-existing-keys. Default True (safer than current behavior).
   `FABRIK_SUBAGENT_REQUIRE_REACHABLE=0` env override.
2. **Empty-pool fallback** — WARN + fall through to unfiltered pool (fail-open,
   never wedge daily_refresh).
3. **`record_agent_run(..., reachable_at_dispatch: int | None = None)`** + additive
   `subagent_runs.reachable_at_dispatch INTEGER` column — the flywheel can now
   score reachable vs unreachable pools separately.

Source diff for reference: /opt/fabrik commits by `Agent-Phase: B|C` on that plan.
EOF
```

**D.2 — Update `.windsurf/rules/ai/00-ai-model-selection.md`** with the new rule.

**D.3 — Update `docs/CONFIGURATION.md`** with the env var.

**D.4 — Update `docs/reference/kilo/AI_VENDOR_ACCESS.md`** prose (small note near the OR/Kilo gateway rows).

**D.5 — Gate + review + commit.** BLOCKING pool `/fabrik-review` looped to no-op.

---

## Phase E — Final gate + docs-review + archive

**Goal.** Whole-plan review, Tier-2 gate green fresh THIS turn, doc-review convergence, CHANGELOG + INDEX entries, plan Status flip + archive.

### Steps

**E.1 — Run `/fabrik-docs-review`** on the cumulative changed surface.

**E.2 — Update `CHANGELOG.md`** — one entry under `## [Unreleased]`:

```
### Added — pick_models reachability gate (Plan 1, 2026-07-09)

Closed the "AI recommends a model whose vendor the operator can't reach → wasted call + silent fail" trap. Pre-fix: 344/369 active agents (93%) flagged unreachable and pick_models had no reachability filter. Fix: (0) seed_specialty_catalog.py bulk backfill by provider — 25 → ≥222 reachable; (A) rank_coding + rank_task filter at emit time + <!-- reachable: N/M --> header; (B) pick_models(..., require_reachable=True) + FABRIK_SUBAGENT_REQUIRE_REACHABLE env; (C) empty-pool WARN fallback + reachable_at_dispatch telemetry column; (D) fabrik-lib upstream via UPSTREAM_FEEDBACK.md.
```

**E.3 — Update `INDEX.md`** — 2 new files (`migrations/*.sql`, `test_seed_reachability_backfill.py`; other tests co-locate under `tests/`).

**E.4 — FULL final gate** (Tier 2, NOT `--lean`):

```bash
python scripts/final_gate.py --json 2>&1 | tail -10
# Expected: {"status": "success", "tier": 2, ...}
```

**E.5 — `check_convergence.py`.**

```bash
python scripts/enforcement/check_convergence.py 2>&1 | tail -5
```

**E.6 — Whole-plan `/fabrik-review`** on cumulative diff (`git diff <step-8 baseline>..HEAD`), pool-first, looped to no-op.

**E.7 — Flip Status + archive.**

```bash
# Edit plan Status: IN-PROGRESS → EXECUTED 2026-07-09 (<final-commit-sha>)
git mv docs/development/plans/2026-07-09-plan-1-pick-models-reachability-gate.md \
       docs/development/plans/archived/2026-07-09-plan-1-pick-models-reachability-gate.md
# Update .fabrik/plan-locks/…-plan-1-*.json → status=released, plan pointer updated.
```

**E.8 — Doc-sync + commit.**

---

## File Scope (owned paths)

This plan owns these files. `/fabrik-execute-plan` refuses to start if any overlap another active plan-lock.

```
scripts/kilo-benchmarks/seed_specialty_catalog.py                                            [MODIFY Phase 0]
scripts/kilo-benchmarks/tests/test_seed_reachability_backfill.py                             [CREATE Phase 0]
scripts/kilo-benchmarks/kilo_agents.db                                                        [MODIFY Phase 0 — re-seed]
scripts/kilo-benchmarks/rank_coding_subagents.py                                             [MODIFY Phase A]
scripts/kilo-benchmarks/rank_task_subagents.py                                               [MODIFY Phase A]
scripts/kilo-benchmarks/tests/test_rank_reachability_filter.py                               [CREATE Phase A]
docs/reference/kilo/CODING_SUBAGENT_SELECTION.md                                             [MODIFY Phase A — re-emit]
docs/reference/kilo/TASK_SUBAGENT_SELECTION.md                                               [MODIFY Phase A — re-emit]
libs/subagents/select.py                                                                      [MODIFY Phase B, C]
libs/subagents/pg_ledger.py                                                                   [MODIFY Phase C]
libs/subagents/loop.py                                                                        [MODIFY Phase C — read _LAST_PICK_REACHABLE]
tests/test_pick_models_reachability.py                                         [CREATE Phase B]
tests/test_reachable_at_dispatch.py                                             [CREATE Phase C]
scripts/kilo-benchmarks/migrations/2026-07-09-add-reachable-at-dispatch.sql                  [CREATE Phase C]
scripts/kilo-benchmarks/apply_subagent_runs_ddl.sh                                            [MODIFY Phase C.1b — EXPECTED_COLUMNS constant]
.windsurf/rules/ai/00-ai-model-selection.md                                                  [MODIFY Phase D]
docs/CONFIGURATION.md                                                                         [MODIFY Phase D]
docs/reference/kilo/AI_VENDOR_ACCESS.md                                                      [MODIFY Phase D — prose only]
CHANGELOG.md                                                                                  [APPEND Phase E]
INDEX.md                                                                                      [APPEND Phase E]
docs/development/plans/2026-07-09-plan-1-pick-models-reachability-gate.md                    [MODIFY Status Phase E; git mv → archived/]
.fabrik/plan-locks/2026-07-09-plan-1-pick-models-reachability-gate.json                      [CREATE Phase 0; MODIFY status=released Phase E.7]
/opt/fabrik-lib/subagents/UPSTREAM_FEEDBACK.md                                               [APPEND Phase D — allowed cross-repo write per CLAUDE.md fabrik-lib exception]
```

**Concurrency check (2026-07-09, live this turn):** zero active plan-locks — verified. Every recently-released lock's owned paths inspected; no overlap. Disjoint from plans 5 (`sysadmin/**`) and 6 (`libs/subagents/UPSTREAM_FEEDBACK.md` fleet-sync; my Phase D append is compatible — both plans append, neither rewrites).

**Serialization points:** `CHANGELOG.md` + `INDEX.md` (appended, never rewritten). `libs/subagents/UPSTREAM_FEEDBACK.md` — Phase 6 (from a sibling AI) also touches this; my Phase D APPENDS one section, doesn't modify existing content. If Plan 6 lock is active at execute time, serialize Phase D after Plan 6 completes.

---

## Evidence

### Phase 0 evidence

- **`path:line`**: `scripts/kilo-benchmarks/seed_specialty_catalog.py:194` — `"UPDATE agents SET reachable_with_existing_keys = ? WHERE id = ?"` — per-ID only; read this turn.
- **`path:line`**: `scripts/kilo-benchmarks/seed_specialty_catalog.py:85-113` — reads AI_VENDOR_ACCESS.md, builds `accessible` dict; the LLM providers land there as `openai`, `anthropic`, etc. Read this turn.
- **`path:line`**: `docs/reference/kilo/AI_VENDOR_ACCESS.md:20` — OpenRouter gateway row with 18 providers. Live-quoted this turn.
- **Live command output** (this turn):
  ```
  active + unblocked agents: 369
     reachable_with_existing_keys=1: 25  (6%)
     reachable_with_existing_keys=0: 344  (93%)
  ```

### Phase A evidence

- **`path:line`**: `scripts/kilo-benchmarks/rank_coding_subagents.py:268` — `WHERE status='active' AND service_type='llm'` — the exact filter injection point. Read this turn.

### Phase B evidence

- **`path:line`**: `libs/subagents/select.py:275-284` — real `pick_models` signature captured this turn. Adding `require_reachable: bool = True` is a keyword-only additive change (backwards compatible).

### Phase C evidence

- **`path:line`**: `libs/subagents/pg_ledger.py:55` — the `_INSERT` string constant `INSERT INTO subagent_runs (project, agent_id, task_type, model, provider, status, cost_usd, turns, latency_s, quality_score, tool_calls) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)` — 11 columns. Phase C **must edit this string** to add `reachable_at_dispatch` as column #12 AND add another `%s` in VALUES AND extend the tuple passed to `.execute()` at the call site. Fail-open at `:85` documented — INSERT-level failures return False. Sequencing: Phase C.1 migration runs BEFORE C.3 code change so the DB has the column when the extended INSERT first fires.
- **Live command output** (this turn):
  ```
  psycopg columns list: ['id', 'ts', 'project', 'agent_id', 'task_type', 'model', 'provider', 'status', 'cost_usd', 'turns', 'latency_s', 'quality_score', 'tool_calls']
  ```
  (13 columns today; add `reachable_at_dispatch` → 14, backwards compatible.)

### Phase D evidence

- **`path:line`**: `.windsurf/rules/ai/00-ai-model-selection.md` — the rule pack Phase D updates. Referenced in Context Ledger.

### Phase E evidence

- **`path:line`**: `scripts/final_gate.py:1203-1227` — `--check --json` flags verified live in prior plan this session.
- **`path:line`**: `scripts/enforcement/check_convergence.py` — requires `## Evidence`, self-audit, path:line per Phase, fenced command output. This plan's Phase 4 section satisfies all four.

---

## Self-audit

### Grounding passes run this turn

1. **Pass 1** — read the 6 key files at exact line ranges; probed live DB for reachable stats; quoted AI_VENDOR_ACCESS.md OR row; confirmed `/opt/fabrik/libs/subagents` diverges from `/opt/fabrik-lib/subagents`; verified `pick_models` signature; confirmed `subagent_runs` schema (13 columns).
2. **Pass 2** (structural check): every phase has `Interfaces` + `Behavior Contract` + `/fabrik-review` step + doc-sync step + commit. TDD-first for every risky path. Global Constraints present. Context Ledger present. File Scope disjoint from active plans.

### Coverage check (What we already agreed ↔ phases)

- Trap #1 (reachability filter missing) → **Phase B**
- Root cause #1 (seeder only per-ID) → **Phase 0**
- Downstream filter at emit → **Phase A**
- Fallback + telemetry → **Phase C**
- fabrik-lib upstream + docs → **Phase D**
- Rejected: rent-gpu integration, music_gen — explicitly out of scope, not a phase.
- Final gate + archive → **Phase E**

Every agreed item mapped. No gap.

### Cross-phase signature consistency

- `backfill_reachable_by_provider(conn, accessible_providers) -> int` — Phase 0 produces + used only in Phase 0's `main()`. ✓
- `pick_models(..., require_reachable=True)` — Phase B produces; Phase C reads the fallback path.  ✓
- `record_agent_run(..., reachable_at_dispatch=None)` — Phase C produces; Phase C's own `loop.py` change consumes. ✓
- `_LAST_PICK_REACHABLE` module-level dict — Phase C internal side-channel; not exposed as public API. ✓
- `subagent_runs.reachable_at_dispatch INTEGER` column — Phase C migration produces; Phase C's `record_agent_run` INSERTs. ✓

### Fixed-point claim

This is DRAFT. `/fabrik-plan-review` will run the adversarial convergence pass. Do NOT claim CONVERGED here.

---

## Residual unknowns

### Resolved during this plan

- **Schema migration mechanism**: additive `ADD COLUMN IF NOT EXISTS` in a dated `.sql` file, run via `psql`. Not deferred.
- **Cross-repo edit path**: `/opt/fabrik/libs/subagents/select.py` local + `/opt/fabrik-lib/subagents/UPSTREAM_FEEDBACK.md` append. Not deferred.
- **Reachable-set encoding in the MD**: HTML comments `<!-- reachable: N/M -->` + `<!-- reachable-set: id1, id2, ... -->` at the top. Locked-in this planning turn.
- **Empty-pool policy**: fail-open with WARN, not raise/exit. Decided.
- **AA gateway list scope**: 18 providers from `AI_VENDOR_ACCESS.md:20` OpenRouter row + Kilo CLI row `:21` (peer gateway, same providers). Locked-in.

### Still-open (each carries a named resolution step)

1. **B0.4 coverage-gate outcome**: post-seed reachable % might fall below 60% if `AI_VENDOR_ACCESS.md` has drifted. **Resolution**: Phase 0's B0.4 gate BLOCKS if <60%, executor surfaces the exact provider gap to the operator; not a runtime discovery.
2. **Tilde-prefixed providers** (`~anthropic`, `~google`, `~moonshotai`, `~openai`, `~x-ai` — 10 rows / 369 = 3% of active): AI_VENDOR_ACCESS.md OR/Kilo rows list non-tilde names, so these rows stay unreachable after Phase 0's backfill. Confirmed live: at least the 5 tilde-prefixed providers have non-tilde duplicate routes already in the DB (they're Kilo peer-gateway aliases). **Resolution — SELF-SERVICE**: Phase 0's `backfill_reachable_by_provider` optionally also matches `TRIM(BOTH '~' FROM provider)` for symmetry; if the executor sees ≥90% coverage without it, ship as-is (tilde rows are duplicates of non-tilde reachable rows — no downstream `pick_models` caller resolves against a tilde-prefixed id). Not blocking; the 60% B0.4 gate is trivially satisfied without touching tildes.

**None are `[OPEN → resolve with <other AI>]` cross-AI dependencies.** All self-service.

---

## Handoff

- **Next step (this command, automatic):** `/fabrik-plan-review docs/development/plans/2026-07-09-plan-1-pick-models-reachability-gate.md` — runs adversarial grounding to fixed point, flips `Status: DRAFT → CONVERGED`.
- **User approval gate.**
- `/fabrik-execute-plan docs/development/plans/2026-07-09-plan-1-pick-models-reachability-gate.md` — user-triggered.

**Expected wall clock:** Phase 0 (~30 min including live re-seed + B0.4 gate), A (~30 min), B (~30 min), C (~45 min with migration + `loop.py` wiring), D (~15 min), E (~15 min). Total ~3 hours.

**Expected spend:** ~$0 inline; ~$0.30 for the per-phase pool `/fabrik-review` rounds (3 minimax-m3 finders × ~$0.03 × 5 phases = ~$0.45 if every phase spawns full parallel finders).
