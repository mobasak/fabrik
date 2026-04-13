"""Content pipeline orchestrator — canonical module for this epic.

Imports the implementation from fabrik.orchestrator.content_publisher and
re-exports it under the canonical path ``fabrik.content.orchestrator``.

All new code and tests MUST import from this module, not from the legacy path.
"""

from fabrik.orchestrator.content_publisher import (  # noqa: F401
    ContentPublisher,
    PublishContext,
    PublishResult,
    PublishSummary,
)

__all__ = [
    "ContentPublisher",
    "PublishContext",
    "PublishResult",
    "PublishSummary",
]
