# T03 — the Stop hook: DEFERRAL D1–D4, the DECISION parser, the reasons, the input, the event

## Scope
Implements spec § C1 (the DEFERRAL shape, its scope, inputs and reasons) and § C2 (the DECISION block's parse and checks) in `.claude/hooks/final_gate_stop.py`, plus the `decision_block` event registration (spec § Contract deltas). Folds in the review's recorded inputs: A-O40 (D4 fires only when the agent hands ITS OWN remaining work to a later session — the five factual sentences are green fixtures) and A-O43 (an `asked:` or `scope:` quote must occur verbatim in an operator entry that is neither a tool result, a compaction summary, a hook-injected block nor a slash-command expansion, and an `asked:` quote ends in `?`). DO-NOT: change the five existing pattern shapes' behaviour or exemptions except `_PERMISSION_RE`'s loop, which D3 replaces (spec § C1 "The one behaviour that moves"); change `CAP`, `decide_stall` or any other cause; touch `scripts/thread_anchor.py` (T04).

Depends: T01, T02b
Parallel: ⛓️
Complexity: native
Gate: uv run pytest tests/test_final_gate_stop_deferral.py tests/test_stop_hook_deferral_exemption.py tests/test_final_gate_stop_hook.py tests/test_kaizen_events.py -q
Docs: CHANGELOG (Deltas) — the three docs rows are T05's

## Touches
- .claude/hooks/final_gate_stop.py — PRIMARY PATH
- scripts/sysadmin/kaizen_events.py
- tests/test_final_gate_stop_deferral.py
- tests/test_stop_hook_deferral_exemption.py

## Behavior Contract
- **Given** an interactive turn ending on a D1–D4 deferral with no DECISION block, **When** the Stop hook runs, **Then** it blocks with `cause=deferral` and the one-paragraph reason, and warns through after three blocks (spec § C1)
- **Given** a turn ending on a well-formed DECISION block, **When** the Stop hook runs, **Then** it allows the stop, emits a `decision_block` event with its ground, and refuses `owned`+`scope:` inside a live run and an `asked:`/`scope:` quote not found in an operator entry (spec § C2; A-O43)
- **Given** factual prose about a new session and the judged false matches, **When** D4 runs, **Then** it does not fire, while it fires on at least 6 of the 8 judged real excuses (spec § C1 D4; A-O40)

## Steps (the coder's order)
1. Red first, `tests/test_final_gate_stop_deferral.py` (new): red fixtures per shape drawn from the committed verdicts (`docs/reference/research/2026-09-23-stop-compaction/verdict-opdec.json` quotes of the say-the-word and menu shapes; `verdict-context.json` STOP-EXCUSE quotes), each driven through `_detect_stall` on a synthetic transcript; a well-formed block per ground; a malformed block per rule (missing field, unknown ground, `gate` without a listed class, `owned`+`scope:` with a `running` record under a scratch `COMMAND_RUN_DIR`, an `asked:` quote absent from the transcript's operator entries, an `asked:` quote found only inside a `<command-name>` expansion); the headless case (`CLAUDE_MESH_HEADLESS=1`, and a last user entry with `"entrypoint": "sdk-cli"`); the `last_assistant_message` input taking precedence over the transcript. Watch every red fixture FAIL on the unmodified hook.
2. Green fixtures (proven by mutation, spec § V2: widen the shape on a throwaway copy and watch each fail): the conversational footer `NEXT: awaiting your reply`; `NEXT: none — terminal`; a findings list; a quoted operator question; the nine judged FALSE-MATCH quotes; the seven ordinary sentences in `docs/reference/research/2026-09-23-stop-compaction/d4_probe.py`; and A-O40's five — "The fix takes effect in a new session; nothing to do.", "Hooks load when you start a new session.", "Verified in a fresh session: the hook fires.", "The new session will inherit the synced hooks.", "A new session runs SessionStart first."
3. Implement in `.claude/hooks/final_gate_stop.py`: `_DEFER_RE` (spec § C1 D1's closed vocabulary) and `deferral_shape(text) -> str | None` returning `D1`…`D4`; D4 requires a hand-off frame whose subject is the agent's own remaining work (`I|we|this|the rest|the remaining|the converge|it` … `(in|to|for) a (fresh|new|clean) (session|window|context)`, or `a/the (fresh|new) session (finishes|must|should)`), never a bare mention; `_DECISION_GATE_RE` (spec § C2's closed class list); `parse_decision_block(text, *, run_live, transcript_path) -> tuple[bool, str]` reading only the LAST heading outside a fenced block with its four lines; the DEFERRAL check inside `_detect_stall` (`:1631`) after the existing shapes, sharing the stall counter, never taking the dispatch-kept exemption; D3 replacing the `_PERMISSION_RE` loop (`:1744-1751`).
4. Inputs: read `last_assistant_message` from the Stop payload in `main` (`:1814`) when present, falling back to `_final_turn`; log the key's presence as a kaizen field on every Stop (spec U1); correct the header claim at `:17`.
5. Reasons: the DEFERRAL reason (spec § C1, one paragraph); rewrite the existing stall reason at `:2137-2139` to name only the two exits, a `ground: gate` DECISION block or `BLOCKED:` (C-O7, C-O10).
6. Harvest: the call at `:1836-1847` passes `--decision-ok` to `thread_anchor.py harvest` only when `parse_decision_block` returned `(True, …)` (the T03 → T04 interface).
7. Events: `stop_block` gains `cause=deferral` and `shape`; a `decision_block` event carries `ground`; register `decision_block` in `scripts/sysadmin/kaizen_events.py:114` (`EVENT_TYPES`) so `emit()` does not warn.
8. Adapt `tests/test_stop_hook_deferral_exemption.py`: its three graders pin today's per-line exemption for the pattern shapes, which stays; add one asserting that the same exemption no longer clears a DEFERRAL.
9. Gate green; `uv run ruff check` on the touched files; CHANGELOG line into the Deltas block.
10. `/fabrik-review` on this ticket's changed surface, partitioned by file (Opus on the hook), to a coverage-adjudicated exit; every finding FIXED or REFUTED.
11. Commit with explicit pathspecs + provenance trailers (`Agent-Role: subagent`, `Agent-Task: T03`).

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- .claude/hooks/final_gate_stop.py
- scripts/sysadmin/kaizen_events.py
- tests/test_stop_hook_deferral_exemption.py
- docs/superpowers/specs/2026-09-23-stop-and-compaction-enforcement-design.md
- docs/reference/research/2026-09-23-stop-compaction/verdict-opdec.json
- docs/reference/research/2026-09-23-stop-compaction/verdict-context.json
