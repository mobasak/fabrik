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
