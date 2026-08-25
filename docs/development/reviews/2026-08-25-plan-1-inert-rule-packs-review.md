# Whole-plan review — 2026-08-25-plan-1-inert-rule-packs

Status: IN-PROGRESS

Cumulative surface: `git diff 4a9731ca..HEAD` across `scripts/`, `commands/`, `tests/`,
`.windsurf/rules/`, `docs/reference/`. Five Board units (T01, T02, T03, T04, T99), fifteen commits.

## Pass Ledger

| Pass | finders | found | fixed | refuted | notes |
|---:|---|---:|---:|---:|---|
| 1 | per-ticket rounds (pool 4 + native Opus ×2, T01/T04) | 22 | 6 | 6 | incl. a LIVE 48-repo fleet break |
| 2 | per-ticket round (pool 3, T02) | 9 | 1 | 2 | 7 overreach candidates weighed |
| 3 | orchestrator acceptance (T03) + T99 integration | 1 | 1 | — | T99 found a BLOCKING INDEX drift no ticket review could see |
| 4 | D7 whole-plan: pool 5 axes + native Opus authoritative | — | — | — | IN FLIGHT — exit NOT claimed |

`Finders: pool deepseek-v3.2-exp×1 + gemini-3-flash×1 + qwen3-max×1 + deepseek-v4-flash×1 — round 1`
`Finders: native opus×2 — round 1`
`Finders: pool deepseek-v3.2-exp×1 + gemini-3-flash×1 + qwen3-max×1 — round 2`
`Finders: pool ×5 + native opus×1 — round 4`

⚠️ **Exit NOT claimed.** Round 4 is still running; `found: 0, fixed: 0` has not been reached.

## What the plan closed, proven end-to-end

The class: rule-pack `globs:` were written for a **directory-per-concern** layout (`workers/`,
`auth/`) while the fabrik scaffolds emit **file-per-concern** (`worker.py`, `billing_routes.py`), so
a pack can be silently inert in every project it governs and nothing detects it. In transdoc that
cost 19 frontend calls to routes that did not exist, 14 endpoints with no caller, an empty beat-loop
body and a retention purge never run — while `final_gate` was green and 296 tests passed.

**The shipped check catches the original defect.** Replaying transdoc's exact pre-fix condition —
the directory-only globs still claiming `file-worker`:

```
=== the ORIGINAL defect, replayed: pre-fix globs + a file-worker claim ===
  FINDING: pack='core/75-workers-jobs.md' type='file-worker'
  -> caught: True
=== and the FIXED globs on the same claim -> no finding ===
  findings: 0
```

It flags the historical bug and goes quiet on the fix. That is the proof no individual ticket could
give.

## Requirements coverage (Finish step 3)

Every `## File Scope` path shipped with a commit; every `Interfaces.Produces` symbol exists:

```
✓ scripts/rules_match.py                     d388c9ef   ✓ rules_match.pack_matches_path
✓ scripts/enforcement/pack_layout_audit.py   d8ac7d31   ✓ rules_match.any_path_matches
✓ scripts/enforcement/check_pack_reachability.py d8aa4749  ✓ rules_match.packs_for_paths
✓ scripts/select_rules.py                    fec39417   ✓ pack_layout_audit.audit_layout
✓ scripts/review_rubric.py                   b589a1b8
✓ scripts/final_gate.py                      d8aa4749
✓ commands/_sources/fabrik-execute-plan.md   b589a1b8
✓ .windsurf/rules/core/75-workers-jobs.md    f562b49f
✓ .windsurf/rules/core/app-audit-log.md      f562b49f
✓ tests/… (4 files)                          d8aa4749 / d8ac7d31 / d4d3bafc
✓ docs/reference/rule-pack-reachability.md   d8aa4749
```

## Cross-ticket seam — proven in BOTH directions

One matcher, not three: `pack_layout_audit` and `check_pack_reachability` both import
`rules_match`; the check consumes `audit_layout`. Positive and negative control, per pack:

```
core/75-workers-jobs.md  claims ['file-worker']   · asked 'saas-skeleton' -> findings: 0
core/app-audit-log.md    claims ['saas-skeleton'] · asked 'file-worker'   -> findings: 0
positive: T02 reachable / T03 examined+reachable / T04 reachable -> AGREE
OVERALL_AGREE: true
```

The negative control matters: a positive-only proof cannot distinguish "the three agree" from "all
three say yes to everything". T99 added it; the orchestrator re-ran it independently.

## Coverage Checklist

| Class | Verdict | Evidence |
|---|---|---|
| fail-open vs fail-closed | FIXED | two instances: the audit's parser failed OPEN on legal YAML (`d8ac7d31`); the check's silent-on-absent row is made honest by printing its examined count |
| cost/quota/limit accounting | REFUTED | no metered call, no LLM dispatch, no quota surface anywhere in the plan |
| boundary/sentinel/prefix collisions | FIXED | the empty-pattern sentinel (deliberate True/False divergence + the inherited `/**` asymmetry, both pinned) and the `activation: manual` sentinel |
| behavior-without-a-test | FIXED | 31 tests across four suites, green together on the integrated tree; two dishonest tests found and strengthened |
| fleet-sync blast radius | FIXED | a 48-repo import break shipped and healed (`3f7b8bd2`); pack globs measured at 81 files/9 repos before accepting; corrected packs verified distributed to 48/49 |
| claims vs behavior | FIXED | THREE false docstring claims found and corrected — each a property nobody had executed |
| doc truthfulness | CLEAN | T99 verified every checkable claim in the reference doc by running it; no corrections needed |
| requirements coverage | CLEAN | every File Scope path and every produced symbol accounted for above |

## Residual, reported not fixed

1. **`/opt/fabrik-lib` is broken by this change and the fix cannot reach it.** It re-vendored the new
   `select_rules.py` at 2026-08-25 20:37 without `rules_match.py`; it is sync-EXCLUDED by design
   (`sync_enforcement_to_projects.py:795`), so the force-sync that healed the other 48 structurally
   cannot touch it. Reported via fabrik-mail with the one-line fix. **Cross-repo edits are a HARD
   STOP** — not fixed here.
2. **The class has no enforcement.** A synced/vendored script's IMPORTS are part of its surface.
   Nothing cross-checks a module-scope import against `fabrik_synced_manifest.py`, and fabrik-lib's
   own `check_vendored_drift.py` compares files it already vendors — it structurally cannot see a NEW
   file it should now be vendoring. This class has now fired twice in one day.
3. **`select_rules.py --changed` returns before the Kaizen M1 sensor block**, so that invocation
   emits no `rule_activation` event. Behavioral, possibly intended, undocumented.
