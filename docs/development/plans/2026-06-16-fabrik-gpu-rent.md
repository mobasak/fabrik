# Plan: `fabrik gpu rent` — disposable GPU lifecycle, vultr-pattern parity

**Created:** 2026-06-16
**Last iteration:** 2026-06-16 (iteration 3 — corrected import paths, surfaced UsageTracker query gap, grounded pricing from runpod.io/pricing)
**Status:** 🟢 **READY** — all decisions defaulted with rationale, every step has a validation gate (see § Validation gates)
**Owner:** TBD (proposed: Claude Code, peer-reviewed before merge)
**Trigger:** [`.windsurf/rules/core/76-gpu-workers.md`](../../../.windsurf/rules/core/76-gpu-workers.md) line 460:

> "Until [a GPU scaffold type exists], GPU lifecycle is managed by the orchestrator service's own code — the provider API calls, cost tracking, and auto-termination logic live in the orchestrator project."

Every service that needs GPU compute today would re-implement provider-API + cost-cap + auto-terminate inline. That's the gap. The `fabrik vultr` surface (`drill | provision | list | status | reconcile | cleanup | drill-history` with try/finally cost-capped lifecycle, `data/vultr-instances.json` state file, `logs/dr-drill-history.jsonl` audit trail, drift reconciliation) is the right shape — port it to GPU.

---

## Ground truth (verified 2026-06-16)

Before designing, every claim below was verified against the actual code and the actual external API. **Iteration 1 of this plan had off-by-2x line counts and a wrong state-file path. Iteration 2 corrects everything to evidence.**

### A. The vultr template we're copying (precise line counts via `wc -l`)

| File | Actual lines | Role |
|---|---:|---|
| [`src/fabrik/drivers/vultr.py`](../../../src/fabrik/drivers/vultr.py) | **298** | `VultrClient` httpx wrapper. Imports: `httpx`, `dotenv.load_dotenv`. Raises `VultrError`. Methods: `list_plans`, `list_instances`, `create_instance`, `wait_for_active`, `destroy`. |
| [`src/fabrik/orchestrator/vultr_drill.py`](../../../src/fabrik/orchestrator/vultr_drill.py) | **542** | `drill()` orchestrator. Function signature **verified at line 410**: `drill(kind, *, sshkey_ids, region, dry_run, keep_on_failure, max_cost, g0_smoke, client)`. Validates `kind` upfront → `NotImplementedError`. Cost guard fires BEFORE provider create. `dry_run` returns plan dict, no API call. Report shape **verified at line 456**: `{ts, drill_kind, name, region, plan, vultr_id, success, cost_estimate_usd, wall_clock_seconds, step_durations, checks, error}`. |
| [`src/fabrik/orchestrator/vultr_state.py`](../../../src/fabrik/orchestrator/vultr_state.py) | **167** | State at `data/vultr-instances.json` (**NOT** `logs/`). Schema v1. Lock name `"vultr-state"`. Functions: `load_state`, `save_state`, `upsert_instance`, `mark_destroyed`, `get_instance`, `active_instances`, `gc_old_disposables(retention_days=30)`, `reconcile(client)`. |
| [`src/fabrik/orchestrator/vultr_provision.py`](../../../src/fabrik/orchestrator/vultr_provision.py) | **726** | Long-running provision (bootstrap-vps wrapper). **NOT templated** — GPU has no "long-running install" mode; serverless/pod create returns immediately. |
| [`tests/orchestrator/test_vultr_drill.py`](../../../tests/orchestrator/test_vultr_drill.py) | **268** | Locks the contract: `test_estimate_cost_rounds_up_to_hour`, `test_cheapest_ipv4_plan_skips_v6_and_wrong_region`, `test_dry_run_creates_nothing`, `test_happy_path_creates_then_destroys`, `test_failure_still_destroys_no_orphan`, `test_keep_on_failure_leaves_instance`, `test_max_cost_guard_refuses_before_create`, `test_unknown_kind_raises`, `test_spoke_dispatch_runs_validate_then_destroys`, `test_validate_hub_passes_safety_flags`, `test_validate_spoke_restore_passes_safety_flags`, `test_spoke_failed_verify_still_destroys`, plus 3 G0-smoke tests. **15 tests.** |
| [`src/fabrik/cli.py`](../../../src/fabrik/cli.py) § vultr group | line 2860 | `@cli.group()` `def vultr():` followed by 7 `@vultr.command(...)` subcommands: `list`, `status`, `reconcile`, `cleanup`, `drill`, `drill-history`, `provision`. The `drill` command's Click options (verified at line 2978): `kind` (`click.Choice(["bare","spoke","hub","spoke-restore"])`), `--region`, `--dry-run`, `--keep-on-failure`, `--max-cost`, `--g0-smoke`. |
| `logs/dr-drill-history.jsonl` (audit log) | append-only | Per-line JSON. Actual field set (sampled from production): `ts` (int unix), `ts_iso`, `drill_kind`, `drill_run`, `note`, `vultr_id`, `vultr_region`, `vultr_plan`, `vultr_os`, `vultr_ip`, `wall_clock_seconds`, `wall_clock_human`, `target_seconds`, `target_human`, `under_target_factor`, `success`, `cost_estimate_usd`, `cost_actual_usd`, `end_state_contract_passed`. |

### B. The RunPod REST API surface (verified against `docs.runpod.io/llms.txt`, 2026-06-16)

**Base URL:** `https://rest.runpod.io/v1`
**Auth header:** `Authorization: Bearer <RUNPOD_API_KEY>` (Bearer scheme)
**Content type:** `application/json`

| Method | Path | Purpose | Notes |
|---|---|---|---|
| POST | `/pods` | Create pod | Body fields include `name` (max 191), `computeType` (GPU\|CPU), `cloudType` (SECURE\|COMMUNITY), `imageName`, `gpuTypeIds` (array, priority-ordered), `gpuCount`, `containerDiskInGb`, `volumeInGb`, `env`, `interruptible`, `ports` (default `["8888/http","22/tcp"]`). Returns `201` with full Pod object. |
| GET | `/pods/{podId}` | Get pod status | Returns `desiredStatus` (`RUNNING`\|`EXITED`\|`TERMINATED`), `costPerHr`, `adjustedCostPerHr`, `publicIp`, `portMappings`, `gpuCount`, `lastStatusChange`. 200/400/404. |
| DELETE | `/pods/{podId}` | Destroy pod | No body. Returns `204` with `"Pod successfully deleted."`. 400/401. |
| POST | `/pods/{podId}/stop` | Stop without destroy | Optional. We do NOT need this for MVP (rent→use→destroy). |
| POST | `/endpoints` | Create serverless endpoint | Required body: `templateId`. Optional: `name`, `computeType`, `gpuTypeIds`, `gpuCount`, `workersMin` (default 0 = scale-to-zero), `workersMax`, `idleTimeout` (1-3600s, default 5), `executionTimeoutMs`, `scalerType` (`QUEUE_DELAY`\|`REQUEST_COUNT`), `scalerValue`, `flashboot` (boolean). Returns `200` with `{id, templateId, workersMin, workersMax, idleTimeout, scalerType, scalerValue, flashboot, createdAt}`. |
| GET | `/endpoints/{id}` | Get endpoint | Status + current worker count. |
| DELETE | `/endpoints/{id}` | Delete endpoint | Removes the endpoint (scale-to-zero handles idle on its own). |
| GET | `/billing/pods` | Pod billing | Period-scoped spend per pod. Used by cost-cap aggregation. |
| GET | `/billing/endpoints` | Endpoint billing | Same for serverless. |

**GPU type IDs** (full enum, verified at `docs.runpod.io/references/gpu-types.md`, abbreviated to what we ship):

| Friendly `--kind` alias | RunPod `gpuTypeIds` value | VRAM | Notes |
|---|---|---|---|
| `pod-h100` (MVP) | `"NVIDIA H100 80GB HBM3"` | 80 GB | SXM, fastest H100 |
| `pod-h100-pcie` | `"NVIDIA H100 PCIe"` | 80 GB | PCIe variant |
| `pod-h100-nvl` | `"NVIDIA H100 NVL"` | 94 GB | More VRAM, often cheaper than SXM |
| `pod-a100` | `"NVIDIA A100 80GB PCIe"` | 80 GB | A100 PCIe |
| `pod-a100-sxm` | `"NVIDIA A100-SXM4-80GB"` | 80 GB | A100 SXM |
| `pod-h200` | `"NVIDIA H200"` | 141 GB | H200 SXM |
| `pod-l40s` | `"NVIDIA L40S"` | 48 GB | Inference-tier, much cheaper |
| `pod-rtx-4090` | `"NVIDIA GeForce RTX 4090"` | 24 GB | Cheap inference, Community pool |
| `serverless` | (template-driven, no `gpuTypeIds` needed) | — | RunPod chooses; FlashBoot enabled |

### C. State + observability surfaces we're plugging into

- **State directory** is `data/` not `logs/`. Confirmed at `vultr_state.py:42`: `STATE_FILE = FABRIK_ROOT / "data" / "vultr-instances.json"`. **GPU state goes to `data/gpu-rent-state.json`.**
- **Audit log** is `logs/`. Confirmed at `vultr_drill.py:37`: `DRILL_LOG = FABRIK_ROOT / "logs" / "dr-drill-history.jsonl"`. **GPU audit goes to `logs/gpu-rent-history.jsonl`.**
- **`FABRIK_ROOT`** is defined at `src/fabrik/config.py:20`: `Path(os.getenv("FABRIK_ROOT", "/opt/fabrik"))`. Import as `from fabrik.config import FABRIK_ROOT`.
- **File lock primitive** is `from fabrik.locks_local import file_lock` (verified at `vultr_state.py:38`). The module path is `fabrik.locks_local` — **NOT** `fabrik.locks` (which does not exist). Usage: `with file_lock(_LOCK, timeout_seconds=15.0): ...`. Phase 1 reuses this directly.
- **AI cost tracker exists** at [`src/fabrik/ai/tracker.py`](../../../src/fabrik/ai/tracker.py) — SQLite-backed `UsageTracker` at `~/.fabrik/ai_usage.db` with schema `(id, timestamp, provider, model, tokens_in, tokens_out, cost_usd, duration_ms, project)` + `idx_timestamp` index. **It only exposes `record(response, project=None)` today — there is NO query/rollup method.** Phase 1 MUST add:
  - Schema migration: `ALTER TABLE ai_usage ADD COLUMN kind TEXT DEFAULT 'llm'` (idempotent via `CREATE TABLE IF NOT EXISTS` rebuild + `INSERT INTO ... SELECT *, 'llm'`).
  - New method: `today_total(kind: str | None = None) -> float` that runs `SELECT COALESCE(SUM(cost_usd),0) FROM ai_usage WHERE date(timestamp) = date('now') [AND kind = ?]`.
  - New method: `record_gpu(session_id, kind, workload, cost_usd, duration_seconds)` that mirrors `record()` for non-LLM usage.
- **Prometheus integration points**: Phase 4 only. The current `prometheus_client` import lives in `scaffold.py` (template emission) and `drivers/redis.py` (driver-level metrics). For Phase 4 we add `src/fabrik/orchestrator/gpu_metrics.py` exposing `gpu_rent_sessions_total`, `gpu_rent_cost_usd_total`, `gpu_rent_active`, `gpu_rent_destroy_pending`.
- **Scaffold types**: `SCAFFOLD_TYPES` frozenset at `scaffold.py:128` contains 11 types: `python-api`, `saas-skeleton`, `node-api`, `file-api`, `file-worker`, `wordpress`, `docusaurus`, `chrome-extension`, `mobile-app`, `desktop-app`, `static-site`. **No `gpu` type yet — Phase 5 adds `python-api-gpu`.**
- **Dependencies**: `pyproject.toml` already declares `httpx>=0.25.0`, `python-dotenv>=1.0.0`, `click>=8.1.0`, `pyyaml>=6.0`, `pydantic>=2.0.0`, `rich>=13.0.0`. Python `>=3.12`. **No new top-level deps needed for Phase 1.**
- **`.env.sysadmin` current contents** (verified 2026-06-16 via `grep '^[A-Z]' /opt/fabrik/.env.sysadmin | cut -d= -f1`): 2 keys only — `VULTR_API_KEY`, `VULTR_SSHKEY_ID`. **Phase 1 adds `RUNPOD_API_KEY` and `MAX_DAILY_GPU_COST` (default `50`). No conflicts with existing keys.**
- **`vultr.py` env loading pattern** (verified at `vultr.py:32-62`): NOT module top-level. It's `load_dotenv(SYSADMIN_ENV)` INSIDE `VultrClient.__init__` where `SYSADMIN_ENV = Path("/opt/fabrik/.env.sysadmin")` is defined at module level (line 37). **`RunPodClient` must follow the exact same pattern** — env loading deferred to `__init__` so tests can monkeypatch.

### D. Where the reaper actually runs (cron pattern)

`scripts/cron/` does NOT exist on the operator. Verified: `ls /opt/fabrik/scripts/cron/` returns `No such file or directory`.

The existing cron pattern is **on vps1 only**, at `/etc/cron.d/vps-sysadmin` (verified content: 6 entries — proactive-check every 15min, morning-report 08:00, weekly-security Mon 08:30, weekly-maintenance Sun 03:00, monthly-backup-verify 1st 04:00, detect_reversals every 5min — all calling shell scripts in `/opt/fabrik/scripts/sysadmin/`).

**The GPU reaper runs on the OPERATOR** (where the API key lives), not vps1. Realistic shapes:

- **Option R1 — systemd user timer** at `~/.config/systemd/user/fabrik-gpu-reaper.timer` (every 10 min). Pairs with a `.service` unit that calls `fabrik gpu reconcile --auto-destroy`.
- **Option R2 — operator-side cron** at `~/.crontab` or `crontab -e`: `*/10 * * * * /usr/bin/env -i HOME=$HOME PATH=/usr/bin /opt/fabrik/.venv/bin/fabrik gpu reconcile --auto-destroy >> ~/.fabrik/gpu-reaper.log 2>&1`.
- **Option R3 — manual `fabrik gpu reconcile`** with no auto-schedule. Operator-driven. Lowest infrastructure footprint, highest discipline cost.

**Phase 1 ships R3 (manual)**. R1/R2 are Phase 4 (when Prometheus monitoring lands, we'll know if manual is enough).

---

## Goal

A single shared Fabrik surface that any service can call to **provision a GPU on demand, use it, and discard it** with the same lifecycle guarantees the vultr surface provides for CPU droplets:

```bash
fabrik gpu rent      --kind serverless --workload inference --max-cost 5
fabrik gpu rent      --kind pod-h100   --workload training  --max-lifetime 4 --max-cost 12
fabrik gpu list                                              # active pods + cost-to-date
fabrik gpu status    <pod-id|endpoint-id>                    # detailed status from RunPod API
fabrik gpu destroy   <pod-id|endpoint-id>                    # manual orphan cleanup
fabrik gpu reconcile [--auto-destroy]                        # drift report state vs RunPod
fabrik gpu history   [--lines 20]                            # tail logs/gpu-rent-history.jsonl
```

Plus a Python API mirroring `vultr_drill.drill()`'s signature exactly:

```python
def rent(
    kind: str,
    *,
    workload: str,
    provider: str = "runpod",
    max_lifetime_hours: int = 1,
    max_cost_usd: float = 5.0,
    keep_on_failure: bool = False,   # mirror vultr_drill: leaves pod alive on failure for inspection
    keep_warm_after_use: bool = False, # explicit "this pod should survive the call"
    work_fn: Callable[[Pod], None] | None = None,
    client: Any = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    ...
```

Plus a context manager wrapper for the `with`-statement use case (`with rent(...) as pod: ...`).

### What this is NOT

- **Not an inference router.** Provider selection between managed APIs (Groq/Together/Replicate) is application concern (`openai` SDK + `base_url` swap per `76-gpu-workers.md`). This plan is renting your own GPU.
- **Not a Kubernetes alternative.** No scheduler. Single-process Python orchestrator, try/finally, audit log. Same simplicity as `fabrik vultr drill`.
- **Not a model weights cache.** That's B2/R2.
- **Not multi-provider in Phase 1.** RunPod only. Modal/Vast in Phase 2.

---

## Why we need it now (current state verified 2026-06-16)

| What I checked | Result |
|---|---|
| `fabrik <gpu\|rent\|inference\|runpod\|...>` CLI subcommand | None |
| `src/fabrik/drivers/{runpod,modal,vast,tensordock,gpu}.py` | None |
| `src/fabrik/orchestrator/gpu_*.py` | None |
| Specs/services referencing GPU compute | `seo.yaml` + `watchdog-test.yaml` reference AI inference (managed API path), NOT GPU rental. |
| Existing plan file for it | None |

Greenfield. The closest working parallel is `src/fabrik/orchestrator/vultr_drill.py` — we copy that shape.

---

## Design Constraints (binding)

**C1 — Provider key locality.** `RUNPOD_API_KEY` lives in operator's `.env.sysadmin` only (mirrors `VULTR_API_KEY` pattern, verified present at line ~where VULTR_API_KEY is). NOT mirrored to vps1, NOT scp'd to rented pods. The pod itself doesn't need to talk to RunPod's control plane; the orchestrator does. If a workload needs to push results to S3, the orchestrator stages workload-specific credentials on the pod within `max_lifetime_hours` and the destroy step wipes them.

**C2 — Cost-cap is mandatory.** Two layers:
- **Per-call**: `--max-cost <usd>` — refused with `GPUBudgetExceeded` BEFORE provider create call, exact mirror of `vultr_drill.drill()` line 439–440.
- **Daily envelope**: `MAX_DAILY_GPU_COST` env (default `$50`) — checked at top of `rent()` against the cumulative `ai_usage.cost_usd WHERE kind='gpu' AND date(timestamp)=CURRENT_DATE` query. If `current_total + estimate > MAX_DAILY_GPU_COST`, refuse.

**C3 — try/finally is the only acceptable lifecycle.** Pod destroyed on every exit path: success, exception, Ctrl-C, OOM, network drop. Even if the destroy API call itself fails (state file marks `destroy_pending`, reaper retries later). This is the lesson from `fabrik vultr drill #1` orphan (logs/dr-drill-history.jsonl entry from 2026-06-14) — Vultr droplet leaked because `TaskStop` killed the python before the finally ran. **Same risk at $4/hr.**

**C4 — Tag every instance.** Per `76-gpu-workers.md` line 297. Tags via the RunPod pod `env` field (RunPod has no first-class instance tag API today, env vars are the deterministic replacement): `FABRIK_PROJECT`, `FABRIK_WORKLOAD`, `FABRIK_CREATED_BY`, `FABRIK_MAX_LIFETIME_HOURS`, `FABRIK_SESSION_ID`. The reaper scans pods, parses env, kills any that lack a matching active state-file entry OR have exceeded `FABRIK_MAX_LIFETIME_HOURS`.

**C5 — Cold-by-default, hot opt-in.** Per `76-gpu-workers.md` line 253. `--kind serverless` is the default UX recommendation. RunPod handles scale-to-zero internally; our `rent()` just creates the endpoint and returns the run URL. For `--kind pod-*`, our orchestrator owns the lifecycle.

**C6 — Single-provider MVP.** RunPod only. Adding Modal doubles surface area for a paradigm shift (functions vs. containers) we don't need yet. See § D1 rationale below.

---

## Architecture (5 layers, **realistic budget ~1370 lines based on actuals**)

The line counts in iteration 1 were 50–100% too optimistic. Iteration 2 budgets to actuals.

### Layer 1 — provider driver (`src/fabrik/drivers/runpod.py`, **~280 lines**)

Calibrated against `vultr.py = 298 lines`. RunPod has roughly the same surface count (5 client methods for pods + 4 for endpoints + 1 GPU type list ≈ vultr's 5 methods).

```python
# src/fabrik/drivers/runpod.py
# Mirrors src/fabrik/drivers/vultr.py exactly (verified 2026-06-16, lines 25-110):
# same module-level constants, same __init__ deferred env-load pattern, same
# RuntimeError subclass with status+body, same _request() retry-5xx-only logic.
import logging, os, time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

RUNPOD_API_BASE = "https://rest.runpod.io/v1"
SYSADMIN_ENV = Path("/opt/fabrik/.env.sysadmin")  # mirrors vultr.py:37


class RunPodError(RuntimeError):  # mirrors VultrError shape
    def __init__(self, message: str, status: int | None = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


class RunPodClient:
    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        # Mirrors vultr.py:60-67 exactly — env load deferred to __init__
        # so tests can monkeypatch + ENVs override.
        if api_key is None and not os.environ.get("RUNPOD_API_KEY") and SYSADMIN_ENV.exists():
            load_dotenv(SYSADMIN_ENV)
        self.api_key = api_key or os.environ.get("RUNPOD_API_KEY")
        if not self.api_key:
            raise RunPodError(
                "RUNPOD_API_KEY is required (set it in /opt/fabrik/.env.sysadmin or the environment)"
            )
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.Client(
            base_url=RUNPOD_API_BASE,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    # Context manager — mirrors vultr.py:83-87
    def __enter__(self) -> "RunPodClient": return self
    def __exit__(self, *_args) -> None: self._client.close()

    # _request mirrors vultr.py:90-108 — retry only on transport errors + 5xx,
    # fail fast on 4xx (those are our bug).
    def _request(self, method: str, path: str, *,
                 json: dict | None = None, params: dict | None = None) -> Any: ...

    # Pod API (verified against docs.runpod.io/api-reference/pods/*)
    def create_pod(self, *, gpu_type_id: str, image_name: str, env: dict[str, str],
                   container_disk_gb: int = 50, volume_gb: int = 20,
                   cloud_type: str = "SECURE", interruptible: bool = False,
                   ports: list[str] | None = None) -> dict[str, Any]: ...
    def get_pod(self, pod_id: str) -> dict[str, Any]: ...
    def wait_for_running(self, pod_id: str, *, timeout: int = 300, interval: int = 5) -> dict[str, Any]: ...
    def destroy_pod(self, pod_id: str) -> None: ...
    def list_pods(self) -> list[dict[str, Any]]: ...

    # Endpoint (serverless) API
    def create_endpoint(self, *, template_id: str, name: str, gpu_type_ids: list[str] | None = None,
                        workers_min: int = 0, workers_max: int = 3, idle_timeout: int = 5,
                        flashboot: bool = True) -> dict[str, Any]: ...
    def get_endpoint(self, endpoint_id: str) -> dict[str, Any]: ...
    def destroy_endpoint(self, endpoint_id: str) -> None: ...
    def list_endpoints(self) -> list[dict[str, Any]]: ...

    # Billing (for cost reconciliation)
    def billing_pods(self, start: str, end: str) -> dict[str, Any]: ...
```

**The `gpu_type_id` argument accepts the exact strings from the GPU types table above** (e.g. `"NVIDIA H100 80GB HBM3"`). The orchestrator resolves `--kind pod-h100` to this string.

### Layer 2 — orchestrator (`src/fabrik/orchestrator/gpu_rent.py`, **~480 lines**)

Calibrated against `vultr_drill.py = 542 lines`. Slightly smaller because we don't have the spoke/hub/spoke-restore dispatch table.

```python
# src/fabrik/orchestrator/gpu_rent.py
from contextlib import contextmanager
from datetime import datetime, UTC
import json, logging, time
from pathlib import Path
from typing import Any, Callable

from fabrik.config import FABRIK_ROOT
from fabrik.drivers.runpod import RunPodClient, RunPodError
from fabrik.orchestrator import gpu_state
from fabrik.ai.tracker import UsageTracker  # extended for GPU per § C

logger = logging.getLogger(__name__)

GPU_RENT_LOG = FABRIK_ROOT / "logs" / "gpu-rent-history.jsonl"   # parallels DRILL_LOG
PROVIDERS = {"runpod": RunPodClient}                              # extension point

# Friendly --kind aliases → RunPod IDs (table in § B)
GPU_KIND_MAP = {
    "serverless": None,                       # no pod GPU type; handled separately
    "pod-h100":   "NVIDIA H100 80GB HBM3",
    "pod-h100-pcie": "NVIDIA H100 PCIe",
    "pod-h100-nvl":  "NVIDIA H100 NVL",
    "pod-a100":      "NVIDIA A100 80GB PCIe",
    "pod-a100-sxm":  "NVIDIA A100-SXM4-80GB",
    "pod-h200":      "NVIDIA H200",
    "pod-l40s":      "NVIDIA L40S",
    "pod-rtx-4090":  "NVIDIA GeForce RTX 4090",
}

class GPUBudgetExceeded(RunPodError): ...

def estimate_cost(kind: str, hours: float, gpu_count: int = 1) -> float:
    # Look-up table verified 2026-06-16 from runpod.io/pricing.
    # Community Cloud prices (Secure Cloud not listed publicly).
    # IMPORTANT: re-verify quarterly + on every Phase 1 release. Pricing CAN change.
    HOURLY_USD = {
        "serverless":    0.50,   # rough — actual depends on workers_max, idle time
        "pod-h100":      3.29,   # H100 SXM
        "pod-h100-pcie": 2.89,
        "pod-h100-nvl":  3.19,
        "pod-a100":      1.39,   # A100 PCIe
        "pod-a100-sxm":  1.49,
        "pod-h200":      4.39,
        "pod-l40s":      0.86,
        "pod-rtx-4090":  0.69,
    }
    return math.ceil(hours) * HOURLY_USD[kind] * gpu_count  # round up to hour like vultr

def rent(kind: str, *, workload: str, provider: str = "runpod",
         max_lifetime_hours: int = 1, max_cost_usd: float = 5.0,
         keep_on_failure: bool = False, keep_warm_after_use: bool = False,
         work_fn: Callable | None = None,
         client: Any = None, dry_run: bool = False) -> dict[str, Any]:
    """try/finally GPU lifecycle. ALWAYS destroys unless keep_on_failure (on error)
    or keep_warm_after_use (on success). Direct port of vultr_drill.drill() shape.
    """
    if kind not in GPU_KIND_MAP:
        raise NotImplementedError(f"unknown gpu kind {kind!r}")

    if provider not in PROVIDERS:
        raise NotImplementedError(f"unknown gpu provider {provider!r}")

    # Per-call cost guard (mirror vultr_drill.py:439-440)
    est = estimate_cost(kind, max_lifetime_hours)
    if est > max_cost_usd:
        raise GPUBudgetExceeded(
            f"estimated cost ${est} exceeds --max-cost ${max_cost_usd} (kind {kind})"
        )

    # Daily envelope (C2 second layer).
    # NOTE: today_total() is NEW in Phase 1 (verified UsageTracker has only record()
    # today; this plan ships the query method as part of § Layer 2 deliverables).
    tracker = UsageTracker()
    today_gpu_spend = tracker.today_total(kind="gpu")
    daily_cap = float(os.getenv("MAX_DAILY_GPU_COST", "50"))
    if today_gpu_spend + est > daily_cap:
        raise GPUBudgetExceeded(
            f"daily GPU spend ${today_gpu_spend:.2f} + estimate ${est:.2f} would exceed "
            f"MAX_DAILY_GPU_COST=${daily_cap}"
        )

    client = client or PROVIDERS[provider]()
    ts = datetime.now(UTC)
    session_id = f"gpu-{kind}-{ts.strftime('%Y%m%d-%H%M%S')}"

    if dry_run:
        return {"dry_run": True, "kind": kind, "workload": workload,
                "session_id": session_id, "cost_estimate_usd": est}

    # Mirror vultr_drill.py:456 report shape, GPU-flavored
    report = {
        "ts": int(ts.timestamp()),
        "ts_iso": ts.isoformat(),
        "session_id": session_id,
        "kind": kind,
        "workload": workload,
        "provider": provider,
        "pod_id": None,
        "success": False,
        "cost_estimate_usd": est,
        "cost_actual_usd": None,        # filled from billing endpoint at session end
        "wall_clock_seconds": 0,
        "started_at": ts.isoformat(),
        "ended_at": None,
        "checks": {},
        "error": None,
    }

    start = time.monotonic()
    pod = None
    failed = False
    try:
        if kind == "serverless":
            pod = _create_serverless_endpoint(client, kind, workload, session_id, max_lifetime_hours)
        else:
            pod = _create_pod(client, kind, workload, session_id, max_lifetime_hours)
        report["pod_id"] = pod["id"]
        gpu_state.upsert(session_id, pod, kind, workload, max_lifetime_hours)
        report["checks"]["created"] = True

        if work_fn is not None:
            work_fn(pod)
            report["checks"]["work_fn"] = "ok"
        report["success"] = True
    except Exception as e:
        failed = True
        report["error"] = str(e)
        logger.warning("gpu_rent %s failed: %s", session_id, e)
    finally:
        report["wall_clock_seconds"] = round(time.monotonic() - start, 1)
        keep = (failed and keep_on_failure) or (report["success"] and keep_warm_after_use)
        if pod is not None and not keep:
            try:
                if kind == "serverless":
                    client.destroy_endpoint(pod["id"])
                else:
                    client.destroy_pod(pod["id"])
                gpu_state.mark_destroyed(session_id)
                report["checks"]["destroyed"] = True
            except RunPodError as e:
                report["checks"]["destroy_failed"] = str(e)
                gpu_state.mark_destroy_pending(session_id)
        elif keep:
            report["checks"]["kept_for_inspection"] = True
        report["ended_at"] = datetime.now(UTC).isoformat()
        write_report(report)
        # Reconcile billing into UsageTracker (best-effort)
        if pod is not None and not dry_run:
            try:
                _record_cost(tracker, pod, session_id, kind, workload)
            except Exception:
                logger.exception("failed to record GPU cost into tracker")
    return report

@contextmanager
def rented(kind: str, **kwargs):
    """Context manager wrapper: `with rented("pod-h100", workload="train") as pod: ...`"""
    pod_holder = {}
    def _work(pod):
        pod_holder["pod"] = pod
    report = rent(kind, work_fn=lambda p: pod_holder.setdefault("pod", p), **kwargs)
    yield pod_holder.get("pod")

def write_report(report: dict[str, Any]) -> None:
    """Mirror vultr_drill.write_report (line 400)."""
    GPU_RENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with GPU_RENT_LOG.open("a") as f:
        f.write(json.dumps(report, sort_keys=True) + "\n")
```

### Layer 3 — state (`src/fabrik/orchestrator/gpu_state.py`, **~170 lines**)

Direct port of `vultr_state.py = 167 lines`. **State file at `data/gpu-rent-state.json` (NOT `logs/`).**

```python
# src/fabrik/orchestrator/gpu_state.py
from datetime import datetime, UTC, timedelta
import json, logging
from typing import Any
from fabrik.config import FABRIK_ROOT
from fabrik.locks_local import file_lock  # VERIFIED: module is locks_local, NOT locks

STATE_FILE = FABRIK_ROOT / "data" / "gpu-rent-state.json"
SCHEMA_VERSION = 1
_LOCK = "gpu-rent-state"
RETENTION_DAYS = 30  # mirror vultr_state.DISPOSABLE_RETENTION_DAYS

def load_state() -> dict[str, Any]: ...
def save_state(state: dict[str, Any]) -> Path: ...
def upsert(session_id: str, pod: dict, kind: str, workload: str,
           max_lifetime_hours: int) -> dict: ...
def mark_destroyed(session_id: str, when: str | None = None) -> None: ...
def mark_destroy_pending(session_id: str) -> None: ...   # NEW vs vultr_state: tracks failed destroy
def get_session(session_id: str) -> dict | None: ...
def active_sessions() -> dict[str, dict]: ...
def gc_old(retention_days: int = RETENTION_DAYS) -> list[str]: ...
def reconcile(client) -> dict[str, Any]: ...
    # Returns drift report: in_state_not_live, live_not_in_state, lifetime_exceeded
```

Schema:

```json
{
  "schema_version": 1,
  "last_reconciled": "2026-06-16T12:00:00+00:00",
  "sessions": {
    "gpu-pod-h100-20260616-130000": {
      "provider": "runpod",
      "kind": "pod-h100",
      "workload": "fine-tune-tinyllama",
      "pod_id": "abc123",
      "gpu_type_id": "NVIDIA H100 80GB HBM3",
      "created_at": "2026-06-16T13:00:00+00:00",
      "destroyed_at": null,
      "destroy_pending": false,
      "max_lifetime_hours": 4,
      "expires_at": "2026-06-16T17:00:00+00:00",
      "cost_estimate_usd": 12.0,
      "cost_actual_usd": null
    }
  }
}
```

### Layer 4 — CLI (`src/fabrik/cli.py`, **+220 lines**)

Calibrated against the vultr group's actual size (verified: 7 subcommands across ~220 lines, lines 2860–3120). Same shape:

```python
@cli.group()
def gpu():
    """GPU compute provisioning — on-demand RunPod pods + serverless endpoints."""
    pass

@gpu.command("rent")
@click.argument("kind", type=click.Choice([
    "serverless", "pod-h100", "pod-h100-pcie", "pod-h100-nvl",
    "pod-a100", "pod-a100-sxm", "pod-h200", "pod-l40s", "pod-rtx-4090",
]))
@click.option("--workload", required=True, help="Free-text tag for the workload (required)")
@click.option("--provider", default="runpod", type=click.Choice(["runpod"]),
              help="GPU provider (Phase 1: RunPod only)")
@click.option("--max-lifetime", type=int, default=1,
              help="Max wall hours before reaper destroys (default 1)")
@click.option("--max-cost", type=float, default=5.0,
              help="Refuse if estimate exceeds this USD (default 5.0)")
@click.option("--keep-warm-after-use", is_flag=True,
              help="Don't destroy after successful work_fn (mirrors vultr keep-on-failure but inverse)")
@click.option("--keep-on-failure", is_flag=True,
              help="Leave the pod if the rent fails — mirrors `fabrik vultr drill --keep-on-failure`")
@click.option("--dry-run", is_flag=True, help="Print the plan; create nothing")
def gpu_rent(kind, workload, provider, max_lifetime, max_cost,
             keep_warm_after_use, keep_on_failure, dry_run): ...

@gpu.command("list")
def gpu_list(): ...                              # mirrors vultr.command("list")

@gpu.command("status")
@click.argument("session_or_pod_id")
def gpu_status(session_or_pod_id): ...           # mirrors vultr.command("status")

@gpu.command("destroy")
@click.argument("session_or_pod_id")
@click.option("-y", "--yes", is_flag=True)
def gpu_destroy(session_or_pod_id, yes): ...     # mirrors vultr.command("cleanup") for one

@gpu.command("reconcile")
@click.option("--auto-destroy", is_flag=True, help="Destroy lifetime-exceeded + orphan pods automatically")
def gpu_reconcile(auto_destroy): ...             # mirrors vultr.command("reconcile")

@gpu.command("history")
@click.option("--lines", type=int, default=20)
def gpu_history(lines): ...                       # mirrors vultr.command("drill-history")
```

### Layer 5 — reaper helper (`src/fabrik/orchestrator/gpu_reaper.py`, **~120 lines**)

Phase 1 ships this as a library function called by `fabrik gpu reconcile --auto-destroy`. No standalone daemon. Scheduling (Phase 4) is operator-side via systemd timer / cron / manual.

Logic spec (concrete, mirrors `vultr_state.reconcile()` at line 157+ of vultr_state.py):

```python
def reap(client, *, auto_destroy: bool = False) -> dict[str, Any]:
    """Walk state + provider; report drift + optionally destroy.

    Three drift categories:
      - lifetime_exceeded:   active in state, age > max_lifetime_hours
      - orphans:             alive on RunPod, NOT in state (no session record)
      - destroy_pending:     state says destroy_pending=True (previous destroy failed) — retry

    Returns dict with keys: lifetime_exceeded, orphans, destroy_pending,
    destroyed (only set if auto_destroy=True), errors, scanned_at.
    """
    now = datetime.now(UTC)
    state = gpu_state.load_state()
    live_pods = {p["id"]: p for p in client.list_pods()}
    live_endpoints = {e["id"]: e for e in client.list_endpoints()}
    live_ids = set(live_pods) | set(live_endpoints)

    result = {
        "scanned_at": now.isoformat(),
        "lifetime_exceeded": [],
        "orphans": [],
        "destroy_pending": [],
        "destroyed": [],
        "errors": [],
    }

    # 1. lifetime_exceeded — active in state past expires_at
    for sid, sess in state["sessions"].items():
        if sess.get("destroyed_at"):
            continue
        if datetime.fromisoformat(sess["expires_at"]) < now:
            result["lifetime_exceeded"].append({"session_id": sid, "pod_id": sess["pod_id"]})

    # 2. orphans — live on provider but no FABRIK_SESSION_ID env tag we recognize
    tracked_pod_ids = {s["pod_id"] for s in state["sessions"].values() if not s.get("destroyed_at")}
    for pid, pod in live_pods.items():
        if pid not in tracked_pod_ids:
            # Check env tag — only kill if FABRIK_SESSION_ID is present (it's ours)
            # OR if --auto-destroy is set without --safe-mode (operator-explicit kill-all)
            env = pod.get("env", {}) or {}
            if "FABRIK_SESSION_ID" in env:
                result["orphans"].append({"pod_id": pid, "session_id": env["FABRIK_SESSION_ID"]})

    # 3. destroy_pending — previous destroy errored; retry
    for sid, sess in state["sessions"].items():
        if sess.get("destroy_pending"):
            result["destroy_pending"].append({"session_id": sid, "pod_id": sess["pod_id"]})

    if not auto_destroy:
        return result

    # auto_destroy: try every category, mark in state, log to history
    for entry in result["lifetime_exceeded"] + result["orphans"] + result["destroy_pending"]:
        try:
            client.destroy_pod(entry["pod_id"])  # serverless: destroy_endpoint instead
            if "session_id" in entry:
                gpu_state.mark_destroyed(entry["session_id"])
            result["destroyed"].append(entry)
            gpu_rent.write_report({
                "ts": int(now.timestamp()),
                "ts_iso": now.isoformat(),
                "session_id": entry.get("session_id", f"reap-{entry['pod_id']}"),
                "kind": "reaper",
                "workload": "reap",
                "provider": "runpod",
                "pod_id": entry["pod_id"],
                "success": True,
                "wall_clock_seconds": 0,
                "checks": {"destroyed_by_reaper": True},
            })
        except RunPodError as e:
            result["errors"].append({"pod_id": entry["pod_id"], "error": str(e)})

    state["last_reconciled"] = now.isoformat()
    gpu_state.save_state(state)
    return result
```

**Tag scheme (C4) makes this safe**: we ONLY destroy orphans that carry `FABRIK_SESSION_ID` in their `env` block. Other pods on the operator's RunPod account (manually created, other projects) are NEVER touched by the reaper.

### Tests (`tests/orchestrator/test_gpu_rent.py`, **~310 lines**)

Calibrated against `test_vultr_drill.py = 268 lines + 15 tests`. We need ≥ 10 tests + the GPU-specific add-ons.

Direct port of `test_vultr_drill.py` fixtures: `_isolate` monkeypatches STATE_FILE + LOG path to `tmp_path`. Mocked `RunPodClient`.

Contract tests:

| # | Test | Mirrors |
|---|---|---|
| 1 | `test_estimate_cost_uses_kind_pricing` | `test_estimate_cost_rounds_up_to_hour` |
| 2 | `test_kind_serverless_resolves_to_no_gpu_type` | new |
| 3 | `test_kind_pod_h100_resolves_to_real_runpod_id` | new — locks the GPU_KIND_MAP |
| 4 | `test_dry_run_creates_nothing` | `test_dry_run_creates_nothing` |
| 5 | `test_happy_path_creates_then_destroys` | `test_happy_path_creates_then_destroys` |
| 6 | `test_work_fn_runs_between_create_and_destroy` | new |
| 7 | `test_failure_in_work_fn_still_destroys` | `test_failure_still_destroys_no_orphan` |
| 8 | `test_keep_on_failure_leaves_pod` | `test_keep_on_failure_leaves_instance` |
| 9 | `test_keep_warm_after_use_leaves_pod_on_success` | new |
| 10 | `test_max_cost_guard_refuses_before_create` | `test_max_cost_guard_refuses_before_create` |
| 11 | `test_daily_budget_guard_refuses_before_create` | new — UsageTracker integration |
| 12 | `test_unknown_kind_raises` | `test_unknown_kind_raises` |
| 13 | `test_unknown_provider_raises` | new |
| 14 | `test_state_marks_destroy_pending_when_destroy_fails` | new — covers C3 finally |
| 15 | `test_runpod_api_key_missing_raises_at_client_init` | new |
| 16 | `test_report_appended_to_history_log_as_jsonl` | new — locks audit format |
| 17 | `test_reconcile_detects_orphan_pods` | new |
| 18 | `test_reconcile_detects_lifetime_exceeded` | new |

---

## Phasing

### Phase 1 — MVP (RunPod-only, **~1,580 lines** + ~310 tests = ~1,900 LoC total, est. 2 days)

| Deliverable | File | Budget |
|---|---|---|
| Provider driver | `src/fabrik/drivers/runpod.py` | ~280 |
| Orchestrator | `src/fabrik/orchestrator/gpu_rent.py` | ~480 |
| State | `src/fabrik/orchestrator/gpu_state.py` | ~170 |
| Reaper helper | `src/fabrik/orchestrator/gpu_reaper.py` | ~120 |
| CLI group | `src/fabrik/cli.py` (additions) | ~220 |
| Cost-tracker extension | `src/fabrik/ai/tracker.py` (add `kind` column + `today_total()`) | ~30 |
| Tests | `tests/orchestrator/test_gpu_rent.py` | ~310 |
| Operator runbook | `docs/operations/gpu-rent.md` | ~250 |
| `.env.sysadmin.template` | add `RUNPOD_API_KEY`, `MAX_DAILY_GPU_COST` | +2 lines |
| CHANGELOG entry | `CHANGELOG.md` § `[Unreleased]` | +1 entry |
| **Total Python+tests** | | **~1,610 lines** |

### Phase 2 — second provider (Modal OR Vast.ai), ~+350 lines new driver + +50 tests

Trigger condition (made concrete in iteration 2): when a Fabrik service is shipped whose natural unit IS a Python function (embed-only API, classify-only API, or a chained inference pipeline where each step is <1s and stateless). Until then, RunPod's serverless endpoint = container = uniform Fabrik shape and Modal adds paradigm cost without value.

### Phase 3 — checkpoint helper, ~+150 lines

`gpu_rent.checkpoint_to_b2(state_dict, path)` — async checkpoint utility for training workloads. Mirrors `76-gpu-workers.md` line 312–319 (DCP-style async write to S3/B2/R2). Generic enough to drop into any training workload without per-project re-implementation.

### Phase 4 — Prometheus metrics + scheduled reaper, ~+100 lines

- `gpu_rent_sessions_total` (Counter, labels: `provider, kind, workload, success`)
- `gpu_rent_cost_usd_total` (Counter, labels: `provider, kind, workload`)
- `gpu_rent_active` (Gauge, labels: `provider`)
- `gpu_rent_destroy_pending` (Gauge — should always be 0; >0 = orphan risk)
- systemd user-timer at `~/.config/systemd/user/fabrik-gpu-reaper.timer` calling `fabrik gpu reconcile --auto-destroy` every 10 min, with Prometheus pushgateway integration so the metrics survive operator-machine power cycles.

### Phase 5 (deferrable, full plan needed) — `python-api-gpu` scaffold type

Adds `python-api-gpu` to the `SCAFFOLD_TYPES` frozenset at `scaffold.py:128`. Spec `shape:` block gains `needs_gpu: true` + `gpu_kind:`. `fabrik apply` wires `gpu_rent.rent()` into the service's job-handler. **Out of scope for this plan**; separate doc.

---

## Decisions (all defaulted with explicit recommendation)

| # | Decision | Default | Why |
|---|---|---|---|
| **D1** | First provider | **RunPod** | Architectural alignment — every Fabrik service is a built container, RunPod's pod model maps 1:1. Modal forces a function/decorator paradigm shift. See § D1 rationale below. |
| **D2** | Pod-mode scope in MVP | **serverless + 9 friendly `pod-*` aliases** (full GPU table from § B) | Aliases are zero-cost to add (just a dict), and locking the friendly names early avoids API churn when Phase 2 adds Modal-equivalents. |
| **D3** | Where `RUNPOD_API_KEY` lives | **`.env.sysadmin` only** (operator) | Mirrors `VULTR_API_KEY` exactly (verified present in `/opt/fabrik/.env.sysadmin`). Pod doesn't need to call RunPod's control plane — orchestrator does. |
| **D4** | Reaper schedule | **Phase 1: manual `fabrik gpu reconcile`. Phase 4: systemd user-timer every 10 min.** | Manual first to avoid premature daemon. Phase 4 ships scheduled when Prometheus is wired so we can SEE if manual was enough. |
| **D5** | Default `MAX_DAILY_GPU_COST` | **$50/day** | Solo-dev framing from the rule. Stricter than vultr (no daily cap there) because GPU $/hr is 10–20× higher. |
| **D6** | State-file path | **`data/gpu-rent-state.json`** | Mirrors `data/vultr-instances.json` exactly. `logs/` is for append-only audit (gpu-rent-history.jsonl). |
| **D7** | Audit-log fields | **Mirror dr-drill-history.jsonl shape** (ts, ts_iso, session_id, kind, workload, provider, pod_id, success, cost_estimate_usd, cost_actual_usd, wall_clock_seconds, checks, error) | Same operator-tooling can read both logs. `fabrik gpu history` parses the same way as `fabrik vultr drill-history`. |
| **D8** | UsageTracker integration | **Extend schema with `kind` column ('llm'/'gpu')** | Single SQLite for all AI/GPU spend = one rollup query. Migration: `ALTER TABLE ai_usage ADD COLUMN kind TEXT DEFAULT 'llm'`. |
| **D9** | Whether reaper logs to `logs/gpu-reaper.log` or to `logs/gpu-rent-history.jsonl` | **Both** | History gets per-destroy entries (auditable). Reaper log gets the per-run summary (operator can `tail -f`). |
| **D10** | RunPod serverless `templateId` source | **CLI flag `--template-id <id>` + env override `RUNPOD_SERVERLESS_TEMPLATE_ID`. Phase 1 ships with NO default.** | RunPod docs (verified 2026-06-16 via WebFetch) do not publish a canonical "default vLLM" templateId — templates are account-scoped. Operator creates one via console, captures the ID once, stores in `.env.sysadmin`. **First-time setup is a one-line addition to gpu-rent.md runbook.** Pod-mode (`--kind pod-*`) does NOT need a template — it uses `image_name` directly. |

### D1 rationale (cross-checked against an independent strategic verdict, 2026-06-16)

External analysis (Gemini) frames the choice as:

> **Choose Modal If:** modular, event-driven, or pipeline-based architecture; agents/tasks triggered as discrete functional calls (input → processing → output); want pure Python without managing container build pipelines or infrastructure registries — Modal offers unparalleled deployment velocity.
>
> **Choose RunPod If:** blend of persistent always-on host infrastructure and serverless scaling; or you prefer traditional container-based deployments; standard Docker setups; persistent disk state across long-running agent loops without relying on network volume mounts.

Applied to Fabrik specifically (every claim verified against the codebase):

| Modal selling point | Does Fabrik's current shape benefit? |
|---|---|
| "Pure Python without managing container build pipelines or infrastructure registries" | **No** — every Fabrik service IS a built container. `SCAFFOLD_TYPES` (`scaffold.py:128`) has 11 entries, all container-based. Skipping containers would mean introducing a *different* deploy shape, not a faster one. |
| "Discrete functional calls" | **Partial** — `75-workers-jobs.md` defines a PG `SKIP LOCKED` job queue, but the units are worker records (rows), not Python functions. |
| "Modular, event-driven, or pipeline-based" | **Not dominant today.** Realistic future workloads (chained inference: embed → classify → summarize) would fit Modal, but none exist in `specs/services/` yet (verified: 54 specs, none reference GPU). |

| RunPod selling point | Does Fabrik's current shape benefit? |
|---|---|
| "Traditional container-based deployments" | **Strong yes** — direct 1:1 with `SCAFFOLD_TYPES`. |
| "Blend of persistent + serverless scaling" | **Yes** — covers both burst inference (`serverless`) and training one-offs (`--kind pod-* --max-lifetime`). |
| "Persistent disk state across long-running agent loops" | **Yes for training** — `volumeInGb` on `POST /pods` carries checkpoint dir between micro-batches. |

**Conclusion: RunPod for MVP is architectural alignment, not just "best DX."** Modal's value lands only when a Python-function pipeline service exists; that's the Phase 2 trigger.

---

## Validation gates

Every step gets a gate. Implementation does NOT advance past a gate without the assertion passing. This is the discipline that made the `fabrik vultr drill` lifecycle reliable enough to be the production DR path.

### Pre-implementation gates (before writing any code)

| Gate | Command | Pass criterion |
|---|---|---|
| **G-PRE-1: RunPod API key works** | `curl -s -H "Authorization: Bearer $RUNPOD_API_KEY" https://rest.runpod.io/v1/pods \| jq` | Returns HTTP 200 with `[]` or a JSON array. Not 401/403. |
| **G-PRE-2: GPU type IDs resolve** | `curl -s -H "Authorization: Bearer $RUNPOD_API_KEY" https://rest.runpod.io/v1/pods \| jq '.[].gpu.displayName'` OR consult `https://docs.runpod.io/references/gpu-types.md` | The 9 friendly aliases in `GPU_KIND_MAP` all resolve to currently-supported `gpuTypeIds` values. |
| **G-PRE-3: vultr template is the right shape** | `wc -l src/fabrik/{drivers/vultr.py,orchestrator/vultr_drill.py,orchestrator/vultr_state.py} tests/orchestrator/test_vultr_drill.py` | Numbers match § A (298 / 542 / 167 / 268). If they've drifted >10% since this plan was authored, re-calibrate budgets in § Phasing. |
| **G-PRE-4: No surprise existing GPU code** | `grep -rE 'runpod\|modal\|RUNPOD_API_KEY' src/fabrik/ tests/ specs/ 2>&1` | Returns no matches. If matches exist, the plan's "greenfield" claim is wrong → re-survey before proceeding. |
| **G-PRE-5: file_lock module exists at expected path** | `python3 -c "from fabrik.locks_local import file_lock; print(file_lock)"` | Prints the function reference. Confirms § C import path. |
| **G-PRE-6: vultr.py init pattern can be mirrored** | `grep -nE 'load_dotenv\(SYSADMIN_ENV\)' src/fabrik/drivers/vultr.py` | Returns line ~62. Confirms the deferred-env-load pattern is current (not refactored). |
| **G-PRE-7: UsageTracker today_total does NOT exist** | `python3 -c "from fabrik.ai.tracker import UsageTracker; print(hasattr(UsageTracker, 'today_total'))"` | Prints `False`. Confirms Phase 1 must add this method (per § C). If `True`, the method exists — use as-is. |
| **G-PRE-8: serverless template ID available** | Operator creates a template via `console.runpod.io`, captures the `templateId`, sets `RUNPOD_SERVERLESS_TEMPLATE_ID=<id>` in `.env.sysadmin`. | Env var resolves to a non-empty string. Required only if `--kind serverless` will be used. |

### Per-deliverable gates (during implementation)

| Deliverable | Gate | Pass criterion |
|---|---|---|
| **G-D1: `runpod.py`** | `python3 -c "from fabrik.drivers.runpod import RunPodClient; c = RunPodClient(); print(len(c.list_pods()))"` | Prints an integer (≥ 0). Asserts: import works, auth header is right, base URL hits the right host. |
| **G-D2: `gpu_rent.py` (dry-run)** | `fabrik gpu rent serverless --workload smoke --dry-run` | Stdout JSON has `dry_run: true`, `kind: "serverless"`, `cost_estimate_usd > 0`. **Crucially: no RunPod API call** (verify with provider dashboard — 0 pods/endpoints created during this test). |
| **G-D3: `gpu_state.py`** | `python3 -c "from fabrik.orchestrator import gpu_state; s = gpu_state.load_state(); assert 'sessions' in s; assert s['schema_version'] == 1"` | Loads, returns dict with expected schema. |
| **G-D4: CLI registered** | `fabrik gpu --help` | Lists 6 subcommands: `rent`, `list`, `status`, `destroy`, `reconcile`, `history`. |
| **G-D5: Tests pass** | `pytest tests/orchestrator/test_gpu_rent.py -x -v` | All 18 tests pass. No skips. |
| **G-D6: Cost-cap guard works** | `MAX_DAILY_GPU_COST=0.01 fabrik gpu rent pod-h100 --workload smoke --max-cost 1` | Exits non-zero with message `GPUBudgetExceeded: daily GPU spend $X + estimate $Y would exceed MAX_DAILY_GPU_COST=$0.01`. No RunPod API call (verify dashboard). |
| **G-D7: Audit log appended** | After each successful run: `tail -1 logs/gpu-rent-history.jsonl \| python3 -m json.tool` | Valid JSON, contains: `ts`, `ts_iso`, `session_id`, `kind`, `workload`, `success`, `cost_estimate_usd`, `wall_clock_seconds`, `checks`. |
| **G-D8: State file consistent** | After each create+destroy cycle: `python3 -c "from fabrik.orchestrator import gpu_state; sess = gpu_state.get_session('<id>'); assert sess['destroyed_at'] is not None"` | Session in state has `destroyed_at` populated. |

### Live-validation gates (before declaring Phase 1 complete)

| Gate | Command | Pass criterion |
|---|---|---|
| **G-LIVE-1: Live serverless smoke** | `fabrik gpu rent serverless --workload smoke-test --max-cost 1` | RunPod endpoint created (verify dashboard shows endpoint), endpoint URL printed, endpoint destroyed at exit. Wall-clock < 60s. Cost < $0.05. **Provider dashboard shows 0 active endpoints after.** |
| **G-LIVE-2: Live pod try/finally** | `fabrik gpu rent pod-rtx-4090 --workload smoke-test --max-cost 0.50 --max-lifetime 1` with a `work_fn` that sleeps 30s | Pod created (`desiredStatus: RUNNING`), work_fn runs, pod destroyed at exit. Wall-clock < 5 min. Cost < $0.20. **Provider dashboard shows 0 active pods after.** |
| **G-LIVE-3: Live failure path** | Inject a raise into work_fn. Run rent again. | Pod still destroyed (try/finally invariant). State file shows `destroyed_at != null`. Audit log shows `success: false, error: "<msg>", checks.destroyed: true`. |
| **G-LIVE-4: Live orphan reaper (tag-safe)** | Manually create TWO pods via RunPod dashboard: one WITH `env: {FABRIK_SESSION_ID: "test-orphan"}`, one WITHOUT any FABRIK_ env. Run `fabrik gpu reconcile --auto-destroy`. | ONLY the `FABRIK_SESSION_ID`-tagged pod is destroyed. The other pod (manual, no tag) is left alive — critical safety invariant (C4). |
| **G-LIVE-5: Live lifetime-exceeded reaper** | Create a pod via `rent()` with `max_lifetime_hours=0.01` (~36s). Wait 60s. Run `fabrik gpu reconcile --auto-destroy`. | Pod is destroyed. Output names it under `lifetime_exceeded: [...]`. |
| **G-LIVE-6: Cost reconciliation matches RunPod billing** | Run a 5-min pod-rtx-4090 session. After completion, query `GET /billing/pods?start=...&end=...`. Compare to `cost_actual_usd` in our JSONL entry. | Difference < 5% (RunPod billing rounds to nearest minute; our wall-clock measures seconds). |
| **G-LIVE-7: Concurrent sessions don't corrupt state** | Run 2 `fabrik gpu rent` sessions in parallel. | Both complete. State file has both `destroyed_at` populated. No lost updates (verify with `file_lock` — same pattern as `vultr_state._LOCK`). |

### Documentation gates (before merge)

| Gate | Pass criterion |
|---|---|
| **G-DOC-1** | `docs/operations/gpu-rent.md` exists, covers: prerequisites, `fabrik gpu rent` examples for serverless + pod, troubleshooting (orphan, budget exceeded, API key wrong), reaper, monitoring. |
| **G-DOC-2** | CHANGELOG.md `## [Unreleased]` has an entry referencing this plan + Phase 1 commit SHA. |
| **G-DOC-3** | `76-gpu-workers.md` line 460's "Until then" caveat is updated to reference `fabrik gpu rent` (the orchestrator layer it punts to). |
| **G-DOC-4** | `INDEX.md` lists the new module entries. |

### Post-merge gates (before announcing the surface)

| Gate | Pass criterion |
|---|---|
| **G-POST-1** | A real Fabrik service uses `fabrik gpu rent` end-to-end. **Validation: pick a low-volume workload (e.g., one-off `seo.yaml` keyword embedding) and refactor it to call `with rented("serverless", workload="seo-embed") as ep:` instead of the inline managed-API path. Measure end-to-end cost.** |
| **G-POST-2** | First two weeks: `logs/gpu-rent-history.jsonl` shows ZERO orphan-cleanup events from G-LIVE-4 path. (If any > 0, the cron isn't catching them — Phase 4 must accelerate.) |
| **G-POST-3** | First month: `MAX_DAILY_GPU_COST` was hit zero times (or operator explicitly raised it). If hit unintentionally, default of $50 was wrong → raise. |

---

## Verification plan (Phase 1 acceptance)

1. **G-PRE-1 through G-PRE-4** pass before writing code.
2. **G-D1 through G-D8** pass during incremental implementation. Test suite (G-D5) is green after EVERY commit.
3. **G-LIVE-1 through G-LIVE-7** pass on a real RunPod account with `--max-cost` set to ≤ $1 per gate.
4. **G-DOC-1 through G-DOC-4** pass before opening the PR.
5. PR review (peer AI runs the 5-axis code review).
6. Merge to master.
7. **G-POST-1 through G-POST-3** monitored for 1 month after merge.

If any post-merge gate fails, file a remediation issue. Do NOT advertise the surface as "production-ready" until all G-POST gates have passed at least once in the wild.

---

## Cross-references

- [`.windsurf/rules/core/76-gpu-workers.md`](../../../.windsurf/rules/core/76-gpu-workers.md) — decision framework (the WHY)
- [`src/fabrik/orchestrator/vultr_drill.py`](../../../src/fabrik/orchestrator/vultr_drill.py) — architectural template (line 410: `drill()` signature; line 456: report shape; line 439: cost guard)
- [`src/fabrik/orchestrator/vultr_state.py`](../../../src/fabrik/orchestrator/vultr_state.py) — state-file template (line 42: STATE_FILE path; line 46: DISPOSABLE_RETENTION_DAYS)
- [`tests/orchestrator/test_vultr_drill.py`](../../../tests/orchestrator/test_vultr_drill.py) — test pattern (15 tests, ~268 lines)
- [`src/fabrik/ai/tracker.py`](../../../src/fabrik/ai/tracker.py) — UsageTracker SQLite schema (extending in Phase 1 § D8)
- [`docs/operations/disaster-recovery.md`](../../../docs/operations/disaster-recovery.md) — operational doc style for `gpu-rent.md` to follow
- RunPod REST API docs index: `https://docs.runpod.io/llms.txt`
- RunPod GPU type IDs: `https://docs.runpod.io/references/gpu-types.md`

---

## Lessons that pre-shaped this plan

- **Hub DR Drill #1 (2026-06-14) orphan** — `TaskStop` killed the python before try/finally ran, leaving a Vultr droplet alive ([`logs/dr-drill-history.jsonl`](../../../logs/dr-drill-history.jsonl)). At Vultr's $0.10/hr that cost a few cents. At RunPod H100's $4/hr a similar leak costs **$96/day, $720/week**. Try/finally invariant is non-negotiable; the `destroy_pending` state + reaper is the second-line defense.
- **`fabrik vultr drill` cost-cap pattern** — `--max-cost` refused before provider create-instance call (line 439–440). Copied verbatim into `gpu_rent.py`.
- **Backrest `host-state` plan-id tagging bug** (Hub DR Drill #5) — assumptions about external-system contracts (tag names, API shapes) ALWAYS need a live probe, not a doc-read. **Iteration 2 of this plan grounded RunPod's REST shape by fetching the actual `llms.txt` index + per-endpoint markdown.** No guessed methods.
- **Iteration 1 of this plan** had vultr-line-count claims that were off by 50–100% (vultr.py: said 510, actual 298; vultr_state.py: said 85, actual 167). Iteration 2 verified all numbers with `wc -l`. The lesson generalizes: every "~X lines" claim in any plan should be cited to actual current state.
- **`fabrik vultr list` reconciliation discipline** — state file vs. live API drift is inevitable; explicit `reconcile` command surfaces it daily before it becomes 30 stale pods. The G-LIVE-4 gate ensures we ship this from day one.
