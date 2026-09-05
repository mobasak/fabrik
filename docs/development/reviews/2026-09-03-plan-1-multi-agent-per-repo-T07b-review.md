# Acceptance review — T07b (plan set 2026-09-03-plan-1-multi-agent-per-repo)

**Status:** IN-PROGRESS

**Surface:** the coder's worktree branch diff against the dispatch base a6518d1e (master after the joint T06/T07a merge) — see the round sections below (one file per ticket, rounds APPENDED).

## Round 1 — over `a6518d1e..8b8d8661` (.claude/hooks/skill_router.py 61/2 — `vision`/`epics`/`epics-review` in both `STEM_SKILLS` and `KEYWORD_STEMS` at indices 4–6 above `spec` 9 / `plan` 12, the review twin first, TR forms; tests/test_skill_router_hook.py 217/27 — 75 new tests incl. a 55-row routing snapshot re-derived against the base router and neighbour-theft tests; the rest of both files `ruff format` of pre-existing dirt; 244 passed (169 at base); the false-positive surface measured over 9,849 real operator prompts — a bare-noun cut changed 96 and was rejected, the shipped cut changes 2 (both the new stems on their advertised phrases); the real hook binary end-to-end on six prompts incl. two Turkish)
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native opus×1 — round 1.
Pool + native: PENDING — appended when they return.
