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


# --------------------------------------------------------------------------- #
# verify_host_reachable (W-2b657bee)                                           #
# --------------------------------------------------------------------------- #


def _probe(answers):
    """A `subprocess.run` stand-in: answers[i] is an int rc, a (rc, stderr) pair or an
    exception, consumed one per call; every argv is recorded on the returned list."""
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        answer = answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        rc, err = answer if isinstance(answer, tuple) else (answer, "")
        return MagicMock(returncode=rc, stdout="", stderr=err)

    return run, calls


class TestVerifyHostReachable:
    def test_direct_pass_probes_once_with_batchmode_and_devnull(self, monkeypatch):
        monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
        run, calls = _probe([0])
        with patch("subprocess.run", side_effect=run):
            preflight.verify_host_reachable("vps", timeout=7)
        argv, kwargs = calls[0]
        assert argv == ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=7", "vps", "true"]
        assert kwargs["timeout"] == 12
        assert kwargs["stdin"] is subprocess.DEVNULL
        assert kwargs["errors"] == "replace"  # undecodable stderr never escapes as an error
        assert len(calls) == 1

    @pytest.mark.parametrize(
        "answer, reason",
        [
            ((255, "ssh: Connection timed out during banner exchange\n"), "banner exchange"),
            (subprocess.TimeoutExpired(cmd="ssh", timeout=15), "no answer in 15s"),
            (OSError("No such file or directory: 'ssh'"), "No such file"),
            (OSError("No such file or directory."), "No such file or directory."),
        ],
    )
    def test_dead_direct_path_names_alias_path_and_fix(self, answer, reason, monkeypatch):
        monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
        run, _ = _probe([answer])
        with patch("subprocess.run", side_effect=run):
            with pytest.raises(preflight.HostUnreachableError) as info:
                preflight.verify_host_reachable("vps", timeout=10)
        msg = str(info.value)
        assert "'vps'" in msg and "without a FABRIK jump" in msg and reason in msg
        assert ".." not in msg
        assert "nothing was changed" in msg
        if not isinstance(answer, OSError):
            assert "FABRIK_SSH_JUMP_VPS=" in msg

    def test_non_network_failure_gets_no_jump_advice(self, monkeypatch):
        monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
        run, _ = _probe([(255, "Host key verification failed.\n")])
        with patch("subprocess.run", side_effect=run):
            with pytest.raises(preflight.HostUnreachableError) as info:
                preflight.verify_host_reachable("vps")
        msg = str(info.value)
        assert "Host key verification failed." in msg
        assert "ssh vps true" in msg
        assert "FABRIK_SSH_JUMP_VPS=" not in msg

    def test_jumped_failure_names_the_dead_leg(self, monkeypatch):
        monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
        # target via jump fails, first hop answers → the hop-to-target leg is dead
        run, calls = _probe([(255, "Connection timed out\n"), 0])
        with patch("subprocess.run", side_effect=run):
            with pytest.raises(preflight.HostUnreachableError) as info:
                preflight.verify_host_reachable("vps")
        assert calls[0][0][:3] == ["ssh", "-o", "ProxyJump=vps2"]
        assert calls[1][0][-2:] == ["vps2", "true"]
        msg = str(info.value)
        assert "via jump 'vps2'" in msg
        assert "'vps2' answers; the leg from it to 'vps' does not" in msg
        assert "Check that leg's network" in msg and "Check `ssh vps2 true`" not in msg
        # first hop dead too → the jump host is named
        run, _ = _probe([(255, "Connection timed out\n"), (255, "Connection refused\n")])
        with patch("subprocess.run", side_effect=run):
            with pytest.raises(
                preflight.HostUnreachableError, match="jump host 'vps2' is unreachable"
            ):
                preflight.verify_host_reachable("vps")

    def test_first_hop_with_user_and_port_is_probed_as_an_ssh_uri(self, monkeypatch):
        """`ssh … ops@vps2:2222 true` reads `vps2:2222` as the HOSTNAME; only ssh:// carries a port."""
        monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "ops@vps2:2222,b")
        run, calls = _probe([(255, "Connection timed out\n"), 0])
        with patch("subprocess.run", side_effect=run):
            with pytest.raises(preflight.HostUnreachableError) as info:
                preflight.verify_host_reachable("vps")
        assert calls[1][0][-2:] == ["ssh://ops@vps2:2222", "true"]
        assert "a later hop or the leg to 'vps' does not" in str(info.value)
        # the advice names the same destination the probe used (never `ssh ops@vps2:2222`)
        run, _ = _probe(
            [(255, "Connection timed out\n"), (255, "Permission denied (publickey).\n")]
        )
        with patch("subprocess.run", side_effect=run):
            with pytest.raises(preflight.HostUnreachableError) as info:
                preflight.verify_host_reachable("vps")
        assert "Run `ssh ssh://ops@vps2:2222 true` by hand" in str(info.value)

    def test_first_hop_auth_failure_gets_no_network_advice(self, monkeypatch):
        monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
        run, _ = _probe([(255, "Connection timed out\n"), (255, "Host key verification failed.\n")])
        with patch("subprocess.run", side_effect=run):
            with pytest.raises(preflight.HostUnreachableError) as info:
                preflight.verify_host_reachable("vps")
        msg = str(info.value)
        assert "The jump host 'vps2' fails: Host key verification failed." in msg
        assert "Run `ssh vps2 true` by hand" in msg and "unset FABRIK_SSH_JUMP_VPS" not in msg
        assert ".." not in msg

    def test_reason_is_the_cause_line_and_reset_is_network_shaped(self, monkeypatch):
        monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
        stderr = (
            "kex_exchange_identification: read: Connection reset by peer\n"
            "Connection closed by 172.93.160.197 port 22\n"
        )
        run, _ = _probe([(255, stderr)])
        with patch("subprocess.run", side_effect=run):
            with pytest.raises(preflight.HostUnreachableError) as info:
                preflight.verify_host_reachable("vps")
        msg = str(info.value)
        assert "Connection reset by peer" in msg and "Connection closed" not in msg
        assert "FABRIK_SSH_JUMP_VPS=" in msg
        # an auth-side close alone is not network-shaped
        run, _ = _probe([(255, "Connection closed by 172.93.160.197 port 22\n")])
        with patch("subprocess.run", side_effect=run):
            with pytest.raises(preflight.HostUnreachableError) as info:
                preflight.verify_host_reachable("vps")
        assert "FABRIK_SSH_JUMP_VPS=" not in str(info.value)

    def test_reason_skips_ssh_generic_sign_off(self, monkeypatch):
        monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
        stderr = (
            "channel 0: open failed: administratively prohibited: open failed\n"
            "stdio forwarding failed\n"
            "Connection closed by UNKNOWN port 65535\n"
        )
        run, _ = _probe([(255, stderr)])
        with patch("subprocess.run", side_effect=run):
            with pytest.raises(preflight.HostUnreachableError) as info:
                preflight.verify_host_reachable("vps")
        msg = str(info.value)
        assert "administratively prohibited" in msg and "stdio forwarding failed" in msg
        assert "Connection closed" not in msg

    @pytest.mark.parametrize(
        "stderr, cause",
        [
            (
                "Warning: Permanently added 'vps' (ED25519) to the list of known hosts.\n"
                "Permission denied (publickey).\n",
                "Permission denied (publickey)",
            ),
            (
                "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n"
                "@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @\n"
                "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n"
                "IT IS POSSIBLE THAT SOMEONE IS DOING SOMETHING NASTY!\n"
                "Host key verification failed.\n",
                "Host key verification failed",
            ),
        ],
    )
    def test_reason_is_the_failure_not_a_leading_warning_or_banner(
        self, stderr, cause, monkeypatch
    ):
        monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
        run, _ = _probe([(255, stderr)])
        with patch("subprocess.run", side_effect=run):
            with pytest.raises(preflight.HostUnreachableError) as info:
                preflight.verify_host_reachable("vps")
        msg = str(info.value)
        assert cause in msg
        assert "Warning:" not in msg and "@@@" not in msg
        assert "FABRIK_SSH_JUMP_VPS=" not in msg  # an auth/host-key failure, not the network

    def test_a_warning_line_never_makes_a_failure_network_shaped(self, monkeypatch):
        """`Warning: Permanently added 'vps-unreachable-box' …` contains 'unreachable'."""
        monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
        stderr = (
            "Warning: Permanently added 'vps-unreachable-box' (ED25519) to the list of known hosts.\n"
            "Permission denied (publickey).\n"
        )
        run, _ = _probe([(255, stderr)])
        with patch("subprocess.run", side_effect=run):
            with pytest.raises(preflight.HostUnreachableError) as info:
                preflight.verify_host_reachable("vps")
        assert "FABRIK_SSH_JUMP_VPS=" not in str(info.value)

    def test_a_long_reason_keeps_its_tail(self, monkeypatch):
        monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
        stderr = "".join(f"line {i} of a long host-key notice\n" for i in range(40))
        stderr += "Host key verification failed.\n"
        run, _ = _probe([(255, stderr)])
        with patch("subprocess.run", side_effect=run):
            with pytest.raises(preflight.HostUnreachableError) as info:
                preflight.verify_host_reachable("vps")
        msg = str(info.value)
        assert "Host key verification failed" in msg and "…" in msg and "line 0 " not in msg

    @pytest.mark.parametrize("alias", ["-oProxyCommand=x", "a b", "a;b"])
    def test_non_alias_host_is_refused_before_any_probe(self, alias):
        with patch("subprocess.run") as mock_run:
            with pytest.raises(preflight.HostUnreachableError, match="not an ssh alias"):
                preflight.verify_host_reachable(alias)
            mock_run.assert_not_called()

    def test_invalid_jump_value_is_a_host_unreachable_error(self, monkeypatch):
        monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "-oProxyCommand=x")
        with patch("subprocess.run") as mock_run:
            with pytest.raises(preflight.HostUnreachableError, match="FABRIK_SSH_JUMP_VPS"):
                preflight.verify_host_reachable("vps")
            mock_run.assert_not_called()

    def test_direct_path_back_is_logged_not_switched(self, monkeypatch, caplog):
        monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
        run, calls = _probe([0, 0])
        with caplog.at_level("WARNING", logger="fabrik.drivers.preflight"):
            with patch("subprocess.run", side_effect=run):
                preflight.verify_host_reachable("vps")
        advisory = calls[1][0]
        assert "ProxyJump=none" in advisory and "ProxyJump=vps2" not in advisory
        assert calls[1][1]["stdin"] is subprocess.DEVNULL
        assert "FABRIK_SSH_JUMP_VPS" in caplog.text and "direct path" in caplog.text
        # dead, or raising, advisory probes stay silent and the preflight still passes
        for advisory_answer in [
            (255, "timed out"),
            subprocess.TimeoutExpired("ssh", 5),
            OSError("x"),
        ]:
            caplog.clear()
            run, _ = _probe([0, advisory_answer])
            with caplog.at_level("WARNING", logger="fabrik.drivers.preflight"):
                with patch("subprocess.run", side_effect=run):
                    preflight.verify_host_reachable("vps")
            assert "direct path" not in caplog.text


# The full banner ssh prints for a changed host key (OpenSSH 9.x), BatchMode on.
_REAL_CHANGED_KEY_BANNER = (
    "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n"
    "@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @\n"
    "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n"
    "IT IS POSSIBLE THAT SOMEONE IS DOING SOMETHING NASTY!\n"
    "Someone could be eavesdropping on you right now (man-in-the-middle attack)!\n"
    "It is also possible that a host key has just been changed.\n"
    "The fingerprint for the ED25519 key sent by the remote host is\n"
    "SHA256:0pQ1kX9vJm2HcQyLrT7sWbA3eN5uD8fG4iK6oZ1xYc0.\n"
    "Please contact your system administrator.\n"
    "Add correct host key in /home/ops/.ssh/known_hosts to get rid of this message.\n"
    "Offending ED25519 key in /home/ops/.ssh/known_hosts:3\n"
    "  remove with:\n"
    "  ssh-keygen -f '/home/ops/.ssh/known_hosts' -R 'vps'\n"
    "Host key for vps has changed and you have requested strict checking.\n"
    "Host key verification failed.\n"
)


class TestProbeReason:
    """W-6a96f699 (review P5-01..03): the reason keeps what says why, and only that."""

    def _reason(self, stderr):
        run, _ = _probe([(255, stderr)])
        with patch("subprocess.run", side_effect=run):
            return preflight._probe(["ssh", "vps", "true"], 5)

    def test_the_real_banner_leads_with_its_headline_and_ends_with_the_failure(self):
        ok, network, reason = self._reason(_REAL_CHANGED_KEY_BANNER)
        assert ok is False and network is False
        assert reason.startswith("WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!")
        assert reason.endswith("Host key verification failed")
        assert "@" not in reason and len(reason) <= preflight._REASON_MAX + 80

    def test_a_cause_bearing_warning_is_kept_and_never_network_shaped(self):
        stderr = (
            "Warning: the ECDSA host key for 'vps-unreachable' differs from the key for the IP "
            "address '203.0.113.7'\n"
            "Offending key for IP in /home/ops/.ssh/known_hosts:5\n"
            "Host key verification failed.\n"
        )
        ok, network, reason = self._reason(stderr)
        assert "differs from the key for the IP address" in reason
        assert network is False  # 'unreachable' sits inside a Warning: line

    def test_the_known_hosts_notice_is_still_dropped(self):
        stderr = (
            "Warning: Permanently added 'vps' (ED25519) to the list of known hosts.\n"
            "Permission denied (publickey).\n"
        )
        assert self._reason(stderr)[2] == "Permission denied (publickey)"

    @pytest.mark.parametrize(
        "stderr, reason",
        [
            (".\n", "rc=255, stderr held no text"),
            ("@@@@@@@@@@\n", "rc=255, stderr held no text"),
            ("", "rc=255, no stderr"),
            (
                "Connection closed by 203.0.113.7 port 22\n.\n",
                "Connection closed by 203.0.113.7 port 22",
            ),
        ],
    )
    def test_a_lone_period_never_empties_the_reason(self, stderr, reason):
        assert self._reason(stderr)[2] == reason

    def test_the_headline_appears_once_and_is_bounded(self):
        """Review B-S1/B-S4: a repeated headline is said once, and the headline part is capped."""
        assert self._reason("@ x @\n@ x @\nHost key verification failed.\n")[2] == (
            "x; Host key verification failed"
        )
        many = "".join(f"@ headline {i} {'z' * 40} @\n" for i in range(30))
        reason = self._reason(many + "Host key verification failed.\n")[2]
        assert reason.endswith("Host key verification failed")
        assert len(reason) <= 2 * preflight._REASON_MAX + 4
        head = reason.split("; Host key verification failed")[0]
        assert len(head) == preflight._REASON_MAX and head.endswith("…")  # a cut is marked (B2-1)
