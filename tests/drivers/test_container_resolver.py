import os
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from fabrik.drivers.wordpress import ContainerResolver, ContainerNotFoundError


@patch("subprocess.run")
def test_resolve_env_var_set(mock_run):
    with patch.dict(os.environ, {"WP_CONTAINER_NAME_OCORON_COM": "my-container"}):
        resolver = ContainerResolver("ocoron.com")
        assert resolver.resolve() == "my-container"
        mock_run.assert_not_called()


@patch("subprocess.run")
def test_resolve_ssh_match(mock_run):
    # env var absent by default
    with patch.dict(os.environ, clear=True):
        mock_result = MagicMock()
        mock_result.stdout = "ocoron-com-wordpress-1\n"
        mock_run.return_value = mock_result

        resolver = ContainerResolver("ocoron.com")
        assert resolver.resolve() == "ocoron-com-wordpress-1"
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "docker ps" in args[2]
        assert "name=ocoron.com" in args[2]


@patch("subprocess.run")
def test_resolve_ssh_no_match(mock_run):
    with patch.dict(os.environ, clear=True):
        mock_result = MagicMock()
        mock_result.stdout = "\n"
        mock_run.return_value = mock_result

        resolver = ContainerResolver("ocoron.com")
        with pytest.raises(ContainerNotFoundError):
            resolver.resolve()


@patch("subprocess.run")
def test_resolve_cached_no_repeat_ssh(mock_run):
    with patch.dict(os.environ, clear=True):
        mock_result = MagicMock()
        mock_result.stdout = "some-container-name\n"
        mock_run.return_value = mock_result

        resolver = ContainerResolver("ocoron.com")
        res1 = resolver.resolve_cached()
        res2 = resolver.resolve_cached()

        assert res1 == "some-container-name"
        assert res2 == "some-container-name"
        mock_run.assert_called_once()
