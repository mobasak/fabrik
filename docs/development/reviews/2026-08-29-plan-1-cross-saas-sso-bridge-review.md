# Whole-plan review — 2026-08-29-plan-1-cross-saas-sso-bridge

Execution review of the hub `product_entitlements_bridge` module + integration reference (Epic-2 hub
slice). Phase mode, 3 phases, all EXECUTED. Every phase ran a native-Opus authoritative review to a clean
round (auth/idempotency/teardown are the high-risk slices); the Finish adds a pool breadth layer over the
cumulative diff. 35 tests, gate green.

## Phase verdicts

- **Phase A (ZitadelClient + ZitadelGrantSource)** — FIXED then CLEAN. Native-Opus review (3 rounds) found
  + fixed 3 real fail-opens: a token-404 that mis-matched the idempotency string and swallowed an auth
  outage (now keyed on the DeleteAuthorization response phase+status), an inert circuit breaker (wrong
  `kind` values — must be `"429"`/`"5xx"`), and a session-teardown under-drain (offset-paging skipped
  sessions the deletes shifted forward — now re-query-from-front until empty, fail-closed page cap). 16 tests.
- **Phase B (reconcile_user_grants)** — FIXED then CLEAN. Native-Opus review (2 rounds) found + fixed a
  role-sharing phantom-audit (audit inferred products from role-subset membership — now the symmetric
  satisfied-transition, before-vs-desired) and an audit-before-mutation that a raising sink turned into
  paid-but-locked-out (now swallowed, best-effort). Mutation idempotency proven zero-on-unchanged. 13 tests.
- **Phase C (revoke_and_teardown + reference doc)** — FIXED then CLEAN. Native-Opus review found + fixed a
  single-product cache-bust fail-open (a full grant delete busts the WHOLE-user cache now, not one product)
  and a wrong `record_event` doc signature (a TypeError that best-effort audit would silently swallow → zero
  audit). 6 tests.

## Class verdicts

| Class | Verdict | Evidence |
|---|---|---|
| Fail-CLOSED access (GrantSource) | CLEAN | `product_access` propagates any client error (no try/except); `grant_source.py:30-39`; test `test_source_error_raises_never_returns_empty` |
| JWT mint / token cache | CLEAN | RS256 assertion iss=sub=userId, aud=issuer, kid header; cache refresh 30s early from pre-request `now`; `zitadel_client.py` `_access_token`; test `test_token_is_cached_across_calls` |
| Delete idempotency | FIXED | keyed on response `phase=="request" and status_code==404`, never a message substring; test `test_delete_authorization_does_not_swallow_token_404` |
| Circuit breaker | FIXED | kinds `"429"`/`"5xx"` match the registry; 429 records failure; test `test_breaker_trips_after_5xx_failures_then_fails_closed` |
| Session teardown (criterion #3) | FIXED | re-query-from-front until empty, fail-closed page cap; stateful-mock drain test + `raises_when_undrainable` |
| Reconciler idempotency | CLEAN | `desired_roles` sorted-set compare → zero mutation on unchanged; test `test_second_run_unchanged_makes_zero_mutations` |
| Per-product audit correctness | FIXED | symmetric satisfied-transition handles shared roles (no phantom); best-effort guarded; tests `test_shared_roles_*`, `test_raising_audit_sink_*` |
| Teardown cache-bust | FIXED | whole-user bust (`gate.revoke(user_id, None)`) after total grant delete; test asserts `("u1", None)` |
| Doc↔code accuracy | FIXED | `record_event` example corrected to the real keyword-only signature; all module signatures verified against code |
| Scope / cross-repo leak | CLEAN | File Scope hub-only; per-RP wiring dispatched, not executed |

## Finish — pool breadth pass (cumulative diff)

`fanout("review", 3 units, mode="read_only")` over the 4 modules — models deepseek-v3.2 / gemini-3-flash /
qwen3-max, recorded + scored to the flywheel. All findings **refuted** (no new real defect): empty-role
audit is by-design (no grant to audit); the delete→bust order + partial-failure are fail-CLOSED (raises →
caller retries, TTL-bounded); a roleKeys schema-rename would fail CLOSED (deny, safe) + is a documented
integration check; re-query-from-front catches sessions created mid-teardown; transport-as-`5xx`, `404`=gone,
and `expires_in` token math are correct. The refutations confirm the native rounds were thorough.

FINDERS: pool deepseek-v3.2 / gemini-3-flash / qwen3-max ×1 each + native Opus ×6 across the phases

Final round: found: 0, fixed: 0

## Gate

```
$ python scripts/final_gate.py --check --json
{"status": "success", "passed": 53, "failed": 0}
```

## BLOCKED: none
