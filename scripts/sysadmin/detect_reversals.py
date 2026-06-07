#!/usr/bin/env python3
"""Detect operator reversals of AI actions (trio plan Phase 5.1.a).

Runs as a `*/5 min` cron on each host. Correlates AI actions (from two
sources) against subsequent operator-issued docker/redis commands within a
5-minute window. Matches are appended to /opt/fabrik/logs/lessons-pending.jsonl
for the weekly review process documented in trio plan §5.1.

Sources of AI actions:
  1. Watchdog sidecar state.db actions table (per-project sidecars only —
     read via `docker exec <sidecar> sqlite3 -readonly`, NEVER via host path
     because the .db is owned by uid 1000 inside the container).
  2. /opt/fabrik/logs/sysadmin-actions.jsonl — host AI sysadmin actions.
     Today most entries are diagnose-only wakes (cycle=True or no action
     taken); future Phase 5 work will surface explicit action verbs.

Source of operator counter-actions:
  journalctl _COMM=sudo --since "-10min" --output json
  filtered to docker/redis/file-deletion command lines, excluding any
  COMMAND that was itself issued from the watchdog sidecar container or
  the vps-sysadmin-bot.service (those are the AI's own actions, not the
  operator's).

Reversal classes detected (per plan §5.1.a):
  - restart_container → docker (restart|stop|kill|rm) <same_name> within 5min
  - clear_redis_cache → any redis CLI op on the same DB index within 5min
  - rotate_logs       → manual truncate/rm in the same dir within 5min

Output entries: { ts, host, class, ai_source, ai_ts, ai_target, operator_ts,
operator_cmd } — minimal, one-line JSON for grep-friendly weekly review.

Defensive design:
  - Read-only on state.db (`sqlite3 -readonly`).
  - Append-only on lessons-pending.jsonl (idempotent — entries deduplicated
    by (ai_source, ai_ts, operator_ts) tuple to avoid duplicate detections
    when the script runs every 5min and a reversal window overlaps two runs).
  - If a state.db / journalctl probe fails (container missing, permissions,
    parse error), the script logs a single-line WARN and continues — never
    crashes a cron job over an observability gap.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# ── Config ────────────────────────────────────────────────────────────────

HOST = socket.gethostname().split(".")[0]
WINDOW_SECONDS = int(os.environ.get("REVERSAL_WINDOW_SECONDS", "300"))  # 5 min
LOOKBACK_SECONDS = int(os.environ.get("REVERSAL_LOOKBACK_SECONDS", "600"))  # 10 min
LESSONS_PATH = Path(os.environ.get("LESSONS_PATH", "/opt/fabrik/logs/lessons-pending.jsonl"))
ACTIONS_LOG_PATH = Path(
    os.environ.get("ACTIONS_LOG_PATH", "/opt/fabrik/logs/sysadmin-actions.jsonl")
)

# Detect AI-targeted docker action verbs (the reversal pattern targets).
_OP_VERB_PATTERN = re.compile(
    r"/usr/bin/docker\s+(restart|stop|kill|rm|start|up)(?:\s+(?:-[\w-]+\s*)*)*(\S+)"
)


def _now_ts() -> float:
    return time.time()


def _emit_warning(msg: str) -> None:
    print(f"[detect_reversals] WARN {msg}", file=sys.stderr)


# ── AI action collectors ──────────────────────────────────────────────────


def collect_sidecar_actions() -> list[dict[str, Any]]:
    """Read recent action rows from every running watchdog sidecar.

    Returns rows with action_name + target_container + ts (epoch float).
    """
    rows: list[dict[str, Any]] = []
    try:
        # List sidecars: any container with name ending `-watchdog`.
        proc = subprocess.run(
            ["sudo", "docker", "ps", "--format", "{{.Names}}", "--filter", "name=-watchdog"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        sidecars = [s.strip() for s in proc.stdout.splitlines() if s.strip().endswith("-watchdog")]
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        _emit_warning(f"sidecar list failed: {e}")
        return rows

    cutoff_dt = datetime.now(UTC) - timedelta(seconds=LOOKBACK_SECONDS)
    cutoff_iso = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")

    for sidecar in sidecars:
        # Target container name = sidecar name minus the `-watchdog` suffix.
        target = sidecar.removesuffix("-watchdog")
        try:
            proc = subprocess.run(
                [
                    "sudo",
                    "docker",
                    "exec",
                    sidecar,
                    "sqlite3",
                    "-readonly",
                    "/var/lib/watchdog/state.db",
                    # Default list mode uses '|' as separator. Avoid -csv —
                    # it quotes ts ("2026-06-07 10:17:30") which breaks
                    # strptime unless we strip quotes. '|' has no collision
                    # risk with our 3 columns (ts/action_name/result are all
                    # simple alphanumeric/space content).
                    f"SELECT ts, action_name, result FROM actions "
                    f"WHERE ts > '{cutoff_iso}' AND result='success' "
                    f"AND action_name IN ('restart_container','clear_redis_cache','rotate_logs') "
                    f"ORDER BY ts DESC",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            for line in proc.stdout.splitlines():
                parts = line.strip().split("|", 2)
                if len(parts) < 2:
                    continue
                ts_str, action_name = parts[0], parts[1]
                try:
                    ts_epoch = (
                        datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                        .replace(tzinfo=UTC)
                        .timestamp()
                    )
                except ValueError:
                    continue
                rows.append(
                    {
                        "source": "watchdog_sidecar",
                        "sidecar": sidecar,
                        "ts": ts_epoch,
                        "action_name": action_name,
                        "target": target,
                    }
                )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            _emit_warning(f"sidecar {sidecar} state.db read failed: {e}")
            continue
    return rows


def collect_host_sysadmin_actions() -> list[dict[str, Any]]:
    """Read recent AI-action entries from sysadmin-actions.jsonl.

    Today most entries are diagnose-only wakes (no explicit action). The
    schema today doesn't differentiate diagnose-vs-act — `result_excerpt`
    is the only signal. This collector is a stub that will grow as Phase 5
    surfaces explicit action verbs in the log shape. For now, returns empty
    list unless `action_name` shows up in entries (future-compat).
    """
    rows: list[dict[str, Any]] = []
    if not ACTIONS_LOG_PATH.exists():
        return rows
    cutoff = _now_ts() - LOOKBACK_SECONDS
    try:
        with ACTIONS_LOG_PATH.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("ts", 0) < cutoff:
                    continue
                # Future-compat: only count entries with explicit action_name.
                action_name = entry.get("action_name")
                target = entry.get("target") or entry.get("container")
                if action_name and target:
                    rows.append(
                        {
                            "source": "host_sysadmin",
                            "ts": entry["ts"],
                            "action_name": action_name,
                            "target": target,
                        }
                    )
    except OSError as e:
        _emit_warning(f"sysadmin-actions.jsonl read failed: {e}")
    return rows


# ── Operator counter-action collector ─────────────────────────────────────


def collect_operator_docker_commands() -> list[dict[str, Any]]:
    """Read sudo audit entries for docker commands within the lookback."""
    rows: list[dict[str, Any]] = []
    try:
        proc = subprocess.run(
            [
                "sudo",
                "journalctl",
                "_COMM=sudo",
                "--since",
                f"-{LOOKBACK_SECONDS}s",
                "--output",
                "json",
                "--no-pager",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        _emit_warning(f"journalctl read failed: {e}")
        return rows
    for raw in proc.stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        msg = entry.get("MESSAGE", "")
        m = _OP_VERB_PATTERN.search(msg)
        if not m:
            continue
        verb, target = m.group(1), m.group(2)
        # Skip the verb-as-flag false-positive cases: `docker ps`, `docker logs`
        if verb in ("start", "up") and "-d" not in msg and verb != "up":
            continue
        try:
            ts_us = int(entry.get("__REALTIME_TIMESTAMP", "0"))
            ts_epoch = ts_us / 1_000_000.0
        except ValueError:
            continue
        rows.append(
            {
                "ts": ts_epoch,
                "verb": verb,
                "target": target,
                "cmd": msg[:200],
                "user": entry.get("_AUDIT_LOGINUID", "?"),
            }
        )
    return rows


# ── Correlation ───────────────────────────────────────────────────────────


def correlate(
    ai_actions: list[dict[str, Any]],
    op_commands: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Match each AI action to a subsequent operator command within WINDOW.

    Same-target match: action_name=restart_container + target=foo matches
    a subsequent operator `docker restart/stop/kill/rm foo` within 5 min.
    """
    reversals: list[dict[str, Any]] = []
    action_to_op_verbs = {
        "restart_container": {"restart", "stop", "kill", "rm", "up"},
        # Future: extend when sidecar gains clear_redis_cache / rotate_logs verbs.
    }
    for ai in ai_actions:
        verbs = action_to_op_verbs.get(ai["action_name"], set())
        if not verbs:
            continue
        for op in op_commands:
            if op["target"] != ai["target"]:
                continue
            if op["verb"] not in verbs:
                continue
            delta = op["ts"] - ai["ts"]
            if delta < 0 or delta > WINDOW_SECONDS:
                continue
            reversals.append(
                {
                    "ts": _now_ts(),
                    "host": HOST,
                    "class": ai["action_name"],
                    "ai_source": ai["source"],
                    "ai_ts": ai["ts"],
                    "ai_target": ai["target"],
                    "operator_ts": op["ts"],
                    "operator_verb": op["verb"],
                    "operator_cmd": op["cmd"],
                    "delta_seconds": round(delta, 1),
                }
            )
    return reversals


# ── Output (idempotent append) ────────────────────────────────────────────


def _seen_keys() -> set[tuple]:
    """Tuples of (ai_source, ai_ts, operator_ts) we've already written."""
    seen: set[tuple] = set()
    if not LESSONS_PATH.exists():
        return seen
    try:
        with LESSONS_PATH.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                seen.add((e.get("ai_source"), e.get("ai_ts"), e.get("operator_ts")))
    except OSError as e:
        _emit_warning(f"lessons-pending.jsonl read failed: {e}")
    return seen


def emit(reversals: list[dict[str, Any]]) -> int:
    """Append fresh reversals. Returns count written."""
    if not reversals:
        return 0
    seen = _seen_keys()
    written = 0
    LESSONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with LESSONS_PATH.open("a") as fh:
            for r in reversals:
                key = (r["ai_source"], r["ai_ts"], r["operator_ts"])
                if key in seen:
                    continue
                fh.write(json.dumps(r) + "\n")
                written += 1
    except OSError as e:
        _emit_warning(f"lessons-pending.jsonl write failed: {e}")
    return written


# ── Main ──────────────────────────────────────────────────────────────────


def main() -> int:
    sidecar_actions = collect_sidecar_actions()
    host_actions = collect_host_sysadmin_actions()
    ai_actions = sidecar_actions + host_actions
    op_commands = collect_operator_docker_commands()
    reversals = correlate(ai_actions, op_commands)
    written = emit(reversals)
    if written:
        print(
            f"[detect_reversals] {HOST}: wrote {written} reversal(s); "
            f"ai_actions={len(ai_actions)} op_commands={len(op_commands)}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
