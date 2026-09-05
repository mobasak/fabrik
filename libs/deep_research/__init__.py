"""deep-research — a generic staged evidence-research engine + injected pack.

Public surface: the engine (:func:`run_research`, :class:`ResearchDeps`, the structural Protocols) and,
once vendored with a pack, :func:`load_pack` / :class:`Pack`. The engine imports no web-tools / cost-budget
module — the search/scrape executors and the money ceiling are injected via ``ResearchDeps`` (vendorable-alone).
"""

from __future__ import annotations

from deep_research.engine import (
    LegExecutor,
    LegResult,
    LegSpec,
    LlmFn,
    Pack,
    ResearchDeps,
    Row,
    load_checkpoint,
    run_research,
)
from deep_research.pack import (
    CardField,
    LegConfig,
    PackData,
    PackError,
    load_pack,
)

__all__ = [
    "run_research",
    "ResearchDeps",
    "load_pack",
    "PackData",
    "LegConfig",
    "CardField",
    "PackError",
    "Pack",
    "Row",
    "LegResult",
    "LegExecutor",
    "LegSpec",
    "LlmFn",
    "load_checkpoint",
]
