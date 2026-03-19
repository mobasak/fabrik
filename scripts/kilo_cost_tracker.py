#!/usr/bin/env python3
"""
Kilo Cost Tracker - Extract and analyze agent run costs.

Parses agent transcripts and usage logs to track:
- Token costs (input/output)
- Execution duration
- Agent model used
- Phase type (implementation/verification/review)
- Success rate
- Cost per commit

Usage:
    python scripts/kilo_cost_tracker.py [--project PATH] [--since DATE] [--format json|table]
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

# Model pricing (per 1M tokens)
MODEL_PRICING = {
    "claude-sonnet-4.6": {"input": 3.00, "output": 15.00},
    "claude-opus-4.6": {"input": 15.00, "output": 75.00},
    "gpt-5.4": {"input": 2.50, "output": 10.00},
    "gpt-5.2-pro": {"input": 5.00, "output": 15.00},
    "deepseek-v3.2": {"input": 0.27, "output": 0.81},
    "gemini-3.1-pro": {"input": 1.25, "output": 5.00},
}


def parse_transcript(transcript_path: Path) -> dict:
    """Parse a transcript file for cost metrics."""
    content = transcript_path.read_text()
    filename = transcript_path.name

    # Parse filename: 20260318-224345-T4-Pro11-sonnet46-exit0.txt
    match = re.match(r"(\d{8})-(\d{6})-([^-]+)-([^-]+)-([^-]+)-exit(\d+)\.txt", filename)
    if not match:
        return {}

    date_str, time_str, tier, rank, model, exit_code = match.groups()

    # Extract metrics from content
    metrics = {
        "timestamp": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}T{time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}",
        "agent": f"{tier}-{rank}-{model}",
        "tier": tier,
        "model": model,
        "exit_code": int(exit_code),
        "transcript_size": len(content),
    }

    # Detect phase type from prompt patterns (check actual content, not just keywords)
    if "code · " in content[:200]:  # Kilo header indicates code agent
        # Check for verification fix pattern in first 500 chars
        first_500 = content[:500].lower()
        if "verification" in first_500 or "traycer verification" in first_500:
            metrics["phase_type"] = "verification_fix"
        elif "code review" in first_500 or "review issues" in first_500:
            metrics["phase_type"] = "review_fix"
        else:
            metrics["phase_type"] = "implementation"
    else:
        metrics["phase_type"] = "unknown"

    # Extract gate results
    fg_match = re.search(r"FG_PRE=(\w+).*FG_POST=(\w+)", content)
    if fg_match:
        metrics["fg_pre"] = fg_match.group(1)
        metrics["fg_post"] = fg_match.group(2)

    # Extract issues agent faced
    issues = []
    if "[FAIL]" in content:
        fail_matches = re.findall(r"\[FAIL\]\s*(\w+)", content)
        issues.extend([f"FAIL:{m}" for m in fail_matches])
    if "FAILED tests/" in content:
        test_fails = re.findall(r"FAILED (tests/[^\s]+)", content)
        issues.extend([f"TEST:{t.split('::')[-1][:30]}" for t in test_fails])
    if "error:" in content.lower():
        issues.append("ERROR:detected")
    if "Comment" in content and "Fix Comment" in content:
        comment_count = len(re.findall(r"\[x\] Fix Comment", content))
        if comment_count:
            issues.append(f"VERIFY:{comment_count}_comments_fixed")
    metrics["issues_faced"] = issues
    metrics["issue_count"] = len(issues)

    # Count tool calls (approximate)
    metrics["tool_calls"] = (
        content.count("→ Read") + content.count("⚙ apply_patch") + content.count("$ ")
    )

    # Estimate tokens (rough: 4 chars ≈ 1 token)
    metrics["estimated_output_tokens"] = len(content) // 4

    return metrics


def estimate_cost(metrics: dict) -> float:
    """Estimate cost based on model and token count."""
    model = metrics.get("model", "")
    output_tokens = metrics.get("estimated_output_tokens", 0)

    # Map model shorthand to full name
    model_map = {
        "sonnet46": "claude-sonnet-4.6",
        "opus46": "claude-opus-4.6",
        "gpt54": "gpt-5.4",
        "gpt52pro": "gpt-5.2-pro",
        "deepseek32": "deepseek-v3.2",
        "gemini31": "gemini-3.1-pro",
    }

    full_model = model_map.get(model, model)
    pricing = MODEL_PRICING.get(full_model, {"input": 3.0, "output": 15.0})

    # Estimate input tokens as 2x output (typical for coding tasks)
    input_tokens = output_tokens * 2

    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
    return round(cost, 4)


def analyze_project(project_path: Path, since: datetime | None = None) -> list[dict]:
    """Analyze all transcripts in a project."""
    transcripts_dir = project_path / ".droid" / "transcripts"
    if not transcripts_dir.exists():
        return []

    results = []
    for transcript in sorted(transcripts_dir.glob("*.txt")):
        metrics = parse_transcript(transcript)
        if not metrics:
            continue

        # Filter by date if specified
        if since:
            ts = datetime.fromisoformat(metrics["timestamp"])
            if ts < since:
                continue

        metrics["estimated_cost"] = estimate_cost(metrics)
        results.append(metrics)

    return results


def summarize(results: list[dict]) -> dict:
    """Generate summary statistics."""
    if not results:
        return {}

    total_cost = sum(r.get("estimated_cost", 0) for r in results)
    total_runs = len(results)
    success_runs = sum(1 for r in results if r.get("exit_code") == 0)

    by_phase = {}
    for r in results:
        pt = r.get("phase_type", "unknown")
        if pt not in by_phase:
            by_phase[pt] = {"runs": 0, "cost": 0}
        by_phase[pt]["runs"] += 1
        by_phase[pt]["cost"] += r.get("estimated_cost", 0)

    by_agent = {}
    for r in results:
        agent = r.get("agent", "unknown")
        if agent not in by_agent:
            by_agent[agent] = {"runs": 0, "cost": 0}
        by_agent[agent]["runs"] += 1
        by_agent[agent]["cost"] += r.get("estimated_cost", 0)

    # Aggregate issues
    all_issues: dict[str, int] = {}
    for r in results:
        for issue in r.get("issues_faced", []):
            issue_type = issue.split(":")[0]
            all_issues[issue_type] = all_issues.get(issue_type, 0) + 1

    return {
        "total_runs": total_runs,
        "success_rate": round(success_runs / total_runs * 100, 1) if total_runs else 0,
        "total_cost": round(total_cost, 4),
        "avg_cost_per_run": round(total_cost / total_runs, 4) if total_runs else 0,
        "by_phase_type": by_phase,
        "by_agent": by_agent,
        "issues_summary": all_issues,
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze Kilo agent costs")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="Project path")
    parser.add_argument("--since", type=str, help="Filter since date (YYYY-MM-DD)")
    parser.add_argument("--format", choices=["json", "table"], default="table")
    args = parser.parse_args()

    since = datetime.fromisoformat(args.since) if args.since else None
    results = analyze_project(args.project, since)
    summary = summarize(results)

    if args.format == "json":
        print(json.dumps({"runs": results, "summary": summary}, indent=2))
    else:
        print(f"\n{'=' * 60}")
        print(f"KILO COST ANALYSIS - {args.project}")
        print(f"{'=' * 60}")
        print(f"Total Runs: {summary.get('total_runs', 0)}")
        print(f"Success Rate: {summary.get('success_rate', 0)}%")
        print(f"Total Cost: ${summary.get('total_cost', 0):.4f}")
        print(f"Avg Cost/Run: ${summary.get('avg_cost_per_run', 0):.4f}")

        print(f"\n{'─' * 40}")
        print("BY PHASE TYPE:")
        for pt, data in summary.get("by_phase_type", {}).items():
            print(f"  {pt}: {data['runs']} runs, ${data['cost']:.4f}")

        print(f"\n{'─' * 40}")
        print("BY AGENT:")
        for agent, data in summary.get("by_agent", {}).items():
            print(f"  {agent}: {data['runs']} runs, ${data['cost']:.4f}")

        issues = summary.get("issues_summary", {})
        if issues:
            print(f"\n{'─' * 40}")
            print("ISSUES FACED BY AGENTS:")
            for issue_type, count in sorted(issues.items(), key=lambda x: -x[1]):
                print(f"  {issue_type}: {count}x")
        print()


if __name__ == "__main__":
    main()
