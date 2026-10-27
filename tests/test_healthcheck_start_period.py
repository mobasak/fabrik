"""W-3197a125: a compose healthcheck's start_period is always a string, and a spec's own value reaches it.

`Health` had no `start_period` field and ignores unknown keys, so `health.start_period` was Jinja Undefined:
templates guarding it with `if health` rendered an empty `start_period:` (null), which `docker compose config`
refuses, and python-api fell back to 30s over the value seo and youtube declared.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from fabrik.orchestrator.deployer_ssh import _generate_docker_compose, _validate_compose
from fabrik.spec_loader import Health, Spec, load_spec
from fabrik.template_renderer import TemplateRenderer

REPO = Path(__file__).resolve().parent.parent

# Every template whose compose healthcheck reads the spec's health block, with the start period it uses when the
# spec sets none. file-worker and the companion partial hardcode their probe and read no health block.
DEFAULTS = {
    "static-site": "10s",
    "node-api": "30s",
    "chrome-extension": "30s",
    "docusaurus": "40s",
    "python-api": "30s",
    "file-api": "10s",
    "saas-skeleton": "40s",
}


def _start_periods(compose: str) -> dict[str, object]:
    services = yaml.safe_load(compose)["services"]
    return {
        name: svc["healthcheck"].get("start_period")
        for name, svc in services.items()
        if "healthcheck" in svc
    }


def _spec(template: str, health: dict[str, object] | None) -> Spec:
    data: dict[str, object] = {
        "id": "demo-svc",
        "template": template,
        "domain": "demo.vps1.ocoron.com",
        "resources": {"memory": "512M", "cpu": "0.5"},
    }
    if health is not None:
        data["health"] = health
    return Spec.model_validate(data)


def _render(spec: Spec) -> str:
    return TemplateRenderer().render(spec, dry_run=True)["compose.yaml"]


FLEET_SPECS = sorted(
    p
    for p in (REPO / "specs" / "services").glob("*.yaml")
    if (REPO / "templates" / load_spec(p).template / "compose.yaml.j2").exists()
)


def test_the_populations_are_not_empty() -> None:
    assert len(FLEET_SPECS) > 50
    assert all((REPO / "templates" / t / "compose.yaml.j2").exists() for t in DEFAULTS)


@pytest.mark.parametrize("path", FLEET_SPECS, ids=lambda p: p.stem)
def test_every_fleet_spec_renders_a_string_start_period(path: Path) -> None:
    for name, value in _start_periods(_render(load_spec(path))).items():
        assert isinstance(value, str) and value, f"{name}: start_period={value!r}"


@pytest.mark.parametrize("template", sorted(DEFAULTS))
def test_a_declared_start_period_reaches_the_file(template: str) -> None:
    periods = _start_periods(_render(_spec(template, {"start_period": "17s"})))
    assert periods and set(periods.values()) == {"17s"}, periods


@pytest.mark.parametrize("template", sorted(DEFAULTS))
def test_an_omitted_start_period_keeps_the_template_default(template: str) -> None:
    periods = _start_periods(_render(_spec(template, {"path": "/health"})))
    assert periods and set(periods.values()) == {DEFAULTS[template]}, periods


@pytest.mark.parametrize(
    ("health", "want"),
    [({}, "20s"), ({"start_period": None}, "20s"), ({"start_period": "45s"}, "45s")],
)
def test_the_docker_source_compose_honours_start_period(health: dict[str, str], want: str) -> None:
    compose = _generate_docker_compose("my-app", "img:latest", 8000, "", {"health": health})
    assert _start_periods(compose) == {"my-app": want}, compose


@pytest.mark.parametrize("bad", [10, 1.5, True])
def test_a_non_string_start_period_is_refused(bad: object) -> None:
    with pytest.raises(ValidationError):
        Health.model_validate({"start_period": bad})


def _compose_with(healthcheck: dict[str, object]) -> str:
    """A compose file `_validate_compose` passes on every other check."""
    return yaml.safe_dump(
        {
            "services": {
                "app": {
                    "image": "img:1",
                    "container_name": "app",
                    "platform": "linux/amd64",
                    "restart": "unless-stopped",
                    "deploy": {"resources": {"limits": {"memory": "256M"}}},
                    "networks": ["fabrik"],
                    "healthcheck": {"test": ["CMD", "true"], **healthcheck},
                }
            },
            "networks": {"fabrik": {"external": True}},
        }
    )


def test_the_compose_gate_passes_string_durations_and_an_int_retries() -> None:
    hc = {"interval": "30s", "timeout": "5s", "start_period": "10s", "retries": 3}
    assert _validate_compose(_compose_with(hc)) == []


@pytest.mark.parametrize("key", ["interval", "timeout", "start_period", "start_interval"])
@pytest.mark.parametrize("bad", [None, 10, True, ""])
def test_the_compose_gate_refuses_a_non_string_duration(key: str, bad: object) -> None:
    errors = _validate_compose(_compose_with({key: bad}))
    assert any(f"healthcheck.{key}" in e for e in errors), errors
