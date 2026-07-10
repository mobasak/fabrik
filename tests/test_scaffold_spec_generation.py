"""Tests for scaffold spec auto-generation hook and fabrik new --from-project flag.

Tests verify:
- Spec generated on scaffold success (mock generate_and_save_spec)
- Skipped when generate_spec=False
- Skipped for unsupported type
- Failure in generate_and_save_spec does not break scaffold
- new --from-project populates env/secrets
- new --from-project maps dependency context to depends.postgres/depends.redis
- default output path is specs/services
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from click.testing import CliRunner

from fabrik.cli import cli
from fabrik.spec_loader import Depends, SecretsPolicy

# ---------------------------------------------------------------------------
# TestScaffoldSpecHook — unit tests for create_project spec generation hook
# ---------------------------------------------------------------------------


class TestScaffoldSpecHook:
    """Tests for the generate_spec hook inside create_project()."""

    @patch("fabrik.scaffold.generate_and_save_spec")
    @patch("fabrik.scaffold._post_scaffold_sync")
    @patch("fabrik.scaffold._scaffold_shared")
    def test_spec_generated_on_scaffold_success(
        self, mock_shared: MagicMock, mock_sync: MagicMock, mock_gen: MagicMock, tmp_path: Path
    ) -> None:
        """generate_and_save_spec is called with correct args when generate_spec=True."""
        from fabrik.scaffold import create_project

        # _scaffold_shared creates the project dir; simulate it
        project_dir = tmp_path / "test-api"

        def fake_shared(pd: Path, *_args: object, **_kw: object) -> None:
            pd.mkdir(parents=True, exist_ok=True)

        mock_shared.side_effect = fake_shared

        # Register a fake scaffolder so create_project doesn't fail
        with patch.dict("fabrik.scaffold._TYPE_SCAFFOLDERS", {"python-api": lambda *a, **kw: None}):
            result = create_project(
                "test-api",
                "A test API",
                base=tmp_path,
                project_type="python-api",
                generate_spec=True,
            )

        assert result == project_dir
        mock_gen.assert_called_once()
        call_args = mock_gen.call_args
        assert call_args[1].get("name", call_args[0][0]) == "test-api"
        assert call_args[1].get("project_type", call_args[0][1]) == "python-api"

    @patch("fabrik.scaffold.generate_and_save_spec")
    @patch("fabrik.scaffold._post_scaffold_sync")
    @patch("fabrik.scaffold._scaffold_shared")
    def test_spec_skipped_when_generate_spec_false(
        self, mock_shared: MagicMock, mock_sync: MagicMock, mock_gen: MagicMock, tmp_path: Path
    ) -> None:
        """generate_and_save_spec is NOT called when generate_spec=False."""
        from fabrik.scaffold import create_project

        def fake_shared(pd: Path, *_args: object, **_kw: object) -> None:
            pd.mkdir(parents=True, exist_ok=True)

        mock_shared.side_effect = fake_shared

        with patch.dict("fabrik.scaffold._TYPE_SCAFFOLDERS", {"python-api": lambda *a, **kw: None}):
            create_project(
                "test-api2",
                "A test",
                base=tmp_path,
                project_type="python-api",
                generate_spec=False,
            )

        mock_gen.assert_not_called()

    @patch("fabrik.scaffold.generate_and_save_spec")
    @patch("fabrik.scaffold._post_scaffold_sync")
    @patch("fabrik.scaffold._scaffold_shared")
    def test_spec_skipped_for_unsupported_type(
        self, mock_shared: MagicMock, mock_sync: MagicMock, mock_gen: MagicMock, tmp_path: Path
    ) -> None:
        """generate_and_save_spec is NOT called for wordpress (unsupported type)."""
        from fabrik.scaffold import create_project

        def fake_shared(pd: Path, *_args: object, **_kw: object) -> None:
            pd.mkdir(parents=True, exist_ok=True)

        mock_shared.side_effect = fake_shared

        with patch.dict("fabrik.scaffold._TYPE_SCAFFOLDERS", {"wordpress": lambda *a, **kw: None}):
            create_project(
                "test-wp",
                "A WP site",
                base=tmp_path,
                project_type="wordpress",
                generate_spec=True,
            )

        mock_gen.assert_not_called()

    @patch("fabrik.scaffold.generate_and_save_spec", side_effect=RuntimeError("disk full"))
    @patch("fabrik.scaffold._post_scaffold_sync")
    @patch("fabrik.scaffold._scaffold_shared")
    def test_spec_generation_failure_does_not_raise(
        self, mock_shared: MagicMock, mock_sync: MagicMock, mock_gen: MagicMock, tmp_path: Path
    ) -> None:
        """create_project still returns a path when generate_and_save_spec raises."""
        from fabrik.scaffold import create_project

        def fake_shared(pd: Path, *_args: object, **_kw: object) -> None:
            pd.mkdir(parents=True, exist_ok=True)

        mock_shared.side_effect = fake_shared

        with patch.dict("fabrik.scaffold._TYPE_SCAFFOLDERS", {"python-api": lambda *a, **kw: None}):
            result = create_project(
                "test-api3",
                "A test",
                base=tmp_path,
                project_type="python-api",
                generate_spec=True,
            )

        # Scaffold completes despite spec failure
        assert result == tmp_path / "test-api3"
        mock_gen.assert_called_once()


# ---------------------------------------------------------------------------
# TestScaffoldSpecHookNewTypes — new scaffold types generate specs
# ---------------------------------------------------------------------------


class TestScaffoldSpecHookNewTypes:
    """Tests for spec generation across project-type categories.

    Three contracts are pinned here:

    * **Deployable types** (docusaurus, chrome-extension, plus the rest
      in ``SPEC_ENABLED_TYPES``) trigger ``generate_and_save_spec`` so
      the project is ready for ``fabrik apply``.
    * **chrome-extension is special**: the CRX itself ships via the
      Chrome Web Store, but the scaffolder also emits a real FastAPI
      backend (``server/``) with ``compose.yaml`` + Traefik labels.
      The spec drives the **backend**, not the CRX.
    * **Artifact-only ``desktop-app``** MUST NOT trigger spec generation —
      its scaffolder emits no ``compose.yaml`` (no companion backend).
      ``mobile-app`` was promoted in plan-1 Phase C (it now ships a real
      FastAPI backend). Pre-fix (B3) the scaffolder
      emitted ``specs/services/<name>.yaml`` for them with public
      domains — ``fabrik apply`` would have created phantom Cloudflare
      DNS + Coolify resources for non-existent services.
    """

    @patch("fabrik.scaffold.generate_and_save_spec")
    @patch("fabrik.scaffold._post_scaffold_sync")
    @patch("fabrik.scaffold._scaffold_shared")
    def test_spec_generated_for_docusaurus(
        self, mock_shared: MagicMock, mock_sync: MagicMock, mock_gen: MagicMock, tmp_path: Path
    ) -> None:
        """generate_and_save_spec is called for docusaurus when generate_spec=True."""
        from fabrik.scaffold import create_project

        def fake_shared(pd: Path, *_args: object, **_kw: object) -> None:
            pd.mkdir(parents=True, exist_ok=True)

        mock_shared.side_effect = fake_shared

        with patch.dict("fabrik.scaffold._TYPE_SCAFFOLDERS", {"docusaurus": lambda *a, **kw: None}):
            result = create_project(
                "test-docs",
                "A docs site",
                base=tmp_path,
                project_type="docusaurus",
                generate_spec=True,
            )

        assert result == tmp_path / "test-docs"
        mock_gen.assert_called_once()

    @patch("fabrik.scaffold.generate_and_save_spec")
    @patch("fabrik.scaffold._post_scaffold_sync")
    @patch("fabrik.scaffold._scaffold_shared")
    def test_spec_generated_for_mobile_app(
        self, mock_shared: MagicMock, mock_sync: MagicMock, mock_gen: MagicMock, tmp_path: Path
    ) -> None:
        """plan-1 Phase C: mobile-app now emits a deployment spec (bundled FastAPI backend)."""
        from fabrik.scaffold import create_project

        def fake_shared(pd: Path, *_args: object, **_kw: object) -> None:
            pd.mkdir(parents=True, exist_ok=True)

        mock_shared.side_effect = fake_shared

        with patch.dict("fabrik.scaffold._TYPE_SCAFFOLDERS", {"mobile-app": lambda *a, **kw: None}):
            result = create_project(
                "test-mobile",
                "A mobile app",
                base=tmp_path,
                project_type="mobile-app",
                generate_spec=True,
            )

        assert result == tmp_path / "test-mobile"
        mock_gen.assert_called_once()

    @patch("fabrik.scaffold.generate_and_save_spec")
    @patch("fabrik.scaffold._post_scaffold_sync")
    @patch("fabrik.scaffold._scaffold_shared")
    def test_spec_not_generated_for_desktop_app(
        self, mock_shared: MagicMock, mock_sync: MagicMock, mock_gen: MagicMock, tmp_path: Path
    ) -> None:
        """B3 regression: desktop-app must NOT emit a deployment spec."""
        from fabrik.scaffold import create_project

        def fake_shared(pd: Path, *_args: object, **_kw: object) -> None:
            pd.mkdir(parents=True, exist_ok=True)

        mock_shared.side_effect = fake_shared

        with patch.dict(
            "fabrik.scaffold._TYPE_SCAFFOLDERS", {"desktop-app": lambda *a, **kw: None}
        ):
            result = create_project(
                "test-desktop",
                "A desktop app",
                base=tmp_path,
                project_type="desktop-app",
                generate_spec=True,
            )

        assert result == tmp_path / "test-desktop"
        mock_gen.assert_not_called()

    @patch("fabrik.scaffold.generate_and_save_spec")
    @patch("fabrik.scaffold._post_scaffold_sync")
    @patch("fabrik.scaffold._scaffold_shared")
    def test_spec_generated_for_chrome_extension(
        self, mock_shared: MagicMock, mock_sync: MagicMock, mock_gen: MagicMock, tmp_path: Path
    ) -> None:
        """G9: chrome-extension MUST emit a deployment spec for its backend.

        The CRX itself ships via the Chrome Web Store, but the scaffolder
        also emits a real FastAPI backend at ``server/`` plus a canonical
        ``compose.yaml`` with Traefik labels + CORS middleware (B16/B18
        fixes). ``generate_and_save_spec`` MUST run on scaffold so the
        backend is ready for ``fabrik apply`` — same contract as every
        other VPS-deployable type.

        Users who scaffold a pure-client CRX (no backend wanted) opt out
        with ``--no-spec``; they then delete ``server/`` + ``compose.yaml``
        manually.
        """
        from fabrik.scaffold import create_project

        def fake_shared(pd: Path, *_args: object, **_kw: object) -> None:
            pd.mkdir(parents=True, exist_ok=True)

        mock_shared.side_effect = fake_shared

        with patch.dict(
            "fabrik.scaffold._TYPE_SCAFFOLDERS", {"chrome-extension": lambda *a, **kw: None}
        ):
            result = create_project(
                "test-ext",
                "A chrome extension",
                base=tmp_path,
                project_type="chrome-extension",
                generate_spec=True,
            )

        assert result == tmp_path / "test-ext"
        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args
        # Verify the spec is emitted with the chrome-extension type so
        # _build_shape_for_type pulls in the canonical shape from
        # templates/chrome-extension/defaults.yaml (kind=service,
        # is_public=false, etc.). spec_generator.py raises ValueError
        # if the type is not in SPEC_ENABLED_TYPES, so this also
        # implicitly verifies the wiring there.
        assert (
            call_kwargs[1].get("project_type", call_kwargs[0][1] if len(call_kwargs[0]) > 1 else None)
            == "chrome-extension"
        )

    @patch("fabrik.scaffold.generate_and_save_spec")
    @patch("fabrik.scaffold._post_scaffold_sync")
    @patch("fabrik.scaffold._scaffold_shared")
    def test_db_flag_propagates_to_generate_and_save_spec(
        self,
        mock_shared: MagicMock,
        mock_sync: MagicMock,
        mock_gen: MagicMock,
        tmp_path: Path,
    ) -> None:
        """B1 regression: ``--db`` must flow through to ``generate_and_save_spec``.

        When the scaffolder is invoked with ``use_database=True``, the
        kwarg must reach ``generate_and_save_spec`` so the emitted spec
        carries ``shape.needs_database: true``. Pre-fix the kwarg was
        silently dropped at the spec hook.
        """
        from fabrik.scaffold import create_project

        def fake_shared(pd: Path, *_args: object, **_kw: object) -> None:
            pd.mkdir(parents=True, exist_ok=True)

        mock_shared.side_effect = fake_shared

        with patch.dict("fabrik.scaffold._TYPE_SCAFFOLDERS", {"python-api": lambda *a, **kw: None}):
            create_project(
                "test-db-prop",
                "A DB-backed API",
                base=tmp_path,
                project_type="python-api",
                generate_spec=True,
                use_database=True,
            )

        mock_gen.assert_called_once()
        kwargs = mock_gen.call_args.kwargs
        assert kwargs.get("use_database") is True, (
            f"--db must propagate; got use_database={kwargs.get('use_database')!r}"
        )


# ---------------------------------------------------------------------------
# TestNewCommandFromProject — CLI tests for `fabrik new --from-project`
# ---------------------------------------------------------------------------


class TestNewCommandFromProject:
    """Tests for the --from-project flag and --output default on `fabrik new`."""

    def _make_project(
        self, tmp_path: Path, include_postgres: bool = True, include_redis: bool = False
    ) -> Path:
        """Create a fake scaffolded project with compose.yaml and .env.example."""
        project_dir = tmp_path / "existing-project"
        project_dir.mkdir()

        compose_env = {
            "PORT": "8000",
            "LOG_LEVEL": "info",
            "DATABASE_PASSWORD": "secret123",
        }
        if include_postgres:
            compose_env["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/db"
        if include_redis:
            compose_env["REDIS_URL"] = "redis://localhost:6379/0"

        compose = {"services": {"app": {"environment": compose_env}}}
        (project_dir / "compose.yaml").write_text(yaml.dump(compose))

        env_example = (
            "# Config\n"
            "PORT=8000\n"
            "LOG_LEVEL=info\n"
            "DATABASE_URL=postgresql://user:pass@localhost:5432/db\n"
            "DATABASE_PASSWORD=\n"
            "API_SECRET_KEY=\n"
        )
        (project_dir / ".env.example").write_text(env_example)

        return project_dir

    @patch("fabrik.cli.list_templates", return_value=["python-api", "node-api"])
    @patch("fabrik.cli.save_spec")
    @patch("fabrik.cli.create_spec")
    def test_from_project_flag_populates_env(
        self,
        mock_create: MagicMock,
        mock_save: MagicMock,
        mock_templates: MagicMock,
        tmp_path: Path,
    ) -> None:
        """--from-project extracts env vars and passes them to create_spec."""
        project_dir = self._make_project(tmp_path)
        mock_create.return_value = MagicMock()

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "new",
                "my-api",
                "--template",
                "python-api",
                "--domain",
                "api.vps1.ocoron.com",
                "--from-project",
                str(project_dir),
                "--output",
                str(tmp_path / "specs" / "services"),
            ],
        )

        assert result.exit_code == 0, result.output
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        # Non-secret env vars should be present
        assert "PORT" in call_kwargs["env"]
        assert "LOG_LEVEL" in call_kwargs["env"]
        # Secret vars should NOT be in env (they go to secrets)
        assert "DATABASE_PASSWORD" not in call_kwargs["env"]

    @patch("fabrik.cli.list_templates", return_value=["python-api", "node-api"])
    @patch("fabrik.cli.save_spec")
    @patch("fabrik.cli.create_spec")
    def test_from_project_flag_populates_secrets(
        self,
        mock_create: MagicMock,
        mock_save: MagicMock,
        mock_templates: MagicMock,
        tmp_path: Path,
    ) -> None:
        """--from-project extracts secrets and passes SecretsPolicy to create_spec."""
        project_dir = self._make_project(tmp_path)
        mock_create.return_value = MagicMock()

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "new",
                "my-api",
                "--template",
                "python-api",
                "--domain",
                "api.vps1.ocoron.com",
                "--from-project",
                str(project_dir),
                "--output",
                str(tmp_path / "specs" / "services"),
            ],
        )

        assert result.exit_code == 0, result.output
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        secrets_policy = call_kwargs["secrets"]
        assert isinstance(secrets_policy, SecretsPolicy)
        assert "DATABASE_PASSWORD" in secrets_policy.required
        assert "API_SECRET_KEY" in secrets_policy.required

    @patch("fabrik.cli.list_templates", return_value=["python-api"])
    @patch("fabrik.cli.save_spec")
    @patch("fabrik.cli.create_spec")
    def test_output_default_is_specs_services(
        self,
        mock_create: MagicMock,
        mock_save: MagicMock,
        mock_templates: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Default --output is specs/services (not specs)."""
        mock_create.return_value = MagicMock()

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "new",
                "my-api",
                "--template",
                "python-api",
                "--domain",
                "api.vps1.ocoron.com",
            ],
        )

        assert result.exit_code == 0, result.output
        mock_save.assert_called_once()
        # The spec_file path should use specs/services as parent
        saved_path = mock_save.call_args[0][1]
        assert Path(saved_path).parent == Path("specs/services")

    @patch("fabrik.cli.list_templates", return_value=["python-api", "node-api"])
    @patch("fabrik.cli.save_spec")
    @patch("fabrik.cli.create_spec")
    def test_from_project_maps_depends_when_detected(
        self,
        mock_create: MagicMock,
        mock_save: MagicMock,
        mock_templates: MagicMock,
        tmp_path: Path,
    ) -> None:
        """--from-project maps postgres/redis detection to Depends(postgres='main', redis='main')."""
        project_dir = self._make_project(tmp_path, include_postgres=True, include_redis=True)
        mock_create.return_value = MagicMock()

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "new",
                "my-api",
                "--template",
                "python-api",
                "--domain",
                "api.vps1.ocoron.com",
                "--from-project",
                str(project_dir),
                "--output",
                str(tmp_path / "specs" / "services"),
            ],
        )

        assert result.exit_code == 0, result.output
        mock_create.assert_called_once()
        depends = mock_create.call_args[1]["depends"]
        assert isinstance(depends, Depends)
        assert depends.postgres == "main"
        assert depends.redis == "main"

    @patch("fabrik.cli.list_templates", return_value=["python-api", "node-api"])
    @patch("fabrik.cli.save_spec")
    @patch("fabrik.cli.create_spec")
    def test_from_project_maps_depends_to_none_when_not_detected(
        self,
        mock_create: MagicMock,
        mock_save: MagicMock,
        mock_templates: MagicMock,
        tmp_path: Path,
    ) -> None:
        """--from-project maps missing postgres/redis context to Depends(postgres=None, redis=None)."""
        project_dir = self._make_project(tmp_path, include_postgres=False, include_redis=False)
        mock_create.return_value = MagicMock()

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "new",
                "my-api",
                "--template",
                "python-api",
                "--domain",
                "api.vps1.ocoron.com",
                "--from-project",
                str(project_dir),
                "--output",
                str(tmp_path / "specs" / "services"),
            ],
        )

        assert result.exit_code == 0, result.output
        mock_create.assert_called_once()
        depends = mock_create.call_args[1]["depends"]
        assert isinstance(depends, Depends)
        assert depends.postgres is None
        assert depends.redis is None
