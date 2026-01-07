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

    # Deployment results
    coolify_uuid: str | None = None
    dns_record_id: str | None = None
    deployed_url: str | None = None

    # Error tracking
    error: str | None = None
    error_step: str | None = None

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
