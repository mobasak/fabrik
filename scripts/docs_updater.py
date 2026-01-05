#!/usr/bin/env python3
"""
Fabrik Documentation Updater

Automatically updates documentation when code changes are detected.
Uses low-cost AI models to analyze changes and write updates directly to doc files.

This is SEPARATE from the code review workflow (review_processor.py).

Workflow:
1. Post-edit hook detects code change
2. Queues documentation update task
3. This script runs async, analyzes changes
4. Writes documentation updates DIRECTLY to files
5. User sees changes in Windsurf diff view (native Accept/Reject)

Usage:
    python scripts/docs_updater.py                    # Process queue once
    python scripts/docs_updater.py --daemon           # Run continuously
    python scripts/docs_updater.py --file <path>      # Update docs for specific file
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any

# Configuration via environment variables (Fabrik convention)
FABRIK_ROOT = Path(os.getenv("FABRIK_ROOT", "/opt/fabrik"))
DOCS_QUEUE_DIR = Path(os.getenv("FABRIK_DOCS_QUEUE", FABRIK_ROOT / ".droid" / "docs_queue"))
DOCS_LOG_DIR = Path(os.getenv("FABRIK_DOCS_LOG", FABRIK_ROOT / ".droid" / "docs_log"))
CONFIG_FILE = Path(os.getenv("FABRIK_MODELS_CONFIG", FABRIK_ROOT / "config" / "models.yaml"))
PID_FILE = DOCS_QUEUE_DIR / "docs_updater.pid"

# Batch settings
BATCH_DELAY_SECONDS = 10  # Wait for more changes before processing
MAX_BATCH_SIZE = 10

# Ensure directories exist
DOCS_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
DOCS_LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_docs_model() -> str:
    """Get the model for documentation updates from config."""
    fallback = "gemini-3-flash-preview"  # Low cost (0.2x)
    try:
        import yaml

        with open(CONFIG_FILE) as f:
            config = yaml.safe_load(f)

        # Check for documentation scenario
        docs_config = config.get("scenarios", {}).get("documentation", {})
        if "primary" in docs_config:
            return docs_config["primary"]

        return fallback
    except Exception:
        return fallback


def get_pending_tasks() -> list[dict[str, Any]]:
    """Get all pending documentation update tasks."""
    if not DOCS_QUEUE_DIR.exists():
        return []

    tasks = []
    now = datetime.now()

    for task_file in DOCS_QUEUE_DIR.glob("*.json"):
        if task_file.name == "docs_updater.pid":
            continue
        # Security: reject symlinks to prevent arbitrary file access
        if task_file.is_symlink():
            print(f"Security: Rejecting symlink task file: {task_file}", file=sys.stderr)
            continue
        try:
            task = json.loads(task_file.read_text())
            status = task.get("status")

            # Handle stuck "processing" tasks (stale after 15 minutes)
            if status == "processing":
                updated_at = task.get("updated_at", task.get("queued_at", ""))
                if updated_at:
                    try:
                        task_time = datetime.fromisoformat(
                            updated_at.replace("Z", "+00:00").replace("+00:00", "")
                        )
                        age_minutes = (now - task_time).total_seconds() / 60
                        if age_minutes > 15:
                            # Reset stale processing task to pending
                            print(
                                f"Resetting stale processing task: {task_file.name}",
                                file=sys.stderr,
                            )
                            task["status"] = "pending"
                            task["retries"] = task.get("retries", 0) + 1
                            task_file.write_text(json.dumps(task, indent=2))
                            status = "pending"
                    except (ValueError, TypeError):
                        pass

            # Include pending and failed (for retry)
            if status in ["pending", "failed"]:
                # Check retry count
                if status == "failed" and task.get("retries", 0) >= 3:
                    continue
                task["_file"] = task_file
                tasks.append(task)
        except json.JSONDecodeError as e:
            print(f"Warning: Malformed task file {task_file}: {e}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"Warning: Error reading {task_file}: {e}", file=sys.stderr)
            continue

    # Sort by queued time
    tasks.sort(key=lambda t: t.get("queued_at", ""))
    return tasks


def mark_task_status(task: dict[str, Any], status: str, result: str = "") -> None:
    """Mark a task with a status and handle appropriately."""
    task_file: Path = task.get("_file")
    if not task_file or not task_file.exists():
        return

    # Security: reject symlinks
    if task_file.is_symlink():
        print(f"Security: Rejecting symlink task file: {task_file}", file=sys.stderr)
        return

    task["status"] = status
    task["updated_at"] = datetime.now().isoformat()
    task["result"] = result[:2000]

    # Remove internal field
    save_task = {k: v for k, v in task.items() if not k.startswith("_")}

    if status == "completed":
        # Move to log directory - write updated content first, then move
        DOCS_LOG_DIR.mkdir(parents=True, exist_ok=True)
        task_file.write_text(json.dumps(save_task, indent=2))  # Update file first
        dest = DOCS_LOG_DIR / task_file.name
        shutil.move(str(task_file), str(dest))  # Then move
    elif status == "failed":
        # Increment retry count and keep in queue
        task["retries"] = task.get("retries", 0) + 1
        save_task = {k: v for k, v in task.items() if not k.startswith("_")}

        if task["retries"] >= 3:
            # Max retries reached, move to log
            DOCS_LOG_DIR.mkdir(parents=True, exist_ok=True)
            task_file.write_text(json.dumps(save_task, indent=2))  # Update file first
            dest = DOCS_LOG_DIR / task_file.name
            shutil.move(str(task_file), str(dest))
        else:
            # Keep in queue for retry
            task["status"] = "pending"  # Reset to pending
            save_task["status"] = "pending"
            task_file.write_text(json.dumps(save_task, indent=2))
    else:
        # Processing or other status - just update the file
        task_file.write_text(json.dumps(save_task, indent=2))


def analyze_change_type(file_path: str) -> str:
    """Analyze what type of change this is to guide documentation."""
    path = Path(file_path)

    # Read file content to detect patterns
    try:
        content = path.read_text() if path.exists() else ""
    except Exception:
        content = ""

    change_types = []

    # API endpoints
    if any(p in content for p in ["@app.get", "@app.post", "@router.", "FastAPI", "APIRouter"]):
        change_types.append("api_endpoint")

    # CLI arguments
    if any(p in content for p in ["argparse", "ArgumentParser", "add_argument", "typer"]):
        change_types.append("cli_command")

    # Configuration / env vars
    if any(p in content for p in ["os.getenv", "environ.get", "load_dotenv", "Settings"]):
        change_types.append("configuration")

    # Health endpoints
    if any(p in content for p in ["/health", "healthcheck", "liveness", "readiness"]):
        change_types.append("health_endpoint")

    # Database models
    if any(p in content for p in ["SQLAlchemy", "Base.metadata", "Prisma", "Model"]):
        change_types.append("database_model")

    return ", ".join(change_types) if change_types else "general"


def _sanitize_path(path: str) -> str:
    """Sanitize file path to prevent prompt injection."""
    # Remove newlines, control chars, and limit length
    return path.replace("\n", "").replace("\r", "").replace("\x00", "")[:200]


def build_docs_prompt(files: list[str], change_types: list[str]) -> str:
    """Build the prompt for the documentation model."""
    files_info = []
    for f, ct in zip(files, change_types, strict=True):
        safe_path = _sanitize_path(f)
        files_info.append(f"- {safe_path} ({ct})")

    files_str = "\n".join(files_info)

    return f"""You are updating Fabrik documentation. These files were modified:

{files_str}

Follow Fabrik documentation conventions strictly:

1. **Update docs/README.md structure map** if files were added/moved/deleted
2. **Update relevant docs in docs/reference/** based on change type:
   - api_endpoint → Update API documentation
   - cli_command → Update CLI reference
   - configuration → Update ENVIRONMENT_VARIABLES.md
   - health_endpoint → Update deployment/health docs
   - database_model → Update data model docs
3. **Add "Last Updated: {datetime.now().strftime("%Y-%m-%d")}"** to modified docs
4. **Use clear titles, purpose statements, runnable examples**
5. **Cross-reference related docs** with relative paths

IMPORTANT:
- Read the changed files to understand what was added/modified
- Only update documentation that is ACTUALLY out of sync
- Write changes DIRECTLY to the doc files
- Keep documentation concise and practical
- If no documentation update is needed, say so and don't modify files

Start by reading the changed files, then update the relevant documentation."""


def run_docs_update(files: list[str]) -> dict[str, Any]:
    """Run the documentation update using droid exec."""
    if not files:
        return {"success": True, "result": "No files to process"}

    # Analyze change types
    change_types = [analyze_change_type(f) for f in files]

    # Build prompt
    prompt = build_docs_prompt(files, change_types)

    # Get model
    model = get_docs_model()

    print(f"Running docs update with {model} for {len(files)} files...")

    try:
        # Run droid exec with medium autonomy (can write files)
        result = subprocess.run(
            [
                "droid",
                "exec",
                "--auto",
                "medium",  # Can write to docs
                "-m",
                model,
                "-o",
                "json",
                prompt,
            ],
            capture_output=True,
            text=True,
            timeout=600,  # 10 min timeout
            cwd=str(FABRIK_ROOT),
        )

        if result.returncode != 0:
            return {
                "success": False,
                "result": f"Exit code {result.returncode}: {result.stderr[:500]}",
            }

        # Parse output
        try:
            output = json.loads(result.stdout.strip())
            return {
                "success": not output.get("is_error", False),
                "result": output.get("result", "")[:2000],
            }
        except json.JSONDecodeError:
            return {"success": True, "result": result.stdout[:2000]}

    except subprocess.TimeoutExpired:
        return {"success": False, "result": "Timeout after 600s"}
    except Exception as e:
        return {"success": False, "result": str(e)[:500]}


def process_batch(tasks: list[dict[str, Any]]) -> None:
    """Process a batch of documentation update tasks."""
    if not tasks:
        return

    files = [_sanitize_path(t["file_path"]) for t in tasks]
    print(f"Processing documentation update for {len(files)} files...")

    # Mark tasks as processing first
    for task in tasks:
        mark_task_status(task, "processing")

    result = {"success": False, "result": "Unknown error"}  # Default for crash path
    try:
        # Run the update
        result = run_docs_update(files)

        # Mark all tasks based on result
        status = "completed" if result["success"] else "failed"
        for task in tasks:
            mark_task_status(task, status, result.get("result", ""))
    except Exception as e:
        # On error, mark tasks as failed for retry
        result = {"success": False, "result": str(e)[:500]}
        for task in tasks:
            mark_task_status(task, "failed", result["result"])

    # Log the update
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "files": files,
        "model": get_docs_model(),
        "success": result["success"],
        "result": result.get("result", "")[:1000],
    }

    log_file = DOCS_LOG_DIR / f"update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log_file.write_text(json.dumps(log_entry, indent=2))

    if result["success"]:
        print(f"✓ Documentation updated for {len(files)} files")
        # Send notification
        send_notification(
            f"📄 Documentation updated for {len(files)} files - check Windsurf diff view"
        )
    else:
        print(f"✗ Documentation update failed: {result.get('result', 'unknown error')}")


def send_notification(message: str) -> None:
    """Send notification about documentation updates."""
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


def _acquire_lock() -> int | None:
    """Acquire exclusive lock using fcntl. Returns file descriptor or None."""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Security: reject symlinks
    if PID_FILE.exists() and PID_FILE.is_symlink():
        print(f"Security: Rejecting symlink PID file: {PID_FILE}", file=sys.stderr)
        return None

    try:
        fd = os.open(str(PID_FILE), os.O_CREAT | os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.write(fd, str(os.getpid()).encode())
        os.fsync(fd)
        return fd
    except OSError:
        print("Another docs updater is running, exiting")
        return None


def _release_lock(fd: int) -> None:
    """Release the lock and clean up."""
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def run_once() -> None:
    """Process queue once."""
    fd = _acquire_lock()
    if fd is None:
        return

    try:
        tasks = get_pending_tasks()
        if tasks:
            process_batch(tasks[:MAX_BATCH_SIZE])
        else:
            print("No pending documentation tasks")
    finally:
        _release_lock(fd)


def run_daemon() -> None:
    """Run continuously, processing batches."""
    fd = _acquire_lock()
    if fd is None:
        return

    try:
        print("Documentation updater daemon started")
        while True:
            tasks = get_pending_tasks()

            if tasks:
                # Wait for batch to accumulate
                time.sleep(BATCH_DELAY_SECONDS)
                tasks = get_pending_tasks()

                if tasks:
                    process_batch(tasks[:MAX_BATCH_SIZE])
            else:
                time.sleep(10)
    except KeyboardInterrupt:
        print("\nDaemon stopped")
    finally:
        _release_lock(fd)


def update_single_file(file_path: str) -> None:
    """Update documentation for a single file immediately."""
    print(f"Updating documentation for: {file_path}")
    result = run_docs_update([file_path])

    if result["success"]:
        print("✓ Documentation updated")
        print(f"  Result: {result.get('result', '')[:200]}")
    else:
        print(f"✗ Failed: {result.get('result', 'unknown error')}")


def main():
    parser = argparse.ArgumentParser(description="Fabrik Documentation Updater")
    parser.add_argument("--daemon", action="store_true", help="Run continuously")
    parser.add_argument("--file", type=str, help="Update docs for a specific file")

    args = parser.parse_args()

    if args.file:
        update_single_file(args.file)
    elif args.daemon:
        run_daemon()
    else:
        run_once()


if __name__ == "__main__":
    main()
