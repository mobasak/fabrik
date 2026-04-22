"""Unit tests for fabrik.drivers.gatus — mocked ssh/scp, no VPS required."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import yaml as yaml_lib

from fabrik.drivers import gatus
from fabrik.drivers.gatus import (
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_HEALTH_PATH,
    GATUS_CONFIG_DIR,
    _build_endpoint_yaml,
    _validate_domain,
    _validate_health_path,
    _validate_project_name,
    add_endpoint,
    remove_endpoint,
)

# --------------------------------------------------------------------------- #
# validators                                                                   #
# --------------------------------------------------------------------------- #


class TestValidators:
    @pytest.mark.parametrize("name", ["my-project", "proj_2026", "a", "A1_b-2"])
    def test_valid_project_names_accepted(self, name):
        _validate_project_name(name)

    @pytest.mark.parametrize(
        "name", ["", "-lead", "has space", "has/slash", "has.dot", "has;semi"]
    )
    def test_invalid_project_names_rejected(self, name):
        with pytest.raises(ValueError):
            _validate_project_name(name)

    @pytest.mark.parametrize(
        "domain",
        ["app.vps1.ocoron.com", "example.com", "a.b.c.d.example.org"],
    )
    def test_valid_domains_accepted(self, domain):
        _validate_domain(domain)

    @pytest.mark.parametrize(
        "domain",
        ["https://app.com", "app.com/path", "app.com:8080", "app com", "", "-leading"],
    )
    def test_invalid_domains_rejected(self, domain):
        with pytest.raises(ValueError):
            _validate_domain(domain)

    @pytest.mark.parametrize("path", ["/", "/health", "/v1/health/check"])
    def test_valid_health_paths_accepted(self, path):
        _validate_health_path(path)

    @pytest.mark.parametrize(
        "path", ["health", "", "/has'quote", '/has"quote']
    )
    def test_invalid_health_paths_rejected(self, path):
        with pytest.raises(ValueError):
            _validate_health_path(path)


# --------------------------------------------------------------------------- #
# _build_endpoint_yaml                                                         #
# --------------------------------------------------------------------------- #


class TestBuildEndpointYaml:
    def test_renders_parseable_yaml(self):
        body = _build_endpoint_yaml(
            "my-proj", "my-proj.vps1.ocoron.com", "/health", "60s", 3
        )
        parsed = yaml_lib.safe_load(body)
        assert parsed["endpoints"][0]["url"] == "https://my-proj.vps1.ocoron.com/health"
        assert parsed["endpoints"][0]["interval"] == "60s"
        assert parsed["endpoints"][0]["conditions"] == ["[STATUS] == 200"]
        assert parsed["endpoints"][0]["alerts"][0]["failure-threshold"] == 3
        assert parsed["endpoints"][0]["alerts"][0]["send-on-resolved"] is True

    def test_group_is_apps(self):
        body = _build_endpoint_yaml("x", "x.ocoron.com", "/h", "60s", 3)
        parsed = yaml_lib.safe_load(body)
        assert parsed["endpoints"][0]["group"] == "apps"

    def test_custom_threshold_flows_through(self):
        body = _build_endpoint_yaml("x", "x.ocoron.com", "/h", "30s", 5)
        parsed = yaml_lib.safe_load(body)
        assert parsed["endpoints"][0]["alerts"][0]["failure-threshold"] == 5


# --------------------------------------------------------------------------- #
# add_endpoint                                                                 #
# --------------------------------------------------------------------------- #


class TestAddEndpoint:
    def test_existing_file_returns_exists_without_restart(self):
        with (
            patch.object(gatus, "ssh", return_value="exists") as mock_ssh,
            patch.object(gatus, "scp_to_vps") as mock_scp,
        ):
            result = add_endpoint("my-proj", "my-proj.vps1.ocoron.com")
        assert result == {"status": "exists", "endpoint": "my-proj"}
        # Only the test -f check was issued; no scp, no restart
        assert mock_ssh.call_count == 1
        assert "test -f" in mock_ssh.call_args.args[0]
        mock_scp.assert_not_called()

    def test_new_endpoint_scps_moves_and_restarts(self):
        calls: list[str] = []

        def fake_ssh(cmd, **_kw):
            calls.append(cmd)
            if "test -f" in cmd:
                return "missing"
            return ""

        with (
            patch.object(gatus, "ssh", side_effect=fake_ssh),
            patch.object(gatus, "scp_to_vps") as mock_scp,
        ):
            result = add_endpoint("my-proj", "my-proj.vps1.ocoron.com")

        assert result == {"status": "created", "endpoint": "my-proj"}
        assert mock_scp.call_count == 1
        # Verify the YAML file reaches GATUS_CONFIG_DIR via sudo mv
        mv_cmd = next(c for c in calls if "sudo mv" in c)
        assert GATUS_CONFIG_DIR in mv_cmd
        assert "my-proj.yaml" in mv_cmd
        # Gatus restart via prefix match
        restart_cmd = next(c for c in calls if "docker restart" in c)
        assert "^gatus-" in restart_cmd

    def test_new_endpoint_local_tmpfile_cleaned_up(self):
        """The staging tempfile must be removed even if scp/ssh raise."""
        import pathlib

        captured_local_path: list[str] = []

        def fake_scp(local, _remote, **_kw):
            captured_local_path.append(local)
            # path should exist at this point
            assert pathlib.Path(local).exists()

        def fake_ssh(cmd, **_kw):
            return "missing" if "test -f" in cmd else ""

        with (
            patch.object(gatus, "ssh", side_effect=fake_ssh),
            patch.object(gatus, "scp_to_vps", side_effect=fake_scp),
        ):
            add_endpoint("my-proj", "my-proj.vps1.ocoron.com")

        assert captured_local_path, "scp should have been called"
        # After finally block, the local tempfile is gone
        assert not pathlib.Path(captured_local_path[0]).exists()

    def test_dry_run_skips_all_ssh_and_scp(self):
        with (
            patch.object(gatus, "ssh") as mock_ssh,
            patch.object(gatus, "scp_to_vps") as mock_scp,
        ):
            result = add_endpoint("my-proj", "my-proj.vps1.ocoron.com", dry_run=True)
        assert result == {"status": "dry_run", "endpoint": "my-proj"}
        mock_ssh.assert_not_called()
        mock_scp.assert_not_called()

    def test_invalid_project_name_raises_before_ssh(self):
        with (
            patch.object(gatus, "ssh") as mock_ssh,
            patch.object(gatus, "scp_to_vps") as mock_scp,
        ):
            with pytest.raises(ValueError):
                add_endpoint("bad name", "my.ocoron.com")
            mock_ssh.assert_not_called()
            mock_scp.assert_not_called()

    def test_invalid_domain_raises_before_ssh(self):
        with patch.object(gatus, "ssh") as mock_ssh:
            with pytest.raises(ValueError):
                add_endpoint("my-proj", "https://has-scheme.com")
            mock_ssh.assert_not_called()

    def test_health_path_flows_into_url(self):
        calls: list[str] = []

        def fake_ssh(cmd, **_kw):
            calls.append(cmd)
            return "missing" if "test -f" in cmd else ""

        captured_yaml: list[str] = []

        def fake_scp(local, _remote, **_kw):
            from pathlib import Path

            captured_yaml.append(Path(local).read_text())

        with (
            patch.object(gatus, "ssh", side_effect=fake_ssh),
            patch.object(gatus, "scp_to_vps", side_effect=fake_scp),
        ):
            add_endpoint("my-proj", "my.ocoron.com", health_path="/v1/ping")

        assert captured_yaml
        parsed = yaml_lib.safe_load(captured_yaml[0])
        assert parsed["endpoints"][0]["url"] == "https://my.ocoron.com/v1/ping"

    def test_default_health_path_is_slash_health(self):
        captured_yaml: list[str] = []

        def fake_scp(local, _remote, **_kw):
            from pathlib import Path

            captured_yaml.append(Path(local).read_text())

        with (
            patch.object(gatus, "ssh", return_value="missing"),
            patch.object(gatus, "scp_to_vps", side_effect=fake_scp),
        ):
            add_endpoint("my-proj", "my.ocoron.com")

        parsed = yaml_lib.safe_load(captured_yaml[0])
        assert parsed["endpoints"][0]["url"].endswith(DEFAULT_HEALTH_PATH)

    def test_default_failure_threshold_matches_audit_baseline(self):
        captured: list[str] = []

        def fake_scp(local, _remote, **_kw):
            from pathlib import Path

            captured.append(Path(local).read_text())

        with (
            patch.object(gatus, "ssh", return_value="missing"),
            patch.object(gatus, "scp_to_vps", side_effect=fake_scp),
        ):
            add_endpoint("my-proj", "my.ocoron.com")

        parsed = yaml_lib.safe_load(captured[0])
        assert (
            parsed["endpoints"][0]["alerts"][0]["failure-threshold"]
            == DEFAULT_FAILURE_THRESHOLD
        )


# --------------------------------------------------------------------------- #
# remove_endpoint                                                              #
# --------------------------------------------------------------------------- #


class TestRemoveEndpoint:
    def test_success_returns_true_and_restarts(self):
        calls: list[str] = []

        def fake_ssh(cmd, **_kw):
            calls.append(cmd)
            return ""

        with patch.object(gatus, "ssh", side_effect=fake_ssh):
            assert remove_endpoint("my-proj") is True
        assert any("rm -f" in c and "my-proj.yaml" in c for c in calls)
        assert any("docker restart" in c for c in calls)

    def test_ssh_failure_returns_false_without_raising(self):
        """Rollback must never raise — returns False on any error."""

        def failing(*_args, **_kw):
            raise RuntimeError("ssh failed")

        with patch.object(gatus, "ssh", side_effect=failing):
            assert remove_endpoint("my-proj") is False

    def test_dry_run_returns_true_without_ssh(self):
        with patch.object(gatus, "ssh") as mock_ssh:
            assert remove_endpoint("my-proj", dry_run=True) is True
            mock_ssh.assert_not_called()

    def test_invalid_project_name_still_raises_value_error(self):
        """Input validation happens before the try/except."""
        with patch.object(gatus, "ssh") as mock_ssh:
            with pytest.raises(ValueError):
                remove_endpoint("bad name")
            mock_ssh.assert_not_called()
