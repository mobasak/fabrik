# Plan: `fabrik vultr` — on-demand VPS provisioning (permanent + disposable)

**Created:** 2026-06-07
**Status:** ✅ Shipped & archived 2026-06-08 — Phases 1–6 implemented, gated, and core live-validated (drill bare 98s / drill spoke vps4 rc=0 / live create→destroy round-trip ~$0.02). Hardening landed on top: PR1 (`c48f3c0`, G1/G2/G4/G10 + Coolify cleanup), G5 (`c158ee2`, ufw conflict), PR2 (`cbbdb99`, G6/G3), G5b (`658a68f`, DR-restore alignment). 45/45 unit tests green. Post-plan follow-ups tracked separately (NOT part of this plan's scope): G8 `fabrik apply --target-vps` live test, G9 hub DR + B2 restore drill, G11 Phase 7 snapshot/restore enhancement, G12 Gatus configs to source control; plus live shakedown of G5/G6/G5b on the next real drill.
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
- **Any Vultr compute product line, on demand** — `vc2`/`vdc`/`vhf`/`vhp`/`voc`/`vcg` (incl. Cloud GPU) via `/v2/instances`, and `vbm` Bare Metal via `/v2/bare-metals`. Operator can buy/deploy/configure/use any server type at any time (see Addendum §A).
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
- Block storage (volumes), VPC/VPC 2.0 networks, reserved IPs — *server* provisioning only this iteration (these are attachable add-ons, not server types; revisit if a workload needs them)
- Cost forecasting / monthly budget alerting — minimal cost-tracking only
- Managed databases via Vultr — we use our own postgres-main

> **Note:** GPU (`vcg`) and Bare Metal (`vbm`) are now **in scope** — see In-scope above + Addendum §A. The operator requirement is to be able to buy/deploy/configure/use *any* Vultr server type on demand.

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
| `/v2/plans?type=<tag>` | GET | List plans for a product line (`vc2`/`vdc`/`vhf`/`vhp`/`voc`/`vcg`) + pricing |
| `/v2/bare-metals` | POST/GET | Create / list **Bare Metal** instances (`vbm`) — separate endpoint family |
| `/v2/bare-metals/<id>` | GET/DELETE | Get / destroy a Bare Metal instance |
| `/v2/bare-metals/<id>/reboot` | POST | Reboot a Bare Metal instance |
| `/v2/plans-metal` | GET | List Bare Metal plans (`vbm-*`) + pricing (separate from `/v2/plans`) |

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
9. (No manual SSH-user switch — the script handles root→ozgur internally via EFFECTIVE_REMOTE; see §K.1)
10. Continue tailing log; wait for bootstrap completion or timeout (15 min)
11. Verify end-state by running `bootstrap-vps.sh --verify ozgur@<ip> vps4` (its own run_verify); pass = exit 0. (NOT vps-spoke-rebuild.md's restore contract — see §K.2)
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

## Addendum — completed gaps (2026-06-07)

Fills the parts the first draft left open. Verified against Vultr API v2 docs (<https://www.vultr.com/api/>) on 2026-06-07.

### §A. Supporting *any* Vultr server type (operator requirement)

The operator must be able to buy/deploy/configure/use **any** Vultr server type, any time. Vultr exposes seven compute product lines, selectable via the `type` filter on `/v2/plans?type=<tag>`:

| Tag | Product line | Create endpoint | Plans endpoint |
|---|---|---|---|
| `vc2` | Regular Cloud Compute | `/v2/instances` | `/v2/plans?type=vc2` |
| `vdc` | Dedicated Cloud | `/v2/instances` | `/v2/plans?type=vdc` |
| `vhf` | High-Frequency Compute | `/v2/instances` | `/v2/plans?type=vhf` |
| `vhp` | High Performance | `/v2/instances` | `/v2/plans?type=vhp` |
| `voc` | Optimized Cloud Compute | `/v2/instances` | `/v2/plans?type=voc` |
| `vcg` | Cloud GPU (A100/A40/A16) | `/v2/instances` | `/v2/plans?type=vcg` |
| `vbm` | **Bare Metal** | **`/v2/bare-metals`** | **`/v2/plans-metal`** |

**Key fact:** every line *except* Bare Metal creates through `/v2/instances` — only the `plan` value changes (e.g. `vcg-a100-12c-120g-80vram` for GPU). **Bare Metal is the sole exception** — distinct endpoint family (`/v2/bare-metals`, `/v2/plans-metal`) with parallel create/get/delete/reboot/reinstall verbs. So `VultrClient` needs one extra thin path for `vbm`; all other types are a single parameterized path.

- CLI: `--plan <id>` accepts any plan. Client auto-routes to `/v2/bare-metals` when the plan starts `vbm-` (or `--bare-metal` is passed).
- New discovery command: `fabrik vultr plans [--type vhf|vcg|vbm|…]` — lists plans + monthly cost for any line (queries `/v2/plans` or `/v2/plans-metal`).
- `VultrClient` (Phase 1) gains: `list_plans(type=None)`, `list_bare_metal_plans()`, and bare-metal variants `create_bare_metal()`, `get_bare_metal()`, `destroy_bare_metal()`, `reboot_bare_metal()`. `create_instance(...)` dispatches to the bare-metal path when `plan.startswith("vbm-")`.

### §B. ID resolution + catalog caching

Human inputs (`--region lhr`, `--plan vc2-2c-4gb`, `"Ubuntu 24.04"`) must resolve to API IDs (`os_id` is an int). Cache the four stable catalogs — `/v2/regions`, `/v2/plans` (all types), `/v2/plans-metal`, `/v2/os` — in `data/vultr-catalog.json` with a 24h TTL; `fabrik vultr plans --refresh` forces a re-fetch. Fail loudly with the valid set if a name doesn't resolve.

### §C. Mesh IP allocation (permanent mode) — CORRECTED from ground truth

**The mesh IP is deterministic, not "lowest free."** `bootstrap-vps.sh:110` derives `SPOKE_MESH_IP="10.99.0.${SPOKE_NUM}"` where `SPOKE_NUM="${SPOKE_NAME#vps}"` — i.e. `vps4` → `10.99.0.4`, always. The spoke **name** is the only choice; the IP follows. Constraints (verified `bootstrap-vps.sh:104-115`): name must match `^vps[0-9]+$`, `SPOKE_NUM` in **2-254** (hub is `vps1`=`10.99.0.1`; 0/255 reserved). Subnet/hub constants live in `scripts/bootstrap/bootstrap-config.sh:14-16` (`10.99.0.0/24`, hub `10.99.0.1`, WG UDP `51820`). So `fabrik vultr provision` picks the **next free `vpsN`** (lowest N≥2 not present on vps1's wg0 nor in `vultr-instances.json`); the IP is then fixed as `10.99.0.N`. `bootstrap-vps.sh` preflight already collision-checks both name and IP on the hub (lines 237-244) — reuse it, don't reimplement.

### §D. Concurrency + locking — CORRECTED from ground truth

**Use the LOCAL lock, not `run_locked`.** `drivers/locks.py::run_locked()` runs a bash script **on the VPS** via `ssh … flock /tmp/fabrik-<resource>.lock` (`locks.py:68-113`) — wrong layer for a WSL-local JSON file. The correct primitive is the one `state.py` already uses for local files: **`fabrik.locks_local.file_lock(name, timeout_seconds)`** (`state.py:168`, `locks_local.py:60-108`). Pattern to mirror verbatim (`state.py:164-170`): write to `target.with_suffix(f".tmp.{os.getpid()}")`, then `os.replace(tmp, target)` **inside** `with file_lock("vultr-state", timeout_seconds=15.0):`. This is atomic + lock-safe and matches the codebase. (The race still matters: the AI sysadmin on vps1 and the operator on WSL can both invoke `fabrik vultr` — but each writes its own local copy; if state ever needs to be shared cross-host, that's a separate sync concern, out of scope.)

### §E. Cost estimation method — CORRECTED from ground truth

Vultr bills hourly, capped at the monthly price (672h month). So `hourly = plan.monthly_cost / 672`; `cost_estimate_usd = hourly × wall_clock_hours`, rounded up to the hour. Bare Metal pulls `monthly_cost` from `/v2/plans-metal`. **Do NOT gate on account balance** — verified live, `/v2/account` returns `{"account": {...}}` (wrapper key `account`) and this account shows `balance: -305` with `pending_charges` (it is postpaid, balance runs negative), so a "refuse if balance < cost" check would always refuse. **Gate on the configured caps instead**: per-call `--max-cost` and a monthly cap in `.env.sysadmin`; surface `account.pending_charges` for visibility only. (`/v2/account` is still useful as the auth pre-check — a 200 with an `account` object means the token works.)

### §F. Permanent-mode rollback — concrete steps

`fabrik vultr destroy <name> --reverse-fleet-add` undoes provision steps 6–12 in **reverse** order (each idempotent, best-effort, continue-on-error):
1. Remove Gatus `aro-wake-<name>` endpoint
2. Remove Prometheus scrape targets (node/cadvisor/promtail spokes)
3. Remove Backrest plans for the spoke
4. Remove DNS records via site-provisioner
5. Deregister the wg0 peer on vps1 (free the `mesh_ip`)
6. Update `PEER_HOSTS` on all remaining spokes
7. `DELETE` the instance (or `/v2/bare-metals/<id>` for `vbm`)
8. Mark `destroyed_at` in state

Without `--reverse-fleet-add`, destroy refuses on a permanent instance (prevents orphaned mesh/DNS/monitoring residue).

### §G. Execution context + autonomous use

- Runs from **operator WSL** (primary) and from **vps1** (for the AI sysadmin). The Vultr API-key IP allowlist must include both public IPs (WSL dev IP + `172.93.160.197`).
- **Autonomy boundary:** the AI sysadmin may auto-run **disposable** drills (`fabrik vultr drill …`) within the cost cap, posting a Telegram notice on each create/destroy. **Permanent** `provision` always requires interactive human confirmation — it is irreversible billing and a fleet topology change. (Consistent with operator policy: real-money caps are fine; the "no caps" rule applies only to LLM calls, not cloud spend.)

### §H. Secrets + doc-sync obligations

- `VULTR_API_KEY` + `VULTR_SSHKEY_ID` live in `/opt/fabrik/.env.sysadmin` (mode 600 — the autonomous-agent secrets file, deliberately separate from the app `/opt/fabrik/.env`).
- Doc Sync Matrix obligations when implemented: add both vars to `.env.example` (names only, no values) + `docs/CONFIGURATION.md`; add the new `drivers/vultr.py` + `orchestrator/vultr_state.py` to `INDEX.md`; `CHANGELOG.md` entry per phase.

### §I. Testing + gate

- `tests/test_vultr_client.py` — mock `httpx`: both the `/v2/instances` and `/v2/bare-metals` paths, ID resolution, 4xx-vs-5xx handling, retry/backoff. No real network.
- `tests/test_vultr_state.py` — load/save/reconcile, lock contention, drift detection.
- `fabrik vultr drill bare` is the **live** integration smoke (operator-run, ~$0.005) — not in CI.
- `scripts/final_gate.py --lean` must stay green; unit tests never hit the network.

---

## Iteration 2 — convergence to ground truth (verified 2026-06-07)

Every value below was confirmed against the **live Vultr API** (read-only, real token), the **Vultr API changelog + create-instance/bare-metal docs**, or **existing fabrik code** (file:line). No item is assumed.

### §J. Verified ground-truth reference (zero unknowns)

**J.1 — Live Vultr API (queried with the real `.env.sysadmin` token, GETs only):**

| Fact | Verified value |
|---|---|
| Auth / ACL | Token works; ACL = `root` (full). `/v2/account` wraps in **`{"account": {...}}`** |
| Ubuntu 24.04 `os_id` | **`2284`** (`Ubuntu 24.04 LTS x64`) |
| SSH key | `VULTR_SSHKEY_ID=fff13c0e-de4a-4027-aee1-68efad7e53ae` (name `ssh-key-for-all`) — valid; **must be sent as `sshkey_id: ["<id>"]`** in create or the box has no key |
| Regions | 33 total; `lax`=Los Angeles (drill default — vps1 is in LA), `lhr`=London |
| Current instances | **0** (clean baseline) |
| Account balance | `balance: -305`, `pending_charges` present → **postpaid**; do not gate on balance (see §E) |
| Plan IDs (live `monthly_cost`) | `vc2-1c-2gb` **$10** (drill spoke), `vc2-2c-4gb` **$20** (perm spoke default), `vc2-1c-0.5gb-v6` **$2.5** (cheapest, IPv6-only → `drill bare`), `vhf-1c-1gb` $6, `vhp-1c-1gb-amd` $6, `voc-c-1c-2gb-25s-amd` $28, `vcg-a16-2c-8g-2vram` **$43** (GPU), `vbm-4c-32gb` **$120** (bare metal) |
| `vdc` (Dedicated Cloud) | **Zero plans returned — not offered on this account.** Drop from the supported list. |

**J.2 — Create payloads + changelog (Vultr docs):**

- `POST /v2/instances` (vc2/vhf/vhp/voc/**vcg GPU**): body `{region, plan, os_id, label, hostname, sshkey_id:[<id>], enable_ipv6, tags:[…]}`. GPU is the **same** endpoint.
- `POST /v2/bare-metals` (`vbm`): same body shape. Plans from `/v2/plans-metal`.
- **Changelog deprecations that bind us:** API **v1 is offline — v2 only** (Oct 2023); **`tag` (singular) is deprecated → use `tags` (list)** (Apr/Nov 2022) — `VultrClient` must send `tags`, never `tag`; `enable_private_network`→`enable_vpc` (we use neither — VPC is out of scope).
- New instance returns `main_ip:"0.0.0.0"` until active → `wait_for_active` polls `GET /v2/instances/<id>` until `status=="active" && main_ip!="0.0.0.0" && power_status=="running"` (bare metal: poll `status=="active"`).

**J.3 — Existing-code anchors (file:line, verified):**

| Concern | Anchor + fact |
|---|---|
| Bootstrap invocation | `scripts/bootstrap/bootstrap-vps.sh` — `[OPTIONS] root@<ip> <vpsN>`; 15 steps; `--skip-mesh` skips 04-10; `--skip-dns` skips 13; **`--verify` runs `run_verify()`** (reuse as drill end-state, don't reimplement) |
| Root→ozgur transition | Internal via `EFFECTIVE_REMOTE` (`step_00` creates `ozgur`, `step_01` disables root). **The drill must NOT manually switch users** |
| Mesh IP | `bootstrap-vps.sh:110` `10.99.0.${N}`; constants `bootstrap-config.sh:14-16` |
| HTTP driver shape | `drivers/cloudflare.py:40-58` — `httpx.Client(base_url=, headers={"Authorization": f"Bearer {token}"}, timeout=30)`; `VultrClient` mirrors this |
| SSH/SCP | `drivers/ssh.py:46-127` (`ssh()`, `scp_to_vps()`) |
| Local state | `src/fabrik/state.py:100-184` — atomic `tmp` + `os.replace` inside `locks_local.file_lock(...)`; store at `data/vultr-instances.json` (registry style, like `data/projects.yaml`) |
| CLI group | `cli.py:2205` `@cli.group() def domain()` + `@domain.command("provision")`; options at `apply` `347-382`; `_post_deploy_sync()` `59-108` |
| `.env.sysadmin` | **Not auto-loaded** by `config.py` (it only `load_dotenv()`s the default `.env`) → the vultr CLI/driver must `load_dotenv("/opt/fabrik/.env.sysadmin")` explicitly |
| Tests | `@patch("fabrik.drivers.<mod>.httpx.Client")`; live in `tests/drivers/` |
| Monitoring | aro-wake job in `configs/prometheus/prometheus.yml` (targets `10.99.0.N:8201`); Gatus `apps/<name>.yaml` via `gatus.py`; Backrest `/opt/backrest/config/config.json` via `backrest.py` (jq+flock) |

### §J.4 — Exact create/response schemas (official GoVultr SDK `master`, iteration 3)

Verified from the canonical `vultr/govultr` source — the structs the API literally accepts/returns. **Zero ambiguity for Phase 1.**

**Instances** — `/v2/instances` (covers `vc2`/`vhf`/`vhp`/`voc`/`vcg` GPU):
- **Create body (JSON):** `region`, `plan`, `os_id`(int), `label`, `hostname`, **`sshkey_id`** (array of key IDs — exact field name), `tags`(array), `enable_ipv6`(bool); optional `backups`("enabled"/"disabled"), `user_data`, `snapshot_id`, `ddos_protection`, `disable_public_ipv4`, `firewall_group_id`. **Never send `tag` (singular) — deprecated.**
- **Response wrapper:** create/get → `{"instance": {…}}`; list → `{"instances":[…],"meta":{…}}`.
- **`Instance` fields we use:** `id`, `main_ip` (=`"0.0.0.0"` until ready), `status` (`pending`→`active`), `power_status` (`running`), `server_status` (`none`→`installingbooting`→`ok`), `default_password`, `region`, `plan`, `os_id`, `tags`.
- **`wait_for_active` (instances):** poll `GET /v2/instances/<id>` until `status=="active" && power_status=="running" && server_status=="ok" && main_ip!="0.0.0.0"`.
- **LIVE-VERIFIED 2026-06-08** (real create→destroy of `vc2-1c-2gb`/`lax`, cost ~$0.02): `CREATE`→**HTTP 202**, wrapper `{"instance":{…}}`, initial `status=pending power=running server=none main_ip=0.0.0.0`, `default_password` present at create. **Transition is NON-MONOTONIC — `status` reached `active` at t+23s while `power=stopped server=locked` (and `main_ip` already assigned), only becoming `active/running/ok` at t+58s.** This is exactly why all four conditions are mandatory: a `status=="active"`-only check returns a stopped, locked box. `DELETE`→**HTTP 204**, `GET` after→**404**. Provision-to-ready ≈ **60s** for a small plan → 120s poll timeout is safe.

**Bare Metal** — `/v2/bare-metals` (`vbm`):
- **Create body (`BareMetalCreate`):** `region`, `plan`, `os_id`, `label`, `hostname`, **`sshkey_id`** (array), `tags`, `enable_ipv6`; optional `mdisk_mode` (RAID1/none), `persistent_pxe`, `user_data`, `reserved_ipv4`.
- **Response wrapper:** `{"bare_metal": {…}}`; list → `{"bare_metals":[…],"meta":{…}}`.
- **Schema differs from Instance:** `ram`/`disk` are **strings**; field is **`cpu_count`** (not `vcpu_count`); **NO `power_status`/`server_status`** fields exist.
- **`wait_for_active` (bare metal):** poll `GET /v2/bare-metals/<id>` until `status=="active" && main_ip!="0.0.0.0"` (no power/server status; "IP info only available in active state").

**Common:** Bearer auth; object returned inside a single-key wrapper; `DELETE /<id>` → 204 no body; `POST /<id>/{reboot,halt,start}` empty body. **VPC2 is fully deprecated** ("no longer supported" in both SDKs) — never use. → `VultrClient.create_instance()` dispatches to the bare-metal path + poll when `plan.startswith("vbm-")`, and each path unwraps its own wrapper key.

### §K. Corrections to the draft body (these supersede earlier text)

1. **Phase 3 step 9** ("after step_01, switch SSH user to ozgur") — **remove**; the script handles the transition internally (EFFECTIVE_REMOTE). The drill just runs `bootstrap-vps.sh --skip-mesh --skip-dns root@<ip> vps<N>`.
2. **Phase 3 step 11 end-state contract** — do **not** reimplement checks, and do **not** use `vps-spoke-rebuild.md`'s contract (that is the *restore-from-backup* contract — it checks WG handshake / hub peer table, which need mesh that the drill skips). Pass = **`bootstrap-vps.sh --verify ozgur@<ip> vps<N>` exits 0**.
3. **Phase 5 step 9** ("node-spokes / cadvisor-spokes / promtail-spokes" scrape targets) — no such separate files exist; node/cadvisor bind `SPOKE_MESH_IP` and are covered. Correct action: add the spoke's **aro-wake target** to `configs/prometheus/prometheus.yml` + reload.
4. **`vdc`** removed from supported product lines (not offered — J.1).

### §L. Validation gates (per step — for 100%-accurate implementation)

Each phase ships only when its gate passes. Gates are concrete commands with explicit pass criteria.

**Phase 1 — VultrClient**
- **G1.1** `pytest tests/drivers/test_vultr_client.py -q` green — covers `/v2/instances` + `/v2/bare-metals` create paths, `sshkey_id` sent as list, **`tags` not `tag`**, 4xx (no retry) vs 5xx (3× backoff), `wait_for_active` polling. httpx mocked, no network.
- **G1.2** Live auth smoke (operator): `VultrClient().get_account()["name"]` returns the account name (proves auth + `.account` unwrap).
- **G1.3** `ruff check src/fabrik/drivers/vultr.py` clean + `scripts/final_gate.py --lean` green.

**Phase 2 — state + reconcile**
- **G2.1** `pytest tests/test_vultr_state.py -q` green — save/load round-trip, atomic write, `file_lock` contention, reconcile drift both directions.
- **G2.2** `fabrik vultr list` on empty state prints 0 and reconciles cleanly vs live (0 instances).

**Phase 3a — drill bare**
- **G3a.1** `fabrik vultr drill bare --dry-run` prints the planned create (region `lax`, cheapest plan) and touches nothing.
- **G3a.2** `fabrik vultr drill bare` creates → SSH-ready → destroys; `logs/dr-drill-history.jsonl` gains one `success:true` line; `cost_estimate_usd ≤ 0.01`.
- **G3a.3** Orphan check: `GET /v2/instances` count returns to **0** (try/finally destroy verified).

**Phase 3b — drill spoke**
- **G3b.1** Runs `bootstrap-vps.sh --skip-mesh --skip-dns root@<ip> vps<N>`; end-state = `bootstrap-vps.sh --verify` exits 0; droplet destroyed; report has `success:true` + `step_durations`.
- **G3b.2** Hermetic: after the drill, `ssh vps 'sudo wg show wg0'` shows **no new peer** and no `*.vps<N>` DNS exists (both `--skip` flags honored → zero production residue).
- **G3b.3** Failure path: force a bootstrap failure → droplet **still destroyed** (no orphan), report `success:false` with the failing step.

**Phase 4 — drill hub:** **G4.1** completes < 120 min · **G4.2** destroyed · **G4.3** report `success:true`.

**Phase 5 — provision (permanent)**
- **G5.1** `--dry-run` prints the next free `vpsN` + `10.99.0.N` + all 13 steps; touches nothing.
- **G5.2** Interactive confirmation **required** (no `-y` bypass for permanent — irreversible billing).
- **G5.3** Post: `bootstrap-vps.sh --verify ozgur@<ip> vps<N>` exits 0; spoke in `ssh vps 'sudo wg show wg0'`; DNS resolves; aro-wake target in `prometheus.yml`; Gatus endpoint present; state `mode=permanent`.
- **G5.4** Rollback: `fabrik vultr destroy vps<N> --reverse-fleet-add --dry-run` lists the 8 reverse steps in order; real run leaves **zero residue** (no wg peer, no DNS, no prometheus/gatus/backrest entries, instance gone).

**Phase 6 — guardrails**
- **G6.1** `--max-cost 0.001` on any drill refuses **before** create.
- **G6.2** `fabrik vultr cleanup` destroys a deliberately-orphaned disposable (past `destroy_after`) and prints a cost report.
- **G6.3** Monthly-cap breach → create refused + Telegram alert.

**Cross-phase doc-sync gate (every phase):** new env vars in `.env.example` + `docs/CONFIGURATION.md`; new files in `INDEX.md`; `CHANGELOG.md` entry; `final_gate.py --lean` green.

### Convergence status

Four convergence iterations were run: (1) live read-only API + code agents + changelog; (2) corrected §C/§D/§E + added §J–§L; (3) pinned exact create/response schemas + `wait_for_active` from the official GoVultr SDK (§J.4); (4) **live create→active→destroy round-trip (2026-06-08, ~$0.02)** that empirically confirmed HTTP codes (202/204/404), the wrapper key, ~60s provision time, and — critically — the non-monotonic `status==active`-while-`stopped/locked` transition that validates the 4-condition poll (§J.4 LIVE-VERIFIED). Zero orphans left. With §J–§L there are **no remaining unknowns resolvable from code / state / API**: all IDs (`os_id 2284`, ssh key, plan IDs, 33 regions), every code anchor (file:line), the **exact request fields + response wrappers + poll criteria for both `/v2/instances` and `/v2/bare-metals`**, the binding deprecations (v1 dead, `tag`→`tags`, VPC/VPC2 dead), and the correct local-lock / atomic-state / `--verify` patterns are pinned to ground truth. The **only** non-code dependencies are operator actions, and both are satisfied or expected: the API key already exists ✓; running live drills spends real (cents) money and must be operator-initiated. **No room left to iterate — plan is ready to implement.**

---

## Cross-references

- [`docs/STRATEGIC_BACKLOG.md`](../STRATEGIC_BACKLOG.md) — Now tier, this plan resolves the "DR drill on throwaway VPS" item
- [`docs/infrastructure/vps-spoke-rebuild.md`](../../infrastructure/vps-spoke-rebuild.md) — runbook this drills against
- [`docs/infrastructure/vps-hub-rebuild.md`](../../infrastructure/vps-hub-rebuild.md) — runbook this drills against
- [`scripts/bootstrap/bootstrap-vps.sh`](../../../scripts/bootstrap/bootstrap-vps.sh) — script invoked by Phase 3 drills
- [`scripts/bootstrap/bootstrap-hub.sh`](../../../scripts/bootstrap/bootstrap-hub.sh) — script invoked by Phase 4 drill
- [`.windsurf/rules/core/90-bootstrap-scripts.md`](../../../.windsurf/rules/core/90-bootstrap-scripts.md) — operator-discipline rules this plan eliminates by automating
- Vultr API v2 docs: <https://www.vultr.com/api/>
