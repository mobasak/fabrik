"""
Unit tests for FABRIK_EXEC_MODE env-gate in fabrik.drivers.wordpress (T1.1).

Covers:
- Module-level `_get_exec_mode()` helper: default, explicit local, unknown raises, case-insensitive.
- `ContainerResolver` SSH and local-mode subprocess argv.
- `WordPressClient` SSH and local-mode subprocess argv.
- Constructor parameter overrides env value.
- `WP_CONTAINER_NAME_<SLUG>` short-circuit preserved in both modes.

All subprocess invocations are mocked — no live SSH or Docker calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fabrik.drivers.wordpress import (
    ContainerResolver,
    WordPressClient,
    WPSite,
    _get_exec_mode,
)


class TestGetExecMode:
    """Tests for the module-level _get_exec_mode() helper."""

    def test_default_mode_is_ssh_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("FABRIK_EXEC_MODE", raising=False)
        assert _get_exec_mode() == "ssh"

    def test_local_mode_when_env_set(self, monkeypatch):
        monkeypatch.setenv("FABRIK_EXEC_MODE", "local")
        assert _get_exec_mode() == "local"

    def test_unknown_mode_raises_at_helper(self, monkeypatch):
        monkeypatch.setenv("FABRIK_EXEC_MODE", "paramiko")
        with pytest.raises(ValueError, match="paramiko"):
            _get_exec_mode()

    def test_case_insensitive_env_value(self, monkeypatch):
        monkeypatch.setenv("FABRIK_EXEC_MODE", "LOCAL")
        assert _get_exec_mode() == "local"


class TestContainerResolverExecMode:
    """Tests for ContainerResolver SSH vs local-mode dispatch."""

    @patch("subprocess.run")
    def test_resolver_ssh_mode_invokes_ssh(self, mock_run, monkeypatch):
        monkeypatch.delenv("WP_CONTAINER_NAME_OCORON_COM", raising=False)
        mock_run.return_value = MagicMock(stdout="ocoron-com-wordpress-1\n", stderr="")

        resolver = ContainerResolver("ocoron.com", exec_mode="ssh")
        result = resolver.resolve()

        assert result == "ocoron-com-wordpress-1"
        args = mock_run.call_args[0][0]
        assert args[0] == "ssh"
        assert args[1] == "vps"
        assert "docker ps" in args[2]

    @patch("subprocess.run")
    def test_resolver_local_mode_invokes_docker_directly(self, mock_run, monkeypatch):
        monkeypatch.delenv("WP_CONTAINER_NAME_OCORON_COM", raising=False)
        mock_run.return_value = MagicMock(stdout="ocoron-com-wordpress-1\n", stderr="")

        resolver = ContainerResolver("ocoron.com", exec_mode="local")
        result = resolver.resolve()

        assert result == "ocoron-com-wordpress-1"
        args = mock_run.call_args[0][0]
        assert args[0] == "sudo"
        assert args[1] == "docker"
        assert args[2] == "ps"
        assert "ssh" not in args


class TestWordPressClientExecMode:
    """Tests for WordPressClient SSH vs local-mode dispatch."""

    @patch("subprocess.run")
    def test_client_ssh_mode_invokes_ssh(self, mock_run, monkeypatch):
        monkeypatch.delenv("FABRIK_EXEC_MODE", raising=False)
        mock_run.return_value = MagicMock(returncode=0, stdout="6.4.2\n", stderr="")

        site = WPSite(name="s", domain="d", container="c")
        client = WordPressClient(site, exec_mode="ssh")
        client.run("core version")

        args = mock_run.call_args[0][0]
        assert args[0] == "ssh"
        assert args[1] == "vps"
        assert "sudo docker exec" in args[2]
        assert "wp core version" in args[2]
        assert "--allow-root" in args[2]

    @patch("subprocess.run")
    def test_client_local_mode_invokes_docker_directly(self, mock_run, monkeypatch):
        monkeypatch.delenv("FABRIK_EXEC_MODE", raising=False)
        mock_run.return_value = MagicMock(returncode=0, stdout="6.4.2\n", stderr="")

        site = WPSite(name="s", domain="d", container="c")
        client = WordPressClient(site, exec_mode="local")
        client.run("core version")

        args = mock_run.call_args[0][0]
        assert args == ["sudo", "docker", "exec", "c", "wp", "core", "version", "--allow-root"]


class TestConstructorOverridesEnv:
    """Constructor exec_mode kwarg must win over FABRIK_EXEC_MODE env."""

    @patch("subprocess.run")
    def test_constructor_param_overrides_env(self, mock_run, monkeypatch):
        monkeypatch.setenv("FABRIK_EXEC_MODE", "ssh")
        mock_run.return_value = MagicMock(returncode=0, stdout="ok\n", stderr="")

        site = WPSite(name="s", domain="d", container="c")
        client = WordPressClient(site, exec_mode="local")
        client.run("core version")

        args = mock_run.call_args[0][0]
        assert args[0] == "sudo"
        assert "ssh" not in args


class TestWpContainerNameShortCircuit:
    """The WP_CONTAINER_NAME_<SLUG> escape hatch must survive in both modes."""

    @patch("subprocess.run")
    def test_wp_container_name_env_var_short_circuit_preserved(self, mock_run, monkeypatch):
        monkeypatch.setenv("WP_CONTAINER_NAME_OCORON_COM", "ocoron-com-wordpress-1")

        resolver = ContainerResolver("ocoron.com", exec_mode="local")
        result = resolver.resolve()

        assert result == "ocoron-com-wordpress-1"
        mock_run.assert_not_called()
