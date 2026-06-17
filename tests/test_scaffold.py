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
        ["python-api", "node-api", "file-api", "file-worker", "docusaurus"],
    )
    def test_scaffold_uses_droid_gitignore_block(self, project_type, tmp_path):
        """Verify these scaffold types use _DROID_GITIGNORE_BLOCK constant.

        (``wordpress`` dropped 2026-06-17 — scaffolding moved to /opt/wpf;
        ``fabrik scaffold --type wordpress`` now redirects instead of building.)
        """
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


@requires_fabrik_env
class TestProjectYamlHasUserGuide:
    """Test has_user_guide field is scaffolded into project.yaml."""

    def test_project_yaml_contains_has_user_guide(self, tmp_path):
        """Verify project.yaml includes has_user_guide: false by default."""
        create_project(
            name="test-guide",
            project_type="python-api",
            description="Test project",
            base=tmp_path,
        )
        project_dir = tmp_path / "test-guide"
        content = (project_dir / "project.yaml").read_text()
        assert "has_user_guide" in content, "has_user_guide field missing from project.yaml"

        import yaml

        data = yaml.safe_load(content)
        assert data["has_user_guide"] is False, "has_user_guide should default to false"

    # Aligned 2026-04-19 with intentional narrowing in commit f557c35 (2026-04-15)
    # which removed saas-skeleton/mobile-app/desktop-app from GUIDE_ENABLED_TYPES.
    @pytest.mark.parametrize("project_type", ["chrome-extension", "static-site"])
    def test_guide_enabled_type_sets_true(self, tmp_path, project_type):
        """Verify guide-enabled scaffold types set has_user_guide: true."""
        create_project(
            name="test-guide-enabled",
            project_type=project_type,
            description="Test project",
            base=tmp_path,
        )
        project_dir = tmp_path / "test-guide-enabled"

        import yaml

        data = yaml.safe_load((project_dir / "project.yaml").read_text())
        assert data["has_user_guide"] is True, f"{project_type} should set has_user_guide: true"

    @pytest.mark.parametrize("project_type", ["node-api", "docusaurus"])
    def test_non_guide_type_stays_false(self, tmp_path, project_type):
        """Verify non-guide scaffold types keep has_user_guide: false."""
        create_project(
            name="test-guide-disabled",
            project_type=project_type,
            description="Test project",
            base=tmp_path,
        )
        project_dir = tmp_path / "test-guide-disabled"

        import yaml

        data = yaml.safe_load((project_dir / "project.yaml").read_text())
        assert data["has_user_guide"] is False, f"{project_type} should keep has_user_guide: false"


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
        """Verify extension/ directory structure with manifest, Vite, stubs."""
        create_project(
            name="test-ext",
            project_type="chrome-extension",
            description="Test Extension",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-ext"

        # Verify extension/ structure
        assert (project_dir / "extension" / "src").is_dir()
        assert (project_dir / "extension" / "icons").is_dir()

        # Verify core files (Vite + CRXJS, not webpack)
        assert (project_dir / "extension" / "manifest.json").exists()
        assert (project_dir / "extension" / "package.json").exists()
        assert (project_dir / "extension" / "vite.config.ts").exists()
        assert not (project_dir / "extension" / "webpack.config.js").exists()

        # Verify stubs
        assert (project_dir / "extension" / "src" / "popup.ts").exists()
        assert (project_dir / "extension" / "src" / "background.ts").exists()
        assert (project_dir / "extension" / "src" / "content.ts").exists()
        assert (project_dir / "extension" / "src" / "popup.html").exists()

        # Verify manifest content
        manifest = (project_dir / "extension" / "manifest.json").read_text()
        assert '"name": "test-ext"' in manifest
        assert '"description": "Test Extension"' in manifest

    def test_extension_uses_vite_crxjs(self, tmp_path):
        """Verify extension uses Vite + CRXJS, not webpack."""
        create_project(
            name="test-ext",
            project_type="chrome-extension",
            description="Test Extension",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-ext"

        # Verify vite.config.ts content
        vite_config = (project_dir / "extension" / "vite.config.ts").read_text()
        assert "@crxjs/vite-plugin" in vite_config
        assert "crx({ manifest })" in vite_config

        # Verify package.json uses Vite + CRXJS deps
        import json

        pkg = json.loads((project_dir / "extension" / "package.json").read_text())
        assert "vite" in pkg["scripts"]["dev"]
        assert "vite build" in pkg["scripts"]["build"]
        assert "@crxjs/vite-plugin" in pkg["devDependencies"]
        assert "vite" in pkg["devDependencies"]
        # No webpack deps
        assert "webpack" not in pkg.get("devDependencies", {})
        assert "webpack-cli" not in pkg.get("devDependencies", {})

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
        assert "platform: linux/amd64" in compose
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

    def test_test_workflow_is_wired_correctly(self, tmp_path):
        """Verify test workflow runs out-of-box (BUG-3 regression guard)."""
        create_project(
            name="test-ext",
            project_type="chrome-extension",
            description="Test Extension",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-ext"

        # Verify pytest in requirements.txt
        reqs = (project_dir / "requirements.txt").read_text()
        assert "pytest" in reqs, "pytest missing from requirements.txt"

        # Verify Makefile test target has PYTHONPATH
        makefile = (project_dir / "Makefile").read_text()
        assert "PYTHONPATH=server/src" in makefile, "PYTHONPATH not set in Makefile test target"
        assert ".venv/bin/pytest" in makefile, "pytest not invoked via .venv in Makefile"

        # Verify test file exists with correct import
        test_health = (project_dir / "tests" / "test_health.py").read_text()
        assert "from test_ext.main import app" in test_health, "test imports package incorrectly"
        assert "TestClient" in test_health, "TestClient not imported in tests"


@requires_fabrik_env
class TestStaticSiteScaffold:
    """Test static-site scaffold generates saas-skeleton structure with correct type."""

    def test_generates_project_yaml_with_static_site_type(self, tmp_path):
        """Verify project.yaml has type: static-site, not saas-skeleton."""
        create_project(
            name="test-static",
            project_type="static-site",
            description="Test Static Site",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-static"
        project_yaml = (project_dir / "project.yaml").read_text()
        assert "type: static-site" in project_yaml
        assert "type: saas-skeleton" not in project_yaml

    def test_generates_saas_skeleton_structure(self, tmp_path):
        """Verify static-site output matches saas-skeleton structure."""
        create_project(
            name="test-static",
            project_type="static-site",
            description="Test Static Site",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-static"

        # Shared required files present
        assert (project_dir / "README.md").exists()
        assert (project_dir / "CHANGELOG.md").exists()
        assert (project_dir / "docs" / "README.md").exists()

    def test_assigns_frontend_port_range(self, tmp_path):
        """Verify port is in frontend range (3000-3099), not Python range."""
        create_project(
            name="test-static",
            project_type="static-site",
            description="Test Static Site",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-static"
        project_yaml = (project_dir / "project.yaml").read_text()
        # Port should be in 3000-3099 range
        import re

        port_match = re.search(r"- (\d+)", project_yaml)
        assert port_match, "No port found in project.yaml"
        port = int(port_match.group(1))
        assert 3000 <= port <= 3099, f"Port {port} not in frontend range 3000-3099"


@requires_fabrik_env
class TestMobileAppScaffold:
    """Test mobile-app scaffold generates template-backed React Native structure."""

    def test_uses_react_native_scripts(self, tmp_path):
        """Verify package.json has React Native scripts, not Expo."""
        import json

        create_project(
            name="test-mobile",
            project_type="mobile-app",
            description="Test Mobile App",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-mobile"
        pkg = json.loads((project_dir / "package.json").read_text())
        scripts = pkg["scripts"]

        # React Native scripts must be present
        assert scripts["start"] == "react-native start"
        assert scripts["android"] == "react-native run-android"
        assert scripts["ios"] == "react-native run-ios"

        # No Expo references
        for key, val in scripts.items():
            assert "expo" not in val.lower(), f"Expo reference found in scripts.{key}: {val}"

    def test_has_full_react_native_deps(self, tmp_path):
        """Verify package.json has real React Native deps from template."""
        import json

        create_project(
            name="test-mobile",
            project_type="mobile-app",
            description="Test Mobile App",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-mobile"
        pkg = json.loads((project_dir / "package.json").read_text())

        # Must have full deps from template, not bare inline
        assert "react-native" in pkg.get("dependencies", {}), "Missing react-native dep"
        assert "react" in pkg.get("dependencies", {}), "Missing react dep"
        assert "@react-navigation/native" in pkg.get("dependencies", {}), "Missing navigation dep"

    def test_creates_navigation_tree(self, tmp_path):
        """Verify src/navigation/ tree is copied from template."""
        create_project(
            name="test-mobile",
            project_type="mobile-app",
            description="Test Mobile App",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-mobile"
        nav = project_dir / "src" / "navigation" / "AppNavigator.tsx"
        assert nav.exists(), "src/navigation/AppNavigator.tsx not created"
        content = nav.read_text()
        assert "NavigationContainer" in content, "AppNavigator missing NavigationContainer"

        types_file = project_dir / "src" / "navigation" / "types.ts"
        assert types_file.exists(), "src/navigation/types.ts not created"

    def test_creates_features_tree(self, tmp_path):
        """Verify src/features/ tree is copied from template."""
        create_project(
            name="test-mobile",
            project_type="mobile-app",
            description="Test Mobile App",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-mobile"
        assert (project_dir / "src" / "features" / "files" / "types.ts").exists()
        assert (project_dir / "src" / "features" / "files" / "services" / "fileService.ts").exists()

    def test_creates_entry_file(self, tmp_path):
        """Verify src/App.tsx exists with SafeAreaProvider (template content)."""
        create_project(
            name="test-mobile",
            project_type="mobile-app",
            description="Test Mobile App",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-mobile"
        app_tsx = project_dir / "src" / "App.tsx"
        assert app_tsx.exists(), "src/App.tsx not created"
        content = app_tsx.read_text()
        assert "SafeAreaProvider" in content, "App.tsx missing SafeAreaProvider from template"

    def test_no_dockerfile(self, tmp_path):
        """Verify mobile-app does not generate Docker files (non-container)."""
        create_project(
            name="test-mobile",
            project_type="mobile-app",
            description="Test Mobile App",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-mobile"
        assert not (project_dir / "Dockerfile").exists()


@requires_fabrik_env
class TestDesktopAppScaffold:
    """Test desktop-app scaffold generates template-backed Electron structure."""

    def test_uses_electron_scripts(self, tmp_path):
        """Verify package.json has Electron scripts from template."""
        import json

        create_project(
            name="test-desktop",
            project_type="desktop-app",
            description="Test Desktop App",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-desktop"
        pkg = json.loads((project_dir / "package.json").read_text())

        assert pkg["scripts"]["dev"] == "electron ."
        assert "electron-builder" in pkg["scripts"]["build"]

    def test_has_electron_deps(self, tmp_path):
        """Verify package.json has Electron deps from template."""
        import json

        create_project(
            name="test-desktop",
            project_type="desktop-app",
            description="Test Desktop App",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-desktop"
        pkg = json.loads((project_dir / "package.json").read_text())

        assert "electron" in pkg.get("devDependencies", {}), "Missing electron devDep"
        assert "electron-builder" in pkg.get("devDependencies", {}), "Missing electron-builder"

    def test_has_build_config(self, tmp_path):
        """Verify package.json has electron-builder build config with project name."""
        import json

        create_project(
            name="test-desktop",
            project_type="desktop-app",
            description="Test Desktop App",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-desktop"
        pkg = json.loads((project_dir / "package.json").read_text())

        assert "build" in pkg, "Missing build config"
        assert pkg["build"]["appId"] == "com.fabrik.test-desktop"
        assert pkg["build"]["productName"] == "test-desktop"

    def test_creates_electron_main(self, tmp_path):
        """Verify electron/main.js is copied from template."""
        create_project(
            name="test-desktop",
            project_type="desktop-app",
            description="Test Desktop App",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-desktop"
        main_js = project_dir / "electron" / "main.js"
        assert main_js.exists(), "electron/main.js not created"
        content = main_js.read_text()
        assert "BrowserWindow" in content, "main.js missing BrowserWindow"
        assert "contextIsolation: true" in content, "main.js missing security setting"

    def test_creates_index_html(self, tmp_path):
        """Verify index.html is created (referenced by electron/main.js)."""
        create_project(
            name="test-desktop",
            project_type="desktop-app",
            description="Test Desktop App",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-desktop"
        index = project_dir / "index.html"
        assert index.exists(), "index.html not created"
        assert "test-desktop" in index.read_text()

    def test_name_substitution(self, tmp_path):
        """Verify project name is substituted in package.json."""
        import json

        create_project(
            name="my-electron-app",
            project_type="desktop-app",
            description="My Electron App",
            base=tmp_path,
        )

        project_dir = tmp_path / "my-electron-app"
        pkg = json.loads((project_dir / "package.json").read_text())
        assert pkg["name"] == "my-electron-app"
        assert pkg["description"] == "My Electron App"


@requires_fabrik_env
class TestDocusaurusScaffold:
    """Test docusaurus scaffold generates template-backed Docusaurus structure."""

    def test_has_docusaurus_deps(self, tmp_path):
        """Verify package.json has full Docusaurus deps from template."""
        import json

        create_project(
            name="test-docs",
            project_type="docusaurus",
            description="Test Docs Site",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-docs"
        pkg = json.loads((project_dir / "package.json").read_text())

        deps = pkg.get("dependencies", {})
        assert "@docusaurus/core" in deps, "Missing @docusaurus/core"
        assert "@docusaurus/preset-classic" in deps, "Missing preset-classic"
        assert "react" in deps, "Missing react"

    def test_has_docusaurus_scripts(self, tmp_path):
        """Verify package.json has Docusaurus scripts from template."""
        import json

        create_project(
            name="test-docs",
            project_type="docusaurus",
            description="Test Docs Site",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-docs"
        pkg = json.loads((project_dir / "package.json").read_text())
        scripts = pkg["scripts"]

        assert scripts["start"] == "docusaurus start"
        assert scripts["build"] == "docusaurus build"
        assert scripts["serve"] == "docusaurus serve"

    def test_creates_config(self, tmp_path):
        """Verify docusaurus.config.js is generated with full OpenAPI contract."""
        create_project(
            name="test-docs",
            project_type="docusaurus",
            description="Test Docs Site",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-docs"
        config = project_dir / "docusaurus.config.js"
        assert config.exists(), "docusaurus.config.js not created"
        content = config.read_text()
        assert "test-docs" in content, "Config missing project name"
        assert "prismThemes" in content, "Config missing prism themes"

        # OpenAPI template contract
        assert '@theme/ApiItem' in content, "Config missing docItemComponent"
        assert "docusaurus-plugin-openapi-docs" in content, "Config missing OpenAPI plugin"
        assert "docusaurus-theme-openapi-docs" in content, "Config missing OpenAPI theme"
        assert "apiSidebar" in content, "Config missing apiSidebar navbar item"

    def test_creates_sidebars(self, tmp_path):
        """Verify sidebars.js is generated with apiSidebar."""
        create_project(
            name="test-docs",
            project_type="docusaurus",
            description="Test Docs Site",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-docs"
        sidebars = project_dir / "sidebars.js"
        assert sidebars.exists(), "sidebars.js not created"
        content = sidebars.read_text()
        assert "guideSidebar" in content
        assert "apiSidebar" in content, "sidebars.js missing apiSidebar"
        assert "docs/api/sidebar.js" in content, "sidebars.js missing api sidebar require"

    def test_creates_openapi_yaml(self, tmp_path):
        """Verify openapi.yaml placeholder is created."""
        create_project(
            name="test-docs",
            project_type="docusaurus",
            description="Test Docs Site",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-docs"
        spec = project_dir / "openapi.yaml"
        assert spec.exists(), "openapi.yaml not created"
        content = spec.read_text()
        assert "openapi: 3.0.3" in content
        assert "test-docs" in content, "openapi.yaml missing project name"

    def test_creates_api_sidebar(self, tmp_path):
        """Verify docs/api/sidebar.js placeholder is created."""
        create_project(
            name="test-docs",
            project_type="docusaurus",
            description="Test Docs Site",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-docs"
        sidebar = project_dir / "docs" / "api" / "sidebar.js"
        assert sidebar.exists(), "docs/api/sidebar.js not created"
        content = sidebar.read_text()
        assert "module.exports" in content
        assert "gen-api" in content, "sidebar.js missing gen-api regeneration hint"

    def test_creates_intro_doc(self, tmp_path):
        """Verify docs/intro.md is created with frontmatter."""
        create_project(
            name="test-docs",
            project_type="docusaurus",
            description="Test Docs Site",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-docs"
        intro = project_dir / "docs" / "intro.md"
        assert intro.exists(), "docs/intro.md not created"
        content = intro.read_text()
        assert "sidebar_position" in content, "intro.md missing frontmatter"
        assert "test-docs" in content

    def test_creates_custom_css(self, tmp_path):
        """Verify src/css/custom.css is created."""
        create_project(
            name="test-docs",
            project_type="docusaurus",
            description="Test Docs Site",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-docs"
        css = project_dir / "src" / "css" / "custom.css"
        assert css.exists(), "src/css/custom.css not created"
        assert "--ifm-color-primary" in css.read_text()

    def test_creates_static_dir(self, tmp_path):
        """Verify static/img/ directory is created."""
        create_project(
            name="test-docs",
            project_type="docusaurus",
            description="Test Docs Site",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-docs"
        assert (project_dir / "static" / "img").is_dir()

    def test_name_substitution(self, tmp_path):
        """Verify project name is substituted in package.json."""
        import json

        create_project(
            name="my-docs-site",
            project_type="docusaurus",
            description="My Docs",
            base=tmp_path,
        )

        project_dir = tmp_path / "my-docs-site"
        pkg = json.loads((project_dir / "package.json").read_text())
        assert pkg["name"] == "my-docs-site-docs"
        assert pkg["description"] == "My Docs"


@requires_fabrik_env
class TestWorkflowsPropagation:
    """Test .windsurf/workflows/ is propagated during scaffold."""

    def test_scaffold_copies_workflows(self, tmp_path):
        """Verify .windsurf/workflows/ directory exists in scaffolded projects."""
        create_project(
            name="test-workflows",
            project_type="python-api",
            description="Test Workflows",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-workflows"
        workflows_dir = project_dir / ".windsurf" / "workflows"
        assert workflows_dir.exists(), ".windsurf/workflows/ not created during scaffold"
        assert workflows_dir.is_dir(), ".windsurf/workflows/ is not a directory"

        # Verify at least one workflow file was copied
        workflow_files = list(workflows_dir.glob("*.md"))
        assert len(workflow_files) > 0, "No workflow files found in .windsurf/workflows/"

    def test_fix_project_refreshes_workflows(self, tmp_path):
        """Verify fix_project() copies .windsurf/workflows/ to existing projects."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        _ = fix_project(project_dir, dry_run=False)

        workflows_dir = project_dir / ".windsurf" / "workflows"
        assert workflows_dir.exists(), "fix_project() did not create .windsurf/workflows/"
        assert workflows_dir.is_dir()

        workflow_files = list(workflows_dir.glob("*.md"))
        assert len(workflow_files) > 0, "No workflow files after fix_project()"


class TestDocsSiteVendoring:
    """saas-skeleton auto-vendors fabrik-lib/docs-site; static-site does not."""

    def test_dispatch_scopes_docs_to_saas_only(self):
        from fabrik.scaffold import (
            _TYPE_SCAFFOLDERS,
            _scaffold_saas_skeleton,
            _scaffold_saas_skeleton_with_docs,
        )

        assert _TYPE_SCAFFOLDERS["saas-skeleton"] is _scaffold_saas_skeleton_with_docs
        # static-site reuses the bare saas scaffolder — it is not a SaaS, no docs site.
        assert _TYPE_SCAFFOLDERS["static-site"] is _scaffold_saas_skeleton

    def test_vendor_docs_site_noop_when_source_missing(self, tmp_path, monkeypatch):
        """A missing fabrik-lib must not hard-fail the scaffold."""
        import fabrik.scaffold as scaffold_mod

        monkeypatch.setattr(scaffold_mod, "FABRIK_LIB_DIR", tmp_path / "nonexistent")
        proj = tmp_path / "acme"
        proj.mkdir()
        scaffold_mod._vendor_docs_site(proj, "acme")  # must not raise
        assert not (proj / "docs-site").exists()

    @requires_fabrik_env
    def test_vendor_docs_site_copies_template(self, tmp_path):
        import json

        from fabrik.scaffold import FABRIK_LIB_DIR, _vendor_docs_site

        if not (FABRIK_LIB_DIR / "docs-site").is_dir():
            pytest.skip("fabrik-lib/docs-site not present")

        proj = tmp_path / "acme"
        proj.mkdir()
        _vendor_docs_site(proj, "acme")

        ds = proj / "docs-site"
        assert (ds / "docusaurus.config.js").exists()
        assert (ds / "docs").is_dir()
        # Build artefacts excluded; local .gitignore written.
        assert not (ds / "node_modules").exists()
        assert (ds / ".gitignore").exists()
        # Package name pointed at the project.
        assert json.loads((ds / "package.json").read_text())["name"] == "acme-docs"
