"""Tests for saas-skeleton pino logger scaffold generation."""

import json
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
class TestSaasSkeletonLogger:
    """Test saas-skeleton scaffold generates lib/logger.ts with pino."""

    def test_logger_ts_exists(self, tmp_path):
        """Verify lib/logger.ts is created during saas-skeleton scaffold."""
        create_project(
            name="test-saas-log",
            project_type="saas-skeleton",
            description="Test SaaS Logger",
            base=tmp_path,
        )
        project_dir = tmp_path / "test-saas-log"
        logger_path = project_dir / "lib" / "logger.ts"
        assert logger_path.exists(), "lib/logger.ts was not created"

    def test_logger_ts_imports_pino(self, tmp_path):
        """Verify lib/logger.ts contains pino import and default export."""
        create_project(
            name="test-saas-log",
            project_type="saas-skeleton",
            description="Test SaaS Logger",
            base=tmp_path,
        )
        project_dir = tmp_path / "test-saas-log"
        content = (project_dir / "lib" / "logger.ts").read_text()
        assert "import pino from 'pino'" in content
        assert "export default logger" in content

    def test_logger_ts_substitutes_project_name(self, tmp_path):
        """Verify lib/logger.ts has the project name as fallback SERVICE_NAME."""
        create_project(
            name="test-saas-log",
            project_type="saas-skeleton",
            description="Test SaaS Logger",
            base=tmp_path,
        )
        project_dir = tmp_path / "test-saas-log"
        content = (project_dir / "lib" / "logger.ts").read_text()
        assert "|| 'test-saas-log'" in content

    def test_package_json_has_pino_dependency(self, tmp_path):
        """Verify package.json contains pino dependency."""
        create_project(
            name="test-saas-log",
            project_type="saas-skeleton",
            description="Test SaaS Logger",
            base=tmp_path,
        )
        project_dir = tmp_path / "test-saas-log"
        pkg = json.loads((project_dir / "package.json").read_text())
        assert "pino" in pkg["dependencies"], "pino missing from dependencies"
        assert pkg["dependencies"]["pino"] == "^9.0.0"

    def test_static_site_also_gets_logger(self, tmp_path):
        """Verify static-site (alias for saas-skeleton) also gets lib/logger.ts."""
        create_project(
            name="test-static-log",
            project_type="static-site",
            description="Test Static Logger",
            base=tmp_path,
        )
        project_dir = tmp_path / "test-static-log"
        logger_path = project_dir / "lib" / "logger.ts"
        assert logger_path.exists(), "static-site should also generate lib/logger.ts"
        content = logger_path.read_text()
        assert "import pino from 'pino'" in content
        assert "|| 'test-static-log'" in content
