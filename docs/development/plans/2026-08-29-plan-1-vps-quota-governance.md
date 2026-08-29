# Plan — VPS single-key Claude quota governance (ob@)

Status: DRAFT
Spec: docs/superpowers/specs/2026-08-29-vps-claude-quota-governance-design.md (CONVERGED)
Shape: MONOLITH — one cohesive `scripts/sysadmin/` toolset (governor + broker + marshaller) whose files
call each other; a spine+ticket set would serialize on shared paths. 3 phases.

## Scope of THIS plan (fleet, box-local sysadmin tooling)

Build the quota-governance layer the CONVERGED spec designed: **one system-wide claude on ob@ per VPS, kept
under its 5h + weekly caps without ever capping the sysadmin fix loop.** New code is all under
`scripts/sysadmin/` + `docs/workstation/` — no scaffold type, no deployed service, no DB, **no new python
dependency**. It VENDORS (reuses) the existing machinery and adds a governor router, a completion-only
container broker, and a host-side context marshaller. **Not in scope:** the WSL multi-account rotation
(`claude_rotate.py` core, unchanged); switching the fleet's live crons to route through the governor is the
LAST wiring step (Phase C), gated on the governor being proven.

## Intake Inventory (inherited from the spec — see its `## Intake Inventory`)

7 items, 6 IN / 1 OUT-OF-SCOPE (WSL rotation). Every operator decision (single-key ob@, no VPS account
rotation, no `ANTHROPIC_API_KEY`, no per-call $ cap, containers hold no creds) is a Global Constraint below.

## Global Constraints (every phase inherits)

- **Claude Code CLI + subscription OAuth ONLY** for the fix loop — never `ANTHROPIC_API_KEY` on the
  operational path (spec I6; `core/35-security-auth.md` secret handling; env-only config, 12-Factor III).
- **No per-call $ budget cap** on the sysadmin loop — the governor SHEDS routine demand, it never caps the
  fix (spec I6; `core/58-resilience.md` — degrade, don't block).
- **The fix is never DROPPED** — ob@ headroom → autonomous fix; ob@ capped → pool read-only diagnosis (from a
  host-marshalled bundle) + operator-gated apply (never auto-applied). Single-flight so concurrent incidents
  don't double-spend.
- **The reserve spans EVERY window the live `--status --json` payload exposes** — for the active ob@ account
  that means `five_hour`, `seven_day`, **AND every `model_windows` entry** (the per-model weekly sub-limits —
  Opus/Fable etc. — which `_usage_windows` already extracts; see the Context Ledger). Shed routine when
  `max(<every utilization in {five_hour, seven_day} ∪ model_windows.values()>)` ≥ the reserve threshold —
  **never weekly-only** (a 5h burst, or a per-model weekly wall, can cap ob@ while the top-level weekly is
  fine). The `max` iterates whatever windows the payload actually carries, so a new window is covered by
  construction — never a hardcoded count. **Phase-A step 0 grounds the live payload shape** (fleet vs legacy —
  see below) and enumerates its windows before the parser is written.
- **Containers hold NO ob@ creds** — the credential stays on the host; containers reach only the
  completion-only broker (empty tool allowlist), never the operator's full-tool claude.
- **Fail-SAFE degraded state** — a failed / unparseable `--status` probe / down governor defaults routine →
  pool, incident → ob@; consumers reach ob@ ONLY through the governor (no bypass). **`resets_at_epoch` may be
  `None`** (`_iso_to_epoch` returns `None` on a missing/garbage `resets_at` — `claude_rotate.py:1083`): a
  `None` epoch is treated as UNKNOWN, never as "already reset" and never fed to a `now ≥ epoch` comparison
  (which would raise) — the fail-safe default applies until a subsequent `--status` yields a real epoch
  (bounded so a one-off `None` never wedges a caller open or a cap closed forever — see Phase A/B).
- **The broker fails CLOSED on the tool-disable assertion** — it serves a container completion ONLY if it can
  PROVE the built-in tools are disabled for that invocation; if the empty-allowlist incantation cannot be
  verified (Phase-B step 0), the broker REFUSES to serve rather than fall open to an operator-tool `claude`
  reachable from a container (the confused-deputy the spec rejects).
- **No new dependency** — the broker's per-caller budget counter is a **stdlib local JSON file** under
  `~/.claude/state/` (the `redis` python client is NOT in the sysadmin `.venv`; adding it is a HARD STOP),
  matching the `claude_rotate.py` state-file convention. No new DB, no new deployed service. **Logs**
  unbuffered stdout (12-Factor XI).

## Context Ledger (grounded reuse — build against these)

| Source | What binds | Grounded ref |
|---|---|---|
| `core/58-resilience.md` (ACTIVE) | timeout/retry/circuit-breaker; degrade-don't-block; the governor is the degrade layer | pack |
| `core/75-workers-jobs.md` (ACTIVE) | the pool workers + the single-flight discipline for the fix loop | pack |
| `core/self-healing.md` (ACTIVE) | the escalation ladder (ob@ fix → pool diagnosis → operator gate) this governor orchestrates | pack |
| `core/35-security-auth.md` (ACTIVE) | broker per-caller token auth; secret (ob@ cred) stays host-side; no secret in code | pack |
| `core/45-testing-strategy.md` (ACTIVE) | one test per behavior, risk-ordered, TDD the risky | pack |
| **Headroom source — the LIVE `--status --json` contract (NOT the internal `_status_payload`)** | `claude_rotate.py --status --json` BRANCHES: on a **fleet-mode** box (≥1 scaffolded `~/.claude-fleet/` dir — TRUE on this box AND the single-key VPS) `_cmd_status` returns `_cmd_fleet_status` BEFORE it ever calls `_status_payload`, emitting `{fleet_root, accounts:[{email, slugs, five_hour, seven_day, model_windows, weekly_cap, cap_walled, …}], active, pending, …}`; only an **empty-fleet** box falls through to the legacy `_status_payload` shape. The governor consumes the ACTIVE ob@ account row and reads `five_hour`+`seven_day`+`model_windows` from it. | `claude_rotate.py::_cmd_status` fleet branch :1232-1234, `_cmd_fleet_status`/`_fleet_account_rows` :3202+ storing `model_windows` :3361-3371, `_usage_windows` (parses `five_hour`/`seven_day` + per-model `weekly_scoped`→`model_windows`) :3103-3141, legacy `_status_payload` :1205 (empty-fleet only), `_fleet_dirs` :2642 |
| Reactive limit signal | `is_usage_limit(text)` — regex over weekly/session/5h/"out of extra usage" | `claude_rotate.py:92` |
| Epoch parse (may be None) | `_iso_to_epoch(resets_at)` → `float | None` (None on missing/garbage) — every window's `resets_at_epoch` flows through it | `claude_rotate.py:1083-1093` |
| Host claude entrypoint | `claude-run.sh` runs claude via `claude_rotate` as the operator; `main` forwards `argv[1:]` to `run_claude` | `scripts/sysadmin/claude-run.sh:4-18`, `claude_rotate.py:4013,4110` |
| The pool (routine offload + sandboxed diagnosis) | `libs/subagents` — the `pool-diagnose` path is a SINGLE-SHOT read-only worker (`fanout(mode="read_only")`), which by contract requires the material it reasons over to be **INLINED into the worker's prompt text** — it is not a repo/tool-using agent. So the diagnosis is prose over an inlined bundle, sandboxed (`sandbox=True` default), no host writes, no network → diagnosis-only | `libs/subagents/agent.py:1152-1155` (read_only = single-shot, MUST inline), `loop.py:399` (`tools_enabled=False` → `[]` tools), `agent.py:169` (sandbox default) |
| Why INLINE, not a worktree path or `--ro-bind` read | a `tools_enabled=False` single-shot worker has NO file tools at all (`loop.py:399`); its native file tools are workdir-confined and RAISE on an absolute host path (`tools.py:86-97` `_resolve_in_workdir`→`WorkdirEscapeError`; `cat`/`ls`/`grep` excluded from `DEFAULT_ALLOWED_COMMANDS` `:51`); and the worktree is created INTERNALLY in `_run_one` (detached-HEAD, internal id — no pre-seed seam). Hence the bundle CONTENT is inlined, never handed as a path | `libs/subagents/tools.py:86-97,51`, `agent.py:722`, `workspace.py:89-104` |
| Per-caller budget store — STDLIB file (NOT redis) | a JSON counter under `~/.claude/state/broker-budgets.json`, keyed by caller+window, reset from `resets_at_epoch`; NO `redis` dep (not importable in `.venv`) | `claude_rotate.py` state-file pattern (`.active-account`, `~/.claude/state/` VM-cut-survivable) |
| Alert transport | `claude-sound.sh mesh-notify <sid> <cwd> <err>` (Telegram) | `~/.claude/bin/claude-sound.sh:249` |
| Consumer inventory | the crons/scripts that spend ob@ today (route through the governor) — all verified present under `scripts/sysadmin/` | `bot.py`, `kaizen_*.py`, `weekly_catchup.sh`, `morning-report.sh`, `daily-digest.sh`, `weekly-security.sh`, `proactive-check.sh`, `canary_grounding.py`, `ci_health_probe.py`, `claude-keepalive-rotate.sh` (retire the ping) |

## Execution Discipline

- **Review floor:** each phase ends by running `/fabrik-review` on its changed surface to a coverage-adjudicated
  exit before commit (native Opus for the routing/security correctness — the broker auth + the governor's
  fail-safe + single-flight are high-risk); no phase commits on a first-pass green.
- **Dispatch:** pool-default (`fanout`) for the per-behavior tests; native Opus for the authoritative
  security/concurrency review + decide/merge. Flywheel-record every pool dispatch.
- **TDD the risky:** the reserve decision, the fail-safe default, the single-flight lock, the broker's
  empty-tool-allowlist + fail-closed + budget are watched-fail-first.

## Phase A — the governor router (`scripts/sysadmin/quota_governor.py`)

**One responsibility:** decide, per call, whether ob@ or the pool runs it — and never block an incident.

**Interfaces — Consumes:** `claude_rotate.py --status --json` (headroom — the LIVE contract, fleet shape on
this box + the VPS), `is_usage_limit` (reactive).
**Produces:**
- `scripts/sysadmin/quota_governor.py`: `class QuotaGovernor` with `route(kind: Literal["incident","routine"], *, caller: str|None=None) -> Literal["ob@","pool","pool-diagnose"]`. Reads the ACTIVE ob@ account row from `claude_rotate --status --json` and collects its per-window utilizations: `{five_hour, seven_day} ∪ model_windows.values()`. **routine** → `pool` if `max(<those utilizations>)` ≥ `RESERVE_PCT` (default 80, env `QUOTA_RESERVE_PCT`) else `ob@` — the `max` iterates whatever windows the row carries, so the per-model weekly (Opus) wall is covered without a hardcoded count. **incident** → `ob@` if not capped, else `pool-diagnose`. Reactive: a returned `is_usage_limit` marks ob@ capped until the relevant window's `resets_at_epoch`. **None-epoch (MED-1):** a window whose `resets_at_epoch` is `None` is treated as UNKNOWN — never compared with `now`; a reactive cap with a `None` epoch holds for a bounded default `CAP_TTL_S` (env, default 6h ≈ the 5h window) then re-probes, so one unparseable payload never wedges ob@ capped forever. **Fail-safe:** a `--status` failure / unparseable row → routine returns `pool`, incident returns `ob@`. **Single-flight:** an `ob@` incident takes a **non-blocking** `fcntl.flock(LOCK_NB)` on `~/.claude/state/quota-governor-incident.lock`; if the lock is HELD (another fix in flight), the incident routes to `pool-diagnose` + alerts (never blocks a cron, never double-spends ob@ on two concurrent fixes).
- Alerts: on a reserve-threshold or cap crossing, call `claude-sound.sh mesh-notify`.

**Steps:**
0. **Ground the live payload shape + window set:** run `claude_rotate.py --status --json` on the target and read the ACTUAL top-level keys + the active ob@ row's keys. On a fleet-mode box (verified: this box + the VPS both carry `~/.claude-fleet/`) the row carries `five_hour`, `seven_day`, `model_windows` (+ `weekly_cap`/`cap_walled`); on an empty-fleet box it is the legacy `_status_payload` shape. Write the parser to the OBSERVED shape (prefer the fleet `accounts[active]` row; fall back to legacy) and enumerate every window it exposes. Record the observed shape + window list in a code comment. **Do NOT edit `_account_status`/`_status_payload`** — they are the legacy path `--status --json` bypasses in fleet mode; the governor is a READER of the CLI output, it does not modify the producer.
1. **[TDD — highest risk] Write `tests/test_quota_governor.py` FIRST** (pool fanout): (a) routine sheds to pool when 5h util ≥80 even though weekly is low (multi-window proof); (a2) routine sheds when ONLY a `model_windows` entry (e.g. Opus weekly) ≥80 — the per-model-weekly wall (fed a fleet-shape row fixture); (b) routine runs on ob@ below the reserve; (c) incident always returns ob@ when not capped; (d) incident returns pool-diagnose when ob@ is capped; (e) `--status` failure / unparseable row → routine=pool, incident=ob@ (fail-safe); (f) a reactive `is_usage_limit` marks capped until that window's reset; (f2) a window with `resets_at_epoch = None` never raises and un-caps after `CAP_TTL_S` (None-epoch boundary); (g) single-flight: with the lock held, a second incident returns `pool-diagnose` (non-blocking), the first keeps ob@. Fixtures use the REAL fleet `--status --json` shape. Mock `--status` output + `is_usage_limit` + the lock. Run → RED.
2. Implement `quota_governor.py`. Run → GREEN.
3. **Gate:** `python -m pytest tests/test_quota_governor.py -q`; ruff; mypy.
4. `python scripts/enforcement/check_doc_sync.py`.
5. **`/fabrik-review`** (native Opus — the fail-safe + single-flight + multi-window + None-epoch logic) → adjudicated exit.
6. Commit (explicit paths + provenance trailers).

**Behavior Contract:**
- **Given** the ob@ row's 5h-utilization ≥ the reserve but weekly low, **When** a routine job routes, **Then** it goes to `pool` (multi-window reserve) (scripts/sysadmin/quota_governor.py).
- **Given** ONLY a `model_windows` (Opus/model-weekly) utilization ≥ the reserve, **When** a routine job routes, **Then** it goes to `pool` (the per-model weekly wall is covered) (scripts/sysadmin/quota_governor.py).
- **Given** ob@ is capped, **When** an incident routes, **Then** it returns `pool-diagnose`, never blocked (scripts/sysadmin/quota_governor.py).
- **Given** a window with `resets_at_epoch = None`, **When** anything routes, **Then** no `now ≥ None` comparison is made and the cap un-holds after `CAP_TTL_S` (scripts/sysadmin/quota_governor.py).
- **Given** the `--status` probe fails or the row is unparseable, **When** anything routes, **Then** routine→pool + incident→ob@ (fail-safe) (scripts/sysadmin/quota_governor.py).
- **Given** the single-flight lock is held by a live fix, **When** a second incident arrives, **Then** it routes to `pool-diagnose` (non-blocking, never a concurrent ob@ slot) (scripts/sysadmin/quota_governor.py).

## Phase B — the completion-only container broker (`scripts/sysadmin/claude_broker.py`)

**One responsibility:** give containers subscription-billed LLM completion on ob@ with NO host tools + NO creds.

**Interfaces — Consumes:** `QuotaGovernor` (A), `claude-run.sh` (host claude), the stdlib budget file.
**Produces:**
- `scripts/sysadmin/claude_broker.py`: a stdlib loopback/bridge-gateway service; `POST {prompt, model?}` →
  runs `claude -p` with the **empty-tool-allowlist invocation grounded + fail-closed in step 0** (no
  bash/edit/MCP) via the host entrypoint, returns the completion. Controls: **(a)** per-caller shared-token
  auth (`401` without a valid token); **(b)** per-caller budget — a **stdlib JSON file**
  `~/.claude/state/broker-budgets.json` keyed `caller → {five_hour:{count,resets_at_epoch}, seven_day:{…}}`,
  incremented per job; a window's count resets to 0 when `now ≥ resets_at_epoch` — and when
  `resets_at_epoch is None` the counter is NOT reset on this cycle (never `now ≥ None`) but re-checked on the
  next `--status`, so a `None` never permanently 429s a caller (MED-1); over-budget → `429` (or downgrade to
  pool); **(c)** an audit line per job (caller, prompt hash, tokens) to stdout; **(d)** class forced to
  `routine` from the caller identity (never self-labelled); the broker calls
  `QuotaGovernor.route("routine", caller=…)` — so a container job sheds to the pool under the reserve exactly
  like any routine work (returns a pool completion, never dropped). **Fail-CLOSED (MED-2):** if step 0 cannot
  verify the invocation disables the built-in tools, the broker refuses to serve (503/misconfig) rather than
  run an operator-tool `claude` for a container.

**Steps:**
0. **Ground the empty-tool-allowlist incantation — with a fallback, fail-closed:** confirm the real Claude Code invocation that disables ALL built-in tools for a headless `-p` run (`claude -p --allowedTools ""` vs a `--permission-mode`/deny form) via `claude --help` / the docs, and PROVE it (a probe run that shows a tool call is refused). If the empty-allowlist form is not reliably "deny all", use the verified deny form instead. **If NO reliable deny incantation exists, the broker fails CLOSED** — it does not serve, and Phase B surfaces this as a BLOCKED finding (never ship an operator-tool claude reachable from a container). Record the verified invocation.
1. **[TDD] Write `tests/test_claude_broker.py` FIRST** (pool fanout): (a) a job with a valid token returns a completion; no/invalid token → 401; (b) the claude invocation carries the grounded tool-disable flag (no host tools) — assert the argv; (b2) if the tool-disable assertion is unset/unverifiable, the broker refuses to serve (fail-closed), never invokes an unrestricted claude; (c) an over-budget caller → 429 (seed the JSON counter file); (d) the counter resets when `now ≥ resets_at_epoch`, and a `None` epoch neither resets nor raises (MED-1); (e) the broker forces `routine` + calls the governor (a job under the reserve routes to pool, not ob@). Mock `claude-run.sh` + a temp budget file. Run → RED.
2. Implement `claude_broker.py` (stdlib JSON file counter — no redis dep). Run → GREEN.
3. **Gate + doc_sync.**
4. **`/fabrik-review`** (native Opus — the auth + tool-disable-or-fail-closed + budget are the confused-deputy defenses) → adjudicated exit.
5. Commit.

**Behavior Contract:**
- **Given** a broker job, **When** it runs claude, **Then** the argv carries the grounded tool-disable flag (no host tools ever) (scripts/sysadmin/claude_broker.py).
- **Given** step 0 could not verify a tool-disable incantation, **When** a container requests a completion, **Then** the broker refuses to serve (fail-closed), never an operator-tool claude (scripts/sysadmin/claude_broker.py).
- **Given** a request without a valid per-caller token, **When** it hits the broker, **Then** it is refused 401 (scripts/sysadmin/claude_broker.py).
- **Given** a caller over its window budget, **When** it submits, **Then** it is refused 429 / downgraded; a crossed `resets_at_epoch` zeroes the counter and a `None` epoch neither resets nor raises (scripts/sysadmin/claude_broker.py).

## Phase C — context marshaller + wire consumers + retire the ping + dashboard + docs

**One responsibility:** make the pool-diagnosis path real, route the fleet's consumers through the governor,
and document it.

**Interfaces — Consumes:** `QuotaGovernor` (A), the pool (`libs/subagents`), the consumer scripts.
**Produces:**
- `scripts/sysadmin/incident_context.py`: a HOST-side marshaller (a plain script, run BEFORE the pool worker).
  Given an incident (the GlitchTip webhook payload), it writes a bundle to a **stable host path**
  `~/.claude/state/incidents/<incident_id>.json` — `{webhook, log_tails: {<container>: <docker logs --tail
  200, env `INCIDENT_LOG_TAIL_LINES` default 200>}, state: <docker ps + systemctl status>}` — for durability +
  operator inspection. The concrete 200-line bound is what keeps the inlined bundle size bounded. The
  `pool-diagnose` path then reads that bundle and **INLINES its (bounded) content into the worker's prompt
  text**, dispatching a `libs/subagents` SINGLE-SHOT read-only worker (`fanout(mode="read_only")`, which sets
  `allow_ungrounded` itself). The worker reasons over the inlined bundle and returns a prose diagnosis — it is
  NOT given the bundle as a path and NOT expected to read files: a `tools_enabled=False` single-shot worker has
  no file tools (`loop.py:399`) and a grounded single-shot dispatch is refused unless content is inlined
  (`agent.py:1152`). `libs/subagents` is untouched (out of File Scope) — inlining needs no dispatch-seam edit.
  The path then `mesh-notify`s the operator with the proposal for a **gated apply (never auto-applied)**.
- **Wire the consumers** through `QuotaGovernor` (route every ob@ call): `bot.py`, `weekly_catchup.sh`, the
  kaizen crons, `morning-report.sh`/`daily-digest.sh`/`weekly-security.sh`, `proactive-check.sh`,
  `canary_grounding.py`, `ci_health_probe.py`, the daily-VPS-docs pipeline. **Per-consumer verdict:**
  each row is tagged pure-reasoning→pool or needs-host-tools→ob@-low-priority (the spec names the criterion +
  the suspects `proactive-check.sh`/`weekly-security.sh`); classify each row and wire accordingly.
- **Retire the keepalive ping:** drop `claude -p ping` from `claude-keepalive-rotate.sh` under single-key (a
  regularly-used ob@ needs no warmth ping; it burns the quota being conserved).
- **The dashboard panel:** extend `quota_dashboard.py` with an ob@-VPS panel showing the governor's current
  routing mode + per-window headroom (incl. `model_windows`).
- **Docs:** `docs/workstation/vps-claude-quota-governance.md` (the box-local runbook) + INDEX row; CHANGELOG;
  the Doc Sync Matrix rows.

**Steps:**
1. **[TDD] Write `tests/test_incident_context.py` FIRST**: the marshaller assembles the bundle (webhook payload + a log-tail stub + a state stub) at the host path `~/.claude/state/incidents/<id>.json`; the pool-diagnose path dispatches a SINGLE-SHOT read-only worker with the bundle's CONTENT inlined into the prompt text (assert the prompt string contains the log-tail/state text — not a bare path), AND `mesh-notify`s + does NOT auto-apply. Run → RED.
2. Implement `incident_context.py` + the pool-diagnose dispatch (durable host-path bundle + inlined-content single-shot `fanout(mode="read_only")`). GREEN.
3. Wire the consumers (per-verdict) + retire the ping + the dashboard panel.
4. **Gate (whole-plan):** `python scripts/final_gate.py --check --json` → success + `check_convergence.py`.
5. **Doc Sync Matrix:** `docs/workstation/…` + INDEX + CHANGELOG + `docs/RESILIENCE.md` §7 if applicable.
6. **`/fabrik-review`** (native Opus — the marshaller + the consumer wiring) → adjudicated exit; then **`/fabrik-docs-review`** on the new runbook.
7. Commit + push.

**Behavior Contract:**
- **Given** an incident when ob@ is capped, **When** the diagnosis path runs, **Then** the host marshaller has written the bundle to `~/.claude/state/incidents/<id>.json` and the single-shot read-only worker's prompt carries the bundle's inlined CONTENT (not a path), BEFORE the worker is dispatched (scripts/sysadmin/incident_context.py).
- **Given** a pool diagnosis completes, **When** ob@ is capped, **Then** the proposal is mesh-notify'd to the operator and NOT auto-applied (operator-gated) (scripts/sysadmin/incident_context.py).
- **Given** the single-key model, **When** the keepalive runs, **Then** it no longer issues a billed `claude -p ping` (scripts/sysadmin/claude-keepalive-rotate.sh).
- **Given** a wired consumer, **When** it needs an LLM step, **Then** it routes through `QuotaGovernor` (never a direct ob@ call) (the consumer scripts).

## File Scope (owned paths)

- scripts/sysadmin/quota_governor.py
- scripts/sysadmin/claude_broker.py
- scripts/sysadmin/incident_context.py
- scripts/sysadmin/claude-keepalive-rotate.sh   (retire the ping)
- scripts/sysadmin/quota_dashboard.py           (add the ob@-VPS panel)
- tests/test_quota_governor.py
- tests/test_claude_broker.py
- tests/test_incident_context.py
- docs/workstation/vps-claude-quota-governance.md
- (the consumer scripts wired in Phase C — `bot.py`, `kaizen_*.py`, `weekly_catchup.sh`, `morning-report.sh`, `daily-digest.sh`, `weekly-security.sh`, `proactive-check.sh`, `canary_grounding.py`, `ci_health_probe.py` — each a minimal route-through-the-governor edit)

**Explicitly OUT of scope (do not edit):** `scripts/sysadmin/claude_rotate.py` (the governor READS its
`--status --json` output; it never modifies the producer — HIGH-1/2 corrected), and `libs/subagents/**` (the
pool-diagnose path INLINES the bundle content into a single-shot `fanout(mode="read_only")` worker — no
dispatch-seam edit, no worktree pre-seed — HIGH-3 corrected).

(Runtime state — `~/.claude/state/broker-budgets.json`, `~/.claude/state/quota-governor-incident.lock`,
`~/.claude/state/incidents/*.json` — is OUTSIDE the repo, not a File-Scope path. Governance shared-append
surfaces CHANGELOG.md / INDEX.md / docs/README.md are updated per the Doc Sync Matrix, orchestrator-applied,
outside the plan lock.)

## Behavior Contract (whole-plan, one row per user-observable behavior)

- **Given** a routine job and ob@ near ANY exposed cap window (5h, weekly, or a per-model weekly), **When** it routes, **Then** it goes to the pool (ob@ quota conserved).
- **Given** an incident, **When** it fires, **Then** it is handled on ob@ (headroom) or escalated with a pool diagnosis (capped) — never dropped, never blocked, never auto-applied when capped.
- **Given** a container, **When** it uses claude, **Then** it gets completion-only (no host tools, no creds) via the broker — or the broker fails CLOSED if it cannot prove tools are disabled.
- **Given** the governor/probe is down or a window epoch is None, **When** anything routes, **Then** it fails SAFE (routine→pool) without raising.

## Evidence

```
$ python3 scripts/sysadmin/claude_rotate.py --status --json | python3 -c "import sys,json;d=json.load(sys.stdin);print('TOP',list(d.keys()));print('ROW',list(d['accounts'][0].keys()))"
TOP ['fleet_root', 'accounts', 'active', 'pending', 'pause', 'fleet_warnings']   # FLEET shape — not _status_payload
ROW ['email', 'slugs', 'five_hour', 'seven_day', 'source', 'age_s', 'refresh_expires_epoch', 'identity_mismatches', 'weekly_cap', 'cap_walled', 'model_windows']
$ sed -n '1232,1235p' scripts/sysadmin/claude_rotate.py    # --status branches to fleet BEFORE _status_payload
    fleet_dirs = _fleet_dirs()
    if fleet_dirs:
        return _cmd_fleet_status(fleet_dirs, as_json)
    pay = _status_payload()
$ grep -n "model_windows" scripts/sysadmin/claude_rotate.py | head -3   # per-model weekly windows stored (model-agnostic by display_name; live payload: Fable)
3140:        out["model_windows"] = models
3370:                if c.get("model_windows"):
3371:                    row["model_windows"] = c["model_windows"]
$ grep -n "def is_usage_limit\|def _iso_to_epoch" scripts/sysadmin/claude_rotate.py   # reactive + epoch(None)
92:def is_usage_limit(text: str) -> bool:
1083:def _iso_to_epoch(s: object) -> float | None:
$ grep -n "if tools_enabled else" libs/subagents/loop.py    # tools_enabled=False → [] tools (single-shot prose)
399:        (list(TOOL_SCHEMAS) if tools_enabled else [])
$ grep -n "create_worktree" libs/subagents/agent.py     # worktree is INTERNAL (no pre-seed seam) → inline instead
9:2. each agent gets its **own git worktree** (``workspace.create_worktree``);
722:                wt = await asyncio.to_thread(workspace.create_worktree, repo, agent_id)
$ .venv/bin/python -c "import redis" 2>&1 | tail -1     # the sysadmin/gate interpreter — NO redis dep → stdlib file counter
ModuleNotFoundError: No module named 'redis'           # (bare python3 may see a user-site redis; the .venv is the operative one)
```

## Self-audit

- **Grounding:** every reuse point resolves to a real `path:line` (Context Ledger + Evidence), re-verified live
  this run. The headroom source is the **live `--status --json` fleet contract** (`accounts[active]` row with
  `five_hour`+`seven_day`+`model_windows`), NOT the internal `_status_payload`/`_account_status` legacy path
  that `--status --json` bypasses in fleet mode (HIGH-1). `_usage_windows` extracts EVERY per-model
  `weekly_scoped` window by `display_name` into `model_windows` — model-AGNOSTIC (the live payload carries
  `Fable`; an Opus weekly sub-limit is covered by the SAME mechanism whenever it appears, not asserted present
  today), so the reserve's `max` iterates them (HIGH-2). The pool-diagnose
  path INLINES the bundle content into a single-shot `fanout(mode="read_only")` worker (a `tools_enabled=False`
  worker has no file tools and grounded single-shot is refused unless inlined — `loop.py:399`, `agent.py:1152`),
  not a worktree pre-seed nor a path-read the API can't do (HIGH-3). `None`
  `resets_at_epoch` is handled everywhere it is consumed (MED-1). The broker fails CLOSED if the tool-disable
  incantation is unverifiable (MED-2). The budget store is a **stdlib file** (no redis dep — `import redis`
  fails under `.venv/bin/python`, the gate interpreter). The two external facts (Claude Max caps; docker
  #22066) are the spec's.
- **Constraint adherence:** no `ANTHROPIC_API_KEY`; no per-call cap (governor sheds routine only); containers
  completion-only + broker fail-closed; fail-safe (incl. None-epoch); single-flight non-blocking; multi-window
  reserve incl. model_windows; no new dependency; `claude_rotate.py` + `libs/subagents` OUT of scope — all
  traced to the CONVERGED spec.
- **No deferred questions:** the reserve threshold (default 80, env), `CAP_TTL_S` (default 6h, env), the broker
  transport (loopback HTTP), the budget store (stdlib file), the single-flight semantics (non-blocking →
  pool-diagnose), the bundle path (`~/.claude/state/incidents/<id>.json`), the inlined log-tail bound
  (`INCIDENT_LOG_TAIL_LINES` default 200 — the concrete knob that bounds bundle size), and the per-consumer verdict
  criterion (the spec names it) are decided defaults, not `[OPEN]` residuals — the executor applies them
  without stopping. The two Phase-step-0 groundings (live payload shape + window set; the tool-disable
  incantation) are runnable probes: the first has a defined fallback (fleet→legacy shape), the second fails
  CLOSED (a BLOCKED finding) rather than shipping an open door — neither is an open question.

## Coverage Checklist

Classes derived from the rubric (not from memory) + the four standing recurrence classes. Ran:

```
$ python3 scripts/review_rubric.py --changed scripts/sysadmin/quota_governor.py \
    scripts/sysadmin/claude_broker.py scripts/sysadmin/incident_context.py
# FLOOR: core/35-security-auth · core/25-data-postgres · core/30-ops · 12-FACTOR (all axes)
```

Each row adjudicates whether the PLAN's design + Behavior Contracts close the class for a cold executor
(a plan can't carry a runtime bug in code not yet written — the sweep is: does the design handle the class).

| # | Failure class (rubric / standing) | Swept against | Verdict |
|---|---|---|---|
| 1 | **fail-open / fail-silent** (standing) | Fail-SAFE degraded state (Global Constraint + Phase-A BC: `--status` fail/unparseable → routine=pool, incident=ob@; consumers reach ob@ ONLY via the governor, no bypass); broker fails CLOSED on the tool-disable assertion (MED-2) | FIXED (MED-2) |
| 2 | **cost/quota accounting** (standing) | the plan's whole subject — multi-window reserve via `max({five_hour,seven_day} ∪ model_windows)` (incl. per-model weekly), per-caller budget file with `resets_at_epoch` reset, no per-call $ cap | FIXED (HIGH-2) |
| 3 | **boundary / sentinel** (standing) | budget window reset at `now ≥ resets_at_epoch`; **`None` epoch never compared with `now` and un-holds after `CAP_TTL_S`** (MED-1); single-flight `flock(LOCK_NB)` held→pool-diagnose boundary; tool-disable argv (grounded Phase-B step 0) | FIXED (MED-1) |
| 4 | **behavior-without-a-test** (standing) | every Behavior Contract row carries a `(path)`; Phase steps write tests FIRST (TDD), watched-fail-first on the reserve / fail-safe / None-epoch / single-flight / broker-auth+fail-closed risky paths; fixtures use the REAL fleet `--status --json` shape | CLEAN |
| 5 | **config-via-env / no hardcoded secret** (12-Factor III · core/35) | no `ANTHROPIC_API_KEY`; ob@ cred stays host-side; broker per-caller token; `RESERVE_PCT`/`CAP_TTL_S` env-configurable | CLEAN |
| 6 | **confused-deputy / auth boundary** (core/35) | broker tool-disable (no host tools) + **fail-CLOSED if unverifiable** + per-caller token 401 + containers hold no creds + class forced server-side | FIXED (MED-2) |
| 7 | **degrade-don't-block** (core/58) | governor SHEDS routine only, never caps the fix; incident never dropped/blocked/auto-applied-when-capped | CLEAN |
| 8 | **spec / Global-Constraint contradiction** | Self-audit traces every constraint to the CONVERGED spec; no phase step contradicts it; `claude_rotate.py` + `libs/subagents` explicitly OUT of scope | CLEAN |
| 9 | **12-Factor IV backing-service swap = config not code / no new dep** | budget store is a stdlib JSON file — no `redis` dep added to the `.venv` (HARD STOP avoided) | CLEAN |
| 10 | **Evidence reproducibility (proxy-never-evidence)** | Evidence commands re-run live this pass; the live `--status --json` shape, the fleet branch, `model_windows`, and the redis-absence proof (pinned to `.venv/bin/python`) all captured verbatim | FIXED (F8+HIGH-1) |
| 11 | **ungrounded external/telemetry claim** | data source re-grounded on the LIVE `--status --json` **fleet** contract (`accounts[active]` row), not the legacy `_status_payload`; `model_windows` confirmed exposed + parsed (model-agnostic by `display_name`; live payload carries `Fable`, Opus covered by the same mechanism if present — not claimed live); marshaller re-grounded on an INLINED single-shot `fanout(mode="read_only")` worker (a `tools_enabled=False` worker has no file tools; the worktree is internal — neither a worktree pre-seed nor a `--ro-bind` path-read is usable) | FIXED (HIGH-1/2/3) |
| 12 | **mechanism self-consistency (pool dispatch)** | pass-2 caught the first HIGH-3 fix asserting `tools_enabled=False` yet a `--ro-bind` path-read (contradictory — no file tools); re-fixed to inline the bundle content, the canonical read_only single-shot contract | FIXED (pass-2 HIGH) |

Exit: pass 1 (author-blind native Opus grounding + pool breadth) raised 5 (3 HIGH + 2 MED), all CONFIRMED and
FIXED; pass 2 (author-blind native Opus) confirmed those 5 TRUE, REFUTED the scale-mismatch risk, and raised 2
NEW (1 HIGH mechanism-contradiction + 1 MED Evidence-reproducibility), both FIXED here. The next full pass must
reach a zero-new, md5-verified no-op before the flip. No UNCHECKED rows, no `## BLOCKED` escalation owed.

## Residual unknowns

**Resolved (from the spec's two review passes):** the full design — see the spec's `## Open unknowns`.

**Still-open (plan-time tuning/grounding, non-blocking, each with a defined default):** the exact reserve %
(default 80); `CAP_TTL_S` (default 6h); the inlined log-tail bound (`INCIDENT_LOG_TAIL_LINES` default 200);
broker transport (loopback HTTP default); the live `--status --json`
shape on the VPS (Phase-A step 0 probe — fallback: fleet→legacy shape, both handled); the exact tool-disable
incantation (Phase-B step 0 probe — fails CLOSED if none is verifiable); the per-consumer
pure-reasoning-vs-host-tools verdicts (finalized per-row at Phase C against each consumer's actual LLM step).
