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
    tool_calls    JSONB
);
CREATE INDEX IF NOT EXISTS subagent_runs_task_model_idx ON subagent_runs (task_type, model);
CREATE INDEX IF NOT EXISTS subagent_runs_ts_idx ON subagent_runs (ts);
""".strip()

_INSERT = (
    "INSERT INTO subagent_runs "
    "(project, agent_id, task_type, model, provider, status, cost_usd, turns, "
    "latency_s, quality_score, tool_calls) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)"
)
# The `_INSERT` column order — the outbox serializes a row as a name→value dict so `flush_outbox`
# can rebuild the exact tuple regardless of dict ordering. Keep in lockstep with `_INSERT`.
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
)


def _outbox_path(outbox_dir: str | None) -> Path:
    """The store-and-forward outbox file. Co-located with the ledger under ``<repo>/.tmp/subagents``
    (or ``outbox_dir`` if given). Scored rows land here when the DB is UNREACHABLE (no DSN in dev,
    or a transient failure) so the quality verdict is never lost — :func:`flush_outbox` replays them
    from a machine that CAN reach ``postgres-main`` (the hub)."""
    base = Path(outbox_dir) if outbox_dir else Path(".tmp") / "subagents"
    return base / "pg_outbox.jsonl"


def _append_outbox(row: tuple, outbox_dir: str | None) -> None:
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
    record: dict,
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
        )
    except Exception:  # noqa: BLE001 — fail-open: never raises
        return False
    # Try the DB when a DSN is configured; on ANY miss, outbox the scored delta so it isn't lost.
    if dsn:
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
    good: list[dict] = []
    bad: list[str] = []
    for ln in lines:
        if not ln.strip():
            continue
        try:
            obj = json.loads(ln)
        except Exception:  # noqa: BLE001 — a torn/corrupt line
            bad.append(ln)
            continue
        if isinstance(obj, dict) and all(c in obj for c in _COLS):
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
    try:
        conn = connect(dsn) if connect is not None else _connect(dsn)
        with conn:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = 30000")
                for r in good:
                    cur.execute(_INSERT, tuple(r.get(c) for c in _COLS))
    except Exception:  # noqa: BLE001 — DB failed → the good batch stays in `.flushing` for retry
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
                write_receipt(
                    r.get("agent_id"), r.get("project"), receipt_dir=receipt_dir
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
