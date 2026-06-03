# P5 Sub-plan — Watchdog Dogfood E2E (defensive sub-plan; parent plan says none needed)

**Date:** 2026-06-03
**Phase:** P5 of the AI Watchdog Platform plan (3-day phase per parent plan)
**Parent plan:** [`2026-05-30-ai-watchdog-platform.md`](2026-05-30-ai-watchdog-platform.md) § "Acceptance criteria (whole plan)" (line 346)
**Prompt that motivated this sub-plan:** [`2026-05-30-ai-watchdog-platform-prompts.md` § P5 — Dogfood E2E](2026-05-30-ai-watchdog-platform-prompts.md) (lines 464–542)
**Status:** ✅ Sub-plan draft — awaiting owner confirmation. **No code edits performed in this turn (META-RULE 5).**
**Why a sub-plan when parent plan says none needed:** T-P5 touches live infra on the hub (docker build of a per-project image, compose-overlay write, sidecar container lifecycle, postgres-main reads, optional postgres-main outage chaos test). Doc + rule-pack edits like T-P3 / T-P4 are idempotent and easy to roll back; T-P5 is not. A 60-line sub-plan defines what we touch, how we abort, and what passes vs fails.
**Prior work shipped:** T-P1 + T-P2 + T-P3 + T-P4 — all 4 complete as of `4e9674a` (this morning). T-P5 is the only remaining watchdog phase.

---

## 0. Verification (META-RULE 1 — no assumptions)

### 0.1 Files / paths read for this sub-plan

| Path | State (verified 2026-06-03) |
| --- | --- |
| `/opt/test-saas-for-epic-wf` | **DOES NOT EXIST** — operator retired this in commit `cda4a48` ("first delete this /opt/test-saas-for-epic-wf it was a test project"). |
| `specs/services/test-saas-for-epic-wf.yaml` | **DOES NOT EXIST** — deleted in same `cda4a48` close-out. |
| `specs/services/watchdog-test.yaml` | ✅ Exists (~80 lines, docker-source `nginx:alpine` with `watchdog.enabled: true` + conservative caps daily $0.50 / per-incident $0.05 / 20 invocations/day / deadman 120s). Created 2026-06-03 as T-P2 artifact 15 for the end-to-end wire-up verification. |
| `docs/development/plans/2026-05-30-ai-watchdog-platform.md` § Acceptance criteria | ✅ Present at line 346. |
| All 10 T-P1/T-P2/T-P3/T-P4 artifacts (spec_loader, agent.py, Dockerfile, emitter.py, infrastructure.py, drivers/watchdog.py, 60-watchdog.md, self-healing.md, 02 + 03 mega-epic command files) | ✅ All present. |

### 0.2 Hub-side prereqs (read-only probes; live verified)

| Prereq | Probe + result |
| --- | --- |
| `cost_ledger` table on `postgres-main:fabrik_analytics` | ✅ Exists. `\d cost_ledger` returns the schema (id uuid PK, project_id text NOT NULL, ...). Provisioned by T-P1. |
| `apprise` container on hub | ✅ `apprise Up 3 days (healthy)`. Reachable via the `fabrik` docker network at `apprise:8000`. |
| Operator's `~/.claude/` on hub | ✅ Exists at `/home/ozgur/.claude/` (14 subdirs). This is the OAuth mount source `WatchdogDriver._push_overlay` bind-mounts RO into the sidecar. |
| `/opt/fabrik-lib/watchdog/sidecar/` on dev WSL | ✅ Exists with all sidecar code from T-P2. Driver vendors from here at build time. |

### 0.3 META-RULE 6 — verification failures

**1 failure surfaced.** The P5 prompt's deliverable line says: *"Deliverables: end-to-end test on `/opt/test-saas-for-epic-wf`."* That directory + its matching spec were deleted by the operator yesterday. **The P5 prompt is stale on its test target.** This sub-plan proposes a replacement (§ 2 below) and does NOT recreate the retired directory.

---

## 1. T-P5 scope reframed (decoupled from P5 prompt's stale targets)

The P5 prompt bundles two distinct verification goals into one 9-step chain:

| Sub-goal | Steps in P5 prompt | What it exercises |
| --- | --- | --- |
| **A — Traycer mega-epic-breakdown dogfood** | 1, 2, 3, 4 | The T-P4 edits to `02-epic-decomposition-command.md` + `03-expand-epic-files-command.md`. Operator-driven (Traycer GUI), not Claude-Code-agent-driven. |
| **B — Watchdog runtime dogfood** | 5, 6, 7, 8, 9 | The T-P1 + T-P2 + T-P3 runtime: deploy sidecar, emit incidents, chaos-test failover paths. Mostly automatable from Claude Code via SSH. |

**A and B can be decoupled.** They share nothing except "verifies the watchdog program shipped this week works end-to-end." Decoupling lets us:

- Run **B** first (more time-critical; touches live hub) against the small `watchdog-test.yaml` spec — which is what that spec was *built* for.
- Defer **A** to operator's Traycer-GUI session, or skip if operator considers the dry-run verification I did in T-P2 artifact 15 sufficient evidence the contract holds.

This sub-plan focuses on **B** (runtime dogfood). Sub-goal A is flagged as operator-decision in § 11 below.

---

## 2. Test target selection

**Recommended target: `specs/services/watchdog-test.yaml`** (the existing T-P2 artifact 15 spec). Reasoning:

- Already designed for sidecar wire-up verification (header comment in the spec says so).
- Conservative budget caps (daily $0.50; per-incident $0.05; 20 invocations/day) make accidental-real-spend impossible.
- Short deadman timer (120s vs 300s default) makes verification fast.
- Docker source (`nginx:alpine`) — no source repo to clone, no build, deploys in <30s.
- `target_vps: vps1` (default) — keeps the test on the hub where the operator can `docker logs` interactively.
- `domain: watchdog-test.vps1.ocoron.com` — no DNS record at Cloudflare yet, so HTTPS verifier will 404. That's fine for T-P5 (we're testing the sidecar, not Traefik).

**Alternative considered: recreate `test-saas-for-epic-wf`.** Rejected — operator explicitly retired it yesterday; recreating it contradicts that decision.

**Alternative considered: spin up a fresh test spec.** Rejected — would duplicate watchdog-test.yaml without adding signal.

---

## 3. Pre-flight checks (run before any T-P5 step)

These are the verifier commands; § 0 already ran each successfully but they should be re-run at T-P5 execution time since the hub state can change.

```bash
# A. Artifacts on dev WSL
ls /opt/fabrik-lib/watchdog/sidecar/{agent,llm_client,actions,state,cost_budget}.py \
   /opt/fabrik-lib/watchdog/sidecar/{Dockerfile,claude-settings.json.template,requirements.txt} \
   /opt/fabrik-lib/watchdog/emitter/emitter.py
ls /opt/fabrik/src/fabrik/{spec_loader.py,orchestrator/infrastructure.py,drivers/watchdog.py}
ls /opt/fabrik/specs/services/watchdog-test.yaml

# B. Spec validates clean (no real deploy)
cd /opt/fabrik && .venv/bin/fabrik apply specs/services/watchdog-test.yaml --dry-run

# C. Hub-side state
ssh vps "sudo docker ps --filter name=postgres-main --filter name=apprise --format '{{.Names}} {{.Status}}'"
ssh vps "sudo docker exec postgres-main psql -U postgres -d fabrik_analytics -c '\d cost_ledger'"
ssh vps "ls -la /home/ozgur/.claude/.credentials.json"
ssh vps "df -h / | tail -1"  # need >2 GB free for the ~600 MB sidecar image build

# D. No existing watchdog-test deployment to interfere
ssh vps "sudo docker ps -a --filter name=watchdog-test --format '{{.Names}} {{.Status}}'"
ssh vps "ls -la /opt/watchdog-test/ 2>/dev/null"
```

**Hard stop if any probe fails.** Each probe maps to a specific T-P5 step that would fail downstream.

---

## 4. Execution flow — adapted from P5 prompt Steps 5–9

Each step has: action → expected observation → pass/fail → rollback. Operator runs one step at a time; Claude Code agent assists with command construction + log parsing.

### Step 5 — `fabrik apply` the test spec

**Action:**

```bash
cd /opt/fabrik
.venv/bin/fabrik apply specs/services/watchdog-test.yaml
```

**Expected observation:**

- Cloudflare DNS A record for `watchdog-test.vps1.ocoron.com` is created (or already exists).
- SSH deploy of the nginx compose to `/opt/watchdog-test/` succeeds.
- Watchdog registrar fires (per the `_provision_watchdog` path shipped in T-P2 artifact 12).
- `WatchdogDriver.provision()` runs: vendors sidecar source to dev WSL tempdir → renders `claude-settings.json` from template → patches Dockerfile COPY line → tars → scps to `/tmp/fabrik-watchdog-build/watchdog-test/` on hub → `docker build -t fabrik/watchdog:watchdog-test` (expect ~3 min cold; ~5 s warm if Docker cache hits).
- Compose overlay written: `/opt/watchdog-test/compose.watchdog.yaml`.
- `docker compose -f compose.yaml -f compose.watchdog.yaml up -d watchdog` brings up `watchdog-test-watchdog` container.

**Pass criteria (`docker ps` after step):**

- `watchdog-test` (the main nginx container) — `Up (healthy)`.
- `watchdog-test-watchdog` (the sidecar) — `Up` + healthcheck eventually `healthy` (start_period 30s).
- `docker exec watchdog-test-watchdog ls /var/lib/watchdog/` returns `state.db` (created by `state.connect` on agent boot).

**Fail / rollback:**

- If Docker build fails: capture last 50 lines of the build log; check Dockerfile + rendered claude-settings.json on `/tmp/fabrik-watchdog-build/watchdog-test/`; STOP — sub-plan rev needed.
- If sidecar container loops on restart: `docker logs watchdog-test-watchdog --tail 100`; the agent.py boot path's `WatchdogContext.from_env` raises `SystemExit` on missing env vars, which surfaces as the most likely first-cause.
- Rollback: `fabrik destroy --use-state specs/services/watchdog-test.yaml` removes container + compose dir + image.

### Step 6 — Synthetic anomaly: kill the main container

**Action:** `ssh vps "sudo docker kill watchdog-test"` then wait up to 90 s.

**Expected observation within 90 s:**

- Sidecar's `gather_snapshot` notices the `oom-killer`-like signal in `docker logs` (or detects `State.Status: exited`).
- `detect_anomalies` doesn't fire (no log line for plain SIGKILL); `read_emitted_incidents` is empty (no host-app emitter); BUT the next-iteration `inspect` reports `RestartCount` increment + `State.Status=running` (Docker's `restart: unless-stopped` already restarted nginx).
- Sidecar may NOT emit an incident at all on this path — Docker's auto-restart could land before the sidecar's 60s tick.
- Expectation softened: **either** the sidecar logs a successful Tier A `restart_container` action (we'd see it in `state.db` `actions` table) **or** Docker's `restart: unless-stopped` beats the sidecar (no `actions` row).

**Pass criteria:**

- `nginx` is running again within 90 s (either path).
- If sidecar fired Tier A: `sqlite3 -readonly /var/lib/watchdog/state.db "SELECT * FROM actions WHERE action_name = 'restart_container'"` returns one row.
- If sidecar fired Tier A: 1 row in `cost_ledger` on postgres-main with `project_id='watchdog-test'`.

**Fail / rollback:**

- If nginx stays dead past 90 s: rule out `restart: unless-stopped` being absent (`docker inspect watchdog-test --format '{{.HostConfig.RestartPolicy.Name}}'`); rule out kernel-level docker issue.
- Rollback: same as Step 5.

**Note on the P5 prompt's "audit_log row written (verify hash chain integrity)":** the sidecar's `state.db actions` table is local SQLite; the **shared** `audit_log` on postgres-main is a separate concern (T-P1's `cost_ledger` is on postgres-main, but a shared `audit_log` table for `watchdog.tier_a_action` events would require a dedicated migration that I cannot verify shipped). **Side finding #1 below.**

### Step 7 — Provider fallback: kill host Claude Code session

**Action:** rename `~/.claude/.credentials.json` on the hub temporarily (`ssh vps "sudo mv /home/ozgur/.claude/.credentials.json /home/ozgur/.claude/.credentials.json.bak"`) then re-trigger the anomaly: `ssh vps "sudo docker kill watchdog-test"`.

**Expected observation within 60 s:**

- Sidecar's `_invoke_claude_code` exits non-zero (no OAuth credential).
- `llm_client.diagnose` catches `ProviderUnavailable`, falls back to `_invoke_openrouter`.
- OpenRouter is called if `WATCHDOG_OPENROUTER_KEY` is set in the sidecar env; if not set, `_invoke_openrouter` raises `ProviderUnavailable` and `diagnose` returns `RuleOnlyFallback`.

**Pass criteria:**

- If `WATCHDOG_OPENROUTER_KEY` is set: cost_ledger row with `provider='openrouter'` and non-zero `cost_usd`.
- If `WATCHDOG_OPENROUTER_KEY` is NOT set: cost_ledger row with `provider='rule-only'` (or no row at all if the agent skips ledger writes for rule-only); Apprise alert lands with the rule-only escalation tag.

**Rollback (mandatory after Step 7):** `ssh vps "sudo mv /home/ozgur/.claude/.credentials.json.bak /home/ozgur/.claude/.credentials.json"`. **Without this, every subsequent watchdog sidecar across the fleet loses Claude.** Sub-plan acceptance A4 below makes this rollback step a hard requirement.

### Step 8 — Budget kill-switch: force cost-budget to zero

**Action:** Edit the spec's cap in place via inject_env (or just SSH-edit `/opt/watchdog-test/.env`): set `WATCHDOG_DAILY_BUDGET_USD=0.01` (effectively zero after first call). Then `ssh vps "cd /opt/watchdog-test && sudo docker compose -f compose.yaml -f compose.watchdog.yaml up -d watchdog"` to apply.

**Expected observation:**

- Next anomaly: `cost_budget.check_caps` returns `BudgetState` with `over_cap=True` after one call.
- `cost_budget.drop_to_rule_only_mode(state)` returns `True`.
- agent.py `_handle_incident` short-circuits: escalates via Apprise with `(BUDGET-CAP)` tag, **never calls `llm_client.diagnose`**.

**Pass criteria:**

- Apprise message arrives carrying `(BUDGET-CAP)` text.
- No new row in `cost_ledger` for the budget-blocked incident (since no LLM call was made).
- agent.py logs `"budget kill-switch active for watchdog-test; rule-only escalation"`.

**Rollback:** revert `.env` edit; re-up the container.

### Step 9 — postgres-main outage: stop postgres-main for 60s

**Action:** `ssh vps "sudo docker stop postgres-main; sleep 60; sudo docker start postgres-main"`.

**Expected observation:**

- During outage: agent.py's `_open_pg` catches `psycopg.OperationalError`, returns `None`; `cost_budget.record_cost` falls open to WAL only (per cost-budget design — never blocks).
- `cost_wal.db` accumulates rows for any LLM calls fired during outage.
- After postgres-main returns: next iteration's `cost_budget.replay_wal` drains the WAL into the `cost_ledger` table within ~30 s.

**Pass criteria:**

- During outage: sidecar does NOT crash; healthcheck stays green.
- During outage: any anomalies still get processed (LLM call + action taken); cost rows queue in `cost_wal.db`.
- After restart: `SELECT count(*) FROM cost_ledger WHERE project_id='watchdog-test' AND ts > <outage_start>` matches the count of LLM calls made during the outage window. No rows lost.

**⚠ Risk: postgres-main outage breaks ALL fleet tenants for 60 s.** Per memory "silence ContainerDown alerts before any planned op >2 min", silencing required even though 60s < 2min — because postgres-main going down triggers cascading alerts from every consumer (gatus, alertmanager, every connecting app). **Mandatory: silence the ContainerDown alert group for the postgres-main name BEFORE running this step.**

**Rollback:** postgres-main restart restores. If postgres-main fails to come back up: `ssh vps "cd /opt/postgres && sudo docker compose up -d"` (postgres-main is in its own compose stack). If THAT fails: it's a real incident, not a test failure — operator handles.

---

## 5. Operator vs Claude Code agent boundaries

Claude Code agent CAN do (via SSH from dev WSL):

- Run the pre-flight `bash` probes in § 3.
- Run `fabrik apply` from dev WSL (Step 5).
- Run `docker kill`, `docker stop`, `mv` on hub for chaos tests (Steps 6, 7, 9).
- Query `state.db` via `docker exec watchdog-test-watchdog sqlite3 -readonly /var/lib/watchdog/state.db ...`.
- Query `cost_ledger` via `docker exec postgres-main psql -U postgres -d fabrik_analytics -c "SELECT ..."`.
- Tail `docker logs watchdog-test-watchdog`.

Claude Code agent CANNOT do (operator must):

- Verify Apprise → Telegram message actually arrived on operator's phone.
- Verify `~/.claude/.credentials.json` rename succeeded for Step 7 (requires operator's home dir access on hub).
- Decide GO/NO-GO between steps when a verification is ambiguous.
- Decide whether to ship Sub-goal A (Traycer dogfood) at all or defer.

Recommend operator stays at the keyboard for the full T-P5 session.

---

## 6. Idempotency analysis per step

| Step | Idempotent? | Notes |
| --- | --- | --- |
| Step 5 (`fabrik apply`) | ✅ Yes | Re-running re-builds image (cache-driven; fast), re-writes overlay (unconditional), `docker compose up -d` reconciles. State.db preserves rows. |
| Step 6 (`docker kill`) | ✅ Yes | Can run multiple times; each kill produces a fresh incident; `state.db` accumulates rows. |
| Step 7 (cred-mv chaos) | ⚠️ Requires explicit rollback | Without restoring `.credentials.json`, subsequent runs of any watchdog sidecar on the hub will all fall back to OpenRouter — silently inflating cost across the fleet. Rollback MUST land at end of Step 7. |
| Step 8 (budget zero) | ✅ Yes | Spec-side `.env` edit; reversible. |
| Step 9 (postgres-main stop) | ⚠️ Cascades to every tenant for 60s | Silence ContainerDown alert group first. After step, postgres consumers (every tenant) reconnect automatically; no data loss unless mid-write. |

---

## 7. State observation queries (for pass/fail verification)

```bash
# Sidecar state.db — incidents + actions table
ssh vps "sudo docker exec watchdog-test-watchdog sqlite3 -readonly /var/lib/watchdog/state.db \
  'SELECT id, source, name, severity, datetime(detected_at) FROM incidents ORDER BY detected_at DESC LIMIT 10'"

ssh vps "sudo docker exec watchdog-test-watchdog sqlite3 -readonly /var/lib/watchdog/state.db \
  'SELECT id, incident_id, tier, action_name, result, datetime(ts) FROM actions ORDER BY ts DESC LIMIT 10'"

# cost_ledger on postgres-main
ssh vps "sudo docker exec postgres-main psql -U postgres -d fabrik_analytics -c \
  \"SELECT id, project_id, provider, model, cost_usd, in_tokens, out_tokens, ts \
    FROM cost_ledger WHERE project_id='watchdog-test' ORDER BY ts DESC LIMIT 10\""

# cost-budget WAL (during postgres outage / replay verification)
ssh vps "sudo docker exec watchdog-test-watchdog sqlite3 -readonly /var/lib/watchdog/cost_wal.db \
  'SELECT seq, datetime(ts), provider, cost_usd, pushed_to_pg FROM cost_wal ORDER BY seq DESC LIMIT 10'"

# Sidecar healthcheck
ssh vps "sudo docker inspect watchdog-test-watchdog --format '{{.State.Health.Status}}'"

# Sidecar log tail
ssh vps "sudo docker logs watchdog-test-watchdog --tail 50"
```

These are read-only probes; safe to run repeatedly.

---

## 8. Risks & mitigations

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Sidecar Docker build OOMs on hub (hub has 11.6 GiB / 6 cores; build pulls Node.js + Claude Code CLI) | Low | Hub had ~7.7 GiB free on last check; build peak < 1 GiB. If OOM: run build on dev WSL via `docker save → scp → docker load`. |
| Sidecar memory limit (1024m per Dockerfile) too tight | Low–Medium | If sidecar OOMs at runtime: bump memory to 2048m via spec override (`watchdog.memory_limit` — not yet a config field; would need T-P5.5 amendment). |
| Step 7 rollback skipped → all fleet watchdog sidecars fall back to OpenRouter | High impact, low likelihood with discipline | Acceptance A4 below makes Step 7 rollback a HARD requirement. Add explicit "Step 7-DONE" checklist. |
| Step 9 cascades alerts → Telegram flood (memory: silence alerts before downtime) | High | Silence ContainerDown for postgres-main + dependent services BEFORE Step 9. |
| Build context tar.gz on hub fills `/tmp` if disk pressure | Low | Driver cleans `/tmp/fabrik-watchdog-build/<project>/` in `finally`. Acceptance A3 verifies post-run. |
| Apprise message arrives but operator misses it on phone | Medium | Operator self-paces; we don't push past Apprise verification without operator ack. |
| OpenRouter cost overrun if Step 7 fires repeatedly | Low (caps + WATCHDOG_PER_INCIDENT_BUDGET_USD=0.05 enforced) | Spec's `daily_budget_usd: 0.50` is the hard ceiling. Worst case 1 day = $0.50. |
| watchdog-test container occupies port 80 on hub? | Low — Traefik fronts everything, no host-port binding per the Fabrik invariant. Verify via `docker ps` `Ports` column post-Step-5. | — |

---

## 9. Pass / fail criteria for the whole phase

| # | Criterion | How to verify |
| --- | --- | --- |
| A1 | Sidecar deploys + reaches `healthy` state | `docker inspect` Step 5 |
| A2 | Tier A path (Step 6) lands a row in `state.db actions` OR Docker auto-restart beats the sidecar | sqlite3 query Step 6 |
| A3 | Build dir `/tmp/fabrik-watchdog-build/watchdog-test/` cleaned post-run | `ssh vps "ls /tmp/fabrik-watchdog-build/"` empty or absent |
| A4 | Step 7 rollback executed before next step | Operator-confirmed checklist; `ssh vps "ls /home/ozgur/.claude/.credentials.json"` returns the file |
| A5 | Step 8 budget-cap path: Apprise message contains `(BUDGET-CAP)`; no new `cost_ledger` row | Apprise log + sqlite3 query |
| A6 | Step 9 postgres outage: `cost_wal.db` accumulated rows during outage; drained into `cost_ledger` after restart; row count matches | sqlite3 + psql queries |
| A7 | No fleet-side regressions: gatus checks for postgres-main, glitchtip, traefik all green by end of session | gatus dashboard |
| A8 | Operator confirms Apprise → Telegram path actually delivered messages | Operator's phone (not automatable) |

---

## 10. CHANGELOG + LESSONS_LEARNT post-run

Per parent plan acceptance: each artifact gets a CHANGELOG entry; any cross-cutting insight goes into `docs/LESSONS_LEARNT.md`.

After T-P5 completes successfully:

- **CHANGELOG entry** under `[Unreleased]`: `### Verified — T-P5 dogfood E2E: watchdog runtime verified end-to-end (2026-06-04)`. Body names each of Steps 5–9 with the evidence rows/Apprise messages observed.
- **LESSONS_LEARNT entry** *only* if a cross-cutting insight emerged (e.g., "Docker `restart: unless-stopped` beats the watchdog sidecar tick window — sidecar Tier A `restart_container` may never fire in practice for fast-restart paths" would be a real lesson worth recording).

After T-P5 close:

- Subplan archived to `docs/development/plans/archived/2026-06-03-watchdog-P5-subplan.md`.
- `vps-status.md` + `vps-ai-sysadmin.md` watchdog rows bumped from "T-P5 ⏳ remaining" to "T-P5 ✅ complete" with the evidence summary.
- Parent plan `2026-05-30-ai-watchdog-platform.md` archived since all 5 phases shipped.

---

## 11. Open questions for owner before T-P5 execution starts

1. **Sub-goal A (Traycer dogfood Steps 1–4) — ship or defer?** Per § 1 above, Steps 1–4 require an operator-driven Traycer GUI session against a NEW SaaS vision. They exercise T-P4's universal-coverage edits. If deferred, T-P5 ships only Sub-goal B (runtime dogfood) and parent-plan acceptance is met but Sub-goal A is documented as a pending operator action.
2. **Step 9 (postgres-main outage) — green-light or skip?** This is the riskiest step. The pre-existing 60-second postgres-main outage cascades alerts across every tenant. If operator prefers to skip: A6 becomes "verified separately via cost-budget unit tests" (T-P1 already shipped tests for `replay_wal`).
3. **OpenRouter API key on the sidecar — set or not?** Determines whether Step 7 verifies the OpenRouter fallback path or the rule-only-mode fallback path. Both are valid T-P5 outcomes; just need to know which.
4. **Sidecar image build location — hub or dev WSL?** Driver builds on hub by default. If hub disk pressure is a concern, can pre-build on dev WSL and `docker save → scp → docker load` instead. Adds ~3 min round-trip but avoids any hub-side OOM risk.

---

## 12. Side findings (META-RULE 4 — flagged, NOT fixed)

1. **Shared `audit_log` table for `watchdog.tier_a_action` events — status unknown.** The P5 prompt step 6 says "audit_log row written (verify hash chain integrity)". I verified `cost_ledger` exists on postgres-main, but did NOT verify a shared `audit_log` table exists. Sub-plan §4 Step 6 softened the criterion to local `state.db actions` table only. **If operator wanted hash-chained postgres audit_log per T-P1, that table may or may not have shipped — needs verification before T-P5 execution.** Out of scope for this sub-plan write.
2. **`docs/LESSONS_LEARNT.md` Lesson 31** (env-var verification via `docker inspect`) — cited correctly in 02 § Observability Defaults (E7). No issue.
3. **Driver's `_push_overlay` mounts `/opt/<project_id>` RO into sidecar at `/project`.** Step 6's "clear_file_cache" Tier A handler writes to `/project/<subpath>/*` — that's a RO mount, so `clear_file_cache` is a no-op for read-only project trees. **For watchdog-test (nginx default content), this means clear_file_cache cannot succeed.** Sub-plan §4 doesn't test this Tier A action; flagging because P5 prompt acceptance "Tier A action handlers work" would fail for this specific handler against this specific test target.
4. **Sub-step 2h (T-P4) requires Traycer to actually read 02 fresh.** If operator runs Sub-goal A but Traycer has 02 cached, the new sub-step 2h may not execute. Operator should paste 02's content into Traycer fresh, not "load from My Workflows" — per the source-file header comment.
5. **Parent plan archive timing.** Per § 10 above, parent plan archives after T-P5. If T-P5 Sub-goal A is deferred indefinitely, parent plan never archives. Operator decides whether "Sub-goal B complete + Sub-goal A documented as deferred" is sufficient to archive the parent plan, or whether the parent plan stays open until Sub-goal A ships.

---

## 13. Self-review against META-RULES

| META-RULE | This sub-plan addresses |
| --- | --- |
| 1. No assumptions, no hallucinations | § 0 verifies every claim with live probes; flags 1 failure (P5 prompt's stale test target). |
| 2. Read before write | All cited paths read or grep'd before this turn's writing. Parent plan § Acceptance criteria found at line 346. |
| 3. One artifact per turn | This sub-plan IS the artifact. No 02 / 03 / sidecar / live edits performed this turn. |
| 4. Scope discipline | 5 side findings (§ 12) flagged, NOT fixed. T-P5 execution itself is the next artifact. |
| 5. Sub-plan first, code second | Defensive sub-plan written per owner request; no code edits this turn. |
| 6. When verification fails, say so | P5 prompt's test target is stale (deleted by operator yesterday); surfaced in § 0.3 and addressed in § 2. |
| 7. End: name files touched | See "Files touched this turn" below. |
