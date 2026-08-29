# Whole-plan review — vps-claude-quota-governance (cross-phase, Finish step)

**Surface:** 3b43e281 · diff-md5 12ac1a60 (cumulative `188d8fc9..HEAD`, scripts/sysadmin/)
**Plan:** docs/development/plans/2026-08-29-plan-1-vps-quota-governance.md
**Status:** DONE — coverage-adjudicated exit, cross-phase seams sound

The three per-phase reviews (A: 3 rounds · B: 3 rounds · C: 2 rounds) caught the phase-local defects.
This pass reviews what only appears once the phases combine — the governor ↔ broker ↔ gate ↔
marshaller integration seams — via a native Opus finder over the whole-plan cumulative diff, plus a
re-derivation confirming pass.

## Pass Ledger

The checklist classes derive from the rubric — armed with `python3 scripts/review_rubric.py --changed`
over the plan's `## File Scope`:

```
$ python3 scripts/review_rubric.py --changed scripts/sysadmin/quota_governor.py \
    scripts/sysadmin/claude_broker.py scripts/sysadmin/incident_context.py
# FLOOR: core/35-security-auth · core/25-data-postgres · core/30-ops · 12-FACTOR (all axes)
```

- **Pass 1** (native-Opus integration finder over the cumulative diff — broker↔governor↔gate, return
  contract, capped()↔route(), the incident trigger, the config mirror): found: 2, fixed: 5 — MED #3
  (the incident trigger has no in-repo caller) and LOW #5 (the dashboard panel diverges from `route()`
  on drift).
- **Pass 2** (method: **re-derivation** — primary-source re-count, not a citation re-check: re-grepped
  every caller of `route`/`mark_capped`/`release_incident`/`IncidentMarshaller` repo-wide, re-ran the
  dashboard panel against `route()` on a drift payload, re-confirmed the broker `bypass` env reaches
  `claude-run.sh`): found: 0, fixed: 0 — the closing quiet round; the in-repo integration surface is
  clean and the incident trigger is cross-repo (filed to fabrik-lib).

## Seams verified SOUND (Pass 1 + re-derived Pass 2)

- **Broker ↔ governor ↔ gate:** broker calls `route("routine")`; on `pool` → the pool, else runs
  `claude-run.sh` with `CLAUDE_GOVERNOR_KIND=bypass` — no double-gating; the broker never runs
  `claude-run.sh` without bypass; no `pool` decision still hits ob@.
- **route() return contract:** `route("routine")` returns only `pool`/`ob@`; the broker treats `pool`
  as the sole shed. `claude-run.sh`'s `case` matches exactly `pool|pool-diagnose` → exit 75 and falls
  through (fail-open) on `ob@`/empty/unknown.
- **capped() vs route():** both key on `_is_capped(row)` → they agree; `bot.py` uses the lock-free
  `capped()` (no single-flight side effect per message).
- **Config mirror:** `_RESERVE_PCT` agrees (same env `QUOTA_RESERVE_PCT`, default 80).

## Coverage Checklist

| Class | Swept | Verdict |
|---|---|---|
| **fail-open/fail-closed** (standing) | the `claude-run.sh` gate FAILS-OPEN on governor error/timeout (claude runs); broker fails CLOSED on the tool-disable assertion; no seam re-opened a fail-open | CLEAN |
| **cost/quota accounting** (standing) | the routine-conservation path (route→gate→consumers, `bypass` for the broker) conserves ob@ quota end-to-end; the incident quota-wall path routes to pool-diagnose | CLEAN |
| **boundary/sentinel/prefix** (standing) | exit-75 sentinel handled by all 4 consumers; the `pool`/`pool-diagnose`/`ob@` return values are matched exactly at every seam (no prefix/partial-match) | CLEAN |
| **behavior-without-a-test** (standing) | the terminal `run_incident()` entry added this pass carries 2 tests (ob@ + capped branches); all 3 modules 51 tests total | FIXED |
| stored-and-never-read (producer w/o consumer) | MED #3 — the marshaller had 0 production callers. FIXED in-scope: added `run_incident()` + `diagnose` CLI (invocable); production trigger is the fabrik-lib watchdog — filed cross-repo (`01M17S35BG`, ack:required), documented in the runbook, noted in the plan's residuals. Companion orphans `mark_capped`/`release_incident` dormant-but-correct | FIXED (in-scope) |
| truthfulness (code advertising an unwired capability) | `bot.py` over-claim ("fix loop still runs via pool-diagnose") removed | FIXED |
| display↔logic divergence | LOW #5 — dashboard panel now sheds routine on the `mx is None` drift case, matching `route()`; verified (drift→pool, healthy→ob@) | FIXED |

## Gate

```
$ python3 scripts/final_gate.py --check --json   →  MY surface clean; residual reds are sibling-owned (kilo-benchmarks E741 4b085763, review-coverage hooks-index 1ab80afc — both concurrent sibling commits, files outside this plan's scope)
$ pytest tests/test_quota_governor.py tests/test_claude_broker.py tests/test_incident_context.py  →  51 passed
```

Exit: cross-phase seams sound; the one MED (incident trigger) resolved in-scope with the cross-repo
remainder filed to fabrik-lib; the one LOW fixed + verified. Pass-2 re-derivation raised **found: 0** on
the in-repo integration surface. Status: DONE.
