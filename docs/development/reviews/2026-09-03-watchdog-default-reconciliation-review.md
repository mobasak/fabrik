# Review — the watchdog default now agrees on both code paths (D-108, 2026-09-03)

**Command:** `/fabrik-review` · **Trigger:** operator ruling on fleet's three-option sizing — "make the model default match what apply already does, which changes no provisioning and closes the teardown gap" · **Scope:** `src/fabrik/spec_loader.py`, `src/fabrik/orchestrator/infrastructure.py`, `tests/test_spec_loader.py`, `docs/infrastructure/vps-ai-sysadmin.md`, `docs/STRATEGIC_BACKLOG.md`, `docs/DECISIONS.md`, `CHANGELOG.md` · **Method:** NO-POOL, in-line finders; the MIRROR rule applied first (name every shape the changed default breaks) · **Verdict:** CONVERGED — round 2 re-swept every class with 0 real findings.

## Phase 0 — What changed and why it is safe

`WatchdogConfig.enabled` flips `False` → `True`. The apply path never constructed that class: it reads raw yaml and has always fallen back to `True`. So **no live provisioning changes** — what changes is that `fabrik plan`, `audit` and the DESTROYER, which reach applicability through `model_dump()`, now report what apply actually creates. The destroyer replaying on the old `False` side was the sharp edge: a sidecar apply created could be called not-applicable at teardown and outlive its stack.

Population: **34 of 72** `specs/services/*.yaml` omit the block (re-derived this round), and **21** disable it explicitly — those are untouched.

## Phase 1 — MIRROR: every shape the changed default breaks

| # | Shape | Verdict |
|---|---|---|
| 1 | bare `WatchdogConfig()` — now enabled, so the caps validator applies | **CLEAN, executed** — defaults 1.0 USD / 200 invocations satisfy `_check_caps_set_when_enabled`; an explicitly uncapped enabled config is still REFUSED; an explicit `enabled=False` with zero caps still constructs |
| 2 | `test_default_values_match_subplan` — asserted the sub-plan's ten defaults verbatim | **FIXED with the supersession named** — one of the ten is now deliberately different; the test says which, and why, rather than quietly changing a number |
| 3 | `test_spec_default_watchdog_when_absent` | **FIXED** — flipped, docstring rewritten to state that this is the answer apply always gave |
| 4 | `test_post_merge_resolves_full_registrar_set` — asserted a shape-less python-api resolves to exactly four registrars | **FIXED (found by the run, not predicted)** — `watchdog` now appears in the set. Its ABSENCE was the defect being fixed, not the contract: apply provisioned a sidecar for exactly this spec while this assertion said otherwise. Docstring and message updated to say so |
| 5 | red-on-revert for all three | **PROVEN** — reverting the single field default reds all three assertions (3 failed); restored, 3 passed |
| 6 | docs carrying the old divergence | **FIXED** — `infrastructure.py`'s gate comment and module docstring (the comment that asserted the wrong default in the first place), `docs/infrastructure/vps-ai-sysadmin.md:68` (infra's corrected paragraph, now describing a resolved state), the backlog row marked RESOLVED with the two rejected options preserved |
| 7 | contract-supersession | **STATED** — the P2 sub-plan's `enabled: False` and the never-built `_register_watchdog` shape-kind dispatcher are explicitly superseded in the field description, the ledger row and the doc; option (c), encoding the kind matrix, stays open as the only remaining reason to touch this field |
| 8 | fail-open / boundary | **CLEAN** — no new I/O, no new branch; one field default and the comments around it |
| 9 | behavior-without-a-test | **CLEAN** — every behaviour that changed is pinned by one of the three flipped assertions, each proven red on revert |

## Phase 2 — Round 2 re-sweep

Re-derived rather than re-read: the 34/72 and 21 counts, the validator behaviour (executed, not reasoned about), all three suites (69 passed), ruff and mypy on the changed modules, the ledger shape (109 rows, 0 short, 0 over-wide).

One apparent finding was a **false positive of my own sweep**: a grep for stale "defaults to False" claims matched my own new paragraph, which narrates that history correctly. Recorded because a sweep pattern that cannot tell a current claim from its own history note will keep firing.

## Phase 3 — Prove

```json
{
  "status": "success",
  "tier": 2,
  "passed": 56,
  "failed": 0,
  "skipped": 1,
  "skipped_checks": [
    "pytest"
  ]
}
```

`skipped: 1 (['pytest'])` is this repo's permanent by-design skip — its CI does not invoke pytest, so the gate does not either. The three suites above were run separately and are reported as their own fact.

## Phase 4 — Converge

| Round | classes swept | found | new | note |
|---|---|---|---|---|
| 1 | correctness · mirror-shapes · fail-open · boundary/sentinel · behavior-without-a-test · docs-stale · contract-supersession | 1 | mirror-shapes | the registrar-set assertion, surfaced by running the suite rather than by prediction |
| 2 (method: re-derivation) | the same ledger: counts re-derived, validator executed, suites re-run, docs re-grepped | **0** (one self-matching grep, refuted) | — | TERMINAL |
