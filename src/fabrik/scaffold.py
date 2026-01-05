"""Project scaffolding - create new projects with full structure."""

import subprocess
from datetime import date
from pathlib import Path

TEMPLATE_DIR = Path("/opt/fabrik/templates/scaffold")

TEMPLATE_MAP = {
    "docs/PROJECT_README_TEMPLATE.md": "README.md",
    "docs/CHANGELOG_TEMPLATE.md": "CHANGELOG.md",
    "docs/TASKS_TEMPLATE.md": "tasks.md",
    "docs/DOCS_INDEX_TEMPLATE.md": "docs/README.md",
    "docs/QUICKSTART_TEMPLATE.md": "docs/QUICKSTART.md",
    "docs/CONFIGURATION_TEMPLATE.md": "docs/CONFIGURATION.md",
    "docs/TROUBLESHOOTING_TEMPLATE.md": "docs/TROUBLESHOOTING.md",
    "docs/BUSINESS_MODEL_TEMPLATE.md": "docs/BUSINESS_MODEL.md",
    # Droid exec / Docker workflow files
    "AGENTS.md": "AGENTS.md",
    "docker/Dockerfile.python": "Dockerfile",
    "docker/compose.yaml.template": "compose.yaml",
}

REQUIRED_FILES = [
    "README.md",
    "CHANGELOG.md",
    "tasks.md",
    "docs/README.md",
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


def create_project(name: str, description: str, base: Path = Path("/opt")) -> Path:
    """Create a new project with full structure."""
    project_dir = base / name
    if project_dir.exists():
        raise ValueError(f"Project already exists: {project_dir}")
    if name.startswith("_"):
        raise ValueError("Project name cannot start with underscore")

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
                ("YYYY-MM-DD", today),
                ("[Brief description]", description),
                ("[One-line description]", description),
            ]:
                content = content.replace(old, new)
            (project_dir / dest).write_text(content)

    # Symlink windsurfrules
    (project_dir / ".windsurfrules").symlink_to("/opt/fabrik/windsurfrules")

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
    subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "Initial commit"], cwd=project_dir, capture_output=True
    )

    return project_dir


def validate_project(project_path: Path) -> tuple[list, list]:
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
    added = []

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
                agents_link.symlink_to("/opt/fabrik/AGENTS.md")
                added.append("AGENTS.md (symlink)")
        except OSError:
            # Log but don't fail - symlinks are nice-to-have
            pass
    else:
        # Check what would be added in dry_run
        windsurfrules_link = project_path / ".windsurfrules"
        if not windsurfrules_link.exists() and not windsurfrules_link.is_symlink():
            added.append(".windsurfrules (symlink)")
        agents_link = project_path / "AGENTS.md"
        if not agents_link.exists() and not agents_link.is_symlink():
            added.append("AGENTS.md (symlink)")

    return added
