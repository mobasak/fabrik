# Modal — full reference for Fabrik

**Last verified:** 2026-06-16 against `modal-1.5.0` SDK + [modal.com/docs/guide](https://modal.com/docs/guide).
**Why this file exists:** the Modal driver lives at [`src/fabrik/drivers/modal_provider.py`](../../src/fabrik/drivers/modal_provider.py); the orchestrator's [`selection_advice()`](../../src/fabrik/orchestrator/gpu_rent.py) routes low-utilization workloads here. This doc is the source of truth for what Modal can/can't do, what every knob means, and which Fabrik surfaces map to which Modal primitive. Re-verify the **Pricing** + **GPU types** sections quarterly.

---

## TL;DR for Fabrik

| Question | Answer |
|---|---|
| When does `fabrik gpu rent --provider modal` win? | Low-utilization (<50%) bursty inference. Per-second billing crushes RunPod's hourly when the GPU sits idle 30+ min/hr. Also: native pipelines (functions chained as a graph). |
| When does RunPod still win? | Sustained inference / training (≥50% util). RunPod's H100 Secure is $2.89/hr; Modal's H100 is $3.95/hr — break-even is roughly 73% utilization. |
| Auth | `MODAL_TOKEN_ID` + `MODAL_TOKEN_SECRET` in `/opt/fabrik/.env.sysadmin`. Operator-generated via `.venv/bin/python -m modal setup` (interactive browser). |
| Default GPU for `pod-rtx-4090` kind | Mapped to **L4** (Modal doesn't sell RTX 4090s). See `MODAL_GPU_TYPES` in [`modal_provider.py`](../../src/fabrik/drivers/modal_provider.py). |
| Pricing model | Per-second, no minimums. CPU $0.0000131/core/sec, RAM $0.00000222/GiB/sec, GPU per table below. |
| Free tier | $30/mo on Starter, $100/mo on Team. Don't burn credits on training — use for inference smoke tests. |
| What Modal does NOT do (vs RunPod) | No bring-your-own-container in the RunPod sense — you build images via the Python `Image` builder. No native "rent a pod and SSH in" — `Sandbox` is the equivalent, but it's an exec-on-container, not a long-lived shell. |

---

## 1. Mental model — Modal vs RunPod (and how the driver hides the difference)

| Concept | RunPod | Modal | How `modal_provider.py` maps it |
|---|---|---|---|
| Unit of work | Pod (container) | Function (decorated Python callable) | `create_pod()` decorates a no-op `_gpu_session_holder` function and `.spawn()`s it; the `FunctionCall.object_id` becomes the "pod_id". |
| Long-lived process | Pod with SSH | Sandbox (Modal's exec-on-container) — but Phase 2 of Fabrik's GPU surface still treats Modal "pods" as one-shot. | Driver returns synthetic `desiredStatus: RUNNING` from `get_pod`; the spawned function `time.sleep(86400)` so the container stays alive until `destroy_pod()` cancels it. |
| Container image | Docker registry image | `modal.Image` builder chain (`debian_slim().pip_install(...).run_commands(...)`) | Driver uses `modal.Image.debian_slim(python_version="3.12").env(env)` as a minimal MVP. Workload-specific images are a Phase 3 task. |
| Cold start | 10s–90s, FlashBoot reduces re-warm | Sub-4s typical with memory snapshots; 30–60s without | `selection_advice()` rewards Modal more heavily as `hours` shrinks. |
| Billing | Hourly (rounded up) on Secure pods | Per-second, no rounding | `estimate_cost()` rounds UP to whole hours for parity — over-estimates on Modal but never under. |
| Serverless | Endpoints (we pin one via `RUNPOD_SERVERLESS_ENDPOINT_ID`) | `@modal.fastapi_endpoint()` / `@modal.asgi_app()` deployed via `modal deploy` | Driver's `create_endpoint()`/`destroy_endpoint()`/`run_endpoint_sync()` are stubs that raise `NotImplementedError` — Phase 3 work because Modal serverless requires an operator-provided App definition file. |
| GPU API | REST `POST /pods` | SDK `app.function(gpu="H100").spawn()` | The "control plane" is the SDK itself; no HTTP layer to retry on 5xx (vs runpod.py's `_request()` retry loop). SDK exceptions wrap into `ModalError(cause=...)`. |

**Implication:** for the operator running `fabrik gpu rent --provider modal --kind pod-h100 -- work_fn`, the driver does the right thing for one-shot rentals. But if you want **persistent Modal infrastructure** (deployed FastAPI app, scheduled cron, daemon-style worker), you operate Modal **directly** (Python file + `modal deploy`) rather than through `fabrik gpu`. Treat `fabrik gpu rent --provider modal` as "burst compute" and `modal deploy` as "Modal as a deploy target."

---

## 2. Auth + CLI setup

### 2.1 Generate tokens
```bash
cd /opt/fabrik
.venv/bin/python -m modal setup
# → opens browser, authenticates against modal.com, writes ~/.modal.toml
```

`~/.modal.toml` format:
```toml
[default]
token_id = "ak-..."
token_secret = "as-..."
active = true
```

### 2.2 Wire into Fabrik
```bash
# Backup then append (root-owned in production):
sudo cp /opt/fabrik/.env.sysadmin \
       /opt/fabrik/backups/.env.sysadmin.before-modal.$(date +%Y%m%d-%H%M%S)

# Read values from ~/.modal.toml and append:
TOKEN_ID=$(grep -E '^token_id' ~/.modal.toml | head -1 | cut -d'"' -f2)
TOKEN_SECRET=$(grep -E '^token_secret' ~/.modal.toml | head -1 | cut -d'"' -f2)
printf "\nMODAL_TOKEN_ID=%s\nMODAL_TOKEN_SECRET=%s\n" "$TOKEN_ID" "$TOKEN_SECRET" \
  | sudo tee -a /opt/fabrik/.env.sysadmin >/dev/null
```

The driver reads from env first, then falls back to `/opt/fabrik/.env.sysadmin` via `dotenv`.

### 2.3 CLI cheat-sheet

```bash
# Account
modal token new           # rotate tokens (also writes ~/.modal.toml)
modal profile current     # which workspace is active
modal profile list

# Apps
modal app list                    # list deployed apps
modal app stop <app-id>           # stop a deployed app
modal app logs <app-id> --since 5m

# Deploy
modal deploy script.py            # ship an App + its Functions
modal run script.py::main         # run a local entrypoint
modal serve script.py             # hot-reload dev server for web endpoints

# Volumes
modal volume create my-vol
modal volume create --version=2 my-v2-vol
modal volume put my-vol ./local.txt /remote.txt
modal volume get my-vol /remote.txt ./local.txt
modal volume ls my-vol
modal volume cp my-vol /src /dst
modal volume rm my-vol /path
modal volume delete my-vol
modal volume list

# Secrets
modal secret create my-secret KEY1=val1 KEY2=val2
modal secret list
modal secret delete my-secret

# Misc
modal shell --volume my-vol --image my-image    # interactive shell
modal nfs ...                                    # legacy NetworkFileSystem (avoid)
```

---

## 3. Apps, Functions, Classes, Entrypoints

### 3.1 `modal.App` — namespace + deploy unit
An **App** groups Functions and Classes for atomic deployment. Every Function belongs to exactly one App.

```python
import modal

app = modal.App(name="my-app")          # required positional in idiomatic usage
# Other constructor args (per SDK source): image (default for all functions),
# secrets (default), volumes (default), include_source.
```

### 3.2 `@app.function()` — the unit of compute

The decorator wraps a callable into a remote-executable Function. Every parameter and what it controls:

```python
@app.function(
    image=my_image,                  # modal.Image — see §5
    gpu="H100",                      # see §6
    cpu=8.0,                         # cores; tuple (req, limit) for soft cap
    memory=32768,                    # MiB; tuple (req, limit) for hard OOM cap
    ephemeral_disk=500 * 1024,       # MiB; max 3 TiB; billed at 20:1 vs memory
    timeout=600,                     # seconds; max 86400 (24h); default 300
    startup_timeout=60,              # @modal.enter() budget; separate from runtime
    secrets=[modal.Secret.from_name("my-secret")],
    volumes={"/data": modal.Volume.from_name("my-vol")},
    schedule=modal.Period(hours=1),  # OR modal.Cron("0 8 * * 1") — see §11
    retries=modal.Retries(           # see §16
        max_retries=3,
        backoff_coefficient=2.0,
        initial_delay=1.0,
        max_delay=60.0,
    ),
    min_containers=1,                # always-warm baseline (was keep_warm)
    max_containers=20,               # upper bound
    buffer_containers=2,             # extra during active periods
    scaledown_window=300,            # seconds idle before shutdown (2–1200)
    nonpreemptible=False,            # True → 3x price, CPU-only
    region="us-east",                # see §18
    enable_memory_snapshot=True,     # see §14
    experimental_options={...},      # alpha features (e.g. enable_gpu_snapshot)
)
def my_function(arg):
    ...
```

### 3.3 `@app.cls()` — stateful container (load model once, serve many)

This is the pattern Fabrik LLM workloads should use. The class is instantiated once per container; `@modal.enter()` runs before any method handles a request.

```python
@app.cls(gpu="H100", image=vllm_image, scaledown_window=600)
class Llama:
    @modal.enter()                   # called once per container, after start
    def load(self):
        from vllm import LLM
        self.llm = LLM(model="meta-llama/Llama-3.1-8B-Instruct")

    @modal.method()
    def generate(self, prompt: str) -> str:
        return self.llm.generate(prompt)[0].outputs[0].text

    @modal.exit()                    # called on graceful shutdown / preemption
    def shutdown(self):
        del self.llm

# Invocation:
result = Llama().generate.remote("Hello")
```

#### `@modal.enter(snap=True)` — for memory snapshots
Splits init into two phases. `snap=True` runs **before** the snapshot is taken (no GPU available); `snap=False` (default) runs after restore (GPU available).
```python
@app.cls(gpu="H100", enable_memory_snapshot=True,
         experimental_options={"enable_gpu_snapshot": True})
class Model:
    @modal.enter(snap=True)
    def prep(self):
        # CPU work: download weights to /vol, parse tokenizer
        ...
    @modal.enter(snap=False)
    def warmup(self):
        # GPU work: load to CUDA, run forward pass to JIT-compile
        ...
```

### 3.4 `@app.local_entrypoint()` — your script's `main()`
Runs locally; invokes `@app.function()` via `.remote()` / `.map()` / `.spawn()`.
```python
@app.local_entrypoint()
def main(prompt: str = "Hi"):
    print(Llama().generate.remote(prompt))
```
Trigger: `modal run script.py::main --prompt "Hello"`.

### 3.5 Three ways to run an App

| Method | When | Lifetime |
|---|---|---|
| `modal run script.py::main` | Dev / one-off | Ephemeral — App exits when entrypoint returns. |
| `modal serve script.py` | Dev web endpoints | Hot-reload server; App stops on Ctrl-C. |
| `modal deploy script.py` | Production | Persistent. App stays on `modal.com/apps/<workspace>` until `modal app stop`. |

---

## 4. CLI — full table (for the runbook)

Already covered in §2.3. Pin: `modal deploy` is the prod ship; `modal run` is dev.

---

## 5. Images — building containers

Modal builds container images via a chainable Python API. Every method call is a layer with content-addressed caching.

### 5.1 Base images

| Method | Notes |
|---|---|
| `modal.Image.debian_slim(python_version="3.13")` | Default. Slim Debian + Python. Use this. |
| `modal.Image.micromamba(python_version="3.12")` | For conda/mamba ecosystems. |
| `modal.Image.from_registry("nvidia/cuda:12.4.1-runtime-ubuntu22.04")` | Pull arbitrary Docker image. Use when you need CUDA/system libs without rebuilding. |
| `modal.Image.from_dockerfile("Dockerfile")` | Build from an existing Dockerfile. |
| `modal.Image.from_aws_ecr(...)` | Private AWS ECR image (needs Secret). |
| `modal.Image.from_gcp_artifact_registry(...)` | Private GCP image (needs Secret). |

### 5.2 Chainable builders

```python
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git", "curl", "build-essential")
    .pip_install("torch==2.4.0", "transformers==4.44.0")
    .pip_install("vllm==0.6.0", gpu="H100")          # GPU available DURING build
    .pip_install_from_requirements("requirements.txt")
    .uv_pip_install("pandas==2.2.0")                  # faster than pip
    .micromamba_install("cuda-toolkit", channels=["nvidia"])
    .run_commands(
        "git clone https://github.com/x/y /opt/y",
        "cd /opt/y && make",
    )
    .env({"HF_HOME": "/cache/hf", "TRANSFORMERS_CACHE": "/cache/hf"})
    .add_local_dir("./prompts", remote_path="/prompts")
    .add_local_file("./config.yaml", remote_path="/etc/config.yaml")
    .add_local_python_source("my_module")             # local pkg → image
    .run_function(download_models,                     # run a Python fn at build
                   secrets=[modal.Secret.from_name("hf")],
                   volumes={"/cache": vol})
)
```

### 5.3 Cache semantics
- Each method call is a layer. **Breaking a layer invalidates everything after it** — same as Docker.
- Cache key = layer args + previous layers' content hash.
- Force rebuild: `force_build=True` on a layer, or `MODAL_FORCE_BUILD=1` env, or `MODAL_IGNORE_CACHE=1`.
- First build is slow; subsequent builds reuse cached layers.

### 5.4 Reference recipe — vLLM serving image
```python
vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.4.1-devel-ubuntu22.04",
                              add_python="3.12")
    .pip_install("vllm==0.6.0",
                 "transformers==4.44.0",
                 "huggingface-hub==0.24.0",
                 gpu="H100")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1",
          "VLLM_WORKER_MULTIPROC_METHOD": "spawn"})
)
```

---

## 6. GPU resources

### 6.1 Every GPU Modal sells (verified 2026-06-16, [pricing](https://modal.com/pricing))

| `gpu=` string | Per-second | Per-hour | VRAM | Use case |
|---|---|---|---|---|
| `"B200"` | $0.001736 | $6.25 | 192 GB | Cutting-edge; auto-upgrades to H300 on `B200+` |
| `"H200"` | $0.001261 | $4.54 | 141 GB | Big-context LLMs (200B params @ FP8) |
| `"H100"` | $0.001097 | $3.95 | 80 GB | Workhorse for ≥13B LLMs |
| `"H100!"` | $0.001097 | $3.95 | 80 GB | Same as H100 but **forbids** auto-upgrade to H200 |
| `"RTX-PRO-6000"` | $0.000842 | $3.03 | 48 GB | Workstation-class, cheaper H100 alternative |
| `"A100-80GB"` | $0.000694 | $2.50 | 80 GB | Older flagship; cheaper than H100 |
| `"A100"` / `"A100-40GB"` | $0.000583 | $2.10 | 40 GB | 7B–13B inference; may auto-upgrade to 80GB |
| `"L40S"` | $0.000542 | $1.95 | 48 GB | Inference + light training |
| `"A10"` | $0.000306 | $1.10 | 24 GB | Sub-7B inference, fine-tuning |
| `"L4"` | $0.000222 | $0.80 | 24 GB | Small-model inference; **Fabrik's `pod-rtx-4090` maps here** |
| `"T4"` | $0.000164 | $0.59 | 16 GB | Old but cheap; embeddings, classification |

### 6.2 GPU syntax variants
```python
@app.function(gpu="H100")              # one H100
@app.function(gpu="H100:8")            # eight H100s on one box (NVLink)
@app.function(gpu=["H100", "A100:2"])  # fallback chain — try H100 first
@app.function(gpu="A100-80GB")         # explicit 80GB
```

### 6.3 Multi-GPU limits
| GPU | Max per box |
|---|---|
| B200, H200, H100, A100, L4, T4, L40S | 8 (up to 1,536 GB VRAM) |
| A10 | 4 (96 GB VRAM) |

Requests >2 GPUs typically queue longer. Multi-node training is private Beta.

### 6.4 Pricing modifiers
| Modifier | Cost multiplier |
|---|---|
| `nonpreemptible=True` | **3×** base. Not available for GPU functions. |
| `region="us-east"` (narrow) | 1.75× base |
| `region="us"` (broad) | 1.5× base |
| Sandbox CPU/RAM | 3× function CPU/RAM (GPU same rate) |

---

## 7. CPU / Memory / Disk

### 7.1 Resources

| Param | Default | Max | Notes |
|---|---|---|---|
| `cpu=8.0` | 0.125 cores | Workspace limit (raises `InvalidError` if exceeded) | Floating-point **physical** cores. Tuple `cpu=(1.0, 4.0)` sets soft min/max. |
| `memory=32768` | 128 MiB | Workspace limit | MiB. Tuple `memory=(1024, 2048)` sets hard cap (OOM kill). |
| `ephemeral_disk=500*1024` | 512 GiB | 3 TiB (3,145,728 MiB) | Billed as **memory × 20** (so 500 GiB disk = +25 GiB memory bill). |

### 7.2 Billing rule
Charge = `max(requested, actual)` × time × rate. Soft limits help with bursty workloads.

---

## 8. Web endpoints — serverless HTTP

### 8.1 Decorator matrix

| Decorator | Use for | Framework |
|---|---|---|
| `@modal.fastapi_endpoint()` | Simple JSON endpoint (replaces deprecated `@modal.web_endpoint`) | FastAPI under the hood |
| `@modal.asgi_app()` | Full FastAPI/Starlette/FastHTML app | ASGI (async) |
| `@modal.wsgi_app()` | Django/Flask | WSGI (sync, threaded) |
| `@modal.web_server(port=8000)` | Arbitrary server (e.g. nginx, custom) | Raw port forwarding; supports WebSockets |

### 8.2 Minimal FastAPI example
```python
image = modal.Image.debian_slim().pip_install("fastapi[standard]")
app = modal.App("web-demo", image=image)

@app.function()
@modal.fastapi_endpoint(method="POST")
def predict(payload: dict) -> dict:
    return {"echo": payload}
```
Deploy: `modal deploy script.py`. URL pattern: `https://<workspace>--web-demo-predict.modal.run`.

### 8.3 Full ASGI app + auth
```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

web = FastAPI()
bearer = HTTPBearer()

@web.post("/v1/generate")
async def generate(payload: dict,
                   token: HTTPAuthorizationCredentials = Depends(bearer)):
    import os
    if token.credentials != os.environ["AUTH_TOKEN"]:
        raise HTTPException(401)
    return {"ok": True}

@app.function(secrets=[modal.Secret.from_name("auth")])
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def fastapi_app():
    return web
```

### 8.4 Proxy auth tokens
Modal's native auth: clients send `Modal-Key` + `Modal-Secret` headers. Configure per-endpoint in dashboard. Use this for service-to-service; use bearer tokens for user-facing.

### 8.5 Streaming endpoints
For SSE / chunked responses, return a generator from a FastAPI `StreamingResponse`. `@modal.concurrent` is essential — without it, every connection holds a whole container.

### 8.6 Custom domains + TLS
Dashboard → Settings → Domains → `modal domains add api.example.com`. Then on the endpoint: `@modal.fastapi_endpoint(custom_domains=["api.example.com"])`. TLS is automatic.

---

## 9. Storage — Volumes, Dicts, Queues, NetworkFileSystem

### 9.1 `modal.Volume` — primary storage primitive

```python
vol = modal.Volume.from_name("my-vol", create_if_missing=True, version=2)
# version=2 → no inode limit, better concurrent writes

@app.function(volumes={"/data": vol})
def write():
    with open("/data/x.txt", "w") as f:
        f.write("hi")
    vol.commit()   # explicit persist (background commit every few sec by default)

@app.function(volumes={"/data": vol})
def read():
    vol.reload()   # fetch latest snapshot
    return open("/data/x.txt").read()
```

#### Read/write semantics
- **Concurrent writes to different files** = OK.
- **Concurrent writes to the same file** = last-write-wins, data loss risk.
- **`vol.reload()`** errors with "volume busy" if any file is open. Always close first.
- **Bandwidth**: up to 2.5 GB/s, not guaranteed.

#### v1 vs v2
| | v1 | v2 |
|---|---|---|
| File limit | 500k inodes (50k recommended) | unlimited |
| Concurrent writers | ≤5 recommended | hundreds |
| Random access | slow | fast |
| **Use v2 for new volumes.** | | |

#### Mount options
```python
vol.with_mount_options(read_only=True)
vol.with_mount_options(sub_path="/users/123")
```

#### Storage cost
$0.09/GiB/month, first 1 TiB free.

### 9.2 `modal.NetworkFileSystem` — legacy
Pre-Volume. Use Volume for everything new. CLI: `modal nfs ...` (kept for migration).

### 9.3 `modal.Dict` + `modal.Queue` — shared state primitives
For coordination across containers. Dict = key-value, Queue = FIFO. Don't abuse — Redis is better for high-throughput.

### 9.4 `modal.CloudBucketMount` — mount S3/R2/GCS at runtime
```python
bucket = modal.CloudBucketMount("my-bucket",
                                 secret=modal.Secret.from_name("aws"))
@app.function(volumes={"/s3": bucket})
def read_from_s3(): ...
```

---

## 10. Secrets + env vars

### 10.1 Creation paths

| Path | Use |
|---|---|
| `modal secret create my-secret K1=v1 K2=v2` (CLI) | Production secrets |
| `modal.Secret.from_name("my-secret")` | Reference at decorator time |
| `modal.Secret.from_dict({"K": "v"})` | Programmatic / local-dev |
| `modal.Secret.from_dotenv()` | Load `.env` file |

### 10.2 Multi-secret merge
```python
@app.function(secrets=[
    modal.Secret.from_name("aws"),
    modal.Secret.from_name("db"),       # later ones override earlier on key clash
])
def f():
    import os
    aws_key = os.environ["AWS_ACCESS_KEY_ID"]
```

### 10.3 Auto-injected env vars
Inside a function, these are always set:
- `MODAL_TASK_ID`, `MODAL_FUNCTION_CALL_ID`, `MODAL_INPUT_ID`
- `MODAL_ENVIRONMENT` (workspace env name)

Fabrik's reaper-safety tags (`FABRIK_SESSION_ID`, `FABRIK_PROJECT`, etc.) should be passed via `secrets=` or via `image.env({...})` at build time when using Modal directly — they aren't automatic from `gpu_rent.rent()` because the driver creates an inline App, not a deployed one.

---

## 11. Scheduling

### 11.1 Two scheduler primitives

```python
@app.function(schedule=modal.Cron("0 8 * * 1"))             # 8am UTC every Mon
@app.function(schedule=modal.Cron("0 6 * * *",
                                  timezone="America/New_York"))  # 6am ET daily
@app.function(schedule=modal.Period(days=1))                # every 24h
@app.function(schedule=modal.Period(hours=5))               # every 5h
```

### 11.2 Behavior
- Deploy with `modal deploy script.py` (NOT `modal run`).
- `Cron` is stable across redeploys.
- `Period` resets the timer on redeploy — use `Cron` for production reliability.
- View history: dashboard → app → function → "Schedule" tab. Manual trigger available.
- Cannot pause — to disable, remove decorator and redeploy.

---

## 12. Scaling — map, spawn, concurrent

### 12.1 Execution methods

| Method | Returns | Blocks? | Use |
|---|---|---|---|
| `f.remote(*args)` | result | yes | Single sync call |
| `f.spawn(*args)` | `FunctionCall` handle | no | Fire-and-poll; >1M pending limit |
| `f.map(iterable)` | iterator of results | yes (lazy) | Parallel over one arg |
| `f.starmap(iterable_of_tuples)` | iterator | yes | Parallel over multi-arg |
| `f.for_each(iterable)` | None | yes | Side-effect-only parallel |
| `f.local(*args)` | result | yes | Run locally (no Modal); debug |
| `f.aio.remote(...)` | awaitable | n/a | Async variant for all of the above |

### 12.2 `.map()` parameters
```python
results = f.map(
    inputs,
    return_exceptions=True,    # don't propagate; wrap as result
    order_outputs=True,        # preserve input order (default True)
)
```

### 12.3 `FunctionCall` — handle for spawn
```python
fc = f.spawn(42)
fc.object_id                          # the ID — what our driver returns as pod_id
result = fc.get(timeout=300)          # blocks until done
fc.cancel()                           # abort
# Look up later from another script:
fc2 = modal.FunctionCall.from_id("fc-abc123")
```

### 12.4 Autoscaler knobs (set on `@app.function`)

| Param | Default | Meaning |
|---|---|---|
| `min_containers` | 0 | Always-warm baseline (replaces deprecated `keep_warm`) |
| `max_containers` | unlimited | Upper bound |
| `buffer_containers` | 0 | Extra headroom during active periods |
| `scaledown_window` | 60s | Idle time before container shuts down (2s–1200s = 20min) |

### 12.5 `@modal.concurrent` — multi-input per container

```python
@app.function()
@modal.concurrent(max_inputs=100, target_inputs=80)
def serve(req):
    ...
```
- **`max_inputs`**: hard cap per container.
- **`target_inputs`**: autoscaler's "comfort zone" — burst above this triggers more containers.
- **Sync functions** → threaded. Must be thread-safe.
- **Async functions** → asyncio. Must not block event loop.
- **For classes** → apply at class level, not method level.
- **For LLM serving** → essential. Continuous batching only works when inputs share a container.

---

## 13. Lifecycle hooks (on `@app.cls`)

| Decorator | When | Notes |
|---|---|---|
| `@modal.enter()` | Once per container, after start, before first method | Default for model loading |
| `@modal.enter(snap=True)` | Before memory snapshot taken | CPU only, no GPU. Pair with `enable_memory_snapshot=True`. |
| `@modal.enter(snap=False)` | After snapshot restore | GPU available |
| `@modal.exit()` | Container shutdown / preemption | 30s grace |
| `@modal.method()` | Method-level — replaces `@app.function` inside classes | Each method is independently callable |
| `@modal.batched(max_batch_size=N, wait_ms=M)` | Auto-batch inputs into chunks | For inference where the model handles batched tensors natively |

Example with batching:
```python
@app.cls(gpu="A10")
class Embedder:
    @modal.enter()
    def load(self):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer("BAAI/bge-small-en-v1.5")

    @modal.batched(max_batch_size=32, wait_ms=50)
    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts).tolist()
```

---

## 14. Cold start + Memory Snapshots

### 14.1 Cold-start strategies (in order of cost-effectiveness)

1. **`scaledown_window=300`** — keep container around longer. Free if it gets reused.
2. **`min_containers=1`** — always have one warm. Pay full container price 24/7.
3. **Memory snapshots** — serialize container memory after init. 3–10× speedup on init-heavy workloads.
4. **Image-baked weights** — copy models into image during build via `.run_function(download_models)`. Image pull is faster than fresh download.
5. **Concurrent file loading** — `ThreadPoolExecutor` parallel loads from disk.

### 14.2 Memory snapshots

```python
@app.cls(
    gpu="h100",
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},  # alpha
    image=image,
)
class Llm:
    @modal.enter(snap=True)
    def init(self):
        # All CPU work, then a warmup pass:
        from transformers import pipeline
        self.pipe = pipeline(model="Qwen/Qwen3-1.7B", device_map="cuda")
        self.pipe([{"role": "user", "content": "hi"}])   # JIT compile
```

#### Constraints
- CPU snapshots: GPUs unavailable during `snap=True`. Calling `torch.cuda.is_available()` can poison the snapshot.
- GPU snapshots: alpha. **Incompatible with multi-GPU**. Doesn't accelerate weight I/O — only the in-memory state.
- Don't help with bandwidth-bound model loads. Help massively with `torch.compile` / CUDA Graph capture.

---

## 15. LLM serving patterns (vLLM / SGLang)

Modal recommends **vLLM for throughput**, **SGLang for low-latency / small models**. No native TGI or TensorRT-LLM examples in current docs.

### 15.1 vLLM serving skeleton
```python
vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.4.1-devel-ubuntu22.04",
                              add_python="3.12")
    .pip_install("vllm==0.6.0", gpu="H100")
)

app = modal.App("vllm", image=vllm_image)

MODEL = "meta-llama/Llama-3.1-8B-Instruct"

@app.cls(
    gpu="H100",
    scaledown_window=600,
    min_containers=0,                              # scale to zero
    enable_memory_snapshot=True,
)
@modal.concurrent(max_inputs=64, target_inputs=48)
class VLLM:
    @modal.enter()
    def load(self):
        from vllm import AsyncLLMEngine, AsyncEngineArgs
        args = AsyncEngineArgs(model=MODEL, dtype="bfloat16",
                               gpu_memory_utilization=0.9)
        self.engine = AsyncLLMEngine.from_engine_args(args)

    @modal.method()
    async def generate(self, prompt: str) -> str:
        from vllm import SamplingParams
        params = SamplingParams(max_tokens=512, temperature=0.7)
        results = self.engine.generate(prompt, params, request_id="r1")
        async for output in results:
            final = output
        return final.outputs[0].text
```

Reference example: [modal.com/docs/examples/vllm_throughput](https://modal.com/docs/examples/vllm_throughput).

### 15.2 Bursty workload pattern
`modal.com/docs/examples/vllm_snapshot` — uses memory snapshots + scale-to-zero. Match this for Fabrik workloads where traffic is <50% util.

---

## 16. Retries + Timeouts + Preemption

### 16.1 `modal.Retries`
```python
retries = modal.Retries(
    max_retries=3,           # required
    backoff_coefficient=2.0, # 1.0 = fixed delay
    initial_delay=1.0,       # seconds before first retry
    max_delay=60.0,          # cap
)
@app.function(retries=retries)
def f(): ...

# Shorthand: retries=3 → modal.Retries(max_retries=3) with defaults
```
Default behavior without `retries=`: 1s fixed delay, retried on container crash but NOT on function-raised exceptions (caller sees the exception).

### 16.2 Timeouts
- `timeout=N` — max single-execution time. Range 1s–86400s (24h). Default 300s.
- `startup_timeout=N` — separate budget for `@modal.enter()`.
- Per-retry: each retry gets its own timeout. 3 retries × 100s = up to 400s billed.
- Exception: `modal.exception.FunctionTimeoutError` (catchable on the caller side).

### 16.3 Preemption
- **All Functions are preemptible by default.** Modal restarts on the same input.
- `nonpreemptible=True` → 3× price. **CPU only — not allowed for GPU functions.**
- Exit handlers (`@modal.exit()`) get a grace period to clean up.
- Pattern: checkpoint to Volume every N steps. On preemption + restart, `@modal.enter()` resumes from checkpoint.
- GPU Sandboxes are NOT preempted (different SLA).

---

## 17. Sandboxes — arbitrary container execution

A Sandbox is a long-lived container you can `exec` into. Use for:
- Running LLM-generated code (agent loops)
- Executing untrusted scripts
- CI-style work (clone repo, run test suite)
- Stateful sessions

### 17.1 Create + exec
```python
sb_app = modal.App.lookup("sandbox-app", create_if_missing=True)

sb = modal.Sandbox.create(
    image=modal.Image.debian_slim().pip_install("pandas"),
    gpu="A10",                                  # optional
    timeout=600,                                # default 300, max 24h
    idle_timeout=120,                           # auto-kill after inactivity
    volumes={"/data": modal.Volume.from_name("vol")},
    secrets=[modal.Secret.from_name("hf")],
    workdir="/work",
    app=sb_app,
)

p = sb.exec("python", "-c", "import pandas; print(pandas.__version__)")
p.wait()
print(p.returncode)             # 0
print(p.stdout.read())          # "2.2.0\n"

sb.terminate(wait=True)
```

### 17.2 Readiness probes
```python
sb = modal.Sandbox.create(
    "python3", "-m", "http.server", "8080",
    readiness_probe=modal.Probe.with_tcp(8080),
    app=sb_app,
)
sb.wait_until_ready()           # blocks until port accepts connections
```
Or exec probe:
```python
readiness_probe=modal.Probe.with_exec("test", "-f", "/tmp/ready", interval_ms=250)
```

### 17.3 Named (singleton) Sandboxes
```python
sb = modal.Sandbox.create(app=sb_app, name="my-singleton")
# Later, from another script:
sb2 = modal.Sandbox.from_name("sandbox-app", "my-singleton")
```

### 17.4 Pricing
**Sandbox CPU + RAM cost 3× the Function rate** (GPU rate unchanged). See §6.4.
This is why `gpu_rent.rent()` uses `@app.function` for one-shot rentals, not Sandbox.

### 17.5 Sandbox vs Function — when to pick which

| Want | Use |
|---|---|
| One-shot remote Python call | `@app.function` + `.remote()` |
| Sustained server with HTTP | `@modal.asgi_app` |
| Run a shell command | `Sandbox.exec()` |
| Agent executing LLM-generated code | `Sandbox` (isolation matters) |
| Long-lived dev environment | `Sandbox` with `idle_timeout` |

---

## 18. Regions + cloud providers

### 18.1 Region values
**Broad** (1.5× base): `us`, `eu`, `ap`, `uk`, `ca`, `me`, `sa`, `af`, `mx`
**Narrow** (1.75× base): `us-east`, `us-central`, `us-south`, `us-west`, `eu-west`, `eu-north`, `eu-south`, `ap-northeast`, `ap-southeast`, `ap-south`, `ap-melbourne`, `jp`, `au`

```python
@app.function(region="us-east")   # narrow → 1.75×
@app.function(region="us")        # broad → 1.5×
@app.function(region=["us-east", "us-west"])   # fallback list
```

### 18.2 Routing regions (separate, for web endpoints)
Only `us-east`, `us-west`, `eu-west`, `ap-south`. Match the function's region to minimize transit.

### 18.3 Cloud providers
Not directly user-selectable as of 2026-06-16. Modal multiplexes AWS / GCP / Oracle behind the region abstraction.

### 18.4 Recommendation for Fabrik
Default to **broad** regions (`us`, `eu`) unless latency-bound — improves availability and cold-start without huge price uplift. Hardcoding `us-east` for vps1-adjacent latency would cost 1.75× — usually not worth it.

---

## 19. Cross-script invocation — `Function.from_name`

To call a deployed Modal function from a different Python script (or from Fabrik service code):

```python
import modal

f = modal.Function.from_name("my-app", "my_function")
result = f.remote(42)              # sync call
fc = f.spawn(42)                   # async, get handle
results = f.map([1, 2, 3])         # parallel
```

Authentication: `~/.modal.toml` or `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` env vars. **Authenticated to your workspace only** — calls are private.

### 19.1 Polling a `FunctionCall` from another process
```python
# Producer:
fc = f.spawn(payload)
print(fc.object_id)                # store this — e.g. in DB

# Consumer (different script, later):
fc2 = modal.FunctionCall.from_id("fc-abc123")
try:
    result = fc2.get(timeout=300)
except modal.exception.FunctionTimeoutError:
    fc2.cancel()
```

This is the integration shape if Fabrik wants Modal-deployed inference behind `fabrik gpu rent --provider modal --kind serverless` — Phase 3 work.

---

## 20. Billing summary (decision-making reference)

| Resource | Rate | Notes |
|---|---|---|
| GPU H100 | $0.001097/sec = $3.95/hr | Per second, no rounding |
| GPU A100-80GB | $0.000694/sec = $2.50/hr | |
| GPU L4 (Fabrik `pod-rtx-4090`) | $0.000222/sec = $0.80/hr | |
| CPU | $0.0000131/core/sec = $0.047/core/hr | Min 0.125 cores |
| Memory | $0.00000222/GiB/sec = $0.008/GiB/hr | |
| Sandbox CPU | $0.00003942/core/sec = $0.142/core/hr | **3× Function** |
| Sandbox Memory | $0.00000672/GiB/sec = $0.024/GiB/hr | **3× Function** |
| Volume storage | $0.09/GiB/month | First 1 TiB/month free |
| Bandwidth | Free (per current docs) | |
| Free tier (Starter) | $30/mo credits | Renews monthly |
| Free tier (Team) | $100/mo credits | |
| Non-preemptible (CPU-only) | 3× base | |
| Broad region | 1.5× base | |
| Narrow region | 1.75× base | |

### 20.1 Comparison vs RunPod (Secure Cloud)

| GPU | RunPod $/hr | Modal $/hr | Break-even utilization |
|---|---|---|---|
| H100 80GB | $2.89 | $3.95 | 73% (Modal wins below this) |
| A100 80GB | $1.89 | $2.50 | 76% |
| A100 40GB | $1.49 | $2.10 | 71% |
| L40S | $0.86 | $1.95 | 44% |
| L4 / RTX-4090 | $0.69 (RunPod 4090) | $0.80 (L4) | 86% |

Below the break-even utilization rate, Modal wins on net cost because of per-second vs hourly billing. This is the math `gpu_rent.selection_advice()` encodes — see [`src/fabrik/orchestrator/gpu_rent.py`](../../src/fabrik/orchestrator/gpu_rent.py).

---

## 21. How Fabrik uses Modal

### 21.1 Driver: `src/fabrik/drivers/modal_provider.py`

**Live-validated** 2026-06-16 (G-LIVE-7 success path, G-LIVE-8 exception path, G-LIVE-9 auto-routing). Total live spend: ~$0.001.

- `ModalClient.__init__`: deferred SDK import; reads `MODAL_TOKEN_ID` + `MODAL_TOKEN_SECRET` from env / `.env.sysadmin`. Initializes `self._active_app_ctx / _active_app / _active_fc / _active_fc_id` to `None` — these hold the live `app.run()` context.
- `create_pod()` — **THIS IS THE NON-OBVIOUS BIT**: Modal requires functions to be hydrated inside an `app.run()` context. The driver:
  1. Builds a fresh `modal.App(name=fabrik-gpu-rent-<uuid>)` per rental (unique name avoids concurrent-session collision).
  2. Decorates the **module-level** `_modal_gpu_session_holder` function via `app.function(image=..., gpu=..., timeout=86400, serialized=True)(_modal_gpu_session_holder)`. The `serialized=True` is mandatory for any non-global-scope binding pattern.
  3. **Manually enters** the `app.run()` context: `app_ctx = app.run(); running_app = app_ctx.__enter__()`. The handle is stored on `self._active_app_ctx`.
  4. Spawns the holder: `fc = holder.spawn()`. Returns the FC's `object_id` as the pod ID.
  5. On any spawn failure, the context is exited to avoid leaking a running App.
- `destroy_pod(pod_id)`: cancels the FunctionCall (best-effort, ignores already-done), then exits the `app.run()` context via `self._active_app_ctx.__exit__(None, None, None)`. **The context-exit is what actually releases the GPU.** Clears the four `_active_*` handles regardless of cancel outcome.
- `wait_for_running()`: no-op (returns `{"id": pod_id, "desiredStatus": "RUNNING"}` synchronously). Modal hydrates functions on entering `app.run()` so spawn returns when ready; the container may still be cold-starting but Modal's per-second billing only charges active time.
- `get_pod(pod_id)`: tries `FunctionCall.from_id(pod_id)` and maps `fc.finalized()` to `EXITED` vs `RUNNING`. Best-effort — Modal doesn't expose a stable per-FC poll API.
- `list_pods()`: returns `[]` — Modal has no global "list my containers" API. Inventory lives in `data/gpu-rent-state.json` + tag-scoped reaper (see §21.5).
- `create_endpoint()` / `run_endpoint_sync()` / `billing_*`: stubs that raise `NotImplementedError`. Phase 3 work.

**Module-level holder** (the key piece):

```python
def _modal_gpu_session_holder() -> dict:
    """Keep a Modal GPU container alive until the FunctionCall is cancelled."""
    import time as _time
    _time.sleep(86400)
    return {"status": "sleep_timeout"}
```

Defined at module level (not inline in `create_pod`) because Modal's SDK rejects inner-scope decorations even with `serialized=True` once you also need `.spawn()` against it. The decorator is applied **dynamically** by `create_pod()`, not as a normal `@app.function` line.

### 21.1.1 What G-LIVE-7 caught (2026-06-16)

Two bugs from the pre-live driver:

1. **Inner-scope `@app.function`** raised `InvalidError: The @app.function decorator must apply to functions in global scope, unless serialized=True is set.` Fix: module-level function + dynamic decoration + `serialized=True`.
2. **`.spawn()` outside `app.run()` context** raised `ExecutionError: Function has not been hydrated with the metadata it needs to run on Modal, because the App it is defined on is not running.` Fix: enter `app.run()` context manually, store handle, exit on destroy.

The reference doc §3.5 had warned `with app.run():` was required; the pre-live driver ignored it. Lesson 70 added.

### 21.2 Orchestrator routing
`selection_advice(kind, hours, utilization_rate, needs_checkpointing, needs_serverless)` in [`src/fabrik/orchestrator/gpu_rent.py`](../../src/fabrik/orchestrator/gpu_rent.py):
- High utilization (≥50%) → recommend **RunPod**.
- Low utilization (<50%) + bursty → recommend **Modal** (per-second billing wins).
- Checkpointing tolerant + spot-OK → recommend **Vast.ai**.
- `needs_serverless=True` + Modal selected → routes to a deployed Modal App (Phase 3 work — not wired yet).

### 21.3 What the operator does directly
Modal works best when you `modal deploy` a real Python file. Use `fabrik gpu rent --provider modal` for **transient burst compute**; use `modal deploy` for **persistent infrastructure** (vLLM endpoint, scheduled cron, ETL job). Don't try to manage a deployed Modal App through `fabrik gpu` — they're different patterns.

### 21.4 Phase 3 expansion (not yet implemented)
- Real serverless endpoint creation via operator-supplied App file.
- vLLM image baked into Fabrik (`fabrik-lib/modal-vllm/` reusable module).
- Memory-snapshot enabled by default for cold-start.
- `fabrik gpu rent --provider modal --deploy <script>` → `modal deploy` wrapper with reaper hooks.

---

## 22. Common errors + troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `modal.exception.AuthError` | `~/.modal.toml` missing or token invalid | `modal token new` |
| `FunctionTimeoutError` | `timeout=` reached | Raise timeout, or chunk work + checkpoint |
| `volume busy` on `vol.reload()` | Open file handle in same container | `with open(...)` blocks; close before reload |
| Cold start >60s on first call | No `enable_memory_snapshot`, big model | Add snapshot + `@modal.enter(snap=True)` warmup |
| `InvalidError` on `cpu=` / `memory=` | Exceeded workspace ceiling | Lower request or contact Modal to raise |
| Container OOM-killed | `memory=(req, hard_cap)` exceeded | Raise hard cap or fix leak |
| `nonpreemptible` raises on GPU function | Not supported | Remove the flag; design for preemption with checkpoints |
| Region 1.75× bill surprise | `region="us-east"` instead of `"us"` | Use broad region unless latency-bound |
| Sandbox 3× CPU/RAM bill surprise | Used Sandbox where Function would do | Switch to `@app.function` for one-shot Python calls |

---

## 23. Reference links

- [Modal Guide TOC](https://modal.com/docs/guide) — full nav above in §A.
- [Pricing](https://modal.com/pricing) — re-verify GPU rates quarterly.
- [vLLM example](https://modal.com/docs/examples/vllm_throughput)
- [vLLM snapshot bursty example](https://modal.com/docs/examples/vllm_snapshot)
- [Cold-start guide](https://modal.com/docs/guide/cold-start)
- [Memory snapshots](https://modal.com/docs/guide/memory-snapshots)
- [Modal Reference (full SDK)](https://modal.com/docs/reference)
- [Modal 1.0 migration guide](https://modal.com/docs/guide/modal-1-0-migration) — if the SDK upgrades past 1.x

---

## §A — Full guide TOC (verified 2026-06-16)

For navigating when this file falls behind:

- **Custom container images**: defining-images · existing-images · named-images · fast-pull-from-registry
- **GPUs and other resources**: gpu · cuda · resources
- **Scaling out**: scale · concurrent-inputs · batch-processing · job-queue · dynamic-batching · multi-node-training
- **Deployment**: apps · managing-deployments · trigger-deployed-functions · continuous-deployment · restricted-access
- **Sandboxes**: sandboxes · sandbox-spawn · sandbox-networking · sandbox-files · sandbox-snapshots · sandbox-resources · docker-in-sandboxes · vm-sandboxes
- **Notebooks**: notebooks
- **Secrets**: secrets · environment_variables
- **Cron**: cron
- **Web Functions**: webhooks · streaming-endpoints · webhook-urls · webhook-timeouts · webhook-proxy-auth
- **Networking**: tunnels · proxy-ips · private-networking
- **Storage**: local-data · volumes · model-weights · cloud-bucket-mounts · dicts · queues · dataset-ingestion
- **Performance**: cold-start · memory-snapshots · high-performance-llm-inference
- **Reliability**: retries · preemption · timeouts · gpu-health
- **Troubleshooting**: troubleshooting
- **Security**: security · customer-supplied-encryption-keys · audit-logs
- **Integrations**: oidc-integration · datadog-integration · otel-integration · okta-sso · saml-sso · slack-notifications
- **Workspace**: workspaces · environments · modal-user-account-setup · service-users · rbac
- **Billing**: billing
- **Other**: feature-maturity · sdk-javascript-go · modal-1-0-migration · project-structure · developing-debugging · developing-with-llms · jupyter-notebooks · async · global-variables · region-selection · lifecycle-functions · parametrized-functions · dynamic-function-config · s3-gateway-endpoints · gpu-metrics
