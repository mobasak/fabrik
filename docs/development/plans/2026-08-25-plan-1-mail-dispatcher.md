# Plan — fabrik-mail addressing enforcement + escalation (v3, enforcement-first)

Status: CONVERGED (v3.1 2026-08-26 — enforcement-first, consistent with spec v3.1; sixth review's 17 findings each a step, test row, or documented residual)
Date: 2026-08-26
Spec (source of truth): `docs/superpowers/specs/2026-08-25-fabrik-mail-dispatcher-design.md` (v3.1)

## What we already agreed (operator decisions verbatim where theirs)

- **Operator 2026-08-26: "why dont we enforce sender agents to add recipent address … instead?"**
  → the dispatcher is DEAD (spec Rejected alternative E). **"do we need to develop a dispatcher
  at all?" → No.** The build: library-level send guard + caller/doc updates + escalation digest
  + one-time triage.
- Guard in the LIBRARY `send()` (`to == "fabrik"` literal, never `_is_hub` — fabrik-lib's
  mailbox stays open); CLI exit 2 + beat guide; ordering AFTER the secret/star checks (D6/E1).
- BOTH live automated hub senders gain `--broadcast`: `claude_rotate.py:_drain_mail` (dominant
  — 10/15 live unaddressed are its quota advisories, `stderr=DEVNULL`) + kaizen. Instruction
  surfaces (governance template, /fabrik-upstream sources, renderer summary) teach the beat
  guide; command sources render from merged master.
- Escalation: ALL mailboxes, three populations (inbox · archive strands · `*.md.resolving*`
  windows), inclusive `>=` threshold, at most one Telegram per LOCAL calendar day via
  **`send_alert`** (the telegram.send-dedup premise was false; Apprise leg + diagnosis win);
  day-stamp only after send success; `0 */6` cron with the env override INLINE in the line.
- No daemons, watchers, LLM, ledgers, systemd units.

Richness: RICH (spec-fed v3.1).

## Global Constraints (every phase inherits)

- **`scripts/mail.py` is FLEET-SYNCED and its commit FIRES the sync at pre-commit**
  (`.pre-commit-config.yaml:69` includes `mail` in the files-filter; 49 project copies).
  The guard must be provably a no-op off the hub mailbox; the FULL mail suite is the gate.
- `templates/governance/CLAUDE.md` is a sync-trigger surface too; `commands/_sources/` changes
  reach the box only via `assemble_commands.py` RENDERED FROM MERGED MASTER (never bare-render
  from a worktree).
- Untrusted text (sender/subject/agent/repo fields) sanitized before ANY output surface: strip
  control chars, length-cap, and replace the NAMED Markdown metachars `` _ * [ ] ` `` (a `_` is
  legal in repo names and would 400 the `parse_mode: Markdown` post, `telegram.py:89,112`).
- Escalation failure fail-soft: exit 0, loud on the script's OWN stdout.
- Day-stamp uses the LOCAL date (`date.today()`; box = Europe/Istanbul, cron fires local — a
  UTC stamp double-sends across 21:00-00:00).
- Python stdlib only; `pyproject.toml` untouched. `ruff` clean; `uv run pytest`.
- Shared tree: explicit pathspecs; commit + push per phase with provenance trailers.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| Spec v3.1 (this stem) | the whole shape; Rejected alternative E bans dispatcher machinery | spec § Chosen approach / § Rejected |
| `scripts/mail.py` (EXTEND) | library `send()` at `:604` (guard site, AFTER `:658-666` D6/E1 ordering); `route()` `:758` (+`HUB_BEATS` when repo==fabrik); CLI `main()` `:1415-1427` (stdout stays path-only; `broadcast` note → stderr); `HUB_NODES` trap `:47` (`_is_hub` includes fabrik-lib — never use it for the guard); `_import_alerting` sys.path precedent `:1307-1320`; digest three-population precedent `:1051-1131` (resolving windows `:1102-1109` mtime-aged; dotfile guards `:1059,:1111` P13-6); `_ACK_LINE` `:191`; inclusive `>=` `:1076` | read live this session |
| `tests/test_mail.py` (EXTEND) | 55 `to="fabrik"` unaddressed call sites — updated mechanically with the guard (it is `mail.py`'s AFTER-EDIT coupling partner) | `grep -c` verified |
| `scripts/sysadmin/claude_rotate.py` (EXTEND) | `_drain_mail` `:2169-2200` + call `:3764-3770` — Popen argv gains `--broadcast` (quota advisories are all-agents); `stderr=DEVNULL` means a refusal would be SILENT loss of the quota-wall warning | read live |
| `scripts/sysadmin/kaizen_collect_v2.py` (EXTEND) | send argv `:2469` gains `--broadcast`; `returncode` checked at `:2478` — safe | read live |
| `templates/governance/CLAUDE.md` + `commands/_sources/fabrik-upstream.md` + `commands/assemble_commands.py:69` (EXTEND) | the surfaces that TEACH `--to fabrik` (`:95,:234,:239` / `:155,:245`) get the beat guide | grepped live (sixth review) |
| `scripts/enforcement/check_vendored_drift.py` (EXTEND) | add `scripts/mail.py` to the governance set — makes the fabrik-lib fork's drift visible (fabrik-lib is sync-EXCLUDED, `sync_enforcement_to_projects.py:795`, 36 live messages of correspondence) | read live |
| `libs/alerting` (REUSE) | **`send_alert(title, body) -> bool`** (`__init__.py:123` — Apprise primary leg `:88-104` + `format_diagnosis` `:109`; the in-process `_last_sent` dedup `:56` can never suppress a fresh-process daily digest); CWD-walking dotenv → `cd /opt/fabrik` load-bearing; `DOTENV_KEYS` is a curated allowlist (`_dotenv.py:30-43`) → `FABRIK_MAIL_ESCALATE_DAYS` must ride the CRON LINE env prefix, not `.env` | grounded live (sixth review) |
| `core/45-testing` / `core/35-security` / `core/62-subagents` (ACTIVE) | TDD watched-fail-first · untrusted-input · pool-default fan-out | Behavior Contracts / § Execution pillars |
| Crontab classifier block | operator installs the line | memory + spec Locked decisions |

No 🆕 fabrik-lib candidate.

## Phase A — the send guard + every sender + every instruction surface

**Interfaces.Produces:** `HUB_BEATS` constant; guarded library `send(to, ..., to_agent=None,
broadcast=False)`; hardened `route()`; `--broadcast` CLI flag; updated callers
(`claude_rotate._drain_mail`, kaizen) + instruction surfaces (template, upstream sources,
renderer summary); updated `tests/test_mail.py` call sites; `check_vendored_drift.py`
governance-set row.

Steps:
1. `HUB_BEATS = ("infra", "fleet", "intel")` beside `_safe_agent`; guard INSIDE `send()` after
   the recipient/star + HIGH-secret checks (`:658-666` — D6/E1 ordering preserved; test pins
   that an unaddressed hub send CARRYING a secret gets the SECRET refusal first). Refusal =
   `MailRefusedError`; CLI exit 2 + three-beat guide on stderr; `broadcast` note on stderr,
   stdout stays path-only (`:1427` contract).
2. `route()`: when `repo == "fabrik"`, `to_agent` must be in `HUB_BEATS` or `''` (clear stays
   legal). `requeue`'s unaddressed return is ACCEPTED legacy (visible to all; escalation
   catches aging) — documented, not "fixed".
3. Mechanical update of the 55 `tests/test_mail.py` `to="fabrik"` sites (add
   `to_agent="infra"` or `broadcast=True` per each test's intent — sed + hand-check; tests
   asserting guard-refusal behavior are NEW, watched-fail-first).
4. Callers: `_drain_mail` argv += `--broadcast` (`claude_rotate.py:2178` region);
   kaizen argv += `--broadcast` (`:2469`). Static caller-tests pin both (source-line reads —
   neither can silently regress; the census lesson: callers are READ, not grep'd).
5. Instruction surfaces: beat guide into `templates/governance/CLAUDE.md:95,234,239`,
   `commands/_sources/fabrik-upstream.md:155,245`, `assemble_commands.py:69`; then render the
   command corpus FROM MERGED MASTER (post-merge step — never from a worktree).
6. `check_vendored_drift.py`: `scripts/mail.py` joins the governance set (one tuple entry +
   test pin); executor sends the fabrik-lib re-vendor notice via fabrik-mail (attended act).

Phase gate: `uv run pytest tests/test_mail.py tests/test_mail_addressing.py -q` → ALL pass
(the full mail suite — the 55-site update is the regression surface); `ruff check
scripts/mail.py scripts/sysadmin/claude_rotate.py scripts/sysadmin/kaizen_collect_v2.py
scripts/enforcement/check_vendored_drift.py` → clean.

### Behavior Contract (risk-ordered)
- **Given** library `send(to="fabrik")` with neither `to_agent` nor `broadcast`, **When**
  called, **Then** `MailRefusedError` — no file created (the importable bypass is closed). (TDD)
- **Given** CLI `send --to fabrik` unaddressed, **When** run, **Then** exit 2 and stderr
  contains all three beat names. (TDD)
- **Given** an unaddressed hub send whose body carries a HIGH-class secret, **When** refused,
  **Then** the SECRET diagnosis is the refusal shown (D6/E1 ordering). (TDD)
- **Given** `send --to fabrik-lib` unaddressed, **When** run, **Then** it succeeds — the guard
  keys on the literal `fabrik`, never `_is_hub`. (TDD)
- **Given** `send --to transdoc` unaddressed, **When** run, **Then** unchanged (non-hub no-op).
- **Given** `--to fabrik --to-agent devops`, **Then** refused; **Given** `route <id>
  --to-agent inrfa --repo fabrik`, **Then** refused; **Given** `route <id> --to-agent ''`,
  **Then** allowed (clear stays legal). (TDD)
- **Given** `--to fabrik --broadcast`, **Then** delivered unaddressed; stdout is STILL only the
  path (the `broadcast` note is on stderr).
- **Given** the two caller sources, **When** the static tests run, **Then** both send argvs
  contain `--broadcast`.

Close: doc-sync check → **/fabrik-review on Phase A's changed surface to its
coverage-adjudicated exit (BLOCKING — fleet-synced files)** → commit (explicit paths +
trailers; the governance-sync fires AT this commit — blast radius known and intended) + push →
render the command corpus from merged master.

## Phase B — escalation digest + install + docs + triage

**Interfaces.Consumes:** `mail.py` import surface (`_parse`, `_age_seconds`, `_ACK_LINE`).
**Interfaces.Produces:** `scripts/sysadmin/mail_escalate.py` — `collect_obligations(root)
-> list[Obligation]` (ALL mailboxes, three populations), `build_digest(items) -> str`,
`main()`; the cron line + install block.

Steps:
1. `mail_escalate.py`: sys.path bootstrap per the `_import_alerting` precedent
   (`mail.py:1307-1320` — a `scripts/sysadmin/` invocation has neither repo root nor
   `scripts/` on the path; `cd` only serves the dotenv walk). Scan ALL mailboxes (digest
   parity): inbox `ack: required` regardless of `agent:`; archive strands (no `_ACK_LINE`);
   `*.md.resolving*` windows aged by mtime (`:1102-1109`); dotfile guard on EVERY glob
   (P13-6, `:1111` — a `.vim` backup must never escalate daily forever). Age =
   `_age_seconds(ts) >= FABRIK_MAIL_ESCALATE_DAYS * 86400` (env read at runtime; the override
   rides the cron line's env prefix — cron reads no `.env` and the alerting dotenv allowlist
   excludes it, `_dotenv.py:30-43`). Digest: oldest ≤20 (`id · repo · sender · age(d) ·
   agent`, sanitized per the named metachar set; fewer if 3900 would overflow) + the
   always-surviving `+K more (total)` line. Send via **`send_alert(title, body)`**; on True
   write the day-stamp with the send-moment LOCAL date (crash in the send→stamp window
   duplicates once — accepted); on False print the failure on stdout, exit 0. Today's stamp
   present → exit 0 silently.
2. Tests (TDD: addressed-but-unacked escalates; archive strand included; resolving-window
   strand included (mtime-aged); dotfile ignored; day-stamp ONLY after success (monkeypatched
   `send_alert` → False leaves no stamp); LOCAL-date stamp (freeze at 22:30 UTC → stamp is
   tomorrow's local date); boundary exactly `N*86400`; 50 items → `+30 more (50)` ≤3900,
   metachar-free incl. a `_`-bearing repo name; fresh-clone suite touches no live
   mailbox/crontab/Telegram — `FABRIK_MAIL_ROOT` tmp + monkeypatch).
3. Install block (operator, verbatim in `docs/workstation/fabrik-mail.md` § Escalation): the
   spec § 4 cron line (with `mkdir -p`, `cd /opt/fabrik`, inline `FABRIK_MAIL_ESCALATE_DAYS`,
   `flock -n`); `sudo touch /var/log/fabrik-mail-escalate.log && sudo chown $USER:`; the
   logrotate snippet shipped at `configs/logrotate/fabrik-mail-escalate` with the operator
   `sudo cp` into `/etc/logrotate.d/` (sudo already present in the block).
4. Docs: `docs/reference/fabrik-mail.md` — BOTH dispatcher references updated (`:219`
   "forthcoming" AND `:257` "the dispatcher must pass a resolvable `--re`") → § Addressing
   enforcement + § Escalation; `docs/workstation/fabrik-mail.md` § Escalation install;
   `.env.example` + `docs/CONFIGURATION.md` (`FABRIK_MAIL_ESCALATE_DAYS` — noting the
   cron-line override mechanism); `INDEX.md`; `CHANGELOG.md`; `docs/LESSONS_LEARNT.md` (entry
   or `none` — candidate: five reviews refined a router before asking whether the routed
   population should exist; and: enumerate senders by reading callers, never literal grep).
5. One-time backlog triage: route the accidentally-unaddressed hub messages; quota advisories
   + kaizen stay broadcast-class; record the count.
6. **/fabrik-docs-review** over the touched docs.
7. Final: `python scripts/final_gate.py --check --json` → `"status":"success"` AND
   `python scripts/enforcement/check_convergence.py` → green.

### Behavior Contract (risk-ordered)
- **Given** a message ADDRESSED 3 days ago and never acked, **Then** it IS in the digest
  (population = unacked, never unaddressed). (TDD)
- **Given** an archive strand and a stranded `*.md.resolving*` window, **Then** BOTH are in
  the digest. (TDD)
- **Given** a dotfile `.X.md` with `ack: required` in the archive, **Then** it is NOT in the
  digest. (TDD)
- **Given** `send_alert` returns False, **Then** no day-stamp, exit 0, failure on stdout. (TDD)
- **Given** a run at 22:30 UTC (01:30 local next day), **Then** the stamp carries the LOCAL
  date. (TDD)
- **Given** today's stamp exists, **Then** no send attempted.
- **Given** an obligation exactly `N*86400` old, **Then** escalated; one second younger, not.
- **Given** 50 obligations incl. a `_`-bearing repo name, **Then** oldest ≤20 + `+30 more
  (50)`, ≤3900 chars, no `` _ * [ ] ` `` in the output.
- **Given** a fresh clone, **Then** `pytest` touches no live mailbox, crontab, or Telegram.

Close: doc-sync check → **/fabrik-review on Phase B's changed surface (BLOCKING)** → commit +
push.

## Execution pillars (binding on /fabrik-execute-plan)

- **Review floor:** each phase ends with a full `/fabrik-review` to a coverage-adjudicated
  exit before the next starts — Phase A doubly so (fleet-synced files, sync fires at commit).
- **Dispatch policy:** pool-default (`fanout` → `set_quality` back-fill) for per-behavior test
  authoring + review finders; native Claude on top for the authoritative pass on the `mail.py`
  guard + the decide/refute/merge. Never all-native.
- **Parallelism:** within Phase A, steps 3 (test-site update), 4 (callers), 5 (instruction
  surfaces) fan out after steps 1-2 land; Phase B steps 1-2 are independent of A's docs legs.
  Merge/dedupe at the executor before each phase gate. Phases commit separately.

## File Scope (owned paths)

- scripts/mail.py
- tests/test_mail.py
- tests/test_mail_addressing.py
- tests/test_mail_escalate.py
- tests/fixtures/mail_escalate/
- scripts/sysadmin/claude_rotate.py
- scripts/sysadmin/kaizen_collect_v2.py
- scripts/sysadmin/mail_escalate.py
- scripts/enforcement/check_vendored_drift.py
- templates/governance/CLAUDE.md
- commands/_sources/fabrik-upstream.md
- commands/assemble_commands.py
- configs/logrotate/fabrik-mail-escalate
- docs/reference/fabrik-mail.md
- docs/workstation/fabrik-mail.md
- docs/CONFIGURATION.md
- .env.example
- docs/development/reviews/2026-08-25-plan-1-mail-dispatcher-review.md

(CHANGELOG.md / INDEX.md / docs/LESSONS_LEARNT.md stay outside the lock per the plan grammar.
Sync-trigger surfaces in scope: `scripts/mail.py`, `scripts/enforcement/`,
`templates/governance/` — blast radius named in Phase A's close.)

## Evidence

- `.pre-commit-config.yaml:69` — `mail` in the governance-sync files-filter (commit-time
  distribution, verified).
- `scripts/mail.py:47` `HUB_NODES` incl. `fabrik-lib` (the `_is_hub` trap); `:604` `send()`;
  `:658-666` D6/E1 ordering doc; `:758` `route`; `:886` `requeue`; `:926/:948/:191` import
  surface; `:1051-1131` digest three populations (`:1102-1109` resolving windows;
  `:1059/:1111` dotfile guards); `:1076` inclusive compare; `:1307-1320` `_import_alerting`
  sys.path precedent; `:1427` stdout path-only contract.
- `scripts/sysadmin/claude_rotate.py:2169-2200` `_drain_mail` (Popen, `stderr=DEVNULL`),
  `:3764-3770` fallback-to-every-mailbox call site.
- `scripts/sysadmin/kaizen_collect_v2.py:2469` argv, `:2478` returncode check.
- `libs/alerting/__init__.py:56` in-process `_last_sent` (the false-dedup premise), `:88-109`
  Apprise leg + diagnosis, `:123` `send_alert`; `_dotenv.py:30-43` `DOTENV_KEYS` allowlist.
- `sync_enforcement_to_projects.py:795` fabrik-lib exclusion.
- Live probes:

```
$ grep -c 'to="fabrik"' tests/test_mail.py
55
$ grep -n '"mail.py"' scripts/fabrik_synced_manifest.py
40:    "mail.py",  # fabrik-mail sender/store — fleet-consumed by /fabrik-upstream (...)
$ ls /etc/logrotate.d/ | grep -c fabrik ; timedatectl show -p Timezone 2>/dev/null || cat /etc/timezone
0
Europe/Istanbul
```

## Self-audit

- (a) Coverage vs agreed: guard (library) → A1; typo/route hardening → A2; 55 test sites →
  A3; BOTH senders → A4; instruction surfaces + render-from-master → A5; fabrik-lib hole →
  A6 + Locked decisions; escalation all-mailbox three-population → B1-2; local-date stamp →
  B1-2; env-override-in-cron → B1/B3; install + logrotate → B3; both dispatcher doc refs →
  B4; triage → B5. No gaps found against the sixth review's 17 findings (each is either a
  step, a test row, or an accepted-and-documented residual).
- (b) Cross-phase signatures: B imports only read-helpers A does not change; `send_alert`
  consumed per its live signature. Consistent.
- Wired consumers: guard → every `mail.py send` caller; digest → operator Telegram via the
  cron line. No stored-and-never-read.
- Not yet a fixed point: `/fabrik-plan-review` owns convergence.

## Residual unknowns

- OPEN (discovery-by-design): project-side automated hub-bound senders beyond the hub census —
  the refusal is the discovery mechanism; hub census is now caller-read, not grep'd.
- ACCEPTED residuals (documented, not defects): `requeue` may return legacy mail unaddressed
  (visible to all; escalation catches aging); `--broadcast` keeps a deliberate unaddressed
  class; send→stamp crash window can duplicate one Telegram.
- RESOLVED: everything else, incl. all 17 sixth-review findings.
