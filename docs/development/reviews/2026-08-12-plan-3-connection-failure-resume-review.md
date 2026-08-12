# Review — 2026-08-12-plan-3-connection-failure-resume

Scope: the box-side production surface `~/.claude/bin/claude-stop-decider.py` (DR-versioned, not
git) — the new `_retries_exhausted` helper + the no-role `type=system`/`subtype=api_error` branch in
`_tail_is_stalled` + 12 new self-test fixtures — plus the repo-side doc rows (hooks-index Stop
clause, CHANGELOG, LESSONS_LEARNT). Single-phase plan: the step-9 loop below is the phase review and
the whole-plan review.

## Phase A — verdict: CLEAN-CONVERGED ✅

Closing round: **found: 0, fixed: 0** — the pool's sole CONFIRMED refuted by 2292 live records, the
native closer CLEAN against 5094, no edits owed on the current surface.

Pool finder + native Opus closer, both dispositioned to a clean close. The design (structural
exhausted-retries key + connection-code discriminator) is validated against the LIVE corpus, not
asserted.

## Round ledger

| Finder | Verdict | Disposition |
|---|---|---|
| pool `deepseek-v3.2-exp` (scored 3) | 1 CONFIRMED (numeric `connection.code` missed by `isinstance(str)`) + 3 PLAUSIBLE (malformed-data speculation) | **REFUTED** — grounded against 2292 live `system/api_error` records: `connection.code` is ALWAYS a string errno (ENOTIMP/ConnectionRefused/ECONNRESET/FailedToOpenSocket/cert-error); a numeric code never occurs. The `isinstance(code, str)` guard is correct discrimination, not a false-negative. |
| native Opus closer | **CLEAN** | Verified against 5094 real records: 0 false deaths, 0 role-diversions (0 of 5094 carry `message.role`, so no precedence conflict with the assistant `isApiErrorMessage` branch), and **0 cases where `retryAttempt==maxRetries` was followed by assistant auto-recovery** — 10/10 exhaustion is a true give-up only manual resume clears, so the structural key IS the death signal. |

**Author-driven improvements from the grounding** (fixtures upgraded before the closer's pass):
the family fixtures now use the REAL codes the CLI emits (ConnectionRefused — not the errno
spelling `ECONNREFUSED`; FailedToOpenSocket; the cert error), documenting that the structural key is
code-agnostic; and a `connnoconn` fixture proves a `system/api_error` with NO `connection.code`
(the 2294 auth/rate/server records) is correctly NOT this class — the exact line between the
resumable network family and StopFailure's loud classes.

## The decisive proof (the real incident)

```
$ head -36370 <the iterative_image_editor 35204643 incident> | _tail_is_stalled  → True   (detected)
$ <the full current transcript, recovered>              | _tail_is_stalled  → False  (operator
  resumed manually at line 36371 — recovery-discrimination holds on the real data, not just fixtures)
```
E2E through `_run_hook_inner` (sandboxed, headless): the connfail transcript writes the
`api_error_stalled <epoch>` `.errparked` record the armed self-watch consumes + the class log line —
the mid-stream revival path inherited unchanged.

## Requirements coverage

| Requirement (plan § What we already agreed) | Verdict | Proof |
|---|---|---|
| Detect the whole connection-failure family, structural key not string allowlist | ✅ | `_retries_exhausted` + code-present branch; covers all 5 live codes incl. odd spellings by construction |
| Route into the existing revival (no new layer) | ✅ | same `stalled-api-error` verdict + `api_error_stalled` `.errparked`; E2E-proven; :966/:1039 unchanged |
| No false-death on non-exhausted / non-connection api_errors | ✅ | connfail2 (mid-retry) + connnoconn (no code) fixtures; corpus 2294 no-code records skipped |
| Recovery discrimination (operator resume suppresses) | ✅ | connfail4a fixture + the real recovered transcript stays False |
| Malformed guards never raise | ✅ | connbad1-3 (non-dict error/connection, non-int retry) green |
| Arming-gap diagnosed | ✅ | root cause found (advisory arm, session never complied) → Lesson 115 + recorded follow-up |
| No rotation coupling; only the decider edited | ✅ | zero switch code; DR diff = single box surface |

## Final gate (verbatim, run 2026-08-12 in the sealing turn)

```json
{"status": "success", "tier": 2, "passed": 46, "failed": 0}
```

Self-test suite 82→94 (12 red-first fixtures); mesh harness 114/114; DR pushed 20260812T211418Z.
