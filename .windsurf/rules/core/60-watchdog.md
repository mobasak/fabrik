---
activation: glob
globs: ["**/watchdog*", "**/specs/services/*.yaml", "**/fabrik-lib/watchdog/**", "**/state.db", "**/emitter_inbox*", "**/WatchdogConfig*", "**/cost_ledger*"]
description: Watchdog sidecar contract — when to enable, how Tier A/B/C/D act, OAuth inheritance, fail-safe emitter, cost ceilings
trigger: glob
---
<!-- CONSUMER: Coding agents (all) + Traycer (tech-plan step)
     GOAL: Per-project AI sysadmin sidecar — autonomous diagnosis + Tier A bleed-stop, Tier B opt-in, Tier C escalate, Tier D code-remediation (opt-in, human-gated), cost-capped, OAuth-inherited Claude Code subprocess
     TRAYCER USAGE: When a spec opts into watchdog or shape.kind implies it, inject "wire the emitter at meaningful business events; declare WatchdogConfig if non-default" into ticket ACs. Reference this pack + 58-resilience + 55-observability.
     AGENT USAGE: Vendor watchdog/emitter/ into projects that need watchdog catch. Never call the sidecar from main app — emit incidents to the inbox instead. Don't put secrets in details. -->

# Watchdog Contract

**Activation:** Glob — watchdog spec field, sidecar source, emitter library, related state.db / emitter_inbox / cost_ledger files.
**Purpose:** Per-project AI sysadmin sidecar that diagnoses anomalies via Claude Code (subprocess) and dispatches scoped remediations. Four tiers: A auto, B opt-in, C escalate, D code-remediation (opt-in, human-gated). Bounded by `WatchdogConfig` budget caps and a deadman timer.

---

## When to enable

| Shape | Default | Override |
|---|---|---|
| `python-api`, `node-api` | **on** when `shape.is_admin_dashboard` OR `shape.has_persistent_data` is true | `watchdog: { enabled: false }` in spec |
| `worker` | **on** | `watchdog: { enabled: false }` |
| `static-site`, `docusaurus` | **off** | `watchdog: { enabled: true }` if you want diagnosis of build/deploy issues |
| any | — | `watchdog: { enabled: true, daily_budget_usd: 5.0, auto_tier_b: true }` for full override |

Defaults preserve current behavior — existing specs without a `watchdog:` block inherit the shape-driven default and don't break.

**Make it project-specific** — set `watchdog.project_system_prompt_file: docs/WATCHDOG_PROMPT.md` (project-relative Markdown, ≤32 KB). The driver injects its contents as `WATCHDOG_SYSTEM_PROMPT`; the sidecar appends it as a `## This project` section *after* the canonical veteran-sysadmin prompt (rails never replaced). Use it to teach the watchdog THIS app's architecture, failure modes, what "healthy" means, and hands-off zones. **Fail-soft:** a missing / unreadable / oversized / absolute / `..`-escaping path is ignored (logged warning) and the sidecar runs the canonical prompt only — a prompt-file problem never disables the watchdog or blocks the deploy, and a bad path is never read. Commit the prompt file to the repo before `fabrik apply` (the driver reads it hub-side at render).

---

## Architecture summary

- **One sidecar per spec.** Image: `fabrik/watchdog:<project_id>`. Built by the watchdog driver (`src/fabrik/drivers/watchdog.py` — T-P2 artifact 13, not yet shipped at the time of this pack) at `fabrik apply` time with placeholders rendered.
- **Mounts (all per-project, set by driver):**
  - `~/.claude/` (RO from host) → `/home/watchdog/.claude/` — Claude Code OAuth credentials. Sidecar does NOT carry an API key.
  - `/var/lib/watchdog/` (RW, named volume) — `state.db` + `cost_wal.db` + `proposed/<project_id>/` PR workspace + `keys/git-deploy.key` (RO, 600).
  - `/var/run/docker.sock` — scoped read access via PreToolUse hook + claude-settings allow/deny; only `docker logs|inspect|stats|restart <main_container>` and `docker exec <main> ps|df|cat /proc/*` are allowed.
  - `/opt/<project_id>/` (RO) — the project tree for `Read`/`Grep`/`Glob`. This is the `/project` mount the fix lane reads conventions from (`.windsurf/rules/*` + `CLAUDE.md` are gitignored, so a bare clone would lose them); code changes materialize into a writable scratch worktree, never the RO mount.
- **Database access (auto-provisioned, per-project).** When a spec has `shape.needs_database` **and** the watchdog is applicable (`spec.watchdog.enabled`, default true), the postgres registrar mints two dedicated roles on the app DB alongside the app's owner role and injects their DSNs into the project `.env` (read by the sidecar via `env_file`):
  - `WATCHDOG_DB_URL_RO` → `{db}_wd_ro`, **SELECT-only** (`LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE`, `CONNECT`+`USAGE`+`SELECT`, incl. future tables via `ALTER DEFAULT PRIVILEGES FOR ROLE <owner>`). The sidecar's default DSN — the diagnosis lane across all tiers.
  - `WATCHDOG_DB_URL_RW` → `{db}_wd_rw`, **DML-only** (SELECT/INSERT/UPDATE/DELETE + sequence usage; **no DDL, no DROP, not owner**). Consumed only by the Tier-C approved-write lane.
  - Per-project by design: each sidecar's DSN reaches ONLY its own DB (a compromised RO cred can't read another tenant). Password lifecycle mirrors `DATABASE_URL`: a fresh password is minted + injected only when a role is newly created; an existing role is preserved (no rotation), so its `.env` DSN stays valid and a cached-image re-apply never breaks a running sidecar. The batch runs under `\set ON_ERROR_STOP on` (failures raise, never false-succeed); grants are re-applied every apply (idempotent — covers newly-added tables); `ALTER DEFAULT PRIVILEGES` targets the real DB owner (looked up from `pg_database.datdba`, omitted when unresolvable), so it works on postgres-owned legacy DBs. Roles are non-owner / non-superuser (least privilege) — on `FORCE ROW LEVEL SECURITY` tables the RO lane sees only policy-permitted rows; a multi-tenant app needing cross-tenant diagnosis adds a policy for `{db}_wd_ro` upstream. Teardown: `drop_database` also drops the two roles (`DROP ROLE IF EXISTS`, on both the DB-present and already-gone paths) so a drop+recreate never orphans them; a provisioning failure surfaces as a `watchdog-db-roles` entry in the deploy resource summary (not just a log warning). (Distinct from the shared, manual `scripts/provision_watchdog_ro.py` escape hatch, which this supersedes for the auto path.)
- **State machine** (agent.py):
  1. Snapshot main container (logs + inspect + restart count).
  2. Rule-pass for OOM/panic/traceback/5xx-spike.
  3. Drain `emitter_inbox` (events from main app via vendored emitter).
  4. Per incident: cost-cap check → LLM diagnose (Claude Code primary, OpenRouter fallback) → action dispatch → **if code-class and Tier-D enabled: generate+test fix → Telegram-gate → apply via deploy adapter → verify/rollback → record**; else record → escalate if Tier C.
  5. Deadman: any unacked Tier C past `deadman_timeout_seconds` (default 300) → `docker restart <main>` + Apprise re-alert with `[DEADMAN-TIMEOUT]` prefix.

---

## Action allow-list (Tier A / B / C / D)

**Tier A** — automatic, no opt-in needed. Bounded by `per_incident_budget_usd` (default 0.25) and `daily_invocations_cap`.

| Action | What | Guards |
|---|---|---|
| `restart_container` | `docker restart <main>` | Refuses 14-entry shared-infra list (postgres-main, redis-main, traefik, authelia, …) |
| `clear_file_cache` | `rm -rf /project/<subpath>/*` | Path-escape rejected; scoped under `/project/` |
| `scale_concurrency` | env edit + `compose up -d <main>` | CONST_CASE env-key validation |
| `pause_worker` | Redis SETEX `<project_prefix>:pause:<resource>` | Matches `pause-state` vendor read contract; TTL ∈ [5, 3600]s |
| `drop_queue_items` | `DELETE … ORDER BY <age_col> LIMIT N` | Identifier validation; row cap 10000 |
| `rotate_locks` | `UPDATE … SET locked_at = NULL WHERE locked_at < now() − interval` | Identifier validation; age ∈ [30, 86400]s |

**Tier B** — opt-in per spec via `watchdog.auto_tier_b: true`. Without opt-in, Tier B diagnosis escalates as Tier C.

| Action | What | Guards |
|---|---|---|
| `wipe_redis_cache` | `SCAN` + `DEL` pattern | Project-prefixed forcibly; 100k key safety cap |
| `reset_db_pool` | POST `/admin/reset-db-pool` with `X-Internal-Token` | Requires `SERVICE_INTERNAL_SECRET_KEY` env |
| `install_log_drop_rule` | Add regex drop to promtail via hub update service | Refuses too-broad patterns (`.*`, `.+`, `^.*$`) |

**Tier C** — escalate-only by default. With `propose_fix_prs: true`, also pushes branch `watchdog/<incident_id>`.

| Action | What | Guards |
|---|---|---|
| `escalate_apprise` | POST to Apprise → Telegram | always allowed |
| `create_fix_pr` | `git push -u origin watchdog/<incident_id>` | Requires `WATCHDOG_PROJECT_GIT_REMOTE` + deploy key; refuses pushes to main/master/develop/staging/production/release/*; refuses force-push, branch deletion, `git config`, `git rebase`, `git reset --hard`, `git tag` |

**Tier D** — code-remediation, **off by default**, opt-in like B/C and **human-gated**. This is the only tier that can change running code, and it never does so silently.

**Enable:** `watchdog: { auto_code_fix: true }` in the spec **plus** an injected `deploy_adapter` + `test_cmd` (the `code_fix_window_sec` silence window defaults to 1800s / 30 min — see below). Absent → Tier D is unavailable and code-class incidents behave exactly as today (Tier C escalate / `propose_fix_prs`).

| Action | What | Guards |
|---|---|---|
| `apply_code_fix` | generate a fix on `watchdog/<incident_id>` → tests pass (**HARD gate**) → secret-scan the diff → Telegram the diff with **Approve / Reject / STOP** → on approval **OR** silence past `code_fix_window_sec` → `deploy_adapter.apply(branch)` → VERIFY health → **auto-rollback on regression** | Isolated clone only (never the RO `/project` mount); deploy mechanism **injected** (no in-place src edit); every apply/rollback written to the `deploys` audit table; same forbidden push targets as `create_fix_pr` (no main/master, no force-push) |

---

## Owner approval flow for Tier B opt-in

1. Spec author edits `specs/services/<id>.yaml`: `watchdog: { auto_tier_b: true }`.
2. `fabrik apply` registrar picks up the change, renders compose with `WATCHDOG_AUTO_TIER_B=true`.
3. On first Tier B execution, the sidecar fires an Apprise message: `[Watchdog Tier B activated for <project_id>] action=<name>, reasoning=<…>`.
4. The operator can revert by setting `auto_tier_b: false` and re-applying — the next sidecar boot reads the new env and Tier B falls back to `skipped` (escalate-only).

Same flow for `propose_fix_prs: true` — first PR fires `[Watchdog proposed PR] watchdog/<incident_id> at <repo>`.

### Tier-D code-remediation gate (the human-in-the-loop terminal)

When `apply_code_fix` produces a **green, secret-scanned** diff, the sidecar fires a Telegram message carrying the diff + **Approve / Reject / STOP**:

- **Approve** → `deploy_adapter.apply(branch)` immediately.
- **Reject** → discard the branch; fall back to Tier C escalate.
- **STOP** → kill-switch: disable Tier-D for this project until re-enabled in the spec.
- **No response within `code_fix_window_sec`** (default **1800s / 30 min**) → treated as approval and applied. Since silence auto-applies a tested-green fix, the window is sized for a realistic human review (5 min was too short to reliably `Reject` a wrong-but-passing fix); it IS the operator-bound terminal (see [self-healing](self-healing.md) acceptance checklist), not a fully-autonomous layer.

Every apply/rollback is written to the `deploys` table (and the approval to `approvals`); post-apply health VERIFY failing triggers automatic rollback. Tier-D requires the `auto_code_fix` opt-in **plus** an injected `deploy_adapter` + `test_cmd`; absent any of these, code-class incidents stay Tier C.

---

## Integration with adjacent vendor modules

- **`pause-state`** — worker code reads pause flags via the vendored `pause-state` module. Watchdog writes flags directly via `redis.setex(<project_prefix>:pause:<resource>, ttl, "watchdog")` matching the read contract. Workers see the pause without code change.
- **`async-http-client`** — sidecar's OpenRouter fallback uses `httpx` directly (not async); circuit-breaker for OpenRouter is implicit in `llm_client.diagnose`'s primary→fallback→rule-only chain rather than a per-call breaker.
- **`abuse-prevention`** — host-app side only. Sidecar does not call it. If the host app fires `abuse_event` → emitter → sidecar reads → LLM proposes Tier A `pause_worker` for the offending resource.
- **`cost-budget`** — vendored into the sidecar tree (`/opt/fabrik-lib/watchdog/watchdog_sidecar/cost_budget.py`); writes go through `record_cost`/`replay_wal` so the shared `cost_ledger` table on postgres-main carries every project's burn. Daily caps via `check_caps` + `drop_to_rule_only_mode`.

---

## Cost behavior

- **Claude Code returns `total_cost_usd` directly** in its `--output-format json` envelope; the sidecar records that value. Subscription-mode burn shows up as `cost_usd=0.0` but token counts still flow into `daily_invocations_cap`.
- **OpenRouter** carries real per-token dollar cost; recorded verbatim via `usage.include=true` in the response envelope.
- **`per_incident_budget_usd`** ceiling enforced by Claude Code's `--max-budget-usd` flag (primary path) and by the OpenRouter fallback timing out at `_OPENROUTER_TIMEOUT` (45s).
- **`daily_budget_usd`** + **`daily_invocations_cap`** enforced by `cost_budget.check_caps`; over-cap routes the incident to rule-only escalation (no LLM call) and tags the Apprise alert with `(BUDGET-CAP)`.

---

## Anti-patterns

- **Calling the sidecar from main app.** Use the emitter (vendor `watchdog/emitter/`). The sidecar is a one-way reader; HTTP back-channel breaks fail-safe.
- **Bypassing the PreToolUse hook.** Hook + claude-settings allow-list + sandbox.filesystem + docker.sock scoping are 4-layer defense-in-depth. If you "just need" to let Claude run an arbitrary `bash` command, the right move is to add the command to claude-settings.json — never `chmod -x` the hook.
- **Putting secret tokens in `details`.** The LLM sees every value. Even with WebFetch/WebSearch gated to allowedDomains, log exfil via reasoning text is the worst-case prompt injection. Pass IDs, not values.
- **Running sidecar as root.** Claude Code refuses bypass mode under root/sudo on Linux. The Dockerfile creates UID 1000 `watchdog`; honor it.
- **Editing `/opt/<id>/src` in-place from the sidecar.** In-place src editing from the sidecar is still **banned** — code changes go through the isolated workspace + injected deploy adapter. **Without Tier-D opt-in, watchdog never merges** (operator merges, via the PR workspace at `/var/lib/watchdog/proposed/<project_id>/` pushed to `watchdog/<incident_id>`). **With Tier-D**, watchdog MAY apply a tested, secret-scanned fix via the deploy adapter after explicit Telegram approval or a configured silence window, with auto-rollback armed and a STOP kill-switch.
- **Letting `emit_incident()` raise.** It catches everything by design. If you "fix" it to raise, you've coupled the main app's billing/checkout path to telemetry — exactly the brittleness this contract avoids.
- **Reusing `<project_prefix>` across projects.** It namespaces redis keys + emitter events; collision = one project sees another's pause flag.

---

## Worked example — OOM diagnosis

1. Main container hits OOM-kill (kernel `oom-killer` log line).
2. Sidecar's next 60s tick:
   - `gather_snapshot` captures `docker logs --since 120s <main>` containing the `oom-killer` line.
   - `detect_anomalies` regex hits `_LOG_TRIGGERS["oom_kill"]` → incident with `severity=urgent`.
   - `state.record_incident(...)` → uuid7 row in `incidents`.
   - `cost_budget.check_caps` returns under-cap.
   - `llm_client.diagnose` invokes `claude -p` with the incident + snapshot. Claude returns `{tier: "A", action: "restart_container", reasoning: "OOM with no obvious leak — restart restores baseline RSS", confidence: 0.9}`.
   - `actions.execute("A", "restart_container", {}, ctx)` → `_restart_main` → `docker restart <main>` → `ActionResult(status="success")`.
   - `state.record_action(...)` + `state.resolve_incident(id, "auto")`.
   - No Apprise alert (Tier A success).
3. Cost ledger row: `provider=claude-code`, `cost_usd=<from envelope>`, `in_tokens=<…>`, `out_tokens=<…>`.
4. If the same OOM repeats inside the cost window, `check_caps` may flip the project to rule-only mode; the next OOM escalates as Tier C with `(BUDGET-CAP)` — operator sees Telegram alert without an LLM call. Deadman armed; if operator doesn't ack within 300s, `docker restart <main>` fires as bleed-stop and an Apprise re-alert lands.

---

## Cross-references

- Spec field: [`src/fabrik/spec_loader.py`](../../../src/fabrik/spec_loader.py) `WatchdogConfig` class.
- Sidecar source: `/opt/fabrik-lib/watchdog/watchdog_sidecar/` (vendored into image by driver at apply time).
- Emitter: `/opt/fabrik-lib/watchdog/emitter/`.
- Cost ledger schema: shared `cost_ledger` on `postgres-main`, provisioned once by Fabrik postgres registrar.
- Adjacent packs: [55-observability](55-observability.md) (preventive visibility), [58-resilience](58-resilience.md) (preventive circuit-breakers), [cost-budget](cost-budget.md) (vendored module reference), [app-audit-log](app-audit-log.md) (cross-tenant audit trail).
