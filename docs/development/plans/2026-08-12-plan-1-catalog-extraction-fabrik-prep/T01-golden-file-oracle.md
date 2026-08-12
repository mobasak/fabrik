# T01 — Golden-file oracle: freeze the consumer contract before anything moves

## Scope

Build the regression oracle the whole extraction is gated on: a snapshot+verify harness that freezes
today's **consumed outputs** byte-for-byte, so any later divergence — engine relocated, delivery bridged,
residue excised — is caught mechanically rather than noticed months later as silent staleness. The
harness has two modes: `--snapshot` (write the goldens) and `--verify` (diff live outputs against them,
naming the exact drifted file and exiting non-zero). It lives OUTSIDE the engine tree so it survives the
eventual excise.

The frozen set, grounded 2026-08-12: the **12** `docs/reference/kilo/*.md` selection docs, the **4**
`scripts/kilo_*.json` Traycer registry files, and the marker blocks in the **8** `.windsurf/rules/ai/*.md`
packs that carry `GATEWAY_COUNTS` / `OPENROUTER_ROUTES` / `AUTO-GENERATED` regions.

**Wire the consumer, not just the tool.** An oracle nothing invokes is stored-and-never-read: this ticket
also adds the `--verify` call to `daily_refresh.sh` as a **non-blocking drift canary**, so contract drift is
caught continuously from day one rather than only at migration time. `daily_refresh.sh` is shared with T03
(which un-mutes a different line in the same file) — the spine carries a `Serialized:` row for it, so T01
merges first and T03 rebases onto it.

DO-NOT: do not touch the producers themselves (`rank_*.py`, `export_*.py`, `category_export_markdown.py`)
— this ticket only observes their output. Do not put the harness under `scripts/kilo-benchmarks/`; it must
outlive that tree. Do not make the canary blocking, and do not touch the `rank_task_subagents` invocation
line — that line is T03's.

Depends: —
Parallel: ⚡
Complexity: complex
Gate: python -m pytest tests/catalog_contract/test_snapshot.py -q
Docs: INDEX.md (files added) — orchestrator-applied via Deltas

## Touches
- scripts/catalog_contract_snapshot.py — PRIMARY PATH
- tests/catalog_contract/test_snapshot.py
- scripts/catalog-contract-goldens/
- scripts/kilo-benchmarks/daily_refresh.sh — canary wiring ONLY; shared with T03, see the spine Serialized row

## Behavior Contract
- **Given** the live fabrik tree, **When** `catalog_contract_snapshot.py --snapshot` runs, **Then** it writes a golden for each of the 12 `docs/reference/kilo/*.md` selection docs, the 4 `scripts/kilo_*.json` registries, and the marker blocks of the 8 `.windsurf/rules/ai/*.md` packs (docs/reference/kilo/TASK_SUBAGENT_SELECTION.md:1)
- **Given** goldens captured from an unchanged tree, **When** `--verify` runs, **Then** it reports zero drift and exits 0 (scripts/catalog_contract_snapshot.py:1)
- **Given** a single consumed output has been mutated, **When** `--verify` runs, **Then** it names that exact file in its output and exits non-zero (scripts/catalog_contract_snapshot.py:1)
- **Given** a consumed output is missing entirely, **When** `--verify` runs, **Then** it reports the absence as drift rather than skipping it silently (scripts/catalog_contract_snapshot.py:1)
- **Given** a rule pack whose marker block moved position but whose block CONTENT is unchanged, **When** `--verify` runs, **Then** it reports no drift (the block, not the byte offset, is the contract) (.windsurf/rules/ai/00-ai-model-selection.md:1)
- **Given** the canary wiring, **When** `daily_refresh.sh` runs, **Then** it invokes `catalog_contract_snapshot.py --verify` and reports drift without aborting the run (scripts/kilo-benchmarks/daily_refresh.sh:115)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- .windsurf/rules/core/40-documentation.md
- docs/superpowers/specs/2026-07-26-catalog-extraction-design.md
- scripts/kilo-benchmarks/category_export_markdown.py
- scripts/kilo_model_sync.py
