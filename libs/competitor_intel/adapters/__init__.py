"""The opt-in source-adapter SEAM.

The core ships **Tier-C search-excerpts only** (ToS-clean, self-contained). Richer sources (Apple RSS, HN
Algolia, Trustpilot, …) are OPTIONAL lazy adapters the consumer enables with an operator key — each
tier-tagged, key-gated, and a small addition that only REGISTERS into this seam.

The seam ships with an EMPTY registry, so the reviews stage can call :func:`enabled_adapters`
unconditionally and get ``[]`` → Tier-C only. The two free exemplars (HN Algolia, Apple RSS) register via
:func:`use_free_adapters` — an EXPLICIT call, not an import side-effect (Python imports a module once per
process, so an import-time ``register()`` could not be re-run after a registry reset).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from ..dossier import Signal


@runtime_checkable
class Adapter(Protocol):
    """A concrete source adapter. ``key_env`` is the env var that gates it (absent → the adapter stays
    off). ``product_types`` are the profiles it applies to. ``fetch`` returns tier-tagged signals for one
    subject (a competitor brand); it MUST never raise — a failed fetch returns ``[]`` (the reviews stage
    also wraps it defensively)."""

    #: the module-unique adapter id, e.g. ``"hn_algolia"``.
    name: str
    #: the env var whose presence enables the adapter (``""`` = free/no-key, always enabled when listed).
    key_env: str

    async def fetch(self, subject: str, *, client: Any, config: Any) -> list[Signal]: ...


#: name -> (adapter, product_types it serves). Populated by :func:`register` (Phase C exemplars).
_REGISTRY: dict[str, tuple[Adapter, frozenset[str]]] = {}


def register(adapter: Adapter, *, product_types: frozenset[str]) -> None:
    """Register a concrete adapter into the seam. Called by :func:`use_free_adapters` (for the shipped
    exemplars) or by a consumer wiring a custom adapter. Last registration for a name wins (idempotent)."""
    _REGISTRY[adapter.name] = (adapter, product_types)


def use_free_adapters() -> None:
    """Opt in to the free, no-key exemplar adapters (HN Algolia · Apple RSS) — registers each into the seam
    EXPLICITLY (not via an import side-effect, which Python would run only once per process and which a
    registry reset couldn't re-trigger). The core never calls this, so an app that doesn't opt in keeps the
    Tier-C-only default. Key-gated (paid) adapters additionally require their env key."""
    from .apple_rss import PRODUCT_TYPES as APPLE_TYPES
    from .apple_rss import AppleRssAdapter
    from .hn_algolia import PRODUCT_TYPES as HN_TYPES
    from .hn_algolia import HnAlgoliaAdapter

    register(HnAlgoliaAdapter(), product_types=HN_TYPES)
    register(AppleRssAdapter(), product_types=APPLE_TYPES)


def _clear_registry() -> None:
    """Test-only: empty the process-global registry (it persists across a session, so a test that registers
    an adapter must reset it to avoid polluting sibling tests)."""
    _REGISTRY.clear()


def enabled_adapters(product_type: str, env: Mapping[str, str]) -> list[Adapter]:
    """The adapters active for this ``product_type`` given the operator environment. An adapter is active
    when its ``product_types`` covers ``product_type`` AND its ``key_env`` is either empty (free/no-key)
    or present + non-empty in ``env``.

    Phase A: the registry is empty → always ``[]`` (Tier-C search-excerpts only). This is the ToS-clean,
    self-contained default; the module works with zero adapters."""
    active: list[Adapter] = []
    for adapter, product_types in _REGISTRY.values():
        if product_type not in product_types:
            continue
        gate = adapter.key_env
        if gate and not (env.get(gate) or "").strip():
            continue
        active.append(adapter)
    return active
