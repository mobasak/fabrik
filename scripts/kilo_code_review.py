#!/usr/bin/env python3
"""
Kilo-powered iterative code review with fix-and-revalidate loop.

This script provides a Cascade-directed code review system using Kilo CLI.
It performs iterative review → fix → re-review cycles until clean or max iterations.

Usage:
    # Review specific files
    python scripts/kilo_code_review.py review src/file.py tests/test_file.py

    # Review with auto-fix loop
    python scripts/kilo_code_review.py auto-fix src/file.py --max-iterations 3

    # Review git staged files
    python scripts/kilo_code_review.py staged

    # Review git changed files (working tree)
    python scripts/kilo_code_review.py changed

    # Continue existing session
    python scripts/kilo_code_review.py auto-fix src/ --session continue

Exit codes:
    0 - Review passed (PASS verdict)
    1 - Review failed (FAIL verdict with issues remaining)
    2 - Error (Kilo unavailable, invalid input, etc.)

Workflow Doc: docs/workflows/KILO_REVIEW_WORKFLOW.md
  ⚠️  Update the workflow doc when modifying this script.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

# DB-driven model selection (replaces hardcoded TIER_MODELS and REASONING_MODELS)
# Handle missing kilo-benchmarks/ when script is synced to child projects
_kilo_benchmarks_path = Path(__file__).parent / "kilo-benchmarks"
if _kilo_benchmarks_path.exists():
    sys.path.insert(0, str(_kilo_benchmarks_path))
    from db_models import (
        get_fallback_chain,
        get_tier_models,
        has_reasoning,
        is_model_blocked,
    )
else:
    # Fallback stubs when kilo-benchmarks/ not present (child projects)
    # Use env vars for models, with reasonable fallbacks
    _DEFAULT_MODEL = os.getenv("KILO_DEFAULT_MODEL", "anthropic:claude-sonnet-4-5-20250929")
    _FALLBACK_MODEL = os.getenv("KILO_FALLBACK_MODEL", "openai:gpt-4.1")

    def get_fallback_chain(_role: str) -> list[str]:
        return [_DEFAULT_MODEL, _FALLBACK_MODEL]

    def get_tier_models(_role: str) -> dict[str, list[str]]:
        return {"default": [_DEFAULT_MODEL]}

    def has_reasoning(model: str) -> bool:
        return "thinking" in model or "o1" in model or "o3" in model

    def is_model_blocked(_model: str) -> bool:
        return False

# =============================================================================
# CONFIGURATION
# =============================================================================

# Max file size (bytes) to attach directly
MAX_FILE_SIZE = 50_000  # 50KB

# Max lines per file before chunking
MAX_LINES_PER_FILE = 500

# Max files per Kilo call
MAX_FILES_PER_BATCH = 5

# Max diff size (characters)
MAX_DIFF_SIZE = 15_000  # 15KB

# Max prompt size (bytes) to prevent memory exhaustion
MAX_PROMPT_SIZE = 100_000  # 100KB

# Timeout configuration for monitored Kilo execution
KILO_IDLE_TIMEOUT = int(os.getenv("KILO_IDLE_TIMEOUT", "120"))  # seconds without output
KILO_HARD_TIMEOUT = int(os.getenv("KILO_HARD_TIMEOUT", "1200"))  # absolute max runtime
KILO_POLL_INTERVAL = float(os.getenv("KILO_POLL_INTERVAL", "1.0"))  # monitor check interval

# Feature flags (expensive features opt-in, default OFF)
KILO_ENABLE_MULTI_PASS = os.getenv("KILO_ENABLE_MULTI_PASS", "0") == "1"
KILO_ENABLE_PASS_VERIFY = os.getenv("KILO_ENABLE_PASS_VERIFY", "0") == "1"
KILO_ENABLE_AUDIT = os.getenv("KILO_ENABLE_AUDIT", "0") == "1"

# Valid Kilo agents
VALID_AGENTS = {
    "ask",
    "code",
    "compaction",
    "debug",
    "general",
    "orchestrator",
    "plan",
    "summary",
    "title",
}

# Valid Kilo variants
VALID_VARIANTS = {"minimal", "low", "high", "max"}

# Valid review categories (for --skip-categories)
VALID_CATEGORIES = {"SPEC", "SECURITY", "CONFIG", "EDGE", "FABRIK", "DOCS"}

# Doc-only categories (lighter review for .md files)
DOC_ONLY_CATEGORIES = {"SPEC", "DOCS"}

# Max iterations by file type (docs need fewer iterations)
MAX_ITERATIONS_DOCS = 2
MAX_ITERATIONS_CODE = 5

# Documentation file extensions (lighter review)
DOC_EXTENSIONS = {".md", ".rst", ".txt", ".adoc"}

# Default model for code review
# AUTO MODEL (kilo/auto - recommended):
#   - Automatically routes to best model for task
#   - Opus 4.6 for planning/reasoning modes (architect, orchestrator, ask, review)
#   - Sonnet 4.5 for implementation modes (code, build, debug, explore)
#   - No configuration needed, transparent routing
#
# Note: Kilo CLI requires full model path with kilo/ prefix (e.g. "kilo/anthropic/claude-opus-4.6")
# This differs from config/models.yaml which uses short names (e.g. "claude-opus-4-6").
# The kilo_models section in models.yaml maps providers to short model names;
# this script uses the kilo/<provider>/<model> format required by Kilo CLI.
# Can be overridden via KILO_REVIEW_MODEL env var (validated at runtime)
# Default: kilo/auto (automatic mode-based routing)
# Fallback: Gemini 3 Flash if auto unavailable
_DEFAULT_MODEL = "kilo/auto"
_DEFAULT_MODEL_FALLBACK = "kilo/google/gemini-3-flash-preview"

# Multi-pass review triggers
SECURITY_SENSITIVE_PATHS = {
    "auth",
    "login",
    "password",
    "secret",
    "token",
    "session",
    "crypto",
    "encryption",
    "jwt",
    "oauth",
    "permission",
    "role",
    "admin",
    "sudo",
    "credential",
    "key",
    "certificate",
}
RISK_DIFF_SIZE_THRESHOLD = 500  # lines changed

# Progress event prefix (for agent-to-agent communication)
PROGRESS_PREFIX = "[KILO_PROGRESS]"


def emit_progress(event: str, **kwargs) -> None:
    """
    Emit a progress event for calling agents (Kilo CLI or Cascade) to parse.

    Events are JSON objects prefixed with PROGRESS_PREFIX for easy filtering.
    Calling agents can grep for this prefix and parse the JSON.

    Example output:
        [KILO_PROGRESS] {"event": "model_start", "model": "claude-opus-4.6", "attempt": 1}
        [KILO_PROGRESS] {"event": "escalation", "from": "claude-opus-4.6", "to": "gemini-3.1-pro"}
        [KILO_PROGRESS] {"event": "complete", "model": "gemini-3.1-pro", "verdict": "PASS"}
    """
    data = {"event": event, "timestamp": datetime.now(UTC).isoformat(), **kwargs}
    print(f"{PROGRESS_PREFIX} {json.dumps(data)}", file=sys.stderr, flush=True)


# =============================================================================
# STRICT SCHEMA VALIDATION (ENFORCED)
# =============================================================================

REVIEW_RESULT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["verdict", "summary", "issues", "plan_coverage"],
    "additionalProperties": False,  # CRITICAL: enforces hard-gated output
    "properties": {
        "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
        "summary": {"type": "string", "minLength": 10, "maxLength": 1000},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "severity",
                    "category",
                    "file",
                    "lines",
                    "why",
                    "fix_hint",
                    "evidence",
                ],
                "additionalProperties": False,  # CRITICAL: no extra fields in issues
                "properties": {
                    "severity": {"type": "string", "enum": ["BLOCKER", "MAJOR", "MINOR"]},
                    "category": {
                        "type": "string",
                        "enum": ["SPEC", "SECURITY", "CONFIG", "EDGE", "FABRIK", "DOCS"],
                    },
                    "file": {"type": "string", "minLength": 1},
                    "lines": {"type": "string", "pattern": "^(L\\d+(-L\\d+)?|N/A)$"},
                    "snippet": {"type": "string"},
                    "why": {"type": "string", "minLength": 10},
                    "fix_hint": {"type": "string", "minLength": 5},
                    "evidence": {
                        "type": "object",
                        "required": ["type"],
                        "additionalProperties": False,
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": [
                                    "diff",
                                    "file_line",
                                    "tool_output",
                                    "missing",
                                    "multi_file",
                                    "external",
                                ],
                            },
                            "ref": {"type": "string", "minLength": 1},
                            "explanation": {"type": "string", "minLength": 10},
                            "supporting_refs": {"type": "array", "items": {"type": "string"}},
                        },
                        "oneOf": [
                            {
                                "properties": {
                                    "type": {"enum": ["diff", "file_line", "tool_output"]}
                                },
                                "required": ["ref"],
                            },
                            {
                                "properties": {
                                    "type": {"enum": ["missing", "multi_file", "external"]}
                                },
                                "required": ["explanation"],
                            },
                        ],
                    },
                },
            },
        },
        "plan_coverage": {
            "type": "array",
            "minItems": 1,  # CRITICAL: at least 1 entry required
            "items": {
                "type": "object",
                "required": ["requirement", "status", "evidence"],
                "additionalProperties": False,
                "properties": {
                    "requirement_id": {"type": "string"},
                    "requirement": {"type": "string", "minLength": 5},
                    "status": {
                        "type": "string",
                        "enum": ["satisfied", "missing", "partial", "n/a"],
                    },
                    "evidence": {"type": "string", "minLength": 5},
                    "notes": {"type": "string"},
                },
            },
        },
        "notes": {"type": "array", "items": {"type": "string"}},
        "stats": {
            "type": "object",
            "properties": {
                "files_reviewed": {"type": "integer", "minimum": 0},
                "lines_changed": {"type": "integer", "minimum": 0},
                "issues_by_severity": {
                    "type": "object",
                    "properties": {
                        "BLOCKER": {"type": "integer", "minimum": 0},
                        "MAJOR": {"type": "integer", "minimum": 0},
                        "MINOR": {"type": "integer", "minimum": 0},
                    },
                },
            },
        },
    },
}

# Compile validator once (performance optimization)
REVIEW_SCHEMA_VALIDATOR = Draft7Validator(REVIEW_RESULT_SCHEMA)


def validate_review_schema(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate reviewer output against strict JSON schema.

    Returns:
        (is_valid, list_of_error_messages)
    """
    errors = []
    for error in REVIEW_SCHEMA_VALIDATOR.iter_errors(data):
        path = ".".join(str(p) for p in error.path) if error.path else "root"
        errors.append(f"{path}: {error.message}")
    return len(errors) == 0, errors


# =============================================================================
# PLAN REQUIREMENT EXTRACTION
# =============================================================================


def extract_plan_requirements(plan_text: str) -> list[dict[str, str]]:
    """
    Extract requirements from Traycer plan.

    Recognizes patterns (priority order):
    1. REQ-1: text (explicit IDs)
    2. 1. text (numbered lists)
    3. - text (bulleted lists, fallback)

    Returns:
        [{"id": "REQ-1", "text": "Requirement description"}, ...]
        Empty list if no structured requirements found
    """
    if not plan_text or len(plan_text.strip()) < 10:
        return []

    requirements = []

    # Pattern 1: Explicit IDs (REQ-1:, REQ-2:, etc.)
    explicit_pattern = re.compile(r"\b(REQ-\d+):\s*(.+?)(?:\n|$)", re.MULTILINE)
    for match in explicit_pattern.finditer(plan_text):
        requirements.append({"id": match.group(1), "text": match.group(2).strip()})

    # If explicit IDs found, use only those
    if requirements:
        return requirements

    # Pattern 2: Numbered lists (1. text, 2. text, etc.)
    numbered_pattern = re.compile(r"^\s*(\d+)\.\s+(.+?)(?:\n|$)", re.MULTILINE)
    for match in numbered_pattern.finditer(plan_text):
        req_text = match.group(2).strip()
        # Filter out very short lines (likely not requirements)
        if len(req_text) > 5:
            requirements.append({"id": f"R{match.group(1)}", "text": req_text})

    # If numbered lists found, use those
    if requirements:
        return requirements

    # Pattern 3: Bulleted lists (- text or * text)
    bullets = []
    bullet_pattern = re.compile(r"^\s*[-*]\s+(.+?)(?:\n|$)", re.MULTILINE)
    for match in bullet_pattern.finditer(plan_text):
        req_text = match.group(1).strip()
        if len(req_text) > 5:
            bullets.append(req_text)

    if bullets:
        for idx, text in enumerate(bullets, 1):
            requirements.append({"id": f"B{idx}", "text": text})

    return requirements


def format_requirements_for_prompt(requirements: list[dict[str, str]]) -> str:
    """
    Format extracted requirements for inclusion in review prompt.

    Returns:
        Formatted string ready for prompt injection
    """
    if not requirements:
        return """[No explicit requirements extracted - plan is freeform]

**Coverage requirement:** Include at least 1 general coverage entry describing what was reviewed."""

    lines = ["**Extracted Requirements (MUST be covered in plan_coverage):**"]
    for req in requirements:
        lines.append(f"  {req['id']}: {req['text']}")

    lines.append("\n**You MUST include each requirement in plan_coverage array.**")

    return "\n".join(lines)


@dataclass
class KiloReviewConfig:
    """Configuration for Kilo code review."""

    # Model selection (None = auto-routed based on diff file paths)
    model: str | None = None

    # Kilo-specific options
    review_agent: str = "ask"  # Agent for review phase (read-only)
    fix_agent: str = "code"  # Agent for fix phase (code editing)
    variant: str = "high"  # Reasoning level: minimal, low, high, max

    # Review scope
    max_files_per_batch: int = MAX_FILES_PER_BATCH
    max_lines_per_file: int = MAX_LINES_PER_FILE
    review_mode: str = "diff_only"  # full, diff_only, staged

    # Iteration control
    max_iterations: int = 3
    min_severity: str = "MAJOR"  # BLOCKER, MAJOR, MINOR
    auto_fix: bool = False  # Default: report-only. Calling agent fixes issues.

    # Session management
    session_id: str | None = None
    persist_session: bool = True
    tracked_review_id: str | None = None  # Stable review cycle ID for scoped sessions

    # Output
    output_dir: Path = field(default_factory=lambda: SESSION_DIR)
    output_format: str = "json"  # json, text, markdown
    verbose: bool = False

    # Plan/spec context
    traycer_plan: str | None = None

    # Verify mode (cheaper workflow: review → manual fix → verify)
    verify_mode: bool = False
    fixes_description: str | None = None

    # Doc-specific review options
    doc_mode: bool = False  # Use lighter doc-only review (auto-detected for .md files)
    skip_categories: set[str] = field(default_factory=set)  # Categories to skip

    # Tiered model selection (cost-aware escalation)
    strategy: str | None = None  # free, economy, standard, premium, critical
    max_cost: float | None = None  # Stop escalation at budget cap
    no_escalate: bool = False  # Stay at initial tier
    verify_high_risk: bool = False  # Auto-verify PASS on high-risk code


@dataclass
class EscalationState:
    """Tracks model escalation within a review session."""

    strategy: str  # free, economy, standard, premium, critical
    current_tier_idx: int = 0  # Index in escalation path
    failed_models: set[str] = field(default_factory=set)  # Models that errored
    session_id: str = ""  # Kilo session ID for cache hits
    spent_cost: float = 0.0  # Accumulated cost
    max_cost: float | None = None  # Budget cap
    risk_level: str = "medium"  # low, medium, high, critical
    verification_performed: bool = False  # Did we verify PASS?
    false_negative_detected: bool = False  # Did cheap model miss issues?

    def get_escalation_path(self) -> list[str]:
        """Get the escalation path for current strategy."""
        return ESCALATION_PATHS.get(self.strategy, ESCALATION_PATHS["economy"])

    def can_escalate(self) -> bool:
        """Check if we can escalate to next tier."""
        path = self.get_escalation_path()
        return self.current_tier_idx < len(path) - 1

    def get_current_tier(self) -> str:
        """Get current tier name."""
        path = self.get_escalation_path()
        if self.current_tier_idx < len(path):
            return path[self.current_tier_idx]
        return path[-1] if path else "Economy"


@dataclass
class ReviewIssue:
    """A single issue found during review."""

    severity: str  # BLOCKER, MAJOR, MINOR
    category: str  # SPEC, SECURITY, CONFIG, EDGE, DOCS
    file: str
    lines: str
    why: str
    fix_hint: str
    snippet: str | None = None
    evidence: dict[str, Any] | None = None  # NEW: structured evidence object

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewResult:
    """Result of a Kilo review call."""

    verdict: str  # PASS, FAIL
    summary: str
    issues: list[ReviewIssue]
    notes: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    plan_coverage: list[dict[str, Any]] = field(default_factory=list)  # NEW: required plan coverage
    session_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    raw_output: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


@dataclass
class FixResult:
    """Result of a Kilo fix call."""

    status: str  # SUCCESS, PARTIAL, FAILED
    total_fixed: int
    fixes_applied: list[dict[str, Any]]
    total_skipped: int = 0
    needs_manual: list[dict[str, Any]] = field(default_factory=list)
    diff: str | None = None
    session_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0


@dataclass
class UsageStats:
    """Tracks token usage and costs for a session."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0

    # Review-specific stats
    review_calls: int = 0
    review_input_tokens: int = 0
    review_output_tokens: int = 0
    review_cost_usd: float = 0.0

    # Fix-specific stats
    fix_calls: int = 0
    fix_input_tokens: int = 0
    fix_output_tokens: int = 0
    fix_cost_usd: float = 0.0

    def add_review(self, result: ReviewResult) -> None:
        # Update totals
        self.input_tokens += result.input_tokens
        self.output_tokens += result.output_tokens
        self.total_tokens += result.input_tokens + result.output_tokens
        self.cost_usd += result.cost
        # Update review-specific
        self.review_calls += 1
        self.review_input_tokens += result.input_tokens
        self.review_output_tokens += result.output_tokens
        self.review_cost_usd += result.cost

    def add_fix(self, result: FixResult) -> None:
        # Update totals
        self.input_tokens += result.input_tokens
        self.output_tokens += result.output_tokens
        self.total_tokens += result.input_tokens + result.output_tokens
        self.cost_usd += result.cost
        # Update fix-specific
        self.fix_calls += 1
        self.fix_input_tokens += result.input_tokens
        self.fix_output_tokens += result.output_tokens
        self.fix_cost_usd += result.cost

    def add_review_call(self, usage: dict[str, Any]) -> None:
        """Add usage from a raw Kilo response dict."""
        input_t = usage.get("input_tokens", 0)
        output_t = usage.get("output_tokens", 0)
        cost = usage.get("cost", 0.0)

        self.input_tokens += input_t
        self.output_tokens += output_t
        self.total_tokens += input_t + output_t
        self.cost_usd += cost

        self.review_calls += 1
        self.review_input_tokens += input_t
        self.review_output_tokens += output_t
        self.review_cost_usd += cost


@dataclass
class SessionState:
    """Persistent session state for Cascade chat continuity."""

    session_id: str
    created_at: str
    last_used_at: str
    model: str
    variant: str
    files_reviewed: list[str]
    iteration: int
    status: str  # in_progress, completed, failed
    usage: dict[str, Any]
    last_verdict: str | None = None
    last_issues: list[dict[str, Any]] = field(default_factory=list)

    # Scoped session resolution fields
    project_root: str = ""
    git_branch: str = ""
    tracked_review_id: str | None = None


@dataclass
class FinalReport:
    """Final report from the review loop."""

    status: str  # CLEAN, NEEDS_FIX, NEEDS_MANUAL, MAX_ITERATIONS, ERROR
    verdict: str  # PASS, FAIL
    iterations: int
    files_reviewed: list[str]
    all_issues: list[dict[str, Any]]
    all_fixes: list[dict[str, Any]]
    remaining_issues: list[dict[str, Any]]
    usage: dict[str, Any]
    session_id: str
    summary: str


def get_default_model() -> str:
    """Get validated default model from env var or kilo/auto default."""
    import re

    model = os.getenv("KILO_REVIEW_MODEL", _DEFAULT_MODEL)

    # Special case: kilo/auto is always valid
    if model == "kilo/auto":
        return model
    # Validate model format to prevent path traversal/injection
    # Allow: letters, numbers, slashes, underscores, hyphens, dots, colons (for :free suffix)
    if not re.match(r"^kilo/[a-zA-Z0-9/_.\-:]+$", model):
        print(
            f"Warning: Invalid KILO_REVIEW_MODEL format '{model}', using kilo/auto", file=sys.stderr
        )
        return _DEFAULT_MODEL
    return model


DEFAULT_MODEL = get_default_model()

# Code file extensions to review
CODE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",  # Python, TypeScript, JavaScript
    ".sh",
    ".bash",  # Shell scripts
    ".yaml",
    ".yml",
    ".toml",
    ".json",  # Config files
    ".md",  # Markdown (for docs review)
    ".sql",  # SQL files
    ".html",
    ".css",
    ".scss",  # Web files
}

# Directories to ignore
IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".droid",
    ".factory",
    "dist",
    "build",
    ".next",
}

# Max diff size (characters)
MAX_DIFF_SIZE = 15_000  # 15KB

# Session state directory (configurable via env var)
SESSION_DIR = Path(os.getenv("KILO_SESSION_DIR", ".droid/reviews"))

# Model cache file and refresh tracking
MODEL_CACHE_FILE = Path(os.getenv("KILO_MODEL_CACHE", ".droid/kilo_models_cache.json"))
MODEL_CACHE_REFRESH_FILE = Path(".droid/.kilo_cache_last_refresh")

# Retry configuration for transient failures
try:
    MAX_RETRIES = max(1, int(os.getenv("KILO_MAX_RETRIES", "3")))  # Max retry attempts (min 1)
except ValueError:
    print(
        f"Warning: Invalid KILO_MAX_RETRIES value"
        f" '{os.getenv('KILO_MAX_RETRIES')}', using default 3",
        file=sys.stderr,
    )
    MAX_RETRIES = 3
RETRYABLE_EXIT_CODES = {124, 503}  # Timeout (124) and Service Unavailable (503)

# Model successor mapping for deprecated models
MODEL_SUCCESSORS = {
    "kilo/anthropic/claude-sonnet-4.5": "kilo/anthropic/claude-sonnet-4.6",
    "kilo/anthropic/claude-opus-4.5": "kilo/anthropic/claude-opus-4.6",
    "kilo/openai/gpt-5.1-codex": "kilo/openai/gpt-5.2-codex",
    "kilo/openai/gpt-4o": "kilo/openai/gpt-5",
}

# Models that support reasoning (required for code review)
# Now checked via has_reasoning() from db_models - queries DB directly

# =============================================================================
# BACKUP MODELS & FALLBACK CHAIN
# =============================================================================
#
# Primary model: Claude Opus 4.6 (best reasoning, used for review AND fix)
# Fallback chain is tried IN ORDER when a model is unavailable or errors.
#
# TESTED MODELS (2026-02-28):
# ┌─────────────────────────────────────┬───────────┬────────────┬─────────────────────┐
# │ Model                               │ Cost/10M  │ Status     │ Notes               │
# ├─────────────────────────────────────┼───────────┼────────────┼─────────────────────┤
# │ Claude Opus 4.6                     │ $50/$250  │ ✅ Primary │ Best reasoning      │
# │ Claude Sonnet 4.6                   │ $30/$150  │ ✅ Backup  │ Cheaper Anthropic   │
# │ GPT-5.3-Codex                       │ $12.5/$50 │ ✅ NEW     │ Opus-like quality   │
# │ GPT-5.3-Codex-Spark                 │ $6.25/$25 │ ✅ NEW     │ Fast iteration      │
# │ GPT-5.2-Codex                       │ $12.5/$50 │ ✅ Backup  │ OpenAI alternative  │
# │ Gemini 3.1 Pro                      │ $12.5/$50 │ ✅ Backup  │ Heavy reasoning     │
# │ Gemini 3 Flash                      │ $0.75/$3  │ ✅ Backup  │ Speed fallback      │
# │ O3-Mini                             │ $10/$40   │ ✅ NEW     │ Fast reasoning      │
# │ Gemini 2.5 Pro                      │ $15/$60   │ ✅ NEW     │ Next-gen Google     │
# └─────────────────────────────────────┴───────────┴────────────┴─────────────────────┘
#
# FALLBACK ORDER:
# 1. Claude Opus 4.6      - Primary (best quality, $50/10M in, $250/10M out)
# 2. GPT-5.3-Codex        - Opus-like quality ($12.50/10M in, $50/10M out)
# 3. Claude Sonnet 4.6    - Cheaper Anthropic ($30/10M in, $150/10M out)
# 4. GPT-5.2-Codex        - OpenAI alternative ($12.50/10M in, $50/10M out)
# 5. Gemini 3.1 Pro       - Heavy reasoning ($12.50/10M in, $50/10M out)
# 6. GPT-5.3-Codex-Spark  - Fast iteration ($6.25/10M in, $25/10M out)
# 7. O3-Mini              - Fast reasoning ($10/10M in, $40/10M out)
# 8. Gemini 2.5 Pro       - Next-gen Google ($15/10M in, $60/10M out)
# 9. Gemini 3 Flash       - Speed fallback ($0.75/10M in, $3/10M out)
#
# CLI override: --model <model_name> (uses exactly that model, no fallback)

BACKUP_MODELS = {
    # Model ID: (input_cost_per_10M, output_cost_per_10M, description)
    "kilo/anthropic/claude-opus-4.6": (50.0, 250.0, "Primary - best reasoning"),
    "kilo/openai/gpt-5.3-codex": (12.50, 50.0, "Opus-like quality"),
    "kilo/anthropic/claude-sonnet-4.6": (30.0, 150.0, "Cheaper Anthropic"),
    "kilo/openai/gpt-5.2-codex": (12.50, 50.0, "OpenAI alternative"),
    "kilo/google/gemini-3.1-pro-preview": (12.50, 50.0, "Heavy reasoning"),
    "kilo/openai/gpt-5.3-codex-spark": (6.25, 25.0, "Fast iteration"),
    "kilo/openai/o3-mini": (10.0, 40.0, "Fast reasoning"),
    "kilo/google/gemini-2.5-pro": (15.0, 60.0, "Next-gen Google"),
    "kilo/google/gemini-3-flash-preview": (0.75, 3.0, "Speed fallback"),
}

# Fallback chain cache (loaded from DB once per process)
_FALLBACK_CHAIN_CACHE: list[str] | None = None


def _load_fallback_chain() -> list[str]:
    """Load fallback chain from DB (reviewing role, priority order)."""
    global _FALLBACK_CHAIN_CACHE
    if _FALLBACK_CHAIN_CACHE is None:
        _FALLBACK_CHAIN_CACHE = get_fallback_chain("reviewing")
    return _FALLBACK_CHAIN_CACHE


# =============================================================================
# TIERED MODEL SELECTION (Cost-Aware Escalation)
# =============================================================================
#
# Strategy: Start cheap, escalate on failure
# Risk assessment determines starting tier, escalation path handles quality
#
# Usage:
#   --strategy free      Start at Free tier ($0)
#   --strategy economy   Start at Economy tier (~$0.02/M)
#   --strategy standard  Start at Balanced tier (~$0.5/M) [default for high-risk]
#   --strategy premium   Start at Strong tier (~$3/M)
#   --strategy critical  Start at Prime tier (~$5/M)
#   --max-cost 1.00      Stop escalating at budget cap
#   --no-escalate        Stay at initial tier

# =============================================================================
# DB-DRIVEN TIER MODELS (from kilo_agents.db)
# =============================================================================
# Models loaded from agent_roles table for 'reviewing' role.
# Source of truth: scripts/kilo-benchmarks/kilo_agents.db
# Blocked models are automatically excluded.
#
# VARIANT RECOMMENDATIONS (thinking depth, not model-specific):
#   - minimal: Skip for reviews (too shallow)
#   - low: Quick lint checks only (~10s, lowest cost)
#   - high: Standard reviews (~20s, best quality/cost) [DEFAULT]
#   - max: Complex/security reviews (~40s, highest quality)
#

# Cache for DB-loaded tier models (loaded once per process)
_TIER_MODELS_CACHE: dict[str, list[str]] | None = None


def _load_tier_models() -> dict[str, list[str]]:
    """Load tier models from DB (cached)."""
    global _TIER_MODELS_CACHE
    if _TIER_MODELS_CACHE is None:
        _TIER_MODELS_CACHE = get_tier_models("reviewing")
    return _TIER_MODELS_CACHE


# Variant recommendations per risk level (auto-selected)
VARIANT_BY_RISK = {
    "low": "low",  # Fast lint checks
    "medium": "high",  # Standard reviews (default)
    "high": "high",  # Security/complex reviews
    "critical": "max",  # Mission-critical code
}


def get_auto_variant(risk_level: str, user_variant: str | None = None) -> str:
    """Get appropriate variant based on risk level.

    User-specified variant takes precedence.
    """
    if user_variant and user_variant != "high":  # high is default, so auto-select
        return user_variant
    return VARIANT_BY_RISK.get(risk_level, "high")


# Escalation paths: strategy → list of tiers to try
# Uses tier names for compatibility, maps to DB priorities internally
ESCALATION_PATHS = {
    "free": ["Free", "Economy", "Balanced"],  # Start cheap
    "economy": ["Economy", "Balanced", "Strong"],  # Start economy
    "standard": ["Balanced", "Strong", "Prime"],  # Start balanced
    "premium": ["Strong", "Prime"],  # Start strong
    "critical": ["Prime"],  # Only best
}

RISK_TO_STRATEGY = {
    "low": "free",
    "medium": "economy",
    "high": "standard",
    "critical": "premium",
}

# Tier cost estimates (for budget checks)
TIER_ESTIMATED_COST = {
    "Free": 0.0,
    "Economy": 0.02,
    "Balanced": 0.01,
    "Strong": 0.05,
    "Prime": 0.50,
}


def get_tier_model(tier: str, failed_models: set[str] | None = None) -> str | None:
    """Get first available model from tier, skipping failed ones.

    Models are loaded from DB (reviewing role assignments).
    Blocked models are already excluded by DB query.
    """
    if failed_models is None:
        failed_models = set()

    tier_models = _load_tier_models()
    for model in tier_models.get(tier, []):
        if model not in failed_models and not is_model_blocked(model):
            return model
    return None


def get_escalation_model(
    strategy: str,
    current_tier_idx: int,
    failed_models: set[str] | None = None,
    max_cost: float | None = None,
) -> tuple[str | None, str, int]:
    """
    Get next model in escalation path.

    Returns: (model_id, tier_name, new_tier_idx) or (None, "", -1) if exhausted
    """
    path = ESCALATION_PATHS.get(strategy, ESCALATION_PATHS["economy"])

    for idx in range(current_tier_idx, len(path)):
        tier = path[idx]
        # Check cost cap
        if max_cost is not None and TIER_ESTIMATED_COST.get(tier, 0) > max_cost:
            continue
        model = get_tier_model(tier, failed_models)
        if model:
            return model, tier, idx
    return None, "", -1


# =============================================================================
# DIFF-SCOPED MODEL ROUTING (Cost-Aware)
# =============================================================================
#
# Default model: Gemini 3 Flash (cheap)
# Escalate to Opus 4.6: Only if diff touches high-risk paths
#
# Routing is based ONLY on diff file paths - no content inspection.
# Extend via env var: KILO_HIGH_RISK_PATHS=custom/,extra/ (added to defaults)

# High-risk directory prefixes (escalate to Opus if diff touches these)
HIGH_RISK_DIR_PREFIXES = [
    # Backend runtime
    "src/",
    "backend/",
    "server/",
    "api/",
    "app/",
    # Auth & security
    "auth/",
    "security/",
    "session/",
    "middleware/",
    "permissions/",
    # Database
    "migrations/",
    "alembic/",
    "prisma/",
    "db/",
    "database/",
    "models/",
    # Docker & infra
    "docker/",
    "infra/",
    "infrastructure/",
    ".github/",
    "ci/",
    # WordPress
    "wp-content/plugins/",
    "wp-content/themes/",
    # Scripts (runtime logic)
    "scripts/",
]

# High-risk filenames (exact match, case-insensitive)
HIGH_RISK_FILENAMES = [
    # Dependency graph
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
    # Docker build surface
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yaml",  # Per spec: compose.yaml is HIGH risk
    "compose.yml",
    # Env surface
    ".env",
    ".env.production",
    ".env.local",
    # Chrome extension (privileged)
    "manifest.json",
    "background.js",
    "service_worker.js",
]

# Pre-computed lowercase set for O(1) filename lookups
_HIGH_RISK_FILENAMES_LOWER = {f.lower() for f in HIGH_RISK_FILENAMES}

# Flag to track if high-risk paths have been initialized from env
_high_risk_paths_initialized = False


def _init_high_risk_paths(*, verbose: bool = False) -> None:
    """
    Extend high-risk paths from KILO_HIGH_RISK_PATHS env var.

    Called from main() (with verbose=True) and review_loop() (with verbose=False)
    to support both CLI and programmatic flows without import-time side effects.

    Args:
        verbose: If True, print routing message to stderr. Only enabled for CLI flow.

    Idempotent: safe to call multiple times.
    """
    global _high_risk_paths_initialized
    if _high_risk_paths_initialized:
        return
    _high_risk_paths_initialized = True

    env_high_risk = os.getenv("KILO_HIGH_RISK_PATHS")
    if env_high_risk:
        extra_paths = [p.strip() for p in env_high_risk.split(",") if p.strip()]
        HIGH_RISK_DIR_PREFIXES.extend(extra_paths)
        if verbose:
            print(
                f"[ROUTING] Extended high-risk paths with {len(extra_paths)}"
                " entries from KILO_HIGH_RISK_PATHS",
                file=sys.stderr,
            )


# Default models for routing
MODEL_CHEAP = "kilo/google/gemini-3-flash-preview"
MODEL_EXPENSIVE = "kilo/anthropic/claude-opus-4.6"

# Legacy: Security-sensitive patterns for max variant (used by should_use_max_variant)
SECURITY_PATTERNS = {
    "auth",
    "login",
    "password",
    "token",
    "jwt",
    "oauth",
    "session",
    "permission",
    "credential",
    "secret",
    "encrypt",
    "decrypt",
}

# Hard cap for iterations (even with auto-continue)
HARD_MAX_ITERATIONS = 10

# Cumulative usage tracking file
USAGE_LOG_FILE = Path(os.getenv("KILO_USAGE_LOG", ".droid/kilo_usage.jsonl"))
METRICS_FILE = Path(os.getenv("KILO_METRICS_FILE", ".droid/kilo_metrics.jsonl"))
REVIEW_SESSIONS_FILE = Path(os.getenv("KILO_SESSIONS_FILE", ".droid/review_sessions.jsonl"))
AUDIT_LOG_FILE = Path(os.getenv("KILO_AUDIT_LOG", ".droid/review_audits.jsonl"))

# Audit sampling rate (per spec: 5% random sampling of PASS verdicts)
AUDIT_SAMPLE_RATE = float(os.getenv("KILO_AUDIT_SAMPLE_RATE", "0.05"))

# Project root for path validation (will be set to git root or CWD at runtime)
# This is initialized lazily to avoid subprocess calls at import time
_PROJECT_ROOT: Path | None = None


def _is_valid_session_id(session_id: str) -> bool:
    """Validate session_id format to prevent path traversal.

    Accepts alphanumeric, underscores, and hyphens.
    Rejects dots (path traversal risk), path separators, and overly long values.
    """
    import re

    # No dots allowed - prevents .. path traversal
    return bool(re.match(r"^[a-zA-Z0-9_-]{1,128}$", session_id))


def should_escalate_to_opus(diff_files: list[str] | list[Path]) -> tuple[bool, str]:
    """
    Determine if review should use expensive model (Opus) based on diff file paths.

    Returns (should_escalate, reason)

    Escalation rules (diff-scoped, no content inspection):
    1. If ANY file path matches HIGH_RISK_DIR_PREFIXES → escalate
    2. If ANY filename matches HIGH_RISK_FILENAMES → escalate
    3. Otherwise → use cheap model (Gemini Flash)

    This is deterministic and evaluated BEFORE review starts.
    """
    for fp in diff_files:
        # Normalize path: forward slashes, lowercase
        normalized = str(fp).replace("\\", "/").lower()
        filename = Path(fp).name.lower()

        # Check filename match (exact, case-insensitive, pre-computed set)
        if filename in _HIGH_RISK_FILENAMES_LOWER:
            return True, f"high_risk_file:{filename}"

        # Check directory prefix match (path-component boundary, not substring)
        # Prepend '/' so prefixes like "src/" match at the start or after a component
        normalized_with_slash = "/" + normalized
        for prefix in HIGH_RISK_DIR_PREFIXES:
            prefix_lower = prefix.lower()
            if normalized.startswith(prefix_lower) or ("/" + prefix_lower) in normalized_with_slash:
                return True, f"high_risk_dir:{prefix}"

    return False, "low_risk"


def select_model_for_diff(
    diff_files: list[str] | list[Path],
    user_model: str | None = None,
) -> tuple[str, bool, str]:
    """
    Intelligent model routing based on diff characteristics.

    Strategy:
    - AUTO (kilo/auto) for automatic mode-based routing (recommended)
      - Opus 4.6 for review mode (quality critical)
      - Sonnet 4.5 for code mode (implementation)
    - Gemini Pro Thinking for complex diffs (high-stakes changes, reasoning needed)
    - Sonnet for standard code review (balanced cost/quality)
    - Flash for simple documentation changes (docs, comments, minimal risk)

    Escalation triggers:
    - High-risk directories (scripts/, src/fabrik/, .windsurf/)
    - Large diffs (>500 lines changed)
    - Security-sensitive file types (.sh, .py in scripts/)

    Note: If KILO_REVIEW_MODEL=kilo/auto, routing is handled by Kilo Code automatically.
    """
    if user_model:
        return user_model, False, "user_override"

    escalate, reason = should_escalate_to_opus(diff_files)
    if escalate:
        return MODEL_EXPENSIVE, True, reason
    return MODEL_CHEAP, False, reason


def log_routing_decision(
    diff_files: list[str] | list[Path],
    selected_model: str,
    escalated: bool,
    reason: str,
) -> None:
    """Log model routing decision to stderr."""
    print(f"[ROUTING] Diff files: {len(diff_files)}", file=sys.stderr)
    print(f"[ROUTING] Escalated to Opus: {escalated}", file=sys.stderr)
    print(f"[ROUTING] Reason: {reason}", file=sys.stderr)
    print(f"[ROUTING] Selected model: {selected_model}", file=sys.stderr)


def _scan_file_for_critical_keywords(filepath: Path, max_size: int = 100_000) -> bool:
    """
    Scan file contents for critical keywords (password, token, key, secret).

    Per spec: content-based keyword detection elevates risk to CRITICAL.
    Only scans text files under max_size bytes to avoid memory issues.
    """
    content_keywords = ["password", "token", "secret", "api_key", "apikey", "private_key"]

    try:
        if not filepath.exists() or not filepath.is_file():
            return False
        if filepath.stat().st_size > max_size:
            return False  # Skip large files

        # Read file content
        content = filepath.read_text(encoding="utf-8", errors="ignore").lower()

        # Check for keywords that look like actual secrets (not just variable names)
        # Pattern: keyword followed by = or : and a quoted/unquoted value
        # Content is already lowercased, so use lowercase keywords
        for kw in content_keywords:
            # Look for assignment patterns like: password = "...", secret: "..."
            if re.search(rf'{kw}\s*[=:]\s*["\'][^"\']+["\']', content):
                return True
            # Look for environment variable patterns like: password=value (case-insensitive)
            if re.search(rf"^{kw}\s*=\s*\S+", content, re.MULTILINE):
                return True

    except (OSError, UnicodeDecodeError):
        pass  # Skip files we can't read

    return False


def determine_risk_level(
    diff_files: list[str] | list[Path],
    total_diff_lines: int | None = None,
) -> str:
    """
    Determine risk level based on file paths, keywords, diff size, and content.

    Risk levels (per spec):
    - CRITICAL: auth/, security/, payment/, crypto/, secrets/, OR content contains secrets
    - HIGH: src/, scripts/, migrations/, OR diff > 400 lines
    - MEDIUM: normal code
    - LOW: docs only
    """
    has_high_risk = False
    has_critical = False

    # Critical keywords in path
    critical_path_keywords = [
        "auth/",
        "security/",
        "payment",
        "secret",
        "crypt",
        "token",
        "key/",
        "password",
    ]

    for fp in diff_files:
        filepath = Path(fp)
        normalized = str(fp).replace("\\", "/").lower()
        filename = filepath.name.lower()

        # Critical: security, auth, payments, secrets in path
        if any(kw in normalized for kw in critical_path_keywords):
            has_critical = True
            break  # No need to check more

        # Critical: content contains secret patterns (per spec)
        if _scan_file_for_critical_keywords(filepath):
            has_critical = True
            break

        # High: source code, scripts, configs, or sensitive files
        if (
            any(normalized.startswith(p.lower()) for p in HIGH_RISK_DIR_PREFIXES)
            or filename in _HIGH_RISK_FILENAMES_LOWER
        ):
            has_high_risk = True

    # Large diffs are high risk (per spec: > 400 lines)
    if total_diff_lines is not None and total_diff_lines > 400:
        has_high_risk = True

    if has_critical:
        return "critical"
    if has_high_risk:
        return "high"
    # Check if all docs
    if is_doc_only_review(diff_files):
        return "low"
    return "medium"


def get_next_model_from_state(state: EscalationState) -> tuple[str | None, str]:
    """
    Get next available model from current escalation state.

    Returns: (model_id, tier_name) or (None, "") if exhausted
    """
    path = state.get_escalation_path()

    # Try tiers starting from current index
    for idx in range(state.current_tier_idx, len(path)):
        tier = path[idx]
        # Check cost cap
        tier_cost = TIER_ESTIMATED_COST.get(tier, 0)
        if state.max_cost is not None and tier_cost > state.max_cost:
            continue
        # Get first available model from tier
        model = get_tier_model(tier, state.failed_models)
        if model:
            state.current_tier_idx = idx
            return model, tier

    return None, ""


def should_verify_pass(risk_level: str, tier: str, findings_count: int) -> bool:
    """
    Determine if a PASS verdict needs verification with stronger model.

    Per spec: "Zero issues on critical code is a red flag"
    HIGH risk starts at Balanced, verify if below Strong.
    """
    if findings_count > 0:
        return False  # Found issues, no verification needed

    if risk_level == "critical" and tier != "Prime":
        return True  # Always verify critical code

    # HIGH risk: verify if tier is below Strong (Free, Economy, or Balanced)
    return risk_level == "high" and tier in ("Free", "Economy", "Balanced")


def select_model_with_strategy(
    diff_files: list[str] | list[Path],
    user_model: str | None,
    strategy: str | None,
    max_cost: float | None,
    total_diff_lines: int | None = None,
) -> tuple[str, str, str, int, str]:
    """
    Select model using tiered escalation strategy.

    Returns: (model_id, tier_name, strategy_used, tier_idx, risk_level)
    """
    # User override bypasses strategy
    if user_model:
        return user_model, "user", "override", 0, "unknown"

    # Determine risk level
    risk_level = determine_risk_level(diff_files, total_diff_lines)

    # Determine strategy from risk level if not specified
    if not strategy:
        strategy = RISK_TO_STRATEGY.get(risk_level, "economy")

    # Get initial model from strategy
    strategy_used = strategy
    model, tier, idx = get_escalation_model(strategy, 0, None, max_cost)
    if not model:
        # Fallback to economy respecting max_cost (per spec: graceful degradation)
        strategy_used = "economy"
        model, tier, idx = get_escalation_model("economy", 0, None, max_cost)
    if not model:
        # Final fallback to free tier if budget exhausted
        strategy_used = "free"
        model, tier, idx = get_escalation_model("free", 0, None, max_cost)

    return model or MODEL_CHEAP, tier or "Free", strategy_used, idx, risk_level


def log_tiered_routing(
    diff_files: list[str] | list[Path],
    model: str,
    tier: str,
    strategy: str,
    risk_level: str,
) -> None:
    """Log tiered model routing decision."""
    print(f"[ROUTING] Files: {len(diff_files)} | Risk: {risk_level}", file=sys.stderr)
    print(f"[ROUTING] Strategy: {strategy} | Tier: {tier}", file=sys.stderr)
    print(f"[ROUTING] Model: {model}", file=sys.stderr)


def is_doc_only_review(files: list[Path] | list[str]) -> bool:
    """Check if ALL files are documentation files (.md, .rst, etc.)."""
    if not files:
        return False
    for f in files:
        ext = Path(f).suffix.lower()
        if ext not in DOC_EXTENSIONS:
            return False
    return True


def get_max_iterations_for_files(files: list[Path] | list[str], user_max: int | None = None) -> int:
    """Get appropriate max iterations based on file types.

    Docs: 2 iterations max (lighter review)
    Code: 5 iterations max (thorough review)
    Mixed: Use code limit
    User override: Respected if provided
    """
    if user_max is not None:
        return user_max

    if is_doc_only_review(files):
        return MAX_ITERATIONS_DOCS
    return MAX_ITERATIONS_CODE


def parse_skip_categories(skip_arg: str | None) -> set[str]:
    """Parse --skip-categories argument into a set of valid categories."""
    if not skip_arg:
        return set()

    categories = set()
    for cat in skip_arg.upper().split(","):
        cat = cat.strip()
        if cat in VALID_CATEGORIES:
            categories.add(cat)
        else:
            print(
                f"[WARNING] Invalid category '{cat}', ignoring. Valid: {VALID_CATEGORIES}",
                file=sys.stderr,
            )
    return categories


def get_issue_fingerprint(issue: dict[str, Any]) -> str:
    """Generate a fingerprint for an issue to detect repeated false positives."""
    # Fingerprint = file + lines + category + first 50 chars of why
    file = issue.get("file", "")
    lines = issue.get("lines", "")
    category = issue.get("category", "")
    why = issue.get("why", "")[:50]
    return f"{file}:{lines}:{category}:{why}"


def filter_repeated_issues(
    current_issues: list[dict[str, Any]],
    issue_history: dict[str, int],
    threshold: int = 2,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Filter out issues that have been reported repeatedly (likely false positives).

    Args:
        current_issues: Issues from current review
        issue_history: Map of fingerprint -> count
        threshold: Number of times an issue must appear to be considered a false positive

    Returns:
        (filtered_issues, false_positives)
    """
    filtered = []
    false_positives = []

    for issue in current_issues:
        fp = get_issue_fingerprint(issue)
        count = issue_history.get(fp, 0) + 1
        issue_history[fp] = count

        if count >= threshold:
            issue["_repeated_count"] = count
            false_positives.append(issue)
        else:
            filtered.append(issue)

    return filtered, false_positives


def get_project_root() -> Path:
    """Get project root (git root or CWD)."""
    global _PROJECT_ROOT
    if _PROJECT_ROOT is None:
        try:
            # Validate git executable path
            git_path = shutil.which("git")
            if not git_path or not os.path.isabs(git_path):
                raise RuntimeError("Invalid git executable path")

            result = subprocess.run(
                [git_path, "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            _PROJECT_ROOT = Path(result.stdout.strip())
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, RuntimeError):
            _PROJECT_ROOT = Path.cwd()
    return _PROJECT_ROOT


def get_current_git_branch() -> str:
    """Get current git branch name."""
    try:
        git_path = shutil.which("git")
        if not git_path:
            return "unknown"
        result = subprocess.run(
            [git_path, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def issue_key(tracked_review_id: str, issue: dict[str, Any]) -> str:
    """Generate stable key for issue tracking across iterations."""
    base = "|".join(
        [
            tracked_review_id,
            issue.get("file", ""),
            issue.get("lines", ""),
            issue.get("category", ""),
            issue.get("why", "")[:120],
        ]
    )
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def get_issue_state_file(tracked_review_id: str) -> Path:
    """Get path to issue state file for a review cycle."""
    return Path(".droid/reviews") / f"{tracked_review_id}_issues.json"


def load_issue_state(tracked_review_id: str) -> dict[str, Any]:
    """Load issue state for a review cycle."""
    state_file = get_issue_state_file(tracked_review_id)
    if not state_file.exists():
        return {"tracked_review_id": tracked_review_id, "issues": {}}

    try:
        return json.loads(state_file.read_text())
    except Exception:
        return {"tracked_review_id": tracked_review_id, "issues": {}}


def save_issue_state(tracked_review_id: str, state: dict[str, Any]) -> None:
    """Save issue state for a review cycle."""
    state_file = get_issue_state_file(tracked_review_id)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2))


def update_issue_state(
    tracked_review_id: str,
    current_issues: list[dict[str, Any]],
    iteration: int,
    allow_auto_fix_close: bool = False,
) -> None:
    """
    Update issue state after a review iteration.

    Args:
        tracked_review_id: Review cycle ID
        current_issues: Issues found in this iteration
        iteration: Current iteration number
        allow_auto_fix_close: If True, mark unseen issues as fixed
            (safe only for full-scope reviews)
    """
    state = load_issue_state(tracked_review_id)
    issues = state.get("issues", {})

    # Track seen issues in this iteration
    seen_keys = set()

    for issue in current_issues:
        key = issue_key(tracked_review_id, issue)
        seen_keys.add(key)

        if key in issues:
            # Update existing issue
            issues[key]["last_seen_iteration"] = iteration
        else:
            # New issue
            issues[key] = {
                "status": "open",
                "file": issue.get("file", ""),
                "lines": issue.get("lines", ""),
                "category": issue.get("category", ""),
                "severity": issue.get("severity", ""),
                "why": issue.get("why", ""),
                "fix_hint": issue.get("fix_hint", ""),
                "first_seen_iteration": iteration,
                "last_seen_iteration": iteration,
            }

    # Mark previously open issues as fixed if not seen (only when safe)
    if allow_auto_fix_close:
        for key, issue_data in issues.items():
            if issue_data["status"] == "open" and key not in seen_keys:
                issue_data["status"] = "fixed"

    state["issues"] = issues
    save_issue_state(tracked_review_id, state)


def get_open_issues(tracked_review_id: str) -> list[dict[str, Any]]:
    """Get only open issues for a review cycle."""
    state = load_issue_state(tracked_review_id)
    issues = state.get("issues", {})

    open_issues = []
    for issue_data in issues.values():
        if issue_data["status"] == "open":
            open_issues.append(issue_data)

    return open_issues


def should_refresh_model_cache() -> bool:
    """Check if model cache should be refreshed (once per day)."""
    if not MODEL_CACHE_REFRESH_FILE.exists():
        return True
    try:
        last_refresh = MODEL_CACHE_REFRESH_FILE.read_text().strip()
        last_date = datetime.fromisoformat(last_refresh).date()
        return last_date < datetime.now().date()
    except (ValueError, OSError):
        return True


def refresh_model_cache_if_needed() -> None:
    """Refresh model cache on first run of the day."""
    if not should_refresh_model_cache():
        return

    kilo_path = find_kilo_executable()
    if not kilo_path:
        return  # Can't refresh without kilo

    try:
        print("[KILO] Refreshing model cache (daily)...", file=sys.stderr)
        subprocess.run(
            [kilo_path, "models", "--refresh"],
            capture_output=True,
            text=True,
            timeout=30,
            shell=False,  # Never use shell=True to prevent command injection
        )

        # Mark as refreshed today
        MODEL_CACHE_REFRESH_FILE.parent.mkdir(parents=True, exist_ok=True)
        MODEL_CACHE_REFRESH_FILE.write_text(datetime.now().isoformat())
        print("[KILO] Model cache refreshed.", file=sys.stderr)
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"[KILO] Cache refresh failed: {e}", file=sys.stderr)


def check_model_deprecation(model: str) -> str:
    """Check if model is deprecated and return successor if available."""
    if model in MODEL_SUCCESSORS:
        successor = MODEL_SUCCESSORS[model]
        print(f"[KILO] Model {model} has successor: {successor}", file=sys.stderr)
        return successor
    return model


def check_model_availability(model: str) -> bool:
    """Check if model exists in Kilo CLI."""
    kilo_path = find_kilo_executable()
    if not kilo_path:
        return True  # Assume available if we can't check

    try:
        result = subprocess.run(
            [kilo_path, "models", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return True  # Assume available on error

        models_data = json.loads(result.stdout)
        model_ids = [m.get("id", "") for m in models_data if isinstance(m, dict)]
        # Check both with and without kilo/ prefix
        return (
            model in model_ids
            or f"kilo/{model}" in model_ids
            or model.replace("kilo/", "") in model_ids
        )
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return True  # Assume available on error


@dataclass
class ReviewSession:
    """Track review session metrics for analysis."""

    session_id: str
    files: list[str]
    file_types: list[str]
    model: str
    iterations: int
    total_cost: float = 0.0
    verdict: str = "PENDING"
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None

    def save(self) -> None:
        """Save session metrics to review_sessions.jsonl."""
        REVIEW_SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.completed_at = datetime.now(UTC).isoformat()
        with open(REVIEW_SESSIONS_FILE, "a") as f:
            json.dump(asdict(self), f)
            f.write("\n")


def run_stats_command(by_filetype: bool = False, by_model: bool = False, days: int = 30) -> None:
    """Show usage statistics from review sessions."""
    from collections import defaultdict
    from datetime import timedelta

    cutoff = datetime.now(UTC) - timedelta(days=days)

    # Load sessions
    sessions: list[dict[str, Any]] = []
    if REVIEW_SESSIONS_FILE.exists():
        with open(REVIEW_SESSIONS_FILE) as f:
            for line in f:
                try:
                    session = json.loads(line.strip())
                    started_str = session.get("started_at", "")
                    if not started_str:
                        continue
                    started = datetime.fromisoformat(started_str)
                    if started >= cutoff:
                        sessions.append(session)
                except (json.JSONDecodeError, ValueError):
                    continue

    # Also load from usage log
    if USAGE_LOG_FILE.exists():
        with open(USAGE_LOG_FILE) as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    ts_str = entry.get("timestamp", "")
                    if not ts_str:
                        continue
                    ts = datetime.fromisoformat(ts_str)
                    if ts >= cutoff:
                        sessions.append(entry)
                except (json.JSONDecodeError, ValueError):
                    continue

    if not sessions:
        print(f"No sessions found in last {days} days.")
        return

    print(f"\n📊 Kilo Usage Statistics (Last {days} Days)")
    print(f"{'=' * 60}")
    print(f"Total sessions: {len(sessions)}")

    # Calculate totals (handle both ReviewSession and log_usage schemas)
    def get_cost(s: dict[str, Any]) -> float:
        return s.get("total_cost", s.get("total_cost_usd", s.get("cost_usd", 0.0)))

    def get_model(s: dict[str, Any]) -> str:
        return s.get("model", s.get("session_id", "unknown"))

    total_cost = sum(get_cost(s) for s in sessions)
    total_tokens = sum(s.get("total_tokens", 0) for s in sessions)
    pass_count = sum(1 for s in sessions if s.get("verdict") == "PASS")

    print(f"Total cost: ${total_cost:.4f}")
    print(f"Total tokens: {total_tokens:,}")
    print(f"Pass rate: {pass_count}/{len(sessions)} ({100 * pass_count / len(sessions):.1f}%)")

    if by_model:
        print("\n📈 By Model:")
        by_model_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "cost": 0.0, "passes": 0}
        )
        for s in sessions:
            model = get_model(s)
            by_model_stats[model]["count"] += 1
            by_model_stats[model]["cost"] += get_cost(s)
            if s.get("verdict") == "PASS":
                by_model_stats[model]["passes"] += 1

        for model, stats in sorted(by_model_stats.items(), key=lambda x: -x[1]["cost"]):
            rate = 100 * stats["passes"] / stats["count"] if stats["count"] > 0 else 0
            print(f"  {model}: {stats['count']} sessions, ${stats['cost']:.4f}, {rate:.0f}% pass")

    if by_filetype:
        print("\n📁 By File Type:")
        by_type_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "cost": 0.0})
        for s in sessions:
            # Handle both ReviewSession.file_types and log_usage.files_reviewed
            file_types = s.get("file_types", [])
            if not file_types:
                # Extract extensions from files_reviewed if available
                files_reviewed = s.get("files_reviewed", [])
                file_types = list({Path(f).suffix for f in files_reviewed if Path(f).suffix})
            cost_per_type = get_cost(s) / max(len(file_types), 1)
            for ft in file_types:
                by_type_stats[ft]["count"] += 1
                by_type_stats[ft]["cost"] += cost_per_type

        for ft, stats in sorted(by_type_stats.items(), key=lambda x: -x[1]["count"]):
            print(f"  {ft}: {stats['count']} files, ${stats['cost']:.4f}")

    print()


def get_validated_model(model: str) -> str:
    """Get validated model, checking for deprecation and ensuring reasoning capability."""
    # Refresh cache daily
    refresh_model_cache_if_needed()

    # Check for successor
    validated = check_model_deprecation(model)

    # Validate model has reasoning capability - auto-select if not (DB-driven)
    if not has_reasoning(validated):
        fallback = _DEFAULT_MODEL_FALLBACK
        print(
            f"[KILO] Model {validated} lacks reasoning capability. Auto-selecting {fallback}",
            file=sys.stderr,
        )
        return fallback

    return validated


def get_model_with_fallback(preferred: str, failed_models: set[str] | None = None) -> str:
    """
    Get available model, falling back through chain if preferred unavailable.

    Args:
        preferred: Preferred model to use
        failed_models: Set of models that have already failed (to skip)

    Returns:
        Model ID to use

    Fallback is triggered when:
    - Model returns error during Kilo call
    - Model is in failed_models set (already tried and failed)

    Does NOT auto-fallback for:
    - CLI --model override (user explicitly chose model)
    """
    if failed_models is None:
        failed_models = set()

    # Build candidate list starting with preferred (fallback chain from DB)
    fallback_chain = _load_fallback_chain()
    candidates = [preferred] + [m for m in fallback_chain if m != preferred]

    for model in candidates:
        if model not in failed_models:
            validated = get_validated_model(model)
            if validated not in failed_models:
                return validated

    # All models failed - raise error
    raise RuntimeError(f"All models in fallback chain have failed: {failed_models}")


def should_use_max_variant(
    changed_files: list[Path],
    previous_verdict: str | None = None,
) -> tuple[bool, str]:
    """
    Determine if max variant should be used.

    Returns (should_use_max, reason)

    KISS approach - Use max only when:
    1. Final gate: previous high review PASSED (no BLOCKER/MAJOR) → one max verification
    2. Security-sensitive file paths in changed files (not content scanning)

    Does NOT use:
    - Circular triggers (issue.category from review output)
    - File content scanning (noisy, triggers on existing code)
    """
    # 1. Final gate: previous verdict was PASS (zero BLOCKER/MAJOR) → run max verification
    # Note: PASS means no blocking issues per review contract; MINORs are allowed
    if previous_verdict == "PASS":
        return True, "final_gate"

    # 2. Security-sensitive paths in CHANGED files only (not content)
    for fp in changed_files:
        path_lower = str(fp).lower()
        # Check path components for security patterns
        for pattern in SECURITY_PATTERNS:
            if (
                f"/{pattern}" in path_lower
                or f"\\{pattern}" in path_lower
                or f"{pattern}." in fp.name.lower()
            ):
                return True, f"security_path:{pattern}"

    # Default: use high (cheaper, still production-grade)
    return False, "standard"


# =============================================================================
# KILO CLI INTERACTION
# =============================================================================


def _redact_secrets(text: str) -> str:
    """Redact potential secrets from error messages."""
    import re

    # Redact common secret patterns
    text = re.sub(
        r'(api[_-]?key|token|secret|password)["\s:=]+[a-zA-Z0-9+/=_-]{16,}',
        r"\1=REDACTED",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"sk-[a-zA-Z0-9]{20,}", "sk-REDACTED", text)  # OpenAI-style keys
    text = re.sub(r"Bearer\s+[a-zA-Z0-9._-]{16,}", "Bearer REDACTED", text, flags=re.IGNORECASE)
    return text


def find_kilo_executable() -> str | None:
    """Find the kilo executable path."""
    # Check KILO_PATH env var first (most secure - user explicitly sets this)
    kilo_path_env = os.getenv("KILO_PATH")
    if kilo_path_env:
        kilo_path_env = os.path.abspath(os.path.expanduser(kilo_path_env))
        if os.path.isfile(kilo_path_env) and os.access(kilo_path_env, os.X_OK):
            return kilo_path_env

    # Check common locations (WSL npm-global first to avoid Windows binary in PATH)
    paths_to_check = [
        os.path.expanduser("~/.npm-global/bin/kilo"),  # WSL npm-global (priority)
        shutil.which("kilo"),
        os.path.expanduser("~/.local/bin/kilo"),
        "/usr/local/bin/kilo",
    ]
    for path in paths_to_check:
        if path:
            # Convert to absolute path to prevent TOCTOU issues
            path = os.path.abspath(path)
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
    return None


def build_kilo_command(
    kilo_path: str,
    model: str,
    agent: str,
    variant: str,
    session_id: str | None = None,
    file_paths: list[Path] | None = None,
) -> list[str]:
    """Build the kilo CLI command with strict input validation."""
    import re

    # Validate model format (prevent command injection)
    cli_model = model if model.startswith("kilo/") else f"kilo/{model}"
    # Allow: letters, numbers, slashes, underscores, hyphens, dots, colons (for :free suffix)
    if not re.match(r"^kilo/[a-zA-Z0-9/_.\-:]+$", cli_model):
        raise ValueError(f"Invalid model format: {cli_model}")

    # Validate variant (must be in whitelist)
    if variant and variant not in VALID_VARIANTS:
        raise ValueError(f"Invalid variant: {variant}")

    # Validate agent (must be in whitelist)
    if agent and agent not in VALID_AGENTS:
        raise ValueError(f"Invalid agent: {agent}")

    # Validate session_id format (must be UUID-like or Kilo session format)
    if session_id and not re.match(r"^[a-zA-Z0-9_-]{1,64}$", session_id):
        raise ValueError(f"Invalid session_id format: {session_id}")

    args = [kilo_path, "run", "--format", "json", "--auto"]
    args.extend(["--model", cli_model])

    if variant and variant in VALID_VARIANTS:
        args.extend(["--variant", variant])

    if agent and agent in VALID_AGENTS:
        args.extend(["--agent", agent])

    # Only pass --session for REAL Kilo sessions (returned from previous Kilo calls)
    # Kilo sessions always start with "ses_" prefix and are returned in step_finish events
    # Do NOT pass locally-generated tracking IDs - they don't exist in Kilo's DB
    if session_id and session_id.startswith("ses_") and len(session_id) > 20:
        # Real Kilo session IDs are longer (e.g., ses_2fa04657affervfKa7bqDLCufy)
        args.extend(["--session", session_id])

    if file_paths:
        project_root = get_project_root().resolve()
        for fp in file_paths:
            # Validate path is within project root (prevent path traversal and symlink attacks)
            try:
                # Check if symlink before resolving (reject symlinks outside project)
                if fp.is_symlink():
                    # Resolve symlink and validate target is within project
                    fp_abs = fp.resolve(strict=True)
                    fp_abs.relative_to(project_root)
                else:
                    # For regular files, validate existence and location atomically
                    fp_abs = fp.resolve(strict=True)
                    fp_abs.relative_to(project_root)

                # Check file size after validation
                if fp_abs.stat().st_size <= MAX_FILE_SIZE:
                    args.extend(["--file", str(fp_abs)])

            except (ValueError, OSError, RuntimeError) as e:
                print(
                    f"Warning: Skipping file outside project or invalid: {fp} ({e})",
                    file=sys.stderr,
                )
                continue

    return args


def parse_kilo_jsonl(output: str) -> dict[str, Any]:
    """
    Parse Kilo JSONL output.

    Kilo outputs events as concatenated JSON objects (not newline-delimited).
    Example:
        {"type":"step_start","sessionID":"ses_xxx"}
        {"type":"text","text":"Hello "}
        {"type":"step_finish","tokens":{"input":100,"output":50},"cost":0.01}
    """
    # Protect against extremely large outputs that could cause OOM
    # Increased to 5MB to handle large fix outputs with code diffs
    max_output_size = 5_000_000  # 5MB

    # Validate output length BEFORE processing
    if not isinstance(output, str):
        raise RuntimeError(f"Invalid output type: expected str, got {type(output).__name__}")
    if len(output) > max_output_size:
        raise RuntimeError(f"Kilo output too large: {len(output)} bytes (max {max_output_size})")

    try:
        result_text: list[str] = []
        session_id: str | None = None
        input_tokens = 0
        output_tokens = 0
        cost = 0.0
        has_step_finish = False

        decoder = json.JSONDecoder()
        idx = 0
        output_stripped = output.strip()
        max_iterations = 10_000  # Prevent infinite loops in malformed output

        iteration_count = 0
        parse_error_count = 0
        parse_errors: list[str] = []

        while idx < len(output_stripped) and iteration_count < max_iterations:
            iteration_count += 1
            # Skip whitespace
            while idx < len(output_stripped) and output_stripped[idx] in " \t\n\r":
                idx += 1
            if idx >= len(output_stripped):
                break

            try:
                obj, end_idx = decoder.raw_decode(output_stripped, idx)
                # raw_decode returns (obj, end_position) where end_position is ABSOLUTE
                # Ensure we always advance to prevent infinite loop
                if end_idx <= idx:
                    idx += 1
                    continue
                idx = end_idx  # Use absolute position, not relative offset
                # Reset error count on successful parse
                parse_error_count = 0
            except json.JSONDecodeError as e:
                # Track parse errors to detect attacks or corruption
                parse_error_count += 1
                if parse_error_count <= 3:
                    # Log first 3 errors with redacted snippet
                    snippet = output_stripped[idx : idx + 50].replace("\n", "\\n")
                    snippet = _redact_secrets(snippet)
                    parse_errors.append(f"Parse error at {idx}: {e} (snippet: {snippet})")

                # If too many consecutive errors, abort to prevent exploitation
                if parse_error_count > 10:
                    error_msg = "; ".join(parse_errors[:3])
                    raise RuntimeError(
                        f"Too many parse errors ({parse_error_count})"
                        f" - possible attack or corruption."
                        f" First errors: {error_msg}"
                    )

                # Skip malformed content
                idx += 1
                continue

            if not isinstance(obj, dict):
                continue

            # Extract session ID from any event
            if "sessionID" in obj:
                session_id = obj["sessionID"]
            elif "session_id" in obj:
                session_id = obj["session_id"]

            event_type = obj.get("type", "")

            # Handle error events from Kilo (e.g., network issues, model not found)
            if event_type == "error":
                error_data = obj.get("error", {})
                # Handle both dict and string error formats
                if isinstance(error_data, str):
                    raise RuntimeError(f"Kilo API error: {error_data}")
                error_name = error_data.get("name", "UnknownError")
                error_msg = error_data.get("data", {}).get("message", str(error_data))
                raise RuntimeError(f"Kilo API error ({error_name}): {error_msg}")

            if event_type == "text":
                # Text can be in obj["text"] or obj["part"]["text"]
                text = obj.get("text", "")
                if not text and "part" in obj:
                    text = obj["part"].get("text", "")
                if text:
                    result_text.append(text)

            elif event_type == "step_finish":
                has_step_finish = True
                # Tokens/cost can be in obj directly or in obj["part"]
                # Accumulate across multiple step_finish events (multi-step agent runs)
                part = obj.get("part", {})
                tokens = obj.get("tokens") or part.get("tokens", {})
                input_tokens += tokens.get("input", 0)
                output_tokens += tokens.get("output", 0)
                cost += obj.get("cost") or part.get("cost", 0.0)

        # Log warning if iteration limit hit
        if iteration_count >= max_iterations:
            print(f"Warning: JSONL parse hit max iterations ({max_iterations})", file=sys.stderr)

        # Log parse errors if any occurred
        if parse_errors:
            print(
                f"Warning: {len(parse_errors)} parse errors during JSONL parsing", file=sys.stderr
            )
            for err in parse_errors[:3]:
                print(f"  {err}", file=sys.stderr)

        if not has_step_finish:
            # Raise exception for incomplete runs instead of returning partial results
            raise RuntimeError("Kilo run incomplete - no step_finish event received")

        return {
            "result": "".join(result_text),
            "session_id": session_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
        }
    except (json.JSONDecodeError, ValueError, KeyError, AttributeError) as e:
        # Catch decoder exploits and malformed data
        raise RuntimeError(f"Failed to parse Kilo JSONL output: {e}") from e


def _monitor_process(proc, idle_timeout, hard_timeout, poll_interval, stream_output=False):
    """
    Monitor subprocess with liveness checking and optional streaming.

    Uses reader threads to avoid blocking on pipe reads.
    Tracks BOTH stdout AND stderr growth to detect progress.

    Args:
        proc: subprocess.Popen instance
        idle_timeout: seconds without output before killing
        hard_timeout: absolute max seconds before killing
        poll_interval: seconds between health checks
        stream_output: if True, stream JSONL text events to stderr in real-time

    Returns:
        (stdout_bytes, stderr_bytes, returncode)

    Raises:
        TimeoutError: if idle or hard timeout exceeded
    """
    import queue
    import threading

    stdout_queue = queue.Queue()
    stderr_queue = queue.Queue()

    def reader_thread(stream, q):
        """Read stream in chunks, push to queue."""
        try:
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    break
                q.put(("data", chunk))
        except Exception as e:
            q.put(("error", e))
        finally:
            q.put(("eof", None))

    # Start reader threads
    stdout_thread = threading.Thread(target=reader_thread, args=(proc.stdout, stdout_queue))
    stderr_thread = threading.Thread(target=reader_thread, args=(proc.stderr, stderr_queue))
    stdout_thread.daemon = True
    stderr_thread.daemon = True
    stdout_thread.start()
    stderr_thread.start()

    # Monitor loop
    start_time = time.time()
    last_output_time = start_time
    stdout_chunks = []
    stderr_chunks = []
    text_buffer = ""  # For streaming text extraction

    while proc.poll() is None:
        time.sleep(poll_interval)

        got_output = False

        # Drain stdout queue
        while not stdout_queue.empty():
            msg_type, data = stdout_queue.get_nowait()
            if msg_type == "data":
                stdout_chunks.append(data)
                got_output = True

                # Stream text events in real-time (extract from JSONL)
                if stream_output:
                    text_buffer += data.decode("utf-8", errors="replace")
                    # Parse complete JSONL lines
                    while "\n" in text_buffer:
                        line, text_buffer = text_buffer.split("\n", 1)
                        if line.strip():
                            try:
                                obj = json.loads(line)
                                # Extract and print text events
                                if obj.get("type") == "text":
                                    text = obj.get("text", "") or obj.get("part", {}).get(
                                        "text", ""
                                    )
                                    if text:
                                        print(text, end="", file=sys.stderr, flush=True)
                            except json.JSONDecodeError:
                                pass  # Not valid JSON, skip

        # Drain stderr queue - ALSO counts as progress
        while not stderr_queue.empty():
            msg_type, data = stderr_queue.get_nowait()
            if msg_type == "data":
                stderr_chunks.append(data)
                got_output = True  # stderr counts as progress too

        if got_output:
            last_output_time = time.time()

        # Check timeouts
        elapsed = time.time() - start_time
        idle = time.time() - last_output_time

        if idle > idle_timeout:
            proc.kill()
            proc.wait()
            if stream_output:
                print(f"\n[TIMEOUT] Idle: no output for {idle:.0f}s", file=sys.stderr)
            raise TimeoutError(f"Idle timeout: no output for {idle:.0f}s (limit {idle_timeout}s)")

        if elapsed > hard_timeout:
            proc.kill()
            proc.wait()
            if stream_output:
                print(f"\n[TIMEOUT] Hard limit: {elapsed:.0f}s", file=sys.stderr)
            raise TimeoutError(
                f"Hard timeout: total runtime {elapsed:.0f}s (limit {hard_timeout}s)"
            )

    # Collect remaining output
    stdout_thread.join(timeout=2)
    stderr_thread.join(timeout=2)

    while not stdout_queue.empty():
        msg_type, data = stdout_queue.get_nowait()
        if msg_type == "data":
            stdout_chunks.append(data)

    while not stderr_queue.empty():
        msg_type, data = stderr_queue.get_nowait()
        if msg_type == "data":
            stderr_chunks.append(data)

    if stream_output:
        print("", file=sys.stderr)  # Newline after streaming

    return (b"".join(stdout_chunks), b"".join(stderr_chunks), proc.returncode)


def _is_retryable_parse_failure(exc: Exception) -> bool:
    """Check if a parse failure is retryable (incomplete/garbled JSONL)."""
    msg = str(exc)
    retryable_markers = (
        "no step_finish event received",
        "Too many parse errors",
    )
    return any(marker in msg for marker in retryable_markers)


async def run_kilo(
    prompt: str,
    config: KiloReviewConfig,
    agent: str,
    file_paths: list[Path] | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """
    Execute Kilo CLI with monitored process execution.

    Monitors process health via output growth (stdout/stderr), not just wall-clock.
    Kills only if truly hung (no output) or hard limit exceeded.

    Args:
        prompt: The prompt to send to Kilo
        config: Review configuration
        agent: Kilo agent to use (ask, code, etc.)
        file_paths: Files to attach via --file
        timeout: Hard timeout override in seconds (default: KILO_HARD_TIMEOUT env)

    Returns:
        Parsed result dict with 'result', 'session_id', 'input_tokens', etc.
    """
    # Timeout configuration
    idle_timeout = KILO_IDLE_TIMEOUT
    hard_timeout = timeout if timeout is not None else KILO_HARD_TIMEOUT
    poll_interval = KILO_POLL_INTERVAL

    # Prompt size check removed - caller handles degradation

    kilo_path = find_kilo_executable()
    if not kilo_path:
        raise RuntimeError("Kilo executable not found. Is it installed?")

    if config.model is None:
        raise RuntimeError("config.model is None - model routing failed")

    cmd = build_kilo_command(
        kilo_path=kilo_path,
        model=config.model,
        agent=agent,
        variant=config.variant,
        session_id=config.session_id or "",
        file_paths=file_paths,
    )

    if config.verbose:
        print(f"[KILO] Running: {' '.join(cmd)}", file=sys.stderr)

    # Retry loop for transient failures
    last_exception: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            # Start monitored process
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
            )

            # Write prompt to stdin - must flush before close to ensure delivery
            try:
                if process.stdin:
                    process.stdin.write(prompt.encode("utf-8"))
                    process.stdin.flush()  # Ensure data is sent to subprocess
                    process.stdin.close()
            except (BrokenPipeError, OSError):
                pass  # Process may have exited early

            # Monitor in executor for async compatibility
            import concurrent.futures

            # Stream output when verbose - lets you watch the agent work
            stream_output = config.verbose

            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                stdout, stderr, returncode = await loop.run_in_executor(
                    executor,
                    _monitor_process,
                    process,
                    idle_timeout,
                    hard_timeout,
                    poll_interval,
                    stream_output,
                )

            # Check for retryable failures
            if returncode in RETRYABLE_EXIT_CODES and attempt < MAX_RETRIES - 1:
                wait_time = 2**attempt
                print(
                    f"⏳ Kilo transient failure (exit {returncode}). Retrying in {wait_time}s...",
                    file=sys.stderr,
                )
                await asyncio.sleep(wait_time)
                continue

            if returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")[:200]
                error_msg = _redact_secrets(error_msg)
                raise RuntimeError(f"Kilo failed (exit {returncode}): {error_msg}")

            output = stdout.decode("utf-8", errors="replace")

            if config.verbose:
                print(f"[KILO] Output: {len(output)} chars", file=sys.stderr)

            try:
                return parse_kilo_jsonl(output)
            except RuntimeError as e:
                last_exception = e
                if _is_retryable_parse_failure(e) and attempt < MAX_RETRIES - 1:
                    wait_time = 2**attempt
                    print(
                        f"⏳ Kilo incomplete/garbled response ({e}). Retrying in {wait_time}s...",
                        file=sys.stderr,
                    )
                    await asyncio.sleep(wait_time)
                    continue
                raise

        except TimeoutError as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                wait_time = 2**attempt
                print(f"⏳ Kilo timeout ({e}). Retrying...", file=sys.stderr)
                await asyncio.sleep(wait_time)
                continue
            raise RuntimeError(f"Kilo timed out: {e}")

    if last_exception:
        raise last_exception
    raise RuntimeError("Kilo call failed after all retries")


# =============================================================================
# REVIEW PROMPT
# =============================================================================

REVIEW_PROMPT_TEMPLATE = """ROLE
You are Kilo Reviewer (Opus). LAST gate before Traycer verification + commit.

⚠️ **ENFORCEMENT ACTIVE (HARD GATES)**
- Schema validation + evidence validation + plan coverage validation enforced by caller
- Invalid output = automatic FAIL + re-run once
- Missing evidence on BLOCKER/MAJOR = automatic rejection
- Incomplete plan coverage = automatic rejection

{gate_results}

ITERATION CONTEXT
- Review #: {iteration_number}
- Previous issues (if any): {previous_issues}
Re-review rule: verify previous BLOCKER/MAJOR issues are resolved.
You may report newly discovered issues.

SCOPE (HARD)
- Review ONLY the uncommitted diff in this worktree (staged + unstaged if present),
  OR only the explicitly provided diff/files.
- Do NOT commit. Do NOT apply fixes unless explicitly instructed in a separate step.
- Do NOT propose redesigns/refactors.
  Do NOT expand scope beyond the diff unless necessary to demonstrate a real bug/security issue.

INPUTS (REQUIRED)
1) **Traycer plan/spec:** {traycer_plan}
2) Repo conventions if present (AGENTS.md / existing patterns).
   If conflicts: report as SPEC/CONVENTION mismatch.
3) Diff/files: obtained from the workspace or attached via --file.

{requirements_section}

REVIEW CHECKS (IN THIS ORDER)
A) SPEC
   - Every behavior change maps to an explicit plan/spec requirement.
   - No missing plan steps; no extra features beyond plan.
B) SECURITY
   - Injection risks, auth/authz flaws, sensitive data exposure,
     unsafe deserialization, SSRF/path traversal, crypto misuse.
C) CONFIG & SECRETS HYGIENE
   - Env var misuse (wrong names, missing defaults, leaking secrets to logs,
     reading env at import-time if problematic).
   - Hardcoded values that should be config-driven (URLs/keys/ports/feature flags).
D) EDGE CASES & CORRECTNESS
   - Null/empty handling, error paths, retries/timeouts, idempotency,
     concurrency/race hazards (if relevant).
E) FABRIK CONVENTIONS (PROJECT-SPECIFIC)
   - Container images: MUST use -slim-bookworm (never Alpine).
     ❌ FROM python:3.12-alpine → ✅ FROM python:3.12-slim-bookworm
     ❌ FROM alpine:latest → ✅ FROM debian:bookworm-slim
   - Health checks: MUST test actual dependencies (not just return {{"status": "ok"}}).
     ❌ return {{"status": "ok"}}
     → ✅ await db.execute("SELECT 1"); return {{"status": "ok", "db": "connected"}}
   - Config loading: MUST be function-level (never class-level os.getenv at definition time).
     ❌ class Config: DB_URL = f"postgresql://{{os.getenv('DB_USER')}}:..."
     ✅ def get_db_url(): return f"postgresql://{{os.getenv('DB_USER')}}:..."
   - Temporary files: MUST use project-local .tmp/ (never /tmp/).
     ❌ open("/tmp/data.json") → ✅ open(".tmp/data.json")
   - Secrets: MUST use CSPRNG with 32+ chars (never hardcoded weak secrets).
     ❌ password = "abc123" → ✅ password = secrets.token_urlsafe(32)
   - Bug classes: flag dead/unreachable code, broken control flow (missing break/fallthrough),
     async/await mistakes, off-by-one errors, resource leaks (unclosed files/connections).
F) DOCS & DEV WORKFLOW
   - README/config/migration notes updated and accurate when behavior/config changes.

EVIDENCE REQUIREMENT (CRITICAL)
- EVERY issue MUST include an evidence object with type + ref/explanation
- Evidence types: diff, file_line, tool_output (need ref),
  missing, multi_file, external (need explanation)
- File + line references required for all issues (line ranges preferred)

PLAN COVERAGE REQUIREMENT (CRITICAL)
- MUST include plan_coverage array with at least 1 entry
- Each extracted requirement MUST be covered
- Status: satisfied, missing, partial, n/a
- Evidence field REQUIRED for all coverage items

If you cannot access the diff/files or the plan/spec input is missing,
return FAIL with a single SPEC issue explaining exactly what is missing.

OUTPUT FORMAT (JSON ONLY - SCHEMA ENFORCED)
Return ONLY valid JSON with this exact schema:

{{
  "verdict": "PASS" | "FAIL",
  "summary": "1-2 sentences",
  "issues": [
    {{
      "severity": "BLOCKER" | "MAJOR" | "MINOR",
      "category": "SPEC" | "SECURITY" | "CONFIG" | "EDGE" | "FABRIK" | "DOCS",
      "file": "path/to/file.ext",
      "lines": "L10-L20",
      "why": "1-2 sentences on impact/risk",
      "fix_hint": "minimal change hint; no redesign",
      "snippet": "optional short snippet",
      "evidence": {{
        "type": "diff|file_line|tool_output|missing|multi_file|external",
        "ref": "REQUIRED for diff/file_line/tool_output (e.g., 'src/file.py:L10-L20')",
        "explanation": "REQUIRED for missing/multi_file/external types"
      }}
    }}
  ],

⚠️ **LINES FIELD FORMAT (CRITICAL - SCHEMA ENFORCED)**
- MUST match pattern: ^(L\\d+(-L\\d+)?|N/A)$
- Valid: "L10", "L10-L20", "N/A"
- INVALID: "L10-L11,L155-L157" (NO commas, NO multi-ranges)
- If issue spans multiple non-contiguous ranges
  → create separate issue entries OR use primary range only
  "plan_coverage": [
    {{
      "requirement": "Exact text from plan (or general description if no explicit requirements)",
      "status": "satisfied|missing|partial|n/a",
      "evidence": "file:line reference or explanation of how requirement is met"
    }}
  ],
  "notes": ["optional non-blocking observations"],
  "stats": {{
    "files_reviewed": 0,
    "lines_changed": 0,
    "issues_by_severity": {{"BLOCKER": 0, "MAJOR": 0, "MINOR": 0}}
  }}
}}

BLOCKING RULES (HARD)
- verdict="FAIL" if ANY BLOCKER or MAJOR exists.
- verdict="PASS" if only MINOR issues exist (MINOR may be placed in notes instead of issues).
- BLOCKER: exploitable security issue, data loss, breaks core functionality, secrets exposure.
- MAJOR: spec violation, likely runtime failure, incorrect behavior in main path.
- MINOR: non-critical improvement, optional docs, small cleanups not required by spec.

**COMPLETE EXAMPLE (use this exact structure):**
```json
{{
  "verdict": "FAIL",
  "summary": "SQL injection vulnerability in user input handling.",
  "issues": [
    {{
      "severity": "BLOCKER",
      "category": "SECURITY",
      "file": "src/db.py",
      "lines": "L45-L48",
      "why": "User input directly concatenated into SQL query enables injection attacks.",
      "fix_hint": "Use parameterized queries with cursor.execute(sql, params).",
      "snippet": "cursor.execute(f\"SELECT * FROM users WHERE id = {{user_id}}\")",
      "evidence": {{"type": "diff", "ref": "src/db.py:L45-L48"}}
    }}
  ],
  "plan_coverage": [
    {{"requirement": "Add user lookup endpoint", "status": "satisfied",
      "evidence": "src/api.py:L20-L30"}}
  ],
  "notes": [],
  "stats": {{"files_reviewed": 2, "lines_changed": 45,
    "issues_by_severity": {{"BLOCKER": 1, "MAJOR": 0, "MINOR": 0}}}}
}}
```

FILES TO REVIEW:
{files_list}

{diff_content}
"""

# Doc-specific review prompt (lighter - only SPEC and DOCS categories)
DOC_REVIEW_PROMPT_TEMPLATE = """ROLE
You are Kilo Doc Reviewer. Review documentation files for accuracy and consistency.
This is a LIGHTER review - focus only on documentation quality, not security/edge cases.

ITERATION CONTEXT
- Review #: {iteration_number}
- Previous issues (if any): {previous_issues}
Re-review rule: verify previous issues are resolved. You may report newly discovered issues.

SCOPE (HARD)
- Review ONLY the provided documentation files.
- Focus on ACCURACY and CONSISTENCY with implementation.
- Do NOT report security, edge cases, or code-level issues.

REVIEW CHECKS (DOCUMENTATION ONLY)
A) SPEC - Accuracy
   - Does documentation match the actual implementation?
   - Are code examples correct and up-to-date?
   - Are model names, function signatures, CLI flags accurate?
B) DOCS - Quality
   - Is documentation clear and complete?
   - Are there broken links or outdated references?
   - Is formatting consistent?

EVIDENCE RULE
- Provide file + line references for every issue.
- If you reference implementation code to verify docs, cite both.

OUTPUT FORMAT (JSON ONLY - SCHEMA ENFORCED)
{{
  "verdict": "PASS" | "FAIL",
  "summary": "1-2 sentences",
  "issues": [
    {{
      "severity": "MAJOR" | "MINOR",
      "category": "SPEC" | "DOCS",
      "file": "path/to/file.md",
      "lines": "L10-L20",
      "snippet": "the incorrect text",
      "why": "what's wrong and what it should say",
      "fix_hint": "corrected text",
      "evidence": {{
        "type": "file_line",
        "ref": "path/to/file.md:L10-L20"
      }}
    }}
  ],

⚠️ **LINES FIELD FORMAT**: Must match ^(L\\d+(-L\\d+)?|N/A)$
  Valid: "L10", "L10-L20", "N/A" — INVALID: "L10,L20" (NO commas)

  "plan_coverage": [
    {{
      "requirement": "Review documentation files",
      "status": "satisfied",
      "evidence": "Reviewed {files_list}"
    }}
  ],
  "notes": ["optional observations"]
}}

VERDICT RULES
- FAIL if ANY MAJOR issue (incorrect info that could mislead users)
- PASS if only MINOR issues (typos, formatting, style)
- No BLOCKER severity for docs (use MAJOR for critical inaccuracies)

SKIP CATEGORIES (if specified): {skip_categories}

FILES TO REVIEW:
{files_list}

{diff_content}
"""

# Verify prompt template (cheaper workflow: review → manual fix → verify)
VERIFY_PROMPT_TEMPLATE = """ROLE
You are Kilo Verifier. Your job is to VERIFY that manually-applied fixes are correct.
This is a verification pass, not a full review. Focus on the fixes described below.

CONTEXT
The developer has manually fixed issues from a previous review.
Your task: verify the fixes are correctly implemented and no new issues were introduced.

FIXES APPLIED (by developer):
{fixes_description}

VERIFICATION CHECKS
1. Are the described fixes correctly implemented in the code?
2. Do the fixes resolve the original issues?
3. Were any new issues introduced by the fixes?
4. Are there any obvious problems in the changed code?

DO NOT:
- Redesign or suggest refactors
- Expand scope beyond verifying the fixes
- Report pre-existing issues not related to the fixes

OUTPUT FORMAT (JSON ONLY - SCHEMA ENFORCED)
{{
  "verdict": "PASS" | "FAIL",
  "summary": "1-2 sentences on verification result",
  "issues": [
    {{
      "severity": "BLOCKER" | "MAJOR" | "MINOR",
      "category": "SPEC",
      "file": "path/to/file.ext",
      "lines": "L10-L20",
      "why": "what's wrong with the fix or what new issue was introduced",
      "fix_hint": "minimal correction",
      "evidence": {{
        "type": "file_line",
        "ref": "path/to/file.ext:L10-L20"
      }}
    }}
  ],

⚠️ **LINES FIELD FORMAT**: Must match ^(L\\d+(-L\\d+)?|N/A)$
  Valid: "L10", "L10-L20", "N/A" — INVALID: "L10,L20" (NO commas)

  "plan_coverage": [
    {{
      "requirement": "Verify fixes applied",
      "status": "satisfied",
      "evidence": "All described fixes verified"
    }}
  ],
  "notes": ["Verified fixes: fix1, fix2, etc."]
}}

VERDICT RULES
- PASS: All described fixes are correctly implemented, no new issues
- FAIL: Any fix is incomplete, incorrect, or introduces new problems

FILES TO VERIFY:
{files_list}

{diff_content}
"""


FIX_PROMPT_TEMPLATE = """
You are a code fixer. Fix the following issues found in the previous code review.

PREVIOUS REVIEW ISSUES TO FIX:
{issues_json}

INSTRUCTIONS:
1. Fix each issue in order of severity (BLOCKER first, then MAJOR, then MINOR).
2. For each fix, edit the file directly using your code editing capabilities.
3. Apply minimal, targeted fixes - no redesigns or refactors.
4. After fixing, provide a summary of changes made.

OUTPUT FORMAT (JSON ONLY):
{{
  "fixes_applied": [
    {{
      "file": "path/to/file.ext",
      "lines": "Lx-Ly",
      "original_issue": "Brief description of the issue",
      "fix_description": "What was changed",
      "status": "fixed" | "skipped" | "needs_manual"
    }}
  ],
  "summary": {{
    "total_fixed": 0,
    "total_skipped": 0,
    "needs_manual": []
  }}
}}

If any issue cannot be auto-fixed, set status to "needs_manual" and explain why in the summary.
"""


# =============================================================================
# GIT HELPERS
# =============================================================================


def get_git_root() -> Path | None:
    """Get the git repository root."""
    try:
        # Validate git executable path
        git_path = shutil.which("git")
        if not git_path or not os.path.isabs(git_path):
            return None

        result = subprocess.run(
            [git_path, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        return None


def get_staged_files() -> list[Path]:
    """Get list of staged files."""
    try:
        # Validate git executable path
        git_path = shutil.which("git")
        if not git_path or not os.path.isabs(git_path):
            return []

        result = subprocess.run(
            [git_path, "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            capture_output=True,
            text=True,
            check=True,
        )
        git_root = get_git_root() or Path.cwd()
        output = result.stdout.strip()
        if not output:
            return []
        files = output.split("\n")
        return [
            git_root / f for f in files if f and any(f.endswith(ext) for ext in CODE_EXTENSIONS)
        ]
    except subprocess.CalledProcessError:
        return []


def get_changed_files() -> list[Path]:
    """Get list of changed files (staged + unstaged)."""
    try:
        # Validate git executable path
        git_path = shutil.which("git")
        if not git_path or not os.path.isabs(git_path):
            return []

        result = subprocess.run(
            [git_path, "diff", "--name-only", "--diff-filter=ACMR", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        git_root = get_git_root() or Path.cwd()
        output = result.stdout.strip()
        if not output:
            return []
        files = output.split("\n")
        return [
            git_root / f for f in files if f and any(f.endswith(ext) for ext in CODE_EXTENSIONS)
        ]
    except subprocess.CalledProcessError:
        return []


def get_diff_line_count(files: list[Path] | None = None) -> int:
    """
    Get total number of changed lines in the diff.

    Returns sum of additions + deletions from git diff --stat.
    """
    try:
        git_path = shutil.which("git")
        if not git_path or not os.path.isabs(git_path):
            return 0

        # Get git root for path normalization
        root_result = subprocess.run(
            [git_path, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        git_root = Path(root_result.stdout.strip())

        cmd = [git_path, "diff", "--stat", "HEAD"]
        if files:
            cmd.append("--")
            # Normalize to repo-relative paths for git pathspecs
            for f in files:
                try:
                    rel_path = Path(f).resolve().relative_to(git_root)
                    cmd.append(str(rel_path))
                except ValueError:
                    # Already relative or outside repo
                    cmd.append(str(f))

        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        # Parse last line: "X files changed, Y insertions(+), Z deletions(-)"
        lines = result.stdout.strip().split("\n")
        if not lines:
            return 0
        summary = lines[-1]
        total = 0
        # Extract insertions
        if "insertion" in summary:
            match = re.search(r"(\d+)\s+insertion", summary)
            if match:
                total += int(match.group(1))
        # Extract deletions
        if "deletion" in summary:
            match = re.search(r"(\d+)\s+deletion", summary)
            if match:
                total += int(match.group(1))
        return total
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return 0


def get_diff_content(
    files: list[Path] | None = None,
    staged_only: bool = False,
    include_staged: bool = False,
) -> str:
    """
    Get git diff content.

    Args:
        files: Optional list of files to diff
        staged_only: If True, only show staged changes (--cached)
        include_staged: If True, show both staged and unstaged (diff HEAD)
    """
    try:
        # Validate git executable path
        git_path = shutil.which("git")
        if not git_path or not os.path.isabs(git_path):
            return ""

        cmd = [git_path, "diff"]
        if staged_only:
            cmd.append("--cached")
        elif include_staged:
            # Diff against HEAD to capture BOTH staged and unstaged changes
            cmd.append("HEAD")
        if files:
            cmd.append("--")
            cmd.extend(str(f) for f in files)

        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        diff = result.stdout

        # Truncate if too large
        if len(diff) > MAX_DIFF_SIZE:
            diff = diff[:MAX_DIFF_SIZE] + "\n... [truncated for size]"

        return diff
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""


# =============================================================================
# FILE HANDLING
# =============================================================================


def collect_files(paths: list[str]) -> list[Path]:
    """Collect all code files from given paths (files or directories)."""
    files: list[Path] = []

    for path_str in paths:
        path = Path(path_str)

        if not path.exists():
            print(f"Warning: Path does not exist: {path}", file=sys.stderr)
            continue

        if path.is_file():
            if path.suffix.lower() in CODE_EXTENSIONS:
                files.append(path)
        elif path.is_dir():
            try:
                for root, dirs, filenames in os.walk(
                    path, onerror=lambda e: print(f"Warning: {e}", file=sys.stderr)
                ):
                    # Filter out ignored directories
                    dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

                    for filename in filenames:
                        filepath = Path(root) / filename
                        if filepath.suffix.lower() in CODE_EXTENSIONS:
                            files.append(filepath)
            except OSError as e:
                print(f"Warning: Cannot walk directory {path}: {e}", file=sys.stderr)

    return files


def get_file_content(path: Path, max_lines: int = MAX_LINES_PER_FILE) -> str:
    """Read file content with line numbers, truncating if too large."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        # Truncate if too many lines
        truncated = False
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            truncated = True

        # Add line numbers
        numbered_lines = [f"L{i + 1}: {line}" for i, line in enumerate(lines)]
        content = "".join(numbered_lines)

        if truncated:
            content += f"\n... [truncated at {max_lines} lines]"

        return content
    except Exception as e:
        return f"[Error reading file: {e}]"


def format_files_for_review(files: list[Path]) -> str:
    """Format files list for the review prompt."""
    if not files:
        return "[No files provided]"

    result = []
    for f in files:
        try:
            rel_path = f.relative_to(Path.cwd()) if f.is_absolute() else f
        except ValueError:
            # Path is not relative to CWD (different drive on Windows, etc.)
            rel_path = f
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                line_count = sum(1 for _ in fh)
        except OSError:
            line_count = 0
        result.append(f"- {rel_path} ({line_count} lines)")

    return "\n".join(result)


# =============================================================================
# SESSION MANAGEMENT
# =============================================================================


def get_session_file(session_id: str) -> Path:
    """Get path to session state file."""
    if not _is_valid_session_id(session_id):
        raise ValueError(f"Invalid session_id format: {session_id!r}")
    return SESSION_DIR / session_id / "session_state.json"


def load_session(session_id: str) -> SessionState | None:
    """Load session state from file."""
    session_file = get_session_file(session_id)
    if not session_file.exists():
        return None

    try:
        with open(session_file) as f:
            data = json.load(f)
        return SessionState(**data)
    except Exception:
        return None


def save_session(state: SessionState) -> None:
    """Save session state to file."""
    if not _is_valid_session_id(state.session_id):
        raise ValueError(f"Invalid session_id format: {state.session_id!r}")
    session_dir = SESSION_DIR / state.session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    session_file = session_dir / "session_state.json"
    with open(session_file, "w") as f:
        json.dump(asdict(state), f, indent=2, default=str)


def log_usage(report: FinalReport) -> None:
    """
    Append usage data to cumulative log file.

    Each line is a JSON object with separate review/fix tracking.
    """
    USAGE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    usage = report.usage or {}
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "session_id": report.session_id,
        "status": report.status,
        "verdict": report.verdict,
        "iterations": report.iterations,
        "files_count": len(report.files_reviewed),
        "issues_found": len(report.all_issues),
        "issues_fixed": len(report.all_fixes),
        # Total stats
        "total_tokens": usage.get("total_tokens", 0),
        "total_cost_usd": usage.get("cost_usd", 0.0),
        # Review-specific stats
        "review_calls": usage.get("review_calls", 0),
        "review_tokens": usage.get("review_input_tokens", 0) + usage.get("review_output_tokens", 0),
        "review_cost_usd": usage.get("review_cost_usd", 0.0),
        # Fix-specific stats
        "fix_calls": usage.get("fix_calls", 0),
        "fix_tokens": usage.get("fix_input_tokens", 0) + usage.get("fix_output_tokens", 0),
        "fix_cost_usd": usage.get("fix_cost_usd", 0.0),
    }

    with open(USAGE_LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def get_cumulative_usage() -> dict[str, Any]:
    """Get cumulative usage stats from log file with separate review/fix tracking."""
    if not USAGE_LOG_FILE.exists():
        return {
            "total_runs": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "review_tokens": 0,
            "review_cost_usd": 0.0,
            "fix_tokens": 0,
            "fix_cost_usd": 0.0,
        }

    stats = {
        "total_runs": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "review_tokens": 0,
        "review_cost_usd": 0.0,
        "fix_tokens": 0,
        "fix_cost_usd": 0.0,
    }

    with open(USAGE_LOG_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                stats["total_runs"] += 1
                stats["total_tokens"] += entry.get("total_tokens", 0)
                stats["total_cost_usd"] += entry.get("total_cost_usd", entry.get("cost_usd", 0.0))
                stats["review_tokens"] += entry.get("review_tokens", 0)
                stats["review_cost_usd"] += entry.get("review_cost_usd", 0.0)
                stats["fix_tokens"] += entry.get("fix_tokens", 0)
                stats["fix_cost_usd"] += entry.get("fix_cost_usd", 0.0)
            except json.JSONDecodeError:
                continue

    return stats


def get_scoped_session(
    project_root: str,
    git_branch: str,
    tracked_review_id: str,
) -> SessionState | None:
    """Get session scoped by project_root, git_branch, and tracked_review_id."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    candidates: list[SessionState] = []
    for session_file in SESSION_DIR.glob("*/session_state.json"):
        try:
            data = json.loads(session_file.read_text())
            sess = SessionState(**data)
        except Exception:
            continue

        if sess.status != "in_progress":
            continue
        if sess.project_root != project_root:
            continue
        if sess.git_branch != git_branch:
            continue
        if sess.tracked_review_id != tracked_review_id:
            continue

        candidates.append(sess)

    if not candidates:
        return None

    candidates.sort(key=lambda s: s.last_used_at, reverse=True)
    return candidates[0]


def get_latest_session() -> SessionState | None:
    """Get the most recent session (for --session continue)."""
    if not SESSION_DIR.exists():
        return None

    sessions = []
    for session_dir in SESSION_DIR.iterdir():
        if session_dir.is_dir():
            state_file = session_dir / "session_state.json"
            if state_file.exists():
                try:
                    with open(state_file) as f:
                        data = json.load(f)
                    sessions.append((data.get("last_used_at", ""), session_dir.name))
                except Exception:
                    pass

    if not sessions:
        return None

    # Sort by last_used_at descending
    sessions.sort(reverse=True)
    return load_session(sessions[0][1])


# =============================================================================
# REVIEW LOGIC
# =============================================================================


def _extract_json_object(text: str) -> dict | None:
    """
    Extract the first valid JSON object from text using json.JSONDecoder.raw_decode.

    Uses raw_decode at each '{' position, which correctly handles braces inside
    JSON string literals (unlike naive brace-counting approaches).
    """
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(text):
        # Find next opening brace
        brace_pos = text.find("{", idx)
        if brace_pos == -1:
            break
        try:
            obj, end_idx = decoder.raw_decode(text, brace_pos)
            if isinstance(obj, dict):
                return obj
            # raw_decode succeeded but result isn't a dict, skip past it
            idx = end_idx
        except json.JSONDecodeError:
            # Not valid JSON starting here, try next '{'
            idx = brace_pos + 1

    return None


def parse_review_output(raw_output: str) -> ReviewResult:
    """
    Parse review JSON output with strict schema validation.

    CRITICAL: This is a PURE SYNC function. NO async, NO asyncio.run().
    Retry logic is handled by the CALLER (_run_single_batch_review).

    CRITICAL: NO AUTO-FILL. If schema validation fails, return ReviewResult
    with <reviewer> BLOCKER. Do NOT silently default missing fields.

    Args:
        raw_output: Raw Kilo output (may contain markdown, text, JSON)

    Returns:
        ReviewResult object (may contain <reviewer> BLOCKER if validation failed)
    """
    # Step 1: Extract JSON object from output
    data = _extract_json_object(raw_output)

    if not data:
        # NO JSON found - this is a reviewer failure (NO AUTO-FILL)
        return ReviewResult(
            verdict="FAIL",
            summary="Reviewer failed to return valid JSON",
            issues=[
                ReviewIssue(
                    severity="BLOCKER",
                    category="SPEC",
                    file="<reviewer>",
                    lines="N/A",
                    why="Reviewer output did not contain valid JSON. This is a reviewer failure.",
                    fix_hint="Re-run review with explicit JSON format instruction.",
                    evidence={"type": "tool_output", "ref": "kilo_parser:no_json_found"},
                )
            ],
            plan_coverage=[],  # Empty coverage for failure case
        )

    # Step 2: Validate against strict schema (NO AUTO-FILL)
    is_valid, schema_errors = validate_review_schema(data)

    if not is_valid:
        # Schema validation failed - return structured failure (NO AUTO-FILL)
        error_summary = "; ".join(schema_errors[:5])  # First 5 errors

        return ReviewResult(
            verdict="FAIL",
            summary=f"Schema validation failed: {error_summary}",
            issues=[
                ReviewIssue(
                    severity="BLOCKER",
                    category="SPEC",
                    file="<reviewer>",
                    lines="N/A",
                    why=(
                        f"Reviewer output does not conform to required schema."
                        f" Errors: {error_summary}"
                    ),
                    fix_hint="Ensure all required fields are present and types are correct.",
                    evidence={"type": "tool_output", "ref": "schema_validator:validation_failed"},
                )
            ],
            plan_coverage=[],
            raw_output=raw_output,
        )

    # Step 3: Schema is valid - parse into ReviewResult
    issues = []
    for item in data["issues"]:
        issues.append(
            ReviewIssue(
                severity=item["severity"],
                category=item["category"],
                file=item["file"],
                lines=item["lines"],
                why=item["why"],
                fix_hint=item["fix_hint"],
                snippet=item.get("snippet"),  # Optional
                evidence=item["evidence"],  # Required by schema
            )
        )

    return ReviewResult(
        verdict=data["verdict"],
        summary=data["summary"],
        issues=issues,
        notes=data.get("notes", []),
        stats=data.get("stats", {}),
        plan_coverage=data["plan_coverage"],  # Required by schema
        raw_output=raw_output,
    )


# =============================================================================
# EVIDENCE + COVERAGE VALIDATION
# =============================================================================


def validate_evidence(issues: list[ReviewIssue]) -> tuple[bool, list[str]]:
    """
    Validate that BLOCKER/MAJOR issues have proper structured evidence.

    Evidence rules (enforced):
    - diff/file_line/tool_output: MUST have "ref" field
    - missing/multi_file/external: MUST have "explanation" field

    IMPORTANT: Schema already enforces evidence field exists for ALL issues.
    This function validates evidence QUALITY for BLOCKER/MAJOR only.
    MINOR issues can have minimal evidence without validation failure.

    Returns:
        (all_valid, list_of_violation_messages)
    """
    violations = []

    for idx, issue in enumerate(issues):
        # Only enforce quality for BLOCKER and MAJOR
        if issue.severity not in ("BLOCKER", "MAJOR"):
            continue

        # Check evidence object exists (should be caught by schema, but double-check)
        if not issue.evidence or not isinstance(issue.evidence, dict):
            violations.append(
                f"Issue #{idx + 1} ({issue.severity}/{issue.category} in {issue.file}): "
                f"missing evidence object"
            )
            continue

        ev_type = issue.evidence.get("type")
        if not ev_type:
            violations.append(f"Issue #{idx + 1} ({issue.file}): evidence.type is missing")
            continue

        # Validate based on evidence type
        if ev_type in ("diff", "file_line", "tool_output"):
            # These types require "ref" field
            if not issue.evidence.get("ref"):
                violations.append(
                    f"Issue #{idx + 1} ({issue.file}): "
                    f"evidence type '{ev_type}' requires 'ref' field (e.g., 'src/file.py:L10-L20')"
                )

        elif ev_type in ("missing", "multi_file", "external"):
            # These types require "explanation" field
            if not issue.evidence.get("explanation"):
                violations.append(
                    f"Issue #{idx + 1} ({issue.file}): "
                    f"evidence type '{ev_type}' requires 'explanation' field"
                )

        else:
            # Invalid evidence type (should be caught by schema)
            violations.append(f"Issue #{idx + 1} ({issue.file}): invalid evidence type '{ev_type}'")

    return len(violations) == 0, violations


def validate_plan_coverage(
    extracted_requirements: list[dict[str, str]],
    coverage: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    """
    Validate plan coverage completeness.

    Rules:
    - If requirements extracted: ALL must appear in coverage
    - If no requirements: at least 1 coverage entry required
    - missing/partial status should have detailed evidence

    Returns:
        (all_valid, list_of_violation_messages)
    """
    violations = []

    # If no explicit requirements, still need at least 1 coverage entry
    if not extracted_requirements:
        if not coverage:
            violations.append(
                "plan_coverage is empty - at least 1 entry required for freeform plans "
                "(describe what was reviewed)"
            )
        return len(violations) == 0, violations

    # Build requirement text lookup (case-insensitive, normalized, strip all ID prefixes)
    covered_texts_normalized = set()
    for c in coverage:
        req_text = c["requirement"].lower().strip()
        # Strip any generated prefix: REQ-1:, R1:, B1:, etc.
        req_text = re.sub(r"^(req-|r|b)\d+:\s*", "", req_text, flags=re.IGNORECASE)
        covered_texts_normalized.add(req_text)

    # Check that all requirements are covered
    for req in extracted_requirements:
        req_normalized = req["text"].lower().strip()
        if req_normalized not in covered_texts_normalized:
            violations.append(
                f"Requirement '{req['id']}' not covered in plan_coverage: {req['text'][:60]}..."
            )

    # Check for missing/partial status without detailed evidence
    for item in coverage:
        if item["status"] in ("missing", "partial") and (
            not item.get("evidence") or len(item["evidence"]) < 10
        ):
            violations.append(
                f"Coverage item marked '{item['status']}' lacks detailed evidence: "
                f"{item['requirement'][:40]}..."
            )

    return len(violations) == 0, violations


# =============================================================================
# PRE-REVIEW DETERMINISTIC GATES (RENAMED)
# =============================================================================


def run_pre_review_gates() -> dict[str, Any]:
    """
    Run scripts/final_gate.py with fault tolerance.

    RENAMED from run_final_gate() to avoid collision with existing
    "final_gate" max-variant verification logic in this script.

    Returns structured result even if script missing/errors/times out.

    Returns:
        {
            "overall": "PASS" | "FAIL",
            "summary": "X/Y checks passed",
            "failures": [{"check": "name", "error": "description"}, ...],
            "warnings": ["warning text", ...],
            "raw_output": "full output text"
        }
    """
    import subprocess

    final_gate_path = Path("scripts/final_gate.py")

    # Check if script exists
    if not final_gate_path.exists():
        return {
            "overall": "FAIL",
            "summary": "0/0 checks (script not found)",
            "failures": [
                {
                    "check": "script_exists",
                    "error": "scripts/final_gate.py not found - pre-review gates are required",
                }
            ],
            "warnings": [],
            "raw_output": "",
        }

    # Run with timeout
    try:
        result = subprocess.run(
            ["python", str(final_gate_path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        raw_output = result.stdout + result.stderr

        # Parse output for pass/fail
        # Heuristic: look for "All checks passed" or exit code 0
        if result.returncode == 0:
            return {
                "overall": "PASS",
                "summary": "All checks passed",
                "failures": [],
                "warnings": [],
                "raw_output": raw_output,
            }

        # Parse failures from output (simple heuristic)
        failures = []
        for line in raw_output.split("\n"):
            if "FAIL" in line or "ERROR" in line:
                failures.append({"check": "unknown", "error": line.strip()})

        return {
            "overall": "FAIL",
            "summary": f"{len(failures)} check(s) failed",
            "failures": failures[:10],  # Max 10 failures
            "warnings": [],
            "raw_output": raw_output[:2000],  # Truncate
        }

    except subprocess.TimeoutExpired:
        return {
            "overall": "FAIL",
            "summary": "Gate script timed out (>60s)",
            "failures": [{"check": "timeout", "error": "script exceeded 60s limit"}],
            "warnings": [],
            "raw_output": "",
        }

    except Exception as e:
        return {
            "overall": "FAIL",
            "summary": f"Gate script error: {type(e).__name__}",
            "failures": [{"check": "execution", "error": str(e)}],
            "warnings": [],
            "raw_output": "",
        }


def format_gate_results_compact(gate_data: dict[str, Any]) -> str:
    """
    Format gate results compactly for prompt injection.

    Only includes failures/warnings (not full output) to save tokens.

    Args:
        gate_data: Output from run_pre_review_gates()

    Returns:
        Formatted string for prompt (empty if PASS with no warnings)
    """
    if gate_data["overall"] == "PASS" and not gate_data.get("warnings"):
        return ""  # No gate issues - don't clutter prompt

    lines = ["**Pre-Review Gates:**"]
    lines.append(f"Status: {gate_data['overall']} ({gate_data['summary']})")

    if gate_data.get("failures"):
        lines.append("Failures:")
        for fail in gate_data["failures"][:5]:  # Max 5 failures
            lines.append(f"  - {fail.get('check', 'unknown')}: {fail.get('error', 'N/A')}")

    if gate_data.get("warnings"):
        lines.append("Warnings:")
        for warn in gate_data["warnings"][:3]:  # Max 3 warnings
            lines.append(f"  - {warn}")

    lines.append("")  # Blank line separator
    return "\n".join(lines)


def parse_fix_output(raw_output: str) -> FixResult:
    """Parse fix JSON output from Kilo."""
    data = _extract_json_object(raw_output)

    if data is None:
        return FixResult(
            status="FAILED",
            fixes_applied=[],
            total_fixed=0,
            total_skipped=0,
            needs_manual=[{"error": "No JSON in output"}],
        )

    summary = data.get("summary", {})
    status = "SUCCESS" if summary.get("total_fixed", 0) > 0 else "FAILED"
    if summary.get("needs_manual"):
        status = "PARTIAL"

    return FixResult(
        status=status,
        fixes_applied=data.get("fixes_applied", []),
        total_fixed=summary.get("total_fixed", 0),
        total_skipped=summary.get("total_skipped", 0),
        needs_manual=summary.get("needs_manual", []),
    )


async def _run_review_batched(
    files: list[Path],
    config: KiloReviewConfig,
    iteration: int,
    previous_issues: list[dict[str, Any]] | None = None,
) -> ReviewResult:
    """
    Process ALL files in batches and aggregate results.

    This ensures no files are silently skipped when file count exceeds MAX_FILES_PER_BATCH.
    """
    batch_size = config.max_files_per_batch
    total_files = len(files)
    num_batches = (total_files + batch_size - 1) // batch_size  # Ceiling division

    print(
        f"  Processing {total_files} files in {num_batches} batch(es) of {batch_size}...",
        file=sys.stderr,
    )

    # Aggregate results from all batches
    all_issues: list[ReviewIssue] = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0
    final_verdict = "PASS"
    summaries: list[str] = []
    session_id = config.session_id

    for batch_num in range(num_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, total_files)
        batch_files = files[start_idx:end_idx]

        print(
            f"    Batch {batch_num + 1}/{num_batches}: files {start_idx + 1}-{end_idx}",
            file=sys.stderr,
        )

        # Run single batch review (calls run_review which won't recurse since batch is small)
        batch_result = await _run_single_batch_review(
            files=batch_files,
            config=config,
            iteration=iteration,
            previous_issues=previous_issues,
        )

        # Capture session ID from first batch for subsequent batches
        # Validate to prevent path traversal via malicious/corrupted response
        if batch_result.session_id and not session_id:
            if _is_valid_session_id(batch_result.session_id):
                session_id = batch_result.session_id
                config.session_id = session_id
            else:
                print(
                    f"Warning: Invalid session_id from Kilo batch response: "
                    f"{batch_result.session_id!r}, ignoring",
                    file=sys.stderr,
                )

        # Aggregate issues
        all_issues.extend(batch_result.issues)
        total_input_tokens += batch_result.input_tokens
        total_output_tokens += batch_result.output_tokens
        total_cost += batch_result.cost

        # Aggregate verdict (FAIL if any batch fails)
        if batch_result.verdict == "FAIL":
            final_verdict = "FAIL"

        if batch_result.summary:
            summaries.append(f"Batch {batch_num + 1}: {batch_result.summary}")

    # Build aggregated summary
    if final_verdict == "PASS":
        aggregated_summary = f"All {num_batches} batches passed. {total_files} files reviewed."
    else:
        issue_count = len(all_issues)
        aggregated_summary = (
            f"Found {issue_count} issue(s) across {num_batches} batches ({total_files} files)."
        )

    return ReviewResult(
        verdict=final_verdict,
        summary=aggregated_summary,
        issues=all_issues,
        notes=summaries,
        stats={"batches": num_batches, "total_files": total_files},
        session_id=session_id,
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
        cost=total_cost,
    )


async def _run_single_batch_review(
    files: list[Path],
    config: KiloReviewConfig,
    iteration: int,
    previous_issues: list[dict[str, Any]] | None = None,
) -> ReviewResult:
    """
    Run review with ALL enforcement gates.

    Corrections applied:
    - Token accounting: tracks all attempts, sums costs
    - Safe gate write: only if SESSION_DIR exists
    - Metadata from correct call after retry
    - Retry includes JSON skeleton
    - Evidence validation for BLOCKER/MAJOR
    - Plan coverage validation
    """
    # Track ALL attempts for accurate cost accounting
    attempt_results = []

    files_to_review = files

    # Build prompt with only the files we'll actually review
    files_list = format_files_for_review(files_to_review)

    # Get diff content based on mode
    if config.review_mode == "staged":
        diff_content = get_diff_content(files_to_review, staged_only=True)
        diff_section = f"STAGED DIFF:\n```diff\n{diff_content}\n```" if diff_content else ""
    elif config.review_mode == "diff_only":
        # Use include_staged=True to capture BOTH staged and unstaged changes (git diff HEAD)
        diff_content = get_diff_content(files_to_review, include_staged=True)
        diff_section = f"DIFF:\n```diff\n{diff_content}\n```" if diff_content else ""
    else:
        # Full mode - include file contents
        file_contents = []
        for f in files_to_review:
            content = get_file_content(f)
            try:
                rel_path = f.relative_to(Path.cwd()) if f.is_absolute() else f
            except ValueError:
                rel_path = f
            file_contents.append(f"### {rel_path}\n```\n{content}\n```")
        diff_section = "\n\n".join(file_contents)

    # Format previous issues
    prev_issues_str = "None (first review)"
    if previous_issues:
        prev_issues_str = json.dumps(previous_issues, indent=2)

    # Format plan
    plan_str = config.traycer_plan or "[No plan/spec provided - review for general issues]"

    # Extract plan requirements (for coverage validation)
    plan_requirements = extract_plan_requirements(plan_str)
    requirements_section = format_requirements_for_prompt(plan_requirements)

    # Run pre-review gates (fault-tolerant)
    gate_data = run_pre_review_gates()
    gate_results_str = format_gate_results_compact(gate_data)

    # Save gate output SAFELY (check SESSION_DIR exists)
    if hasattr(config, "session_id") and config.session_id:
        try:
            gate_log_dir = SESSION_DIR if "SESSION_DIR" in globals() else Path(".droid/reviews")
            gate_log_dir.mkdir(parents=True, exist_ok=True)
            # Only write if we have output (could be empty on error/timeout)
            if gate_data.get("raw_output"):
                (gate_log_dir / "gate_output.txt").write_text(gate_data["raw_output"])
        except Exception as e:
            print(f"⚠️  Could not save gate output: {e}", file=sys.stderr)

    # Select prompt template based on mode
    if config.verify_mode and config.fixes_description:
        # Verify mode: use lighter verification prompt (no gates/requirements)
        prompt = VERIFY_PROMPT_TEMPLATE.format(
            fixes_description=config.fixes_description,
            files_list=files_list,
            diff_content=diff_section,
        )
    elif config.doc_mode or is_doc_only_review(files):
        # Doc-only mode: use lighter doc-specific prompt (no gates/requirements)
        skip_cats_str = ", ".join(config.skip_categories) if config.skip_categories else "None"
        prompt = DOC_REVIEW_PROMPT_TEMPLATE.format(
            iteration_number=iteration,
            previous_issues=prev_issues_str,
            skip_categories=skip_cats_str,
            files_list=files_list,
            diff_content=diff_section,
        )
    else:
        # Standard review mode - WITH gates and requirements
        prompt = REVIEW_PROMPT_TEMPLATE.format(
            iteration_number=iteration,
            previous_issues=prev_issues_str,
            traycer_plan=plan_str,
            requirements_section=requirements_section,  # NEW
            gate_results=gate_results_str,  # NEW
            files_list=files_list,
            diff_content=diff_section,
        )

    # Check prompt size and degrade if needed
    if len(prompt) > MAX_PROMPT_SIZE:
        if config.review_mode == "full":
            # Degrade to diff_only and rebuild
            print(
                f"⚠️  Prompt too large ({len(prompt)} bytes), degrading to diff_only",
                file=sys.stderr,
            )
            config = replace(config, review_mode="diff_only")

            # Rebuild diff section with diff_only mode
            diff_content = get_diff_content(files_to_review, include_staged=True)
            diff_section = f"DIFF:\n```diff\n{diff_content}\n```" if diff_content else ""

            # Rebuild prompt with diff_only
            prompt = REVIEW_PROMPT_TEMPLATE.format(
                iteration_number=iteration,
                previous_issues=prev_issues_str,
                traycer_plan=plan_str,
                requirements_section=requirements_section,
                gate_results=gate_results_str,
                files_list=files_list,
                diff_content=diff_section,
            )

            # Check again after degradation
            if len(prompt) > MAX_PROMPT_SIZE:
                raise ValueError(
                    f"Prompt still too large after degrading to diff_only: "
                    f"{len(prompt)} > {MAX_PROMPT_SIZE}"
                )
        else:
            # Already diff_only or other mode, can't degrade further
            raise ValueError(f"Prompt too large: {len(prompt)} > {MAX_PROMPT_SIZE}")

    # Attempt 1: Run Kilo
    result = await run_kilo(
        prompt=prompt,
        config=config,
        agent=config.review_agent,
        file_paths=files_to_review,
    )
    attempt_results.append(result)

    # Update session ID from Kilo response (capture real Kilo session ID)
    # Check length because local tracking IDs are shorter (20 chars)
    # than real Kilo sessions (30+ chars)
    kilo_session = result.get("session_id", "")
    if kilo_session and len(kilo_session) > 20 and kilo_session != config.session_id:
        config.session_id = kilo_session

    # Parse strict (NO auto-fill)
    review_result = parse_review_output(result["result"])

    # Check if schema validation failed OR no JSON found
    schema_failed = (
        review_result.verdict == "FAIL"
        and len(review_result.issues) >= 1
        and review_result.issues[0].file == "<reviewer>"
        and (
            "schema" in review_result.issues[0].why.lower()
            or "json" in review_result.issues[0].why.lower()
        )
    )

    if schema_failed:
        print("⚠️  Schema validation failed, retrying with JSON skeleton...", file=sys.stderr)

        # Retry with complete JSON skeleton
        retry_prompt = f"""SCHEMA VALIDATION FAILED

Your previous output did not match the required JSON schema.

**You MUST return valid JSON matching this structure:**

{{
  "verdict": "PASS",
  "summary": "Brief description (min 10 chars)",
  "issues": [
    {{
      "severity": "BLOCKER",
      "category": "SPEC",
      "file": "src/example.py",
      "lines": "L10-L20",
      "snippet": "optional",
      "why": "Detailed explanation (min 10 chars)",
      "fix_hint": "How to fix (min 5 chars)",
      "evidence": {{
        "type": "file_line",
        "ref": "src/example.py:L10-L20"
      }}
    }}
  ],
  "plan_coverage": [
    {{
      "requirement": "Requirement text from plan (min 5 chars)",
      "status": "satisfied",
      "evidence": "src/example.py:L10 implements this"
    }}
  ],
  "notes": [],
  "stats": {{"files_reviewed": {len(files)}, "lines_changed": 0}}
}}

Return ONLY the JSON object (no markdown, no text before/after).

Original task: {plan_str[:300]}...
"""

        # Attempt 2: Retry
        retry_result = await run_kilo(
            prompt=retry_prompt,
            config=config,
            agent=config.review_agent,
            file_paths=files_to_review,
        )
        attempt_results.append(retry_result)

        # Parse retry
        review_result = parse_review_output(retry_result["result"])

        if review_result.verdict == "FAIL" and any(
            i.file == "<reviewer>" for i in review_result.issues
        ):
            print("❌ Schema still invalid after retry. Giving up.", file=sys.stderr)
            # Will attach metadata below and return

    # Validate evidence (only if schema passed)
    if not any(i.file == "<reviewer>" for i in review_result.issues):
        evidence_valid, evidence_violations = validate_evidence(review_result.issues)

        if not evidence_valid:
            print("❌ Evidence validation failed", file=sys.stderr)
            review_result.verdict = "FAIL"
            review_result.issues.insert(
                0,
                ReviewIssue(
                    severity="BLOCKER",
                    category="SPEC",
                    file="<reviewer>",
                    lines="N/A",
                    why=(
                        f"Missing required evidence."
                        f" Violations: {'; '.join(evidence_violations[:3])}"
                    ),
                    fix_hint="Add structured evidence to all BLOCKER/MAJOR issues",
                    evidence={"type": "tool_output", "ref": "evidence_validator:failed"},
                ),
            )
        else:
            # Validate plan coverage (skip for doc/verify modes - they don't use plans)
            skip_coverage = config.doc_mode or config.verify_mode or is_doc_only_review(files)

            if not skip_coverage:
                coverage_valid, coverage_violations = validate_plan_coverage(
                    plan_requirements,
                    review_result.plan_coverage,
                )

                if not coverage_valid:
                    print("❌ Coverage validation failed", file=sys.stderr)
                    review_result.verdict = "FAIL"
                    review_result.issues.insert(
                        0,
                        ReviewIssue(
                            severity="BLOCKER",
                            category="SPEC",
                            file="<reviewer>",
                            lines="N/A",
                            why=(
                                f"Incomplete plan coverage."
                                f" Violations: {'; '.join(coverage_violations[:3])}"
                            ),
                            fix_hint="Include all requirements in plan_coverage array",
                            evidence={"type": "tool_output", "ref": "coverage_validator:failed"},
                        ),
                    )

    # Attach metadata - SUM ALL ATTEMPTS
    total_input_tokens = sum(r.get("input_tokens", 0) for r in attempt_results)
    total_output_tokens = sum(r.get("output_tokens", 0) for r in attempt_results)
    total_cost = sum(r.get("cost", 0.0) for r in attempt_results)

    review_result.session_id = attempt_results[-1].get("session_id")
    review_result.input_tokens = total_input_tokens
    review_result.output_tokens = total_output_tokens
    review_result.cost = total_cost

    # Add attempt count to stats
    if not review_result.stats:
        review_result.stats = {}
    review_result.stats["attempts"] = len(attempt_results)
    if len(attempt_results) > 1:
        review_result.stats["retried"] = True
        review_result.stats["retry_reason"] = "schema_validation_failed"

    return review_result


# =============================================================================
# MULTI-PASS REVIEW (RISK-BASED)
# =============================================================================


def assess_review_risk(files: list[Path], diff_content: str) -> dict[str, Any]:
    """
    Assess risk level for multi-pass decision.

    Returns:
        {
            "requires_multi_pass": bool,
            "risk_level": "low" | "medium" | "high",
            "triggers": ["reason1", "reason2", ...],
            "diff_size": int,
        }
    """
    triggers = []
    diff_size = len(diff_content.split("\n"))

    # Check for security-sensitive paths
    security_matches = []
    for f in files:
        path_str = str(f).lower()
        for keyword in SECURITY_SENSITIVE_PATHS:
            if keyword in path_str:
                security_matches.append(f"{f.name} (keyword: {keyword})")
                break

    if security_matches:
        triggers.append(f"security_sensitive_paths: {', '.join(security_matches[:3])}")

    # Check diff size
    if diff_size > RISK_DIFF_SIZE_THRESHOLD:
        triggers.append(f"large_diff: {diff_size} lines > {RISK_DIFF_SIZE_THRESHOLD} threshold")

    # Determine risk level and multi-pass requirement
    if len(triggers) >= 2:
        risk_level = "high"
        requires_multi_pass = True
    elif len(triggers) == 1:
        risk_level = "medium"
        requires_multi_pass = True
    else:
        risk_level = "low"
        requires_multi_pass = False

    return {
        "requires_multi_pass": requires_multi_pass,
        "risk_level": risk_level,
        "triggers": triggers,
        "diff_size": diff_size,
    }


async def run_multi_pass_review(
    files: list[Path],
    config: KiloReviewConfig,
    iteration: int,
    previous_issues: list[dict[str, Any]] | None = None,
    risk_assessment: dict[str, Any] | None = None,  # noqa: ARG001
) -> ReviewResult:
    """
    Multi-pass review: general + security-focused.

    CRITICAL: Uses dataclasses.replace() to avoid config mutation.

    Args:
        files: Files to review
        config: Review configuration
        iteration: Review iteration number
        previous_issues: Issues from previous review
        risk_assessment: Risk assessment data (optional, for logging)

    Returns:
        Merged ReviewResult from both passes
    """
    print(
        "⚠️  HIGH RISK detected - running multi-pass review (general + security)",
        file=sys.stderr,
    )

    # Pass 1: General review (all categories)
    print("  [PASS 1/2] General review...", file=sys.stderr)
    pass1_result = await _run_single_batch_review(files, config, iteration, previous_issues)

    # Pass 2: Security-focused review (skip non-security categories)
    # CRITICAL: Use dataclasses.replace() to create config copy (avoid mutation)
    print("  [PASS 2/2] Security-focused review...", file=sys.stderr)
    security_config = replace(
        config,
        skip_categories={"SPEC", "CONFIG", "EDGE", "DOCS"},  # Focus on SECURITY only
    )
    pass2_result = await _run_single_batch_review(
        files, security_config, iteration, previous_issues
    )

    # Merge results
    # Strategy: combine issues, sum tokens/costs, use worse verdict
    merged_issues = list(pass1_result.issues)

    # Add pass2 security issues that aren't duplicates
    for p2_issue in pass2_result.issues:
        # Simple dedup: check if same file+lines+category exists in pass1
        is_duplicate = any(
            p1_issue.file == p2_issue.file
            and p1_issue.lines == p2_issue.lines
            and p1_issue.category == p2_issue.category
            for p1_issue in pass1_result.issues
        )
        if not is_duplicate:
            merged_issues.append(p2_issue)

    # Merge plan_coverage (prefer pass1 as it's more complete)
    merged_coverage = pass1_result.plan_coverage or pass2_result.plan_coverage

    # Merge notes
    merged_notes = list(pass1_result.notes)
    merged_notes.append(
        f"Multi-pass review: {len(pass1_result.issues)} general"
        f" + {len(pass2_result.issues)} security-focused"
    )

    # Compute merged verdict (FAIL if either pass failed)
    merged_verdict = (
        "FAIL" if (pass1_result.verdict == "FAIL" or pass2_result.verdict == "FAIL") else "PASS"
    )

    # Sum tokens and costs
    total_input_tokens = pass1_result.input_tokens + pass2_result.input_tokens
    total_output_tokens = pass1_result.output_tokens + pass2_result.output_tokens
    total_cost = pass1_result.cost + pass2_result.cost

    # Merge stats
    merged_stats = pass1_result.stats.copy() if pass1_result.stats else {}
    merged_stats["multi_pass"] = True
    merged_stats["pass1_issues"] = len(pass1_result.issues)
    merged_stats["pass2_issues"] = len(pass2_result.issues)
    merged_stats["total_issues"] = len(merged_issues)

    return ReviewResult(
        verdict=merged_verdict,
        summary=f"Multi-pass review: {merged_verdict} ({len(merged_issues)} total issues)",
        issues=merged_issues,
        notes=merged_notes,
        stats=merged_stats,
        plan_coverage=merged_coverage,
        session_id=pass2_result.session_id,  # Use last session ID
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
        cost=total_cost,
    )


async def run_review(
    files: list[Path],
    config: KiloReviewConfig,
    iteration: int,
    previous_issues: list[dict[str, Any]] | None = None,
) -> ReviewResult:
    """
    Run a single review iteration with multi-pass support.

    Assesses risk based on file paths and diff size. If high-risk, triggers
    multi-pass review (general + security-focused).
    """
    # Get diff content for risk assessment
    if config.review_mode == "staged":
        diff_content = get_diff_content(files, staged_only=True)
    elif config.review_mode == "diff_only":
        diff_content = get_diff_content(files, include_staged=True)
    else:
        # Full mode - still get diff for risk assessment (large diffs should trigger multi-pass)
        diff_content = get_diff_content(files, include_staged=True)

    # Assess risk for multi-pass decision
    risk_assessment = assess_review_risk(files, diff_content)

    # Route based on risk (gated by KILO_ENABLE_MULTI_PASS)
    if KILO_ENABLE_MULTI_PASS and risk_assessment["requires_multi_pass"]:
        print(
            f"[RISK] {risk_assessment['risk_level'].upper()} risk detected:"
            f" {', '.join(risk_assessment['triggers'])}",
            file=sys.stderr,
        )
        return await run_multi_pass_review(
            files, config, iteration, previous_issues, risk_assessment
        )

    # Standard path: single or batched review
    if len(files) > config.max_files_per_batch:
        return await _run_review_batched(files, config, iteration, previous_issues)

    return await _run_single_batch_review(files, config, iteration, previous_issues)


def capture_git_diff(files: list[str] | None = None) -> str:
    """Capture git diff for specified files or all unstaged changes."""
    try:
        git_path = shutil.which("git")
        if not git_path:
            return ""

        cmd = [git_path, "diff", "--no-color"]
        if files:
            cmd.extend(files)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=get_project_root(),
        )
        return result.stdout[:50000] if result.stdout else ""  # Limit to 50KB
    except (subprocess.TimeoutExpired, OSError):
        return ""


async def run_fix(
    issues: list[ReviewIssue],
    config: KiloReviewConfig,
) -> FixResult:
    """Run fix phase for identified issues."""
    # Build fix prompt
    issues_json = json.dumps([i.to_dict() for i in issues], indent=2)
    prompt = FIX_PROMPT_TEMPLATE.format(issues_json=issues_json)

    # Get affected files for diff capture
    affected_files = list({i.file for i in issues if i.file})

    # Run Kilo with code agent
    result = await run_kilo(
        prompt=prompt,
        config=config,
        agent=config.fix_agent,
    )

    # Parse result
    fix_result = parse_fix_output(result["result"])
    fix_result.session_id = result.get("session_id")
    fix_result.input_tokens = result.get("input_tokens", 0)
    fix_result.output_tokens = result.get("output_tokens", 0)
    fix_result.cost = result.get("cost", 0.0)

    # Capture git diff of changes made
    if fix_result.fixes_applied:
        fix_result.diff = capture_git_diff(affected_files)
        if fix_result.diff and config.verbose:
            print(f"\n[DIFF] Changes made by Kilo:\n{fix_result.diff[:2000]}...", file=sys.stderr)

    return fix_result


async def review_loop(
    files: list[Path],
    config: KiloReviewConfig,
) -> FinalReport:
    """
    Main review-fix-review loop.

    Flow:
    1. Review files → get findings
    2. If findings with BLOCKER/MAJOR severity:
       a. Fix using same session (context preserved!)
       b. Re-review modified files
       c. Repeat until clean or max iterations
    3. Return final report
    """
    # Initialize high-risk paths for programmatic callers (no stderr output)
    _init_high_risk_paths(verbose=False)

    # Initialize session with scoped resolution
    project_root = str(get_project_root())
    git_branch = get_current_git_branch()

    # Auto-generate tracked_review_id if not provided (prevents session mixing)
    # Uses deterministic hash of project+branch+date for same-day continuity
    if not config.tracked_review_id:
        import hashlib

        today = datetime.now().strftime("%Y%m%d")
        scope_key = f"{project_root}:{git_branch}:{today}"
        config.tracked_review_id = f"auto_{hashlib.sha256(scope_key.encode()).hexdigest()[:12]}"

    if config.session_id == "continue":
        existing = get_scoped_session(
            project_root=project_root,
            git_branch=git_branch,
            tracked_review_id=config.tracked_review_id,
        )

        if existing:
            config.session_id = existing.session_id
            print(f"Continuing scoped session: {config.session_id}", file=sys.stderr)
            print(f"  Project: {project_root}", file=sys.stderr)
            print(f"  Branch: {git_branch}", file=sys.stderr)
            print(f"  Review ID: {config.tracked_review_id}", file=sys.stderr)
        else:
            config.session_id = f"ses_{uuid.uuid4().hex[:16]}"
            print(f"No existing session found, creating new: {config.session_id}", file=sys.stderr)
    elif not config.session_id:
        config.session_id = f"ses_{uuid.uuid4().hex[:16]}"

    # Track the session ID we'll use for persistence
    local_session_id = config.session_id

    # ==========================================================================
    # TIERED MODEL ROUTING (Cost-Aware Escalation)
    # ==========================================================================
    # Select model using tiered strategy based on risk level.
    # User --model override takes precedence; otherwise use strategy-based selection.
    # Strategy can be: free, economy, standard, premium, critical
    # Note: config.model is None if user didn't specify --model

    # Compute total diff lines for large diff detection (>400 lines = HIGH risk)
    total_diff_lines = get_diff_line_count(files)

    selected_model, tier, strategy_used, tier_idx, risk_level = select_model_with_strategy(
        diff_files=files,
        user_model=config.model,  # None if not specified by user
        strategy=config.strategy,
        max_cost=config.max_cost,
        total_diff_lines=total_diff_lines,
    )
    config.model = selected_model

    # Auto-select variant based on risk level (user override takes precedence)
    original_variant = config.variant
    config.variant = get_auto_variant(
        risk_level, original_variant if original_variant != "high" else None
    )

    log_tiered_routing(files, selected_model, tier, strategy_used, risk_level)
    if config.variant != original_variant:
        print(
            f"[ROUTING] Variant: {config.variant} (auto-selected for {risk_level} risk)",
            file=sys.stderr,
        )

    # Initialize escalation state for tracking
    escalation_state = EscalationState(
        strategy=strategy_used,
        current_tier_idx=tier_idx,
        session_id=local_session_id,
        max_cost=config.max_cost,
        risk_level=risk_level,
    )

    # Initialize tracking
    usage = UsageStats()
    all_issues: list[dict[str, Any]] = []
    all_fixes: list[dict[str, Any]] = []
    files_reviewed = [str(f) for f in files]

    # Pre-review validation (fail fast before spending credits)
    validation_issues = pre_review_checks(files)
    if validation_issues:
        return FinalReport(
            status="ERROR",
            verdict="FAIL",
            iterations=0,
            files_reviewed=files_reviewed,
            all_issues=[
                {
                    "severity": "BLOCKER",
                    "category": "VALIDATION",
                    "file": "pre-review",
                    "lines": "",
                    "why": issue,
                    "fix_hint": "Fix the validation error before running review",
                }
                for issue in validation_issues
            ],
            all_fixes=[],
            remaining_issues=[],
            usage={},
            session_id="",
            summary=f"Pre-review validation failed: {len(validation_issues)} issue(s) found",
        )

    # Initialize previous_issues from persisted state if tracked_review_id is present
    previous_issues: list[dict[str, Any]] | None = None
    if config.tracked_review_id:
        previous_issues = get_open_issues(config.tracked_review_id)
        if previous_issues:
            print(
                f"[ISSUE STATE] Loaded {len(previous_issues)} open issues from previous iterations",
                file=sys.stderr,
            )

    previous_verdict: str | None = None  # Track last review verdict for max variant decision
    iteration = 0
    issue_history: dict[str, int] = {}  # Track repeated issues for false positive detection
    false_positives_total: list[dict[str, Any]] = []  # Accumulated false positives

    # Auto-detect doc mode and adjust max iterations
    is_doc_review = config.doc_mode or is_doc_only_review(files)
    if is_doc_review and config.max_iterations > MAX_ITERATIONS_DOCS:
        print(
            f"[DOC MODE] Auto-reducing max iterations:"
            f" {config.max_iterations} → {MAX_ITERATIONS_DOCS}",
            file=sys.stderr,
        )
        config.max_iterations = MAX_ITERATIONS_DOCS

    # Create session state (using local_session_id for file storage)
    session_state = SessionState(
        session_id=local_session_id,
        created_at=datetime.now(UTC).isoformat(),
        last_used_at=datetime.now(UTC).isoformat(),
        model=config.model,
        variant=config.variant,
        files_reviewed=files_reviewed,
        iteration=0,
        status="in_progress",
        usage={},
        project_root=project_root,
        git_branch=git_branch,
        tracked_review_id=config.tracked_review_id,
    )

    try:
        # Use soft limit from config, but enforce hard cap
        effective_max = min(config.max_iterations, HARD_MAX_ITERATIONS)

        while iteration < effective_max:
            iteration += 1

            # Smart variant selection: KISS approach
            # Use max only for: (1) final gate after PASS, (2) security-sensitive paths
            use_max, max_reason = should_use_max_variant(
                changed_files=files,
                previous_verdict=previous_verdict,
            )
            current_variant = "max" if use_max else config.variant

            if use_max and max_reason == "final_gate":
                print(
                    "\n=== Final Verification (variant=max) ===",
                    file=sys.stderr,
                )
            elif use_max:
                print(
                    f"\n=== Review Iteration {iteration}/{effective_max}"
                    f" (variant=max, reason={max_reason}) ===",
                    file=sys.stderr,
                )
            else:
                print(
                    f"\n=== Review Iteration {iteration}/{effective_max} ===",
                    file=sys.stderr,
                )

            # PHASE 1: Review (with adaptive variant and model error retry)
            # Temporarily override variant for this iteration
            # Save original model to prevent escalation state leak
            original_model = config.model
            original_variant = config.variant
            config.variant = current_variant

            try:
                # Model error retry loop - try up to 4 fallbacks (all 5 assigned models)
                max_model_retries = 3
                model_escalation_count = 0
                max_model_escalations = 4  # Try all 5 assigned reviewing models
                review_result = None
                for model_attempt in range(max_model_retries):
                    try:
                        # Emit progress: model starting
                        emit_progress(
                            "model_start",
                            model=config.model,
                            attempt=model_attempt + 1,
                            iteration=iteration,
                            escalation=model_escalation_count,
                        )

                        review_result = await run_review(
                            files=files,
                            config=config,
                            iteration=iteration,
                            previous_issues=previous_issues,
                        )

                        # Emit progress: model succeeded
                        emit_progress(
                            "model_success",
                            model=config.model,
                            verdict=review_result.verdict if review_result else "UNKNOWN",
                        )
                        break  # Success, exit retry loop
                    except Exception as model_error:
                        # Track failed model
                        if config.model:
                            escalation_state.failed_models.add(config.model)

                        # Emit progress: model failed
                        emit_progress(
                            "model_failed",
                            model=config.model,
                            reason=str(model_error)[:200],
                            escalation=model_escalation_count,
                        )

                        print(
                            f"  [MODEL ERROR] {config.model} failed: {model_error}",
                            file=sys.stderr,
                        )

                        # Check if escalation is allowed
                        if config.no_escalate:
                            emit_progress("abort", reason="no_escalate_flag")
                            print("  [ABORT] --no-escalate set, not retrying", file=sys.stderr)
                            raise

                        # Check escalation limit
                        if model_escalation_count >= max_model_escalations:
                            emit_progress(
                                "abort",
                                reason="escalation_limit",
                                tried=model_escalation_count,
                                max=max_model_escalations,
                            )
                            print(
                                f"  [ABORT] Model escalation limit reached"
                                f" ({max_model_escalations} fallbacks tried)",
                                file=sys.stderr,
                            )
                            raise

                        # Try next model in escalation path
                        next_model, next_tier = get_next_model_from_state(escalation_state)
                        if not next_model:
                            emit_progress("abort", reason="no_more_models")
                            print("  [ABORT] No more models in escalation path", file=sys.stderr)
                            raise

                        # Increment ONLY after getting valid next_model
                        model_escalation_count += 1

                        # Emit progress: escalating to next model
                        emit_progress(
                            "escalation",
                            from_model=config.model,
                            to_model=next_model,
                            tier=next_tier,
                            escalation=model_escalation_count,
                            max_escalations=max_model_escalations,
                        )

                        print(
                            f"  [ESCALATE] Retrying with {next_model}"
                            f" ({next_tier} tier)"
                            f" (escalation {model_escalation_count}/{max_model_escalations})",
                            file=sys.stderr,
                        )
                        config.model = next_model
                        escalation_state.current_tier_idx = (
                            ESCALATION_PATHS.get(escalation_state.strategy, []).index(next_tier)
                            if next_tier in ESCALATION_PATHS.get(escalation_state.strategy, [])
                            else escalation_state.current_tier_idx
                        )

                if review_result is None:
                    raise RuntimeError("All models in escalation path failed")

                usage.add_review(review_result)
            finally:
                # Always restore original state to prevent leaks across iterations
                config.variant = original_variant
                config.model = original_model

            # Capture real Kilo session ID for subsequent calls (enables --session flag)
            # Real Kilo sessions are longer (30+ chars) than our local tracking IDs (20 chars)
            # Validate to prevent path traversal via malicious/corrupted response
            kilo_session = review_result.session_id or ""
            if kilo_session and len(kilo_session) > 20 and kilo_session != config.session_id:
                if _is_valid_session_id(kilo_session):
                    config.session_id = kilo_session
                    session_state.session_id = kilo_session
                else:
                    print(
                        f"Warning: Invalid session_id from Kilo response: "
                        f"{kilo_session!r}, ignoring",
                        file=sys.stderr,
                    )

            # Save iteration output
            if config.persist_session:
                review_file = SESSION_DIR / local_session_id / f"review_iter_{iteration}.json"
                review_file.parent.mkdir(parents=True, exist_ok=True)
                with open(review_file, "w") as f:
                    json.dump(
                        {
                            "iteration": iteration,
                            "verdict": review_result.verdict,
                            "summary": review_result.summary,
                            "issues": [i.to_dict() for i in review_result.issues],
                            # NEW: must persist coverage
                            "plan_coverage": review_result.plan_coverage,
                            "notes": review_result.notes,
                            "stats": review_result.stats,
                            "tokens": {
                                "input": review_result.input_tokens,
                                "output": review_result.output_tokens,
                            },
                            "cost": review_result.cost,
                        },
                        f,
                        indent=2,
                    )

            # Update session state and track verdict for next iteration
            session_state.iteration = iteration
            session_state.last_used_at = datetime.now(UTC).isoformat()
            session_state.last_verdict = review_result.verdict
            session_state.last_issues = [i.to_dict() for i in review_result.issues]

            # Update issue-state persistence
            if config.tracked_review_id:
                # Only auto-close unseen issues for full-scope auto-fix reviews
                # Conservative: do NOT auto-close for verify mode, partial scope, or batched runs
                allow_auto_close = (
                    config.auto_fix
                    and not config.verify_mode
                    and config.review_mode == "staged"
                    and len(files) <= config.max_files_per_batch
                )
                update_issue_state(
                    tracked_review_id=config.tracked_review_id,
                    current_issues=[i.to_dict() for i in review_result.issues],
                    iteration=iteration,
                    allow_auto_fix_close=allow_auto_close,
                )

            # Check if clean
            if review_result.verdict == "PASS":
                # Final gate: if this PASS was from a non-max variant and we haven't
                # done the max-variant verification yet, continue to next iteration
                # so should_use_max_variant can trigger final_gate.
                # If this PASS was already the final_gate verification (max variant),
                # or if the user explicitly chose max, we're done.
                # Skip final-gate when auto_fix=False (e.g. `review` command) since
                # no fixes happen between iterations — re-reviewing unchanged code
                # with max variant would waste tokens with no benefit.
                # Gated by KILO_ENABLE_PASS_VERIFY (default OFF)
                if (
                    KILO_ENABLE_PASS_VERIFY
                    and current_variant != "max"
                    and iteration < effective_max
                    and config.auto_fix
                ):
                    # Record PASS so next iteration triggers final_gate max verification
                    previous_verdict = review_result.verdict
                    print(
                        "  PASS at variant=high — scheduling final max-variant verification...",
                        file=sys.stderr,
                    )
                    continue

                # =================================================================
                # FALSE NEGATIVE MITIGATION (Per Spec Phase 4)
                # =================================================================
                # "Zero issues on critical code is a red flag" - all 3 models agreed
                # If cheap model says PASS on high-risk code, verify with stronger tier
                # Respect --no-escalate and --max-cost flags
                # Per spec: critical → Prime, high → Strong
                # Skip verification if user explicitly set --model (strategy == "override")
                verify_tier = "Prime" if escalation_state.risk_level == "critical" else "Strong"
                verify_tier_cost = TIER_ESTIMATED_COST.get(verify_tier, 3.0)
                can_verify = (
                    config.verify_high_risk
                    and escalation_state.strategy != "override"  # Skip if user set --model
                    and not config.no_escalate  # Respect no-escalate flag
                    and not escalation_state.verification_performed
                    and (config.max_cost is None or verify_tier_cost <= config.max_cost)
                    and should_verify_pass(
                        escalation_state.risk_level,
                        escalation_state.get_current_tier(),
                        len(review_result.issues),
                    )
                )
                if can_verify:
                    escalation_state.verification_performed = True
                    # Get appropriate tier model for verification
                    # (Prime for critical, Strong for high)
                    verify_model = get_tier_model(verify_tier, escalation_state.failed_models)
                    if verify_model and verify_model != config.model:
                        print(
                            f"  [VERIFY] Zero issues on {escalation_state.risk_level}-risk code. "
                            f"Verifying with {verify_model}...",
                            file=sys.stderr,
                        )
                        # Create a copy of config with stronger model
                        original_model = config.model
                        config.model = verify_model
                        # Run verification review
                        verify_result = await _run_single_batch_review(
                            files=files,
                            config=config,
                            iteration=iteration,
                            previous_issues=None,
                        )
                        config.model = original_model  # Restore original
                        usage.add_review(verify_result)

                        if verify_result.verdict == "FAIL" and verify_result.issues:
                            # Cheap model missed issues! Log for quality tracking
                            escalation_state.false_negative_detected = True
                            print(
                                f"  [FALSE NEGATIVE] Cheap model missed "
                                f"{len(verify_result.issues)} issue(s)!",
                                file=sys.stderr,
                            )

                            # Write quality metrics entry per spec section 5.2
                            quality_entry = {
                                "timestamp": datetime.now().isoformat(),
                                "files": [str(f) for f in files],
                                "risk_level": escalation_state.risk_level,
                                "initial_tier": escalation_state.get_current_tier(),
                                "initial_verdict": "PASS",
                                "initial_findings": 0,
                                "verification_tier": verify_tier,
                                "verification_verdict": "FAIL",
                                "verification_findings": len(verify_result.issues),
                                "false_negative": True,
                                "model_initial": original_model,
                                "model_verification": verify_model,
                            }
                            if KILO_ENABLE_AUDIT:
                                try:
                                    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
                                    with open(METRICS_FILE, "a") as f:
                                        f.write(json.dumps(quality_entry) + "\n")
                                except OSError as e:
                                    print(f"  [METRICS] Failed to write: {e}", file=sys.stderr)

                            # Use verification result and skip PASS return
                            review_result = verify_result
                            # Fall through to issue processing below (skip PASS block)

                # Only return PASS if review_result is still PASS after verification
                if review_result.verdict == "PASS":
                    # =================================================================
                    # 5% AUDIT SAMPLING (Per Spec Phase 5)
                    # =================================================================
                    # Random sampling of PASS verdicts for quality monitoring
                    # Gated by KILO_ENABLE_AUDIT (default OFF)
                    if KILO_ENABLE_AUDIT:
                        import random

                        if random.random() < AUDIT_SAMPLE_RATE:
                            audit_entry = {
                                "timestamp": datetime.now().isoformat(),
                                "session_id": config.session_id or local_session_id,
                                "files": [str(f) for f in files_reviewed],
                                "tier": escalation_state.get_current_tier(),
                                "model": config.model,
                                "risk_level": escalation_state.risk_level,
                                "verdict": "PASS",
                                "iterations": iteration,
                                "verification_performed": escalation_state.verification_performed,
                                "false_negative_detected": escalation_state.false_negative_detected,
                            }
                            try:
                                AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
                                with open(AUDIT_LOG_FILE, "a") as f:
                                    f.write(json.dumps(audit_entry) + "\n")
                                print(
                                    "  [AUDIT] Sampled PASS verdict for quality monitoring",
                                    file=sys.stderr,
                                )
                            except OSError as e:
                                print(f"  [AUDIT] Failed to write audit log: {e}", file=sys.stderr)

                    # Definitive PASS (either max-variant verification or at iteration limit)
                    session_state.status = "completed"
                    session_state.usage = asdict(usage)
                    if config.persist_session:
                        save_session(session_state)

                    # Emit progress: review complete
                    emit_progress(
                        "complete",
                        status="CLEAN",
                        verdict="PASS",
                        model=config.model,
                        iterations=iteration,
                        files_count=len(files_reviewed),
                    )

                    return FinalReport(
                        status="CLEAN",
                        verdict="PASS",
                        iterations=iteration,
                        files_reviewed=files_reviewed,
                        all_issues=all_issues,
                        all_fixes=all_fixes,
                        remaining_issues=[],
                        usage=asdict(usage),
                        session_id=config.session_id or "",
                        summary=(
                            f"Review passed after {iteration} iteration(s). {review_result.summary}"
                        ),
                    )

            previous_verdict = review_result.verdict  # For max variant decision

            # Collect issues
            current_issue_dicts = [i.to_dict() for i in review_result.issues]

            # Filter out repeated issues (likely false positives)
            filtered_issues, false_positives = filter_repeated_issues(
                current_issue_dicts, issue_history, threshold=2
            )
            if false_positives:
                false_positives_total.extend(false_positives)
                print(
                    f"  [FALSE POSITIVE] Filtered {len(false_positives)} repeated issue(s) "
                    f"(appeared 2+ times after fix)",
                    file=sys.stderr,
                )
                for fp in false_positives:
                    print(
                        f"    - {fp.get('file')}:{fp.get('lines')} [{fp.get('category')}]",
                        file=sys.stderr,
                    )

            all_issues.extend(current_issue_dicts)

            # Filter to actionable issues (based on min_severity)
            # Use dict lookup with safe default (unknown severities map to MAJOR=1)
            # to prevent ValueError from LLM-generated unexpected severity strings
            severity_rank = {"BLOCKER": 0, "MAJOR": 1, "MINOR": 2}
            min_rank = severity_rank.get(config.min_severity, 1)
            actionable = [
                i for i in review_result.issues if severity_rank.get(i.severity, 1) <= min_rank
            ]

            if not actionable:
                # No actionable issues, but check if verdict was actually PASS
                # (could be FAIL with no issues due to parse errors)
                if review_result.verdict == "FAIL" and not review_result.issues:
                    # Kilo returned FAIL but no issues - likely a parse error or incomplete run
                    session_state.status = "failed"
                    session_state.usage = asdict(usage)
                    if config.persist_session:
                        save_session(session_state)

                    emit_progress(
                        "complete",
                        status="ERROR",
                        verdict="FAIL",
                        model=config.model,
                        reason="no_issues_on_fail",
                    )

                    return FinalReport(
                        status="ERROR",
                        verdict="FAIL",
                        iterations=iteration,
                        files_reviewed=files_reviewed,
                        all_issues=all_issues,
                        all_fixes=all_fixes,
                        remaining_issues=[],
                        usage=asdict(usage),
                        session_id=config.session_id or "",
                        summary=(
                            f"Review failed but returned no issues (possible parse error)."
                            f" {review_result.summary}"
                        ),
                    )

                # Only MINOR issues remain - this is a pass
                session_state.status = "completed"
                session_state.usage = asdict(usage)
                if config.persist_session:
                    save_session(session_state)

                emit_progress(
                    "complete",
                    status="CLEAN",
                    verdict="PASS",
                    model=config.model,
                    iterations=iteration,
                    minor_issues=len(review_result.issues),
                )

                return FinalReport(
                    status="CLEAN",
                    verdict="PASS",
                    iterations=iteration,
                    files_reviewed=files_reviewed,
                    all_issues=all_issues,
                    all_fixes=all_fixes,
                    remaining_issues=[i.to_dict() for i in review_result.issues],
                    usage=asdict(usage),
                    session_id=config.session_id or "",
                    summary=f"Review passed (only MINOR issues). {review_result.summary}",
                )

            # Skip fix phase if disabled
            if not config.auto_fix:
                session_state.status = "completed"
                session_state.usage = asdict(usage)
                if config.persist_session:
                    save_session(session_state)

                emit_progress(
                    "complete",
                    status="NEEDS_FIX",
                    verdict="FAIL",
                    model=config.model,
                    issues_count=len(review_result.issues),
                )

                return FinalReport(
                    status="NEEDS_FIX",
                    verdict="FAIL",
                    iterations=iteration,
                    files_reviewed=files_reviewed,
                    all_issues=all_issues,
                    all_fixes=all_fixes,
                    remaining_issues=[i.to_dict() for i in review_result.issues],
                    usage=asdict(usage),
                    session_id=config.session_id or "",
                    summary=f"Review found issues (auto-fix disabled). {review_result.summary}",
                )

            # PHASE 2: Fix
            print(f"  Fixing {len(actionable)} issues...", file=sys.stderr)
            fix_result = await run_fix(
                issues=actionable,
                config=config,
            )
            usage.add_fix(fix_result)

            # Save fix output
            if config.persist_session:
                fix_file = SESSION_DIR / local_session_id / f"fix_iter_{iteration}.json"
                with open(fix_file, "w") as f:
                    json.dump(asdict(fix_result), f, indent=2, default=str)

            all_fixes.extend(fix_result.fixes_applied)

            # Save diff to session for analysis (not shown in console)
            if fix_result.diff and config.persist_session:
                diff_file = SESSION_DIR / local_session_id / f"diff_iter_{iteration}.patch"
                diff_file.write_text(fix_result.diff, encoding="utf-8")
                print(f"  [DIFF] Saved to {diff_file}", file=sys.stderr)

            # Check if fixes were applied
            if fix_result.total_fixed == 0 and fix_result.needs_manual:
                session_state.status = "needs_manual"
                session_state.usage = asdict(usage)
                if config.persist_session:
                    save_session(session_state)

                return FinalReport(
                    status="NEEDS_MANUAL",
                    verdict="FAIL",
                    iterations=iteration,
                    files_reviewed=files_reviewed,
                    all_issues=all_issues,
                    all_fixes=all_fixes,
                    remaining_issues=[i.to_dict() for i in actionable],
                    usage=asdict(usage),
                    session_id=config.session_id or "",
                    summary=f"Some issues require manual fix: {fix_result.needs_manual}",
                )

            # Prepare for re-review
            previous_issues = [i.to_dict() for i in review_result.issues]

        # Max iterations reached
        session_state.status = "max_iterations"
        session_state.usage = asdict(usage)
        if config.persist_session:
            save_session(session_state)

        return FinalReport(
            status="MAX_ITERATIONS",
            verdict="FAIL",
            iterations=iteration,
            files_reviewed=files_reviewed,
            all_issues=all_issues,
            all_fixes=all_fixes,
            remaining_issues=previous_issues or [],
            usage=asdict(usage),
            session_id=config.session_id or "",
            summary=f"Max iterations ({config.max_iterations}) reached with issues remaining.",
        )

    except Exception:
        session_state.status = "failed"
        session_state.usage = asdict(usage)
        if config.persist_session:
            save_session(session_state)
        raise


# =============================================================================
# PRE-REVIEW VALIDATION
# =============================================================================


def pre_review_checks(files: list[Path]) -> list[str]:
    """Run fast validation before Kilo review to fail fast.

    Returns list of blocking issues that should prevent review.
    """
    issues = []
    max_file_size = 500 * 1024  # 500KB

    for f in files:
        if not f.exists():
            issues.append(f"File does not exist: {f}")
            continue
        size = f.stat().st_size
        if size > max_file_size:
            issues.append(f"File too large: {f} ({size:,} bytes, max {max_file_size:,})")

    for f in [f for f in files if f.suffix == ".py"]:
        if not f.exists():
            continue
        try:
            content = f.read_text(encoding="utf-8")
            compile(content, str(f), "exec")
        except SyntaxError as e:
            issues.append(f"Syntax error in {f}:{e.lineno}: {e.msg}")
        except UnicodeDecodeError as e:
            issues.append(f"Encoding error in {f}: {e}")
        except Exception:
            pass

    for f in files:
        if not f.exists():
            continue
        if f.stat().st_size == 0:
            issues.append(f"Empty file: {f}")

    return issues


# =============================================================================
# OUTPUT FORMATTING
# =============================================================================


def format_report_json(report: FinalReport) -> str:
    """Format report as JSON."""
    return json.dumps(asdict(report), indent=2, default=str)


def format_report_text(report: FinalReport) -> str:
    """Format report as human-readable text."""
    lines = []

    # Status line
    status_emoji = {
        "CLEAN": "✅",
        "NEEDS_FIX": "❌",
        "NEEDS_MANUAL": "🔧",
        "MAX_ITERATIONS": "⚠️",
        "ERROR": "💥",
    }
    emoji = status_emoji.get(report.status, "❓")
    lines.append(f"{emoji} CODE REVIEW: {report.verdict} ({report.iterations} iteration(s))")
    lines.append("")
    lines.append(report.summary)
    lines.append("")

    # Files reviewed
    lines.append(f"📁 Files reviewed: {len(report.files_reviewed)}")
    for f in report.files_reviewed[:5]:
        lines.append(f"   - {f}")
    if len(report.files_reviewed) > 5:
        lines.append(f"   ... and {len(report.files_reviewed) - 5} more")
    lines.append("")

    # Issues
    if report.remaining_issues:
        lines.append(f"🔴 Remaining issues: {len(report.remaining_issues)}")
        for issue in report.remaining_issues[:10]:
            sev = issue.get("severity", "?")
            cat = issue.get("category", "?")
            file = issue.get("file", "?")
            line = issue.get("lines", "?")
            why = issue.get("why", "")
            lines.append(f"   [{sev}] {cat}: {file}:{line}")
            if why:
                lines.append(f"      └─ {why[:80]}")
        if len(report.remaining_issues) > 10:
            lines.append(f"   ... and {len(report.remaining_issues) - 10} more")
        lines.append("")

    # Fixes applied
    if report.all_fixes:
        lines.append(f"🔧 Fixes applied: {len(report.all_fixes)}")
        for fix in report.all_fixes[:5]:
            file = fix.get("file", "?")
            desc = fix.get("fix_description", fix.get("original_issue", ""))
            status = fix.get("status", "?")
            lines.append(f"   [{status}] {file}: {desc[:60]}")
        if len(report.all_fixes) > 5:
            lines.append(f"   ... and {len(report.all_fixes) - 5} more")
        lines.append("")

    # Usage stats with separate review/fix breakdown
    usage = report.usage
    review_tokens = usage.get("review_input_tokens", 0) + usage.get("review_output_tokens", 0)
    fix_tokens = usage.get("fix_input_tokens", 0) + usage.get("fix_output_tokens", 0)
    review_cost = usage.get("review_cost_usd", 0.0)
    fix_cost = usage.get("fix_cost_usd", 0.0)

    lines.append("📊 This Run:")
    lines.append(f"   Session: {report.session_id}")
    lines.append(
        f"   Review: {review_tokens:,} tokens, ${review_cost:.4f}"
        f" ({usage.get('review_calls', 0)} calls)"
    )
    lines.append(
        f"   Fix:    {fix_tokens:,} tokens, ${fix_cost:.4f} ({usage.get('fix_calls', 0)} calls)"
    )
    lines.append(
        f"   Total:  {usage.get('total_tokens', 0):,} tokens, ${usage.get('cost_usd', 0):.4f}"
    )

    return "\n".join(lines)


# =============================================================================
# CLI
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Kilo-powered iterative code review",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Review specific files
  python scripts/kilo_code_review.py review src/file.py

  # Review with auto-fix loop
  python scripts/kilo_code_review.py auto-fix src/ --max-iterations 3

  # Review staged files
  python scripts/kilo_code_review.py staged

  # Review with specific model and variant
  python scripts/kilo_code_review.py auto-fix src/ --model anthropic/claude-opus-4-6 --variant max

  # Continue existing session
  python scripts/kilo_code_review.py auto-fix src/ --session continue
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Common arguments
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--model",
        default=None,
        help="Override model (default: auto-routed based on file paths)",
    )
    common.add_argument(
        "--variant", default="high", choices=list(VALID_VARIANTS), help="Reasoning level"
    )
    common.add_argument(
        "--review-agent", default="ask", choices=list(VALID_AGENTS), help="Agent for review phase"
    )
    common.add_argument(
        "--fix-agent", default="code", choices=list(VALID_AGENTS), help="Agent for fix phase"
    )
    common.add_argument("--session", help="Session ID (use 'continue' for latest)")
    common.add_argument(
        "--tracked-review-id",
        help="Stable review cycle ID used to scope session continuation",
    )
    common.add_argument(
        "--output", default="text", choices=["json", "text", "markdown"], help="Output format"
    )
    common.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    common.add_argument("--plan", help="Traycer plan/spec text or file path")
    common.add_argument(
        "--skip-categories",
        help="Comma-separated categories to skip (SPEC,SECURITY,CONFIG,EDGE,DOCS)",
    )
    common.add_argument(
        "--doc-mode",
        action="store_true",
        help="Use lighter doc-only review (auto-detected for .md files)",
    )
    common.add_argument(
        "--skip-precommit",
        action="store_true",
        help="Skip pre-commit checks (not recommended)",
    )
    common.add_argument(
        "--strategy",
        default=None,
        choices=["free", "economy", "standard", "premium", "critical"],
        help=(
            "Cost strategy: free ($0), economy (~$0.02/M), standard (~$0.5/M),"
            " premium (~$3/M), critical (~$5/M)"
        ),
    )
    common.add_argument(
        "--max-cost",
        type=float,
        default=None,
        help="Max cost per review in $/M tokens (stops escalation at budget)",
    )
    common.add_argument(
        "--no-escalate",
        action="store_true",
        help="Stay at initial tier, don't escalate on failure",
    )
    common.add_argument(
        "--verify-high-risk",
        action="store_true",
        default=None,
        help="Verify PASS on high-risk code with stronger model (default: True)",
    )

    # review command
    review_parser = subparsers.add_parser(
        "review", parents=[common], help="Review files (read-only)"
    )
    review_parser.add_argument("files", nargs="+", help="Files or directories to review")
    review_parser.add_argument(
        "--mode", default="full", choices=["full", "diff_only"], help="Review mode"
    )

    # auto-fix command
    autofix_parser = subparsers.add_parser(
        "auto-fix", parents=[common], help="Review and fix in a loop"
    )
    autofix_parser.add_argument("files", nargs="+", help="Files or directories to review")
    autofix_parser.add_argument(
        "--max-iterations", type=int, default=3, help="Max review-fix cycles"
    )
    autofix_parser.add_argument(
        "--min-severity",
        default="MAJOR",
        choices=["BLOCKER", "MAJOR", "MINOR"],
        help="Min severity to fix",
    )
    autofix_parser.add_argument(
        "--mode", default="full", choices=["full", "diff_only"], help="Review mode"
    )

    # staged command
    staged_parser = subparsers.add_parser(
        "staged", parents=[common], help="Review git staged files (report-only by default)"
    )
    staged_parser.add_argument(
        "--max-iterations", type=int, default=3, help="Max review-fix cycles (only with --fix)"
    )
    staged_parser.add_argument(
        "--fix",
        action="store_true",
        help="Enable auto-fix by Kilo code agent (default: report-only)",
    )

    # changed command
    changed_parser = subparsers.add_parser(
        "changed", parents=[common], help="Review git changed files (report-only by default)"
    )
    changed_parser.add_argument(
        "--max-iterations", type=int, default=3, help="Max review-fix cycles (only with --fix)"
    )
    changed_parser.add_argument(
        "--fix",
        action="store_true",
        help="Enable auto-fix by Kilo code agent (default: report-only)",
    )

    # verify command (cheaper workflow: review-only → manual fix → verify)
    verify_parser = subparsers.add_parser(
        "verify",
        parents=[common],
        help="Verify manual fixes (cheap: tells Kilo what was fixed, asks to verify)",
    )
    verify_parser.add_argument("files", nargs="+", help="Files that were manually fixed")
    verify_parser.add_argument(
        "--fixes",
        required=True,
        help="Description of fixes applied (text or @file path)",
    )

    # stats command (analyze usage logs)
    stats_parser = subparsers.add_parser(
        "stats",
        help="Show usage statistics from review sessions",
    )
    stats_parser.add_argument(
        "--by-filetype",
        action="store_true",
        help="Group statistics by file type",
    )
    stats_parser.add_argument(
        "--by-model",
        action="store_true",
        help="Group statistics by model",
    )
    stats_parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to analyze (default: 30)",
    )

    return parser.parse_args()


def load_plan(plan_arg: str | None) -> str | None:
    """Load plan from file or use as-is."""
    if not plan_arg:
        return None

    plan_path = Path(plan_arg)
    if plan_path.exists() and plan_path.is_file():
        # Validate the plan file is within the project root to prevent
        # accidental or malicious reading of files outside the project
        # (e.g. /etc/passwd, private keys) via the --plan CLI argument.
        try:
            plan_path.resolve(strict=True).relative_to(get_project_root().resolve())
        except ValueError:
            raise ValueError(
                f"Plan file '{plan_arg}' is outside the project root. "
                "Only files within the project directory are allowed."
            )
        return plan_path.read_text()

    return plan_arg


# =============================================================================
# PRE-COMMIT INTEGRATION
# =============================================================================

MAX_PRECOMMIT_ITERATIONS = 5


def run_precommit(files: list[Path], max_iterations: int = MAX_PRECOMMIT_ITERATIONS) -> bool:
    """
    Run pre-commit on specified files, auto-fixing issues until clean.

    Args:
        files: List of files to check
        max_iterations: Max fix-and-retry cycles

    Returns:
        True if pre-commit passes, False if still failing after max iterations
    """
    if not files:
        return True

    # Check if pre-commit is available
    precommit_path = shutil.which("pre-commit")
    if not precommit_path:
        print("[PRE-COMMIT] pre-commit not found, skipping...", file=sys.stderr)
        return True

    file_paths = [str(f) for f in files]
    project_root = get_project_root()
    previous_output = ""  # Track output to detect infinite loops

    for iteration in range(1, max_iterations + 1):
        print(f"\n[PRE-COMMIT] Iteration {iteration}/{max_iterations}...", file=sys.stderr)

        try:
            result = subprocess.run(
                [precommit_path, "run", "--files"] + file_paths,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=project_root,
            )

            if result.returncode == 0:
                print("[PRE-COMMIT] ✅ All checks passed!", file=sys.stderr)
                return True

            # Pre-commit failed - check if files were modified (auto-fixed)
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            output = stdout + stderr

            # Check for "files were modified" which means auto-fix happened
            if "files were modified" in output.lower():
                print(
                    f"[PRE-COMMIT] Files auto-fixed, re-running... ({iteration}/{max_iterations})",
                    file=sys.stderr,
                )
                continue

            # Check for specific fixable issues and try to fix them
            if "ruff" in output.lower() and iteration < max_iterations:
                # Check if we're stuck on the same error
                if previous_output and output == previous_output:
                    print(
                        "[PRE-COMMIT] ❌ No progress made - same errors as previous iteration",
                        file=sys.stderr,
                    )
                    print(
                        "[PRE-COMMIT] Ruff cannot auto-fix these issues. Please fix manually.",
                        file=sys.stderr,
                    )
                    return False

                # Try running ruff --fix directly
                print("[PRE-COMMIT] Running ruff --fix...", file=sys.stderr)
                subprocess.run(
                    ["ruff", "check", "--fix"] + file_paths,
                    capture_output=True,
                    cwd=project_root,
                    timeout=60,
                )
                subprocess.run(
                    ["ruff", "format"] + file_paths,
                    capture_output=True,
                    cwd=project_root,
                    timeout=60,
                )

                # Store output to detect if next iteration is the same
                previous_output = output
                continue

            # Non-fixable failure - show output and return False
            print(f"[PRE-COMMIT] ❌ Failed (iteration {iteration}):", file=sys.stderr)
            # Show last 50 lines of output
            lines = output.strip().split("\n")
            for line in lines[-50:]:
                print(f"  {line}", file=sys.stderr)

            if iteration < max_iterations:
                print(
                    f"[PRE-COMMIT] Retrying... ({iteration}/{max_iterations})",
                    file=sys.stderr,
                )
            else:
                print(
                    f"[PRE-COMMIT] ❌ Max iterations ({max_iterations}) reached. "
                    "Fix remaining issues manually before Kilo review.",
                    file=sys.stderr,
                )
                return False

        except subprocess.TimeoutExpired:
            print(f"[PRE-COMMIT] Timeout after 120s (iteration {iteration})", file=sys.stderr)
            return False
        except FileNotFoundError:
            print("[PRE-COMMIT] pre-commit not found", file=sys.stderr)
            return True  # Skip if not installed

    return False


async def main() -> int:
    """Main entry point."""
    # Initialize high-risk paths from env var (deferred from module level to avoid side effects)
    # CLI gets verbose=True to show routing message; programmatic calls use verbose=False
    _init_high_risk_paths(verbose=True)

    args = parse_args()

    # Handle stats command (no async needed)
    if args.command == "stats":
        run_stats_command(
            by_filetype=getattr(args, "by_filetype", False),
            by_model=getattr(args, "by_model", False),
            days=getattr(args, "days", 30),
        )
        return 0

    # Validate model if user specified one (check deprecation, refresh cache daily)
    # If None, model will be auto-selected by diff-scoped routing in review_loop
    validated_model = get_validated_model(args.model) if args.model else None

    # Get strategy from args or env var
    strategy = getattr(args, "strategy", None) or os.getenv("KILO_DEFAULT_STRATEGY")
    max_cost_str = os.getenv("KILO_MAX_COST")
    max_cost = getattr(args, "max_cost", None)
    if max_cost is None and max_cost_str:
        with contextlib.suppress(ValueError):
            max_cost = float(max_cost_str)

    # Get verify_high_risk from args or env var (default: True per spec)
    verify_high_risk_arg = getattr(args, "verify_high_risk", None)
    if verify_high_risk_arg is None:
        env_val = os.getenv("KILO_VERIFY_HIGH_RISK", "true").lower()
        verify_high_risk = env_val in ("true", "1", "yes")
    else:
        verify_high_risk = verify_high_risk_arg

    # Build config
    config = KiloReviewConfig(
        model=validated_model,
        variant=args.variant,
        review_agent=args.review_agent,
        fix_agent=args.fix_agent,
        session_id=args.session,
        tracked_review_id=args.tracked_review_id,
        output_format=args.output,
        verbose=args.verbose,
        traycer_plan=load_plan(getattr(args, "plan", None)),
        skip_categories=parse_skip_categories(getattr(args, "skip_categories", None)),
        doc_mode=getattr(args, "doc_mode", False),
        strategy=strategy,
        max_cost=max_cost,
        no_escalate=getattr(args, "no_escalate", False),
        verify_high_risk=verify_high_risk,
    )

    # Get files based on command
    if args.command in ("review", "auto-fix"):
        files = collect_files(args.files)
        config.review_mode = getattr(args, "mode", "full")
    elif args.command == "staged":
        # ENFORCE: auto-stage ALL changes before review (agents miss unstaged files)
        unstaged_before = get_changed_files()
        staged_before = get_staged_files()
        unstaged_only = [f for f in unstaged_before if f not in staged_before]
        if unstaged_only:
            print(
                f"\n📌 Auto-staging {len(unstaged_only)} unstaged file(s) for complete review:",
                file=sys.stderr,
            )
            for uf in unstaged_only[:10]:
                print(f"   + {uf.name}", file=sys.stderr)
            if len(unstaged_only) > 10:
                print(f"   ... and {len(unstaged_only) - 10} more", file=sys.stderr)
            git_path = shutil.which("git")
            if git_path:
                subprocess.run(
                    [git_path, "add", "-A"],
                    capture_output=True,
                    check=False,
                )
                print("   ✓ All changes staged.\n", file=sys.stderr)
        files = get_staged_files()
        config.review_mode = "staged"
    elif args.command == "changed":
        files = get_changed_files()
        config.review_mode = "diff_only"
    elif args.command == "verify":
        files = collect_files(args.files)
        config.review_mode = "full"
        # Load fixes description
        fixes_desc = load_plan(args.fixes)  # Reuse load_plan for @file support
        if not fixes_desc:
            print("Error: --fixes is required for verify command", file=sys.stderr)
            return 2
        config.fixes_description = fixes_desc
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 2

    if not files:
        print("No files to review.", file=sys.stderr)
        return 0

    # Run pre-commit checks first (unless skipped)
    if not getattr(args, "skip_precommit", False):
        print("\n" + "=" * 60, file=sys.stderr)
        print("PHASE 1: PRE-COMMIT CHECKS", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        if not run_precommit(files):
            print(
                "\n❌ Pre-commit checks failed after max iterations. "
                "Fix remaining issues manually or use --skip-precommit.",
                file=sys.stderr,
            )
            return 2
        print("\n" + "=" * 60, file=sys.stderr)
        print("PHASE 2: KILO AI REVIEW", file=sys.stderr)
        print("=" * 60, file=sys.stderr)

    # Set iteration and auto-fix based on command
    if args.command == "review":
        config.max_iterations = 1
        config.auto_fix = False
    elif args.command == "auto-fix":
        config.max_iterations = args.max_iterations
        config.min_severity = args.min_severity
        config.auto_fix = True
    elif args.command in ("staged", "changed"):
        config.max_iterations = getattr(args, "max_iterations", 3)
        # Default: report-only. Use --fix to enable auto-fix by Kilo code agent.
        config.auto_fix = getattr(args, "fix", False)
    elif args.command == "verify":
        config.max_iterations = 1
        config.auto_fix = False
        config.verify_mode = True

    try:
        # Run review loop
        report = await review_loop(files, config)

        # Log usage to cumulative tracking file
        log_usage(report)

        # Show cumulative usage
        cumulative = get_cumulative_usage()

        # Output result
        if config.output_format == "json":
            print(format_report_json(report))
        else:
            print(format_report_text(report))
            # Show cumulative stats with review/fix breakdown
            print(f"\n📈 Project Total ({cumulative['total_runs']} runs):", file=sys.stderr)
            print(
                f"   Review: {cumulative['review_tokens']:,} tokens,"
                f" ${cumulative['review_cost_usd']:.4f}",
                file=sys.stderr,
            )
            print(
                f"   Fix:    {cumulative['fix_tokens']:,} tokens,"
                f" ${cumulative['fix_cost_usd']:.4f}",
                file=sys.stderr,
            )
            print(
                f"   Total:  {cumulative['total_tokens']:,} tokens,"
                f" ${cumulative['total_cost_usd']:.4f}",
                file=sys.stderr,
            )

        # Save final report (use session_id from report, with path traversal guard)
        if config.persist_session and report.session_id and _is_valid_session_id(report.session_id):
            final_file = SESSION_DIR / report.session_id / "final_report.json"
            final_file.parent.mkdir(parents=True, exist_ok=True)
            with open(final_file, "w") as f:
                f.write(format_report_json(report))

        # Return exit code
        return 0 if report.verdict == "PASS" else 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
