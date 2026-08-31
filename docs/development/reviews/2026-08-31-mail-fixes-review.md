# Review — mail-driven fixes 01M1CM6G + 01M1CKEK (c6c983e7^..HEAD)

Status: CLOSED
Surface: c6c983e7^..0b267e2f — commits c6c983e7 (final_gate vulture whitelist, D-058), 1ef8d40f
(backlog row, docs-only), e0acb0d2 (redis envelope parse + no-green-exit, 01M1CKEK), 308c6f52
(round-1 review fixes), 547f46b3 (round-2 release lock), 0b267e2f (round-3 shared-analytics).
Invoked: routed UP from /fabrik-review-scoped per its own escalation rule (enforcement path
`scripts/final_gate.py` + 11 files > 5). Review-before-reply: the 01M1CKEK reply is held unsent
until this review's quiet round.
Dispatch note: pool finders were NOT used — `libs/subagents/` is a sibling session's live
uncommitted WIP (M on `__init__.py`, `_client.py`, `_dotenv.py`, `_transport.py`, `agent.py`,
`providers.py` at review time); exercising a half-edited module to record flywheel rows risks
false verdicts. Native `fabrik-reviewer` finders substituted (records nothing — accepted,
stated here per the advisory-WARN contract). Two first-wave finders died on the session quota
limit (reset 12:30am Europe/Istanbul); both were re-dispatched after reset — deaths recorded
in the Pass Ledger, per the finder-death contract.

## Coverage Checklist

| Class | Verdict | Evidence |
|---|---|---|
| driver-parse (envelope/flat, value shapes) | FIXED | unicode-digit ValueError escape, bool, " 7"/"+7" forms — `src/fabrik/drivers/redis.py::extract_assignments`; pinned `tests/drivers/test_redis.py::TestExtractAssignments` (8 tests) |
| range/boundary (index 0..15) | FIXED | out-of-range int rejection + `REDIS_LAST_INDEX` bound; pinned `test_out_of_range_index_rejected` |
| dup-index (double-booking) | FIXED | duplicate-index refusal names the services; pinned `test_double_booked_index_rejected` |
| version-guard (schema evolution) | FIXED | v≠1 envelope read refused (prevents silent downgrade-clobber); pinned `test_newer_envelope_version_refused`. Full unknown-key preservation REFUTED — version discipline is the adopted boundary |
| concurrency-lock (file_lock parity) | FIXED | `acquire_db_index` AND `release_db_index` wrap their read-modify-write in `file_lock("redis-assignments")` — the postgres parity the docstring claims; pinned `TestAcquireHoldsTheLock` ×2 |
| refresh-green-swallow | FIXED | `fabrik redeploy --refresh-infra` shared the green-exit swallow (the exact re-run path); exit-2 contract mirrored — `src/fabrik/cli.py`; pinned `test_refresh_infra_exits_2_on_failed_registrar` |
| shared-analytics-swallow | FIXED | the one swallow the first rewire left invisible (finder 3's delivered finding); `_nonfatal(ctx, "shared-analytics", e)`; pinned `test_failed_shared_analytics_is_recorded` |
| glitchtip re-raise contract | CLEAN | `except RuntimeError: raise` precedes the broad except — DSN-verify rollback path untouched, no double-record (`infrastructure.py::_provision_glitchtip`) |
| state persistence | CLEAN | `_persist_state` builds explicit fields; failed registrars correctly absent from `registrars_applied` (orchestrator/__init__.py:498-523) |
| persistence-roundtrip | CLEAN | envelope written with recomputed complement `free_indexes`; live-file fixture round-trips (`TestWriteRegistry`) |
| fail-open/fail-closed | FIXED | the whole surface IS this class: green-exit swallow closed on apply + refresh paths; registry parse fails closed on malformed values (`extract_assignments` raises, never guesses) |
| cost/quota accounting | CLEAN | no cost/limit surface in range; the review itself hit the session quota (2 finder deaths, re-dispatched — recorded in Pass Ledger) |
| behavior-without-a-test | FIXED | every adjudicated fix carries its pin — 23 tests across the three files; red-on-revert 9-fail proven at e0acb0d2's parent |

| glitchtip degraded early-returns | FIXED | no-DSN + no-app_name `return`s now record (SENTRY_DSN never injected = main promise broken); pinned `test_glitchtip_no_dsn_degraded_return_is_recorded` |
| postgres sub-role swallows ×3 | FIXED | watchdog-roles / payments-ingest / subagent-ins failures route through `_nonfatal`; pinned `test_postgres_watchdog_role_failure_is_recorded` |
| over-broad glitchtip fatal contract | FIXED | `except RuntimeError: raise` escalated ANY config error to full rollback; narrowed to dedicated `DsnInjectionError`; pinned `test_glitchtip_config_error_records_instead_of_rolling_back` |
| deploy_router alternate entry | FIXED | `_deploy_generic` success now denies on `registrar_failures` (was pre-01M1CKEK semantics); pinned `test_deploy_router_denies_success_on_registrar_failures` |
| failure-branch diagnostics | FIXED | ROLLED_BACK/FAILED branches print collected non-fatal failures (information-loss finding) |
| shared-analytics scope | FIXED | recording gated on watchdog applicability (`record_failure=should_run["watchdog"]`) — a watchdog-disabled spec no longer exits 2 on an analytics blip; pinned both ways |
| docs-factual-claim | FIXED | CHANGELOG red-on-revert wording now states the 9-of-then-11 measurement + today's 19-of-22 re-measurement (finder re-measured; my number was time-bound, not wrong at commit) |
| cli-test-coupling | FIXED | CLI tests use a tmp spec file, not the live `specs/services/tryton-crm.yaml` (click.Path(exists=True) fleet-churn coupling) |
| vulture-cwd-anchoring | FIXED | whitelist lookup anchored to `PROJECT_ROOT` (the module's own cwd snapshot) — coincidental-correctness removed |
| brittle-guard-test | FIXED | indentation-exact negative assertion replaced by the positive `run_cmd(_vulture_argv())` call-site pin |
| dry-run carve-out | REFUTED | a dry run that cannot read the registry FAILED to simulate — loud exit 2 is correct, silent green would repeat the original lie |
| state-file failure persistence | REFUTED for this change | real gap, but an 8-field G-F3 schema change deserves its own consumer sweep — routed to STRATEGIC_BACKLOG (`[fleet]` row, 2026-09-01) |

Finder deaths: both first-wave finders (orch-cli, gate-tests) died on the session quota limit;
both re-dispatched after reset and returned (9 + 4 candidates, adjudicated above — 10 fixed,
2 refuted-with-disposition, 1 backlogged).

## Rubric (verbatim head of `review_rubric.py --changed <the six code files>` — full output armed each finder prompt)

```
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3)

### core/35-security-auth.md
```

## Pass Ledger

| Pass 1 | method: gate | found: 8 | new: 8 | fixed: 6 | finders: redis-driver(native, returned) · orch-cli(native, DIED quota) · gate-tests(native, DIED quota, 1 finding delivered) · authority(self, returned) |
| Pass 2 | method: re-derivation | found: 1 | new: 1 | fixed: 1 | finders: authority re-sweep of the open ledger (release-lock-gap) |
| Pass 3 | method: citation | found: 1 | new: 1 | fixed: 1 | finders: gate-tests finder's delivered finding adjudicated (shared-analytics-swallow) |
| Pass 4 | method: re-derivation | found: 0 | new: 0 | fixed: 0 | finders: authority re-sweep of shared-analytics-swallow (call site + except + pin re-read) |
| Pass 5 | method: gate | found: 12 | new: 10 | fixed: 10 | finders: orch-cli(native redo, returned 9) · gate-tests(native redo, returned 4) · authority adjudication; 2 refuted, 1 backlogged |
| Pass 7 | method: re-derivation | found: 0 | new: 0 | fixed: 0 | finders: authority closing fresh pass — full uncommitted diff re-read, 30 tests green, gate green |

(Pass 6 was the round-5 ledger annotation recorded without new work — the run record holds both rows.)

## Gate

`python scripts/final_gate.py --check --json` (2026-09-01, closing pass): `"status": "success"` —
run read-only in this turn after the pass-5 fixes; verbatim single-field output: `success`.

## Terminal

Round 7: found: 0 · new: 0 · fixed: 0 — every class ledger row CLEAN/FIXED/REFUTED, both
re-dispatched finders returned and adjudicated. Totals across the run: 22 candidates raised,
18 fixed, 3 refuted with dispositions, 1 backlogged; commits e0acb0d2 · 308c6f52 · 547f46b3 ·
0b267e2f · c3fae730 + the closing commit.
