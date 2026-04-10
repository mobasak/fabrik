"""Tests for deploy_validator.py — deployment readiness checks."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from fabrik.cli import cli
from fabrik.deploy_validator import (
    ValidationResult,
    _check_dockerfile,
    _check_env_example,
    _check_health_endpoint,
    _check_spec_exists,
    _check_template_exists,
    format_warnings,
    validate,
)


# ---------------------------------------------------------------------------
# TestCheckTemplateExists
# ---------------------------------------------------------------------------


class TestCheckTemplateExists:
    """Tests for _check_template_exists."""

    def test_known_type_passes(self):
        result = _check_template_exists("python-api")
        assert result.passed is True
        assert result.check == "deploy_template"
        assert "python-api" in result.message

    def test_unknown_type_fails(self):
        result = _check_template_exists("nonexistent-type")
        assert result.passed is False
        assert result.check == "deploy_template"
        assert "nonexistent-type" in result.message


# ---------------------------------------------------------------------------
# TestCheckEnvExample
# ---------------------------------------------------------------------------


class TestCheckEnvExample:
    """Tests for _check_env_example."""

    def test_present_passes(self, tmp_path: Path):
        (tmp_path / ".env.example").write_text("KEY=value\n")
        result = _check_env_example(tmp_path)
        assert result.passed is True
        assert result.check == "env_example"

    def test_missing_fails(self, tmp_path: Path):
        result = _check_env_example(tmp_path)
        assert result.passed is False
        assert result.check == "env_example"


# ---------------------------------------------------------------------------
# TestCheckDockerfile
# ---------------------------------------------------------------------------


class TestCheckDockerfile:
    """Tests for _check_dockerfile."""

    def test_present_passes(self, tmp_path: Path):
        (tmp_path / "Dockerfile").write_text("FROM python:3.12-slim-bookworm\n")
        result = _check_dockerfile(tmp_path)
        assert result.passed is True
        assert result.check == "dockerfile"

    def test_missing_fails(self, tmp_path: Path):
        result = _check_dockerfile(tmp_path)
        assert result.passed is False
        assert result.check == "dockerfile"


# ---------------------------------------------------------------------------
# TestCheckHealthEndpoint
# ---------------------------------------------------------------------------


class TestCheckHealthEndpoint:
    """Tests for _check_health_endpoint."""

    def test_python_file_with_health_route_passes(self, tmp_path: Path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        main_py = src_dir / "main.py"
        main_py.write_text(
            '@app.get("/health")\nasync def health():\n    return {"status": "ok"}\n'
        )
        result = _check_health_endpoint(tmp_path, "python-api")
        assert result.passed is True
        assert result.check == "health_endpoint"
        assert "detected" in result.message.lower()

    def test_no_src_dir_fails(self, tmp_path: Path):
        result = _check_health_endpoint(tmp_path, "python-api")
        assert result.passed is False
        assert "src/ directory not found" in result.message

    def test_no_health_string_fails(self, tmp_path: Path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("print('hello')\n")
        result = _check_health_endpoint(tmp_path, "python-api")
        assert result.passed is False
        assert result.check == "health_endpoint"

    def test_node_type_checks_js_files(self, tmp_path: Path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "index.js").write_text(
            'app.get("/health", (req, res) => res.json({ok: true}));\n'
        )
        result = _check_health_endpoint(tmp_path, "node-api")
        assert result.passed is True

    def test_node_type_checks_ts_files(self, tmp_path: Path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "index.ts").write_text('router.get("/health", handler);\n')
        result = _check_health_endpoint(tmp_path, "saas-skeleton")
        assert result.passed is True


# ---------------------------------------------------------------------------
# TestCheckSpecExists
# ---------------------------------------------------------------------------


class TestCheckSpecExists:
    """Tests for _check_spec_exists."""

    def test_no_spec_returns_passed_true(self, tmp_path: Path):
        result = _check_spec_exists("my-api", tmp_path)
        assert result.passed is True
        assert "clean state" in result.message

    def test_existing_spec_returns_passed_true_with_overwrite_message(self, tmp_path: Path):
        (tmp_path / "my-api.yaml").write_text("id: my-api\n")
        result = _check_spec_exists("my-api", tmp_path)
        assert result.passed is True
        assert "overwritten" in result.message


# ---------------------------------------------------------------------------
# TestValidate
# ---------------------------------------------------------------------------


class TestValidate:
    """Tests for the aggregate validate() function."""

    def test_returns_5_results(self, tmp_path: Path):
        results = validate(tmp_path, "python-api", specs_dir=tmp_path)
        assert len(results) == 5
        assert all(isinstance(r, ValidationResult) for r in results)

    def test_all_pass_for_complete_project(self, tmp_path: Path):
        # Create all required files for a passing project
        (tmp_path / ".env.example").write_text("KEY=value\n")
        (tmp_path / "Dockerfile").write_text("FROM python:3.12-slim-bookworm\n")
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text('@app.get("/health")\n')
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        results = validate(tmp_path, "python-api", specs_dir=specs_dir)
        assert all(r.passed is True for r in results)

    def test_partial_failures_reported(self, tmp_path: Path):
        # .env.example present, Dockerfile missing
        (tmp_path / ".env.example").write_text("KEY=value\n")
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text('@app.get("/health")\n')

        results = validate(tmp_path, "python-api", specs_dir=tmp_path)
        failed = [r for r in results if not r.passed]
        # Exactly Dockerfile should fail
        assert len(failed) == 1
        assert failed[0].check == "dockerfile"


# ---------------------------------------------------------------------------
# TestFormatWarnings
# ---------------------------------------------------------------------------


class TestFormatWarnings:
    """Tests for format_warnings()."""

    def test_only_failed_results_included(self):
        results = [
            ValidationResult("template", True, "Template found"),
            ValidationResult("dockerfile", False, "Dockerfile missing"),
            ValidationResult("env", False, "env missing"),
        ]
        warnings = format_warnings(results)
        assert len(warnings) == 2

    def test_passed_results_excluded(self):
        results = [
            ValidationResult("template", True, "Template found"),
        ]
        warnings = format_warnings(results)
        assert warnings == []

    def test_warning_format_contains_check_name_and_message(self):
        results = [
            ValidationResult("dockerfile", False, "Dockerfile missing"),
        ]
        warnings = format_warnings(results)
        assert len(warnings) == 1
        assert "dockerfile" in warnings[0]
        assert "Dockerfile missing" in warnings[0]
        assert "\u26a0\ufe0f" in warnings[0]


# ---------------------------------------------------------------------------
# TestValidateDeployCLI
# ---------------------------------------------------------------------------


class TestValidateDeployCLI:
    """Tests for the `fabrik validate-deploy` CLI command."""

    def test_command_exits_0_even_with_failures(self, tmp_path: Path):
        runner = CliRunner()
        result = runner.invoke(cli, ["validate-deploy", str(tmp_path), "--type", "python-api"])
        assert result.exit_code == 0

    def test_output_shows_check_symbols(self, tmp_path: Path):
        # Create partial project so we get a mix of pass/fail
        (tmp_path / ".env.example").write_text("KEY=value\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["validate-deploy", str(tmp_path), "--type", "python-api"])
        assert result.exit_code == 0
        # Should contain at least one pass or warning symbol
        assert "\u2705" in result.output or "\u26a0\ufe0f" in result.output

    def test_command_exits_0_when_validator_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        def _boom(path: Path, project_type: str):
            raise RuntimeError("simulated validator failure")

        monkeypatch.setattr("fabrik.cli.validate_deploy", _boom)
        runner = CliRunner()
        result = runner.invoke(cli, ["validate-deploy", str(tmp_path), "--type", "python-api"])

        assert result.exit_code == 0
        assert "Deployment validator error" in result.output
