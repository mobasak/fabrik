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
    session_id    TEXT
);
CREATE INDEX IF NOT EXISTS subagent_runs_task_model_idx ON subagent_runs (task_type, model);
CREATE INDEX IF NOT EXISTS subagent_runs_ts_idx ON subagent_runs (ts);
-- Added 2026-08-15 with the session_id column. A table created from an OLDER copy of
-- this DDL needs the column added before this module can write to it at all:
--     ALTER TABLE subagent_runs ADD COLUMN IF NOT EXISTS session_id TEXT;
""".strip()

_INSERT = (
    "INSERT INTO subagent_runs "
    "(project, agent_id, task_type, model, provider, status, cost_usd, turns, "
    "latency_s, quality_score, tool_calls, session_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)"
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
    name = type(exc).__name__
    if name in {"OperationalError", "InterfaceError", "PoolError", "AdminShutdown"}:
        return True
    text = str(exc).lower()
    if any(k in text for k in ("could not connect", "server closed", "connection", "timeout")):
        return True
    # Rejections of the ROW: constraint/type/column problems. Anything explicitly in this
    # family is poison; anything else falls through to transient.
    return name not in {
        "IntegrityError", "DataError", "ProgrammingError", "NotSupportedError", "ValueError",
    }


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

    if poison and not transient:
        with contextlib.suppress(Exception):
            q = base / "pg_outbox.quarantine.jsonl"
            with q.open("a", encoding="utf-8") as fh:
                for r, why in poison:
                    fh.write(json.dumps({"row": r, "error": why}, default=str) + "\n")
                fh.flush()
    # A transient failure anywhere means the batch is NOT finished: report nothing landed so
    # `.flushing` is retried intact, rather than declaring partial success and dropping the
    # rows that never got their chance.
    # ⚠ EVERY row ends up in exactly one of `landed`, `poison`, or (on a transient) back in
    # the retry path. The first version keyed both the quarantine and the return on a
    # `reachable` latch, so a row failing BEFORE the first success was in none of them — not
    # landed, not quarantined, not retried. It simply vanished, and these are the scored rows
    # the outbox exists to protect.
    if transient:
        return [], False  # nothing is finished; `.flushing` must survive intact
    assert len(landed) + len(poison) == len(rows)  # noqa: S101 — accounting invariant
    return landed, True


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
) -> bool:
    """Judge-once flywheel write for a (spec, result) pair — the call an orchestrator SHOULD use.

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
        # AUTO-0 for the one failure every other net misses (upstream report from /opt/fabrik,
        # 2026-08-12, hub plan-2 C4): a run whose status is "done" but whose OUTPUT is empty or
        # whitespace "succeeded" with nothing gradeable. `success_rate` cannot see it — the run
        # succeeded. `record_run`'s error/capped NULL-coercion does not apply — the status IS done.
        # That empty output IS a 0-quality verdict, so record it as one.
        #
        # ⚠ Deliberately NOT extended to error/capped: those are INFRA failures, and teaching the
        # ranker a 0 for an infra failure is a false zero — the ranker's `success_rate` already
        # punishes them. Only when the caller passed no score: an explicit judgment always wins.
        if quality_score is None:
            _txt = getattr(result, "text", None)
            # ⚠ The diff clause is LOAD-BEARING, not a redundant None-check. A mode="write"
            # coder's value IS its diff: it returns the work as a patch and often says nothing in
            # `text`. Judging it on `text` alone auto-scores real work 0 — the same false zero the
            # comment above warns against, aimed at ourselves, and it teaches the ranker to
            # down-rank coders. Only test_write_unit_with_diff_but_empty_text_stays_null shows
            # this; the clause is invisible to inspection, so keep the test adjacent to it.
            # Reported upstream by intel 2026-08-15 after their copy was overwritten twice by our
            # sync — a vendored copy cannot hold a fix against its own upstream.
            _diff = getattr(result, "diff", None)
            if (
                str(record.get("status") or "") == "done"
                and isinstance(_txt, str)
                and not _txt.strip()
                and not (isinstance(_diff, str) and _diff.strip())
            ):
                quality_score = 0.0
    except Exception:  # noqa: BLE001 — fail-open: a malformed spec/result never raises
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
    ``receipt_dir`` are the injectable DB factory + receipt location, as on :func:`record_agent_run`."""
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
        )
    except Exception:  # noqa: BLE001 — fail-open: never raises
        return False
    # Try the DB when a DSN is configured; on ANY miss, outbox the scored delta so it isn't lost.
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
        present = agent_ids_present([str(agent_id)], dsn=dsn, connect=connect)
        if present is not None and str(agent_id) not in present:
            # ⚠ Absent from the DB is NOT automatically an orphan. If the dispatch row is
            # pending in our own outbox it WILL land, and discarding the verdict here threw
            # away the flywheel's most valuable signal during precisely the outage the
            # outbox exists to survive — while the docstring promised it was preserved.
            # Fall through to the outbox so the score lands AFTER its dispatch row.
            if not _agent_id_pending_in_outbox(str(agent_id), outbox_dir):
                return False  # genuine orphan: the run does not exist, so the score is not real
            _append_outbox(row, outbox_dir)
            return False  # not committed to the DB — the caller must not read this as landed
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
        except Exception:  # noqa: BLE001 — fail-open: unreachable/bad insert → outbox below
            pass
        finally:
            if conn is not None:
                with contextlib.suppress(Exception):
                    conn.close()
    # No DSN (dev) or the DB write failed → capture the scored delta locally for flush_outbox.
    _append_outbox(row, outbox_dir if outbox_dir is not None else receipt_dir)
    return False


def flush_outbox(
    dsn: str | None = None,
    *,
    outbox_dir: str | None = None,
    connect: Callable[[str], Any] | None = None,
    receipt_dir: str | None = None,
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
        (atomic); a concurrent :func:`_append_outbox` lands in the claimed file or a fresh live, never a
        lost gap. A batch already pending in ``.flushing`` (a prior crash / DB outage) is processed
        first and ``live`` is left to accumulate (claimed next run) — there is NO file-merging, so no
        merge-crash double-insert or non-atomic-rewrite loss.
      * **Poison-proof** — parsed LINE BY LINE; any MALFORMED line (bad JSON from a torn write, a
        non-dict, or a row missing a required column) is quarantined to ``pg_outbox.corrupt.jsonl`` and
        the good rows still flush — a malformed line can't brick the batch. (A well-formed row a healthy
        DB rejects is left in ``.flushing`` for a maintainer; ``_append_outbox`` never produces one.)
    On a DB failure the batch stays in ``.flushing`` for the next run. A crash BETWEEN commit and cleanup
    can re-insert the batch once (at-least-once — a rare, minor skew for an aggregate flywheel;
    exactly-once would need a unique dedup key on the shared schema, a hub-coordinated change). FAIL-OPEN:
    never raises; returns the number of rows flushed (0 on any error / no DSN / lock held / empty)."""
    try:
        import fcntl

        dsn = dsn or os.getenv("SUBAGENT_RUNS_DSN")
        if not dsn:
            return 0
        live = _outbox_path(outbox_dir)
        base = live.parent
        flushing = base / "pg_outbox.flushing.jsonl"
        if not live.exists() and not flushing.exists():
            return 0
        base.mkdir(parents=True, exist_ok=True)
        lock_fh = (base / "pg_outbox.lock").open("w", encoding="utf-8")
    except Exception:  # noqa: BLE001 — fail-open: setup failure never raises
        return 0
    try:
        try:
            fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception:  # noqa: BLE001 — another flush holds the lock → skip cleanly
            return 0
        return _flush_locked(dsn, live, flushing, base, connect, receipt_dir)
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
) -> int:
    """The flush critical section, run under the outbox lock. See :func:`flush_outbox`.

    Deliberately NO file-merging (no staging file): if a batch is already pending in ``flushing`` (a
    prior run crashed, or the DB was down), process THAT this run and leave ``live`` to accumulate —
    it's claimed on the next flush. The only file mutations are an atomic ``os.replace`` claim and the
    post-commit ``unlink``, so the sole at-least-once window is a crash between commit and unlink (a
    prior over-clever staging/merge introduced a double-insert + a non-atomic-rewrite loss; both gone)."""
    # 1) Claim the batch. A pending `.flushing` is processed first (live untouched); else atomically
    #    claim `live` → `flushing` (a concurrent append lands in a fresh `live`, never a lost gap).
    if not flushing.exists():
        if not live.exists():
            return 0
        try:
            os.replace(live, flushing)
        except Exception:  # noqa: BLE001 — fail-open: a claim failure leaves the file for the next run
            return 0
    # 2) Parse LINE BY LINE — anything that is not a COMPLETE _COLS dict (bad JSON, a non-dict, or a row
    #    missing a required column from a stale/cross-version outbox) is quarantined so ONE malformed
    #    line can never brick the good rows.
    try:
        lines = flushing.read_text(encoding="utf-8").splitlines()
    except Exception:  # noqa: BLE001
        return 0
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
        return 0
    # 3) INSERT the good rows in one transaction.
    conn = None
    # ⚠ Distinguishes an EXECUTE-phase failure from a COMMIT-phase one, because only the
    # first is safe to retry row-by-row. `with conn:` commits at __exit__; if THAT fails
    # (network drop, server restart, pooler kill) the server may well have committed
    # already, and re-inserting every row would be a GUARANTEED full-batch duplicate
    # rather than the rare crash-window the module documents. A commit-phase failure
    # therefore leaves `.flushing` intact for a normal retry, exactly as before.
    execute_failed = False
    try:
        conn = connect(dsn) if connect is not None else _connect(dsn)
        with conn:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = 30000")
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
        if not execute_failed:
            return 0  # commit-phase: in doubt, so retry the batch rather than duplicate it
        good, all_accounted = _flush_row_by_row(good, dsn, connect, base)
        if not all_accounted:
            return 0  # transient: leave `.flushing` intact for a clean retry
        if not good:
            # Every row was rejected. They are quarantined, so the batch is FINISHED —
            # dropping through unlinks `.flushing`. Returning early here (as the first
            # version did) left it in place to be retried identically forever, which is
            # the permanent-loop bug this fallback exists to fix, unfixed.
            with contextlib.suppress(Exception):
                flushing.unlink()
            return 0
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
    return len(good)


__all__ = [
    "SUBAGENT_RUNS_DDL",
    "record_run",
    "record_agent_run",
    "set_quality",
    "flush_outbox",
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
            cur.execute(
                "SELECT DISTINCT agent_id FROM subagent_runs "
                "WHERE agent_id = ANY(%s) AND status = 'scored'",
                (list(agent_ids),),
            )
            scored = {r[0] for r in cur.fetchall()}
        return [a for a in agent_ids if a not in scored]
    except Exception:  # noqa: BLE001 — fail-open, mirroring the writer
        return []
