# T05 — the Stop hook passes `--repo` to both harvests; the V1 seam test

## Scope

Implements the hook half of spec § NEXT, DECISION blocks and the register, item 1 ("The Stop hook passes
`--repo <root>` to the harvest"). In `.claude/hooks/final_gate_stop.py`:

- the plain harvest (`.claude/hooks/final_gate_stop.py:2809`, argv `[sys.executable, str(_ta), "harvest",
  "--session", sid]`) and the decision harvest in `_store_decision` (:2644, the same argv plus
  `--decision-ok`) both append `--repo <root>`, where `root` is the hook's resolved payload cwd (:2758).
  The plain harvest runs on EVERY Stop, blocked ones included, so it is the claim heartbeat.
- mirror the "only a script that KNOWS the flag gets it" guard at :2641: pass `--repo` only when the
  resolved `thread_anchor.py` source contains `"--repo"` (a fleet repo whose sync is behind keeps
  working; `parse_known_args` would ignore it anyway, the guard keeps the argv honest).
- nothing else in the hook changes: `parse_decision_block` (:2332) keeps judging, `_store_decision`
  keeps running only at the allowed exits (:2821, :2863, :3088), and the 5 s subprocess timeout stays.

The seam test is the spec's V1 replay, end to end, with no stubs: a temp git repo initialised with
`work.py init`, no `scripts/final_gate.py` in it (so the hook takes its non-fabrik allowed exit and
`_store_decision` runs), the REAL hook run as a subprocess with a Stop payload whose
`last_assistant_message` ends on a DECISION block; then the REAL `thread_anchor.py line --hook` with
UserPromptSubmit and SessionStart `source=compact` payloads from a different session id.

DO-NOT: `scripts/thread_anchor.py` or `scripts/work.py` (T04, T01b); any other Stop-hook behaviour.

Depends: T04
Parallel: ⛓️
Complexity: never-route
Gate: .venv/bin/python -m pytest tests/test_work_hook_seam.py tests/test_final_gate_stop_hook.py -q
Docs: docs/workstation/hooks-index.md is T09's

## Touches
- .claude/hooks/final_gate_stop.py — PRIMARY PATH
- tests/test_work_hook_seam.py (new)

## Behavior Contract
- **Given** an initialised temp repo, **When** the real Stop hook runs on a final message ending in a valid DECISION block, **Then** the repo's store holds one `awaiting-operator` item for it (spec § Validation V1)
- **Given** that item, **When** a second Stop from another session ends on a different valid DECISION block, **Then** the store holds two awaiting items (spec § Validation V1)
- **Given** the two items, **When** a third session's `thread_anchor.py line --hook` runs on UserPromptSubmit and then on SessionStart `source=compact`, **Then** both questions print, unfolded, in both outputs, and they still print after that session's own state file is deleted (spec § Validation V1)
- **Given** a claim held by a session, **When** the Stop hook runs for that session on a message with no DECISION block, **Then** the claim's lease is renewed (spec § Identity, the lock, the lease)
- **Given** a repo whose `scripts/thread_anchor.py` does not know `--repo`, **When** the Stop hook runs, **Then** the harvest argv carries no `--repo` and the Stop is allowed as before (spec § Lifecycle — Degradation)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- tests/test_thread_anchor.py — `_env`, `run3`, `_hook_line`, `_git` (tests/test_thread_anchor.py:215, :233, :247, :263)
- docs/development/plans/2026-09-24-plan-2-work-tracking/T04-thread-anchor-items.md — the producer's `--repo` contract and Behavior Contract
