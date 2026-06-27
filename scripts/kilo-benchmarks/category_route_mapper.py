#!/usr/bin/env python3
"""Category-route orchestrator — sibling to `embedding_role_mapper.py`.

Phase 3 of the OpenRouter routing plan
(`docs/development/plans/2026-06-27-plan-openrouter-routing.md` §9.2).

End-to-end daily flow:

  1. Load `ai_category_configs.yaml`.
  2. For each category, call `category_selector.select_for_category()`
     to get the top-N candidates per `slots`.
  3. Catch `NoEligibleCategoryError` per category (don't crash the
     whole run) — emit a graceful empty-routes entry per plan §9.2.
  4. Persist winners to `agent_roles` with `role = 'openrouter:{cat}'`
     and `assigned_by = 'category_route_mapper'`. Upsert today's
     snapshot in `agent_roles_history`.
  5. Emit two JSON files that mirror the embedding pipeline output:
       - `scripts/kilo-benchmarks/openrouter_routes.json` (full detail)
       - `scripts/kilo_openrouter_routes_final.json` (compact for
         Traycer / downstream consumers)

Idempotent: running twice on the same day overwrites `agent_roles`
for the openrouter:* keys and upserts today's history rows (UNIQUE on
snapshot_date). Determinism: same DB + same YAML → byte-identical JSON
output.

Pass B Finding 3 contract: PRAGMA foreign_keys = ON set on the DB
connection before any agent_roles writes.

Plan §9.2 zero-eligible contract: every category appears in the output
JSON with either `routes: [...]` or `routes: [], reason: "..."`.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from category_selector import (  # noqa: E402
    NoEligibleCategoryError,
    select_for_category,
)

DB_PATH = SCRIPT_DIR / "kilo_agents.db"
CONFIG_PATH = SCRIPT_DIR / "ai_category_configs.yaml"
ROUTES_JSON_PATH = SCRIPT_DIR / "openrouter_routes.json"
TRAYCER_EXPORT_PATH = SCRIPT_DIR.parent / "kilo_openrouter_routes_final.json"

ASSIGNED_BY = "category_route_mapper"
ROLE_PREFIX = "openrouter:"


def _log(msg: str) -> None:
    print(f"[category_route_mapper] {msg}")


def _utc_today_iso() -> str:
    """Today's UTC date in ISO format — matches SQLite's `DATE('now')`."""
    return datetime.now(UTC).date().isoformat()


def _persist_to_agent_roles(
    conn: sqlite3.Connection,
    routes: dict[str, list[dict[str, Any]]],
    today_iso: str,
) -> None:
    """Overwrite openrouter:* rows in agent_roles + upsert today's history.

    Only touches roles that start with ROLE_PREFIX — chat-side rows
    (`assigned_by='cheapest-above-floors'`) are untouched (Pass 1D D5
    rollback safety + Pass A Finding 6 verified). The pre-check `DELETE
    WHERE role LIKE 'openrouter:%'` can never widen its scope because
    ROLE_PREFIX is a hardcoded literal — no user input.

    Idempotency contract — Pass A Finding 2 fix: the live
    `agent_roles_history` table does NOT carry a UNIQUE constraint
    (verified live 2026-06-27), so `INSERT OR REPLACE` would behave as
    plain INSERT and double the history rows on every re-run within a
    day. Restored idempotency with explicit DELETE-by-day-then-INSERT:
    we delete today's openrouter:* history rows before inserting, so
    running the mapper twice on the same UTC day produces one set of
    rows, not two.

    Atomicity contract — Pass B Finding 1 fix: Python sqlite3's default
    isolation_level='' (deferred) does NOT auto-rollback on a failed
    statement — `conn.commit()` after a mid-loop IntegrityError would
    commit the prior DELETEs anyway, dropping today's history without
    re-populating it. Wrapped in explicit `BEGIN ... COMMIT / ROLLBACK`
    so the DELETE + INSERT loop is all-or-nothing.

    Cross-midnight UTC race fix (full-surface Pass 1 F3): SQLite's
    `DATE('now')` is evaluated per-statement, NOT per-transaction. If
    the BEGIN…COMMIT spans 00:00 UTC, the DELETE may match day N rows
    while INSERTs land with day N+1 timestamps — zero history rows
    for the day that was 'today' at start. Caller now computes
    `today_iso = datetime.now(UTC).date().isoformat()` ONCE and binds
    it to both the DELETE and the INSERTs.

    Pass 7 F1 fix — commit moved OUT of this function and into `run()`
    so the BEGIN/COMMIT envelope spans the promote step too. If the
    promote fails after `_persist_to_agent_roles` returns, `run()`
    rolls back the DB and JSON snapshots restore — both stores end on
    yesterday. Previously the commit landed before the promote, so a
    promote failure left the DB on today and the JSON on yesterday.
    """
    try:
        conn.execute("BEGIN")
        conn.execute(
            "DELETE FROM agent_roles WHERE role LIKE ?",
            (f"{ROLE_PREFIX}%",),
        )
        conn.execute(
            "DELETE FROM agent_roles_history WHERE role LIKE ? AND DATE(assigned_at) = ?",
            (f"{ROLE_PREFIX}%", today_iso),
        )
        _do_inserts(conn, routes, today_iso)
    except Exception:
        conn.rollback()
        raise
    # NB: caller owns the commit — happens AFTER the JSON promote so a
    # promote failure rolls back the DB and avoids DB↔JSON split-brain.


def _do_inserts(
    conn: sqlite3.Connection,
    routes: dict[str, list[dict[str, Any]]],
    today_iso: str,
) -> None:
    """Pure INSERTs — the BEGIN/COMMIT wrapper lives in
    `_persist_to_agent_roles` (Pass B Finding 1 atomicity contract).
    """
    for category, winners in routes.items():
        role = f"{ROLE_PREFIX}{category}"
        for priority, row in enumerate(winners, start=1):
            conn.execute(
                "INSERT INTO agent_roles "
                "(role, agent_id, priority, reason, score_used, score_type, assigned_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    role,
                    row["id"],
                    priority,
                    row.get("reason", ""),
                    row["score_used"],
                    row["score_type"],
                    ASSIGNED_BY,
                ),
            )
            # Today's history snapshot. assigned_at set by SQLite (UTC)
            # so writer + reader agree across timezones.
            conn.execute(
                "INSERT INTO agent_roles_history "
                "(role, agent_id, priority, reason, min_elo, "
                " score_used, score_type, assigned_by, assigned_at) "
                "VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?)",
                (
                    role,
                    row["id"],
                    priority,
                    row.get("reason", ""),
                    row["score_used"],
                    row["score_type"],
                    ASSIGNED_BY,
                    today_iso,
                ),
            )
    # NB: no commit here — `_persist_to_agent_roles` owns the
    # BEGIN/COMMIT/ROLLBACK envelope.


def _emit_routes_json(
    routes: dict[str, list[dict[str, Any]]],
    skipped: dict[str, str],
    routes_json_path: Path,
    today_iso: str,
) -> None:
    """Write the full-detail openrouter_routes.json."""
    payload = {
        "generated_at": today_iso,
        "assigned_by": ASSIGNED_BY,
        "categories": {},
    }
    # Every config'd category appears in the output — either with routes
    # or with an explicit zero-eligible explanation. Per plan §9.2.
    for category, winners in routes.items():
        payload["categories"][category] = {
            "routes": [
                {
                    "priority": idx + 1,
                    "id": row["id"],
                    "provider": row["provider"],
                    "input_cost_per_m": row["input_cost_per_m"],
                    "output_cost_per_m": row["output_cost_per_m"],
                    "context_window_k": row["context_window_k"],
                    "has_vision": bool(row.get("has_vision")),
                    "has_tools": bool(row.get("has_tools")),
                    "has_reasoning": bool(row.get("has_reasoning")),
                    "is_ga": bool(row.get("is_ga")),
                    "score_used": row["score_used"],
                    "score_type": row["score_type"],
                    "reason": row.get("reason", ""),
                }
                for idx, row in enumerate(winners)
            ],
            "reason": "",
        }
    for category, reason in skipped.items():
        payload["categories"][category] = {"routes": [], "reason": reason}
    routes_json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _emit_traycer_export(
    routes: dict[str, list[dict[str, Any]]],
    skipped: dict[str, str],
    traycer_export_path: Path,
    today_iso: str,
) -> None:
    """Compact category → priority → model id mapping for downstream."""
    payload: dict[str, Any] = {
        "generated_at": today_iso,
        "categories": {},
    }
    for category, winners in routes.items():
        payload["categories"][category] = {
            str(idx + 1): row["id"] for idx, row in enumerate(winners)
        }
    for category in skipped:
        payload["categories"][category] = {}
    traycer_export_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _snapshot_and_promote(
    routes_tmp: Path,
    routes_final: Path,
    traycer_tmp: Path,
    traycer_final: Path,
) -> dict[str, Path | bool]:
    """Snapshot the prior state of both final paths to *.bak, then
    promote tmp→final. Returns a dict with the bak paths + had-snapshot
    flags so the caller can defer cleanup until the DB commit succeeds.

    Pass 8 F1 contract: the .bak files MUST survive across the caller's
    `conn.commit()` so that a commit failure can restore yesterday's
    JSON state (DB rolled back to yesterday → JSON also restored to
    yesterday → no DB↔JSON split-brain).

    Pass 6 F-B contract preserved: if the SECOND `os.replace` raises,
    the FIRST file is restored from its snapshot before re-raising.
    """
    routes_bak = routes_final.with_suffix(routes_final.suffix + ".bak")
    traycer_bak = traycer_final.with_suffix(traycer_final.suffix + ".bak")

    routes_had_snapshot = False
    traycer_had_snapshot = False
    routes_promoted = False
    traycer_promoted = False

    # Pass 9 fix: snapshot and promote both sit inside the try block so
    # any failure triggers `_restore_snapshots`. Per-file `_promoted`
    # flags let the restore distinguish:
    #   - snapshot-phase failure (promote not run) → leave non-snapshotted
    #     finals alone (they still hold yesterday)
    #   - promote-phase failure → unlink finals that got today's content
    #     but had no prior state to restore
    try:
        if routes_final.exists():
            os.replace(routes_final, routes_bak)
            routes_had_snapshot = True
        if traycer_final.exists():
            os.replace(traycer_final, traycer_bak)
            traycer_had_snapshot = True
        os.replace(routes_tmp, routes_final)
        routes_promoted = True
        _log(f"wrote {routes_final}")
        os.replace(traycer_tmp, traycer_final)
        traycer_promoted = True
        _log(f"wrote {traycer_final}")
    except OSError as e:
        _log(
            f"CRITICAL: snapshot/promote failed mid-flight "
            f"({type(e).__name__}: {e}); restoring pre-state snapshots"
        )
        _restore_snapshots(
            routes_final,
            routes_bak,
            routes_had_snapshot,
            routes_promoted,
            traycer_final,
            traycer_bak,
            traycer_had_snapshot,
            traycer_promoted,
        )
        for tmp in (routes_tmp, traycer_tmp):
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass
        raise

    # Both promotes succeeded by the time we return — used by the
    # post-commit-failure restore path in `run()` to know whether the
    # final paths should be unlinked (no prior snapshot) or restored
    # from their .bak (had a prior snapshot).
    return {
        "routes_bak": routes_bak,
        "routes_had_snapshot": routes_had_snapshot,
        "routes_promoted": True,
        "traycer_bak": traycer_bak,
        "traycer_had_snapshot": traycer_had_snapshot,
        "traycer_promoted": True,
        "routes_final": routes_final,
        "traycer_final": traycer_final,
    }


def _restore_snapshots(
    routes_final: Path,
    routes_bak: Path,
    routes_had: bool,
    routes_promoted: bool,
    traycer_final: Path,
    traycer_bak: Path,
    traycer_had: bool,
    traycer_promoted: bool,
) -> None:
    """Best-effort restore both final paths from their .bak snapshots.

    The `_promoted` flag distinguishes "this run wrote today's content
    to final" from "this run didn't touch final". If we promoted and
    there was no prior snapshot, we unlink final (it was created by
    this run and should be rolled back to its prior 'did not exist'
    state). If we DIDN'T promote and there was no snapshot, final still
    holds whatever it did before this run — leave it alone.
    """
    for final, bak, had, promoted in (
        (routes_final, routes_bak, routes_had, routes_promoted),
        (traycer_final, traycer_bak, traycer_had, traycer_promoted),
    ):
        if had:
            try:
                os.replace(bak, final)
            except OSError as rerr:
                _log(f"CRITICAL: failed to restore {final}: {rerr}")
        elif promoted and final.exists():
            try:
                final.unlink()
            except OSError:
                pass


def _cleanup_snapshots(snapshot_state: dict[str, Path | bool]) -> None:
    """Delete the .bak files after a successful DB commit. Best-effort —
    a permission error on .bak cleanup AFTER both DB and JSON committed
    to today is operator-noise, not a coherence problem (the stale .bak
    file is harmless clutter that the next run overwrites)."""
    for key in ("routes_bak", "traycer_bak"):
        bak = snapshot_state[key]
        try:
            bak.unlink()
        except OSError:
            pass


def run(
    db_path: Path | str = DB_PATH,
    config_path: Path | str = CONFIG_PATH,
    routes_json_path: Path | str | None = None,
    traycer_export_path: Path | str | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    """Run the full route mapping pipeline. Returns (routes, skipped).

    Full-surface Pass 1 F1 fix: `routes_json_path` and
    `traycer_export_path` are now keyword args so an ad-hoc caller
    passing `db_path=/tmp/staging.db` no longer silently clobbers the
    production JSON files that `category_export_markdown.py` reads
    downstream. None sentinels resolve to the current module-level
    constants at call time (preserves monkeypatch ergonomics for tests).
    """
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    categories = cfg.get("categories", {})

    routes_json_path = Path(routes_json_path) if routes_json_path is not None else ROUTES_JSON_PATH
    traycer_export_path = (
        Path(traycer_export_path) if traycer_export_path is not None else TRAYCER_EXPORT_PATH
    )
    today_iso = _utc_today_iso()

    routes: dict[str, list[dict[str, Any]]] = {}
    skipped: dict[str, str] = {}

    for category, cat_cfg in categories.items():
        try:
            winners = select_for_category(category, cat_cfg, db_path=db_path)
        except NoEligibleCategoryError as e:
            _log(f"{category}: NO ELIGIBLE — {e}")
            skipped[category] = str(e)
            continue
        except ValueError as e:
            _log(f"{category}: CONFIG ERROR — {e}")
            skipped[category] = f"config error: {e}"
            continue

        reason = (cat_cfg.get("notes") or "").strip()
        for w in winners:
            w["reason"] = reason
        routes[category] = winners
        ids = [w["id"] for w in winners]
        _log(f"{category}: {len(winners)} routes → {ids}")

    # Pass 5 F3 fix: write JSON outputs to *.tmp + os.replace BEFORE the
    # DB commit, so the disk + DB end states are coupled. If either JSON
    # path is unwritable, the DB transaction is rolled back via the
    # `except` in `_persist_to_agent_roles` (no openrouter:* pins land,
    # no history rows land).
    #
    # Pass 5 F1 fix: PRAGMA now runs inside the try/finally so an
    # OperationalError on PRAGMA doesn't leak the connection.
    #
    # Pass 6 F-B fix: the two-replace promotion was non-atomic — if the
    # second `os.replace` failed (cross-device move, EACCES, ENOSPC),
    # routes.json showed today while traycer.json still showed yesterday.
    # Mitigation: snapshot the pre-state of both final paths to .bak BEFORE
    # replacing, then on any replace failure restore the snapshots so the
    # two consumers stay coherent. Cannot make the two-rename truly atomic
    # without two-phase commit, but the snapshot+restore closes the
    # observable window: end-state is either "both today" or "both
    # yesterday" — never split-brain.
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("PRAGMA foreign_keys could not be enabled.")
        routes_tmp = routes_json_path.with_suffix(routes_json_path.suffix + ".tmp")
        traycer_tmp = traycer_export_path.with_suffix(traycer_export_path.suffix + ".tmp")
        try:
            _emit_routes_json(routes, skipped, routes_tmp, today_iso)
            _emit_traycer_export(routes, skipped, traycer_tmp, today_iso)
        except OSError:
            for p in (routes_tmp, traycer_tmp):
                try:
                    p.unlink()
                except FileNotFoundError:
                    pass
            raise
        _persist_to_agent_roles(conn, routes, today_iso)
        # Pass 7 F1 + Pass 8 F1: the DB transaction stays OPEN across
        # the promote step AND the commit. The .bak snapshots are kept
        # alive across the commit so a commit failure (WAL checkpoint,
        # ENOSPC at fsync, busy timeout) can restore the JSON to
        # yesterday's state — matching the DB rollback. Without this,
        # the JSON would advertise today while the DB had rolled back
        # to yesterday.
        snapshot_state: dict[str, Path | bool] | None = None
        try:
            snapshot_state = _snapshot_and_promote(
                routes_tmp,
                routes_json_path,
                traycer_tmp,
                traycer_export_path,
            )
        except Exception:
            try:
                conn.rollback()
            except Exception as rerr:
                _log(
                    f"CRITICAL: rollback after promote failure also raised "
                    f"({type(rerr).__name__}: {rerr})"
                )
            raise
        try:
            conn.commit()
        except Exception:
            _log("CRITICAL: conn.commit() failed after promote — restoring JSON snapshots")
            try:
                conn.rollback()
            except Exception as rerr:
                _log(
                    f"CRITICAL: rollback after commit failure also raised "
                    f"({type(rerr).__name__}: {rerr})"
                )
            _restore_snapshots(
                snapshot_state["routes_final"],
                snapshot_state["routes_bak"],
                snapshot_state["routes_had_snapshot"],
                snapshot_state["routes_promoted"],
                snapshot_state["traycer_final"],
                snapshot_state["traycer_bak"],
                snapshot_state["traycer_had_snapshot"],
                snapshot_state["traycer_promoted"],
            )
            raise
        # Both stores committed → safe to drop snapshots.
        _cleanup_snapshots(snapshot_state)
    finally:
        conn.close()

    total_routes = sum(len(v) for v in routes.values())
    _log(f"wrote {total_routes} pins across {len(routes)} categories ({len(skipped)} skipped)")
    return routes, skipped


if __name__ == "__main__":
    if not DB_PATH.exists():
        _log(f"ERROR: {DB_PATH} does not exist. Run kilo_agents_db.py init first.")
        sys.exit(1)
    run()
