# Spec review — lean command corpus design

**Command:** /fabrik-spec-review
**Surface:** `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md`
**Work item:** W-96f36043 (P0) · nested in `/fabrik-spec` · design approval: the Opus + Fable panel, D-1217
**Shape:** agent-tool (hub, D-961: no `Workflow`)

## Slices (round 1, disjoint)

| Slice | Seat | Scope |
|---|---|---|
| A-rules | opus×1 (`fabrik-reviewer`) | § Target, § The measure, § The rule test, § How a command is cut, § Loop changes, § Order, § Binding |
| B-rest | sonnet×1 (`fabrik-reviewer`) | § Personas, § Problem, § Intake Inventory, § Constraints Digest, § Panel, § fabrik-lib verdict, § Lifecycle, § Review and landing, § Rejected alternatives, § Residual unknowns |
| C-facts | sonnet×1 (`fabrik-researcher`) | the three cited external pages |

## Pass Ledger

| Pass | seats · axes re-checked (intake · personas · facts · vendor · approach · completeness · constraints) | counters | method | spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 + sonnet×1 + sonnet×1 researcher · all axes | found: 30, new: 30, confirmed: 25, fixed: 25, unexecuted: 0, edits: 25 | method: citation — full pass; orchestrator executed: `check_spec_convergence.py` on a flipped scratch copy (1 examined, 0 findings after the residual section), `curl` status 200 on both docs pages, a raw-page search of the prompting page (history: 5 hits, none advising a rule's history), `grep -nE "TemporaryDirectory\|sys.exit\("` on `commands/assemble_commands.py` (:1323, :1382, :1265, :1438), the `{{include:` count over 39 sources (24 fragments shared), the change-axis and distinct-id re-counts (2,449/220; 42 ids, 12 dates); 1 REFUTED (B-C11, "~46 repos" is `CLAUDE.md`'s own figure), 1 RECORDED — measured (B-C6, `llm-dispatch` sizes a call's input, not a rendered file), 3 minor A-findings fixed with the 12 | dd172afbe67c63fb8c244403bf06f38a → 7f9b1e312c3444950fdb075a5df8ad0b |

| Pass 2 | opus×1 + sonnet×1 (round-1 owners of A-rules, B-rest; C-facts closed, no open claim) · delta over round-1 hunks + one hop | found: 9, new: 9, confirmed: 8, fixed: 8, unexecuted: 0, edits: 8 | method: re-derivation — every round-1 fix's code claim re-read at its line (render :1163, exits :1265/:1382/:1438, 24 shared includes, `_CLOSE_FEEDBACK` :31, pilot includes), every count re-derived by script (3,072 h, 741, 2,449/220, 42/12, 16 intake rows); orchestrator re-ran `ls commands/_sources \| wc -l` (39 branch) vs `/opt/fabrik/commands/_sources` (40 master) and the charter `grep -n` (§ Beat :28-29); own-fix: round 1 for all 8; 1 out-of-hop (shared `_agents` definitions without ledger-first) folded into the N3 fix | 7f9b1e312c3444950fdb075a5df8ad0b → 846bc4de7af2baf6cff26f03f7f83fb1 |

| Pass 3 | opus×1 + sonnet×1 (round-1 owners) · delta over round-2 hunks + one hop | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0, edits: 3 | method: re-derivation — B-rest re-derived 40/39/38 populations and the charter cite (confirmed 0); A-rules re-read `check()` (orchestrator re-ran `sed -n -e 1322,1328p`: `render()` runs before any gate) and the pilot's dispatched seats (`fabrik-review-scoped.md:8`); own-fix: round 2 for all 3. Not a review fix, also landed after this pass: U4 resolved from intel's W-0a91bf86 table and a new § Time budget section, put to a second panel | 846bc4de7af2baf6cff26f03f7f83fb1 → (with the U4 and § Time budget additions) see Pass 4 |

| Pass 4 | opus×1 + sonnet×1 (round-1 owners) · the scope-growth stop's fixed set (round 3) + the § Time budget section (second panel, D-1219) | found: 7, new: 7, confirmed: 7, fixed: 7, unexecuted: 0, edits: 7 | method: re-derivation — B-rest re-counted 17/16/1 intake rows and matched U4's eight figures to intel's receipt (confirmed 0); A-rules re-read `assemble_commands.py:1261-1270`, `:1322`, `:1382`, `:1430-1438` and `fabrik-review-scoped.md:8`; orchestrator re-ran `sed -n -e 164,168p commands/_sources/fabrik-review-scoped.md` (no D-344 pair on the pilot: "never applies here"); own-fix: the § Time budget text added in this review, all 7 | aafb2b9eee3869bd84592c54feb4e812 → 740d7d7bf7dd1c17e3d48c3928af31aa |

| Pass 5 | opus×1 (A-rules round-1 owner; B-rest had no open claim and no fix hunk) · the round-4 fixed set (scope-growth exit) | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 2 | method: re-derivation — C1-C3, C5-C7 CLOSED with their pin-5 lines quoted; `fabrik-repo-review.md:47` and `fabrik-review.md:179,502,512` re-read for the D-344 pair; orchestrator ran `check_review_hygiene.py` (1 split-table hit at the round-3 I17 row, fixed, 0 after) and `check_spec_convergence.py` on a flipped copy (1 examined, 0 findings); own-fix: round 4; 2 RECORDED — measured (folded into the C4 fix; `/fabrik-execute-plan`'s Opus floor is not a pair, one hop out) | 740d7d7bf7dd1c17e3d48c3928af31aa → 3ca433c034eb738c30da61fb650a5996 |

| Pass 6 | opus×1 (A-rules owner) · the round-5 fix (2 hunks) | found: 4, new: 4, confirmed: 1, fixed: 1, unexecuted: 0, edits: 1 | method: re-derivation — C4 CLOSED (pin-6:328-330, :275, :300); one in-hunk defect at the T1 site; class rewrite — T1 bullet (rounds 4, 5, 6), rewritten to one sentence; own-fix: round 5. Oscillation note: the 3 → 7 step was the § Time budget section added mid-review on the coordinator's request, not a re-scoped brief | 3ca433c034eb738c30da61fb650a5996 → bf6479292c4ec36c276350c8ab79c81e |

| Pass 7 | opus×1 (round-1 owner of A-rules; B-rest and C-facts restated at their last verified counts, no open claim, no fix hunk) · the round-6 class rewrite | found: 3, new: 3, **confirmed: 0**, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — the T1 sentence (pin-7:298-300) re-derived against the windows, frozen-sample, panel and before-window definitions; standing clean since their last full pass: intake, personas, facts, vendor, counts, lifecycle; 3 RECORDED — measured (the "confirmed defects per run" figure added to the measure list, the case of fewer than 5 sample surfaces, and T1 not isolated from the phase's other levers — destination: the plan set's tooling ticket and the `/fabrik-review` phase ticket) | bf6479292c4ec36c276350c8ab79c81e → bf6479292c4ec36c276350c8ab79c81e ✓ → **CONVERGED** |

Design approval: answered by the Opus + Fable panel twice — D-1217 (the design) and D-1219 (§ Time budget), both APPROVE-WITH-AMENDMENTS, the amendments agreeing and folded; no split reached the operator.

## Round 6 dispositions

| id | finding | disposition |
|---|---|---|
| A6-C1 | T1's spread condition never compares before and after recall | CONFIRMED (pin-6:299-302) — fixed by a class rewrite of the T1 bullet: spreads only when confirmed defects per run hold at or above the before window and the frozen sample shows no rise; else the panel reverts |
| A6-R1 | § Lifecycle names the pinned script as the source of both cobra counters; the frozen sample is a report | RECORDED — measured (one hop, pre-existing; destination: the plan set's tooling ticket, which writes the after-window report) |
| A6-R2 | revert by D-row vs the panel revisiting | RECORDED — measured (closed by the A6-C1 rewrite: the panel reverts) |
| A6-R3 | fewer than 5 fast-closed surfaces in a window | RECORDED — measured (destination: the plan set's tooling ticket — sample all of them when fewer than 5) |

## Round 5 dispositions

| id | finding | disposition |
|---|---|---|
| A5-C4 | the frozen sample runs at a phase close, before the new command has run, into a D-row a plain-lever phase never writes | CONFIRMED (pin-5:269, :285 vs :326-328) — fixed: at the after window's end, recorded in the after-window report; T1's D-row is provisional on it |
| A5-R1 | T1's D-row cannot cite a sample taken after its phase | RECORDED — measured (closed by the A5-C4 fix) |
| A5-R2 | `/fabrik-execute-plan`'s per-round Opus floor (fabrik-review.md:179) is not a pair | RECORDED — measured (T1 applies only where the pair exists; the floor is untouched by construction) |

## Round 4 dispositions

| id | finding | disposition |
|---|---|---|
| A4-C1 | T1 trialled on a pilot that has no D-344 pair | CONFIRMED (`fabrik-review-scoped.md:164-165`) — fixed: T1 only on the partitioned loops, trialled in `/fabrik-review`'s phase; the scoped three-seat floor stays |
| A4-C2 | T2's added fix-hunk condition changes D-335 without a D-row | CONFIRMED — fixed: T2 is D-335 as written; any added condition is a rule change |
| A4-C3 | T1/T4 decided in phase 3 while the pilot owns the `_agents` ledgers | CONFIRMED (pin text) — fixed: T4 decided in the pilot phase, T1 in `/fabrik-review`'s |
| A4-C4 | "fast-closed", "a rise" and the frozen sample's owner undefined | CONFIRMED — fixed |
| A4-C5 | which baseline the 50% target compares against | CONFIRMED — fixed: the command's own before window; the tooling baseline is the text one |
| A4-C6 | the T3 paraphrase dropped migration and >5-file routes | CONFIRMED (`fabrik-task.md:216-217`) — fixed |
| A4-C7 | one `changed-by` marker; step 5's audit not told | CONFIRMED — fixed: a list, the audit reads its last D-row |

## Round 3 dispositions

| id | finding | disposition |
|---|---|---|
| A3-C1 | the pilot's own text dispatches shared `_agents` definitions but phase 3 ledgers them after the pilot cuts | CONFIRMED (`fabrik-review-scoped.md:8`) — fixed: the pilot ledgers them |
| A3-C2 | exit precedence claims 4 wins over a render failure, but `check()` renders first | CONFIRMED (`assemble_commands.py:1327`) — fixed: render failure stops before the gate |
| A3-C3 | step 3's `file` values omit `_fragments/` | CONFIRMED (pin text) — fixed |

## Round 2 dispositions

| id | finding | disposition |
|---|---|---|
| B2-C1 | "39 commands" — master renders 40 | CONFIRMED (40 master, 39 branch) — fixed with both populations named; BUDGET follows |
| B2-C2 | Lifecycle cites the charter's "Real time" for the daily read | CONFIRMED (§ Beat :28-29) — fixed |
| B2-C3 | the ledger-size trigger's source is printed by nothing | CONFIRMED — fixed: the test prints each ledger's entry count |
| A2-N1 | exit 1 is not only drift; one process returns one code | CONFIRMED (`raise SystemExit("…")` exits 1) — fixed: gate before drift, precedence 4, 5, 1 |
| A2-N2 | "four" shared pilot fragments omits `close-feedback` | CONFIRMED — fixed |
| A2-N3 | `review-probe-catalogue` and shared `_agents` escape ledger-first | CONFIRMED (0 includers, 6 namers) — fixed: step 1 covers every shared `commands/` file by four routes |
| A2-N4 | the tail's unchanged sentences had no standing carrier | CONFIRMED — fixed: every rule gets an entry, generated for unchanged sentences |
| A2-N5 | the builder hold had no lift on KILL and was ambiguous between phases | CONFIRMED — fixed |

## Round 1 dispositions

| id | finding | disposition |
|---|---|---|
| C-1 | the prompting page is now titled "Prompting best practices" | CONFIRMED (raw fetch) — fixed |
| B-C1 | change-axis counts were over all states, not `done` | CONFIRMED (re-count 2,449/220) — fixed |
| B-C2 | 129/23 are mentions, not distinct ids/dates | CONFIRMED (42, 12) — fixed |
| B-C3 | D-1216's "all other builder work pauses" has no row | CONFIRMED (pin grep 0 hits) — fixed: I14 + § Program holds |
| B-C4 | D-1216's command-improve pause has no row, holder or lift | CONFIRMED — fixed: I15 + § Program holds |
| B-C5 | the "not doing its work" complaint has no row | CONFIRMED — fixed: I16 |
| B-C6 | `llm-dispatch` prompt sizing unmentioned | RECORDED — measured (per-call input size, not a rendered-file measure; no reuse) |
| B-C7 | ceiling-raise trigger names no usable source | CONFIRMED (the file holds only the current value) — fixed: git log source |
| B-C8 | `remove: none` ratio has no denominator or holder | CONFIRMED — fixed |
| B-C9 | 300-entry trigger unmeasured | CONFIRMED — fixed: the test prints counts |
| B-C10 | no holder files trigger items | CONFIRMED — fixed: kaizen, daily digest read |
| B-C11 | "~46 repos" unverifiable | REFUTED (`CLAUDE.md` line 7 states ~46 repos) |
| A-C1 | the test cannot read `--check`'s temp dir | CONFIRMED (`assemble_commands.py:1323`, `:1382`) — fixed: the test renders itself |
| A-C2 | the pilot does not share `/fabrik-review`'s fragments | CONFIRMED (include grep) — fixed |
| A-C3 | the step-3 fragment list is wrong | CONFIRMED (24 shared + `close-feedback`; `review-probe-catalogue` is not rendered) — fixed |
| A-C4 | L1's ledger-less refusal contradicts the program's own additions | CONFIRMED — fixed: three exemptions |
| A-C5 | own text excluded new kaizen docs | CONFIRMED — fixed: own text widened |
| A-C6 | rules moved into seat definitions had no ledger | CONFIRMED — fixed: the `file:` field |
| A-C7 | pins on non-render files were deleted with no carrier | CONFIRMED (`tests/test_review_scoped_queue_pass.py` reads `_agents`, the catalogue and the workflow js) — fixed |
| A-C8 | the light form excluded steps it depends on | CONFIRMED — fixed: steps 2-8 apply, ledger holds only changed rules |
| A-C9 | `reads` growth both needed a D-row and was not blocked | CONFIRMED — fixed: a D-row only for an added path |
| A-C10 | agent definitions belonged to both ceilings | CONFIRMED — fixed: own text / `render` |
| A-C11 | a ceiling breach had no exit code distinct from drift | CONFIRMED (codes 1, 2, 3 in use) — fixed: LOSS 4, ceiling 5 |
| A-C12 | the floor's median is undefined before any command reaches 50% | CONFIRMED — fixed: U1 |
| A-m1 | TRIPWIRE "AND" ambiguous | CONFIRMED — fixed: EITHER |
| A-m2 | "about 30 commands" vs 39 rendered | CONFIRMED — fixed |
| A-m3 | "closed one level deep" undefined | CONFIRMED — fixed |
