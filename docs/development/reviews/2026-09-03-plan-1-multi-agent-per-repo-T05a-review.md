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
### Native finder (opus) — executed: 32 adversarial glob shapes correct (mid-`**` zero depth, `*` not crossing a separator where fnmatch would, `?`, `(admin)`/`(deploy)`/`[`/`\` literal, trailing `/`, bare `**`/`*`, glob-free → `_covered_by`); both links fire; 12 fail-closed shapes; base vs branch byte-identical over 68 plan dirs without `Epic:`; a `["**"]` epic against 43 live tickets → 0 findings; `_carved_out` condition-for-condition equal to the File-Scope skip set; stdlib-only, ruff/format clean, mypy = master's 3, 146 passed. 7 raised:
- [M] `_glob_regex`/`_glob_covers` have ZERO unit tests — 6 of 9 semantic mutants survive the 8 CLI tests (mid-`**` ≥1 segment; `?` crossing `/`; literals unescaped → `app/(admin)/**` becomes a group, a live web-ecommerce-factory shape; the 2nd subtree probe dropped; `_carved_out` ≡ False; trailing `**` → one level), two Behavior Contract rows guarded by pure-negative asserts (:199/:211) → FIXUP (1).
- [M] the copied `_parse_frontmatter` (:845-891) diverges from T03a's FINAL parser on 5 of 17 fixtures — a block with a blank line is silently TRUNCATED (the gate then emits a believable false accusation; the docstring's fail-CLOSED claim is wrong for it), a comment line empties the block, unindented block, `k: #x`, a `#` inside a quoted item; 0 of 10 live epics hit a divergent shape today → FIXUP (2): port the classifier + collector verbatim, hub-only parity test over the 17 fixtures.
- [L] the `EPIC_HEADER_RE` comment claims fence-stripping prevents a quoted example keying containment — false for `~~~`, 4-space indented code and prose (`Epic: this plan…` → `'this'`), each failing CLOSED; fire rate verified with its denominator: 1 of 1,003 files fleet-wide, an archived standalone the checker never enters → FIXUP (3, comment). [L] the "no repo root is resolvable" arm (:931-937) is unreachable → FIXUP (4). [L] `(?:[^/]+/)*` per mid-`**` backtracks ~4× per `**` (11 → 6.8 s on a non-match; a project-authored input; no timeout) → FIXUP (5). [L] `_glob_covers("src/a/**","src/a")` → True is the one permissive path (dir vs file undecidable without disk) — docstring must state the resolution → FIXUP (6). [L] no INDEX row for the new test → orchestrator Delta at merge (`delta_T05a_index.py`), not a coder item.
Round 1 verdict: 7 raised → 6 routed (2 M, 4 L) + 1 orchestrator Delta; pool layer's items subsumed. Not the no-op round.
