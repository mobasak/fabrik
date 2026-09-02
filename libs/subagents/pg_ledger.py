"""Centralized run-metrics sink — one shared `subagent_runs` table on `postgres-main`.

The local JSONL :class:`ledger.Ledger` is per-project provenance. THIS is the fleet-wide
aggregation: every project's vendored ``subagents`` writes each run's metrics to ONE shared
Postgres table (over the network, env-driven DSN) — never to another project's repo. It
mirrors ``cost-budget``'s cross-project ``cost_ledger`` on ``postgres-main``: a shared DB
*service* is how sandboxed agents centralize data without touching each other's files.

Storage contract (what a vendoring project must know):
  * **Where:** the table ``subagent_runs`` on the shared ``postgres-main`` (never localhost).
    The DSN comes from env ``SUBAGENT_RUNS_DSN`` (unset ⇒ this sink is a no-op — JSONL only).
    The owning project label comes from env ``SUBAGENT_PROJECT`` (unset ⇒ ``"unknown"``).
  * **What:** one row per subagent run — see :data:`SUBAGENT_RUNS_DDL` for the exact columns
    (task_type, model, provider, status, cost_usd, turns, latency_s, quality_score, …).
  * **How:** FAIL-OPEN — a Postgres error/outage NEVER breaks a run (the JSONL ledger is the
    durable local copy). Least-privilege: the module only ``INSERT``s; the table is
    provisioned centrally (the hub, alongside ``kilo-benchmarks``), so it does NOT auto-DDL.
  * **Why:** aggregating these rows per (task_type, model) — success rate × avg cost ×
    avg quality → value — is what refines ``select.pick_models`` fleet-wide (the flywheel).
    NOTE: a run may have MORE THAN ONE row — an objective dispatch row plus a later
    ``status='scored'`` delta from :func:`set_quality`. The aggregation MUST therefore reconcile
    PER ``agent_id`` first (a run's effective quality = the non-NULL/latest ``quality_score``
    across its rows) and count RUNS from the objective rows only (``status <> 'scored'``), so a
    back-filled score neither double-counts ``n`` nor skews ``avg quality``. See :func:`set_quality`.

``quality_score`` is the one field the ORCHESTRATOR records after judging (it is a verdict,
not a measurement); the objective columns are captured automatically from the run.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Canonical schema. Provisioned centrally (hub) — shipped here so the hub/DBA can apply it and
# so a WSL-dev project can create it locally. `id` is a surrogate key; the indexes serve the
# per-(task_type, model) aggregation the ranking runs.
SUBAGENT_RUNS_DDL = """
CREATE TABLE IF NOT EXISTS subagent_runs (
    id            BIGSERIAL PRIMARY KEY,
    ts            TIMESTAMPTZ NOT NULL DEFAULT now(),
    project       TEXT NOT NULL,
    agent_id      TEXT NOT NULL,
    task_type     TEXT NOT NULL,
    model         TEXT NOT NULL,
    provider      TEXT,
    status        TEXT NOT NULL,
    cost_usd      DOUBLE PRECISION,
    turns         INTEGER,
    latency_s     DOUBLE PRECISION,
    quality_score REAL,
    tool_calls    JSONB,
    session_id    TEXT,
    -- Added 2026-09-02 (plan 2026-09-02-plan-1-flywheel-recording, Phase F). ALL NULLABLE, so none
    -- of them belongs in _REQUIRED_OUTBOX_COLS — an outbox row written by an OLDER vendored copy
    -- lacks every one of these keys and must still flush.
    failure_reason TEXT,        -- F1: WHY a run failed. The table previously had NO error column at
                                -- all, so `error` could not be told from OUR price cap, and a
                                -- provider stall could not be told from OUR turn ceiling. Three
                                -- wrong model verdicts in one day came from that single gap.
    queue_s        DOUBLE PRECISION,  -- F2: latency_s is measured from dispatch, and the provider
                                -- sub-cap + global semaphore are acquired ~100 lines later, so the
                                -- queue wait sits INSIDE latency_s by construction (the same model
                                -- read 1051s benchmarked and 61s in production). Recorded
                                -- separately; latency_s keeps its meaning for the 48 copies.
    tokens_out     INTEGER,     -- F3: $/run alone confounds model price with task size.
    tokens_in      INTEGER,     -- F3: ⚠️ NO PRODUCER YET — see AgentResult. Ships nullable so the
                                -- column exists when a producer lands; never written today.
    run_label      TEXT,        -- F4: `project` is meant to be the REPO. It holds run labels today
                                -- (4,435 of 9,327 rows said 'review'), so the label moves here and
                                -- `project` becomes what its name claims.
    corpus_id      TEXT         -- F5: nothing recorded WHICH task a run performed, so two runs were
                                -- never known to be comparable.
);
CREATE INDEX IF NOT EXISTS subagent_runs_task_model_idx ON subagent_runs (task_type, model);
CREATE INDEX IF NOT EXISTS subagent_runs_ts_idx ON subagent_runs (ts);
-- Added 2026-08-15 with the session_id column. A table created from an OLDER copy of
-- this DDL needs the column added before this module can write to it at all:
--     ALTER TABLE subagent_runs ADD COLUMN IF NOT EXISTS session_id TEXT;
-- Added 2026-09-02 (Phase F). ⚠️ `CREATE TABLE IF NOT EXISTS` does NOTHING to an existing table, so
-- editing the DDL above is not a migration — these must be run by hand against EVERY live database.
-- There are TWO: the hub's local `fabrik_analytics` (what the ranking reads) and postgres-main (what
-- `fabrik apply` provisions). `ensure_shared_analytics_db()` reaches only the second.
--     ALTER TABLE subagent_runs ADD COLUMN IF NOT EXISTS failure_reason TEXT;
--     ALTER TABLE subagent_runs ADD COLUMN IF NOT EXISTS queue_s DOUBLE PRECISION;
--     ALTER TABLE subagent_runs ADD COLUMN IF NOT EXISTS tokens_out INTEGER;
--     ALTER TABLE subagent_runs ADD COLUMN IF NOT EXISTS tokens_in INTEGER;
--     ALTER TABLE subagent_runs ADD COLUMN IF NOT EXISTS run_label TEXT;
--     ALTER TABLE subagent_runs ADD COLUMN IF NOT EXISTS corpus_id TEXT;
""".strip()

_INSERT = (
    "INSERT INTO subagent_runs "
    "(project, agent_id, task_type, model, provider, status, cost_usd, turns, "
    "latency_s, quality_score, tool_calls, session_id, "
    # Added 2026-09-02 (Phase F) — in the SAME order as _COLS, which is what builds the value tuple.
    "failure_reason, queue_s, tokens_out, tokens_in, run_label, corpus_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s) "
    # UNTARGETED on purpose. ⚠️ UPDATE 2026-09-02: the index the rest of this comment says does not
    # exist NOW DOES — `subagent_runs_dispatch_agent_uidx`, `UNIQUE (agent_id) WHERE status <>
    # 'scored'` — so this clause is no longer inert: it actively dedupes dispatch rows (measured: 0
    # duplicate non-scored agent_ids). `scored` rows stay EXEMPT by design, because set_quality
    # writes a second row per run on purpose, and 120 agent_ids currently carry more than one.
    # The historical note below is kept because it explains WHY the bare form was chosen.
    # `subagent_runs` had no unique index on agent_id at the time, and the hub
    # reported 995 duplicate agent_ids table-wide (review 205, deploy-triad-gateA 93, …) — any
    # repeated write of one agent_id duplicated, because nothing rejected it. `ON CONFLICT
    # (agent_id) DO NOTHING` would be a syntax error against the table as it stands, which is
    # what made this look like it needed a coordinated two-repo change and therefore stall.
    #
    # The bare form needs no coordination: verified against a live Postgres that it is VALID
    # with no unique constraint (a harmless no-op — 2 inserts, 2 rows) and dedupes the instant
    # the index exists (2 inserts, 1 row). So it ships now, inert, and starts working by itself
    # the moment the table's owner adds the constraint. No flag day, no lockstep release.
    #
    # ⚠️ It does NOT fix the 995 rows already there; those need a dedupe pass by whoever holds
    # the DSN. This only stops the count growing.
    "ON CONFLICT DO NOTHING"
)
# The `_INSERT` column order — the outbox serializes a row as a name→value dict so `flush_outbox`
# can rebuild the exact tuple regardless of dict ordering. Keep in lockstep with `_INSERT`.
# The outbox gate checks THIS, not _COLS. The distinction is what makes adding a column safe.
#
# An outbox row is written by an OLDER copy of this module than the one flushing it — that is the
# whole point of an outbox (the DB was unreachable; the row waits). So growing _COLS and validating
# against it retroactively condemns every row already on disk: `all(c in obj for c in _COLS)` fails
# on the new key and quarantines them to pg_outbox.corrupt.jsonl. Those rows are the SCORED ones —
# precisely what the outbox exists to protect — and there are 61 vendored copies that could have
# written them.
#
# The INSERT path never needed the strictness: it reads `r.get(c)`, so a missing key is already
# None. Only the gate was too strict. Ordering condition from the table's owner (intel), and the
# reason this lands BEFORE any ALTER TABLE or any code that writes the new column.
#
# ⚠ Add a name here ONLY for a column that is NOT NULL with no default — i.e. one whose absence
# genuinely makes a row unusable. A new NULLABLE column must never be added.
_REQUIRED_OUTBOX_COLS = (
    "project",
    "agent_id",
    "task_type",
    "model",
    "status",
)

_COLS = (
    "project",
    "agent_id",
    "task_type",
    "model",
    "provider",
    "status",
    "cost_usd",
    "turns",
    "latency_s",
    "quality_score",
    "tool_calls",
    # Added 2026-08-15 with the DB column. Safe to append ONLY because the flush gate checks
    # _REQUIRED_OUTBOX_COLS, not _COLS — an older copy's outbox row lacks this key and must still
    # flush. That ordering was the precondition the table's owner made explicit; adding it here
    # first would have quarantined every pending SCORED row as poison.
    "session_id",
    # Added 2026-09-02 (Phase F), same rule: nullable, absent from _REQUIRED_OUTBOX_COLS, so an
    # older copy's rows keep flushing. ⚠️ Growing _COLS is NOT optional — adding the DB columns
    # alone would create six columns that nothing ever writes.
    "failure_reason",
    "queue_s",
    "tokens_out",
    "tokens_in",
    "run_label",
    "corpus_id",
)


def _outbox_path(outbox_dir: str | None) -> Path:
    """The store-and-forward outbox file. Co-located with the ledger under ``<repo>/.tmp/subagents``
    (or ``outbox_dir`` if given). Scored rows land here when the DB is UNREACHABLE (no DSN in dev,
    or a transient failure) so the quality verdict is never lost — :func:`flush_outbox` replays them
    from a machine that CAN reach ``postgres-main`` (the hub). Env ``SUBAGENT_OUTBOX_DIR`` overrides the
    cwd-relative default — the suite sets it to a tmp dir so a test can never append FIXTURE rows to the
    real outbox (they were being flushed into the shared flywheel as bogus `project="unknown"` runs)."""
    base = (
        Path(outbox_dir)
        if outbox_dir
        else Path(os.getenv("SUBAGENT_OUTBOX_DIR") or Path(".tmp") / "subagents")
    )
    return base / "pg_outbox.jsonl"


def _is_transient_db_error(exc: BaseException) -> bool:
    """Is this a failure to REACH the database, rather than a rejection of the row?

    Deny-list by class name so the module keeps its zero-import-of-psycopg2 property (the
    DB handle arrives through an injected `connect`). Unknown errors are treated as
    TRANSIENT — the safe direction here, because a mis-classified transient costs one
    retry, whereas a mis-classified rejection retires a good row into quarantine where
    nothing will look for it.
    """
    # ⚠️ WALK THE MRO, DO NOT MATCH THE LEAF NAME. This compared `type(exc).__name__` against the
    # base-class names — and psycopg NEVER raises those bases for a real rejection. It raises
    # SQLSTATE subclasses: `UniqueViolation`, `NotNullViolation`, `ForeignKeyViolation`,
    # `CheckViolation`, `InvalidTextRepresentation`. None of their leaf names is `IntegrityError`, so
    # EVERY genuine row rejection fell through to the default and was classified TRANSIENT — never
    # quarantined, retried on every flush, failing identically forever. Exactly the "blocking forever"
    # outcome the quarantine exists to prevent, sitting underneath the two rounds spent fixing the
    # batch-gating side of the same problem. Verified against the installed psycopg 3.3.3: 6 of 6
    # rejection classes misclassified.
    #
    # It survived every test because the tests define `class IntegrityError(Exception)` by hand — a
    # fixture that matches the deny-list by construction. Offline mocks hide real-library semantics;
    # this repo recorded that lesson once already, in ses_transport.
    names = {c.__name__ for c in type(exc).__mro__}
    if names & {"OperationalError", "InterfaceError", "PoolError", "AdminShutdown"}:
        return True
    # ⚠️ THE POISON FAMILY IS CHECKED BEFORE THE TEXT HEURISTIC, and the original order was the bug.
    # A CLASS is definitive; a substring is a guess. With the text test running first, an
    # `IntegrityError` whose message merely NAMES a constraint containing "connection" —
    # `duplicate key value violates unique constraint "subagent_runs_agent_connection_uidx"` — was
    # classified TRANSIENT. The consequence is the file's own worst bug re-opened by a different
    # root cause: `all_accounted` goes False, `.flushing` is kept, and on the next flush the rows
    # that DID commit are re-inserted while the poison row fails identically forever. The docstring
    # already promised class-based classification; now the code does it.
    if names & {"IntegrityError", "DataError", "ValueError"}:
        return False
    # ⚠️ `ProgrammingError` IS BOTH THINGS, AND SPLITTING IT NEEDS THE SQLSTATE — NOT THE CLASS.
    # An earlier revision dropped it from the poison set on the argument that "the INSERT is a module
    # constant, so a ProgrammingError cannot be specific to one row". That argument is FALSE, and a
    # live reproduction against a real Postgres proved it: psycopg raises a bare, leaf
    # `ProgrammingError` CLIENT-SIDE when a parameter value cannot be adapted —
    # `_adapters_map.py:227`, "cannot adapt type 'dict' using placeholder '%s'". That is as
    # row-specific as a rejection gets, and treating it as transient retried the row forever: the
    # very defect the MRO fix above was written to close, reopened one commit later by its own
    # "mirror". Two rounds of this file's history are the same lesson — a claim about what CANNOT
    # happen deserves an execution, not a plausible sentence.
    #
    # The discriminator is provenance, not type: an error raised BY THE SERVER carries a `sqlstate`
    # (psycopg3) / `pgcode` (psycopg2); one raised client-side before anything was sent does not.
    #   · no sqlstate  → the driver refused THIS ROW's values      → poison, quarantine it
    #   · has sqlstate → the server refused the STATEMENT (e.g. `UndefinedColumn` 42703 against a
    #     table predating `session_id`) → an environment problem every row shares, whose documented
    #     recovery is `ALTER TABLE` after which the queued rows flush. Quarantining those would move
    #     the whole outbox out of the retry path recovery depends on.
    # Verified against the installed driver: psycopg has 44 bare-`ProgrammingError` raise sites and
    # every one is client-side (conninfo parsing, cursor state, query building, row factories);
    # server errors arrive only as SQLSTATE-mapped subclasses, which carry the code on the CLASS.
    #
    # TWO RESIDUALS, stated rather than discovered later:
    #  1. a schema mismatch retries until the operator migrates — recoverable, which quarantine is not.
    #  2. of the client-side sites reachable from `cur.execute(_INSERT, params)`, one is NOT
    #     row-specific: a placeholder/parameter COUNT mismatch, i.e. `_INSERT` and `_COLS` disagreeing.
    #     That would quarantine the whole batch. It is a module bug that can never succeed on retry,
    #     so quarantine (inspectable, loud — a quarantine file appears where none was) is the better
    #     of the two bad outcomes; it is named here so the next reader does not rediscover it as a
    #     surprise.
    # `is not None`, not truthiness: an empty-string sqlstate is still PROVENANCE — it says the server
    # spoke. Truthiness would read `""` as "no code at all" and quarantine a server-raised error,
    # stranding the outbox outside the retry path. Unreproducible against a live Postgres (the wire
    # protocol always populates the field), which is exactly why it is worth spelling out rather than
    # leaving to a reader to re-derive.
    if names & {"ProgrammingError", "NotSupportedError"} and (
        getattr(exc, "sqlstate", None) is None and getattr(exc, "pgcode", None) is None
    ):
        return False
    text = str(exc).lower()
    if any(k in text for k in ("could not connect", "server closed", "connection", "timeout")):
        return True
    # Unknown class, no connection-shaped text: treat as TRANSIENT — the safe direction, because a
    # mis-classified transient costs one retry while a mis-classified rejection retires a good row
    # into quarantine where nothing will look for it.
    return True


def _flush_row_by_row(
    rows: list[dict[str, object]],
    dsn: str,
    connect: Callable[[str], Any] | None,
    base: Path,
) -> tuple[list[dict[str, object]], bool]:
    """Insert each row in its own transaction.

    Returns ``(landed_rows, all_accounted)``. ``all_accounted`` is False when a TRANSIENT
    failure means the batch is unfinished and `.flushing` must be kept for a clean retry;
    True when every row is either landed or quarantined.

    The batch path is the fast path; this runs only after it failed, to find out which row
    is actually poison. Anything that still fails is written to `pg_outbox.quarantine.jsonl`
    with the error, so it is inspectable rather than either lost or blocking forever.

    A row that fails for a TRANSIENT reason (the DB is simply down) fails here too and is
    NOT quarantined — the whole call returns nothing landed and `.flushing` is retried
    later, which is the behaviour that was always intended.
    """
    landed: list[dict[str, object]] = []
    poison: list[tuple[dict[str, object], str]] = []
    transient = False
    quarantined: list[tuple[dict[str, object], str]] = []
    for r in rows:
        conn = None
        try:
            conn = connect(dsn) if connect is not None else _connect(dsn)
            with conn:
                with conn.cursor() as cur:
                    cur.execute("SET LOCAL statement_timeout = 30000")
                    cur.execute(_INSERT, tuple(r.get(c) for c in _COLS))
            landed.append(r)
        except Exception as exc:  # noqa: BLE001
            # ⚠ Classify by ERROR CLASS, not by "has any row succeeded yet".
            #
            # `reachable` is a once-True latch, so if the DB dies HALFWAY through the loop
            # every remaining row was quarantined as poison while being merely transient —
            # and a quarantined row is removed from the retry path, so a blip would have
            # silently retired good rows. Same mistake, and the same fix, as db-pool's
            # retry classifier: a connection-shaped failure is transient and must be left
            # for the next attempt; only a REJECTION of the row itself is poison.
            if _is_transient_db_error(exc):
                transient = True
            else:
                poison.append((r, f"{type(exc).__name__}: {exc}"))
        finally:
            if conn is not None:
                with contextlib.suppress(Exception):
                    conn.close()

    # ⚠️ POISON IS A PROPERTY OF THE ROW, NOT OF THE BATCH. This read `if poison and not transient:`,
    # so a definitively-rejected row that merely SHARED a batch with a flaky one was not quarantined —
    # it was folded back into the retry set and re-attempted on every flush, invisible to the
    # quarantine file the README tells operators to inspect, for as long as the intermittent failures
    # continued. The docstring above promises the opposite ("inspectable rather than either lost or
    # blocking forever"). Classification is already by error CLASS, deliberately (`_is_transient_db_error`
    # fails OPEN toward transient), so a row that reached `poison` was rejected on its own merits and
    # the neighbouring outage does not change that.
    if poison:
        # ⚠️ THE SUPPRESSED WRITE WAS A DELETE. This block quarantined poison rows inside
        # `contextlib.suppress(Exception)` and returned `all_accounted=True` REGARDLESS — and the
        # caller then unlinks `.flushing`. So when the quarantine write failed (a read-only or full
        # outbox dir, a path collision) the row was in neither the DB, nor the quarantine, nor the
        # retry path: destroyed, while `flush_outbox` returned a POSITIVE count and an empty
        # `reason_sink`. That inverts this file's own premise — "inspectable rather than either lost"
        # — and these are the scored rows the outbox exists to protect.
        # A quarantine that did not happen is NOT an accounting: report it unfinished and keep
        # `.flushing`, so the rows are retried instead of silently dropped.
        try:
            q = base / "pg_outbox.quarantine.jsonl"
            with q.open("a", encoding="utf-8") as fh:
                for r, why in poison:
                    fh.write(json.dumps({"row": r, "error": why}, default=str) + "\n")
                fh.flush()
        except Exception:  # noqa: BLE001 — could not preserve them, so do not declare them accounted
            # ⚠️ AND NARROW THE RETRY SET, or the previous fix trades a LOSS for an unbounded
            # DUPLICATE. Returning `all_accounted=False` makes the caller keep `.flushing` — which
            # still holds the rows that ALREADY LANDED in their own committed per-row transactions.
            # If the quarantine dir stays unwritable (read-only mount, full disk), every subsequent
            # flush re-inserts those rows again, forever. Reproduced: two flushes, `good-1` committed
            # twice, and it does not converge. The module's at-least-once tolerance is scoped to a
            # crash between commit and cleanup — bounded, and once.
            # So rewrite `.flushing` down to the UNACCOUNTED rows only. The poison row is still
            # retried (and re-quarantined the moment the dir is writable again); the landed ones are
            # not. If THIS write also fails we are on a wholly unwritable dir and fall back to the
            # old behaviour — duplicates, never loss — which is the right way round.
            # ⚠️ EVERYTHING NOT LANDED, not just the poison rows. This named `poison` alone, which was
            # equivalent while the gate above read `if poison and not transient:` — the branch could
            # only be reached with zero transient rows. Widening that gate (correctly) made this
            # branch reachable WITH transient rows present, and it then rewrote `.flushing` to the
            # poison rows only: a transiently-failed row was not landed, not quarantined (the write
            # is what just failed) and no longer in the retry set. It vanished, silently, against a
            # module that promises "duplicates, never loss". A fix that widens a condition owes an
            # audit of every branch that condition now reaches.
            _landed = {id(r) for r in landed}
            _narrow_flushing(base, [r for r in rows if id(r) not in _landed])
            return landed, False
        quarantined = list(poison)
    # A transient failure anywhere means the batch is NOT finished: report nothing landed so
    # `.flushing` is retried intact, rather than declaring partial success and dropping the
    # rows that never got their chance.
    # ⚠ EVERY row ends up in exactly one of `landed`, `poison`, or (on a transient) back in
    # the retry path. The first version keyed both the quarantine and the return on a
    # `reachable` latch, so a row failing BEFORE the first success was in none of them — not
    # landed, not quarantined, not retried. It simply vanished, and these are the scored rows
    # the outbox exists to protect.
    if transient:
        # ⚠️ THE MIRROR OF THE QUARANTINE CASE, and the first fix closed only one of the two. "Nothing
        # is finished" is true of the BATCH and false of the ROWS: everything in `landed` committed in
        # its own transaction before the connection died, so retrying the file intact re-inserts them
        # on every subsequent flush. Keep exactly what is still owed.
        done = {id(r) for r in landed}
        # …and drop the quarantined rows too, or the transient path re-adds what we just filed.
        done |= {id(r) for r, _why in quarantined}
        _narrow_flushing(base, [r for r in rows if id(r) not in done])
        return [], False  # this CALL finished nothing; the retry set is now only what is unfinished
    assert len(landed) + len(poison) == len(rows)  # noqa: S101 — accounting invariant
    return landed, True


def _narrow_flushing(base: Path, keep: list[dict[str, object]]) -> None:
    """Rewrite the claimed batch down to the rows still owed a retry. NEVER raises.

    ⚠️ THE RETRY SET IS DURABLE STATE, AND IT WAS ALWAYS THE WHOLE BATCH. Both unfinished paths in
    :func:`_flush_row_by_row` — a failed quarantine write, and a transient error partway through —
    return ``all_accounted=False`` so the caller keeps ``.flushing`` for a clean retry. But
    ``.flushing`` also holds every row that ALREADY LANDED in its own committed per-row transaction,
    so each later flush re-inserts them. With a persistent cause (a read-only quarantine dir, a row
    that reliably kills the connection) that never converges: reproduced at 1 duplicate insert per
    flush, climbing without bound.

    This module's at-least-once tolerance is deliberately scoped to a crash between commit and
    cleanup — bounded, and once. An unbounded multiplier in the shared ``subagent_runs`` table is a
    different animal: it inflates cost/turns/latency for one agent_id and silently skews the flywheel
    ranking that `pick_models` reads.

    Best-effort by design: if THIS write fails too we are on a wholly unwritable directory and the
    caller falls back to retrying the full batch — duplicates, never loss, which is the right way
    round when only one of the two is available.
    """
    with contextlib.suppress(Exception):
        tmp = base / "pg_outbox.flushing.residual"
        with tmp.open("w", encoding="utf-8") as fh:
            for r in keep:
                fh.write(json.dumps(r, default=str) + "\n")
            fh.flush()
        os.replace(tmp, base / "pg_outbox.flushing.jsonl")


def _agent_id_pending_in_outbox(agent_id: str, outbox_dir: str | None) -> bool:
    """Is this agent_id's DISPATCH row sitting unflushed in our own outbox?

    ⚠ This is what makes the orphan guard correct rather than merely strict. "Absent from
    the DB" has two causes and they need opposite answers:

      * never recorded at all      → a genuine orphan; scoring it invents flywheel data
      * recorded but not yet flushed → the row IS coming; discarding the verdict loses the
        single most valuable signal the flywheel collects, in exactly the outage the
        outbox exists to survive

    `set_quality` used to return False for both, while its own docstring promised the
    opposite ("this scored delta stands ALONE … the quality verdict is preserved").
    """
    for name in ("pg_outbox.jsonl", "pg_outbox.flushing.jsonl"):
        f = _outbox_path(outbox_dir).with_name(name)
        try:
            if not f.exists():
                continue
            lines = f.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            if not line.strip():
                continue
            # Per-LINE tolerance: the outbox is flush-not-fsync, so a torn tail line is an
            # expected state and must not hide the rows after it.
            try:
                obj = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if not isinstance(obj, dict) or str(obj.get("agent_id") or "") != agent_id:
                continue
            # ⚠ Must be a DISPATCH row, not a scored delta. `status == "scored"` is the
            # delta marker; matching it made the guard SELF-SUSTAINING — a scored delta
            # outboxed by the no-DSN branch (which does no orphan check at all) would
            # satisfy the pending lookup for the NEXT score, so deltas for a run with no
            # dispatch row could accumulate indefinitely and then flush into the table,
            # re-opening the orphan hole this guard exists to close.
            if str(obj.get("status") or "") == "scored":
                continue
            return True
    return False


def _append_outbox(row: tuple[object, ...], outbox_dir: str | None) -> None:
    """Best-effort append of one scored row (as a name→value dict) to the outbox. Same durability
    envelope as the JSONL :class:`ledger.Ledger` — ``flush``ed, not ``fsync``ed, so a power-loss can
    still lose the last write (acceptable for a flywheel; the objective metrics are also in the
    ledger). NEVER raises — a capture failure must not break the run."""
    try:
        p = _outbox_path(outbox_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        # row[10] (tool_calls) is ALREADY a JSON string (built in record_run); it round-trips as a
        # string and feeds _INSERT's `%s::jsonb` cast verbatim on flush — do not re-encode it.
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(zip(_COLS, row, strict=True)), default=str) + "\n")
    except Exception:  # noqa: BLE001 — best-effort; never raise
        pass


def _session_id() -> str | None:
    """This session's identity for the ledger row, or ``None``.

    Deferred import, like every other ``.ledger`` use here, so a broken ``ledger`` module can
    never block a record; and fail-open, because a missing session must degrade to NULL rather
    than lose the row. The column is nullable exactly to allow that.
    """
    try:
        from .ledger import session_id  # noqa: PLC0415 — deferred by module convention

        return session_id()
    except Exception:  # noqa: BLE001 — never let identity lookup break a record
        return None


def _connect(dsn: str) -> Any:
    """Lazy psycopg (v3) connection — imported only when a DSN is configured, so the module
    imports fine without psycopg installed (the Postgres sink is optional). Bounds the TCP
    connect via ``connect_timeout``; the INSERT is bounded separately by a ``SET LOCAL
    statement_timeout`` inside the transaction (see :func:`record_run`) so we do NOT pass an
    ``options`` kwarg — that would REPLACE any ``options`` the project's DSN already sets (e.g.
    ``search_path``), silently pointing the INSERT at the wrong schema."""
    import psycopg  # noqa: PLC0415 — lazy: optional dependency, only needed for this sink

    return psycopg.connect(dsn, connect_timeout=5)


def record_run(
    record: dict[str, object],
    *,
    dsn: str | None = None,
    project: str | None = None,
    quality_score: float | None = None,
    connect: Callable[[str], Any] | None = None,
    outbox_dir: str | None = None,
) -> bool:
    """Best-effort INSERT one ledger record into the shared ``subagent_runs`` table.

    FAIL-OPEN: returns ``False`` on ANY error and NEVER raises. Returns ``True`` only on a committed
    DB insert. When the DB is UNREACHABLE (no DSN — the norm in WSL dev, which has no route to
    ``postgres-main`` — or a transient error), the SCORED row is durably appended to a local OUTBOX
    (``<outbox_dir or .tmp/subagents>/pg_outbox.jsonl``) so :func:`flush_outbox` can replay it from a
    machine that CAN reach the DB (the hub). This is what stops the ``quality_score`` — the verdict,
    the highest-value flywheel signal — from being LOST when a dev box can't reach the flywheel DB.
    ``dsn``/``project`` default to env ``SUBAGENT_RUNS_DSN`` / ``SUBAGENT_PROJECT``.
    """
    # Build the row inside the try so a bad `record` (non-dict — this is a public exported
    # symbol) or an unserializable `tool_calls` (default=str, like the JSONL path) can't raise:
    # the "never raises" contract is absolute.
    try:
        dsn = dsn or os.getenv("SUBAGENT_RUNS_DSN")
        if not isinstance(record, dict):
            # THE #1 flywheel footgun: a raw AgentResult (not a provenance dict) → silent no-op,
            # indistinguishable from a real write. Warn LOUDLY (still fail-open — never raise) so the
            # misuse is visible. An AgentResult has an ``agent_id`` attribute; a stray non-dict does not.
            if hasattr(record, "agent_id"):
                print(
                    "subagents.record_run: received an AgentResult, not a provenance dict — this is a "
                    "SILENT no-op (nothing was recorded). Use "
                    "record_agent_run(spec, result, quality_score=…) instead.",
                    file=sys.stderr,
                    flush=True,
                )
            return False
        proj = project or os.getenv("SUBAGENT_PROJECT") or "unknown"
        # A run with no gradeable output (status != "done": capped/error) carries NO quality verdict —
        # coerce to NULL so an infra/provider failure (e.g. a stalled `capped` run) can't teach
        # pick_models a false 0. quality_score is a judgment of the OUTPUT; there is none to judge.
        if str(record.get("status") or "") != "done":
            quality_score = None
        row = (
            proj,
            str(record.get("agent_id") or ""),
            str(record.get("task_type") or "code"),
            str(record.get("model") or ""),
            record.get("provider"),
            str(record.get("status") or ""),
            record.get("cost_usd"),
            record.get("turns"),
            record.get("latency_s"),
            quality_score,
            json.dumps(record.get("tool_calls") or {}, default=str),
            # Which session produced this run. NULL when the harness provides none (a vendored
            # copy in CI), which the column is nullable to allow. Never derived from the process:
            # a pid/ppid-based identity changes between an agent's own commands, which is how a
            # repo lock here became unreleasable by its own author.
            record.get("session_id") or _session_id(),
            # Added 2026-09-02 (Phase F). ⚠️ THIS TUPLE IS HAND-BUILT AND IS *NOT* DRIVEN BY _COLS —
            # _COLS drives the OUTBOX path only. Growing _INSERT without growing this tuple makes
            # every direct insert raise, and the fail-open below swallows it into the outbox, so the
            # DB silently stops receiving rows while everything still "works". That is exactly what
            # happened while writing this change, and only executing an insert revealed it: the
            # placeholder count matched _COLS perfectly and told us nothing.
            record.get("failure_reason"),
            record.get("queue_s"),
            record.get("tokens_out"),
            record.get("tokens_in"),
            # F4: `project` is the REPO; the run label moves to its own column. Falls back to the
            # legacy `project` value so an older caller's label is not lost on the way through.
            record.get("run_label") or record.get("project"),
            record.get("corpus_id"),
        )
    except Exception:  # noqa: BLE001 — fail-open: a malformed record never raises
        return False
    # Try the DB first when a DSN is configured; on ANY miss (no DSN / connect fail / insert fail),
    # fall through to the durable outbox so the scored row is never lost.
    if dsn:
        conn = None
        try:
            conn = connect(dsn) if connect is not None else _connect(dsn)
            with conn:  # psycopg: commits on clean exit, rolls back on error
                with conn.cursor() as cur:
                    # bound the INSERT to 5s WITHOUT clobbering the DSN's own connect options —
                    # SET LOCAL scopes to this transaction only
                    cur.execute("SET LOCAL statement_timeout = 5000")
                    cur.execute(_INSERT, row)
            return True  # committed to postgres-main — the flywheel has it
        except Exception:  # noqa: BLE001 — fail-open: unreachable/bad insert → outbox below
            pass
        finally:
            if conn is not None:
                with contextlib.suppress(Exception):
                    conn.close()
    # No DSN (dev) or the DB write failed → durably capture the SCORED row locally for flush_outbox.
    _append_outbox(row, outbox_dir)
    return False  # False = "not in the DB" (contract preserved); the outbox holds it for replay


def record_agent_run(
    spec: object,
    result: object,
    *,
    quality_score: float | None = None,
    project: str | None = None,
    dsn: str | None = None,
    connect: Callable[[str], Any] | None = None,
    receipt_dir: str | None = None,
    outbox_dir: str | None = None,
    reason_sink: list[str] | None = None,
) -> bool:
    """Judge-once flywheel write for a (spec, result) pair — the call an orchestrator SHOULD use.

    ``reason_sink`` (optional list): on a ``False`` return, receives a token naming WHY —
    ``malformed-spec-or-result`` (the spec/result could not be read at all) or
    ``record-refused`` (the write itself declined; call ``flush_outbox(reason_sink=…)`` for the
    detail, since the row is queued rather than lost). ⚠️ This closes the LAST bare boolean on the
    recording path: the README section that documents these tokens is titled "Why did nothing get
    recorded?", and until now it answered for the two writers and not for the RECORDING call, which
    is the one an orchestrator actually invokes.

    ``record_run`` takes the *merged provenance dict* (:func:`ledger.agent_record`), because the
    flywheel row's ``model`` / ``task_type`` live on the **spec**, not the :class:`~agent.AgentResult`
    (the result has no such fields). Passing a raw ``AgentResult`` straight to ``record_run`` therefore
    matches ``isinstance(record, dict) → False`` and **silently no-ops** (fail-open) — a recorded run
    that never reaches ``subagent_runs``. This wrapper closes that trap: it builds the canonical record
    from the pair, then inserts it. Same fail-open contract (never raises; ``False`` on any error).

    Typical loop::

        results = run_agents(specs, repo=repo)
        for spec, r in zip(specs, results):
            q = judge(r)  # YOUR 0–5 verdict after materializing the diff + running the gate/tests
            record_agent_run(spec, r, quality_score=q, project="my-project")

    On a CONFIRMED DB write (return ``True``) it also drops a LOCAL receipt
    (:func:`ledger.write_receipt`) so the fleet enforcement gate can reconcile ledger↔receipts
    WITHOUT reading the INSERT-only ``subagent_runs`` table. ``receipt_dir`` locates the receipts
    file (the run's ``<repo>/.tmp/subagents``); default co-locates with the ledger when the
    orchestrator runs from the repo root. A fail-open ``False`` writes NO receipt — so an unrecorded
    run stays unreceipted and :func:`ledger.audit_unrecorded` flags it (that is the point).
    """
    try:
        # import INSIDE the try so a broken package context (relative import fails) is caught too —
        # the documented "never raises" contract is absolute, so nothing above the guard may throw.
        from .ledger import agent_record, write_receipt

        record = agent_record(spec, result)
        # ⚠ NO auto-0 for an empty `done` run — an empty is left UNSCORED (NULL), the honest unknown.
        # (SUPERSEDES the 2026-08-12/08-15 auto-0, reversed by intel 2026-08-29.) That auto-0 did two
        # jobs — VISIBILITY (the only way an empty surfaced) and VERDICT. da1af57d split them: the
        # `AgentResult.empty_output` marker (⚠EMPTY in results_table + the fanout harvest warning) now
        # carries visibility on its own. What remained was only the verdict, and the verdict was measured
        # usually FALSE: an empty completion is typically output-BUDGET burn (reasoning ate max_tokens — a
        # CALLER config error, not model failure), so a 0 permanently tanks a good model for the caller's
        # wrong max_tokens. A 0 must mean "the model did something bad," never "something went wrong" —
        # same principle as the error/capped NULL-coercion. NULL is ignored by the aggregation's two-level
        # reconcile, so leaving it unscored is the honest signal; an explicit caller score still wins.
    except Exception:  # noqa: BLE001 — fail-open: a malformed spec/result never raises
        if reason_sink is not None:
            reason_sink.append("malformed-spec-or-result")
        return False
    ok = record_run(
        record,
        dsn=dsn,
        project=project,
        quality_score=quality_score,
        connect=connect,
        outbox_dir=outbox_dir if outbox_dir is not None else receipt_dir,
    )
    if ok:
        # receipt ONLY on a confirmed DB insert — best-effort, never raises. (An OUTBOXED row is not
        # in the DB yet, so it stays unreceipted → audit_unrecorded still flags it until flush_outbox
        # lands it and writes the receipt then. receipt ⟺ in-the-DB.)
        write_receipt(record.get("agent_id"), project, receipt_dir=receipt_dir)
    elif reason_sink is not None:
        # ⚠️ NOT "lost". `record_run` returning False means the row went to the OUTBOX (or was
        # refused outright); `flush_outbox(reason_sink=…)` is where the specific token lives. What
        # this token fixes is the caller who could not tell "your spec was garbage" from "the DB is
        # down" — two states with opposite operator responses, behind one bare `False`.
        reason_sink.append("record-refused")
    return ok


def set_quality(
    agent_id: str,
    quality_score: float,
    *,
    project: str,
    task_type: str,
    model: str,
    dsn: str | None = None,
    connect: Callable[[str], Any] | None = None,
    receipt_dir: str | None = None,
    outbox_dir: str | None = None,
    reason_sink: list[str] | None = None,
) -> bool:
    """Back-fill a post-adjudication ``quality_score`` for a run that was recorded UNSCORED (e.g. by
    :func:`agent.fanout`, which auto-records at dispatch, before you've judged the output).

    The writer is INSERT-only by design (least-privilege — it never ``UPDATE``s, so it *cannot* rewrite
    the ``NULL``-quality dispatch-time row). So this APPENDS a **scored delta row**: same
    ``(project, agent_id, task_type, model)``, ``status="scored"``, every OBJECTIVE metric
    (provider/cost/turns/latency/tool_calls) ``NULL``, and ``quality_score`` set. Note the delta's
    status is ``"scored"`` (not ``"done"``) precisely so it is NOT the dispatch row and so it bypasses
    :func:`record_run`'s "non-``done`` ⇒ null the score" gate.

    **Aggregation contract (the hub rank scripts must honor this — see README):** reconcile PER
    ``agent_id`` — a run's effective quality is the non-``NULL`` / latest ``quality_score`` across its
    rows (the ``scored`` delta wins over the dispatch ``NULL``); count RUNS from the objective rows
    (``status <> 'scored'``) so a back-fill never inflates ``n``.

    ⚠️ **Score the ``agent_id`` from the result/batch YOU dispatched — never one read out of the ledger
    file.** The ``agent_id`` belongs on ``AgentResult.agent_id`` (and ``FanoutBatch.score()`` scores your
    batch for you); ``.tmp/subagents/ledger.jsonl`` is REPO HISTORY across every session, not your dispatch
    set, and it has no session scoping. Scoring an ``agent_id`` you pulled from that file back-fills a
    verdict onto ANOTHER session's run — and the INSERT-only latest-wins reconcile means there is no undo
    (transdoc contaminated 226 rows this way, `01M154PZQ`). If your vendored copy lacks
    ``AgentResult.agent_id``/``FanoutBatch.score()``, it is STALE — re-vendor rather than reach into the file.

    Pass the run's OWN ``task_type``/``model`` — the ``model`` is on the result (``AgentResult.model``,
    stamped by ``run_agents``/``fanout``), the ``task_type`` is the one you dispatched. Both are REQUIRED
    and non-empty (an empty/defaulted bucket silently misattributes the score — this returns ``False``
    instead). The INSERT-only writer can't read the dispatch row to verify them, so a wrong value would
    misattribute to the wrong ``(task_type, model)`` bucket. Use this for a run recorded UNSCORED (don't
    ALSO score it inline via ``record_agent_run(quality_score=…)`` — that leaves two non-NULL rows).

    On a committed insert it drops a local receipt (:func:`ledger.write_receipt`) so
    :func:`ledger.audit_unrecorded` stops flagging the ``agent_id`` (the orchestrator has now scored the
    run). If the ORIGINAL dispatch insert never landed (a DB blip at dispatch — ``record_agent_run``
    returned ``False`` then), this scored delta stands ALONE: the objective metrics for that one run are
    gone, but the quality verdict — the key flywheel signal — is preserved. FAIL-OPEN: returns ``False``
    on any error (bad score, missing project, no DSN, unreachable DB) and NEVER raises. ``quality_score``
    must be a real number in ``[0, 5]`` (``bool``/``NaN``/``inf`` rejected). ``dsn``/``connect``/
    ``receipt_dir`` are the injectable DB factory + receipt location, as on :func:`record_agent_run`.

    ``reason_sink`` (optional list): on a ``False`` return, receives the token(s) naming WHY. The
    validation branch may append SEVERAL (every missing field, plus a score problem); every other
    branch appends exactly one. Read the LIST, not ``sink[-1]`` — with two fields wrong,
    ``sink[-1]`` names only the last, and a caller fixing just that one is still refused. Tokens —
    ``missing-<field>`` · ``score-is-bool`` · ``score-not-a-number`` · ``score-out-of-range-0-5`` ·
    ``row-build-failed`` · ``orphan-agent-id`` · ``outboxed-not-committed`` ·
    ``missing-driver-psycopg`` · ``db-write-failed`` · ``no-dsn-outboxed``. A bare ``False`` told
    the caller only "no", which is what the upstream report was about."""
    def _sq_no(reason: str) -> bool:
        # ⚠️ FOUR OF FIVE `return False` BRANCHES WERE SILENT after the first fix — including the two
        # that matter most operationally: a GENUINE ORPHAN (this agent_id never ran, so the score is
        # not real) and OUTBOXED-NOT-COMMITTED (it will land on the next flush). A caller could not
        # tell those from a validation rejection. Found by the review, after I had already replied.
        if reason_sink is not None:
            reason_sink.append(reason)
        return False

    try:
        dsn = dsn or os.getenv("SUBAGENT_RUNS_DSN")
        # validate the verdict up front — a bad score must never reach the flywheel (a bool is an int
        # subclass, so exclude it explicitly, else True/False would sneak in as 1.0/0.0).
        if (
            not agent_id
            or not project
            or not task_type
            or not model
            or isinstance(quality_score, bool)
            or not isinstance(quality_score, (int, float))
            or not (0.0 <= float(quality_score) <= 5.0)
        ):
            # task_type/model are REQUIRED + non-empty: a scored delta with a defaulted/empty bucket
            # (the old `task_type or "code"` / `model or ""`) silently misattributes quality to the
            # wrong (task_type, model) aggregate — worse than a no-op. Reject it.
            # ⚠️ SAY WHICH FIELD. A bare `False` told the caller only "no", and a consumer scoring
            # three fanout units got three noes with nothing to act on — reported upstream
            # 2026-08-28. The rejection is right; the silence was not. Same shape as `flush_outbox`'s
            # ambiguous `0`, one function over.
            if reason_sink is not None:
                for field, value in (
                    ("agent_id", agent_id), ("project", project),
                    ("task_type", task_type), ("model", model),
                ):
                    if not value:
                        reason_sink.append(f"missing-{field}")
                if isinstance(quality_score, bool):
                    reason_sink.append("score-is-bool")
                elif not isinstance(quality_score, (int, float)):
                    reason_sink.append("score-not-a-number")
                elif not (0.0 <= float(quality_score) <= 5.0):
                    reason_sink.append("score-out-of-range-0-5")
            # ⚠️ RETURN DIRECTLY — the specific token above is the whole answer. This used to fall
            # through to the generic `row-build-failed`, appending a SECOND token AFTER the
            # specific one, so a caller reading `sink[-1]` (the obvious read) saw an internal
            # error for a plain caller-side validation rejection and could not tell it from the
            # real exception path. That inverts this module's own "most specific wins" rule.
            return False
        row = (
            project,
            str(agent_id),
            str(task_type),
            str(model),
            None,  # provider — objective dims live on the dispatch row, NULL on the scored delta
            "scored",  # the delta marker (bypasses record_run's non-done score-null gate)
            None,  # cost_usd
            None,  # turns
            None,  # latency_s
            float(quality_score),
            json.dumps({}),
            # ⚠ _INSERT is SHARED with record_run, so this tuple's arity is load-bearing: an
            # 11-element row against the 12-column INSERT breaks EVERY scored delta. The scored
            # delta carries its own session — the one that did the JUDGING, which is the useful
            # attribution here (the dispatch row already records the session that ran it).
            _session_id(),
            # Added 2026-09-02 (Phase F). ⚠️ SECOND hand-built tuple that must track _COLS — and the
            # one that was missed. `_append_outbox` does `zip(_COLS, row, strict=True)`, so a short
            # tuple raises ValueError, the bare `except` swallows it, and set_quality silently stops
            # outboxing verdicts: no error, no reason, just a quality signal that never arrives.
            # Caught only by running fabrik-lib's own suite after the re-vendor.
            #
            # All NULL by nature: a scored delta is a judgment of an ALREADY-RECORDED run. It has no
            # failure (it is not a run), no queue wait, no tokens of its own, and no corpus — those
            # belong to the dispatch row this delta is reconciled against per `agent_id`.
            None,  # failure_reason
            None,  # queue_s
            None,  # tokens_out
            None,  # tokens_in
            project,  # run_label — same fallback as record_run, so the label is not lost
            None,  # corpus_id
        )
    except Exception:  # noqa: BLE001 — fail-open: never raises
        return _sq_no("row-build-failed")
    # Try the DB when a DSN is configured; on ANY miss, outbox the scored delta so it isn't lost.
    db_attempt_failed: str | None = None
    if dsn:
        # ── ORPHAN GUARD (2026-08-14). Refuse to score a run that has no dispatch row.
        #
        # This writer is INSERT-only, so scoring an agent_id that was never recorded does not
        # fail — it APPENDS a scored delta with no run behind it, carrying a real model name into
        # the flywheel. Seven such rows exist in fabrik_analytics (5 with real models, 4 of them
        # zeros); two are traceable to a disclosed incident where a consumer misread fanout's
        # return and scored results whose dispatch rows had never been written.
        #
        # ⚠ THREE-STATE, NOT TWO. `None` means "could not ask", and it MUST behave like today:
        # this function is documented fail-open and outboxes on any miss, so treating "cannot
        # ask" as "absent" would stop every DB-less vendored copy (CI, offline dev) from scoring
        # at all — trading a 0.8% integrity defect for total loss of the flywheel signal.
        # ⚠️ OUTBOX FIRST, DB SECOND. Reading the DB first maximised a false-orphan window: a
        # concurrent `flush_outbox` (the hub wires one into `daily_refresh.sh`) that lands the
        # dispatch row and unlinks `.flushing` BETWEEN the two reads made both answer "absent", and a
        # good verdict was discarded. Reading the outbox first closes it — the row is in one place or
        # the other at every instant, never neither.
        _ob_first = outbox_dir if outbox_dir is not None else receipt_dir
        _pending_locally = _agent_id_pending_in_outbox(str(agent_id), _ob_first)
        present = agent_ids_present([str(agent_id)], dsn=dsn, connect=connect)
        if present is not None and str(agent_id) not in present:
            # ⚠ Absent from the DB is NOT automatically an orphan. If the dispatch row is
            # pending in our own outbox it WILL land, and discarding the verdict here threw
            # away the flywheel's most valuable signal during precisely the outage the
            # outbox exists to survive — while the docstring promised it was preserved.
            # Fall through to the outbox so the score lands AFTER its dispatch row.
            # ⚠️ ONE RESOLUTION, NOT TWO. `record_agent_run` outboxes the DISPATCH row to
            # `outbox_dir if outbox_dir is not None else receipt_dir`, and this function's own
            # terminal append uses that same fallback — but the pending-check and the append here
            # used bare `outbox_dir`. A caller passing only `receipt_dir` therefore had its dispatch
            # row written to one directory and looked for in another, so a perfectly good verdict was
            # discarded as `orphan-agent-id` — exactly the harm the comment above says this guard
            # exists to prevent. `FanoutBatch.score` already works around it by passing both kwargs,
            # which means the module knew and the public API still had it.
            _ob = _ob_first
            if not _pending_locally:
                return _sq_no("orphan-agent-id")  # the run does not exist, so the score is not real
            _append_outbox(row, _ob)
            return _sq_no("outboxed-not-committed")  # the caller must not read this as landed
        conn = None
        try:
            conn = connect(dsn) if connect is not None else _connect(dsn)
            with conn:  # commits on clean exit, rolls back on error
                with conn.cursor() as cur:
                    cur.execute("SET LOCAL statement_timeout = 5000")
                    cur.execute(_INSERT, row)
            # committed → receipt (DEFERRED import so a broken .ledger can't block the committed score)
            with contextlib.suppress(Exception):
                from .ledger import write_receipt

                write_receipt(str(agent_id), project, receipt_dir=receipt_dir)
            return True
        except Exception as exc:  # noqa: BLE001 — fail-open: unreachable/bad insert → outbox below
            # ⚠️ WHICH failure, not merely THAT one. This terminal return covered TWO states with one
            # token — the comment below said so out loud ("No DSN (dev) OR the DB write failed") while
            # the token said only `no-dsn-outboxed`. With a DSN set and psycopg missing, the caller was
            # told to go check their env: a MISLEADING reason, which is worse than none, and the exact
            # connect-vs-commit defect fixed in `flush_outbox` left standing in its twin one function
            # over. A missing driver is its own cause and dominates every other check.
            # ⚠️ NAME THE MODULE, don't assume it. `isinstance(exc, ModuleNotFoundError)` alone
            # mislabels an INJECTED `connect=` whose own import of some other package fails — the
            # caller would be told to install psycopg when psycopg was never the problem. A wrong
            # reason is worse than none; check which module actually went missing.
            db_attempt_failed = (
                "missing-driver-psycopg"
                if isinstance(exc, ModuleNotFoundError) and getattr(exc, "name", None) == "psycopg"
                else "db-write-failed"
            )
        finally:
            if conn is not None:
                with contextlib.suppress(Exception):
                    conn.close()
    # No DSN (dev) or the DB write failed → capture the scored delta locally for flush_outbox.
    _append_outbox(row, outbox_dir if outbox_dir is not None else receipt_dir)
    return _sq_no(db_attempt_failed or "no-dsn-outboxed")

def flush_outbox(
    dsn: str | None = None,
    *,
    outbox_dir: str | None = None,
    connect: Callable[[str], Any] | None = None,
    receipt_dir: str | None = None,
    reason_sink: list[str] | None = None,
) -> int:
    """Replay locally-outboxed scored rows to ``subagent_runs`` — run from a machine WITH the DSN (the
    hub, e.g. wired into ``daily_refresh.sh`` next to the ranking regen). This closes the dev→flywheel
    loop: rows captured on a WSL box that couldn't reach ``postgres-main`` finally land in the DB, so
    ``pick_models`` learns from the 100+ runs/day that actually happen at dev-time.

    Robustness (all hardened + tested):
      * **Serialized** — an exclusive :func:`fcntl.flock` on ``pg_outbox.lock`` means two overlapping
        callers (the hub cron + a manual run) can't both flush the same batch (no-crash double-insert).
        A second caller that can't take the lock returns 0 cleanly.
      * **Atomic claim, no merge** — the live outbox is claimed with a single :func:`os.replace`
        (atomic); a concurrent :func:`_append_outbox` that opens its handle AFTER the rename lands in a
        fresh live. ⚠️ One that opened BEFORE it does NOT: an appended write follows the INODE, so it
        lands inside the file this flush already read and is unlinked with it. See the README gotcha
        "a row appended during a claim can be lost" — the window is real, narrow and cross-process, and
        `_append_outbox` deliberately does not take `pg_outbox.lock` (it must never block a run). A batch already pending in ``.flushing`` (a prior crash / DB outage) is processed
        first and ``live`` is left to accumulate (claimed next run) — there is NO file-merging, so no
        merge-crash double-insert or non-atomic-rewrite loss.
      * **Poison-proof** — parsed LINE BY LINE; any MALFORMED line (bad JSON from a torn write, a
        non-dict, or a row missing a required column) is quarantined to ``pg_outbox.corrupt.jsonl`` and
        the good rows still flush — a malformed line can't brick the batch. (A well-formed row a healthy
        DB rejects is left in ``.flushing`` for a maintainer; ``_append_outbox`` never produces one.)
    On a DB failure the batch stays in ``.flushing`` for the next run. A crash BETWEEN commit and cleanup
    can re-insert the batch once (at-least-once — a rare, minor skew for an aggregate flywheel;
    exactly-once would need a unique dedup key on the shared schema, a hub-coordinated change). FAIL-OPEN:
    never raises; returns the number of rows flushed (0 on any error / no DSN / lock held / empty).

⚠️ **A BARE ``0`` IS MANY DIFFERENT ANSWERS, and a consumer could not tell them apart.** Reported
    upstream 2026-08-28 by `brand-identiy-creator`: this returned 0 against a 203KB outbox with no hint
    whether the DSN was unset, the DB unreachable, the lock held, or the file empty — and the rows
    stayed unscoreable behind that silence (their backlog: 517 runs).

    The return type is a documented contract and stays an ``int``. Pass ``reason_sink=[]`` to receive a
    machine-readable token instead:

        ``dsn-missing`` · ``outbox-empty`` · ``setup-failed`` · ``lock-held`` · ``claim-failed`` ·
        ``outbox-unreadable`` · ``all-rows-malformed`` · ``all-rows-rejected`` ·
        ``missing-driver-psycopg`` · ``db-connect-failed`` · ``db-session-lost-before-insert`` ·
        ``db-commit-uncertain`` · ``db-failed``

    ⚠️ **It does NOT log.** An earlier version of this docstring said "every zero-return now LOGS a
    distinct reason" while the code five lines below states, correctly, that this module has NO logger
    by deliberate convention. That is the same defect the fix itself was written to close — a docstring
    advertising something the file does not contain — so the wording is now what the code does: the
    reason travels through the caller's sink, and if you want it logged, log the token.
    """
    def _no(reason: str) -> int:
        # ⚠️ NO LOGGER, deliberately — this module has none, and the convention it states elsewhere is
        # that "the caller distinguishes the states via the return value". That convention is precisely
        # what failed here: a bare `0` cannot distinguish five states. So the reason is returned through
        # the caller's own sink rather than smuggled into a logging setup the module does not have.
        if reason_sink is not None:
            reason_sink.append(reason)
        return 0

    try:
        import fcntl

        dsn = dsn or os.getenv("SUBAGENT_RUNS_DSN")
        if not dsn:
            return _no("dsn-missing")
        live = _outbox_path(outbox_dir)
        base = live.parent
        flushing = base / "pg_outbox.flushing.jsonl"
        if not live.exists() and not flushing.exists():
            return _no("outbox-empty")
        base.mkdir(parents=True, exist_ok=True)
        lock_fh = (base / "pg_outbox.lock").open("w", encoding="utf-8")
    except Exception:  # noqa: BLE001 — fail-open: setup failure never raises
        return _no("setup-failed")
    try:
        try:
            fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception:  # noqa: BLE001 — another flush holds the lock → skip cleanly
            return _no("lock-held")
        try:
            return _flush_locked(dsn, live, flushing, base, connect, receipt_dir, reason_sink=reason_sink)
        except Exception:  # noqa: BLE001 — the documented contract is FAIL-OPEN: never raises
            # ⚠️ THE CONTRACT HAD NO GUARD. This `try` carried only a `finally`, so anything
            # unexpected out of `_flush_locked` — including the bare `assert` in `_flush_row_by_row`'s
            # accounting invariant, which sits directly in this call chain — propagated straight out
            # of a function whose docstring says "never raises" twice. A hub cron calling this would
            # have died on it. The lock/handle cleanup below was always correct; the promise was not.
            return _no("internal-error")
    finally:
        with contextlib.suppress(Exception):
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
        with contextlib.suppress(Exception):
            lock_fh.close()


def _flush_locked(
    dsn: str,
    live: Path,
    flushing: Path,
    base: Path,
    connect: Callable[[str], Any] | None,
    receipt_dir: str | None,
    reason_sink: list[str] | None = None,
) -> int:
    """The flush critical section, run under the outbox lock. See :func:`flush_outbox`.

    Deliberately NO file-merging (no staging file): if a batch is already pending in ``flushing`` (a
    prior run crashed, or the DB was down), process THAT this run and leave ``live`` to accumulate —
    it's claimed on the next flush. The only file mutations are an atomic ``os.replace`` claim and the
    post-commit ``unlink``, so the sole at-least-once window is a crash between commit and unlink (a
    prior over-clever staging/merge introduced a double-insert + a non-atomic-rewrite loss; both gone)."""
    _db_reason_recorded: list[bool] = []  # THIS invocation only — never the caller's list

    def _no(reason: str) -> int:
        # ⚠️ THE DB-INTERACTION PATH HAD NO REASONS AT ALL. `flush_outbox` named its four SETUP
        # failures and then delegated here without the sink — so the reporter's actual scenario (a
        # 203KB outbox, DB unreachable) still returned a bare silent 0 after the "fix", and the
        # `db-failed` token the docstring advertised did not exist anywhere in the file. Found by the
        # review I should have run BEFORE replying.
        #
        # ⚠️ FIRST DB REASON WINS. A connect failure propagates to the outer handler, which would then
        # append `db-commit-uncertain` on top of `db-connect-failed` — and "the commit may have half
        # landed" is FALSE when the connection never opened. The reason recorded closest to the cause
        # is the specific one; the outer handler's is the fallback for when nothing more precise ran.
        if reason_sink is not None:
            # ⚠️ PER-INVOCATION, not a scan of the caller's list. The rule used to ask whether ANY
            # `db-` token was already in `reason_sink` — a list the CALLER owns. A caller accumulating
            # reasons across a retry loop (the natural pattern) had every later db-reason suppressed by
            # one from a previous call, and was then told "connect failed, nothing was sent" while the
            # batch may in fact have half-landed. That is the same opposite-branch harm this rule was
            # written to prevent, recreated across calls instead of within one.
            if not (reason.startswith("db-") and _db_reason_recorded):
                reason_sink.append(reason)
        if reason.startswith("db-"):
            _db_reason_recorded.append(True)
        return 0

    # 1) Claim the batch. A pending `.flushing` is processed first (live untouched); else atomically
    #    claim `live` → `flushing`. ⚠️ THIS COMMENT USED TO SAY "never a lost gap". It is only true for
    #    an append whose handle is opened AFTER the rename; a handle opened BEFORE follows the inode
    #    into `.flushing`, past the read at step 2, and is unlinked on success. Re-enacted
    #    deterministically (open → os.replace → read → write → unlink): the row is gone. Documented as
    #    a README gotcha rather than papered over; closing it means locking the append path.
    if not flushing.exists():
        if not live.exists():
            return _no("outbox-empty")
        try:
            os.replace(live, flushing)
        except Exception:  # noqa: BLE001 — fail-open: a claim failure leaves the file for the next run
            return _no("claim-failed")
    # 2) Parse LINE BY LINE — anything that is not a COMPLETE _COLS dict (bad JSON, a non-dict, or a row
    #    missing a required column from a stale/cross-version outbox) is quarantined so ONE malformed
    #    line can never brick the good rows.
    try:
        lines = flushing.read_text(encoding="utf-8").splitlines()
    except Exception:  # noqa: BLE001
        return _no("outbox-unreadable")
    good: list[dict[str, object]] = []
    bad: list[str] = []
    for ln in lines:
        if not ln.strip():
            continue
        try:
            obj = json.loads(ln)
        except Exception:  # noqa: BLE001 — a torn/corrupt line
            bad.append(ln)
            continue
        if isinstance(obj, dict) and all(c in obj for c in _REQUIRED_OUTBOX_COLS):
            good.append(obj)
        else:
            bad.append(ln)  # valid JSON but wrong shape → still poison; quarantine it
    if bad:  # best-effort audit trail; a DB-failure retry may re-append the same bad line (harmless)
        with contextlib.suppress(Exception):
            with (base / "pg_outbox.corrupt.jsonl").open("a", encoding="utf-8") as q:
                q.write("\n".join(bad) + "\n")
    if not good:
        with contextlib.suppress(Exception):
            flushing.unlink()
        return _no("all-rows-malformed")
    # 3) INSERT the good rows in one transaction.
    conn = None
    # ⚠ Distinguishes an EXECUTE-phase failure from a COMMIT-phase one, because only the
    # first is safe to retry row-by-row. `with conn:` commits at __exit__; if THAT fails
    # (network drop, server restart, pooler kill) the server may well have committed
    # already, and re-inserting every row would be a GUARANTEED full-batch duplicate
    # rather than the rare crash-window the module documents. A commit-phase failure
    # therefore leaves `.flushing` intact for a normal retry, exactly as before.
    execute_failed = False
    _pre_insert = False
    _conn_usable = True
    _quarantined = 0
    try:
        # ⚠️ CONNECT IS ITS OWN FAILURE. Wrapped together with the commit, a connection that never
        # opened reported "the commit may have partially landed" — a MISLEADING reason, which is worse
        # than none: "could not reach the DB, nothing was attempted" and "it may have half-landed,
        # retry carefully" send a caller down opposite branches. This is the reporter's exact case.
        try:
            conn = connect(dsn) if connect is not None else _connect(dsn)
        except Exception:  # noqa: BLE001 — never reached the server; nothing was sent
            # Disambiguate the two causes that surface identically here (wef, intel `01M17XKJXM`): a
            # MISSING psycopg driver vs a genuinely unreachable DB. "pip install psycopg" and "the DB is
            # down" send the operator down opposite branches, so a single `db-connect-failed` is a
            # misleading reason (worse than none). When we used the DEFAULT `_connect` (no injected
            # `connect=`) and psycopg is not importable, name THAT — a zero-cost `find_spec` probe, the
            # runtime half of the split the hub's gate-time check already makes.
            import importlib.util  # noqa: PLC0415 — stdlib, lazy

            if connect is None and importlib.util.find_spec("psycopg") is None:
                _no("missing-driver-psycopg")
            else:
                _no("db-connect-failed")
            raise
        # ⚠️ EVERYTHING BEFORE THE FIRST ROW IS ALSO "nothing was sent". The connect/commit split fixed
        # the instance a reviewer named and left the statements between them in the commit-uncertain
        # bucket: a pooler that accepts the TCP connect and then kills the session, or a restart
        # between `connect()` and first use, reported "the commit may have half-landed" with zero rows
        # sent. Marked here so the pre-INSERT window reports what actually happened.
        _pre_insert = True
        # capture it HERE: the except handler closes and CLEARS `conn` before the classification runs,
        # so asking "was it a real connection?" afterwards always saw None
        _conn_usable = hasattr(conn, "__enter__") and hasattr(conn, "cursor")
        with conn:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = 30000")
                _pre_insert = False  # a statement has now been sent; "nothing was sent" no longer holds
                try:
                    for r in good:
                        cur.execute(_INSERT, tuple(r.get(c) for c in _COLS))
                except Exception:
                    execute_failed = True
                    raise
    except Exception:  # noqa: BLE001
        # ⚠ ALL-OR-NOTHING WAS PERMANENT. One row the DB rejects (a NOT NULL violation, a
        # cross-version row whose `tool_calls` is a dict rather than a JSON string, a column
        # this copy writes that the table lacks) failed the whole transaction; `.flushing` was
        # left in place and claimed FIRST on the next call, so it failed identically forever
        # while `live` grew unbounded and was never claimed. The relaxed gate (which stopped
        # quarantining cross-version rows on key-presence alone) is what lets such a row reach
        # the INSERT, so this fallback is what keeps that relaxation safe.
        #
        # Retry ROW BY ROW so one poison row cannot hold the rest hostage, and quarantine it
        # with the reason rather than dropping it silently.
        # Close and CLEAR before retrying, so the `finally` below does not close a second
        # time. psycopg2 tolerates a repeat close, but relying on that is exactly the kind
        # of unstated assumption this loop keeps finding — and a caller-supplied `connect`
        # may return a handle that does not.
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()
            conn = None
        # ⚠ Safe against double-INSERT: the batch above runs inside `with conn:`, which
        # ROLLS BACK on the exception, so no row from the failed batch is committed. The
        # per-row retry therefore starts from a clean slate rather than re-inserting
        # anything that already landed.
        if _pre_insert and not _conn_usable:
            # the factory handed back something that is not a connection at all — a caller bug, and
            # blaming "a pooler killed the session" would be the misleading-reason defect again
            return _no("connect-returned-non-connection")
        if _pre_insert:
            # connected, but died before any statement went out — a pooler that accepts the TCP
            # connect then kills the session, or a restart between connect() and first use.
            return _no("db-session-lost-before-insert")
        if not execute_failed:
            return _no("db-commit-uncertain")  # in doubt, so retry rather than duplicate
        _before_retry = len(good)
        good, all_accounted = _flush_row_by_row(good, dsn, connect, base)
        _quarantined = _before_retry - len(good)
        if not all_accounted:
            return _no("db-failed")  # transient: leave `.flushing` intact for a clean retry
        if not good:
            # Every row was rejected. They are quarantined, so the batch is FINISHED —
            # dropping through unlinks `.flushing`. Returning early here (as the first
            # version did) left it in place to be retried identically forever, which is
            # the permanent-loop bug this fallback exists to fix, unfixed.
            with contextlib.suppress(Exception):
                flushing.unlink()
            return _no("all-rows-rejected")
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()
    # committed → receipt per row (DEFERRED + suppressed import so a broken .ledger can't raise out of
    # flush_outbox — the "never raises" contract; matches record_agent_run/set_quality) + discard batch
    with contextlib.suppress(Exception):
        from .ledger import write_receipt

        for r in good:
            with contextlib.suppress(Exception):
                proj_val = r.get("project")
                write_receipt(
                    r.get("agent_id"),
                    str(proj_val) if proj_val is not None else None,
                    receipt_dir=receipt_dir,
                )
    with contextlib.suppress(Exception):
        flushing.unlink()
    # ⚠️ A POSITIVE COUNT IS ALSO MANY ANSWERS. `return len(good)` reports only what LANDED, so a
    # batch of 100 with 40 quarantined came back as `40` with an empty `reason_sink` — the same
    # "a bare number tells the caller nothing" defect this whole change set exists to fix, sitting on
    # the success branch where nobody looked for it.
    if _quarantined:
        _no(f"partial-{_quarantined}-quarantined")
    return len(good)


__all__ = [
    "SUBAGENT_RUNS_DDL",
    "record_run",
    "record_agent_run",
    "set_quality",
    "flush_outbox",
    # ⚠️ These two are non-underscored, docstring-rich, and INTENDED for an external caller —
    # `unscored_agent_ids`' own docstring says the hub round-close requires it — yet they were in
    # neither `__all__` nor the README, so the only way to reach them was the private path
    # `subagents.pg_ledger.unscored_agent_ids`. A public-looking name that is not exported is a trap
    # for the consumer who needs it most; this repo's Vendoring Contract assumes a reader with only
    # the README.
    "agent_ids_present",
    "unscored_agent_ids",
]


def agent_ids_present(
    agent_ids: list[str],
    *,
    dsn: str | None = None,
    connect: Callable[[str], Any] | None = None,
) -> set[str] | None:
    """Which of ``agent_ids`` have a DISPATCH row. ``None`` = could not tell (DB unreachable).

    ⚠ This is the module's FIRST read. Everything else here is INSERT-only by design
    (least-privilege), so the three-state return is deliberate and load-bearing:

        set(...)  the DB answered — anything absent genuinely has no dispatch row
        set()     the DB answered "none of them"
        None      we could not ask

    A two-state (present/absent) return would collapse "no such run" into "database is down", and a
    caller acting on that would refuse to score during an outage — turning a 0.8% integrity defect
    into total loss of the flywheel signal in CI and offline dev. ``None`` is what lets
    :func:`set_quality` stay FAIL-OPEN on an unreachable DB while failing CLOSED on a real miss.
    """
    if not agent_ids:
        return set()
    dsn = dsn if dsn is not None else os.getenv("SUBAGENT_RUNS_DSN")
    if not dsn:
        return None  # no sink configured — indistinguishable from unreachable, so: cannot tell
    try:
        conn = connect(dsn) if connect is not None else _connect(dsn)
        with conn, conn.cursor() as cur:
            # ⚠ The two READ paths had no statement_timeout while all three WRITE paths
            # do. `connect_timeout=5` bounds only the TCP handshake, not the query — so a
            # server that accepts connections but blocks on a lock made this hang FOREVER
            # inside a function documented "FAIL-OPEN … NEVER raises". A hang is not a
            # fail-open; it is the worst failure mode, because nothing times out.
            cur.execute("SET LOCAL statement_timeout = 5000")
            cur.execute(
                "SELECT DISTINCT agent_id FROM subagent_runs "
                "WHERE agent_id = ANY(%s) AND status <> 'scored'",
                (list(agent_ids),),
            )
            return {r[0] for r in cur.fetchall()}
    except Exception:  # noqa: BLE001 — fail-open: a read must never become a new failure mode
        # Silent by module convention: this sink logs nothing anywhere (there is no logger here),
        # and the caller distinguishes the states via the return value, not a log line.
        return None


def unscored_agent_ids(
    agent_ids: list[str],
    *,
    dsn: str | None = None,
    connect: Callable[[str], Any] | None = None,
) -> list[str]:
    """Of ``agent_ids``, those with a dispatch row but NO scored delta yet.

    Reads the ledger rather than tracking in-process ``score()`` calls, so a back-fill made
    directly via :func:`set_quality` (which the hub round-close currently requires as its interim)
    is correctly seen as scored instead of being reported as still owed.

    ⚠️ **"With a dispatch row" is load-bearing, and the query used to ignore it.** It asked only which
    ids were ``scored`` and returned everything else — so an id that was **never dispatched at all**
    came back as "owed a score", identical to a real unscored run. That is not a cosmetic
    misclassification: the caller's next move is to score what this returns, and scoring a
    never-dispatched id creates an INSERT-only ``scored`` delta with no run behind it — the ORPHAN
    row :meth:`FanoutBatch.score` refuses by name, carrying a real model name into the flywheel.
    Seven such rows already exist upstream.

    MIRROR (what this change costs): a caller using this to detect ids with no row at all no longer
    gets them here. :func:`agent_ids_present` answers exactly that question and always did.

    ⚠️ **The empty list is three answers.** ``[]`` means "nothing is owed", "no DSN configured", or
    "the database could not be read" — this helper is fail-open by design, mirroring the writers, and
    deliberately has no ``reason_sink``. If you need to tell those apart, check the DSN yourself
    before calling; an empty result is never evidence that the runs were scored.
    """
    if not agent_ids:
        return []
    dsn = dsn if dsn is not None else os.getenv("SUBAGENT_RUNS_DSN")
    if not dsn:
        return []
    try:
        conn = connect(dsn) if connect is not None else _connect(dsn)
        with conn, conn.cursor() as cur:
            # Same reasoning as `agent_ids_present`: a read without a statement_timeout
            # can hang forever inside a documented fail-open helper.
            cur.execute("SET LOCAL statement_timeout = 5000")
            # One pass answers BOTH questions per id: is there a dispatch row (any status that is
            # not the INSERT-only `scored` delta), and is there already a scored delta.
            cur.execute(
                "SELECT agent_id, bool_or(status = 'scored'), bool_or(status <> 'scored') "
                "FROM subagent_runs WHERE agent_id = ANY(%s) GROUP BY agent_id",
                (list(agent_ids),),
            )
            state = {r[0]: (bool(r[1]), bool(r[2])) for r in cur.fetchall()}
        return [
            a for a in agent_ids
            if state.get(a, (False, False))[1] and not state.get(a, (False, False))[0]
        ]
    except Exception:  # noqa: BLE001 — fail-open, mirroring the writer
        return []
