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
                ("[project]", name),
                ("<project>", name),
                ("project-name", name),  # pyproject.toml
                ("YYYY-MM-DD", today),
                ("[Brief description]", description),
                ("[One-line description]", description),
                ("Brief project description", description),  # pyproject.toml
            ]:
                content = content.replace(old, new)
            (project_dir / dest).write_text(content)

    # Symlink windsurfrules (legacy) and .windsurf/rules/
    (project_dir / ".windsurfrules").symlink_to("/opt/fabrik/windsurfrules")
    (project_dir / ".windsurf").mkdir(exist_ok=True)
    (project_dir / ".windsurf" / "rules").symlink_to("/opt/fabrik/.windsurf/rules")

    # AGENTS.md: symlink to master, fallback to copy
    _link_agents_md(project_dir)

    # Create .gitignore and .env.example
    (project_dir / ".gitignore").write_text(
        ".env\nvenv/\n__pycache__/\nlogs/\ndata/\n.tmp/\n.cache/\noutput/\n*.log\n.venv/\n"
    )
    (project_dir / ".env.example").write_text(
        f"# {name} Configuration\nDATABASE_URL=postgresql://localhost:5432/{name}_dev\nLOG_LEVEL=INFO\nPORT=8000\n"
    )

    # Create requirements.txt
    (project_dir / "requirements.txt").write_text(
        "fastapi>=0.109.0\nuvicorn[standard]>=0.27.0\npydantic>=2.0\npython-dotenv>=1.0.0\n"
    )

    # Create starter src/main.py
    (project_dir / "src" / "__init__.py").write_text("")
    (project_dir / "src" / "main.py").write_text(
        f'''"""Main entry point for {name}."""\nimport os\nfrom fastapi import FastAPI\n\napp = FastAPI(title="{name}")\n\n@app.get("/health")\nasync def health():\n    return {{"status": "ok", "service": "{name}"}}\n\n@app.get("/")\nasync def root():\n    return {{"message": "Welcome to {name}"}}\n'''
    )

    # Create basic test
    (project_dir / "tests" / "__init__.py").write_text("")
    (project_dir / "tests" / "test_health.py").write_text(
        '''"""Health endpoint tests."""\nfrom fastapi.testclient import TestClient\nfrom src.main import app\n\nclient = TestClient(app)\n\ndef test_health():\n    response = client.get("/health")\n    assert response.status_code == 200\n    assert response.json()["status"] == "ok"\n'''
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
