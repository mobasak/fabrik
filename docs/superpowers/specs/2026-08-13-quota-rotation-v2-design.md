# Design spec — preemptive quota rotation v2 (4-account Claude Max pool)

Status: DRAFT (operator approval → /fabrik-spec-review)
Date: 2026-08-13 · Owner: infra

## Goal

The 4 Claude Max 20x accounts (ob@, can@, sarp@, mob@ — can/sarp/mob are inbox-aliases of
ob@ocoron.com) operate as ONE continuous pool: agents never stop at a quota wall. Telemetry
(both windows + reset times per account) → preemptive in-place switch at threshold → zero
logins in steady state.

## Grounded facts (all live-probed THIS session, 2026-08-13)

1. **The quota endpoint — the whole telemetry problem is solved.**
   `GET https://api.anthropic.com/api/oauth/usage` (headers: `Authorization: Bearer <token>`,
   `anthropic-beta: oauth-2025-04-20`) returns per-account:
   `five_hour.{utilization, resets_at}` · `seven_day.{utilization, resets_at}` · a `limits[]`
   array with `{kind, percent, severity, resets_at}`. Live probe output (sarp@ 18%/4%;
   ob@ 95% session resetting 14:59Z, 72% weekly resetting 2026-08-19 11:59Z) captured in the
   session transcript. Works with any account's stored token — a WALLED account still answers
   (quota ≠ auth). Source: CLI binary string table (`api/oauth/usage`) + live probes.
2. **Identity authority**: `GET api/oauth/profile` (same headers) → account email. Already
   shipped as the drift-check identity gate (765ed888 + aro-wake twin 6edf83bd) after the
   2026-08-13 mis-filing incident.
3. **Switch semantics (live-proven today)**: in-place snapshot swap via
   `scripts/sysadmin/claude_rotate.py --switch` — running agents keep their in-memory token
   and lazily re-read the file on 401/expiry; zero prompts when the target snapshot is fresh.
   `login ≠ logout`; `/logout` is the only mass-relogin trigger. `claude login` is not a
   subcommand (in-app `/login`).
4. **Mass-relogin root cause (solved)**: single-use refresh tokens + stale/misattributed
   snapshots. Fresh, identity-verified snapshots switch silently.
5. **Wall state at writing**: sarp@ live (18%/4%) · ob@ 95%/72% · mob@ weekly-walled → Sat
   2026-08-16 11:00 · can@ weekly-walled → Mon 2026-08-18 11:59 (their stored tokens are dead
   → onboarding logins deferred; safe recipe below).

## Locked decisions (inherit, don't re-decide)

- The store layout (`~/.claude/manager-accounts/<name>/`), `claude_rotate.py` + its aro-wake
  twin (AFTER-EDIT coupled), the drift-check identity gate, the mesh (walls park/revive via
  `claude-quota.py`). v2 EXTENDS these — no parallel system.
- **REJECTED**: Gemini's static-vault + `pkill` design (stale single-use refresh tokens =
  guaranteed relogins; pkill kills 13 live sessions); login automation / operator inbox access
  (browser OAuth + 2FA — brittle, worse credential surface, and unnecessary).

## Approach (single — alternatives rejected above)

One new daemon leg + `--list` enrichment on the existing tool:

1. **`--status` / enriched `--list`**: for every store with a valid token, call `oauth/usage` +
   `oauth/profile` → table: account · live? · session % (reset) · weekly % (reset) · snapshot
   health. THIS answers operator wants #1 and #2 directly.
2. **Rotation daemon** (cron every 5 min, flock'd, state in `~/.claude/state/` — the
   VM-cut-survivable dir from today's sweep work): poll the LIVE account's usage; at
   ≥ THRESHOLD (default 95%, operator asked ~98% — configurable) on EITHER window, pick the
   healthiest sibling (lowest weekly utilization among un-walled, valid-snapshot accounts) and
   run the existing `--switch`. Telegram one line via the existing mesh-notify plumbing.
   Below-threshold: silent.
3. **Keep-warm**: same daemon tick refreshes each PARKED account's snapshot (the CLI token
   refresh flow) every ≤24h so refresh tokens never age out; each refresh is identity-gated
   before filing (shipped). Steady state: zero logins forever.
4. **Onboarding (deferred, operator-timed)**: for mob@ (post-Sat) and can@ (post-Mon):
   one-window `/login` → identity-gated capture fires → immediate `--switch sarp` back
   (~30s exposure; any turn that walls parks + revives via the mesh).

## fabrik-lib verdict

| Capability | Verdict |
|---|---|
| Telegram alert | VENDOR the existing mesh-notify path (already on the box) — no new module |
| cron/flock daemon | BUILD thin (≈150 lines in claude_rotate.py itself — no new file family); not a fabrik-lib candidate (single-box, credential-coupled) |
| usage/profile client | BUILD in-tool (stdlib urllib, ~30 lines, both endpoints already proven) |

## Requirements → acceptance

| # | Requirement | Acceptance |
|---|---|---|
| 1 | Per-account both-window % + reset times | `--status` table matches live probes for ≥2 accounts |
| 2 | Preemptive switch at threshold | daemon test: mock usage ≥98% → `--switch` invoked to healthiest sibling; below → no-op |
| 3 | Zero-relogin steady state | keep-warm keeps a parked account's token valid ≥7 days (measured); no login prompts across ≥3 daemon-driven switches |
| 4 | Never interrupt agents | switches are file-swaps only; no process signals anywhere (grep-enforced: no pkill/kill) |
| 5 | Survive VM cuts | daemon state + last-switch ledger in `~/.claude/state/`; @reboot-safe (flock; idempotent tick) |
| 6 | Identity safety | every write path behind the profile-endpoint gate (extends 765ed888) |

## Open items (named, non-blocking)

- `seven_day_opus`/`seven_day_sonnet` fields returned null on Max 20x today — re-probe under
  load in plan phase (per-model weekly windows may bind separately).
- Keep-warm refresh mechanics: the CLI refreshes on use; the daemon's refresh call for a
  PARKED token needs the token-refresh endpoint grounded in the plan (candidate:
  `api/oauth/claude_cli/*` family — probe, don't guess).
- mob@/can@ dead snapshots mean telemetry covers them only after onboarding.
