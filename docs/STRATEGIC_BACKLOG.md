# Strategic Backlog

**Last Updated:** 2026-06-07

> **Purpose:** Track work that's been deliberately deferred from active development — not because it's unimportant, but because it's not yet ready for a focus window, blocked on operator action, or correctly waiting for a triggering incident.

Generated from the end-of-day plan-state on 2026-06-07 after the trio Phase 5.1.a ship. Each item below is something we explicitly DIDN'T do this session and explicitly DIDN'T commit to today — and why.

---

## Now — Ready for Focus Window

| Effort | Item | Why Priority | Ready When |
| :--- | :--- | :--- | :--- |
| **M** | **DR drill on a throwaway VPS** — run [`scripts/bootstrap/bootstrap-hub.sh`](../scripts/bootstrap/bootstrap-hub.sh) against a fresh GreenCloudVPS instance, measure wall-clock against the ≤90 min target in [`vps-hub-rebuild.md`](infrastructure/vps-hub-rebuild.md). Same for spoke via [`bootstrap-vps.sh`](../scripts/bootstrap/bootstrap-vps.sh) (≤30 min target). The drill ALSO validates the 4 spoke-dep installs baked into bootstrap on 2026-06-07 (Node.js 22 + Claude CLI, `python3-venv` + `python3-pip`, `python-telegram-bot==22.7`, `/opt/fabrik/` ownership reset). | "Scripted end-to-end" today is target-not-measured; until drilled, the DR-in-hours claim is aspirational. | Operator buys a $5 throwaway VPS (BudgetKVMCUK-3 in UK or similar) and has 3-4 hours uninterrupted. |
| **S** | **Pull Gatus configs into source control** under `/opt/fabrik/configs/gatus/apps/`. Today (2026-06-07) `/opt/monitoring/configs/prometheus/`, `/opt/monitoring/configs/alertmanager/`, `/opt/monitoring/configs/loki/` are all source-controlled under `/opt/fabrik/configs/` — but `/opt/monitoring/configs/gatus/` is NOT. The `aro-wake.yaml` Gatus config I shipped today lives ONLY on vps1; if vps1 disk dies the file is in the Backrest snapshot but not in git. Pattern: copy `gatus/` to `/opt/fabrik/configs/gatus/`, add it to the monitoring-stack deploy flow, deprecate hand-edits on vps1. | Closes the asymmetry — every other monitoring config is in git, gatus shouldn't be the exception. | 1-2 hour block; no operator dependency. |

---

## Later

- [ ] **propose/ack peer-protocol verbs** (trio plan Phase 5, deferred): Today the cross-host destructive bridge is operator Telegram `reply "go"`. Build the `propose`/`ack` HTTP verbs in aro-wake only when a real incident proves the bridge is insufficient — don't speculate. The "real cross-host destructive action" use case hasn't shown up yet. Blocked by: first real incident where consult-only + operator-bridge is provably too slow.
- [ ] **Apprise pre-route through aro-wake** (trio plan Phase 5, deferred): Gatus / GlitchTip / Backrest webhooks currently go straight to Telegram. AI never sees them. Wire Apprise to aro-wake first with `continue: true` semantics like Alertmanager Phase 4. Blocked by: first real incident proving Alertmanager-only triage missed something.
- [ ] **Loki ruler with starting rule set** (trio plan Phase 5, deferred): Log-pattern alerts not generated at all today. Sidecars catch their own container's logs; cross-container log signals on vps1 aren't observed. Blocked by: first incident that log-pattern-rule would have caught earlier than container-state probe.
- [ ] **Grafana `aro-wake` dashboard**: 8 SLI metrics + 2 alert rules live on full fleet since 2026-06-06. PromQL + Telegram alerts cover real operator needs today. Build a dashboard only when ad-hoc PromQL queries become tedious. Blocked by: operator running the same PromQL recipe 3+ times in a week.
- [ ] **"Repeated-flag-no-action" pattern detector** (complement to `detect_reversals.py`): The 2026-06-07 netdata flood was 24 benign "anomaly detected" wakes with no AI action taken — `detect_reversals.py` correctly doesn't fire (no AI action to reverse), but a different correlator could flag "AI flagged X N times in a row, operator never acted → AI is wrong OR alert is misconfigured". Same `lessons-pending.jsonl` output stream, different correlator. Blocked by: second occurrence of a similar pattern that's not the netdata case (which is now fixed).
- [ ] **Bake the new operator-reversal cron line into the live cron-template DEPLOY path for existing hosts**: Today I appended to `/etc/cron.d/vps-sysadmin` on all 3 hosts manually and also updated [`sysadmin-cron.template`](../scripts/bootstrap/templates/sysadmin-cron.template) for future spokes. There's no `fabrik`-level redeploy step that re-renders the cron template on existing hosts after a template change. Blocked by: another cron template change that needs to propagate.
- [ ] **Reset `/opt/fabrik/` ownership on vps2 + vps3 from `root:root` to `ozgur:ozgur`** (cosmetic): Today's bootstrap-vps.sh change covers fresh installs going forward, but the live state on vps2/vps3 still has `/opt/fabrik` as `root:root`. Nothing is breaking — the venv was already created earlier — but the asymmetry would be discovered during the first real maintenance touch. Blocked by: nothing; one-liner SSH per spoke, but not worth interrupting steady state for.
- [ ] **Bot token rotation** for `SysAdminVPS2` (`8838110344:...`) + `SysAdminVPS3` (`8674270904:...`): Operator declared this private chat 2026-06-07 and declined rotation. Re-evaluate if the chat scope ever changes. Blocked by: operator decision.

---

## Context

- ⚠️ **Stale Prometheus scrape targets cause Telegram floods via the Phase 4 wire**. The netdata flood on 2026-06-06→07 ran for ~12 hours (24 messages every 30 min) because a `netdata:19999` scrape target was left in `prometheus.yml` after the container was retired 2026-05-30. Pattern: removing a service from compose MUST also remove its scrape job from `prometheus.yml`. Captured in commit `f5c6e48`. Should make this a registrar invariant check long-term.
- 💡 **Cross-mesh container→host scrape pattern works** via docker MASQUERADE rewriting the source IP to vps1's wg0 IP (`10.99.0.1`), which the spokes' existing `from 10.99.0.0/24 to any port <port>` UFW rules permit. Documented in [`prometheus-app-metrics-setup.md`](infrastructure/prometheus-app-metrics-setup.md) § aro-wake SLI metrics. Reusable for any future host-service that needs Prometheus scrape coverage from spokes (no firewall changes needed beyond the existing mesh allow).
- 💡 **Loop-guard counters are in-memory by design** — restart = reset = safe default. `rate()` / `increase()` in PromQL handle this via the `_created` timestamps that prometheus_client emits. Don't migrate to persistent counters; the reset semantics are correct.
- 💡 **Operator-reversal detector deduplicates by `(ai_source, ai_ts, operator_ts)` tuple** in [`detect_reversals.py`](../scripts/sysadmin/detect_reversals.py). Re-running 2× after a match produces 0 new entries. If we ever extend the schema, preserve this idempotency property.
- ⚠️ **sqlite3 `-csv` mode quotes timestamp fields with embedded space**, breaking `strptime` unless you strip quotes. The default `-list` (pipe-separator) mode works cleanly for our 3 simple columns. Documented in `detect_reversals.py` `collect_sidecar_actions()`.
- 💡 **Trio loop guards (4 layers) are sufficient for `consult`-only protocol AND future `propose`/`ack` Phase 5 work**. Same handler, same guards. No protocol version bump needed when Phase 5 ships propose/ack. Documented in [`scripts/sysadmin/peer-protocol.md`](../scripts/sysadmin/peer-protocol.md) §3.2.1.
- 💡 **Watchdog sidecar action log (`state.db`) is the canonical source for "AI took an action"** today — `sysadmin-actions.jsonl` is mostly diagnose-only wakes for now. When host-AI gains explicit action verbs (e.g., autonomous container restart from proactive-check), add the `action_name` + `target` fields to the jsonl entry so `detect_reversals.py::collect_host_sysadmin_actions()` starts firing.
- ⚠️ **Gatus configs live ONLY on vps1** (not in this repo) — see "Now" row above. If you edit an existing endpoint and want it source-controlled, you need to also pull the file into the repo manually OR do the gatus-source-control work first.

---

## Activation

Items move to active development when:

1. **Focus window opens**: A block of 3+ hours of uninterrupted time is identified — applies to "Now" tier specifically (DR drill needs 3-4 hours, Gatus migration needs 1-2 hours).
2. **Triggering incident**: A "deferred until real case" item gets a real case (propose/ack, Apprise pre-route, Loki ruler, repeated-flag detector).
3. **Repeated friction**: The same operational pain hits 3+ times in a week — e.g., the same PromQL query becomes "type this AGAIN" → Grafana dashboard tier.
4. **Resource availability**: External tools / budgets / operator availability — DR drill needs a throwaway VPS purchase.

The hardest discipline here is the second one — resisting the urge to build "propose/ack" speculatively because it sounds important. The Phase 5 plan explicitly says: each new incident teaches; capability expands from incidents, not architecture.
