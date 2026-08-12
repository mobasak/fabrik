# T04 — Relocate the two shared cost JSONs out of the engine tree

## Scope

Close the rule-7 data-file dependency **before** the engine tree is ever deleted, so the eventual excise
cannot cause a silent fleet-wide wrong-number regression.

`scripts/claude_p_cost.py` is fleet-synced consumer infrastructure that **stays in fabrik**, but it resolves
`claude_p_cost.json` and `claude_price_ratios.json` through a fallback chain: env override → `_HERE/<name>`
(i.e. `scripts/`) → `_HERE/"kilo-benchmarks"/<name>`. Both files exist **only** under
`scripts/kilo-benchmarks/` today, so the consumer is living on its second-choice path. When the engine tree
goes, that path vanishes and `cached_amortized_per_mtok()` fail-softs to the wrong `$0.093/M` anchor — a
wrong number, fleet-wide, with no crash and no alert.

The fix is a **copy, never a move**: `git add` a copy at `scripts/<name>`, leaving the originals in place.
A bare `mv` would break the engine's own readers, which resolve `_HERE`-relative and keep running
throughout the migration (`derive_cost.py`, `rank_task_subagents.py`). After the copy, `scripts/` becomes
the consumer's first-choice path and the only surviving copy post-excise.

**⚠️ The copy creates a refresh divergence — own it explicitly.** `refresh()` writes to `_cost_path()`
→ `_find()` first-choice `_HERE/<name>`. Today that is the engine's copy; **after this ticket it becomes
`scripts/<name>`**, so the engine's copy stops being updated. That is acceptable ONLY because no cron runs
`--refresh` today (`crontab -l | grep -c claude_p_cost` → 0) and the migration window is short — but the
ticket must state it, because the engine's readers (`derive_cost.py:23`, `:234`,
`rank_task_subagents.py:483`) publish the ② amortized rate into `TASK_SUBAGENT_SELECTION.md`, which is
fleet-synced and frozen by T01's oracle. If the window lengthens, refresh both copies.

DO-NOT: do not `mv` or delete the originals under `scripts/kilo-benchmarks/`; do not edit
`scripts/claude_p_cost.py`'s resolution order — the existing fallback chain is what makes the copy work.

Depends: —
Parallel: ⚡
Complexity: simple
Gate: python -m pytest tests/catalog_contract/test_cost_json_resolution.py -q
Docs: INDEX.md (files added) — orchestrator-applied via Deltas

## Touches
- scripts/claude_p_cost.json — PRIMARY PATH
- scripts/claude_price_ratios.json
- tests/catalog_contract/test_cost_json_resolution.py

## Behavior Contract
- **Given** the copies exist at `scripts/`, **When** `claude_p_cost.py._find()` resolves either name, **Then** it returns the `scripts/` path, not the `kilo-benchmarks/` fallback (scripts/claude_p_cost.py:53)
- **Given** the `scripts/kilo-benchmarks/` originals are absent (simulating post-excise), **When** `cached_amortized_per_mtok()` runs, **Then** it returns the real rate and never the `$0.093/M` fail-soft anchor (scripts/claude_p_cost.py:97)
- **Given** the copy has been made, **When** the engine's own readers run, **Then** they still resolve their `_HERE`-relative originals unchanged (scripts/kilo-benchmarks/derive_cost.py:23)
- **Given** the copies exist, **When** `python scripts/claude_p_cost.py --refresh` runs, **Then** the ticket documents which copy it writes and how the engine's copy stays valid for the migration window (scripts/claude_p_cost.py:157)
- **Given** the two copies, **When** their contents are compared to the originals, **Then** they are byte-identical at copy time (scripts/kilo-benchmarks/claude_p_cost.json:1)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/development/plans/2026-07-26-plan-1-ai-model-catalog-extraction.md
- scripts/claude_p_cost.py
- scripts/kilo-benchmarks/derive_cost.py
- scripts/kilo-benchmarks/rank_task_subagents.py
