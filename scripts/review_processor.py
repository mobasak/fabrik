#!/usr/bin/env python3
"""
Review Processor - Async dual-model code review and docs update

Processes queued review tasks from the post-edit hook.
Runs dual-model code review using models from config/models.yaml.
Updates documentation if needed.

Usage:
    python scripts/review_processor.py          # Process queue once
    python scripts/review_processor.py --daemon # Run continuously
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from typing import Any, TextIO

# Import ProcessMonitor for proper completion detection
ProcessMonitor: Any
try:
    process_monitor_module = importlib.import_module("process_monitor")
    ProcessMonitor = process_monitor_module.ProcessMonitor
    PROCESS_MONITOR_AVAILABLE = True
except Exception:
    ProcessMonitor = None
    PROCESS_MONITOR_AVAILABLE = False

# Paths - configurable via env vars (Fabrik convention)
FABRIK_ROOT = Path(os.getenv("FABRIK_ROOT", "/opt/fabrik"))
QUEUE_DIR = Path(os.getenv("FABRIK_REVIEW_QUEUE", str(FABRIK_ROOT / ".droid/review_queue")))
RESULTS_DIR = Path(os.getenv("FABRIK_REVIEW_RESULTS", str(FABRIK_ROOT / ".droid/review_results")))
PID_FILE = QUEUE_DIR / "processor.pid"
CONFIG_FILE = Path(os.getenv("FABRIK_MODELS_CONFIG", str(FABRIK_ROOT / "config/models.yaml")))

# Batch settings
BATCH_DELAY_SECONDS = 5  # Wait for more edits before processing
MAX_BATCH_SIZE = 10  # Max files per review batch


def _stream_reader(stream: TextIO, queue: Queue[str]) -> None:
    """Read lines from a stream and push them to a queue."""
    try:
        for line in iter(stream.readline, ""):
            queue.put(line)
    finally:
        with suppress(Exception):
            stream.close()


def run_command_with_monitor(
    args: list[str],
    timeout_seconds: int,
    warn_after_seconds: int = 300,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """
    Run a subprocess with optional ProcessMonitor support and streaming capture.

    - Uses stdin=DEVNULL to avoid interactive blocking.
    - Streams stdout/stderr via background threads to prevent buffer deadlocks.
    - Emits periodic diagnostics via ProcessMonitor (if available) when no output
      is observed for `warn_after_seconds`.
    - Kills the process after `timeout_seconds` (graceful terminate → kill).
    """
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

    proc = subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(cwd) if cwd else None,
        env=env,
        bufsize=1,
    )

    monitor: Any | None = None
    if PROCESS_MONITOR_AVAILABLE:
        try:
            monitor = ProcessMonitor(proc, warn_threshold=warn_after_seconds)
            print("ProcessMonitor active (CPU/IO/Network monitoring)", file=sys.stderr)
        except Exception as e:
            print(f"ProcessMonitor init failed: {e}", file=sys.stderr)

    stdout_queue: Queue[str] = Queue()
    stderr_queue: Queue[str] = Queue()
    threads = [
        threading.Thread(
            target=_stream_reader,
            args=(proc.stdout, stdout_queue),
            daemon=True,
        ),
        threading.Thread(
            target=_stream_reader,
            args=(proc.stderr, stderr_queue),
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    start_time = time.time()
    last_activity = start_time
    last_warning = 0.0
    timed_out = False

    try:
        while True:
            activity_detected = False

            try:
                line = stdout_queue.get(timeout=1)
                stdout_lines.append(line)
                activity_detected = True
                last_activity = time.time()
                if monitor:
                    monitor.record_activity()
            except Empty:
                pass

            try:
                while True:
                    line = stderr_queue.get_nowait()
                    stderr_lines.append(line)
                    activity_detected = True
                    last_activity = time.time()
                    if monitor:
                        monitor.record_activity()
            except Empty:
                pass

            if proc.poll() is not None and stdout_queue.empty() and stderr_queue.empty():
                break

            if time.time() - start_time > timeout_seconds:
                timed_out = True
                proc.kill()
                break

            # Emit diagnostics if no output for a while
            if (
                not activity_detected
                and (time.time() - last_activity) > warn_after_seconds
                and (time.time() - last_warning) > 60
            ):
                if monitor:
                    diagnosis: dict[str, Any] = monitor.analyze()
                    state = diagnosis.get("state", "UNKNOWN")
                    reason = diagnosis.get("reason", "")
                    metrics = diagnosis.get("metrics", {})

                    metric_str = ""
                    if metrics:
                        metric_str = (
                            f" CPU={metrics.get('avg_cpu', 0):.1f}%"
                            f" IO={metrics.get('total_io_bytes', 0)}B"
                            f" Net={metrics.get('any_network', False)}"
                        )

                    print(
                        f"[monitor] {state}: {reason}{metric_str}",
                        file=sys.stderr,
                    )
                else:
                    elapsed = int(time.time() - last_activity)
                    print(
                        f"[monitor] No output for {elapsed}s (process still running)",
                        file=sys.stderr,
                    )
                last_warning = time.time()
    finally:
        for thread in threads:
            thread.join(timeout=1)

        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    return {
        "returncode": proc.returncode if proc.returncode is not None else -1,
        "stdout": "".join(stdout_lines),
        "stderr": "".join(stderr_lines),
        "timed_out": timed_out,
    }


def get_review_models() -> list[str]:
    """Get code review models from config/models.yaml dynamically.

    Returns fallback models if config is missing or empty.
    """
    fallback = ["gpt-5.1-codex-max", "gemini-3-flash-preview"]
    try:
        import yaml  # type: ignore[import-untyped]

        with open(CONFIG_FILE) as f:
            config: dict[str, Any] = yaml.safe_load(f)

        code_review = config.get("scenarios", {}).get("code_review", {})

        # Check for 'models' list (dual-model) or fall back to primary/alternatives
        if "models" in code_review:
            models = code_review["models"]
            # Return fallback if models list is empty or not a list
            if not models or not isinstance(models, list):
                return fallback
            return models

        models = []
        if "primary" in code_review:
            models.append(code_review["primary"])
        if "alternatives" in code_review:
            models.extend(code_review["alternatives"])

        return models if models else fallback
    except Exception as e:
        print(f"Warning: Could not read models from config: {e}", file=sys.stderr)
        return ["gpt-5.1-codex-max", "gemini-3-flash-preview"]


def get_pending_tasks() -> list[dict[str, Any]]:
    """Get all pending review tasks."""
    if not QUEUE_DIR.exists():
        return []

    tasks: list[dict[str, Any]] = []
    for task_file in QUEUE_DIR.glob("*.json"):
        if task_file.name == "processor.pid":
            continue
        # Security: reject symlinks to prevent arbitrary file reads
        if task_file.is_symlink():
            print(f"Security: Skipping symlink task file: {task_file}", file=sys.stderr)
            continue
        try:
            task: dict[str, Any] = json.loads(task_file.read_text())
            # Validate required fields to prevent KeyError crashes
            if not task.get("file_path"):
                print(
                    f"Warning: Skipping malformed task (no file_path): {task_file}", file=sys.stderr
                )
                continue
            if task.get("status") == "pending":
                task["_file"] = task_file
                tasks.append(task)
        except json.JSONDecodeError as e:
            print(f"Warning: Malformed JSON in {task_file}: {e}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"Warning: Error reading {task_file}: {e}", file=sys.stderr)
            continue

    # Sort by queued time
    tasks.sort(key=lambda t: t.get("queued_at", ""))
    return tasks


def mark_task_status(task: dict[str, Any], status: str, result: str | None = None) -> None:
    """Update task status."""
    task_file = task.get("_file")
    if not task_file:
        return

    # Security: reject symlinks to prevent arbitrary file overwrites
    if task_file.is_symlink():
        print(f"Security: Rejecting symlink task file: {task_file}", file=sys.stderr)
        return

    task["status"] = status
    task["processed_at"] = datetime.now().isoformat()
    if result:
        task["result"] = result

    # Remove internal field before saving
    save_task = {k: v for k, v in task.items() if not k.startswith("_")}
    task_file.write_text(json.dumps(save_task, indent=2))

    # Move completed tasks to results (keep failed in queue for retry)
    if status == "completed":
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        dest = RESULTS_DIR / task_file.name
        shutil.move(str(task_file), str(dest))  # Cross-filesystem safe
    elif status == "failed":
        # Reset to pending for retry (max 3 attempts)
        retries = task.get("retries", 0)
        if retries >= 3:
            # Max retries reached, move to results
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            dest = RESULTS_DIR / task_file.name
            shutil.move(str(task_file), str(dest))  # Cross-filesystem safe
        else:
            # Increment retry count and reset to pending
            task["retries"] = retries + 1
            task["status"] = "pending"
            save_task = {k: v for k, v in task.items() if not k.startswith("_")}
            task_file.write_text(json.dumps(save_task, indent=2))


def run_dual_model_review(files: list[str]) -> dict[str, dict[str, Any]]:
    """Run code review with both models from config."""
    models = get_review_models()
    results: dict[str, dict[str, Any]] = {}

    # Sanitize ALL file paths to prevent prompt injection (remove newlines, control chars)
    # Include ALL files in review, not just first 5, to avoid coverage gaps
    safe_files = [f.replace("\n", "").replace("\r", "")[:200] for f in files]
    files_str = ", ".join(safe_files)

    review_prompt = f"""Review these recently changed files for bugs, security issues, and Fabrik convention violations:

Files: {files_str}

Focus on:
1. Security vulnerabilities
2. Error handling gaps
3. Fabrik conventions (no hardcoded localhost, proper health checks, env vars for config)
4. Logic errors

Be concise. Only report actual issues, not style suggestions."""

    for model in models:
        try:
            command = [
                "droid",
                "exec",
                "--auto",
                "low",
                "-m",
                model,
                "-o",
                "json",
                review_prompt,
            ]

            result = run_command_with_monitor(
                command,
                timeout_seconds=600,
                warn_after_seconds=300,
                cwd=str(os.getenv("FABRIK_ROOT", "/opt/fabrik")),
            )

            if result["timed_out"]:
                results[model] = {
                    "status": "error",
                    "error": "Process killed after 10 minute timeout",
                }
                continue

            if result["returncode"] == 0:
                stdout = result["stdout"] or ""
                # Handle empty or non-JSON stdout
                if not stdout.strip():
                    results[model] = {
                        "status": "error",
                        "error": "Empty response from droid exec",
                    }
                    continue
                try:
                    output = json.loads(stdout)
                    results[model] = {
                        "status": "success",
                        "review": output.get("finalText", stdout[:2000]),
                    }
                except json.JSONDecodeError:
                    # Non-JSON but non-empty - treat as raw review text
                    results[model] = {
                        "status": "success",
                        "review": stdout[:2000],
                    }
            else:
                error_text = result["stderr"] or f"Exit code: {result['returncode']}"
                results[model] = {
                    "status": "error",
                    "error": error_text[:500],
                }
        except Exception as e:
            results[model] = {
                "status": "error",
                "error": str(e),
            }

    return results


def check_docs_update_needed(files: list[str]) -> list[str]:
    """Check which files need documentation updates."""
    needs_update = []

    for file_path in files:
        # Check if this is a source file that should have docs
        if any(p in file_path for p in ["src/", "lib/", "api/"]):
            # Check if there's a corresponding doc
            # This is a simple heuristic - can be expanded
            needs_update.append(file_path)

    return needs_update


def run_docs_update(files: list[str]) -> bool:
    """Trigger documentation update for changed files.

    Returns True if docs update succeeded, False if it failed.
    """
    if not files:
        return True  # No files to update is success

    # Sanitize ALL file paths to prevent prompt injection - include all files
    safe_files = [f.replace("\n", "").replace("\r", "")[:200] for f in files]
    files_str = ", ".join(safe_files)

    docs_prompt = f"""These files were recently changed: {files_str}

Check if documentation needs updating:
1. If API endpoints changed, update docs/reference/
2. If CLI commands changed, update relevant docs
3. If config options changed, update CONFIGURATION.md
4. Update docs/INDEX.md structure map if files were added/moved

Only make changes if documentation is actually out of sync."""

    try:
        command = [
            "droid",
            "exec",
            "--auto",
            "medium",
            "-m",
            (get_review_models() or ["gpt-5.1-codex-max"])[0],
            "-o",
            "json",
            docs_prompt,
        ]

        result = run_command_with_monitor(
            command,
            timeout_seconds=600,
            warn_after_seconds=300,
            cwd=FABRIK_ROOT,
        )

        if result["returncode"] != 0:
            err_text = result["stderr"] or "no error"
            print(
                f"Docs update failed (exit {result['returncode']}): {err_text[:200]}",
                file=sys.stderr,
            )
            return False
        else:
            # Log what docs update did
            stdout = result.get("stdout", "")
            if stdout:
                # Ensure RESULTS_DIR exists before writing log
                RESULTS_DIR.mkdir(parents=True, exist_ok=True)
                docs_log = RESULTS_DIR / "docs_updates.log"
                with open(docs_log, "a") as f:
                    f.write(f"\n=== {datetime.now().isoformat()} ===\n")
                    f.write(f"Files: {files_str}\n")
                    f.write(f"Result: {stdout[:2000]}\n")
                print(f"Docs update completed - logged to {docs_log}")
            return True
    except Exception as e:
        print(f"Docs update failed: {e}", file=sys.stderr)
        return False


def send_notification(message: str) -> None:
    """Send notification about review results."""
    # Use env var for notification script path (Fabrik convention: config via env)
    notify_path = os.getenv(
        "FABRIK_NOTIFY_SCRIPT", os.path.expanduser("~/.factory/hooks/notify.sh")
    )
    notify_script = Path(notify_path)
    if notify_script.exists():
        with suppress(Exception):
            subprocess.run(
                [str(notify_script)],
                input=json.dumps({"message": message}),
                text=True,
                timeout=5,
            )


def process_batch(tasks: list[dict[str, Any]]) -> None:
    """Process a batch of review tasks."""
    if not tasks:
        return

    files = [t["file_path"] for t in tasks]
    files_needing_docs = [t["file_path"] for t in tasks if t.get("needs_docs_update")]

    print(f"Processing {len(files)} files for review...")

    # Mark as processing - wrap entire batch in try/finally to prevent orphaned tasks
    for task in tasks:
        mark_task_status(task, "processing")

    review_results: dict[str, Any] = {}
    try:
        # Run dual-model review
        review_results = run_dual_model_review(files)
    except Exception as e:
        # On any error, reset tasks to failed for retry
        print(f"Review failed: {e}", file=sys.stderr)
        for task in tasks:
            mark_task_status(task, "failed", str(e))
        return

    # Check for issues - use phrases that indicate actual problems, not just word presence
    has_issues = False
    issue_summary: list[str] = []

    # Patterns that indicate actual issues found (not "no issues")
    issue_patterns = [
        "found issue",
        "found bug",
        "found error",
        "vulnerability detected",
        "security issue",
        "error handling gap",
        "potential issue",
        "issue found",
        "bug found",
        "issues found",
        "issues identified",
        "# issues",
        "## issues",
        "# review findings",
        "## review findings",
        "# findings",
        "## findings",
        "potential deadlock",
        "concurrency",
        "race condition",
        "hardcoded",
        "missing error",
        "unhandled",
        "injection",
        "sql injection",
        "xss",
        "valueerror",
        "keyerror",
        "typeerror",
        "raises",
        "throws",
        "logic error",
        "flawed",
        "dead code",
        "unused",
    ]
    # Patterns that indicate NO issues
    no_issue_patterns = [
        "no issue",
        "no bug",
        "no error",
        "no vulnerability",
        "no problems",
        "looks good",
        "no findings",
        "no hardcoded",
        "not hardcoded",
        "no race",
        "no deadlock",
        "no concurrency",
        "no security",
        "clean",
        "all clear",
    ]

    for model, result in review_results.items():
        if result.get("status") == "success":
            review_text = result.get("review", "").lower()

            # Skip empty reviews (treat as "no issues found")
            if not review_text.strip():
                continue

            # Check for explicit "no issues" - but don't skip if issue patterns also found
            has_no_issue_phrase = any(pattern in review_text for pattern in no_issue_patterns)
            has_issue_phrase = any(pattern in review_text for pattern in issue_patterns)

            # If both patterns found, prioritize issue detection
            if has_no_issue_phrase and not has_issue_phrase:
                continue

            # Check for issue patterns
            if any(pattern in review_text for pattern in issue_patterns):
                has_issues = True
                issue_summary.append(f"{model}: Found issues")

    # Run docs update if needed
    docs_update_failed = False
    if files_needing_docs:
        print(f"Checking docs update for {len(files_needing_docs)} files...")
        docs_update_failed = not run_docs_update(files_needing_docs)

    # Determine final status based on review results
    all_failed = all(r.get("status") in ["error", "timeout"] for r in review_results.values())
    any_failed = any(r.get("status") in ["error", "timeout"] for r in review_results.values())

    # Store full results - don't truncate (both models' reviews are important)
    result_summary = json.dumps(review_results, indent=2)

    if all_failed:
        # All reviews failed - mark as failed for retry
        for task in tasks:
            mark_task_status(task, "failed", result_summary)
        send_notification(
            f"Code review FAILED for {len(files)} files - all models errored/timed out"
        )
    else:
        # At least one review succeeded
        for task in tasks:
            mark_task_status(task, "completed", result_summary)

        # Send notification if issues found or docs update failed
        if has_issues:
            send_notification(
                f"Code review found issues in {len(files)} files: {', '.join(issue_summary)}"
            )
        elif docs_update_failed:
            send_notification(
                f"Code review OK but docs update FAILED for {len(files_needing_docs)} files"
            )
        elif any_failed:
            send_notification(
                f"Code review partial: {len(files)} files reviewed, some models failed"
            )

    print(f"Completed review of {len(files)} files")


def cleanup_orphaned_tasks() -> None:
    """Reset tasks stuck in 'processing' state back to 'pending'.

    Called at startup to recover from crashes.
    """
    if not QUEUE_DIR.exists():
        return

    for task_file in QUEUE_DIR.glob("*.json"):
        if task_file.name == "processor.pid":
            continue
        if task_file.is_symlink():
            continue
        try:
            task = json.loads(task_file.read_text())
            if task.get("status") == "processing":
                print(f"Resetting orphaned task: {task_file.name}")
                task["status"] = "pending"
                task_file.write_text(json.dumps(task, indent=2))
        except Exception:
            continue


def run_once() -> None:
    """Process queue once."""
    # Write PID file to prevent concurrent processors
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Security: reject symlinks to prevent arbitrary file overwrites
    if PID_FILE.exists() and PID_FILE.is_symlink():
        print(f"Security: Rejecting symlink PID file: {PID_FILE}", file=sys.stderr)
        return

    # Check if another processor is running
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)  # Check if process exists
            print("Another processor is running, exiting")
            return
        except (ProcessLookupError, ValueError):
            PID_FILE.unlink(missing_ok=True)

    # Write our PID
    PID_FILE.write_text(str(os.getpid()))

    try:
        # Cleanup orphaned tasks from previous crashes
        cleanup_orphaned_tasks()
        tasks = get_pending_tasks()
        if tasks:
            process_batch(tasks[:MAX_BATCH_SIZE])
    finally:
        PID_FILE.unlink(missing_ok=True)


def run_daemon() -> None:
    """Run continuously, processing batches."""
    # Check if another processor is running
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Security: reject symlinks to prevent arbitrary file overwrites
    if PID_FILE.exists() and PID_FILE.is_symlink():
        print(f"Security: Rejecting symlink PID file: {PID_FILE}", file=sys.stderr)
        return

    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)  # Check if process exists
            print("Another processor is running, exiting")
            return
        except (ProcessLookupError, ValueError):
            PID_FILE.unlink(missing_ok=True)

    # Write PID file
    PID_FILE.write_text(str(os.getpid()))

    try:
        # Cleanup orphaned tasks from previous crashes
        cleanup_orphaned_tasks()
        print("Review processor daemon started")
        while True:
            tasks = get_pending_tasks()

            if tasks:
                # Wait for batch to accumulate
                time.sleep(BATCH_DELAY_SECONDS)
                tasks = get_pending_tasks()  # Re-check after delay

                if tasks:
                    process_batch(tasks[:MAX_BATCH_SIZE])
            else:
                # No tasks - check less frequently
                time.sleep(10)
    finally:
        PID_FILE.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Process code review queue")
    parser.add_argument("--daemon", action="store_true", help="Run continuously")
    args = parser.parse_args()

    if args.daemon:
        run_daemon()
    else:
        run_once()


if __name__ == "__main__":
    main()
