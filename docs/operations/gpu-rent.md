# GPU rentals — operator runbook

**Last updated:** 2026-06-16 (Phase 1+2+3+4+5 shipped; live-validated against RunPod)
**Companion docs:**

- [Plan](../development/plans/archived/2026-06-17-gpu-rent-and-serverless-shipped/2026-06-16-fabrik-gpu-rent.md) — implementation plan + validation gates
- [RunPod API reference](../reference/apis/runpod-api.md) — what the driver wraps
- [RunPod HF models](../reference/apis/runpod-hf-models.md) — deployable model catalog
- [`.windsurf/rules/core/76-gpu-workers.md`](../../.windsurf/rules/core/76-gpu-workers.md) — decision framework

## TL;DR

```bash
# Compare providers for a workload
fabrik gpu compare pod-h100 --hours 4 --utilization 1.0

# Rent on demand, run work, auto-destroy
fabrik gpu rent serverless --workload smoke --max-cost 1
fabrik gpu rent pod-rtx-4090 --workload train --max-lifetime 4 --max-cost 3

# Audit + cleanup
fabrik gpu list
fabrik gpu history --lines 20
fabrik gpu reconcile [--auto-destroy]
fabrik gpu destroy <session-id-or-pod-id> -y
```

---

## What this surface does

`fabrik gpu` rents GPU compute on demand, runs your work, and **always
destroys the resource at exit** — success, failure, exception, even
network drop. Mirrors `fabrik vultr drill`'s try/finally lifecycle for
GPUs. State + cost tracked in `data/gpu-rent-state.json` and
`logs/gpu-rent-history.jsonl`. Daily budget cap enforced before any
provider call.

**Providers (all three live-validated 2026-06-16):**

| Provider | Pod mode | Serverless mode | When auto picks it |
| --- | --- | --- | --- |
| **RunPod** | ✅ live (G-LIVE-2/3) | ✅ live (G-LIVE-1, pinned endpoint reuse) | utilization ≥ 0.5, no checkpointing |
| **Modal** | ✅ live (G-LIVE-7/8/9) | ✅ live (LIVE-12 echo; LIVE-13 vLLM lifecycle PARTIAL — destroy verified) | utilization < 0.5 (per-second billing wins) |
| **Vast.ai** | ✅ live (G-LIVE-5) | ✅ driver shipped + LIVE-16 cross-provider reconcile GREEN (LIVE-14 requires ≥$5 account balance for endpoint create) | `--needs-checkpointing` (spot ~50% cheaper) |

`fabrik gpu compare` shows side-by-side pricing + recommends one based on utilization rate + checkpointing requirement. `--provider auto` (the default) runs that recommendation and proceeds directly.

**Cold vs hot:**

- `--kind serverless` → RunPod scale-to-zero endpoint (cold-by-default,
  ~500ms FlashBoot warm dispatch, $0 idle)
- `--kind pod-*` → dedicated pod (hot until destroyed). Auto-reaped past
  `--max-lifetime` hours.

---

## Prerequisites

1. **RunPod account + API key.** Generate at
   <https://www.console.runpod.io/user/settings> → "API Keys".
2. **(serverless)** A deployed endpoint. Easiest: <https://console.runpod.io/serverless/new> → "Deploy LLM from Hugging Face" → pick a model (see [reference catalog](../reference/apis/runpod-hf-models.md)).
   Capture the **endpoint ID** from the URL (e.g. `5fm6047mmhueoe`).
3. **Drop credentials into `/opt/fabrik/.env.sysadmin`:**

   ```bash
   RUNPOD_API_KEY=rpa_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   MAX_DAILY_GPU_COST=5
   RUNPOD_SERVERLESS_ENDPOINT_ID=5fm6047mmhueoe
   ```

4. **(optional Phase 2 providers)**:

   ```bash
   MODAL_TOKEN_ID=<from `modal token new`>
   MODAL_TOKEN_SECRET=<paired secret>
   VAST_API_KEY=<from https://console.vast.ai/account>
   ```

5. **(optional Phase 3 checkpoints)** B2 creds already present in
   `.env.sysadmin` for Backrest (`B2_KEY_ID`, `B2_APPLICATION_KEY`).
   No new keys needed.

---

## Commands

### `fabrik gpu rent <kind>`

Provision a GPU, optionally use it, **always destroy at exit**.

| Flag | Default | Purpose |
|---|---|---|
| `kind` (positional) | — | One of `serverless`, `pod-h100`, `pod-h100-pcie`, `pod-h100-nvl`, `pod-a100`, `pod-a100-sxm`, `pod-h200`, `pod-l40s`, `pod-rtx-4090` |
| `--workload` | (required) | Free-text tag (e.g. `train-tinyllama`, `seo-embed`) |
| `--provider` | `auto` | `auto` (recommended), `runpod`, `modal`, or `vast`. **`auto` runs `selection_advice()` and picks per workload shape.** |
| `--utilization` | `1.0` | (auto only) Fraction of `--max-lifetime` the GPU will be actively computing. 1.0 = training, 0.2 = bursty. |
| `--needs-checkpointing` | off | (auto only) Workload writes checkpoints to B2/R2 — opts into Vast.ai spot (~50% cheaper). |
| `--needs-serverless` | off | (auto only) Restrict to providers publishing a serverless tier — RunPod, Modal, and Vast all qualify (Phase 3.5), so this filter currently excludes no one. |
| `--max-lifetime` | `1` (hours) | Reaper destroys past this |
| `--max-cost` | `5.0` (USD) | Refused BEFORE provider create if estimate exceeds |
| `--keep-warm-after-use` | off | Don't destroy after successful work_fn |
| `--keep-on-failure` | off | Leave pod alive if work_fn raised, for inspection |
| `--dry-run` | off | Print the plan + cost guard result, no API call |
| `--image` | NVIDIA CUDA runtime | (pod-* only) Override container image |
| `--cloud` | `SECURE` | `SECURE` (datacenter) or `COMMUNITY` (~50% cheaper, shared kernel) |
| `--interruptible` | off | (pod-* only) Spot/preemptible — auto-enabled when `auto` picks Vast |

**Examples:**

```bash
# Plan-only dry run (no API call, no cost)
fabrik gpu rent pod-rtx-4090 --workload smoke --dry-run

# Auto-pick provider for continuous training (high util → RunPod)
fabrik gpu rent pod-h100 --workload train-7b --max-lifetime 8 --max-cost 30

# Auto-pick provider for bursty inference (low util → Modal per-second)
fabrik gpu rent pod-h100 --workload chat-server --utilization 0.2 \
                          --max-lifetime 24 --max-cost 50

# Auto-pick provider for checkpoint-resumable training (cheapest → Vast spot)
fabrik gpu rent pod-h100 --workload distill --needs-checkpointing \
                          --max-lifetime 12 --max-cost 25

# Force a specific provider (override auto)
fabrik gpu rent pod-rtx-4090 --workload smoke --provider runpod --max-cost 3
fabrik gpu rent pod-rtx-4090 --workload smoke --provider vast --max-cost 1
```

**How `auto` decides** (verified by `fabrik gpu compare` + unit tests):

- **utilization ≥ 0.5 + no checkpointing** → **RunPod**. Sustained workloads win on RunPod's hourly Secure pricing (e.g. H100 at $2.89/hr).
- **utilization < 0.5** → **Modal**. Per-second billing dominates for bursty work — a 20%-util 4hr workload pays only the active 48 minutes (effective $3.16 for an H100 vs RunPod's $11.56 for the full 4 hours).
- **--needs-checkpointing** + GPU available on Vast → **Vast.ai spot/interruptible**. ~50% cheaper, but preemptible — only safe if your workload writes checkpoints.
- **--needs-serverless** → keeps only providers publishing a serverless tier; all three now do (Vast serverless wired in Phase 3.5), so it no longer drops Vast.

The CLI prints the chosen provider + rationale on every invocation:

```text
🤖 provider=auto → modal ($3.16)
   low utilization (20%) — Modal's per-second billing wins. Cost $3.16.
```

### `fabrik gpu compare <kind>` — decision support

Side-by-side cost across RunPod, Modal, Vast.ai for a workload. Encodes
the rule's selection logic + Gemini's utilization-rate framework.

```bash
# Continuous training (high utilization → RunPod usually wins)
fabrik gpu compare pod-h100 --hours 4 --utilization 1.0

# Bursty event-driven (low utilization → Modal's per-second billing wins)
fabrik gpu compare pod-h100 --hours 4 --utilization 0.2

# Cheap training with checkpointing (Vast.ai spot becomes viable)
fabrik gpu compare pod-h100 --hours 4 --needs-checkpointing
```

Output includes recommended provider + rationale.

### `fabrik gpu list` / `status` / `destroy` / `pause` / `resume` / `reconcile` / `history`

All five commands are **provider-aware** (live-validated 2026-06-16, G-LIVE-10/11). They read the session's recorded `provider` from `data/gpu-rent-state.json` and dispatch to the matching API — so a Modal-rented pod is destroyed via Modal SDK, a Vast-rented one via Vast REST, etc.

| Command | Purpose |
| --- | --- |
| `list` | All active sessions in local state (provider-agnostic) |
| `status <id>` | Detailed state for a session/resource + live provider probe (dispatches by session's recorded provider) |
| `destroy <id>` | Manual cleanup (orphan removal) — dispatches to the right provider |
| `reconcile [--auto-destroy] [--provider all\|runpod\|modal\|vast]` | Walks every configured provider, reports drift, optionally auto-destroys lifetime-exceeded + tagged orphans. `--provider all` (default) iterates all three. |
| `history [--lines N]` | Tail `logs/gpu-rent-history.jsonl` (audit log) |

```bash
# See what's alive across all 3 providers + foreign-pod count
fabrik gpu reconcile --provider all

# Reconcile against just Modal (skips RunPod + Vast even if tokens are set)
fabrik gpu reconcile --provider modal

# Status of a session (auto-detects provider from state)
fabrik gpu status gpu-pod-rtx-4090-20260616-204119-302ea1
# → reads provider=modal from state, queries modal.FunctionCall.from_id(...)

# Destroy a session (auto-detects provider from state)
fabrik gpu destroy gpu-pod-rtx-4090-20260616-204119-302ea1 -y
# → reads provider=modal, calls ModalClient.destroy_pod(fc-id)
```

**Critical safety (C4)**: `reconcile --auto-destroy` only touches pods carrying `FABRIK_SESSION_ID` env tag. **Foreign pods (not created by Fabrik) are NEVER destroyed — on ANY of the three accounts.** A foreign-count of `1` on RunPod (your manually-created SmolLM2 serverless endpoint) is expected and intentional.

**Modal `--keep-warm-after-use` limitation**: Modal "pods" are really FunctionCalls inside an `app.run()` context. The context is process-scoped — when the CLI exits, the context closes regardless. So `--keep-warm-after-use` does NOT work for `--provider modal --kind pod-*` (the context dies anyway). Use Modal serverless (Phase 3) for persistent endpoints. RunPod + Vast pods CAN survive the CLI exit and honor `--keep-warm-after-use`.

---

## Cost cap layers (Constraint C2)

Two guards fire BEFORE any provider call:

1. **Per-call** (`--max-cost`): refuses if `estimate_cost(kind, max_lifetime) > max-cost`.
2. **Daily envelope** (`MAX_DAILY_GPU_COST` env): refuses if
   `today's GPU spend + estimate > MAX_DAILY_GPU_COST`.

When tripped, `GPUBudgetExceededError` is raised (the CLI renders it as
`✗ budget exceeded: <msg>`); no provider API call has been made.

---

## Common workflows

### Smoke test (G-LIVE-1 pattern)

```python
from fabrik.orchestrator.gpu_rent import rent
from fabrik.drivers.runpod import RunPodClient

def workflow(endpoint):
    c = RunPodClient()
    try:
        result = c.run_endpoint_sync(
            endpoint["id"],
            {"input": {"prompt": "Hello world"}},
            timeout=120,
        )
        print(result["output"])
    finally:
        c.close()

rent("serverless", workload="smoke", work_fn=workflow, max_cost_usd=1.0)
```

### Training with checkpointing (Phase 3)

```python
from fabrik.orchestrator.gpu_rent import rent
from fabrik.orchestrator.gpu_checkpoint import (
    checkpoint_to_b2, load_latest_checkpoint, write_checkpoint_to_tarball,
)

def training_loop(pod):
    # Resume from last checkpoint if any
    prev = load_latest_checkpoint("my-project", "run-001")
    start_step = prev[1]["latest_step"] + 1 if prev else 0
    for step in range(start_step, 1000):
        # ... training ...
        if step % 50 == 0:
            payload = write_checkpoint_to_tarball({"model": ..., "step": step})
            checkpoint_to_b2(
                payload, project="my-project", run_id="run-001",
                step=step, async_upload=True,  # doesn't block training
            )

rent("pod-rtx-4090", workload="train", work_fn=training_loop,
     max_lifetime_hours=4, max_cost_usd=3.0, interruptible=True)
```

### Scheduled reaper (Phase 4)

Install the user-mode systemd timer (every 10 min):

```bash
mkdir -p ~/.config/systemd/user
cp /opt/fabrik/scripts/systemd/fabrik-gpu-reaper.{service,timer} \
   ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now fabrik-gpu-reaper.timer
systemctl --user list-timers fabrik-gpu-reaper.timer
```

The reaper writes Prometheus metrics to `logs/gpu-rent-metrics.prom` for
the node-exporter textfile collector. Add panels in Grafana for:

- `gpu_rent_active{provider="runpod"}` — live count
- `rate(gpu_rent_cost_usd_total[1d])` — daily spend
- `gpu_rent_destroy_pending` — orphan risk (alert if > 0)
- `gpu_rent_last_reconcile_age_seconds` — alert if > 3600 (reaper not running)

### Scaffolding a new GPU service (Phase 5)

```bash
fabrik scaffold my-gpu-service --type python-api-gpu
```

This creates a standard `python-api` project (identical spec shape — the Shape model has no `needs_gpu`/`gpu_kind` fields yet) + adds:

- `src/<package>/gpu_handler.py` with the `rent_for_workload(workload, work_fn)` helper; its `DEFAULT_KIND = "pod-rtx-4090"` constant sets the GPU kind

Edit `src/<package>/gpu_handler.py` to call your workload from a job handler.

---

## Troubleshooting

### `✗ budget exceeded: estimated cost $X exceeds --max-cost $Y` (`GPUBudgetExceededError`)

The per-call cap caught you. Either:

- Lower `--max-lifetime` so the estimate fits
- Raise `--max-cost` to match the workload
- Use a cheaper `--kind` (e.g. `pod-rtx-4090` vs `pod-h100`)
- Use `--cloud COMMUNITY` for ~50% cheaper pods (shared kernel — see
  rule line 342)

### `✗ budget exceeded: daily GPU spend $X + estimate $Y would exceed MAX_DAILY_GPU_COST=$Z` (`GPUBudgetExceededError`)

Today's cumulative spend would breach the daily cap. Either:

- Wait until UTC midnight (cap resets)
- Set `MAX_DAILY_GPU_COST=<higher>` in `.env.sysadmin` if intentional
- Reduce the per-call cost (see above)

### `RUNPOD_API_KEY is required`

Set it in `/opt/fabrik/.env.sysadmin` (per the Prerequisites section).
Generate at <https://www.console.runpod.io/user/settings>.

### `RunPod 500: Container image "<image>" was not found on the registry`

The default `DEFAULT_POD_IMAGE` in `gpu_rent.py` may have been removed
by RunPod. Override with `--image nvidia/cuda:12.4.1-runtime-ubuntu22.04`
(or any current public image) until the default is updated.

### Pod stuck in `EXITED` or never reaches `RUNNING`

The container image likely crashed on boot. `fabrik gpu status <id>`
shows the RunPod state. Common causes:

- Wrong CUDA version for the GPU type
- Image missing required CMD/ENTRYPOINT
- Out-of-memory at startup (raise `containerDiskInGb`)

### Orphan (pod alive on RunPod, no local state)

`fabrik gpu reconcile` detects this. If it carries
`FABRIK_SESSION_ID` (Fabrik created it, state file got lost), it shows
under `orphan_pods`. `--auto-destroy` will clean it up.

Foreign pods (no `FABRIK_SESSION_ID` — operator created via dashboard
or other tooling) show under `foreign_count` and are **never** touched.

### `destroy_pending` count > 0

A previous destroy attempt errored. The reaper retries automatically on
its next run. Or run `fabrik gpu reconcile --auto-destroy` manually.

---

## What's NOT supported (yet)

- **Multi-GPU pods**: driver accepts `gpu_count` but orchestrator hardcodes
  to 1. Add `--gpu-count` flag if needed (small change).
- **Network volumes**: pods get an ephemeral 20GB volume by default. For
  persistent data across rentals, use B2 (`checkpoint_to_b2`).
- **Modal serverless deployment**: shape is in the driver but actual
  `App.deploy()` requires an operator-supplied Modal App definition file
  — Phase 6 work.
- ~~Vast.ai serverless~~ — **now supported** (Phase 3.5: endptjobs/workergroups wired; LIVE-16 reconcile GREEN; LIVE-14 endpoint create needs ≥$5 account balance).
- **HF inference endpoints / OpenAI-compatible /v1 routes**: RunPod's
  vLLM template exposes both `/run` (Fabrik's path) and `/v1/chat/completions`
  (OpenAI-compat). Phase 1 wires `/run`. For OpenAI-compat, use the
  `openai` Python SDK directly with `base_url=https://api.runpod.ai/v2/<id>/openai/v1`
  and `api_key=$RUNPOD_API_KEY`.

---

## See also

- [Plan](../development/plans/archived/2026-06-17-gpu-rent-and-serverless-shipped/2026-06-16-fabrik-gpu-rent.md)
- [RunPod API reference](../reference/apis/runpod-api.md)
- [RunPod HF models catalog](../reference/apis/runpod-hf-models.md)
- [`.windsurf/rules/core/76-gpu-workers.md`](../../.windsurf/rules/core/76-gpu-workers.md) — the decision framework
- [`.../scripts/systemd/README.md`](../../scripts/systemd/README.md) — systemd timer install
