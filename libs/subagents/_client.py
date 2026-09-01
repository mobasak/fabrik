"""OpenRouter transport: SSE streaming with state-aware liveness (idle-timeout =
"stuck" detector) + restart-on-stuck + full cost capture. Sync and async.

Ported from /opt/fabrik/scripts/kilo_code_review.py's _monitor_process: output
(here = bytes on the SSE socket) resets liveness; a silent socket trips the idle
timeout and the call is RESTARTED, then escalated. Vendor this folder, don't import.
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import urlparse

import httpx


def _is_openrouter_host(base_url: str) -> bool:
    """True iff ``base_url``'s HOST is OpenRouter (exact host or a ``*.openrouter.ai`` subdomain).
    A host match, not a prefix — so ``https://openrouter.ai.evil.example`` does NOT qualify."""
    host = (urlparse(base_url).hostname or "").lower()
    return host == "openrouter.ai" or host.endswith(".openrouter.ai")

__all__ = [
    "OpenRouterClient",
    "State",
    "RawResult",
    "ConsultError",
    "TransientError",
    "StuckError",
    "TruncatedError",
    "EmptyContentError",
    "HardTimeoutError",
    "AuthError",
]

StateCb = Callable[[str, str, int], None]
TokenCb = Callable[[str], None]


class State(str, Enum):  # noqa: UP042 — exported public API; StrEnum would change str(member) output (a behavior change for vendored consumers), and nothing here relies on the modern form
    CONNECTING = "connecting"
    ALIVE_WAITING = "alive_waiting"
    STREAMING = "streaming"
    COMPLETE = "complete"
    STUCK = "stuck"
    TRUNCATED = "truncated"
    TIMEOUT = "timeout"
    ERROR = "error"


# ── Errors ──────────────────────────────────────────────────────────────────
class ConsultError(Exception):
    """Base. Carries partial text + the per-attempt chain (never a silent empty)."""

    def __init__(
        self,
        message: str,
        *,
        partial: str = "",
        status: int | None = None,
        attempts: list[dict[str, object]] | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.partial = partial
        self.status = status
        self.attempts = attempts or []
        self.retry_after = retry_after


class TransientError(ConsultError):
    """5xx / connection error — re-issue the model (counts against restart_max)."""


class StuckError(ConsultError):
    """Idle timeout: no bytes for idle_timeout_s — restart."""


class TruncatedError(ConsultError):
    """Stream ended with no [DONE] and no finish_reason — restart."""


class EmptyContentError(ConsultError):
    """COMPLETE but content empty (reasoner spent its budget) — bump max_tokens once."""


class HardTimeoutError(ConsultError):
    """Absolute hard_timeout_s ceiling hit — restart."""


class ContentStallError(ConsultError):
    """No CONTENT token (text/tool_call) within ``first_token_timeout_s`` — the provider connected
    and may even be heart-beating (`: OPENROUTER PROCESSING`, which resets the byte-level read
    timeout) but is producing no output. Deliberately NOT in ``_RETRYABLE`` so ``call_model`` does
    not swallow/retry it — it propagates to the caller (``loop.py``), which owns the
    exclude-the-stalled-provider-and-retry policy. ``provider`` is the served upstream provider when
    known (any data chunk arrived — OR sends it in chunk 0), else ``None`` (a zero-chunk hang)."""

    def __init__(
        self, message: str, *, partial: str = "", provider: str | None = None
    ) -> None:
        super().__init__(message, partial=partial)
        self.provider = provider


class AuthError(ConsultError):
    """401/403 — not retryable (raise immediately)."""


@dataclass
class RawResult:
    text: str
    reasoning: str
    finish_reason: str | None
    usage: dict[str, object]
    cost_usd: float | None
    cost_unknown: bool
    gen_id: str | None
    model: str
    status: State = State.COMPLETE
    # New (Phase A) — defaulted + appended so provider.py + _finalize (both construct by
    # kwargs) stay valid. `model` stays the REQUESTED id (backward-compat: ConsultResult.model
    # + the persisted store record must not silently switch to the resolved id). `served_model`
    # is the resolved id from the stream (may differ, e.g. an alias/snapshot); the Phase-B run()
    # layer WILL surface `served_model or model` as its provenance (not wired at this layer).
    # `provider` is the SERVED upstream
    # provider (e.g. "Anthropic"). `tool_calls` None unless the model requested tools.
    tool_calls: list[dict[str, object]] | None = None
    provider: str | None = None
    served_model: str | None = None


@dataclass
class _Acc:
    text: str = ""
    reasoning: str = ""
    finish_reason: str | None = None
    usage: dict[str, object] = field(default_factory=dict)
    gen_id: str | None = None
    saw_done: bool = False
    tool_calls: dict[int, dict[str, object]] = field(
        default_factory=dict
    )  # keyed by delta index
    provider: str | None = None  # served upstream provider (top-level chunk field)
    served_model: str | None = None  # resolved model id (top-level chunk field)
    # monotonic count of OUTPUT frames — any data chunk whose `delta` carries a non-`role` value
    # (content / tool_calls / reasoning / refusal / a field this parser doesn't model). It's the
    # robust liveness signal the stall detector resets on: parsed-or-not, an output frame is the
    # provider WORKING, whereas heartbeats / blank / role-only frames are not.
    output_frames: int = 0


def _feed(line: str, acc: _Acc, on_token: TokenCb | None) -> str:
    """Apply one SSE line to the accumulator. Returns the line kind."""
    if not line:
        return "blank"
    if line.startswith(":"):
        return (
            "heartbeat"  # `: OPENROUTER PROCESSING` keepalive — liveness, not content
        )
    if not line.startswith("data:"):
        return "blank"
    payload = line[5:].strip()
    if payload == "[DONE]":
        acc.saw_done = True
        return "done"
    try:
        d = json.loads(payload)
    except (ValueError, TypeError):
        return "data"  # malformed chunk — ignore body, still counts as activity
    if not isinstance(d, dict):
        return "data"
    if acc.gen_id is None:
        acc.gen_id = d.get("id")
    if acc.provider is None:  # served upstream provider — first non-empty wins
        prov = d.get("provider")
        if isinstance(prov, str) and prov:
            acc.provider = prov
    if (
        acc.served_model is None
    ):  # resolved model id (may differ from the requested one)
        sm = d.get("model")
        if isinstance(sm, str) and sm:
            acc.served_model = sm
    usage = d.get("usage")
    if isinstance(usage, dict):
        acc.usage = usage
    # Guard every structural shape defensively — a misbehaving upstream can emit a non-list
    # `choices`, a non-dict element, or a non-dict `delta`; none may raise a raw
    # KeyError/AttributeError/TypeError out of _feed (contract: never a raw exception).
    choices = d.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        ch = choices[0]
        delta = ch.get("delta")
        if not isinstance(delta, dict):
            delta = {}
        # Robust liveness: any non-`role` truthy delta key is the provider streaming an OUTPUT frame
        # (content / tool_calls / reasoning / refusal / legacy function_call / audio / anything this
        # parser doesn't model). Count the frame so the stall detector never false-positives on an
        # output channel we don't parse — a `role`-only or empty delta doesn't count.
        if any(v for k, v in delta.items() if k != "role"):
            acc.output_frames += 1
        content = delta.get("content")
        if (
            isinstance(content, str) and content
        ):  # a non-string content (multimodal part
            acc.text += (
                content  # array / number from a misbehaving upstream) must not crash
            )
            if (
                on_token is not None
            ):  # `str += non-str` — drop it, never raise a raw TypeError
                on_token(content)
        _accumulate_tool_calls(delta.get("tool_calls"), acc)
        for rk in ("reasoning", "reasoning_content"):
            rv = delta.get(rk)
            if isinstance(rv, str) and rv:
                acc.reasoning += rv
        # A streamed safety `refusal` (OpenAI Structured-Outputs / moderation) IS the model's
        # response — surface it as text (else it's silently dropped from RawResult) AND, because it
        # then grows the output signal, a refusal-only stream is never misread as a content stall.
        refusal = delta.get("refusal")
        if isinstance(refusal, str) and refusal:
            acc.text += refusal
        fr = ch.get("finish_reason")
        if fr:
            acc.finish_reason = fr
    return "data"


def _accumulate_tool_calls(deltas: object, acc: _Acc) -> None:
    """Accumulate streamed OpenAI-compatible tool_call deltas, keyed by `index`: the first
    delta for an index carries id/type/function.name; later deltas append function.arguments
    fragments. Malformed entries (non-dict, bad/negative/bool index) are skipped defensively."""
    if not isinstance(deltas, list):
        return
    for tc in deltas:
        if not isinstance(tc, dict):
            continue
        idx = tc.get("index")
        if isinstance(idx, bool):
            continue  # bool is an int subclass — a True index must not alias index 1
        if isinstance(idx, float) and idx.is_integer():
            idx = int(
                idx
            )  # tolerate a non-strict serializer emitting an integral index as 0.0
        if not isinstance(idx, int) or idx < 0:
            continue
        slot = acc.tool_calls.setdefault(
            idx,
            {
                "id": None,
                "type": "function",
                "function": {"name": None, "arguments": ""},
            },
        )
        if tc.get("id"):
            slot["id"] = tc["id"]
        if tc.get("type"):
            slot["type"] = tc["type"]
        fn = tc.get("function")
        if isinstance(fn, dict):
            slot_fn = slot["function"]
            assert isinstance(slot_fn, dict)
            if fn.get("name"):
                slot_fn["name"] = fn["name"]
            arg = fn.get("arguments")
            if isinstance(arg, str):
                slot_fn["arguments"] += arg


def _finalize_tool_calls(acc: _Acc) -> list[dict[str, object]] | None:
    """The accumulated tool_calls as an ordered list (by index), or None. A fully-empty stub
    (no id, no function name, no arguments — e.g. a stray index-only delta) is dropped so it
    cannot masquerade as a real tool call and mask an empty-content / reasoning-only response."""
    if not acc.tool_calls:
        return None
    out: list[dict[str, object]] = []
    for idx in sorted(acc.tool_calls):
        tc = acc.tool_calls[idx]
        fn = tc["function"]
        assert isinstance(fn, dict)
        if tc["id"] is None and fn["name"] is None and not fn["arguments"]:
            continue
        out.append(tc)
    return out or None


class OpenRouterClient:
    """Thin OpenRouter chat client. `api_key` is injected (never read from env here;
    that's the consult layer). `transport` is a test seam (httpx.MockTransport).
    """

    def __init__(
        self,
        api_key: str,
        *,
        referer: str | None = None,
        title: str | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        transport: httpx.BaseTransport | None = None,
        progress: bool = True,
    ) -> None:
        self._api_key = api_key
        self._referer = referer
        self._title = title
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._progress = (
            progress  # emit [CONSULT_PROGRESS] to stderr (opt-out for quiet consumers)
        )

    def _headers(self) -> dict[str, str]:
        # Authorization is emitted ONLY when there is a key. An anonymous provider (a registry row
        # with `key_optional=True`, e.g. Kilo's `:free` tier) is built with `api_key=""`, and an
        # unguarded f-string would send the literal header `Bearer ` — which no provider accepts,
        # so this is strictly safer than the previous unconditional form rather than a new mode.
        h = {"Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        if self._referer:
            h["HTTP-Referer"] = self._referer
        if self._title:
            h["X-Title"] = self._title
        return h

    def _body(
        self,
        messages: list[dict[str, object]],
        model: str,
        *,
        response_format: dict[str, object] | None = None,
        max_tokens: int | None = None,
        plugins: list[dict[str, object]] | None = None,
        body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Build the request body. `body` is a purpose-neutral OpenRouter passthrough — the
        caller may carry provider/models/reasoning/transforms/tools/tool_choice/usage/
        response_format/parallel_tool_calls/etc. A nested `extra_body` dict is flattened to
        the top level (OpenAI-SDK-style). The legacy kwargs fold OVER the caller body (so the
        empty-content max_tokens bump wins), and the managed keys (model/messages/stream) ALWAYS
        win — a caller cannot override the transport invariants. (Usage/cost ships automatically
        on every OpenRouter response, so `stream_options:{include_usage}` is no longer sent — it
        is a deprecated no-op; see ai-consult/UPSTREAM_FEEDBACK.md.)"""
        merged: dict[str, object] = dict(body or {})
        extra = merged.get("extra_body")
        if isinstance(extra, dict):
            merged.pop("extra_body")
            merged.update(extra)
        # a non-dict extra_body is left in place → the API surfaces the caller's shape error
        # instead of it being silently swallowed.
        if response_format is not None:
            merged["response_format"] = response_format
        if plugins:
            merged["plugins"] = plugins
        if (
            max_tokens is not None
        ):  # explicit param wins over any body-supplied max_tokens
            merged["max_tokens"] = max_tokens
        merged["model"] = model
        merged["messages"] = messages
        merged["stream"] = True
        return merged

    def _emit(self, cb: StateCb | None, event: str, model: str, attempt: int) -> None:
        if self._progress:
            # stderr.write, NOT print(): library code stays print-free so a consuming project's
            # print-ban gate never trips on a vendored copy. Behaviour is identical to the old
            # print(..., file=sys.stderr, flush=True) — same stream, explicit newline + flush.
            sys.stderr.write(
                f"[CONSULT_PROGRESS] {json.dumps({'event': event, 'model': model, 'attempt': attempt})}\n"
            )
            sys.stderr.flush()
        if cb is not None:
            cb(event, model, attempt)  # callback fires regardless of the stderr flag

    def _raise_for_http(
        self, status: int, body_text: str, retry_after: float | None = None
    ) -> None:
        if status in (401, 403):
            raise AuthError(
                f"auth failed (HTTP {status})", status=status, partial=body_text[:500]
            )
        if status in (408, 429) or status >= 500:
            raise TransientError(
                f"HTTP {status}",
                status=status,
                partial=body_text[:500],
                retry_after=retry_after,
            )
        # other 4xx — caller's bad request; not retryable
        raise ConsultError(f"HTTP {status}: {body_text[:300]}", status=status)

    @staticmethod
    def _retry_after(resp: httpx.Response) -> float | None:
        raw = resp.headers.get("retry-after")
        if raw is None:
            return None
        try:
            return float(
                raw
            )  # seconds form; HTTP-date form is ignored (rare for OpenRouter)
        except ValueError:
            return None

    @staticmethod
    def _finalize(acc: _Acc, model: str) -> RawResult:
        ended = acc.saw_done or acc.finish_reason is not None
        tool_calls = _finalize_tool_calls(acc)
        if not ended:
            raise TruncatedError(
                "stream ended without [DONE] or finish_reason", partial=acc.text
            )
        # A tool-call response — finish_reason=="tool_calls" OR real tool_calls accumulated —
        # is a VALID completion even with empty text; never treat it as empty/truncated. The
        # finish_reason arm covers a server that reports a tool-call turn whose deltas we could
        # not accumulate (index-less/malformed), avoiding a spurious retry storm on a completed
        # exchange.
        is_tool_completion = tool_calls is not None or acc.finish_reason == "tool_calls"
        if not acc.text and not is_tool_completion:
            if acc.reasoning:
                raise EmptyContentError(
                    "completed but content empty (reasoner spent its budget on reasoning)",
                    partial=acc.reasoning,
                )
            raise TruncatedError("no content received", partial="")
        return RawResult(
            text=acc.text,
            reasoning=acc.reasoning,
            finish_reason=acc.finish_reason,
            usage=acc.usage,
            cost_usd=None,
            cost_unknown=False,
            gen_id=acc.gen_id,
            model=model,  # the REQUESTED model — backward-compat (served id is `served_model`)
            status=State.COMPLETE,
            tool_calls=tool_calls,
            provider=acc.provider,
            served_model=acc.served_model,
        )

    # ── sync stream ───────────────────────────────────────────────────────
    def stream_chat(
        self,
        messages: list[dict[str, object]],
        model: str,
        *,
        response_format: dict[str, object] | None = None,
        max_tokens: int | None = None,
        plugins: list[dict[str, object]] | None = None,
        body: dict[str, object] | None = None,
        idle_timeout_s: float = 120.0,
        hard_timeout_s: float = 1800.0,
        connect_timeout_s: float = 30.0,
        first_token_timeout_s: float = 0.0,
        on_token: TokenCb | None = None,
        on_state: StateCb | None = None,
        _now: Callable[[], float] = time.monotonic,
    ) -> RawResult:
        payload = self._body(
            messages,
            model,
            response_format=response_format,
            max_tokens=max_tokens,
            plugins=plugins,
            body=body,
        )
        timeout = httpx.Timeout(
            connect=connect_timeout_s,
            read=idle_timeout_s,
            write=connect_timeout_s,
            pool=connect_timeout_s,
        )
        acc = _Acc()
        deadline = _now() + hard_timeout_s
        # Idle-since-last-OUTPUT window (0 = off). The window RESETS whenever new output arrives
        # (text / tool_calls / reasoning) and is NOT reset by heartbeats (`: OPENROUTER PROCESSING`,
        # which do reset the byte-level `read` timeout — that's why this exists). It catches BOTH a
        # provider that never produces output AND one that produces then hangs mid-stream; a fixed
        # one-shot deadline would miss the latter (a reasoner streams one token then stalls). Reasoning
        # counts as output — a reasoner streaming its chain-of-thought is WORKING, not stalled.
        stall_window = first_token_timeout_s if first_token_timeout_s > 0 else None
        last_output = _now()
        last_sig = 0
        self._emit(on_state, "model_start", model, 0)
        streaming = False
        with httpx.Client(
            base_url=self._base_url, transport=self._transport, timeout=timeout
        ) as client:
            try:
                with client.stream(
                    "POST", "/chat/completions", json=payload, headers=self._headers()
                ) as resp:
                    if resp.status_code != 200:
                        self._raise_for_http(
                            resp.status_code,
                            resp.read().decode(errors="replace"),
                            self._retry_after(resp),
                        )
                    self._emit(on_state, "alive_waiting", model, 0)
                    for line in resp.iter_lines():
                        if _now() > deadline:
                            raise HardTimeoutError(
                                f"hard timeout {hard_timeout_s}s", partial=acc.text
                            )
                        kind = _feed(line, acc, on_token)
                        if (
                            kind == "data"
                            and not streaming
                            and (acc.text or acc.tool_calls)
                        ):
                            streaming = True
                            self._emit(on_state, "streaming", model, 0)
                        if kind == "done":
                            break
                        # Idle-since-last-output stall. `sig` grows with any output (text + reasoning +
                        # per-tool-call arg bytes); heartbeats/blank lines don't change it. New output ⇒
                        # reset the window; NO new output for `stall_window` ⇒ the provider is
                        # heart-beating into the void → stall. Checked AFTER the done-break so a
                        # completed-but-empty response takes the EmptyContentError (bump) path, not a stall.
                        if stall_window is not None:
                            if acc.output_frames != last_sig:
                                last_sig = acc.output_frames
                                last_output = _now()
                            elif _now() - last_output > stall_window:
                                raise ContentStallError(
                                    f"no output for {first_token_timeout_s}s",
                                    partial=acc.text,
                                    provider=acc.provider,
                                )
            except httpx.ReadTimeout as exc:
                raise StuckError(
                    f"idle > {idle_timeout_s}s (stuck)", partial=acc.text
                ) from exc
            except httpx.RequestError as exc:
                raise TransientError(
                    f"connection error: {exc}", partial=acc.text
                ) from exc
        result = self._finalize(acc, model)
        result.cost_usd, result.cost_unknown = self._resolve_cost(
            acc, allow_blocking=True
        )
        self._emit(on_state, "complete", model, 0)
        return result

    # ── async stream ──────────────────────────────────────────────────────
    async def astream_chat(
        self,
        messages: list[dict[str, object]],
        model: str,
        *,
        response_format: dict[str, object] | None = None,
        max_tokens: int | None = None,
        plugins: list[dict[str, object]] | None = None,
        body: dict[str, object] | None = None,
        idle_timeout_s: float = 120.0,
        hard_timeout_s: float = 1800.0,
        connect_timeout_s: float = 30.0,
        first_token_timeout_s: float = 0.0,
        on_token: TokenCb | None = None,
        on_state: StateCb | None = None,
        _now: Callable[[], float] = time.monotonic,
    ) -> RawResult:
        payload = self._body(
            messages,
            model,
            response_format=response_format,
            max_tokens=max_tokens,
            plugins=plugins,
            body=body,
        )
        timeout = httpx.Timeout(
            connect=connect_timeout_s,
            read=idle_timeout_s,
            write=connect_timeout_s,
            pool=connect_timeout_s,
        )
        acc = _Acc()
        deadline = _now() + hard_timeout_s
        # Idle-since-last-OUTPUT window (0 = off) — see stream_chat: resets on new output
        # (text/tool_calls/reasoning), heartbeat-immune; catches never-produces AND produces-then-hangs.
        stall_window = first_token_timeout_s if first_token_timeout_s > 0 else None
        last_output = _now()
        last_sig = 0
        self._emit(on_state, "model_start", model, 0)
        streaming = False
        atransport = (
            self._transport
            if isinstance(self._transport, httpx.AsyncBaseTransport)
            else None
        )
        async with httpx.AsyncClient(
            base_url=self._base_url, transport=atransport, timeout=timeout
        ) as client:
            try:
                async with client.stream(
                    "POST", "/chat/completions", json=payload, headers=self._headers()
                ) as resp:
                    if resp.status_code != 200:
                        self._raise_for_http(
                            resp.status_code,
                            (await resp.aread()).decode(errors="replace"),
                            self._retry_after(resp),
                        )
                    self._emit(on_state, "alive_waiting", model, 0)
                    async for line in resp.aiter_lines():
                        if _now() > deadline:
                            raise HardTimeoutError(
                                f"hard timeout {hard_timeout_s}s", partial=acc.text
                            )
                        kind = _feed(line, acc, on_token)
                        if (
                            kind == "data"
                            and not streaming
                            and (acc.text or acc.tool_calls)
                        ):
                            streaming = True
                            self._emit(on_state, "streaming", model, 0)
                        if kind == "done":
                            break
                        # Idle-since-last-output stall. `sig` grows with any output (text + reasoning +
                        # per-tool-call arg bytes); heartbeats/blank lines don't change it. New output ⇒
                        # reset the window; NO new output for `stall_window` ⇒ the provider is
                        # heart-beating into the void → stall. Checked AFTER the done-break so a
                        # completed-but-empty response takes the EmptyContentError (bump) path, not a stall.
                        if stall_window is not None:
                            if acc.output_frames != last_sig:
                                last_sig = acc.output_frames
                                last_output = _now()
                            elif _now() - last_output > stall_window:
                                raise ContentStallError(
                                    f"no output for {first_token_timeout_s}s",
                                    partial=acc.text,
                                    provider=acc.provider,
                                )
            except httpx.ReadTimeout as exc:
                raise StuckError(
                    f"idle > {idle_timeout_s}s (stuck)", partial=acc.text
                ) from exc
            except httpx.RequestError as exc:
                raise TransientError(
                    f"connection error: {exc}", partial=acc.text
                ) from exc
        result = self._finalize(acc, model)
        # async path: do NOT call the blocking /generation fallback (sync sleep + sync
        # httpx would stall the event loop). usage.cost is in-stream (include_usage); if
        # absent, mark unknown — gen_id is preserved on the result for later recovery.
        result.cost_usd, result.cost_unknown = self._resolve_cost(
            acc, allow_blocking=False
        )
        self._emit(on_state, "complete", model, 0)
        return result

    # ── cost ──────────────────────────────────────────────────────────────
    def _resolve_cost(
        self, acc: _Acc, *, allow_blocking: bool
    ) -> tuple[float | None, bool]:
        cost = acc.usage.get("cost")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool):
            return float(cost), False
        # The /generation cost-recovery endpoint is OpenRouter-specific; a non-OR OpenAI-compatible
        # endpoint (NVIDIA) has no such route, so skip the blocking GET there (it would 404 + stall
        # ~6s). NVIDIA is $0/free anyway, so cost_unknown is the honest, harmless result. Match on
        # the URL HOST (not a prefix — `openrouter.ai.evil.example` must not slip through); base_url
        # comes from the provider registry.
        if allow_blocking and acc.gen_id and _is_openrouter_host(self._base_url):
            recovered = self._fetch_generation_cost(acc.gen_id)
            if recovered is not None:
                return recovered, False
        return None, True

    # ── per-model restart loop (ports kilo_code_review retry-on-timeout) ────
    _RETRYABLE = (StuckError, TruncatedError, TransientError, HardTimeoutError)
    _EMPTY_BUMP_TOKENS = 16000

    @staticmethod
    def _body_max_tokens(body: object) -> int | None:
        """The caller's requested max_tokens from the passthrough ``body``, resolved the way
        :meth:`_body` does (top-level, or a nested ``extra_body`` which wins on flatten). ``None``
        if absent or not a positive int — so the empty-content bump can *floor* at it without ever
        LOWERING a deliberately-large caller budget (e.g. glm-5's ``{"max_tokens": 20000}``)."""
        if not isinstance(body, dict):
            return None
        val = body.get("max_tokens")
        extra = body.get("extra_body")
        if isinstance(extra, dict) and "max_tokens" in extra:
            val = extra.get(
                "max_tokens"
            )  # extra_body wins — matches _body's merged.update(extra)
        return (
            val
            if isinstance(val, int) and not isinstance(val, bool) and val > 0
            else None
        )

    def call_model(
        self,
        messages: list[dict[str, object]],
        model: str,
        *,
        restart_max: int = 2,
        max_tokens: int | None = None,
        on_state: StateCb | None = None,
        sleep: Callable[[float], None] = time.sleep,
        **kw: Any,
    ) -> RawResult:
        """stream_chat with restart-on-stuck (up to restart_max) + a one-shot
        empty-content max_tokens bump. Raises with the attempt chain when exhausted.
        """
        attempts: list[dict[str, object]] = []
        bumped = False
        restarts = 0
        while True:
            try:
                return self.stream_chat(
                    messages, model, max_tokens=max_tokens, on_state=on_state, **kw
                )
            except EmptyContentError as exc:
                attempts.append(
                    {"model": model, "error": "EmptyContentError", "restart": restarts}
                )
                if bumped:
                    exc.attempts = attempts
                    raise
                bumped = True
                # distinct retry, not a restart. Bump the budget but NEVER below what the caller
                # asked for (max_tokens kwarg OR the body passthrough) — the bump exists to RAISE a
                # too-small budget, not shrink a deliberately-large one (regression: a body
                # max_tokens=20000 was silently downgraded to 16000 on this path).
                caller_mt = (
                    max_tokens
                    if max_tokens is not None
                    else self._body_max_tokens(kw.get("body"))
                )
                max_tokens = max(self._EMPTY_BUMP_TOKENS, caller_mt or 0)
            except self._RETRYABLE as exc:
                attempts.append(
                    {
                        "model": model,
                        "error": type(exc).__name__,
                        "restart": restarts,
                        "partial_len": len(exc.partial),
                    }
                )
                if restarts >= restart_max:
                    exc.attempts = attempts
                    raise
                restarts += 1
                self._emit(on_state, "restarting", model, restarts)
                sleep(
                    exc.retry_after
                    if exc.retry_after is not None
                    else float(2 ** (restarts - 1))
                )
            except ConsultError as exc:  # AuthError + clean 4xx — not retryable
                attempts.append(
                    {"model": model, "error": type(exc).__name__, "restart": restarts}
                )
                exc.attempts = attempts
                raise

    async def acall_model(
        self,
        messages: list[dict[str, object]],
        model: str,
        *,
        restart_max: int = 2,
        max_tokens: int | None = None,
        on_state: StateCb | None = None,
        **kw: Any,
    ) -> RawResult:
        import asyncio

        attempts: list[dict[str, object]] = []
        bumped = False
        restarts = 0
        while True:
            try:
                return await self.astream_chat(
                    messages,
                    model,
                    max_tokens=max_tokens,
                    on_state=on_state,
                    **kw,
                )
            except EmptyContentError as exc:
                attempts.append(
                    {"model": model, "error": "EmptyContentError", "restart": restarts}
                )
                if bumped:
                    exc.attempts = attempts
                    raise
                bumped = True
                # never below the caller's budget — see the sync call_model for the rationale.
                caller_mt = (
                    max_tokens
                    if max_tokens is not None
                    else self._body_max_tokens(kw.get("body"))
                )
                max_tokens = max(self._EMPTY_BUMP_TOKENS, caller_mt or 0)
            except self._RETRYABLE as exc:
                attempts.append(
                    {
                        "model": model,
                        "error": type(exc).__name__,
                        "restart": restarts,
                        "partial_len": len(exc.partial),
                    }
                )
                if restarts >= restart_max:
                    exc.attempts = attempts
                    raise
                restarts += 1
                self._emit(on_state, "restarting", model, restarts)
                await asyncio.sleep(
                    exc.retry_after
                    if exc.retry_after is not None
                    else float(2 ** (restarts - 1))
                )
            except ConsultError as exc:
                attempts.append(
                    {"model": model, "error": type(exc).__name__, "restart": restarts}
                )
                exc.attempts = attempts
                raise

    def _fetch_generation_cost(
        self, gen_id: str, *, sleep: Callable[[float], None] = time.sleep
    ) -> float | None:
        # /generation is eventually-consistent (~6s); retry with backoff. Best-effort.
        with httpx.Client(
            base_url=self._base_url, transport=self._transport, timeout=15.0
        ) as client:
            for delay in (0.0, 2.0, 4.0):
                if delay:
                    sleep(delay)
                try:
                    r = client.get(
                        "/generation", params={"id": gen_id}, headers=self._headers()
                    )
                except httpx.RequestError:
                    return None
                if r.status_code == 200:
                    data = (r.json() or {}).get("data") or {}
                    tc = data.get("total_cost")
                    return (
                        float(tc)
                        if isinstance(tc, (int, float)) and not isinstance(tc, bool)
                        else None
                    )
                if r.status_code != 404:
                    return None
        return None
