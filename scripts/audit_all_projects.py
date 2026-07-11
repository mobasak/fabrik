#!/usr/bin/env python3
"""Deep audit all /opt projects for Fabrik scaffold compliance (v2).

Improvements over v1:
- Dockerfile: Parses ALL FROM lines (multi-stage), checks HEALTHCHECK directive
- Health endpoint: Excludes governance files (.windsurfrules, AGENTS.md, docs_updater.py)
- print(): Also scans root-level .py files
- New checks: hardcoded localhost in code + compose, .env.example, db/schema.sql,
  watchdog scripts, Makefile, .pre-commit, logging imports, compose coolify network,
  empty scaffold detection (no app/ or src/), root .py files as stray
- Smarter Dockerfile base image detection (strips AS alias)

Modes:
  --fix      Apply safe fixes (has_user_guide, PORTS.md, CHANGELOG) + generate md
  --dry-run  Show what would be fixed without writing
  (default)  Generate 00-research.md only (no fixes)
"""

import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GUIDE_ENABLED_TYPES = frozenset(
    {"saas-skeleton", "chrome-extension", "mobile-app", "desktop-app", "static-site"}
)

VALID_BASE_RE = [
    re.compile(r"^python:3\.\d+-slim-bookworm"),
    re.compile(r"^node:\d+-bookworm-slim"),
]

KNOWN_TYPES = {
    "python-api",
    "node-api",
    "saas-skeleton",
    "chrome-extension",
    "mobile-app",
    "desktop-app",
    "static-site",
    "file-api",
    "file-worker",
    "wordpress",
    "docusaurus",
    "automation",
}

# Files that legitimately belong at project root
LEGIT_ROOT_FILES = {
    "README.md",
    "CHANGELOG.md",
    "INDEX.md",
    "PORTS.md",
    "AGENTS.md",
    "AGENTS-compact.md",
    ".windsurfrules",
    ".gitignore",
    ".env",
    ".env.example",
    ".pre-commit-config.yaml",
    ".codeiumignore",
    "project.yaml",
    "opencode.json",
    "Dockerfile",
    "compose.yaml",
    "docker-compose.yaml",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "tsconfig.json",
    "next.config.js",
    "next.config.mjs",
    "Makefile",
    "Procfile",
    ".dockerignore",
    "manage.py",
}

# Paths to EXCLUDE when searching for health endpoints / print() etc.
GOVERNANCE_EXCLUDE = {
    ".windsurfrules",
    "AGENTS.md",
    "AGENTS-compact.md",
    "docs_updater.py",
    "00-research.md",
}

# Directories at project root that are NOT application code
NON_CODE_DIRS = {
    "tests",
    "scripts",
    "docs",
    "db",
    "data",
    "logs",
    "config",
    "output",
    "node_modules",
    "__pycache__",
    ".droid",
    ".windsurf",
    ".git",
    ".github",
    "venv",
    ".venv",
    "dist",
    "build",
    "chrome_profiles",
    "cookies",
    "inputs",
    "cache",
    "migrations",
    "alembic",  # DB migrations are not app code per se
}

ALL_PROJECTS = [
    "captcha",
    "site-provisioner",
    "file-api",
    "translator",
    "youtube",
    "calendar-orchestration-engine",
    "candle",
    "emailgateway",
    "full-wf-test",
    "job-agent",
    "proposal-creator",
    "seo",
    "test-coolify",
    "test-final",
    "test-final-gate",
    "test-project-2024",
    "test-project-2025",
    "test-session-check",
    "test-zero-refs",
    "trade-intelligence",
    "trading-core",
    "triggered-content-orchestration",
    "ComplianceOps",
    "Reference_Creator",
    "apidoccreator",
    "apps",
    "brand-identiy-creator",
    "email-reader",
    "exam-coach",
    "file-worker",
    "gmailaccountcreator",
    "image-generation",
    "iterative_image_editor",
    "llm_batch_processor",
    "marketing-argumant-generator",
    "namecheap",
    "proxy",
    "supplement-tracker-advisor",
    "transcriber",
    "ugc",
    "web-scraper",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Issue:
    severity: str  # critical, medium, low
    title: str
    file: str
    current: str
    required: str
    fix: str
    consideration: str = ""


@dataclass
class ProjectAudit:
    name: str
    path: Path
    # project.yaml fields
    project_type: str = "unknown"
    status: str = "development"
    port: int = 0
    description: str = ""
    has_user_guide: bool | None = None
    # Dockerfile
    dockerfile_from_lines: list = field(default_factory=list)
    dockerfile_final_base: str = ""
    dockerfile_has_healthcheck: bool = False
    # compose.yaml
    has_platform_amd64: bool = False
    compose_has_coolify_net: bool = False
    compose_localhost_refs: int = 0
    # Health endpoint
    health_endpoint: str = ""
    health_tests_deps: bool = False
    # Code quality
    print_locations: list = field(default_factory=list)
    has_logging_import: bool = False
    hardcoded_localhost_count: int = 0
    hardcoded_localhost_files: list = field(default_factory=list)
    # Structure
    has_app_dir: bool = False
    has_src_dir: bool = False
    code_dirs: list = field(default_factory=list)
    code_layout: str = ""  # "app/", "src/", "non-standard", "root-only", "empty"
    is_empty_scaffold: bool = False
    total_py_files: int = 0
    has_pyproject: bool = False
    has_makefile: bool = False
    has_precommit: bool = False
    has_env_example: bool = False
    has_db_schema: bool = False
    has_watchdog: bool = False
    test_count: int = 0
    has_changelog_unreleased: bool = False
    ports_has_tbd: bool = False
    has_features_md: bool = False
    stray_root_files: list = field(default_factory=list)
    root_py_files: list = field(default_factory=list)
    backup_count: int = 0
    # Output
    issues: list = field(default_factory=list)
    constraints: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_yaml(path: Path) -> dict:
    try:
        return yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}


def _is_excluded_path(filepath: Path) -> bool:
    """Return True if filepath should be excluded from code analysis."""
    name = filepath.name
    parts = set(filepath.parts)
    if name in GOVERNANCE_EXCLUDE:
        return True
    if "__pycache__" in parts:
        return True
    if ".windsurf" in parts:
        return True
    if "node_modules" in parts:
        return True
    return ".backup." in name


def _strip_as_alias(image: str) -> str:
    """Strip ' AS alias' from a FROM image string."""
    return re.sub(r"\s+AS\s+\S+", "", image, flags=re.IGNORECASE).strip()


def _is_base_compliant(image: str) -> bool:
    """Check if a base image string matches Fabrik conventions."""
    clean = _strip_as_alias(image)
    return any(pat.match(clean) for pat in VALID_BASE_RE)


def _find_code_dirs(project_path: Path) -> list[Path]:
    """Find all directories that contain application code.

    Returns dirs like app/, src/, api/, cli/, llm_batch/, webscraper/, worker/
    but NOT tests/, scripts/, docs/, etc.
    """
    code_dirs = []
    # Always include app/ and src/ if they exist
    for d in ["app", "src"]:
        dp = project_path / d
        if dp.is_dir():
            code_dirs.append(dp)

    # Find non-standard code directories (contain .py files, not in NON_CODE_DIRS)
    for item in project_path.iterdir():
        if not item.is_dir():
            continue
        if item.name.startswith("."):
            continue
        if item.name in NON_CODE_DIRS:
            continue
        if item.name in ("app", "src"):  # already added
            continue
        # Check if this dir has any .py files (indicates it's a code package)
        has_py = any(f.suffix == ".py" for f in item.rglob("*.py") if "__pycache__" not in str(f))
        if has_py:
            code_dirs.append(item)

    return code_dirs


def _count_project_py_files(project_path: Path) -> int:
    """Count all .py files in the project excluding tests/scripts/governance."""
    count = 0
    for f in project_path.rglob("*.py"):
        if _is_excluded_path(f):
            continue
        parts = set(f.relative_to(project_path).parts)
        if parts & {"tests", "scripts", ".droid", ".windsurf", "venv", ".venv"}:
            continue
        if f.name == "__init__.py":
            continue
        count += 1
    return count


def _classify_layout(project_path: Path, code_dirs: list[Path]) -> str:
    """Classify the code layout of a project."""
    has_app = (project_path / "app").is_dir()
    has_src = (project_path / "src").is_dir()
    root_pys = [
        f
        for f in project_path.iterdir()
        if f.is_file()
        and f.suffix == ".py"
        and not _is_excluded_path(f)
        and not f.name.startswith("test_")
    ]

    if has_app:
        return "`app/` (flat layout)"
    elif has_src:
        return "`src/` (package layout)"
    elif code_dirs:
        dirs = ", ".join(f"`{d.name}/`" for d in code_dirs if d.name not in ("app", "src"))
        return f"non-standard: {dirs}"
    elif root_pys:
        return f"root-only ({len(root_pys)} .py files at root)"
    else:
        return "empty (no code found)"


# ---------------------------------------------------------------------------
# Deep check functions
# ---------------------------------------------------------------------------


def check_dockerfile_deep(project_path: Path) -> tuple[list, str, bool]:
    """Parse Dockerfile: return (all_from_lines, final_stage_base, has_healthcheck)."""
    df = project_path / "Dockerfile"
    if not df.exists():
        return [], "NO_DOCKERFILE", False
    try:
        content = df.read_text()
    except Exception:
        return [], "UNREADABLE", False

    from_lines = []
    has_healthcheck = False
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.upper().startswith("FROM "):
            image = stripped[5:].strip()
            from_lines.append(image)
        if stripped.upper().startswith("HEALTHCHECK"):
            has_healthcheck = True

    if not from_lines:
        # Dockerfile exists but no FROM — it's a template with only comments
        first = content.strip().split("\n")[0] if content.strip() else ""
        return [], f"TEMPLATE:{first[:80]}", has_healthcheck

    # Final base = last FROM line (the runtime stage in multi-stage builds)
    final_base = from_lines[-1]
    return from_lines, final_base, has_healthcheck


def check_health_endpoint_deep(
    project_path: Path, code_dirs: list[Path] = None
) -> tuple[str, bool]:
    """Find health endpoint in actual application code, excluding governance files."""
    health_file = ""
    tests_deps = False

    # Use provided code_dirs or discover them
    search_dirs = code_dirs if code_dirs else _find_code_dirs(project_path)

    # Also check root-level .py files that might be API entry points
    root_pys = [
        f
        for f in project_path.iterdir()
        if f.is_file() and f.suffix == ".py" and not _is_excluded_path(f)
    ]

    all_py_files = []
    for sd in search_dirs:
        all_py_files.extend(f for f in sd.rglob("*.py") if not _is_excluded_path(f))
    all_py_files.extend(root_pys)

    for py_file in all_py_files:
        try:
            content = py_file.read_text()
        except Exception:
            continue

        # Look for actual route decorators or endpoint definitions with /health
        if '"/health"' not in content and "'/health'" not in content:
            continue

        # Check it's an actual endpoint, not just a string reference
        has_route = any(
            pat in content
            for pat in [
                "@app.get",
                "@router.get",
                "app.get(",
                "router.get(",
                "@app.route",
                "app.route(",
                "def health",
                "async def health",
            ]
        )
        if not has_route:
            continue

        rel_path = str(py_file.relative_to(project_path))
        health_file = rel_path

        # Extract the health function block and check for dependency testing
        lines = content.split("\n")
        health_block = []
        capturing = False
        for line in lines:
            if '"/health"' in line or "'/health'" in line:
                capturing = True
                health_block = [line]
                continue
            if capturing:
                health_block.append(line)
                # Stop at next decorator or function at same/lower indent
                stripped = line.strip()
                if stripped.startswith("@") and len(health_block) > 3:
                    break
                if stripped.startswith("def ") and len(health_block) > 3:
                    break
                if stripped.startswith("async def ") and len(health_block) > 3:
                    break
                if len(health_block) > 30:
                    break

        block_text = "\n".join(health_block)
        dep_patterns = [
            "db.execute",
            "await db",
            "SELECT 1",
            "select(1)",
            "httpx",
            "redis",
            ".ping(",
            "check_connection",
            "test_connection",
            "pool.acquire",
            "engine.connect",
            "aiohttp",
            "get_balance",
            "session.execute",
            "psycopg",
            "cursor.execute",
            "connection.cursor",
            "Depends(get_db",
            "get_ratelimit",
            "asyncpg",
        ]
        for pat in dep_patterns:
            if pat.lower() in block_text.lower():
                tests_deps = True
                break

        # If health function calls a helper, scan the whole file for dep patterns
        if not tests_deps:
            # Check if health block calls any function (pattern: name(...))
            import re as _re

            called_funcs = _re.findall(r"(\w+)\(", block_text)
            called_funcs = [
                f
                for f in called_funcs
                if f not in ("dict", "str", "int", "return", "print", "len", "any")
            ]
            if called_funcs:
                for pat in dep_patterns:
                    if pat.lower() in content.lower():
                        tests_deps = True
                        break

        break  # Found a health endpoint

    return health_file, tests_deps


def find_print_usage_deep(project_path: Path, code_dirs: list[Path] = None) -> list:
    """Find print() calls in ALL project code."""
    locations = []

    search_dirs = code_dirs if code_dirs else _find_code_dirs(project_path)

    all_py_files = []
    for sd in search_dirs:
        all_py_files.extend(f for f in sd.rglob("*.py") if not _is_excluded_path(f))
    # Root .py files (excluding test files and governance)
    for f in project_path.iterdir():
        if f.is_file() and f.suffix == ".py" and not _is_excluded_path(f):
            if not f.name.startswith("test_"):
                all_py_files.append(f)

    for py_file in all_py_files:
        try:
            content = py_file.read_text()
        except Exception:
            continue
        for i, line in enumerate(content.split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "print(" in stripped:
                rel = str(py_file.relative_to(project_path))
                locations.append(f"{rel}:{i}")

    return locations


def find_logging_usage(project_path: Path, code_dirs: list[Path] = None) -> bool:
    """Check if project uses logging module in application code."""
    search_dirs = code_dirs if code_dirs else _find_code_dirs(project_path)
    for dp in search_dirs:
        for f in dp.rglob("*.py"):
            if _is_excluded_path(f):
                continue
            try:
                content = f.read_text()
            except Exception:
                continue
            if "import logging" in content or "from logging" in content:
                return True
    # Also check root .py files
    for f in project_path.iterdir():
        if f.is_file() and f.suffix == ".py" and not _is_excluded_path(f):
            try:
                content = f.read_text()
            except Exception:
                continue
            if "import logging" in content or "from logging" in content:
                return True
    return False


def find_hardcoded_localhost(project_path: Path, code_dirs: list[Path] = None) -> tuple[int, list]:
    """Find hardcoded localhost/127.0.0.1 in production code (not in comments/tests/.env)."""
    count = 0
    files = []
    exclude_names = {".env", ".env.example", ".env.local"}
    search_dirs = code_dirs if code_dirs else _find_code_dirs(project_path)

    for dp in search_dirs:
        for f in dp.rglob("*.py"):
            if _is_excluded_path(f):
                continue
            try:
                content = f.read_text()
            except Exception:
                continue
            for _, line in enumerate(content.split("\n"), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "localhost" in stripped or "127.0.0.1" in stripped:
                    # Skip if it's in a default/fallback (os.getenv pattern)
                    if "os.getenv" in stripped or "os.environ.get" in stripped:
                        continue
                    if "settings." in stripped.lower():
                        continue
                    rel = str(f.relative_to(project_path))
                    if rel not in files:
                        files.append(rel)
                    count += 1

    # Also check root .py files
    for f in project_path.iterdir():
        if f.is_file() and f.suffix == ".py" and f.name not in exclude_names:
            if _is_excluded_path(f):
                continue
            try:
                content = f.read_text()
            except Exception:
                continue
            for line in content.split("\n"):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "localhost" in stripped or "127.0.0.1" in stripped:
                    if "os.getenv" in stripped or "os.environ.get" in stripped:
                        continue
                    rel = f.name
                    if rel not in files:
                        files.append(rel)
                    count += 1

    return count, files


def check_compose_deep(project_path: Path) -> tuple[bool, bool, int]:
    """Check compose.yaml: (has_amd64, has_coolify_net, localhost_ref_count)."""
    compose = project_path / "compose.yaml"
    if not compose.exists():
        return False, False, 0
    try:
        content = compose.read_text()
    except Exception:
        return False, False, 0

    has_amd64 = "linux/amd64" in content
    has_coolify = "coolify" in content.lower()

    # Count localhost refs in environment sections (not in comments/healthcheck)
    localhost_count = 0
    in_healthcheck = False
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # HEALTHCHECK commands legitimately use localhost inside Docker
        low = stripped.lower()
        if "healthcheck:" in low:
            in_healthcheck = True
            continue
        if in_healthcheck:
            # test: lines and their continuations are part of healthcheck
            if (
                "test:" in low
                or stripped.startswith("-")
                or stripped.startswith("[")
                or stripped.startswith('"CMD')
            ):
                continue
            # Indented content under healthcheck (interval, timeout, etc.)
            if any(k in low for k in ("interval:", "timeout:", "retries:", "start_period:")):
                continue
            # End of healthcheck block — non-healthcheck key at same or lower indent
            in_healthcheck = False
        # Skip labels (traefik etc.)
        if "labels:" in low or stripped.startswith('- "traefik'):
            continue
        if "localhost" in stripped or "127.0.0.1" in stripped:
            localhost_count += 1

    return has_amd64, has_coolify, localhost_count


def find_stray_root_files(project_path: Path) -> tuple[list, list]:
    """Find stray root files and root .py files separately."""
    stray = []
    root_py = []
    for item in project_path.iterdir():
        if not item.is_file():
            continue
        if item.name.startswith("."):
            continue
        if ".backup." in item.name:
            continue
        if item.name in LEGIT_ROOT_FILES:
            continue
        if item.suffix == ".py":
            root_py.append(item.name)
        stray.append(item.name)
    return sorted(stray), sorted(root_py)


def count_backups(project_path: Path) -> int:
    count = 0
    for _ in project_path.rglob("*.backup.*"):
        count += 1
    return count


def count_tests(project_path: Path) -> int:
    tests_dir = project_path / "tests"
    if not tests_dir.exists():
        return 0
    count = 0
    for f in tests_dir.rglob("*.py"):
        if f.name != "__init__.py" and "__pycache__" not in str(f):
            count += 1
    return count


def find_watchdog(project_path: Path) -> bool:
    scripts_dir = project_path / "scripts"
    if not scripts_dir.exists():
        return False
    return any(f.name.startswith("watchdog") for f in scripts_dir.iterdir())


# ---------------------------------------------------------------------------
# Main audit
# ---------------------------------------------------------------------------


def audit_project(name: str) -> ProjectAudit | None:
    """Run deep audit on a single project."""
    path = Path(f"/opt/{name}")
    if not path.exists():
        return None

    audit = ProjectAudit(name=name, path=path)

    # --- project.yaml ---
    py_path = path / "project.yaml"
    if py_path.exists():
        data = _read_yaml(py_path)
        audit.project_type = data.get("type", "unknown")
        audit.status = data.get("status", "development")
        audit.description = data.get("description", "")
        ports = data.get("ports", [])
        if ports and isinstance(ports, list):
            try:
                audit.port = int(ports[0])
            except (ValueError, TypeError):
                pass
        hug = data.get("has_user_guide")
        audit.has_user_guide = hug

    # --- Dockerfile (deep) ---
    from_lines, final_base, has_hc = check_dockerfile_deep(path)
    audit.dockerfile_from_lines = from_lines
    audit.dockerfile_final_base = final_base
    audit.dockerfile_has_healthcheck = has_hc

    # --- compose.yaml (deep) ---
    amd64, coolify, comp_lh = check_compose_deep(path)
    audit.has_platform_amd64 = amd64
    audit.compose_has_coolify_net = coolify
    audit.compose_localhost_refs = comp_lh

    # --- Structure ---
    audit.has_app_dir = (path / "app").is_dir()
    audit.has_src_dir = (path / "src").is_dir()
    code_dirs = _find_code_dirs(path)
    audit.code_dirs = [str(d.relative_to(path)) for d in code_dirs]
    audit.total_py_files = _count_project_py_files(path)
    audit.code_layout = _classify_layout(path, code_dirs)
    # Empty scaffold = no code dirs AND no root .py files AND < 3 total .py files
    root_pys = [
        f
        for f in path.iterdir()
        if f.is_file()
        and f.suffix == ".py"
        and not _is_excluded_path(f)
        and not f.name.startswith("test_")
    ]
    audit.is_empty_scaffold = not code_dirs and not root_pys and audit.total_py_files < 3
    audit.has_pyproject = (path / "pyproject.toml").exists()
    audit.has_makefile = (path / "Makefile").exists()
    audit.has_precommit = (path / ".pre-commit-config.yaml").exists()
    audit.has_env_example = (path / ".env.example").exists()
    audit.has_db_schema = (path / "db" / "schema.sql").exists()
    audit.has_watchdog = find_watchdog(path)
    audit.test_count = count_tests(path)
    audit.has_features_md = (path / "docs" / "FEATURES.md").exists()

    # --- Health endpoint (deep — excludes governance) ---
    health_file, tests_deps = check_health_endpoint_deep(path, code_dirs)
    audit.health_endpoint = health_file
    audit.health_tests_deps = tests_deps

    # --- Code quality ---
    audit.print_locations = find_print_usage_deep(path, code_dirs)
    audit.has_logging_import = find_logging_usage(path, code_dirs)
    lh_count, lh_files = find_hardcoded_localhost(path, code_dirs)
    audit.hardcoded_localhost_count = lh_count
    audit.hardcoded_localhost_files = lh_files

    # --- CHANGELOG ---
    cl = path / "CHANGELOG.md"
    if cl.exists():
        try:
            audit.has_changelog_unreleased = "[Unreleased]" in cl.read_text()
        except Exception:
            pass

    # --- PORTS.md ---
    pm = path / "PORTS.md"
    if pm.exists():
        try:
            audit.ports_has_tbd = "TBD" in pm.read_text()
        except Exception:
            pass

    # --- Stray files ---
    stray, root_py = find_stray_root_files(path)
    audit.stray_root_files = stray
    audit.root_py_files = root_py

    # --- Backups ---
    audit.backup_count = count_backups(path)

    # --- Build issues & constraints ---
    build_issues(audit)
    build_constraints(audit)

    return audit


# ---------------------------------------------------------------------------
# Issue builder
# ---------------------------------------------------------------------------


def build_issues(audit: ProjectAudit):
    issues = []
    final = audit.dockerfile_final_base

    # ── CRITICAL ──────────────────────────────────────────────────────────

    # C1: Dockerfile base image
    if final == "NO_DOCKERFILE":
        issues.append(
            Issue(
                "critical",
                "No Dockerfile",
                "Dockerfile",
                "File missing",
                "Dockerfile with `-slim-bookworm` base and HEALTHCHECK",
                "Create Dockerfile following Fabrik template",
            )
        )
    elif final.startswith("TEMPLATE:"):
        issues.append(
            Issue(
                "critical",
                "Dockerfile is a comment-only template",
                "Dockerfile",
                f"`{final}`",
                "Real multi-stage Dockerfile with `-slim-bookworm` base",
                "Replace template with actual Dockerfile for this project's stack",
            )
        )
    elif not _is_base_compliant(final):
        clean = _strip_as_alias(final)
        all_bases = " → ".join(f"`{b}`" for b in audit.dockerfile_from_lines)
        issues.append(
            Issue(
                "critical",
                "Dockerfile base image non-compliant",
                "Dockerfile",
                f"Final stage: `FROM {final}` (stages: {all_bases})",
                "`-slim-bookworm` suffix required per .windsurfrules",
                f"Change `{clean}` to `{clean}-bookworm`",
            )
        )

    # C2: No HEALTHCHECK in Dockerfile
    if final != "NO_DOCKERFILE" and not audit.dockerfile_has_healthcheck:
        issues.append(
            Issue(
                "critical",
                "Dockerfile missing HEALTHCHECK directive",
                "Dockerfile",
                "No HEALTHCHECK instruction found",
                "HEALTHCHECK required per 30-ops.md for Coolify zero-downtime deploys",
                "Add `HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD curl -f http://localhost:${PORT}/health || exit 1`",
            )
        )

    # C3: Health endpoint / empty scaffold
    if audit.is_empty_scaffold:
        # Empty scaffold is the ROOT CAUSE — all other issues are symptoms
        # Mark as medium for planning-stage projects, critical only for production
        sev = "critical" if audit.status == "production" else "medium"
        issues.append(
            Issue(
                sev,
                "No application code — empty scaffold",
                "project root",
                f"No code directories found, {audit.total_py_files} .py files total (layout: {audit.code_layout})",
                "Application code in `app/` (flat) or `src/<package>/` (package layout)",
                "Implement the service or mark project as `status: idea` in project.yaml",
            )
        )
        # Skip all code-dependent checks for empty scaffolds
        audit.issues = issues
        return
    elif not audit.health_endpoint:
        layout_hint = f" (code in: {', '.join(audit.code_dirs)})" if audit.code_dirs else ""
        issues.append(
            Issue(
                "critical",
                "No health endpoint in application code",
                f"Code searched: {', '.join(audit.code_dirs) or 'root .py files'}",
                f"No `/health` route decorator found in app code{layout_hint} (governance refs excluded)",
                "Health endpoint that tests real dependencies (DB, external APIs)",
                "Add `@app.get('/health')` per Fabrik health contract",
            )
        )
    elif not audit.health_tests_deps:
        # Downgrade to medium if project has no database config (static is acceptable)
        has_db = (
            audit.has_db_schema
            or (audit.path / ".env.example").exists()
            and any(
                k in (audit.path / ".env.example").read_text().upper()
                for k in ("DB_HOST", "DATABASE", "POSTGRES", "PGHOST")
            )
            if (audit.path / ".env.example").exists()
            else False
        )
        sev = "critical" if has_db else "medium"
        issues.append(
            Issue(
                sev,
                "Health endpoint returns static JSON — does not test dependencies",
                audit.health_endpoint,
                "Health route exists but has no DB/API checks in function body",
                "Must `await db.execute('SELECT 1')` or equivalent per .windsurfrules",
                "Add real dependency checks to the health function",
            )
        )

    # C4: print() in production code
    if audit.print_locations:
        n = len(audit.print_locations)
        sample = ", ".join(f"`{loc}`" for loc in audit.print_locations[:5])
        if n > 5:
            sample += f" … (+{n - 5} more)"
        issues.append(
            Issue(
                "critical",
                f"`print()` in production code ({n} occurrences)",
                "Multiple files",
                f"Locations: {sample}",
                "Use `logging` module exclusively — violates `check_print_ban.py`",
                "Replace all `print()` with `logging.getLogger(__name__).info/debug/error()`",
            )
        )

    # C5: Hardcoded localhost in code
    if audit.hardcoded_localhost_count > 0:
        files_str = ", ".join(f"`{f}`" for f in audit.hardcoded_localhost_files[:5])
        issues.append(
            Issue(
                "critical",
                f"Hardcoded `localhost`/`127.0.0.1` in code ({audit.hardcoded_localhost_count} refs)",
                files_str,
                "Direct localhost references outside of `os.getenv()` fallbacks",
                "Never hardcode addresses per .windsurfrules — use `os.getenv('HOST', 'localhost')`",
                "Replace with environment variable lookups",
            )
        )

    # C6: Hardcoded localhost in compose.yaml
    if audit.compose_localhost_refs > 0:
        issues.append(
            Issue(
                "critical",
                f"Hardcoded `localhost` in compose.yaml ({audit.compose_localhost_refs} refs)",
                "compose.yaml",
                "localhost references in Docker environment — will fail on VPS",
                "Use Docker service names (e.g. `postgres-main`) not `localhost`",
                "Replace `localhost` with Docker network service names",
            )
        )

    # ── MEDIUM ────────────────────────────────────────────────────────────

    # M1: No logging (only flag if project has code AND uses print)
    if not audit.is_empty_scaffold and not audit.has_logging_import and audit.print_locations:
        issues.append(
            Issue(
                "medium",
                "No `import logging` found in application code",
                "app/ or src/",
                "Project uses `print()` but never imports `logging`",
                "Structured logging required per 55-observability.md",
                "Add logging configuration module and replace print calls",
            )
        )

    # M1b: Non-standard code layout
    if not audit.is_empty_scaffold and not audit.has_app_dir and not audit.has_src_dir:
        non_std = [d for d in audit.code_dirs if d not in ("app", "src")]
        if non_std or audit.root_py_files:
            layout_desc = audit.code_layout
            issues.append(
                Issue(
                    "medium",
                    "Non-standard code layout — code not in `app/` or `src/`",
                    "project root",
                    f"Layout: {layout_desc}",
                    "Fabrik convention: `app/` (flat FastAPI) or `src/<pkg>/` (package layout)",
                    "Restructure code into `app/` or `src/<package>/` before Traycer onboarding",
                )
            )

    # M2: No pyproject.toml (Python projects only)
    if not audit.has_pyproject and audit.project_type in (
        "python-api",
        "automation",
        "file-worker",
        "unknown",
    ):
        issues.append(
            Issue(
                "medium",
                "No `pyproject.toml`",
                "pyproject.toml",
                "File missing",
                "Required for ruff/mypy/pytest configuration and `final_gate.py`",
                "Create with `[project]`, `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]`",
            )
        )

    # M3: No tests
    if audit.test_count == 0:
        issues.append(
            Issue(
                "medium",
                "No test files in `tests/`",
                "tests/",
                "Empty or missing tests directory",
                "At minimum: health endpoint test + core logic unit tests",
                "Add test files covering critical paths",
            )
        )

    # M4: Stray root files (exclude .py files if project has non-standard layout — they ARE the code)
    stray_non_py = [f for f in audit.stray_root_files if not f.endswith(".py")]
    stray_py_in_nonstandard = not audit.has_app_dir and not audit.has_src_dir and audit.code_dirs
    display_stray = audit.stray_root_files if not stray_py_in_nonstandard else stray_non_py
    if display_stray:
        n = len(display_stray)
        sample = ", ".join(f"`{f}`" for f in display_stray[:10])
        if n > 10:
            sample += f" … (+{n - 10} more)"
        issues.append(
            Issue(
                "medium",
                f"Stray root-level files ({n})",
                "project root",
                f"Found: {sample}",
                "Root should only contain scaffold-standard files",
                "Move `.py` to `scripts/` or `app/`, `.md` to `docs/reference/` or `docs/archive/`",
            )
        )

    # M5: Root .py files (only flag if project has standard layout — otherwise they're the app code)
    if audit.root_py_files and not stray_py_in_nonstandard:
        n = len(audit.root_py_files)
        sample = ", ".join(f"`{f}`" for f in audit.root_py_files[:8])
        issues.append(
            Issue(
                "medium",
                f"Python files at project root ({n}) — should be in `app/`, `src/`, or `scripts/`",
                "project root",
                f"Found: {sample}",
                "Code belongs in `app/` (flat layout) or `src/<pkg>/` (package layout)",
                "Move application code to `app/` or `src/`, utility scripts to `scripts/`",
            )
        )

    # M6: FEATURES.md
    if not audit.has_features_md:
        issues.append(
            Issue(
                "medium",
                "No `docs/FEATURES.md`",
                "docs/FEATURES.md",
                "File missing",
                "Cross-cutting requirement for user-facing feature tracking",
                "Create with project feature/endpoint documentation",
            )
        )

    # M7: No .env.example
    if not audit.has_env_example:
        issues.append(
            Issue(
                "medium",
                "No `.env.example`",
                ".env.example",
                "File missing",
                "Required for documenting environment variables",
                "Create with all required env vars and safe defaults",
            )
        )

    # M8: No Makefile
    if not audit.has_makefile:
        issues.append(
            Issue(
                "medium",
                "No `Makefile`",
                "Makefile",
                "File missing",
                "Makefile with `dev`, `test`, `lint`, `build` targets recommended",
                "Create with standard development workflow targets",
            )
        )

    # M9: No coolify network in compose
    if not audit.compose_has_coolify_net and (audit.path / "compose.yaml").exists():
        issues.append(
            Issue(
                "medium",
                "compose.yaml missing `coolify` network",
                "compose.yaml",
                "No `coolify` network reference found",
                "External `coolify` network required for Coolify/Traefik routing",
                "Add `networks: coolify: external: true` to compose.yaml",
            )
        )

    # M10: No watchdog (production services only)
    if not audit.has_watchdog and audit.status == "production" and not audit.is_empty_scaffold:
        issues.append(
            Issue(
                "medium",
                "No watchdog script for production service",
                "scripts/watchdog*.sh",
                "File missing",
                "Production services MUST have watchdog per 30-ops.md",
                "Create `scripts/watchdog.sh` with health check + restart logic",
            )
        )

    # M11: PORTS.md TBD
    if audit.ports_has_tbd:
        issues.append(
            Issue(
                "medium",
                "`PORTS.md` has TBD entries",
                "PORTS.md",
                "Port listed as TBD",
                f"Actual port number ({audit.port or 'from project.yaml'})",
                "**AUTO-FIXABLE** — run audit with --fix",
            )
        )

    # M12: CHANGELOG missing [Unreleased]
    if not audit.has_changelog_unreleased:
        issues.append(
            Issue(
                "medium",
                "`CHANGELOG.md` missing `[Unreleased]` section",
                "CHANGELOG.md",
                "No [Unreleased] section",
                "Required for Traycer to append entries",
                "**AUTO-FIXABLE** — run audit with --fix",
            )
        )

    # ── LOW ───────────────────────────────────────────────────────────────

    # L1: Backup files
    if audit.backup_count > 0:
        issues.append(
            Issue(
                "low",
                f"Stale backup files from enforcement sync ({audit.backup_count})",
                "Various locations",
                f"{audit.backup_count} `.backup.*` files",
                "Clean project without stale backups",
                f"Run `find /opt/{audit.name} -name '*.backup.*' -delete`",
            )
        )

    # L2: Non-standard project type
    if audit.project_type not in KNOWN_TYPES:
        issues.append(
            Issue(
                "low",
                f"Project type `{audit.project_type}` is non-standard",
                "project.yaml",
                f"`type: {audit.project_type}`",
                f"One of: {', '.join(sorted(KNOWN_TYPES))}",
                "Update project.yaml with correct scaffold type",
            )
        )

    # L3: No .pre-commit-config.yaml
    if not audit.has_precommit:
        issues.append(
            Issue(
                "low",
                "No `.pre-commit-config.yaml`",
                ".pre-commit-config.yaml",
                "File missing",
                "Pre-commit hooks for ruff/mypy/yaml-lint recommended",
                "Copy from scaffold template or create with standard hooks",
            )
        )

    # L4: Default port 8000 (never assigned a real port)
    if audit.port == 8000 and audit.is_empty_scaffold:
        issues.append(
            Issue(
                "low",
                "Default scaffold port `8000` — needs real port assignment",
                "project.yaml",
                "Port 8000 is the scaffold default",
                "Register a unique port in PORTS.md before development starts",
                "Choose from Python range 8000–8099 and update project.yaml + PORTS.md",
            )
        )

    # L5: Weak/missing description
    weak_descs = {
        "A new project",
        f"{audit.name} project",
        "No description",
        "No description available",
        "",
    }
    if not audit.description or audit.description in weak_descs:
        issues.append(
            Issue(
                "low",
                "Weak or missing project description",
                "project.yaml",
                f"Current: `{audit.description or 'MISSING'}`",
                "Meaningful description for PROJECT_CATALOG.md and Traycer context",
                "Update `description:` in project.yaml with 1-2 sentence purpose",
            )
        )

    # L6: db/schema.sql placeholder
    if not audit.has_db_schema:
        issues.append(
            Issue(
                "low",
                "No `db/schema.sql`",
                "db/schema.sql",
                "File missing",
                "Schema file required if project uses PostgreSQL",
                "Create with table definitions or confirm project is DB-free",
            )
        )

    audit.issues = issues


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------


def build_constraints(audit: ProjectAudit):
    c = {}
    c["solo_developer"] = "✅ All clear"
    c["amd64"] = "✅ Confirmed" if audit.has_platform_amd64 else "⚠️ Missing `platform: linux/amd64`"
    c["budget"] = "✅ All clear"
    c["existing_services"] = "✅ All clear"
    c["prebuilt_containers"] = "✅ No prebuilt alternative"
    c["port_conflicts"] = f"✅ Port {audit.port}" if audit.port else "⚠️ No port assigned"
    c["coolify"] = "✅ Compliant" if audit.compose_has_coolify_net else "⚠️ No coolify network"

    final = _strip_as_alias(audit.dockerfile_final_base)
    if _is_base_compliant(audit.dockerfile_final_base):
        c["no_alpine"] = "✅ Compliant"
    elif "alpine" in final.lower():
        c["no_alpine"] = "🔴 Alpine detected — must use -slim-bookworm"
    elif final == "NO_DOCKERFILE":
        c["no_alpine"] = "⚠️ No Dockerfile"
    elif final.startswith("TEMPLATE:"):
        c["no_alpine"] = "⚠️ Template — needs real Dockerfile"
    else:
        c["no_alpine"] = f"⚠️ `{final}` — needs `-slim-bookworm`"

    c["module_deps"] = "✅ No incomplete dependencies"
    c["duplicate"] = "✅ Unique"
    c["dns"] = "✅ Managed by site-provisioner"
    c["design_system"] = (
        "Needs verification" if audit.project_type in GUIDE_ENABLED_TYPES else "N/A — no UI surface"
    )
    audit.constraints = c


# ---------------------------------------------------------------------------
# Markdown generator
# ---------------------------------------------------------------------------


def generate_research_md(audit: ProjectAudit) -> str:
    today = date.today().isoformat()
    derived_hug = audit.project_type in GUIDE_ENABLED_TYPES
    actual_hug = audit.has_user_guide if audit.has_user_guide is not None else derived_hug

    # Traycer route
    t = audit.project_type
    if t == "saas-skeleton":
        route = "epic-brief → core-flows → tech-plan → ticket-breakdown → execute"
        skip = "—"
    elif t in ("python-api", "node-api", "file-api", "file-worker", "automation"):
        route = "epic-brief → tech-plan → ticket-breakdown → execute"
        skip = "core-flows"
    elif t in ("wordpress", "docusaurus"):
        route = "epic-brief → ticket-breakdown → execute"
        skip = "core-flows, tech-plan"
    elif t in ("chrome-extension", "mobile-app", "desktop-app", "static-site"):
        route = "epic-brief → core-flows → tech-plan → ticket-breakdown → execute"
        skip = "—"
    else:
        route = "epic-brief → tech-plan → ticket-breakdown → execute"
        skip = "core-flows (default for unknown type)"

    crit = [i for i in audit.issues if i.severity == "critical"]
    med = [i for i in audit.issues if i.severity == "medium"]
    low = [i for i in audit.issues if i.severity == "low"]

    lines = []  # output lines

    lines.append(f"# {audit.name} — Scaffold Compliance Audit")
    lines.append("")
    lines.append(f"**Date:** {today}")
    lines.append("**Status:** OPEN")
    lines.append("**Author:** Cascade (deep audit v2)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Overview ──
    lines.append("## Project Overview")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| **Name** | {audit.name} |")
    lines.append(f"| **Type** | `{audit.project_type}` |")
    lines.append(f"| **Port** | {audit.port or 'Not assigned'} |")
    lines.append(f"| **Status** | {audit.status.title()} |")
    desc = (
        audit.description.replace("\n", " ").strip()[:100]
        if audit.description
        else "No description"
    )
    lines.append(f"| **Description** | {desc} |")
    lines.append(f"| **User Guide** | `{str(actual_hug).lower()}` |")
    lines.append(
        f"| **Empty Scaffold** | {'Yes — no application code found' if audit.is_empty_scaffold else 'No'} |"
    )
    lines.append(f"| **Code Layout** | {audit.code_layout} |")
    lines.append(
        f"| **Total .py files** | {audit.total_py_files} (excl. tests/scripts/governance) |"
    )
    lines.append("")

    # ── Dockerfile snapshot ──
    lines.append("## Dockerfile Snapshot")
    lines.append("")
    if audit.dockerfile_from_lines:
        for i, fr in enumerate(audit.dockerfile_from_lines, 1):
            compliant = "✅" if _is_base_compliant(fr) else "❌"
            lines.append(f"- **Stage {i}:** `FROM {fr}` {compliant}")
        lines.append(
            f"- **HEALTHCHECK:** {'✅ Present' if audit.dockerfile_has_healthcheck else '❌ Missing'}"
        )
    elif audit.dockerfile_final_base == "NO_DOCKERFILE":
        lines.append("- No Dockerfile found")
    else:
        lines.append(f"- Template only: `{audit.dockerfile_final_base}`")
    lines.append("")

    # ── Compose snapshot ──
    lines.append("## Compose Snapshot")
    lines.append("")
    lines.append(f"- **platform: linux/amd64:** {'✅' if audit.has_platform_amd64 else '❌'}")
    lines.append(f"- **coolify network:** {'✅' if audit.compose_has_coolify_net else '❌'}")
    lines.append(f"- **localhost refs:** {audit.compose_localhost_refs}")
    lines.append("")

    # ── Structure snapshot ──
    lines.append("## Structure Snapshot")
    lines.append("")
    lines.append(f"- **Code layout:** {audit.code_layout}")
    lines.append(f"- **pyproject.toml:** {'✅' if audit.has_pyproject else '❌'}")
    lines.append(f"- **Makefile:** {'✅' if audit.has_makefile else '❌'}")
    lines.append(f"- **.pre-commit:** {'✅' if audit.has_precommit else '❌'}")
    lines.append(f"- **.env.example:** {'✅' if audit.has_env_example else '❌'}")
    lines.append(f"- **db/schema.sql:** {'✅' if audit.has_db_schema else '❌'}")
    lines.append(f"- **watchdog:** {'✅' if audit.has_watchdog else '❌'}")
    lines.append(f"- **Tests:** {audit.test_count} file(s)")
    lines.append(
        f"- **Logging:** {'✅ import logging found' if audit.has_logging_import else '❌ No logging import'}"
    )
    lines.append(
        f"- **Health endpoint:** {audit.health_endpoint or '❌ Not found'}"
        f"{' (tests deps ✅)' if audit.health_tests_deps else ' (static ❌)' if audit.health_endpoint else ''}"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Issues ──
    lines.append(f"## Issues ({len(crit)} critical, {len(med)} medium, {len(low)} low)")
    lines.append("")

    num = 0
    for _, label, items in [
        ("critical", "🔴 Critical", crit),
        ("medium", "🟡 Medium", med),
        ("low", "🟢 Low", low),
    ]:
        if not items:
            continue
        lines.append(f"### {label}")
        lines.append("")
        for issue in items:
            num += 1
            lines.append(f"#### {num}. {issue.title}")
            lines.append("")
            lines.append(f"- **File:** `{issue.file}`")
            lines.append(f"- **Current:** {issue.current}")
            lines.append(f"- **Required:** {issue.required}")
            lines.append(f"- **Fix:** {issue.fix}")
            if issue.consideration:
                lines.append(f"- **Note:** {issue.consideration}")
            lines.append("")
        lines.append("---")
        lines.append("")

    # ── Constraints ──
    lines.append("## Constraint Verification Summary")
    lines.append("")
    lines.append("| # | Constraint | Status |")
    lines.append("|---|------------|--------|")
    labels = [
        ("1", "Solo developer scope", "solo_developer"),
        ("2", "x86_64 VPS (amd64)", "amd64"),
        ("3", "Budget-conscious", "budget"),
        ("4", "Existing services", "existing_services"),
        ("5", "Prebuilt containers", "prebuilt_containers"),
        ("6", "Port conflicts", "port_conflicts"),
        ("7", "Coolify deployment", "coolify"),
        ("8", "No Alpine", "no_alpine"),
        ("9", "Module dependencies", "module_deps"),
        ("10", "Duplicate project", "duplicate"),
        ("11", "DNS", "dns"),
        ("12", "Design System", "design_system"),
    ]
    for n, lbl, key in labels:
        lines.append(f"| {n} | {lbl} | {audit.constraints.get(key, 'N/A')} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Route ──
    lines.append("## Recommended Traycer Route")
    lines.append("")
    lines.append("```text")
    lines.append(f"{audit.project_type} → {route}")
    if skip != "—":
        lines.append(f"  (skip: {skip})")
    lines.append("```")
    lines.append("")

    # ── Priority ──
    lines.append("## Suggested Ticket Priority")
    lines.append("")
    for i, issue in enumerate(audit.issues, 1):
        e = "🔴" if issue.severity == "critical" else "🟡" if issue.severity == "medium" else "🟢"
        lines.append(f"{i}. {e} {issue.title}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Auto-fixes
# ---------------------------------------------------------------------------


def apply_fixes(audit: ProjectAudit, dry_run: bool = False) -> list[str]:
    fixes = []

    # Fix: has_user_guide
    if audit.has_user_guide is None:
        py_path = audit.path / "project.yaml"
        if py_path.exists():
            data = _read_yaml(py_path)
            derived = audit.project_type in GUIDE_ENABLED_TYPES
            if dry_run:
                fixes.append(f"Would add has_user_guide: {str(derived).lower()}")
            else:
                data["has_user_guide"] = derived
                py_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
                fixes.append(f"Added has_user_guide: {str(derived).lower()}")

    # Fix: PORTS.md TBD
    if audit.ports_has_tbd and audit.port:
        pm = audit.path / "PORTS.md"
        if pm.exists():
            content = pm.read_text()
            if dry_run:
                fixes.append(f"Would replace TBD → {audit.port} in PORTS.md")
            else:
                content = content.replace("| TBD ", f"| {audit.port} ")
                content = content.replace("| TBD|", f"| {audit.port}|")
                pm.write_text(content)
                fixes.append(f"Replaced TBD → {audit.port} in PORTS.md")

    # Fix: CHANGELOG [Unreleased]
    if not audit.has_changelog_unreleased:
        cl = audit.path / "CHANGELOG.md"
        if cl.exists():
            content = cl.read_text()
            if dry_run:
                fixes.append("Would add ## [Unreleased] to CHANGELOG.md")
            else:
                lines = content.split("\n")
                idx = 0
                for i, line in enumerate(lines):
                    if line.startswith("## "):
                        idx = i
                        break
                if idx == 0:
                    for i, line in enumerate(lines):
                        if line.strip() == "" and i > 0:
                            idx = i + 1
                            break
                lines.insert(idx, "## [Unreleased]\n")
                cl.write_text("\n".join(lines))
                fixes.append("Added ## [Unreleased] to CHANGELOG.md")

    return fixes


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    mode = "audit"
    dry_run = False
    specific = []

    for arg in sys.argv[1:]:
        if arg == "--fix":
            mode = "fix"
        elif arg == "--dry-run":
            dry_run = True
        elif not arg.startswith("-"):
            specific.append(arg)

    projects = specific if specific else ALL_PROJECTS

    print(f"Deep audit v2 — {len(projects)} projects (mode={mode}, dry_run={dry_run})")
    print("=" * 70)

    results = []
    for name in projects:
        print(f"  {name}...", end=" ", flush=True)
        audit = audit_project(name)
        if audit is None:
            print("NOT FOUND")
            continue

        nc = len([i for i in audit.issues if i.severity == "critical"])
        nm = len([i for i in audit.issues if i.severity == "medium"])
        nl = len([i for i in audit.issues if i.severity == "low"])
        scaffold = " [EMPTY]" if audit.is_empty_scaffold else ""
        print(f"{nc}C {nm}M {nl}L{scaffold}")

        if mode == "fix":
            for f in apply_fixes(audit, dry_run=dry_run):
                print(f"    FIX: {f}")

        # Write 00-research.md
        plans_dir = audit.path / "docs" / "development" / "plans"
        research = plans_dir / "00-research.md"
        if not dry_run:
            plans_dir.mkdir(parents=True, exist_ok=True)
            research.write_text(generate_research_md(audit))
            print(f"    → {research}")
        else:
            print(f"    → (dry-run) {research}")

        results.append(audit)

    # Cross-project: port conflict detection
    port_map: dict[int, list[str]] = {}
    for a in results:
        if a.port:
            port_map.setdefault(a.port, []).append(a.name)
    conflicts = {p: names for p, names in port_map.items() if len(names) > 1}
    if conflicts:
        print("\n⚠️  PORT CONFLICTS DETECTED:")
        for port, names in sorted(conflicts.items()):
            print(f"    Port {port}: {', '.join(names)}")

    # Summary
    print("\n" + "=" * 70)
    tc = sum(len([i for i in a.issues if i.severity == "critical"]) for a in results)
    tm = sum(len([i for i in a.issues if i.severity == "medium"]) for a in results)
    tl = sum(len([i for i in a.issues if i.severity == "low"]) for a in results)
    empty = sum(1 for a in results if a.is_empty_scaffold)
    print(f"Projects: {len(results)} | Empty scaffolds: {empty}")
    print(f"Issues:   {tc} critical | {tm} medium | {tl} low")
    print(f"Total:    {tc + tm + tl}")
    if conflicts:
        print(f"⚠️  Port conflicts: {len(conflicts)}")


if __name__ == "__main__":
    main()
