"""Tests for scaffold.py gitignore and .droid/ structure."""

import os
import re
from pathlib import Path

import pytest

from fabrik.scaffold import (
    _DROID_GITIGNORE_BLOCK,
    _RETIRED_DROID_GITIGNORE_LINES,
    MOBILE_APP_TEMPLATE_DIR,
    NODE_API_TEMPLATE_DIR,
    TYPE_REQUIRED_FILES,
    _patch_droid_block,
    create_project,
    fix_project,
)
from fabrik.version_registry import load_versions

# Skip tests that require full fabrik environment (templates at /opt/fabrik)
# These tests can only run locally where /opt/fabrik exists
FABRIK_ROOT = Path("/opt/fabrik")
requires_fabrik_env = pytest.mark.skipif(
    not FABRIK_ROOT.exists() or os.getenv("CI") == "true",
    reason="Requires full fabrik environment at /opt/fabrik (not available in CI)",
)


class TestDroidGitignoreBlock:
    """Test _DROID_GITIGNORE_BLOCK constant correctness."""

    def test_constant_holds_only_the_live_entries(self):
        """The block ignores docs_updater's two dirs and .factory/consultations/, nothing retired."""
        assert _DROID_GITIGNORE_BLOCK.splitlines() == [
            ".factory/consultations/",
            ".droid/docs_queue/",
            ".droid/docs_log/",
        ]
        for retired in _RETIRED_DROID_GITIGNORE_LINES:
            assert retired not in _DROID_GITIGNORE_BLOCK, retired

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
        """Replace scattered scaffold-written entries; a project's own .droid/ lines survive."""
        content = ".env\n.droid/reviews/\nlogs/\n.droid/old2\n.droid/kilo_usage.jsonl\n*.log\n"
        result = _patch_droid_block(content, _DROID_GITIGNORE_BLOCK)
        assert ".droid/docs_queue/" in result
        assert ".droid/reviews/" not in result
        assert ".droid/kilo_usage.jsonl" not in result
        assert ".droid/old2\n" in result  # the project's own line
        assert "logs/\n" in result  # Non-.droid/ content preserved

    def test_noop_when_already_updated(self):
        """No change when .droid/ block is already canonical."""
        content = ".env\n" + _DROID_GITIGNORE_BLOCK + "*.log\n"
        result = _patch_droid_block(content, _DROID_GITIGNORE_BLOCK)
        assert result == content

    def test_canonical_present_still_drops_a_stray_retired_line(self):
        """The fast path never keeps a retired line sitting beside an already-current block."""
        content = ".env\n" + _DROID_GITIGNORE_BLOCK + ".droid/reviews/\n*.log\n"
        result = _patch_droid_block(content, _DROID_GITIGNORE_BLOCK)
        assert ".droid/reviews/" not in result
        assert result.count(".droid/docs_queue/") == 1

    def test_replace_contiguous_block(self):
        """Replace contiguous retired entries with the reduced block."""
        content = (
            ".env\n.droid/kilo_usage.jsonl\n.droid/reviews/\n.droid/kilo_models_cache.json\n*.log\n"
        )
        result = _patch_droid_block(content, _DROID_GITIGNORE_BLOCK)
        assert ".droid/docs_queue/" in result
        assert ".droid/kilo_usage.jsonl" not in result  # retired, so replaced


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

        # The reduced _DROID_GITIGNORE_BLOCK is present and no retired line is
        for entry in (".droid/docs_queue/", ".droid/docs_log/"):
            assert entry in content, f"{entry} missing in {project_type} .gitignore"
        for retired in _RETIRED_DROID_GITIGNORE_LINES:
            assert retired not in content, f"{retired} still in {project_type} .gitignore"


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
    """fix_project() no longer creates or rewrites anything under .droid/ (D-529)."""

    def test_creates_no_droid_structure(self, tmp_path):
        """fix_project() leaves a project without .droid/ without one."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()  # Make it look like a git repo

        added = fix_project(project_dir, project_type="python-api", dry_run=False)

        assert not (project_dir / ".droid").exists()
        assert not any(".droid" in item and "block updated" not in item for item in added)

    def test_leaves_an_existing_droid_gitignore_alone(self, tmp_path):
        """An existing .droid/.gitignore is byte-identical after fix_project()."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()
        droid_dir = project_dir / ".droid"
        droid_dir.mkdir()
        (droid_dir / ".gitignore").write_text("# Old content\n*\n")

        _ = fix_project(project_dir, project_type="python-api", dry_run=False)

        assert (droid_dir / ".gitignore").read_text() == "# Old content\n*\n"

    def test_dry_run_reports_no_droid_writes(self, tmp_path):
        """fix_project() dry_run reports no .droid/ creation and writes nothing."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        added = fix_project(project_dir, project_type="python-api", dry_run=True)

        assert not any(".droid/.gitignore" in item for item in added)
        assert not (project_dir / ".droid").exists()


class TestFixProjectRootGitignorePatch:
    """Test fix_project() patches root .gitignore .droid/ block."""

    def test_patches_outdated_root_gitignore(self, tmp_path):
        """fix_project() updates root .gitignore with current _DROID_GITIGNORE_BLOCK."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        # Write .gitignore with old .droid/ entries
        (project_dir / ".gitignore").write_text(
            ".env\n.droid/kilo_usage.jsonl\n.droid/reviews/\n*.log\n"
        )

        added = fix_project(project_dir, project_type="python-api", dry_run=False)

        assert ".gitignore (.droid/ block updated)" in added
        content = (project_dir / ".gitignore").read_text()
        assert ".droid/docs_queue/" in content
        assert ".droid/docs_log/" in content
        assert ".droid/kilo_usage.jsonl" not in content  # retired, so replaced

    def test_appends_when_no_droid_entries(self, tmp_path):
        """fix_project() appends .droid/ block when missing entirely."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        # Write .gitignore with no .droid/ entries
        (project_dir / ".gitignore").write_text(".env\nnode_modules/\n*.log\n")

        added = fix_project(project_dir, project_type="python-api", dry_run=False)

        assert ".gitignore (.droid/ block updated)" in added
        content = (project_dir / ".gitignore").read_text()
        assert ".droid/docs_queue/" in content

    def test_noop_when_gitignore_already_updated(self, tmp_path):
        """fix_project() doesn't modify .gitignore if already up-to-date."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        # Write .gitignore with current block
        (project_dir / ".gitignore").write_text(".env\n" + _DROID_GITIGNORE_BLOCK + "*.log\n")

        added = fix_project(project_dir, project_type="python-api", dry_run=False)

        assert ".gitignore (.droid/ block updated)" not in added

    def test_dry_run_reports_gitignore_patch(self, tmp_path):
        """fix_project() dry_run reports .gitignore patch without writing."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        original_content = ".env\n.droid/old_entry\n*.log\n"
        (project_dir / ".gitignore").write_text(original_content)

        added = fix_project(project_dir, project_type="python-api", dry_run=True)

        assert ".gitignore (.droid/ block updated)" in added
        # Verify file wasn't actually modified
        assert (project_dir / ".gitignore").read_text() == original_content


@requires_fabrik_env
class TestChromeExtensionScaffold:
    """Test chrome-extension scaffold generates dual-artifact structure."""

    def test_creates_extension_directory_structure(self, tmp_path):
        """Verify extension/ is a WXT project (auto-manifest, file-based entrypoints)."""
        create_project(
            name="test-ext",
            project_type="chrome-extension",
            description="Test Extension",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-ext"

        # WXT layout (srcDir='src', file-based entrypoints, public/ for assets)
        assert (project_dir / "extension" / "src" / "entrypoints").is_dir()
        assert (project_dir / "extension" / "public").is_dir()
        assert (project_dir / "extension" / "wxt.config.ts").exists()
        assert (project_dir / "extension" / "package.json").exists()

        # WXT auto-generates the manifest at build — never a hand-written one; @crxjs's
        # vite.config.ts and the old flat src/*.ts stubs are gone.
        assert not (project_dir / "extension" / "manifest.json").exists()
        assert not (project_dir / "extension" / "vite.config.ts").exists()
        assert not (project_dir / "extension" / "src" / "popup.ts").exists()

        # File-based entrypoints
        assert (project_dir / "extension" / "src" / "entrypoints" / "background.ts").exists()
        assert (project_dir / "extension" / "src" / "entrypoints" / "content.tsx").exists()
        assert (project_dir / "extension" / "src" / "entrypoints" / "popup" / "index.html").exists()

    def test_extension_uses_wxt_preact(self, tmp_path):
        """Verify extension uses WXT + Preact, not Vite + CRXJS."""
        import json

        create_project(
            name="test-ext",
            project_type="chrome-extension",
            description="Test Extension",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-ext"

        cfg = (project_dir / "extension" / "wxt.config.ts").read_text()
        assert "@preact/preset-vite" in cfg
        assert "@wxt-dev/i18n/module" in cfg

        pkg = json.loads((project_dir / "extension" / "package.json").read_text())
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        assert "wxt" in deps
        assert "preact" in deps
        assert "wxt build" in pkg["scripts"]["build"]
        assert not any("crxjs" in d for d in deps)
        assert "webpack" not in deps

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
        # The Debian variant comes from the version registry (W-3860ebf6), never a literal.
        assert f"python:3.12-slim-{load_versions()['debian_codename']}" in dockerfile
        assert "PYTHONPATH=/app/server/src" in dockerfile
        assert "uvicorn test_ext.main:app" in dockerfile

        # Verify compose.yaml content
        compose = (project_dir / "compose.yaml").read_text()
        assert "platform: linux/amd64" in compose
        assert "fabrik" in compose  # network renamed from coolify 2026-05-31
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
        assert "pnpm dev" in makefile
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
        assert "extension/.output/" in gitignore  # WXT build output
        assert "extension/.wxt/" in gitignore  # WXT generated dir
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

        # The reduced .droid/ block is present and no retired line is
        for entry in (".droid/docs_queue/", ".droid/docs_log/"):
            assert entry in gitignore, f"{entry} missing in chrome-extension .gitignore"
        for retired in _RETIRED_DROID_GITIGNORE_LINES:
            assert retired not in gitignore, f"{retired} still in chrome-extension .gitignore"

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
    """Test mobile-app scaffold generates the Obytes/expo-router client + bundled FastAPI backend."""

    def test_uses_expo_scripts(self, tmp_path):
        """Verify package.json has Expo SDK 57 scripts (plan-1 Phase A rebase)."""
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

        assert scripts["start"] == "expo start"
        assert scripts["android"] == "expo run:android"
        assert scripts["ios"] == "expo run:ios"
        assert pkg["dependencies"].get("expo", "").startswith("~57"), "expected Expo SDK 57"

    def test_gitignore_keeps_dependencies_and_signing_files_out_of_git(self, tmp_path):
        """`git add .` in a new mobile project must not stage node_modules or a keystore (W-149de516).

        The generated .gitignore carries every rule of templates/mobile-app/.gitignore, so the
        template stays the one list rather than a second hand-kept copy drifting from it.
        """
        create_project(
            name="test-mobile",
            project_type="mobile-app",
            description="Test Mobile App",
            base=tmp_path,
            generate_spec=False,
        )
        rules = set((tmp_path / "test-mobile" / ".gitignore").read_text().splitlines())
        for must in (
            "node_modules/",
            ".env",
            ".env*.local",
            "*.jks",
            "*.p8",
            "*.p12",
            "*.mobileprovision",
        ):
            assert must in rules, must
        template = (MOBILE_APP_TEMPLATE_DIR / ".gitignore").read_text().splitlines()
        missing = [
            ln for ln in template if ln.strip() and not ln.startswith("#") and ln not in rules
        ]
        assert missing == [], missing
        # a set cannot see order: a later `!` line would re-include what an earlier rule ignored
        assert not [ln for ln in rules if ln.startswith("!")]

    def test_node_api_gitignore_carries_its_template_rules(self, tmp_path):
        """node-api once hand-wrote a .gitignore that dropped its template's `.env.local` (W-149de516)."""
        create_project(
            name="test-node",
            project_type="node-api",
            description="Test Node API",
            base=tmp_path,
            generate_spec=False,
        )
        rules = set((tmp_path / "test-node" / ".gitignore").read_text().splitlines())
        template = (NODE_API_TEMPLATE_DIR / ".gitignore").read_text().splitlines()
        missing = [
            ln for ln in template if ln.strip() and not ln.startswith("#") and ln not in rules
        ]
        assert missing == [], missing
        assert ".env.local" in rules

    def test_scaffolds_expo_config_files(self, tmp_path):
        """The Expo/expo-router foundation must ship, and the app identity must be
        substituted off the Obytes defaults (else every scaffolded app collides on
        `com.obytes` / `ObytesApp`)."""
        create_project(
            name="test-mobile",
            project_type="mobile-app",
            description="Test Mobile App",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-mobile"
        for f in (
            "app.config.ts",
            "eas.json",
            "babel.config.js",
            "metro.config.js",
            "tsconfig.json",
            "env.ts",
        ):
            assert (project_dir / f).exists(), f"missing Expo config file: {f}"

        # Identity substituted (slug "test-mobile" -> "testmobile").
        assert "slug: 'testmobile'" in (project_dir / "app.config.ts").read_text(), (
            "app slug not substituted"
        )
        env_ts = (project_dir / "env.ts").read_text()
        assert "com.testmobile" in env_ts, "bundle id not substituted"
        assert "com.obytes" not in env_ts, "Obytes bundle id leaked into the scaffold"

        env = (project_dir / ".env.example").read_text()
        assert "EXPO_PUBLIC_" in env, ".env.example missing EXPO_PUBLIC_* vars"

    def test_has_full_react_native_deps(self, tmp_path):
        """Verify package.json has the expo-router client deps (no @react-navigation)."""
        import json

        create_project(
            name="test-mobile",
            project_type="mobile-app",
            description="Test Mobile App",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-mobile"
        deps = json.loads((project_dir / "package.json").read_text()).get("dependencies", {})

        assert "react-native" in deps, "Missing react-native dep"
        assert "react" in deps, "Missing react dep"
        assert "expo-router" in deps, "Missing expo-router (the routing entry)"
        assert not any(k.startswith("@react-navigation") for k in deps), (
            "expo-router template must not carry @react-navigation"
        )

    def test_creates_router_tree(self, tmp_path):
        """Verify the expo-router src/app/ tree is copied (replaces the old navigation/ tree)."""
        create_project(
            name="test-mobile",
            project_type="mobile-app",
            description="Test Mobile App",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-mobile"
        assert (project_dir / "src" / "app" / "_layout.tsx").exists(), (
            "src/app/_layout.tsx not created"
        )
        assert (project_dir / "src" / "app" / "(app)" / "_layout.tsx").exists(), (
            "src/app/(app)/_layout.tsx not created"
        )

    def test_creates_features_tree(self, tmp_path):
        """Verify src/features/ tree is copied from the Obytes template."""
        create_project(
            name="test-mobile",
            project_type="mobile-app",
            description="Test Mobile App",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-mobile"
        assert (project_dir / "src" / "features" / "auth").is_dir(), "src/features/auth missing"
        assert (project_dir / "src" / "features" / "settings").is_dir(), (
            "src/features/settings missing"
        )

    def test_ships_client_seams(self, tmp_path):
        """The Phase-A seams ship + JWTs use expo-secure-store, never MMKV."""
        create_project(
            name="test-mobile",
            project_type="mobile-app",
            description="Test Mobile App",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-mobile"
        for seam in ("consent", "offline", "update", "auth"):
            assert (project_dir / "src" / "lib" / seam).exists(), f"missing seam lib/{seam}"
        auth_utils = (project_dir / "src" / "lib" / "auth" / "utils.tsx").read_text()
        assert "expo-secure-store" in auth_utils, "auth token must use expo-secure-store"
        assert "@/lib/storage" not in auth_utils, "JWT must not fall back to MMKV storage"

    def test_emits_backend_dockerfile(self, tmp_path):
        """mobile-app now ships a FastAPI backend that DEPLOYS — Dockerfile + compose +
        server/ (reverses the old ``test_no_dockerfile``: plan-1 Phase C bundled backend)."""
        create_project(
            name="test-mobile",
            project_type="mobile-app",
            description="Test Mobile App",
            base=tmp_path,
        )

        project_dir = tmp_path / "test-mobile"
        dockerfile = project_dir / "Dockerfile"
        assert dockerfile.exists(), "mobile-app must emit a backend Dockerfile"
        df = dockerfile.read_text()
        assert "python:" in df, "Dockerfile is not a Python/FastAPI image"
        assert "8000" in df, "backend must expose port 8000"
        assert "app.main:app" in df, "uvicorn entrypoint must be app.main:app"

        assert (project_dir / "compose.yaml").exists(), "missing compose.yaml"
        assert (project_dir / "server" / "src" / "app" / "main.py").exists(), (
            "backend code not shipped"
        )
        assert (project_dir / "server" / "src" / "mobile_config" / "__init__.py").exists(), (
            "vendored mobile_config not shipped"
        )
        assert (project_dir / "requirements.txt").exists(), "backend requirements.txt not shipped"

        # .dockerignore excludes the RN client (root-anchored) so the image ships server/ only.
        dockerignore = (project_dir / ".dockerignore").read_text()
        assert "/src/" in dockerignore, ".dockerignore must root-anchor-exclude the RN client src/"


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

    def _scaffold(self, tmp_path):
        create_project(
            name="test-desktop",
            project_type="desktop-app",
            description="Test Desktop App",
            base=tmp_path,
        )
        return tmp_path / "test-desktop"

    def test_ships_a_preload_bridge(self, tmp_path):
        """W-bfaa9e9b: main.js promised a preload + contextBridge bridge and shipped none."""
        project_dir = self._scaffold(tmp_path)
        preload = project_dir / "electron" / "preload.js"
        assert preload.exists(), "electron/preload.js not shipped"
        text = preload.read_text()
        code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("//"))
        # the documented surface, and nothing else: window.api.versions, no IPC channel (a
        # handler would owe a sender-origin check, 72-desktop.md)
        assert re.search(r"contextBridge\.exposeInMainWorld\(\s*'api'\s*,\s*\{\s*versions:", code)
        assert code.count("exposeInMainWorld(") == 1
        assert "ipcRenderer" not in code, "the preload opens an IPC channel"
        main = (project_dir / "electron" / "main.js").read_text()
        assert "preload: path.join(__dirname, 'preload.js')" in main
        assert "require('path')" in main or 'require("path")' in main
        # the required-files table knows main.js now depends on it
        assert "electron/preload.js" in TYPE_REQUIRED_FILES["desktop-app"]

    def test_update_check_is_packaged_only(self, tmp_path):
        """An unpackaged run has no app-update.yml: the check must be skipped there and never reject unhandled."""
        main = (self._scaffold(tmp_path) / "electron" / "main.js").read_text()
        code = "\n".join(ln for ln in main.splitlines() if not ln.lstrip().startswith("//"))
        assert code.count("checkForUpdates") == 1, "exactly one update check, the guarded one"
        assert re.search(
            r"if \(app\.isPackaged\) \{\s*autoUpdater\.checkForUpdatesAndNotify\(\)\.catch\(\(err\) => \{",
            code,
        ), "the update check is not packaged-only, or its rejection is unhandled"
        assert "from your VPS" not in main

    def test_update_feed_comes_from_env(self, tmp_path):
        import json

        project_dir = self._scaffold(tmp_path)
        publish = json.loads((project_dir / "package.json").read_text())["build"]["publish"]
        assert publish == [{"provider": "generic", "url": "${env.UPDATE_FEED_URL}/${os}"}]
        env_lines = (project_dir / ".env.example").read_text().splitlines()
        # one key, shipped EMPTY (a real host is the project's to set, never a template default)
        assert [ln for ln in env_lines if ln.startswith("UPDATE_FEED_URL")] == ["UPDATE_FEED_URL="]

    def test_template_has_no_companion_container(self):
        """The desktop app is an installer, not a VPS service (spec_loader.Shape, the B3 regression)."""
        import yaml

        from fabrik.scaffold import DESKTOP_APP_TEMPLATE_DIR
        from fabrik.spec_loader import Shape

        for name in ("Dockerfile.j2", "compose.yaml.j2"):
            assert not (DESKTOP_APP_TEMPLATE_DIR / name).exists(), f"{name} is back"
        shape = yaml.safe_load((DESKTOP_APP_TEMPLATE_DIR / "defaults.yaml").read_text())["shape"]
        assert shape["kind"] == "static"
        assert not any(v for k, v in shape.items() if k != "kind")
        assert "desktop-app         static" in (Shape.__doc__ or "")


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
        assert "serve" not in scripts  # no Node runtime in production — nginx serves the build

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

        # B38: the OpenAPI plugin/theme are intentionally NOT wired into the
        # default config (docusaurus-plugin-openapi-docs 4.3.x fails the build
        # under @docusaurus/core 3.10.x). A bare site builds out-of-the-box;
        # users opt back in. A placeholder openapi.yaml is still emitted
        # (see test_creates_openapi_yaml).
        # The docItemComponent (@theme/ApiItem) is the active OpenAPI wiring —
        # only present when the plugin is enabled. (The plugin *name* still
        # appears in the B38 explanatory comment, so assert on this instead.)
        assert "@theme/ApiItem" not in content, (
            "B38: the OpenAPI docItemComponent must stay out of the default config"
        )
        assert "guideSidebar" in content, "Config missing guideSidebar navbar item"

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
        # B38: apiSidebar (and its docs/api/sidebar.js require) are dropped from
        # the default sidebars — they crash `npm run build` until OpenAPI docs
        # are generated. Re-added when a project opts into the OpenAPI plugin.
        assert "apiSidebar" not in content, "B38: apiSidebar must stay out of default sidebars"

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

        _ = fix_project(project_dir, project_type="python-api", dry_run=False)

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


class TestCreateProjectRejectsUnknownKeywords:
    """W-202f7fc6: `create_project(**kwargs)` swallowed a mistyped `base_dir=` (the keyword is
    `base=`), so the default base `/opt` was used and four projects were scaffolded there."""

    def test_a_mistyped_keyword_raises_before_anything_is_written(self, tmp_path):
        from fabrik.scaffold import create_project

        base = tmp_path / "base"
        base.mkdir()
        with pytest.raises(TypeError, match="base_dir"):
            create_project(name="typo-probe", description="d", base=base, base_dir=base)

        assert list(base.iterdir()) == [], "a refused call must write nothing"

    def test_use_database_is_still_accepted(self, tmp_path):
        from fabrik.scaffold import create_project

        project = create_project(
            name="db-probe", description="d", base=tmp_path, generate_spec=False, use_database=True
        )

        assert (project / ".env.local").exists(), (
            "use_database=True must still reach the scaffolder"
        )
        # the CI replica (no ci.yml, by operator directive) starts Postgres only when told to
        ci_local = (project / "scripts" / "ci_local.sh").read_text()
        assert 'PG_IMAGE="' in ci_local, "use_database=True must reach the CI replica"

    def test_no_database_means_no_ci_postgres(self, tmp_path):
        from fabrik.scaffold import create_project

        project = create_project(
            name="nodb-probe", description="d", base=tmp_path, generate_spec=False
        )

        assert 'PG_IMAGE="' not in (project / "scripts" / "ci_local.sh").read_text()

    def test_a_truthy_use_database_reaches_the_ci_writer_as_a_bool(self, tmp_path, monkeypatch):
        """The removed `bool(kwargs.get(...))` normalised the flag; the explicit parameter keeps it."""
        import fabrik.scaffold as scaffold

        seen = []
        monkeypatch.setattr(
            scaffold, "_write_ci_files", lambda _dir, *, needs_database: seen.append(needs_database)
        )
        scaffold.create_project(
            name="truthy-probe", description="d", base=tmp_path, generate_spec=False, use_database=1
        )

        assert seen == [True] and type(seen[0]) is bool


# --- plan-1 2026-10-03: the scaffold and `fabrik fix` stop emitting the retired Kilo/Traycer
# surface (spec docs/superpowers/specs/2026-10-03-scaffold-retired-agent-surface-design.md, D-529).

_RETIRED_PROJECT_FILES = (
    ".windsurfrules",
    "AGENTS-compact.md",
    "opencode.json",
    "scripts/kilo_47_agents_final.json",
)
_REDUCED_DROID_LINES = {".factory/consultations/", ".droid/docs_queue/", ".droid/docs_log/"}


def _fake_hub(root: Path, *, windsurfrules: bool = True, opencode: bool = True) -> Path:
    """A hub root carrying every source the scaffold or fix could copy (outside the project)."""
    (root / ".windsurf" / "rules").mkdir(parents=True)
    (root / ".windsurf" / "rules" / "10-python.md").write_text("# rules\n")
    (root / ".windsurf" / "workflows").mkdir(parents=True)
    (root / ".windsurf" / "workflows" / "test.md").write_text("# wf\n")
    (root / "AGENTS.md").write_text("# AGENTS\n")
    (root / "AGENTS-compact.md").write_text("# AGENTS-compact\n")
    (root / "docs" / "reference" / "kilo").mkdir(parents=True)
    (root / "docs" / "reference" / "kilo" / "x.md").write_text("# kilo\n")
    (root / "scripts").mkdir()
    (root / "scripts" / "kilo_47_agents_final.json").write_text('{"hub": true}\n')
    (root / ".pre-commit-config.yaml").write_text("repos: []\n")
    if windsurfrules:
        (root / ".windsurfrules").write_text("# rules\n")
    if opencode:
        (root / "opencode.json").write_text("{}\n")
    return root


def _hub_patches(root: Path):
    """Point every module-level hub path the scaffold and fix read at the fake root."""
    from contextlib import ExitStack
    from unittest.mock import patch

    import fabrik.scaffold as scaffold

    stack = ExitStack()
    stack.enter_context(patch.object(scaffold, "FABRIK_ROOT", root))
    stack.enter_context(patch.object(scaffold, "TEMPLATE_DIR", root / "templates" / "scaffold"))
    stack.enter_context(patch.object(scaffold, "FABRIK_AGENTS_MD", root / "AGENTS.md"))
    stack.enter_context(
        patch.object(scaffold, "FABRIK_WINDSURF_HOOKS", root / ".windsurf" / "hooks.json")
    )
    stack.enter_context(patch("subprocess.run"))
    return stack


def _droid_lines(gitignore: str) -> set[str]:
    return {
        line.strip()
        for line in gitignore.splitlines()
        if line.strip().startswith((".droid/", ".factory/"))
    }


def _old_project(root: Path) -> Path:
    """A project as the old scaffold left it: both markers and the old .droid/.gitignore."""
    (root / ".git").mkdir(parents=True)
    (root / ".droid" / "review-context").mkdir(parents=True)
    (root / ".droid" / "review-context" / ".gitkeep").write_text("")
    (root / ".droid" / "traycer-reports").mkdir()
    (root / ".droid" / "traycer-reports" / ".gitignore").write_text("*.md\n!.gitignore\n")
    (root / ".droid" / ".gitignore").write_text("# OLD\n*\n!review-context/\n")
    return root


class TestRetiredSurfaceScaffold:
    """A1-A2: `_scaffold_shared` (every create-time copy) emits no retired artifact."""

    def test_a1_scaffold_emits_no_retired_surface(self, tmp_path):
        import fabrik.scaffold as scaffold

        hub = _fake_hub(tmp_path / "hub")
        proj = tmp_path / "proj"
        proj.mkdir()
        with _hub_patches(hub):
            scaffold._scaffold_shared(proj, "svc", "Test", "2026-10-03", 8099, "python-api")

        assert not (proj / ".droid").exists()
        for rel in _RETIRED_PROJECT_FILES:
            assert not (proj / rel).exists(), rel
        assert (proj / "docs" / "reference" / "kilo" / "x.md").exists()
        gitignore = (proj / ".gitignore").read_text()
        assert _droid_lines(gitignore) == _REDUCED_DROID_LINES
        assert "traycer" not in gitignore

    def test_a2_scaffold_needs_no_hub_windsurfrules_or_opencode(self, tmp_path):
        import fabrik.scaffold as scaffold

        hub = _fake_hub(tmp_path / "hub", windsurfrules=False, opencode=False)
        proj = tmp_path / "proj"
        proj.mkdir()
        with _hub_patches(hub):
            scaffold._scaffold_shared(proj, "svc", "Test", "2026-10-03", 8099, "python-api")

        assert (proj / ".gitignore").exists()


class TestRetiredSurfaceFix:
    """A3-A7: `fix_project` removes only the scaffold's dead markers and writes none of the rest."""

    def _fix(self, hub: Path, proj: Path, dry_run: bool = False) -> list[str]:
        with _hub_patches(hub):
            return fix_project(proj, project_type="python-api", dry_run=dry_run)

    def test_a3_fix_removes_markers_and_kilo_copy_and_creates_no_droid(self, tmp_path):
        hub = _fake_hub(tmp_path / "hub")
        old = _old_project(tmp_path / "old")
        (old / "scripts").mkdir()
        (old / "scripts" / "kilo_47_agents_final.json").write_text("{}\n")
        fresh = tmp_path / "fresh"
        (fresh / ".git").mkdir(parents=True)

        added = self._fix(hub, old)
        self._fix(hub, fresh)

        for gone in (
            ".droid/review-context",
            ".droid/traycer-reports",
            "scripts/kilo_47_agents_final.json",
        ):
            assert not (old / gone).exists(), gone
        for entry in (
            "removed .droid/review-context/.gitkeep",
            "removed .droid/review-context/ (empty)",
            "removed .droid/traycer-reports/.gitignore",
            "removed .droid/traycer-reports/ (empty)",
            "removed scripts/kilo_47_agents_final.json",
        ):
            assert entry in added, entry
        assert (old / ".droid" / ".gitignore").read_text() == "# OLD\n*\n!review-context/\n"
        assert not (fresh / ".droid").exists()

    def test_a4_fix_guard_holds_on_every_odd_tree(self, tmp_path):
        hub = _fake_hub(tmp_path / "hub")

        nonempty = _old_project(tmp_path / "nonempty")
        (nonempty / ".droid" / "review-context" / "notes.md").write_text("mine")
        assert "kept .droid/review-context/ (1 other entries)" in self._fix(hub, nonempty)
        assert (nonempty / ".droid" / "review-context" / "notes.md").read_text() == "mine"

        target = tmp_path / "target"
        target.mkdir()
        (target / ".gitignore").write_text("t")
        symdir = tmp_path / "symdir"
        (symdir / ".git").mkdir(parents=True)
        (symdir / ".droid").mkdir()
        os.symlink(target, symdir / ".droid" / "traycer-reports")
        assert "skipped .droid/traycer-reports/ (symlink)" in self._fix(hub, symdir)
        assert (target / ".gitignore").read_text() == "t"

        for name, link_to in (("symdroid", tmp_path / "droid-target"), ("dangdroid", None)):
            proj = tmp_path / name
            (proj / ".git").mkdir(parents=True)
            proj.joinpath(".gitignore").write_text(".env\n.droid/kilo_usage.jsonl\n")
            if link_to is not None:
                link_to.mkdir()
                os.symlink(link_to, proj / ".droid")
            else:
                os.symlink(tmp_path / "nowhere", proj / ".droid")
            added = self._fix(hub, proj)
            assert "skipped .droid/ (symlink)" in added
            if link_to is not None:
                assert list(link_to.iterdir()) == []
            assert ".droid/kilo_usage.jsonl" not in proj.joinpath(".gitignore").read_text()

        dirmarker = tmp_path / "dirmarker"
        (dirmarker / ".git").mkdir(parents=True)
        (dirmarker / ".droid" / "review-context" / ".gitkeep").mkdir(parents=True)
        assert "kept .droid/review-context/ (1 other entries)" in self._fix(hub, dirmarker)
        assert (dirmarker / ".droid" / "review-context" / ".gitkeep").is_dir()

        dangmarker = tmp_path / "dangmarker"
        (dangmarker / ".git").mkdir(parents=True)
        (dangmarker / ".droid" / "review-context").mkdir(parents=True)
        os.symlink(tmp_path / "gone", dangmarker / ".droid" / "review-context" / ".gitkeep")
        assert "kept .droid/review-context/ (1 other entries)" in self._fix(hub, dangmarker)

        filedroid = tmp_path / "filedroid"
        (filedroid / ".git").mkdir(parents=True)
        (filedroid / ".droid").write_text("f")
        assert "kept .droid (not a directory)" in self._fix(hub, filedroid)

        filerc = tmp_path / "filerc"
        (filerc / ".git").mkdir(parents=True)
        (filerc / ".droid").mkdir()
        (filerc / ".droid" / "review-context").write_text("f")
        assert "kept .droid/review-context (not a directory)" in self._fix(hub, filerc)

        if os.geteuid() != 0:
            unread = _old_project(tmp_path / "unread")
            os.chmod(unread / ".droid" / "review-context", 0)
            try:
                added = self._fix(hub, unread)
            finally:
                os.chmod(unread / ".droid" / "review-context", 0o755)
            assert any(e.startswith("could not remove .droid/review-context") for e in added)

        kilo_target = tmp_path / "kilo-target"
        kilo_target.mkdir()
        (kilo_target / "kilo_47_agents_final.json").write_text("hub copy")
        symscripts = tmp_path / "symscripts"
        (symscripts / ".git").mkdir(parents=True)
        os.symlink(kilo_target, symscripts / "scripts")
        added = self._fix(hub, symscripts)
        assert "skipped scripts/kilo_47_agents_final.json (scripts/ is a symlink)" in added
        assert (kilo_target / "kilo_47_agents_final.json").read_text() == "hub copy"

        symkilo = tmp_path / "symkilo"
        (symkilo / ".git").mkdir(parents=True)
        (symkilo / "scripts").mkdir()
        os.symlink(
            kilo_target / "kilo_47_agents_final.json",
            symkilo / "scripts" / "kilo_47_agents_final.json",
        )
        assert not any("kilo_47" in e for e in self._fix(hub, symkilo))
        assert (kilo_target / "kilo_47_agents_final.json").read_text() == "hub copy"

        from unittest.mock import patch

        refused = _old_project(tmp_path / "refused")
        (refused / "scripts").mkdir()
        (refused / "scripts" / "kilo_47_agents_final.json").write_text("{}")
        rmdirs: list[Path] = []
        with (
            patch.object(Path, "unlink", side_effect=PermissionError(13, "Permission denied")),
            patch.object(Path, "rmdir", lambda self: rmdirs.append(self)),
        ):
            added = self._fix(hub, refused)
        assert "could not remove .droid/review-context/.gitkeep: Permission denied" in added
        assert "could not remove scripts/kilo_47_agents_final.json: Permission denied" in added
        assert rmdirs == []

    def test_a4c_each_guard_of_the_marker_helper_holds_on_its_own(self, tmp_path):
        """One tree per guard the A4 trees never reach on their own (Finish review A-O1..A-O4)."""
        hub = _fake_hub(tmp_path / "hub")

        user_file = tmp_path / "users-notes.txt"
        user_file.write_text("keep me")
        livemarker = tmp_path / "livemarker"
        (livemarker / ".git").mkdir(parents=True)
        (livemarker / ".droid" / "review-context").mkdir(parents=True)
        os.symlink(user_file, livemarker / ".droid" / "review-context" / ".gitkeep")
        added = self._fix(hub, livemarker)
        assert "removed .droid/review-context/.gitkeep" not in added
        assert "kept .droid/review-context/ (1 other entries)" in added
        assert (livemarker / ".droid" / "review-context" / ".gitkeep").is_symlink()
        assert user_file.read_text() == "keep me"

        dangdir = tmp_path / "dangdir"
        (dangdir / ".git").mkdir(parents=True)
        (dangdir / ".droid").mkdir()
        os.symlink(tmp_path / "no-such-dir", dangdir / ".droid" / "traycer-reports")
        assert "skipped .droid/traycer-reports/ (symlink)" in self._fix(hub, dangdir)
        assert (dangdir / ".droid" / "traycer-reports").is_symlink()

        empty_target = tmp_path / "scripts-target"
        empty_target.mkdir()
        nokilo = tmp_path / "nokilo"
        (nokilo / ".git").mkdir(parents=True)
        os.symlink(empty_target, nokilo / "scripts")
        assert not any("kilo_47" in e for e in self._fix(hub, nokilo))

        three = _old_project(tmp_path / "three")
        for name in ("a.md", "b.md", "c.md"):
            (three / ".droid" / "review-context" / name).write_text(name)
        assert "kept .droid/review-context/ (3 other entries)" in self._fix(hub, three)

    def test_a4b_a_refused_droid_probe_is_reported_never_raised(self, tmp_path):
        """An OSError while probing `.droid` itself is a `could not remove` entry, not a traceback."""
        from unittest.mock import patch

        import fabrik.scaffold as scaffold

        proj = _old_project(tmp_path / "proj")
        real = Path.is_symlink

        def refuse(self):
            if self.name == ".droid":
                raise PermissionError(13, "Permission denied")
            return real(self)

        with patch.object(Path, "is_symlink", refuse):
            entries = scaffold._retire_droid_and_kilo_config(proj, dry_run=False)
        assert entries == ["could not remove .droid: Permission denied"]
        assert (proj / ".droid" / "review-context" / ".gitkeep").exists()

    def test_a5_fix_never_writes_or_deletes_the_synced_files(self, tmp_path):
        hub = _fake_hub(tmp_path / "hub")
        own = tmp_path / "own"
        (own / ".git").mkdir(parents=True)
        for rel in (".windsurfrules", "AGENTS-compact.md", "opencode.json"):
            (own / rel).write_text(f"project's own {rel}\n")
        bare = tmp_path / "bare"
        (bare / ".git").mkdir(parents=True)

        added = self._fix(hub, own)
        self._fix(hub, bare)

        for rel in (".windsurfrules", "AGENTS-compact.md", "opencode.json"):
            assert (own / rel).read_text() == f"project's own {rel}\n"
            assert not any(rel in e for e in added), rel
        for rel in _RETIRED_PROJECT_FILES:
            assert not (bare / rel).exists(), rel

    def test_a6_dry_run_reports_what_live_does_and_changes_nothing(self, tmp_path):
        hub = _fake_hub(tmp_path / "hub")
        for name, notes in (("plain", False), ("nonempty", True)):
            dry_proj = _old_project(tmp_path / f"dry-{name}")
            live_proj = _old_project(tmp_path / f"live-{name}")
            for p in (dry_proj, live_proj):
                (p / "scripts").mkdir()
                (p / "scripts" / "kilo_47_agents_final.json").write_text("{}")
                if notes:
                    (p / ".droid" / "review-context" / "notes.md").write_text("mine")
            before = sorted(str(p.relative_to(dry_proj)) for p in dry_proj.rglob("*"))

            verbs = ("removed ", "kept ", "skipped ", "could not remove ")
            dry = [e for e in self._fix(hub, dry_proj, dry_run=True) if e.startswith(verbs)]
            live = [e for e in self._fix(hub, live_proj) if e.startswith(verbs)]
            assert "removed scripts/kilo_47_agents_final.json" in live

            assert dry == live
            assert sorted(str(p.relative_to(dry_proj)) for p in dry_proj.rglob("*")) == before

    def test_a7_gitignore_patch_keeps_user_droid_lines(self, tmp_path):
        hub = _fake_hub(tmp_path / "hub")
        proj = tmp_path / "proj"
        (proj / ".git").mkdir(parents=True)
        old_block = (
            ".factory/consultations/\n.droid/kilo_usage.jsonl\n.droid/reviews/\n"
            ".droid/kilo_models_cache.json\n.droid/.kilo_cache_last_refresh\n"
            ".droid/docs_queue/\n.droid/docs_log/\n.droid/traycer-reports/*.md\n"
        )
        (proj / ".gitignore").write_text(".env\n" + old_block + ".droid/secrets.json\n*.log\n")

        first = self._fix(hub, proj)
        content = (proj / ".gitignore").read_text()
        second = self._fix(hub, proj)

        assert ".gitignore (.droid/ block updated)" in first
        assert _droid_lines(content) == _REDUCED_DROID_LINES | {".droid/secrets.json"}
        lines = content.splitlines()
        assert lines.index(".env") < lines.index(".droid/secrets.json") < lines.index("*.log")
        assert ".gitignore (.droid/ block updated)" not in second


class TestFixCommandRendering:
    """A8: `fabrik fix` prints removals as removals and notes as notes, never as "Added"."""

    def _run(self, tmp_path, entries, *flags):
        from unittest.mock import patch

        from click.testing import CliRunner

        from fabrik.cli import cli

        with patch("fabrik.scaffold.fix_project", return_value=entries):
            return CliRunner().invoke(cli, ["fix", str(tmp_path), *flags])

    def test_a8_removals_notes_and_failures_render_by_kind(self, tmp_path):
        mixed = self._run(
            tmp_path,
            [
                "README.md",
                "removed .droid/review-context/.gitkeep",
                "kept .droid/review-context/ (1 other entries)",
            ],
        )
        assert "Added: README.md" in mixed.output
        assert "Removed: .droid/review-context/.gitkeep" in mixed.output
        assert "Added: removed" not in mixed.output and "Added: kept" not in mixed.output
        assert "Added 1 files" in mixed.output
        assert "Removed 1 retired paths" in mixed.output

        dry = self._run(
            tmp_path,
            ["removed .droid/review-context/.gitkeep", "removed .droid/review-context/ (empty)"],
            "--dry-run",
        )
        assert "Would remove: .droid/review-context/.gitkeep" in dry.output
        assert "Run without --dry-run to remove 2 retired paths" in dry.output
        assert "Removed:" not in dry.output

        partial = self._run(
            tmp_path,
            [
                "removed .droid/review-context/.gitkeep",
                "skipped .droid/traycer-reports/ (symlink)",
                "could not remove .droid/review-context/: Permission denied",
            ],
        )
        assert "Removed: .droid/review-context/.gitkeep" in partial.output
        assert "skipped .droid/traycer-reports/ (symlink)" in partial.output
        assert "Added:" not in partial.output and "Added " not in partial.output
        assert "project structure is complete" not in partial.output
        assert partial.exit_code == 0

        notes_only = self._run(tmp_path, ["kept .droid/review-context/ (1 other entries)"])
        assert "No missing files - project structure is complete!" in notes_only.output
        assert notes_only.exit_code == 0

        failure = self._run(
            tmp_path, ["could not remove .droid/review-context/.gitkeep: Permission denied"]
        )
        assert "could not remove .droid/review-context/.gitkeep" in failure.output
        assert "project structure is complete" not in failure.output
        assert failure.exit_code == 0
