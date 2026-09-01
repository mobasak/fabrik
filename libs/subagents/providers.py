"""Provider registry — the `(base_url, key_env)` seam for multi-provider dispatch.

The transport (`_client.py`/`_transport.py`) speaks the OpenAI-compatible chat protocol;
the ONLY per-provider differences are the endpoint, the API-key env var, and whether the
outgoing body may carry OpenRouter's `provider` routing object. Those three facts are DATA
(a registry row), not code — a new OpenAI-compatible provider is one dict entry here.

Backward-compat contract: `"openrouter"` is the default everywhere; an unset provider
resolves to this row and behaves EXACTLY as before the seam existed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

__all__ = ["ProviderConfig", "UnknownProviderError", "resolve_provider", "known_providers"]


class UnknownProviderError(ValueError):
    """Raised when a spec names a provider not in the registry — fail LOUD (never a
    silent fall-through to OpenRouter, which would misroute the request + the key)."""


@dataclass(frozen=True)
class ProviderConfig:
    """One provider's dispatch facts.

    * ``base_url`` — the OpenAI-compatible ``/v1`` endpoint.
    * ``key_env`` — the env var holding this provider's API key (read via ``os.getenv``;
      never a hardcoded default).
    * ``sends_or_provider_object`` — whether the outgoing request body may carry
      OpenRouter's ``provider`` routing object (max-price / latency / ignore hints).
      ``False`` for any non-OpenRouter endpoint: an unknown ``provider`` key there is at
      best ignored and at worst a 400. Gating the body injectors on this flag (rather than
      a ``== "openrouter"`` string) keeps the registry the single source of truth.
    * ``sends_or_attribution_headers`` — whether ``HTTP-Referer``/``X-Title`` (OpenRouter
      attribution headers) are set on the client. OR-only; harmless-but-pointless elsewhere.
    * ``blind_rate_backoff`` — whether the loop must apply its OWN blind exponential backoff
      on HTTP 429. OpenRouter reroutes around a congested provider (health-aware routing) and
      is left UNCHANGED; a free-tier endpoint like NVIDIA hard-429s with no ``Retry-After`` and
      no rerouting, so the loop owns the retry. ``restart_max=0`` (set by the loop) disables the
      transport's own retry, so this backoff is net-new.
    * ``max_concurrency`` — a per-provider in-flight cap (``None`` = no sub-cap, bounded only by
      the global ``max_concurrency``). NVIDIA's free tier 429s above ~a dozen concurrent, so a
      mixed fan-out must cap NVIDIA below OR — a single global semaphore cannot. Overridable via
      ``SUBAGENT_<PROVIDER>_MAX_CONCURRENCY``.
    """

    name: str
    base_url: str
    key_env: str
    sends_or_provider_object: bool
    sends_or_attribution_headers: bool
    blind_rate_backoff: bool = False
    max_concurrency: int | None = None
    # An endpoint that bills $0 for ALL runs — including a hung/timed-out one (a free endpoint
    # charges nothing regardless of outcome). So a run with UNKNOWN cost (no in-stream cost, or a
    # backstop-timeout that honestly reported cost=None) is ledgered as the KNOWN $0, not a guess —
    # the flywheel counts it as a real zero-cost run. Set True ONLY for an always-free endpoint;
    # a metered/paid mode must leave this False so an unknown cost stays "unknown", never a fake $0.
    free_tier: bool = False
    #: Name of the env var holding this provider's JOINT monthly USD ceiling — a NAME, never a
    #: value, the same discipline as ``key_env``. ``None`` (both shipped rows) means uncapped, and
    #: an uncapped provider's dispatch path is byte-identical to before this field existed: no
    #: Postgres connection is opened and nothing is reserved.
    #:
    #: The cap is joint because it is keyed by PROVIDER, not by key: four Mistral keys under
    #: ``MISTRAL_MONTHLY_CAP_USD=10`` share ten dollars, they do not get ten each.
    #:
    #: ⚠️ APPENDED LAST, WITH A DEFAULT, DELIBERATELY. ``ProviderConfig`` is frozen and ships to
    #: ~46 vendored copies; a consumer constructing it POSITIONALLY would break if this landed
    #: anywhere but the end. In this repo all 3 construction sites are safe (2 keyword registry
    #: rows + one 5-positional-arg test) — but the vendored copies cannot be counted from here, so
    #: "3 of 3 checked" is the honest denominator, not "no consumer breaks".
    monthly_cap_env: str | None = None
    #: Whether this provider's key is OPTIONAL — i.e. the endpoint serves anonymous requests.
    #: ``False`` (every row but Kilo) keeps today's fail-loud behavior: a missing key raises at
    #: :func:`_transport._resolve_client` rather than sending an unauthenticated request.
    #:
    #: OPTIONAL IS NOT IGNORED. When the key IS set it is still used — Kilo's anonymous mode only
    #: covers its `:free` models, so a consumer who provisions a key gets the authenticated tier.
    #:
    #: ⚠️ APPENDED LAST, WITH A DEFAULT — the same discipline as ``monthly_cap_env`` above and for
    #: the same reason. Re-derived at review time: this repo has FOUR ``ProviderConfig(`` call sites
    #: (2 keyword registry rows below + ``tests/test_agent.py`` and ``tests/test_spend_cap_wiring.py``,
    #: BOTH of which pass exactly 5 positional args), so a 9th field with a default breaks none of
    #: them. The ~46 vendored copies cannot be counted from here — "4 of 4 in-repo checked" is the
    #: honest denominator, never "no consumer breaks". A consumer constructing this with 9+
    #: positional args is the shape that would break.
    key_optional: bool = False


# MappingProxyType so a caller reaching `providers._REGISTRY` cannot mutate the shared
# registry and corrupt dispatch for concurrently-running units (rows are already frozen).
_REGISTRY: Mapping[str, ProviderConfig] = MappingProxyType(
    {
        "openrouter": ProviderConfig(
            name="openrouter",
            base_url="https://openrouter.ai/api/v1",
            key_env="OPENROUTER_API_KEY",
            sends_or_provider_object=True,
            sends_or_attribution_headers=True,
        ),
        "nvidia": ProviderConfig(
            name="nvidia",
            base_url="https://integrate.api.nvidia.com/v1",
            key_env="NVIDIA_API_KEY",
            sends_or_provider_object=False,
            sends_or_attribution_headers=False,
            blind_rate_backoff=True,  # free tier hard-429s, no Retry-After, no rerouting
            max_concurrency=8,  # empirically ~16 trips 429s; 8 is safe headroom
            free_tier=True,  # $0 free endpoint — unknown cost ledgered as $0
        ),
        # ── free lanes ───────────────────────────────────────────────────────────────────────
        # Endpoints + limits grounded 2026-08-30 against vendor docs (see the design spec
        # `docs/superpowers/specs/2026-08-30-free-lane-llm-engine-design.md` § External
        # dependencies for the fetched URLs). The free-model roster ROTS within weeks: a provider
        # that goes paid or dies is dropped by deleting its row — data, not code.
        #
        # ⚠️ ALL FIVE SHARE THREE FLAGS — do not vary them per row.
        #   * `free_tier=True`          — every one bills $0, so an UNKNOWN cost is ledgered as the
        #                                 KNOWN $0 rather than a guess (see the field docs above).
        #                                 A row missing this silently records "cost unknown" on a
        #                                 free call and poisons the flywheel's cost column.
        #   * `blind_rate_backoff=True` — each is a DIRECT free endpoint that hard-429s with no
        #                                 Retry-After and no rerouting, which is exactly the
        #                                 condition this flag exists for.
        #   * `sends_or_*=False`        — non-OpenRouter endpoints: an unknown `provider` object is
        #                                 ignored at best and a 400 at worst.
        # `max_concurrency` is each vendor's published free ceiling, floored to a safe integer;
        # `lane_chain` and the fan-out both hold a per-provider semaphore sized from it.
        "mistral": ProviderConfig(  # last-verified: 2026-08-30
            name="mistral",
            base_url="https://api.mistral.ai/v1",
            key_env="MISTRAL_API_KEY",
            sends_or_provider_object=False,
            sends_or_attribution_headers=False,
            blind_rate_backoff=True,
            max_concurrency=1,  # free tier is 1 req/s — anything above 1 in flight self-429s
            free_tier=True,
        ),
        "kilo": ProviderConfig(  # last-verified: 2026-08-30 (docs; anonymous mode not exercised)
            name="kilo",
            base_url="https://api.kilo.ai/api/gateway",
            key_env="KILO_API_KEY",
            sends_or_provider_object=False,
            sends_or_attribution_headers=False,
            blind_rate_backoff=True,
            max_concurrency=4,  # 200 req/hr/IP — the hourly bucket, not a concurrency limit
            free_tier=True,
            # The ONLY anonymous row: Kilo serves `:free` models with no key at all. A provisioned
            # key is still sent (optional ≠ ignored) and unlocks its authenticated tier.
            key_optional=True,
        ),
        "groq": ProviderConfig(  # last-verified: 2026-08-30
            name="groq",
            base_url="https://api.groq.com/openai/v1",
            key_env="GROQ_API_KEY",
            sends_or_provider_object=False,
            sends_or_attribution_headers=False,
            blind_rate_backoff=True,
            max_concurrency=4,  # ~30 RPM on the free tier
            free_tier=True,
        ),
        "cerebras": ProviderConfig(  # last-verified: 2026-08-30
            name="cerebras",
            base_url="https://api.cerebras.ai/v1",
            key_env="CEREBRAS_API_KEY",
            sends_or_provider_object=False,
            sends_or_attribution_headers=False,
            blind_rate_backoff=True,
            max_concurrency=1,  # free trial is 5 RPM — the tightest ceiling in the registry
            free_tier=True,
        ),
        "gemini": ProviderConfig(  # last-verified: 2026-08-30
            name="gemini",
            # Google AI Studio's OpenAI-compatibility shim. The trailing slash is part of the
            # documented base path; the client rstrips it, so `/chat/completions` still resolves.
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            key_env="GEMINI_API_KEY",
            sends_or_provider_object=False,
            sends_or_attribution_headers=False,
            blind_rate_backoff=True,
            max_concurrency=2,  # Flash-Lite ~15 RPM; volatile — billing kills the free tier
            free_tier=True,
        ),
        # NOTE: no `github` row. GitHub Models RETIRED 2026-07-30 — a row for it would be a dead
        # lane that costs a real call to discover.
    }
)


def resolve_provider(name: str) -> ProviderConfig:
    """Look up a provider row, or raise :class:`UnknownProviderError` naming the offender."""
    try:
        return _REGISTRY[name]
    except KeyError:
        raise UnknownProviderError(
            f"unknown provider {name!r}; known: {sorted(_REGISTRY)}"
        ) from None


def known_providers() -> frozenset[str]:
    """The registered provider names (for validation / help text)."""
    return frozenset(_REGISTRY)
