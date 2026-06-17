# Phase 3.5 — Modal + Vast.ai serverless for `fabrik gpu rent --kind serverless`

**Date:** 2026-06-16
**Status:** SCOPED, ready to implement
**Predecessors:** [2026-06-16-fabrik-gpu-rent.md](2026-06-16-fabrik-gpu-rent.md) Phases 1–5 SHIPPED; provider-aware management surface SHIPPED (commit `b5b2c64`). Pod mode live-validated on all three providers (G-LIVE-1 through G-LIVE-11).
**Why Phase 3.5 and not Phase 6:** the original plan deferred this as "Phase 3" without naming it precisely; it's named here as 3.5 because Phases 3 (checkpoint), 4 (Prometheus + systemd), 5 (scaffold) all already shipped. This closes the only remaining gap: serverless on the providers that aren't RunPod.

---

## Goal

After this plan ships:

```bash
# Auto-routing already picks Modal/Vast for serverless workloads when appropriate
fabrik gpu rent --kind serverless --workload chatbot --provider auto --needs-serverless

# Explicit:
fabrik gpu rent --kind serverless --workload chatbot --provider modal --model "Qwen/Qwen3-1.7B"
fabrik gpu rent --kind serverless --workload chatbot --provider vast --model "TinyLlama-1.1B"

# Endpoint lifecycle is symmetric across all three providers:
fabrik gpu list                              # endpoints + pods unified
fabrik gpu status <session-id>               # provider-aware, works for endpoints too
fabrik gpu destroy <session-id> -y           # provider-aware destroy
fabrik gpu reconcile --provider all          # walks endpoints + workergroups too
```

**The bar:** every command listed above runs against a live RunPod / Modal / Vast account and the test cost stays under $0.50 per provider per full lifecycle.

---

## Ground truth (verified 2026-06-16)

### A. Modal serverless — the SDK pattern

**Programmatic deploy verified against `modal-1.5.0` (already in `.venv`):**

```python
>>> import modal, inspect
>>> inspect.signature(modal.App.deploy)
(self, *, name: str | None = None, environment_name: str | None = None,
 tag: str = '', client: modal.client._Client | None = None,
 strategy: str = 'rolling') -> Self
>>> inspect.signature(modal.App.lookup)
(name: str, *, client: modal.client._Client | None = None,
 environment_name: str | None = None, create_if_missing: bool = False) -> '_App'
```

The Modal CLI's `modal deploy script.py` is a thin wrapper around `app.deploy()`. We can drive this programmatically.

**Stop-app API**: `modal app stop <app-id>` (CLI). Programmatic: `_app.stop()` on the lookup result. Both are async-internally but SDK exposes sync wrappers.

**App-instance lookup**: `modal.App.lookup("fabrik-gpu-<workload>", create_if_missing=False)` returns a handle. From the handle, `app_instance.deploy(...)` redeploys; `app_instance.stop()` tears down.

**Function reference for HTTP calls**: deployed Modal Apps expose `Function.from_name("<app-name>", "<function-name>")`. The handle has `.remote()`, `.spawn()`, `.map()`, all hydrated automatically because the App is deployed.

**Web endpoints**: for a real HTTP surface (not just `.remote()` calls), the deployed App must contain a `@modal.fastapi_endpoint()` or `@modal.asgi_app()` function. The URL pattern is `https://<workspace>--<app-name>-<func-name>.modal.run`.

### B. Vast.ai serverless — the REST pattern

**Endpoints API (verified live 2026-06-16):**
- `GET /api/v0/endptjobs/` returns `{"success": true, "results": []}` — confirms reachable + 200 with auth header.
- `POST /api/v0/endptjobs/` creates endpoint, returns `endpoint_id` (the autoscale group ID).
- `POST /api/v0/autogroups/` creates workergroup against an `endpoint_id`. Returns `workergroup_id`.
- `POST run.vast.ai/route/` (different host) routes a request to a worker.

**The `autogroups` endpoint we hit returned 404 on bare GET** — it's PUT-by-id only. The list comes from `/endptjobs/<id>/workergroups/`.

**PyWorker** (`github.com/vast-ai/pyworker`): a Python web server that runs inside each worker instance. Receives client requests with `auth_data` + `payload`, forwards to a model server on `localhost`, reports metrics to the Serverless Engine. We **don't have to write a custom PyWorker** — Vast ships templates for vLLM, TGI, and ComfyUI. We fork only when a workload needs custom payload shape.

**The flow per request** (already detailed in [`docs/reference/vast-api.md` §10.7](../reference/vast-api.md)):
1. Client `POST run.vast.ai/route/` with `{"endpoint": name, "cost": N}`.
2. Engine returns either `{"url": "http://worker-ip:8000", "signature": ..., "reqnum": ...}` or `{"status": "Stopped"}`.
3. Client `POST <worker-url>/<handler>` with `{"auth_data": {...}, "payload": {...}}`.
4. PyWorker validates auth, forwards payload to model server, returns response.

### C. What's already in place

| File | Lines | Status | Notes |
|---|---|---|---|
| `src/fabrik/drivers/modal_provider.py::create_endpoint` | 25 | **stub raises NotImplementedError** | "Phase 2 ships the SHAPE; actual deployment is Phase 3" |
| `src/fabrik/drivers/modal_provider.py::destroy_endpoint` | 5 | **stub raises NotImplementedError** | Same |
| `src/fabrik/drivers/modal_provider.py::run_endpoint_sync` | 6 | **stub raises NotImplementedError** | Same |
| `src/fabrik/drivers/vast_provider.py::create_endpoint` | 6 | **stub raises NotImplementedError** | "Vast.ai has no serverless endpoint API" — wrong, the API exists; it just wasn't wired |
| `src/fabrik/drivers/vast_provider.py::destroy_endpoint` | 3 | **stub raises NotImplementedError** | Same |
| `src/fabrik/drivers/vast_provider.py::run_endpoint_sync` | 3 | **stub raises NotImplementedError** | Same |
| `src/fabrik/orchestrator/gpu_rent.py::HOURLY_USD_BY_PROVIDER["vast"]["serverless"]` | 1 | **= None** ("not supported") | Flip to a real rate after PyWorker pricing analysis |
| `src/fabrik/orchestrator/gpu_rent.py::_create_serverless_endpoint` | ~40 | **works for RunPod only** | Generalize via provider dispatch |
| `src/fabrik/orchestrator/gpu_rent.py::selection_advice` | — | excludes Vast on serverless | Update once Vast supports it |
| `src/fabrik/orchestrator/gpu_reaper.py::reap` | — | iterates `list_endpoints()` already | No change once drivers return real lists |

**Realistic budget:** ~600 LoC code + ~150 LoC tests across both providers.

### D. The PyWorker question — fork or use stock?

Vast.ai's pre-built templates (verified at `cloud.vast.ai/templates/`):

- **TGI** (`atinoda/text-generation-webui:default-nightly` + Vast PyWorker)
- **vLLM** (`vllm/vllm-openai:latest` + Vast PyWorker)
- **ComfyUI** (image gen)
- **Hello-world** (echo handler — useful for smoke tests)

**Decision: use Vast's stock templates for Phase 3.5.** Custom PyWorker is a fork-and-extend job that's only justified when a Fabrik service has non-standard payload shapes. Add to Phase 4 backlog if needed.

For Modal, the equivalent question is "do we ship a fabrik-vllm App template?" — and the answer is yes, because Modal's idiom is one Python file per App. We ship a templated `fabrik-modal-vllm.py.j2` that the driver renders into a per-workload App.

---

## Design Constraints (binding)

**C1 (carried from main plan).** Try/finally invariant: every `create_endpoint` is paired with `destroy_endpoint`. If `run_endpoint_sync` raises mid-flight, the endpoint is still destroyed unless `--keep-warm-after-use` is set. Modal serverless honors `--keep-warm-after-use` (the deployed App persists across CLI exit). Vast serverless honors it too (endpoint stays on Vast until explicit destroy).

**C2.** Cost cap: `--max-cost` and daily `MAX_DAILY_GPU_COST` apply. Per-second-billed Modal endpoint cost computed from `wall_clock_seconds × workers_active × rate`. Vast endpoint cost = sum of worker instance hours (per-worker bill, no platform fee per [`vast-api.md` §10.9](../reference/vast-api.md)).

**C3.** Tag-safety / C4 invariant: every Modal App created by Fabrik carries name `fabrik-gpu-<workload>-<session-id-short>`. Every Vast endpoint carries `--endpoint_name fabrik-gpu-<workload>-<sid>`. Reaper destroys ONLY resources matching `fabrik-gpu-` prefix. **Foreign endpoints/apps are NEVER touched.**

**C4.** Reaper symmetry: `gpu_reaper.reap_all_providers()` already iterates `list_endpoints()` per provider. Once drivers return real endpoint lists, reaper works automatically.

**C5.** Per-provider authentication boundary: Modal serverless requires `MODAL_TOKEN_ID` + `MODAL_TOKEN_SECRET` (already set). Vast serverless requires `VAST_API_KEY` (already set). No new credentials.

**C6.** Phase 3.5 is **NOT** about custom PyWorker authoring or Modal vLLM template optimization. Those are Phase 4 work. Phase 3.5 wires the **lifecycle** (create / use / destroy / list / reconcile) and proves it against stock templates.

---

## Architecture (3 deliverables across 2 drivers + orchestrator)

### Layer 1 — Modal driver serverless (`src/fabrik/drivers/modal_provider.py`, **+220 lines**)

#### `create_endpoint(template_id, name, gpu_type_ids, workers_min, workers_max, idle_timeout, flashboot, execution_timeout_ms) -> dict`

```python
def create_endpoint(self, *, template_id, name, gpu_type_ids=None,
                    workers_min=0, workers_max=3, idle_timeout=300,
                    flashboot=True, execution_timeout_ms=600_000,
                    model=None) -> dict:
    """Deploy a Modal App as a serverless endpoint.

    template_id: name of a Fabrik-shipped Modal template file
                 (e.g. "vllm-openai", "echo-handler").
    name: stable App name (used for lookup + destroy).
    model: HuggingFace model ID for the vLLM template.
    """
    # 1. Render the template file from templates/modal/<template_id>.py.j2
    #    into a tmpfile with {name, model, gpu, workers_min, workers_max,
    #    idle_timeout} substituted.
    rendered_path = _render_modal_template(template_id, name=name,
                                            model=model, gpu=gpu_type_ids[0],
                                            workers_min=workers_min,
                                            workers_max=workers_max,
                                            idle_timeout=idle_timeout)
    # 2. exec("modal", "deploy", rendered_path) — OR use the programmatic
    #    `from rendered_path import app; app.deploy(name=name)` route.
    #    Prefer the latter — avoids subprocess overhead, gets structured
    #    errors, deterministic in tests.
    spec = importlib.util.spec_from_file_location("_fabrik_app", rendered_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    app = mod.app  # the @app variable in the template
    app.deploy(name=name)

    # 3. Look up the endpoint URL — for fastapi_endpoint-shaped apps,
    #    Modal exposes a deterministic URL pattern. Capture via the
    #    function reference returned by app.deploy().
    function = modal.Function.from_name(name, "_fabrik_handler")
    endpoint_url = function.get_web_url()  # 1.5.0 has this

    return {
        "id": name,  # Modal apps are addressed by name, not numeric ID
        "_provider": "modal",
        "_app_name": name,
        "_endpoint_url": endpoint_url,
        "workersMin": workers_min,
        "workersMax": workers_max,
        "idleTimeout": idle_timeout,
        "flashboot": flashboot,
    }
```

#### `destroy_endpoint(endpoint_id) -> None`

```python
def destroy_endpoint(self, endpoint_id: str) -> None:
    app = self._modal.App.lookup(endpoint_id, create_if_missing=False)
    app.stop()  # blocks until torn down
```

#### `run_endpoint_sync(endpoint_id, payload, timeout) -> dict`

```python
def run_endpoint_sync(self, endpoint_id, payload, *, timeout=600.0) -> dict:
    # Two paths:
    # (a) HTTP via the endpoint URL — most flexible; matches RunPod's runsync
    # (b) function.remote(**payload) — faster, but requires payload to be
    #     Python-serializable args
    # We default to (a) because it works for vLLM/asgi templates.
    info = self.get_endpoint(endpoint_id)  # cached after create
    url = info["_endpoint_url"]
    resp = httpx.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()
```

#### `list_endpoints() -> list[dict]`

```python
def list_endpoints(self) -> list[dict]:
    # Modal has no global "list all my apps" API in 1.5.0.
    # We list via the dashboard's listing API: GET /v1/apps/
    # which is exposed in modal._utils.app_utils.list_apps (private but
    # stable). Fallback: read from data/gpu-rent-state.json for endpoints
    # carrying provider="modal".
    try:
        from modal._utils.app_utils import list_apps  # private but works
        apps = list_apps(client=self._modal.Client.from_env())
        return [
            {
                "id": app.name,
                "_provider": "modal",
                "_app_name": app.name,
                "env": {"FABRIK_SESSION_ID": app.name.split("-")[-1]}
                       if app.name.startswith("fabrik-gpu-") else {},
            }
            for app in apps
        ]
    except (ImportError, AttributeError):
        # Fallback: state-file-driven listing
        from fabrik.orchestrator import gpu_state
        active = gpu_state.active_sessions()
        return [
            {"id": rec["resource_id"], "env": {"FABRIK_SESSION_ID": sid}}
            for sid, rec in active.items()
            if rec.get("provider") == "modal"
                and rec.get("resource_type") == "endpoint"
        ]
```

#### Template: `templates/modal/vllm-openai.py.j2` (~80 lines, new file)

A Jinja2 template that renders to a deployable Modal App with vLLM serving. Parameters: `{name, model, gpu, workers_min, workers_max, idle_timeout}`.

The output is a real Python file that:
- Defines `app = modal.App(name="{{ name }}")`
- Decorates a vLLM-OpenAI compatible serving class with `@app.cls(gpu="{{ gpu }}", ...)` + `@modal.asgi_app()`
- Handles `/v1/chat/completions` requests (OpenAI-compatible API surface)
- Reads the `MODEL` constant injected by template render

#### Template: `templates/modal/echo-handler.py.j2` (~30 lines, new file)

Minimal smoke template — accepts JSON, echoes back. Used by G-LIVE-12 for cheap lifecycle validation (sub-cent cost per cycle).

### Layer 2 — Vast.ai driver serverless (`src/fabrik/drivers/vast_provider.py`, **+250 lines**)

#### `create_endpoint(template_id, name, gpu_type_ids, workers_min, workers_max, idle_timeout, flashboot, execution_timeout_ms) -> dict`

```python
def create_endpoint(self, *, template_id, name, gpu_type_ids=None,
                    workers_min=0, workers_max=3, idle_timeout=300,
                    flashboot=True, execution_timeout_ms=600_000,
                    model=None, target_util=0.9, cold_mult=2.5,
                    cold_workers=2, search_params=None) -> dict:
    """Two-step: create endpoint group → create workergroup attached.

    template_id: name of a Vast public template (we use "vast-ai/vllm-openai"
                 or a fabrik-published one). User can override.
    name: stable endpoint_name (used for lookup + destroy).
    search_params: hardware filter for workers, e.g. "gpu_ram>=24 num_gpus=1".
                  Defaults derived from gpu_type_ids.
    """
    # 1. Resolve template_id → template_hash via /templates/ search if needed
    if template_id and not template_id.startswith("hash:"):
        template_hash = self._resolve_template_hash(template_id)
    else:
        template_hash = template_id.removeprefix("hash:")

    # 2. POST /api/v0/endptjobs/ to create endpoint
    endpoint_body = {
        "endpoint_name": name,
        "min_load": 0.0,
        "target_util": target_util,
        "cold_mult": cold_mult,
        "cold_workers": cold_workers,
        "max_workers": workers_max,
        "max_queue_time": 30.0,
        "target_queue_time": 10.0,
        "inactivity_timeout": idle_timeout,
    }
    ep_resp = self._request("POST", "/endptjobs/", json=endpoint_body)
    endpoint_id = ep_resp["endpoint_id"]

    # 3. POST /api/v0/autogroups/ to create workergroup
    wg_body = {
        "endpoint_id": endpoint_id,
        "template_hash": template_hash,
        "test_workers": 1,  # cheap smoke; production uses 3
        "search_params": search_params or self._default_search_params(gpu_type_ids[0]),
    }
    wg_resp = self._request("POST", "/autogroups/", json=wg_body)
    workergroup_id = wg_resp["workergroup_id"]

    return {
        "id": str(endpoint_id),
        "_provider": "vast",
        "_endpoint_name": name,
        "_workergroup_id": workergroup_id,
        "workersMin": workers_min,
        "workersMax": workers_max,
        "idleTimeout": idle_timeout,
    }
```

#### `destroy_endpoint(endpoint_id) -> None`

```python
def destroy_endpoint(self, endpoint_id: str) -> None:
    # DELETE /api/v0/endptjobs/<id>/ cascades to attached workergroups
    # AND active workers per docs/reference/vast-api.md §10.10.
    self._request("DELETE", f"/endptjobs/{endpoint_id}/")
```

#### `run_endpoint_sync(endpoint_id, payload, timeout) -> dict`

```python
def run_endpoint_sync(self, endpoint_id, payload, *, timeout=600.0) -> dict:
    """Full two-phase: POST /route/ → POST worker URL with auth_data."""
    # Phase 1: get worker URL from the engine
    name = self._lookup_endpoint_name(endpoint_id)  # cached
    route = httpx.post(
        "https://run.vast.ai/route/",
        headers={"Authorization": f"Bearer {self.api_key}"},
        json={"endpoint": name, "cost": payload.get("_cost", 100)},
        timeout=30.0,
    ).json()
    if "url" not in route:
        raise VastError(f"no workers available: {route.get('status')}")

    # Phase 2: call the worker with auth_data wrap
    worker_url = route["url"]
    auth_data = {
        "signature": route["signature"],
        "cost": route["cost"],
        "endpoint": route["endpoint"],
        "reqnum": route["reqnum"],
        "url": worker_url,
    }
    body = {"auth_data": auth_data, "payload": payload}
    # vLLM endpoint typically at /generate or /v1/chat/completions
    handler_path = payload.get("_handler", "/generate")
    resp = httpx.post(f"{worker_url}{handler_path}", json=body, timeout=timeout)
    resp.raise_for_status()
    return resp.json()
```

#### `list_endpoints() -> list[dict]`

```python
def list_endpoints(self) -> list[dict]:
    data = self._request("GET", "/endptjobs/")
    results = data.get("results", []) if isinstance(data, dict) else data
    return [
        {
            "id": str(ep["endpoint_id"]),
            "_endpoint_name": ep.get("endpoint_name"),
            "_provider": "vast",
            "env": {"FABRIK_SESSION_ID": ep["endpoint_name"].split("-")[-1]}
                   if ep.get("endpoint_name", "").startswith("fabrik-gpu-") else {},
        }
        for ep in results
    ]
```

#### Helpers

- `_resolve_template_hash(template_id)`: search `/templates/` by name, return first match's hash. For Phase 3.5, accept a known set (`vllm-openai`, `tgi-default`, `comfyui`, `hello-world`).
- `_default_search_params(gpu_type_id)`: produces a sensible search filter — e.g. `"gpu_name=RTX_4090 gpu_ram>=23 num_gpus=1 disk_space>=50 reliability2>=0.98 direct_port_count>=2"`.
- `_lookup_endpoint_name(endpoint_id)`: GET `/endptjobs/<id>/` → extract `endpoint_name`. Cached in driver's state.

### Layer 3 — orchestrator dispatch (`src/fabrik/orchestrator/gpu_rent.py`, **+90 lines**)

#### `_create_serverless_endpoint` generalization

Current implementation (verified at line ~390 in gpu_rent.py) calls `client.create_endpoint(template_id=os.environ["RUNPOD_SERVERLESS_TEMPLATE_ID"], ...)`. Needs:

1. Accept per-provider template params:
   - RunPod: `template_id` (existing)
   - Modal: `template_name` (e.g. `"vllm-openai"`), `model` (HF model ID)
   - Vast: `template_id` (template hash or known name), `model`

2. Provider-aware envelope:

```python
def _create_serverless_endpoint(client, kind, workload, session_id, max_lifetime_hours,
                                provider="runpod", model=None, template=None):
    name = f"fabrik-gpu-{workload}-{session_id[-6:]}"
    if provider == "runpod":
        template_id = template or os.environ.get("RUNPOD_SERVERLESS_TEMPLATE_ID")
        if not template_id:
            raise NotImplementedError("RUNPOD_SERVERLESS_TEMPLATE_ID required")
        return client.create_endpoint(template_id=template_id, name=name, ...)
    elif provider == "modal":
        template_name = template or "vllm-openai"
        if not model:
            raise NotImplementedError("--model required for Modal serverless")
        return client.create_endpoint(template_id=template_name, name=name,
                                      model=model, gpu_type_ids=["L4"], ...)
    elif provider == "vast":
        template_name = template or "vllm-openai"
        if not model:
            raise NotImplementedError("--model required for Vast serverless")
        return client.create_endpoint(template_id=template_name, name=name,
                                      model=model, gpu_type_ids=["RTX 4090"], ...)
```

#### `selection_advice` update

Drop the `needs_serverless` exclusion of Vast. Once the driver supports it, all three providers are eligible for serverless. The routing logic stays the same (high-util → RunPod, low-util → Modal, checkpoint-tolerant → Vast).

```python
# REMOVE this line in gpu_rent.py around line ~266:
if needs_serverless:
    eligible = {name: data for name, data in eligible.items() if name != "vast"}
# REPLACE with: serverless is supported on all 3 providers in Phase 3.5+
```

#### CLI flag additions

`fabrik gpu rent --kind serverless` gains `--model` and `--template` flags:

- `--model HF_ID` — required for Modal and Vast serverless when not using a pre-built template that has the model baked in. Optional for RunPod (template already specifies).
- `--template NAME_OR_HASH` — overrides the default (`"vllm-openai"` for Modal/Vast, `RUNPOD_SERVERLESS_TEMPLATE_ID` for RunPod).

---

## Phasing

### Phase 3.5a — Modal serverless (priority 1, ~3 hours)

Modal is easier to live-test because $30 credit gives us room and Modal's serverless cost is roughly fully visible (per-second compute + per-request charges already tracked elsewhere).

1. Write `templates/modal/echo-handler.py.j2` (cheap smoke template).
2. Implement `ModalClient.create_endpoint` / `destroy_endpoint` / `run_endpoint_sync` / `list_endpoints`.
3. Orchestrator generalize `_create_serverless_endpoint` to dispatch on provider.
4. G-LIVE-12: deploy echo template, route a request, get echo back, destroy. Total spend target: <$0.05.
5. Write `templates/modal/vllm-openai.py.j2` (production-grade vLLM template).
6. G-LIVE-13: deploy vLLM (Qwen3-1.7B), run `/v1/chat/completions` request, destroy. Spend target: <$0.30.

### Phase 3.5b — Vast serverless (priority 2, ~4 hours)

Vast is trickier because the PyWorker layer introduces a per-instance protocol on top of the plain GPU rental. The first endpoint will likely surface 1–2 quirks similar to G-LIVE-5's run of bugs (status field names, request shape mismatches).

1. Implement `VastClient.create_endpoint` / `destroy_endpoint` / `run_endpoint_sync` / `list_endpoints`.
2. Implement `_resolve_template_hash` against `vastai/vllm-openai` (find the live template hash).
3. G-LIVE-14: deploy minimal hello-world template, route a request, destroy. Spend target: <$0.50 (Vast bills per minute on cheap GPUs).
4. G-LIVE-15: deploy vLLM template (smallest model — TinyLlama-1.1B fits on RTX 4090), one inference request, destroy. Spend target: <$1.

### Phase 3.5c — wrap-up (priority 3, ~1 hour)

1. Update `HOURLY_USD_BY_PROVIDER` to set Vast `serverless` rate from 0 → realistic (e.g. $0.40/hr based on RTX 4090 + 30s avg request).
2. Drop the `needs_serverless` Vast exclusion in `selection_advice`.
3. Add unit tests (10–15): create→destroy mocking, error paths, listing.
4. Update `docs/reference/modal-api.md` §21.1.2 (serverless surface).
5. Update `docs/reference/vast-api.md` §13.4 (driver-side serverless implementation).
6. Update `docs/operations/gpu-rent.md` with serverless examples for all 3.
7. CHANGELOG + commit.

---

## Validation gates

### Pre-implementation (run BEFORE writing code)

| Gate | Command | Pass criterion |
|---|---|---|
| **G-PRE-12: Modal deploy API is stable** | `python -c "import modal, inspect; print(inspect.signature(modal.App.deploy))"` | Returns the signature documented in §A. ✅ already verified. |
| **G-PRE-13: Vast serverless endpoints reachable** | `curl -H "Authorization: Bearer $VAST_API_KEY" https://console.vast.ai/api/v0/endptjobs/` | Returns `{"success": true, "results": []}` (or non-empty). ✅ already verified. |
| **G-PRE-14: Vast vLLM template hash discoverable** | `vastai search templates 'vllm'` | Returns at least one template with name containing `vllm`. |
| **G-PRE-15: Modal account has serverless quota** | `modal app list` succeeds | Lists empty array `[]` or any apps. Confirms auth works for serverless surface (not just functions). |
| **G-PRE-16: Account balances sufficient** | `vastai show user \| grep credit` + Modal dashboard | Vast: ≥ $3 (for ~5 G-LIVE cycles). Modal: ≥ $5 of the $30 credit untouched. |

### Per-deliverable gates

| Deliverable | Gate | Pass criterion |
|---|---|---|
| `templates/modal/echo-handler.py.j2` | `modal run templates/modal/echo-handler.py::main` locally | Runs without error. |
| `ModalClient.create_endpoint` | Unit test: mock `app.deploy()`, assert called with right args | Test passes. |
| `ModalClient.destroy_endpoint` | Unit test: mock `App.lookup().stop()`, assert called | Test passes. |
| `ModalClient.run_endpoint_sync` | Unit test: mock httpx, assert POST to endpoint URL with payload | Test passes. |
| `ModalClient.list_endpoints` | Unit test: mock private `list_apps`, filter by `fabrik-gpu-` prefix | Test passes. |
| `VastClient.create_endpoint` | Unit test: mock `_request` for `/endptjobs/` + `/autogroups/`, assert both called | Test passes. |
| `VastClient.destroy_endpoint` | Unit test: mock DELETE `/endptjobs/<id>/` | Test passes. |
| `VastClient.run_endpoint_sync` | Unit test: mock `/route/` + worker POST, assert auth_data wrap | Test passes. |
| `VastClient.list_endpoints` | Unit test: mock GET, assert tag extraction | Test passes. |
| Orchestrator dispatch | Unit test: assert correct driver method called per provider | Test passes. |

### Live gates (against real accounts)

| Gate | Cost target | Pass criterion |
|---|---|---|
| **G-LIVE-12: Modal echo endpoint lifecycle** | <$0.05 | `fabrik gpu rent --kind serverless --provider modal --template echo-handler --workload smoke` deploys, gets `pong` from `/echo`, destroys via `--keep-warm-after-use=False`. State file shows `destroyed: true`. |
| **G-LIVE-13: Modal vLLM endpoint lifecycle** | <$0.30 | Same as G-LIVE-12 but with `--template vllm-openai --model Qwen/Qwen3-1.7B`. Inference response includes generated text. |
| **G-LIVE-14: Vast hello-world endpoint lifecycle** | <$0.50 | Vast endpoint deployed, route returns worker URL, request echoes back, endpoint destroyed. No orphans (`vastai show endpoints` returns empty after). |
| **G-LIVE-15: Vast vLLM endpoint lifecycle** | <$1 | Same as G-LIVE-14 with vLLM template + TinyLlama-1.1B model. Inference works. |
| **G-LIVE-16: Cross-provider serverless reconcile** | $0 (read-only) | `fabrik gpu reconcile --provider all` lists serverless endpoints from all three with correct tag-safety counts. |
| **G-LIVE-17: `fabrik gpu destroy` against orphaned Modal serverless app** | <$0.05 | Manually deploy a `fabrik-gpu-test` app, then `fabrik gpu reconcile --provider modal --auto-destroy` finds + destroys it. |
| **G-LIVE-18: `--provider auto` picks Modal for low-util serverless** | <$0.05 | `fabrik gpu rent --kind serverless --workload bursty --utilization 0.2` auto-routes to Modal, runs G-LIVE-12-equivalent. |

---

## Decisions (defaulted with rationale)

| # | Decision | Default | Why |
|---|---|---|---|
| **D11** | Modal template format | **Jinja2-rendered Python file** in `templates/modal/` | Modal requires real Python files for `app.deploy()`. Rendering one per workload avoids hand-editing. |
| **D12** | Default Modal serverless GPU | **L4** (mapped from `pod-rtx-4090`) | Cheapest workable inference GPU on Modal ($0.80/hr). H100 is overkill for the test workloads. |
| **D13** | Default Vast serverless template | **`vllm-openai`** (Vast public template) | Most common inference workload. We don't ship a custom PyWorker fork in 3.5; that's Phase 4. |
| **D14** | Default Vast serverless GPU | **RTX 4090** | Cheapest, plentiful supply, fits 7B-class models with quantization. |
| **D15** | Modal app naming convention | **`fabrik-gpu-{workload}-{session_id_last6}`** | Stable enough for reaper tag-safety; unique enough to avoid collisions. |
| **D16** | Vast endpoint naming convention | Same as D15 | Symmetric with Modal. |
| **D17** | When Modal serverless `--keep-warm-after-use` is set, what survives? | **The deployed App** (Modal-side persistent). `data/gpu-rent-state.json` flips `destroyed: false`. | Modal Apps survive CLI exit (unlike Modal pods). Operator destroys via `fabrik gpu destroy <session-id>` later. |
| **D18** | When Vast serverless `--keep-warm-after-use` is set, what survives? | **The endpoint + workergroup**. Active workers may scale to 0 via `inactivity_timeout` but the endpoint persists. | Vast endpoints are inherently persistent until DELETE. |
| **D19** | How much to scope PyWorker customization | **Zero in Phase 3.5.** Use stock Vast templates. | Custom PyWorker is real engineering (Python web server, payload schema design, metrics protocol). Justified only when a Fabrik service needs it. Add to Phase 4 backlog. |
| **D20** | Should `fabrik gpu rent --kind serverless` block on first request? | **No** — return immediately after deploy, let operator's `--work-fn` make the first call. | Mirrors RunPod serverless behavior. Cold start is the workload's concern, not the lifecycle's. |

---

## What this is NOT

- **NOT** a custom PyWorker authoring framework. Phase 4 if needed.
- **NOT** vLLM optimization (LoRA loading, prefill/decode separation, etc.). Phase 4 if needed.
- **NOT** Modal memory-snapshot optimization (covered by stock template defaults).
- **NOT** Modal multi-workspace / environment management. Single workspace per operator.
- **NOT** auto-rollout / A-B testing of multiple endpoint configs. Single endpoint per `rent()` call.

---

## Realistic budget

| Item | LoC | Time |
|---|---|---|
| `modal_provider.py` serverless methods | +220 | 1.5h |
| `templates/modal/echo-handler.py.j2` | +30 | 15m |
| `templates/modal/vllm-openai.py.j2` | +80 | 30m |
| `vast_provider.py` serverless methods | +250 | 2h |
| `gpu_rent.py` dispatch generalization | +90 | 30m |
| `cli.py` `--model` / `--template` flags | +30 | 15m |
| Unit tests | +200 | 1h |
| Live gates (G-LIVE-12 through 18) | — | 1.5h (mostly waiting for cold starts) |
| Docs updates (modal-api §21.1.2, vast-api §13.4, runbook) | +150 | 1h |
| CHANGELOG + Lesson 71 (when Vast's serverless surfaces its quirks) | +50 | 15m |
| **Total** | **~1,100 LoC** | **~8.5h** |

Live spend budget: ~$2 total across all G-LIVE-12 through G-LIVE-18 (Modal ~$0.40, Vast ~$1.50, RunPod ~$0.10 for the cross-provider reconcile).

---

## Risks + mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Modal private `list_apps` API moves / breaks in 1.6.x | Medium | Fallback to state-file listing already coded. Document in driver. |
| Vast template hashes change | Medium | `_resolve_template_hash` does a live search instead of hardcoding. |
| Vast PyWorker payload shape varies per template | High | Stock templates documented at github.com/vast-ai/pyworker. We test against vLLM first (most stable). |
| Modal app.deploy hangs / fails non-deterministically | Low | Wrap in 60s timeout; on timeout, attempt `app.lookup().stop()` before re-raising. |
| Vast endpoint takes >5min to recruit first worker | High (marketplace) | `_create_serverless_endpoint` doesn't block on worker ready — returns immediately. Operator's work_fn handles the wait via `/route/` polling. |
| Cost overrun on G-LIVE-15 (vLLM live test) | Medium | Set `--max-cost 1.5` explicitly; tight `--max-lifetime 1` (1 hour ceiling). |
| Modal's `get_web_url()` method missing in 1.5.0 | Low | If missing, construct from the documented pattern: `https://<workspace>--<app-name>-<func-name>.modal.run`. |

---

## Open questions (decide before implementation)

These have defaults I'll commit to unless directed otherwise:

1. **Custom PyWorker for Fabrik?** → Default **NO** (use stock Vast templates). Add to Phase 4 backlog. (D19)
2. **Should `--kind serverless --provider modal` deploy a stable per-workload App OR a per-session ephemeral one?** → Default **per-session ephemeral** (matches RunPod's lifecycle). Each `rent()` call → unique App name; `destroy_endpoint` removes it. The deployed-and-shared pattern is Phase 4.
3. **`fabrik gpu rent` `--model` flag — required or optional for Modal/Vast?** → Default **required when `--template` is not specified**. Templates that bake in a model (rare) can omit it.
4. **Where do rendered Modal templates live?** → Default **`/tmp/fabrik-modal-<session>.py`** (ephemeral, cleaned up on `destroy_endpoint`). Long-term consideration: bake into the operator's `~/.cache/fabrik/modal-templates/` so re-deploys reuse the build cache.

---

## Post-implementation cleanup (Phase 4 backlog)

- Custom Fabrik PyWorker fork in `fabrik-lib/vast-pyworker/` for non-vLLM payload shapes.
- Modal vLLM template optimization: memory snapshots, FlashBoot-equivalent warm pools, LoRA adapters.
- `fabrik gpu deploy <script.py>` — wrapping `modal deploy` for fully-operator-authored Modal Apps.
- Vast custom autoscaler hooks (per-request perf-unit accounting).
- Multi-provider serverless A/B routing (`fabrik gpu rent --kind serverless --provider modal --shadow vast`).

---

## Sign-off

When this plan ships, the table at the end of [commit `b5b2c64`'s CHANGELOG entry](../../CHANGELOG.md) becomes:

| Surface | RunPod | Modal | Vast.ai |
| --- | --- | --- | --- |
| `fabrik gpu rent` pod mode | ✅ G-LIVE-2/3 | ✅ G-LIVE-7/8/9 | ✅ G-LIVE-5 |
| `fabrik gpu rent` serverless | ✅ G-LIVE-1 | ✅ **G-LIVE-12/13** | ✅ **G-LIVE-14/15** |
| `--provider auto` routing | ✅ | ✅ | ✅ + **serverless** |
| `fabrik gpu status / destroy` | ✅ | ✅ G-LIVE-11 + **endpoints** | ✅ + **endpoints** |
| `fabrik gpu reconcile --provider all` | ✅ G-LIVE-10 | ✅ + **endpoints** | ✅ + **endpoints** |
| Reaper tag-safety (C4) | ✅ | ✅ | ✅ + **endpoints** |

Plan finished, GPU surface complete across all three providers in both modes.
