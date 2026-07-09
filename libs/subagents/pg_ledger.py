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

``quality_score`` is the one field the ORCHESTRATOR records after judging (it is a verdict,
not a measurement); the objective columns are captured automatically from the run.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
from typing import Any, Callable

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
    "latency_s, quality_score, tool_calls, reachable_at_dispatch) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)"
)


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
) -> bool:
    """Best-effort INSERT one ledger record into the shared ``subagent_runs`` table.

    FAIL-OPEN: returns ``False`` on ANY error (no DSN, unreachable DB, missing table, driver
    absent) and NEVER raises — the JSONL ledger is the durable copy. Returns ``True`` only on
    a committed insert. ``dsn``/``project`` default to env ``SUBAGENT_RUNS_DSN`` /
    ``SUBAGENT_PROJECT``. ``connect`` is an injectable connection factory for offline tests.
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
        if not dsn:
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
            # Plan-1 Phase C: reachable_at_dispatch — 1 if pick_models had the
            # model in the reachable-set at dispatch, 0 if it fell through the
            # empty-pool WARN, None if the caller didn't wire it. NULL is OK
            # (nullable column); the flywheel treats NULL as "unknown".
            record.get("reachable_at_dispatch"),
        )
    except Exception:  # noqa: BLE001 — fail-open: a malformed record never raises
        return False
    try:
        conn = connect(dsn) if connect is not None else _connect(dsn)
    except Exception:  # noqa: BLE001 — fail-open: connect failure is never fatal
        return False
    try:
        with conn:  # psycopg: commits on clean exit, rolls back on error
            with conn.cursor() as cur:
                # bound the INSERT to 5s WITHOUT clobbering the DSN's own connect options —
                # SET LOCAL scopes to this transaction only
                cur.execute("SET LOCAL statement_timeout = 5000")
                cur.execute(_INSERT, row)
        return True
    except Exception:  # noqa: BLE001 — fail-open: a bad insert never breaks the run
        return False
    finally:
        with contextlib.suppress(Exception):
            conn.close()


def record_agent_run(
    spec: object,
    result: object,
    *,
    quality_score: float | None = None,
    project: str | None = None,
    dsn: str | None = None,
    connect: Callable[[str], Any] | None = None,
    receipt_dir: str | None = None,
    reachable_at_dispatch: int | None = None,
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
        # Plan-1 Phase C: thread reachable_at_dispatch into the record so
        # record_run's INSERT picks it up. Kept None-safe: an omitted kwarg
        # writes NULL (semantically "unknown", not 0).
        if reachable_at_dispatch is not None:
            record["reachable_at_dispatch"] = reachable_at_dispatch
    except Exception:  # noqa: BLE001 — fail-open: a malformed spec/result never raises
        return False
    ok = record_run(
        record, dsn=dsn, project=project, quality_score=quality_score, connect=connect
    )
    if ok:
        # receipt ONLY on a confirmed insert — best-effort, never raises.
        write_receipt(record.get("agent_id"), project, receipt_dir=receipt_dir)
    return ok


__all__ = ["SUBAGENT_RUNS_DDL", "record_run", "record_agent_run"]
