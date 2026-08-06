"""Tests for python-api, chrome-extension, and file-worker scaffold logging modules.

Verifies that scaffolded projects contain:
- logger.py with structlog configuration and get_logger
- middleware.py with CorrelationMiddleware and ContextVar
- main.py importing logger and middleware
- requirements.txt with structlog>=24.0.0
- .env.example with SERVICE_NAME
- test_health.py with correlation ID tests (python-api only)
- file-worker logger.py with correct structlog config (PrintLoggerFactory, context_class=dict)
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture()
def temp_dir():
    """Create and clean up a temporary directory for scaffold output."""
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture()
def mock_fabrik_root(temp_dir: Path) -> Path:
    """Create minimal fabrik root structure for scaffold to work."""
    fabrik_root = temp_dir / "fabrik-root"
    fabrik_root.mkdir()

    # Create minimal template structure
    scaffold_tpl = fabrik_root / "templates" / "scaffold"
    scaffold_tpl.mkdir(parents=True)

    # Create required docs templates (SHARED_TEMPLATE_MAP entries)
    docs_dir = scaffold_tpl / "docs"
    docs_dir.mkdir()
    for tpl_name in [
        "PROJECT_INDEX_TEMPLATE.md",
        "PROJECT_README_TEMPLATE.md",
        "CHANGELOG_TEMPLATE.md",
        "DOCS_INDEX_TEMPLATE.md",
        "QUICKSTART_TEMPLATE.md",
        "CONFIGURATION_TEMPLATE.md",
        "TROUBLESHOOTING_TEMPLATE.md",
        "BUSINESS_MODEL_TEMPLATE.md",
        "FEATURES_TEMPLATE.md",
        "data-contract-template.md",
    ]:
        (docs_dir / tpl_name).write_text("# [Project Name]\n\nYYYY-MM-DD\n[Brief description]\n")

    # Create docker templates
    docker_dir = scaffold_tpl / "docker"
    docker_dir.mkdir()
    (docker_dir / "Dockerfile.python").write_text(
        "FROM python:3.12-slim-bookworm\nWORKDIR /app\n"
        "HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \\\n"
        "    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1\n"
        'CMD ["uvicorn", "<package_name>.main:app"]\n'
    )
    (docker_dir / "compose.yaml.template").write_text("services:\n  myproject:\n    build: .\n")
    (docker_dir / "compose.dev.yaml.template").write_text("services:\n  myproject:\n    build: .\n")
    (docker_dir / "dockerignore.template").write_text(".venv\n__pycache__\n")
    (docker_dir / "Makefile.python").write_text(".PHONY: dev\ndev:\n\tuvicorn myproject.main:app\n")

    # Create python templates
    python_dir = scaffold_tpl / "python"
    python_dir.mkdir()
    (python_dir / "pyproject.toml.template").write_text('[project]\nname = "project-name"\n')

    # Create .windsurfrules and .windsurf/rules/ and .windsurf/workflows/
    (fabrik_root / ".windsurfrules").write_text("# rules\n")
    windsurf_rules = fabrik_root / ".windsurf" / "rules"
    windsurf_rules.mkdir(parents=True)
    (windsurf_rules / "10-python.md").write_text("# python rules\n")
    windsurf_workflows = fabrik_root / ".windsurf" / "workflows"
    windsurf_workflows.mkdir(parents=True)
    (windsurf_workflows / "test.md").write_text("# test workflow\n")

    # Create AGENTS.md and AGENTS-compact.md
    (fabrik_root / "AGENTS.md").write_text("# AGENTS\n")
    (fabrik_root / "AGENTS-compact.md").write_text("# AGENTS-compact\n")
    (fabrik_root / "opencode.json").write_text("{}\n")
    (fabrik_root / ".pre-commit-config.yaml").write_text("repos: []\n")

    # chrome-extension is now WXT (wxt.config.ts auto-generates the manifest at build) —
    # _scaffold_chrome_extension emits everything inline, reading no chrome-ext template,
    # so no templates/chrome-extension/ fixture is needed.

    return fabrik_root


def _scaffold_python_api(mock_fabrik_root: Path, temp_dir: Path, name: str = "test-svc") -> Path:
    """Helper to run python-api scaffold with mocked root."""
    from fabrik import scaffold

    project_dir = temp_dir / name
    project_dir.mkdir()

    with (
        patch.object(scaffold, "FABRIK_ROOT", mock_fabrik_root),
        patch.object(scaffold, "TEMPLATE_DIR", mock_fabrik_root / "templates" / "scaffold"),
        patch.object(scaffold, "FABRIK_AGENTS_MD", mock_fabrik_root / "AGENTS.md"),
        patch("subprocess.run"),
    ):
        scaffold._scaffold_shared(project_dir, name, "Test service", "2026-04-09", 8099)
        scaffold._scaffold_python_api(project_dir, name, "Test service")

    return project_dir


def _scaffold_chrome_ext(mock_fabrik_root: Path, temp_dir: Path, name: str = "test-ext") -> Path:
    """Helper to run chrome-extension scaffold with mocked root."""
    from fabrik import scaffold

    project_dir = temp_dir / name
    project_dir.mkdir()

    with (
        patch.object(scaffold, "FABRIK_ROOT", mock_fabrik_root),
        patch.object(scaffold, "TEMPLATE_DIR", mock_fabrik_root / "templates" / "scaffold"),
        patch.object(scaffold, "FABRIK_AGENTS_MD", mock_fabrik_root / "AGENTS.md"),
        patch("subprocess.run"),
    ):
        scaffold._scaffold_shared(project_dir, name, "Test extension", "2026-04-09", 8099)
        scaffold._scaffold_chrome_extension(project_dir, name, "Test extension")

    return project_dir


class TestPythonApiLogging:
    """Tests for python-api scaffold logging modules."""

    def test_logger_py_exists(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """logger.py is generated in the package directory."""
        project = _scaffold_python_api(mock_fabrik_root, temp_dir)
        assert (project / "src" / "test_svc" / "logger.py").exists()

    def test_logger_py_contains_get_logger(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """logger.py defines get_logger function."""
        project = _scaffold_python_api(mock_fabrik_root, temp_dir)
        content = (project / "src" / "test_svc" / "logger.py").read_text()
        assert "def get_logger" in content

    def test_logger_py_uses_structlog(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """logger.py configures structlog."""
        project = _scaffold_python_api(mock_fabrik_root, temp_dir)
        content = (project / "src" / "test_svc" / "logger.py").read_text()
        assert "structlog.configure" in content
        assert "structlog.contextvars.merge_contextvars" in content

    def test_logger_py_has_service_name(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """logger.py reads SERVICE_NAME env var with package_name fallback."""
        project = _scaffold_python_api(mock_fabrik_root, temp_dir)
        content = (project / "src" / "test_svc" / "logger.py").read_text()
        assert "SERVICE_NAME" in content
        assert "test_svc" in content

    def test_middleware_py_exists(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """middleware.py is generated in the package directory."""
        project = _scaffold_python_api(mock_fabrik_root, temp_dir)
        assert (project / "src" / "test_svc" / "middleware.py").exists()

    def test_middleware_has_correlation(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """middleware.py contains CorrelationMiddleware with ContextVar."""
        project = _scaffold_python_api(mock_fabrik_root, temp_dir)
        content = (project / "src" / "test_svc" / "middleware.py").read_text()
        assert "class CorrelationMiddleware" in content
        assert "ContextVar" in content
        assert "bind_contextvars" in content
        assert "unbind_contextvars" in content

    def test_main_imports_logger_and_middleware(
        self, mock_fabrik_root: Path, temp_dir: Path
    ) -> None:
        """main.py imports from logger and middleware modules."""
        project = _scaffold_python_api(mock_fabrik_root, temp_dir)
        content = (project / "src" / "test_svc" / "main.py").read_text()
        assert "from test_svc.logger import get_logger" in content
        assert "from test_svc.middleware import CorrelationMiddleware" in content
        assert "app.add_middleware(CorrelationMiddleware)" in content

    def test_main_uses_structured_logging(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """main.py uses logger.info for startup/shutdown."""
        project = _scaffold_python_api(mock_fabrik_root, temp_dir)
        content = (project / "src" / "test_svc" / "main.py").read_text()
        assert 'logger.info("service_starting"' in content
        assert 'logger.info("service_stopping")' in content
        assert 'logger.error("health_check_failed"' in content

    def test_requirements_includes_structlog(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """requirements.txt includes structlog."""
        project = _scaffold_python_api(mock_fabrik_root, temp_dir)
        content = (project / "requirements.txt").read_text()
        assert "structlog>=24.0.0" in content

    def test_env_example_has_service_name(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """.env.example contains SERVICE_NAME."""
        project = _scaffold_python_api(mock_fabrik_root, temp_dir)
        content = (project / ".env.example").read_text()
        assert "SERVICE_NAME=test-svc" in content

    def test_test_health_has_correlation_tests(
        self, mock_fabrik_root: Path, temp_dir: Path
    ) -> None:
        """test_health.py includes correlation ID test functions."""
        project = _scaffold_python_api(mock_fabrik_root, temp_dir)
        content = (project / "tests" / "test_health.py").read_text()
        assert "def test_health_returns_correlation_id" in content
        assert "def test_health_preserves_provided_request_id" in content
        assert '"x-request-id" in response.headers' in content
        assert '"X-Request-ID": "test-123"' in content

    def test_no_print_in_scaffolded_python(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """No print() in scaffolded Python files."""
        project = _scaffold_python_api(mock_fabrik_root, temp_dir)
        for py_file in (project / "src" / "test_svc").glob("*.py"):
            content = py_file.read_text()
            # Skip __init__.py (empty)
            if py_file.name == "__init__.py":
                continue
            assert "print(" not in content, f"print() found in {py_file.name}"


class TestChromeExtensionLogging:
    """Tests for chrome-extension scaffold logging modules."""

    def test_server_logger_exists(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """logger.py is generated in the server package directory."""
        project = _scaffold_chrome_ext(mock_fabrik_root, temp_dir)
        assert (project / "server" / "src" / "test_ext" / "logger.py").exists()

    def test_server_middleware_exists(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """middleware.py is generated in the server package directory."""
        project = _scaffold_chrome_ext(mock_fabrik_root, temp_dir)
        assert (project / "server" / "src" / "test_ext" / "middleware.py").exists()

    def test_server_logger_content(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """Server logger.py has structlog configuration."""
        project = _scaffold_chrome_ext(mock_fabrik_root, temp_dir)
        content = (project / "server" / "src" / "test_ext" / "logger.py").read_text()
        assert "def get_logger" in content
        assert "structlog.configure" in content
        assert "merge_contextvars" in content

    def test_server_main_imports(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """Server main.py imports logger and middleware."""
        project = _scaffold_chrome_ext(mock_fabrik_root, temp_dir)
        content = (project / "server" / "src" / "test_ext" / "main.py").read_text()
        assert "from test_ext.logger import get_logger" in content
        assert "from test_ext.middleware import CorrelationMiddleware" in content
        assert "app.add_middleware(CorrelationMiddleware)" in content

    def test_server_main_keeps_cors(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """Server main.py still has CORSMiddleware."""
        project = _scaffold_chrome_ext(mock_fabrik_root, temp_dir)
        content = (project / "server" / "src" / "test_ext" / "main.py").read_text()
        assert "CORSMiddleware" in content

    def test_requirements_includes_structlog(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """requirements.txt includes structlog."""
        project = _scaffold_chrome_ext(mock_fabrik_root, temp_dir)
        content = (project / "requirements.txt").read_text()
        assert "structlog>=24.0.0" in content

    def test_env_example_has_service_name(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """.env.example contains SERVICE_NAME inline."""
        project = _scaffold_chrome_ext(mock_fabrik_root, temp_dir)
        content = (project / ".env.example").read_text()
        assert "SERVICE_NAME=test-ext" in content

    def test_no_structlog_in_extension_frontend(
        self, mock_fabrik_root: Path, temp_dir: Path
    ) -> None:
        """Extension frontend does not import structlog."""
        project = _scaffold_chrome_ext(mock_fabrik_root, temp_dir)
        for ts_file in (project / "extension" / "src").rglob("*.ts*"):
            content = ts_file.read_text()
            assert "structlog" not in content


def _scaffold_file_worker(
    mock_fabrik_root: Path, temp_dir: Path, name: str = "test-worker"
) -> Path:
    """Helper to run file-worker scaffold with mocked root."""
    from fabrik import scaffold

    project_dir = temp_dir / name
    project_dir.mkdir()

    # Create minimal file-worker template (only worker/main.py is copied from template)
    fw_tpl = mock_fabrik_root / "templates" / "file-worker" / "worker"
    fw_tpl.mkdir(parents=True)
    (fw_tpl / "main.py").write_text('"""Placeholder worker main."""\n')

    with (
        patch.object(scaffold, "FABRIK_ROOT", mock_fabrik_root),
        patch.object(scaffold, "TEMPLATE_DIR", mock_fabrik_root / "templates" / "scaffold"),
        patch.object(
            scaffold, "FILE_WORKER_TEMPLATE_DIR", mock_fabrik_root / "templates" / "file-worker"
        ),
        patch.object(scaffold, "FABRIK_AGENTS_MD", mock_fabrik_root / "AGENTS.md"),
        patch("subprocess.run"),
    ):
        scaffold._scaffold_shared(project_dir, name, "Test worker", "2026-04-09", 8099)
        scaffold._scaffold_file_worker(project_dir, name, "Test worker")

    return project_dir


class TestFileWorkerLogging:
    """Tests for file-worker scaffold logging module."""

    def test_logger_py_exists(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """worker/logger.py is generated."""
        project = _scaffold_file_worker(mock_fabrik_root, temp_dir)
        assert (project / "worker" / "logger.py").exists()

    def test_logger_py_uses_print_logger_factory(
        self, mock_fabrik_root: Path, temp_dir: Path
    ) -> None:
        """worker/logger.py uses PrintLoggerFactory, not stdlib.LoggerFactory."""
        project = _scaffold_file_worker(mock_fabrik_root, temp_dir)
        content = (project / "worker" / "logger.py").read_text()
        assert "structlog.PrintLoggerFactory()" in content
        assert "structlog.stdlib.LoggerFactory()" not in content

    def test_logger_py_has_context_class_dict(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """worker/logger.py sets context_class=dict."""
        project = _scaffold_file_worker(mock_fabrik_root, temp_dir)
        content = (project / "worker" / "logger.py").read_text()
        assert "context_class=dict" in content

    def test_logger_py_has_correct_processors(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """worker/logger.py has all required processors."""
        project = _scaffold_file_worker(mock_fabrik_root, temp_dir)
        content = (project / "worker" / "logger.py").read_text()
        # Matches the unified _logger_py_content contract (shared with python-api):
        # merge_contextvars, add_log_level, TimeStamper, _redact_sensitive, JSONRenderer.
        assert "merge_contextvars" in content
        assert "add_log_level" in content
        assert "TimeStamper" in content
        assert "_redact_sensitive" in content
        assert "JSONRenderer" in content

    def test_logger_py_has_bound_logger(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """worker/logger.py uses a filtering bound-logger wrapper class."""
        project = _scaffold_file_worker(mock_fabrik_root, temp_dir)
        content = (project / "worker" / "logger.py").read_text()
        assert "wrapper_class=structlog.make_filtering_bound_logger" in content

    def test_logger_py_caches_on_first_use(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """worker/logger.py sets cache_logger_on_first_use=True."""
        project = _scaffold_file_worker(mock_fabrik_root, temp_dir)
        content = (project / "worker" / "logger.py").read_text()
        assert "cache_logger_on_first_use=True" in content

    def test_get_logger_default_name(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """get_logger has __name__ default and service fallback."""
        project = _scaffold_file_worker(mock_fabrik_root, temp_dir)
        content = (project / "worker" / "logger.py").read_text()
        assert "def get_logger(name: str = __name__)" in content
        assert "SERVICE_NAME" in content
        # Fallback is the package name (snake_case), per the shared _logger_py_content.
        assert '"test_worker"' in content

    def test_env_example_has_service_name(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        """.env.example contains SERVICE_NAME with comment."""
        project = _scaffold_file_worker(mock_fabrik_root, temp_dir)
        content = (project / ".env.example").read_text()
        assert "# Service identity for structured logging" in content
        assert "SERVICE_NAME=test-worker" in content


class TestDataContractSeeding:
    """docs/data-contract.md is seeded for every type EXCEPT the docs-publisher (docusaurus),
    where it would leak into the public docs site. Regression guard for the
    `_NO_DATA_CONTRACT_TYPES` skip in `_scaffold_shared` — including that `static-site` (which maps
    to the DB-backed saas-skeleton scaffolder) is NOT wrongly excluded."""

    def _scaffold(self, mock_fabrik_root: Path, temp_dir: Path, project_type: str) -> Path:
        from fabrik import scaffold

        project_dir = temp_dir / f"proj-{project_type}"
        project_dir.mkdir()
        with (
            patch.object(scaffold, "FABRIK_ROOT", mock_fabrik_root),
            patch.object(scaffold, "TEMPLATE_DIR", mock_fabrik_root / "templates" / "scaffold"),
            patch.object(scaffold, "FABRIK_AGENTS_MD", mock_fabrik_root / "AGENTS.md"),
            patch("subprocess.run"),
        ):
            scaffold._scaffold_shared(project_dir, "svc", "Test", "2026-07-06", 8099, project_type)
        return project_dir

    def test_python_api_seeds_contract(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        project_dir = self._scaffold(mock_fabrik_root, temp_dir, "python-api")
        assert (project_dir / "docs" / "data-contract.md").exists()

    def test_static_site_seeds_contract(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        # static-site maps to the DB-backed saas-skeleton scaffolder — must NOT be excluded.
        project_dir = self._scaffold(mock_fabrik_root, temp_dir, "static-site")
        assert (project_dir / "docs" / "data-contract.md").exists()

    def test_docusaurus_skips_contract(self, mock_fabrik_root: Path, temp_dir: Path) -> None:
        # docusaurus publishes docs/ as a public site — the contract must NOT be seeded there.
        project_dir = self._scaffold(mock_fabrik_root, temp_dir, "docusaurus")
        assert not (project_dir / "docs" / "data-contract.md").exists()
