"""Behavior contract for _generate_docker_compose (deployer_ssh.py) — the docker-source compose emitter.

Native-Opus plan re-review (2026-08-28) proved two gaps that made a scratch-image / custom-command service
(Zitadel) undeployable: the emitter DROPPED `source.image_command` (the container ran its default CMD) and
ALWAYS emitted a shell `wget --spider` healthcheck ignoring `health.disabled` (fails on a FROM-scratch image).
These tests pin the fix: image_command is emitted as `command:`, and `health.disabled` omits the healthcheck —
without regressing the evolution-api-style specs that use neither.
"""

from fabrik.orchestrator.deployer_ssh import _generate_docker_compose

_IMG = "ghcr.io/zitadel/zitadel:v4.17.1"


def _render(spec: dict) -> str:
    return _generate_docker_compose("zitadel", _IMG, 8080, "auth.ocoron.com", spec)


def test_image_command_is_emitted_as_compose_command() -> None:
    cmd = 'start-from-init --masterkey "${ZITADEL_MASTERKEY}" --tlsMode external'
    out = _render({"source": {"image": _IMG, "image_port": 8080, "image_command": cmd}, "resources": {"memory": "1G"}})
    assert "command:" in out, "source.image_command was dropped — the container runs its default CMD"
    assert "start-from-init" in out and "--tlsMode external" in out, "the command string did not reach the compose"


def test_image_command_with_yaml_special_chars_stays_valid_yaml() -> None:
    import yaml

    # A colon-space or other YAML-special char in the command must not break the emitted compose.
    cmd = "serve --opt a: b --note this#that --key ${K}"
    out = _render({"source": {"image": _IMG, "image_port": 8080, "image_command": cmd}, "resources": {"memory": "1G"}})
    parsed = yaml.safe_load(out)  # raises if the command scalar broke the document
    assert parsed["services"]["zitadel"]["command"] == cmd, "single-quoting mangled the command"


def test_health_disabled_omits_the_healthcheck_block() -> None:
    out = _render({"health": {"disabled": True}, "resources": {"memory": "1G"}})
    assert "healthcheck:" not in out, "health.disabled ignored — a shell wget check fails on a scratch image"


def test_no_command_and_wget_healthcheck_when_neither_set() -> None:
    # Regression guard: an evolution-api-style spec (no image_command, no health.disabled) is unchanged —
    # the wget healthcheck stays and no command: line appears.
    out = _render({"resources": {"memory": "512M"}})
    assert "healthcheck:" in out and "wget" in out, "the default wget healthcheck must remain for non-disabled specs"
    assert "\n    command:" not in out, "no command: should be emitted when image_command is unset"
