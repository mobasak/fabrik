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

NEXT: the closing re-derivation pass, then the CONVERGED flip. The remaining MED/LOW items ride § Residual unknowns.
