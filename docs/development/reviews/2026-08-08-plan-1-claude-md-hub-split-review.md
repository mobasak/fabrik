# Whole-plan validation — 2026-08-08-plan-1-claude-md-hub-split

Surface: commits `bee1eb31` (Phase A machinery) + `29176126` (Phase B content) + `e46bd7c5` (Phase C docs)
+ `3427b25f` (adjudication fixes) — the full cumulative diff of the CLAUDE.md hub/project split.
Native Opus finder seat + orchestrator adjudication (NO-POOL surface class: enforcement, scaffold,
CLAUDE.md, pre-commit config — declared in `3427b25f`).

## Coverage Checklist

| class | verdict |
|---|---|
| Distribution correctness (remaining hub-path consumers; src==dest assumptions) | FIXED(1 HIGH) — gitignore block name-list consumer; all pair-iterator consumers CLEAN |
| Lock / drift semantics (`synced.lock` writer + `check_synced_unmodified`) | CLEAN — dest-keyed, no repoint needed; pre-split local edits flag exactly as before |
| Hub contract truth (every factual claim in the new hub file) | FIXED(1 MEDIUM) — Sync-consciousness trigger surfaces now match the filter, which the row names as truth source |
| Test quality (real invariant vs proxy; revert reddens) | FIXED(1) — filter-swap guard added red-on-revert; source-inspection scaffold test noted as text-proxy, kept (fails safe) |
| Template content (nothing newly wrong project-side) | CLEAN — byte-identity held; pre-existing stale rows (wpf) filed as follow-up, not regressions |
| Pre-commit filter vs manifest surface | FIXED(partial) + FILED — the 5 high-churn gaps closed; ~30 pre-existing gaps documented as follow-up (same class as the `.claude/hooks/` gap, `41fa489a`) |

## Finding adjudication (7 from the finder seat)

1. **HIGH, CONFIRMED, fixed** — fleet `.gitignore` block dropped CLAUDE.md (name-list consumer
   `fabrik_synced_manifest.py::gitignore_dest_paths`); canary seen red → fix → fleet re-synced;
   `git check-ignore CLAUDE.md` → IGNORED verified on tojlo-mail, whatsapp-agent, meb,
   web-ecommerce-factory, seo. Lesson 106 recorded.
2. **MEDIUM, CONFIRMED, fixed** — hub row taught untrue trigger surfaces; filter extended
   (`fabrik_synced_manifest.py`, `sync_enforcement_to_projects.py`, `.claude/settings.json`,
   `.windsurf/hooks.json`, `agents-fabrik(-core).md`), row repointed at the filter + `--force` escape.
3. **LOW, pre-existing, FILED** — ~30 manifest paths outside the trigger filter (RUN_SCRIPTS,
   GOVERNANCE_DIRS, REFERENCE_DOCS legs, one stale filter entry). Follow-up, not this plan's scope.
4. **LOW, CONFIRMED, fixed** — `check_structure.py:28` comment staleness (scope-adjacent one-liner,
   disclosed in `3427b25f`).
5. **NOTE, addressed** — missing canaries: gitignore canary + filter-swap guard added
   (`tests/test_governance_template_split.py`, 6 tests).
6. **NOTE, FILED** — template carries pre-existing stale rows (wpf) protected by the byte-identity
   invariant; first real template edit fixes them and syncs cleanly.
7. **NOTE, recorded** — lock-writer laundering window on missing-source legs (pre-existing pattern,
   ~1 min exposure here, closed by the Phase C sync); a line for whenever the lock writer is next touched.

## Phase verdicts

- **Phase A** — machinery matches the plan (`GOVERNANCE_TEMPLATES` pair leg, unconditional yield, scaffold
  repoint `src/fabrik/scaffold.py:1148`, filter swap); 4 tests seen red first; commit sequencing held
  (no sync fired at A).
- **Phase B** — byte-identity proven end-to-end: `bee1eb31^:CLAUDE.md` == template == project files ==
  locks, all `20f25d8e7ee5d6cfda0cd025fd9ae919`; hub deltas present; `@agents-fabrik-core.md` + 6-line
  FINAL OUTPUT in both files.
- **Phase C** — docs truth-matched (`SYNC_ENFORCEMENT_WORKFLOW.md`, `docs/FEATURES.md:302`); fleet
  `--force` sync ×2 (Phase C + post-fix); `/opt/fabrik-lib/CLAUDE.md` untouched (`6ab88afc…`,
  mtime 2026-07-23).

## Round ledger

- Round 1 (finder seat, full surface): found: 7 — 4 fixable now, 3 filed follow-ups.
- Round 2 (fix pass + fleet re-sync + 5-project verification): fixed: 4.
- Round 3 (confirming pass, fresh: suites 37 green, ruff clean, yaml parse OK, gate re-run):
  **found: 0 · fixed: 0** — quiet.

## Gate (verbatim, run after `3427b25f`)

```
$ python scripts/final_gate.py --check --json
{
 "status": "failure",
 "tier": 2,
 "passed": 43,
 "failed": 1,
 "failures": [
  {
   "check": "Spec <-> Project DB Name Match (Phase 1c)",
   "output": "spec <-> project DB-name DRIFT — ✗ seo: spec resolves to 'seo' but project .env uses 'seo_dev'"
  }
 ]
}
```

The sole failure is the standing, disclosed, operator-owned seo spec↔env DB-name decision — pre-dating
this plan and untouched by it; the plan's own gate definition (Phase C step 5: "the standing 43/1 with NO
new failures") is met exactly. Formal claim vocabulary is withheld while that item stays open.

## Addendum (2026-08-09) — withholding condition CLEARED

The seo spec↔env DB-name item was closed on the operator side the same day. Fresh full gate:

```
$ python scripts/final_gate.py --check --json
{"status": "success", "tier": 2, "passed": 44, "failed": 0}
```

With the condition cleared, the withheld vocabulary is now stated plainly: the plan's whole surface is
**reviewed — sign-off**, per the checklist, the 7-finding adjudication, and the quiet round above.
