# Plan: `fabrik vultr` — on-demand VPS provisioning (permanent + disposable)

**Created:** 2026-06-07
**Status:** Planned — not started
**Priority:** Now (per `docs/STRATEGIC_BACKLOG.md` Now tier)
**Trigger:** 2026-06-07 DR drill burned 10 min on operator-discipline traps (root@ re-runs, fail2ban ban, etc.) that a thin Vultr API wrapper would have eliminated by running the whole drill end-to-end as a single command.

---

## Why

Today, provisioning a VPS for either purpose requires manual clicking through Vultr's dashboard, copying the IP, editing `~/.ssh/config`, and remembering operator discipline (root@ vs ozgur@, --skip-mesh + --skip-dns, fail2ban thresholds). Every step is a place to introduce error. We hit two of them in the first drill.

A `fabrik vultr` subcommand with two modes — **permanent** (becomes a real fleet member) and **disposable** (a throwaway for drills/experiments) — collapses the whole flow into one well-typed call with state tracking + auto-cleanup + cost reporting.

### Two operator workflows this enables

| Workflow | Today | After this plan |
|---|---|---|
| **Add a 4th permanent spoke** (`vps4` for a future region) | Dashboard click → SSH key paste → Wait for boot → Update ~/.ssh/config → Run bootstrap-vps.sh → Manual mesh peer registration → Manual DNS → Manual Backrest setup | `fabrik vultr provision vps4 --region lhr` — done in 8-10 min, all state recorded |
| **DR drill for spoke rebuild** | Dashboard click → SSH key → ip copy → bootstrap-vps.sh --skip-mesh --skip-dns → run end-state check → dashboard destroy | `fabrik vultr drill spoke` — 5-15 min, auto-destroys, writes drill report |

---

## Modes

### Mode A — Permanent (`fabrik vultr provision <name>`)

Becomes a real fleet member after provisioning. Joins the trio sysadmin set (`vps4`+, future spokes). Auto-registered on vps1's wg0, DNS created, Backrest configured, Prometheus scrape target added.

**Pre-conditions**: operator confirms intent, fleet has capacity, name doesn't collide, region picked.

**Post-conditions**: spoke is bootstrap-vps.sh complete + registered + observable in Prometheus/Gatus + adds to strategic-trio peer list.

**Cost**: ongoing — operator pays monthly for the lifetime of the spoke.

### Mode B — Disposable (`fabrik vultr drill <kind>`)

Throwaway VPS for DR drills, experiments, one-off validations. Auto-destroyed at end (success OR failure). Never registered on production mesh/DNS. Drill report written to `logs/dr-drill-history.jsonl`.

**Pre-conditions**: operator picks drill kind (`spoke`, `hub`, or `bare`).

**Post-conditions**: zero residue on production fleet, drill report saved, droplet destroyed, billing stopped.

**Cost**: ~$0.02-0.30 per drill depending on duration + plan.

---

## Scope

### In scope

- Vultr API v2 integration (auth, instance CRUD, snapshot, billing)
- Two modes: permanent, disposable
- `fabrik vultr` CLI subcommand with discoverable subcommands
- State store: `data/vultr-instances.json` — tracks active permanent instances, recent disposable instances (last 30 days)
- Drill report writer: `logs/dr-drill-history.jsonl` — every drill emits one line with start_ts, end_ts, wall_clock_seconds, plan, region, success, step_durations, cost_estimate
- Cost guardrails: per-call budget cap, monthly fleet-wide budget cap, auto-destroy timer for disposable instances
- Integration with existing `bootstrap-vps.sh`, `bootstrap-hub.sh`, `bootstrap-spoke-restore.sh`
- Cleanup-on-failure discipline: if any post-provision step fails, the disposable instance is still destroyed (no orphan droplets racking up cost)

### Out of scope

- Other providers (DigitalOcean, Hetzner, AWS) — Vultr only this iteration
- Multi-region failover orchestration
- Vultr GPU/Bare Metal instances
- Block storage (volumes), VPC networks, reserved IPs — basic compute only
- Cost forecasting / monthly budget alerting — minimal cost-tracking only
- Managed databases via Vultr — we use our own postgres-main

---

## Vultr API surface we'll use

Vultr REST API v2 documentation: <https://www.vultr.com/api/>

| Endpoint | Method | Purpose |
|---|---|---|
| `/v2/instances` | POST | Create new instance |
| `/v2/instances/<id>` | GET | Get instance state |
| `/v2/instances/<id>` | DELETE | Destroy instance |
| `/v2/instances/<id>/reboot` | POST | Reboot (clears fail2ban state) |
| `/v2/instances` | GET | List all instances (state reconciliation) |
| `/v2/ssh-keys` | GET | List SSH keys (find key ID by fingerprint) |
| `/v2/regions` | GET | List available regions |
| `/v2/plans` | GET | List available plans + pricing |
| `/v2/os` | GET | List available OS images (need Ubuntu 24.04 LTS ID) |
| `/v2/account` | GET | Verify auth, get account balance |

**Auth**: Bearer token in `Authorization` header. Token stored in `/opt/fabrik/.env.sysadmin` as `VULTR_API_KEY` (mode 600).

**Rate limits**: Vultr documents none for small-scale operations. No retry-with-backoff complexity needed.

---

## CLI design

```bash
# Mode A — permanent
fabrik vultr provision vps4 \
  --region lhr \
  --plan vc2-2c-4gb \
  --label "Spoke deployed 2026-06-12"
  # → creates instance, runs bootstrap-vps.sh, registers on vps1's wg0, creates DNS,
  #   adds to /opt/fabrik/data/vultr-instances.json, prints final state contract.

fabrik vultr provision vps4 --dry-run
  # → prints what would happen; touches nothing.

# Mode B — disposable drill
fabrik vultr drill spoke
  # → creates 2GB droplet in lax, runs --skip-mesh --skip-dns bootstrap-vps.sh as vps4,
  #   verifies end-state contract, destroys droplet, writes drill report.

fabrik vultr drill spoke --keep-on-failure
  # → if drill fails, leave the droplet running so operator can investigate.
  # Operator must manually `fabrik vultr destroy <id>` when done.

fabrik vultr drill hub
  # → 8GB droplet, runs bootstrap-hub.sh against a fake snapshot, validates,
  #   destroys. ~90 min wall-clock target.

fabrik vultr drill bare
  # → smallest cheapest instance, only validates Vultr+SSH+stock-Ubuntu wiring.
  # ~2 min. The smoke test for the smoke tests.

# Inspection
fabrik vultr list
  # → all our Vultr instances + state from /opt/fabrik/data/vultr-instances.json

fabrik vultr status <name>
  # → details of one instance (Vultr state + our state + bootstrap state if known)

fabrik vultr destroy <name>
  # → destroy by NAME (not ID — operator-friendly). Confirms before destroying permanent.

fabrik vultr cleanup
  # → finds disposable instances older than 4h that weren't auto-destroyed (bug recovery),
  #   destroys them, writes a cost report.

# Cost
fabrik vultr cost
  # → query Vultr billing API; print this month's usage + per-instance breakdown.

fabrik vultr drill-history
  # → tail of logs/dr-drill-history.jsonl with wall-clock trend.
```

---

## State management

### `/opt/fabrik/data/vultr-instances.json`

Single source of truth for instances Fabrik provisioned via this command. Schema:

```json
{
  "schema_version": 1,
  "last_reconciled": "2026-06-07T22:30:00Z",
  "instances": {
    "vps4": {
      "vultr_id": "f8e109a0-5a8f-4448-8d3e-737dd4831eb4",
      "mode": "permanent",
      "ip": "203.0.113.45",
      "region": "lhr",
      "plan": "vc2-2c-4gb",
      "created_at": "2026-06-12T14:32:00Z",
      "bootstrap_completed_at": "2026-06-12T14:40:12Z",
      "mesh_ip": "10.99.0.4",
      "spoke_name": "vps4"
    },
    "dr-drill-spoke-2026-06-07-1856": {
      "vultr_id": "...",
      "mode": "disposable",
      "ip": "149.28.70.237",
      "region": "lax",
      "plan": "vc2-1c-2gb",
      "created_at": "2026-06-07T18:56:53Z",
      "destroy_after": "2026-06-07T22:56:53Z",
      "drill_kind": "spoke",
      "destroyed_at": null
    }
  }
}
```

Disposable instances stay in the file with `destroyed_at` populated for 30 days (audit trail) then garbage-collected.

### `/opt/fabrik/logs/dr-drill-history.jsonl`

One line per drill (success OR failure). Schema:

```json
{
  "ts": 1780827614,
  "drill_kind": "spoke",
  "vultr_id": "...",
  "wall_clock_seconds": 295,
  "plan": "vc2-1c-2gb",
  "region": "lax",
  "success": true,
  "cost_estimate_usd": 0.02,
  "step_durations": {
    "provision_wait": 32,
    "ssh_ready_wait": 8,
    "bootstrap_total": 198,
    "end_state_verify": 12,
    "destroy_wait": 4
  },
  "end_state_contract_passed": ["sshd", "ufw", "docker", "fabrik-network", "aro-wake-service", "vps-sysadmin-bot-service"],
  "end_state_contract_failed": []
}
```

Operator-side analysis: `jq` over the history file → wall-clock trend, success rate, average cost per drill.

---

## Implementation phases

Iterative — each phase ships independently and is useful on its own.

### Phase 1 — Vultr API client (Python, ~150 lines)

`/opt/fabrik/src/fabrik/drivers/vultr.py`:

```python
class VultrClient:
    def __init__(self, api_key: str): ...
    def list_instances(self) -> list[dict]: ...
    def get_instance(self, instance_id: str) -> dict: ...
    def create_instance(self, region: str, plan: str, os_id: int,
                        ssh_key_ids: list[str], hostname: str,
                        label: str = "", tags: list[str] = None) -> dict: ...
    def destroy_instance(self, instance_id: str) -> None: ...
    def reboot_instance(self, instance_id: str) -> None: ...
    def wait_for_active(self, instance_id: str, timeout: int = 120) -> dict: ...
    def list_ssh_keys(self) -> list[dict]: ...
    def get_billing(self) -> dict: ...
```

Defensive design: 10s HTTP timeout, 3-attempt retry only on 5xx (not on 4xx — those are our bug, not transient), clear error messages distinguishing "auth failed" from "instance not found" from "billing failed".

Unit tests: mock `httpx` responses; verify schema, error handling, retry logic.

### Phase 2 — State store + reconciliation (Python, ~100 lines)

`/opt/fabrik/src/fabrik/orchestrator/vultr_state.py`:

```python
def load_state() -> VultrState
def save_state(state: VultrState) -> None
def reconcile(client: VultrClient, state: VultrState) -> ReconcileReport
    # Compare local state to Vultr's view of the world.
    # Flag: instances in state.json but not in Vultr (deleted out-of-band)
    # Flag: instances in Vultr but not in state.json (created out-of-band — maybe a manual UI provision)
```

Manual reconciliation command: `fabrik vultr reconcile` — prints the report, asks operator how to resolve drift.

### Phase 3 — `fabrik vultr drill` (disposable mode first — lower risk)

Skip the permanent flow until disposable is rock-solid.

```python
# fabrik vultr drill spoke
1. Validate VULTR_API_KEY + VULTR_SSHKEY_ID env vars set
2. Validate /opt/fabrik/data/vultr-instances.json writable
3. Generate disposable hostname: dr-drill-spoke-<UTC-timestamp>
4. Create instance via VultrClient
5. Wait for active state (poll every 5s, timeout 120s)
6. Wait for SSH (poll ssh root@<ip> 'echo ok' every 3s, timeout 60s)
7. Record start of drill timer
8. Run bootstrap-vps.sh --skip-mesh --skip-dns root@<ip> vps4 (capture output to /tmp/drill-<id>.log)
9. After step_01 completes (detect by parsing log for "step 01 done"), switch SSH user to ozgur@<ip>
10. Continue tailing log; wait for bootstrap completion or timeout (15 min)
11. Verify end-state contract: ssh ozgur@<ip> per the 7-check list from vps-spoke-rebuild.md
12. Record end of drill timer
13. ALWAYS destroy instance (try/finally) — no orphans even on failure
14. Write drill report to logs/dr-drill-history.jsonl
15. Print summary: wall-clock, contract pass/fail, cost estimate
```

End-state contract for spoke drill (subset of vps-spoke-rebuild.md, the parts that don't require mesh):

1. `sshd_config` hardened: PermitRootLogin no, PasswordAuthentication no
2. UFW active with rules: 22/tcp, 80/tcp, 443/tcp, 51820/udp, 10.0.0.0/8 → 8201, 10.99.0.0/24 → 8201
3. Docker installed + running + `fabrik` network exists
4. `/opt/fabrik/` ownership = ozgur:ozgur
5. Node.js 22 + claude binary on PATH
6. `python-telegram-bot==22.7` importable in system Python
7. `aro-wake.service` exists (whether running depends on env config)
8. `vps-sysadmin-bot.service` exists

### Phase 4 — `fabrik vultr drill hub`

Bigger droplet (8GB), runs bootstrap-hub.sh against a sanitized fake DR snapshot. ~90 min wall-clock target. Validates the hub rebuild path end-to-end.

This is the highest-value drill but the most expensive (per-drill cost ~$0.10-0.30) and longest (~90 min). Don't run frequently — once per quarter is probably right.

### Phase 5 — `fabrik vultr provision` (permanent mode)

Once disposable drills are stable, build the permanent provisioning flow:

```python
# fabrik vultr provision vps4 --region lhr
1. Pre-flight: name doesn't collide with existing instance in state.json or live Vultr
2. Operator confirmation (interactive prompt — this is irreversible billing)
3. Create instance with stable hostname=vps4
4. Wait for active + SSH ready
5. Run bootstrap-vps.sh root@<ip> vps4 (full bootstrap, no --skip flags)
6. Mesh peer registration on vps1's wg0 (handled by bootstrap-vps.sh step_06)
7. DNS records via site-provisioner (handled by bootstrap-vps.sh step_13)
8. Add Backrest plans for the new spoke
9. Add Prometheus scrape targets (node-spokes, cadvisor-spokes, promtail-spokes)
10. Add Gatus aro-wake-vps4 endpoint
11. Update /opt/fabrik/data/vultr-instances.json with mode=permanent
12. Update PEER_HOSTS env on all existing spokes (so they know about vps4)
13. Print: state contract complete; vps4 is now part of the fleet.
```

This is a SIGNIFICANT operation. Should be explicitly opt-in, slow, and reversible (`fabrik vultr destroy vps4 --reverse-fleet-add` un-does steps 6-12).

### Phase 6 — Cost guardrails + safety net

- Per-call max budget: `fabrik vultr drill spoke --max-cost 0.50` → refuse if estimated cost exceeds
- Auto-destroy timer for disposable: max 4h lifetime regardless of failure mode
- Weekly cron: `fabrik vultr cleanup` finds orphans, destroys them, alerts on Telegram if cost > $X
- Monthly cost report: `fabrik vultr cost` — pulled from Vultr billing API, posted to Telegram

---

## Failure modes + recovery

| Failure | Behavior |
|---|---|
| Vultr API auth fails (bad token) | Clear error; operator regenerates token; no instance created |
| Vultr API 5xx | 3-attempt retry with 5/15/30s backoff; if still failing, error to operator |
| Instance created but SSH never ready | Destroy + retry once (Vultr sometimes provisions slow); on second fail, leave for operator + alert |
| Bootstrap fails mid-way (disposable) | Destroy instance + write drill report with success=false + step_durations.bootstrap_failed_at_step |
| Bootstrap fails mid-way (permanent) | Leave instance running for operator inspection; mark state.json with bootstrap_completed_at=null; operator must explicitly `fabrik vultr destroy` or retry bootstrap |
| State.json corrupted | Reconcile from Vultr API; warn on any drift |
| Operator Ctrl-C mid-drill | Trap SIGINT; destroy instance; write partial drill report |
| Vultr API key revoked mid-operation | Catch 401; if instance was created, alert operator with manual destroy instructions |
| Cost exceeds monthly cap | Refuse to create new instances; alert operator |

---

## How to get the Vultr API key (operator instructions)

1. Go to <https://my.vultr.com/settings/#settingsapi>
2. **Personal Access Token** section → click **"Generate API Token"** (or "Enable API" if first time)
3. **Allowed IPs** section: add your dev WSL's public IP (`curl -s https://api.ipify.org` to get it). You can also add vps1's public IP (`172.93.160.197`) if you want fabrik on vps1 to be able to call the API. Or "Allow All IPv4" if you accept the risk (less secure but simpler).
4. Copy the API key — **it's shown only once**.
5. Store securely on dev WSL:
   ```bash
   echo "VULTR_API_KEY=YOUR_KEY_HERE" >> /opt/fabrik/.env.sysadmin
   chmod 600 /opt/fabrik/.env.sysadmin
   ```
6. Also save the **SSH key ID** for `id_ed25519_do.pub` (or whichever pubkey you'll use). Get it via:
   ```bash
   curl -sH "Authorization: Bearer $VULTR_API_KEY" https://api.vultr.com/v2/ssh-keys | jq '.ssh_keys[] | {id, name}'
   ```
   Then `echo "VULTR_SSHKEY_ID=<id>" >> /opt/fabrik/.env.sysadmin`

That's enough state for Phase 1-3 to function.

---

## Verification

- `fabrik vultr drill bare` — smallest cheapest drill, validates the entire pipeline; runs in <2 min, costs ~$0.005
- `fabrik vultr drill spoke` — validates bootstrap-vps.sh end-to-end against today's edits; ~5-15 min, ~$0.02-0.05
- `fabrik vultr drill hub` — validates bootstrap-hub.sh; ~90 min, ~$0.10-0.30
- All drills emit a line to `logs/dr-drill-history.jsonl`; operator can `jq` over history for trend
- Weekly cron runs `fabrik vultr cleanup` + `fabrik vultr cost` for orphan detection + cost tracking
- Quarterly: operator runs `fabrik vultr drill hub` to keep the DR-in-hours target measured

---

## Implementation order (concrete tickets when this becomes work)

1. **Phase 1**: `VultrClient` + unit tests (~1 day)
2. **Phase 2**: state store + reconcile + `fabrik vultr list/status/cleanup` (~half day)
3. **Phase 3a**: `fabrik vultr drill bare` (~half day — smallest drill, validates plumbing)
4. **Phase 3b**: `fabrik vultr drill spoke` with full end-state contract (~1 day)
5. **Phase 4**: `fabrik vultr drill hub` (~half day after Phase 3 works)
6. **Phase 5**: `fabrik vultr provision <name>` permanent mode (~1 day)
7. **Phase 6**: cost guardrails + weekly cron (~half day)

**Total**: ~4-5 days of focused work. Realistically 1-2 weeks calendar time with interruptions.

---

## Open questions

1. Should `fabrik vultr drill` use a Vultr snapshot of a pre-provisioned base image (faster drills) or stock Ubuntu (more realistic)? Probably stock Ubuntu for now — drilling against a snapshot defeats the validation purpose.
2. Should permanent-mode `fabrik vultr provision` auto-trigger the existing `bootstrap-vps.sh`'s mesh registration + DNS, or split those into separate explicit subcommands the operator runs after provision? **Recommendation**: auto-trigger but require `--confirm-mesh-add` flag to make it explicit.
3. Per-call cost cap: should be per-drill or per-fabrik-invocation? **Recommendation**: per-drill, with config in `.env.sysadmin` for fleet-wide cap.
4. Region picking: pin a single region for drills (faster + cheaper)? **Recommendation**: yes — `lax` for now since vps1 is in LA. Operator can override per-call.
5. What about Vultr's snapshot/backup feature for permanent instances? Out of scope this iteration; we use Backrest.

---

## Cross-references

- [`docs/STRATEGIC_BACKLOG.md`](../STRATEGIC_BACKLOG.md) — Now tier, this plan resolves the "DR drill on throwaway VPS" item
- [`docs/infrastructure/vps-spoke-rebuild.md`](../../infrastructure/vps-spoke-rebuild.md) — runbook this drills against
- [`docs/infrastructure/vps-hub-rebuild.md`](../../infrastructure/vps-hub-rebuild.md) — runbook this drills against
- [`scripts/bootstrap/bootstrap-vps.sh`](../../../scripts/bootstrap/bootstrap-vps.sh) — script invoked by Phase 3 drills
- [`scripts/bootstrap/bootstrap-hub.sh`](../../../scripts/bootstrap/bootstrap-hub.sh) — script invoked by Phase 4 drill
- [`.windsurf/rules/core/90-bootstrap-scripts.md`](../../../.windsurf/rules/core/90-bootstrap-scripts.md) — operator-discipline rules this plan eliminates by automating
- Vultr API v2 docs: <https://www.vultr.com/api/>
