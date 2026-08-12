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

---

## Re-adjudication — operator /fabrik-review (2026-08-13)

Surface: HEAD=535d7dc28d9eba4b83e24e30a8164454b7d87db8 · git-diff-md5=d41d8cd98f00b204e9800998ecf8427e (clean tree; the substantive surface is
the box decider `~/.claude/bin/claude-stop-decider.py`, DR-versioned). Anchor: this report.
Rubric run (Phase-0 step 2):

```
$ python scripts/review_rubric.py --changed docs/workstation/hooks-index.md CHANGELOG.md docs/LESSONS_LEARNT.md
# FLOOR (always injected): core/35-security-auth · core/25-data-postgres · core/30-ops · 12-Factor.
# MATCHED globs: none (the git-changed paths are docs only).
```

The FLOOR auth/postgres/ops classes are CONTEXT, not target — a stdlib Stop-hook decider has no
auth, DB, or HTTP surface. The decider's real classes are the STANDING recurrence set the
termination contract names (fail-open/closed guards · boundary/sentinel/prefix · behavior-without-
a-test · cost/limit edges — the last N/A here), adjudicated in the checklist below.

Two fresh **non-author** Opus finders (neutral briefs — not the executor's framing), the confirming
independent round an operator's gate-invocation asks for after a self-declared CLEAN — a wide Pass 1
sweep and a closing Pass 2 full sweep on the fix.

### Coverage Checklist (re-adjudicated)

| Class | Verdict |
|---|---|
| fail-open vs fail-closed (, the system/api_error branch) | **FIXED(1)** — see F1 |
| boundary/sentinel (, bool/float/str coercion) | FIXED(1) — the coercion was the sentinel gap |
| precedence in the newest→oldest walk (recovery-discrimination) | CLEAN — verified vs 123 live exhausted records; every one operator-followed → False |
| behavior-without-a-test (new branch edges) | CLEAN — connfail/connbad/connfam/connnoconn + connbad4 cover every path |
| double-classification (assistant isApiErrorMessage vs system branch) | CLEAN — a system record has no message.role; role is checked first, no overlap |
| cost/quota/limit accounting (unknown≠0, per-call vs batch) | CLEAN — N/A: the decider spends no budget and calls no metered API; the only "limit" it reads is the CLI's own `retryAttempt`/`maxRetries` pair, adjudicated under boundary/sentinel above (unknown/garbage → fail-closed, not 0) |

### F1 — FIXED: `_retries_exhausted` coerced non-int retry counters toward a false death

Round 1's fresh finder reproduced: `"10"/"10"`, `True/True`, `9.9/9.1` each passed the old
`int(attempt)==int(mx)` and, with a connection code present, returned a `stalled-api-error`
death → auto-resume. PLAUSIBLE-but-unreachable (the live CLI emits int/int in 5094/5094 records),
but a false death is the worst outcome on this surface and it is the truthy-wrong-type class the
mid-stream plan closed — so FIXED, not refuted-on-unreachable. The helper now rejects `bool` (an
int subclass) and any non-`int` type before the equality (fail-closed). 3 red-first fixtures
(`connbad4`, watched RED). Real detection unchanged (int 10/10 still fires; 123 live death
records still covered — round 2 verified).

### Pass Ledger

| Pass | scope | finders | found | new | fixed |
|---|---|---|---:|---:|---:|
| 1 (wide, non-author) | `_tail_is_stalled` + `_retries_exhausted` + call sites + fixtures, vs 5094 live records | native Opus fabrik-reviewer ×1 | 1 | 1 | 0 |
| — fix | harden `_retries_exhausted` (reject bool/non-int) + connbad4 ×3 red-first | — | — | — | 1 |
| 2 (closing, non-author full sweep) | the fix + surrounding surface, vs 4586 live records | native Opus fabrik-reviewer ×1 | 0 | 0 | 0 → **CLEAN** |

Suite 82→97 (3 new coercion fixtures); mesh harness 114/114; DR pushed 20260812T234258Z.

```json
{"status": "success", "tier": 2, "passed": 46, "failed": 0}
```
