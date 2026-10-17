"""Tests for scaffold.py gitignore and .droid/ structure."""

import os
import re
import shutil
import subprocess
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

        # pytest reaches the dev venv through requirements-dev.txt, which `make install` installs; the
        # image's requirements.txt carries runtime deps only (W-4d6a37c8)
        dev = (project_dir / "requirements-dev.txt").read_text()
        assert re.search(r"^-r requirements\.txt$", dev, re.M), dev
        assert re.search(r"^pytest>=", dev, re.M) and re.search(r"^pytest-timeout>=", dev, re.M), (
            dev
        )
        assert "pytest" not in (project_dir / "requirements.txt").read_text()
        assert (
            ".venv/bin/pip install -r requirements-dev.txt"
            in (project_dir / "Makefile").read_text()
        )

        # Verify Makefile test target has PYTHONPATH
        makefile = (project_dir / "Makefile").read_text()
        assert "PYTHONPATH=server/src" in makefile, "PYTHONPATH not set in Makefile test target"
        assert ".venv/bin/pytest" in makefile, "pytest not invoked via .venv in Makefile"

        # Verify test file exists with correct import
        test_health = (project_dir / "tests" / "test_health.py").read_text()
        assert "from test_ext.main import app" in test_health, "test imports package incorrectly"
        assert "TestClient" in test_health, "TestClient not imported in tests"


def _chrome_ext_project(base: Path) -> Path:
    create_project(
        name="test-ext",
        project_type="chrome-extension",
        description="Test Extension",
        base=base,
    )
    return base / "test-ext"


def _ext_id_from_pub(pub_b64: str) -> str:
    """Chrome's derivation: SHA-256 of the decoded key, first 16 bytes, hex mapped to a-p."""
    import base64
    import hashlib

    digest = hashlib.sha256(base64.b64decode(pub_b64)).hexdigest()[:32]
    return "".join(chr(ord("a") + int(c, 16)) for c in digest)


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t.invalid",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _make_target(makefile: str, target: str) -> str:
    """The recipe of `target`: its rule line up to the next rule line."""
    m = re.search(rf"^{re.escape(target)}:.*?(?=^[A-Za-z0-9_.-]+:|\Z)", makefile, re.M | re.S)
    assert m, f"{target} target missing"
    return m.group(0)


def _node_major_minor() -> tuple[int, int]:
    if shutil.which("node") is None:
        return (0, 0)
    out = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=30).stdout
    m = re.match(r"v(\d+)\.(\d+)", out.strip())
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


# 22.6 is the first node with --experimental-strip-types (the .ts rules) and has util.parseEnv
needs_node = pytest.mark.skipif(_node_major_minor() < (22, 6), reason="needs node >= 22.6")


def _node_json(cwd: Path, program: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run an ES-module `program` under node (type stripping on, so a .ts import works)."""
    return subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            "--no-warnings",
            "--input-type=module",
            "-e",
            program,
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


def _committed_release_project(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    """A scaffold with a key, the given extension files, and everything committed."""
    project = _chrome_ext_project(tmp_path)
    ext = project / "extension"
    keygen = subprocess.run(
        ["node", "scripts/keygen.mjs"], cwd=ext, capture_output=True, timeout=60
    )
    assert keygen.returncode == 0, keygen.stderr
    for name, body in (files or {}).items():
        (ext / name).write_text(body)
    _git(project, "add", "-A")
    _git(
        project,
        "add",
        "-f",
        "extension/extension-key.pub",
        *[f"extension/{n}" for n in files or {}],
    )
    assert _git(project, "commit", "-qm", "scaffold").returncode == 0
    return project


def _release_check(
    project: Path, env_url: str | None = None, extra_env: dict | None = None, *args: str
) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("VITE_PUBLIC_API_URL", "STORE_BUILD")}
    if env_url is not None:
        env["VITE_PUBLIC_API_URL"] = env_url
    env.update(extra_env or {})
    return subprocess.run(
        ["node", "scripts/release-check.mjs", *args],
        cwd=project / "extension",
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


@requires_fabrik_env
class TestChromeExtensionReleaseKit:
    """W-e2af3303: the developer-mode release kit the chrome-extension scaffold emits."""

    @pytest.fixture(scope="class")
    def project(self, tmp_path_factory) -> Path:
        return _chrome_ext_project(tmp_path_factory.mktemp("cx"))

    def test_a0_keygen_script_and_package_script(self, project):
        """A0: the keygen script is emitted and `pnpm keygen` runs it."""
        import json

        assert (project / "extension" / "scripts" / "keygen.mjs").is_file()
        scripts = json.loads((project / "extension" / "package.json").read_text())["scripts"]
        assert scripts.get("keygen") == "node scripts/keygen.mjs"

    @needs_node
    def test_a1_keygen_writes_a_private_key_and_a_pub_with_the_chrome_id(self, tmp_path):
        """A1: a fresh key — PEM 0600 under .keys/, a 392-char .pub, the derived ID, the backup warning."""
        ext = _chrome_ext_project(tmp_path) / "extension"
        r = subprocess.run(
            ["node", "scripts/keygen.mjs"], cwd=ext, capture_output=True, text=True, timeout=60
        )
        assert r.returncode == 0, r.stderr
        pem = ext / ".keys" / "extension-key.pem"
        assert pem.is_file() and (pem.stat().st_mode & 0o777) == 0o600
        assert (pem.parent.stat().st_mode & 0o777) == 0o700
        assert "PRIVATE KEY" in pem.read_text()
        pub = (ext / "extension-key.pub").read_text().strip()
        assert len(pub) == 392 and "\n" not in pub
        ext_id = _ext_id_from_pub(pub)
        assert f"extension id: {ext_id}" in r.stdout
        assert f"EXTENSION_ID={ext_id}" in r.stdout
        assert "back up" in r.stdout.lower() and ".keys/extension-key.pem" in r.stdout

    @needs_node
    def test_a2_keygen_never_overwrites_an_existing_key(self, tmp_path):
        """A2: a second run changes no byte and prints the same ID."""
        ext = _chrome_ext_project(tmp_path) / "extension"
        first = subprocess.run(
            ["node", "scripts/keygen.mjs"], cwd=ext, capture_output=True, text=True, timeout=60
        )
        pem, pub = ext / ".keys" / "extension-key.pem", ext / "extension-key.pub"
        before = (pem.read_bytes(), pub.read_bytes())
        second = subprocess.run(
            ["node", "scripts/keygen.mjs"], cwd=ext, capture_output=True, text=True, timeout=60
        )
        assert second.returncode == 0, second.stderr
        assert (pem.read_bytes(), pub.read_bytes()) == before
        ext_id = _ext_id_from_pub(pub.read_text().strip())
        assert f"EXTENSION_ID={ext_id}" in first.stdout
        assert f"EXTENSION_ID={ext_id}" in second.stdout

    @needs_node
    def test_a2b_keygen_with_a_pub_but_no_pem_warns_and_writes_nothing(self, tmp_path):
        """A2 edge: a cloned repo has the .pub but not the private key — ID printed, warning, no new key."""
        ext = _chrome_ext_project(tmp_path) / "extension"
        subprocess.run(["node", "scripts/keygen.mjs"], cwd=ext, capture_output=True, timeout=60)
        (ext / ".keys" / "extension-key.pem").unlink()
        pub_before = (ext / "extension-key.pub").read_bytes()
        r = subprocess.run(
            ["node", "scripts/keygen.mjs"], cwd=ext, capture_output=True, text=True, timeout=60
        )
        assert r.returncode == 0
        assert not (ext / ".keys" / "extension-key.pem").exists()
        assert (ext / "extension-key.pub").read_bytes() == pub_before
        assert "missing" in (r.stdout + r.stderr).lower()

    @needs_node
    @pytest.mark.parametrize("garbage", ["", "A" * 120])
    def test_a2d_keygen_refuses_a_pub_that_is_not_a_key(self, tmp_path, garbage):
        """A2 edge (review round 2): an empty or garbage .pub prints no ID — an operator would copy
        a wrong EXTENSION_ID into the backend."""
        ext = _chrome_ext_project(tmp_path) / "extension"
        (ext / "extension-key.pub").write_text(garbage + "\n")
        r = subprocess.run(
            ["node", "scripts/keygen.mjs"], cwd=ext, capture_output=True, text=True, timeout=60
        )
        assert r.returncode != 0
        assert "EXTENSION_ID=" not in r.stdout
        assert "not a public key" in r.stderr
        assert "restore it" in r.stderr
        assert (
            "delete extension-key.pub" not in r.stderr
        )  # no .pem here: deleting would mint a new ID

    @needs_node
    def test_a2e_keygen_never_mints_over_a_tracked_pub(self, tmp_path):
        """A2 edge (Finish review): a clone without the .pem whose .pub went missing locally must
        not mint a new key — the committed .pub is the extension's identity."""
        project = _committed_release_project(tmp_path)
        ext = project / "extension"
        (ext / "extension-key.pub").unlink()
        shutil.rmtree(ext / ".keys")
        r = subprocess.run(
            ["node", "scripts/keygen.mjs"], cwd=ext, capture_output=True, text=True, timeout=60
        )
        assert r.returncode != 0
        assert not (ext / ".keys").exists()
        assert "git checkout" in r.stderr

    @needs_node
    def test_a2f_keygen_refuses_a_pub_that_does_not_match_the_pem(self, tmp_path):
        """A2 edge (Finish review): a .pub from another key beside this .pem is refused, not echoed."""
        ext = _chrome_ext_project(tmp_path / "one") / "extension"
        other = _chrome_ext_project(tmp_path / "two") / "extension"
        for e in (ext, other):
            subprocess.run(["node", "scripts/keygen.mjs"], cwd=e, capture_output=True, timeout=60)
        (ext / "extension-key.pub").write_text((other / "extension-key.pub").read_text())
        r = subprocess.run(
            ["node", "scripts/keygen.mjs"], cwd=ext, capture_output=True, text=True, timeout=60
        )
        assert r.returncode != 0
        assert "does not match" in r.stderr
        assert "EXTENSION_ID=" not in r.stdout

    @needs_node
    def test_a2c_keygen_with_a_pem_but_no_pub_rederives_the_same_pub(self, tmp_path):
        """A2 edge (review round 1): the .pub was lost — keygen rebuilds it from the .pem, same ID."""
        ext = _chrome_ext_project(tmp_path) / "extension"
        subprocess.run(["node", "scripts/keygen.mjs"], cwd=ext, capture_output=True, timeout=60)
        pub = ext / "extension-key.pub"
        original = pub.read_text()
        pem_before = (ext / ".keys" / "extension-key.pem").read_bytes()
        pub.unlink()
        r = subprocess.run(
            ["node", "scripts/keygen.mjs"], cwd=ext, capture_output=True, text=True, timeout=60
        )
        assert r.returncode == 0, r.stdout + r.stderr
        assert pub.read_text() == original
        assert (ext / ".keys" / "extension-key.pem").read_bytes() == pem_before
        assert f"EXTENSION_ID={_ext_id_from_pub(original.strip())}" in r.stdout

    def test_a0b_emitted_scripts_sort_their_imports(self, project):
        """Lint (Finish review): antfu's sort-imports wants the node: built-ins in order."""
        for script in sorted((project / "extension" / "scripts").glob("*.mjs")):
            specs = re.findall(r"^import .* from '(node:[^']+)';$", script.read_text(), re.M)
            assert specs == sorted(specs), script.name

    def test_a3_wxt_config_reads_the_key_through_the_shared_resolver(self, project):
        """A3 (read half): wxt.config.ts takes `key` from scripts/manifest-key.mjs; alarms; no
        host permissions. The resolver's behaviour is test_a3b; the built manifest is the WXT build test."""
        cfg = (project / "extension" / "wxt.config.ts").read_text()
        assert "from './scripts/manifest-key.mjs'" in cfg
        assert "key: pinnedKey()," in cfg
        assert "permissions: ['storage', 'activeTab', 'contextMenus', 'alarms']" in cfg
        assert "host_permissions" not in cfg
        assert (project / "extension" / "scripts" / "manifest-key.d.mts").is_file()

    @needs_node
    def test_a3b_manifest_key_resolver(self, tmp_path):
        """A3 (behaviour): no .pub → none; a .pub → it, from any cwd; STORE_BUILD=1 → none; a
        malformed .pub → the build fails loudly."""
        import base64

        ext = _chrome_ext_project(tmp_path) / "extension"
        mod = (ext / "scripts" / "manifest-key.mjs").as_uri()
        prog = f"import {{ pinnedKey }} from '{mod}'; console.log(JSON.stringify(pinnedKey() ?? null));"
        base_env = {k: v for k, v in os.environ.items() if k != "STORE_BUILD"}
        none = _node_json(tmp_path, prog, base_env)  # cwd OUTSIDE extension/ on purpose
        assert none.returncode == 0 and none.stdout.strip() == "null", none.stderr
        subprocess.run(["node", "scripts/keygen.mjs"], cwd=ext, capture_output=True, timeout=60)
        pub = (ext / "extension-key.pub").read_text().strip()
        got = _node_json(tmp_path, prog, base_env)
        assert got.returncode == 0 and got.stdout.strip() == f'"{pub}"', got.stderr
        store = _node_json(tmp_path, prog, {**base_env, "STORE_BUILD": "1"})
        assert store.returncode == 0 and store.stdout.strip() == "null"
        junk = base64.b64encode(base64.b64decode(pub) + b"\0\0\0").decode()
        for garbage in ("not a key\n", "A" * 120 + "\n", junk + "\n"):
            (ext / "extension-key.pub").write_text(garbage)
            bad = _node_json(tmp_path, prog, base_env)
            assert bad.returncode != 0 and "not a public key" in bad.stderr, garbage

    @needs_node
    def test_a4_update_rules_executed(self, project):
        """A4 (behaviour): integer-wise comparison, untrusted-response validation, https-only base."""
        import json

        mod = (project / "extension" / "src" / "lib" / "update-version.ts").as_uri()
        prog = (
            f"import {{ isNewer, nextNotice, parseLatest, secureBase }} from '{mod}';"
            "console.log(JSON.stringify({"
            "newer: [isNewer('1.2', '1.1.9'), isNewer('1.10', '1.9'), isNewer('2', '1.9.9.9'),"
            " isNewer('1.0.0', '1'), isNewer('1.1', '1.2'), isNewer('1.0', '1.0.0.0')],"
            "ok: parseLatest({version: '1.2.3', download_url: 'https://x.invalid/a.zip', sha256: 'z'}),"
            "bad: [parseLatest({version: '1.2.3.4.5', download_url: 'https://x.invalid/a'}),"
            " parseLatest({version: 'v1', download_url: 'https://x.invalid/a'}),"
            " parseLatest({version: '1', download_url: 'http://x.invalid/a'}),"
            " parseLatest({version: '1', download_url: 'javascript:alert(1)'}),"
            " parseLatest({version: '1'}), parseLatest(null), parseLatest('1')],"
            "bases: [secureBase('https://api.invalid/v1/'), secureBase('http://api.invalid'),"
            " secureBase('http://localhost:8000'), secureBase('http://127.0.0.1:8000/'),"
            " secureBase(''), secureBase('not a url'), secureBase('https://api.invalid/v1/?x=1#h'),"
            " secureBase('https://u:p@api.invalid')],"
            "notice: [nextNotice(404, null, '1.0'), nextNotice(500, null, '1.0'),"
            " nextNotice(200, {version: '1.1', download_url: 'https://x.invalid/a'}, '1.0'),"
            " nextNotice(200, {version: '1.0', download_url: 'https://x.invalid/a'}, '1.0'),"
            " nextNotice(200, {version: '1.1', download_url: 'http://x.invalid/a'}, '1.0')],"
            "big: [parseLatest({version: '65535.1', download_url: 'https://x.invalid/a'}) !== null,"
            " parseLatest({version: '65536', download_url: 'https://x.invalid/a'}),"
            " parseLatest({version: '1.02', download_url: 'https://x.invalid/a'})]}));"
        )
        r = _node_json(project, prog)
        assert r.returncode == 0, r.stderr
        out = json.loads(r.stdout)
        assert out["newer"] == [True, True, True, False, False, False]
        assert out["ok"] == {"version": "1.2.3", "download_url": "https://x.invalid/a.zip"}
        assert out["bad"] == [None] * 7
        assert out["bases"] == [
            "https://api.invalid/v1",
            "",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "",
            "",
            "https://api.invalid/v1",
            "",
        ]
        assert out["big"] == [True, None, None]
        assert out["notice"] == [
            {"action": "clear"},  # 404: the release was withdrawn — drop the stale notice
            {"action": "keep"},  # a server error says nothing about the release
            {"action": "set", "notice": {"version": "1.1", "download_url": "https://x.invalid/a"}},
            {"action": "clear"},
            {"action": "keep"},  # an untrusted body that fails validation changes nothing
        ]

    def test_a4b_update_checker_wiring(self, project):
        """A4 (wiring): the checker uses those rules, skips store/policy installs, prefers the stored
        backend, asks /extension/latest with a timeout and no credentials, and badges both ways."""
        src = (project / "extension" / "src" / "lib" / "update-check.ts").read_text()
        assert "from '@/lib/update-version'" in src
        assert re.search(
            r"if \(browser\.runtime\.getManifest\(\)\.update_url\)\s*\n\s*return;", src
        )
        assert "secureBase(stored || API_BASE_URL)" in src
        assert "credentials: 'omit'" in src and "AbortSignal.timeout(10000)" in src
        assert "nextNotice(res.status," in src
        assert "setBadgeText({ text: '↑' })" in src and "setBadgeText({ text: '' })" in src

    def test_a5_background_schedules_checks_without_resetting_the_alarm(self, project):
        """A5: onStartup + onInstalled schedule checks; the alarm is created ONLY when absent;
        onAlarm handles update-check."""
        bg = (project / "extension" / "src" / "entrypoints" / "background.ts").read_text()
        chk = (project / "extension" / "src" / "lib" / "update-check.ts").read_text()
        assert re.search(
            r"runtime\.onStartup\.addListener\(\(\) => void scheduleUpdateChecks\(\)\)", bg
        )
        installed = bg[bg.index("runtime.onInstalled.addListener(") :]
        installed = installed[: installed.index("\n  });")]
        assert "void scheduleUpdateChecks();" in installed
        assert re.search(r"alarm\.name === 'update-check'\)\s*\n\s*void checkForUpdate\(\);", bg)
        assert re.search(
            r"if \(!\(await browser\.alarms\.get\('update-check'\)\)\)\s*\n"
            r"\s*await browser\.alarms\.create\('update-check', \{ periodInMinutes: 360 \}\);",
            chk,
        )
        assert chk.count("alarms.create(") == 1

    def test_a5b_popup_shows_the_update_banner_in_both_locales(self, project):
        """A4/A5 consumer: the popup reads updateNotice and labels it through the i18n locale."""
        import json

        popup = (project / "extension" / "src" / "entrypoints" / "popup" / "main.tsx").read_text()
        assert "updateNotice" in popup and "i18n.t('updateAvailable')" in popup
        assert "parseLatest(" in popup  # storage.local is writable by content scripts: re-check
        assert (
            "from '#i18n'" not in popup
        )  # auto-imported by @wxt-dev/i18n; tsconfig paths drop '#i18n'
        for loc in ("en", "tr"):
            msgs = json.loads(
                (project / "extension" / "src" / "locales" / f"{loc}.json").read_text()
            )
            assert msgs.get("updateAvailable"), loc

    def test_a6_install_guide(self, project):
        """A6: the guide names the four steps, keep Developer mode on, replace + Reload, the policy."""
        guide = (project / "extension" / "INSTALL.md").read_text()
        for needle in (
            "chrome://extensions",
            "Load unpacked",
            "keep Developer mode on",
            "manifest.json",
            "replace the contents",
            "Reload",
            "ExtensionDeveloperModeSettings",
            "Edge",
            "Brave",
        ):
            assert needle in guide, needle

    def test_a7_gitignore_phony_and_release_recipe(self, project):
        """A7 (read half): .gitignore, .PHONY, and a recipe that checks first, zips, checksums, copies
        the guide and publishes nothing."""
        gitignore = (project / ".gitignore").read_text()
        assert "extension/.keys/" in gitignore and ".env.*.local" in gitignore
        makefile = (project / "Makefile").read_text()
        assert "release-ext" in makefile.splitlines()[0]
        recipe = _make_target(makefile, "release-ext")
        lines = [ln.strip() for ln in recipe.splitlines()[1:] if ln.startswith("\t")]
        assert lines[0] == "cd extension && node scripts/release-check.mjs"
        assert "keygen" not in recipe
        assert "pnpm zip" in lines[1]
        assert 'sha256sum "$$zip" > "$$zip.sha256"' in lines[1]
        assert "cp ../INSTALL.md ." in lines[1]
        assert "release-check.mjs --summary" in lines[1]
        for banned in ("scp", "rsync", "curl", "upload", "gh release"):
            assert banned not in recipe, banned

    @needs_node
    def test_a7_release_refuses_without_a_committed_pub(self, tmp_path):
        """A7 (run half): no committed .pub → `make release-ext` exits non-zero before any zip, naming
        the missing key and the next steps."""
        if shutil.which("make") is None:
            pytest.skip("make not installed")
        project = _chrome_ext_project(tmp_path)
        (project / "extension" / ".env.production").write_text(
            "VITE_PUBLIC_API_URL=https://ok.invalid\n"
        )
        _git(project, "add", "-A")
        _git(project, "commit", "-qm", "scaffold")
        r = subprocess.run(
            ["make", "release-ext"], cwd=project, capture_output=True, text=True, timeout=120
        )
        assert r.returncode != 0
        assert "extension-key.pub is missing or not committed" in r.stderr
        assert "extension/.env.production and commit it" in r.stderr
        assert "VITE_PUBLIC_API_URL" not in r.stderr.split("next steps")[0]  # only the key is wrong
        assert not (project / "extension" / ".output").exists()

    @needs_node
    @pytest.mark.parametrize(
        ("env_url", "files", "ok"),
        [
            # the environment wins over every file
            (
                "http://insecure.invalid",
                {".env.production": "VITE_PUBLIC_API_URL=https://ok.invalid\n"},
                False,
            ),
            (
                "https://ok.invalid",
                {".env.production": "VITE_PUBLIC_API_URL=http://bad.invalid\n"},
                True,
            ),
            ("", {".env": "VITE_PUBLIC_API_URL=https://ok.invalid\n"}, False),  # defined but empty
            # unset in the environment: WXT's order — later files win
            (
                None,
                {
                    ".env.production": "VITE_PUBLIC_API_URL=http://bad.invalid\n",
                    ".env": "VITE_PUBLIC_API_URL=https://ok.invalid\n",
                },
                False,
            ),
            (
                None,
                {
                    ".env.production.local": "VITE_PUBLIC_API_URL=http://bad.invalid\n",
                    ".env.production": "VITE_PUBLIC_API_URL=https://ok.invalid\n",
                },
                False,
            ),
            # WXT also loads the browser-suffixed files, highest of all
            (
                None,
                {
                    ".env.production.chrome": "VITE_PUBLIC_API_URL=http://bad.invalid\n",
                    ".env.production": "VITE_PUBLIC_API_URL=https://ok.invalid\n",
                },
                False,
            ),
            (None, {".env.chrome": "VITE_PUBLIC_API_URL=https://ok.invalid\n"}, True),
            # dotenv forms the build reads
            (None, {".env": "VITE_PUBLIC_API_URL='https://ok.invalid'\n"}, True),
            (None, {".env": 'export VITE_PUBLIC_API_URL="https://ok.invalid" # prod\r\n'}, True),
            # a colon form only Vite's dotenv reads — refused, never guessed
            (
                None,
                {
                    ".env.production": "VITE_PUBLIC_API_URL: http://bad.invalid\n",
                    ".env": "VITE_PUBLIC_API_URL=https://ok.invalid\n",
                },
                False,
            ),
            (None, {".env": "VITE_PUBLIC_API_URL=https://\n"}, False),  # no host
            (None, {".env.production": "VITE_PUBLIC_API_URL=https://${API_HOST}\n"}, False),
            (None, {".env": "VITE_PUBLIC_API_URL=https:ok.invalid\n"}, False),  # no //
            (None, {}, False),
        ],
    )
    def test_a7b_release_checks_the_effective_api_url(self, tmp_path, env_url, files, ok):
        """A7 (S1-P1): the URL gate reads the value the production build will use, the way WXT loads
        it, and a refusal names the URL as the reason."""
        project = _committed_release_project(tmp_path, files)
        r = _release_check(project, env_url)
        assert (r.returncode == 0) is ok, r.stdout + r.stderr
        if not ok:
            assert "VITE_PUBLIC_API_URL" in r.stderr.split("next steps")[0]

    @needs_node
    @pytest.mark.parametrize(
        ("change", "reason"),
        [
            ("store", "STORE_BUILD"),
            ("dirty", "not clean"),
            ("prerelease", "not a Chrome version"),
            ("toobig", "not a Chrome version"),
            ("leadingzero", "not a Chrome version"),
            ("badpub", "not a public key"),
            ("untracked", "missing or not committed"),
        ],
    )
    def test_a7c_release_refuses_a_store_build_a_dirty_tree_and_a_non_chrome_version(
        self, tmp_path, change, reason
    ):
        """A7 (review round 1): a store build carries no key, a dirty tree is not what was committed,
        and a version Chrome cannot parse never reaches the update checker."""
        import json

        good = {".env.production": "VITE_PUBLIC_API_URL=https://ok.invalid\n"}
        project = _committed_release_project(tmp_path, good)
        assert _release_check(project).returncode == 0  # the baseline passes
        extra = {}
        if change == "store":
            extra = {"STORE_BUILD": "1"}
        elif change == "dirty":
            (project / "README.md").write_text("edited\n")
        elif change == "badpub":
            (project / "extension" / "extension-key.pub").write_text("A" * 120 + "\n")
            _git(project, "commit", "-qam", "garbage pub")
        elif change == "untracked":
            _git(project, "rm", "-q", "--cached", "extension/extension-key.pub")
            _git(project, "commit", "-qm", "untrack pub")
            (project / ".git" / "info" / "exclude").write_text("extension/extension-key.pub\n")
        else:
            pkg = project / "extension" / "package.json"
            data = json.loads(pkg.read_text())
            data["version"] = {"prerelease": "1.2.0-beta.1", "toobig": "70000.0"}.get(
                change, "1.02"
            )
            pkg.write_text(json.dumps(data))
            _git(project, "commit", "-qam", "beta")
        r = _release_check(project, None, extra)
        assert r.returncode != 0 and reason in r.stderr.split("next steps")[0], r.stdout + r.stderr

    @needs_node
    def test_a7d_summary_prints_the_four_backend_values(self, tmp_path):
        """A7: `--summary <zip>` prints EXTENSION_ID, the version, the URL placeholder and the SHA-256."""
        import json

        project = _committed_release_project(tmp_path)
        out_dir = project / "extension" / ".output"
        out_dir.mkdir()
        (out_dir / "test-ext-1.0.0-chrome.zip").write_bytes(b"zip")
        (out_dir / "test-ext-1.0.0-chrome.zip.sha256").write_text(
            "abc123  test-ext-1.0.0-chrome.zip\n"
        )
        r = subprocess.run(
            ["node", "../scripts/release-check.mjs", "--summary", "test-ext-1.0.0-chrome.zip"],
            cwd=out_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert r.returncode == 0, r.stderr
        pub = (project / "extension" / "extension-key.pub").read_text().strip()
        version = json.loads((project / "extension" / "package.json").read_text())["version"]
        for line in (
            f"EXTENSION_ID={_ext_id_from_pub(pub)}",
            f"EXTENSION_LATEST_VERSION={version}",
            "EXTENSION_LATEST_URL=<download-url>",
            "EXTENSION_LATEST_SHA256=abc123",
        ):
            assert line in r.stdout, line


_EXT_ID = "abcdefghijklmnopabcdefghijklmnop"
_OTHER_ID = "ponmlkjihgfedcbaponmlkjihgfedcba"
_SERVER_ENV_KEYS = (
    "EXTENSION_ID",
    "EXTENSION_LATEST_VERSION",
    "EXTENSION_LATEST_URL",
    "EXTENSION_LATEST_SHA256",
    "CORS_ALLOW_ANY_EXTENSION",
)


def _run_server(project: Path, env: dict[str, str], program: str) -> tuple[dict, str]:
    """Import the emitted server in a FRESH interpreter with `env` (CORS is fixed at import) and
    run `program` inside `with TestClient(app) as client` (so lifespan runs). Returns the JSON the
    program stored in `out`, and the process stdout (where the emitted structlog writes)."""
    import json
    import sys

    base = {k: v for k, v in os.environ.items() if k not in _SERVER_ENV_KEYS}
    prog = (
        "import json, sys\n"
        "from fastapi.testclient import TestClient\n"
        "from test_ext.main import app\n"
        "out = {}\n"
        "with TestClient(app) as client:\n"
        + "".join(f"    {line}\n" for line in program.strip().splitlines())
        + "print('RESULT ' + json.dumps(out))\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", prog],
        cwd=project / "server" / "src",
        capture_output=True,
        text=True,
        timeout=120,
        env={**base, **env},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    line = next(ln for ln in r.stdout.splitlines() if ln.startswith("RESULT "))
    return json.loads(line[len("RESULT ") :]), r.stdout


def _log_events(stdout: str) -> list[tuple[str, str]]:
    """(event, level) for every JSON log line the emitted structlog wrote."""
    import json

    events = []
    for line in stdout.splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and "event" in rec:
            events.append((rec["event"], str(rec.get("level", "")).lower()))
    return events


_PREFLIGHT = f"""
for name, origin in (("other", "chrome-extension://{_OTHER_ID}"), ("pinned", "chrome-extension://{_EXT_ID}")):
    r = client.options("/health", headers={{"Origin": origin, "Access-Control-Request-Method": "GET"}})
    out[name] = r.headers.get("access-control-allow-origin")
    g = client.get("/health", headers={{"Origin": origin}})
    out[name + "_get"] = g.headers.get("access-control-allow-origin")
    out[name + "_cred"] = r.headers.get("access-control-allow-credentials")
r = client.options("/extension/latest", headers={{"Origin": "chrome-extension://{_EXT_ID}", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"}})
out["auth_origin"] = r.headers.get("access-control-allow-origin")
out["auth_headers"] = (r.headers.get("access-control-allow-headers") or "").lower()
"""


@requires_fabrik_env
class TestChromeExtensionBackendRelease:
    """W-e2af3303 Phase B: GET /extension/latest and closed-by-default exact-origin CORS."""

    @pytest.fixture(scope="class")
    def project(self, tmp_path_factory) -> Path:
        return _chrome_ext_project(tmp_path_factory.mktemp("cxb"))

    @pytest.mark.parametrize(
        "env",
        [
            {},
            {
                "EXTENSION_LATEST_VERSION": "",
                "EXTENSION_LATEST_URL": "",
                "EXTENSION_LATEST_SHA256": "",
            },
            {
                "EXTENSION_LATEST_VERSION": "1.2.0",
                "EXTENSION_LATEST_URL": "https://x.invalid/a.zip",
            },
            {"EXTENSION_LATEST_VERSION": "1.2.0", "EXTENSION_LATEST_SHA256": "ab" * 32},
            {
                "EXTENSION_LATEST_URL": "https://x.invalid/a.zip",
                "EXTENSION_LATEST_SHA256": "ab" * 32,
            },
            {
                "EXTENSION_LATEST_VERSION": "1.2.0",
                "EXTENSION_LATEST_URL": "   ",
                "EXTENSION_LATEST_SHA256": "ab" * 32,
            },
        ],
    )
    def test_b1_latest_is_404_until_all_three_are_set(self, project, env):
        """B1: unset, empty, or two of three → 404 'no release published'."""
        out, _ = _run_server(
            project,
            env,
            "r = client.get('/extension/latest')\nout['status'] = r.status_code\nout['body'] = r.json()\n"
            "out['cache'] = r.headers.get('cache-control')",
        )
        # no-store on the 404 too: a cached "no release" would hide the next release
        assert out == {
            "status": 404,
            "body": {"detail": "no release published"},
            "cache": "no-store",
        }

    def test_b2_latest_returns_exactly_the_three_values(self, project):
        """B2: all three set → 200 with exactly those values."""
        env = {
            "EXTENSION_LATEST_VERSION": "1.2.0",
            "EXTENSION_LATEST_URL": "https://x.invalid/a.zip",
            "EXTENSION_LATEST_SHA256": "ab" * 32,
        }
        out, _ = _run_server(
            project,
            env,
            "r = client.get('/extension/latest')\nout['status'] = r.status_code\nout['body'] = r.json()\n"
            "out['cache'] = r.headers.get('cache-control')",
        )
        assert out["status"] == 200
        assert out["body"] == {
            "version": "1.2.0",
            "download_url": "https://x.invalid/a.zip",
            "sha256": "ab" * 32,
        }
        assert out["cache"] == "no-store"

    def test_b2b_latest_is_read_per_request(self, project):
        """B2: a new value set after import (a redeploy's .env) is served without a code change."""
        out, _ = _run_server(
            project,
            {},
            "import os\n"
            "os.environ.update(EXTENSION_LATEST_VERSION='2.0', EXTENSION_LATEST_URL='https://x.invalid/b.zip', "
            "EXTENSION_LATEST_SHA256='cd' * 32)\n"
            "out['body'] = client.get('/extension/latest').json()",
        )
        assert out["body"]["version"] == "2.0"

    @pytest.mark.parametrize("raw", [_EXT_ID, _EXT_ID + "\r"])
    def test_b3_exact_extension_origin_only(self, project, raw):
        """B3: a valid EXTENSION_ID (even with a trailing CR) admits that origin and no other."""
        out, _ = _run_server(project, {"EXTENSION_ID": raw}, _PREFLIGHT)
        assert out["other"] is None and out["other_get"] is None
        assert out["pinned"] == f"chrome-extension://{_EXT_ID}"
        assert out["pinned_get"] == f"chrome-extension://{_EXT_ID}"
        assert (
            out["pinned_cred"] == "true"
        )  # the Bearer-carrying requests (70-chrome-ext.md § Auth)
        assert out["auth_origin"] == f"chrome-extension://{_EXT_ID}"
        assert "authorization" in out["auth_headers"]

    @pytest.mark.parametrize(
        ("env", "invalid"),
        [
            ({}, False),
            ({"EXTENSION_ID": ""}, False),
            ({"EXTENSION_ID": f"chrome-extension://{_EXT_ID}"}, True),
            # the exact shape: 32 letters a-p — q-z, a wrong length or upper case is not an ID
            ({"EXTENSION_ID": "z" * 32}, True),
            ({"EXTENSION_ID": _EXT_ID[:31]}, True),
            ({"EXTENSION_ID": _EXT_ID + "a"}, True),
            ({"EXTENSION_ID": _EXT_ID.upper()}, True),
        ],
    )
    def test_b4_no_valid_id_admits_no_extension(self, project, env, invalid):
        """B4: no valid ID → cors_no_extension_id (and cors_extension_id_invalid for a bad value),
        no allow-origin header for any extension."""
        out, stdout = _run_server(project, env, _PREFLIGHT)
        assert out["other"] is None and out["pinned"] is None
        assert out["other_get"] is None and out["pinned_get"] is None
        events = _log_events(stdout)
        assert events.index(("service_starting", "info")) < events.index(
            ("cors_no_extension_id", "warning")
        )  # logged in lifespan, after startup — not at import
        assert (("cors_extension_id_invalid", "error") in events) is invalid

    def test_b4c_a_valid_id_beats_the_local_opt_in(self, project):
        """B4 edge: EXTENSION_ID valid AND CORS_ALLOW_ANY_EXTENSION=1 → the exact ID only, no warning."""
        out, stdout = _run_server(
            project, {"EXTENSION_ID": _EXT_ID, "CORS_ALLOW_ANY_EXTENSION": "1"}, _PREFLIGHT
        )
        assert out["other"] is None and out["pinned"] == f"chrome-extension://{_EXT_ID}"
        assert "cors_any_extension_origin" not in stdout and "cors_no_extension_id" not in stdout

    def test_b4b_local_opt_in_admits_any_extension(self, project):
        """B4b: CORS_ALLOW_ANY_EXTENSION=1 (local only) → the dev regex and its own warning."""
        out, stdout = _run_server(project, {"CORS_ALLOW_ANY_EXTENSION": "1"}, _PREFLIGHT)
        assert out["other"] == f"chrome-extension://{_OTHER_ID}"
        assert out["pinned"] == f"chrome-extension://{_EXT_ID}"
        assert ("cors_any_extension_origin", "warning") in _log_events(stdout)
        assert "cors_no_extension_id" not in stdout

    def test_b5_compose_template_defaults_and_env_example(self, project):
        """B5: no Traefik CORS labels; the four ${VAR:-} env lines on both compose paths; no
        CORS_ORIGINS anywhere; .env.example names the four and the commented local opt-in."""
        template_dir = Path(__file__).resolve().parents[1] / "templates" / "chrome-extension"
        compose = (project / "compose.yaml").read_text()
        template = (template_dir / "compose.yaml.j2").read_text()
        for text in (compose, template):
            assert "-cors" not in text
            assert "CORS_ORIGINS" not in text
            for var in _SERVER_ENV_KEYS[:4]:
                assert f"- {var}=${{{var}:-}}" in text, var
        assert "CORS_ORIGINS" not in (template_dir / "defaults.yaml").read_text()
        example = (project / ".env.example").read_text()
        for var in _SERVER_ENV_KEYS[:4]:
            assert re.search(rf"^{var}=", example, re.M), var
        assert re.search(r"^# CORS_ALLOW_ANY_EXTENSION=1", example, re.M)
        assert "never in a deploy" in example

    def test_b5b_template_renders_each_extension_value_once(self, project, tmp_path):
        """B5 (review round 1): the generated spec copies the four values into its env:, so the
        template must not render them a second time from its env loop."""
        from fabrik.spec_loader import load_spec
        from fabrik.template_renderer import TemplateRenderer

        templates = Path(__file__).resolve().parents[1] / "templates"
        spec = load_spec(project.parent / "specs" / "services" / "test-ext.yaml")
        # the precondition that makes this a test of the template filter, not of the generator
        assert set(_SERVER_ENV_KEYS[:4]) <= set(spec.env)
        rendered = TemplateRenderer(templates_dir=templates, output_dir=tmp_path).render(
            spec, dry_run=True
        )
        compose = rendered["compose.yaml"]
        for var in _SERVER_ENV_KEYS[:4]:
            assert compose.count(f"- {var}=") == 1, var
        # defaults.yaml carries these two as well; a second literal copy would override .env
        for var in ("LOG_LEVEL", "PYTHONUNBUFFERED"):
            assert compose.count(f"- {var}=") == 1, var

    @pytest.mark.parametrize("value", ["0", "true", "yes", ""])
    def test_b4d_the_local_opt_in_is_exactly_one(self, project, value):
        """B4 edge (Finish review): only CORS_ALLOW_ANY_EXTENSION=1 opens CORS — 0/true/yes do not."""
        out, stdout = _run_server(project, {"CORS_ALLOW_ANY_EXTENSION": value}, _PREFLIGHT)
        assert out["other"] is None and out["pinned"] is None
        assert ("cors_no_extension_id", "warning") in _log_events(stdout)

    def test_b7_emitted_server_type_checks(self, project):
        """The emitted server passes mypy under its own config (Finish review: the CORS branches)."""
        import sys

        server = project / "server"
        r = subprocess.run(
            [sys.executable, "-m", "mypy", "--config-file", "pyproject.toml", "src"],
            cwd=server,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert r.returncode == 0, r.stdout + r.stderr

    def test_b6_dev_targets_load_the_local_env(self, project):
        """B6: `make dev` and `make dev-server` pass .env to uvicorn when it exists."""
        makefile = (project / "Makefile").read_text()
        for target in ("dev", "dev-server"):
            recipe = _make_target(makefile, target)
            uvicorn = [ln for ln in recipe.splitlines() if ln.startswith("\t") and "uvicorn" in ln]
            assert uvicorn, target
            assert all("$(if $(wildcard .env),--env-file .env,)" in ln for ln in uvicorn), target


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
