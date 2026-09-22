---
activation: glob
globs: ["**/gpu/**", "**/inference/**", "**/ml/**", "**/training/**", "**/workers/**/gpu*", "**/serverless-gpu/**"]
description: GPU worker discipline — decision framework for API vs self-host, provider/engine/quantization selection, two-faced architecture, lifecycle via `fabrik gpu`, fault tolerance
trigger: glob
currency_pass: 2026-09-22
---
<!-- CONSUMER: Coding agents building GPU inference/training orchestrators + Traycer (tech-plan)
     GOAL: API vs self-host decision, two-faced architecture, provider selection, cost control
     TRAYCER USAGE: Decision framework shapes tech-plan. Injects orchestrator requirements into tickets.
     AGENT USAGE: Build the orchestrator as a Fabrik python-api-gpu. GPU worker is external; its lifecycle is `fabrik gpu`. -->

# GPU Workers Rules

Apply when building services that use GPU compute for inference, training, or fine-tuning. This file is the decision authority — it tells you when NOT to use GPU cloud (most of the time), and when you must, how to do it right.

For local Ollama inference on the dev machine, see `docs/reference/LOCAL_LLM_INFRASTRUCTURE.md`.

---

## Two-Faced Architecture

GPU services are **two-faced** like mobile-app and chrome-extension:

| Lane | Runs on | Deploy | Rules |
|---|---|---|---|
| **Orchestrator** (API gateway + job dispatch) | VPS via `fabrik apply` | The `python-api-gpu` scaffold — a standard `python-api` (Dockerfile, compose, Traefik, registrars) plus `src/<package>/gpu_handler.py`, a HUB-CONTEXT wrapper over `fabrik.orchestrator.gpu_rent.rent()` — which must not be WIRED into any container code path (it ships by default via `COPY . .`; § Lifecycle, § Done When) | `10-python.md`, `30-ops.md`, `55-observability.md`, `58-resilience.md`, `75-workers-jobs.md` |
| **GPU Worker** (inference / training / fine-tuning) | External GPU cloud (RunPod, Modal, Vast.ai — the three `fabrik gpu` drives) or managed API (Together, Groq, …) | Provider API through `fabrik gpu` / `gpu_rent` — NOT the Fabrik VPS (it has no GPU) | This file |

- The **orchestrator** is a standard Fabrik service: `postgres-main:5432`, `redis-main:6379`, structlog, `/health`, `/metrics`, GlitchTip, Traefik labels, `deploy.resources.limits.memory`, the `-slim-<debian_codename>` base (`<debian_codename>` = the value in `.windsurf/rules/versions.yaml`, written out), `fabrik` network. All `30-ops.md` rules apply. ⚠️ Verify the EMITTED Dockerfile: the scaffold's base image lags that yaml (backlogged, fleet beat) — the rule is the yaml value, not whatever the template wrote.
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
| Frontier MoE models (400B+ parameter) | **Always API** | MoE requires VRAM for ALL parameters even though only a fraction activates per token. Self-hosting needs a multi-GPU node (4x H100 at INT4 for Llama 4 Maverick, 8x H200 for DeepSeek-class); the one exception is `gpt-oss-120b`, whose MXFP4 experts fit a single 80 GB GPU. API providers amortize the rest. |
| Fine-tuning / training | **Always GPU cloud** | No managed API for this. Need raw GPU access. |
| Prototyping / dev | **Local Ollama first** | Free, instant, offline. Only go cloud when local VRAM can't fit the model. See `docs/reference/LOCAL_LLM_INFRASTRUCTURE.md` for machine specs. |

**The concrete break-even:** a self-hosted H100 at ~$2/hr running 24/7 = ~$1,500/month. A 70B-class open-weight model costs $0.10-$1.04 per 1M tokens depending on the provider (Provider Snapshot) — a 10x spread — so the break-even sits anywhere from ~1.5B to ~15B tokens/month; re-derive it against the provider you would actually use. A solo dev's service will almost never reach it.

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
    chat_model: str = "openai/gpt-oss-120b"
    batch_provider: str = "together"
    batch_model: str = "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"
    groq_api_key: str = ""
    together_api_key: str = ""
    runpod_api_key: str = ""
    runpod_endpoint_id: str = ""

# All providers expose OpenAI-compatible /v1/chat/completions — use openai SDK with base_url swap
```

API keys live in env vars (compose env or `.env`). Never hardcoded. See `10-python.md` § Config Loading. Model ids are ENV VALUES, not constants: the defaults above are the Provider Snapshot's date-stamped examples and a provider retires a model id without notice.

---

## Orchestrator Responsibilities

The orchestrator is a `python-api-gpu` Fabrik service. It handles:

### Job Queue (async/batch inference)

For non-interactive workloads (batch embeddings, report generation, fine-tune dispatch):

- Enqueue via PG `SKIP LOCKED` per `75-workers-jobs.md` — same outbox pattern, idempotency, retry/backoff.
- The orchestrator dequeues and calls the GPU provider API with timeout + retry.
- If the adaptive worker pool applies (per `75-workers-jobs.md`), the orchestrator scales workers that call GPU endpoints, not GPU instances directly.

### Direct Call (real-time inference)

For interactive workloads (chat, autocomplete, streaming):

- Call the provider API directly from the API handler — no queue.
- Wrap with `httpx.AsyncClient` + timeout + retry + circuit-breaker per `58-resilience.md`.
- Stream SSE tokens back to the client. If the provider fails, return a graceful fallback (cached response, error message, or degraded mode).

### Provider Failover

**A provider death is not a blip.** Retry/backoff/circuit-breaker all heal a *transient* fault. A model
that is gone for this whole run needs a **SWAP**, which no retry loop is empowered to make. The chain
below therefore needs **two kinds of diversity** — and an `except` that catches the errors a dead free
tier actually returns.

```python
# Quality-ordered candidates. INTRA-provider diversity (a single model can die while its
# siblings stay up) AND cross-provider diversity (a whole provider can go down).
INFERENCE_CANDIDATES = [
    {"provider": "groq",     "model": "openai/gpt-oss-120b"},
    {"provider": "groq",     "model": "openai/gpt-oss-20b"},               # same provider, live sibling
    {"provider": "together", "model": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"},
]

_key = lambda r: f'{r["provider"]}/{r["model"]}'

def rebuild_chain() -> list[dict]:
    # ONCE at run start (never per item): probe every candidate, keep the live ones in YOUR
    # order, so the best route returns to the front by itself when it recovers. The helper is
    # fabrik-lib `health-probe/` (the governance sync vendors it at `libs/health_probe/` — `fabrik_synced_manifest.py::VENDORED_DIRS`; a project that has not synced does not have it yet; it also feeds `alerting/`):
    #   live_chain(candidate_names, probe_results) -> .chain (survivors), .dropped, .degraded
    # An unprobed candidate is DROPPED, never assumed healthy — probe_for(r) returns a zero-arg
    # probe whose result's `system` == _key(r). With NO healthy candidate live_chain RAISES —
    # in a batch run let it abort at start; in a long-lived service catch that ValueError, keep
    # serving the per-request graceful fallback, and let /health report the provider map with a
    # non-200 (55-observability: a consumed API is a dependency) instead of crash-looping — the
    # non-200 marks the container unhealthy and trips Gatus; Traefik keeps routing (no LB healthcheck
    # label is emitted), so it buys an alert, not a drain.
    live = live_chain([_key(r) for r in INFERENCE_CANDIDATES],
                      run_all_checks([probe_for(r) for r in INFERENCE_CANDIDATES])).chain
    return [r for r in INFERENCE_CANDIDATES if _key(r) in live]

async def infer_with_failover(messages: list[dict]) -> str:
    # Do NOT hand-roll this at all if you route via OpenRouter (see the bullet below).
    for route in CHAIN:  # CHAIN = rebuild_chain() at run start
        try:
            return await call_provider(route, messages, timeout=30.0)
        except (httpx.TimeoutException, httpx.ConnectError):
            reason = "transport"
        except httpx.HTTPStatusError as e:
            # A billing-gated free tier returns 402; quota returns 429. Both are HTTPStatusError,
            # so a transport-only except would PROPAGATE them and the remaining rungs would
            # never be tried. Retry 5xx; SWAP on 402/403/429.
            if e.response.status_code < 500 and e.response.status_code not in (402, 403, 429):
                raise                                   # a real client error: don't mask it
            reason = f"http_{e.response.status_code}"
            # 429 has TWO correct responses; which applies depends on whether a live sibling
            # exists — see the bullet below before copying this.
        logger.warning("provider_failover", failed=route["provider"], model=route["model"], reason=reason)
    return FALLBACK_RESPONSE  # graceful degradation — and it must be an EXERCISED path (below)
```

- Every provider in the chain must have a row in `docs/RESILIENCE.md` §2a.
- **Circuit-breaker per `(provider, model)`, not per provider.** A per-provider breaker is the wrong
  resolution for a model-specific death: it writes off live capacity and hides the real failure — one
  model of a provider goes ReadTimeout-down while its siblings stay up.
- **Exercise the last rung on a schedule.** An untested fallback is a silently-dead fallback (an expired
  credential on the last resort makes the chain one rung shorter than its author believes). Prove the
  SWAP, not just the retry: a test that only asserts backoff fires certifies nothing about provider death.
- **A 429 is NOT automatically a swap — reconcile with [`self-healing`](self-healing.md) row 3.** That row
  prescribes `pause-state.set_global_pause(resource, ttl=min(Retry-After, cap))` for a vendor rate-limit — the vendor value CLAMPED before it becomes a queue-wide TTL — and it is
  right whenever the rate-limited provider is your ONLY route: swapping there just burns the next rung and
  you lose the `Retry-After` the vendor handed you. Swap on 429 **only when a live sibling exists** — re-probe THAT ONE sibling on the 429 path — a targeted probe, not a chain rebuild; the sample's
  "never per item" governs the rebuild (the chain was built at start, and a sibling dead since then is a
  wasted swap into a dead rung); otherwise pause with the
  vendor's TTL, clamped — and `cap` is a value YOU set and state (an unbounded cap is a day-long pause). The chain above swaps because it is, by
  construction, a multi-candidate chain — a single-provider caller must take row 3's path instead.
- **Routing through OpenRouter?** Then the live chain is largely the gateway's job, not yours — see
  `58-resilience.md` § Provider-death resilience for which outcomes you owe on which route, and for the
  `sort`/`order` trap that silently opts you out of it.

### Health Endpoint

The orchestrator's `/health` must verify:

- DB connectivity (`SELECT 1` on `postgres-main`)
- Redis connectivity (if used)
- At least one inference provider reachable (lightweight ping, not a full inference call)
- Report provider status in the response body. Status semantics follow `55-observability.md` (a consumed API is a dependency): one dead provider with a live sibling is HTTP 200 with the per-provider map; ZERO reachable providers is non-200 with the same map — the container reads unhealthy and Gatus pages, while Traefik keeps routing and the API keeps serving its graceful fallback per request

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
  Rental spend is metered separately by `fabrik gpu` itself (`gpu_rent_*` counters written to
  `logs/gpu-rent-metrics.prom` for the node-exporter textfile collector — `docs/operations/gpu-rent.md`).
- **Cost logging:** every inference call logs `provider`, `model`, `input_tokens`, `output_tokens`, `duration_s`, `cost_usd` as structured JSON. Monthly rollup via Grafana LogQL query.
- **GlitchTip:** init before app start. Provider API errors auto-capture.
- **Cold start alert:** if p95 TTFT > 5s (serverless) or > 60s (pod), alert via Prometheus.

---

## When You DO Need GPU Cloud

Three cases: (1) self-hosted inference at scale, (2) fine-tuning, (3) training.

### Inference Server Selection

**TGI is dead.** text-generation-inference entered maintenance mode on 2025-12-11 and the repository was archived on 2026-03-21; Hugging Face's Inference Endpoints docs recommend vLLM or SGLang in its place (the engine is still chosen per endpoint — nothing "defaults").

| Engine | Use when | Throughput (H100, 70B) | Cold start |
|---|---|---|---|
| **vLLM** | Default for everything. Broadest hardware support, largest community, battle-tested. | Baseline (1x) | Weights into GPU memory: ~30s for a 7-8B, minutes for a 70B — unless a snapshot/NVMe cache serves it (§ cold start mitigation) |
| **SGLang** | Multi-turn chat, structured output (JSON mode), prefix-heavy RAG pipelines. RadixAttention gives real gains on shared prefixes. | Ahead on prefix-heavy workloads (multiples on shared-prefix RAG); near parity on unique-prompt batches — benchmark YOUR traffic | as vLLM |
| **TensorRT-LLM** | Maximum throughput on NVIDIA. Since v1.0 the PyTorch backend is the ONLY backend — no checkpoint conversion, no engine build (the old compile step is gone). NVIDIA GPUs only. | Highest peak on NVIDIA; published runs put it single-digit to ~30% over vLLM, configuration-dependent | as vLLM (model load, no compile) |
| **Ollama** | Local dev only. Not for production serving. | N/A | Instant (already loaded) |

**Default: vLLM.** Switch to SGLang only if your workload is measurably prefix-heavy. Switch to TensorRT-LLM only if you've validated throughput gains on YOUR model. Engine-vs-engine ratios move with every release — never carry a number here; measure on your model.

### Quantization Decision Guide

Quantization is the #1 lever for reducing GPU cost. Smaller model = cheaper GPU. Quality retention is model-dependent — benchmark on your specific model before committing to a quantization level.

| Method | Bits | Quality | Speed (GPU) | Best for |
|---|---|---|---|---|
| **FP16/BF16** | 16 | baseline | 1x | Training, fine-tuning — never quantize during training |
| **FP8** | 8 | near-lossless | native on Hopper and Blackwell | Production inference on H100/H200 |
| **NVFP4** | 4 | within ~1% of FP8 on large models | up to ~3x FP8 peak; ~1.8x smaller than FP8 | Production inference on Blackwell (B200/GB200/B300) — hardware-native; FP4-ready weights ship under the `nvidia/` HF namespace |
| **AWQ** | 4 | best-quality 4-bit | fast | Production inference on A100/L40S/RTX — preserves salient weights by activation statistics |
| **GPTQ** | 4 | slightly below AWQ | fastest 4-bit kernels (Marlin) | Maximum throughput inference |
| **GGUF (Q4_K_M)** | 4 | good | varies | CPU or hybrid CPU+GPU (llama.cpp/Ollama). Not for pure GPU serving — use AWQ/GPTQ/FP8 |

**Decision rule:**

- Training/fine-tuning → FP16/BF16 always
- Production inference on H100/H200 → FP8 (best quality-speed ratio with native hardware support)
- Production inference on Blackwell (B200/GB200/B300) → NVFP4 (native 4-bit; FP8 still runs there but is no longer the best)
- Production inference on A100/L40S/RTX → AWQ (best quality at 4-bit)
- Maximum throughput, quality less critical → GPTQ
- Local/edge/CPU → GGUF Q4_K_M
- **MoE models quantize like any other** — expert weights are weights; what stays large is the TOTAL parameter count every expert must sit in VRAM for. Quantize to fit, then re-read the frontier-MoE row above: at 400B+ total parameters even 4-bit needs a multi-GPU node, which is why the answer is still API.

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
| 405B dense | 810 GB | 405 GB | 203 GB | 4-8x H200 (FP8, headroom for KV cache and power-of-2 tensor parallel) or 8x A100 (INT4) |

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

**The comparison is executable:** `fabrik gpu compare <kind> --hours N --utilization U` prices the three wired providers (RunPod, Modal, Vast.ai) for a workload from `gpu_rent.HOURLY_USD_BY_PROVIDER` and names the cheapest viable one — run it before you pick, and treat this pack's snapshot as the wider market, not the authority for those three.

**Cold start mitigation (applies to any serverless provider):**

1. Enable NVMe model caching (provider-specific feature — reduces model load from minutes to seconds)
2. Set idle timeout to 5-15s — keeps warm workers alive for short bursts
3. Use NVMe-backed network volumes — model loads from local storage, not network download
4. Minimize container image — strip dev dependencies, use multi-stage Docker builds
5. Set a warm floor for latency-critical endpoints (RunPod `minWorkers=1`, Modal `min_containers=1`; `rent(workers_min=1)` is the library argument; `fabrik gpu rent` exposes no flag for it, so the warm floor is set from code) — always-warm, but you pay idle
6. On Modal, enable Memory Snapshots (checkpoint after model load; restores in seconds instead of reloading weights) and tune `scaledown_window`

#### Client-Side Pattern (orchestrator)

```python
# Swap 3 lines in any OpenAI SDK code to point to your GPU provider
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=os.getenv("RUNPOD_API_KEY"),  # or TOGETHER_API_KEY, GROQ_API_KEY
    base_url=os.getenv("INFERENCE_BASE_URL"),  # provider endpoint — RunPod serverless vLLM: https://api.runpod.ai/v2/<endpoint-id>/openai/v1
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

## Lifecycle: Spin Up → Execute → Checkpoint → Terminate — through `fabrik gpu`

The lifecycle is a SHIPPED hub surface, not a pattern to re-implement: `fabrik gpu rent|list|status|destroy|pause|resume|reconcile|compare|history` and the library `fabrik.orchestrator.gpu_rent.rent(kind, workload=…, provider=…, max_lifetime_hours=…, max_cost_usd=…, work_fn=…)` (context-manager form `rented(...)`), with providers `runpod` · `modal` · `vast`, kinds `serverless` and the pod aliases (`pod-h100`, `pod-h100-pcie`, `pod-h100-nvl`, `pod-a100`, `pod-a100-sxm`, `pod-h200`, `pod-l40s`, `pod-rtx-4090`), state in `data/gpu-rent-state.json`, an audit line per rental in `logs/gpu-rent-history.jsonl`, and actual cost recorded to the usage tracker. Authority: `docs/operations/gpu-rent.md`.

⚠️ **`rent()` runs HUB-SIDE.** It reads provider keys from `/opt/fabrik/.env.sysadmin`, writes `$FABRIK_ROOT/data/gpu-rent-state.json`, and checks the daily cap in `~/.fabrik/ai_usage.db` — none of which a deployed service has, and the emitted service's `requirements.txt` does not carry `fabrik` (scaffold defect, fleet beat). So a deployed orchestrator never rents: it enqueues the GPU work as a job the HUB executes (`fabrik gpu rent <kind> --workload <name>`, or `rent(work_fn=…)` from a hub process), or it calls a serverless endpoint the hub provisioned and pinned (`RUNPOD_SERVERLESS_ENDPOINT_ID`). The scaffold's `gpu_handler.rent_for_workload(workload, work_fn)` is that hub-context helper — it imports only where `fabrik` is installed (`/opt/fabrik/.venv`). The service never calls a provider's create/destroy API inline either: the rule is *through `fabrik gpu`*, with the hub as the caller. `providers`: `runpod` is the library default; the CLI defaults to `auto`, which prices the three via `selection_advice()`.

### Spin Up

- **`rent()` / `rented()` only — templates or images, never SSH + `pip install` on a GPU instance.** `dry_run=True` returns the plan (kind, provider, estimate) without a provider call — but BOTH cost caps fire first and the daily cap reads the live `~/.fabrik/ai_usage.db`, so a test sets `max_cost_usd` and `MAX_DAILY_GPU_COST` explicitly or fails on the box's spend.
- **Tags are written for you — on PODS.** `rent()` injects `FABRIK_PROJECT`, `FABRIK_WORKLOAD`, `FABRIK_CREATED_BY`, `FABRIK_MAX_LIFETIME_HOURS`, `FABRIK_SESSION_ID` into every pod; the reaper recognises Fabrik resources by `FABRIK_SESSION_ID` and never touches a foreign one. ⚠️ Serverless endpoints are NOT tagged today (`_create_serverless_endpoint` never passes `env=` — mailed to fleet), so an endpoint whose state record is lost reads as FOREIGN to `reconcile` and is never reaped: keep `data/gpu-rent-state.json` intact, and prefer a pod when the endpoint carries a warm floor (`workers_min>0` bills while idle — an unreapable true scale-to-zero endpoint idles at $0). Anything provisioned outside `rent()` MUST carry the same five — that buys orphan DETECTION only (§ Terminate); an untagged instance is a zombie candidate nobody can prove is ours.

### Execute

- **Separate GPU compute from request routing.** The orchestrator (CPU, on the Fabrik VPS) routes requests. The GPU worker (external cloud) runs inference. Never mix them — mixing causes cascading OOM under burst.
- **`max_lifetime_hours` is a `rent()` argument, not a note.** A zombie H100 at $3/hr = $72/day. It sizes the cost estimate both caps check BEFORE the provider call (§ Cost Control) and it is the lifetime the reaper enforces AFTER (§ Terminate).
- **Streaming for interactive, batching for background.** Real-time: SSE/WebSocket token streaming via the orchestrator. Batch: accumulate in PG queue, process in one GPU session, amortize cold start.

### Checkpoint (training only)

- **Async checkpointing mandatory.** A checkpoint that blocks the training step wastes the GPU for its whole upload. The hub primitive is `fabrik.orchestrator.gpu_checkpoint` — `write_checkpoint_to_tarball(...)` serializes, `checkpoint_to_b2(payload: bytes, …)` uploads in a background thread, `load_latest_checkpoint(project, run_id)` resumes from the highest step. For in-process distributed state use `torch.distributed.checkpoint.async_save` (DCP) — `dcp.save` is SYNCHRONOUS and blocks the step.
- **Frequency:** every 15-30 min (on-demand instances), every 5 min (spot/preemptible).
- **Storage:** S3/R2/B2 only — the hub primitive writes to the fleet's B2 (`fabrik-gpu-checkpoints/` prefix, credentials in `.env.sysadmin`). Never local disk alone — it dies with the instance.
- **Naming:** `fabrik-gpu-checkpoints/{project}/{run_id}/checkpoint-{step:08d}-{ts}.tar.gz` — what `gpu_checkpoint` writes (the bucket prefix included); a hand-rolled writer uses the same key so `load_latest_checkpoint` can resume it.

```python
# In-process async checkpoint — does not block training (torch.distributed.checkpoint)
import torch.distributed.checkpoint as dcp

def save_checkpoint(model, optimizer, step: int, storage_path: str):
    state = {"model": model.state_dict(), "optimizer": optimizer.state_dict(), "step": step}
    return dcp.async_save(state, storage_writer=dcp.FileSystemWriter(storage_path))  # a Future; await it before the NEXT save
```

### Terminate

- **`rent()` destroys in its `finally` — on success or exception, with a recorded-id fallback when the create/wait step itself raised. It imposes NO timeout on `work_fn`**, and `max_lifetime_hours` is enforced by the REAPER from the state record's `expires_at` (`lifetime_exceeded`), not by a timer inside `rent()` — the `FABRIK_MAX_LIFETIME_HOURS` tag is provenance, read by nothing, so a hand-provisioned resource has no lifetime cap at all. A hung `work_fn` holds the GPU until the reaper timer fires; the timer is what makes the cap real. `keep_on_failure=True` / `keep_warm_after_use=True` are the only ways a rental survives the call, both deliberate, named arguments — a kept pod is `lifetime_exceeded` once past its hours. ⚠️ Prefer `rent(work_fn=…)` over the context-manager `rented()`: today `rented()` lacks the recorded-id fallback (a `wait_for_running` failure orphans the pod) and catches only `RunPodError` on destroy (mailed to fleet).
- **The reaper is the second line:** `fabrik gpu reconcile --auto-destroy` compares local state to the live provider accounts and destroys drift — `lifetime_exceeded` and `destroy_pending` from the STATE record, orphans by tag; install the user-mode systemd timer from `docs/operations/gpu-rent.md` § Scheduled reaper (every 10 min). Alert on the TEXTFILE's age, not on the in-file value: `node_textfile_mtime_seconds{file="gpu-rent-metrics.prom"}` older than 3600 s, or `absent(gpu_rent_last_reconcile_age_seconds)` — the age series is written only by the reaper unit's own `ExecStartPost`, so a timer that was never installed leaves it absent, one that died leaves it frozen small, and a never-run reconcile writes `-1`: an alert on `> 3600` can never fire in exactly the cases it exists for.
- **Verify** — `fabrik gpu status <id>` after a manual `destroy`; some providers take 10-30s. If still running after 60s, alert.
- **Clean up ephemeral volumes.** Persistent data (model weights, datasets, checkpoints) lives in B2, not on the rental.

---

## Fault Tolerance

GPU instances are inherently unreliable. Spot instances preempt. Marketplace hosts vanish. OOM kills happen.

- **All spot/community workloads must be checkpoint-resumable.** Death mid-training → next worker picks up from last checkpoint.
- **Heartbeat:** worker → orchestrator every 30s. 3 missed → dead, spin replacement.
- **Warm standby** (revenue-critical inference only): second instance on different provider. Failover <60s vs 5-10min cold start.
- **Set `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`** to reduce CUDA memory fragmentation — it is off by default, documented experimental, and ignored under `backend:cudaMallocAsync`.
- **Provider calls from orchestrator** have timeout + retry + circuit-breaker per `58-resilience.md`. Every provider must have a row in `docs/RESILIENCE.md` §2a.

### Provider Gotchas <!-- verify at provisioning — these details change with provider updates -->

- **Vast.ai budget tier:** VRAM contention — host may oversell. OOM on a "24GB" card = overselling. Switch host.
- **RunPod Community:** shared host kernel. Custom CUDA drivers may conflict. Use RunPod Templates only.
- **TensorDock:** snapshot support unconfirmed — reproduce via Cloud-Init scripts, never via a disk image you cannot re-create.
- **Salad Cloud:** consumer RTX nodes (plus an RTX PRO 6000 Blackwell dedicated tier) — no H100/A100. Nodes preempt with ~30 min minimum runs and no published churn figure; design for the node dying at any moment. $0 egress.
- **Modal:** GPU is billed per second at a flat rate; CPU and memory are billed separately; non-preemptible execution is **3x base price** and a region multiplier (1.15-1.75x) stacks on top — read the pricing page before assuming the GPU line is the bill.
---

## Disposability (12-Factor IX)

CRITICAL: GPU jobs are the MOST expensive kind to silently drop. A single dropped training run at hour 47 wastes $141+ in GPU time. Every GPU worker MUST implement disposability per 12-Factor IX.

> *"Graceful shutdown is achieved by returning the current job to the work queue"*
> *"All jobs are reentrant … idempotent"*
> Processes must be *"robust against sudden death"*

### SIGTERM Handler (mandatory)

The GPU worker process MUST trap `SIGTERM` and `SIGINT` via Python's `signal` module. On signal:

1. **Stop accepting new jobs immediately.** Set an in-process flag; the claim loop checks it before dequeuing.
2. **Determine whether the in-flight job can complete.** If the remaining inference/training step can finish inside the grace period (default: `GRACEFUL_SHUTDOWN_TIMEOUT_SEC = 60`), let it finish.
3. **If it cannot finish: return the job to the queue.** Update the queue row — reset `status` to `'pending'`, reset `attempts` if needed per retry policy. The orchestrator's orphan sweep re-enqueues it if the worker dies before resetting.
4. **Free the GPU before exiting.** Release CUDA context (`torch.cuda.empty_cache()`, `del model`), unload the model from GPU memory, close provider SDK clients. This ensures the next worker can claim the device — GPU memory is a single-consumer resource; a leaked context blocks the next allocation.
5. **Exit with code 0** after cleanup. Do not `os._exit(1)` — that bypasses signal handlers and leaves CUDA state dirty.

```python
import signal, os, torch

_shutting_down = False
_inflight_job_id: str | None = None
_graceful_timeout: int = 60  # env GRACEFUL_SHUTDOWN_TIMEOUT_SEC

def _handle_sigterm(signum, frame):
    global _shutting_down
    _shutting_down = True
    if _inflight_job_id is None:
        os._exit(0)
    # If in-flight job can finish in time, let it; otherwise return to queue
    # The claim loop checks _shutting_down after each token/step

signal.signal(signal.SIGTERM, _handle_sigterm)
signal.signal(signal.SIGINT, _handle_sigterm)
```

### Job Idempotency (deterministic key)

Every GPU job MUST be idempotent — re-running must NOT double-charge a paid inference API, duplicate outputs, or submit duplicate training checkpoints.

- **Derive the idempotency key deterministically** from the stable business properties that define the operation: e.g. `SHA-256(inference_request_id + model_hash + input_payload_hash)`. Do NOT include a wall-clock timestamp or random UUID — they defeat dedup on retry.
- **Store the key** in a unique constraint column (dedicated `idempotency_keys` table or `processed_at` on the domain entity). On duplicate key, skip execution.
- **Paid API safety:** if the GPU worker calls a billed external API (Together, Groq, RunPod serverless), the idempotency check MUST happen BEFORE the API call. Otherwise a retry burns money even though the result is discarded.
- **Training checkpoint idempotency:** if a training step writes checkpoint N, a retry that replays step N from the prior checkpoint must produce byte-identical state N. Use deterministic random seeds (not wall-clock) and fixed data ordering.

### Preemptible / Spot Instance Handling

Preemptible GPU instances (spot, marketplace, consumer-node providers like Salad Cloud) can vanish without warning — no `SIGTERM` at all, just a kill signal from the hypervisor.

- **Architect for non-graceful death by design.** If a worker is killed mid-job, the orchestrator's orphan sweep (visibility timeout + sweep query per `75-workers-jobs.md`) reclaims the job and resets it to `pending`.
- **Checkpoint frequency for training:** every 5 min on spot/preemptible (already mandated in § Checkpoint above). Inference jobs that are interrupted just need requeue — the caller retries.
- **No graceful-shutdown dependency.** Never assume the worker will get a clean `SIGTERM` on spot/preemptible. The job must survive a hard kill at any point.

### Cross-Reference to 75-workers-jobs.md

The full queue contract (PG `SKIP LOCKED`, outbox pattern, retry/backoff, dead-letter handling, visibility timeout, orphan sweep, the SIGTERM requeue fast path) lives in `75-workers-jobs.md`. THIS section adds the GPU-specific mandates that 75 does NOT cover:

| Concern | 75 covers? | This section adds |
|---|---|---|
| SIGTERM handler | Yes — trap, drain, requeue fast path | GPU-release (CUDA context, model unload) before exit |
| Return job to queue | Yes — requeue on SIGTERM | The in-flight step's finish-or-return decision against the grace period |
| Idempotency | Generic key derivation | Paid-API idempotency guard, checkpoint determinism |
| Orphan sweep | Yes — full contract | Spot/preemptible death MUST be survivable without graceful path |
| Visibility timeout | Yes — 6x expected time | Worst-case GPU jobs may need higher multiplier (10x+) |

**Never skip this section because 75 exists.** If `src/inference/` loads THIS pack and NOT 75, the GPU worker gets zero disposability guidance without this section.
---

## Cost Control

GPU is the most expensive line item. Every decision minimizes idle GPU time.

1. **Default to managed APIs.** Most fabrik services never need GPU cloud.
2. **Scale to zero.** `kind="serverless"` (RunPod / Modal / Vast.ai through `rent()`). No persistent pods unless steady traffic AND latency-critical.
3. **Right-size.** Don't use H100 for a 7B model. L4 handles <=13B INT4, T4 <=7B; a 70B INT4 needs an 80 GB card (35 GB weights + KV cache + headroom).
4. **Quantize.** AWQ (best quality) or GPTQ (best speed) at 4-bit for inference. FP8 where the hardware has it natively.
5. **Two cost caps, both enforced BEFORE the provider call by `rent()`:** the per-call `max_cost_usd` (estimate = hourly rate × `max_lifetime_hours`) and the daily `MAX_DAILY_GPU_COST` (env, `.env.sysadmin`, default $50; today's tracked GPU spend + the estimate must fit). Either breach raises `GPUBudgetExceededError` and nothing is provisioned. Set the provider dashboard's spend cap too — it is the cap `rent()` cannot see (a hand-provisioned pod).
6. **Batch non-realtime.** Accumulate requests in PG queue, process in one GPU session. Amortize cold start.
7. **Multi-provider routing.** Train on the cheapest marketplace. Infer on the best cold start. `fabrik gpu compare` prices the three wired providers per workload. Never put all eggs in one provider.
8. **Cost logging.** Every inference call logs cost to structured log; every rental lands in `logs/gpu-rent-history.jsonl`, and POD rentals in the `gpu_rent_cost_usd_total` counter — a serverless rental's actual cost is recorded as $0 today, and pod cost is priced at RunPod rates whatever the provider (so the daily cap under-counts Modal by roughly a quarter; both mailed to fleet). Meter serverless and Modal spend from the provider dashboard until then. Monthly rollup via Grafana.

---

## Provider Snapshot — verify at provisioning time

<!-- Last verified: 2026-09-22 (claims rows gpu-* in CLAIMS.yaml carry the URLs). Prices, models, and
     provider features change frequently — verify current rates at the provider's pricing page before
     provisioning. The durable frameworks above (decision table, selection criteria, lifecycle, fault
     tolerance) do NOT depend on these specific numbers. For RunPod / Modal / Vast.ai the hub's own
     table (`gpu_rent.HOURLY_USD_BY_PROVIDER`, `fabrik gpu compare`) is the copy the code prices with —
     stamped 2026-06-16 on a quarterly re-verify cadence, so just past due (mailed to fleet); where it and this
     snapshot disagree, this snapshot is the newer number and the code's caps are computed on the older one. -->

### Managed API Providers

| Workload | Provider | Model id | $ per 1M tokens (in / out) |
|---|---|---|---|
| Real-time chat, streaming | Groq | `openai/gpt-oss-120b` (LPU, sub-second TTFT). `llama-3.3-70b-versatile` and `llama-3.1-8b-instant` left the self-serve tiers on 2026-08-16 — enterprise-only | $0.15 / $0.60 |
| Real-time chat, cheapest | Groq | `openai/gpt-oss-20b` | $0.075 / $0.30 |
| Batch, cheapest 70B-class | DeepInfra | `meta-llama/Llama-3.3-70B-Instruct-Turbo` | $0.10 / $0.32 |
| Batch, frontier MoE | Together AI | `meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8` (the id carries the suffix; without it the call 404s) | $0.27 / $0.85 |
| Batch (flat-rate alternative) | Together AI | `meta-llama/Llama-3.3-70B-Instruct-Turbo` | $1.04 flat |
| Code generation | Fireworks | 70B-class coder | $0.90 flat |
| Vision / multimodal | DeepInfra · Together AI | `Qwen3-VL-30B-A3B-Instruct` $0.15 / $0.60 · `Qwen3-VL-235B-A22B-Instruct` $0.20 / $0.88 · Llama 4 Maverick (vision-capable) $0.27 / $0.85 | — |
| Niche/custom models | Replicate | any HuggingFace model | per-second hardware billing (per-token only for its popular LLMs) — several times a dense per-token rate on an under-utilised GPU |

OpenAI-compatible base URLs: Groq `https://api.groq.com/openai/v1` · Together `https://api.together.ai/v1` · Fireworks `https://api.fireworks.ai/inference/v1` (no trailing slash; model ids are `accounts/fireworks/models/…`) · RunPod serverless vLLM `https://api.runpod.ai/v2/<endpoint-id>/openai/v1`.

### GPU Cloud Providers (inference)

| Provider | Billing | H100 $/hr | Cold start | Egress | Notes |
|---|---|---|---|---|---|
| RunPod Serverless | Per-second, per-request | $4.79 flex / $9.98 active (always-on worker) | FlashBoot: ~0.5s best case, 95% < 2.3s (warm-worker dispatch from NVMe — not a true cold start); free on every endpoint | $0 | Default for inference; pre-built vLLM worker exposes `/run` and the OpenAI-compatible route |
| Modal | Per-second | $3.95 (H100 SXM5 = $0.001097/s); CPU $0.0000131/core-s and memory $0.00000222/GiB-s billed separately; non-preemptible 3x; region 1.15-1.75x | Memory Snapshots restore in seconds (skip the weight load) | Included | Python decorator DX. B200 ≈ $6.25/hr, H200 ≈ $4.54/hr |
| RunPod Secure Pod | Per-second | $2.89-3.49 by SKU (PCIe / SXM / NVL) | N/A (always on) | $0 | SLA-backed |
| RunPod Community Pod | Per-second | ~$2.69 | N/A | $0 | Shared host kernel |

### GPU Cloud Providers (training / fine-tuning)

| Provider | Billing | H100 $/hr | Stability | Notes |
|---|---|---|---|---|
| Vast.ai | Marketplace bid | $1.30-2.50 verified hosts (spot ~50% lower) | Low-Medium | Hosts are scored on uptime/network/DLPerf — no VRAM guarantee; egress is per byte, host-set, no published range |
| TensorDock | KVM VM | $1.91 spot – $2.25 on-demand | High (vendor SLA) | Full root; snapshot support unconfirmed |
| Spheron Network | Spot/on-demand | ~$2.0-2.1 spot SXM5 / $2.5-3.4 on-demand; PCIe from $2.01 | Medium | Neo-cloud aggregator, per-minute billing, no egress |
| Thunder Compute | On-demand, per-minute | $3.20 (PCIe); A100 80GB $1.09 | Medium | $0 egress; managed availability — no longer the cheapest H100 |
| RunPod Community / Secure | Pod | ~$2.69 / $2.89-3.49 | Medium / High | As above |

### GPU Hardware

| GPU | VRAM | Mem BW | Best for | $/hr range (market) |
|---|---|---|---|---|
| B200 | 192 GB HBM3e | 8 TB/s | Frontier training, NVFP4 inference | $3.75 - $6.79 |
| H200 | 141 GB | 4.8 TB/s | 70B+ FP16 inference, long context | $2.09 - $4.44 |
| H100 SXM | 80 GB | 3.35 TB/s | Distributed training, 70B INT4 | $1.30 - $3.49 |
| RTX PRO 6000 Blackwell | 96 GB GDDR7 ECC | 1.79 TB/s | High-VRAM single-GPU inference, NVFP4 | from ~$2.26 |
| A100 80GB | 80 GB | 2 TB/s | Fine-tuning 7-70B, batch inference | $0.40 - $1.85 |
| L40S | 48 GB | 864 GB/s | FP8 inference, vision models | $0.55 - $1.47 |
| RTX 5090 | 32 GB GDDR7 | 1.8 TB/s | Prototyping, <=13B inference | $0.55 - $0.67 |
| RTX 4090 | 24 GB | ~1 TB/s | Prototyping, <=13B inference | $0.33 - $0.49 |
| L4 | 24 GB | 300 GB/s | Budget inference, video processing | $0.31 - $0.90 |
| T4 | 16 GB | 300 GB/s | Cheapest inference, demos, <=7B | $0.15 - $0.64 |

**Egress:** RunPod, TensorDock, Thunder Compute = $0. Vast.ai = per byte, host-set. Factor it into TCO for data-heavy jobs.

**Distributed training:** an RDMA fabric is mandatory for multi-node — InfiniBand is the safe default, and RoCEv2 on 400GbE+ with a lossless (PFC/ECN) configuration is a proven-at-scale alternative. Plain 1-10 Gbps Ethernet is unusable for gradient sync above ~2 nodes whatever the protocol.

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
│   ├── Low traffic → a serverless endpoint the hub provisions (rent(kind="serverless")) and pins
│   │                 via RUNPOD_SERVERLESS_ENDPOINT_ID for reuse + vLLM — scale to zero
│   └── High traffic → a dedicated pod is NOT a rent() session (rent() destroys on return; the reaper
│                     kills anything past max_lifetime_hours): provision it deliberately —
│                     keep_warm_after_use=True with a lifetime covering the serving window — which the
│                     DEFAULT caps refuse (max_cost_usd=5 ⇒ 1 h — the lifetime is an int and the estimate
│                     rounds up — and MAX_DAILY_GPU_COST=50 ⇒ 17 h of pod-h100):
│                     raise both deliberately in .env.sysadmin and the call; Modal pods cannot be kept — + vLLM
│
├── Do you need to fine-tune?
│   ├── < 70B params → provider="vast" (cheapest A100/H100; checkpoint-resume mandatory)
│   └── >= 70B or multi-day → RunPod Secure (stability)
│
├── Do you need to train from scratch?
│   ├── Single node → RunPod Pod (multi-GPU template — `fabrik gpu` rents ONE GPU per pod today)
│   └── Multi-node → Dedicated multi-GPU cluster (InfiniBand or equivalent RDMA fabric mandatory)
│
└── Local dev / prototyping?
    └── Ollama on WSL (see docs/reference/LOCAL_LLM_INFRASTRUCTURE.md)
```

---

## Integration with Fabrik — what exists, what does not

**Shipped:** `fabrik gpu` + `gpu_rent` (above); `fabrik scaffold <name> --type python-api-gpu` emits a standard `python-api` plus `src/<package>/gpu_handler.py` (`rent_for_workload(workload, work_fn)`, `DEFAULT_KIND = "pod-rtx-4090"`, per-call defaults as module constants); the reaper timer; B2 checkpoints; textfile metrics. Detail and the phase history: `docs/operations/gpu-rent.md` and the archived plan set `docs/development/plans/archived/2026-06-17-gpu-rent-and-serverless-shipped/`.

**Not shipped — do NOT write these into a spec or a ticket as if they existed:**

- `shape.needs_gpu` / `shape.gpu_kind` — the `Shape` model has NO such fields; a spec carrying either FAILS TO LOAD. The `python-api-gpu` spec is the plain `python-api` shape; the GPU kind is the `DEFAULT_KIND` constant in `gpu_handler.py` (per-call override), nothing in `specs/services/`.
- A `gpu:` spec block (today it LOADS and is silently ignored — `Spec` has no `extra="forbid"`), a GPU registrar in `resolve_applicability`, `fabrik destroy` tearing down rentals — the auto-provisioning slice.
- ⚠️ The emitted `gpu_handler.py` docstring says the kind "is read from the spec's `shape.gpu_kind` field" — it is not; `DEFAULT_KIND` is the only source (scaffold defect, mailed to fleet).
- Multi-GPU pods (`rent()` provisions one GPU), Modal serverless `App.deploy()` from a spec, persistent network volumes (use B2).

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| GPU inference on the Fabrik VPS | External GPU cloud (RunPod, Modal, Vast.ai) or managed API (Together, Groq) |
| Self-hosting when < 1B tokens/month | Managed API — zero idle cost |
| Self-hosting frontier MoE models (400B+ parameter) | Managed API — VRAM cost is prohibitive |
| TGI for new deployments | vLLM (TGI is maintenance-mode) |
| Quantizing during training/fine-tuning | FP16/BF16 only for training |
| Sync `OpenAI` client in async FastAPI | `AsyncOpenAI` with `base_url` swap |
| Hardcoded API keys, provider config, or model ids | Pydantic Settings from env vars |
| `print()` in orchestrator code | `structlog` structured logger |
| Provider API calls without timeout + retry | `httpx.AsyncClient` + `tenacity` + circuit-breaker per `58-resilience.md` |
| GPU provider not in `docs/RESILIENCE.md` §2a | Add the row before adding the call site |
| Calling a provider's create/destroy API from anywhere other than `rent()`/`rented()` or the shipped `fabrik gpu destroy` / `fabrik gpu reconcile` — a hand-rolled hub script included — or a code path in a deployed container that executes a `fabrik` import | `fabrik gpu` ON THE HUB (`rent()`/`rented()`: try/finally destroy, both cost caps, tags, audit line); the service enqueues the job or calls a pinned serverless endpoint |
| `shape.needs_gpu` / `shape.gpu_kind` in `specs/services/` (the spec FAILS TO LOAD — `Shape` is `extra="forbid"`) · ANY top-level key the spec does not define (`gpu:`, `gpu_config:`, …) — SILENTLY DROPPED, `Spec` is not `extra="forbid"`, so `fabrik apply` runs and provisions nothing | Nothing in the spec — the kind lives in `gpu_handler.py` |
| SSH + manual `pip install` on GPU instance | Templates / Cloud-Init / `rent(image_name=…)` only |
| Untagged GPU instances | `rent()` tags them; hand-provisioned resources carry the same five `FABRIK_*` env tags |
| Sync checkpointing during training | `gpu_checkpoint.checkpoint_to_b2` (background upload) or `dcp.async_save` — never `dcp.save` in the step |
| Checkpoints to local disk only | S3/R2/B2 — local disk dies with the instance |
| Zombie GPU instances running after work | `rent()`'s `finally` + the `fabrik gpu reconcile --auto-destroy` timer |
| H100 for a 7B model | L4 handles <=13B INT4, T4 <=7B |
| Single provider for all workloads | Multi-provider routing (cost + resilience) |

---

## Related Rule Packs

- `10-python.md` — orchestrator FastAPI patterns, Pydantic Settings, `uv`, structlog, async
- `30-ops.md` — orchestrator Dockerfile, compose, Traefik, resource limits, `fabrik apply` deploy
- `55-observability.md` — orchestrator structured logging, `/health`, `/metrics`, GlitchTip
- `58-resilience.md` — timeout/retry/circuit-breaker for provider API calls, `docs/RESILIENCE.md` contract, § Provider-death resilience
- `75-workers-jobs.md` — PG job queue for async/batch GPU requests, adaptive worker pool for orchestrator workers
- `self-healing.md` — row 3 (vendor 429 → pause with `Retry-After`) reconciled with the failover chain above

---

## Done When

### Orchestrator (Fabrik service on VPS)

- [ ] `python-api-gpu` scaffold: Dockerfile (`-slim-<debian_codename>`, the placeholder replaced by the value in `.windsurf/rules/versions.yaml` — verified in the EMITTED file), compose (Traefik, resource limits, `fabrik` network). GPU work reaches the hub's `rent()` as a hub-run job or a pinned serverless endpoint; no code path in the container EXECUTES a `fabrik` import — the scaffold's `gpu_handler.py` ships in the image (`COPY . .`) with a function-local import, so delete it from the image or leave it unwired.
- [ ] `/health` verifies DB + Redis + at least one inference provider reachable.
- [ ] `/metrics` exposes `inference_requests_total`, `inference_latency_seconds`, `inference_tokens_total`, `inference_cost_usd_total`.
- [ ] Structured logging via `structlog` — no `print()`. Every inference call logged with provider, model, tokens, cost.
- [ ] GlitchTip initialized before app start.
- [ ] Provider API calls wrapped with `httpx.AsyncClient` + timeout + retry + circuit-breaker.
- [ ] Every provider has a row in `docs/RESILIENCE.md` §2a.
- [ ] Provider failover chain implemented — `live_chain` at run start, primary → sibling → other provider → graceful degradation, the last rung exercised on a schedule.
- [ ] API keys AND model ids in env vars (Pydantic Settings) — never hardcoded.
- [ ] Async/batch requests flow through PG job queue per `75-workers-jobs.md`.
- [ ] Both cost caps in force — `max_cost_usd` per call, `MAX_DAILY_GPU_COST` in `.env.sysadmin` — and `GPUBudgetExceededError` handled (logged, job parked), never swallowed.

### GPU Worker (external cloud)

- [ ] Provider selected per decision framework (managed API first, GPU cloud only when justified; `fabrik gpu compare` run for the three wired providers).
- [ ] Engine selected: vLLM (default), SGLang, or TensorRT-LLM with documented justification.
- [ ] Quantization selected per decision guide — FP8 where native, AWQ on A100/L40S/RTX, never quantize training.
- [ ] VRAM budget calculated — model fits with 15-20% headroom.
- [ ] Cold start mitigated (NVMe cache, idle timeout, warm floor).
- [ ] Every rental goes through `rent()` (tags on pods, caps, audit line, `finally` destroy with the recorded-id fallback — never `rented()` until it gains the same); anything provisioned outside it carries the five `FABRIK_*` tags and is understood to have NO lifetime cap.
- [ ] The reaper timer is installed and the metrics textfile's mtime (or the series' absence) is alerted on — never the in-file age alone.
- [ ] Training/fine-tuning: async checkpointing to B2 via `gpu_checkpoint` (or `dcp.async_save`), frequency per instance type (5 min spot, 15-30 min on-demand), resume via `load_latest_checkpoint`.
- [ ] Fault tolerance: checkpoint-resumable, heartbeat every 30s, replacement spin on 3 missed.
- [ ] Disposability per 12-Factor IX:
- [ ] SIGTERM handler traps signal, stops accepting new jobs, returns in-flight job to queue (`status = 'pending'`), frees GPU (CUDA context, model unload) before exiting.
- [ ] Idempotency: deterministic job key (not random UUID/clock); paid-API idempotency check BEFORE the external call to prevent double-charge.
- [ ] Preemptible/spot: architect for hard kill — no graceful shutdown dependency; checkpoint every 5 min (training), orphan sweep reclaims inference jobs.
