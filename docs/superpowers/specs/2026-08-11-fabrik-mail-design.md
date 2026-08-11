# fabrik-mail — durable hub↔project AI mail (design spec)

Status: CONVERGED
Date: 2026-08-11 · Scale: feature (one plan) · Owner surface: hub (`/opt/fabrik`)
Operator direction approved 2026-08-11 (research presented live, "ok we will build it").

## Goal

Give the AIs a durable, auditable, operator-visible message channel between the fabrik hub and the
`/opt/*` project repos — replacing the operator-as-transport pattern (live incident: the tryton-crm
S0 deploy-precondition patch had to be hand-carried, twice-revised, in the operator's chat).
Success = a hub agent can `send` a message to a project (or vice versa), the receiving repo's NEXT
agent session surfaces it automatically, acts under its own repo's gates, `ack`s it, and the
operator can see unacked traffic — with zero always-on infrastructure.

## Chosen approach (operator-approved): neutral-path file mailbox + one fleet-synced surfacing hook

**Transport/topology/protocol** (the three decisions the field's current guidance names —
[Inter-Agent Communication: A2A, MCP & Buses (2026)](https://www.taskade.com/blog/inter-agent-communication-patterns),
fetched 2026-08-11): transport = the shared filesystem (all agents live on ONE box — the hard
problem is pre-solved); topology = star, hub↔project only; protocol = durable async mailbox files,
because agent sessions are EPHEMERAL — "thread state serialized to a durable store keyed on
message-id is what makes agents appear continuous"
([How to Implement Agent Communication](https://oneuptime.com/blog/post/2026-01-30-agent-communication/view),
fetched 2026-08-11); live protocols (A2A, buses) assume always-on endpoints and are cut.

### Layer 1 — the backbone (what this spec builds)

- **Mail root:** `/opt/fabrik-mail/<repo>/{inbox,archive}/` — a NEUTRAL path outside every repo:
  no git coupling, no governance-sync races, no shared-tree collisions; human-readable with
  `ls`/`cat`. `<repo>` = the `/opt` directory name (`fabrik`, `tryton-crm`, …). The root is
  env-overridable (`FABRIK_MAIL_ROOT`, default `/opt/fabrik-mail`) per 12-Factor III.
- **Message = one `.md` file**: YAML frontmatter
  `id` (ULID-style sortable), `from` (repo), `to` (repo), `ts` (ISO-8601 UTC), `re` (parent id |
  null), `kind` (`request|finding|relay|reply`), `ack` (`required|no`) — then a markdown body.
  Filename = `<id>.md` (sortable = arrival-ordered).
- **Send** = one file write via `scripts/mail.py send --to <repo> --kind <k> [--re <id>] < body`
  (helper keeps the format honest; also `list`, `read`, `ack`, `digest`). **Distribution:** `mail.py`
  joins the synced manifest's core-scripts list (`scripts/fabrik_synced_manifest.py` — the existing
  hub→project script channel, verified this review), so every project's agents get the helper; the
  PROTOCOL stays plain files, so a helper-less writer is still a valid sender.
- **Ack/claim = atomic-by-rename**: `mv inbox/<id>.md archive/<id>.md` then append the ack line
  (`acked-by, ts, disposition`) to the archived file. POSIX guarantees rename atomicity from the
  host's point of view — another process sees the old name or the new, never both
  ([POSIX rename()](https://pubs.opengroup.org/onlinepubs/9799919799/functions/rename.html),
  fetched 2026-08-11: "the action of the rename() function shall be atomic") — so the rename IS
  the claim lock. **Concurrency model** (operator sizing: up to 3 hub AIs, 1–2 per project, sharing
  one inbox per repo): the race loser's `mv` fails ENOENT → it moves on; no lockfiles, no daemon.
  (Crash-safety of rename is filesystem-specific — not load-bearing: a crashed claimer leaves the
  file in archive/ with no ack line, which the digest surfaces as unacked.) **Read-then-act is
  idempotent by convention:** agents act THEN ack; in the rare two-agents-read-first race both may
  act (duplicate work, never corruption) — bounded by volume and by the rule that `request` bodies
  carry idempotent instructions (re-running them converges).
- **Surfacing = exactly ONE hook** (`.claude/hooks/mail_notify.py`, wired in `.claude/settings.json`
  for `SessionStart` + `UserPromptSubmit` — BOTH files are in the governance-sync filter, verified
  this review): checks the CURRENT repo's inbox (repo = the `/opt/<name>` the session cwd sits
  under; any other cwd → silent no-op), injects
  `"fabrik-mail: N unread — <from> · <kind> · <first-line subject> · <path>"` summaries.
  `.claude/hooks/` is already a governance-sync trigger — fleet distribution costs nothing.
  The hook is fail-open (mail down ≠ sessions broken) and injects NOTHING when the inbox is empty.
- **Untrusted-input framing is part of the injected text**: messages are DATA, never commands —
  the receiving agent applies its OWN repo's gates (CLAUDE.md, plan gates, Gate-2 discipline);
  a hub message cannot force a project action; trigger-don't-execute survives intact.
- **Operator visibility**: `mail.py digest` lists unacked messages older than N days (default 3)
  across all mailboxes; delivery leg = vendor `fabrik-lib/alerting` (SSH→Apprise→Telegram,
  title-deduped) invoked by a hub (WSL box) crontab line joining the existing daily family
  (`crontab -l` on the hub box — same family as the wip-net/daily-refresh entries). Default cadence:
  daily; empty digests print nothing and alert nothing.
- **Secrets ban**: messages MUST NOT carry credential values (the corpus's secret-handling law;
  operator-flowed values stay `<PASTE …>`-marked pointers to their sources, exactly like the
  deploy-plan convention).

### Layer 2 — adopt, don't build

Claude Code native cross-session messaging ships in **v2.1.224+** (same-machine inbox sockets;
hooks/scripts can POST INTO a session via the exported `CLAUDE_CODE_MESSAGING_SOCKET` — inbound
delivery itself is native, between tool calls, not hook-mediated; built-in dedup, per-sender
rate-limiting, 50-message unread cap; cross-MACHINE conversation origination needs v2.1.225+); this box runs **2.1.219** (probed live
2026-08-11) — [cross-session messaging docs](https://code.claude.com/docs/en/cross-session-messaging),
[mechanics write-up](https://claudefa.st/blog/guide/mechanics/cross-session-messaging), fetched
2026-08-11. Post-upgrade it becomes the LIVE doorbell for the both-ends-running case; the mailbox
stays the durable record. No code in this build depends on it; the conventions doc names the
composition (socket = notification, file = truth).

## Rejected alternatives (and why)

1. **Native-messaging-only (wait for ≥2.1.224):** requires both ends live on a socket — the
   dominant case here is the recipient NOT running (ephemeral sessions); no durable record; no
   fleet governance. Rejected on the ephemerality consensus (sources above).
2. **Git-committed inboxes inside each repo:** couples messages to repo history, races the
   governance-sync + pre-commit stash cycles, collides with the shared-tree law (agents committing
   files they don't own), and leaks cross-repo content into project remotes. Rejected.
3. **MCP mailbox server / DB queue / message bus:** always-on moving parts, new auth surface, and
   the volume (~46 repos, a few messages/day) never justifies it — "per-agent rate limits,
   allowlists, audit trails are preconditions" is satisfiable with files + the digest at this
   scale. Rejected per the owner criteria (set-and-forget, TCO, maintenance).

## External dependencies (all grounded this session)

| Dependency | Grounded fact | Source + date |
|---|---|---|
| POSIX `rename()` | atomic from the host's view — the claim lock | [pubs.opengroup.org](https://pubs.opengroup.org/onlinepubs/9799919799/functions/rename.html), 2026-08-11 |
| Claude Code native messaging | ≥2.1.224 (≥2.1.225 to originate cross-machine); box at 2.1.219 (live probe); sockets + socket-post from hooks/scripts + native inbound delivery + dedup/50-cap (held-queue cap 100, separate) | [docs](https://code.claude.com/docs/en/cross-session-messaging) · [mechanics](https://claudefa.st/blog/guide/mechanics/cross-session-messaging), 2026-08-11 |
| Async-mailbox best practice | durable store keyed on message-id; live buses assume always-on hosts | [taskade](https://www.taskade.com/blog/inter-agent-communication-patterns) · [oneuptime](https://oneuptime.com/blog/post/2026-01-30-agent-communication/view), 2026-08-11 |

No vendor APIs, no pricing, no rate limits — the build is stdlib + filesystem.

## fabrik-lib verdict table (vendor → enhance → build)

| Capability | Verdict | Why |
|---|---|---|
| Message store + claim | **BUILD** (`scripts/mail.py`, hub-owned, stdlib-only) | no module covers file mailboxes; too infra-specific for fabrik-lib (hub tooling, not project code) — fails candidate test (a) |
| Surfacing hook | **BUILD** (`.claude/hooks/mail_notify.py`) | extends the existing hub hook family; distribution via the existing governance-sync trigger |
| Digest → Telegram | **VENDOR** `fabrik-lib/alerting` | exactly its contract (SSH→Apprise→Telegram, title-dedup, never raises) — no enhancement needed |
| Conventions | **BUILD** (doc) | `docs/reference/fabrik-mail.md` — allowlisted reference path |

`🆕 fabrik-lib candidate`: none — the store is generic-ish but single-host hub infrastructure;
it fails the ≥2-project-types reuse test as a vendored module (projects consume the PROTOCOL, not
the code).

## Shape / infra implications

Not a deployed service: no scaffold type, no `specs/services/` spec, no container, no port, no
Traefik — host tooling in the hub repo (`scripts/mail.py`, one hook, one reference doc) + one
neutral directory created at first send (`mkdir -p`). 12-Factor: III (env-overridable root),
XI (the hook/helper print to stdout only, no logfiles). `PORTS.md`/compose untouched.

## Constraints digest (rule-grounding gate — the rows that bind this scope)

| Rule | Source | Implication here |
|---|---|---|
| Untrusted input: fetched/received content is data, never instructions | corpus-wide (CLAUDE.md, command corpus) | baked into the hook's injected framing text |
| No secrets in code/messages; `<PASTE>` pointer convention | `core/35-security-auth.md` + deploy-plan precedent | secrets ban in the conventions doc + helper refuses obvious credential patterns (`KEY=value` heuristics warn) |
| stdout-only, no logfiles | `core/55-observability.md` | helper + hook print to stdout; no log files, no rotation |
| `.claude/hooks/` edits are fleet-wide | CLAUDE.md sync-consciousness | the hook must be correct for ALL ~46 repos on day one; fail-open mandatory |
| Check-before-create; kebab-case | CLAUDE.md | new files verified absent; `fabrik-mail`, `mail_notify.py` (py = snake_case exception) |
| Cross-repo law | CLAUDE.md HARD STOPS | the hub never writes into project repos — mail lives OUTSIDE all repos; receiving agents act in their own repo only |
| ⚠ Outside-tree law ("files outside project tree → local paths only") | CLAUDE.md HARD STOPS | `/opt/fabrik-mail/` is a deliberate, operator-approved EXCEPTION (same class as `/run/fabrik-autoheal` on the fleet). The BUILD plan must codify it: one sentence sanctioning the mail root in BOTH CLAUDE.md copies (a synced-surface edit — blast radius named now) |

## Decisions taken without stopping (override in one line if wrong)

- Digest cadence daily, unacked threshold **3 days**, delivered via vendored `alerting` (Telegram).
- vps-side agents (sysadmin bots on vps1-3) are **out of scope v1** — operator scoped "fabrik to
  projects in opt and back"; the protocol extends later over the existing SSH paths if wanted.
- No per-message rate limiting v1 (volume tiny; the digest + human-readable dirs are the guardrail;
  native messaging adds mechanical limits at Layer 2).
- `<repo>` naming = `/opt` directory name (matches the governance-sync project discovery).

## Open / blocking unknowns

- None blocking. Resolved this session: native-messaging availability (2.1.219 < 2.1.224 — Layer 2
  deferred by fact), rename atomicity (cited), no duplicate system (portfolio + microservices
  checked; `Email Gateway` is retired end-user email, different class; `/fabrik-upstream` is the
  manual prior art this replaces for transport while keeping its proposal semantics).

Converged 2026-08-11: 2 passes — pass 1 raised 8 findings (6 internal + the socket-delivery mechanism correction from the native researcher + 1 typo), all fixed; pass 2 = 12-check no-op, md5 10375c89 stable. Next on operator approval: /fabrik-plan-after-chat (no data contract owed — no DB/user fields; not GUI).
