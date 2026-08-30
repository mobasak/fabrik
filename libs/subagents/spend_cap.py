"""A JOINT monthly USD cap across ALL of a provider's API keys.

Four keys on one provider share ONE ceiling: ``MISTRAL_MONTHLY_CAP_USD=10`` means ten dollars
across all of them, never ten each. The cap is keyed by PROVIDER, which is what makes it joint —
and it means **no key material is ever PASSED to this module**: not a key, not a fingerprint, not
a prefix. Every entry point takes a provider name and an amount.

One qualification, because the stronger version of that sentence was written here first and was
not quite true: ``cap_env_value`` reads whatever environment variable it is pointed at, and the
name comes from operator configuration. Aim ``monthly_cap_env`` at ``MISTRAL_API_KEY`` by mistake
and this module holds a live credential in a local for as long as it takes to reject it. So the
guarantee is not "it can never touch one" — it is that a rejected cap **names the variable and
never echoes its contents**, and raises ``from None`` so the value cannot resurface through a
chained ``__cause__``. A module that is handed money figures should not be able to turn a
misconfiguration into a credential disclosure in the logs.

VENDORED — the PATTERN, not the tables
--------------------------------------
The atomic conditional upsert below is copied from ``cost-budget/cost_reservations.py``
(``_RESERVE_UPSERT`` / ``_LOCK_ROW`` / ``_MOVE_MONTH`` / ``_UPDATE_SETTLE`` / ``_UPDATE_ABANDON`` /
``_transition``), at the commit current on 2026-08-29. A future upstream fix should be a diffable
re-vendor of those statements.

What is deliberately NOT vendored is that module's SCHEMA, because it cannot express this feature:

* its monthly aggregate is keyed on ``month`` ALONE and its own schema comment calls it
  *"the app-global monthly spend aggregate (one row per month across ALL tenants) … cross-tenant BY
  DEFINITION"* — so a per-provider cap is impossible on it; two capped providers would share one row
  and the last caller's budget would decide;
* its ``tenant_id`` is ``uuid NOT NULL``, cast at three sites — a provider NAME cannot be passed.

Hence local tables keyed ``(provider, month)`` — see ``schema_spend_cap.sql``.

VENDORABLE-ALONE — this module imports NO ``cost_budget``/``cost_reservations`` at load. The async
connection is typed by the LOCAL structural Protocol below, and a real ``psycopg.AsyncConnection``
duck-types in. Same shape as ``deep-research``'s injected-Protocol precedent.

⚠️ THIS MODULE OWNS THE TRANSACTION ON THE CONNECTION YOU HAND IT
------------------------------------------------------------------
Every entry point ends in ``commit()`` or ``rollback()``. That is not incidental — the aggregate
increment and the reservation row MUST land together, and the settle trio must be atomic or a
crash between its statements strands the estimate forever (see ``_transition``). But it means
this module will commit, or discard, whatever else is pending on that connection.

**So pass a connection dedicated to the cap, not the one carrying your application's work.** A
consumer that reuses its request-scoped connection will have its own uncommitted writes committed
by a reservation, or rolled back by a refused one. Neither is recoverable and neither is visible
until it happens.

This is the cost of vendoring the source module's ``_commit_scope`` shape into a module that
cannot see its caller's transaction. It is stated here rather than defended against, because the
alternative — a savepoint — would make the atomicity above depend on the caller's outer
transaction actually committing, which this module has no way to guarantee.

MONEY DIRECTION — every choice here errs toward the cap, never away from it
---------------------------------------------------------------------------
* an unusable/unknown state REFUSES the spend rather than allowing it;
* a failure after money may have been spent RETAINS the estimate rather than releasing it;
* an unmatched or ambiguous read degrades to a refusal, never to a confident wrong answer.

Under-spending is recoverable by re-running. Over-spending is not.
"""

from __future__ import annotations

import logging
import os
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

log = logging.getLogger(__name__)

#: The scale of both money columns — numeric(16,6) and numeric(14,6).
_CENTS = Decimal("0.000001")

__all__ = [
    "CapExceededError",
    "CapRefusalError",
    "SpendCapTables",
    "SpendLedgerError",
    "abandon",
    "cap_env_value",
    "money",
    "reclaim_stale",
    "reserve",
    "settle",
]


# ── LOCAL structural Protocols (a real psycopg AsyncConnection duck-types in) ───────────────────


class _AsyncCursor(Protocol):
    #: READ-ONLY, declared as a property on purpose. Written as a plain ``rowcount: int``
    #: attribute, this Protocol demands a MUTABLE attribute — and psycopg's ``rowcount`` is a
    #: read-only property, so a real ``AsyncCursor`` fails to match and the whole Protocol stops
    #: describing the only class it was ever meant to describe.
    @property
    def rowcount(self) -> int: ...

    async def execute(self, sql: str, params: Any = ...) -> Any: ...
    async def fetchone(self) -> Any: ...
    async def fetchall(self) -> Any: ...


class _AsyncConnection(Protocol):
    #: ``*args``/``**kwargs`` mirrors psycopg's OVERLOADED ``cursor()`` (``binary=``,
    #: ``row_factory=``, a server-side ``name``).
    #:
    #: ⚠️ CORRECTED: this comment used to claim a bare ``def cursor(self)`` was REJECTED by mypy
    #: and that the widening was therefore load-bearing. A review ran the negative control and
    #: showed the bare form type-checks fine against psycopg 3.3.3 / mypy 1.19. What was actually
    #: load-bearing is the read-only ``rowcount`` property below (its negative control DOES fail).
    #: The widening is kept because it matches the real signature, but it is a convenience, not a
    #: requirement — and it does weaken the Protocol, which now admits any ``cursor()`` shape.
    def cursor(self, *args: Any, **kwargs: Any) -> AbstractAsyncContextManager[_AsyncCursor]: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...


class CapRefusalError(Exception):
    """Base: the spend was NOT authorised. Never raised after a paid call."""


class CapExceededError(CapRefusalError):
    """The reservation did not fit under the provider's monthly ceiling.

    Raised ONLY when the server confirmed the refusal — the conditional upsert returned no row.
    Every other failure (driver, connection, anything unrecognised) is a different, louder state:
    see the caller's ``cap-unverifiable`` handling. Conflating "over budget" with "database down"
    would make the fail-direction table meaningless.
    """


class SpendLedgerError(Exception):
    """The reservation and the aggregate disagree — a spend could not be recorded against any row.

    Raised when the month-move matches NO aggregate row, which means the ``(provider, month)`` the
    reservation belongs to is missing. Measured: with no such row, a settle of $9.00 against a
    $5.00 reservation marked the run ``settled`` and returned success while the month recorded
    NOTHING — four dollars of real spend erased from the cap, silently, in the one direction money
    must never err. The transaction is rolled back, so the reservation stays ``pending`` and the
    settle can be retried once the aggregate is repaired.
    """


class SpendCapTables:
    """The table names this module reads and writes — a NAMING record, not a rename hook.

    ⚠️ **Reassigning these at runtime does NOTHING, and the earlier docstring here claimed
    otherwise.** Every statement below is an f-string interpolated once, at import; by the time a
    consumer could set ``SpendCapTables.aggregate = "my_table"`` the SQL is already built against
    the original name. Verified by doing exactly that and re-reading ``_MOVE_MONTH``: it still
    targeted ``subagent_provider_spend``.

    That failure mode is worse than a plain limitation, because it is SILENT. A consumer who
    renames the attribute gets no error; their statements simply keep addressing the original
    tables. If those tables happen to exist too, the cap quietly maintains the wrong ones.

    To genuinely use different names in a vendored copy, **edit the two strings here** — you copied
    the file, editing it is the supported path — and keep ``schema_spend_cap.sql`` in step.
    """

    aggregate = "subagent_provider_spend"
    reservations = "subagent_spend_reservations"


# ── SQL — spelled out in full, deliberately ────────────────────────────────────────────────────
#
# Two clauses here look optional and are not. Both were reproduced against a live Postgres 16
# during this plan's review, and an abbreviated version of this statement was wrong twice:
#
#   ① the WHERE on the INSERT arm. Without it, `ON CONFLICT` never fires on an empty table, so a
#      FIRST-EVER reservation of $50 lands against a $10 cap. The source module carries the same
#      warning: "a bare VALUES would admit it even at a $0 kill-switch budget."
#   ② every `spent_usd` in the UPDATE arm must be TABLE-QUALIFIED. Unqualified, Postgres raises
#      `ERROR: column reference "spent_usd" is ambiguous` and the statement does not run at all.
#
# The `RETURNING`-only-if-it-fits shape is the correctness property: no row returned means the
# increment did not fit. That is how overshoot is made impossible across concurrent writers without
# a read-then-write race.
_RESERVE_UPSERT = f"""
    INSERT INTO {SpendCapTables.aggregate} (provider, month, spent_usd)
    SELECT %(p)s, %(m)s, CAST(%(est)s AS numeric)
     WHERE CAST(%(est)s AS numeric) <= CAST(%(budget)s AS numeric)
    ON CONFLICT (provider, month) DO UPDATE
       SET spent_usd = {SpendCapTables.aggregate}.spent_usd + CAST(%(est)s AS numeric)
     WHERE {SpendCapTables.aggregate}.spent_usd + CAST(%(est)s AS numeric)
           <= CAST(%(budget)s AS numeric)
    RETURNING spent_usd
"""

_INSERT_RESERVATION = f"""
    INSERT INTO {SpendCapTables.reservations} (job_id, provider, cost_usd, status, created_at)
    VALUES (%(j)s, %(p)s, CAST(%(est)s AS numeric), 'pending', %(now)s)
"""

#: Lock the per-run row and read the OLD figure, its provider, and the month it belongs to. Plain
#: text compare — `agent_id` is NOT a uuid, so the source's `CAST(%(j)s AS uuid)` must not be
#: carried over.
#:
#: ⚠️ `provider` is selected HERE, under the row lock, and not re-queried later. A second lookup
#: would have to answer "what if it misses?", and every answer is wrong: returning "" makes the
#: month-move's WHERE match zero rows, so the delta vanishes silently and the reservation is
#: released without the aggregate ever learning. One locked read cannot disagree with itself.
_LOCK_ROW = f"""
    SELECT cost_usd, provider, to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM')
      FROM {SpendCapTables.reservations}
     WHERE job_id = %(j)s
       FOR UPDATE
"""

#: ⚠️ BOTH keys. The source filters on `month` alone because its aggregate has no provider column;
#: against a (provider, month) table that predicate matches EVERY provider's row for the month, so a
#: single settle would move all of them.
_MOVE_MONTH = f"""
    UPDATE {SpendCapTables.aggregate}
       SET spent_usd = spent_usd + CAST(%(delta)s AS numeric)
     WHERE provider = %(p)s AND month = %(m)s
"""

_UPDATE_SETTLE = f"""
    UPDATE {SpendCapTables.reservations}
       SET cost_usd = CAST(%(new)s AS numeric), status = 'settled'
     WHERE job_id = %(j)s AND status = 'pending'
"""

_UPDATE_ABANDON = f"""
    UPDATE {SpendCapTables.reservations}
       SET cost_usd = CAST(%(new)s AS numeric), status = 'abandoned'
     WHERE job_id = %(j)s AND status = 'pending'
"""

#: Per-row savepoints, so ONE unreleasable row cannot discard the whole batch's releases.
_ROW_SAVEPOINT = "SAVEPOINT spend_cap_row"
_RELEASE_ROW_SAVEPOINT = "RELEASE SAVEPOINT spend_cap_row"
_ROLLBACK_TO_ROW = "ROLLBACK TO SAVEPOINT spend_cap_row"

#: The reclaim sweep: stale 'pending' rows. SKIP LOCKED so a concurrent settle is never fought over.
#:
#: SELECTION is by AGE; the PROCESSING order is by provider (see ``_lock_order`` below). The two
#: orderings answer different questions and collapsing them into one gets a different thing wrong:
#:
#: * ``ORDER BY created_at`` here keeps the sweep AGE-FAIR. Ordering the selection by provider
#:   instead would mean a provider whose name sorts early, holding more stale rows than ``limit``,
#:   fills every batch — and an older reservation for a late-sorting provider waits behind newer
#:   ones, with its money held the whole time.
#: * Sorting the SELECTED rows by provider before touching aggregates is the DEADLOCK guard. This
#:   is the only entry point that holds more than one aggregate-row lock at a time (it accumulates
#:   them across the loop and releases none until the final commit), so it is the only one that can
#:   be both sides of an AB-BA cycle. Under ``SKIP LOCKED`` two concurrent sweeps split the stale
#:   set arbitrarily: one can hold P1 and want P2 while the other holds P2 and wants P1. Taking the
#:   aggregate locks in provider order makes that cycle impossible for ANY two sweeps, because a
#:   consistent order over a shared resource set admits no cycle.
#:
#: ``LIMIT`` bounds the transaction. Without it a missed sweep (an outage, a deploy gap) leaves a
#: backlog that the next run locks ENTIRELY in one transaction — and because these locks are held
#: to the end, a legitimate settle whose run crosses the cutoff mid-sweep blocks on ``_LOCK_ROW``
#: (a plain ``FOR UPDATE``, no SKIP LOCKED) for the whole duration, not merely for its own row.
_SELECT_STALE = f"""
    SELECT job_id, provider, cost_usd, to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM')
      FROM {SpendCapTables.reservations}
     WHERE status = 'pending' AND created_at < %(cutoff)s
     ORDER BY created_at
     LIMIT %(limit)s
       FOR UPDATE SKIP LOCKED
"""


def money(value: Any, *, field: str = "amount") -> Decimal:
    """Coerce to a NON-NEGATIVE, finite ``Decimal`` — the ONE place float meets numeric.

    ``AgentResult.cost_usd`` and ``AgentSpec.max_cost_usd`` are ``float``; both tables are
    ``numeric`` and the delta arithmetic is ``Decimal``. Mixing them raises
    ``TypeError: unsupported operand type(s) for -: 'float' and 'decimal.Decimal'`` — hit while
    verifying this design against a live Postgres.

    ``Decimal(str(x))``, never ``Decimal(float)``: the latter carries binary float error into money.

    ⚠️ **Negative is rejected, and that is a money-safety guard, not tidiness.** Every amount that
    reaches this function is a spend — an estimate, an actual, a checkpoint — and a spend cannot be
    below zero. A negative one is not merely wrong, it INVERTS the cap: reserving ``-5000`` against
    a $10 ceiling passes the conditional upsert (``-4990 <= 10``), drives the aggregate to
    ``-4990``, and every reservation for the rest of the month then fits trivially. The cap would
    still be there, still be checked, and enforce nothing.

    Note this constrains the AMOUNTS only. The month-move DELTA is computed downstream
    (``new_cost - old_cost``) and is legitimately negative on every settle that came in under
    estimate — it never passes through here.
    """
    try:
        out = Decimal(str(value))
        if out.is_finite():
            # ⚠️ INSIDE the try. Quantizing a value at/above ~1e22 raises InvalidOperation, which
            # is an ArithmeticError and NOT a ValueError — so it bypassed `cap_env_value`'s
            # handler (losing the variable name and the no-echo guarantee) and propagated an
            # unexpected type out of `_cap_estimate` into the batch's gather.
            out = out.quantize(_CENTS)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field} is not a usable money value: {value!r}") from exc
    if not out.is_finite():
        raise ValueError(f"{field} must be finite, got {value!r}")
    if out < 0:
        raise ValueError(f"{field} must not be negative, got {value!r}")
    # (Quantization to the columns' numeric(_,6) scale happens above, inside the try: Postgres
    # rounds on assignment anyway, so an unquantized value makes the delta arithmetic use a figure
    # the DB never stored, and the aggregate drifts from the sum of reservations.)
    return out


def _require_aware(now: datetime, *, field: str) -> datetime:
    """Reject a naive datetime, because the two halves of this module would read it differently.

    ``_month_of`` resolves a naive value using the PROCESS's local zone, while the same value
    written to a ``timestamptz`` column is resolved using the DATABASE SESSION's ``TimeZone``. When
    those disagree, ``reserve`` increments one ``(provider, month)`` row and the later ``settle``
    — which derives the month server-side from ``created_at`` — moves a DIFFERENT one. The
    reservation is released from a month that never held it and the original month keeps the
    estimate forever. Nothing downstream can detect this, so it is refused at entry.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError(
            f"{field} must be timezone-aware — a naive datetime resolves differently in Python "
            f"than in Postgres, which silently splits the month aggregate: {now!r}"
        )
    return now


def cap_env_value(cap_env: str | None) -> Decimal | None:
    """The provider's monthly ceiling from env, or ``None`` when no cap is configured.

    Read-only ``os.getenv`` — never a default, never a fetch. A cap is an explicit operator opt-in;
    absence means "this provider is uncapped" and its dispatch path must not change at all.

    A cap that is SET but unparseable is NOT treated as absent — that would silently uncap a
    provider the operator meant to bound, which is the failure this whole module exists to prevent.
    It raises, at entry, before any paid call.
    """
    if not cap_env:
        return None
    raw = os.getenv(cap_env)
    if raw is None:
        return None
    if not raw.strip():
        # PRESENT but EMPTY. The value stays "uncapped" — `VAR=` is a widespread convention for
        # unset, and failing loud on it would break deployments that legitimately export empties.
        # But it is NOT silent: somebody wrote this variable down, so the likeliest reading is a
        # config mistake, and silently running a provider uncapped is exactly the outcome this
        # module exists to prevent. The objection is to the SILENCE, not to the semantic.
        log.warning(
            "subagent_cap_env_blank %s is set but EMPTY — treating the provider as UNCAPPED. "
            "If a cap was intended, give it a value; if not, unset the variable.",
            cap_env,
        )
        return None
    try:
        return money(raw, field=cap_env)
    except ValueError as exc:
        # ⚠️ Re-raised WITHOUT the value. `money()` echoes what it rejected — right for an
        # argument the caller already holds, wrong for the contents of an environment variable
        # this module did not choose. `monthly_cap_env` is operator-configured, and pointing it at
        # the wrong var (say `MISTRAL_API_KEY`) would otherwise print that key verbatim into an
        # exception and every log that catches it. A module whose whole premise is "no key
        # material ever reaches it" must not have a misconfiguration that turns it into a
        # credential disclosure. Naming the variable is enough to diagnose; its value never is.
        raise ValueError(
            f"{cap_env} is not a usable monthly cap (value not shown — it may not be a cap at "
            f"all): expected a non-negative decimal amount of USD, e.g. '10' or '2.50'. "
            f"[{type(exc).__name__}]"
        ) from None


def _cell(row: Any, index: int, name: str) -> Any:
    """Read one column positionally OR by name.

    ⚠️ The row factory belongs to the CALLER's connection, and these are PUBLIC entry points that
    take that connection. A consumer who connects with ``row_factory=dict_row`` — entirely
    reasonable, and nothing here forbade it — would otherwise have every money path break:
    ``row[0]`` raises ``KeyError(0)``, and tuple-unpacking a dict yields its KEYS, so
    ``money('cost_usd')`` raises and the whole sweep rolls back forever. The failure direction is
    safe (nothing is released) but the cap is silently non-functional for that consumer, in a
    module that ships by being copied into ~46 repos. Supporting both shapes costs three lines.
    """
    if hasattr(row, "keys"):
        return row[name]
    return row[index]


def _lock_order(row: Any) -> tuple[str, str]:
    """The aggregate-lock key ``(provider, month)`` for a stale row — the sweep's processing order.

    Kept as a named function rather than an inline lambda so the deadlock guard has somewhere to be
    explained and something to be tested by name.
    """
    return (str(_cell(row, 1, "provider")), str(_cell(row, 3, "to_char")))


def _month_of(now: datetime) -> str:
    return now.astimezone(UTC).strftime("%Y-%m")


async def reserve(
    conn: _AsyncConnection,
    *,
    provider: str,
    job_id: str,
    estimate_usd: Any,
    monthly_cap_usd: Any,
    now: datetime,
) -> None:
    """Authorise ``estimate_usd`` against the provider's joint monthly ceiling, or refuse.

    Raises :class:`CapExceededError` ONLY on a server-confirmed refusal (the upsert returned no row).
    Any driver/connection error propagates unchanged so the caller can tell it apart — that
    distinction is the whole of the fail-direction contract.

    The aggregate move and the per-run row are written in ONE transaction: a reservation recorded
    without its aggregate increment (or vice versa) is a ledger that lies.
    """
    est = money(estimate_usd, field="estimate_usd")
    cap = money(monthly_cap_usd, field="monthly_cap_usd")
    if cap == 0:
        # A $0 cap is a KILL SWITCH, and the README publishes it as one. The agent seam refuses it
        # early (without opening a connection), but `reserve` is PUBLIC API for anyone vendoring
        # this module — and left to the upsert, `0 <= 0` admits a zero-estimate run whose ACTUAL
        # can still be billed. One branch guarded and its sibling not is the pattern this review
        # kept finding; this closes it at the layer consumers actually call.
        raise CapExceededError(
            f"provider {provider!r} monthly cap is 0 — a zero cap is a kill switch; "
            f"nothing is authorised"
        )
    month = _month_of(_require_aware(now, field="now"))
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                _RESERVE_UPSERT,
                {"p": provider, "m": month, "est": str(est), "budget": str(cap)},
            )
            if await cur.fetchone() is None:
                await conn.rollback()
                raise CapExceededError(
                    f"provider {provider!r} monthly cap {cap} cannot fit an estimate of {est} "
                    f"for {month}"
                )
            # A duplicate job_id raises here, AFTER the aggregate was incremented in this same
            # transaction. The rollback below is what stops a retry from charging the month twice
            # for a run that was never reserved — without it the increment sits in an aborted
            # transaction on a connection the caller will reuse.
            await cur.execute(
                _INSERT_RESERVATION,
                {"j": job_id, "p": provider, "est": str(est), "now": now},
            )
        await conn.commit()
    except CapExceededError:
        raise  # already rolled back; re-raising must not double-rollback
    except Exception:
        await conn.rollback()
        raise


async def _transition(
    conn: _AsyncConnection, *, job_id: str, new_cost: Decimal, update_sql: str
) -> bool:
    """Move a pending reservation to its terminal state and the month by the DELTA.

    ⚠️ TWO things make this correct, and both were established by executing a crash rather than
    reasoning about one:

    * **The month move is gated on the status UPDATE's ``rowcount``, in Python.** If it affected 0
      rows the run was already settled, and moving the month anyway double-counts on every retry.
      An SQL-only port drops this gate silently.
    * **All three statements share ONE transaction.** Split across two, a crash between the status
      flip and the month move leaves the row ``settled`` while the month still holds the full
      estimate — and the retry's rowcount gate then skips the move FOREVER. The gate that makes a
      retry safe is exactly what makes a split-transaction crash unrecoverable. Measured.

    Returns False when there was nothing pending to transition (an idempotent no-op).
    """
    try:
        async with conn.cursor() as cur:
            await cur.execute(_LOCK_ROW, {"j": job_id})
            row = await cur.fetchone()
            if row is None:
                await conn.rollback()
                return False
            old_cost = money(_cell(row, 0, "cost_usd"), field="cost_usd")
            provider = str(_cell(row, 1, "provider"))
            month = str(_cell(row, 2, "to_char"))
            await cur.execute(update_sql, {"new": str(new_cost), "j": job_id})
            if cur.rowcount == 0:  # already terminal — a second call must NOT move the month
                await conn.rollback()
                return False
            await cur.execute(
                _MOVE_MONTH,
                {"delta": str(new_cost - old_cost), "p": provider, "m": month},
            )
            if cur.rowcount == 0:
                # No aggregate row for this (provider, month) — the spend has nowhere to land.
                # Silently succeeding here loses real money from the cap; see SpendLedgerError.
                # NOTE: raise only — the enclosing `except Exception` below owns the rollback.
                # Rolling back here too would roll back TWICE, which is the identical defect
                # already fixed once in reserve(); the early-RETURN paths above must roll back
                # themselves precisely because they do not raise.
                raise SpendLedgerError(
                    f"no {SpendCapTables.aggregate} row for provider={provider!r} "
                    f"month={month!r}: cannot record the spend for job {job_id!r}"
                )
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    return True


async def settle(
    conn: _AsyncConnection, *, job_id: str, actual_usd: Any
) -> bool:
    """``pending → settled`` at the true actual; the month moves by ``actual − estimate``.

    Idempotent: a second settle is a no-op, which is what makes a retried ``finally`` safe.
    """
    return await _transition(
        conn, job_id=job_id, new_cost=money(actual_usd, field="actual_usd"),
        update_sql=_UPDATE_SETTLE,
    )


async def abandon(
    conn: _AsyncConnection, *, job_id: str, checkpoint_usd: Any = 0
) -> bool:
    """``pending → abandoned`` at the CHECKPOINT figure — NOT an unconditional zero.

    A run that spent $0.25 of a $0.29 reservation keeps $0.25; the month drops by
    ``estimate − checkpoint``. Zero is the true full refund ONLY when no paid call can have
    happened. Passing 0 for a run that may still be billing is how spend becomes invisible to the
    cap — see the caller's backstop-timeout handling.
    """
    return await _transition(
        conn, job_id=job_id, new_cost=money(checkpoint_usd, field="checkpoint_usd"),
        update_sql=_UPDATE_ABANDON,
    )


async def reclaim_stale(
    conn: _AsyncConnection,
    *,
    cutoff: datetime,
    limit: int = 500,
    reason_sink: list[str] | None = None,
) -> int:
    """Release reservations left ``pending`` past ``cutoff``. Returns how many were reclaimed.

    ``limit`` bounds ONE sweep's transaction — see ``_SELECT_STALE`` for why an unbounded sweep
    blocks live settles. **The bound publishes its residual:** when the sweep fills its limit,
    ``sweep-truncated`` is appended to ``reason_sink`` (the module-family idiom from
    ``pg_ledger``) and a warning is logged, because a caller that reads only the returned count
    cannot distinguish "released 500, done" from "released 500, and 4,000 are still held". A
    truncated sweep is not an error — run it again — but a silent one would let a backlog grow
    while the number looked healthy.

    The residual signal is a lower bound, not an exact one: ``SKIP LOCKED`` drops rows a concurrent
    settle happens to hold, and those never count toward ``limit``. So under heavy contention the
    sweep can come back short while stale rows remain, and stay quiet. That is the harmless
    direction — the rows it skipped are ones another transaction is actively finalising, not
    orphans — and the next sweep picks up whatever is genuinely stranded.

    ⚠️ ``cutoff`` MUST exceed the caller's outer wall-clock backstop. This sweep releases money, so
    reclaiming a run that is STILL EXECUTING would hand its budget to someone else while the money
    is going out the door. The age gate is the whole safety property, exactly as the worktree GC
    this is modelled on is age-gated "so a live concurrent batch is never touched".

    Without a caller this function is decorative: ``reclaim`` is caller-scheduled and does not
    self-invoke, so a retained estimate would otherwise accumulate until the provider refuses
    everything for the rest of the month — a cap that ratchets shut while looking like it works.

    ⚠️ **THE ONE PLACE THIS MODULE'S MONEY DIRECTION IS NOT AIRTIGHT — stated, not hidden.** This
    sweep releases at $0, which is right for its intended subject: a run that died without
    spending. It is WRONG for a run that finished, actually spent, and whose ``settle`` raised at
    ``commit()`` — the money left the building, the reservation is still ``pending``, and this
    sweep will eventually refund it in full. The estimate is not merely under-retained, it is
    released, which is the opposite of the rule above.

    It is left this way deliberately: making the sweep RETAIN instead would mean a genuinely dead
    run never returns its budget, and the cap ratchets shut — a worse and far likelier failure.
    The real defence is at the caller: **a ``settle`` that raises must be retried, not dropped.**
    A retry is safe and idempotent (the ``status='pending'`` guard makes a second settle a no-op),
    so the cost of retrying is nil and the cost of giving up is a silently under-recorded spend.
    """
    _require_aware(cutoff, field="cutoff")
    if limit < 1:
        raise ValueError(f"limit must be at least 1, got {limit!r}")
    reclaimed = 0
    quarantined: list[str] = []
    stale: list[Any] = []
    try:
        async with conn.cursor() as cur:
            await cur.execute(_SELECT_STALE, {"cutoff": cutoff, "limit": limit})
            selected = await cur.fetchall() or []
            # Age-fair SELECTION above; provider-ordered PROCESSING here — the deadlock guard.
            # Sorting the already-locked subset is enough: any two sweeps then take the aggregate
            # locks they share in the same relative order, which is what forbids an AB-BA cycle.
            stale = sorted(selected, key=_lock_order)
            for row in stale:
                if await _release_one(cur, row, quarantined):
                    reclaimed += 1
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    if quarantined:
        if reason_sink is not None:
            reason_sink.append("rows-quarantined")
        log.warning(
            "subagent_spend_cap_quarantined count=%d jobs=%s — these reservations could not be "
            "released (no %s row for their (provider, month), or the release itself failed) and "
            "were SKIPPED, not released; the rest of the sweep committed normally.",
            len(quarantined), quarantined[:5], SpendCapTables.aggregate,
        )
    if len(stale) >= limit:
        # The sweep filled its bound, so there is almost certainly more still held.
        if reason_sink is not None:
            reason_sink.append("sweep-truncated")
        log.warning(
            "subagent_spend_cap_sweep_truncated limit=%d reclaimed=%d — more reservations may "
            "still be held; run the sweep again",
            limit, reclaimed,
        )
    return reclaimed


async def _release_one(cur: _AsyncCursor, row: Any, quarantined: list[str]) -> bool:
    """Release ONE stale reservation, bracketed by its own savepoint. True ⇒ it was released.

    ⚠️ The savepoint brackets the WHOLE row, exceptions included — not only the "matched no
    aggregate row" case. A release that RAISES (its delta would drive the aggregate below zero and
    trip the non-negative CHECK, which the schema's self-heal block makes reachable on deployments
    that previously had no constraint) would otherwise abort the entire batch, discarding every
    legitimate release in it. And because selection is age-ordered, that same row is re-selected on
    every future sweep: the release path wedges PERMANENTLY, which is exactly the failure the
    quarantine exists to prevent — one level deeper than the first version handled.
    """
    await cur.execute(_ROW_SAVEPOINT)
    job_id = str(_cell(row, 0, "job_id"))
    try:
        provider = str(_cell(row, 1, "provider"))
        cost_usd = _cell(row, 2, "cost_usd")
        month = str(_cell(row, 3, "to_char"))
        await cur.execute(_UPDATE_ABANDON, {"new": "0", "j": job_id})
        if cur.rowcount == 0:
            # Already terminal — a concurrent settle won it. Nothing to release, not an error.
            await cur.execute(_RELEASE_ROW_SAVEPOINT)
            return False
        await cur.execute(
            _MOVE_MONTH,
            {"delta": str(-money(cost_usd, field="cost_usd")), "p": provider, "m": month},
        )
        if cur.rowcount == 0:
            raise SpendLedgerError(
                f"no {SpendCapTables.aggregate} row for provider={provider!r} month={month!r}"
            )
    except Exception as exc:  # noqa: BLE001 — quarantine this row, never the batch
        await cur.execute(_ROLLBACK_TO_ROW)
        # RELEASE as well: `ROLLBACK TO` leaves the savepoint VALID, so without this each
        # quarantined row leaks a subtransaction and the next iteration nests another of the same
        # name. At limit=500 that can push one transaction past Postgres's 64-entry subxid cache
        # into snapshot overflow — cluster-wide SubtransSLRU contention on the SHARED
        # postgres-main, caused by a housekeeping sweep.
        await cur.execute(_RELEASE_ROW_SAVEPOINT)
        quarantined.append(f"{job_id} ({type(exc).__name__})")
        return False
    await cur.execute(_RELEASE_ROW_SAVEPOINT)
    return True


# No `ddl()` helper here, deliberately. Reading `schema_spend_cap.sql` off `__file__` would make a
# consumer who vendored only the .py fail at RUNTIME with a FileNotFoundError, on the money path.
# The schema is applied by the consuming project, the same convention cost-budget's own reservation
# schema documents.
