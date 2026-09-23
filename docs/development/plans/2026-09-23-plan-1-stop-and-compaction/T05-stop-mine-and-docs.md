# T05 — `stop_mine.py` (the miner, sharing `_DEFER_RE`), the V1 backtest, the three docs

## Scope
Implements spec § Cost's measurement tool and § Validation V1, and § Documentation landing sites. The research miner (`docs/reference/research/2026-09-23-stop-compaction/mine.py`) becomes `scripts/sysadmin/stop_mine.py`: it imports `_DEFER_RE` and `deferral_shape` from the hook (the T03 → T05 interface) instead of its own `OPDEC` (`docs/reference/research/2026-09-23-stop-compaction/mine.py:28`), keeps a `--since`/`--until` window (the research copy reads only a lower bound, `docs/reference/research/2026-09-23-stop-compaction/mine.py:20`, A-O37), replaces the home-rooted `ROOT` (`docs/reference/research/2026-09-23-stop-compaction/mine.py:19`) with a `--root` argument, and adds `--backtest` to print V1's fire rate per shape and per repo. Also: `draw.py`'s docstring says it re-draws from the 2026-09-23 reservoirs, not "run mine.py first" (the recorded note). DO-NOT: change the committed verdict files; judge anything (V1's judged sample is T06's).

Depends: T04
Parallel: ⛓️
Complexity: simple
Gate: uv run pytest tests/test_stop_mine.py -q
Docs: `docs/workstation/hooks-index.md` (the Stop row gains DEFERRAL and the DECISION block; the SessionStart row names WHERE YOU ARE) · `docs/reference/thread-anchors.md` (the fold, the DECISION harvest and clear, the compact block) · `docs/workstation/kaizen-event-stream.md` (`cause=deferral`, `shape`, the `decision_block` event) · CHANGELOG (Deltas)

## Touches
- scripts/sysadmin/stop_mine.py — PRIMARY PATH
- tests/test_stop_mine.py
- docs/workstation/hooks-index.md
- docs/reference/thread-anchors.md
- docs/workstation/kaizen-event-stream.md
- docs/reference/research/2026-09-23-stop-compaction/draw.py

## Behavior Contract
- **Given** the promoted miner, **When** it runs the V1 backtest, **Then** it counts deferrals with the hook's own `_DEFER_RE` and reports the fire rate per shape and per repo (spec § Validation V1)

## Steps (the coder's order)
1. Red first, `tests/test_stop_mine.py`: `test_the_miner_counts_with_the_hooks_vocabulary` (the seam: the miner's matcher IS the hook's `_DEFER_RE`, by identity) and a backtest over a synthetic `projects/` tree under a scratch root, with two repos and one turn end per shape, asserting the per-shape and per-repo counts. Watch it FAIL.
2. Write `scripts/sysadmin/stop_mine.py` from the research miner: `# AFTER-EDIT:` header naming the three docs; `--root`, `--since`, `--until`, `--backtest`, `--out`; hook import by path; transcripts read line by line, fail-open per file.
3. Fix `draw.py`'s docstring (`docs/reference/research/2026-09-23-stop-compaction/draw.py:1` says "run mine.py first"; spec § Derivations: the draw is reproducible, the mine is not).
4. The three docs rows, each a present-tense statement of what the code does, citing `path:line`.
5. Run the backtest over the box's real transcripts (`--since 2026-08-09 --until 2026-09-23`) and paste its summary into the Deltas block for T06.
6. Gate green; `uv run ruff check` on the touched files; `python3 scripts/render_doc_script_links.py --check`; CHANGELOG line into the Deltas block.
7. `/fabrik-review` on this ticket's changed surface to a coverage-adjudicated exit; every finding FIXED or REFUTED.
8. Commit with explicit pathspecs + provenance trailers (`Agent-Role: subagent`, `Agent-Task: T05`).

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/40-documentation.md
- docs/reference/research/2026-09-23-stop-compaction/mine.py
- docs/reference/research/2026-09-23-stop-compaction/draw.py
- docs/workstation/hooks-index.md
- docs/reference/thread-anchors.md
- docs/workstation/kaizen-event-stream.md
