# Acceptance review — T05a (plan set 2026-09-03-plan-1-multi-agent-per-repo)

**Status:** IN-PROGRESS

**Surface:** the coder's worktree branch (worktree-agent-aa202dd80ecd23540, head 6a065def) against its merge base 2f982a5f — `scripts/enforcement/check_plan_tickets.py` +269/−1 (FLEET-SYNCED), `tests/enforcement/test_plan_tickets_epic_scope.py` +287 (new, 8 tests). Coder: native Opus worktree (Execution Discipline). Gates: 8 passed; 321 across the five plan-ticket suites; ruff + format clean; mypy 0 new. Red-first: 5 of 8 red on the first run, the 3 vacuously-green rows proven by on-disk mutation (`_glob_covers` → `_covered_by`; an always-printed line mutated). Byte-identical proof on the live 33-ticket set (md5 `249e63c3…` both sides). Grounding measured: 10 live epics parsed (9 with `owned_paths`; the schema-less 2026-07-14 epic fails closed); 15-shape predicate table 15/15; `EPIC_HEADER_RE` fires on 1 archived plan fleet-wide. Coder's declared residual: a second `Epic:` line silently uses the first (0 spines carry two today).

## Round 1
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native opus×1 — round 1.
### Adjudication (pool layer)
- gemini — CLEAN (separator-awareness; the two-depth subtree probe distinguishes `src/**` from `src/*`; the parser's parity with T03a's incl. comment stripping and list-key restriction; fail-closed paths; the byte-identical baseline; `_carved_out`).
- qwen — CLEAN (7/7 classes; `src/**/x.py` matches `src/x.py` — `**` matches zero segments; `**` alone → `.*\Z`; trailing `/` stripped then probed; the parser compared line-by-line with T03a's branch; six fail-closed conditions; a second `Epic:` line acceptable at ≤1 fleet-wide).
- deepseek — 2+ raised (18,790 chars): "`(?:[^/]+/)*` requires at least one segment, so `src/**/config/**` rejects `src/config/settings.py`" — REFUTED by execution against the branch's own `_glob_covers` (a `*`-quantified group matches zero repetitions; probe output recorded below); "`**` alone compiles to `\Z`" — REFUTED (`**` alone → covers `src/a/x.py`: True). Its remaining items restate the passing rows.
Orchestrator probe on the branch's `_glob_covers` (executed in its worktree):
```
'src/**/config/**'                       covers 'src/config/settings.py'                  -> True
'src/**/config/**'                       covers 'src/a/b/config/x.py'                     -> True
'**'                                     covers 'src/a/x.py'                              -> True
'src/a/*'                                covers 'src/a/b/deep.py'                         -> False
'src/a/**'                               covers 'src/a/x.py'                              -> True
'libs/**/product_entitlements_bridge/**' covers 'libs/x/product_entitlements_bridge/y.py' -> True
'docs/**'                                covers 'docs/x/'                                 -> True
'docs/*'                                 covers 'docs/x/'                                 -> False
```
Native finder (opus): PENDING — appended when it returns.
