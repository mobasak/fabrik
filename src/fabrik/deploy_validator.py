"""Deployment readiness validator — checks scaffolded projects before fabrik apply."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from fabrik.template_renderer import TemplateRenderer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data container
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationResult:
    """Result of a single deployment readiness check."""

    check: str
    passed: bool
    message: str


# ---------------------------------------------------------------------------
# Node-type scaffold types (used for health endpoint file extension selection)
# ---------------------------------------------------------------------------

_NODE_TYPES: frozenset[str] = frozenset(
    {
        "saas-skeleton",
        "node-api",
        "file-api",
        "static-site",
        "desktop-app",
        "docusaurus",
    }
)

_STATIC_TYPES: frozenset[str] = frozenset({"docusaurus", "static-site"})
_ELECTRON_TYPES: frozenset[str] = frozenset({"desktop-app"})

# Types whose validator does NOT require the standard root-Dockerfile check:
#  - docusaurus / static-site → static files (Netlify / Vercel / S3)
#  - desktop-app → binaries (distributable installers)
#  - chrome-extension / mobile-app → mixed layout: the CLIENT lives at the repo
#    root and the deployable FastAPI backend under ``server/``, so the scaffolder
#    DOES emit a root Dockerfile (building only ``server/``) but the standard
#    "src/-app needs a root Dockerfile" requirement is skipped for this shape.
#  - wordpress → uses compose.yaml(.j2) with multi-stage php-fpm/ + nginx/ Dockerfiles,
#    never a root-level Dockerfile
_NO_DOCKERFILE_TYPES: frozenset[str] = frozenset(
    {
        "docusaurus",
        "static-site",
        "mobile-app",
        "desktop-app",
        "chrome-extension",
        "wordpress",
    }
)

# Types whose application code does NOT live under src/ (different layout):
#  - saas-skeleton → Next.js app-router layout uses app/ + components/ + lib/
#  - chrome-extension → WXT extension (src/entrypoints, auto-manifest); backend at server/src/
#  - wordpress → wp-content/ + plugins/ + themes/ (no src/)
# static-site / docusaurus are already short-circuited as _STATIC_TYPES above.
_NO_SRC_LAYOUT_TYPES: frozenset[str] = frozenset(
    {
        "saas-skeleton",
        "chrome-extension",
        "wordpress",
    }
)

# Types that legitimately do NOT serve an HTTP /health endpoint:
#  - file-worker → background worker (processes tasks, uses worker/ dir, no HTTP server)
#  - desktop-app → electron/native desktop app, no HTTP server by default
# For these, operators monitor liveness via the process manager (Coolify container
# restart policy / watchdog scripts) rather than an HTTP route.
# NOTE: mobile-app is NOT here (plan-1 Phase C) — its bundled FastAPI backend serves
# /health under server/src/, which the health check validates (see _check_health_endpoint).
_NO_HTTP_HEALTH_TYPES: frozenset[str] = frozenset(
    {
        "file-worker",
        "desktop-app",
    }
)

# ---------------------------------------------------------------------------
# Private check functions
# ---------------------------------------------------------------------------


def _check_template_exists(project_type: str) -> ValidationResult:
    """Check whether a deploy template exists for the given project type."""
    renderer = TemplateRenderer()
    exists = renderer.template_exists(project_type)
    if exists:
        return ValidationResult(
            check="deploy_template",
            passed=True,
            message=f"Deploy template found: {project_type}",
        )
    return ValidationResult(
        check="deploy_template",
        passed=False,
        message=f"No deploy template for type: {project_type}",
    )


def _check_env_example(project_path: Path) -> ValidationResult:
    """Check whether .env.example is present in the project root."""
    if (project_path / ".env.example").exists():
        return ValidationResult(
            check="env_example",
            passed=True,
            message=".env.example present",
        )
    return ValidationResult(
        check="env_example",
        passed=False,
        message=".env.example missing — secrets cannot be detected",
    )


def _check_dockerfile(project_path: Path, project_type: str) -> ValidationResult:
    """Check whether a Dockerfile is present in the project root.

    Some project types legitimately don't produce a root-level Dockerfile —
    see ``_NO_DOCKERFILE_TYPES`` for the rationale per type. Returning
    ``passed=True`` with an explanatory message avoids alarming the operator
    after a clean scaffold.
    """
    if project_type in _NO_DOCKERFILE_TYPES:
        return ValidationResult(
            check="dockerfile",
            passed=True,
            message=f"N/A for {project_type} (no root Dockerfile expected)",
        )
    if (project_path / "Dockerfile").exists():
        return ValidationResult(
            check="dockerfile",
            passed=True,
            message="Dockerfile present",
        )
    return ValidationResult(
        check="dockerfile",
        passed=False,
        message="Dockerfile missing — container cannot be built",
    )


def _check_health_endpoint(project_path: Path, project_type: str) -> ValidationResult:
    """Check whether a /health endpoint is declared in the project src/ directory."""
    if project_type in _STATIC_TYPES:
        return ValidationResult(
            check="health_endpoint",
            passed=True,
            message="Static site — health check targets / (root), no /health route required",
        )

    # Project types whose code does NOT live under src/ use a different layout
    # convention (Next.js app/, chrome-extension root scripts, WordPress wp-content/).
    # Skip the src-based scan; operators verify health manually for these.
    if project_type in _NO_SRC_LAYOUT_TYPES:
        return ValidationResult(
            check="health_endpoint",
            passed=True,
            message=(
                f"N/A for {project_type} — code lives outside src/ "
                "(check manually if the project serves a /health route)"
            ),
        )

    # Project types that don't expose an HTTP /health route by design:
    # workers (file-worker), mobile apps, desktop apps. Liveness is monitored
    # at the process-manager layer instead.
    if project_type in _NO_HTTP_HEALTH_TYPES:
        return ValidationResult(
            check="health_endpoint",
            passed=True,
            message=(
                f"N/A for {project_type} — no HTTP server by design "
                "(liveness monitored by the process manager / watchdog)"
            ),
        )

    if project_type in _ELECTRON_TYPES:
        src_dir = project_path / "electron"
    elif project_type == "mobile-app":
        # The root src/ is the RN client; the deployable FastAPI backend (and
        # its /health route) lives under server/src/ — scan there, not src/.
        src_dir = project_path / "server" / "src"
    else:
        src_dir = project_path / "src"

    if not src_dir.exists():
        return ValidationResult(
            check="health_endpoint",
            passed=False,
            message="src/ directory not found",
        )

    # Select file extensions based on project type
    patterns = ["*.js", "*.ts"] if project_type in _NODE_TYPES else ["*.py"]

    for pattern in patterns:
        for source_file in src_dir.rglob(pattern):
            try:
                content = source_file.read_text(encoding="utf-8", errors="ignore")
                if "/health" in content:
                    return ValidationResult(
                        check="health_endpoint",
                        passed=True,
                        message="Health endpoint detected",
                    )
            except OSError:
                continue

    return ValidationResult(
        check="health_endpoint",
        passed=False,
        message="Health endpoint not detected (check manually for Node projects)",
    )


def _check_spec_exists(project_name: str, specs_dir: Path) -> ValidationResult:
    """Check whether a spec file already exists for this project (informational)."""
    spec_path = specs_dir / f"{project_name}.yaml"
    if spec_path.exists():
        return ValidationResult(
            check="spec_exists",
            passed=True,
            message="Spec already exists — will be overwritten by scaffold",
        )
    return ValidationResult(
        check="spec_exists",
        passed=True,
        message="No pre-existing spec (clean state)",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate(
    project_path: Path,
    project_type: str,
    specs_dir: Path | None = None,
) -> list[ValidationResult]:
    """Run all deployment readiness checks against a project.

    Args:
        project_path: Absolute path to the scaffolded project directory.
        project_type: Scaffold type (e.g. ``"python-api"``).
        specs_dir: Directory containing service specs. Defaults to
            ``/opt/fabrik/specs/services``.

    Returns:
        List of exactly 5 :class:`ValidationResult` objects (one per check).
    """
    if specs_dir is None:
        specs_dir = Path("/opt/fabrik/specs/services")

    project_name = project_path.name

    return [
        _check_template_exists(project_type),
        _check_env_example(project_path),
        _check_dockerfile(project_path, project_type),
        _check_health_endpoint(project_path, project_type),
        _check_spec_exists(project_name, specs_dir),
    ]


def format_warnings(results: list[ValidationResult]) -> list[str]:
    """Format failed checks as warning strings.

    Args:
        results: List of :class:`ValidationResult` objects.

    Returns:
        List of formatted warning strings for every result where
        ``passed`` is ``False``. Returns an empty list when all checks pass.
    """
    return [
        f"\u26a0\ufe0f  [{result.check}] {result.message}"
        for result in results
        if not result.passed
    ]
