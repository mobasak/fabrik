"""The scaffold's compose outputs hand the deploy's ``.env`` to the container (W-9ead34bd).

``fabrik apply`` writes the registrar-injected values (DATABASE_URL, REDIS_URL, SENTRY_DSN, the
declared secrets) to ``/opt/<name>/.env``. Compose reads that file on its own only to interpolate
``${VAR}`` inside the compose file; a key reaches the container only through ``env_file`` (or an
``environment:`` entry naming it). Both compose outputs of the scaffolder — ``_write_canonical_compose``
and ``templates/scaffold/docker/compose.yaml.template`` — therefore declare ``.env`` in the long
syntax with ``required: false``: the scaffolder writes no local ``.env``, so the short form would make
``docker compose`` refuse in a fresh checkout, while every deploy path writes the file first.

Input domain: the two compose outputs, a project name, and a ``.env`` that is present (with keys
absent from ``environment:`` and one key a literal ``environment:`` value also sets) or absent. The
docker-backed tests EXECUTE ``docker compose config`` and skip only when docker is not installed;
they run with the environment stripped to PATH/HOME/DOCKER_HOST/DOCKER_CONFIG, because importing ``fabrik`` loads the hub
``.env`` into ``os.environ`` and compose interpolation would read it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from fabrik.scaffold import TEMPLATE_DIR, _write_canonical_compose

NAME = "envfile-probe"
ENV_TEXT = (
    "DATABASE_URL=postgresql://app:pw@postgres-main:5432/envfile_probe\n"
    "REDIS_URL=redis://redis-main:6379/3\n"
    "PORT=9999\n"
    "LOG_LEVEL=DEBUG\n"
)
needs_docker = pytest.mark.skipif(
    shutil.which("docker") is None, reason="docker is not installed on this host"
)


def _canonical(project_dir: Path, **kwargs: object) -> Path:
    _write_canonical_compose(project_dir, NAME, **kwargs)  # type: ignore[arg-type]
    return project_dir / "compose.yaml"


def _template(project_dir: Path) -> Path:
    text = (TEMPLATE_DIR / "docker" / "compose.yaml.template").read_text(encoding="utf-8")
    out = project_dir / "compose.yaml"
    out.write_text(
        text.replace("<project>", NAME).replace("<domain>", f"{NAME}.example.com"), encoding="utf-8"
    )
    return out


OUTPUTS = {"canonical": _canonical, "template": _template}


def _service_env(project_dir: Path) -> dict[str, str]:
    """The app service's resolved ``environment`` as ``docker compose config`` reports it."""
    keep = ("PATH", "HOME", "DOCKER_HOST", "DOCKER_CONFIG")  # rootless docker needs the last two
    stripped = {k: v for k, v in os.environ.items() if k in keep}
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--project-directory",
            str(project_dir),
            "config",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        env=stripped,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["services"][NAME].get("environment", {})


@needs_docker
def test_canonical_compose_delivers_env_keys_to_the_container(tmp_path: Path) -> None:
    _canonical(tmp_path)
    (tmp_path / ".env").write_text(ENV_TEXT, encoding="utf-8")
    env = _service_env(tmp_path)
    assert env.get("DATABASE_URL") == "postgresql://app:pw@postgres-main:5432/envfile_probe"
    assert env.get("REDIS_URL") == "redis://redis-main:6379/3"


@needs_docker
def test_template_compose_delivers_env_keys_to_the_container(tmp_path: Path) -> None:
    _template(tmp_path)
    (tmp_path / ".env").write_text(ENV_TEXT, encoding="utf-8")
    env = _service_env(tmp_path)
    assert env.get("DATABASE_URL") == "postgresql://app:pw@postgres-main:5432/envfile_probe"
    assert env.get("REDIS_URL") == "redis://redis-main:6379/3"


@needs_docker
def test_literal_environment_value_wins_over_env_file(tmp_path: Path) -> None:
    _canonical(tmp_path, port=8000)
    (tmp_path / ".env").write_text(ENV_TEXT, encoding="utf-8")
    env = _service_env(tmp_path)
    # Both literal entries of the canonical compose, each also set (differently) in .env.
    assert env["PORT"] == "8000"
    assert env["LOG_LEVEL"] == "INFO"


@needs_docker
@pytest.mark.parametrize("output", sorted(OUTPUTS))
def test_compose_parses_without_a_local_env_file(tmp_path: Path, output: str) -> None:
    OUTPUTS[output](tmp_path)
    assert not (tmp_path / ".env").exists()
    env = _service_env(tmp_path)
    assert "DATABASE_URL" not in env


@pytest.mark.parametrize(
    ("output", "kwargs"),
    [
        ("canonical", {}),
        (
            "canonical",
            {"with_traefik": False, "healthcheck_kind": "heartbeat"},
        ),
        ("template", {}),
    ],
)
def test_app_service_declares_optional_env_file_and_never_the_owner_file(
    tmp_path: Path, output: str, kwargs: dict[str, object]
) -> None:
    path = _canonical(tmp_path, **kwargs) if output == "canonical" else _template(tmp_path)
    service = yaml.safe_load(path.read_text(encoding="utf-8"))["services"][NAME]
    assert service.get("env_file") == [{"path": ".env", "required": False}]
