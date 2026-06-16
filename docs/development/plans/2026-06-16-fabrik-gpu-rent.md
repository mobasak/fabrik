# Plan: `fabrik gpu rent` — disposable GPU lifecycle, vultr-pattern parity

**Created:** 2026-06-16
**Status:** 🟡 **DRAFT** — open decisions on first provider and pod-mode scope (see § Open decisions)
**Owner:** TBD (proposed: Claude Code, peer-reviewed before merge)
**Trigger:** [`.windsurf/rules/core/76-gpu-workers.md`](../../../.windsurf/rules/core/76-gpu-workers.md) is the **decision framework** for GPU work. Its line 460 explicitly punts the implementation:

> "Until [a GPU scaffold type exists], GPU lifecycle is managed by the orchestrator service's own code — the provider API calls, cost tracking, and auto-termination logic live in the orchestrator project."

Every service that needs GPU compute today would re-implement provider-API + cost-cap + auto-terminate inline. That's the gap. The `fabrik vultr` surface (`drill | provision | list | destroy | disposable` with try/finally cost-capped lifecycle, `dr-drill-history.jsonl` audit trail, orphan reconciliation) is the right shape — port it to GPU.

---

## Goal

A single shared Fabrik surface that any service can call to **provision a GPU on demand, use it, and discard it** with the same lifecycle guarantees the vultr surface provides for CPU droplets:

```bash
fabrik gpu rent   --kind serverless --workload inference --max-cost 5
fabrik gpu rent   --kind pod-h100   --workload training  --max-lifetime 4 --max-cost 12
fabrik gpu list                                           # active pods + cost-to-date
fabrik gpu destroy <pod-id>                               # manual orphan cleanup
```

Plus a Python API (`from fabrik.orchestrator.gpu_rent import rent`) so services can call it programmatically with try/finally semantics:

```python
with rent(kind="pod-h100", workload="training", max_lifetime_hours=4, max_cost_usd=12) as pod:
    # pod.endpoint, pod.ssh, pod.id available here
    run_training(pod)
# pod auto-destroyed on exit (success or exception)
```

This is **infrastructure**, independent of which AI service uses it first. The benefit compounds: every GPU-touching service stops re-implementing provider calls + cost caps + reaper logic.

### What this is NOT

- **Not an inference router.** Provider selection between managed APIs (Groq/Together/Replicate) is application-level concern (`openai` SDK + `base_url` swap per the rule). This plan is about **renting your own GPU**, not calling someone else's.
- **Not a Kubernetes/k8s alternative.** No pod scheduling, no resource quotas, no helm charts. Single-process Python orchestrator, try/finally, audit log. Same simplicity as `fabrik vultr drill`.
- **Not a model registry / weights cache.** That belongs in B2/R2; this plan provisions raw GPU access only.

---

## Why we need it now (current state, verified 2026-06-16)

| What I checked | Result |
|---|---|
| `fabrik <gpu|rent|inference|runpod|...>` CLI subcommand | None |
| `src/fabrik/drivers/{runpod,modal,vast,tensordock,gpu}.py` | None |
| `src/fabrik/orchestrator/gpu_*.py` | None |
| Specs/services referencing GPU compute | None live |
| Existing plan file for it | None |

So this is a greenfield addition. The closest parallel is `src/fabrik/orchestrator/vultr_drill.py` + `vultr_state.py` + `vultr_provision.py` + the CLI's `vultr` group — a working, drilled, in-production lifecycle wrapper. We copy the shape.

---

## Design Constraints (binding)

**C1 — No `ANTHROPIC_API_KEY`-analog credential leakage in the operational path.** Per the project's standing principle: operational AI surfaces run on subscription auth (Claude Code OAuth for sysadmin/watchdog; provider API keys are environment-scoped). For GPU: **every provider key (RunPod, Modal, Vast.ai, ...) lives in `.env.sysadmin` on the operator dev machine + W9-mirrored to DR-store**, NEVER scp'd to a rented GPU pod. The pod authenticates to the orchestrator (heartbeat), not to other providers. If a workload needs an API key (e.g., to push results to S3), the orchestrator stages it on the pod with `max_lifetime_hours` matching the rental, and the destroy step wipes it.

**C2 — Cost-cap is mandatory, not advisory.** `MAX_DAILY_GPU_COST` (env, default $50) is read by `rent()` at the top of every call. If `daily_spend + estimate > MAX_DAILY_GPU_COST` → raise `GPUBudgetExceeded` BEFORE the provider create call. The vultr `--max-cost` flag is the model; here it's a daily envelope, not per-call. Telemetry to `logs/gpu-rent-history.jsonl` (mirror of `dr-drill-history.jsonl`).

**C3 — try/finally is the only acceptable lifecycle.** The pod is destroyed on every exit path — success, exception, Ctrl-C, OOM, network drop, even if the destroy API call itself fails (state file marks as `destroy_pending`, reaper job cleans up). This is the lesson from `fabrik vultr drill #1` orphan ([dr-drill-history.jsonl](../../../logs/dr-drill-history.jsonl)) — we already paid the price for getting it wrong; same discipline applies here.

**C4 — Tag every instance, untagged = kill candidate.** Per the rule line 297: every GPU pod gets `project`, `workload_type`, `created_by`, `max_lifetime_hours`, `rent_session_id` tags. A daily reaper (cron) scans active pods across all configured providers — any pod without a matching live session entry in our state file gets destroyed.

**C5 — Cold-by-default. Hot is opt-in.** The rule line 253: "Default: serverless with scale-to-zero. Always-on pods only when traffic is steady AND latency-critical." Implement `--kind serverless` first (provider handles scale-to-zero, our orchestrator just creates the endpoint + returns the URL). `--kind pod-*` second (we manage the lifecycle directly, try/finally destroys at exit or `max_lifetime_hours`).

**C6 — Single-provider scope for MVP.** Multi-provider routing is in the rule but doubles the surface area. Ship RunPod first (best DX, has both serverless + pod, single auth model). Modal/Vast.ai/Thunder Compute deferrable.

---

## Grounded surfaces (verified 2026-06-16)

**The vultr pattern we're copying** (relevant files, sizes give a budget anchor):

- `src/fabrik/drivers/vultr.py` (~510 lines) — `VultrClient` API wrapper, raises `VultrError`. Methods: `list_plans`, `list_instances`, `create_instance`, `wait_for_active`, `destroy`.
- `src/fabrik/orchestrator/vultr_drill.py` (~520 lines) — `drill()` orchestrator with try/finally, cost estimation, `_run_script` for bootstrap, `write_report` to `logs/dr-drill-history.jsonl`. **Direct template for `gpu_rent.py`.**
- `src/fabrik/orchestrator/vultr_state.py` (~85 lines) — JSON state file at `logs/vultr-instances.json` tracking create/destroy lifecycle. **Direct template for `gpu_state.py`.**
- `src/fabrik/orchestrator/vultr_provision.py` (~350 lines) — long-running provision (full bootstrap-vps), different shape from drill. Not directly templated — GPU has no "long-running provision" mode; serverless/pod is enough.
- `src/fabrik/cli.py` § vultr group — Click subcommand group. `fabrik gpu` group sits next to it.
- `tests/orchestrator/test_vultr_drill.py` (~220 lines) — locks the contract (safety flags, destroy-on-failure, dry-run, max-cost guard). **Direct template for `test_gpu_rent.py`.**
- `logs/dr-drill-history.jsonl` — append-only audit log. `logs/gpu-rent-history.jsonl` is the parallel.

**The rule we're operationalizing** ([`76-gpu-workers.md`](../../../.windsurf/rules/core/76-gpu-workers.md)):

- Two-faced architecture (lines 21–34): orchestrator on vps1, GPU worker external. **This plan ships the orchestrator-side machinery.**
- Selection criteria (lines 248–253): scale-to-zero default, always-on only for steady + latency-critical.
- Lifecycle (lines 292–325): spin up via Templates/Cloud-Init, tag every instance, set `max_lifetime_hours`, async checkpoint to B2, immediate-after-work destroy + verify.
- Cost control (lines 351–360): scale to zero, right-size, quantize, `MAX_DAILY_GPU_COST` env, batch non-realtime, multi-provider routing, cost logging.
- Provider snapshot (lines 364–399): current RunPod Serverless $4.18/hr H100, FlashBoot ~563ms median cold, $0 egress — **default for inference**. RunPod Secure Pod $2.99/hr for always-on SLA. Verified 2026-05-24, re-verify at provisioning time.

---

## Architecture (5 layers, 600–800 line MVP budget)

### Layer 1 — provider driver (`src/fabrik/drivers/runpod.py`, ~250 lines)

One driver per provider. RunPod first.

```python
class RunPodClient:
    def __init__(self, api_key: str | None = None): ...

    # Serverless endpoints
    def list_endpoints(self) -> list[dict]: ...
    def create_endpoint(self, name: str, template_id: str, tags: dict) -> dict: ...
    def destroy_endpoint(self, endpoint_id: str) -> None: ...

    # On-demand pods (Secure / Community / Cloud GPU)
    def list_pods(self) -> list[dict]: ...
    def list_gpu_types(self) -> list[dict]:  # for `--kind pod-h100` resolution
        ...
    def create_pod(self, gpu_type_id: str, template_id: str, tags: dict, ...) -> dict: ...
    def wait_for_running(self, pod_id: str, timeout: int = 300) -> dict: ...
    def destroy_pod(self, pod_id: str) -> None: ...

class RunPodError(Exception): ...
```

Auth via `RUNPOD_API_KEY` env (read from operator's `/opt/fabrik/.env.sysadmin`, NOT pushed to vps1 — operator-only). HTTP client = `httpx` (already a dep, matches vultr driver style). Retries + structured error messages.

### Layer 2 — orchestrator (`src/fabrik/orchestrator/gpu_rent.py`, ~300 lines)

```python
GPU_RENT_LOG = FABRIK_ROOT / "logs" / "gpu-rent-history.jsonl"
PROVIDERS = {"runpod": RunPodClient}  # extension point

@dataclass
class RentReport:
    session_id: str
    provider: str
    kind: str               # serverless | pod-h100 | pod-a100 | ...
    workload: str
    success: bool
    cost_estimate_usd: float
    wall_clock_seconds: float
    checks: dict[str, Any]  # provisioned, ready, destroyed, etc.
    error: str | None

def rent(
    kind: str,
    workload: str,
    *,
    provider: str = "runpod",
    max_lifetime_hours: int = 1,
    max_cost_usd: float = 5.0,
    keep_warm_after_use: bool = False,
    work_fn: Callable[[Pod], None] | None = None,
    client: Any = None,
    dry_run: bool = False,
) -> dict:
    """try/finally GPU lifecycle. Always destroys unless keep_warm_after_use.

    Mirrors vultr_drill.drill() shape EXACTLY:
    - dry_run path returns plan, creates nothing
    - cost guard runs BEFORE provision
    - state file marks create + destroy
    - finally always destroys + writes report
    - JSON-line audit to logs/gpu-rent-history.jsonl
    """
```

Context-manager wrapper:

```python
class RentedGPU:
    """Context manager around rent() for `with rent(...) as pod:` syntax."""
    def __enter__(self) -> Pod: ...
    def __exit__(self, exc_type, exc, tb) -> bool: ...  # destroys, never swallows
```

### Layer 3 — state (`src/fabrik/orchestrator/gpu_state.py`, ~85 lines)

Direct port of `vultr_state.py`. JSON state file at `logs/gpu-rent-state.json`. Records: `{provider, pod_id, kind, workload, created_at, destroyed_at, max_lifetime_at, daily_cost_so_far}`. Same reconcile API: `track_creation`, `mark_destroyed`, `list_active`, `list_orphans` (active in state but not in provider, or vice versa).

### Layer 4 — CLI (`src/fabrik/cli.py`, ~150 lines additional)

`@gpu.command("rent")` mirrors `@vultr.command("drill")`. Flags:

- `--kind` (Choice: serverless, pod-h100, pod-a100, pod-l40s) — first cut. Extensible.
- `--workload` (free-text tag, mandatory)
- `--provider` (Choice: runpod — extensible)
- `--max-lifetime <hours>` (default 1)
- `--max-cost <usd>` (default 5)
- `--keep-warm-after-use` (flag — cold by default per C5)
- `--dry-run`

Plus:

- `fabrik gpu list` — active pods from state + provider reconcile (mirrors `fabrik vultr list`)
- `fabrik gpu destroy <pod-id> [-y]` — manual cleanup (mirrors `fabrik vultr destroy`)
- `fabrik gpu reconcile` — diff state vs provider; offer to destroy orphans (mirrors `fabrik vultr reconcile-all`)

### Layer 5 — reaper (`src/fabrik/orchestrator/gpu_reaper.py`, ~80 lines)

Cron-driven (entry in `scripts/cron/` or systemd timer). Scans the provider, destroys anything older than its tagged `max_lifetime_hours`. The vultr equivalent is the disposable-instance TTL reaper. Runs every 10 min. Logs to `logs/gpu-reaper.log`.

### Tests (`tests/orchestrator/test_gpu_rent.py`, ~200 lines)

Direct port of `test_vultr_drill.py`. Mock the RunPodClient. Contract assertions:

- `test_rent_creates_then_destroys`
- `test_failure_still_destroys_no_orphan` (try/finally invariant)
- `test_keep_warm_after_use_leaves_pod` (only mode where pod survives)
- `test_max_cost_guard_refuses_before_create`
- `test_max_daily_budget_guard` (cumulative spend cap)
- `test_dry_run_creates_nothing`
- `test_unknown_kind_raises`
- `test_serverless_uses_provider_scale_to_zero` (doesn't manage lifecycle directly)

---

## Phasing

### Phase 1 — MVP (~600–800 lines, ~1–2 days)

**Goal:** RunPod serverless + on-demand pod, with `fabrik gpu rent | list | destroy`, try/finally, cost-cap, state file, reaper, tests.

Deliverables:

1. `src/fabrik/drivers/runpod.py` — RunPodClient + RunPodError
2. `src/fabrik/orchestrator/gpu_rent.py` — `rent()` + `RentedGPU` context manager
3. `src/fabrik/orchestrator/gpu_state.py` — state file shape + reconcile
4. `src/fabrik/cli.py` — `@gpu` Click group
5. `src/fabrik/orchestrator/gpu_reaper.py` — reaper loop + cron entry
6. `tests/orchestrator/test_gpu_rent.py` — locked contract (≥ 8 tests)
7. `docs/operations/gpu-rent.md` — operator runbook, `--help` body, troubleshooting
8. `.env.sysadmin.template` — `RUNPOD_API_KEY`, `MAX_DAILY_GPU_COST`
9. CHANGELOG entry under `## [Unreleased]`

### Phase 2 — second provider (Modal OR Vast.ai), ~+250 lines

Adds provider routing per the rule's selection criteria (lines 282–288). Phase 1's `PROVIDERS` registry was an extension point; Phase 2 fills it.

**Decision gate**: Modal if Python-decorator DX is the priority (training notebooks), Vast.ai if cost minimization is the priority (cheapest marketplace for fine-tuning).

### Phase 3 — checkpoint helper, ~+100 lines

`gpu_rent.checkpoint_to_b2()` — async checkpoint utility for training workloads. Mirrors rule line 312–319 (DCP-style async write to S3/B2/R2). Generic enough to drop into any training workload without per-project re-implementation.

### Phase 4 — Prometheus metrics, ~+50 lines

`gpu_rent_session_seconds` (Histogram, labeled by `provider, kind, workload`), `gpu_rent_cost_usd_total` (Counter), `gpu_rent_active` (Gauge). Wired to the existing Prometheus + Grafana stack on vps1. Monthly cost rollup dashboard.

### Phase 5 (deferrable) — `gpu` scaffold type

Per rule line 357: "Until the GPU scaffold type exists, this logic lives in the orchestrator's own code." Adding a `gpu` template to `scripts/scaffold.py` lets new services declare GPU dependency in their spec and have `fabrik apply` wire the orchestrator integration. Significant — full plan needed when prioritized.

---

## Open decisions (block Phase 1 start)

| # | Decision | Options |
|---|---|---|
| **D1** | First provider | **RunPod** (recommended — see § D1 rationale below) / Modal (when pipeline-shape workloads emerge) / both |
| **D2** | Pod-mode scope in MVP | **Just `serverless` + 1 pod kind (`pod-h100`)** (recommended — proves both paths) / serverless only / serverless + all pod GPU types |
| **D3** | Where the operator's RUNPOD_API_KEY lives | **`.env.sysadmin` only** (recommended, mirrors VULTR_API_KEY pattern) / `/opt/fabrik/.env` (riskier; vps1 doesn't need this) |
| **D4** | Reaper schedule | **Every 10 min** (recommended — costs add up fast at $4/hr) / every 30 min / hourly |
| **D5** | Default `MAX_DAILY_GPU_COST` | **$50/day** (recommended; matches the rule's "solo dev" framing) / $20 / $100 / no default (must always be set) |

**Recommended Phase 1 commit point**: D1=RunPod, D2=serverless + pod-h100, D3=`.env.sysadmin` only, D4=10min, D5=$50/day.

### D1 rationale (cross-checked against an independent strategic verdict, 2026-06-16)

External analysis (Gemini) frames the choice as:

> **Choose Modal If:** modular, event-driven, or pipeline-based architecture; agents/tasks triggered as discrete functional calls (input → processing → output); want pure Python without managing container build pipelines or infrastructure registries — Modal offers unparalleled deployment velocity.
>
> **Choose RunPod If:** blend of persistent always-on host infrastructure and serverless scaling; or you prefer traditional container-based deployments; standard Docker setups; persistent disk state across long-running agent loops without relying on network volume mounts.

Applied to Fabrik specifically:

| Modal selling point | Does Fabrik's current shape benefit? |
|---|---|
| "Pure Python without managing container build pipelines or infrastructure registries" | **No** — every Fabrik service IS a built container (`compose.yaml`, multi-stage Dockerfile, scaffold-generated). Skipping containers would mean introducing a *different* deploy shape, not a faster one. |
| "Discrete functional calls" | **Partial** — our PG `SKIP LOCKED` job queue (`75-workers-jobs.md`) is unit-of-work-based, but the units are worker records, not Python functions. |
| "Modular, event-driven, or pipeline-based" | **Not the dominant shape today.** Realistic future workloads (chained inference: embed → classify → summarize) would fit, but none exist yet. |

| RunPod selling point | Does Fabrik's current shape benefit? |
|---|---|
| "Traditional container-based deployments" | **Strong yes** — direct 1:1 with Fabrik's existing service shape. |
| "Blend of persistent + serverless scaling" | **Yes** — covers both burst inference (serverless) and training one-offs (`--kind pod-* --max-lifetime`). |
| "Persistent disk state across long-running agent loops" | **Yes for training** — checkpoint dir survives between micro-batches. |

**Conclusion: RunPod for MVP is not just "best DX," it's architectural alignment with how every other Fabrik service is shaped.** Forcing a Modal-style decorator paradigm at this stage would introduce a parallel deploy concept (functions vs. containers) for one consumer, fragmenting the mental model.

**Phase 2 Modal trigger (explicit):** when a Fabrik service is built whose natural unit IS a Python function (embed-only API, classify-only API, or a chained inference pipeline where each step is <1s and stateless), revisit Modal. Until then, RunPod's serverless endpoint = container = uniform Fabrik shape.

---

## Verification plan

1. **Unit tests** — `pytest tests/orchestrator/test_gpu_rent.py -x` against mocked RunPodClient. Contract locked: 8+ tests covering create/destroy invariant, cost guards, dry-run, orphan-protection.
2. **Dry-run sanity** — `fabrik gpu rent --kind serverless --workload smoke --max-cost 1 --dry-run` returns plan (cost estimate, no API call made).
3. **Live serverless smoke** — `fabrik gpu rent --kind serverless --workload smoke-test --max-cost 1` — provisions a RunPod serverless endpoint, fires a single inference call, destroys. Compare elapsed wall-clock to vultr bare drill (~2 min target). Should land cheaper (<$0.05 typical).
4. **Live pod try/finally** — `fabrik gpu rent --kind pod-h100 --workload smoke-test --max-cost 2 --max-lifetime 1` with a synthetic `work_fn` that sleeps 30s. Pod auto-destroys at finally. Verify zero orphans via `fabrik gpu list`.
5. **Failure path** — `fabrik gpu rent` with a `work_fn` that raises mid-execution. Pod MUST still be destroyed (try/finally invariant). Verify via state file + provider.
6. **Cost-cap guard** — set `MAX_DAILY_GPU_COST=0.01`, attempt to rent — refuses BEFORE provider create. Verify no API call made.
7. **Reaper smoke** — orphan a pod (manually create via provider, no state entry), run `fabrik gpu reconcile` — reaper destroys the orphan.
8. **History audit** — every session above appends one line to `logs/gpu-rent-history.jsonl`; line is valid JSON, has `session_id`, `provider`, `cost_estimate_usd`, `success`, `wall_clock_seconds`.

---

## Cross-references

- [`.windsurf/rules/core/76-gpu-workers.md`](../../../.windsurf/rules/core/76-gpu-workers.md) — decision framework (the WHY this plan exists)
- [`src/fabrik/orchestrator/vultr_drill.py`](../../../src/fabrik/orchestrator/vultr_drill.py) — direct architectural template
- [`tests/orchestrator/test_vultr_drill.py`](../../../tests/orchestrator/test_vultr_drill.py) — test pattern to mirror
- [`docs/operations/disaster-recovery.md`](../../../docs/operations/disaster-recovery.md) — operational doc style
- [RunPod API docs](https://docs.runpod.io/api-reference/serverless-endpoints/POST/sls/create-endpoint) — provider API reference (verify before Phase 1)

---

## Lessons that pre-shaped this plan

- **Hub DR Drill #1 (2026-06-14) orphan** — `TaskStop` killed the python before try/finally ran, leaving a Vultr droplet alive. Recovery cost: ~$0.10 + 5 min of manual destroys. Same risk class for GPU pods at $4/hr — try/finally invariant is non-negotiable. See `logs/dr-drill-history.jsonl` for the incident.
- **`fabrik vultr drill` cost-cap pattern** — `--max-cost` refused before provider create-instance call. This is the cleanest gate; copy it directly.
- **Backrest `host-state` plan-id tagging bug** (Hub DR Drill #5) — assumptions about external-system contracts (tag names, API shapes) ALWAYS need a live probe, not a doc-read. For GPU: list providers' actual GPU type IDs before hardcoding `pod-h100` to a magic string.
- **`fabrik vultr list` reconciliation discipline** — state file vs. live API drift is inevitable; an explicit `list` command surfaces it daily before it becomes 30 stale pods.
