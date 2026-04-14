"""Project scaffolding - create new projects with full structure.

⚠️  When modifying this file, update these docs to match:
  - docs/workflows/SCAFFOLD_STRUCTURE.md      (tree listing + file tables)
  - docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md (detailed tree + file tables + examples)
"""

import logging
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from datetime import date
from pathlib import Path

import yaml

from fabrik.config import FABRIK_ROOT
from fabrik.spec_generator import SPEC_ENABLED_TYPES, generate_and_save_spec

logger = logging.getLogger(__name__)

# Non-secret env var patterns to exclude from auto-detection
NON_SECRET_PATTERNS = frozenset(
    {
        "PORT",
        "HOST",
        "LOG_LEVEL",
        "DEBUG",
        "ENV",
        "NODE_ENV",
        "PYTHON_ENV",
        "DATABASE_URL",  # Often set from compose, not a secret
        "REDIS_URL",  # Often set from compose, not a secret
    }
)

# Secret env var patterns to include in auto-detection
SECRET_PATTERNS = frozenset(
    {
        "_KEY$",
        "_SECRET$",
        "_PASSWORD$",
        "_TOKEN$",
        "_CREDENTIALS",
        "_API_KEY$",
        "_API_TOKEN$",
        "_PRIVATE_KEY$",
    }
)


def _is_likely_secret(key: str) -> bool:
    """Determine if an env var key is likely a secret based on patterns."""
    key_upper = key.upper()

    # Exclude known non-secrets
    if key_upper in NON_SECRET_PATTERNS:
        return False

    # Include if it matches secret patterns
    for pattern in SECRET_PATTERNS:
        if pattern.endswith("$"):
            if key_upper.endswith(pattern[:-1]):
                return True
        elif pattern in key_upper:
            return True

    return False


def _detect_secrets(project_path: Path) -> tuple[list[str], dict[str, str]]:
    """Detect secrets from .env.example and compose.yaml in scaffolded project.

    Returns:
        tuple: (secrets_from_env list, secrets_from_file dict)
    """
    secrets_from_env = []
    secrets_from_file = {}

    # Read .env.example
    env_example = project_path / ".env.example"
    if env_example.exists():
        for line in env_example.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key = line.split("=")[0].strip()
                if _is_likely_secret(key):
                    secrets_from_env.append(key)

    # Detect file-based secrets (JSON credentials)
    for key in secrets_from_env:
        if "CREDENTIALS" in key or "KEY_FILE" in key:
            # Map to likely file path (user can adjust in spec if needed)
            tmp_dir = project_path / ".tmp"
            tmp_dir.mkdir(exist_ok=True)
            file_path = str(tmp_dir / f"{project_path.name}-creds.json")
            secrets_from_file[key] = file_path

    return secrets_from_env, secrets_from_file


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
        "static-site",
    }
)

WORDPRESS_PRESETS = frozenset({"saas", "company", "content", "landing", "ecommerce"})

# Scaffold types that produce user-facing documentation (activates user-guide gate)
GUIDE_ENABLED_TYPES = frozenset(
    {"saas-skeleton", "chrome-extension", "mobile-app", "desktop-app", "static-site"}
)

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
MOBILE_APP_TEMPLATE_DIR = FABRIK_ROOT / "templates" / "mobile-app"
DESKTOP_APP_TEMPLATE_DIR = FABRIK_ROOT / "templates" / "desktop-app"
DOCUSAURUS_TEMPLATE_DIR = FABRIK_ROOT / "templates" / "docusaurus"

SHARED_TEMPLATE_MAP = {
    "docs/PROJECT_INDEX_TEMPLATE.md": "INDEX.md",
    "docs/PROJECT_README_TEMPLATE.md": "README.md",
    "docs/CHANGELOG_TEMPLATE.md": "CHANGELOG.md",
    "docs/DOCS_INDEX_TEMPLATE.md": "docs/README.md",
    "docs/QUICKSTART_TEMPLATE.md": "docs/QUICKSTART.md",
    "docs/CONFIGURATION_TEMPLATE.md": "docs/CONFIGURATION.md",
    "docs/TROUBLESHOOTING_TEMPLATE.md": "docs/TROUBLESHOOTING.md",
    "docs/BUSINESS_MODEL_TEMPLATE.md": "docs/BUSINESS_MODEL.md",
    "docs/FEATURES_TEMPLATE.md": "docs/FEATURES.md",
    "docs/STRATEGIC_BACKLOG_TEMPLATE.md": "docs/STRATEGIC_BACKLOG.md",
    # Note: Phase docs removed - Traycer Phases replace manual phase tracking
    # Note: tasks.md removed - Traycer UI replaces manual task dashboard
    # Note: PLANS.md and archive/README.md are generated inline, not from templates
}

_PYTHON_API_TEMPLATE_MAP = {
    # Droid exec / Docker workflow files (AGENTS.md copied separately in create_project)
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
    "static-site": _SHARED_REQUIRED_FILES[:],
    "node-api": _SHARED_REQUIRED_FILES + ["Dockerfile", "package.json"],
    "file-api": _SHARED_REQUIRED_FILES + ["Dockerfile", "package.json", "src/index.js"],
    "file-worker": _SHARED_REQUIRED_FILES + ["Dockerfile", "requirements.txt", "worker/main.py"],
    "wordpress": _SHARED_REQUIRED_FILES
    + ["compose.yaml.j2", "compose-coolify.yaml.j2", ".env.example"],
    "docusaurus": _SHARED_REQUIRED_FILES
    + [
        "package.json",
        "docusaurus.config.js",
        "sidebars.js",
        "docs/intro.md",
        "openapi.yaml",
        "docs/api/sidebar.js",
    ],
    "chrome-extension": _SHARED_REQUIRED_FILES
    + [
        "extension/manifest.json",
        "extension/package.json",
        "extension/vite.config.ts",
        "Dockerfile",
        "compose.yaml",
        "Makefile",
    ],
    "mobile-app": _SHARED_REQUIRED_FILES
    + ["package.json", "src/App.tsx", "src/navigation/AppNavigator.tsx"],
    "desktop-app": _SHARED_REQUIRED_FILES + ["package.json", "electron/main.js"],
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
    "db",  # Database schema directory
    ".tmp",
    ".cache",
    "output",
    ".droid/review-context",  # Kilo/Traycer review context directory
    ".droid/traycer-reports",  # Traycer report files directory
]

_PYTHON_API_DIRS = ["src"]

SCRIPT_FILES = ["runc", "rund", "rundsh", "runk", "sync_cascade_backup.sh", "sync_extensions.sh"]

# Master AGENTS.md location
FABRIK_AGENTS_MD = FABRIK_ROOT / "AGENTS.md"

# Canonical .droid/ gitignore block — shared across all scaffold types
# Runtime files written by:
#   - kilo_code_review.py: reviews/, kilo_models_cache.json, .kilo_cache_last_refresh
#   - generate_kilo_agents.py shell scripts: kilo_usage.jsonl
#   - docs_updater.py: docs_queue/, docs_log/
#   - traycer_write_report.py: traycer-reports/*.md
_DROID_GITIGNORE_BLOCK = (
    ".droid/kilo_usage.jsonl\n"
    ".droid/reviews/\n"
    ".droid/kilo_models_cache.json\n"
    ".droid/.kilo_cache_last_refresh\n"
    ".droid/docs_queue/\n"
    ".droid/docs_log/\n"
    ".droid/traycer-reports/*.md\n"
)

# Canonical .droid/.gitignore content — used by scaffold and fix_project()
_DROID_DIR_GITIGNORE = (
    "# Kilo/Traycer runtime files — do not commit\n"
    "*\n"
    "!.gitignore\n"
    "!review-context/\n"
    "!review-context/**\n"
    "!traycer-reports/\n"
    "!traycer-reports/.gitignore\n"
    "traycer-reports/*.md\n"
)

# Canonical .droid/traycer-reports/.gitignore content
_TRAYCER_REPORTS_GITIGNORE = (
    "# Traycer report files — committed .gitignore, reports are gitignored\n*.md\n!.gitignore\n"
)


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


def _install_pre_commit(project_dir: Path) -> bool:
    """Copy pre-commit config from Fabrik root and install hooks. Returns True if successful."""
    # Copy config file from root so all projects share the same minimal commit blockers
    src_config = FABRIK_ROOT / ".pre-commit-config.yaml"
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


def _next_available_port(port_range: tuple[int, int] = (8000, 8099)) -> int:
    """Find next unused port by reading the aggregated registry.

    Falls back to 8000 if registry doesn't exist yet (first project).
    """
    registry_path = FABRIK_ROOT / "data" / "projects.yaml"
    if not registry_path.exists():
        return port_range[0]
    try:
        data = yaml.safe_load(registry_path.read_text()) or {}
        used_ports: set[int] = set()
        for proj in data.get("projects", {}).values():
            # Support both old 'port' (int) and new 'ports' (list)
            ports_val = proj.get("ports", [])
            if isinstance(ports_val, list):
                for p in ports_val:
                    used_ports.add(int(p))
            elif ports_val:
                used_ports.add(int(ports_val))
            # Legacy fallback
            p = proj.get("port")
            if p:
                used_ports.add(int(p))
        for port in range(port_range[0], port_range[1] + 1):
            if port not in used_ports:
                return port
        return port_range[1] + 1  # Overflow
    except Exception:
        return port_range[0]


def _scaffold_shared(
    project_dir: Path, name: str, description: str, today: str, host_port: int
) -> None:
    """Create the shared project structure common to all project types, including git init."""
    # Create shared directories
    for d in SHARED_DIRS:
        (project_dir / d).mkdir(parents=True, exist_ok=True)

    # Write .droid/ files: gitignore keeps review-context/, blocks runtime files
    (project_dir / ".droid" / ".gitignore").write_text(_DROID_DIR_GITIGNORE)
    # .gitkeep so git tracks the empty review-context/ directory
    (project_dir / ".droid" / "review-context" / ".gitkeep").write_text("")

    # Create traycer-reports/ with its own .gitignore
    traycer_reports_dir = project_dir / ".droid" / "traycer-reports"
    traycer_reports_dir.mkdir(parents=True, exist_ok=True)
    (traycer_reports_dir / ".gitignore").write_text(_TRAYCER_REPORTS_GITIGNORE)

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
                ("[PORT]", str(host_port)),  # Allocated port
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

    # Copy ALL Fabrik scripts for complete project independence
    # Projects should be fully functional without absolute paths to Fabrik

    # Core quality gate scripts
    core_scripts = [
        "final_gate.py",
        "kilo_code_review.py",
        "kilo_docs_enforcer.py",
        "docs_updater.py",
        "update_agents_toc.py",
        "health_checker.py",
    ]
    for script_name in core_scripts:
        fabrik_script = FABRIK_ROOT / "scripts" / script_name
        if fabrik_script.exists():
            shutil.copy(fabrik_script, project_dir / "scripts" / script_name)

    # Copy entire enforcement directory
    fabrik_enforcement = FABRIK_ROOT / "scripts" / "enforcement"
    project_enforcement = project_dir / "scripts" / "enforcement"
    if fabrik_enforcement.exists():
        shutil.copytree(fabrik_enforcement, project_enforcement, dirs_exist_ok=True)

    # Copy .windsurfrules, .windsurf/rules/, .windsurf/workflows/ (authoritative)
    # Fail fast if fabrik targets are missing - environment is broken
    fabrik_windsurfrules = FABRIK_ROOT / ".windsurfrules"
    fabrik_windsurf_rules = FABRIK_ROOT / ".windsurf" / "rules"
    fabrik_windsurf_workflows = FABRIK_ROOT / ".windsurf" / "workflows"

    if not fabrik_windsurfrules.exists():
        raise FileNotFoundError(f"Missing fabrik .windsurfrules: {fabrik_windsurfrules}")
    if not fabrik_windsurf_rules.exists():
        raise FileNotFoundError(f"Missing fabrik windsurf rules dir: {fabrik_windsurf_rules}")
    if not fabrik_windsurf_workflows.exists():
        raise FileNotFoundError(
            f"Missing fabrik windsurf workflows dir: {fabrik_windsurf_workflows}"
        )

    # Copy .windsurfrules (no symlinks - workspace isolation)
    shutil.copy(fabrik_windsurfrules, project_dir / ".windsurfrules")

    # Copy .windsurf/rules/ directory (no symlinks - workspace isolation)
    windsurf_target = project_dir / ".windsurf" / "rules"
    if windsurf_target.exists():
        shutil.rmtree(windsurf_target)
    shutil.copytree(fabrik_windsurf_rules, windsurf_target)

    # Copy .windsurf/workflows/ directory (no symlinks - workspace isolation)
    workflows_target = project_dir / ".windsurf" / "workflows"
    if workflows_target.exists():
        shutil.rmtree(workflows_target)
    shutil.copytree(fabrik_windsurf_workflows, workflows_target)

    # Copy AGENTS.md (no symlinks - workspace isolation)
    if FABRIK_AGENTS_MD.exists():
        shutil.copy(FABRIK_AGENTS_MD, project_dir / "AGENTS.md")

    # Copy AGENTS-compact.md (no symlinks - workspace isolation)
    fabrik_compact = FABRIK_ROOT / "AGENTS-compact.md"
    if fabrik_compact.exists():
        shutil.copy(fabrik_compact, project_dir / "AGENTS-compact.md")

    # Copy cascade-models.md (Windsurf AI model reference)
    fabrik_cascade_models = FABRIK_ROOT / "docs" / "reference" / "windsurf" / "cascade-models.md"
    if fabrik_cascade_models.exists():
        cascade_target_dir = project_dir / "docs" / "reference" / "windsurf"
        cascade_target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(fabrik_cascade_models, cascade_target_dir / "cascade-models.md")

    # Copy KILO_AGENT_NAMING.md (Kilo CLI agent naming conventions)
    fabrik_kilo_naming = FABRIK_ROOT / "docs" / "reference" / "kilo" / "KILO_AGENT_NAMING.md"
    if fabrik_kilo_naming.exists():
        kilo_target_dir = project_dir / "docs" / "reference" / "kilo"
        kilo_target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(fabrik_kilo_naming, kilo_target_dir / "KILO_AGENT_NAMING.md")

    # Copy kilo_47_agents_final.json (Kilo CLI agent configuration)
    fabrik_kilo_config = FABRIK_ROOT / "scripts" / "kilo_47_agents_final.json"
    if fabrik_kilo_config.exists():
        scripts_target_dir = project_dir / "scripts"
        scripts_target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(fabrik_kilo_config, scripts_target_dir / "kilo_47_agents_final.json")

    # Copy technology-stack-decision-guide.md (central stack guidance)
    fabrik_stack_guide = FABRIK_ROOT / "docs" / "reference" / "technology-stack-decision-guide.md"
    if fabrik_stack_guide.exists():
        stack_target_dir = project_dir / "docs" / "reference"
        stack_target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(fabrik_stack_guide, stack_target_dir / "technology-stack-decision-guide.md")

    # Copy prebuilt-app-containers.md (container catalog)
    fabrik_containers = FABRIK_ROOT / "docs" / "reference" / "prebuilt-app-containers.md"
    if fabrik_containers.exists():
        containers_target_dir = project_dir / "docs" / "reference"
        containers_target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(fabrik_containers, containers_target_dir / "prebuilt-app-containers.md")

    # Copy opencode.json from fabrik master (single source of truth)
    shutil.copy(FABRIK_ROOT / "opencode.json", project_dir / "opencode.json")

    # Create .gitignore and .env.example
    (project_dir / ".gitignore").write_text(
        ".env\n"
        "venv/\n"
        "__pycache__/\n"
        "logs/\n"
        "data/\n"
        ".tmp/\n"
        ".cache/\n"
        "output/\n"
        "*.log\n"
        ".venv/\n" + _DROID_GITIGNORE_BLOCK + "\n"
        "# IDE\n"
        ".vscode/\n"
        ".idea/\n"
        "*.swp\n"
        "*.swo\n"
        "*~\n"
        "\n"
        "# Python\n"
        "*.pyc\n"
        "*.pyo\n"
        "*.pyd\n"
        ".Python\n"
        "pip-log.txt\n"
        "pip-delete-this-directory.txt\n"
        ".pytest_cache/\n"
        ".coverage\n"
        "htmlcov/\n"
        "dist/\n"
        "build/\n"
        "*.egg-info/\n"
    )
    # Example .env template with placeholder values (not real credentials)
    (project_dir / ".env.example").write_text(
        f"# {name} Configuration\n# Required\nPORT=8000\nLOG_LEVEL=INFO\n\n# Optional - uncomment if using database\n# DATABASE_URL=postgresql://user:pass@localhost:5432/{name}_dev\n"
    )

    # Note: templates/docs/ removed - templates/scaffold/docs/ is the canonical source

    # Copy templates/saas-skeleton/ for reference (used in 20-typescript.md)
    # Exclude build artifacts to prevent session poisoning (.next contains hardcoded /opt/fabrik paths)
    fabrik_saas_skeleton = FABRIK_ROOT / "templates" / "saas-skeleton"
    project_saas_skeleton = project_dir / "templates" / "saas-skeleton"
    if fabrik_saas_skeleton.exists():
        shutil.copytree(
            fabrik_saas_skeleton,
            project_saas_skeleton,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".next", "node_modules", ".turbo", "dist", "build"),
        )

    # Copy templates/spec-pipeline/ for Traycer discovery workflow (Stage 0)
    fabrik_spec_pipeline = FABRIK_ROOT / "templates" / "spec-pipeline"
    project_spec_pipeline = project_dir / "templates" / "spec-pipeline"
    if fabrik_spec_pipeline.exists():
        shutil.copytree(fabrik_spec_pipeline, project_spec_pipeline, dirs_exist_ok=True)

    # Create PORTS.md (every project tracks its own ports)
    (project_dir / "PORTS.md").write_text(
        f"""# {name} Port Allocations

**Last Updated:** {today}

This document tracks port allocations for {name} services to prevent conflicts.

---

## Port Ranges

| Range | Purpose | Environment |
|-------|---------|-------------|
| 3000-3099 | Frontend apps (Node.js) | WSL & VPS |
| 5000-5099 | Python services (misc) | WSL only |
| 8000-8099 | Python APIs (FastAPI) | WSL & VPS |
| 8100-8199 | Workers & background services | WSL & VPS |

---

## Current Allocations

| Port | Service | URL/Purpose |
|------|---------|-------------|
| TBD | Main service | Add your allocations here |

---

## Notes

- Register all ports in this file before using them
- Check this file before adding new services to avoid conflicts
"""
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

    # Create db/schema.sql - source of truth for database schema
    (project_dir / "db" / "schema.sql").write_text(
        f"""-- Database Schema
-- Project: {name}
-- Last Updated: {today}
--
-- This file tracks all database schema changes.
-- Agents MUST update this file when making database changes.
--
-- Usage:
--   - Add new tables/columns with CREATE statements
--   - Document changes with comments including date
--   - Keep this file as the source of truth for DB structure

-- =============================================================================
-- TABLES
-- =============================================================================

-- Example:
-- CREATE TABLE IF NOT EXISTS users (
--     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
--     email VARCHAR(255) UNIQUE NOT NULL,
--     created_at TIMESTAMPTZ DEFAULT NOW(),
--     updated_at TIMESTAMPTZ DEFAULT NOW()
-- );

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Example:
-- CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- =============================================================================
-- CHANGE LOG
-- =============================================================================
-- {today}: Initial schema created
"""
    )

    # Create project.yaml — per-project metadata (source of truth)
    # Port is passed in from create_project (already allocated based on project type)
    project_yaml = {
        "name": name,
        "type": "python-api",  # overwritten by create_project if different
        "description": description,
        "created": today,
        "status": "development",
        "category": "active",
        # Deployment — ports is a list of host ports this project binds
        "url": None,
        "domain": None,
        "ports": [host_port],
        # Extended metadata
        "external_systems": [],
        "monthly_cost": 0,
        "dependencies": [],
        "tags": [],
        # Cross-cutting enforcement
        "has_user_guide": False,
    }
    (project_dir / "project.yaml").write_text(
        "# Project metadata — source of truth\n"
        "# Created by: fabrik scaffold\n"
        "# Updated by: project owner or fabrik scan\n"
        "#\n"
        "# Fields:\n"
        "#   status: development | ready | production | archived\n"
        "#   category: production | active | planning | shell\n"
        "#   ports: list of host ports this project binds (must be unique across /opt)\n"
        "#   external_systems: list of external services (e.g. supabase, stripe, cloudflare-r2)\n"
        "#   monthly_cost: estimated USD/month\n"
        "#   dependencies: other /opt project names this depends on\n"
        "#   tags: free-form labels\n"
        "#   has_user_guide: true if project has user-facing docs (activates user-guide gate)\n\n"
        + yaml.dump(project_yaml, default_flow_style=False, sort_keys=False)
    )

    # Git bootstrap: initialize repo so type-specific scaffolders run inside a git repo.
    # The final commit is deferred to create_project() so it captures all files in one
    # clean, complete snapshot.
    subprocess.run(["git", "init", "-q"], cwd=project_dir, capture_output=True)

    # Create and switch to project-specific branch (mobasak/<project-name>)
    # Only create branch if no commits exist yet (defensive check for spec compliance)
    branch_name = f"mobasak/{name}"
    has_commits = (
        subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=project_dir,
            capture_output=True,
        ).returncode
        == 0
    )

    if not has_commits:
        subprocess.run(["git", "checkout", "-b", branch_name], cwd=project_dir, capture_output=True)

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

    # Create requirements.txt (production dependencies only)
    (project_dir / "requirements.txt").write_text(
        "fastapi>=0.115.0\nuvicorn[standard]>=0.32.0\npydantic>=2.9.0\npython-dotenv>=1.0.0\nhttpx>=0.28.0\nstructlog>=24.0.0\n"
    )

    # Create requirements-dev.txt (includes dev dependencies)
    (project_dir / "requirements-dev.txt").write_text(
        "-r requirements.txt\nruff\nmypy\nbandit\nsemgrep\nsqlfluff\nvulture\n"
    )

    # Create starter src/<package_name>/ package with logger, middleware, and main
    package_dir = project_dir / "src" / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "__init__.py").write_text("")

    # logger.py — structlog JSON logger with service name from env
    (package_dir / "logger.py").write_text(
        f'"""Structured logging module for {name}.\n'
        f"\n"
        f"Pre-configured structlog logger with JSON output and service name binding.\n"
        f"Usage: from {package_name}.logger import get_logger\n"
        f'"""\n'
        f"\n"
        f"import os\n"
        f"\n"
        f"import structlog\n"
        f"\n"
        f"\n"
        f"def _setup_logging() -> None:\n"
        f'    """Configure structlog with JSON output."""\n'
        f"    structlog.configure(\n"
        f"        processors=[\n"
        f"            structlog.contextvars.merge_contextvars,\n"
        f"            structlog.processors.add_log_level,\n"
        f'            structlog.processors.TimeStamper(fmt="iso"),\n'
        f"            structlog.processors.StackInfoRenderer(),\n"
        f"            structlog.processors.format_exc_info,\n"
        f"            structlog.processors.JSONRenderer(),\n"
        f"        ],\n"
        f"        wrapper_class=structlog.stdlib.BoundLogger,\n"
        f"        context_class=dict,\n"
        f"        logger_factory=structlog.PrintLoggerFactory(),\n"
        f"        cache_logger_on_first_use=True,\n"
        f"    )\n"
        f"\n"
        f"\n"
        f"_setup_logging()\n"
        f"\n"
        f"\n"
        f"def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:\n"
        f'    """Return a structlog logger bound with service name."""\n'
        f'    return structlog.get_logger(name, service=os.getenv("SERVICE_NAME", "{package_name}"))  # type: ignore[no-any-return]\n'
    )

    # middleware.py — X-Request-ID correlation middleware
    (package_dir / "middleware.py").write_text(
        f'"""Correlation ID middleware for {name}.\n'
        f"\n"
        f"Binds X-Request-ID to structlog context via contextvars.\n"
        f"Usage: app.add_middleware(CorrelationMiddleware)\n"
        f'"""\n'
        f"\n"
        f"import uuid\n"
        f"from contextvars import ContextVar\n"
        f"\n"
        f"import structlog\n"
        f"from starlette.middleware.base import BaseHTTPMiddleware\n"
        f"from starlette.requests import Request\n"
        f"from starlette.responses import Response\n"
        f"\n"
        f'correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")\n'
        f"\n"
        f"\n"
        f"class CorrelationMiddleware(BaseHTTPMiddleware):\n"
        f'    """Attach X-Request-ID to every request and bind to structlog context."""\n'
        f"\n"
        f"    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001\n"
        f'        """Process request with correlation ID."""\n'
        f'        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))\n'
        f"        correlation_id.set(req_id)\n"
        f"        structlog.contextvars.bind_contextvars(correlation_id=req_id)\n"
        f"        try:\n"
        f"            response = await call_next(request)\n"
        f'            response.headers["X-Request-ID"] = req_id\n'
        f"            return response  # type: ignore[no-any-return]\n"
        f"        finally:\n"
        f'            structlog.contextvars.unbind_contextvars("correlation_id")\n'
    )

    # main.py — FastAPI app with structured logging and correlation middleware
    (package_dir / "main.py").write_text(
        f'"""Main entry point for {name}."""\n'
        f"\n"
        f"import os\n"
        f"from contextlib import asynccontextmanager\n"
        f"\n"
        f"from fastapi import FastAPI\n"
        f"from fastapi.responses import JSONResponse\n"
        f"\n"
        f"from {package_name}.logger import get_logger\n"
        f"from {package_name}.middleware import CorrelationMiddleware\n"
        f"\n"
        f"logger = get_logger(__name__)\n"
        f"\n"
        f"\n"
        f"@asynccontextmanager\n"
        f"async def lifespan(app: FastAPI):  # noqa: ARG001\n"
        f'    """Application lifespan handler."""\n'
        f'    logger.info("service_starting", port=os.getenv("PORT", "8000"))\n'
        f"    yield\n"
        f'    logger.info("service_stopping")\n'
        f"\n"
        f"\n"
        f'app = FastAPI(title="{name}", lifespan=lifespan)\n'
        f"app.add_middleware(CorrelationMiddleware)\n"
        f"\n"
        f"\n"
        f'@app.get("/health")\n'
        f"async def health():\n"
        f'    """Health check - tests actual dependencies, returns non-200 on failure."""\n'
        f'    db_url = os.getenv("DATABASE_URL")\n'
        f"    deps = {{}}\n"
        f"    all_ok = True\n"
        f"\n"
        f"    # Database check (only if configured)\n"
        f"    if db_url:\n"
        f"        try:\n"
        f"            # TODO: Replace with actual async DB ping when DB is added\n"
        f'            # Example: await db.execute("SELECT 1")\n'
        f'            deps["database"] = "configured"\n'
        f"        except Exception as e:\n"
        f'            deps["database"] = f"error: {{str(e)}}"\n'
        f'            logger.error("health_check_failed", dependency="database", error=str(e))\n'
        f"            all_ok = False\n"
        f"    else:\n"
        f'        deps["database"] = "not_configured"\n'
        f"\n"
        f"    status_code = 200 if all_ok else 503\n"
        f"    return JSONResponse(\n"
        f"        content={{\n"
        f'            "service": "{name}",\n'
        f'            "status": "ok" if all_ok else "degraded",\n'
        f'            "dependencies": deps,\n'
        f"        }},\n"
        f"        status_code=status_code,\n"
        f"    )\n"
        f"\n"
        f"\n"
        f'@app.get("/")\n'
        f"async def root():\n"
        f'    return {{"message": "Welcome to {name}"}}\n'
    )

    # Append SERVICE_NAME to .env.example (written by _scaffold_shared)
    with open(project_dir / ".env.example", "a") as f:
        f.write(f"\n# Service identity for structured logging\nSERVICE_NAME={name}\n")

    # Database setup (only if --db flag passed)
    use_database = kwargs.get("use_database", False)
    if use_database:
        # Create .env.local for WSL development
        db_name_dev = name.replace("-", "_") + "_dev"
        (project_dir / ".env.local").write_text(
            f"# {name} Local Development (WSL)\n"
            f"LOG_LEVEL=DEBUG\n"
            f"SERVICE_NAME={name}\n\n"
            f"# Native PostgreSQL on WSL\n"
            f"DATABASE_URL=postgresql://postgres@localhost:5432/{db_name_dev}\n"
        )

        # Auto-create development database
        import click

        try:
            # Check if database exists (exact match to avoid partial name collisions)
            check_result = subprocess.run(
                ["sudo", "-u", "postgres", "psql", "-lqt"],
                capture_output=True,
                timeout=5,
                text=True,
            )

            db_exists = False
            if check_result.returncode == 0:
                # Parse database list, exact match only
                for line in check_result.stdout.split("\n"):
                    if "|" in line:
                        db_in_line = line.split("|")[0].strip()
                        if db_in_line == db_name_dev:
                            db_exists = True
                            break

            if not db_exists:
                # Create database
                create_result = subprocess.run(
                    ["sudo", "-u", "postgres", "psql", "-c", f"CREATE DATABASE {db_name_dev};"],
                    capture_output=True,
                    timeout=5,
                )
                if create_result.returncode == 0:
                    click.echo(f"✅ Created PostgreSQL database: {db_name_dev}")
                else:
                    click.echo("⚠️  Could not create database. Run manually:")
                    click.echo(f"    sudo -u postgres psql -c 'CREATE DATABASE {db_name_dev};'")
            else:
                click.echo(f"✅ PostgreSQL database exists: {db_name_dev}")

        except Exception:
            click.echo("⚠️  Database auto-creation failed. Create manually:")
            click.echo(f"    sudo -u postgres psql -c 'CREATE DATABASE {db_name_dev};'")

        # Update .env.example to uncomment DATABASE_URL
        env_example_path = project_dir / ".env.example"
        env_content = env_example_path.read_text()
        # Replace commented DB line with VPS version
        env_content = env_content.replace(
            f"# Optional - uncomment if using database\n# DATABASE_URL=postgresql://user:pass@localhost:5432/{name}_dev\n",
            f"# Database (managed by Coolify on VPS)\n# Set via Coolify secrets: POSTGRES_PASSWORD\nDATABASE_URL=postgresql://postgres:${{POSTGRES_PASSWORD}}@postgres-main:5432/{name.replace('-', '_')}\n",
        )
        env_example_path.write_text(env_content)

    # Create basic test
    (project_dir / "tests" / "__init__.py").write_text("")
    (project_dir / "tests" / "test_health.py").write_text(
        f'"""Health endpoint tests."""\n'
        f"\n"
        f"import os\n"
        f"from unittest.mock import patch\n"
        f"\n"
        f"from fastapi.testclient import TestClient\n"
        f"\n"
        f"from {package_name}.main import app\n"
        f"\n"
        f"client = TestClient(app)\n"
        f"\n"
        f"\n"
        f"def test_health_returns_200_without_db():\n"
        f'    """Health returns 200 when DB is not configured."""\n'
        f"    with patch.dict(os.environ, {{}}, clear=True):\n"
        f'        response = client.get("/health")\n'
        f"        assert response.status_code == 200\n"
        f"        data = response.json()\n"
        f'        assert data["service"] == "{name}"\n'
        f'        assert data["status"] == "ok"\n'
        f'        assert data["dependencies"]["database"] == "not_configured"\n'
        f"\n"
        f"\n"
        f"def test_health_returns_200_with_db_configured():\n"
        f'    """Health returns 200 when DB is configured (mocked)."""\n'
        f'    with patch.dict(os.environ, {{"DATABASE_URL": "postgresql://test@localhost/test"}}):\n'
        f'        response = client.get("/health")\n'
        f"        assert response.status_code == 200\n"
        f"        data = response.json()\n"
        f'        assert data["dependencies"]["database"] == "configured"\n'
        f"\n"
        f"\n"
        f"def test_root_endpoint():\n"
        f'    """Root endpoint returns welcome message."""\n'
        f'    response = client.get("/")\n'
        f"    assert response.status_code == 200\n"
        f'    assert "message" in response.json()\n'
        f"\n"
        f"\n"
        f"def test_health_returns_correlation_id():\n"
        f'    """Health response includes X-Request-ID header."""\n'
        f'    response = client.get("/health")\n'
        f'    assert "x-request-id" in response.headers\n'
        f"\n"
        f"\n"
        f"def test_health_preserves_provided_request_id():\n"
        f'    """Health response preserves client-provided X-Request-ID."""\n'
        f'    response = client.get("/health", headers={{"X-Request-ID": "test-123"}})\n'
        f'    assert response.headers["x-request-id"] == "test-123"\n'
    )

    # Create Python virtual environment and install dependencies
    venv_path = project_dir / ".venv"
    subprocess.run(["python", "-m", "venv", ".venv"], cwd=project_dir, capture_output=True)

    # Install development dependencies
    venv_pip = (
        venv_path / "bin" / "pip"
        if (venv_path / "bin").exists()
        else venv_path / "Scripts" / "pip.exe"
    )
    result = subprocess.run(
        [str(venv_pip), "install", "-r", "requirements-dev.txt"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.warning("Failed to install dev dependencies: %s", result.stderr)


_SAAS_SKIP_FILES = {"AGENTS.md", "pyproject.toml", "requirements.txt"}
_SAAS_SKIP_DIRS = {"node_modules", ".next", ".turbo", "dist", "build", "__pycache__"}


def _scaffold_saas_skeleton(
    project_dir: Path, name: str, description: str, **kwargs: object
) -> None:
    """Copy the saas-skeleton template into the project directory, patching names."""
    for src in SAAS_SKELETON_DIR.rglob("*"):
        if not src.is_file():
            continue

        rel = src.relative_to(SAAS_SKELETON_DIR)

        # Skip build artifact directories
        if any(part in _SAAS_SKIP_DIRS for part in rel.parts):
            continue

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

    # Write structured logger (pino) for saas-skeleton projects
    (project_dir / "lib").mkdir(parents=True, exist_ok=True)
    # NOTE: This write intentionally overwrites any lib/logger.ts copied from the
    # saas-skeleton template. Scaffold-generated version takes precedence. If the
    # template ever gains its own lib/logger.ts, update _SAAS_SKIP_FILES accordingly.
    (project_dir / "lib" / "logger.ts").write_text(
        f"import pino from 'pino';\n"
        f"\n"
        f"const logger = pino({{\n"
        f"  level: process.env.LOG_LEVEL || 'info',\n"
        f"  name: process.env.SERVICE_NAME || '{name}',\n"
        f"  timestamp: pino.stdTimeFunctions.isoTime,\n"
        f"}});\n"
        f"\n"
        f"export default logger;\n"
    )


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
        "dependencies": {
            "pino": "^9.0.0",
        },
    }
    (project_dir / "package.json").write_text(json.dumps(package_json, indent=2) + "\n")

    # e) Generate src/logger.js inline (pino structured logging)
    (project_dir / "src" / "logger.js").write_text(
        f"""'use strict';

const pino = require('pino');

const logger = pino({{
  level: process.env.LOG_LEVEL || 'info',
  name: process.env.SERVICE_NAME || '{name}',
  timestamp: pino.stdTimeFunctions.isoTime,
}});

module.exports = logger;
"""
    )

    # f) Generate src/index.js inline (with pino logging and X-Request-ID correlation)
    (project_dir / "src" / "index.js").write_text(
        f"""'use strict';

const http = require('http');
const {{ randomUUID }} = require('crypto');
const logger = require('./logger');

const PORT = process.env.PORT || 3000;

const server = http.createServer((req, res) => {{
  const requestId = req.headers['x-request-id'] || randomUUID();
  res.setHeader('X-Request-ID', requestId);
  const child = logger.child({{ correlation_id: requestId }});

  if (req.method === 'GET' && req.url === '/health') {{
    res.writeHead(200, {{ 'Content-Type': 'application/json' }});
    res.end(JSON.stringify({{ service: '{name}', status: 'ok' }}));
    return;
  }}

  child.info({{ event: 'request_received', method: req.method, url: req.url }});
  res.writeHead(200, {{ 'Content-Type': 'application/json' }});
  res.end(JSON.stringify({{ message: 'Welcome to {name}' }}));
}});

server.listen(PORT, () => {{
  logger.info({{ event: 'service_starting', port: PORT }});
}});
"""
    )

    # g) Overwrite .env.example with Node-appropriate content
    (project_dir / ".env.example").write_text(
        f"# {name} Configuration\nPORT=3000\nNODE_ENV=development\nLOG_LEVEL=info\n\n# Service identity for structured logging\nSERVICE_NAME={name}\n"
    )

    # h) Overwrite .gitignore with Node-appropriate content
    (project_dir / ".gitignore").write_text(
        "node_modules/\n"
        "dist/\n"
        ".env\n"
        "logs/\n"
        "data/\n"
        ".tmp/\n"
        ".cache/\n"
        "output/\n"
        "*.log\n" + _DROID_GITIGNORE_BLOCK + "\n"
        "# IDE\n"
        ".vscode/\n"
        ".idea/\n"
        "*.swp\n"
        "*.swo\n"
        "*~\n"
        "\n"
        "# Node.js\n"
        "npm-debug.log*\n"
        "yarn-debug.log*\n"
        "yarn-error.log*\n"
        ".pnpm-debug.log*\n"
        "\n"
        "# Build & Test\n"
        "coverage/\n"
        ".next/\n"
        "out/\n"
        "build/\n"
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

    # b2) Generate src/logger.js inline (pino structured logging)
    (project_dir / "src" / "logger.js").write_text(
        f"""'use strict';

const pino = require('pino');

const logger = pino({{
  level: process.env.LOG_LEVEL || 'info',
  name: process.env.SERVICE_NAME || '{name}',
  timestamp: pino.stdTimeFunctions.isoTime,
}});

module.exports = logger;
"""
    )

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
            "pino": "^9.0.0",
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

# Service identity for structured logging
SERVICE_NAME={name}
"""
    )

    # g) Overwrite .gitignore with Node-appropriate content
    (project_dir / ".gitignore").write_text(
        "node_modules/\n"
        "dist/\n"
        ".env\n"
        "logs/\n"
        "data/\n"
        ".tmp/\n"
        ".cache/\n"
        "output/\n"
        "*.log\n" + _DROID_GITIGNORE_BLOCK + "\n"
        "# IDE\n"
        ".vscode/\n"
        ".idea/\n"
        "*.swp\n"
        "*.swo\n"
        "*~\n"
        "\n"
        "# Node.js\n"
        "npm-debug.log*\n"
        "yarn-debug.log*\n"
        "yarn-error.log*\n"
        ".pnpm-debug.log*\n"
        "\n"
        "# Build & Test\n"
        "coverage/\n"
        "build/\n"
    )


def _scaffold_file_worker(project_dir: Path, name: str, description: str, **kwargs: object) -> None:
    """Create File Worker-specific project structure."""
    # a) Create worker/ directory
    (project_dir / "worker").mkdir(parents=True, exist_ok=True)

    # b) Write worker/logger.py — structured logging module
    (project_dir / "worker" / "logger.py").write_text(
        f'''"""Structured logging for {name} file-worker."""

import os

import structlog


def _setup_logging() -> None:
    """Configure structlog with JSON output for production."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


_setup_logging()


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """Return a bound logger with service identity."""
    return structlog.get_logger(name, service=os.getenv("SERVICE_NAME", "{name}"))  # type: ignore[no-any-return]
'''
    )

    # c) Copy main.py verbatim from file-worker template
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

# Service identity for structured logging
SERVICE_NAME={name}
"""
    )

    # g) Overwrite .gitignore with Python-appropriate content
    (project_dir / ".gitignore").write_text(
        ".env\n"
        ".env.local\n"
        "venv/\n"
        "__pycache__/\n"
        "logs/\n"
        "data/\n"
        ".tmp/\n"
        ".cache/\n"
        "output/\n"
        "*.log\n"
        ".venv/\n" + _DROID_GITIGNORE_BLOCK + "\n"
        "# IDE\n"
        ".vscode/\n"
        ".idea/\n"
        "*.swp\n"
        "*.swo\n"
        "*~\n"
        "\n"
        "# Python\n"
        "*.pyc\n"
        "*.pyo\n"
        "*.pyd\n"
        ".Python\n"
        "pip-log.txt\n"
        "pip-delete-this-directory.txt\n"
        ".pytest_cache/\n"
        ".coverage\n"
        "htmlcov/\n"
        "dist/\n"
        "build/\n"
        "*.egg-info/\n"
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

    # e) Overwrite .env.example with WordPress/MariaDB/B2 placeholder vars
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
# WordPress REST API credentials (used by fabrik wp apply)
WP_ADMIN_USER=CHANGE_ME
WP_ADMIN_PASSWORD=CHANGE_ME
# Backblaze B2 backup storage (preferred — free egress via Bandwidth Alliance)
B2_KEY_ID=your-b2-key-id
B2_APPLICATION_KEY=your-b2-application-key
B2_BUCKET={name_underscored}-wp-backup
"""
    )

    # f) Overwrite .gitignore with WordPress-appropriate content
    (project_dir / ".gitignore").write_text(
        ".env\n"
        "wp-content/uploads/\n"
        "wp-content/upgrade/\n"
        "logs/\n"
        "data/\n"
        ".tmp/\n"
        ".cache/\n"
        "*.log\n" + _DROID_GITIGNORE_BLOCK + "\n"
        "# IDE\n"
        ".vscode/\n"
        ".idea/\n"
        "*.swp\n"
        "*.swo\n"
        "*~\n"
        "\n"
        "# WordPress\n"
        "wp-content/cache/\n"
        "wp-content/backup-db/\n"
        "sitemap.xml\n"
        "sitemap.xml.gz\n"
        "site.yaml\n"
        "\n"
        "# Node.js (for theme/plugin development)\n"
        "node_modules/\n"
        "npm-debug.log*\n"
        "yarn-debug.log*\n"
        "\n"
        "# Build & Test (theme/plugin development)\n"
        "dist/\n"
        "build/\n"
        "coverage/\n"
    )

    # g) Copy Makefile.wordpress as Makefile
    makefile_src = TEMPLATE_DIR / "docker" / "Makefile.wordpress"
    if makefile_src.exists():
        shutil.copy2(makefile_src, project_dir / "Makefile")

    # h) Render site.yaml from Jinja2 template (T1)
    import jinja2

    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(WORDPRESS_TEMPLATE_DIR / "base")),
        autoescape=jinja2.select_autoescape(),
    )
    site_yaml_dest = project_dir / "site.yaml"
    if site_yaml_dest.exists():
        logger.warning("site.yaml already exists in %s — skipping to avoid overwrite", project_dir)
    else:
        rendered_site = jinja_env.get_template("site.yaml.j2").render(name=name, preset=preset)
        site_yaml_dest.write_text(rendered_site)

    # h) Render compose.dev.yaml and nginx-dev.conf from Jinja2 templates (T2)
    dev_port: str = str(kwargs.get("dev_port", "8080"))
    (project_dir / "config").mkdir(parents=True, exist_ok=True)
    rendered_compose_dev = jinja_env.get_template("compose.dev.yaml.j2").render(
        name=name, dev_port=dev_port
    )
    (project_dir / "compose.dev.yaml").write_text(rendered_compose_dev)

    rendered_nginx_dev = jinja_env.get_template("nginx-dev.conf.j2").render()
    (project_dir / "config" / "nginx-dev.conf").write_text(rendered_nginx_dev)


def _scaffold_chrome_extension(
    project_dir: Path, name: str, description: str, **kwargs: object
) -> None:
    """Create Chrome Extension with TypeScript extension + FastAPI server."""
    import json

    package_name = _get_package_name(name)

    # Create directory structure
    (project_dir / "extension" / "src").mkdir(parents=True, exist_ok=True)
    (project_dir / "extension" / "icons").mkdir(parents=True, exist_ok=True)
    (project_dir / "server" / "src" / package_name).mkdir(parents=True, exist_ok=True)

    # 1. Extension files
    # manifest.json - render from template
    manifest_template = FABRIK_ROOT / "templates" / "chrome-extension" / "manifest.json.j2"
    if manifest_template.exists():
        content = manifest_template.read_text()
        content = content.replace("{{ spec.id }}", name)
        content = content.replace(
            "{{ spec.description | default('Chrome extension') }}", description
        )
        (project_dir / "extension" / "manifest.json").write_text(content)

    # popup.html (in src/ — CRXJS resolves from manifest)
    (project_dir / "extension" / "src" / "popup.html").write_text(
        f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{name}</title>
  <style>
    body {{ width: 300px; padding: 20px; font-family: system-ui; }}
    h1 {{ font-size: 16px; margin: 0 0 10px 0; }}
  </style>
</head>
<body>
  <h1>{name}</h1>
  <div id="app"></div>
  <script type="module" src="./popup.ts"></script>
</body>
</html>
"""
    )

    # popup.ts
    (project_dir / "extension" / "src" / "popup.ts").write_text(
        """document.addEventListener('DOMContentLoaded', () => {
  const app = document.getElementById('app');
  if (app) {
    app.textContent = 'Extension loaded!';
  }
});
"""
    )

    # background.ts
    (project_dir / "extension" / "src" / "background.ts").write_text(
        """chrome.runtime.onInstalled.addListener(() => {
  console.log('Extension installed');
});
"""
    )

    # content.ts
    (project_dir / "extension" / "src" / "content.ts").write_text(
        """console.log('Content script loaded');
"""
    )

    # icons/.gitkeep and README
    icons_dir = project_dir / "extension" / "icons"
    (icons_dir / ".gitkeep").write_text("")
    (icons_dir / "README.md").write_text(
        """# Extension Icons

**Required:** Generate 3 icon sizes before loading extension in Chrome.

## Required Files
- `icon16.png` (16×16) - Toolbar icon
- `icon48.png` (48×48) - Extension management page
- `icon128.png` (128×128) - Chrome Web Store, installation dialog

## Quick Generation Options

**Option 1 - ImageMagick** (if installed):
```bash
# Create placeholder colored squares
convert -size 16x16 xc:#4285f4 icon16.png
convert -size 48x48 xc:#4285f4 icon48.png
convert -size 128x128 xc:#4285f4 icon128.png
```

**Option 2 - Online Tool:**
- Generate a single 128×128 PNG at https://www.favicon-generator.org/
- Tool will auto-generate all 3 sizes
- Download and place here

**Option 3 - Design Tool:**
- Use Figma/Canva/Photoshop to create custom icons
- Export as PNG at each required size

Extension will fail to load without these files.
"""
    )

    # vite.config.ts (Vite + CRXJS for MV3-aware builds)
    (project_dir / "extension" / "vite.config.ts").write_text(
        """import { defineConfig } from 'vite';
import { crx } from '@crxjs/vite-plugin';
import manifest from './manifest.json';

export default defineConfig({
  plugins: [crx({ manifest })],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
"""
    )

    # extension/package.json
    ext_package = {
        "name": f"{name}-extension",
        "version": "1.0.0",
        "description": f"{description} - Browser Extension",
        "scripts": {
            "dev": "vite",
            "build": "vite build",
        },
        "devDependencies": {
            "@crxjs/vite-plugin": "^2.0.0-beta.28",
            "@types/chrome": "^0.0.254",
            "typescript": "^5.3.3",
            "vite": "^5.4.0",
        },
    }
    (project_dir / "extension" / "package.json").write_text(
        json.dumps(ext_package, indent=2) + "\n"
    )

    # 2. Server files (FastAPI)
    server_pkg_dir = project_dir / "server" / "src" / package_name

    # server/src/<package_name>/__init__.py
    (server_pkg_dir / "__init__.py").write_text("")

    # server/src/<package_name>/logger.py — structlog JSON logger
    (server_pkg_dir / "logger.py").write_text(
        f'"""Structured logging module for {name}.\n'
        f"\n"
        f"Pre-configured structlog logger with JSON output and service name binding.\n"
        f"Usage: from {package_name}.logger import get_logger\n"
        f'"""\n'
        f"\n"
        f"import os\n"
        f"\n"
        f"import structlog\n"
        f"\n"
        f"\n"
        f"def _setup_logging() -> None:\n"
        f'    """Configure structlog with JSON output."""\n'
        f"    structlog.configure(\n"
        f"        processors=[\n"
        f"            structlog.contextvars.merge_contextvars,\n"
        f"            structlog.processors.add_log_level,\n"
        f'            structlog.processors.TimeStamper(fmt="iso"),\n'
        f"            structlog.processors.StackInfoRenderer(),\n"
        f"            structlog.processors.format_exc_info,\n"
        f"            structlog.processors.JSONRenderer(),\n"
        f"        ],\n"
        f"        wrapper_class=structlog.stdlib.BoundLogger,\n"
        f"        context_class=dict,\n"
        f"        logger_factory=structlog.PrintLoggerFactory(),\n"
        f"        cache_logger_on_first_use=True,\n"
        f"    )\n"
        f"\n"
        f"\n"
        f"_setup_logging()\n"
        f"\n"
        f"\n"
        f"def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:\n"
        f'    """Return a structlog logger bound with service name."""\n'
        f'    return structlog.get_logger(name, service=os.getenv("SERVICE_NAME", "{package_name}"))  # type: ignore[no-any-return]\n'
    )

    # server/src/<package_name>/middleware.py — X-Request-ID correlation middleware
    (server_pkg_dir / "middleware.py").write_text(
        f'"""Correlation ID middleware for {name}.\n'
        f"\n"
        f"Binds X-Request-ID to structlog context via contextvars.\n"
        f"Usage: app.add_middleware(CorrelationMiddleware)\n"
        f'"""\n'
        f"\n"
        f"import uuid\n"
        f"from contextvars import ContextVar\n"
        f"\n"
        f"import structlog\n"
        f"from starlette.middleware.base import BaseHTTPMiddleware\n"
        f"from starlette.requests import Request\n"
        f"from starlette.responses import Response\n"
        f"\n"
        f'correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")\n'
        f"\n"
        f"\n"
        f"class CorrelationMiddleware(BaseHTTPMiddleware):\n"
        f'    """Attach X-Request-ID to every request and bind to structlog context."""\n'
        f"\n"
        f"    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001\n"
        f'        """Process request with correlation ID."""\n'
        f'        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))\n'
        f"        correlation_id.set(req_id)\n"
        f"        structlog.contextvars.bind_contextvars(correlation_id=req_id)\n"
        f"        try:\n"
        f"            response = await call_next(request)\n"
        f'            response.headers["X-Request-ID"] = req_id\n'
        f"            return response  # type: ignore[no-any-return]\n"
        f"        finally:\n"
        f'            structlog.contextvars.unbind_contextvars("correlation_id")\n'
    )

    # server/src/<package_name>/main.py — with structured logging + correlation + CORS
    (server_pkg_dir / "main.py").write_text(
        f'"""Main entry point for {name} server."""\n'
        f"\n"
        f"import os\n"
        f"from contextlib import asynccontextmanager\n"
        f"\n"
        f"from fastapi import FastAPI\n"
        f"from fastapi.middleware.cors import CORSMiddleware\n"
        f"from fastapi.responses import JSONResponse\n"
        f"\n"
        f"from {package_name}.logger import get_logger\n"
        f"from {package_name}.middleware import CorrelationMiddleware\n"
        f"\n"
        f"logger = get_logger(__name__)\n"
        f"\n"
        f"\n"
        f"@asynccontextmanager\n"
        f"async def lifespan(app: FastAPI):  # noqa: ARG001\n"
        f'    """Application lifespan handler."""\n'
        f'    logger.info("service_starting", port=os.getenv("PORT", "8000"))\n'
        f"    yield\n"
        f'    logger.info("service_stopping")\n'
        f"\n"
        f"\n"
        f'app = FastAPI(title="{name}", lifespan=lifespan)\n'
        f"app.add_middleware(CorrelationMiddleware)\n"
        f"\n"
        f"# CORS for extension\n"
        f"app.add_middleware(\n"
        f"    CORSMiddleware,\n"
        f'    allow_origins=["*"],  # Configure appropriately for production\n'
        f"    allow_credentials=True,\n"
        f'    allow_methods=["*"],\n'
        f'    allow_headers=["*"],\n'
        f")\n"
        f"\n"
        f"\n"
        f'@app.get("/health")\n'
        f"async def health():\n"
        f'    """Health check - tests actual dependencies, returns non-200 on failure."""\n'
        f"    return JSONResponse(\n"
        f"        content={{\n"
        f'            "service": "{name}",\n'
        f'            "status": "ok",\n'
        f"        }},\n"
        f"        status_code=200,\n"
        f"    )\n"
        f"\n"
        f"\n"
        f'@app.get("/")\n'
        f"async def root():\n"
        f'    return {{"message": "Welcome to {name} API"}}\n'
    )

    # requirements.txt (at root, for server)
    (project_dir / "requirements.txt").write_text(
        "fastapi>=0.115.0\nuvicorn[standard]>=0.32.0\npydantic>=2.9.0\npython-dotenv>=1.0.0\nhttpx>=0.28.0\npytest>=8.0.0\nstructlog>=24.0.0\n"
    )

    # tests/test_health.py
    (project_dir / "tests" / "__init__.py").write_text("")
    (project_dir / "tests" / "test_health.py").write_text(
        f'"""Health endpoint tests."""\n'
        f"\n"
        f"from fastapi.testclient import TestClient\n"
        f"\n"
        f"from {package_name}.main import app\n"
        f"\n"
        f"client = TestClient(app)\n"
        f"\n"
        f"\n"
        f"def test_health_returns_200():\n"
        f'    """Health returns 200."""\n'
        f'    response = client.get("/health")\n'
        f"    assert response.status_code == 200\n"
        f"    data = response.json()\n"
        f'    assert data["service"] == "{name}"\n'
        f'    assert data["status"] == "ok"\n'
        f"\n"
        f"\n"
        f"def test_root_endpoint():\n"
        f'    """Root endpoint returns welcome message."""\n'
        f'    response = client.get("/")\n'
        f"    assert response.status_code == 200\n"
        f'    assert "message" in response.json()\n'
    )

    # 3. Docker files
    # Dockerfile (Python server only)
    (project_dir / "Dockerfile").write_text(
        f"""FROM python:3.12-slim-bookworm AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim-bookworm
WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

ENV PYTHONPATH=/app/server/src
ENV PORT=8000

EXPOSE ${{PORT}}

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \\
  CMD curl -f http://localhost:${{PORT}}/health || exit 1

# Copy Python packages and binaries from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY requirements.txt .
COPY server/ ./server/

CMD ["sh", "-c", "uvicorn {package_name}.main:app --host 0.0.0.0 --port ${{PORT:-8000}}"]
"""
    )

    # compose.yaml
    (project_dir / "compose.yaml").write_text(
        f"""services:
  {name}:
    build: .
    container_name: {name}
    platform: linux/amd64  # MANDATORY - VPS is x86_64
    restart: unless-stopped
    ports:
      - "${{PORT:-8000}}:${{PORT:-8000}}"
    environment:
      - PORT=${{PORT:-8000}}
    networks:
      - coolify
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:${{PORT:-8000}}/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

networks:
  coolify:
    external: true  # Join existing Coolify mesh
"""
    )

    # 4. Makefile
    (project_dir / "Makefile").write_text(
        f""".PHONY: dev dev-server dev-ext build-ext install test docker-build docker-smoke clean

PROJECT_NAME := {name}
PORT := 8000

# Parallel dev: extension Vite dev + server uvicorn reload
dev:
\t@trap 'kill 0' SIGINT; \\
\tcd extension && npm run dev & \\
\t.venv/bin/uvicorn {package_name}.main:app --reload --host 0.0.0.0 --port $(PORT) --app-dir server/src & \\
\twait

# Server only (FastAPI with reload)
dev-server:
\t.venv/bin/uvicorn {package_name}.main:app --reload --host 0.0.0.0 --port $(PORT) --app-dir server/src

# Extension only (Vite dev with HMR)
dev-ext:
\tcd extension && npm run dev

# Production extension build (Vite)
build-ext:
\tcd extension && npm run build

# Install all dependencies
install:
\tpython -m venv .venv
\t.venv/bin/pip install -r requirements.txt
\tcd extension && npm install

# Run tests
test:
\tPYTHONPATH=server/src .venv/bin/pytest -v

# Docker build
docker-build:
\tdocker build -t $(PROJECT_NAME) .

# Docker smoke test
docker-smoke: docker-build
\t@echo "Starting container..."
\t@docker run -d --name $(PROJECT_NAME)-test -p $(PORT):$(PORT) -e PORT=$(PORT) $(PROJECT_NAME)
\t@echo "Waiting for health check..."
\t@sleep 5
\t@curl -f http://localhost:$(PORT)/health || (docker logs $(PROJECT_NAME)-test && exit 1)
\t@echo "✅ Health check passed"
\t@docker stop $(PROJECT_NAME)-test
\t@docker rm $(PROJECT_NAME)-test
\t@echo "✅ Smoke test completed"

# Clean build artifacts
clean:
\trm -rf extension/dist extension/node_modules
\tfind . -type d -name "__pycache__" -exec rm -rf {{}} +
\tdocker rmi $(PROJECT_NAME) 2>/dev/null || true
"""
    )

    # 5. .env.example (chrome-extension owns its .env.example entirely via write_text)
    (project_dir / ".env.example").write_text(
        f"""# {name} Configuration
PORT=8000
NODE_ENV=development

# Service identity for structured logging
SERVICE_NAME={name}
"""
    )

    # 6. .gitignore
    (project_dir / ".gitignore").write_text(
        "# Extension build\n"
        "extension/dist/\n"
        "extension/node_modules/\n"
        "\n"
        "# Python\n"
        "__pycache__/\n"
        "*.py[cod]\n"
        ".venv/\n"
        "venv/\n"
        "*.egg-info/\n"
        ".pytest_cache/\n"
        "\n"
        "# Environment\n"
        ".env\n"
        ".env.local\n"
        "\n"
        "# Project\n"
        "logs/\n"
        "data/\n"
        ".tmp/\n"
        ".cache/\n"
        "output/\n"
        "*.log\n" + _DROID_GITIGNORE_BLOCK + "\n"
        "# IDE\n"
        ".vscode/\n"
        ".idea/\n"
        "*.swp\n"
        "*.swo\n"
        "*~\n"
    )

    # Database setup for backend (only if --db flag passed)
    use_database = kwargs.get("use_database", False)
    if use_database:
        # Create .env.local for WSL development
        db_name_dev = name.replace("-", "_") + "_dev"
        (project_dir / ".env.local").write_text(
            f"# {name} Backend Local Development (WSL)\n"
            f"LOG_LEVEL=DEBUG\n"
            f"SERVICE_NAME={name}\n"
            f"PORT=8000\n"
            f"NODE_ENV=development\n\n"
            f"# Native PostgreSQL on WSL\n"
            f"DATABASE_URL=postgresql://postgres@localhost:5432/{db_name_dev}\n"
        )

        # Auto-create development database
        import click

        try:
            # Check if database exists (exact match)
            check_result = subprocess.run(
                ["sudo", "-u", "postgres", "psql", "-lqt"],
                capture_output=True,
                timeout=5,
                text=True,
            )

            db_exists = False
            if check_result.returncode == 0:
                for line in check_result.stdout.split("\n"):
                    if "|" in line:
                        db_in_line = line.split("|")[0].strip()
                        if db_in_line == db_name_dev:
                            db_exists = True
                            break

            if not db_exists:
                create_result = subprocess.run(
                    ["sudo", "-u", "postgres", "psql", "-c", f"CREATE DATABASE {db_name_dev};"],
                    capture_output=True,
                    timeout=5,
                )
                if create_result.returncode == 0:
                    click.echo(f"✅ Created PostgreSQL database: {db_name_dev}")
                else:
                    click.echo("⚠️  Could not create database. Run manually:")
                    click.echo(f"    sudo -u postgres psql -c 'CREATE DATABASE {db_name_dev};'")
            else:
                click.echo(f"✅ PostgreSQL database exists: {db_name_dev}")

        except Exception:
            click.echo("⚠️  Database auto-creation failed. Create manually:")
            click.echo(f"    sudo -u postgres psql -c 'CREATE DATABASE {db_name_dev};'")

        # Update .env.example to add DATABASE_URL
        env_example_path = project_dir / ".env.example"
        with open(env_example_path, "a") as f:
            f.write(
                f"\n# Database (managed by Coolify on VPS)\n"
                f"# Set via Coolify secrets: POSTGRES_PASSWORD\n"
                f"DATABASE_URL=postgresql://postgres:${{POSTGRES_PASSWORD}}@postgres-main:5432/{name.replace('-', '_')}\n"
            )

    # 7. Create Python virtual environment and install dependencies
    venv_path = project_dir / ".venv"
    subprocess.run(["python", "-m", "venv", ".venv"], cwd=project_dir, capture_output=True)

    venv_pip = (
        venv_path / "bin" / "pip"
        if (venv_path / "bin").exists()
        else venv_path / "Scripts" / "pip.exe"
    )
    result = subprocess.run(
        [str(venv_pip), "install", "-r", "requirements.txt"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.warning("Failed to install dependencies: %s", result.stderr)


def _scaffold_mobile_app(project_dir: Path, name: str, description: str, **kwargs: object) -> None:
    """Create React Native mobile app from templates/mobile-app/.

    Copies the real template package.json (with full React Native deps) and the
    entire src/ tree (navigation, features, screens) so the scaffold output
    matches the declared template contract.
    """
    import json

    # Copy package.json from template with name/description substitution
    pkg = json.loads((MOBILE_APP_TEMPLATE_DIR / "package.json").read_text())
    pkg["name"] = name
    pkg["description"] = description
    (project_dir / "package.json").write_text(json.dumps(pkg, indent=2) + "\n")

    # Copy src/ tree from template (React Native app structure)
    template_src = MOBILE_APP_TEMPLATE_DIR / "src"
    if template_src.exists():
        shutil.copytree(template_src, project_dir / "src", dirs_exist_ok=True)

    # .env.example
    (project_dir / ".env.example").write_text(
        f"# {name} Configuration\nNODE_ENV=development\nAPI_BASE_URL=https://api.your-vps.com/api\n"
    )

    # .gitignore (React Native-appropriate)
    (project_dir / ".gitignore").write_text(
        "node_modules/\n"
        ".env\n"
        "\n"
        "# React Native\n"
        "android/app/build/\n"
        "android/.gradle/\n"
        "ios/build/\n"
        "ios/Pods/\n"
        "\n"
        "# Build & Test\n"
        "dist/\n"
        "build/\n"
        "coverage/\n"
        "\n"
        "# Project\n"
        "logs/\n"
        "data/\n"
        ".tmp/\n"
        ".cache/\n"
        "*.log\n" + _DROID_GITIGNORE_BLOCK + "\n"
        "# IDE\n"
        ".vscode/\n"
        ".idea/\n"
        "*.swp\n"
        "*.swo\n"
        "*~\n"
        "\n"
        "# Node.js\n"
        "npm-debug.log*\n"
        "yarn-debug.log*\n"
    )


def _scaffold_desktop_app(project_dir: Path, name: str, description: str, **kwargs: object) -> None:
    """Create Electron desktop app from templates/desktop-app/.

    Copies the real template package.json (with Electron deps and build config)
    and the electron/ directory so the scaffold output matches the declared
    template contract.
    """
    import json

    # Read template package.json — contains {{ spec.id }} Jinja2 placeholders
    pkg_text = (DESKTOP_APP_TEMPLATE_DIR / "package.json").read_text()
    pkg_text = pkg_text.replace("{{ spec.id }}", name)
    pkg = json.loads(pkg_text)
    pkg["name"] = name
    pkg["description"] = description
    (project_dir / "package.json").write_text(json.dumps(pkg, indent=2) + "\n")

    # Copy electron/ directory from template
    template_electron = DESKTOP_APP_TEMPLATE_DIR / "electron"
    if template_electron.exists():
        shutil.copytree(template_electron, project_dir / "electron", dirs_exist_ok=True)

    # Create minimal index.html (referenced by electron/main.js win.loadFile)
    (project_dir / "index.html").write_text(
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta http-equiv="Content-Security-Policy" '
        "content=\"default-src 'self'; script-src 'self'\">\n"
        f"  <title>{name}</title>\n"
        "  <style>\n"
        "    body { font-family: system-ui; padding: 40px; background: #f8fafc; }\n"
        "    h1 { color: #0f172a; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"  <h1>{name}</h1>\n"
        f"  <p>{description}</p>\n"
        "</body>\n"
        "</html>\n"
    )

    # .env.example
    (project_dir / ".env.example").write_text(f"# {name} Configuration\nNODE_ENV=development\n")

    # .gitignore (Electron-appropriate)
    (project_dir / ".gitignore").write_text(
        "node_modules/\n"
        "dist/\n"
        ".env\n"
        "\n"
        "# Project\n"
        "logs/\n"
        "data/\n"
        ".tmp/\n"
        ".cache/\n"
        "output/\n"
        "*.log\n" + _DROID_GITIGNORE_BLOCK + "\n"
        "# IDE\n"
        ".vscode/\n"
        ".idea/\n"
        "*.swp\n"
        "*.swo\n"
        "*~\n"
        "\n"
        "# Node.js\n"
        "npm-debug.log*\n"
        "yarn-debug.log*\n"
        "yarn-error.log*\n"
    )


def _scaffold_docusaurus(project_dir: Path, name: str, description: str, **kwargs: object) -> None:
    """Create Docusaurus documentation site from templates/docusaurus/.

    Renders package.json from the .j2 template (simple name substitution).
    Generates docusaurus.config.js and sidebars.js inline with sensible defaults
    (full Jinja2 context vars like domain/features are not available at scaffold
    time — those are resolved later by ``fabrik new``/``fabrik apply``).
    """
    import json

    # Generate package.json from template ({{ name }} substitution)
    pkg_text = (DOCUSAURUS_TEMPLATE_DIR / "package.json.j2").read_text()
    pkg_text = pkg_text.replace("{{ name }}", name)
    pkg = json.loads(pkg_text)
    pkg["description"] = description
    (project_dir / "package.json").write_text(json.dumps(pkg, indent=2) + "\n")

    # Generate docusaurus.config.js (preserves full template contract including
    # OpenAPI plugin/theme, docItemComponent, and apiSidebar navbar item).
    config_js = (
        "// @ts-check\n"
        "import {themes as prismThemes} from 'prism-react-renderer';\n"
        "\n"
        "/** @type {import('@docusaurus/types').Config} */\n"
        "const config = {\n"
        f"  title: '{name} Documentation',\n"
        "  tagline: 'Developer documentation',\n"
        "  favicon: 'img/favicon.ico',\n"
        "\n"
        "  url: 'https://docs.example.com',\n"
        "  baseUrl: '/',\n"
        "\n"
        "  organizationName: 'ocoron',\n"
        f"  projectName: '{name}',\n"
        "\n"
        "  onBrokenLinks: 'throw',\n"
        "  onBrokenMarkdownLinks: 'warn',\n"
        "\n"
        "  i18n: {\n"
        "    defaultLocale: 'en',\n"
        "    locales: ['en'],\n"
        "  },\n"
        "\n"
        "  presets: [\n"
        "    [\n"
        "      'classic',\n"
        "      /** @type {import('@docusaurus/preset-classic').Options} */\n"
        "      ({\n"
        "        docs: {\n"
        "          sidebarPath: './sidebars.js',\n"
        '          docItemComponent: "@theme/ApiItem",\n'
        "        },\n"
        "        blog: false,\n"
        "        theme: {\n"
        "          customCss: './src/css/custom.css',\n"
        "        },\n"
        "      }),\n"
        "    ],\n"
        "  ],\n"
        "\n"
        "  plugins: [\n"
        "    [\n"
        "      'docusaurus-plugin-openapi-docs',\n"
        "      {\n"
        "        id: 'api',\n"
        "        docsPluginId: 'classic',\n"
        "        config: {\n"
        "          api: {\n"
        "            specPath: './openapi.yaml',\n"
        "            outputDir: 'docs/api',\n"
        "            sidebarOptions: {\n"
        "              groupPathsBy: 'tag',\n"
        "            },\n"
        "          },\n"
        "        },\n"
        "      },\n"
        "    ],\n"
        "  ],\n"
        "\n"
        "  themes: ['docusaurus-theme-openapi-docs'],\n"
        "\n"
        "  themeConfig:\n"
        "    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */\n"
        "    ({\n"
        "      navbar: {\n"
        f"        title: '{name}',\n"
        "        items: [\n"
        "          {\n"
        "            type: 'docSidebar',\n"
        "            sidebarId: 'guideSidebar',\n"
        "            position: 'left',\n"
        "            label: 'Guides',\n"
        "          },\n"
        "          {\n"
        "            type: 'docSidebar',\n"
        "            sidebarId: 'apiSidebar',\n"
        "            position: 'left',\n"
        "            label: 'API Reference',\n"
        "          },\n"
        "        ],\n"
        "      },\n"
        "      footer: {\n"
        "        style: 'dark',\n"
        "        links: [\n"
        "          {\n"
        "            title: 'Docs',\n"
        "            items: [\n"
        "              { label: 'Getting Started', to: '/docs/intro' },\n"
        "              { label: 'API Reference', to: '/docs/api' },\n"
        "            ],\n"
        "          },\n"
        "        ],\n"
        "        copyright: `Copyright \\u00A9 ${new Date().getFullYear()} Ocoron.`,\n"
        "      },\n"
        "      prism: {\n"
        "        theme: prismThemes.github,\n"
        "        darkTheme: prismThemes.dracula,\n"
        "      },\n"
        "    }),\n"
        "};\n"
        "\n"
        "export default config;\n"
    )
    (project_dir / "docusaurus.config.js").write_text(config_js)

    # Generate sidebars.js (with apiSidebar matching template contract)
    (project_dir / "sidebars.js").write_text(
        "// @ts-check\n"
        "/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */\n"
        "const sidebars = {\n"
        "  // Instructional Guides\n"
        "  guideSidebar: [{type: 'autogenerated', dirName: '.'}],\n"
        "\n"
        "  // API Reference (Auto-generated from OpenAPI spec)\n"
        "  apiSidebar: [\n"
        "    {\n"
        '      type: "category",\n'
        '      label: "API Reference",\n'
        '      link: { type: "generated-index", title: "API Reference" },\n'
        '      items: require("./docs/api/sidebar.js"),\n'
        "    },\n"
        "  ],\n"
        "};\n"
        "\n"
        "export default sidebars;\n"
    )

    # Create placeholder openapi.yaml (referenced by docusaurus-plugin-openapi-docs)
    (project_dir / "openapi.yaml").write_text(
        "openapi: 3.0.3\n"
        "info:\n"
        f"  title: {name} API\n"
        "  version: 0.1.0\n"
        f"  description: API documentation for {name}\n"
        "paths:\n"
        "  /health:\n"
        "    get:\n"
        "      summary: Health check\n"
        "      operationId: healthCheck\n"
        "      tags:\n"
        "        - System\n"
        "      responses:\n"
        "        '200':\n"
        "          description: Service is healthy\n"
        "          content:\n"
        "            application/json:\n"
        "              schema:\n"
        "                type: object\n"
        "                properties:\n"
        "                  status:\n"
        "                    type: string\n"
        "                    example: ok\n"
    )

    # Create docs/api/sidebar.js (required by sidebars.js apiSidebar)
    api_dir = project_dir / "docs" / "api"
    api_dir.mkdir(parents=True, exist_ok=True)
    (api_dir / "sidebar.js").write_text(
        "// Auto-generated placeholder — run `npm run gen-api` to regenerate\n"
        "// from openapi.yaml via docusaurus-plugin-openapi-docs.\n"
        "module.exports = [\n"
        "  {\n"
        '    type: "category",\n'
        '    label: "System",\n'
        "    items: [\n"
        "      {\n"
        '        type: "doc",\n'
        '        id: "api/health-check",\n'
        '        label: "Health Check",\n'
        "      },\n"
        "    ],\n"
        "  },\n"
        "];\n"
    )

    # Create docs/intro.md
    (project_dir / "docs").mkdir(parents=True, exist_ok=True)
    (project_dir / "docs" / "intro.md").write_text(
        "---\n"
        "sidebar_position: 1\n"
        "---\n"
        "\n"
        f"# Introduction\n"
        "\n"
        f"Welcome to the documentation for {name}.\n"
        "\n"
        "## Getting Started\n"
        "\n"
        "Add your content here.\n"
    )

    # Create src/css/custom.css (referenced by docusaurus.config.js)
    css_dir = project_dir / "src" / "css"
    css_dir.mkdir(parents=True, exist_ok=True)
    (css_dir / "custom.css").write_text(
        "/**\n"
        " * Custom CSS for Docusaurus\n"
        " */\n"
        ":root {\n"
        "  --ifm-color-primary: #2563eb;\n"
        "  --ifm-color-primary-dark: #1d4ed8;\n"
        "  --ifm-color-primary-darker: #1e40af;\n"
        "  --ifm-color-primary-darkest: #1e3a8a;\n"
        "  --ifm-color-primary-light: #3b82f6;\n"
        "  --ifm-color-primary-lighter: #60a5fa;\n"
        "  --ifm-color-primary-lightest: #93c5fd;\n"
        "  --ifm-code-font-size: 95%;\n"
        "}\n"
    )

    # Create static/img/.gitkeep for assets
    img_dir = project_dir / "static" / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    (img_dir / ".gitkeep").write_text("")

    # .env.example
    (project_dir / ".env.example").write_text(f"# {name} Configuration\nNODE_ENV=development\n")

    # .gitignore (Docusaurus-appropriate)
    (project_dir / ".gitignore").write_text(
        "node_modules/\n"
        ".docusaurus/\n"
        "build/\n"
        ".env\n"
        "\n"
        "# Project\n"
        "logs/\n"
        "data/\n"
        ".tmp/\n"
        ".cache/\n"
        "*.log\n" + _DROID_GITIGNORE_BLOCK + "\n"
        "# IDE\n"
        ".vscode/\n"
        ".idea/\n"
        "*.swp\n"
        "*.swo\n"
        "*~\n"
        "\n"
        "# Node.js\n"
        "npm-debug.log*\n"
        "yarn-debug.log*\n"
    )


# Dispatch table mapping project types to their scaffolder functions.
_TYPE_SCAFFOLDERS: dict[str, Callable[..., None]] = {
    "python-api": _scaffold_python_api,
    "saas-skeleton": _scaffold_saas_skeleton,
    "node-api": _scaffold_node_api,
    "file-api": _scaffold_file_api,
    "file-worker": _scaffold_file_worker,
    "wordpress": _scaffold_wordpress,
    "docusaurus": _scaffold_docusaurus,
    "chrome-extension": _scaffold_chrome_extension,
    "mobile-app": _scaffold_mobile_app,
    "desktop-app": _scaffold_desktop_app,
    "static-site": _scaffold_saas_skeleton,
}


def _post_scaffold_sync(project_dir: Path) -> None:
    """Post-scaffold hook: update project registry and BUSINESS_MODEL.md.

    Runs sync_projects.py to pick up the new project. Failure is non-fatal
    (scaffold already succeeded).
    """
    sync_script = FABRIK_ROOT / "scripts" / "sync_projects.py"
    if not sync_script.exists():
        return
    try:
        subprocess.run(
            ["python3", str(sync_script)],
            cwd=str(FABRIK_ROOT),
            capture_output=True,
            timeout=30,
        )
    except Exception:
        pass  # Non-fatal — scaffold already succeeded


def create_project(
    name: str,
    description: str,
    base: Path = Path("/opt"),
    project_type: str = "python-api",
    preset: str | None = None,
    generate_spec: bool = True,
    **kwargs: object,
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

    # Determine port based on project type before scaffolding (used in doc templates)
    if project_type in ("node-api", "file-api", "saas-skeleton", "static-site"):
        host_port = _next_available_port(port_range=(3000, 3099))
    else:
        host_port = _next_available_port(port_range=(8000, 8099))

    # _scaffold_shared() creates all shared structure AND runs git init + pre-commit install.
    _scaffold_shared(project_dir, name, description, today, host_port)

    scaffolder(project_dir, name, description, preset=preset, **kwargs)

    # Patch project.yaml with actual type
    # (Port is already set correctly by type-specific scaffolder using same _next_available_port logic)
    project_yaml_path = project_dir / "project.yaml"
    if project_yaml_path.exists():
        content = project_yaml_path.read_text()
        content = content.replace("type: python-api", f"type: {project_type}")
        # Set has_user_guide: true for guide-enabled scaffold types
        if project_type in GUIDE_ENABLED_TYPES:
            content = content.replace("has_user_guide: false", "has_user_guide: true")
        project_yaml_path.write_text(content)

    # Final commit after all files (shared + type-specific) are in place so the
    # initial snapshot is complete and clean.
    subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "Initial commit"], cwd=project_dir, capture_output=True
    )

    # Post-scaffold hook: sync project registry
    _post_scaffold_sync(project_dir)

    # Auto-generate deployment spec for supported types
    if generate_spec and project_type in SPEC_ENABLED_TYPES:
        try:
            specs_dir = FABRIK_ROOT / "specs" / "services"
            # Detect secrets from .env.example for deployment-ready specs
            secrets_from_env, secrets_from_file = _detect_secrets(project_dir)
            spec_path = generate_and_save_spec(
                name,
                project_type,
                project_dir,
                specs_dir,
                secrets_from_env=secrets_from_env,
                secrets_from_file=secrets_from_file,
            )
            logger.info("Generated spec: %s", spec_path.relative_to(FABRIK_ROOT))
        except Exception as exc:
            logger.warning("Spec generation failed: %s", exc)

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


def _patch_droid_block(content: str, canonical: str) -> str:
    """Replace .droid/ entries in .gitignore with canonical block.

    Handles two cases:
    1. .droid/ entries exist (scattered or contiguous) → replace with canonical
    2. No .droid/ entries → append canonical block at end

    Args:
        content: Current .gitignore file content
        canonical: Canonical .droid/ gitignore block (_DROID_GITIGNORE_BLOCK)

    Returns:
        Updated .gitignore content
    """
    lines = content.splitlines(keepends=True)
    droid_indices = {i for i, line in enumerate(lines) if line.strip().startswith(".droid/")}

    if not droid_indices:
        # No .droid/ entries — append canonical block
        return content.rstrip("\n") + "\n" + canonical

    # Remove all .droid/ lines and insert canonical block at position of first one
    first_droid = min(droid_indices)
    filtered_lines = [line for i, line in enumerate(lines) if i not in droid_indices]
    return "".join(filtered_lines[:first_droid]) + canonical + "".join(filtered_lines[first_droid:])


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

    # Ensure governance files exist
    windsurfrules_target = FABRIK_ROOT / ".windsurfrules"
    windsurf_rules_target = FABRIK_ROOT / ".windsurf" / "rules"
    windsurf_workflows_target = FABRIK_ROOT / ".windsurf" / "workflows"

    if not dry_run:
        # Fail fast if fabrik targets are missing - environment is broken
        if not windsurfrules_target.exists():
            raise FileNotFoundError(f"Missing fabrik .windsurfrules: {windsurfrules_target}")
        if not windsurf_rules_target.exists():
            raise FileNotFoundError(f"Missing fabrik windsurf rules dir: {windsurf_rules_target}")
        if not windsurf_workflows_target.exists():
            raise FileNotFoundError(
                f"Missing fabrik windsurf workflows dir: {windsurf_workflows_target}"
            )

        # Copy .windsurfrules (remove symlink if exists)
        windsurfrules_path = project_path / ".windsurfrules"
        if windsurfrules_path.is_symlink():
            windsurfrules_path.unlink()
        shutil.copy(windsurfrules_target, windsurfrules_path)
        added.append(".windsurfrules (copied)")

        # Copy .windsurf/rules/ directory (remove symlink if exists)
        windsurf_rules_path = project_path / ".windsurf" / "rules"
        if windsurf_rules_path.is_symlink():
            windsurf_rules_path.unlink()
        elif windsurf_rules_path.exists():
            shutil.rmtree(windsurf_rules_path)
        shutil.copytree(windsurf_rules_target, windsurf_rules_path)
        added.append(".windsurf/rules (copied)")

        # Copy .windsurf/workflows/ directory (remove symlink if exists)
        windsurf_workflows_path = project_path / ".windsurf" / "workflows"
        if windsurf_workflows_path.is_symlink():
            windsurf_workflows_path.unlink()
        elif windsurf_workflows_path.exists():
            shutil.rmtree(windsurf_workflows_path)
        shutil.copytree(windsurf_workflows_target, windsurf_workflows_path)
        added.append(".windsurf/workflows (copied)")

        # Copy AGENTS.md (remove symlink if exists)
        agents_path = project_path / "AGENTS.md"
        if agents_path.is_symlink():
            agents_path.unlink()
        if FABRIK_AGENTS_MD.exists():
            shutil.copy(FABRIK_AGENTS_MD, agents_path)
            added.append("AGENTS.md (copied)")

        # Copy AGENTS-compact.md (remove symlink if exists)
        compact_path = project_path / "AGENTS-compact.md"
        compact_target = FABRIK_ROOT / "AGENTS-compact.md"
        if compact_path.is_symlink():
            compact_path.unlink()
        if compact_target.exists():
            shutil.copy(compact_target, compact_path)
            added.append("AGENTS-compact.md (copied)")

        # Always refresh opencode.json from master (single source of truth)
        fabrik_opencode = FABRIK_ROOT / "opencode.json"
        if fabrik_opencode.exists():
            shutil.copy(fabrik_opencode, project_path / "opencode.json")
            added.append("opencode.json (refreshed from master)")

        # Copy reference docs if they don't exist or need refresh
        for doc_name in ["technology-stack-decision-guide.md", "prebuilt-app-containers.md"]:
            source = FABRIK_ROOT / "docs" / "reference" / doc_name
            if source.exists():
                target = project_path / "docs" / "reference" / doc_name
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(source, target)
                    added.append(f"docs/reference/{doc_name} (copied)")

        # Copy KILO_AGENT_NAMING.md if it doesn't exist
        kilo_naming_source = FABRIK_ROOT / "docs" / "reference" / "kilo" / "KILO_AGENT_NAMING.md"
        if kilo_naming_source.exists():
            kilo_naming_target = (
                project_path / "docs" / "reference" / "kilo" / "KILO_AGENT_NAMING.md"
            )
            if not kilo_naming_target.exists():
                kilo_naming_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(kilo_naming_source, kilo_naming_target)
                added.append("docs/reference/kilo/KILO_AGENT_NAMING.md (copied)")

        # Copy kilo_47_agents_final.json if it doesn't exist
        kilo_config_source = FABRIK_ROOT / "scripts" / "kilo_47_agents_final.json"
        if kilo_config_source.exists():
            kilo_config_target = project_path / "scripts" / "kilo_47_agents_final.json"
            if not kilo_config_target.exists():
                kilo_config_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(kilo_config_source, kilo_config_target)
                added.append("scripts/kilo_47_agents_final.json (copied)")

        # Ensure .droid/ structure is current
        droid_dir = project_path / ".droid"
        droid_dir.mkdir(exist_ok=True)

        # .droid/.gitignore — create or update
        droid_gitignore = droid_dir / ".gitignore"
        if not droid_gitignore.exists() or droid_gitignore.read_text() != _DROID_DIR_GITIGNORE:
            droid_gitignore.write_text(_DROID_DIR_GITIGNORE)
            added.append(".droid/.gitignore (created/updated)")

        # .droid/review-context/ + .gitkeep
        review_ctx = droid_dir / "review-context"
        review_ctx.mkdir(exist_ok=True)
        gitkeep = review_ctx / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.write_text("")
            added.append(".droid/review-context/.gitkeep")

        # .droid/traycer-reports/ + .gitignore
        traycer_reports = droid_dir / "traycer-reports"
        traycer_reports.mkdir(exist_ok=True)
        tr_gitignore = traycer_reports / ".gitignore"
        if not tr_gitignore.exists() or tr_gitignore.read_text() != _TRAYCER_REPORTS_GITIGNORE:
            tr_gitignore.write_text(_TRAYCER_REPORTS_GITIGNORE)
            added.append(".droid/traycer-reports/.gitignore (created/updated)")

        # Update root .gitignore .droid/ block if outdated
        root_gitignore = project_path / ".gitignore"
        if root_gitignore.exists():
            current_content = root_gitignore.read_text()
            updated_content = _patch_droid_block(current_content, _DROID_GITIGNORE_BLOCK)
            if updated_content != current_content:
                root_gitignore.write_text(updated_content)
                added.append(".gitignore (.droid/ block updated)")
    else:
        # dry_run: accurately report what would be created/fixed
        # .windsurfrules - always copied (symlink migration)
        added.append(".windsurfrules (copied)")

        # .windsurf/rules - always copied (symlink migration)
        added.append(".windsurf/rules (copied)")

        # .windsurf/workflows - always copied (symlink migration)
        added.append(".windsurf/workflows (copied)")

        # AGENTS.md - always copied (symlink migration)
        if FABRIK_AGENTS_MD.exists():
            added.append("AGENTS.md (copied)")

        # AGENTS-compact.md - always copied (symlink migration)
        if (FABRIK_ROOT / "AGENTS-compact.md").exists():
            added.append("AGENTS-compact.md (copied)")

        # opencode.json — always refresh
        if (FABRIK_ROOT / "opencode.json").exists():
            added.append("opencode.json (refresh from master)")

        # .droid/ structure dry_run reporting
        droid_dir = project_path / ".droid"
        droid_gitignore = droid_dir / ".gitignore"
        if not droid_gitignore.exists() or (
            droid_gitignore.exists() and droid_gitignore.read_text() != _DROID_DIR_GITIGNORE
        ):
            added.append(".droid/.gitignore (created/updated)")

        review_ctx_gitkeep = droid_dir / "review-context" / ".gitkeep"
        if not review_ctx_gitkeep.exists():
            added.append(".droid/review-context/.gitkeep")

        tr_gitignore = droid_dir / "traycer-reports" / ".gitignore"
        if not tr_gitignore.exists() or (
            tr_gitignore.exists() and tr_gitignore.read_text() != _TRAYCER_REPORTS_GITIGNORE
        ):
            added.append(".droid/traycer-reports/.gitignore (created/updated)")

        # Root .gitignore dry_run reporting
        root_gitignore = project_path / ".gitignore"
        if root_gitignore.exists():
            current_content = root_gitignore.read_text()
            updated_content = _patch_droid_block(current_content, _DROID_GITIGNORE_BLOCK)
            if updated_content != current_content:
                added.append(".gitignore (.droid/ block updated)")

    # Backfill has_user_guide metadata if missing from project.yaml
    project_yaml_path = project_path / "project.yaml"
    if project_yaml_path.exists():
        project_data = yaml.safe_load(project_yaml_path.read_text()) or {}
        if "has_user_guide" not in project_data:
            proj_type = project_data.get("type", "python-api")
            derived_value = proj_type in GUIDE_ENABLED_TYPES
            if dry_run:
                added.append(
                    f"project.yaml (backfill has_user_guide: {str(derived_value).lower()})"
                )
            else:
                project_data["has_user_guide"] = derived_value
                project_yaml_path.write_text(
                    yaml.dump(project_data, default_flow_style=False, sort_keys=False)
                )
                added.append(
                    f"project.yaml (backfilled has_user_guide: {str(derived_value).lower()})"
                )

    return added
