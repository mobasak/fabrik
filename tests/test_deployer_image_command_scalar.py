"""W-4b977f21: the docker-image deployer emits source.image_command as a safe YAML scalar.

A single-quoted scalar folds a newline to a space and passes DEL / non-BMP raw; the template deploy
path's `TemplateRenderer._compose_str` round-trips every string, so the image path uses it too.
"""

import pytest
import yaml

from fabrik.orchestrator.deployer_ssh import _generate_docker_compose

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
