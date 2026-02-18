"""Project scaffolding - create new projects with full structure."""

import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

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

TEMPLATE_DIR = Path("/opt/fabrik/templates/scaffold")

TEMPLATE_MAP = {
    "docs/PROJECT_README_TEMPLATE.md": "README.md",
    "docs/CHANGELOG_TEMPLATE.md": "CHANGELOG.md",
    "docs/TASKS_TEMPLATE.md": "tasks.md",
    "docs/DOCS_INDEX_TEMPLATE.md": "docs/INDEX.md",
    "docs/QUICKSTART_TEMPLATE.md": "docs/QUICKSTART.md",
    "docs/CONFIGURATION_TEMPLATE.md": "docs/CONFIGURATION.md",
    "docs/TROUBLESHOOTING_TEMPLATE.md": "docs/TROUBLESHOOTING.md",
    "docs/BUSINESS_MODEL_TEMPLATE.md": "docs/BUSINESS_MODEL.md",
    # Phase docs for project roadmap (dashboard in tasks.md links here)
    "docs/PHASE_TEMPLATE.md": "docs/development/Phase1.md",
    # Note: PLANS.md and archive/README.md are generated inline, not from templates
    # Droid exec / Docker workflow files (AGENTS.md handled separately as symlink)
    "docker/Dockerfile.python": "Dockerfile",
    "docker/compose.yaml.template": "compose.yaml",
    # Python tooling config
    "python/pyproject.toml.template": "pyproject.toml",
}

REQUIRED_FILES = [
    "README.md",
    "CHANGELOG.md",
    "tasks.md",
    "docs/INDEX.md",
    "docs/QUICKSTART.md",
    "docs/CONFIGURATION.md",
    "docs/TROUBLESHOOTING.md",
    "Dockerfile",
    "compose.yaml",
]

DIRS = [
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
    "src",  # Source code directory
]

# Master AGENTS.md location
FABRIK_AGENTS_MD = Path("/opt/fabrik/AGENTS.md")


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
            link_path.write_text("# AGENTS.md\n\nSee /opt/fabrik/AGENTS.md for full briefing.\n")


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


def create_project(name: str, description: str, base: Path = Path("/opt")) -> Path:
    """Create a new project with full structure."""
    # Validate inputs
    _validate_project_name(name)

    project_dir = base / name
    if project_dir.exists():
        raise ValueError(f"Project already exists: {project_dir}")

    # Get package name before template replacement
    package_name = _get_package_name(name)

    # Create directories
    for d in DIRS:
        (project_dir / d).mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()

    # Copy templates
    for src, dest in TEMPLATE_MAP.items():
        src_path = TEMPLATE_DIR / src
        if src_path.exists():
            content = src_path.read_text()
            for old, new in [
                ("[Project Name]", name),
                ("<project>", name),
                ("project-name", name),  # pyproject.toml
                ("<package_name>", package_name),  # Package name for imports
                ("YYYY-MM-DD", today),
                ("[Brief description]", description),
                ("[One-line description]", description),
                ("Brief project description", description),  # pyproject.toml
            ]:
                content = content.replace(old, new)
            (project_dir / dest).write_text(content)

    # Symlink windsurfrules (legacy) and .windsurf/rules/ with existence checks
    fabrik_windsurfrules = Path("/opt/fabrik/windsurfrules")
    fabrik_windsurf_rules = Path("/opt/fabrik/.windsurf/rules")
    if fabrik_windsurfrules.exists():
        (project_dir / ".windsurfrules").symlink_to(fabrik_windsurfrules)
    if fabrik_windsurf_rules.exists():
        (project_dir / ".windsurf").mkdir(exist_ok=True)
        (project_dir / ".windsurf" / "rules").symlink_to(fabrik_windsurf_rules)

    # AGENTS.md: symlink to master, fallback to copy
    _link_agents_md(project_dir)

    # Create .gitignore and .env.example
    (project_dir / ".gitignore").write_text(
        ".env\nvenv/\n__pycache__/\nlogs/\ndata/\n.tmp/\n.cache/\noutput/\n*.log\n.venv/\n"
    )
    (project_dir / ".env.example").write_text(
        f"# {name} Configuration\n# Use env vars - never hardcode connection strings\nDATABASE_URL=postgresql://user:pass@localhost:5432/{name}_dev\nLOG_LEVEL=INFO\nPORT=8000\n"
    )

    # Create requirements.txt
    (project_dir / "requirements.txt").write_text(
        "fastapi>=0.109.0\nuvicorn[standard]>=0.27.0\npydantic>=2.0\npython-dotenv>=1.0.0\n"
    )

    # Create starter src/<package_name>/main.py with proper health check
    package_name = _get_package_name(name)
    package_dir = project_dir / "src" / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "__init__.py").write_text("")
    (package_dir / "main.py").write_text(
        f'''"""Main entry point for {name}."""\nimport os\nfrom fastapi import FastAPI\nfrom fastapi.responses import JSONResponse\n\napp = FastAPI(title="{name}")\n\n@app.get("/health")\nasync def health():\n    """Health check that validates actual dependencies."""\n    try:\n        # Test actual dependencies\n        import fastapi\n        import uvicorn\n        import pydantic\n\n        # Test environment variable loading\n        env_loaded = bool(os.getenv("PYTHONPATH"))\n\n        # Check if real dependencies are configured\n        has_real_deps = os.getenv("DATABASE_URL") is not None\n\n        checks = {{\n            "service": "{name}",\n            "status": "degraded" if not has_real_deps else "ok",\n            "dependencies": {{\n                "fastapi": "connected",\n                "uvicorn": "connected",\n                "pydantic": "connected"\n            }},\n            "environment": "loaded" if env_loaded else "missing",\n            "note": "No real dependencies configured - add database/redis checks for production"\n        }}\n        status_code = 200 if has_real_deps else 503\n        return JSONResponse(content=checks, status_code=status_code)\n    except Exception as e:\n        return JSONResponse(\n            content={{\n                "service": "{name}",\n                "status": "error",\n                "error": str(e)\n            }},\n            status_code=503\n        )\n\n@app.get("/")\nasync def root():\n    return {{"message": "Welcome to {name}"}}\n'''
    )

    # Create basic test
    (project_dir / "tests" / "__init__.py").write_text("")
    (project_dir / "tests" / "test_health.py").write_text(
        f'''"""Health endpoint tests."""\nfrom fastapi.testclient import TestClient\nfrom {package_name}.main import app\n\nclient = TestClient(app)\n\ndef test_health_degraded():\n    """Health check returns degraded when no real dependencies configured."""\n    response = client.get("/health")\n    # Returns 503 when no DATABASE_URL configured\n    assert response.status_code in [200, 503]\n    data = response.json()\n    assert "dependencies" in data\n    assert data["dependencies"]["fastapi"] == "connected"\n    assert data["dependencies"]["uvicorn"] == "connected"\n    assert data["dependencies"]["pydantic"] == "connected"\n'''
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

    # Git init
    subprocess.run(["git", "init", "-q"], cwd=project_dir, capture_output=True)

    # Install pre-commit config (after git init, before add)
    _install_pre_commit(project_dir)

    subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "Initial commit"], cwd=project_dir, capture_output=True
    )

    return project_dir


def validate_project(project_path: Path) -> tuple[list[str], list[str]]:
    """Validate project structure. Returns (present, missing) file lists."""
    present, missing = [], []
    for f in REQUIRED_FILES:
        if (project_path / f).exists():
            present.append(f)
        else:
            missing.append(f)
    return present, missing


def fix_project(project_path: Path, dry_run: bool = False) -> list[str]:
    """Add missing required files to a project. Returns list of files added."""
    from datetime import date

    project_path = Path(project_path)
    name = project_path.name
    today = date.today().isoformat()
    added: list[str] = []

    _, missing = validate_project(project_path)

    if not missing:
        return added

    for f in missing:
        dest_path = project_path / f

        if dry_run:
            added.append(f)
            continue

        # Create parent directories
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if we have a template
        template_name = None
        for src, dest in TEMPLATE_MAP.items():
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
            ]:
                content = content.replace(old, new)
            dest_path.write_text(content)
        else:
            # Create minimal placeholder
            dest_path.write_text(f"# {f}\n\n**Last Updated:** {today}\n\nTODO: Add content\n")

        added.append(f)

    # Ensure symlinks exist (skip in dry_run)
    if not dry_run:
        try:
            windsurfrules_link = project_path / ".windsurfrules"
            if not windsurfrules_link.exists() and not windsurfrules_link.is_symlink():
                windsurfrules_link.symlink_to("/opt/fabrik/windsurfrules")
                added.append(".windsurfrules (symlink)")

            agents_link = project_path / "AGENTS.md"
            if not agents_link.exists() and not agents_link.is_symlink():
                _link_agents_md(project_path)
                added.append("AGENTS.md (symlink or copy)")
        except OSError:
            # Fallback for AGENTS.md
            _link_agents_md(project_path)
            added.append("AGENTS.md (copy fallback)")
    else:
        # Check what would be added in dry_run
        windsurfrules_link = project_path / ".windsurfrules"
        if not windsurfrules_link.exists() and not windsurfrules_link.is_symlink():
            added.append(".windsurfrules (symlink)")
        agents_link = project_path / "AGENTS.md"
        if not agents_link.exists() and not agents_link.is_symlink():
            added.append("AGENTS.md (symlink)")

    return added
