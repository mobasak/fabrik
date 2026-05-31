"""Deployment context - shared state across orchestrator components."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from fabrik.orchestrator.states import DeploymentState


@dataclass
class ResourceRecord:
    """Track a created resource for potential rollback."""

    resource_type: str  # "dns", "coolify", "monitor"
    resource_id: str
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentContext:
    """Shared context for a deployment run."""

    spec_path: Path
    spec: dict[str, Any] = field(default_factory=dict)
    spec_hash: str = ""

    state: DeploymentState = DeploymentState.PENDING
    dry_run: bool = False

    # Secrets loaded from env/.env/generated
    secrets: dict[str, str] = field(default_factory=dict)

    # Resources created (for rollback)
    created_resources: list[ResourceRecord] = field(default_factory=list)

    # Deployment results — holds the compose app name (== directory name
    # under /opt/) for SSH-deployed services. Field is named ``coolify_uuid``
    # only for state-file backward compatibility (older ``.fabrik/state/*.json``
    # files use this key); new code should use ``ctx.app_name`` (alias below).
    coolify_uuid: str | None = None
    dns_record_id: str | None = None
    deployed_url: str | None = None

    # Target host in the fleet (hub or spoke). Maps to an ~/.ssh/config alias
    # that the SSHDeployer uses to route deploy commands. The hub-side
    # registrars (postgres, redis, gatus, glitchtip, authelia, etc.) keep
    # running against vps1 regardless of target_vps — they live there.
    target_vps: str = "vps1"

    # Error tracking
    error: str | None = None
    error_step: str | None = None

    @property
    def app_name(self) -> str | None:
        """Preferred name for what's stored in :attr:`coolify_uuid`.

        For SSH+Compose deploys this is the compose app name (== directory
        name under ``/opt/``). The underlying field is named ``coolify_uuid``
        for state-file backward compat; new call sites should use this
        property.
        """
        return self.coolify_uuid

    @app_name.setter
    def app_name(self, value: str | None) -> None:
        self.coolify_uuid = value

    def add_resource(self, resource_type: str, resource_id: str, **metadata: Any) -> None:
        """Record a created resource."""
        self.created_resources.append(
            ResourceRecord(
                resource_type=resource_type,
                resource_id=resource_id,
                metadata=metadata,
            )
        )

    def get_resources_by_type(self, resource_type: str) -> list[ResourceRecord]:
        """Get all resources of a specific type."""
        return [r for r in self.created_resources if r.resource_type == resource_type]
