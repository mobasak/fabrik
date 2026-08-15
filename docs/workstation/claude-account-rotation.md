# Claude account rotation — the 4-account quota pool

**What it is:** four Claude Max 20x subscriptions (`ob@`, `can@`, `sarp@`, `mob@` — the latter
three are inbox-aliases of `ob@ocoron.com`) operated as ONE continuous pool, so agents never
stop at a quota wall. Tool: `scripts/sysadmin/claude_rotate.py` (+ its AFTER-EDIT twin
`scripts/aro-wake/claude_rotate.py` — every edit lands in both).

## The one command you need

```bash
python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --status
```

Prints each account's session % / weekly % with reset times, marks the live one (`*`), and
flags any store whose credentials are missing or dead. Add `--json` for machine output.

## How a switch works (and why it doesn't interrupt anything)

`--switch <name>` swaps `~/.claude/.credentials.json` in place. Running sessions keep their
in-memory token and lazily re-read the file on 401/expiry, so **no window is interrupted and
nothing needs restarting**. Never `pkill` and never `/logout` — `/logout` is the only action
that forces every window to re-authenticate.

The `*/5` cron tick (`--tick`) does this automatically: at `ROTATE_THRESHOLD` (95%) on either
window it switches to the **perishable-first** successor (soonest weekly reset — quota about to
refresh is the cheapest to burn), Telegrams one line, and holds a 30-minute dwell so it can
never ping-pong. With no installable sibling at `ROTATE_DRAIN_THRESHOLD` (85%) it broadcasts a
**graceful-drain** fabrik-mail to every mailbox-bearing repo ("reach a commit-and-push
checkpoint; work revives at HH:MM") plus one Telegram, suppressed for 24h. Audit trail:
`~/.claude/state/rotate-ledger.jsonl`.

**Pausing the auto-switch** — `--pause-switch` drops a `switch-paused` marker in
`~/.claude/state/`; while it exists the tick installs NOTHING (it prints the withheld
successor instead) but keeps telemetry, keep-warm and the drain warnings armed — a paused
pool warns before the wall instead of silently hitting it. `--resume-switch` re-enables;
`--status` shows a `⏸` banner while paused. Use it whenever the successor pool is
unverified or known-dead: on 2026-08-15 an auto-switch would have installed a consumed
chain (a store whose single-use refresh token had already been spent while it was live)
box-wide, killing every session at once.

## Logins: when they are actually needed

Refresh tokens are **single-use but ~30-day-lived**, and the CLI rotates them on every real
use; each rotation is captured back into the account's store by the identity-gated
`--drift-check` (hourly + at every SessionStart). Therefore:

- **An account that gets used at all never needs a login.** Its 30-day clock resets on use.
- **Only a completely unused account expires.** Check `--status`; if one has sat idle for
  weeks, either switch to it briefly for real work, or log in once.
- **After a long idle (overnight, a pause), open ONE window first** and let it settle before
  opening the rest — 13 windows waking together race the same single-use refresh token, and
  the losers get a login prompt. This is the cause of the "why did it ask me to log in again"
  class, not a broken store.

`--touch <account>` exists to refresh a parked account without disturbing live sessions (an
isolated `CLAUDE_CONFIG_DIR` copy + one trivial `claude -p`). **It is not wired to cron**: on
the CLI version tested (2.1.231) the isolated run does not refresh — it writes a blanked pair,
which the mode's liveness gate correctly refuses to file. Re-evaluate when the CLI changes.

## Onboarding a new/relogged account

1. `/login` in any window as that account (the verification mail lands in `ob@ocoron.com`).
2. The identity gate captures it into the matching store automatically — it verifies WHOSE
   token it is via `api/oauth/profile` before writing, so a capture can never be mis-filed
   (the 2026-08-13 incident: a stale marker filed ob@'s tokens into the sarp/can stores).
   A store directory that exists but is empty is a valid onboarding target.
3. `--switch <the account you want live>` to return.

If the account is quota-walled, logging in is still safe — capture only needs auth, not quota —
but do it while no agents are working, or they will hit the wall until you switch back.

## Safety invariants (why credential loss is hard here)

- Every credential write is atomic (tmp + rename) under the shared rotation flock, and the
  previous pair is retained as `.credentials.json.prev` — that backup has already recovered a
  store damaged by a bad refresh.
- Nothing is filed without a POSITIVE identity verification, except a pair produced by the
  store's own refresh token (provenance), and never when the pair is structurally dead.
- The tick never sends process signals (grep-enforced in tests) — it cannot interrupt an agent.

**Known gap (2026-08-15, open):** the drift-check's identity gate skips ("live identity
unverifiable") when the live ACCESS token is expired at check time — over a whole live period
that means zero captures, the rolling chain exists only in `~/.claude/.credentials.json`, and
the next `/login` (which overwrites that file) destroys the account's chain. This is how can@'s
chain was lost overnight 2026-08-15 (store mtime stuck at Aug 11 through nine hourly checks).
Until fixed: before `/login`-ing a DIFFERENT account, run `--capture-current` so the live
chain is filed first.

## Cross-repo asks that reach the hub through mail

The drain broadcast is not the only mail traffic this pool creates: `--tick`'s graceful-drain
finding lands in every mailbox-bearing repo, and repos reply/ack through the same channel. The
mailbox is triaged with the same rule the rotation itself follows — **verify, then route by
beat**: a claim gets checked against the live system before it is relayed or acted on, and work
that belongs to another agent's beat (deploy/registrar → fleet, flywheel/model data → intel) is
handed over with the grounding attached rather than executed cross-beat.

## Related

- `docs/development/plans/archived/2026-08-13-plan-2-quota-rotation-v2.md` (the build)
- `docs/superpowers/specs/2026-08-13-quota-rotation-v2-design.md` (the design + rejections:
  no login automation, no static vault, no `pkill`)
- `docs/workstation/hooks-index.md` §2c (the cron tick row)
