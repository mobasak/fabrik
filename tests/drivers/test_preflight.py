"""Unit tests for fabrik.drivers.preflight — mocked subprocess and ssh, no VPS required.

Covers the three Phase 4b pre-deploy checks:
* :func:`verify_architecture` — pure YAML validation
* :func:`verify_dns_before_deployment` — VPS getent + public dig polling
* :func:`restart_traefik_and_wait` — docker restart + API poll

All tests run offline by patching :func:`fabrik.drivers.ssh.ssh` where used
inside :mod:`fabrik.drivers.preflight` and :func:`subprocess.run` for the
local ``dig`` call. No network or SSH hop is made.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from fabrik.drivers import preflight
from fabrik.drivers.preflight import (
    DEFAULT_VPS_IP,
    PUBLIC_DNS_RESOLVER,
    restart_traefik_and_wait,
    verify_architecture,
    verify_dns_before_deployment,
)

# --------------------------------------------------------------------------- #
# verify_architecture                                                          #
# --------------------------------------------------------------------------- #


class TestVerifyArchitecture:
    def test_single_service_with_amd64_passes(self):
        compose = """
services:
  app:
    image: nginx
    platform: linux/amd64
"""
        verify_architecture(compose)  # does not raise

    def test_multiple_services_all_amd64_passes(self):
        compose = """
services:
  web:
    image: nginx
    platform: linux/amd64
  worker:
    image: python:3.12-slim-bookworm
    platform: linux/amd64
"""
        verify_architecture(compose)

    def test_missing_platform_raises_runtime_error(self):
        compose = """
services:
  app:
    image: nginx
"""
        with pytest.raises(RuntimeError, match="linux/amd64") as exc:
            verify_architecture(compose)
        assert "'app'" in str(exc.value)

    def test_wrong_platform_raises_runtime_error(self):
        compose = """
services:
  app:
    image: nginx
    platform: linux/arm64
"""
        with pytest.raises(RuntimeError, match="linux/amd64"):
            verify_architecture(compose)

    def test_mixed_services_reports_only_offenders(self):
        compose = """
services:
  good:
    image: nginx
    platform: linux/amd64
  bad_one:
    image: nginx
  bad_two:
    image: nginx
    platform: linux/arm64
"""
        with pytest.raises(RuntimeError) as exc:
            verify_architecture(compose)
        msg = str(exc.value)
        assert "bad_one" in msg
        assert "bad_two" in msg
        assert "good" not in msg

    def test_invalid_yaml_raises_value_error(self):
        with pytest.raises(ValueError, match="not valid YAML"):
            verify_architecture("services:\n  app:\n  - bad: [unclosed")

    def test_non_mapping_top_level_raises_value_error(self):
        with pytest.raises(ValueError, match="mapping at the top level"):
            verify_architecture("- just-a-list\n- items")

    def test_empty_services_raises_value_error(self):
        with pytest.raises(ValueError, match="no 'services' mapping"):
            verify_architecture("services: {}\n")

    def test_no_services_key_raises_value_error(self):
        with pytest.raises(ValueError, match="no 'services' mapping"):
            verify_architecture("version: '3'\nnetworks:\n  default: {}\n")

    def test_service_with_non_dict_body_is_flagged(self):
        compose = """
services:
  app: null
"""
        with pytest.raises(RuntimeError, match="app"):
            verify_architecture(compose)


# --------------------------------------------------------------------------- #
# verify_dns_before_deployment                                                 #
# --------------------------------------------------------------------------- #


class TestVerifyDnsBeforeDeployment:
    def test_dry_run_does_not_invoke_resolvers(self):
        with (
            patch.object(preflight, "ssh") as mock_ssh,
            patch("subprocess.run") as mock_run,
        ):
            verify_dns_before_deployment("example.vps1.ocoron.com", dry_run=True)
            mock_ssh.assert_not_called()
            mock_run.assert_not_called()

    def test_both_resolvers_agree_on_first_try_returns_none(self):
        # VPS getent hosts returns "<ip> <fqdn>\n"
        # dig +short returns "<ip>\n"
        with (
            patch.object(
                preflight,
                "ssh",
                return_value=f"{DEFAULT_VPS_IP}  example.vps1.ocoron.com",
            ) as mock_ssh,
            patch(
                "subprocess.run",
                return_value=MagicMock(returncode=0, stdout=f"{DEFAULT_VPS_IP}\n", stderr=""),
            ) as mock_run,
        ):
            verify_dns_before_deployment("example.vps1.ocoron.com", timeout=5)
            mock_ssh.assert_called_once()
            mock_run.assert_called_once()

    def test_calls_dig_with_public_resolver(self):
        with (
            patch.object(
                preflight, "ssh", return_value=f"{DEFAULT_VPS_IP}  example.vps1.ocoron.com"
            ),
            patch(
                "subprocess.run",
                return_value=MagicMock(returncode=0, stdout=f"{DEFAULT_VPS_IP}\n", stderr=""),
            ) as mock_run,
        ):
            verify_dns_before_deployment("example.vps1.ocoron.com", timeout=5)
            args = mock_run.call_args.args[0]
            assert args[:3] == ["dig", "+short", "example.vps1.ocoron.com"]
            assert args[3] == f"@{PUBLIC_DNS_RESOLVER}"

    def test_vps_returns_wrong_ip_times_out(self):
        # VPS claims a different IP; public side is fine
        with (
            patch.object(
                preflight,
                "ssh",
                return_value="10.0.0.1  example.vps1.ocoron.com",
            ),
            patch(
                "subprocess.run",
                return_value=MagicMock(returncode=0, stdout=f"{DEFAULT_VPS_IP}\n", stderr=""),
            ),
            patch("time.sleep"),  # don't actually sleep
        ):
            with pytest.raises(TimeoutError, match="VPS resolver"):
                verify_dns_before_deployment(
                    "example.vps1.ocoron.com", timeout=1, poll_interval=0.1
                )

    def test_public_returns_wrong_ip_times_out(self):
        with (
            patch.object(
                preflight,
                "ssh",
                return_value=f"{DEFAULT_VPS_IP}  example.vps1.ocoron.com",
            ),
            patch(
                "subprocess.run",
                return_value=MagicMock(returncode=0, stdout="10.0.0.1\n", stderr=""),
            ),
            patch("time.sleep"),
        ):
            with pytest.raises(TimeoutError, match="public resolver"):
                verify_dns_before_deployment(
                    "example.vps1.ocoron.com", timeout=1, poll_interval=0.1
                )

    def test_ssh_runtime_error_is_treated_as_not_yet_resolving(self):
        """If getent fails (exit 2 = not found), retry loop should continue."""
        calls = {"n": 0}

        def flaky_ssh(_cmd, timeout=5):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("getent exit 2")
            return f"{DEFAULT_VPS_IP}  example.vps1.ocoron.com"

        with (
            patch.object(preflight, "ssh", side_effect=flaky_ssh),
            patch(
                "subprocess.run",
                return_value=MagicMock(returncode=0, stdout=f"{DEFAULT_VPS_IP}\n", stderr=""),
            ),
            patch("time.sleep"),
        ):
            verify_dns_before_deployment("example.vps1.ocoron.com", timeout=5, poll_interval=0.01)
            assert calls["n"] >= 3

    def test_dig_timeout_is_treated_as_not_yet_resolving(self):
        # First call times out, second returns correct answer
        calls = {"n": 0}

        def flaky_run(*_args, **_kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise subprocess.TimeoutExpired(cmd="dig", timeout=5)
            return MagicMock(returncode=0, stdout=f"{DEFAULT_VPS_IP}\n", stderr="")

        with (
            patch.object(
                preflight, "ssh", return_value=f"{DEFAULT_VPS_IP}  example.vps1.ocoron.com"
            ),
            patch("subprocess.run", side_effect=flaky_run),
            patch("time.sleep"),
        ):
            verify_dns_before_deployment("example.vps1.ocoron.com", timeout=5, poll_interval=0.01)
            assert calls["n"] >= 2

    def test_dig_nonzero_exit_is_treated_as_not_yet_resolving(self):
        with (
            patch.object(
                preflight, "ssh", return_value=f"{DEFAULT_VPS_IP}  example.vps1.ocoron.com"
            ),
            patch(
                "subprocess.run",
                return_value=MagicMock(returncode=1, stdout="", stderr="SERVFAIL"),
            ),
            patch("time.sleep"),
        ):
            with pytest.raises(TimeoutError, match="public resolver"):
                verify_dns_before_deployment(
                    "example.vps1.ocoron.com", timeout=1, poll_interval=0.1
                )


# --------------------------------------------------------------------------- #
# restart_traefik_and_wait                                                     #
# --------------------------------------------------------------------------- #


class TestRestartTraefikAndWait:
    def test_dry_run_does_not_invoke_ssh(self):
        with patch.object(preflight, "ssh") as mock_ssh:
            restart_traefik_and_wait(dry_run=True)
            mock_ssh.assert_not_called()

    def test_restart_then_api_reachable_on_first_poll(self):
        # ssh is called once for "docker restart traefik" and once for the curl probe
        with (
            patch.object(preflight, "ssh", return_value="") as mock_ssh,
            patch("time.sleep") as mock_sleep,
        ):
            restart_traefik_and_wait(timeout=5, poll_interval=0.1)
            assert mock_ssh.call_count == 2
            assert mock_ssh.call_args_list[0].args[0] == "sudo docker restart traefik"
            assert "127.0.0.1:8080" in mock_ssh.call_args_list[1].args[0]
            mock_sleep.assert_not_called()  # didn't need to poll twice

    def test_api_unreachable_until_third_poll(self):
        # Restart succeeds; first two probe attempts fail, third succeeds
        calls = {"n": 0}

        def fake_ssh(cmd, timeout=60):
            if cmd.startswith("sudo docker restart"):
                return ""
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("curl: (7) Failed to connect")
            return ""

        with (
            patch.object(preflight, "ssh", side_effect=fake_ssh),
            patch("time.sleep"),
        ):
            restart_traefik_and_wait(timeout=5, poll_interval=0.01)
            assert calls["n"] == 3

    def test_api_never_reachable_raises_timeout_error(self):
        def fake_ssh(cmd, timeout=60):
            if cmd.startswith("sudo docker restart"):
                return ""
            raise RuntimeError("curl: (7) Failed to connect")

        with (
            patch.object(preflight, "ssh", side_effect=fake_ssh),
            patch("time.sleep"),
        ):
            with pytest.raises(TimeoutError, match="Traefik API"):
                restart_traefik_and_wait(timeout=1, poll_interval=0.1)

    def test_docker_restart_failure_propagates_runtime_error(self):
        def fake_ssh(cmd, timeout=60):
            if cmd.startswith("sudo docker restart"):
                raise RuntimeError("docker: Error response from daemon: no such container")
            return ""

        with patch.object(preflight, "ssh", side_effect=fake_ssh):
            with pytest.raises(RuntimeError, match="no such container"):
                restart_traefik_and_wait(timeout=5)
