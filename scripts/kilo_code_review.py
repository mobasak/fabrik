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
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# =============================================================================
# CONFIGURATION
# =============================================================================

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
VALID_CATEGORIES = {"SPEC", "SECURITY", "CONFIG", "EDGE", "DOCS"}

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
        f"Warning: Invalid KILO_MAX_RETRIES value '{os.getenv('KILO_MAX_RETRIES')}', using default 3",
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
REASONING_MODELS = {
    "kilo/anthropic/claude-opus-4.6",
    "kilo/anthropic/claude-sonnet-4.6",
    "kilo/anthropic/claude-opus-4.5",
    "kilo/anthropic/claude-sonnet-4.5",
    "kilo/openai/gpt-5.2-codex",
    "kilo/openai/gpt-5.1-codex-max",
    "kilo/openai/gpt-5.3-codex",
    "kilo/openai/gpt-5.3-codex-spark",
    "kilo/openai/o3",
    "kilo/openai/o3-mini",
    "kilo/google/gemini-2.5-pro",
    "kilo/google/gemini-3-flash-preview",
    "kilo/google/gemini-3.1-pro-preview",
}

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

# Ordered fallback chain (tried in order if model unavailable)
MODEL_FALLBACK_CHAIN = [
    "kilo/anthropic/claude-opus-4.6",  # 1. Primary - best quality
    "kilo/openai/gpt-5.3-codex",  # 2. Opus-like quality, cheaper
    "kilo/anthropic/claude-sonnet-4.6",  # 3. Cheaper Anthropic
    "kilo/openai/gpt-5.2-codex",  # 4. OpenAI alternative
    "kilo/google/gemini-3.1-pro-preview",  # 5. Heavy reasoning
    "kilo/openai/gpt-5.3-codex-spark",  # 6. Fast iteration
    "kilo/openai/o3-mini",  # 7. Fast reasoning
    "kilo/google/gemini-2.5-pro",  # 8. Next-gen Google
    "kilo/google/gemini-3-flash-preview",  # 9. Speed fallback
]

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

# Extend high-risk paths from env var (comma-separated, added to defaults)
_env_high_risk = os.getenv("KILO_HIGH_RISK_PATHS")
if _env_high_risk:
    _extra_paths = [p.strip() for p in _env_high_risk.split(",") if p.strip()]
    HIGH_RISK_DIR_PREFIXES.extend(_extra_paths)
    print(
        f"[ROUTING] Extended high-risk paths with {len(_extra_paths)} entries from KILO_HIGH_RISK_PATHS",
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

# Project root for path validation (will be set to git root or CWD at runtime)
# This is initialized lazily to avoid subprocess calls at import time
_PROJECT_ROOT: Path | None = None


def _is_valid_session_id(session_id: str) -> bool:
    """Validate session_id format to prevent path traversal.

    Accepts alphanumeric, underscores, hyphens, and dots (for Kilo ses_xxx format).
    Rejects path separators, parent refs (..), and overly long values.
    """
    import re

    return bool(re.match(r"^[a-zA-Z0-9_.\-]{1,128}$", session_id))


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


def get_validated_model(model: str) -> str:
    """Get validated model, checking for deprecation and ensuring reasoning capability."""
    # Refresh cache daily
    refresh_model_cache_if_needed()

    # Check for successor
    validated = check_model_deprecation(model)

    # Validate model has reasoning capability - auto-select if not
    if validated not in REASONING_MODELS:
        fallback = _DEFAULT_MODEL_FALLBACK
        print(
            f"[KILO] Model {validated} lacks reasoning capability. Auto-selecting {fallback}",
            file=sys.stderr,
        )
        return fallback

    return validated

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

    # Build candidate list starting with preferred
    candidates = [preferred] + [m for m in MODEL_FALLBACK_CHAIN if m != preferred]

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
# DATA CLASSES
# =============================================================================


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
    review_mode: str = "full"  # full, diff_only, staged

    # Iteration control
    max_iterations: int = 3
    min_severity: str = "MAJOR"  # BLOCKER, MAJOR, MINOR
    auto_fix: bool = True

    # Session management
    session_id: str | None = None
    persist_session: bool = True

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


@dataclass
class ReviewIssue:
    """A single issue found during review."""

    severity: str  # BLOCKER, MAJOR, MINOR
    category: str  # SPEC, SECURITY, CONFIG, EDGE, DOCS
    file: str
    lines: str  # "L42-L50" or "L42"
    snippet: str | None = None
    why: str = ""
    fix_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ReviewResult:
    """Result from a single review call."""

    verdict: str  # PASS, FAIL
    summary: str
    issues: list[ReviewIssue]
    notes: list[str]
    stats: dict[str, Any]
    session_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    raw_output: str = ""


@dataclass
class FixResult:
    """Result from a fix phase."""

    fixes_applied: list[dict[str, Any]]
    total_fixed: int = 0
    total_skipped: int = 0
    needs_manual: list[dict[str, Any]] = field(default_factory=list)
    session_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    diff: str = ""  # Git diff of changes made


@dataclass
class UsageStats:
    """Accumulated usage statistics with separate review/fix tracking."""

    # Total stats
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
    if session_id:
        if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", session_id):
            raise ValueError(f"Invalid session_id format: {session_id}")

    args = [kilo_path, "run", "--format", "json", "--auto"]
    args.extend(["--model", cli_model])

    if variant and variant in VALID_VARIANTS:
        args.extend(["--variant", variant])

    if agent and agent in VALID_AGENTS:
        args.extend(["--agent", agent])

    if session_id:
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
                        f"Too many parse errors ({parse_error_count}) - possible attack or corruption. First errors: {error_msg}"
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


async def run_kilo(
    prompt: str,
    config: KiloReviewConfig,
    agent: str,
    file_paths: list[Path] | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """
    Execute Kilo CLI and return parsed result.

    Args:
        prompt: The prompt to send to Kilo
        config: Review configuration
        agent: Kilo agent to use (ask, code, etc.)
        file_paths: Files to attach via --file
        timeout: Command timeout in seconds (default: KILO_REVIEW_TIMEOUT env var or 300)

    Returns:
        Parsed result dict with 'result', 'session_id', 'input_tokens', etc.
    """
    if timeout is None:
        try:
            timeout = int(os.getenv("KILO_REVIEW_TIMEOUT", "300"))
        except ValueError:
            print(
                f"Warning: Invalid KILO_REVIEW_TIMEOUT value '{os.getenv('KILO_REVIEW_TIMEOUT')}', using default 300s",
                file=sys.stderr,
            )
            timeout = 300
    # Validate prompt size to prevent memory exhaustion
    if not isinstance(prompt, str):
        raise ValueError(f"Prompt must be string, got {type(prompt).__name__}")
    if len(prompt) > MAX_PROMPT_SIZE:
        raise ValueError(f"Prompt too large: {len(prompt)} bytes (max {MAX_PROMPT_SIZE})")

    kilo_path = find_kilo_executable()
    if not kilo_path:
        raise RuntimeError("Kilo executable not found. Is it installed?")

    cmd = build_kilo_command(
        kilo_path=kilo_path,
        model=config.model,
        agent=agent,
        variant=config.variant,
        session_id=config.session_id,
        file_paths=file_paths,
    )

    if config.verbose:
        print(f"[KILO] Running: {' '.join(cmd)}", file=sys.stderr)

    # Retry loop with exponential backoff for transient failures
    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            # Use synchronous subprocess for reliability on Windows
            # Run in thread pool to keep async interface
            import concurrent.futures

            def run_subprocess():
                result = subprocess.run(
                    cmd,
                    input=prompt.encode("utf-8"),
                    capture_output=True,
                    timeout=timeout,
                    shell=False,  # Never use shell=True to prevent command injection
                )
                return result

            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = await asyncio.wait_for(
                    loop.run_in_executor(executor, run_subprocess),
                    timeout=timeout + 10,  # Extra buffer for executor overhead
                )

            stdout = result.stdout
            stderr = result.stderr

            # Check for retryable failures (timeout or service unavailable)
            if result.returncode in RETRYABLE_EXIT_CODES and attempt < MAX_RETRIES - 1:
                wait_time = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                error_msg = stderr.decode("utf-8", errors="replace")[:200]
                print(
                    f"⏳ Kilo transient failure (exit {result.returncode}). "
                    f"Retrying in {wait_time}s (attempt {attempt + 1}/{MAX_RETRIES})...",
                    file=sys.stderr,
                )
                if config.verbose:
                    print(f"[RETRY] Error: {error_msg}", file=sys.stderr)
                await asyncio.sleep(wait_time)
                continue

            if result.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")
                # Truncate and redact secrets to prevent leaking sensitive data in logs
                error_msg = error_msg[:200]
                error_msg = _redact_secrets(error_msg)
                raise RuntimeError(f"Kilo failed (exit {result.returncode}): {error_msg}")

            output = stdout.decode("utf-8", errors="replace")

            if config.verbose:
                print(f"[KILO] Output: {len(output)} chars", file=sys.stderr)
                if stderr:
                    stderr_text = stderr.decode("utf-8", errors="replace")
                    if stderr_text.strip() and "error" in stderr_text.lower():
                        print(f"[KILO] Stderr: {stderr_text[:300]}", file=sys.stderr)

            # Parse and return result
            return parse_kilo_jsonl(output)

        except subprocess.TimeoutExpired as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                wait_time = 2**attempt
                print(
                    f"⏳ Kilo timeout. Retrying in {wait_time}s (attempt {attempt + 1}/{MAX_RETRIES})...",
                    file=sys.stderr,
                )
                await asyncio.sleep(wait_time)
                continue
            raise RuntimeError(f"Kilo timed out after {timeout}s (tried {MAX_RETRIES} times)")
        except TimeoutError as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                wait_time = 2**attempt
                print(
                    f"⏳ Kilo async timeout. Retrying in {wait_time}s (attempt {attempt + 1}/{MAX_RETRIES})...",
                    file=sys.stderr,
                )
                await asyncio.sleep(wait_time)
                continue
            raise RuntimeError(
                f"Kilo async timeout after {timeout + 10}s (tried {MAX_RETRIES} times)"
            )

    # If we exhausted retries, raise the last exception
    if last_exception:
        raise last_exception
    raise RuntimeError("Kilo call failed after all retries")


# =============================================================================
# REVIEW PROMPT
# =============================================================================

REVIEW_PROMPT_TEMPLATE = """ROLE
You are Kilo Reviewer (Opus). You are the LAST gate before Traycer verification + commit.
Strict, fast, diff-scoped. No redesigns. No scope expansion.

ITERATION CONTEXT
- Review #: {iteration_number}
- Previous issues (if any): {previous_issues}
Re-review rule: verify previous BLOCKER/MAJOR issues are resolved. You may report newly discovered issues.

SCOPE (HARD)
- Review ONLY the uncommitted diff in this worktree (staged + unstaged if present), OR only the explicitly provided diff/files.
- Do NOT commit. Do NOT apply fixes unless explicitly instructed in a separate step.
- Do NOT propose redesigns/refactors. Do NOT expand scope beyond the diff unless necessary to demonstrate a real bug/security issue.

INPUTS (YOU MUST USE)
1) Traycer plan/spec for this task: {traycer_plan}
2) Repo conventions if present (AGENTS.md / existing patterns). If conflicts: report as SPEC/CONVENTION mismatch.
3) Diff/files: obtained from the workspace or attached via --file.

REVIEW CHECKS (IN THIS ORDER)
A) SPEC
   - Every behavior change maps to an explicit plan/spec requirement.
   - No missing plan steps; no extra features beyond plan.
B) SECURITY
   - Injection risks, auth/authz flaws, sensitive data exposure, unsafe deserialization, SSRF/path traversal, crypto misuse.
C) CONFIG & SECRETS HYGIENE
   - Env var misuse (wrong names, missing defaults, leaking secrets to logs, reading env at import-time if problematic).
   - Hardcoded values that should be config-driven (URLs/keys/ports/feature flags).
D) EDGE CASES & CORRECTNESS
   - Null/empty handling, error paths, retries/timeouts, idempotency, concurrency/race hazards (if relevant).
E) DOCS & DEV WORKFLOW
   - README/config/migration notes updated and accurate when behavior/config changes.

EVIDENCE RULE (HARD)
- Provide file + line references for every issue (line ranges preferred).
- Include minimal code snippets only when necessary.
- If you must reference surrounding code outside the diff, keep it minimal and explain why.

If you cannot access the diff/files or the plan/spec input is missing, return FAIL with a single SPEC issue explaining exactly what is missing.

OUTPUT FORMAT (JSON ONLY, EXACT SCHEMA)
Return ONLY valid JSON with this schema:

{{
  "verdict": "PASS" | "FAIL",
  "summary": "1-2 sentences",
  "issues": [
    {{
      "severity": "BLOCKER" | "MAJOR" | "MINOR",
      "category": "SPEC" | "SECURITY" | "CONFIG" | "EDGE" | "DOCS",
      "file": "path/to/file.ext",
      "lines": "Lx-Ly",
      "snippet": "optional short snippet",
      "why": "1-2 sentences on impact/risk",
      "fix_hint": "minimal change hint; no redesign"
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

OUTPUT FORMAT (JSON ONLY)
{{
  "verdict": "PASS" | "FAIL",
  "summary": "1-2 sentences",
  "issues": [
    {{
      "severity": "MAJOR" | "MINOR",
      "category": "SPEC" | "DOCS",
      "file": "path/to/file.md",
      "lines": "Lx-Ly",
      "snippet": "the incorrect text",
      "why": "what's wrong and what it should say",
      "fix_hint": "corrected text"
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

OUTPUT FORMAT (JSON ONLY)
{{
  "verdict": "PASS" | "FAIL",
  "summary": "1-2 sentences on verification result",
  "issues": [
    {{
      "severity": "BLOCKER" | "MAJOR" | "MINOR",
      "category": "FIX_INCOMPLETE" | "FIX_INCORRECT" | "NEW_ISSUE",
      "file": "path/to/file.ext",
      "lines": "Lx-Ly",
      "why": "what's wrong with the fix or what new issue was introduced",
      "fix_hint": "minimal correction"
    }}
  ],
  "verified_fixes": ["list of fixes that were correctly verified"],
  "notes": ["optional observations"]
}}

VERDICT RULES
- PASS: All described fixes are correctly implemented, no new issues
- FAIL: Any fix is incomplete, incorrect, or introduces new problems

FILES TO VERIFY:
{files_list}

{diff_content}
"""


FIX_PROMPT_TEMPLATE = """You are a code fixer. Fix the following issues found in the previous code review.

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
    """Parse review JSON output from Kilo."""
    # Use robust JSON extraction
    data = _extract_json_object(raw_output)

    if data is None:
        # No valid JSON found - treat as error
        return ReviewResult(
            verdict="FAIL",
            summary="Failed to parse review output - no valid JSON found",
            issues=[
                ReviewIssue(
                    severity="BLOCKER",
                    category="SPEC",
                    file="N/A",
                    lines="N/A",
                    why="Review output did not contain valid JSON",
                    fix_hint="Check Kilo CLI output",
                )
            ],
            notes=[],
            stats={"error": "parse_failed"},
            raw_output=raw_output,
        )

    # Validate expected structure
    if "verdict" not in data:
        data["verdict"] = "FAIL"
    if "summary" not in data:
        data["summary"] = "No summary provided"
    if "issues" not in data:
        data["issues"] = []

    # data is already validated by _extract_json_object

    # Parse issues
    issues = []
    for issue_data in data.get("issues", []):
        issues.append(
            ReviewIssue(
                severity=issue_data.get("severity", "MAJOR"),
                category=issue_data.get("category", "SPEC"),
                file=issue_data.get("file", "unknown"),
                lines=issue_data.get("lines", "?"),
                snippet=issue_data.get("snippet"),
                why=issue_data.get("why", ""),
                fix_hint=issue_data.get("fix_hint", ""),
            )
        )

    return ReviewResult(
        verdict=data.get("verdict", "FAIL"),
        summary=data.get("summary", ""),
        issues=issues,
        notes=data.get("notes", []),
        stats=data.get("stats", {}),
        raw_output=raw_output,
    )


def parse_fix_output(raw_output: str) -> FixResult:
    """Parse fix JSON output from Kilo."""
    data = _extract_json_object(raw_output)

    if data is None:
        return FixResult(
            fixes_applied=[],
            total_fixed=0,
            total_skipped=0,
            needs_manual=[{"error": "No JSON in output"}],
        )

    summary = data.get("summary", {})
    return FixResult(
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
    """Run review on a single batch of files (internal helper)."""
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

    # Select prompt template based on mode
    if config.verify_mode and config.fixes_description:
        # Verify mode: use lighter verification prompt
        prompt = VERIFY_PROMPT_TEMPLATE.format(
            fixes_description=config.fixes_description,
            files_list=files_list,
            diff_content=diff_section,
        )
    elif config.doc_mode or is_doc_only_review(files):
        # Doc-only mode: use lighter doc-specific prompt
        skip_cats_str = ", ".join(config.skip_categories) if config.skip_categories else "None"
        prompt = DOC_REVIEW_PROMPT_TEMPLATE.format(
            iteration_number=iteration,
            previous_issues=prev_issues_str,
            skip_categories=skip_cats_str,
            files_list=files_list,
            diff_content=diff_section,
        )
    else:
        # Standard review mode
        prompt = REVIEW_PROMPT_TEMPLATE.format(
            iteration_number=iteration,
            previous_issues=prev_issues_str,
            traycer_plan=plan_str,
            files_list=files_list,
            diff_content=diff_section,
        )

    # Run Kilo
    result = await run_kilo(
        prompt=prompt,
        config=config,
        agent=config.review_agent,
        file_paths=files_to_review,
    )

    # Update session ID from Kilo response
    if result.get("session_id") and not config.session_id:
        config.session_id = result["session_id"]

    # Parse result
    review_result = parse_review_output(result["result"])
    review_result.session_id = result.get("session_id")
    review_result.input_tokens = result.get("input_tokens", 0)
    review_result.output_tokens = result.get("output_tokens", 0)
    review_result.cost = result.get("cost", 0.0)

    return review_result


async def run_review(
    files: list[Path],
    config: KiloReviewConfig,
    iteration: int,
    previous_issues: list[dict[str, Any]] | None = None,
) -> ReviewResult:
    """Run a single review iteration, processing ALL files in batches."""
    # Process files in batches if more than max_files_per_batch
    if len(files) > config.max_files_per_batch:
        return await _run_review_batched(files, config, iteration, previous_issues)

    # Single batch - use the helper directly
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
    # Initialize session
    # Note: Don't pre-generate session IDs - let Kilo create them
    # We'll capture the session ID from Kilo's response and use it for subsequent calls
    if config.session_id == "continue":
        existing = get_latest_session()
        if existing and existing.status == "in_progress":
            config.session_id = existing.session_id
            print(f"Continuing session: {config.session_id}", file=sys.stderr)
        else:
            config.session_id = None  # Let Kilo create new session
    elif not config.session_id:
        config.session_id = None  # Let Kilo create new session

    # Track the session ID we'll use for persistence (will be set after first Kilo call)
    local_session_id = config.session_id or f"local_{uuid.uuid4().hex[:16]}"

    # ==========================================================================
    # DIFF-SCOPED MODEL ROUTING (Cost-Aware)
    # ==========================================================================
    # Select model based on diff file paths BEFORE review starts.
    # User --model override takes precedence; otherwise escalate to Opus only
    # for high-risk paths (backend, auth, docker, etc.)
    # Note: config.model is None if user didn't specify --model
    selected_model, escalated, routing_reason = select_model_for_diff(
        diff_files=files,
        user_model=config.model,  # None if not specified by user
    )
    config.model = selected_model
    log_routing_decision(files, selected_model, escalated, routing_reason)

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
        )
    previous_issues: list[dict[str, Any]] | None = None
    previous_verdict: str | None = None  # Track last review verdict for max variant decision
    iteration = 0
    issue_history: dict[str, int] = {}  # Track repeated issues for false positive detection
    false_positives_total: list[dict[str, Any]] = []  # Accumulated false positives

    # Auto-detect doc mode and adjust max iterations
    is_doc_review = config.doc_mode or is_doc_only_review(files)
    if is_doc_review and config.max_iterations > MAX_ITERATIONS_DOCS:
        print(
            f"[DOC MODE] Auto-reducing max iterations: {config.max_iterations} → {MAX_ITERATIONS_DOCS}",
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
                    f"\n=== Review Iteration {iteration}/{effective_max} (variant=max, reason={max_reason}) ===",
                    file=sys.stderr,
                )
            else:
                print(
                    f"\n=== Review Iteration {iteration}/{effective_max} ===",
                    file=sys.stderr,
                )

            # PHASE 1: Review (with adaptive variant)
            # Temporarily override variant for this iteration
            original_variant = config.variant
            config.variant = current_variant
            review_result = await run_review(
                files=files,
                config=config,
                iteration=iteration,
                previous_issues=previous_issues,
            )
            config.variant = original_variant  # Restore
            usage.add_review(review_result)

            # Capture session ID from Kilo response for subsequent calls
            # Validate to prevent path traversal via malicious/corrupted response
            if review_result.session_id and not config.session_id:
                if _is_valid_session_id(review_result.session_id):
                    config.session_id = review_result.session_id
                    local_session_id = review_result.session_id
                    session_state.session_id = review_result.session_id
                else:
                    print(
                        f"Warning: Invalid session_id from Kilo response: "
                        f"{review_result.session_id!r}, ignoring",
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
                if current_variant != "max" and iteration < effective_max and config.auto_fix:
                    # Record PASS so next iteration triggers final_gate max verification
                    previous_verdict = review_result.verdict
                    print(
                        "  PASS at variant=high — scheduling final max-variant verification...",
                        file=sys.stderr,
                    )
                    continue

                # Definitive PASS (either max-variant verification or at iteration limit)
                session_state.status = "completed"
                session_state.usage = asdict(usage)
                if config.persist_session:
                    save_session(session_state)

                return FinalReport(
                    status="CLEAN",
                    verdict="PASS",
                    iterations=iteration,
                    files_reviewed=files_reviewed,
                    all_issues=all_issues,
                    all_fixes=all_fixes,
                    remaining_issues=[],
                    usage=asdict(usage),
                    session_id=config.session_id,
                    summary=f"Review passed after {iteration} iteration(s). {review_result.summary}",
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

                    return FinalReport(
                        status="ERROR",
                        verdict="FAIL",
                        iterations=iteration,
                        files_reviewed=files_reviewed,
                        all_issues=all_issues,
                        all_fixes=all_fixes,
                        remaining_issues=[],
                        usage=asdict(usage),
                        session_id=config.session_id,
                        summary=f"Review failed but returned no issues (possible parse error). {review_result.summary}",
                    )

                # Only MINOR issues remain - this is a pass
                session_state.status = "completed"
                session_state.usage = asdict(usage)
                if config.persist_session:
                    save_session(session_state)

                return FinalReport(
                    status="CLEAN",
                    verdict="PASS",
                    iterations=iteration,
                    files_reviewed=files_reviewed,
                    all_issues=all_issues,
                    all_fixes=all_fixes,
                    remaining_issues=[i.to_dict() for i in review_result.issues],
                    usage=asdict(usage),
                    session_id=config.session_id,
                    summary=f"Review passed (only MINOR issues). {review_result.summary}",
                )

            # Skip fix phase if disabled
            if not config.auto_fix:
                session_state.status = "completed"
                session_state.usage = asdict(usage)
                if config.persist_session:
                    save_session(session_state)

                return FinalReport(
                    status="NEEDS_FIX",
                    verdict="FAIL",
                    iterations=iteration,
                    files_reviewed=files_reviewed,
                    all_issues=all_issues,
                    all_fixes=all_fixes,
                    remaining_issues=[i.to_dict() for i in review_result.issues],
                    usage=asdict(usage),
                    session_id=config.session_id,
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
                    session_id=config.session_id,
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
            session_id=config.session_id,
            summary=f"Max iterations ({config.max_iterations}) reached with issues remaining.",
        )

    except Exception:
        session_state.status = "failed"
        session_state.usage = asdict(usage)
        if config.persist_session:
            save_session(session_state)
        raise


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


def pre_review_checks(files: list[Path]) -> list[str]:
    """Run fast validation before Kilo review to fail fast.

    Returns list of blocking issues that should prevent review.
    """
    issues = []
    MAX_FILE_SIZE = 500 * 1024

    for f in files:
        if not f.exists():
            issues.append(f"File does not exist: {f}")
            continue
        size = f.stat().st_size
        if size > MAX_FILE_SIZE:
            issues.append(f"File too large: {f} ({size:,} bytes, max {MAX_FILE_SIZE:,})")

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
        f"   Review: {review_tokens:,} tokens, ${review_cost:.4f} ({usage.get('review_calls', 0)} calls)"
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
        "staged", parents=[common], help="Review git staged files"
    )
    staged_parser.add_argument(
        "--max-iterations", type=int, default=3, help="Max review-fix cycles"
    )
    staged_parser.add_argument("--no-fix", action="store_true", help="Don't auto-fix, just report")

    # changed command
    changed_parser = subparsers.add_parser(
        "changed", parents=[common], help="Review git changed files"
    )
    changed_parser.add_argument(
        "--max-iterations", type=int, default=3, help="Max review-fix cycles"
    )
    changed_parser.add_argument("--no-fix", action="store_true", help="Don't auto-fix, just report")

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
    args = parse_args()

    # Validate model if user specified one (check deprecation, refresh cache daily)
    # If None, model will be auto-selected by diff-scoped routing in review_loop
    validated_model = get_validated_model(args.model) if args.model else None

    # Build config
    config = KiloReviewConfig(
        model=validated_model,
        variant=args.variant,
        review_agent=args.review_agent,
        fix_agent=args.fix_agent,
        session_id=args.session,
        output_format=args.output,
        verbose=args.verbose,
        traycer_plan=load_plan(getattr(args, "plan", None)),
        skip_categories=parse_skip_categories(getattr(args, "skip_categories", None)),
        doc_mode=getattr(args, "doc_mode", False),
    )

    # Get files based on command
    if args.command in ("review", "auto-fix"):
        files = collect_files(args.files)
        config.review_mode = getattr(args, "mode", "full")
    elif args.command == "staged":
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
        config.auto_fix = not getattr(args, "no_fix", False)
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
                f"   Review: {cumulative['review_tokens']:,} tokens, ${cumulative['review_cost_usd']:.4f}",
                file=sys.stderr,
            )
            print(
                f"   Fix:    {cumulative['fix_tokens']:,} tokens, ${cumulative['fix_cost_usd']:.4f}",
                file=sys.stderr,
            )
            print(
                f"   Total:  {cumulative['total_tokens']:,} tokens, ${cumulative['total_cost_usd']:.4f}",
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
