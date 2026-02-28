#!/usr/bin/env python3
"""
Extract separate input/output pricing for priority Kilo models.

Uses 2-call algebraic method:
1. Short input call (minimize input tokens)
2. Long input call (maximize input tokens)
3. Solve system of equations for input/output prices

Usage:
    python extract_pricing.py --test              # Test on 2 models
    python extract_pricing.py --run               # Extract all shortlist
    python extract_pricing.py --model <model_id>  # Single model
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np


def make_kilo_call(model: str, message: str) -> dict | None:
    """Make a Kilo API call and extract cost/token data."""
    try:
        result = subprocess.run(
            ["kilo", "run", "--model", model, "--message", message, "--format", "json"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        for line in result.stdout.strip().split("\n"):
            try:
                event = json.loads(line)
                if event.get("type") == "step_finish":
                    part = event.get("part", {})
                    return {
                        "cost": part.get("cost", 0),
                        "input": part.get("tokens", {}).get("input", 0),
                        "output": part.get("tokens", {}).get("output", 0),
                        "total": part.get("tokens", {}).get("total", 0),
                    }
            except json.JSONDecodeError:
                continue

        return None
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        print(f"  ✗ API call failed: {e}")
        return None


def extract_pricing(model_id: str) -> dict | None:
    """Extract input/output pricing for a model using 2-call method."""
    print(f"\nExtracting: {model_id}")
    print("-" * 80)

    # Call 1: Short input, allow normal output
    print("  Call 1: Short input...")
    call1 = make_kilo_call(model_id, "What is 2+2? Respond briefly.")

    if not call1:
        return None

    print(f"    Cost: ${call1['cost']:.6f}, Input: {call1['input']}, Output: {call1['output']}")

    # Call 2: Long input (maximize input tokens), request minimal output
    long_prompt = (
        "Please respond with only 'OK' and nothing else. Do not explain. "
        "Context for reference (ignore this): "
        + ("Machine learning involves training models on data. " * 200)  # ~2000 tokens input
    )
    print("  Call 2: Long input...")
    call2 = make_kilo_call(model_id, long_prompt)

    if not call2:
        return None

    print(f"    Cost: ${call2['cost']:.6f}, Input: {call2['input']}, Output: {call2['output']}")

    # Solve system of equations: Ax = b
    # [input1, output1] [price_in ] = [cost1]
    # [input2, output2] [price_out] = [cost2]

    a = np.array([[call1["input"], call1["output"]], [call2["input"], call2["output"]]])
    b = np.array([call1["cost"], call2["cost"]])

    try:
        prices = np.linalg.solve(a, b)

        # Convert to per-1M tokens
        price_in_per_1m = prices[0] * 1_000_000
        price_out_per_1m = prices[1] * 1_000_000

        # Verify solution
        calc_cost1 = (call1["input"] * prices[0]) + (call1["output"] * prices[1])
        calc_cost2 = (call2["input"] * prices[0]) + (call2["output"] * prices[1])
        error1 = abs(call1["cost"] - calc_cost1)
        error2 = abs(call2["cost"] - calc_cost2)

        print(f"  ✓ Input:  ${price_in_per_1m:.4f}/1M tokens")
        print(f"  ✓ Output: ${price_out_per_1m:.4f}/1M tokens")
        print(f"  ✓ Ratio:  {price_out_per_1m / price_in_per_1m:.2f}x")
        print(f"  ✓ Verification error: ${error1:.6f}, ${error2:.6f}")

        return {
            "input_per_1m": round(price_in_per_1m, 4),
            "output_per_1m": round(price_out_per_1m, 4),
            "verification": {
                "call1_error": round(error1, 6),
                "call2_error": round(error2, 6),
                "call1_tokens": {"input": call1["input"], "output": call1["output"]},
                "call2_tokens": {"input": call2["input"], "output": call2["output"]},
            },
        }

    except np.linalg.LinAlgError:
        print("  ✗ Cannot solve - linearly dependent equations")
        return None


def main():
    parser = argparse.ArgumentParser(description="Extract Kilo model pricing")
    parser.add_argument("--test", action="store_true", help="Test on 2 models only")
    parser.add_argument("--run", action="store_true", help="Extract all shortlist models")
    parser.add_argument("--model", type=str, help="Extract single model")
    args = parser.parse_args()

    # Load shortlist
    shortlist_path = Path("/opt/fabrik/scripts/kilo_pricing_shortlist.json")
    if not shortlist_path.exists():
        print("✗ Shortlist not found. Run identification script first.")
        sys.exit(1)

    with open(shortlist_path) as f:
        data = json.load(f)
        shortlist = data["models"]

    # Determine models to process
    if args.model:
        models = [m for m in shortlist if m["full_name"] == args.model]
        if not models:
            print(f"✗ Model {args.model} not in shortlist")
            sys.exit(1)
    elif args.test:
        models = shortlist[:2]
        print("TEST MODE: Processing first 2 models only")
    elif args.run:
        models = shortlist
    else:
        parser.print_help()
        sys.exit(1)

    print("=" * 80)
    print("KILO PRICING EXTRACTION")
    print(f"Models to process: {len(models)}")
    print(f"Estimated time: ~{len(models) * 4 // 60} minutes")
    print("=" * 80)

    # Extract pricing
    results = {}
    success = 0
    failed = 0

    for i, model in enumerate(models, 1):
        print(f"\n[{i}/{len(models)}]", end=" ")

        pricing = extract_pricing(model["full_name"])

        if pricing:
            results[model["full_name"]] = pricing
            success += 1
        else:
            failed += 1

        # Rate limit: 2 second pause between models (4 calls per model)
        if i < len(models):
            time.sleep(2)

    # Save results
    output_path = Path("/opt/fabrik/scripts/kilo_pricing_extracted.json")
    with open(output_path, "w") as f:
        json.dump(
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "total_models": len(models),
                "successful": success,
                "failed": failed,
                "pricing": results,
            },
            f,
            indent=2,
        )

    print("\n" + "=" * 80)
    print("EXTRACTION COMPLETE")
    print("=" * 80)
    print(f"Success: {success}/{len(models)} models")
    print(f"Failed:  {failed}/{len(models)} models")
    print(f"Saved to: {output_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
