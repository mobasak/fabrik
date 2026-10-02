# T04 — The Stop hook holds a merge owner with a waiting request

## Scope
Implements spec § The delta 6 (duties D-B, D-C). `.claude/hooks/final_gate_stop.py` gains one cause, evaluated ONLY in a repo's main checkout by a session that resolves to the repo's merge owner: the turn is blocked while an unclaimed `merge-request` addressed to it waits in the repo inbox, or a `fabrik-merge/<id>.json` record is short of `replied` and STRANDED by T03's rule — its recorded pid dead, or alive with a `/proc/<pid>/stat` start time different from the recorded one (spec § The delta 5; W-8a6a5644 O36); the block text carries the `merge_request.py merge` (or `resume <id>`) command; CAP 3 and warn-through like every other cause (`.claude/hooks/final_gate_stop.py:45` `CAP = 3`, `:1409` `decide_review` as the pattern); silent in an UNDECLARED repo, in a linked worktree, and for any other agent. The hook imports no script (its own design) and copies no resolver: only when a `merge-request` file or a `fabrik-merge/` record exists does it run, each under a timeout, the OWNER resolver `python3 /opt/fabrik/scripts/decisions.py --merge-owner <repo root>` (the hub's absolute path, as the template calls it at `templates/governance/CLAUDE.md:129`; the owner is whatever it prints — which row it selects is W-076ff4a9's, never this ticket's) and the CALLER resolver `python3 scripts/whoami_agent.py --who` with `CLAUDE_CODE_SESSION_ID` set to the stdin `session_id` (`resolve_agent_name`, `scripts/whoami_agent.py:259-270`: `CLAUDE_AGENT`, else the last identity row for that session with a valid name). A missing script, a timeout, exit 3 (UNDECLARED) or an empty caller makes the cause silent — fail-open, as every other cause's own error path. The inbox is `$FABRIK_MAIL_ROOT` (default `/opt/fabrik-mail`, `scripts/mail.py:299`) `/<repo>/inbox`, read by each file's `kind:` and `agent:` header lines. The new cause needs its OWN attempts slot: `_COUNTER_SLOTS` (`.claude/hooks/final_gate_stop.py:467`) goes 6 → 7, `_read_counters` (`:470`) returns a 7-tuple, both unpack sites take seven names, and all seven `counter.write_text` sites (`:3047`, `:3107`, `:3163`, `:3212`, `:3218`, `:3375`, `:3386`) write seven fields, carrying the new slot through every other cause's write — the hook's own comment records a slot-count mismatch that crashed every Stop and failed the gate open box-wide; a 6-field counter file from before the change reads with the new slot 0 (the pad at `:480`).

Depends: T03
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/test_stop_hook_merge_requests.py $(command grep -rl final_gate_stop tests --include="*.py") -q
Docs: none (the hooks-index row is T06's)

## Touches
- .claude/hooks/final_gate_stop.py — PRIMARY PATH
- tests/test_stop_hook_merge_requests.py

## Behavior Contract
- **Given** the merge owner's session in the main checkout and an unclaimed merge-request addressed to it, **When** the Stop hook runs, **Then** it blocks with the `merge_request.py merge` command, and after CAP attempts warns through (spec § Validation V8)
- **Given** a record short of `replied` whose recorded pid is dead, or alive with a different start time (a reused pid), **When** the Stop hook runs for the owner, **Then** it blocks with `merge_request.py resume <id>`; whose pid and start time are a live process's, **Then** it does not (spec § The delta 5, 6; W-8a6a5644 O36)
- **Given** the same inbox, **When** the Stop hook runs in a linked worktree, for a non-owner agent, or in an UNDECLARED repo, **Then** this cause is silent (spec § The delta 6, 8)
- **Given** a fixture ledger with ONE D-row `MERGE OWNER: beta` and a session bound to `beta` only through the identity file (no `CLAUDE_AGENT`), **When** the hook runs with a request addressed to `beta`, **Then** it blocks; for a session bound to `alpha`, **Then** it is silent; with the resolver's `subprocess.run` raising `FileNotFoundError` (the seam `tests/test_stop_hook_push_attribution.py:182` already uses), **Then** it is silent (spec § The delta 6, 8)
- **Given** a 6-field counter file written before this change, **When** the hook runs, **Then** it reads without error, every existing cause keeps its count, and the new cause reaches CAP after 3 blocks and warns through while an unrelated cause's block does not reset it (spec § The delta 6)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-09-30-merge-request-loop-design.md
- .claude/hooks/final_gate_stop.py
- scripts/whoami_agent.py
