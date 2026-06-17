# Archive — GPU rent + serverless shipped (2026-06-16 → 2026-06-17)

This directory holds the plans that drove the GPU surface from zero to production-ready across 3 providers (RunPod / Modal / Vast.ai), shipped in 7 commits over ~36 hours.

## Plans in this archive

| File | Status | Shipped in |
|---|---|---|
| [`2026-06-16-fabrik-gpu-rent.md`](2026-06-16-fabrik-gpu-rent.md) | ✅ SHIPPED — all 5 phases | Commits over 2026-06-16/17 (RunPod pod + serverless, then Modal + Vast drivers, then scaffold + reaper + metrics) |
| [`2026-06-16-gpu-serverless-phase-3-5.md`](2026-06-16-gpu-serverless-phase-3-5.md) | 📦 SUPERSEDED by converged | v1 plan; replaced by `*-converged.md` after iteration caught 4 critical bugs (`_app.stop` missing, `list_apps` import fail, wrong exception name, `/autogroups/` wrong path) |
| [`2026-06-17-gpu-serverless-phase-3-5-converged.md`](2026-06-17-gpu-serverless-phase-3-5-converged.md) | ✅ SHIPPED — Modal + Vast serverless | Commits `48b41ea` (Phase 3.5 wired) + `5a72cb4` (hardening with 5 LIVE gates) + `0397063` (doc sync) |
| [`2026-06-17-comprehensive-scenario-validation.md`](2026-06-17-comprehensive-scenario-validation.md) | ✅ SHIPPED — 13 CSV scenarios + 3 L-REAL live scenarios | Commits `dda3463` (CSV-1..13) + `946214f` (L-REAL-1..3 with pause/resume + Constraint 2 fix) |
| [`2026-06-17-daily-digest-fleet-hardening.md`](2026-06-17-daily-digest-fleet-hardening.md) | 📦 SUPERSEDED by converged | v1 plan; replaced by `*-converged.md` (in-flight, NOT archived) |

## What this work produced (final scorecard)

| Surface | RunPod | Modal | Vast.ai |
|---|---|---|---|
| **Pod** create→work→destroy | ✅ live (G-LIVE-2/3) | ✅ live (G-LIVE-7/8/9) | ✅ live (G-LIVE-5) |
| **Serverless** | ✅ live (G-LIVE-1) | ✅ live (LIVE-12 + LIVE-13 + L-REAL-3) | ✅ live (LIVE-14 + LIVE-15) |
| `--provider auto` routing | ✅ | ✅ | ✅ |
| `fabrik gpu status / destroy` | ✅ | ✅ | ✅ |
| `fabrik gpu reconcile --provider all` | ✅ (LIVE-16) | ✅ | ✅ |
| `fabrik gpu pause / resume` | ✅ pause (resume best-effort) | ❌ Modal stateless (raises NotImplementedError) | ✅ full pause/resume cycle |
| Reaper C4 tag-safety | ✅ | ✅ (LIVE-17) | ✅ (LIVE-17) |
| `final_gate.py --lean --json` | ✅ status=success | | |

**Total live spend across the entire arc: ~$0.20.** Total credits remaining at archive time: Modal ~$29.95 / RunPod $9.92 / Vast $9.98 = **~$49.85** of $50 starter credits.

## Convergence methodology that made this work

Every plan in this archive went through 3–4 rounds of audit-before-execute:

1. **v1** written with assumed APIs (typically caught 4–8 critical bugs that would have wasted real spend)
2. **Iter 2**: parallel agents audited every claim against actual code
3. **Iter 3**: bugs fixed, binding rules from `.windsurf/rules/` mapped, gates embedded
4. **Iter 4** (when needed): final scan for residual unknowns (caught hallucinated template hashes)

**No commit ever happened without `scripts/final_gate.py --lean --json` returning `status: success`.**

## What's NOT archived (still in `plans/`)

- `2026-06-17-daily-digest-fleet-hardening-converged.md` — fleet digest routing for vps1/vps2/vps3 (plan CONVERGED, implementation NOT yet started)

## Backlog items surfaced during this work

Documented in CHANGELOG.md but not yet planned:

- **Modal pod-mode `keep-on-failure`**: `app.run()` is process-scoped — can't survive CLI exit. Would need rewrite to `modal deploy` programmatic.
- **RunPod resume after SECURE pause**: GPU slot can be released — resume isn't guaranteed. Mitigation: persistent network volume.
