# Review — 2026-08-13-plan-2-quota-rotation-v2

Scope: the whole-plan cumulative surface — `scripts/sysadmin/claude_rotate.py` + its AFTER-EDIT
twin `scripts/aro-wake/claude_rotate.py`, `tests/test_claude_rotate_v2.py`,
`tests/test_claude_rotate_capture.py`, docs rows, and the box-side `*/5` crontab tick.
Single-phase plan: this step-6 loop is the phase review and the whole-plan review.
Surface: HEAD=d15750d3c3de0d3281488532b86c1b6ffd11da1b · git-diff-md5=528a373bcc4d2bc460848487fe85afd9

Rubric run (Phase-0 step 2):

```
$ python scripts/review_rubric.py --changed scripts/sysadmin/claude_rotate.py tests/test_claude_rotate_v2.py
# FLOOR: core/35-security-auth · core/25-data-postgres · core/30-ops · 12-Factor
# MATCHED: core/10-python (stdlib-only tool, fail-open cron discipline)
```

The FLOOR's DB/HTTP-service rows are CONTEXT (this is a stdlib credential tool). The binding
classes are credential-safety + the standing recurrence set, adjudicated below.

## Phase A — verdict: CLEAN-CONVERGED ✅

Closing state: **found: 0, fixed: 0** on the current surface — the closing VERIFY re-ran every
live probe and the full suites after the last fix (57/57, gate 47/0, twin parity exact).
Four review rounds, four fix waves, 24 findings folded; two of them would have made the shipped
feature a silent no-op and one could have stranded the fleet's live credentials.

## Coverage Checklist

| Class | Verdict |
|---|---|
| credential-safety (single-use refresh tokens, atomic filing, lock coverage) | **FIXED(5)→CLEAN** — live-token guard (closer #1, T5e: zero-grant asserted) · writability pre-check before the grant (pool F1, T5d) · ROTATE_LOCK + unique tmp + secure probe on the filing path (#9) · outgoing-store capture before every tick switch (#3) · keep-warm-by-HTTP retired entirely (403/1010, T12) |
| fail-open vs fail-closed | **FIXED(3)→CLEAN** — `_account_status` missing windows now UNKNOWN not 0% (#6, T8) · failed switch falls through to drain (#4, T9) · always-exits-0 ENFORCED (#11, T10) |
| boundary/sentinel/prefix | **FIXED(2)→CLEAN** — grant host corrected to platform.claude.com + redirects refused (#2) · provenance flag replaces a synthesized email that mis-parsed dashless stores (#17) |
| second-writer / concurrency | **FIXED(3)→CLEAN** — selector re-validates FITNESS not just path (#7) · every switch writer ledgers the dwell clock (#5) · drain broadcast fire-and-forget so the tick flock is never held ~25 min (#8) |
| behavior-without-a-test | **FIXED(6)→CLEAN** — T8–T14 added for the classes the closer proved untested; T6 widened to catch os.killpg/signal.alarm/from-signal-import while ignoring prose (#17) |
| cost/quota accounting (the feature's own domain) | **FIXED(1)→CLEAN** — parked stores' 8h-expired access tokens read `unknown-parked` (eligible, ranked last) instead of INVALID; without it every sibling read dead within 8h and the pool collapsed to one account (live-observed on ob@ 18:26) |
| doc-truth | FIXED(2)→CLEAN — spec's keep-warm section + CHANGELOG corrected to the probed reality rather than left claiming a dead mechanism |

## Pass Ledger

| Pass | scope | finders | found | new | fixed |
|---|---|---:|---:|---:|---:|
| 1 (impl, pool) | the v2 diff | deepseek-v3.2-exp (scored 4) | 7 | 7 | 0 |
| — fix wave 1 | writability pre-check + provenance filing + T5c/T5d | — | — | — | 2 |
| 2 (wide, non-author) | whole surface + cross-file contracts + binary grounding | native Opus (died on an API error, RESUMED via SendMessage) | 17 | 16 | 0 |
| — fix wave 2 | 13 of 17 landed (#1–#9, #11–#13, #15, #17); #10/#16 adjudicated | — | — | — | 13 |
| VERIFY (live) | `--status` + forced-no-op tick on the fixed code | orchestrator probes | 2 | 2 | 0 (grant 403/1010 both hosts · parked-access-expiry collapse) |
| — fix wave 3 | keep-warm retired honestly + unknown-parked telemetry + T12–T14 + spec/CHANGELOG correction | — | — | — | 2 |
| — fix wave 4 | lint-ratchet debt from the waves (5 ruff errors, both copies + tests) | — | — | — | 5 |
| CLOSING VERIFY | live probes + 57/57 + ruff clean + gate 47/0 + twin parity | orchestrator | **0** | **0** | 0 → **CLEAN** |

`new:` trend 7→16→2→0 — strictly falling.

## Adjudicated (recorded, not fixed)

- **#10 fleet-sync window**: keep-warm was the mechanism that could invalidate other boxes'
  snapshots — retiring it (wave 3) removes the cause entirely.
- **#16 twin docstring drift**: closed by wave 3's verbatim re-lift (parity now exact, checked).
- **Operator-facing residual**: can@/mob@ onboarding logins remain (their stores hold dead
  refresh tokens); the tick treats them as parked-unknown until then.

## The decisive proofs

```
$ python3 -c "...POST /v1/oauth/token both hosts..."
https://platform.claude.com/v1/oauth/token → HTTP 403 error code: 1010
https://console.anthropic.com/v1/oauth/token → HTTP 403 error code: 1010   ← keep-warm is impossible by HTTP
$ python3 scripts/sysadmin/claude_rotate.py --status
  can-…  parked — quota unknown until used (refresh token valid)
  ob-…   parked — quota unknown until used (refresh token valid)
* sarp@ocoron.com  session 62% (resets Thu 21:29)   weekly 12% (resets Thu 10:59)
```

## Final gate (verbatim, sealing turn)

```json
{"status": "success", "tier": 2, "passed": 47, "failed": 0}
```
