# Plan review — 2026-09-03-plan-1-multi-agent-per-repo (author-blind pass)

Surface: 2b6258df68b8f75f8f1814eb85e0b81fe5497431
Plan set: `docs/development/plans/2026-09-03-plan-1-multi-agent-per-repo/` (spine + 26 tickets), Status **DRAFT**
Reviewer: intel (`/fabrik-plan-review`), passes 1–5; the author-blind layer was one native Opus pass with live repo tools.
Verdict at first write: **NOT CONVERGED** — seven HIGH findings, three of them fail-open defects the plan would have shipped into
fleet-synced enforcement.
**Verdict now: all seven are CLOSED in the set** (2026-09-04, same session, after the operator ruled that infra is
unreachable and asked me to resolve my own part). The plan grew from 26 to 32 tickets: five of the closures needed new
tickets, and three of those were split again purely by read budget. See § Closure below.

## Why the author-blind layer was a single native pass

The pool breadth layer was dispatched (24 grounders, one per ticket) and returned **HTTP 402 on every unit**:
OpenRouter shows $225.00 granted / $225.00 used, remaining -$0.0015. Zero output, zero spend. The pool is
unavailable fleet-wide until the operator tops it up — recorded here because "we ran the pool" would otherwise
be assumed by the next reader. The native pass carried the whole breadth load alone.

## HIGH — verified by the reviewer independently, not taken on the finder's word

| # | Finding | Proof I re-ran myself | Owner |
|---|---|---|---|
| H1 | **Relocating the plan-locks silently disarms the fleet-synced Stop hook.** `.claude/hooks/final_gate_stop.py:864` arms on `if ".fabrik/plan-locks/" in rel and p.is_file():`. Move the locks to `~/.claude/state/` and that hook never arms again — in this repo and in every project it is synced to. | `grep -n 'plan-locks' .claude/hooks/final_gate_stop.py` → `:864`; `git grep -l '\.fabrik/plan-locks' \| wc -l` → **50 tracked files**, of which the plan maps **3** | T04b / T05a (or a new T05c) |
| H2 | **The renderer does NOT auto-append the run record.** T06a's Scope asserts "the source carries NO run-record … the renderer appends them"; `commands/assemble_commands.py:774` auto-appends **only** `_CLOSE_FEEDBACK`. Every other fragment needs an explicit `{{include:<name>}}` line. The three new commands would ship with no run record, no pinned `RUN:` line, and `check_command_corpus` (BLOCKING) would flag the missing close sites. | `sed -n '770,780p' commands/assemble_commands.py`; `grep -c '{{include:run-record}}' commands/_sources/*.md` → **30 of 33 sources carry it explicitly** | T06a (T06b/T06c inherit) |
| H3 | **T07b's Behavior Contract asserts the wrong return value and omits the dict that actually routes.** `first_regex_match` returns a bare STEM; `STEM_SKILLS` (`.claude/hooks/skill_router.py:108`) maps stem → skill name and `resolve_target` reads it. Adding only `KEYWORD_STEMS` entries yields `resolve_target → None` and the router never fires for the three commands. | `grep -n '^STEM_SKILLS' .claude/hooks/skill_router.py` → `:108` | T07b |
| H4 | **Every source-touching ticket's own `--check` gate is unsatisfiable at its position, and merging the first one refuses every sibling's `commands/` commit until T07a renders.** The `command-corpus-check` pre-commit hook runs `assemble_commands.py --check` on any commit under `commands/` or `docs/orchestrator/`; a new source reads MISSING and an edited source reads HAND-EDITED, both `sys.exit(1)`. | `.pre-commit-config.yaml` `command-corpus-check` files-filter; `check()`'s MISSING/HAND-EDITED branches | § Global Constraints + T04a, T04b, T06a, T06b, T06c |
| H5 | **T14b's gate can never reach 0.** ~21 tracked files still carry retired-chain references after every ticket runs, none in any Touches. Three are FUNCTIONAL, not prose: `scripts/review_rubric.py:103` points at the ettw checklist **T11 moves**; `check_review_coverage.py:581,1314` keys a live parser on `fab-mega-04-validate` **T07a deletes**; `scripts/command_run.py:1236` hard-codes the same name. `orchestrator-cockpit-decisions.md` is declared OUT-OF-SCOPE (I13) but is not in the gate's exclusion list. | the finder's post-retirement simulation, re-checkable with its own `git grep` | T14b |
| H6 | **T13's prune requirement is impossible against the loop it cites.** `scripts/wip_backup.sh:35` globs `refs/wip/bak-*` and compares a timestamp parsed out of the ref name; `wt-<name>` matches neither. The ticket calls it a "dated ref" while its own contract names `refs/wip/wt-beta`. Separately `:40` `|| continue` skips the repo body when the MAIN tree is clean, which is exactly T13's own test case. | `sed -n '34,40p' scripts/wip_backup.sh` | T13 |
| H7 | **The spec's "`**Owner:**` becomes mandatory on new plans and the per-epic spec" is unmapped, and the spine's Self-audit credits a ticket that does not do it.** Neither T04a nor T04b mentions `**Owner:**`; no command source is edited to emit it; no check enforces it — yet T15's PLANS table reads it. | spec § Ownership surfaces; T04a/T04b Scope + Behavior Contract | T04a/T04b + spine § Self-audit |

## MED (16) and LOW (11)

Recorded in full in the finder's report and carried into the spine's § Residual unknowns as named open items.
The substantive ones: T07a's deletion range misses two live `ORCH_SOURCES` sites (`:792`, `:877`) → `NameError` on
render; T09's `DIRS` → file-list breaks the check in ~46 projects where those files do not exist (`FileNotFoundError`
where today a missing dir yields "PASS - 0 files"); T05b's cited skip precedent is itself a PASS row, contradicting
its own contract ("never as passed"); T05a implements ticket ⊆ epic but not spine ⊆ epic, two of the spec's three
containment levels; T15 changes three PLANS columns and `Phase` has no defined source; T02 leaves the `Agent-Name`
enum stale in both governance contracts; T01 never names `GOVERNANCE_TEMPLATES`, the list that actually distributes
a new template file; T01 contradicts the spec's "hub settings.json untouched" without declaring the supersede; the
`rule-grounding-gate v2` twin-sync marker spans 9 orchestrator files, 7 of which move, with no ticket; the
`~/.traycer` install step (README ×7, INDEX ×2) is unmapped. LOW includes six wrong-but-harmless anchors and a
sizing understatement (T06a's real read set is 231,812 B, T07's 254,871 B — 7 KB of headroom, not 90 KB).

## What passes 1–5 already fixed (21 findings, committed)

Fail-open gates in four retirement tickets, proven vacuous by execution (`|| true` → unconditional exit 0) · a gate
calling a script that does not exist · four rotted anchors (`CLAUDE.md:150`→`:155`, `:173`→`:178`,
`final_gate.py:906,932`→`:772,:929`, `wip_backup.sh:41`→`:40`) · the Coverage Checklist carrying no verdict tokens
and no pasted rubric, both of which would have failed the CONVERGED flip · a self-inclusive link-sweep denominator
· a MATCHED pack missing from the Constraints Digest · a bare-filename citation · four empty `## Context Files`
sections · two unlisted consumed files · ten dangling ticket IDs after five splits · two breadth splits (peak score
9 → 7).

## Coverage Checklist

Armed by running the rubric over the plan's own `## File Scope (owned paths)` (95 entries):

```
$ python scripts/review_rubric.py --changed $(the 95 File Scope entries)
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3)
### core/35-security-auth.md
### core/25-data-postgres.md
### core/30-ops.md
### 12-FACTOR (all twelve axes)
## MATCHED — packs whose globs hit the changed paths
### ai/50-agentic.md  (hit: docs/orchestrator/00-autonomous-factory-north-star.md, docs/orchestrator/_retired/epic-to-ticket-workflow/00-trigger-fabrik.RETIRED.md, docs/orchestrator/_retired/epic-to-ticket-workflow/01-decisions-lock-fabrik.RETIRED.md)
### core/10-python.md  (hit: .claude/hooks/agent_role.py, .claude/hooks/skill_router.py, commands/assemble_commands.py)
### core/40-documentation.md  (hit: .windsurf/rules/core/40-documentation.md, CLAUDE.md, agents-fabrik-core.md)
### core/45-testing-strategy.md  (hit: tests/enforcement/test_final_gate_epic_order.py, tests/enforcement/test_plan_lock_release_dir.py, tests/enforcement/test_plan_tickets_epic_scope.py)
[STRUCTURAL EXCERPT of a 33069-byte output — verbatim header and every section line; each pack's rule body elided for length.]
```

| Class | Verdict | Evidence |
|---|---|---|
| fail-open/fail-closed | FIXED (5) | Four retirement gates ended in `\|\| true` — proven vacuous by executing them against a tree where their own condition is false (exit 0; the replacements exit 1). Fifth: a gate calling `check_governance_texts.py`, which does not exist, behind `2>/dev/null \|\|`. **The author-blind pass then found a sixth and worse one: H1, moving the plan-locks silently disarms `final_gate_stop.py:864` — still OPEN.** |
| cost/quota accounting | FIXED (3) | Per-ticket READ budgets recomputed after every edit: T04 (293,629 B), T05 (267,161 B) and T08 (258,556 B, 3.6 KB of headroom while a sibling grew both files) each forced a split. Also recorded: the pool returned HTTP 402 on all 24 units, OpenRouter at $225.00 of $225.00 — the breadth layer was unavailable, not skipped. |
| boundary/sentinel/prefix | CLEAN | T02's name bound tested at 32 (accept) / 33 (refuse) / uppercase (refuse); T05a's containment tested on both the `Epic:`-present and `Epic:`-absent branches, the second asserting byte-identical output to today; the `.claude/worktrees/` line asserted with its trailing slash; T03's round-robin tested across a phase boundary. |
| behavior-without-a-test | CLEAN | All 26 tickets walked: every Behavior-Contract row's implied test file sits in that same ticket's Touches. The prose-only tickets carry executable gates (`assemble_commands.py --check`, `check_traycer_chain.py`, `git grep` denominators) instead of test files — which is why H4 matters: those gates are unsatisfiable at their tickets' positions. |
| author-blind coverage | FIXED (7 HIGH raised) | One native Opus pass with live repo tools; its three severest claims independently re-verified by the reviewer before being written down. |
| pool breadth layer | ROUTED | Unavailable (HTTP 402); escalated to the operator for a top-up. |

## Pass Ledger

| Pass | axes re-checked | method | raised | new | edits | combined md5 (start → end) |
|-----:|---|---|---:|---:|---:|---|
| Pass 1 | rubric arming · constraints digest · anchors · gates · budgets · spec coverage | method: citation | 12 | 12 | 12 | 38a0f16f → (many) |
| Pass 2 | counts · denominators · breadth adjudication · board-vs-tickets | **method: re-derivation** | 3 | 3 | 3 | … |
| Pass 3 | definedness · context files · budget recheck | method: citation | 3 | 3 | 3 | … |
| Pass 4 | dangling ticket IDs · roll-up set equality | method: gate | 3 | 3 | 3 | … |
| Pass 5 | full mechanical sweep + anchor re-resolution | **method: re-derivation** | 0 | 0 | 0 | d4d10ce3 → d4d10ce3 ✓ |
| Pass 6 | **author-blind #1** (live repo tools) | method: re-derivation | 34 | 34 | 21 | … |
| Pass 7 | **author-blind #2** — the six tickets pass 6's closures created | method: re-derivation | 10 | 10 | 10 | … |
| Pass 8 | **author-blind #3** — the closure delta of pass 7 | method: re-derivation | 7 | 7 | 7 | … |
| Pass 9 | **author-blind #4** — the r11 re-convergence + a re-read of both earlier passes | method: re-derivation | 24 | 24 | 24 | … |
| Pass 10 | flip pre-flight: `check_convergence`'s predicates run against a scratch copy flipped to CONVERGED | method: gate | 1 | 1 | 1 | 00612f7a → 81e04ecb |
| Pass 11 | **author-blind #5** — the confirming pass over pass 9's closures | method: re-derivation | 18 | 18 | 18 | 3934a2d5 → e6f284e6 |
| Pass 12 | my own re-sweep of pass 11's five open classes | **method: re-derivation** | 3 | 3 | 3 | e6f284e6 → e6f284e6 |
| Pass 13 | **author-blind #6** — the confirming pass over pass 11's closures | method: re-derivation | 16 | 16 | 16 | bf680901 → e7c9e68b |
| Pass 14 | **author-blind #7** — pass 13's brief REPEATED VERBATIM; caught a regression pass 13's own closure introduced | method: re-derivation | 7 | 7 | 7 | e7c9e68b → 7e93639a |
| Pass 15 | **author-blind #8** — the same brief a THIRD time; found a BLOCKING gate no round had executed against the moved paths | method: re-derivation | 10 | 10 | 10 | 7e93639a → 2bf7767b |
| Pass 16 | **author-blind #9** — the same brief a FOURTH time | method: re-derivation | — | — | — | (in flight) |

Pass 5 was edit-free and md5-stable — but pass 6, the author-blind layer, raised 34. **An edit-free own-pass is
method-stability, not truth**, which is precisely why this command forbids the author's own re-read from counting.
Every author-blind pass since has found defects in the previous pass's closure work: 34 → 10 → 7 → 24. The plan's
own spine now carries this same ledger, because `check_convergence.py:507` requires it and because the history is
the most useful thing in the artifact.

## Closure — how each HIGH was resolved

| # | Closed by | What changed |
|---|---|---|
| H1 | **T05c + T05d + T05e** (new) | The lock move now carries its consumers. T05c takes the fleet-synced Stop hook (`final_gate_stop.py:864`) — the one whose silent disarm made this the severest finding; T05d takes `check_plan_tickets`' own-lock metadata exemption (`:320`, `:1038`), which T05a edits the file for but never touched; T05e takes cert-coverage, the manifest's salvage-diff gitignore leg (`:258`) and the four test files. Split three ways because the combined read set measured 623,472 B against a 262,144 budget. Each ends with a `git grep` gate proving zero code consumers remain on the old path. |
| H2 | T06a, T06b, T06c | Each now states the four explicit `{{include:…}}` lines the source must carry, and says why: `assemble_commands.py:774` auto-appends `close-feedback` and nothing else, which is why 30 of 33 existing sources carry `{{include:run-record}}` themselves. |
| H3 | T07b | Scope now names `STEM_SKILLS` (`skill_router.py:108`) alongside `KEYWORD_STEMS`, and all three contract rows assert the real return value — `first_regex_match` yields a STEM, `resolve_target` maps it to the skill name. Adding one dict without the other yields `None` and a router that never fires. |
| H4 | § Global Constraints | "Merge-time render only" is rewritten as a hard ordering constraint: EVERY source-touching ticket renders before committing, not just T07a — because `command-corpus-check` refuses any `commands/` commit whose sources are ahead of the installed corpus, so one un-rendered merge would block every other session's commit under those paths until someone rendered. |
| H5 | T14b + **T14d, T14e, T14f** (new) | The three functional survivors are now owned: `review_rubric.py:103`'s dead checklist path (T14d, with the previously unmapped `~/.traycer` README retirement), `check_review_coverage.py:581,1314`'s dead command key (T14e), `command_run.py:1236`'s report obligation (T14f). T14b keeps the prose sweep and its gate now lists every DECLARED deferral as an explicit pathspec, so a reader sees what was deferred instead of inferring it from a passing check. |
| H6 | T13 | Refs are `refs/wip/wt-<name>-<UTC-ts>` (the existing prune parses the time out of the ref NAME, so a bare `wt-beta` would never expire), the prune glob is widened, and the inner loop is pinned ABOVE `:40`'s clean-tree `continue` — below it, T13's own test case would never run. |
| H7 | T04b + spine § Self-audit | T04b now makes `**Owner:**` mandatory at creation, emitted from `CLAUDE_AGENT` by `/fabrik-plan-after-chat`. The Self-audit's false credit to "T04" is withdrawn and named as withdrawn. |

Two MED claims were also withdrawn rather than defended: the Self-audit's four-way settings-JSON identity (T14a's line (d) and T15's doc never restated it), and the silent contradiction of the spec's "hub `.claude/settings.json` untouched" — now a declared, argued supersede in § What we already agreed.

## Second author-blind pass — on the six tickets the first pass's closures created

Work written to close a review finding is the least-reviewed work in a set, so the six new tickets got their own
author-blind pass. It raised **10 HIGH + 5 MED + 3 LOW**, every one verified by me against the live code before
acting. The severest was in my own fix:

| # | Finding | Proof | Closed by |
|---|---|---|---|
| P2-H1 | **The Stop-hook fix could not work.** T05c re-keyed `final_gate_stop.py:864`, but that line iterates `authored`, built by `_session_files()` (`:303`) whose docstring reads *"Only paths INSIDE root count"* and which drops everything else. A lock at `~/.claude/state/` can never enter `authored`, so the re-key arms nothing — silently, in the hub and ~46 projects. | `sed -n '303,310p'` + `:861` | T05c now owns the ARMING SOURCE, not the path: stat the lock directly, and re-derive the session-scoping the `authored` membership used to give (matching the lock's `plan` field against a plan set this session authored), because losing it turns every sibling's active plan into a stall for everyone. |
| P2-H2 | All three lock tickets mandated "the single `FABRIK_PLAN_LOCK_DIR`-aware helper T05a introduces" — **T05a introduces no such helper, and cannot**: enforcement checks are synced dependency-free and the Stop hook is standalone. | T05a's Scope + Touches | The phrase is gone from all three; each carries the verbatim four-line snippet instead. |
| P2-H3 | `scripts/enforcement/check_phase_tests.py:36` builds the path COMPONENTWISE, so no slash-grep census found it; `_active_locks()` returns `[]` when the dir is absent, so the whole phase-tests gate would pass silently for every plan. | `grep -n 'plan-locks' scripts/enforcement/check_phase_tests.py` | T05e owns it as PRIMARY PATH. |
| P2-H4 | `check_plan_tickets.py:650` and `:1574` are componentwise too and both fail OPEN (board-staleness class dies; sibling plan sets never discovered) — and T05d's own gate greps only the slash form, so it passed with both still wrong. | `grep -n 'plan-locks'` → 320, 650, 1038, 1052, 1574 | T05d names both, with a gate pattern matching BOTH forms. |
| P2-H5 | T05e's Gate 2 was unsatisfiable: `final_gate.py:1153` matches and T05e was forbidden to touch that file. | the residual after T05a–T05e | The comment is handed to T05b, which already owns the file — carrying a 123 KB file for one comment blew T05e's budget at 337,981 B. |
| P2-H6 | `tests/test_check_certification_coverage.py:47` builds fixtures at the old dir and is a different file from the one T05e's gate ran — a guaranteed red escaping the plan. | `ls tests/ \| grep cert` | Added to T05e's Touches and its pytest gate. |
| P2-H7 | The functional cert-lock site is the constant `FORBIDDEN_LOCK_DIR` (`:59`, consumed `:237`), not the `:257` message the ticket cited — leaving it makes a BLOCKING detector scan an empty directory while a message-only edit reports green. | `grep -n 'FORBIDDEN_LOCK_DIR'` | T05e cites it by SYMBOL, per the spine's own anchors-move rule. |
| P2-H8 | **T14e's Gate 1 ran no test and could not fail:** `tests/test_check_review_coverage.py` does not exist, pytest exits 4, `2>/dev/null` hides it and `\|\|` runs a fallback that exits 0. | measured exit codes | Gate now runs the two files that DO exist, with no `\|\|` and no stderr suppression. |
| P2-H9 | **T14e's stated root cause was false.** Both `fab-mega-04-validate` strings are prose; routing is by `MEGA_REPORT_H1` (`:604`) and a reserved filename regex (`:606`). The real risk is the inverse — if `/fabrik-epics-review` renames its report, the mega grammar stops routing and the report falls through. | `grep -n 'MEGA_REPORT_H1\|_is_mega_report'` | T14e is re-scoped to a prose re-word; **T06c** now pins the report filename and H1 as a contract, with a Behavior-Contract row, and T14e depends on it. |
| P2-H10 | `templates/governance/CLAUDE.md:132` states the old lock path to 47 repos and was owned by NOBODY — T05e delegated it to T14a, whose Scope never mentioned it. | both Scopes | T14a gains it as a fourth numbered item. |

MED closures: T16's Depends omitted all six new tickets and the dispatch policy still named a retired `T05`; the
census was stale in both directions (55 by the slash form, 69 including componentwise); T14b's gate still could not
reach 0, so **T14g** now owns the six survivors — one of them, `fabrik-conformance-review.md:11`, is a live routing
instruction naming a deleted command; T05e's gitignore row asserted something a repo-relative pattern cannot do
(the leg is DELETED, not re-pointed); T14d left a two-branch decision to the coder (now: drop the `ettw` key) with a
gate blind to the docstring mentions.

Set is now spine + 33 tickets. Emit gate exit 0 / zero WARN after every edit; closing pass edit-free.

## Third author-blind pass — and the verdict that stops the loop

The delta from pass 2's closures got its own pass: **7 HIGH + 7 MED**. Non-lock findings are closed (T14b's gate
was a zero-count that can NEVER pass, because after the tombstone moves the banned tokens live inside the PATHS
`INDEX.md` is required to list — it is now an allowlist; the spine's fan-out line dispatched T14d and T14g
alongside T11, which both Depend on; T06a/b/c's chain gate scanned four `docs/` roots and never the new sources,
so it passed without reading them; T03 now owns two `mega-epic-breakdown/` files whose stale references nobody held).

**The lock family is a different matter, and the pattern across three passes is the finding.** Each round closed
the previous round's defect and the next pass disproved the fix:

| Round | The fix | What the next pass proved |
|---|---|---|
| 1 | Move the path in 3 files | 50 consumers, not 3 — including a fleet-synced Stop hook |
| 2 | Own the hook and the other consumers | The hook only sees repo-relative `authored`; the re-key arms nothing |
| 3 | Stat the lock directly, re-derive session scope from its `plan` field | `root` is cwd so the repo basename is underivable there; and the `plan` field has 4 shapes across 60 live locks, 4 of them holding no path |

That is not plan quality any more. **The spec's § Live locks relocation fights four in-repo invariants** — the Stop
hook's `authored` contract, `check_plan_tickets`' deliberate refusal of `~`/absolute tokens (`:314` says so in
words), `check_certification_coverage`'s tuple-joined-onto-root addressing, and a repo-relative gitignore leg that
can only be deleted. It is recorded as a **BLOCKING spec re-freeze item** in the spine's § Residual unknowns, with
a derived recommendation: drop the relocation, because `epic_order.py --check` already proves per-phase
`owned_paths` disjointness before dispatch, so the lock's cross-agent role is largely redundant under this very
design and its surviving job — resume after a crash — is per-tree and works in-repo today.

**Verdict: the plan does not converge, and should not.** Everything outside the lock family is closed and
gate-green at 33 tickets. Five tickets wait on one spec decision that is cheaper to make than to keep patching.

## Re-convergence against spec r11

The spec was re-opened on § Live locks alone and reached **CONVERGED r11** (fae8e820, ruling D-117): the lock
relocation is WITHDRAWN, and § Assignment's disjointness claim is corrected as false. The plan was re-converged
against it in 884a5728.

**The five blocked tickets resolved mostly by SUBTRACTION, which is the point.** T05c, T05d and T05e were deleted
outright — they owned the Stop hook, the metadata exemption, the certification check, the manifest's ignore leg and
eight test files, and every line of that existed only because the locks were moving. T04b keeps the `Epic:` line,
the dispatch containment and the merge target, and now states per-worktree locks as the design rather than a
compromise. T05a keeps both epic-containment levels and loses its lock half (and its slug, which said
"lock-dir-move"). T05b loses the gate-comment task; T14a's fourth item is void.

**One thing r11 ADDED:** the disjointness check has always been credited with proving parallel-set `owned_paths`
disjointness and does not — it intersects glob STRINGS for pairs that each declared the other parallel. T03b now
owns making it real, keyed on `phased_order()` phases rather than the author-declared field.

**Two splits, both forced by measurement rather than taste.** T02 scored 9 on the breadth check AND broke the read
budget at 264,036 B once the spec grew at r11 — split into the hook (T02a) and the two governance contracts (T02b).
T03 scored 9 on eight behaviours once the disjointness work landed — split into assignment (T03a) and the
strengthening (T03b). Peak breadth fell from 9 to 7.

**A process defect caught by grep, not by a check:** an earlier re-converge script died on an assertion BEFORE its
write, so the spine's residuals, interfaces, constraints digest and dispatch lists silently kept describing a
design that no longer existed. The count a script prints is not proof the file changed; verify inside the same
script, after the write.

Set is spine + 32 tickets. Emit gate exit 0 / zero WARN, no DAG violations.

### Class re-sweep — the Stop hook refused the close, correctly

The run record's class ledger still had `lost-script-write` OPEN, so the hook refused to let the run end. Re-sweeping
that class with the SAME brief (never a re-scoped one) found **nine more instances of exactly it** — text that
survived a change to the set because nothing re-derived it:

| What | Was | Now |
|---|---|---|
| Coverage Checklist coverage claims (×4) | "all 26 tickets" | all 32 |
| Breadth residual | "16 of the 24 tickets" | "16 of the then-24" |
| Synced-surface list, testing-strategy digest row | named a split-away `T02` / `T03` | T02a/T02b, T03a/T03b |
| Boundary-collision row | "T02's name bound", "T03's round-robin" | T02a's, T03a's |
| Self-audit gap check | "84a → T03" | T03a |
| Breadth adjudication table | a KEEP row for a `T03` that no longer exists | replaced by the T03a split record |
| Self-audit | `check_plan_lock_release.py:396` → T05a | the relocation → NO ticket (r11) |
| Cost/limit row | three budget-forced splits | four — spec r11 grew the design doc and pushed T02 to 264,036 B |

One thing the sweep deliberately did NOT "fix": `all 24 grounder units` is the number of pool units dispatched, not
a ticket count. Correcting it would have been the denominator error in reverse.

### Subtraction verified independently

The riskiest edit in a re-convergence is DELETION, so the twelve files the three deleted tickets used to own were
checked one by one. Every one is now either unowned AND unmentioned by the plan — correct, because the relocation
was their only reason to exist — or owned by a surviving ticket for an unrelated reason
(`check_plan_tickets.py` by T05a for epic containment, `fabrik_synced_manifest.py` by T01a/T01b for the
worktree-include leg). Nothing was dropped silently.

Closing state: 32 tickets, Board 32 = disk 32, spine roll-up 106 = ticket roll-up 106, checklist 17/17 verdicts and
0 UNCHECKED, emit gate exit 0 with zero WARN, class ledger clean.

## Passes 4 and 5 — and a false BLOCKED close I have to own

**Correction first.** I closed the previous run BLOCKED, reasoning that the author-blind layer was unavailable: the
pool returns HTTP 402 fleet-wide, and two native dispatches each showed a 130-byte output file that had been quiet
for minutes. **That reasoning was wrong.** Both passes completed and returned full reports; the 130-byte file is
not where the result lands. I reported an infrastructure outage that did not exist, on a proxy I had never
validated — the same class as the proxy-never-evidence rule, committed while enforcing it elsewhere. The pool
exhaustion is real; the native failure was not.

Between them the two passes raised **24 findings**. The severest were not in the plan at all:

| # | Finding | Why it mattered |
|---|---|---|
| P4-H1 | **The SPEC was self-contradicting.** r11 re-froze § Live locks but left four r10 residuals naming the withdrawn path (§ Personas, § Chain consolidation (e), the fabrik-lib verdict row, § Documentation landing sites). | A plan cannot conform to a contract that disagrees with itself. Fixed as an r12 editorial pass — no design change. |
| P4-H2 | **§ Self-audit (b) was CORRUPTED by my own blind global replace**, which consumed a four-clause span and left a fragment mid-sentence in a `check_convergence` artifact. | Self-inflicted, and invisible to every gate. Restored from `884a5728^` and re-derived. |
| P4-H3 | **T02b's premise was false.** `templates/governance/CLAUDE.md` has no `Agent-Name` row — its trailer table never carried one, because Agent-Name is hub-only by design. | The ticket would have sent a coder to invent that concept in a file syncing to ~46 repos, and its gate went green after editing the hub file alone. |
| P4-H4 | **T05b would have redded the hub's own gate.** `epic_order --check` FAILS today on a legacy epic with no frontmatter, and the script it registers is in no synced manifest. | The row would ship to ~46 repos pointing at a file none of them has, while the ticket's own gate could never pass here. |
| P4-H5 | **T03b failed open on the design's primary case.** Epics are authored before the code, so two greenfield epics owning the same path both realise to ∅ and no finding fires — exactly the case its own contract row demands. | Now unions realised sets with a pattern-level check. |
| P4-H6 | **Both glob predicates named bare `fnmatch`, which is separator-blind** — it matches `src/a/b/deep.py` against `src/a/*`. | A deliberately shallow epic scope would have admitted a whole subtree, silently voiding the "a window cannot build outside its epic" guarantee. |
| P4-H7 | **The dispatch and fan-out lists omitted T02b, T03b and T14g entirely.** | The three tickets carrying the r11 work would never have been dispatched, and no gate parses that prose. |

Also closed: T06c told a project-side command to run a hub-only script by relative path; the one NON-relocation
item the three deletions dropped (a stale `final_gate_stop.py:785` citation at three sites) is rescued as **T14h**;
`docs/reference/plan-lock-lifecycle.md` went back into scope under T15, since this design makes it partly untrue;
`phased_order()` raises on a cycle and would have turned `--check` into a traceback inside the gate; and T14a's
rollout-wait edit had no gate at all, so two of its three edits would have gone green.

Set is spine + 33 tickets. `check_plan_tickets --plan-dir` exit 0 with zero WARN; `final_gate.py --check --json`
**success, 55 passed, 0 failed**.

## Pass 10 — the flip pre-flight, which found its own blocker

Rather than attempt the flip and see, I copied the set to a scratch directory, flipped the copy to CONVERGED, and
ran `check_convergence`'s own predicates against it. It refuses a CONVERGED claim whose spine carries no
`method: re-derivation` Pass-Ledger row (`check_convergence.py:507`) — and this spine had **no Pass Ledger at
all**. The artifact had one; the plan did not. The flip would have failed after the loop rather than during it.
Written and re-simulated clean at 81e04ecb.

NEXT: **pass 11, the confirming author-blind pass, is in flight** — the flip waits for it. It is not ready before
then, and the earlier version of this line said otherwise, which was wrong: pass 10 had not yet run and pass 9's
closures have never been independently reviewed.

## Pass 11 — the confirming pass was not a no-op, and three of its findings were wrong

I held the flip on a confirming author-blind pass and it raised **18 findings — 6 HIGH, 8 MED, 4 LOW**. The
headline is worth stating plainly, because it is the reason the flip was held: the pass found the plan
**mechanically sound and the flip pre-flight clean**, and the artifact that flip would pass on **untrue** in
several places. `check_convergence` gates on the presence and shape of the Coverage Checklist, the Pass
Ledger's re-derivation row and the rubric header — none of which can tell whether the numbers inside them
are true. The gate would have passed. That is the failure mode this pass existed to catch.

**Two decisions had been delegated to the coder.** T05b named two blockers and offered a fork on each, and
in both cases every remedy it offered was outside its own Touches — the coder could not have taken either.
Decided at plan time: bring the one non-compliant epic (of three on disk) up to the schema, and do **not**
relax `check_integrity`, which would silently un-gate every future malformed epic; and register `epic_order`
conditionally on the script existing, rather than adding it to the synced set, which is a ~46-repo
distribution call this plan has no mandate to make. The epic's path is now in T05b's Touches and the spine
File Scope, which is what makes the first decision executable rather than a wish.

**Four gates passed with the work undone.** T10/T11/T12a/T12b asserted rename-purity with
`git diff --cached -M --numstat`, which is empty after the commit — the same "green with the work undone"
class an earlier round fixed for `|| true`, reappearing in a different disguise. I proved it rather than
reasoning about it: the old form passes against the empty index, and the replacement (`git show ... HEAD`)
correctly flags a content commit. T02b and T14h asserted only that the old string was gone, so deleting the
row outright would have passed; both now carry the positive half.

**Three of the eighteen were wrong, and checking rather than accepting is the point.** The pass's File Scope
count of 109 came from a hardcoded `sed -n '296,406p'` range that my own earlier insert had already shifted
— the real count is 112, and the same bound is why its T12a byte figure (196,735 B) disagreed with the
measured 181,435 B. It attributed a misquote to T14b; the misquote is in T14e. And it reported the spec
repeating a rotted `check_traycer_chain.py:28-33` anchor at `:152` — the spec cites that check **by symbol**
at `:315`, and `:152` carries no anchor at all. A reviewer's finding is a claim like any other.

**Pass 12 was my own re-sweep and it found three residuals — all created by pass 11's own fixes.** Adding
the legacy epic to File Scope invalidated the rubric block I had refreshed minutes earlier (111 → 112), and
two dangling ranges survived the first sweep. This is the fix-residue share the contract predicts, and it is
why a round that changes anything is never the round that closes the ledger.

Both gates green at `e6f284e6`: `check_plan_tickets --plan-dir` exit 0 / 0 bytes, `check_convergence` exit 0.
**Status stays DRAFT** pending pass 13 — the terminal condition asks for a confirming pass over these
closures, not my own re-read of them.

## Pass 13 — the method changed, and two whole classes appeared that no earlier round could see

Pass 13 returned **16 findings, 5 HIGH, verdict "do not flip."** What made it different from the twelve
passes before it was not effort but METHOD: it **executed all 64 `Gate:` lines** instead of reading them.
Every earlier round, mine included, had inspected gates as text. Two classes fell out immediately, and
neither is visible to a reader:

**Gates that could never pass.** T14b's tree-wide token grep ran at Merge Order 25 while twelve matching
files are cleared by T14c–T14g at positions 26–30 — a coder would have been handed twelve `UNOWNED:` lines
naming files their own `DO-NOT` forbids them to touch, with no way to green the gate at dispatch or at merge.
T15's `docs_updater.py --check` is repo-global with no `--path` flag and exits 1 today on 123 lines of
pre-existing debt in *other* plans, none of it in T15's scope. And T05b said "DECIDED: bring the legacy epic
to schema" while never naming `epic_n` — the obvious value from the filename (`epic-1`) collides with the
zitadel epic and reds T05b's own gate; `epic_n: 3` is the only passing value.

**Gates that could never fail.** Seven tickets had no gate that is red today, so a coder who did nothing
passed. The Coverage Checklist had already recorded this class as FIXED — true for the five tickets it
named, and never swept across the set. That is the more instructive half: the class was known, the fix was
applied to its instances, and the sweep was declared without being run.

**Three corrections to my own work, from the same pass.** The sibling-plan serialization paragraph I had
written hours earlier carried three wrong facts about a six-row table: "six of seven tickets" came from
`grep -c '^| T'` counting the `| Ticket |` HEADER as a data row — the exact structural-line-as-data-row shape
this repo's contract warns about and which I had quoted the same day; the "one 🔴 ticket" is a conditional
inside a run log, not a Board status; and the manifest belongs to T01a alone. The paragraph was itself the
output of a disjointness check I ran to catch other people's ordering defects.

**The breadth table moved under its own fixes.** T03b and T07a measured 5 earlier in this review and measure
6 now — raised by *this round's* additions to their Behavior Contracts. The general lesson is recorded in the
table itself: a breadth score is a function of the ticket as it stands, so it is re-derived at the end of a
round, never cited from the round that opened it.

**The stall-breaker fired** on 18 → 3 → 16 and offered two diagnoses: a loop that re-scopes each round, or a
stable ledger over a surface that keeps yielding. The honest answer is the second with a caveat — the ledger
was stable, but pass 13 widened the METHOD, and a widened method is how the two new classes surfaced. That is
not a re-scope, and it is also not free: it means the earlier "0 findings" rounds were measuring a narrower
question than they claimed. Pass 14 therefore repeats pass 13's brief **verbatim**, which is the only way to
tell the two apart.

Both gates green at `e7c9e68b`. **Status stays DRAFT.**

## Pass 14 — the same brief, a third of the findings, and the worst one was mine

Repeating pass 13's brief verbatim was the stall-breaker's own prescription, and it did what it was
supposed to: **16 → 7**. A re-scoping loop produces a fresh crop each round; a yielding surface drains.
This one drained.

**The regression I introduced.** Pass 13's fix for "seven tickets with no red gate" was supposed to ADD a
marker gate beside each ticket's existing one. It did that for T08b, T04a, T04b and T16 (1→2, 2→3). For
**T02a, T07b and T13 it REPLACED the pytest gate instead** — the count stayed at 1, so nothing that counts
gates could see it, and the only surviving evidence was the comments I had written alongside: *"The pytest
gate above passes 164 tests today"*, with no pytest gate above. Three suites holding 14, 164 and 5 passing
tests — each proving four Behavior-Contract rows, each still named in its ticket's Touches — stopped being
executed by anything. T02a would have merged green on a coder who wrote the new name bound as a *comment*
in `agent_role.py` and left `_ROLES` untouched.

That is the same class the round was created to hunt, manufactured by the round's own fix, and it is the
argument for repeating a brief rather than declaring a class closed: **the sweep that closes a class is
also an edit, and edits belong to the next round's surface.**

**T15 was the last ticket of 33 with no red-today gate.** Scoping its docs gate in pass 13 made it
satisfiable and left it green — a fix that solved the stated problem and missed the adjacent one. It now
gates on its two actual deliverables, the Owner column in `PLANS.md` (0 today) and the reference doc
(absent today), both verified red. The repo-global `docs_updater.py --check` is demoted to a Docs step with
its reason recorded: with 123 lines of pre-existing debt in other plans, it is unsatisfiable as *any*
ticket's gate.

**Two enumerations were wrong in the direction that matters.** T09 justified KEEPing two docs with *"8 live
references from rules packs"* and *"6"* — the rules packs reference them **zero** times. The verdict
survives on 13 real dependents (11 once this plan set's own two files are excluded, the self-inflation shape
the checklist warns about), but a false reason on the delete/keep axis of a retirement ticket is how a later
reader gets a documented licence to delete something eleven files need. T03a enumerated **6 of 12**
banned-token lines; a coder working that list merges green at Merge Order 5 and the gap surfaces only at
T16's tree-wide gate at 33.

Also closed: the Pass Ledger's last row still read `(pending)` at the moment of flip; the Evidence fence's
byte figures were stale by 11–19% (the T08 pair is 284,847 B today, 22,703 **over** budget — which is why
the split was right, stated with the current number); five dangling parent IDs in live instructions; and
T04b's *"8 of 118 project plans"* named no population at all, re-derived fleet-wide as **41 occurrences
across 40 of 950 plan files in 41 repos**, bound declared.

Both gates green at `7e93639a`, with zero WARN. **Status stays DRAFT**; pass 15 repeats the brief a third time.

## Pass 15 — the third identical brief, and a blocking gate nobody had ever run

Findings went 16 → 7 → **10**. The rise is not a regression in the plan; it is the third repetition
reaching a check no earlier round had *executed*. `check_doc_links.py` was Gate 3 on all four retirement
tickets, and no pass had ever run it against the paths the plan MOVES.

**The HIGH: a blocking gate that could not pass at four tickets' merge positions.** `check_doc_links.py`
resolves bare repo-path mentions and does **not** skip `docs/orchestrator/_retired/`, so a move made at
Merge Order 21 breaks references in files owned by tickets at 25 and 30 — T11 relocates
`EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md`, cited by `docs/reference/command-evaluation-checklist.md:8`
(T14g's, at 30); T12a relocates `00-trigger-mega-epic-fabrik.md`, cited by `agents-fabrik.md` (T14b's, at
25). The coder gets an exit 1 whose only fix is a file their own `DO-NOT` forbids. Worse: **four referrers
were owned by no ticket at all**, so the check would have stayed red through T16 and past the end of the
plan.

Fixed by moving the assertion to where it can be true, not by widening it. `check_doc_links` is a blocking
Tier-2 check inside `final_gate.py:1518`, which *is* T16's Gate 1 at position 33 — so removing it from the
four retirement tickets loses no coverage at all. The referrers each move breaks are now named on the
**moving** ticket's `Docs:` line, which the orchestrator applies and which sits outside the read budget —
they total 292,956 B and would have blown it as Touches.

**The adjacent one, which the same fix exposed.** T12b's rename-purity gate forbade exactly the edit its
doc-link gate required: `awk '$2 > 0'` reads the *deletions* column, so a tombstone header (`2 0`) passes
and a content scrub (`N 1`) fails. All four rename gates now pin to the rename commit itself
(`git log -1 --diff-filter=R`), which also closes the hazard round 6 had flagged and left open — `HEAD` on
a three-session tree is whatever a sibling committed last.

**T14c could be finished exactly as written and still red T16.** Its only gate read the *rendered* CLI
hint; the banned token also sits in a source comment at `src/fabrik/cli.py:1882`. T16 owns a single file
and cannot fix the tree, so the plan would have ended red. It now carries a token gate, verified red today.

**Four counts corrected, each re-derived rather than accepted.** The Owner-line denominator drew numerator
and denominator from *different populations* — `grep -rl` over directories swept in a `.md.archive` outside
the `.md` list; it is 40 occurrences across 39 of 949 readable files (950 found, one a broken symlink).
"13 dependents each" was one file's number generalised to three (`README.md` is 8). T03a put `:153` in the
wrong token group. And two Evidence byte figures had drifted under sibling commits — one of them **seven
seconds** before pass 14's own close commit.

That last one is now annotated as expected drift rather than left to be re-raised: the figures that carry a
verdict have margins of tens of kilobytes, and a reviewer finding a few hundred bytes of movement in a file
three sessions write to should re-derive, not file. A review that regenerates the same finding every round
is measuring the tree's churn, not the plan.

Both gates green at `2bf7767b`. **Status stays DRAFT**; pass 16 repeats the brief a fourth time.

