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
import uuid
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
        # Live state: Modal requires functions to run INSIDE an `app.run()`
        # context. We open the context in create_pod() and store the handle
        # so destroy_pod() can close it. Treating Modal like a "spawn and
        # forget" pod provider doesn't work — the SDK rejects un-hydrated
        # function calls (G-LIVE-7 caught this 2026-06-16).
        self._active_app_ctx: Any = None
        self._active_app: Any = None
        self._active_fc: Any = None
        self._active_fc_id: str | None = None

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
        """Open a Modal App ephemeral run and spawn a GPU holder.

        Modal's pattern: functions are hydrated only INSIDE an ``app.run()``
        context. G-LIVE-7 confirmed: ``.spawn()`` outside the context raises
        ``ExecutionError('Function has not been hydrated...')``.

        This implementation:
        1. Builds a fresh ``modal.App`` per rental (one app per session).
        2. Decorates a no-op holder at MODULE level (via a global registry)
           because Modal forbids inner-scope decorators even with
           ``serialized=True`` once you also need `.spawn()` against it.
        3. Manually enters the app's ``run()`` context — stores the context
           manager on ``self._active_app_ctx`` so ``destroy_pod()`` can exit.
        4. Spawns the holder, returns FC id as pod_id.

        ``gpu_type_id`` is Modal's string ("H100", "A100", "L4", etc.) —
        translated from the friendly ``--kind`` alias upstream.
        """
        if self._active_app_ctx is not None:
            raise ModalError(
                "ModalClient already has an active app context — "
                "destroy_pod() must be called before create_pod() again"
            )
        modal = self._modal

        # Build a unique App name so concurrent rentals don't collide.
        app_name = name or f"fabrik-gpu-rent-{uuid.uuid4().hex[:8]}"
        app = modal.App(app_name)

        # Build the image — debian_slim + env vars passed at runtime.
        # NOTE: Modal also accepts the env on the function (preferred) so the
        # image stays cached across calls with different envs.
        image = modal.Image.debian_slim(python_version="3.12")

        # The session holder — uses MODULE-LEVEL function (defined below the
        # class) which Modal hydrates correctly. We bind the gpu_type at the
        # decorator call time. `serialized=True` allows the inline binding.
        holder = app.function(image=image, gpu=gpu_type_id, timeout=86400, serialized=True)(
            _modal_gpu_session_holder
        )

        # Enter the app.run() context manually. This is what Modal needs:
        # `with app.run(): holder.spawn()`. We expand the `with` into
        # __enter__/__exit__ to fit Fabrik's create→work→destroy lifecycle.
        app_ctx = app.run()
        running_app = app_ctx.__enter__()

        try:
            # The holder is a no-op sleep — env vars are baked into the image
            # at decoration time via .env() if needed, not passed at call.
            fc = holder.spawn()
        except Exception:
            # If spawn fails, we must close the context to avoid leaking the
            # running app. Re-raise after cleanup.
            try:
                app_ctx.__exit__(None, None, None)
            finally:
                pass
            raise

        # Store the live handles so destroy_pod can clean up.
        self._active_app_ctx = app_ctx
        self._active_app = running_app
        self._active_fc = fc
        self._active_fc_id = fc.object_id

        return {
            "id": fc.object_id,
            "desiredStatus": "RUNNING",
            "publicIp": None,
            "costPerHr": None,
            "_app_name": app_name,
            "_provider": "modal",
        }

    def wait_for_running(
        self, pod_id: str, *, timeout: int = 300, interval: int = 5
    ) -> dict[str, Any]:
        """Modal hydrates functions when entering app.run(); spawn returns
        immediately. The CONTAINER may still be cold-starting, but Modal
        bills only the active seconds, so no extra wait needed here."""
        return {
            "id": pod_id,
            "desiredStatus": "RUNNING",
            "_provider": "modal",
        }

    def destroy_pod(self, pod_id: str) -> None:
        """Cancel the function call AND exit the app.run() context.

        Order matters: cancel the FC first so Modal stops scheduling work,
        then exit the context (which would auto-cancel anyway but adds an
        explicit checkpoint for our state tracking).
        """
        if self._active_fc_id and self._active_fc_id != pod_id:
            logger.warning(
                "destroy_pod called for %s but active session is %s — "
                "attempting via Function.from_id",
                pod_id,
                self._active_fc_id,
            )
        # Cancel the function call (best-effort; ignore if already done)
        try:
            if self._active_fc is not None:
                self._active_fc.cancel()
            else:
                fc = self._modal.FunctionCall.from_id(pod_id)
                fc.cancel()
        except Exception as e:  # noqa: BLE001
            logger.warning("modal FC.cancel(%s) failed (non-fatal): %s", pod_id, e)

        # Exit the app.run() context — this is what actually releases the GPU.
        if self._active_app_ctx is not None:
            try:
                self._active_app_ctx.__exit__(None, None, None)
            except Exception as e:
                logger.warning("modal app_ctx.__exit__ failed: %s", e)
                raise ModalError(f"failed to exit modal app context for {pod_id}: {e}", cause=e)
            finally:
                self._active_app_ctx = None
                self._active_app = None
                self._active_fc = None
                self._active_fc_id = None

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


# ---------------------------------------------------------------------------
# Module-level holder function — Modal hydrates this correctly because it's
# at module scope. The decorator is applied dynamically by `create_pod()`
# (via `app.function(...)(_modal_gpu_session_holder)`), not as a normal
# `@app.function` line, so the function itself stays plain.
#
# Body: sleep until cancelled. Modal will bill the L4/A100/H100 for the
# wall-clock the holder is alive. Fabrik destroys the container by cancelling
# the FunctionCall + exiting the app.run() context.
# ---------------------------------------------------------------------------
def _modal_gpu_session_holder() -> dict:
    """Keep a Modal GPU container alive until the FunctionCall is cancelled.

    Modal's per-second billing applies the whole time this function runs.
    Fabrik's ``ModalClient.destroy_pod()`` cancels this call, which raises
    a ``modal.exception.FunctionCallCancelled`` inside the container so it
    exits cleanly. Total cost = (wall_clock_seconds × hourly_rate / 3600).
    """
    import time as _time

    # Max lifetime ceiling = 24h (Modal's hard timeout). Reaper destroys
    # before this for runaway sessions.
    _time.sleep(86400)
    return {"status": "sleep_timeout"}
