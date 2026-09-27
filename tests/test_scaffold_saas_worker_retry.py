"""The saas-skeleton worker retries with jittered, env-tunable backoff (75 §Retry).

The emitted worker imports asyncpg, which the hub venv does not carry, so the pure pieces are
lifted out of the template with ast and run on their own.
"""

from __future__ import annotations

import ast
import os
import random

import pytest
import yaml

import fabrik.scaffold as scaffold

WORKER = scaffold._SAAS_WORKER_PY.replace("__PKG__", "pkg").replace("__NAME__", "probe")
TREE = ast.parse(WORKER)
KNOBS = {"RETRY_BASE_SEC", "RETRY_MAX_SEC"}


def _retry_module(env: dict[str, str]) -> dict:
    keep = []
    for n in TREE.body:
        names = {t.id for t in getattr(n, "targets", []) if isinstance(t, ast.Name)}
        is_knob = bool(names & KNOBS)
        is_function = isinstance(n, ast.FunctionDef) and n.name == "_retry_delay"
        is_guard = isinstance(n, ast.If) and "RETRY_BASE_SEC" in ast.unparse(n.test)
        if is_knob or is_function or is_guard:
            keep.append(n)
    assert len(keep) == 4, [ast.unparse(n)[:60] for n in keep]
    ns: dict = {"os": os, "random": random}
    old = dict(os.environ)
    os.environ.update(env)
    try:
        exec(compile(ast.Module(body=keep, type_ignores=[]), "worker", "exec"), ns)
    finally:
        os.environ.clear()
        os.environ.update(old)
    return ns


def test_the_first_retry_waits_the_base_then_doubles_with_jitter():
    ns = _retry_module({"WORKER_RETRY_BASE_SEC": "5", "WORKER_RETRY_MAX_SEC": "3600"})
    first = {ns["_retry_delay"](1) for _ in range(50)}
    fourth = {ns["_retry_delay"](4) for _ in range(50)}
    assert all(5 <= d <= 10 for d in first), sorted(first)
    assert all(40 <= d <= 80 for d in fourth), sorted(fourth)
    assert len(fourth) > 1, "no jitter: every retry of a burst fires at the same instant"


def test_jitter_survives_the_cap_and_huge_attempt_counts_do_not_overflow():
    ns = _retry_module({"WORKER_RETRY_BASE_SEC": "1", "WORKER_RETRY_MAX_SEC": "10"})
    capped = {ns["_retry_delay"](5000) for _ in range(50)}
    assert all(10 <= d <= 20 for d in capped), sorted(capped)
    assert len(capped) > 1, "at the cap every job of a burst would re-fire together"


@pytest.mark.parametrize(
    ("base", "cap"), [("0", "3600"), ("-5", "3600"), ("10", "5"), ("5", "inf")]
)
def test_a_knob_that_would_disable_backoff_is_refused_at_import(base, cap):
    with pytest.raises(ValueError, match="WORKER_RETRY_BASE_SEC"):
        _retry_module({"WORKER_RETRY_BASE_SEC": base, "WORKER_RETRY_MAX_SEC": cap})


def test_the_failure_path_binds_the_jittered_delay_and_keeps_the_row_budget():
    calls = [
        n
        for n in ast.walk(TREE)
        if isinstance(n, ast.Call)
        and ast.unparse(n.func) == "pool.execute"
        and n.args
        and isinstance(n.args[0], ast.Constant)
        and "make_interval(secs => $4)" in str(n.args[0].value)
    ]
    assert len(calls) == 1, len(calls)
    assert ast.unparse(calls[0].args[4]) == "_retry_delay(attempts)"
    assert "POWER(2" not in WORKER
    terminal = [
        n
        for n in ast.walk(TREE)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "terminal"
    ]
    assert [ast.unparse(n.value) for n in terminal] == ["attempts >= row['max_retries']"]


def test_the_worker_service_reaps_its_children_and_its_knobs_are_documented(tmp_path, monkeypatch):
    monkeypatch.setenv("FABRIK_SCAFFOLD_OFFLINE", "1")
    scaffold.create_project(
        name="wk", description="d", base=tmp_path, project_type="saas-skeleton", generate_spec=False
    )
    services = yaml.safe_load((tmp_path / "wk" / "compose.yaml").read_text())["services"]
    assert services["worker"]["init"] is True
    env = (tmp_path / "wk" / ".env.example").read_text()
    assert "WORKER_RETRY_BASE_SEC" in env and "WORKER_RETRY_MAX_SEC" in env
