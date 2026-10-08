"""T01 — the committed Alloy configs are the converter's output, and both load cleanly.

Plan: docs/development/plans/2026-10-08-plan-1-promtail-to-alloy/T01-alloy-configs.md
Spec: docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md § The delta D1, § Validation V1/V2.

V1 — re-run `alloy convert --source-format=promtail` (grafana/alloy:v1.20.1) on the hub Promtail
config and on the spoke template rendered with fixed values, and diff each output against the
committed Alloy file (the spoke template rendered with the same fixed values). The diff must be
empty, so any hand edit or drift from a future converter version fails this test.
V2 — `alloy run` loads both committed configs (the spoke one rendered) without a config error, in a
container with no network.
Per core/45-testing-strategy.md, this is Chore/Infrastructure-shaped (the configs ARE the
converter's output, nothing to unit-test) but carries a drift guard per the ticket's own Behavior
Contract, and skips with a stated reason rather than passing silently when docker or the pinned
image is unavailable (core/45-testing-strategy.md § skip discipline; the ticket's fourth row).
"""

from __future__ import annotations

import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ALLOY_IMAGE = "grafana/alloy:v1.20.1"

HUB_PROMTAIL = REPO_ROOT / "configs/promtail/promtail-config.yaml"
HUB_ALLOY = REPO_ROOT / "configs/alloy/config.alloy"
SPOKE_PROMTAIL_TEMPLATE = REPO_ROOT / "scripts/bootstrap/templates/promtail.yaml.template"
SPOKE_ALLOY_TEMPLATE = REPO_ROOT / "scripts/bootstrap/templates/alloy.alloy.template"

# Fixed spoke values used only to render both templates for this local proof (spec D1 ran the
# converter "for vps2"); the live render at bootstrap time uses the real mesh IPs per host.
FIXED_SPOKE_VALUES = {
    "SPOKE_NAME": "vps2",
    "SPOKE_MESH_IP": "10.99.0.2",
    "HUB_MESH_IP": "10.99.0.1",
}

_UNSET = object()
_docker_reason: object = _UNSET


def _render(template_text: str, values: dict[str, str]) -> str:
    rendered = template_text
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    return rendered


def _docker_unavailable_reason() -> str | None:
    """None when docker is usable AND the pinned image is cached or pullable; otherwise the
    reason to state in the skip (ticket Behavior Contract row 4)."""
    global _docker_reason
    if _docker_reason is not _UNSET:
        return _docker_reason  # type: ignore[return-value]

    if shutil.which("docker") is None:
        _docker_reason = "docker is not installed on this machine"
        return _docker_reason  # type: ignore[return-value]

    try:
        inspect = subprocess.run(
            ["docker", "image", "inspect", ALLOY_IMAGE],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        _docker_reason = f"docker is not usable: {exc}"
        return _docker_reason  # type: ignore[return-value]

    if inspect.returncode == 0:
        _docker_reason = None
        return None

    try:
        pull = subprocess.run(
            ["docker", "pull", ALLOY_IMAGE],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        _docker_reason = f"{ALLOY_IMAGE} is not cached locally and the pull errored: {exc}"
        return _docker_reason  # type: ignore[return-value]

    if pull.returncode == 0:
        _docker_reason = None
        return None

    _docker_reason = (
        f"{ALLOY_IMAGE} is neither cached locally nor pullable: {pull.stderr.strip()[-300:]}"
    )
    return _docker_reason  # type: ignore[return-value]


@pytest.fixture(autouse=True)
def _require_docker_and_image() -> None:
    reason = _docker_unavailable_reason()
    if reason is not None:
        pytest.skip(reason)


def _convert_promtail(promtail_text: str) -> str:
    """Run `alloy convert --source-format=promtail` in a throwaway, network-less container,
    feeding the Promtail YAML over stdin and reading the Alloy config back over stdout — no
    volume mount, so nothing but the pinned image touches the host."""
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-i",
            "--network",
            "none",
            ALLOY_IMAGE,
            "convert",
            "--source-format=promtail",
            "-",
        ],
        input=promtail_text,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, f"alloy convert failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout


def test_hub_alloy_config_equals_the_converters_output_byte_for_byte() -> None:
    converted = _convert_promtail(HUB_PROMTAIL.read_text())
    assert converted == HUB_ALLOY.read_text()


def test_spoke_alloy_template_rendered_equals_the_converters_output() -> None:
    rendered_promtail = _render(SPOKE_PROMTAIL_TEMPLATE.read_text(), FIXED_SPOKE_VALUES)
    converted = _convert_promtail(rendered_promtail)
    rendered_committed_alloy = _render(SPOKE_ALLOY_TEMPLATE.read_text(), FIXED_SPOKE_VALUES)
    assert converted == rendered_committed_alloy


def _validate_alloy_run(config_text: str, tmp_path: Path, tag: str) -> None:
    """Start the committed config under `alloy run` in a throwaway, network-less container and
    assert it reaches the running state rather than exiting on a config-load error (spec V2)."""
    work = tmp_path / tag
    work.mkdir()
    config_path = work / "config.alloy"
    config_path.write_text(config_text)
    name = f"alloy-validate-{tag}-{uuid.uuid4().hex[:8]}"

    start = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--network",
            "none",
            "--name",
            name,
            "-v",
            f"{config_path}:/etc/alloy/config.alloy:ro",
            ALLOY_IMAGE,
            "run",
            "--server.http.listen-addr=127.0.0.1:12345",
            "--storage.path=/tmp/alloy-data",
            "/etc/alloy/config.alloy",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert start.returncode == 0, f"docker run failed to start: {start.stderr}"

    try:
        deadline = time.monotonic() + 15
        logs = ""
        reached_running = False
        while time.monotonic() < deadline:
            proc = subprocess.run(
                ["docker", "logs", name], capture_output=True, text=True, timeout=10, check=False
            )
            logs = proc.stdout + proc.stderr  # alloy logs to stderr, not stdout
            if "Alloy is running" in logs:
                reached_running = True
                break
            inspect = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", name],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if inspect.stdout.strip() != "true":
                break  # the container exited before reaching the running state
            time.sleep(0.5)
        assert reached_running, f"{tag}: alloy did not reach the running state:\n{logs[-3000:]}"
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True, timeout=15)


def test_hub_alloy_config_loads_under_alloy_run_with_no_network(tmp_path: Path) -> None:
    _validate_alloy_run(HUB_ALLOY.read_text(), tmp_path, "hub")


def test_spoke_alloy_template_rendered_loads_under_alloy_run_with_no_network(
    tmp_path: Path,
) -> None:
    rendered = _render(SPOKE_ALLOY_TEMPLATE.read_text(), FIXED_SPOKE_VALUES)
    _validate_alloy_run(rendered, tmp_path, "spoke")
