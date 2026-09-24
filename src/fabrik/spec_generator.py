"""Spec generation and project context extraction for scaffold-to-deploy automation."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import yaml

from fabrik.spec_loader import (
    CompanionService,
    Expose,
    Health,
    Kind,
    Resources,
    SecretsPolicy,
    Shape,
    Source,
    SourceType,
    Spec,
    create_spec,
    save_spec,
)

# Templates directory — single source of truth for shape: blocks per scaffold type.
# Phase 4k moved shape defaults out of Python (`_TYPE_DEFAULTS`) and into
# `templates/<type>/defaults.yaml` so they can be grep'd / diff'd / version-controlled
# alongside the template itself.
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Project types that are deployed to the VPS via SSH + Docker Compose. Each
# of these gets an auto-generated ``specs/services/<name>.yaml`` so
# ``fabrik apply`` has something to consume.
#
# ``chrome-extension`` IS enabled because the scaffolder emits a real
# FastAPI backend at ``server/`` plus a canonical ``compose.yaml`` with
# Traefik labels + CORS middleware (see ``scaffold.py::_scaffold_chrome_extension``
# B16/B18 fixes). The CRX itself ships via the Chrome Web Store; the
# spec drives the **backend**, which is a real VPS service. Users who
# want a pure-client CRX with no backend can opt out via ``--no-spec``.
#
# **Excluded by design** (do NOT add):
#   - ``desktop-app`` / ``mobile-app``: packaged client artifacts
#     (.dmg/.exe installer, APK/IPA). The current scaffolder does NOT
#     emit a ``compose.yaml`` for these — they have no companion backend.
#     Tracked under Phase C (G11) for backend-scaffolding implementation.
#   - ``next-tailwind``: template files exist but no ``_scaffold_next_tailwind``
#     wired up yet; tracked as G10. Add to this set in the same change
#     that lands the scaffolder.
#   - ``wordpress``: out of fabrik — ``fabrik scaffold --type wordpress``
#     refuses with ``scaffold.WORDPRESS_REFUSAL`` (the standalone project is
#     archived and has no CLI); ``wordpress`` stays a recognised deploy/shape
#     type here.
SPEC_ENABLED_TYPES: frozenset[str] = frozenset(
    {
        "python-api",
        "python-api-gpu",  # python-api + GPU rental helper; same deploy shape
        "saas-skeleton",
        "node-api",
        "file-api",
        "file-worker",
        "static-site",
        "docusaurus",
        "chrome-extension",
        "mobile-app",  # ships a bundled FastAPI backend (port 8000, /health) like chrome-extension
    }
)

SECRET_PATTERNS: tuple[str, ...] = (
    "PASSWORD",
    "SECRET",
    "KEY",
    "TOKEN",
    "CREDENTIAL",
    "PRIVATE",
)

# Resource & health defaults per VPS-deployable project type. Keys MUST match
# ``SPEC_ENABLED_TYPES``; the artifact-only ``desktop-app`` has no entry because
# it doesn't deploy. ``chrome-extension`` and ``mobile-app`` ARE here because
# each bundles a FastAPI backend (port 8000, ``/health``) that is deployable.
_TYPE_DEFAULTS: dict[str, dict] = {
    "python-api": {"memory": "512M", "cpu": "0.5", "health_path": "/health"},
    "python-api-gpu": {"memory": "512M", "cpu": "0.5", "health_path": "/health"},
    "node-api": {"memory": "256M", "cpu": "0.5", "health_path": "/api/health"},
    "saas-skeleton": {"memory": "256M", "cpu": "0.5", "health_path": "/api/health"},
    "static-site": {"memory": "256M", "cpu": "0.5", "health_path": "/api/health"},
    "file-api": {"memory": "256M", "cpu": "0.5", "health_path": "/api/health"},
    "file-worker": {"memory": "256M", "cpu": "0.5", "health_path": None},
    "docusaurus": {"memory": "256M", "cpu": "0.5", "health_path": "/docs/intro"},
    "chrome-extension": {"memory": "256M", "cpu": "0.5", "health_path": "/health"},
    "mobile-app": {"memory": "256M", "cpu": "0.5", "health_path": "/health"},
}

# The audit-log jobs module (retention + the weekly chain verification, D-390 / spec § 3)
# of each Python backend that has no scheduler of its own, as the ``python -m`` module
# its image resolves (python-api: PYTHONPATH=/app/src; file-worker: /app; the ``server/``
# backends: /app/server/src). A database spec of one of these types declares the jobs as
# a companion service (core/30-ops.md § Multi-Service Compose). The saas family is absent
# on purpose: its worker's beat loop schedules the same jobs. ``{pkg}`` is the project's
# package name. The scaffolder emits the module at the matching path.
AUDIT_JOBS_MODULES: dict[str, str] = {
    "python-api": "{pkg}.audit_jobs",
    "python-api-gpu": "{pkg}.audit_jobs",
    "chrome-extension": "{pkg}.audit_jobs",
    "mobile-app": "app.audit_jobs",
    "file-worker": "worker.audit_jobs",
}

# The companion's memory limit, MEASURED (2026-09-24, the T05 receipt records the run):
# the emitted jobs module under ``/usr/bin/time -v`` against a scratch PostgreSQL 16
# holding a 10,000-row chain peaked at 62,012 kB RSS for the verification pass and
# 47,588 kB for retention. 128M is about twice the verification peak; ``verify_chain``
# holds its whole window in memory, so a project whose weekly window grows far past
# 10k rows raises this limit in its own spec.
AUDIT_JOBS_COMPANION_MEMORY = "128M"


def type_needs_database(project_type: str) -> bool:
    """``shape.needs_database`` of ``templates/<type>/defaults.yaml`` (False without a shape)."""
    shape = _build_shape_for_type(project_type)
    return bool(shape is not None and shape.needs_database)


def audit_jobs_companion(name: str, project_type: str) -> CompanionService | None:
    """The ``<name>-audit-jobs`` companion for a database spec of ``project_type``.

    ``None`` for a type whose backend schedules the jobs itself (the saas family) or has
    no Python backend. No ``env_overrides``: the jobs read ``DATABASE_URL_OWNER``
    themselves, from the project ``.env`` the companion loads through ``env_file`` — the
    committed compose the scaffolder writes and the companion partial both carry it,
    because ``DATABASE_URL_OWNER`` exists nowhere else (compose ``environment:`` never
    holds it).
    """
    module = AUDIT_JOBS_MODULES.get(project_type)
    if module is None:
        return None
    return CompanionService(
        id=f"{name}-audit-jobs",
        command=["python", "-m", module.format(pkg=name.replace("-", "_"))],
        memory=AUDIT_JOBS_COMPANION_MEMORY,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _is_secret(key: str) -> bool:
    """Return True if *key* matches any pattern in SECRET_PATTERNS (case-insensitive)."""
    upper = key.upper()
    return any(pattern in upper for pattern in SECRET_PATTERNS)


def _parse_compose_env(compose_path: Path) -> dict[str, str]:
    """Parse environment variables from the first service in a compose.yaml.

    Handles both list format (``["KEY=VALUE"]``) and dict format
    (``{KEY: VALUE}``).  Returns ``{}`` on any error.
    """
    try:
        with open(compose_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        if data is None:
            return {}

        services = data.get("services", {})
        if not services:
            return {}

        first_service = next(iter(services.values()))
        env_raw = first_service.get("environment")
        if env_raw is None:
            return {}

        result: dict[str, str] = {}

        if isinstance(env_raw, list):
            for item in env_raw:
                item_str = str(item)
                if "=" in item_str:
                    k, v = item_str.split("=", 1)
                    result[k.strip()] = v.strip()
                else:
                    result[item_str.strip()] = ""
        elif isinstance(env_raw, dict):
            for k, v in env_raw.items():
                result[str(k)] = str(v) if v is not None else ""

        return result
    except Exception:
        logger.debug("Failed to parse compose env from %s", compose_path, exc_info=True)
        return {}


def _load_template_defaults(project_type: str) -> dict:
    """Load ``templates/<project_type>/defaults.yaml`` as a dict.

    Returns an empty dict if the file is missing or fails to parse (both are
    non-fatal — caller treats missing data as "use all-False Shape defaults").

    Phase 4k: this replaces the Python-hardcoded ``_TYPE_DEFAULTS`` for shape
    fields. Resource / health defaults still live in ``_TYPE_DEFAULTS`` below
    (they are not yet migrated to defaults.yaml to keep this phase focused).
    """
    defaults_path = _TEMPLATES_DIR / project_type / "defaults.yaml"
    if not defaults_path.exists():
        logger.debug(
            "No defaults.yaml for project_type=%s at %s — returning empty dict",
            project_type,
            defaults_path,
        )
        return {}
    try:
        data = yaml.safe_load(defaults_path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            logger.warning(
                "defaults.yaml for %s is not a mapping (type=%s) — ignoring",
                project_type,
                type(data).__name__,
            )
            return {}
        return data
    except Exception:
        logger.warning("Failed to parse %s — returning empty dict", defaults_path, exc_info=True)
        return {}


def _build_shape_for_type(project_type: str) -> Shape | None:
    """Build a validated :class:`Shape` from ``templates/<type>/defaults.yaml``.

    Returns ``None`` if the template has no ``shape:`` block (e.g. a template
    predating Phase 4k). Returning ``None`` keeps the generated spec
    backwards-compatible — the orchestrator's ``resolve_applicability`` already
    tolerates a missing shape via ``spec.get("shape", {})``.

    Raises:
        pydantic.ValidationError: If the shape block contains an unknown key.
            This is intentional — a typo in defaults.yaml (e.g.
            ``need_database: true`` instead of ``needs_database: true``)
            MUST fail loudly at scaffold/apply time, never silently.
    """
    data = _load_template_defaults(project_type)
    shape_raw = data.get("shape")
    if shape_raw is None:
        return None
    return Shape(**shape_raw)


def _validated_shape_overlay(shape: Shape, **updates: object) -> Shape:
    """Apply field overlays to *shape*, RE-RUNNING its ``model_validator``s.

    ``shape.model_copy(update=...)`` writes fields directly and skips every
    ``model_validator(mode="after")`` — an overlay built that way could
    silently produce an invalid ``Shape`` (e.g. ``database_url_app_role=True``
    with ``needs_database=False``) that direct construction (``Shape(...)``)
    would refuse outright. Round-tripping through ``model_validate`` closes
    that gap: an overlay that would violate a cross-field invariant raises
    ``pydantic.ValidationError`` here instead of shipping a spec no directly
    constructed ``Shape`` could have produced.
    """
    return Shape.model_validate({**shape.model_dump(), **updates})


def _parse_env_example(env_example_path: Path) -> list[str]:
    """Return secret key names found in ``.env.example``.

    Lines starting with ``#`` and blank lines are skipped.  Only keys that
    match :func:`_is_secret` are returned.  Returns ``[]`` if the file does
    not exist.
    """
    if not env_example_path.exists():
        return []

    secrets: list[str] = []
    try:
        with open(env_example_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key = line.split("=", 1)[0].strip()
                if key and _is_secret(key):
                    secrets.append(key)
    except Exception:
        logger.debug("Failed to parse .env.example at %s", env_example_path, exc_info=True)
        return []

    return secrets


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def extract_project_context(project_path: Path) -> dict:
    """Extract environment, secrets, and dependency info from a scaffolded project.

    Returns a dict with keys ``env``, ``secrets``, ``depends_postgres``,
    ``depends_redis``, ``project_type``.
    """
    # Read project type from project.yaml
    project_type = None
    project_yaml_path = project_path / "project.yaml"
    if project_yaml_path.exists():
        try:
            project_yaml = yaml.safe_load(project_yaml_path.read_text())
            project_type = project_yaml.get("type")
        except Exception:
            pass  # Fall through to None

    compose_env = _parse_compose_env(project_path / "compose.yaml")
    secret_keys = _parse_env_example(project_path / ".env.example")

    env: dict[str, str] = {}
    secrets: list[str] = list(secret_keys)  # from .env.example

    for k, v in compose_env.items():
        if _is_secret(k):
            if k not in secrets:
                secrets.append(k)
        else:
            env[k] = v

    # Dependency detection — scan both keys and values (case-insensitive)
    all_text = " ".join(
        [k.lower() for k in compose_env] + [v.lower() for v in compose_env.values()]
    )

    depends_postgres = "database_url" in all_text or "postgres" in all_text
    depends_redis = "redis_url" in all_text or "redis" in all_text

    return {
        "env": env,
        "secrets": secrets,
        "depends_postgres": depends_postgres,
        "depends_redis": depends_redis,
        "project_type": project_type,
    }


_SHAPE_KIND_TO_TOP_KIND: dict[str, Kind] = {
    "service": Kind.SERVICE,
    "worker": Kind.WORKER,
    "static": Kind.STATIC,
    "wordpress": Kind.WORDPRESS,
}


def detect_git_source(project_path: Path) -> Source | None:
    """Detect a git remote on ``project_path`` and return a Source(type=git).

    B7 (historical): the legacy Coolify-API inline-compose path could only
    submit a rendered compose YAML and lacked a source tree, so compose
    templates that use ``build: context: .`` couldn't deploy through it.
    The SSH+Compose deployer (the active path) handles both — when a git
    remote is present, ``source.type=git`` triggers a ``git clone`` +
    ``docker compose build`` on the VPS; ``source.type=template`` renders
    the compose locally and ships it. Detection here picks the right shape
    so the spec round-trips cleanly across both source types.

    Returns:
        ``Source(type=GIT, repository=<remote-url>, branch=<HEAD>)`` when a
        remote is configured, otherwise ``None`` (caller falls back to the
        legacy ``template`` source — which now logs a clear warning).
    """
    try:
        url = (
            subprocess.check_output(
                ["git", "-C", str(project_path), "remote", "get-url", "origin"],
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            .decode()
            .strip()
        )
        if not url:
            return None
        try:
            branch = (
                subprocess.check_output(
                    ["git", "-C", str(project_path), "symbolic-ref", "--short", "HEAD"],
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                )
                .decode()
                .strip()
                or "main"
            )
        except subprocess.SubprocessError:
            branch = "main"
        return Source(type=SourceType.GIT, repository=url, branch=branch)
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return None


def generate_spec(
    name: str,
    project_type: str,
    domain: str | None,
    context: dict | None = None,
    use_database: bool = False,
    project_path: Path | None = None,
) -> Spec:
    """Build a :class:`Spec` for a scaffolded project.

    Args:
        name: Project name (also the compose app name == directory under ``/opt/``).
        project_type: One of :data:`SPEC_ENABLED_TYPES`.
        domain: FQDN for the deployed service (or ``None`` for workers).
        context: Extracted project context (env vars, secrets, deps).
        use_database: When ``True``, force ``shape.needs_database = True``
            in the emitted spec. This is what the ``fabrik scaffold --db``
            flag plumbs through: ``--db`` creates a local PostgreSQL DB on
            WSL **and** must trigger the postgres registrar on VPS apply.
            Pre-fix (B1) the flag was silently dropped here, so apply
            skipped the registrar even though the project was DB-backed.

    Raises:
        ValueError: If *project_type* is not in :data:`SPEC_ENABLED_TYPES`.
    """
    if project_type not in SPEC_ENABLED_TYPES:
        raise ValueError(
            f"Unsupported project type for spec generation: {project_type!r}. "
            f"Supported types: {sorted(SPEC_ENABLED_TYPES)}"
        )

    ctx = context or {}
    defaults = _TYPE_DEFAULTS[project_type]

    # Build shape from templates/<type>/defaults.yaml first — it is the
    # source of truth for kind + applicability flags. ``use_database`` then
    # overlays on top so the CLI ``--db`` flag survives spec emission.
    shape = _build_shape_for_type(project_type)
    if shape is not None and use_database:
        shape = _validated_shape_overlay(shape, needs_database=True)

    # D-390: every new database project is born on the app role — the owner
    # DSN (DATABASE_URL_OWNER) is provisioned alongside it, but DATABASE_URL
    # itself is the non-owner <db>_app role from day one. Applies whenever the
    # emitted shape ends up needs_database=True, whether that came from the
    # type's own defaults.yaml or the ``--db`` overlay above.
    if shape is not None and shape.needs_database:
        shape = _validated_shape_overlay(shape, database_url_app_role=True)

    # Acceptance-review S1: a database spec with NO shape at all would carry
    # no database_url_app_role flag (and, since D7, no depends.postgres either —
    # a database-backed project silently deployed without its database). Every enabled type carries a
    # `shape:` block today (see the "every enabled type" test in
    # test_spec_generator.py); fail loud rather than let a future template
    # regression (a missing/deleted `shape:` block) ship that silently.
    wants_database = bool(ctx.get("depends_postgres")) or use_database
    if shape is None and wants_database:
        raise ValueError(
            f"{project_type!r} would emit a database-backed spec "
            f"(use_database={use_database!r}, "
            f"depends_postgres={ctx.get('depends_postgres')!r}) but "
            f"templates/{project_type}/defaults.yaml has no `shape:` block — "
            "refusing to emit depends.postgres with no database_url_app_role "
            "flag. Add a `shape:` block to the template's defaults.yaml."
        )

    # Top-level ``kind`` MUST match ``shape.kind`` so the spec is internally
    # consistent (validators and downstream tooling key off both). Pre-fix
    # (B4) static-site / docusaurus had top-level ``kind=service`` while
    # ``shape.kind=static`` — semantically wrong even if benign at deploy.
    if shape is not None:
        kind = _SHAPE_KIND_TO_TOP_KIND.get(shape.kind, Kind.SERVICE)
    elif project_type == "file-worker":
        kind = Kind.WORKER
    else:
        kind = Kind.SERVICE

    if kind == Kind.WORKER:
        expose = Expose(http=False)
        domain = None  # workers have no domain (no Traefik route, no Gatus)
    else:
        expose = Expose()

    resources = Resources(memory=defaults["memory"], cpu=defaults["cpu"])

    health_path = defaults["health_path"]
    health = Health(path=health_path) if health_path is not None else None

    from fabrik.spec_loader import Depends

    # D7-registrar-O1/O3: the registrar reads ``depends.postgres`` as the DATABASE
    # NAME (infrastructure.py ``_provision_postgres``: ``configured or derived``), so
    # the old ``"main"`` put every new project in one shared database — where the
    # app-role cutover this spec asks for is refused forever. A database spec pins
    # the project's OWN database, the exact name the registrar derives on its own;
    # gated on the RESOLVED shape (defaults.yaml or the --db overlay), never the raw
    # flag/context. Redis stays "main": it names a server, not a database.
    depends = Depends(
        postgres=name.replace("-", "_") if (shape is not None and shape.needs_database) else None,
        redis="main" if ctx.get("depends_redis") else None,
    )

    # Secrets - avoid duplication: if from_env is provided, don't populate required
    secrets_from_env = ctx.get("secrets_from_env", [])
    secrets_policy = SecretsPolicy(
        required=ctx.get("secrets", []) if not secrets_from_env else [],
        from_env=secrets_from_env,
        from_file=ctx.get("secrets_from_file", {}),
    )

    # B7: detect git remote → emit ``source.type: git`` so the SSH+Compose
    # deployer clones the repo before building. Falls back to ``template``
    # (the pydantic default) when no remote is configured; a clear warning
    # is logged so the user knows the spec can't deploy until they push to
    # a remote.
    source: Source | None = None
    if project_path is not None:
        source = detect_git_source(project_path)
    if source is None and project_path is not None:
        logger.warning(
            "No git remote configured at %s — emitting source.type=template. "
            "If the rendered compose.yaml has a `build:` directive, the deploy "
            "will fail: `fabrik apply` (SSH + Docker Compose) only ships "
            "compose.yaml + .env to the VPS — the build context (source code) "
            "won't be present. Add a git remote so the spec becomes "
            "source.type=git and the VPS can `git clone` to build: "
            "`git -C %s remote add origin <url> && git push -u origin HEAD`",
            project_path,
            project_path,
        )

    extra: dict = {}
    if source is not None:
        extra["source"] = source
    # The audit-log jobs companion (D-390): only for a database spec whose Python backend
    # has no scheduler of its own; a spec without it keeps its companion_services empty.
    # Gated on the RESOLVED shape the spec carries (defaults.yaml or the --db overlay),
    # never the raw flag — the scaffolder emits the module under the same rule.
    has_database = shape is not None and shape.needs_database
    companion = audit_jobs_companion(name, project_type) if has_database else None
    if companion is not None:
        extra["companion_services"] = [companion]

    return create_spec(
        id=name,
        template=project_type,
        domain=domain,
        kind=kind,
        expose=expose,
        resources=resources,
        health=health,
        depends=depends,
        secrets=secrets_policy,
        env=ctx.get("env", {}),
        # Phase 4k: emit shape: from templates/<type>/defaults.yaml.
        # None is passed through when the template predates Phase 4k
        # (back-compat path — orchestrator tolerates a missing shape).
        shape=shape,
        **extra,
    )


def generate_and_save_spec(
    name: str,
    project_type: str,
    project_path: Path,
    specs_dir: Path,
    secrets_from_env: list[str] | None = None,
    secrets_from_file: dict[str, str] | None = None,
    use_database: bool = False,
) -> Path:
    """Extract project context, generate a spec, and save it.

    Returns the path to the saved spec file.

    Args:
        use_database: Forwarded to :func:`generate_spec`. ``True`` when the
            scaffolder was invoked with ``--db`` — propagates through so the
            emitted spec carries ``shape.needs_database: true`` and the
            postgres registrar fires on apply.

    Raises:
        RuntimeError: If spec generation or saving fails.
    """
    try:
        context = extract_project_context(project_path)
        # Pass secrets context for deployment-ready specs
        if secrets_from_env:
            context["secrets_from_env"] = secrets_from_env
        if secrets_from_file:
            context["secrets_from_file"] = secrets_from_file
        spec = generate_spec(
            name=name,
            project_type=project_type,
            domain=f"{name}.vps1.ocoron.com",
            context=context,
            use_database=use_database,
            project_path=project_path,
        )
        spec_path = specs_dir / f"{name}.yaml"
        save_spec(spec, spec_path)
        logger.info("Spec saved to %s", spec_path)
        return spec_path
    except Exception as exc:
        raise RuntimeError(f"Spec generation failed: {exc}") from exc
