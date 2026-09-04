# T05c — the Stop hook follows the locks (the fleet-synced one)

## Scope
Resolve the directory with the SAME four-line snippet in every consumer — there is no shared helper and there cannot be one (`scripts/enforcement/` is synced dependency-free, and `.claude/hooks/final_gate_stop.py` is a standalone synced hook that cannot import it):
```python
LOCK_DIR = Path(os.environ.get("FABRIK_PLAN_LOCK_DIR") or
                Path.home() / ".claude" / "state" / "plan-locks" / <repo-basename>)
```
Census, re-derived 2026-09-04: **55** tracked files match `\.fabrik/plan-locks`, and the broader `git grep -l -e plan-locks -e plan_locks` matches **69** — the slash form is a BOUNDED SEARCH that misses every consumer building the path componentwise, which is where three of the breaking ones live. **This ticket owns the hardest consumer, and the fix is NOT a path swap.** `.claude/hooks/final_gate_stop.py:864` reads `if ".fabrik/plan-locks/" in rel and p.is_file():` inside a loop over `authored` (`:861`), and `authored` comes from `_session_files()` (`:303`), whose docstring states **"Only paths INSIDE root count"** and which drops anything else (`relative_to(root)` inside a `try`, `except … continue`). Once T04b moves the lock to `~/.claude/state/plan-locks/<repo>/`, **no lock path can ever enter `authored`** — re-keying `:864` alone arms nothing, silently, in the hub and in ~46 synced projects. The second author-blind pass caught this in the first draft of this very ticket.

So this ticket owns the ARMING SOURCE. Replace the membership test in `_midrun_marker` with a direct stat of `<LOCK_DIR>/<plan-id>.json`, and preserve the property `:857-860` documents — *"A SESSION-OWNED mid-run signal… Session-scoped deliberately — an unrelated sibling session's active lock must not turn another session's legitimate follow-up offer into a stall."* The session link that `authored` used to provide must be re-derived explicitly: match the lock's `plan` field against a plan-set path this session actually authored (which `authored` still gives you, since the PLAN files remain in-repo), and arm only on that. Write the chosen mechanism into the ticket's commit body — a reviewer must be able to see how session-scoping survived, because losing it converts every sibling's active plan into a stall for everyone.

The template's lock-path sentence (`templates/governance/CLAUDE.md:132`) is T14a's — one ticket owns each governance file's prose. DO-NOT: touch the enforcement checks (T05d/T05e), `check_plan_lock_release.py` (T05a), the command sources (T04b) or any governance template (T14a).

Depends: T04b, T05a
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/test_final_gate_stop_hook.py -q
Gate: test -z "$(git grep -n '\.fabrik/plan-locks' -- .claude/hooks/final_gate_stop.py)"
Docs: docs/workstation/hooks-index.md is T02's; CHANGELOG.md — orchestrator-applied

## Touches
- .claude/hooks/final_gate_stop.py — PRIMARY PATH
- tests/test_final_gate_stop_hook.py

## Behavior Contract
- **Given** a live plan lock in the NEW directory whose `plan` field names a plan set THIS session authored, **When** the Stop hook evaluates whether a run is in flight, **Then** it arms — proving the arming path no longer depends on the lock appearing in `authored`, which by construction it cannot (.claude/hooks/final_gate_stop.py:303)
- **Given** a live lock in the new directory belonging to a DIFFERENT session's plan, **When** the hook runs, **Then** it does NOT arm — the session-scoping property at `:857-860` survives the redesign (.claude/hooks/final_gate_stop.py:857)
- **Given** a lock at the OLD `.fabrik/plan-locks/` path only, **When** the hook runs, **Then** it does NOT arm — proving the move is complete rather than dual-homed (.claude/hooks/final_gate_stop.py:864)
- **Given** no lock anywhere, **When** the hook runs, **Then** its behaviour is unchanged from today (.claude/hooks/final_gate_stop.py:864)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
