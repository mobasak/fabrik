"""Project scaffolding - create new projects with full structure."""

import os
import re
import shutil
import subprocess
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

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

WORDPRESS_PRESETS = frozenset({"saas", "company", "content", "landing", "ecommerce"})

# Types whose type-specific missing files cannot be safely reconstructed
# by fix_project (they require the full scaffolder to be run correctly).
UNSUPPORTED_FIX_TYPES = frozenset(
    {
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
WORDPRESS_TEMPLATE_DIR = FABRIK_ROOT / "templates" / "wordpress"
FILE_API_TEMPLATE_DIR = FABRIK_ROOT / "templates" / "file-api"
FILE_WORKER_TEMPLATE_DIR = FABRIK_ROOT / "templates" / "file-worker"
SAAS_SKELETON_DIR = FABRIK_ROOT / "templates" / "saas-skeleton"

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
    "node-api": _SHARED_REQUIRED_FILES + ["Dockerfile", "package.json"],
    "file-api": _SHARED_REQUIRED_FILES + ["Dockerfile", "package.json", "src/index.js"],
    "file-worker": _SHARED_REQUIRED_FILES + ["Dockerfile", "requirements.txt", "worker/main.py"],
    "wordpress": _SHARED_REQUIRED_FILES
    + ["compose.yaml.j2", "compose-coolify.yaml.j2", ".env.example"],
    "docusaurus": _SHARED_REQUIRED_FILES + ["package.json", "docs/intro.md"],
    "chrome-extension": _SHARED_REQUIRED_FILES + ["package.json", "src/background.ts"],
    "mobile-app": _SHARED_REQUIRED_FILES + ["package.json", "src/App.tsx"],
    "desktop-app": _SHARED_REQUIRED_FILES + ["package.json", "src/main.ts"],
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


_SAAS_SKIP_FILES = {"AGENTS.md", "pyproject.toml", "requirements.txt"}


def _scaffold_saas_skeleton(
    project_dir: Path, name: str, description: str, **kwargs: object
) -> None:
    """Copy the saas-skeleton template into the project directory, patching names."""
    for src in SAAS_SKELETON_DIR.rglob("*"):
        if not src.is_file():
            continue

        rel = src.relative_to(SAAS_SKELETON_DIR)

        # Skip excluded filenames
        if src.name in _SAAS_SKIP_FILES:
            continue

        dest = project_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            content = src.read_text(encoding="utf-8")
            content = content.replace("saas-skeleton", name)
            dest.write_text(content, encoding="utf-8")
        except UnicodeDecodeError:
            shutil.copy2(src, dest)


def _scaffold_node_api(project_dir: Path, name: str, description: str, **kwargs: object) -> None:
    """Create Node API-specific project structure."""
    import json

    # a) Create src/ directory
    (project_dir / "src").mkdir(parents=True, exist_ok=True)

    # b) Copy and patch Dockerfile.node -> Dockerfile
    dockerfile_src = TEMPLATE_DIR / "docker" / "Dockerfile.node"
    if dockerfile_src.exists():
        content = dockerfile_src.read_text()
        content = content.replace("PROJECT_NAME", name)
        content = content.replace("dist/index.js", "src/index.js")
        content = content.replace("./dist", "./src")
        # Replace `npm ci` with `npm install` — no lockfile is generated during
        # scaffold, so `npm ci` would fail on a fresh docker build.
        content = content.replace("RUN npm ci", "RUN npm install")
        (project_dir / "Dockerfile").write_text(content)

    # c) Copy and patch Makefile.node -> Makefile
    makefile_src = TEMPLATE_DIR / "docker" / "Makefile.node"
    if makefile_src.exists():
        content = makefile_src.read_text()
        content = content.replace("myproject", name)
        (project_dir / "Makefile").write_text(content)

    # d) Generate package.json inline
    package_json = {
        "name": name,
        "version": "0.1.0",
        "description": description,
        "main": "src/index.js",
        "scripts": {
            "start": "node src/index.js",
            "dev": "node --watch src/index.js",
            "test": "node --test",
            "lint": "echo 'No linter configured'",
        },
    }
    (project_dir / "package.json").write_text(json.dumps(package_json, indent=2) + "\n")

    # e) Generate src/index.js inline
    (project_dir / "src" / "index.js").write_text(
        f"""'use strict';

const http = require('http');

const PORT = process.env.PORT || 3000;

const server = http.createServer((req, res) => {{
  if (req.method === 'GET' && req.url === '/health') {{
    res.writeHead(200, {{ 'Content-Type': 'application/json' }});
    res.end(JSON.stringify({{ service: '{name}', status: 'ok' }}));
    return;
  }}

  res.writeHead(200, {{ 'Content-Type': 'application/json' }});
  res.end(JSON.stringify({{ message: 'Welcome to {name}' }}));
}});

server.listen(PORT, () => {{
  console.log(`{name} listening on port ${{PORT}}`);
}});
"""
    )

    # f) Overwrite .env.example with Node-appropriate content
    (project_dir / ".env.example").write_text(
        f"# {name} Configuration\nPORT=3000\nNODE_ENV=development\nLOG_LEVEL=info\n"
    )

    # g) Overwrite .gitignore with Node-appropriate content
    (project_dir / ".gitignore").write_text(
        "node_modules/\ndist/\n.env\nlogs/\ndata/\n.tmp/\n.cache/\noutput/\n*.log\n"
        ".droid/kilo_usage.jsonl\n.droid/reviews/\n.droid/kilo_models_cache.json\n.droid/.kilo_cache_last_refresh\n"
    )


def _scaffold_file_api(project_dir: Path, name: str, description: str, **kwargs: object) -> None:
    """Create File API-specific project structure."""
    import json

    # a) Create src/ directory
    (project_dir / "src").mkdir(parents=True, exist_ok=True)

    # b) Copy index.js verbatim from file-api template
    src_index = FILE_API_TEMPLATE_DIR / "src" / "index.js"
    if src_index.exists():
        shutil.copy2(src_index, project_dir / "src" / "index.js")

    # c) Copy and patch Dockerfile.node -> Dockerfile
    dockerfile_src = TEMPLATE_DIR / "docker" / "Dockerfile.node"
    if dockerfile_src.exists():
        content = dockerfile_src.read_text()
        content = content.replace("PROJECT_NAME", name)
        content = content.replace("dist/index.js", "src/index.js")
        content = content.replace("./dist", "./src")
        content = content.replace("RUN npm ci", "RUN npm install")
        (project_dir / "Dockerfile").write_text(content)

    # d) Copy and patch Makefile.node -> Makefile
    makefile_src = TEMPLATE_DIR / "docker" / "Makefile.node"
    if makefile_src.exists():
        content = makefile_src.read_text()
        content = content.replace("myproject", name)
        (project_dir / "Makefile").write_text(content)

    # e) Generate package.json inline with R2/Supabase dependencies
    package_json = {
        "name": name,
        "version": "0.1.0",
        "description": description,
        "main": "src/index.js",
        "scripts": {
            "start": "node src/index.js",
            "dev": "node --watch src/index.js",
            "test": "node --test",
            "lint": "echo 'No linter configured'",
        },
        "dependencies": {
            "express": "^4.18.2",
            "cors": "^2.8.5",
            "@supabase/supabase-js": "^2.38.0",
            "@aws-sdk/client-s3": "^3.450.0",
            "@aws-sdk/s3-request-presigner": "^3.450.0",
            "uuid": "^9.0.1",
        },
    }
    (project_dir / "package.json").write_text(json.dumps(package_json, indent=2) + "\n")

    # f) Overwrite .env.example with R2/Supabase-specific vars
    (project_dir / ".env.example").write_text(
        f"""# {name} Configuration
PORT=3000
NODE_ENV=development
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
R2_ENDPOINT=https://your-account.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your-access-key-id
R2_SECRET_ACCESS_KEY=your-secret-access-key
R2_BUCKET=your-bucket-name
MAX_FILE_SIZE_MB=100
ALLOWED_CONTENT_TYPES=application/pdf,audio/mpeg
UPLOAD_URL_EXPIRY_SECONDS=3600
DOWNLOAD_URL_EXPIRY_SECONDS=3600
"""
    )

    # g) Overwrite .gitignore with Node-appropriate content
    (project_dir / ".gitignore").write_text(
        "node_modules/\ndist/\n.env\nlogs/\ndata/\n.tmp/\n.cache/\noutput/\n*.log\n"
        ".droid/kilo_usage.jsonl\n.droid/reviews/\n.droid/kilo_models_cache.json\n.droid/.kilo_cache_last_refresh\n"
    )


def _scaffold_file_worker(project_dir: Path, name: str, description: str, **kwargs: object) -> None:
    """Create File Worker-specific project structure."""
    # a) Create worker/ directory
    (project_dir / "worker").mkdir(parents=True, exist_ok=True)

    # b) Copy main.py verbatim from file-worker template
    src_main = FILE_WORKER_TEMPLATE_DIR / "worker" / "main.py"
    if src_main.exists():
        shutil.copy2(src_main, project_dir / "worker" / "main.py")

    # c) Copy and patch Dockerfile.python -> Dockerfile
    dockerfile_src = TEMPLATE_DIR / "docker" / "Dockerfile.python"
    if dockerfile_src.exists():
        content = dockerfile_src.read_text()
        content = content.replace("myproject", name)
        content = content.replace("PROJECT_NAME", name)
        # Replace CMD: perform explicit line substitution to handle both the raw
        # template token form (<package_name>) and any already-substituted variant.
        # We iterate lines and replace whichever CMD line is present.
        lines = content.splitlines(keepends=True)
        new_lines = []
        for line in lines:
            if line.startswith("CMD ") and "main:app" in line:
                new_lines.append('CMD ["python", "worker/main.py"]\n')
            else:
                new_lines.append(line)
        content = "".join(new_lines)
        # Replace HEALTHCHECK to check process instead of HTTP
        content = re.sub(
            r"HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \\\n"
            r"    CMD curl -f http://localhost:\$\{PORT:-8000\}/health \|\| exit 1",
            "HEALTHCHECK --interval=30s --timeout=5s --retries=3 \\\n"
            '    CMD pgrep -f "python worker/main.py" || exit 1',
            content,
        )
        # Replace PYTHONPATH
        content = content.replace("ENV PYTHONPATH=/app/src", "ENV PYTHONPATH=/app")
        (project_dir / "Dockerfile").write_text(content)

    # d) Copy and patch Makefile.python -> Makefile
    makefile_src = TEMPLATE_DIR / "docker" / "Makefile.python"
    if makefile_src.exists():
        content = makefile_src.read_text()
        content = content.replace("myproject", name)
        # Replace the dev target body: match any uvicorn invocation on the line
        # following the "dev:" target and replace it with the worker command.
        # This handles the actual template command regardless of exact arguments.
        lines = content.splitlines(keepends=True)
        new_lines = []
        in_dev_target = False
        for line in lines:
            stripped = line.strip()
            if stripped == "dev:":
                in_dev_target = True
                new_lines.append(line)
            elif in_dev_target and line.startswith("\t") and "uvicorn" in line:
                new_lines.append("\tpython worker/main.py\n")
                in_dev_target = False
            else:
                in_dev_target = False
                new_lines.append(line)
        content = "".join(new_lines)
        (project_dir / "Makefile").write_text(content)

    # e) Generate requirements.txt inline with worker dependencies
    (project_dir / "requirements.txt").write_text(
        """boto3>=1.35.0
structlog>=24.4.0
supabase>=2.9.0
pypdf>=4.3.0
"""
    )

    # f) Overwrite .env.example with worker-specific vars
    (project_dir / ".env.example").write_text(
        f"""# {name} Configuration
WORKER_ID=worker-1
JOB_TYPES=transcribe,ocr,extract_text
POLL_INTERVAL=5
MAX_CONCURRENT_JOBS=2
MAX_PROCESSING_TIME=3600
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
R2_ENDPOINT=https://your-account.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your-access-key-id
R2_SECRET_ACCESS_KEY=your-secret-access-key
R2_BUCKET=your-bucket-name
"""
    )

    # g) Overwrite .gitignore with Python-appropriate content
    (project_dir / ".gitignore").write_text(
        ".env\nvenv/\n__pycache__/\nlogs/\ndata/\n.tmp/\n.cache/\noutput/\n*.log\n.venv/\n"
        ".droid/kilo_usage.jsonl\n.droid/reviews/\n.droid/kilo_models_cache.json\n.droid/.kilo_cache_last_refresh\n"
    )


def _scaffold_wordpress(project_dir: Path, name: str, description: str, **kwargs: object) -> None:
    """Create WordPress-specific project structure."""
    # a) Extract and validate preset
    preset = kwargs.get("preset") or "saas"
    if preset not in WORDPRESS_PRESETS:
        raise ValueError(
            f"Invalid WordPress preset: {preset}. "
            f"Valid options: {', '.join(sorted(WORDPRESS_PRESETS))}"
        )

    # b) Create WordPress-specific directories
    (project_dir / "plugins").mkdir(parents=True, exist_ok=True)
    (project_dir / "themes").mkdir(parents=True, exist_ok=True)
    (project_dir / "backup").mkdir(parents=True, exist_ok=True)

    # c) Recursively copy all files from base template, preserving relative paths
    base_dir = WORDPRESS_TEMPLATE_DIR / "base"
    if base_dir.exists():
        for src_file in base_dir.rglob("*"):
            if not src_file.is_file():
                continue
            rel = src_file.relative_to(base_dir)
            dest_file = project_dir / rel
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dest_file)
        # Re-apply executable permission to backup script after copy
        backup_sh = project_dir / "backup" / "backup.sh"
        if backup_sh.exists():
            os.chmod(backup_sh, 0o755)  # noqa: S103  # nosec B103

    # d) Copy the chosen preset YAML
    preset_src = WORDPRESS_TEMPLATE_DIR / "presets" / f"{preset}.yaml"
    if preset_src.exists():
        shutil.copy2(preset_src, project_dir / "config" / "preset.yaml")

    # e) Overwrite .env.example with WordPress/MariaDB/R2 placeholder vars
    name_underscored = name.replace("-", "_")
    (project_dir / ".env.example").write_text(
        f"""# WordPress: {name}
DB_NAME={name_underscored}_wp
DB_USER={name_underscored}_user
DB_PASSWORD=CHANGE_ME
DB_ROOT_PASSWORD=CHANGE_ME
WORDPRESS_DEBUG=false
SITE_URL=https://example.com
SITE_NAME={name}
R2_ENDPOINT=https://your-account.r2.cloudflarestorage.com
R2_ACCESS_KEY=your-r2-access-key
R2_SECRET_KEY=your-r2-secret-key
R2_BUCKET=fabrik-backups
"""
    )

    # f) Overwrite .gitignore with WordPress-appropriate content
    (project_dir / ".gitignore").write_text(
        """.env
wp-content/uploads/
wp-content/upgrade/
logs/
data/
.tmp/
.cache/
*.log
.droid/kilo_usage.jsonl
.droid/reviews/
.droid/kilo_models_cache.json
.droid/.kilo_cache_last_refresh
"""
    )


def _scaffold_generic_ts(
    project_dir: Path, name: str, description: str, type_name: str, **kwargs: object
) -> None:
    """Create generic TypeScript/Node project structure for docusaurus, chrome-extension, mobile-app, desktop-app."""
    import json

    # Type-specific configurations
    # has_docker: only set True when the type has a runnable Node entrypoint
    #   that the Dockerfile.node template can target directly (src/index.js).
    #   - docusaurus: serves via `docusaurus start`; no src/index.js entrypoint.
    #   - desktop-app: uses Electron (src/main.ts); Electron apps do not run in
    #     a standard Node HTTP container and have no src/index.js entrypoint.
    #   - chrome-extension / mobile-app: no server; Docker is not applicable.
    type_configs: dict[str, dict[str, Any]] = {
        "docusaurus": {
            "entry_dir": "docs/",
            "entry_file": "docs/intro.md",
            "has_docker": False,
            "scripts": {
                "start": "docusaurus start",
                "build": "docusaurus build",
                "serve": "docusaurus serve",
            },
        },
        "chrome-extension": {
            "entry_dir": "src/",
            "entry_file": "src/background.ts",
            "has_docker": False,
            "scripts": {"build": "tsc", "test": "echo 'No tests configured'"},
        },
        "mobile-app": {
            "entry_dir": "src/",
            "entry_file": "src/App.tsx",
            "has_docker": False,
            "scripts": {
                "start": "expo start",
                "android": "expo start --android",
                "ios": "expo start --ios",
                "test": "jest",
            },
        },
        "desktop-app": {
            "entry_dir": "src/",
            "entry_file": "src/main.ts",
            "has_docker": False,
            "scripts": {"start": "electron .", "build": "electron-builder", "test": "jest"},
        },
    }

    if type_name not in type_configs:
        raise ValueError(f"Unknown generic TS type: {type_name}")

    config = type_configs[type_name]

    # a) Create the entry directory
    entry_dir: str = config["entry_dir"]  # type: ignore[assignment]
    (project_dir / entry_dir).mkdir(parents=True, exist_ok=True)

    # b) Write minimal entry file
    entry_file: str = config["entry_file"]  # type: ignore[assignment]
    entry_file_path = project_dir / entry_file
    if type_name == "docusaurus":
        entry_file_path.write_text(
            """# Introduction

Welcome to the documentation for this project.

## Getting Started

Add your content here.
"""
        )
    elif type_name == "chrome-extension":
        entry_file_path.write_text(
            """chrome.runtime.onInstalled.addListener(() => {
  console.log('Extension installed');
});
"""
        )
    elif type_name == "mobile-app":
        entry_file_path.write_text(
            """import React from 'react';
import { View, Text } from 'react-native';

export default function App() {
  return (
    <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
      <Text>Welcome to Mobile App</Text>
    </View>
  );
}
"""
        )
    elif type_name == "desktop-app":
        entry_file_path.write_text(
            """const { app, BrowserWindow } = require('electron');

function createWindow() {
  const win = new BrowserWindow({
    width: 800,
    height: 600,
  });
  win.loadFile('index.html');
}

app.whenReady().then(createWindow);
"""
        )

    # c) Generate package.json inline
    package_json = {
        "name": name,
        "version": "0.1.0",
        "description": description,
        "scripts": config["scripts"],
    }
    (project_dir / "package.json").write_text(json.dumps(package_json, indent=2) + "\n")

    # d) If has_docker, copy and patch Dockerfile + Makefile
    if config["has_docker"]:
        dockerfile_src = TEMPLATE_DIR / "docker" / "Dockerfile.node"
        if dockerfile_src.exists():
            content = dockerfile_src.read_text()
            content = content.replace("PROJECT_NAME", name)
            content = content.replace("dist/index.js", "src/index.js")
            content = content.replace("./dist", "./src")
            content = content.replace("RUN npm ci", "RUN npm install")
            (project_dir / "Dockerfile").write_text(content)

        makefile_src = TEMPLATE_DIR / "docker" / "Makefile.node"
        if makefile_src.exists():
            content = makefile_src.read_text()
            content = content.replace("myproject", name)
            (project_dir / "Makefile").write_text(content)

    # e) Overwrite .env.example with minimal Node-style env
    (project_dir / ".env.example").write_text(f"# {name} Configuration\nNODE_ENV=development\n")

    # f) Overwrite .gitignore with Node-appropriate content
    (project_dir / ".gitignore").write_text(
        "node_modules/\ndist/\n.env\nlogs/\ndata/\n.tmp/\n.cache/\noutput/\n*.log\n"
        ".droid/kilo_usage.jsonl\n.droid/reviews/\n.droid/kilo_models_cache.json\n.droid/.kilo_cache_last_refresh\n"
    )


# Dispatch table mapping project types to their scaffolder functions.
_TYPE_SCAFFOLDERS: dict[str, Callable[..., None]] = {
    "python-api": _scaffold_python_api,
    "saas-skeleton": _scaffold_saas_skeleton,
    "node-api": _scaffold_node_api,
    "file-api": _scaffold_file_api,
    "file-worker": _scaffold_file_worker,
    "wordpress": _scaffold_wordpress,
    "docusaurus": lambda pd, n, d, **kw: _scaffold_generic_ts(pd, n, d, "docusaurus", **kw),
    "chrome-extension": lambda pd, n, d, **kw: _scaffold_generic_ts(
        pd, n, d, "chrome-extension", **kw
    ),
    "mobile-app": lambda pd, n, d, **kw: _scaffold_generic_ts(pd, n, d, "mobile-app", **kw),
    "desktop-app": lambda pd, n, d, **kw: _scaffold_generic_ts(pd, n, d, "desktop-app", **kw),
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

    # Shared required file set for fast membership test
    shared_required_set = set(_SHARED_REQUIRED_FILES)

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
                ("<project>", name),
                ("YYYY-MM-DD", today),
                ("[Brief description]", f"{name} project"),
                ("[One-line description]", f"{name} project"),
                ("myproject", name),  # Makefile
            ]:
                content = content.replace(old, new)
            dest_path.write_text(content)
        elif project_type in UNSUPPORTED_FIX_TYPES and f not in shared_required_set:
            # Type-specific artifact that fix_project cannot safely reconstruct.
            # Report as missing (return value) but do NOT write a placeholder that
            # would silently mask a broken scaffold.
            added.append(f"[unsupported-fix] {f}")
            continue
        else:
            # Create minimal placeholder for shared docs
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
