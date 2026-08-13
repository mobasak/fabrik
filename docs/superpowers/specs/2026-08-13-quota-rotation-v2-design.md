# Design spec — preemptive quota rotation v2 (4-account Claude Max pool)

Status: CONVERGED (2026-08-13 — /fabrik-spec-review: 4-pass loop; probe re-run both passes
(sarp 26→27% live drift observed mid-review — the endpoint is real-time); walled-token claim
demoted to a marked ASSUMPTION with a degradation path; fabrik-lib alerting/ considered and
passed over on topology; perishable-first + graceful drain operator-settled. md5
b588e735a82207859af1b38294e9287c closing no-op. AWAITING OPERATOR APPROVAL)
Date: 2026-08-13 · Owner: infra

## Goal

The 4 Claude Max 20x accounts (ob@, can@, sarp@, mob@ — can/sarp/mob are inbox-aliases of
ob@ocoron.com) operate as ONE continuous pool: agents never stop at a quota wall. Telemetry
(both windows + reset times per account) → preemptive in-place switch at threshold → zero
logins in steady state.

## Grounded facts (live-probed THIS session, 2026-08-13 — the one assumption is marked inline)

1. **The quota endpoint — the whole telemetry problem is solved.**
   `GET https://api.anthropic.com/api/oauth/usage` (headers: `Authorization: Bearer <token>`,
   `anthropic-beta: oauth-2025-04-20`) returns per-account:
   `five_hour.{utilization, resets_at}` · `seven_day.{utilization, resets_at}` · a `limits[]`
   array with `{kind, percent, severity, resets_at}`. Live probe output (sarp@ 18%/4%;
   ob@ 95% session resetting 14:59Z, 72% weekly resetting 2026-08-19 11:59Z) captured in the
   session transcript. Runnable probe (email-safe, no token bytes printed):

```
$ python3 -c "import json,urllib.request,pathlib; t=json.loads((pathlib.Path.home()/'.claude'/'.credentials.json').read_text())['claudeAiOauth']['accessToken']; r=json.load(urllib.request.urlopen(urllib.request.Request('https://api.anthropic.com/api/oauth/usage', headers={'Authorization':'Bearer '+t,'anthropic-beta':'oauth-2025-04-20'}), timeout=15)); print({w: (r[w]['utilization'], r[w]['resets_at']) for w in ('five_hour','seven_day')})"
{'five_hour': (<pct>, '<iso>'), 'seven_day': (<pct>, '<iso>')}
```

   Source: CLI binary string table (`api/oauth/usage`) + live probes on two accounts.
   **ASSUMPTION (verify at first walled onboarding): a WALLED account's token still answers
   usage** (quota ≠ auth is expected, but both live probes used un-walled tokens; can/mob's
   stored tokens are dead so it is unprobeable today). If false, the daemon reads walled
   siblings' state from its own last-seen cache + reset clocks — design degrades, not breaks.
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
   ≥ THRESHOLD (default 95%, configurable toward the operator's ~98%) on EITHER window, pick
   the successor and run the existing `--switch`. Telegram one line via the existing
   mesh-notify plumbing. Below-threshold: silent.
   **Successor policy (operator-settled 2026-08-13): PERISHABLE-FIRST.** Eligibility gates:
   valid identity-verified snapshot · not walled on either window (live-probed) · not the
   account being left. Rank eligible siblings by **soonest weekly reset** (quota about to
   refresh is the cheapest to burn — use-it-or-lose-it economics); tie-break lower weekly %,
   then lower session %. Hysteresis: ≥30 min dwell unless the new account walls outright; an
   account rotated away from re-enters the pool automatically when its 5h window resets.
3. **Keep-warm — RETIRED at execution (live-probed 2026-08-13):** a script-side refresh POST
   to `/v1/oauth/token` returns HTTP 403 (Cloudflare 1010) on BOTH platform.claude.com and
   console.anthropic.com — the grant is CLI-only, and defeating that check is out of bounds.
   What actually keeps accounts warm: USE — the CLI refreshes live credentials in place and
   drift-check captures them, so any account the rotation visits stays warm against a ~30-day
   refresh-token life. A store parked longer needs one operator rotate-through.
4. **Onboarding (deferred, operator-timed)**: for mob@ (post-Sat) and can@ (post-Mon):
   one-window `/login` → identity-gated capture fires → immediate `--switch sarp` back
   (~30s exposure; any turn that walls parks + revives via the mesh).

### Graceful drain (operator-proposed 2026-08-13 — pool-exhaustion foresight)

When the pool is FORECAST to exhaust — the last eligible account crosses a DRAIN threshold
(default 85%) with no sibling to rotate to — the daemon broadcasts a **drain warning via
fabrik-mail** to every repo WITH a mailbox (mail.py refuses hookless repos — e.g. the watchdog): "pool exhaustion forecast ~HH:MM; reach a commit-and-push
checkpoint NOW, do not start new phases; work revives at HH:MM (earliest weekly/session
reset)." This needs NO new agent behavior: the commit-at-task-end law already defines the
checkpoint, and mail banners surface on every prompt AND background-task notification, so
mid-plan agents see it within minutes. Escalation: one Telegram to the operator with the same
forecast. At the actual wall, the existing park/revive mesh takes over; cleanly-parked
autonomous sessions are swept back at reset (Leg A markers). Acceptance: mock forecast →
drain mail lands in ≥2 repo inboxes + Telegram sent + no new mails on repeat ticks (24h-class
suppress stamp in `~/.claude/state/`).

## fabrik-lib verdict

| Capability | Verdict |
|---|---|
| Telegram alert | VENDOR the box's existing mesh-notify path. fabrik-lib `alerting/` WAS considered (README:15) and passed over on topology: its transport is SSH→VPS Apprise — wrong direction for a WSL workstation daemon; mesh-notify curls Telegram directly with per-target suppress already proven here |
| cron/flock daemon | BUILD thin (≈150 lines in claude_rotate.py itself — no new file family); not a fabrik-lib candidate (single-box, credential-coupled) |
| usage/profile client | BUILD in-tool (stdlib urllib, ~30 lines, both endpoints already proven) |

## Requirements → acceptance

| # | Requirement | Acceptance |
|---|---|---|
| 1 | Per-account both-window % + reset times | `--status` table matches live probes for ≥2 accounts |
| 2 | Preemptive switch at threshold | daemon test: mock usage ≥ threshold → `--switch` invoked to the PERISHABLE-FIRST successor (soonest weekly reset among eligible); below → no-op |
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
