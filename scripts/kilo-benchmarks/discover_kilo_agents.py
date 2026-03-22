#!/usr/bin/env python3
"""
Discover all available Kilo agents and save to kilo_all_agents.json.

This creates a comprehensive catalog of ALL available Kilo models (~332)
with pricing, provider info, and capabilities.

Usage:
    python scripts/discover_kilo_agents.py
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

FABRIK_ROOT = Path(__file__).parent.parent
ALL_AGENTS_JSON = FABRIK_ROOT / "scripts" / "kilo_all_agents.json"


def log(msg: str) -> None:
    print(f"[kilo-discover] {msg}")


def get_all_models() -> list[str]:
    """Get all available Kilo models."""
    result = subprocess.run(
        ["kilo", "models"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    models = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
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
    log("Discovering all Kilo agents...")

    models = get_all_models()
    log(f"Found {len(models)} models")

    agents = []
    for full_name in models:
        info = parse_model_info(full_name)
        agents.append(info)

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
