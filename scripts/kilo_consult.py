#!/usr/bin/env python3
# RETIRED 2026-07-19 — Kilo CLI stack retired (operator directive: LLM access = Claude Max OAuth + OpenRouter only). Zero runtime callers; kept for history — do not use.
"""
kilo_consult.py - Cascade consultation via Kilo CLI (Q&A only)

Workflow Doc: docs/workflows/KILO_CONSULT_WORKFLOW.md

Usage:
    python scripts/kilo_consult.py --file path/to/file.py "Your question"
    python scripts/kilo_consult.py --model kilo/anthropic/claude-opus-4.6 --file file.py "Question"
    python scripts/kilo_consult.py --session consult-coolify-20260415 "Follow-up question"

Features:
    - Risk-based routing (high-risk paths → escalate to Opus)
    - Session management (session_id for related questions)
    - Optional git diff context for stuck-on-changes scenarios
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# =============================================================================
# CONFIGURATION
# =============================================================================

# High-risk directory prefixes (escalate to Opus if diff touches these)
HIGH_RISK_DIR_PREFIXES = [
    "backend/",
    "server/",
    "api/",
    "auth/",
    "security/",
    "session/",
    "middleware/",
    "permissions/",
    "migrations/",
    "alembic/",
    "prisma/",
    "db/",
    "database/",
    "models/",
    "docker/",
    "infra/",
    "infrastructure/",
    ".github/",
    "ci/",
    "wp-content/plugins/",
    "wp-content/themes/",
]

# High-risk filenames (exact match, case-insensitive)
HIGH_RISK_FILENAMES = [
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "requirements.txt",
    "poetry.lock",
    "pyproject.toml",
    "go.mod",
    "go.sum",
    "cargo.toml",
    "cargo.lock",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yaml",
    "compose.yml",
    ".env",
    ".env.production",
    ".env.local",
    "manifest.json",
    "background.js",
    "service_worker.js",
]

_HIGH_RISK_FILENAMES_LOWER = {f.lower() for f in HIGH_RISK_FILENAMES}

# Default models (configurable via env vars)
MODEL_CHEAP = os.getenv("KILO_MODEL_CHEAP", "kilo/google/gemini-3-flash-preview")
MODEL_MID = os.getenv("KILO_MODEL_MID", "kilo/openai/gpt-5.4")
MODEL_EXPENSIVE = os.getenv("KILO_MODEL_EXPENSIVE", "kilo/anthropic/claude-opus-4.6")

# Variant by risk level
VARIANT_BY_RISK = {
    "low": "low",
    "medium": "high",
    "high": "high",
    "critical": "max",
}

# Session directory
SESSION_DIR = Path(os.getenv("KILO_SESSION_DIR", ".droid/consultations"))

# Timeout configuration
KILO_TIMEOUT = int(os.getenv("KILO_TIMEOUT", "600"))  # seconds

# Consulted agent directives — injected into every prompt sent to Kilo.
# Consulting agent directives (for Cascade) stay in the workflow doc only.
CONSULTED_AGENT_DIRECTIVES = (
    "Response directives:\n"
    "- Give crystal clear step-by-step answers. Be specific — cite line numbers and function names.\n"
    "- Explain the why, not just the what. Mention edge cases and failure modes.\n"
    "- Be thorough. Do not assume — state assumptions explicitly before proceeding.\n"
    "- Do not hallucinate APIs, methods, or library features. If unsure, say so.\n"
    "- Before returning, review your output for correctness and completeness."
)

# =============================================================================
# RISK ASSESSMENT
# =============================================================================


def assess_risk(file_path: str) -> str:
    """Assess risk level based on file path."""
    path_obj = Path(file_path)

    # Check high-risk filenames (exact match on filename only) - O(1) set lookup
    if path_obj.name.lower() in _HIGH_RISK_FILENAMES_LOWER:
        return "critical"

    # Check high-risk directory prefixes
    for prefix in HIGH_RISK_DIR_PREFIXES:
        if file_path.startswith(prefix):
            return "high"

    # Check if it's a documentation file (low risk)
    doc_extensions = {".md", ".rst", ".txt"}
    if path_obj.suffix in doc_extensions:
        return "low"

    # Everything else is medium risk
    return "medium"


# =============================================================================
# MODEL SELECTION
# =============================================================================


def get_model_for_risk(risk_level: str) -> str:
    """Get appropriate model based on risk level."""
    # Direct risk → model mapping (no escalation implemented)
    return {
        "critical": MODEL_EXPENSIVE,
        "high": MODEL_MID,
        "medium": MODEL_CHEAP,
        "low": MODEL_CHEAP,
    }.get(risk_level, MODEL_CHEAP)


def get_variant_for_risk(risk_level: str) -> str:
    """Get appropriate variant based on risk level."""
    return VARIANT_BY_RISK.get(risk_level, "high")


# =============================================================================
# SESSION MANAGEMENT
# =============================================================================


def create_session_id(file_path: str) -> str:
    """Create session ID from file path with hash suffix to avoid collisions."""
    path_hash = hashlib.sha256(file_path.encode()).hexdigest()[:6]
    filename = Path(file_path).stem
    date_str = datetime.now(UTC).strftime("%Y%m%d")
    return f"consult-{filename}-{path_hash}-{date_str}"


def load_session_state(session_id: str) -> dict[str, Any] | None:
    """Load session state from file."""
    session_file = SESSION_DIR / f"{session_id}.json"
    if session_file.exists():
        with open(session_file, encoding="utf-8") as f:
            return json.load(f)
    return None


def save_session_state(session_id: str, state: dict[str, Any]) -> None:
    """Save session state to file."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    session_file = SESSION_DIR / f"{session_id}.json"
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# =============================================================================
# KILO CLI EXECUTION
# =============================================================================


def run_kilo(
    model: str,
    variant: str,
    file_path: str | None,
    question: str,
    session_id: str,
    timeout: int,
    diff: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> tuple[str, int]:
    """Run Kilo CLI with given parameters.

    Returns:
        (output, exit_code)
    """
    cmd = [
        "kilo",
        "run",
        "--model",
        model,
        "--variant",
        variant,
        "--title",
        session_id,
        "--auto",  # Non-interactive
    ]

    if file_path:
        cmd.extend(["--file", file_path])

    # Build input with optional history and diff context
    input_text = question
    if diff:
        input_text = f"Current git diff:\n\n{diff}\n\n{input_text}"
    if history:
        history_text = "\n\n".join(
            f"Q: {h['question']}\nA: {h['answer']}"
            for h in history[-5:]  # Last 5 Q&A pairs
        )
        input_text = f"Previous conversation:\n\n{history_text}\n\n{input_text}"

    # Prepend consulted agent directives (outermost — sets response expectations)
    input_text = f"{CONSULTED_AGENT_DIRECTIVES}\n\n{input_text}"

    try:
        result = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.stderr:
            print(f"[Kilo stderr] {result.stderr}", file=sys.stderr)
        return result.stdout, result.returncode
    except subprocess.TimeoutExpired as exc:
        raw = exc.stdout
        partial = (
            raw
            if isinstance(raw, str)
            else raw.decode("utf-8", errors="replace")
            if isinstance(raw, bytes)
            else ""
        )
        if partial:
            print(
                f"[Kilo] Timeout after {timeout}s — returning partial output ({len(partial)} chars)",
                file=sys.stderr,
            )
        else:
            print(f"[Kilo] Timeout after {timeout}s — no output captured", file=sys.stderr)
        return partial, 124
    except FileNotFoundError:
        return "[Error] kilo CLI not found on PATH", 127


# =============================================================================
# MAIN
# =============================================================================


def main():
    parser = argparse.ArgumentParser(description="Cascade consultation via Kilo CLI")
    parser.add_argument("--file", help="File to consult about")
    parser.add_argument("--model", help="Override model selection")
    parser.add_argument("--variant", help="Override variant selection")
    parser.add_argument("--session", help="Continue existing session")
    parser.add_argument("--timeout", type=int, default=KILO_TIMEOUT, help="Timeout in seconds")
    parser.add_argument(
        "--diff", action="store_true", help="Include git diff in consultation context"
    )
    parser.add_argument("question", help="Your question")

    args = parser.parse_args()

    # Determine session ID
    if args.session:
        session_id = args.session
        session_state = load_session_state(session_id)
        if session_state:
            file_path = args.file or session_state.get("file_path")
            risk_level = (
                assess_risk(file_path) if file_path else session_state.get("risk_level", "medium")
            )
        else:
            file_path = args.file
            risk_level = assess_risk(file_path) if file_path else "medium"
    else:
        file_path = args.file
        risk_level = assess_risk(file_path) if file_path else "medium"
        session_id = (
            create_session_id(file_path)
            if file_path
            else f"consult-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        )
        session_state = None

    # Determine model and variant
    model = args.model or get_model_for_risk(risk_level)
    variant = args.variant or get_variant_for_risk(risk_level)

    # Cost warning for Opus 4.6
    if "claude-opus-4.6" in model:
        print("[Warning] Routing to Opus 4.6 ($25/1M output tokens).", file=sys.stderr)

    # File existence check
    if file_path and not Path(file_path).exists():
        print(f"[Error] File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    # Get git diff if requested
    diff_text = None
    if args.diff:
        try:
            result = subprocess.run(
                ["git", "diff"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            diff_text = result.stdout if result.stdout else None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            diff_text = None

    # Print consultation info
    print(f"[Consult] Session: {session_id}", file=sys.stderr)
    print(f"[Consult] Risk: {risk_level}", file=sys.stderr)
    print(f"[Consult] Model: {model}", file=sys.stderr)
    print(f"[Consult] Variant: {variant}", file=sys.stderr)
    if file_path:
        print(f"[Consult] File: {file_path}", file=sys.stderr)
    if diff_text:
        print(f"[Consult] Diff: {len(diff_text)} bytes", file=sys.stderr)
    print(f"[Consult] Question: {args.question}", file=sys.stderr)
    print(file=sys.stderr)

    # Run Kilo
    output, exit_code = run_kilo(
        model=model,
        variant=variant,
        file_path=file_path,
        question=args.question,
        session_id=session_id,
        timeout=args.timeout,
        diff=diff_text,
        history=session_state.get("history") if session_state else None,
    )

    # Print output
    print(output)

    # Reminder for consulting agent (Cascade-side verification)
    if exit_code == 0:
        print("[Reminder] Verify critical claims before acting.", file=sys.stderr)

    # Save session state only on success
    if exit_code == 0 and output:
        prev_history = session_state.get("history", []) if session_state else []
        new_history = prev_history + [{"question": args.question, "answer": output}]
        # Cap history to last 10 entries to prevent unbounded growth
        if len(new_history) > 10:
            new_history = new_history[-10:]
        state = {
            "session_id": session_id,
            "created_at": session_state.get("created_at")
            if session_state
            else datetime.now(UTC).isoformat(),
            "last_used_at": datetime.now(UTC).isoformat(),
            "model": model,
            "variant": variant,
            "file_path": file_path,
            "risk_level": risk_level,
            "iteration": (session_state.get("iteration", 0) + 1) if session_state else 1,
            "history": new_history,
        }
        save_session_state(session_id, state)

    # Exit with Kilo's exit code
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
