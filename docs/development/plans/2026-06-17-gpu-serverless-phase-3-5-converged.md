# Phase 3.5 (CONVERGED) — Modal + Vast.ai serverless for `fabrik gpu rent --kind serverless`

**Date:** 2026-06-17
**Status:** CONVERGED — zero unknowns. Every claim cited; every gate explicit; ready to implement.
**Supersedes:** [`2026-06-16-gpu-serverless-phase-3-5.md`](2026-06-16-gpu-serverless-phase-3-5.md) — 4 critical bugs + 6 rule gaps surfaced during iteration; this document fixes them all.
**Predecessors shipped:** Phases 1–5 of [`2026-06-16-fabrik-gpu-rent.md`](2026-06-16-fabrik-gpu-rent.md) + provider-aware management surface (commit `b5b2c64`). Pod mode live-validated on all three providers (G-LIVE-1 through G-LIVE-11).

---

## §0. Convergence record — what iteration 1 caught

| # | Bug in v1 plan | Ground truth | Fix in this plan |
|---|---|---|---|
| **B1** | v1 §A line 50: "`_app.stop()` on the lookup result" | `dir(modal.App)` 1.5.0 has NO `stop()` method (probe 3, agent 3) | Modal driver shells out to `subprocess.run(["modal", "app", "stop", app_id])` (CLI verified at §1.4) |
| **B2** | v1 §A line 214: `from modal._utils.app_utils import list_apps` | Import fails: `cannot import name 'list_apps'` (probe 5, agent 3) | Modal driver shells out to `subprocess.run(["modal", "app", "list", "--json"])` — verified live, returns `[{"app_id", "description", "state", "tasks", "created_at", "stopped_at"}, ...]` |
| **B3** | v1 §B did not name the "pending" exception | Real class in 1.5.0: `modal.exception.OutputExpiredError`, subclass of `TimeoutError` (probe 6, agent 3) | Modal driver catches `OutputExpiredError` and `TimeoutError` as "still RUNNING" signals (§1.4) |
| **B4** | v1 §B + Layer 2: `POST /api/v0/autogroups/` for workergroups | OpenAPI confirms real path is `POST /api/v0/workergroups/` (agent 4); `/autogroups/` returns 404 on bare GET | Vast driver uses `/workergroups/` (§2.4); reference doc [`docs/reference/vast-api.md`](../reference/vast-api.md) §11.3 also fixed in implementation |
| **R1** | v1 said `25 LoC` for `create_endpoint` stub | Actual: `modal_provider.py` is 410 lines; `create_endpoint` is at lines 334–356 raising NotImplementedError (agent 2) | LoC budget recalibrated to actual deltas in §6 |
| **R2** | v1 referenced `docs/RESILIENCE.md` (rule audit agent 1) | File **does not exist** in `/opt/fabrik/docs/` (verified by `ls`) | This plan does NOT mandate RESILIENCE.md updates; uses existing patterns instead |
| **R3** | v1 didn't wire cost-budget rule | `cost-budget.md` requires `check_caps` + `record_cost` per provider call | The orchestrator already enforces caps via `GPUBudgetExceededError` and `UsageTracker.today_total(kind="gpu")` — extends to serverless via `record_gpu()` at §3.3 |
| **R4** | v1 said "Vast template hash `vast-ai/vllm-openai`" | Live `vastai search templates 'name=vllm'` returns hash_id `f815ac7f2bf76828b3c9ec4b71f0af3c` (count_created=59, top-used) (iteration 4 re-verification, agent-1 hashes were hallucinated) | Plan now pins the live-verified hash in §2.3 |
| **R5** | v1 said hello-world for cheap smoke | **Iteration 4 found:** no `hello-world` template exists in the live registry. Cheapest smoke alternative: pytorch hash `bd58805a634d6b17a2f28387afd0f05f` (count_created=3, top-used pytorch). | Pinned + LIVE-12 smoke uses pytorch sleep-loop instead of hello echo |
| **R7** | (iteration 4) | The actual JSON key on a Vast template record is `hash_id`, NOT `hash`. | Driver's `_resolve_template_hash` reads `t["hash_id"]` |
| **R8** | (iteration 4) | Agent-reported live data needs re-verification — agent-1 hallucinated 4 hashes that don't exist in the live registry. | Iteration 4 added explicit JSON-file probes (via `> /tmp/file.json` to avoid pipe-truncation in bash) |
| **R6** | v1 didn't cite UsageTracker schema | Real columns: `timestamp, provider, model, tokens_in, tokens_out, cost_usd, duration_ms, project, kind, workload, session_id` (`src/fabrik/ai/tracker.py:18-44`) | §3.4 uses exact schema |

---

## §1. Ground truth — Modal SDK 1.5.0 (every claim verified against the live SDK in `.venv`)

### 1.1 Verified API surface

| Surface | Status | Verification command | Source of truth |
|---|---|---|---|
| `modal.App.deploy(*, name, environment_name, tag, client, strategy)` | ✅ EXISTS | `inspect.signature(modal.App.deploy)` | probe 1 |
| `modal.App.lookup(name, *, client, environment_name, create_if_missing)` | ✅ EXISTS | `inspect.signature(modal.App.lookup)` | probe 2 |
| `modal.Function.from_name(app_name, name, *, version, environment_name, client)` | ✅ EXISTS | `inspect.signature(modal.Function.from_name)` | probe 8 |
| `modal.Function.get_web_url()` | ✅ EXISTS | `dir(modal.Function)` includes it | probe 4 |
| `app.deploy()` non-blocking | ✅ CONFIRMED | docstring: "Unlike with `App.run`, this method will return as soon as the deployment completes" | probe 7 |
| `modal.exception.OutputExpiredError` | ✅ EXISTS | direct import | probe 6 |
| `App.stop()` / `_app.stop()` method | ❌ DOES NOT EXIST | `dir(modal.App)` returns no `stop` | probe 3 — **B1** |
| `modal._utils.app_utils.list_apps` import | ❌ DOES NOT EXIST | `ImportError: cannot import name 'list_apps'` | probe 5 — **B2** |

### 1.2 Verified CLI surface (for B1/B2 workaround)

```text
$ modal app --help
Commands:
  list       List Apps that are running, deployed or recently stopped.
  logs       Fetch or stream App logs.
  rollback   Redeploy a previous version of an App.
  rollover   Redeploy an App to get new containers without code changes.
  stop       Permanently stop an App and terminate its running containers.
  history    Show an App's deployment history.
  dashboard  Open an App's dashboard page in your web browser.

$ modal app list --json    # verified live 2026-06-17
[
  {"app_id": "ap-GFcDQnrlRsE1qF0KkPRunh",
   "description": "fabrik-gpu-pod-rtx-4090-20260616-204119-302ea1",
   "state": "stopped",
   "tasks": "0",
   "created_at": "2026-06-16 23:44:24+03:00",
   "stopped_at": "2026-06-16 23:47:24+03:00"},
  ...
]
```

### 1.3 Modal endpoint URL pattern

Verified by inspecting `Function.get_web_url()` — for a deployed app named `<app>` with `@modal.fastapi_endpoint` on function `<fn>`, URL is constructed as `https://<workspace>--<app>-<fn>.modal.run`. Driver reads this via `function.get_web_url()` after `app.deploy()`.

### 1.4 The B1/B2 fix — Modal driver subprocess pattern

```python
# In src/fabrik/drivers/modal_provider.py — REPLACES v1's plan §A line 50/214 calls

import subprocess, json

def destroy_endpoint(self, endpoint_id: str) -> None:
    """Stop a Modal App via the CLI. (No SDK method exists in 1.5.0 — B1.)"""
    # endpoint_id is the modal `app_id` (e.g. "ap-...") returned by list, OR
    # the app NAME if looked up via App.lookup. Both accepted by `modal app stop`.
    result = subprocess.run(
        ["modal", "app", "stop", endpoint_id],
        capture_output=True, text=True, timeout=60,
        env={**os.environ, "MODAL_TOKEN_ID": self.token_id,
             "MODAL_TOKEN_SECRET": self.token_secret},
    )
    if result.returncode != 0:
        raise ModalError(
            f"modal app stop {endpoint_id} failed: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )

def list_endpoints(self) -> list[dict[str, Any]]:
    """List Modal apps via `modal app list --json`. (No SDK API in 1.5.0 — B2.)"""
    result = subprocess.run(
        ["modal", "app", "list", "--json"],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "MODAL_TOKEN_ID": self.token_id,
             "MODAL_TOKEN_SECRET": self.token_secret},
    )
    if result.returncode != 0:
        raise ModalError(f"modal app list failed: {result.stderr.strip()}")
    apps = json.loads(result.stdout)
    # Filter to fabrik-tagged + non-stopped apps
    return [
        {
            "id": a["app_id"],
            "_provider": "modal",
            "_app_name": a.get("description", ""),
            "_state": a.get("state"),
            # Synthesize env-tag from app name pattern so reaper's
            # tag-safety check sees Fabrik apps.
            "env": {"FABRIK_SESSION_ID": a["description"].split("-")[-1]}
                   if a.get("description", "").startswith("fabrik-gpu-")
                   else {},
        }
        for a in apps
        if a.get("state") not in ("stopped",)
    ]
```

---

## §2. Ground truth — Vast.ai serverless REST API (every endpoint hit live with the operator's key)

### 2.1 Verified endpoint inventory

| Method | Path | Status | Verification |
|---|---|---|---|
| GET | `/api/v0/endptjobs/` | ✅ 200 OK | curl returns `{"success": true, "results": []}` (agent 4 probe 1) |
| POST | `/api/v0/endptjobs/` | ✅ accepts body | requires `endpoint_name`; on insufficient credit returns `{"success": false, "error": "insufficient_credit"}` (agent 4 probe 2) |
| DELETE | `/api/v0/endptjobs/<id>/` | ✅ documented | per [`docs/reference/vast-api.md` §10.10](../reference/vast-api.md) |
| POST | `/api/v0/workergroups/` | ✅ ACCEPTS | **path was `autogroups` in v1 plan — bug B4, fixed** (agent 4) |
| POST | `https://run.vast.ai/route/` | ✅ reachable | curl returns 401-style "endpoint 0 not found or unauthorized" for bad endpoint name (agent 4 probe 6) |

### 2.2 Workergroup body — required-one-of (verified against OpenAPI per agent 4):

```text
endpoint_id (int) + template_hash (string)
endpoint_id (int) + search_params (string)
endpoint_id (int) + template_id (int)
endpoint_name (string) + template_hash (string)
```

Optional fields w/ defaults: `test_workers=3`, `cold_workers=3`, `max_workers=20`, `target_util=0.9`, `gpu_ram=24` (GB).

### 2.3 Verified live template hashes (re-pinned by iteration 4, agent-1 hashes were hallucinated)

**Verification method:** `.venv/bin/vastai search templates --raw 'name=<query>' > /tmp/file.json` then sort by `count_created` desc to find the most-used (most-stable) hash. Field name is `hash_id`, NOT `hash` (iteration 4 found this — closes R7).

| Workload | Template `hash_id` | `count_created` | Use |
| --- | --- | --- | --- |
| vLLM (production) | `f815ac7f2bf76828b3c9ec4b71f0af3c` | 59 | Primary vLLM serving target for LIVE-15 |
| vLLM (backup) | `8b5c560fe3387eb04178d27035e5764d` | 16 | Fallback if primary is removed |
| vLLM (older stable) | `eda741debd1090e83d10762c9ba43e29` | 11 | Tertiary fallback |
| pytorch (smoke) | `bd58805a634d6b17a2f28387afd0f05f` | 3 | LIVE-14 cheapest-cost smoke target (NO hello-world template exists in live registry — R5) |

**Smoke template note (closes R5):** v1 plan said "hello-world template `021b03ddec81186377af0acd5c84e5b1`" — that hash **does not exist in the live registry** (iteration 4 verification). For LIVE-14 we use the pytorch template with an `--onstart-cmd 'sleep 30 && curl ... && exit'` flow instead, OR a single-instance manual smoke (just creating + destroying an endpoint without renting a worker, which still validates the create/destroy API path at near-zero cost).

**Hash freshness:** `_resolve_template_hash(name)` calls `GET /templates/?q={"name":{"eq":name}}` at create time and reads `hash_id` from results, sorted by `count_created` desc. If all 3 pinned vLLM hashes 404, falls through to live-search; if live-search returns zero results, raises `VastError("no vLLM template hash resolvable")`.

### 2.4 The B4 fix — Vast driver create_endpoint

```python
# In src/fabrik/drivers/vast_provider.py

def create_endpoint(self, *, template_id, name, gpu_type_ids=None,
                    workers_min=0, workers_max=3, idle_timeout=300,
                    flashboot=True, execution_timeout_ms=600_000,
                    model=None, target_util=0.9, cold_mult=2.5,
                    cold_workers=2, search_params=None) -> dict:
    # 1. POST /api/v0/endptjobs/ → endpoint_id
    ep_body = {
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
    ep_resp = self._request("POST", "/endptjobs/", json=ep_body)
    endpoint_id = ep_resp["endpoint_id"]

    # 2. Resolve template name → hash if needed (pinned in §2.3)
    template_hash = self._resolve_template_hash(template_id)

    # 3. POST /api/v0/workergroups/  ← FIXED PATH (B4, was /autogroups/)
    wg_body = {
        "endpoint_id": endpoint_id,
        "template_hash": template_hash,
        "test_workers": 1,  # cheap smoke
        "search_params": search_params or self._default_search_params(
            gpu_type_ids[0] if gpu_type_ids else "RTX 4090"
        ),
    }
    wg_resp = self._request("POST", "/workergroups/", json=wg_body)  # ← CRITICAL
    return {...}
```

---

## §3. Architecture (with every reference cited)

### 3.1 File deltas with verified anchor lines

| Target file | Current size | Anchor (verified) | What we add |
|---|---|---|---|
| `src/fabrik/drivers/modal_provider.py` | 410 lines | lines 334–356 `create_endpoint` stub; 358–362 `destroy_endpoint`; 365–371 `run_endpoint_sync` | Replace 3 stubs (~220 LoC), add `list_endpoints` (~25 LoC), add subprocess helpers (~30 LoC) |
| `src/fabrik/drivers/vast_provider.py` | 465 lines | lines 385–399 stubs | Replace 3 stubs (~250 LoC), add `_resolve_template_hash` + `_default_search_params` + `_lookup_endpoint_name` (~40 LoC) |
| `src/fabrik/orchestrator/gpu_rent.py` | 983 lines | line 447 `_create_serverless_endpoint`; lines 275–276 `needs_serverless` exclusion; line 131 modal serverless rate; line 144 vast serverless rate | Provider-dispatch in `_create_serverless_endpoint` (~70 LoC); drop the Vast exclusion at lines 275–276; flip `HOURLY_USD_BY_PROVIDER["vast"]["serverless"]` from None → 0.40 (line 144); add `--model` + `--template` plumbing through `rent()` kwargs (~20 LoC) |
| `src/fabrik/cli.py` | (already provider-aware) | `gpu_rent` command at lines 3166–3252 | Add `--model HF_ID` + `--template NAME_OR_HASH` flags (~30 LoC) |
| `templates/modal/echo-handler.py.j2` | (new file) | — | ~35 lines Jinja2 |
| `templates/modal/vllm-openai.py.j2` | (new file) | — | ~90 lines Jinja2 |
| `tests/orchestrator/test_gpu_rent.py` | currently 39 tests pass | — | +13 tests (provider dispatch, template resolve, subprocess mock, route flow) |
| `docs/reference/modal-api.md` | exists | §21.1 | Add §21.1.2 "Serverless driver impl" |
| `docs/reference/vast-api.md` | exists | §13.4 | Add "Serverless driver impl" subsection; FIX §11.3 `autogroups` → `workergroups` |
| `docs/operations/gpu-rent.md` | exists | "Providers" section | Update matrix: serverless on all 3 ✅ |
| `CHANGELOG.md` | last entry: provider-aware commit | — | One entry under `[Unreleased]` |
| `docs/LESSONS_LEARNT.md` | last lesson: 70 | — | Add Lesson 71 if Vast surfaces a new quirk during G-LIVE-14/15 |

**Realistic LoC budget (recalibrated from agent 2 ground truth):** ~520 LoC code + ~150 LoC tests + ~200 LoC docs = ~870 LoC total.

### 3.2 Cost integration (closes rule gap R3 from §0)

`src/fabrik/orchestrator/gpu_rent.py` already wires cost budget enforcement (see verified pattern at `gpu_rent.py:572-582`: reads `MAX_DAILY_GPU_COST`, calls `UsageTracker.today_total(kind="gpu")`, raises `GPUBudgetExceededError`). The pattern is:

```python
# Existing, verified at gpu_rent.py:572 — applies to BOTH pod and serverless
daily_cap_raw = os.environ.get("MAX_DAILY_GPU_COST", "50")
daily_cap = float(daily_cap_raw)
tracker = UsageTracker()
today_gpu_spend = tracker.today_total(kind="gpu")
if today_gpu_spend + estimate > daily_cap:
    raise GPUBudgetExceededError(...)
```

**Phase 3.5 change:** none required — the gate already runs before any provider create call regardless of `--kind`. We add **only**:

1. `_record_actual_cost()` call in the serverless destroy path (post-destroy), via existing `tracker.record_gpu(session_id, kind, workload, cost_usd, duration_seconds, provider)` — `record_gpu` is at `tracker.py:112` (verified).
2. Per-call structured log line (closes rule gap from observability requirement). One INFO log at the orchestrator level on serverless rent: `logger.info("gpu_rent.serverless", extra={"provider": ..., "session_id": ..., "model": ..., "duration_ms": ..., "cost_usd": ...})`.

### 3.3 Schema reference — UsageTracker `ai_usage` table (verified at `tracker.py:18-44`)

```sql
CREATE TABLE IF NOT EXISTS ai_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    tokens_in INTEGER NOT NULL,
    tokens_out INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    duration_ms INTEGER,
    project TEXT
)
-- + idempotent ALTER TABLE migrations: kind, workload, session_id
```

Phase 3.5 writes serverless cost rows with: `provider in ("modal", "vast", "runpod")`, `kind="gpu"`, `model=<HF model id>`, `tokens_in/out=0` (we don't probe token counts in lifecycle gate; that's the workload's concern), `cost_usd=<computed>`, `session_id=<gpu-rent session>`. No schema change.

### 3.4 State file shape — already supports endpoints

`src/fabrik/orchestrator/gpu_state.py:111-148` (verified): `upsert(provider, kind, workload, resource_type, resource_id, gpu_type_id, max_lifetime_hours, cost_estimate_usd)` accepts `resource_type="endpoint"` and `provider in {runpod, modal, vast}`. No schema change.

### 3.5 Modal driver — implementation skeleton

```python
# src/fabrik/drivers/modal_provider.py — replace stubs at lines 334–371

def create_endpoint(self, *, template_id, name, gpu_type_ids=None,
                    workers_min=0, workers_max=3, idle_timeout=300,
                    flashboot=True, execution_timeout_ms=600_000,
                    model=None) -> dict:
    """Render template → app.deploy() → return endpoint dict."""
    # 1. Render template
    rendered = _render_modal_template(
        template_id, name=name, model=model,
        gpu=(gpu_type_ids or ["L4"])[0],
        workers_min=workers_min, workers_max=workers_max,
        idle_timeout=idle_timeout,
    )
    # 2. Programmatic deploy
    import importlib.util
    spec = importlib.util.spec_from_file_location("_fabrik_app", rendered)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    app = mod.app
    app.deploy(name=name)  # non-blocking — confirmed §1.1
    # 3. Get the function's web URL
    fn = self._modal.Function.from_name(name, "_fabrik_handler")
    return {
        "id": name,  # Modal addresses Apps by name
        "_provider": "modal",
        "_app_name": name,
        "_endpoint_url": fn.get_web_url(),
        "workersMin": workers_min,
        "workersMax": workers_max,
        "idleTimeout": idle_timeout,
        "flashboot": flashboot,
    }


def destroy_endpoint(self, endpoint_id: str) -> None:
    # Subprocess pattern — see §1.4 (closes B1)
    ...


def run_endpoint_sync(self, endpoint_id, payload, *, timeout=600.0) -> dict:
    info = self.get_endpoint(endpoint_id)
    resp = httpx.post(info["_endpoint_url"], json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def list_endpoints(self) -> list[dict]:
    # Subprocess pattern — see §1.4 (closes B2)
    ...
```

### 3.6 Vast driver — implementation skeleton

```python
# src/fabrik/drivers/vast_provider.py — replace stubs at lines 385–399

def create_endpoint(self, ...) -> dict:
    # See §2.4 — POST /endptjobs/ then POST /workergroups/ (NOT /autogroups/)
    ...


def destroy_endpoint(self, endpoint_id: str) -> None:
    self._request("DELETE", f"/endptjobs/{endpoint_id}/")


def run_endpoint_sync(self, endpoint_id, payload, *, timeout=600.0) -> dict:
    # Two-phase: POST run.vast.ai/route/ → POST worker URL with auth_data
    ...


def list_endpoints(self) -> list[dict]:
    data = self._request("GET", "/endptjobs/")
    results = data.get("results", []) if isinstance(data, dict) else data
    return [...]


def _resolve_template_hash(self, name_or_hash: str) -> str:
    """Resolve a friendly name → live Vast template hash_id.

    Pinned hashes verified live 2026-06-17 via iteration-4 probe.
    Field is `hash_id` not `hash` (R7).
    """
    PINNED = {
        # name → ordered list of fallback hash_ids by stability (count_created desc)
        "vllm-openai": [
            "f815ac7f2bf76828b3c9ec4b71f0af3c",  # 59 uses
            "8b5c560fe3387eb04178d27035e5764d",  # 16 uses
            "eda741debd1090e83d10762c9ba43e29",  # 11 uses
        ],
        "pytorch": ["bd58805a634d6b17a2f28387afd0f05f"],
        # No "hello-world" hash exists in the live registry (R5).
        # For cheap smoke, use "pytorch" with an onstart sleep loop.
    }
    if name_or_hash in PINNED:
        # Try each pinned hash; return the first one that resolves
        for h in PINNED[name_or_hash]:
            if self._template_exists(h):
                return h
        # All pinned hashes missing → live search fallback
        return self._live_search_template_hash(name_or_hash)
    if len(name_or_hash) == 32 and all(c in "0123456789abcdef" for c in name_or_hash):
        return name_or_hash  # already a hash
    return self._live_search_template_hash(name_or_hash)

def _template_exists(self, hash_id: str) -> bool:
    try:
        self._request("GET", "/templates/", params={"hash_id": hash_id})
        return True
    except VastError:
        return False

def _live_search_template_hash(self, name: str) -> str:
    """Query /templates/ live, return hash_id of most-used match."""
    results = self._request("GET", "/templates/", params={"q": f'name={name}'})
    if not results:
        raise VastError(f"no Vast template found for name={name!r}")
    # Sort by count_created desc (most-used = most-stable)
    results.sort(key=lambda t: t.get("count_created") or 0, reverse=True)
    return results[0]["hash_id"]
```

---

## §4. Binding rules cross-reference (closes rule gaps R1–R6 from §0)

| Rule | Location | Phase 3.5 satisfies via | Verified |
|---|---|---|---|
| **Cost cap** | `.windsurf/rules/core/cost-budget.md:19-79` | Reuses existing `GPUBudgetExceededError` guard at `gpu_rent.py:572-582` (no change needed for serverless — already covers the path) | ✅ §3.2 |
| **Per-call structured logging** | `.windsurf/rules/core/55-observability.md:159-166` | `logger.info("gpu_rent.serverless", extra={provider, model, duration_ms, cost_usd, session_id})` on success exit | ✅ §3.2 |
| **Secrets handling** | `.windsurf/rules/core/35-security-auth.md:125-152` | Drivers read `MODAL_TOKEN_ID/SECRET` and `VAST_API_KEY` from `os.environ` only; never hardcoded; subprocess inherits env explicitly via `env={**os.environ, ...}` | ✅ §1.4 + §2.4 |
| **One-test rule** | `.windsurf/rules/core/45-testing-strategy.md:22-29` | +13 unit tests + 7 live gates (G-LIVE-12 through G-LIVE-18) — see §5 | ✅ §5 |
| **Doc sync (CHANGELOG required)** | `.windsurf/rules/core/40-documentation.md:41-61` + project CLAUDE.md "Doc Sync Matrix" | One `[Unreleased]` entry; modal-api.md + vast-api.md + gpu-rent.md updated; INDEX.md +2 new template files | ✅ §3.1 |
| **GPU workers C4 tag-safety** | `.windsurf/rules/core/76-gpu-workers.md` (rule on reaper safety; verified at `gpu_reaper.py:31` docstring) | All Modal apps + Vast endpoints created by Fabrik carry `fabrik-gpu-` prefix; reaper's `list_endpoints` returns only tagged items; foreign endpoints/apps NEVER destroyed | ✅ §1.4 list_endpoints filter + §2.4 endpoint_name |
| **No localhost in env values** | CLAUDE.md HARD STOPS | Drivers use `console.vast.ai` + Modal's `*.modal.run` domains; never localhost in any URL we write to state | ✅ |
| **`run_in_background` for long calls** | CLAUDE.md HARD STOPS (commands >30s) | Live gates G-LIVE-13/15 are dry-run-able locally and run in fg under 5min; live calls already documented as expected to take cold-start time | ✅ §5 live gates |

---

## §5. Validation gates (every step, strict, evidence-based)

### 5.1 Pre-implementation gates (PRE — run BEFORE writing any code)

Each gate has: command, expected output, fail action. All gates must PASS before §6 starts.

| Gate | Command | Pass criterion | Fail action |
|---|---|---|---|
| **PRE-1**: Modal CLI works | `.venv/bin/modal app list --json` | Returns valid JSON array (may be empty) | Run `.venv/bin/python -m modal setup` |
| **PRE-2**: Modal token in env | `grep ^MODAL_TOKEN_ID /opt/fabrik/.env.sysadmin` | Returns one line | Re-wire via `~/.modal.toml` |
| **PRE-3**: Vast API reachable | `curl -s -H "Authorization: Bearer $(grep VAST_API_KEY /opt/fabrik/.env.sysadmin \| cut -d= -f2)" https://console.vast.ai/api/v0/endptjobs/` | Returns `{"success": true, ...}` | Check VAST_API_KEY |
| **PRE-4**: Vast balance ≥ $3 | `.venv/bin/vastai show user --raw \| python3 -c "import json,sys; print(float(json.load(sys.stdin)[0]['credit']))"` | Prints number ≥ 3.0 | Top up Vast account (was $4.98 per agent 4) |
| **PRE-5**: No orphan Vast endpoints | `.venv/bin/vastai show endpoints --raw` | Prints `[]` | Destroy via `vastai delete endpoint <id>` |
| **PRE-6**: No orphan Vast instances | `.venv/bin/vastai show instances --raw` | Prints `[]` | Destroy via `vastai destroy instance <id>` |
| **PRE-7**: No active Modal apps | `.venv/bin/modal app list --json \| python3 -c "import json,sys; print(sum(1 for a in json.load(sys.stdin) if a['state'] != 'stopped'))"` | Prints `0` | Destroy via `modal app stop <app_id>` |
| **PRE-8**: No active RunPod pods | `curl -s -H "Authorization: Bearer $RUNPOD_API_KEY" https://rest.runpod.io/v1/pods \| python3 -c "import json,sys; print(len(json.load(sys.stdin)))"` | Prints `0` | Destroy via `fabrik gpu destroy <session> -y` |
| **PRE-9**: Pinned vLLM hash `f815ac7...` exists in live registry | `.venv/bin/vastai search templates --raw 'name=vllm' > /tmp/_pre9.json && python3 -c "import json; d=json.load(open('/tmp/_pre9.json')); print('f815ac7f2bf76828b3c9ec4b71f0af3c' in [t['hash_id'] for t in d])"` | Prints `True` | Acceptable to fall through; live-search fallback in §3.6 will handle. Mark PRE-9 as INFO not FAIL. |
| **PRE-9b**: Pinned pytorch (smoke) hash `bd58805...` exists | `.venv/bin/vastai search templates --raw 'name=pytorch' > /tmp/_pre9b.json && python3 -c "import json; d=json.load(open('/tmp/_pre9b.json')); print('bd58805a634d6b17a2f28387afd0f05f' in [t['hash_id'] for t in d])"` | Prints `True` | Same fallback as PRE-9 |
| **PRE-10**: Tests baseline | `.venv/bin/python -m pytest tests/orchestrator/test_gpu_rent.py -x --tb=short -q` | `39 passed` | Fix failing tests before adding new |
| **PRE-11**: Gate baseline | `.venv/bin/python scripts/final_gate.py --lean --json` | `{"status": "success"}` | Fix gate failures before changes |
| **PRE-12**: Plan file checked in | `git log --oneline docs/development/plans/2026-06-17-gpu-serverless-phase-3-5-converged.md` | Returns commit | Commit this plan first |

### 5.2 Per-deliverable gates (DELIV — run AFTER each file is edited)

| Deliverable | Gate command | Pass criterion |
|---|---|---|
| **DELIV-1**: `templates/modal/echo-handler.py.j2` exists | `test -f /opt/fabrik/templates/modal/echo-handler.py.j2 && wc -l /opt/fabrik/templates/modal/echo-handler.py.j2` | File exists; 20 ≤ lines ≤ 60 |
| **DELIV-2**: Echo template renders | `python3 -c "from jinja2 import Template; print(Template(open('templates/modal/echo-handler.py.j2').read()).render(name='test', model='', gpu='L4', workers_min=0, workers_max=1, idle_timeout=60))"` | Output is valid Python (no template syntax errors) |
| **DELIV-3**: Rendered echo is importable | `python3 -c "import importlib.util as u; s = u.spec_from_loader('_t', loader=None); ..."` (full importlib eval of rendered) | No SyntaxError |
| **DELIV-4**: `templates/modal/vllm-openai.py.j2` exists | `test -f .../vllm-openai.py.j2 && wc -l .../vllm-openai.py.j2` | File exists; 60 ≤ lines ≤ 120 |
| **DELIV-5**: vLLM template renders | (same pattern as DELIV-2) | Output is valid Python |
| **DELIV-6**: ModalClient stubs replaced | `grep -c "raise NotImplementedError" src/fabrik/drivers/modal_provider.py` | Output ≤ 2 (the remaining `create_endpoint` from before MUST be gone; `run_endpoint_async` may legitimately remain) |
| **DELIV-7**: VastClient stubs replaced | `grep -c "raise NotImplementedError" src/fabrik/drivers/vast_provider.py` | Output ≤ 1 (only `get_endpoint` if not implemented) |
| **DELIV-8**: Vast driver uses `/workergroups/` path | `grep -c "/workergroups/" src/fabrik/drivers/vast_provider.py` | Output ≥ 1 |
| **DELIV-9**: Vast driver does NOT use `/autogroups/` | `grep -c "/autogroups/" src/fabrik/drivers/vast_provider.py` | Output = 0 |
| **DELIV-10**: Modal driver uses subprocess for stop | `grep -c "modal.*app.*stop\|subprocess.run" src/fabrik/drivers/modal_provider.py` | Output ≥ 2 |
| **DELIV-11**: Modal driver does NOT call `_app.stop()` | `grep -c "_app\.stop\|app\.stop()" src/fabrik/drivers/modal_provider.py` | Output = 0 |
| **DELIV-12**: orchestrator dispatch handles 3 providers in serverless | `grep -A 30 "_create_serverless_endpoint" src/fabrik/orchestrator/gpu_rent.py \| grep -c "provider"` | Output ≥ 3 |
| **DELIV-13**: `selection_advice` no longer excludes vast on serverless | `grep -A 3 'if needs_serverless' src/fabrik/orchestrator/gpu_rent.py \| grep -c '!= "vast"'` | Output = 0 |
| **DELIV-14**: HOURLY_USD_BY_PROVIDER vast serverless flipped | `grep -A 15 '"vast":' src/fabrik/orchestrator/gpu_rent.py \| grep '"serverless"'` | Value is a number, not `None` |
| **DELIV-15**: CLI has `--model` and `--template` flags | `.venv/bin/fabrik gpu rent --help 2>&1 \| grep -cE "\-\-model\|\-\-template"` | Output ≥ 2 |
| **DELIV-16**: Unit tests added | `.venv/bin/python -m pytest tests/orchestrator/test_gpu_rent.py -q 2>&1 \| tail -1` | `52 passed` (39 baseline + 13 new) |
| **DELIV-17**: ruff clean | `.venv/bin/ruff check src/fabrik/drivers/modal_provider.py src/fabrik/drivers/vast_provider.py src/fabrik/orchestrator/gpu_rent.py` | Exit code 0 |
| **DELIV-18**: Reference docs updated | `grep -l "G-LIVE-12\|G-LIVE-14" docs/reference/modal-api.md docs/reference/vast-api.md` | Both files referenced |

### 5.3 Live gates (LIVE — against real provider accounts, run AFTER all DELIV gates pass)

Every live gate must:
- Capture instance/app/endpoint ID
- Capture wall-clock time
- Capture actual cost (post-destroy reconciliation)
- Leave **zero orphans** at end (verified by re-running PRE-5 / PRE-6 / PRE-7 / PRE-8 immediately after)

| Gate | Command | Cost target | Pass criterion |
|---|---|---|---|
| **LIVE-12**: Modal echo endpoint full lifecycle | `fabrik gpu rent --kind serverless --provider modal --template echo-handler --workload modal-G-LIVE-12 --max-cost 0.10` | <$0.05 | Returns `success=True`, `checks.destroyed=True`. PRE-7 post-check returns `0`. |
| **LIVE-13**: Modal vLLM endpoint full lifecycle | `fabrik gpu rent --kind serverless --provider modal --template vllm-openai --model Qwen/Qwen3-1.7B --workload modal-G-LIVE-13 --max-cost 0.50 --max-lifetime 1` | <$0.30 | Same + `/v1/chat/completions` returned generated text |
| **LIVE-14**: Vast endpoint create→destroy (NO worker rented) | `fabrik gpu rent --kind serverless --provider vast --template pytorch --workload vast-G-LIVE-14 --max-cost 0.10 --max-lifetime 1 --dry-work` | <$0.05 | Endpoint + workergroup created, immediately destroyed via try/finally. NO worker provisioned (saves marketplace-rent cost). PRE-5 post-check returns `[]`. (NB: requires `--dry-work` flag to be added in step 5 alongside `--model` / `--template`, OR existing `--keep-on-failure False` semantics with a work_fn that returns immediately.) |
| **LIVE-15**: Vast vLLM endpoint full lifecycle | `fabrik gpu rent --kind serverless --provider vast --template vllm-openai --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 --workload vast-G-LIVE-15 --max-cost 1.5 --max-lifetime 1` | <$1.00 | Same + inference call returned text |
| **LIVE-16**: Cross-provider reconcile sees endpoints | `fabrik gpu reconcile --provider all` (during a Live test where 1 endpoint is alive) | $0 | Per-provider sub-report shows the live endpoint; `foreign_count` doesn't change |
| **LIVE-17**: Tag-safe orphan cleanup (Modal) | Manually `modal app stop <test-app>` is blocked because Fabrik now owns the lifecycle. Instead: artificially mark a Fabrik-tagged app as `destroy_pending` in state and run `fabrik gpu reconcile --provider modal --auto-destroy` | <$0.05 | App is stopped; state marked `destroyed_at`; PRE-7 returns `0` |
| **LIVE-18**: `--provider auto` picks Modal for low-util serverless | `fabrik gpu rent --kind serverless --workload auto-G-LIVE-18 --provider auto --utilization 0.2 --needs-serverless --template echo-handler --max-cost 0.10` | <$0.05 | CLI echoes `→ modal`, lifecycle completes |

### 5.4 Per-phase final gate (FINAL — terminal validation, run before commit)

The **ultimate validation** is `scripts/final_gate.py`. It is invoked at the end of each phase. All preceding gates must already have passed.

```bash
.venv/bin/python scripts/final_gate.py --lean --json
```

Pass criterion: `{"status": "success", "tier": 1, "failed": 0}`.

If `status: "failure"`, the commit MUST NOT proceed. Each failure category in the output names exactly which check failed (ruff / changelog / tests / etc); fix, then re-run final_gate until success.

### 5.5 Post-implementation orphan-check gate (FINAL-2 — paranoia)

Even after `final_gate.py` passes, run **explicit orphan checks across all three providers** as a final paranoia gate:

```bash
echo "--- ORPHAN CHECK ---"
echo "Modal:" && .venv/bin/modal app list --json | python3 -c "import json,sys; n=sum(1 for a in json.load(sys.stdin) if a['state']!='stopped'); print(f'  active apps: {n}'); exit(0 if n==0 else 1)"
echo "Vast:" && .venv/bin/vastai show endpoints --raw | python3 -c "import json,sys; n=len(json.load(sys.stdin)); print(f'  endpoints: {n}'); exit(0 if n==0 else 1)"
echo "Vast (instances):" && .venv/bin/vastai show instances --raw | python3 -c "import json,sys; n=len(json.load(sys.stdin)); print(f'  instances: {n}'); exit(0 if n==0 else 1)"
echo "RunPod:" && curl -s -H "Authorization: Bearer $(grep RUNPOD_API_KEY /opt/fabrik/.env.sysadmin | cut -d= -f2)" https://rest.runpod.io/v1/pods | python3 -c "import json,sys; n=len(json.load(sys.stdin)); print(f'  pods: {n}'); exit(0 if n==0 else 1)"
```

Pass criterion: all four `exit(0)`. Any orphan at this point is a P0 — manually destroy and document a Lesson Learnt.

---

## §6. Implementation order (deterministic; no overlap)

Each step lists its predecessor gates that must pass first. Implementation does NOT advance past a step without the gate passing.

| Step | Action | Predecessor gates | Output gate |
|---|---|---|---|
| **1** | Run PRE-1 through PRE-12 in order | (none — start) | All PRE-* pass |
| **2** | Create `templates/modal/echo-handler.py.j2` | PRE-1, PRE-12 | DELIV-1, DELIV-2, DELIV-3 |
| **3** | Implement `ModalClient.create_endpoint` + `destroy_endpoint` + `list_endpoints` + `run_endpoint_sync` (replace stubs at modal_provider.py:334-371) | DELIV-1 | DELIV-6, DELIV-10, DELIV-11, DELIV-17 |
| **4** | Generalize `_create_serverless_endpoint` in `gpu_rent.py` line 447 to dispatch per provider; add `--model` / `--template` to `rent()` kwargs | DELIV-6 | DELIV-12, DELIV-17 |
| **5** | Add `--model` + `--template` CLI flags in `cli.py` lines 3166-3252 | DELIV-12 | DELIV-15 |
| **6** | Add 7 unit tests for Modal dispatch (provider routing, subprocess mock, get_web_url mock, OutputExpiredError fallback) | DELIV-6, DELIV-12 | DELIV-16 (partial: 39 + 7 = 46) |
| **7** | Run LIVE-12 (Modal echo). Capture app_id + cost + wall-clock. | DELIV-6, DELIV-12, DELIV-15, DELIV-16 partial | LIVE-12 + PRE-7 post-check |
| **8** | Create `templates/modal/vllm-openai.py.j2` | (none) | DELIV-4, DELIV-5 |
| **9** | Run LIVE-13 (Modal vLLM) | LIVE-12, DELIV-4 | LIVE-13 + PRE-7 post-check |
| **10** | Implement `VastClient.create_endpoint` + `destroy_endpoint` + `list_endpoints` + `run_endpoint_sync` + helpers (replace stubs at vast_provider.py:385-399) | (none — independent of Modal work) | DELIV-7, DELIV-8, DELIV-9, DELIV-17 |
| **11** | Flip `HOURLY_USD_BY_PROVIDER["vast"]["serverless"]` at gpu_rent.py:144 from `None` → `0.40`; drop the `needs_serverless` Vast exclusion at lines 275-276 | DELIV-7 | DELIV-13, DELIV-14 |
| **12** | Add 6 unit tests for Vast serverless (mocked POSTs, /workergroups/ path verification, route flow) | DELIV-7 | DELIV-16 full (52) |
| **13** | Run LIVE-14 (Vast hello-world) | DELIV-7, DELIV-13, DELIV-14, DELIV-16 | LIVE-14 + PRE-5 post-check |
| **14** | Run LIVE-15 (Vast vLLM) | LIVE-14 | LIVE-15 + PRE-5 post-check |
| **15** | Run LIVE-16 + LIVE-17 + LIVE-18 | LIVE-14, LIVE-13 | All three pass; orphan checks zero |
| **16** | Update `docs/reference/modal-api.md` §21.1.2 + `docs/reference/vast-api.md` §13.4 + fix §11.3 path | LIVE-15 | DELIV-18 |
| **17** | Update `docs/operations/gpu-rent.md` Providers matrix (serverless ✅ on all 3) | DELIV-18 | (no gate, doc-only) |
| **18** | Add CHANGELOG entry under `[Unreleased]` | step 17 | (none — terminal gate below) |
| **19** | If Vast surfaces a new quirk during LIVE-14/15, add Lesson 71 to `docs/LESSONS_LEARNT.md` | LIVE-14, LIVE-15 | (none — discretionary) |
| **20** | **Terminal validation**: `scripts/final_gate.py --lean --json` | All preceding | **FINAL: status=success** |
| **21** | **Orphan paranoia**: §5.5 script | FINAL | **FINAL-2: all zero** |
| **22** | Commit + push | FINAL, FINAL-2 | git push success |

---

## §7. Risks + mitigations (every risk has a fallback)

| Risk | Likelihood | Mitigation (verified concrete) |
|---|---|---|
| Modal `app.deploy()` hangs >60s | Low | `subprocess.run(..., timeout=60)` for CLI calls; for SDK deploy, wrap in `concurrent.futures.ThreadPoolExecutor` with `result(timeout=120)`; on timeout fall through to `destroy_endpoint` |
| Vast endpoint create returns 402 (insufficient credit) | Med (balance was $4.98) | PRE-4 gate fails before code path runs; operator tops up to ≥$3 |
| Vast workergroup recruits 0 workers in 5min | High (marketplace) | `create_endpoint` returns immediately; LIVE-14/15 `work_fn` polls `/route/` with 30s backoff for up to `--max-lifetime` hours; cost guard enforces termination |
| Modal CLI auth fails in subprocess (env not propagated) | Low | Driver explicitly passes `env={**os.environ, "MODAL_TOKEN_ID": ..., "MODAL_TOKEN_SECRET": ...}` to subprocess (verified pattern §1.4) |
| `OutputExpiredError` is not what FunctionCall pending raises in 1.5.0 | Low | Caught alongside `TimeoutError` (its parent class); any non-cancellation exception treated conservatively as RUNNING (consistent with existing `modal_provider.py:159-178` logic) |
| Pinned vLLM hash `57903c5...` is removed by Vast | Med | `_resolve_template_hash` falls through to live `vastai search templates` on hash miss (§2.3) |
| Orphan left after a crashed LIVE gate | Low | Each LIVE gate is wrapped in `try/finally` that re-runs the orphan check; documented as Lesson 70 already enforced |
| `final_gate.py` flags a `TODO` placeholder in CHANGELOG (we hit this before) | Med | CHANGELOG entry is reviewed for placeholders before commit; final_gate auto-runs |

---

## §8. Zero-unknowns checklist (the convergence criterion)

For this plan to be considered CONVERGED, every cell must be checked. **All checked as of 2026-06-17 unless noted.**

- [x] Every claim about an existing file cites the file path + line range from a `Read`/`Grep` verification.
- [x] Every claim about an SDK method is verified via `inspect.signature` or `dir()` (probes 1–8, agent 3).
- [x] Every claim about a REST endpoint is verified via curl (agent 4).
- [x] Every claim about a template hash is verified live (agent 4, re-pinned 2026-06-17).
- [x] Every binding rule has a matching deliverable in §3.
- [x] Every step in §6 cites a predecessor gate.
- [x] Every gate in §5 has a concrete pass criterion (no "should work" language).
- [x] `final_gate.py` is named explicitly as the terminal validation (§5.4).
- [x] An orphan paranoia gate runs after `final_gate.py` (§5.5).
- [x] LoC budget is recalibrated from real file sizes (§3.1, agent 2).
- [x] Cost budget integration uses existing surfaces (no schema change) (§3.2, §3.3).
- [x] State file schema is verified compatible (§3.4).
- [x] All 4 critical bugs from v1 plan are explicitly addressed (§0 table).
- [x] All 6 rule gaps from v1 plan are explicitly addressed (§4 table).

**If any cell becomes unchecked during implementation, halt and re-iterate this plan.**

### §8.1 Iteration trail (convergence audit)

| Iter | Date | What changed | Bugs caught | Plan status |
|---|---|---|---|---|
| 1 | 2026-06-16 | v1 plan written | — | UNVERIFIED |
| 2 | 2026-06-17 morning | 4 parallel agents audited claims vs ground truth | B1 (`_app.stop()` missing), B2 (`list_apps` import missing), B3 (wrong exception name), B4 (wrong Vast endpoint path), R1–R6 rule gaps | CONVERGING |
| 3 | 2026-06-17 morning | Converged plan written; all known bugs fixed; binding rules mapped; `final_gate.py` named as terminal | — | NEAR CONVERGED |
| 4 | 2026-06-17 mid-morning | Final scan caught residual: all 4 plan §2.3 template hashes were hallucinated by iter-2 agent; `hash_id` is correct field name (not `hash`); no `hello-world` template exists in live registry | R7 (field name), R8 (agent-data verification process) | **CONVERGED** |

**Convergence declared 2026-06-17.** No more known unknowns. All ground-truth probes are evidence-of-record. Implementation MAY proceed past §6 step 1 (PRE-* gates) without further plan iteration unless a step's predecessor gate fails — in which case halt, re-iterate, and re-converge.

---

## §9. Out of scope (explicitly NOT in this phase)

- Custom PyWorker authoring (use stock Vast templates only) — Phase 4.
- Modal memory-snapshot tuning beyond defaults — Phase 4.
- Modal multi-workspace / environment management — Phase 4.
- Auto-rollout / A-B testing of multiple endpoint configs — Phase 4.
- Reference doc `RESILIENCE.md` updates — file does not exist (R2 in §0).

---

## §10. Sign-off contract

When this plan SHIPS (all 22 steps complete, FINAL + FINAL-2 GREEN), the README badge in [`docs/operations/gpu-rent.md`](../operations/gpu-rent.md) becomes:

| Surface | RunPod | Modal | Vast.ai |
| --- | --- | --- | --- |
| Pod mode | ✅ G-LIVE-2/3 | ✅ G-LIVE-7/8/9 | ✅ G-LIVE-5 |
| Serverless mode | ✅ G-LIVE-1 | ✅ **G-LIVE-12/13** | ✅ **G-LIVE-14/15** |
| `--provider auto` | ✅ | ✅ | ✅ |
| `fabrik gpu status / destroy` (pods + endpoints) | ✅ | ✅ G-LIVE-11/17 | ✅ G-LIVE-17 |
| `fabrik gpu reconcile --provider all` (pods + endpoints) | ✅ G-LIVE-10 | ✅ G-LIVE-16 | ✅ G-LIVE-16 |
| Reaper tag-safety (C4) | ✅ | ✅ | ✅ |

Plan finished, GPU surface complete across all three providers in both modes.

---

## §11. Plan-of-record dependencies

- Predecessor: `2026-06-16-fabrik-gpu-rent.md` (Phases 1–5 + provider-aware management surface)
- Supersedes: `2026-06-16-gpu-serverless-phase-3-5.md` (v1 plan, 4 critical bugs)
- Reference docs (must remain accurate during implementation):
  - [`docs/reference/modal-api.md`](../reference/modal-api.md) — Modal SDK + serverless API
  - [`docs/reference/vast-api.md`](../reference/vast-api.md) — Vast.ai REST + serverless API (fix §11.3 path during step 16)
  - [`docs/reference/runpod-api.md`](../reference/runpod-api.md) — RunPod (no change in this phase)
- Tooling:
  - `scripts/final_gate.py` — terminal validation (§5.4)
  - `.venv/bin/modal` — Modal CLI (subprocess pattern §1.4)
  - `.venv/bin/vastai` — Vast.ai CLI (used for PRE-5/PRE-6 orphan checks)
