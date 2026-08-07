# Whole-plan validation review — 2026-08-07-plan-2-superpowers-adoptions

Validation of the two-phase monolith plan (executed in phase mode by the operator-carried session,
2026-08-07). Baseline `6b935492` (the convergence-flip commit) → final HEAD (post fix rounds).

## Phase verdicts (A · B · Finish)

| Phase | Deliverable | Boundary review | Verdict |
|---|---|---|---|
| A | watched-fail-first (CLAUDE.md §1 + 45-testing-strategy) + ad-hoc end-of-branch menu (§ EXIT) + AGENTS-compact mirrors | native Opus, 13 findings → all fixed in `67596027` (restore-to-green half, gated present-and-STOP menu, prospective scoping, rules-not-changelogs, pinned merge mechanics) | CLEAN |
| B | `commands/_fragments/repo-identity.md` + includes into catchup/upstream + master render | native Opus with live git probes, 8 findings → all fixed in `bfa49607` (normalized worktree test, MAIN via worktree-list porcelain, empty-TOP abort, submodule-own-identity, placement) | CLEAN |
| §Finish | cross-phase seams + requirements | native Opus whole-plan pass: 2 CONFIRMED at-distance breaks (upstream's orphaned manifest-presence antecedent + content-based hub test; EXIT clause's dirname-of-COMMON vs the fragment) → both fixed, confirming greps + re-render green | CLEAN after fix |

All four Behavior Contract rows verified on final text by the whole-plan reviewer (greps re-run).
Scope: 7 declared files + AGENTS-compact.md (justified synced-governance mirror, added by Phase A
review-fix; recorded here as the declaration the plan lacked).

## Embedded gate evidence (verbatim, this session, post-fix HEAD)

```json
{
  "status": "failure",
  "tier": 2,
  "passed": 43,
  "failed": 1,
  "failures": [
    {
      "check": "Spec <-> Project DB Name Match (Phase 1c)",
      "output": "spec <-> project DB-name DRIFT \u2014 the orchestrator will provision the spec-resolved name while the app connects to the project name:\n  \u2717 seo: spec resolves to 'seo' but project .env uses 'seo_dev'\nFix: set spec.depends.postgres to the project's DB name (or align the project's PG_DATABASE/DATABASE_URL), then re-apply."
    }
  ],
  "warnings": []
}
```

The single failing check is the concurrent sibling session's seo spec↔project DB-name drift (their
work — disclosed across this session's artifacts; not this plan's surface; operator decision filed:
rename the spec to `.yaml.draft` per the established mid-migration convention, or repoint
`/opt/seo/.env`). Every check touching this plan's files is green; corpus `--check` OK (24/24). The
embedded artifact above will be refreshed to a fully green run once that sibling item closes — until
then this document deliberately withholds the formal claim words the convergence checker keys on,
because the repo contract binds them to a green gate.
