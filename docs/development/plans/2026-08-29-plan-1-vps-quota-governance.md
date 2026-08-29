# Plan — VPS single-key Claude quota governance (ob@)

Status: DRAFT
Spec: docs/superpowers/specs/2026-08-29-vps-claude-quota-governance-design.md (CONVERGED)
Shape: MONOLITH — one cohesive `scripts/sysadmin/` toolset (governor + broker + marshaller) whose files
call each other; a spine+ticket set would serialize on shared paths. 3 phases.

## Scope of THIS plan (fleet, box-local sysadmin tooling)

Build the quota-governance layer the CONVERGED spec designed: **one system-wide claude on ob@ per VPS, kept
under its 5h+weekly+Opus caps without ever capping the sysadmin fix loop.** New code is all under
`scripts/sysadmin/` + `docs/workstation/` — no scaffold type, no deployed service, no DB. It VENDORS (reuses)
the existing machinery and adds a governor router, a completion-only container broker, and a host-side context
marshaller. **Not in scope:** the WSL multi-account rotation (`claude_rotate.py`, unchanged); actually
switching the fleet's live crons to route through the governor is the LAST wiring step (Phase C), gated on the
governor being proven.

## Intake Inventory (inherited from the spec — see its `## Intake Inventory`)

7 items, 6 IN / 1 OUT-OF-SCOPE (WSL rotation). Every operator decision (single-key ob@, no VPS account
rotation, no `ANTHROPIC_API_KEY`, no per-call $ cap, containers hold no creds) is a Global Constraint below.

## Global Constraints (every phase inherits)

- **Claude Code CLI + subscription OAuth ONLY** for the fix loop — never `ANTHROPIC_API_KEY` on the
  operational path (spec I6; `core/35-security-auth.md` secret handling; env-only config, 12-Factor III).
- **No per-call $ budget cap** on the sysadmin loop — the governor SHEDS routine demand, it never caps the
  fix (spec I6; `core/58-resilience.md` — degrade, don't block).
- **The fix is never DROPPED** — ob@ headroom → autonomous fix; ob@ capped → pool read-only diagnosis (from a
  host-marshalled bundle) + operator-gated apply. Single-flight so concurrent incidents serialize.
- **The reserve spans ALL THREE cap windows** (5h-rolling + 7-day-weekly + Opus-weekly): shed routine when
  `max(utilization)` ≥ the reserve threshold — never weekly-only.
- **Containers hold NO ob@ creds** — the credential stays on the host; containers reach only the
  completion-only broker (empty tool allowlist), never the operator's full-tool claude.
- **Fail-SAFE degraded state** — a failed `--status` probe / down governor defaults routine → pool, incident →
  ob@; consumers reach ob@ ONLY through the governor (no bypass).
- **Backing services** — the broker's per-caller budget counter uses the existing `redis-main` (`REDIS_URL`
  config, never `localhost`); no new DB, no new deployed service. **Logs** unbuffered stdout (12-Factor XI).

## Context Ledger (grounded reuse — build against these)

| Source | What binds | Grounded ref |
|---|---|---|
| `core/58-resilience.md` (ACTIVE) | timeout/retry/circuit-breaker; degrade-don't-block; the governor is the degrade layer | pack |
| `core/75-workers-jobs.md` (ACTIVE) | the pool workers + the single-flight/queue discipline for the fix loop | pack |
| `core/self-healing.md` (ACTIVE) | the escalation ladder (ob@ fix → pool diagnosis → operator gate) this governor orchestrates | pack |
| `core/35-security-auth.md` (ACTIVE) | broker per-caller token auth; secret (ob@ cred) stays host-side; no secret in code | pack |
| `core/45-testing-strategy.md` (ACTIVE) | one test per behavior, risk-ordered, TDD the risky | pack |
| Headroom source | `claude_rotate.py --status --json` → per-account `{five_hour:{utilization,resets_at_epoch}, seven_day:{…}}` (+ Opus if present) | `scripts/sysadmin/claude_rotate.py::_status_payload` :1205, `_account_status` :1139, utilization parse :1181-1186 |
| Reactive limit signal | `is_usage_limit(text)` — regex over weekly/session/5h/"out of extra usage" | `claude_rotate.py:92` |
| Host claude entrypoint | `claude-run.sh` runs claude via `claude_rotate` as the operator, one cred home | `scripts/sysadmin/claude-run.sh:6-18` |
| The pool (routine offload + sandboxed diagnosis) | `libs/subagents` — `sandbox=True` FAIL-closed default (`--unshare-net`, read-only host) confirms the pool can't touch the host → diagnosis-only, marshalled bundle | `libs/subagents/agent.py:159` (tools_enabled), `:169` (sandbox), `sandbox.py` |
| redis-main client pattern | existing sysadmin redis usage to copy for the budget counter | `scripts/sysadmin/detect_reversals.py`, `liveness_audit.py` |
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
- `scripts/sysadmin/quota_governor.py`: `class QuotaGovernor` with `route(kind: Literal["incident","routine"], *, caller: str|None=None) -> Literal["ob@","pool","pool-diagnose"]`. Reads ob@'s per-window utilization; **routine** → `pool` if `max(five_hour, seven_day, opus_weekly) ≥ RESERVE_PCT` (default 80, env `QUOTA_RESERVE_PCT`) else `ob@`; **incident** → `ob@` if not capped, else `pool-diagnose`. Reactive: a returned `is_usage_limit` marks ob@ capped until its reset (from `resets_at_epoch`). **Fail-safe:** a `--status` failure → routine returns `pool`, incident returns `ob@`. **Single-flight:** an `ob@` incident acquires a lock (`fcntl.flock` on a state file); a second incident waits/queues.
- Alerts: on a reserve-threshold or cap crossing, call `claude-sound.sh mesh-notify`.

**Steps:**
1. **[TDD — highest risk] Write `tests/test_quota_governor.py` FIRST** (pool fanout): (a) routine sheds to pool when 5h util ≥80 even though weekly is low (the F1 multi-window proof); (b) routine runs on ob@ below the reserve; (c) incident always returns ob@ when not capped; (d) incident returns pool-diagnose when ob@ is capped; (e) `--status` failure → routine=pool, incident=ob@ (fail-safe); (f) a reactive `is_usage_limit` marks capped until reset; (g) single-flight: a second concurrent incident does not get a parallel ob@ slot. Mock `claude_rotate --status` output + `is_usage_limit`. Run → RED.
2. Implement `quota_governor.py`. Run → GREEN.
3. **Gate:** `python -m pytest tests/test_quota_governor.py -q`; ruff; mypy.
4. `python scripts/enforcement/check_doc_sync.py`.
5. **`/fabrik-review`** (native Opus — the fail-safe + single-flight + multi-window logic) → adjudicated exit.
6. Commit (explicit paths + provenance trailers).

**Behavior Contract:**
- **Given** ob@ 5h-utilization ≥ the reserve but weekly low, **When** a routine job routes, **Then** it goes to `pool` (multi-window reserve) (scripts/sysadmin/quota_governor.py).
- **Given** ob@ is capped, **When** an incident routes, **Then** it returns `pool-diagnose`, never blocked (scripts/sysadmin/quota_governor.py).
- **Given** the `--status` probe fails, **When** anything routes, **Then** routine→pool + incident→ob@ (fail-safe) (scripts/sysadmin/quota_governor.py).
- **Given** an ob@ incident holds the single-flight lock, **When** a second incident arrives, **Then** it does not get a concurrent ob@ slot (scripts/sysadmin/quota_governor.py).

## Phase B — the completion-only container broker (`scripts/sysadmin/claude_broker.py`)

**One responsibility:** give containers subscription-billed LLM completion on ob@ with NO host tools + NO creds.

**Interfaces — Consumes:** `QuotaGovernor` (A), `claude-run.sh` (host claude), `redis-main` (budget).
**Produces:**
- `scripts/sysadmin/claude_broker.py`: a stdlib loopback/bridge-gateway service; `POST {prompt, model?}` →
  runs `claude -p --allowedTools ""` (empty allowlist — no bash/edit/MCP) via the host entrypoint, returns the
  completion. Controls: **(a)** per-caller shared-token auth (a `401` without a valid token); **(b)** per-caller
  budget — a `redis-main` counter keyed `(caller, window)`, decremented per job, reset on the 5h + weekly
  boundaries; over-budget → `429` (or downgrade to pool); **(c)** an audit line per job (caller, prompt hash,
  tokens) to stdout; **(d)** class forced to `routine` from the caller identity (never self-labelled); the
  broker calls `QuotaGovernor.route("routine", caller=…)` — so a container job sheds to the pool under the
  reserve exactly like any routine work.

**Steps:**
1. **[TDD] Write `tests/test_claude_broker.py` FIRST** (pool fanout): (a) a job with a valid token returns a completion; no/invalid token → 401; (b) the claude invocation carries `--allowedTools ""` (no host tools) — assert the argv; (c) an over-budget caller → 429 (mock the redis counter); (d) the budget counter resets on a window boundary; (e) the broker forces `routine` + calls the governor (a job under the reserve routes to pool, not ob@). Mock `claude-run.sh` + redis. Run → RED.
2. Implement `claude_broker.py` (copy the redis client pattern from `detect_reversals.py`). Run → GREEN.
3. **Gate + doc_sync.**
4. **`/fabrik-review`** (native Opus — the auth + empty-tool-allowlist + budget are the confused-deputy defenses) → adjudicated exit.
5. Commit.

**Behavior Contract:**
- **Given** a broker job, **When** it runs claude, **Then** the argv includes `--allowedTools ""` (no host tools ever) (scripts/sysadmin/claude_broker.py).
- **Given** a request without a valid per-caller token, **When** it hits the broker, **Then** it is refused 401 (scripts/sysadmin/claude_broker.py).
- **Given** a caller over its window budget, **When** it submits, **Then** it is refused 429 / downgraded (scripts/sysadmin/claude_broker.py).

## Phase C — context marshaller + wire consumers + retire the ping + dashboard + docs

**One responsibility:** make the pool-diagnosis path real, route the fleet's consumers through the governor,
and document it.

**Interfaces — Consumes:** `QuotaGovernor` (A), the pool (`libs/subagents`), the consumer scripts.
**Produces:**
- `scripts/sysadmin/incident_context.py`: a HOST-side marshaller — given an incident (the GlitchTip webhook
  payload), assemble a context bundle (payload + relevant `docker logs`/`journalctl` tails + a `docker ps`/state
  snapshot) into a file the pool worker reads; the `pool-diagnose` path dispatches a `libs/subagents` read-only
  worker over that bundle + `mesh-notify`s the operator with the proposal.
- **Wire the consumers** through `QuotaGovernor` (route every ob@ call): `bot.py`, `weekly_catchup.sh`, the
  kaizen crons, `morning-report.sh`/`daily-digest.sh`/`weekly-security.sh`, `proactive-check.sh`,
  `canary_grounding.py`, `ci_health_probe.py`, the daily-VPS-docs pipeline. **Per-consumer verdict** (F6):
  each row is tagged pure-reasoning→pool or needs-host-tools→ob@-low-priority; wire accordingly.
- **Retire the keepalive ping:** drop `claude -p ping` from `claude-keepalive-rotate.sh` under single-key (a
  regularly-used ob@ needs no warmth ping; it burns the quota being conserved).
- **The dashboard panel:** extend `quota_dashboard.py` with an ob@-VPS panel showing the governor's current
  routing mode + per-window headroom.
- **Docs:** `docs/workstation/vps-claude-quota-governance.md` (the box-local runbook) + INDEX row; CHANGELOG;
  the Doc Sync Matrix rows.

**Steps:**
1. **[TDD] Write `tests/test_incident_context.py` FIRST**: the marshaller assembles the bundle (payload + a log-tail stub + a state stub) into the expected file; the pool-diagnose path is dispatched read-only (assert no host-write tool). Run → RED.
2. Implement `incident_context.py` + the pool-diagnose dispatch. GREEN.
3. Wire the consumers (per-verdict) + retire the ping + the dashboard panel.
4. **Gate (whole-plan):** `python scripts/final_gate.py --check --json` → success + `check_convergence.py`.
5. **Doc Sync Matrix:** `docs/workstation/…` + INDEX + CHANGELOG + `docs/RESILIENCE.md` §7 (the governor is a scheduled/pause-aware layer) if applicable.
6. **`/fabrik-review`** (native Opus — the marshaller + the consumer wiring) → adjudicated exit; then **`/fabrik-docs-review`** on the new runbook.
7. Commit + push.

**Behavior Contract:**
- **Given** an incident when ob@ is capped, **When** the diagnosis path runs, **Then** the host marshaller has assembled the bundle BEFORE the pool worker (which runs read-only) is dispatched (scripts/sysadmin/incident_context.py).
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
- (the consumer scripts wired in Phase C — `bot.py`, `kaizen_*.py`, `*.sh`, `canary_grounding.py`, `ci_health_probe.py` — each a minimal route-through-the-governor edit)

(Governance shared-append surfaces CHANGELOG.md / INDEX.md / docs/README.md are updated per the Doc Sync
Matrix, orchestrator-applied, outside the plan lock.)

## Behavior Contract (whole-plan, one row per user-observable behavior)

- **Given** a routine job and ob@ near ANY cap window, **When** it routes, **Then** it goes to the pool (ob@ quota conserved).
- **Given** an incident, **When** it fires, **Then** it is handled on ob@ (headroom) or escalated with a pool diagnosis (capped) — never dropped, never blocked.
- **Given** a container, **When** it uses claude, **Then** it gets completion-only (no host tools, no creds) via the broker.
- **Given** the governor/probe is down, **When** anything routes, **Then** it fails SAFE (routine→pool).

## Evidence

```
$ grep -n "_status_payload\|_account_status" scripts/sysadmin/claude_rotate.py   # headroom source
1139:def _account_status(store: Path) -> dict:
1205:def _status_payload() -> dict:
$ grep -n "def is_usage_limit" scripts/sysadmin/claude_rotate.py                 # reactive signal
92:def is_usage_limit(text: str) -> bool:
$ grep -n "sandbox: bool = True" libs/subagents/agent.py                         # pool is sandboxed → diagnosis-only
169:    sandbox: bool = True
$ grep -c "mesh-notify)" ~/.claude/bin/claude-sound.sh                          # alert transport
1
```

## Self-audit

- **Grounding:** every reuse point resolves to a real `path:line` (Context Ledger + Evidence); the two external
  facts (Claude Max 3-window caps; docker #22066) are the spec's, cited there.
- **Constraint adherence:** no `ANTHROPIC_API_KEY` (pool = OpenRouter, host = claude OAuth); no per-call cap
  (governor sheds routine only); containers get completion-only; fail-safe; single-flight; multi-window reserve
  — all traced to the CONVERGED spec's post-review design (12 findings fixed across two passes).
- **No deferred questions:** the reserve threshold (default 80, env-tunable), the broker transport (loopback
  HTTP default), and the token issuance (per-service env at `fabrik apply`) are decided defaults, not `[OPEN]`
  residuals — the executor applies them without stopping.

## Residual unknowns

**Resolved (from the spec's two review passes):** the full design (multi-window reserve, host marshaller,
single-flight, fail-safe, redis budget, per-consumer poolable verdict) — see the spec's `## Open unknowns`.

**Still-open (plan-time tuning, non-blocking):** the exact reserve % (default 80, tune from the live board);
broker transport (loopback HTTP default vs unix socket); per-consumer pure-reasoning-vs-host-tools verdicts —
finalized per-row at Phase C against each consumer's actual LLM step.
