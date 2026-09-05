# Acceptance review — T08a (plan set 2026-09-03-plan-1-multi-agent-per-repo)

**Status:** IN-PROGRESS

**Surface:** the coder's worktree branch diff against the dispatch base b1f7e675 — see the round sections below (one file per ticket, rounds APPENDED).

## Round 1 — over `b1f7e675..a994e02d` (scripts/enforcement/check_command_corpus.py 9/164 — `TRAYCER_SKILLS`, `_ORCH_DOC_RE`, `_orch_corpus()`, its `audit()` call site with the "wrapper tree missing in the hub" problem, the `traycer_skills` parameter and its 5 selftest callers, the selftest's wrapper fixture + two VACUOUS assertions deleted, all anchored by symbol (the ticket's line numbers had drifted: `:1001`, `:1123`, `:1616`); plus one consumer the ticket did not name, found by the first gate run: `orch_doc_set` and the orchestrator-only `templates/**/<script>` fallback in script-path resolution (mirror stated: command sources never received it); three history-only comments left; the denominator comment corrected; watched-fail: the importlib gate exit 1 and grep 20 BEFORE the edit; the check green over 63 files with `_traycer-skills/` parked out of the tree — the three new sources audited by the per-source predicates with no special case; `--selftest` 15 canaries over 8 predicates (was 17: exactly the two wrapper canaries); T08b's untouched test file 69 failed / 55 passed — 65 `traycer_skills` kwarg TypeErrors, 1 `_orch_corpus` AttributeError, 3 hard-coded canary counts each off by 2; the tests asserting the removed semantics named for T08b)
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native opus×1 (an enforcement gate) — round 1.
### Orchestrator execution (in the worktree)
- the check → `✓ … all sound across 63 file(s) read`; the importlib gate exit 0; `--selftest` → 15 canaries over 8 predicates; grep 0; `ruff check` clean; `pytest tests/test_check_command_corpus.py` → 69 failed, 55 passed (T08b's expected reds).
### Pool layer (3 units returned — deepseek/deepseek-v4-flash, deepseek/deepseek-v3.2-exp, deepseek/deepseek-v4-flash; $0.0133)
- All three CLEAN: every deleted symbol gone, no remaining `docs/orchestrator` reference but the three history comments, the `templates/` fallback reachable only via `path in orch_doc_set` (dead once no orch doc is in `files`), the audited denominator 63 before/after, the three new sources under the per-source predicates, no fail-open for command sources, one file touched.
Native: PENDING — appended when it returns.
