# Plan: PR3 — `fabrik vultr provision` auto-installs the spoke's AI sysadmin

**Created:** 2026-06-13
**Status:** ✅ **SHIPPED 2026-06-13** (commit [`0dc92e3`](https://github.com/mobasak/fabrik/commit/0dc92e3)) — live-validated 2026-06-14 via `fabrik vultr drill spoke --g0-smoke`: bootstrap_rc=0, verify_rc=0, 0 orphans, 528s wall-clock, ~$0.015 cost. **G0 copied-creds branch closed by decision** (not pursued) — `immediate_auth_ok=True` proved the copy works for first use, but the 4-day refresh-token rotation race can only be observed multi-day AND that observation risks rotating the live vps1 sysadmin's token. Risk ≫ reward with the fleet settled at 3; keep the proven per-spoke `ssh <spoke> 'claude'` device-flow.
**Owner:** Claude Code (this agent). Review: the peer AI ran the 5-axis verification — all green before merge.
**Trigger:** Post-bootstrap a new spoke needed 5 manual operator steps before its AI sysadmin was live ([bootstrap-vps.sh:1186-1192](../../../scripts/bootstrap/bootstrap-vps.sh#L1186-L1192)). PR3 collapsed that to **1** (the `ssh <spoke> 'claude'` device-flow).

**Plan archived 2026-06-14 after live validation.** All concrete deliverables shipped + drilled. Any future enhancement (copied-creds zero-touch, satellite refactor) tracked in [`docs/STRATEGIC_BACKLOG.md`](../../../STRATEGIC_BACKLOG.md), not here.

---

## Goal

`fabrik vultr provision vpsN` brings up a new spoke whose AI sysadmin is running, reachable, and answering Telegram — with the operator's only remaining action being a single `ssh <spoke> 'claude'` device-flow (the proven-safe independent-grant path).

This is a **capability**, independent of fleet size. The fleet is settled at 3 (vps1+vps2+vps3); no 4th permanent spoke is planned now. PR3 exists so that *if/when* a spoke is added (or a drill provisions one), the sysadmin comes up unattended save for the one OAuth step.

### The 5 manual steps today → what PR3 does to each
| # | Manual step today | PR3 |
|---|---|---|
| 1 | Fill `TELEGRAM_BOT_TOKEN` + `TELEGRAM_OWNER_ID` in `.env.sysadmin` | **Automated** — claim a pre-staged per-host token from the DR-store pool; owner ID + OpenRouter key are fleet-uniform (templated) |
| 2 | `ssh <spoke> 'claude'` device-flow | **Stays manual** — the one proven-safe step (copied-creds zero-touch is deferred, see C2) |
| 3 | `systemctl enable --now` both units | **Automated** — provision enables them (bot needs only the Telegram token at startup; no crash-loop) |
| 4 | Send a test Telegram message | **Automated** — provision fires a startup-hello round-trip as the verify signal |
| 5 | `curl http://10.99.0.N:8201/health` | **Automated** — verify gate, with an explicit timeout + fail path |

---

## Design Constraints (binding — not footnotes)

**C1 — Never `ANTHROPIC_API_KEY` in the provision / operational path.** The operational AI surface (sysadmin bot, watchdog, every `scripts/sysadmin/*` `claude -p`, the bootstrap `@anthropic-ai/claude-code` install) runs on **Claude Code subscription OAuth** (`~/.claude/.credentials.json`). `ANTHROPIC_API_KEY` exists only for `fabrik ai generate/revise/usage` content utilities ([.env.example:111](../../../.env.example#L111), `src/fabrik/ai/client.py`) and is **out of bounds** here. If an OAuth limit forces a fallback, the legitimate rungs are (a) one-time device-flow per spoke, (b) the satellite/single-hub-bot refactor — **never** a per-spoke API key. (Cost model: subscription IS the budget.)

**C2 — G0 is two questions; PR3 ships on the proven half.**
- *Independent grant per host* (each spoke does its own `claude` device-flow → its own `credentials.json`): **PROVEN** — running live on vps1/2/3 right now. PR3 rides this.
- *Copied creds* (provision copies one `credentials.json` to skip device-flow): **unproven**, blocked on the OAuth **refresh-token rotation race** (rotating refresh tokens go stale across hosts on the ~4-day cycle, per Lesson 75). This is a **separate gated enhancement**, not a PR3 dependency. PR3 does **not** copy creds into the permanent provision path.

**C3 — Fallback ladder (every rung floored by C1):**
| G0 outcome | Fallback |
|---|---|
| Copied-creds proven safe later | Zero-touch — drop step 2. |
| Single concurrent session rejected | Keep the 1-step device-flow. |
| Shared rate-limit | 1-step device-flow + backoff/queue around `claude -p`. |
| Device fingerprint / IP-binding | Satellite refactor (needs Phase 5 `propose`/`ack`). |
| **Any** failure | **Never** `ANTHROPIC_API_KEY` per spoke. |

**C4 — Token-pool hygiene.** Per-host bot tokens are pre-staged once (operator @BotFather batch) in the DR store. `claim_bot_token(name)` MUST: refuse to double-assign a token already bound to another host; be atomic under a lock; record `assigned_to`/`assigned_at`; and **log + refuse-to-enable-the-bot on depletion** (an empty pool must NOT write the placeholder and enable — that crash-loops `bot.py` into `StartLimitBurst`). Reverse-teardown returns the token to the pool.

---

## Grounded surfaces (verified 2026-06-13)

- **`.env.sysadmin`** ([env.sysadmin.template](../../../scripts/bootstrap/templates/env.sysadmin.template)): `TELEGRAM_BOT_TOKEN` (per-host, placeholder `__OPERATOR_TO_FILL__`), `TELEGRAM_OWNER_ID` (fleet-uniform), `WATCHDOG_OPENROUTER_KEY` (fleet-uniform), `SYSADMIN_HOST_NAME/ROLE/IP/PEER_HOSTS`, `SYSADMIN_HEALTH_HOST/PORT` (default `127.0.0.1:8017`), `SYSADMIN_MODEL=opus`. Mode 600, mirrored to DR-store `env/sysadmin/<host>` by the W9 watcher.
- **Two health surfaces:** sysadmin bot = `8017` (loopback by default, not hub-probeable); **aro-wake = `8201`** (mesh-facing) — the verify gate targets `8201`.
- **`bot.py` startup deps:** only `TELEGRAM_BOT_TOKEN` + `TELEGRAM_OWNER_ID` (`os.environ[...]`). No `~/.claude` check at startup → enabling the unit with a real token is safe; claude path unlocks at device-flow. ([bot.py:41-42](../../../scripts/sysadmin/bot.py#L41-L42))
- **Bot unit:** `Restart=always, RestartSec=30, StartLimitIntervalSec=300, StartLimitBurst=5` → a bad/placeholder token crash-loops to `failed` in ~150s. Real token required before enable.
- **Peer registration is a static map**, not a config/wg0 edit: [watchdog.py:288-304](../../../src/fabrik/drivers/watchdog.py#L288-L304) hardcodes peers per host with an `"unknown"` fallback, rendered into the system prompt at bootstrap (step_14). A new vpsN renders `unknown` peers unless the map is made deterministic.
- **DR store:** `/opt/fabrik-dr-store/` (git, W9-mirrored); `env/` holds env snapshots. Token pool home: `env/sysadmin-bot-tokens.json`.
- **provision()** already runs full `bootstrap-vps.sh` + registers prometheus/gatus aro-wake targets ([vultr_provision.py:191,344](../../../src/fabrik/orchestrator/vultr_provision.py#L191)). PR3 adds one post-bootstrap stage and a reverse step.

---

## Implementation

### 1. Token pool (DR store)
`/opt/fabrik-dr-store/env/sysadmin-bot-tokens.json`:
```json
{
  "pool": [
    {"token": "<botfather-token>", "label": "SysAdminVPS4", "assigned_to": null, "assigned_at": null}
  ]
}
```
New module `src/fabrik/orchestrator/sysadmin_tokens.py` (or a section in vultr_provision):
- `claim_bot_token(name) -> str | None` — atomic (locks_local.file_lock), returns first `assigned_to is null` token, stamps `assigned_to=name`, writes back. Returns `None` (logged) if pool empty or `name` already holds one (idempotent reclaim returns the same token).
- `release_bot_token(name)` — clears the assignment for `name` (reverse-teardown).
- Pool file absent ⇒ treat as empty (log a clear "stage tokens at <path>" message).

### 2. `_provision_sysadmin(name, ip)` — new post-bootstrap stage in `vultr_provision.py`
Ordered, best-effort with explicit per-step status in `report["sysadmin"]`:
1. `tok = claim_bot_token(name)`. If `None` → **skip enabling the bot**, record `sysadmin.bot="skipped: token pool empty"`, still do aro-wake + peer map. (No crash-loop.)
2. Write `/opt/fabrik/.env.sysadmin` on the spoke from the rendered template with real `TELEGRAM_BOT_TOKEN=tok`, fleet-uniform `TELEGRAM_OWNER_ID` + `WATCHDOG_OPENROUTER_KEY` (sourced from the hub's `.env.sysadmin`), mode 600 owner `ozgur:ozgur`. (scp-to-/tmp-then-`install`, Rule 2.)
3. `systemctl enable --now aro-wake.service` (no Claude dep). If `tok` claimed: `systemctl enable --now vps-sysadmin-bot.service`.
4. **Verify gate** (each with `--max-time`/timeout + clear fail path; failure ⇒ `success:false` for the stage, never a hang): from hub, `curl --max-time 10 http://10.99.0.N:8201/health` == 200; then a startup-hello that round-trips spoke→hub→Telegram (bounded wait, annotate on timeout).
5. Print the single remaining operator action: `ssh <name> 'claude'`.

### 3. Deterministic peer map ([watchdog.py](../../../src/fabrik/drivers/watchdog.py))
Replace the hardcoded per-host dict with a fleet-derived computation: peers = every `vpsK (10.99.0.K)` for K in the known fleet set except self; a new vpsN derives correct peers instead of `"unknown"`. Note in the doc: **live trio prompts are baked at bootstrap and do NOT auto-update** — adding a host to the live fleet's peer awareness is a separate re-render/re-bootstrap action (out of PR3's auto path; documented, not silently assumed).

### 4. Partial-G0 smoke in `drill spoke`
On the throwaway drill spoke (already bootstrapped + auto-destroyed): copy the hub's `~/.claude/.credentials.json`, run one `claude -p "ok"`, and hash the creds file before/after. **Explicit pass/fail:** PASS = `claude -p` exit 0 **and** hash check recorded. This catches *immediate* single-session rejection at $0. It explicitly does **not** cover the 4-day refresh race (logged as such — no silent "validated"). Result appended to the drill report.

### 5. Reverse-teardown symmetry ([reverse_fleet_destroy](../../../src/fabrik/orchestrator/vultr_provision.py#L375))
Add reverse steps: `systemctl disable --now vps-sysadmin-bot.service aro-wake.service` (best-effort, host may be gone) and `release_bot_token(name)` so a destroyed/rebuilt spoke frees its pool slot.

---

## Validation gates

- **GP1** unit: `claim_bot_token` — claims first free; refuses double-assign; idempotent reclaim; empty-pool ⇒ `None` + log; `release` round-trips. (mocked file, `file_lock`.)
- **GP2** unit: `_provision_sysadmin` — happy path (token claimed → both units enabled → health 200); **empty-pool path** (bot skipped, aro-wake still enabled, no placeholder written); **health-timeout path** (gate fails fast, no hang). All SSH/curl mocked, no spend.
- **GP3** unit: deterministic peer map — `vps4` renders real peers (not `unknown`); existing trio hosts render unchanged.
- **GP4** drill: partial-G0 smoke has explicit pass/fail asserted in the drill-report schema test.
- **GP5** doc-sync + `scripts/final_gate.py --lean --json` green; CHANGELOG + (if new files) INDEX updated. No new env var in code (token pool is a DR-store file, not an env var) — confirm before claiming.

## Five-axis review contract (for the peer AI)
1. Four constraints present in **Design Constraints**; **C1 (never `ANTHROPIC_API_KEY`)** named explicitly.
2. Token-pool depletion visible; no silent double-assign; empty-pool refuses to enable (no crash-loop).
3. Partial-G0 smoke: explicit pass/fail (`exit 0` **and** hash), not "run and see"; refresh-race explicitly out of scope.
4. Peer-map change is deterministic and append-only in spirit — and (corrected from the original framing) touches **no** `wg0.conf`/`[Interface]` block, so no MSS-clamp concern; confirm it doesn't regress the live trio's rendered peers.
5. Verify gate's health + Telegram round-trip have a timeout + clean failure path — a comms outage fails the gate, never hangs provision.

## Out of scope (explicit)
- **Copied-creds zero-touch** (eliminating step 2) — gated on the 4-day refresh-race characterization.
- **Satellite / single-hub-bot** refactor — needs Phase 5 `propose`/`ack`.
- Anything touching `ANTHROPIC_API_KEY`.
- Auto-re-rendering the live trio's peer awareness when a host is added (separate re-bootstrap action).

## One-Test Rule

**Why:** The highest-risk path is the empty/exhausted token pool. If `claim_bot_token` returned a placeholder (or the caller enabled the bot anyway), `bot.py` would start with an invalid `TELEGRAM_BOT_TOKEN`, crash on `Application.builder().token(...)`, and `Restart=always`+`StartLimitBurst=5/300s` would drive the unit to `failed` in ~150s — a silent broken sysadmin on a freshly-billed box. This is the one failure that turns "automated" into "worse than manual."

**Contract:**
- **Given:** a provisioned, bootstrapped spoke `vps4` and an empty/exhausted bot-token pool.
- **When:** `_provision_sysadmin("vps4", ip, mesh_ip, report)` runs (claim returns `None`).
- **Then:** the bot is NOT enabled (`units_enabled == "aro-wake.service"`), `.env.sysadmin` is left untouched (no `sed`/placeholder write — asserted on the recorded ssh commands), `report["sysadmin"]["env_sysadmin"] == "skipped: token pool empty"`, and the function does not raise.
- **Mocked:** `claim_bot_token`, `_ssh_ozgur`, `_local_env_sysadmin`, `_check_aro_wake_health`, `_check_bot_token` (no real SSH/curl/Vultr/Telegram, no spend). Test: `test_provision_sysadmin_empty_pool_skips_bot_no_placeholder`.

## Cross-references
- [scripts/bootstrap/bootstrap-vps.sh](../../../scripts/bootstrap/bootstrap-vps.sh) — step_14 sysadmin pack, manual-finish message PR3 shrinks
- [scripts/sysadmin/bot.py](../../../scripts/sysadmin/bot.py) — the bot PR3 enables
- [scripts/sysadmin/peer-protocol.md](../../../scripts/sysadmin/peer-protocol.md) — mesh control plane (`:8201/wake`)
- [docs/archive/2026-06-07-fabrik-vultr-provisioning.md](../../archive/2026-06-07-fabrik-vultr-provisioning.md) — the shipped plan PR3 extends
