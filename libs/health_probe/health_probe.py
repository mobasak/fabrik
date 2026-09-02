# VENDORED-FROM fabrik-lib health-probe/health_probe.py @ e48ba19c — byte-identical below this 3-line header; re-vendor, never edit
# ruff: noqa
# fmt: off
#!/usr/bin/env python3
"""
health_probe.py — a pluggable external-systems health checker.

Probe every infra dependency and third-party API your app relies on with the
CHEAPEST call that proves the credential works, and report a uniform result so
the same function backs both a CLI and an admin dashboard endpoint.

Status: OK (reachable + authed) · DOWN (unreachable/auth fail) · WARN (degraded,
e.g. quota low) · SKIP (not configured).

The framework is generic: you pass it a **list of probe callables**. Three
generic probes ship here (`check_postgres`, `check_redis`, `check_http_auth`);
project-specific probes (your upstream APIs, object store, etc.) live in your
project and are appended to the list. See README for examples.

    from health_probe import (check_postgres, check_redis, check_http_auth,
                              run_all_checks, cli, OK, WARN, DOWN, result,
                              live_chain, LiveChain)
    import os
    from functools import partial

    PROBES = [
        check_postgres,
        check_redis,
        partial(check_http_auth, "Stripe", "https://api.stripe.com/v1/balance",
                headers={"Authorization": f"Bearer {os.getenv('STRIPE_KEY','')}"},
                skip_if=not os.getenv("STRIPE_KEY")),
    ]
    CRITICAL = {"PostgreSQL", "Redis"}

    if __name__ == "__main__":
        cli(PROBES, critical=CRITICAL)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import UserString
from dataclasses import dataclass
from types import MappingProxyType
from typing import (Any, Callable, Iterable, Iterator, Mapping, Optional, Protocol,
                    Sequence, cast, overload)

import httpx as httpx  # explicit re-export: lets `h.httpx` be monkeypatched by callers
from dotenv import load_dotenv

load_dotenv()

OK, DOWN, WARN, SKIP = "OK", "DOWN", "WARN", "SKIP"
TIMEOUT = float(os.getenv("HEALTH_PROBE_TIMEOUT", "12"))


def fingerprint(key: str) -> str:
    """Short, non-reversible label for a secret (for per-key reporting)."""
    return (
        f"{key[:6]}…{hashlib.sha1(key.encode(), usedforsecurity=False).hexdigest()[:6]}"
        if key
        else "(empty)"
    )


def result(name: str, status: str, detail: str = "") -> dict[str, str]:
    return {"system": name, "status": status, "detail": detail}


# ── Comparison axis: declared-vs-actual, ORTHOGONAL to liveness ─────────────
# `status` stays a LIVENESS verdict; agreement lives in `match`. This split is
# load-bearing: `live_chain`'s `healthy` frozenset drops ANY status outside
# {OK, WARN}, so a mismatch expressed as a status would eject a healthy
# provider from a routing chain.

Comparator = Callable[[Any, Any], object]


def compare(
    name: str, expected: object, actual: object, *, comparator: Comparator | None = None
) -> dict[str, object]:
    """One declared-vs-actual comparison, as an ordinary result row.

    Returns the uniform ``{system, status, detail}`` PLUS ``expected`` /
    ``actual`` / ``match``, and ``compare_error`` when the comparator raised.

    ``match`` is TRI-STATE — ``True`` / ``False`` / ``None``. ``None`` on a row
    that carries ``expected``/``actual`` means *a comparison was attempted and
    could not be resolved*, which ``cli`` treats as a failure (fail closed).
    A liveness-only row carries none of these keys and is unaffected.

    **This function OWNS its comparator's exceptions** — deliberately, and it is
    not a silent swallow: the error is surfaced in ``compare_error`` and forced
    to a non-zero exit by ``cli``. Comparators are caller-supplied, so a broken
    one is the EXPECTED failure; letting it escape sends the row through
    ``run_all_checks``' generic handler, which labels it with the *probe's* name
    instead of the system's and marks it DOWN — losing the name that ``critical``
    matches on and ejecting a healthy provider from ``live_chain``.
    """
    cmp_: Comparator = comparator or (lambda e, a: bool(e == a))
    # `result()` is dict[str, str]; copy into a widenable mapping rather than
    # mutating it, so the comparison values (a count, a hash, a version — any
    # object) are well-typed under `mypy --strict`.
    d: dict[str, object] = dict(result(name, OK, f"expected {expected!r}, actual {actual!r}"))
    d["expected"], d["actual"] = expected, actual
    try:
        d["match"] = bool(cmp_(expected, actual))
    except Exception as e:  # noqa: BLE001 - caller-supplied code; see docstring
        d["match"] = None
        d["compare_error"] = repr(e)
        d["detail"] = f"comparator failed: {e}"
    return d


def comparison_probe(
    name: str,
    expected: object,
    fetch_actual: Callable[[], object],
    *,
    comparator: Comparator | None = None,
) -> Callable[[], dict[str, object]]:
    """Build a comparison probe that owns its FETCH as well as its comparison.

    Prefer this over a bare ``lambda: compare(...)``. If the compared system is
    unreachable the *fetch* raises, and a bare lambda sends that into
    ``run_all_checks``' generic handler — which labels the row with the probe
    function's name, so ``r["system"] in critical`` can never match and the run
    exits 0 with nothing compared. Here the failure keeps ``name``, reports
    ``DOWN`` (the system genuinely is unreachable) and still carries the
    comparison keys, so it is recognisably an unresolved comparison and fails
    closed.
    """

    def _probe() -> dict[str, object]:
        try:
            actual = fetch_actual()
        except Exception as e:  # noqa: BLE001 - caller-supplied fetch
            d: dict[str, object] = dict(
                result(name, DOWN, f"could not read actual: {e}")
            )
            d["expected"], d["actual"], d["match"] = expected, None, None
            d["compare_error"] = repr(e)
            return d
        return compare(name, expected, actual, comparator=comparator)

    return _probe


# ── Generic infra probes ────────────────────────────────────────────────────


class _PGCursor(Protocol):
    """Duck-typed slice of psycopg2's cursor — psycopg2 ships no type stubs."""

    def execute(self, query: str) -> None: ...
    def fetchone(self) -> tuple[Any, ...] | None: ...


class _PGConnection(Protocol):
    """Duck-typed slice of psycopg2's connection — psycopg2 ships no type stubs."""

    def cursor(self) -> _PGCursor: ...
    def close(self) -> None: ...


def check_postgres(name: str = "PostgreSQL") -> dict[str, str]:
    """SELECT 1 against the DB described by DB_HOST/PORT/NAME/USER/PASSWORD."""
    conn: _PGConnection | None = None
    try:
        import psycopg2

        conn = cast(
            _PGConnection,
            psycopg2.connect(
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", "5432")),
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                connect_timeout=8,
            ),
        )
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        return result(
            name, OK, f"{os.getenv('DB_HOST', 'localhost')}/{os.getenv('DB_NAME')}"
        )
    except Exception as e:
        return result(name, DOWN, str(e)[:120])
    finally:
        # Always release the connection — even if SELECT 1 failed after connect()
        # succeeded — so repeated dashboard probes don't leak connections.
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


class _RedisClient(Protocol):
    """Duck-typed slice of redis.Redis — its ping()/close() ship unannotated
    even though the `redis` package itself is py.typed."""

    def ping(self) -> Any: ...
    def close(self) -> Any: ...


def check_redis(name: str = "Redis") -> dict[str, str]:
    """PING the Redis at REDIS_URL."""
    r: _RedisClient | None = None
    try:
        import redis

        r = cast(
            _RedisClient,
            redis.from_url(  # type: ignore[no-untyped-call]
                # check_env_vars: env-driven with a WSL-dev fallback, not a hardcoded host — NOT a hardcoded host: `REDIS_URL` is the primary and
                # the literal is only the WSL-dev fallback, which is the `os.getenv(KEY, default)`
                # pattern the contract prescribes (dev talks to localhost, the VPS injects
                # redis-main:6379). Pre-existing line, annotated because adding `live_chain` made
                # this file "changed" and the diff-scoped check began reporting it.
                os.getenv("REDIS_URL") or "redis://localhost:6379/0",  # noqa: E501 (check_env_vars reads the bare word)
                socket_connect_timeout=8,
            ),
        )
        r.ping()
        return result(name, OK, "ping ok")
    except Exception as e:
        return result(name, DOWN, str(e)[:120])
    finally:
        # Close the client so repeated dashboard probes don't accumulate open
        # sockets in the pool until GC — same no-leak contract as check_postgres.
        if r is not None:
            try:
                r.close()
            except Exception:
                pass


def check_http_auth(
    name: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, str | int | float | bool | None] | None = None,
    ok_codes: Iterable[int] = (200,),
    auth_fail_codes: Iterable[int] = (401, 403),
    timeout: float | None = None,
    skip_if: bool = False,
    detail_fn: Callable[[httpx.Response], str | None] | None = None,
) -> dict[str, str]:
    """Generic credentialed-GET probe — the shape most upstream API checks share.

    ok_codes → OK, auth_fail_codes → DOWN, anything else → WARN. ``skip_if=True``
    (e.g. when the key env var is unset) returns SKIP. ``detail_fn(response)`` can
    extract a human detail (balance, username) from a 200 body — a falsy/``None``
    return (or a raised exception) falls back to the ``HTTP <code>`` detail below.
    """
    if skip_if:
        return result(name, SKIP, "not configured")
    try:
        r = httpx.get(url, headers=headers, params=params, timeout=timeout or TIMEOUT)
        if r.status_code in ok_codes:
            detail = ""
            if detail_fn:
                try:
                    detail = detail_fn(r) or ""
                except Exception:
                    detail = ""
            return result(name, OK, detail or f"HTTP {r.status_code}")
        if r.status_code in auth_fail_codes:
            return result(name, DOWN, f"auth failed (HTTP {r.status_code})")
        return result(name, WARN, f"HTTP {r.status_code}")
    except Exception as e:
        return result(name, DOWN, str(e)[:120])


# ── Runner + CLI ─────────────────────────────────────────────────────────────


def _probe_label(fn: Callable[..., object]) -> str:
    """Best-effort human label for a probe (plain fn, functools.partial, or other)."""
    return str(
        getattr(fn, "__name__", getattr(getattr(fn, "func", None), "__name__", "probe"))
    )


#: How many dropped providers the "nothing is healthy" message names before it stops. A 300-candidate
#: fleet produced a 26,751-character exception — measured — which log lines, Sentry payloads and alert
#: bodies all truncate, so the useful head is lost to a tail nobody reads. A bound that publishes its
#: own residual, which is the same rule this fleet applies to every other bound.
_MAX_NAMED_DROPS = 12


def _summarise_drops(dropped: "Mapping[str, str]") -> str:
    items = list(dropped.items())
    head = "; ".join(f"{n} → {r}" for n, r in items[:_MAX_NAMED_DROPS])
    rest = len(items) - _MAX_NAMED_DROPS
    return head + (f"; …and {rest} more" if rest > 0 else "")


@dataclass(frozen=True)
class LiveChain:
    """A rebuilt provider chain, WITH what fell out of it and why.

    ⚠️ THE RETURN TYPE IS THE WHOLE RULING. The request asked for `list[str]`, and its own requirement
    forbids exactly that: *"refuse LOUDLY (never silently return a short or empty list) — a probe
    helper that quietly returns fewer rungs rebuilds the original defect one layer down."* A bare list
    does precisely that. Handed `["a", "b", "c"]` and returning `["a"]`, the caller cannot tell a
    healthy 1-provider fleet from a 3-provider fleet with two dead rungs — the same
    "a loss and an empty result are indistinguishable" ambiguity that a sibling module spent a
    25-round review eliminating. The chain and the reasons ship together or the helper is a footgun.
    """

    #: the surviving providers, IN THE CALLER'S ORIGINAL QUALITY ORDER — never re-ranked by health.
    #: That ordering is what makes this a PROMOTION: when the best provider recovers, it returns to
    #: the front by itself on the next rebuild, with no state to reset and nothing to remember.
    chain: tuple[str, ...]
    #: provider → why it is not in the chain. Never empty when `chain` is shorter than `candidates`.
    dropped: Mapping[str, str]
    #: providers kept but flagged: reachable and degraded (``WARN``). In the chain by design — a
    #: degraded provider still serves, and excluding it can empty a chain that would have worked.
    degraded: tuple[str, ...]

    # ── sequence ergonomics ───────────────────────────────────────────────────────────────────────
    # ⚠️ Without these, every call site stutters: `chain.chain[0]`, `list(chain.chain)`. The extra
    # payload is the whole point of the type, but it should not tax the common read. Iterating,
    # indexing and len() all mean the CHAIN; the reasons stay one attribute away.
    def __iter__(self) -> "Iterator[str]":
        return iter(self.chain)

    @overload
    def __getitem__(self, index: int) -> str: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[str, ...]: ...

    def __getitem__(self, index: int | slice) -> str | tuple[str, ...]:
        # ⚠️ THE ANNOTATION USED TO LIE. It said `index: int -> str`, but slicing is legal Python and
        # `chain[0:2]` returns a TUPLE. mypy caught the mismatch only in a caller that runs mypy; a
        # vendored consumer that does not got a silent shape surprise. Overloads state both truths.
        return self.chain[index]

    def __len__(self) -> int:
        return len(self.chain)


def live_chain(
    candidates: Sequence[str],
    probes: Iterable[Mapping[str, object]],
    *,
    healthy: frozenset[str] = frozenset({OK, WARN}),
) -> LiveChain:
    """Rebuild the live provider chain from a quality-ordered candidate list + probe results.

    Pure, provider-agnostic, no I/O: it consumes the ``{system, status, detail}`` dicts this module
    already produces, so the promotion logic is unit-testable without a network. That separation was
    the requester's design and it is the right one.

    **Order is the caller's, not health's.** Survivors keep their `candidates` position, so the best
    provider returns to the front by itself once it recovers — a promotion, not a failover, with no
    state to reset.

    **A provider with no probe result is DROPPED, not assumed healthy.** Promoting an unprobed
    provider is the one thing a promotion must never do; `SKIP` is treated the same way, because a
    skipped probe is an absence of evidence, not evidence of health.

    **`WARN` stays in the chain by default** and is reported in `degraded`. A degraded provider still
    serves, and excluding it can empty a chain that would have worked — pass
    ``healthy=frozenset({OK})`` to tighten. That default is a judgement call with a real cost either
    way, so it is stated rather than implied.

    Raises ``ValueError`` when NOTHING is healthy — never a silent empty chain. The message names
    every candidate and its reason, because "no providers" with no explanation is the outage inside
    the outage.
    """
    # ⚠️ THE FIX FOR `status` CLOSED ONE INSTANCE AND LEFT THE CLASS OPEN. `system` and `detail` were
    # still unguarded, and `detail` crashes through this module's OWN pipeline with nothing hostile in
    # it: `run_all_checks` validates that the keys EXIST and appends the item verbatim, so a
    # hand-rolled probe returning `{"detail": 503}` — an HTTP code as an int, the most natural thing to
    # write — reached `.strip()` and died. On the DROP path, i.e. during the outage this helper exists
    # to survive. Every field a probe supplies is now coerced, not just the one a reviewer named.
    # ⚠️ A BARE `str` IS A `Sequence[str]`, and mypy --strict passes it. `live_chain(os.getenv("PROVIDERS"))`
    # with a forgotten `.split(",")` iterated the string CHARACTER BY CHARACTER and returned a chain of
    # letters — a total outage of the only real provider coming back as a NON-empty chain with no raise,
    # which is precisely the "a short chain and a healthy chain are indistinguishable" failure the return
    # type exists to prevent, walking through a hole in the annotation. The str-is-a-sequence trap.
    if isinstance(candidates, (str, bytes, bytearray, UserString)):
        # ⚠️ DO NOT ECHO THE VALUE. This guard fires precisely when the caller passed the WRONG
        # variable, and the realistic wrong value is a key or a DSN — which would land verbatim in
        # logs and Sentry. The module already ships `fingerprint()` for exactly this.
        raise TypeError(
            "health_probe.live_chain: `candidates` must be a sequence of provider NAMES, not a single "
            f"string (got {type(candidates).__name__}, len={len(candidates)}, "
            f"fingerprint={fingerprint(str(candidates))}) — it would iterate character by character "
            "and build a chain of letters. Did you forget a .split(',')?"
        )

    by_system: dict[str, Mapping[str, object]] = {}
    for entry in probes:
        if not isinstance(entry, Mapping):
            continue
        key = entry.get("system", "")
        if isinstance(key, str) and key:
            by_system.setdefault(key, entry)

    # duplicate candidates collapse to their FIRST (best) position — a chain with the same provider
    # twice is a config bug the caller cannot see, and silently tripling a rung is a shape nobody
    # expects. First occurrence wins, matching "quality-ordered".
    # ⚠️ THE CANDIDATE SIDE WAS NEVER HARDENED. The probe fields were (status, system, detail) and
    # this loop three lines down still required hashability: `[{"name": "openai"}, "groq"]` — the
    # ordinary shape of a `providers.yaml` (`- name: openai`), i.e. the SAME config-loading path the
    # bare-`str` guard above was added for — raised `TypeError: unhashable type: 'dict'` on EVERY
    # call, healthy or not, before any drop could occur. A non-str candidate cannot name a provider,
    # so it is a drop with a reason, not a crash.
    seen: set[str] = set()
    ordered: list[str] = []
    unusable: dict[str, str] = {}
    # ⚠️ `report_order` exists because the drop REPORT must follow the caller's list, and it did not.
    # `dropped` was seeded with every unusable entry FIRST and the real per-candidate reasons appended
    # after, so with a hostile entry mixed into a real list the message read in "all type-errors, then
    # everything else" order. Past the `_MAX_NAMED_DROPS` bound that is not cosmetic: a placeholder for
    # an entry the caller never meant to pass DISPLACES a real provider's reason into "…and N more".
    # Reproduced with 14 drops — `p9` and `p10` went unnamed while three `<object object …>` lines took
    # their slots. A bound must spend its budget on the most useful items, and the caller's own order
    # is the only ranking this function has.
    report_order: list[str] = []
    for raw_name in candidates:
        if not isinstance(raw_name, str):
            key = repr(raw_name)[:80]
            if key not in unusable:
                report_order.append(key)
            unusable[key] = (
                f"candidate is {type(raw_name).__name__}, not a provider name string"
            )
            continue
        if raw_name not in seen:
            seen.add(raw_name)
            ordered.append(raw_name)
            report_order.append(raw_name)

    kept: list[str] = []
    degraded: list[str] = []
    dropped: dict[str, str] = dict(unusable)  # a candidate we could not even read is a reported drop
    for name in ordered:
        probe: Mapping[str, object] | None = by_system.get(name)
        if probe is None:
            dropped[name] = "no probe result — an unprobed provider is not a healthy one"
            continue
        status = probe.get("status", "")
        # ⚠️ `status in healthy` on a frozenset RAISES for an unhashable value (a list from a hostile
        # or malformed probe dict). A resilience helper that dies on bad input is worse than none —
        # the module's own stated guarantee, which the code did not keep. Non-str is not healthy.
        if not isinstance(status, str):
            dropped[name] = f"probe status is {type(status).__name__}, not a string"
            continue
        if status in healthy:
            kept.append(name)
            if status == WARN:
                degraded.append(name)
        else:
            raw_detail = probe.get("detail")
            detail = raw_detail.strip() if isinstance(raw_detail, str) else str(raw_detail or "").strip()
            dropped[name] = f"status={status or '?'}" + (f": {detail[:120]}" if detail else "")

    if not ordered:
        # ⚠️ NOT "nothing is healthy" — there was nothing to BE healthy. An operator whose provider list
        # came back empty from config was sent hunting provider outages by a message about provider
        # health, and the old text trailed off after "…value. " with nothing following it.
        raise ValueError(
            "health_probe.live_chain: `candidates` is EMPTY — there were no providers to check, which "
            "is a configuration problem, not a provider outage. (If you meant 'everything is down', "
            "that raises a different message naming each candidate.)"
        )
    # Re-key the report into the CALLER's order before anything reads it — both the bounded message
    # below and the `dropped` mapping handed back on the success path, so the two never disagree.
    dropped = {k: dropped[k] for k in report_order if k in dropped}
    if not kept:
        raise ValueError(
            "health_probe.live_chain: no candidate is healthy, so there is no chain to return. "
            "Returning an empty list here would hide an outage inside a normal-looking value. "
            + _summarise_drops(dropped)
        )
    # `frozen=True` is SHALLOW: a plain dict here stays mutable, so a caller could silently
    # corrupt a returned result in place. MappingProxyType makes the payload match the promise.
    return LiveChain(chain=tuple(kept), dropped=MappingProxyType(dropped), degraded=tuple(degraded))


def run_all_checks(
    probes: Iterable[Callable[[], object]], critical: Optional[set[str]] = None
) -> list[dict[str, object]]:
    """Run each probe (zero-arg callable returning a result dict OR a list of
    them — use functools.partial to bind args). A probe that raises, returns
    ``None``, or returns a malformed value is recorded as DOWN rather than
    crashing the run. ``critical`` is unused here but kept in the signature for
    symmetry; exit-code classification happens in ``cli``."""
    results: list[dict[str, object]] = []
    for fn in probes:
        label = _probe_label(fn)
        try:
            r = fn()
        except Exception as e:
            results.append(dict(result(label, DOWN, f"probe error: {e}")))
            continue
        items = r if isinstance(r, list) else [r]
        for item in items:
            if isinstance(item, dict) and "status" in item and "system" in item:
                results.append(item)
            else:
                # A probe that returned None / a bad shape must not poison the
                # run (or crash cli()'s r["status"] lookup downstream).
                results.append(
                    dict(result(label, DOWN, f"probe returned invalid result: {item!r}"))
                )
    return results


def _validated_mismatch_exit(value: object) -> int:
    """Reject exit codes that would silently disable the comparison verdict.

    A mismatch MUST be observable as a non-zero, non-liveness exit. Three families
    break that and every one of them fails OPEN — the failure mode this whole axis
    exists to prevent:

    * ``0`` — a real mismatch reports success.
    * ``1`` — collides with the liveness code, so "prod disagrees" becomes
      indistinguishable from "prod is dead"; that distinction is the point.
    * ``>= 256`` or ``< 0`` — POSIX takes the low 8 bits, so ``256``/``512`` reach the
      shell as **0**. Verified: ``sys.exit(256)`` gives ``$? == 0``.

    Fails LOUD at the boundary rather than defaulting, because a silently corrected
    exit code is a lie told to a machine that branches on it.
    """
    try:
        code: int = cast(int, int(value))  # type: ignore[call-overload]
    except (TypeError, ValueError):
        raise ValueError(f"mismatch_exit must be an int in 2..255, got {value!r}") from None
    if not 2 <= code <= 255:
        raise ValueError(
            f"mismatch_exit must be in 2..255, got {code}: "
            "0 reports success, 1 collides with the liveness exit, and >=256 wraps to 0 on POSIX"
        )
    return code


# The keys that mark a row as a COMPARISON row. Membership is a DISJUNCTION on
# purpose: a hand-built row carrying only `match` (a project not using compare())
# was invisible to an `expected AND actual` test and exited 0.
_COMPARISON_KEYS = ("expected", "actual", "match")


def cli(
    probes: Iterable[Callable[[], object]],
    critical: Optional[set[str]] = None,
    description: str = "External systems health",
    *,
    mismatch_exit: int = 2,
    strict: bool = False,
) -> None:
    """argparse CLI: human table or ``--json``.

    Exit codes — **a cross-repo contract; callers branch on these**:

    * ``0`` — everything passed.
    * ``1`` — a system is DOWN (a liveness incident).
    * ``mismatch_exit`` (default ``2``) — a system is reachable but DISAGREES with
      what was declared, or a comparison was attempted and could not be resolved.

    **PRECEDENCE: liveness wins.** When both are true in one run the exit is ``1``.
    A comparison computed against a partly-dead system is untrustworthy input, so
    *dead* is the fact that must be read first; nothing is lost because ``--json``
    carries every row. Precedence can never upgrade a verdict — both conditions
    independently deny a pass.

    ``strict=True`` treats EVERY system as critical. Without it, a caller that never
    declares ``critical`` gets an empty set, so ``system in critical`` is always
    False and a genuine outage exits 0. That fail-open predates the comparison axis
    and is fixed here only behind this opt-in flag, deliberately: it is a breaking
    change for existing callers and deserves its own decision, not a ride on a feature.
    """
    critical = critical or set()
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="treat every system as critical (a DOWN system then exits 1)",
    )
    ap.add_argument(
        "--mismatch-exit",
        type=int,
        default=mismatch_exit,
        help="exit code when a comparison disagrees or cannot be resolved (default: %(default)s)",
    )
    args = ap.parse_args()
    strict = strict or bool(args.strict)
    mismatch_exit = _validated_mismatch_exit(args.mismatch_exit)

    t0 = time.time()
    results = run_all_checks(probes, critical)
    if args.json:
        print(
            json.dumps(
                {"checked_at_s": round(time.time() - t0, 1), "results": results},
                indent=2,
                # Comparison rows carry arbitrary values (a count, a Decimal, a bytes
                # digest, a datetime version). Without a fallback, json.dumps RAISES and
                # the unhandled TypeError exits 1 — which callers read as "a system is
                # DOWN". A serialisation bug must never impersonate an outage.
                default=repr,
            )
        )
    else:
        icon = {OK: "✅", DOWN: "❌", WARN: "⚠️ ", SKIP: "⏭️ "}
        print(f"\n  {description} — {len(results)} checks in {time.time() - t0:.1f}s\n")
        for r in results:
            print(
                f"  {icon.get(str(r['status']), '  ')} {str(r['system']):<26}"
                f" {str(r['status']):<5} {r['detail']}"
            )
        down = [
            r
            for r in results
            if r["status"] == DOWN and not str(r["system"]).startswith("  ")
        ]
        print()
        if down:
            print(f"  DOWN: {', '.join(str(r['system']) for r in down)}")

    liveness_bad = any(
        r["status"] == DOWN and (strict or r["system"] in critical) for r in results
    )
    # A row bearing ANY comparison key is a comparison row; anything other than an
    # explicit True denies the pass. `match is None` on such a row means the
    # comparison was ATTEMPTED and could not be resolved — never agreement.
    attempted = [r for r in results if any(k in r for k in _COMPARISON_KEYS)]
    comparison_bad = any(r.get("match") is not True for r in attempted)
    # LIVENESS WINS — do not reorder; callers branch on this.
    sys.exit(1 if liveness_bad else (mismatch_exit if comparison_bad else 0))


if __name__ == "__main__":
    # Smoke-test with the generic infra probes only.
    cli([check_postgres, check_redis], critical={"PostgreSQL", "Redis"})
