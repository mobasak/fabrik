"""Modal driver — Phase 2 of the fabrik gpu rent plan.

Modal exposes its API via the ``modal`` Python SDK rather than a REST surface
(unlike RunPod's ``rest.runpod.io``). This driver wraps the SDK in the same
shape as :class:`fabrik.drivers.runpod.RunPodClient` so the orchestrator can
dispatch on ``provider`` without caring about the underlying transport.

Auth: ``MODAL_TOKEN_ID`` + ``MODAL_TOKEN_SECRET`` env vars (Modal's standard
two-part token). Stored in ``/opt/fabrik/.env.sysadmin``, same pattern as
``RUNPOD_API_KEY``.

When to pick Modal over RunPod (from the plan's D1 rationale + the rule
file ``76-gpu-workers.md`` lines 387 + 354):

- **Modal wins** for pipeline-shape workloads (functions chained as a graph),
  pure-Python decorator DX without container build pipelines, per-second
  billing with sub-4s cold start, and "deploy from local terminal" flows.
- **RunPod wins** for container-based deploys, traditional Docker images,
  persistent network volumes, and cheapest H100 inference.

Phase 1 default is RunPod (matches Fabrik's container-first model 1:1).
Phase 2 adds Modal so chained-function workloads have a native target.

Cost (per the rule, verified 2026-05-24 at modal.com/pricing):
- $4.56/hr base GPU rate (H100)
- 3.75x multiplier on CPU+RAM in US non-preemptible
- Per-second billing

Phase 2 status: driver shape complete, NOT live-tested (operator hasn't
created a Modal account yet). When account is ready:
    pip install modal
    modal token new
    drop MODAL_TOKEN_ID + MODAL_TOKEN_SECRET into .env.sysadmin
Then re-run tests with @pytest.mark.requires_fabrik_env marked tests.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

SYSADMIN_ENV = Path("/opt/fabrik/.env.sysadmin")

# Modal's GPU type strings (the SDK's `gpu="H100"` argument value, NOT
# RunPod-style full hardware IDs).
# Verified 2026-06-16 at modal.com/docs/guide/gpu.
MODAL_GPU_TYPES = {
    "pod-h100": "H100",
    "pod-h100-pcie": "H100",  # Modal doesn't distinguish SXM vs PCIe
    "pod-a100": "A100",
    "pod-a100-sxm": "A100",
    "pod-h200": "H200",
    "pod-l40s": "L40S",
    "pod-rtx-4090": "L4",  # Modal doesn't offer 4090; map to closest small inference GPU
}


class ModalError(RuntimeError):
    """Modal API error. Carries the original SDK exception for debugging."""

    def __init__(self, message: str, *, cause: Exception | None = None):
        super().__init__(message)
        self.cause = cause


class ModalClient:
    """Modal SDK wrapper. Interface mirrors RunPodClient where shapes overlap.

    Modal's primitive is the ``App`` containing ``Function`` deployments —
    NOT pods in the RunPod sense. The "pod" abstraction here is implemented
    via Modal's `App.spawn()` returning a function call handle that we treat
    as the pod's "id".

    Phase 2 is offline-mockable. Live tests require ``modal`` SDK install +
    operator's Modal token. The SDK import is deferred inside ``__init__``
    so the rest of Fabrik can import this module without ``modal`` installed.
    """

    def __init__(
        self,
        token_id: str | None = None,
        token_secret: str | None = None,
        timeout: float = 30.0,
    ):
        # Load .env.sysadmin once (mirror vultr/runpod pattern)
        if token_id is None and not os.environ.get("MODAL_TOKEN_ID") and SYSADMIN_ENV.exists():
            load_dotenv(SYSADMIN_ENV)
        self.token_id = token_id or os.environ.get("MODAL_TOKEN_ID")
        self.token_secret = token_secret or os.environ.get("MODAL_TOKEN_SECRET")
        if not self.token_id or not self.token_secret:
            raise ModalError(
                "MODAL_TOKEN_ID + MODAL_TOKEN_SECRET are required "
                "(set in /opt/fabrik/.env.sysadmin or environment; "
                "generate via `modal token new`)"
            )
        self.timeout = timeout

        # Deferred SDK import — Phase 2 doesn't require `modal` to be
        # installed unless ModalClient is actually instantiated.
        try:
            import modal  # noqa: F401

            self._modal = modal
        except ImportError as e:
            raise ModalError(
                "modal SDK not installed (`pip install modal>=0.65`). "
                "Phase 2 requires this when --provider=modal is used.",
                cause=e,
            )

    # --- lifecycle ----------------------------------------------------------
    def close(self) -> None:
        pass  # Modal SDK manages its own connections

    def __enter__(self) -> ModalClient:
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    # --- Pod-equivalent API (function spawn) -------------------------------
    def list_pods(self) -> list[dict[str, Any]]:
        """List active function calls (Modal's pod analog).

        Modal does NOT have a global "list all my containers" API in v1.
        For Phase 2 we maintain pod IDs only in our own state file
        (``data/gpu-rent-state.json``) and verify each via ``get_pod()``.
        """
        return []

    def get_pod(self, pod_id: str) -> dict[str, Any]:
        """Look up a Modal function call by ID.

        ``pod_id`` here is the FunctionCall.object_id returned at spawn time.
        We translate Modal's FunctionCall state into the RunPod-style fields
        the orchestrator expects (``desiredStatus``, ``costPerHr``).
        """
        try:
            fc = self._modal.FunctionCall.from_id(pod_id)
            # Modal exposes finalized() and stats(); we map to status string.
            status = "RUNNING" if not fc.finalized() else "EXITED"
        except Exception as e:
            raise ModalError(f"could not resolve Modal call {pod_id}: {e}", cause=e)
        return {
            "id": pod_id,
            "desiredStatus": status,
            "costPerHr": None,  # Modal bills per-second; not surfaced per call
            "adjustedCostPerHr": None,
            "_provider": "modal",
        }

    def create_pod(
        self,
        *,
        gpu_type_id: str,
        image_name: str,
        env: dict[str, str] | None = None,
        container_disk_gb: int = 50,  # Modal ignores; kept for signature parity
        volume_gb: int = 20,  # ditto
        cloud_type: str = "SECURE",  # Modal: oracle (default) vs custom; ignored here
        interruptible: bool = False,
        ports: list[str] | None = None,  # not used; Modal exposes via web_endpoints
        name: str | None = None,
        gpu_count: int = 1,
    ) -> dict[str, Any]:
        """Spawn a Modal function on a GPU.

        ``gpu_type_id`` should be Modal's string ("H100", "A100", etc.).
        Use :data:`MODAL_GPU_TYPES` to translate from the orchestrator's
        friendly ``--kind pod-*`` aliases.

        This builds an inline ``modal.App`` + ``modal.Function`` from a
        minimal Python lambda, spawns it, and returns the FunctionCall ID
        as the pod_id. The handler is intentionally a no-op — work_fn from
        gpu_rent.rent() owns the actual execution.
        """
        modal = self._modal
        app = modal.App(name or "fabrik-gpu-rent")

        # Build an image. For Phase 2 MVP we use the default Modal Python
        # image with the env vars injected. Operator can extend this.
        image = modal.Image.debian_slim(python_version="3.12")
        if env:
            for k, v in env.items():
                image = image.env({k: v})

        # Spawn a no-op "container" — Modal will allocate a GPU + workspace.
        # The actual work happens via work_fn which Fabrik invokes after this
        # returns. For Modal's idiomatic flow, work_fn should itself be a
        # @app.function-decorated callable; Phase 2 punts on that integration
        # and treats Modal pods as equivalent to RunPod pods.
        @app.function(image=image, gpu=gpu_type_id, timeout=86400)
        def _gpu_session_holder():
            # Hold the container alive until destroyed.

            time.sleep(86400)

        fc = _gpu_session_holder.spawn()
        return {
            "id": fc.object_id,
            "desiredStatus": "RUNNING",
            "publicIp": None,  # Modal doesn't expose public IPs by default
            "costPerHr": None,
            "_modal_function_call": fc,
            "_provider": "modal",
        }

    def wait_for_running(
        self, pod_id: str, *, timeout: int = 300, interval: int = 5
    ) -> dict[str, Any]:
        """Modal containers are RUNNING by the time spawn() returns. No-op poll."""
        return self.get_pod(pod_id)

    def destroy_pod(self, pod_id: str) -> None:
        """Cancel a Modal function call."""
        try:
            fc = self._modal.FunctionCall.from_id(pod_id)
            fc.cancel()
        except Exception as e:
            raise ModalError(f"failed to cancel Modal call {pod_id}: {e}", cause=e)

    # --- Serverless API (Modal's `web_endpoint`) ---------------------------
    def list_endpoints(self) -> list[dict[str, Any]]:
        # Modal exposes endpoints via App.deploy() + @web_endpoint — no
        # global API to list. For Phase 2 we track endpoint IDs in state.
        return []

    def get_endpoint(self, endpoint_id: str) -> dict[str, Any]:
        # Endpoint URLs are deterministic from app+function name; we just
        # return the URL we stored when create_endpoint was called.
        return {"id": endpoint_id, "_provider": "modal"}

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
        """Modal serverless: declares a web_endpoint and deploys.

        ``template_id`` is interpreted as a Modal App name (we don't have
        RunPod-style template IDs in Modal). ``flashboot`` and ``workers_min``
        are ignored — Modal handles cold-start mitigation transparently.
        """
        raise NotImplementedError(
            "Modal serverless endpoint creation requires a deployable App. "
            "Phase 2 ships the SHAPE; actual deployment is Phase 3 work because "
            "it needs the operator to provide a Modal App definition file."
        )

    def destroy_endpoint(self, endpoint_id: str) -> None:
        raise NotImplementedError(
            "Modal endpoint destroy: requires `modal app delete <name>` via SDK. "
            "Phase 2 stub — wire up in Phase 3."
        )

    # --- Inference plane ---------------------------------------------------
    def run_endpoint_sync(
        self, endpoint_id: str, payload: dict[str, Any], *, timeout: float = 600.0
    ) -> dict[str, Any]:
        raise NotImplementedError(
            "Modal inference: call the function directly via fc.get(). "
            "Phase 2 shape; wire in Phase 3."
        )

    def run_endpoint_async(self, endpoint_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("see run_endpoint_sync")

    # --- Billing ------------------------------------------------------------
    def billing_pods(self, start: str | None = None, end: str | None = None) -> dict[str, Any]:
        # Modal exposes billing via dashboard, not SDK as of 0.65.x.
        # Phase 2 returns empty; cost reconciliation lives in
        # gpu_rent._compute_actual_cost using wall-clock + HOURLY_USD.
        return {"pods": [], "_note": "Modal billing not yet SDK-accessible"}

    def billing_endpoints(self, start: str | None = None, end: str | None = None) -> dict[str, Any]:
        return {"endpoints": [], "_note": "Modal billing not yet SDK-accessible"}
