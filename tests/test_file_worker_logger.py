"""Tests for file-worker structured logger scaffold generation."""

import os
from pathlib import Path

import pytest

from fabrik.scaffold import create_project

FABRIK_ROOT = Path("/opt/fabrik")
requires_fabrik_env = pytest.mark.skipif(
    not FABRIK_ROOT.exists() or os.getenv("CI") == "true",
    reason="Requires full fabrik environment at /opt/fabrik (not available in CI)",
)


@requires_fabrik_env
class TestFileWorkerLogger:
    """Test file-worker scaffold generates worker/logger.py with structlog."""

    def test_logger_py_exists(self, tmp_path: Path) -> None:
        """Verify worker/logger.py is created during file-worker scaffold."""
        create_project(
            name="test-fw-log",
            project_type="file-worker",
            description="Test File Worker Logger",
            base=tmp_path,
        )
        project_dir = tmp_path / "test-fw-log"
        logger_path = project_dir / "worker" / "logger.py"
        assert logger_path.exists(), "worker/logger.py was not created"

    def test_logger_py_has_setup_and_get_logger(self, tmp_path: Path) -> None:
        """Verify worker/logger.py contains _setup_logging and get_logger."""
        create_project(
            name="test-fw-log",
            project_type="file-worker",
            description="Test File Worker Logger",
            base=tmp_path,
        )
        project_dir = tmp_path / "test-fw-log"
        content = (project_dir / "worker" / "logger.py").read_text()
        assert "def _setup_logging() -> None:" in content
        assert "def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:" in content
        assert "_setup_logging()" in content

    def test_logger_py_uses_json_renderer(self, tmp_path: Path) -> None:
        """Verify worker/logger.py configures JSONRenderer for production output."""
        create_project(
            name="test-fw-log",
            project_type="file-worker",
            description="Test File Worker Logger",
            base=tmp_path,
        )
        project_dir = tmp_path / "test-fw-log"
        content = (project_dir / "worker" / "logger.py").read_text()
        assert "structlog.processors.JSONRenderer()" in content
        assert "structlog.contextvars.merge_contextvars" in content
        assert "structlog.processors.add_log_level" in content
        assert 'structlog.processors.TimeStamper(fmt="iso")' in content

    def test_logger_py_substitutes_project_name(self, tmp_path: Path) -> None:
        """Verify worker/logger.py has the project name as fallback SERVICE_NAME."""
        create_project(
            name="test-fw-log",
            project_type="file-worker",
            description="Test File Worker Logger",
            base=tmp_path,
        )
        project_dir = tmp_path / "test-fw-log"
        content = (project_dir / "worker" / "logger.py").read_text()
        assert '"test-fw-log"' in content

    def test_main_py_imports_worker_logger(self, tmp_path: Path) -> None:
        """Verify main.py imports from worker.logger instead of raw structlog."""
        create_project(
            name="test-fw-log",
            project_type="file-worker",
            description="Test File Worker Logger",
            base=tmp_path,
        )
        project_dir = tmp_path / "test-fw-log"
        content = (project_dir / "worker" / "main.py").read_text()
        assert "from worker.logger import get_logger" in content
        assert "import structlog" not in content
        assert "structlog.configure" not in content

    def test_env_example_has_service_name(self, tmp_path: Path) -> None:
        """Verify .env.example contains SERVICE_NAME variable."""
        create_project(
            name="test-fw-log",
            project_type="file-worker",
            description="Test File Worker Logger",
            base=tmp_path,
        )
        project_dir = tmp_path / "test-fw-log"
        content = (project_dir / ".env.example").read_text()
        assert "SERVICE_NAME=test-fw-log" in content
