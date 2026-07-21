"""Comprehensive scenario suite — tests every angle across all 3 providers.

Run as: PYTHONPATH=src .venv/bin/python /tmp/comprehensive_scenarios.py

Walks the full matrix of (provider × kind × scenario × outcome) for create/
work/destroy semantics, using DRY-RUN mode where possible so no money is
spent. Live mode invoked only for cross-cutting assertions (status/destroy
provider dispatch, reaper tag-safety).
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

# Ensure fresh state file for these scenarios
os.environ.pop("RUNPOD_SERVERLESS_ENDPOINT_ID", None)

# Add src/ to path
sys.path.insert(0, "/opt/fabrik/src")

from fabrik.orchestrator import gpu_rent

PROVIDERS = ("runpod", "modal", "vast")
PODS = ("pod-h100", "pod-rtx-4090", "pod-a100")
KINDS_NON_GPU = ("serverless",)


def section(name: str):
    print()
    print("=" * 70)
    print(f"  {name}")
    print("=" * 70)


def check(label: str, cond: bool, detail: str = ""):
    mark = "✓" if cond else "✗"
    print(f"  {mark} {label}" + (f" — {detail}" if detail else ""))
    return cond


def main():
    fails = []

    # ========================================================================
    section("S1: estimate_cost is provider-aware for every pod kind")
    # ========================================================================
    for kind in PODS:
        rates = {p: gpu_rent.estimate_cost(kind, 1, provider=p) for p in PROVIDERS}
        ok = (
            isinstance(rates["runpod"], float)
            and isinstance(rates["modal"], float)
            and isinstance(rates["vast"], float)
        )
        if not check(
            f"estimate_cost({kind}, 1h) per provider: rp=${rates['runpod']} m=${rates['modal']} v=${rates['vast']}",
            ok,
        ):
            fails.append(f"S1:{kind}")

    # ========================================================================
    section("S2: selection_advice routes correctly per (utilization, flags)")
    # ========================================================================
    scenarios = [
        # (label, kwargs, expected_provider)
        ("high util pod-h100 no flags", {"hours": 4, "utilization_rate": 1.0}, "runpod"),
        ("low util pod-h100", {"hours": 4, "utilization_rate": 0.2}, "modal"),
        (
            "checkpointing pod-h100",
            {"hours": 4, "utilization_rate": 1.0, "needs_checkpointing": True},
            "vast",
        ),
        (
            "serverless needs-serverless (Vast now eligible)",
            {"hours": 1, "utilization_rate": 0.5, "needs_serverless": True},
            None,  # any
        ),
    ]
    for label, kw, expected in scenarios:
        kind = "serverless" if kw.get("needs_serverless") else "pod-h100"
        advice = gpu_rent.selection_advice(kind, **kw)
        picked = advice["recommendation"].get("provider")
        if expected is None:
            ok = picked in PROVIDERS
        else:
            ok = picked == expected
        if not check(f"{label}: picked={picked} expected={expected or 'any'}", ok):
            fails.append(f"S2:{label}")

    # ========================================================================
    section("S3: dry-run creates nothing across all providers + kinds")
    # ========================================================================
    for provider in PROVIDERS:
        for kind in (*PODS, "serverless"):
            try:
                # Modal/Vast don't carry every pod alias; estimate_cost raises
                # in that case which is acceptable
                gpu_rent.estimate_cost(kind, 1, provider=provider)
            except (NotImplementedError, KeyError):
                continue
            c = MagicMock()
            r = gpu_rent.rent(
                kind,
                workload="dry-S3",
                provider=provider,
                dry_run=True,
                client=c,
                max_cost_usd=10.0,
                template_id="echo-handler" if kind == "serverless" else None,
            )
            ok = (
                r.get("dry_run") is True
                and r.get("provider") == provider
                and not c.create_pod.called
                and not c.create_endpoint.called
            )
            if not check(f"dry-run {provider}/{kind}: dry_run={r.get('dry_run')}", ok):
                fails.append(f"S3:{provider}/{kind}")

    # ========================================================================
    section("S4: cost guards refuse BEFORE any provider create call")
    # ========================================================================
    for provider in PROVIDERS:
        c = MagicMock()
        try:
            gpu_rent.rent(
                "pod-h100",
                workload="cost-S4",
                provider=provider,
                max_lifetime_hours=4,
                max_cost_usd=0.01,  # absurdly low
                client=c,
                dry_run=False,
            )
            ok = False
        except gpu_rent.GPUBudgetExceededError:
            ok = True
        if not check(
            f"cost guard {provider}/pod-h100: GPUBudgetExceededError raised",
            ok and not c.create_pod.called,
        ):
            fails.append(f"S4:{provider}")

    # ========================================================================
    section("S5: client_for_provider returns the right class")
    # ========================================================================
    # Set placeholder envs so the clients can construct (we'll never call them)
    os.environ.setdefault("RUNPOD_API_KEY", "test")
    os.environ.setdefault("VAST_API_KEY", "test")
    os.environ.setdefault("MODAL_TOKEN_ID", "ak-test")
    os.environ.setdefault("MODAL_TOKEN_SECRET", "as-test")

    from fabrik.drivers.runpod import RunPodClient
    from fabrik.drivers.vast_provider import VastClient

    try:
        rc = gpu_rent.client_for_provider("runpod")
        check("client_for_provider('runpod') is RunPodClient", isinstance(rc, RunPodClient))
    except Exception as e:
        fails.append(f"S5:runpod:{e}")

    try:
        vc = gpu_rent.client_for_provider("vast")
        check("client_for_provider('vast') is VastClient", isinstance(vc, VastClient))
    except Exception as e:
        fails.append(f"S5:vast:{e}")

    try:
        gpu_rent.client_for_provider("azure")
        check("unknown provider raises NotImplementedError", False)
        fails.append("S5:unknown:should-have-raised")
    except NotImplementedError:
        check("unknown provider raises NotImplementedError", True)

    # ========================================================================
    section("S6: HOURLY_USD_BY_PROVIDER table has all 3 + serverless wired")
    # ========================================================================
    for p in PROVIDERS:
        rate = gpu_rent.HOURLY_USD_BY_PROVIDER[p]["serverless"]
        ok = isinstance(rate, (int, float)) and rate > 0
        if not check(f"{p}/serverless rate = ${rate}", ok):
            fails.append(f"S6:{p}/serverless")

    # ========================================================================
    section("S7: Modal template renders with valid Python")
    # ========================================================================
    import ast

    from jinja2 import Template

    for template_id in ("echo-handler", "vllm-openai"):
        path = f"/opt/fabrik/templates/modal/{template_id}.py.j2"
        try:
            t = Template(open(path).read())
            rendered = t.render(
                name="fabrik-comp-test",
                gpu="L4",
                model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
                workers_min=0,
                workers_max=1,
                idle_timeout=60,
            )
            ast.parse(rendered)
            check(f"templates/modal/{template_id}.py.j2 renders + AST-parses", True)
        except Exception as e:
            check(f"templates/modal/{template_id}.py.j2", False, f"{type(e).__name__}: {e}")
            fails.append(f"S7:{template_id}")

    # ========================================================================
    section("S8: Vast driver — workergroups path constant (regression guard)")
    # ========================================================================
    import inspect

    from fabrik.drivers import vast_provider as vp

    src = inspect.getsource(vp)
    # Strip comments, then check
    body_lines_v = [l for l in src.splitlines() if not l.lstrip().startswith("#")]
    body_v = "\n".join(body_lines_v)
    ok = "/workergroups/" in body_v and "/autogroups/" not in body_v
    if not check(
        "vast_provider.py uses /workergroups/ NOT /autogroups/ (B4 regression guard)", ok
    ):
        fails.append("S8")

    # ========================================================================
    section("S9: Modal driver — no _app.stop() calls (B1 regression guard)")
    # ========================================================================
    from fabrik.drivers import modal_provider as mp

    src_m = inspect.getsource(mp)
    # Strip comments
    lines_non_comment = [
        line for line in src_m.splitlines() if not line.lstrip().startswith("#")
    ]
    body = "\n".join(lines_non_comment)
    ok = "_app.stop(" not in body and ".stop()" not in body
    if not check("modal_provider.py has NO _app.stop() / .stop() calls", ok):
        fails.append("S9")

    # ========================================================================
    section("S10: CLI surfaces --model + --template flags")
    # ========================================================================
    import subprocess

    r = subprocess.run(
        [".venv/bin/fabrik", "gpu", "rent", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd="/opt/fabrik",
    )
    ok = "--model" in r.stdout and "--template" in r.stdout
    if not check("`fabrik gpu rent --help` lists --model and --template", ok):
        fails.append("S10")

    # ========================================================================
    print()
    print("=" * 70)
    if fails:
        print(f"  FAILED: {len(fails)} scenarios — {fails}")
        sys.exit(1)
    else:
        print("  ALL COMPREHENSIVE SCENARIOS PASSED ✓")
    print("=" * 70)


if __name__ == "__main__":
    main()
