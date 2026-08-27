"""competitor-intel — a headless, vendorable competitor finder + "match-then-beat" engine.

Drives the injected ``deep-research`` engine across stages (discover -> mine reviews -> [Phase B:
extract -> align -> matrix -> gap synthesis + optional price-wedge / white-space]) under ONE money
ceiling, a never-raise boundary, and an orchestrator checkpoint, then owns the novel synthesis tail.

Vendored, not imported: wire deep-research / web-tools / an LLM in via :class:`Deps`; nothing here imports
``deep_research``. See the module ``README.md`` for the Vendoring Contract.

Public API (Phase A):
    run(us, market, *, product_type, deps, enable_pricing=False, enable_white_space=False) -> Dossier
    Deps, Us, Dossier, Signal — the injected bundle, the input product, and the output shapes.
    ResearchFn, PackLoader, SynthLlm, Pack — the structural Protocols the consumer wires.
"""

from __future__ import annotations

from .dossier import Dossier, Signal, Tier, Us
from .orchestrator import run
from .protocols import Deps, Pack, PackLoader, ResearchFn, SynthLlm
from .stages import PricingBlock, PricingModel, UnmetNeed, WhiteSpaceBlock
from .synth import (
    CELL_KEY_SEP,
    BeatItem,
    Feature,
    FeatureSet,
    MatchItem,
    Matrix,
    MatrixCell,
    cell_key,
)

__all__ = [
    "run",
    "Deps",
    "Us",
    "Dossier",
    "Signal",
    "Tier",
    "ResearchFn",
    "PackLoader",
    "SynthLlm",
    "Pack",
    # Phase B synthesis result shapes (so consumers can type the Dossier fields)
    "Feature",
    "FeatureSet",
    "Matrix",
    "MatrixCell",
    # the flat `to_dict()` cell-key contract (guessing the separator fails SILENTLY — see README)
    "CELL_KEY_SEP",
    "cell_key",
    "MatchItem",
    "BeatItem",
    "PricingModel",
    "PricingBlock",
    "UnmetNeed",
    "WhiteSpaceBlock",
]
