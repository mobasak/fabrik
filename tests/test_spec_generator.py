"""Tests for spec_generator.py — spec generation and project context extraction."""

from pathlib import Path

import pytest
import yaml

from fabrik.spec_generator import (
    _TYPE_DEFAULTS,
    SECRET_PATTERNS,
    SPEC_ENABLED_TYPES,
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

    def test_spec_enabled_types_has_nine_entries(self):
        # 9 deployable types: python-api, python-api-gpu, node-api,
        # saas-skeleton, file-api, file-worker, static-site, docusaurus,
        # chrome-extension. The CRX is client-side but its companion FastAPI
        # backend (``server/``) IS a real VPS service; python-api-gpu is
        # python-api + a GPU rental helper (same deploy shape) — see the
        # ``SPEC_ENABLED_TYPES`` docstring.
        # Still excluded: desktop-app, mobile-app (no companion backend),
        # wordpress (scaffolding moved to /opt/wpf).
        assert len(SPEC_ENABLED_TYPES) == 9

    def test_file_worker_in_enabled_types(self):
        assert "file-worker" in SPEC_ENABLED_TYPES

    def test_chrome_extension_in_enabled_types(self):
        """G9: chrome-extension's FastAPI backend is a real VPS service.

        The CRX itself ships via the Chrome Web Store, but the scaffolder
        emits ``server/`` + a canonical ``compose.yaml`` with Traefik
        labels + CORS middleware (B16/B18 fixes). ``fabrik apply`` SHOULD
        deploy that backend by default; pure-client CRX users opt out
        with ``--no-spec``.
        """
        assert "chrome-extension" in SPEC_ENABLED_TYPES

    def test_wordpress_excluded_from_enabled_types(self):
        assert "wordpress" not in SPEC_ENABLED_TYPES

    def test_desktop_mobile_excluded_from_enabled_types(self):
        """B3 regression (narrowed): desktop-app/mobile-app must NOT
        emit a deployable spec.

        Why: the scaffolder does not currently emit a ``compose.yaml``
        for these — they have no companion backend, only an Electron /
        React Native build artifact. Adding them to ``SPEC_ENABLED_TYPES``
        would make ``fabrik apply`` create a phantom Cloudflare DNS
        record + Coolify app pointing at a service that doesn't exist.

        chrome-extension was removed from this assertion in G9 because
        its scaffolder DOES emit a real backend ``compose.yaml``.
        Tracked under Phase C (G11): finish the desktop/mobile backend
        scaffolders so they can be promoted to deployable too.
        """
        for artifact_type in ("desktop-app", "mobile-app"):
            assert artifact_type not in SPEC_ENABLED_TYPES, (
                f"{artifact_type!r} has no companion backend yet "
                f"and must not be in SPEC_ENABLED_TYPES until Phase C"
            )

    def test_secret_patterns_are_uppercase(self):
        for pattern in SECRET_PATTERNS:
            assert pattern == pattern.upper(), f"{pattern!r} is not uppercase"


# ---------------------------------------------------------------------------
# TestNewTypeDefaults
# ---------------------------------------------------------------------------


class TestNewTypeDefaults:
    """Verify _TYPE_DEFAULTS entries for new scaffold types."""

    def test_docusaurus_health_path(self):
        # B45: Docusaurus preset-classic has no auto-generated `/` route, so the
        # health check targets the intro doc instead.
        assert _TYPE_DEFAULTS["docusaurus"]["health_path"] == "/docs/intro"

    def test_chrome_extension_health_path(self):
        """G9: chrome-extension defaults to /health (FastAPI backend convention)."""
        assert _TYPE_DEFAULTS["chrome-extension"]["health_path"] == "/health"

    def test_desktop_mobile_have_no_type_defaults(self):
        """B3 regression (narrowed): desktop-app/mobile-app must not
        appear in ``_TYPE_DEFAULTS`` — the resource/health defaults are
        meaningless for types with no compose.yaml.

        chrome-extension was removed from this assertion in G9 because
        it now deploys its FastAPI backend.
        """
        for artifact_type in ("desktop-app", "mobile-app"):
            assert artifact_type not in _TYPE_DEFAULTS


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

    def test_docusaurus_generates_static_kind(self):
        """B4 regression: top-level ``kind`` is derived from
        ``shape.kind``. Docusaurus is a static site, so both the
        top-level ``kind`` and ``shape.kind`` must be ``static`` —
        pre-fix they disagreed (top=service, shape=static)."""
        spec = generate_spec("my-docs", "docusaurus", "my-docs.vps1.ocoron.com")
        assert spec.kind == Kind.STATIC
        assert spec.shape is not None and spec.shape.kind == "static"

    def test_static_site_generates_static_kind(self):
        """B4 regression for static-site (same rationale as docusaurus)."""
        spec = generate_spec("my-site", "static-site", "my-site.vps1.ocoron.com")
        assert spec.kind == Kind.STATIC
        assert spec.shape is not None and spec.shape.kind == "static"

    def test_docusaurus_health_path_is_docs_intro(self):
        # B45: `/` 404s on a default Docusaurus build — health targets /docs/intro.
        spec = generate_spec("my-docs", "docusaurus", "my-docs.vps1.ocoron.com")
        assert spec.health.path == "/docs/intro"

    def test_artifact_types_raise_value_error(self):
        """B3 regression (narrowed): passing desktop-app or mobile-app
        to generate_spec must raise ``ValueError``, not silently emit
        a phantom spec.

        chrome-extension was removed from this assertion in G9 because
        its FastAPI backend is now deployable. See
        ``test_chrome_extension_emits_valid_spec`` for the positive
        contract.
        """
        for artifact_type in ("desktop-app", "mobile-app"):
            with pytest.raises(ValueError, match="Unsupported project type"):
                generate_spec(
                    f"my-{artifact_type}",
                    artifact_type,
                    f"my-{artifact_type}.vps1.ocoron.com",
                )

    def test_chrome_extension_emits_valid_spec(self):
        """G9: chrome-extension's FastAPI backend produces a valid Spec.

        The CRX itself ships via Chrome Web Store; this spec drives the
        backend. Verifies:
        - top-level kind == SERVICE (mapped from shape.kind=service)
        - shape pulled from templates/chrome-extension/defaults.yaml
        - health.path == /health (FastAPI convention)
        - resources match _TYPE_DEFAULTS
        - source.type detected (git source if .git exists, else template)
        """
        spec = generate_spec(
            "my-ext", "chrome-extension", "my-ext.vps1.ocoron.com"
        )
        assert spec.kind == Kind.SERVICE
        assert spec.shape is not None
        assert spec.shape.kind == "service"
        # is_public defaults to false in chrome-extension/defaults.yaml
        # (Gatus opt-in) — verify the shape is loaded from the template,
        # not synthesized from generic defaults.
        assert spec.shape.is_public is False
        assert spec.health is not None and spec.health.path == "/health"
        assert spec.resources.memory == "256M"
        assert spec.resources.cpu == "0.5"

    def test_use_database_propagates_to_shape(self):
        """B1 regression: ``use_database=True`` must overlay
        ``shape.needs_database = True`` even when the template's
        ``defaults.yaml`` says false.

        Why: ``fabrik scaffold --db`` creates a local PostgreSQL DB but
        pre-fix the flag was silently dropped at spec generation, so
        the postgres registrar would skip on apply — a DB-backed
        project would deploy without a VPS database (silent feature
        breakage).
        """
        spec_off = generate_spec("db-off", "python-api", "db-off.vps1.ocoron.com")
        assert spec_off.shape is not None
        assert spec_off.shape.needs_database is False

        spec_on = generate_spec(
            "db-on",
            "python-api",
            "db-on.vps1.ocoron.com",
            use_database=True,
        )
        assert spec_on.shape is not None
        assert spec_on.shape.needs_database is True
        # Also verify ``depends.postgres`` is wired so the rendered
        # compose / orchestrator dependency graph reflects the DB.
        assert spec_on.depends.postgres == "main"

    def test_emits_canonical_coolify_project(self):
        """B2 regression: emitted specs MUST declare the canonical
        ``coolify.project`` (``fabrik-services``), not the pydantic
        default ``"default"``.

        Why: post the deployer fix from the same session, an unset
        ``COOLIFY_PROJECT_UUID`` env var falls back to
        ``spec.coolify.project`` and would auto-create a useless
        ``default`` project on every fresh-environment deploy.
        """
        spec = generate_spec("my-api", "python-api", "my-api.vps1.ocoron.com")
        assert spec.coolify.project == "fabrik-services"


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


# ---------------------------------------------------------------------------
# B7: git remote detection -> source.type=git
# ---------------------------------------------------------------------------


class TestB7DetectGitSource:
    """`detect_git_source` flips source.type to git when a remote exists.

    Coolify v4 inline-compose has no source for `build:` to consume; spec must
    point at a git repo so Coolify can clone it. See spec_generator.detect_git_source.
    """

    def _make_repo(self, tmp_path: Path, remote: str | None = "https://github.com/x/y.git") -> Path:
        import subprocess
        project = tmp_path / "p"
        project.mkdir()
        subprocess.run(["git", "-C", str(project), "init", "-q", "-b", "main"], check=True)
        # need at least one commit so symbolic-ref works in some git versions
        (project / "README.md").write_text("x")
        subprocess.run(["git", "-C", str(project), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(project), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "i"],
            check=True,
        )
        if remote:
            subprocess.run(["git", "-C", str(project), "remote", "add", "origin", remote], check=True)
        return project

    def test_returns_none_when_no_git(self, tmp_path: Path):
        from fabrik.spec_generator import detect_git_source
        project = tmp_path / "no-git"
        project.mkdir()
        assert detect_git_source(project) is None

    def test_returns_none_when_git_but_no_remote(self, tmp_path: Path):
        from fabrik.spec_generator import detect_git_source
        project = self._make_repo(tmp_path, remote=None)
        assert detect_git_source(project) is None

    def test_returns_source_with_git_type_and_remote_url(self, tmp_path: Path):
        from fabrik.spec_generator import detect_git_source
        from fabrik.spec_loader import SourceType
        project = self._make_repo(tmp_path, remote="https://github.com/mobasak/foo.git")
        src = detect_git_source(project)
        assert src is not None
        assert src.type == SourceType.GIT
        assert src.repository == "https://github.com/mobasak/foo.git"
        assert src.branch == "main"

    def test_generate_spec_emits_git_source_when_project_path_has_remote(self, tmp_path: Path):
        from fabrik.spec_generator import generate_spec
        from fabrik.spec_loader import SourceType
        project = self._make_repo(tmp_path, remote="git@github.com:mobasak/bar.git")
        spec = generate_spec(
            name="bar",
            project_type="python-api",
            domain="bar.vps1.ocoron.com",
            project_path=project,
        )
        assert spec.source.type == SourceType.GIT
        assert spec.source.repository == "git@github.com:mobasak/bar.git"

    def test_generate_spec_falls_back_to_template_without_path(self):
        from fabrik.spec_generator import generate_spec
        from fabrik.spec_loader import SourceType
        spec = generate_spec(
            name="x",
            project_type="python-api",
            domain="x.vps1.ocoron.com",
        )
        assert spec.source.type == SourceType.TEMPLATE

