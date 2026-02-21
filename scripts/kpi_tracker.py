#!/usr/bin/env python3
"""KPI Tracker CLI for managing droid execution metrics.

Usage:
    python scripts/kpi_tracker.py summary [--since DATE] [--until DATE] [--model MODEL] [--format table|json|csv]
    python scripts/kpi_tracker.py export [--format json|csv] [--since DATE] [--until DATE]
    python scripts/kpi_tracker.py ingest [--source PATH]
    python scripts/kpi_tracker.py prune [--older-than DURATION]
    python scripts/kpi_tracker.py sanitize [--field FIELD]

Exit codes:
    0 - Success
    1 - No data for period
    2 - Parse error
    3 - File not found / permission error
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

VALID_EVENT_TYPES = {"task_start", "task_end", "review_start", "review_end", "error"}

KPI_DIR = Path(".droid")
KPI_FILE = KPI_DIR / "kpis.jsonl"
DEFAULT_TOKEN_LOG = Path("scripts/.droid_token_usage.jsonl")


@dataclass
class KPIEvent:
    """Represents a single KPI event."""

    event_id: str
    event_type: str
    timestamp: str
    task_id: str
    session_id: str | None = None
    model: str | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    duration_seconds: float | None = None
    status: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KPIEvent:
        """Create from dict, ignoring unknown fields."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


def _ensure_kpi_dir() -> Path:
    """Ensure .droid/ directory exists and return path to kpis.jsonl."""
    KPI_DIR.mkdir(parents=True, exist_ok=True)
    return KPI_FILE


def load_events(path: Path) -> list[KPIEvent]:
    """Load KPI events from JSONL file, deduplicating by event_id."""
    if not path.exists():
        return []

    events: list[KPIEvent] = []
    seen_ids: set[str] = set()

    try:
        with path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    event_id = data.get("event_id")
                    if event_id and event_id in seen_ids:
                        continue
                    event = KPIEvent.from_dict(data)
                    if event_id:
                        seen_ids.add(event_id)
                    events.append(event)
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"Warning: Skipping malformed line {line_num}: {e}", file=sys.stderr)
    except PermissionError as e:
        print(f"Error: Permission denied reading {path}: {e}", file=sys.stderr)
        sys.exit(3)

    return events


def save_events(path: Path, events: list[KPIEvent]) -> None:
    """Save KPI events to JSONL file atomically."""
    tmp_path = path.with_suffix(".jsonl.tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event.to_dict()) + "\n")
        os.replace(tmp_path, path)
    except PermissionError as e:
        print(f"Error: Permission denied writing {path}: {e}", file=sys.stderr)
        sys.exit(3)


def append_event(path: Path, event: KPIEvent) -> None:
    """Append a single event to JSONL file."""
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict()) + "\n")
    except PermissionError as e:
        print(f"Error: Permission denied writing {path}: {e}", file=sys.stderr)
        sys.exit(3)


def parse_duration(duration_str: str) -> timedelta:
    """Parse duration string like '90d', '30d', '7d'."""
    match = re.match(r"^(\d+)([dhms])$", duration_str.lower())
    if not match:
        raise ValueError(f"Invalid duration format: {duration_str}. Use format like '90d', '30d'.")

    value, unit = int(match.group(1)), match.group(2)
    if unit == "d":
        return timedelta(days=value)
    elif unit == "h":
        return timedelta(hours=value)
    elif unit == "m":
        return timedelta(minutes=value)
    elif unit == "s":
        return timedelta(seconds=value)
    raise ValueError(f"Unknown duration unit: {unit}")


def parse_timestamp(ts: str) -> datetime:
    """Parse ISO 8601 timestamp string."""
    ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)


def _safe_parse_timestamp(ts: str, event_id: str | None = None) -> datetime | None:
    """Parse timestamp, returning None on error instead of raising."""
    try:
        return parse_timestamp(ts)
    except (ValueError, TypeError) as e:
        event_ref = f" (event_id: {event_id})" if event_id else ""
        print(f"Warning: Skipping event with invalid timestamp{event_ref}: {e}", file=sys.stderr)
        return None


def filter_events(
    events: list[KPIEvent],
    since: str | None = None,
    until: str | None = None,
    model: str | None = None,
) -> list[KPIEvent]:
    """Filter events by time range and model."""
    filtered = events

    if since:
        since_dt = parse_timestamp(since)
        result = []
        for e in filtered:
            event_ts = _safe_parse_timestamp(e.timestamp, e.event_id)
            if event_ts is not None and event_ts >= since_dt:
                result.append(e)
        filtered = result

    if until:
        until_dt = parse_timestamp(until)
        result = []
        for e in filtered:
            event_ts = _safe_parse_timestamp(e.timestamp, e.event_id)
            if event_ts is not None and event_ts <= until_dt:
                result.append(e)
        filtered = result

    if model:
        filtered = [e for e in filtered if e.model == model]

    return filtered


def cmd_summary(args: argparse.Namespace) -> int:
    """Execute summary subcommand."""
    kpi_path = _ensure_kpi_dir()
    events = load_events(kpi_path)
    events = filter_events(events, args.since, args.until, args.model)

    task_end_events = [e for e in events if e.event_type == "task_end"]

    if not task_end_events:
        print("No data for period", file=sys.stderr)
        return 1

    total_tasks = len(task_end_events)
    success_count = sum(1 for e in task_end_events if e.status == "success")
    success_rate = success_count / total_tasks if total_tasks > 0 else 0.0

    durations = [e.duration_seconds for e in task_end_events if e.duration_seconds is not None]
    avg_duration = sum(durations) / len(durations) if durations else 0.0

    total_tokens_input = sum(e.tokens_input or 0 for e in task_end_events)
    total_tokens_output = sum(e.tokens_output or 0 for e in task_end_events)
    total_tokens = total_tokens_input + total_tokens_output

    by_model: dict[str, dict[str, Any]] = {}
    for e in task_end_events:
        model_name = e.model or "unknown"
        if model_name not in by_model:
            by_model[model_name] = {"tasks": 0, "tokens": 0, "success": 0}
        by_model[model_name]["tasks"] += 1
        by_model[model_name]["tokens"] += (e.tokens_input or 0) + (e.tokens_output or 0)
        if e.status == "success":
            by_model[model_name]["success"] += 1

    summary = {
        "total_tasks": total_tasks,
        "success_rate": round(success_rate, 4),
        "avg_duration_seconds": round(avg_duration, 2),
        "total_tokens_input": total_tokens_input,
        "total_tokens_output": total_tokens_output,
        "total_tokens": total_tokens,
    }

    if args.format == "json":
        output = {"summary": summary, "by_model": by_model}
        print(json.dumps(output, indent=2))
    elif args.format == "csv":
        writer = csv.writer(sys.stdout)
        writer.writerow(["metric", "value"])
        for k, v in summary.items():
            writer.writerow([k, v])
    else:  # table
        print("=== KPI Summary ===")
        for k, v in summary.items():
            print(f"  {k}: {v}")
        print("\n=== By Model ===")
        for model_name, stats in by_model.items():
            print(
                f"  {model_name}: {stats['tasks']} tasks, {stats['tokens']} tokens, {stats['success']} success"
            )

    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Execute export subcommand."""
    kpi_path = _ensure_kpi_dir()
    events = load_events(kpi_path)
    events = filter_events(events, args.since, args.until, None)

    if not events:
        print("No data for period", file=sys.stderr)
        return 1

    period = {
        "since": args.since or "all",
        "until": args.until or "now",
        "count": len(events),
    }

    task_end_events = [e for e in events if e.event_type == "task_end"]
    summary = {
        "total_tasks": len(task_end_events),
        "total_tokens": sum(
            (e.tokens_input or 0) + (e.tokens_output or 0) for e in task_end_events
        ),
    }

    if args.format == "json":
        output = {
            "period": period,
            "summary": summary,
            "events": [e.to_dict() for e in events],
        }
        print(json.dumps(output, indent=2))
    else:  # csv
        if not events:
            return 0
        fieldnames = list(KPIEvent.__dataclass_fields__.keys())
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for event in events:
            writer.writerow(event.to_dict())

    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    """Execute ingest subcommand - import from token usage log."""
    source_path = Path(args.source)

    if not source_path.exists():
        print(f"No token log at {source_path}, nothing to ingest")
        return 0

    kpi_path = _ensure_kpi_dir()
    existing_events = load_events(kpi_path)
    existing_ids = {e.event_id for e in existing_events}

    new_events: list[KPIEvent] = []
    ingested_count = 0
    skipped_count = 0

    try:
        with source_path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)

                    session_id = data.get("session_id", "")
                    timestamp = data.get("timestamp", "")

                    # Validate required fields per spec
                    if not session_id or not timestamp:
                        print(
                            f"Warning: Line {line_num} missing required session_id or timestamp",
                            file=sys.stderr,
                        )
                        return 2

                    event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, session_id + timestamp))

                    if event_id in existing_ids:
                        skipped_count += 1
                        continue

                    event = KPIEvent(
                        event_id=event_id,
                        event_type="task_end",
                        timestamp=timestamp,
                        task_id=session_id,
                        session_id=session_id,
                        model=data.get("model"),
                        tokens_input=data.get("input_tokens"),
                        tokens_output=data.get("output_tokens"),
                        status="success",
                    )
                    new_events.append(event)
                    existing_ids.add(event_id)
                    ingested_count += 1

                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    print(f"Warning: Skipping malformed line {line_num}: {e}", file=sys.stderr)
                    return 2

    except PermissionError as e:
        print(f"Error: Permission denied reading {source_path}: {e}", file=sys.stderr)
        return 3

    for event in new_events:
        append_event(kpi_path, event)

    print(f"Ingested {ingested_count} events, skipped {skipped_count} duplicates")
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    """Execute prune subcommand - remove old events."""
    try:
        retention = parse_duration(args.older_than)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    kpi_path = _ensure_kpi_dir()
    events = load_events(kpi_path)

    if not events:
        print("No events to prune")
        return 0

    cutoff = datetime.now(tz=UTC) - retention
    kept_events = []
    pruned_count = 0

    for event in events:
        try:
            event_time = parse_timestamp(event.timestamp)
            if event_time >= cutoff:
                kept_events.append(event)
            else:
                pruned_count += 1
        except (ValueError, TypeError):
            kept_events.append(event)

    save_events(kpi_path, kept_events)
    print(f"Pruned {pruned_count} events older than {args.older_than}")
    return 0


def cmd_sanitize(args: argparse.Namespace) -> int:
    """Execute sanitize subcommand - strip PII from specified field."""
    kpi_path = _ensure_kpi_dir()
    events = load_events(kpi_path)

    if not events:
        print("No events to sanitize")
        return 0

    path_pattern = re.compile(r"/[^\s]+")
    trace_pattern = re.compile(r'File "[^"]*"')

    try:
        from scripts.enforcement.check_secrets import SECRET_PATTERNS
    except ImportError:
        secret_patterns = []
    else:
        secret_patterns = SECRET_PATTERNS

    sanitized_count = 0

    for event in events:
        field_value = getattr(event, args.field, None)
        if field_value and isinstance(field_value, str):
            original = field_value

            field_value = path_pattern.sub("[PATH]", field_value)
            field_value = trace_pattern.sub('File "[REDACTED]"', field_value)

            for pattern in secret_patterns:
                if isinstance(pattern, re.Pattern):
                    field_value = pattern.sub("[REDACTED]", field_value)
                elif isinstance(pattern, str):
                    field_value = re.sub(pattern, "[REDACTED]", field_value)

            if field_value != original:
                setattr(event, args.field, field_value)
                sanitized_count += 1

    save_events(kpi_path, events)
    print(f"Sanitized {sanitized_count} events")
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="KPI Tracker CLI for managing droid execution metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    summary_parser = subparsers.add_parser("summary", help="Show KPI summary")
    summary_parser.add_argument("--since", help="Start date (ISO 8601)")
    summary_parser.add_argument("--until", help="End date (ISO 8601)")
    summary_parser.add_argument("--model", help="Filter by model name")
    summary_parser.add_argument("--format", choices=["table", "json", "csv"], default="table")

    export_parser = subparsers.add_parser("export", help="Export KPI events")
    export_parser.add_argument("--format", choices=["json", "csv"], default="json")
    export_parser.add_argument("--since", help="Start date (ISO 8601)")
    export_parser.add_argument("--until", help="End date (ISO 8601)")

    ingest_parser = subparsers.add_parser("ingest", help="Ingest from token usage log")
    ingest_parser.add_argument(
        "--source",
        default=str(DEFAULT_TOKEN_LOG),
        help=f"Source token log file (default: {DEFAULT_TOKEN_LOG})",
    )

    prune_parser = subparsers.add_parser("prune", help="Remove old events")
    prune_parser.add_argument(
        "--older-than",
        default="90d",
        help="Remove events older than duration (default: 90d)",
    )

    sanitize_parser = subparsers.add_parser("sanitize", help="Sanitize PII from events")
    sanitize_parser.add_argument(
        "--field",
        default="error_message",
        help="Field to sanitize (default: error_message)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "summary": cmd_summary,
        "export": cmd_export,
        "ingest": cmd_ingest,
        "prune": cmd_prune,
        "sanitize": cmd_sanitize,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
