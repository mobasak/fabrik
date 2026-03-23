#!/usr/bin/env python3
"""
Discover all available Kilo agents and save to kilo_all_agents.json.

This creates a comprehensive catalog of ALL available Kilo models (~332)
with pricing, provider info, and capabilities including reasoning.

Usage:
    python scripts/kilo-benchmarks/discover_kilo_agents.py

When updating: Also update README.md in this folder.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
ALL_AGENTS_JSON = SCRIPT_DIR / "kilo_all_agents.json"


def log(msg: str) -> None:
    print(f"[kilo-discover] {msg}")


def get_all_models_verbose() -> list[dict]:
    """Get all available Kilo models with full metadata."""
    result = subprocess.run(
        ["kilo", "models", "--verbose"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    models = []
    current_model = None
    json_lines = []
    brace_depth = 0

    for line in result.stdout.split("\n"):
        line_stripped = line.strip()

        # Model ID line (starts with kilo/)
        if line_stripped.startswith("kilo/") and brace_depth == 0:
            current_model = line_stripped
            continue

        # Count braces in this line
        open_braces = line.count("{")
        close_braces = line.count("}")

        # Start or continue JSON block
        if open_braces > 0 or brace_depth > 0:
            if brace_depth == 0 and open_braces > 0:
                json_lines = []
            json_lines.append(line)
            brace_depth += open_braces - close_braces

            # Complete JSON block
            if brace_depth == 0 and json_lines:
                try:
                    data = json.loads("\n".join(json_lines))
                    data["full_name"] = current_model or f"kilo/{data.get('id', 'unknown')}"
                    models.append(data)
                except json.JSONDecodeError as e:
                    log(f"Failed to parse JSON for {current_model}: {e}")
                json_lines = []

    return models


def parse_model_info(full_name: str) -> dict:
    """Parse model info from full name like kilo/anthropic/claude-3.5-sonnet."""
    parts = full_name.split("/")
    if len(parts) >= 3:
        provider = parts[1]
        model_name = "/".join(parts[2:])
    elif len(parts) == 2:
        provider = parts[0]
        model_name = parts[1]
    else:
        provider = "unknown"
        model_name = full_name

    # Detect if free model
    is_free = ":free" in model_name.lower() or "free" in model_name.lower()

    # Provider display name mapping
    provider_display = {
        "anthropic": "Anthropic",
        "openai": "OpenAI",
        "google": "Google",
        "meta-llama": "Meta",
        "mistralai": "Mistral",
        "deepseek": "DeepSeek",
        "alibaba": "Alibaba",
        "cohere": "Cohere",
        "zhipu": "Zhipu",
        "x-ai": "xAI",
        "amazon": "Amazon",
        "nvidia": "NVIDIA",
        "microsoft": "Microsoft",
        "bytedance-seed": "ByteDance",
        "bytedance": "ByteDance",
        "baidu": "Baidu",
        "tencent": "Tencent",
        "minimax": "MiniMax",
        "moonshot": "Moonshot",
        "stepfun": "StepFun",
        "allenai": "AllenAI",
        "arcee-ai": "Arcee",
        "aion-labs": "Aion",
        "ai21": "AI21",
    }.get(provider, provider.title())

    return {
        "full_name": full_name,
        "provider": provider_display,
        "provider_id": provider,
        "model_name": model_name,
        "is_free": is_free,
    }


def main() -> int:
    log("Discovering all Kilo agents with full metadata...")

    raw_models = get_all_models_verbose()
    log(f"Found {len(raw_models)} models with metadata")

    agents = []
    reasoning_count = 0
    for model_data in raw_models:
        full_name = model_data.get("full_name", "")
        basic_info = parse_model_info(full_name)

        # Extract ALL capabilities from verbose output
        caps = model_data.get("capabilities", {})
        input_caps = caps.get("input", {})
        output_caps = caps.get("output", {})
        cost = model_data.get("cost", {})
        cache_cost = cost.get("cache", {})
        limit = model_data.get("limit", {})

        agent = {
            **basic_info,
            "name": model_data.get("name", basic_info["model_name"]),
            "status": model_data.get("status", "unknown"),
            "release_date": model_data.get("release_date"),
            # Core capabilities
            "has_reasoning": caps.get("reasoning", False),
            "has_tools": caps.get("toolcall", False),
            "has_attachment": caps.get("attachment", False),
            "has_temperature": caps.get("temperature", False),
            "has_interleaved": caps.get("interleaved", False),
            # Input modalities
            "input_text": input_caps.get("text", False),
            "input_image": input_caps.get("image", False),
            "input_audio": input_caps.get("audio", False),
            "input_video": input_caps.get("video", False),
            "input_pdf": input_caps.get("pdf", False),
            # Output modalities
            "output_text": output_caps.get("text", False),
            "output_image": output_caps.get("image", False),
            "output_audio": output_caps.get("audio", False),
            "output_video": output_caps.get("video", False),
            # Cost (per token)
            "input_cost": cost.get("input", 0),
            "output_cost": cost.get("output", 0),
            "cache_read_cost": cache_cost.get("read", 0),
            "cache_write_cost": cache_cost.get("write", 0),
            # Limits
            "context_window": limit.get("context", 0),
            "max_output": limit.get("output", 0),
            # Variants (for thinking modes etc)
            "variants": model_data.get("variants", {}),
            # Raw capabilities for future use
            "_raw_capabilities": caps,
        }
        agents.append(agent)

        if agent["has_reasoning"]:
            reasoning_count += 1

    log(f"Models with reasoning: {reasoning_count}/{len(agents)}")

    # Group by provider for stats
    providers = {}
    for agent in agents:
        p = agent["provider"]
        providers[p] = providers.get(p, 0) + 1

    # Sort agents by provider then model name
    agents.sort(key=lambda x: (x["provider"], x["model_name"]))

    # Build output
    output = {
        "timestamp": datetime.now().isoformat(),
        "total_models": len(agents),
        "providers": dict(sorted(providers.items(), key=lambda x: -x[1])),
        "description": "All available Kilo CLI models. Use kilo_selected_agents.json for curated production agents.",
        "models": agents,
    }

    ALL_AGENTS_JSON.write_text(json.dumps(output, indent=2))
    log(f"Saved to {ALL_AGENTS_JSON}")

    # Print top providers
    log("Top providers:")
    for provider, count in sorted(providers.items(), key=lambda x: -x[1])[:10]:
        log(f"  {provider}: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
