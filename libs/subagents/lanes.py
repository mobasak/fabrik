"""Free multi-provider lane chain — one call, many free providers, skip-don't-retry.

Walks an ordered chain of ``(provider, model, cap)`` tiers: the first to answer wins, a failure
falls through, and a rate-limited or dead lane is **benched** (skipped for a cooldown) rather than
retried into. Mirrors LiteLLM Router *semantics* — typed fallbacks, cooldowns, rate-limit-aware
routing — **without importing LiteLLM** (the Mar-2026 PyPI key-theft compromise + CVE-2026-42208,
CVSS 9.3; see the design spec § Rejected alternatives).

⚠️ **When NOT to use it.** The lanes are free tiers: dev/eval/batch/background work with a paid or
subscription backstop, **not a production request path serving real users** (NVIDIA's free API is
ToS-restricted to internal testing and evaluation). Published rate numbers are hints, not SLAs.

**Three properties that are correctness, not tuning:**

1. ``Liveness(restart_max=0)`` — ``_client._RETRYABLE`` includes ``TransientError`` and
   ``_raise_for_http`` maps **429 into it**, and the retry arm SLEEPS ``retry_after``. Left at the
   default 2, a 429 carrying ``Retry-After: 90`` burns three free calls and blocks ~180 s inside the
   client before this chain gets to skip anything. Disabling it is what makes "skip-fast" true.
   (``loop.py``'s ``run_loop`` does the same for the same reason.)

   ⚠️ **It does NOT disable the empty-content ``max_tokens`` bump, and that is a real hole.**
   ``call_model`` tracks the bump on its own ``bumped`` flag, independent of ``restart_max``: if a
   response arrives with empty content it raises ``max_tokens`` to ``_EMPTY_BUMP_TOKENS`` (16000)
   and issues **one more call**. So a lane can cost TWO requests, not one — and on a small free
   tier the bumped request is often rejected outright (observed live: Groq free tier answers
   ``413`` to the 16000-token retry, for a model that works fine at 300). Pass a sane
   ``body={"max_tokens": N}`` so the first call returns content and the bump never triggers;
   ``413`` is treated as a request-shape error and benches nothing.
2. **The bench key depends on the CAUSE.** A 429/503 is account-scoped, so it benches the
   *provider*. A pulled or renamed model is a 4xx about ONE model, so it benches only
   ``(provider, model)`` — benching the provider there would turn one dead model into a dead
   provider and destroy the intra-provider diversity a fallback chain depends on.
3. **The bench state is IN-PROCESS.** A fresh process re-probes each provider once. A cross-process
   bench would need a file, whose failure modes (staleness, permissions, concurrent writers) cost
   more than the single wasted call it would save. Stated, not hidden.

**Auto-promotion without a probe.** The default issues no health probe: the first call through the
chain drops dead rungs, and every subsequent call in the run is served from the survivors in the
caller's original order — so a recovered provider returns to the front by itself when its bench
expires. A caller wanting a run-start probe passes ``probe=`` (Phase C). The residual cost of the
default is that a single-call (non-batch) consumer pays the dead-primary failure once.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any

from . import _transport
from ._client import AuthError, ConsultError
from ._transport import Liveness, Result
from .pg_ledger import record_agent_run
from .providers import resolve_provider

__all__ = [
    "lane_chain",
    "AllLanesExhaustedError",
    "FailureCause",
    "classify",
    "apply_bench",
    "bench_remaining",
    "lane_progress",
    "reset_lane_state",
]

#: Cooldown for a rate-limited provider when it sent no ``Retry-After`` (seconds).
_DEFAULT_COOLDOWN_S = 60.0
#: Cooldown for a lane whose MODEL looks gone (a non-429 4xx), and for an auth failure — neither is
#: a transient condition, so re-dialling it soon just burns quota discovering the same thing.
_DEFAULT_DEAD_COOLDOWN_S = 900.0
#: Ceiling on any cooldown. A provider (or a proxy in front of it) can send an absurd
#: ``Retry-After``; without a clamp one bad header benches a lane for a week.
_DEFAULT_MAX_COOLDOWN_S = 3600.0

#: Consecutive TRANSIENT failures a lane is allowed before it is actually benched. The field norm
#: (LiteLLM's ``allowed_fails``, commonly 3/min) COUNTS failures before cooling a deployment down;
#: benching on the FIRST one ejects a healthy lane over a single blip. ⚠️ **THE ONE DELIBERATE
#: BEHAVIOUR CHANGE this module makes to the old ``_bench`` (T07)** — every other line in this
#: file is T01's byte-for-byte ``classify``/``apply_bench`` split; this constant is not. PERMANENT
#: causes (401/402/410/model-gone/…) are unaffected — they still bench on the first occurrence.
_DEFAULT_FAIL_THRESHOLD = 3

#: provider -> monotonic deadline. Rate limits and auth failures are account-scoped.
_bench_provider: dict[str, float] = {}
#: (provider, model) -> monotonic deadline. A dead/renamed model, scoped to that model alone.
_bench_model: dict[tuple[str, str], float] = {}
#: Consecutive TRANSIENT failure count, keyed by the BENCH TARGET — the provider name alone for a
#: provider-scoped cause (429/503's default: every model of that provider is equally unavailable,
#: so a failure on ANY of them is evidence about the SAME account-wide threshold), or
#: ``"<provider>:<model>"`` when the effective scope is model (a per-provider
#: ``…_TRANSIENT_SCOPE=model`` override, or a future model-scoped transient cause). Keying by the
#: LANE instead would dilute a provider-scoped threshold by however many models are in flight —
#: review round 1, fixup 2. Reset to 0 the instant a bench is actually written (a fresh grace
#: period starts once the lane is live again), and by ``reset_lane_state()``. Shared,
#: ``_lock``-guarded state, same as the two bench maps above.
_fail_count: dict[str, int] = {}
#: Per-provider in-flight caps, built lazily from the registry + env override.
_sems: dict[str, threading.Semaphore] = {}
#: Cursor for ``mode="rotate"``.
_rotate: dict[str, int] = {"i": 0}
#: Monotonic forward-progress counters. ``58-resilience`` § Provider-death outcome 3 wants an alarm
#: on ABSENCE OF PROGRESS, not on error codes — a stall is invisible for as long as it lasts because
#: zero progress is not an error. The engine SURFACES the signal; the consuming project wires the
#: alarm (threshold ≥ 2 full runs of its loop).
_progress: dict[str, int] = {"attempts": 0, "completions": 0, "defers": 0}
#: Last probe result: monotonic timestamp + the survivor set, for the optional TTL refresh.
_probe_state: dict[str, Any] = {"at": None, "healthy": None}
#: ONE lock covers every structure above — they are read and written together on each call, and
#: separate locks would let a bench land against a chain the cursor has already moved past.
_lock = threading.Lock()


class AllLanesExhaustedError(ConsultError):
    """Every lane failed or was benched and no backstop was configured.

    Raised rather than returning ``""`` — a silent empty completion is indistinguishable from a
    model that legitimately answered with nothing, and the caller cannot tell an outage from a
    result. The message names every lane and why it was unavailable.
    """


def _env_float(name: str, default: float) -> float:
    """Read a positive float from the env at CALL time. A malformed or non-positive value falls
    back to the default rather than raising: a typo in a cooldown must not take the chain down."""
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return default
    return val if val > 0 and val == val and val != float("inf") else default


def _env_int(name: str, default: int) -> int:
    """Read a non-negative int from the env at CALL time. Mirrors ``_env_float``'s defensive
    parsing — a malformed or negative value falls back to the default rather than raising.
    ``0`` is a valid, deliberate value (``SUBAGENT_LANE_FAIL_THRESHOLD=0``): it turns the grace
    period off entirely, i.e. back to benching on the first failure."""
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return default
    return val if val >= 0 else default


def _provider_limit(provider: str) -> int | None:
    """This provider's in-flight cap: the env override wins, else the registry row.

    ``SUBAGENT_<PROVIDER>_MAX_CONCURRENCY`` is the same knob the fan-out already documents; honouring
    it here means one setting bounds BOTH paths rather than a batch quietly exceeding the cap that
    the pool respects.
    """
    raw = os.getenv(f"SUBAGENT_{provider.upper()}_MAX_CONCURRENCY")
    if raw:
        try:
            val = int(raw)
            if val > 0:
                return val
        except (TypeError, ValueError):
            pass  # malformed override → fall through to the registry value
    return resolve_provider(provider).max_concurrency


def _semaphore(provider: str) -> threading.Semaphore | None:
    limit = _provider_limit(provider)
    if limit is None:
        return None
    with _lock:
        sem = _sems.get(provider)
        if sem is None:
            sem = _sems[provider] = threading.Semaphore(limit)
        return sem


def bench_remaining(provider: str, model: str | None = None) -> float:
    """Seconds until ``provider`` (or one of its models) is dialled again. ``0.0`` = available."""
    now = time.monotonic()
    with _lock:
        left = max(0.0, _bench_provider.get(provider, 0.0) - now)
        if model is not None:
            left = max(left, _bench_model.get((provider, model), 0.0) - now)
    return max(0.0, left)


def lane_progress() -> Mapping[str, int]:
    """A read-only snapshot of the monotonic progress counters.

    ``attempts`` — lanes dialled. ``completions`` — calls that returned text. ``defers`` — calls
    that ended with every lane unavailable. **Alarm on the absence of movement in ``completions``**,
    not on error codes: the permanent all-providers-down case produces no errors at all once every
    lane is benched, so an error-rate alarm stays silent through exactly the outage that matters
    (`58-resilience.md` § Provider-death, outcome 3). Returned as a proxy so a caller cannot mutate
    the engine's counters by editing what it was handed.
    """
    with _lock:
        return MappingProxyType(dict(_progress))


def reset_lane_state() -> None:
    """Clear bench maps, the failure-threshold counter, semaphores, the rotate cursor, the probe
    cache and the counters. For tests and long-lived hosts that want a deliberate re-probe; the
    state is in-process, so a fresh process starts clear anyway."""
    with _lock:
        _bench_provider.clear()
        _bench_model.clear()
        _fail_count.clear()
        _sems.clear()
        _rotate["i"] = 0
        _progress.update({"attempts": 0, "completions": 0, "defers": 0})
        _probe_state.update({"at": None, "healthy": None})


@dataclass(frozen=True)
class FailureCause:
    """The pure verdict ``classify`` reaches about one exception. Carries everything
    ``apply_bench`` needs to act, with no side effect baked in.

    ``scope`` says what a caller SHOULD bench: ``"provider"`` (account-scoped — every model of
    that provider is equally unavailable), ``"model"`` (this one model alone — its siblings are
    fine), or ``"none"`` (bench nothing, just try the next lane). ``permanent`` selects the DEAD
    cooldown over the transient one. ``status``/``retry_after`` are carried through from ``exc``
    so ``apply_bench`` never has to re-inspect it.

    ⚠️ ``scope="key"`` is what ``classify`` RETURNS for a 402 — it is technically a per-KEY
    verdict, not per-provider (see the design spec), but no key-scoped bench store exists yet.
    ``apply_bench`` deliberately falls back to the provider bench for it, visibly, rather than
    silently dropping the signal or baking the limitation into the classification itself — T07
    (which owns the applier) is explicit that collapsing this to ``"provider"`` here would make
    the future key-scoped fix invisible. Do not add a key-scoped store off this value without one.
    """

    cause: str
    scope: str
    status: int | None
    retry_after: float | None
    permanent: bool


def _is_priced_out(exc: BaseException) -> bool:
    """Our OWN ``provider.max_price`` ceiling, not a dead model — ``loop.py:65`` documents the
    live case (kimi-k2.5 ($2.025): 200 bare, 404 at ``max_price=1.5``, 200 at 3×), and
    ``_apply_max_price`` (``loop.py:40-48``) merges that ceiling into every priced model's outgoing
    body automatically, so this is the DEFAULT 404, not an edge case. Benching it as
    ``model-gone`` would blacklist a WORKING model for 900 s.

    Reuses the literal ``ledger.py:191`` discriminator (``"max price"``, lowercased-substring) so
    the two cannot diverge on wording — do not "improve" it.

    ``ConsultError`` has no ``.body`` attribute: per ``_client._raise_for_http``, a generic 4xx
    (incl. 404) puts the body IN THE MESSAGE (truncated to 300 chars), while ``AuthError``/
    ``TransientError`` put it in ``.partial`` (truncated to 500). Checked as two SEPARATE
    substring tests, never joined into one string first: joining with a separator can manufacture
    the marker across the boundary (a message ending "...max" + a partial starting "price...") on
    pure coincidence.

    ⚠️ The ``.partial`` read's ACTUAL reach, traced through ``classify``'s branch order — honestly,
    not aspirationally: ``AuthError`` (401/403) is short-circuited above this function entirely, and
    429/503/413 all return before reaching it, so of the classes that populate ``.partial``, only a
    **408** (``TransientError``, which falls through to the generic-4xx arm) ever arrives here with
    it non-empty. A 404 is always ``ConsultError`` with no ``.partial`` at all
    (``_client.py:398`` passes none). The read is still correct to keep — a future family or status
    could land here with the marker in ``.partial`` — but it is not, today, "every family".

    ⚠️ Guarded: `str(exc)` (and `.partial`, on a hostile subclass) can itself raise, and this is a
    NEW raise site on the failure-handling path — the old ``_bench`` never called ``str(exc)``. A
    secondary exception here would mask the original failure and take the lane walk down instead
    of advancing it, so any read failure falls back to ``False`` (the safe default: ``model-gone``).
    """
    try:
        message = str(exc)
        partial = str(getattr(exc, "partial", ""))
    except Exception:
        return False
    return "max price" in message.lower() or "max price" in partial.lower()


def classify(exc: BaseException) -> FailureCause:
    """Read the cause out of ``exc`` alone — PURE: no clock, no env, no lock, no module state.
    Same exception in, an equal ``FailureCause`` out, every time.

    The key (``FailureCause.scope``) is the whole point: a 429 is the ACCOUNT being throttled
    (every model of that provider is equally unavailable), while a 404/400 is one MODEL being gone
    (its siblings are fine). ``apply_bench`` is the only place any of this reaches a bench map.
    """
    status = getattr(exc, "status", None)

    if isinstance(exc, AuthError):
        return FailureCause("auth", "provider", status, None, True)

    # 402 Payment Required is an ACCOUNT verdict, not a model one: the free credit is spent, so
    # every model of that provider will answer identically. Benching one model would make the chain
    # burn a call per sibling model rediscovering the same wall. Found by a LIVE smoke test —
    # Mistral returned 402 and the offline suite had no such fixture, because nothing told me to
    # write one. Same cause string as AuthError: both are "this provider is closed to you", not
    # transient — but the SCOPE differs. A 402 is technically a per-KEY verdict, not per-provider
    # (unlike a bad credential, a second key on the same provider might not be broke), so this
    # returns ``scope="key"`` rather than collapsing it to ``"provider"`` — see the FailureCause
    # docstring for why ``apply_bench`` still benches the provider today.
    if status == 402:
        return FailureCause("auth", "key", status, None, True)

    if status in (429, 503):
        # `retry_after` is read HERE, and only here — the one arm that consumes it — the same
        # exposure the pre-split `_bench` had. It is a hostile-attribute read on an exception this
        # module did not author (same reasoning as `_is_priced_out`'s guard below), so it is not
        # read unconditionally for every exception that reaches `classify`.
        retry_after = getattr(exc, "retry_after", None)
        if not (isinstance(retry_after, (int, float)) and retry_after and retry_after > 0):
            retry_after = None
        cause = "rate-limited" if status == 429 else "unavailable"
        return FailureCause(cause, "provider", status, retry_after, False)

    if status == 413:
        # 413 is about OUR REQUEST, not the model — and on a free tier it is usually SELF-INFLICTED:
        # `call_model`'s one-shot empty-content bump raises `max_tokens` to `_EMPTY_BUMP_TOKENS`
        # (16000) after a first response arrives empty, and a small free tier rejects that outright.
        # Observed live on Groq's free tier with `openai/gpt-oss-20b`, whose reasoning arrives before
        # any content. Benching the MODEL for 15 minutes over a request WE malformed would take a
        # perfectly healthy lane out of the chain. Fall through to the next lane, bench nothing.
        return FailureCause("request-too-large", "none", status, None, False)

    if isinstance(status, int) and 400 <= status < 500:
        if _is_priced_out(exc):
            # OURS, not the model's (mirrors ledger.py:192) — re-route, bench nothing.
            return FailureCause("priced-out", "none", status, None, False)
        if status in (400, 422):
            # ⚠️ DELIBERATE CHANGE (review round 1, fixup 4; review round 2, fixup 5 + the 422
            # verdict) — a bare 400 used to fall through to `model-gone` below, on the reasoning
            # "a 404/400 is one MODEL being gone". That held while `lane_chain` owned the request
            # body; it stopped holding once `classify` was wired into `run_loop` (T02a), where
            # `extra_body` is a CALLER-supplied passthrough and the loop itself injects
            # `provider.max_price` + latency preferences. A malformed caller body 400s IDENTICALLY
            # for every model of that provider — proved live: `FailureCause(cause='model-gone',
            # scope='model', ..., permanent=True)` benched a perfectly healthy model for 900s over
            # a request WE malformed, and the cascade then burned each sibling rung rediscovering
            # the same 400. Exactly the 413 arm's reasoning above, carried onto this status: OUR
            # REQUEST, not the model — bench nothing, advance a rung.
            #
            # 422 joins it for the SAME reason (review round 2 asked the question explicitly
            # rather than letting it default): a 422 Unprocessable Entity means the server parsed
            # the request but rejected its SEMANTIC content — an invalid parameter value/shape,
            # not "the model is gone". Every model behind that provider would 422 identically on
            # the same malformed body, so benching just one would be exactly the 400 defect again.
            # Genuinely rarer 4xx codes (405/406/409/411/412/414/415/...) are left as `model-gone`
            # below — none have been observed live, and this ticket answers only the code the
            # review named, not every exotic 4xx.
            #
            # ⚠️ `cause` is its OWN string here, distinct from 413's `"request-too-large"` — that
            # string ships to `_bench`'s return value, the degradation-event name, and (T04) the
            # ledger's `failure_reason` column. Reusing 413's string for a "400 Bad Request" read
            # as a token-count problem to an operator debugging a run that actually died on a
            # malformed body — review round 2, fixup 5. `status` was ALREADY the only reliable
            # discriminator between 400/422 and 413; now `.cause` distinguishes them too.
            return FailureCause("bad-request", "none", status, None, False)
        return FailureCause("model-gone", "model", status, None, True)

    # 5xx, a transport/timeout error, or anything unclassified: try the next lane now, but do NOT
    # bench — a one-off blip must not cost the best provider its position for the next 15 minutes.
    return FailureCause("error", "none", status, None, False)


def _bench_scope_for(cause: FailureCause, provider: str) -> str:
    """The scope ``apply_bench`` actually writes to — ``cause.scope`` unless a provider-specific
    override applies.

    This module's own docstring (§ 2) asserts a 429 is the ACCOUNT being throttled: true for a
    per-account free tier, NOT true for a provider with PER-MODEL quotas — an assumption this
    ticket (T07) inherits rather than fixes. The provider scope stays the DEFAULT (right for the
    measured lanes); a provider can override it to ``"model"`` via
    ``SUBAGENT_<PROVIDER>_TRANSIENT_SCOPE=model``.

    Applies to every provider-scoped TRANSIENT cause (today: 429 ``"rate-limited"`` and 503
    ``"unavailable"``) — never to a PERMANENT one (401/402's ``scope="key"`` fallback stays
    provider-wide unconditionally; a closed account has no narrower interpretation) and never to
    ``scope="model"``/``"none"`` (nothing to override). Review round 1, fixup 3: the original gate
    covered 429 only, which was arbitrary — several vendors use 503 for the identical per-model
    overload signal, so an operator isolating one provider's throttling still got whole-provider
    benching on its 503s. Named ``…_TRANSIENT_SCOPE``, not ``…_429_SCOPE``, for exactly that
    reason — free to rename now, before T08 documents it and before anything vendors it.
    """
    if cause.scope == "provider" and not cause.permanent:
        override = os.getenv(f"SUBAGENT_{provider.upper()}_TRANSIENT_SCOPE", "").strip().lower()
        if override == "model":
            return "model"
    return cause.scope


def apply_bench(cause: FailureCause, provider: str, model: str) -> str:
    """Turn a pure ``classify`` verdict into the side effect, and name the cause.

    Every side effect ``_bench`` used to do lives here: the env-driven cooldowns, the
    ``min(..., max_cd)`` clamp, the ``max(existing, now+cooldown)`` monotonic extension, the lock.

    ⚠️ **T07's one deliberate departure from that "every side effect `_bench` used to do" claim:**
    a TRANSIENT cause (``permanent=False``) with something to bench no longer benches on the
    FIRST occurrence — see ``_DEFAULT_FAIL_THRESHOLD``. A PERMANENT cause (401/402/410/
    model-gone/…) still benches immediately, exactly as the old ``_bench`` always did; that path
    is untouched.

    ⚠️ **Concurrency (review round 1, fixup 1).** The increment, the threshold check, the counter
    reset and the bench write for the TRANSIENT arm all happen inside ONE ``_lock`` acquisition —
    not four separate ones. Four separate critical sections let two threads failing the SAME lane
    concurrently each read a sub-threshold count, each release, and both return unbenched where a
    sequential pair would have crossed the threshold; worse, the window between a reset and its
    bench write was briefly a state with no count AND no cooldown, so a third thread could start a
    fresh grace period against a lane that was already about to be benched. `subagents` runs under
    `run_agents` concurrency, which is exactly why `_bench_provider`/`_bench_model` were already
    ``_lock``-guarded — the counter added here inherits the same requirement.
    """
    if cause.scope == "none":
        return cause.cause

    scope = _bench_scope_for(cause, provider)

    if not cause.permanent:
        threshold = _env_int("SUBAGENT_LANE_FAIL_THRESHOLD", _DEFAULT_FAIL_THRESHOLD)
        # Keyed by the BENCH TARGET, not the lane (review round 1, fixup 2) — see `_fail_count`'s
        # own comment for why a provider-scoped cause counts failures across every model, not just
        # the one that happened to fail this time.
        key = provider if scope in ("provider", "key") else f"{provider}:{model}"
        with _lock:
            count = _fail_count.get(key, 0) + 1
            _fail_count[key] = count
            if count <= threshold:
                # Below the grace period: this lane is NOT benched — it stays in the walk for the
                # next call too. This is the behaviour change: the old `_bench` wrote the bench
                # right here, on the first failure, for every transient cause.
                return cause.cause
            _fail_count[key] = 0  # the bench about to be written starts a fresh grace period
            now = time.monotonic()
            max_cd = _env_float("SUBAGENT_LANE_MAX_COOLDOWN_S", _DEFAULT_MAX_COOLDOWN_S)
            base = (
                float(cause.retry_after)
                if cause.retry_after is not None
                else _env_float("SUBAGENT_LANE_COOLDOWN_S", _DEFAULT_COOLDOWN_S)
            )
            cooldown = min(base, max_cd)
            _write_bench_locked(scope, provider, model, now, cooldown)
        return cause.cause

    # PERMANENT: unchanged from before this ticket — bench on the first (and only) occurrence,
    # never counted against the transient threshold above.
    max_cd = _env_float("SUBAGENT_LANE_MAX_COOLDOWN_S", _DEFAULT_MAX_COOLDOWN_S)
    now = time.monotonic()
    dead = _env_float("SUBAGENT_LANE_DEAD_COOLDOWN_S", _DEFAULT_DEAD_COOLDOWN_S)
    cooldown = min(dead, max_cd)
    with _lock:
        _write_bench_locked(scope, provider, model, now, cooldown)
    return cause.cause


def _write_bench_locked(
    scope: str, provider: str, model: str, now: float, cooldown: float
) -> None:
    """The actual bench-map write, shared by both `apply_bench` arms. CALLER MUST ALREADY HOLD
    `_lock` — this never acquires it, so the transient arm can fold the write into its single
    increment/check/reset critical section (see `apply_bench`'s fixup-1 note) without a
    non-reentrant `threading.Lock` deadlocking on itself."""
    if scope in ("provider", "key"):
        # "key" has no store yet (see FailureCause docstring) — fall back to the provider bench
        # deliberately and visibly rather than silently dropping the signal.
        _bench_provider[provider] = max(_bench_provider.get(provider, 0.0), now + cooldown)
    elif scope == "model":
        _bench_model[(provider, model)] = max(
            _bench_model.get((provider, model), 0.0), now + cooldown
        )


def _bench(provider: str, model: str, exc: BaseException) -> str:
    """Bench the lane at the right key for the cause, and name that cause.

    Thin wrapper over the pure ``classify`` + side-effecting ``apply_bench`` split — kept as one
    call so the single call site below never has to know about the split.
    """
    return apply_bench(classify(exc), provider, model)


def _parse_lane(entry: object) -> tuple[str, str, float | None]:
    """One chain entry → ``(provider, model, cap)``.

    Accepts ``"provider:model"``, ``(provider, model)`` and ``(provider, model, cap)``. The string
    form splits on the FIRST colon only, because free-model ids legitimately contain one
    (``openrouter:deepseek/deepseek-chat:free``).
    """
    if isinstance(entry, str):
        provider, sep, model = entry.partition(":")
        if not sep or not provider.strip() or not model.strip():
            raise ValueError(
                f"lane {entry!r} is not 'provider:model' — e.g. 'groq:llama-3.3-70b-versatile'"
            )
        return provider.strip(), model.strip(), None
    if isinstance(entry, (tuple, list)) and len(entry) in (2, 3):
        provider, model = str(entry[0]).strip(), str(entry[1]).strip()
        cap = None
        if len(entry) == 3 and entry[2] is not None:
            cap = float(entry[2])
        if not provider or not model:
            raise ValueError(f"lane {entry!r} has an empty provider or model")
        return provider, model, cap
    raise ValueError(
        f"lane {entry!r} must be 'provider:model', (provider, model) or (provider, model, cap)"
    )


def _resolve_chain(chain: object) -> list[tuple[str, str, float | None]]:
    if chain is None:
        raw = os.getenv("SUBAGENT_LANES", "")  # read per call, never at import (12F-III)
        chain = [c.strip() for c in raw.split(",") if c.strip()]
    if isinstance(chain, (str, bytes, bytearray)):
        # `lane_chain(prompt, "groq:a")` is the natural typo; iterating a str yields characters and
        # would build a chain of letters — a total misconfiguration that returns a NON-empty chain.
        raise TypeError(
            "lane_chain: `chain` must be a sequence of lanes, not a single string "
            f"(got {type(chain).__name__}) — did you mean [{chain!r}]?"
        )
    if not isinstance(chain, Sequence):
        raise TypeError(f"lane_chain: `chain` must be a sequence, got {type(chain).__name__}")
    lanes = [_parse_lane(e) for e in chain]
    if not lanes:
        raise ValueError(
            "lane_chain: no lanes configured — pass `chain=[...]` or set SUBAGENT_LANES "
            "(comma-separated 'provider:model' entries)."
        )
    for provider, _, _ in lanes:
        resolve_provider(provider)  # fail LOUD on a bad chain BEFORE any paid call
    # Duplicate lanes collapse to their FIRST (best) position — the vendored `live_chain`'s rule
    # (`health_probe.py:331-333`): a chain naming the same rung twice is a config bug the caller
    # cannot see, and here it also BURNS FREE QUOTA, dialling the same provider+model twice for one
    # call. Dedup is on (provider, model): the same model at two different per-lane caps is still
    # one rung, and the first cap wins because the chain is quality-ordered.
    seen: set[tuple[str, str]] = set()
    deduped: list[tuple[str, str, float | None]] = []
    for lane in lanes:
        key = (lane[0], lane[1])
        if key not in seen:
            seen.add(key)
            deduped.append(lane)
    return deduped


#: Probe statuses that keep a provider in the chain. WARN is kept BY DESIGN — a degraded provider
#: still serves, and excluding it can empty a chain that would have worked.
_HEALTHY = frozenset({"OK", "WARN"})


def _probe_verdicts(
    probe: Callable[[], Iterable[Mapping[str, Any]]],
) -> tuple[set[str], dict[str, str]] | None:
    """Run the probe once and return the set of providers that may stay in the chain.

    **VENDORED, not imported** — this is `health-probe`'s `live_chain` semantics
    (`health-probe/health_probe.py:272-410`) reduced to the membership question this module asks.
    `subagents` must stay vendorable alone, so the logic is copied; the three load-bearing
    properties are copied with it:

    * **order is the CALLER's, never health's** — this returns a SET and the caller filters its own
      ordered chain, so a recovered provider returns to the front by itself. Promotion, not
      failover; no state to reset.
    * **an unprobed provider is DROPPED, not assumed healthy** — promoting an unprobed provider is
      the one thing a promotion must never do.
    * **a malformed probe row cannot crash the chain** — a non-str status (an unhashable list from
      a hostile probe) is treated as unhealthy rather than raising through `in frozenset`. A
      resilience helper that dies on bad input is worse than none.

    Returns ``None`` when the probe itself failed, meaning "no opinion" — the caller then uses the
    unfiltered chain. The probe is an optimisation over benching and must never become a NEW single
    point of failure.
    """
    try:
        rows = list(probe())
    except Exception:  # noqa: BLE001 — a broken probe must not take down a chain that works
        return None
    healthy: set[str] = set()
    reasons: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        name = row.get("system")
        if not isinstance(name, str) or not name:
            continue
        status = row.get("status")
        if not isinstance(status, str):
            # A non-str status (an unhashable list from a hostile probe) would RAISE through
            # `in frozenset`. Unhealthy, with a reason, never an exception.
            reasons[name] = f"probe status is {type(status).__name__}, not a string"
        elif status in _HEALTHY:
            healthy.add(name)
        else:
            raw = row.get("detail")
            detail = raw.strip() if isinstance(raw, str) else str(raw or "").strip()
            reasons[name] = f"status={status or '?'}" + (f": {detail[:120]}" if detail else "")
    return healthy, reasons


def _apply_probe(
    lanes: list[tuple[str, str, float | None]],
    probe: Callable[[], Iterable[Mapping[str, Any]]] | None,
    probe_ttl_s: float | None,
) -> tuple[list[tuple[str, str, float | None]], dict[str, str]]:
    """Filter the chain to probe-healthy providers, running the probe at most once per run (or per
    ``probe_ttl_s``). Never re-orders — see :func:`_healthy_from_probe`."""
    if probe is None:
        return lanes, {}
    now = time.monotonic()
    with _lock:
        at, verdicts = _probe_state["at"], _probe_state["healthy"]
        fresh = at is not None and (probe_ttl_s is None or (now - at) < probe_ttl_s)
    if not fresh:
        verdicts = _probe_verdicts(probe)
        with _lock:
            _probe_state["at"], _probe_state["healthy"] = time.monotonic(), verdicts
    if verdicts is None:  # probe errored → no opinion, use the chain as given
        return lanes, {}
    healthy, reasons = verdicts
    # A provider with NO probe result is dropped, never assumed healthy. It needs no entry here:
    # the caller reads `reasons` with a "no probe result" DEFAULT, so seeding one would be dead
    # code with no observable effect. (Mutation proved exactly that — deleting the seeding loop
    # changed nothing, because the default already covered it.)
    return [lane for lane in lanes if lane[0] in healthy], reasons


@dataclass(frozen=True)
class _LaneSpec:
    """The `spec` half of a flywheel row. `agent_record` reads whitelisted attributes off whatever
    it is handed (`ledger.py:153`), so a lane-shaped object records correctly without pretending to
    be an `AgentSpec`."""

    task: str
    model: str
    task_type: str = "lane"
    owned_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class _LaneRunResult:
    """The `result` half. `status="done"` matches the ledger's vocabulary."""

    agent_id: str
    provider: str
    cost_usd: float | None
    status: str = "done"
    turns: int = 1
    latency_s: float | None = None
    diff: str = ""
    error: str | None = None


def _order(lanes: list[tuple[str, str, float | None]], mode: str) -> list[tuple[str, str, float | None]]:
    if mode == "best_first":
        return lanes
    if mode == "rotate":
        with _lock:
            start = _rotate["i"] % len(lanes)
            _rotate["i"] = (start + 1) % len(lanes)
        return lanes[start:] + lanes[:start]
    raise ValueError(f"lane_chain: mode must be 'best_first' or 'rotate', got {mode!r}")


def _fill(sink: dict[str, Any] | None, **kw: Any) -> None:
    if sink is not None:
        sink.update(kw)


def lane_chain(
    prompt: str,
    chain: Any = None,
    *,
    mode: str = "best_first",
    backstop: Callable[[str], str] | None = None,
    sink: dict[str, Any] | None = None,
    probe: Callable[[], Iterable[Mapping[str, Any]]] | None = None,
    probe_ttl_s: float | None = None,
    project: str | None = None,
    run_fn: Callable[..., Result] | None = None,
    **opts: Any,
) -> str:
    """Run ``prompt`` through the first lane that answers; return the completion text.

    ``chain`` — lanes best-first: ``"provider:model"``, ``(provider, model)`` or
    ``(provider, model, cap)`` where ``cap`` is that lane's ``max_cost_usd``. Defaults to the
    comma-separated ``SUBAGENT_LANES`` env var, read at call time.

    ``mode`` — ``"best_first"`` (always start at position 0) or ``"rotate"`` (start one position
    further each call, to spread load across free quotas).

    ``backstop`` — ``Callable[[str], str]`` tried ONLY when every lane is exhausted. Without one,
    exhaustion raises :class:`AllLanesExhaustedError` — never a silent ``""``.

    ``sink`` — an optional dict filled on EVERY exit path (success, backstop, raise) with
    ``provider``/``model``/``attempts``/``benched``/``failures``/``cost_usd``/``reason``. This is the
    module's ``reason_sink`` idiom: provenance without forcing every caller to unpack a tuple. It
    never carries key material.

    ``probe`` / ``probe_ttl_s`` — accepted here, honoured in Phase C. Declared now so adding the
    behavior later is not a public-signature change.

    ``run_fn`` — the transport seam (defaults to :func:`_transport.run`); inject a fake for offline
    tests. ``**opts`` are forwarded to it unchanged.

    :raises AllLanesExhaustedError: every lane failed or was benched and no backstop was given.
    :raises ValueError: an unusable chain or mode. :raises UnknownProviderError: a bad provider.
    """
    call = run_fn if run_fn is not None else _transport.run

    # ── `**opts` COLLISION GUARD ──────────────────────────────────────────────────────────────
    # The README says opts are "forwarded to the transport unchanged", and three of the transport's
    # keywords are ALSO set by this function — so a caller doing the documented thing
    # (`lane_chain(p, chain, liveness=Liveness(hard_timeout_s=30))` to bound a 30-minute default,
    # or `max_cost_usd=` for a global ceiling) got `TypeError: got multiple values for keyword
    # argument`. Each is resolved by what it MEANS rather than by refusing all three:
    #   * `provider`/`messages` — owned by the chain itself; passing them is a genuine mistake, so
    #     fail LOUD naming the conflict instead of silently ignoring the caller's value.
    #   * `liveness` — the caller's wins, EXCEPT `restart_max`, which is forced to 0 because the
    #     no-retry property is load-bearing (see the module docstring) and not a caller's to relax.
    #   * `max_cost_usd` — becomes the DEFAULT ceiling; a per-lane 3-tuple `cap` still overrides it.
    for owned in ("provider", "messages"):
        if owned in opts:
            raise TypeError(
                f"lane_chain: `{owned}` is set per-lane by the chain and cannot be passed in "
                f"**opts — put it in the chain entry instead (e.g. ('groq', 'model'))."
            )
    caller_liveness = opts.pop("liveness", None)
    liveness = (
        replace(caller_liveness, restart_max=0)
        if isinstance(caller_liveness, Liveness)
        else Liveness(restart_max=0)
    )
    default_cap = opts.pop("max_cost_usd", None)

    all_lanes = _resolve_chain(chain)
    probed, probe_reasons = _apply_probe(all_lanes, probe, probe_ttl_s)
    if not probed:
        # Every candidate was probe-dead. RAISE naming them — returning a short/empty chain here
        # would hide an outage inside a normal-looking value (health-probe's own ruling).
        with _lock:
            _progress["defers"] += 1
        # Name the REASON per candidate, not just the candidate. "no chain" with no explanation
        # is exactly what the vendored original refuses to return.
        dead = "; ".join(
            f"{p}:{m} ({probe_reasons.get(p, 'no probe result')})" for p, m, _ in all_lanes
        )
        _fill(
            sink, provider=None, model=None, attempts=0, benched=[], failures=[],
            cost_usd=None, reason="all-lanes-probe-dead",
        )
        raise AllLanesExhaustedError(
            f"no candidate passed the health probe, so there is no chain to walk — {dead}"
        )
    lanes = _order(probed, mode)
    # Annotated, not inferred: `run` takes `list[dict[str, object]]`, and a bare literal infers as
    # `list[dict[str, str]]`, which mypy --strict rejects as invariant-incompatible.
    messages: list[dict[str, object]] = [{"role": "user", "content": prompt}]

    attempts = 0
    benched: list[str] = []
    failures: list[str] = []

    for provider, model, cap in lanes:
        if bench_remaining(provider, model) > 0:
            benched.append(f"{provider}:{model}")
            continue

        # ⚠️ MONEY ERRS TOWARD THE CAP. The joint monthly USD cap is enforced in `agent.py`
        # (`_cap_acquire`, :1215) on the AGENT dispatch path — it is NOT on the transport path this
        # walks, so a `lane_chain` call CANNOT reserve against it. Spending uncapped on a provider
        # whose operator explicitly configured a ceiling is the one outcome a cap exists to prevent,
        # so the lane is SKIPPED rather than dialled: unverifiable ⇒ refuse, the same direction as
        # `SUBAGENT_CAP_FAIL`'s fail-closed default. The rest of the chain still runs, and the
        # reason is named in the sink instead of being silent.
        cap_env = resolve_provider(provider).monthly_cap_env
        if cap_env and os.getenv(cap_env, "").strip():
            failures.append(f"{provider}:{model} (cap-unenforceable via {cap_env})")
            continue

        sem = _semaphore(provider)
        if sem is not None:
            sem.acquire()
        try:
            attempts += 1
            with _lock:
                _progress["attempts"] += 1
            t0 = time.monotonic()
            result = call(
                model,
                messages,
                provider=provider,
                liveness=liveness,  # restart_max forced to 0 — load-bearing, see the docstring
                max_cost_usd=cap if cap is not None else default_cap,
                **opts,
            )
        except ConsultError as exc:
            reason = _bench(provider, model, exc)
            # `exc` can quote an upstream body; keep only the status + our own reason token so a
            # logged sink can never carry a key an endpoint echoed back.
            status = getattr(exc, "status", None)
            failures.append(f"{provider}:{model} ({reason}{f', HTTP {status}' if status else ''})")
            continue
        finally:
            if sem is not None:
                sem.release()

        # ⚠️ AN EMPTY BODY IS A FAILURE, NOT AN ANSWER. The design spec is explicit (§ Lifecycle):
        # "an empty/unparseable body is a transient failure (defer + retry, never a silent
        # 0-result)". Returning "" as success is indistinguishable from a model that genuinely
        # answered nothing, and at batch scale that is silent zero-results by the thousand. The
        # AGENT path has `AgentResult.empty_output` for exactly this; the transport path has no such
        # marker, so the check lives here — the same "what the agent path does for you" class as the
        # spend cap and the free-tier $0 coercion. NOT benched: an empty body is transient, and
        # costing a provider its position for 15 minutes over one blank answer would be wrong.
        # ⚠️ TOOL CALLS COUNT AS OUTPUT. A model answering with only a tool call has EMPTY `text`
        # and is working perfectly — rejecting it would break every caller that forwards
        # `body={"tools": [...]}` through `**opts` (which the README says reaches the transport
        # unchanged). Empty means "no text AND no tool calls", not "no text".
        if not result.text.strip() and not result.tool_calls:
            failures.append(f"{provider}:{model} (empty-body)")
            continue

        cost = result.cost_usd
        if cost is None and resolve_provider(provider).free_tier:
            # A $0 endpoint that reported no cost really did cost $0. `agent.py`'s equivalent
            # coercion is on the AGENT path and operates on an `AgentResult`; this holds a
            # `_transport.Result` and never passes through it, so the rule is applied here or the
            # flywheel records "unknown" for exactly the providers this feature exists to use.
            cost = 0.0
        with _lock:
            _progress["completions"] += 1
        if project is not None:
            # OPT-IN, deliberately. The flywheel grades MODELS on TASKS; a 100k-item batch would
            # otherwise write 100k rows, which is not what it is for. Naming a project is the
            # caller saying "these calls are worth grading". `record_agent_run`, never `record_run`
            # — the latter wants a merged dict and silently no-ops on a result object.
            try:
                record_agent_run(
                    # ⚠️ The PROMPT IS NOT RECORDED. `agent_record` persists `task` to the shared
                    # fleet ledger, and its own redaction is credential-SHAPE based and explicitly
                    # "NOT a full secret scanner" (`ledger.py:34-41`). For `run_agents` the task is
                    # an instruction the caller wrote; a lane prompt is arbitrary user/document
                    # content, at batch volume — a different content class, and not ours to persist.
                    # The flywheel grades MODELS: `model` + `task_type` + `provider` + `cost_usd`
                    # are what it aggregates, and none of them need the prompt.
                    _LaneSpec(task=f"lane:{provider}", model=model),
                    _LaneRunResult(
                        agent_id=result.consult_id,
                        provider=provider,
                        cost_usd=cost,
                        # The agent path times its call (`agent.py` t0 -> result.latency_s); the
                        # transport path does not, so an unset value would leave every lane row
                        # latency-blind to the flywheel's own latency preferences.
                        latency_s=round(time.monotonic() - t0, 3),
                    ),
                    project=project,
                )
            except Exception:  # noqa: BLE001 — bookkeeping must never lose a paid-for completion
                pass
        _fill(
            sink,
            provider=provider,
            model=model,
            attempts=attempts,
            benched=benched,
            failures=failures,
            cost_usd=cost,
            reason="ok",
        )
        return result.text

    detail = "; ".join(failures + [f"{b} (benched)" for b in benched]) or "no lanes were tried"
    with _lock:
        _progress["defers"] += 1  # forward progress did NOT happen — the alarmable event
    if backstop is not None:
        # ⚠ The backstop call is GUARDED. It was not, and the sink stayed unfilled whenever the
        # backstop itself raised — while this function's public docstring promises the sink is
        # "filled on EVERY exit path (success, backstop, raise)". That promise ships to every
        # vendored copy, and the unfilled path is the WORST one: every lane dead AND the backstop
        # dead is exactly the total-outage moment a caller most needs provenance for. Found
        # 2026-09-02 by an adversarial review of a design that had just claimed this sink closed
        # its warning-channel hole.
        try:
            text = backstop(prompt)
        except BaseException:
            _fill(
                sink,
                provider=None,
                model=None,
                attempts=attempts,
                benched=benched,
                failures=failures,
                cost_usd=None,
                reason="backstop-failed",
            )
            raise
        _fill(
            sink,
            provider=None,
            model=None,
            attempts=attempts,
            benched=benched,
            failures=failures,
            cost_usd=None,
            reason="backstop",
        )
        return text

    _fill(
        sink,
        provider=None,
        model=None,
        attempts=attempts,
        benched=benched,
        failures=failures,
        cost_usd=None,
        reason="all-lanes-exhausted",
    )
    raise AllLanesExhaustedError(f"every lane is unavailable — {detail}")
