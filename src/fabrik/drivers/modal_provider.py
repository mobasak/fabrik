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

import importlib.util
import json
import logging
import os
import subprocess
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
        # Modal SDK 1.x: no `finalized()` method. `get(timeout=0)` raises
        # if the call is still pending, returns the result if complete, or
        # raises FunctionCallCancelled if cancelled. We swallow the
        # "still pending" exception as the RUNNING signal.
        try:
            fc = self._modal.FunctionCall.from_id(pod_id)
        except Exception as e:
            raise ModalError(f"could not resolve Modal call {pod_id}: {e}", cause=e)
        try:
            # timeout=0 → poll without blocking. Raises if pending or done.
            fc.get(timeout=0)
            status = "EXITED"  # returned normally → call completed
        except Exception as e:
            name = type(e).__name__
            if "FunctionCallCancelled" in name or "Cancelled" in name:
                status = "EXITED"
            elif "Timeout" in name or "Pending" in name or "still pending" in str(e).lower():
                status = "RUNNING"
            else:
                # Unknown exception — treat as RUNNING (conservative; the
                # reaper's destroy_pending machinery will retry).
                logger.debug("modal fc.get() returned %s: %s", name, e)
                status = "RUNNING"
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

    # --- Serverless API (Modal's `app.deploy` + `@modal.fastapi_endpoint`) -
    #
    # Phase 3.5 (2026-06-17 plan §3.5): real implementation. Closes B1/B2/B3
    # caught by iteration 2 — Modal 1.5.0 has NO `App.stop()` method and NO
    # `list_apps()` import; we shell out to `modal app stop` / `modal app
    # list --json` instead. See docs/development/plans/2026-06-17-gpu-
    # serverless-phase-3-5-converged.md §1.4.
    def list_endpoints(self) -> list[dict[str, Any]]:
        """List Modal apps via `modal app list --json` (B2 workaround).

        Returns only ACTIVE (non-stopped) apps so the reaper doesn't try
        to destroy already-stopped ones. Synthesizes a FABRIK_SESSION_ID
        env tag from the app description so C4 tag-safety works.
        """
        result = subprocess.run(
            ["modal", "app", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
            env={
                **os.environ,
                "MODAL_TOKEN_ID": self.token_id or "",
                "MODAL_TOKEN_SECRET": self.token_secret or "",
            },
        )
        if result.returncode != 0:
            raise ModalError(
                f"modal app list failed: {result.stderr.strip() or result.stdout.strip()}"
            )
        try:
            apps = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise ModalError(f"modal app list returned non-JSON: {e}") from e
        out: list[dict[str, Any]] = []
        for a in apps:
            if a.get("state") == "stopped":
                continue
            desc = a.get("description") or ""
            env_tag = {}
            if desc.startswith("fabrik-gpu-"):
                # C4 tag-safety: synthesize env so reaper sees Fabrik apps
                env_tag = {"FABRIK_SESSION_ID": desc.rsplit("-", 1)[-1]}
            out.append(
                {
                    "id": a["app_id"],
                    "_provider": "modal",
                    "_app_name": desc,
                    "_state": a.get("state"),
                    "env": env_tag,
                }
            )
        return out

    def get_endpoint(self, endpoint_id: str) -> dict[str, Any]:
        """Look up a Modal endpoint by App name or app_id.

        Modal addresses Apps by name; we accept either form. Uses cached
        info from create_endpoint when available.
        """
        cached = getattr(self, "_endpoint_cache", {}).get(endpoint_id)
        if cached:
            return cached
        # Fallback: list and filter
        for ep in self.list_endpoints():
            if ep["id"] == endpoint_id or ep.get("_app_name") == endpoint_id:
                return ep
        return {"id": endpoint_id, "_provider": "modal"}

    def create_endpoint(
        self,
        *,
        template_id: str,
        name: str,
        gpu_type_ids: list[str] | None = None,
        workers_min: int = 0,
        workers_max: int = 3,
        idle_timeout: int = 60,
        flashboot: bool = True,
        execution_timeout_ms: int = 600_000,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Render Fabrik Modal template → app.deploy() → return endpoint dict.

        Plan §3.5 implementation. ``template_id`` is a Fabrik template name
        (e.g. ``"echo-handler"``, ``"vllm-openai"``) under
        ``/opt/fabrik/templates/modal/<template_id>.py.j2``.

        Returns the endpoint dict with ``_endpoint_url`` populated via
        ``Function.get_web_url()`` (verified live in Modal 1.5.0).
        """
        gpu = (gpu_type_ids or ["L4"])[0]
        rendered_path = self._render_modal_template(
            template_id,
            name=name,
            gpu=gpu,
            model=model or "",
            workers_min=workers_min,
            workers_max=workers_max,
            idle_timeout=idle_timeout,
        )
        # Phase 3.5 iter-2 fix: if anything fails between render and the
        # successful cache-of-rendered-path below, the template tmpfile
        # leaks. Track it and clean up on any error path.
        deploy_succeeded = False
        try:
            # Programmatic deploy. app.deploy() returns immediately
            # (non-blocking — verified in plan §1.1 probe 7).
            spec = importlib.util.spec_from_file_location("_fabrik_modal_app", rendered_path)
            if spec is None or spec.loader is None:
                raise ModalError(f"could not load rendered template {rendered_path}")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if not hasattr(mod, "app"):
                raise ModalError(
                    f"rendered template {rendered_path} has no `app` module-level variable"
                )
            app = mod.app
            try:
                app.deploy(name=name)
            except Exception as e:
                raise ModalError(f"app.deploy({name}) failed: {e}", cause=e) from e
            deploy_succeeded = True
        finally:
            if not deploy_succeeded:
                try:
                    Path(rendered_path).unlink(missing_ok=True)
                except OSError:
                    pass

        # Discover the web endpoint URL via the App's registry. Modal 1.5.0
        # exposes ``app.registered_web_endpoints`` listing all web-exposed
        # function names. Templates may expose either:
        # - a plain @app.function decorated function (e.g. _fabrik_handler)
        # - a class method decorated with @modal.fastapi_endpoint (e.g.
        #   FabrikVLLM.generate)
        # Either way, registered_web_endpoints names the function (key into
        # registered_functions). We grab the URL from get_web_url().
        endpoint_url = None
        try:
            web_eps = (
                list(app.registered_web_endpoints)
                if hasattr(app, "registered_web_endpoints")
                else []
            )
            registered = (
                dict(app.registered_functions) if hasattr(app, "registered_functions") else {}
            )
            logger.info(
                "post-deploy app=%s registered_functions=%s registered_web_endpoints=%s",
                name,
                list(registered.keys()),
                web_eps,
            )
            # After app.deploy(), Functions in registered_functions are
            # hydrated and expose .get_web_url(). For class-based endpoints
            # the key is `ClassName.*` (consolidated Function for the class).
            for fn_key, fn in registered.items():
                try:
                    url = fn.get_web_url()
                    if url:
                        endpoint_url = url
                        logger.info(
                            "resolved endpoint via registered_functions[%s] → %s", fn_key, url
                        )
                        break
                except Exception as e:
                    logger.debug("registered_functions[%s].get_web_url() failed: %s", fn_key, e)
            # For class-based endpoints (web endpoint name like 'ClassName.method'),
            # Modal requires Cls.from_name + instantiation. Function.from_name
            # raises InvalidError on 'ClassName.method' — caught by probe above.
            if not endpoint_url and hasattr(app, "registered_classes"):
                for cls_name in app.registered_classes:
                    try:
                        cls = self._modal.Cls.from_name(name, cls_name)
                        inst = cls()  # required — Modal's enforced pattern
                        # Iterate the class's methods to find one with a URL
                        for ep_name in web_eps:
                            # ep_name format is "ClassName.method_name"
                            if not ep_name.startswith(f"{cls_name}."):
                                continue
                            method_name = ep_name.split(".", 1)[1]
                            method = getattr(inst, method_name, None)
                            if method is None:
                                continue
                            try:
                                url = method.get_web_url()
                                if url:
                                    endpoint_url = url
                                    logger.info("resolved Cls method %s → %s", ep_name, url)
                                    break
                            except Exception as e:
                                logger.debug(
                                    "Cls.from_name(%s).%s.get_web_url() failed: %s",
                                    cls_name,
                                    method_name,
                                    e,
                                )
                        if endpoint_url:
                            break
                    except Exception as e:
                        logger.debug("Cls.from_name(%s, %s) failed: %s", name, cls_name, e)
        except Exception as e:
            logger.warning("registered_functions lookup failed for %s: %s", name, e)
        # Fallback: known function names from Fabrik's two templates
        if not endpoint_url:
            for fn_name in ("_fabrik_handler", "FabrikVLLM.generate", "generate"):
                try:
                    fn = self._modal.Function.from_name(name, fn_name)
                    url = fn.get_web_url()
                    if url:
                        endpoint_url = url
                        logger.info("resolved via fallback (%s) → %s", fn_name, url)
                        break
                except Exception:
                    continue
        if not endpoint_url:
            logger.warning("could not resolve web URL for %s", name)

        ep_info: dict[str, Any] = {
            "id": name,  # Modal Apps are addressed by name
            "_provider": "modal",
            "_app_name": name,
            "_endpoint_url": endpoint_url,
            "_rendered_path": rendered_path,
            "workersMin": workers_min,
            "workersMax": workers_max,
            "idleTimeout": idle_timeout,
            "flashboot": flashboot,
        }
        # Cache for subsequent get_endpoint / run_endpoint_sync calls
        if not hasattr(self, "_endpoint_cache"):
            self._endpoint_cache = {}
        self._endpoint_cache[name] = ep_info
        return ep_info

    def destroy_endpoint(self, endpoint_id: str) -> None:
        """Stop a Modal App via `modal app stop` (B1 workaround — no SDK method).

        Accepts either an app_id (e.g. `ap-...`) or an app name (e.g.
        `fabrik-gpu-...`). The CLI accepts both.
        """
        # --yes required for non-interactive (no TTY in subprocess); without
        # it the CLI prompts "Are you sure?" and aborts on no-input.
        result = subprocess.run(
            ["modal", "app", "stop", "--yes", endpoint_id],
            capture_output=True,
            text=True,
            timeout=60,
            env={
                **os.environ,
                "MODAL_TOKEN_ID": self.token_id or "",
                "MODAL_TOKEN_SECRET": self.token_secret or "",
            },
        )
        if result.returncode != 0:
            # Idempotent semantics: if the app is already stopped or gone,
            # treat as success (mirrors Vast's 404-on-DELETE handling).
            # Modal CLI messages we've seen in the wild:
            #   "App is already stopped. (Stopped at ... by 'mobasak')."
            #   "App not found"
            msg = (result.stderr.strip() or result.stdout.strip()).lower()
            if "already stopped" in msg or "not found" in msg or "no such app" in msg:
                logger.info(
                    "modal app %s already stopped/missing — treating as success",
                    endpoint_id,
                )
            else:
                raise ModalError(
                    f"modal app stop {endpoint_id} failed: "
                    f"{result.stderr.strip() or result.stdout.strip()}"
                )
        # Clean up the cached entry + rendered tempfile
        cache = getattr(self, "_endpoint_cache", {})
        ep = cache.pop(endpoint_id, None)
        if ep and ep.get("_rendered_path"):
            try:
                Path(ep["_rendered_path"]).unlink(missing_ok=True)
            except OSError:
                pass

    # --- Inference plane ---------------------------------------------------
    def run_endpoint_sync(
        self, endpoint_id: str, payload: dict[str, Any], *, timeout: float = 600.0
    ) -> dict[str, Any]:
        """POST to the deployed endpoint URL.

        Modal's @modal.fastapi_endpoint exposes a standard HTTPS surface.
        We do not wrap auth_data — Modal's URL is the auth boundary.
        """
        info = self.get_endpoint(endpoint_id)
        url = info.get("_endpoint_url")
        if not url:
            raise ModalError(
                f"endpoint {endpoint_id!r} has no _endpoint_url; create_endpoint must run first"
            )
        import httpx as _httpx

        resp = _httpx.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def run_endpoint_async(self, endpoint_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(
            "Modal async invocation not yet wired — use run_endpoint_sync. "
            "(Modal's Function.spawn() requires app.run() context which the "
            "deployed endpoint pattern bypasses.)"
        )

    # --- Template rendering helper (private) -------------------------------
    def _render_modal_template(
        self,
        template_id: str,
        *,
        name: str,
        gpu: str,
        model: str,
        workers_min: int,
        workers_max: int,
        idle_timeout: int,
    ) -> str:
        """Render templates/modal/<template_id>.py.j2 → /tmp/fabrik-modal-<name>.py.

        Returns the rendered file path. Caller is responsible for cleanup
        (done in destroy_endpoint via cached _rendered_path).
        """
        try:
            from jinja2 import Template
        except ImportError as e:
            raise ModalError(
                "jinja2 is required for Modal serverless templating; "
                "install via `pip install jinja2`"
            ) from e
        tpl_path = Path("/opt/fabrik/templates/modal") / f"{template_id}.py.j2"
        if not tpl_path.exists():
            raise ModalError(
                f"Modal template {template_id!r} not found at {tpl_path}. "
                f"Available: {sorted(p.stem.removesuffix('.py') for p in tpl_path.parent.glob('*.py.j2'))}"
            )
        rendered = Template(tpl_path.read_text()).render(
            name=name,
            gpu=gpu,
            model=model,
            workers_min=workers_min,
            workers_max=workers_max,
            idle_timeout=idle_timeout,
        )
        out_path = Path(f"/tmp/fabrik-modal-{name}.py")
        out_path.write_text(rendered)
        return str(out_path)

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
