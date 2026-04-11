"""Tests for spec_generator.py — spec generation and project context extraction."""

from pathlib import Path

import pytest
import yaml

from fabrik.spec_generator import (
    SPEC_ENABLED_TYPES,
    SECRET_PATTERNS,
    _TYPE_DEFAULTS,
    _is_secret,
    _parse_compose_env,
    _parse_env_example,
    extract_project_context,
    generate_and_save_spec,
    generate_spec,
)
from fabrik.spec_loader import Kind, load_spec


# ---------------------------------------------------------------------------
# TestConstants
# ---------------------------------------------------------------------------


class TestConstants:
    """Verify module-level constants are correctly defined."""

    def test_spec_enabled_types_has_10_entries(self):
        assert len(SPEC_ENABLED_TYPES) == 10

    def test_file_worker_in_enabled_types(self):
        assert "file-worker" in SPEC_ENABLED_TYPES

    def test_wordpress_excluded_from_enabled_types(self):
        assert "wordpress" not in SPEC_ENABLED_TYPES

    def test_secret_patterns_are_uppercase(self):
        for pattern in SECRET_PATTERNS:
            assert pattern == pattern.upper(), f"{pattern!r} is not uppercase"


# ---------------------------------------------------------------------------
# TestNewTypeDefaults
# ---------------------------------------------------------------------------


class TestNewTypeDefaults:
    """Verify _TYPE_DEFAULTS entries for new scaffold types."""

    def test_docusaurus_health_path(self):
        assert _TYPE_DEFAULTS["docusaurus"]["health_path"] == "/"

    def test_mobile_app_health_path(self):
        assert _TYPE_DEFAULTS["mobile-app"]["health_path"] == "/health"

    def test_desktop_app_health_path(self):
        assert _TYPE_DEFAULTS["desktop-app"]["health_path"] == "/health"


# ---------------------------------------------------------------------------
# TestIsSecret
# ---------------------------------------------------------------------------


class TestIsSecret:
    """Verify _is_secret() pattern matching."""

    def test_password_key_is_secret(self):
        assert _is_secret("DB_PASSWORD") is True

    def test_api_key_is_secret(self):
        assert _is_secret("API_KEY") is True

    def test_token_is_secret(self):
        assert _is_secret("AUTH_TOKEN") is True

    def test_log_level_is_not_secret(self):
        assert _is_secret("LOG_LEVEL") is False

    def test_debug_is_not_secret(self):
        assert _is_secret("DEBUG") is False

    def test_case_insensitive_match(self):
        assert _is_secret("db_password") is True
        assert _is_secret("Db_Password") is True


# ---------------------------------------------------------------------------
# TestParseComposeEnv
# ---------------------------------------------------------------------------


class TestParseComposeEnv:
    """Verify _parse_compose_env() handles various compose.yaml formats."""

    def test_dict_format_env_vars(self, tmp_path: Path):
        compose = tmp_path / "compose.yaml"
        compose.write_text(
            yaml.dump(
                {
                    "services": {
                        "app": {
                            "image": "python:3.12",
                            "environment": {
                                "DATABASE_URL": "postgres://localhost/db",
                                "LOG_LEVEL": "info",
                            },
                        }
                    }
                }
            )
        )
        result = _parse_compose_env(compose)
        assert result == {"DATABASE_URL": "postgres://localhost/db", "LOG_LEVEL": "info"}

    def test_list_format_env_vars(self, tmp_path: Path):
        compose = tmp_path / "compose.yaml"
        compose.write_text(
            yaml.dump(
                {
                    "services": {
                        "app": {
                            "image": "python:3.12",
                            "environment": [
                                "DATABASE_URL=postgres://localhost/db",
                                "LOG_LEVEL=info",
                            ],
                        }
                    }
                }
            )
        )
        result = _parse_compose_env(compose)
        assert result == {"DATABASE_URL": "postgres://localhost/db", "LOG_LEVEL": "info"}

    def test_missing_file_returns_empty_dict(self, tmp_path: Path):
        result = _parse_compose_env(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_malformed_yaml_returns_empty_dict(self, tmp_path: Path):
        compose = tmp_path / "compose.yaml"
        compose.write_text(":::\ninvalid: [yaml: {{{")
        result = _parse_compose_env(compose)
        assert result == {}

    def test_none_yaml_returns_empty_dict(self, tmp_path: Path):
        compose = tmp_path / "compose.yaml"
        compose.write_text("")  # yaml.safe_load returns None
        result = _parse_compose_env(compose)
        assert result == {}


# ---------------------------------------------------------------------------
# TestParseEnvExample
# ---------------------------------------------------------------------------


class TestParseEnvExample:
    """Verify _parse_env_example() extraction logic."""

    def test_extracts_secret_keys_only(self, tmp_path: Path):
        env_file = tmp_path / ".env.example"
        env_file.write_text("DB_PASSWORD=\nLOG_LEVEL=info\nAPI_KEY=\nDEBUG=false\nSECRET_KEY=\n")
        result = _parse_env_example(env_file)
        assert "DB_PASSWORD" in result
        assert "API_KEY" in result
        assert "SECRET_KEY" in result
        assert "LOG_LEVEL" not in result
        assert "DEBUG" not in result

    def test_skips_comment_lines(self, tmp_path: Path):
        env_file = tmp_path / ".env.example"
        env_file.write_text("# This is a comment\nDB_PASSWORD=\n# Another comment\n")
        result = _parse_env_example(env_file)
        assert result == ["DB_PASSWORD"]

    def test_skips_blank_lines(self, tmp_path: Path):
        env_file = tmp_path / ".env.example"
        env_file.write_text("\n\nDB_PASSWORD=\n\n\nAPI_KEY=abc\n\n")
        result = _parse_env_example(env_file)
        assert "DB_PASSWORD" in result
        assert "API_KEY" in result

    def test_missing_file_returns_empty_list(self, tmp_path: Path):
        result = _parse_env_example(tmp_path / ".env.example")
        assert result == []

    def test_non_secret_keys_not_returned(self, tmp_path: Path):
        env_file = tmp_path / ".env.example"
        env_file.write_text("LOG_LEVEL=info\nDEBUG=false\nPORT=8000\nHOST=0.0.0.0\n")
        result = _parse_env_example(env_file)
        assert result == []

    def test_ignores_malformed_lines_without_equals(self, tmp_path: Path):
        env_file = tmp_path / ".env.example"
        env_file.write_text(
            "DB_PASSWORD\nAPI_KEY=\nexport SECRET_KEY\nSECRET_TOKEN=abc\njust some text\n"
        )
        result = _parse_env_example(env_file)
        assert result == ["API_KEY", "SECRET_TOKEN"]


# ---------------------------------------------------------------------------
# TestExtractProjectContext
# ---------------------------------------------------------------------------


class TestExtractProjectContext:
    """Verify extract_project_context() assembles env/secrets/depends correctly."""

    def test_detects_postgres_from_database_url(self, tmp_path: Path):
        compose = tmp_path / "compose.yaml"
        compose.write_text(
            yaml.dump(
                {
                    "services": {
                        "app": {
                            "environment": {
                                "DATABASE_URL": "postgres://user:pass@db:5432/mydb",
                            }
                        }
                    }
                }
            )
        )
        ctx = extract_project_context(tmp_path)
        assert ctx["depends_postgres"] is True

    def test_detects_redis_from_redis_url(self, tmp_path: Path):
        compose = tmp_path / "compose.yaml"
        compose.write_text(
            yaml.dump(
                {
                    "services": {
                        "app": {
                            "environment": {
                                "REDIS_URL": "redis://cache:6379",
                            }
                        }
                    }
                }
            )
        )
        ctx = extract_project_context(tmp_path)
        assert ctx["depends_redis"] is True

    def test_no_dependencies_when_absent(self, tmp_path: Path):
        compose = tmp_path / "compose.yaml"
        compose.write_text(
            yaml.dump(
                {
                    "services": {
                        "app": {
                            "environment": {
                                "LOG_LEVEL": "info",
                            }
                        }
                    }
                }
            )
        )
        ctx = extract_project_context(tmp_path)
        assert ctx["depends_postgres"] is False
        assert ctx["depends_redis"] is False

    def test_secrets_separated_from_env(self, tmp_path: Path):
        compose = tmp_path / "compose.yaml"
        compose.write_text(
            yaml.dump(
                {
                    "services": {
                        "app": {
                            "environment": {
                                "LOG_LEVEL": "info",
                                "DB_PASSWORD": "secret123",
                            }
                        }
                    }
                }
            )
        )
        env_example = tmp_path / ".env.example"
        env_example.write_text("DB_PASSWORD=\nAPI_KEY=\n")

        ctx = extract_project_context(tmp_path)
        assert "LOG_LEVEL" in ctx["env"]
        assert "DB_PASSWORD" not in ctx["env"]
        assert "DB_PASSWORD" in ctx["secrets"]
        assert "API_KEY" in ctx["secrets"]

    def test_missing_compose_returns_empty_env(self, tmp_path: Path):
        ctx = extract_project_context(tmp_path)
        assert ctx["env"] == {}
        assert ctx["depends_postgres"] is False
        assert ctx["depends_redis"] is False

    def test_missing_env_example_returns_empty_secrets(self, tmp_path: Path):
        compose = tmp_path / "compose.yaml"
        compose.write_text(
            yaml.dump(
                {
                    "services": {
                        "app": {
                            "environment": {
                                "LOG_LEVEL": "info",
                            }
                        }
                    }
                }
            )
        )
        ctx = extract_project_context(tmp_path)
        assert ctx["secrets"] == []


# ---------------------------------------------------------------------------
# TestGenerateSpec
# ---------------------------------------------------------------------------


class TestGenerateSpec:
    """Verify generate_spec() produces correct Spec objects."""

    def test_python_api_generates_service_kind(self):
        spec = generate_spec("my-api", "python-api", "my-api.vps1.ocoron.com")
        assert spec.kind == Kind.SERVICE

    def test_file_worker_generates_worker_kind(self):
        spec = generate_spec("my-worker", "file-worker", "any.domain.com")
        assert spec.kind == Kind.WORKER

    def test_file_worker_has_no_domain(self):
        spec = generate_spec("my-worker", "file-worker", "any.domain.com")
        assert spec.domain is None

    def test_file_worker_expose_http_false(self):
        spec = generate_spec("my-worker", "file-worker", "any.domain.com")
        assert spec.expose.http is False

    def test_invalid_type_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported project type"):
            generate_spec("test", "wordpress", None)

    def test_postgres_dependency_set_when_detected(self):
        ctx = {"depends_postgres": True, "depends_redis": False}
        spec = generate_spec("my-api", "python-api", "my-api.vps1.ocoron.com", context=ctx)
        assert spec.depends.postgres == "main"
        assert spec.depends.redis is None

    def test_redis_dependency_set_when_detected(self):
        ctx = {"depends_postgres": False, "depends_redis": True}
        spec = generate_spec("my-api", "python-api", "my-api.vps1.ocoron.com", context=ctx)
        assert spec.depends.redis == "main"
        assert spec.depends.postgres is None

    def test_domain_defaults_applied(self):
        spec = generate_spec("my-api", "python-api", "my-api.vps1.ocoron.com")
        assert spec.domain == "my-api.vps1.ocoron.com"

    def test_resources_match_type_defaults_python_api(self):
        spec = generate_spec("my-api", "python-api", "my-api.vps1.ocoron.com")
        assert spec.resources.memory == "512M"
        assert spec.resources.cpu == "0.5"

    def test_resources_match_type_defaults_node_api(self):
        spec = generate_spec("my-api", "node-api", "my-api.vps1.ocoron.com")
        assert spec.resources.memory == "256M"
        assert spec.resources.cpu == "0.5"

    def test_docusaurus_generates_service_kind(self):
        spec = generate_spec("my-docs", "docusaurus", "my-docs.vps1.ocoron.com")
        assert spec.kind == Kind.SERVICE

    def test_mobile_app_generates_service_kind(self):
        spec = generate_spec("my-mobile", "mobile-app", "my-mobile.vps1.ocoron.com")
        assert spec.kind == Kind.SERVICE

    def test_desktop_app_generates_service_kind(self):
        spec = generate_spec("my-desktop", "desktop-app", "my-desktop.vps1.ocoron.com")
        assert spec.kind == Kind.SERVICE

    def test_docusaurus_health_path_is_root(self):
        spec = generate_spec("my-docs", "docusaurus", "my-docs.vps1.ocoron.com")
        assert spec.health.path == "/"

    def test_mobile_app_health_path(self):
        spec = generate_spec("my-mobile", "mobile-app", "my-mobile.vps1.ocoron.com")
        assert spec.health.path == "/health"

    def test_desktop_app_health_path(self):
        spec = generate_spec("my-desktop", "desktop-app", "my-desktop.vps1.ocoron.com")
        assert spec.health.path == "/health"


# ---------------------------------------------------------------------------
# TestGenerateAndSaveSpec
# ---------------------------------------------------------------------------


class TestGenerateAndSaveSpec:
    """Verify generate_and_save_spec() end-to-end flow."""

    def _make_project(self, tmp_path: Path) -> Path:
        """Create a minimal scaffolded project directory."""
        project = tmp_path / "my-api"
        project.mkdir()
        compose = project / "compose.yaml"
        compose.write_text(
            yaml.dump(
                {
                    "services": {
                        "app": {
                            "environment": {
                                "DATABASE_URL": "postgres://localhost/db",
                                "LOG_LEVEL": "info",
                            }
                        }
                    }
                }
            )
        )
        env_example = project / ".env.example"
        env_example.write_text("DB_PASSWORD=\n")
        return project

    def test_creates_yaml_file_at_correct_path(self, tmp_path: Path):
        project = self._make_project(tmp_path)
        specs_dir = tmp_path / "specs" / "services"
        result = generate_and_save_spec("my-api", "python-api", project, specs_dir)
        assert result == specs_dir / "my-api.yaml"
        assert result.exists()

    def test_saved_spec_is_valid_yaml(self, tmp_path: Path):
        project = self._make_project(tmp_path)
        specs_dir = tmp_path / "specs" / "services"
        result = generate_and_save_spec("my-api", "python-api", project, specs_dir)
        with open(result, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        assert isinstance(data, dict)
        assert data["id"] == "my-api"
        assert data["template"] == "python-api"

    def test_saved_spec_health_path_not_stripped_for_python_api(self, tmp_path: Path):
        """health.path must be written even when it equals the Health model default (/health)."""
        project = self._make_project(tmp_path)
        specs_dir = tmp_path / "specs" / "services"
        result = generate_and_save_spec("my-api", "python-api", project, specs_dir)
        with open(result, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        assert "health" in data
        assert isinstance(data["health"], dict)
        assert data["health"].get("path") == "/health"

    def test_saved_spec_passes_load_spec_validation(self, tmp_path: Path):
        project = self._make_project(tmp_path)
        specs_dir = tmp_path / "specs" / "services"
        result = generate_and_save_spec("my-api", "python-api", project, specs_dir)
        loaded = load_spec(result)
        assert loaded.id == "my-api"
        assert loaded.kind == Kind.SERVICE

    def test_returns_path_to_saved_file(self, tmp_path: Path):
        project = self._make_project(tmp_path)
        specs_dir = tmp_path / "specs" / "services"
        result = generate_and_save_spec("my-api", "python-api", project, specs_dir)
        assert isinstance(result, Path)
        assert result.name == "my-api.yaml"
