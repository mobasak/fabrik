#!/usr/bin/env python3
# AFTER-EDIT: docs/workflows/KILO_AGENT_MANAGEMENT.md
"""
Ticket-outcome telemetry for the Kilo dispatcher.

Writes one row per dispatched ticket to `ticket_outcomes` in
`kilo_agents.db`. The schema is defined in KILO_AGENT_MANAGEMENT.md
(see "Telemetry" section).

Usage from the dispatcher:

    from kilo_telemetry import start_ticket, complete_ticket

    start_ticket(
        ticket_id="T-1234",
        role_called="coding_complex",
        classifier_confidence="keyword:complex",
        priority_used=1,
        agent_used="kilo/google/gemini-3.1-pro-preview",
    )
    # ... run kilo, capture cost + duration ...
    complete_ticket(
        ticket_id="T-1234",
        cost_usd=0.014,
        revisions_needed=0,
        bug_shipped=False,
        duration_seconds=42.3,
    )

The two-phase pattern (start + complete) keeps the classified_at timestamp
honest even when execution is long. If complete_ticket is never called
(crash, timeout), the row still exists with completed_at = NULL — easy to
audit.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / "kilo_agents.db"


# ─── Kilo JSON event-stream parser ────────────────────────────────────────
# When Kilo CLI is invoked with `--format json`, it emits concatenated JSON
# objects (NOT newline-delimited). Each object has a `type` field:
#   - "text"         → carries the model's textual response
#   - "step_finish"  → carries token counts and per-step cost
#   - "error"        → error info
# Mirrors the parser pattern used in scripts/kilo_code_review.py, but
# distilled to the minimum the dispatcher needs.


def parse_kilo_json_stream(raw: str) -> dict[str, Any]:
    """
    Parse Kilo `--format json` output. Returns:
        {
          "text":          concatenated text emitted by the model,
          "cost_usd":      float, summed across step_finish events,
          "input_tokens":  int,   summed,
          "output_tokens": int,   summed,
          "session_id":    str | None,
          "had_step_finish": bool — true iff at least one step_finish seen
                              (false signals an incomplete run; cost = 0
                              should NOT be trusted as "real zero cost"),
          "error":         str | None — first error message if any,
        }
    """
    text_parts: list[str] = []
    cost = 0.0
    input_tokens = 0
    output_tokens = 0
    session_id: str | None = None
    had_step_finish = False
    error_msg: str | None = None

    decoder = json.JSONDecoder()
    s = raw.strip()
    idx = 0
    while idx < len(s):
        # Skip whitespace between objects
        while idx < len(s) and s[idx] in " \t\n\r":
            idx += 1
        if idx >= len(s):
            break
        try:
            obj, end_idx = decoder.raw_decode(s, idx)
        except json.JSONDecodeError:
            idx += 1
            continue
        if end_idx <= idx:
            idx += 1
            continue
        idx = end_idx

        if not isinstance(obj, dict):
            continue

        if "sessionID" in obj:
            session_id = obj["sessionID"]

        event_type = obj.get("type", "")

        if event_type == "error" and error_msg is None:
            err = obj.get("error", {})
            error_msg = err.get("data", {}).get("message") or err.get("name") or str(err)

        elif event_type == "text":
            chunk = obj.get("text") or obj.get("part", {}).get("text") or ""
            if chunk:
                text_parts.append(chunk)

        elif event_type == "step_finish":
            had_step_finish = True
            part = obj.get("part", {})
            tokens = obj.get("tokens") or part.get("tokens", {})
            input_tokens += int(tokens.get("input") or 0)
            output_tokens += int(tokens.get("output") or 0)
            cost += float(obj.get("cost") or part.get("cost") or 0.0)

    return {
        "text": "".join(text_parts),
        "cost_usd": round(cost, 6),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "session_id": session_id,
        "had_step_finish": had_step_finish,
        "error": error_msg,
    }


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"kilo_agents.db not found at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    return conn


def start_ticket(
    ticket_id: str,
    role_called: str,
    classifier_confidence: str,
    priority_used: int | None = None,
    agent_used: str | None = None,
) -> None:
    """
    Insert (or REPLACE) the initial row for a dispatched ticket.

    Always overwrites — if a dispatcher restarts and re-classifies the same
    ticket_id, we want the new role/agent recorded, not the stale one.
    """
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO ticket_outcomes
                (ticket_id, role_called, classifier_confidence, priority_used,
                 agent_used, classified_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                ticket_id,
                role_called,
                classifier_confidence,
                priority_used,
                agent_used,
                datetime.now(UTC).isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def complete_ticket(
    ticket_id: str,
    cost_usd: float | None = None,
    revisions_needed: int = 0,
    bug_shipped: bool = False,
    duration_seconds: float | None = None,
    agent_used: str | None = None,
) -> None:
    """
    Mark a previously-started ticket as complete with cost/duration/outcomes.

    Safe to call even if start_ticket was never invoked — uses INSERT OR
    REPLACE so a row will exist either way. In that case the role/confidence
    columns will be NULL, which is itself a useful signal ("dispatcher
    completed a ticket it never opened").
    """
    conn = _connect()
    try:
        now = datetime.now(UTC).isoformat(timespec="seconds")
        cur = conn.execute("SELECT 1 FROM ticket_outcomes WHERE ticket_id = ?", (ticket_id,))
        exists = cur.fetchone() is not None

        if exists:
            conn.execute(
                """
                UPDATE ticket_outcomes
                   SET cost_usd        = COALESCE(?, cost_usd),
                       revisions_needed = ?,
                       bug_shipped     = ?,
                       duration_seconds = COALESCE(?, duration_seconds),
                       agent_used      = COALESCE(?, agent_used),
                       completed_at    = ?
                 WHERE ticket_id = ?
                """,
                (
                    cost_usd,
                    int(revisions_needed),
                    int(bool(bug_shipped)),
                    duration_seconds,
                    agent_used,
                    now,
                    ticket_id,
                ),
            )
        else:
            # No start_ticket call — record what we have anyway.
            conn.execute(
                """
                INSERT INTO ticket_outcomes
                    (ticket_id, role_called, classifier_confidence, agent_used,
                     cost_usd, revisions_needed, bug_shipped, duration_seconds,
                     classified_at, completed_at)
                VALUES (?, NULL, 'dispatcher-bypass', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket_id,
                    agent_used,
                    cost_usd,
                    int(revisions_needed),
                    int(bool(bug_shipped)),
                    duration_seconds,
                    now,
                    now,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def query_summary(days: int = 30) -> list[dict[str, Any]]:
    """
    Return the standard audit summary — useful for ad-hoc inspection.
    Matches the SQL recommended in KILO_AGENT_MANAGEMENT.md `Telemetry` section.
    """
    conn = _connect()
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            """
            SELECT role_called,
                   classifier_confidence,
                   COUNT(*)                          AS n,
                   ROUND(AVG(revisions_needed), 2)   AS avg_revisions,
                   ROUND(SUM(cost_usd), 2)           AS total_cost_usd,
                   ROUND(AVG(duration_seconds), 1)   AS avg_seconds,
                   SUM(bug_shipped)                  AS bugs_shipped
              FROM ticket_outcomes
             WHERE classified_at > datetime('now', ?)
          GROUP BY role_called, classifier_confidence
          ORDER BY n DESC
            """,
            (f"-{days} days",),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


if __name__ == "__main__":
    # Quick CLI: print the standard summary for the last N days.
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    rows = query_summary(days)
    if not rows:
        print(f"No ticket_outcomes rows in the last {days} days.")
        sys.exit(0)
    print(f"Ticket outcomes — last {days} days:\n")
    header = f"{'role':18} {'confidence':22} {'n':>4} {'avg_rev':>7} {'cost($)':>9} {'avg_s':>7} {'bugs':>5}"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{(r['role_called'] or '-'):18} "
            f"{(r['classifier_confidence'] or '-'):22} "
            f"{r['n']:>4} "
            f"{(r['avg_revisions'] or 0):>7} "
            f"{(r['total_cost_usd'] or 0):>9} "
            f"{(r['avg_seconds'] or 0):>7} "
            f"{(r['bugs_shipped'] or 0):>5}"
        )
