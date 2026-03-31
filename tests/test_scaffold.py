"""Tests for scaffold.py gitignore and .droid/ structure."""

import os
from pathlib import Path

import pytest

from fabrik.scaffold import (
    _DROID_DIR_GITIGNORE,
    _DROID_GITIGNORE_BLOCK,
    _TRAYCER_REPORTS_GITIGNORE,
    _patch_droid_block,
    create_project,
    fix_project,
)

# Skip tests that require full fabrik environment (templates at /opt/fabrik)
# These tests can only run locally where /opt/fabrik exists
FABRIK_ROOT = Path("/opt/fabrik")
requires_fabrik_env = pytest.mark.skipif(
    not FABRIK_ROOT.exists() or os.getenv("CI") == "true",
    reason="Requires full fabrik environment at /opt/fabrik (not available in CI)",
)


class TestDroidGitignoreBlock:
    """Test _DROID_GITIGNORE_BLOCK constant correctness."""

    def test_constant_contains_required_entries(self):
        """Verify all required runtime files are in the constant."""
        required = [
            ".droid/kilo_usage.jsonl",
            ".droid/reviews/",
            ".droid/kilo_models_cache.json",
            ".droid/.kilo_cache_last_refresh",
            ".droid/docs_queue/",
            ".droid/docs_log/",
            ".droid/traycer-reports/*.md",
        ]
        for entry in required:
            assert entry in _DROID_GITIGNORE_BLOCK, f"Missing {entry}"

    def test_no_dead_entries(self):
        """Verify removed phantom files are not in the constant."""
        dead_entries = [
            "kilo_metrics.jsonl",
            "review_sessions.jsonl",
            "review_audits.jsonl",
        ]
        for entry in dead_entries:
            assert entry not in _DROID_GITIGNORE_BLOCK, f"Dead entry {entry} still present"


class TestPatchDroidBlock:
    """Test _patch_droid_block() helper function."""

    def test_append_when_no_droid_entries(self):
        """Append canonical block when no .droid/ entries exist."""
        content = ".env\nnode_modules/\n*.log\n"
        result = _patch_droid_block(content, _DROID_GITIGNORE_BLOCK)
        assert ".droid/docs_queue/" in result
        assert result.startswith(".env\n")

    def test_replace_scattered_entries(self):
        """Replace scattered .droid/ entries with canonical block."""
        content = ".env\n.droid/old1\nlogs/\n.droid/old2\n*.log\n"
        result = _patch_droid_block(content, _DROID_GITIGNORE_BLOCK)
        assert ".droid/docs_queue/" in result
        assert ".droid/old1" not in result
        assert ".droid/old2" not in result
        assert "logs/\n" in result  # Non-.droid/ content preserved

    def test_noop_when_already_updated(self):
        """No change when .droid/ block is already canonical."""
        content = ".env\n" + _DROID_GITIGNORE_BLOCK + "*.log\n"
        result = _patch_droid_block(content, _DROID_GITIGNORE_BLOCK)
        assert result == content

    def test_replace_contiguous_block(self):
        """Replace contiguous .droid/ entries."""
        content = (
            ".env\n"
            ".droid/kilo_usage.jsonl\n"
            ".droid/reviews/\n"
            ".droid/kilo_models_cache.json\n"
            "*.log\n"
        )
        result = _patch_droid_block(content, _DROID_GITIGNORE_BLOCK)
        assert ".droid/docs_queue/" in result
        assert result.count(".droid/kilo_usage.jsonl") == 1  # Not duplicated


@requires_fabrik_env
class TestScaffoldGitignoreCoverage:
    """Test all scaffold types write correct .gitignore content."""

    @pytest.mark.parametrize(
        "project_type",
        ["python-api", "node-api", "file-api", "file-worker", "wordpress", "docusaurus"],
    )
    def test_scaffold_uses_droid_gitignore_block(self, project_type, tmp_path):
        """Verify all 6 scaffold types use _DROID_GITIGNORE_BLOCK constant."""
        # Scaffold the project with explicit base to avoid writing to /opt/
        create_project(
            name="test-project",
            project_type=project_type,
            description="Test project",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-project"

        # Read generated .gitignore
        gitignore_path = project_dir / ".gitignore"
        assert gitignore_path.exists(), f".gitignore not created for {project_type}"
        content = gitignore_path.read_text()

        # Verify all required entries from _DROID_GITIGNORE_BLOCK are present
        required_entries = [
            ".droid/kilo_usage.jsonl",
            ".droid/reviews/",
            ".droid/docs_queue/",
            ".droid/docs_log/",
            ".droid/traycer-reports/*.md",
        ]
        for entry in required_entries:
            assert entry in content, f"{entry} missing in {project_type} .gitignore"


class TestFixProjectDroidStructure:
    """Test fix_project() repairs .droid/ structure."""

    def test_creates_missing_droid_structure(self, tmp_path):
        """fix_project() creates missing .droid/ directories and files."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()  # Make it look like a git repo

        # Run fix_project
        _ = fix_project(project_dir, dry_run=False)

        # Verify .droid/ structure
        assert (project_dir / ".droid" / ".gitignore").exists()
        assert (project_dir / ".droid" / "review-context" / ".gitkeep").exists()
        assert (project_dir / ".droid" / "traycer-reports" / ".gitignore").exists()

        # Verify canonical content
        droid_gitignore = (project_dir / ".droid" / ".gitignore").read_text()
        assert droid_gitignore == _DROID_DIR_GITIGNORE

        traycer_gitignore = (project_dir / ".droid" / "traycer-reports" / ".gitignore").read_text()
        assert traycer_gitignore == _TRAYCER_REPORTS_GITIGNORE

    def test_updates_outdated_droid_gitignore(self, tmp_path):
        """fix_project() updates outdated .droid/.gitignore."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()
        droid_dir = project_dir / ".droid"
        droid_dir.mkdir()

        # Write old content
        (droid_dir / ".gitignore").write_text("# Old content\n*\n")

        _ = fix_project(project_dir, dry_run=False)

        # Verify content was updated
        droid_gitignore = (droid_dir / ".gitignore").read_text()
        assert "# Kilo/Traycer runtime files" in droid_gitignore
        content = (droid_dir / ".gitignore").read_text()
        assert content == _DROID_DIR_GITIGNORE

    def test_dry_run_reports_droid_changes(self, tmp_path):
        """fix_project() dry_run accurately reports .droid/ changes."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        added = fix_project(project_dir, dry_run=True)

        assert any(".droid/.gitignore" in item for item in added)
        assert any("review-context/.gitkeep" in item for item in added)
        assert any("traycer-reports/.gitignore" in item for item in added)

        # Verify nothing was actually written
        assert not (project_dir / ".droid" / ".gitignore").exists()


class TestFixProjectRootGitignorePatch:
    """Test fix_project() patches root .gitignore .droid/ block."""

    def test_patches_outdated_root_gitignore(self, tmp_path):
        """fix_project() updates root .gitignore with current _DROID_GITIGNORE_BLOCK."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        # Write .gitignore with old .droid/ entries
        (project_dir / ".gitignore").write_text(
            ".env\n"
            ".droid/kilo_usage.jsonl\n"
            ".droid/reviews/\n"
            "*.log\n"
        )

        added = fix_project(project_dir, dry_run=False)

        assert ".gitignore (.droid/ block updated)" in added
        content = (project_dir / ".gitignore").read_text()
        assert ".droid/docs_queue/" in content
        assert ".droid/docs_log/" in content
        assert content.count(".droid/kilo_usage.jsonl") == 1  # Not duplicated

    def test_appends_when_no_droid_entries(self, tmp_path):
        """fix_project() appends .droid/ block when missing entirely."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        # Write .gitignore with no .droid/ entries
        (project_dir / ".gitignore").write_text(".env\nnode_modules/\n*.log\n")

        added = fix_project(project_dir, dry_run=False)

        assert ".gitignore (.droid/ block updated)" in added
        content = (project_dir / ".gitignore").read_text()
        assert ".droid/docs_queue/" in content

    def test_noop_when_gitignore_already_updated(self, tmp_path):
        """fix_project() doesn't modify .gitignore if already up-to-date."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        # Write .gitignore with current block
        (project_dir / ".gitignore").write_text(
            ".env\n" + _DROID_GITIGNORE_BLOCK + "*.log\n"
        )

        added = fix_project(project_dir, dry_run=False)

        assert ".gitignore (.droid/ block updated)" not in added

    def test_dry_run_reports_gitignore_patch(self, tmp_path):
        """fix_project() dry_run reports .gitignore patch without writing."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        original_content = ".env\n.droid/old_entry\n*.log\n"
        (project_dir / ".gitignore").write_text(original_content)

        added = fix_project(project_dir, dry_run=True)

        assert ".gitignore (.droid/ block updated)" in added
        # Verify file wasn't actually modified
        assert (project_dir / ".gitignore").read_text() == original_content


class TestTracerReportsScaffolding:
    """Test traycer-reports/ directory scaffolding."""

    def test_traycer_reports_created_in_scaffold(self, tmp_path):
        """Verify traycer-reports/ is created with correct .gitignore."""
        create_project(
            name="test-project",
            project_type="python-api",
            description="Test",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-project"

        traycer_dir = project_dir / ".droid" / "traycer-reports"
        assert traycer_dir.exists()
        assert traycer_dir.is_dir()

        gitignore = traycer_dir / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text()
        assert "*.md" in content
        assert "!.gitignore" in content

    def test_droid_gitignore_allows_traycer_reports(self, tmp_path):
        """Verify .droid/.gitignore allows traycer-reports/.gitignore tracking."""
        create_project(
            name="test-project",
            project_type="python-api",
            description="Test",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-project"

        droid_gitignore = (project_dir / ".droid" / ".gitignore").read_text()
        assert "!traycer-reports/" in droid_gitignore
        assert "!traycer-reports/.gitignore" in droid_gitignore
        assert "traycer-reports/*.md" in droid_gitignore


@requires_fabrik_env
class TestChromeExtensionScaffold:
    """Test chrome-extension scaffold generates dual-artifact structure."""

    def test_creates_extension_directory_structure(self, tmp_path):
        """Verify extension/ directory structure with manifest, webpack, stubs."""
        create_project(
            name="test-ext",
            project_type="chrome-extension",
            description="Test Extension",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-ext"

        # Verify extension/ structure
        assert (project_dir / "extension" / "src").is_dir()
        assert (project_dir / "extension" / "public").is_dir()
        assert (project_dir / "extension" / "public" / "icons").is_dir()

        # Verify core files
        assert (project_dir / "extension" / "manifest.json").exists()
        assert (project_dir / "extension" / "package.json").exists()
        assert (project_dir / "extension" / "webpack.config.js").exists()

        # Verify stubs
        assert (project_dir / "extension" / "src" / "popup.ts").exists()
        assert (project_dir / "extension" / "src" / "background.ts").exists()
        assert (project_dir / "extension" / "src" / "content.ts").exists()
        assert (project_dir / "extension" / "public" / "popup.html").exists()

        # Verify manifest content
        manifest = (project_dir / "extension" / "manifest.json").read_text()
        assert '"name": "test-ext"' in manifest
        assert '"description": "Test Extension"' in manifest

    def test_creates_server_directory_structure(self, tmp_path):
        """Verify server/ directory structure with FastAPI backend."""
        create_project(
            name="test-ext",
            project_type="chrome-extension",
            description="Test Extension",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-ext"

        # Verify server/ structure (package name: test_ext)
        server_pkg = project_dir / "server" / "src" / "test_ext"
        assert server_pkg.is_dir()
        assert (server_pkg / "__init__.py").exists()
        assert (server_pkg / "main.py").exists()

        # Verify requirements.txt at root
        assert (project_dir / "requirements.txt").exists()
        reqs = (project_dir / "requirements.txt").read_text()
        assert "fastapi" in reqs
        assert "uvicorn" in reqs

        # Verify main.py content
        main_py = (server_pkg / "main.py").read_text()
        assert "FastAPI" in main_py
        assert "/health" in main_py
        assert "CORSMiddleware" in main_py

    def test_creates_docker_files(self, tmp_path):
        """Verify Dockerfile and compose.yaml at project root."""
        create_project(
            name="test-ext",
            project_type="chrome-extension",
            description="Test Extension",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-ext"

        # Verify files exist
        assert (project_dir / "Dockerfile").exists()
        assert (project_dir / "compose.yaml").exists()

        # Verify Dockerfile content
        dockerfile = (project_dir / "Dockerfile").read_text()
        assert "python:3.12-slim-bookworm" in dockerfile
        assert "PYTHONPATH=/app/server/src" in dockerfile
        assert "uvicorn test_ext.main:app" in dockerfile

        # Verify compose.yaml content
        compose = (project_dir / "compose.yaml").read_text()
        assert "platform: linux/arm64" in compose
        assert "coolify" in compose
        assert "/health" in compose

    def test_makefile_has_parallel_dev_target(self, tmp_path):
        """Verify Makefile contains parallel dev target with trap."""
        create_project(
            name="test-ext",
            project_type="chrome-extension",
            description="Test Extension",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-ext"

        # Verify Makefile exists
        assert (project_dir / "Makefile").exists()

        # Verify content
        makefile = (project_dir / "Makefile").read_text()
        assert "dev:" in makefile
        assert "trap 'kill 0' SIGINT" in makefile
        assert "npm run dev" in makefile
        assert "uvicorn" in makefile
        assert "dev-server:" in makefile
        assert "dev-ext:" in makefile
        assert "build-ext:" in makefile
        assert "docker-smoke:" in makefile

    def test_gitignore_includes_extension_artifacts(self, tmp_path):
        """Verify .gitignore includes extension build artifacts."""
        create_project(
            name="test-ext",
            project_type="chrome-extension",
            description="Test Extension",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-ext"

        gitignore = (project_dir / ".gitignore").read_text()
        assert "extension/dist/" in gitignore
        assert "extension/node_modules/" in gitignore

    def test_project_yaml_type_is_chrome_extension(self, tmp_path):
        """Verify project.yaml has correct type and port range."""
        create_project(
            name="test-ext",
            project_type="chrome-extension",
            description="Test Extension",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-ext"

        project_yaml = (project_dir / "project.yaml").read_text()
        assert "type: chrome-extension" in project_yaml

        # Verify port is in Python range (8000-8099)
        import yaml
        data = yaml.safe_load(project_yaml)
        port = data["ports"][0]
        assert 8000 <= port <= 8099

    def test_droid_gitignore_block_present(self, tmp_path):
        """Verify _DROID_GITIGNORE_BLOCK entries are in .gitignore."""
        create_project(
            name="test-ext",
            project_type="chrome-extension",
            description="Test Extension",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-ext"

        gitignore = (project_dir / ".gitignore").read_text()

        # Verify required .droid/ entries
        required_entries = [
            ".droid/kilo_usage.jsonl",
            ".droid/reviews/",
            ".droid/docs_queue/",
            ".droid/docs_log/",
            ".droid/traycer-reports/*.md",
        ]
        for entry in required_entries:
            assert entry in gitignore, f"{entry} missing in chrome-extension .gitignore"
