# Plan — quota rotation v2: --status telemetry + perishable-first daemon + graceful drain

Status: CONVERGED (2026-08-13 — /fabrik-plan-review: 3-pass solo loop (spec independently
4-pass-converged at dd79fe9a this hour; all cites re-verified fresh); pass 1: selector-under-
lock design upgrade (:299-311 TOCTOU-free), T6 pattern fix, fallback-coverage honesty; pass 2:
spec keep-warm delta made explicit; closing pass raised 0 / edits 0, md5
958b42a98e51f158f62a994d600f7146 start==end)
Date: 2026-08-13
Owner: infra (spec-fed: docs/superpowers/specs/2026-08-13-quota-rotation-v2-design.md, CONVERGED dd79fe9a, operator-approved)
Shape: monolith, single phase (~half-day; one repo script + AFTER-EDIT twin + tests + one crontab line)

## What we already agreed (spec-inherited — not re-derived)

- Endpoints (probed live, runnable fence in the spec): `GET api.anthropic.com/api/oauth/usage`
  → `five_hour/seven_day.{utilization, resets_at}` + `limits[]`; `GET api/oauth/profile` →
  email (the identity authority; gate shipped 765ed888 + twin 6edf83bd).
- **Perishable-first** successor (operator): eligible = valid identity-verified snapshot ·
  not walled either window · not the account being left; rank by soonest weekly reset;
  tie-break lower weekly% then session%; ≥30min hysteresis; auto re-entry on 5h reset.
- **Graceful drain** (operator): last eligible account ≥85% with no sibling → one fabrik-mail
  per mailbox-bearing repo ("reach a commit-and-push checkpoint; revives at HH:MM") + one
  operator Telegram; suppress stamp in `~/.claude/state/` (24h-class).
- Threshold default 95% (configurable, operator leaning 98%); switch only between daemon
  ticks — never process signals (**no pkill/kill anywhere — grep-enforced acceptance**).
- Keep-warm parked snapshots; zero-relogin steady state. Walled-token telemetry is a marked
  spec ASSUMPTION with a degradation path (last-seen cache + reset clocks).
- REJECTED (spec): Gemini vault/pkill; login automation; fabrik-lib `alerting/` (topology).

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `scripts/sysadmin/claude_rotate.py` | the ONLY build surface (plus twin): `_active_account` :152, `_activate_snapshot`/switch path :299-441, `_cmd_drift_check` + identity gate (`_live_email`/`_store_for_email`, shipped today), CLI modes :960-970 | read in full this session |
| AFTER-EDIT coupling | every edit lands in BOTH `scripts/sysadmin/claude_rotate.py` AND `scripts/aro-wake/claude_rotate.py` (header line 2; done twice today — 765ed888/6edf83bd pattern: lift blocks verbatim) | header :2 |
| refresh grant | CLI binary strings: `/v1/oauth/token` (console host); snapshots carry `refreshToken` + **`refreshTokenExpiresAt`** → keep-warm keys on REAL expiry, not a blind 24h. ⚠️ refresh CONSUMES the single-use token — the new pair must be written to the store ATOMICALLY with the identity gate, or a crashed refresh strands the account | binary grep + ob-store field dump this session |
| drain recipients | a repo can receive mail iff `/opt/<repo>/.claude/hooks/mail_notify.py` exists (`mail.py:157`, refusal :261) — enumeration = that scan, never a hardcoded list | `scripts/mail.py:157,261` |
| mesh-notify | `claude-sound.sh mesh-notify <sid> <cwd> <err>` — `/opt/*` gate, `MESH_NOTIFY_CMD` seam, 30-min suppress (invoked, never edited; READ-ONLY surface) | `claude-sound.sh:249-262` |
| state dir | `~/.claude/state/` — VM-cut-survivable (today's sweep work); daemon ledger + drain/keep-warm stamps live here | plan-1 executed today |
| tests | `tests/test_claude_rotate_capture.py` exists (capture seams); new tests extend the same import-by-path pattern | ls this session |
| `.windsurf/rules` | core/10-python (the tool is stdlib-only urllib — keep it), fail-open hook discipline for anything cron-invoked | select_rules ACTIVE set |
| crontab | box-side, one new line (`*/5` flock'd tick); box surfaces documented in hooks-index §2b pattern | crontab read this session |

## Design (settled)

All new code in `claude_rotate.py` (+ twin), three additions:

1. **`--status`**: for each store: profile+usage via the stored token → table
   `account · LIVE? · session% (reset) · weekly% (reset) · snapshot age · refresh-expiry`.
   Dead token → row shows `INVALID (relogin needed)`. Machine mode `--status --json` for the
   daemon and tests.
2. **`--tick`** (the daemon; crontab `*/5 * * * * ... claude_rotate.py --tick`, flock'd via
   `~/.claude/state/rotate.lock`): (a) usage-poll the LIVE account; (b) ≥threshold on either
   window → switch via `_activate_snapshot(selector=...)` with the perishable-first pick AS
   the selector callback — it runs UNDER the existing flock (`:299-311`), so poll→pick→install
   is TOCTOU-free against a concurrent manual `--switch`/aro-wake → mesh-notify one line;
   (c) drain check: no eligible successor AND live ≥ drain-threshold → fabrik-mail broadcast
   (enumerated recipients) + Telegram, stamped; (d) keep-warm: any parked snapshot within
   48h of `refreshTokenExpiresAt` → refresh via `/v1/oauth/token` (SETTLES the spec's named
   open item — expiry-keyed supersedes its provisional ≤24h blind cadence: fewer refreshes,
   each single-use token consumed only when genuinely near death), identity-gate the result,
   write new pair atomically (tmp+rename), keep `.prev`; failure → loud log, never a crash;
   (e) every decision one `note()` line (the sweep's no-silent-black-box discipline).
   Env knobs: `ROTATE_THRESHOLD` (95), `ROTATE_DRAIN_THRESHOLD` (85), `ROTATE_DWELL_MIN` (30).
3. **State ledger** `~/.claude/state/rotate-ledger.jsonl` (append-only: tick verdicts,
   switches, drains) — the audit trail + hysteresis source; survives VM cuts.

## Phase A — implement + prove (single phase)

1. **Red-first tests** (`tests/test_claude_rotate_v2.py`, seam-injected — fake usage/profile
   responses, fake clock, tmp state dir; watch each RED):
   - T1 successor policy: 3 eligible siblings → soonest weekly reset wins; tie → lower
     weekly%; walled/invalid/current excluded.
   - T2 threshold: 94% → no-op; 96% either window → switch invoked exactly once.
   - T3 hysteresis: switch at T then threshold again at T+10min → no second switch; at
     T+31min → allowed.
   - T4 drain: one eligible account at 86%, no sibling → broadcast list == mailbox-bearing
     repos (fake /opt tree) + Telegram called + stamp written; second tick → suppressed.
   - T5 keep-warm: parked snapshot expiring in 47h → refresh called; fresh one → not called;
     refresh response filed atomically + identity-gated (mismatched email → NOT filed, loud).
   - T6 no-signals guard: `grep -E 'pkill|os\.kill|signal\.' scripts/sysadmin/claude_rotate.py`
     → 0 matches (test asserts; same grep on the twin).
   - T7 --status --json shape: rows for valid + INVALID stores.
2. **Implement** `--status`, `--tick`, ledger + knobs in `scripts/sysadmin/claude_rotate.py`;
   lift verbatim into the aro-wake twin (AFTER-EDIT).
3. **Live probes** (read-only): `--status` against the real stores (expect sarp LIVE + ob
   valid + can/mob INVALID); one manual `--tick` with `ROTATE_THRESHOLD=101` (forced no-op
   path — proves the poll+note leg without switching).
4. **Crontab**: add the flock'd `*/5` tick line (box-side; backup crontab first per policy).
   ⚠️ NOT the sweep's cron pattern — this is a periodic tick, plain `*/5` + flock.
5. **Docs**: hooks-index §2b sibling row (cron tick), `docs/workstation/` pointer if the
   review demands; CHANGELOG entry; memory update (rotation-v2 → EXECUTED).
6. **/fabrik-review** on the full delta to a coverage-adjudicated quiet close; FULL gate;
   commit (repo files, pathspecs + trailers), push; DR backup (crontab is box-side).

Gates: `pytest tests/test_claude_rotate_v2.py tests/test_claude_rotate_capture.py` green ·
T6 grep zero · `python scripts/final_gate.py --json` success · `--status` live output matches
the store truth table established today.

## Risks / edge cases baked in

- **Refresh atomicity**: the single-use refresh token means a crashed keep-warm can strand an
  account → write-to-tmp + rename + `.prev` retained + identity gate BEFORE rename; on any
  doubt the old snapshot stays (a stale-but-unconsumed refresh token beats a consumed-and-lost
  one). T5 pins the mismatch path.
- **Daemon vs manual switch race**: closed BY CONSTRUCTION — the tick's successor pick runs
  as `_activate_snapshot`'s selector callback under the shared flock (`:299-311`, verbatim:
  "the selector runs under the lock … a concurrent rotation can't make two processes pick the
  same target"); the tick's own `~/.claude/state/rotate.lock` flock additionally serializes
  whole ticks.
- **Walled-token assumption** (spec): if a walled token stops answering usage, `--tick`
  degrades to last-seen cache + reset clocks from the ledger — the fallback path itself is
  exercised by T1's exclusion seams only indirectly; its LIVE verification is explicitly the
  mob@ Saturday onboarding (recorded, not silently assumed covered).
- **Drain false-fire during onboarding gap**: with only 2 valid accounts today, drain can
  legitimately fire — acceptable (it's true), Telegram says why.
- **No new MCP/deps**: stdlib urllib only (core/10 discipline; the tool already imports it).

## File Scope

Repo: this plan · `docs/development/reviews/2026-08-13-plan-2-quota-rotation-v2-review.md` ·
`scripts/sysadmin/claude_rotate.py` · `scripts/aro-wake/claude_rotate.py` ·
`tests/test_claude_rotate_v2.py` · `docs/workstation/hooks-index.md`.
(CHANGELOG/LESSONS stay OUT per the plan-lock grammar; steps remain.)
Box: crontab line (backed up first) · `~/.claude/state/` runtime files (not DR'd — runtime).

## Evidence

(Appended at execution; plan-time grounding = the spec's probes + this session's store/field
dumps + binary-string greps, all cited in the Context Ledger.)

## Self-audit

- Every design decision traces to the CONVERGED spec or an operator message this session;
  zero open questions ride into execution (the two spec open-items have named in-plan probes:
  refresh grant → T5's seam + a live probe at implement time; walled-token → degradation path).
- The twin-coupling obligation is a Context Ledger row, not tribal memory.
- Single writer: the tick funnels through the existing switch lock; no parallel credential
  mutation path is introduced.
