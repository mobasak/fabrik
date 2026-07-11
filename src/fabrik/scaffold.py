"""Project scaffolding - create new projects with full structure.

⚠️  When modifying this file, update these docs to match:
  - docs/workflows/SCAFFOLD_STRUCTURE.md      (tree listing + file tables)
  - docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md (detailed tree + file tables + examples)
"""

# noqa-file: template-generator
# This module EMITS project config into scaffolded projects — its string literals are
# output TEMPLATES (localhost dev URLs, <user>:<pass> example creds, placeholder
# DATABASE_URLs), not this repo's runtime config. check_secrets/check_env_vars would
# otherwise false-flag that template content on every edit; they skip this file via the
# marker above. check_print_ban honors it too (its emitted-code print()s are template
# strings), so three checks now consult the marker — all other gate checks still run.
# Real runtime secrets never live here; they belong in .env.

import json
import logging
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from datetime import date
from pathlib import Path
from types import ModuleType

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
        "python-api-gpu",  # NEW — GPU-aware python-api, hooks gpu_rent into job handler
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

# Scaffold types that produce user-facing documentation (activates user-guide gate)
GUIDE_ENABLED_TYPES = frozenset({"chrome-extension", "static-site"})

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
FILE_API_TEMPLATE_DIR = FABRIK_ROOT / "templates" / "file-api"
FILE_WORKER_TEMPLATE_DIR = FABRIK_ROOT / "templates" / "file-worker"
SAAS_SKELETON_DIR = FABRIK_ROOT / "templates" / "saas-skeleton"
MOBILE_APP_TEMPLATE_DIR = FABRIK_ROOT / "templates" / "mobile-app"
DESKTOP_APP_TEMPLATE_DIR = FABRIK_ROOT / "templates" / "desktop-app"
DOCUSAURUS_TEMPLATE_DIR = FABRIK_ROOT / "templates" / "docusaurus"
I18N_KIT_DIR = FABRIK_ROOT / "templates" / "i18n-kit"
# fabrik-lib is the sibling repo (/opt/fabrik-lib) of FABRIK_ROOT (/opt/fabrik);
# it holds the vendorable lib modules (docs-site, etc.).
FABRIK_LIB_DIR = FABRIK_ROOT.parent / "fabrik-lib"

# Scaffold types that get i18n-kit provisioned automatically.
# Maps project_type → i18n strategy so the copy helper knows which files to place.
I18N_ENABLED_TYPES: dict[str, str] = {
    "saas-skeleton": "react",  # React context provider + Next.js server helpers
    "static-site": "vanilla",  # DOM-based i18n.js loader
    "desktop-app": "vanilla",  # Electron uses Chromium renderer → same DOM loader
    # chrome-extension i18n is owned by @wxt-dev/i18n (src/locales/*.json → native
    # _locales/ at build). No legacy chrome_messages.py/i18n.js provisioning.
    "mobile-app": "rn",  # React Native i18next adapter
    "docusaurus": "docusaurus",  # Docusaurus code.json adapter
}

SHARED_TEMPLATE_MAP = {
    "docs/PROJECT_INDEX_TEMPLATE.md": "INDEX.md",
    "docs/PROJECT_README_TEMPLATE.md": "README.md",
    "docs/CHANGELOG_TEMPLATE.md": "CHANGELOG.md",
    "docs/DOCS_INDEX_TEMPLATE.md": "docs/README.md",
    "docs/QUICKSTART_TEMPLATE.md": "docs/QUICKSTART.md",
    "docs/CONFIGURATION_TEMPLATE.md": "docs/CONFIGURATION.md",
    "docs/TROUBLESHOOTING_TEMPLATE.md": "docs/TROUBLESHOOTING.md",
    "docs/SERVICES_TEMPLATE.md": "docs/SERVICES.md",
    "docs/RESILIENCE_TEMPLATE.md": "docs/RESILIENCE.md",
    "docs/OPERATIONS_TEMPLATE.md": "docs/OPERATIONS.md",
    "docs/BUSINESS_MODEL_TEMPLATE.md": "docs/BUSINESS_MODEL.md",
    "docs/FEATURES_TEMPLATE.md": "docs/FEATURES.md",
    "docs/STRATEGIC_BACKLOG_TEMPLATE.md": "docs/STRATEGIC_BACKLOG.md",
    "docs/LESSONS_LEARNT_TEMPLATE.md": "docs/LESSONS_LEARNT.md",
    "docs/data-contract-template.md": "docs/data-contract.md",  # frozen field dictionary; filled by /fabrik-data-contract
    # kilo-consult-workflow.md removed 2026-07-11 — `kilo consult` superseded by the OpenRouter
    # fabrik-lib consult module; no longer seeded (template archived, kilo_consult.py dormant).
    # Note: Phase docs removed - Traycer Phases replace manual phase tracking
    # Note: tasks.md removed - Traycer UI replaces manual task dashboard
    # Note: PLANS.md and archive/README.md are generated inline, not from templates
}

# Scaffold types where seeding `docs/data-contract.md` would LEAK it: `docusaurus` autogenerates
# its public site from the whole `docs/` tree, so an internal schema/PII field-dictionary would be
# published. We gate ONLY the leak vector — deliberately NOT on "has a database", which is not a
# type property (it's the per-project `--db`/`use_database` flag, and `static-site` maps to the
# saas-skeleton scaffolder so it IS DB-backed). Non-DB types just get a harmless, deletable stub.
_NO_DATA_CONTRACT_TYPES = frozenset({"docusaurus"})


def _load_doc_registry() -> ModuleType | None:
    """Import the canonical doc registry HUB-SIDE. scaffold runs on the hub, so the
    FABRIK_ROOT/scripts/enforcement path is correct here — UNLIKE check_structure.py, which
    runs project-side and uses a same-dir import. Returns the module, or ``None`` on any
    failure (seeding then falls back to the untyped SHARED_TEMPLATE_MAP — never crash a scaffold)."""
    import sys as _sys  # noqa: PLC0415 — lazy, matching this module's import idiom

    # FABRIK_ROOT is the normal hub path; fall back to the real module-relative repo root so
    # the registry (a fixed code asset, not a template) still resolves when a test patches
    # FABRIK_ROOT to a mock templates dir.
    for base in (FABRIK_ROOT, Path(__file__).resolve().parents[2]):
        try:
            enforce_dir = str(base / "scripts" / "enforcement")
            if enforce_dir not in _sys.path:
                _sys.path.insert(0, enforce_dir)
            import _doc_registry  # noqa: PLC0415  (lazy: only needed at scaffold time)

            return _doc_registry
        except Exception:  # noqa: BLE001 — try the next base; never break scaffolding
            continue
    return None


def _type_seeds_doc(reg: ModuleType, project_type: str, dest: str) -> bool:
    """Whether a SHARED_TEMPLATE_MAP destination ``dest`` is seeded for ``project_type``, per
    the canonical registry's type buckets (the SSOT — type-aware seeding).

    - ``universal`` docs → always seeded (byte-identical to prior behavior).
    - ``data`` (data-contract) → seeded, keeping the deliberate all-but-docusaurus behavior
      (the leak guard is applied separately by the caller via ``_NO_DATA_CONTRACT_TYPES``).
      Gating it on ``shape.needs_database`` is unreliable at scaffold time: ``use_database``
      defaults False even for saas-skeleton / static-site, which legitimately carry the
      contract — so a needs_database gate would wrongly strip it from them.
    - ``deployed`` / ``gui`` / ``saas`` docs → seeded only when ``project_type`` is in that
      bucket (a headless python-api no longer gets BUSINESS_MODEL; a client app no longer
      gets SERVICES/OPERATIONS/RESILIENCE).
    - a ``dest`` not in the registry → seeded unconditionally (preserve prior behavior).
    """
    row = next((r for r in reg.PROJECT_DOCS if r.name == dest), None)
    if row is None:
        return True
    for bucket in row.applies_to:
        if bucket in ("universal", "data"):
            return True
        if project_type in reg.TYPE_BUCKETS.get(bucket, frozenset()):
            return True
    return False


def _is_data_doc(reg: ModuleType, dest: str) -> bool:
    """Whether ``dest``'s registry row is in the ``data`` bucket (used to generalize the
    docusaurus leak guard to ANY data-shaped doc, not just data-contract.md by name)."""
    row = next((r for r in reg.PROJECT_DOCS if r.name == dest), None)
    return row is not None and "data" in row.applies_to


def _should_seed_doc(reg: ModuleType | None, project_type: str, dest: str) -> bool:
    """Robust seeding decision — NEVER raises (a registry glitch must not break a scaffold).
    Returns True (seed) when ``reg`` is None or on ANY error (degrade to the prior full-seed
    behavior). Applies the docusaurus data-leak guard for every ``data``-bucket doc, then the
    type-bucket gate."""
    if reg is None:
        return True
    try:
        if project_type in _NO_DATA_CONTRACT_TYPES and _is_data_doc(reg, dest):
            return False  # docs-publisher must never carry a data-shaped doc (leak)
        return _type_seeds_doc(reg, project_type, dest)
    except Exception:  # noqa: BLE001 — degrade to seeding, never crash a scaffold
        return True


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
    "saas-skeleton": _SHARED_REQUIRED_FILES
    + ["compose.yaml", "server/requirements.txt", "server/Dockerfile", "server/db/schema.sql"],
    "static-site": _SHARED_REQUIRED_FILES + ["compose.yaml"],
    "node-api": _SHARED_REQUIRED_FILES + ["Dockerfile", "package.json", "compose.yaml"],
    "file-api": _SHARED_REQUIRED_FILES
    + ["Dockerfile", "package.json", "src/index.js", "compose.yaml"],
    "file-worker": _SHARED_REQUIRED_FILES
    + ["Dockerfile", "requirements.txt", "worker/main.py", "compose.yaml"],
    "docusaurus": _SHARED_REQUIRED_FILES
    + [
        "package.json",
        "docusaurus.config.js",
        "sidebars.js",
        "docs/intro.md",
        "openapi.yaml",
        "docs/api/sidebar.js",
        "compose.yaml",
    ],
    "chrome-extension": _SHARED_REQUIRED_FILES
    + [
        "extension/wxt.config.ts",
        "extension/package.json",
        "Dockerfile",
        "compose.yaml",
        "Makefile",
    ],
    "mobile-app": _SHARED_REQUIRED_FILES + ["package.json", "app.config.ts", "src/app/_layout.tsx"],
    "desktop-app": _SHARED_REQUIRED_FILES + ["package.json", "electron/main.js"],
}

SHARED_DIRS = [
    "docs/guides",
    "docs/reference",
    "docs/reference/kilo",  # Kilo AI agent system docs (synced from fabrik)
    "docs/reference/MD",  # Markdown + AI prompt reference (synced from fabrik)
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
    "backups",  # Credential/config backups (gitignored)
    ".tmp",
    ".cache",
    "output",
    ".droid/review-context",  # Kilo/Traycer review context directory
    ".droid/traycer-reports",  # Traycer report files directory
]

_PYTHON_API_DIRS = ["src"]

SCRIPT_FILES = [
    # Long Command Monitoring System v1.1.0 — see docs/reference/long-command-monitoring.md
    "rund",
    "rundsh",
    "runc",
    "runk",
    "runls",
    "runlast",
    "runwait",
    "runtail",
    "runclean",
    "sync_cascade_backup.sh",
    "sync_extensions.sh",
]

# Master AGENTS.md location
FABRIK_AGENTS_MD = FABRIK_ROOT / "AGENTS.md"

# Master .windsurf/hooks.json location
FABRIK_WINDSURF_HOOKS = FABRIK_ROOT / ".windsurf" / "hooks.json"


def _copy_windsurf_hooks(project_dir: Path) -> bool:
    """Copy .windsurf/hooks.json from fabrik root into project_dir verbatim.

    The Cascade hook commands self-locate the repo root via ``git rev-parse`` (no
    hardcoded ``cwd``), so the file is correct in any project without rewriting —
    matching what sync_enforcement_to_projects.py distributes. Returns True if
    copied, False if the source is missing.
    """
    if not FABRIK_WINDSURF_HOOKS.exists():
        return False
    target = project_dir / ".windsurf" / "hooks.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(FABRIK_WINDSURF_HOOKS, target)
    return True


# Canonical .droid/ gitignore block — shared across all scaffold types
# Runtime files written by:
#   - kilo_code_review.py: reviews/, kilo_models_cache.json, .kilo_cache_last_refresh
#   - generate_kilo_agents.py shell scripts: kilo_usage.jsonl
#   - docs_updater.py: docs_queue/, docs_log/
#   - traycer_write_report.py: traycer-reports/*.md
_DROID_GITIGNORE_BLOCK = (
    ".factory/consultations/\n"
    ".droid/kilo_usage.jsonl\n"
    ".droid/reviews/\n"
    ".droid/kilo_models_cache.json\n"
    ".droid/.kilo_cache_last_refresh\n"
    ".droid/docs_queue/\n"
    ".droid/docs_log/\n"
    ".droid/traycer-reports/*.md\n"
)


# Common gitignore patterns for all project types
def _fabrik_synced_gitignore_block() -> str:
    """Generate the ``.gitignore`` Fabrik-synced block from the shared manifest.

    Single source of truth: ``scripts/fabrik_synced_manifest.py``. The header
    doubles as the "do not edit" warning agents see in the project's .gitignore.
    """
    import sys as _sys

    scripts_dir = str(FABRIK_ROOT / "scripts")
    if scripts_dir not in _sys.path:
        _sys.path.insert(0, scripts_dir)
    from fabrik_synced_manifest import gitignore_block_text

    return str(gitignore_block_text())  # str() pins the type (dynamic-path import is Any to mypy)


def _fabrik_vendored_dirs() -> list[str]:
    """The vendored fabrik-lib module dirs to copy into a new project — read from the SAME manifest
    constant the fleet sync uses (``VENDORED_DIRS``), so scaffold and sync can never drift."""
    import sys as _sys

    scripts_dir = str(FABRIK_ROOT / "scripts")
    if scripts_dir not in _sys.path:
        _sys.path.insert(0, scripts_dir)
    from fabrik_synced_manifest import VENDORED_DIRS

    return list(VENDORED_DIRS)


def _assert_not_hub(target: Path) -> None:
    """Refuse to scaffold/fix the Fabrik hub (/opt/fabrik) or any path inside it.

    The hub is the canonical source of the synced governance files
    (``.windsurf/``, ``CLAUDE.md``, ``AGENTS.md``, ``scripts/run*``, …). Writing
    the *project* synced-gitignore block here would ignore the hub's own sources
    (they would then only be tracked via ``git add -f``). Scaffold and fix
    operate on projects under /opt/<id>, never the hub or any path within it. ``sync_enforcement_to_projects.py``
    already excludes the hub from its project list; this closes the manual path.
    """
    if target.resolve().is_relative_to(FABRIK_ROOT.resolve()):
        raise ValueError(
            f"refusing to scaffold/fix the Fabrik hub or any path inside it ({FABRIK_ROOT}); "
            "scaffold operates on projects under /opt/<id>, never the hub or its subdirs"
        )


_COMMON_GITIGNORE_PATTERNS = (
    (
        "# Secrets (never commit)\n"
        ".env\n"
        ".env.backup\n"
        "*.key\n"
        "*.pem\n"
        "*.token\n"
        "\n"
        "# Logs\n"
        "*.log\n"
        "logs/\n"
        "Logs/\n"
        "\n"
        "# Python\n"
        "__pycache__/\n"
        "*.pyc\n"
        "*.pyo\n"
        ".pytest_cache/\n"
        "*.egg-info/\n"
        "\n"
        "# IDE\n"
        ".vscode/\n"
        ".idea/\n"
        "*.swp\n"
        "*.swo\n"
        "*.code-workspace\n"
        "\n"
        "# OS\n"
        ".DS_Store\n"
        "Thumbs.db\n"
        "\n"
        "# Data directories (large files)\n"
        "Audio_downloads/\n"
        "YT_audio_text/\n"
        "exports/\n"
        "\n"
        "# SQLite databases\n"
        "*.db\n"
        "\n"
        "# Database backups\n"
        "backups/\n"
        "\n"
        "# Legacy migration files (not Alembic)\n"
        "db/migrations/*.sql\n"
        "\n"
        "# Temp files\n"
        "*.tmp\n"
        "/tmp/\n"
        "\n"
    )
    + _fabrik_synced_gitignore_block()
    + (
        "\n"
        "# Ad-hoc research dumps\n"
        "docs/reference/*Search*.md\n"
        "\n"
        "# State files\n"
        "state.json\n"
        "retry_queue.json\n"
        "\n"
        "# Cookie files\n"
        "cookies*.txt\n"
        "\n"
        "# Pipeline test outputs\n"
        "pipeline_output/\n"
    )
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


def _logger_py_content(name: str, package_name: str) -> str:
    """Return the content for a scaffolded logger.py module.

    Shared across python-api, file-worker, and chrome-extension server scaffolds.
    Includes: structlog JSON, UTC timestamps, PII redaction, LOG_LEVEL from env,
    SERVICE_NAME binding.
    """
    return (
        f'"""Structured logging module for {name}.\n'
        f"\n"
        f"Pre-configured structlog logger with JSON output, PII redaction,\n"
        f"and service name binding.\n"
        f"Usage: from {package_name}.logger import get_logger\n"
        f'"""\n'
        f"\n"
        f"import os\n"
        f"from collections.abc import MutableMapping\n"
        f"from typing import Any\n"
        f"\n"
        f"import structlog\n"
        f"\n"
        f"_SENSITIVE_KEYS = frozenset({{\n"
        f'    "api_key", "password", "token", "authorization", "secret",\n'
        f'    "key", "access_token", "refresh_token", "cookie",\n'
        f"}})\n"
        f"\n"
        f"\n"
        f"def _redact_sensitive(\n"
        f"    _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any],\n"
        f") -> MutableMapping[str, Any]:\n"
        f'    """Redact PII/secrets from log entries (GDPR/KVKK safe)."""\n'
        f"    for k in list(event_dict.keys()):\n"
        f"        if k.lower() in _SENSITIVE_KEYS:\n"
        f'            event_dict[k] = "[REDACTED]"\n'
        f"    return event_dict\n"
        f"\n"
        f"\n"
        f"_LOG_LEVELS = {{\n"
        f'    "DEBUG": 10, "INFO": 20, "WARNING": 30, "WARN": 30,\n'
        f'    "ERROR": 40, "CRITICAL": 50,\n'
        f"}}\n"
        f"\n"
        f"\n"
        f"def _setup_logging() -> None:\n"
        f'    """Configure structlog with JSON output, PII redaction, and LOG_LEVEL from env."""\n'
        f'    level = _LOG_LEVELS.get(os.getenv("LOG_LEVEL", "INFO").upper(), 20)\n'
        f"    structlog.configure(\n"
        f"        processors=[\n"
        f"            structlog.contextvars.merge_contextvars,\n"
        f"            structlog.stdlib.add_log_level,\n"
        f'            structlog.processors.TimeStamper(fmt="iso", utc=True),\n'
        f"            _redact_sensitive,\n"
        f"            structlog.processors.JSONRenderer(),\n"
        f"        ],\n"
        f"        wrapper_class=structlog.make_filtering_bound_logger(level),\n"
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


def _write_canonical_compose(
    project_dir: Path,
    name: str,
    *,
    port: int = 8000,
    domain: str | None = None,
    healthcheck_path: str = "/health",
    with_traefik: bool = True,
    extra_labels: tuple[str, ...] = (),
    extra_env_lines: tuple[str, ...] = (),
    healthcheck_kind: str = "http",  # "http" | "tcp" | "process:<pattern>"
    process_pattern: str | None = None,
    memory: str = "512M",
    cpus: str = "0.5",
) -> None:
    """Write the canonical Coolify-compatible ``compose.yaml`` for a scaffold.

    Born from B16/B18/B20-B22: the scaffolded compose is what Coolify
    clones for git-source deploys, so it must be Coolify-correct on the
    first commit. Hand-rolling per scaffolder repeatedly drifted into
    bugs (missing Traefik labels, unexpanded ``${PORT}`` in label
    strings, generic ``app:`` service names, missing ``fabrik``
    network) — this helper centralises the invariants enforced by
    ``tests/test_scaffold_compose_traefik.py``:

    1. Service name == project name (drives Traefik routing + container
       lookup).
    2. ``platform: linux/amd64`` (mandatory for the VPS).
    3. External ``fabrik`` network so Traefik can discover the
       container.
    4. Hardcoded port + Host(...) in Traefik labels — Coolify's compose
       parser does not expand ``${VAR:-default}`` inside label strings.
    5. Healthcheck shaped to the workload (HTTP for web services,
       process probe for workers).

    Args:
        project_dir: Project root; ``compose.yaml`` is written at the top.
        name: Project / service name (must equal ``project_dir.name``).
        port: Container port the service listens on. Hardcoded into
            both the healthcheck and the Traefik loadbalancer label.
        domain: Public hostname used in the ``Host(...)`` rule. Defaults
            to ``<name>.vps1.ocoron.com`` (Fabrik convention).
        healthcheck_path: Path appended to ``http://localhost:<port>``
            for the HTTP healthcheck.
        with_traefik: When False (e.g. ``file-worker``), omit Traefik
            labels entirely. The container still joins the ``fabrik``
            network so Coolify can manage it, but no router is created.
        extra_labels: Additional raw label strings (e.g. CORS or auth
            middlewares) appended verbatim under ``labels:``.
        extra_env_lines: Additional ``- KEY=VALUE`` env entries appended
            verbatim under ``environment:``.
        healthcheck_kind: ``"http"`` (default), ``"tcp"``, or
            ``"process"`` to use ``pgrep -f <process_pattern>``.
        process_pattern: Pattern for the ``process`` healthcheck kind.

    Existing files are overwritten — type-specific scaffolders that
    historically wrote their own broken compose should call this last.
    """
    fqdn = domain or f"{name}.vps1.ocoron.com"

    if healthcheck_kind == "http":
        hc_test = f'["CMD", "curl", "-f", "http://localhost:{port}{healthcheck_path}"]'
    elif healthcheck_kind == "tcp":
        hc_test = f'["CMD-SHELL", "(echo > /dev/tcp/localhost/{port}) >/dev/null 2>&1 || exit 1"]'
    elif healthcheck_kind == "process":
        if not process_pattern:
            raise ValueError("process_pattern is required for healthcheck_kind='process'")
        hc_test = f'["CMD-SHELL", "pgrep -f \\"{process_pattern}\\" || exit 1"]'
    else:
        raise ValueError(f"Unknown healthcheck_kind: {healthcheck_kind!r}")

    env_block = "\n".join(f"      {line}" for line in extra_env_lines) if extra_env_lines else ""
    extra_labels_block = (
        "\n".join(f'      - "{label}"' for label in extra_labels) if extra_labels else ""
    )

    if with_traefik:
        traefik_labels = f"""    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=fabrik"
      - "traefik.http.routers.{name}.rule=Host(`{fqdn}`)"
      - "traefik.http.routers.{name}.entrypoints=websecure"
      - "traefik.http.routers.{name}.tls=true"
      - "traefik.http.routers.{name}.tls.certresolver=letsencrypt"
      # B18: hardcoded port — Coolify's compose parser does not expand
      # ${{VAR:-default}} inside Traefik label strings, so a literal
      # ``${{PORT:-8000}}`` reaches Traefik as the port and 404s the
      # router. Edit alongside the healthcheck above if the app moves.
      - "traefik.http.services.{name}.loadbalancer.server.port={port}"
"""
        if extra_labels_block:
            traefik_labels = traefik_labels + extra_labels_block + "\n"
    else:
        traefik_labels = ""

    # NOTE: do NOT use shell-fallback `${VAR:-default}` here. Coolify
    # auto-extracts compose env keys into its env-vars table on first
    # deploy via `fabrik apply` (no .env uploaded), storing the literal
    # unresolved string. BuildKit's HCL bake parser then rejects `:-`
    # when the env value is forwarded as a `--build-arg`, breaking the
    # build with `Extra characters after interpolation expression`.
    # Use a concrete literal default; runtime override still works via
    # Coolify env config or a project-local .env file.
    env_section = f"""    environment:
      - PORT={port}
      - LOG_LEVEL=INFO
"""
    if env_block:
        env_section = env_section + env_block + "\n"

    content = f"""# compose.yaml - Production-like Docker Compose
# Auto-generated by fabrik scaffold (_write_canonical_compose).
# Used by Coolify (git source) for first-deploy and by ``make docker-smoke``.
#
# B16/B18/B20-B22 invariants (do not regress):
#   - service name == project name (drives Traefik routing + ``docker ps``)
#   - hardcoded port in the loadbalancer label (no ${{VAR:-...}})
#   - Host(...) uses the literal FQDN (no shell-fallback placeholders)
#   - container joins the external ``fabrik`` network for Traefik mesh
#
# See ``tests/test_scaffold_compose_traefik.py`` for the enforced contract.

services:
  {name}:
    build:
      context: .
      dockerfile: Dockerfile
    platform: linux/amd64
    container_name: {name}
{env_section}    healthcheck:
      test: {hc_test}
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    restart: unless-stopped
    # F5: Coolify v4.0.0-beta.459 does not translate its limits_memory UI field
    # into ``deploy.resources.limits`` for build_pack=dockercompose apps, so
    # Docker sees no cap. Declaring the limit here makes it survive redeploys.
    deploy:
      resources:
        limits:
          memory: {memory}
          cpus: '{cpus}'
    networks:
      - fabrik
{traefik_labels}
networks:
  fabrik:
    external: true
"""
    (project_dir / "compose.yaml").write_text(content, encoding="utf-8")


_CI_PYTHON_TYPES = frozenset({"python-api", "python-api-gpu", "file-api"})


def _write_ci_files(project_dir: Path, *, needs_database: bool, needs_web: bool = False) -> None:
    """Emit .github/workflows/ci.yml + scripts/ci_local.sh from the one-source generator
    so CI and its local replica cannot drift (Fix B —
    docs/development/plans/2026-07-01-plan-fabrik-ci-parity.md). Python types only."""
    from fabrik.ci_scaffold import CiConfig, ci_files

    cfg = CiConfig(needs_database=needs_database, needs_web=needs_web)
    for rel, content in ci_files(cfg).items():
        dest = project_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        if dest.suffix == ".sh":
            dest.chmod(0o755)


def _scaffold_shared(
    project_dir: Path,
    name: str,
    description: str,
    today: str,
    host_port: int,
    project_type: str = "",
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

    # Copy shared templates — type-aware, driven by the canonical registry (SSOT).
    _doc_reg = _load_doc_registry()
    for src, dest in SHARED_TEMPLATE_MAP.items():
        # Type-aware seeding: skip a doc whose registry bucket doesn't cover this type (e.g.
        # a headless python-api skips BUSINESS_MODEL; a client app skips SERVICES). Crash-safe:
        # any registry problem degrades to seeding, never breaks a scaffold.
        if not _should_seed_doc(_doc_reg, project_type, dest):
            continue
        # Belt-and-suspenders leak guard (registry-independent): a docs-publisher never gets
        # the data contract even if the registry is unavailable.
        if dest == "docs/data-contract.md" and project_type in _NO_DATA_CONTRACT_TYPES:
            continue
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

    # Copy vendored fabrik-lib modules (the subagents pool → libs/subagents) so every new project — of
    # ANY type — ships with the dev-time pool the /fabrik-* commands import (`from libs.subagents import …`).
    # Driven by the SAME manifest constant the fleet sync uses (VENDORED_DIRS) so the two never drift; the
    # .gitignore "Fabrik-synced" block already lists libs/subagents/ (via gitignore_block_text()), so the
    # copy is gitignored in the project, matching the other synced dirs. Skip bytecode.
    for _vendored_rel in _fabrik_vendored_dirs():
        fabrik_vendored = FABRIK_ROOT / _vendored_rel
        if fabrik_vendored.is_dir():
            shutil.copytree(
                fabrik_vendored,
                project_dir / _vendored_rel,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )

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

    # (.windsurf/hooks.json is copied by _copy_windsurf_hooks() below — Cascade
    # definition-of-done hook that surfaces final_gate.)

    # Copy .claude/ (Claude Code Stop hook — blocks "done" until final_gate is green).
    # Path/cwd-agnostic (resolves project via ${CLAUDE_PROJECT_DIR} + stdin cwd), so the
    # copy is correct verbatim. Mirrors what sync_enforcement_to_projects.py distributes
    # to existing projects (AGENT_HOOK_FILES in fabrik_synced_manifest.py).
    fabrik_claude = FABRIK_ROOT / ".claude"
    if fabrik_claude.exists():
        claude_target = project_dir / ".claude"
        if claude_target.exists():
            shutil.rmtree(claude_target)
        # Copy ONLY the hook essentials (settings.json + hooks/ + commands/agents),
        # NOT Claude Code's runtime/session state — worktrees/ alone can be hundreds
        # of MB (agent worktrees) and would bloat every scaffold; session/cache dirs
        # and any credential files must never ship to a project.
        shutil.copytree(
            fabrik_claude,
            claude_target,
            ignore=shutil.ignore_patterns(
                "worktrees",
                "projects",
                "todos",
                "shell-snapshots",
                "cache",
                "file-history",
                "downloads",
                "debug",
                "ide",
                "statsig",
                "backups",
                "history.jsonl",
                ".credentials.json*",
                "manager-accounts",
                "*.log",
                "__pycache__",
            ),
        )

    # Copy docs/reference/kilo/ directory (Kilo AI agent system docs)
    fabrik_kilo_docs = FABRIK_ROOT / "docs" / "reference" / "kilo"
    if fabrik_kilo_docs.exists():
        kilo_target = project_dir / "docs" / "reference" / "kilo"
        if kilo_target.exists():
            shutil.rmtree(kilo_target)
        shutil.copytree(fabrik_kilo_docs, kilo_target)

    # Copy AGENTS.md (no symlinks - workspace isolation)
    if FABRIK_AGENTS_MD.exists():
        shutil.copy(FABRIK_AGENTS_MD, project_dir / "AGENTS.md")

    # Copy AGENTS-compact.md (no symlinks - workspace isolation)
    fabrik_compact = FABRIK_ROOT / "AGENTS-compact.md"
    if fabrik_compact.exists():
        shutil.copy(fabrik_compact, project_dir / "AGENTS-compact.md")

    # G-B5 (T1-02): Copy CLAUDE.md (no symlinks - workspace isolation).
    # Claude Code reads CLAUDE.md as its always-on bootstrap; without this
    # copy, scaffolded projects under /opt/<name>/ would have no per-project
    # CLAUDE.md and Claude Code would fall back to whatever it finds upward
    # (or nothing). Symmetric to AGENTS-compact.md (Kilo) and .windsurfrules
    # (Cascade) which are already copied.
    fabrik_claude_md = FABRIK_ROOT / "CLAUDE.md"
    if fabrik_claude_md.exists():
        shutil.copy(fabrik_claude_md, project_dir / "CLAUDE.md")

    # Copy the /opt project catalog (so Traycer can check for duplicate projects + wire to
    # siblings). Renamed 2026-07-11 from BUSINESS_MODEL.md → PROJECT_CATALOG.md, and placed at
    # docs/reference/opt-project-catalog.md so it never overwrites the project's own monetization
    # BUSINESS_MODEL.md (which is seeded from its template via SHARED_TEMPLATE_MAP).
    fabrik_catalog = FABRIK_ROOT / "docs" / "PROJECT_CATALOG.md"
    if fabrik_catalog.exists():
        catalog_target = project_dir / "docs" / "reference" / "opt-project-catalog.md"
        catalog_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(fabrik_catalog, catalog_target)

    # Copy PORTS.md (so Traycer can check port conflicts)
    fabrik_ports = FABRIK_ROOT / "PORTS.md"
    if fabrik_ports.exists():
        shutil.copy(fabrik_ports, project_dir / "PORTS.md")

    # Copy .windsurf/hooks.json (rewriting cwd to point at the new project)
    _copy_windsurf_hooks(project_dir)

    # Copy AFCL.md (Agentic Friction & Constraint Log template)
    afcl_template = FABRIK_ROOT / "templates" / "scaffold" / "AFCL_TEMPLATE.md"
    if afcl_template.exists():
        shutil.copy(afcl_template, project_dir / "AFCL.md")

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
        _COMMON_GITIGNORE_PATTERNS + "\n" + _DROID_GITIGNORE_BLOCK + "\n" + "# Python-specific\n"
        "venv/\n"
        ".venv/\n"
        "*.pyd\n"
        ".Python\n"
        "pip-log.txt\n"
        "pip-delete-this-directory.txt\n"
        ".coverage\n"
        "htmlcov/\n"
        "dist/\n"
        "build/\n"
        "*.egg-info/\n"
    )
    # Example .env template with placeholder values (not real credentials)
    (project_dir / ".env.example").write_text(
        f"# {name} Configuration\n"
        f"# Required\n"
        f"PORT=8000\n"
        f"LOG_LEVEL=INFO\n"
        f"\n"
        f"# M2M Authentication — REQUIRED for all Fabrik API services\n"
        f"# Value: copy SERVICE_INTERNAL_SECRET_KEY from /opt/fabrik/.env\n"
        f"# Set via project .env (/opt/<name>/.env, managed by `fabrik apply`); never hardcode the real value here\n"
        f"SERVICE_INTERNAL_SECRET_KEY=change-me-copy-from-fabrik-env\n"
        f"\n"
        f"# Error reporting (GlitchTip) — recommended for production deploys\n"
        f"# Get DSN by running: scripts/provision_glitchtip_project.sh {name}\n"
        f"# Set via project .env (managed by `fabrik apply`). If unset, SDK becomes a no-op (zero overhead).\n"
        f"SENTRY_DSN=\n"  # primary (fabrik orchestrator injects this); GLITCHTIP_DSN below kept as fallback alias
        f"GLITCHTIP_DSN=\n"
        f"ENVIRONMENT=production\n"
        f"\n"
        f"# Optional - uncomment if using database\n"
        f"# DATABASE_URL=postgresql://postgres:<pass>@postgres-main:5432/{name}_dev\n"
        f"# REDIS_URL=redis://redis-main:6379/0\n"
        f"\n"
        f"# Optional - subagent pool flywheel (record_agent_run scoring feeds pick_models)\n"
        f"# INSERT-only writer DSN for fabrik_analytics.subagent_runs; the hub injects the real\n"
        f"# value via `fabrik apply` (create_subagent_ins_role + inject_env). Unset = record_agent_run\n"
        f"# fail-opens (no row written, no crash). The vendored subagents module autoloads this from .env.\n"
        f"# SUBAGENT_RUNS_DSN=postgresql://<writer>:<pass>@postgres-main:5432/fabrik_analytics\n"
        f"# SUBAGENT_PROJECT={name}\n"
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


def _scaffold_fastapi_backend(dest_dir: Path, name: str, package_name: str) -> None:
    """Emit the canonical Fabrik FastAPI backend package into ``dest_dir``.

    Single source of truth for the backend that both ``python-api`` (dest_dir ==
    project root) and ``saas-skeleton`` (dest_dir == ``project/server``) emit:
    ``src/<package_name>/{__init__,internal_auth,metrics,glitchtip_init,logger,
    pause_state,middleware,main}.py``. Pure file emission — no venv/tests/
    template side effects; callers add those and their own requirements.txt.
    """
    # Create starter src/<package_name>/ package with logger, middleware, and main
    package_dir = dest_dir / "src" / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "__init__.py").write_text("")

    # internal_auth.py — canonical M2M auth module (X-Internal-Token pattern)
    # Agents: always use require_internal_token from this module, never inline auth logic
    (package_dir / "internal_auth.py").write_text(
        '"""\n'
        "Canonical internal token auth — shared M2M auth pattern for all Fabrik services.\n"
        "Header:  X-Internal-Token\n"
        "Env var: SERVICE_INTERNAL_SECRET_KEY\n"
        "\n"
        "Usage:\n"
        f"  from {package_name}.internal_auth import require_internal_token\n"
        "  # In router: dependencies=[Depends(require_internal_token)]\n"
        '"""\n'
        "import hmac\n"
        "import os\n"
        "\n"
        "from fastapi import HTTPException, Security\n"
        "from fastapi.security.api_key import APIKeyHeader\n"
        "\n"
        '_HEADER = APIKeyHeader(name="X-Internal-Token", auto_error=False)\n'
        "\n"
        "\n"
        "def require_internal_token(token: str = Security(_HEADER)) -> str:\n"
        '    """FastAPI dependency — validates X-Internal-Token in constant time."""\n'
        '    expected = os.getenv("SERVICE_INTERNAL_SECRET_KEY", "")\n'
        "    if not token or not expected:\n"
        '        raise HTTPException(status_code=403, detail="Missing or invalid token")\n'
        "    if not hmac.compare_digest(token, expected):\n"
        '        raise HTTPException(status_code=403, detail="Missing or invalid token")\n'
        "    return token\n"
    )
    # metrics.py — Prometheus business metrics registry
    # Usage: from {pkg}.metrics import REQUEST_COUNT, ERROR_COUNT, record_request
    # Wire to FastAPI: app.mount("/metrics", make_asgi_app())
    (package_dir / "metrics.py").write_text(
        f'''"""
Prometheus metrics for {name}.

Business metrics — add counters/histograms here for domain events.
Exposed at /metrics (wired in main.py lifespan).

Usage example:
    from {package_name}.metrics import REQUEST_COUNT, PROCESSING_SECONDS
    REQUEST_COUNT.labels(endpoint="/api/translate", status="success").inc()
"""

from prometheus_client import CollectorRegistry, Counter, Histogram, make_asgi_app

REGISTRY = CollectorRegistry()

# ── Core request metrics (all services) ──────────────────────────────────────
REQUEST_COUNT = Counter(
    "fabrik_requests_total",
    "Total HTTP requests processed",
    ["endpoint", "status"],
    registry=REGISTRY,
)

REQUEST_DURATION = Histogram(
    "fabrik_request_duration_seconds",
    "HTTP request duration in seconds",
    ["endpoint"],
    registry=REGISTRY,
)

# ── Business metrics (customize per service) ──────────────────────────────────
# Example: rename/add counters relevant to this service's domain
PROCESSING_COUNT = Counter(
    "fabrik_{name.replace("-", "_")}_processed_total",
    "Items successfully processed",
    ["type"],
    registry=REGISTRY,
)

ERROR_COUNT = Counter(
    "fabrik_{name.replace("-", "_")}_errors_total",
    "Processing errors",
    ["type", "reason"],
    registry=REGISTRY,
)

ACTIVE_JOBS = Histogram(
    "fabrik_{name.replace("-", "_")}_job_duration_seconds",
    "Job processing duration in seconds",
    ["job_type"],
    registry=REGISTRY,
)


def metrics_app():
    """Return ASGI app for /metrics endpoint. Mount in main.py lifespan."""
    return make_asgi_app(registry=REGISTRY)
'''
    )

    # glitchtip_init.py — GlitchTip / Sentry SDK initialization (no-op if GLITCHTIP_DSN unset)
    # Errors auto-report to GlitchTip when DSN is set in environment.
    # Wire by importing this module BEFORE creating FastAPI app in main.py.
    (package_dir / "glitchtip_init.py").write_text('''"""GlitchTip / Sentry SDK initialization.

If SENTRY_DSN (preferred, fabrik standard) or GLITCHTIP_DSN is set, errors and traces auto-report to GlitchTip.
If unset, init is a no-op (zero overhead, zero exceptions).

Import this module BEFORE FastAPI app creation in main.py:
    from {pkg}.glitchtip_init import init_glitchtip
    init_glitchtip()  # call once at module load
    app = FastAPI(...)

Provision a project + DSN: scripts/provision_glitchtip_project.sh <service-name>
Push DSN to Coolify env on deploy.
"""
import os


def init_glitchtip() -> bool:
    """Initialize Sentry SDK pointed at GlitchTip.

    Returns True if init ran (DSN was set), False if no-op.
    Safe to call multiple times — Sentry SDK handles re-init internally.
    """
    dsn = (os.environ.get("SENTRY_DSN") or os.environ.get("GLITCHTIP_DSN") or "").strip()
    if not dsn:
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        # sentry-sdk not installed; no-op rather than crash
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("ENVIRONMENT", "production"),
        release=os.environ.get("GIT_SHA") or os.environ.get("COOLIFY_DEPLOYMENT_UUID"),
        # Lean defaults — keep volume manageable on shared GlitchTip
        traces_sample_rate=float(os.environ.get("GLITCHTIP_TRACES_SAMPLE_RATE", "0.05")),
        profiles_sample_rate=float(os.environ.get("GLITCHTIP_PROFILES_SAMPLE_RATE", "0.0")),
        send_default_pii=False,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            StarletteIntegration(transaction_style="endpoint"),
        ],
    )
    return True
''')

    # logger.py — structlog JSON logger with PII redaction, UTC timestamps, LOG_LEVEL from env
    (package_dir / "logger.py").write_text(_logger_py_content(name, package_name))

    # pause_state.py — pause-flag primitives for worker resilience (see 58-resilience.md)
    # Copied from template; projects customize TRANSIENT_PATTERNS for their dependencies.
    pause_src = TEMPLATE_DIR / "python" / "pause_state.py"
    if pause_src.exists():
        shutil.copy2(pause_src, package_dir / "pause_state.py")

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
        f"from {package_name}.glitchtip_init import init_glitchtip\n"
        f"from {package_name}.logger import get_logger\n"
        f"from {package_name}.metrics import metrics_app\n"
        f"from {package_name}.middleware import CorrelationMiddleware\n"
        f"\n"
        f"# Initialize error reporting BEFORE app construction so SDK\n"
        f"# instruments FastAPI from the very first request.\n"
        f"init_glitchtip()\n"
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
        f"# Prometheus metrics endpoint — scraped by Prometheus at /metrics\n"
        f"# Add prometheus_scrape=true label in Coolify if using docker_sd_config\n"
        f'app.mount("/metrics", metrics_app())\n'
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


def _scaffold_python_api(project_dir: Path, name: str, description: str, **kwargs: object) -> None:
    """Create Python API-specific project structure."""
    package_name = _get_package_name(name)
    today = date.today().isoformat()

    # Create Python API-specific directories
    for d in _PYTHON_API_DIRS:
        (project_dir / d).mkdir(parents=True, exist_ok=True)

    # Copy Python API templates
    # B16: ``<domain>`` is substituted into compose.yaml.template's Traefik
    # labels so the scaffolded compose carries the correct Host(...) rule.
    # Default Fabrik convention is ``<name>.vps1.ocoron.com``; users can
    # edit the file post-scaffold for staging/custom domains.
    domain = f"{name}.vps1.ocoron.com"
    for src, dest in _PYTHON_API_TEMPLATE_MAP.items():
        src_path = TEMPLATE_DIR / src
        if src_path.exists():
            content = src_path.read_text()
            for old, new in [
                ("[Project Name]", name),
                ("<project>", name),  # QUICKSTART paths + compose service name
                ("project-name", name),  # pyproject.toml
                ("myproject", name),  # Makefile
                ("[package_name]", package_name),  # README imports
                ("<package_name>", package_name),  # QUICKSTART imports
                ("<domain>", domain),  # compose Traefik labels (B16)
                ("YYYY-MM-DD", today),
                ("[Brief description]", description),
                ("[One-line description]", description),
                ("Brief project description", description),  # pyproject.toml
            ]:
                content = content.replace(old, new)
            (project_dir / dest).write_text(content)

    # Create requirements.txt (production dependencies only)
    (project_dir / "requirements.txt").write_text(
        "fastapi>=0.115.0\nuvicorn[standard]>=0.32.0\npydantic>=2.9.0\npython-dotenv>=1.0.0\nhttpx>=0.28.0\nstructlog>=24.0.0\nprometheus-client>=0.21.0\nsentry-sdk[fastapi]>=2.18.0\n"
    )

    # Create requirements-dev.txt (includes dev dependencies)
    # pytest + pytest-asyncio are explicit because tests/test_health.py is
    # scaffolded alongside this file; relying on transitive resolution via
    # semgrep etc. is brittle across environments.
    (project_dir / "requirements-dev.txt").write_text(
        "-r requirements.txt\n"
        "pytest>=8.3.0\n"
        "pytest-asyncio>=0.24.0\n"
        "ruff\n"
        "mypy\n"
        "bandit\n"
        "semgrep\n"
        "sqlfluff\n"
        "vulture\n"
    )

    # Emit the canonical FastAPI backend package (shared with saas-skeleton,
    # via _scaffold_fastapi_backend). Keeps one backend generator.
    _scaffold_fastapi_backend(project_dir, name, package_name)

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
            f"# Database (managed by Fabrik orchestrator on VPS via postgres registrar)\n# Set via project .env (managed by `fabrik apply`): POSTGRES_PASSWORD\nDATABASE_URL=postgresql://postgres:${{POSTGRES_PASSWORD}}@postgres-main:5432/{name.replace('-', '_')}\n",
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


# ───────────────────────────────────────────────────────────────────────────
# saas-skeleton backend (FastAPI) — multi-tenant + auth + jobs tier
#
# Emitted under ``<project>/server`` by ``_scaffold_saas_backend``. The base
# package comes from ``_scaffold_fastapi_backend`` (shared with python-api);
# the saas layer adds db/schema.sql (RLS + jobs queue), tenant.py, auth.py,
# worker.py, and a saas-flavoured main.py. Grounded in .windsurf/rules:
# 95-multi-tenant-saas, 35-security-auth, 15-api-contracts, 75-workers-jobs.
# Bodies use __PKG__/__NAME__ tokens (not f-strings) to avoid brace escaping.
# ───────────────────────────────────────────────────────────────────────────

_SAAS_SERVER_REQUIREMENTS = (
    "fastapi>=0.115.0\n"
    "uvicorn[standard]>=0.32.0\n"
    "pydantic[email]>=2.9.0\n"  # [email] => email-validator, for fastapi_user_auth EmailStr
    "python-dotenv>=1.0.0\n"
    "httpx>=0.28.0\n"
    "structlog>=24.0.0\n"
    "prometheus-client>=0.21.0\n"
    "sentry-sdk[fastapi]>=2.18.0\n"
    "asyncpg>=0.30.0\n"
    "pyjwt[crypto]>=2.9.0\n"
    # --- vendored fastapi_user_auth (Pattern A) runtime deps ---
    "sqlalchemy[asyncio]>=2.0\n"
    "argon2-cffi>=23.1\n"  # password hashing (core/35)
    "pydantic-settings>=2.2\n"  # module Settings (BaseSettings)
    "uuid-utils>=0.10\n"  # UUIDv7 PKs (core/25)
    "redis>=5.0\n"  # jti denylist / instant revocation
)

_SAAS_SCHEMA_SQL = """-- schema.sql — multi-tenant schema for __NAME__ (PostgreSQL, RLS fail-closed).
-- Per .windsurf/rules/saas/95-multi-tenant-saas.md (RLS) + core/75-workers-jobs.md (queue).
-- Apply once after the DB is provisioned:  psql "$DATABASE_URL" -f db/schema.sql
-- (Fabrik runs NO automatic migrations — you apply this yourself.)
--
-- IMPORTANT — Row-Level Security only applies to a NON-superuser role. Fabrik's
-- postgres registrar provisions a dedicated, non-superuser role that OWNS this
-- database and injects its DATABASE_URL, so the app (api + worker) connects as
-- that role and apply this schema as that role (it owns the tables → FORCE RLS
-- bites). Do NOT connect as the postgres superuser — it bypasses RLS entirely.
-- ``gen_random_uuid()`` is built into PostgreSQL 13+. ``citext`` is a TRUSTED
-- extension (PG13+), so the DB-owning role can CREATE it without superuser — no
-- registrar step needed. It backs the case-insensitive ``users.email`` UNIQUE.

-- Auth (Pattern A — this app is the IdP; see src/__PKG__/auth.py) -------------
-- Case-insensitive email UNIQUE via citext (trusted extension; owner-creatable).
CREATE EXTENSION IF NOT EXISTS citext;

-- Tenants — the isolation boundary -------------------------------------------
-- NOTE (Pattern-A onboarding): /auth signup creates a ``users`` row ONLY — it does
-- NOT create a tenant or membership (the module has no tenant endpoint; onboarding is
-- app work per saas/95). Until you wire tenant + membership creation, a new user's
-- login WITH a tenant 403s (no membership) and tenant-scoped queries return nothing
-- (empty tenant context => current_tenant_id() NULL => RLS denies). Wire it here.
CREATE TABLE IF NOT EXISTS tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Users — app-owned identities (Pattern A). PKs are UUIDv7 supplied by the app
-- (uuid_utils); the gen_random_uuid() default is a harmless fallback.
CREATE TABLE IF NOT EXISTS users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email          CITEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,
    email_verified BOOLEAN NOT NULL DEFAULT false,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Membership — which app user belongs to which tenant ------------------------
CREATE TABLE IF NOT EXISTS memberships (
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,  -- app users.id (JWT ``sub``)
    role        TEXT NOT NULL DEFAULT 'member',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_memberships_user ON memberships(user_id);

-- Auth tokens (Pattern A) — opaque refresh tokens + email-verify/reset nonces.
-- Tokens are app-generated (secrets.token_urlsafe); no DB default needed.
CREATE TABLE IF NOT EXISTS refresh_tokens (
    token       TEXT PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id   UUID REFERENCES tenants(id) ON DELETE CASCADE,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_refresh_user ON refresh_tokens(user_id);

CREATE TABLE IF NOT EXISTS email_verify_tokens (
    token       TEXT PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at  TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    token       TEXT PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at  TIMESTAMPTZ NOT NULL
);

-- Fail-closed tenant resolver: NULL when app.tenant_id is unset/blank --------
-- NULLIF(...,'')::UUID => NULL => every tenant_isolation policy DENIES.
-- LANGUAGE sql (inlinable → the planner folds it into the RLS predicate; fastest). The
-- GUC is only ever set from a signed-JWT ``tid`` (a valid UUID) or '' (empty), so the
-- ``::UUID`` cast never sees malformed input in practice; empty/unset => NULL => deny.
CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS UUID AS $$
    SELECT NULLIF(current_setting('app.tenant_id', TRUE), '')::UUID;
$$ LANGUAGE sql STABLE;

-- Native-mode companion (fastapi_user_auth rls/native.sql): the current user id from
-- app.user_id, for user-scoped policies you add. Fail-closed like current_tenant_id().
CREATE OR REPLACE FUNCTION current_user_id() RETURNS UUID AS $$
    SELECT NULLIF(current_setting('app.user_id', TRUE), '')::UUID;
$$ LANGUAGE sql STABLE;

-- Example tenant-scoped resource (the wired CRUD pattern) -------------------
CREATE TABLE IF NOT EXISTS widgets (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_widgets_tenant ON widgets(tenant_id);

ALTER TABLE widgets ENABLE ROW LEVEL SECURITY;
ALTER TABLE widgets FORCE  ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON widgets;
CREATE POLICY tenant_isolation ON widgets
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

-- Background-jobs queue: PostgreSQL IS the broker (no Celery/Rabbit/Redis) ---
-- Claimed with FOR UPDATE SKIP LOCKED; NOTIFY wakes idle workers instantly.
-- NOT RLS-protected: the worker (the DB-owning role) drains across tenants; the
-- API filters by tenant_id explicitly when it enqueues/reads its own jobs.
CREATE TABLE IF NOT EXISTS jobs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID REFERENCES tenants(id) ON DELETE CASCADE,
    task_name   TEXT NOT NULL,
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    attempts    INT NOT NULL DEFAULT 0,
    max_retries INT NOT NULL DEFAULT 5,
    run_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Mandatory partial index — without it, claim queries full-scan (75 §Schema).
CREATE INDEX IF NOT EXISTS idx_jobs_pending ON jobs (run_at) WHERE status = 'pending';

-- No GRANTs needed: the API and worker both connect as the DB-owning role, which
-- already owns ``jobs``. The API filters by tenant_id explicitly when it
-- enqueues/reads; the worker drains across tenants (jobs is not RLS-protected).

-- Instant wake-up: NOTIFY on insert; the worker LISTENs (75 §Worker Wake-Up).
CREATE OR REPLACE FUNCTION notify_job_inserted() RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('job_inserted', NEW.id::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_job_inserted ON jobs;
CREATE TRIGGER trg_job_inserted AFTER INSERT ON jobs
    FOR EACH ROW EXECUTE FUNCTION notify_job_inserted();
"""

_SAAS_TENANT_PY = '''"""Tenant context propagation for __NAME__ (multi-tenant RLS).

Per .windsurf/rules/saas/95-multi-tenant-saas.md: resolve the tenant per
request, validate membership (403 if the user is not a member), expose it via
a ContextVar, and ``SET LOCAL app.tenant_id`` at the start of every DB
transaction so PostgreSQL RLS appends the tenant filter automatically.
Developers then write plain queries — the ``tenant_isolation`` policy scopes
them transparently.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from __PKG__.auth import decode_token, token_revoked

# Empty default => current_setting('app.tenant_id') is '' => current_tenant_id()
# returns NULL => RLS denies. The context is fail-closed by construction.
tenant_context: ContextVar[str] = ContextVar("tenant_id", default="")
# Native-mode companion GUC (app.user_id) for current_user_id() (fastapi_user_auth
# rls/native.sql). Empty default = fail-closed, same as the tenant context.
user_context: ContextVar[str] = ContextVar("user_id", default="")

# Paths that never carry a tenant (health/metrics/landing) — pass straight through.
# ``/auth/*`` (login/signup/refresh/reset) is the IdP router: it manages its own DB
# sessions and must NOT be gated by tenant resolution, so it is skipped here too.
_PUBLIC_PREFIXES = ("/api/health", "/health", "/metrics", "/")


def get_tenant_id() -> str:
    """Return the current request's tenant id, or '' when unset (RLS denies)."""
    return tenant_context.get()


def get_user_id() -> str:
    """Return the current request's user id, or '' when unset."""
    return user_context.get()


def _problem(status: int, title: str, detail: str, request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": "about:blank",
            "title": title,
            "status": status,
            "detail": detail,
            "instance": request.url.path,
        },
    )


async def _is_member(tenant_id: str, user_id: str) -> bool:
    """Validate that ``user_id`` belongs to ``tenant_id`` — FAIL-CLOSED by default.

    Returns ``False`` until you wire a real lookup against the ``memberships``
    table (``SELECT 1 FROM memberships WHERE tenant_id=$1 AND user_id=$2``). This
    gates ONLY the untrusted ``X-Tenant-ID`` header path; a tenant carried on the
    cryptographically-validated JWT is trusted without this check. Defaulting to
    ``False`` means the header path is DENIED until you implement it, rather than
    letting any authenticated user cross into any tenant by setting a header.
    """
    return False


class TenantMiddleware(BaseHTTPMiddleware):
    """Decode our access token, resolve + validate the tenant, bind the ContextVars.

    Tenant resolution is fail-closed and trust-aware:
      * ``tid`` on the **validated JWT** is trusted (this service signed it) —
        bound directly.
      * ``X-Tenant-ID`` **header** is user-controlled and untrusted — bound only
        if ``_is_member`` confirms membership (403 otherwise; denied by default).
      * neither present → empty tenant → RLS denies every row (fail-closed).
    A present-but-invalid bearer token is rejected with 401; public paths skip auth.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if (
            request.url.path in _PUBLIC_PREFIXES
            or request.url.path.startswith("/metrics")
            or request.url.path.startswith("/auth/")  # IdP router; NOT "/authors" etc.
        ):
            return await call_next(request)

        claims: dict[str, Any] = {}
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            try:
                claims = decode_token(auth_header[7:].strip())
            except Exception:  # noqa: BLE001 — any decode failure is a 401
                return _problem(401, "Unauthorized", "Invalid or expired token", request)
            # Revocation must bite on EVERY protected route, not just /auth (the module's
            # current_user only guards /auth/logout). A logged-out / denylisted jti is 401.
            if await token_revoked(claims.get("jti", "")):
                return _problem(401, "Unauthorized", "Token has been revoked", request)
        request.state.jwt_claims = claims

        user_id = claims.get("sub", "") if claims else ""
        claim_tenant = (claims.get("tid") or "") if claims else ""
        if claim_tenant:
            tenant_id = claim_tenant  # trusted: signed into the JWT
        elif claims:
            # Authenticated but no tenant claim — the untrusted X-Tenant-ID header
            # is honoured only after an explicit membership check (denied by default).
            header_tenant = request.headers.get("X-Tenant-ID", "")
            if header_tenant and not await _is_member(header_tenant, user_id):
                return _problem(403, "Forbidden", "Not a member of this tenant", request)
            tenant_id = header_tenant
        else:
            # Unauthenticated — no tenant; require_user issues a clean 401 on
            # protected routes, and RLS denies everything in the meantime.
            tenant_id = ""

        ctx_token = tenant_context.set(tenant_id)
        usr_token = user_context.set(user_id)
        try:
            return await call_next(request)
        finally:
            tenant_context.reset(ctx_token)
            user_context.reset(usr_token)


async def apply_tenant(conn: Any) -> None:
    """Scope a transaction to the current tenant — call FIRST in every txn::

        async with pool.acquire() as conn:
            async with conn.transaction():
                await apply_tenant(conn)
                rows = await conn.fetch("SELECT * FROM widgets")  # RLS-filtered

    Sets ``app.tenant_id`` + ``app.user_id`` (``LOCAL`` → reset at COMMIT) so
    ``current_tenant_id()`` / ``current_user_id()`` resolve them and the
    ``tenant_isolation`` RLS policy filters the query. No role switch is needed: the
    app already connects as Fabrik's dedicated, NON-superuser DB-owning role, so RLS
    (``FORCE``) applies directly. An empty tenant context → ``current_tenant_id()``
    is NULL → the policy denies every row (fail-closed).
    """
    await conn.execute("SELECT set_config('app.tenant_id', $1, true)", get_tenant_id())
    await conn.execute("SELECT set_config('app.user_id', $1, true)", get_user_id())
'''

_SAAS_AUTH_PY = '''"""Auth Pattern A for __NAME__ — this service is the IdP (issues its own JWTs).

Per .windsurf/rules/core/35-security-auth.md Pattern A: this backend issues AND
validates its own user tokens — there is no external IdP. Login / signup / refresh
/ logout / password-reset are the vendored ``fastapi_user_auth`` router mounted at
``/auth`` (Argon2 login, atomic refresh-token rotation, jti-denylist revocation,
native-mode tenant RLS). This module also ships the standard security-headers
middleware and a CORS allow-list (never ``*`` with credentials), plus a
``decode_token`` helper the TenantMiddleware uses to validate the request bearer.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from fastapi_user_auth import (
    Settings,
    build_auth_router,
    make_engine,
    make_sessionmaker,
)
from fastapi_user_auth.tokens import NullDenylist, RedisDenylist, decode_access_token


@lru_cache
def get_settings() -> Settings:
    """Pattern-A settings from OUR infra env — unprefixed DATABASE_URL / REDIS_URL /
    JWT_SECRET (postgres-main / redis-main; the module's own env_prefix stays
    generic). Fails fast if JWT_SECRET is missing or < 32 chars (module validator)."""
    return Settings(
        database_url=os.environ["DATABASE_URL"],
        redis_url=os.getenv("REDIS_URL"),
        jwt_secret=os.environ["JWT_SECRET"],
        email_from=os.getenv("EMAIL_FROM", ""),
    )


@lru_cache
def _engine() -> Any:
    """One shared AsyncEngine for the whole app (disposed on shutdown via aclose())."""
    return make_engine(get_settings())


@lru_cache
def _denylist() -> Any:
    """Shared jti denylist for instant revocation (35 §Token Revocation). Redis-backed
    when REDIS_URL is set; otherwise NullDenylist — which SILENTLY disables revocation,
    so we log a loud warning (a missing REDIS_URL is a security downgrade, not a default)."""
    settings = get_settings()
    if settings.redis_url:
        import redis.asyncio as aioredis

        return RedisDenylist(aioredis.from_url(settings.redis_url))
    logging.getLogger("__NAME__.auth").warning(
        "REDIS_URL is unset — jti token revocation is DISABLED (NullDenylist). Logout / "
        "revoked access tokens stay valid until they expire. Set REDIS_URL (redis-main) "
        "to enable instant revocation."
    )
    return NullDenylist()


class _LogEmailSender:
    """Scaffold-default EmailSender — logs the verify/reset link instead of sending.
    Swap to fabrik-lib/email-transport (Resend) for production (35 §Email, 86)."""

    async def send(
        self, *, to_email: str, subject: str, html: str, plain_text: str | None = None
    ) -> None:
        print(f"[email:stub] to={to_email} subject={subject!r} — wire email-transport")


class _LogAuditLogger:
    """Scaffold-default AuditLogger — structured stdout. Swap to fabrik-lib/app-audit-log."""

    async def log(
        self,
        *,
        actor: str,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        print(f"[audit] actor={actor} action={action} target={target_type}:{target_id} {details or {}}")


def build_saas_auth_router() -> APIRouter:
    """The vendored Pattern-A /auth router (login/signup/refresh/logout/reset),
    mounted by main.py. Shares the app engine + denylist singletons."""
    return build_auth_router(
        settings=get_settings(),
        sessionmaker=make_sessionmaker(_engine()),
        email=_LogEmailSender(),
        audit=_LogAuditLogger(),
        denylist=_denylist(),
    )


def decode_token(token: str) -> dict[str, Any]:
    """Validate one of OUR access tokens (HS256 / JWT_SECRET) and return its claims
    (sub / tid / role / jti / exp). Raises on any failure. Used by TenantMiddleware."""
    return decode_access_token(token, secret=get_settings().jwt_secret)


async def token_revoked(jti: str) -> bool:
    """True if this access token's jti has been revoked (logout / denylist). Consulted by
    TenantMiddleware on EVERY protected request so revocation takes effect app-wide — NOT
    just on /auth routes (the module's own current_user only guards /auth/logout). Empty
    jti => not revoked.

    Fails OPEN if the denylist backend (Redis) is unreachable: logs a warning and returns
    False. Rationale — the token is still cryptographically valid and short-lived
    (access_ttl), so a Redis blip degrades early-revocation to normal token expiry rather
    than 500-ing every protected request (an availability foot-gun). Auth itself (signature
    + exp) is unaffected."""
    if not jti:
        return False
    try:
        return bool(await _denylist().contains(jti))
    except Exception:  # noqa: BLE001 — denylist backend down: degrade to token expiry
        logging.getLogger("__NAME__.auth").warning(
            "denylist check failed (Redis unreachable?) — revocation degraded to token "
            "expiry for this request",
            exc_info=True,
        )
        return False


async def aclose() -> None:
    """Dispose the shared engine + Redis client on shutdown (called from main.py lifespan)
    so the SQLAlchemy pool and the aioredis connection close cleanly."""
    await _engine().dispose()
    client = getattr(_denylist(), "_client", None)
    if client is not None:
        closer = getattr(client, "aclose", None) or getattr(client, "close", None)
        if closer is not None:
            try:
                await closer()
            except Exception:  # noqa: BLE001 — best-effort shutdown
                pass


async def require_user(request: Request) -> dict[str, Any]:
    """FastAPI dependency — gate a route on a validated user.

    ``TenantMiddleware`` has already decoded the bearer token and stashed the
    claims on ``request.state``; this just enforces their presence (401 if not)
    and surfaces the auth requirement in the OpenAPI schema.
    """
    claims = getattr(request.state, "jwt_claims", None)
    if not claims:
        raise HTTPException(status_code=401, detail="Authentication required")
    return claims  # type: ignore[no-any-return]


# Precomputed once — attached to every response (35 §Security Headers).
_SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-XSS-Protection": "0",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach the standard security headers to every response (35:112)."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        response: Response = await call_next(request)
        for key, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        return response


def cors_origins() -> list[str]:
    """Allow-list from ``CORS_ORIGINS`` (comma-separated). Empty => no CORS.

    Never returns ``["*"]`` — credentialed wildcard CORS is banned (35:91).
    """
    raw = os.getenv("CORS_ORIGINS", "").strip()
    return [o.strip() for o in raw.split(",") if o.strip() and o.strip() != "*"]
'''

_SAAS_WORKER_PY = '''"""Background worker for __NAME__ — PostgreSQL queue + adaptive pool + beat.

The canonical Fabrik job model (.windsurf/rules/core/75-workers-jobs.md):
  * PostgreSQL is the queue — no external broker. Jobs are claimed with
    ``SELECT ... FOR UPDATE SKIP LOCKED`` so N concurrent loops never block.
  * Instant wake-up — idle loops block on LISTEN/NOTIFY (``job_inserted``) with a
    safety-net fallback poll; no banned ``sleep(1)`` busy-poll (75 §Worker Wake-Up).
  * Adaptive pool — the number of concurrent claim-loops scales between
    ``WORKER_MIN`` and ``WORKER_MAX`` on queue depth (``scale_loop``, 30s tick).
  * Beat scheduler — a single leader (``pg_advisory_lock``) runs periodic/cron
    tasks (orphan sweep, etc.) exactly once, even across N replicas.

Run (the compose ``worker`` service command):  python -m __PKG__.worker

This is an asyncio implementation tuned for I/O-bound jobs. For CPU-bound work,
swap in the fork-based adaptive pool from the file-worker scaffold.
"""
from __future__ import annotations

import asyncio
import os
import pathlib
import signal
from typing import Any

import asyncpg

from __PKG__.glitchtip_init import init_glitchtip
from __PKG__.logger import get_logger

log = get_logger(__name__)

# Liveness heartbeat: the worker touches this file each tick; the container
# healthcheck (python, not pgrep — the slim image has no procps) checks it is
# fresh. Proves the worker is alive AND looping, and works during the DB-wait.
HEARTBEAT_PATH = os.getenv("WORKER_HEARTBEAT", "/app/.worker-heartbeat")
HEARTBEAT_TICK_SEC = int(os.getenv("WORKER_HEARTBEAT_TICK_SEC", "15"))

DATABASE_URL = os.getenv("DATABASE_URL", "")
WORKER_MIN = int(os.getenv("WORKER_MIN", "1"))
WORKER_MAX = int(os.getenv("WORKER_MAX", "8"))
SCALE_TICK_SEC = int(os.getenv("WORKER_SCALE_TICK_SEC", "30"))
BEAT_TICK_SEC = int(os.getenv("WORKER_BEAT_TICK_SEC", "300"))
# Safety-net poll: workers wake instantly on NOTIFY; this bounds a missed one.
POLL_FALLBACK_SEC = int(os.getenv("WORKER_POLL_FALLBACK_SEC", "60"))
ORPHAN_TIMEOUT = os.getenv("WORKER_ORPHAN_TIMEOUT", "10 minutes")
# Stable advisory-lock key so only ONE replica runs the beat scheduler.
BEAT_LOCK_KEY = int(os.getenv("WORKER_BEAT_LOCK_KEY", "910771"))

_shutdown = asyncio.Event()
# Set by the LISTEN/NOTIFY listener to instantly wake idle claim-loops.
_wake = asyncio.Event()


async def _handle(row: asyncpg.Record) -> None:
    """Example job handler. Replace with a ``task_name`` dispatch table.

    Handlers MUST be idempotent — delivery is at-least-once (75 §Idempotency).
    """
    log.info("job_processed", job_id=str(row["id"]), task=row["task_name"])


async def _claim_one(pool: asyncpg.Pool) -> bool:
    """Claim and run a single job. Returns True if a job was processed."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, task_name, payload, attempts, max_retries
                FROM jobs
                WHERE status = 'pending' AND run_at <= NOW()
                ORDER BY run_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """
            )
            if row is None:
                return False
            await conn.execute(
                "UPDATE jobs SET status = 'processing', updated_at = NOW() WHERE id = $1",
                row["id"],
            )
    # Process OUTSIDE the claim txn so a slow handler never holds the row lock.
    try:
        await _handle(row)
        await pool.execute(
            "UPDATE jobs SET status = 'completed', updated_at = NOW() WHERE id = $1",
            row["id"],
        )
    except Exception as exc:  # noqa: BLE001 — retry with backoff, else dead-letter
        attempts = row["attempts"] + 1
        terminal = attempts >= row["max_retries"]
        await pool.execute(
            """
            UPDATE jobs
            SET status = $2,
                attempts = $3,
                run_at = NOW() + (INTERVAL '5 seconds' * POWER(2, $3)),
                updated_at = NOW()
            WHERE id = $1
            """,
            row["id"],
            "failed" if terminal else "pending",
            attempts,
        )
        log.error("job_failed", job_id=str(row["id"]), error=str(exc), terminal=terminal)
    return True


async def _claim_loop(pool: asyncpg.Pool, worker_id: int) -> None:
    """One worker: claim → process → repeat.

    When the queue is empty the loop BLOCKS on the LISTEN/NOTIFY wake event
    (set by ``_listen_loop`` on job insertion) with a ``POLL_FALLBACK_SEC``
    safety-net timeout — never a naive ``sleep(1)`` busy-poll (75 §Worker
    Wake-Up). A missed NOTIFY costs at most one fallback interval of latency,
    not a lost job.
    """
    while not _shutdown.is_set():
        try:
            did = await _claim_one(pool)
        except Exception as exc:  # noqa: BLE001 — never let a loop die silently
            log.error("claim_loop_error", worker=worker_id, error=str(exc))
            did = False
        if did:
            continue  # keep draining while work remains
        _wake.clear()
        try:
            await asyncio.wait_for(_wake.wait(), timeout=POLL_FALLBACK_SEC)
        except asyncio.TimeoutError:
            pass  # safety-net poll — re-check the queue


async def _listen_loop() -> None:
    """Hold a dedicated LISTEN connection and wake claim-loops on NOTIFY.

    The schema's ``trg_job_inserted`` trigger fires ``pg_notify('job_inserted')``
    on every insert (75 §Worker Wake-Up). Reconnects on drop — the claim-loop
    fallback poll covers any gap. If the DB is reached through a transaction-mode
    pooler (PgBouncer), point this at a DIRECT connection (``DATABASE_URL_DIRECT``):
    LISTEN/NOTIFY does not survive transaction pooling.
    """
    dsn = os.getenv("DATABASE_URL_DIRECT", DATABASE_URL)
    while not _shutdown.is_set():
        conn = None
        try:
            conn = await asyncpg.connect(dsn)
            await conn.add_listener("job_inserted", lambda *_a: _wake.set())
            while not _shutdown.is_set():
                await asyncio.sleep(5)
                await conn.execute("SELECT 1")  # liveness — raises if the conn died
        except Exception as exc:  # noqa: BLE001 — reconnect on any listener failure
            log.warning("listen_reconnect", error=str(exc))
            await asyncio.sleep(2)
        finally:
            if conn is not None:
                await conn.close()


async def _queue_depth(pool: asyncpg.Pool) -> int:
    val = await pool.fetchval(
        "SELECT COUNT(*) FROM jobs WHERE status = 'pending' AND run_at <= NOW()"
    )
    return int(val or 0)


async def _scale_loop(pool: asyncpg.Pool, workers: list[asyncio.Task[Any]]) -> None:
    """Grow/shrink the claim-loop pool between WORKER_MIN..WORKER_MAX on depth."""
    while not _shutdown.is_set():
        try:
            depth = await _queue_depth(pool)
        except Exception as exc:  # noqa: BLE001 — DB blip; keep current size
            log.error("scale_loop_error", error=str(exc))
            await asyncio.sleep(SCALE_TICK_SEC)
            continue
        target = max(WORKER_MIN, min(WORKER_MAX, depth or WORKER_MIN))
        while len(workers) < target:
            workers.append(asyncio.create_task(_claim_loop(pool, len(workers))))
        while len(workers) > target:
            workers.pop().cancel()
        log.info("pool_scaled", depth=depth, workers=len(workers))
        await asyncio.sleep(SCALE_TICK_SEC)


async def _beat_loop(pool: asyncpg.Pool) -> None:
    """Single-leader beat: only the advisory-lock holder enqueues periodic work.

    A session-level advisory lock is bound to the CONNECTION that took it, so
    the lock, the work, and the unlock must all run on the SAME connection —
    using the pool's ``fetchval`` for each would check out different
    connections and leak the lock forever. Hence the dedicated ``acquire()``.
    """
    while not _shutdown.is_set():
        try:
            async with pool.acquire() as conn:
                got = await conn.fetchval("SELECT pg_try_advisory_lock($1)", BEAT_LOCK_KEY)
                if got:
                    try:
                        # Orphan sweep — reclaim jobs stuck in 'processing' past the timeout.
                        await conn.execute(
                            """
                            UPDATE jobs SET status = 'pending', updated_at = NOW()
                            WHERE status = 'processing'
                              AND updated_at < NOW() - $1::interval
                            """,
                            ORPHAN_TIMEOUT,
                        )
                        # Add cron/periodic tasks here by INSERTing into ``jobs`` — they are
                        # dispatched onto the queue, not run inline by the scheduler (75 §Beat).
                        log.info("beat_tick")
                    finally:
                        await conn.fetchval("SELECT pg_advisory_unlock($1)", BEAT_LOCK_KEY)
        except Exception as exc:  # noqa: BLE001 — e.g. the schema/jobs table isn't applied
            # yet (Fabrik runs no migrations); log and retry — never crash the worker.
            log.warning("beat_loop_error", error=str(exc))
        await asyncio.sleep(BEAT_TICK_SEC)


async def _heartbeat_loop() -> None:
    """Touch the heartbeat file each tick so the healthcheck sees liveness."""
    hb = pathlib.Path(HEARTBEAT_PATH)
    while not _shutdown.is_set():
        try:
            hb.touch()
        except OSError as exc:  # noqa: PERF203 — log + keep beating
            log.warning("heartbeat_write_failed", path=str(hb), error=str(exc))
        try:
            await asyncio.wait_for(_shutdown.wait(), timeout=HEARTBEAT_TICK_SEC)
        except asyncio.TimeoutError:
            pass


def _install_signals() -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown.set)


async def _await_pool() -> asyncpg.Pool | None:
    """Wait until a DB pool can be created — never crash the container.

    On Fabrik the postgres registrar provisions the DB + injects DATABASE_URL
    shortly AFTER the first deploy (recreating this container with the URL), so
    the very first boot legitimately has no/unreachable DB. Staying alive while
    retrying keeps the heartbeat healthcheck green so the deploy's health-wait
    passes; the container is then recreated with a working DATABASE_URL.
    """
    while not _shutdown.is_set():
        url = os.getenv("DATABASE_URL", "")
        if url:
            try:
                return await asyncpg.create_pool(url, min_size=2, max_size=WORKER_MAX + 2)
            except Exception as exc:  # noqa: BLE001 — transient DB unavailability
                log.warning("worker_db_unavailable_retrying", error=str(exc))
        else:
            log.info("worker_waiting_for_database_url")
        try:
            await asyncio.wait_for(_shutdown.wait(), timeout=5)
        except asyncio.TimeoutError:
            pass
    return None


async def main() -> None:
    init_glitchtip()  # unhandled job exceptions auto-report (75 §Observability)
    _install_signals()
    # Start the heartbeat FIRST so the container is healthy even while _await_pool
    # is still waiting for the registrar-injected DB on first boot.
    heartbeat = asyncio.create_task(_heartbeat_loop())
    pool = await _await_pool()
    if pool is None:
        heartbeat.cancel()
        log.info("worker_stopped_before_db_ready")
        return
    workers: list[asyncio.Task[Any]] = [
        asyncio.create_task(_claim_loop(pool, i)) for i in range(WORKER_MIN)
    ]
    log.info("worker_starting", min=WORKER_MIN, max=WORKER_MAX)
    try:
        await asyncio.gather(
            _scale_loop(pool, workers), _beat_loop(pool), _listen_loop(), heartbeat
        )
    finally:
        heartbeat.cancel()
        for task in workers:
            task.cancel()
        await pool.close()
        log.info("worker_stopped")


if __name__ == "__main__":
    asyncio.run(main())
'''

_SAAS_MAIN_PY = '''"""Main entry point for __NAME__ — multi-tenant FastAPI backend.

Wires the layers the saas-skeleton mandates:
  * RFC 9457 ``application/problem+json`` errors (15 §Error Schema)
  * ``/api/v1`` versioned business routes; unversioned ``/api/health`` + ``/metrics``
  * camelCase JSON via a ``to_camel`` base model (15 §Casing)
  * Self-hosted Pattern-A auth (this app is the IdP; /auth router) + security headers + CORS allow-list (35)
  * Tenant context middleware feeding PostgreSQL RLS (95)
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from starlette.exceptions import HTTPException as StarletteHTTPException

from __PKG__.auth import (
    SecurityHeadersMiddleware,
    aclose,
    build_saas_auth_router,
    cors_origins,
    require_user,
)
from __PKG__.glitchtip_init import init_glitchtip
from __PKG__.logger import get_logger
from __PKG__.metrics import metrics_app
from __PKG__.middleware import CorrelationMiddleware
from __PKG__.tenant import TenantMiddleware, get_tenant_id

# Initialise error reporting BEFORE app construction.
init_glitchtip()
logger = get_logger(__name__)

PROBLEM_JSON = "application/problem+json"


class CamelModel(BaseModel):
    """Base model — serialises camelCase, accepts camelCase or snake_case (15:22)."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def _problem(status: int, title: str, detail: str, request: Request) -> JSONResponse:
    """RFC 9457 problem+json response."""
    return JSONResponse(
        status_code=status,
        media_type=PROBLEM_JSON,
        content={
            "type": "about:blank",
            "title": title,
            "status": status,
            "detail": detail,
            "instance": request.url.path,
        },
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:  # noqa: ARG001
    logger.info("service_starting", port=os.getenv("PORT", "8000"))
    yield
    logger.info("service_stopping")
    # Close the shared auth engine + Redis client (build_saas_auth_router creates them).
    await aclose()


app = FastAPI(title="__NAME__", lifespan=lifespan)

# add_middleware stacks outermost-last, so the actual request order is:
# CORS (outermost, when configured) -> Correlation -> Security -> Tenant (innermost,
# runs right before the route so the ContextVar is set for handlers).
app.add_middleware(TenantMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CorrelationMiddleware)
_origins = cors_origins()
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Pattern-A IdP: mount the vendored fastapi_user_auth router at /auth
# (login/signup/refresh/logout/password-reset). TenantMiddleware skips /auth — the
# router owns its own DB sessions and issues tokens; it is not tenant-scoped.
app.include_router(build_saas_auth_router())

# Prometheus metrics — scraped internally at /metrics (shape.exposes_metrics).
app.mount("/metrics", metrics_app())


@app.exception_handler(StarletteHTTPException)
async def _http_exc(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Error"
    return _problem(exc.status_code, detail, detail, request)


@app.exception_handler(RequestValidationError)
async def _validation_exc(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _problem(422, "Unprocessable Entity", "Request validation failed", request)


@app.get("/api/health")
async def health() -> JSONResponse:
    """Health check — verifies the real DB dependency (55 §Health, SELECT 1)."""
    db_url = os.getenv("DATABASE_URL")
    deps: dict[str, str] = {}
    ok = True
    if db_url:
        try:
            import asyncpg

            conn = await asyncpg.connect(db_url, timeout=3)
            try:
                await conn.execute("SELECT 1")
            finally:
                await conn.close()
            deps["database"] = "ok"
        except Exception as exc:  # noqa: BLE001 — degrade, don't crash
            deps["database"] = f"error: {exc}"
            ok = False
    else:
        deps["database"] = "not_configured"
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "service": "__NAME__",
            "status": "ok" if ok else "degraded",
            "dependencies": deps,
        },
    )


# ── Example tenant-scoped resource (the wired CRUD pattern) ──────────────────
v1 = APIRouter(prefix="/api/v1")


class WidgetIn(CamelModel):
    name: str


class WidgetOut(CamelModel):
    id: str
    name: str


@v1.get("/widgets", response_model=list[WidgetOut])
async def list_widgets(claims: dict[str, Any] = Depends(require_user)) -> list[WidgetOut]:
    """List the caller's widgets. RLS scopes the query to their tenant (95).

    Wire a real asyncpg pool + ``tenant.apply_tenant(conn)`` here; returns [] until
    then so the scaffold runs end-to-end without a populated database.
    """
    logger.info("list_widgets", tenant=get_tenant_id())
    return []


@v1.post("/widgets", response_model=WidgetOut, status_code=201)
async def create_widget(
    body: WidgetIn,
    request: Request,
    claims: dict[str, Any] = Depends(require_user),
) -> WidgetOut:
    """Create a widget. Honour ``X-Idempotency-Key`` for safe retries (15:57)."""
    idempotency_key = request.headers.get("X-Idempotency-Key", "")
    logger.info("create_widget", tenant=get_tenant_id(), idempotency_key=idempotency_key)
    return WidgetOut(id="00000000-0000-0000-0000-000000000000", name=body.name)


app.include_router(v1)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Welcome to __NAME__"}
'''


def _write_saas_compose(project_dir: Path, name: str) -> None:
    """Write the three-service saas ``compose.yaml`` (web + api + worker).

    The Next.js ``web`` service keeps the project name (Coolify routing + the
    ``test_scaffold_compose_traefik`` contract). ``api`` takes ``PathPrefix(/api)``
    at higher priority (FastAPI backend, :8000); ``worker`` is internal —
    queue-driven, no Traefik/ports. All three carry a memory limit
    (``deployer_ssh._validate_compose`` enforces it per service).
    """
    fqdn = f"{name}.vps1.ocoron.com"
    db_name = name.replace("-", "_")  # worker module path / healthcheck pattern
    # DATABASE_URL / REDIS_URL are delivered ONLY via ``env_file: .env`` — the
    # postgres + redis registrars create the DB/role + index and inject the URLs
    # into .env AFTER the first deploy, then recreate the containers. We must NOT
    # bake a ``${DATABASE_URL:-...}`` fallback here: a fabricated blank-password URL
    # (POSTGRES_PASSWORD is provisioned nowhere) makes the api 503 and the worker
    # crash on first boot — before the registrar exists — failing the deploy's
    # health-wait. With the var simply ABSENT at first boot, the api health reports
    # ``not_configured`` → 200 and the resilient worker idles until the URL arrives.
    content = f"""# compose.yaml - Production-like Docker Compose (saas-skeleton: 3 services)
# Auto-generated by fabrik scaffold (_write_saas_compose).
# Used by Coolify (git source) for first-deploy. Invariants (do not regress):
#   - ``{name}`` (web) service name == project name (Coolify routing + docker ps)
#   - ``api`` takes Host(...) && PathPrefix(`/api`) at higher priority
#   - ``worker`` is internal: no Traefik labels, no published ports
#   - every service declares deploy.resources.limits.memory (OOM invariant)
#   - all join the external ``fabrik`` network for the Traefik mesh
# See tests/test_scaffold_compose_traefik.py + test_scaffold_saas_backend.py.

services:
  {name}:
    build:
      context: .
      dockerfile: Dockerfile
    platform: linux/amd64
    container_name: {name}
    environment:
      - PORT=3000
      - LOG_LEVEL=INFO
    env_file:
      - .env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
    networks:
      - fabrik
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=fabrik"
      - "traefik.http.routers.{name}.rule=Host(`{fqdn}`)"
      - "traefik.http.routers.{name}.entrypoints=websecure"
      - "traefik.http.routers.{name}.tls=true"
      - "traefik.http.routers.{name}.tls.certresolver=letsencrypt"
      - "traefik.http.services.{name}.loadbalancer.server.port=3000"

  api:
    build:
      context: ./server
      dockerfile: Dockerfile
    platform: linux/amd64
    container_name: {name}-api
    environment:
      - PORT=8000
      - LOG_LEVEL=INFO
    env_file:
      - .env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.5'
    networks:
      - fabrik
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=fabrik"
      # Higher priority than the web router so /api/* reaches the backend, not Next.js.
      - "traefik.http.routers.{name}-api.rule=Host(`{fqdn}`) && PathPrefix(`/api`)"
      - "traefik.http.routers.{name}-api.priority=100"
      - "traefik.http.routers.{name}-api.entrypoints=websecure"
      - "traefik.http.routers.{name}-api.tls=true"
      - "traefik.http.routers.{name}-api.tls.certresolver=letsencrypt"
      - "traefik.http.routers.{name}-api.middlewares=gzip@docker"
      - "traefik.http.services.{name}-api.loadbalancer.server.port=8000"

  worker:
    build:
      context: ./server
      dockerfile: Dockerfile
    platform: linux/amd64
    container_name: {name}-worker
    command: ["python", "-m", "{db_name}.worker"]
    environment:
      - LOG_LEVEL=INFO
    env_file:
      - .env
    healthcheck:
      # python liveness (the slim image has no pgrep/procps): the worker touches
      # WORKER_HEARTBEAT each tick; fail if it is missing or older than 60s.
      test: ["CMD", "python", "-c", "import os,time,sys; p=os.getenv('WORKER_HEARTBEAT','/app/.worker-heartbeat'); sys.exit(0 if os.path.exists(p) and time.time()-os.path.getmtime(p) < 60 else 1)"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 30s
    restart: unless-stopped
    stop_grace_period: 45s
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
    networks:
      - fabrik

networks:
  fabrik:
    external: true
"""
    (project_dir / "compose.yaml").write_text(content, encoding="utf-8")


_SAAS_TEST_AUTH_PY = '''"""Pattern-A auth smoke tests for __NAME__.

Asserts the vendored ``fastapi_user_auth`` /auth router is mounted and the
access-token round-trip (issue -> decode_token) works — the wiring the app boots
with. DB-backed signup/login is a separate integration test (needs a live
DATABASE_URL); these run with NO DB/Redis (create_async_engine is lazy; REDIS_URL
unset -> NullDenylist).
"""
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u@localhost/x")
os.environ.setdefault("JWT_SECRET", "test-" + "x" * 40)  # >= 32 chars (module validator)


def test_auth_router_mounted() -> None:
    from __PKG__.auth import build_saas_auth_router

    routes = {getattr(r, "path", "") for r in build_saas_auth_router().routes}
    assert any(p.endswith("/login") for p in routes), routes
    assert any(p.endswith("/signup") for p in routes), routes


def test_access_token_round_trip() -> None:
    from fastapi_user_auth.tokens import issue_access_token

    from __PKG__.auth import decode_token

    secret = os.environ["JWT_SECRET"]
    token = issue_access_token(subject="u1", tenant_id="t1", secret=secret, ttl_seconds=60)
    claims = decode_token(token)
    assert claims["sub"] == "u1"
    assert claims["tid"] == "t1"
'''


def _scaffold_saas_backend(project_dir: Path, name: str, package_name: str) -> None:
    """Emit the multi-tenant FastAPI backend under ``<project>/server``.

    Reuses ``_scaffold_fastapi_backend`` for the base package (logger,
    middleware, metrics, internal_auth, glitchtip_init) then layers on the
    saas spine: db/schema.sql (RLS + jobs queue), tenant.py, auth.py, worker.py
    and a saas-flavoured main.py. Bodies carry ``__PKG__``/``__NAME__`` tokens.
    """
    server_dir = project_dir / "server"
    _scaffold_fastapi_backend(server_dir, name, package_name)

    def _sub(text: str) -> str:
        return text.replace("__PKG__", package_name).replace("__NAME__", name)

    (server_dir / "requirements.txt").write_text(_SAAS_SERVER_REQUIREMENTS)

    # server/Dockerfile — mirror the python Dockerfile, entrypoint at <pkg>.main:app.
    # The saas backend serves /api/health (not /health), so retarget the image
    # HEALTHCHECK to match — otherwise a plain ``docker run`` of the image (no
    # compose override) would report unhealthy. The compose api healthcheck also
    # uses /api/health.
    dockerfile_src = TEMPLATE_DIR / "docker" / "Dockerfile.python"
    if dockerfile_src.exists():
        df = dockerfile_src.read_text()
        df = df.replace("PROJECT_NAME", name).replace("<package_name>", package_name)
        df = df.replace("${PORT:-8000}/health", "${PORT:-8000}/api/health")
        (server_dir / "Dockerfile").write_text(df)

    (server_dir / "db").mkdir(parents=True, exist_ok=True)
    (server_dir / "db" / "schema.sql").write_text(_sub(_SAAS_SCHEMA_SQL))

    pkg_dir = server_dir / "src" / package_name
    (pkg_dir / "tenant.py").write_text(_sub(_SAAS_TENANT_PY))
    (pkg_dir / "auth.py").write_text(_sub(_SAAS_AUTH_PY))
    (pkg_dir / "worker.py").write_text(_sub(_SAAS_WORKER_PY))
    # Overwrite the base main.py with the saas (multi-tenant) variant.
    (pkg_dir / "main.py").write_text(_sub(_SAAS_MAIN_PY))

    # Vendor fabrik-lib/fastapi-user-auth (Pattern-A IdP) as a top-level package on
    # the server src path, so its internal ``from fastapi_user_auth.…`` imports resolve
    # unchanged (vendor, don't rewrite — fabrik-lib README rule).
    _vendor_fastapi_user_auth(server_dir / "src")

    # Pattern-A auth smoke test (router mounted + token round-trip) beside test_health.
    (server_dir / "tests").mkdir(parents=True, exist_ok=True)
    (server_dir / "tests" / "test_auth.py").write_text(_sub(_SAAS_TEST_AUTH_PY))


def _vendor_fastapi_user_auth(dest_src: Path) -> None:
    """Copy the ``fastapi_user_auth`` package from ``/opt/fabrik-lib`` into ``<server>/src/``.

    It lands as a top-level package (``server/src/fastapi_user_auth/``) so its own
    ``from fastapi_user_auth.…`` imports work with no rewriting. ``reference_adapter.py``
    is excluded — it composes other fabrik-lib modules (email-transport / app-audit-log)
    that are not vendored here; the scaffold supplies its own EmailSender/AuditLogger.

    A Pattern-A saas backend cannot boot without this module (``auth.py``/``main.py``
    import it), so its absence is FATAL: fail the scaffold loudly rather than emit a
    project that ``ModuleNotFound``-crashes at boot with no recovery path.
    """
    module_src = FABRIK_LIB_DIR / "fastapi-user-auth" / "fastapi_user_auth"
    if not module_src.is_dir():
        raise FileNotFoundError(
            f"Cannot scaffold a Pattern-A saas backend: fabrik-lib/fastapi-user-auth was "
            f"not found at {module_src}. The auth module must be vendored (auth.py and "
            f"main.py import it). Ensure /opt/fabrik-lib is present next to /opt/fabrik."
        )
    dest = dest_src / "fastapi_user_auth"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        module_src,
        dest,
        ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", "reference_adapter.py", "conftest.py", "pytest.ini"
        ),
    )


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
            # B26: replace `npm ci` with `npm install` in the Dockerfile.
            # The shipped template Dockerfile uses `RUN npm ci`, but `npm ci`
            # requires a `package-lock.json` and the scaffolder does not run
            # `npm install` to generate one. Without this patch the first
            # Coolify build fails with::
            #
            #   npm error code EUSAGE
            #   npm error The `npm ci` command can only install with an
            #   existing package-lock.json or npm-shrinkwrap.json
            #
            # `_scaffold_node_api` and `_scaffold_file_api` already do this
            # exact substitution (see lines 1325-1327 and 1487); saas-skeleton
            # was the lone gap. Surfaced by proof-run on 2026-04-28.
            if rel.name == "Dockerfile":
                content = content.replace("RUN npm ci", "RUN npm install")
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

    # Emit the multi-tenant FastAPI backend under server/ (Phase 1) and the
    # three-service compose (web + api + worker) that fronts it (Phase 6).
    # _write_saas_compose replaces the old single-service B21 canonical compose:
    # it overwrites the template's compose.yaml with the Coolify-correct
    # 3-service version (literal FQDN + ports in Traefik labels — Coolify does
    # not expand ${VAR}; web on 3000, api on 8000 behind PathPrefix(/api)).
    _scaffold_saas_backend(project_dir, name, _get_package_name(name))
    _write_saas_compose(project_dir, name)


def _vendor_docs_site(project_dir: Path, name: str) -> None:
    """Vendor fabrik-lib/docs-site into ``<project>/docs-site/``.

    Copies the canonical Docusaurus docs template (Ocoron tokens, Scalar API
    reference, Pagefind search, legal pages) following the fabrik-lib "vendor,
    don't depend" pattern — a self-contained copy with no runtime ``/opt``
    dependency. Build artefacts and the upstream ``.git`` are excluded, the
    package name is pointed at the project, and a local ``.gitignore`` keeps
    the vendored ``node_modules``/``build`` out of the repo.

    No-op (with a warning) when fabrik-lib is absent — e.g. CI checkouts
    without the sibling repo. A scaffold must not hard-fail on a missing
    optional source. Per ``.windsurf/rules/saas/88-saas-launch-checklist.md``.
    """
    docs_src = FABRIK_LIB_DIR / "docs-site"
    if not docs_src.is_dir():
        logger.warning(
            "fabrik-lib/docs-site not found at %s — skipping docs-site vendoring "
            "(add it later: cp -r /opt/fabrik-lib/docs-site docs-site)",
            docs_src,
        )
        return

    dest = project_dir / "docs-site"
    shutil.copytree(
        docs_src,
        dest,
        ignore=shutil.ignore_patterns(
            "node_modules", "build", ".docusaurus", "package-lock.json", ".git"
        ),
    )

    # Point the vendored docs site at this project (post-vendor checklist step).
    pkg = dest / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            data["name"] = f"{name}-docs"
            pkg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except (json.JSONDecodeError, OSError):
            logger.debug("could not patch docs-site/package.json name", exc_info=True)

    (dest / ".gitignore").write_text("node_modules/\nbuild/\n.docusaurus/\n", encoding="utf-8")
    logger.info("Vendored fabrik-lib/docs-site -> %s/docs-site", project_dir.name)


def _scaffold_saas_skeleton_with_docs(
    project_dir: Path, name: str, description: str, **kwargs: object
) -> None:
    """saas-skeleton scaffold + an auto-vendored docs site.

    Identical to ``_scaffold_saas_skeleton`` plus a vendored copy of
    fabrik-lib/docs-site under ``docs-site/`` (per the SaaS launch checklist).
    ``static-site`` keeps using the bare ``_scaffold_saas_skeleton`` — it is
    not a SaaS and does not get a docs site.
    """
    _scaffold_saas_skeleton(project_dir, name, description, **kwargs)
    _vendor_docs_site(project_dir, name)


def _scaffold_node_api(project_dir: Path, name: str, description: str, **kwargs: object) -> None:
    """Create Node API-specific project structure."""
    import json

    # a) Create src/ directory
    (project_dir / "src").mkdir(parents=True, exist_ok=True)

    # src/internal_auth.js — canonical M2M auth for Node.js Fastify services
    (project_dir / "src" / "internal_auth.js").write_text(
        "/**\n"
        " * Canonical internal token auth for Fabrik Node.js services.\n"
        " * Header:  X-Internal-Token\n"
        " * Env var: SERVICE_INTERNAL_SECRET_KEY\n"
        " * Usage: import { requireInternalToken } from './internal_auth.js';\n"
        " *        fastifyApp.addHook('preHandler', requireInternalToken);\n"
        " */\n"
        "import { timingSafeEqual } from 'node:crypto';\n"
        "\n"
        "function safeCompare(a, b) {\n"
        "  try {\n"
        "    const ba = Buffer.from(a);\n"
        "    const bb = Buffer.from(b);\n"
        "    if (ba.length !== bb.length) return false;\n"
        "    return timingSafeEqual(ba, bb);\n"
        "  } catch { return false; }\n"
        "}\n"
        "\n"
        "export async function requireInternalToken(request, reply) {\n"
        "  const token = request.headers['x-internal-token'];\n"
        "  const secret = process.env.SERVICE_INTERNAL_SECRET_KEY ?? '';\n"
        "  if (!token || !secret || !safeCompare(token, secret)) {\n"
        "    return reply.code(403).send({ error: 'Missing or invalid token' });\n"
        "  }\n"
        "}\n"
    )

    # b) Copy and patch Dockerfile.node -> Dockerfile
    dockerfile_src = TEMPLATE_DIR / "docker" / "Dockerfile.node"
    if dockerfile_src.exists():
        content = dockerfile_src.read_text()
        content = content.replace("PROJECT_NAME", name)
        content = content.replace("dist/index.js", "src/index.js")
        content = content.replace("./dist", "./src")
        # B31: also rewrite the absolute /app/dist path in the runtime stage's
        # ``COPY --from=builder /app/dist ./src`` directive. The node-api
        # scaffold has no compile step (source is plain JS in ``src/``), so
        # ``/app/dist`` never exists in the builder image and the COPY fails:
        #   failed to compute cache key: failed to calculate checksum of ref
        #   ...: "/app/dist": not found
        # The other replacements above only catch ``./dist`` and ``dist/index.js``
        # — they don't match the absolute path. Surfaced by proof-run on
        # 2026-04-28.
        content = content.replace("/app/dist", "/app/src")
        # Replace `npm ci` with `npm install --ignore-scripts` — no lockfile is
        # generated during scaffold, so `npm ci` would fail on a fresh docker
        # build. `--ignore-scripts` is non-negotiable (core/12-node.md): blocks
        # malicious postinstall payloads (Mastra `easy-day-js` 2026 typosquat).
        content = content.replace("RUN npm ci", "RUN npm install --ignore-scripts")
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
        # ESM is the fabrik default (core/12-node.md): all src/*.js use import/export.
        "type": "module",
        "private": True,
        "main": "src/index.js",
        "engines": {"node": ">=22.0.0"},
        "scripts": {
            "start": "node src/index.js",
            "dev": "node --watch src/index.js",
            "test": "node --test",
            "lint": "echo 'No linter configured'",
        },
        "dependencies": {
            "pino": "^9.0.0",
            "@sentry/node": "^8.40.0",
        },
    }
    (project_dir / "package.json").write_text(json.dumps(package_json, indent=2) + "\n")

    # e) Generate src/logger.js inline (pino structured logging, ESM)
    # Mandatory redact paths (core/12-node.md) keep tokens/passwords out of Loki.
    (project_dir / "src" / "logger.js").write_text(
        """import pino from 'pino';

export const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  name: process.env.SERVICE_NAME || '{name}',
  timestamp: pino.stdTimeFunctions.isoTime,
  redact: [
    'req.headers.authorization',
    'req.headers["x-internal-token"]',
    'req.body.password',
    'req.body.token',
    '*.access_token',
    '*.refresh_token',
  ],
});

export default logger;
""".replace("{name}", name)
    )

    # e2) Generate src/glitchtip_init.js — GlitchTip / Sentry SDK init (no-op if DSN unset)
    # Require this module BEFORE creating any HTTP server / Express app so SDK
    # instruments outgoing handlers from the very first request. Errors auto-report
    # to GlitchTip when GLITCHTIP_DSN is set in environment.
    (project_dir / "src" / "glitchtip_init.js").write_text(
        """/**
 * GlitchTip / Sentry SDK initialization (ESM).
 *
 * If SENTRY_DSN (preferred, fabrik standard) or GLITCHTIP_DSN is set, errors and unhandled rejections auto-report to GlitchTip.
 * If unset, init is a no-op (zero overhead).
 *
 * Import this module FIRST in index.js, before any handler creation:
 *   import './glitchtip_init.js';
 *
 * Provision a project + DSN: scripts/provision_glitchtip_project.sh <service-name> --platform javascript-node
 * Push DSN to Coolify env on deploy.
 */
const dsn = (process.env.SENTRY_DSN || process.env.GLITCHTIP_DSN || '').trim();

let Sentry = null;
if (dsn) {
  try {
    // Dynamic import keeps @sentry/node optional — no DSN means it's never loaded.
    Sentry = await import('@sentry/node');
    Sentry.init({
      dsn,
      environment: process.env.ENVIRONMENT || 'production',
      release: process.env.GIT_SHA || process.env.COOLIFY_DEPLOYMENT_UUID || undefined,
      tracesSampleRate: parseFloat(process.env.GLITCHTIP_TRACES_SAMPLE_RATE || '0.05'),
      profilesSampleRate: parseFloat(process.env.GLITCHTIP_PROFILES_SAMPLE_RATE || '0'),
      sendDefaultPii: false,
    });
  } catch {
    // @sentry/node not installed; emit a one-time warning rather than crash.
    process.stderr.write('[glitchtip_init] @sentry/node not installed; error reporting disabled\\n');
    Sentry = null;
  }
}

export default Sentry;
"""
    )

    # f) Generate src/index.js inline (ESM, pino + AsyncLocalStorage correlation,
    #    graceful SIGTERM drain per core/12-node.md).
    (project_dir / "src" / "index.js").write_text(
        """// Initialize error reporting BEFORE any handler creation so the SDK
// instruments the runtime from the very first request. No-op if DSN unset.
import './glitchtip_init.js';

import http from 'node:http';
import { randomUUID } from 'node:crypto';
import { AsyncLocalStorage } from 'node:async_hooks';
import { logger } from './logger.js';

const asyncCtx = new AsyncLocalStorage();
const PORT = process.env.PORT || 3000;

// Flipped true on SIGTERM so /health returns 503 and Traefik drains us.
let isShuttingDown = false;

const server = http.createServer((req, res) => {
  const requestId = req.headers['x-request-id'] || randomUUID();
  res.setHeader('X-Request-ID', requestId);

  asyncCtx.run({ traceId: requestId }, () => {
    if (req.method === 'GET' && req.url === '/health') {
      const code = isShuttingDown ? 503 : 200;
      res.writeHead(code, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ service: '{name}', status: isShuttingDown ? 'draining' : 'ok' }));
      return;
    }

    logger.info({ ...asyncCtx.getStore(), event: 'request_received', method: req.method, url: req.url });
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ message: 'Welcome to {name}' }));
  });
});

server.listen(PORT, () => {
  logger.info({ event: 'service_starting', port: PORT });
});

// Graceful drain on SIGTERM (Docker stop): 503 health flip -> stop idle conns ->
// close once in-flight finishes -> 20s hard backstop. See core/12-node.md.
process.on('SIGTERM', () => {
  isShuttingDown = true;
  setTimeout(() => process.exit(1), 20_000).unref();
  server.closeIdleConnections?.();
  server.close(() => process.exit(0));
  setTimeout(() => server.closeAllConnections?.(), 5_000).unref();
});
""".replace("{name}", name)
    )

    # g) Overwrite .env.example with Node-appropriate content
    (project_dir / ".env.example").write_text(
        f"# {name} Configuration\nPORT=3000\nNODE_ENV=development\nLOG_LEVEL=info\n\n"
        f"# Service identity for structured logging\nSERVICE_NAME={name}\n\n"
        f"# Error reporting (GlitchTip) — recommended for production deploys\n"
        f"# Get DSN: scripts/provision_glitchtip_project.sh {name} --platform javascript-node\n"
        f"# Set via project .env (managed by `fabrik apply`). If unset, SDK is a no-op (zero overhead).\n"
        f"GLITCHTIP_DSN=\nENVIRONMENT=production\n"
    )

    # h) Overwrite .gitignore with Node-appropriate content
    (project_dir / ".gitignore").write_text(
        _COMMON_GITIGNORE_PATTERNS + "\n" + _DROID_GITIGNORE_BLOCK + "\n" + "# Node.js-specific\n"
        "node_modules/\n"
        "dist/\n"
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

    # B20: Emit a Coolify-correct compose.yaml. node-api scaffolders
    # previously relied on the .j2 deploy-time template, which is never
    # consulted on git-source deploys (Coolify clones the repo and
    # reads ``/compose.yaml`` directly). Without this, git-source
    # deployment errors with ``compose-file not found``.
    _write_canonical_compose(
        project_dir,
        name,
        port=3000,
        healthcheck_path="/api/health",
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

    # b2) Generate src/logger.js inline (pino structured logging, CJS — file-api
    # stays CommonJS + Express per core/12-node.md "existing CJS stays CJS").
    # Mandatory redact paths keep tokens/passwords out of Loki.
    (project_dir / "src" / "logger.js").write_text(
        """'use strict';

const pino = require('pino');

const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  name: process.env.SERVICE_NAME || '{name}',
  timestamp: pino.stdTimeFunctions.isoTime,
  redact: [
    'req.headers.authorization',
    'req.headers["x-internal-token"]',
    'req.body.password',
    'req.body.token',
    '*.access_token',
    '*.refresh_token',
  ],
});

module.exports = logger;
""".replace("{name}", name)
    )

    # c) Copy and patch Dockerfile.node -> Dockerfile
    dockerfile_src = TEMPLATE_DIR / "docker" / "Dockerfile.node"
    if dockerfile_src.exists():
        content = dockerfile_src.read_text()
        content = content.replace("PROJECT_NAME", name)
        content = content.replace("dist/index.js", "src/index.js")
        content = content.replace("./dist", "./src")
        # B31: see above — same fix for file-api.
        content = content.replace("/app/dist", "/app/src")
        content = content.replace("RUN npm ci", "RUN npm install")
        (project_dir / "Dockerfile").write_text(content)

    # d) Copy and patch Makefile.node -> Makefile
    makefile_src = TEMPLATE_DIR / "docker" / "Makefile.node"
    if makefile_src.exists():
        content = makefile_src.read_text()
        content = content.replace("myproject", name)
        (project_dir / "Makefile").write_text(content)

    # e) Generate package.json inline with R2/Supabase dependencies.
    # CJS + Express (stays CommonJS per core/12-node.md). The undici handler +
    # adaptive retry strategy are mandatory for S3-compatible clients (67-file-api
    # "Done When" #1); lib-storage powers backpressure-safe multipart streaming.
    package_json = {
        "name": name,
        "version": "0.1.0",
        "description": description,
        "private": True,
        "main": "src/index.js",
        "engines": {"node": ">=22.0.0"},
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
            "@aws-sdk/lib-storage": "^3.450.0",
            "@aws-sdk/util-retry": "^3.374.0",
            "@smithy/undici-http-handler": "^2.2.0",
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
# region: 'auto' for Cloudflare R2; set the real region for Backblaze B2
R2_REGION=auto
# forcePathStyle: leave false for R2; set true for Backblaze B2 (path-style required)
R2_FORCE_PATH_STYLE=false
MAX_FILE_SIZE_MB=100
ALLOWED_CONTENT_TYPES=application/pdf,audio/mpeg
# Presigned PUT URLs are capped at 900s (15 min) in code per 67-file-api (NIST observation contracts)
UPLOAD_URL_EXPIRY_SECONDS=900
DOWNLOAD_URL_EXPIRY_SECONDS=3600

# Service identity for structured logging
SERVICE_NAME={name}
"""
    )

    # g) Overwrite .gitignore with Node-appropriate content
    (project_dir / ".gitignore").write_text(
        _COMMON_GITIGNORE_PATTERNS + "\n" + _DROID_GITIGNORE_BLOCK + "\n" + "# Node.js-specific\n"
        "node_modules/\n"
        "dist/\n"
        "npm-debug.log*\n"
        "yarn-debug.log*\n"
        "yarn-error.log*\n"
        ".pnpm-debug.log*\n"
        "\n"
        "# Build & Test\n"
        "coverage/\n"
        "build/\n"
    )

    # B20: Coolify-correct compose for git-source deploys.
    _write_canonical_compose(
        project_dir,
        name,
        port=3000,
        healthcheck_path="/api/health",
    )


def _scaffold_file_worker(project_dir: Path, name: str, description: str, **kwargs: object) -> None:
    """Create File Worker-specific project structure."""
    # a) Create worker/ directory
    (project_dir / "worker").mkdir(parents=True, exist_ok=True)

    # b) Write worker/logger.py — structured logging with PII redaction
    (project_dir / "worker" / "logger.py").write_text(
        _logger_py_content(name, name.replace("-", "_"))
    )

    # c) Copy main.py verbatim from file-worker template
    src_main = FILE_WORKER_TEMPLATE_DIR / "worker" / "main.py"
    if src_main.exists():
        shutil.copy2(src_main, project_dir / "worker" / "main.py")

    # c2) Copy pause_state.py — pause-flag primitives for worker resilience
    pause_src = TEMPLATE_DIR / "python" / "pause_state.py"
    if pause_src.exists():
        shutil.copy2(pause_src, project_dir / "worker" / "pause_state.py")

    # d) Copy and patch Dockerfile.python -> Dockerfile
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
        _COMMON_GITIGNORE_PATTERNS + "\n" + _DROID_GITIGNORE_BLOCK + "\n" + "# Python-specific\n"
        ".env.local\n"
        "venv/\n"
        ".venv/\n"
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

    # B20: Worker-style compose. file-worker has no HTTP surface, so no
    # Traefik labels — Coolify still manages the container via the
    # ``fabrik`` network. Healthcheck probes the worker process by
    # name (``python worker/main.py``) instead of HTTP.
    _write_canonical_compose(
        project_dir,
        name,
        with_traefik=False,
        healthcheck_kind="process",
        process_pattern="python worker/main.py",
        port=8000,  # unused but required by signature
    )


def _write_placeholder_png(
    path: Path, size: int, rgba: tuple[int, int, int, int] = (66, 133, 244, 255)
) -> None:
    """Write a solid-color square PNG (pure stdlib — no Pillow dependency).

    The chrome-extension scaffold ships icon16/48/128.png under extension/public/
    (WXT copies public/ verbatim into the build output). These placeholders
    (Google-blue #4285f4) make the extension build usable out of the box; the
    developer replaces them with real branding.
    """
    import struct
    import zlib

    r, g, b, a = rgba
    row = bytes((r, g, b, a)) * size
    raw = bytearray()
    for _ in range(size):
        raw.append(0)  # PNG filter type 0 (None) per scanline
        raw.extend(row)

    def _chunk(ctype: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + ctype
            + data
            + struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def _scaffold_chrome_extension(
    project_dir: Path, name: str, description: str, **kwargs: object
) -> None:
    """Create Chrome Extension with TypeScript extension + FastAPI server."""
    import json

    package_name = _get_package_name(name)

    # Create directory structure — WXT layout (srcDir='src', file-based entrypoints).
    ext = project_dir / "extension"
    (ext / "src" / "entrypoints" / "popup").mkdir(parents=True, exist_ok=True)
    (ext / "src" / "entrypoints" / "options").mkdir(parents=True, exist_ok=True)
    (ext / "src" / "locales").mkdir(parents=True, exist_ok=True)
    (ext / "public").mkdir(parents=True, exist_ok=True)
    (project_dir / "server" / "src" / package_name).mkdir(parents=True, exist_ok=True)

    # 1. Extension files — WXT is the default build tool (chrome-ext/70-chrome-ext.md
    #    § Build Tooling). The manifest is AUTO-GENERATED by WXT from wxt.config.ts +
    #    the entrypoints (never a hand-written manifest.json). UI = Preact via
    #    @preact/preset-vite, which auto-aliases react/react-dom -> preact/compat so the
    #    fabrik-lib UI-bearing kits' React-API (JSX+hooks) components render on Preact.

    # wxt.config.ts
    (ext / "wxt.config.ts").write_text(
        """import preact from '@preact/preset-vite';
import { defineConfig } from 'wxt';

// WXT generates manifest.json from this config + the entrypoints. @preact/preset-vite
// aliases react/react-dom -> preact/compat (reactAliasesEnabled default), wiring Preact
// JSX + HMR so React-API kit components run on the Preact default. To override to real
// React for a heavy side-panel app, swap @preact/preset-vite for @wxt-dev/module-react.
export default defineConfig({
  srcDir: 'src',
  modules: ['@wxt-dev/i18n/module'],
  vite: () => ({
    plugins: [preact()],
  }),
  manifest: {
    name: '__MSG_extName__',
    description: '__MSG_extDescription__',
    default_locale: 'en',
    permissions: ['storage', 'activeTab'],
  },
});
"""
    )

    # extension/package.json — WXT + Preact + the MV3 dep set (versions grounded 2026-07).
    ext_package = {
        "name": f"{name}-extension",
        "version": "1.0.0",
        "description": f"{description} - Browser Extension (WXT + Preact)",
        "type": "module",
        "private": True,
        "scripts": {
            "dev": "wxt",
            "build": "wxt build",
            "zip": "wxt zip",
            "postinstall": "wxt prepare",
            "compile": "tsc --noEmit",
            "size": "size-limit",
            "lint": "eslint .",
        },
        "dependencies": {
            "preact": "^10.25.0",
            "@wxt-dev/storage": "^1.2.8",
            "@wxt-dev/i18n": "^0.2.6",
            "@hey-api/openapi-ts": "0.99.0",
            "@sentry/browser": "^10.65.0",
            "webext-bridge": "^6.0.1",
            "webext-permission-toggle": "^6.0.1",
            "webext-dynamic-content-scripts": "^10.0.4",
            "webext-permissions": "^3.1.3",
            "element-ready": "^9.0.2",
            "zustand": "^5.0.0",
            "@webext-pegasus/store-zustand": "^0.3.6",
        },
        "devDependencies": {
            "wxt": "^0.20.27",
            "@preact/preset-vite": "^2.10.1",
            "@types/chrome": "^0.2.2",
            "typescript": "^5.7.0",
            "size-limit": "^12.1.0",
            "@size-limit/preset-app": "^12.1.0",
            "@playwright/test": "^1.59.0",
            "@axe-core/playwright": "^4.10.1",
            "eslint": "^9.39.2",
            "@antfu/eslint-config": "^7.2.0",
        },
    }
    (ext / "package.json").write_text(json.dumps(ext_package, indent=2) + "\n")

    # pnpm-workspace.yaml — pnpm 11 build-script approval. pnpm 11 REMOVED
    # onlyBuiltDependencies (+ the package.json `pnpm` field) and replaced them with
    # `allowBuilds: {pkg: bool}`; strictDepBuilds now defaults true (unlisted build-deps
    # error). Pre-declare the exact build-script deps in the tree so `pnpm install` exits
    # 0 with no prompt/placeholder-write: esbuild links its platform binary (needed by the
    # bundler); spawn-sync (legacy size-limit polyfill) is denied — node has spawnSync.
    (ext / "pnpm-workspace.yaml").write_text("allowBuilds:\n  esbuild: true\n  spawn-sync: false\n")

    # tsconfig.json — extends WXT's generated config (auto-import types, generated by
    # `wxt prepare` postinstall); Preact JSX via jsxImportSource.
    (ext / "tsconfig.json").write_text(
        """{
  "extends": "./.wxt/tsconfig.json",
  "compilerOptions": {
    "jsx": "react-jsx",
    "jsxImportSource": "preact",
    "strict": true
  }
}
"""
    )

    # .size-limit.json — per-surface bundle budgets (chrome-ext/70-chrome-ext.md § Bundle Budgets).
    (ext / ".size-limit.json").write_text(
        """[
  { "name": "popup", "path": ".output/chrome-mv3/chunks/popup-*.js", "limit": "40 KB" },
  { "name": "options", "path": ".output/chrome-mv3/chunks/options-*.js", "limit": "60 KB" },
  { "name": "background", "path": ".output/chrome-mv3/background.js", "limit": "30 KB" }
]
"""
    )

    # eslint.config.mjs — ignore WXT/generated dirs; disable markdown+yaml processing so
    # governance .md/.yaml files don't crash the linter (Lessons 78/89).
    (ext / "eslint.config.mjs").write_text(
        """import antfu from '@antfu/eslint-config';

export default antfu({
  typescript: true,
  jsonc: false,
  markdown: false,
  yaml: false,
  stylistic: { semi: true },
  ignores: ['.wxt/**', '.output/**', 'src/lib/api/generated/**'],
});
"""
    )

    # 1a. Entrypoints (WXT file-based; auto-imports defineBackground/defineContentScript
    #     after `wxt prepare`). Phase A = minimal stubs that build; surfaces fleshed out next.
    (ext / "src" / "entrypoints" / "background.ts").write_text(
        """// MV3 service worker. WXT auto-imports defineBackground.
export default defineBackground(() => {
  // Onboarding + command/context-menu registration land here (native snippets).
  browser.runtime.onInstalled.addListener(({ reason }) => {
    if (reason === 'install') {
      // Open packaged onboarding on first install (Phase B wires onboarding.html).
    }
  });
});
"""
    )
    (ext / "src" / "entrypoints" / "content.ts").write_text(
        """// Content script. WXT auto-imports defineContentScript.
export default defineContentScript({
  matches: ['<all_urls>'],
  main() {
    // Shadow-DOM overlay (createShadowRootUi) lands here in Phase B.
  },
});
"""
    )
    _cx_popup_html = """<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Popup</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="./main.tsx"></script>
  </body>
</html>
"""
    (ext / "src" / "entrypoints" / "popup" / "index.html").write_text(_cx_popup_html)
    (ext / "src" / "entrypoints" / "options" / "index.html").write_text(
        _cx_popup_html.replace("<title>Popup</title>", "<title>Options</title>")
    )
    (ext / "src" / "entrypoints" / "popup" / "main.tsx").write_text(
        f"""import {{ render }} from 'preact';

function App() {{
  return <main style={{{{ width: 360, padding: 16, fontFamily: 'system-ui' }}}}>{name}</main>;
}}

render(<App />, document.getElementById('root')!);
"""
    )
    (ext / "src" / "entrypoints" / "options" / "main.tsx").write_text(
        f"""import {{ render }} from 'preact';

function App() {{
  return <main style={{{{ padding: 24, fontFamily: 'system-ui' }}}}>{name} — Settings</main>;
}}

render(<App />, document.getElementById('root')!);
"""
    )

    # locales/*.json — @wxt-dev/i18n source (flat key:value). extName/extDescription feed
    # the manifest __MSG_*__ refs; @wxt-dev/i18n generates the native _locales/ at build.
    (ext / "src" / "locales" / "en.json").write_text(
        json.dumps({"extName": name, "extDescription": description}, indent=2) + "\n"
    )
    (ext / "src" / "locales" / "tr.json").write_text(
        json.dumps({"extName": name, "extDescription": description}, indent=2) + "\n"
    )

    # public/ icons — real placeholder PNGs so the build has assets immediately.
    for icon_size in (16, 48, 128):
        _write_placeholder_png(ext / "public" / f"icon{icon_size}.png", icon_size)

    # 2. Server files (FastAPI)
    server_pkg_dir = project_dir / "server" / "src" / package_name

    # server/src/<package_name>/__init__.py
    (server_pkg_dir / "__init__.py").write_text("")

    # server/src/<package_name>/logger.py — structlog JSON logger with PII redaction
    (server_pkg_dir / "logger.py").write_text(_logger_py_content(name, package_name))

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

    # compose.yaml — chrome-extension's backend ships an FastAPI server
    # at port 8000 and the extension hits it cross-origin, so we add CORS
    # middleware via Traefik. B16/B18: the previous inline compose had
    # no Traefik labels at all and used unexpanded ``${PORT:-8000}`` for
    # the host port, so the deployed backend 404'd at the gateway.
    _write_canonical_compose(
        project_dir,
        name,
        port=8000,
        healthcheck_path="/health",
        extra_labels=(
            f"traefik.http.middlewares.{name}-cors.headers.accesscontrolallowmethods=GET,POST,PUT,DELETE,OPTIONS",
            f"traefik.http.middlewares.{name}-cors.headers.accesscontrolalloworiginlist=chrome-extension://*",
            f"traefik.http.middlewares.{name}-cors.headers.accesscontrolallowheaders=*",
            f"traefik.http.middlewares.{name}-cors.headers.accesscontrolmaxage=100",
            f"traefik.http.routers.{name}.middlewares={name}-cors",
        ),
    )

    # 4. Makefile
    (project_dir / "Makefile").write_text(
        f""".PHONY: dev dev-server dev-ext build-ext install test docker-build docker-smoke clean

PROJECT_NAME := {name}
PORT := 8000

# Parallel dev: WXT dev server + server uvicorn reload
dev:
\t@trap 'kill 0' SIGINT; \\
\tcd extension && pnpm dev & \\
\t.venv/bin/uvicorn {package_name}.main:app --reload --host 0.0.0.0 --port $(PORT) --app-dir server/src & \\
\twait

# Server only (FastAPI with reload)
dev-server:
\t.venv/bin/uvicorn {package_name}.main:app --reload --host 0.0.0.0 --port $(PORT) --app-dir server/src

# Extension only (WXT dev with HMR)
dev-ext:
\tcd extension && pnpm dev

# Production extension build (WXT → extension/.output/chrome-mv3)
build-ext:
\tcd extension && pnpm build

# Install all dependencies
install:
\tpython -m venv .venv
\t.venv/bin/pip install -r requirements.txt
\tcd extension && pnpm install

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
\trm -rf extension/.output extension/.wxt extension/node_modules
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
        _COMMON_GITIGNORE_PATTERNS
        + "\n"
        + _DROID_GITIGNORE_BLOCK
        + "\n"
        + "# Chrome extension-specific (WXT)\n"
        "extension/.output/\n"
        "extension/.wxt/\n"
        "extension/node_modules/\n"
        "\n"
        "# Python-specific\n"
        ".env.local\n"
        "venv/\n"
        ".venv/\n"
        "*.egg-info/\n"
        "output/\n"
        ".cache/\n"
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
                f"\n# Database (managed by Fabrik orchestrator on VPS via postgres registrar)\n"
                f"# Set via project .env (managed by `fabrik apply`): POSTGRES_PASSWORD\n"
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
    """Create the Expo (React Native) client + bundled FastAPI backend from
    templates/mobile-app/.

    Ships the full RN client (``src/``, Expo/babel/metro/tsconfig, ``.github``
    CI, ``.maestro`` E2E, jest, ``openapi.json`` + generated hey-api client) AND
    a minimal Pattern-A FastAPI backend (``server/``) that DOES deploy to the VPS
    via ``fabrik apply`` — mirroring ``_scaffold_chrome_extension``: the inline
    Dockerfile builds only the backend (the RN client is excluded from the image
    via a root-anchored ``.dockerignore``) and ``_write_canonical_compose``
    emits the Coolify-correct compose. The app identity (name/slug/bundle id/
    package/scheme) is substituted off the Obytes defaults so scaffolded apps
    don't collide on ``com.obytes`` / ``ObytesApp``.
    """
    import json
    import re

    slug = re.sub(r"[^a-z0-9]", "", name.lower())
    # Android package segments (and Expo slugs) must start with a letter, never a
    # digit — ``com.123shop`` is an invalid package. Prefix if empty or digit-first.
    if not slug or not slug[0].isalpha():
        slug = "app" + slug

    # 1. Wholesale copy of the template tree, minus scaffolder-only config,
    #    build cruft, and the files substituted / generated below. A wholesale
    #    copy (vs the old enumerated list) ensures server/, requirements*,
    #    openapi.json, .github CI, .maestro, jest config, eslint config, etc. all
    #    ship — the enumeration silently dropped most of them.
    _skip = {
        "node_modules",
        "__pycache__",
        ".git",
        "defaults.yaml",  # scaffolder shape config — read by the scaffolder, not shipped
        ".gitignore",  # generated below
        "package.json",  # name/description-substituted below
        "AGENTS.md.j2",  # rendered below
        "env.ts",  # identity-substituted below
        "app.config.ts",  # identity-substituted below
    }
    for entry in sorted(MOBILE_APP_TEMPLATE_DIR.iterdir()):
        if entry.name in _skip:
            continue
        dest = project_dir / entry.name
        if entry.is_dir():
            shutil.copytree(
                entry,
                dest,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("node_modules", "__pycache__", "*.pyc"),
            )
        else:
            shutil.copy2(entry, dest)

    # 2. package.json — name + description substitution; also rewrite the Obytes
    #    bundle id in the maestro `e2e-test` script (APP_ID=com.obytes.development)
    #    to the project's, matching the env.ts/app.config.ts identity substitution.
    pkg = json.loads((MOBILE_APP_TEMPLATE_DIR / "package.json").read_text())
    pkg["name"] = name
    pkg["description"] = description
    pkg_text = (json.dumps(pkg, indent=2) + "\n").replace("com.obytes", f"com.{slug}")
    (project_dir / "package.json").write_text(pkg_text)

    # 3. env.ts / app.config.ts — replace the Obytes app identity (display name,
    #    slug, bundle id, package, scheme) with the project's, so two scaffolded
    #    apps don't ship the same `com.obytes` bundle id / `ObytesApp` name.
    env_text = (MOBILE_APP_TEMPLATE_DIR / "env.ts").read_text()
    env_text = (
        env_text.replace("com.obytes", f"com.{slug}")
        .replace("'ObytesApp'", f"'{name}'")
        .replace("obytesApp", slug)
    )
    (project_dir / "env.ts").write_text(env_text)
    appcfg_src = MOBILE_APP_TEMPLATE_DIR / "app.config.ts"
    if appcfg_src.exists():
        # Blank the Obytes Expo account owner + shared EAS project id: each
        # scaffolded app must bind its OWN (via `eas init`), never ship on
        # Obytes's account/project.
        appcfg_text = (
            appcfg_src.read_text()
            .replace("'obytesapp'", f"'{slug}'")
            .replace("const EXPO_ACCOUNT_OWNER = 'obytes';", "const EXPO_ACCOUNT_OWNER = '';")
            .replace(
                "const EAS_PROJECT_ID = 'c3e1075b-6fe7-4686-aa49-35b46a229044';",
                "const EAS_PROJECT_ID = '';",
            )
        )
        (project_dir / "app.config.ts").write_text(appcfg_text)

    # 4. AGENTS.md — render the .j2 (simple {{ spec.name }} substitution).
    agents_j2 = MOBILE_APP_TEMPLATE_DIR / "AGENTS.md.j2"
    if agents_j2.exists():
        (project_dir / "AGENTS.md").write_text(
            agents_j2.read_text().replace("{{ spec.name }}", name)
        )

    # 5. .gitignore — fabrik blocks + Expo patterns.
    (project_dir / ".gitignore").write_text(
        _COMMON_GITIGNORE_PATTERNS
        + "\n"
        + _DROID_GITIGNORE_BLOCK
        + "\n"
        + "# Expo / React Native\n"
        ".expo/\n"
        "dist/\n"
        "web-build/\n"
        "expo-env.d.ts\n"
        "/ios/\n"
        "/android/\n"
        "\n"
        "# Metro / logs\n"
        "*.log\n"
        ".metro-health-check*\n"
    )

    # 6. Backend Dockerfile (inline, FastAPI — package ``app``), mirroring
    #    _scaffold_chrome_extension. The RN client is excluded via .dockerignore.
    (project_dir / "Dockerfile").write_text(
        """FROM python:3.12-slim-bookworm AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim-bookworm
WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

ENV PYTHONPATH=/app/server/src
ENV PORT=8000

EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \\
  CMD curl -f http://localhost:${PORT}/health || exit 1

# Copy Python packages and binaries from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY requirements.txt .
COPY server/ ./server/

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
"""
    )

    # 7. compose.yaml — canonical Coolify-correct helper. No CORS labels: a
    #    native RN client makes no cross-origin browser requests (unlike the
    #    chrome extension), so it needs no Traefik CORS middleware. 256M matches
    #    the mobile-app _TYPE_DEFAULTS row.
    _write_canonical_compose(
        project_dir,
        name,
        port=8000,
        healthcheck_path="/health",
        memory="256M",
    )

    # 8. .dockerignore — the backend image ships server/ only. Exclude the RN
    #    client with ROOT-ANCHORED patterns: an unanchored ``src/`` would also
    #    match the backend's own ``server/src/`` and empty it in the image,
    #    breaking ``uvicorn app.main:app``.
    (project_dir / ".dockerignore").write_text(
        "# Backend image ships server/ only — exclude the RN client (root-anchored).\n"
        "/src/\n"
        "/node_modules/\n"
        "/.expo/\n"
        "/ios/\n"
        "/android/\n"
        "/dist/\n"
        "/web-build/\n"
        "/.maestro/\n"
        "/assets/\n"
        "*.log\n"
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
        _COMMON_GITIGNORE_PATTERNS + "\n" + _DROID_GITIGNORE_BLOCK + "\n" + "# Electron-specific\n"
        "node_modules/\n"
        "dist/\n"
        "output/\n"
        "\n"
        "# Node.js-specific\n"
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
        "  // B43: ``warn`` instead of ``throw``. The scaffold imports the\n"
        "  // full Fabrik docs tree (BUSINESS_MODEL.md, STRATEGIC_BACKLOG.md,\n"
        "  // README.md, etc.) which contain inter-doc links written for the\n"
        "  // GitHub renderer (relative paths, ``.md`` suffixes, anchors that\n"
        "  // don't match Docusaurus's slugified IDs). ``throw`` would block\n"
        "  // every single proof-run on the first dangling link; ``warn``\n"
        "  // surfaces the same information in build logs without failing.\n"
        "  onBrokenLinks: 'warn',\n"
        "  onBrokenMarkdownLinks: 'warn',\n"
        "\n"
        "  // B42: treat ``.md`` files as plain CommonMark, ``.mdx`` as MDX.\n"
        "  // Without this Docusaurus 3.x runs every ``.md`` through MDX 3,\n"
        "  // which rejects markdown tables containing ``[brackets]``,\n"
        "  // template-literal-like ``${var}`` strings, raw HTML attribute\n"
        "  // values, and various other constructs that the scaffold's\n"
        "  // standard meta-docs (``BUSINESS_MODEL.md``, ``CONFIGURATION.md``,\n"
        "  // ``FEATURES.md``, ``QUICKSTART.md``) all contain. Surfaced by\n"
        "  // proof-run on 2026-04-28.\n"
        "  markdown: {\n"
        "    format: 'detect',\n"
        "  },\n"
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
        "        },\n"
        "        blog: false,\n"
        "        theme: {\n"
        "          customCss: './src/css/custom.css',\n"
        "        },\n"
        "      }),\n"
        "    ],\n"
        "  ],\n"
        "\n"
        "  // B38: ``docusaurus-plugin-openapi-docs`` and its theme were\n"
        "  // removed from the default scaffold. The 4.3.x line passes an\n"
        "  // options object to webpack's ProgressPlugin that fails schema\n"
        "  // validation under @docusaurus/core 3.10.x (unknown properties:\n"
        "  // 'name', 'color', 'reporters', 'reporter'). A bare Docusaurus\n"
        "  // site builds and deploys cleanly; users who need OpenAPI-driven\n"
        "  // API docs can opt back in by adding the plugin + theme and\n"
        "  // restoring the apiSidebar. Surfaced by proof-run on 2026-04-28.\n"
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
        "        ],\n"
        "      },\n"
        "      footer: {\n"
        "        style: 'dark',\n"
        "        links: [\n"
        "          {\n"
        "            title: 'Docs',\n"
        "            items: [\n"
        "              { label: 'Getting Started', to: '/docs/intro' },\n"
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

    # B38: sidebars.js without the apiSidebar entry (openapi plugin
    # dropped from defaults). guideSidebar is autogenerated from the
    # ``docs/`` tree, which now contains only ``intro.md`` plus whatever
    # the user adds. Removing apiSidebar also removes the dangling
    # ``require("./docs/api/sidebar.js")`` which would otherwise crash
    # ``npm run build`` once that file is also gone.
    (project_dir / "sidebars.js").write_text(
        "// @ts-check\n"
        "/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */\n"
        "const sidebars = {\n"
        "  // Instructional Guides\n"
        "  guideSidebar: [{type: 'autogenerated', dirName: '.'}],\n"
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
    # B37: empty placeholder. The previous version referenced a doc
    # ``api/health-check`` that was never generated, causing every fresh
    # docusaurus scaffold to fail ``npm run build`` with::
    #
    #   Invalid sidebar file at "sidebars.js".
    #   These sidebar document ids do not exist: - api/health-check
    #
    # The real ``api/`` subtree is meant to be produced by
    # ``docusaurus-plugin-openapi-docs`` via ``npm run gen-api``; until
    # that runs there are no docs under ``docs/api/``, so the placeholder
    # must be empty (not stub-pointing at a non-existent doc).
    # Surfaced by proof-run on 2026-04-28.
    (api_dir / "sidebar.js").write_text(
        "// Auto-generated placeholder — empty until `npm run gen-api`\n"
        "// regenerates this file from openapi.yaml via\n"
        "// docusaurus-plugin-openapi-docs.\n"
        "module.exports = [];\n"
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
        _COMMON_GITIGNORE_PATTERNS
        + "\n"
        + _DROID_GITIGNORE_BLOCK
        + "\n"
        + "# Docusaurus-specific\n"
        "node_modules/\n"
        ".docusaurus/\n"
        "build/\n"
        "\n"
        "# Node.js-specific\n"
        "npm-debug.log*\n"
        "yarn-debug.log*\n"
    )

    # B36: render Dockerfile from the shipped Dockerfile.j2 template.
    # The scaffolder previously generated ``compose.yaml``, ``package.json``,
    # ``docusaurus.config.js`` and the docs tree but \u2014 as discovered by
    # proof-run on 2026-04-28 \u2014 silently skipped the Dockerfile, so Coolify's
    # buildpack failed at:
    #   failed to read dockerfile: open Dockerfile: no such file or directory
    # The .j2 here has no actual Jinja vars; it's a literal Dockerfile that
    # needs ``npm ci`` swapped for ``npm install`` (no lockfile is generated
    # at scaffold time \u2014 same pattern as ``_scaffold_node_api``,
    # ``_scaffold_file_api``, ``_scaffold_saas_skeleton``).
    dockerfile_src = DOCUSAURUS_TEMPLATE_DIR / "Dockerfile.j2"
    if dockerfile_src.exists():
        dockerfile = dockerfile_src.read_text().replace("RUN npm ci", "RUN npm install")
        (project_dir / "Dockerfile").write_text(dockerfile)

    # B20+B45: Coolify-correct compose for git-source deploys. Docusaurus
    # serves its built static site on port 3000 by default
    # (``docusaurus serve`` or the production server output of
    # ``docusaurus build``). Healthcheck hits ``/docs/intro`` instead of
    # ``/`` because Docusaurus's preset-classic does NOT auto-generate a
    # root landing page \u2014 ``/`` returns 404 (404.html), while
    # ``/docs/intro`` is the first guaranteed-200 page (the scaffolder
    # always emits ``docs/intro.md``). Surfaced by proof-run on
    # 2026-04-28: container ran fine, ``docusaurus serve`` reported
    # success, but the healthcheck looped 404 for the entire start
    # period and Coolify marked the app exited:unhealthy.
    _write_canonical_compose(
        project_dir,
        name,
        port=3000,
        healthcheck_path="/docs/intro",
    )


# ---------------------------------------------------------------------------
# i18n-kit provisioning
# ---------------------------------------------------------------------------


def _provision_i18n(project_dir: Path, project_type: str) -> None:
    """Copy i18n-kit files appropriate for ``project_type`` into the project.

    Called from ``create_project`` after the type-specific scaffolder has run,
    so all destination directories already exist.  Only runs for types listed
    in :data:`I18N_ENABLED_TYPES`.
    """
    strategy = I18N_ENABLED_TYPES.get(project_type)
    if not strategy or not I18N_KIT_DIR.exists():
        return

    kit = I18N_KIT_DIR

    # --- Always copy: validator + examples + plan doc ---
    scripts_dir = project_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(kit / "scripts" / "validate_i18n.py", scripts_dir / "validate_i18n.py")

    # Determine the JSON source directory based on strategy
    if strategy == "react":
        json_dir = project_dir / "public" / "i18n"
    elif strategy == "docusaurus":
        json_dir = project_dir / "i18n-source"
    else:
        json_dir = project_dir / "static" / "i18n"

    json_dir.mkdir(parents=True, exist_ok=True)

    # Copy en.json starter + example files
    for f in kit.glob("static/i18n/*.json"):
        shutil.copy2(f, json_dir / f.name)

    # Copy the multilingual plan doc
    docs_ref = project_dir / "docs" / "reference"
    docs_ref.mkdir(parents=True, exist_ok=True)
    shutil.copy2(kit / "docs" / "multilingual-plan.md", docs_ref / "multilingual-plan.md")

    # --- Strategy-specific files ---

    if strategy == "vanilla":
        # static-site, desktop-app: DOM-based loader + HTML snippets
        js_dir = project_dir / "static" / "js"
        js_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(kit / "static" / "js" / "i18n.js", js_dir / "i18n.js")
        snippets_dir = project_dir / "docs" / "reference" / "i18n-snippets"
        snippets_dir.mkdir(parents=True, exist_ok=True)
        for f in (kit / "snippets").iterdir():
            if f.is_file():
                shutil.copy2(f, snippets_dir / f.name)

    elif strategy == "react":
        # saas-skeleton (Next.js): React provider + server helpers + switcher
        i18n_lib = project_dir / "lib" / "i18n"
        i18n_lib.mkdir(parents=True, exist_ok=True)
        for f in (kit / "react").iterdir():
            if f.is_file():
                shutil.copy2(f, i18n_lib / f.name)

    elif strategy == "rn":
        # mobile-app (React Native): adapter that syncs to src/locales/
        shutil.copy2(kit / "adapters" / "sync_rn_locales.py", scripts_dir / "sync_rn_locales.py")

    elif strategy == "docusaurus":
        # Docusaurus: adapter that syncs custom strings to i18n/<lang>/code.json
        shutil.copy2(kit / "adapters" / "sync_docusaurus.py", scripts_dir / "sync_docusaurus.py")

    logger.info("i18n-kit provisioned (%s strategy) for %s", strategy, project_dir.name)


def _scaffold_python_api_gpu(
    project_dir: Path, name: str, description: str, **kwargs: object
) -> None:
    """python-api-gpu = python-api + an on-demand GPU rental helper.

    Identical to python-api PLUS ``src/<package>/gpu_handler.py``, which wraps
    ``fabrik.orchestrator.gpu_rent.rent()`` so the service can rent a GPU
    imperatively from its job handler (workload tag = project_name).

    The deploy *shape* is the standard python-api shape (see
    ``templates/python-api-gpu/defaults.yaml``); the spec is generated by
    ``create_project`` from that defaults file like any other spec-enabled
    type. GPU *auto-provisioning* — a ``shape.needs_gpu`` flag plus a GPU
    registrar in ``resolve_applicability`` — is a separate vertical slice in
    the GPU subsystem and is intentionally NOT injected here (the ``Shape``
    model has no such field yet; injecting it would make the spec fail to load).
    """
    # Build the normal python-api scaffold first; the GPU spec shape comes from
    # templates/python-api-gpu/defaults.yaml through the normal spec path.
    _scaffold_python_api(project_dir, name, description, **kwargs)

    # Add a GPU integration helper module INSIDE the package (python-api uses a
    # src/<package>/ layout — app/ would be orphaned, outside the importable pkg).
    package_name = _get_package_name(name)
    gpu_handler_path = project_dir / "src" / package_name / "gpu_handler.py"
    gpu_handler_path.parent.mkdir(parents=True, exist_ok=True)
    gpu_handler_path.write_text(f'''"""GPU rental integration for {name}.

This module is the bridge between the service's job handler and
``fabrik.orchestrator.gpu_rent.rent``. Use ``rent_for_workload(...)`` to
provision a GPU on demand for a single job, then auto-destroy.

Configuration is read from the spec's ``shape.gpu_kind`` field — change
that in ``specs/services/{name}.yaml`` (default: pod-rtx-4090).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

# Default kind for this service — override per call if needed
DEFAULT_KIND = "pod-rtx-4090"
DEFAULT_MAX_LIFETIME_HOURS = 1
DEFAULT_MAX_COST_USD = 1.0


def rent_for_workload(
    workload: str,
    work_fn: Callable[[dict[str, Any]], Any],
    *,
    kind: str = DEFAULT_KIND,
    max_lifetime_hours: int = DEFAULT_MAX_LIFETIME_HOURS,
    max_cost_usd: float = DEFAULT_MAX_COST_USD,
) -> dict[str, Any]:
    """Provision a GPU, run ``work_fn(pod_or_endpoint_dict)``, always destroy.

    Wraps ``fabrik.orchestrator.gpu_rent.rent`` with this project's defaults.
    """
    from fabrik.orchestrator.gpu_rent import rent

    return rent(
        kind,
        workload=workload,
        max_lifetime_hours=max_lifetime_hours,
        max_cost_usd=max_cost_usd,
        work_fn=work_fn,
    )
''')

    logger.info("python-api-gpu scaffolded for %s (gpu_kind=pod-rtx-4090)", name)


# Dispatch table mapping project types to their scaffolder functions.
_TYPE_SCAFFOLDERS: dict[str, Callable[..., None]] = {
    "python-api": _scaffold_python_api,
    "python-api-gpu": _scaffold_python_api_gpu,  # NEW: Phase 5
    # NB: "wordpress" is intentionally NOT here — scaffolding moved to /opt/wpf
    # (see create_project's redirect). It stays in SCAFFOLD_TYPES for deploy/shape.
    "saas-skeleton": _scaffold_saas_skeleton_with_docs,
    "node-api": _scaffold_node_api,
    "file-api": _scaffold_file_api,
    "file-worker": _scaffold_file_worker,
    "docusaurus": _scaffold_docusaurus,
    "chrome-extension": _scaffold_chrome_extension,
    "mobile-app": _scaffold_mobile_app,
    "desktop-app": _scaffold_desktop_app,
    "static-site": _scaffold_saas_skeleton,
}


def _post_scaffold_sync(project_dir: Path) -> None:
    """Post-scaffold hook: update project registry and PROJECT_CATALOG.md.

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


def _layer_preplan_into_project(project_dir: Path, preplan: object) -> None:
    """T3-01 G-A4: copy the preplan + inject reference line into all 4 AI guardrails.

    Stage-1 of the Fabrik lifecycle says every agent that opens the project
    should know the original intent. Putting a single ``Preplan:`` reference
    in just one guardrail file would mean Claude Code / Kilo / Windsurf
    miss it — only Traycer would see it. So we inject the line into all 4:

    - ``AGENTS.md`` (Traycer)
    - ``CLAUDE.md`` (Claude Code)
    - ``AGENTS-compact.md`` (Kilo)
    - ``.windsurfrules`` (Windsurf)

    The reference path is RELATIVE to project root so the line stays valid
    if the project tree moves.

    Args:
        project_dir: The freshly-scaffolded project root.
        preplan: A :class:`fabrik.preplan.Preplan` instance (parsed by
            ``parse_preplan``). Accepts ``object`` in the signature to
            avoid a heavy import — duck-typed access to ``.path``.
    """
    if preplan is None:
        return
    source_path = getattr(preplan, "path", None)
    if source_path is None or not source_path.exists():
        logger.warning("preplan layering: source path missing; skipping")
        return

    # 1. Copy preplan into project's docs/ dir
    project_docs = project_dir / "docs"
    project_docs.mkdir(parents=True, exist_ok=True)
    dest = project_docs / "preplan.md"
    dest.write_text(source_path.read_text(encoding="utf-8"))

    # 2. Inject a Preplan reference line into each of the 4 AI guardrails
    reference_line = (
        "\n> **Preplan:** [docs/preplan.md](docs/preplan.md) "
        f"(original intent captured {getattr(preplan, 'date', 'pre-scaffold')}). "
        "Read it for the project's Idea, Shape, External deps, Success criteria, "
        "and VPS1-inventory reminders before proposing changes.\n"
    )
    guardrail_files = [
        "AGENTS.md",
        "CLAUDE.md",
        "AGENTS-compact.md",
        ".windsurfrules",
    ]
    for fname in guardrail_files:
        target = project_dir / fname
        if not target.exists():
            # Some scaffold types may not emit all 4 (e.g. static-site
            # might skip .windsurfrules). Skip silently.
            continue
        try:
            content = target.read_text(encoding="utf-8")
            # Idempotent: if a Preplan reference already exists, don't dup.
            if "Preplan:" in content and "docs/preplan.md" in content:
                continue
            target.write_text(content.rstrip() + "\n" + reference_line)
        except Exception as e:  # noqa: BLE001
            logger.warning("preplan layering: %s update failed: %s", fname, e)

    logger.info(
        "preplan layering: copied to %s + reference injected into 4 guardrails",
        dest.relative_to(project_dir),
    )


def create_project(
    name: str,
    description: str,
    base: Path = Path("/opt"),
    project_type: str = "python-api",
    preset: str | None = None,
    generate_spec: bool = True,
    preplan: object = None,  # T3-01: a fabrik.preplan.Preplan instance or None
    **kwargs: object,
) -> Path:
    """Create a new project with full structure.

    T3-01: when ``preplan`` is provided (parsed via
    ``fabrik.preplan.parse_preplan``), the resulting project gets the
    preplan layered in as Stage-1 context:

    - Preplan markdown copied to ``<project>/docs/preplan.md``
    - A ``Preplan: docs/preplan.md`` reference line appended to each of
      the 4 AI guardrail files (AGENTS.md, CLAUDE.md, AGENTS-compact.md,
      .windsurfrules) so every agent that opens the project knows the
      original intent.
    - The shape block, domain, and secrets list from the preplan are
      passed through to the spec generator (post-scaffold hook).
    """
    # Validate inputs
    _validate_project_name(name)
    _assert_not_hub(Path(base) / name)

    if project_type not in SCAFFOLD_TYPES:
        valid = ", ".join(sorted(SCAFFOLD_TYPES))
        raise ValueError(f"Invalid project type: '{project_type}'. Valid types: {valid}")

    project_dir = base / name
    if project_dir.exists():
        raise ValueError(f"Project already exists: {project_dir}")

    # Resolve the type-specific scaffolder BEFORE writing anything so that an
    # unimplemented (or redirected) type raises immediately, leaving no
    # partial project directory on disk.
    if project_type not in _TYPE_SCAFFOLDERS:
        if project_type == "wordpress":
            # Scaffolding moved to the standalone /opt/wpf project (2026-06-17).
            # `wordpress` stays in SCAFFOLD_TYPES for deploy/shape routing, but
            # there is no scaffolder here. cli.py intercepts this earlier with a
            # clean message; this guard covers direct create_project() callers.
            raise NotImplementedError(
                "WordPress scaffolding has moved to the standalone /opt/wpf "
                f"project — use the `wpf` CLI (e.g. `wpf new {name}`) instead of "
                "`fabrik scaffold --type wordpress`."
            )
        raise NotImplementedError(f"Scaffolder for '{project_type}' not yet implemented")
    scaffolder = _TYPE_SCAFFOLDERS[project_type]

    today = date.today().isoformat()

    # Determine port based on project type before scaffolding (used in doc templates)
    if project_type in ("node-api", "file-api", "saas-skeleton", "static-site"):
        host_port = _next_available_port(port_range=(3000, 3099))
    else:
        host_port = _next_available_port(port_range=(8000, 8099))

    # _scaffold_shared() creates all shared structure AND runs git init + pre-commit install.
    _scaffold_shared(project_dir, name, description, today, host_port, project_type)

    scaffolder(project_dir, name, description, preset=preset, **kwargs)

    # CI-parity (Fix B): Python API types get ci.yml + ci_local.sh from one source, so
    # "green locally" (scripts/ci_local.sh) means "green CI". needs_database reuses the
    # same signal the compose scaffolder uses; pgvector/web toggles come from the spec.
    if project_type in _CI_PYTHON_TYPES:
        _write_ci_files(project_dir, needs_database=bool(kwargs.get("use_database", False)))

    # Provision i18n-kit for GUI-enabled scaffold types
    _provision_i18n(project_dir, project_type)

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

    # T3-01 G-A4: layer preplan context BEFORE the final commit so the
    # preplan copy + 4-file guardrail reference are part of the initial
    # snapshot.
    if preplan is not None:
        _layer_preplan_into_project(project_dir, preplan)

    # Final commit after all files (shared + type-specific) are in place so the
    # initial snapshot is complete and clean.
    subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "Initial commit"], cwd=project_dir, capture_output=True
    )

    # Post-scaffold hook: sync project registry
    _post_scaffold_sync(project_dir)

    # Auto-generate deployment spec for supported types.
    # ``use_database`` propagates the CLI ``--db`` flag through so the emitted
    # spec carries ``shape.needs_database: true`` and the postgres registrar
    # fires on ``fabrik apply``. Pre-fix (B1) the flag was silently dropped,
    # so DB-backed projects deployed without a VPS Postgres database.
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
                use_database=bool(kwargs.get("use_database", False)),
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

    Handles three cases:
    1. Canonical block already present → no-op
    2. .droid/ or .factory/ entries exist (scattered or contiguous) → replace with canonical
    3. No managed entries → append canonical block at end

    Args:
        content: Current .gitignore file content
        canonical: Canonical .droid/ gitignore block (_DROID_GITIGNORE_BLOCK)

    Returns:
        Updated .gitignore content
    """
    # Fast path: canonical block already present verbatim
    if canonical in content:
        return content

    lines = content.splitlines(keepends=True)
    # Match both .droid/ and .factory/ lines — both are part of the canonical block
    managed_prefixes = (".droid/", ".factory/")
    managed_indices = {
        i for i, line in enumerate(lines) if line.strip().startswith(managed_prefixes)
    }

    if not managed_indices:
        # No managed entries — append canonical block
        return content.rstrip("\n") + "\n" + canonical

    # Remove all managed lines and insert canonical block at position of first one
    first_managed = min(managed_indices)
    filtered_lines = [line for i, line in enumerate(lines) if i not in managed_indices]
    return (
        "".join(filtered_lines[:first_managed])
        + canonical
        + "".join(filtered_lines[first_managed:])
    )


def fix_project(
    project_path: Path,
    dry_run: bool = False,
    project_type: str = "python-api",
) -> list[str]:
    """Add missing required files to a project. Returns list of files added."""
    from datetime import date

    project_path = Path(project_path)
    _assert_not_hub(project_path)
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

        # Copy docs/reference/kilo/ directory (remove symlink if exists)
        fabrik_kilo_docs = FABRIK_ROOT / "docs" / "reference" / "kilo"
        if fabrik_kilo_docs.exists():
            kilo_path = project_path / "docs" / "reference" / "kilo"
            if kilo_path.is_symlink():
                kilo_path.unlink()
            elif kilo_path.exists():
                shutil.rmtree(kilo_path)
            kilo_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(fabrik_kilo_docs, kilo_path)
            added.append("docs/reference/kilo (copied)")

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

        # Copy .windsurf/hooks.json (rewriting cwd to point at the project)
        hooks_path = project_path / ".windsurf" / "hooks.json"
        if hooks_path.is_symlink():
            hooks_path.unlink()
        if _copy_windsurf_hooks(project_path):
            added.append(".windsurf/hooks.json (copied)")

        # Copy AFCL.md (Agentic Friction & Constraint Log template)
        # Only created if missing — preserves accumulated project-specific findings.
        # Once a project starts logging friction/constraints into AFCL, those entries
        # are project-local lore that fix_project must not overwrite.
        afcl_template = FABRIK_ROOT / "templates" / "scaffold" / "AFCL_TEMPLATE.md"
        afcl_target = project_path / "AFCL.md"
        if afcl_template.exists() and not afcl_target.exists():
            shutil.copy(afcl_template, afcl_target)
            added.append("AFCL.md (created)")

        # Always refresh opencode.json from master (single source of truth)
        fabrik_opencode = FABRIK_ROOT / "opencode.json"
        if fabrik_opencode.exists():
            shutil.copy(fabrik_opencode, project_path / "opencode.json")
            added.append("opencode.json (refreshed from master)")

        # Always refresh reference docs from canonical source — Fabrik root is
        # authoritative and these files may have been updated since last fix.
        for doc_name in ["technology-stack-decision-guide.md", "prebuilt-app-containers.md"]:
            source = FABRIK_ROOT / "docs" / "reference" / doc_name
            if source.exists():
                target = project_path / "docs" / "reference" / doc_name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(source, target)
                added.append(f"docs/reference/{doc_name} (refreshed from master)")

        # Always refresh KILO_AGENT_NAMING.md from canonical source.
        kilo_naming_source = FABRIK_ROOT / "docs" / "reference" / "kilo" / "KILO_AGENT_NAMING.md"
        if kilo_naming_source.exists():
            kilo_naming_target = (
                project_path / "docs" / "reference" / "kilo" / "KILO_AGENT_NAMING.md"
            )
            kilo_naming_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(kilo_naming_source, kilo_naming_target)
            added.append("docs/reference/kilo/KILO_AGENT_NAMING.md (refreshed from master)")

        # Always refresh kilo_47_agents_final.json from canonical source.
        kilo_config_source = FABRIK_ROOT / "scripts" / "kilo_47_agents_final.json"
        if kilo_config_source.exists():
            kilo_config_target = project_path / "scripts" / "kilo_47_agents_final.json"
            kilo_config_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(kilo_config_source, kilo_config_target)
            added.append("scripts/kilo_47_agents_final.json (refreshed from master)")

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

        # .windsurf/hooks.json - always copied (with cwd rewrite)
        if FABRIK_WINDSURF_HOOKS.exists():
            added.append(".windsurf/hooks.json (copied)")

        # AFCL.md - only created if missing (preserves project-local findings)
        afcl_template = FABRIK_ROOT / "templates" / "scaffold" / "AFCL_TEMPLATE.md"
        afcl_target = project_path / "AFCL.md"
        if afcl_template.exists() and not afcl_target.exists():
            added.append("AFCL.md (created)")

        # opencode.json — always refresh
        if (FABRIK_ROOT / "opencode.json").exists():
            added.append("opencode.json (refresh from master)")

        # Reference docs — always refreshed (no longer guarded by "missing only")
        for doc_name in ["technology-stack-decision-guide.md", "prebuilt-app-containers.md"]:
            source = FABRIK_ROOT / "docs" / "reference" / doc_name
            if source.exists():
                added.append(f"docs/reference/{doc_name} (refreshed from master)")

        # KILO_AGENT_NAMING.md — always refreshed
        if (FABRIK_ROOT / "docs" / "reference" / "kilo" / "KILO_AGENT_NAMING.md").exists():
            added.append("docs/reference/kilo/KILO_AGENT_NAMING.md (refreshed from master)")

        # kilo_47_agents_final.json — always refreshed
        if (FABRIK_ROOT / "scripts" / "kilo_47_agents_final.json").exists():
            added.append("scripts/kilo_47_agents_final.json (refreshed from master)")

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
