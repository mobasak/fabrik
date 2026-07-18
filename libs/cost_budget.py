"""
cost-budget — per-project LLM (and any paid-API) cost caps with a shared
postgres-main ledger + local SQLite write-ahead buffer (fail-open).

Framework-agnostic. Vendor it. The shared cost_ledger table on postgres-main
is provisioned ONCE by the Fabrik postgres registrar at fabrik apply time;
projects do NOT create it.

Decisions (locked in plan v2 § Locked decisions):
  - B2: shared postgres-main ledger + per-project rows + fail-open WAL.
  - LLM provider chain: Claude Code primary (subscription, cost_usd=0)
    with OpenRouter fallback (per-token, real cost_usd). Token counts
    are recorded for BOTH providers so subscription burn is visible per
    project even though dollar cost isn't real-time for Claude Code.

Failure semantics (fail-open):
  - record_cost() writes to local SQLite WAL FIRST (cheap, near-zero
    failure). Then attempts a synchronous postgres-main INSERT. On
    postgres-main unreachable → caller still gets success; the WAL row
    stays queued; replay drains it within ~30s of postgres-main returning.
  - check_caps() reads LOCAL WAL aggregate (pending rows) plus the
    shared postgres-main aggregate. Total = cap check. If postgres-main
    unreachable → uses WAL alone + sets BudgetState.stale=True so the
    caller can decide.
  - drop_to_rule_only_mode() is a pure predicate over BudgetState. The
    host (watchdog) reacts.

Concurrency: single sidecar process per project. No cross-process locking
needed inside one project. If you vendor this into a multi-process service,
SQLite WAL handles concurrent reads but record_cost() should be funneled
through a single writer thread.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

try:
    # Fabrik convention: time-sortable uuid7.
    from uuid_utils.compat import uuid7  # type: ignore
except ImportError:
    from uuid import uuid4 as _uuid4

    def uuid7(timestamp: int | None = None) -> Any:  # type: ignore[misc]  # pragma: no cover
        # signature mirrors uuid_utils.compat.uuid7 (conditional import fallback).
        return _uuid4()


logger = logging.getLogger(__name__)


# ───────────────────────── data shapes ──────────────────────────


@dataclass
class CostEvent:
    """One LLM call's cost telemetry, ready for the ledger."""

    project_id: str
    provider: str  # 'claude-code' | 'openrouter'
    model: str
    in_tokens: int
    out_tokens: int
    cost_usd: float  # 0.0 for claude-code subscription
    incident_id: Optional[str] = None
    action_id: Optional[str] = None

    def to_payload(self) -> dict[str, Any]:
        """Serializable shape for the WAL payload column and the pg INSERT."""
        return {
            "id": str(uuid7()),
            "ts": datetime.now(timezone.utc).isoformat(),
            **asdict(self),
        }


@dataclass
class BudgetState:
    """What the watchdog needs to decide rule-only mode."""

    project_id: str
    daily_usd_spent: float
    daily_usd_cap: float
    daily_invocations_spent: int
    daily_invocations_cap: int
    over_cap: bool  # True once a cap is REACHED (spend == cap is over — see check_caps)
    stale: bool  # True if postgres-main was unreachable when computed

    @property
    def remaining_usd(self) -> float:
        """Budget left today, floored at 0.

        Bound a single call to THIS, not to the full cap: `max_cost_usd=state.remaining_usd`.
        Without it every consumer re-derives `cap - spent` by hand (and some forget to floor it,
        handing a negative budget to the provider).
        """
        return max(0.0, self.daily_usd_cap - self.daily_usd_spent)

    @property
    def remaining_invocations(self) -> int:
        """Invocations left today, floored at 0."""
        return max(0, self.daily_invocations_cap - self.daily_invocations_spent)


# Module-level WAL connection cache. One SQLite handle per wal_path.
_WAL_CONNECTIONS: dict[str, sqlite3.Connection] = {}


# ───────────────────────── core API ──────────────────────────


def record_cost(
    *,
    pg_conn,
    wal_path: str,
    event: CostEvent,
) -> None:
    """Record one cost event. Fail-open on postgres-main.

    Steps:
      1. Generate id + ts; serialize to WAL payload.
      2. INSERT into local SQLite WAL (raises on local failure — that's a
         real bug, not a network condition).
      3. Attempt synchronous postgres-main INSERT.
         - Success → delete WAL row (replayed inline).
         - Failure → leave WAL row queued; replay loop drains later.

    Args:
        pg_conn:  Connection to fabrik_analytics on postgres-main. May be
                  None (forces WAL-only path; useful for tests).
        wal_path: Path to local cost_wal.db.
        event:    CostEvent to record.

    Raises:
        sqlite3.Error: WAL write failed (genuine local bug — caller decides).
    """
    payload = event.to_payload()
    wal_conn = _wal_init(wal_path)

    # Step 1: WAL insert (synchronous, transactional).
    with wal_conn:
        cur = wal_conn.execute(
            "INSERT INTO cost_wal (payload) VALUES (?)",
            (json.dumps(payload, sort_keys=True),),
        )
        wal_seq = cur.lastrowid

    # Step 2: attempt pg insert inline (fail-open).
    if pg_conn is None:
        logger.debug("cost-budget: pg_conn None; row queued in WAL seq=%s", wal_seq)
        return

    try:
        _pg_insert_payload(pg_conn, payload)
    except Exception as e:  # noqa: BLE001 — fail-open is the contract
        logger.warning(
            "cost-budget: postgres-main insert failed (%s); row queued in WAL seq=%s",
            e,
            wal_seq,
        )
        return

    # Step 3: pg succeeded → delete WAL row inline.
    with wal_conn:
        wal_conn.execute("DELETE FROM cost_wal WHERE seq = ?", (wal_seq,))


def replay_wal(
    *,
    pg_conn,
    wal_path: str,
    batch_size: int = 100,
    max_age_seconds: int = 60 * 60 * 24 * 7,
) -> dict[str, int]:
    """Drain WAL rows into postgres-main. Idempotent (ON CONFLICT DO NOTHING).

    Call from the watchdog sidecar's main loop every ~30s, OR from a
    host-project scheduler.

    Args:
        pg_conn:        Connection to fabrik_analytics on postgres-main.
        wal_path:       Path to local cost_wal.db.
        batch_size:     Rows per replay call. 100 is a balanced default.
        max_age_seconds: WAL rows older than this are DROPPED with a
                        warning (postgres-main was down for too long;
                        unbounded WAL would exhaust disk). Default 7 days.

    Returns:
        {'replayed': n, 'failed': m, 'dropped_stale': k}.
    """
    if pg_conn is None:
        return {"replayed": 0, "failed": 0, "dropped_stale": 0}

    wal_conn = _wal_init(wal_path)
    counts = {"replayed": 0, "failed": 0, "dropped_stale": 0}

    # Drop stale rows first.
    cutoff_iso = (
        datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
    ).isoformat()
    with wal_conn:
        stale_cur = wal_conn.execute(
            "DELETE FROM cost_wal WHERE enqueued_at < ?", (cutoff_iso,)
        )
        counts["dropped_stale"] = stale_cur.rowcount or 0
    if counts["dropped_stale"]:
        logger.warning(
            "cost-budget: dropped %s stale WAL rows older than %s seconds",
            counts["dropped_stale"],
            max_age_seconds,
        )

    # Drain a batch.
    rows = wal_conn.execute(
        "SELECT seq, payload FROM cost_wal ORDER BY seq ASC LIMIT ?",
        (int(batch_size),),
    ).fetchall()

    for seq, payload_json in rows:
        payload = json.loads(payload_json)
        try:
            _pg_insert_payload(pg_conn, payload)
        except Exception as e:  # noqa: BLE001
            counts["failed"] += 1
            with wal_conn:
                wal_conn.execute(
                    """
                    UPDATE cost_wal
                       SET attempts = attempts + 1,
                           last_attempt_at = ?
                     WHERE seq = ?
                    """,
                    (datetime.now(timezone.utc).isoformat(), seq),
                )
            logger.debug(
                "cost-budget: replay seq=%s failed (%s); retry next loop", seq, e
            )
            continue

        with wal_conn:
            wal_conn.execute("DELETE FROM cost_wal WHERE seq = ?", (seq,))
        counts["replayed"] += 1

    return counts


def check_caps(
    *,
    pg_conn,
    wal_path: str,
    project_id: str,
    daily_usd_cap: float,
    daily_invocations_cap: int,
    window_start: Optional[datetime] = None,
) -> BudgetState:
    """Aggregate today's spend from postgres-main + WAL; return state.

    If postgres-main is unreachable, fall back to WAL alone and set stale=True.
    The caller decides whether to trust the cap during outage or hold.

    ``over_cap`` is REACHED-not-exceeded (``>=``): spend that lands exactly ON the cap is over.
    With a strict ``>``, a gate that only consults ``drop_to_rule_only_mode`` let one more call
    through at ``spent == cap`` and the day ended slightly over budget.
    """
    if window_start is None:
        window_start = _today_utc_midnight()

    stale = False
    pg_usd, pg_count = 0.0, 0
    if pg_conn is not None:
        try:
            pg_usd, pg_count = _pg_aggregate(pg_conn, project_id, window_start)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "cost-budget: pg aggregate failed (%s); using WAL only; stale=True", e
            )
            stale = True
    elif os.getenv("FABRIK_ANALYTICS_URL"):
        # Analytics IS configured, yet the caller handed us no connection — it could not connect.
        # This must read as stale, not as "$0 spent": a successful `record_cost` DELETES the WAL
        # row, so the WAL does not retain today's cumulative total. Aggregating WAL-only during a
        # pg outage therefore returns ~$0 with over_cap=False — indistinguishable from a genuinely
        # idle day, and the caller would happily spend the whole cap again.
        logger.warning(
            "cost-budget: FABRIK_ANALYTICS_URL is set but no pg_conn was supplied; "
            "WAL-only totals are NOT today's cumulative spend; stale=True"
        )
        stale = True

    wal_usd, wal_count = _wal_aggregate(wal_path, project_id, window_start)

    total_usd = pg_usd + wal_usd
    total_count = pg_count + wal_count
    over_cap = (total_usd >= daily_usd_cap) or (total_count >= daily_invocations_cap)

    return BudgetState(
        project_id=project_id,
        daily_usd_spent=total_usd,
        daily_usd_cap=daily_usd_cap,
        daily_invocations_spent=total_count,
        daily_invocations_cap=daily_invocations_cap,
        over_cap=over_cap,
        stale=stale,
    )


def drop_to_rule_only_mode(state: BudgetState) -> bool:
    """Pure predicate: True if state.over_cap (named hook for rule pack citation)."""
    return state.over_cap


def _escape_prom_label(s: str) -> str:
    """Escape a string for safe use as a Prometheus label value.

    Per the Prometheus exposition format, label values must escape:
      backslash → \\\\
      double-quote → \\"
      newline → \\n
    Without this, a label containing any of those characters produces
    malformed metric lines that the Prometheus parser rejects (one bad
    line invalidates the whole scrape).
    """
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def prometheus_metrics(state: BudgetState) -> str:
    """Render BudgetState as Prometheus text-format metrics."""
    label = _escape_prom_label(state.project_id)
    return (
        f'llm_cost_dollars_total{{project="{label}"}} {state.daily_usd_spent}\n'
        f'llm_cost_dollars_cap{{project="{label}"}} {state.daily_usd_cap}\n'
        f'llm_invocations_total{{project="{label}"}} {state.daily_invocations_spent}\n'
        f'llm_invocations_cap{{project="{label}"}} {state.daily_invocations_cap}\n'
        f'cost_budget_over_cap{{project="{label}"}} {1 if state.over_cap else 0}\n'
        f'cost_budget_stale{{project="{label}"}} {1 if state.stale else 0}\n'
    )


def wal_stuck_count(*, wal_path: str, threshold_attempts: int = 5) -> int:
    """Count WAL rows with attempts >= threshold (Prometheus metric source)."""
    wal_conn = _wal_init(wal_path)
    row = wal_conn.execute(
        "SELECT COUNT(*) FROM cost_wal WHERE attempts >= ?", (threshold_attempts,)
    ).fetchone()
    return int(row[0]) if row else 0


# ───────────────────────── internals ──────────────────────────


def _wal_init(wal_path: str) -> sqlite3.Connection:
    """Open (or reuse) a SQLite connection to the WAL DB. Applies schema if needed."""
    conn = _WAL_CONNECTIONS.get(wal_path)
    if conn is not None:
        return conn

    Path(wal_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        wal_path, isolation_level="DEFERRED", check_same_thread=False
    )
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    # Apply schema (idempotent).
    schema_path = Path(__file__).resolve().parent / "schema_sqlite.sql"
    if schema_path.exists():
        conn.executescript(schema_path.read_text(encoding="utf-8"))
    else:
        # Fallback inline DDL for cases where the .sql sidecar file isn't shipped.
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS cost_wal (
                seq             INTEGER PRIMARY KEY AUTOINCREMENT,
                payload         TEXT    NOT NULL,
                enqueued_at     TEXT    NOT NULL DEFAULT (datetime('now', 'utc')),
                last_attempt_at TEXT,
                attempts        INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_cost_wal_seq ON cost_wal (seq);
            """
        )
    conn.commit()
    _WAL_CONNECTIONS[wal_path] = conn
    return conn


def _pg_insert_payload(pg_conn, payload: dict[str, Any]) -> None:
    """INSERT a cost_ledger row from the canonical payload. Idempotent via PK."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO cost_ledger
                (id, project_id, ts, provider, model,
                 in_tokens, out_tokens, cost_usd,
                 incident_id, action_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                payload["id"],
                payload["project_id"],
                payload["ts"],
                payload["provider"],
                payload["model"],
                payload["in_tokens"],
                payload["out_tokens"],
                payload["cost_usd"],
                payload.get("incident_id"),
                payload.get("action_id"),
            ),
        )
    # Durability is REQUIRED here: record_cost()/replay_wal() delete the WAL row
    # as soon as this returns, so the insert must be committed now — not left to
    # the caller's connection mode. Without this, a default (non-autocommit)
    # psycopg2 connection would buffer the INSERT, the WAL row would be deleted,
    # and the cost event would be lost from BOTH stores. A no-op on autocommit.
    pg_conn.commit()


def _pg_aggregate(
    pg_conn, project_id: str, window_start: datetime
) -> tuple[float, int]:
    """Return (sum_cost_usd, count_calls) since window_start for project_id."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(SUM(cost_usd), 0), COUNT(*)
            FROM cost_ledger
            WHERE project_id = %s AND ts >= %s
            """,
            (project_id, window_start),
        )
        row = cur.fetchone()
    return (float(row[0]), int(row[1])) if row else (0.0, 0)


def _wal_aggregate(
    wal_path: str, project_id: str, window_start: datetime
) -> tuple[float, int]:
    """Sum pending WAL rows for project_id since window_start."""
    wal_conn = _wal_init(wal_path)
    rows = wal_conn.execute("SELECT payload FROM cost_wal").fetchall()
    total_usd = 0.0
    total_count = 0
    # Compare as tz-aware datetimes, NOT ISO strings: a lexicographic compare is
    # wrong across UTC offsets (e.g. "...+03:00" vs a "...+00:00" payload), which
    # would make the WAL window disagree with the pg window for a non-UTC caller.
    if window_start.tzinfo is None:
        window_start = window_start.replace(tzinfo=timezone.utc)
    for (payload_json,) in rows:
        payload = json.loads(payload_json)
        if payload.get("project_id") != project_id:
            continue
        try:
            ts = datetime.fromisoformat(payload.get("ts", ""))
        except ValueError:
            continue  # unparseable ts — skip rather than miscount
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts < window_start:
            continue
        total_usd += float(payload.get("cost_usd", 0.0))
        total_count += 1
    return (total_usd, total_count)


def _today_utc_midnight() -> datetime:
    """Return today's 00:00 UTC."""
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


__all__ = (
    "CostEvent",
    "BudgetState",
    "record_cost",
    "replay_wal",
    "check_caps",
    "drop_to_rule_only_mode",
    "prometheus_metrics",
    "wal_stuck_count",
)
