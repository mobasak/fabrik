# Code review — `db_before_boot` pre-provision machinery (changed surface)

Adversarial `/fabrik-review` of this session's `deploy.db_before_boot` fix (the D1 resolution):
`src/fabrik/orchestrator/__init__.py::_pre_provision_db_for_boot` + its `deploy()` call site +
`tests/orchestrator/test_pre_provision_db.py` + the `specs/services/zitadel.yaml` flag. Rubric injected via
`python scripts/review_rubric.py --changed src/fabrik/orchestrator/__init__.py tests/orchestrator/test_pre_provision_db.py specs/services/zitadel.yaml` (mandatory-core floor + matched packs). One native Opus finder + author-blind
grounding. Fixes committed `d097a26d`.

## Coverage Checklist

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | Correctness — gate/applicability | FIXED | #1: pre-provision ignored the `infra.postgres: false` override the registrar honors (`infrastructure.py:204`) → would create an opted-out DB. Now gates on `_enabled(infra,"postgres")` + a test |
| 2 | Correctness — name derivation | FIXED | #6: `None`-default parity — `name = ... or "unknown"` matches `infrastructure.py:413`; realistic name-first parity already held (round-1 #3) |
| 3 | Error handling | FIXED | `create_database` raises `RuntimeError`/`ValueError` (`postgres.py:130`), NOT in `deploy()`'s caught tuple → uncaught traceback + no rollback. Now wrapped → `ProvisioningError` (registrar contract) + a test |
| 4 | Secrets (zero hardcoding) | CLEAN | the `noqa`'d DSN password is a runtime CSPRNG value from `create_database`→`_generate_password` (`postgres.py:389`); host `@postgres-main` is the Fabrik shared-infra invariant, not app config (12-Factor clean) |
| 5 | Test coverage | FIXED | #2/#3: added tests for the dry-run DSN-seed guard, the `ProvisioningError` wrap, the `infra` override skip, and the `deploy()` call-site ORDERING (pre-provision before `deployer.deploy`). 10 tests total |
| 6 | Ordering / integration | CLEAN | `deploy()` calls pre-provision at step 2b (`__init__.py:161`) after `_load_secrets` (`:154`) before `deployer.deploy` (`:170`); pinned by `test_deploy_calls_pre_provision_before_deployer_deploy` |
| 7 | Idempotency / rollback | CLEAN | registrar re-call early-returns `exists`→no password→`.env` preserved (`deployer_ssh.py:593`); DB tracked for the rollback advisory (`ctx.add_resource`, round-1 #4a) |
| 8 | Recurrence sweep | CLEAN | #4 double resource-track ACCEPTED (harmless — success-path only, postgres rollback is advisory/non-destructive); #5 retry-after-partial is the already-documented S-RB/#4b manual-drop recovery; opt-in flag → byte-identical for every other service |

## Findings adjudication

- **#1 infra.postgres-override divergence** [MEDIUM] — FIXED (`d097a26d`).
- **error-handling: uncaught `create_database` failure** [author] — FIXED (`ProvisioningError` wrap).
- **#2 untested dry_run guard** [MEDIUM] — FIXED (test added; the guard itself was already correct).
- **#3 untested deploy() call-site ordering** [MEDIUM] — FIXED (ordering test added).
- **#6 `None`-default / "mirror EXACTLY" overstatement** [LOW] — FIXED (`or "unknown"` + docstring softened).
- **#4 double resource-tracking** [LOW] — ACCEPTED: occurs only on the success path (both pre-provision +
  registrar run), where rollback never fires; postgres rollback is an advisory manual-drop log, so the only
  effect is a duplicated WARNING that never actually runs. Not worth a dedup branch.
- **#5 retry-after-partial-failure** [LOW] — ACCEPTED/DOCUMENTED: this is the pre-existing registrar
  early-return-no-password behavior; the deploy plan's S-RB / #4b already documents the manual-drop-then-re-apply
  recovery. No new code owed.

## Pass Ledger

| Round | classes swept | found | fixed | new |
|------:|---|---:|---:|---:|
| 1 | correctness · secrets · test-coverage · error-handling | 7 | 5 (2 accepted) | 7 |
| 2 | correctness · secrets · test-coverage · error-handling | 0 | 0 | 0 ✓ |

Round 2 swept every class clean with 0 new findings — the no-op the contract demands.

## Gate

```
$ python -m pytest tests/orchestrator/test_pre_provision_db.py -q
10 passed
$ python -m pytest tests/orchestrator/test_infrastructure.py tests/orchestrator/test_states.py -q
........................  (all pass — the #1 gate change + error-wrap regress nothing)
$ python scripts/final_gate.py --json
status: failure | failed: 1
  Behavior Contract Proposal :: 2026-08-28-plan-1-canary-grounding.md — Given/When/Then missing
```

⚠️ **The sole gate failure is NOT this review's surface.** `2026-08-28-plan-1-canary-grounding.md` is a
concurrent session's plan, left `AM` (staged) in the shared index — a whole-tree false-positive that reds every
session's gate (memory: shared-master gate false-positives). I did not touch it (shared-tree rule); routed to
intel (fabrik-mail 01M1534H). This review's own changed files are committed clean at `d097a26d`; every check
above passes on them.

## Verdict

The `db_before_boot` machinery is correct and safe for the zitadel deploy: opt-in (byte-identical for other
services), applicability-consistent with the registrar, fails closed (`ProvisioningError` + rollback), and
covered by 10 behavior tests including the load-bearing ordering. **CLEAN.**

## BLOCKED: none
