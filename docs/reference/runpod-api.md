# RunPod REST API reference (Fabrik consumer view)

**Last verified:** 2026-06-16 (against `docs.runpod.io/llms.txt` index + per-endpoint markdown specs + `docs.runpod.io/overview`)
**Source of truth:** `https://docs.runpod.io/llms.txt` (canonical), `https://docs.runpod.io/api-reference/*` (per-endpoint specs), `https://docs.runpod.io/overview` (product surface)
**Why this exists:** the [`fabrik gpu rent`](../development/plans/archived/2026-06-17-gpu-rent-and-serverless-shipped/2026-06-16-fabrik-gpu-rent.md) implementation wraps these endpoints in [`src/fabrik/drivers/runpod.py`](../../src/fabrik/drivers/runpod.py). This doc is the "what's in" snapshot — re-verify if RunPod changes the shape and adjust the driver accordingly.

Not exhaustive of RunPod's full API — only the endpoints Fabrik calls.

---

## RunPod product surface map (which surfaces Fabrik uses, which it does NOT)

RunPod has 5 product surfaces. Fabrik's Phase 1 + 2 + 3 use only the first two.

| Surface | What | Fabrik usage | Rationale |
|---|---|---|---|
| **Pods** | Dedicated GPU/CPU instances for containerized workloads | ✅ **Used** via `--kind pod-*`. Try/finally lifecycle, `max_lifetime_hours`, full container control. | Matches Fabrik's container-first model 1:1. |
| **Serverless** | Pay-per-second auto-scaling endpoints | ✅ **Used** via `--kind serverless`. Phase 1 points at an existing endpoint; future phases may create+destroy. | Default cold-start path per `76-gpu-workers.md` line 354. |
| **Flash (Beta)** | Run Python functions on remote GPUs directly from local terminal | ❌ **Not used.** It's Modal-style decorator DX. | Beta status + same paradigm conflict as Modal (Phase 2 trigger condition). |
| **Public Endpoints** | RunPod-hosted model APIs (Stable Diffusion, Llama, etc.) — pre-deployed by RunPod | ❌ **Not used.** | Plan is about renting GPUs to run OUR code, not consuming RunPod's pre-deployed models. For consuming pre-built models we'd use Groq/Together API path (managed APIs in the rule). |
| **Instant Clusters** | Multi-node distributed GPU (Slurm/PyTorch) | ❌ **Not used.** | `76-gpu-workers.md` lines 23–28 explicitly cautions against multi-node clusters for solo-dev scope. |

## Gaps in RunPod's public docs that affect Fabrik

| Gap | Impact on Fabrik | Mitigation |
|---|---|---|
| No published rate limits | Can't proactively throttle in driver | `_request()` already retries on 5xx (which includes 429 surrogates); add explicit 429 handling in Phase 2 if we hit it |
| No published SLA | No guarantee `wait_for_running()` timeout (300s) is generous enough | We'll widen if Phase 1 G-LIVE-2 ever times out |
| No webhooks | Can't subscribe to "pod started" / "pod terminated" events | Polling via `get_pod()` is sufficient; `wait_for_running()` is the implementation |
| No idempotency keys | Re-running `create_pod()` after a network blip could create duplicates | State file's `FABRIK_SESSION_ID` env tag identifies our pods; reaper destroys duplicates |
| No region availability API | Can't pre-check whether a GPU type is available in a region | Use `gpuTypePriority="availability"` (RunPod default) — driver passes this implicitly |

---

## Auth

```
Authorization: Bearer <RUNPOD_API_KEY>
```

Generate via `https://www.console.runpod.io/user/settings` → "API Keys".

In Fabrik: stored in `/opt/fabrik/.env.sysadmin` as `RUNPOD_API_KEY=<key>`. Loaded by `RunPodClient.__init__()` via `dotenv.load_dotenv(SYSADMIN_ENV)` only when the env var isn't already set (matches `vultr.py` pattern).

---

## Control plane

**Base URL:** `https://rest.runpod.io/v1`
**Content-Type:** `application/json`
**Driver method that wraps this base:** `RunPodClient._request(method, path, ...)`

### Pods

| Method | Path | Driver method | Notes |
|---|---|---|---|
| `POST` | `/pods` | `create_pod(gpu_type_id, image_name, ...)` | Body schema below. Returns `201` with full Pod object. |
| `GET` | `/pods` | `list_pods()` | Returns list (empty `[]` if no pods). |
| `GET` | `/pods/{podId}` | `get_pod(pod_id)` | Returns Pod (200/400/404). |
| `DELETE` | `/pods/{podId}` | `destroy_pod(pod_id)` | Returns `204` with `"Pod successfully deleted."` |
| `POST` | `/pods/{podId}/stop` | (not wrapped — Phase 2+ if needed) | Stop without destroy; reduces cost. |
| `POST` | `/pods/{podId}/start` | (not wrapped) | Restart a stopped pod. |
| `POST` | `/pods/{podId}/reset` | (not wrapped) | Reset GPU. |
| `POST` | `/pods/{podId}/restart` | (not wrapped) | Reboot container. |
| `POST` | `/pods/{podId}/update` | (not wrapped) | Update config. |
| `PATCH` | `/pods/{podId}` | (not wrapped) | Patch fields. |

#### `POST /pods` request body (verified 2026-06-16)

All fields are optional unless noted. The ones we actually use are **bold**.

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | No | Max 191 chars, default: "my pod" |
| **`computeType`** | string | No | `"GPU"` or `"CPU"`. Fabrik sets `"GPU"`. Default: `"GPU"`. |
| **`cloudType`** | string | No | `"SECURE"` or `"COMMUNITY"`. Fabrik defaults to `"SECURE"` (datacenter, more stable). `"COMMUNITY"` is ~50% cheaper but shared host kernel — rule `76-gpu-workers.md` line 342 warns custom CUDA drivers may conflict. |
| **`imageName`** | string | No | Docker image tag (e.g. `runpod/pytorch:2.1.0-py3.10-cuda12.1.1`). Required for our use. |
| **`gpuTypeIds`** | array[string] | No | Priority-ordered. Fabrik passes a single ID — see `GPU_TYPE_IDS` in driver. |
| `gpuCount` | integer | No | Default: 1. Fabrik defaults to 1. |
| `gpuTypePriority` | string | No | `"availability"` or `"custom"`. Default: `"availability"`. |
| `vcpuCount` | integer | No | Default: 2. For CPU pods only. |
| `minRAMPerGPU` | integer | No | GB per GPU, default: 8. |
| `minVCPUPerGPU` | integer | No | Default: 2. |
| **`containerDiskInGb`** | integer | No | Default: 50. Fabrik default matches. |
| **`volumeInGb`** | integer | No | Persistent storage, default: 20. Fabrik default matches. |
| `volumeMountPath` | string | No | Default: `/workspace`. |
| `networkVolumeId` | string | No | Attach a persistent network volume. |
| `dataCenterIds` | array[string] | No | Restrict to specific regions. |
| `dataCenterPriority` | string | No | `"availability"` or `"custom"`. |
| `allowedCudaVersions` | array[string] | No | E.g. `["13.0", "12.9"]`. |
| `countryCodes` | array[string] | No | Restrict to specific countries (e.g. `["US"]`). |
| **`ports`** | array[string] | No | Format: `"port/protocol"`. Default: `["8888/http","22/tcp"]` (Jupyter + SSH). |
| **`env`** | object | No | Env vars injected into the container. Fabrik adds `FABRIK_PROJECT`, `FABRIK_WORKLOAD`, `FABRIK_CREATED_BY`, `FABRIK_MAX_LIFETIME_HOURS`, `FABRIK_SESSION_ID` for orphan tracking. |
| `dockerEntrypoint` | array[string] | No | Override container ENTRYPOINT. |
| `dockerStartCmd` | array[string] | No | Override container CMD. |
| **`interruptible`** | boolean | No | Spot/preemptible. Default: false. Cheaper but can be reclaimed mid-job. |
| `locked` | boolean | No | Prevent stop/reset. |
| `globalNetworking` | boolean | No | Enable global private networking. |
| `supportPublicIp` | boolean | No | Request public IP (Community Cloud only). |
| `containerRegistryAuthId` | string | No | For private registries. |
| `templateId` | string | No | Use a saved template. |
| `minDownloadMbps` / `minUploadMbps` / `minDiskBandwidthMBps` | number | No | Performance constraints. |

#### Pod object (returned by `GET /pods/{id}` and `POST /pods`)

| Field | Type | Notes |
|---|---|---|
| `id` | string | Pod ID (use in `DELETE /pods/{id}`). |
| `name` | string | |
| `image` | string | Resolved image. |
| `desiredStatus` | enum | `"RUNNING"`, `"EXITED"`, `"TERMINATED"`. Fabrik's `wait_for_running()` polls this. |
| `costPerHr` | number | Base hourly cost (USD). |
| `adjustedCostPerHr` | number | After savings plans. **Use this for cost calculations.** |
| `locked` | boolean | |
| `interruptible` | boolean | |
| `gpuCount` | integer | |
| `vcpuCount` | number | |
| `memoryInGb` | number | |
| `containerDiskInGb` | integer | |
| `volumeInGb` | integer | |
| `volumeEncrypted` | boolean | |
| `volumeMountPath` | string | |
| `publicIp` | string \| null | IPv4 if `supportPublicIp` was set. |
| `portMappings` | object \| null | Map of internal → external ports. |
| `ports` | array[string] | |
| `machineId` | string | Internal RunPod machine ID. |
| `machine` | object | GPU/CPU specs (optional, present in detailed responses). |
| `networkVolume` | object | (optional) |
| `savingsPlans` | array | |
| `templateId` | string | |
| `containerRegistryAuthId` | string | |
| `consumerUserId` | string | |
| `lastStartedAt` | string | ISO 8601. |
| `lastStatusChange` | string | ISO 8601. |

### Serverless endpoints

Scale-to-zero inference endpoints. Cold-start ~0.5–2.3s with FlashBoot.

| Method | Path | Driver method | Notes |
|---|---|---|---|
| `POST` | `/endpoints` | `create_endpoint(template_id, name, ...)` | Body schema below. Returns endpoint object. |
| `GET` | `/endpoints` | `list_endpoints()` | List all endpoints. |
| `GET` | `/endpoints/{endpointId}` | `get_endpoint(endpoint_id)` | Returns endpoint object. |
| `DELETE` | `/endpoints/{endpointId}` | `destroy_endpoint(endpoint_id)` | Removes the endpoint. |
| `PATCH` | `/endpoints/{endpointId}` | (not wrapped) | Update worker counts, etc. |
| `POST` | `/endpoints/{endpointId}/update` | (not wrapped) | Alternative update. |

#### `POST /endpoints` request body

| Field | Type | Required | Notes |
|---|---|---|---|
| **`templateId`** | string | **Yes** | The template defining the worker image/handler. Captured from console.runpod.io after the operator creates one via the HF deployment flow. |
| **`name`** | string | No | Max 191 chars. |
| **`computeType`** | string | No | `"GPU"` or `"CPU"`. Default `"GPU"`. |
| **`gpuTypeIds`** | array[string] | No | Priority-ordered. Default: RunPod picks. |
| `gpuCount` | integer | No | Workers per request, default 1, min 1. |
| `cpuFlavorIds` | array[string] | No | E.g. `"cpu3c"`, `"cpu5g"`. |
| `vcpuCount` | integer | No | Default 2. |
| `dataCenterIds` | array[string] | No | E.g. `["EU-RO-1", "US-TX-1"]`. |
| `allowedCudaVersions` | array[string] | No | E.g. `["12.4", "13.0"]`. |
| `minCudaVersion` | string | No | Min version. |
| **`workersMin`** | integer | No | Always-running workers (≥ 0). Fabrik default: **0** (true scale-to-zero). Set to ≥ 1 for latency-critical paths (you pay idle). |
| **`workersMax`** | integer | No | Max concurrent workers. Fabrik default: 3. |
| **`idleTimeout`** | integer | No | Seconds before a warm worker is released, 1–3600. Default 5. Higher = fewer cold starts under bursty load, higher idle cost. |
| **`executionTimeoutMs`** | integer | No | Per-request max wall time. Fabrik default: 600 000 (10 min). |
| `scalerType` | string | No | `"QUEUE_DELAY"` or `"REQUEST_COUNT"`. Default: `"QUEUE_DELAY"`. |
| `scalerValue` | integer | No | Threshold for spinning up another worker. Default: 4. |
| `networkVolumeId` | string | No | |
| `networkVolumeIds` | array[string] | No | |
| **`flashboot`** | boolean | No | Enable warm-worker dispatch from NVMe cache. Default: true (Fabrik). |

#### Endpoint object (returned)

```json
{
  "id": "jpnw0v75y3qoql",
  "templateId": "30zmvf89kd",
  "name": "my endpoint",
  "computeType": "GPU",
  "gpuCount": 1,
  "gpuTypeIds": ["NVIDIA H100 PCIe", "NVIDIA H100 80GB HBM3", ...],
  "dataCenterIds": ["EU-NL-1"],
  "workersMin": 0,
  "workersMax": 3,
  "idleTimeout": 5,
  "scalerType": "QUEUE_DELAY",
  "scalerValue": 4,
  "executionTimeoutMs": 600000,
  "flashboot": true,
  "networkVolumeId": "agv6w2qcg7",
  "networkVolumeIds": ["agv6w2qcg7"],
  "createdAt": "2026-06-16T16:45:20.127Z",
  "env": {"MODEL_NAME": "huggingfacetb/smollm2-135m-instruct"},
  "userId": "user_2PyTJrLzeuwfZilRZ7JhCQDuSqo",
  "version": 0
}
```

### Billing

| Method | Path | Driver method | Notes |
|---|---|---|---|
| `GET` | `/billing/pods` | `billing_pods(start, end)` | Period spend per pod. |
| `GET` | `/billing/endpoints` | `billing_endpoints(start, end)` | Period spend per endpoint. |
| `GET` | `/billing/networkvolumes` | (not wrapped) | |

Query params: `start`, `end` (ISO 8601 dates).

---

## Inference plane

**Base URL:** `https://api.runpod.ai/v2` (different subdomain from REST!)
**Driver client:** `RunPodClient._inf_client` (separate `httpx.Client` instance).

| Method | Path | Driver method | Notes |
|---|---|---|---|
| `POST` | `/{endpointId}/runsync` | `run_endpoint_sync(endpoint_id, payload, timeout)` | Blocks until worker completes (or `executionTimeoutMs` fires). Returns the worker's output. |
| `POST` | `/{endpointId}/run` | `run_endpoint_async(endpoint_id, payload)` | Returns `{id, status: "IN_QUEUE"}`. Poll `/status/{id}` to retrieve result. |
| `POST` | `/{endpointId}/cancel/{requestId}` | (not wrapped) | Cancel in-flight request. |
| `GET` | `/{endpointId}/status/{requestId}` | (not wrapped) | Poll async status. |
| `GET` | `/{endpointId}/health` | (not wrapped) | Endpoint health (workers, queue depth). |

### Request payload shape (vLLM workers)

For RunPod's vLLM template (what the SmolLM2 endpoint uses):

```json
{
  "input": {
    "prompt": "Write a short poem about artificial intelligence."
  }
}
```

Other handlers accept different `input` shapes — check the template's docs. For OpenAI-compatible serving, RunPod also exposes a `/v1/chat/completions` route per endpoint, hitting which uses the `openai` SDK with `base_url=https://api.runpod.ai/v2/{endpoint_id}/openai/v1` and `api_key=$RUNPOD_API_KEY`.

---

## Error codes (across all endpoints)

| Code | Meaning | Fabrik action |
|---|---|---|
| 200 / 201 / 204 | Success | Parse JSON or return `None` (204). |
| 400 | Bad request (validation) | Raise `RunPodError`. Our bug — don't retry. |
| 401 | Unauthorized (bad/missing key) | Raise `RunPodError`. |
| 403 | Forbidden | Raise `RunPodError`. |
| 404 | Not found | Raise `RunPodError`. |
| 429 | Rate-limited | Currently not handled specially — retried as 5xx. Worth a Phase 2 enhancement. |
| 500–504 | Server errors | Retry up to `max_retries=3` with exponential backoff (2^attempt, capped at 10s). |

---

## Known gaps in this reference (Phase 1)

- **Network volumes**: not wrapped. Fabrik uses ephemeral disk (`containerDiskInGb`, `volumeInGb`) for Phase 1. If we need persistent state across pod sessions, wrap `POST /networkvolumes`.
- **Templates**: not wrapped. Templates are created via console.runpod.io; Phase 1 captures the ID via `RUNPOD_SERVERLESS_ENDPOINT_ID` env var.
- **Pod savings plans**: not wrapped. Savings plans require commitment (1mo / 3mo) — out of scope for disposable lifecycle.
- **`/billing/networkvolumes`**: not wrapped (we don't use network volumes).

---

## How to re-verify this doc

1. Re-fetch `https://docs.runpod.io/llms.txt` and diff against the URL list cited above. New endpoints → consider adding to driver.
2. For any endpoint we wrap: re-fetch its `.md` spec, diff body schema against this doc.
3. For any 4xx/5xx error encountered in production: confirm the status-code → action mapping above.
4. **When to do this**: before any Phase 1 release, when RunPod announces an API change, or quarterly (calendar audit).

---

## Cross-references

- [`src/fabrik/drivers/runpod.py`](../../src/fabrik/drivers/runpod.py) — Fabrik's implementation of this surface (~360 lines)
- [`docs/reference/runpod-hf-models.md`](runpod-hf-models.md) — HuggingFace models available for serverless deployment
- [`docs/development/plans/2026-06-16-fabrik-gpu-rent.md`](../development/plans/archived/2026-06-17-gpu-rent-and-serverless-shipped/2026-06-16-fabrik-gpu-rent.md) — implementation plan
- [`.windsurf/rules/core/76-gpu-workers.md`](../../.windsurf/rules/core/76-gpu-workers.md) — decision framework
- `https://docs.runpod.io/llms.txt` — canonical API index (re-verify against this)
