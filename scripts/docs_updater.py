#!/usr/bin/env python3
# AFTER-EDIT: docs/development/PLANS.md, scripts/decisions.py (keep MERGE_OWNER_RE identical)
"""
Fabrik Documentation Updater

Automatically updates documentation when code changes are detected.
Uses low-cost AI models to analyze changes and write updates directly to doc files.

This is SEPARATE from the code review workflow (kilo_code_review.py).

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
    python scripts/docs_updater.py --task-file tasks/update-docs.md \
        --check-files src/api.py src/models.py

    # Custom prompt directly
    python scripts/docs_updater.py --prompt "Update CHANGELOG for auth changes" \
        --check-files src/auth/*.py

    # Validation and sync
    python scripts/docs_updater.py --check           # Validate docs, fail on drift
    python scripts/docs_updater.py --sync            # Create missing stubs
    python scripts/docs_updater.py --sync --dry-run  # Preview changes

Workflow Doc: docs/archive/DOCUMENTATOR_WORKFLOW.md (archived — Kilo-era framing; this script is LIVE)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from queue import Empty, Queue
from typing import Any

# fcntl is POSIX-only; on non-Linux platforms, locking is skipped (no-op)
_HAS_FCNTL = False
if sys.platform.startswith("linux"):
    try:
        import fcntl

        _HAS_FCNTL = True
    except ImportError:
        fcntl = None  # type: ignore[assignment]
else:
    fcntl = None  # type: ignore[assignment]

# Import ProcessMonitor for subprocess monitoring
try:
    from process_monitor import ProcessMonitor

    PROCESS_MONITOR_AVAILABLE = True
except ImportError:
    PROCESS_MONITOR_AVAILABLE = False


def _stream_reader(stream: Any, output_queue: Queue[Any], name: str) -> None:
    """Read lines from a stream and push them to a queue (for threading)."""
    try:
        for line in iter(stream.readline, ""):
            output_queue.put((name, line))
    finally:
        with suppress(Exception):
            stream.close()
        output_queue.put((name, None))  # Signal EOF


# Configuration - operate on current project
PROJECT_ROOT = Path.cwd()
DOCS_QUEUE_DIR = Path(os.getenv("FABRIK_DOCS_QUEUE", PROJECT_ROOT / ".droid" / "docs_queue"))
DOCS_LOG_DIR = Path(os.getenv("FABRIK_DOCS_LOG", PROJECT_ROOT / ".droid" / "docs_log"))
CONFIG_FILE = Path(os.getenv("FABRIK_MODELS_CONFIG", PROJECT_ROOT / "config" / "models.yaml"))
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
            return str(docs_config["primary"])

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
    task_file: Path | None = task.get("_file")
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

Start by reading the changed files, then update CHANGELOG.md first,
then other relevant documentation."""


def run_docs_update(files: list[str]) -> dict[str, Any]:
    """Run the documentation update using Kilo CLI."""
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
            cwd=str(PROJECT_ROOT),
        )

        # Initialize ProcessMonitor if available
        monitor = None
        if PROCESS_MONITOR_AVAILABLE:
            with suppress(Exception):
                monitor = ProcessMonitor(process, warn_threshold=warn_after_seconds)

        # Use threading to read stdout/stderr without blocking
        output_queue: Queue[Any] = Queue()
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
            mark_task_status(task, status, str(result.get("result", "")))
    except Exception as e:
        # On error, mark tasks as failed for retry
        result = {"success": False, "result": str(e)[:500]}
        for task in tasks:
            mark_task_status(task, "failed", str(result["result"]))

    # Log the update
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "files": files,
        "model": get_docs_model(),
        "success": result["success"],
        "result": str(result.get("result", ""))[:1000],
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
    """Acquire exclusive lock using fcntl. Returns file descriptor or None.

    Note:
        On non-Linux platforms where fcntl is unavailable, locking is skipped
        and the function returns a valid descriptor without locking.
    """
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Use O_NOFOLLOW to atomically reject symlinks (avoids TOCTOU race)
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(str(PID_FILE), flags)
        if _HAS_FCNTL:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.write(fd, str(os.getpid()).encode())
        os.fsync(fd)
        return fd
    except OSError:
        print("Another docs updater is running, exiting")
        return None


def _release_lock(fd: int) -> None:
    """Release the lock and clean up.

    Note:
        On non-Linux platforms where fcntl is unavailable, only closes the
        file descriptor and removes the PID file.
    """
    try:
        if _HAS_FCNTL:
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

PLANS_DIR = PROJECT_ROOT / "docs" / "development" / "plans"
# Spine+ticket plan sets: a dated plan directory is one plan unit (its spine).
_PLAN_DIR_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-plan-[a-z0-9-]+$")
PLANS_INDEX = PROJECT_ROOT / "docs" / "development" / "PLANS.md"
README_PATH = PROJECT_ROOT / "INDEX.md"
TEMPLATE_PATH = PROJECT_ROOT / "templates" / "docs" / "MODULE_REFERENCE_TEMPLATE.md"

# All docs that need staleness/completeness checks
MANUAL_DOCS = [
    "README.md",
    # tasks.md is a deliberately-frozen 2026-03 superseded snapshot (see its banner) — kept as
    # history, not a living doc, so it is exempt from the freshness/staleness gate.
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
    base = PROJECT_ROOT / "src" / "fabrik"
    if not base.exists():
        return []
    # Module reference docs live in docs/reference/modules/ (docs-truth convergence
    # 2026-07-20); the flat docs/reference/<name>.md location is the legacy fallback.
    # orchestrator's doc is renamed to avoid colliding with docs/orchestrator/.
    name_map = {"orchestrator": "deployment-orchestrator"}
    mods = []
    for d in base.iterdir():
        if d.is_dir() and is_public_module(d):
            doc_name = name_map.get(d.name, d.name)
            candidates = [
                PROJECT_ROOT / "docs" / "reference" / "modules" / f"{doc_name}.md",
                PROJECT_ROOT / "docs" / "reference" / f"{d.name}.md",
            ]
            if not any(c.exists() for c in candidates):
                mods.append(d)
    return mods


_BLOCK_MACHINERY_PREFIX = "<!-- AUTO-GENERATED:"  # START/END markers + the writer's stamp line


def _block_body_norm(body: str) -> str:
    """The comparable form of a block body, applied to BOTH sides of the idempotency
    compare: only the block MACHINERY is dropped — the START/END markers and the
    `<!-- AUTO-GENERATED:<NAME> v1 | <stamp> -->` line the writer adds — so a
    timestamp alone never reads as a change. Every other line stays, comments included:
    the PLANS block's `<!-- Phase: … -->` header DEFINES its columns, and rewording it
    must read stale everywhere (dropping all `<!--` lines silently froze the old
    definition in every repo — acceptance round 1)."""
    return "\n".join(
        line for line in body.split("\n") if not line.startswith(_BLOCK_MACHINERY_PREFIX)
    ).strip()


def extract_block_body(text: str, block_re: re.Pattern[str]) -> str | None:
    """Extract current body from bounded block (excluding stamp line)."""
    match = block_re.search(text)
    if not match:
        return None
    return _block_body_norm(match.group(0))


def replace_block(
    text: str, new_body: str, block_re: re.Pattern[str], block_name: str
) -> tuple[str, bool]:
    """Replace block only if body changed; do not update stamp otherwise."""
    current_body = extract_block_body(text, block_re)
    if current_body == _block_body_norm(new_body):
        return text, False  # No change needed — idempotent

    stamp = datetime.now().strftime("%Y-%m-%dT%H:%M")

    def replacer(m: re.Match[str]) -> str:
        return (
            f"{m.group(1)}\n<!-- AUTO-GENERATED:{block_name} v1 | {stamp} -->"
            f"\n{new_body}\n{m.group(2)}"
        )

    return block_re.sub(replacer, text), True


def generate_docs_structure_tree() -> str:
    """Generate indented tree string of docs/ directory with comments."""
    docs_dir = PROJECT_ROOT / "docs"
    if not docs_dir.exists():
        return "docs/ (not found)"

    comments = {
        "FAQ.md": "Frequently asked questions",
        "INDEX.md": "Main documentation entry point",
        "TESTING.md": "How to run and write tests",
        "README.md": "Folder index / charter",
        "QUICKSTART.md": "Get Fabrik running in 5 minutes",
        "CONFIGURATION.md": "Environment variables and settings",
        "SERVICES.md": "External services Fabrik depends on",
        "TROUBLESHOOTING.md": "Common issues & solutions",
        "EXTERNAL_SYSTEMS.md": "External service dependencies",
        "FEATURES.md": "Feature list",
        "BUSINESS_MODEL.md": "Monetization strategy",
        "owner_ozgur_basak.md": "Owner profile & AI instructions",
        "reference/": "Technical reference and module documentation",
        "architecture.md": "System architecture overview",
        "health-monitoring.md": "Health monitoring patterns",
        "fabrik-cli-reference.md": "Fabrik CLI command reference",
        "drivers.md": "Fabrik driver API (DNS, Cloudflare, GPU providers, etc.)",
        "prebuilt-app-containers.md": "Prebuilt container catalog",
        "technology-stack-decision-guide.md": "Tech decision flowchart",
        "templates.md": "Available deployment templates",
        "KILO_MODEL_CAPABILITIES.md": "Kilo model capabilities",
        "windsurf/": "Windsurf IDE optimization",
        "kilo_selected_agents.md": "Kilo selected agents",
        "PLAN_OUTPUT_LOCATION.md": "Plan output location",
        "operations/": "Operational runbooks and VPS state",
        "vps-status.md": "Current VPS state and configuration",
        "vps-urls.md": "All deployed service URLs",
        "disaster-recovery.md": "Backup and recovery procedures",
        "n8n-webhooks.md": "n8n webhook configuration",
        "development/": "Active development plans and specs",
        "PLANS.md": "Development plans index",
        "plans/": "Plan documents (YYYY-MM-DD-plan-*.md)",
        "infrastructure/": "Infrastructure docs",
        "WSL2-DNS-FIX.md": "WSL2 DNS resolution fix",
        "archive/": "Archived and completed documentation",
        "workflows/": "Workflow documentation",
        "FABRIK_SCAFFOLD_WORKFLOW.md": "Fabrik scaffold workflow",
        "FINAL_GATE_WORKFLOW.md": "Final gate workflow",
        "HEALTH_CHECKER_WORKFLOW.md": "Health checker workflow",
        "KILO_AGENT_MANAGEMENT.md": "Kilo agent management",
        "SYNC_ENFORCEMENT_WORKFLOW.md": "Sync enforcement workflow",
        "SYNC_PROJECTS_WORKFLOW.md": "Sync projects workflow",
    }

    tree = ["docs/"]

    def walk(directory: Path, prefix: str = "") -> None:
        items = sorted(directory.iterdir())
        # Filter items
        items = [i for i in items if not i.name.startswith(".")]

        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "

            comment = comments.get(item.name, "")
            # If directory, check with trailing slash
            if item.is_dir() and not comment:
                comment = comments.get(f"{item.name}/", "")

            line = f"{prefix}{connector}{item.name}"
            if comment:
                line = f"{line.ljust(35)} # {comment}"

            tree.append(line)

            if item.is_dir():
                # Skip expanding archive/ and trajectories/ (too noisy)
                skip_dirs = {
                    "archive",
                    "trajectories",
                    "archived",
                    "previously-planned-fabrik-phases",
                    "issues",
                }
                if item.name not in skip_dirs:
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    walk(item, new_prefix)

    walk(docs_dir)
    tree_str = "\n".join(tree)
    return f"```text\n{tree_str}\n```"


def _strip_quoted(content: str) -> str:
    """Plan text with its QUOTED spans removed — the scan surface for header lines
    (`Status:`, `Owner:`). Fenced blocks go first (line-anchored + inline — never a
    bare ```.*?```, which swallows across an unpaired backtick), then blockquoted
    lines: a `> Status: DRAFT` grammar example above the real line must not win
    first-match (fail-open: misreported status + a defeated COMPLETE check). Same
    consumer-side strip as check_plan_tickets/check_plan_quality; the blockquote
    regex keeps `>` for cross-module byte-parity (Lesson 103)."""
    scan = re.sub(
        r"(?:^[ \t]*(`{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$|```[^`\n]+```)",
        "",
        content,
        flags=re.M | re.S,
    )
    return re.sub(r"^[ \t]*>.*$", "", scan, flags=re.M)


_OWNER_LINE_RE = re.compile(
    r"^\s*(?:[-*>]\s+)?\*{0,2}Owner\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*(.+?)(?:\n|$)",
    re.I | re.M,
)
NO_OWNER = "—"  # an untagged row — `--adopt` fills it
# The owner NAME is the line's leading token; live hub plans append prose
# (`infra (build) — spec by fleet, …`) that must not become a table cell.
_OWNER_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.@-]*")


def parse_plan_owner(plan_path: Path) -> str:
    """The plan's `**Owner:**` line (a monolith plan) or `Owner:` header (a spine) —
    same line grammar as `Status:` (bold or plain, colon mandatory, quoted spans
    ignored); first match wins, and only its leading name token is returned.
    Absent → `NO_OWNER`."""
    try:
        content = plan_path.read_text(encoding="utf-8")
    except Exception:
        return NO_OWNER
    m = _OWNER_LINE_RE.search(_strip_quoted(content))
    if not m:
        return NO_OWNER
    name = _OWNER_NAME_RE.search(m.group(1).strip().strip("*"))
    return name.group(0) if name else NO_OWNER


def parse_plan_status(plan_path: Path) -> tuple[str, int, int]:
    """Extract status and checkbox counts from a plan file.

    Returns: (status, checked_count, total_count)
    Status is normalized: COMPLETE, PARTIAL, NOT_DONE, IN_PROGRESS, or Active
    """
    try:
        content = plan_path.read_text()
    except Exception:
        return "Unknown", 0, 0

    # Extract status line — bold OR plain, colon MANDATORY and allowed inside or
    # outside the bold (`Status:`, `**Status:**`, `**Status**:`). The colon
    # requirement keeps prose bullets like `- Status page` from matching (a real
    # in-repo false positive), and the leading-* strip below never leaks a `: `.
    status = "Active"
    # Fences are quotes for the STATUS search only — checkbox counting stays on
    # RAW content (DONE-WHEN lists inside fences are live house style in this
    # repo's archived plans; uncounting them would fail-open the COMPLETE check).
    status_scan = _strip_quoted(content)
    status_match = re.search(
        r"^\s*(?:[-*>]\s+)?\*{0,2}Status\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*(.+?)(?:\n|$)",
        status_scan,
        re.I | re.M,
    )
    if status_match:
        raw_status = status_match.group(1).strip().lstrip("*:").strip()
        lower = raw_status.lower()
        first = lower.split()[0].rstrip(":*—–-") if lower.split() else ""
        # Exact-value-first (modern pipeline vocabulary, incl. BLOCKED): the status
        # VALUE is the first token. Substring fallbacks run LEGACY-first so a
        # free-text `COMPLETE — converged with baseline` stays COMPLETE (the
        # validate_plan_consistency check depends on it).
        if first in ("converged", "draft", "planned", "executed", "blocked"):
            status = first.upper()
        elif first in ("in-progress", "in_progress"):
            status = "IN_PROGRESS"
        elif "complete" in lower:
            status = "COMPLETE"
        elif "partial" in lower:
            status = "PARTIAL"
        elif "not done" in lower or "not_done" in lower:
            status = "NOT_DONE"
        elif "in progress" in lower or "in_progress" in lower or "in-progress" in lower:
            status = "IN_PROGRESS"
        elif "converged" in lower:
            status = "CONVERGED"
        elif "blocked" in lower:
            status = "BLOCKED"
        elif "executed" in lower:
            status = "EXECUTED"
        elif "draft" in lower:
            status = "DRAFT"
        else:
            status = raw_status[:20]  # Truncate if weird

    # Count checkboxes in DONE WHEN section (handles [x], [X], [ ])
    checked = len(re.findall(r"- \[[xX]\]", content))
    unchecked = len(re.findall(r"- \[ \]", content))
    total = checked + unchecked

    return status, checked, total


_PLANS_TABLE_HEADER = "| Epic/Plan | Owner | Status | Phase |"
_PLANS_TABLE_RULE = "|---|---|---|---|"
# The Phase column has two DEFINED sources, stated in the block itself so the column is
# never ambiguous (multi-agent-per-repo spec § Ownership surfaces names the header only).
_PLANS_PHASE_NOTE = (
    "<!-- Phase: epic rows = the epic's position in scripts/epic_order.py phased_order() "
    "(1 = no upstream dependency; `cycle` = dependency cycle, see `epic_order.py --check`); "
    "plan rows = Board progress, checked/total task boxes (`-` = no boxes). "
    "Owner: the leading name token of a plan's **Owner:** line / a spine's Owner: header, "
    "or an epic's frontmatter `owner`; `—` = untagged (`--adopt` fills it). "
    "Regenerate: python scripts/docs_updater.py --sync -->"
)
_EPIC_STATUS = {"0": "TODO", "1": "IN_PROGRESS", "2": "DONE"}  # EPIC-ARTIFACT-SCHEMA.md `status`

# D1 (multi-agent-per-repo spec): the merge owner is ONE ledger row per repo — grammar
# shared verbatim with scripts/decisions.py's `--merge-owner` (T01; no import — see the
# Interfaces seam: both tests share one fixture ledger and must agree on the same name).
MERGE_OWNER_RE = re.compile(r"^\**\s*MERGE OWNER:\s*([A-Za-z0-9][A-Za-z0-9_.@-]*)", re.I)
_DECISION_ROW_ID_RE = re.compile(r"^\|\s*D-\d+\s*\|", re.I)
# --adopt's own name grammar — IDENTICAL to epic_order.py's `_OWNER_NAME_RE`
# (`^[a-z0-9-]{1,32}$`, epic_order.py:748), not merely "the same class": a name
# epic_order.py's own `--assign` would refuse (uppercase, `_`, `.`, `@`, or >32 chars)
# must never get as far as markers + owner lines + the IMMUTABLE merge-owner ledger
# row here, only to have the epic half fail afterward — a half-adopted repo. This is
# ALSO narrower than MERGE_OWNER_RE's capture group (which stays permissive so it can
# still READ a name minted before this tightening), so it never needs to round-trip
# the other way.
_ADOPT_NAME_RE = re.compile(r"^[a-z0-9-]{1,32}$")

# T02b — STRATEGIC_BACKLOG.md row tagging (step (c') of --adopt). A "tag" is
# recognized ONLY at the row's own tag POSITION — the text right after a bullet's
# marker/checkbox/leading `**`, or a table row's tag/Item cell start — NEVER by
# searching the whole line (acceptance review r2, DEFECT-1: the round-1 widen's
# `.search(line)` read ANY prose bracket as a tag; measured fleet-wide over 25
# backlogs/1618 rows, 54 of 58 newly-"tagged" rows were false positives —
# `[key: string]`, `[tool.ruff]`, `[0-9A-F]`, `[the review]`,
# `[prometheus-app-metrics-setup.md](y.md)` — across 15 repos). The grammar: a
# beat-shaped head `[a-z0-9-]{1,32}` either closes immediately, or is followed by
# a compound tail — `/`, `+` or `→` then ANY text up to the next `]` — covering
# the fleet's real compound owner tags `[infra/T16 decision]`, `[infra/docs]`,
# `[fleet+infra]`, `[intel→fabrik-lib]` (docs/STRATEGIC_BACKLOG.md:55/56/60/908).
# Excluded at the head: checkbox syntax (`[x]`/`[ ]`/`[X]` — the r1 pipeline
# error), an uppercase-led head (`[WIP]`), and a bare `YYYY-MM-DD` date (a
# changelog stamp, never a tag). A `.`-led tail (a markdown link's `.md` — the
# probe that caught DEFECT-1) is deliberately NOT a valid separator: only
# `/`, `+`, `→` open the free-text tail.
_BACKLOG_TAG_AT_POS_RE = re.compile(
    r"^\[(?!x\])(?!\s)(?!\d{4}-\d{2}-\d{2}\])[a-z0-9-]{1,32}(?:[/+→][^\]\n]{0,60})?\]"
)
# `- `, `* `, `- [ ] `, `- [x] ` — group(1) is the marker (+ optional checkbox) to
# leave untouched, group(2) is the row's own content, where the tag is inserted.
_BACKLOG_BULLET_RE = re.compile(r"^(\s*[-*]\s+(?:\[[ xX]\]\s+)?)(.*)$")
# A GFM separator row: every non-blank char is `-`, `:`, or `|` (Tag column, header
# rows, and this row itself are all distinguished from ordinary data rows elsewhere).
_BACKLOG_SEPARATOR_RE = re.compile(r"^\|?[\s:|-]*-[\s:|-]*\|?$")
_BACKLOG_TAG_HEADER = "Tag"
# D5: the hub's own "Now" table names its owner cell `Owner`, never `Tag` (its
# header row starts `| Effort | Owner | Item | Why Priority | ...` — grep
# `^| Effort \| Owner \| Item` in docs/STRATEGIC_BACKLOG.md, a line number will
# drift; `Tag` lives only in the legend table two sections above it) — so the
# tag-cell lookup matches EITHER name, case-insensitively.
_BACKLOG_TAG_HEADER_NAMES = {"tag", "owner"}
_BACKLOG_ITEM_HEADER = "Item"


def _backlog_tag_header_index(names: list[str]) -> int | None:
    """Index of the header cell that holds the row's owner tag — named `Tag` or
    `Owner`, case-insensitively (D5) — or `None` when the table has neither (the
    project-shaped `| Effort | Item | Why | Ready when |` header). Shared by
    `classify_backlog_row` and `_tag_backlog_rows` so the two never disagree on
    which cell a `table-tag` row's tag lives in."""
    for i, cell in enumerate(names):
        if cell.strip().lower() in _BACKLOG_TAG_HEADER_NAMES:
            return i
    return None


def _backlog_starts_with_tag(text: str) -> bool:
    """True when `text` (a bullet's own content, or a table-item row's Item
    cell) already opens with a tag AT ITS OWN START — never searched anywhere
    else in the text (DEFECT-1: a prose bracket later in the same row, e.g.
    `[key: string]`, must never read as "already tagged"). Strips one leading
    `**` bold marker first, since the fleet's real bullets wrap the tag alone
    (`**[infra]**`) or open a longer bold span AT the tag (`**[infra] Title**`)."""
    probe = text.lstrip()
    if probe.startswith("**"):
        probe = probe[2:]
    return _BACKLOG_TAG_AT_POS_RE.match(probe) is not None


def _backlog_row_cells(line: str) -> list[str]:
    """Split one `|`-delimited table row into trimmed cell texts (leading/trailing
    pipe optional). Naive pipe-position split — matches this module's existing table
    readers (`read_merge_owner`), which already assume unescaped pipes."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def classify_backlog_row(line: str, header_cells: list[str] | None) -> str:
    """Classify one STRATEGIC_BACKLOG.md candidate row for `--adopt`'s tagging step
    (T02b, consumed by T03's `--check` advisory per the spine's Interfaces). Returns
    `"table-tag"` (a table row under a header carrying a `Tag`-or-`Owner` cell —
    case-insensitive, D5 — tag goes in that cell), `"table-item"` (a table row under
    a header WITHOUT one, tag prefixes the SECOND cell), `"bullet"` (a `-`/`*` row,
    checkbox optional, tag inserted after marker+checkbox), or `"skip"` (already
    tagged AT ITS OWN POSITION — never anywhere else in the row, r2 DEFECT-1 — the
    legend table — header cell 0 == `Tag`, the header/separator row itself, or a
    struck-through Item). `header_cells` is the enclosing table's already-split
    header — supplied by the CALLER, which alone tracks fences and table
    boundaries; this function never infers table state from `line` alone, so it
    stays a pure per-line classifier callable directly in tests without
    reconstructing a scan."""
    if header_cells is not None:
        if not line.strip().startswith("|"):
            return "skip"
        if _BACKLOG_SEPARATOR_RE.match(line.strip()):
            return "skip"
        names = [c.strip() for c in header_cells]
        cells = _backlog_row_cells(line)
        if cells == names:
            return "skip"  # the header row itself, re-offered to the classifier
        if names and names[0] == _BACKLOG_TAG_HEADER:
            return "skip"  # the legend table (`| Tag | Agent | Beat |`) — never tagged
        item_idx = names.index(_BACKLOG_ITEM_HEADER) if _BACKLOG_ITEM_HEADER in names else 1
        if item_idx < len(cells) and cells[item_idx].strip().startswith("~~"):
            return "skip"  # resolved/struck-through row
        tag_idx = _backlog_tag_header_index(names)
        if tag_idx is not None:
            if tag_idx < len(cells) and cells[tag_idx].strip() == "":
                return "table-tag"
            return "skip"  # occupied by non-tag content — never overwrite
        if len(cells) > 1 and _backlog_starts_with_tag(cells[1]):
            return "skip"  # the Item cell already opens with a tag (idempotent re-run)
        return "table-item"

    m = _BACKLOG_BULLET_RE.match(line)
    if not m:
        return "skip"
    content = m.group(2)
    if content.strip().startswith("~~"):
        return "skip"
    if _backlog_starts_with_tag(content):
        return "skip"
    return "bullet"


def _backlog_cell_span(line: str, cell_index: int) -> tuple[int, int] | None:
    """(start, end) offsets of the `cell_index`-th cell's raw text (whitespace
    included, delimiting pipes excluded) — position-based, so a mutation can insert
    into just that cell without reflowing any other part of the row. `None` when the
    row has too few pipes for that index (never raises — a caller sees no span and
    leaves the row untouched rather than guessing)."""
    positions = [i for i, ch in enumerate(line) if ch == "|"]
    if len(positions) < cell_index + 2:
        return None
    return positions[cell_index] + 1, positions[cell_index + 1]


def _tag_backlog_rows(text: str, names: list[str]) -> tuple[str, list[tuple[str, str, str]]]:
    """Tag every untagged STRATEGIC_BACKLOG.md row in `text`, round-robin over `names`
    in file order (one shared counter across all three shapes — table-tag, table-item,
    bullet), inserting only the tag text (never reordering or reflowing a row). Fenced
    blocks are passed through verbatim; a fence never leaves an outer table's header
    context (this file never nests a table inside a fence). Returns `(new_text,
    report_entries)`; a byte-identical run for the same names yields an empty report."""
    lines = text.split("\n")
    header_cells: list[str] | None = None
    in_fence = False
    report: list[tuple[str, str, str]] = []
    idx = 0
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            header_cells = None
            out.append(line)
            i += 1
            continue

        if in_fence:
            out.append(line)
            i += 1
            continue

        if not stripped.startswith("|"):
            header_cells = None
            # fall through to the bullet path below (header_cells is now None)
        elif i + 1 < n and _BACKLOG_SEPARATOR_RE.match(lines[i + 1].strip()):
            # a NEW header immediately followed by its separator — never tagged.
            header_cells = _backlog_row_cells(line)
            out.append(line)
            i += 1
            continue
        elif header_cells is not None and _BACKLOG_SEPARATOR_RE.match(stripped):
            out.append(line)  # the separator row belonging to the header just set
            i += 1
            continue

        shape = classify_backlog_row(line, header_cells)
        if shape == "table-tag":
            names_row = [c.strip() for c in header_cells or []]
            tag_idx = _backlog_tag_header_index(names_row)
            assert tag_idx is not None  # classify_backlog_row already confirmed a Tag/Owner header
            span = _backlog_cell_span(line, tag_idx)
            if span is None:
                out.append(line)
                i += 1
                continue
            start, end = span
            name = names[idx % len(names)]
            new_line = line[:start] + f" `[{name}]` " + line[end:]
            out.append(new_line)
            report.append((line.strip()[:60], name, "backlog-row"))
            idx += 1
        elif shape == "table-item":
            span = _backlog_cell_span(line, 1)
            if span is None:
                out.append(line)
                i += 1
                continue
            start, end = span
            raw = line[start:end]
            lead = len(raw) - len(raw.lstrip())
            name = names[idx % len(names)]
            new_line = line[:start] + raw[:lead] + f"[{name}] " + raw[lead:] + line[end:]
            out.append(new_line)
            report.append((line.strip()[:60], name, "backlog-row"))
            idx += 1
        elif shape == "bullet":
            m = _BACKLOG_BULLET_RE.match(line)
            assert m is not None  # classify_backlog_row already confirmed the match
            name = names[idx % len(names)]
            new_line = m.group(1) + f"[{name}] " + m.group(2)
            out.append(new_line)
            report.append((line.strip()[:60], name, "backlog-row"))
            idx += 1
        else:
            out.append(line)

        i += 1

    return "\n".join(out), report


def read_merge_owner() -> tuple[str, str] | None:
    """The `(name, "D-NNN")` declared by the LAST row of `docs/DECISIONS.md` whose `what`
    cell (cells[3] — decisions.py:82's own `|`-split) matches MERGE_OWNER_RE. A LATER row
    always wins: a changed merge owner is a NEW row that supersedes, never an edit of this
    one (the ledger's own law). `None` when the ledger is missing/unreadable or no row
    matches — the repo hasn't adopted yet."""
    ledger = PROJECT_ROOT / "docs" / "DECISIONS.md"
    try:
        text = ledger.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    found: tuple[str, str] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not _DECISION_ROW_ID_RE.match(stripped):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 4:
            continue
        m = MERGE_OWNER_RE.match(cells[3])
        if m:
            found = (m.group(1), cells[0].upper())
    return found


def _merge_owner_header_line() -> str:
    """The PLANS block's second header line (right after `_PLANS_PHASE_NOTE`, in every
    branch `generate_plans_table()` returns): who the ledger names as merge owner, or the
    command that would declare one."""
    owner = read_merge_owner()
    if owner is None:
        return (
            "<!-- Merge owner: UNDECLARED — run: python scripts/docs_updater.py --adopt <name> -->"
        )
    name, decision_id = owner
    return f"<!-- Merge owner: {name} | source: {decision_id} -->"


def _epics_dir() -> Path:
    """`docs/development/epics/`, resolved as PLANS_DIR's sibling so a test that
    monkeypatches PLANS_DIR into a scratch tree never reads the real epics."""
    return PLANS_DIR.parent / "epics"


# A pipe is LIVE when preceded by an EVEN number of backslashes (zero included) — markdown
# escaping is by parity: in `a\\|b` the `\\` is an escaped backslash and the pipe delimits.
_UNESCAPED_PIPE_RE = re.compile(r"(?<!\\)((?:\\\\)*)\|")


def _cell(value: str) -> str:
    """A table cell: a LIVE `|` is escaped so a value can never split the row (an epic
    `owner: "a | b"` or a `Status:` carrying a pipe made 5 cells of 4). Parity-correct
    and idempotent on every shape: `a|b` → `a\\|b`; `a\\|b` unchanged (already
    escaped — escaping again would yield a literal backslash before a live delimiter);
    `a\\\\|b` → `a\\\\\\|b`; `a\\\\\\|b` unchanged (rounds 2–3)."""
    return _UNESCAPED_PIPE_RE.sub(r"\1\\|", value)


def _epic_placeholder(epics_dir: Path, reason: str) -> list[str]:
    """ONE visible placeholder row when the epics cannot be listed — never a crash,
    never silence (this script is fleet-synced; the parser is not)."""
    n = len(list(epics_dir.glob("*.md")))
    return [f"| ({n} epic file(s) not listed — {_cell(reason)}) | - | - | - |"]


def _epic_rows() -> list[str]:
    """One table row per epic file under docs/development/epics/, read through
    scripts/epic_order.py (the frontmatter parser + the phased order are ITS truth,
    never a second parser here). An epic without frontmatter or `epic_n` renders
    `-` for Phase; a dependency cycle renders `cycle` on every epic row."""
    epics_dir = _epics_dir()
    if not epics_dir.is_dir():
        return []
    try:
        from epic_order import load_epics, phased_order
    except ImportError:  # imported as scripts.docs_updater (tests) — scripts/ not on sys.path
        try:
            from scripts.epic_order import load_epics, phased_order  # type: ignore[no-redef]
        except ImportError:
            # scripts/epic_order.py is hub-only; a project with an epics dir must still --sync.
            return _epic_placeholder(
                epics_dir, "scripts/epic_order.py is not available in this repo"
            )

    try:
        epics = load_epics(str(epics_dir))
    except (UnicodeDecodeError, OSError) as exc:
        # load_epics opens every *.md as UTF-8 with no guard; one undecodable or unreadable
        # file must not abort --check/--sync for the whole repo.
        return _epic_placeholder(
            epics_dir, f"one is not decodable/readable — {type(exc).__name__}: {exc}"
        )
    phase_of: dict[int, str] = {}
    try:
        for i, phase in enumerate(phased_order(epics), 1):
            for n in phase:
                phase_of[n] = str(i)
    except ValueError:  # a dependency cycle — epic_order.py --check names it
        phase_of = {}
        cycle = True
    else:
        cycle = False

    rows: list[str] = []
    for e in epics:
        name = Path(e["_path"]).name
        rel = f"epics/{name}"
        if e.get("_no_frontmatter"):
            rows.append(f"| [{name}]({rel}) | {NO_OWNER} | - | - |")
            continue
        owner = str(e.get("owner") or "").strip() or NO_OWNER
        status = _EPIC_STATUS.get(str(e.get("status", "")).strip(), str(e.get("status", "-")))
        n = e.get("epic_n")
        phase = "cycle" if cycle else phase_of.get(n, "-") if n is not None else "-"
        rows.append(f"| [{name}]({rel}) | {_cell(owner)} | {_cell(status)} | {_cell(phase)} |")
    return rows


def _plan_units() -> list[tuple[str, str, Path]]:
    """Every plan unit under PLANS_DIR — monolith files + spine+ticket plan SETS
    (represented by their same-stem spine; ticket files are never listed), sorted by
    display name. Directories are filtered to the dated prefix — `archived/` (or any
    non-dated dir) is never a plan unit. Single source shared by `generate_plans_table()`
    and `run_adopt()` so both see the identical unit list."""
    if not PLANS_DIR.exists():
        return []
    plans = [(p.name, f"plans/{p.name}", p) for p in sorted(PLANS_DIR.glob("*.md"))]
    plans += [
        (f"{d.name}.md", f"plans/{d.name}/{d.name}.md", d / f"{d.name}.md")
        for d in sorted(PLANS_DIR.iterdir())
        if d.is_dir() and _PLAN_DIR_NAME_RE.match(d.name) and (d / f"{d.name}.md").is_file()
    ]
    return sorted(plans)


def generate_plans_table() -> str:
    """The `AUTO-GENERATED:PLANS` block body for docs/development/PLANS.md: every
    epic (docs/development/epics/) and every plan unit (docs/development/plans/ —
    monolith files + spine+ticket plan SETS, represented by their same-stem spine;
    ticket files are never listed) with Owner, Status and Phase. Consumed by
    `sync_plans_index` (--sync) and `validate_plans_indexed` (--check)."""
    empty = (
        f"{_PLANS_PHASE_NOTE}\n{_merge_owner_header_line()}\n{_PLANS_TABLE_HEADER}\n"
        f"{_PLANS_TABLE_RULE}\n| (none) | - | - | - |"
    )
    rows = _epic_rows()
    for name, rel, p in _plan_units():
        status, checked, total = parse_plan_status(p)
        phase = f"{checked}/{total}" if total > 0 else "-"
        rows.append(
            f"| [{name}]({rel}) | {_cell(parse_plan_owner(p))} | {_cell(status)} | {phase} |"
        )
    if not rows:
        return empty
    return "\n".join(
        [
            _PLANS_PHASE_NOTE,
            _merge_owner_header_line(),
            _PLANS_TABLE_HEADER,
            _PLANS_TABLE_RULE,
            *rows,
        ]
    )


def sync_plans_index(dry_run: bool = False) -> tuple[bool, str]:
    """Regenerate the `AUTO-GENERATED:PLANS` block in docs/development/PLANS.md in
    place — the same Tier-0 mechanism as INDEX.md's STRUCTURE block (`replace_block`,
    idempotent, stamp bumped only on a real change). Opt-in by the markers: a repo
    without PLANS.md, or without the block, is left alone (this script is fleet-synced).
    Returns (changed, message)."""
    if not PLANS_INDEX.exists():
        return False, "docs/development/PLANS.md not present — skipped"
    content = PLANS_INDEX.read_text(encoding="utf-8")
    if not PLANS_BLOCK_RE.search(content):
        return False, "docs/development/PLANS.md has no AUTO-GENERATED:PLANS markers — skipped"
    new_content, changed = replace_block(content, generate_plans_table(), PLANS_BLOCK_RE, "PLANS")
    if not changed:
        return False, "docs/development/PLANS.md (PLANS block) up to date"
    if dry_run:
        return True, "Would update: docs/development/PLANS.md (PLANS block)"
    PLANS_INDEX.write_text(new_content, encoding="utf-8")
    return True, "Updated: docs/development/PLANS.md (PLANS block)"


def validate_plans_indexed() -> list[str]:
    """--check: a finding when the PLANS block no longer matches what
    `generate_plans_table()` would emit (never mutates). Missing file or missing
    markers = opted out, not a finding — the mirror of `sync_plans_index`."""
    if not PLANS_INDEX.exists():
        return []
    current = extract_block_body(PLANS_INDEX.read_text(encoding="utf-8"), PLANS_BLOCK_RE)
    if current is None:
        return []
    if current != _block_body_norm(generate_plans_table()):
        return [
            "docs/development/PLANS.md AUTO-GENERATED:PLANS block is stale — "
            "run: python scripts/docs_updater.py --sync"
        ]
    return []


def validate_plan_consistency() -> list[str]:
    """Check plan status matches checkbox completion. For --check mode.

    ERROR: Plan marked COMPLETE but has unchecked boxes
    WARNING: Plan marked COMPLETE for >14 days (should archive)
    """
    errors: list[str] = []
    if not PLANS_DIR.exists():
        return errors

    from datetime import timedelta

    targets = list(PLANS_DIR.glob("*.md")) + [
        d / f"{d.name}.md"
        for d in PLANS_DIR.iterdir()
        if d.is_dir() and _PLAN_DIR_NAME_RE.match(d.name) and (d / f"{d.name}.md").is_file()
    ]
    for p in targets:
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
                        f"WARNING: {p.name} is COMPLETE and {age.days} days old"
                        " - consider archiving"
                    )
            except ValueError:
                pass  # Invalid date format, skip age check

    return errors


def create_module_stub(module: Path) -> bool:
    """Create reference doc stub for a module. Returns True if created."""
    out = PROJECT_ROOT / "docs" / "reference" / f"{module.name}.md"
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
from {PROJECT_ROOT.name}.{module.name} import ...
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
    issues: list[str] = []
    ref_dir = PROJECT_ROOT / "docs" / "reference"
    if not ref_dir.exists():
        return issues

    for doc in ref_dir.glob("*.md"):
        content = doc.read_text()
        for marker in STUB_MARKERS:
            if marker in content:
                issues.append(
                    f"Incomplete stub: {doc.relative_to(PROJECT_ROOT)}"
                    f" (contains '{marker[:20]}...')"
                )
                break
    return issues


def _gitignored(paths: list[Path]) -> set[Path]:
    """The subset of *paths* that git ignores, via ONE batched `git check-ignore` call.

    Why the link walk needs this: `docs/reference/kilo/`, `docs/reference/MD/` and friends are
    FABRIK-SYNCED (see `fabrik_synced_manifest.py`) and gitignored in every consuming project. Their
    links point at the tree that OWNS them — `scripts/kilo-benchmarks/*`, `docs/workflows/*` — which
    exists on the hub and in no project. So the checker was validating centrally-managed content
    against the wrong repo and reporting broken links no project could fix, blocking
    `/fabrik-release` (whose preconditions require this check green) on work that was ready.

    Gitignore-awareness rather than a hardcoded directory list: it covers every synced surface at
    once and stays correct as the manifest grows. On the HUB these files are TRACKED, so they keep
    being checked there — which is where a genuinely broken link in them can actually be fixed.

    Batched deliberately: a per-file shell-out is one subprocess per doc (80+ in a typical project).
    On ANY git failure this returns an empty set, i.e. check everything — a visible false positive
    beats silently skipping a doc the project really owns.
    """
    if not paths:
        return set()
    try:
        # `-z`: NUL-separated in and out, so paths with spaces/newlines survive intact.
        # Exit 1 means "nothing matched" and is NOT an error; 128 is.
        proc = subprocess.run(
            ["git", "check-ignore", "-z", "--stdin"],
            input="\0".join(str(p) for p in paths),
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    if proc.returncode not in (0, 1):
        return set()
    return {PROJECT_ROOT / n for n in proc.stdout.split("\0") if n}


def check_link_integrity() -> list[str]:
    """Check all internal markdown links are valid."""
    issues: list[str] = []
    docs_dir = PROJECT_ROOT / "docs"
    if not docs_dir.exists():
        return issues

    # Match markdown links but not code blocks or regex patterns
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    # Skip these path prefixes (external Factory docs, not our files)
    external_prefixes = ("/cli/", "/guides/", "/web/", "/reference/")

    # Skip files that are copies of external docs
    skip_files = (
        "markdown-cheatsheet.md",  # a Markdown syntax reference — its links are illustrative examples
        "droid-exec-headless.md",
        "building-interactive-apps-with-droid-exec.md",
        "n8n-webhooks.md",
        "factoryai-power-user-settings.md",
        "factory-skills.md",
        "factory-enterprise.md",
    )

    all_docs = sorted(docs_dir.rglob("*.md"))
    # Fabrik-synced governance/reference copies are gitignored in consuming projects and their
    # links resolve only in the repo that owns them — same rationale as the cross-repo skip below.
    ignored = _gitignored(all_docs)

    for doc in all_docs:
        # Skip known external doc copies
        if doc.name in skip_files:
            continue

        # Skip archived docs and design archives
        if "/archive" in str(doc) or "/.archive" in str(doc):
            continue

        # Skip centrally-managed synced copies (gitignored here, owned elsewhere)
        if doc in ignored:
            continue

        content = doc.read_text()
        for match in link_pattern.finditer(content):
            link_text, link_path = match.groups()

            # Skip external links, anchors, mailto, and file:// URIs (usually cross-repo)
            if link_path.startswith(("http://", "https://", "#", "mailto:", "file://")):
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
            # Skip template-date placeholders (e.g. infra-probe-YYYY-MM-DDTHH-MMZ.yaml)
            if "YYYY" in link_path or "HH-MM" in link_path:
                continue

            # Resolve relative path (URL-decode %20 etc — files with spaces are legitimately encoded)
            if link_path.startswith("/"):
                # A real absolute FS path OUTSIDE this repo (e.g. /opt/fabrik-lib/...) is a
                # cross-repo reference, not a repo-root-relative link — not ours to validate.
                literal = Path(urllib.parse.unquote(link_path.split("#")[0]))
                if literal.is_absolute() and literal.exists():
                    try:
                        literal.relative_to(PROJECT_ROOT)
                    except ValueError:
                        continue
                # Absolute from repo root
                target = PROJECT_ROOT / urllib.parse.unquote(link_path.lstrip("/"))
            else:
                # Handle anchor in path
                path_part = urllib.parse.unquote(link_path.split("#")[0])
                if not path_part:
                    continue
                target = (doc.parent / path_part).resolve()

            # Skip cross-repo / external references (resolve OUTSIDE this repo) — a link into
            # /opt/fabrik-lib or another repo is not this checker's to validate.
            try:
                target.relative_to(PROJECT_ROOT)
            except ValueError:
                continue

            if not target.exists():
                issues.append(
                    f"Broken link in {doc.relative_to(PROJECT_ROOT)}: [{link_text}]({link_path})"
                )
    return issues


def check_staleness() -> list[str]:
    """Check for docs that haven't been updated recently."""
    issues: list[str] = []
    today = datetime.now()
    last_updated_re = re.compile(r"\*\*Last Updated:\*\*\s*(\d{4}-\d{2}-\d{2})")

    for doc_path in MANUAL_DOCS:
        full_path = PROJECT_ROOT / doc_path
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
    issues: list[str] = []

    # Check plan status/checkbox consistency + the PLANS.md block's freshness
    issues.extend(validate_plan_consistency())
    issues.extend(validate_plans_indexed())

    # Check for missing module docs
    missing_modules = detect_new_modules()
    for m in missing_modules:
        issues.append(f"Missing reference doc: docs/reference/{m.name}.md")

    # Check bounded blocks exist
    if README_PATH.exists():
        readme = README_PATH.read_text()
        if "<!-- AUTO-GENERATED:STRUCTURE:START -->" not in readme:
            issues.append("INDEX.md missing STRUCTURE auto-block markers")

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

    # Sync STRUCTURE block in INDEX.md
    if README_PATH.exists():
        content = README_PATH.read_text()
        new_tree = generate_docs_structure_tree()
        new_content, changed = replace_block(content, new_tree, STRUCTURE_BLOCK_RE, "STRUCTURE")

        if changed:
            if dry_run:
                print("Would update: docs/INDEX.md (STRUCTURE block)")
            else:
                README_PATH.write_text(new_content)
                print("Updated: docs/INDEX.md (STRUCTURE block)")

    # Sync the PLANS block in docs/development/PLANS.md (opt-in by its markers)
    plans_changed, plans_msg = sync_plans_index(dry_run=dry_run)
    if plans_changed:
        print(plans_msg)

    # Create missing module stubs
    missing = detect_new_modules()
    for m in missing:
        if dry_run:
            print(f"Would create: docs/reference/{m.name}.md")
        else:
            if create_module_stub(m):
                print(f"Created: docs/reference/{m.name}.md")

    if not missing:
        print("\nAll documentation is up to date.")


def count_sessions_sharing(cwd: Path, proc_root: Path = Path("/proc")) -> int:
    """Number of processes under `proc_root` whose `comm` is `claude` and whose `cwd`
    symlink resolves to the same real path as `cwd`. stdlib only, never reads
    `environ`; an unreadable or vanished entry is skipped, and this function never
    raises — `proc_root` exists so a test can point it at a fake tree and exercise the
    real scan instead of overriding the count."""
    target = os.path.realpath(str(cwd))
    count = 0
    try:
        entries = os.listdir(proc_root)
    except OSError:
        return 0
    for entry in entries:
        if not entry.isdigit():
            continue
        pid_dir = Path(proc_root) / entry
        try:
            comm = (pid_dir / "comm").read_text(encoding="utf-8", errors="ignore").strip()
            if comm != "claude":
                continue
            link_target = os.readlink(pid_dir / "cwd")
            if os.path.realpath(link_target) == target:
                count += 1
        except OSError:
            continue
    return count


def _insert_owner_line(path: Path, name: str) -> bool:
    """Insert `**Owner:** <name>` as the first line after the plan's H1 — after the
    blank line that follows the H1, if one does — never inside a fenced code block,
    and never inside a leading YAML frontmatter block (a `# comment` line there must
    never be mistaken for the document's H1). No-op (returns False, no write) when the
    file has no H1 at all."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    lines = text.split("\n")
    start = 0
    if lines and lines[0].strip() == "---":
        # Leading frontmatter fence: skip to its close so nothing inside — including a
        # bare `# ...` comment line — is ever read as the document's H1.
        start = len(lines)
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                start = j + 1
                break
    h1_idx: int | None = None
    in_fence = False
    for i in range(start, len(lines)):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.startswith("# "):
            h1_idx = i
            break
    if h1_idx is None:
        return False
    insert_at = h1_idx + 1
    if insert_at < len(lines) and lines[insert_at].strip() == "":
        insert_at += 1
    lines.insert(insert_at, f"**Owner:** {name}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return True


def _mint_next_decision_id() -> str:
    """max existing `D-NNN` id + 1 in `docs/DECISIONS.md`, `D-001` when none/absent —
    the same `^\\|\\s*D-(\\d+)\\s*\\|` scan `decisions.py:162`'s `_next_id` uses,
    reimplemented locally (T02a does not import `scripts/decisions.py` — see the
    Interfaces seam; `# AFTER-EDIT` binds the two regexes to stay identical)."""
    ledger = PROJECT_ROOT / "docs" / "DECISIONS.md"
    try:
        text = ledger.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    ids = [int(m) for m in re.findall(r"^\|\s*D-(\d+)\s*\|", text, re.M)]
    return f"D-{(max(ids) + 1) if ids else 1:03d}"


def run_adopt(names: list[str], single_window: bool, proc_root: Path = Path("/proc")) -> int:
    """`--adopt <name>[,<name>…]`: seed the PLANS ownership markers, stamp every open
    unowned plan unit's Owner (round-robin), declare the merge owner (the first name)
    when the ledger has none, tag every untagged docs/STRATEGIC_BACKLOG.md row
    round-robin in its own shape (T02b — `classify_backlog_row`/`_tag_backlog_rows`;
    silently nothing when the file is absent), delegate the epic half to
    `epic_order.py --assign` WHEN that script is present (it is hub-only, never
    synced to projects — a repo with an epics dir but no vendored copy is skipped
    here; the hub adopts those epics separately, from /opt/fabrik, with `python3
    /opt/fabrik/scripts/epic_order.py --assign <names>`), then regenerate the PLANS
    block. Refuses (exit 2, one stderr line) on any name failing `_ADOPT_NAME_RE`, or
    on a checkout only this session shares unless `single_window` overrides it.
    Returns 3 only when a PRESENT epic_order.py genuinely refused the assignment
    (rc≠0) — never for an absent script. Idempotent: a re-run with the same names
    touches no byte and prints `(nothing to adopt)`."""
    bad = [n for n in names if not _ADOPT_NAME_RE.fullmatch(n)]
    if bad:
        sys.stderr.write(
            f"docs_updater --adopt: invalid agent name(s) {bad!r} — must match "
            f"{_ADOPT_NAME_RE.pattern!r}\n"
        )
        return 2

    if not single_window:
        n = count_sessions_sharing(PROJECT_ROOT, proc_root)
        if n < 2:
            sys.stderr.write(
                f"docs_updater --adopt: refused — only {n} Claude session(s) share this "
                "checkout (need ≥2, or pass --single-window)\n"
            )
            return 2

    report: list[tuple[str, str, str]] = []

    # (a) seed the AUTO-GENERATED:PLANS markers when PLANS.md is absent or marker-less
    # — left below any existing hand table, which stays as history.
    ownership_block = (
        "\n## Ownership (auto-generated)\n\n"
        "<!-- AUTO-GENERATED:PLANS:START -->\n<!-- AUTO-GENERATED:PLANS:END -->\n"
    )
    if PLANS_INDEX.exists():
        content = PLANS_INDEX.read_text(encoding="utf-8")
        if not PLANS_BLOCK_RE.search(content):
            PLANS_INDEX.write_text(content + ownership_block, encoding="utf-8")
            report.append(("docs/development/PLANS.md", NO_OWNER, "markers"))
    else:
        PLANS_INDEX.parent.mkdir(parents=True, exist_ok=True)
        PLANS_INDEX.write_text(f"# Development Plans\n{ownership_block}", encoding="utf-8")
        report.append(("docs/development/PLANS.md", NO_OWNER, "markers"))

    # (b) stamp Owner on every open (non-terminal), unowned plan unit — round-robin
    # over `names`, in file-sorted order (same order `_plan_units()` lists them).
    i = 0
    for _name_file, rel, p in _plan_units():
        if parse_plan_owner(p) != NO_OWNER:
            continue
        status, _checked, _total = parse_plan_status(p)
        if status in ("EXECUTED", "COMPLETE"):
            continue
        owner_name = names[i % len(names)]
        if _insert_owner_line(p, owner_name):
            report.append((rel, owner_name, "owner-line"))
            i += 1

    # (c) declare the merge owner (first name) — ONLY when the ledger has none yet; a
    # changed merge owner is a hand-minted superseding row, never --adopt's write.
    if read_merge_owner() is None:
        first = names[0]
        did = _mint_next_decision_id()
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        cells = [
            did,
            today,
            f"{first} (--adopt)",
            f"MERGE OWNER: {first} — the only writer of the base branch; agents 2..N "
            "commit to worktree branches (multi-agent-per-repo model)",
            "declared by `docs_updater.py --adopt` at adoption; a change is a NEW row "
            "superseding this one",
            "docs/development/PLANS.md (the AUTO-GENERATED:PLANS header prints it)",
        ]
        row = "| " + " | ".join(_cell(c) for c in cells) + " |"
        ledger = PROJECT_ROOT / "docs" / "DECISIONS.md"
        if ledger.exists():
            ledger_text = ledger.read_text(encoding="utf-8")
            sep = "" if ledger_text.endswith("\n") else "\n"
            ledger.write_text(f"{ledger_text}{sep}{row}\n", encoding="utf-8")
        else:
            ledger.parent.mkdir(parents=True, exist_ok=True)
            ledger.write_text(
                "# Decisions\n\n| id | when | who | what (the decision) | why | where |\n"
                f"|---|---|---|---|---|---|\n{row}\n",
                encoding="utf-8",
            )
        report.append((f"{did} (MERGE OWNER)", first, "ledger-row"))

    # (c') tag every untagged docs/STRATEGIC_BACKLOG.md row — round-robin over
    # `names`, in the row's own shape (T02b). A missing file is silently nothing (23
    # of 41 repos have one — the ticket's own denominator).
    backlog_path = PROJECT_ROOT / "docs" / "STRATEGIC_BACKLOG.md"
    if backlog_path.is_file():
        backlog_text = backlog_path.read_text(encoding="utf-8")
        new_backlog_text, backlog_report = _tag_backlog_rows(backlog_text, names)
        if backlog_report:
            backlog_path.write_text(new_backlog_text, encoding="utf-8")
            report.extend(backlog_report)

    # (d) the epic half — delegated to epic_order.py --assign, never re-implemented here.
    # scripts/epic_order.py is HUB-ONLY (never synced to projects — same guard
    # `_epic_rows()` already applies at :1026-1028): a project with an epics dir but no
    # vendored epic_order.py must be skipped entirely, not treated as a failed
    # delegation — the hub adopts those epics separately, from here, with
    # `python3 /opt/fabrik/scripts/epic_order.py --assign <names>`. A row is emitted
    # ONLY when an epic actually gained an owner (or a PRESENT script genuinely
    # refused) — --assign is itself idempotent (a no-op write when the file already
    # reads the target way), so re-running --adopt over the same epics dir with the
    # same names must never keep reporting a change that did not happen.
    epic_order_failed = False
    epics_dir = _epics_dir()
    epic_order_script = PROJECT_ROOT / "scripts" / "epic_order.py"
    if epics_dir.is_dir() and any(epics_dir.glob("*.md")) and epic_order_script.is_file():
        epic_files = sorted(epics_dir.glob("*.md"))
        before = {p: p.read_bytes() for p in epic_files}
        result = subprocess.run(
            [sys.executable, "scripts/epic_order.py", "--assign", ",".join(names)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            epic_order_failed = True
            report.append(
                (
                    "epics (epic_order.py --assign)",
                    names[0],
                    f"epic_order (rc={result.returncode})",
                )
            )
        elif any(p.read_bytes() != before[p] for p in epic_files if p.exists()):
            report.append(("epics (epic_order.py --assign)", names[0], "epic_order"))

    # (e) regenerate the block so the new owners / merge-owner header are visible.
    sync_plans_index()

    if not report:
        print("(nothing to adopt)")
        return 3 if epic_order_failed else 0

    lines = ["| Item | Owner | Source |", "|---|---|---|"]
    for item, owner, source in report:
        lines.append(f"| {_cell(item)} | {_cell(owner)} | {_cell(source)} |")
    print("\n".join(lines))
    return 3 if epic_order_failed else 0


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
    """Run AI CLI with a custom prompt, optionally referencing files (legacy path)."""
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
            cwd=str(PROJECT_ROOT),
        )

        monitor = None
        if PROCESS_MONITOR_AVAILABLE:
            with suppress(Exception):
                monitor = ProcessMonitor(process, warn_threshold=warn_after_seconds)

        output_queue: Queue[Any] = Queue()
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


def main() -> None:
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
    parser.add_argument(
        "--adopt",
        type=str,
        metavar="NAMES",
        help=(
            "comma-separated agent name(s): seed the PLANS ownership markers, stamp "
            "every open unowned plan unit's Owner, declare the merge owner when "
            "undeclared, delegate the epic half to epic_order.py --assign, and print "
            "a table of what changed"
        ),
    )
    parser.add_argument(
        "--single-window",
        action="store_true",
        help="override --adopt's refusal on a checkout only this session shares",
    )

    args = parser.parse_args()

    if args.adopt is not None:
        names = [n.strip() for n in args.adopt.split(",") if n.strip()]
        if not names:
            parser.error("--adopt requires at least one name")
        sys.exit(run_adopt(names, args.single_window))
    elif args.check:
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
