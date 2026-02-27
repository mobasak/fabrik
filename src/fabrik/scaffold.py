"""Project scaffolding - create new projects with full structure."""

import os
import re
import shutil
import subprocess
from collections.abc import Callable
from datetime import date
from pathlib import Path

from fabrik.config import FABRIK_ROOT

# Reserved project names that conflict with system dirs or packages
RESERVED_NAMES = frozenset(
    {
        "src",
        "test",
        "tests",
        "lib",
        "bin",
        "opt",
        "tmp",
        "var",
        "usr",
        "home",
        "root",
        "etc",
        "dev",
        "proc",
        "sys",
        "fabrik",
        "python",
    }
)

SCAFFOLD_TYPES = frozenset(
    {
        "python-api",
        "saas-skeleton",
        "node-api",
        "file-api",
        "file-worker",
        "wordpress",
        "docusaurus",
        "chrome-extension",
        "mobile-app",
        "desktop-app",
    }
)

TEMPLATE_DIR = FABRIK_ROOT / "templates" / "scaffold"

SHARED_TEMPLATE_MAP = {
    "docs/PROJECT_INDEX_TEMPLATE.md": "INDEX.md",
    "docs/PROJECT_README_TEMPLATE.md": "README.md",
    "docs/CHANGELOG_TEMPLATE.md": "CHANGELOG.md",
    "docs/DOCS_INDEX_TEMPLATE.md": "docs/README.md",
    "docs/QUICKSTART_TEMPLATE.md": "docs/QUICKSTART.md",
    "docs/CONFIGURATION_TEMPLATE.md": "docs/CONFIGURATION.md",
    "docs/TROUBLESHOOTING_TEMPLATE.md": "docs/TROUBLESHOOTING.md",
    "docs/BUSINESS_MODEL_TEMPLATE.md": "docs/BUSINESS_MODEL.md",
    # Note: Phase docs removed - Traycer Phases replace manual phase tracking
    # Note: tasks.md removed - Traycer UI replaces manual task dashboard
    # Note: PLANS.md and archive/README.md are generated inline, not from templates
}

_PYTHON_API_TEMPLATE_MAP = {
    # Droid exec / Docker workflow files (AGENTS.md handled separately as symlink)
    "docker/Dockerfile.python": "Dockerfile",
    "docker/compose.yaml.template": "compose.yaml",
    "docker/compose.dev.yaml.template": "compose.dev.yaml",
    "docker/dockerignore.template": ".dockerignore",
    "docker/Makefile.python": "Makefile",
    # Python tooling config
    "python/pyproject.toml.template": "pyproject.toml",
}

_SHARED_REQUIRED_FILES = [
    "INDEX.md",
    "README.md",
    "CHANGELOG.md",
    "docs/README.md",
    "docs/QUICKSTART.md",
    "docs/CONFIGURATION.md",
    "docs/TROUBLESHOOTING.md",
]

TYPE_REQUIRED_FILES: dict[str, list[str]] = {
    "python-api": _SHARED_REQUIRED_FILES + ["Dockerfile", "compose.yaml"],
    "saas-skeleton": _SHARED_REQUIRED_FILES[:],
    "node-api": _SHARED_REQUIRED_FILES[:],
    "file-api": _SHARED_REQUIRED_FILES[:],
    "file-worker": _SHARED_REQUIRED_FILES[:],
    "wordpress": _SHARED_REQUIRED_FILES[:],
    "docusaurus": _SHARED_REQUIRED_FILES[:],
    "chrome-extension": _SHARED_REQUIRED_FILES[:],
    "mobile-app": _SHARED_REQUIRED_FILES[:],
    "desktop-app": _SHARED_REQUIRED_FILES[:],
}

SHARED_DIRS = [
    "docs/guides",
    "docs/reference",
    "docs/operations",
    "docs/development",
    "docs/development/plans",
    "docs/archive",
    "config",
    "scripts",
    "tests",
    "logs",
    "data",
    ".tmp",
    ".cache",
    "output",
    ".droid/review-context",  # Kilo/Traycer review context directory
]

_PYTHON_API_DIRS = ["src"]

SCRIPT_FILES = ["runc", "rund", "rundsh", "runk", "sync_cascade_backup.sh", "sync_extensions.sh"]

# Master AGENTS.md location
FABRIK_AGENTS_MD = FABRIK_ROOT / "AGENTS.md"


def _ensure_symlink(link_path: Path, target: Path) -> bool:
    """
    Ensure link_path is a symlink pointing to target.
    Returns True if created/updated, False if already correct.
    """
    link_path.parent.mkdir(parents=True, exist_ok=True)

    # If it exists and is a symlink, verify target
    if link_path.is_symlink():
        resolved = Path(link_path.resolve())
        target_resolved = Path(target.resolve())
        if resolved == target_resolved:
            return False
        link_path.unlink()  # wrong target -> replace

    # If it exists but is NOT a symlink, do not clobber silently
    if link_path.exists():
        raise FileExistsError(f"Expected symlink but found existing path: {link_path}")

    link_path.symlink_to(target)
    return True


def _get_package_name(project_name: str) -> str:
    """Convert project name to Python package name (hyphens to underscores)."""
    return project_name.replace("-", "_")


def _validate_project_name(name: str) -> None:
    """Validate project name. Raises ValueError if invalid."""
    if not name:
        raise ValueError("Project name cannot be empty")
    if not re.match(r"^[a-z][a-z0-9-]*$", name):
        raise ValueError(
            f"Invalid project name: '{name}'. "
            "Must be lowercase, start with letter, contain only letters, numbers, hyphens."
        )
    if name in RESERVED_NAMES:
        raise ValueError(f"Reserved project name: '{name}'")
    if len(name) > 50:
        raise ValueError(f"Project name too long: {len(name)} chars (max 50)")


def _link_agents_md(project_dir: Path) -> None:
    """Symlink AGENTS.md to master, fallback to copy if master unavailable."""
    link_path = project_dir / "AGENTS.md"
    if FABRIK_AGENTS_MD.exists():
        try:
            link_path.symlink_to(FABRIK_AGENTS_MD)
        except OSError:
            # Symlink failed, copy instead
            shutil.copy(FABRIK_AGENTS_MD, link_path)
    else:
        # Master not found, copy template
        template = TEMPLATE_DIR / "AGENTS.md"
        if template.exists():
            shutil.copy(template, link_path)
        else:
            link_path.write_text(f"# AGENTS.md\n\nSee {FABRIK_AGENTS_MD} for full briefing.\n")


def _install_pre_commit(project_dir: Path) -> bool:
    """Copy pre-commit config and install hooks. Returns True if successful."""
    # Copy config file
    src_config = TEMPLATE_DIR / "pre-commit-config.yaml"
    dest_config = project_dir / ".pre-commit-config.yaml"
    if src_config.exists():
        shutil.copy(src_config, dest_config)
    else:
        return False

    # Try to install hooks (graceful failure)
    if shutil.which("pre-commit"):
        result = subprocess.run(
            ["pre-commit", "install"],
            cwd=project_dir,
            capture_output=True,
        )
        return result.returncode == 0
    else:
        # pre-commit not available, but config is copied
        return True


def _scaffold_shared(project_dir: Path, name: str, description: str, today: str) -> None:
    """Create the shared project structure common to all project types, including git init."""
    # Create shared directories
    for d in SHARED_DIRS:
        (project_dir / d).mkdir(parents=True, exist_ok=True)

    # Write .droid/ files: gitignore keeps review-context/, blocks runtime files
    (project_dir / ".droid" / ".gitignore").write_text(
        "# Kilo/Traycer runtime files — do not commit\n"
        "*\n"
        "!.gitignore\n"
        "!review-context/\n"
        "!review-context/**\n"
    )
    # .gitkeep so git tracks the empty review-context/ directory
    (project_dir / ".droid" / "review-context" / ".gitkeep").write_text("")

    package_name = _get_package_name(name)

    # Copy shared templates
    for src, dest in SHARED_TEMPLATE_MAP.items():
        src_path = TEMPLATE_DIR / src
        if src_path.exists():
            content = src_path.read_text()
            for old, new in [
                ("[Project Name]", name),
                ("[project]", name),  # README paths
                ("<project>", name),  # QUICKSTART paths
                ("project-name", name),  # pyproject.toml
                ("myproject", name),  # Makefile
                ("[package_name]", package_name),  # README imports
                ("<package_name>", package_name),  # QUICKSTART imports
                ("YYYY-MM-DD", today),
                ("[Brief description]", description),
                ("[One-line description]", description),
                ("Brief project description", description),  # pyproject.toml
            ]:
                content = content.replace(old, new)
            (project_dir / dest).write_text(content)

    # Copy executable scripts from templates/scaffold/scripts/
    for f in SCRIPT_FILES:
        script_src = TEMPLATE_DIR / "scripts" / f
        if script_src.exists():
            script_dest = project_dir / "scripts" / f
            shutil.copy(script_src, script_dest)
            os.chmod(script_dest, 0o755)  # noqa: S103  # nosec B103

    # Symlink windsurfrules (legacy) and .windsurf/rules/ (authoritative)
    # Fail fast if fabrik targets are missing - environment is broken
    fabrik_windsurfrules = FABRIK_ROOT / "windsurfrules"
    fabrik_windsurf_rules = FABRIK_ROOT / ".windsurf" / "rules"

    if not fabrik_windsurfrules.exists():
        raise FileNotFoundError(f"Missing fabrik windsurfrules: {fabrik_windsurfrules}")
    if not fabrik_windsurf_rules.exists():
        raise FileNotFoundError(f"Missing fabrik windsurf rules dir: {fabrik_windsurf_rules}")

    _ensure_symlink(project_dir / ".windsurfrules", fabrik_windsurfrules)
    _ensure_symlink(project_dir / ".windsurf" / "rules", fabrik_windsurf_rules)

    # AGENTS.md: symlink to master, fallback to copy
    _link_agents_md(project_dir)

    # Create .gitignore and .env.example
    (project_dir / ".gitignore").write_text(
        ".env\nvenv/\n__pycache__/\nlogs/\ndata/\n.tmp/\n.cache/\noutput/\n*.log\n.venv/\n"
        ".droid/kilo_usage.jsonl\n.droid/reviews/\n.droid/kilo_models_cache.json\n.droid/.kilo_cache_last_refresh\n"
    )
    # Example .env template with placeholder values (not real credentials)  # noqa: secrets
    (project_dir / ".env.example").write_text(
        f"# {name} Configuration\n# Required\nPORT=8000\nLOG_LEVEL=INFO\n\n# Optional - uncomment if using database\n# DATABASE_URL=postgresql://user:pass@localhost:5432/{name}_dev\n"  # noqa: secrets
    )

    # Create PLANS.md inline (no template file)
    (project_dir / "docs" / "development" / "PLANS.md").write_text(
        f"""# Development Plans

Plan documents for {name}.

## Naming: `YYYY-MM-DD-plan-<name>.md`

## Lifecycle
1. Create in `docs/development/plans/`
2. Add to this index
3. Update `**Status:**` as work progresses
4. Archive when COMPLETE → `docs/archive/`

## Active Plans

| Plan | Date | Status |
|------|------|--------|
| (none) | - | - |
"""
    )

    # Create archive README inline (no template file)
    (project_dir / "docs" / "archive" / "README.md").write_text(
        f"""# Archived Documentation

Obsolete or completed docs for {name}.

## Convention: `YYYY-MM-DD-<topic>/` or `YYYY-MM-DD-<topic>.md`

## Index

| Date | Topic | Description |
|------|-------|-------------|
| (none) | - | - |
"""
    )

    # Git bootstrap: initialize repo so type-specific scaffolders run inside a git repo.
    # The final commit is deferred to create_project() so it captures all files in one
    # clean, complete snapshot.
    subprocess.run(["git", "init", "-q"], cwd=project_dir, capture_output=True)
    _install_pre_commit(project_dir)


def _scaffold_python_api(project_dir: Path, name: str, description: str, **kwargs: object) -> None:
    """Create Python API-specific project structure."""
    package_name = _get_package_name(name)
    today = date.today().isoformat()

    # Create Python API-specific directories
    for d in _PYTHON_API_DIRS:
        (project_dir / d).mkdir(parents=True, exist_ok=True)

    # Copy Python API templates
    for src, dest in _PYTHON_API_TEMPLATE_MAP.items():
        src_path = TEMPLATE_DIR / src
        if src_path.exists():
            content = src_path.read_text()
            for old, new in [
                ("[Project Name]", name),
                ("[project]", name),  # README paths
                ("<project>", name),  # QUICKSTART paths
                ("project-name", name),  # pyproject.toml
                ("myproject", name),  # Makefile
                ("[package_name]", package_name),  # README imports
                ("<package_name>", package_name),  # QUICKSTART imports
                ("YYYY-MM-DD", today),
                ("[Brief description]", description),
                ("[One-line description]", description),
                ("Brief project description", description),  # pyproject.toml
            ]:
                content = content.replace(old, new)
            (project_dir / dest).write_text(content)

    # Create requirements.txt (versions match pyproject.toml)
    (project_dir / "requirements.txt").write_text(
        "fastapi>=0.115.0\nuvicorn[standard]>=0.32.0\npydantic>=2.9.0\npython-dotenv>=1.0.0\nhttpx>=0.28.0\n"
    )

    # Create starter src/<package_name>/main.py with proper health check
    package_dir = project_dir / "src" / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "__init__.py").write_text("")
    (package_dir / "main.py").write_text(
        f'''"""Main entry point for {name}."""\nimport os\nfrom contextlib import asynccontextmanager\nfrom fastapi import FastAPI\nfrom fastapi.responses import JSONResponse\n\n\n@asynccontextmanager\nasync def lifespan(app: FastAPI):\n    """Application lifespan handler."""\n    # Startup: initialize resources here\n    yield\n    # Shutdown: cleanup resources here\n\n\napp = FastAPI(title="{name}", lifespan=lifespan)\n\n\n@app.get("/health")\nasync def health():\n    """Health check - tests actual dependencies, returns non-200 on failure."""\n    db_url = os.getenv("DATABASE_URL")\n    deps = {{}}\n    all_ok = True\n\n    # Database check (only if configured)\n    if db_url:\n        try:\n            # TODO: Replace with actual async DB ping when DB is added\n            # Example: await db.execute("SELECT 1")\n            deps["database"] = "configured"\n        except Exception as e:\n            deps["database"] = f"error: {{str(e)}}"\n            all_ok = False\n    else:\n        deps["database"] = "not_configured"\n\n    status_code = 200 if all_ok else 503\n    return JSONResponse(\n        content={{\n            "service": "{name}",\n            "status": "ok" if all_ok else "degraded",\n            "dependencies": deps,\n        }},\n        status_code=status_code,\n    )\n\n\n@app.get("/")\nasync def root():\n    return {{"message": "Welcome to {name}"}}\n'''
    )

    # Create basic test
    (project_dir / "tests" / "__init__.py").write_text("")
    (project_dir / "tests" / "test_health.py").write_text(
        f'''"""Health endpoint tests."""\nimport os\nfrom unittest.mock import patch\nfrom fastapi.testclient import TestClient\nfrom {package_name}.main import app\n\nclient = TestClient(app)\n\n\ndef test_health_returns_200_without_db():\n    """Health returns 200 when DB is not configured."""\n    with patch.dict(os.environ, {{}}, clear=True):\n        response = client.get("/health")\n        assert response.status_code == 200\n        data = response.json()\n        assert data["service"] == "{name}"\n        assert data["status"] == "ok"\n        assert data["dependencies"]["database"] == "not_configured"\n\n\ndef test_health_returns_200_with_db_configured():\n    """Health returns 200 when DB is configured (mocked)."""\n    with patch.dict(os.environ, {{"DATABASE_URL": "postgresql://test@localhost/test"}}):\n        response = client.get("/health")\n        assert response.status_code == 200\n        data = response.json()\n        assert data["dependencies"]["database"] == "configured"\n\n\ndef test_root_endpoint():\n    """Root endpoint returns welcome message."""\n    response = client.get("/")\n    assert response.status_code == 200\n    assert "message" in response.json()\n'''
    )


# Dispatch table mapping project types to their scaffolder functions.
# Subsequent phases will add entries for the other 9 types.
_TYPE_SCAFFOLDERS: dict[str, Callable[..., None]] = {
    "python-api": _scaffold_python_api,
}


def create_project(
    name: str,
    description: str,
    base: Path = Path("/opt"),
    project_type: str = "python-api",
    preset: str | None = None,
) -> Path:
    """Create a new project with full structure."""
    # Validate inputs
    _validate_project_name(name)

    if project_type not in SCAFFOLD_TYPES:
        valid = ", ".join(sorted(SCAFFOLD_TYPES))
        raise ValueError(f"Invalid project type: '{project_type}'. Valid types: {valid}")

    project_dir = base / name
    if project_dir.exists():
        raise ValueError(f"Project already exists: {project_dir}")

    # Resolve the type-specific scaffolder BEFORE writing anything so that an
    # unimplemented type raises NotImplementedError immediately, leaving no
    # partial project directory on disk.
    if project_type not in _TYPE_SCAFFOLDERS:
        raise NotImplementedError(f"Scaffolder for '{project_type}' not yet implemented")
    scaffolder = _TYPE_SCAFFOLDERS[project_type]

    today = date.today().isoformat()

    # _scaffold_shared() creates all shared structure AND runs git init + pre-commit install.
    _scaffold_shared(project_dir, name, description, today)

    scaffolder(project_dir, name, description, preset=preset)

    # Final commit after all files (shared + type-specific) are in place so the
    # initial snapshot is complete and clean.
    subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "Initial commit"], cwd=project_dir, capture_output=True
    )

    return project_dir


def validate_project(
    project_path: Path,
    project_type: str = "python-api",
) -> tuple[list[str], list[str]]:
    """Validate project structure. Returns (present, missing) file lists."""
    if project_type not in SCAFFOLD_TYPES:
        valid = ", ".join(sorted(SCAFFOLD_TYPES))
        raise ValueError(f"Invalid project type: '{project_type}'. Valid types: {valid}")

    required = TYPE_REQUIRED_FILES.get(project_type, TYPE_REQUIRED_FILES["python-api"])
    present, missing = [], []
    for f in required:
        if (project_path / f).exists():
            present.append(f)
        else:
            missing.append(f)
    return present, missing


def fix_project(
    project_path: Path,
    dry_run: bool = False,
    project_type: str = "python-api",
) -> list[str]:
    """Add missing required files to a project. Returns list of files added."""
    from datetime import date

    project_path = Path(project_path)
    name = project_path.name
    today = date.today().isoformat()
    added: list[str] = []

    _, missing = validate_project(project_path, project_type=project_type)

    # Build the combined template map for this project type
    type_template_map = _PYTHON_API_TEMPLATE_MAP if project_type == "python-api" else {}
    combined_template_map = {**SHARED_TEMPLATE_MAP, **type_template_map}

    # Create missing files (if any)
    for f in missing:
        dest_path = project_path / f

        if dry_run:
            added.append(f)
            continue

        # Create parent directories
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if we have a template
        template_name = None
        for src, dest in combined_template_map.items():
            if dest == f:
                template_name = src
                break

        if template_name and (TEMPLATE_DIR / template_name).exists():
            content = (TEMPLATE_DIR / template_name).read_text()
            for old, new in [
                ("[Project Name]", name),
                ("[project]", name),
                ("<project>", name),
                ("YYYY-MM-DD", today),
                ("[Brief description]", f"{name} project"),
                ("[One-line description]", f"{name} project"),
                ("myproject", name),  # Makefile
            ]:
                content = content.replace(old, new)
            dest_path.write_text(content)
        else:
            # Create minimal placeholder
            dest_path.write_text(f"# {f}\n\n**Last Updated:** {today}\n\nTODO: Add content\n")

        added.append(f)

    # Ensure symlinks exist
    windsurfrules_target = FABRIK_ROOT / "windsurfrules"
    windsurf_rules_target = FABRIK_ROOT / ".windsurf" / "rules"

    if not dry_run:
        # Fail fast if fabrik targets are missing - environment is broken
        if not windsurfrules_target.exists():
            raise FileNotFoundError(f"Missing fabrik windsurfrules: {windsurfrules_target}")
        if not windsurf_rules_target.exists():
            raise FileNotFoundError(f"Missing fabrik windsurf rules dir: {windsurf_rules_target}")

        if _ensure_symlink(project_path / ".windsurfrules", windsurfrules_target):
            added.append(".windsurfrules (symlink)")

        if _ensure_symlink(project_path / ".windsurf" / "rules", windsurf_rules_target):
            added.append(".windsurf/rules (symlink)")

        agents_link = project_path / "AGENTS.md"
        if not agents_link.exists() and not agents_link.is_symlink():
            _link_agents_md(project_path)
            added.append("AGENTS.md (symlink or copy)")
    else:
        # dry_run: accurately report what would be created/fixed
        # .windsurfrules
        link = project_path / ".windsurfrules"
        if link.is_symlink():
            if Path(link.resolve()) != Path(windsurfrules_target.resolve()):
                added.append(".windsurfrules (symlink fix)")
        elif not link.exists():
            added.append(".windsurfrules (symlink)")

        # .windsurf/rules
        link = project_path / ".windsurf" / "rules"
        if link.is_symlink():
            if Path(link.resolve()) != Path(windsurf_rules_target.resolve()):
                added.append(".windsurf/rules (symlink fix)")
        elif not link.exists():
            added.append(".windsurf/rules (symlink)")

        # AGENTS.md
        agents = project_path / "AGENTS.md"
        if agents.is_symlink():
            if Path(agents.resolve()) != Path(FABRIK_AGENTS_MD.resolve()):
                added.append("AGENTS.md (symlink fix)")
        elif not agents.exists():
            added.append("AGENTS.md (symlink or copy)")

    return added
