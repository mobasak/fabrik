"""Phase 4 (deploy-readiness-gaps): first-class `companion_services`.

A companion is a 2nd compose service that shares the app's image but runs a
different command (scheduler / queue worker for the SAME codebase). It must:
render as an additional service, inherit env + DATABASE_URL/REDIS_URL, override
command/container_name/memory, carry NO Traefik labels, and pass the deployer's
`_validate_compose`. Specs without the field render exactly as before.
"""

from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from fabrik.orchestrator.deployer_ssh import _validate_compose
from fabrik.spec_loader import CompanionService, Spec
from fabrik.template_renderer import TemplateRenderer

BASE = {
    "id": "demo-svc",
    "template": "node-api",
    "domain": "demo.vps1.ocoron.com",
    "shape": {"kind": "service", "is_public": True, "needs_database": True},
    "depends": {"postgres": "demo_db"},
    "env": {"NODE_ENV": "production"},
    "resources": {"memory": "512M", "cpu": "0.5"},
}


def _render(companions: list[dict]) -> dict:
    spec = Spec.model_validate({**BASE, "companion_services": companions})
    compose = TemplateRenderer().render(spec, secrets={}, dry_run=True)["compose.yaml"]
    return yaml.safe_load(compose), compose


# --- model validation -------------------------------------------------------
def test_companion_requires_memory():
    with pytest.raises(ValidationError):
        CompanionService(id="x-sched", command=["node", "s.js"])  # type: ignore[call-arg]


def test_companion_rejects_bad_memory():
    with pytest.raises(ValidationError):
        CompanionService(id="x-sched", command=["node", "s.js"], memory="lots")


def test_companion_rejects_empty_command():
    with pytest.raises(ValidationError):
        CompanionService(id="x-sched", command=[], memory="256M")


def test_companion_rejects_bad_id():
    with pytest.raises(ValidationError):
        CompanionService(id="X_Bad", command=["node", "s.js"], memory="256M")


# --- render -----------------------------------------------------------------
def test_render_emits_two_services():
    doc, _ = _render(
        [{"id": "demo-svc-scheduler", "command": ["node", "dist/scheduler.js"], "memory": "256M"}]
    )
    assert set(doc["services"]) == {"demo-svc", "demo-svc-scheduler"}


def test_multiple_companions_all_render():
    # Regression: jinja strips each partial's trailing newline, so without an
    # explicit separator consecutive companions concatenated ('- fabrik  next:').
    doc, compose = _render(
        [
            {"id": "demo-svc-scheduler", "command": ["node", "sched.js"], "memory": "256M"},
            {"id": "demo-svc-worker", "command": ["node", "worker.js"], "memory": "512M"},
        ]
    )
    assert set(doc["services"]) == {"demo-svc", "demo-svc-scheduler", "demo-svc-worker"}
    assert _validate_compose(compose) == []


def test_companion_overrides_command_and_memory():
    doc, _ = _render(
        [{"id": "demo-svc-scheduler", "command": ["node", "dist/scheduler.js"], "memory": "256M"}]
    )
    sch = doc["services"]["demo-svc-scheduler"]
    assert sch["command"] == ["node", "dist/scheduler.js"]
    assert sch["deploy"]["resources"]["limits"]["memory"] == "256M"
    assert sch["container_name"] == "demo-svc-scheduler"


def test_companion_inherits_db_and_applies_env_override():
    doc, _ = _render(
        [
            {
                "id": "demo-svc-scheduler",
                "command": ["node", "s.js"],
                "memory": "256M",
                "env_overrides": {"ROLE": "scheduler"},
            },
        ]
    )
    env = doc["services"]["demo-svc-scheduler"]["environment"]
    assert any("DATABASE_URL" in e for e in env)
    assert any(e == "ROLE=scheduler" for e in env)


def test_companion_has_no_traefik_labels():
    doc, _ = _render([{"id": "demo-svc-scheduler", "command": ["node", "s.js"], "memory": "256M"}])
    assert "labels" not in doc["services"]["demo-svc-scheduler"]
    assert "labels" in doc["services"]["demo-svc"]  # parent keeps its router


# --- _validate_compose (deployer gate) --------------------------------------
def test_companion_compose_passes_validate():
    _, compose = _render(
        [{"id": "demo-svc-scheduler", "command": ["node", "s.js"], "memory": "256M"}]
    )
    assert _validate_compose(compose) == []


def test_no_companion_is_single_service_and_valid():
    spec = Spec.model_validate(BASE)  # no companion_services
    compose = TemplateRenderer().render(spec, secrets={}, dry_run=True)["compose.yaml"]
    assert list(yaml.safe_load(compose)["services"]) == ["demo-svc"]
    assert _validate_compose(compose) == []
