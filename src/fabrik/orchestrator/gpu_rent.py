"""GPU rental orchestrator — try/finally lifecycle.

Direct port of ``src/fabrik/orchestrator/vultr_drill.drill()`` for GPU rentals.

Public API
==========

- :func:`rent` — one-shot rent. Provisions, optionally runs ``work_fn``,
  always destroys (unless ``keep_warm_after_use`` or ``keep_on_failure``).
- :class:`rented` — context-manager wrapper around :func:`rent`.
- :class:`GPUBudgetExceededError` — raised by ``rent()`` BEFORE any provider
  create call when either the per-call ``--max-cost`` or the daily
  ``MAX_DAILY_GPU_COST`` envelope would be exceeded.
- :func:`write_report` — append a session record to
  ``logs/gpu-rent-history.jsonl`` (parallels ``vultr_drill.write_report``).

State + cost tracking
=====================

Every successful create writes to ``data/gpu-rent-state.json`` via
:mod:`fabrik.orchestrator.gpu_state`. Every session (success or failure)
appends one line to ``logs/gpu-rent-history.jsonl``. Actual cost is recorded
into ``~/.fabrik/ai_usage.db`` via :class:`fabrik.ai.tracker.UsageTracker`
so the daily envelope is enforceable on the NEXT call.

Cost guards (Constraint C2 of the plan)
========================================

Two gates fire BEFORE any provider create call:

1. Per-call: ``estimate_cost(kind, max_lifetime_hours) > max_cost_usd``
2. Daily envelope: ``UsageTracker.today_total(kind='gpu') + estimate >
   MAX_DAILY_GPU_COST`` (default $50, override via env).

Either trip raises :class:`GPUBudgetExceededError`. No provider call has been made.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from fabrik.ai.tracker import UsageTracker
from fabrik.config import FABRIK_ROOT
from fabrik.drivers.runpod import GPU_TYPE_IDS, RunPodClient, RunPodError
from fabrik.orchestrator import gpu_state


# Phase 2 providers — import lazily inside PROVIDERS to avoid hard dep on
# `modal` and `vast` SDK at module-import time.
def _modal_client_factory():
    from fabrik.drivers.modal_provider import ModalClient

    return ModalClient


def _vast_client_factory():
    from fabrik.drivers.vast_provider import VastClient

    return VastClient


# Load .env.sysadmin at import-time so MAX_DAILY_GPU_COST is honored even
# when rent() is called without a pre-constructed client (the cost guards
# fire BEFORE the client init that would otherwise load it).
_SYSADMIN_ENV = Path("/opt/fabrik/.env.sysadmin")
if _SYSADMIN_ENV.exists():
    load_dotenv(_SYSADMIN_ENV)

logger = logging.getLogger(__name__)

GPU_RENT_LOG = FABRIK_ROOT / "logs" / "gpu-rent-history.jsonl"

# Provider registry. Each provider client implements the RunPod-shaped
# interface (create_pod, destroy_pod, wait_for_running, list_pods,
# create_endpoint, destroy_endpoint, billing_*). Lazy factories so
# `modal` and Vast.ai SDK imports don't crash if not installed.
PROVIDERS: dict[str, Any] = {
    "runpod": RunPodClient,
    "modal": _modal_client_factory,  # called when first used: PROVIDERS['modal']()
    "vast": _vast_client_factory,
}


def _get_provider_class(name: str) -> type:
    p = PROVIDERS.get(name)
    if p is None:
        raise NotImplementedError(f"unknown gpu provider {name!r}; valid: {sorted(PROVIDERS)}")
    return p() if callable(p) and not isinstance(p, type) else p


# Cost lookup per (provider, kind). Verified 2026-06-16 from each provider's
# pricing page. Re-verify quarterly. Each cell is hourly USD.
# - RunPod = Secure Cloud (more stable; we default cloud_type=SECURE in driver)
# - Modal = on-demand non-preemptible
# - Vast.ai = on-demand verified (interruptible spot ~50% less, but unstable)
HOURLY_USD_BY_PROVIDER: dict[str, dict[str, float]] = {
    "runpod": {
        "serverless": 0.50,  # rough budget for an idle endpoint
        "pod-h100": 2.89,  # RunPod Secure Cloud H100 SXM
        "pod-h100-pcie": 2.89,
        "pod-h100-nvl": 3.19,
        "pod-a100": 1.49,
        "pod-a100-sxm": 1.49,
        "pod-h200": 4.39,
        "pod-l40s": 0.86,
        "pod-rtx-4090": 0.69,
    },
    "modal": {
        "serverless": 0.50,  # serverless is the default Modal flow anyway
        "pod-h100": 3.95,
        "pod-h100-pcie": 3.95,
        "pod-h100-nvl": 3.95,
        "pod-a100": 2.50,
        "pod-a100-sxm": 2.50,
        "pod-h200": 4.50,
        "pod-l40s": 0.80,
        "pod-rtx-4090": 0.80,  # Modal maps RTX to L4 (no 4090 in catalog)
    },
    "vast": {
        # Vast.ai prices fluctuate; these are typical floor prices
        # (verified-cloud, non-spot). Spot is ~50% lower.
        "serverless": None,  # NOT supported (Vast.ai has no serverless)
        "pod-h100": 2.00,
        "pod-h100-pcie": 1.80,
        "pod-h100-nvl": 2.00,
        "pod-a100": 1.00,
        "pod-a100-sxm": 1.00,
        "pod-h200": 3.00,
        "pod-l40s": 0.60,
        "pod-rtx-4090": 0.40,
    },
}

# Friendly --kind aliases → driver GPU_TYPE_IDS lookup. "serverless" is a
# special case that creates/uses an endpoint instead of a pod.
KINDS_SERVERLESS = frozenset({"serverless"})
KINDS_POD = frozenset(GPU_TYPE_IDS.keys())  # pod-h100, pod-rtx-4090, ...
ALL_KINDS = KINDS_SERVERLESS | KINDS_POD

# Default per-kind hourly cost for the DEFAULT provider (runpod). Kept as a
# convenience for estimate_cost() — providers > 1 use HOURLY_USD_BY_PROVIDER.
HOURLY_USD: dict[str, float] = dict(HOURLY_USD_BY_PROVIDER["runpod"])

# Default image for pod-mode rentals. NVIDIA's public CUDA runtime image is
# always available (vs `runpod/pytorch:*` which RunPod versions and removes).
# Workload-specific images should be passed via the ``image_name`` kwarg.
DEFAULT_POD_IMAGE = "nvidia/cuda:12.4.1-runtime-ubuntu22.04"


class GPUBudgetExceededError(RunPodError):
    """Raised before any provider create call when a cost guard trips."""


# ---------------------------------------------------------------------------
# Cost
# ---------------------------------------------------------------------------


def estimate_cost(
    kind: str, hours: float, gpu_count: int = 1, *, provider: str = "runpod"
) -> float:
    """Estimate the upper-bound cost for a rental of ``kind`` over ``hours``.

    Provider-aware (Phase 2): RunPod / Modal / Vast.ai have different hourly
    rates. Pass ``provider`` to scope the estimate.

    Mirrors ``vultr_drill.estimate_cost``: rounds UP to the whole hour
    (matches RunPod's hourly-billing semantics; Modal/Vast use per-second
    but we estimate conservatively).
    """
    if provider not in HOURLY_USD_BY_PROVIDER:
        raise NotImplementedError(f"unknown gpu provider {provider!r}")
    pricing = HOURLY_USD_BY_PROVIDER[provider]
    if kind not in pricing:
        raise NotImplementedError(f"unknown gpu kind {kind!r}")
    rate = pricing[kind]
    if rate is None:
        raise NotImplementedError(f"provider {provider!r} does not support kind {kind!r}")
    billable_hours = max(1, math.ceil(hours))
    return round(rate * billable_hours * gpu_count, 4)


def selection_advice(
    kind: str,
    *,
    hours: float,
    utilization_rate: float = 1.0,
    needs_checkpointing: bool = False,
    needs_serverless: bool = False,
) -> dict[str, Any]:
    """Compare RunPod / Modal / Vast.ai for a workload + pick the cheapest.

    Encodes the rule (``76-gpu-workers.md``) + Gemini's utilization-rate
    decision framework as code.

    Parameters
    ----------
    kind
        One of the ``--kind`` aliases (``pod-h100``, ``serverless``, ...).
    hours
        Wall-clock duration of the workload.
    utilization_rate
        Fraction of ``hours`` the GPU is ACTIVELY computing (0–1).
        - 1.0 = always working (e.g. continuous training)
        - 0.5 = working half the time (event-driven pipeline)
        - 0.1 = bursty (occasional inference)
    needs_checkpointing
        If True, Vast.ai spot is on the table (cheaper but preemptible —
        needs checkpoint-resume logic in the workload).
    needs_serverless
        If True, only providers offering serverless (RunPod, Modal) are
        considered.

    Returns
    -------
    Dict with per-provider cost estimates + a ``recommendation`` field
    containing the cheapest viable provider for this workload.
    """
    results: dict[str, Any] = {
        "kind": kind,
        "hours": hours,
        "utilization_rate": utilization_rate,
        "providers": {},
    }
    for provider in ("runpod", "modal", "vast"):
        pricing = HOURLY_USD_BY_PROVIDER[provider]
        if kind not in pricing or pricing[kind] is None:
            results["providers"][provider] = {
                "supported": False,
                "reason": "kind not offered by this provider",
            }
            continue
        # Modal bills per-second so utilization_rate actually scales cost.
        # RunPod + Vast bill per-hour (always-on); utilization_rate just
        # tells US whether the user is wasting paid-for cycles.
        rate_hourly = pricing[kind]
        if provider == "modal":
            actual_hours = hours * utilization_rate
            est = round(rate_hourly * actual_hours, 4)
        else:
            # Round up to hour-boundaries
            actual_hours = max(1, math.ceil(hours))
            est = round(rate_hourly * actual_hours, 4)
        results["providers"][provider] = {
            "supported": True,
            "hourly_rate_usd": rate_hourly,
            "estimated_cost_usd": est,
            "billing": "per-hour (rounded up)" if provider != "modal" else "per-second",
        }

    # Eligibility filter
    eligible = {name: data for name, data in results["providers"].items() if data.get("supported")}
    if needs_serverless:
        eligible = {name: data for name, data in eligible.items() if name != "vast"}
    if not needs_checkpointing and "vast" in eligible:
        # Without checkpointing, Vast's spot instability outweighs cost savings.
        # Still listed in eligible — operator can override — but recommendation
        # only picks Vast if checkpointing is explicit.
        pass

    if not eligible:
        results["recommendation"] = {
            "provider": None,
            "reason": "no provider supports this combination of kind + flags",
        }
        return results

    # Choose cheapest eligible
    ranked = sorted(eligible.items(), key=lambda kv: kv[1]["estimated_cost_usd"])
    cheapest_name, cheapest_data = ranked[0]
    rationale_parts = [
        f"cheapest at ${cheapest_data['estimated_cost_usd']:.2f}",
    ]
    # Apply rule-based veto
    if cheapest_name == "vast" and not needs_checkpointing:
        # Skip Vast unless user explicitly asked for it via checkpointing
        for name, data in ranked[1:]:
            if name == "vast":
                continue
            rationale_parts = [
                f"Vast.ai cheapest at ${cheapest_data['estimated_cost_usd']:.2f} but spot "
                f"requires checkpointing (not flagged); falling back to {name} "
                f"at ${data['estimated_cost_usd']:.2f}",
            ]
            cheapest_name, cheapest_data = name, data
            break
    # Modal is preferred when utilization < 0.5 even if not strictly cheapest
    if utilization_rate < 0.5 and "modal" in eligible:
        modal_cost = eligible["modal"]["estimated_cost_usd"]
        if modal_cost <= cheapest_data["estimated_cost_usd"] * 1.2:
            # Within 20% — Modal's per-second billing wins on low-utilization
            cheapest_name = "modal"
            cheapest_data = eligible["modal"]
            rationale_parts = [
                f"low utilization ({utilization_rate:.0%}) — Modal's per-second "
                f"billing wins. Cost ${modal_cost:.2f}.",
            ]

    results["recommendation"] = {
        "provider": cheapest_name,
        "kind": kind,
        "estimated_cost_usd": cheapest_data["estimated_cost_usd"],
        "rationale": "; ".join(rationale_parts),
    }
    return results


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


def write_report(report: dict[str, Any]) -> None:
    """Append one JSON line to the rental history (best-effort)."""
    try:
        GPU_RENT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with GPU_RENT_LOG.open("a") as f:
            f.write(json.dumps(report, sort_keys=True, default=str) + "\n")
    except OSError as e:
        logger.warning("gpu_rent.write_report failed: %s", e)


# ---------------------------------------------------------------------------
# Provisioning helpers (private)
# ---------------------------------------------------------------------------


def _make_session_id(kind: str) -> str:
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"gpu-{kind}-{ts}-{uuid.uuid4().hex[:6]}"


def _fabrik_env_tags(session_id: str, workload: str, max_lifetime_hours: int) -> dict[str, str]:
    """Env vars injected into every Fabrik-rented pod/endpoint.

    These are how the reaper recognises our resources and tells us apart
    from foreign pods on the operator's account (Constraint C4).
    """
    return {
        "FABRIK_PROJECT": "fabrik",
        "FABRIK_WORKLOAD": workload,
        "FABRIK_CREATED_BY": os.environ.get("USER", "unknown"),
        "FABRIK_MAX_LIFETIME_HOURS": str(max_lifetime_hours),
        "FABRIK_SESSION_ID": session_id,
    }


def _resolve_gpu_type_id(kind: str, provider: str) -> str:
    """Translate the friendly ``--kind`` alias to the provider-specific GPU string.

    Each provider names hardware differently:
    - RunPod: ``"NVIDIA GeForce RTX 4090"`` (full marketing name)
    - Vast.ai: ``"RTX 4090"`` (matches their marketplace ``gpu_name`` field)
    - Modal: ``"L4"`` (Modal doesn't sell consumer cards; closest analog)

    Without this translation, passing RunPod's GPU string to Vast.ai's search
    returns zero offers (G-LIVE-5 caught this 2026-06-16).
    """
    if provider == "runpod":
        return GPU_TYPE_IDS[kind]
    if provider == "vast":
        from fabrik.drivers.vast_provider import VAST_GPU_NAMES

        if kind not in VAST_GPU_NAMES:
            raise NotImplementedError(
                f"Vast.ai does not have a mapping for kind {kind!r}; "
                f"valid: {sorted(VAST_GPU_NAMES)}"
            )
        return VAST_GPU_NAMES[kind]
    if provider == "modal":
        from fabrik.drivers.modal_provider import MODAL_GPU_TYPES

        if kind not in MODAL_GPU_TYPES:
            raise NotImplementedError(
                f"Modal does not have a mapping for kind {kind!r}; valid: {sorted(MODAL_GPU_TYPES)}"
            )
        return MODAL_GPU_TYPES[kind]
    raise NotImplementedError(f"unknown provider {provider!r} for kind resolution")


def _create_pod(
    client: Any,
    *,
    session_id: str,
    kind: str,
    workload: str,
    max_lifetime_hours: int,
    image_name: str | None,
    cloud_type: str,
    interruptible: bool,
    provider: str = "runpod",
    report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a pod and wait for it to reach RUNNING.

    Records ``report["resource_id"]`` AS SOON AS the pod ID is known so the
    outer ``rent()`` try/finally can clean up even if ``wait_for_running``
    raises (poll-trap, timeout, etc). Without this, a failed-during-wait
    instance is orphaned and bills until manually destroyed — G-LIVE-5
    caught this on Vast on 2026-06-16 (instance 41228973).
    """
    gpu_type_id = _resolve_gpu_type_id(kind, provider)
    image = image_name or DEFAULT_POD_IMAGE
    pod = client.create_pod(
        gpu_type_id=gpu_type_id,
        image_name=image,
        env=_fabrik_env_tags(session_id, workload, max_lifetime_hours),
        cloud_type=cloud_type,
        interruptible=interruptible,
        name=f"fabrik-{session_id}",
    )
    pod_id = pod["id"]
    # Record pod_id NOW (before wait_for_running) so the finally block in
    # rent() can destroy on wait failure — this closes the orphan-pod gap.
    if report is not None:
        report["resource_id"] = pod_id
    # Vast.ai needs longer than RunPod (marketplace hosts have slower image
    # pulls than RunPod's pre-cached registry). 180s is generous for cached
    # images, tight enough that a stuck host doesn't burn $0.10+ before bail.
    wait_timeout = 180 if provider == "vast" else 300
    ready = client.wait_for_running(pod_id, timeout=wait_timeout, interval=5)
    return ready


def _create_serverless_endpoint(
    client: Any,
    *,
    session_id: str,
    workload: str,
    max_lifetime_hours: int,
    template_id: str | None,
    workers_min: int,
    workers_max: int,
    idle_timeout: int,
    flashboot: bool,
) -> dict[str, Any]:
    """Create a serverless endpoint, OR reuse an existing endpoint pinned by
    ``RUNPOD_SERVERLESS_ENDPOINT_ID``.

    Reuse path (Phase 1 default): if ``RUNPOD_SERVERLESS_ENDPOINT_ID`` is set
    in the operator's env, we DO NOT create a new endpoint. We return the
    existing endpoint's metadata. The session is still tracked but the
    "destroy" step is a no-op (endpoint persists for the next session, which
    matches RunPod's scale-to-zero design — endpoints cost $0 when idle).

    Create path: if no env pin and ``template_id`` is provided, create a new
    endpoint via ``POST /v1/endpoints``.
    """
    pinned_id = os.environ.get("RUNPOD_SERVERLESS_ENDPOINT_ID")
    if pinned_id:
        ep = client.get_endpoint(pinned_id)
        # Annotate the returned object with a marker so the destroy path knows
        # to skip the API call for this rental.
        ep["_fabrik_reuse"] = True
        ep["_fabrik_session_id"] = session_id
        return ep
    if not template_id:
        raise GPUBudgetExceededError(
            "serverless requires either RUNPOD_SERVERLESS_ENDPOINT_ID (reuse "
            "pinned endpoint) or template_id (create a new endpoint). Neither set."
        )
    ep = client.create_endpoint(
        template_id=template_id,
        name=f"fabrik-{session_id}",
        workers_min=workers_min,
        workers_max=workers_max,
        idle_timeout=idle_timeout,
        flashboot=flashboot,
    )
    ep["_fabrik_reuse"] = False
    return ep


def _destroy(
    client: Any,
    *,
    resource_type: str,
    resource_id: str,
    reuse: bool,
) -> None:
    """Destroy a pod or endpoint. No-op for reused endpoints."""
    if reuse:
        logger.info("gpu_rent._destroy: skipping (reused endpoint %s)", resource_id)
        return
    if resource_type == "pod":
        client.destroy_pod(resource_id)
    elif resource_type == "endpoint":
        client.destroy_endpoint(resource_id)
    else:
        raise ValueError(f"unknown resource_type {resource_type!r}")


def _record_actual_cost(
    tracker: UsageTracker,
    *,
    session_id: str,
    kind: str,
    workload: str,
    provider: str,
    wall_clock_seconds: float,
    cost_actual_usd: float,
) -> None:
    """Record the actual cost to the usage tracker + the state file."""
    try:
        tracker.record_gpu(
            session_id=session_id,
            kind=kind,
            workload=workload,
            cost_usd=cost_actual_usd,
            duration_seconds=wall_clock_seconds,
            provider=provider,
        )
    except Exception:
        logger.exception("gpu_rent: failed to record GPU cost in tracker")
    try:
        gpu_state.record_actual_cost(session_id, cost_actual_usd)
    except Exception:
        logger.exception("gpu_rent: failed to record actual cost in state")


def _compute_actual_cost(kind: str, wall_clock_seconds: float, *, reused: bool) -> float:
    """Cost actually consumed by the session.

    For pods: hourly rate * (wall_clock / 3600), no rounding.
    For reused serverless endpoints: $0 — the endpoint persists scale-to-zero,
    we didn't pay for the rental session itself (per-request billing happens
    via RunPod's own metering, not our control plane).
    For created serverless endpoints: also $0 for the session (they bill
    per-request); the cost shows up only when requests fire.
    """
    if kind == "serverless":
        return 0.0
    if kind not in HOURLY_USD:
        return 0.0
    return round(HOURLY_USD[kind] * (wall_clock_seconds / 3600.0), 6)


# ---------------------------------------------------------------------------
# Public API: rent()
# ---------------------------------------------------------------------------


def rent(
    kind: str,
    *,
    workload: str,
    provider: str = "runpod",
    max_lifetime_hours: int = 1,
    max_cost_usd: float = 5.0,
    keep_on_failure: bool = False,
    keep_warm_after_use: bool = False,
    work_fn: Callable[[dict[str, Any]], Any] | None = None,
    client: Any = None,
    dry_run: bool = False,
    # Pod-mode overrides:
    image_name: str | None = None,
    cloud_type: str = "SECURE",
    interruptible: bool = False,
    # Serverless overrides:
    template_id: str | None = None,
    workers_min: int = 0,
    workers_max: int = 3,
    idle_timeout: int = 5,
    flashboot: bool = True,
) -> dict[str, Any]:
    """Provision a GPU, optionally run ``work_fn``, ALWAYS destroy.

    Direct port of ``vultr_drill.drill()`` shape:

    - Validates ``kind`` upfront → raises ``NotImplementedError``.
    - Cost guards fire BEFORE provider create call.
    - ``dry_run=True`` returns a plan dict, no API call made.
    - Always writes a JSON-line audit entry to ``logs/gpu-rent-history.jsonl``.
    - Records actual cost into ``~/.fabrik/ai_usage.db`` via UsageTracker.

    Parameters
    ----------
    kind
        ``"serverless"`` or one of the pod aliases (``"pod-h100"``,
        ``"pod-rtx-4090"``, etc.). See :data:`ALL_KINDS`.
    workload
        Free-text tag — required, used for cost rollups + reaper visibility.
    max_lifetime_hours
        Reaper destroys the resource if it's still alive past this point.
    max_cost_usd
        Per-call budget. Refuses BEFORE any provider call if
        ``estimate_cost(kind, max_lifetime_hours) > max_cost_usd``.
    keep_on_failure
        On exception during ``work_fn``, leave the resource alive for
        operator inspection. Mirrors ``vultr_drill --keep-on-failure``.
    keep_warm_after_use
        On successful completion, leave the resource alive (operator owns
        cleanup). Default: destroy after work_fn.
    work_fn
        Called as ``work_fn(resource_dict)`` once the resource is RUNNING.
        ``resource_dict`` is the full provider response (Pod or Endpoint).
    """
    if kind not in ALL_KINDS:
        raise NotImplementedError(f"unknown gpu kind {kind!r}; valid: {sorted(ALL_KINDS)}")
    if provider not in PROVIDERS:
        raise NotImplementedError(f"unknown gpu provider {provider!r}; valid: {sorted(PROVIDERS)}")

    # --- Cost guards (FIRE BEFORE PROVIDER CALL) -----------------------
    est = estimate_cost(kind, max_lifetime_hours, provider=provider)
    if est > max_cost_usd:
        raise GPUBudgetExceededError(
            f"estimated cost ${est} exceeds --max-cost ${max_cost_usd} (kind {kind})"
        )
    daily_cap_raw = os.environ.get("MAX_DAILY_GPU_COST", "50")
    try:
        daily_cap = float(daily_cap_raw)
    except (TypeError, ValueError):
        daily_cap = 50.0
    tracker = UsageTracker()
    today_gpu_spend = tracker.today_total(kind="gpu")
    if today_gpu_spend + est > daily_cap:
        raise GPUBudgetExceededError(
            f"daily GPU spend ${today_gpu_spend:.2f} + estimate ${est:.2f} "
            f"would exceed MAX_DAILY_GPU_COST=${daily_cap:.2f}"
        )

    # --- Identifiers + dry-run early return ----------------------------
    ts = datetime.now(UTC)
    session_id = _make_session_id(kind)

    if dry_run:
        return {
            "dry_run": True,
            "session_id": session_id,
            "kind": kind,
            "workload": workload,
            "provider": provider,
            "max_lifetime_hours": max_lifetime_hours,
            "cost_estimate_usd": est,
            "today_gpu_spend": today_gpu_spend,
            "daily_cap": daily_cap,
        }

    # --- Build report skeleton (filled in throughout try/finally) ------
    report: dict[str, Any] = {
        "ts": int(ts.timestamp()),
        "ts_iso": ts.isoformat(),
        "session_id": session_id,
        "kind": kind,
        "workload": workload,
        "provider": provider,
        "max_lifetime_hours": max_lifetime_hours,
        "resource_type": "endpoint" if kind == "serverless" else "pod",
        "resource_id": None,
        "gpu_type_id": GPU_TYPE_IDS.get(kind),
        "success": False,
        "cost_estimate_usd": est,
        "cost_actual_usd": None,
        "wall_clock_seconds": 0.0,
        "started_at": ts.isoformat(),
        "ended_at": None,
        "checks": {},
        "error": None,
    }

    # --- Try/finally lifecycle -----------------------------------------
    if client is None:
        cls = _get_provider_class(provider)
        client = cls()
    resource: dict[str, Any] | None = None
    failed = False
    start = time.monotonic()
    try:
        if kind == "serverless":
            resource = _create_serverless_endpoint(
                client,
                session_id=session_id,
                workload=workload,
                max_lifetime_hours=max_lifetime_hours,
                template_id=template_id,
                workers_min=workers_min,
                workers_max=workers_max,
                idle_timeout=idle_timeout,
                flashboot=flashboot,
            )
        else:
            resource = _create_pod(
                client,
                session_id=session_id,
                kind=kind,
                workload=workload,
                max_lifetime_hours=max_lifetime_hours,
                image_name=image_name,
                cloud_type=cloud_type,
                interruptible=interruptible,
                provider=provider,
                report=report,
            )
        report["resource_id"] = resource["id"]
        report["checks"]["created"] = True

        # Persist to state file
        gpu_state.upsert(
            session_id,
            provider=provider,
            kind=kind,
            workload=workload,
            resource_type=report["resource_type"],
            resource_id=resource["id"],
            gpu_type_id=report["gpu_type_id"],
            max_lifetime_hours=max_lifetime_hours,
            cost_estimate_usd=est,
        )

        # User-provided work
        if work_fn is not None:
            try:
                work_fn(resource)
                report["checks"]["work_fn"] = "ok"
            except Exception as work_exc:
                report["checks"]["work_fn"] = f"failed: {work_exc!r}"
                raise
        report["success"] = True
    except RunPodError as e:
        failed = True
        report["error"] = str(e)
        logger.warning("gpu_rent %s failed (RunPodError): %s", session_id, e)
    except Exception as e:  # noqa: BLE001
        failed = True
        report["error"] = repr(e)
        logger.warning("gpu_rent %s failed: %s", session_id, e)
    finally:
        wall = round(time.monotonic() - start, 1)
        report["wall_clock_seconds"] = wall

        # Cost actually consumed
        reuse_flag = bool(resource and resource.get("_fabrik_reuse"))
        cost_actual = _compute_actual_cost(kind, wall, reused=reuse_flag)
        report["cost_actual_usd"] = cost_actual
        report["reused_endpoint"] = reuse_flag

        # Decide whether to keep the resource alive.
        # CRITICAL: if create_pod succeeded but wait_for_running raised
        # (poll-trap, timeout), resource is None BUT report["resource_id"]
        # is recorded. Use the recorded ID to destroy — otherwise the pod
        # is orphaned and bills until manually destroyed (G-LIVE-5 bug).
        keep = (failed and keep_on_failure) or (report["success"] and keep_warm_after_use)
        destroy_id = (resource or {}).get("id") or report.get("resource_id")
        if destroy_id and not keep:
            try:
                _destroy(
                    client,
                    resource_type=report["resource_type"],
                    resource_id=destroy_id,
                    reuse=reuse_flag,
                )
                if reuse_flag:
                    report["checks"]["destroyed"] = "skipped_reused"
                    gpu_state.mark_destroyed(session_id, cost_actual_usd=cost_actual)
                else:
                    gpu_state.mark_destroyed(session_id, cost_actual_usd=cost_actual)
                    report["checks"]["destroyed"] = True
            except Exception as e:  # noqa: BLE001
                # Catch ALL provider errors (RunPodError, VastError, ModalError)
                # — never let destroy failures escape the finally block.
                logger.exception("gpu_rent destroy failed for %s", session_id)
                report["checks"]["destroyed"] = False
                report["checks"]["destroy_error"] = repr(e)
                gpu_state.mark_destroy_pending(session_id)
        elif keep and destroy_id:
            report["checks"]["kept_for_inspection"] = True

        report["ended_at"] = datetime.now(UTC).isoformat()
        write_report(report)

        if resource is not None and cost_actual > 0:
            _record_actual_cost(
                tracker,
                session_id=session_id,
                kind=kind,
                workload=workload,
                provider=provider,
                wall_clock_seconds=wall,
                cost_actual_usd=cost_actual,
            )

    return report


# ---------------------------------------------------------------------------
# Public API: rented() context manager
# ---------------------------------------------------------------------------


@contextmanager
def rented(
    kind: str,
    *,
    workload: str,
    provider: str = "runpod",
    max_lifetime_hours: int = 1,
    max_cost_usd: float = 5.0,
    keep_on_failure: bool = False,
    keep_warm_after_use: bool = False,
    client: Any = None,
    image_name: str | None = None,
    cloud_type: str = "SECURE",
    interruptible: bool = False,
    template_id: str | None = None,
    workers_min: int = 0,
    workers_max: int = 3,
    idle_timeout: int = 5,
    flashboot: bool = True,
) -> Iterator[dict[str, Any]]:
    """Context-manager wrapper.

    Usage::

        from fabrik.orchestrator.gpu_rent import rented

        with rented("pod-h100", workload="train", max_lifetime_hours=4) as pod:
            ssh_into(pod["publicIp"])
            run_training_job(pod)
        # Pod auto-destroyed at exit (success or exception).

    Implementation note: this is NOT a thin wrapper around :func:`rent` —
    rent() requires a callback (``work_fn``) which doesn't fit the with-block
    style. Instead, ``rented()`` duplicates the try/finally lifecycle here
    (smaller scope: no work_fn callback, but otherwise identical guards).
    """
    if kind not in ALL_KINDS:
        raise NotImplementedError(f"unknown gpu kind {kind!r}; valid: {sorted(ALL_KINDS)}")
    if provider not in PROVIDERS:
        raise NotImplementedError(f"unknown gpu provider {provider!r}")

    # Cost guards (same as rent())
    est = estimate_cost(kind, max_lifetime_hours)
    if est > max_cost_usd:
        raise GPUBudgetExceededError(
            f"estimated cost ${est} exceeds --max-cost ${max_cost_usd} (kind {kind})"
        )
    try:
        daily_cap = float(os.environ.get("MAX_DAILY_GPU_COST", "50"))
    except (TypeError, ValueError):
        daily_cap = 50.0
    tracker = UsageTracker()
    today_gpu_spend = tracker.today_total(kind="gpu")
    if today_gpu_spend + est > daily_cap:
        raise GPUBudgetExceededError(
            f"daily GPU spend ${today_gpu_spend:.2f} + estimate ${est:.2f} "
            f"would exceed MAX_DAILY_GPU_COST=${daily_cap:.2f}"
        )

    ts = datetime.now(UTC)
    session_id = _make_session_id(kind)
    resource_type = "endpoint" if kind == "serverless" else "pod"
    if client is None:
        cls = _get_provider_class(provider)
        client = cls()
    resource: dict[str, Any] | None = None
    failed = False
    start = time.monotonic()
    report: dict[str, Any] = {
        "ts": int(ts.timestamp()),
        "ts_iso": ts.isoformat(),
        "session_id": session_id,
        "kind": kind,
        "workload": workload,
        "provider": provider,
        "resource_type": resource_type,
        "resource_id": None,
        "gpu_type_id": GPU_TYPE_IDS.get(kind),
        "max_lifetime_hours": max_lifetime_hours,
        "cost_estimate_usd": est,
        "cost_actual_usd": None,
        "wall_clock_seconds": 0.0,
        "started_at": ts.isoformat(),
        "ended_at": None,
        "success": False,
        "checks": {},
        "error": None,
    }
    try:
        if kind == "serverless":
            resource = _create_serverless_endpoint(
                client,
                session_id=session_id,
                workload=workload,
                max_lifetime_hours=max_lifetime_hours,
                template_id=template_id,
                workers_min=workers_min,
                workers_max=workers_max,
                idle_timeout=idle_timeout,
                flashboot=flashboot,
            )
        else:
            resource = _create_pod(
                client,
                session_id=session_id,
                kind=kind,
                workload=workload,
                max_lifetime_hours=max_lifetime_hours,
                image_name=image_name,
                cloud_type=cloud_type,
                interruptible=interruptible,
                provider=provider,
                report=report,
            )
        report["resource_id"] = resource["id"]
        report["checks"]["created"] = True
        gpu_state.upsert(
            session_id,
            provider=provider,
            kind=kind,
            workload=workload,
            resource_type=resource_type,
            resource_id=resource["id"],
            gpu_type_id=report["gpu_type_id"],
            max_lifetime_hours=max_lifetime_hours,
            cost_estimate_usd=est,
        )
        yield resource
        report["success"] = True
    except Exception as e:
        failed = True
        report["error"] = repr(e)
        raise
    finally:
        wall = round(time.monotonic() - start, 1)
        report["wall_clock_seconds"] = wall
        reuse_flag = bool(resource and resource.get("_fabrik_reuse"))
        cost_actual = _compute_actual_cost(kind, wall, reused=reuse_flag)
        report["cost_actual_usd"] = cost_actual
        report["reused_endpoint"] = reuse_flag

        keep = (failed and keep_on_failure) or (report["success"] and keep_warm_after_use)
        if resource is not None and not keep:
            try:
                _destroy(
                    client,
                    resource_type=resource_type,
                    resource_id=resource["id"],
                    reuse=reuse_flag,
                )
                gpu_state.mark_destroyed(session_id, cost_actual_usd=cost_actual)
                report["checks"]["destroyed"] = "skipped_reused" if reuse_flag else True
            except RunPodError as e:
                logger.exception("rented() destroy failed for %s", session_id)
                report["checks"]["destroyed"] = False
                report["checks"]["destroy_error"] = str(e)
                gpu_state.mark_destroy_pending(session_id)
        elif keep and resource is not None:
            report["checks"]["kept_for_inspection"] = True

        report["ended_at"] = datetime.now(UTC).isoformat()
        write_report(report)
        if resource is not None and cost_actual > 0:
            _record_actual_cost(
                tracker,
                session_id=session_id,
                kind=kind,
                workload=workload,
                provider=provider,
                wall_clock_seconds=wall,
                cost_actual_usd=cost_actual,
            )
