"""Tests for SSH + Docker Compose deployer (deployer_ssh.py).

Covers: _parse_env, _format_env, _validate_name, _validate_compose,
_generate_docker_compose, _build_env_content, and all SSHDeployer
public methods (deploy, find_existing, delete, inject_env, redeploy)
with mocked SSH.
"""

from __future__ import annotations

import contextlib
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.deployer_ssh import (
    _NO_COMPOSE_FILE,
    SSHDeployer,
    _assert_claude_cli_mounts,
    _assert_deployed_env_present,
    _format_env,
    _generate_docker_compose,
    _parse_env,
    _read_compose_from_vps,
    _validate_compose,
    _validate_name,
    claude_cli_mount_lines,
)
from fabrik.orchestrator.exceptions import DeployError

_MKTEMP_PATH = "/tmp/fabrik-Ab3dE5gH9k"


def _fake_remote(cmds: list[str]):
    """An ssh stand-in: `mktemp` answers with a fixed path; every other command is recorded."""

    def run(cmd, timeout=10):
        if cmd.startswith("mktemp "):
            return _MKTEMP_PATH + "\n"
        cmds.append(cmd)
        return ""

    return run


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


class TestReadComposeFromVps:
    def test_a_non_text_read_is_refused(self):
        """W-51d6c153: an ssh patch with no return value hands back a MagicMock; the reader
        refuses it rather than passing a never-ending `.read` on to the YAML parser."""
        with patch("fabrik.drivers.ssh.ssh"), pytest.raises(DeployError, match="not text"):
            _read_compose_from_vps("my-app")

    def test_text_is_returned(self):
        """Read with sudo (the template path writes the rendered compose root:root 0600) through a
        shell probe that prints a sentinel for an absent file (W-51d6c153 critiques + review)."""
        with patch("fabrik.drivers.ssh.ssh", return_value="services: {}\n") as mock_ssh:
            assert _read_compose_from_vps("my-app") == "services: {}\n"
        cmd = mock_ssh.call_args.args[0]
        assert cmd.startswith("sudo sh -c ") and "cat /opt/my-app/compose.yaml" in cmd, cmd

    @pytest.mark.parametrize(
        ("files", "expected"),
        [
            ({"compose.yml": "b: 1\n"}, "b: 1"),  # compose.yaml absent -> the next name
            ({"compose.yaml": "", "compose.yml": "b: 1\n"}, ""),  # first EXISTING file, even empty
            ({"docker-compose.yml": "c: 1\n", "docker-compose.yaml": "d: 1\n"}, "c: 1"),
        ],
    )
    def test_the_real_shell_probe_finds_the_first_existing_file(self, tmp_path, files, expected):
        """The probe's own shell text is graded, not a mocked sentinel: the command runs through a
        local `sh` with /opt/my-app mapped to a tmp dir (a bare `cat` revert stays red here)."""
        app = tmp_path / "my-app"
        app.mkdir()
        for name, body in files.items():
            (app / name).write_text(body)

        def local_ssh(cmd, timeout=10):
            assert cmd.startswith("sudo "), cmd
            run = subprocess.run(
                ["sh", "-c", cmd[len("sudo ") :].replace("/opt/my-app", str(app))],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if run.returncode != 0:
                raise RuntimeError(run.stderr)
            return run.stdout.strip()  # the real driver strips stdout

        with patch("fabrik.drivers.ssh.ssh", side_effect=local_ssh):
            assert _read_compose_from_vps("my-app") == expected

    def test_an_absent_file_moves_to_the_next_name(self):
        with patch(
            "fabrik.drivers.ssh.ssh", side_effect=[_NO_COMPOSE_FILE, "services: {}\n"]
        ) as mock_ssh:
            assert _read_compose_from_vps("my-app") == "services: {}\n"
        assert "compose.yml" in mock_ssh.call_args_list[1].args[0]

    @pytest.mark.parametrize(
        "failure",
        [RuntimeError("Permission denied"), subprocess.TimeoutExpired(["ssh"], 15), OSError("ssh")],
    )
    def test_an_unreadable_existing_file_refuses_and_never_falls_through(self, failure):
        """A failed read of compose.yaml must not fall through to a stale docker-compose.yml —
        `up` would run the unchecked compose.yaml (review pass 1, executed by a seat)."""
        with (
            patch("fabrik.drivers.ssh.ssh", side_effect=[failure, "services: {}\n"]) as mock_ssh,
            pytest.raises(DeployError, match="Cannot read /opt/my-app/compose.yaml"),
        ):
            _read_compose_from_vps("my-app")
        assert mock_ssh.call_count == 1

    def test_restart_turns_a_read_timeout_into_a_deploy_error(self):
        """The real reader under restart(): a timed-out read is a DeployError, never a raw
        TimeoutExpired, and nothing is started."""
        with (
            patch(
                "fabrik.drivers.ssh.ssh", side_effect=[subprocess.TimeoutExpired(["ssh"], 15)]
            ) as mock_ssh,
            pytest.raises(DeployError, match="Cannot read"),
        ):
            SSHDeployer().restart("my-app")
        assert mock_ssh.call_count == 1


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
    @pytest.mark.parametrize("content", [None, b"services: {}\n", 42, ["services"]])
    def test_non_text_content_is_refused_up_front(self, content):
        """W-51d6c153: yaml.safe_load streams from anything with a `.read`, and a MagicMock's
        `.read` never returns empty — an unguarded call grew to 32 GB and killed WSL twice. The
        guard answers before the parser sees the object."""
        errors = _validate_compose(content)
        assert errors and "not text" in errors[0], errors

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

    @pytest.mark.parametrize(
        "env_block",
        [
            "    environment:\n      DATABASE_URL: postgresql://u:p@localhost:5432/db\n",
            "    environment:\n      - DATABASE_URL=postgresql://u:p@localhost:5432/db\n",
            "    environment:\n      - REDIS_URL=${REDIS_URL:-redis://localhost:6379/0}\n",
        ],
        ids=["mapping", "list", "list-default"],
    )
    def test_localhost_dsn_refused_in_either_environment_form(self, env_block):
        """The list form (`- KEY=value`, the fleet's documented shape) was never checked, so a
        localhost DSN in it read as clean (brand-identiy-creator 01M482YX)."""
        compose = self._valid_compose().replace(
            "    networks:\n      - fabrik\n", env_block + "    networks:\n      - fabrik\n", 1
        )
        errors = _validate_compose(compose)
        assert any("localhost" in e for e in errors), errors

    @pytest.mark.parametrize(
        "hc_block",
        [
            "    healthcheck:\n      disable: true\n",
            '    healthcheck:\n      disable: "true"\n',
            '    healthcheck:\n      test: ["NONE"]\n',
            "    healthcheck:\n      test: NONE\n",
            "    healthcheck:\n      test: []\n",
        ],
        ids=["disable-bool", "disable-string", "test-none-list", "test-none-string", "test-empty"],
    )
    def test_disabled_healthcheck_refused_before_compose_up_wait(self, hc_block):
        """A disabled healthcheck makes `docker compose up -d --wait` exit 1 ("has no healthcheck
        configured", measured on compose 2.40.3 for disable: true, disable: "true" and
        test: ["NONE"]); every git and redeploy path runs --wait, so each spelling is refused
        before `up`. A liveness probe, or no healthcheck block at all, still passes."""
        disabled = self._valid_compose().replace(
            "    networks:\n      - fabrik\n", hc_block + "    networks:\n      - fabrik\n", 1
        )
        assert any("disabled healthcheck" in e for e in _validate_compose(disabled))
        probe = self._valid_compose().replace(
            "    networks:\n      - fabrik\n",
            '    healthcheck:\n      test: ["CMD-SHELL", "kill -0 1"]\n    networks:\n      - fabrik\n',
            1,
        )
        assert _validate_compose(probe) == []

    def test_an_empty_string_healthcheck_test_is_not_refused(self):
        """compose runs `test: ""` as `CMD-SHELL ""`, which exits 0 and passes `--wait` (measured,
        compose 2.40.3) — a valid check, never a disabled one (review round 3 of ee2e55362)."""
        compose = self._valid_compose().replace(
            "    networks:\n      - fabrik\n",
            '    healthcheck:\n      test: ""\n    networks:\n      - fabrik\n',
            1,
        )
        assert _validate_compose(compose) == []

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
        with (
            patch("fabrik.drivers.ssh.ssh") as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps") as mock_write,
        ):
            mock_ssh.side_effect = ["present", "EXISTING=keep\nOLD_KEY=old\n", ""]

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


class TestSSHDeployerReadEnv:
    """``read_env`` feeds a DECISION (the app-role cutover) and ``inject_env``'s merge,
    so it never swallows a failure: absent file → ``{}``, anything else → raise."""

    def _ctx(self, target_vps: str | None = None) -> DeploymentContext:
        ctx = _ctx({"name": "my-app"})
        ctx.app_name = "my-app"
        ctx.target_vps = target_vps
        return ctx

    def test_present_file_is_parsed(self):
        with patch("fabrik.drivers.ssh.ssh") as mock_ssh:
            mock_ssh.side_effect = ["present\n", "DATABASE_URL=postgresql://u:x@h:5432/d\nA=1\n"]
            env = SSHDeployer().read_env(self._ctx())
        assert env == {"DATABASE_URL": "postgresql://u:x@h:5432/d", "A": "1"}
        assert "/opt/my-app/.env" in mock_ssh.call_args_list[0].args[0]

    def test_absent_file_is_empty(self):
        with patch("fabrik.drivers.ssh.ssh", return_value="absent\n") as mock_ssh:
            assert SSHDeployer().read_env(self._ctx()) == {}
        assert mock_ssh.call_count == 1  # no cat when test -f says absent

    def test_ssh_failure_raises(self):
        with (
            patch("fabrik.drivers.ssh.ssh", side_effect=RuntimeError("ssh down")),
            pytest.raises(DeployError, match="cannot read"),
        ):
            SSHDeployer().read_env(self._ctx())

    def test_cat_failure_raises(self):
        with (
            patch("fabrik.drivers.ssh.ssh", side_effect=["present", RuntimeError("perm")]),
            pytest.raises(DeployError, match="cannot read"),
        ):
            SSHDeployer().read_env(self._ctx())

    def test_unexpected_probe_output_raises(self):
        with (
            patch("fabrik.drivers.ssh.ssh", return_value="garbage"),
            pytest.raises(DeployError),
        ):
            SSHDeployer().read_env(self._ctx())

    def test_refused_sudo_is_not_absent(self):
        """A failing sudo must yield NO recognised answer: `sudo test -f … || echo absent`
        printed `absent` when sudo itself failed, and absent reads as `{}` (fixup O2)."""
        with (
            patch("fabrik.drivers.ssh.ssh", return_value="") as mock_ssh,
            pytest.raises(DeployError),
        ):
            SSHDeployer().read_env(self._ctx())
        probe = mock_ssh.call_args_list[0].args[0]
        assert probe.startswith("sudo sh -c ")
        assert "sudo test -f" not in probe

    def test_export_prefix_is_the_same_key(self):
        """`export DATABASE_URL=…` is the key DATABASE_URL, for read_env AND the merge (O9)."""
        content = "export DATABASE_URL=postgresql://u:x@h:5432/d\n"
        with patch("fabrik.drivers.ssh.ssh", side_effect=["present", content]):
            env = SSHDeployer().read_env(self._ctx())
        assert env == {"DATABASE_URL": "postgresql://u:x@h:5432/d"}
        with (
            patch("fabrik.drivers.ssh.ssh", side_effect=["present", content, ""]),
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps") as mock_write,
        ):
            SSHDeployer().inject_env(self._ctx(), {"DATABASE_URL": "postgresql://v:y@h:5432/d"})
        assert _parse_env(mock_write.call_args[0][2]) == {
            "DATABASE_URL": "postgresql://v:y@h:5432/d"
        }

    def test_quoted_value_with_trailing_comment(self):
        """`KEY="v" # note` is the bare value v — read_env and the merge (fixup r2 O9)."""
        content = 'DATABASE_URL="postgresql://shop_app:pw@h:5432/shop" # app role\n'
        with patch("fabrik.drivers.ssh.ssh", side_effect=["present", content]):
            env = SSHDeployer().read_env(self._ctx())
        assert env == {"DATABASE_URL": "postgresql://shop_app:pw@h:5432/shop"}
        with (
            patch("fabrik.drivers.ssh.ssh", side_effect=["present", content, ""]),
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps") as mock_write,
        ):
            SSHDeployer().inject_env(self._ctx(), {"OTHER": "1"})
        assert _parse_env(mock_write.call_args[0][2]) == {
            "DATABASE_URL": "postgresql://shop_app:pw@h:5432/shop",
            "OTHER": "1",
        }

    def test_quote_edge_cases_read_as_compose_reads_them(self):
        # single quotes + comment; escaped quote inside; unterminated; text after the closing quote
        # (W-2ae286e2: compose refuses an unterminated quote and ignores a quote tail, measured)
        assert _parse_env("A='x y' # c") == {"A": "x y"}
        assert _parse_env('B="say \\"hi\\"" # c') == {"B": 'say "hi"'}
        with pytest.raises(ValueError, match="unterminated"):
            _parse_env('C="unterminated # c')
        assert _parse_env('D="a" junk') == {"D": "a"}
        with pytest.raises(ValueError, match="after the closing quote"):
            _parse_env('D="a" "b"')

    def test_runs_inside_target_vps_env(self):
        import os

        os.environ.pop("FABRIK_VPS_SSH_HOST", None)
        seen: list[str | None] = []

        def fake_ssh(cmd, timeout=10):
            seen.append(os.environ.get("FABRIK_VPS_SSH_HOST"))
            return "absent"

        with patch("fabrik.drivers.ssh.ssh", side_effect=fake_ssh):
            SSHDeployer().read_env(self._ctx(target_vps="vps2"))
        assert seen == ["vps2"]
        assert os.environ.get("FABRIK_VPS_SSH_HOST") is None

    @pytest.mark.parametrize(
        "reads",
        [
            [RuntimeError("ssh down")],  # the probe itself fails
            ["present", RuntimeError("perm")],  # the file exists but `sudo cat` fails
            [""],  # a refused sudo answers nothing recognisable
        ],
    )
    def test_inject_env_raises_on_a_failed_read_and_writes_nothing(self, reads):
        """D7-registrar-O7: a failed read must never become an empty merge base — that
        wrote a .env holding ONLY the injected keys and dropped every other secret."""
        with (
            patch("fabrik.drivers.ssh.ssh", side_effect=reads),
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps") as mock_write,
            pytest.raises(DeployError, match="cannot read"),
        ):
            SSHDeployer().inject_env(self._ctx(), {"K": "v"})
        mock_write.assert_not_called()

    def test_inject_env_absent_file_writes_just_the_injected_keys(self):
        with (
            patch("fabrik.drivers.ssh.ssh", side_effect=["absent", ""]) as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps") as mock_write,
        ):
            SSHDeployer().inject_env(self._ctx(), {"K": "v"})
        assert _parse_env(mock_write.call_args[0][2]) == {"K": "v"}
        assert mock_ssh.call_count == 2  # probe, then compose up — no cat

    def test_inject_env_present_file_merges(self):
        with (
            patch("fabrik.drivers.ssh.ssh", side_effect=["present", "A=1\nK=old\n", ""]),
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps") as mock_write,
        ):
            SSHDeployer().inject_env(self._ctx(), {"K": "v"})
        assert _parse_env(mock_write.call_args[0][2]) == {"A": "1", "K": "v"}


class TestAssertDeployedEnvPresent:
    """W-6f690b90 review C1: every deploy path writes /opt/<name>/.env before up; restart and
    redeploy write none, so they refuse when it is gone instead of starting without it."""

    def test_present_passes(self):
        with patch("fabrik.drivers.ssh.ssh", return_value="present") as mock_ssh:
            assert _assert_deployed_env_present("my-app") is None
        assert mock_ssh.call_args.args[0].startswith("sudo sh -c ")

    @pytest.mark.parametrize(
        ("answer", "state"),
        [
            ("absent", "is absent"),
            ("", "is unconfirmed"),
            (None, "is unconfirmed"),
            (b"present", "is unconfirmed"),
            ("present\nextra", "is unconfirmed"),
        ],
    )
    def test_anything_but_present_refuses(self, answer, state):
        with (
            patch("fabrik.drivers.ssh.ssh", return_value=answer),
            pytest.raises(DeployError, match=rf"/opt/my-app/\.env {state}"),
        ):
            _assert_deployed_env_present("my-app")

    @pytest.mark.parametrize(
        "failure",
        [
            RuntimeError("Permission denied"),
            subprocess.TimeoutExpired(["ssh"], 15),
            OSError("ssh"),
            ValueError("bad host"),
        ],
    )
    def test_a_failed_probe_refuses(self, failure):
        with (
            patch("fabrik.drivers.ssh.ssh", side_effect=failure),
            pytest.raises(DeployError, match="Cannot check /opt/my-app/.env"),
        ):
            _assert_deployed_env_present("my-app")

    @pytest.mark.parametrize(
        ("make", "ok"),
        [("file", True), ("empty-file", True), ("none", False), ("dir", False)],
    )
    def test_the_real_shell_probe(self, tmp_path, make, ok):
        """The probe's own shell text runs through a local sh with /opt/my-app mapped to a tmp
        dir; an empty .env (a deploy with no keys) is present, a directory is not."""
        app = tmp_path / "my-app"
        app.mkdir()
        if make == "file":
            (app / ".env").write_text("K=v\n")
        elif make == "empty-file":
            (app / ".env").write_text("")
        elif make == "dir":
            (app / ".env").mkdir()

        def local_ssh(cmd, timeout=10):
            assert cmd.startswith("sudo "), cmd
            run = subprocess.run(
                ["sh", "-c", cmd[len("sudo ") :].replace("/opt/my-app", str(app))],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if run.returncode != 0:
                raise RuntimeError(run.stderr)
            return run.stdout.strip()

        with patch("fabrik.drivers.ssh.ssh", side_effect=local_ssh):
            if ok:
                _assert_deployed_env_present("my-app")
            else:
                with pytest.raises(DeployError, match="is absent"):
                    _assert_deployed_env_present("my-app")


class TestSSHDeployerRedeploy:
    """redeploy()/restart() validate /opt/<name>'s compose first (W-51d6c153); every test hands
    the read an explicit string, never an unconfigured mock (a MagicMock fed to the YAML parser
    reads forever — WSL went down twice on 2026-10-17)."""

    @staticmethod
    @contextlib.contextmanager
    def _compose(text: str = ""):
        """The compose read returns *text*; the .env presence probe passes (its own tests below)."""
        with (
            patch(
                "fabrik.orchestrator.deployer_ssh._read_compose_from_vps",
                return_value=text or _VALID_LOCAL_COMPOSE,
            ),
            patch("fabrik.orchestrator.deployer_ssh._assert_deployed_env_present"),
        ):
            yield

    _VIOLATING = "services:\n  web:\n    image: x\n    networks: [coolify]\n"

    def test_redeploy_refuses_a_violating_compose_before_up(self):
        with (
            self._compose(self._VIOLATING),
            patch("fabrik.drivers.ssh.ssh", return_value="") as mock_ssh,
            pytest.raises(
                DeployError, match=r"(?s)Compose validation failed for my-app.*limits.memory"
            ),
        ):
            SSHDeployer().redeploy("my-app", source_type="template")
        assert not any("compose up" in c.args[0] for c in mock_ssh.call_args_list)

    def test_git_redeploy_resets_to_old_sha_on_a_violating_compose(self):
        old = "a" * 40
        with (
            self._compose(self._VIOLATING),
            patch("fabrik.drivers.ssh.ssh", side_effect=[old + "\n", "", ""]) as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._persist_git_sha") as persist,
            pytest.raises(
                DeployError, match=r"(?s)Compose validation failed for my-app.*limits.memory"
            ),
        ):
            SSHDeployer().redeploy("my-app", source_type="git")
        cmds = [c.args[0] for c in mock_ssh.call_args_list]
        assert "git pull" in cmds[1], cmds
        assert cmds[2] == f"cd /opt/my-app && sudo git reset --hard {old}", cmds
        assert not any("compose build" in c or "compose up" in c for c in cmds), cmds
        persist.assert_not_called()

    def test_git_redeploy_resets_on_a_read_timeout_and_names_a_failed_reset(self):
        """A timed-out compose read still resets the checkout; a reset that fails is reported as
        a DeployError naming both errors — never the bare ssh error, never a silent skip."""
        import subprocess

        old = "b" * 40
        read_timeout = patch(
            "fabrik.orchestrator.deployer_ssh._read_compose_from_vps",
            side_effect=subprocess.TimeoutExpired(["ssh"], 15),
        )
        with (
            read_timeout,
            patch("fabrik.drivers.ssh.ssh", side_effect=[old + "\n", "", ""]) as mock_ssh,
            pytest.raises(DeployError, match=f"checkout reset to {old[:12]}"),
        ):
            SSHDeployer().redeploy("my-app", source_type="git")
        assert mock_ssh.call_args_list[2].args[0].endswith(f"git reset --hard {old}")

        with (
            self._compose(self._VIOLATING),
            patch(
                "fabrik.drivers.ssh.ssh",
                side_effect=[old + "\n", "", RuntimeError("index.lock")],
            ),
            pytest.raises(DeployError, match=r"(?s)AND the reset to .* failed.*index.lock"),
        ):
            SSHDeployer().redeploy("my-app", source_type="git")

    def test_git_redeploy_never_resets_to_a_non_sha(self):
        """A rev-parse answer that is not a 40-hex SHA never reaches the reset command."""
        with (
            self._compose(self._VIOLATING),
            patch("fabrik.drivers.ssh.ssh", side_effect=["fatal: ambiguous\n", ""]) as mock_ssh,
            pytest.raises(DeployError, match="no valid previous commit"),
        ):
            SSHDeployer().redeploy("my-app", source_type="git")
        assert not any("reset" in c.args[0] for c in mock_ssh.call_args_list)

    def test_restart_refuses_a_violating_compose(self):
        with (
            self._compose(self._VIOLATING),
            patch("fabrik.drivers.ssh.ssh", return_value="") as mock_ssh,
            pytest.raises(
                DeployError, match=r"(?s)Compose validation failed for my-app.*limits.memory"
            ),
        ):
            SSHDeployer().restart("my-app")
        mock_ssh.assert_not_called()

    def test_restart_refuses_when_the_deployed_env_is_absent(self):
        """W-6f690b90 review C1: the scaffold composes load .env as optional, so a missing
        /opt/<name>/.env would start an unconfigured stack that still reports healthy; restart
        refuses it before up."""
        with (
            patch(
                "fabrik.orchestrator.deployer_ssh._read_compose_from_vps",
                return_value=_VALID_LOCAL_COMPOSE,
            ),
            patch("fabrik.drivers.ssh.ssh", side_effect=["absent"]) as mock_ssh,
            pytest.raises(DeployError, match=r"/opt/my-app/\.env is absent"),
        ):
            SSHDeployer().restart("my-app")
        assert not any("compose up" in c.args[0] for c in mock_ssh.call_args_list)

    @pytest.mark.parametrize("source_type", ["template", "local"])
    def test_non_git_redeploy_refuses_when_the_deployed_env_is_absent(self, source_type):
        with (
            patch(
                "fabrik.orchestrator.deployer_ssh._read_compose_from_vps",
                return_value=_VALID_LOCAL_COMPOSE,
            ),
            patch("fabrik.drivers.ssh.ssh", side_effect=["absent"]) as mock_ssh,
            pytest.raises(DeployError, match=r"/opt/my-app/\.env is absent"),
        ):
            SSHDeployer().redeploy("my-app", source_type=source_type)
        assert not any("compose up" in c.args[0] for c in mock_ssh.call_args_list)

    def test_git_redeploy_resets_when_the_deployed_env_is_absent(self):
        old = "c" * 40
        with (
            patch(
                "fabrik.orchestrator.deployer_ssh._read_compose_from_vps",
                return_value=_VALID_LOCAL_COMPOSE,
            ),
            patch("fabrik.drivers.ssh.ssh", side_effect=[old + "\n", "", "absent", ""]) as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._persist_git_sha") as persist,
            pytest.raises(DeployError, match=rf"(?s)checkout reset to {old[:12]}.*\.env is absent"),
        ):
            SSHDeployer().redeploy("my-app", source_type="git")
        cmds = [c.args[0] for c in mock_ssh.call_args_list]
        assert cmds[3] == f"cd /opt/my-app && sudo git reset --hard {old}", cmds
        assert not any("compose build" in c or "compose up" in c for c in cmds), cmds
        persist.assert_not_called()

    def test_redeploy_template(self):
        with self._compose(), patch("fabrik.drivers.ssh.ssh") as mock_ssh:
            deployer = SSHDeployer()
            deployer.redeploy("my-app", source_type="template")

        cmds = [c.args[0] for c in mock_ssh.call_args_list]
        assert len(cmds) == 1
        assert "docker compose up -d" in cmds[0]
        assert "--force-recreate" not in cmds[0]

    def test_redeploy_template_force(self):
        with self._compose(), patch("fabrik.drivers.ssh.ssh") as mock_ssh:
            deployer = SSHDeployer()
            deployer.redeploy("my-app", source_type="template", force=True)

        cmds = [c.args[0] for c in mock_ssh.call_args_list]
        assert "--force-recreate" in cmds[0]

    def test_redeploy_git(self):
        with self._compose(), patch("fabrik.drivers.ssh.ssh", return_value="") as mock_ssh:
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
        with self._compose(), patch("fabrik.drivers.ssh.ssh", return_value="") as mock_ssh:
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
        ctx = _ctx(
            {
                "name": "my-app",
                "source": {"type": "template"},
                "template": "python-api",
                "domain": "my-app.example.com",
            }
        )
        deployer = SSHDeployer()
        with (
            patch.object(deployer, "find_existing", return_value=None),
            patch.object(deployer, "_deploy_template") as mock_tmpl,
        ):
            deployer.deploy(ctx)

        mock_tmpl.assert_called_once()
        assert ctx.coolify_uuid == "my-app"
        # New deploy should track resource
        compose_resources = ctx.get_resources_by_type("compose")
        assert len(compose_resources) == 1
        assert compose_resources[0].resource_id == "my-app"

    def test_dispatch_git(self):
        ctx = _ctx(
            {
                "name": "my-app",
                "source": {"type": "git", "repository": "git@github.com:user/repo.git"},
            }
        )
        deployer = SSHDeployer()
        with (
            patch.object(deployer, "find_existing", return_value=None),
            patch.object(deployer, "_deploy_git") as mock_git,
        ):
            deployer.deploy(ctx)

        mock_git.assert_called_once()

    def test_dispatch_docker(self):
        ctx = _ctx(
            {
                "name": "my-app",
                "source": {"type": "docker", "image": "nginx:latest"},
                "domain": "my-app.example.com",
            }
        )
        deployer = SSHDeployer()
        with (
            patch.object(deployer, "find_existing", return_value=None),
            patch.object(deployer, "_deploy_docker") as mock_docker,
        ):
            deployer.deploy(ctx)

        mock_docker.assert_called_once()

    def test_dispatch_local(self):
        ctx = _ctx(
            {
                "name": "my-app",
                "source": {"type": "local", "path": "/opt/my-app"},
            }
        )
        deployer = SSHDeployer()
        with (
            patch.object(deployer, "find_existing", return_value=None),
            patch.object(deployer, "_deploy_local") as mock_local,
        ):
            deployer.deploy(ctx)

        mock_local.assert_called_once()

    def test_existing_app_no_resource_tracking(self):
        """Updating an existing app should NOT add a resource record."""
        ctx = _ctx({"name": "my-app", "source": {"type": "template"}})
        deployer = SSHDeployer()
        existing = {"name": "my-app", "status": "", "path": "/opt/my-app"}
        with (
            patch.object(deployer, "find_existing", return_value=existing),
            patch.object(deployer, "_deploy_template"),
        ):
            deployer.deploy(ctx)

        assert ctx.get_resources_by_type("compose") == []

    def test_source_type_from_source_object(self):
        """deploy() handles Source objects (not just dicts)."""
        from fabrik.spec_loader import Source, SourceType

        source_obj = Source(type=SourceType.LOCAL, path="/opt/my-app")
        ctx = _ctx({"name": "my-app", "source": source_obj})
        deployer = SSHDeployer()
        with (
            patch.object(deployer, "find_existing", return_value=None),
            patch.object(deployer, "_deploy_local") as mock_local,
        ):
            deployer.deploy(ctx)

        mock_local.assert_called_once()


# ======================================================================
# _deploy_git — SSH-level assertions
# ======================================================================


# A valid compose the git path reads back from the VPS for validation (D1, 2026-07-13).
_VALID_GIT_COMPOSE = (
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


class TestDeployGit:
    def test_new_clone(self):
        ctx = _ctx(
            {
                "name": "my-app",
                "source": {
                    "type": "git",
                    "repository": "git@github.com:user/repo.git",
                    "branch": "main",
                },
            }
        )
        with (
            patch("fabrik.drivers.ssh.ssh") as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps"),
        ):
            # test -d .git fails (not cloned yet)
            mock_ssh.side_effect = [
                RuntimeError("not exists"),  # test -d .git
                "",  # ssh-keyscan github.com → known_hosts (added 2026-05-31)
                "",  # git clone
                "a" * 40 + "\n",  # rev-parse HEAD → GIT_SHA in .env
                _VALID_GIT_COMPOSE,  # D1: cat compose.yaml (read back for validation)
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
        ctx = _ctx(
            {
                "name": "my-app",
                "source": {"type": "git", "repository": "git@github.com:user/repo.git"},
            }
        )
        with (
            patch("fabrik.drivers.ssh.ssh") as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps"),
        ):
            mock_ssh.side_effect = [
                "exists",  # test -d .git → exists
                "",  # ssh-keyscan github.com → known_hosts
                "",  # git pull
                "a" * 40 + "\n",  # rev-parse HEAD → GIT_SHA in .env
                _VALID_GIT_COMPOSE,  # D1: cat compose.yaml (read back for validation)
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
        ctx = _ctx(
            {
                "name": "my-app",
                "source": {"type": "docker", "image": "nginx:latest", "image_port": 80},
                "domain": "my-app.example.com",
            }
        )
        with (
            patch("fabrik.drivers.ssh.ssh") as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps") as mock_write,
        ):
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

# A compose that passes `_validate_compose` (W-807287f1: the local path now reads and validates it).
_VALID_LOCAL_COMPOSE = (
    "services:\n"
    "  my-app:\n"
    "    image: example/app:1\n"
    "    platform: linux/amd64\n"
    "    container_name: my-app\n"
    "    restart: unless-stopped\n"
    "    deploy:\n"
    "      resources:\n"
    "        limits:\n"
    "          memory: 256M\n"
    "    networks: [fabrik]\n"
    "networks:\n"
    "  fabrik:\n"
    "    external: true\n"
)


class TestDeployLocal:
    def test_writes_env_and_up(self):
        ctx = _ctx(
            {
                "name": "my-app",
                "source": {"type": "local", "path": "/opt/my-app"},
            }
        )
        with (
            patch("fabrik.drivers.ssh.ssh") as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps_path") as mock_write,
        ):
            mock_ssh.side_effect = [
                "exists",  # test -f compose.yaml
                _VALID_LOCAL_COMPOSE,  # sudo cat compose.yaml (validated)
                "absent",  # .env probe — a first deploy has none
                "",  # docker compose up -d
            ]
            deployer = SSHDeployer()
            deployer._deploy_local(ctx, "my-app", ctx.spec["source"], None)

        mock_write.assert_called_once()
        assert mock_write.call_args[0][0] == "/opt/my-app"

    def test_local_source_off_opt_keeps_registrar_injected_keys(self):
        """W-7ec31807: ``find_existing`` probes ``/opt/<name>`` only, so a local source living
        elsewhere arrives with ``existing=None``. The compose at ``source.path`` proves the app
        exists there, so its ``.env`` must be read and merged — rebuilding from spec env +
        secrets alone dropped every registrar-injected key, ``DATABASE_URL_OWNER`` included."""
        ctx = _ctx(
            {
                "name": "my-app",
                "source": {"type": "local", "path": "/srv/my-app"},
                "env": {"PORT": "8000"},
            }
        )
        ctx.secrets = {}
        existing_env = (
            "DATABASE_URL=postgresql://shop_app:apppw@postgres-main:5432/shop\n"
            "DATABASE_URL_OWNER=postgresql://shop:ownerpw@postgres-main:5432/shop\n"
        )
        with (
            patch("fabrik.drivers.ssh.ssh") as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps_path") as mock_write,
        ):
            mock_ssh.side_effect = [
                "exists",  # test -f /srv/my-app/compose.yaml
                _VALID_LOCAL_COMPOSE,  # sudo cat /srv/my-app/compose.yaml (validated)
                "present",  # .env probe
                existing_env,  # sudo cat /srv/my-app/.env
                "",  # docker compose up -d --wait
            ]
            SSHDeployer()._deploy_local(ctx, "my-app", ctx.spec["source"], None)

        # Owner split (2026-10-12 plan, D-754): the owner key rides the FIRST write, `.env.owner`;
        # the LAST write is `.env`, which never carries it.
        writes = [c.args for c in mock_write.call_args_list]
        assert [(p, f) for p, f, _ in writes] == [
            ("/srv/my-app", ".env.owner"),
            ("/srv/my-app", ".env"),
        ], writes
        owner = _parse_env(writes[0][2])
        assert owner == {"DATABASE_URL_OWNER": "postgresql://shop:ownerpw@postgres-main:5432/shop"}
        parsed = _parse_env(writes[-1][2])
        assert "DATABASE_URL_OWNER" not in parsed, "the owner key must never land in .env"
        assert parsed["DATABASE_URL"] == "postgresql://shop_app:apppw@postgres-main:5432/shop"
        assert parsed["PORT"] == "8000"

    def test_local_source_off_opt_env_probe_failure_aborts_before_writing(self):
        """W-7ec31807 mirror: the always-on ``.env`` read is fail-closed like the /opt path's —
        a probe that fails (e.g. a refused sudo) raises ``DeployError`` and nothing is written,
        never a silent rebuild from spec env + secrets."""
        ctx = _ctx({"name": "my-app", "source": {"type": "local", "path": "/srv/my-app"}})
        ctx.secrets = {}
        with (
            patch("fabrik.drivers.ssh.ssh") as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps_path") as mock_write,
        ):
            mock_ssh.side_effect = [
                "exists",
                _VALID_LOCAL_COMPOSE,
                RuntimeError("sudo: a password is required"),
            ]
            with pytest.raises(DeployError, match=r"/srv/my-app/\.env"):
                SSHDeployer()._deploy_local(ctx, "my-app", ctx.spec["source"], None)
        mock_write.assert_not_called()

    def test_missing_compose_raises(self):
        ctx = _ctx(
            {
                "name": "my-app",
                "source": {"type": "local", "path": "/opt/my-app"},
            }
        )
        with patch("fabrik.drivers.ssh.ssh", side_effect=RuntimeError("no file")):
            deployer = SSHDeployer()
            with pytest.raises(DeployError, match="no compose.yaml found"):
                deployer._deploy_local(ctx, "my-app", ctx.spec["source"], None)

    def test_uses_claude_cli_requires_mount_in_compose(self):
        """Wiring: _deploy_local enforces the claude mount for a uses_claude_cli service — a
        compose without it aborts the deploy (proves the validator is actually wired in, and
        that the mount check runs on the single compose read the validation already made)."""
        ctx = _ctx(
            {
                "name": "seo",
                "source": {"type": "local", "path": "/opt/seo"},
                "shape": {"uses_claude_cli": True, "claude_cli_home": "/home/appuser"},
            }
        )
        with patch("fabrik.drivers.ssh.ssh") as mock_ssh:
            mock_ssh.side_effect = [
                "exists",  # test -f compose.yaml
                _VALID_LOCAL_COMPOSE,  # cat compose.yaml — passes validation, NO claude mount
            ]
            deployer = SSHDeployer()
            with pytest.raises(DeployError, match="does not mount BOTH"):
                deployer._deploy_local(ctx, "seo", ctx.spec["source"], None)
        cats = [c.args[0] for c in mock_ssh.call_args_list if "cat " in c.args[0]]
        assert cats == ["sudo cat /opt/seo/compose.yaml"], cats

    def test_source_path_is_shell_quoted_in_every_command(self):
        """source.path is spec-supplied and reaches a root shell: a metacharacter stays inside
        one quoted word in the existence check, the compose read and the `cd` before `up`."""
        path = "/srv/a;echo INJECTED"
        ctx = _ctx({"name": "my-app", "source": {"type": "local", "path": path}})
        ctx.secrets = {}
        with (
            patch("fabrik.drivers.ssh.ssh") as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps_path"),
        ):
            mock_ssh.side_effect = ["exists", _VALID_LOCAL_COMPOSE, "absent", ""]
            SSHDeployer()._deploy_local(ctx, "my-app", ctx.spec["source"], None)
        cmds = [c.args[0] for c in mock_ssh.call_args_list]
        quoted_file = "'/srv/a;echo INJECTED/compose.yaml'"
        assert cmds[0] == f"test -f {quoted_file} && echo exists", cmds[0]
        assert cmds[1] == f"sudo cat {quoted_file}", cmds[1]
        assert cmds[-1].startswith("cd '/srv/a;echo INJECTED' && "), cmds[-1]

    def test_a_tilde_source_path_stays_expandable_in_every_command(self):
        """A leading ~/ is left for the remote shell (as the .env writer leaves it), while the
        rest of the path is still one quoted word — quoting the tilde would refuse every
        ~-rooted local source with "no compose.yaml found"."""
        ctx = _ctx({"name": "my-app", "source": {"type": "local", "path": "~/apps/my app"}})
        ctx.secrets = {}
        with (
            patch("fabrik.drivers.ssh.ssh") as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps_path"),
        ):
            mock_ssh.side_effect = ["exists", _VALID_LOCAL_COMPOSE, "absent", ""]
            SSHDeployer()._deploy_local(ctx, "my-app", ctx.spec["source"], None)
        cmds = [c.args[0] for c in mock_ssh.call_args_list]
        assert cmds[0] == "test -f ~/'apps/my app/compose.yaml' && echo exists", cmds[0]
        assert cmds[1] == "sudo cat ~/'apps/my app/compose.yaml'", cmds[1]
        assert cmds[-1].startswith("cd ~/'apps/my app' && "), cmds[-1]

    def test_compose_read_oserror_aborts_before_writing(self):
        """An OSError from the ssh driver (no ssh binary) refuses like any failed read."""
        ctx = _ctx({"name": "my-app", "source": {"type": "local", "path": "/srv/my-app"}})
        ctx.secrets = {}
        with (
            patch("fabrik.drivers.ssh.ssh") as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps_path") as mock_write,
        ):
            mock_ssh.side_effect = ["exists", FileNotFoundError("ssh")]
            with pytest.raises(DeployError, match=r"/srv/my-app/compose\.yaml"):
                SSHDeployer()._deploy_local(ctx, "my-app", ctx.spec["source"], None)
        mock_write.assert_not_called()

    def test_uses_claude_cli_with_both_mounts_deploys(self):
        """The positive half of the mount wiring: a valid compose that mounts both claude paths
        passes the single read's two checks and reaches `.env` + `up`."""
        compose = _VALID_LOCAL_COMPOSE.replace(
            "    networks: [fabrik]\n",
            "    networks: [fabrik]\n"
            "    volumes:\n"
            "      - /root/.claude:/home/appuser/.claude:ro\n"
            "      - /root/.claude.json:/home/appuser/.claude.json:ro\n",
        )
        ctx = _ctx(
            {
                "name": "seo",
                "source": {"type": "local", "path": "/opt/seo"},
                "shape": {"uses_claude_cli": True, "claude_cli_home": "/home/appuser"},
            }
        )
        ctx.secrets = {}
        with (
            patch("fabrik.drivers.ssh.ssh") as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps_path") as mock_write,
        ):
            mock_ssh.side_effect = ["exists", compose, "absent", ""]
            SSHDeployer()._deploy_local(ctx, "seo", ctx.spec["source"], None)
        mock_write.assert_called()
        assert "compose up" in mock_ssh.call_args_list[-1].args[0]

    def test_compose_read_timeout_aborts_before_writing(self):
        """A compose read that times out refuses like any other failed read; nothing written."""
        ctx = _ctx({"name": "my-app", "source": {"type": "local", "path": "/srv/my-app"}})
        ctx.secrets = {}
        with (
            patch("fabrik.drivers.ssh.ssh") as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps_path") as mock_write,
        ):
            mock_ssh.side_effect = ["exists", subprocess.TimeoutExpired(["ssh"], 10)]
            with pytest.raises(DeployError, match=r"/srv/my-app/compose\.yaml"):
                SSHDeployer()._deploy_local(ctx, "my-app", ctx.spec["source"], None)
        mock_write.assert_not_called()

    # W-807287f1: the local path validates its compose like the git/template/docker paths.
    _VIOLATING_COMPOSE = "services:\n  web:\n    image: x\n    networks: [coolify]\nnetworks:\n  coolify:\n    external: true\n"

    def test_invalid_compose_aborts_before_writing_or_up(self):
        """A compose missing the Fabrik invariants (memory limit, container_name, platform, the
        `fabrik` network) refuses with the validator's list — no `.env` write, no `compose up`."""
        ctx = _ctx({"name": "my-app", "source": {"type": "local", "path": "/srv/my-app"}})
        ctx.secrets = {}
        with (
            patch("fabrik.drivers.ssh.ssh") as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps_path") as mock_write,
        ):
            mock_ssh.side_effect = ["exists", self._VIOLATING_COMPOSE, "absent", ""]
            with pytest.raises(DeployError, match="Compose validation failed for my-app") as exc:
                SSHDeployer()._deploy_local(ctx, "my-app", ctx.spec["source"], None)
        assert "limits.memory" in str(exc.value)
        mock_write.assert_not_called()
        assert not any("compose up" in c.args[0] for c in mock_ssh.call_args_list)

    def test_compose_is_read_from_the_source_path(self):
        """The validated bytes come from `<source.path>/compose.yaml`, never `/opt/<name>`."""
        ctx = _ctx({"name": "my-app", "source": {"type": "local", "path": "/srv/my-app"}})
        ctx.secrets = {}
        with (
            patch("fabrik.drivers.ssh.ssh") as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps_path"),
        ):
            mock_ssh.side_effect = ["exists", _VALID_LOCAL_COMPOSE, "absent", ""]
            SSHDeployer()._deploy_local(ctx, "my-app", ctx.spec["source"], None)
        reads = [c.args[0] for c in mock_ssh.call_args_list if " cat " in f" {c.args[0]} "]
        assert reads and all("/srv/my-app/compose.yaml" in r for r in reads), reads
        assert not any("/opt/my-app" in c.args[0] for c in mock_ssh.call_args_list)

    def test_compose_read_failure_aborts_before_writing(self):
        """A compose read that fails (e.g. a refused sudo) refuses; nothing is written."""
        ctx = _ctx({"name": "my-app", "source": {"type": "local", "path": "/srv/my-app"}})
        ctx.secrets = {}
        with (
            patch("fabrik.drivers.ssh.ssh") as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps_path") as mock_write,
        ):
            mock_ssh.side_effect = ["exists", RuntimeError("sudo: a password is required")]
            with pytest.raises(DeployError, match=r"/srv/my-app/compose\.yaml"):
                SSHDeployer()._deploy_local(ctx, "my-app", ctx.spec["source"], None)
        mock_write.assert_not_called()

    def test_default_path_from_name(self):
        ctx = _ctx(
            {
                "name": "my-app",
                "source": {"type": "local"},
            }
        )
        with (
            patch("fabrik.drivers.ssh.ssh") as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps_path"),
        ):
            mock_ssh.side_effect = ["exists", _VALID_LOCAL_COMPOSE, "absent", ""]  # +compose read
            deployer = SSHDeployer()
            deployer._deploy_local(ctx, "my-app", ctx.spec["source"], None)

        # Should check /opt/my-app/compose.yaml
        test_cmd = mock_ssh.call_args_list[0].args[0]
        assert "/opt/my-app/compose.yaml" in test_cmd


# ======================================================================
# _build_env_content — read-merge strategy
# ======================================================================


class TestClaudeCliMounts:
    """shape.uses_claude_cli → the deployer REQUIRES the host's rotated ~/.claude mounted
    read-only (rotation-aware; never a static CLAUDE_CODE_OAUTH_TOKEN)."""

    def test_mount_lines_target_the_container_home(self):
        assert claude_cli_mount_lines("/home/appuser") == [
            "/home/ozgur/.claude:/home/appuser/.claude:ro",
            "/home/ozgur/.claude.json:/home/appuser/.claude.json:ro",
        ]

    def test_mount_lines_default_root(self):
        lines = claude_cli_mount_lines("/root")
        assert lines[0].endswith("/root/.claude:ro")
        assert lines[1].endswith("/root/.claude.json:ro")

    def test_noop_when_flag_off(self):
        _assert_claude_cli_mounts("services:\n  x: {}\n", {"shape": {}})
        _assert_claude_cli_mounts("anything", {})  # no shape at all

    def test_passes_when_both_mounts_present(self):
        compose = (
            "services:\n  seo:\n    volumes:\n"
            "      - /home/ozgur/.claude:/home/appuser/.claude:ro\n"
            "      - /home/ozgur/.claude.json:/home/appuser/.claude.json:ro\n"
        )
        spec = {"shape": {"uses_claude_cli": True, "claude_cli_home": "/home/appuser"}}
        _assert_claude_cli_mounts(compose, spec)  # must not raise

    def test_requires_both_mounts_not_just_the_first(self):
        """Regression: a compose with only ~/.claude:ro (missing ~/.claude.json:ro) must FAIL —
        `claude -p` exits 'config file not found' without the .json mount (watchdog.py:818)."""
        compose = (
            "services:\n  seo:\n    volumes:\n"
            "      - /home/ozgur/.claude:/home/appuser/.claude:ro\n"  # only the first mount
        )
        spec = {"shape": {"uses_claude_cli": True, "claude_cli_home": "/home/appuser"}}
        with pytest.raises(DeployError, match="BOTH"):
            _assert_claude_cli_mounts(compose, spec)

    def test_raises_with_snippet_when_mount_missing(self):
        spec = {"shape": {"uses_claude_cli": True, "claude_cli_home": "/home/appuser"}}
        with pytest.raises(DeployError, match="does not mount BOTH"):
            _assert_claude_cli_mounts("services:\n  seo:\n    volumes: []\n", spec)

    def test_static_token_without_mount_still_fails(self):
        """A CLAUDE_CODE_OAUTH_TOKEN env (no mount) does NOT satisfy the flag — it pins
        one account and ignores rotation."""
        compose = "services:\n  seo:\n    environment:\n      - CLAUDE_CODE_OAUTH_TOKEN=x\n"
        spec = {"shape": {"uses_claude_cli": True, "claude_cli_home": "/root"}}
        with pytest.raises(DeployError):
            _assert_claude_cli_mounts(compose, spec)


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

        with patch("fabrik.drivers.ssh.ssh", side_effect=["present", existing_env]):
            deployer = SSHDeployer()
            result = deployer._build_env_content(
                ctx,
                "my-app",
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

        with patch("fabrik.drivers.ssh.ssh", side_effect=["present", existing_env]):
            deployer = SSHDeployer()
            result = deployer._build_env_content(
                ctx,
                "my-app",
                existing={"name": "my-app", "status": "", "path": "/opt/my-app"},
            )

        parsed = _parse_env(result)
        assert parsed["API_KEY"] == "new-secret"

    @pytest.mark.parametrize(
        "reads",
        [
            [RuntimeError("SSH timeout")],  # the probe itself fails
            ["present", RuntimeError("perm")],  # the file exists but `sudo cat` fails
            [""],  # a refused sudo answers nothing recognisable
        ],
    )
    def test_failed_read_of_an_existing_env_raises(self, reads):
        """D7 r1b (O7's class on the redeploy path): a failed read of an EXISTING .env
        must never degrade to spec env + secrets — that rewrote .env without the
        registrar-injected keys, DATABASE_URL_OWNER (the only owner-password copy after
        a cutover) included. The deploy aborts before anything is written."""
        ctx = _ctx({"name": "my-app", "env": {"PORT": "8000"}})
        ctx.secrets = {}

        with (
            patch("fabrik.drivers.ssh.ssh", side_effect=reads),
            pytest.raises(DeployError, match="cannot read"),
        ):
            SSHDeployer()._build_env_content(
                ctx,
                "my-app",
                existing={"name": "my-app", "status": "", "path": "/opt/my-app"},
            )

    def test_failed_env_read_on_redeploy_writes_nothing(self):
        """Through the real deploy path: the .env read fails → DeployError, and no
        file (compose or .env) is written to the VPS."""
        ctx = _ctx({"name": "my-app", "source": {"type": "docker", "image": "nginx:1"}})
        ctx.secrets = {}

        def fake_ssh(cmd, timeout=10):
            if "[ -f" in cmd:
                raise RuntimeError("SSH timeout")
            return ""

        with (
            patch("fabrik.drivers.ssh.ssh", side_effect=fake_ssh),
            patch.object(
                SSHDeployer, "find_existing", return_value={"name": "my-app", "path": "/opt/my-app"}
            ),
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps") as mock_write,
            pytest.raises(DeployError, match="cannot read"),
        ):
            SSHDeployer().deploy(ctx)
        mock_write.assert_not_called()

    def test_absent_env_on_an_existing_app_builds_from_spec(self):
        ctx = _ctx({"name": "my-app", "env": {"PORT": "8000"}})
        ctx.secrets = {"API_KEY": "k"}

        with patch("fabrik.drivers.ssh.ssh", side_effect=["absent"]):
            result = SSHDeployer()._build_env_content(
                ctx,
                "my-app",
                existing={"name": "my-app", "status": "", "path": "/opt/my-app"},
            )

        assert _parse_env(result) == {"PORT": "8000", "API_KEY": "k"}

    def test_registrar_injected_keys_survive_a_redeploy(self):
        """DATABASE_URL and DATABASE_URL_OWNER are injected by the registrar, never named
        in the spec's env — a redeploy must carry them over unchanged."""
        existing_env = (
            "DATABASE_URL=postgresql://shop_app:apppw@postgres-main:5432/shop\n"
            "DATABASE_URL_OWNER=postgresql://shop:ownerpw@postgres-main:5432/shop\n"
        )
        ctx = _ctx({"name": "my-app", "env": {"PORT": "8000"}})
        ctx.secrets = {}

        with patch("fabrik.drivers.ssh.ssh", side_effect=["present", existing_env]):
            result = SSHDeployer()._build_env_content(
                ctx,
                "my-app",
                existing={"name": "my-app", "status": "", "path": "/opt/my-app"},
            )

        parsed = _parse_env(result)
        assert parsed["DATABASE_URL"] == "postgresql://shop_app:apppw@postgres-main:5432/shop"
        assert parsed["DATABASE_URL_OWNER"] == "postgresql://shop:ownerpw@postgres-main:5432/shop"
        assert parsed["PORT"] == "8000"

    def test_local_source_reads_its_own_path(self):
        """``_deploy_local`` passes ``app_path``: the read must target that path."""
        ctx = _ctx({"name": "my-app", "env": {}})
        ctx.secrets = {}

        with patch("fabrik.drivers.ssh.ssh", side_effect=["present", "A=1\n"]) as mock_ssh:
            result = SSHDeployer()._build_env_content(
                ctx, "my-app", existing={"name": "my-app"}, app_path="/srv/elsewhere"
            )

        assert _parse_env(result) == {"A": "1"}
        assert all("/srv/elsewhere/.env" in c.args[0] for c in mock_ssh.call_args_list)

    _PLACEHOLDER_DSN = "postgresql+asyncpg://placeholder:placeholder@postgres-main:5432/placeholder"

    def test_spec_placeholder_does_not_clobber_injected_real_value(self):
        """Regression (site-provisioner outage, 2026-08-02): a re-apply must NOT
        overwrite the registrar-injected real DATABASE_URL with the spec's
        placeholder — that breaks `compose up --wait` before the registrar can
        re-inject."""
        existing_env = (
            "DATABASE_URL=postgresql+asyncpg://real:s3cret@postgres-main:5432/real_db\n"
            "LOG_LEVEL=DEBUG\n"
        )
        ctx = _ctx(
            {"name": "my-app", "env": {"DATABASE_URL": self._PLACEHOLDER_DSN, "LOG_LEVEL": "INFO"}}
        )
        ctx.secrets = {}

        with patch("fabrik.drivers.ssh.ssh", side_effect=["present", existing_env]):
            deployer = SSHDeployer()
            result = deployer._build_env_content(
                ctx,
                "my-app",
                existing={"name": "my-app", "status": "", "path": "/opt/my-app"},
            )

        parsed = _parse_env(result)
        # the injected real DSN is preserved; the placeholder does NOT win
        assert (
            parsed["DATABASE_URL"] == "postgresql+asyncpg://real:s3cret@postgres-main:5432/real_db"
        )
        assert "placeholder:placeholder" not in result
        # a non-placeholder spec var still overrides existing (unchanged behavior)
        assert parsed["LOG_LEVEL"] == "INFO"

    def test_first_deploy_applies_placeholder_when_no_real_value(self):
        """First deploy (no existing real value) still gets the placeholder — the
        registrar fills it in post-deploy."""
        ctx = _ctx({"name": "my-app", "env": {"DATABASE_URL": self._PLACEHOLDER_DSN}})
        ctx.secrets = {}

        deployer = SSHDeployer()
        result = deployer._build_env_content(ctx, "my-app", existing=None)

        assert "placeholder:placeholder" in result

    def test_secret_still_overrides_placeholder(self):
        """A real value provided as a secret keeps highest precedence."""
        ctx = _ctx({"name": "my-app", "env": {"DATABASE_URL": self._PLACEHOLDER_DSN}})
        ctx.secrets = {"DATABASE_URL": "postgresql+asyncpg://from_secret:pw@postgres-main:5432/db"}

        deployer = SSHDeployer()
        result = deployer._build_env_content(ctx, "my-app", existing=None)

        assert "from_secret:pw" in result


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

        def fake_ssh(cmd, timeout=10):
            # The merge read goes through read_env: it must be patched (never the
            # live fleet) and must run on the spoke too.
            seen["read"] = os.environ.get("FABRIK_VPS_SSH_HOST")
            return "absent"

        mod._write_file_to_vps = fake_write
        try:
            try:
                with patch("fabrik.drivers.ssh.ssh", side_effect=fake_ssh):
                    SSHDeployer().inject_env(ctx, {"X": "1"})
            except RuntimeError as e:
                assert "stop-after-checking-env" in str(e)
            assert seen.get("read") == "vps2"
            assert seen.get("env") == "vps2"
            # And env must be restored after the contextmanager exits.
            assert os.environ.get("FABRIK_VPS_SSH_HOST") is None
        finally:
            mod._write_file_to_vps = real_write
            os.environ.pop("FABRIK_VPS_SSH_HOST", None)


class TestWriteFileToVpsPathNested:
    """A rendered key with a slash (`src/theme/SearchBar/index.js`) needs its remote parent dir:
    the writer `sudo mv`s into `{path}/{filename}`, and `mv` fails on a missing directory
    (plan 2026-10-01-plan-1-docusaurus-static-runtime, Phase A step 3b; D-476)."""

    def _run(self, filename: str) -> list[str]:
        from fabrik.orchestrator.deployer_ssh import _write_file_to_vps_path

        cmds: list[str] = []
        with (
            patch("fabrik.drivers.ssh.scp_to_vps"),
            patch("fabrik.drivers.ssh.ssh", side_effect=_fake_remote(cmds)),
        ):
            _write_file_to_vps_path("/opt/docs", filename, "content")
        return cmds

    # Exact commands, not substrings: a mkdir of the FILE path, or `;` / `||` in place of `&&`,
    # all still contain the expected fragments (the scoped review's escape variants S5-S7).
    @staticmethod
    def _tmp(filename: str) -> str:
        return _MKTEMP_PATH  # the remote mktemp's answer, whatever the filename

    def test_nested_key_creates_the_remote_parent_before_the_move(self) -> None:
        key = "src/theme/SearchBar/index.js"
        (cmd,) = self._run(key)
        dest = f"/opt/docs/{key}"
        assert cmd == (
            "sudo mkdir -p /opt/docs/src/theme/SearchBar && "
            f"sudo mv {self._tmp(key)} {dest} && sudo chown root:root {dest}"
        ), cmd

    def test_flat_key_command_is_unchanged(self) -> None:
        (cmd,) = self._run("Dockerfile")
        assert cmd == (
            f"sudo mv {self._tmp('Dockerfile')} /opt/docs/Dockerfile && "
            "sudo chown root:root /opt/docs/Dockerfile"
        ), cmd

    def test_a_nested_path_with_a_space_is_quoted(self) -> None:
        # Only the FILENAME part is quoted: the app dir is a hub value the same caller also uses
        # unquoted (`cd {path}`), so quoting it would stop a `~` from expanding (closing pass N1).
        (cmd,) = self._run("a b/c.js")
        assert cmd == (
            "sudo mkdir -p /opt/docs/'a b' && "
            f"sudo mv {self._tmp('a b/c.js')} /opt/docs/'a b/c.js' && "
            "sudo chown root:root /opt/docs/'a b/c.js'"
        ), cmd

    def test_a_tilde_app_dir_is_left_for_the_shell_to_expand(self) -> None:
        from fabrik.orchestrator.deployer_ssh import _write_file_to_vps_path

        cmds: list[str] = []
        with (
            patch("fabrik.drivers.ssh.scp_to_vps"),
            patch("fabrik.drivers.ssh.ssh", side_effect=_fake_remote(cmds)),
        ):
            _write_file_to_vps_path("~/apps/foo", ".env", "content")
        assert cmds == [
            f"sudo chmod 0600 {self._tmp('.env')} && "
            f"sudo mv {self._tmp('.env')} ~/apps/foo/.env && sudo chown root:root ~/apps/foo/.env"
        ], cmds

    @pytest.mark.parametrize("bad", ["../x", "/abs/x", "a/../../x", "", ".", "a/./b", "a//b", "a/"])
    def test_an_escaping_filename_is_refused_before_any_remote_call(self, bad: str) -> None:
        from fabrik.orchestrator.deployer_ssh import _write_file_to_vps_path

        with (
            patch("fabrik.drivers.ssh.scp_to_vps") as scp,
            patch("fabrik.drivers.ssh.ssh") as ssh,
            pytest.raises(ValueError, match="filename"),
        ):
            _write_file_to_vps_path("/opt/docs", bad, "content")
        scp.assert_not_called()
        ssh.assert_not_called()

    def test_the_remote_temp_file_comes_from_mktemp_never_a_pid_name(self) -> None:
        """W-8dd25072: a pid-derived /tmp name is predictable — a local VPS user could pre-create it
        0666 and read a DSN through the open fd. The temp file is made remotely by `mktemp` (O_EXCL,
        0600) BEFORE scp writes into it."""

        from fabrik.orchestrator.deployer_ssh import _write_file_to_vps_path

        order: list[str] = []

        def ssh(cmd, timeout=10):
            order.append(f"ssh:{cmd}")
            return _MKTEMP_PATH + "\n" if cmd.startswith("mktemp ") else ""

        with (
            patch("fabrik.drivers.ssh.ssh", side_effect=ssh),
            patch(
                "fabrik.drivers.ssh.scp_to_vps",
                side_effect=lambda local, remote, timeout=30: order.append(f"scp:{remote}"),
            ),
        ):
            _write_file_to_vps_path("/opt/x", ".env", "K=v\n")
        assert order[0] == "ssh:mktemp /tmp/fabrik-XXXXXXXXXX"
        assert order[1] == f"scp:{_MKTEMP_PATH}"
        assert len(order) == 3  # mktemp, scp, then the one chmod+mv+chown command

    @pytest.mark.parametrize(
        "answer", ["", "/tmp/fabrik-a b", "/etc/passwd", "/tmp/fabrik-x;rm -rf /", "/tmp/fabrik-"]
    )
    def test_an_unexpected_mktemp_answer_is_refused_before_scp(self, answer) -> None:
        from fabrik.orchestrator.deployer_ssh import _write_file_to_vps_path

        with (
            patch("fabrik.drivers.ssh.ssh", return_value=answer + "\n"),
            patch("fabrik.drivers.ssh.scp_to_vps") as scp,
            pytest.raises(RuntimeError, match="mktemp"),
        ):
            _write_file_to_vps_path("/opt/x", ".env", "K=v\n")
        scp.assert_not_called()

    def test_login_shell_noise_before_the_path_is_ignored(self) -> None:
        from fabrik.orchestrator.deployer_ssh import _write_file_to_vps_path

        with (
            patch("fabrik.drivers.ssh.ssh", return_value="Welcome to vps1\n" + _MKTEMP_PATH + "\n"),
            patch("fabrik.drivers.ssh.scp_to_vps") as scp,
        ):
            _write_file_to_vps_path("/opt/x", "compose.yaml", "services: {}\n")
        assert scp.call_args.args[1] == _MKTEMP_PATH

    def test_noise_after_the_path_is_refused_and_the_created_file_removed(self) -> None:
        from fabrik.orchestrator.deployer_ssh import _write_file_to_vps_path

        cmds: list[str] = []

        def ssh(cmd, timeout=10):
            if cmd.startswith("mktemp "):
                return _MKTEMP_PATH + "\nlogout\n"
            cmds.append(cmd)
            return ""

        with (
            patch("fabrik.drivers.ssh.ssh", side_effect=ssh),
            patch("fabrik.drivers.ssh.scp_to_vps") as scp,
            pytest.raises(RuntimeError, match="unexpected path"),
        ):
            _write_file_to_vps_path("/opt/x", ".env", "K=v\n")
        scp.assert_not_called()
        assert cmds == [f"rm -f {_MKTEMP_PATH}"]

    def test_a_local_temp_failure_never_creates_a_remote_file(self) -> None:
        from fabrik.orchestrator.deployer_ssh import _write_file_to_vps_path

        with (
            patch(
                "fabrik.orchestrator.deployer_ssh.tempfile.mkstemp",
                side_effect=OSError("disk full"),
            ),
            patch("fabrik.drivers.ssh.ssh") as ssh,
            pytest.raises(OSError, match="disk full"),
        ):
            _write_file_to_vps_path("/opt/x", ".env", "K=v\n")
        ssh.assert_not_called()

    def test_an_interrupt_during_scp_still_removes_the_remote_temp_file(self) -> None:
        from fabrik.orchestrator.deployer_ssh import _write_file_to_vps_path

        cmds: list[str] = []
        with (
            patch("fabrik.drivers.ssh.ssh", side_effect=_fake_remote(cmds)),
            patch("fabrik.drivers.ssh.scp_to_vps", side_effect=KeyboardInterrupt),
            pytest.raises(KeyboardInterrupt),
        ):
            _write_file_to_vps_path("/opt/x", ".env", "K=v\n")
        assert cmds == [f"rm -f {_MKTEMP_PATH}"]

    def test_a_failed_scp_removes_the_remote_temp_file(self) -> None:
        from fabrik.orchestrator.deployer_ssh import _write_file_to_vps_path

        cmds: list[str] = []
        with (
            patch("fabrik.drivers.ssh.ssh", side_effect=_fake_remote(cmds)),
            patch(
                "fabrik.drivers.ssh.scp_to_vps", side_effect=RuntimeError("scp: lost connection")
            ),
            pytest.raises(RuntimeError, match="lost connection"),
        ):
            _write_file_to_vps_path("/opt/x", ".env", "K=v\n")
        assert cmds == [f"rm -f {_MKTEMP_PATH}"]


# ======================================================================
# The owner DSN split — `.env.owner` (plan 2026-10-12-plan-1-owner-dsn-split, D-754)
# ======================================================================

_OWNER_DSN = "postgresql://shop:ownerpw@postgres-main:5432/shop"
_APP_DSN = "postgresql://shop_app:apppw@postgres-main:5432/shop"


class TestOwnerEnvSplit:
    """`DATABASE_URL_OWNER` lives in `/opt/<name>/.env.owner` and nowhere else on the VPS: one
    probe + one SEPARATED read, one writer (owner file FIRST, then `.env` without owner keys),
    `chmod 0600` on the temp file before the `mv`. Spec § The delta 1-3, 6."""

    def _ctx(self) -> DeploymentContext:
        ctx = _ctx({"name": "my-app"})
        ctx.app_name = "my-app"
        return ctx

    # G1 — the split write, owner first, one restart
    def test_g1_inject_env_writes_owner_file_first_then_env_then_one_restart(self, caplog):
        with (
            caplog.at_level("DEBUG", logger="fabrik.orchestrator.deployer_ssh"),
            patch("fabrik.drivers.ssh.ssh", side_effect=["absent", ""]) as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps") as mock_write,
        ):
            SSHDeployer().inject_env(
                self._ctx(), {"DATABASE_URL": _APP_DSN, "DATABASE_URL_OWNER": _OWNER_DSN}
            )
        writes = [c.args for c in mock_write.call_args_list]
        assert [(n, f) for n, f, _ in writes] == [("my-app", ".env.owner"), ("my-app", ".env")]
        assert _parse_env(writes[0][2]) == {"DATABASE_URL_OWNER": _OWNER_DSN}
        assert _parse_env(writes[1][2]) == {"DATABASE_URL": _APP_DSN}
        ups = [c for c in mock_ssh.call_args_list if "docker compose up" in c.args[0]]
        assert len(ups) == 1
        # No DSN value ever reaches the log (core/35; the Finish review, deployer-O5).
        assert "ownerpw" not in caplog.text and "apppw" not in caplog.text

    # G2 — the merged view in one probe + one (separated) read, the owner file winning
    def test_g2_read_env_merges_both_files_in_one_separated_read(self):
        answers = [
            "present\nowner\n",
            f"DATABASE_URL={_APP_DSN}\nDATABASE_URL_OWNER=stale\n\n__fabrik_env_owner_follows__\n"
            f"DATABASE_URL_OWNER={_OWNER_DSN}\n",
        ]
        with patch("fabrik.drivers.ssh.ssh", side_effect=answers) as mock_ssh:
            env = SSHDeployer().read_env(self._ctx())
        assert env == {"DATABASE_URL": _APP_DSN, "DATABASE_URL_OWNER": _OWNER_DSN}
        assert mock_ssh.call_count == 2
        assert mock_ssh.call_args_list[1].args[0] == (
            "sudo sh -c 'cat /opt/my-app/.env && echo && echo __fabrik_env_owner_follows__ && "
            "cat /opt/my-app/.env.owner'"
        )

    def test_g2_a_failed_two_file_read_raises_never_returns_the_owner_half(self):
        """Phase A review O1: the two-file read is chained with `&&`, so a failed `cat <env>` is a
        non-zero exit the ssh driver raises on, which the reader turns into DeployError; a `;` chain
        exits with the LAST cat's status and would have returned the owner keys alone as the merged
        view (executed in review: rc 0 under `;`, rc 1 under `&&`). The fake PLAYS THE SHELL: it
        raises only on the `&&` chain and returns the owner half with rc 0 for a `;` chain, so a `;`
        spelling makes the reader return instead of raise (review O8); the issued command is
        asserted too."""
        cmds: list[str] = []

        def ssh(cmd, timeout=10):
            # The fake plays the SHELL: a `&&` chain whose first `cat` fails exits non-zero (the
            # driver raises); a `;` chain would run on and print the owner half with rc 0.
            cmds.append(cmd)
            if len(cmds) == 1:
                return "present\nowner\n"
            if " && echo && echo " in cmd:
                raise RuntimeError("SSH to 'vps1' failed (rc=1): cat: .env: Permission denied")
            return f"\nDATABASE_URL_OWNER={_OWNER_DSN}\n"

        with (
            patch("fabrik.drivers.ssh.ssh", side_effect=ssh),
            pytest.raises(DeployError, match="cannot read"),
        ):
            SSHDeployer().read_env(self._ctx())
        assert len(cmds) == 2
        assert cmds[1] == (
            "sudo sh -c 'cat /opt/my-app/.env && echo && echo __fabrik_env_owner_follows__ && "
            "cat /opt/my-app/.env.owner'"
        )
        assert "; echo;" not in cmds[1] and "&& echo &&" in cmds[1]

    def test_g2_bare_present_answer_issues_todays_cat_exactly(self):
        with patch("fabrik.drivers.ssh.ssh", side_effect=["present\n", "A=1\n"]) as mock_ssh:
            assert SSHDeployer().read_env(self._ctx()) == {"A": "1"}
        assert mock_ssh.call_args_list[1].args[0] == "sudo cat /opt/my-app/.env"

    # G2b — the separator is load-bearing: a plain two-file `cat` joins lines when `.env` lacks
    # a trailing newline (the approval panel's executed reproduction, kept as the negative half)
    def test_g2b_plain_join_loses_the_owner_key_and_the_separated_join_keeps_it(self):
        env_no_newline = f"DATABASE_URL={_APP_DSN}\nREDIS_URL=redis://r:6379/0"
        owner = f"DATABASE_URL_OWNER={_OWNER_DSN}\n"
        joined = _parse_env(env_no_newline + owner)
        assert "DATABASE_URL_OWNER" not in joined
        assert joined["REDIS_URL"].endswith(f"DATABASE_URL_OWNER={_OWNER_DSN}")
        separated = _parse_env(env_no_newline + "\n" + owner)
        assert separated == {
            "DATABASE_URL": _APP_DSN,
            "REDIS_URL": "redis://r:6379/0",
            "DATABASE_URL_OWNER": _OWNER_DSN,
        }

    # G3 — the one writer: owner first, `.env` without owner keys, one log line
    def test_g3_write_env_files_splits_owner_first_and_logs_once(self, caplog):
        from fabrik.orchestrator.deployer_ssh import _write_env_files

        writes: list[tuple[str, str, str]] = []

        def write(path: str, filename: str, content: str) -> None:
            writes.append((path, filename, content))

        with caplog.at_level("INFO", logger="fabrik.orchestrator.deployer_ssh"):
            _write_env_files(
                "/opt/x",
                {"DATABASE_URL": _APP_DSN, "DATABASE_URL_OWNER": _OWNER_DSN, "K": "v"},
                write,
            )
        assert [(p, f) for p, f, _ in writes] == [("/opt/x", ".env.owner"), ("/opt/x", ".env")]
        assert _parse_env(writes[0][2]) == {"DATABASE_URL_OWNER": _OWNER_DSN}
        assert _parse_env(writes[1][2]) == {"DATABASE_URL": _APP_DSN, "K": "v"}
        assert "1 owner key(s) kept in .env.owner" in caplog.text
        # The log line names the count and the file, never a value (deployer-O5).
        assert "ownerpw" not in caplog.text and "apppw" not in caplog.text

        writes.clear()
        caplog.clear()
        _write_env_files("/opt/x", {"K": "v"}, write)
        assert [(p, f) for p, f, _ in writes] == [("/opt/x", ".env")]
        assert "owner key(s) kept" not in caplog.text

    # G4 — no owner key, no owner write, today's ssh call count
    def test_g4_no_owner_key_means_no_owner_write(self):
        with (
            patch("fabrik.drivers.ssh.ssh", side_effect=["absent", ""]) as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps") as mock_write,
        ):
            SSHDeployer().inject_env(self._ctx(), {"K": "v"})
        assert [c.args[1] for c in mock_write.call_args_list] == [".env"]
        assert mock_ssh.call_count == 2

    # G5 — the chmod by name, BEFORE the mv
    @pytest.mark.parametrize("filename", [".env", ".env.owner"])
    def test_g5_env_files_are_chmod_0600_on_the_temp_file_before_the_mv(self, filename):
        from fabrik.orchestrator.deployer_ssh import _write_file_to_vps_path

        cmds: list[str] = []
        with (
            patch("fabrik.drivers.ssh.scp_to_vps"),
            patch("fabrik.drivers.ssh.ssh", side_effect=_fake_remote(cmds)),
        ):
            _write_file_to_vps_path("/opt/x", filename, "K=v\n")
        tmp = _MKTEMP_PATH
        assert cmds == [
            f"sudo chmod 0600 {tmp} && sudo mv {tmp} /opt/x/{filename} "
            f"&& sudo chown root:root /opt/x/{filename}"
        ], cmds

    def test_g5_other_files_keep_todays_command(self):
        from fabrik.orchestrator.deployer_ssh import _write_file_to_vps_path

        cmds: list[str] = []
        with (
            patch("fabrik.drivers.ssh.scp_to_vps"),
            patch("fabrik.drivers.ssh.ssh", side_effect=_fake_remote(cmds)),
        ):
            _write_file_to_vps_path("/opt/x", "compose.yaml", "services: {}\n")
        tmp = _MKTEMP_PATH
        assert cmds == [
            f"sudo mv {tmp} /opt/x/compose.yaml && sudo chown root:root /opt/x/compose.yaml"
        ]

    # G6 — the probe protocol stays fail-closed
    def test_g6_probe_protocol_is_fail_closed(self):
        from fabrik.orchestrator.deployer_ssh import _read_env_file

        assert _read_env_file("/opt/my-app", lambda cmd, timeout=10: "absent\nowner\n") == {}
        with pytest.raises(DeployError, match=r"/opt/my-app/\.env"):
            _read_env_file("/opt/my-app", lambda cmd, timeout=10: "nonsense\n")
        with pytest.raises(DeployError, match=r"/opt/my-app/\.env"):
            _read_env_file("/opt/my-app", lambda cmd, timeout=10: "")
        # Phase A review O3: a second line that is not `owner`, or a third line, is refused — never
        # read as "no owner file" (the real command prints exactly one or two lines).
        for answer in ("present\nnonsense\n", "present\nowner\nextra\n", "present\n\nowner\n"):
            with pytest.raises(DeployError, match="unexpected probe answer"):
                _read_env_file("/opt/my-app", lambda cmd, timeout=10, a=answer: a)

    def test_g6_probe_lines_are_stripped_so_crlf_and_trailing_spaces_still_parse(self):
        """Phase A review O5: a `\\r\\n` or a trailing space on either probe line is whitespace,
        not a different answer."""
        from fabrik.orchestrator.deployer_ssh import _read_env_file

        answers = iter(
            [
                "present \r\nowner \r\n",
                "A=1\n\n__fabrik_env_owner_follows__\nDATABASE_URL_OWNER=o\n",
            ]
        )
        cmds: list[str] = []

        def ssh(cmd, timeout=10):
            cmds.append(cmd)
            return next(answers)

        assert _read_env_file("/opt/my-app", ssh) == {"A": "1", "DATABASE_URL_OWNER": "o"}
        assert cmds[1].endswith("&& cat /opt/my-app/.env.owner'")

    # G7 — every writer goes through the one writer: an existing `.env` carrying the owner key
    # ends up with the key in `.env.owner` (written first) and never in `.env`
    _MERGED = f"A=1\n\n__fabrik_env_owner_follows__\nDATABASE_URL_OWNER={_OWNER_DSN}\n"
    _MERGED_DICT = {"A": "1", "DATABASE_URL_OWNER": _OWNER_DSN}

    @staticmethod
    def _owner_then_env(writes: list[tuple[str, str, str]]) -> None:
        env_writes = [(p, f, c) for p, f, c in writes if f in (".env", ".env.owner")]
        assert [f for _, f, _ in env_writes] == [".env.owner", ".env"], env_writes
        assert _parse_env(env_writes[0][2]) == {"DATABASE_URL_OWNER": _OWNER_DSN}
        assert "DATABASE_URL_OWNER" not in _parse_env(env_writes[1][2])

    def test_g7_persist_git_sha_goes_through_the_split_writer(self):
        from fabrik.orchestrator.deployer_ssh import _persist_git_sha

        answers = ["present\nowner\n", self._MERGED]
        with (
            patch("fabrik.drivers.ssh.ssh", side_effect=answers) as mock_ssh,
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps") as mock_write,
        ):
            _persist_git_sha("my-app", "a" * 40, mock_ssh)
        writes = [c.args for c in mock_write.call_args_list]
        self._owner_then_env(writes)
        assert _parse_env(writes[-1][2]) == {"A": "1", "GIT_SHA": "a" * 40}

    def test_g7_deploy_template_goes_through_the_split_writer(self):
        ctx = _ctx(
            {
                "name": "my-app",
                "source": {"type": "template"},
                "template": "python-api",
                "domain": "my-app.example.com",
            }
        )
        ctx.secrets = {}
        with (
            patch("fabrik.drivers.ssh.ssh", return_value=""),
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps") as mock_write,
            patch.object(SSHDeployer, "_build_env", return_value=dict(self._MERGED_DICT)),
        ):
            SSHDeployer()._deploy_template(ctx, "my-app", None)
        self._owner_then_env([c.args for c in mock_write.call_args_list])

    def test_g32_deploy_template_renders_no_owner_key_into_compose(self):
        """G32 (the Finish review, deployer-O1): the renderer puts every secret into every service's
        `environment:`; an owner key among the secrets (`secrets.from_env`) must never reach
        compose.yaml — it goes to `.env.owner` through the writer. An ordinary secret still renders."""
        ctx = _ctx(
            {
                "name": "my-app",
                "source": {"type": "template"},
                "template": "python-api",
                "domain": "my-app.example.com",
            }
        )
        ctx.secrets = {"DATABASE_URL_OWNER": _OWNER_DSN, "API_TOKEN": "tok-visible"}
        merged = dict(self._MERGED_DICT) | {"API_TOKEN": "tok-visible"}
        with (
            patch("fabrik.drivers.ssh.ssh", return_value=""),
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps") as mock_write,
            patch.object(SSHDeployer, "_build_env", return_value=merged),
        ):
            SSHDeployer()._deploy_template(ctx, "my-app", None)
        by_name = {c.args[1]: c.args[2] for c in mock_write.call_args_list}
        compose = by_name["compose.yaml"]
        assert "DATABASE_URL_OWNER" not in compose and "ownerpw" not in compose, compose
        assert "API_TOKEN=tok-visible" in compose
        assert _parse_env(by_name[".env.owner"]) == {"DATABASE_URL_OWNER": _OWNER_DSN}

    def test_g7_deploy_git_goes_through_the_split_writer(self):
        ctx = _ctx(
            {"name": "my-app", "source": {"type": "git", "repository": "git@github.com:u/r.git"}}
        )
        with (
            patch(
                "fabrik.drivers.ssh.ssh",
                side_effect=["exists", "", "", "a" * 40 + "\n", _VALID_GIT_COMPOSE, "", ""],
            ),
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps") as mock_write,
            patch.object(SSHDeployer, "_build_env", return_value=dict(self._MERGED_DICT)),
        ):
            SSHDeployer()._deploy_git(ctx, "my-app", ctx.spec["source"], None)
        self._owner_then_env([c.args for c in mock_write.call_args_list])

    def test_g7_deploy_docker_goes_through_the_split_writer(self):
        ctx = _ctx(
            {
                "name": "my-app",
                "source": {"type": "docker", "image": "nginx:latest", "image_port": 80},
                "domain": "my-app.example.com",
            }
        )
        with (
            patch("fabrik.drivers.ssh.ssh", return_value=""),
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps") as mock_write,
            patch.object(SSHDeployer, "_build_env", return_value=dict(self._MERGED_DICT)),
        ):
            SSHDeployer()._deploy_docker(ctx, "my-app", ctx.spec["source"], None)
        self._owner_then_env([c.args for c in mock_write.call_args_list])

    def test_g7_deploy_paths_write_a_newline_value_intact(self):
        """Phase A review O2: the deploy paths hand the merged DICT to the writer — a value holding a
        newline survives (the old format→parse round trip turned `a\\nb` into `"a`)."""
        ctx = _ctx(
            {
                "name": "my-app",
                "source": {"type": "docker", "image": "nginx:latest", "image_port": 80},
                "domain": "my-app.example.com",
            }
        )
        with (
            patch("fabrik.drivers.ssh.ssh", return_value=""),
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps") as mock_write,
            patch.object(SSHDeployer, "_build_env", return_value={"K": "a\nb", "Z": "1"}),
        ):
            SSHDeployer()._deploy_docker(ctx, "my-app", ctx.spec["source"], None)
        (env_write,) = [c.args for c in mock_write.call_args_list if c.args[1] == ".env"]
        assert env_write[2] == _format_env({"K": "a\nb", "Z": "1"})

    def test_g7_deploy_local_goes_through_the_split_writer(self):
        ctx = _ctx({"name": "my-app", "source": {"type": "local", "path": "/srv/my-app"}})
        ctx.secrets = {}
        with (
            patch("fabrik.drivers.ssh.ssh", side_effect=["exists", _VALID_LOCAL_COMPOSE, ""]),
            patch("fabrik.orchestrator.deployer_ssh._write_file_to_vps_path") as mock_write,
            patch.object(SSHDeployer, "_build_env", return_value=dict(self._MERGED_DICT)),
        ):
            SSHDeployer()._deploy_local(ctx, "my-app", ctx.spec["source"], None)
        writes = [c.args for c in mock_write.call_args_list]
        assert all(p == "/srv/my-app" for p, _, _ in writes)
        self._owner_then_env(writes)
