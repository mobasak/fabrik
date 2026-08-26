# Plan — fabrik-mail addressing enforcement + escalation (v3, enforcement-first)

Status: CONVERGED (v3.1 2026-08-26 — seventh review (armed, independent): 24 candidates, 20 folded / 4 refuted; checklist fully adjudicated; final no-op pass md5 aee43157)
Date: 2026-08-26
Spec (source of truth): `docs/superpowers/specs/2026-08-25-fabrik-mail-dispatcher-design.md` (v3.1)

## What we already agreed (operator decisions verbatim where theirs)

- **Operator 2026-08-26: "why dont we enforce sender agents to add recipent address … instead?"**
  → the dispatcher is DEAD (spec Rejected alternative E). **"do we need to develop a dispatcher
  at all?" → No.** The build: library-level send guard + caller/doc updates + escalation digest
  + one-time triage.
- Guard in the LIBRARY `send()` (`to == "fabrik"` literal, never `_is_hub` — fabrik-lib's
  mailbox stays open); CLI exit 2 + beat guide; ordering AFTER the secret/star checks (D6/E1).
- ALL live automated hub senders gain `--broadcast` — THREE argvs across two programs:
  `claude_rotate.py:_drain_mail` in BOTH byte-identical copies (sysadmin + fleet-rsync'd
  aro-wake twin) (dominant
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
| `scripts/enforcement/check_vendored_drift.py` (EXTEND) | add `scripts/mail.py` to the governance set — makes the fabrik-lib fork's drift visible (fabrik-lib is sync-EXCLUDED, `sync_enforcement_to_projects.py:795`, 83 archived messages of correspondence — re-measured) | read live |
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
   that an unaddressed hub send CARRYING a secret gets the SECRET refusal first). Interface
   truth (verified live): `send()` ALREADY takes `to_agent` (`:612`) — the ONLY new parameter
   is `broadcast: bool = False`; and the CLI ladder ALREADY maps `MailRefusedError → exit 2`
   (`:1481-1483`) — the guard just RAISES it, no new exit plumbing. Three-beat guide in the
   exception message (lands on stderr via the existing `REFUSED —` printer); `broadcast` note
   on stderr, stdout stays path-only (`:1427` contract). Semantics pinned: `broadcast=True`
   with `to != "fabrik"` is a LEGAL NO-OP (callers may pass it unconditionally);
   `broadcast=True` + `to_agent=<beat>` → `to_agent` wins (broadcast is a redundant no-op);
   **`broadcast=True` + `ack="required"` is REFUSED** (an obligation nobody owns is a
   contradiction — this is what keeps broadcast mail OUT of the escalation digest by
   construction); **`--re` with a RESOLVABLE parent is EXEMPT from the guard** (a threaded
   reply is conversation-anchored — the documented project reply path,
   `templates/governance/CLAUDE.md:226-229`, keeps working unchanged; `send()` already
   resolves the parent at `:676-684`). Implementation raises the EXISTING `MailRefusedError`
   INSIDE `send()` — never a new `except` branch in the CLI ladder (`MailHoldError`
   SUBCLASSES `MailRefusedError`, `:212`, and is caught first at `:1478`; a new branch could
   shadow it and turn HOLD's exit 3 into 2 — test pins HOLD still exits 3).
2. `route()`: when `repo == "fabrik"`, `to_agent` must be in `HUB_BEATS` or `''` (clear stays
   legal). `requeue` needs NO change and the earlier claim is CORRECTED: it preserves ALL
   frontmatter including `agent:` (`mail.py:886-922` — it strips only a trailing acked-by
   line); only mail that was ALREADY unaddressed returns unaddressed — accepted legacy tail.
3. Update the 55 `tests/test_mail.py` `to="fabrik"` sites by a PINNED rule, not intuition:
   sites whose assertions REQUIRE unaddressed semantics (`:2262` no-agent-field, `:2266`
   list-visibility, `:2329/:2344/:2352` `.get("agent") is None`) take `broadcast=True`
   (+ `ack="no"` where they used ack:required — the new combination refusal); every other
   site takes `to_agent="infra"`. A wrong pick turns a real assertion into a tautology —
   hence the rule is enumerated here, and guard-refusal tests are NEW, watched-fail-first.
4. Callers: `_drain_mail` argv += `--broadcast` in BOTH byte-identical copies —
   `scripts/sysadmin/claude_rotate.py` AND `scripts/aro-wake/claude_rotate.py` (the file's
   own header declares the twin invariant; aro-wake is fleet-rsync'd — the census lesson
   struck twice: the twin was found by READING the header, not by grep). `--broadcast` is
   safe unconditionally there (legal no-op off-hub, pinned in A1). Kaizen argv +=
   `--broadcast --ack no` (`:2469` — its current `kind: request` defaults ack:required,
   which under broadcast would permanently stuff the escalation digest with ownerless
   obligations; the kaizen ledger, not mail-ack, is its accountability). Static caller-tests
   pin all three argvs + the twin byte-equality.
5. Instruction surfaces: beat guide into `templates/governance/CLAUDE.md:95,234,239` (the
   reply path `:226-229` needs NO edit — replies are guard-exempt per A1),
   `commands/_sources/fabrik-upstream.md:155,245`, `assemble_commands.py:69`. ⚠️ ORDER:
   RENDER BEFORE COMMIT — the pre-commit hook `assemble_commands.py --check` REFUSES any
   commit touching `commands/` while installed ≠ rendered (`.pre-commit-config.yaml:62`);
   execute-plan runs on master, so rendering from the working master tree pre-commit
   satisfies merge-time-render (never from a worktree).
6. `check_vendored_drift.py`: `scripts/mail.py` joins the governance set (one tuple entry +
   test pin — VISIBILITY only; the check is advisory by design, it never closes the fork);
   executor sends the fabrik-lib re-vendor notice via fabrik-mail (attended act).
7. Register the Phase B cron in `.fabrik/liveness-registry.json` (cron_match + evidence log
   + max_age_hours per `docs/workstation/liveness.md` — an unregistered cron is unmonitored;
   the registry's own history: "the fabrik-mail digest cron did not exist", liveness.md:21).

Phase gate: `uv run pytest tests/test_mail.py tests/test_mail_addressing.py
tests/test_claude_rotate_v2.py tests/test_claude_fleet.py tests/test_kaizen_collect_v2.py -q`
→ ALL pass (the mail suite PLUS every edited caller's suite — the 55-site update and the two
caller argvs are the regression surface); `ruff check scripts/mail.py
scripts/sysadmin/claude_rotate.py scripts/aro-wake/claude_rotate.py
scripts/sysadmin/kaizen_collect_v2.py scripts/enforcement/check_vendored_drift.py` → clean.

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
1. `mail_escalate.py`: sys.path bootstrap = `repo_root = Path(__file__).resolve().parents[2]`
   then insert BOTH `repo_root` and `repo_root / "scripts"` (the `_import_alerting` precedent
   `mail.py:1307-1320` is ONE level shallower — copied verbatim it resolves `import mail` but
   NOT `libs.alerting`; the depth is pinned here so the first cron run cannot die on a
   module-scope ImportError, which the fail-soft contract does NOT cover — it covers send
   failure). Env parse via the `_env_cap` precedent (`mail.py:66-86`: garbage or below-minimum
   warns and uses the default — a bare `int()` would crash on garbage and `=0` would escalate
   everything). Day-stamp READ failure (OSError) → treat as absent (a duplicate beats
   permanent silence). Unparseable `ts` → `_age_seconds` returns `inf` → escalates (correct:
   a message with a broken timestamp IS suspect) and renders as `>999d`, never `inf`. Scan ALL mailboxes (digest
   parity): inbox `ack: required` regardless of `agent:`; archive strands (no `_ACK_LINE`);
   `*.md.resolving*` windows aged by mtime (`:1102-1109`); dotfile guard on EVERY glob
   (P13-6, `:1111` — a `.vim` backup must never escalate daily forever). Age =
   `_age_seconds(ts) >= FABRIK_MAIL_ESCALATE_DAYS * 86400` (env read at runtime; the override
   rides the cron line's env prefix — cron reads no `.env` and the alerting dotenv allowlist
   excludes it, `_dotenv.py:30-43`). Digest: oldest ≤20 (`id · repo · sender · age(d) ·
   agent`, sanitized per the named metachar set; fewer if 3900 would overflow) + the
   always-surviving `+K more (total)` line. Send via **`send_alert(title, body)`**; on True
   write the day-stamp with the send-moment LOCAL date (crash in the send→stamp window
   duplicates once — accepted); on False print the failure on stdout, exit 0 (DELIBERATE
   fail-soft: the no-stamp retry in ≤6h is the recovery; the log line is the visibility —
   a non-zero exit would only make flock/cron noise, nothing watches cron exit codes here).
   Truncation order pinned: sanitize fields FIRST → build rows → drop trailing rows to fit
   the budget → the `+K more (total)` count is computed from the FINAL included set, never
   stale. (Budget honesty: the telegram leg itself truncates `f"*{title}*\n{body}"[:4096]`
   at `telegram.py:87`, and the Markdown-400 risk applies to the FALLBACK telegram leg — the
   Apprise primary posts plain JSON; sanitize regardless, the digest must survive whichever
   leg delivers.) Test seam pinned: `mail_escalate` exposes module-level
   `_send = None` resolved lazily in `main()` via `_resolve_sender()` — tests monkeypatch
   `_resolve_sender`, so importing the module NEVER imports `libs.alerting` (whose import-time
   `load_env` would pull live TELEGRAM keys into a test process). Today's stamp
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
4. Docs: `docs/reference/fabrik-mail.md` — BOTH dispatcher references (`:219`, `:257`) →
   § Addressing enforcement + § Escalation; `docs/workstation/fabrik-mail.md` § Escalation
   install; `docs/CONFIGURATION.md` (`FABRIK_MAIL_ESCALATE_DAYS` — stating the cron-line env
   prefix IS the override; `.env.example` gets the entry WITH the comment "# read from the
   cron line, not .env — see workstation/fabrik-mail.md" so it can never mislead);
   `docs/STRATEGIC_BACKLOG.md` row M rewritten to the v3 shape (it still sanctions the dead
   dispatcher); `docs/workstation/kaizen.md:233` (teaches the unaddressed send); `INDEX.md`;
   `CHANGELOG.md`; `docs/FEATURES.md` fabrik-mail rows (shipped-feature matrix row — via the
   shared-append discipline); `docs/LESSONS_LEARNT.md` (entry or `none` — candidates: the
   frame-break; callers are READ, never grep'd — twice).
5. One-time backlog triage: route the accidentally-unaddressed hub messages; quota advisories
   + kaizen stay broadcast-class; record the count. Also remove the stray
   `/opt/fabrik-mail/inbox/` directory (an empty artifact the mailbox walk would treat as a
   repo literally named `inbox`).
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
- **Dispatch policy:** pool-default for per-behavior test authoring + review finders —
  `fanout(...)` (auto-records) + `set_quality` back-fill per unit, the two artifacts
  `check_subagent_flywheel.py` looks for; native Claude on top for the authoritative pass on
  the `mail.py` guard + the decide/refute/merge. Never all-native. Tools-enabled fan-outs set
  DISJOINT `owned_paths` per unit or they silently serialize (62 § Parallelism).
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
- scripts/aro-wake/claude_rotate.py
- scripts/sysadmin/kaizen_collect_v2.py
- scripts/sysadmin/mail_escalate.py
- scripts/enforcement/check_vendored_drift.py
- templates/governance/CLAUDE.md
- commands/_sources/fabrik-upstream.md
- commands/assemble_commands.py
- configs/logrotate/fabrik-mail-escalate
- docs/reference/fabrik-mail.md
- docs/workstation/fabrik-mail.md
- docs/workstation/kaizen.md
- docs/STRATEGIC_BACKLOG.md
- .fabrik/liveness-registry.json
- docs/workstation/liveness.md
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

- (a) Coverage vs agreed: guard + pinned semantics (broadcast no-op off-hub; to_agent wins;
  broadcast+ack:required refused; reply-exempt; no new except branch) → A1; route hardening +
  requeue truth → A2; 55 sites by PINNED rule → A3; THREE caller argvs incl. the aro-wake
  twin → A4; instruction surfaces + render-BEFORE-commit → A5; fabrik-lib visibility + notice
  → A6; liveness registration → A7; escalation (all mailboxes, three populations, syspath
  depth, env-cap parse, day-stamp fail-modes, inf-age render, test seam) → B1-2; install →
  B3; docs incl. BACKLOG row M + kaizen.md + FEATURES rows → B4; triage + stray-dir cleanup →
  B5. Adjudicated against the seventh review's 24 candidates: 20 folded, 4 refuted (>= 
  boundary arithmetic; exit-0 deliberate fail-soft; unknown-caller exit-2 = documented
  discovery-by-design; "new dir" wording).
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

## Review rubric (verbatim — review_rubric.py --changed <File Scope>)

```
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3)

### core/35-security-auth.md
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: an error-open helper turns one bad/empty JWT into a full cross-tenant read. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on `middleware.ts` for access control.** CVE-2025-29927 allows complete middleware bypass via header manipulation.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.

### core/25-data-postgres.md
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv`:
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Critical:** import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID` subclass). **PostgreSQL 18** (released Sep 2025) added native `uuidv7()` — if your instance is PG18+, you can use `DEFAULT uuidv7()` at the schema level instead of app-side generation. On PG16/17, generate app-side as above.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)

### core/30-ops.md
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed AND version-pinned in the Dockerfile, with a `shutil.which()` startup probe that fails fast. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/10-python.md  (hit: scripts/enforcement/check_vendored_drift.py, scripts/mail.py, scripts/sysadmin/claude_rotate.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always `python:<version>-slim-bookworm` on `linux/amd64`. Never use Alpine (musl libc breaks wheels).
- `uvicorn.run()` is for local development only. Never ship it in production code.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### core/40-documentation.md  (hit: commands/_sources/fabrik-upstream.md, docs/CONFIGURATION.md, docs/reference/fabrik-mail.md)
- **Tier-1 (cheap-pool author → verify → converge):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_mail.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`).
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
**BANNED in tests:**
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.

# promote-to-check_*: 51 injected mandate(s) look deterministically greppable
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: an error-open helper turns one bad/empty JWT into a full cross-tenant read. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on `middleware.ts` for access control.** CVE-2025-29927 allows complete middleware bypass via header manipulation.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv`:
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Critical:** import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID` subclass). **PostgreSQL 18** (released Sep 2025) added native `uuidv7()` — if your instance is PG18+, you can use `DEFAULT uuidv7()` at the schema level instead of app-side generation. On PG16/17, generate app-side as above.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
```

## Coverage Checklist (rubric FLOOR + MATCHED + the four standing classes)

| Class | Verdict |
|---|---|
| Untrusted-input → instructions (35-security FLOOR) | CLEAN — named metachar set + control-strip before ANY surface; digest plain-text; no body execution anywhere (hunted: Global Constraints, B1) |
| Config via env only, zero secrets in code (35-security FLOOR) | CLEAN — env with defaults via the `_env_cap` precedent; credentials only via libs/alerting's dotenv; `.env.example` entry carries the truth-comment (hunted: B1, B3-4) |
| 12F axes applicability (XI stdout / VIII no-daemon / IX idempotent reruns) | CLEAN — stdout-only, cron-owned logfile, no daemons/units, reruns idempotent by day-stamp + refusal-idempotent guard (hunted: Global Constraints, B1) |
| 25-postgres / 30-ops deploy rules — applicability | CLEAN — N/A by construction: no DB, no compose, no ports, no deploy (hunted: spec § Shape) |
| Watched-fail-first / behavior-without-a-test (45-testing + standing) | FIXED(2) — guard-refusal + HOLD-exit-3 + seam tests NEW and TDD; the 55-site rewrite governed by the pinned rule (seventh review finding 13) (hunted: A3, both Contracts) |
| Fleet-sync blast radius (synced files in scope; guard no-op off-hub; render-from-master) | FIXED(4) — aro-wake twin added; render-BEFORE-commit ordering fixed; reply path exempted; caller-suite gate files added (seventh review findings 1-3, 6) |
| Fail-open vs fail-closed on every guard (send guard, route guard, day-stamp, strand scan) | FIXED(3) — day-stamp read-fail → duplicate-not-silence; env parse via _env_cap; inf-age escalates + renders >999d (seventh review finding 14) |
| Cost/limit accounting edges (unknown≠0; digest truncation counts) (standing) | FIXED(1) — truncation order pinned; +K computed from the FINAL set (hunted: B1) |
| Boundary/sentinel/prefix collisions (literal "fabrik" vs _is_hub; metachar set; dotfiles) (standing) | CLEAN — literal pinned (fabrik-lib test row); dotfile guards on every glob; stray inbox/ dir cleaned in triage (hunted: A1, B1, B5) |
| Doc Sync Matrix completeness (40-documentation) | FIXED(3) — BACKLOG row M, kaizen.md:233, FEATURES rows added to B4 (seventh review finding 7) |
| Pool-default dispatch + flywheel named (62-subagents) | FIXED(1) — fanout+set_quality artifacts + disjoint owned_paths named in the pillar (seventh review finding 20) |
