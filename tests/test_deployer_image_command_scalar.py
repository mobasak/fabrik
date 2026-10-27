"""W-4b977f21: the docker-image deployer emits source.image_command as a safe YAML scalar.

A single-quoted scalar folds a newline to a space and passes DEL / non-BMP raw; the template deploy
path's `TemplateRenderer._compose_str` round-trips every string, so the image path uses it too.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.deployer_ssh import SSHDeployer, _generate_docker_compose
from fabrik.orchestrator.exceptions import DeployError

_IMG = "ghcr.io/zitadel/zitadel:v4.17.1"
_ZITADEL = 'start-from-init --masterkey "${ZITADEL_MASTERKEY}" --tlsMode external'


def _command(cmd: str) -> str:
    out = _generate_docker_compose(
        "svc",
        _IMG,
        8080,
        "svc.example.com",
        {"source": {"image": _IMG, "image_port": 8080, "image_command": cmd}},
    )
    return yaml.safe_load(out)["services"]["svc"]["command"]


@pytest.mark.parametrize(
    "cmd",
    [
        "sh -c 'echo a\necho b'",  # newline folds to a space in a single-quoted scalar
        "echo \U0001f600",  # non-BMP
        "echo a\x7fb",  # DEL
        "echo it's # not: a comment",
    ],
)
def test_image_command_round_trips(cmd: str) -> None:
    assert _command(cmd) == cmd


def test_plain_command_unchanged() -> None:
    assert _command(_ZITADEL) == _ZITADEL
    assert _command("--port 80") == "--port 80"


def test_refused_value_raises_like_template_path() -> None:
    with pytest.raises(ValueError, match="NUL"):
        _command("echo a\x00b")


def test_deploy_maps_a_refused_command_to_deploy_error_before_any_ssh() -> None:
    # A spec error reaches the operator as a DeployError, never a traceback (D-1289's mapping).
    ctx = DeploymentContext(spec_path=Path("test.yaml"))
    ctx.spec = {
        "name": "svc",
        "source": {"type": "docker", "image": _IMG, "image_command": "echo a\x00b"},
        "domain": "svc.example.com",
    }
    with patch("fabrik.drivers.ssh.ssh") as mock_ssh:
        with pytest.raises(DeployError, match="image_command: the value contains a NUL byte"):
            SSHDeployer()._deploy_docker(ctx, "svc", ctx.spec["source"], None)
    mock_ssh.assert_not_called()
