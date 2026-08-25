# Review — T04 (one shared path→pack matcher) · phase-1 of 2026-08-25-plan-1-inert-rule-packs

Status: IN-PROGRESS

Surface: `scripts/rules_match.py` (new) · `scripts/select_rules.py` · `scripts/review_rubric.py` ·
`tests/test_rules_match.py`. Commits: `b589a1b8` (build) · `3f7b8bd2` (fleet hotfix) ·
`fec39417` (equivalence claim) · `d388c9ef` (wildcard-normalization claim).

## Pass Ledger

| Pass | finders | found | fixed | refuted | notes |
|---:|---|---:|---:|---:|---|
| 1 | pool 4 (deepseek-v3.2-exp, gemini-3-flash, qwen3-max, deepseek-v4-flash) | 4 | 0 | 3 | one carried to pass 2 |
| 2 | native Opus authoritative | 17 | 3 | 2 | **caught a LIVE fleet breakage all 4 pool finders missed** |
| 3 | pool 3 (confirming) | 1 | 1 | 3 | `/**` normalization claim — raised INDEPENDENTLY by two finders |
| 4 | confirming round — OWED, not yet run | — | — | — | exit NOT claimed; `found: 0, fixed: 0` not reached |

`Finders: pool deepseek-v3.2-exp×1 + gemini-3-flash×1 + qwen3-max×1 + deepseek-v4-flash×1 — round 1`
`Finders: native opus×1 — round 2`
`Finders: pool deepseek-v3.2-exp×1 + gemini-3-flash×1 + qwen3-max×1 — round 3`

⚠️ **Exit NOT claimed.** Round 3 made a fix, so round 4 is owed.

## The finding that mattered

**A LIVE FLEET BREAKAGE, shipped before it was caught.** `select_rules.py` and `review_rubric.py`
now `import rules_match` at MODULE SCOPE. Both are in `CORE_SCRIPTS` and both are governance-sync
trigger surfaces; `rules_match.py` was in neither. The T04 commit fired the sync, shipped the
rewired pair to every project, and left the dependency behind.

Measured: 49 projects carry `select_rules.py`; **48 were missing `rules_match.py`**, and
`/opt/transdoc`'s copy died with `ModuleNotFoundError: No module named 'rules_match'` — the tool
`CLAUDE.md` § Orient step 4 makes MANDATORY before planning.

Fixed in `3f7b8bd2`; verified 47 synced, 0 missing, transdoc runs again.

**Why every local check passed it:** purity byte-identical, all three call sites rewired, `_GLOBS`
intact, scope-clean diff, 11 tests green — all of it hub-local, while the defect existed only
OUTSIDE the hub. **A synced script's IMPORTS are part of the synced surface**, and nothing in the
gate cross-checks that today.

## Three false claims — the recurring shape of this ticket

Every material defect here was a docstring asserting a property nobody had executed.

1. **`packs_for_paths` "returns the same pack set `review_rubric.py --changed` returns"** — false.
   The rubric emits `FLOOR_PACKS` into its FLOOR section then SKIPS them in MATCHED. Proven:
   `--changed db/schema.sql` → `MATCHED — none` vs `packs_for_paths` → `['core/25-data-postgres.md']`.
   Asserted in FOUR places (module docstring, `--changed` help, spine BC row, ticket BC row); all
   corrected to `MATCHED ∪ (FLOOR packs whose glob fired)` in `fec39417`.
2. **The equivalence TEST passed only because its hard-coded paths dodged the divergent case.**
   Adding `db/schema.sql` + `Dockerfile` makes the old assertion fail. Red-on-revert proven.
3. **`_strip_wildcards` "returns None for a wildcard-only glob, e.g. `**/` or `/**`"** — false for
   `/**`, which becomes `'**'` and bypasses `empty_matches_all` entirely. **Proven NOT a regression**
   against `b589a1b8~1`: the pre-extraction function returned False/True/True for `**/`/`/**`/`**`,
   byte-identical. Fixed the CLAIM, not the behavior — normalizing it would move packs between
   ACTIVE and AVAILABLE across ~46 repos as a side effect of a pure move (`d388c9ef`).

## Coverage Checklist

| Class | Verdict | Evidence |
|---|---|---|
| fail-open vs fail-closed | CLEAN | `empty_matches_all` is keyword-only with NO default — a caller that forgets it gets a `TypeError`, never a silent wrong answer. All three call sites verified passing the value matching their original semantics |
| cost/quota/limit accounting | REFUTED | no metered call, no LLM dispatch, no quota surface — pure path matching |
| boundary/sentinel/prefix collisions | FIXED | THE class of this ticket: the empty-pattern sentinel. Both the deliberate `True`/`False` divergence and the inherited `/**` asymmetry are now pinned by tests |
| behavior-without-a-test | FIXED | 12 tests; the equivalence test strengthened from input-dependent to relationship-asserting; the wildcard asymmetry characterization-tested |
| fleet-sync blast radius | FIXED | the 48-repo import break — found, fixed, re-synced, verified project-side |
| claims vs behavior | FIXED | three false docstring claims found and corrected; all others grepped (`same as`, `identical`, `preserves`, `never`, `always`) |
| purity of the move | CLEAN | rubric output and `select_rules --json` byte-identical; an independent differential harness (27 globs × 19 paths, 17 globs × 4 root spellings) found 0 divergences |

## Evidence

```
$ python scripts/review_rubric.py --changed db/schema.sql
## MATCHED — none (no pack glob hits the changed paths; the FLOOR still arms you)
>>> rules_match.packs_for_paths(['db/schema.sql'], Path('/opt/fabrik'))
['core/25-data-postgres.md']
```

Pre-extraction comparison, proving the wildcard asymmetry is inherited (detached worktree at
`b589a1b8~1`):

```
PRE-CHANGE select_rules._glob_has_match (empty semantics = False):
  glob '**/' -> False
  glob '/**' -> True
  glob '**'  -> True
```

Fleet state after the hotfix:

```
projects with select_rules.py: 49 | still MISSING rules_match.py: 1
(the 1 is /opt/fabrik-lib — sync-EXCLUDED by design, its vendored copy predates the import)
$ cd /opt/transdoc && python scripts/select_rules.py
Project type: saas-skeleton
ACTIVE — read these in full now (25):
```

Integrated suites, this turn:

```
$ python -m pytest tests/test_execute_plan_d7.py tests/test_rules_match.py tests/enforcement/test_pack_layout_audit.py -q
24 passed in 1.70s
```
