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
        """Vast.ai's ``GET /instances/<id>/`` response shape varies:

        - For a valid existing instance: ``{"instances": {<inst dict>}}``
          — singular dict UNDER the plural key (a quirk)
        - For ``GET /instances/`` (list all): ``{"instances": [<inst>, ...]}``
          — actual list
        - For an unknown ID: ``{"instances": null}``

        Handle all three. Earlier versions of this method assumed wrong
        shapes and raised ``KeyError(0)`` (G-LIVE-5 2026-06-16 run #7).
        """
        data = self._request("GET", f"/instances/{pod_id}/")
        inst: Any = {}
        if isinstance(data, dict):
            payload = data.get("instances", data.get("instance"))
            if isinstance(payload, dict):
                inst = payload
            elif isinstance(payload, list):
                inst = payload[0] if payload else {}
            elif payload is None and "instances" in data and data["instances"] is None:
                raise VastError(f"Vast.ai instance {pod_id} not found (instances=null)")
            else:
                inst = data
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
        # 1) Search marketplace for cheapest matching offer.
        # CRITICAL: verified --explain on the vastai CLI shows the real API
        # contract is POST /bundles/ with the FULL query AS JSON BODY (not
        # url-encoded params, not GET). See docs/reference/vast-api.md §11.4
        # quirks. Defaults `external=false rentable=true type=on-demand` match
        # the CLI's default query.
        # `reliability2 >= 0.98` filters out flaky hosts (those whose containers
        # get stuck in 'unknown' state on Vast). Verified empirically against
        # the live RTX 4090 pool 2026-06-16 — the cheapest sub-0.95 hosts
        # routinely fail to pull NVIDIA's public CUDA image. The floor only
        # raises cost by ~10% but eliminates ~all stuck-loading failures.
        search_query: dict[str, Any] = {
            "verified": {"eq": True} if cloud_type == "SECURE" else {"eq": False},
            "external": {"eq": False},
            "rentable": {"eq": True},
            "gpu_name": {"eq": gpu_type_id},
            "num_gpus": {"eq": gpu_count},
            "disk_space": {"gte": container_disk_gb},
            "rented": {"eq": False},
            "reliability2": {"gte": 0.98},
            "type": "bid" if interruptible else "on-demand",
            "order": [["dph_total", "asc"]],
            "allocated_storage": float(container_disk_gb),
            "limit": 10,
        }
        offers = self._request("POST", "/bundles/", json=search_query)
        offer_list = offers.get("offers", []) if isinstance(offers, dict) else offers
        if not offer_list:
            raise VastError(
                f"no Vast.ai offers found matching gpu_type={gpu_type_id} "
                f"verified={cloud_type == 'SECURE'} interruptible={interruptible}"
            )

        # 2) Try offers in cheapest-first order. Marketplace race: another
        # renter may claim our top pick between search and PUT /asks/, so
        # iterate down the list on 404/3603 `no_such_ask` errors instead of
        # giving up. Try up to max_offer_attempts to bound API spend.
        max_offer_attempts = 5
        last_err: VastError | None = None
        for attempt, offer in enumerate(offer_list[:max_offer_attempts], 1):
            offer_id = offer["id"]
            body = {
                "client_id": "me",
                "image": image_name,
                "disk": container_disk_gb,
                "label": name or "fabrik-gpu-rent",
                "env": env or {},
                "runtype": "ssh" if (ports and any("22" in p for p in ports)) else "args",
            }
            if interruptible:
                body["price"] = offer.get("min_bid", offer["dph_total"] * 0.5)
            try:
                result = self._request("PUT", f"/asks/{offer_id}/", json=body)
            except VastError as e:
                # 404/3603 `no_such_ask` = offer claimed by someone else.
                # Any 4xx on the claim is fatal for that specific offer;
                # try the next-cheapest.
                body_msg = ""
                if isinstance(e.body, dict):
                    body_msg = e.body.get("msg", "") or e.body.get("error", "")
                logger.info(
                    "vast offer %s unavailable (attempt %d/%d): %s",
                    offer_id,
                    attempt,
                    max_offer_attempts,
                    body_msg or e,
                )
                last_err = e
                continue

            if not result.get("success"):
                last_err = VastError(f"Vast.ai instance creation failed: {result}")
                logger.info("vast offer %s create returned non-success: %s", offer_id, result)
                continue

            instance_id = result["new_contract"]
            return self._normalize_instance(
                {
                    "id": instance_id,
                    "actual_status": "loading",
                    "dph_total": offer["dph_total"],
                    "gpu_name": gpu_type_id,
                }
            )

        raise VastError(
            f"all {min(len(offer_list), max_offer_attempts)} cheapest Vast offers "
            f"for {gpu_type_id} were unavailable at claim time — try again with "
            f"different filters or a less popular GPU. Last error: {last_err}"
        )

    # Poll-trap states per Vast's own llms.txt — once an instance hits one
    # of these, it will NEVER reach `running`. Destroy + retry.
    # NOTE: `unknown` is in the docs' terminal list BUT empirically it's
    # also the initial state after `PUT /asks/<offer>/` returns — Vast
    # hasn't yet propagated the actual host status. Trip only after the
    # instance has been alive for ``_UNKNOWN_GRACE_SECONDS`` to avoid
    # destroying healthy-but-still-loading pods. (G-LIVE-5 2026-06-16.)
    _TERMINAL_BAD_STATES = frozenset({"exited", "offline"})
    _UNKNOWN_GRACE_SECONDS = 90

    def wait_for_running(
        self, pod_id: str, *, timeout: int = 600, interval: int = 10
    ) -> dict[str, Any]:
        """Poll until the instance is running. Honors Vast's poll-trap quirk.

        Vast.ai instances take longer than RunPod to load (image pull, etc.).
        Default timeout 600s. Raises VastError immediately if the status drops
        to any of ``_TERMINAL_BAD_STATES`` — those never recover.
        """
        started = time.monotonic()
        deadline = started + timeout
        while time.monotonic() < deadline:
            pod = self.get_pod(pod_id)
            cur_state = (pod.get("_cur_state") or "").lower()
            actual = (pod.get("_actual_status") or "").lower()
            status_msg = pod.get("_status_msg") or ""

            # Success signal: container's `cur_state` is running.
            # `actual_status` is allowed to be 'exited' as long as `status_msg`
            # explicitly says "success" (e.g. when image's PID 1 has exited
            # but the container is otherwise healthy).
            if cur_state == "running" and (
                actual == "running"
                or actual == "loading"
                or (actual == "exited" and "success" in status_msg.lower())
            ):
                return pod

            # Hard terminal: container itself is in a bad state.
            if cur_state in self._TERMINAL_BAD_STATES:
                raise VastError(
                    f"Vast.ai instance {pod_id} container state "
                    f"{cur_state!r} — destroy + retry on a different offer. "
                    f"status_msg={status_msg!r}",
                    body=pod,
                )

            # actual_status='exited' WITHOUT a success status_msg = real failure
            if (
                actual == "exited"
                and "success" not in status_msg.lower()
                and (time.monotonic() - started) > self._UNKNOWN_GRACE_SECONDS
            ):
                raise VastError(
                    f"Vast.ai instance {pod_id} actual_status=exited and "
                    f"status_msg={status_msg!r} — entrypoint failed",
                    body=pod,
                )

            # Initial 'unknown' is OK, but only for the grace window
            if (
                cur_state == "unknown"
                and (time.monotonic() - started) > self._UNKNOWN_GRACE_SECONDS
            ):
                raise VastError(
                    f"Vast.ai instance {pod_id} still in cur_state='unknown' "
                    f"after {self._UNKNOWN_GRACE_SECONDS}s grace — host likely "
                    f"failed to pull image. Destroy + retry.",
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
        """Map Vast.ai's instance fields to the RunPod-style dict the orchestrator expects.

        Vast.ai has *multiple* status fields and they're NOT consistent:
        - ``actual_status`` — the entrypoint process state (often 'exited'
          immediately after image start even when the container is healthy,
          because the default `python` entrypoint runs + exits)
        - ``cur_state`` — the **container** lifecycle state. THIS is the
          authoritative "is it usable?" field.
        - ``intended_status`` / ``next_state`` — desired state.
        - ``status_msg`` — human-readable; "success, running <image>" is
          the success signal even when actual_status='exited'.

        Verified via live probe 2026-06-16: a fresh on-demand RTX 4090 went
        ``actual_status: loading → exited`` while ``cur_state: running``
        throughout. The container WAS healthy; ``actual_status`` reflected
        the image's PID-1 exit, not container death.

        We prefer ``cur_state`` and fall back to ``actual_status``.
        """
        status_map = {
            "running": "RUNNING",
            "loading": "RUNNING",  # transient pull state, will resolve
            "created": "RUNNING",
            "starting": "RUNNING",
            "stopped": "EXITED",
            "exited": "EXITED",
            "offline": "TERMINATED",
        }
        cur_state = (inst.get("cur_state") or "").lower()
        actual = (inst.get("actual_status") or inst.get("status") or "unknown").lower()
        # Authoritative: cur_state (container lifecycle). Fallback: actual_status.
        primary = cur_state if cur_state else actual
        return {
            "id": str(inst.get("id")),
            "desiredStatus": status_map.get(primary, "RUNNING"),
            "_raw_status": primary,
            "_actual_status": actual,
            "_cur_state": cur_state,
            "_status_msg": inst.get("status_msg") or "",
            "publicIp": inst.get("public_ipaddr"),
            "costPerHr": inst.get("dph_total"),
            "adjustedCostPerHr": inst.get("dph_total"),
            "gpu_name": inst.get("gpu_name"),
            "env": inst.get("env") or {},
            "_provider": "vast",
        }
