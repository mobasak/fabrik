---
activation: glob
globs: ["**/gpu/**", "**/inference/**", "**/ml/**", "**/training/**", "**/workers/**/gpu*", "**/serverless-gpu/**"]
description: GPU worker discipline — decision framework for API vs self-host, provider/engine/quantization selection, two-faced architecture, lifecycle automation, fault tolerance
trigger: glob
---
<!-- CONSUMER: Coding agents building GPU inference/training orchestrators + Traycer (tech-plan)
     GOAL: API vs self-host decision, two-faced architecture, provider selection, cost control
     TRAYCER USAGE: Decision framework shapes tech-plan. Injects orchestrator requirements into tickets.
     AGENT USAGE: Build the orchestrator as a standard Fabrik python-api. GPU worker is external. -->

# GPU Workers Rules

Apply when building services that use GPU compute for inference, training, or fine-tuning. This file is the decision authority — it tells you when NOT to use GPU cloud (most of the time), and when you must, how to do it right.

For local Ollama inference on the dev machine, see `LOCAL_LLM_INFRASTRUCTURE.md`.

---

## Two-Faced Architecture

GPU services are **two-faced** like mobile-app and chrome-extension:

| Lane | Runs on | Deploy | Rules |
|---|---|---|---|
| **Orchestrator** (API gateway + job dispatch) | VPS via `fabrik apply` | Standard Fabrik `python-api` scaffold — Dockerfile, compose, Traefik, registrars | `10-python.md`, `30-ops.md`, `55-observability.md`, `58-resilience.md`, `75-workers-jobs.md` |
| **GPU Worker** (inference / training / fine-tuning) | External GPU cloud (RunPod, Modal, Vast.ai) or managed API (Together, Groq) | Provider API — NOT the Fabrik VPS (it has no GPU) | This file |

- The **orchestrator** is a standard Fabrik service: `postgres-main:5432`, `redis-main:6379`, structlog, `/health`, `/metrics`, GlitchTip, Traefik labels, `deploy.resources.limits.memory`, `slim-bookworm`, `coolify` network. All `30-ops.md` rules apply.
- The **GPU worker** is external. The orchestrator calls it via provider API (RunPod endpoint, Modal function, Together/Groq `/v1/chat/completions`).
- The orchestrator owns the job queue (PG `SKIP LOCKED` per `75-workers-jobs.md`). Async/batch GPU requests are jobs. Real-time streaming requests bypass the queue and call the provider directly with timeout + fallback.

**Never deploy GPU inference on the VPS.** The VPS has no GPU. If an agent tries to add a GPU container to `compose.yaml`, stop — it goes to a GPU cloud provider.

---

## First Decision: Do You Even Need GPU Cloud?

**Most fabrik services should NOT self-host inference.** The break-even math is brutal for a solo dev:

| Monthly volume | Winner | Why |
|---|---|---|
| < 1B tokens/month | **Managed API** (Together AI, Groq) | Zero idle cost, zero ops. GPU cloud charges even when idle. |
| 1B - 5B tokens/month | **Depends on utilization** | If you can sustain 60%+ GPU utilization 24/7, self-host may win. Below that, API wins. |
| > 5B tokens/month | **Self-hosted GPU** | Unit economics dominate at this volume — but almost no solo-dev service reaches this. |
| Frontier MoE models (400B+ parameter) | **Always API** | MoE requires VRAM for ALL parameters even though only a fraction activates per token. Self-hosting needs 8x H100 cluster. API providers amortize this. |
| Fine-tuning / training | **Always GPU cloud** | No managed API for this. Need raw GPU access. |
| Prototyping / dev | **Local Ollama first** | Free, instant, offline. Only go cloud when local VRAM can't fit the model. See `LOCAL_LLM_INFRASTRUCTURE.md` for machine specs. |

**The concrete break-even:** a self-hosted H100 at ~$2/hr running 24/7 = ~$1,500/month. At typical API rates (~$0.30/M input tokens), you need ~5-8 billion tokens/month to beat API pricing. A solo dev's service will almost never reach this volume.

**Rule: Start with managed APIs. Move to GPU cloud only when your monthly token bill exceeds $1,500 AND your serving config is stable.**

### Managed API Selection (when GPU cloud is NOT the answer)

Route requests by workload type. Use multi-provider routing for cost savings:

| Workload | Route to | Why |
|---|---|---|
| Real-time chat, streaming | Lowest-latency provider (LPU/custom silicon) | Sub-second TTFT for interactive UX |
| Batch processing, cost-sensitive | Cheapest open-source provider | Cost per token is the only metric |
| Niche/custom models | Pay-per-prediction provider | Runs any HuggingFace model |
| Code generation | Low-latency provider | IDE integration needs speed |
| Vision / multimodal | Provider with best model selection | Multi-modal model availability varies |

All major providers expose OpenAI-compatible `/v1/chat/completions` — use the `openai` SDK with `base_url` swap. Specific provider names, models, and prices in the Provider Snapshot below.

**Implementation pattern (orchestrator-side):**

```python
# config/inference.py — env-based, never hardcoded
from pydantic_settings import BaseSettings, SettingsConfigDict

class InferenceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFERENCE_")

    chat_provider: str = "groq"
    chat_model: str = "llama-3.3-70b-versatile"
    batch_provider: str = "together"
    batch_model: str = "meta-llama/Llama-4-Maverick-17B-128E"
    groq_api_key: str = ""
    together_api_key: str = ""
    runpod_api_key: str = ""
    runpod_endpoint_id: str = ""

# All providers expose OpenAI-compatible /v1/chat/completions — use openai SDK with base_url swap
```

API keys live in env vars (compose env or `.env`). Never hardcoded. See `10-python.md` § Config Loading.

---

## Orchestrator Responsibilities

The orchestrator is a standard `python-api` Fabrik service. It handles:

### Job Queue (async/batch inference)

For non-interactive workloads (batch embeddings, report generation, fine-tune dispatch):

- Enqueue via PG `SKIP LOCKED` per `75-workers-jobs.md` — same outbox pattern, idempotency, retry/backoff.
- The orchestrator dequeues and calls the GPU provider API with timeout + retry.
- If adaptive worker pool applies (per `75-workers-jobs.md`), the orchestrator scales workers that call GPU endpoints, not GPU instances directly.

### Direct Call (real-time inference)

For interactive workloads (chat, autocomplete, streaming):

- Call the provider API directly from the API handler — no queue.
- Wrap with `httpx.AsyncClient` + timeout + retry + circuit-breaker per `58-resilience.md`.
- Stream SSE tokens back to the client. If the provider fails, return a graceful fallback (cached response, error message, or degraded mode).

### Provider Failover

```python
# Resilience: primary → fallback → graceful degradation
INFERENCE_CHAIN = [
    {"provider": "groq", "model": "llama-3.3-70b-versatile"},
    {"provider": "together", "model": "meta-llama/Llama-4-Maverick-17B-128E"},
]

async def infer_with_failover(messages: list[dict]) -> str:
    for route in INFERENCE_CHAIN:
        try:
            return await call_provider(route, messages, timeout=30.0)
        except (httpx.TimeoutException, httpx.ConnectError):
            logger.warning("provider_failover", failed=route["provider"])
            continue
    return FALLBACK_RESPONSE  # graceful degradation
```

- Every provider in the chain must have a row in `docs/RESILIENCE.md` §2a.
- Circuit-breaker per provider (not per model) — if Groq is down, don't keep trying Groq.

### Health Endpoint

The orchestrator's `/health` must verify:

- DB connectivity (`SELECT 1` on `postgres-main`)
- Redis connectivity (if used)
- At least one inference provider reachable (lightweight ping, not a full inference call)
- Report provider status in the response body

```json
{
  "status": "ok",
  "providers": {
    "groq": "reachable",
    "together": "reachable",
    "runpod": "unreachable"
  }
}
```

### Observability (orchestrator-side)

Standard Fabrik observability applies to the orchestrator:

- **Structured logging:** `structlog` — JSON to stdout. `print()` banned. See `55-observability.md`.
- **Metrics:** scaffolded counters + GPU-specific gauges:
  ```python
  INFERENCE_REQUESTS = Counter("inference_requests_total", "Inference requests", ["provider", "model", "status"])
  INFERENCE_LATENCY = Histogram("inference_latency_seconds", "Inference latency", ["provider"])
  INFERENCE_TOKENS = Counter("inference_tokens_total", "Tokens processed", ["provider", "direction"])
  INFERENCE_COST = Counter("inference_cost_usd_total", "Inference cost in USD", ["provider"])
  ```
- **Cost logging:** every inference call logs `provider`, `model`, `input_tokens`, `output_tokens`, `duration_s`, `cost_usd` as structured JSON. Monthly rollup via Grafana LogQL query.
- **GlitchTip:** init before app start. Provider API errors auto-capture.
- **Cold start alert:** if p95 TTFT > 5s (serverless) or > 60s (pod), alert via Prometheus.

---

## When You DO Need GPU Cloud

Three cases: (1) self-hosted inference at scale, (2) fine-tuning, (3) training.

### Inference Server Selection

**TGI is dead.** Hugging Face put it in maintenance mode (Dec 2025), no new features. HF Inference Endpoints now defaults to vLLM.

| Engine | Use when | Throughput (H100, 70B) | Cold start |
|---|---|---|---|
| **vLLM** | Default for everything. Broadest hardware support, largest community, battle-tested. | Baseline (1x) | ~5-10s (true cold start — model load into GPU memory) |
| **SGLang** | Multi-turn chat, structured output (JSON mode), prefix-heavy RAG pipelines. RadixAttention gives real gains on shared prefixes. | 1.29x on 7B, ~1.05x on 70B | ~5-10s |
| **TensorRT-LLM** | Maximum throughput when you can afford 28-min compilation step. NVIDIA GPUs only. | 1.3-1.5x vs vLLM | 28min compile + 5s |
| **Ollama** | Local dev only. Not for production serving. | N/A | Instant (already loaded) |

**Default: vLLM.** Switch to SGLang only if your workload is measurably prefix-heavy. Switch to TensorRT-LLM only if you've validated throughput gains on YOUR model and can tolerate the compilation step.

### Quantization Decision Guide

Quantization is the #1 lever for reducing GPU cost. Smaller model = cheaper GPU. Quality retention percentages below are approximate and model-dependent — benchmark on your specific model before committing to a quantization level.

| Method | Bits | Quality retention | Speed (GPU) | Best for |
|---|---|---|---|---|
| **FP16/BF16** | 16 | 100% (baseline) | 1x | Training, fine-tuning — never quantize during training |
| **FP8** | 8 | ~99% | 1.2-1.5x | Production inference on H100/H200 (native FP8 support) |
| **AWQ** | 4 | ~95% (best 4-bit) | 1.5-2x | Production inference — preserves critical weights by activation pattern analysis |
| **GPTQ** | 4 | ~90% | 1.8-2.2x (highest) | Maximum throughput inference — slightly worse quality than AWQ but faster |
| **GGUF (Q4_K_M)** | 4 | ~92% | Varies | CPU or hybrid CPU+GPU. Not for pure GPU serving — use AWQ/GPTQ instead |

**Decision rule:**

- Training/fine-tuning → FP16/BF16 always
- Production inference on H100/H200 → FP8 (best quality-speed ratio with native hardware support)
- Production inference on A100/L40S/RTX → AWQ (best quality at 4-bit)
- Maximum throughput, quality less critical → GPTQ
- Local/edge/CPU → GGUF Q4_K_M
- **Never self-host quantized MoE models** — the VRAM savings are minimal because MoE requires loading all experts

### VRAM Budget Calculator

Before provisioning, calculate whether the model fits:

```
VRAM_GB = (params_B * bytes_per_param) + KV_cache + overhead

Where:
  params_B     = model parameter count in billions
  bytes_per_param = 2 (FP16), 1 (INT8/FP8), 0.5 (INT4)
  KV_cache     = batch_size * seq_len * num_layers * 2 * hidden_dim * bytes / 1e9
  overhead     = ~2GB (CUDA context, inference server, buffers)
```

**Quick reference (single GPU, no KV cache estimate):**

| Model size | FP16 | FP8/INT8 | INT4 (AWQ/GPTQ) | Minimum GPU |
|---|---|---|---|---|
| 7-8B | 16 GB | 8 GB | 4 GB | L4 (24GB) or RTX 4090 |
| 13B | 26 GB | 13 GB | 7 GB | L40S (48GB) or A100 40GB |
| 34B | 68 GB | 34 GB | 17 GB | A100 80GB (FP8) or L40S (INT4) |
| 70B | 140 GB | 70 GB | 35 GB | H100 80GB (FP8) or A100 80GB (INT4) |
| 70B + KV for 4K context | ~150 GB | ~80 GB | ~45 GB | H200 141GB (FP8) comfortable |
| 405B (Llama 3.1) | 810 GB | 405 GB | 203 GB | 3x H200 (FP8) or 8x A100 (INT4) |

**Always leave 15-20% VRAM headroom.** KV cache grows linearly with context length and batch size.

---

## GPU Cloud Provider Selection (durable framework)

Only after confirming self-hosting is cheaper than APIs:

### For Inference — Selection Criteria

Pick by these criteria (specific providers and prices in the Provider Snapshot below):

1. **Bursty / scale-to-zero** → serverless provider with fast cold start + NVMe model cache. Pay per request. $0 when idle.
2. **Steady traffic, SLA** → dedicated pod, always-on. Pay per hour.
3. **Cost-sensitive, steady** → community/marketplace pod. Cheaper per hour, less stability.
4. **Code-first DX, fast iteration** → per-second billing with Python decorator pattern. Accept premium for DX.

**Default: serverless with scale-to-zero for inference.** Always-on pods only when traffic is steady AND latency-critical.

**Cold start mitigation (applies to any serverless provider):**

1. Enable NVMe model caching (provider-specific feature — reduces model load from minutes to seconds)
2. Set idle timeout to 5-15s — keeps warm workers alive for short bursts
3. Use NVMe-backed network volumes — model loads from local storage, not network download
4. Minimize container image — strip dev dependencies, use multi-stage Docker builds
5. Set min_workers=1 for latency-critical endpoints (always-warm, but you pay idle)

#### Client-Side Pattern (orchestrator)

```python
# Swap 3 lines in any OpenAI SDK code to point to your GPU provider
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=os.getenv("RUNPOD_API_KEY"),  # or TOGETHER_API_KEY, GROQ_API_KEY
    base_url=os.getenv("INFERENCE_BASE_URL"),  # provider endpoint
)
response = await client.chat.completions.create(
    model=os.getenv("INFERENCE_MODEL"),
    messages=[{"role": "user", "content": "Hello"}],
    stream=True,
)
```

Note: use `AsyncOpenAI` (not sync `OpenAI`) to avoid blocking the event loop per `10-python.md`. All major providers expose OpenAI-compatible endpoints.

### For Training / Fine-tuning — Selection Criteria

1. **Cheapest, fault-tolerant** → marketplace bid provider. Accept instability, design for checkpoint-resume.
2. **Stability for long runs (>24hr)** → SLA-backed dedicated pod. Pay more, avoid losing a 3-day run at hour 47.
3. **Custom CUDA/kernel** → KVM VM provider. Full root access.

**Default: cheapest marketplace for fine-tuning, SLA-backed for training >24hr.**

---

## Lifecycle: Spin Up → Execute → Checkpoint → Terminate

### Spin Up

- **Templates / Cloud-Init only.** Never SSH into a GPU instance and `pip install` manually.
- **Tag every instance:** `project`, `workload_type`, `created_by`, `max_lifetime_hours`. Untagged = kill candidate.

### Execute

- **Separate GPU compute from request routing.** The orchestrator (CPU, on the Fabrik VPS) routes requests. The GPU worker (external cloud) runs inference. Never mix them — mixing causes cascading OOM under burst.
- **Set `max_lifetime_hours`.** A zombie H100 at $3/hr = $72/day. The orchestrator auto-terminates via provider API.
- **Streaming for interactive, batching for background.** Real-time: SSE/WebSocket token streaming via the orchestrator. Batch: accumulate in PG queue, process in one GPU session, amortize cold start.

### Checkpoint (training only)

- **Async checkpointing mandatory.** Sync checkpointing blocks the GPU. Use `torch.distributed.checkpoint` (DCP).
- **Frequency:** every 15-30 min (on-demand instances), every 5 min (spot/preemptible).
- **Storage:** S3/R2/B2 only. Never local disk alone — it dies with the instance.
- **Naming:** `{project}/{run_id}/checkpoint-{step}-{timestamp}.pt`

```python
# Async checkpoint — does not block training
import torch.distributed.checkpoint as dcp

def save_checkpoint(model, optimizer, step: int, storage_path: str):
    state = {"model": model.state_dict(), "optimizer": optimizer.state_dict(), "step": step}
    dcp.save(state, storage_writer=dcp.FileSystemWriter(storage_path))
```

### Terminate

- **Immediately after work.** `DEL /pods/{id}` (RunPod), `vastai destroy` (Vast.ai), `DELETE /instances/{id}` (TensorDock).
- **Verify.** Poll status — some providers take 10-30s. If running after 60s, alert.
- **Clean up ephemeral volumes.** Persistent volumes (model weights, datasets) stay.

---

## Fault Tolerance

GPU instances are inherently unreliable. Spot instances preempt. Marketplace hosts vanish. OOM kills happen.

- **All spot/community workloads must be checkpoint-resumable.** Death mid-training → next worker picks up from last checkpoint.
- **Heartbeat:** worker → orchestrator every 30s. 3 missed → dead, spin replacement.
- **Warm standby** (revenue-critical inference only): second instance on different provider. Failover <60s vs 5-10min cold start.
- **Set `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`** to reduce CUDA memory fragmentation.
- **Provider calls from orchestrator** have timeout + retry + circuit-breaker per `58-resilience.md`. Every provider must have a row in `docs/RESILIENCE.md` §2a.

### Provider Gotchas <!-- verify at provisioning — these details change with provider updates -->

- **Vast.ai budget tier:** VRAM contention — host may oversell. OOM on a "24GB" card = overselling. Switch host.
- **RunPod Community:** shared host kernel. Custom CUDA drivers may conflict. Use RunPod Templates only.
- **TensorDock:** no snapshot API. Reproducibility via Cloud-Init scripts, not disk images.
- **Salad Cloud:** 15-25% monthly node churn (confirmed — inherent to consumer-node architecture). $0 egress. Design for the node dying at any moment.
- **Modal non-preemptible multiplier:** 3x cost. Most people don't realize until the bill arrives.

---

## Cost Control

GPU is the most expensive line item. Every decision minimizes idle GPU time.

1. **Default to managed APIs.** Most fabrik services never need GPU cloud.
2. **Scale to zero.** RunPod Serverless / Modal for inference. No persistent pods unless steady traffic AND latency-critical.
3. **Right-size.** Don't use H100 for a 7B model. L4/T4 handles <=13B. A100 40GB handles <=70B INT4.
4. **Quantize.** AWQ (best quality) or GPTQ (best speed) at 4-bit for inference. FP8 on H100/H200.
5. **Budget alerts.** Daily spend cap in provider dashboard. Orchestrator enforces a `MAX_DAILY_GPU_COST` env var — refuses to provision new instances if exceeded. (Until the GPU scaffold type exists, this logic lives in the orchestrator's own code, not in `specs/services/`.)
6. **Batch non-realtime.** Accumulate requests in PG queue, process in one GPU session. Amortize cold start.
7. **Multi-provider routing.** Train on Vast.ai (cheapest). Infer on RunPod Serverless (best cold start). Never put all eggs in one provider.
8. **Cost logging.** Every inference call logs cost to structured log. Monthly rollup via Grafana.

---

## Provider Snapshot — verify at provisioning time

<!-- Last verified: 2026-05-24. Prices, models, and provider features change frequently.
     Verify current rates at the provider's pricing page before provisioning.
     The durable frameworks above (decision table, selection criteria, lifecycle, fault tolerance)
     do NOT depend on these specific numbers. -->

### Managed API Providers

| Workload | Provider | Model example | Price (per 1M tokens) |
|---|---|---|---|
| Real-time chat, streaming | Groq | Llama 3.3 70B Versatile (LPU, <1s TTFT) | $0.59 input / $0.79 output |
| Batch processing, cost-sensitive | Together AI | Llama 4 Maverick | $0.27 input / $0.85 output |
| Batch (flat-rate alternative) | Together AI | Llama 3.3 70B Instruct Turbo | $0.88 flat (input+output) |
| Niche/custom models | Replicate | Any HuggingFace model | Variable, typically 2-5x Together |
| Code generation | Groq or Fireworks | 70B-class coder | $0.20 - $0.90 |
| Vision / multimodal | Together AI or Replicate | Vision models | $0.80 - $3.00 |

### GPU Cloud Providers (inference)

| Provider | Billing | H100 $/hr | Cold start | Egress | Notes |
|---|---|---|---|---|---|
| RunPod Serverless (PRO) | Per-request | $4.18 | FlashBoot: ~563ms measured, 95% < 2.3s (warm-worker dispatch from NVMe — not a true cold start) | $0 | Default for inference; pre-built vLLM worker. FlashBoot now standard for Flex workers. |
| Modal | Per-second | $4.56 (base GPU rate; CPU/RAM multipliers separate: US non-preemptible CPU/mem = 3.75x) | 1-4s | Included | Python decorator DX. GPU rate is flat regardless of region/preemption. |
| RunPod Secure Pod | Per-hour | $2.99 | N/A (always on) | $0 | SLA-backed, per-second billing |
| RunPod Community Pod | Per-hour | $1.99-2.69 | N/A | $0 | Shared host kernel |

### GPU Cloud Providers (training / fine-tuning)

| Provider | Billing | H100 $/hr | Stability | Notes |
|---|---|---|---|---|
| Thunder Compute | On-demand | $1.38 | Medium | New entrant — cheapest verified H100 on-demand |
| Vast.ai | Marketplace bid | $1.50-2.50 | Low-Medium | Host may oversell VRAM |
| Spheron Network | Spot/on-demand | $1.03 (spot SXM5) / $2.01 (on-demand PCIe) | Medium | Neo-cloud aggregator |
| TensorDock | KVM VM | $2.25-2.36 | High (99.99%) | Full root; no snapshot API |
| RunPod Community | Pod | $1.99-2.69 | Medium | Shared kernel; use templates only |
| RunPod Secure | Pod | $2.99 | High | SLA-backed for long runs |

### GPU Hardware

| GPU | VRAM | Mem BW | Best for | $/hr range |
|---|---|---|---|---|
| B200 | 192 GB | 8 TB/s | Frontier training, trillion-param | $5.00 - $6.50 |
| H200 | 141 GB | 4.8 TB/s | 70B+ FP16 inference, long context | $3.50 - $4.50 |
| H100 SXM | 80 GB | 3.35 TB/s | Distributed training, 70B INT4 | $1.50 - $3.00 |
| A100 80GB | 80 GB | 2 TB/s | Fine-tuning 7-70B, batch inference | $1.00 - $2.00 |
| L40S | 48 GB | 864 GB/s | FP8 inference, vision models | $0.40 - $0.90 |
| RTX 4090 | 24 GB | 1 TB/s | Prototyping, <=13B inference | $0.14 - $0.35 |
| L4 | 24 GB | 300 GB/s | Budget inference, video processing | $0.15 - $0.30 |
| T4 | 16 GB | 300 GB/s | Cheapest inference, demos, <=7B | $0.07 - $0.20 |

**Egress:** RunPod + TensorDock = $0. Vast.ai = $0.01-0.10/GB. Factor into TCO for data-heavy jobs.

**Distributed training:** InfiniBand required for multi-node. Standard Ethernet (1-10 Gbps) creates gradient sync bottleneck above 2 nodes.

### Embedding Models

Embedding model selection is owned by `65-rag-search.md`. Use whatever that pack specifies. Do NOT define embedding model defaults here — single-source to avoid drift.

---

## Decision Framework

```
Do you need AI inference in your service?
│
├── Can a managed API handle it? (< 1B tokens/month, no fine-tuned model)
│   └── YES → Together AI / Groq / Replicate. Stop here.
│
├── Is it a fine-tuned or private model?
│   ├── Low traffic → RunPod Serverless + vLLM (scale to zero)
│   └── High traffic → RunPod Secure Pod + vLLM (always-on)
│
├── Do you need to fine-tune?
│   ├── < 70B params → Vast.ai (cheapest A100/H100)
│   └── >= 70B or multi-day → RunPod Secure (stability)
│
├── Do you need to train from scratch?
│   ├── Single node → RunPod Pod (multi-GPU template)
│   └── Multi-node → Dedicated multi-GPU cluster (InfiniBand mandatory)
│
└── Local dev / prototyping?
    └── Ollama on WSL (see LOCAL_LLM_INFRASTRUCTURE.md)
```

---

## Integration with Fabrik (future)

**Not yet implemented.** When fabrik gains a GPU scaffold type:

- `specs/services/<id>.yaml` gets `gpu:` block: `type`, `provider_preference`, `max_daily_cost`, `checkpoint_bucket`, `auto_terminate_hours`
- GPU driver provisions via provider API, tags instance, monitors lifetime
- `fabrik destroy` terminates GPU instance + cleans volumes
- VPS sysadmin monitors GPU spend via provider API

**As of 2026-06-16** the shared lifecycle surface is **`fabrik gpu`** (RunPod + Modal + Vast.ai; try/finally cost-capped; state at `data/gpu-rent-state.json`; audit log at `logs/gpu-rent-history.jsonl`; reaper at `fabrik gpu reconcile --auto-destroy`). See [`docs/operations/gpu-rent.md`](../../../docs/operations/gpu-rent.md) and [`docs/development/plans/2026-06-16-fabrik-gpu-rent.md`](../../../docs/development/plans/2026-06-16-fabrik-gpu-rent.md). Services should call `fabrik.orchestrator.gpu_rent.rent(...)` instead of re-implementing provider-API + cost-cap + auto-terminate inline. The `fabrik scaffold ... --type python-api-gpu` shorthand wires the integration automatically.

Until the spec block above is implemented (Phase 6 work), services declare GPU usage via the `gpu_rent.rent()` call directly + a `shape.needs_gpu: true` annotation in their spec (no `gpu:` config block yet).

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| GPU inference on the Fabrik VPS | External GPU cloud (RunPod, Modal) or managed API (Together, Groq) |
| Self-hosting when < 1B tokens/month | Managed API — zero idle cost |
| Self-hosting frontier MoE models (400B+ parameter) | Managed API — VRAM cost is prohibitive |
| TGI for new deployments | vLLM (TGI is maintenance-mode since Dec 2025) |
| Quantizing during training/fine-tuning | FP16/BF16 only for training |
| Sync `OpenAI` client in async FastAPI | `AsyncOpenAI` with `base_url` swap |
| Hardcoded API keys or provider config | Pydantic Settings from env vars |
| `print()` in orchestrator code | `structlog` structured logger |
| Provider API calls without timeout + retry | `httpx.AsyncClient` + `tenacity` + circuit-breaker per `58-resilience.md` |
| GPU provider not in `docs/RESILIENCE.md` §2a | Add the row before adding the call site |
| SSH + manual `pip install` on GPU instance | Templates / Cloud-Init only |
| Untagged GPU instances | Tag: project, workload_type, created_by, max_lifetime_hours |
| Sync checkpointing during training | `torch.distributed.checkpoint` (async) |
| Checkpoints to local disk only | S3/R2/B2 — local disk dies with the instance |
| Zombie GPU instances running after work | Auto-terminate via provider API + verify poll |
| H100 for a 7B model | L4/T4 handles <=13B |
| Single provider for all workloads | Multi-provider routing (cost + resilience) |

---

## Related Rule Packs

- `10-python.md` — orchestrator FastAPI patterns, Pydantic Settings, `uv`, structlog, async
- `30-ops.md` — orchestrator Dockerfile, compose, Traefik, resource limits, `fabrik apply` deploy
- `55-observability.md` — orchestrator structured logging, `/health`, `/metrics`, GlitchTip
- `58-resilience.md` — timeout/retry/circuit-breaker for provider API calls, `docs/RESILIENCE.md` contract
- `75-workers-jobs.md` — PG job queue for async/batch GPU requests, adaptive worker pool for orchestrator workers

---

## Done When

### Orchestrator (Fabrik service on VPS)

- [ ] Standard `python-api` scaffold: Dockerfile (`slim-bookworm`), compose (Traefik, resource limits, `coolify` network).
- [ ] `/health` verifies DB + Redis + at least one inference provider reachable.
- [ ] `/metrics` exposes `inference_requests_total`, `inference_latency_seconds`, `inference_tokens_total`, `inference_cost_usd_total`.
- [ ] Structured logging via `structlog` — no `print()`. Every inference call logged with provider, model, tokens, cost.
- [ ] GlitchTip initialized before app start.
- [ ] Provider API calls wrapped with `httpx.AsyncClient` + timeout + retry + circuit-breaker.
- [ ] Every provider has a row in `docs/RESILIENCE.md` §2a.
- [ ] Provider failover chain implemented — primary → fallback → graceful degradation.
- [ ] API keys in env vars (Pydantic Settings) — never hardcoded.
- [ ] Async/batch requests flow through PG job queue per `75-workers-jobs.md`.
- [ ] Daily cost cap enforced — orchestrator refuses to provision if exceeded.

### GPU Worker (external cloud)

- [ ] Provider selected per decision framework (managed API first, GPU cloud only when justified).
- [ ] Engine selected: vLLM (default), SGLang, or TensorRT-LLM with documented justification.
- [ ] Quantization selected per decision guide — FP8 on H100, AWQ on A100/L40S, never quantize training.
- [ ] VRAM budget calculated — model fits with 15-20% headroom.
- [ ] Cold start mitigated (NVMe cache, idle timeout, min_workers).
- [ ] All instances tagged (project, workload_type, created_by, max_lifetime_hours).
- [ ] Auto-terminate after work — verified via provider API poll.
- [ ] Training/fine-tuning: async checkpointing to B2/S3/R2, frequency per instance type (5min spot, 15min on-demand).
- [ ] Fault tolerance: checkpoint-resumable, heartbeat every 30s, replacement spin on 3 missed.
