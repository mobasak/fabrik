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
    # Process queue once (default)
    python scripts/docs_updater.py

    # Run continuously as daemon
    python scripts/docs_updater.py --daemon

    # Update docs for specific file
    python scripts/docs_updater.py --file src/api.py

    # Custom prompt from task file (with files to check)
    python scripts/docs_updater.py --task-file tasks/update-docs.md --check-files src/api.py src/models.py

    # Custom prompt directly
    python scripts/docs_updater.py --prompt "Update CHANGELOG for auth changes" --check-files src/auth/*.py

    # Validation and sync
    python scripts/docs_updater.py --check           # Validate docs, fail on drift
    python scripts/docs_updater.py --sync            # Create missing stubs
    python scripts/docs_updater.py --sync --dry-run  # Preview changes
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from typing import Any

# Import ProcessMonitor for droid exec monitoring
try:
    from process_monitor import ProcessMonitor

    PROCESS_MONITOR_AVAILABLE = True
except ImportError:
    PROCESS_MONITOR_AVAILABLE = False


def _stream_reader(stream, output_queue: Queue, name: str) -> None:
    """Read lines from a stream and push them to a queue (for threading)."""
    try:
        for line in iter(stream.readline, ""):
            output_queue.put((name, line))
    finally:
        with suppress(Exception):
            stream.close()
        output_queue.put((name, None))  # Signal EOF


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

1. **UPDATE CHANGELOG.md** (MANDATORY for all code changes):
   - Add entry under `## [Unreleased]` section
   - Use format: `### Added/Changed/Fixed - <Brief Title> ({datetime.now().strftime("%Y-%m-%d")})`
   - List what was added/changed/fixed with file paths
   - Keep entries concise but informative

2. **Update docs/INDEX.md structure map** if files were added/moved/deleted

3. **Update relevant docs in docs/reference/** based on change type:
   - api_endpoint → Update API documentation
   - cli_command → Update CLI reference
   - configuration → Update ENVIRONMENT_VARIABLES.md
   - health_endpoint → Update deployment/health docs
   - database_model → Update data model docs

4. **Add "Last Updated: {datetime.now().strftime("%Y-%m-%d")}"** to modified docs

5. **Use clear titles, purpose statements, runnable examples**

6. **Cross-reference related docs** with relative paths

IMPORTANT:
- ALWAYS update CHANGELOG.md for code changes - no exceptions
- Read the changed files to understand what was added/modified
- Only update other documentation that is ACTUALLY out of sync
- Write changes DIRECTLY to the doc files
- Keep documentation concise and practical

Start by reading the changed files, then update CHANGELOG.md first, then other relevant documentation."""


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

    timeout_seconds = 600  # 10 min timeout
    warn_after_seconds = 300  # Warn after 5 min of no activity
    args = [
        "droid",
        "exec",
        "--auto",
        "medium",  # Can write to docs
        "-m",
        model,
        "-o",
        "json",
        prompt,
    ]

    try:
        # Use Popen with threading for proper ProcessMonitor polling
        process = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(FABRIK_ROOT),
        )

        # Initialize ProcessMonitor if available
        monitor = None
        if PROCESS_MONITOR_AVAILABLE:
            with suppress(Exception):
                monitor = ProcessMonitor(process, warn_threshold=warn_after_seconds)

        # Use threading to read stdout/stderr without blocking
        output_queue: Queue = Queue()
        stdout_thread = threading.Thread(
            target=_stream_reader, args=(process.stdout, output_queue, "stdout")
        )
        stderr_thread = threading.Thread(
            target=_stream_reader, args=(process.stderr, output_queue, "stderr")
        )
        stdout_thread.start()
        stderr_thread.start()

        # Collect output while polling ProcessMonitor
        stdout_lines = []
        stderr_lines = []
        start_time = time.time()
        streams_closed = 0

        while streams_closed < 2:
            # Check timeout
            if time.time() - start_time > timeout_seconds:
                process.kill()
                process.wait()
                return {"success": False, "result": f"Timeout after {timeout_seconds}s"}

            # Poll ProcessMonitor periodically
            if monitor and (time.time() - start_time) % 30 < 1:
                diagnosis = monitor.analyze()
                if diagnosis["state"] in ("LIKELY_STUCK", "CONFIRMED_STUCK"):
                    print(f"⚠️ ProcessMonitor: {diagnosis['reason']}", file=sys.stderr)

            try:
                name, line = output_queue.get(timeout=1.0)
                if line is None:
                    streams_closed += 1
                elif name == "stdout":
                    stdout_lines.append(line)
                    if monitor:
                        monitor.record_activity()
                else:
                    stderr_lines.append(line)
            except Empty:
                continue

        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)
        process.wait()

        stdout = "".join(stdout_lines)
        stderr = "".join(stderr_lines)

        if process.returncode != 0:
            return {
                "success": False,
                "result": f"Exit code {process.returncode}: {stderr[:500]}",
            }

        # Parse output
        try:
            output = json.loads(stdout.strip())
            return {
                "success": not output.get("is_error", False),
                "result": output.get("result", "")[:2000],
            }
        except json.JSONDecodeError:
            return {"success": True, "result": stdout[:2000]}

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


# =============================================================================
# Documentation Structure Automation (docs-automation plan)
# =============================================================================

PLANS_DIR = FABRIK_ROOT / "docs" / "development" / "plans"
PLANS_INDEX = FABRIK_ROOT / "docs" / "development" / "PLANS.md"
README_PATH = FABRIK_ROOT / "docs" / "INDEX.md"
TEMPLATE_PATH = FABRIK_ROOT / "templates" / "docs" / "MODULE_REFERENCE_TEMPLATE.md"

# All docs that need staleness/completeness checks
MANUAL_DOCS = [
    "README.md",
    "tasks.md",
    "AGENTS.md",
    "docs/INDEX.md",
    "docs/QUICKSTART.md",
    "docs/CONFIGURATION.md",
    "docs/TROUBLESHOOTING.md",
    "docs/BUSINESS_MODEL.md",
]

# Placeholder markers that indicate incomplete stubs
STUB_MARKERS = [
    "[One-line description",
    "[TODO",
    "[TBD",
    "[PLACEHOLDER",
    "| ... | ... | ... |",
    "[team/person]",
    "[Related doc](../path.md)",
]

# Max days before a doc is considered stale
STALENESS_DAYS = 90

STRUCTURE_BLOCK_RE = re.compile(
    r"(<!-- AUTO-GENERATED:STRUCTURE:START -->).*?(<!-- AUTO-GENERATED:STRUCTURE:END -->)",
    re.S,
)
PLANS_BLOCK_RE = re.compile(
    r"(<!-- AUTO-GENERATED:PLANS:START -->).*?(<!-- AUTO-GENERATED:PLANS:END -->)",
    re.S,
)


def is_public_module(p: Path) -> bool:
    """Only create stubs for modules with __all__ or README.md."""
    if not (p / "__init__.py").exists():
        return False
    if (p / "README.md").exists():
        return True
    init = (p / "__init__.py").read_text(encoding="utf-8", errors="ignore")
    return "__all__" in init


def detect_new_modules() -> list[Path]:
    """Find public src/fabrik/*/ without docs/reference/*.md."""
    base = FABRIK_ROOT / "src" / "fabrik"
    if not base.exists():
        return []
    mods = []
    for d in base.iterdir():
        if d.is_dir() and is_public_module(d):
            ref = FABRIK_ROOT / "docs" / "reference" / f"{d.name}.md"
            if not ref.exists():
                mods.append(d)
    return mods


def extract_block_body(text: str, block_re: re.Pattern) -> str | None:
    """Extract current body from bounded block (excluding stamp line)."""
    match = block_re.search(text)
    if not match:
        return None
    content = match.group(0)
    lines = content.split("\n")
    body_lines = [line for line in lines if not line.startswith("<!--")]
    return "\n".join(body_lines).strip()


def replace_block(
    text: str, new_body: str, block_re: re.Pattern, block_name: str
) -> tuple[str, bool]:
    """Replace block only if body changed; do not update stamp otherwise."""
    current_body = extract_block_body(text, block_re)
    if current_body == new_body.strip():
        return text, False  # No change needed — idempotent

    stamp = datetime.now().strftime("%Y-%m-%dT%H:%M")

    def replacer(m):
        return f"{m.group(1)}\n<!-- AUTO-GENERATED:{block_name} v1 | {stamp} -->\n{new_body}\n{m.group(2)}"

    return block_re.sub(replacer, text), True


def parse_plan_status(plan_path: Path) -> tuple[str, int, int]:
    """Extract status and checkbox counts from a plan file.

    Returns: (status, checked_count, total_count)
    Status is normalized: COMPLETE, PARTIAL, NOT_DONE, IN_PROGRESS, or Active
    """
    try:
        content = plan_path.read_text()
    except Exception:
        return "Unknown", 0, 0

    # Extract status line (handles emojis like ✅, ⚠️, ❌)
    status = "Active"
    status_match = re.search(r"\*\*Status:\*\*\s*(.+?)(?:\n|$)", content)
    if status_match:
        raw_status = status_match.group(1).strip()
        # Normalize status
        lower = raw_status.lower()
        if "complete" in lower:
            status = "COMPLETE"
        elif "partial" in lower:
            status = "PARTIAL"
        elif "not done" in lower or "not_done" in lower:
            status = "NOT_DONE"
        elif "in progress" in lower or "in_progress" in lower:
            status = "IN_PROGRESS"
        else:
            status = raw_status[:20]  # Truncate if weird

    # Count checkboxes in DONE WHEN section (handles [x], [X], [ ])
    checked = len(re.findall(r"- \[[xX]\]", content))
    unchecked = len(re.findall(r"- \[ \]", content))
    total = checked + unchecked

    return status, checked, total


def generate_plans_table() -> str:
    """Generate markdown table of all plan files with real status."""
    if not PLANS_DIR.exists():
        return "| Plan | Date | Status | Progress |\n|------|------|--------|----------|\n| (none) | - | - | - |"

    # Use glob for top-level only (subfolders are for grouped incomplete work)
    plans = sorted(PLANS_DIR.glob("*.md"))
    if not plans:
        return "| Plan | Date | Status | Progress |\n|------|------|--------|----------|\n| (none) | - | - | - |"

    lines = ["| Plan | Date | Status | Progress |", "|------|------|--------|----------|"]
    for p in plans:
        date = p.name[:10] if len(p.name) > 10 else "-"
        status, checked, total = parse_plan_status(p)
        progress = f"{checked}/{total}" if total > 0 else "-"
        lines.append(f"| [{p.name}](plans/{p.name}) | {date} | {status} | {progress} |")
    return "\n".join(lines)


def sync_plans_index(dry_run: bool = False) -> tuple[bool, str]:
    """Sync PLANS.md bounded block. Returns (changed, message)."""
    if not PLANS_INDEX.exists():
        return False, "Missing docs/development/PLANS.md"

    text = PLANS_INDEX.read_text()
    new_body = generate_plans_table()
    new_text, changed = replace_block(text, new_body, PLANS_BLOCK_RE, "PLANS")

    if not changed:
        return False, "PLANS.md already up to date"

    if dry_run:
        return True, f"Would update PLANS.md:\n{new_body}"

    PLANS_INDEX.write_text(new_text)
    return True, "Updated PLANS.md"


def validate_plans_indexed() -> list[str]:
    """Check all plan files are in PLANS.md. For --check mode."""
    if not PLANS_INDEX.exists():
        return ["Missing docs/development/PLANS.md"]

    idx = PLANS_INDEX.read_text()
    errors = []
    if PLANS_DIR.exists():
        for p in PLANS_DIR.glob("*.md"):
            if p.name not in idx:
                errors.append(f"Plan not indexed: {p.name}")
    return errors


def validate_plan_consistency() -> list[str]:
    """Check plan status matches checkbox completion. For --check mode.

    ERROR: Plan marked COMPLETE but has unchecked boxes
    WARNING: Plan marked COMPLETE for >14 days (should archive)
    """
    errors = []
    if not PLANS_DIR.exists():
        return errors

    from datetime import timedelta

    for p in PLANS_DIR.glob("*.md"):
        status, checked, total = parse_plan_status(p)

        # ERROR: COMPLETE with unchecked boxes
        if status == "COMPLETE" and total > 0 and checked < total:
            errors.append(
                f"ERROR: {p.name} marked COMPLETE but has {total - checked} unchecked items"
            )

        # WARNING: COMPLETE plans should be archived after 14 days
        if status == "COMPLETE":
            try:
                # Extract date from filename YYYY-MM-DD-slug.md
                date_str = p.name[:10]
                plan_date = datetime.strptime(date_str, "%Y-%m-%d")
                age = datetime.now() - plan_date
                if age > timedelta(days=14):
                    errors.append(
                        f"WARNING: {p.name} is COMPLETE and {age.days} days old - consider archiving"
                    )
            except ValueError:
                pass  # Invalid date format, skip age check

    return errors


def create_module_stub(module: Path) -> bool:
    """Create reference doc stub for a module. Returns True if created."""
    out = FABRIK_ROOT / "docs" / "reference" / f"{module.name}.md"
    if out.exists():
        return False

    try:
        if TEMPLATE_PATH.exists():
            content = TEMPLATE_PATH.read_text().format(
                module_name=module.name,
                date=datetime.now().date().isoformat(),
            )
        else:
            content = f"""# {module.name}

**Last Updated:** {datetime.now().date().isoformat()}

## Purpose

[One-line description of what this module does]

## Usage

```python
from fabrik.{module.name} import ...
```

## Configuration

| Env Var | Description | Default |
|---------|-------------|---------|
| ... | ... | ... |

## Ownership

- **Owner:** [team/person]
- **SLA:** [response time expectation]

## See Also

- [Related doc](../path.md)
"""
        out.write_text(content)
        return True
    except OSError as e:
        print(f"Error creating stub {out}: {e}", file=sys.stderr)
        return False


def check_stub_completeness() -> list[str]:
    """Check that reference docs aren't just empty stubs."""
    issues = []
    ref_dir = FABRIK_ROOT / "docs" / "reference"
    if not ref_dir.exists():
        return issues

    for doc in ref_dir.glob("*.md"):
        content = doc.read_text()
        for marker in STUB_MARKERS:
            if marker in content:
                issues.append(
                    f"Incomplete stub: {doc.relative_to(FABRIK_ROOT)} (contains '{marker[:20]}...')"
                )
                break
    return issues


def check_link_integrity() -> list[str]:
    """Check all internal markdown links are valid."""
    issues = []
    docs_dir = FABRIK_ROOT / "docs"
    if not docs_dir.exists():
        return issues

    # Match markdown links but not code blocks or regex patterns
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    # Skip these path prefixes (external Factory docs, not our files)
    external_prefixes = ("/cli/", "/guides/", "/web/", "/reference/")

    # Skip files that are copies of external docs
    skip_files = (
        "droid-exec-headless.md",
        "building-interactive-apps-with-droid-exec.md",
        "factory-hooks.md",
        "factoryai-power-user-settings.md",
        "factory-skills.md",
        "factory-enterprise.md",
    )

    for doc in docs_dir.rglob("*.md"):
        # Skip known external doc copies
        if doc.name in skip_files:
            continue

        # Skip archived docs and design archives
        if "/archive" in str(doc) or "/.archive" in str(doc):
            continue

        content = doc.read_text()
        for match in link_pattern.finditer(content):
            link_text, link_path = match.groups()

            # Skip external links, anchors, mailto
            if link_path.startswith(("http://", "https://", "#", "mailto:")):
                continue

            # Skip external Factory doc paths
            if link_path.startswith(external_prefixes):
                continue

            # Skip regex patterns (contain special chars)
            if any(c in link_path for c in ["[", "]", "(", ")", "*", "+", "?", "\\"]):
                continue

            # Skip template placeholders and code examples
            if link_path.startswith("../path") or "[" in link_text:
                continue
            if "{" in link_path or "}" in link_path:
                continue

            # Resolve relative path
            if link_path.startswith("/"):
                # Absolute from repo root
                target = FABRIK_ROOT / link_path.lstrip("/")
            else:
                # Handle anchor in path
                path_part = link_path.split("#")[0]
                if not path_part:
                    continue
                target = (doc.parent / path_part).resolve()

            if not target.exists():
                issues.append(
                    f"Broken link in {doc.relative_to(FABRIK_ROOT)}: [{link_text}]({link_path})"
                )
    return issues


def check_staleness() -> list[str]:
    """Check for docs that haven't been updated recently."""
    issues = []
    today = datetime.now()
    last_updated_re = re.compile(r"\*\*Last Updated:\*\*\s*(\d{4}-\d{2}-\d{2})")

    for doc_path in MANUAL_DOCS:
        full_path = FABRIK_ROOT / doc_path
        if not full_path.exists():
            continue
        content = full_path.read_text()
        match = last_updated_re.search(content)
        if not match:
            issues.append(f"Missing 'Last Updated' date: {doc_path}")
            continue
        try:
            last_date = datetime.strptime(match.group(1), "%Y-%m-%d")
            days_old = (today - last_date).days
            if days_old > STALENESS_DAYS:
                issues.append(f"Stale doc ({days_old} days old): {doc_path}")
        except ValueError:
            issues.append(f"Invalid date format in: {doc_path}")
    return issues


def validate_docs() -> tuple[bool, list[str]]:
    """Check for drift. Returns (valid, issues)."""
    issues = []

    # Check plans are indexed
    issues.extend(validate_plans_indexed())

    # Check plan status/checkbox consistency
    issues.extend(validate_plan_consistency())

    # Check for missing module docs
    missing_modules = detect_new_modules()
    for m in missing_modules:
        issues.append(f"Missing reference doc: docs/reference/{m.name}.md")

    # Check bounded blocks exist
    if README_PATH.exists():
        readme = README_PATH.read_text()
        if "<!-- AUTO-GENERATED:STRUCTURE:START -->" not in readme:
            issues.append("docs/INDEX.md missing STRUCTURE auto-block markers")

    if PLANS_INDEX.exists():
        plans_md = PLANS_INDEX.read_text()
        if "<!-- AUTO-GENERATED:PLANS:START -->" not in plans_md:
            issues.append("docs/development/PLANS.md missing PLANS auto-block markers")

    # NEW: Stub completeness check
    issues.extend(check_stub_completeness())

    # NEW: Link integrity check
    issues.extend(check_link_integrity())

    # NEW: Staleness check
    issues.extend(check_staleness())

    return len(issues) == 0, issues


def run_sync(dry_run: bool = False) -> None:
    """Create missing stubs + sync structure."""
    print("=== Documentation Sync ===\n")

    # Sync PLANS.md index
    changed, msg = sync_plans_index(dry_run=dry_run)
    print(f"Plans index: {msg}")

    # Create missing module stubs
    missing = detect_new_modules()
    for m in missing:
        if dry_run:
            print(f"Would create: docs/reference/{m.name}.md")
        else:
            if create_module_stub(m):
                print(f"Created: docs/reference/{m.name}.md")

    if not missing and not changed:
        print("\nAll documentation is up to date.")


def run_check() -> int:
    """Validate docs, fail on drift. Returns exit code."""
    print("=== Documentation Check ===\n")

    valid, issues = validate_docs()

    if valid:
        print("✓ All documentation checks passed")
        return 0
    else:
        print("✗ Documentation issues found:\n")
        for issue in issues:
            print(f"  - {issue}")
        print("\nRun 'python scripts/docs_updater.py --sync' to fix.")
        return 1


def load_prompt_from_file(file_path: str) -> str:
    """Load prompt from a markdown or text file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Task file not found: {file_path}")
    return path.read_text().strip()


def run_custom_prompt(prompt: str, files_to_check: list[str] | None = None) -> dict[str, Any]:
    """Run droid exec with a custom prompt, optionally referencing files."""
    model = get_docs_model()

    # If files are provided, prepend them to the prompt
    if files_to_check:
        files_list = "\n".join(f"- {f}" for f in files_to_check)
        prompt = f"Files to check:\n{files_list}\n\n{prompt}"

    print(f"Running custom prompt with {model}...")

    timeout_seconds = 600
    warn_after_seconds = 300
    args = [
        "droid",
        "exec",
        "--auto",
        "medium",
        "-m",
        model,
        "-o",
        "json",
        prompt,
    ]

    try:
        process = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(FABRIK_ROOT),
        )

        monitor = None
        if PROCESS_MONITOR_AVAILABLE:
            with suppress(Exception):
                monitor = ProcessMonitor(process, warn_threshold=warn_after_seconds)

        output_queue: Queue = Queue()
        stdout_thread = threading.Thread(
            target=_stream_reader, args=(process.stdout, output_queue, "stdout")
        )
        stderr_thread = threading.Thread(
            target=_stream_reader, args=(process.stderr, output_queue, "stderr")
        )
        stdout_thread.start()
        stderr_thread.start()

        stdout_lines = []
        stderr_lines = []
        start_time = time.time()
        streams_closed = 0

        while streams_closed < 2:
            if time.time() - start_time > timeout_seconds:
                process.kill()
                process.wait()
                return {"success": False, "result": f"Timeout after {timeout_seconds}s"}

            if monitor and (time.time() - start_time) % 30 < 1:
                diagnosis = monitor.analyze()
                if diagnosis["state"] in ("LIKELY_STUCK", "CONFIRMED_STUCK"):
                    print(f"⚠️ ProcessMonitor: {diagnosis['reason']}", file=sys.stderr)

            try:
                name, line = output_queue.get(timeout=1.0)
                if line is None:
                    streams_closed += 1
                elif name == "stdout":
                    stdout_lines.append(line)
                    if monitor:
                        monitor.record_activity()
                else:
                    stderr_lines.append(line)
            except Empty:
                continue

        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)
        process.wait()

        stdout = "".join(stdout_lines)
        stderr = "".join(stderr_lines)

        if process.returncode != 0:
            return {"success": False, "result": f"Exit code {process.returncode}: {stderr[:500]}"}

        try:
            output = json.loads(stdout.strip())
            return {
                "success": not output.get("is_error", False),
                "result": output.get("result", "")[:2000],
            }
        except json.JSONDecodeError:
            return {"success": True, "result": stdout[:2000]}

    except Exception as e:
        return {"success": False, "result": str(e)[:500]}


def main():
    parser = argparse.ArgumentParser(description="Fabrik Documentation Updater")
    parser.add_argument("--daemon", action="store_true", help="Run continuously")
    parser.add_argument("--file", type=str, help="Update docs for a specific file")
    parser.add_argument("--task-file", type=str, help="Load prompt from a .md or .txt file")
    parser.add_argument("--prompt", type=str, help="Run with a custom prompt")
    parser.add_argument(
        "--check-files",
        nargs="+",
        help="Files for droid to check/review (with --task-file or --prompt)",
    )
    parser.add_argument("--check", action="store_true", help="Validate docs, fail on drift")
    parser.add_argument("--sync", action="store_true", help="Create missing stubs + sync structure")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")

    args = parser.parse_args()

    if args.check:
        sys.exit(run_check())
    elif args.sync:
        run_sync(dry_run=args.dry_run)
    elif args.task_file:
        prompt = load_prompt_from_file(args.task_file)
        result = run_custom_prompt(prompt, args.check_files)
        print(result["result"])
        sys.exit(0 if result["success"] else 1)
    elif args.prompt:
        result = run_custom_prompt(args.prompt, args.check_files)
        print(result["result"])
        sys.exit(0 if result["success"] else 1)
    elif args.file:
        update_single_file(args.file)
    elif args.daemon:
        run_daemon()
    else:
        run_once()


if __name__ == "__main__":
    main()
