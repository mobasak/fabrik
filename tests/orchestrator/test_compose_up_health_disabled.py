"""Behavior contract for `_compose_up` — health.disabled must NOT use `docker compose up --wait`.

`docker compose up -d --wait` REQUIRES a healthcheck: `--wait` waits for containers to become
*healthy*, and a container with NO healthcheck makes it exit rc=1 ("container X has no healthcheck
configured"). A `health.disabled` service (a FROM-scratch image like Zitadel has no in-container
shell/curl for a healthcheck) therefore ALWAYS false-fails the deploy — `deploy()` aborts before the
post-deploy registrars even when the container is running fine (live S3 halt, Zitadel RUN 2, 2026-08-28:
the container served /debug/ready 200 but `up --wait` returned 1, skipping gatus/prometheus/glitchtip).

Fix: for `health.disabled`, run `up -d` (NO --wait) + an external readiness poll that STILL fails a
crash-loop (exited / restarting / RestartCount climbing) — so a genuinely broken container is caught,
not slipped through as a false success.
"""

from unittest.mock import MagicMock, patch

import pytest

from fabrik.orchestrator.deployer_ssh import _compose_up, _health_disabled
from fabrik.orchestrator.exceptions import DeployError


def test_health_disabled_helper() -> None:
    assert _health_disabled({"health": {"disabled": True}}) is True
    assert _health_disabled({"health": {"disabled": False}}) is False
    assert _health_disabled({"health": {}}) is False
    assert _health_disabled({}) is False
    assert _health_disabled({"health": None}) is False


def test_healthchecked_service_uses_wait() -> None:
    ssh = MagicMock(return_value="")
    _compose_up("svc", health_disabled=False, ssh_fn=ssh)
    cmd = ssh.call_args_list[0].args[0]
    assert "up -d --wait" in cmd, "a healthchecked service must keep the --wait behavior"


def test_health_disabled_up_without_wait_and_stable_running_ok() -> None:
    # up -d (no --wait), then inspect returns a stable running state → no raise.
    ssh = MagicMock(side_effect=["", "running 0", "running 0", "running 0", "running 0"])
    with patch("fabrik.orchestrator.deployer_ssh.time.sleep"):
        _compose_up("svc", health_disabled=True, ssh_fn=ssh)
    up_cmd = ssh.call_args_list[0].args[0]
    assert "up -d" in up_cmd and "--wait" not in up_cmd, "health.disabled must NOT use --wait"


def test_health_disabled_crashloop_raises() -> None:
    # container never holds a running state (restarting, RestartCount climbing) → DeployError.
    ssh = MagicMock(
        side_effect=[""] + [f"restarting {i}" for i in range(1, 9)]
    )
    with patch("fabrik.orchestrator.deployer_ssh.time.sleep"):
        with pytest.raises(DeployError):
            _compose_up("svc", health_disabled=True, ssh_fn=ssh)


def test_health_disabled_running_but_restart_climbing_raises() -> None:
    # a subtler crash-loop: status "running" but RestartCount keeps climbing → not stable → raise.
    ssh = MagicMock(side_effect=[""] + [f"running {i}" for i in range(1, 9)])
    with patch("fabrik.orchestrator.deployer_ssh.time.sleep"):
        with pytest.raises(DeployError):
            _compose_up("svc", health_disabled=True, ssh_fn=ssh)
