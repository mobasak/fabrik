"""
Spec Loader - Parse and validate Fabrik deployment spec files.

This module is the single source of truth for spec file schema.
All spec files are validated against Pydantic models before use.
"""

from pathlib import Path
from typing import Optional, Literal
from enum import Enum

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class Kind(str, Enum):
    """Type of deployment."""
    SERVICE = "service"
    WORKER = "worker"


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
    LOCAL = "local"      # postgres-main on VPS
    SUPABASE = "supabase"  # Supabase Postgres (Phase 1b)


class StorageType(str, Enum):
    """File storage backend options."""
    LOCAL = "local"  # VPS disk
    R2 = "r2"        # Cloudflare R2 (Phase 1b)


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
    priority: Optional[int] = Field(default=None, description="For MX records")


class DNSConfig(BaseModel):
    """DNS configuration for the service."""
    provider: DNSProvider = DNSProvider.NAMECHEAP
    records: list[DNSRecord] = Field(default_factory=list)


class Source(BaseModel):
    """Application source configuration."""
    type: SourceType = SourceType.TEMPLATE
    repository: Optional[str] = Field(default=None, description="Git repo URL")
    branch: str = "main"
    image: Optional[str] = Field(default=None, description="Docker image")


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
    required: list[str] = Field(default_factory=list, description="Required secret names")
    generate: list[str] = Field(default_factory=list, description="Auto-generate these secrets")


class CoolifyConfig(BaseModel):
    """Coolify deployment configuration."""
    project: str = "default"
    server: str = "localhost"
    compose_path: Optional[str] = None


class Depends(BaseModel):
    """Service dependencies."""
    postgres: Optional[str] = Field(default=None, description="Postgres database name")
    redis: Optional[str] = Field(default=None, description="Redis instance name")


class Infrastructure(BaseModel):
    """Infrastructure backend configuration (Phase 1b extensibility)."""
    database: DatabaseType = DatabaseType.LOCAL
    storage: StorageType = StorageType.LOCAL
    auth: AuthType = AuthType.NONE


class WordPressPlugin(BaseModel):
    """WordPress plugin configuration."""
    slug: str
    activate: bool = True
    source: Literal["wp_repo", "zip"] = "wp_repo"
    zip_url: Optional[str] = None


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
    id: str = Field(..., min_length=1, max_length=63, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")
    kind: Kind = Kind.SERVICE
    template: str = Field(..., min_length=1)
    domain: Optional[str] = None
    
    expose: Expose = Field(default_factory=Expose)
    source: Source = Field(default_factory=Source)
    coolify: CoolifyConfig = Field(default_factory=CoolifyConfig)
    depends: Depends = Field(default_factory=Depends)
    infrastructure: Infrastructure = Field(default_factory=Infrastructure)
    
    env: dict[str, str] = Field(default_factory=dict)
    secrets: SecretsPolicy = Field(default_factory=SecretsPolicy)
    
    resources: Resources = Field(default_factory=Resources)
    health: Optional[Health] = None
    volumes: list[Volume] = Field(default_factory=list)
    
    dns: Optional[DNSConfig] = None
    backup: Backup = Field(default_factory=Backup)
    
    wordpress: Optional[WordPressConfig] = None

    @field_validator('id')
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Ensure ID is DNS-safe."""
        if v.startswith('-') or v.endswith('-'):
            raise ValueError('id cannot start or end with hyphen')
        if '--' in v:
            raise ValueError('id cannot contain consecutive hyphens')
        return v.lower()

    @model_validator(mode='after')
    def validate_domain_for_http(self):
        """HTTP services require a domain."""
        if self.kind == Kind.SERVICE and self.expose.http and not self.domain:
            raise ValueError('domain is required for HTTP services')
        return self

    @model_validator(mode='after')
    def validate_source_config(self):
        """Validate source configuration based on type."""
        if self.source.type == SourceType.GIT and not self.source.repository:
            raise ValueError('repository is required for git source type')
        if self.source.type == SourceType.DOCKER and not self.source.image:
            raise ValueError('image is required for docker source type')
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
    
    if not path.suffix in ('.yaml', '.yml'):
        raise ValueError(f"Spec file must be .yaml or .yml: {spec_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
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
    data = spec.model_dump(exclude_none=True, exclude_defaults=True)
    
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def create_spec(
    id: str,
    template: str,
    domain: Optional[str] = None,
    kind: Kind = Kind.SERVICE,
    **kwargs
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
    return Spec(
        id=id,
        kind=kind,
        template=template,
        domain=domain,
        **kwargs
    )
