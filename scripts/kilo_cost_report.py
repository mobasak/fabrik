#!/usr/bin/env python3
"""
Kilo Cost Report - Analyze Kilo usage and costs.

Reads .droid/kilo_usage.jsonl and .droid/kilo_metrics.jsonl to generate cost reports.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_usage_log(file_path: Path) -> list[dict[str, Any]]:
    """Load usage entries from JSONL file."""
    if not file_path.exists():
        return []

    entries = []
    with open(file_path) as f:
        for line in f:
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def load_metrics(file_path: Path) -> list[dict[str, Any]]:
    """Load metrics entries from JSONL file."""
    if not file_path.exists():
        return []

    metrics = []
    with open(file_path) as f:
        for line in f:
            if line.strip():
                try:
                    metrics.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return metrics


def generate_cost_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate overall cost summary from usage entries."""
    total_cost = sum(e.get("cost_usd", 0.0) for e in entries)
    total_review_cost = sum(e.get("review_cost_usd", 0.0) for e in entries)
    total_fix_cost = sum(e.get("fix_cost_usd", 0.0) for e in entries)
    total_runs = len(entries)
    total_tokens = sum(e.get("total_tokens", 0) for e in entries)

    return {
        "total_runs": total_runs,
        "total_cost": round(total_cost, 2),
        "review_cost": round(total_review_cost, 2),
        "fix_cost": round(total_fix_cost, 2),
        "total_tokens": total_tokens,
        "avg_cost_per_run": round(total_cost / total_runs, 4) if total_runs > 0 else 0.0,
    }


def generate_model_breakdown(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate cost breakdown by model."""
    model_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"runs": 0, "cost": 0.0, "tokens": 0}
    )

    for entry in entries:
        model = entry.get("model", "unknown")
        model_stats[model]["runs"] += 1
        model_stats[model]["cost"] += entry.get("cost_usd", 0.0)
        model_stats[model]["tokens"] += entry.get("total_tokens", 0)

    breakdown = []
    for model, stats in sorted(model_stats.items(), key=lambda x: x[1]["cost"], reverse=True):
        breakdown.append(
            {
                "model": model,
                "runs": stats["runs"],
                "total_cost": round(stats["cost"], 2),
                "total_tokens": stats["tokens"],
                "avg_cost_per_run": round(stats["cost"] / stats["runs"], 4)
                if stats["runs"] > 0
                else 0.0,
            }
        )

    return breakdown


def generate_filetype_breakdown(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate performance breakdown by file type."""
    filetype_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "total_reviews": 0,
            "weighted_iterations": 0.0,
            "weighted_cost": 0.0,
            "weighted_pass_rate": 0.0,
        }
    )

    for metric in metrics:
        file_type = metric.get("file_type", "unknown")
        reviews = metric.get("total_reviews", 0)
        filetype_stats[file_type]["total_reviews"] += reviews
        # Weighted averages: multiply by review count for proper aggregation
        filetype_stats[file_type]["weighted_iterations"] += (
            metric.get("avg_iterations", 0.0) * reviews
        )
        filetype_stats[file_type]["weighted_cost"] += metric.get("avg_cost", 0.0) * reviews
        filetype_stats[file_type]["weighted_pass_rate"] += metric.get("pass_rate", 0.0) * reviews

    breakdown = []
    for file_type, stats in sorted(
        filetype_stats.items(), key=lambda x: x[1]["total_reviews"], reverse=True
    ):
        reviews = stats["total_reviews"]
        breakdown.append(
            {
                "file_type": file_type,
                "total_reviews": reviews,
                "avg_iterations": round(stats["weighted_iterations"] / reviews, 2)
                if reviews > 0
                else 0.0,
                "avg_cost": round(stats["weighted_cost"] / reviews, 4) if reviews > 0 else 0.0,
                "avg_pass_rate": round(stats["weighted_pass_rate"] / reviews, 2)
                if reviews > 0
                else 0.0,
            }
        )

    return breakdown


def format_report_text(summary: dict[str, Any], model_breakdown: list[dict[str, Any]]) -> str:
    """Format report as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("KILO COST REPORT")
    lines.append("=" * 60)
    lines.append("")
    lines.append("SUMMARY")
    lines.append("-" * 60)
    lines.append(f"Total Runs:        {summary['total_runs']}")
    lines.append(f"Total Cost:        ${summary['total_cost']:.2f}")
    lines.append(f"  Review Cost:     ${summary['review_cost']:.2f}")
    lines.append(f"  Fix Cost:        ${summary['fix_cost']:.2f}")
    lines.append(f"Total Tokens:      {summary['total_tokens']:,}")
    lines.append(f"Avg Cost/Run:      ${summary['avg_cost_per_run']:.4f}")
    lines.append("")
    lines.append("MODEL BREAKDOWN")
    lines.append("-" * 60)
    lines.append(f"{'Model':<40} {'Runs':<8} {'Cost':<10} {'Avg/Run':<10}")
    lines.append("-" * 60)
    for model in model_breakdown:
        lines.append(
            f"{model['model']:<40} {model['runs']:<8} ${model['total_cost']:<9.2f} ${model['avg_cost_per_run']:<9.4f}"
        )
    lines.append("=" * 60)
    return "\n".join(lines)


def format_report_json(
    summary: dict[str, Any],
    model_breakdown: list[dict[str, Any]],
    filetype_breakdown: list[dict[str, Any]],
) -> str:
    """Format report as JSON."""
    report = {
        "summary": summary,
        "by_model": model_breakdown,
        "by_filetype": filetype_breakdown,
    }
    return json.dumps(report, indent=2)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Analyze Kilo usage and costs")
    parser.add_argument(
        "--usage-log",
        type=Path,
        default=Path(".droid/kilo_usage.jsonl"),
        help="Path to usage log file (default: .droid/kilo_usage.jsonl)",
    )
    parser.add_argument(
        "--metrics",
        type=Path,
        default=Path(".droid/kilo_metrics.jsonl"),  # Reserved: no script writes this yet
        help="Path to metrics JSONL file (reserved for future kilo metrics collection)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--by-model",
        action="store_true",
        help="Show breakdown by model",
    )
    parser.add_argument(
        "--by-filetype",
        action="store_true",
        help="Show breakdown by file type",
    )

    args = parser.parse_args()

    # Load data
    usage_entries = load_usage_log(args.usage_log)
    if not usage_entries:
        print(f"No usage data found in {args.usage_log}", file=sys.stderr)
        return 1

    # Generate reports
    summary = generate_cost_summary(usage_entries)
    model_breakdown = generate_model_breakdown(usage_entries)

    filetype_breakdown = []
    if args.by_filetype or args.format == "json":
        metrics_entries = load_metrics(args.metrics)
        if metrics_entries:
            filetype_breakdown = generate_filetype_breakdown(metrics_entries)

    # Output
    if args.format == "json":
        print(format_report_json(summary, model_breakdown, filetype_breakdown))
    else:
        # Text output: show summary always, model/filetype based on flags
        lines = []
        lines.append("=" * 60)
        lines.append("KILO COST REPORT")
        lines.append("=" * 60)
        lines.append("")
        lines.append("SUMMARY")
        lines.append("-" * 60)
        lines.append(f"Total Runs:        {summary['total_runs']}")
        lines.append(f"Total Cost:        ${summary['total_cost']:.2f}")
        lines.append(f"  Review Cost:     ${summary['review_cost']:.2f}")
        lines.append(f"  Fix Cost:        ${summary['fix_cost']:.2f}")
        lines.append(f"Total Tokens:      {summary['total_tokens']:,}")
        lines.append(f"Avg Cost/Run:      ${summary['avg_cost_per_run']:.4f}")
        print("\n".join(lines))

        if args.by_model:
            print("")
            print("MODEL BREAKDOWN")
            print("-" * 60)
            print(f"{'Model':<40} {'Runs':<8} {'Cost':<10} {'Avg/Run':<10}")
            print("-" * 60)
            for model in model_breakdown:
                print(
                    f"{model['model']:<40} {model['runs']:<8} "
                    f"${model['total_cost']:<9.2f} ${model['avg_cost_per_run']:<9.4f}"
                )

        if args.by_filetype and filetype_breakdown:
            print("\nFILE TYPE BREAKDOWN")
            print("-" * 60)
            print(
                f"{'Type':<12} {'Reviews':<10} {'Avg Iter':<12} {'Avg Cost':<12} {'Pass Rate':<10}"
            )
            print("-" * 60)
            for ft in filetype_breakdown:
                print(
                    f"{ft['file_type']:<12} {ft['total_reviews']:<10} "
                    f"{ft['avg_iterations']:<12.2f} ${ft['avg_cost']:<11.4f} {ft['avg_pass_rate']:<9.1f}%"
                )

    return 0


if __name__ == "__main__":
    sys.exit(main())
