"""Unified deploy entry point — routes deployment to the correct pipeline.

Resolves project type from ``project.yaml`` and delegates to either
the WordPress pipeline (Planner + SiteDeployer) or the generic
DeploymentOrchestrator for all other scaffold types.
"""

import logging
from pathlib import Path

import yaml

from fabrik.config import FABRIK_ROOT
from fabrik.notifications import notify_deploy
from fabrik.orchestrator import DeploymentOrchestrator, DeploymentState
from fabrik.scaffold import SCAFFOLD_TYPES

logger = logging.getLogger(__name__)


def resolve_project_dir(project_path: str | None) -> Path:
    """Return the absolute project directory.

    Args:
        project_path: Explicit path to the project folder, or *None*
            to use the current working directory.

    Returns:
        Resolved :class:`Path` to the project directory.

    Raises:
        RuntimeError: If the resolved directory does not exist.
    """
    project_dir = Path(project_path).resolve() if project_path is not None else Path.cwd()

    if not project_dir.is_dir():
        raise RuntimeError(f"Project directory does not exist: {project_dir}")

    return project_dir


def get_project_metadata(project_dir: Path) -> dict:
    """Load and return the contents of ``project.yaml``.

    Args:
        project_dir: Path to the project root.

    Returns:
        Parsed dict from ``project.yaml``.

    Raises:
        RuntimeError: If ``project.yaml`` is missing or unparseable.
    """
    project_yaml = project_dir / "project.yaml"
    if not project_yaml.is_file():
        raise RuntimeError(
            f"No project.yaml found in {project_dir}. "
            "Run 'fabrik scaffold' first or pass --project to a scaffolded project."
        )
    try:
        with open(project_yaml, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise RuntimeError(f"Failed to parse {project_yaml}: {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"project.yaml must be a YAML mapping, got {type(data).__name__}")

    return data


def get_project_type(project_dir: Path) -> str:
    """Return the validated ``type`` field from ``project.yaml``.

    Raises:
        RuntimeError: If the type field is missing or not a recognised scaffold type.
    """
    meta = get_project_metadata(project_dir)
    project_type = meta.get("type")
    if not project_type:
        raise RuntimeError(f"project.yaml in {project_dir} is missing a 'type' field.")
    if project_type not in SCAFFOLD_TYPES:
        raise RuntimeError(
            f"Unknown project type '{project_type}' in {project_dir}/project.yaml. "
            f"Valid types: {', '.join(sorted(SCAFFOLD_TYPES))}"
        )
    return str(project_type)


def resolve_service_spec_path(project_dir: Path) -> Path:
    """Return the path to the centralised service spec for a non-WordPress project.

    The spec is expected at ``FABRIK_ROOT / specs / services / <name>.yaml``
    where ``<name>`` is the ``name`` field from ``project.yaml``.

    Raises:
        RuntimeError: If the spec file does not exist.
    """
    meta = get_project_metadata(project_dir)
    project_name = meta.get("name")
    if not project_name:
        raise RuntimeError(f"project.yaml in {project_dir} is missing a 'name' field.")

    spec_path = FABRIK_ROOT / "specs" / "services" / f"{project_name}.yaml"
    if not spec_path.is_file():
        raise RuntimeError(
            f"No service spec found for project '{project_name}' "
            f"at specs/services/{project_name}.yaml"
        )
    return spec_path


def _deploy_wordpress(project_dir: Path, dry_run: bool) -> int:
    """WordPress deployment moved to /opt/wpf/ (standalone project).

    Use the `wpf` CLI: wpf plan <site> && wpf apply <site>
    """
    raise NotImplementedError(
        "WordPress deployment has moved to /opt/wpf/. "
        "Use the `wpf` CLI instead of `fabrik deploy` for WordPress projects."
    )


def _deploy_generic(project_dir: Path, dry_run: bool) -> int:
    """Run the generic orchestrator pipeline for non-WordPress projects.

    Returns:
        0 on success (``DeploymentState.COMPLETE``), 1 otherwise.
    """
    spec_path = resolve_service_spec_path(project_dir)

    logger.info("Deploying via orchestrator: %s", spec_path)
    orchestrator = DeploymentOrchestrator()
    ctx = orchestrator.deploy(spec_path, dry_run=dry_run)

    success = ctx.state == DeploymentState.COMPLETE
    spec = ctx.spec or {}
    notify_deploy(
        project=spec.get("name", str(spec_path)),
        domain=spec.get("domain", ""),
        success=success,
        url=ctx.deployed_url,
        error=ctx.error,
        error_step=ctx.error_step,
    )
    return 0 if success else 1


def route_deploy(project_dir: Path, project_type: str, dry_run: bool = False) -> int:
    """Dispatch deployment to the correct pipeline.

    Args:
        project_dir: Resolved project root.
        project_type: Validated scaffold type string.
        dry_run: If ``True``, simulate without side effects.

    Returns:
        Exit code — 0 for success, 1 for failure.
    """
    if project_type == "wordpress":
        return _deploy_wordpress(project_dir, dry_run=dry_run)
    return _deploy_generic(project_dir, dry_run=dry_run)
