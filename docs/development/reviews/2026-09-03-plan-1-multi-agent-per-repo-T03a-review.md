# Acceptance review — T03a (plan set 2026-09-03-plan-1-multi-agent-per-repo)

**Status:** IN-PROGRESS

**Surface:** the coder's worktree branch (worktree-agent-adba677796831b5c2) against its merge base 716ce944 — 4 files. Dispatch history (D6): attempt 1 was a pool write-mode coder (openai/gpt-5.6-luna) REJECTED without review — gate red with no captured output, a 198-line deletion of the checklist, 53 lines of the script removed; attempt 2 a native Sonnet worktree coder that died on a network error with gate-green uncommitted work, salvaged to `.fabrik/plan-locks/…-salvage-T03a.diff` and resumed on its intact worktree to commit (923a2dfd).

## Round 1

Finders: pool deepseek-v4-flash+gemini-3-flash-preview+qwen3-max + native opus×1 — round 1

### Adjudication (pool layer)
- gemini: CLEAN (12 checks, row→line map). qwen: CLEAN on the 6 rows with the 12-line removal enumerated; its `_write_owner` "\n---" assumption note overlaps the native finding 1. deepseek: "CHANGELOG/INDEX are in Touches and missing" — REFUTED: they are `Docs: … orchestrator-applied` (D3), never Touches; applied as Deltas at merge.
- `check_doc_sync.py --range <base>..<branch>`: CHANGELOG wanted — the Delta. Gates on the branch: 7 passed; `--help | grep -c assign` = 3; retired tokens 0/0.

### Native finder (opus) — executed (4 mutations on a copy, each turning exactly its test red; `--check` parity master vs branch 4/4 arg shapes identical over the hub's 3 epic files; checklist numstat 15/15 with every removed line replaced; no leak from the rejected attempt)
1. [write-safety, H] the append branch leaves a blank line inside the frontmatter of every epic lacking an `owner:` key — CONFIRMED → FIXUP.
2. [docs-residual, M] a section heading still reads "Traycer-Readiness" above the rewritten "No mirror" row — CONFIRMED → FIXUP.
3. [cli, M] `--owners` without `--check` silently discarded — CONFIRMED → FIXUP (argparse error + test).
4. [gate-warn, L] no `# AFTER-EDIT:` header (pre-existing) — CONFIRMED → FIXUP in the same commit.

## Round 2 — over `716ce944..6c55625c` (40,418 B; the round-1 fixup 6c55625c: 9 passed)
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native opus×1 — round 2.
### Round-1 classes re-swept (native finder, red-on-revert in an isolated copy)
1 blank line in frontmatter — FIXED and guarded (restoring the `+ "\n"` reds `test_assign_append_adds_no_blank_line_in_frontmatter`). 2 stale heading — FIXED (0 hits). 3 `--owners` without `--check` — FIXED (`error: --owners requires --check`, rc=2). 4 AFTER-EDIT header — FIXED and parsed by `check_script_headers._header_of`.
### Native finder (opus) — 10 raised
- [M] owner name used raw as the `re.sub` replacement template, never validated: `--assign 'ok,\1bad,alsook'` crashes mid-loop AFTER writing e1 (partial write vs the all-or-nothing contract); `'a\g<0>b'` writes `owner: aowner: oldb` rc=0; a newline in the name grows the frontmatter every run → FIXUP class A (validate `[a-z0-9-]{1,32}` before any write).
- [M] `_write_owner` text-mode I/O rewrites a CRLF epic to LF throughout (body changed: True) → FIXUP class B.
- [M] EVALUATION_CHECKLIST :156 "never built" vs :8/:140/:158 still routing dispatch to the cockpit/driver; EPIC-ARTIFACT-SCHEMA :47/:51 likewise → FIXUP class C.
- [M] schema keeps `kind`/`status` for a card renderer 84d says never existed (`"kind"` 0 hits in the script; `status` loaded, never read) → FIXUP class D.
- [L] writer writes raw, reader strips quotes: `--assign '"alpha"'` then `--check --owners '"alpha"'` rc=1 → closed by A + round-trip test (class E).
- [L] `--check --owners` on zero epics rc=0 → FIXUP class F.
- [L] `owner` appended last vs the schema's documented position → FIXUP class G.
- [L] `test_mega_docs_are_free_of_retired_references` cwd-dependent (errors off the repo root; 3 of 199 hub test files share the pattern); reassignment untested → FIXUP class H.
- [L] no CHANGELOG/INDEX entry on the branch — REFUTED: Deltas are orchestrator-applied at merge (D3), drafted in the orchestrator's scratch.
### Adjudication (pool layer)
- deepseek — 3 raised: "contiguity is not checked so `test_assign_integrity_failure_writes_nothing` will fail" REFUTED by execution (9 passed at 6c55625c, twice); "colon in a name splits the parser" — a `:`-name round-trips clean in the native finder's probe, and class A forbids it anyway; "duplicate `epic_n` undetected" — UNVERIFIED, carried to the coder as an evidence item.
- gemini — 3 raised: "`--assign` silently skips a no-frontmatter epic" REFUTED (the native finder's probe: `ASSIGN: REFUSED (integrity failure)`, bytes unchanged); quoted `owner:` vs unquoted writer = class E; "by_n KeyError desync" speculative, no evidence, subsumed by the refusal above.
- qwen — 0 defects (idempotency, no-frontmatter, spaces/quotes reasoned through; agrees with the native finder's evidence where they overlap).
Round 2 verdict: 8 findings in 7 classes (A–H) → FIXUP routed to the T03a coder; 1 refuted; 1 evidence item. Not the no-op round.
