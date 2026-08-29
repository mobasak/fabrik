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
(`claude_rotate.py`, unchanged); switching the fleet's live crons to route through the governor is the LAST
wiring step (Phase C), gated on the governor being proven.

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
- **The reserve spans EVERY window the telemetry exposes** — today `_account_status` emits `five_hour` +
  `seven_day`; shed routine when `max(five_hour, seven_day)` ≥ the reserve threshold — **never weekly-only**
  (a 5h burst can cap ob@ while weekly is fine). The Opus-weekly sub-limit is separately tracked by Anthropic
  but is NOT in `_account_status` today; Phase A grounds whether the telemetry exposes it and, if so, extends
  the parse + the `max`. Until then Opus rides the weekly window (conservative: the weekly reserve already
  holds back headroom the Opus fix draws from).
- **Containers hold NO ob@ creds** — the credential stays on the host; containers reach only the
  completion-only broker (empty tool allowlist), never the operator's full-tool claude.
- **Fail-SAFE degraded state** — a failed `--status` probe / down governor defaults routine → pool, incident →
  ob@; consumers reach ob@ ONLY through the governor (no bypass).
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
| Headroom source (2 windows today) | `claude_rotate.py --status --json` → per-account `{five_hour:{utilization,resets_at_epoch}, seven_day:{…}}`. `_account_status` loops over exactly `("five_hour","seven_day")` and discards other keys — **no `opus_weekly` today** (Phase A grounds whether the telemetry has it) | `scripts/sysadmin/claude_rotate.py::_status_payload` :1205, `_account_status` :1139, window loop + utilization parse :1179-1186 |
| Reactive limit signal | `is_usage_limit(text)` — regex over weekly/session/5h/"out of extra usage" | `claude_rotate.py:92` |
| Host claude entrypoint | `claude-run.sh` runs claude via `claude_rotate` as the operator, one cred home | `scripts/sysadmin/claude-run.sh:6-18` |
| The pool (routine offload + sandboxed diagnosis) | `libs/subagents` — `sandbox=True` FAIL-closed default (`--unshare-net`, read-only host) confirms the pool can't touch the host → diagnosis-only over a host-marshalled bundle | `libs/subagents/agent.py:159` (tools_enabled), `:169` (sandbox), `sandbox.py` |
| Per-caller budget store — STDLIB file (NOT redis) | a JSON counter under `~/.claude/state/broker-budgets.json`, keyed by caller+window, reset from `resets_at_epoch`; NO `redis` dep (not importable in `.venv`) | `claude_rotate.py` state-file pattern (`.active-account`, `~/.claude/state/` VM-cut-survivable) |
| Alert transport | `claude-sound.sh mesh-notify <sid> <cwd> <err>` (Telegram) | `~/.claude/bin/claude-sound.sh:249` |
| Consumer inventory | the crons/scripts that spend ob@ today (route through the governor) | `bot.py`, `kaizen_*.py`, `weekly_catchup.sh`, `morning-report.sh`, `daily-digest.sh`, `weekly-security.sh`, `proactive-check.sh`, `canary_grounding.py`, `ci_health_probe.py`, `claude-keepalive-rotate.sh` (retire the ping) |

## Execution Discipline

- **Review floor:** each phase ends by running `/fabrik-review` on its changed surface to a coverage-adjudicated
  exit before commit (native Opus for the routing/security correctness — the broker auth + the governor's
  fail-safe + single-flight are high-risk); no phase commits on a first-pass green.
- **Dispatch:** pool-default (`fanout`) for the per-behavior tests; native Opus for the authoritative
  security/concurrency review + decide/merge. Flywheel-record every pool dispatch.
- **TDD the risky:** the reserve decision, the fail-safe default, the single-flight lock, the broker's
  empty-tool-allowlist + budget are watched-fail-first.

## Phase A — the governor router (`scripts/sysadmin/quota_governor.py`)

**One responsibility:** decide, per call, whether ob@ or the pool runs it — and never block an incident.

**Interfaces — Consumes:** `claude_rotate.py --status --json` (headroom), `is_usage_limit` (reactive).
**Produces:**
- `scripts/sysadmin/quota_governor.py`: `class QuotaGovernor` with `route(kind: Literal["incident","routine"], *, caller: str|None=None) -> Literal["ob@","pool","pool-diagnose"]`. Reads ob@'s per-window utilization from `claude_rotate --status --json`; **routine** → `pool` if `max(<every window in the payload>)` ≥ `RESERVE_PCT` (default 80, env `QUOTA_RESERVE_PCT`) else `ob@` — the `max` iterates whatever windows the payload carries (5h + weekly today, + Opus if Phase-A step 0 finds it), so a new window is covered by construction, never a hardcoded 2. **incident** → `ob@` if not capped, else `pool-diagnose`. Reactive: a returned `is_usage_limit` marks ob@ capped until that window's `resets_at_epoch`. **Fail-safe:** a `--status` failure → routine returns `pool`, incident returns `ob@`. **Single-flight:** an `ob@` incident takes a **non-blocking** `fcntl.flock(LOCK_NB)` on `~/.claude/state/quota-governor-incident.lock`; if the lock is HELD (another fix in flight), the incident routes to `pool-diagnose` + alerts (never blocks a cron, never double-spends ob@ on two concurrent fixes).
- Alerts: on a reserve-threshold or cap crossing, call `claude-sound.sh mesh-notify`.

**Steps:**
0. **Ground the window set:** run `claude_rotate.py --status --json` for ob@ and read the actual keys under a window record; if an Opus-weekly window is present, extend `_account_status`'s loop (`:1179`) to parse it so the governor's `max` includes it; if absent, proceed on `five_hour` + `seven_day` (Opus rides weekly per Global Constraints). Record which in a code comment.
1. **[TDD — highest risk] Write `tests/test_quota_governor.py` FIRST** (pool fanout): (a) routine sheds to pool when 5h util ≥80 even though weekly is low (multi-window proof); (a2) if an Opus window is present, routine sheds when ONLY Opus ≥80 (parametrized on the grounded window set); (b) routine runs on ob@ below the reserve; (c) incident always returns ob@ when not capped; (d) incident returns pool-diagnose when ob@ is capped; (e) `--status` failure → routine=pool, incident=ob@ (fail-safe); (f) a reactive `is_usage_limit` marks capped until that window's reset; (g) single-flight: with the lock held, a second incident returns `pool-diagnose` (non-blocking), the first keeps ob@. Mock `--status` output + `is_usage_limit` + the lock. Run → RED.
2. Implement `quota_governor.py`. Run → GREEN.
3. **Gate:** `python -m pytest tests/test_quota_governor.py -q`; ruff; mypy.
4. `python scripts/enforcement/check_doc_sync.py`.
5. **`/fabrik-review`** (native Opus — the fail-safe + single-flight + multi-window logic) → adjudicated exit.
6. Commit (explicit paths + provenance trailers).

**Behavior Contract:**
- **Given** ob@ 5h-utilization ≥ the reserve but weekly low, **When** a routine job routes, **Then** it goes to `pool` (multi-window reserve) (scripts/sysadmin/quota_governor.py).
- **Given** ob@ is capped, **When** an incident routes, **Then** it returns `pool-diagnose`, never blocked (scripts/sysadmin/quota_governor.py).
- **Given** the `--status` probe fails, **When** anything routes, **Then** routine→pool + incident→ob@ (fail-safe) (scripts/sysadmin/quota_governor.py).
- **Given** the single-flight lock is held by a live fix, **When** a second incident arrives, **Then** it routes to `pool-diagnose` (non-blocking, never a concurrent ob@ slot) (scripts/sysadmin/quota_governor.py).

## Phase B — the completion-only container broker (`scripts/sysadmin/claude_broker.py`)

**One responsibility:** give containers subscription-billed LLM completion on ob@ with NO host tools + NO creds.

**Interfaces — Consumes:** `QuotaGovernor` (A), `claude-run.sh` (host claude), the stdlib budget file.
**Produces:**
- `scripts/sysadmin/claude_broker.py`: a stdlib loopback/bridge-gateway service; `POST {prompt, model?}` →
  runs `claude -p` with the **empty-tool-allowlist invocation grounded in step 0** (no bash/edit/MCP) via the
  host entrypoint, returns the completion. Controls: **(a)** per-caller shared-token auth (`401` without a
  valid token); **(b)** per-caller budget — a **stdlib JSON file** `~/.claude/state/broker-budgets.json` keyed
  `caller → {five_hour:{count,resets_at_epoch}, seven_day:{…}}`, incremented per job; a window's count resets
  to 0 when `now ≥ resets_at_epoch` (the epoch comes from the same `--status` payload, so the reset tracks the
  real cap window); over-budget → `429` (or downgrade to pool); **(c)** an audit line per job (caller, prompt
  hash, tokens) to stdout; **(d)** class forced to `routine` from the caller identity (never self-labelled);
  the broker calls `QuotaGovernor.route("routine", caller=…)` — so a container job sheds to the pool under the
  reserve exactly like any routine work (returns a pool completion, never dropped).

**Steps:**
0. **Ground the empty-tool-allowlist incantation:** confirm the real Claude Code flag/env for "no tools" (`claude -p --allowedTools ""` vs a different form) via `claude --help` / the docs, so the confused-deputy defense is live, not a green-but-wrong test. Record the verified flag.
1. **[TDD] Write `tests/test_claude_broker.py` FIRST** (pool fanout): (a) a job with a valid token returns a completion; no/invalid token → 401; (b) the claude invocation carries the grounded empty-allowlist flag (no host tools) — assert the argv; (c) an over-budget caller → 429 (seed the JSON counter file); (d) the counter resets when `now ≥ resets_at_epoch` for that window; (e) the broker forces `routine` + calls the governor (a job under the reserve routes to pool, not ob@). Mock `claude-run.sh` + a temp budget file. Run → RED.
2. Implement `claude_broker.py` (stdlib JSON file counter — no redis dep). Run → GREEN.
3. **Gate + doc_sync.**
4. **`/fabrik-review`** (native Opus — the auth + empty-tool-allowlist + budget are the confused-deputy defenses) → adjudicated exit.
5. Commit.

**Behavior Contract:**
- **Given** a broker job, **When** it runs claude, **Then** the argv carries the grounded empty-tool-allowlist flag (no host tools ever) (scripts/sysadmin/claude_broker.py).
- **Given** a request without a valid per-caller token, **When** it hits the broker, **Then** it is refused 401 (scripts/sysadmin/claude_broker.py).
- **Given** a caller over its window budget, **When** it submits, **Then** it is refused 429 / downgraded; a crossed `resets_at_epoch` zeroes the counter (scripts/sysadmin/claude_broker.py).

## Phase C — context marshaller + wire consumers + retire the ping + dashboard + docs

**One responsibility:** make the pool-diagnosis path real, route the fleet's consumers through the governor,
and document it.

**Interfaces — Consumes:** `QuotaGovernor` (A), the pool (`libs/subagents`), the consumer scripts.
**Produces:**
- `scripts/sysadmin/incident_context.py`: a HOST-side marshaller (a plain script, run BEFORE the pool worker).
  Given an incident (the GlitchTip webhook payload), it writes a bundle **`incident_context.json`** — `{webhook,
  log_tails: {<container>: <docker logs tail>}, state: <docker ps + systemctl status>}` — **into the pool
  worker's worktree** (`libs/subagents` runs each worker in a git worktree; the bundle is placed there and its
  path passed in the worker prompt), so the read-only sandboxed worker reasons over it (it cannot fetch live
  context itself). The `pool-diagnose` path then dispatches a `libs/subagents` read-only worker over that bundle
  + `mesh-notify`s the operator with the proposal for a **gated apply (never auto-applied)**.
- **Wire the consumers** through `QuotaGovernor` (route every ob@ call): `bot.py`, `weekly_catchup.sh`, the
  kaizen crons, `morning-report.sh`/`daily-digest.sh`/`weekly-security.sh`, `proactive-check.sh`,
  `canary_grounding.py`, `ci_health_probe.py`, the daily-VPS-docs pipeline. **Per-consumer verdict** (F6):
  each row is tagged pure-reasoning→pool or needs-host-tools→ob@-low-priority (the spec names the criterion +
  the suspects `proactive-check.sh`/`weekly-security.sh`); classify each row and wire accordingly.
- **Retire the keepalive ping:** drop `claude -p ping` from `claude-keepalive-rotate.sh` under single-key (a
  regularly-used ob@ needs no warmth ping; it burns the quota being conserved).
- **The dashboard panel:** extend `quota_dashboard.py` with an ob@-VPS panel showing the governor's current
  routing mode + per-window headroom.
- **Docs:** `docs/workstation/vps-claude-quota-governance.md` (the box-local runbook) + INDEX row; CHANGELOG;
  the Doc Sync Matrix rows.

**Steps:**
1. **[TDD] Write `tests/test_incident_context.py` FIRST**: the marshaller assembles `incident_context.json` (webhook payload + a log-tail stub + a state stub) into the target worktree path; the pool-diagnose path dispatches read-only (assert no host-write tool) AND `mesh-notify`s + does NOT auto-apply. Run → RED.
2. Implement `incident_context.py` + the pool-diagnose dispatch. GREEN.
3. Wire the consumers (per-verdict) + retire the ping + the dashboard panel.
4. **Gate (whole-plan):** `python scripts/final_gate.py --check --json` → success + `check_convergence.py`.
5. **Doc Sync Matrix:** `docs/workstation/…` + INDEX + CHANGELOG + `docs/RESILIENCE.md` §7 if applicable.
6. **`/fabrik-review`** (native Opus — the marshaller + the consumer wiring) → adjudicated exit; then **`/fabrik-docs-review`** on the new runbook.
7. Commit + push.

**Behavior Contract:**
- **Given** an incident when ob@ is capped, **When** the diagnosis path runs, **Then** the host marshaller has written `incident_context.json` into the worktree BEFORE the read-only pool worker is dispatched (scripts/sysadmin/incident_context.py).
- **Given** a pool diagnosis completes, **When** ob@ is capped, **Then** the proposal is mesh-notify'd to the operator and NOT auto-applied (operator-gated) (scripts/sysadmin/incident_context.py).
- **Given** the single-key model, **When** the keepalive runs, **Then** it no longer issues a billed `claude -p ping` (scripts/sysadmin/claude-keepalive-rotate.sh).
- **Given** a wired consumer, **When** it needs an LLM step, **Then** it routes through `QuotaGovernor` (never a direct ob@ call) (the consumer scripts).

## File Scope (owned paths)

- scripts/sysadmin/quota_governor.py
- scripts/sysadmin/claude_broker.py
- scripts/sysadmin/incident_context.py
- scripts/sysadmin/claude-keepalive-rotate.sh   (retire the ping)
- scripts/sysadmin/quota_dashboard.py           (add the ob@-VPS panel)
- scripts/sysadmin/claude_rotate.py             (Phase-A step 0 only IF the telemetry exposes an Opus window — extend `_account_status`'s loop; else untouched)
- tests/test_quota_governor.py
- tests/test_claude_broker.py
- tests/test_incident_context.py
- docs/workstation/vps-claude-quota-governance.md
- (the consumer scripts wired in Phase C — `bot.py`, `kaizen_*.py`, `weekly_catchup.sh`, `morning-report.sh`, `daily-digest.sh`, `weekly-security.sh`, `proactive-check.sh`, `canary_grounding.py`, `ci_health_probe.py` — each a minimal route-through-the-governor edit)

(Runtime state — `~/.claude/state/broker-budgets.json`, `~/.claude/state/quota-governor-incident.lock` — is
OUTSIDE the repo, not a File-Scope path. Governance shared-append surfaces CHANGELOG.md / INDEX.md /
docs/README.md are updated per the Doc Sync Matrix, orchestrator-applied, outside the plan lock.)

## Behavior Contract (whole-plan, one row per user-observable behavior)

- **Given** a routine job and ob@ near ANY exposed cap window, **When** it routes, **Then** it goes to the pool (ob@ quota conserved).
- **Given** an incident, **When** it fires, **Then** it is handled on ob@ (headroom) or escalated with a pool diagnosis (capped) — never dropped, never blocked, never auto-applied when capped.
- **Given** a container, **When** it uses claude, **Then** it gets completion-only (no host tools, no creds) via the broker.
- **Given** the governor/probe is down, **When** anything routes, **Then** it fails SAFE (routine→pool).

## Evidence

```
$ grep -n "_status_payload\|_account_status" scripts/sysadmin/claude_rotate.py   # headroom source (2 windows)
1139:def _account_status(store: Path) -> dict:
1205:def _status_payload() -> dict:
$ sed -n '1179,1186p' scripts/sysadmin/claude_rotate.py | grep -o 'five_hour\|seven_day'  # ONLY 2 windows today
five_hour
seven_day
$ grep -n "def is_usage_limit" scripts/sysadmin/claude_rotate.py                 # reactive signal
92:def is_usage_limit(text: str) -> bool:
$ grep -n "sandbox: bool = True" libs/subagents/agent.py                         # pool sandboxed → diagnosis-only
169:    sandbox: bool = True
$ .venv/bin/python -c "import redis" 2>&1 | tail -1     # the sysadmin/gate interpreter — NO redis dep → stdlib file counter
ModuleNotFoundError: No module named 'redis'           # (bare python3 may see a user-site redis; the .venv is the operative one)
```

## Self-audit

- **Grounding:** every reuse point resolves to a real `path:line` (Context Ledger + Evidence). The headroom
  source emits **2 windows today** (5h+weekly), not 3 — the governor's `max` iterates the payload's actual
  windows (Phase-A step 0 grounds Opus), so no hardcoded window count. The budget store is a **stdlib file**
  (no redis dep — `import redis` fails under `.venv/bin/python`, the gate interpreter). The two external facts
  (Claude Max caps; docker #22066) are the spec's.
- **Constraint adherence:** no `ANTHROPIC_API_KEY`; no per-call cap (governor sheds routine only); containers
  completion-only; fail-safe; single-flight non-blocking; multi-window reserve; no new dependency — all traced
  to the CONVERGED spec.
- **No deferred questions:** the reserve threshold (default 80, env), the broker transport (loopback HTTP), the
  budget store (stdlib file), the single-flight semantics (non-blocking → pool-diagnose), and the per-consumer
  verdict criterion (the spec names it) are decided defaults, not `[OPEN]` residuals — the executor applies
  them without stopping. The two Phase-step-0 groundings (Opus window presence; empty-tool-allowlist flag) are
  runnable probes with a defined fallback, not open questions.

## Residual unknowns

**Resolved (from the spec's two review passes):** the full design — see the spec's `## Open unknowns`.

**Still-open (plan-time tuning/grounding, non-blocking, each with a defined default):** the exact reserve %
(default 80); broker transport (loopback HTTP default); whether the `--status` telemetry exposes an Opus
window (Phase-A step 0 probe — fallback: 2 windows, Opus rides weekly); the exact empty-tool-allowlist flag
(Phase-B step 0 probe); the per-consumer pure-reasoning-vs-host-tools verdicts (finalized per-row at Phase C
against each consumer's actual LLM step).
