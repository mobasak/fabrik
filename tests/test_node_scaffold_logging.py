"""Tests for node-api and file-api scaffold pino logging integration."""

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
class TestNodeApiLogging:
    """Test node-api scaffold generates pino logging files."""

    def test_logger_js_created(self, tmp_path):
        """Verify src/logger.js is created."""
        create_project(
            name="test-node-log", project_type="node-api", description="Test", base=tmp_path
        )
        assert (tmp_path / "test-node-log" / "src" / "logger.js").exists()

    def test_logger_js_uses_pino(self, tmp_path):
        """Verify logger.js imports pino and exports logger (ESM per 12-node.md)."""
        create_project(
            name="test-node-log", project_type="node-api", description="Test", base=tmp_path
        )
        content = (tmp_path / "test-node-log" / "src" / "logger.js").read_text()
        assert "import pino from 'pino'" in content, "logger.js must import pino (ESM)"
        assert "export const logger" in content, "logger.js must export named logger"
        assert "export default logger" in content, "logger.js must default-export logger"
        # Mandatory redact paths keep tokens out of Loki (12-node.md).
        assert "redact:" in content, "logger.js must declare pino redact paths"

    def test_logger_js_uses_service_name(self, tmp_path):
        """Verify logger.js references SERVICE_NAME env var with project name fallback."""
        create_project(
            name="test-node-log", project_type="node-api", description="Test", base=tmp_path
        )
        content = (tmp_path / "test-node-log" / "src" / "logger.js").read_text()
        assert "process.env.SERVICE_NAME" in content, "Must read SERVICE_NAME from env"
        assert "'test-node-log'" in content, "Must use project name as fallback"

    def test_index_js_no_console_log(self, tmp_path):
        """Verify index.js has zero console.log occurrences."""
        create_project(
            name="test-node-log", project_type="node-api", description="Test", base=tmp_path
        )
        content = (tmp_path / "test-node-log" / "src" / "index.js").read_text()
        assert "console.log" not in content, "index.js must not contain console.log"

    def test_index_js_uses_logger(self, tmp_path):
        """Verify index.js imports and uses the logger module."""
        create_project(
            name="test-node-log", project_type="node-api", description="Test", base=tmp_path
        )
        content = (tmp_path / "test-node-log" / "src" / "index.js").read_text()
        assert "from './logger.js'" in content, "Must import logger (ESM)"
        assert "logger.info(" in content, "Must use logger.info()"

    def test_index_js_has_request_id_correlation(self, tmp_path):
        """Verify index.js generates X-Request-ID and carries it via AsyncLocalStorage.

        12-node.md mandates ambient correlation context (AsyncLocalStorage)
        over prop-drilling child loggers through business code.
        """
        create_project(
            name="test-node-log", project_type="node-api", description="Test", base=tmp_path
        )
        content = (tmp_path / "test-node-log" / "src" / "index.js").read_text()
        assert "randomUUID" in content, "Must import randomUUID from crypto"
        assert "x-request-id" in content, "Must read x-request-id header"
        assert "X-Request-ID" in content, "Must set X-Request-ID response header"
        assert "AsyncLocalStorage" in content, "Must use AsyncLocalStorage for ambient context"
        assert "traceId" in content, "Ambient context must carry traceId"

    def test_index_js_service_starting_event(self, tmp_path):
        """Verify index.js logs service_starting event on listen."""
        create_project(
            name="test-node-log", project_type="node-api", description="Test", base=tmp_path
        )
        content = (tmp_path / "test-node-log" / "src" / "index.js").read_text()
        assert "event: 'service_starting'" in content, "Must log service_starting event"

    def test_package_json_has_pino_dep(self, tmp_path):
        """Verify package.json includes pino dependency."""
        create_project(
            name="test-node-log", project_type="node-api", description="Test", base=tmp_path
        )
        pkg = json.loads((tmp_path / "test-node-log" / "package.json").read_text())
        assert "pino" in pkg.get("dependencies", {}), "package.json must list pino dependency"

    def test_env_example_has_service_name(self, tmp_path):
        """Verify .env.example includes SERVICE_NAME."""
        create_project(
            name="test-node-log", project_type="node-api", description="Test", base=tmp_path
        )
        content = (tmp_path / "test-node-log" / ".env.example").read_text()
        assert "SERVICE_NAME=test-node-log" in content, ".env.example must include SERVICE_NAME"


@requires_fabrik_env
class TestFileApiLogging:
    """Test file-api scaffold generates pino logging files."""

    def test_logger_js_created(self, tmp_path):
        """Verify src/logger.js is created."""
        create_project(
            name="test-file-log", project_type="file-api", description="Test", base=tmp_path
        )
        assert (tmp_path / "test-file-log" / "src" / "logger.js").exists()

    def test_logger_js_uses_pino(self, tmp_path):
        """Verify logger.js requires pino and exports logger."""
        create_project(
            name="test-file-log", project_type="file-api", description="Test", base=tmp_path
        )
        content = (tmp_path / "test-file-log" / "src" / "logger.js").read_text()
        assert "require('pino')" in content, "logger.js must require pino"
        assert "module.exports = logger" in content, "logger.js must export logger"

    def test_logger_js_uses_service_name(self, tmp_path):
        """Verify logger.js references SERVICE_NAME env var with project name fallback."""
        create_project(
            name="test-file-log", project_type="file-api", description="Test", base=tmp_path
        )
        content = (tmp_path / "test-file-log" / "src" / "logger.js").read_text()
        assert "process.env.SERVICE_NAME" in content, "Must read SERVICE_NAME from env"
        assert "'test-file-log'" in content, "Must use project name as fallback"

    def test_package_json_has_pino_dep(self, tmp_path):
        """Verify package.json includes pino dependency."""
        create_project(
            name="test-file-log", project_type="file-api", description="Test", base=tmp_path
        )
        pkg = json.loads((tmp_path / "test-file-log" / "package.json").read_text())
        assert "pino" in pkg.get("dependencies", {}), "package.json must list pino dependency"

    def test_env_example_has_service_name(self, tmp_path):
        """Verify .env.example includes SERVICE_NAME."""
        create_project(
            name="test-file-log", project_type="file-api", description="Test", base=tmp_path
        )
        content = (tmp_path / "test-file-log" / ".env.example").read_text()
        assert "SERVICE_NAME=test-file-log" in content, ".env.example must include SERVICE_NAME"

    def test_index_js_no_console_log(self, tmp_path):
        """Verify index.js has zero console.log/console.error occurrences."""
        create_project(
            name="test-file-log", project_type="file-api", description="Test", base=tmp_path
        )
        content = (tmp_path / "test-file-log" / "src" / "index.js").read_text()
        assert "console.log" not in content, "index.js must not contain console.log"
        assert "console.error" not in content, "index.js must not contain console.error"

    def test_index_js_imports_logger(self, tmp_path):
        """Verify index.js imports the logger module."""
        create_project(
            name="test-file-log", project_type="file-api", description="Test", base=tmp_path
        )
        content = (tmp_path / "test-file-log" / "src" / "index.js").read_text()
        assert "require('./logger')" in content, "Must import logger"

    def test_index_js_service_starting_event(self, tmp_path):
        """Verify index.js logs service_starting event on listen."""
        create_project(
            name="test-file-log", project_type="file-api", description="Test", base=tmp_path
        )
        content = (tmp_path / "test-file-log" / "src" / "index.js").read_text()
        assert "event: 'service_starting'" in content, "Must log service_starting event"
