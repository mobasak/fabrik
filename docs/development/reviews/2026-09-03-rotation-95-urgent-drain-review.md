# Review — rotation per the operator's spec: 95% trip, 90% URGENT no-successor drain with the next-reset hook time (2026-09-03)

**Command:** `/fabrik-review` · **Trigger:** operator spec after three hand-rescues in one day and the instruction "do not act without understanding what we have, do not break what is implemented" · **Scope:** `scripts/sysadmin/claude_rotate.py` (+ byte-identical twin), `scripts/sysadmin/quota_dashboard.py`, `tests/test_claude_fleet.py`, `tests/test_claude_rotate_v2.py`, `tests/test_quota_dashboard.py`, three workstation docs, CHANGELOG, the ledger row · **Method:** NO-POOL, in-line finders; every claim executed · **Verdict:** CONVERGED — round 2 re-swept every class with 0 findings.

## Phase 0 — What we HAVE (read before touching), mapped to the spec

| Spec clause | Already implemented? | Changed |
|---|---|---|
| every 20 s check status | yes — the board's probe loop invokes the tick | no |
| at 95% session, switch | trip line was 98 (`_rotate_threshold`, board copy) | **98 → 95**, both copies, pinned equal by test |
| next account must have weekly AND session headroom | yes — `_flip_candidate_verdict` refuses walled / cap-walled / ≥threshold / no-5h-budget (target max 85) | no |
| closest weekly reset wins | yes — `_pick_flip_target` is perishable-first | no |
| we know the next account's session reset | yes — every row carries `five_hour.resets_at_epoch` (verified on live rows) | no |
| at 90% with no account available → URGENT mail: stop gracefully, hook to 1 min after the next session reset | the wall advisory existed (fires at the wall, generic text) | **new 90 tier** on the same advisory, latch and re-arm reused; the operator's words; `_next_session_relief` computes the instant |
| the mail must go out fast | the board only invoked the tick at the flip line | **drain tier at 90** on the board, own cooldown |

Measured before changing anything: at the moment of the report the picker had **zero eligible targets** (can 97 / sarp 98 session → "no 5h budget", mob weekly-walled); the tick had printed "NO successor has headroom" **38** times today; the inter-tick burn over **34** measured gaps is median 4, p90 10, max 16 — which is why 98 kept losing and why 95 alone would still have left today's state with nothing to switch to.

## Phase 1 — Finders

| # | Class | Candidate | Verdict |
|---|---|---|---|
| 1 | correctness | `_next_session_relief` picks a weekly-blocked sibling's session reset (useless — it would still be blocked) | **REFUTED by test** — session resets are considered only for siblings whose weekly is under cap and under 100; weekly-blocked siblings contribute their weekly reset only, as the fallback |
| 2 | boundary | a stale cached row with a reset in the past | **CLEAN** — skipped (`> now`), tested |
| 3 | boundary | the active account as its own relief | **CLEAN** — excluded by email, tested |
| 4 | fail-open | no sibling has any reset time | **CLEAN** — the mail still goes out with an explicit "no resume time can be given", tested |
| 5 | cooldown interaction | the board's drain tick at 90 blocks the flip tick at 95 for up to 120 s | **FIXED by design** — two independent cooldown slots (`_LAST_TRIGGER[0]` flip, `[1]` drain), tested: 91 then 96 with a 600 s cooldown fires both |
| 6 | contract | the localhost ban on my own message text (the board URL) | **FIXED** — the gate caught it (54/1); the URL is now env-derived (`QUOTA_DASH_URL` / host+port), which is also right: a literal would drift with the port |
| 7 | test-suite honesty | two fleet tests still pinned the dwell hold retired by D-104 and were RED AT HEAD since b74847fc | **FIXED and disclosed** — my earlier "116 green" ran `test_claude_rotate_v2` only, never `test_claude_fleet`; both rewritten to the dwell-exempt rule (the class they protect — no false alarm while a sibling has headroom — is unchanged; the mechanism of relief moved from "wait out the dwell" to "flip now") |
| 8 | not mine | `test_oauth_get_gives_up_after_attempts` expects 2 tries, measures 4 | **REPORTED, not guessed** — pre-existing at HEAD (re-run against HEAD's copy), my diff does not touch `_oauth_get` (grep 0), from a sibling's 627f8815; the two possible fixes are opposites and only the author knows which (01M1MG98SC90HB863AW18XJKQ6) |
| 9 | behavior-without-a-test | the message wording itself | **CLEAN** — pinned: URGENT, STOP YOUR WORK ASAP, GRACEFULLY, "1 MINUTE AFTER <acct>'s session window resets", the epoch, the `sleep` line |
| 10 | cost/quota | the 90 tier adds one tick per cooldown per crossing | **CLEAN** — the tick already runs every 5 min; at most one extra run per 120 s while ≥ 90 |
| 11 | twin | `scripts/aro-wake/claude_rotate.py` | **CLEAN** — byte-identical after the last edit |
| 12 | formatting | `claude_rotate.py` "would be reformatted" | **CLEAN, deliberate** — it was unformatted at HEAD; never `ruff format` such a file (append-only discipline); `ruff check` is clean |

## Phase 2 — Verify

Red on revert against HEAD's script: **7 of 8** new/rewritten fleet tests fail (the eighth is a negative guard that passes on old code by design). Suites: `test_claude_fleet` + `test_claude_rotate_v2` + `test_claude_rotate_capture` + `test_quota_dashboard` → **304 passed, 1 failed** (row 8). Twin `cmp` identical. ruff clean on all four changed `.py`; mypy clean on the dashboard.

## Phase 3 — Prove

```json
{
  "status": "success",
  "tier": 2,
  "passed": 55,
  "failed": 0,
  "skipped": 1,
  "skipped_checks": [
    "pytest"
  ]
}
```

Live after the restart: the board reports its two tiers from the running code, and one tick line shows the 95 line in force (recorded in the run report).

## Phase 4 — Converge

| Round | classes swept | found | new | note |
|---|---|---|---|---|
| 1 | correctness · boundary · fail-open · cooldown-interaction · contract · test-suite-honesty · behavior-without-a-test · cost/quota · twin · formatting | 3 | cooldown-interaction · test-suite-honesty | rows 5, 6, 7 |
| 2 (method: re-derivation) | the same ledger after the fixes: suites re-run, revert-proof re-run, gate re-run, twin re-cmp'd | **0** | — | TERMINAL |
