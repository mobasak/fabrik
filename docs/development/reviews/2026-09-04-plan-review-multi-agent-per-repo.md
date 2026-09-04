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
| Pass 6 | **author-blind native pass (live repo tools)** | method: re-derivation | 34 | 34 | pending | — |

Pass 5 was edit-free and md5-stable — but pass 6, the author-blind layer, raised 34. **An edit-free own-pass is
method-stability, not truth**, which is precisely why this command forbids the author's own re-read from counting.

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

NEXT: the plan is ready for its CONVERGED flip. Five author-blind passes have now run over it; the last two found
24 defects between them, two of which were in the spec and one of which was damage I caused.
