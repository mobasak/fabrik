# Review — mail-handling governance + corpus diff (2026-09-10)

Status: IN-PROGRESS
Surface: 6a606972d31c771b4d746a77c9884603fd36b34f + git diff HEAD | md5sum = 8865e54cda747811edf877b987c0e689
Scope (mine, 6 paths): CLAUDE.md · templates/governance/CLAUDE.md · commands/_fragments/close-feedback.md · commands/_fragments/subagents-core.md · docs/DECISIONS.md (D-214) · CHANGELOG.md
Not mine, present in the same working tree and EXCLUDED: libs/subagents/** · docs/reference/agents/kaizen-log-*.md · docs/superpowers/specs/2026-09-10-review-family-adoption-design.md (siblings WIP)
Anchor: no prior review artifact for this scope — full WIDE pass 1.

## Partition (D-207)

| Slice | Model | Files | Why this tier |
|---|---|---|---|
| A — the two contracts | opus | CLAUDE.md, templates/governance/CLAUDE.md | fleet-synced (`templates/governance/` is a named RISKY path); a table-row break or a reworded anchor ships to ~46 repos |
| B — corpus + ledgers | sonnet | commands/_fragments/close-feedback.md, commands/_fragments/subagents-core.md, docs/DECISIONS.md, CHANGELOG.md | box-wide prose; causal claims about `dispatch_headroom.py` / `command_run.py` must be read against those scripts |

Union of the slices IS the full pass; no file read by two seats. Third angle = the orchestrator EXECUTING every candidate and refutation.

## Coverage Checklist

| # | Class | Source | State |
|---|---|---|---|
| C1 | Markdown structure — table-row integrity (a stray pipe character splits the cell), no skipped heading levels, fenced blocks only | rubric: doc/markdown floor | UNCHECKED |
| C2 | UNIVERSAL governance anchors survive verbatim (`check_governance_drift.py` parses them out of the hub file) | CLAUDE.md § UNIVERSAL governance markers | UNCHECKED |
| C3 | Every asserted NUMBER re-derived from its primary source (57/0/4/0/57, the .gitignore lines, 36/36 and 20/20 render coverage) | CLAUDE.md § denominator HARD STOP | UNCHECKED |
| C4 | Recipe truth — the three named recipes actually see ignored files in a project repo OTHER than the one measured | finding 01M25D51A9BBK44MK03G4T65TR | UNCHECKED |
| C5 | Causal claims in close-feedback.md read against `dispatch_headroom.py` + `command_run.py` (unstamped seats invisible; `--confirmed` is D-206 exit counter) | rubric: core/62-using-subagents | UNCHECKED |
| C6 | Placement — no second source of truth (READ BEFORE YOU EDIT); the subject has no existing home elsewhere in the corpus or the rule packs | CLAUDE.md § Behavior | UNCHECKED |
| C7 | Hub↔template parity — the two insertions byte-identical where claimed, and correct for ALL ~46 projects | CLAUDE.md § synced-surface HARD STOP | UNCHECKED |
| C8 | Ledger hygiene — D-214 id minted not guessed, row immutable-append, CHANGELOG `[Unreleased]` appended not reset | CLAUDE.md § decision ledger | UNCHECKED |
| S1 | STANDING: fail-open vs fail-closed on every gate/guard | standing recurrence | UNCHECKED |
| S2 | STANDING: cost/quota/limit accounting edges | standing recurrence | UNCHECKED |
| S3 | STANDING: boundary/sentinel/prefix collisions | standing recurrence | UNCHECKED |
| S4 | STANDING: behavior-without-a-test (here: a governance claim with no executable proof) | standing recurrence | UNCHECKED |

## Pass Ledger

| Pass | method | found | new | confirmed | fixed | unexecuted | finders |
|---|---|---|---|---|---|---|---|
| Pass 1 | method: citation | found: 9 | new: 9 | confirmed: 8 | fixed: 8 | unexecuted: 0 | finders: dispatched 2, returned 2 — Opus slice A (the two contracts), Sonnet slice B (fragments + ledgers); orchestrator executed every candidate and both refutations |
| Pass 2 | method: re-derivation | found: 15 | new: 15 | confirmed: 13 | fixed: 13 | unexecuted: 0 | finders: dispatched 2, returned 2 — Opus (new check + rewritten clause), Sonnet (ledgers + fragment); DELTA over pass 1's fix diff. Every asserted number re-derived from its primary source, and the two example commands EXECUTED rather than read |
| Pass 3 | method: re-derivation | found: 8 | new: 8 | confirmed: 3 | fixed: 3 | unexecuted: 0 | finders: dispatched 2, returned 2 — fresh Opus (check, tests, registration; 13 mutants executed), fresh Sonnet (clause + pending ledger; whole-table render and every command re-run live) |
| Pass 4 | method: re-derivation | found: 4 | new: 4 | confirmed: 4 | fixed: 4 | unexecuted: 0 | finders: dispatched 1, returned 1 — a fresh non-authoring Opus seat over the round-3 fix diff; it rebuilt all three mutants, re-derived both new numbers, and re-read the JUSTIFICATION text nobody had graded |

## Adjudication — round 1 (slice B returned; slice A outstanding)

Every row below was EXECUTED by the orchestrator, not taken from the seat's report.

| # | Candidate | Verdict | Proof (run here, not quoted from the seat) |
|---|---|---|---|
| B-1 | CHANGELOG's "20/20 fan-out commands the dispatch note" is a coverage claim with the wrong denominator: 30 rendered commands instruct `dispatch --seats`, only 20 include the shared fragment | **CONFIRMED → FIXED** | re-derived: `command grep -l '{{include:subagents-core}}' commands/_sources/*.md` = 20 · `command grep -rl 'dispatch --seats' ~/.claude/commands/*.md` = 30 · `comm -13` names the ten hand-inliners exactly as reported. Entry rewritten to "36 of 36 … 20 of the 30", the ten named as a pre-existing corpus defect and FILED (F4) rather than widened here. The irony is the finding: a denominator-free number inside the commit that adds a denominator rule. |
| B-9 | The new `subagents-core.md` parenthetical RESTATES the causal consequence instead of pointing at the fragment that owns it — a second place to update | **CONFIRMED → FIXED** | READ BEFORE YOU EDIT applies to my own edit. Trimmed to "(a vendored copy answering `invalid choice: 'dispatch'` is STALE, not exempt — § Close-out feedback has the class and what to do about it)". Re-rendered; 20/20 carry the trimmed form; `assemble_commands.py --check` rc=0. |
| B-2 | Placement: is the new paragraph a duplicate of `run-record.md`'s sync-excluded paragraph? | **REFUTED** | different failure modes: `run-record.md:40` covers a check SCRIPT absent from a frozen tree (remedy: run the hub copy read-only); this covers a PRESENT script whose CLI is older than the corpus (remedy: do the work, report in prose, file). Placed immediately after the `--feedback` paragraph it generalizes, same file. |
| B-3 | Causal claim (i) — unstamped seats invisible to the sibling subtraction | **CLEAN — verified in code** | `scripts/sysadmin/dispatch_headroom.py::_frame_seats` counts a record with no stamp into `unrecorded` and prints "carry NO seat figure — the box number is a LOWER bound" (this run printed exactly that line for 4 sibling sessions). |
| B-4 | Causal claim (ii) — `--confirmed` is D-206's exit counter, `--findings` the fallback | **CLEAN — verified in code** | `scripts/command_run.py::_round_report`: `counter = findings if last_confirmed is None else last_confirmed`. |
| B-5 | D-214 ledger hygiene | **CLEAN** | 216 rows / 216 ids / 0 duplicates; D-214 once, 7 pipes like D-213; `decisions.py --check` rc=1 only for trade-intelligence's pre-existing dangling pointer (another repo — routed, not edited). |
| B-6 | CHANGELOG heading grammar / section not reset | **CLEAN** | both entries match `### Changed\|Fixed — Title (YYYY-MM-DD)` and sit above the pre-existing entry. |
| B-7 | Is the instruction followable end to end in fabrik-lib? | **CLEAN** | seat walked it against their live script: `dispatch` exits 2, `round --findings` works, `done --evidence` closes; `--feedback` IS present there now, so the older paragraph's mention of it is history, not a live claim. |
| O-1 | **Orchestrator's own find:** the denominator HARD STOP row is a 2-column table row containing THREE unescaped pipes inside code spans (`git diff \| grep …` twice, `grep -c '^\| I'` once) — it parses as SIX cells, so the FIFTH, SIXTH and my new SEVENTH shapes are pushed into phantom columns that renderers drop | **CONFIRMED → FIXED** | measured before: `cells=5` on that row vs `cells=2` on both neighbours, in BOTH files, and present at HEAD (pre-existing). After escaping: `unescaped pipes in body = 1 -> cells = 2` in both. Only that row was affected — the other 8/9 multi-pipe rows are the legitimate 3-column trailers table. No script parses the row's cells (`check_rule_grounding.py:102` splits pipes for `.windsurf/rules` tables, not for CLAUDE.md), and no anchor phrase contains a pipe. |

## Adjudication — round 1, slice A (the Opus seat on the two contracts)

Every row re-derived by the orchestrator with its own command before the fix was written.

| # | Candidate | Verdict | Proof executed here |
|---|---|---|---|
| A-1 | The clause SANCTIONED `rg --no-ignore`, which un-ignores but still skips every HIDDEN directory — so it never descends `.claude/` or `.windsurf/`, the exact machinery the rule protects | **CONFIRMED → FIXED** | `/opt/web-ecommerce-factory`, pattern `check_convergence`: `command grep` **1551** · `rg --no-ignore` **51** · `rg --no-ignore --hidden` **1551** · shim `--no-ignore-files` **1551**. A 30× undercount. The governance would have CAUSED the failure it warns about. Recipe corrected to `rg --no-ignore --hidden` with the plain form called out as NOT sanctioned. This is the finding of the round. |
| A-2 | The row itself renders truncated — three unescaped pipes discard every cell past the second, so FIFTH, SIXTH and the new SEVENTH are absent from every rendered view | **CONFIRMED → FIXED** (same as O-1, found independently by both) | seat rendered it with `markdown_it-py`: 2 cells, `SEVENTH shape` absent. After escaping, re-rendered here: row contains `FIFTH shape`, `SIXTH shape`, `SEVENTH shape`, `rg --no-ignore --hidden` — all True, both files. Guarded by a new check (below). |
| A-3 | `.gitignore:180` cited as if universal | **CONFIRMED → FIXED** | census of 45 `/opt` git repos with `git check-ignore -v --no-index`: 40 ignore `scripts/enforcement/`, at **27 distinct line numbers, 67–194**; `:180` is true in exactly ONE. Clause now cites the RULE and says the line number differs per repo. |
| A-4 | `git grep` → 0 stated as general truth | **CONFIRMED → FIXED** | 3 of 47 repos carrying `.fabrik/synced.lock` TRACK `scripts/enforcement/` (ai-model-catalog 90 files, compliance-ops 79, exam-coach 79) — there `git grep` sees MORE than the shim. Clause now says tracked-only, repo-dependent, name the repo. |
| A-5 | "three surviving callers" is three call SITES in two files | **CONFIRMED → FIXED** | the cited mail lists `doc_reconcile.py:331`, `:347`, `rivals_run.py:1144`. Clause now says "three surviving call sites — in two files". A count on the denominator row. |
| A-6 | The shim is not always the shim: an output-format flag (`-Z`, `-z`, `--null`, `--*-config`) falls through to real `grep` | PLAUSIBLE → **FIXED** (folded in) | snapshot `:107-110` case-statement read directly; seat measured `shim grep -rl` 0 vs `shim grep -rlZ` 11 in transdoc. Direction is fail-SAFE (more results), so it is a completeness gap, not danger — one sentence added. |
| A-7 | C2 anchor contract | **CLEAN** | seat ran `/opt/fabrik-lib/scripts/enforcement/check_governance_drift.py` → rc=0, and instrumented its parse over HEAD vs worktree: 13 declared markers both sides, identical labels, `UNSTATED = []` both, per-anchor counts unchanged. |
| A-8 | C6 parity | **CLEAN** | inserted fragment byte-identical in both files (`frags['hub'] == frags['tmpl']` → True), correct row of the correct table, and 4 of 4 sampled project `CLAUDE.md` files md5-identical to the template at HEAD — so the commit ships verbatim to ~46 repos. |

**Two MACHINERY notes from the seat, kept because they are the trap one level down from the rule itself:**
sourcing a shell snapshot in a parent shell and then INVOKING a probe script silently loses the shims (bash
functions do not export), so the probe measures `/usr/bin/grep` and returns a plausible, exactly-inverted
result — the seat's own first run did this and it reported the opposite of the truth; and `git check-ignore -v`
prints NOTHING for a path tracked in the index, so a fleet sweep without `--no-index` misclassifies the three
tracked repos as un-ignored. Both are now in the clause's own advice or in this receipt.

## Fixes applied in round 1 (all by the orchestrator, none by a seat)

| Fix | Files | Guard |
|---|---|---|
| SEVENTH shape rewritten from a single string — recipe corrected to `rg --no-ignore --hidden`, line-number citation dropped, `git grep` claim scoped, call-sites count corrected, shim fall-through added | `CLAUDE.md`, `templates/governance/CLAUDE.md` (byte-identical, 2,184 chars) | D-216 supersedes D-214 on the recipe list; ledger rows are immutable so D-214 stands as written |
| Three unescaped pipes escaped as `\|` | both contracts | **NEW** `scripts/enforcement/check_governance_tables.py`, registered advisory in `final_gate.py`. ⚠️ Its first draft returned 1 on a finding, which `run_optional_check`'s own docstring says would HARD-FAIL the gate in every synced repo the first time it fired (`warn_only` = no failing exit path by contract; all 33 other warn_only checks return 0 on every path). Caught by the S1 standing class against my own code before the delta seats returned: `main()` now returns 0 always and `--strict` carries the regression signal. Both paths proven against a HEAD fixture in a temp root — advisory rc=0 with the finding printed, `--strict` rc=1, both files named — and rc=0 on the fixed tree, live tree never mutated |
| Coverage claim given its denominator | `CHANGELOG.md` | the number is now "36 of 36 … 20 of the 30", and the ten hand-inliners are FILED (F4), not silently absorbed |
| Point-of-use clause trimmed to POINT rather than restate | `commands/_fragments/subagents-core.md` | re-rendered; `assemble_commands.py --check` rc=0 |

## Delta round — the two open classes, swept by orchestrator EXECUTION

The class ledger from round 1 carried two open classes. Both were swept here by running the thing, not by
re-reading it; the independent non-authoring read is the delta round's two seats.

**`recipe-generalisation`** — the class is "a recipe or a measurement generalised from one repo and one
pattern" (which is how the `rg --no-ignore` defect got in). Swept across **4 repos × 2 patterns = 8 cells**,
shim sourced in the same shell that ran each command:

| repo | pattern | `command grep` | `grep --no-ignore-files` | `rg --no-ignore --hidden` | the shim |
|---|---|---|---|---|---|
| youtube | `final_gate_stop` | 11 | 11 | 11 | 0 |
| youtube | `check_convergence` | 50 | 50 | 50 | 0 |
| transdoc | `final_gate_stop` | 11 | 11 | 11 | 0 |
| transdoc | `check_convergence` | 50 | 50 | 50 | 0 |
| site-provisioner | `final_gate_stop` | 11 | 11 | 11 | 0 |
| site-provisioner | `check_convergence` | 50 | 50 | 50 | 0 |
| web-ecommerce-factory | `final_gate_stop` | 341 | 341 | 341 | 0 |
| web-ecommerce-factory | `check_convergence` | 1551 | 1551 | 1551 | 1 |

All three sanctioned recipes agree with `command grep` in every cell; the shim is blind in every cell. The
corrected list holds beyond the one repo and the one pattern it was first derived from — which is the whole
content of this class. **CLEAN.**

**`rendered-truth`** — the class is "a rule that does not survive rendering". Rendered both whole contracts
with `markdown_it-py` (`MarkdownIt("commonmark").enable("table")`) and asserted against the HTML, not the
source: all six ordinal shape markers (`Two more shapes`, `A THIRD` … `A SEVENTH`) present in the rendered
output of BOTH files; **zero** table rows anywhere in either file off their header's width; four sampled
UNIVERSAL governance anchors intact in the raw text. **CLEAN.**

**`MIRROR` (the standing contract-change class)** — does the corrected recipe now contradict anything the
fleet already reads? `command grep -rn 'rg --no-ignore\|--no-ignore-files'` over `.windsurf/rules`,
`commands/_sources`, `commands/_fragments`, `templates/governance` and `docs/reference`, excluding the new
`--hidden` form: **zero hits**. The only `git ls-files` mention in any synced file is this clause itself.
Nothing in the fleet teaches the superseded recipe. **CLEAN.**

## Adjudication — delta round, slice B (ledgers, INDEX, fragment)

| # | Candidate | Verdict | Proof executed here |
|---|---|---|---|
| dB-1 | My "127 times over 34,415 rows in 1,117 files" wallpaper figure does not reproduce — the seat measured 128 / 41,055 / 1,300 over the same six roots and could not find a scope that lands on mine | **CONFIRMED → FIXED** | re-ran my own scan both ways: with `*/archive/*` skipped → **127 / 34,493 / 1,118**; without → **128 / 41,115 / 1,301**. My numbers were right for a scope I never declared, and the two-row drift is the tree growing under me. This is the THIRD instance of the denominator class in this run and the second on my own numbers — on the commit that extends that very rule. Both the check's docstring and the CHANGELOG now carry the UNBOUNDED figures with the six roots named, and say what the earlier draft's bound was. |
| dB-2 | D-216's web-ecommerce-factory absolutes (1,551 / 51) do not reproduce — the seat measured 2,530 / 138 in the same repo, same pattern | **CONFIRMED → FIXED (framing)** | the repo is live and committed at 14:02 today; the seat's own note is that the QUALITATIVE claim reproduces exactly (`command grep` == `rg --no-ignore --hidden`, both vastly exceed plain `rg --no-ignore`, 94–97% of hits under `.claude/` in both runs). The absolutes were true at measurement and are not durable, so the clause now says "that hour" and names the ratio as the invariant. The recipe correction depends on the ratio, not the absolutes. |
| dB-3 | `CHANGELOG.md` changed under the seat mid-review (two different paragraph texts in one session) | **REFUTED as a defect, RECORDED as a hazard** | that edit was mine — the `warn_only` exit-contract correction, landed while the seat was reading. The seat re-verified the NEW text against `final_gate.py:347-374` and `:1231-1234` and found it accurate. A delta round over an UNCOMMITTED diff has no SHA to pin, which is the structural hazard; recorded rather than fixed. |
| dB-4 | E1 ledger integrity | **CLEAN** | D-216 at the top, D-214's row byte-identical between HEAD and worktree, no duplicate ids, `--next-id` → D-217, `decisions.py --check` shows only the known pre-existing trade-intelligence dangling pointer, CLASS stated, what-cell opens with the supersede, 6 cells matching the header. |
| dB-5 | E2 the gitignore census and the TRACK count | **CLEAN — reproduced independently** | 41 real git repos ignore `scripts/enforcement/` (I measured 40 — the set moves), **27 distinct line numbers, range 67–194 — exact match**, exactly **1** repo at `:180` — exact match, and "3 of 47 synced repos TRACK it" reproduces once the hub itself and sync-excluded fabrik-lib are excluded from the raw 5. |
| dB-6 | E3 CHANGELOG mechanics · E4 INDEX row · E5 the fragment trim · E6 cross-document consistency | **CLEAN** | `[Unreleased]` appended not reset and no sibling entry touched (4 removed lines, all inside my own two entries); editing an `[Unreleased]` entry in place is correct for a CHANGELOG and is NOT the ledger's immutability contract; `INDEX.md:1184` is a 2-cell row in a 2-cell table with a resolving link and `check_doc_index` green; the trimmed parenthetical points at a section that genuinely carries the class (`close-feedback.md:50-60`) rather than restating it, `assemble_commands.py --check` OK, 20 of 36 sources include the fragment; and D-214 still literally listing the superseded recipe is CORRECT — rows are immutable and D-216 supersedes that detail only. |

**dB-1 is the round's lesson and it is mine:** two independent readers of the same six roots got different
denominators because the author's scan carried a silent `*/archive/*` exclusion. The rule the commit ships
says to state the bound; the commit's own supporting figure did not. Fixed by removing the bound rather than
by declaring it, so the number a reader re-derives is the number published.

## Dogfood — the receipt had the defect it reports

Ran the new check's own algorithm over THIS file: **2 of 78 table rows** rendered off their header's width —
`| B-6 | … `### Changed|Fixed — Title (YYYY-MM-DD)` … |` (5 cells against 4) and
`| Ledger ids | parse of every `^| D-` row … |` (4 against 3). Both are pipes inside code spans, in the
document that reports the class, written by the author who had just fixed it in the contracts. Escaped; the
receipt is now 0 of 78. Kept here rather than quietly fixed because it is the measurement that says the class
is a HABIT, not an incident — which is the argument for a check rather than a rule alone.

## Adjudication — delta round, slice A (the Opus seat on the new check + the rewritten clause)

Eleven findings. Every verdict below was reproduced by the orchestrator before the fix was written.

| # | Candidate | Verdict | Proof executed here |
|---|---|---|---|
| dA-F2 | **The round-1 escaping fix broke the PRIMARY consumption path.** `CLAUDE.md` is injected VERBATIM into every agent's prompt; in GNU BRE a backslash-pipe is ALTERNATION, so the SIXTH shape's own example command went from counting 3 rows to 5, and the FIFTH shape's example pipeline stopped being a pipeline (the words became arguments, rc=0, nothing filtered) | **CONFIRMED → FIXED** | reproduced on a 5-line fixture: the original pattern counted **3**, the escaped pattern **5**; the escaped pipeline printed its own arguments and exited 0. And un-escaping re-breaks the render (`keeps 'here'=False`). Escaping and not-escaping are BOTH wrong, so the pipes are GONE: the two example commands are now phrased without a literal pipe — 0 unescaped pipes and 0 escapes in the row, all shapes present in the rendered HTML, and nothing in the raw text that mis-executes. This is the finding of the delta round: round 1 fixed one path and silently broke the other, which is the mirror class the contract names. |
| dA-F4 | The check is BLIND to a live governance table in the file it guards — `CLAUDE.md:63-72` § Orient is 3-space indented, and an `rstrip()`-only test skips it AND resets the header | **CONFIRMED → FIXED** | GFM accepts up to 3 spaces; the seat proved GFM discards that table's text while the check said OK under `--strict`. Scanner now measures indent and reads a table at `indent < 4`. Guarded by `test_indented_table_is_still_read`, proven RED. |
| dA-F5 | An unescaped pipe in the HEADER row inflates the width, so no body row can exceed it and the check is silent — while GFM renders NO table at all. Strictly worse than the defect guarded | **CONFIRMED → FIXED** | header width is now compared against its own delimiter row and a mismatch is reported in its own right. Guarded by `test_header_row_carrying_a_pipe_is_reported`, proven RED. |
| dA-F6 | False positive: a FENCED block of pipe-leading lines is not a table, and a rule about bad table rows is exactly the document that grows a fenced example of one | **CONFIRMED → FIXED** | fence state is tracked and fenced lines are skipped. Guarded by `test_fenced_example_is_not_a_finding`, proven RED. |
| dA-F7 | `python3 -OO` crashes the check — `__doc__.splitlines()` on `None`, introduced by the argparse the F1 fix added | **CONFIRMED → FIXED** | `python3 -OO scripts/enforcement/check_governance_tables.py` now rc=0. |
| dA-F1 | `warn_only=True` with `return 1` would have HARD-FAILED the gate in ~46 repos on the first sync — the seat measured **47 of 49** `/opt` `CLAUDE.md` files failing | **CONFIRMED — already fixed mid-round** | I caught the same defect independently from `run_optional_check`'s docstring before the seat returned; the seat then proved the blast radius by running the real registration against a fixture. Agreement from two directions on the highest-consequence item in the diff. |
| dA-F3 | The fix shipped with NO grader, and the docstring asserted a regression test that did not exist — FIX DIRECTIVE 4 unmet on a fleet-synced file | **CONFIRMED → FIXED** | `tests/enforcement/test_check_governance_tables.py`, 7 tests, **7 passed**; 4 of them proven RED against a neutered copy carrying the pre-fix exit code and the pre-hardening scanner (`4 failed, 3 passed`), live tree never mutated. The docstring's claim is now true. |
| dA-F8 | `51 against 1,551` names no pattern and no search root, so the pair is unfalsifiable — inside the rule that forbids exactly that. The seat tried four patterns and reproduced none | **CONFIRMED → FIXED** | the clause now names the pattern (`check_convergence`) and the root, says why (unfalsifiable otherwise), and states the invariant that survives the repo's growth: 94–97% of matches under `.claude/`. |
| dA-F9 | `93 of 723 files` drops the UNIT — the source says 723 on-disk PYTHON files | **CONFIRMED → FIXED** | source re-read at `/opt/fabrik-mail/youtube/archive/01M21TG2YAW0KFBKY25HFGV900.md:13`. Dropping the unit from a denominator, in the denominator rule. |
| dA-F10 | `40 of the 45` is reproducible only under an unstated method: 43 repos carry the rule, 3 of them track the files so it is inert, and plain `git check-ignore` is silent for a tracked path | **CONFIRMED → FIXED** | clause now gives 43 / 3 inert / 40 effective AND names the command difference. |
| dA-F11 | The clause had become a case study: 2,477 chars, two sentences pure history | **CONFIRMED → FIXED** | the review-provenance fragment and the incident narrative are trimmed to their operative halves. |
| dA-F5b | `(?<!\\)` skips a pipe preceded by a literal double backslash — a false negative GFM would split on | **RECORDED — latent** | measured 0 occurrences in either contract, and all escapes are now gone from both files. Fixing the lookbehind correctly needs escape-run counting; recorded rather than built, per FIX DIRECTIVE 5. |
| dA-D1/D2/D6 | root resolution in hub / project / worktree · registration tier, uniqueness, list semantics · the fleet MIRROR | **CLEAN** | `parent.parent.parent` resolves correctly in all three layouts, no `scripts/enforcement` symlink anywhere under `/opt`; the row is unique in `final_gate.py` and nothing keys on list length or order; and a **7,275-file** search of `commands/`, `.windsurf/`, `scripts/`, `templates/`, `docs/reference/` finds NO instruction teaching the superseded recipe. |

**Two MACHINERY notes from this seat, both real:** a delta round dispatched against UNTRACKED new code has no
SHA to pin, so the preamble's own remedy (`git show <sha>:<path>`) is unavailable — the seat improvised by
copying to scratch and reporting md5s, and a brief for untracked code should say to do that; and
`sync_enforcement_to_projects.py --dry-run` prints nothing while it runs, so a foreground dry-run is
indistinguishable from a hang (it hit the 120s Bash default).

## Round 2's two new classes, swept by orchestrator EXECUTION before the closing round

**`raw-vs-rendered`** — the class round 2 opened: a text consumed on TWO paths (rendered markdown and the
verbatim prompt injection) can be fixed on one and broken on the other. Swept by measuring both, in both
files: every shape present in the rendered HTML; **170** code spans in the hub's HARD STOPS table and **163**
in the template's, **0 of them containing a pipe**; **0** backslash-pipe escapes left in either file; and the
two example commands run correctly for real (the row-counting one returns 3 on a 3-row fixture, where the
escaped form had returned 5). **CLEAN.**

**`check-blind-spots`** — swept with a boundary matrix rendered by `markdown_it` and compared against the
check's own scanner:

| case | GFM renders a table | content lost | check fires |
|---|---|---|---|
| body-row pipe (the known defect) | yes | yes | **yes** |
| HEADER-row pipe | **no table at all** | yes | **yes** |
| 3-space indented table | yes | yes | **yes** |
| fenced example of a bad row | yes | no | no |
| under-width row (GFM pads it) | yes | no | no |
| clean table | yes | no | no |

The check now fires on exactly the three lossy cases and stays silent on the three legitimate ones. Plus
7/7 tests green, 4 of them proven RED against a neutered copy, and `python3 -OO` clean. **CLEAN.**

## RECORDED — found, not fixed, with the reason

`INDEX.md:1202-1203` — a sibling's two COMMITTED rows for `check_review_hygiene.py` carry 3 cells in a
2-cell table, so GFM drops their third cell (" | enforcement (advisory)" and " | tests") in every rendered
view. Same class as the defect this diff fixes, different file. Under § Behavior a defect in committed code
is the REPO'S, not the author's, so this is mine to fix — but it was found with two closing seats in flight
over a deliberately frozen surface, and widening that surface is exactly the re-scope the loop forbids.
Queued as F5 with its line numbers and its one-line fix. Denominator: 2 of 380 table rows in `INDEX.md`;
the two rows this diff adds are 2-cell and clean.

## Closing-round re-derivation by the orchestrator (method: re-derivation, not citation)

Every number the clause publishes, re-derived from its primary source in the closing round — the shim sourced
in the SAME shell (`type -t grep` → `function`, the trap that silently inverts this measurement):

| claim in the clause | re-derived |
|---|---|
| `command grep` 57 | **57** |
| the shim 0 | **0** |
| `rg` default 4 | **4** |
| `git grep` 0 | **0** |
| shim `--no-ignore-files` 57 | **57** |
| rooted at `scripts` 13 | **13** |
| `rg --no-ignore --hidden` (the sanctioned recipe) | **57** — agrees with `command grep` |
| 27 distinct `.gitignore` line numbers, 67–194 | **27**, `67…194`, exactly 1 at `:180` |
| 43 carry the rule / 3 inert because tracked / 40 effective | **43 / 3 / 40** |
| 3 of 47 synced repos TRACK `scripts/enforcement/` | **3** (ai-model-catalog, compliance-ops, exam-coach) |
| the recipes agree with `command grep` beyond one repo and one pattern | **8 of 8** cells across 4 repos × 2 patterns |

And the two commands the clause now describes rather than quotes were EXECUTED: the row-counting one returns
**3** on a 3-row fixture (the escaped form had returned 5), and the diff filter runs as a real pipeline.

## Blast radius, measured

47 repos under `/opt` carry `.fabrik/synced.lock`. **45 of the 47** have a `CLAUDE.md` byte-identical to
`templates/governance/CLAUDE.md` at HEAD, so the SEVENTH clause ships to those 45 verbatim on the post-commit
governance sync; the other 2 have diverged and are the project-side `check_synced_unmodified` gate's business,
not this commit's. `scripts/enforcement/` and `scripts/final_gate.py` sync with it, so the new advisory check
begins running in all 47 — which is exactly why its exit contract (advisory returns 0, `--strict` returns 1)
had to be correct before it landed rather than after.

## Why the exit contract was the load-bearing fix — measured on the live fleet

Ran the check's algorithm against every `CLAUDE.md` under `/opt` **right now**, before the sync:

```
scanned 49 /opt CLAUDE.md files; 47 would fire   (all at the pre-fix denominator row, line 222 —
                                                  line 214 in the two fabrik-lib worktrees)
hub + template, post-fix (the check's real targets): 0 findings
```

The only two that do not fire are `/opt/fabrik` (fixed here) and `/opt/fabrik-lib` (hand-maintained, no such
row). Every other project still holds the OLD template, so they carry the defect until the governance sync
delivers the fixed one — and the check ships in the SAME sync as the fixed template, so the steady state is
clean. But the transient is real, and with the first draft's `return 1` under `warn_only=True` that transient
would have been a **hard gate failure in 47 repos**, with a message blaming the registration rather than the
table. Advisory-returns-0 turns the same 47 into 47 warnings that vanish on the next sync. That is the whole
argument for the exit contract, and it is a measurement rather than a worry.

## The D-216 id, and why it is not the one `--next-id` prints

`--next-id` now returns **D-220**: siblings minted D-217, D-218 and D-219 while my D-216 row was reverted out
of the tree by their commit. D-216 itself is FREE (`grep -c '^| D-216 |'` → 0) and unreferenced by anyone
else, and it is the id the CHANGELOG entry, this receipt and the commit body already name. So the row keeps
D-216 rather than jumping to D-220 — a HOLE is harmless to `decisions.py --check`, which forbids duplicates
and dangling supersede pointers, while a renumber would have to be chased through four artifacts. The payload
re-asserts `"| D-216 |" not in file` immediately before it writes, so a sibling taking 216 in the meantime
aborts the apply rather than colliding.

## Adjudication — CLOSING round, slice A (fresh Opus seat on the check, its tests, and the registration)

| # | Candidate | Verdict | Proof executed here |
|---|---|---|---|
| cA-F1 | **BLOCKING** — the `final_gate.py` registration comment restates `127 times in 34,415 rows`, a figure the co-located check's own docstring RETRACTS as an undeclared-bound scan; neither number reproduces under either bound, and the comment states no file denominator at all. In a file that syncs to ~46 repos | **CONFIRMED → FIXED** | the seat's own wide scan: 1,301 files / 40,290 rows / 125 fires with archives, 1,010 / 30,257 / 114 without — file count matches the docstring exactly, rows and fires within ~2% (a tree three sessions are editing). Fixed the way the seat proposed and the way the doc-script coupling rule demands: the comment no longer restates the number at all, it POINTS at the docstring as the single source. The docstring's figure is now dated. A comment restating another file's values is the drift class itself, and this one had gone stale against the docstring beside it within the same hour. |
| cA-M | **8 of 13 mutants SURVIVED the tests** — the grader bound less than the fix depends on. The three that matter: `_TARGETS` reduced to the root contract (the FLEET-SYNCED half silently unscanned), `_root()` returning the wrong directory (prints `SKIPPED`, returns 0, i.e. a permanently GREEN advisory row in every synced repo), and the advisory losing its `file:line` (for a warn_only check the stdout IS the product) | **CONFIRMED → FIXED** | three tests added and each proven to KILL its mutant: `_TARGETS` mutant now **2 failed** (was 7 passed), `_root()` mutant **1 failed** (was 7 passed), file:line mutant **3 failed** (was 7 passed); live suite **10 passed**. `_root()` had ZERO coverage because every other test monkeypatches it — that is the gap that would have shipped a green check that reads nothing. |
| cA-F3/F4/F5/F6 | Latent classes in the row predicate: fence-state inversion (nested/4-backtick/indented fences), tab-indented pipe lines read as tables, GFM tables without outer pipes, and two pipe-lines with no delimiter row firing as a false positive | **RECORDED — latent, zero live occurrences** | the seat measured the whole population of 50 contracts: tab-indented pipe lines **0**, `~~~` fences **0**, 4+-backtick fences **0**, outer-pipe-less delimiter rows **0**, lone `\|` lines **0**; and on the 302 real fence lines the tracker is BYTE-EXACT against markdown_it's own spans (0 code lines scanned, 0 prose lines skipped, state closed at EOF). Building for a class with no live instance is the wallpaper the FIX DIRECTIVE forbids; queued instead. |
| cA-P1 | No read-error guard: an unreadable contract raises and `run_optional_check` then blames the registration ("drop `warn_only=True`") rather than the OSError | **RECORDED — pre-existing, shared by all 34 warn_only checks** | the misleading wording is not this check's; it is `final_gate.py:395-398` and it fires for ANY non-zero exit including a crash. Filed as machinery rather than patched here — fixing it inside one check would leave 33 with the same face. |
| cA-G2/G4 | The exit contract end to end, and fleet safety | **CLEAN — both measured** | through the gate's OWN call path on a finding: `passed=True` with the advisory text; on a CRASH: `passed=False` with the traceback preserved (so a broken check is loud, not silent). Fleet differential over all 50 live contracts with markdown_it as ground truth: **0 fire-only rows, 0 lost-only rows** — precision and recall both 1.0. Recall against the real historical defect: `git show HEAD:CLAUDE.md` loses row 250 and the check reports exactly `(250, 5, 2)`. |
| cA-G5 | fail-open/closed edges · cost · boundary/sentinel | **CLEAN** | missing file, a DIRECTORY where the file should be, invalid UTF-8, CRLF — all handled; no `walk`/`glob`/`rglob` in the source, exactly `len(_TARGETS)` opens, ~0.17 s per run; `_DELIM` correct on alignment colons and padding; a bare `\|` excluded; an escaped pipe in a body cell correctly does not fire. |

**And the remedy the rule prescribes was itself verified**: a cell written as an escaped pipe inside a code
span renders as a proper table with the literal pipe intact, and the check goes quiet on it. The advice is
executable, not just plausible.

## Adjudication — CLOSING round, slice B (fresh Sonnet seat on the clause and the pending ledger)

| # | Candidate | Verdict | Proof executed here |
|---|---|---|---|
| cB-1 | **"3 of 47 synced repos" — the denominator 47 matches NO population the seat could derive**: the sync tool's own count is 45 projects, 45 git repos exist under `/opt`, and the document says "~46" in four other places. A fourth unexplained exact number for the same population, in text injected verbatim into every agent's prompt | **CONFIRMED → FIXED** | re-derived all three: `.fabrik/synced.lock` present → **47** · `sync_enforcement_to_projects.py --dry-run` → "Found 45 projects" · `/opt/*/.git` → **45**. So 47 is REAL but was the lock-carrying population and the clause never said so — which is the defect the clause itself defines. Now reads "3 repos (of the 47 carrying `.fabrik/synced.lock`)", and adds "name the repo AND the population you counted". |
| cB-2 | "27 different `.gitignore` line numbers" is stale — live measurement gives 28 | **CONFIRMED → FIXED, by removing the number** | re-derived with two different probe paths, both → **28** distinct values, range **67–194**, 43 occurrences. My 27 was measured 40 minutes earlier: an exact distinct-count over a live fleet is unstable by construction, while the RANGE is stable under both probes and IS the point (the line differs per repo, so cite the rule). The clause now gives the range and drops the count. Third time this run that an exact count over a moving population needed correcting — the lesson is structural, not arithmetical. |
| cB-3 | The whole HARD STOPS table's render/execute parity | **CLEAN — measured over the whole table, not just the row** | zero literal pipes inside any code span anywhere in the table; zero `\|` escapes left in either file; markdown_it renders 1 header + **22 data rows 1:1** with the reviewed row at exactly 2 cells and its ~6.5 KB of prose intact. And both anti-patterns the FIFTH and SIXTH shapes DESCRIBE were reproduced on fixtures — the diff filter really does drop added bullets, and the row-count really does over-count by the header — so the rephrased prose still describes a real failure. |
| cB-4 | Every SEVENTH-clause number, re-run live | **CLEAN** | the six `/opt/youtube` numbers match exactly (57 / 0 / 4 / 0 / 57 / 13); `rg --no-ignore --hidden` returns the full **57**, confirming the corrected recipe is correct and not merely plausible; real `/usr/bin/grep --no-ignore-files` errors and reads as a silent zero, as claimed; the web-ecommerce-factory absolutes moved (139 / 2,531) while the `.claude/` ratio landed at **94.4%**, inside the clause's own stated 94–97% band — the hedge held. |
| cB-5 | The pending ledger payload | **CLEAN** | D-216 is 7 pipes / 6 cells matching D-214's structure, opens with the supersede, states CLASS, and its recipe description matches the LIVE clause in substance; `D-216` is absent from the ledger (a genuine gap between D-215 and D-217) so no collision despite three sibling mints since; the CHANGELOG anchor is present exactly once byte-for-byte, so the payload's `elif` branch fires; and neither entry still claims the pipes were "escaped". |
| cB-6 | "93 of 723 on-disk Python files" · the shim's output-format fall-through | **RECORDED — unvalidated by this seat** | the seat could not reproduce 723 with its own bounded search and said so rather than calling it wrong; the citation traces to fabrik-lib's own finding, and an earlier seat in this review DID read the source line and confirm the figure and the unit. The fall-through was read directly from the snapshot's case-statement by the round-2 Opus seat. Both stand on another seat's execution, and the receipt says so rather than implying I re-ran them. |

**The through-line of three rounds:** every defect that survived to be found was a NUMBER — a recipe generalised
from one repo, a bound never declared, a denominator never named, an exact count over a moving population, and
a comment restating another file's figures. Not one was a logic error. The rule this commit extends is the
right rule; obeying it while writing it is the hard part, and the review is what made that visible.

## Shared-tree events during this run

- **A sibling's pathspec commit swept two of my six paths before I could commit them.** `338c96d7`
  (`docs(spec): review-family adoption of D-203`, Agent-Role: primary, 13:43:34) carried my D-214 row and
  both of my `[Unreleased]` CHANGELOG entries along with its own D-213 row, because `git commit -- <paths>`
  reads the WORKING TREE for those paths. Content is safe and pushed (HEAD == origin/master == `88a800a7`);
  what is wrong is ATTRIBUTION, and history is not rewritten for it (§ HARD STOPS: never `--amend` on a
  shared tree). My commit therefore carries the four authored files only and says so in its body. This is
  the class youtube already filed (`01M1RHJEYEMV2XY5CSGZ547KVX`, "explicit pathspecs do NOT prevent
  bundling a sibling's work") — CITED, not refiled.
- Consequence for the reviewers: `docs/DECISIONS.md` and `CHANGELOG.md` are now CLEAN against HEAD, so
  slice B's B4/B5 classes are graded against `git show 338c96d7`, not against a working-tree diff.

## Orchestrator mechanical sweep (round 1, no Haiku seat dispatched — these classes are the script's)

| Check | Command | Result |
|---|---|---|
| Command corpus integrity | `python3 scripts/enforcement/check_command_corpus.py` | rc=0 — "all sound across 63 file(s) read" |
| Corpus render parity | `python commands/assemble_commands.py --check` | "check OK — installed commands + skills match rendered sources" |
| Completion gate (read-only) | `python scripts/final_gate.py --check --json` | `status: success`, failed 0, blocking 40, `skipped_checks: ['pytest']` (hub leg off by design) |
| Ledger ids | parse of every `^\| D-` row | 216 rows, 216 ids, 0 duplicates; D-214 present once, 7 cells, same shape as D-213 |
| Ledger integrity (fleet-wide) | `python3 scripts/decisions.py --check .` | rc=1 — ONE defect and it is NOT mine and NOT this repo's: trade-intelligence's D-007 supersedes a D-048 row absent from THEIR ledger. Cross-repo: routed, never edited from here. |

## Method defect caught in-run (recorded, not hidden)

The rubric first embedded here was produced with `python scripts/review_rubric.py --changed <paths> | tail -60`.
The real output is **154 lines**; the tail bound dropped **94 of them (61%)**, including the
`# REVIEW RUBRIC … generated by review_rubric.py` header the grader's `RUBRIC_RUN` regex anchors on and the
mandatory-core FLOOR mandates. The finders were armed from the hand-written hazard classes in their briefs,
so recall was not lost — but the artifact quoted a truncated rubric as if it were the whole one. Re-generated
without the bound and re-embedded below. This is the FOURTH shape of the same HARD STOP the diff extends
(`tail` is a bound wearing the opposite mask), committed by the author of the SEVENTH shape in the same run:
the rule is right, and knowing it is not the same as obeying it.

## Rubric (verbatim, `python scripts/review_rubric.py --changed <the 6 paths>` — full 154 lines, no bound)

```
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: an error-open helper turns one bad/empty JWT into a full cross-tenant read. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: `postgres:16-alpine`, `plpgsql` only); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project and per-tenant isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- VOLUME gets a plan pointed at a directory that never exists — a paper backup that reads green and archives nothing. *Measured: `/opt/zitadel/data` is absent while the `zitadel-data` plan points at it.* If the data is a volume, say so in the spec comment and rely on the global `docker-volumes` plan; never let a service-named plan be mistaken for the protection.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout. *Measured: trytond bakes an init script but sets no `command:`, and its base entrypoint is a bare `exec "$@"`.* An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency (web-ecommerce-factory 01M1Q8X9, 2026-09-05).
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (2026-09-01: `postgres:16-alpine` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- > sees a file that looks exactly like a migration step, and ships a deploy where migrations never run —
- > the rule producing the very defect it exists to prevent. Do not re-add either without a `path:line` in
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/40-documentation.md  (hit: CHANGELOG.md, CLAUDE.md, commands/_fragments/close-feedback.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/62-using-subagents.md  (hit: commands/_fragments/subagents-core.md)
- GOAL: One place that says which subagent runtime to use, what tools it gets, what NEVER goes to a subagent, and how tool access is a single-source change. AGENT USAGE: When a command dispatches subagents, pick the runtime + the tool scope from here. Design authority: docs/superpowers/specs/archived/2026-07-07-subagent-tool-parity-design.md (Claude Code side) + fabrik-lib subagents/PROPOSED_RULE-using-subagents.md + its 2026-07-07-subagents-mcp-client-design.md (pool side). -->
- > **⚠️ STATUS — POOL OFF (D-181, operator, 2026-09-07).** Runtime B (the OpenRouter pool) is OFF by ruling; its credentials stay provisioned (D-182), so this pack and the gate are the control. Every fan-out runs Runtime A (native Claude Task subagents); the pool sections below are kept in `<!-- POOL OFF -->` comments for re-enable. Binding detail: § Dispatch policy.
- Two runtimes dispatch subagents; each scopes tools differently. **Never restate tool lists in a command brief — the access lives in the agent-type file (Runtime A) or the `AgentSpec` (Runtime B).**
- **B — fabrik-lib `subagents` pool** — **OFF by ruling since D-181 (2026-09-07; mechanism revised by D-182 — the credentials stay provisioned, so a dispatch would still spend: do not call it).** (OpenRouter-API models, sandboxed worktree). Not Claude; tools = the module's `web_tools` (Exa/Firecrawl/Context7/Brave HTTP) + `mcp_servers` (MCP client) + `allowed_commands`. **No browser** — GUI work never routes here.
- **Safe-server allowlist (fail-safe):** research servers `exa`/`brave-search`/`firecrawl`/`context7` are default-on; **FS/shell/exec MCPs are refused** unless `allow_unlisted=True`; **browser MCPs are opt-in** on a capable host only — never default-on the pool.
- **Keys via the process env** (`EXA/FIRECRAWL/CONTEXT7/BRAVE_API_KEY`) — same model as `web_tools`; the hub provisions them into the pool env (`/opt/fabrik/.env` on WSL, deploy env on VPS). Never inline a key.
- The pool is a **rule, not a roster: `pick_models(task_type)` returns the flywheel-ranked models for the task, best-first — take the top that clears your bar.** **Name no model rosters or per-stage rankings in this pack** — they are the flywheel's *output* and live in ONE place: the module's vendored `_TABLE` (fallback seed) + the synced per-task table **`/opt/fabrik/docs/reference/kilo/TASK_SUBAGENT_SELECTION.md`** — one `### <task_type>` section each (`code · docs · plan · research · review · spec`), rows ranked by real recorded runs (`shrunk_q · success · avg_cost · n`; `[benchmark]` = a never-run candidate). `pick_models` **auto-reads that hub doc** (`_HUB_SELECTION_DOC` in `select.py`, overridable via `SUBAGENT_SELECTION_DOC`) and prefers its empirical order over `_TABLE`. Copying any model name into this pack is the drift this pack exists to avoid.
**Select with `pick_models(task_type, …)` — never hand-pick, never name a model in prose.** It returns the flywheel-ranked pool best-first (`prefer="value"` biases toward cheapest-that-clears-the-bar; `exclude=` drops a model). **No `anthropic/*` via the pool** — Claude is subscription-native; use the `fabrik-reviewer` Claude Code subagent, not the pool. Don't invent OpenRouter IDs — verify any ID against the table, not memory.
- **Close the flywheel loop (every *pool* dispatch):** `pick_models(task_type)` → judge the run → **`record_agent_run(spec, result, quality_score, project=<name>)`**. Via `fanout` the dispatch half is automatic (recorded UNSCORED) — your judgment lands with `set_quality`. ⚠️ `record_run(result, …)` on a raw `AgentResult` **silently no-ops** (it wants a dict; `model`/`task_type` live on the *spec*) — always `record_agent_run(spec, result, …)`. Fleet runs → `subagent_runs` → per-task aggregation → **`TASK_SUBAGENT_SELECTION.md`** → sharper `pick_models` next time.
- **⚠️ Keep the sources aligned:** the module's vendored `_TABLE` (fallback seed) and the flywheel-refreshed `TASK_SUBAGENT_SELECTION.md` (which overrides it via `_HUB_SELECTION_DOC`/`SUBAGENT_SELECTION_DOC`). **This pack lists NO models and NO price literal — only the mechanism — so it can never be the source that drifts.**
**⚠️ THE OPENROUTER POOL IS OFF — operator ruling D-181 (2026-09-07), OFF BY POLICY (D-182 revised the mechanism: the credentials stay provisioned, so a `fanout` would still dispatch and spend — this pack is the control; intel monitors `fabrik_analytics.subagent_runs` for any dispatch).** Until the operator re-enables it: **every fan-out a command names runs NATIVE (Runtime A)** — `fabrik-reviewer` / `fabrik-researcher` / `fabrik-gui` / general-purpose — with the SAME unit split, the SAME author-blind rule (§ Role separation) and the SAME decide/refute/merge you own. Nothing records to the flywheel (a native seat has no `AgentResult`) and nothing is scored; `scripts/enforcement/check_subagent_flywheel.py`'s pool-or-declare layer stands down by the same ruling (`_POOL_POLICY_ON = False`, D-182), so **no `NO-POOL:` declaration is owed**. Native sizing has TWO shapes and the command picks by kind. **PARTITIONED — the two review loops (`/fabrik-review`, `/fabrik-repo-review`; D-207, on the operator's ruling D-203):** the surface is cut into DISJOINT slices by file, the union of the slices IS the full pass and no file's logic is read by two seats — **Opus on the RISKY units only** (concurrency and locks, record and file formats, fleet-synced paths — `scripts/enforcement/`, `scripts/command_run.py`, the hooks, `templates/governance/` — auth, schema, migrations, secrets; a surface with no risky unit still gets ONE Opus seat over its most consequential slice, carved OUT of Sonnet's allocation, never added to it), **Sonnet on every other code and doc unit**, **at most ONE Haiku seat** across the whole surface — for a judgement-shaped inventory class the close-out hygiene script cannot express, and only when the brief NAMES it (the scriptable classes — stale phrases, table and fence shape, dead symbols, `{{` residue — are the script's from round 1's start, never a seat) — and **Fable** (Opus BY NAME when Fable refuses) orchestrating: it partitions, dispatches, adjudicates and EXECUTES every refutation and every confirmed reproduction, never a finder. Size it with `python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --slices opus=N,sonnet=N,haiku=N` (SEATS = Σ slices against the same CLI/box/quota caps, NO floor padding; the kinds are exactly `opus`/`sonnet`/`haiku` — a `fable=` kind, a negative count or a repeated kind is REFUSED, exit 2) and stamp it BEFORE dispatch with `python3 scripts/command_run.py dispatch --seats <n>`. **Round 1 is the ONLY full pass; every round ≥ 2 is a DELTA round**, and its surface is COMPUTED, not judged: `git diff <last round's commit>..HEAD -- <the review's surface>`, plus one hop of callers and callees (grep the changed symbols, or `find_referencing_symbols` where the language server is up), plus the tests that import a changed module, plus any sibling commit that landed on the surface since the last round. The class ledger PERSISTS across rounds: a delta round sweeps the classes its diff touches and CITES the rest as standing-clean from the last full pass, and the receipt says which — a round is never a re-scope. **A delta round that dispatches NO finder seat may not close the loop:** the fix diff is the orchestrator's own work and § Role separation binds, so the closing delta round always carries a fresh, non-authoring seat over that diff (Opus if any hunk is risky, else Sonnet); the hygiene script and the orchestrator's own execution never close a review alone. **Quiet is zero CONFIRMED code or doc defects (D-206), never zero raised:** a candidate becomes CONFIRMED only when the orchestrator REPRODUCES it (probe, failing test, or a mutation on a pinned copy), and REFUTED only when it EXECUTES the refutation and the receipt row cites that command and its output; a candidate neither reproduced nor refuted is `RECORDED — unexecuted (<why>)`, one reproduced and kept on purpose is `RECORDED — by design (<owning row>, round N)`, and RECORDED and REFUTED rows never reopen the loop. The Pass Ledger row states the counters in that order — `found: F, new: N, confirmed: C, fixed: X, unexecuted: U` — and the loop closes on `confirmed: 0, fixed: 0` with `unexecuted: 0` or none — a round that FIXED something is never the closing row. **UNITS-SIZED — every OTHER command:** per INDEPENDENT unit of the surface — failure class · file · screen · doc · pack · journey · fact · behaviour — a Sonnet breadth seat plus a Haiku mechanical seat, all dispatched in a SINGLE message so they run in parallel, plus the Opus authoritative seat(s): a 3-unit surface with a mechanical angle is 7 seats (4 with `--mechanical 0`), never a token 1–2 (the executable number is (1) below). The CAP is independence OF THE SURFACE, not of the reader — partition so no unit's ground truth is another's; a unit you cannot brief distinctly is not a seat. ⚠️ **NEVER solo, never two — the FLOOR is three seats for every command that is NOT one of the two partitioned review loops (D-208):** `/fabrik-review-scoped`, the grounding and adjudication commands (`/fabrik-plan-review`, the researcher floors) and the sweep and audit reviews (`/fabrik-spec-review` renders the units-sized review floor, not a grounding one). Under a partition the floor stands DOWN — it is satisfied by construction, since every non-empty slice kind already keeps its own seat, and the third angle there is the orchestrator's EXECUTION of every candidate rather than a third reader. Where it applies, a surface with fewer than three units still dispatches THREE seats on DIFFERENT angles over it: measured, not assumed (1 seat found 0; 3 over the same surface found 0/5/0, and the 5 held a real fail-open two self-sweeps had read past). (Deliberate DUPLICATE briefs over one small surface are a different, measured technique — `/fabrik-review-scoped` § floor: 1 seat found 0, 3 seats sharing one brief found 0/5/0 and the 5 held a real fail-open. They buy sampling variance, not coverage, and are budgeted as ONE unit.) ⚠️ **Dispatch economics — five constraints, ONE executable number (D-189, operator 2026-09-08: *"maximum count of viable and useful subagents … utilize the box capacity properly, do not cause OOMs, finish fastest with affordable token usage, and utilize proper claude models such as fable, opus, sonnet, haiku"*).** EVERY partitioned review loop runs `python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --slices opus=N,sonnet=N,haiku=N` before it dispatches, however small the partition — sized at Σ slices with NO floor padding. A units-sized surface runs `--units <N> [--heavy] [--risky <R>] [--mechanical <M>]` before any fan-out wider than the floor and dispatches the `SEATS:` it prints — `min(units × angles + the Opus seat(s), CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=20, box_cap, quota_cap)`, never below 3 unless a hard cap binds or the fleet is on HOLD; a floor-sized units fan-out (1 unit = 3 seats = the floor) needs no script — stamp its three seats with `dispatch --seats 3`. (1) **Maximum (D-191 — the operator's third statement of it)**: the BOX is the ceiling and the units are the PARTITION. Every unit gets one seat per ANGLE — a Sonnet breadth seat and a Haiku mechanical seat — plus the Opus authoritative seat(s), one per risky unit and at least one (a risky unit therefore carries THREE angles: authoritative, breadth, mechanical — cost 8); `dispatch_headroom.py` computes that as the WANTED count and trims it to what the box, the CLI cap and the quota allow for maximum unit COVERAGE — Haiku first, then the extra Opus seats, then Sonnet, never the last Opus seat. **The mechanical angle is grep-shaped and therefore GLOBAL:** `--mechanical <M>` is the number of grep-able classes the surface HAS (inventory · naming · format · links/anchors · counts); when the budget trims below one Haiku seat per unit, each remaining Haiku seat sweeps ONE class across every unit; and a grounding or adjudication surface has no mechanical angle at all (`--mechanical 0`) — a Haiku seat briefed on a judgement returns a claim you must refute, which is spend without recall. A 3-unit surface on an idle box is 7 seats, not 3; before D-191 the rule capped at the unit count while the box allowed 23. Dispatch ALL of what it prints, in ONE message, each seat a distinct unit × angle brief — and when the COST line says TRIMMED, dispatch the trimmed mix, never the per-unit sentence. (2) **Box, no OOMs**: a native seat runs inside its parent `claude` process, so its memory is its TOOL subprocesses — and a "read-only" finder still runs pytest through Bash (measured 2026-09-08: 1.19 GB max RSS), so the box bound applies to EVERY seat: 2 GB planned per `--heavy` seat (pytest/build/render), 1 GB per read-only seat, against `min(MemAvailable, CommitLimit − Committed_AS)` and one core per seat, MINUS the seats sibling sessions DISPATCHED in the last 25 minutes (`command_run.py dispatch --seats <n>`, stamped BEFORE the seats go out and accumulated within the round — a `round --seats` written at the round's close reserved nothing while the seats ran; measured 2026-09-08 on 245 seat transcripts: median 550 s, p95 1354 s; the caller's OWN record is never subtracted) — three sessions cannot each take the whole box in the same minute, but siblings RESERVE, they never starve: a session always gets the floor the box physically has room for. The floor never overrides a hard cap: a box with room for two seats gets two, with the reason. Measured on this box: 24 cores, 47 GB, ~25 GB available with 9 sessions up ⇒ 12 heavy seats. (3) **Fastest**: every seat in ONE message (parallel), never one message apart; keep working while they run. ⚠️ Measured cost of D-191 on this axis (2026-09-08, n=95 completed seats of THIS session's reviews since 09-07 timed on their own transcripts — first to last line; median 446 s, p90 832 s — the typical round; the reservation window in (2) uses the wider n=245 across every account's seats, median 550 s, p95 1354 s, because a reservation must cover the tail, a barrier estimate the typical seat; bootstrap of the round barrier = max of its seats): 3 → 7 seats is **+28 % wall-clock per round** (763 s → 976 s), 6 → 13 is +23 % (an earlier +31 % came from the old synchronous shape's last-turn durations, the same instrument D-193 retired for tokens); and the ledger says round-1 findings predict MORE rounds (r = 0.672, n=36). ⚠️ And the seats are NOT cheap: measured on their OWN transcripts (`<sid>/subagents/agent-*.jsonl` — the parent's result line carries one turn, 10× under), one review's 21 seats billed 69.5M input against the orchestrator's 35.7M — seats ≈ 195 % of the orchestrator's spend AT THE ROUND BOUNDARY (before the orchestrator read their reports; ~150 % once it had — the ratio is a curve, the stable figure is ~3.3M billed input per seat); a 13-seat round is ~43M ≈ 1.4 quota points at ~30M per point. D-191 roughly TRIPLES a run's tokens: "maximum" is paid in tokens AND per-round wall-clock, the quota band in (4) is the guard that bounds it, and the tripwire below (rounds) plus the ledger's `tok_seat_*` columns (cost) are what say whether it was worth it — the operator holds that judgement with the number in front of them. (4) **Affordable**: native seats are subscription quota shared by five accounts, three hub sessions and ~46 repos — at ≥85% on the active account's hottest window (the picture's own `in_drain_band`) the round runs at the FLOOR and sweeps the remaining units NEXT round; with no COOL standby the round still runs but the script names the risk ("0 of N standby(s) are COOL" — every fallback is itself in the band — or "NO standby account at all"), so keep the seats proportionate to the active window; on the fleet HOLD it dispatches nothing. (5) **The right model per ROLE** — and the MECHANISM is the one-token per-dispatch override, `Agent(subagent_type=…, model="opus"|"sonnet"|"haiku"|"fable")`: `fabrik-reviewer` defaults to Sonnet and `fabrik-researcher`/`fabrik-gui` inherit, so a role stated without the token IS Sonnet, authoritative pass included. The four names, one job each: **Fable** = orchestrator/adjudicator and the final validation's authoritative seat (substitutes for, never adds to, the Opus seat there; never a routine finder, never a coder) — ⚠️ **Fable is METERED usage credits, not a subscription window** (the CLI bundle: "Fable 5 requires usage credits"; the quota probe cannot see it): check availability before a run that needs it, and a Fable seat that refuses falls back to Opus BY NAME with the fallback recorded, never silently · **Opus** = the authoritative pass — its RISKY slices under a partition, ≥1 seat on every review — and design-heavy never-route coding · **Sonnet** = breadth, one seat per independent unit, and the default never-route coder · **Haiku** = every unit's mechanical seat (grep-able classes, format, inventory), never codes. GUI stays `fabrik-gui`. Model is chosen by the seat's JOB, never by what is idle. **Price multipliers (operator ruling D-190, 2026-09-08): haiku 1× · sonnet 2× · opus 5× · fable 10×** — "affordable" is a NUMBER, `cost = Σ seats × multiplier` in haiku-units, and `dispatch_headroom.py` prints it (`--mix opus=1,sonnet=5` → 15). Breadth on Sonnet costs 2 per seat; the same seat on Opus costs 5, so an Opus breadth seat costs 2.5× a Sonnet one — whether it buys more recall is UNMEASURED (the D-186 tripwire ledger, with `--seats` recorded, is where that answer will come from), and until it is measured the default is the cheaper seat; a Fable adjudicator costs 10 and is one seat per run, never per unit. The default mix is the script's `full_mix` (D-191): one Opus authoritative seat plus one Sonnet AND one Haiku seat per unit; risk-bearing units (auth/schema/migrations/secrets) each get their own Opus seat (`--risky N`), and when a cap binds the cheapest angle is trimmed first — Haiku, then Sonnet, never the last Opus seat; the `/fabrik-review-scoped` floor is one unit, i.e. the script's 3-seat answer. The number is RELATIVE and dimensionless — it assumes equal tokens per seat, and the orchestrator's own reading (at its own multiplier, growing with every seat's report; the ledger's median run reads 37.4M tokens on the orchestrator's transcript (n=31 rows), ~80M/hour just existing) is NOT counted — and the seats' own reading is larger still (~3.3M billed input per seat on its own transcript; ~30M tokens per quota point measured 2026-09-08, so a 13-seat round is ≈ 1.4 points): the quota band guards the seats, and nothing yet guards the orchestrator's own reading; the Fable adjudicator is one seat per run at 10, printed beside the seat total, never inside it. ⚠️ The quota band of (4) is a SEAT band by design and cost stays advisory until `round --seats` rows let the band be re-cut in cost — three Opus seats (15) cost more than six Sonnet (12), and the band cannot see that yet. **And record what you dispatched** — `python3 scripts/command_run.py round --seats <n> …` — because the D-186 tripwire is evaluated with seats unknown on every row that omits it (0 of 97 rounds carried one when this was written). The ledger's token columns now include the SEATS' own usage (`tok_seat_*`, summed from each seat's OWN transcript under `<sid>/subagents/` — synchronous and background seats alike; the parent's result line carries one turn, 10× under, and a background launch none, so the two earlier instruments saw 0 % and then one turn of seat spend), so the tripwire has a cost leg: findings per 100K seat-tokens per run, falling while seats rise, is the manufactured-seat signal. **Dispatch them together and keep working while they run** — measured across the 37 agent-closed runs in the feedback ledger, wall-clock tracks ROUNDS (r = 0.937 over the 32 rows that carry a round count; median **6.7 min/round**, and bimodal — 3.2 scoped vs 10.5 heavy, with only 6 of 32 within ±20% of any single figure). ⚠️ Two honesty bounds on that: 5 further rows record 0 rounds and carry 31% of all measured wall-clock, so the model does not cover them (r falls to 0.638 over all 37); and the ledger has **no seat-count field**, so "seats do not drive wall-clock" is an INFERENCE, not a measurement — `command_run.py round --seats <n>` now records it so the next audit is not blind; blocking on a single seat is how one round becomes twelve minutes of nothing. ⚠️ **The payoff claim is a HYPOTHESIS under test, not a measured result:** in the same ledger, more findings in round 1 predicts MORE rounds (r = 0.672, n=36 — the same figure as (3)) and more wall-clock (r = 0.648, n=37), and `check_ticket_breadth.py` carries a measured `rounds ≈ 1.0 × risk-class count` model — so a wider round may converge slower, not faster. TRIPWIRE (re-based at D-191 — the 20 rows count from 2026-09-08, and the variable that changed last is per-unit-per-ANGLE sizing, not per-unit): if `/fabrik-review`'s median rounds rises above 4 (the median before D-186/D-191, n=9) over the next 20 ledger rows, seat inflation is inflating convergence and the rule reverts to a per-round class budget. ⚠️ **The unit count is what the SURFACE HAS — the rule scales itself and is not a quota to spend:** a one-file diff in a small synced project yields one or two units, not eight, and only the AUTHORITATIVE seat is Opus (breadth is Sonnet, the mechanical seat Haiku) — so the spend is bounded by the UNIT count (one unit = 3 seats = 8 haiku-units), never by how idle that project's box looks. That is what reconciles this with the standing quota line — native seats bill one shared subscription across ~46 repos, so more units means more seats, and a padded unit list means a wasted account. ⚠️ Do NOT "turn the pool off" by emptying `TASK_SUBAGENT_SELECTION.md` — `pick_models` falls through an EMPTY section to the unrestricted vendored `_TABLE` (40 models incl. ones the operator removed under D-159/D-168); under D-182 the only lever that refuses is this text (the credential is provisioned). The pool-default contract is kept below, commented, so re-enabling is an uncomment, not a rewrite.
**The OpenRouter pool is the DEFAULT worker for gradeable text/code fan-out** — review finders, repo-review unit reviewers, doc reconcilers, rules-pack auditors, spec/plan research grounders, code implementers. **Route it through `fanout(task_type, units, *, repo, project, mode="read_only"|"write")`** — where **`repo=` is the project ROOT as an absolute path** (e.g. `repo="/opt/job-agent"`, NEVER a bare name: `repo="job-agent"` called from inside the repo silently nested every ledger/env path under `<root>/<name>/` until the module learned to refuse it — the flywheel rows recorded there were invisible to the gate) — the one-call helper that selects via `pick_models` (flywheel-ranked, NO default price cap; **family diversity is BEST-EFFORT, not a guarantee** — `agent.py` reorders the draw distinct-family-first, but it can only diversify across what `pick_models` RETURNS, and the operator's routing allowlist (D-159) currently pins every task kind to two models of one vendor family, so a fan-out repeats them rather than spanning families. Where family diversity is the POINT — a substantial review's recall breadth — add the native layer on top, which is what § Dispatch policy already requires), runs parallel-safe, **auto-records each unit to the flywheel UNSCORED**, and recovers a zero-output straggler once; then **back-fill your 0–5 verdict with `set_quality(agent_id, score, project=, task_type=, model=)`** after you judge — a `fanout` row left unscored teaches the flywheel nothing. `run_agents([AgentSpec, …])` is the lower-level primitive for a hand-tuned mix — then YOU owe `record_agent_run(spec, result)` + `results_table` per unit (§ Report every pool run). A single-shot (`tools_enabled=False`) **repo-grounded** worker (`task_type` `review`/`docs`/`plan` — they assert about code they can't see) must set `allow_ungrounded=True` to attest it inlined the content into `task`, or use `tools_enabled=True` for real file reads — the module **refuses** ungrounded single-shot verification (it hallucinates). **The attestation is only as good as the inline: VERIFY the inlined content actually resolved before dispatch** — a `[MISSING: <path>]` marker passed as "source" produced a full, confident, line-numbered fabrication of a file the model never saw (measured 2026-08-28: one model refused honestly in its first sentence, another invented status values, methods and a five-step trace — wrong in exactly the direction that plans the wrong fix). Enforced (not prose) by `scripts/enforcement/check_subagent_flywheel.py`.
- ⚠️ **NEITHER MODE FITS A READ-ONLY REVIEWER OVER A LARGE FILE — know this before you dispatch.** Verified in `libs/subagents/agent.py` at HEAD: `read_only` sets `tools_enabled=False` (`:938`), so the unit CANNOT read files and you must INLINE the content — for a 1,950-line contract plus its siblings that is most of a context window before the reviewer has read anything. `write` gives real file reads but **requires a non-empty, disjoint `owned_paths` per unit** (`:1066`, an explicit raise) because it is built to return a DIFF. So a reviewer that CORRECTLY writes nothing returns an empty diff — and `AgentStatus` (`:48`) is `done | capped | error | out_of_scope`, with **no value distinguishing … (wrapped further — read the pack)
*"the output/diff is PARTIAL … do NOT trust a capped diff"*, and that message was the only reason the third unit was distrusted. The empty-`done` case has no such signal.
**Until the pool grows a read-only-with-file-reads mode, do NOT fan out a large-file review to the pool.** Either inline a BOUNDED extract (the section under review, not the whole contract) and accept `read_only`, or run that reviewer NATIVELY (`fabrik-reviewer`, which has real file reads) and keep the pool for units whose content genuinely fits inline. **And whichever you pick, treat an empty return as a FAILED unit, never a clean one** — check the output length before you score it, because the status will not tell you.
- FORK, never breadth.** The pool buys gradeable recall and the flywheel learns from it; native buys authority on subscription; `ai-consult` buys the one thing neither can — genuinely foreign frontier judgment (the `frontier` roster: 7 seats, 6 vendor families, zero Anthropic — Claude eyes come via `claude -p`, never metered). It records nothing to the flywheel and burns real credits, so it fires ONLY at these four entry points, and never as a reflex:
- operator for a credit top-up naming the estimated cost; never spend the tail silently and never substitute a degraded panel**. Single-model `consult()` before any panel; the panel only when the single opinion conflicts with ours or the fork genuinely needs diversity. Every use reports `cost_usd` in the run's evidence (the `Result` carries it). Never for gradeable fan-out — that is the pool's job (`/fabrik-review` already names bypassing `fanout` for ai-consult as throwing away recording, containment and caps). Live-verify the roster's model IDs before a paid session — `curl -s https://openrouter.ai/api/v1/models | python3 -c "import sys,json; print('\n'.join(m['id'] for m in json.load(sys.stdin)['data']))" | grep -x "<id>"` … (wrapped further — read the pack)
**⚠️ BOTH layers, never either/or — native is ADDED ON TOP of the pool breadth, not instead of it.** A *substantial* review / repo-review / rules-audit runs the **pool** breadth layer (`run_agents` finders — recall + they record) **AND** native `fabrik-reviewer` (Opus) for the auth/schema/migrations/secrets/concurrency slices + the decide/merge. "Native for the high-risk pass" does NOT mean native-**only**: a high-risk surface needs the pool breadth *plus* the native authoritative pass. Going all-native and skipping the pool layer lands **zero** flywheel rows (the flywheel learns nothing) — the exact miss `check_subagent_flywheel.py` advisory-WARNs (a big changed surface with no pool run). Trivial one-file reviews may run a single layer; anything substantial runs both.
**Trust = the METHODOLOGY, not a model pin.** A review's trust does NOT come from which pool model ran; it comes from **≥1 native Opus finder as the authoritative decider + every pool finding independently refuted before it is acted on** — both hold regardless of which models the flywheel currently ranks top. So never gate trust on a model name; gate it on the native-Opus-authority + refutation invariant.
- ⚠️ **`tools_enabled=True` + empty/overlapping `owned_paths` → one group → SERIAL — the #1 dispatch trap** (looks parallel, runs serial). If a read-only fan-out needs file reads, prefer shape 1 (inline) over shape 2.
- is **`n=1`**, so you MUST pass `n` to get more than one model. Parallel groups run **`max_concurrency` (default 4)** at a time — raise it to widen a big fan-out. Worker tools (**tools-enabled workers only** — a read-only single-shot worker has none of these, it just returns text): `read_file · write_file · apply_patch · list_dir · grep · run_command` (bwrap-sandboxed). (Prices + the per-kind best model are the flywheel's *output* — they live in `select.py`'s `_TABLE` + the synced `CODING_SUBAGENT_SELECTION.md`, never restated here; `pick_models(task_type)` returns them cheapest-that-clears-the-bar first — see § Pool model selection for why no roster lives in this pack.)
- Seats dispatched as multiple Task calls **in one assistant message** are started together; seats dispatched one message apart are serial by construction, which is the failure this pack exists to prevent. The ceiling is **`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`, default 20** — unset on this box, so 20 here (read out of the CLI bundle 2026-09-08, v2.1.263: `pt=20; … CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS??pt`; re-check it with `grep -aoE 'MAX_CONCURRENT_SUBAGENTS.{0,80}' "$(readlink -f "$(which claude)")"` rather than trusting this line). It is per-SESSION, not box-wide, so three hub sessions each get their own budget. ⚠️ **Past the ceiling a seat is REFUSED, not queued** (`Concurrent subagent limit reached … Do not retry`) — a refused seat is a FAILED seat and its absence is never a clean round. Under D-191 a wide surface DOES reach the ceiling (16 units want 33 seats) and `dispatch_headroom.py` trims to it — the cap is a HARD cap the script never exceeds; below it **the binding constraint on fan-out width is the box and subscription QUOTA, not concurrency** — check headroom, not the cap. (§ Parallelism — the two shapes, below, is Runtime B's and lives inside a `<!-- POOL OFF -->` comment with the rest of the pool contract; its `max_concurrency` default of 4 is the POOL's, not this one's.)
- author's own quiet round never closes a review loop: the context that shaped the artifact is the one least able to see its gaps (an author re-reads intentions, not text). **One sanctioned exception — the solo self-convergence loop:** a command whose loop dispatches NO finders anywhere (an author self-convergence pass, e.g. `/fabrik-ui-design`'s own convergence) closes with its own full fresh read — independence there is deferred to the PAIRED review command that follows it (`/fabrik-ui-design-review`), never silently skipped. **Adjudication — decide/refute/merge — stays with the orchestrator** (CLAUDE.md § Subagent fan-out: "the … (wrapped further — read the pack)
| `/fabrik-spec`, `-spec-review`, `-plan-review`, `-plan-after-chat`, `-data-contract`, `-docs-review`, `-ui-design-review` | grounders / reconcilers | **RO** (inline) — OR TE-disjoint (`owned_paths` per unit) if the worker reads the tree itself; **never** `tools_enabled=True` + empty `owned_paths` + "parallel" |
- > non-pooled (native runtimes never hit the `disjoint()` grouping). Same for any native pass.
- Auth/identity/session/crypto · schema/migrations · secrets/`.env`/keys · security controls (RLS, rate-limits, `final_gate`) · deploy/infra. These stay with the primary (human-supervised) agent. **Never web/MCP-enable a task carrying sensitive context** — the model's output exfiltrates via a scraped URL. Keep the bwrap sandbox on (`sandbox=True`, fail-closed).
- The canonical MCP server list is a hub-owned standard-format file — `/opt/fabrik/mcp.json` (`{"mcpServers": {name: {type, command, args, env}}}`, keys via `${ENV}` expansion, never inline). The pool's MCP client reads it via `AgentSpec.mcp_config` (path → unwrap the `mcpServers` key; dict → the bare server map).
- `docs/workstation/mcp-roster.md`; the user-level rosters carry only the universal 6. Never hand-edit an emitted `.mcp.json` — change the roster/ledger ruling, then re-run the emitter.
- `mcpServers` in the relevant Runtime-A agent type → `/opt/fabrik/mcp.json` (pool) — never a command brief.
- 2. **A flywheel row per unit** — **`record_agent_run(spec, result, quality_score=<the same 0-5>, project=<name>)`**. ⚠️ the older `record_run(result, …)` **silently no-ops** on a raw `AgentResult` (it wants a dict; `model`/`task_type` live on the *spec*) — always `record_agent_run(spec, result, …)`. On the VPS `SUBAGENT_RUNS_DSN` connects directly; on WSL dev pass a peer-auth `connect=` factory. It is fail-open (returns `False` silently on a DB problem) — to prove the plumbing, SELECT the row back, don't trust the return.
- When a project fixes a real bug in a **vendored `fabrik-lib` module** (e.g. `libs/subagents/`), it MUST append the fix — symptom + fix + date — to `/opt/fabrik-lib/<module>/UPSTREAM_FEEDBACK.md`. That file is the **one write allowed back into `/opt/fabrik-lib`** (cross-repo HARD STOP otherwise); the module author reads + resolves it, so the fix isn't silently lost on the next re-vendor. Fixing a vendored module without the entry breaks the loop.
- A pool run that emitted a `record_agent_run` but no `results_table` (or vice-versa) — both, one verdict. (And never `record_run(result, …)` — it no-ops; use `record_agent_run(spec, result, …)`.)

# promote-to-check_*: 85 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `fabrik-lib/fastapi-user-auth` `DELETE … RETURNING` `jti` `agents-fabrik.md § Supabase`
- `chrome-extension` `chrome.identity.launchWebAuthFlow` `https://<ext-id>.chromiumapp.org/` `chrome.storage.session`
- `desktop-app` `safeStorage` `desktop-app/72-desktop.md`
- `fabrik` `X-Internal-Token` `internal_auth.py` `hmac.compare_digest` `APIKeyHeader`
- `auth.uid()` `current_tenant_id()` `NULL` `EXCEPTION WHEN OTHERS THEN RETURN NULL` `SELECT auth.uid()` `NULL`
- `openssl rand -hex 32`
- `algorithms=["HS256"]` `alg` `alg: none`
- `redis-main`
- `expo-secure-store` `80-mobile.md`
- `localStorage` `sessionStorage`
- `chrome.storage.session` `TRUSTED_CONTEXTS` `chrome.runtime.sendMessage` `chrome.identity.launchWebAuthFlow` `code_verifier` `crypto.subtle` `storage.session`
- `x-middleware-subrequest` `middleware.ts` `proxy.ts` `middleware.ts`
- `CORSMiddleware` `allow_origins`
- `X-Frame-Options: DENY` `frame-ancestors`
- `APIKeyHeader` `require_api_key` `SERVICE_API_KEY` `PROXY_API_KEY` `python-api` `internal_auth.py` `metrics.py` `/metrics` `SERVICE_INTERNAL_SECRET_KEY`
- `os.getenv("KEY", "default")` `config/production.yml` `settings.production`
- `expo-secure-store`
- `^/api/` `/api/*` `/api/v1` `/api/*` `shape.bearer_bypass_prefix: "^/api/v1"` `fabrik apply` `^/` `orchestrator/verifier.check_api_bypass` `/api/*` `^/api/`
- `postgres-main` `fabrik-lib/rag` `postgres:16-alpine` `plpgsql` `postgres-main`
- `postgres-main` `docs/DECISIONS.md`

```

## Adjudication — QUIET round (it was not quiet): the justification text was never graded

The three previous rounds graded the RULE and the CHECK. Nobody had graded the paragraph that says WHY the
check exists — and it carried three false measurements about the tree it names.

| # | Candidate | Verdict | Proof executed here |
|---|---|---|---|
| qA-1a | "the FIFTH, SIXTH and SEVENTH shapes were absent from the output entirely" — FALSE for two of the three | **CONFIRMED → FIXED** | rendered `git show HEAD:CLAUDE.md` with markdown_it: the pre-fix row contains `A FIFTH shape` **True**, `A SIXTH shape` **False**. The FIFTH rendered and was cut mid-sentence at the first stray pipe; only the SIXTH vanished. Text now says exactly that. |
| qA-1b | "…and SEVENTH" — the SEVENTH shape did not EXIST at HEAD; this change adds it, so it cannot have been lost from a rendering | **CONFIRMED → FIXED** | same render: `A SEVENTH shape` **False** at HEAD, by construction. A reader re-deriving from HEAD would find the claim incoherent. |
| qA-1c | **"in both fleet-synced contracts" / "the two files that ship to ~46 repos" — wrong by a factor of two** | **CONFIRMED → FIXED in five places** | `scripts/fabrik_synced_manifest.py:98-101`: *"/opt/fabrik/CLAUDE.md is the HUB agents' contract and is NEVER distributed; projects receive the template."* `GOVERNANCE_TEMPLATES` carries `('templates/governance/CLAUDE.md', 'CLAUDE.md')` and `'CLAUDE.md' in GOVERNANCE_FILES` is **False**. Corrected in the check's docstring, the gate comment, both CHANGELOG entries, D-216's where-cell and the commit body. |
| qA-1d | The pipe ATTRIBUTION: all three blamed on the FIFTH shape's example | **CONFIRMED → FIXED** | `git log -S` puts two at `adce3017` (FIFTH) and the third at `66aa32a5` (the SIXTH's own example), both 2026-09-03. Now attributed per commit. |
| qA-2 | "the other 33 warn_only checks" is **32** — the sentence counts itself | **CONFIRMED → FIXED** | `grep -c 'warn_only=True'` → **33** in the working tree, **32** at HEAD; the 33rd is this check's own registration. |
| qA-3 | Lint + format debt invisible while the files were untracked | **CONFIRMED → FIXED** | `ruff check` found `F401 import sys` and `ruff format --diff` four hunks — both files now `All checks passed!` and `already formatted`, suite still 10 passed, and the check's exit codes re-verified unchanged (advisory 0, `--strict` 0 on a clean tree). |
| qA-4 | A row with no TRAILING pipe is truncated by GFM but invisible to the check | **RECORDED — latent, 0 live occurrences** | measured: 0 such rows in either contract, fence markers even (6/6) in both. A false-negative widening, not a regression this diff introduced. |
| qA-MIRROR | Replacing the distinct-count with a range LOST the argument: a range is satisfied by 42 repos at line 67 and one outlier, so a reader could still conclude "it's usually 67" — the DISPERSION was the point | **CONFIRMED → FIXED** | the clause now says "spanning 67–194 and genuinely SCATTERED — 28 distinct values across those 43 when last measured, so no line number is typical", with the count dated and marked re-derivable. The reviewer was right that my round-3 fix traded one honesty problem for another. |
| qA-CODE | Every code-shaped class: the three mutants, the docstring edit's behaviour, the render, byte-identity, fail-open edges, the `CLAUDE.md:3` assertion's brittleness | **CLEAN** | the seat rebuilt each mutant in a full tree copy and confirmed the claimed test fires (1/1/2 failures); `-OO` fine; the row renders 2 cells with all six shapes; the SEVENTH clause byte-identical at 2,982 chars; UTF-16 and directory inputs fail open to `SKIPPED`/`OK` at rc 0; and the `:3` in the advisory assertion is the line number inside the test's OWN fixture, not a repo coupling. |

**Why this round mattered most:** the first three rounds hardened the rule and the mechanism. This one read the
*evidence* — and found that the story justifying a new fleet-adjacent check was wrong in three ways about the
very tree it cites. A check whose stated reason for existing is false is a check nobody can audit later.

## Gate — re-measured in this round, not inherited

`python scripts/final_gate.py --check --json` over the whole working set (the run that preceded staging;
the staged-scope re-run and its three findings are below it):

```
{"status": "success", "tier": 2, "passed": 63, "failed": 0, "blocking": 41, "skipped_checks": ["pytest"]}
```

⚠️ **Staging CHANGED the verdict, which is the point of running it staged.** With the three new files in
the index the same command returned `status: failure, failed: 3` and every one was real:

| Phase | Finding at staging | Verdict |
|---|---|---|
| Phase 0–1 (scope, partition) | — | no findings |
| Phase 2 (mechanical sweep) | Lint Ratchet: repo-wide ruff errors rose 0 → 1 — an unused `import sys` in the new test file, invisible while the file was untracked | **FIXED** — removed; `ruff check` on both new files clean, suite still 10 passed |
| Phase 3 (adjudication + fixes) | Convergence Evidence: the receipt carried no embedded `final_gate` success inside a fence and no per-phase verdict | **FIXED** — this section |
| Phase 4 (delta rounds) | Coverage Checklist: the final ledger round raised 8, so the exit round is not quiet | **CORRECT AS REPORTED** — the loop is genuinely still open: the quiet round's seat was outstanding at commit time, so the header declares `Status: IN-PROGRESS` exactly as the grader's own escape prescribes. It flips to CONVERGED when that seat returns clean. |

The lint finding is the one worth keeping: an untracked file is OUTSIDE the gate's scope, so a repo-wide
ratchet cannot see its debt until it is staged. Running the gate before staging asserts less than it looks
like it does — the same shape as this commit's own subject.

