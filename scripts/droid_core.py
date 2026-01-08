#!/usr/bin/env python3
"""
Droid Core - Unified droid exec wrapper for all task types.

Consolidates droid_tasks.py + droid_runner.py into a single module.

FEATURES
========
- 11 task types: analyze, code, refactor, test, review, spec, scaffold, deploy, migrate, health, preflight
- Task persistence and monitoring via .droid/ folder
- ProcessMonitor integration for activity tracking
- Session continuation (Pattern 2) and interactive sessions (Pattern 1)
- Batch processing from JSONL files
- Task file (.md) support

USAGE
=====

    # Single task by type
    python scripts/droid_core.py analyze "Review the authentication flow"
    python scripts/droid_core.py code "Add error handling" --auto medium
    python scripts/droid_core.py spec "Plan the new feature"

    # From file (with monitoring)
    python scripts/droid_core.py run --task tasks/my_task.md

    # Direct prompt with monitoring
    python scripts/droid_core.py run --prompt "Analyze codebase" --verbose

    # Continue previous session (Pattern 2)
    python scripts/droid_core.py code "Now add error handling" --session-id <id>

    # Interactive session (Pattern 1)
    python scripts/droid_core.py session

    # Batch tasks with shared session
    python scripts/droid_core.py batch tasks.jsonl --auto low

    # Task management
    python scripts/droid_core.py status <task-id>
    python scripts/droid_core.py list --limit 10
"""

import argparse
import contextlib
import json
import os
import select
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

# Import model registry (handle both module and script execution)
try:
    from scripts.droid_models import (
        DEFAULT_MODEL,
        TaskCategory,
        check_model_change_warning,
        recommend_model,
        refresh_models_from_docs,
    )
except ModuleNotFoundError:
    from droid_models import (
        DEFAULT_MODEL,
        TaskCategory,
        check_model_change_warning,
        recommend_model,
        refresh_models_from_docs,
    )

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

# =============================================================================
# Data Directories (from droid_runner.py)
# =============================================================================

DROID_DATA_DIR = Path(os.getenv("DROID_DATA_DIR", "/opt/fabrik/.droid"))
TASKS_DIR = DROID_DATA_DIR / "tasks"
RESPONSES_DIR = DROID_DATA_DIR / "responses"
SESSIONS_DIR = DROID_DATA_DIR / "sessions"


def ensure_dirs():
    """Ensure data exchange directories exist."""
    for d in [TASKS_DIR, RESPONSES_DIR, SESSIONS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


class Autonomy(str, Enum):
    LOW = "low"  # Safest - analysis only, no edits
    MEDIUM = "medium"  # Moderate - edits with confirmation
    HIGH = "high"  # Full autonomy - use with caution


class TaskType(str, Enum):
    # Core task types
    ANALYZE = "analyze"  # Read-only analysis
    CODE = "code"  # Coding with potential edits
    REFACTOR = "refactor"  # Refactoring existing code
    TEST = "test"  # Generate or run tests
    REVIEW = "review"  # Code review
    # Discovery task types (idea → scope → spec pipeline)
    IDEA = "idea"  # Capture and explore product idea
    SCOPE = "scope"  # Define IN/OUT boundaries from idea
    # Fabrik lifecycle task types
    SPEC = "spec"  # Specification mode - plan before implementing
    SCAFFOLD = "scaffold"  # Create new Fabrik project structure
    DEPLOY = "deploy"  # Generate/update deployment configs
    MIGRATE = "migrate"  # Database migration tasks
    HEALTH = "health"  # Verify deployment health (autonomous)
    PREFLIGHT = "preflight"  # Pre-deployment readiness check


@dataclass
class TaskResult:
    """Result from a droid exec task."""

    success: bool
    task_type: TaskType
    prompt: str
    result: str
    error: str | None = None
    duration_ms: int | None = None
    session_id: str | None = None


class TaskStatus(str, Enum):
    """Status for persistent task tracking."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    STUCK = "stuck"


@dataclass
class TaskRecord:
    """Persistent record of a droid task for tracking (from droid_runner.py)."""

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


# Task type configurations
# Safety is controlled via --auto level:
#   low    = read-only by default, edits need approval
#   medium = moderate autonomy, some auto-edits
#   high   = full autonomy (use with caution)
#
# Mixed Models: Different models can be used for planning (spec) vs implementation (code).
# Reasoning levels: off, low, medium, high (Anthropic models only)
#
# Model Compatibility Rules:
#   - OpenAI models only pair with OpenAI (encrypted reasoning traces)
#   - Anthropic with reasoning ON only pairs with Anthropic
#   - Anthropic with reasoning OFF can pair with non-OpenAI models
TOOL_CONFIGS = {
    # Core task types
    TaskType.ANALYZE: {
        "default_auto": "low",
        "model": "gemini-3-flash-preview",  # Cheap exploration
        "reasoning": "off",
        "description": "Read-only analysis, no file modifications",
    },
    TaskType.CODE: {
        "default_auto": "high",
        "model": "gpt-5.1-codex-max",  # Fast implementation
        "reasoning": "medium",
        "description": "File editing allowed",
    },
    TaskType.REFACTOR: {
        "default_auto": "high",
        "model": "gpt-5.1-codex-max",
        "reasoning": "medium",
        "description": "Edit existing files",
    },
    TaskType.TEST: {
        "default_auto": "high",
        "model": "gpt-5.1-codex-max",
        "reasoning": "low",
        "description": "Test generation and execution",
    },
    TaskType.REVIEW: {
        "default_auto": "low",
        "model": "gpt-5.1-codex-max",  # Fast, cheap reviews
        "reasoning": "off",
        "description": "Read-only code review",
    },
    # Discovery task types (idea → scope → spec pipeline)
    TaskType.IDEA: {
        "default_auto": "low",
        "model": "claude-sonnet-4-5-20250929",  # Premium for discovery
        "reasoning": "high",  # Deep exploration
        "description": "Capture and explore product idea through discovery questions",
        "output_path": "specs/{project}/00-idea.md",
    },
    TaskType.SCOPE: {
        "default_auto": "low",
        "model": "claude-sonnet-4-5-20250929",  # Premium for boundaries
        "reasoning": "high",  # Critical thinking for scope
        "description": "Define IN/OUT scope boundaries from idea",
        "output_path": "specs/{project}/01-scope.md",
    },
    # Fabrik lifecycle task types - Mixed Model Configuration
    TaskType.SPEC: {
        "default_auto": "low",
        "use_spec": True,  # Enable --use-spec flag
        "model": "claude-sonnet-4-5-20250929",  # Premium model for planning
        "reasoning": "high",  # Deep analysis prevents implementation mistakes
        "description": "Specification mode - detailed planning before implementation",
    },
    TaskType.SCAFFOLD: {
        "default_auto": "high",
        "model": "gpt-5.1-codex-max",
        "reasoning": "medium",
        "description": "Create new Fabrik project structure with all required files",
    },
    TaskType.DEPLOY: {
        "default_auto": "high",
        "model": "gemini-3-flash-preview",  # Simple config generation
        "reasoning": "low",
        "description": "Generate or update Docker Compose and Coolify configs",
    },
    TaskType.MIGRATE: {
        "default_auto": "high",
        "model": "gpt-5.1-codex-max",
        "reasoning": "medium",
        "description": "Database migration generation and execution",
    },
    TaskType.HEALTH: {
        "default_auto": "high",  # Autonomous - Verify mode
        "model": "gemini-3-flash-preview",  # Quick checks
        "reasoning": "off",
        "description": "Verify deployment health: containers, API, database",
    },
    TaskType.PREFLIGHT: {
        "default_auto": "low",  # Read-only check before deploy
        "model": "gemini-3-flash-preview",
        "reasoning": "off",
        "description": "Pre-deployment readiness check: config, Docker, health, code quality",
    },
}


class DroidSession:
    """
    Multi-turn session using Pattern 2 (session ID continuation).

    Each send() spawns a new process but maintains context via --session-id.
    This is more reliable than long-lived processes (crash recovery, scaling).

    WARNING: Changing models mid-session loses context (new session starts).

    Usage:
        with DroidSession(autonomy=Autonomy.LOW) as session:
            result1 = session.send("Analyze the codebase")
            result2 = session.send("Now refactor the auth module")  # Keeps context
    """

    def __init__(
        self,
        model: str = None,
        autonomy: Autonomy = Autonomy.LOW,
        cwd: str | None = None,
    ):
        self.model = model or DEFAULT_MODEL
        self.autonomy = autonomy
        self.cwd = cwd
        self.session_id: str | None = None
        self._started = False
        self._initial_model = self.model  # Track for model change warnings

    def start(self) -> None:
        """Mark session as started."""
        self._started = True

    def set_model(self, new_model: str) -> str | None:
        """
        Change the model for subsequent tasks.

        Returns warning message if session will be lost, None otherwise.

        IMPORTANT: Provider Switch Behavior
        ===================================
        - OpenAI <-> Anthropic: Session RESET (context lost)
        - Same provider: Session preserved (gpt-4o -> gpt-5.1 OK)
        - Session ID cleared automatically on cross-provider switch

        Example:
            session.set_model("claude-3-5-sonnet")  # From GPT -> resets session_id
        """
        warning = check_model_change_warning(self.model, new_model)
        if warning and self.session_id:
            # Session exists and model is changing - context will be lost
            print(f"⚠️ Provider switch detected: {self.model} → {new_model}", file=sys.stderr)
            print("   Session reset - context will be lost", file=sys.stderr)
            self.session_id = None  # Clear session since it's now invalid
        self.model = new_model
        return warning

    def send(self, prompt: str) -> TaskResult:
        """
        Send a task and wait for completion.

        Uses session ID from previous call to maintain context.
        """
        if not self._started:
            raise RuntimeError("Session not started. Call start() first.")

        # Use run_droid_exec with session ID continuation
        result = run_droid_exec(
            prompt=prompt,
            task_type=TaskType.CODE,
            autonomy=self.autonomy,
            model=self.model,
            cwd=self.cwd,
            session_id=self.session_id,  # Pass previous session ID
        )

        # Capture session ID for next call
        if result.session_id:
            self.session_id = result.session_id

        return result

    def stop(self) -> None:
        """Mark session as stopped."""
        self._started = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False


# Map TaskType to TaskCategory for model selection
TASK_TO_CATEGORY = {
    # Core task types
    TaskType.ANALYZE: TaskCategory.STANDARD,
    TaskType.CODE: TaskCategory.STANDARD,
    TaskType.REFACTOR: TaskCategory.COMPLEX,
    TaskType.TEST: TaskCategory.STANDARD,
    TaskType.REVIEW: TaskCategory.FAST_SIMPLE,
    # Fabrik lifecycle task types
    TaskType.SPEC: TaskCategory.COMPLEX,  # Design mode - needs deep thinking
    TaskType.SCAFFOLD: TaskCategory.STANDARD,  # Project setup
    TaskType.DEPLOY: TaskCategory.STANDARD,  # Deployment configs
    TaskType.MIGRATE: TaskCategory.STANDARD,  # Database migrations
    TaskType.HEALTH: TaskCategory.FAST_SIMPLE,  # Quick health checks
    TaskType.PREFLIGHT: TaskCategory.FAST_SIMPLE,  # Pre-deploy checks
}


# =============================================================================
# Task Persistence Functions (from droid_runner.py)
# =============================================================================


def _sanitize_task_id(task_id: str, max_length: int = 128) -> str:
    """Sanitize task ID to prevent path traversal attacks and limit length."""
    sanitized = task_id.replace("/", "_").replace("\\", "_").replace("..", "__")
    result = "".join(c for c in sanitized if c.isalnum() or c in "_-")
    if len(result) > max_length:
        # Truncate but keep some uniqueness by appending hash suffix
        import hashlib

        suffix = hashlib.md5(result.encode()).hexdigest()[:8]
        result = result[: max_length - 9] + "_" + suffix
    return result


def save_task_record(record: TaskRecord) -> None:
    """Save task record to disk."""
    ensure_dirs()
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


def save_response(task_id: str, response: dict) -> None:
    """Save response to disk."""
    ensure_dirs()
    safe_id = _sanitize_task_id(task_id)
    path = RESPONSES_DIR / f"{safe_id}.json"
    with open(path, "w") as f:
        json.dump(response, f, indent=2)


def load_task_from_file(file_path: Path) -> str:
    """Load task prompt from .md or .txt file."""
    if not file_path.exists():
        raise FileNotFoundError(f"Task file not found: {file_path}")
    return file_path.read_text().strip()


def get_recommended_model(task_type: TaskType) -> str:
    """Get recommended model for a task type."""
    category = TASK_TO_CATEGORY.get(task_type, TaskCategory.STANDARD)
    return recommend_model(category)


def build_prompt(task_type: TaskType, user_prompt: str, cwd: str | None = None) -> str:
    """Build a structured prompt for the task type."""

    context = f"Working directory: {cwd or Path.cwd()}\n\n" if cwd else ""

    prompts = {
        TaskType.ANALYZE: f"""Analyze the following and provide insights.
Do NOT make any changes - this is read-only analysis.

{context}{user_prompt}

Provide your analysis in a structured format.""",
        TaskType.CODE: f"""Complete the following coding task.
You may read and edit files as needed.

{context}{user_prompt}

After completing, summarize what changes were made.""",
        TaskType.REFACTOR: f"""Refactor the following code.
Only modify existing files - do not create new files.

{context}{user_prompt}

Explain the refactoring approach and changes made.""",
        TaskType.TEST: f"""Generate or update tests for the following.
You may create test files and run tests.

{context}{user_prompt}

List all tests created/modified and their status.""",
        TaskType.REVIEW: f"""Review the following code for issues.
Do NOT make any changes - provide review comments only.

{context}{user_prompt}

Use severity levels:
- [P0] Critical - blocks release/operations
- [P1] Urgent - fix in next cycle
- [P2] Normal - fix eventually
- [P3] Low - nice-to-have

For each finding include: title, why it's a problem, file:line, severity, suggested fix.
End with overall assessment: correct/incorrect + 1-3 sentence summary.""",
        # Fabrik lifecycle task types
        TaskType.SPEC: f"""Create a detailed specification for the following.
This is Design mode - plan thoroughly before implementation.
Output a technical spec with: architecture, components, data flow, dependencies.

{context}{user_prompt}

Format:
## Overview
## Architecture
## Components
## Data Flow
## Dependencies
## Implementation Steps""",
        TaskType.SCAFFOLD: f"""Create a new Fabrik project structure.

Required structure:
- src/ with main.py, config.py (env vars via os.getenv)
- tests/, scripts/, docs/
- compose.yaml, Dockerfile, .env.example
- pyproject.toml (ruff, mypy configured)
- README.md with setup instructions

Critical requirements:
- Base image: python:3.12-slim-bookworm (NOT Alpine)
- All config via os.getenv('VAR', 'default') - NEVER hardcode
- Health endpoint that tests actual dependencies
- ARM64 compatible (linux/arm64 for VPS)
- Symlink AGENTS.md to /opt/fabrik/AGENTS.md
- Symlink .windsurfrules to /opt/fabrik/windsurfrules

{context}{user_prompt}

Create all required files for a production-ready Fabrik project.""",
        TaskType.DEPLOY: f"""Generate or update deployment configuration.
Target: Coolify on VPS via Docker Compose.
Include: compose.yaml, health checks, environment variables.

{context}{user_prompt}

Ensure configs work for both WSL dev and VPS production.""",
        TaskType.MIGRATE: f"""Handle database migration task.
Database: PostgreSQL (with pgvector if needed).
Follow Fabrik patterns: env-based connection strings, no hardcoded values.

{context}{user_prompt}

Generate migration files and document the changes.""",
        TaskType.HEALTH: f"""Verify deployment health autonomously.
Check: container status, API endpoints, database connection, service health.
This runs with full autonomy - fix issues if possible.

{context}{user_prompt}

Report status for each component and any issues found.""",
        TaskType.PREFLIGHT: f"""Pre-deployment readiness check for Fabrik project.

Check the following and report pass/fail for each:

## 1. Configuration
- [ ] All secrets in environment variables (not hardcoded)
- [ ] .env.example has all required vars documented
- [ ] compose.yaml environment section complete
- [ ] No localhost references in production config

## 2. Docker
- [ ] Dockerfile uses python:3.12-slim-bookworm (not Alpine)
- [ ] ARM64 compatible (linux/arm64)
- [ ] Health check defined in compose.yaml

## 3. Health Endpoint
- [ ] /health endpoint exists
- [ ] Tests actual dependencies (DB, Redis, etc.)
- [ ] Returns proper status codes

## 4. Code Quality
- [ ] ruff check . passes
- [ ] mypy . passes
- [ ] pytest passes
- [ ] No TODO/FIXME blockers

## 5. Documentation
- [ ] README.md with setup instructions
- [ ] AGENTS.md symlinked
- [ ] API endpoints documented

{context}{user_prompt}

Report status for each item. End with READY or NOT READY verdict.""",
    }

    return prompts.get(task_type, user_prompt)


def _run_streaming(
    args: list[str],
    prompt: str,
    task_type: TaskType,
    original_prompt: str,
    start_time: float,
    on_stream: Callable | None = None,
    timeout_seconds: int = 1800,  # 30 min default timeout
    stuck_threshold_seconds: int = 600,  # 10 min before considering stuck
    max_retries: int | None = None,  # None = auto-detect based on task type
) -> TaskResult:
    """
    Run droid exec in streaming mode, reading events until completion.

    Features:
    - ProcessMonitor integration for stuck detection
    - Auto-retry on stuck state (kills and reinitiates) - DISABLED for write-heavy tasks
    - Timeout enforcement
    - Completion event detection

    The completion event (type="completion") contains finalText and signals done.
    Note: prompt is already in args as CLI argument.
    """
    # Write-heavy tasks should NOT retry (not idempotent - could double-execute)
    write_heavy_tasks = {
        TaskType.CODE,
        TaskType.SCAFFOLD,
        TaskType.DEPLOY,
        TaskType.MIGRATE,
        TaskType.REFACTOR,
    }
    if max_retries is None:
        max_retries = 0 if task_type in write_heavy_tasks else 2
        if task_type in write_heavy_tasks:
            print(f"ℹ️ Retries disabled for {task_type.value} (write-heavy task)", file=sys.stderr)
    retry_count = 0
    max_stderr_lines = 50  # Bounded buffer to avoid memory issues

    def _stderr_reader(stream, buffer: deque) -> None:
        """Read stderr in background thread to avoid deadlock."""
        try:
            for line in stream:
                buffer.append(line.rstrip())
                if len(buffer) > max_stderr_lines:
                    buffer.popleft()
        except Exception:
            pass
        finally:
            with contextlib.suppress(Exception):
                stream.close()

    while retry_count <= max_retries:
        process = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,  # Capture stderr via background thread
            text=True,
        )

        # Capture stderr in background thread (bounded buffer)
        stderr_buffer: deque = deque(maxlen=max_stderr_lines)
        stderr_thread = threading.Thread(
            target=_stderr_reader, args=(process.stderr, stderr_buffer), daemon=True
        )
        stderr_thread.start()

        # Initialize ProcessMonitor if available
        monitor = None
        if PROCESS_MONITOR_AVAILABLE:
            with contextlib.suppress(Exception):
                monitor = ProcessMonitor(process, warn_threshold=300)

        final_text = ""
        session_id = None
        events = []
        got_completion = False
        got_error = False  # P0 FIX: Track is_error in events
        stuck_detected = False
        last_check_time = time.time()
        line_buffer = ""
        malformed_lines: list[str] = []  # Track malformed JSON for debugging

        # Non-blocking read loop using select
        while True:
            # Check if process has exited
            if process.poll() is not None:
                # Read any remaining output
                remaining = process.stdout.read()
                if remaining:
                    line_buffer += remaining
                break

            # Use select to check for available data (1 second timeout)
            ready, _, _ = select.select([process.stdout], [], [], 1.0)

            current_time = time.time()

            # Check for timeout
            if current_time - start_time > timeout_seconds:
                process.kill()
                process.wait()
                return TaskResult(
                    success=False,
                    task_type=task_type,
                    prompt=original_prompt,
                    result="",
                    error=f"Timeout after {timeout_seconds}s",
                    duration_ms=int((current_time - start_time) * 1000),
                )

            # Check for stuck state periodically (every 30s)
            if monitor and (current_time - last_check_time) > 30:
                last_check_time = current_time
                diagnosis = monitor.analyze()
                if diagnosis["state"] == "CONFIRMED_STUCK":
                    print(f"⚠️ Stuck detected: {diagnosis['reason']}", file=sys.stderr)
                    stuck_detected = True
                    break
                elif (
                    diagnosis["state"] == "LIKELY_STUCK"
                    and (current_time - start_time) > stuck_threshold_seconds
                ):
                    print(f"⚠️ Likely stuck: {diagnosis['reason']}", file=sys.stderr)
                    stuck_detected = True
                    break

            if not ready:
                continue  # No data available, loop to check timeout/stuck

            # Read available data
            chunk = process.stdout.read(4096)
            if not chunk:
                break  # EOF
            line_buffer += chunk
            if monitor:
                monitor.record_activity()

            # Process complete lines from buffer
            while "\n" in line_buffer:
                line, line_buffer = line_buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)
                    events.append(event)

                    if on_stream:
                        on_stream(event)

                    if event.get("type") == "completion":
                        final_text = event.get("finalText", "")
                        session_id = event.get("session_id")
                        got_completion = True
                        if event.get("is_error"):
                            process.wait()
                            return TaskResult(
                                success=False,
                                task_type=task_type,
                                prompt=original_prompt,
                                result=final_text,
                                error="Task reported error",
                                duration_ms=int((time.time() - start_time) * 1000),
                                session_id=session_id,
                            )

                    if event.get("type") == "result":
                        final_text = event.get("result", "")
                        session_id = event.get("session_id")
                        got_completion = True
                        if event.get("is_error"):
                            process.wait()
                            return TaskResult(
                                success=False,
                                task_type=task_type,
                                prompt=original_prompt,
                                result=final_text,
                                error="Task reported error",
                                duration_ms=int((time.time() - start_time) * 1000),
                                session_id=session_id,
                            )

                except json.JSONDecodeError:
                    # Log malformed JSON for debugging (don't silently ignore)
                    malformed_lines.append(line[:200])  # Bounded
                    if len(malformed_lines) <= 3:
                        print(f"⚠️ Malformed JSON: {line[:100]}...", file=sys.stderr)
                    continue

        # CRITICAL: Process any remaining lines in buffer after process exit
        # This fixes P0 where completion events in final buffer were not parsed
        while line_buffer:
            if "\n" in line_buffer:
                line, line_buffer = line_buffer.split("\n", 1)
            else:
                line = line_buffer
                line_buffer = ""
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                events.append(event)
                if on_stream:
                    on_stream(event)
                if event.get("type") == "completion":
                    final_text = event.get("finalText", "")
                    session_id = event.get("session_id")
                    got_completion = True
                    # P0 FIX: Check is_error in final buffer completion events
                    if event.get("is_error"):
                        got_error = True
                if event.get("type") == "result":
                    final_text = event.get("result", "")
                    session_id = event.get("session_id")
                    got_completion = True
                    # P0 FIX: Check is_error in final buffer result events
                    if event.get("is_error"):
                        got_error = True
            except json.JSONDecodeError:
                malformed_lines.append(line[:200])

        # Get stderr summary (capture buffer reference for closure)
        stderr_snapshot = list(stderr_buffer)[-10:] if stderr_buffer else []
        stderr_summary = "\nstderr: " + "\n".join(stderr_snapshot) if stderr_snapshot else ""

        # After while loop - handle stuck detection with retry
        if stuck_detected:
            process.kill()
            process.wait()
            stderr_thread.join(timeout=2)
            retry_count += 1
            if retry_count <= max_retries:
                print(
                    f"🔄 Retrying task (attempt {retry_count + 1}/{max_retries + 1})...",
                    file=sys.stderr,
                )
                time.sleep(2)
                continue
            return TaskResult(
                success=False,
                task_type=task_type,
                prompt=original_prompt,
                result="",
                error=f"Task stuck after {max_retries + 1} attempts{stderr_summary}",
                duration_ms=int((time.time() - start_time) * 1000),
            )

        # Normal completion path
        process.wait()
        stderr_thread.join(timeout=2)
        duration_ms = int((time.time() - start_time) * 1000)

        if process.returncode != 0:
            return TaskResult(
                success=False,
                task_type=task_type,
                prompt=original_prompt,
                result="",
                error=f"Exit code: {process.returncode}{stderr_summary}",
                duration_ms=duration_ms,
            )

        # If no completion event AND we had malformed lines, treat as failure
        if not got_completion and not final_text:
            error_msg = "No completion event received"
            if malformed_lines:
                error_msg += f" (had {len(malformed_lines)} malformed JSON lines)"
            return TaskResult(
                success=False,
                task_type=task_type,
                prompt=original_prompt,
                result="",
                error=error_msg + stderr_summary,
                duration_ms=duration_ms,
            )

        # P0 FIX: If got_error flag set, return failure even if got completion
        if got_error:
            return TaskResult(
                success=False,
                task_type=task_type,
                prompt=original_prompt,
                result=final_text,
                error=f"Event indicated error (is_error=True){stderr_summary}",
                duration_ms=duration_ms,
                session_id=session_id,
            )

        return TaskResult(
            success=True,
            task_type=task_type,
            prompt=original_prompt,
            result=final_text,
            duration_ms=duration_ms,
            session_id=session_id,
        )

    # Should not reach here, but safety return
    return TaskResult(
        success=False,
        task_type=task_type,
        prompt=original_prompt,
        result="",
        error="Unexpected loop exit",
        duration_ms=int((time.time() - start_time) * 1000),
    )


def run_droid_exec(
    prompt: str,
    task_type: TaskType,
    autonomy: Autonomy = Autonomy.LOW,
    model: str = DEFAULT_MODEL,
    cwd: str | None = None,
    session_id: str | None = None,
    streaming: bool = False,
    verbose: bool = False,
    on_stream: Callable | None = None,
) -> TaskResult:
    """
    Execute a task via droid exec.

    Waits for process completion (no timeout) - droid exec is a one-shot
    command that exits when done. Exit code 0 = success, non-zero = failure.

    Note: Model names are refreshed from config/models.yaml before each call.

    Args:
        prompt: The task prompt
        task_type: Type of task (affects default autonomy)
        autonomy: Safety level (low/medium/high)
        model: Model to use
        cwd: Working directory for the task
        session_id: Optional session ID for continuity
        streaming: If True, use stream-json format for real-time output
        verbose: If True, use stream-json format for verbose tool-call visibility
        on_stream: Callback for streaming events (receives dict per event)

    Returns:
        TaskResult with success status and output
    """
    # Ensure model names are up-to-date from config
    try:
        refresh_models_from_docs()
    except Exception as e:
        print(f"⚠️ Failed to refresh models from docs: {e}", file=sys.stderr)

    # Build command
    args = ["droid", "exec"]

    # Output format - stream-json for streaming/verbose, json for simple
    if verbose or streaming:
        args.extend(["--output-format", "stream-json"])
    else:
        args.extend(["--output-format", "json"])

    # Model
    args.extend(["--model", model])

    # Autonomy level
    args.extend(["--auto", autonomy.value])

    # Session continuity
    if session_id:
        args.extend(["--session-id", session_id])

    # Working directory
    if cwd:
        args.extend(["--cwd", cwd])

    # Spec mode for design/planning tasks
    task_config = TOOL_CONFIGS.get(task_type, {})
    if task_config.get("use_spec"):
        args.append("--use-spec")

    # Reasoning effort (off, low, medium, high)
    reasoning = task_config.get("reasoning", "off")
    if reasoning and reasoning != "off":
        args.extend(["--reasoning-effort", reasoning])

    # Build full prompt
    full_prompt = build_prompt(task_type, prompt, cwd)

    # Use file for large prompts (>100KB) to avoid "Argument list too long" error
    # OS limit is ~128KB for command line args
    # NOTE: Use project .tmp/ NOT system /tmp/ (per Fabrik rules)
    prompt_file_path = None
    if len(full_prompt) > 100_000:
        project_tmp = Path(__file__).parent.parent / ".tmp"
        project_tmp.mkdir(exist_ok=True)
        prompt_file_path = project_tmp / f"droid_prompt_{uuid.uuid4().hex[:8]}.md"
        prompt_file_path.write_text(full_prompt)
        args.extend(["--file", str(prompt_file_path)])
        print(f"ℹ️ Large prompt ({len(full_prompt)//1000}KB) - using temp file", file=sys.stderr)
    else:
        args.append(full_prompt)

    start_time = time.time()

    try:
        # Use streaming mode if explicitly requested OR if verbose (to show progress)
        use_streaming = streaming or verbose
        if use_streaming:
            # Streaming mode: read events as they come, wait for completion event
            # Pass callback for verbose output even if not explicitly streaming
            callback = on_stream if on_stream else (print_event if verbose else None)
            return _run_streaming(args, full_prompt, task_type, prompt, start_time, callback)

        # Non-streaming: wait for process with timeout (default 30 min for complex tasks)
        timeout_seconds = int(os.getenv("DROID_EXEC_TIMEOUT", "1800"))
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return TaskResult(
                success=False,
                task_type=task_type,
                prompt=prompt,
                result="",
                error=f"Timeout after {timeout_seconds}s",
                duration_ms=int((time.time() - start_time) * 1000),
            )

        duration_ms = int((time.time() - start_time) * 1000)

        if result.returncode != 0:
            return TaskResult(
                success=False,
                task_type=task_type,
                prompt=prompt,
                result="",
                error=result.stderr[:500] if result.stderr else f"Exit code: {result.returncode}",
                duration_ms=duration_ms,
            )

        # Parse JSON output
        output = result.stdout.strip()
        if not output:
            return TaskResult(
                success=False,
                task_type=task_type,
                prompt=prompt,
                result="",
                error="Empty output from droid exec",
                duration_ms=duration_ms,
            )

        try:
            # Try parsing each line as JSON first (more robust than brace matching)
            # This handles cases where droid outputs multiple JSON objects
            for line in output.strip().split("\n"):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        parsed = json.loads(line)
                        # Look for result-type JSON (has 'result' or 'is_error' key)
                        if "result" in parsed or "is_error" in parsed:
                            return TaskResult(
                                success=not parsed.get("is_error", False),
                                task_type=task_type,
                                prompt=prompt,
                                result=parsed.get("result", ""),
                                duration_ms=parsed.get("duration_ms", duration_ms),
                                session_id=parsed.get("session_id"),
                            )
                    except json.JSONDecodeError:
                        continue

            # Fallback: find outermost JSON object by brace matching
            first_brace = output.find("{")
            last_brace = output.rfind("}")
            if first_brace >= 0 and last_brace > first_brace:
                json_text = output[first_brace : last_brace + 1]
                parsed = json.loads(json_text)

                return TaskResult(
                    success=not parsed.get("is_error", False),
                    task_type=task_type,
                    prompt=prompt,
                    result=parsed.get("result", ""),
                    duration_ms=parsed.get("duration_ms", duration_ms),
                    session_id=parsed.get("session_id"),
                )
        except json.JSONDecodeError:
            # JSON parsing failed - check for error indicators in raw output
            # Don't blindly mark as success - look for failure signals
            has_error_indicator = any(
                indicator in output.lower()
                for indicator in ["error", "failed", "exception", "traceback", "is_error"]
            )
            if has_error_indicator:
                return TaskResult(
                    success=False,
                    task_type=task_type,
                    prompt=prompt,
                    result=output[:1000],
                    error="JSON parse failed, error indicators found in output",
                    duration_ms=duration_ms,
                )
            # No error indicators - still mark as failure since we couldn't parse
            return TaskResult(
                success=False,
                task_type=task_type,
                prompt=prompt,
                result=output[:1000],
                error="JSON parse failed, output format unexpected",
                duration_ms=duration_ms,
            )

    except Exception as e:
        return TaskResult(
            success=False,
            task_type=task_type,
            prompt=prompt,
            result="",
            error=str(e)[:500],
        )
    finally:
        # Cleanup temp prompt file if used
        if prompt_file_path and os.path.exists(prompt_file_path):
            with contextlib.suppress(Exception):
                os.unlink(prompt_file_path)


# =============================================================================
# Monitored Execution (from droid_runner.py)
# =============================================================================


def print_event(event: dict) -> None:
    """Default event printer for monitoring."""
    event_type = event.get("type", "unknown")
    if event_type == "message":
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


def run_droid_exec_monitored(
    prompt: str,
    task_id: str,
    model: str = "claude-opus-4-5-20251101",
    autonomy: str = "low",
    output_format: str = "stream-json",
    session_id: str | None = None,
    cwd: str | None = None,
    on_event: Callable[[dict], None] | None = None,
    warn_after_seconds: int = 300,
) -> TaskRecord:
    """
    Run droid exec with monitoring and task persistence.

    Uses stream-json format to monitor progress. Does NOT auto-kill.
    """
    if MODEL_UPDATER_AVAILABLE:
        with contextlib.suppress(Exception):
            update_if_stale()

    ensure_dirs()

    record = TaskRecord(
        task_id=task_id,
        prompt=prompt[:500],
        status=TaskStatus.PENDING,
        created_at=datetime.now(UTC).isoformat(),
        model=model,
        autonomy=autonomy,
        output_format=output_format,
    )
    save_task_record(record)

    args = ["droid", "exec", "--output-format", output_format, "--model", model, "--auto", autonomy]
    if session_id:
        args.extend(["--session-id", session_id])
    if cwd:
        args.extend(["--cwd", cwd])
    args.append(prompt)

    record.status = TaskStatus.RUNNING
    record.started_at = datetime.now(UTC).isoformat()
    record.last_activity_at = record.started_at
    save_task_record(record)

    print(f"[{task_id}] Starting droid exec...", file=sys.stderr)

    env = os.environ.copy()
    env.update({"CI": "1", "GIT_TERMINAL_PROMPT": "0", "TERM": "dumb", "NO_COLOR": "1"})

    process = subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,  # P1 FIX: Capture stderr for diagnostics
        text=True,
        cwd=cwd,
        env=env,
        start_new_session=True,
    )

    start_time = time.time()
    final_text = ""
    captured_session_id = None
    events = []
    stderr_lines: deque[str] = deque(maxlen=50)  # P1 FIX: Bounded stderr buffer

    # P1 FIX: Background thread to capture stderr without blocking
    def capture_stderr():
        try:
            for line in process.stderr:
                stderr_lines.append(line.rstrip())
        except Exception:
            pass

    stderr_thread = threading.Thread(target=capture_stderr, daemon=True)
    stderr_thread.start()

    monitor = None
    if PROCESS_MONITOR_AVAILABLE:
        try:
            monitor = ProcessMonitor(process, warn_threshold=warn_after_seconds)
            print(f"[{task_id}] ProcessMonitor active", file=sys.stderr)
        except Exception as e:
            print(f"[{task_id}] ProcessMonitor init failed: {e}", file=sys.stderr)

    try:
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue

            record.last_activity_at = datetime.now(UTC).isoformat()
            record.num_events += 1
            if monitor:
                monitor.record_activity()

            try:
                event = json.loads(line)
                events.append(event)
                if on_event:
                    on_event(event)

                if event.get("type") == "system" and event.get("subtype") == "init":
                    captured_session_id = event.get("session_id")
                    record.session_id = captured_session_id

                if event.get("type") == "completion":
                    final_text = event.get("finalText", "")
                    captured_session_id = event.get("session_id", captured_session_id)
                    record.completed_at = datetime.now(UTC).isoformat()
                    record.session_id = captured_session_id
                    record.duration_ms = event.get("durationMs")
                    # P0 FIX: Check is_error in completion event
                    if event.get("is_error"):
                        record.status = TaskStatus.FAILED
                        record.error = (
                            final_text[:500] if final_text else "Completion with is_error=True"
                        )
                        print(
                            f"[{task_id}] Failed (completion is_error) in {record.duration_ms}ms",
                            file=sys.stderr,
                        )
                    else:
                        record.status = TaskStatus.COMPLETED
                        record.result = final_text
                        print(f"[{task_id}] Completed in {record.duration_ms}ms", file=sys.stderr)
                    break

                if event.get("type") == "result" and event.get("is_error"):
                    record.status = TaskStatus.FAILED
                    record.error = event.get("result", "Unknown error")
                    break
            except json.JSONDecodeError:
                continue

        process.wait(timeout=30)

        # P0 FIX: If still RUNNING after process exit, mark as FAILED (no completion event)
        if record.status == TaskStatus.RUNNING:
            stderr_snippet = "\n".join(list(stderr_lines)[-10:]) if stderr_lines else ""
            record.status = TaskStatus.FAILED
            record.error = f"No completion event received (exit code {process.returncode})"
            if stderr_snippet:
                record.error += f"\nStderr: {stderr_snippet[:500]}"

        # P0 FIX: Non-zero exit code after completion = FAILED (not just warning)
        if process.returncode != 0 and record.status == TaskStatus.COMPLETED:
            stderr_snippet = "\n".join(list(stderr_lines)[-5:]) if stderr_lines else ""
            record.status = TaskStatus.FAILED
            record.error = f"Completed but exit code {process.returncode}"
            if stderr_snippet:
                record.error += f"\nStderr: {stderr_snippet[:300]}"
            print(
                f"[{task_id}] FAILED: Completed but exit code {process.returncode}", file=sys.stderr
            )

    except Exception as e:
        stderr_snippet = "\n".join(list(stderr_lines)[-10:]) if stderr_lines else ""
        record.status = TaskStatus.FAILED
        record.error = f"{str(e)}\nStderr: {stderr_snippet[:500]}" if stderr_snippet else str(e)

    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

        if record.duration_ms is None:
            record.duration_ms = int((time.time() - start_time) * 1000)

        save_task_record(record)
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
                "events": events[-10:],
            },
        )

    return record


# =============================================================================
# Batch Processing
# =============================================================================


def run_batch_tasks(
    tasks_file: Path,
    autonomy: Autonomy = Autonomy.LOW,
    output_file: Path | None = None,
    shared_session: bool = True,
) -> list[TaskResult]:
    """
    Run multiple tasks from a JSONL file.

    Each line should be: {"type": "analyze|code|...", "prompt": "...", "cwd": "..."}

    Args:
        shared_session: If True, propagate session_id between tasks for context continuity
    """
    results = []
    session_id = None  # Track session for continuity

    with open(tasks_file) as f:
        tasks = [json.loads(line) for line in f if line.strip()]

    print(f"Running {len(tasks)} tasks with autonomy={autonomy.value}")

    # Use ExitStack to handle optional file opening safely
    with contextlib.ExitStack() as stack:
        out_f = stack.enter_context(open(output_file, "w")) if output_file else None

        for i, task in enumerate(tasks, 1):
            # Handle invalid task types gracefully
            try:
                task_type = TaskType(task.get("type", "analyze"))
            except ValueError:
                print(f"[{i}/{len(tasks)}] Invalid type '{task.get('type')}', skipping")
                results.append(
                    TaskResult(
                        success=False,
                        task_type=TaskType.ANALYZE,
                        prompt=task.get("prompt", ""),
                        result="",
                        error=f"Invalid task type: {task.get('type')}",
                    )
                )
                continue

            prompt = task["prompt"]
            cwd = task.get("cwd")

            print(f"[{i}/{len(tasks)}] {task_type.value}: {prompt[:50]}...", end=" ", flush=True)

            result = run_droid_exec(
                prompt=prompt,
                task_type=task_type,
                autonomy=autonomy,
                cwd=cwd,
                session_id=session_id if shared_session else None,
            )

            # Propagate session_id for next task
            if shared_session and result.session_id:
                session_id = result.session_id

            results.append(result)

            if result.success:
                print(f"✓ ({result.duration_ms}ms)")
            else:
                print(f"✗ {result.error[:30]}")

            # Write result
            if out_f:
                out_f.write(
                    json.dumps(
                        {
                            "success": result.success,
                            "type": result.task_type.value,
                            "prompt": result.prompt,
                            "result": result.result[:1000],  # Truncate for storage
                            "error": result.error,
                            "duration_ms": result.duration_ms,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                out_f.flush()

            # Small delay between tasks
            time.sleep(0.5)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Run coding tasks via droid exec",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Task Types (Core):
  analyze   Read-only analysis (safest)
  code      Coding with file edits
  refactor  Modify existing files only
  test      Generate/run tests
  review    Code review (read-only)

Task Types (Fabrik Lifecycle):
  spec      Design mode - detailed planning with --use-spec
  scaffold  Create new Fabrik project structure
  deploy    Generate/update Coolify deployment configs
  migrate   Database migration tasks
  health    Verify deployment health (autonomous)
  preflight Pre-deployment readiness check

Examples:
  # Design mode - plan before implementation
  %(prog)s spec "Plan the authentication system for user-service"

  # Scaffold new project
  %(prog)s scaffold "Create a FastAPI service with PostgreSQL"

  # Deploy config generation
  %(prog)s deploy "Add Redis cache to the compose file"

  # Autonomous health check
  %(prog)s health "Verify user-service deployment on VPS"

  # Batch processing
  %(prog)s batch tasks.jsonl --output results.jsonl
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Single task commands
    for task_type in TaskType:
        task_config = TOOL_CONFIGS.get(task_type, {})
        default_auto = task_config.get("default_auto", "low")
        default_model = task_config.get("model", DEFAULT_MODEL)

        sub = subparsers.add_parser(
            task_type.value,
            help=task_config.get("description", ""),
        )
        sub.add_argument("prompt", help="Task description")
        sub.add_argument("--cwd", help="Working directory")
        sub.add_argument(
            "--auto",
            choices=["low", "medium", "high"],
            default=default_auto,
            help=f"Autonomy level (default: {default_auto})",
        )
        sub.add_argument(
            "--model", default=default_model, help=f"Model to use (default: {default_model})"
        )
        sub.add_argument("--session-id", help="Session ID for continuity")
        sub.add_argument("--stream", action="store_true", help="Stream output in real-time")
        sub.add_argument(
            "--verbose", action="store_true", help="Verbose output showing tool calls (stream-json)"
        )

    # Batch command
    batch = subparsers.add_parser("batch", help="Run batch tasks from JSONL file")
    batch.add_argument("tasks_file", type=Path, help="JSONL file with tasks")
    batch.add_argument("--output", type=Path, help="Output file for results")
    batch.add_argument(
        "--auto",
        choices=["low", "medium", "high"],
        default="low",
        help="Autonomy level (default: low)",
    )

    # Interactive session command (Pattern 1: long-lived process)
    session_cmd = subparsers.add_parser("session", help="Interactive session (long-lived process)")
    session_cmd.add_argument("--cwd", help="Working directory")
    session_cmd.add_argument(
        "--auto",
        choices=["low", "medium", "high"],
        default="low",
        help="Autonomy level (default: low)",
    )
    session_cmd.add_argument("--model", default=DEFAULT_MODEL, help="Model to use")

    # Run command (from droid_runner.py) - with monitoring
    run_parser = subparsers.add_parser("run", help="Run a droid task with monitoring")
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
        "--warn-after", type=int, default=300, help="Seconds without activity before warning"
    )

    # Status command (from droid_runner.py)
    status_parser = subparsers.add_parser("status", help="Check task status")
    status_parser.add_argument("task_id", help="Task ID to check")

    # List command (from droid_runner.py)
    list_parser = subparsers.add_parser("list", help="List recent tasks")
    list_parser.add_argument("--limit", "-n", type=int, default=10, help="Number of tasks to show")

    args = parser.parse_args()

    if args.command == "batch":
        results = run_batch_tasks(
            tasks_file=args.tasks_file,
            autonomy=Autonomy(args.auto),
            output_file=args.output,
        )
        success = sum(1 for r in results if r.success)
        print(f"\nCompleted: {success}/{len(results)} successful")

    elif args.command == "session":
        # Pattern 1: Interactive long-lived session
        print("Starting interactive session (Ctrl+C to exit)")
        print(f"Model: {args.model}, Autonomy: {args.auto}")
        if args.cwd:
            print(f"Working directory: {args.cwd}")
        print("-" * 50)

        with DroidSession(
            model=args.model,
            autonomy=Autonomy(args.auto),
            cwd=args.cwd,
        ) as session:
            while True:
                try:
                    prompt = input("\n> ").strip()
                    if not prompt:
                        continue
                    if prompt.lower() in ("exit", "quit", "q"):
                        break

                    print()  # Newline before response
                    result = session.send(prompt)

                    if result.success:
                        print(result.result)
                        print(f"\n[{result.duration_ms}ms, session: {result.session_id}]")
                    else:
                        print(f"Error: {result.error}", file=sys.stderr)

                except KeyboardInterrupt:
                    print("\nExiting session...")
                    break
                except EOFError:
                    break

        print("Session ended.")

    elif args.command == "run":
        # Run with monitoring (from droid_runner.py)
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

        task_id = args.task_id or f"task-{uuid.uuid4().hex[:8]}"
        record = run_droid_exec_monitored(
            prompt=prompt,
            task_id=task_id,
            model=args.model,
            autonomy=args.auto,
            output_format="stream-json",
            session_id=args.session_id,
            cwd=args.cwd,
            on_event=print_event if args.verbose else None,
            warn_after_seconds=args.warn_after,
        )

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

        sys.exit(0 if record.status == TaskStatus.COMPLETED else 1)

    elif args.command == "status":
        # Check task status (from droid_runner.py)
        record = load_task_record(args.task_id)
        if not record:
            print(f"Task not found: {args.task_id}", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(asdict(record), indent=2, default=str))

    elif args.command == "list":
        # List recent tasks (from droid_runner.py)
        ensure_dirs()
        tasks = sorted(TASKS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for task_path in tasks[: args.limit]:
            with open(task_path) as f:
                data = json.load(f)
            print(
                f"{data['task_id']}: {data['status']} ({data.get('duration_ms', '?')}ms) - {data['prompt'][:50]}..."
            )

    else:
        # Single task execution
        task_type = TaskType(args.command)
        cwd = getattr(args, "cwd", None)
        session_id = getattr(args, "session_id", None)
        streaming = getattr(args, "stream", False)
        verbose = getattr(args, "verbose", False)

        # Streaming callback to print events in real-time
        def on_stream_event(event):
            if event.get("type") == "text_delta":
                print(event.get("text", ""), end="", flush=True)

        result = run_droid_exec(
            prompt=args.prompt,
            task_type=task_type,
            autonomy=Autonomy(args.auto),
            model=args.model,
            cwd=cwd,
            session_id=session_id,
            streaming=streaming or verbose,
            on_stream=on_stream_event if streaming else None,
        )

        if result.success:
            print(result.result)
            # Print session ID for continuation (Pattern 2)
            if result.session_id:
                print(f"\n[Session ID: {result.session_id}]", file=sys.stderr)
        else:
            print(f"Error: {result.error}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
