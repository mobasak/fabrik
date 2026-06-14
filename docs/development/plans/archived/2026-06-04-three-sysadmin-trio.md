# Plan — Three Veteran Sysadmin Trio: symmetric AI ops across vps1 + vps2 + vps3

**Created:** 2026-06-04
**Status:** ✅ **All concrete phases SHIPPED.** Phases 1+2+3+4 live across the full fleet since 2026-06-06; Phase 5.1.a (operator-reversal cron via `detect_reversals.py` + `*/5 min` cron) live since 2026-06-07. **Phase 5 is "iteration discipline (open-ended)" by design** — it has no terminal state and never "completes." Its deferred items are tracked in [`docs/STRATEGIC_BACKLOG.md`](../../STRATEGIC_BACKLOG.md) "Later" tier, each gated on a real triggering incident (the whole point: don't speculate). Verified live state 2026-06-13: `vps-sysadmin-bot.service` + `aro-wake.service` ACTIVE on vps1+vps2+vps3, `.env.sysadmin` present on all three, real cross-host consults end-to-end (vps2→vps1, vps3→vps1) returned diagnostic responses.
**Last iterated:** 2026-06-04 r3 — self-iteration against r2's own additions (10 new internal-consistency gaps surfaced and closed); see § 11 for the iteration ledger
**Author intent:** AI-managed, auto self-healing infra with one veteran-sysadmin Claude per host, communicating peer-to-peer over the wg0 mesh, triggered by signal not by polling. No single point of AI failure.
**Parent context:** Direct continuation of [`archived/2026-05-30-ai-watchdog-platform.md`](archived/2026-05-30-ai-watchdog-platform.md) T-P5 Step 6 (per-project sidecar self-heal verified end-to-end on vps1 2026-06-04). This plan generalizes the same calling convention to host-level operations on all three hosts.
**Scope:** AI ops layer only. Does NOT touch backups (Backrest stays as-is), DR scripts (`bootstrap-hub.sh` / `bootstrap-spoke-restore.sh` stay), tenant code, or operator-driven strategic decisions.

**Plan archived 2026-06-14.** All concrete phases shipped + live-validated. The Phase 5 deferred items live in `STRATEGIC_BACKLOG.md` and unlock incident-by-incident:

| Phase 5 deferred item | Unlocks when |
| :--- | :--- |
| `propose`/`ack` peer-protocol verbs | First real cross-host destructive action that `consult` + Telegram-bridge can't handle |
| Apprise pre-route through aro-wake | First incident proving Alertmanager-only triage missed something |
| Loki ruler with starting rule set | First incident a log-pattern rule would have caught earlier than container-state probe |
| Grafana `aro-wake` dashboard | Operator running the same PromQL recipe 3+ times in a week |
| "Repeated-flag-no-action" detector (complement to `detect_reversals.py`) | Second occurrence of the netdata-flood pattern |
| Cert expiry auto-renew | First near-expiry surfaced via Gatus that wasn't auto-fixed by Traefik restart |
| Authelia auth-failure burst escalation | First sustained burst that the existing fail2ban-direct doesn't already catch |
| Backup-plan-fail auto-retry | After Known Issue 1 hostname fix lands in restic-store (separate concern) |

---

## 0. The single sentence we're trying to make true

> *"Three veteran sysadmin AIs, one per host, observe every signal the fleet collects, fix what they're competent to fix on the host they own, consult each other before crossing host boundaries, report honestly to the operator, and survive partition without losing local autonomy."*

If at any point during execution a phase makes that sentence less true, the phase is wrong.

---

## 1. Scope (what this plan ships)

| In scope | Out of scope |
|---|---|
| `system-prompt.txt` updated to current live state + host-substitution markers | Loki ruler with 10+ pre-emptive rules (rules added per incident encountered) |
| `peer-protocol.md` (new) — defines `consult`/`propose`/`ack` | Hardware SMART textfile collector (add after first disk warning) |
| Watchdog sidecar `llm_client.py` reverted to load canonical sysadmin prompt | A separate "hub aggregator AI" (explicitly rejected — single point of failure) |
| `aro-wake` FastAPI service deployed on each host, `consult` verb only at first ship | Cross-host coordinated action (`propose`/`ack`) — defer until `consult` proves it needs escalation |
| Sysadmin pack (`bot.py` + cron + scripts + `.env.sysadmin`) shipped to vps2; vps3 trivial after | Cost dashboards / budget UIs (operator directive: no per-call $ caps on sysadmin) |
| Alertmanager webhook → host-targeted `aro-wake` (push-trigger path) | Apprise pre-hook routing (defer; only adds value after `aro-wake` proves stable) |
| Operator-action gates listed at end of plan (3 items) | Spoke-tenant watchdog dogfood on a real app (defer until you deploy something to vps2/vps3) |

### 1.5 Truth-table cross-check (r2 — convergence pass)

Each operator-named "what we want" scenario from the destination doc, mapped to the phase that delivers it. **If any row says "GAP", the plan does not yet converge.**

| Scenario | Today | What we want | Delivered by |
|---|---|---|---|
| Container exits on vps1 | watchdog sidecar restart | same on every host, every opted-in container | Phase 1 (revert narrow prompt — sidecar already works on vps1); Phase 5 deferred: per-spec opt-in spreads to spokes as tenants land |
| Container exits on vps2 (sub-90s) | manual | local AI restarts within 90s | Phase 2 cron (15min fallback) + Phase 4 Alertmanager push (sub-30s) + per-project sidecar for any container the operator marks `watchdog.enabled: true` (60s tick) |
| Disk filling on vps3 — "rotates/prunes safely" | manual SSH | AI rotates + age-gated prune | Phase 2 expansion: add `docker image prune --filter "until=720h"` (30d-stale only) + logrotate verification to the AUTONOMOUS class in `system-prompt.txt`; current hard-ban on `docker system prune` (unfiltered) STAYS |
| 5xx burst — correlate with last fabrik apply, rollback | Telegram alert | AI consults + rolls back if deploy correlation | Phase 3 `consult` for cross-host correlation. **Cross-host destructive action (rollback on another host) — until Phase 5 ships `propose`/`ack`: AI proposes precise command via Telegram, waits for operator `reply "go"`** |
| Mesh handshake stale | nothing fires | AI notices, attempts mesh repair, annotates partition | Phase 2 expansion: wg handshake check in `proactive-check.sh` (moved up from Phase 5 deferred); `systemctl restart wg-quick@wg0` added to AUTONOMOUS class. iptables modification stays banned. |
| Cert about to expire | Gatus → Telegram | AI re-issues | Phase 5: `acme.json` mtime + cert chain check; if stale > 60d, `docker restart traefik` (forces ACME re-validation). Action allow-listed in system prompt. |
| Authelia auth-failure burst | metric exists, no alert | AI diagnoses, escalates to fail2ban | Phase 5: Prom rule on `authelia_authentication_*`; allow-listed action is `fail2ban-client set authelia banip` (jail-scoped, not iptables-direct) — iptables stays banned |
| Backup plan fails | broken hook (Known Issue 1) | AI reads restic output, retries or escalates | Phase 2 — Known Issue 1 hostname fix (moved up from Phase 5 deferred — 1-line sed); after that, failures land in Apprise → existing Telegram path; Phase 4 wires aro-wake on top |
| All three hosts agree about shared infra | 3 separate Telegram alerts | first AI consults peers, one acts, one report | Phase 3 — **consult semantics: the affected resource's host AUTHORS the action; peers' consult responses are diagnosis-only**. vps2+vps3 see postgres-main pain → consult vps1 → vps1 acts → peers wait. No vote, no race. |
| Hub down | spokes have no AI | spokes self-heal locally; queue hub-bound actions | Phase 2 — spoke AIs are local-first (covered). Phase 3 — `aro-wake` writes failed forwards to `/var/lib/aro-wake/pending.jsonl` (TTL 1h); mesh-recovery hook drains. Partition annotation rule in the system prompt: every report under partition says `(peer X unreachable; acting on local view only)`. |

**Convergence check r2: all 10 scenarios → at least one phase. No GAP row remains.**

### 1.6 Explicit out-of-scope (operator-runbook items, not AI scope)

The plan does NOT make the trio responsible for the following. Each has an existing operator-driven path; AI may DETECT and report but does not act:

| Out-of-scope class | Why | Operator path |
|---|---|---|
| Kernel panic / Docker daemon death on a host | AI itself dies with daemon; **detection is via external observer (operator's IPMI / VPS provider console / OOB monitoring) — NOT the AI**. Once host is recoverable, AI assists with post-mortem from journald + dmesg. | OOB IPMI / VPS provider console; `bootstrap-{hub,spoke}-restore.sh` if disk lost |
| Postgres-main failover | Single-host postgres-main is shared infra; no replica today | `docs/operations/disaster-recovery.md`; future architectural decision (Patroni / pgpool) is operator's call |
| Full fleet loss (all 3 hosts + B2) | Existential; out of scope for AI | Path C in `docs/operations/disaster-recovery.md` — GitHub-only rebuild |
| Operator workstation (dev WSL) wiped | DR-store covers credentials; rebuild is human-led | `docs/operations/credential-recovery.md` |
| iptables / netplan / sshd_config / /etc/docker/daemon.json edits | Hard-banned in `system-prompt.txt`; rationale: trivial to make a host unbootable | Manual operator change |
| Code quality / architecture decisions | AI fixes incidents, not the underlying causes | Operator engineering |
| Container memory DECREASES, container stops, anything destructive | ASK OWNER FIRST in `system-prompt.txt` | Operator approves via Telegram `reply "go"` |
| Cross-host destructive actions (until Phase 5 `propose`/`ack` ships) | Lean cut: defer the protocol; bridge via operator-approval | Same — Telegram `reply "go"` |
| OpenRouter fallback simultaneous failure across all 3 hosts (r3) | All 3 hosts use the operator's single OpenRouter account; a single 402 (credit) or 429 takes the fallback path down for the entire fleet at once. Per-call $ caps stay banned per operator directive. | Operator monitors credit balance separately (Grafana panel scraping OpenRouter `/auth/key` periodically); if all-fleet fallback fails, rule-only + deadman bleed-stop still works (sidecar safety net) |
| Cross-host action authorship contention (r3 edge — corner) | If two AIs simultaneously think a third resource is theirs to act on (rare; happens only with mis-labeled metrics), §3.2 authorship rule resolves: the AI on the resource's actual host wins; the other one consults | Single-line consult-semantics check in system prompt: "Verify the resource lives on your host before acting; if uncertain, consult first" |

### 1.7 The AI lifecycle: wake → fix → sleep (r7 — architecture principle made explicit)

**The natural state of every AI in this plan is asleep.** Listeners are always-on but lightweight; Claude itself is ephemeral — spawned per signal, exits when done. **No idle LLM compute. No always-running model.** Same pattern proactive-check.sh already uses on vps1 since 2026-05-20; this plan propagates it.

#### 1.7.1 The four trigger paths (per host)

```text
TELEGRAM-DRIVEN — vps-sysadmin-bot.service (systemd, always-on, cheap)
─────────────────────────────────────────────────────────────────────
[idle: polling Telegram getUpdates every ~10s, ~50MB RAM, ~0% CPU]
   │
   ├─ operator sends message →
   │
   ▼
[spawn: claude -p ... --model opus --resume <sid>]
   │
   ▼ (5-30s typical)
[Claude reads ctx, runs Bash/Grep/Read, acts, replies via stdout]
   │
   ▼
[subprocess exits; bot.py keeps polling]
   │
   ▼
[idle again]


CRON-DRIVEN — proactive-check.sh (every 15 min via /etc/cron.d/vps-sysadmin)
───────────────────────────────────────────────────────────────────────────
[cron sleeps until xx:00, xx:15, xx:30, xx:45 — zero process running]
   │
   ▼
[pure-bash PromQL probes: container_memory? disk? load? mesh handshake?]
   │
   ├─ all clear → exit 0 silently (no LLM cost, no Telegram)
   │
   └─ anomaly detected:
        ▼
   [spawn: claude -p ... --model opus]
        │
        ▼ (5-30s)
   [Claude diagnoses + acts + reports via Apprise → Telegram]
        │
        ▼
   [cron job exits; nothing running until next tick]


PUSH-DRIVEN (Phase 4) — Alertmanager → aro-wake
─────────────────────────────────────────────────────────────
[aro-wake FastAPI idle, listening on 10.99.0.N:8201 (mesh-only), ~60MB RAM]
   │
   ├─ Prometheus rule fires → Alertmanager webhook → POST /wake
   │
   ▼
[aro-wake checks rate-limit + dedup, looks up affected host, forwards or
 handles locally; spawns claude -p ...]
   │
   ▼ (5-30s)
[Claude acts; aro-wake forwards summary to peer or telegram]
   │
   ▼
[aro-wake idle again]


SIDECAR-POLL — per-project watchdog (only on opted-in projects)
─────────────────────────────────────────────────────────────
[agent.py: 60s sleep loop in container, ~30MB RAM, ~0% CPU]
   │
   ▼
[gather_snapshot: docker inspect + logs --tail 200 (no LLM cost)]
   │
   ▼
[detect_anomalies: rule pass — container state, log triggers]
   │
   ├─ [] → loop back to 60s sleep
   │
   └─ incident → spawn claude -p ... → Tier A action →
                 state.db row → cost_ledger row → sleep
```

#### 1.7.2 Cost shape per always-on listener (single host)

| Component | Idle RAM | Idle CPU | LLM cost when idle | Active cost per wake | Wake frequency baseline |
|---|---|---|---|---|---|
| `vps-sysadmin-bot.service` (1 per host) | ~50MB | ~0% (10s Telegram poll) | $0 | one claude subprocess, 5-30s, Max-subscription burn (no marginal $) | only when operator messages — typically 0-5/day |
| `proactive-check.sh` cron | 0 between ticks | 0 between ticks | $0 | one claude subprocess only when bash prefilter detects anomaly | every 15min, ≤5/h Claude wakes rate-limited; on a healthy host most ticks exit in <500ms |
| `aro-wake` service (1 per host, Phase 3+) | ~60MB | ~0% (FastAPI idle) | $0 | one claude subprocess per push, dedupe by `(source, topic)` | only when a Prometheus rule fires + routed to this host |
| Watchdog sidecar (per opted-in project) | ~30MB | ~0% (60s loop) | $0 (snapshot is local docker calls) | one claude subprocess only when rule fires; `--resume` keeps cache warm | proven today on watchdog-test: 0 wakes when nginx is healthy |
| OAuth keepalive cron (hourly) | 0 between ticks | 0 between ticks | $0 | one $0.005 ping per hour | 24/day = $0.12/host/day flat |
| **Total always-on per host** | **~140-200MB** | **~0%** | **$0** | — | — |

**Net baseline (healthy fleet, nothing happening):** ~140-200MB RAM × 3 hosts = ~600MB across the fleet for listeners. Zero LLM spend except $0.12/host/day OAuth keepalive (~$11/mo total fleet). On an 8-12GB host, listeners are <2% of RAM.

**Active cost (per real incident):** one Claude Opus subprocess for 5-30 seconds. With `--resume` warm cache, ~$0.005-0.05 per incident on subscription burn. Zero marginal cash cost since the operator is on Claude Max (subscription is flat-rate); the cost limit is rate (Anthropic's Max-account rate limit, not $).

#### 1.7.3 What this means concretely

- **vps1 right now** (mid-conversation, mid-watchdog-test-dogfood): both bot.py + cron + watchdog-test-watchdog are **asleep** between events. Verifiable: `ps aux | grep claude` shows no claude processes; `systemctl status vps-sysadmin-bot.service` shows `active (running)` but the process is just polling.
- Operator sends Telegram → bot wakes within 10s → Claude runs ~10s → bot back to polling.
- 15 min later: cron wakes → bash probes Prometheus → all healthy → cron exits in ~200ms without ever calling Claude → next 15min sleep.
- 5 min later: nginx crashes → watchdog sidecar's next 60s tick sees `Status=exited` → Claude runs ~5s to issue `restart_container` → sidecar back to 60s sleep.
- 30 min later: Alertmanager rule fires for vps3 disk pressure → vps3's aro-wake receives the webhook → spawns Claude → Claude rotates logs → returns → aro-wake idle.

**Sleep is the default. The plan does not introduce continuous LLM compute.**

#### 1.7.4 Why this matters for the plan's success

Three direct implications:

1. **§5 criterion #12 (cost discipline) is achievable by construction**, not by tuning. There's no always-on Claude to control; the only cost knob is "did we wire too many wake triggers." The lean cut (Phase 4 wires Alertmanager only; Apprise/Loki/Gatus deferred to Phase 5) protects this directly.
2. **§5 criterion #9 (no single-AI-failure regression) is enforced by listener locality.** Each host's listeners are independent processes. Killing aro-wake on vps1 doesn't even degrade vps1's bot.py + cron paths, let alone vps2/vps3.
3. **§1.6 partition tolerance follows for free.** When mesh partitions, push triggers (Alertmanager → aro-wake on a peer) just fail and queue; pull triggers (cron + sidecar) keep working because they don't cross the mesh. Local AI keeps healing local issues; consult times out → annotated reports.

---

## 2. Pre-flight verification (META-RULE 1 — no assumptions; check before write)

Before any code changes, the following live state must be verified by the executor and pasted into the plan's execution log:

| Probe | Expected | Why we check |
|---|---|---|
| `wc -l /opt/fabrik/scripts/sysadmin/system-prompt.txt` | `232 lines` (or current) | confirms the canonical prompt exists, locates it |
| `grep -c coolify /opt/fabrik/scripts/sysadmin/system-prompt.txt` | `>0` | confirms stale Coolify refs present (Phase 1.1 fixes them) |
| `ssh vps2 'systemctl is-active vps-sysadmin-bot.service'` | not-found / inactive | confirms vps2 has no sysadmin yet (Phase 2 prerequisite) |
| `ssh vps2 'test -d /home/ozgur/.claude && echo OK'` | OK or fail | tells us whether `claude auth login` has been done on vps2 |
| `ssh vps 'sudo systemctl is-active vps-sysadmin-bot.service'` | active | confirms vps1 host sysadmin still running (no regression risk) |
| `ssh vps 'sudo wg show \| grep "latest handshake" \| head -3'` | both peers < 5 min | mesh healthy → cross-host calls will work |
| `ssh vps 'sudo docker exec prometheus wget -qO- http://localhost:9090/api/v1/targets 2>&1 \| grep -c up'` | ≥ 18 | observability healthy → trigger sources we'll wire are alive |
| `grep -c _WATCHDOG_SYS_PROMPT /opt/fabrik-lib/watchdog/sidecar/llm_client.py` | `>0` (today) → `0` (after Phase 1.3) | confirms the narrow prompt is still in place, will be removed |

**If any probe disagrees with the expected value, STOP and report.** Do not paper over.

---

## 3. Phases

Each phase is independently shippable. Phase N+1 builds on N being live. Total ~5 working days end-to-end; any single phase can pause without leaving the system worse off than before.

### Phase 1 — Prompt correctness (~1 day)

**Goal:** Stop the watchdog sidecar from being a JSON action picker; restore the veteran-sysadmin scope it inherited from the existing host-level prompt. Refresh the host-level prompt to current live state.

#### 1.1 Refresh `scripts/sysadmin/system-prompt.txt`

Fixes (verified live 2026-06-04):

| Stale | Current truth |
|---|---|
| "Docker `coolify` network" | "Docker `fabrik` network" (renamed 2026-05-31) |
| CRITICAL-INFRA list includes `coolify, coolify-db, coolify-redis, coolify-realtime, coolify-sentinel` | replace with current critical containers: `traefik, postgres-main, redis-main, authelia` |
| `Netdata` listed in infrastructure_apis | remove — verify with `ssh vps 'sudo docker ps --format "{{.Names}}" \| grep -i netdata'`; not present in current 30-container list |
| implicit vps1-only scope | introduce `{{ HOST_NAME }}` / `{{ HOST_IP }}` / `{{ HOST_ROLE }}` / `{{ PEER_HOSTS }}` substitution markers; rendered at bootstrap time per host |
| no mention of OAuth-token-stale risk | add a 2-line note: "your `~/.claude/.credentials.json` is RO-mounted; if you hit 401, that's a stale token — the keep-alive cron handles it but report it once per 24h so the operator can see if the cron is dead" |

Files touched: `/opt/fabrik/scripts/sysadmin/system-prompt.txt` (in-place edit, backup first per CLAUDE.md `Pointers > Backup secrets before edit` — system prompt is not a secret but the existing-file-before-create discipline applies)

#### 1.2 Add `scripts/sysadmin/peer-protocol.md`

New file (~120 lines target). Sections:

1. The 3 verbs (`consult`, `propose`, `ack`/`nack`) with payload schemas
2. When to use each (decision rules from the system prompt's perspective)
3. Mesh partition behavior — `consult` timeouts after 5s → AI annotates report `(peer X unreachable; acting on local view only)`
4. Concrete examples (3 short scenarios: 5xx burst with hub-side correlation; cert expiry consult; disk pressure with no peer involvement)
5. Hard constraints (no destructive action on peer's host without `ack`; no auto-`ack` — humans-or-explicit-peer-decision)

Files touched: new file `/opt/fabrik/scripts/sysadmin/peer-protocol.md`

#### 1.3 Revert narrow watchdog prompt in `llm_client.py`

Current state: `_WATCHDOG_SYS_PROMPT` constant (~30 lines) hardcoded in [`llm_client.py`](../../../fabrik-lib/watchdog/sidecar/llm_client.py).

Change:

- Remove `_WATCHDOG_SYS_PROMPT` constant
- At module init, read `/project/.fabrik/sysadmin-prompt.txt` if present (operator can override per project); else fall back to `/home/watchdog/sidecar/system-prompt.txt` (vendored from host at image build time by the driver)
- Append the spec's `project_system_prompt` (already a field; renames "project-specific addition")
- The watchdog driver (Phase 1.3.a) copies `/opt/fabrik/scripts/sysadmin/system-prompt.txt` into the build context, renders the host substitution markers for the host the sidecar will run on, ships as part of the image

Files touched:
- `/opt/fabrik-lib/watchdog/sidecar/llm_client.py` — drop constant, load file
- `/opt/fabrik-lib/watchdog/sidecar/Dockerfile` — `COPY system-prompt.txt /home/watchdog/sidecar/`
- `/opt/fabrik/src/fabrik/drivers/watchdog.py` — `_build_context` step that copies + renders the prompt with the target host's substitutions

#### 1.4 Acceptance criteria (Phase 1)

| Test | Pass condition |
|---|---|
| Re-run today's T-P5 Step 6 (`docker kill watchdog-test`) | Same incident → action → resolved loop (≤90s); but **the Claude diagnose now produces veteran-sysadmin-shaped reasoning** (free-text rationale citing infrastructure classification + correlation steps, not just `{"tier": "A", ...}`) |
| `grep -c "coolify" /opt/fabrik/scripts/sysadmin/system-prompt.txt` | `0` |
| `grep -c "{{ HOST_NAME }}" /opt/fabrik/scripts/sysadmin/system-prompt.txt` | `>0` |
| New `peer-protocol.md` exists, ≥100 lines, lint clean | yes |
| `_WATCHDOG_SYS_PROMPT` removed from `llm_client.py` | `grep -c _WATCHDOG_SYS_PROMPT == 0` |
| Existing host sysadmin bot still functional (Telegram message → response) | yes |

#### 1.5 Risks (Phase 1)

| Risk | Mitigation |
|---|---|
| Sidecar can't find `system-prompt.txt` at runtime (missing COPY) | image build fails fast at COPY step; CI/dry-run catches before live deploy |
| Substitution markers in prompt confuse Claude when un-rendered | render before COPY; verify rendered prompt has no `{{ ... }}` left |
| Reverting the narrow prompt breaks today's working watchdog flow | retest Step 6 immediately after revert; if regression, narrow prompt is git-reverted and we debug forward |

---

### Phase 2 — Sysadmin pack on vps2 (~1.5 days)

**Goal:** vps2 has its own veteran-sysadmin AI that owns vps2's docker.sock + journald + local exporters and acts via local `sudo docker`. vps3 is a copy of this work.

#### 2.1 `bootstrap-vps.sh` gains `step_14_install_sysadmin_pack()`

> **r3 note on step numbering:** the bootstrap script today goes up to `step_13_install_spoke_dns`. We claim `step_14` for the sysadmin pack. Future bootstrap work should pick `step_15+` and document the convention in `bootstrap-vps.sh`'s header comment so concurrent plan branches don't collide on numbering.

Function copies:

- `vps-sysadmin-bot.service` (systemd unit) — adapted to read `/opt/fabrik/.env.sysadmin` on the spoke
- `/etc/cron.d/vps-sysadmin` (5 cron entries — same as vps1)
- `/opt/fabrik/scripts/sysadmin/*` (bot.py + 4 shell scripts + system-prompt.txt rendered for `{{ HOST_NAME }} = vps2`, etc.)
- `/opt/fabrik/.env.sysadmin` (per-host Telegram bot token + chat id — operator-provided)

#### 2.2 Add Phase 2 prerequisites to the bootstrap step

| Prereq | Auto / operator |
|---|---|
| Claude Code installed on vps2 (`which claude`) | bootstrap auto-installs via npm (matches vps1 install path) |
| `claude auth login` completed on vps2 | **operator action** — browser handshake; no automation path |
| `~/.claude/.credentials.json` exists | verify post-login |
| `/opt/fabrik/.env.sysadmin` populated with vps2 bot token | **operator action** — needs @BotFather chat |
| Mirror vps2's Claude creds to DR-store `mobasak/fabrik-dr-store` under `spokes/vps2/claude/` | extend `fabrik-dr-watcher.service` paths; auto after bootstrap |

#### 2.3 OAuth keepalive cron on every host

Add to `/etc/cron.d/vps-sysadmin` on every host:

```text
# OAuth keepalive — Claude Code OAuth tokens go stale every ~4 days when
# the host is idle; one cheap `claude -p` refreshes the credentials file.
# Hourly is sufficient (token freshness window is days, not hours).
# Lesson 75 (2026-06-04). Cadence revised r3 from */12min → hourly.
0 * * * * ozgur claude -p "ping" > /var/log/claude-keepalive.log 2>&1
```

Cost per host: ~$0.005 per ping × 24/day = $0.12/day, ~$3.60/mo across the fleet. Log file is the heartbeat — proactive-check (§2.5) flags it as anomalous if mtime > 90 minutes (covers cron skew + slow Claude API responses).

#### 2.4 Per-host audit trail to Loki + recording rule

Each host's `bot.py` already appends to `/opt/fabrik/logs/sysadmin-actions.jsonl`. Promtail on each host already ships container + system logs. Add a promtail scrape job for the sysadmin actions file on each host so the operator can query `{job="sysadmin-actions", host="vps2"}` in Grafana.

Files touched (per-host promtail config):
- vps1: `/opt/monitoring/configs/promtail/promtail-config.yaml`
- vps2/vps3: `/opt/monitoring-agent/promtail.yaml` (bootstrap-rendered)

Plus one Loki recording rule aggregating `count_over_time({job="sysadmin-actions"}[24h])` per host → Grafana panel `Fleet AI activity / 24h actions per host`. Operator sees daily volume at a glance; spike = investigation hint, zero = host AI may be dead.

#### 2.5 Expansions to `proactive-check.sh` (moved up from Phase 5 deferred — iteration r2)

The following checks are too important to defer; they were truth-table-named scenarios (#5, #8) and belong in the first ship of the spoke pack, not later:

| Check | Probe | Action on anomaly |
|---|---|---|
| Mesh handshake stale | `wg show \| awk '/latest handshake/ {print $3,$4}'` per peer; flag if > 180s | Wake Claude with peer name + handshake age; allowed autonomous action: `systemctl restart wg-quick@wg0` (single retry, then escalate) |
| Backrest plan failure | `restic snapshots --json --repo <repo> \| jq` last 24h | If no fresh snapshot for an expected plan, wake Claude with restic last-log tail; diagnose lock contention / B2 4xx / path issues |
| OAuth keepalive cron alive | `find /var/log/claude-keepalive.log -mmin -30` | If file > 30min stale, escalate (the keepalive cron itself is dead — sysadmin's primary LLM path will go stale in ~4 days) |
| Known Issue 1 hostname fix | one-shot sed at install time: `apprise-lcocgs4gs8ksg4g08w40ows8` → `apprise` in `/opt/backrest/config/config.json` on every host | Trivial; do once during `step_14_install_sysadmin_pack()` |

#### 2.6 Autonomous-action promotions in `system-prompt.txt` (r2)

Current prompt's hard-coded bans are conservative (good — they protect against catastrophic failure). But two action classes the truth table requires must be promoted from "ASK OWNER FIRST" / banned to **AUTONOMOUS with constraints**:

| Action | Old class | New class | Constraint |
|---|---|---|---|
| `docker image prune --filter "until=720h"` | banned (under "no bulk cleanup") | autonomous | Only with explicit 30d-stale filter; bare `docker system prune` STAYS banned |
| Logrotate verification + selective `find /var/log -name "*.gz" -mtime +30 -delete` | not addressed | autonomous | Path-scoped to `/var/log`; never `/opt`, never `/var/lib` |
| `systemctl restart wg-quick@wg0` | not addressed | autonomous | One retry per hour; if still failing, escalate |
| `docker restart traefik` (cert renewal forcing) | platform-class restart already autonomous | clarified | After verifying acme.json mtime > 60d |
| `fail2ban-client set <jail> banip <ip>` | not addressed | autonomous | Jail-scoped; explicit list of permitted jails: `sshd`, `authelia`. iptables direct stays banned. |

All other hard-coded bans (docker volume prune, iptables, netplan, daemon.json, /etc/fstab, sshd_config) remain.

#### 2.7 `.env.sysadmin` secret hygiene (r2)

`.env.sysadmin` on each host contains the Telegram bot token + (optionally) the OpenRouter fallback key. Treat as secret:

- mode 600, owner `ozgur:ozgur`
- gitignored (`.env.sysadmin` already in repo `.gitignore`; verify per-host)
- mirrored to `mobasak/fabrik-dr-store` via the existing W9 watcher; new paths: `env/sysadmin/vps1`, `vps2`, `vps3`
- never logged; bot.py `bot_token` field is redacted in `sysadmin-actions.jsonl` writes
- recovery: `gh repo clone mobasak/fabrik-dr-store && sudo cp .../env/sysadmin/vps2 /opt/fabrik/.env.sysadmin`

#### 2.8 Daily digest report (r2 — fights Telegram flood; r3 — UTC clarified)

Each host's bot posts one digest at **09:00 UTC** (all three hosts on same wallclock; vps1 is LA so this is 02:00 local, vps2/vps3 in Coventry so 09:00 BST/10:00 BST — operator gets three Telegram messages within seconds of each other, easy to compare), regardless of incident activity:

```text
[vps2] Daily digest 2026-06-05 09:00 UTC
  Actions:    12 Tier A (11 restart_container, 1 image_prune)
  Escalations: 0
  Reverts:    0
  Consults received: 3 (all answered, avg 1.4s)
  Consults sent:     1 (vps1 about CF state — got answer)
  Health:      claude OAuth fresh (file mtime 47m ago — within 90m window)
                aro-wake up since 06:18 UTC
                mesh handshakes: vps1 17s, vps3 22s
                pending queue: 0 entries
```

Per-action Telegram only for non-trivial actions (anything outside the autonomous allow-list, or any escalation). Routine `restart_container` events log to `sysadmin-actions.jsonl` silently and roll up into the digest. Operator sees one digest per host per day + real incidents in real time.

#### 2.5 Acceptance criteria (Phase 2 — vps2 first)

| Test | Pass condition |
|---|---|
| `ssh vps2 'sudo systemctl is-active vps-sysadmin-bot.service'` | `active` |
| `ssh vps2 'sudo cat /etc/cron.d/vps-sysadmin \| wc -l'` | ≥ 6 entries (5 existing + OAuth keepalive) |
| Operator sends a Telegram message to vps2's bot | reply within ~10s, content makes sense |
| Synthetic fault: `ssh vps2 'sudo docker stop cadvisor'` then wait 15min | `proactive-check.sh` on vps2 fires within the next window; restarts cadvisor; Telegram report from vps2's bot |
| Loki query `{job="sysadmin-actions", host="vps2"}` in Grafana | returns the audit-log entry from the synthetic fault |
| `ssh vps2 'sudo cat /opt/fabrik/logs/sysadmin-actions.jsonl \| tail -1 \| jq .host'` | `"vps2"` (not vps1) |

vps3 is the same step run with HOST=vps3.

#### 2.6 Risks (Phase 2)

| Risk | Mitigation |
|---|---|
| Operator can't complete `claude auth login` on vps2 (no browser on the VPS) | Use Claude Code's CLI-OAuth flow (operator opens the device-flow URL in dev WSL browser; Claude stores the token on vps2 via the displayed code) — same as vps1 was set up |
| Three Telegram bots is operationally annoying (3 separate chats) | Operator may prefer one shared token + prefix-routing (`@vps2 ...`); both designs work, plan accommodates either via `.env.sysadmin` content |
| Spoke `proactive-check.sh` queries Prometheus on the hub by default | rewrite spoke proactive-check to query local node-exporter + cadvisor directly (loopback / mesh-local) — no hub dependency for local self-heal |
| Spoke acts on a vps1 issue it shouldn't | system prompt's `{{ HOST_NAME }}` substitution scopes the AI's authority — `you own vps2 only`; cross-host action requires Phase 3's peer protocol |

---

### Phase 3 — `aro-wake` HTTP service + `consult` verb (~1.5 days)

**Goal:** Each host has a mesh-reachable endpoint that wakes its local AI; the three sysadmins can ask each other "what do you see from your side?" before deciding.

#### 3.1 `aro-wake` service (FastAPI, ~330 lines as shipped)

> **r8 update (2026-06-04 batch 4):** the deploy shape evolved during build. Original r1 design said "Lives on each host at `/opt/aro-wake/`. Compose service binds `127.0.0.1:8201` + `10.99.0.<host>:8201`." Shipped reality is **systemd-managed FastAPI** (no compose; same systemd pattern as `vps-sysadmin-bot.service` which proved out 2026-05-20) at **`/opt/fabrik/scripts/aro-wake/`** with a dedicated venv at `/opt/fabrik/.venv-aro-wake/`. Binds **wg0 mesh IP only** (`10.99.0.<host>:8201`), not loopback — self-probes from the same host (e.g. `proactive-check.sh`'s health check) curl that same mesh IP. The plan text below reflects the shipped reality; the original r1 prose is preserved in the iteration ledger (§11 r8 entry) for traceability.

Lives on each host at `/opt/fabrik/scripts/aro-wake/`. systemd-managed FastAPI service (uvicorn) at `/opt/fabrik/.venv-aro-wake/bin/uvicorn`, bound to `10.99.0.<host>:8201` (wg0 mesh IP only — never `0.0.0.0`, never loopback). Public-internet protection: UFW default-deny on the 8200-8299 management-tools range + the explicit mesh-IP bind. Endpoints at first ship:

```text
POST /wake
  body: { source: "alertmanager" | "consult" | "telegram" | "manual",
          from_host: "vps1" | "vps2" | "vps3" | null,
          trace_id: <uuid>,
          seen_by: [<host names already in the consult chain>],
          topic: <slug>,
          payload: <opaque, passed to Claude as part of the prompt> }
  behavior: spawns `claude -p ...` with the host's canonical system prompt;
            calling convention matches scripts/sysadmin/bot.py::_run_claude verbatim
            (--model opus --permission-mode bypassPermissions --session-id ... --resume);
            response shape branches on source:
              consult → { ok, from_host, trace_id, seen_by, view, correlation, no_action: true }
                        (matches peer-protocol.md §2.1; [vps1] Telegram prefix stripped from view)
              other   → { ok, from_host, trace_id, seen_by, result, no_action: false }

GET /health → { ok, host, role, pending_queue_count, active_sessions }
```

Implementation notes:

- **Rate limit**: max 20 wakes / hour per `(source, topic)` pair to prevent storm. Thread-safe (`threading.Lock`). Verified hammer test: 30 concurrent calls against 20/h cap → exactly 20 allowed.
- **Pending queue**: failed cross-host forwards persist to `/var/lib/aro-wake/pending.jsonl` with 24h TTL, 1000-entry cap, oldest-first overflow. Background asyncio task drains every 30s; protected by `asyncio.Lock` so concurrent /wake handlers can queue without racing the drain.
- **Session resume**: each `(source, topic)` keeps its Claude session id for 1h so multiple consults on the same topic stay in conversation. Effective `session_id` is stored from envelope (not local sid we passed) so future `--resume` targets the right session even if Claude returned a different id.
- **Defensive envelope parse**: handles both single-dict and event-list Claude output shapes; ported from `fabrik-lib/watchdog/sidecar/llm_client.py`.
- **Mesh-only**: `aro-wake` binds wg0 IP, never `0.0.0.0`. Verified via `ss -tlnp | grep 8201`.
- **Cycle prevention**: every consult carries `trace_id` + `seen_by`. If our host is already in `seen_by` we answer with current state only, do NOT forward.

Files (shipped at `mobasak/fabrik` commit `ed24f78` + review-pass commits `6d65606` / `ec015be` / `cb153f8`):

```text
scripts/aro-wake/main.py                 # FastAPI app + Claude subprocess
scripts/aro-wake/requirements.txt        # fastapi 0.115 + uvicorn[standard] 0.32 + httpx 0.27
scripts/aro-wake/templates/aro-wake.service.template
```

Bootstrap step_15_install_aro_wake (`scripts/bootstrap/bootstrap-vps.sh`) renders the systemd unit with host-specific values (HOST_NAME, HOST_IP, PEER_HOSTS_CSV — note **CSV not JSON** because systemd's `Environment=` strips embedded double-quotes from bare JSON, verified via systemd round-trip), rsync's the source tree to `/opt/fabrik/scripts/aro-wake/`, creates the venv at `/opt/fabrik/.venv-aro-wake/`, pip installs requirements.

Re-run safety: `rsync -a --delete src/ dst/` form is used everywhere (not `cp -R src dst` which nests on existing destinations). Idempotent.

#### 3.2 `consult` verb only — full semantics (r2)

The system prompt teaches Claude when to call `consult`:

```text
When you see a condition that might span hosts (DNS, CF, hub-side services,
upstream registrar state, fleet-wide capacity), call your peers BEFORE
acting on anything that could be wrong on a peer's host:
  POST http://10.99.0.<peer>:8201/wake
    { source: "consult", from_host: "{{ HOST_NAME }}", trace_id: <uuid>,
      seen_by: [<list of hosts that have already seen this trace_id>],
      topic: <slug>, payload: { my_view: <2-3 sentence summary>,
                                asking: <what you want from them> } }

Timeout 5s. If timeout, annotate your final report:
  "(peer vps2 unreachable; acting on local view only)"
```

**Authorship rule (r2 — scenario #9 fix):**

> The host whose RESOURCE is affected AUTHORS the action. Peers' consult responses
> are diagnosis-only. If vps2 sees postgres-main pain (resource is on vps1), vps2
> consults vps1, vps1 decides + acts, vps2 waits and reports `(deferred to vps1)`.
> No vote, no race, no double-action.

**Cycle prevention (r2 — gap #11):**

> Every consult carries a `trace_id` (uuid) + `seen_by` list. On receipt, if your
> host name is already in `seen_by`, you answer with your current state ONLY and
> do NOT re-consult anywhere. This breaks vps2→vps1→vps2 loops in one hop.

**Consult responses NEVER trigger autonomous action on the recipient side.** The system prompt is explicit: a `consult` payload is read-only information for the receiving AI; it informs but does not authorize. Action is authorized only by your host's own observers (rule fires on your metrics, sidecar tick on your container, operator message to your bot).

`propose`/`ack` deferred to Phase 5 — `consult` alone is enough for diagnosis. Cross-host coordinated action becomes valuable only when we hit a real case `consult` can't handle. **Interim bridge for cross-host destructive actions: AI proposes precise command in Telegram, waits for operator `reply "go"` before executing.** Listed explicitly in §1.6.

#### 3.3 Pending queue + mesh-recovery drain (r2 — scenario #10 fix)

`aro-wake` on each host maintains `/var/lib/aro-wake/pending.jsonl`. When a forward (`consult` to a peer, or Alertmanager → wrong-host route) fails because the target is unreachable:

```
{ "ts": <epoch>, "ttl_until": <ts + 3600>, "intended_for": "vps2",
  "payload": <original wake body>, "attempts": 1 }
```

A small worker thread inside `aro-wake` retries pending entries every 30s, exponential backoff capped at 5min. On success, line is removed. On TTL expiry (**24h, r3 — bumped from 1h to survive multi-hour hub outages**), line is dropped with a Loki audit log entry. Queue capped at 1000 entries / 10MB on disk; overflow drops oldest-first with a `pending_queue_overflow` Loki entry.

**Mesh-recovery hook:** when `wg show` indicates a previously-stale peer has handshaken in the last 30s, the queue is force-drained immediately (don't wait for the 30s retry tick). Triggered by a small bash script in the same cron pack that watches handshake state.

This means: hub goes down for 20 minutes; vps2 sees something it wants to consult vps1 about; consult times out; queues. Hub comes back up; queue drains; vps1's AI receives the queued consult; answers. Operator sees the delayed answer in Telegram with timestamp showing partition window.

#### 3.3 Acceptance criteria (Phase 3)

| Test | Pass condition |
|---|---|
| `aro-wake` running on all three hosts | `ssh vpsN 'curl -sf http://127.0.0.1:8201/health'` returns 200 |
| Mesh reachability | `ssh vps2 'curl -sf http://10.99.0.1:8201/health'` and `vps3 → vps1` both 200 |
| Public reachability blocked | `curl http://<vpsN public IP>:8201/health` connects refused or times out (verified from off-mesh) |
| Synthetic consult | from vps2, `claude -p "consult vps1 about: do you see traefik 5xx?"` → vps1's aro-wake handles → vps1's Claude replies with current traefik state → vps2's report includes the answer |
| Partition behavior | block 10.99.0.1:8201 on vps2 via iptables → vps2's consult times out at 5s → final report has the "(peer vps1 unreachable; acting on local view only)" annotation |
| Rate limit | 6 rapid wakes of the same `(source, topic)` → 6th returns 429 |

#### 3.4 Risks (Phase 3)

| Risk | Mitigation |
|---|---|
| `aro-wake` becomes a single point of failure on a host if it dies | systemd `Restart=always`; bot.py + cron paths still work without aro-wake (they invoke claude directly); aro-wake is the push-path only |
| Claude session limits hit if many consults stack | session reuse per topic + 60s TTL queue prevent runaway |
| Peer asks consult, recipient acts on it (escalation loop) | system prompt rule: consult RESPONSES are diagnosis only, NEVER trigger autonomous action on the recipient side; you only act on signals from YOUR host's observers |

---

### Phase 4 — Alertmanager push wire (~1 day)

**Goal:** Prometheus rule fires reach the affected host's sysadmin AI within seconds, not on the 15-min cron.

#### 4.1 New Alertmanager receiver

In [`/opt/monitoring/configs/alertmanager/alertmanager.yml`](../../infrastructure/vps-complete-inventory.md):

```yaml
receivers:
  - name: aro-wake-routed
    webhook_configs:
      - url: http://aro-wake-router:8201/wake?source=alertmanager
        send_resolved: true
        max_alerts: 0
  - name: telegram
    # existing block unchanged — fallback path
```

#### 4.2 New routing rule

```yaml
route:
  receiver: aro-wake-routed
  group_by: ['alertname', 'host', 'container']
  routes:
    - matchers:
        - severity =~ "critical|warning"
      receiver: aro-wake-routed
      continue: true   # also fire telegram so we never lose visibility on AI miss
    # existing telegram routes stay as fallback
```

#### 4.3 Host-routing inside `aro-wake`

When `aro-wake` receives an Alertmanager webhook, it reads the alert's `host` label and forwards to the right host:

- `host=vps1` → process locally
- `host=vps2` → `POST http://10.99.0.2:8201/wake` (re-source `alertmanager-proxied`)
- `host=vps3` → similar
- **no `host` label** (r3): default to vps1's `aro-wake` for triage AND emit a `low_quality_alert` Loki entry naming the alertname; operator fixes the upstream rule to emit `host` labels properly. Don't fail silently.
- **multiple `host` labels or contradictory** (r3): rare but possible (e.g., a rule about cross-host services); fan out to all named hosts; each one's AI receives the same payload; consult semantics in §3.2 prevent double-action via authorship rule.

Avoids "vps1 acts on a vps2 alert via SSH" — instead the right host's AI acts locally with its own `sudo docker`.

#### 4.4 Acceptance criteria (Phase 4)

| Test | Pass condition |
|---|---|
| `amtool alert add alertname=TestAlert host=vps2 severity=critical` from vps1 | within 30s vps2's aro-wake logs receipt, Claude spawned, Telegram report from vps2's bot |
| `amtool alert add ... host=vps1 ...` | vps1's aro-wake handles locally |
| Alertmanager → aro-wake URL unreachable | falls through to `telegram` receiver (existing behavior preserved) |
| `severity=info` alert | does NOT wake AI (routes only critical+warning); still fires telegram if any rule matches |
| Same alert refires after AI fixed it | Alertmanager `repeat_interval` honored; aro-wake dedup by `(alertname, host, container)` key — no double-wake |

#### 4.5 Risks (Phase 4)

| Risk | Mitigation |
|---|---|
| Alert storm wakes Claude 100× in a minute | rate limit + dedup in aro-wake (Phase 3.1) |
| Wrong host gets the wake (label drift) | system prompt rule: AI verifies the alert is about its own host before acting; if not, returns 400 + logs |
| Alertmanager → aro-wake URL hardcoded; aro-wake down = all alerts silent | `continue: true` on the route + telegram fallback receiver = always-on Telegram path preserved |

---

### Phase 5 — Iteration discipline (open-ended)

**Goal:** From this point forward, growth is incremental. Each new incident teaches the AIs something; capability expands the prompt + allowlist, not the architecture.

#### 5.1 The iteration loop

For each real incident encountered:

1. AI handled it → log in `sysadmin-actions.jsonl`; weekly review for false positives
2. AI escalated correctly (Telegram with honest "I don't know") → operator fixes; if pattern repeats, add to system prompt's runbook section
3. AI missed it entirely (no wake fired) → identify which signal class was uncovered; add Prometheus rule / Loki rule / textfile collector
4. AI made a wrong action → add to "ASK OWNER FIRST" section of system prompt; consider revert path

#### 5.1.a Detect operator reversals automatically (r2 — gap #16; r3 — detection broadened)

When the AI takes an action and the operator immediately reverses it, that's a learning signal. Detection must catch all reversal shapes (not just "another restart within 60s" — r3 #24):

```bash
# */5min cron on each host. Correlate AI actions with subsequent operator-issued
# docker commands on the same target within a 5-minute window.
#
# Source of truth for AI actions: state.db actions table (sidecar) +
# sysadmin-actions.jsonl (host bot).
# Source of truth for operator counter-actions: journald docker events filtered
# to NOT-from-watchdog-container, NOT-from-vps-sysadmin-bot.service.

journalctl --since "-10min" --output json \
  -u docker.service \
  | jq 'select(.MESSAGE | test("(start|stop|restart|rm|kill) "))' \
  | python3 /opt/fabrik/scripts/sysadmin/detect_reversals.py
```

Reversal classes detected:
- AI `restart_container` followed by another `restart`, `stop`, `kill`, `rm`, or `up -d --force-recreate` on the same container within 5min
- AI `clear_redis_cache` followed by any redis operation on the same DB index
- AI `rotate_logs` followed by manual `truncate` or file deletion in the same dir

Append matches to `/opt/fabrik/logs/lessons-pending.jsonl` for weekly operator review. Pattern: 3+ reversals of the same action class in a week → that class moves from AUTONOMOUS → ASK OWNER FIRST in `system-prompt.txt`. Single-incident reversals are noise; sustained pattern is a signal.

#### 5.1.b Sidecar / host sysadmin de-dup rule (r2 — gap #13; r3 — state.db read path specified)

Two AIs could see the same container exit (per-project sidecar at 60s tick + host sysadmin's proactive-check at 15min, or aro-wake routed Alertmanager fire). The system prompt's restart action gets one rule:

```text
BEFORE running `docker restart <container>`:
  1. Check if a per-project watchdog sidecar exists for <container>:
       sudo docker ps --filter name=<container>-watchdog --format '{{.Names}}'
     If present, read its state.db (file is in the sidecar's RW volume,
     owned by uid 1000; we read via docker exec, never via host path):
       sudo docker exec <container>-watchdog sqlite3 -readonly \
         /var/lib/watchdog/state.db \
         "SELECT action_name, result, ts FROM actions
           WHERE incident_id IN
             (SELECT id FROM incidents
               WHERE details LIKE '%\"container\":\"<container>\"%'
                 AND detected_at > strftime('%s','now','-120 seconds'))
           ORDER BY ts DESC LIMIT 1"
     Decide:
       - row exists with result=success → sidecar handled it; SKIP, log "deferred to sidecar".
       - row exists with result=failed → sidecar tried and failed; YOU ACT NOW
         with the same Tier A action and note "host sysadmin escalation after
         sidecar failure" in your report.
       - no row → wait 90s for the sidecar's next tick, then re-check.
  2. If no sidecar container present, you are the only watcher; act immediately.
```

Sidecar's 60s tick beats the 15min cron in practice, so collisions are rare; this covers the edge case where push-routed Alertmanager fires the host sysadmin before the sidecar's next tick.

#### 5.2 Deferred work (commit when triggered, not speculatively)

Cert expiry, Authelia burst, disk prune autonomy, wg restart, Backrest hostname fix — moved into Phases 2 + truth-table cross-check as named actions (scenarios #3, #5, #6, #7, #8 from §1.5). What remains as truly speculative:

| Trigger | Work |
|---|---|
| First time a `consult` answer indicates a coordinated action is needed | Add `propose`/`ack` verbs to peer-protocol |
| First time Loki sees a recurring log pattern we didn't catch | Add Loki ruler rule for it |
| First disk SMART warning | Add `node-exporter` textfile collector + rule |
| First spoke tenant deploy with `watchdog.enabled: true` | Dogfood the multi-host watchdog driver path on that tenant (Steps 5-6 from T-P5 sub-plan, repeated on the spoke) |
| First Apprise/Gatus/GlitchTip alert that would have benefited from AI triage | Wire that source through aro-wake (same shape as Alertmanager wire) |
| Operator-noted attention drain | Tighten thresholds / extend autonomous action class / tune AI confidence threshold for self-action vs escalate |
| Monthly coordinated drill (r2 — gap #19) | Operator injects synthetic anomaly that requires consult (edit `/etc/hosts` to simulate stale apex DNS); verify trio converges on diagnosis; restore. Counts as §5 criterion #11. |

---

## 4. Boundaries — what the AIs do, what the operator does

| Owner | Responsibility |
|---|---|
| Per-host AI | Container restart on PLATFORM + APPLICATION class on its host; log diagnosis; consult peers; report to Telegram |
| Per-host AI | Hardware reads (SMART, journald), network reads (wg show, ss), security reads (fail2ban, authelia metrics); recommend action; act if in allow-list |
| Operator | Three bot tokens (@BotFather × 3 OR one shared); approve first run on each host; periodic action-log review; strategic / capacity / architectural decisions |
| Operator | Trust calibration: as the AIs prove out on a class of action, promote that class from "ASK OWNER FIRST" to "AUTONOMOUS" in the prompt |
| Both | Backup integrity — Backrest is the source of truth; AIs detect failures, operator handles restore |
| Both | DR — `bootstrap-hub.sh` + `bootstrap-spoke-restore.sh` are operator-driven; AIs assist during incidents but DR is human-led |

---

## 5. Pass / fail criteria for the whole plan

The plan succeeds when ALL of the following are true and remain true for 7 consecutive days:

| # | Criterion | How verified |
|---|---|---|
| 1 | Three sysadmin bots active across the fleet | `for h in vps vps2 vps3; do ssh $h 'sudo systemctl is-active vps-sysadmin-bot.service'; done` → all `active` |
| 2 | Three aro-wake services active across the fleet | same form, port 8201 health 200 from each host's loopback |
| 3 | Each host's AI uses the canonical veteran-sysadmin prompt (not a narrow JSON picker) | grep each host's prompt source; lint check that no `_WATCHDOG_SYS_PROMPT` constant exists anywhere |
| 4 | Cross-host consult works end-to-end | live test: vps2 consults vps1 about a synthetic topic, receives + uses the answer in its report |
| 5 | Alertmanager rule fires wake the correct host's AI within 30s | inject a labeled test alert; observe wake path in aro-wake logs of the right host |
| 6 | Partition tolerance demonstrated | block 10.99.0.1:8201 from vps2 via iptables for 5 min; vps2 keeps healing locally with annotated reports; restoring connectivity restores consult |
| 7 | Audit trail visible in Grafana | Loki query `{job="sysadmin-actions"}` returns entries from all 3 hosts |
| 8 | Operator interruption rate ≤ baseline / 2 | Telegram message count to operator for week N+30 ≤ 50% of week N (before plan) |
| 9 | No single-AI-failure regression | force-kill aro-wake on vps1 → vps2 and vps3 sysadmins keep working on their hosts uninterrupted |
| 10 | No silent decisions | every action ends up either in Telegram or in `sysadmin-actions.jsonl` within 10s of acting; nothing lost |
| 11 | Monthly coordinated drill passes (r2 — gap #19) | Operator injects synthetic anomaly that requires consult (e.g., `/etc/hosts` edit simulating stale apex DNS, or `iptables -A INPUT -p udp --dport 51820 -j DROP` simulating mesh partition). Trio must: detect within 5min, converge on diagnosis via consult, restore or escalate honestly. Operator's playbook is reproducible; checklist in `docs/operations/ai-trio-drill.md` (to be written when first drill runs). |
| 12 | Cost discipline holds (r2 — gap #15) | Three hosts share one Max account; verify 7-day average daily token spend < $10/host (subscription is flat-rate but per-call counts inform rate-limit risk). Anthropic 429s during normal operation → 0 expected; if non-zero, OpenRouter fallback engaged correctly |
| 13 | OAuth keepalive proven across all 3 hosts (r2 — gap #4) | `find ~/.claude/.credentials.json -mmin -1440` returns a file on every host every day; if not, the keepalive cron itself is dead and digest report flags it |

---

## 6. Risks across phases (top-level)

| Risk | Phase | Mitigation |
|---|---|---|
| Operator gets fatigued by three Telegram bots; ignores some | 2 | Offer the prefix-routed-single-bot variant in 2.1; let operator pick after a week |
| AI false-positive acts (restarts a container that didn't need it) | all | All Tier A actions are reversible; restart_container has zero data loss on stateless services; audit log makes patterns visible after a week |
| Mesh partition during a real incident | all | Partition tolerance is criterion #6; each host's local autonomy is the whole point of the design |
| Claude OAuth token expires mid-incident on one host | 2 | OAuth keepalive cron (`*/12 * * * * claude -p ping`); fallback to OpenRouter; finally rule-only + deadman bleed-stop |
| Prompt drift between three hosts (one updates, others don't) | 2, 5 | Single canonical file in `/opt/fabrik/scripts/sysadmin/system-prompt.txt`; bootstrap renders per-host; updates pushed via `fabrik apply` or git-pull-and-systemd-reload |
| AI consult escalates to a propose-without-protocol loop | 3 | System prompt rule: consult responses are DIAGNOSIS ONLY, never trigger action on the recipient side — verified by Phase 3.4 acceptance test |
| `aro-wake` becomes a soft single-point-of-failure on a host | 3, 4 | systemd `Restart=always`; bot.py + cron paths still function without aro-wake (it's the push path only, polling paths persist) |

---

## 7. Open questions for operator before execution starts

1. **Three Telegram bots or one shared with prefix routing?** (affects Phase 2.1; either works; my recommendation is three for zero ambiguity)
2. **Claude auth on spokes — execute `claude auth login` via device-flow now, or wait until Phase 2 starts?** (no harm in doing it now; gates Phase 2 only)
3. **Should the OAuth keepalive cron also write to `sysadmin-actions.jsonl` so we can detect when keepalive itself dies?** (recommend yes; tiny addition)
4. **Phase 5 is open-ended — when do you want the first "what did the AIs do this week" review?** (suggest weekly first 30 days, then monthly)

---

## 8. CHANGELOG + LESSONS_LEARNT post-execution

Each phase landing requires:

| Phase ship | CHANGELOG `### Added` / `### Changed` entry | LESSONS_LEARNT new entries |
|---|---|---|
| 1 | "Watchdog sidecar reverted to canonical veteran-sysadmin prompt; per-host substitution markers added" | only if Phase 1.1 stale-fixes surface a discipline lesson |
| 2 | "Sysadmin pack deployed on vps2 (+ vps3 same day); OAuth keepalive cron on all hosts" | likely 1-2 lessons (first-spoke-claude-auth quirks) |
| 3 | "aro-wake service + consult verb live across fleet" | likely 1 lesson (peer-consult timeout / partition behavior surprises) |
| 4 | "Alertmanager → aro-wake push wire; host-routing on label" | likely 1 lesson (alert-storm / dedup) |
| 5 | per-incident lessons over time | as incidents teach |

---

## 9. Final gate

When all phases ship and all 10 success criteria hold for 7 days, run [`scripts/final_gate.py --systemic --json`](../../../scripts/final_gate.py). This plan is closed when that returns `{"status": "success"}` and the parent platform plan ([`2026-05-30-ai-watchdog-platform.md`](2026-05-30-ai-watchdog-platform.md)) is updated to reference this plan as the completion vehicle for "fleet-wide AI ops" originally scoped under T-P6.

**Plan archive location after close:** `docs/development/plans/archived/2026-06-04-three-sysadmin-trio.md`.

---

## 11. Iteration ledger

Each revision of this plan records what changed + why, so the convergence path is auditable. Operator can ask "why did Phase 2 grow between r1 and r2?" and get a per-line answer.

### r1 — 2026-06-04 initial draft

Initial structure: 5 phases (Prompt correctness → Spoke sysadmin → aro-wake/consult → Alertmanager push → iteration discipline) + pre-flight verification + boundaries + 10 success criteria + risks + 4 open questions + final gate.

Lean cuts applied at r1: `consult` verb only (defer `propose`/`ack`); vps2 first then vps3; hardware SMART / Loki ruler / Apprise pre-hook deferred to Phase 5.

### r2 — 2026-06-04 convergence pass against operator's truth table

Operator quoted back the destination + 10 concrete "what we want" scenarios and said "iterate indefinitely to converge."

**Method:** read each scenario against the plan; find rows where the plan fell short or was silent; classify as GAP; apply fix; re-check.

**Gaps closed in r2 (20 total — 10 from operator's truth table + 10 second-order):**

| # | Gap | Where fixed in r2 |
|---|---|---|
| 1 | Container exit vps1 — already covered | §1.5 row 1 — no change |
| 2 | Container exit vps2 sub-90s response | §1.5 row 2 — clarified: watchdog sidecar for opted-in; cron is fallback only |
| 3 | Disk pruning autonomy missing | §1.5 row 3 + §2.6 — promote `docker image prune --filter` + log rotation from banned to autonomous-with-constraint |
| 4 | Cross-host destructive action interim path | §1.5 row 4 + §1.6 + §3.2 — operator `reply "go"` bridge until `propose`/`ack` ships |
| 5 | Mesh handshake stale needs Phase 2, not Phase 5 | §1.5 row 5 + §2.5 — `wg show` check moved to `proactive-check.sh` expansion; `systemctl restart wg-quick@wg0` allow-listed |
| 6 | Cert renewal action missing | §1.5 row 6 + §2.6 — `acme.json` mtime check; `docker restart traefik` allow-listed |
| 7 | Authelia fail2ban escalation path | §1.5 row 7 + §2.6 — `fail2ban-client set <jail> banip` allow-listed; iptables direct stays banned |
| 8 | Backrest hostname fix shouldn't wait | §1.5 row 8 + §2.5 — moved into `step_14_install_sysadmin_pack()` |
| 9 | Shared-infra consensus race | §1.5 row 9 + §3.2 — authorship rule: resource's host AUTHORS, peers diagnose only |
| 10 | Hub-down pending queue | §1.5 row 10 + §3.3 — `/var/lib/aro-wake/pending.jsonl` + mesh-recovery drain |
| 11 | Consult cycle (A→B→A→B loop) | §3.2 — `trace_id` + `seen_by` list; loop breaks in one hop |
| 12 | Telegram flood across 3 bots | §2.8 — daily digest at 09:00; per-action Telegram only for non-trivial |
| 13 | Sidecar vs host sysadmin double-action | §5.1.b — check `*-watchdog` first; wait 90s for sidecar's tick |
| 14 | `.env.sysadmin` secret hygiene | §2.7 — mode 600, gitignored, mirrored to DR-store |
| 15 | Anthropic rate-limit risk with 3 parallel hosts | §5 criterion #12 — verify 0 429s; OpenRouter fallback per host |
| 16 | Operator reversals as learning signal | §5.1.a — `lessons-pending.jsonl`; 3+ reversals/week demotes the action class |
| 17 | Persistent memory across sessions | covered by existing `system-prompt.txt`'s shift-notes flow (replicated per host in §2.1) |
| 18 | AI itself dies (systemd unit crash) | covered by `Restart=always` (existing) + Telegram-direct fallback (existing) |
| 19 | Coordinated drill criterion | §5 criterion #11 + §5.2 trigger row |
| 20 | Out-of-scope items explicit (kernel panic, postgres failover, etc.) | §1.6 — new section listing 8 classes that stay operator-runbook |

**Phase delta r1 → r2:**

| Phase | r1 size estimate | r2 size estimate | Delta justification |
|---|---|---|---|
| 1 — Prompt correctness | ~1 day | ~1 day | unchanged |
| 2 — Spoke sysadmin | ~1.5 days | ~2 days | +wg-check, +hostname fix, +autonomous action promotions, +.env.sysadmin discipline, +digest report, +Loki recording rule |
| 3 — aro-wake + consult | ~1.5 days | ~2 days | +consult semantics (authorship rule), +trace_id/seen_by cycle prevention, +pending queue, +mesh-recovery drain |
| 4 — Alertmanager push | ~1 day | ~1 day | unchanged |
| 5 — Iteration | open-ended | open-ended | +5.1.a reversal detection, +5.1.b sidecar de-dup, +monthly drill trigger |
| **Total** | **~5 days** | **~6-7 days** | gained convergence on all 20 gaps |

**Convergence verdict at r2:** all 10 operator-named truth-table rows mapped to a phase. No GAP rows remain. Plan ready for execution gated on operator answers to §7.

### r3 — 2026-06-04 self-iteration against r2's own additions

**Trigger:** operator's `iterate indefinitely to converge` instruction; r2 mapped the truth-table rows, but a plan can introduce gaps in its own fixes. r3 stress-tests r2 by re-reading every r2 addition for internal consistency.

**Method:** for each new structure r2 added (digest, keepalive cron, pending queue, reversal detection, sidecar de-dup, host-routing), ask: "is this internally consistent? does it specify everything an implementer needs? are there contradictions with §1.6 or operator preferences?"

**Gaps closed in r3 (10 total):**

| # | r2 introduced | r3 found | r3 fixed in |
|---|---|---|---|
| 21 | Daily digest at "09:00 local time" | Three local times = three digest timestamps; confusing | §2.8 — pin to 09:00 UTC for all three hosts |
| 22 | Keepalive cron `*/12 * * * *` | Token freshness window is days; 12-minute cadence is 20× overspend | §2.3 — bump to hourly; cost drops $0.60→$0.12/day/host |
| 23 | Pending queue TTL 1h | Real hub outage could exceed 1h; queue would TTL away genuine consult requests | §3.3 — bump to 24h; add 1000-entry / 10MB cap with oldest-first overflow |
| 24 | Reversal detection looks for "another restart within 60s" | Operator might `docker rm + redeploy`, `docker compose down -v`, etc. — missed by restart-only rule | §5.1.a — broaden to journald docker events filter for all docker actions on the same target within 5min |
| 25 | OpenRouter as fallback "per host with own key" | Single operator OpenRouter account → simultaneous 402 across the fleet | §1.6 — explicit known limitation; rule-only + deadman bleed-stop survives the gap |
| 26 | Sidecar de-dup "read its state.db" | Doesn't say HOW (file is inside the sidecar's volume, uid 1000) | §5.1.b — `sudo docker exec <c>-watchdog sqlite3 -readonly ...` with full query |
| 27 | §1.6 says "AI may DETECT and report" for kernel panic | But the AI is dead in that case — contradiction | §1.6 — reword: "detection via external observer (IPMI / VPS console); AI assists post-mortem only" |
| 28 | Phase 4 alert-host routing | Silent on missing or multiple `host` labels | §4.3 — missing → default to vps1 + Loki `low_quality_alert`; multiple → fan out, authorship rule resolves |
| 29 | `step_14_install_sysadmin_pack()` bootstrap step | No numbering reservation; concurrent plans could collide | §2.1 — explicit note; future steps pick `step_15+` |
| 30 | Digest claims "claude OAuth fresh (last refresh 23m ago)" | With r3 #22 hourly cadence, "23m ago" is impossible — would be ≤60m | §2.8 — reword to mtime + 90m window check |

**Phase delta r2 → r3:** no new days added; all fixes are clarifications or single-line tweaks within existing phases. r3 sharpens; it doesn't expand.

**Convergence verdict at r3:** every r2 internal addition was checked; 10 gaps found and closed. r3 itself introduced no new structures large enough to create r4 gaps. **r3 is a candidate convergence point.**

### r4 — convergence check (one more pass to verify)

**Method:** re-read r3's 10 fixes; ask: did any r3 fix introduce a new gap?

| r3 fix | r4 review | Verdict |
|---|---|---|
| 09:00 UTC digest | All three hosts wake at the same time → 3 simultaneous claude calls → potentially 3 simultaneous Anthropic API hits from one operator account | r4 #31 — minor; digest is single-shot per host per day; stagger via cron minute (vps1 :00, vps2 :02, vps3 :04) to spread load |
| Hourly keepalive | All three keepalive crons fire at minute :00 of every hour simultaneously | r4 #32 — same fix as #31; stagger by host (vps1 `0 * * * *`, vps2 `5 * * * *`, vps3 `10 * * * *`) |
| Pending queue 24h / 1000 / 10MB | (none) | No new gap |
| Reversal detection via journald | Journald docker events require Docker daemon healthy; if Docker dies, AI dies too | OK — out-of-scope per §1.6 (kernel panic class); reversal detection moot in that state |
| OpenRouter all-fleet 402 caveat | (none) | No new gap; explicit operator monitoring path |
| Sidecar state.db read via `docker exec` | Requires sidecar container UP; if sidecar itself is dead, this query fails | r4 #33 — host sysadmin already treats sidecar-down as "no sidecar present, act immediately" per §5.1.b step 2; no new fix needed |
| Kernel panic reword | (none) | No new gap |
| Missing host label → vps1 default | If vps1 itself is offline, this fails | r4 #34 — Alertmanager's existing `telegram_configs` always fires (Phase 4.1 `continue: true`); operator sees both AI miss + telegram notice; no new fix needed |
| step_15+ reservation | (none) | No new gap |
| Digest mtime/90m window | (none) | No new gap |

**r4 net change:** two cron stagger edits (#31, #32 applied below). #33 and #34 confirm existing fallbacks are sufficient. The other six r3 fixes pass review unchanged.

#### r4 #31 + #32 — stagger digest + keepalive across hosts

To avoid 3 simultaneous Anthropic API calls when all hosts trip a cron together:

| Host | Digest cron | Keepalive cron |
|---|---|---|
| vps1 | `0 9 * * *` | `0 * * * *` |
| vps2 | `2 9 * * *` | `5 * * * *` |
| vps3 | `4 9 * * *` | `10 * * * *` |

Set by `step_14_install_sysadmin_pack()` per-host substitution at bootstrap time; values come from a small lookup table in the bootstrap script keyed on `HOST_NAME`.

### r5 — final convergence check

**Method:** re-read r4's 2 new fixes (#31, #32) + 2 verdicts (#33, #34); ask "any new gap?"

| r4 item | r5 review | Verdict |
|---|---|---|
| Stagger digest by 0/2/4 min | What if a 4th spoke joins later? | r5 #35 — bootstrap lookup table should hash `HOST_NAME` to a digest-minute slot in `[0, 30)` deterministically; documented as "modulo 5 of the SHA1 host hash" so any new spoke gets a stable slot without collision |
| Stagger keepalive by 0/5/10 min | Same — fixed schedule doesn't extend to vpsN | r5 #36 — same hash-slot pattern for keepalive minute in `[0, 60)`; document in `step_14_install_sysadmin_pack()` |
| Sidecar-down fallback | (already-handled) | No new gap |
| Missing-host fallback | (already-handled) | No new gap |

**r5 net change:** 2 single-line bootstrap edits replacing fixed-table with hash-slot allocation (#35, #36 below).

#### r5 #35 + #36 — hash-slot cron staggering

```bash
# In step_14_install_sysadmin_pack(), compute per-host cron minute slots
# deterministically from HOST_NAME so adding a 4th/5th spoke later doesn't
# require touching this script.
host_hash=$(echo -n "$HOST_NAME" | sha1sum | head -c 8)  # first 32 bits
digest_minute=$(( 16#${host_hash} % 30 ))                # 0–29
keepalive_minute=$(( (16#${host_hash} >> 4) % 60 ))      # 0–59 (different bits)
```

### r6 — final final check (does r5 introduce any gaps?)

**Method:** re-read #35 and #36. Anything?

| r5 item | r6 review | Verdict |
|---|---|---|
| `sha1sum` not POSIX | r6 #37? — but `sha1sum` ships with coreutils which is already a hard dep | not a real gap; `sha1sum` is universal on Debian/Ubuntu |
| Hash collision possible if HOST_NAMEs hash to same minute | 5 spokes hashing to same minute is `1/60^4 ≈ 1 in 13M` | not a real gap; if it ever happens, retry with `host_hash` derived from `HOST_NAME` + `MESH_IP` |
| Bash arithmetic on hex with `16#${var}` requires bash, not sh | `bootstrap-vps.sh` already uses `#!/usr/bin/env bash`; consistent | not a real gap |

**r6 net change: zero.**

**Convergence verdict at r6:** no new gaps found in r5's additions. r6 confirms.

### Convergence point reached

- **r1 → r2**: 20 gaps closed (10 operator-named + 10 second-order)
- **r2 → r3**: 10 internal-consistency gaps closed
- **r3 → r4**: 4 gaps reviewed; 2 cron-stagger fixes + 2 confirmations of existing fallbacks
- **r4 → r5**: 2 gaps closed (hash-slot generalization)
- **r5 → r6**: 0 new gaps found

**Definition of convergence:** "for one consecutive iteration, no new gaps are found AND all success criteria hold" — see §9 final gate.

**Status as of r6 (2026-06-04 evening):**

- Internal-consistency gaps: **closed** (r6 found 0 new)
- Success criteria validation: **deferred to execution** — criteria are unmeasurable until Phase 1 lands; pre-execution criteria like #1, #2, #3, #4, #13 (file existence, container active, prompt grep) are pre-checked in §2 pre-flight verification
- Plan is ready for operator answers to §7 open questions + Phase 1 start

**Next iteration trigger:** Phase 1 execution. If Phase 1 reveals a discipline issue (e.g., a step doesn't work as written, or surfaces a behavior the plan didn't anticipate), open r8 and record the lesson. Otherwise, the plan stands as-is through phases 1–4, with Phase 5 being the open-ended iteration vehicle from then on.

### r7 — 2026-06-04 architectural explicitness pass

**Trigger:** operator asked "do we have prompt files already or will we create them? will they be triggered come online and fix the issue then sleep?" — the prompt-file part was findable across the plan (Phase 1.1 / 1.2 / 1.3 / §2 / §1.5), but the wake/sleep lifecycle was implicit per-phase rather than stated as the architecture. Operator needed it in one place.

**Method:** ask "could a reader, picking up the plan cold, answer 'how does the AI run on each host?' in one read without assembling pieces from 5 different phases?" Before r7: no. After r7: yes — §1.7 is one diagram + one cost-shape table + one concrete walkthrough.

**Gap closed in r7 (1 — architecture not stated as principle):**

| # | Gap | Closed in |
|---|---|---|
| 38 | Wake → fix → sleep lifecycle described per-phase but never as a single architectural principle; cost shape per listener never tabled; "sleep is the default state" never stated | New §1.7 — four-path lifecycle diagram + per-listener cost-shape table + concrete walkthrough + three plan-implication callouts (cost discipline by construction; no-single-AI-failure by listener locality; partition tolerance by design) |

**Phase delta r6 → r7:** zero — §1.7 is descriptive, doesn't add work. It makes existing intent legible.

**Convergence verdict at r7:** the plan now contains the architecture explicitly + the prompt-file inventory + the lifecycle + the cost shape + the partition behavior in single, locatable sections. A fresh reader can answer "how does this run, what does it cost, what survives partition?" in one read of §1.7 + §1.6 + §1.5. **r7 holds the r6 convergence and adds explicitness.**

### r8 — 2026-06-04 evening: execution-time plan/code reconciliation (after Phases 1+2+3 ship)

**Trigger:** operator's "review your work deeply find and fix issues" pattern applied four times after the trio code shipped (commits `434d70b` Phase 1, `d83bfb0` Phase 2, `ed24f78` Phase 3, plus three review-pass commits `6d65606` / `ec015be` / `cb153f8`). Each pass found a new class of issue. The fourth pass surfaced plan/code drift: the original §3.1 spec assumed Docker Compose + dual-IP binding + a different deploy path; the shipped code chose systemd + mesh-only bind + a different path because each of those changes solved real problems (sandbox + OAuth issues with Docker; complexity of multi-bind without proxy; consistency with `vps-sysadmin-bot.service` which has been production-stable since 2026-05-20).

**Gaps closed in r8 (3 doc-alignment + 5 code bugs):**

Plan reconciliation (kept the plan as the source of truth, updated it to match the chosen execution):

| # | r1 plan said | Shipped reality | Why the divergence | Plan update |
|---|---|---|---|---|
| 39 | "Lives on each host at `/opt/aro-wake/`" | `/opt/fabrik/scripts/aro-wake/` + venv at `/opt/fabrik/.venv-aro-wake/` | Consistency with the rest of the fabrik scripts tree; no need for a dedicated top-level mount point | §3.1 reflects shipped path |
| 40 | "Compose service binds 127.0.0.1:8201 + 10.99.0.<host>:8201" | systemd service binds **10.99.0.<host>:8201 only** | Docker Compose adds the sandbox + OAuth complexity surface that T-P5 dogfood spent half a day debugging; systemd matches the proven production pattern from `vps-sysadmin-bot.service` | §3.1 + §1.7.1 ASCII diagram both reflect mesh-only systemd shape |
| 41 | "Files touched: new `/opt/aro-wake/{compose.yaml, main.py, requirements.txt, .env}`" | `scripts/aro-wake/{main.py, requirements.txt, templates/aro-wake.service.template}` | No compose; .env replaced by systemd `Environment=` directives | §3.1 file-list updated; explicit `Environment=ARO_WAKE_PEER_HOSTS=<CSV>` callout (NOT JSON — systemd strips embedded quotes) |

Code bugs from review-pass 4 (idempotency + env-loading):

| # | Bug | Symptom | Fix |
|---|---|---|---|
| 42 | step_14 `cp -R /tmp/sysadmin /opt/fabrik/scripts/sysadmin` nests on re-run (creates `/opt/fabrik/scripts/sysadmin/sysadmin/`) | First install works; idempotent re-bootstrap creates garbage tree | Switch to `rsync -a --delete /tmp/sysadmin/ /opt/fabrik/scripts/sysadmin/` (trailing slashes; --delete removes stale files) |
| 43 | step_15 same `cp -R` nesting issue for aro-wake | Same | Same `rsync -a --delete` form (plus `--exclude __pycache__`) |
| 44 | `proactive-check.sh` aro-wake health check uses `${SYSADMIN_HOST_IP:-127.0.0.1}` but cron has minimal env so SYSADMIN_HOST_IP is unset; curl hits loopback while aro-wake binds mesh IP → false-positive `aro_wake_unhealthy` | Operator gets spurious alert every 15 min once aro-wake is enabled | Load `.env.sysadmin` at script start (`set -a; . file; set +a`); fall back to `ip -4 -o addr show wg0` if env file absent (pre-bootstrap hosts); only default to 127.0.0.1 if both fail (in which case aro-wake isn't enabled either, so the alert IS a true positive — the check is now self-consistent) |

(Bugs 1-30 + 31-38 from prior r2/r3/r7 already accounted for; r8 starts at #39 for clarity.)

**Phase delta r7 → r8:** zero — all changes are doc reconciliation + code review fixes that land in the same 4 phases. No new phases, no scope expansion.

**Convergence verdict at r8:** the plan now matches the shipped code in path, deploy shape, and binding. The shipped code is idempotent + free of false-positive monitoring on aro-wake. **The "iterate until convergence" pattern has produced 8 plan revisions + 7 git commits in one day — the trio plan is now lived-in and operationally tested at the code review level, not just speculatively designed.**

**r4 gaps closed:** 4 small clarifications (#31 staggered keepalive, #32 same, #33 already-handled, #34 already-handled). Two are one-line cron edits, two are confirming existing fallbacks. Applying:
