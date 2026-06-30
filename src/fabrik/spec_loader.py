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

from fabrik.config import FABRIK_ROOT


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
    """How the application source is provided.

    LOCAL added 2026-05-14 (T1-02 G-B1a cascade-fix): pre-G1 deployed specs
    (captcha, file-api, translator, image-broker, emailgateway) declare
    ``source.type: local`` + ``source.path: /opt/<name>``. They were already
    running on the VPS pre-Fabrik-orchestrator (historically via Coolify GUI;
    today they would be deployed via SSH+Compose through ``fabrik apply``).
    LOCAL lets ``load_spec`` / ``fabrik plan`` / ``fabrik status`` /
    ``fabrik audit-registrars`` work on them; full ``fabrik apply`` plumbing
    for LOCAL is handled by the SSH+Compose deployer (Phase 11-1 migration).
    """

    TEMPLATE = "template"
    GIT = "git"
    DOCKER = "docker"
    LOCAL = "local"


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
    path: str | None = Field(default=None, description="VPS path for local source deployments")
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
    bearer_bypass_prefix: str | None = Field(
        default=None,
        pattern=r"^\^/",
        description=(
            "Authelia bypass path-regex for has_bearer_api services. Defaults to "
            "'^/api/' when unset. NARROW it (e.g. '^/api/v1') when bearer auth covers "
            "only a sub-prefix and OTHER /api/* routes are unauthenticated and must "
            "stay behind 2FA — a broad '^/api/' bypass would expose those routes "
            "publicly. Must start with '^/'."
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


class WatchdogConfig(BaseModel):
    """Per-project AI watchdog sidecar configuration (T-P2 watchdog platform).

    Lives at top-level of the spec as ``watchdog:``. Provisioned by
    :func:`fabrik.orchestrator.infrastructure._register_watchdog` at
    ``fabrik apply`` time. Defaults derived from ``spec.shape.kind`` —
    service/worker/wordpress get ``enabled=true``; static gets ``enabled=false``.
    Default-by-kind logic lives in the dispatcher (``_register_watchdog``),
    not in this Pydantic class, because Pydantic doesn't know about Shape.

    See ``docs/development/plans/2026-05-30-ai-watchdog-platform.md``
    § Watchdog architecture for the full design and
    ``docs/development/plans/2026-05-30-ai-watchdog-platform-P2-subplan.md`` § 1
    for the field-by-field design notes.
    """

    model_config = {"extra": "forbid"}

    enabled: bool = Field(
        default=False,
        description=(
            "True to inject the watchdog sidecar into the project's compose. "
            "Default is computed by the dispatcher from spec.shape.kind: True "
            "for service|worker|wordpress, False for static. Owner can override."
        ),
    )

    # Cost caps — exactly one MUST be > 0 if enabled=True (validator below).
    daily_budget_usd: float = Field(
        default=1.0,
        ge=0.0,
        description=(
            "Daily USD cap for LLM calls (Anthropic billing — Claude Code OAuth "
            "OR fallback OpenRouter API). Per-project. Resets at midnight UTC. "
            "0.0 disables USD-cap enforcement (relies on daily_invocations_cap)."
        ),
    )
    daily_invocations_cap: int = Field(
        default=200,
        ge=0,
        description=(
            "Daily invocation-count cap for LLM calls (primarily for Claude Code "
            "subscription-quota visibility; OpenRouter calls count too). Per-project. "
            "Resets at midnight UTC. 0 disables count-cap enforcement."
        ),
    )

    auto_tier_b: bool = Field(
        default=False,
        description=(
            "True to allow autonomous Tier B actions (wipe Redis cache, reset DB "
            "connection pool). Default False — Tier B requires opt-in per project. "
            "Tier A is always autonomous; Tier C always escalates regardless."
        ),
    )

    escalation_channel: str = Field(
        default="apprise",
        description=(
            "Where the sidecar sends owner alerts. v1 supports 'apprise' (sends "
            "via http://apprise:8000/notify). Future: 'telegram' (direct bot)."
        ),
    )

    # LLM provider chain.
    llm_provider_primary: Literal["claude-code", "openrouter"] = Field(
        default="claude-code",
        description=(
            "Primary LLM provider. 'claude-code' invokes the local `claude -p` "
            "subprocess inheriting host OAuth from /home/watchdog/.claude/. "
            "'openrouter' uses the HTTP API directly."
        ),
    )
    llm_provider_fallback: Literal["claude-code", "openrouter", "none"] = Field(
        default="openrouter",
        description=(
            "Fallback when the primary fails (exit non-zero, timeout, classifier "
            "abort, rate-limit). 'none' disables fallback (sidecar drops to "
            "rule-only mode on primary failure)."
        ),
    )

    # Per-tier model selection — applies to whichever provider is active.
    # NOTE: Claude Code internally routes Haiku→Opus already (verified live).
    # We expose explicit fields anyway so OpenRouter callers have the same shape.
    cheap_model: str = Field(
        default="haiku",
        description=(
            "First-pass model alias. For claude-code: 'haiku' (Claude routes). "
            "For openrouter: full id like 'google/gemini-2.5-flash' or 'anthropic/claude-haiku-4.5'."
        ),
    )
    expensive_model: str = Field(
        default="sonnet",
        description=(
            "Escalation model alias. For claude-code: 'sonnet' or 'opus'. "
            "For openrouter: full id like 'anthropic/claude-sonnet-4.6'."
        ),
    )

    # Per-incident hard ceiling. Sidecar passes this to `claude -p --max-budget-usd`.
    per_incident_budget_usd: float = Field(
        default=0.50,
        ge=0.0,
        description=(
            "Hard per-incident USD ceiling passed to `claude -p --max-budget-usd`. "
            "0.0 disables the per-incident cap (only daily caps apply). Recommended "
            "starting value: $0.50 (≈20 Haiku diagnosis calls or 1–2 Sonnet escalations)."
        ),
    )

    # ── v1 capability fields (locked 2026-06-02 during artifact 2 review) ──
    # These 3 fields were added in an artifact 1 amendment after the
    # claude-settings.json.template's v1 capability matrix was finalized.
    # See P2 sub-plan § 4.6 "v1 capability expansion" and the per-field
    # rationale below. All have backwards-compatible defaults so existing
    # specs and tests pass without modification.

    deadman_timeout_seconds: int = Field(
        default=300,
        ge=60,
        le=3600,
        description=(
            "Tier C escalation deadman timer. If a Tier C alert (code/secret/"
            "shared-infra change, restore-from-snapshot) goes unacknowledged "
            "by the operator for this many seconds, the agent (agent.py, "
            "artifact 8) restarts <main_container> as a bleed-stop and "
            "re-alerts with a [DEADMAN-TIMEOUT] prefix. Bleed-stop relies on "
            "the already-allowed `docker restart <main_container>` permission "
            "— no new sidecar privilege required. 60s minimum (avoid alert "
            "storms); 3600s maximum (operator workflow sanity). Default 300s "
            "balances bleed limits vs operator response latency."
        ),
    )

    external_docs_enabled: bool = Field(
        default=True,
        description=(
            "Runtime gate for external documentation lookups. The "
            "claude-settings.json.template always declares WebSearch + "
            "WebFetch as allowed with a 29-domain allow-list "
            "(docs.python.org, stripe.com, docs.aws.amazon.com, MDN, "
            "stackoverflow.com, etc.). This flag is the per-project runtime "
            "switch the agent honors before invoking those tools. Off => "
            "sidecar runs as if WebFetch/WebSearch were denied. Default "
            "True — doc lookups are the watchdog's most cost-effective "
            "diagnosis aid (an error-code lookup avoids many speculation "
            "calls)."
        ),
    )

    propose_fix_prs: bool = Field(
        default=False,
        description=(
            "Allow the sidecar to push proposed-fix PRs to a "
            "`watchdog/<incident_id>` branch when triaging a Tier C incident. "
            "Workspace is /var/lib/watchdog/proposed/<project_id>/; "
            "operator reviews and merges (the sidecar never merges and "
            "cannot push to main/master/develop/staging/production/release/* "
            "branches — those refs are explicit-denied in "
            "claude-settings.json.template). REQUIRES a per-project git "
            "deploy key configured at the GitHub repo with a CODEOWNERS-"
            "enforced ruleset restricting Write to `watchdog/*` refs only. "
            "Default False — opt-in per project once the operator has set "
            "up the deploy key and ruleset. Off => sidecar still detects "
            "code-fix opportunities but escalates them as a Tier C alert "
            "with a human-readable patch description instead of opening "
            "the PR."
        ),
    )

    # ── Tier-D autonomous code-fix (opt-in; canonical in 60-watchdog.md) ──
    auto_code_fix: bool = Field(
        default=False,
        description=(
            "Tier-D: allow the sidecar to autonomously APPLY a fix to production "
            "(not just propose a PR). Off by default. When true the driver renders "
            "a consumer bootstrap that wires the four orchestration planes "
            "(deploy_adapter + remediator + telegram_bot + approval_manager) and "
            "calls configure() before the agent loop; the library only enters the "
            "code-fix path when ALL four are present. Every apply is tests-gated, "
            "secret-scanned, Telegram Approve/Reject/STOP-gated with a silence-"
            "window auto-apply, auto-rolled-back on health regression, and audited. "
            "REQUIRES propose_fix_prs=true (shares the /var/lib/watchdog/proposed/"
            "<id> workspace clone) and a git source (the driver derives the clone "
            "remote from spec.source.repository — NOT a watchdog field); the driver "
            "also refuses to enable it for an app with no HEALTHCHECK (blind "
            "rollback) — degrading to escalate-only."
        ),
    )
    code_fix_window_sec: int = Field(
        default=300,
        ge=60,
        le=3600,
        description=(
            "Tier-D approval/silence window in seconds. After a fix is proposed to "
            "the operator via Telegram, this is how long the sidecar waits for an "
            "explicit Approve/Reject/STOP before the silence-window auto-applies. "
            "Passed to the bootstrap as WATCHDOG_APPROVAL_WINDOW_SEC. 60s min / "
            "3600s max. Default 300s."
        ),
    )
    critical_paths: list[str] = Field(
        default_factory=list,
        description=(
            "Substrings that drive TWO things, rendered to WATCHDOG_CRITICAL_PATHS "
            "(comma-joined) whenever set — independent of Tier-D. (1) Tier-D "
            "remediator: paths it treats as high-blast-radius (escalate rather "
            "than silence-window auto-apply). (2) error_webhook paging (Option A): "
            "an error-tracker signal pages only when its error_type (e.g. "
            "'PaymentError') or url-path (e.g. '/checkout') substring-matches one "
            "of these. So an alerting-only target (trigger_sources includes "
            "error_webhook, auto_code_fix off) MUST set this or signals are "
            "captured-but-never-paged. Empty = library defaults only."
        ),
    )

    trigger_sources: list[str] = Field(
        default_factory=list,
        description=(
            "Opt-in event-driven trigger sources for the sidecar bus, rendered to "
            "WATCHDOG_TRIGGER_SOURCES (csv). Allowed: 'emitter' (app-emitted "
            "incidents), 'health' (container health watch), 'error_webhook' "
            "(GlitchTip new-issue webhook → the sidecar's :8889 ingest server). "
            "Empty (default) leaves WATCHDOG_TRIGGER_SOURCES UNSET, so the library "
            "runs the legacy poll path with NO trigger bus (backward-compatible). "
            "Setting 'error_webhook' starts the :8889 ingest server; point a "
            "GlitchTip 'General Slack-compatible webhook' new-issue alert at "
            "http://<id>-watchdog:8889/ on the internal fabrik net (no Traefik). "
            "Optional shared-secret: set WATCHDOG_INGEST_TOKEN in the project .env."
        ),
    )

    @model_validator(mode="after")
    def _check_caps_set_when_enabled(self) -> "WatchdogConfig":
        """If enabled=true, at least one cap must be > 0.

        Defense against accidentally-uncapped projects: either USD cap > 0
        OR invocations cap > 0. Disabled watchdogs skip the check (no cost
        to cap).
        """
        if self.enabled and self.daily_budget_usd <= 0 and self.daily_invocations_cap <= 0:
            raise ValueError(
                "watchdog: enabled=true requires at least one of "
                "daily_budget_usd > 0 or daily_invocations_cap > 0"
            )
        return self

    @model_validator(mode="after")
    def _check_tier_d_prereqs(self) -> "WatchdogConfig":
        """Tier-D (auto_code_fix) shares the PR workspace clone, which only
        exists when propose_fix_prs is on (``agent.propose_fix`` returns None
        otherwise). Enforce the coupling at the spec layer so a misconfigured
        project fails ``fabrik plan`` rather than silently never remediating.
        The git-remote + app-HEALTHCHECK prerequisites are runtime/deploy
        facts checked by the driver.
        """
        if self.auto_code_fix and not self.propose_fix_prs:
            raise ValueError(
                "watchdog: auto_code_fix=true requires propose_fix_prs=true "
                "(Tier-D reuses the proposed-fix workspace clone)"
            )
        return self

    @model_validator(mode="after")
    def _check_trigger_sources(self) -> "WatchdogConfig":
        """Only the library's known bus sources are valid (fabrik-lib bus.py)."""
        allowed = {"emitter", "health", "error_webhook"}
        bad = [s for s in self.trigger_sources if s not in allowed]
        if bad:
            raise ValueError(
                f"watchdog: unknown trigger_sources {bad!r}; allowed: {sorted(allowed)}"
            )
        return self


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

    # Per-project AI watchdog sidecar configuration (T-P2 watchdog platform).
    # Consumed by ``orchestrator/infrastructure.py::_register_watchdog`` (added
    # in T-P2 artifact 12). The default-by-kind logic (enable for
    # service|worker|wordpress, disable for static) lives in the dispatcher,
    # not in the Pydantic class — see ``WatchdogConfig`` docstring.
    watchdog: WatchdogConfig = Field(
        default_factory=WatchdogConfig,
        description="Per-project AI watchdog sidecar config. See WatchdogConfig.",
    )

    # W-Multi M4 — which host in the fleet this service deploys to.
    # Maps to an ~/.ssh/config alias (vps1 / vps2 / vps3) and to a public IP
    # the DNS provisioner uses for the A record. Defaults to vps1 (hub).
    # CLI --target-vps overrides this.
    target_vps: str | None = Field(
        default=None,
        pattern=r"^vps[1-9][0-9]?$",
        description="Target host alias: vps1 (hub), vps2/vps3 (spokes). None = vps1.",
    )

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

    # G-B1a (T1-02): merge template defaults into the raw spec before
    # validation. Pre-G1 specs (captcha, file-api, translator, image-broker,
    # emailgateway) were written before scaffolds emitted explicit shape:
    # blocks; without this merge, `shape` stays None and
    # `resolve_applicability` silently skips all 9 registrars on those
    # deploys. Spec values win on conflicts (deep-merge, not shallow).
    # Missing templates/<name>/defaults.yaml is tolerated silently — the
    # raw spec is returned unchanged (no crash on typos / deleted templates).
    template_name = raw.get("template")
    if isinstance(template_name, str) and template_name:
        defaults_path = FABRIK_ROOT / "templates" / template_name / "defaults.yaml"
        if defaults_path.exists():
            with open(defaults_path, encoding="utf-8") as df:
                defaults = yaml.safe_load(df)
            if isinstance(defaults, dict):
                raw = _deep_merge(defaults, raw)

    return Spec(**raw)


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge two dicts; overlay wins on conflicts.

    Used by ``load_spec`` to inject template defaults (base) under the
    spec's own values (overlay). Nested dicts merge recursively. A
    non-dict overlay value at any key replaces the entire base value at
    that key (no type coercion). An empty overlay dict at a key whose
    base value is a non-empty dict is treated as "no change" — base wins
    by recursion.

    Pure function, no side effects. Tests in
    ``tests/test_spec_loader.py::test_deep_merge_edge_cases``.
    """
    result = dict(base)  # shallow copy; we mutate `result`, not `base`
    for key, overlay_val in overlay.items():
        base_val = result.get(key)
        if isinstance(base_val, dict) and isinstance(overlay_val, dict):
            result[key] = _deep_merge(base_val, overlay_val)
        else:
            result[key] = overlay_val
    return result


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
