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

## Round 3 — over `716ce944..3fdba9ef` (55,709 B; the round-2 fixup 3fdba9ef: 26 passed, classes A–H + duplicate-`epic_n` test)
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native opus×1 — round 3.
### Adjudication (pool layer)
- gemini — CLEAN (A validation at argparse before I/O; B `newline=""` + per-file terminator; G `m.end()` after `owned_paths:` incl. multi-line lists; F zero-epic finding; 12 doc lines rewritten).
- deepseek — 2 raised: "`test_assign_integrity_failure_writes_nothing` writes only `e2.md`, so contiguity `min..max` passes and the test cannot red" — REFUTED by execution and by reading: the check is `expect = list(range(1, max(nums) + 1))` (`scripts/epic_order.py:127` on the branch), not `min..max`, and the test is green in the 26 (a scenario that produced no finding would fail its own `rc == 1` assertion); "mixed line endings are homogenised to the first style" — carried to the native finder (its brief probes a MIXED-ending file).
- qwen — 3 raised: "trailing whitespace on the `owned_paths:` line defeats the regex and the fallback appends a dangling `\r`" — carried to the native finder (class G probe); "zero epics with `expected_count=None` passes silently" — REFUTED by reading: the finding condition is `owners is not None and not epics and expected_count != 0`, and `None != 0` is True, so the default DOES fire (the coder's `test_check_owners_on_empty_dir_is_not_a_vacuous_pass` asserts rc 1 with no `--expected-count`); the 84d wording remark ends "which is fine" — no finding.
### Native finder (opus) — round-2 classes re-verified by execution (red-on-revert in isolated copies): A, B, C/D, E, F (the `--check` half), G (inline-list shape), H all FIXED and GUARDED; base-vs-branch A/B over 7 fixtures × 5 flag sets = 35 combos, 0 divergences; all 4 deletions are lines the additions replace. 7 raised:
- [M] `--assign` on an existing-but-EMPTY epics dir writes nothing and prints `ASSIGN: OK` rc 0 — the zero-epics guard (:99) is armed only with `owners`, which the `--assign` call site (:291) omits → FIXUP (1).
- [M] a MULTI-LINE YAML `owned_paths:` list is corrupted by the insertion (`owned_paths:\nowner: alpha\n  - src/a/**`), rc 0, and `check_integrity` passes before and after because the flat parser reads the block as `''`; the G test covers only the inline shape → FIXUP (2). (This confirms deepseek's and qwen's carried items only in part: the G probe failed on the multi-line shape, not on trailing whitespace.)
- [L] mixed terminators: the line before the insertion is rewritten LF→CRLF and the inserted line inherits the old one — contradicts the docstring → FIXUP (3) (deepseek's carried item: CONFIRMED for the mixed case only; homogeneous files preserve every byte).
- [L] the tail-append `rstrip("\r\n")` deletes a pre-existing blank line before the closing fence → FIXUP (4).
- [L] `ruff check tests/test_epic_order.py` → I001 (the only error in tests/; unseen because `final_gate.py:2161` scopes ruff to scripts/ + src/) → FIXUP (5).
- [L] EVALUATION_CHECKLIST :176 item 93 still says "Traycer tickets", contradicting the rewritten item 81 and 84f → FIXUP (6).
- [L] `--assign x --json` / `--assign a --check` silently discard the second flag → FIXUP (7).
Round 3 verdict: 7 findings (2 M, 5 L) → FIXUP routed to the coder; pool: 2 refuted by reading, 2 carried items resolved by the native probes (one confirmed narrowly, one re-attributed). Not the no-op round.

## Round 4 — over `716ce944..b0377293` (68,582 B; the round-3 fixup b0377293: 36 passed, seven classes red-first incl. a real block-list parser and `require_epics`)
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native opus×1 — round 4.
### Adjudication (pool layer)
- gemini — CLEAN (6/6 rows, 3/3 DO-NOTs, 4/4 files; `require_epics`; the block parser "handles quoted items, skips comments/blank lines" — the last clause is WRONG, see below; local terminator :246-248; one-CR strip :255; usage errors :317; docs).
- qwen — 2 raised: "the block parser keeps quotes and inline comments" — HALF right: quotes ARE stripped (`.strip("\"'")`), but an inline ` # comment` survives and then mis-strips the quote pair (`- "src/a/**"  # core` → `src/a/**"  # core`) → CONFIRMED by the orchestrator's read of :58-70 → FIXUP; "the disjointness finding now fires on non-parallel epics sharing a path" — it refuted itself mid-sentence (the check compares declared peers only; T03b re-keys it to phases).
- deepseek — 15 checks then 2 raised: the block loop ends at the first blank or `#` line inside the block, silently TRUNCATING the list (the vacuous-pass shape the parser was added to close) → CONFIRMED by reading (the `while` condition requires an indented `- ` line) → same FIXUP class; the tail append "could add an extra blank line when `owned_paths:` is the last field" → [L] carried to the coder as a probe + test.
Round 4 verdict (pool): 1 fix class (block-list robustness: inline comments, interior blank/comment lines, placement regex agreement) + 1 L probe → FIXUP routed before the native verdict, on the strength of the code read.
### Native finder (opus) — all 7 round-3 fixes RE-VERIFIED by mutation (md5-asserted isolated copy); hub A/B on the real `docs/development/epics/` (3 files): byte-identical `--check --json` old vs new, rc 1 = rc 1 (the frontmatter-less 2026-07-14 epic); idempotency on 13 fixture shapes; 10 usage-error shapes all rc 2. 5 raised:
- [M] `_OWNED_PATHS_BLOCK_RE` cannot cross a blank line inside the block → `owner:` inserted between two items (PyYAML after: `owned_paths=['src/a/**']`, `owner='alpha\n- "src/b/**"'`); [M] an inline `#` comment on a block item is swallowed into the glob (under-detects overlap); [L] a comment line inside the block ends the collection → these three ARE the pool-routed class, FIXED concurrently at 49d185d4 (41 passed; `_strip_unquoted_comment`, blank/comment skip, the placement regex agreeing; a zero-width-alternative bug the coder found and fixed by lookahead) — the closing round re-verifies.
- [L] two `owner:` lines: the writer replaces the first (`count=1`), the parser is last-wins → `ASSIGN: OK` then `--check --owners` fails → FIXUP (round 5).
- [L] a `depends_on` cycle escapes `--assign` as an uncaught `ValueError` (pre-existing on master's `--json`; nothing written) → FIXUP (round 5: catch at the entry point; the integrity-finding conversion is T03b's).
Round 4 verdict: 5 raised → 3 fixed in flight, 2 routed. Not the no-op round.

## Round 5 — over `716ce944..c7aab28c` (80,004 B; the round-4/5 fixups 49d185d4 + c7aab28c: 44 passed)
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native opus×1 — round 5.
### Adjudication (pool layer)
- gemini — CLEAN (18 classes re-swept: duplicate owner :195-202, the cycle catch :421-432, the block regex lookahead :276, terminator :317-320, docs, usage errors :382-404).
- deepseek — 2 raised: (1) `_strip_unquoted_comment` runs only inside block-list items; TOP-LEVEL values keep a trailing comment — and the schema's OWN example block (:18-19, this ticket's doc) writes that shape → CONFIRMED by the orchestrator's probe on the worktree: `owned_paths: ["src/x/**"]  # …` → `['["src/x/**"]  # the concurrency contract']`, `owner: ""  # named agent` → `'  # named agent'` → [H] FIXUP routed (strip on every value before branching; the schema block verbatim as a fixture); (2) the tail-append branch's terminator from a file-global scan vs the docstring → carried to the coder to verify/align.
- qwen — 3 raised: the schema header "Cited by 02/03/04" (docs that T12a/T12b retire — their edit, not this ticket's), a test not pinning the duplicate-owner message text (a nit; the finding string is asserted by `test_check_integrity_reports_duplicate_owner_lines`), a concurrent-edit race between parse and write (speculative, no evidence).
### Native finder (opus) — 14/14 earlier fixes killed their mutants (md5-asserted isolated copies); 67 fixture shapes idempotent (byte-identical, mtime unchanged); hub A/B on the real epics dir md5-identical old vs new; name validation, usage errors, zero-epic paths, docs, ruff, script headers all clean. 3 raised:
- [H] the block-list parser returns a LIST for ANY key: a block-shaped value under `title:`/`owner:`/`slug:` crashes `--check` (`TypeError … got 'list'`), `--check --owners` (`unhashable type: 'list'`) and `--json` (envelope lost) where master returned a finding; `slug:` degrades silently → FIXUP (collect blocks only for the three list keys; a scalar key with a continuation is a malformed-value finding).
- [M] `check_integrity`'s docstring "None owners means a plain `--check` is byte-for-byte the pre-assignment behaviour" — falsified by the unconditional duplicate-owner finding and by the above → FIXUP (state what plain `--check` now adds).
- [L] EPIC-ARTIFACT-SCHEMA.md :47 / checklist 84a still say the frontmatter is "flat (scalars + inline lists)" while the parser now handles block lists (8 tests); the script's AFTER-EDIT header names that doc → FIXUP (state the accepted grammar).
- Refuted candidate: the cycle traceback on the default/`--json` paths — T03b's by its Scope (the deferral comment at :429-433 is accurate).
Round 5 verdict: pool 1 [H] (top-level comment stripping, confirmed by the orchestrator's probe) + native 3 → FIXUP routed (one batch); the closing round follows. Not the no-op round.

## Round 6 — over `716ce944..ddd03663` (91,317 B; the round-5/6 fixup: comment stripping on every value with the schema's own block as a live fixture, the tail terminator, `_LIST_KEYS` + malformed-value findings, the docstring, the grammar sentence; 51 passed)
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native opus×1 — round 6.
### Adjudication (pool layer)
- gemini — CLEAN (4 files, 51 tests; round-robin, idempotency with mtime, integrity refusal, the owners gate, the 12 retired references, CRLF/mixed, the block-vs-scalar findings; rounds 1–5 resolved).
- qwen — CLEAN in substance (its items restate the passing contracts).
- deepseek — 2 raised, 2 REFUTED by execution: "the test expects exactly one `traycer` mention but the file has zero" — the suite is green at 51 and the 84d line carries `$TRAYCER_EPIC_ID` (one case-insensitive hit, as rounds 3–5 measured); "a manual trace suggests the mid-body insertion drops the following field" — the placement test on that exact shape passes and the round-5 native finder proved 67 shapes idempotent.
Native finder (opus): PENDING — appended when it returns; if CLEAN, this is the no-op round.

