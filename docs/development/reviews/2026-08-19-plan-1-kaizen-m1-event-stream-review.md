# Whole-implementation review — kaizen M1 event stream (cumulative, all 9 tickets)

Surface: d3afb56c0252830de9d118cb02f33980fa2470d0 + working-diff md5 700509c91e1bbddf196846a3686d7fac
Scope: `git diff 4202c384..HEAD` over the plan's File Scope — 12 files, 5,730 insertions —
plus callers/callees. Prior context: every ticket carries an accepted per-ticket acceptance
ledger (`…-T0[1-9]-review.md`); THIS review is the whole-surface closing loop the operator
mandated — non-author finders, iterated to a `found: 0` full fresh round.

Rubric (verbatim `review_rubric.py --changed <the 12 paths>` output):

```
(see scratchpad m1_rubric.txt — 99 lines; FLOOR: core/35-security-auth, core/25-data-postgres,
core/30-ops, 12-FACTOR all twelve axes; MATCHED: core/10-python via hooks + command_run)
```

## Coverage Checklist

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | fail-open vs fail-closed on every gate/guard | UNCHECKED | |
| 2 | concurrency & atomicity (O_APPEND, flock, TOCTOU, event_seq, killpg) | UNCHECKED | |
| 3 | boundary/sentinel/prefix collisions (dash strings, era keys, sid sanitize, byte bounds) | UNCHECKED | |
| 4 | accounting edges (unknown≠0, denominators, delta math, variance) | UNCHECKED | |
| 5 | cross-file contract breaks (emit/exposure signatures, registry, read_rows consumers) | UNCHECKED | |
| 6 | logic / off-by-one / None-empty handling | UNCHECKED | |
| 7 | resource cleanup & subprocess trees (timeouts, temp dirs, clones, reaps) | UNCHECKED | |
| 8 | security-auth FLOOR (secrets, injection, path traversal) | UNCHECKED | |
| 9 | data-postgres FLOOR | UNCHECKED | |
| 10 | ops FLOOR + 12-Factor (logs→stdout, no daemonize, no host ports, env config) | UNCHECKED | |
| 11 | test quality (red-provability, mock theatre, vacuous assertions) | UNCHECKED | |
| 12 | plan↔code deviation (spec intent) | UNCHECKED | |
| 13 | core/10-python mandates (hooks + command_run) | UNCHECKED | |

## Pass Ledger

Pass 1 (WIDE) — finders: pool fanout ×3 (deepseek-v3.2 raised 9 on the emitter/hooks partition; gemini-3-flash region-403; qwen3-max thin NO FINDINGS) + native Opus fabrik-reviewer (authoritative: fail-open, concurrency, contracts, security, honesty — raised 21, six HIGH, most probe-reproduced against a copied real store) + native Fable fabrik-reviewer (test-quality, 12-factor, boundaries, plan↔code — raised 3, none confirmed-functional) | found: 33 (new: 33) | fixed: 0 this pass → fix wave dispatched | → not done

Pass 2 (fresh non-author Opus finder on the post-wave-1 surface, a31bb5a9) | found: 9 (new: 9) — W2-F1 --check gate runs polluting the taxonomy population, W2-F2 attribution floor absent on windowed metrics, + 7 | wave 2 merged 597c8263 | → not done

Pass 3 (fresh finder, post-597c8263) | found: 10 (new: 10) — the ROOT LAW round: a delta computed against a baseline that never measured the field fabricates 0-baselined growth (S3 window-knowability, cross-version delta baselines, bump-day gaps) | wave 3 merged b7be8671 | → not done

Pass 4 (fresh finder, post-b7be8671) | found: 7 (new: 7) — W4-1 the windowed-delta guard (lifetime unattributed mass swamping a windowed value), killpg/reaper seams, marker persistence | wave 4 merged 3309608d | → not done

Pass 5 (fresh finder, post-3309608d) | found: 8 (new: 8) — W5-1 like-with-like: ONE window definition, value AND guard over the same day-scoped delta rows; W5-3 unknown-accumulator bootstrap; W5-5 the week recompute's mixed semantics named | wave 5 merged eb6679d7 | → not done

Pass 6 (fresh finder, post-eb6679d7) | found: 7 (new: 7) — W6-1 THE SINGLE-SOURCE LAW (weekly cells aggregate the published day series; three fabricated-cell shapes killed), W6-2 attributed bootstrap symmetry, W6-3 causes⊆verdicts, W6-4 measured no-derivation causes, W6-5 the LOCAL day window | wave 6 merged ce3424d9 (coder cancelled mid-run; verified worktree work finished by the orchestrator) | → not done

Pass 7 (fresh finder, post-ce3424d9) | found: 6 (new: 6) — W7-1 HIGH the trailing-window value published as a day point (weekly cells summed seven overlapping windows), W7-2 HIGH silent mid-week version truncation, W7-3 death-pair one-sidedness, W7-4 shrink-suppression reason, W7-5 visible smear, W7-6 coroner-quiet causes | wave 7 merged 05474580 | → not done

Pass 8 (fresh finder, post-05474580) | found: 4 (new: 4) — W8-1 HIGH the weekly rounds cell re-counting a multi-day session once per residency day (→ the single-source law's one carve-out: latest-per-sid recompute), W8-2 the smear annotating every normal consecutive-day baseline, W8-3 one-sided version bumps blinding split-week detection, W8-4 the missing multi-day-sid test shape | wave 8 merged 60c5de6e (implemented inline by the orchestrator after two coder 403 deaths) | → not done

Pass 9 (fresh finder, post-60c5de6e) | found: 7 (new: 7) — W9-1 the smear predicate keyed on the window edge instead of the row's own day (silenced real in-window gaps), W9-2 the carve-out cell discarding its measured detail, W9-3 the zero-current-days split week misdiagnosed as the pair contract, W9-4 the doc's series-consistency claim unscoped, W9-5 the pair note's k-of-N misdescribing halves, W9-6 note wording vs rule, W9-7 week-vs-day bootstrap divergence undocumented — all confined to the wave-8 carve-out seam; 7 classes swept clean incl. the import cycle (refuted) and latest-per-sid ordering (refuted) | wave 9 merged a8b12a68 (inline) | → not done

Pass 10 (fresh finder, post-a8b12a68) | found: 7 (new: 7) — W10-1 HIGH the W9-3 dash precedence masking the true pair-contract cause with a provably false split claim (regression), W10-2 disjoint current-definition halves publishing a mixed pair annotated as covering 0 days, W10-3/W10-4 doc rows/paragraphs stale vs the shipped carve-out and dash precedence, W10-5 unvalidated smear baseline operand, W10-6 the smear folded on unavailable paths, W10-7 zero-mass rows in the smear count — W9-2/W9-5 seams verified clean, version-bump completeness clean | wave 10 merged 99d3b977 (inline) | → not done

Pass 11 (fresh finder, post-99d3b977) | found: 7 (new: 7; severity collapsing — 1 MEDIUM, 6 LOW/wording) — W11-1 the smear's mass predicate wider than the pair's population mass, W11-2 the partial-overlap annotation sentence untrue for pairs (publish behavior adjudicated as accepted design, sentence fixed), W11-3 bootstrap double-report, W11-4 the orphan glob's silent fail-open now guarding a fabrication, W11-5 string-compare on date operands, W11-6 "disjoint definitions" misnaming disjoint day sets, W11-7 invalid-points weeks dashed as "no published days" — W10-1 predicate, SPLIT-vs-quiet masking, disjoint-gate predicates, annotate-skip, note punctuation, call-site filtering all verified clean | wave 11 merged 366a6608 (inline) | → not done

Pass 12 (fresh finder, post-366a6608) | found: 8 (new: 8; 3 MEDIUM confirmed — the bootstrap gate's mass asymmetry, the guard-dash folding a measured exclusion, the W11-4 warn unreachable because Path.glob swallows PermissionError — plus 1 re-raise of the partial-overlap publish REFUTED as adjudicated design, and 4 LOW wording/test-strength) | wave 12 merged de218fc0 (inline) | → not done

Pass 13 (fresh finder, post-de218fc0) | found: 7 raised → 5 in-scope (W13-1 the false "unreadable" warn on every first publish — real; a doubled halves line; dead _stops_mass with a stale gate claim; a deleted bound assertion; a root-hostile chmod test) + 2 OUT-OF-SCOPE (sibling rotation surface: claude_rotate call-site coverage, PATH-prepend scope — recorded for its owner, untouched per the shared-tree rule); iterdir-vs-glob equivalence, W12-1 value paths, boot_note ordering, gate headline all verified clean | wave 13 merged 4503a911 (inline) | → not done

Pass 14 (fresh finder, post-4503a911) | found: 2 (both LOW docs-accuracy — the split-week note shape, the bootstrap family-mass wording; SIXTH consecutive round with zero correctness defects) | wave 14 (doc-only) merged b03b0c0d | → not done

Pass 15 (fresh finder, post-b03b0c0d) | found: 2 (both LOW PLAUSIBLE regression-guard/disclosure gaps, zero live wrong outputs: the W13 standalone-line gating has no test — both failure directions stay green; a single-metric cell dashing for a non-bump reason during a split week discloses nothing about the split). Both wave-14 doc claims verified TRUE by probe; death-pair lockstep, empty-class-map measurability, empty-window, catchup rc/stamp, publish idempotency, per-half orphan logic all probed clean | wave 15 PENDING (operator pause: command-corpus gap takes priority; resume here) | → not done

Pass 15-fix + Pass 16 (fresh finder, post-645873ce) | wave 15 merged 645873ce (the two round-15 guards) | found: 4 (2 MEDIUM mutation-guard gaps ON the wave-15 additions themselves — the W13 double-fire direction untested, the new `not g_split` conjunct untested; 1 LOW doc line for the new third disclosure line; 1 LOW human-only upsert duplicate-row edge). W15-2's logic itself proved CLEAN by exhaustive conjunct probe | wave 16 PENDING (operator pause: command-corpus gap takes priority; resume here) | → not done

Core-layer classes (emitter, hooks, run-records, coroner, store atomicity, backfill, sensors, security) clean since pass 5 — findings from pass 6 onward confined to the weekly-aggregation seam waves 6–8 themselves introduced.

## Per-finding dispositions

Pass-1 triage (33 raised → 27 to FIX, 6 REFUTED):

REFUTED (proof quoted at triage):
- pool#1 _plan_era spine assumption — _read_head returns "" on OSError per candidate (kaizen_events.py); a missing spine file skips that candidate, never degrades the probe; the same-stem spine shape is gate-enforced.
- pool#2 _git_toplevel OSError→Path("/") fabrication — Path() construction never touches the filesystem; the fallback anchor's docs/development/plans is guarded by is_dir() → NOT_MEASURED, no fabrication path.
- pool#5 session_start guard tied to final_gate.py — deliberate T02 design (emit exactly where the Stop hook is armed; final_gate_stop.py is fleet-synced everywhere), documented in the T02 ledger.
- pool#7 probe_timeout 0 should mean no-timeout — contradicts the documented contract (non-positive → default); an unbounded git probe on the session hot path is the actual defect.
- pool#8 raw-sid inconsistency — finder's own text: harmless; resolve_sid sanitizes at the single point of use.
- pool#9 selftest env restore — speculative by the finder's own admission (var never set).
- breadth#3 command_run porcelain octal-quotepath — guarded by is_file(); worst case is a false REFUSE, the check's documented fail direction ("self-discipline, not a security boundary"); exotic-filename support is not promised. REFUTED.

TO FIX (dispatched, each red-first): H1 daily selector excludes active sessions + unknown.jsonl forever · H2 unclassified_rate fabricated 0% (+L8 folded: unknown-project is stratification, not unhealth) · H3 rule_activation fabricated 0% (honesty guard) · H4 hole_count counts healthy sessions · H5 liveness heartbeat satisfiable by the retirement nudge + coroner never scheduled (a plan miss) · H6 stale mechanical cells republished under fresh dates · M1 truncated lines counted complete · M2 coroner sid-naming idempotence break · M3 TTL closures invisible · M4 RS/US injection deflates rework · M5 run-record metrics over n=1 attributed (honesty guard; structural sid propagation recorded as residual) · M6 registry validated after state mutation · M7 noise-floor + series omit the 6 outcome metrics · M8 evidence_hash/cause silent drops · M9 death_class last-wins + fabricated 0/0 · L1 week filter after global collapse · L2 unreapable→rmtree crash · L3 inconclusive verdict closes live records · L4 sources not propagated to hole probe · L5 the hook's --check gate run must not define first_attempt · L6 store/series appends unlocked · L7 outcome metrics unwindowed · P1 _free_key collision · P2 waived[0] under-record · P3 exposure_override partial dict · B1 duplicate constant · B2 empty-corpus test.
