# Plan review — lean command corpus plan set

**Command:** /fabrik-plan-review
**Surface:** `docs/development/plans/2026-10-25-plan-1-lean-command-corpus/` (spine + 57 tickets, 58 files)
**Spec:** `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md` (CONVERGED, D-1217, D-1219)
**Work item:** W-96f36043 (the P0 lean program, D-1216)
**Base:** branch `kaizen-lean-plan-r2`: 773420bac (the plan rebased onto master after slice A merged at bc2a9c30b), 33828e396 (pre-pin currency), 108f46748 (kaizen's lock narrowed, R9), then one commit per pass
**Result:** CONVERGED at the quiet Pass 4 (D-1227), after the scope-growth stop at rounds 2 and 3

## Slices (round 1, disjoint)

`dispatch_headroom.py --slices opus=1,sonnet=2` → `SEATS: 3` (quota cap 3; a 5-slice cut was TRIMMED, so the set was re-cut into three slices that cover every file once).

| Slice | Seat | Files |
|---|---|---|
| A-spine | opus×1 | the spine, T01a-T01d, T02 |
| B-mid | sonnet×1 | T03a-T20 (26 tickets) |
| C-tail | sonnet×1 | T21-T46 (26 tickets) |

Shape: `agent-tool` (the hub never calls the `Workflow` tool, D-961).

## Pass Ledger

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 + sonnet×2 (slices A, B, C) · all axes | found: 49, new: 49, confirmed: 48, fixed: 48, unexecuted: 0, edits: 23 | method: citation — full pass over all 58 files (A 205 claims, B ~700, C ~150); orchestrator executed the reader-test class sweep (366 unnamed, 71 named-but-ungated over 626 test files), the lock-overlap probe (2 active locks, 10 paths), `-rP` on a printing test, `assemble_commands.py` drift and exit lines (:1340-1343, :1395), `_ENTRY` (:183, no `changed-by`), `units()` frontmatter drop (:82-84), the anchors (:34, :1326, :1395); flip gates on a flipped scratch copy: rule grounding 6 examined 0 findings, plan quality 58 examined 0 findings (planted mutant → 1), convergence graded the spine; 1 RECORDED — by design (S2-14b, `fabrik-task.md:216-217` matches the spec's own cite) | 4516608359d074abaf6f0dcf7c0f580a → 13e4df8a85eb5afa96c94e86a6fef3e0 |
| Pass 2 | opus×1 + sonnet×2 (round-1 owners of A, B, C) · delta over the round-1 hunks + one hop | found: 18, new: 18, confirmed: 10, fixed: 10, unexecuted: 0, edits: 12 | method: re-derivation — each seat re-executed its slice's load-bearing claims over pins-2b (A: BC multiset 277 = 277, File Scope 263 = 263, 153 spec quotes, anchors :34/:1326/:1395, the frontmatter carrier on a scratch ledger red/green; B: the step-5 snippet, T07c step 0 (`False`), `decisions.py D-344`, four stem listings; C: 27/27 md5, `-rP`, the doc-gate flags, the folded gate lists); orchestrator ran the stem listing (8 of 15 paths `.pyc`), the corpus-glob census (30 tests glob the corpus and name no stem, `test_review_queue_pass.py` among them), `work.py show` (invalid verb), the item files on `origin/master`; confirmed: the `.pyc` leak (S1-201/S2-201/S3-201), corpus-glob tests unlisted (S3-202, closing S2-202/S2-205), `work.py show` (S1-202/S2-204), rewrite step 2 vs step 5 (S1-204/S2-203), T46 start commit (S3-204) and its master-only gate (S3-205), the `MISSING` token (S2-206/S3-206), T01d's self-justifying floor (S1-203), the Self-audit holds line (S1-205), S1-11 left in the part-a tickets; own-fix: round 1 for all 10; 1 REFUTED (S3-203: `command grep` runs the real binary, CLAUDE.md § HARD STOPS); out-of-hop fixed with destination this plan: the part-a cross-file carve-out (S2-5) and the Coverage row's cite; the corpus-glob listing rewritten from an `xargs` pipe the worktree guard refuses to a Python one-liner; `own_text` described by what it returns (infra-2's text-measure branch keeps include lines as markers) | dfd21005f4e30c84a9cca0faec8578c0 → 0dcbc27ea96e17a9645f461c1e17b73e |
| Pass 3 | opus×1 + sonnet×2 (round-1 owners of A, B, C) · delta over the round-2 hunks + one hop | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0, edits: 4 | method: re-derivation — B quiet (the stem and corpus-glob listings run verbatim, the T03c and T10 unions hold `test_assemble_dispatch_step.py` and `test_agent_definitions.py`, steps 2/3/5 consistent); C quiet (27/27 md5, both listings run, T46 gate 2 matches); A re-derived BC 277 = 277, File Scope 263 = 263, 153 spec quotes, the origin/master probe (`open`, twice); orchestrator ran T46 step 1's start-commit shape on `commands/command_rules.py` (first add 0329c943c, its parent lacks the file and holds the source); confirmed: the corpus-glob listing over-matched identifiers and pulled in `test_prune_transcripts.py`, red at base (S1-301), the T01d no-floor rule never reached T01d step 6, its BC row or T02 (S1-302), the probe's `dropped` case (S1-303); own-fix: round 2 for all 3. SCOPE GROWTH: rounds 2 and 3 both at own-fix ≥ 2/3 (10/10, 3/3), so the hunt stopped; this fixed set alone is re-verified next. Class rewrite — the reader-test bullet (rounds 2, 3): rewritten whole, path-anchored corpus-glob listing (32 tests, `test_prune_transcripts.py` out) and reds measured against the start commit; both listings executed verbatim from the plan text (11 and 32 files, 0 `.pyc`) | 0dcbc27ea96e17a9645f461c1e17b73e → e8135556e3522862a0cbb914ec72b1a1 |
| Pass 4 | opus×1 (round-1 owner of A; B and C restated at their last verified counts, no open claim) · the scope-growth stop's fixed set: S1-301, S1-302, S1-303 | found: 1, new: 1, **confirmed: 0**, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — both reader-test listings run verbatim from the plan (fabrik-researcher 7 files, corpus-glob 32, `test_prune_transcripts.py` absent); the S1-1..S1-4 tests found in their unions; the cost row's 52 and 32 re-counted; T01d step 6, its BC row (byte-identical to the spine copy) and T02 step 9 read; BC multiset 277 = 277; S1-301..S1-303 CLOSED; standing clean since their last full pass: claims, touches, interfaces, definedness, behavior-contract, deferred-questions; 1 RECORDED — measured (S1-401, post-stop residue: T01d's and T02's gate lines say a red test is a Touches miss while the spine rule they cite reports a start-red test; the gate defers to that rule; destination: T01d's own `/fabrik-review`, the gate's first run) | a6fed8e4bba05ee0a24f949902703ae3 → a6fed8e4bba05ee0a24f949902703ae3 ✓ → **CONVERGED** (D-1227) |

## Dispositions

- **Round 1** (49 raised, 48 confirmed, 1 RECORDED — by design):
  - The reader-test class (S1-1..5, S2-1/4/5/8/10, S3-1..7, S3-12): 366 unnamed reader tests and 71 named-but-ungated, over 626 test files.
  - Gates and probes: `--check` exit 1 (S1-9, S2-2, S3-9); the LEDGER line under `-q` (S1-8, S2-9, S3-8); the B/C precondition probe (O1, S1-14); two overlapping plan locks (O2, R9).
  - Ledger grammar and tooling: `changed-by` refused by the loader (S2-3); frontmatter outside the rule test (S1-10); `current` as a `units()` unit (S1-11); `vanished` loading (S3-13); the `file:` default (S2-15).
  - Ticket contents: `agent-feedback.md` appended to every agent (S2-6); the hold's lift (S2-7); T46's steps and goal gates (S3-10/11); T01d's floor before U1 (S1-6); part a vs part c ledger writers (S1-7, S2-13); `_size_ceiling.json` (S1-12); L2 timing inside unit 01's freeze (S1-13); the 50% measure (S1-15); step 7's path (S3-14); light-form pin listing (S2-12); locators (S2-11).
  - Small fixes: anchors (S1-16); a duplicate File Scope row (S1-17); a doubled word (S1-18); T10's cite (S2-14a).
  - RECORDED — by design: S2-14b (`fabrik-task.md:216-217` matches the spec's own cite).
- **Round 2** (18 raised, 10 confirmed, all own-fix; 1 REFUTED):
  - Confirmed: `.pyc` in the listing (S1-201, S2-201, S3-201); corpus-glob tests unlisted (S3-202, closing S2-202 and S2-205); `work.py show` (S1-202, S2-204); rewrite step 2 vs step 5 (S1-204, S2-203); T46's start commit (S3-204) and gate (S3-205); the `MISSING` token (S2-206, S3-206); T01d's self-justifying floor (S1-203); the Self-audit holds line (S1-205); S1-11 left in part a.
  - REFUTED: S3-203 (`command grep` runs the real binary, CLAUDE.md § HARD STOPS).
- **Round 3** (3 raised, 3 confirmed, all own-fix): the corpus-glob listing over-matched identifiers (S1-301, class rewrite of the bullet); the T01d floor rule's readers (S1-302); a `dropped` item (S1-303). The scope-growth stop fired.
- **Round 4** (1 raised, 0 confirmed): S1-401 RECORDED — measured (post-stop residue; destination T01d's own `/fabrik-review`).

## Gates

- `python -m scripts.enforcement.check_plan_tickets --plan-dir docs/development/plans/2026-10-25-plan-1-lean-command-corpus`: 57 tickets, 483 Touches paths, 110 Context-Files entries, 0 findings at every pass.
- Flip gates on a flipped scratch worktree (pass 1): `check_rule_grounding.py` examined 6 CONVERGED in-window plans, 0 with findings. `check_plan_quality` examined 58 files with 0 findings, and a planted missing-section mutant read 1.
- `check_review_hygiene.py` ran on each pin. `check_citations_resolve.py --doc` on the spine pin: 23 of 23 graded citations resolve.

## Coordination

- infra-2 adds `changed-by` to the ledger grammar (branch `w-a9b5e763-lean-measure`), and lands L2's `close-feedback.md` sentence outside unit 01's freeze.
- intel narrows its own-scrape lock in W-487e966a's branch.
