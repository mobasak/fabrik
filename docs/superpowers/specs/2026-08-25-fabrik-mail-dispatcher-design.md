# fabrik-mail ADDRESSING ENFORCEMENT + ESCALATION (design spec — v3, enforcement-first)

Status: CONVERGED (v3.1 2026-08-26 — enforcement-first; sixth+seventh reviews folded: sender census incl. the aro-wake twin, reply-exempt + broadcast/ack-required-refused guard semantics, render-before-commit, liveness registration)
Date: 2026-08-26 (v1/v2 dispatcher shape 2026-08-25 — superseded, § Rejected alternative E)
Author: infra (hub session)
Predecessors: `2026-08-11-fabrik-mail-design.md` (Layer 1, shipped) ·
`2026-08-15-fabrik-mail-loop-safety-design.md` (the `--auto` guards, shipped)

## Goal

Unread hub mail rots because delivery-to-owner is manual — measured: 22 unacked `ack: required`
obligations, one defect reported FIVE times across three repos before anyone actioned it
(STRATEGIC_BACKLOG row M). Five review rounds refined a destination-side DISPATCHER before the
operator broke the frame (2026-08-26): **the send path is ours** — `scripts/mail.py` is
hub-authored, fleet-synced (`scripts/fabrik_synced_manifest.py:40`), and the standard writer
into the mailbox — so unaddressed hub-bound mail should be **impossible to send**, not routed
after the fact. What enforcement cannot solve is recipients not ACTING: that needs the
escalation digest, the one destination-side piece that survives.

**Success criteria (testable):**
1. The **library** `send()` (`mail.py:604` — the guard lives there, NOT only in the CLI branch,
   so the importable path is closed too) refuses a hub-bound send (`to == "fabrik"`,
   **deliberately NOT `_is_hub`** — `HUB_NODES` includes `fabrik-lib` (`mail.py:47`), whose
   mailbox has no beats and must stay unguarded) without `to_agent ∈ HUB_BEATS` or
   `broadcast=True`; the CLI maps this to **exit 2** via the EXISTING `MailRefusedError`
   ladder + the three-beat guide on stderr. With either flag it succeeds. Semantics pinned:
   `broadcast` off-hub = legal no-op; `broadcast`+`to_agent` → `to_agent` wins;
   **`broadcast`+`ack: required` is REFUSED** (an obligation nobody owns is a contradiction —
   and it keeps broadcast mail out of the escalation digest by construction); **a `--re` reply
   with a resolvable parent is EXEMPT** (thread-anchored — the documented project reply path
   keeps working; `send()` already resolves parents at `:676-684`). Project-bound sends
   untouched. **Ordering preserved:** the
   addressing check runs AFTER the recipient/star checks and the HIGH-secret refusal
   (`mail.py:658-666`, invariants D6/E1 — a credential leak must be diagnosed as a leak on the
   FIRST attempt, never masked by an addressing nag).
2. **Every live automated hub-bound sender is updated in the same change** — the census
   (corrected by the sixth review; a literal grep missed variable argv):
   `claude_rotate.py:_drain_mail` (`:2169-2200`, call site `:3764-3770` — the DOMINANT
   sender: 11 of the 15 currently-unaddressed hub messages are its `fleet quota advisory`,
   sent with `stderr=DEVNULL`, so a refusal would be silent loss of the quota-wall warning)
   **in BOTH byte-identical copies (`scripts/sysadmin/` AND the fleet-rsync'd
   `scripts/aro-wake/` twin — the file's own header declares the invariant; the census lesson
   struck twice)**, and `kaizen_collect_v2.py:2469` — gaining `--broadcast` (advisories/
   collections are all-agents by nature), kaizen additionally `--ack no` (broadcast+required
   is now a refused contradiction; the kaizen ledger is its accountability, not mail-ack). The instruction surfaces that TEACH `--to fabrik` are updated in the
   same change too: `templates/governance/CLAUDE.md:95,234,239` and
   `commands/_sources/fabrik-upstream.md:155,245` (+ the `assemble_commands.py:69` summary
   string) carry the beat guide — synced-file/enforcement/commands defects → `--to-agent infra`;
   deploy/VPS/spec-yaml/monitoring → `fleet`; models/benchmarks → `intel`; genuinely unsure →
   `--broadcast` (legal, visible to all three). Command-source edits render from merged master
   (merge-time render only).
3. Any `ack: required` message unacked ≥ `FABRIK_MAIL_ESCALATE_DAYS` (default 3) — **across ALL
   mailboxes** (digest parity, `mail.py:1051-1131`; measured: 2 of the 10 live aged obligations
   sit outside the hub mailbox), in three populations: inbox items, archive
   claimed-but-unresolved strands (no `_ACK_LINE` match, `mail.py:191`), AND stranded
   `*.md.resolving*` windows aged by mtime (`mail.py:1102-1109`, closer D1 — invisible to every
   other verb) — appears in a Telegram escalation at most once per **local** calendar day
   (`date.today()`; the box runs Europe/Istanbul and cron fires local — a UTC stamp would
   double-send across the 21:00–00:00 window).
4. Zero new daemons, watchers, LLM calls, ledgers, or systemd units. The build is the send
   guard + caller/doc updates + one hub-local escalation script + ONE cron line.
5. At ship, the hub inbox holds zero ACCIDENTALLY-unaddressed messages (one-time triage;
   broadcast-class stays). Residual honesty: `--broadcast` and legacy `requeue` (CORRECTED claim: it preserves ALL frontmatter incl. `agent:`, `mail.py:886-922` —
   only already-unaddressed legacy mail returns unaddressed; accepted, escalation catches
   aging), the guard-exempt reply thread class, and the sync-EXCLUDED `fabrik-lib` fork (its
   `mail.py` copy never receives the guard — made VISIBLE by the check_vendored_drift
   extension, closed only when fabrik-lib re-vendors; 83 archived messages of hub
   correspondence) mean the unaddressed population is minimized, not extinct; `route` for the hub
   mailbox is hardened to `HUB_BEATS` in the same change (a typo'd beat via `route` would
   otherwise hide a message from all three `list --agent` views — the same harm one verb
   later).

## Scale + duplicate verdicts

- **Feature-scale**, one plan. No duplicate: extends `mail.py` (Layer 1) + one sysadmin script.
- **Layer model intact:** still Layer 1.5, delivered as protocol enforcement instead of a
  router. Auto-wake stays DEFERRED to Layer 2; escalation is pull-only.

## Locked decisions (inherited, not re-decided)

| Decision | Where it is locked |
|---|---|
| Message protocol: ULID ids, frontmatter, `agent:` as a FILTER never a lock | `scripts/mail.py` + `docs/reference/fabrik-mail.md` (shipped) |
| `mail.py` is fleet-synced; a commit touching it FIRES the governance-sync at pre-commit (verified: the `governance-sync` files-filter alternation includes `mail`, `.pre-commit-config.yaml:69`; 49 project copies exist) | sync-consciousness binds; blast radius intended |
| `fabrik-lib` is sync-EXCLUDED (`sync_enforcement_to_projects.py:795`) — its `mail.py` fork (byte-identical today, 83 archived messages of hub correspondence — re-measured) does NOT receive the guard; closed by (a) a fabrik-mail notice to re-vendor and (b) adding `scripts/mail.py` to `check_vendored_drift.py`'s governance set so undeclared drift is flagged | sixth review, finding 4 |
| Crontab writes CLASSIFIER-BLOCKED; operator installs the line | memory `project_crontab_wipe_2026_08_19` |
| Telegram channel: **`libs.alerting.send_alert(title, body)`** — the PACKAGE entry, not `telegram.send`: the "title-dedup would suppress the daily digest" premise was FALSE (`_last_sent` is in-process state, `__init__.py:56`; a fresh cron process always starts empty), and `send_alert` adds the SSH→Apprise primary leg + `format_diagnosis` (`__init__.py:88-109`) — losing those was the real cost of the bypass. Credentials via the CWD-walking dotenv → **`cd /opt/fabrik` in the cron line stays LOAD-BEARING** | sixth review, finding 5 (grounded live) |
| Mail text is DATA; sender/subject/agent fields sanitized before ANY output surface — the NAMED Markdown-metachar set `` _ * [ ] ` `` is stripped/replaced (a single `_` in a repo name would 400 the send with `parse_mode: Markdown`, `telegram.py:89,112`, and a 400 retries forever) plus control chars + length caps | Layer-1 spec + sixth review, finding 13 |
| No dollar caps on subscription LLM work | moot — v3 makes NO LLM calls |

## Chosen approach — enforce at send, escalate daily

**1. The send guard (library-level, `mail.py:604 send()`).** When `to == "fabrik"` (literal —
see criterion 1): require `to_agent ∈ HUB_BEATS = ("infra", "fleet", "intel")` (constant beside
`_safe_agent`, which stays shape-only for project roles) or `broadcast=True` (new keyword +
`--broadcast` CLI flag; guard bypass only — no frontmatter/schema change; the CLI notes
`broadcast` on **stderr** — stdout keeps its path-only contract, `mail.py:1427`). Refusal:
`MailRefusedError` from the library; exit 2 + the three-beat guide from the CLI. A `to_agent`
outside `HUB_BEATS` for the hub mailbox is refused the same way (typo protection), and
`route()` applies the same `HUB_BEATS` check when `repo == "fabrik"` (clear-to-`''` stays
legal). The ~55 `tests/test_mail.py` call sites that send `to="fabrik"` unaddressed are
updated mechanically in the same change (`tests/test_mail.py` is in `mail.py`'s AFTER-EDIT
coupling header); the phase gate runs the FULL mail suite, not just the new test file.

**2. Callers + instruction surfaces (same change):** `claude_rotate.py:_drain_mail` and
`kaizen_collect_v2.py:2469` gain `--broadcast`; the governance template + `/fabrik-upstream`
sources + renderer summary teach the beat guide (criterion 2). Unknown project-side senders are
DISCOVERED by the refusal (loud at the sender, fix in the error text) — and the hub-side census
lesson binds: enumerate by reading callers, never by literal grep alone.

**3. The escalation digest (`scripts/sysadmin/mail_escalate.py`, hub-local).** Bootstrap
`sys.path` per the `_import_alerting` precedent (`mail.py:1307-1320` — a `scripts/sysadmin/`
invocation has neither the repo root nor `scripts/` on its path; `cd /opt/fabrik` satisfies
ONLY the dotenv walk, a different concern). Imports `mail.py`'s parsing (`_parse`,
`_age_seconds`, `_ACK_LINE` — never re-implemented parsers) and applies `mail.py`'s dotfile
guards on every glob (`:1059,:1111` — P13-6: one `.vim`-backup with `ack: required` would
otherwise escalate daily forever). Collects the three populations of criterion 3 across ALL
mailboxes, aged `>= FABRIK_MAIL_ESCALATE_DAYS * 86400` (inclusive, `:1076`; the override is set
INLINE in the cron line — cron reads no `.env`, and the alerting dotenv loads only its own
curated `DOTENV_KEYS`, `_dotenv.py:30-43`). Sends via `send_alert`; the day-stamp
(`~/.claude/state/mail-escalate/day-stamp`) is written ONLY after a successful send, with the
send-moment's LOCAL date (a crash inside the send→stamp window duplicates once — accepted).
Message: oldest ≤20 items (`id · repo · sender · age(d) · agent`, sanitized per the Locked
metachar set; fewer if 3900 chars would overflow) + the always-surviving `+K more (total)`
line. Failure fail-soft: exit 0, loud on the script's OWN stdout.

**4. One cron line (operator installs):**
`0 */6 * * * /bin/sh -c 'mkdir -p $HOME/.claude/state/mail-escalate && cd /opt/fabrik && FABRIK_MAIL_ESCALATE_DAYS=3 flock -n $HOME/.claude/state/mail-escalate/cron.lock python3 scripts/sysadmin/mail_escalate.py' >> /var/log/fabrik-mail-escalate.log 2>&1`
— 6-hourly + day-stamp = at most one Telegram/local-day, sleep-resilient; the env prefix IS the
operator's override point. The cron registers in `.fabrik/liveness-registry.json` (cron_match + evidence log +
max_age_hours — an unregistered cron is unmonitored, `docs/workstation/liveness.md`).
Install block adds the one-time
`sudo touch /var/log/fabrik-mail-escalate.log && sudo chown $USER:` (the `fabrik-audit.log`
convention) and the logrotate snippet shipped at `configs/logrotate/fabrik-mail-escalate`
(new dir; installed by the operator with `sudo cp` into `/etc/logrotate.d/` — sudo is already
in the install block; verified: no fabrik entry there today).

**5. One-time backlog triage (ship-time, human judgment):** route the current
accidentally-unaddressed hub messages; quota advisories + kaizen stay broadcast-class. Both
dispatcher references in `docs/reference/fabrik-mail.md` (`:219` "forthcoming" AND `:257`
"the dispatcher must pass a resolvable `--re`") are updated to the v3 reality.

## Rejected alternatives

- **E — the destination-side DISPATCHER (v1/v2, five review rounds):** tier-0 regex (26%
  measured) → keyword rules (deleted fifth review: routed-once × 0.8-precision = designed
  permanent misroutes) → Haiku classification (probe-run: 85.2% on the production population) →
  intel floater; ledgers, watcher, quiescence loop. REJECTED AS A SYSTEM (operator frame-break
  2026-08-26): the send path is hub-owned and refusable — empty the routed population by
  construction instead of classifying it after the fact. Probe + tuned prompt retained (git
  history + memory) as the measured fallback; reactivation trigger: accidentally-unaddressed
  hub mail reappearing in volume post-sync (an unenforced sender path — find and close IT).
- **`telegram.send` direct (v3.0):** premise false (see Locked decisions row) — `send_alert`
  wins on the Apprise leg + diagnosis.
- **Auto-replies / auto-handling / wake mechanisms:** out of scope (Layer 2 / own spec).
- **Requiring `--to-agent` for ALL repos:** only the hub mailbox is shared by three agents;
  a fleet-wide requirement breaks project senders for zero benefit.

## External dependencies

None new; all facts grounded live in-repo (sixth review re-verified every citation).

## fabrik-lib / internal verdict table

| Capability | Verdict | Module / why |
|---|---|---|
| Send guard + route hardening | **EXTEND in place** | `scripts/mail.py` (fleet-synced, infra's beat) — library `send()` + `route()` + argparse; `HUB_BEATS` constant |
| Caller updates | **EXTEND in place** | `claude_rotate.py:_drain_mail` + `kaizen_collect_v2.py:2469` (`--broadcast`) |
| Instruction surfaces | **EXTEND in place** | `templates/governance/CLAUDE.md` + `commands/_sources/fabrik-upstream.md` + renderer summary (beat guide; merge-time render) |
| Obligation scan | **REUSE in place** | `mail.py` `_parse`/`_age_seconds`/`_ACK_LINE` + digest's three-population precedent (`:1051-1131`) |
| Telegram | **REUSE in place** | `libs.alerting.send_alert` (package entry — Apprise leg + diagnosis) |
| Drift visibility for the fabrik-lib fork | **EXTEND in place** | `scripts/enforcement/check_vendored_drift.py` — add `scripts/mail.py` to the governance set |
| Escalation glue | **BUILD** (small) | `scripts/sysadmin/mail_escalate.py` — hub-local. New-module check: FAILS (hub-specific; single consumer) |

## Shape / infra implications

None. Fleet-synced file edits (sync-consciousness) + one hub-local script + one cron line.

## Constraints

- Sync blast radius known and intended (Locked decisions); guard provably a no-op off the hub
  mailbox — dedicated tests, full-suite gate.
- Crontab operator-installed; deliverable ships the exact line + log pre-create + logrotate.
- Untrusted text sanitized (named metachar set) before ANY output surface.
- v3 sends no NEW mail kinds and calls no LLM; the fabrik-lib notice is an attended
  fabrik-mail send by the executor, not automation.

## Open / blocking unknowns

- **OPEN (discovery-by-design, non-blocking):** project-side automated hub-bound senders
  beyond the hub census — the refusal is the discovery mechanism (loud at the sender, fix in
  the error text). Hub-side, the census is now caller-read, not grep'd.
- **RESOLVED:** all v1/v2 items (closed by deletion or superseded); the v3.0 channel and
  sender-census defects (sixth review, folded here).
