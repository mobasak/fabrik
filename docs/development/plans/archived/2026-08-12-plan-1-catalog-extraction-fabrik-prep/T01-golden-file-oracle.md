# T01 — Golden-file oracle: freeze the consumer contract before anything moves

## Scope

Build the regression oracle the whole extraction is gated on: a snapshot+verify harness that freezes
today's **engine-produced consumed outputs**, so any later divergence is caught mechanically rather than
noticed months later as silent staleness. Two modes: `--snapshot` (write goldens) and `--verify` (diff live
outputs, name the exact drifted artifact, exit non-zero). It lives OUTSIDE the engine tree so it survives
the eventual excise.

**The frozen set has three parts — a whole-file glob is WRONG and would false-flag daily.** Grounded 2026-08-12:

1. **Whole-file goldens — the 10 engine-WRITTEN docs under `docs/reference/kilo/`,** i.e. every
   `*.md` there that a generator writes. **Excluded, deliberately: `AGGREGATOR_ROADMAP.md` and
   `BENCHMARK_SOURCES.md`** — both have zero writers in `scripts/kilo-benchmarks/*.py` and appear nowhere in
   `daily_refresh.sh`; they are hand-authored, so freezing them would report a human's edit as extraction
   drift. Plus the 4 `scripts/kilo_*.json` Traycer registries.
2. **Marker-BODY goldens keyed by `(host_file, MARKER)`, never whole-file** — because these hosts carry
   hand-authored prose around a generated block. The hosts are NOT confined to `.windsurf/rules/ai/`:
   the 8 `ai/*.md` packs carrying `GATEWAY_COUNTS` / `OPENROUTER_ROUTES`, plus **three more that a
   `ai/*`-only scope would silently drop**: `.windsurf/rules/core/65-rag-search.md` (`EMBEDDING_WINNERS`),
   `docs/reference/kilo/KILO_MODEL_CAPABILITIES.md` (`EMBEDDING_CATALOG`), and
   `docs/reference/kilo/KILO_AGENT_SELECTION_GUIDE.md` (`ROSTER` **and** `EMBEDDING_ROSTER`). The last two
   are ALSO whole-file goldens from part 1, so their generated blocks must be compared as bodies, not twice.
3. **The live consumer DB queries** — the spec's Phase-0 requirement (*"capture the exact DB queries the live
   hub consumers run"*), without which the oracle freezes outputs but not the contract that produces them.

**Volatile-field normalization is REQUIRED, not optional.** These artifacts are rewritten **every single
day** by cron and carry a date *inside* the frozen region: `rank_task_subagents.py:1107` emits
`Last refresh: {today}`, and every marker opener carries `last-refreshed: <date>`. Without normalization the
first `--verify` after midnight reports drift on ~9 docs and 11 marker blocks for reasons that have nothing
to do with the extraction, and T05's barrier run — a different session, very likely a different day — goes
red on arrival.

DO-NOT: do not touch the producers (`rank_*.py`, `export_*.py`, `category_export_markdown.py`,
`update_gateway_counts.py`, `embedding_export_markdown.py`) — this ticket only observes their output. Do not
put the harness under `scripts/kilo-benchmarks/`; it must outlive that tree. Do not make the canary blocking,
and do not touch the `rank_task_subagents` invocation line in `daily_refresh.sh` — that line is T03's.

**Wire the consumer, not just the tool.** An oracle nothing invokes is stored-and-never-read: this ticket
also adds the `--verify` call to `daily_refresh.sh` as a **non-blocking drift canary**. That file is shared
with T03 (which changes a different line) — the spine carries a `Serialized:` row, so T01 merges first.

Depends: —
Parallel: ⚡
Complexity: complex
Gate: python -m pytest tests/catalog_contract/test_snapshot.py -q
Docs: INDEX.md (files added) — orchestrator-applied via Deltas

## Touches
- scripts/catalog_contract_snapshot.py — PRIMARY PATH; carries the mandatory `# AFTER-EDIT:` header
- tests/catalog_contract/test_snapshot.py
- scripts/catalog-contract-goldens/
- scripts/kilo-benchmarks/daily_refresh.sh — canary wiring ONLY; shared with T03, see the spine Serialized row

## Behavior Contract
- **Given** the live fabrik tree, **When** `--snapshot` runs, **Then** it writes whole-file goldens for the 10 engine-written `docs/reference/kilo/*.md` docs and the 4 `scripts/kilo_*.json` registries, and marker-body goldens for all 11 `(host, MARKER)` pairs including the three non-`ai/` hosts (docs/reference/kilo/TASK_SUBAGENT_SELECTION.md:1)
- **Given** a golden whose ONLY difference is a volatile date stamp (`Last refresh:` or `last-refreshed:`), **When** `--verify` runs, **Then** it reports NO drift (scripts/kilo-benchmarks/rank_task_subagents.py:1107)
- **Given** an unchanged tree the day AFTER snapshotting, **When** `--verify` runs, **Then** it reports zero drift and exits 0 (.windsurf/rules/ai/00-ai-model-selection.md:119)
- **Given** a consumed output mutated in a non-volatile field, **When** `--verify` runs, **Then** it names that exact artifact and exits non-zero (scripts/catalog_contract_snapshot.py:1)
- **Given** a consumed output missing entirely, **When** `--verify` runs, **Then** it reports the absence as drift rather than skipping it silently (scripts/catalog_contract_snapshot.py:1)
- **Given** a marker host whose hand-authored prose OUTSIDE the markers changed, **When** `--verify` runs, **Then** it reports no drift for that marker body (the block, not the file, is the contract) (.windsurf/rules/core/65-rag-search.md:134)
- **Given** the hand-authored `AGGREGATOR_ROADMAP.md` or `BENCHMARK_SOURCES.md` is edited, **When** `--verify` runs, **Then** it reports no drift (they are excluded — zero writers, absent from `daily_refresh.sh`) (scripts/kilo-benchmarks/daily_refresh.sh:551)
- **Given** the harness runs, **When** `--snapshot` captures the contract, **Then** it also records the exact DB queries the live hub consumers issue, satisfying the spec's Phase-0 requirement (docs/superpowers/specs/2026-07-26-catalog-extraction-design.md:166)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/kilo-benchmarks/category_export_markdown.py
- scripts/kilo-benchmarks/update_gateway_counts.py
- scripts/kilo-benchmarks/embedding_export_markdown.py
- scripts/kilo_model_sync.py
- scripts/enforcement/check_script_headers.py
