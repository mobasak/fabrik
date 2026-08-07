# T05 — UserPromptSubmit skill-router hook

Depends: —
Parallel: ⚡
Complexity: never-route
Docs: CHANGELOG entry via Deltas
Gate: python -m pytest tests/test_skill_router_hook.py -q && python scripts/final_gate.py --lean --check --json

## Scope

Build `.claude/hooks/skill_router.py`, wire it as a `UserPromptSubmit` hook in
`.claude/settings.json`, add it to `scripts/fabrik_synced_manifest.py` beside the DoD hook, and
test it in `tests/test_skill_router_hook.py`. DO-NOT: block or rewrite the prompt (inject-only);
DO-NOT add any per-prompt cost beyond the bounded Haiku fallback; DO-NOT touch final_gate_stop.py.

Contract (all settled with the operator): reads stdin JSON (`prompt`, `cwd`, `session_id` — same
contract family as final_gate_stop.py). **Exemptions first, silent on all:** prompt already starts
with `/`; cwd is not a fabrik-style project (no `scripts/final_gate.py`); any internal error
(fail-open like the DoD hook). **Tier 1 regex:** a bilingual (EN+TR) keyword→skill map over the
DYNAMIC roster (`~/.claude/skills/fabrik-*` — future commands auto-enroll; map covers the stable
stem semantics: spec/design/fikir, plan, review/incele, docs/döküman, test/certify, release/yayın,
deploy-verify, catchup/güncel, retire/kaldır, upstream). `design-review` is DELIBERATELY outside
the roster (pipeline-invoked GUI sub-gate — spine § Interfaces). **Tier 2 Haiku (regex miss only):**
`claude -p --model haiku` one-liner classifier over the roster names + Stage lines, hard ≤8s
timeout, empty-on-any-error. **On match:** emit the documented NESTED injection shape —
`{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "…"}}`
(verified against the live hooks doc 2026-08-07; the INPUT field carrying the submitted prompt
text was NOT visible in the fetched excerpt — verify it live in-ticket before coding, do not
assume `prompt`) — with the directive-with-escape: `This request matches /fabrik-X (Stage: N) — invoke the skill, or state in
one line why it does not apply.` **On no match:** silence. (The UserPromptSubmit injection-field contract MUST be verified live in-ticket against
https://code.claude.com/docs/en/hooks — external URL, not a repo read.) Tests mirror the DoD-hook suite: pure
map/decide functions unit-tested; the Haiku tier via stubbed subprocess; exemptions; fail-open;
never-blocks; a real-shape stdin replay.

## Touches

- .claude/hooks/skill_router.py
- .claude/settings.json
- tests/test_skill_router_hook.py
- scripts/fabrik_synced_manifest.py

## Behavior Contract

- **Given** a user prompt matching a pipeline stage, **When** the router hook fires, **Then** it injects a directive-with-escape ("matches /fabrik-X — invoke it or state why not") naming the matched stage (.claude/hooks/skill_router.py:1).
- **Given** a prompt matching nothing, an explicit /command, or any internal error, **When** the hook fires, **Then** it stays SILENT — fail-open, no injection, never blocks (.claude/hooks/skill_router.py:1).
- **Given** a Turkish or paraphrased English prompt, **When** the regex tier misses, **Then** the Haiku tier classifies it (claude -p, hard timeout, empty-on-error) (.claude/hooks/skill_router.py:1).

## Context Files

- .claude/hooks/final_gate_stop.py (the idioms: stdin contract, fail-open, tmp state, test style)
- .claude/settings.json (hook wiring shape)
- scripts/fabrik_synced_manifest.py (:87-98 — the AGENT_HOOK_FILES sync block to extend)
- tests/test_final_gate_stop_hook.py (the test-suite pattern to mirror)
