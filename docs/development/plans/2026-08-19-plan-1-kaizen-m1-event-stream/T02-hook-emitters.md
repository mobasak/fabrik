# T02 — hook emitters: session lifecycle + stop_block/final_block + operator_override

Depends: T01
Parallel: ⚡ (with T03, T04)
Complexity: native (FLEET-SYNCED surfaces — .claude/hooks distributes to ~46 repos; highest blast
radius in the plan; must be fail-open and correct for every project)
## Scope
Wire the session-lifecycle emitters into the PROJECT-synced hooks (fabrik_synced_manifest.py AGENT_HOOK_FILES rows, scripts/fabrik_synced_manifest.py:113-121); the Stop hook's block/override decision points live in .claude/hooks/final_gate_stop.py (its cause taxonomy is the event's cause field).

## Touches
- .claude/hooks/session_orient.py
- .claude/hooks/final_gate_stop.py
- .claude/settings.json
- tests/test_kaizen_hook_emitters.py

## Context Files
- docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md
- scripts/fabrik_synced_manifest.py
- .claude/settings.json
- docs/workstation/hooks-index.md
- scripts/sysadmin/kaizen_events.py



## Interfaces

Consumes: T01 `emit()`/`resolve_sid()`. The hooks import `kaizen_events` via an ADDITIVE,
IDEMPOTENT sys.path append (`if p not in sys.path`) of `<project>/scripts/sysadmin` then
`/opt/fabrik/scripts/sysadmin`, wrapped `try: import kaizen_events / except Exception:
kaizen_events = None`, and every emit site guards `if kaizen_events:` — in a project without
the module (sync lag) the hook behaves exactly as today (fail-open at the import layer, proven
by the byte-compare test).
Produces: `session_start` (from session_orient.py — carries cwd/project + exposure),
`session_end` (from final_gate_stop.py's Stop pass-through when it does NOT block),
`stop_block` (cause field: gate-red / uncommitted / unpushed / promise-stall / run-record —
final_gate_stop.py knows its own cause), `final_block_emitted` (the Stop hook already detects the
6-line block to enforce the terminator contract — emit when seen), `operator_override` (the
sanctioned-skip marker the hook already recognizes).

## Steps

1. **The payload sid is GROUNDED (plan-review, 2026-08-19):** the hook stdin JSON carries
   `session_id` — documented at .claude/hooks/final_gate_stop.py:21 and already READ at
   .claude/hooks/session_orient.py:99. Wire `resolve_sid(data.get("session_id"))` from the hook's EXISTING defensive payload parse
   (final_gate_stop.py:756-757 already does `json.loads(raw) if raw.strip() else {}` — emitters
   NEVER add a second stdin read); absent → `unknown`, never a guess. (The live probe step is
   retired — the fact is cited, not assumed.)
2. TDD: `tests/test_kaizen_hook_emitters.py` drives each hook as a subprocess with a fixture
   stdin payload + `KAIZEN_EVENTS_DIR=tmp` and asserts the seam contract (a parseable line with
   schema/ts/sid/event + exposure) per event type — plus the fail-open case: module absent →
   hook exit code and stdout UNCHANGED from today (byte-compare against a no-module control run).
   RUN RED first.
3. Implement the emissions at the hooks' existing decision points (block → `stop_block` with
   cause; clean pass → `session_end`; the override marker branch → `operator_override`).
   ZERO new hook entries in settings.json unless a needed event has no existing hook — prefer
   the seams already wired.
4. Fleet-safety review of the diff: every new line inside `try/except: pass` at the outermost
   emitter boundary; no import-time cost when the module is absent.
5. Gate: hook tests green; a LIVE smoke in this session's next turn shows `session_start` +
   `stop_block`/`session_end` lines in `~/.claude/state/events/<this-sid>.jsonl`.

## Behavior Contract

- **Given** a `SessionStart` and a Stop-hook block in a live session, **When** the hooks fire,
  **Then** `session_start` and `stop_block` (with its cause) events exist in that session's file,
  and a sanctioned-skip marker in the operator's reply emits `operator_override`
  (.claude/hooks/final_gate_stop.py).

Docs: none beyond the schema doc (T01 owns it); hook behavior notes ride T09's kaizen.md pass.
Gate: `uv run pytest tests/test_kaizen_hook_emitters.py -q` + the live smoke.
