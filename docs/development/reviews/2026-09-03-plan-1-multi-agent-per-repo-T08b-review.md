# Acceptance review — T08b (plan set 2026-09-03-plan-1-multi-agent-per-repo)

**Status:** IN-PROGRESS

**Surface:** the coder's worktree branch diff against the dispatch base 0d5a4685 (master after the T08a merge) — see the round sections below (one file per ticket, rounds APPENDED).

## Round 1 — over `0d5a4685..f65e3f3b` (tests/test_check_command_corpus.py 54/237 — the `traycer_skills=` kwarg stripped at 26 sites incl. the one inside a generated `driver.py` string literal; 8 tests deleted (7 wrapper tests + the orch-scoped `templates/**` fallback matrix, whose hub-side assertion is covered by `test_template_shipped_scripts_resolve` — proven by a mutant check that resolves template-only refs → that test reds; the comment-blanker test's two `sources` graders named and still green); the `_orch_fixture` helper removed; the audited-denominator expectation now corpus + agent definitions with its comment rewritten; the three canary strings measured in each test's own tree shape (17→15, 10→8, 11→9 — each exactly the two wrapper canaries); `test_project_with_orch_dir_but_no_corpus…` renamed with both real assertions kept; two subprocess fixtures' wrapper-tree mkdirs dropped; NEW `test_a_former_orchestrator_command_is_audited_like_any_other_source` parametrized over the three mega sources (red on a mirror whose check skips those names); watched-fail: 69 failed / 55 passed → 3 failed (the counts) → 119 passed / 119 collected; selftest exit 0; grep 0; ruff/format clean (base already formatted); one file)
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native: the orchestrator's own execution (a test-only ticket whose shape T08a's native finder measured in advance; stated) — round 1.
### Orchestrator execution (in the worktree)
- `pytest tests/test_check_command_corpus.py -q` → 119 passed; `--collect-only` → 119 collected; `--selftest` → 15 canaries over 8 predicates, exit 0; the grep → 0; `ruff check` clean, `ruff format --check` 1 file already formatted; the new parametrized test present (1 definition).
Pool: PENDING — appended when it returns.
