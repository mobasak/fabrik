#!/usr/bin/env python3
"""
Extract separate input/output pricing using proper regression method.

Uses multi-call regression (5 calls per model) to fit:
    cost = a*input_uncached + b*output + k

Where:
    a = input token price
    b = output token price
    k = per-request overhead (often ~0)

Accounts for cached tokens by using (input - cache.read).

Usage:
    python extract_pricing_regression.py --test              # Test on 1 model
    python extract_pricing_regression.py --run               # Extract all missing pricing
    python extract_pricing_regression.py --model <model_id>  # Single model
"""

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

import numpy as np


def make_kilo_call(model: str, message: str, temperature: float = 0.0) -> dict | None:
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
                    tokens = part.get("tokens", {})
                    cache = tokens.get("cache", {})

                    return {
                        "cost": part.get("cost", 0),
                        "input": tokens.get("input", 0),
                        "output": tokens.get("output", 0),
                        "cache_read": cache.get("read", 0),
                        "cache_write": cache.get("write", 0),
                        "input_uncached": tokens.get("input", 0) - cache.get("read", 0),
                    }
            except json.JSONDecodeError:
                continue

        return None
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        print(f"  ✗ API call failed: {e}")
        return None


def generate_unique_prompt(test_case: str) -> str:
    """Generate unique prompts to prevent cache hits."""
    uid = f"{time.time():.6f}_{random.randint(10000, 99999)}"

    topics = [
        "machine learning",
        "quantum computing",
        "blockchain",
        "artificial intelligence",
        "cybersecurity",
        "cloud computing",
        "data science",
        "software engineering",
        "devops",
        "robotics",
    ]

    filler_words = [
        "innovation",
        "technology",
        "development",
        "research",
        "implementation",
        "optimization",
        "architecture",
        "framework",
    ]

    if test_case == "short_in_long_out":
        return f"Write exactly 150 words about {random.choice(topics)}. ID:{uid}"

    elif test_case == "short_in_med_out":
        return f"Explain {random.choice(topics)} in 80 words. ID:{uid}"

    elif test_case == "med_in_med_out":
        context = " ".join([random.choice(filler_words) for _ in range(100)])
        return f"Given context: {context}. Summarize in 100 words. ID:{uid}"

    elif test_case == "long_in_short_out":
        filler = " ".join(
            [f"{random.choice(topics)} involves {random.choice(filler_words)}." for _ in range(300)]
        )
        return f"Say only 'Understood'. Context: {filler}. ID:{uid}"

    elif test_case == "long_in_minimal_out":
        filler = " ".join([f"Topic {i}: {random.choice(topics)}." for i in range(400)])
        return f"Reply with only 'OK'. Reference data: {filler}. ID:{uid}"

    return f"Test. ID:{uid}"


def extract_pricing_regression(model_id: str) -> dict | None:
    """Extract input/output pricing using 5-call regression method."""
    print(f"\nExtracting: {model_id}")
    print("-" * 80)

    # Make 5 calls with varied input/output ratios
    test_cases = [
        "short_in_long_out",
        "short_in_med_out",
        "med_in_med_out",
        "long_in_short_out",
        "long_in_minimal_out",
    ]

    calls = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"  Call {i}/5 ({test_case})...", end=" ")

        prompt = generate_unique_prompt(test_case)
        result = make_kilo_call(model_id, prompt)

        if not result:
            print("FAILED")
            return None

        calls.append(result)
        print(
            f"Cost=${result['cost']:.6f}, In={result['input_uncached']}, Out={result['output']}, CacheRead={result['cache_read']}"
        )

        # Wait between calls to ensure session cleanup
        if i < len(test_cases):
            time.sleep(2)

    # Regression: cost = a*input_uncached + b*output + k
    x = np.array([[c["input_uncached"], c["output"], 1] for c in calls])
    y = np.array([c["cost"] for c in calls])

    try:
        # Solve using least squares
        params, residuals, rank, s = np.linalg.lstsq(x, y, rcond=None)

        input_price_per_token = params[0]
        output_price_per_token = params[1]
        intercept = params[2]

        # Calculate per-1M prices
        input_per_1m = input_price_per_token * 1_000_000
        output_per_1m = output_price_per_token * 1_000_000
        intercept_per_call = intercept

        # Calculate fit quality
        predictions = x @ params
        errors = np.abs(y - predictions)
        max_error_pct = (errors / y * 100).max()
        mean_error_pct = (errors / y * 100).mean()
    except np.linalg.LinAlgError as e:
        print(f"  ✗ Regression failed: {e}")
        return None

    # Validation checks
    fit_ok = max_error_pct < 5.0  # Allow 5% error
    prices_positive = input_per_1m > 0 and output_per_1m > 0
    ratio_reasonable = 2 <= (output_per_1m / input_per_1m) <= 20
    intercept_small = abs(intercept_per_call) < 0.01  # Less than 1 cent overhead

    status = "✓" if (fit_ok and prices_positive and ratio_reasonable) else "⚠"

    print(f"\n  {status} Results:")
    print(f"    Input:  ${input_per_1m:.4f}/1M tokens")
    print(f"    Output: ${output_per_1m:.4f}/1M tokens")
    print(f"    Ratio:  {output_per_1m / input_per_1m:.2f}x")
    print(f"    Intercept: ${intercept_per_call:.6f} per call")
    print(f"    Max error: {max_error_pct:.2f}%")
    print(f"    Mean error: {mean_error_pct:.2f}%")

    if not fit_ok:
        print(f"  ⚠ Warning: Fit error {max_error_pct:.1f}% exceeds 5% threshold")
    if not ratio_reasonable:
        print(
            f"  ⚠ Warning: Ratio {output_per_1m / input_per_1m:.1f}x outside expected 2-20x range"
        )
    if not intercept_small:
        print(f"  ⚠ Warning: Large per-call overhead ${intercept_per_call:.6f}")

    return {
        "input_per_1m": round(input_per_1m, 4),
        "output_per_1m": round(output_per_1m, 4),
        "intercept_per_call": round(intercept_per_call, 6),
        "validation": {
            "max_error_pct": round(max_error_pct, 2),
            "mean_error_pct": round(mean_error_pct, 2),
            "fit_ok": fit_ok,
            "ratio": round(output_per_1m / input_per_1m, 2),
            "calls": [
                {
                    "input_uncached": c["input_uncached"],
                    "output": c["output"],
                    "cache_read": c["cache_read"],
                    "cost": c["cost"],
                }
                for c in calls
            ],
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Extract Kilo model pricing using regression")
    parser.add_argument("--test", action="store_true", help="Test on 1 model only")
    parser.add_argument("--run", action="store_true", help="Extract all models missing pricing")
    parser.add_argument("--model", type=str, help="Extract single model")
    args = parser.parse_args()

    # Load models needing extraction
    missing_path = Path("/opt/fabrik/scripts/kilo_models_missing_pricing.json")
    if not missing_path.exists():
        print("✗ Missing pricing file not found. Run comparison script first.")
        sys.exit(1)

    with open(missing_path) as f:
        data = json.load(f)
        models_needed = data["models_needing_extraction"]

    # Determine models to process
    if args.model:
        models = [m for m in models_needed if m["full_name"] == args.model]
        if not models:
            print(f"✗ Model {args.model} not in missing list")
            sys.exit(1)
    elif args.test:
        models = models_needed[:1]
        print("TEST MODE: Processing first model only")
    elif args.run:
        models = models_needed
    else:
        parser.print_help()
        sys.exit(1)

    print("=" * 80)
    print("KILO PRICING EXTRACTION - REGRESSION METHOD")
    print("=" * 80)
    print(f"Models to process: {len(models)}")
    print(f"Estimated time: ~{len(models) * 1} minutes (5 calls per model)")
    print("=" * 80)

    # Extract pricing
    results = {}
    success = 0
    failed = 0

    for i, model in enumerate(models, 1):
        print(f"\n[{i}/{len(models)}]", end=" ")

        pricing = extract_pricing_regression(model["full_name"])

        if pricing:
            results[model["full_name"]] = pricing
            success += 1
        else:
            failed += 1

    # Save results
    output_path = Path("/opt/fabrik/scripts/kilo_pricing_regression_results.json")
    with open(output_path, "w") as f:
        json.dump(
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "method": "multi_call_regression",
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
