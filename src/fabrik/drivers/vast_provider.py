"""Vast.ai driver — Phase 2 of the fabrik gpu rent plan.

Vast.ai is a GPU marketplace — community-hosted machines bidding against
each other. Lowest $/hr in the market, but instability is the price (hosts
can reclaim machines, OOM on oversold cards, etc.).

The rule (``76-gpu-workers.md`` line 359) prescribes Vast.ai specifically
for **training/fine-tuning with checkpoint-resumable workflows**:

    "Train on Vast.ai (cheapest). Infer on RunPod Serverless (best cold start)."

Auth: ``VAST_API_KEY`` env var. Stored in ``/opt/fabrik/.env.sysadmin``.

API: Vast.ai exposes a REST API at https://console.vast.ai/api/v0/ —
endpoints are documented at https://vast.ai/docs/cli/api. This driver wraps
the create/list/destroy paths in the same shape as RunPodClient.

Cost (per the rule, verified 2026-05-24 at vast.ai/pricing):
- Interruptible (spot): roughly half the on-demand rate
- On-demand: cheaper than RunPod Secure but with marketplace volatility
- Rule line 341: "VRAM contention — host may oversell. OOM on a 24GB card = overselling. Switch host."

Phase 2 status: driver shape complete, NOT live-tested (operator hasn't
created a Vast.ai account yet). When ready:
    drop VAST_API_KEY into .env.sysadmin
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

VAST_API_BASE = "https://console.vast.ai/api/v0"
SYSADMIN_ENV = Path("/opt/fabrik/.env.sysadmin")

# Vast.ai uses raw GPU names (case-sensitive, matches their search filters).
# Verified 2026-06-16 against the marketplace search filter UI.
VAST_GPU_NAMES = {
    "pod-h100": "H100 SXM",
    "pod-h100-pcie": "H100",  # PCIe variant just called "H100"
    "pod-h100-nvl": "H100 NVL",
    "pod-a100": "A100",
    "pod-a100-sxm": "A100 SXM4",
    "pod-h200": "H200",
    "pod-l40s": "L40S",
    "pod-rtx-4090": "RTX 4090",
}


class VastError(RuntimeError):
    """Vast.ai API error. ``status`` is the HTTP code; ``body`` the response payload."""

    def __init__(self, message: str, status: int | None = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


class VastClient:
    """Vast.ai REST API wrapper. Interface mirrors RunPodClient.

    Vast.ai's API quirks vs RunPod:
    - Instance creation is a 2-step search → create flow (find candidate
      offers, then `PUT /asks/{offer_id}/`). We collapse this into
      ``create_pod()`` by issuing the search ourselves.
    - No first-class "endpoint" / serverless concept. Phase 2 raises
      NotImplementedError for serverless paths — Vast.ai is pod-only.
    - Instance status: "running", "stopped", "offline", etc. We map to
      RunPod's RUNNING/EXITED/TERMINATED.
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        if api_key is None and not os.environ.get("VAST_API_KEY") and SYSADMIN_ENV.exists():
            load_dotenv(SYSADMIN_ENV)
        self.api_key = api_key or os.environ.get("VAST_API_KEY")
        if not self.api_key:
            raise VastError(
                "VAST_API_KEY is required "
                "(set it in /opt/fabrik/.env.sysadmin or the environment; "
                "generate at https://console.vast.ai/account)"
            )
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.Client(
            base_url=VAST_API_BASE,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> VastClient:
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    # --- core request (mirrors runpod.py:_request shape) -------------------
    def _request(
        self, method: str, path: str, *, json: dict | None = None, params: dict | None = None
    ) -> Any:
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._client.request(method, path, json=json, params=params)
            except httpx.RequestError as e:
                last_exc = VastError(f"Vast.ai request error on {method} {path}: {e}")
                if attempt < self.max_retries:
                    time.sleep(min(2**attempt, 10))
                    continue
                raise last_exc from e
            if 400 <= resp.status_code < 500:
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                raise VastError(
                    f"Vast.ai {resp.status_code} on {method} {path}: {body}",
                    status=resp.status_code,
                    body=body,
                )
            if resp.status_code >= 500:
                last_exc = VastError(
                    f"Vast.ai {resp.status_code} on {method} {path}",
                    status=resp.status_code,
                    body=resp.text,
                )
                if attempt < self.max_retries:
                    time.sleep(min(2**attempt, 10))
                    continue
                raise last_exc
            if resp.status_code == 204 or not resp.content:
                return None
            try:
                return resp.json()
            except Exception:
                return resp.text
        if last_exc:
            raise last_exc
        raise VastError(f"Vast.ai request failed after {self.max_retries} retries")

    # --- Pod API (Vast.ai calls them "instances") --------------------------
    def list_pods(self) -> list[dict[str, Any]]:
        """List all instances. Maps Vast.ai's response shape to RunPod-style dicts."""
        data = self._request("GET", "/instances/")
        instances = data.get("instances", []) if isinstance(data, dict) else data
        return [self._normalize_instance(inst) for inst in instances]

    def get_pod(self, pod_id: str) -> dict[str, Any]:
        data = self._request("GET", f"/instances/{pod_id}/")
        inst = data.get("instance") if isinstance(data, dict) and "instance" in data else data
        return self._normalize_instance(inst)

    def create_pod(
        self,
        *,
        gpu_type_id: str,
        image_name: str,
        env: dict[str, str] | None = None,
        container_disk_gb: int = 50,
        volume_gb: int = 20,  # Vast.ai uses container_disk only; volume_gb ignored
        cloud_type: str = "SECURE",  # Vast.ai: rentable=verified vs unverified
        interruptible: bool = False,
        ports: list[str] | None = None,
        name: str | None = None,
        gpu_count: int = 1,
    ) -> dict[str, Any]:
        """Two-phase: search for cheapest matching offer → create instance.

        ``gpu_type_id`` should match Vast.ai's GPU name (``H100 SXM``, ``RTX 4090``).
        Use :data:`VAST_GPU_NAMES` to translate from friendly aliases.
        """
        # 1) Search marketplace for cheapest matching offer
        search_query = {
            "verified": {"eq": True} if cloud_type == "SECURE" else {"eq": False},
            "gpu_name": {"eq": gpu_type_id},
            "num_gpus": {"eq": gpu_count},
            "disk_space": {"gte": container_disk_gb},
            "rentable": {"eq": True},
        }
        if interruptible:
            search_query["rented"] = {"eq": False}  # spot bid
        # Vast.ai's search API expects q as a JSON string in `q` param
        import json as _json

        offers = self._request(
            "GET",
            "/bundles/",
            params={"q": _json.dumps(search_query), "order": "dph_total"},
        )
        offer_list = offers.get("offers", []) if isinstance(offers, dict) else offers
        if not offer_list:
            raise VastError(
                f"no Vast.ai offers found matching gpu_type={gpu_type_id} "
                f"verified={cloud_type == 'SECURE'} interruptible={interruptible}"
            )
        cheapest = offer_list[0]
        offer_id = cheapest["id"]

        # 2) Create instance from the chosen offer
        body = {
            "client_id": "me",
            "image": image_name,
            "disk": container_disk_gb,
            "label": name or "fabrik-gpu-rent",
            "env": env or {},
            "runtype": "ssh" if (ports and any("22" in p for p in ports)) else "args",
        }
        if interruptible:
            body["price"] = cheapest.get("min_bid", cheapest["dph_total"] * 0.5)

        result = self._request("PUT", f"/asks/{offer_id}/", json=body)
        # Vast.ai returns {success: true, new_contract: <instance_id>}
        if not result.get("success"):
            raise VastError(f"Vast.ai instance creation failed: {result}")
        instance_id = result["new_contract"]
        return self._normalize_instance(
            {
                "id": instance_id,
                "actual_status": "loading",
                "dph_total": cheapest["dph_total"],
                "gpu_name": gpu_type_id,
            }
        )

    def wait_for_running(
        self, pod_id: str, *, timeout: int = 600, interval: int = 10
    ) -> dict[str, Any]:
        """Vast.ai instances take longer than RunPod to load (image pull, etc.). Default timeout 600s."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pod = self.get_pod(pod_id)
            status = pod.get("desiredStatus")
            if status == "RUNNING":
                return pod
            if status == "TERMINATED":
                raise VastError(
                    f"Vast.ai instance {pod_id} reached TERMINATED during provisioning",
                    body=pod,
                )
            time.sleep(interval)
        raise VastError(f"Vast.ai instance {pod_id} did not reach RUNNING within {timeout}s")

    def destroy_pod(self, pod_id: str) -> None:
        self._request("DELETE", f"/instances/{pod_id}/")

    # --- Serverless API (Vast.ai has no first-class serverless) ------------
    def list_endpoints(self) -> list[dict[str, Any]]:
        return []

    def get_endpoint(self, endpoint_id: str) -> dict[str, Any]:
        raise NotImplementedError("Vast.ai has no serverless endpoint API — use pods.")

    def create_endpoint(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError(
            "Vast.ai has no serverless API. Use --provider runpod for serverless "
            "or --provider modal for function-as-a-service."
        )

    def destroy_endpoint(self, endpoint_id: str) -> None:
        raise NotImplementedError("Vast.ai has no serverless endpoint API.")

    # --- Inference plane (also pod-only on Vast.ai) ------------------------
    def run_endpoint_sync(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError(
            "Vast.ai pods expose SSH/HTTP from the container — "
            "call directly via the pod's IP, not via this driver."
        )

    def run_endpoint_async(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError("see run_endpoint_sync")

    # --- Billing ------------------------------------------------------------
    def billing_pods(self, start: str | None = None, end: str | None = None) -> dict[str, Any]:
        # Vast.ai exposes a credit-balance + bills endpoint
        data = self._request("GET", "/users/current/")
        return {
            "balance": data.get("balance"),
            "credit": data.get("credit"),
            "_note": "Vast.ai per-pod billing must be aggregated from instance history",
        }

    def billing_endpoints(self, start: str | None = None, end: str | None = None) -> dict[str, Any]:
        return {"endpoints": [], "_note": "Vast.ai is pod-only; no endpoint billing"}

    # --- helpers ------------------------------------------------------------
    @staticmethod
    def _normalize_instance(inst: dict[str, Any]) -> dict[str, Any]:
        """Map Vast.ai's instance fields to the RunPod-style dict the orchestrator expects."""
        status_map = {
            "running": "RUNNING",
            "loading": "RUNNING",  # treat loading as RUNNING for orchestrator purposes
            "created": "RUNNING",
            "starting": "RUNNING",
            "stopped": "EXITED",
            "exited": "EXITED",
            "offline": "TERMINATED",
        }
        actual = inst.get("actual_status") or inst.get("status") or "unknown"
        return {
            "id": str(inst.get("id")),
            "desiredStatus": status_map.get(actual, "RUNNING"),
            "publicIp": inst.get("public_ipaddr"),
            "costPerHr": inst.get("dph_total"),
            "adjustedCostPerHr": inst.get("dph_total"),
            "gpu_name": inst.get("gpu_name"),
            "env": inst.get("env") or {},
            "_provider": "vast",
        }
