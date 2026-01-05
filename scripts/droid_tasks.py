#!/usr/bin/env python3
"""
Droid Exec Task Runner

Assigns coding tasks to droid exec with proper completion detection and session continuity.

PATTERN SELECTION
=================

Pattern 1 (Long-lived) - DroidSession class with stream-jsonrpc:
  Use when:
    - Tasks are frequent (seconds-minutes apart)
    - Heavy context dependency between tasks
    - You want one "agent instance" that maintains state
  Tradeoffs:
    - Crash = lose context (need restart strategy)
    - 1 worker = 1 context (parallelism needs multiple processes)

Pattern 2 (Session ID) - New process per task with --session-id:  [RECOMMENDED DEFAULT]
  Use when:
    - Need maximum reliability and easy retries
    - Want horizontal scaling (multiple workers)
    - Tasks are discrete even if related
    - Standard job queue architecture
  Tradeoffs:
    - Slight per-task overhead (process startup)
    - May need brief "state recap" in prompts

For production task queues: Pattern 2 is safer (timeouts, retries, crashes, memory leaks).

USAGE
=====

    # Single task (one-shot)
    python scripts/droid_tasks.py analyze "Review the authentication flow"

    # Continue previous session (Pattern 2)
    python scripts/droid_tasks.py code "Now add error handling" --session-id <id>

    # Interactive session (Pattern 1 - long-lived process)
    python scripts/droid_tasks.py session

    # Batch tasks with shared session
    python scripts/droid_tasks.py batch tasks.jsonl --auto low
"""

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# Import model registry (handle both module and script execution)
try:
    from scripts.droid_models import (
        DEFAULT_MODEL,
        MODELS,
        TaskCategory,
        check_model_change_warning,
        get_model_info,
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
    # Fabrik lifecycle task types
    SPEC = "spec"  # Specification mode - plan before implementing
    SCAFFOLD = "scaffold"  # Create new Fabrik project structure
    DEPLOY = "deploy"  # Generate/update deployment configs
    MIGRATE = "migrate"  # Database migration tasks
    HEALTH = "health"  # Verify deployment health (autonomous)
    PREFLIGHT = "preflight"  # Pre-deployment readiness check


@dataclass
class TaskResult:
    success: bool
    task_type: TaskType
    prompt: str
    result: str
    error: str | None = None
    duration_ms: int | None = None
    session_id: str | None = None


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
        "model": "claude-haiku-4-5-20251001",  # Fast, cheap reviews
        "reasoning": "off",
        "description": "Read-only code review",
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
        NOTE: Changing model invalidates session - context will be lost.
        """
        warning = check_model_change_warning(self.model, new_model)
        if warning and self.session_id:
            # Session exists and model is changing - context will be lost
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
    on_stream: callable | None = None,
) -> TaskResult:
    """
    Run droid exec in streaming mode, reading events until completion.

    The completion event (type="completion") contains finalText and signals done.
    Note: prompt is already in args as CLI argument.
    """
    process = subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,  # Prevent interactive prompts from hanging
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,  # Prevent deadlock: don't pipe stderr if not reading it
        text=True,
    )

    final_text = ""
    session_id = None
    events = []

    # Read streaming JSONL events until process exits
    for line in process.stdout:
        line = line.strip()
        if not line:
            continue

        try:
            event = json.loads(line)
            events.append(event)

            # Call streaming callback if provided
            if on_stream:
                on_stream(event)

            # Check for completion event (signals done)
            if event.get("type") == "completion":
                final_text = event.get("finalText", "")
                session_id = event.get("session_id")
                # Check is_error flag in completion event
                if event.get("is_error"):
                    process.wait()
                    return TaskResult(
                        success=False,
                        task_type=task_type,
                        prompt=original_prompt,
                        result=final_text,
                        error="Task reported error in completion event",
                        duration_ms=int((time.time() - start_time) * 1000),
                        session_id=session_id,
                    )
                break

            # Also check for result type (non-streaming format)
            if event.get("type") == "result":
                final_text = event.get("result", "")
                session_id = event.get("session_id")
                # Check is_error flag in result event
                if event.get("is_error"):
                    process.wait()
                    return TaskResult(
                        success=False,
                        task_type=task_type,
                        prompt=original_prompt,
                        result=final_text,
                        error="Task reported error in result event",
                        duration_ms=int((time.time() - start_time) * 1000),
                        session_id=session_id,
                    )

        except json.JSONDecodeError:
            continue

    # Wait for process to exit
    process.wait()
    duration_ms = int((time.time() - start_time) * 1000)

    if process.returncode != 0:
        # stderr is DEVNULL so we can't read it - just report exit code
        return TaskResult(
            success=False,
            task_type=task_type,
            prompt=original_prompt,
            result="",
            error=f"Exit code: {process.returncode}",
            duration_ms=duration_ms,
        )

    return TaskResult(
        success=True,
        task_type=task_type,
        prompt=original_prompt,
        result=final_text,
        duration_ms=duration_ms,
        session_id=session_id,
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
    on_stream: callable | None = None,
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
    except Exception:
        pass  # Non-fatal - continue with cached models

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

    # Build full prompt and add as CLI argument (not stdin!)
    # This matches the working calendar-orchestration-engine implementation
    full_prompt = build_prompt(task_type, prompt, cwd)
    args.append(full_prompt)

    start_time = time.time()

    try:
        if streaming:
            # Streaming mode: read events as they come, wait for completion event
            return _run_streaming(args, full_prompt, task_type, prompt, start_time, on_stream)

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
            # Return raw output if JSON parsing fails
            return TaskResult(
                success=True,
                task_type=task_type,
                prompt=prompt,
                result=output,
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


def run_batch_tasks(
    tasks_file: Path,
    autonomy: Autonomy = Autonomy.LOW,
    output_file: Path | None = None,
) -> list[TaskResult]:
    """
    Run multiple tasks from a JSONL file.

    Each line should be: {"type": "analyze|code|...", "prompt": "...", "cwd": "..."}
    """
    results = []

    with open(tasks_file) as f:
        tasks = [json.loads(line) for line in f if line.strip()]

    print(f"Running {len(tasks)} tasks with autonomy={autonomy.value}")

    out_f = open(output_file, "w") if output_file else None

    try:
        for i, task in enumerate(tasks, 1):
            task_type = TaskType(task.get("type", "analyze"))
            prompt = task["prompt"]
            cwd = task.get("cwd")

            print(f"[{i}/{len(tasks)}] {task_type.value}: {prompt[:50]}...", end=" ", flush=True)

            result = run_droid_exec(
                prompt=prompt,
                task_type=task_type,
                autonomy=autonomy,
                cwd=cwd,
            )

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
    finally:
        if out_f:
            out_f.close()

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
