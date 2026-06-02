"""Tests for SSH + Docker Compose deployer (deployer_ssh.py).

Covers: _parse_env, _format_env, _validate_name, _validate_compose,
_generate_docker_compose, _build_env_content, and all SSHDeployer
public methods (deploy, find_existing, delete, inject_env, redeploy)
with mocked SSH.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.deployer_ssh import (
    SSHDeployer,
    _format_env,
    _generate_docker_compose,
    _parse_env,
    _validate_compose,
    _validate_name,
)
from fabrik.orchestrator.exceptions import DeployError


# ======================================================================
# _parse_env / _format_env
# ======================================================================


class TestParseEnv:
    def test_simple_key_value(self):
        assert _parse_env("FOO=bar\nBAZ=qux") == {"FOO": "bar", "BAZ": "qux"}

    def test_strips_double_quotes(self):
        assert _parse_env('FOO="hello world"') == {"FOO": "hello world"}

    def test_strips_single_quotes(self):
        assert _parse_env("FOO='hello world'") == {"FOO": "hello world"}

    def test_ignores_comments(self):
        assert _parse_env("# comment\nFOO=bar\n# another") == {"FOO": "bar"}

    def test_ignores_blank_lines(self):
        assert _parse_env("\n\nFOO=bar\n\n") == {"FOO": "bar"}

    def test_ignores_lines_without_equals(self):
        assert _parse_env("no-equals-here\nFOO=bar") == {"FOO": "bar"}

    def test_value_with_equals(self):
        """Values can contain = (e.g. DATABASE_URL)."""
        assert _parse_env("DB=postgres://u:p@host/db?opt=1") == {
            "DB": "postgres://u:p@host/db?opt=1"
        }

    def test_empty_value(self):
        assert _parse_env("EMPTY=") == {"EMPTY": ""}

    def test_empty_input(self):
        assert _parse_env("") == {}


class TestFormatEnv:
    def test_simple_values(self):
        result = _format_env({"A": "1", "B": "2"})
        assert result == "A=1\nB=2\n"

    def test_sorted_output(self):
        result = _format_env({"Z": "last", "A": "first"})
        assert result.startswith("A=first\n")

    def test_quotes_spaces(self):
        result = _format_env({"MSG": "hello world"})
        assert result == 'MSG="hello world"\n'

    def test_quotes_hash(self):
        result = _format_env({"URL": "http://host#frag"})
        assert result == 'URL="http://host#frag"\n'

    def test_empty_dict(self):
        assert _format_env({}) == ""

    def test_round_trip(self):
        """Parse → format → parse should preserve values."""
        original = "API_KEY=abc123\nDATABASE_URL=postgres://u:p@host:5432/db\nDEBUG=false\n"
        parsed = _parse_env(original)
        formatted = _format_env(parsed)
        reparsed = _parse_env(formatted)
        assert reparsed == parsed

    def test_round_trip_with_quotes(self):
        original = {"MSG": "hello world", "PLAIN": "simple"}
        formatted = _format_env(original)
        reparsed = _parse_env(formatted)
        assert reparsed == original


# ======================================================================
# _validate_name
# ======================================================================


class TestValidateName:
    def test_valid_names(self):
        for name in ["my-app", "app1", "a", "abc-def-123", "a" * 63]:
            _validate_name(name)  # should not raise

    def test_rejects_uppercase(self):
        with pytest.raises(DeployError, match="Invalid app name"):
            _validate_name("MyApp")

    def test_rejects_underscore(self):
        with pytest.raises(DeployError, match="Invalid app name"):
            _validate_name("my_app")

    def test_rejects_leading_hyphen(self):
        with pytest.raises(DeployError, match="Invalid app name"):
            _validate_name("-app")

    def test_rejects_empty(self):
        with pytest.raises(DeployError, match="Invalid app name"):
            _validate_name("")

    def test_rejects_too_long(self):
        with pytest.raises(DeployError, match="Invalid app name"):
            _validate_name("a" * 64)

    def test_rejects_shell_injection(self):
        with pytest.raises(DeployError, match="Invalid app name"):
            _validate_name("app; rm -rf /")

    def test_rejects_spaces(self):
        with pytest.raises(DeployError, match="Invalid app name"):
            _validate_name("my app")

    def test_rejects_dots(self):
        with pytest.raises(DeployError, match="Invalid app name"):
            _validate_name("my.app")


# ======================================================================
# _validate_compose
# ======================================================================


class TestValidateCompose:
    def _valid_compose(self) -> str:
        """Minimal valid compose YAML."""
        return (
            "services:\n"
            "  web:\n"
            "    image: python:3.12\n"
            "    container_name: my-app\n"
            "    platform: linux/amd64\n"
            "    restart: unless-stopped\n"
            "    deploy:\n"
            "      resources:\n"
            "        limits:\n"
            "          memory: 256M\n"
            "    networks:\n"
            "      - fabrik\n"
            "networks:\n"
            "  fabrik:\n"
            "    external: true\n"
        )

    def test_valid_compose_passes(self):
        assert _validate_compose(self._valid_compose()) == []

    def test_invalid_yaml(self):
        errors = _validate_compose("{{invalid yaml")
        assert len(errors) == 1
        assert "Invalid YAML" in errors[0]

    def test_missing_services(self):
        errors = _validate_compose("version: '3'\n")
        assert any("No services" in e for e in errors)

    def test_missing_platform(self):
        compose = self._valid_compose().replace("    platform: linux/amd64\n", "")
        errors = _validate_compose(compose)
        assert any("platform" in e for e in errors)

    def test_wrong_platform(self):
        compose = self._valid_compose().replace("linux/amd64", "linux/arm64")
        errors = _validate_compose(compose)
        assert any("linux/amd64" in e for e in errors)

    def test_missing_memory(self):
        compose = (
            "services:\n"
            "  web:\n"
            "    image: python:3.12\n"
            "    container_name: my-app\n"
            "    platform: linux/amd64\n"
            "    restart: unless-stopped\n"
        )
        errors = _validate_compose(compose)
        assert any("memory" in e for e in errors)

    def test_ports_forbidden(self):
        compose = self._valid_compose().replace(
            "    networks:", "    ports:\n      - '8080:8080'\n    networks:"
        )
        errors = _validate_compose(compose)
        assert any("ports" in e.lower() for e in errors)

    def test_missing_restart(self):
        compose = self._valid_compose().replace("    restart: unless-stopped\n", "")
        errors = _validate_compose(compose)
        assert any("restart" in e for e in errors)

    def test_missing_container_name(self):
        compose = self._valid_compose().replace("    container_name: my-app\n", "")
        errors = _validate_compose(compose)
        assert any("container_name" in e for e in errors)

    def test_depends_on_postgres_main_forbidden(self):
        compose = self._valid_compose().replace(
            "    networks:", "    depends_on:\n      - postgres-main\n    networks:"
        )
        errors = _validate_compose(compose)
        assert any("postgres-main" in e for e in errors)

    def test_depends_on_redis_main_forbidden(self):
        compose = self._valid_compose().replace(
            "    networks:",
            "    depends_on:\n      redis-main:\n        condition: service_started\n    networks:",
        )
        errors = _validate_compose(compose)
        assert any("redis-main" in e for e in errors)

    def test_localhost_in_database_url(self):
        compose = self._valid_compose().replace(
            "    networks:",
            "    environment:\n      DATABASE_URL: postgresql://localhost:5432/db\n    networks:",
        )
        errors = _validate_compose(compose)
        assert any("localhost" in e for e in errors)

    def test_coolify_network_must_be_external(self):
        compose = self._valid_compose().replace("    external: true", "    external: false")
        errors = _validate_compose(compose)
        assert any("external" in e for e in errors)

    def test_traefik_labels_require_websecure(self):
        compose = self._valid_compose().replace(
            "    networks:",
            "    labels:\n"
            "      - traefik.enable=true\n"
            "      - traefik.http.routers.app.entrypoints=http\n"
            "    networks:",
        )
        errors = _validate_compose(compose)
        assert any("websecure" in e for e in errors)

    def test_traefik_labels_require_loadbalancer_port(self):
        compose = self._valid_compose().replace(
            "    networks:",
            "    labels:\n"
            "      - traefik.enable=true\n"
            "      - traefik.http.routers.app.entrypoints=websecure\n"
            "    networks:",
        )
        errors = _validate_compose(compose)
        assert any("loadbalancer.server.port" in e for e in errors)

    def test_valid_traefik_labels_pass(self):
        compose = self._valid_compose().replace(
            "    networks:",
            "    labels:\n"
            "      - traefik.enable=true\n"
            "      - traefik.http.routers.app.entrypoints=websecure\n"
            "      - traefik.http.services.app.loadbalancer.server.port=8000\n"
            "    networks:",
        )
        errors = _validate_compose(compose)
        assert errors == []


# ======================================================================
# _generate_docker_compose
# ======================================================================


class TestGenerateDockerCompose:
    def test_generates_valid_compose(self):
        result = _generate_docker_compose(
            "my-app", "python:3.12-slim", 8000, "my-app.example.com", {}
        )
        errors = _validate_compose(result)
        assert errors == [], f"Generated compose has errors: {errors}"

    def test_includes_container_name(self):
        result = _generate_docker_compose("my-app", "img:latest", 8000, "", {})
        assert "container_name: my-app" in result

    def test_includes_traefik_labels_with_domain(self):
        result = _generate_docker_compose("my-app", "img:latest", 8000, "app.example.com", {})
        assert "traefik.enable=true" in result
        assert "websecure" in result
        assert "letsencrypt" in result
        assert "loadbalancer.server.port=8000" in result

    def test_no_labels_without_domain(self):
        result = _generate_docker_compose("my-app", "img:latest", 8000, "", {})
        assert "traefik" not in result

    def test_uses_custom_memory(self):
        result = _generate_docker_compose(
            "my-app", "img:latest", 8000, "", {"resources": {"memory": "512M"}}
        )
        assert "memory: 512M" in result

    def test_default_memory(self):
        result = _generate_docker_compose("my-app", "img:latest", 8000, "", {})
        assert "memory: 256M" in result

    def test_healthcheck_uses_port(self):
        result = _generate_docker_compose("my-app", "img:latest", 3000, "", {})
        assert "localhost:3000/health" in result


# ======================================================================
# SSHDeployer — public API (all SSH mocked)
# ======================================================================


def _ctx(spec: dict, dry_run: bool = False) -> DeploymentContext:
    """Build a DeploymentContext from a spec dict."""
    ctx = DeploymentContext(spec_path=Path("test.yaml"), dry_run=dry_run)
    ctx.spec = spec
    return ctx


class TestSSHDeployerFindExisting:
    def test_found(self):
        with patch("fabrik.drivers.ssh.ssh") as mock_ssh:
            mock_ssh.side_effect = [
                "exists",  # test -f
                '{"Name": "my-app"}',  # docker compose ps
            ]
            deployer = SSHDeployer()
            result = deployer.find_existing("my-app")

        assert result is not None
        assert result["name"] == "my-app"
        assert result["path"] == "/opt/my-app"

    def test_not_found_ssh_fails(self):
        with patch("fabrik.drivers.ssh.ssh", side_effect=RuntimeError("SSH failed")):
            deployer = SSHDeployer()
            assert deployer.find_existing("my-app") is None

    def test_not_found_no_exists(self):
        with patch("fabrik.drivers.ssh.ssh", return_value=""):
            deployer = SSHDeployer()
            assert deployer.find_existing("my-app") is None

    def test_rejects_invalid_name(self):
        deployer = SSHDeployer()
        with pytest.raises(DeployError, match="Invalid app name"):
            deployer.find_existing("INVALID")


class TestSSHDeployerDelete:
    def test_delete_calls_ssh(self):
        with patch("fabrik.drivers.ssh.ssh") as mock_ssh:
            deployer = SSHDeployer()
            result = deployer.delete("my-app")

        assert result is True
        assert mock_ssh.call_count == 3
        # compose down, rm -rf, image prune
        cmds = [c.args[0] for c in mock_ssh.call_args_list]
        assert "docker compose down -v" in cmds[0]
        assert "rm -rf /opt/my-app" in cmds[1]
        assert "docker image prune" in cmds[2]

    def test_delete_dry_run(self):
        with patch("fabrik.drivers.ssh.ssh") as mock_ssh:
            deployer = SSHDeployer()
            result = deployer.delete("my-app", dry_run=True)

        assert result is True
        mock_ssh.assert_not_called()

    def test_delete_rejects_invalid_name(self):
        deployer = SSHDeployer()
        with pytest.raises(DeployError):
            deployer.delete("BAD NAME")


class TestSSHDeployerInjectEnv:
    def test_merges_and_restarts(self):
        with patch("fabrik.drivers.ssh.ssh") as mock_ssh, \
             patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps") as mock_write:
            mock_ssh.return_value = "EXISTING=keep\nOLD_KEY=old\n"

            ctx = _ctx({"name": "my-app"})
            ctx.coolify_uuid = "my-app"
            deployer = SSHDeployer()
            deployer.inject_env(ctx, {"NEW_KEY": "new", "OLD_KEY": "updated"})

        # Should have written merged .env
        written_content = mock_write.call_args[0][2]
        parsed = _parse_env(written_content)
        assert parsed["EXISTING"] == "keep"
        assert parsed["NEW_KEY"] == "new"
        assert parsed["OLD_KEY"] == "updated"

        # Should have restarted
        restart_call = [c for c in mock_ssh.call_args_list if "docker compose up" in str(c)]
        assert len(restart_call) == 1

    def test_dry_run_skips(self):
        with patch("fabrik.drivers.ssh.ssh") as mock_ssh:
            ctx = _ctx({"name": "my-app"}, dry_run=True)
            ctx.coolify_uuid = "my-app"
            deployer = SSHDeployer()
            deployer.inject_env(ctx, {"KEY": "val"})

        mock_ssh.assert_not_called()

    def test_raises_without_coolify_uuid(self):
        ctx = _ctx({"name": "my-app"})
        ctx.coolify_uuid = None
        deployer = SSHDeployer()
        with pytest.raises(DeployError, match="app_name is not set"):
            deployer.inject_env(ctx, {"KEY": "val"})


class TestSSHDeployerRedeploy:
    def test_redeploy_template(self):
        with patch("fabrik.drivers.ssh.ssh") as mock_ssh:
            deployer = SSHDeployer()
            deployer.redeploy("my-app", source_type="template")

        cmds = [c.args[0] for c in mock_ssh.call_args_list]
        assert len(cmds) == 1
        assert "docker compose up -d" in cmds[0]
        assert "--force-recreate" not in cmds[0]

    def test_redeploy_template_force(self):
        with patch("fabrik.drivers.ssh.ssh") as mock_ssh:
            deployer = SSHDeployer()
            deployer.redeploy("my-app", source_type="template", force=True)

        cmds = [c.args[0] for c in mock_ssh.call_args_list]
        assert "--force-recreate" in cmds[0]

    def test_redeploy_git(self):
        with patch("fabrik.drivers.ssh.ssh", return_value="") as mock_ssh:
            deployer = SSHDeployer()
            deployer.redeploy("my-app", source_type="git")

        cmds = [c.args[0] for c in mock_ssh.call_args_list]
        # rev-parse captures the rollback point BEFORE mutating, then the
        # normal pull/build/up sequence. On success no rollback runs.
        assert any("git rev-parse HEAD" in c for c in cmds)
        assert any("git pull" in c for c in cmds)
        assert any("docker compose build" in c for c in cmds)
        assert any("docker compose up -d --wait" in c for c in cmds)
        # rev-parse must precede the destructive pull
        assert next(i for i, c in enumerate(cmds) if "rev-parse" in c) < next(
            i for i, c in enumerate(cmds) if "git pull" in c
        )

    def test_redeploy_git_force(self):
        with patch("fabrik.drivers.ssh.ssh") as mock_ssh:
            deployer = SSHDeployer()
            deployer.redeploy("my-app", source_type="git", force=True)

        cmds = [c.args[0] for c in mock_ssh.call_args_list]
        build_cmds = [c for c in cmds if "docker compose build" in c]
        assert build_cmds and "--no-cache" in build_cmds[0]

    def test_redeploy_dry_run(self):
        with patch("fabrik.drivers.ssh.ssh") as mock_ssh:
            deployer = SSHDeployer()
            deployer.redeploy("my-app", dry_run=True)

        mock_ssh.assert_not_called()

    def test_redeploy_rejects_invalid_name(self):
        deployer = SSHDeployer()
        with pytest.raises(DeployError):
            deployer.redeploy("BAD NAME")


# ======================================================================
# SSHDeployer.deploy — source type dispatch
# ======================================================================


class TestSSHDeployerDeployDispatch:
    """Tests deploy() dispatch to the 4 source types + dry run + error paths."""

    def test_dry_run_returns_without_ssh(self):
        ctx = _ctx({"name": "my-app", "source": {"type": "template"}}, dry_run=True)
        with patch("fabrik.drivers.ssh.ssh") as mock_ssh:
            deployer = SSHDeployer()
            result = deployer.deploy(ctx)

        assert result == "dry-run-uuid"
        mock_ssh.assert_not_called()

    def test_unknown_source_type_raises(self):
        ctx = _ctx({"name": "my-app", "source": {"type": "ftp"}})
        deployer = SSHDeployer()
        with patch("fabrik.drivers.ssh.ssh"):
            with pytest.raises(DeployError, match="Unknown source type"):
                deployer.deploy(ctx)

    def test_invalid_name_raises(self):
        ctx = _ctx({"name": "INVALID APP"})
        deployer = SSHDeployer()
        with pytest.raises(DeployError, match="Invalid app name"):
            deployer.deploy(ctx)

    def test_dispatch_template(self):
        ctx = _ctx({
            "name": "my-app",
            "source": {"type": "template"},
            "template": "python-api",
            "domain": "my-app.example.com",
        })
        deployer = SSHDeployer()
        with patch.object(deployer, "find_existing", return_value=None), \
             patch.object(deployer, "_deploy_template") as mock_tmpl:
            deployer.deploy(ctx)

        mock_tmpl.assert_called_once()
        assert ctx.coolify_uuid == "my-app"
        # New deploy should track resource
        compose_resources = ctx.get_resources_by_type("compose")
        assert len(compose_resources) == 1
        assert compose_resources[0].resource_id == "my-app"

    def test_dispatch_git(self):
        ctx = _ctx({
            "name": "my-app",
            "source": {"type": "git", "repository": "git@github.com:user/repo.git"},
        })
        deployer = SSHDeployer()
        with patch.object(deployer, "find_existing", return_value=None), \
             patch.object(deployer, "_deploy_git") as mock_git:
            deployer.deploy(ctx)

        mock_git.assert_called_once()

    def test_dispatch_docker(self):
        ctx = _ctx({
            "name": "my-app",
            "source": {"type": "docker", "image": "nginx:latest"},
            "domain": "my-app.example.com",
        })
        deployer = SSHDeployer()
        with patch.object(deployer, "find_existing", return_value=None), \
             patch.object(deployer, "_deploy_docker") as mock_docker:
            deployer.deploy(ctx)

        mock_docker.assert_called_once()

    def test_dispatch_local(self):
        ctx = _ctx({
            "name": "my-app",
            "source": {"type": "local", "path": "/opt/my-app"},
        })
        deployer = SSHDeployer()
        with patch.object(deployer, "find_existing", return_value=None), \
             patch.object(deployer, "_deploy_local") as mock_local:
            deployer.deploy(ctx)

        mock_local.assert_called_once()

    def test_existing_app_no_resource_tracking(self):
        """Updating an existing app should NOT add a resource record."""
        ctx = _ctx({"name": "my-app", "source": {"type": "template"}})
        deployer = SSHDeployer()
        existing = {"name": "my-app", "status": "", "path": "/opt/my-app"}
        with patch.object(deployer, "find_existing", return_value=existing), \
             patch.object(deployer, "_deploy_template"):
            deployer.deploy(ctx)

        assert ctx.get_resources_by_type("compose") == []

    def test_source_type_from_source_object(self):
        """deploy() handles Source objects (not just dicts)."""
        from fabrik.spec_loader import Source, SourceType

        source_obj = Source(type=SourceType.LOCAL, path="/opt/my-app")
        ctx = _ctx({"name": "my-app", "source": source_obj})
        deployer = SSHDeployer()
        with patch.object(deployer, "find_existing", return_value=None), \
             patch.object(deployer, "_deploy_local") as mock_local:
            deployer.deploy(ctx)

        mock_local.assert_called_once()


# ======================================================================
# _deploy_git — SSH-level assertions
# ======================================================================


class TestDeployGit:
    def test_new_clone(self):
        ctx = _ctx({
            "name": "my-app",
            "source": {"type": "git", "repository": "git@github.com:user/repo.git", "branch": "main"},
        })
        with patch("fabrik.drivers.ssh.ssh") as mock_ssh, \
             patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps"):
            # test -d .git fails (not cloned yet)
            mock_ssh.side_effect = [
                RuntimeError("not exists"),  # test -d .git
                "",  # ssh-keyscan github.com → known_hosts (added 2026-05-31)
                "",  # git clone
                "",  # docker compose build
                "",  # docker compose up -d
            ]
            deployer = SSHDeployer()
            deployer._deploy_git(ctx, "my-app", ctx.spec["source"], None)

        # Index 1 is the ssh-keyscan; clone is index 2 now
        keyscan_cmd = mock_ssh.call_args_list[1].args[0]
        assert "ssh-keyscan" in keyscan_cmd
        assert "github.com" in keyscan_cmd
        clone_cmd = mock_ssh.call_args_list[2].args[0]
        assert "git clone" in clone_cmd
        assert "git@github.com:user/repo.git" in clone_cmd

    def test_existing_pull(self):
        ctx = _ctx({
            "name": "my-app",
            "source": {"type": "git", "repository": "git@github.com:user/repo.git"},
        })
        with patch("fabrik.drivers.ssh.ssh") as mock_ssh, \
             patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps"):
            mock_ssh.side_effect = [
                "exists",  # test -d .git → exists
                "",  # ssh-keyscan github.com → known_hosts
                "",  # git pull
                "",  # docker compose build
                "",  # docker compose up -d
            ]
            deployer = SSHDeployer()
            deployer._deploy_git(ctx, "my-app", ctx.spec["source"], None)

        # Pull is now index 2 (after keyscan)
        pull_cmd = mock_ssh.call_args_list[2].args[0]
        assert "git pull" in pull_cmd

    def test_missing_repository_raises(self):
        ctx = _ctx({"name": "my-app", "source": {"type": "git"}})
        deployer = SSHDeployer()
        with pytest.raises(DeployError, match="repository"):
            deployer._deploy_git(ctx, "my-app", ctx.spec["source"], None)


# ======================================================================
# _deploy_docker — SSH-level assertions
# ======================================================================


class TestDeployDocker:
    def test_generates_compose_and_deploys(self):
        ctx = _ctx({
            "name": "my-app",
            "source": {"type": "docker", "image": "nginx:latest", "image_port": 80},
            "domain": "my-app.example.com",
        })
        with patch("fabrik.drivers.ssh.ssh") as mock_ssh, \
             patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps") as mock_write:
            mock_ssh.return_value = ""
            deployer = SSHDeployer()
            deployer._deploy_docker(ctx, "my-app", ctx.spec["source"], None)

        # Should write compose.yaml and .env
        write_calls = {c.args[1] for c in mock_write.call_args_list}
        assert "compose.yaml" in write_calls
        assert ".env" in write_calls

    def test_missing_image_raises(self):
        ctx = _ctx({"name": "my-app", "source": {"type": "docker"}, "domain": ""})
        deployer = SSHDeployer()
        with pytest.raises(DeployError, match="image"):
            deployer._deploy_docker(ctx, "my-app", ctx.spec["source"], None)


# ======================================================================
# _deploy_local — SSH-level assertions
# ======================================================================


class TestDeployLocal:
    def test_writes_env_and_up(self):
        ctx = _ctx({
            "name": "my-app",
            "source": {"type": "local", "path": "/opt/my-app"},
        })
        with patch("fabrik.drivers.ssh.ssh") as mock_ssh, \
             patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps_path") as mock_write:
            mock_ssh.side_effect = [
                "exists",  # test -f compose.yaml
                "",  # docker compose up -d
            ]
            deployer = SSHDeployer()
            deployer._deploy_local(ctx, "my-app", ctx.spec["source"], None)

        mock_write.assert_called_once()
        assert mock_write.call_args[0][0] == "/opt/my-app"

    def test_missing_compose_raises(self):
        ctx = _ctx({
            "name": "my-app",
            "source": {"type": "local", "path": "/opt/my-app"},
        })
        with patch("fabrik.drivers.ssh.ssh", side_effect=RuntimeError("no file")):
            deployer = SSHDeployer()
            with pytest.raises(DeployError, match="no compose.yaml found"):
                deployer._deploy_local(ctx, "my-app", ctx.spec["source"], None)

    def test_default_path_from_name(self):
        ctx = _ctx({
            "name": "my-app",
            "source": {"type": "local"},
        })
        with patch("fabrik.drivers.ssh.ssh") as mock_ssh, \
             patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps_path"):
            mock_ssh.side_effect = ["exists", ""]
            deployer = SSHDeployer()
            deployer._deploy_local(ctx, "my-app", ctx.spec["source"], None)

        # Should check /opt/my-app/compose.yaml
        test_cmd = mock_ssh.call_args_list[0].args[0]
        assert "/opt/my-app/compose.yaml" in test_cmd


# ======================================================================
# _build_env_content — read-merge strategy
# ======================================================================


class TestBuildEnvContent:
    def test_new_deploy_no_existing(self):
        ctx = _ctx({"name": "my-app", "env": {"PORT": "8000"}})
        ctx.secrets = {"API_KEY": "secret123"}

        deployer = SSHDeployer()
        result = deployer._build_env_content(ctx, "my-app", existing=None)

        parsed = _parse_env(result)
        assert parsed["PORT"] == "8000"
        assert parsed["API_KEY"] == "secret123"

    def test_update_preserves_existing(self):
        """Read-merge: existing VPS vars preserved, spec vars overlaid."""
        existing_env = "SENTRY_DSN=https://old@glitchtip/1\nREDIS_URL=redis://redis-main:6379/3\n"
        ctx = _ctx({"name": "my-app", "env": {"PORT": "8000"}})
        ctx.secrets = {"API_KEY": "secret123"}

        with patch("fabrik.drivers.ssh.ssh", return_value=existing_env):
            deployer = SSHDeployer()
            result = deployer._build_env_content(
                ctx, "my-app",
                existing={"name": "my-app", "status": "", "path": "/opt/my-app"},
            )

        parsed = _parse_env(result)
        # Existing vars preserved
        assert parsed["SENTRY_DSN"] == "https://old@glitchtip/1"
        assert parsed["REDIS_URL"] == "redis://redis-main:6379/3"
        # New vars added
        assert parsed["PORT"] == "8000"
        assert parsed["API_KEY"] == "secret123"

    def test_secrets_override_spec_env(self):
        """Secrets take precedence over spec env."""
        ctx = _ctx({"name": "my-app", "env": {"API_KEY": "from-spec"}})
        ctx.secrets = {"API_KEY": "from-secrets"}

        deployer = SSHDeployer()
        result = deployer._build_env_content(ctx, "my-app", existing=None)

        parsed = _parse_env(result)
        assert parsed["API_KEY"] == "from-secrets"

    def test_secrets_override_existing(self):
        """Secrets override even existing VPS vars."""
        existing_env = "API_KEY=old-value\n"
        ctx = _ctx({"name": "my-app", "env": {}})
        ctx.secrets = {"API_KEY": "new-secret"}

        with patch("fabrik.drivers.ssh.ssh", return_value=existing_env):
            deployer = SSHDeployer()
            result = deployer._build_env_content(
                ctx, "my-app",
                existing={"name": "my-app", "status": "", "path": "/opt/my-app"},
            )

        parsed = _parse_env(result)
        assert parsed["API_KEY"] == "new-secret"

    def test_ssh_failure_on_read_degrades_gracefully(self):
        """If reading existing .env fails, proceed with spec env + secrets only."""
        ctx = _ctx({"name": "my-app", "env": {"PORT": "8000"}})
        ctx.secrets = {}

        with patch("fabrik.drivers.ssh.ssh", side_effect=RuntimeError("SSH timeout")):
            deployer = SSHDeployer()
            result = deployer._build_env_content(
                ctx, "my-app",
                existing={"name": "my-app", "status": "", "path": "/opt/my-app"},
            )

        parsed = _parse_env(result)
        assert parsed["PORT"] == "8000"


# ======================================================================
# _destroy_compose (in destroyer.py)
# ======================================================================


class TestDestroyCompose:
    def test_dry_run(self):
        from fabrik.orchestrator.destroyer import _destroy_compose

        result = _destroy_compose("my-app", dry_run=True)
        assert result.status == "dry_run"
        assert result.step == "compose"

    def test_invalid_name(self):
        from fabrik.orchestrator.destroyer import _destroy_compose

        result = _destroy_compose("BAD NAME!", dry_run=False)
        assert result.status == "error"
        assert "invalid" in result.error.lower()

    def test_not_found(self):
        from fabrik.orchestrator.destroyer import _destroy_compose

        with patch("fabrik.drivers.ssh.ssh", side_effect=RuntimeError("no dir")):
            result = _destroy_compose("my-app", dry_run=False)

        assert result.status == "not_found"

    def test_removed_successfully(self):
        from fabrik.orchestrator.destroyer import _destroy_compose

        with patch("fabrik.drivers.ssh.ssh") as mock_ssh:
            mock_ssh.return_value = ""
            result = _destroy_compose("my-app", dry_run=False)

        assert result.status == "removed"
        cmds = [c.args[0] for c in mock_ssh.call_args_list]
        # default drop_data=False → plain down (app-local volumes preserved)
        assert any("docker compose down" in c and " -v" not in c for c in cmds)
        assert any("rm -rf /opt/my-app" in c for c in cmds)
        assert any("docker image prune" in c for c in cmds)


class TestDestroyApp:
    def test_compose_found_no_fallback(self):
        from fabrik.orchestrator.destroyer import _destroy_app

        with patch("fabrik.drivers.ssh.ssh", return_value=""):
            result = _destroy_app("my-app", dry_run=False)

        assert result.status == "removed"
        assert result.step == "compose"

    def test_compose_not_found_surfaces_directly(self):
        """No Coolify fallback: a missing /opt/<name> returns the compose
        not_found result directly (the legacy Coolify-API path was removed
        post-migration — it could only fail or hit a stale endpoint)."""
        from fabrik.orchestrator.destroyer import _destroy_app

        # `test -d /opt/my-app` failing → _destroy_compose returns not_found
        with patch("fabrik.drivers.ssh.ssh", side_effect=RuntimeError("no dir")):
            result = _destroy_app("my-app", dry_run=False)

        assert result.status == "not_found"
        assert result.step == "compose"

    def test_drop_data_gates_volume_removal(self):
        """down -v only when drop_data=True; plain down otherwise, so a
        non-drop-data destroy never deletes app-local named volumes."""
        from fabrik.orchestrator.destroyer import _destroy_compose

        calls = []

        def fake_ssh(cmd, timeout=60):
            calls.append(cmd)
            return ""

        with patch("fabrik.drivers.ssh.ssh", side_effect=fake_ssh):
            _destroy_compose("my-app", dry_run=False, drop_data=False)
        assert any("compose down" in c and " -v" not in c for c in calls)

        calls.clear()
        with patch("fabrik.drivers.ssh.ssh", side_effect=fake_ssh):
            _destroy_compose("my-app", dry_run=False, drop_data=True)
        assert any("compose down -v" in c for c in calls)


# ======================================================================
# W-Multi M4 — target_vps routing
# ======================================================================


class TestTargetVpsRouting:
    """Verify that ctx.target_vps env-swaps FABRIK_VPS_SSH_HOST around the
    deployer's app-targeted calls (``deploy`` and ``inject_env``).

    W14 (2026-06-02): the env-swap is intentionally scoped to ``deploy()``
    and ``inject_env()`` only — i.e. the calls that target the app's
    location on the spoke. Hub-side registrars (gatus, postgres-main,
    authelia) run outside this scope and stay on vps1. An earlier W14
    iteration hoisted the swap up to ``DeploymentOrchestrator.deploy()``,
    which broke hub-side registrars when target_vps != vps1; that hoist
    was reverted and the swap re-applied here + extended to inject_env.
    """

    def test_target_vps_vps2_sets_env(self):
        """When target_vps='vps2', _deploy_inner sees FABRIK_VPS_SSH_HOST=vps2."""
        import os

        os.environ.pop("FABRIK_VPS_SSH_HOST", None)
        ctx = DeploymentContext(spec_path=Path("/tmp/x"))
        ctx.spec = {"name": "app", "source": {"type": "template"}}
        ctx.target_vps = "vps2"
        ctx.dry_run = True

        deployer = SSHDeployer()
        seen = []
        real = deployer._deploy_inner

        def spy(c):
            seen.append(os.environ.get("FABRIK_VPS_SSH_HOST"))
            return real(c)

        deployer._deploy_inner = spy
        deployer.deploy(ctx)
        assert seen[0] == "vps2"

    def test_target_vps_vps1_does_not_swap(self):
        """target_vps='vps1' is the hub default — no env-swap should occur."""
        import os

        os.environ.pop("FABRIK_VPS_SSH_HOST", None)
        ctx = DeploymentContext(spec_path=Path("/tmp/x"))
        ctx.spec = {"name": "app", "source": {"type": "template"}}
        ctx.target_vps = "vps1"
        ctx.dry_run = True

        deployer = SSHDeployer()
        seen = []
        real = deployer._deploy_inner

        def spy(c):
            seen.append(os.environ.get("FABRIK_VPS_SSH_HOST"))
            return real(c)

        deployer._deploy_inner = spy
        deployer.deploy(ctx)
        assert seen[0] is None

    def test_env_restored_after_deploy(self):
        """Pre-existing FABRIK_VPS_SSH_HOST restored after deploy returns."""
        import os

        os.environ["FABRIK_VPS_SSH_HOST"] = "prior-alias"
        try:
            ctx = DeploymentContext(spec_path=Path("/tmp/x"))
            ctx.spec = {"name": "app", "source": {"type": "template"}}
            ctx.target_vps = "vps2"
            ctx.dry_run = True
            SSHDeployer().deploy(ctx)
            assert os.environ.get("FABRIK_VPS_SSH_HOST") == "prior-alias"
        finally:
            os.environ.pop("FABRIK_VPS_SSH_HOST", None)

    def test_inject_env_swaps_for_spoke(self):
        """inject_env must env-swap to ctx.target_vps too (W14 motivation).

        Without this swap, post-deploy registrars (GlitchTip DSN, Redis URL)
        on a spoke-targeted app try to mv .env into /opt/<app>/ on vps1
        where the directory does not exist — the inject_env call fails and
        the orchestrator rolls back a healthy spoke deploy.
        """
        import os

        import fabrik.orchestrator.deployer_ssh as mod

        os.environ.pop("FABRIK_VPS_SSH_HOST", None)
        ctx = DeploymentContext(spec_path=Path("/tmp/x"))
        ctx.spec = {"name": "app", "source": {"type": "docker"}}
        ctx.target_vps = "vps2"
        ctx.dry_run = False  # dry_run short-circuits before the swap window
        ctx.app_name = "app"

        seen = {}
        real_write = mod._write_file_to_vps

        def fake_write(name, fname, content):
            seen["env"] = os.environ.get("FABRIK_VPS_SSH_HOST")
            raise RuntimeError("stop-after-checking-env")

        mod._write_file_to_vps = fake_write
        try:
            try:
                SSHDeployer().inject_env(ctx, {"X": "1"})
            except RuntimeError as e:
                assert "stop-after-checking-env" in str(e)
            assert seen.get("env") == "vps2"
            # And env must be restored after the contextmanager exits.
            assert os.environ.get("FABRIK_VPS_SSH_HOST") is None
        finally:
            mod._write_file_to_vps = real_write
            os.environ.pop("FABRIK_VPS_SSH_HOST", None)
