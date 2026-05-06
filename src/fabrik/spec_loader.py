"""
Spec Loader - Parse and validate Fabrik deployment spec files.

This module is the single source of truth for spec file schema.
All spec files are validated against Pydantic models before use.
"""

from enum import Enum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class Kind(str, Enum):
    """Type of deployment.

    Widened 2026-04-19 (Phase 4k): ``STATIC`` + ``WORDPRESS`` added so the
    `shape:` block can carry the project-type signal through to the
    applicability dispatcher in :mod:`fabrik.orchestrator.infrastructure`.
    Prior to this, the orchestrator hard-coded the string ``"wordpress"``
    in its glitchtip rule (`infrastructure.py:184`) with no enum backing
    it — a latent bug waiting for the first real wordpress deploy.
    """

    SERVICE = "service"
    WORKER = "worker"
    STATIC = "static"
    WORDPRESS = "wordpress"


class SourceType(str, Enum):
    """How the application source is provided."""

    TEMPLATE = "template"
    GIT = "git"
    DOCKER = "docker"


class DNSProvider(str, Enum):
    """Supported DNS providers."""

    NAMECHEAP = "namecheap"
    CLOUDFLARE = "cloudflare"


class DatabaseType(str, Enum):
    """Database backend options."""

    LOCAL = "local"  # postgres-main on VPS
    SUPABASE = "supabase"  # Supabase Postgres (Phase 1b)


class StorageType(str, Enum):
    """File storage backend options."""

    LOCAL = "local"  # VPS disk
    R2 = "r2"  # Cloudflare R2 (Phase 1b)


class AuthType(str, Enum):
    """Authentication backend options."""

    NONE = "none"
    SUPABASE = "supabase"  # Supabase Auth (Phase 1b)


# --- Sub-models ---


class DNSRecord(BaseModel):
    """Individual DNS record configuration."""

    type: str = Field(..., description="Record type: A, CNAME, TXT, MX")
    name: str = Field(..., description="@ for root or subdomain name")
    content: str = Field(..., description="IP address or target")
    ttl: int = Field(default=1800, ge=60, le=86400)
    priority: int | None = Field(default=None, description="For MX records")


class DNSConfig(BaseModel):
    """DNS configuration for the service."""

    provider: DNSProvider = DNSProvider.NAMECHEAP
    records: list[DNSRecord] = Field(default_factory=list)


class Source(BaseModel):
    """Application source configuration."""

    type: SourceType = SourceType.TEMPLATE
    repository: str | None = Field(default=None, description="Git repo URL")
    branch: str = "main"
    image: str | None = Field(default=None, description="Docker image")
    image_port: int | None = Field(default=None, description="Container port for image deployments")
    image_command: str | None = Field(
        default=None, description="Override container command for image deployments"
    )


class Expose(BaseModel):
    """Service exposure configuration."""

    http: bool = True
    internal_only: bool = False


class Resources(BaseModel):
    """Resource limits for the container."""

    memory: str = "256M"
    cpu: str = "0.5"


class Health(BaseModel):
    """Health check configuration."""

    path: str = "/health"
    interval: str = "30s"
    timeout: str = "10s"
    retries: int = 3
    disabled: bool = False
    """When true, no HEALTHCHECK is emitted. Use only for images that lack
    shell tooling (e.g. ``traefik/whoami``) where any healthcheck would
    always fail and Traefik v3 would then filter the container out."""
    test: list[str] | None = None
    """Custom HEALTHCHECK test command (docker-compose ``test`` form).
    Overrides the default wget/curl probe when set."""


class Volume(BaseModel):
    """Persistent volume configuration."""

    name: str
    path: str = Field(..., description="Mount path inside container")
    backup: bool = False


class Backup(BaseModel):
    """Backup configuration."""

    enabled: bool = True
    frequency: str = "daily"
    retention: int = 30


class SecretsPolicy(BaseModel):
    """Secrets management policy."""

    required: list[str] = Field(
        default_factory=list, description="Required secret names (must pass via -s)"
    )
    generate: list[str] = Field(default_factory=list, description="Auto-generate these secrets")
    from_env: list[str] = Field(
        default_factory=list, description="Pull from local environment automatically"
    )
    from_file: dict[str, str] = Field(
        default_factory=dict, description="Read from file: {ENV_VAR: file_path}"
    )


class CoolifyConfig(BaseModel):
    """Coolify deployment configuration."""

    project: str = "default"
    server: str = "localhost"
    compose_path: str | None = None
    # Per-service Coolify SSH deploy-key override. Resolution precedence
    # is spec → ``COOLIFY_PRIVATE_KEY_UUID`` env var → auto-discovery.
    # Required for SSH-URL git repos (``git@...``); ignored otherwise.
    # See ``orchestrator/deployer.py::_resolve_private_key_uuid``.
    private_key_uuid: str | None = None


class Depends(BaseModel):
    """Service dependencies."""

    postgres: str | None = Field(default=None, description="Postgres database name")
    redis: str | None = Field(default=None, description="Redis instance name")


class Infrastructure(BaseModel):
    """Infrastructure backend configuration (Phase 1b extensibility)."""

    database: DatabaseType = DatabaseType.LOCAL
    storage: StorageType = StorageType.LOCAL
    auth: AuthType = AuthType.NONE


class Shape(BaseModel):
    """Project-shape descriptor consumed by the infrastructure dispatcher.

    Purpose
    -------
    ``shape:`` declares what the project IS — orthogonal properties that
    determine which infrastructure registrars (postgres, gatus, backrest,
    glitchtip, grafana, authelia, meilisearch) are applicable. The
    applicability matrix lives in :mod:`fabrik.orchestrator.infrastructure`;
    ``shape:`` is the authoritative source it reads.

    Invariants
    ----------
    * ``extra="forbid"``: unknown keys are a hard error. New applicability
      axes MUST be added here AND in the dispatcher in the same commit so
      the two never drift.
    * Every field defaults to ``False`` (except ``kind``, which defaults
      to ``SERVICE``). The absence of a shape block therefore resolves
      to "a plain HTTP service with no database, no storage, no admin
      auth, no search" — which matches the historical scaffold default.

    `infra:` relationship
    ---------------------
    ``shape:`` is the positive signal (what applies). ``infra:`` is the
    negative override (what to force-skip). The only valid ``infra:``
    entry is ``<registrar>: false``. See
    :func:`fabrik.orchestrator.infrastructure.resolve_applicability`.

    Matrix (Phase 4k, locked 2026-04-19):

    ==================  =======  ==========  ====================  ================  ===================  ================  ====================
     Template            kind     is_public   is_admin_dashboard    has_bearer_api    has_persistent_data   needs_database    has_search_feature
    ==================  =======  ==========  ====================  ================  ===================  ================  ====================
     python-api          service  true        false                 false             false                false             false
     node-api            service  true        false                 false             false                false             false
     saas-skeleton       service  true        false                 false             true                 true              false
     static-site         static   true        false                 false             false                false             false
     docusaurus          static   true        false                 false             false                false             false
     wordpress           wordpress true       false                 false             true                 true              false
     file-worker         worker   false       false                 false             true                 false             false
     file-api            service  true        false                 false             true                 false             false
     chrome-extension    static   false       false                 false             false                false             false
     mobile-app          static   false       false                 false             false                false             false
     desktop-app         static   false       false                 false             false                false             false
    ==================  =======  ==========  ====================  ================  ===================  ================  ====================

    The last three (chrome-extension / mobile-app / desktop-app) are
    packaged artefacts (CRX, app-store binary, installer) rather than
    VPS deployments — every flag is ``false`` because no VPS registrar
    applies. They get a ``shape:`` block anyway for schema uniformity,
    so downstream tooling can assume it's always present.
    """

    model_config = {"extra": "forbid"}

    kind: Kind = Field(
        default=Kind.SERVICE,
        description=(
            "Deployment class. Gates glitchtip (service/worker/wordpress) "
            "and drives the default expose/domain logic."
        ),
    )
    is_public: bool = Field(
        default=False,
        description=(
            "True if the service is reachable from the public internet via "
            "Traefik. Combined with spec.domain, gates Gatus uptime monitoring."
        ),
    )
    is_admin_dashboard: bool = Field(
        default=False,
        description=(
            "True if the service hosts an admin UI that must sit behind "
            "Authelia 2FA forward-auth. When combined with has_bearer_api=true, "
            "the dispatcher installs the ^/api/ bypass rule first (CSF §10)."
        ),
    )
    has_bearer_api: bool = Field(
        default=False,
        description=(
            "True if the service exposes a machine-to-machine API path "
            "(typically ^/api/) that MUST bypass Authelia to keep X-Internal-Token "
            "authentication flows intact."
        ),
    )
    has_persistent_data: bool = Field(
        default=False,
        description=(
            "True if the service writes state to disk that must survive container "
            "restarts. Gates Backrest → B2 backup plan creation."
        ),
    )
    needs_database: bool = Field(
        default=False,
        description=(
            "True if the service requires a PostgreSQL database on postgres-main. "
            "Gates the postgres registrar (creates DB + DATABASE_URL secret)."
        ),
    )
    has_search_feature: bool = Field(
        default=False,
        description=(
            "True if the service uses MeiliSearch for full-text/vector search. "
            "Gates creation of a project-scoped index."
        ),
    )
    needs_cache: bool = Field(
        default=False,
        description=(
            "True if the service needs an isolated Redis logical-DB on the shared "
            "redis-main container. Gates the redis registrar (assigns a unique DB "
            "index 1..15 and injects REDIS_URL=redis://redis-main:6379/<n>). "
            "See drivers/redis.py — DEPLOYMENT.md §9.9 G4."
        ),
    )
    exposes_metrics: bool = Field(
        default=False,
        description=(
            "True if the service exposes a Prometheus-format /metrics endpoint. "
            "Gates the prometheus registrar (appends a scrape job to the shared "
            "prometheus.yml and hot-reloads). See drivers/prometheus.py — "
            "DEPLOYMENT.md §9.9 G5."
        ),
    )


class WordPressPlugin(BaseModel):
    """WordPress plugin configuration."""

    slug: str
    activate: bool = True
    source: Literal["wp_repo", "zip"] = "wp_repo"
    zip_url: str | None = None


class WordPressConfig(BaseModel):
    """WordPress-specific configuration."""

    plugins: list[WordPressPlugin] = Field(default_factory=list)
    disable_xmlrpc: bool = True
    disable_file_edit: bool = True


# --- Main Spec Model ---


class Spec(BaseModel):
    """
    Fabrik deployment specification.

    This is the main model that represents a complete deployment spec.
    All spec YAML files are validated against this schema.
    """

    id: str = Field(
        ..., min_length=1, max_length=63, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$"
    )
    name: str | None = None  # Alias for id, set by validator if missing
    kind: Kind = Kind.SERVICE
    template: str = Field(..., min_length=1)
    domain: str | None = None

    # Shape: project-shape descriptor consumed by the infrastructure
    # dispatcher (`orchestrator/infrastructure.py::resolve_applicability`).
    # Optional for backwards compatibility with pre-Phase-4k specs that
    # relied on the top-level `kind:` field alone. When present, shape is
    # authoritative — shape.kind overrides the top-level kind at dispatch
    # time. Phase 4k scaffold emits both, kept in sync.
    shape: Shape | None = None

    expose: Expose = Field(default_factory=Expose)
    source: Source = Field(default_factory=Source)
    coolify: CoolifyConfig = Field(default_factory=CoolifyConfig)
    depends: Depends = Field(default_factory=Depends)
    infrastructure: Infrastructure = Field(default_factory=Infrastructure)

    # `infra:` override block consumed by `orchestrator/infrastructure.py::
    # resolve_applicability`. It is a negative override — ONLY valid entries
    # are ``<registrar>: false`` to force-skip a registrar that `shape:`
    # would otherwise activate.
    #
    # History (2026-05-04): originally this was intentionally NOT a pydantic
    # field — consumers were expected to read the raw YAML via
    # `orchestrator/validator.py::load_spec`. That worked for the apply path
    # but silently broke `orchestrator/destroyer.py::_spec_to_dict` (which
    # calls `spec.model_dump()`), dropping the override and causing the
    # postgres registrar to run for services with `infra.postgres: false`
    # set. We made it a proper optional field; `exclude_none=True` in
    # `dump_spec` ensures scaffolded specs still emit no `infra:` block,
    # preserving the Phase-4k acceptance criterion.
    infra: dict[str, bool] | None = None

    env: dict[str, str] = Field(default_factory=dict)
    secrets: SecretsPolicy = Field(default_factory=SecretsPolicy)

    resources: Resources = Field(default_factory=Resources)
    health: Health | None = None
    volumes: list[Volume] = Field(default_factory=list)

    dns: DNSConfig | None = None
    backup: Backup = Field(default_factory=Backup)

    wordpress: WordPressConfig | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Ensure ID is DNS-safe."""
        if v.startswith("-") or v.endswith("-"):
            raise ValueError("id cannot start or end with hyphen")
        if "--" in v:
            raise ValueError("id cannot contain consecutive hyphens")
        return v.lower()

    @model_validator(mode="after")
    def validate_domain_for_http(self):
        """HTTP services require a domain."""
        if self.kind == Kind.SERVICE and self.expose.http and not self.domain:
            raise ValueError("domain is required for HTTP services")
        return self

    @model_validator(mode="after")
    def validate_source_config(self):
        """Validate source configuration based on type."""
        if self.source.type == SourceType.GIT and not self.source.repository:
            raise ValueError("repository is required for git source type")
        if self.source.type == SourceType.DOCKER and not self.source.image:
            raise ValueError("image is required for docker source type")
        return self


# --- Public Functions ---


def load_spec(spec_path: str | Path) -> Spec:
    """
    Load and validate a spec file.

    Args:
        spec_path: Path to the YAML spec file

    Returns:
        Validated Spec object

    Raises:
        FileNotFoundError: If spec file doesn't exist
        ValueError: If spec validation fails
        yaml.YAMLError: If YAML parsing fails
    """
    path = Path(spec_path)

    if not path.exists():
        raise FileNotFoundError(f"Spec not found: {spec_path}")

    if path.suffix not in (".yaml", ".yml"):
        raise ValueError(f"Spec file must be .yaml or .yml: {spec_path}")

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ValueError(f"Spec file is empty: {spec_path}")

    if not isinstance(raw, dict):
        raise ValueError(f"Spec file must be a YAML mapping: {spec_path}")

    return Spec(**raw)


def save_spec(spec: Spec, spec_path: str | Path) -> None:
    """
    Save a spec to file.

    Args:
        spec: Spec object to save
        spec_path: Path to save to
    """
    path = Path(spec_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict, excluding None values for cleaner YAML
    data = spec.model_dump(exclude_none=True, mode="json")

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def create_spec(
    id: str, template: str, domain: str | None = None, kind: Kind = Kind.SERVICE, **kwargs
) -> Spec:
    """
    Create a new spec with minimal required fields.

    Args:
        id: Unique identifier for the deployment
        template: Template name (e.g., 'python-api', 'node-api')
        domain: Domain for HTTP services
        kind: Service type (service or worker)
        **kwargs: Additional spec fields

    Returns:
        New Spec object
    """
    return Spec(id=id, kind=kind, template=template, domain=domain, **kwargs)
