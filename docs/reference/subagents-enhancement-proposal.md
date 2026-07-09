# Proposal — `subagents` module enhancements (hand-off to the fabrik-lib AI)

**Status:** proposal · **Date:** 2026-07-10 · **Owner of the module:** fabrik-lib (canonical `/opt/fabrik-lib/subagents`) · **Author:** `/opt/fabrik` (proposes; does NOT write fabrik-lib — cross-repo)

This is a **cross-repo proposal**, not an implementation — `/opt/fabrik` cannot edit `/opt/fabrik-lib`. It lists the
`subagents`-module enhancements that would eliminate the dispatch traps a real session exposed (see the converged
spec `docs/superpowers/specs/2026-07-09-pool-dispatch-map-and-enhancements-design.md`). Each enhancement is
justified by a **verified trap** with the module `path:line` that causes it. Relay to the fabrik-lib AI.

## Why (the traps, verified against the module)

The raw `run_agents` API has silent-failure modes that even a careful caller hits — one did, this session, in a
dogfood that *looked* parallel but ran serial:

| Trap | Wrong result | Cause (`path:line`) |
|---|---|---|
| `tools_enabled=True` + empty/overlapping `owned_paths` | **serial, not parallel** | `workspace.py:321` (`unrestricted = not owned[i] or not owned[j]`); every `tools_enabled=True` worker routed through `disjoint()` at `agent.py:430` |
| `pick_models` default `n=1` | 1 model, not the intended fan-out | `select.py:333` (`def pick_models(task_type, n=1, …)`) |
| `record_run(raw AgentResult)` | **silent no-op** → 0 flywheel rows | `pg_ledger.py:97` (`if not isinstance(record, dict)`) — now warns loudly (already landed) |
| quality judged post-hoc + INSERT-only writer role | rows land `quality_score=NULL` | orchestrator can only score after reading output; no back-fill path |

## The enhancements (ranked by value)

### 1. `fanout()` — a footgun-free dispatch helper (subsumes traps 1, 2, 3)

A single call that makes the common fabrik pattern correct-by-default:

```
fanout(task_type, units, *, n=3, mode="read_only"|"tools", project, quality_fn=None) -> (results, results_table_str)
```

- `pick_models(task_type, n)` internally (fixes the `n=1` default trap).
- Builds **parallel-safe** specs: `mode="read_only"` → each unit's content inlined, `tools_enabled=False`,
  `allow_ungrounded=True` (all parallel); `mode="tools"` → assigns **disjoint `owned_paths`** per unit (fixes the
  serialization trap so the caller can't get it wrong).
- Runs `run_agents`, **auto-records** each via `record_agent_run` (never `record_run`), returns results + the
  rendered `results_table`.

This is the highest-value item: it makes correct-parallel-recording dispatch the path of least resistance — the
adoption problem ("the pool isn't used because the ceremony is error-prone") solved in code, not prose.

### 2. Serialization guard (cheap safety net, independent of #1)

In `arun_agents`, when ≥2 `tools_enabled=True` workers land in one overlap group (would serialize), emit a **loud
stderr warning**: *"N tools-enabled workers with overlapping/empty owned_paths will run SERIALLY — pass disjoint
owned_paths, or tools_enabled=False for a read-only fan-out."* Non-breaking; pure visibility. Prevents the trap
even for callers who don't use `fanout()`.

### 3. Quality-score back-fill (fixes the NULL-quality flywheel gap)

A `set_quality(agent_id, score)` writer (needs an UPDATE/upsert grant on `subagent_runs`) OR a
serialize→reconstruct path, so **judge-once-then-record survives the process boundary**. Today the orchestrator can
only score after reading a worker's output, and the writer role is INSERT-only → rows land `quality_score=NULL`, so
the flywheel learns cost/latency but not the quality signal it exists to rank on.

### 4. `record_run` loud warn — ✅ ALREADY LANDED

Kept for completeness: `record_run(raw AgentResult)` now warns loudly on stderr instead of a silent no-op
(`pg_ledger.py:97`).

## Non-goals

- No new fabrik-lib module — this is an **ENHANCE** of the existing `subagents` module.
- The exact `fanout()` signature/mode names are fabrik-lib's design call; this proposal fixes the **behavior
  contract** (parallel-safe defaults, auto-record, results_table), not the API bikeshed.
- `/opt/fabrik` does not implement any of this — cross-repo. The fabrik-lib AI builds it; the hub re-vendors after.
