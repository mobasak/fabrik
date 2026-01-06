#!/usr/bin/env python3
"""
Droid Model Registry

Manages model selection for droid exec based on task type.
Model info sourced from:
  - https://docs.factory.ai/pricing
  - https://docs.factory.ai/cli/user-guides/choosing-your-model
  - config/models.yaml (local overrides and stack rankings)

WARNING: Changing models mid-session loses context (new session starts).

CLI Commands:
  python droid_models.py                # Show droid models
  python droid_models.py stack-rank     # Show current stack rankings
  python droid_models.py recommend <scenario>  # Get model for scenario
  python droid_models.py check-updates  # Check Factory docs for updates
  python droid_models.py sync           # Sync model names across files
"""

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


# Cache file for model registry
CACHE_FILE = Path(__file__).parent / ".droid_models_cache.json"
CACHE_TTL_HOURS = 24  # Refresh cache daily

# Config file for model rankings and scenarios
CONFIG_FILE = Path(__file__).parent.parent / "config" / "models.yaml"

# Windsurf models source of truth
WINDSURF_MODELS_MD = (
    Path(__file__).parent.parent / "docs" / "reference" / "windsurf" / "cascade-models.md"
)


@dataclass
class ModelInfo:
    """Information about a droid model."""

    name: str
    provider: str
    reasoning_levels: list[str]
    default_reasoning: str
    best_for: list[str]
    cost_tier: str  # "low", "medium", "high", "premium"
    cost_multiplier: float  # Cost multiplier relative to standard tokens
    notes: str = ""


# =============================================================================
# YAML CONFIG LOADING
# =============================================================================


def load_models_config() -> dict:
    """
    Load model configuration from config/models.yaml.

    Returns default config if file doesn't exist or YAML not available.
    """
    if not YAML_AVAILABLE:
        return {"version": "builtin", "error": "PyYAML not installed"}

    if not CONFIG_FILE.exists():
        return {"version": "builtin", "error": f"Config not found: {CONFIG_FILE}"}

    try:
        with open(CONFIG_FILE) as f:
            config = yaml.safe_load(f)

        # Basic schema validation
        if not isinstance(config, dict):
            raise ValueError("Config must be a dictionary")
        if "models" not in config:
            raise ValueError("Config missing 'models' section")

        return config
    except Exception as e:
        # Log error to stderr but don't crash
        import sys

        print(f"Error loading models.yaml: {e}", file=sys.stderr)
        return {"version": "builtin", "error": str(e), "models": {}}


def get_models_from_yaml() -> dict[str, ModelInfo]:
    """Load models from YAML config."""
    config = load_models_config()
    models_data = config.get("models", {})

    loaded_models = {}
    for name, info in models_data.items():
        try:
            loaded_models[name] = ModelInfo(
                name=name,
                provider=info.get("provider", "unknown"),
                reasoning_levels=info.get("reasoning_levels", ["off"]),
                default_reasoning=info.get("default_reasoning", "off"),
                best_for=info.get(
                    "best_for", []
                ),  # Not strictly in YAML schema but useful if added
                cost_tier=info.get("cost_tier", "medium"),
                cost_multiplier=float(info.get("cost_multiplier", 1.0)),
                notes=info.get("notes", ""),
            )
        except Exception:
            continue

    return loaded_models


def get_default_model() -> str:
    """Get default model from config."""
    config = load_models_config()
    return config.get("default_model", "claude-sonnet-4-5-20250929")


def get_stack_rankings() -> list[dict]:
    """
    Get current model stack rankings from config.

    Returns list of dicts with rank, model, and why.
    """
    config = load_models_config()
    stack_rank = config.get("stack_rank", {})

    rankings = []
    for rank in sorted(stack_rank.keys()):
        info = stack_rank[rank]
        rankings.append(
            {
                "rank": rank,
                "model": info.get("model", "unknown"),
                "why": info.get("why", ""),
            }
        )

    return rankings


def get_scenario_recommendation(scenario: str) -> dict:
    """
    Get model recommendation for a specific scenario.

    Args:
        scenario: One of: deep_planning, full_feature_dev, repeatable_edits,
                  ci_cd, high_volume, explore, design, verify, ship

    Returns dict with primary model, alternatives, and notes.
    """
    config = load_models_config()
    scenarios = config.get("scenarios", {})

    if scenario not in scenarios:
        return {
            "error": f"Unknown scenario: {scenario}",
            "available": list(scenarios.keys()),
        }

    return scenarios[scenario]


def get_config_version() -> str:
    """Get the version/date of the current config."""
    config = load_models_config()
    return config.get("version", "unknown")


def print_stack_rankings():
    """Print current model stack rankings."""
    rankings = get_stack_rankings()
    config = load_models_config()
    version = config.get("version", "unknown")

    print(f"Model Stack Rankings (as of {version})")
    print("Source: config/models.yaml")
    print("=" * 80)
    print()
    print(f"{'Rank':<6} {'Model':<30} {'Why'}")
    print("-" * 80)

    for r in rankings:
        print(
            f"{r['rank']:<6} {r['model']:<30} {r['why'][:45]}..."
            if len(r["why"]) > 45
            else f"{r['rank']:<6} {r['model']:<30} {r['why']}"
        )

    print()
    print("To update rankings, edit: config/models.yaml")


def print_scenario_recommendation(scenario: str):
    """Print model recommendation for a scenario."""
    rec = get_scenario_recommendation(scenario)

    if "error" in rec:
        print(f"Error: {rec['error']}")
        print(f"Available scenarios: {', '.join(rec.get('available', []))}")
        return

    print(f"Scenario: {rec.get('description', scenario)}")
    print("=" * 60)

    # Handle dual-model scenarios (e.g., code_review uses 'models' list)
    if "models" in rec:
        print(f"Models (use ALL): {', '.join(rec.get('models', []))}")
        print(f"Notes:            {rec.get('notes', '')}")
        print()
        print("Commands to run:")
        for model in rec.get("models", []):
            print(f'  droid exec -m {model} "Review..."')
    else:
        # Standard primary/alternatives format
        print(f"Primary model: {rec.get('primary', 'unknown')}")
        print(f"Alternatives:  {', '.join(rec.get('alternatives', []))}")
        print(f"Notes:         {rec.get('notes', '')}")


def list_scenarios():
    """List all available scenarios."""
    config = load_models_config()
    scenarios = config.get("scenarios", {})

    print("Available Scenarios")
    print("=" * 60)
    for name, info in scenarios.items():
        print(f"  {name:<20} {info.get('description', '')[:40]}")
    print()
    print("Usage: python droid_models.py recommend <scenario>")


class TaskCategory(str, Enum):
    """Task categories for model selection."""

    FAST_SIMPLE = "fast_simple"  # Quick edits, simple questions
    STANDARD = "standard"  # Normal coding tasks
    COMPLEX = "complex"  # Large refactors, architecture
    REASONING = "reasoning"  # Problems requiring deep thinking
    BUDGET = "budget"  # Cost-sensitive tasks


@dataclass
class ModelInfo:
    """Information about a droid model."""

    name: str
    provider: str
    reasoning_levels: list[str]
    default_reasoning: str
    best_for: list[str]
    cost_tier: str  # "low", "medium", "high", "premium"
    cost_multiplier: float  # Cost multiplier relative to standard tokens
    notes: str = ""


# Session switching rules (from Factory docs)
SESSION_SWITCHING_RULES = """
Switching models mid-session:
- Use /model to swap without losing chat history
- Provider change (e.g., Anthropic→OpenAI): CLI converts session transcript
  - Translation is lossy (provider-specific metadata dropped)
  - No accuracy regressions observed in practice
- Best practice: Switch at natural milestones (after commit, PR lands, plan reset)
- Rapid switching: Expect assistant to re-ground itself; summarize recent progress
"""


# =============================================================================
# EXECUTION MODES - Task-based model selection strategy
# =============================================================================
# Who Decides: "You" = human approval required, "Droid" = autonomous execution


class ExecutionMode(str, Enum):
    """Execution modes for different workflow phases."""

    EXPLORE = "explore"  # Research, discovery, understanding
    DESIGN = "design"  # Architecture, planning, decisions
    BUILD = "build"  # Implementation, coding
    VERIFY = "verify"  # Testing, validation, debugging
    SHIP = "ship"  # Deployment, release, cleanup


@dataclass
class ModeConfig:
    """Configuration for an execution mode."""

    name: str
    executor: str  # Primary model for execution
    executor_source: str  # "droid" or "windsurf"
    decider: str  # "you" (human) or "droid" (autonomous)
    escalation: str  # Model to escalate to when needed
    escalation_source: str  # "droid" or "windsurf"
    description: str = ""


EXECUTION_MODES: dict[ExecutionMode, ModeConfig] = {
    ExecutionMode.EXPLORE: ModeConfig(
        name="Explore",
        executor="gemini-3-flash-preview",
        executor_source="droid",
        decider="you",
        escalation="claude-sonnet-4-5-20250929",
        escalation_source="droid",
        description="Research and discovery - cheap exploration, escalate for depth",
    ),
    ExecutionMode.DESIGN: ModeConfig(
        name="Design",
        executor="claude-sonnet-4-5-20250929",
        executor_source="droid",
        decider="you",
        escalation="claude-opus-4-5-20251101",
        escalation_source="droid",
        description="Architecture and planning - balanced model, escalate for complexity",
    ),
    ExecutionMode.BUILD: ModeConfig(
        name="Build",
        executor="SWE-1.5",
        executor_source="windsurf",
        decider="you",
        escalation="gpt-5.1-codex-max",
        escalation_source="droid",
        description="Implementation - Windsurf Cascade for coding, escalate to Codex-Max",
    ),
    ExecutionMode.VERIFY: ModeConfig(
        name="Verify",
        executor="gpt-5.1-codex-max",
        executor_source="droid",
        decider="droid",
        escalation="claude-opus-4-5-20251101",
        escalation_source="droid",
        description="Testing and validation - autonomous verification, escalate for tricky bugs",
    ),
    ExecutionMode.SHIP: ModeConfig(
        name="Ship",
        executor="gemini-3-flash-preview",
        executor_source="droid",
        decider="you",
        escalation="claude-haiku-4-5-20251001",
        escalation_source="droid",
        description="Deployment and cleanup - cheap routine tasks, escalate if issues",
    ),
}


# =============================================================================
# WINDSURF MODELS - IDE models (non-BYOK)
# =============================================================================


@dataclass
class WindsurfModel:
    """Windsurf IDE model information."""

    name: str
    credits: str  # "Free", "0.25x", "1x", etc.
    category: str  # "free", "budget", "standard", "premium", "ultra"


# Cache for loaded models
_windsurf_models_cache: list[WindsurfModel] | None = None


def _parse_windsurf_models_from_md() -> list[WindsurfModel]:
    """
    Parse Windsurf models from cascade-models.md.
    Source of truth: docs/reference/windsurf/cascade-models.md
    """
    models = []

    if not WINDSURF_MODELS_MD.exists():
        print(
            f"Warning: {WINDSURF_MODELS_MD} not found, using empty list",
            file=__import__("sys").stderr,
        )
        return models

    content = WINDSURF_MODELS_MD.read_text()

    # Map section headers to categories
    category_map = {
        "Free Tier": "free",
        "Budget Tier": "budget",
        "Standard Tier": "standard",
        "Premium Tier": "premium",
        "Ultra Tier": "ultra",
    }

    current_category = None
    in_table = False

    for line in content.split("\n"):
        line = line.strip()

        # Check for tier headers
        for header, cat in category_map.items():
            if header in line and line.startswith("##"):
                current_category = cat
                in_table = False
                break

        # Skip non-table lines
        if not line.startswith("|") or current_category is None:
            continue

        # Skip table headers and separators
        if "Model" in line and "Credits" in line:
            in_table = True
            continue
        if line.startswith("|---") or line.startswith("| ---"):
            continue

        if not in_table:
            continue

        # Parse table row: | Model | Credits |
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3:
            model_name = parts[1].strip().replace("**", "")  # Remove bold markers
            credits = parts[2].strip()
            if model_name and credits and model_name != "Model":
                models.append(WindsurfModel(model_name, credits, current_category))

    return models


def get_windsurf_models() -> list[WindsurfModel]:
    """
    Get Windsurf models, loading from markdown file.
    Caches result for performance.
    """
    global _windsurf_models_cache
    if _windsurf_models_cache is None:
        _windsurf_models_cache = _parse_windsurf_models_from_md()
    return _windsurf_models_cache


def reload_windsurf_models() -> list[WindsurfModel]:
    """Force reload of Windsurf models from markdown file."""
    global _windsurf_models_cache
    _windsurf_models_cache = None
    return get_windsurf_models()


# For backward compatibility - lazy property that loads on first access
class _WindsurfModelsProxy:
    """Proxy to lazy-load WINDSURF_MODELS from markdown file."""

    def __iter__(self):
        return iter(get_windsurf_models())

    def __len__(self):
        return len(get_windsurf_models())

    def __getitem__(self, key):
        return get_windsurf_models()[key]


WINDSURF_MODELS = _WindsurfModelsProxy()


def get_mode_config(mode: ExecutionMode) -> ModeConfig:
    """Get configuration for an execution mode."""
    return EXECUTION_MODES[mode]


def print_execution_modes():
    """Print execution modes table."""
    print("Execution Modes:")
    print(f"{'Mode':<8} {'Name':<10} {'Executor':<25} {'Decider':<8} {'Escalation':<25}")
    print("-" * 85)
    for i, (_mode, cfg) in enumerate(EXECUTION_MODES.items(), 1):
        print(f"{i:<8} {cfg.name:<10} {cfg.executor:<25} {cfg.decider:<8} {cfg.escalation:<25}")


def print_windsurf_models(category: str = None):
    """Print Windsurf models, optionally filtered by category."""
    models = (
        WINDSURF_MODELS if not category else [m for m in WINDSURF_MODELS if m.category == category]
    )
    print(f"Windsurf Models ({len(models)}):")
    print(f"{'Model':<35} {'Credits':<10} {'Category'}")
    print("-" * 60)
    for m in models:
        print(f"{m.name:<35} {m.credits:<10} {m.category}")


# Current models from Factory docs (December 2025)
# Source: https://docs.factory.ai/pricing
MODELS = get_models_from_yaml()

if not MODELS:
    # Fallback if config fails
    MODELS = {
        "gpt-5.1-codex-max": ModelInfo(
            name="gpt-5.1-codex-max",
            provider="openai",
            reasoning_levels=["low", "medium", "high", "extra_high"],
            default_reasoning="medium",
            best_for=["complex_coding"],
            cost_tier="high",
            cost_multiplier=0.5,
            notes="Fallback model",
        )
    }

# Task type to model recommendations
TASK_MODEL_MAP: dict[TaskCategory, list[str]] = {
    TaskCategory.FAST_SIMPLE: [
        "claude-haiku-4-5-20251001",
        "gemini-3-flash-preview",
        "glm-4.6",
    ],
    TaskCategory.STANDARD: [
        "claude-sonnet-4-5-20250929",
        "gpt-5.1-codex",
        "gemini-3-pro-preview",
    ],
    TaskCategory.COMPLEX: [
        "gpt-5.1-codex-max",
        "claude-opus-4-5-20251101",
        "gpt-5.2",
    ],
    TaskCategory.REASONING: [
        "claude-opus-4-5-20251101",
        "gpt-5.2",
        "gpt-5.1-codex-max",
    ],
    TaskCategory.BUDGET: [
        "glm-4.6",
        "claude-haiku-4-5-20251001",
        "gemini-3-flash-preview",
    ],
}

# Default model for general use
DEFAULT_MODEL = get_default_model()


def get_model_info(model_name: str) -> ModelInfo | None:
    """Get info for a specific model."""
    return MODELS.get(model_name)


def get_available_models() -> list[str]:
    """Get list of all available model names."""
    return list(MODELS.keys())


def recommend_model(
    task_category: TaskCategory = TaskCategory.STANDARD,
    prefer_provider: str | None = None,
) -> str:
    """
    Recommend a model based on task category.

    Args:
        task_category: Type of task (fast_simple, standard, complex, etc.)
        prefer_provider: Optional provider preference (anthropic, openai, google)

    Returns:
        Recommended model name
    """
    candidates = TASK_MODEL_MAP.get(task_category, [DEFAULT_MODEL])

    if prefer_provider:
        for model_name in candidates:
            model = MODELS.get(model_name)
            if model and model.provider == prefer_provider:
                return model_name

    return candidates[0] if candidates else DEFAULT_MODEL


def check_model_change_warning(current_model: str, new_model: str) -> str | None:
    """
    Check if changing models would cause session loss.

    Returns warning message if session would be lost, None otherwise.
    """
    if current_model == new_model:
        return None

    current = MODELS.get(current_model)
    new = MODELS.get(new_model)

    if not current or not new:
        return f"WARNING: Changing model from {current_model} to {new_model} will start a new session (context lost)"

    # Provider change is more significant
    if current.provider != new.provider:
        return (
            f"WARNING: Changing provider from {current.provider} to {new.provider} "
            f"({current_model} → {new_model}) will start a new session. "
            "Context is converted but some metadata may be lost."
        )

    return (
        f"NOTE: Changing model from {current_model} to {new_model} "
        "will start a new session (same provider, context mostly preserved)"
    )


def refresh_models_from_docs() -> dict[str, any]:
    """
    Refresh model list from Factory docs.

    Fetches from:
      - https://docs.factory.ai/pricing (model names)
      - https://docs.factory.ai/cli/user-guides/choosing-your-model (use cases)

    Returns dict with status, models found, and any new models not in registry.
    """
    result = {
        "status": "ok",
        "models_found": [],
        "new_models": [],  # Models in docs but not in our registry
        "errors": [],
        "timestamp": datetime.now().isoformat(),
    }

    # Model name patterns - matches gpt-*, claude-*, gemini-*, glm-*
    model_patterns = [
        r"gpt-[0-9\.]+(?:-codex(?:-max)?)?",
        r"claude-(?:sonnet|opus|haiku)-[0-9\-]+",
        r"gemini-[0-9]+-(?:pro|flash)-preview",
        r"glm-[0-9\.]+",
    ]
    combined_pattern = "(" + "|".join(model_patterns) + ")"

    urls = [
        "https://docs.factory.ai/pricing",
        "https://docs.factory.ai/cli/user-guides/choosing-your-model",
    ]

    all_models = set()

    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Fabrik/1.0 (model refresh)"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8")

            # Extract model names using pattern
            found = re.findall(combined_pattern, html, re.IGNORECASE)

            # Clean up matches (remove trailing backslashes from JSON escaping)
            for m in found:
                clean = m.rstrip("\\").strip()
                if clean:
                    all_models.add(clean)

        except Exception as e:
            result["errors"].append(f"Failed to fetch {url}: {str(e)}")

    # Normalize to lowercase and deduplicate
    normalized_models = sorted({m.lower() for m in all_models})
    result["models_found"] = normalized_models

    # Check for new models not in our registry (case-insensitive)
    registry_lower = {k.lower() for k in MODELS}
    for model in normalized_models:
        if model.lower() not in registry_lower:
            result["new_models"].append(model)

    if result["new_models"]:
        result["status"] = "new_models_available"

    # Cache the result
    try:
        CACHE_FILE.write_text(json.dumps(result, indent=2))
    except Exception as e:
        result["errors"].append(f"Failed to cache: {str(e)}")

    return result


def get_cached_models() -> dict | None:
    """Get cached model info if still valid."""
    if not CACHE_FILE.exists():
        return None

    try:
        data = json.loads(CACHE_FILE.read_text())
        cached_time = datetime.fromisoformat(data.get("timestamp", ""))
        if datetime.now() - cached_time < timedelta(hours=CACHE_TTL_HOURS):
            return data
    except Exception:
        pass

    return None


def print_model_table():
    """Print a table of available models."""
    print(f"{'Model':<35} {'Provider':<10} {'Multi':<6} {'Reasoning':<25} {'Best For'}")
    print("-" * 100)
    for name, info in MODELS.items():
        best_for = ", ".join(info.best_for[:2])
        reasoning = f"{info.reasoning_levels} (def:{info.default_reasoning})"
        print(
            f"{name:<35} {info.provider:<10} {info.cost_multiplier:<6.2f} {reasoning:<25} {best_for}"
        )


# =============================================================================
# MODEL SYNC - Update model names in droid_tasks.py and AGENTS.md
# =============================================================================


def get_fabrik_task_models() -> dict[str, str]:
    """
    Get task models from config/models.yaml (single source of truth).
    Falls back to hardcoded defaults if config is missing.
    """
    config = load_models_config()
    scenarios = config.get("scenarios", {})

    # Map scenarios to task types
    # Default fallback mapping
    mapping = {
        "ANALYZE": scenarios.get("explore", {}).get("primary", "gemini-3-flash-preview"),
        "CODE": scenarios.get("full_feature_dev", {}).get("alternatives", ["gpt-5.1-codex-max"])[0],
        "REFACTOR": scenarios.get("full_feature_dev", {}).get(
            "alternatives", ["gpt-5.1-codex-max"]
        )[0],
        "TEST": scenarios.get("verify", {}).get("primary", "gpt-5.1-codex-max"),
        "REVIEW": scenarios.get("code_review", {}).get("models", ["claude-haiku-4-5-20251001"])[
            0
        ],  # review uses list
        "SPEC": scenarios.get("design", {}).get("primary", "claude-sonnet-4-5-20250929"),
        "SCAFFOLD": scenarios.get("full_feature_dev", {}).get(
            "alternatives", ["gpt-5.1-codex-max"]
        )[0],
        "DEPLOY": scenarios.get("ship", {}).get("primary", "gemini-3-flash-preview"),
        "MIGRATE": scenarios.get("full_feature_dev", {}).get("alternatives", ["gpt-5.1-codex-max"])[
            0
        ],
        "HEALTH": scenarios.get("verify", {}).get(
            "primary", "gemini-3-flash-preview"
        ),  # verify primary is codex-max but health is usually cheaper
        "PREFLIGHT": scenarios.get("ship", {}).get("primary", "gemini-3-flash-preview"),
    }

    # Override with specific lookups where logic is more complex
    # Health/Preflight/Deploy -> Ship scenario
    ship_model = scenarios.get("ship", {}).get("primary", "gemini-3-flash-preview")
    mapping["HEALTH"] = ship_model
    mapping["PREFLIGHT"] = ship_model
    mapping["DEPLOY"] = ship_model

    return mapping


# Canonical model assignments for Fabrik task types
# This is the SINGLE SOURCE OF TRUTH - sync command updates other files from here
FABRIK_TASK_MODELS = get_fabrik_task_models()

# Execution modes for AGENTS.md
FABRIK_EXECUTION_MODES = {
    "Explore": {
        "task": "analyze",
        "model": "gemini-3-flash-preview",
        "reasoning": "off",
        "autonomy": "low",
    },
    "Design": {
        "task": "spec",
        "model": "claude-sonnet-4-5-20250929",
        "reasoning": "**high**",
        "autonomy": "low",
    },
    "Build": {
        "task": "code, scaffold",
        "model": "gpt-5.1-codex-max",
        "reasoning": "medium",
        "autonomy": "**high**",
    },
    "Verify": {
        "task": "test, health",
        "model": "gpt-5.1-codex-max / gemini-3-flash-preview",
        "reasoning": "low/off",
        "autonomy": "**high**",
    },
    "Ship": {
        "task": "deploy",
        "model": "gemini-3-flash-preview",
        "reasoning": "off",
        "autonomy": "**high**",
    },
}


def sync_droid_tasks() -> dict:
    """
    Update model names in droid_tasks.py TOOL_CONFIGS from FABRIK_TASK_MODELS.

    Returns dict with status and changes made.
    """
    import re

    tasks_file = Path(__file__).parent / "droid_tasks.py"
    result = {"status": "ok", "changes": [], "errors": []}

    if not tasks_file.exists():
        result["status"] = "error"
        result["errors"].append(f"File not found: {tasks_file}")
        return result

    content = tasks_file.read_text()
    original = content

    # Pattern to match TaskType.XXX model assignments
    # Matches: TaskType.ANALYZE: {\n        "default_auto": "...",\n        "model": "...",
    for task_type, model in FABRIK_TASK_MODELS.items():
        # Match the model line within a TaskType block
        pattern = rf'(TaskType\.{task_type}:\s*\{{\s*[^}}]*?"model":\s*")[^"]+(")'

        match = re.search(pattern, content, re.DOTALL)
        if match:
            old_model = content[match.start(1) : match.end(2)]
            old_model_name = re.search(r'"model":\s*"([^"]+)"', old_model)
            if old_model_name and old_model_name.group(1) != model:
                content = re.sub(pattern, rf"\g<1>{model}\g<2>", content, count=1)
                result["changes"].append(
                    f"TaskType.{task_type}: {old_model_name.group(1)} → {model}"
                )

    if content != original:
        tasks_file.write_text(content)
        result["status"] = "updated"
    else:
        result["status"] = "no_changes"

    return result


def sync_agents_md() -> dict:
    """
    Update model names in AGENTS.md execution modes table from FABRIK_EXECUTION_MODES.

    Returns dict with status and changes made.
    """
    import re

    agents_file = Path(__file__).parent.parent / "AGENTS.md"
    result = {"status": "ok", "changes": [], "errors": []}

    if not agents_file.exists():
        result["status"] = "error"
        result["errors"].append(f"File not found: {agents_file}")
        return result

    content = agents_file.read_text()
    original = content

    # Build the new table
    new_table_lines = [
        "| Mode | Task Type | Model | Reasoning | Autonomy |",
        "|------|-----------|-------|-----------|----------|",
    ]
    for mode, cfg in FABRIK_EXECUTION_MODES.items():
        new_table_lines.append(
            f"| {mode} | `{cfg['task']}` | {cfg['model']} | {cfg['reasoning']} | {cfg['autonomy']} |"
        )
    new_table = "\n".join(new_table_lines)

    # Find and replace the execution modes table
    # Match from "| Mode | Task Type |" to the next blank line or section
    pattern = r"\| Mode \| Task Type \| Model \| Reasoning \| Autonomy \|.*?\n\|[^\n]+\|\n(?:\| [^\n]+\|\n)+"

    match = re.search(pattern, content)
    if match:
        old_table = match.group(0).strip()
        if old_table != new_table:
            content = content[: match.start()] + new_table + "\n" + content[match.end() :]
            result["changes"].append("Updated Execution Modes table")

    if content != original:
        agents_file.write_text(content)
        result["status"] = "updated"
    else:
        result["status"] = "no_changes"

    return result


def sync_droid_exec_usage() -> dict:
    """
    Update model names in droid-exec-usage.md from FABRIK_EXECUTION_MODES and MODELS.

    Updates:
    - Mode Overview table (section 12)
    - Model pricing table (section 13)

    Returns dict with status and changes made.
    """
    import re

    docs_file = Path(__file__).parent.parent / "docs" / "reference" / "droid-exec-usage.md"
    result = {"status": "ok", "changes": [], "errors": []}

    if not docs_file.exists():
        result["status"] = "error"
        result["errors"].append(f"File not found: {docs_file}")
        return result

    content = docs_file.read_text()
    original = content

    # Update Mode Overview table (section 12)
    # Example row: | 1 | **Explore** | gemini-3-flash-preview | droid | you | claude-sonnet-4-5-20250929 | 0.2× → 1.2× |
    mode_rows = {
        "Explore": ("gemini-3-flash-preview", "claude-sonnet-4-5-20250929", "0.2× → 1.2×"),
        "Design": ("claude-sonnet-4-5-20250929", "claude-opus-4-5-20251101", "1.2× → 2.0×"),
        "Build": ("SWE-1.5", "gpt-5.1-codex-max", "Free → 0.5×"),
        "Verify": ("gpt-5.1-codex-max", "claude-opus-4-5-20251101", "0.5× → 2.0×"),
        "Ship": ("gemini-3-flash-preview", "claude-haiku-4-5-20251001", "0.2× → 0.4×"),
    }

    for i, (mode_name, (executor, escalation, cost)) in enumerate(mode_rows.items(), 1):
        source = "windsurf" if mode_name == "Build" else "droid"
        decider = "droid" if mode_name == "Verify" else "you"
        # Match the row pattern loosely and replace with correct values
        pattern = rf"\| {i} \| \*\*{mode_name}\*\* \|[^|]+\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|"
        replacement = (
            f"| {i} | **{mode_name}** | {executor} | {source} | {decider} | {escalation} | {cost} |"
        )
        content = re.sub(pattern, replacement, content)

    # Update Model pricing table - ensure full model names
    model_updates = [
        ("claude-haiku-4-5[^0-9-]", "claude-haiku-4-5-20251001"),
        ("claude-sonnet-4-5[^0-9-]", "claude-sonnet-4-5-20250929"),
        ("claude-opus-4-5[^0-9-]", "claude-opus-4-5-20251101"),
    ]

    for pattern, replacement in model_updates:
        # Only replace in table rows (lines starting with |)
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("|") and re.search(pattern, line):
                # Extract just the model name part and replace
                lines[i] = re.sub(pattern, replacement + " ", line)
        content = "\n".join(lines)

    if content != original:
        docs_file.write_text(content)
        result["status"] = "updated"
        result["changes"].append("Updated Mode Overview table with full model names")
    else:
        result["status"] = "no_changes"

    return result


def sync_windsurfrules() -> dict:
    """
    Update skill triggers in windsurfrules to match AGENTS.md.

    Returns dict with status and changes made.
    """
    # windsurfrules is already updated manually, this ensures consistency
    result = {"status": "no_changes", "changes": [], "errors": []}
    return result


def sync_all_models() -> dict:
    """
    Sync model names across all Fabrik files from the canonical FABRIK_TASK_MODELS.

    This is the main entry point - run: python droid_models.py sync
    """
    results = {
        "droid_tasks.py": sync_droid_tasks(),
        "AGENTS.md": sync_agents_md(),
        "droid-exec-usage.md": sync_droid_exec_usage(),
    }

    return results


if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "droid"

    if cmd == "stack-rank":
        print_stack_rankings()

    elif cmd == "recommend":
        if len(sys.argv) > 2:
            print_scenario_recommendation(sys.argv[2])
        else:
            list_scenarios()

    elif cmd == "check-updates":
        print("Checking Factory docs for model updates...")
        print("=" * 60)

        # Show current config version
        version = get_config_version()
        print(f"Current config version: {version}")
        print(f"Config file: {CONFIG_FILE}")
        print()

        # Refresh from docs
        print("Fetching from Factory docs...")
        result = refresh_models_from_docs()

        if result["errors"]:
            print(f"⚠️  Errors: {result['errors']}")

        models_found = result.get("models_found", [])
        new_models = result.get("new_models", [])

        print(f"Models found in docs: {len(models_found)}")

        if new_models:
            print("\n🆕 NEW MODELS DETECTED:")
            for m in new_models:
                print(f"   • {m}")
            print("\nAction required:")
            print("  1. Check https://docs.factory.ai/cli/user-guides/choosing-your-model")
            print("  2. Update config/models.yaml with new rankings")
            print("  3. Run: python scripts/droid_models.py sync")
        else:
            print("\n✓ No new models detected. Registry is up to date.")

        print(f"\nCache saved: {CACHE_FILE}")

    elif cmd == "sync":
        print("Syncing model names across Fabrik files...")
        print(f"Source of truth: FABRIK_TASK_MODELS in {Path(__file__).name}")
        print()

        results = sync_all_models()

        for file, result in results.items():
            status = result["status"]
            if status == "updated":
                print(f"✓ {file}: Updated")
                for change in result["changes"]:
                    print(f"    {change}")
            elif status == "no_changes":
                print(f"• {file}: Already in sync")
            else:
                print(f"✗ {file}: {result['errors']}")

        print("\nTo change model assignments, edit FABRIK_TASK_MODELS in droid_models.py")
        print("then run: python scripts/droid_models.py sync")

    elif cmd == "refresh":
        print("Refreshing models from Factory docs...")
        print("  - https://docs.factory.ai/pricing")
        print("  - https://docs.factory.ai/cli/user-guides/choosing-your-model")
        print()

        result = refresh_models_from_docs()

        # Normalize to lowercase for comparison
        models_lower = sorted({m.lower() for m in result["models_found"]})
        print(f"Models found ({len(models_lower)}):")
        for m in models_lower:
            in_registry = "✓" if m in MODELS else "NEW"
            print(f"  {in_registry} {m}")

        if result["new_models"]:
            print(f"\n⚠️  New models detected: {result['new_models']}")
            print("   Update MODELS dict in droid_models.py to add them.")
        else:
            print("\n✓ All models are in registry.")

        if result["errors"]:
            print(f"\nErrors: {result['errors']}")

        print(f"\nCache saved to: {CACHE_FILE}")

    elif cmd == "modes":
        print_execution_modes()
        print("\nMode Details:")
        for _mode, cfg in EXECUTION_MODES.items():
            print(f"  {cfg.name}: {cfg.description}")

    elif cmd == "windsurf":
        category = sys.argv[2] if len(sys.argv) > 2 else None
        print_windsurf_models(category)
        if not category:
            print(
                "\nFilter by category: python droid_models.py windsurf <free|budget|standard|premium|ultra>"
            )

    elif cmd == "droid":
        print("Available Droid Models:\n")
        print_model_table()
        print(f"\nDefault: {DEFAULT_MODEL}")
        print(f"\nConfig version: {get_config_version()}")

    else:
        print("Droid Model Registry")
        print("=" * 40)
        print(f"Config version: {get_config_version()}")
        print(f"Config file: {CONFIG_FILE}")
        print("\nCommands:")
        print("  python droid_models.py              # Show droid models")
        print("  python droid_models.py stack-rank   # Show model stack rankings (from config)")
        print("  python droid_models.py recommend    # List scenarios")
        print("  python droid_models.py recommend <scenario>  # Get model for scenario")
        print("  python droid_models.py check-updates # Check Factory docs for new models")
        print("  python droid_models.py modes        # Show execution modes")
        print("  python droid_models.py windsurf     # Show Windsurf models")
        print("  python droid_models.py sync         # Sync model names across files")
        print("\nScenarios: deep_planning, full_feature_dev, ci_cd, explore, design, verify, ship")
