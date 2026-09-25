# T05b — The harvest tells the store whether the register accepted the NEXT; the V1 seam test

## Scope

Implements the `scripts/thread_anchor.py` side of spec § The delta D3 (spec § Cost: no logic change —
the register behaves exactly as today) and the end-to-end V1 seam test through the real Stop hook.

1. `cmd_harvest` (`scripts/thread_anchor.py:535-600`) computes `anchored = bool(matches) and _is_anchor(matches[-1][:300])`
   — the exact string the register judges (`nxt = matches[-1][:300]`, `:576-577`), so a NEXT whose anchor
   shape sits past character 300 is not reported as accepted when the register rejected it —
   and passes it to `_store_harvest` (`:602-614`), which passes `next_anchored=anchored` to
   `w.on_harvest(...)` (`:612`). The quiet-turn call (`:563`) passes `next_anchored=False`.
2. **Version skew.** `thread_anchor.py` and `work.py` ship on the same sync (`scripts/fabrik_synced_manifest.py:62-63`)
   but a repo can hold a newer `thread_anchor.py` beside an older `work.py` for one sync cycle. `_store_harvest`
   passes the keyword only when `"next_anchored"` is in `inspect.signature(w.on_harvest).parameters`
   (computed once per process beside `_work()`'s cache, `:245-270`); otherwise it calls without it —
   a `TypeError` must never cost the decision write that the same call carries.
3. **The seam test** — `tests/test_work_hook_seam.py` gains the V1 walk through the REAL Stop hook
   subprocess (the file's existing harness, `tests/test_work_hook_seam.py:1-60`): three Stops of one
   session ending on accepted free text leave one open `next` item with the last text; a Stop ending
   `NEXT: <open item id>` claims that item and supersedes the `next` item; an operator-decision Stop
   naming an id claims nothing; a Stop ending `NEXT: <awaiting id> <open id>` claims only the second; a
   Stop naming only an item another live session holds claims nothing; and — the third session's `next`
   item with `next_at` 8 days old planted AFTER the first session's last Stop, immediately before the
   second session's Stop (any harvest closes it, so planting it earlier lets the first session's Stops
   close it) — the second session's Stop closes it (spec § Validation V1, every clause through the real
   hook).
4. The register is untouched: every `tests/test_thread_anchor.py` test stays green as T02b left it,
   except `:1318-1328` (a harvested `NEXT: finish <id> — …` sets that item's `next`), which keeps its
   assertion and adds that the session now holds the item's claim.

DO-NOT: `scripts/work.py` (T05a — a defect there is a BLOCKED report); `.claude/hooks/final_gate_stop.py` (it already runs the harvest with `--repo`; no change needed); the anchor caps, keys or `_is_anchor` itself.

Depends: T05a
Parallel: ⛓️
Complexity: never-route
Gate: .venv/bin/python -m pytest tests/test_thread_anchor.py tests/test_thread_anchor_flush_race.py tests/test_work_hook_seam.py -q
Docs: `docs/reference/thread-anchors.md` is T07b's

## Touches
- scripts/thread_anchor.py — PRIMARY PATH
- tests/test_thread_anchor.py
- tests/test_work_hook_seam.py

## Behavior Contract
- **Given** a session whose last NEXT is accepted free text, **When** the harvest runs with `--repo`, **Then** `on_harvest` receives `next_anchored=True`, and a free text the register rejects receives `False` (spec § The delta D3)
- **Given** a `work.py` whose `on_harvest` has no `next_anchored` parameter, **When** the harvest runs on a message carrying a DECISION block, **Then** the decision item is still written and nothing raises (spec § Lifecycle — Degradation)
- **Given** the real Stop hook and an initialised temp repo, **When** one session stops three times on accepted free text, then on `NEXT: <open item id>`, then on `NEXT: operator decision: … <id>`, then on `NEXT: <awaiting id> <open id>`, then on a NEXT naming only an item another live session holds, and a second session stops once after an 8-day-old `next` item is planted, **Then** the store holds one superseded `next` item, the first named item and only the second id of the mixed line claimed by the first session, no item FILE changed by the operator-decision or other-held Stops, and the 8-day-old item closed by the second session's Stop (spec § Validation V1)
- **Given** the register's anchor state before this ticket, **When** the same harvests run, **Then** the session's anchors are identical to what the pre-ticket code writes (spec § Rejected alternatives — the register stays, D-392)

## Context Files
- .windsurf/rules/core/10-python.md
- scripts/thread_anchor.py
- tests/test_thread_anchor.py
- tests/test_work_hook_seam.py
