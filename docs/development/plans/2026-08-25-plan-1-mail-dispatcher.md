# Plan — fabrik-mail dispatcher (Layer 1.5): immediate routing + escalation

Status: CONVERGED
Date: 2026-08-25
Spec (source of truth, CONVERGED): `docs/superpowers/specs/2026-08-25-fabrik-mail-dispatcher-design.md`

## What we already agreed (from the spec + operator, verbatim where theirs)

- Deterministic-first router over `/opt/fabrik-mail/fabrik/inbox/`; LLM fallback ONLY for the
  unmatched remainder, via **vendored `fabrik-lib/llm-dispatch`** (never a raw subprocess).
- **Operator 2026-08-25: "30 minutes too long, i want immediate."** → inotify-backed systemd USER
  path unit fires the dispatcher within seconds; the `*/30` flock cron sweep is the fallback only.
- **Operator 2026-08-25: "we use claude -p, why did we cap ~$0.50/day … i dont want this."** → NO
  dollar budget anywhere. Runaway protection is structural: one-classification-attempt-per-message
  ledger, per-call timeout, `flock`, no retries. `total_cost_usd` logged for visibility only.
- **Operator 2026-08-25: "i dont have ANTHROPIC_API_KEY and i will not have too."** → subscription
  OAuth only; `bare=False` stays (the vendored module's default, deliberate).
- Route, never claim (`claim` is the ack-lock; a robot holding it hides mail from humans).
- v1 sends NO mail, executes nothing, touches no message schema; project inboxes out of scope.
- Escalation: `ack: required` older than `FABRIK_MAIL_ESCALATE_DAYS` (default 3) — inbox AND
  archive strands — → one Telegram per calendar day via the hub-vendored `libs/alerting`
  (send-telegram.sh rejected: its credentials don't exist on this box, third review).
- Operator installs the cron line + enables the systemd units (crontab writes classifier-blocked);
  deliverables include a logrotate snippet (verified: no fabrik entry in `/etc/logrotate.d/`).

Richness: **RICH** (spec-fed, CONVERGED, operator-amended) — no brainstorming, no open product
questions ride into execution.

## Global Constraints (every phase inherits; violations are defects)

- Box-local workstation tooling: no compose, no ports, no Traefik, no `shape:` flags, no deploy.
- Logs: unbuffered plain lines to **stdout only** (cron/systemd redirect); the dispatcher writes
  NO logfile of its own — its only state files are `~/.claude/state/mail-dispatcher/` (stamp,
  attempt ledger, escalation day-stamp) plus the single lock file
  `~/.claude/state/mail-dispatcher.lock` (deliberately OUTSIDE the subdir — its parent must
  pre-exist for flock, § Phase C step 2). (12F XI; `core/55-observability.md` stdout mandate.)
- No daemonizing, no PID files (12F VIII): the watcher is a systemd **.path** unit (systemd owns
  the inotify watch); the dispatcher itself is a run-to-completion script.
- Mail bodies and LLM output are UNTRUSTED DATA: body fenced with a run-unique boundary; `why`
  length-capped + control-char-stripped before logging.
- No `ANTHROPIC_API_KEY` ever; `ClaudeCall(bare=False)` (vendored default) on subscription OAuth.
- No dollar caps: never emit a budget-ceiling check; log estimated cost only.
- One classification attempt per message EVER (ledger keyed by ULID); undecidable → the intel
  floater tier (charter-owned), never retried. One ROUTING per message ever (routed-once ledger)
  — a human clear is final.
- `mail.py` is called as a CLI for MUTATION (`route`) and read directly (frontmatter parse) for
  SCAN — reading is idempotent per the Layer-1 contract; per-message `MailRefusedError`/non-zero
  exits are caught, logged, and never abort the sweep.
- Shared tree: explicit pathspecs only; commit + push at each phase end with provenance trailers.
- Python: stdlib only for the dispatcher (no new deps; `pyproject.toml` untouched — not
  authorized). Type hints + `ruff` clean per `core/10-python.md`.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| Spec (CONVERGED) | goal, approach, all rejected alternatives, operator amendments | `docs/superpowers/specs/2026-08-25-fabrik-mail-dispatcher-design.md` (whole) |
| `core/60-watchdog.md` (ACTIVE) | unattended-loop runaway protection — dollar-ceiling clause OPERATOR-OVERRIDDEN 2026-08-25 for subscription-billed `claude -p`; structural guards instead | pack + spec § Constraints |
| `core/75-workers-jobs.md` (ACTIVE) | idempotent runs; a crashed run leaves no state that blocks the next | single-lock `flock -w 30 -E 0` + stamp design |
| `core/55-observability.md` (ACTIVE) | stdout-only logging, no in-app logfiles | Global Constraints row above |
| `core/35-security-auth.md` (ACTIVE) | untrusted-input handling; no secrets in code (Telegram credentials stay in `/opt/fabrik/.env`, read only by `libs/alerting`) | `libs/alerting/telegram.py:41-51` |
| `core/45-testing-strategy.md` (ACTIVE) | behavior-contract tests, watched-fail-first for the risky ones | Phase Behavior Contracts below |
| `core/62-using-subagents.md` (ACTIVE) | pool-default for gradeable fan-out in execution (test authoring, review finders) | § Execution pillars |
| fabrik-lib `llm-dispatch` (**VENDOR** → `libs/llm_dispatch/`) | the entire `claude -p` call: `ClaudeCall(prompt, json_schema, model="haiku", effort="low", tools=(), permission_mode="dontAsk", timeout_s, bare=False)` → `dispatch()` → `DispatchResult` with `structured`, **`cost_usd`** (`:216`; the envelope's `total_cost_usd`). ⚠️ On an errored envelope `dispatch()` RAISES (`:640-654`) — outcome handling keys on exception TYPES (`DispatchSpawnError`/`DispatchTimeout`/bare `DispatchError` = infra; `SchemaValidationFailed` = message), never on a returned `is_error` | `/opt/fabrik-lib/llm-dispatch/llm_dispatch.py:139-198` (ClaudeCall), `:201-221` (DispatchResult), `:640-654` (raise paths) |
| `scripts/mail.py` (REUSE in place) | `route <id> --to-agent <role> --repo fabrik` mutation CLI (raises/exits non-zero on missing/malformed — catch per message; `--repo` mandatory, CWD-derivation trap at `:229-244`); frontmatter shape + `ts`-based age | `scripts/mail.py:758` (route), `:957` (_quarantine), `:1076` (age compare), `:1398` (--repo flag) |
| `libs/alerting` (REUSE in place, hub-vendored) | telegram send with the split-credential resolver (`TELEGRAM_FULL_BOT_TOKEN` / `TELEGRAM_BOT_ID`+secret / colon-shaped token, chat id `TELEGRAM_CHAT_ID`, from `/opt/fabrik/.env`). `send-telegram.sh` REJECTED — its env file lacks both keys it requires (read live 2026-08-25) | `libs/alerting/telegram.py:3-21,41-51` |
| systemd user manager + inotify | `.path` unit (**`PathModified=` ONLY** — `DirectoryNotEmpty=` banned, retrigger spin) → oneshot service; user manager verified `running`; `/usr/bin/inotifywait` present (fallback probe) | probes in Evidence |
| claude headless CLI (inherited from spec, live-fetched 2026-08-25 ×2) | `-p` non-bare subscription auth; `dontAsk`; `--json-schema` conformance (dispatcher re-checks enum); `total_cost_usd` estimate; `--bare` future-default risk pinned inside the vendored module | spec § External dependencies (URLs + dates) |

No 🆕 fabrik-lib candidate: the dispatcher glue is hub-specific (spec's new-module check: FAILS).

## CONSTRAINTS DIGEST (rule → pack → implication here)

| Rule | Pack:line | Implication |
|---|---|---|
| stdout only, no in-app logfiles/rotation | core/55-observability.md (logs section) | print() lines; cron `>>` + logrotate snippet own the file |
| runaway-proof unattended loops | core/60-watchdog.md (cost ceilings section) | structural guards; $ clause operator-overridden (spec § Locked decisions) |
| idempotent, crash-safe jobs | core/75-workers-jobs.md (idempotency) | attempt ledger + single-lock `flock -w 30 -E 0` + stamp; rerun-safe by construction |
| untrusted input never becomes instructions | core/35-security-auth.md | boundary fence + output sanitization + `tools=()` `dontAsk` |
| watched-fail-first tests for risky behaviors | core/45-testing-strategy.md | Phase A/B contracts marked TDD |
| pool-default dispatch for gradeable work | core/62-using-subagents.md § Dispatch policy | § Execution pillars |

## Phase A — Vendor llm-dispatch + dispatcher core (scan → rules → route)

**Interfaces.Produces:**
- `libs/llm_dispatch/` — verbatim vendored copy of `/opt/fabrik-lib/llm-dispatch/`
  (`llm_dispatch.py`, `README.md`, `requirements.txt`, tests). No install needed for OUR leg:
  `httpx` is imported LAZILY and only by the OpenRouter fallback leg (its requirements.txt says
  so explicitly) — the claude-CLI leg the dispatcher uses runs on stdlib.
- `scripts/mail_dispatcher.py` — CLI: `python3 scripts/mail_dispatcher.py [--dry-run] [--no-llm]`;
  mailbox root from `FABRIK_MAIL_ROOT` (default `/opt/fabrik-mail`) — the dispatcher's OWN scan
  honors the same env seam as `mail.py:_mail_root`, so one variable redirects both layers in
  tests; READ helpers (`_parse`, `_subject_tokens`, `_age_seconds`) are IMPORTED from
  `scripts.mail` (read-only import; mutation stays CLI-only) — never re-implemented parsers
  that drift; importable functions `scan_unaddressed(inbox: Path) -> list[Msg]`,
  `classify_deterministic(msg: Msg, rules: list[Rule]) -> Verdict | None`
  (`Verdict = (beat: str, why: str, operator_decision: bool)`; **`beat` is ALWAYS a real
  `agent:` value `infra|fleet|intel`** — an operator-class rule carries its charter beat plus
  `operator_decision=True`; the string "operator" never reaches `apply_route`),
  `apply_route(msg_id: str, beat: str) -> bool` — wraps
  `subprocess.run([sys.executable, "/opt/fabrik/scripts/mail.py", "route", msg_id, "--to-agent",
  beat, "--repo", "fabrik"], ...)` (argv list, NEVER a shell string): **`--repo fabrik` is
  MANDATORY** — `route()` otherwise derives repo from CWD (`scripts/mail.py:229-244` falls back
  to `Path.cwd().name`), so under cron (CWD=$HOME → repo "ozgur") or systemd (CWD=/ → raises)
  every route fails 100% while a hand-run from /opt/fabrik works — the exact silent-green trap.
  Checks the exit code, NEVER raises — False + log on any failure.
  `RULES: list[Rule]` (ordered, tiered: explicit addressee-prefix → (kind + keyword) → keyword
  → LLM → **intel floater** (the charter's own owner of unowned work, `intel.md` § Floater) —
  **CONTENT-keyed only; the sender repo is NEVER a routing key** (operator correction
  2026-08-25). The addressee-prefix regex matches BOTH live encodings (`[x→y]` and `[x->y]`,
  7/5 split in the archive) and takes the RIGHT-hand token — the left is the SENDER, and a
  group-1 slip would silently reintroduce the banned sender key (dedicated test); a bare `[x]`
  is NOT a signal. Charter-grounded keywords per the spec (DR → infra, not fleet;
  intel = model/benchmark/flywheel/model-selection; templates/governance carve-out → infra);
  the RULES header records the three charter files' md5s and a test compares them live — a
  charter edit reds the suite instead of silently staling the table. **Structural skip-list:**
  the daily kaizen collector mail (dual-charter trigger, unaddressed BY DESIGN) is never routed,
  never LLM'd, logged as skipped. **Routed-once ledger:** the dispatcher routes any message AT
  MOST ONCE EVER (ledger like the LLM one, same pruning) — a human's `route --to-agent ''`
  clear is FINAL, never re-overwritten by the same rule seconds later).
  **Startup bootstrap:** `scripts/mail_dispatcher.py` inserts the REPO ROOT on `sys.path` at
  startup (the `scripts/mail.py:1310` precedent — `sys.path[0]` is `scripts/` when invoked by
  path) and imports the vendored module in PACKAGE form: `from libs.llm_dispatch.llm_dispatch
  import ClaudeCall, dispatch` (the repo convention — `libs/__init__.py` + e.g.
  `scripts/doc_reconcile.py:43`), never a cwd-relative `sys.path.insert(0,'libs')`.
  **Main loop is quiescence-seeking:** after a sweep, re-scan; repeat while new unaddressed
  messages keep appearing (bounded at 10 iterations/run) — a message landing MID-run is caught
  by the same run, so the .path unit's retrigger semantics can never strand one until the sweep.
- State dir `~/.claude/state/mail-dispatcher/` (created on first run).

Steps:
1. Probe preflight (first step, runnable, from /opt/fabrik): `systemctl --user
   is-system-running && flock --version && test -d ~/.claude/state && python3 -c "import libs"`
   → all green (already probed live; the step re-proves in the execution env — package-form
   import, never a cwd-relative sys.path insert).
2. Vendor with hygiene: `rsync -a --exclude='__pycache__' --exclude='.*_cache'
   /opt/fabrik-lib/llm-dispatch/ libs/llm_dispatch/` (dash→underscore; the source dir carries
   `.mypy_cache/.pytest_cache/.ruff_cache/__pycache__` a bare `cp -r` would import into git;
   `UPSTREAM_FEEDBACK.md` IS kept — it is the upstream channel), add the module row to
   `INDEX.md`. ⚠️ Vendor VERBATIM — in particular **never "fix" `bare: bool = False` to match
   the module docstring** (the docstring at `llm_dispatch.py:144-146` wrongly says `bare=True`
   is the default; the CODE default False is deliberate and is the only auth path this box has —
   flipping it returns `is_error:true` with exit 0). Append that docstring↔code contradiction to
   `/opt/fabrik-lib/llm-dispatch/UPSTREAM_FEEDBACK.md` (the sanctioned upstream-note flow).
   `requirements.txt` is copied as documentation only — `httpx` is the OpenRouter leg's lazy
   dep; **never `uv add` anything** (deps files are a HARD STOP). The vendored
   `test_llm_dispatch*.py` sit outside `testpaths=["tests"]` (`pyproject.toml`) and will NOT run
   here — deliberate; the hub-side vendor-integrity test below is the guard. Gate:
   `python3 -c "from libs.llm_dispatch.llm_dispatch import ClaudeCall, dispatch; import dataclasses; assert any(f.name=='cost_usd' for f in dataclasses.fields(__import__('libs.llm_dispatch.llm_dispatch',fromlist=['DispatchResult']).DispatchResult)); print('ok')"`
   (run from /opt/fabrik) → `ok` — this line also ships as a permanent vendor-integrity test in
   `tests/test_mail_dispatcher.py`.
3. Derive the seed rule table from the labeled archive (35 of 144 messages carry `agent:`):
   a ONE-OFF dev-time run by the executor (NOT part of the test suite — Phase C's contract bans
   tests touching the live mailbox, and on a fresh clone the live-archive glob is empty, which
   would make a precision gate vacuously green while measuring nothing): parse
   `/opt/fabrik-mail/fabrik/archive/*.md` frontmatter + subject once, snapshot an ANONYMIZED
   labeled sample as committed fixtures under `tests/fixtures/mail_dispatcher/labeled/`, and
   hand-curate `RULES` from the stats + the beat charters
   (`docs/reference/agents/{infra,fleet,intel}.md`). The SHIPPED test measures precision against
   the committed fixture snapshot (hermetic, clone-safe).
   Gate: per-rule precision vs the fixture labels; every shipped rule ≥0.8
   precision on labeled data or it is cut (misroute worse than LLM fallback — spec § approach 2).
   Coverage/recall is REPORTED, not gated — a thin rule table is safe by design (the LLM covers
   the tail); the report just makes the deterministic share visible.
4. Implement scan + deterministic classify + route with pinned precedence (strictly-more-specific
   wins; same-tier disagreement → UNMATCHED) and per-message error isolation.
5. Tests (TDD — watched fail first for: precedence conflict → UNMATCHED; route-failure isolation;
   operator-decision marker pairing). Fixture mailbox under `tests/fixtures/mail_dispatcher/`.

Phase gate: `uv run pytest tests/test_mail_dispatcher.py -q` → all pass;
`ruff check scripts/mail_dispatcher.py` → clean.

### Behavior Contract (risk-ordered)
- **Given** two same-tier rules disagreeing on beat, **When** classified, **Then** verdict is None (UNMATCHED)
  and the log names both rules. (TDD)
- **Given** a message `route` refuses (claimed mid-run), **When** applied, **Then** `apply_route` returns
  False, logs the id, and the remaining messages still process. (TDD)
- **Given** a message matching a (kind + keyword) composite rule AND a conflicting bare-keyword
  rule, **When** classified, **Then** the more specific composite beat wins.
- **Given** two messages with identical kind + subject from two DIFFERENT sender repos, **When**
  classified, **Then** the verdicts are identical (sender is never a routing key). (TDD)
- **Given** an operator-class match, **When** routed, **Then** the beat is a real `agent:` value and the log
  carries `operator-decision`.
- **Given** an empty inbox, **When** run, **Then** exit 0 with the summary line `scanned 0 …`.

Close: doc-sync check → **/fabrik-review on Phase A's surface to its coverage-adjudicated exit
(BLOCKING; every class CLEAN/FIXED/REFUTED; the fixing pass is never the last look)** → commit
(explicit paths + trailers) + push.

## Phase B — LLM fallback: one bounded call per unmatched message, ever

**Interfaces.Consumes:** Phase A's `scan/classify/apply_route`, `libs/llm_dispatch`.
**Interfaces.Produces:** `classify_llm(msg: Msg) -> Verdict | None` wired into the main loop;
attempt ledger `~/.claude/state/mail-dispatcher/llm-attempts.txt` (one ULID per line; entries are
removed on infra-class outcomes and pruned when a message leaves the inbox — step 3 taxonomy).

Steps:
1. Build the call:
   `ClaudeCall(prompt=<frame+fenced body>, json_schema={"type":"object","properties":{"beat":
   {"enum":["infra","fleet","intel"]},"operator_decision":{"type":"boolean"},"why":
   {"type":"string"}},"required":["beat","operator_decision","why"]},
   model="haiku", effort="low", tools=(), permission_mode="dontAsk", timeout_s=120.0,
   bare=False)` → `dispatch()`. BOTH model and effort pinned — `LLMConfig.from_env` otherwise
   inherits box-level `CLAUDE_CLI_MODEL`/`CLAUDE_CLI_EFFORT` set for other consumers
   (`llm_dispatch.py:109-110`); the `haiku` alias is verified with ONE dev-time live probe
   (`RUN_LIVE=1` lane) before the fallback ships. **Schema erratum vs the spec (grounded, spec updated same-change):** the spec's
   4-value enum with `"operator"` left the operator→beat mapping undefined (the response carried
   no subject-area to map with); a 3-value beat enum + `operator_decision` boolean returns BOTH
   facts and removes the mapping problem. `model="haiku"` is pinned EXPLICITLY — `dispatch()`
   otherwise inherits `LLMConfig` `claude_model="opus"` (`llm_dispatch.py:109`), an Opus call per
   trivial classification and silently overridable by a box-level `CLAUDE_CLI_MODEL`.
   Success = `dispatch()` returned without raising AND `structured` is present (on an errored
   envelope it RAISES, `llm_dispatch.py:640-654`). Beat re-checked
   against the enum in the dispatcher (docs promise conformance, not payload validation).
2. Frame: run-unique `secrets.token_hex(16)` boundary; body containing the boundary → skips the
   LLM, goes to the floater tier, logged. `why` sanitized (≤200 chars, control chars stripped, `untrusted:` prefix).
   Honesty note (grounded `llm_dispatch.py:304-314`, spec updated same-change): the prompt rides
   ARGV for anything under 96 KiB — stdin is only the oversize path — so the isolation property
   is `dontAsk` + `tools=()` + the boundary fence + output sanitization, never "it's on stdin".
3. Ledger with an OUTCOME taxonomy (the attempt is the MESSAGE's only-ever attempt — it must
   never be burned by an infrastructure failure that had nothing to do with the message):
   ULID present in `llm-attempts.txt` → skip (goes to the floater tier). Append BEFORE dispatch
   (crash-safety: a crash mid-call consumes the attempt — deliberate, rare, visible), BUT the
   outcome classes are EXCEPTION TYPES, not `is_error` — `dispatch()` RAISES on an errored
   envelope (`llm_dispatch.py:640-654`), it never returns one: **infra-class** =
   `DispatchSpawnError`, `DispatchTimeout`, and bare `DispatchError` (auth/quota/anything
   unattributable — CONSERVATIVE: an outcome the dispatcher cannot PROVE was about the message
   never burns that message's attempt) → the entry is REMOVED again before the run marks
   LLM-unavailable; only a **message-class outcome** — `SchemaValidationFailed`, an enum
   violation in a returned verdict, or a genuine verdict — consumes the lifetime attempt. Without this split, a
   day-long OAuth outage would permanently park one fresh message per sweep — 48 messages/day
   burned on failures that were never about them. Messages the run never reached are ledger-free
   and retry naturally. Ledger stays bounded: at run end, drop ULIDs no longer present in the
   inbox (routing/archive settled them).
4. Failure ladder: infra-class exception (step 3 taxonomy) → un-consume the ledger entry, mark
   LLM-unavailable for the REST of this run (no per-message retry storm), log loudly — the tail
   goes to the intel floater tier (charter-owned, never ownerless) and re-attempts LLM next run.
   Message-class failure → floater-routed, attempt consumed. Deterministic routing + Phase C
   escalation unaffected either way. NO dollar checks
   anywhere; log `DispatchResult.cost_usd` (or `cost=unknown` when None) in the summary line.
   **Per-run LLM-call bound** `FABRIK_MAIL_LLM_PER_RUN` (default 20 — a LATENCY bound, not a
   money cap: serial 120s calls would otherwise hold the lock for hours under a storm; the
   unreached tail is ledger-free and retries on the next trigger within minutes).
5. Tests (TDD for: message-class consumes / infra-class does NOT consume the ledger entry;
   boundary-collision parks; infra-class EXCEPTION → unavailable-for-run; enum violation →
   floater-routed, attempt consumed).
   `dispatch` is monkeypatched with stubs mirroring the REAL `DispatchResult` field names
   (`cost_usd`, `is_error`, `structured` — the vendor-integrity test pins them, so a stub can't
   drift from the frozen dataclass); no live LLM call in the suite (one optional live smoke
   behind `RUN_LIVE=1`, excluded from the gate). **Every mailbox-touching test sets
   `FABRIK_MAIL_ROOT` to a tmp fixture mailbox** (`scripts/mail.py:220` reads it; the
   `tests/test_mail.py` idiom) — no test ever reads or mutates `/opt/fabrik-mail`.
   **No-send invariant test:** monkeypatched `subprocess.run` records every argv across a full
   fixture-mailbox cycle; assert no argv contains the `send` subcommand (v1 sends NO mail is a
   TESTED invariant, not a File-Scope inference).

Phase gate: `uv run pytest tests/test_mail_dispatcher.py -q` → all pass (new tests seen RED
first on the four TDD rows).

### Behavior Contract
- **Given** a ULID already in the ledger, **When** the run reaches it, **Then** no dispatch happens and it is
  logged as ledger-settled → floater tier. (TDD)
- **Given** an infra-class dispatch failure (spawn/timeout/auth) on a message, **When** the run finishes,
  Then that message's ULID is NOT in the ledger (its lifetime attempt survives the outage). (TDD)
- **Given** `dispatch` raises on message 2 of 5, **When** the run continues, **Then** messages 3–5 get NO LLM
  calls this run and deterministic routing still applied where rules matched. (TDD)
- **Given** a full fixture-mailbox cycle, **When** every subprocess argv is recorded, **Then** none contains
  the `send` subcommand. (TDD)
- **Given** a body containing the boundary string, **When** framed, **Then** no call is made and the
  message goes to the floater tier. (TDD)
- **Given** a structured response whose beat is not in the enum, **When** validated, **Then** floater-
  routed, logged, ledger still consumed. (TDD)
- **Given** a successful classification, **When** routed, **Then** the summary line carries the estimated
  cost and the sanitized `why`.

Close: doc-sync check → **/fabrik-review on Phase B's surface to its coverage-adjudicated exit
(BLOCKING)** → commit + push.

## Phase C — Escalation, watcher units, install deliverables, docs, final gate

**Interfaces.Consumes:** Phase A scan (frontmatter access), Phase B summary line.
**Interfaces.Produces:** `escalate(inbox) -> int`; `configs/systemd/fabrik-mail-dispatcher.service`
(+ `.path`); `configs/logrotate/fabrik-mail-dispatcher`; the operator install block (cron line +
`systemctl --user enable --now` + logrotate copy) in `docs/workstation/fabrik-mail.md`.

Steps:
1. Escalation: dispatcher-side frontmatter scan over the UNACKED population — never the
   "unaddressed" one: **inbox `ack: required` regardless of `agent:`, PLUS archive strands**
   (`ack: required` files in `fabrik/archive/` with no `acked-by:` resolution line — the
   `mail.py:191` `_ACK_LINE` signal; `claim()` renames inbox→archive at `:745`, and measured
   2026-08-25 **8 of 13 live unacked obligations are archive strands** an inbox-only scan would
   never see) — aged `age_seconds(ts) >= FABRIK_MAIL_ESCALATE_DAYS * 86400` (inclusive, same as
   `digest()` `scripts/mail.py:1076`; default 3, env-overridable). **Age source is the
   frontmatter `ts`, NEVER file mtime** — `route()` rewrites via `os.replace`
   (`scripts/mail.py:801-803`), so mtime resets the moment the dispatcher routes a message and
   an mtime-based age would never escalate anything (test-green, production-silent).
   **Channel: the hub-vendored `libs/alerting` telegram module** — NOT `send-telegram.sh`
   (grounded out live: its required `TELEGRAM_BOT_TOKEN`/`TELEGRAM_OWNER_ID` do not exist in
   `/opt/fabrik/.env.sysadmin`, so it exits 1 unconditionally on this box; `libs/alerting`
   handles the split credential in `/opt/fabrik/.env` — `libs/alerting/telegram.py:3-21`).
   One Telegram per calendar day; **the day-stamp is written ONLY after a successful send,
   carrying the send-moment's date** (midnight-safe; a failed send leaves no stamp → next run
   retries, at most once per run, loud on stdout). Message content is `id · age(d) · beat`
   ONLY — no subject/body text, so length is arithmetic — oldest 20 + `+K more (total)`, plus
   the floater/LLM-unavailable health counts when nonzero, and a hard 3900-char
   truncation guard before the send (Telegram caps at 4096 and a 400 is non-retryable in most
   clients). NO `digest()` call — it MUTATES (`_quarantine`, `scripts/mail.py:1069-1071`).
   Tests: the alerting send function is monkeypatched (no live POST), day-stamp-after-success
   ordering (TDD: failed send → no stamp → next run retries), threshold boundary (exactly
   `N*86400` seconds → escalated, one second younger → not), archive-strand inclusion (TDD).
2. systemd USER units (files in-repo; operator symlinks/copies + enables). `.path` uses
   **`PathModified=/opt/fabrik-mail/fabrik/inbox` ONLY — never `DirectoryNotEmpty=`**: the inbox
   is NOT a drained spool (`route` rewrites in place, unacked mail sits for days), so
   `DirectoryNotEmpty=` re-fires the service forever on a non-empty inbox until
   `StartLimitBurst` flips the unit to `failed` and the "immediate" watcher silently dies —
   verified against `man systemd.path` re-check-on-deactivate semantics. Edge losses (an arrival
   while the service is active) are covered by the dispatcher's own quiescence loop (Phase A) +
   the cron sweep. The `.service` (oneshot) pins `WorkingDirectory=/opt/fabrik` and
   `ExecStart=/usr/bin/flock -w 30 -E 0 %h/.claude/state/mail-dispatcher.lock /usr/bin/python3
   /opt/fabrik/scripts/mail_dispatcher.py` — `%h` not `$HOME` (systemd does no shell expansion),
   `-w 30 -E 0` not `-n` (a `flock -n` miss exits 1, marks the oneshot `failed`, and a burst
   walks the unit into `StartLimitBurst` death; `-w` queues one waiter, `-E 0` keeps a timeout
   green), and **the SAME lock file the cron line uses** — one lock path,
   `%h/.claude/state/mail-dispatcher.lock` (parent `~/.claude/state/` EXISTS today; a lock under
   the not-yet-created `mail-dispatcher/` subdir would be a chicken-and-egg: flock cannot create
   the parent, the command never runs, the dir is never created). Gate (inspection, no state
   mutation): `systemd-analyze verify configs/systemd/fabrik-mail-dispatcher.service
   configs/systemd/fabrik-mail-dispatcher.path` → no errors.
3. Fallback cron line + logrotate snippet, verbatim in `docs/workstation/fabrik-mail.md` § Install
   (operator installs; agents never write the crontab):
   `*/30 * * * * flock -w 30 -E 0 $HOME/.claude/state/mail-dispatcher.lock python3 /opt/fabrik/scripts/mail_dispatcher.py >> /var/log/fabrik-mail-dispatcher.log 2>&1`
   (same single lock file as the systemd unit — cron sweep and watcher runs can never overlap;
   parent dir exists today, no chicken-and-egg).
   The install block ALSO carries (grounded this session): a one-time
   `sudo touch /var/log/fabrik-mail-dispatcher.log && sudo chown $USER: /var/log/fabrik-mail-dispatcher.log`
   (`/var/log` is not user-writable; the pre-created user-owned file is the existing
   `fabrik-audit.log` convention), and the linger probe
   `loginctl show-user $USER -p Linger` → `Linger=yes` (already yes on this box — without it the
   user systemd manager, and the .path unit with it, dies at logout).
4. Docs (Doc Sync Matrix rows this plan owes): `docs/reference/fabrik-mail.md` § Dispatcher
   (replaces the ":219 forthcoming" note — canonical behavior doc); `docs/workstation/fabrik-mail.md`
   § Install (box-local specifics); `.env.example` + `docs/CONFIGURATION.md`
   (`FABRIK_MAIL_ESCALATE_DAYS`); `INDEX.md` (new files); `CHANGELOG.md` entry;
   `docs/LESSONS_LEARNT.md` (entry or `none`). Pool-reconciled via `scripts/doc_reconcile.py`
   where it applies, coder-curated.
5. **/fabrik-docs-review** over the touched docs → truthful fixed point.
6. Final: `python scripts/final_gate.py --check --json` → `"status":"success"` AND
   `python scripts/enforcement/check_convergence.py` → green. (Necessary but not sufficient —
   the Evidence section is the proof of design.)

### Behavior Contract
- **Given** an obligation exactly at the threshold and today's escalation already sent, **When** run,
  **Then** no second Telegram today; tomorrow's first run sends it. (TDD)
- **Given** a message ROUTED three days ago (`agent:` set) and never acked, **When** the
  escalation leg runs, **Then** it IS escalated — the escalation population is unacked, never
  unaddressed. (TDD)
- **Given** 50 aging obligations, **When** the Telegram message is built, **Then** it enumerates
  the oldest 20 + `+30 more (50)` and stays under 4096 chars.
- **Given** the alerting send fails, **When** escalating, **Then** the run still exits 0 with the failure
  on stdout (alerting is best-effort; routing is the job).
- **Given** the unit files, **When** `systemd-analyze verify` runs, **Then** zero errors.
- **Given** a fresh clone, **When** `pytest` runs, **Then** no test touches the live mailbox, crontab,
  systemd state, or Telegram.

Close: doc-sync check → **/fabrik-review on Phase C's surface to its coverage-adjudicated exit
(BLOCKING)** → commit + push.

## Execution pillars (binding on /fabrik-execute-plan)

- **Review floor:** every phase ends with a full `/fabrik-review` on its changed surface run to a
  coverage-adjudicated exit BEFORE the next phase starts — written into each phase above.
- **Dispatch policy:** pool-default (`fanout` → `set_quality` back-fill) for gradeable fan-out —
  per-behavior test authoring (Phase A/B/C), review finders; native Claude on top for the
  authoritative high-risk pass (the LLM-call path, the untrusted-input frame) and the
  decide/refute/merge the executor owns. Never all-native.
- **Parallelism:** Phase A steps 2 (vendor) and 3 (rule derivation) are independent — fan out;
  test authoring fans out per behavior row; merge/dedupe at the executor before the phase gate.
  Phases are sequential (true data dependencies A→B→C).

## File Scope (owned paths)

- scripts/mail_dispatcher.py
- libs/llm_dispatch/
- tests/test_mail_dispatcher.py
- tests/fixtures/mail_dispatcher/
- configs/systemd/fabrik-mail-dispatcher.service
- configs/systemd/fabrik-mail-dispatcher.path
- configs/logrotate/fabrik-mail-dispatcher
- docs/reference/fabrik-mail.md
- docs/workstation/fabrik-mail.md
- docs/CONFIGURATION.md
- .env.example
- docs/development/reviews/2026-08-25-plan-1-mail-dispatcher-review.md

(CHANGELOG.md / INDEX.md / docs/LESSONS_LEARNT.md are shared-append surfaces outside the lock,
per the plan grammar. `scripts/mail.py` is deliberately NOT owned: it is a fleet-synced shared
surface this plan only CALLS — a bug discovered in it mid-run is reported and fixed as its own
change with its own gate, never silently patched under this plan's scope.)

## Evidence

Phase A grounding:
- `scripts/mail.py:758` — `def route(msg_id, to_agent, repo=None)`; raises `MailRefusedError` on
  a message not in the inbox (`:785-792`) → per-message catch is mandatory.
- `/opt/fabrik-lib/llm-dispatch/llm_dispatch.py:139-198` — `ClaudeCall` dataclass: `prompt`,
  `json_schema`, `tools: Sequence[str] | None` (`()` → `--tools ""`), `permission_mode`,
  `timeout_s: float = 300.0`, `bare: bool = False` (deliberate, live-proven 2026-08-03 comment).
- Labeled corpus measured live:

```
$ grep -l "^agent:" /opt/fabrik-mail/fabrik/archive/*.md | wc -l ; ls /opt/fabrik-mail/fabrik/archive/*.md | wc -l
35
144
```

Phase B grounding:
- `llm_dispatch.py:201-221` — `DispatchResult`; docstring: "`is_error` is the ONLY authority on
  success" (observed `is_error:true` + exit 0). Real field names, read live:

```
$ sed -n 215,219p /opt/fabrik-lib/llm-dispatch/llm_dispatch.py
    usage: dict[str, Any] | None = None  # opaque pass-through — keys are version-dependent
    cost_usd: float | None = None
    is_error: bool = False
    error_subtype: str | None = None
    terminal_reason: str | None = None
```
- Spec § External dependencies — headless docs live-fetched twice 2026-08-25
  (https://code.claude.com/docs/en/headless): `dontAsk`, schema conformance wording,
  `total_cost_usd` estimate, `--bare` future-default risk.

Phase C grounding:
- `scripts/sysadmin/send-telegram.sh:20-31` — `MESSAGE="${1:-}"`, `DRY_RUN=1` supported, exit 0/1,
  env from `/opt/fabrik/.env.sysadmin`.
- `scripts/mail.py:1069-1071` — `digest()` calls `_quarantine(inbox, f)` (it MUTATES) and scans
  every repo + archive strands → the dispatcher never calls it; escalation detail and counts are
  the dispatcher's own hub-inbox scan (spec erratum, corrected same-change).
- Environment probes, live this session:

```
$ which inotifywait; systemctl --user is-system-running
/usr/bin/inotifywait
running
$ ls /etc/logrotate.d/ | grep -c fabrik
0
```

- `docs/reference/fabrik-mail.md:219` — "the dispatcher, forthcoming" — the section this plan's
  docs step replaces.

## Self-audit

- Grounding passes: mail.py API (route/digest/quarantine read at source), llm-dispatch full
  dataclass read, telegram script read, environment probed (inotify, systemd user, logrotate),
  labeled-corpus measured, plan-name collision checked (`ls docs/development/plans/` → none today).
- (a) Coverage vs "What we already agreed": immediate → Phase C step 2 (.path unit) + criterion
  in spec; no $ caps → Global Constraints + Phase B step 4; no API key → Global Constraints +
  vendored `bare=False`; route-not-claim → Phase A step 4; v1 no sends → the TESTED no-send
  invariant (Phase B step 5 argv-recording test), not a File-Scope inference; escalation → Phase
  C step 1; rule seeding →
  Phase A step 3; operator install → Phase C steps 2-3. No gaps found.
- (b) Cross-phase signatures: `scan_unaddressed`/`classify_deterministic`/`apply_route` (A) are
  consumed by B's main-loop wiring and C's escalation scan under the same names; `Verdict` shape
  shared. Consistent.
- Wired consumer: the terminal consumer of everything is `scripts/mail_dispatcher.py` `main()`
  itself, invoked by the .path unit + cron line (Phase C) — no stored-and-never-read surface.
- Not yet a fixed point: `/fabrik-plan-review` owns convergence.

## Residual unknowns

- RESOLVED: trigger mechanism (systemd user .path — probed), auth path (subscription, vendored
  default), rule seeding source (measured 35/144), all operator decisions (amended spec).
- OPEN (self-service, non-blocking): the exact curated `RULES` content — Phase A step 3 derives
  it from the archive with a precision gate ≥0.8; no operator input needed.
- RESOLVED (was open): `.path` trigger semantics — settled by design, not probing:
  `DirectoryNotEmpty=` is BANNED here (permanent retrigger spin on a never-drained inbox →
  `StartLimitBurst` → silent watcher death, per `man systemd.path` re-check-on-deactivate);
  `PathModified=` edge-trigger + the dispatcher's quiescence loop + the cron sweep together
  cover every arrival pattern.

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

### core/10-python.md  (hit: scripts/mail_dispatcher.py, tests/test_mail_dispatcher.py)
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

### core/40-documentation.md  (hit: docs/CONFIGURATION.md, docs/reference/fabrik-mail.md, docs/workstation/fabrik-mail.md)
- **Tier-1 (cheap-pool author → verify → converge):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_mail_dispatcher.py)
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

## Coverage Checklist (derived from the rubric above + the four standing classes)

| Class | Verdict |
|---|---|
| Untrusted-input → instructions (35-security FLOOR) | FIXED(4) — boundary fence; `why` AND sender/subject sanitized; argv-not-shell telegram; argv-vs-stdin honesty note (hunted: Phase B 1-2, Phase C 1) |
| Config via env only, zero secrets in code (35-security FLOOR) | CLEAN — env vars with defaults only; secrets stay in `.env.sysadmin`, read only by send-telegram.sh (hunted: Global Constraints, Phase C) |
| 12F XI — stdout only, no app logfile/rotation | CLEAN — dispatcher prints to stdout; cron/systemd own redirection; logrotate is an operator install artifact (hunted: Global Constraints, Phase C 3) |
| 12F VIII — no daemonize / PID file | CLEAN — systemd .path owns the watch; oneshot run-to-completion script (hunted: Phase C 2) |
| 12F IX — disposability: crash-safe state, idempotent reruns | FIXED(3) — single shared lock, quiescence loop, ledger crash/prune semantics (hunted: Phase A Interfaces, Phase B 3) |
| 12F X / 25-postgres / 30-ops deploy rules — applicability | REFUTED — no backing service, no compose, no deploy: box-local workstation tooling (grounded: spec § Shape "None") |
| Watched-fail-first / behavior-without-a-test (45-testing + standing) | FIXED(2) — TDD rows marked per phase; no-send invariant and infra-class-ledger rows ADDED as tests (hunted: all three Behavior Contracts) |
| Test-runner + tooling conventions (uv vs venv pytest) | FIXED(1) — `uv run pytest` (uv.lock repo); stubs pinned to real `DispatchResult` fields by the vendor-integrity test (hunted: phase gates, Phase B 5) |
| Doc Sync Matrix completeness (40-documentation MATCHED) | CLEAN — Phase C 4 enumerates every fired row incl. `.env.example`+CONFIGURATION for the new env var; `/fabrik-docs-review` closes (hunted: Phase C 4-5 vs the Matrix) |
| Fail-open vs fail-closed on every gate/guard (standing) | FIXED(5) — `--repo fabrik` CWD trap; day-stamp-after-success; infra-vs-message ledger taxonomy; `/var/log` pre-create; `DirectoryNotEmpty` spin ban (hunted: every guard in A/B/C) |
| Cost/limit accounting edges under the no-caps regime (standing) | FIXED(2) — real field `cost_usd` (AttributeError-on-success-path trap); `cost=unknown` when None, gating nothing (hunted: Phase B 1,4) |
| Boundary/sentinel/prefix collisions (standing) | FIXED(2) — boundary-collision parks (tested); ONE lock path shared by both triggers, parent-exists chicken-and-egg closed (hunted: Phase B 2, Phase C 2-3) |
| Pool-default dispatch + flywheel recording named (62-subagents) | CLEAN — Execution pillars name pool-default + `set_quality` back-fill + native-on-top explicitly (hunted: § Execution pillars) |
