# fabrik-mail — the box's AI-to-AI message channel (workstation view)

Box-level operational reference for **fabrik-mail**, the durable messaging channel between the Claude
sessions on this WSL box (hub `/opt/fabrik`, the ~46 `/opt/*` projects, and `fabrik-lib`). This is the
*operator/box* view — where it lives, what runs, how it distributes, how to observe it. For the **agent
usage protocol** (message format, send/ack/reply, star topology, claim-before-work) see
[`docs/reference/fabrik-mail.md`](../reference/fabrik-mail.md).

## What it is

A repo-to-repo mailbox: a session in one repo can leave a durable message for another repo's sessions,
whose next session surfaces it automatically and acts under its own gates. Zero always-on infra — just
files on the shared box. It replaced the operator-as-transport pattern (hand-relaying between windows).

## Where it lives

```
/opt/fabrik-mail/<repo>/
  inbox/      <ULID>.md    unread + claimed-pending
  archive/    <ULID>.md    acked/resolved — append-only audit trail
  malformed/  <ULID>.md    quarantined (frontmatter wouldn't parse)
```

`<repo>` = the `/opt` directory name (`fabrik`, `tryton-crm`, `fabrik-lib`, …). Root overridable via
`FABRIK_MAIL_ROOT` (default `/opt/fabrik-mail`); the `/opt` base for recipient validation via
`FABRIK_OPT_ROOT` (default `/opt`). **`/opt/fabrik-mail` is a DATA store, not a project** — it is in
`sync_enforcement_to_projects.py::exclude_folders`, so the governance-sync never adopts it (it did once,
2026-08-12, before the exclusion — see the [drift note](#operational-facts)).

## Components (three, all box-local)

| Component | What it is | How it reaches every repo |
|---|---|---|
| `scripts/mail.py` | the CLI + protocol (`send`/`list`/`read`/`ack`/`requeue`/`digest`) | synced via `fabrik_synced_manifest.py::CORE_SCRIPTS` → each project's `scripts/` |
| `.claude/hooks/mail_notify.py` | the surfacing hook (SessionStart + UserPromptSubmit) | synced via `AGENT_HOOK_FILES` → each project's `.claude/hooks/` |
| the digest (a hub crontab line) | operator-visibility — unacked traffic → Telegram | hub-side only; lazy `libs.alerting` import, hub-guarded |

`fabrik-lib` is **sync-excluded**, so it was provisioned by an operator-relayed request (the item-6
cut-over, done 2026-08-12, commit `e714514` in fabrik-lib) — it copied `mail.py` + the hook and merged
the settings wiring itself.

## Two layers

- **Layer 1 — fabrik-mail (this doc):** durable, file-backed, **repo-to-repo**. Survives restarts; the
  archive is the audit trail. Use for cross-repo requests/findings and "leave it for whoever picks it up."
- **Layer 2 — native Claude Code cross-session messaging** (`SendMessage`/`ListAgents`): live,
  **session-to-session**, same-machine socket. Needs Claude Code ≥2.1.224 **AND** a server-side feature
  flag. The box is on ≥2.1.224 but the flag may be off — **probe `/list-agents`; if unrecognized or
  `CLAUDE_CODE_MESSAGING_SOCKET` is empty, it's off** and sessions coordinate via the shared inbox +
  plan-locks meanwhile. Composition: **socket = live notification, file = durable truth.**

Sessions in ONE repo share ONE `<repo>/inbox` (a claim-once queue) — fabrik-mail deliberately does NOT
sub-address individual sessions; that's Layer 2's job. Claim-before-work: `claim` up front (the
inbox→archive rename is the lock, and unlike the retired ack-up-front pattern it asserts NO
disposition — the file carries none until the work is actually done); `ack` resolves it later;
`requeue` re-opens a claimed message and strips a stale `acked-by:` marker if one is there.

## Keeping the queue readable

**The rule is HANDLE-NOW: a message you open, you finish in the same session** — read, validate the
claim against the code yourself, do the work, reply, `ack`, archived. Not in 7 days, not in 14.
`ack <id> --disposition done|blocked|wontfix` works on *every* message (it never inspects the `ack:`
field), so `ack: no` mail exits the same way; if it is not yours, `ack` it `wontfix` naming the owner
or relay it, but it does not sit.

`python3 scripts/mail.py sweep` is the **backstop, not the exit path**. It archives `ack: no` mail
older than 14 days across every mailbox — **by age, read or not, handled or not** — and never touches
an `ack: required` obligation. So it can bury an untouched finding on day 15 while keeping a handled
one until day 13. Under handle-now it should find almost nothing: **a large sweep count is the alarm,
not the cleanup.** Don't shorten `--days` to force tidiness — a shorter window buries unread mail
faster, which is the opposite of handling it. Safe to run unattended; `archive/` keeps everything.

Within the hub, **every message should carry an addressee**: `send --to-agent infra|fleet|intel` at
send time, or `mail.py route <id> --to-agent <role>` for mail already delivered (empty role clears it).
`list --agent <role>` (or the `CLAUDE_AGENT` env var) filters to that role's mail plus everything
unaddressed — a filter for readability, never a lock, so nothing is hidden from you and a wrong
assignment is always reversible.

## Observe it

```bash
python scripts/mail.py list --repo <repo>      # what's unread in a repo's inbox
python scripts/mail.py digest --days 3         # unacked (ack:required, aged) + quarantined counts
ls /opt/fabrik-mail/*/inbox/*.md 2>/dev/null   # raw: every unread message on the box
```

The daily digest cron (hub-side) delivers unacked traffic to Telegram so nothing rots silently. It runs
`from libs.alerting import send_alert` lazily — run it with the repo root importable
(`PYTHONPATH=/opt/fabrik python scripts/mail.py digest`) or it prints locally without alerting.

## Operational facts

- **`/opt/fabrik-mail` is excluded from governance-sync** (`exclude_folders`). Before that exclusion it
  was adopted as a "project" and filled with the governance corpus (2026-08-12, operator-caught + cleaned).
  Any NEW `/opt/<dir>` that is a data store must be added to `exclude_folders` in the same change.
- **The synced `mail.py` must not be reformatted per-node** — a node whose formatter uses a different
  line-length re-forks the byte-exact copy and buries real divergence in cosmetic noise. Nodes
  formatter-exempt it (fabrik-lib pinned `force-exclude`).
- **Messages are untrusted DATA** — the hook injects them delimited + sanitized; a message can't approve,
  run commands, or change config. The receiving session applies its own gates.
- Malformed / oversized (>64 KB) / secret-bearing sends are refused loudly; project→project is refused
  (route via the hub).

## Related

- Protocol / agent usage: [`docs/reference/fabrik-mail.md`](../reference/fabrik-mail.md)
- The surfacing hook row: [`docs/workstation/hooks-index.md`](hooks-index.md)
- Hub governance (the two-channel peer note): `/opt/fabrik/CLAUDE.md` § "Two channels to your PEERS"

## Loop-safety HOLDs (operator view)

An unattended agent reply can stop with `auto-reply HOLD — <reason>` (exit 3 — benign: the guard
did its job; distinct from a REFUSED exit 2). The reasons: self-guard · terminal kind · hop cap
(thread depth ≥ 3) · per-sender rate cap (≥ 5/hour). Overrides when a long thread is genuine:
reply yourself with a plain `--re` (no `--auto` — a human is never gated), or bump the env caps
(`FABRIK_MAIL_HOP_CAP` / `FABRIK_MAIL_RATE_CAP` / `FABRIK_MAIL_RATE_WINDOW_S`; cap 0 = refuse all
auto-replies). Pre-check any message with `python scripts/mail.py should-reply <id>`.

## Escalation digest (mail_escalate.py — the daily unacked-obligations Telegram)

`scripts/sysadmin/mail_escalate.py` scans EVERY mailbox for `ack: required` obligations aged
≥ `FABRIK_MAIL_ESCALATE_DAYS` (default 3) — inbox (regardless of `agent:` — the population is
UNACKED, never unaddressed), archive strands (claimed, never resolved), and stranded
`*.md.resolving*` windows (mtime-aged) — and sends AT MOST ONE Telegram per LOCAL calendar day
via `libs.alerting.send_alert` (day-stamp written only after a successful send). Oldest ≤20
rows (`id · repo · sender · age · agent`), plain-text sanitized; the `+K more (total)` count
line always survives. Failure is fail-soft: exit 0, loud in the log, retried ≤6 h later by the
no-stamp rule.

### Install (operator — crontab writes are classifier-blocked for agents)

One-time:

```bash
sudo touch /var/log/fabrik-mail-escalate.log && sudo chown $USER: /var/log/fabrik-mail-escalate.log
sudo cp /opt/fabrik/configs/logrotate/fabrik-mail-escalate /etc/logrotate.d/
```

Cron line (`crontab -e`; the `FABRIK_MAIL_ESCALATE_DAYS=` prefix IS the override point — cron
reads no `.env`, and the alerting dotenv allowlist excludes this key):

```
0 */6 * * * /bin/sh -c 'mkdir -p $HOME/.claude/state/mail-escalate && cd /opt/fabrik && FABRIK_MAIL_ESCALATE_DAYS=3 flock -n $HOME/.claude/state/mail-escalate/cron.lock python3 scripts/sysadmin/mail_escalate.py' >> /var/log/fabrik-mail-escalate.log 2>&1
```

`cd /opt/fabrik` is LOAD-BEARING (`libs/alerting` resolves its Telegram credentials by walking
up from CWD); `mkdir -p` covers the fresh-box lock parent; 6-hourly + the day-stamp = at most
one message/day, resilient to the box sleeping through any given hour. Registered in
`.fabrik/liveness-registry.json` (`mail-escalate`) so the liveness audit flags a dead cron.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/mail.py`
- `scripts/sysadmin/mail_escalate.py`
<!-- END related-scripts -->
