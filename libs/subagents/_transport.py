"""Vendored OpenRouter transport — a focused copy of ai-consult's `run.py`.

Vendored (not imported) per the fabrik-lib rule: a single OpenRouter call as
`run()`/`arun()` → :class:`Result`, over the :class:`._client.OpenRouterClient`
(SSE streaming + tool-call-by-index accumulation live in ``_client.py``). This
copy is deliberately narrowed vs. the upstream `run.py`:

* the ``.store``/``persist`` coupling is **dropped** — provenance is the Phase-D
  ledger's job, not the transport's;
* the ``run_many``/``arun_many`` batch helpers are **dropped** — ``agent.py``
  implements its own owned_paths-aware concurrency;
* everything else (liveness/restart, cost hygiene, served-model/provider
  provenance, the `over_cost_cap` post-hoc flag) is preserved verbatim so the
  tool-call streaming semantics `openrouter-api.md` warns about stay correct.

Source of truth: `ai-consult/ai_consult/run.py` (do not diverge silently — a bug
found here belongs in `ai-consult/UPSTREAM_FEEDBACK.md`).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import uuid
from dataclasses import dataclass

from ._client import (
    ConsultError,
    OpenRouterClient,
    RawResult,
    StateCb,
    TokenCb,
)
from .providers import resolve_provider

__all__ = ["run", "arun", "Result", "Liveness", "Call", "make_run_id"]


@dataclass
class Liveness:
    """Per-call liveness/restart config (reuses the client's idle-timeout + restart loop)."""

    idle_timeout_s: float = 120.0
    hard_timeout_s: float = 1800.0
    restart_max: int = 2
    connect_timeout_s: float = 30.0
    # CONTENT-level first-token deadline (0 = off). Catches a provider that heart-beats but streams
    # no content (defeating the byte-level idle timeout). Raises ContentStallError, which is NOT
    # retried by the client — it propagates to the caller (loop.py) that owns exclude-and-retry.
    first_token_timeout_s: float = 0.0


@dataclass
class Result:
    """One call's outcome. `model` is the SERVED/resolved id (falls back to
    requested); `provider` is the served upstream provider. `error` is None on
    success. `raw` is the underlying RawResult (None on an errored slot)."""

    text: str
    tool_calls: list[dict[str, object]] | None
    model: str
    provider: str | None
    usage: dict[str, object]
    cost_usd: float | None
    cost_unknown: bool
    finish_reason: str | None
    reasoning: str
    consult_id: str
    over_cost_cap: bool = False
    error: str | None = None
    raw: RawResult | None = None


@dataclass
class Call:
    """One member of a batch — same args as `run`."""

    model: str
    messages: list[dict[str, object]]
    body: dict[str, object] | None = None
    liveness: Liveness | None = None
    tags: list[str] | None = None


_DEFAULT_LIVENESS = Liveness()


def make_run_id(
    model: str, messages: list[dict[str, object]], body: dict[str, object] | None
) -> str:
    """sha1(model + messages + body)[:12] + random suffix, so re-running the SAME
    raw call logs a NEW replayable entry rather than colliding."""
    payload = (
        model
        + "\x00"
        + json.dumps(messages, sort_keys=True, default=str)
        + "\x00"
        + json.dumps(body or {}, sort_keys=True, default=str)
    )
    return f"{hashlib.sha1(payload.encode(), usedforsecurity=False).hexdigest()[:12]}-{uuid.uuid4().hex[:6]}"


def _resolve_client(
    client: OpenRouterClient | None, provider: str = "openrouter"
) -> OpenRouterClient:
    """The injected client, or one built from the provider registry + env. The API
    key is required (never a hardcoded default); an unknown provider fails LOUD."""
    if client is not None:
        return client
    cfg = resolve_provider(provider)
    api_key = os.getenv(cfg.key_env)
    if not api_key:
        if cfg.key_env == "OPENROUTER_API_KEY":
            # keep the well-known, battle-tested onboarding message for the default path
            raise ConsultError(
                "OPENROUTER_API_KEY is not set. `run_agents` auto-loads `<repo>/.env` (the curated "
                "subagents keys), so the usual fix is: put `OPENROUTER_API_KEY=…` in your project's "
                "`.env` and pass the project root as `repo=`. If you dispatched with `load_dotenv=False`, "
                "or called the transport directly, export it yourself (`set -a; . ./.env; set +a`). This "
                "is an env/onboarding gap, NOT 'the pool is unavailable' — wire the key, don't fall back "
                "to a different runtime."
            )
        raise ConsultError(
            f"{cfg.key_env} is not set, required for provider {provider!r}. `run_agents` auto-loads "
            f"`<repo>/.env` (the curated subagents keys) — put `{cfg.key_env}=…` in your project's "
            "`.env` and pass the project root as `repo=`, or export it yourself. This is an "
            "env/onboarding gap, NOT 'the provider is unavailable'."
        )
    # HTTP-Referer/X-Title are OpenRouter attribution headers — set them ONLY for a
    # provider that expects them (registry-gated); a non-OR endpoint ignores them at best.
    if cfg.sends_or_attribution_headers:
        return OpenRouterClient(
            api_key,
            base_url=cfg.base_url,
            referer=os.getenv("SUBAGENTS_REFERER"),
            title=os.getenv("SUBAGENTS_TITLE") or "subagents",
        )
    return OpenRouterClient(api_key, base_url=cfg.base_url)


def _lv(liveness: Liveness | None) -> Liveness:
    return liveness if liveness is not None else _DEFAULT_LIVENESS


def _run_raw(
    model: str,
    messages: list[dict[str, object]],
    *,
    body: dict[str, object] | None,
    liveness: Liveness | None,
    client: OpenRouterClient,
    on_token: TokenCb | None = None,
    on_state: StateCb | None = None,
) -> RawResult:
    lv = _lv(liveness)
    return client.call_model(
        messages,
        model,
        body=body,
        restart_max=lv.restart_max,
        idle_timeout_s=lv.idle_timeout_s,
        first_token_timeout_s=lv.first_token_timeout_s,
        hard_timeout_s=lv.hard_timeout_s,
        connect_timeout_s=lv.connect_timeout_s,
        on_token=on_token,
        on_state=on_state,
    )


async def _arun_raw(
    model: str,
    messages: list[dict[str, object]],
    *,
    body: dict[str, object] | None,
    liveness: Liveness | None,
    client: OpenRouterClient,
    on_token: TokenCb | None = None,
    on_state: StateCb | None = None,
) -> RawResult:
    lv = _lv(liveness)
    return await client.acall_model(
        messages,
        model,
        body=body,
        restart_max=lv.restart_max,
        idle_timeout_s=lv.idle_timeout_s,
        first_token_timeout_s=lv.first_token_timeout_s,
        hard_timeout_s=lv.hard_timeout_s,
        connect_timeout_s=lv.connect_timeout_s,
        on_token=on_token,
        on_state=on_state,
    )


def _clean_cost(raw: RawResult) -> tuple[float | None, bool]:
    """(cost_usd, cost_unknown) with a non-finite (nan/inf) or NEGATIVE provider
    cost treated as UNKNOWN — a bad value would misreport spend."""
    c = raw.cost_usd
    if c is None or not math.isfinite(c) or c < 0:
        return None, True
    return c, raw.cost_unknown


def _validate_cap(max_cost_usd: float | None) -> None:
    """A cap must be a finite, non-negative number (or None). A nan/inf cap would
    silently disable the gate (fail-open); a negative cap is nonsense. Fail LOUD."""
    if max_cost_usd is not None and (
        not math.isfinite(max_cost_usd) or max_cost_usd < 0
    ):
        raise ValueError(
            f"max_cost_usd must be a finite non-negative number or None, got {max_cost_usd!r}"
        )


def _to_result(
    raw: RawResult,
    consult_id: str,
    over_cost_cap: bool,
    *,
    cost_usd: float | None,
    cost_unknown: bool,
) -> Result:
    return Result(
        text=raw.text,
        tool_calls=raw.tool_calls,
        model=raw.served_model or raw.model,
        provider=raw.provider,
        usage=raw.usage,
        cost_usd=cost_usd,
        cost_unknown=cost_unknown,
        finish_reason=raw.finish_reason,
        reasoning=raw.reasoning,
        consult_id=consult_id,
        over_cost_cap=over_cost_cap,
        raw=raw,
    )


def _over_cap(cost_usd: float | None, max_cost_usd: float | None) -> bool:
    return (
        max_cost_usd is not None
        and cost_usd is not None
        and math.isfinite(cost_usd)
        and cost_usd > max_cost_usd
    )


def run(
    model: str,
    messages: list[dict[str, object]],
    *,
    body: dict[str, object] | None = None,
    liveness: Liveness | None = None,
    client: OpenRouterClient | None = None,
    max_cost_usd: float | None = None,
    on_token: TokenCb | None = None,
    on_state: StateCb | None = None,
    provider: str = "openrouter",
) -> Result:
    """One synchronous call → :class:`Result`. ``provider`` selects the endpoint/key
    from the registry (default OpenRouter); an injected ``client`` always wins."""
    _validate_cap(max_cost_usd)
    cli = _resolve_client(client, provider)
    consult_id = make_run_id(model, messages, body)
    raw = _run_raw(
        model,
        messages,
        body=body,
        liveness=liveness,
        client=cli,
        on_token=on_token,
        on_state=on_state,
    )
    cost_usd, cost_unknown = _clean_cost(raw)
    over = _over_cap(cost_usd, max_cost_usd)
    return _to_result(
        raw, consult_id, over, cost_usd=cost_usd, cost_unknown=cost_unknown
    )


async def arun(
    model: str,
    messages: list[dict[str, object]],
    *,
    body: dict[str, object] | None = None,
    liveness: Liveness | None = None,
    client: OpenRouterClient | None = None,
    max_cost_usd: float | None = None,
    on_token: TokenCb | None = None,
    on_state: StateCb | None = None,
    provider: str = "openrouter",
) -> Result:
    """One asynchronous call → :class:`Result`. ``provider`` selects the endpoint/key
    from the registry (default OpenRouter); an injected ``client`` always wins."""
    _validate_cap(max_cost_usd)
    cli = _resolve_client(client, provider)
    consult_id = make_run_id(model, messages, body)
    raw = await _arun_raw(
        model,
        messages,
        body=body,
        liveness=liveness,
        client=cli,
        on_token=on_token,
        on_state=on_state,
    )
    cost_usd, cost_unknown = _clean_cost(raw)
    over = _over_cap(cost_usd, max_cost_usd)
    return _to_result(
        raw, consult_id, over, cost_usd=cost_usd, cost_unknown=cost_unknown
    )
