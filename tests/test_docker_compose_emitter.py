"""Behavior contract for _generate_docker_compose (deployer_ssh.py) — the docker-source compose emitter.

Native-Opus plan re-review (2026-08-28) proved two gaps that made a scratch-image / custom-command service
(Zitadel) undeployable: the emitter DROPPED `source.image_command` (the container ran its default CMD) and
ALWAYS emitted a shell `wget --spider` healthcheck ignoring `health.disabled` (fails on a FROM-scratch image).
These tests pin the fix: image_command is emitted as `command:`, and `health.disabled` omits the healthcheck —
without regressing the evolution-api-style specs that use neither.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pydantic
import pytest

from fabrik.orchestrator.deployer_ssh import _generate_docker_compose
from fabrik.orchestrator.exceptions import ValidationError as ApplyError
from fabrik.orchestrator.validator import SpecValidator
from fabrik.spec_loader import Resources

_IMG = "ghcr.io/zitadel/zitadel:v4.17.1"
_TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


def _render(spec: dict) -> str:
    return _generate_docker_compose("zitadel", _IMG, 8080, "auth.ocoron.com", spec)


def test_image_command_is_emitted_as_compose_command() -> None:
    cmd = 'start-from-init --masterkey "${ZITADEL_MASTERKEY}" --tlsMode external'
    out = _render(
        {
            "source": {"image": _IMG, "image_port": 8080, "image_command": cmd},
            "resources": {"memory": "1G"},
        }
    )
    assert "command:" in out, (
        "source.image_command was dropped — the container runs its default CMD"
    )
    assert "start-from-init" in out and "--tlsMode external" in out, (
        "the command string did not reach the compose"
    )


def test_image_command_with_yaml_special_chars_stays_valid_yaml() -> None:
    import yaml

    # A colon-space or other YAML-special char in the command must not break the emitted compose.
    cmd = "serve --opt a: b --note this#that --key ${K}"
    out = _render(
        {
            "source": {"image": _IMG, "image_port": 8080, "image_command": cmd},
            "resources": {"memory": "1G"},
        }
    )
    parsed = yaml.safe_load(out)  # raises if the command scalar broke the document
    assert parsed["services"]["zitadel"]["command"] == cmd, "single-quoting mangled the command"


def test_health_disabled_omits_the_healthcheck_block() -> None:
    out = _render({"health": {"disabled": True}, "resources": {"memory": "1G"}})
    assert "healthcheck:" not in out, (
        "health.disabled ignored — a shell wget check fails on a scratch image"
    )


def test_no_command_and_wget_healthcheck_when_neither_set() -> None:
    # Regression guard: an evolution-api-style spec (no image_command, no health.disabled) is unchanged —
    # the wget healthcheck stays and no command: line appears.
    out = _render({"resources": {"memory": "512M"}})
    assert "healthcheck:" in out and "wget" in out, (
        "the default wget healthcheck must remain for non-disabled specs"
    )
    assert "\n    command:" not in out, "no command: should be emitted when image_command is unset"


# resources.cpu (W-f01710a0): the emitter wrote only memory, so a docker-sourced service ran with no CPU limit.
# Compose 2.40.3 also reads "0_5" as 5 CPUs, "0" as no limit and "-1" as -1, so the emitter, the apply validator
# and the `Resources` model (the template path) hold one strict grammar. The good values are the box's census.
_GOOD_CPUS = ["0.5", "1.0", "0.1", "4.0", "2", "0.25"]
_BAD_CPUS = ["0_5", "0", "0.0", "-1", ".5", "1e-1", " 0.5", "0.5 ", "", "1.", "01", "１", 0.5, 1, True, None, ["0.5"]]


def _compose_cpus(compose: str, tmp_path: Path) -> float | None:
    """The CPU limit compose itself reads from the emitted file (`docker compose config`), never a text match."""
    if shutil.which("docker") is None:
        pytest.skip("docker compose is not installed")
    path = tmp_path / "compose.yaml"
    path.write_text(compose.replace("    env_file: .env\n", ""))  # no .env beside it in tmp
    out = subprocess.run(
        ["docker", "compose", "-f", str(path), "config", "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    ).stdout
    return json.loads(out)["services"]["zitadel"]["deploy"]["resources"]["limits"].get("cpus")


@pytest.mark.parametrize("cpu", _GOOD_CPUS)
def test_cpu_reaches_compose_limits(cpu: str, tmp_path: Path) -> None:
    out = _render({"resources": {"memory": "1G", "cpu": cpu}})
    assert _compose_cpus(out, tmp_path) == float(cpu), "resources.cpu was dropped — the container runs unlimited"


@pytest.mark.parametrize("resources", [{"memory": "1G"}, None, "1G"])
def test_absent_cpu_takes_the_resources_default(resources: object, tmp_path: Path) -> None:
    out = _render({} if resources is None else {"resources": resources})
    assert _compose_cpus(out, tmp_path) == float(Resources().cpu) == 0.5


@pytest.mark.parametrize("cpu", _BAD_CPUS)
def test_emitter_refuses_out_of_grammar_cpu(cpu: object) -> None:
    with pytest.raises(ValueError, match=r"^resources\.cpu must be") as exc:
        _render({"resources": {"memory": "1G", "cpu": cpu}})
    assert "0_5'" not in str(exc.value).split("(")[0], "the message names the field, never the value"


@pytest.mark.parametrize("cpu", _GOOD_CPUS)
def test_apply_validator_passes_in_grammar_cpu(cpu: str) -> None:
    SpecValidator(templates_dir=_TEMPLATES).validate(_raw_apply_spec(cpu))


@pytest.mark.parametrize("cpu", _BAD_CPUS)
def test_apply_validator_refuses_out_of_grammar_cpu(cpu: object) -> None:
    with pytest.raises(ApplyError, match=r"^resources\.cpu must be") as exc:
        SpecValidator(templates_dir=_TEMPLATES).validate(_raw_apply_spec(cpu))
    assert exc.value.field == "resources.cpu"


def _raw_apply_spec(cpu: object) -> dict:
    return {
        "name": "zitadel",
        "template": "python-api",
        "domain": "auth.ocoron.com",
        "source": {"type": "docker", "image": _IMG, "image_port": 8080},
        "resources": {"memory": "1G", "cpu": cpu},
    }


@pytest.mark.parametrize("cpu", _BAD_CPUS)
def test_resources_model_refuses_out_of_grammar_cpu(cpu: object) -> None:
    assert Resources(cpu="0.25").cpu == "0.25"
    with pytest.raises(pydantic.ValidationError, match=r"resources\.cpu must be"):
        Resources(cpu=cpu)
