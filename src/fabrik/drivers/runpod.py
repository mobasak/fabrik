"""RunPod REST API driver.

Mirrors src/fabrik/drivers/vultr.py exactly:
- Module-level constants (BASE URL, SYSADMIN_ENV path)
- ``RunPodError`` extends RuntimeError with status + body
- ``RunPodClient`` defers env loading to __init__ (so tests can monkeypatch)
- ``_request()`` retries 5xx + transport errors, fails fast on 4xx
- Context-manager support via __enter__/__exit__

Auth: ``Authorization: Bearer <RUNPOD_API_KEY>`` (verified 2026-06-16 against
``rest.runpod.io/v1/pods`` returning HTTP 200).

API surface (verified 2026-06-16 from ``docs.runpod.io/llms.txt`` index):

Pods:
- POST   /v1/pods                 → create
- GET    /v1/pods                 → list
- GET    /v1/pods/{podId}         → get one
- DELETE /v1/pods/{podId}         → destroy

Serverless endpoints:
- POST   /v1/endpoints            → create
- GET    /v1/endpoints            → list
- GET    /v1/endpoints/{endpointId} → get one
- DELETE /v1/endpoints/{endpointId} → destroy

Inference (different host: ``api.runpod.ai``, not ``rest.runpod.io``):
- POST   https://api.runpod.ai/v2/{endpointId}/run    → async fire-and-forget
- POST   https://api.runpod.ai/v2/{endpointId}/runsync → sync, blocks until done

Billing:
- GET    /v1/billing/pods         → period spend per pod
- GET    /v1/billing/endpoints    → period spend per endpoint

Companion: src/fabrik/orchestrator/gpu_rent.py (the try/finally wrapper).
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Control-plane REST API (pods + endpoints + billing)
RUNPOD_API_BASE = "https://rest.runpod.io/v1"
# Data-plane inference API (different subdomain — used for /run + /runsync calls)
RUNPOD_INFERENCE_BASE = "https://api.runpod.ai/v2"
SYSADMIN_ENV = Path("/opt/fabrik/.env.sysadmin")

# Verified 2026-06-16 against docs.runpod.io/references/gpu-types.md.
# Friendly aliases (used by `fabrik gpu rent --kind …`) → exact RunPod gpuTypeIds.
# Add new entries when RunPod publishes more GPU types. See:
#   https://docs.runpod.io/references/gpu-types
GPU_TYPE_IDS = {
    "pod-h100": "NVIDIA H100 80GB HBM3",  # SXM, fastest
    "pod-h100-pcie": "NVIDIA H100 PCIe",
    "pod-h100-nvl": "NVIDIA H100 NVL",  # 94 GB VRAM
    "pod-a100": "NVIDIA A100 80GB PCIe",
    "pod-a100-sxm": "NVIDIA A100-SXM4-80GB",
    "pod-h200": "NVIDIA H200",
    "pod-l40s": "NVIDIA L40S",  # cheap inference tier
    "pod-rtx-4090": "NVIDIA GeForce RTX 4090",  # cheapest test pod
}


class RunPodError(RuntimeError):
    """RunPod API error. ``status`` is the HTTP code; ``body`` the parsed payload."""

    def __init__(self, message: str, status: int | None = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


class RunPodClient:
    """RunPod REST API v1 client.

    Retry policy: 5xx + transport errors → retry up to ``max_retries`` with
    exponential backoff. 4xx → fail fast (these are our bug).

    Auth via Bearer token from RUNPOD_API_KEY env. Loads ``.env.sysadmin`` if
    the env var is not already present AND no api_key was passed.
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        # Mirror vultr.py:60-67 — config.py only loads /opt/fabrik/.env;
        # the sysadmin secrets (incl. RUNPOD_API_KEY) live in .env.sysadmin
        # and must be loaded explicitly here.
        if api_key is None and not os.environ.get("RUNPOD_API_KEY") and SYSADMIN_ENV.exists():
            load_dotenv(SYSADMIN_ENV)
        self.api_key = api_key or os.environ.get("RUNPOD_API_KEY")
        if not self.api_key:
            raise RunPodError(
                "RUNPOD_API_KEY is required "
                "(set it in /opt/fabrik/.env.sysadmin or the environment)"
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
        # Separate client for the inference plane (different base URL)
        self._inf_client = httpx.Client(
            base_url=RUNPOD_INFERENCE_BASE,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    # --- lifecycle ----------------------------------------------------------
    def close(self) -> None:
        self._client.close()
        self._inf_client.close()

    def __enter__(self) -> RunPodClient:
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    # --- core request -------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        client: httpx.Client | None = None,
    ) -> Any:
        """Make a request. Retry on transport errors and 5xx; never on 4xx."""
        cli = client or self._client
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = cli.request(method, path, json=json, params=params)
            except httpx.RequestError as e:
                last_exc = RunPodError(f"RunPod request error on {method} {path}: {e}")
                if attempt < self.max_retries:
                    time.sleep(min(2**attempt, 10))
                    continue
                raise last_exc from e

            # 4xx: don't retry — our bug
            if 400 <= resp.status_code < 500:
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                raise RunPodError(
                    f"RunPod {resp.status_code} on {method} {path}: {body}",
                    status=resp.status_code,
                    body=body,
                )

            # 5xx: retry with backoff
            if resp.status_code >= 500:
                last_exc = RunPodError(
                    f"RunPod {resp.status_code} on {method} {path} (will retry)",
                    status=resp.status_code,
                    body=resp.text,
                )
                if attempt < self.max_retries:
                    time.sleep(min(2**attempt, 10))
                    continue
                raise last_exc

            # 2xx
            if resp.status_code == 204 or not resp.content:
                return None
            try:
                return resp.json()
            except Exception:
                return resp.text

        # Defensive: if loop fell through without returning, raise last
        if last_exc:
            raise last_exc
        raise RunPodError(f"RunPod request failed after {self.max_retries} retries")

    # --- Pod API ------------------------------------------------------------
    def list_pods(self) -> list[dict[str, Any]]:
        """List all pods. Empty list if none."""
        result = self._request("GET", "/pods")
        return result if isinstance(result, list) else result.get("pods", [])

    def get_pod(self, pod_id: str) -> dict[str, Any]:
        """Get pod state. ``desiredStatus`` ∈ RUNNING|EXITED|TERMINATED."""
        return self._request("GET", f"/pods/{pod_id}")

    def create_pod(
        self,
        *,
        gpu_type_id: str,
        image_name: str,
        env: dict[str, str] | None = None,
        container_disk_gb: int = 50,
        volume_gb: int = 20,
        cloud_type: str = "SECURE",
        interruptible: bool = False,
        ports: list[str] | None = None,
        name: str | None = None,
        gpu_count: int = 1,
    ) -> dict[str, Any]:
        """Create a pod. Body fields verified 2026-06-16 against POST /v1/pods.

        ``gpu_type_id`` must be one of the values in GPU_TYPE_IDS (or a raw
        ``gpuTypeIds`` string from docs.runpod.io/references/gpu-types).
        ``cloud_type``: "SECURE" (datacenter) or "COMMUNITY" (cheaper, shared kernel).
        """
        payload: dict[str, Any] = {
            "computeType": "GPU",
            "cloudType": cloud_type,
            "imageName": image_name,
            "gpuTypeIds": [gpu_type_id],
            "gpuCount": gpu_count,
            "containerDiskInGb": container_disk_gb,
            "volumeInGb": volume_gb,
            "interruptible": interruptible,
            "env": env or {},
            "ports": ports or ["8888/http", "22/tcp"],
        }
        if name is not None:
            payload["name"] = name
        return self._request("POST", "/pods", json=payload)

    def wait_for_running(
        self,
        pod_id: str,
        *,
        timeout: int = 300,
        interval: int = 5,
    ) -> dict[str, Any]:
        """Poll until ``desiredStatus == 'RUNNING'`` or timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pod = self.get_pod(pod_id)
            status = pod.get("desiredStatus")
            if status == "RUNNING":
                return pod
            if status in ("EXITED", "TERMINATED"):
                raise RunPodError(
                    f"pod {pod_id} reached terminal status {status} during provisioning",
                    body=pod,
                )
            time.sleep(interval)
        raise RunPodError(f"pod {pod_id} did not reach RUNNING within {timeout}s")

    def destroy_pod(self, pod_id: str) -> None:
        """Destroy a pod. Returns None on success."""
        self._request("DELETE", f"/pods/{pod_id}")

    def pause_pod(self, pod_id: str) -> dict[str, Any]:
        """Stop a pod without destroying it.

        RunPod API: POST /pods/{pod_id}/stop (verified at docs/reference/apis/
        runpod-api.md). Stopped pods keep their volume + container disk
        but stop billing GPU/CPU time. Restart with resume_pod().
        """
        # POST with empty body; RunPod returns updated pod dict
        return self._request("POST", f"/pods/{pod_id}/stop") or {"id": pod_id, "stopped": True}

    def resume_pod(self, pod_id: str) -> dict[str, Any]:
        """Resume a previously paused pod.

        RunPod API: POST /pods/{pod_id}/start. The pod re-acquires GPU
        from the same machine (best-effort — may be relocated). Use
        wait_for_running() after resume to confirm container is live.
        """
        return self._request("POST", f"/pods/{pod_id}/start") or {"id": pod_id, "resumed": True}

    # --- Serverless endpoint API -------------------------------------------
    def list_endpoints(self) -> list[dict[str, Any]]:
        result = self._request("GET", "/endpoints")
        return result if isinstance(result, list) else result.get("endpoints", [])

    def get_endpoint(self, endpoint_id: str) -> dict[str, Any]:
        return self._request("GET", f"/endpoints/{endpoint_id}")

    def create_endpoint(
        self,
        *,
        template_id: str,
        name: str,
        gpu_type_ids: list[str] | None = None,
        workers_min: int = 0,
        workers_max: int = 3,
        idle_timeout: int = 5,
        flashboot: bool = True,
        execution_timeout_ms: int = 600_000,
    ) -> dict[str, Any]:
        """Create a serverless endpoint.

        ``workers_min=0`` = true scale-to-zero (no idle cost).
        ``flashboot=True`` = sub-second cold start via NVMe-cached workers.
        """
        payload: dict[str, Any] = {
            "templateId": template_id,
            "name": name,
            "computeType": "GPU",
            "workersMin": workers_min,
            "workersMax": workers_max,
            "idleTimeout": idle_timeout,
            "flashboot": flashboot,
            "executionTimeoutMs": execution_timeout_ms,
        }
        if gpu_type_ids:
            payload["gpuTypeIds"] = gpu_type_ids
        return self._request("POST", "/endpoints", json=payload)

    def destroy_endpoint(self, endpoint_id: str) -> None:
        self._request("DELETE", f"/endpoints/{endpoint_id}")

    # --- Inference plane (api.runpod.ai/v2) --------------------------------
    def run_endpoint_sync(
        self,
        endpoint_id: str,
        payload: dict[str, Any],
        *,
        timeout: float = 600.0,
    ) -> dict[str, Any]:
        """Fire a synchronous inference call against a serverless endpoint.

        Hits POST https://api.runpod.ai/v2/{endpoint_id}/runsync — blocks until
        the worker completes (up to ``timeout``). Body shape depends on the
        endpoint's handler (for vLLM workers: ``{"input": {"prompt": "..."}}``).
        """
        prior = self._inf_client.timeout
        try:
            self._inf_client.timeout = timeout
            return self._request(
                "POST", f"/{endpoint_id}/runsync", json=payload, client=self._inf_client
            )
        finally:
            self._inf_client.timeout = prior

    def run_endpoint_async(
        self,
        endpoint_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Fire an async inference call. Returns ``{id: ..., status: 'IN_QUEUE'}``."""
        return self._request("POST", f"/{endpoint_id}/run", json=payload, client=self._inf_client)

    # --- Billing ------------------------------------------------------------
    def billing_pods(self, start: str | None = None, end: str | None = None) -> dict[str, Any]:
        """Pod spend for a period. Dates are ISO 8601 if specified."""
        params = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        return self._request("GET", "/billing/pods", params=params or None)

    def billing_endpoints(self, start: str | None = None, end: str | None = None) -> dict[str, Any]:
        params = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        return self._request("GET", "/billing/endpoints", params=params or None)
