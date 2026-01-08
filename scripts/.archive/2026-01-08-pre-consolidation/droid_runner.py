#!/usr/bin/env python3
"""
Droid Runner - Robust droid exec wrapper with monitoring and data exchange.

Features:
- Accepts .md files for task input
- Monitors droid exec progress (not stuck detection)
- Proper completion handling without premature termination
- Data exchange via /opt/fabrik/.droid/ folder
- All output formats supported

Usage:
    # From file
    python scripts/droid_runner.py run --task tasks/my_task.md

    # Direct prompt
    python scripts/droid_runner.py run --prompt "Analyze the codebase"

    # With session continuation
    python scripts/droid_runner.py run --task tasks/followup.md --session-id abc123

    # Monitor a running task
    python scripts/droid_runner.py status --task-id xyz789
"""

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

# Import ProcessMonitor if available
try:
    from process_monitor import ProcessMonitor

    PROCESS_MONITOR_AVAILABLE = True
except ImportError:
    PROCESS_MONITOR_AVAILABLE = False

# Import model updater
try:
    from droid_model_updater import update_if_stale

    MODEL_UPDATER_AVAILABLE = True
except ImportError:
    MODEL_UPDATER_AVAILABLE = False

# Data exchange folder - configurable via env var (Fabrik convention)
DROID_DATA_DIR = Path(os.getenv("DROID_DATA_DIR", "/opt/fabrik/.droid"))
TASKS_DIR = DROID_DATA_DIR / "tasks"
RESPONSES_DIR = DROID_DATA_DIR / "responses"
SESSIONS_DIR = DROID_DATA_DIR / "sessions"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    STUCK = "stuck"


@dataclass
class TaskRecord:
    """Record of a droid task for tracking."""

    task_id: str
    prompt: str
    status: TaskStatus
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    session_id: str | None = None
    model: str | None = None
    autonomy: str = "low"
    output_format: str = "json"
    result: str | None = None
    error: str | None = None
    duration_ms: int | None = None
    last_activity_at: str | None = None
    num_events: int = 0


def ensure_dirs():
    """Ensure data exchange directories exist."""
    for d in [TASKS_DIR, RESPONSES_DIR, SESSIONS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def load_task_from_file(file_path: Path) -> str:
    """Load task prompt from .md or .txt file."""
    if not file_path.exists():
        raise FileNotFoundError(f"Task file not found: {file_path}")
    return file_path.read_text().strip()


def _sanitize_task_id(task_id: str) -> str:
    """Sanitize task ID to prevent path traversal attacks."""
    # Remove path separators and parent directory references
    sanitized = task_id.replace("/", "_").replace("\\", "_").replace("..", "__")
    # Only allow alphanumeric, underscore, dash
    return "".join(c for c in sanitized if c.isalnum() or c in "_-")


def save_task_record(record: TaskRecord):
    """Save task record to disk."""
    safe_id = _sanitize_task_id(record.task_id)
    path = TASKS_DIR / f"{safe_id}.json"
    with open(path, "w") as f:
        json.dump(asdict(record), f, indent=2)


def load_task_record(task_id: str) -> TaskRecord | None:
    """Load task record from disk."""
    safe_id = _sanitize_task_id(task_id)
    path = TASKS_DIR / f"{safe_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
        data["status"] = TaskStatus(data["status"])
        return TaskRecord(**data)


def save_response(task_id: str, response: dict):
    """Save response to disk."""
    safe_id = _sanitize_task_id(task_id)
    path = RESPONSES_DIR / f"{safe_id}.json"
    with open(path, "w") as f:
        json.dump(response, f, indent=2)


def run_droid_exec_monitored(
    prompt: str,
    task_id: str,
    model: str = "claude-opus-4-5-20251101",
    autonomy: str = "low",
    output_format: str = "stream-json",
    session_id: str | None = None,
    cwd: str | None = None,
    on_event: Callable[[dict], None] | None = None,
    warn_after_seconds: int = 300,  # Warn after 5 minutes of no activity (never kills)
) -> TaskRecord:
    """
    Run droid exec with proper monitoring.

    Uses stream-json format to monitor progress and detect if stuck.
    Does NOT prematurely terminate - waits for completion event.

    Args:
        prompt: Task prompt
        task_id: Unique task identifier
        model: Model to use
        autonomy: Autonomy level (low/medium/high)
        output_format: Output format (stream-json recommended for monitoring)
        session_id: Optional session ID to continue
        cwd: Working directory
        on_event: Callback for each streaming event
        warn_after_seconds: Seconds without activity before logging a warning (never auto-kills)

    Returns:
        TaskRecord with final status
    """
    # Refresh model names if stale
    if MODEL_UPDATER_AVAILABLE:
        try:
            update_if_stale()
        except Exception:
            pass  # Non-fatal

    ensure_dirs()

    # Create task record
    record = TaskRecord(
        task_id=task_id,
        prompt=prompt[:500],  # Truncate for storage
        status=TaskStatus.PENDING,
        created_at=datetime.now(UTC).isoformat(),
        model=model,
        autonomy=autonomy,
        output_format=output_format,
    )
    save_task_record(record)

    # Build command
    args = ["droid", "exec", "--output-format", output_format, "--model", model, "--auto", autonomy]

    if session_id:
        args.extend(["--session-id", session_id])

    if cwd:
        args.extend(["--cwd", cwd])

    args.append(prompt)

    # Start process
    record.status = TaskStatus.RUNNING
    record.started_at = datetime.now(UTC).isoformat()
    record.last_activity_at = record.started_at
    save_task_record(record)

    print(f"[{task_id}] Starting droid exec...", file=sys.stderr)

    # Build environment to prevent interactive prompts
    env = os.environ.copy()
    env.update(
        {
            "CI": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "PIP_NO_INPUT": "1",
            "TERM": "dumb",
            "NO_COLOR": "1",
        }
    )

    process = subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,  # Critical: prevents stdin-blocking
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,  # Prevent deadlock: don't pipe stderr if not reading it
        text=True,
        cwd=cwd,
        env=env,
        start_new_session=True,  # Detach from controlling TTY
    )

    start_time = time.time()
    last_activity_time = start_time
    final_text = ""
    captured_session_id = None
    events = []
    current_tool = None  # Track current tool
    last_warning_time = 0  # Track when we last warned about inactivity

    # Initialize ProcessMonitor if available
    monitor = None
    if PROCESS_MONITOR_AVAILABLE:
        try:
            monitor = ProcessMonitor(process, warn_threshold=warn_after_seconds)
            print(f"[{task_id}] ProcessMonitor active (CPU/IO/Network monitoring)", file=sys.stderr)
        except Exception as e:
            print(f"[{task_id}] ProcessMonitor init failed: {e}", file=sys.stderr)

    try:
        # Read streaming events
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue

            # Activity detected
            last_activity_time = time.time()
            record.last_activity_at = datetime.now(UTC).isoformat()
            record.num_events += 1

            # Record activity in ProcessMonitor
            if monitor:
                monitor.record_activity()

            try:
                event = json.loads(line)
                events.append(event)

                # Call event callback
                if on_event:
                    on_event(event)

                # Check for system init (get session ID early)
                if event.get("type") == "system" and event.get("subtype") == "init":
                    captured_session_id = event.get("session_id")
                    record.session_id = captured_session_id
                    print(f"[{task_id}] Session: {captured_session_id}", file=sys.stderr)

                # Check for assistant messages (progress indicator)
                if event.get("type") == "message" and event.get("role") == "assistant":
                    text = event.get("text", "")[:100]
                    print(f"[{task_id}] Progress: {text}...", file=sys.stderr)

                # Check for tool calls (activity indicator)
                if event.get("type") == "tool_call":
                    tool_name = event.get("toolName", "unknown")
                    current_tool = tool_name  # Track for timeout adjustment
                    print(f"[{task_id}] Tool: {tool_name}", file=sys.stderr)

                # Check for tool results (reset current tool)
                if event.get("type") == "tool_result":
                    current_tool = None  # Tool completed

                # Check for completion event (THE END)
                if event.get("type") == "completion":
                    final_text = event.get("finalText", "")
                    captured_session_id = event.get("session_id", captured_session_id)
                    duration_ms = event.get("durationMs")

                    record.status = TaskStatus.COMPLETED
                    record.completed_at = datetime.now(UTC).isoformat()
                    record.result = final_text
                    record.session_id = captured_session_id
                    record.duration_ms = duration_ms

                    print(f"[{task_id}] Completed in {duration_ms}ms", file=sys.stderr)
                    break

                # Check for error
                if event.get("type") == "result" and event.get("is_error"):
                    record.status = TaskStatus.FAILED
                    record.error = event.get("result", "Unknown error")
                    break

            except json.JSONDecodeError:
                continue

            # Warn about long inactivity but NEVER auto-kill
            # Use ProcessMonitor for rich diagnostics if available
            elapsed_since_activity = time.time() - last_activity_time
            if (
                elapsed_since_activity > warn_after_seconds
                and (time.time() - last_warning_time) > 60
            ):
                tool_info = f" (waiting for {current_tool})" if current_tool else ""

                if monitor:
                    # Use ProcessMonitor for detailed diagnostics
                    diagnosis = monitor.analyze()
                    state = diagnosis.get("state", "UNKNOWN")
                    reason = diagnosis.get("reason", "")
                    metrics = diagnosis.get("metrics", {})

                    if state in ("LIKELY_STUCK", "CONFIRMED_STUCK"):
                        print(f"[{task_id}] 🔴 {state}: {reason}", file=sys.stderr)
                        if metrics:
                            print(
                                f"[{task_id}]    CPU={metrics.get('avg_cpu', 0):.1f}% IO={metrics.get('total_io_bytes', 0)}B Net={metrics.get('any_network', False)}",
                                file=sys.stderr,
                            )
                    elif state == "SUSPICIOUS":
                        print(f"[{task_id}] 🟡 {state}: {reason}", file=sys.stderr)
                    else:
                        print(
                            f"[{task_id}] ⚠️  No stdout for {int(elapsed_since_activity)}s{tool_info} - process appears active",
                            file=sys.stderr,
                        )
                else:
                    print(
                        f"[{task_id}] ⚠️  No activity for {int(elapsed_since_activity)}s{tool_info} - still running...",
                        file=sys.stderr,
                    )

                last_warning_time = time.time()

        # Wait for process to finish
        process.wait(timeout=30)

        # Check returncode - detect failed runs that didn't emit completion event
        if process.returncode != 0 and record.status == TaskStatus.RUNNING:
            record.status = TaskStatus.FAILED
            record.error = f"Process exited with code {process.returncode}"
            print(
                f"[{task_id}] Process failed with exit code {process.returncode}", file=sys.stderr
            )

    except Exception as e:
        record.status = TaskStatus.FAILED
        record.error = str(e)
        print(f"[{task_id}] Error: {e}", file=sys.stderr)

    finally:
        # Ensure process is terminated
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

        # Calculate duration if not set
        if record.duration_ms is None:
            record.duration_ms = int((time.time() - start_time) * 1000)

        # Save final state
        save_task_record(record)

        # Save response
        save_response(
            task_id,
            {
                "task_id": task_id,
                "session_id": captured_session_id,
                "status": record.status.value,
                "result": final_text,
                "error": record.error,
                "duration_ms": record.duration_ms,
                "num_events": len(events),
                "events": events[-10:],  # Last 10 events for debugging
            },
        )

    return record


def print_event(event: dict):
    """Default event printer for monitoring."""
    event_type = event.get("type", "unknown")

    if event_type == "system":
        pass  # Quiet
    elif event_type == "message":
        role = event.get("role", "?")
        text = event.get("text", "")[:80]
        if role == "assistant":
            print(f"  💬 {text}...")
    elif event_type == "tool_call":
        tool = event.get("toolName", "?")
        print(f"  🔧 {tool}")
    elif event_type == "tool_result":
        is_error = event.get("isError", False)
        if is_error:
            print("  ❌ Tool error")
    elif event_type == "completion":
        print("  ✅ Complete")


def cmd_run(args):
    """Run a droid task."""
    # Get prompt from file or argument
    if args.task:
        task_path = Path(args.task)
        if not task_path.is_absolute():
            task_path = Path.cwd() / task_path
        prompt = load_task_from_file(task_path)
    elif args.prompt:
        prompt = args.prompt
    else:
        print("Error: Either --task or --prompt required", file=sys.stderr)
        sys.exit(1)

    # Generate task ID
    task_id = args.task_id or f"task-{uuid.uuid4().hex[:8]}"

    # Run with monitoring
    record = run_droid_exec_monitored(
        prompt=prompt,
        task_id=task_id,
        model=args.model,
        autonomy=args.auto,
        output_format="stream-json",  # Always use stream-json for monitoring
        session_id=args.session_id,
        cwd=args.cwd,
        on_event=print_event if args.verbose else None,
        warn_after_seconds=args.warn_after,
    )

    # Output result
    if args.output == "json":
        print(json.dumps(asdict(record), indent=2, default=str))
    else:
        print(f"\n{'='*60}")
        print(f"Task ID: {record.task_id}")
        print(f"Status: {record.status.value}")
        print(f"Duration: {record.duration_ms}ms")
        print(f"Session: {record.session_id}")
        if record.error:
            print(f"Error: {record.error}")
        print(f"{'='*60}")
        if record.result:
            print(f"\nResult:\n{record.result}")

    # Exit code based on status
    sys.exit(0 if record.status == TaskStatus.COMPLETED else 1)


def cmd_status(args):
    """Check status of a task."""
    record = load_task_record(args.task_id)
    if not record:
        print(f"Task not found: {args.task_id}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(asdict(record), indent=2, default=str))


def cmd_list(args):
    """List recent tasks."""
    ensure_dirs()
    tasks = sorted(TASKS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    for task_path in tasks[: args.limit]:
        with open(task_path) as f:
            data = json.load(f)
        print(
            f"{data['task_id']}: {data['status']} ({data.get('duration_ms', '?')}ms) - {data['prompt'][:50]}..."
        )


def main():
    parser = argparse.ArgumentParser(description="Robust droid exec runner with monitoring")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a droid task")
    run_parser.add_argument("--task", "-t", help="Path to task file (.md or .txt)")
    run_parser.add_argument("--prompt", "-p", help="Direct prompt string")
    run_parser.add_argument("--task-id", help="Custom task ID")
    run_parser.add_argument("--session-id", "-s", help="Continue existing session")
    run_parser.add_argument(
        "--model", "-m", default="claude-opus-4-5-20251101", help="Model to use"
    )
    run_parser.add_argument("--auto", "-a", default="low", choices=["low", "medium", "high"])
    run_parser.add_argument("--cwd", help="Working directory")
    run_parser.add_argument("--output", "-o", default="text", choices=["text", "json"])
    run_parser.add_argument("--verbose", "-v", action="store_true", help="Show progress events")
    run_parser.add_argument(
        "--warn-after",
        type=int,
        default=300,
        help="Seconds without activity before warning (default: 300, never auto-kills)",
    )
    run_parser.set_defaults(func=cmd_run)

    # Status command
    status_parser = subparsers.add_parser("status", help="Check task status")
    status_parser.add_argument("task_id", help="Task ID to check")
    status_parser.set_defaults(func=cmd_status)

    # List command
    list_parser = subparsers.add_parser("list", help="List recent tasks")
    list_parser.add_argument("--limit", "-n", type=int, default=10, help="Number of tasks to show")
    list_parser.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
