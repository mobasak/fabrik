"""The injected seam — local structural Protocols + the ``Deps`` bundle.

competitor-intel is **vendored, not imported**: it drives the ``deep-research`` engine and ``web-tools``
executors WITHOUT importing them. The consumer wires their already-vendored ``run_research`` /
``load_pack`` / leg executors / LLM in as callables; these Protocols pin the shapes structurally so
``mypy --strict`` checks the wiring with zero runtime coupling to ``deep_research``.

Grounded against ``deep-research/deep_research/engine.py`` (``run_research`` at :445, the ``Pack``
Protocol at :77, ``ResearchDeps`` at :103) and ``pack.py`` (``load_pack`` at :120). ``run_research``
reads a pack by attribute AND method access only (``_validate_deps`` at :415 is attribute-based, no
``isinstance``), so a structural ``Pack`` + a duck-typed deps shim satisfy it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LegSpec(Protocol):
    """One search leg as the engine reads it (mirrors ``engine.py`` ``LegSpec`` at :61). A real
    ``deep_research`` ``LegConfig`` (from ``load_pack``) satisfies this structurally. The full member set
    ``run_research`` reads (engine.py:244-247) is listed so this Protocol is a faithful contract, not a
    subset — competitor-intel itself reads only ``name``/``is_free`` (in ``_preflight_wiring``)."""

    @property
    def name(self) -> str: ...
    @property
    def cap(self) -> int: ...
    @property
    def is_free(self) -> bool: ...
    @property
    def include_market(self) -> bool: ...
    @property
    def num_results(self) -> int | None: ...


class Pack(Protocol):
    """The FULL injected worldview ``run_research`` reads (the ``engine.py`` ``Pack`` Protocol at :77-96) —
    the prompt attributes + caps + legs + the pure methods. A ``deep_research`` ``PackData`` produced by
    the injected ``load_pack`` satisfies this; competitor-intel never constructs one itself, and itself
    reads only ``legs`` (in ``_preflight_wiring``). Listed in full so a consumer who hand-rolls a pack has
    the complete contract (``run_research`` reads ``query_plan_prompt`` at engine.py:258, ``shortlist_prompt``
    at :338, ``verify_prompt`` at :402 — a subset Protocol would ``AttributeError`` inside the engine)."""

    @property
    def query_plan_prompt(self) -> str: ...
    @property
    def shortlist_prompt(self) -> str: ...
    @property
    def verify_prompt(self) -> str: ...
    @property
    def shortlist_cap(self) -> int: ...
    @property
    def verify_cap(self) -> int: ...
    @property
    def legs(self) -> Sequence[LegSpec]: ...
    def subject(self, brief: Mapping[str, Any]) -> str: ...
    def subject_name(self, brief: Mapping[str, Any]) -> str: ...
    def fallback_plan(self, brief: Mapping[str, Any], market: str) -> dict[str, list[str]]: ...
    def coerce_card(self, raw: Mapping[str, Any]) -> dict[str, Any]: ...


class ResearchFn(Protocol):
    """deep-research's ``run_research`` — an async staged research call. Returns the result doc
    (``{cards, spend_usd (str), credits, degraded_legs, truncated, status, ...}``); never raises for a
    money/staging reason, but DOES raise ``ValueError`` at entry on a deps-wiring bug (``engine.py:450``).
    ``deps`` is the duck-typed shim competitor-intel builds per call (never a real ``ResearchDeps``)."""

    def __call__(
        self, brief: Mapping[str, Any], market: str, *, pack: Pack, deps: Any
    ) -> Awaitable[dict[str, Any]]: ...


class PackLoader(Protocol):
    """deep-research's ``load_pack`` — turns a pack YAML path into a method-bearing ``PackData``. Injected
    (not imported) so the module ships the YAML but keeps ``deep_research`` out of its import graph, AND so
    the pack carries the methods ``run_research`` calls (``subject_name`` / ``fallback_plan`` /
    ``coerce_card``) that a plain ``yaml.safe_load`` dict would lack."""

    def __call__(self, path: str | Path) -> Pack: ...


class SynthLlm(Protocol):
    """The injected LLM for the synthesis tail (Phase B) — an OpenRouter-backed async text completion.
    Same shape as deep-research's ``LlmFn`` (``engine.py:32``). Kept distinct so a consumer MAY wire a
    cheaper model for synthesis than for staged research."""

    def __call__(self, prompt: str, **kwargs: Any) -> Awaitable[str]: ...


# The leg-executor callable the consumer wires from web-tools (``engine.py`` ``LegExecutor`` at :58).
# Opaque to competitor-intel — it only forwards it into the research shim.
LegExecutor = Any


@dataclass
class Deps:
    """Everything injected into :func:`competitor_intel.orchestrator.run`. The consumer wires deep-research
    (``research_fn`` + ``load_pack``), web-tools (``legs`` / ``scrape`` executors + their per-leg cost
    ESTIMATES — only the consumer knows its vendor pricing), the synthesis LLM, an opaque config + http
    client, the ORCHESTRATOR-level money bound (``total_budget_usd`` — one ceiling across ALL sub-calls,
    never per-call), and the checkpoint directory + job id.

    ``cost-budget`` is OPTIONAL — with no reservation, ``total_budget_usd`` is a plain injected USD cap.
    """

    research_fn: ResearchFn
    load_pack: PackLoader
    llm: SynthLlm
    legs: Mapping[str, LegExecutor]
    scrape: LegExecutor
    leg_estimates: Mapping[str, Decimal]
    scrape_estimate: Decimal
    config: Any  # opaque — forwarded to the executors, never read here
    client: Any  # opaque http client — forwarded to executors + adapters
    total_budget_usd: Decimal
    ceiling_factor: Decimal
    checkpoint_dir: Path
    job_id: str
    #: Charged against ``total_budget_usd`` per synthesis LLM call (Phase B) — the injected ``SynthLlm``
    #: returns no cost, so synthesis is metered by this estimate + gated on the remaining budget (a call is
    #: skipped → degrades to ``❓`` when the budget is exhausted). Keep it a realistic per-call USD estimate.
    synth_call_estimate: Decimal = Decimal("0.01")
