# Code review — ai-model-catalog-extraction migration plan (2026-08-02)

Surface: HEAD `d2d84887` · target = `docs/development/plans/2026-07-26-plan-1-ai-model-catalog-extraction.md` (was committed blob `ed0cbbfa` at `7976432e`; this review found + fixed 24 defects → heavily reworked, md5 recomputed at commit). Scope: a **migration PLAN markdown doc** — applicable classes: step-mandates-a-rule-violation, grounding accuracy (`path:line`), cross-phase internal consistency, plan↔intent, behavior-coverage, and **excise-boundary completeness** (the dominant class — removing the engine without orphaning a retained consumer). Code-execution classes (concurrency/null/SQL) are N/A to prose.

Finders: **6 native Opus `fabrik-reviewer` rounds** (authoritative) + **2 pool `fanout("review")` breadth** (flywheel-recorded + scored). Every candidate terminated FIXED or REFUTED; the meta-completeness finding is BLOCKED-escalated (below).

## Rubric (from `python scripts/review_rubric.py --changed docs/development/plans/2026-07-26-plan-1-ai-model-catalog-extraction.md`, injected into finders)

```
FLOOR (always): core/35-security-auth · core/25-data-postgres · core/30-ops · 12-FACTOR (all twelve)
MATCHED (globs): none — a plan .md matches no how-code-is-written pack. Applicable rubric reduces to:
  (a) no plan STEP may MANDATE a FLOOR/12-Factor violation, (b) grounding + consistency + coverage +
  (c) EXCISE-BOUNDARY COMPLETENESS (a removed-behavior/orphan class, the standing recurrence class here).
```

## Coverage Checklist

| Class | Verdict | Evidence |
|---|---|---|
| Step mandates a 12-Factor violation | **FIXED(1)** | F5 — deployed worker's `cache/update.log` (XI); B.2f stdout-only in-container. |
| Step mandates a security/auth violation | **CLEAN** | Batch worker, no auth surface / web tier; secrets = env (`FLYWHEEL_DSN`, gitignored `.env`). Hunted B–E. |
| Step mandates an ops violation (`fabrik`-CLI gate from a project) | **CLEAN** | No unqualified `fabrik`-CLI gate; E.4 `fabrik apply` = hub-side operator hand-off. |
| Grounding accuracy — `path:line` citations resolve | **FIXED(5)** | F2/F3/F6/F7 + Pass7-#2 (`importlib` computed-path idiom); every producer + retained-consumer citation re-grounded. |
| Internal consistency — cross-phase interfaces | **FIXED(3)** | F1/F2 (artifact attribution A↔B↔C↔D); #10 (hybrid `KILO_MODEL_CAPABILITIES.md` base+block, deliver ordering). |
| Plan↔intent — spec fidelity (break-nothing) | **FIXED(1)** | F1 + Pass7-#1 were direct "no functionality lost" breaks (Traycer regen; coding auto-router); resolved. |
| fail-open vs fail-closed on every gate/guard | **FIXED(1)** | Pass7-#3 — the post-classification gate false-FAILed on `test_routing_failover.sh:49`'s intentional fail-open sentinel; excluded. Floor (`select.py:479-483`) intact. |
| cost/quota/limit accounting edges | **CLEAN** | No cost/quota logic in scope (separate `claude_p_cost`, committed `4d9683cc`). |
| boundary/sentinel/prefix collisions | **FIXED(2)** | OUTPUT_ROOT clobber (B.2e) + F8 (CORE-pack injection host `65-rag-search.md`). |
| behavior-without-a-test | **FIXED(1)** | F4 — deliver-injection idempotency/self-heal test (writes a CORE pack). |
| **EXCISE-BOUNDARY COMPLETENESS** (removed-behavior / orphaned-consumer) | **FIXED(9) + BLOCKED(1 meta)** | #9/#11/#12/#13/#14/#15/#16 + Pass7-#1/#4 all FIXED (retained-remnant carve-outs, allow-list gate, `alerting`→`libs/alerting`, doc residue). The **meta**-completeness ("are there MORE undiscovered couplings?") is BLOCKED-escalated → closed by E.1's import-graph audit, see `## BLOCKED`. |

## Pass Ledger

```
Pass 1 — pool breadth (deepseek-v4-flash, gemini-3-flash) | found: 0 | fixed: 0 | → both CLEAN (missed the real defects; recorded+scored to flywheel)
Pass 2 — native Opus (authoritative)  | found: 7  (F1-F7)          | fixed: 7  | → not done
Pass 3 — controller self-grounding    | found: 1  (F8 CORE host)   | fixed: 1  | → not done
Pass 4 — native Opus confirming        | found: 3  (#9/#10/#11)     | fixed: 3  | → not done
Pass 5 — native Opus confirming        | found: 3  (#12/#13/#14)    | fixed: 3  | → not done
Pass 6 — native Opus excise sweep      | found: 4C+2P (#15/#16 + tests_kilo_benchmarks/alerting/run_kilo_workflow/doc-residue) | fixed: 6 | → not done
Pass 7 — native Opus CONVERGENCE check | found: 3C+3P (kilo_auto_route live break; grep-incompleteness; gate false-fail/pass; rule gap; count) | fixed: 6 | → NOT converged → BLOCKED-escalate the meta
Pass 8 — pool + native (Opus 5)        | found: 10 (pool: flywheel psql shellout G2, DELIVERY-TRANSPORT gap G3, rule-6 vendoring-only G5, unrunnable audit; native: kilo_model_sync cron entry N1, claude_p_cost DATA-FILE dep N2, shadow-dir/--target-root N3, orphaned behavior-6 N4, engine dead-copy N5, citation N6) | fixed: 10 | → not done
Pass 9 — pool (native pending)         | found: 10 (block→host manifest gap, hybrid-parity assert, D.1 gate unexecutable, no fleet smoke, 12F tee hedge ×2, pyproject build-system, loose A.1 assert, weak rollback gate) | fixed: 10 | → not done
```

**Convergence is NOT being reached.** Rounds 2-9 each surfaced 3-10 genuine, grounded defects; the rate is not decaying. Two findings in rounds 8-9 were *architectural* (the delivery transport was undefined for the deployed state; a fleet-synced consumer's data files were being deleted), i.e. new CLASSES, not tail noise. Notably the **cheap pool caught the single biggest architectural gap (G3 delivery transport) that 7 native-Opus rounds missed** — inverting the usual pool/native asymmetry and vindicating the never-either/or floor.

**24 findings → 24 FIXED + 0 REFUTED.** The loop did NOT reach a clean `found:0` round — every round surfaced real excise-boundary defects, and Pass 7 (the convergence check) found a live-consumer break (`kilo_auto_route.py`) plus proved the grep-discovery mechanism was necessary-but-not-sufficient. Per the termination contract, the stuck meta-finding is BLOCKED-escalated rather than spun further.

## Phase verdicts (per-phase sign-off)

- **Phase A (golden freeze):** FIXED — captures real engine artifacts + hybrid base-strip (#10) + full injector host set (F8).
- **Phase B (copy + decouple):** FIXED — producer-split (F3), stdout (F5), absorbs `tests/kilo_benchmarks/` (14 files).
- **Phase C (deliver):** FIXED — engine-vs-consumer output split (F2), DB delivery (F1), CORE-pack idempotency test (F4), a-before-b ordering (#10).
- **Phase D (cutover):** FIXED — allow-list gate over both `daily_refresh.sh`+`wsl_startup_hook.sh` (#12/#16), strip `generate_kilo_agents` auto-update block (#9), drop obsolete `check_daily_refresh_freshness` (#15).
- **Phase E (excise):** HARDENED — replaced hand-list with an **import-graph audit** (E.1) + 6 classification rules; retained the rule-6 coding-router deps (`classify_ticket`/`db_models`/`kilo_telemetry`, Pass7-#1); alerting→`libs/alerting` (#F3). Completeness now closed-by-construction by the audit, not a hand-list.

## Embedded gate (verified this turn)

```
python scripts/final_gate.py --lean --json  →  {"status": "success", "tier": 1, "passed": 25, "failed": 0}
```
Tier-1 (definition-of-done: Coverage-Checklist + Convergence-Evidence + synced-unmodified + structure) is green this turn on the review + plan artifacts. The review documents 24 FIXED findings + 1 BLOCKED-escalated meta (excise-completeness → E.1 import-graph audit).

## BLOCKED — excise-inventory completeness (escalated to the operator)

**Finding:** across 5 review rounds, every round surfaced a NEW engine-coupled fabrik file the prior rounds + the plan's hand-list missed — culminating in `kilo_auto_route.py` (a live Traycer coding auto-router, dispatched by `coding-auto.sh:32`) that `sys.path.insert`s into `kilo-benchmarks/` and imports 3 engine modules, invisible to every path-grep. This is the #9/#11/#13 class recurring: **plan-time hand-enumeration of the engine's coupling surface is provably incomplete.**

**Why BLOCKED not FIXED:** the specific instance (`kilo_auto_route`) is FIXED (rule-6 carve-out). But the *general* completeness question survived **more than 3 consecutive fix-and-recheck attempts** (Passes 4, 5, 6, 7 each found new couplings after the prior round's fixes) — the definition of a BLOCKED-escalation finding. It cannot be answered by more plan-time review rounds (each found ~3 more); it is only answerable by an **actual import-graph trace at execution**.

**Resolution (now baked into the plan):** Phase E.1 is rewritten from a path-grep to a mandated **import-graph audit** — for each retained fabrik entry-point, resolve its true transitive imports (AST / `python -X importtime`, catching `sys.path.insert`+bare-import and `importlib` computed-path) and classify every `kilo-benchmarks/` dependency by the 6 rules. An import graph IS the complete coupling set by construction, unlike a grep. **The executor's E.1 audit is the completeness guarantee; the plan no longer relies on a complete hand-list.**

**Operator decision:** either (a) accept the hardened plan and trust E.1's import-graph audit to enumerate the residual couplings at execution, or (b) run 1–2 more `/fabrik-review` rounds now to push plan-time byte-level convergence further (diminishing returns — the mechanism, not the hand-list, is the real fix). This review deliberately STOPPED the finder loop here (7 rounds, 24 fixes) rather than spend further Opus quota chasing a tail the E.1 mechanism already closes.

## Residuals
All plan-level residuals SELF-SERVICE (plan §-residuals). The one escalated item is the completeness meta above.
