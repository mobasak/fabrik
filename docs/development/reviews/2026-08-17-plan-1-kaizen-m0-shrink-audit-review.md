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
