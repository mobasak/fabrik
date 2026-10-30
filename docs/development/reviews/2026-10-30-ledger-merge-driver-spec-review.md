# Spec review — 2026-10-30 ledger merge driver

**Status:** CONVERGED — closing pass 8 confirmed 0, md5 unchanged; design approved by the Opus + Fable panel with every concern accepted
**Final spec md5 (after the flip):** `7a2c4e122ee488ec9d38c2108fdfc5a1`

**Command:** /fabrik-spec-review
**Subject:** `docs/superpowers/specs/2026-10-30-ledger-merge-driver-design.md` (W-53360407)
**Base:** `51716046f`
**Shape:** agent-tool (D-961: no Workflow in the hub)

## Pass Ledger

| Pass | seats · axes re-checked | counters | method | spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (slice A) + sonnet×1 (slice B) + sonnet×1 researcher (slice C) · shape: agent-tool · all axes | found: 19, new: 19, confirmed: 14, fixed: 14, unexecuted: 0, edits: 16 | method: citation — full pass over the three section slices; orchestrator executed C1 (owner/builder replay split), the rebase probe, the towncrier raw curl, the gitattributes line read | be055200… → d9dd2510… |
| Pass 2 | opus×1 + sonnet×1 + sonnet×1 researcher (round-1 slice owners, resumed) · shape: agent-tool · delta over the round-1 hunks + one hop | found: 14, new: 14, confirmed: 8, fixed: 8, unexecuted: 0, edits: 11 | method: citation — delta over the round-1 fix hunks; orchestrator executed the call-cost timing, the builder-residue reasons, the criss-cross multi-base test, the :3779-3790 dispatch read | d9dd2510… → 025cf9e5… |
| Pass 3 | opus×1 + sonnet×1 + sonnet×1 researcher (round-1 slice owners) · shape: agent-tool · the round-2 fix set | found: 4, new: 4, confirmed: 1, fixed: 1, unexecuted: 0, edits: 2 | method: re-derivation — re-executed timing (0.34-0.43 s), the 3 residue reasons, the :3779-3790 anchor, the 22/5/10/7 split, the :164 sentence, the GitLab page read; scope-growth stop fired (8/7 → 1/1) | 025cf9e5… → 66b796df… |
| Pass 4 | sonnet×1 (round-1 owner of slice B) · shape: agent-tool · the round-3 fix set (D3 + Counter) | found: 3, new: 3, confirmed: 2, fixed: 2, unexecuted: 0, edits: 2 | method: re-derivation — re-ran _merge3 for the 3 residue merges under every base; the D3 fragment read against D1's bindings; class rewrite — § Derivations D3 (rounds 3, 4): replaced whole by the executed script, extracted from the spec and re-run (same 3 lines) | 66b796df… → e6ee9eb2… |
| Pass 5 | sonnet×1 (round-1 owner of slice B) · shape: agent-tool · the round-4 rewrite (D3 + Counter); standing clean since pass 3: slices A and C, every other class | found: 2, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — D3 extracted from the pin and executed (output identical to the pasted block); Counter computability derived from its output; standing-clean classes not re-read: facts, cost, invariants, ordering, reversibility, population, tests, docs, intake, personas | e6ee9eb2… → e6ee9eb2… ✓ |
| Pass 6 | opus×1 + sonnet×1 (round-1 owners of slices A and B) · shape: agent-tool · the panel revision (ten accepted concerns + the D5 real-driver figures) | found: 13, new: 13, confirmed: 9, fixed: 9, unexecuted: 0, edits: 9 | method: re-derivation — anchors :980/:1189/:1203-1208 re-read, empty-base and fallback probes executed by the seat, tripwire arithmetic re-derived from D5's printed summary; orchestrator executed D5 (real git merge, 58/67, no duplicated line), the recursive=binary probe, D4 | e6ee9eb2… → 7303e4c5… |
| Pass 7 | opus×1 + sonnet×1 (round-1 owners of slices A and B) · shape: agent-tool · the round-6 fixed set | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0, edits: 3 | method: re-derivation — D5's :355/:359 filters read against the grader and Counter B; tripwire watch/counter re-derived; class rewrite — § Validation replay grader and tripwire counter (rounds 6, 7) | 7303e4c5… → ea754a38… |
| Pass 8 | opus×1 + sonnet×1 (round-1 owners of slices A and B) · shape: agent-tool · the round-7 rewrite only; standing clean since pass 6: every other class | found: 2, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — the replay grader and Counter B read against D5's :355/:359; tripwire watch/counter/threshold re-derived (9 − 3 = 6); both notes RECORDED — measured onto W-6614b62e (scope-growth stop, fired at pass 3) | ea754a38… → ea754a38… ✓ |

## Findings

| ID | Round | Anchor | Disposition | Evidence |
|---|---|---|---|---|
| A1 | 1 | § The delta MIRROR "the order is the same one the merge owner already lands" | CONFIRMED · fixed (Order bullet) | seat probe: builder merge puts branch entry first, owner puts master first (`_resolve_insertions` :980-984) |
| A2/B-C4 | 1 | § Cost "per conflicted ledger file" | CONFIRMED · fixed | seat probe: driver called on a clean both-sides merge |
| A3 | 1 | § Decisions taken undo | CONFIRMED · fixed | `scripts/install_post_commit_hook.sh:81-87` re-sets a missing key |
| A4/A5/B-C2 | 1 | § Validation tripwire | CONFIRMED · fixed (builder residue, commit-date window, >3) | records carry no wall-clock field; 10 = expected value; window before landing |
| A6 | 1 | § Validation bootstrap test | CONFIRMED · fixed | plain git also leaves markers; stderr `invalid choice` now asserted |
| A7 | 1 | `replay.py`/`driver_cover.py`/`readers.txt` | CONFIRMED · fixed (§ Derivations D1, D2) | not findable in the tree; census recount 119/47/4 |
| A8 | 1 | § The delta 3 unanchored patterns | CONFIRMED · fixed | gitignore pattern rules (no slash = any depth) |
| A9 | 1 | § The delta 1 write-then-fail | CONFIRMED · fixed (invariant) | seat probe `d_wrotefail` |
| B-C1 | 1 | § Why 1 "Each of the 400 was a hand resolution" | CONFIRMED · fixed | orchestrator split: owner 557/331/331, builder 229/89/70/67 |
| B-C3 | 1 | § Documentation landing sites | CONFIRMED · fixed | `docs/reference/merge-request.md` absent; `scripts/merge_request.py:2` names multi-agent-operating-model.md |
| B-C5 | 1 | § The delta 1 "as UTF-8" | CONFIRMED · fixed | `scripts/merge_request.py:728-733` surrogateescape |
| B-C6 | 1 | § Why 4 D-1381 attribution | CONFIRMED · fixed | "22 of 51" is the item title's; D-1381 says 7 |
| B-C7 | 1 | § Intake I7/I11 destinations, I1-I3 wording | CONFIRMED · fixed (W-7a1411b3, W-480cdb61 filed) | mail is not a destination |
| B-C8 | 1 | § Personas duty holders | CONFIRMED · fixed | installer stderr, replay grader, tripwire owner |
| C-1 | 1 | gitattributes line numbers | REFUTED | orchestrator raw read of lines 1125-1180 |
| C-2 | 1 | towncrier "Rather than …" opening | REFUTED | raw curl matched the sentence |
| C-3 | 1 | towncrier curly vs straight quotes | RECORDED — measured (wording; changes no behaviour) — then quoted exactly in the rewrite | raw curl |
| C-4 | 1 | precedence row nuance | RECORDED — measured (wording) — reworded | exa raw |
| C-5 | 1 | GitLab "must sit on a specific commit" phrasing | RECORDED — measured (wording) — reworded to the page's advice | WebFetch |
| C-6 | 2 | § Rejected alternatives GitLab bullet (own-fix: round 1) | CONFIRMED · fixed | page gives `-f` after `--amend`, `--force-with-lease` after `rebase -i`, only if already pushed |
| A-N1 | 2 | § Cost "5 × 0.4 s = 2 s" (own-fix: round 1) | CONFIRMED · fixed (≤ 4 s) | seat timeit 0.67-0.79 s; orchestrator re-run 0.37-0.38 s |
| A-N2/B-N1 | 2 | § Validation tripwire (own-fix: round 1) | CONFIRMED · fixed (rewritten whole: non-edit residue only, >0, explicit window) | threshold re-opened fragments on edit-class residue fragments cannot fix; P(X>3 at mean 3) ≈ 0.35; builder residue reasons executed: 3 of 3 edit-class |
| A-N3 | 2 | § The delta 1 "last act before exit 0" (own-fix: round 1) | CONFIRMED · fixed | `scripts/merge_request.py:3796-3806` finally drains after `verb(args)`; `sync-runner` dispatched before it at :3779-3790 |
| B-N2 | 2 | § Personas "Each builder" vs § Validation (own-fix: round 1) | CONFIRMED · fixed | same-document contradiction |
| B-N3 | 2 | § Derivations D1 single merge-base | REFUTED | 10 of 70 multi-base; verdict identical under every base (9 clear, 1 none) |
| B-N4 | 2 | Profile line vs I1-I3 | CONFIRMED · fixed | Profile claimed IN items map to the asked shape |
| B-N5 | 2 | § Why 4 "6 of those refusals" (own-fix: round 1) | CONFIRMED · fixed | 22 with `conflict` = 5 + 10 + 7; the sixth work-item refusal lacks the word |
| B-N6 | 2 | § Documentation landing sites (own-fix: round 1) | CONFIRMED · fixed | `docs/reference/multi-agent-operating-model.md:164` "always conflict at merge" turns false |
| A-R1 | 2 | tripwire re-opens on edit class | RECORDED — measured (merged into A-N2/B-N1) | — |
| A-R2 | 2 | D1 writes tree objects into the shared object store | RECORDED — measured (unreferenced objects, gc'd; the replay grader runs on a scratch clone) | — |
| B-N7 | 2 | D1 codec `replace` vs verb `surrogateescape` | RECORDED — measured (multi-base run used `_decode`: same verdicts) | — |
| B-N8 | 2 | D1 has no committed tool; owner regex hard-codes `merge(coordinator)` | RECORDED — measured (the plan's replay grader is the committed tool; W-53360407 plan scope) | — |
| B-R3 | 3 | § Validation tripwire Counter cites D1, which prints no reasons (own-fix: round 2) | CONFIRMED · fixed (Derivation D3 added, Counter repointed) | D1's script catches `RefusedError` with no reason split |
| A-R3 | 3 | the 56/day counts merge commits, not every build | RECORDED — measured (the bound is over logged merges; rebuilds add at most MAX_REBUILDS per landing) | — |
| A-R4 | 3 | sync-runner returns 70 on a crash | RECORDED — measured (only its dispatch position is copied; delta 1 fixes exit 1) | — |
| B-R4 | 3 | "work-item refusals in all" vs D-1381's "same-item conflicts (7)" | RECORDED — measured (wording; changes no behaviour) | — |
| B-R5a | 4 | § Derivations D3 `sha` undefined (own-fix: round 3) | CONFIRMED · fixed (class rewrite) | site: D3 python block; D1 binds no `sha` |
| B-R5b | 4 | § Derivations D3 comment "read through mr._decode" (own-fix: round 3) | CONFIRMED · fixed (class rewrite) | site: D3 python block; the fragment called D1's `blob()` (`replace`) |
| B-R5c | 4 | Counter counts merges, D3 prints one line per file | RECORDED — measured (latent; folded into the rewrite: the Counter counts distinct SHAs) | — |
| B-R6a | 5 | D3 hard-codes `--since=14 days ago`; the tripwire window is landing-relative | RECORDED — measured (the owner edits one argument; already stated in § Validation) | — |
| B-R6b | 5 | `merge-base … split()[0]` raises on unrelated histories | RECORDED — measured (same as D1; never triggered in the window) | — |
| P6-A-C1 | 6 | delta 1 duplicate-id refusal undone by the `||` fallback on non-overlapping rows (own-fix: panel revision) | CONFIRMED · fixed (narrowed to where it bites) | seat probe: driver exit 1 + fallback → MERGE_RC=0 |
| P6-A-C2 | 6 | duplicate-id check vs `:1203` semantics (own-fix: panel revision) | CONFIRMED · fixed | `:1203` subtracts only `new^1`'s duplicates |
| P6-A-C3 | 6 | delta 4 names one refusal path (own-fix: panel revision) | CONFIRMED · fixed | `_dup_ids` RefusedError at :1205-1207 |
| P6-A-C4 | 6 | tripwire confirm/re-open wording contradicts threshold (own-fix: panel revision) | CONFIRMED · fixed | `:116` vs `:119` |
| P6-B-1/A-C6 | 6 | owner 392/392 underived (own-fix: panel revision) | CONFIRMED · fixed (figure deleted) | D5 skips owners at `:355` |
| P6-B-2 | 6 | Why 2 denominator 70 → 67 unexplained (own-fix: panel revision) | CONFIRMED · fixed | D5 prose only |
| P6-B-3 | 6 | Personas "(or rebase)" vs Goal (own-fix: panel revision) | CONFIRMED · fixed | Goal cites :101-108 |
| P6-B-4/A-C5 | 6 | tripwire counter includes work-item SHAs (own-fix: panel revision) | CONFIRMED · fixed | D5 `still-conflicted 12` |
| P6-B-5 | 6 | binary rejection claims unpasted output (own-fix: panel revision) | CONFIRMED · fixed (stated by mechanism) | no derivation |
| P6-A-P1 | 6 | no-regression test green on a refusing driver | ACCEPTED · fixed (asserts the driver's own exit 0) | seat probe `r_refclean` |
| P7-A-C6/B-1 | 7 | replay grader promises an owner-side Counter B D5 cannot compute (own-fix: round 6) | CONFIRMED · fixed (class rewrite: builder-only grader; Counter B named as a plan pass) | D5 `:355` builder filter, `:359` clean skip |
| P7-B-2 | 7 | tripwire watch sentence vs counter (own-fix: round 6) | CONFIRMED · fixed (counter subtracts every D3 SHA) | `:114` vs `:115` |
| P8-A | 8 | Counter B pass must also lift D5's :355 builder filter | RECORDED — measured (W-6614b62e; own-fix after the scope-growth stop) | — |
| P8-B | 8 | D3's non-edit refusals reported nowhere | RECORDED — measured (W-6614b62e; latent, reads 0 today) | — |

## Orchestrator probes

- `git rebase` invokes a `.gitattributes` merge driver: scratch repo, driver logged one call, rebase clean; the same pair with no driver conflicts (`rebase-probe` in RUN-SCRATCH). Resolves the spec's OPEN unknown.
- `docs/reference/merge-request.md` does not exist (`ls docs/reference/ | grep -i merge` → nothing); `scripts/merge_request.py:2` `# AFTER-EDIT:` names `docs/reference/multi-agent-operating-model.md`, whose § Ledgers and ids across branches (`:162-166`) describes the in-process resolver.

## Ask ↔ spec comparison (recomputed against the closing-round text, md5 e6ee9eb2…)

| Operator / coordinator words | What the spec says (section + one line) | Anchor | Disposition |
|---|---|---|---|
| "fed up with merge issues" | Builders' ledger hand resolutions (70 in 14 d) cleared by a git merge driver (67) | § Why this exists 1-2 | IN |
| "one entry file per CHANGELOG entry and per DECISIONS row" | Not built: a merge driver instead; the fragment design kept whole | § Decisions taken; § Rejected alternatives F | CHANGED (coordinator accepted, answer to 01M677712S) |
| "rendered into CHANGELOG.md and docs/DECISIONS.md at merge by merge_request.py" | git's merge writes the canonical files through `merge_request.py merge-ledger` | § The delta 1-2 | CHANGED |
| "so two branches never touch the same line" | Concurrent insertions never need a hand resolution; edits of landed lines still conflict | § Goal | CHANGED |
| "NO migration of the existing 31,458 lines" | Nothing migrates | § The delta 4 | IN |
| "FIRST extend SKIP, PRETEST_SKIP, LEDGERS and _dup_ids" | Unneeded under the driver; listed for F | § The delta 4; § Rejected alternatives F | DROPPED (no new path exists to add) |
| ".fabrik/work same-item conflicts are a separate item" | Filed as W-7a1411b3 | § Intake I7 | IN (destination) |
| "merge_request.py is fleet-synced" | Verb ships inert to ~46 repos; driver hub-only; rollout W-480cdb61 | § Personas; § The delta 2 | IN |
| "the gate checks that read them (check_convergence, decisions.py --reserve-id, the changelog gate)" | Unchanged under the driver; each named for F | § The delta 4; § Rejected alternatives F | IN |
| "Report in the same turn when the review closes" | The close mails the coordinator | § Intake I9 | IN |
| (not asked) § Validation tripwire | The judges' shared dissent: re-open F only on non-edit residue | § Validation | ADDED (the judge panel's dissent) |
| (not asked) § Derivations D1-D3 | The replay, reader census and residue scripts with output | § Derivations | ADDED (review finding A7: reproducible numbers) |
| (not asked) § Cost / § Lifecycle / § MIRROR | Driver runtime bound, undo, order change | § Cost; § Lifecycle; § The delta MIRROR | ADDED (this command mandates them) |

## Design-approval panel (D-613)

Artifact pinned for the panel: md5 `e6ee9eb2b2002839e904a94039289c6b` at `5bb3e7a34`.

- `VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-30-ledger-merge-driver-design.md` (opus)
- `VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-30-ledger-merge-driver-design.md` (fable)

| Concern | Disposition | Change (where) | Counter-case it must still pass |
|---|---|---|---|
| Opus 1 — the driver may turn clean ledger merges into conflicts | ACCEPTED (measured) | § Derivations D4: 0 of 145 clean both-sides-changed files refused; § The delta 4 sentence on text source corrected | a clean merge with no driver stays clean with it |
| Opus 2 — the tripwire cannot see a driver regression | ACCEPTED | § Validation Counter B (clean without driver, conflicted with it → blocks); rebases named as invisible | a merge that conflicts both with and without the driver is not counted by B |
| Opus 3 — no clean-stays-clean test | ACCEPTED | § Validation No-regression test | the red-first conflicting pair still resolves |
| Opus 4 — the replay grader checks only builders | ACCEPTED | § Validation Replay grader runs D5 over builder and owner merges | owner merges that already refuse today stay refused, not counted as regressions |
| Fable 1 — a duplicate D-id merges cleanly at the builder | ACCEPTED | § The delta 1 duplicate-id refusal; § Validation Duplicate-id test | two different new D-ids still merge clean |
| Fable 2 — the `%P` → DECISIONS branch is untested | ACCEPTED | § Validation red-first DECISIONS ordering leg | CHANGELOG still keeps ours first |
| Fable 3 — the Order sentence overclaims | ACCEPTED | § MIRROR Order rewritten to `_max_d` per hunk | — (wording) |
| Fable 4 — D3 hard-codes its window | ACCEPTED | D3 takes `<since> <until>`; re-run from the spec with `"14 days ago" now`: same 3 lines | — |
| Fable 5 — rebase is not a builder path for pushed branches | ACCEPTED | § Goal cites `scripts/merge_request.py:101-108` | a local unpushed rebase still gets the driver |
| Fable 6 — empty base concatenates two files | ACCEPTED | § MIRROR Empty base note | — (pre-existing on the owner path) |

Panel: opus="VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-30-ledger-merge-driver-design.md" fable="VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-30-ledger-merge-driver-design.md" → both-approve (every concern ACCEPTED and verified by the delta passes 6-8)
