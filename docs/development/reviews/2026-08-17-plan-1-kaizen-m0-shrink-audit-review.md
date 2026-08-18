# Review ledger — 2026-08-17-plan-1-kaizen-m0-shrink-audit

Per-phase `/fabrik-review` rounds during `/fabrik-execute-plan`, followed (Phase C) by the
non-author closing sweep and the whole-plan review. Every finding terminates FIXED or
REFUTED — no deferred bucket.

## Phase A — evidence engine (`kaizen_shrink_audit.py` + tests)

Surface: `scripts/sysadmin/kaizen_shrink_audit.py` (new, ~560 lines),
`tests/test_kaizen_shrink_audit.py` (new, 14 tests). Not auth/schema/secrets — pool
finders per the dispatch policy; native adjudication (this orchestrator).

### Round 1 — 3 pool finders, partitioned failure classes

Finders: pool deepseek/deepseek-v3.2-exp ×1 + qwen/qwen3-max ×1 + google/gemini-3-flash-preview ×1 (errored: region 403) — round 1

| # | Finder | Finding | Disposition |
|---|---|---|---|
| 1 | deepseek | H: typed+skill same-line double count | REFUTED — channels are independent columns by declared plan design (plan § Phase A step 2); a user row carries no tool_use blocks |
| 2 | deepseek | M: quoted `"skill":"x"` prose could count | REFUTED — only a content block with `type=="tool_use" and name=="Skill"` counts; a text block never matches (locked by `test_transcript_invocations_counts_both_channels`) |
| 3 | deepseek | L: `errors="replace"` may corrupt a dirty row's JSON → skill undercount | REFUTED — inherent to the plan-mandated `errors="replace"` semantics; a corrupt row is unparseable evidence, not a fabricated zero |
| 4 | deepseek | M: ALL transcript files unreadable → measurable `{}` (fabricated zero) | **CONFIRMED → FIXED** — `files_read` counter; 0 readable → `Signal.unavailable("… none readable")`. Regression: `test_invocations_all_files_unreadable_is_unmeasurable` (seen RED first) |
| 5 | deepseek | H: substring false positives (`check_doc` counts inside `check_doc_sync`) | **CONFIRMED → FIXED** — boundary-aware `[\w-]` lookarounds. Regression: `test_check_activity_name_boundaries_prevent_substring_false_positives` (seen RED first) |
| 6 | qwen | H: liveness join-key mismatch drops verdicts silently | REFUTED as a code defect — not every artifact declares a liveness surface; `None` = no declared surface, stated in the Phase B report legend |
| 7 | qwen | H: `{typed:0, skill:0}` for an un-invoked command violates honesty | REFUTED — the transcript universe WAS scanned; a scanned-universe zero is an honest zero (legend states the corpus window) |
| 8 | qwen | M: same-basename artifacts in two classes silently share mention counts | **CONFIRMED → FIXED** — collision detection annotates `evidence_note` ("mention count shared with N other artifact(s)"). Regression: `test_audit_flags_shared_mention_keys` (seen RED first) |
| 9 | qwen | L: check-activity bad-fixture selftest is vacuous | REFUTED — misread: the empty-root branch returns `Signal.unavailable` before any counting |

3 CONFIRMED → all fixed with regressions proven red-first; 14 tests green + `--selftest` green after fixes.

### Round 2 — fresh sweep of the updated surface

Finders: pool deepseek/deepseek-v3.2-exp ×1 + google/gemini-3-flash-preview ×1 (errored: region 403) — round 2

| # | Finder | Finding | Disposition |
|---|---|---|---|
| 1 | deepseek | H: hyphen names break the boundary regex | REFUTED — by the finder itself mid-trace ("This is actually CORRECT behavior"); also locked by the boundary regression test |
| 2 | deepseek | M: shared-mention note fires when mentions are unmeasurable | REFUTED — the collision block is inside `if men.measurable:`; the scenario cannot execute |
| 3 | deepseek | L: scaffold types counted via the check-activity collector | REFUTED — the plan's declared design (§ Phase B step 2 legend: "scaffold types: scaffold-invocation greps"), boundary-aware and labeled in the report legend |

**Round 2: found 0 CONFIRMED, 0 PLAUSIBLE — clean round. Phase A review exit reached.**

Red-on-revert proof (plan § Phase A step 4): `_skill_names` neutered in place → 
`test_transcript_invocations_counts_both_channels` FAILED; restored byte-identical
(`cmp` clean) → 14 passed. The suite is discriminating, not decorative.

## Phase B — immune registry, verdicts, report

Surface: `kaizen_immune_list.py` (new), Phase B additions to `kaizen_shrink_audit.py`
(includes collector, cron-liveness join, verdict engine, report renderer), tests, the
generated report, doc rows (INDEX/kaizen.md/spec erratum/CHANGELOG).

### Round 0 — the author's own live-census sanity pass (before any finder)

The first real `--report` run listed **17 candidates**; three were absurd on sight and
each traced to a defect class, all fixed with regressions seen RED first:

| Defect | Failure it caused | Fix + regression |
|---|---|---|
| Fragments measured on ledger mentions | 6 actively-`{{include:}}`-ed fragments listed as deletable | `collect_includes()` — the render-time usage channel; `test_fragment_usage_is_include_references_not_ledger_mentions` |
| Cron liveness never joined (findings key on surface ids via `cron_match`) | provably-live crons (quota_dashboard restarted that same hour) fell to candidate on mentions-only | `_cron_match_map()` + `_best_verdict()`; `test_cron_liveness_joins_via_registry_cron_match` |
| Immune keys absolute-only | `liveness_audit.py` a candidate past its own immune entry | basename aliases in the registry; `test_immune_lookup_matches_relative_cron_forms` |

Post-fix census: **198 rows, 9 candidates** — every remaining candidate spot-verified
(the two fragments grep-confirmed never included; cron candidates carry honest
UNKNOWN/DEAD liveness cells the operator sees).

### Round 1 — 3 pool finders

Finders: pool deepseek/deepseek-v3.2-exp ×1 + qwen/qwen3-max ×1 + google/gemini-3-flash-preview ×1 (errored: region 403) — round 1

| # | Finder | Finding | Disposition |
|---|---|---|---|
| 1 | deepseek | H: rule packs with usage should be keep, not unknown | REFUTED — applicability is never usage (the plan's core premise); unknown-always for non-immune packs IS the design |
| 2 | deepseek | H: basename immune fallback could over-immunize a same-named artifact | REFUTED as live defect — no basename collision exists in the census, and the failure direction is keep (safe); mention collisions are separately annotated |
| 3 | deepseek | M: scaffold hits stored under a different key than read | REFUTED — `transcript_hits` on both sides (misread) |
| 4 | deepseek | M: no runtime guard on the verdict-token enum | **CONFIRMED → FIXED** — `render_report` raises `ValueError` on any token outside the enum; `test_report_refuses_a_row_with_a_decorated_or_missing_verdict`, proven red-on-revert |
| 5 | deepseek | L: `_best_verdict` may return None | REFUTED — None is the legal "no verdict" liveness value, handled by `_fmt`/`_usage_signals` |
| 6 | deepseek | L: `_CLASS_MEASURABILITY` undefined | REFUTED — defined in the Phase A section (finder saw a slice) |
| 7 | qwen | H×2 + M: ledger/transcript zeros must be `—` | REFUTED — re-litigates the settled scanned-universe-zero semantics (universe exists, legend states the window) |

### Round 2 — fresh sweep of the updated surface

Finders: pool deepseek/deepseek-v3.2-exp ×2 (one truncated output, re-dispatched with capture) — round 2

| # | Finding | Disposition |
|---|---|---|
| 1 | H: immune rows fall through without `continue` | REFUTED — the finder's "proposed fix" is byte-for-byte the shipped code; the `continue` exists |
| 2 | H: `cron_match.split()[0]` grabs the cron schedule field | REFUTED — `cron_match` is a script+args substring (`'claude_rotate.py --tick'`), never a full cron line (registry inspected before the join was written); locked by `test_cron_liveness_joins_via_registry_cron_match` |

**Round 2: found 0 CONFIRMED, 0 PLAUSIBLE — clean round. Phase B review exit reached.**
26 tests green + `--selftest` green; token guard proven red-on-revert.

## Phase C — the non-author closing sweep (whole plan surface)

Finders: pool deepseek/deepseek-v3.2-exp ×1 + qwen/qwen3-max ×1 + google/gemini-3-flash-preview ×1 (errored: region 403) + **native fabrik-reviewer (Opus, non-author, grounded itself live on the box)** — round 1

Pool round: qwen NO FINDINGS; deepseek's 7 all REFUTED on trace (the '"Skill"' string check is
a fast-path before structural parsing; same-basename cron merge fails toward keep with no live
instance; no Unicode names exist; git-timeout/mtime/crontab-scope/AST-shape all degrade to
VISIBLE honest notes by design).

**The native reviewer found what three pool rounds missed — 14 findings, 10 CONFIRMED by me,
2 PLAUSIBLE fixed defensively, 1 PLAUSIBLE resolved by declaring the boundary, 1 annotation.**
All fixed in one batch, every behavior-bearing fix behind a regression seen RED first
(10 new tests, 36 total):

| # | Sev | Finding (all grounded `path:line` by the finder) | Disposition |
|---|---|---|---|
| 1 | H | cron census keyed on the first `/opt/fabrik` token — `PYTHONPATH=/opt/fabrik/src` minted a phantom directory artifact and swallowed two LIVE crons (audit_authelia_gates, audit_all_registrars) | FIXED — `_cron_target()` prefers the first script-shaped token; `test_cron_census_prefers_the_script_over_env_assignments` |
| 2 | H | `check_mutation.py` (cron form) offered as a tickable deletion candidate while the SAME file rendered immune as a gate-check — immune keyed on stems, census key carried `.py` | FIXED — lookup ladder exact→basename→stem; `test_immune_lookup_reaches_the_stem_of_a_pathed_check` |
| 3 | H | hook liveness never joined (registry keys hooks via `evidence.command_contains`; the round-0 cron fix was left cron-only) — all five LIVE hooks rendered "declares no liveness surface" | FIXED — `_registry_surface_map()` covers cron_match + command_contains, join applies to cron+hook; `test_hook_liveness_joins_via_registry_command_contains` |
| 4 | M | 54% of transcript files (5,848 subagent sessions under `<proj>/<session>/subagents/`) never scanned — zeros described half the corpus while presenting as the whole | FIXED — `rglob`; `test_transcript_walk_includes_subagent_session_files` |
| 5 | M | mentions counted raw substrings — `fabrik-deploy`'s keep rested on 9 of `fabrik-deploy-plan*`'s mentions; the phantom `/opt/fabrik/src` row scored `ledgers:508` on the bare substring `src` | FIXED — boundary-aware longest-first alternation (same law as check activity); `test_mentions_are_boundary_aware` |
| 6 | M | 5 of 8 classes dropped SILENTLY when a registry was absent, against the docstring | FIXED — every unenumerable class earns a census note; `test_enumerate_notes_every_unenumerable_class` |
| 7 | M | the contract-5 test was vacuous — `text.count("\n| ")` included 17 non-data lines, passing on zero artifact rows | FIXED — counts `| \`` artifact rows, equality not ≥ |
| 8 | M/P | hook denominator is repo-local while 3 box-level hooks exist — scope undeclared | FIXED — the report legend now declares the census boundary (repo-owned artifacts; box-level hooks are liveness-audited, never censused) |
| 9 | L | `assign_verdicts` raised ModuleNotFoundError for file-location importers | FIXED — sys.path fallback around the sibling import |
| 10 | L | `assign_verdicts` not idempotent (duplicate immune justifications on re-pass) | FIXED — `_append_note` skips present notes; `test_assign_verdicts_is_idempotent` |
| 11 | L | `_cron_match_map -> dict[str, str]` annotation lied (returns lists) | FIXED — renamed `_registry_surface_map -> dict[str, list[str]]` |
| 12 | L/P | `collect_includes` unanchored while the assembler substitutes whole-line markers only | FIXED — `^…$` re.M; `test_includes_count_only_whole_line_markers` |
| 13 | L/P | observer effect: a session DISCUSSING the candidate list writes literal `<command-name>` echoes into transcripts via tool results, flipping candidates to keep on the next run | FIXED — typed channel is now structure-keyed like the skill channel (user-text only, tool_result/assistant echoes excluded); `test_typed_channel_ignores_tool_result_echoes` |
| 14 | L | `applicability_recent` counted deleted paths (75-workers-jobs: 15/15 recent matches were deleted files) | FIXED — recent ∩ tracked; `test_applicability_recent_counts_only_still_tracked_files` |

Post-fix: 36 tests green, `--selftest` green, ruff clean; census regenerated over the FULL
corpus (subagent files included) — verification rounds below.

### Verification round 2 — the same native reviewer, closure + fresh sweep of the fixes

All 14: **CLOSED** (each verified live by the finder — e.g. the DEAD verdict on
`audit_authelia_gates.py` traced to a 206h-old log against a 192h threshold: an honest
candidate, not a fix artifact; the sidechain sample showed 121/121 genuine operator rows
still counted). New findings: **5** — 1 M CONFIRMED (core-script liveness join missing — the
hook fix one clause short: `mail.py`'s DEAD digest surface never reached the operator),
2 L CONFIRMED (duplicate cron census notes; the contract-5 test gap), 2 L PLAUSIBLE
(sidechain briefs re-opening the observer effect; substring idempotency guard), plus the
2× wall-time observation (ACCEPTED as an operational fact: 3m07 measured full run, a fair
price for closing a 54% corpus blind spot — the finder concurred). Fixed red-first:
`test_core_script_liveness_joins_via_registry`, `test_sidechain_user_rows_are_not_typed_invocations`,
`test_unreadable_crontab_earns_exactly_one_note`, `test_append_note_dedupes_whole_segments_not_substrings`.

### Verification round 3 — closure check on round 2's fixes

Round 2's fix wave itself swept by the same finder: **3 CONFIRMED** — the split-on-`'; '` dedupe was defeated
by every justification containing `; ` (58 of 68 immune rows, measured ×3 duplication live);
the missing-class guard was a substring test a repo PATH could suppress (verified:
`…/my-hooks-repo/…` silently dropped the hook class's note); the shipped tests exercised
exactly the semicolon-free case. Fixed red-first: `_notes` list on the row (whole-note
equality, renderer-invisible), explicit `noted_classes` set, both tests rewritten with
semicolon-bearing members + the path-collision test.

### Verification round 4 — final closure

**ALL CLOSED, NO NEW FINDINGS** (the finder's own verdict, each closure verified live:
3-pass idempotency on semicolon members → 1 note each; the adversarial path now yields the
hook note; `_notes` proven absent from the rendered report). 41 tests green + `--selftest`
green, run in the finder's own turn. **The closing sweep is at its coverage-adjudicated
exit: found: 0, fixed: 0.**

## Coverage Checklist

Checklist classes derived from `python scripts/review_rubric.py --changed scripts/sysadmin/kaizen_shrink_audit.py scripts/sysadmin/kaizen_immune_list.py tests/test_kaizen_shrink_audit.py docs/workstation/kaizen-shrink-audit.md` (invoked 2026-08-19; floor packs 35-security-auth + 25-data-postgres injected into every finder frame) + the standing recurrence classes.

| Class | Status |
|---|---|
| Parser correctness (both invocation channels; structure-keying; encoding dirt) | FIXED(2 in Pass 1) + hardened; typed channel structure-keyed in Pass 6 #13; echoes/sidechains excluded (Pass 7 #2) |
| Measurement honesty (— vs fabricated 0; scanned-universe zeros) | FIXED(1 in Pass 1 #4); scanned-universe-zero semantics adjudicated and pinned in the legend; corpus widened to the full 11,270 files (Pass 6 #4) |
| Evidence-channel correctness per class (fragments=includes; crons/hooks/core-scripts=registry joins) | FIXED(3 in Pass 3) + FIXED(2 in Pass 6 #1/#3) + FIXED(1 in Pass 7 #1 — core-script join) |
| Census completeness / silent drops | FIXED(2 in Pass 6 #1/#6) + FIXED(1 in Pass 8 #2 — path-suppressed notes); every unenumerable class earns a note, phantom artifact eliminated |
| Immune contract (never a candidate; key-form drift) | FIXED(1 in Pass 3 #3) + FIXED(1 in Pass 6 #2 — stem ladder); enum guarded at render (Pass 4 #4) |
| Verdict-engine correctness (signal semantics, tokens, idempotency) | FIXED(1 in Pass 4 #4) + FIXED(2 in Pass 6 #10 / Pass 8 #1 — whole-note dedupe surviving semicolon justifications) |
| Report truthfulness (row coverage, legend vs code, ruling section) | FIXED(2 in Pass 6 #7/#8 — contract-5 test de-vacuoused, census boundary declared); 199 rows == census total asserted in-script |
| Test adequacy / behavior-without-a-test | FIXED(3) — the vacuous contract-5 assertion (Pass 6 #7), the semicolon test gap (Pass 8 #3), and every review fix landed behind a regression seen RED first; 41 tests; suite red-on-revert proven twice (skill parser, token guard) |
| fail-open/fail-closed | CLEAN — every collector fails toward an HONEST `—`-with-reason (never a fabricated measurement, never a crash): unreadable transcripts → unavailable (Pass 1 #4), unreadable registries → census notes (Pass 6 #6, Pass 8 #2), liveness/report/crontab read failures → `Signal.unavailable`; the sole raise is the render-time verdict-token guard, deliberately fail-closed on corrupt verdicts (Pass 4 #4) |
| Observer effect (the audit contaminating its own next measurement) | FIXED(2 — Pass 6 #13 typed-channel echoes, Pass 7 #2 sidechain briefs); verified live: 121/121 genuine operator rows still count, `fabrik-rules-review` stayed a candidate despite the reviewer's own contaminating rows |
| Operational cost | REFUTED as a defect (finder-concurred disposition) — full census 3m07 over 8.3 GB / 11,270 files (2 passes), a fair price for closing a 54% corpus blind spot; recorded, not hidden |

## Pass Ledger

| Pass | Finders | found | fixed | refuted/accepted |
|---|---|---:|---:|---:|
| Pass 1 (A round 1) | pool deepseek + qwen (+ gemini 403) | 9 | 3 | 6 |
| Pass 2 (A round 2) | pool deepseek (+ gemini 403) | 3 | 0 | 3 — clean round |
| Pass 3 (B round 0) | author's live-census sanity pass | 3 | 3 | 0 |
| Pass 4 (B round 1) | pool deepseek + qwen (+ gemini 403) | 9 | 1 | 8 |
| Pass 5 (B round 2) | pool deepseek ×2 | 2 | 0 | 2 — clean round |
| Pass 6 (C round 1) | pool deepseek + qwen (NO FINDINGS) + **native fabrik-reviewer (Opus, non-author)** | 21 | 13 | 8 (7 pool refuted on trace; 1 disposition-by-declaration) |
| Pass 7 (C round 2) | native verifier: 14/14 CLOSED + fresh sweep | 5 | 4 | 1 accepted (wall time) |
| Pass 8 (C round 3) | native verifier: closure + sweep of the fix wave | 3 | 3 | 0 |
| Pass 9 (C round 4) | native verifier: final closure | **found: 0** | **fixed: 0** | ALL CLOSED, NO NEW FINDINGS |

## Per-phase verdicts

- **Phase A** — evidence engine: EXECUTED f9e253b1; 2 finder rounds, 3 CONFIRMED fixed red-first, round 2 clean.
- **Phase B** — immune registry + verdicts + report: EXECUTED 9a98cde7; round-0 self sweep caught 3 evidence-channel defects before any finder; 2 finder rounds; clean exit.
- **Phase C** — receipt + non-author closing sweep: 4 verification rounds against a grounded native reviewer to `found: 0, fixed: 0`; census regenerated 3× as fixes landed (17→9 candidates, 198→199 rows — the phantom row replaced by two real rescued crons).

## Final gate

`python scripts/final_gate.py --check --json` (Tier 2, full), run 2026-08-19 after the Pass-9
close — top-level result verbatim:

```json
{
 "status": "success",
 "tier": 2,
 "passed": 45,
 "failed": 0,
 "blocking": 38,
 "failures": []
}
```

`check_convergence.py` green in the same run. Docs receipt: `docs_updater.py --check` exit 0
(the two stale-doc warnings — QUICKSTART 119d, CONFIGURATION 115d — predate this plan and
touch none of its files); per-file claim→proof: the report's own header claims (198→199 rows,
8 classes, 9 candidates) recounted against the rendered tables; kaizen.md § M0 claims each pin
to a named test; the INDEX row and the spec erratum verified against the tree (gate-history
absence re-proven at Phase A grounding). This whole-plan ledger is coverage-adjudicated,
closing at Pass 9: found: 0, fixed: 0 — the review is converged.
